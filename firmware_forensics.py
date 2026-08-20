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
import hashlib

from db import get_conn, now
from ledger import append_event

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE_DIR = os.path.join(HERE, "firmware")

BASELINE_ELF = os.path.join(FIRMWARE_DIR, "firmware_baseline.elf")
BASELINE_BIN = os.path.join(FIRMWARE_DIR, "firmware_baseline.bin")
TAMPERED_ELF = os.path.join(FIRMWARE_DIR, "firmware_tampered.elf")
TAMPERED_BIN = os.path.join(FIRMWARE_DIR, "firmware_tampered.bin")

# ======================================================================
# All nodes in the system — dropdown will show all of them
# ======================================================================
ALL_NODES = ["RTU1", "BCU1", "BCU2", "RELAY1", "RELAY2", "RELAY3", "METER1", "METER2", "RELAY-02"]

# Map every node to the same baseline/tampered binaries (for demo).
# In a full deployment, each node would have its own compiled image.
FIRMWARE_MAP = {}
for node in ALL_NODES:
    FIRMWARE_MAP[node] = {
        "baseline_elf": BASELINE_ELF,
        "baseline_bin": BASELINE_BIN,
        "tampered_elf": TAMPERED_ELF,
        "tampered_bin": TAMPERED_BIN,
    }
DEFAULT_NODE = "RELAY-02"

# ----------------------------------------------------------------------
# Tool paths (hardcoded for Windows)
# ----------------------------------------------------------------------
QEMU_BIN = "C:/Program Files/qemu/qemu-system-arm.exe"
if not os.path.exists(QEMU_BIN):
    QEMU_BIN = shutil.which("qemu-system-arm") or QEMU_BIN

GHIDRA_HOME = "C:/ghidra/ghidra_12.1.3_PUBLIC"
if not os.path.exists(GHIDRA_HOME):
    GHIDRA_HOME = os.environ.get("GHIDRA_HOME") or GHIDRA_HOME

GHIDRA_PROJECT_DIR = "C:/ghidra_project"
GHIDRA_PROJECT_NAME = "GridSentinel"
GHIDRA_SCRIPT = os.path.join(HERE, "ghidra_scripts")

NM_BIN = shutil.which("arm-none-eabi-nm")
BINWALK_BIN = shutil.which("binwalk")
YARA_BIN = shutil.which("yara")

# ----------------------------------------------------------------------
# Helper to check if a file exists
# ----------------------------------------------------------------------
def _exists(p):
    return p if p and os.path.exists(p) else None


