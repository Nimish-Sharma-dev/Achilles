"""
pages/1_🔬_Firmware_Forensics.py

Streamlit auto-discovers files in pages/ next to dashboard.py and adds them
to the sidebar nav — run `streamlit run dashboard.py` as usual and this
page appears automatically in the left sidebar.

Two real tools, wired for a live demo:
  - STATIC:  Ghidra headless (if installed) diffing function lists against
             the golden baseline; automatic fallback to a real
             arm-none-eabi-nm symbol diff + byte/entropy diff if Ghidra
             isn't on this machine.
  - DYNAMIC: real QEMU boot of both firmware images (`qemu-system-arm -M
             lm3s6965evb -nographic`), UART transcript diffed line by line.
  - GUI:     a button that launches the actual Ghidra desktop app in its
             own window, pointed at the pre-imported project, for a live
             on-stage decompiler walkthrough. See ghidra_setup.sh — run
             that once before the demo so the project already exists.
"""

import json
import subprocess
import time

import streamlit as st

import firmware_forensics as ff
from db import get_conn
from ledger import append_event

st.set_page_config(page_title="GridSentinel — Firmware Forensics", layout="wide")

COLORS = {
    "bg": "#0A0E14", "panel": "#12161F", "border": "#1F2733",
    "text": "#E6EDF3", "text_dim": "#6B7684",
    "healthy": "#00D9A3", "warn": "#F5A623", "critical": "#FF4757", "accent": "#3DA5FF",
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ background-color: {COLORS['bg']} !important; color: {COLORS['text']}; }}
#MainMenu, footer, header {{visibility: hidden;}}
.wordmark {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.8rem; }}
.eyebrow {{ font-family:'JetBrains Mono',monospace; color:{COLORS['accent']}; letter-spacing:.15em;
            font-size:.75rem; text-transform:uppercase; }}
