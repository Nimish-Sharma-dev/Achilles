"""
firmware_forensics.py — static + dynamic firmware analysis pipeline.

This is real tooling against real compiled firmware, not a simulation of
one. The demo firmware (see firmware/) is genuine bare-metal ARM Cortex-M3
code, cross-compiled with arm-none-eabi-gcc, that actually boots under
QEMU's `lm3s6965evb` machine model. `firmware/main_tampered.c` differs from
`firmware/main_baseline.c` by exactly one injected function — an
unauthorized relay-close override disguised as a diagnostics routine —
so every layer below has a genuine signal to find, not a scripted one.

STATIC ANALYSIS — two tiers, same interface:
  1. Ghidra headless (if GHIDRA_HOME is set and analyzeHeadless exists):
     runs ghidra_scripts/ListFunctions.py against both binaries inside a
     persistent Ghidra project and diffs the decompiled function lists.
  2. Fallback: arm-none-eabi-nm symbol diff + raw byte-size/Shannon-entropy
     comparison. This is a *real* tool call, not a mock — it's just a
     lighter-weight one than Ghidra, in the same spirit as the ledger
     hash-chain standing in for Hyperledger Fabric. Use this tier if
     Ghidra isn't installed on the demo machine.

DYNAMIC ANALYSIS — boots both firmware images under real QEMU
(`qemu-system-arm -M lm3s6965evb -nographic`), captures actual UART
output, and diffs the two transcripts line by line. This genuinely
executes the code; nothing here is precomputed or faked.

Every scan writes to `firmware_scans`, raises an alert into the same
`alerts` table the telemetry-based detectors use (so it shows up on the
main dashboard and drives the threat level), and logs a ledger entry.

Run standalone for a quick check:  python firmware_forensics.py
"""

import os
import re
import json
import math
import shutil
import subprocess
import tempfile

from db import get_conn, now
from ledger import append_event

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.join(HERE, "firmware")

BASELINE_ELF = os.path.join(FIRMWARE_DIR, "firmware_baseline.elf")
BASELINE_BIN = os.path.join(FIRMWARE_DIR, "firmware_baseline.bin")
TAMPERED_ELF = os.path.join(FIRMWARE_DIR, "firmware_tampered.elf")
TAMPERED_BIN = os.path.join(FIRMWARE_DIR, "firmware_tampered.bin")

# The demo's one real firmware pair is associated with RELAY-02 (the same
# node attack_injector.py's firmware_tamper attack targets in the README's
# demo script). Every other node reuses the baseline as a stand-in — one
# real, fully-wired example is worth more for a 24h demo than N shallow
# ones. Extend FIRMWARE_MAP if you compile more per-node images later.
FIRMWARE_MAP = {
    "RELAY-02": {"baseline_elf": BASELINE_ELF, "baseline_bin": BASELINE_BIN,
                 "tampered_elf": TAMPERED_ELF, "tampered_bin": TAMPERED_BIN},
}
DEFAULT_NODE = "RELAY-02"

# ======================================================================
# HARDCODED PATHS FOR WINDOWS DEMO MACHINE
# ======================================================================
# QEMU
QEMU_BIN = "C:/Program Files/qemu/qemu-system-arm.exe"
if not os.path.exists(QEMU_BIN):
    # fallback to PATH search
    QEMU_BIN = shutil.which("qemu-system-arm") or QEMU_BIN

# Ghidra
GHIDRA_HOME = "C:/ghidra/ghidra_12.1.3_PUBLIC"
if not os.path.exists(GHIDRA_HOME):
    # fallback to environment variable
    GHIDRA_HOME = os.environ.get("GHIDRA_HOME") or GHIDRA_HOME

# Ghidra project
GHIDRA_PROJECT_DIR = "C:/ghidra_project"
GHIDRA_PROJECT_NAME = "GridSentinel"
GHIDRA_SCRIPT = os.path.join(HERE, "ghidra_scripts")

# nm fallback – we keep it but it's not required for Ghidra tier
NM_BIN = shutil.which("arm-none-eabi-nm")

# ----------------------------------------------------------------------
# Helper to check if a file exists (for tool_status)
# ----------------------------------------------------------------------
def _exists(p):
    return p if p and os.path.exists(p) else None


def tool_status():
    """What's actually available on this machine — surfaced in the UI so
    the presenter always knows which tier is about to run."""
    # Ghidra headless
    analyze_headless = None
    if GHIDRA_HOME and os.path.exists(GHIDRA_HOME):
        candidate = os.path.join(GHIDRA_HOME, "support", "analyzeHeadless.bat")
        if os.path.exists(candidate):
            analyze_headless = candidate
        else:
            # try without .bat (Linux style) – just in case
            candidate2 = os.path.join(GHIDRA_HOME, "support", "analyzeHeadless")
            if os.path.exists(candidate2):
                analyze_headless = candidate2

    # Ghidra GUI
    ghidra_gui = None
    if GHIDRA_HOME and os.path.exists(GHIDRA_HOME):
        gui_candidate = os.path.join(GHIDRA_HOME, "ghidraRun.bat")
        if os.path.exists(gui_candidate):
            ghidra_gui = gui_candidate
        else:
            gui_candidate2 = os.path.join(GHIDRA_HOME, "ghidraRun")
            if os.path.exists(gui_candidate2):
                ghidra_gui = gui_candidate2

    # Also check PATH
    if not ghidra_gui:
        ghidra_gui = shutil.which("ghidraRun.bat") or shutil.which("ghidraRun")

    return {
        "nm": _exists(NM_BIN),
        "qemu": _exists(QEMU_BIN),
        "ghidra_headless": analyze_headless,
        "ghidra_gui": ghidra_gui,
    }