def tool_status():
    """What's actually available on this machine."""
    analyze_headless = None
    if GHIDRA_HOME and os.path.exists(GHIDRA_HOME):
        candidate = os.path.join(GHIDRA_HOME, "support", "analyzeHeadless.bat")
        if os.path.exists(candidate):
            analyze_headless = candidate
        else:
            candidate2 = os.path.join(GHIDRA_HOME, "support", "analyzeHeadless")
            if os.path.exists(candidate2):
                analyze_headless = candidate2

    ghidra_gui = None
    if GHIDRA_HOME and os.path.exists(GHIDRA_HOME):
        gui_candidate = os.path.join(GHIDRA_HOME, "ghidraRun.bat")
        if os.path.exists(gui_candidate):
            ghidra_gui = gui_candidate
        else:
            gui_candidate2 = os.path.join(GHIDRA_HOME, "ghidraRun")
            if os.path.exists(gui_candidate2):
                ghidra_gui = gui_candidate2
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
    os.makedirs(GHIDRA_PROJECT_DIR, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        out_json = os.path.join(tmp, "functions.json")
        cmd = [
            analyze_headless, GHIDRA_PROJECT_DIR, GHIDRA_PROJECT_NAME,
            "-import", elf_path,
            "-overwrite",
            "-scriptPath", GHIDRA_SCRIPT,
            "-postScript", "ListFunctions.py", out_json,
        ]
        try:
            # Add timeout to prevent hanging
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)  # 30 sec timeout
            if proc.returncode != 0:
                return None
            with open(out_json) as f:
                return json.load(f)
        except subprocess.TimeoutExpired:
            return None
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
    cmd = [QEMU_BIN, "-M", "lm3s6965evb", "-nographic", "-kernel", elf_path, "-semihosting"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 2)
        return proc.stdout
    except subprocess.TimeoutExpired as e:
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
# NEW: Comprehensive full static analysis (metadata, unpacking, YARA, CFG)
# ----------------------------------------------------------------------------
def get_file_hash(file_path):
    """SHA-256 hash of a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha.update(chunk)
    return sha.hexdigest()


def get_elf_architecture(elf_path):
    """Try to read architecture from ELF header using readelf if available."""
    readelf = shutil.which("arm-none-eabi-readelf")
    if readelf:
        try:
            out = subprocess.run([readelf, "-h", elf_path], capture_output=True, text=True, timeout=5)
            for line in out.stdout.splitlines():
                if "Machine" in line:
                    if "ARM" in line:
                        return "ARM Cortex-M3 (32-bit)"
                    return line.split(":")[-1].strip()
        except:
            pass
    return "ARM (Cortex-M3) [detected from ELF]"


def run_binwalk(file_path):
    """Run binwalk and return summary."""
    if not BINWALK_BIN:
        return {"available": False, "output": "binwalk not installed"}
    try:
        proc = subprocess.run([BINWALK_BIN, "--signature", file_path], capture_output=True, text=True, timeout=10)
        output = proc.stdout.strip()
        if not output:
            return {"available": True, "output": "No embedded filesystems or known signatures found."}
        # Simplify output: just show lines with signatures
        lines = [l for l in output.splitlines() if "DECIMAL" not in l and "---" not in l and l.strip()]
        return {"available": True, "output": "\n".join(lines) if lines else "No signatures found."}
    except Exception as e:
        return {"available": True, "output": f"Error running binwalk: {e}"}


# Sample YARA rules (embedded for demo)
YARA_RULES = """
rule ICS_Trojan_Backdoor {
    meta:
        description = "Detects the injected diag_selftest_ext function signature"
        author = "GridSentinel"
    strings:
        $diag = "diag_selftest_ext"
    condition:
        $diag
}
rule Suspicious_Relay_Close {
    meta:
        description = "Detects strings related to unauthorized relay override"
    strings:
        $relay = "RELAY_FORCE_CLOSE"
    condition:
        $relay
}
"""
_YARA_RULES_FILE = None

def _get_yara_rules_file():
    global _YARA_RULES_FILE
    if _YARA_RULES_FILE is None:
        fd, path = tempfile.mkstemp(suffix=".yar", text=True)
        with os.fdopen(fd, "w") as f:
            f.write(YARA_RULES)
        _YARA_RULES_FILE = path
    return _YARA_RULES_FILE


def run_yara(file_path):
    """Run YARA scan using embedded rules."""
    if not YARA_BIN:
        return {"available": False, "output": "yara not installed"}
    rules_file = _get_yara_rules_file()
    try:
        proc = subprocess.run([YARA_BIN, rules_file, file_path], capture_output=True, text=True, timeout=10)
        output = proc.stdout.strip()
        if output:
            matches = [line.strip() for line in output.splitlines() if line.strip()]
            return {"available": True, "matches": matches}
        else:
            return {"available": True, "matches": []}
    except Exception as e:
        return {"available": True, "error": str(e)}


def run_full_static_analysis(node_id):
    """Comprehensive static analysis: metadata, unpacking, YARA, CFG summary."""
    paths = get_firmware_paths(node_id)
    conn = get_conn()
    tampered = is_node_tampered(conn, node_id)
    conn.close()
    current_elf = paths["tampered_elf"] if tampered else paths["baseline_elf"]
    current_bin = paths["tampered_bin"] if tampered else paths["baseline_bin"]

    # 1. Metadata
    arch = get_elf_architecture(current_elf)
    size = os.path.getsize(current_bin)
    with open(current_bin, "rb") as f:
        entropy = _shannon_entropy(f.read())
    golden_hash = get_file_hash(paths["baseline_bin"])
    current_hash = get_file_hash(current_bin)
    hash_match = (golden_hash == current_hash)

    # 2. Unpacking (binwalk)
    binwalk_result = run_binwalk(current_bin)

    # 3. YARA
    yara_result = run_yara(current_bin)

    # 4. CFG summary (use Ghidra or nm)
    ghidra_result = static_analysis_ghidra(paths["baseline_elf"], current_elf)
    nm_result = None
    if ghidra_result:
        func_count = ghidra_result["current_function_count"]
        added_funcs = ghidra_result["added_functions"]
        removed_funcs = ghidra_result["removed_functions"]
        cfg_status = "Clean" if not added_funcs else f"Added functions: {', '.join(added_funcs)}"
        anomaly = "No anomalies" if not added_funcs else "Added functions detected (potential backdoor)"
    else:
        # fallback nm
        nm_result = static_analysis_fallback(paths["baseline_elf"], current_elf, paths["baseline_bin"], current_bin)
        if "added_functions" in nm_result:
            added_funcs = nm_result["added_functions"]
            removed_funcs = nm_result.get("removed_functions", [])
            func_count = "unknown"
            cfg_status = "Clean" if not added_funcs else f"Added functions: {', '.join(added_funcs)}"
            anomaly = "No anomalies" if not added_funcs else "Added functions detected"
        else:
            added_funcs = []
            removed_funcs = []
            func_count = "unknown"
            cfg_status = "Unable to determine (nm not available)"
            anomaly = "Unknown"

    # 5. Overall verdict
    verdict = "CLEAN"
    warnings = []
    if not hash_match:
        verdict = "TROJAN_DETECTED"
        warnings.append("Firmware hash mismatch (golden vs current)")
    if added_funcs:
        verdict = "TROJAN_DETECTED"
        warnings.append(f"Added function(s): {', '.join(added_funcs)}")
    if yara_result.get("matches"):
        verdict = "TROJAN_DETECTED"
        warnings.append(f"YARA rule matches: {', '.join(yara_result['matches'])}")

    return {
        "tool": "full_static_analysis",
        "verdict": verdict,
        "warnings": warnings,
        "metadata": {
            "architecture": arch,
            "file_size_bytes": size,
            "entropy": round(entropy, 3),
            "golden_hash": golden_hash[:16] + "...",
            "current_hash": current_hash[:16] + "...",
            "hash_match": hash_match,
        },
        "unpacking": binwalk_result,
        "yara": yara_result,
        "cfg": {
            "function_count": func_count,
            "added_functions": added_funcs,
            "removed_functions": removed_funcs,
            "status": cfg_status,
            "anomaly": anomaly,
        },
        "raw": {
            "ghidra": ghidra_result,
            "nm_fallback": nm_result
        }
    }


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