.panel {{ background:{COLORS['panel']}; border:1px solid {COLORS['border']}; border-radius:6px; padding:16px 18px; }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
.status-pill {{ display:inline-block; font-family:'JetBrains Mono',monospace; font-size:.85rem; font-weight:700;
                 letter-spacing:.08em; padding:5px 14px; border-radius:3px; }}
.transcript {{ font-family:'JetBrains Mono',monospace; font-size:.78rem; background:#000;
               border:1px solid {COLORS['border']}; border-radius:4px; padding:10px; max-height:280px; overflow-y:auto; }}
.line-extra {{ color:{COLORS['critical']}; }}
.line-normal {{ color:{COLORS['text_dim']}; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="eyebrow">GRIDSENTINEL // STATIC + DYNAMIC FIRMWARE ANALYSIS</div>', unsafe_allow_html=True)
st.markdown('<div class="wordmark">FIRMWARE FORENSICS</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# TOOL STATUS
# ----------------------------------------------------------------------------
status = ff.tool_status()
cols = st.columns(4)
tool_labels = [("nm (fallback static)", status["nm"]), ("qemu (dynamic)", status["qemu"]),
               ("ghidra headless (preferred static)", status["ghidra_headless"]),
               ("ghidra GUI", status["ghidra_gui"])]
for col, (label, path) in zip(cols, tool_labels):
    ok = bool(path)
    color = COLORS["healthy"] if ok else COLORS["warn"]
    state = "READY" if ok else "NOT FOUND"
    col.markdown(f'''<div class="panel" style="text-align:center;">
        <div class="mono" style="font-size:.7rem;color:{COLORS['text_dim']};">{label.upper()}</div>
        <div class="status-pill mono" style="background:{color}22;color:{color};border:1px solid {color};margin-top:6px;">{state}</div>
        </div>''', unsafe_allow_html=True)

if not status["ghidra_headless"]:
    st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};margin-top:8px;">'
                f'Ghidra not detected — static analysis will use the nm/entropy fallback tier automatically. '
                f'Set the <code>GHIDRA_HOME</code> environment variable and re-run to enable Ghidra headless. '
                f'See ghidra_setup.sh.</div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# TARGET SELECTION
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">TARGET</div>', unsafe_allow_html=True)
node_id = st.selectbox("Node under inspection", list(ff.FIRMWARE_MAP.keys()), index=0)

conn = get_conn()
currently_tampered = ff.is_node_tampered(conn, node_id)
conn.close()

c1, c2 = st.columns(2)
with c1:
    st.markdown(f'''<div class="panel">
        <div class="mono" style="font-size:.75rem;color:{COLORS['text_dim']};">DEPLOYED FIRMWARE STATE</div>
        <div class="status-pill mono" style="margin-top:8px;background:{(COLORS['critical'] if currently_tampered else COLORS['healthy'])}22;
             color:{(COLORS['critical'] if currently_tampered else COLORS['healthy'])};
             border:1px solid {(COLORS['critical'] if currently_tampered else COLORS['healthy'])};">
             {'TAMPERED (attack active)' if currently_tampered else 'BASELINE (clean)'}</div>
        <div class="mono" style="font-size:.7rem;color:{COLORS['text_dim']};margin-top:8px;">
             Reflects attack_injector.py's live state for this node — trigger
             <code>python attack_injector.py --node {node_id} --attack firmware_tamper</code>
             from a terminal, then re-run the scans below.</div>
        </div>''', unsafe_allow_html=True)

with c2:
    st.markdown("**Quick trigger (for rehearsal without a terminal)**")
    tcol1, tcol2 = st.columns(2)
    if tcol1.button("⚠️ Inject firmware_tamper", disabled=currently_tampered, use_container_width=True):
        conn = get_conn()
        conn.execute("INSERT INTO attacks (ts, node_id, attack_type, active) VALUES (?,?,?,1)",
                     (time.time(), node_id, "firmware_tamper"))
        conn.commit(); conn.close()
        append_event("ATTACK_INJECTED", {"node_id": node_id, "attack_type": "firmware_tamper", "via": "forensics_page"})
        st.rerun()
    if tcol2.button("Clear / restore baseline", disabled=not currently_tampered, use_container_width=True):
        conn = get_conn()
        conn.execute("UPDATE attacks SET active=0 WHERE node_id=? AND attack_type='firmware_tamper'", (node_id,))
        conn.commit(); conn.close()
        append_event("ATTACK_CLEARED", {"node_id": node_id, "via": "forensics_page"})
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# GHIDRA GUI LAUNCH — real native window, for the live decompiler walkthrough
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">LIVE DECOMPILER WALKTHROUGH</div>', unsafe_allow_html=True)
st.markdown("Opens the real Ghidra desktop app in its own window on this machine, "
            "pointed at the pre-imported project (run `ghidra_setup.sh` once before the demo "
            "so both binaries are already imported and analyzed — launching cold mid-demo is slow).")
if st.button("🖥️ Launch Ghidra GUI", type="primary"):
    ghidra_gui = status["ghidra_gui"]
    if not ghidra_gui:
        st.error("ghidraRun not found. Set GHIDRA_HOME or add Ghidra's install dir to PATH.")
    else:
        try:
            subprocess.Popen([ghidra_gui], cwd=ff.GHIDRA_PROJECT_DIR if __import__("os").path.exists(ff.GHIDRA_PROJECT_DIR) else None)
            st.success("Ghidra launching in a new window — open GridSentinelDemo.gpr from the project view "
                       "(created by ghidra_setup.sh) and pick firmware_tampered.elf.")
        except Exception as e:
            st.error(f"Couldn't launch Ghidra: {e}")

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# STATIC ANALYSIS
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">STATIC ANALYSIS — GHIDRA / SYMBOL DIFF</div>', unsafe_allow_html=True)
if st.button("▶ Run static analysis", type="primary"):
    with st.spinner("Diffing function symbols against golden baseline…"):
        result = ff.run_static_analysis(node_id)
    st.session_state["static_result"] = result

if "static_result" in st.session_state:
    r = st.session_state["static_result"]
    verdict = r.get("verdict", "UNKNOWN")
    vcolor = {"CLEAN": COLORS["healthy"], "SUSPICIOUS": COLORS["warn"],
              "TROJAN_DETECTED": COLORS["critical"]}.get(verdict, COLORS["text_dim"])
    st.markdown(f'<span class="status-pill mono" style="background:{vcolor}22;color:{vcolor};'
                f'border:1px solid {vcolor};">VERDICT: {verdict}</span> '
                f'<span class="mono" style="color:{COLORS["text_dim"]};font-size:.8rem;">tool={r.get("tool")}</span>',
                unsafe_allow_html=True)

    sc1, sc2 = st.columns(2)
    with sc1:
        st.markdown("**Added functions (present in scanned firmware, absent from baseline)**")
        added = r.get("added_functions", [])
        if added:
            for fn in added:
                st.markdown(f'<div class="mono" style="color:{COLORS["critical"]};">+ {fn}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};">none</div>', unsafe_allow_html=True)
    with sc2:
        if "baseline_size_bytes" in r:
            st.markdown("**Byte-level / entropy diff**")
            st.markdown(f'''<div class="mono" style="font-size:.8rem;">
                size: {r["baseline_size_bytes"]} → {r["current_size_bytes"]} bytes
                ({"+" if r["size_delta_bytes"]>=0 else ""}{r["size_delta_bytes"]})<br>
                entropy: {r["baseline_entropy"]} → {r["current_entropy"]}
                </div>''', unsafe_allow_html=True)
        elif "baseline_function_count" in r:
            st.markdown("**Ghidra function counts**")
            st.markdown(f'<div class="mono" style="font-size:.8rem;">'
                        f'{r["baseline_function_count"]} → {r["current_function_count"]} functions</div>',
                        unsafe_allow_html=True)

    with st.expander("Raw scan output (JSON)"):
        st.code(json.dumps(r, indent=2), language="json")

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# DYNAMIC ANALYSIS
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">DYNAMIC ANALYSIS — QEMU EMULATION</div>', unsafe_allow_html=True)
st.markdown("Actually boots both firmware images under `qemu-system-arm -M lm3s6965evb -nographic` "
            "and diffs the real UART transcript. Takes a few seconds — QEMU is genuinely executing the code.")
if st.button("▶ Run QEMU emulation", type="primary"):
    with st.spinner("Booting baseline and current firmware under QEMU (≈8s)…"):
        result = ff.run_dynamic_analysis(node_id, seconds=4)
    st.session_state["dynamic_result"] = result

if "dynamic_result" in st.session_state:
    r = st.session_state["dynamic_result"]
    verdict = r.get("verdict", "UNKNOWN")
    vcolor = {"CLEAN": COLORS["healthy"], "SUSPICIOUS": COLORS["warn"],
              "TROJAN_DETECTED": COLORS["critical"]}.get(verdict, COLORS["text_dim"])
    st.markdown(f'<span class="status-pill mono" style="background:{vcolor}22;color:{vcolor};'
                f'border:1px solid {vcolor};">VERDICT: {verdict}</span>', unsafe_allow_html=True)

    dc1, dc2 = st.columns(2)
    with dc1:
        st.markdown("**Baseline UART transcript**")
        lines = r.get("baseline_transcript", [])
        html = "".join(f'<div>{l}</div>' for l in lines) or "<div>(no output captured)</div>"
        st.markdown(f'<div class="transcript">{html}</div>', unsafe_allow_html=True)
    with dc2:
        st.markdown(f"**{node_id} UART transcript**")
        extra = set(r.get("extra_lines", []))
        lines = r.get("current_transcript", [])
        html = "".join(
            f'<div class="{"line-extra" if l in extra else "line-normal"}">{l}</div>' for l in lines
        ) or "<div>(no output captured)</div>"
        st.markdown(f'<div class="transcript">{html}</div>', unsafe_allow_html=True)

    if r.get("flagged_lines"):
        st.markdown(f'<div class="mono" style="color:{COLORS["critical"]};margin-top:10px;">'
                    f'⚠ Runtime evidence of unauthorized behavior:<br>' +
                    "<br>".join(r["flagged_lines"]) + '</div>', unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# SCAN HISTORY
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">SCAN HISTORY</div>', unsafe_allow_html=True)
history = ff.get_scan_history(node_id, limit=15)
if not history:
    st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};">No scans run yet for {node_id}.</div>',
                unsafe_allow_html=True)
for h in history:
    ts = time.strftime("%H:%M:%S", time.localtime(h["ts"]))
    vcolor = {"CLEAN": COLORS["healthy"], "SUSPICIOUS": COLORS["warn"],
              "TROJAN_DETECTED": COLORS["critical"]}.get(h["verdict"], COLORS["text_dim"])
    st.markdown(f'<div class="mono" style="font-size:.78rem;border-left:3px solid {vcolor};padding:4px 10px;">'
                f'[{ts}] {h["scan_type"]} · {h["tool"]} · '
                f'<span style="color:{vcolor};font-weight:700;">{h["verdict"]}</span></div>',
                unsafe_allow_html=True)