def get_firmware_paths(node_id):
    return FIRMWARE_MAP.get(node_id, FIRMWARE_MAP[DEFAULT_NODE])


def is_node_tampered(conn, node_id):
    row = conn.execute(
        "SELECT 1 FROM attacks WHERE node_id=? AND attack_type='firmware_tamper' AND active=1", (node_id,)
    ).fetchone()
    return bool(row)


# ----------------------------------------------------------------------------
# Tier 2 (guaranteed) static analysis — real nm + byte/entropy diff
# ----------------------------------------------------------------------------
def _shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq if c)


def _nm_functions(elf_path):
    """Defined function symbols (code section, types T/t) via arm-none-eabi-nm."""
    if not NM_BIN or not os.path.exists(NM_BIN):
        return set()
    out = subprocess.run([NM_BIN, "--defined-only", elf_path], capture_output=True, text=True, timeout=15)
    funcs = set()
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in ("T", "t"):
            funcs.add(parts[2])
    return funcs


def static_analysis_fallback(baseline_elf, current_elf, baseline_bin, current_bin):
    if not NM_BIN:
        return {"tool": "unavailable", "error": "arm-none-eabi-nm not found on PATH"}

    base_funcs = _nm_functions(baseline_elf)
    cur_funcs = _nm_functions(current_elf)
    added = sorted(cur_funcs - base_funcs)
    removed = sorted(base_funcs - cur_funcs)

    with open(baseline_bin, "rb") as f:
        base_bytes = f.read()
    with open(current_bin, "rb") as f:
        cur_bytes = f.read()

    base_entropy = round(_shannon_entropy(base_bytes), 3)
    cur_entropy = round(_shannon_entropy(cur_bytes), 3)

    verdict = "CLEAN"
    if added or removed:
        verdict = "TROJAN_DETECTED" if added else "SUSPICIOUS"

    return {
        "tool": "nm_fallback",
        "verdict": verdict,
        "added_functions": added,
        "removed_functions": removed,
        "baseline_size_bytes": len(base_bytes),
        "current_size_bytes": len(cur_bytes),
        "size_delta_bytes": len(cur_bytes) - len(base_bytes),
        "baseline_entropy": base_entropy,
        "current_entropy": cur_entropy,
    }


# ----------------------------------------------------------------------------
# Tier 1 (preferred) static analysis — real Ghidra headless
# ----------------------------------------------------------------------------
def _ghidra_list_functions(elf_path, analyze_headless):
    """Imports elf_path into the persistent Ghidra project (creating it on
    first use), runs ghidra_scripts/ListFunctions.py, and parses the
    function list it writes to a temp JSON file. Returns None on any
    failure so callers can fall back cleanly."""
    os.makedirs(GHIDRA_PROJECT_DIR, exist_ok=True)
    program_name = os.path.basename(elf_path)

    with tempfile.TemporaryDirectory() as tmp:
        out_json = os.path.join(tmp, "functions.json")
        # Note: we use the full path to analyzeHeadless.bat (or .sh)
        cmd = [
            analyze_headless, GHIDRA_PROJECT_DIR, GHIDRA_PROJECT_NAME,
            "-import", elf_path,
            "-overwrite",
            "-scriptPath", GHIDRA_SCRIPT,
            "-postScript", "ListFunctions.py", out_json,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
            with open(out_json) as f:
                return json.load(f)
        except Exception:
            return None


def static_analysis_ghidra(baseline_elf, current_elf):
    analyze_headless = tool_status()["ghidra_headless"]
    if not analyze_headless:
        return None

    base_funcs = _ghidra_list_functions(baseline_elf, analyze_headless)
    cur_funcs = _ghidra_list_functions(current_elf, analyze_headless)
    if base_funcs is None or cur_funcs is None:
        return None

    base_names = {f["name"] for f in base_funcs}
    cur_names = {f["name"] for f in cur_funcs}
    added = sorted(cur_names - base_names)
    removed = sorted(base_names - cur_names)

    verdict = "CLEAN"
    if added or removed:
        verdict = "TROJAN_DETECTED" if added else "SUSPICIOUS"

    return {
        "tool": "ghidra_headless",
        "verdict": verdict,
        "added_functions": added,
        "removed_functions": removed,
        "baseline_function_count": len(base_names),
        "current_function_count": len(cur_names),
    }


def run_static_analysis(node_id):
    paths = get_firmware_paths(node_id)
    conn = get_conn()
    tampered = is_node_tampered(conn, node_id)
    conn.close()
    current_elf = paths["tampered_elf"] if tampered else paths["baseline_elf"]
    current_bin = paths["tampered_bin"] if tampered else paths["baseline_bin"]

    result = static_analysis_ghidra(paths["baseline_elf"], current_elf)
    if result is None:
        result = static_analysis_fallback(paths["baseline_elf"], current_elf, paths["baseline_bin"], current_bin)

    _persist_scan(node_id, "STATIC", result)
    return result


# ----------------------------------------------------------------------------
# Dynamic analysis — real QEMU boot + UART transcript diff
# ----------------------------------------------------------------------------
def _qemu_capture(elf_path, seconds=4):
    if not QEMU_BIN or not os.path.exists(QEMU_BIN):
        return None
    # Use the full path and ensure it works on Windows
    cmd = [QEMU_BIN, "-M", "lm3s6965evb", "-nographic", "-kernel", elf_path, "-semihosting"]
    # No -serial stdio – use semihosting for output
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 2)
        return proc.stdout
    except subprocess.TimeoutExpired as e:
        # QEMU may not exit; we kill it and return captured stdout
        return (e.stdout or "") if isinstance(e.stdout, str) else (e.stdout or b"").decode(errors="ignore")


def run_dynamic_analysis(node_id, seconds=4):
    paths = get_firmware_paths(node_id)
    conn = get_conn()
    tampered = is_node_tampered(conn, node_id)
    conn.close()
    current_elf = paths["tampered_elf"] if tampered else paths["baseline_elf"]

    if not QEMU_BIN or not os.path.exists(QEMU_BIN):
        result = {"tool": "unavailable", "error": "qemu-system-arm not found"}
        _persist_scan(node_id, "DYNAMIC", result)
        return result

    base_out = _qemu_capture(paths["baseline_elf"], seconds) or ""
    cur_out = _qemu_capture(current_elf, seconds) or ""

    base_lines = [l.strip() for l in base_out.splitlines() if l.strip()]
    cur_lines = [l.strip() for l in cur_out.splitlines() if l.strip()]
    extra_lines = [l for l in cur_lines if l not in base_lines]

    suspicious_markers = ["OVERRIDE", "FORCE_CLOSE", "UNAUTHORIZED", "CLOSED"]
    flagged = [l for l in extra_lines if any(m in l for m in suspicious_markers)]

    verdict = "CLEAN"
    if flagged:
        verdict = "TROJAN_DETECTED"
    elif extra_lines:
        verdict = "SUSPICIOUS"

    result = {
        "tool": "qemu",
        "verdict": verdict,
        "baseline_transcript": base_lines,
        "current_transcript": cur_lines,
        "extra_lines": extra_lines,
        "flagged_lines": flagged,
    }
    _persist_scan(node_id, "DYNAMIC", result)
    return result


# ----------------------------------------------------------------------------
# Persistence — feeds firmware_scans + main alert feed + ledger
# ----------------------------------------------------------------------------
def _persist_scan(node_id, scan_type, result):
    verdict = result.get("verdict", "CLEAN")
    tool = result.get("tool", "unknown")
    conn = get_conn()
    conn.execute(
        "INSERT INTO firmware_scans (node_id, ts, scan_type, tool, verdict, details) VALUES (?,?,?,?,?,?)",
        (node_id, now(), scan_type, tool, verdict, json.dumps(result, default=str)),
    )

    if verdict in ("SUSPICIOUS", "TROJAN_DETECTED"):
        severity = "CRITICAL" if verdict == "TROJAN_DETECTED" else "WARN"
        message = f"{scan_type} firmware scan ({tool}) flagged {node_id}: {verdict}"
        if result.get("added_functions"):
            message += f" — extra function(s): {', '.join(result['added_functions'])}"
        if result.get("flagged_lines"):
            message += f" — runtime evidence: {result['flagged_lines'][0]}"
        conn.execute(
            "INSERT INTO alerts (node_id, ts, severity, category, message) VALUES (?,?,?,?,?)",
            (node_id, now(), severity, "FIRMWARE", message),
        )
        if severity == "CRITICAL":
            conn.execute("UPDATE nodes SET status='CRITICAL' WHERE id=? AND status != 'QUARANTINED'", (node_id,))

    conn.commit()
    conn.close()
    append_event("FIRMWARE_SCAN", {"node_id": node_id, "scan_type": scan_type, "tool": tool, "verdict": verdict})


def get_scan_history(node_id=None, limit=20):
    conn = get_conn()
    if node_id:
        rows = conn.execute(
            "SELECT * FROM firmware_scans WHERE node_id=? ORDER BY id DESC LIMIT ?", (node_id, limit)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM firmware_scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print("Tool status:", json.dumps(tool_status(), indent=2))
    print("\n--- Static analysis (RELAY-02) ---")
    print(json.dumps(run_static_analysis("RELAY-02"), indent=2)[:2000])
    print("\n--- Dynamic analysis (RELAY-02) ---")
    print(json.dumps(run_dynamic_analysis("RELAY-02"), indent=2)[:2000])