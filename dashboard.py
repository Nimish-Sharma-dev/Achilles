"""
dashboard.py — PERSON C's file.

GridSentinel command-center view. Run with:
    streamlit run dashboard.py

Design direction (see README for the full rationale): dark substation
control-room panel, monospace telemetry, status colors that mirror real
SCADA indicator lights (green/amber/red), and the network graph rendered
as an animated circuit schematic rather than a generic node-link chart —
compromised nodes glow red, quarantined nodes get a dashed containment
ring, and current "flows" along edges inside an active blast radius.

Needs streamlit >= 1.33 for st.fragment(run_every=...). If your installed
version is older: pip install --upgrade streamlit
"""

import time
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import networkx as nx

from db import get_conn
from ledger import get_ledger, verify_chain, append_event
from detection import build_graph, blast_radius
from detection import overall_threat_level
st.set_page_config(page_title="GridSentinel", layout="wide", initial_sidebar_state="expanded")

# ----------------------------------------------------------------------------
# THEME
# ----------------------------------------------------------------------------
COLORS = {
    "bg": "#0A0E14",
    "panel": "#12161F",
    "border": "#1F2733",
    "text": "#E6EDF3",
    "text_dim": "#6B7684",
    "healthy": "#00D9A3",
    "warn": "#F5A623",
    "critical": "#FF4757",
    "quarantined": "#64748B",
    "accent": "#3DA5FF",
}

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500&display=swap');

html, body, [class*="css"] {{
    background-color: {COLORS['bg']} !important;
    color: {COLORS['text']};
    font-family: 'IBM Plex Sans', sans-serif;
}}
#MainMenu, footer, header {{visibility: hidden;}}
.block-container {{ padding-top: 1.2rem; max-width: 1500px; }}

.eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    color: {COLORS['accent']};
    letter-spacing: 0.15em;
    font-size: 0.75rem;
    text-transform: uppercase;
}}
.wordmark {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 2.1rem;
    letter-spacing: -0.01em;
    margin-top: -6px;
}}
.panel {{
    background: {COLORS['panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 16px 18px;
}}
.mono {{ font-family: 'JetBrains Mono', monospace; }}
.status-pill {{
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 4px 12px;
    border-radius: 3px;
}}
.alert-row {{
    border-left: 3px solid {COLORS['border']};
    padding: 6px 10px;
    margin-bottom: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    background: rgba(255,255,255,0.02);
}}
.alert-CRITICAL {{ border-left-color: {COLORS['critical']}; }}
.alert-WARN {{ border-left-color: {COLORS['warn']}; }}
.alert-INFO {{ border-left-color: {COLORS['accent']}; }}
hr {{ border-color: {COLORS['border']}; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# DATA HELPERS
# ----------------------------------------------------------------------------
def load_state():
    conn = get_conn()
    nodes = [dict(r) for r in conn.execute("SELECT * FROM nodes").fetchall()]
    edges = [dict(r) for r in conn.execute("SELECT * FROM edges").fetchall()]
    alerts = [dict(r) for r in conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT 30")]
    conn.close()
    return nodes, edges, alerts


def load_history(node_id, minutes=5):
    conn = get_conn()
    cutoff = time.time() - minutes * 60
    telemetry = conn.execute(
        "SELECT ts, voltage, current, temp FROM telemetry WHERE node_id=? AND ts >= ? ORDER BY ts ASC",
        (node_id, cutoff),
    ).fetchall()
    risk = conn.execute(
        "SELECT ts, risk_score FROM risk_history WHERE node_id=? AND ts >= ? ORDER BY ts ASC",
        (node_id, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in telemetry], [dict(r) for r in risk]


def _dark_line_chart(df, y_cols, colors, title, y_suffix=""):
    fig = go.Figure()
    for col, color in zip(y_cols, colors):
        fig.add_trace(go.Scatter(
            x=df["time"], y=df[col], mode="lines", name=col,
            line=dict(color=color, width=2),
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(family="JetBrains Mono", size=13, color=COLORS["text_dim"])),
        paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
        font=dict(family="JetBrains Mono", size=11, color=COLORS["text"]),
        margin=dict(l=40, r=20, t=40, b=30), height=240,
        legend=dict(orientation="h", y=1.15, font=dict(size=10)),
        xaxis=dict(gridcolor=COLORS["border"], showgrid=True, title="time"),
        yaxis=dict(gridcolor=COLORS["border"], showgrid=True, ticksuffix=y_suffix),
    )
    return fig



    statuses = [n["status"] for n in nodes]
    if "CRITICAL" in statuses:
        return "CRITICAL", COLORS["critical"]
    if "WARN" in statuses:
        return "ELEVATED", COLORS["warn"]
    if "QUARANTINED" in statuses:
        return "CONTAINED", COLORS["quarantined"]
    return "NOMINAL", COLORS["healthy"]


STATUS_COLOR = {
    "HEALTHY": COLORS["healthy"],
    "WARN": COLORS["warn"],
    "CRITICAL": COLORS["critical"],
    "QUARANTINED": COLORS["quarantined"],
}

SHAPES = {"rtu": "hex", "bcu": "rect", "relay": "diamond", "meter": "circle"}


# ----------------------------------------------------------------------------
# SCHEMATIC SVG RENDERER (the signature visual element)
# ----------------------------------------------------------------------------
def node_shape_svg(x, y, ntype, color, glow, dashed_ring):
    shape = SHAPES.get(ntype, "circle")
    r = 18
    glow_filter = f'filter="drop-shadow(0 0 8px {color})"' if glow else ""
    extra = ""
    if dashed_ring:
        extra = (f'<circle cx="{x}" cy="{y}" r="{r+10}" fill="none" '
                  f'stroke="{COLORS["quarantined"]}" stroke-width="2" stroke-dasharray="4 4">'
                  f'<animateTransform attributeName="transform" type="rotate" '
                  f'from="0 {x} {y}" to="360 {x} {y}" dur="6s" repeatCount="indefinite"/></circle>')

    if shape == "hex":
        pts = " ".join(f"{x + r*0.87*dx:.1f},{y + r*dy:.1f}" for dx, dy in
                        [(0,-1),(0.87,-0.5),(0.87,0.5),(0,1),(-0.87,0.5),(-0.87,-0.5)])
        body = f'<polygon points="{pts}" fill="{COLORS["panel"]}" stroke="{color}" stroke-width="2.5" {glow_filter}/>'
    elif shape == "rect":
        body = (f'<rect x="{x-r}" y="{y-r}" width="{2*r}" height="{2*r}" rx="4" '
                f'fill="{COLORS["panel"]}" stroke="{color}" stroke-width="2.5" {glow_filter}/>')
    elif shape == "diamond":
        pts = f"{x},{y-r} {x+r},{y} {x},{y+r} {x-r},{y}"
        body = f'<polygon points="{pts}" fill="{COLORS["panel"]}" stroke="{color}" stroke-width="2.5" {glow_filter}/>'
    else:
        body = f'<circle cx="{x}" cy="{y}" r="{r}" fill="{COLORS["panel"]}" stroke="{color}" stroke-width="2.5" {glow_filter}/>'

    pulse = ""
    if glow:
        pulse = (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="0.25">'
                  f'<animate attributeName="r" values="{r};{r+14};{r}" dur="1.6s" repeatCount="indefinite"/>'
                  f'<animate attributeName="opacity" values="0.35;0;0.35" dur="1.6s" repeatCount="indefinite"/></circle>')

    return pulse + body + extra


def render_schematic(nodes, edges, radius_nodes, compromised_id):
    node_by_id = {n["id"]: n for n in nodes}
    parts = []

    for e in edges:
        a, b = node_by_id.get(e["source"]), node_by_id.get(e["target"])
        if not a or not b:
            continue
        in_radius = e["source"] in radius_nodes or e["target"] in radius_nodes or \
                    e["source"] == compromised_id or e["target"] == compromised_id
        contained = a["status"] == "QUARANTINED" or b["status"] == "QUARANTINED"
        if contained:
            stroke, width, dash, anim = COLORS["quarantined"], 2, '6 4', ""
        elif in_radius:
            stroke, width, dash, anim = COLORS["critical"], 2.5, "8 5", (
                '<animate attributeName="stroke-dashoffset" from="26" to="0" dur="0.5s" repeatCount="indefinite"/>')
        else:
            stroke, width, dash, anim = COLORS["border"], 1.5, "none", ""
        dash_attr = f'stroke-dasharray="{dash}"' if dash != "none" else ""
        parts.append(f'<line x1="{a["x"]}" y1="{a["y"]}" x2="{b["x"]}" y2="{b["y"]}" '
                      f'stroke="{stroke}" stroke-width="{width}" {dash_attr}>{anim}</line>')

    for n in nodes:
        color = STATUS_COLOR.get(n["status"], COLORS["healthy"])
        glow = n["status"] == "CRITICAL"
        dashed_ring = n["status"] == "QUARANTINED"
        parts.append(node_shape_svg(n["x"], n["y"], n["type"], color, glow, dashed_ring))
        parts.append(f'<text x="{n["x"]}" y="{n["y"]+34}" text-anchor="middle" '
                      f'fill="{COLORS["text_dim"]}" font-family="JetBrains Mono" font-size="10">{n["id"]}</text>')

    svg = f'''<svg viewBox="-20 -20 560 380" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
        {''.join(parts)}
    </svg>'''

    html = f'''<div style="background:{COLORS['panel']};border:1px solid {COLORS['border']};
        border-radius:6px;padding:10px;">{svg}</div>'''
    components.html(html, height=420, scrolling=False)


# ----------------------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------------------
left, right = st.columns([3, 1])
with left:
    st.markdown('<div class="eyebrow">GRIDSENTINEL // SUBSTATION-04 LIVE FEED</div>', unsafe_allow_html=True)
    st.markdown('<div class="wordmark">GRIDSENTINEL</div>', unsafe_allow_html=True)

nodes, edges, alerts = load_state()
level, level_color = overall_threat_level(nodes)
with right:
    st.markdown(f'''<div class="panel" style="text-align:center;">
        <div class="eyebrow">THREAT LEVEL</div>
        <div class="status-pill" style="background:{level_color}22;color:{level_color};
             border:1px solid {level_color};margin-top:4px;font-size:1rem;">{level}</div>
        </div>''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# MAIN LAYOUT — auto-refreshing fragment so the graph/alerts feel "live"
# without a full page reload wiping your selections
# ----------------------------------------------------------------------------
@st.fragment(run_every=1)
def live_view():
    nodes, edges, alerts = load_state()

    conn = get_conn()
    g = build_graph(conn)
    conn.close()

    compromised = next((n["id"] for n in nodes if n["status"] == "CRITICAL"), None)
    radius = set(blast_radius(g, compromised)) if compromised else set()

    col_graph, col_side = st.columns([2, 1])

    with col_graph:
        st.markdown('<div class="eyebrow">DEVICE GRAPH — LIVE TOPOLOGY</div>', unsafe_allow_html=True)
        render_schematic(nodes, edges, radius, compromised)
        if compromised:
            st.markdown(f'<div class="mono" style="color:{COLORS["critical"]};margin-top:6px;">'
                        f'\u26a0 BLAST RADIUS: {len(radius)} node(s) reachable from {compromised} within 2 hops'
                        f'</div>', unsafe_allow_html=True)

    with col_side:
        st.markdown('<div class="eyebrow">ALERT FEED</div>', unsafe_allow_html=True)
        if not alerts:
            st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};">No alerts. All nodes nominal.</div>',
                        unsafe_allow_html=True)
        for a in alerts[:12]:
            ts = time.strftime("%H:%M:%S", time.localtime(a["ts"]))
            st.markdown(f'''<div class="alert-row alert-{a["severity"]}">
                <b>{a["severity"]}</b> · {ts} · {a["node_id"]}<br>
                <span style="color:{COLORS['text_dim']}">{a["message"]}</span>
                </div>''', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">NODE STATUS</div>', unsafe_allow_html=True)
    df = pd.DataFrame(nodes)[["id", "type", "vendor", "model", "status", "risk_score", "current_hash"]]
    df["current_hash"] = df["current_hash"].str[:12] + "…"
    st.dataframe(df, use_container_width=True, hide_index=True)


live_view()

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# NODE INSPECTOR + HUMAN-IN-THE-LOOP QUARANTINE
# (kept outside the auto-refresh fragment so the confirm button doesn't
#  vanish mid-click)
# ----------------------------------------------------------------------------
nodes, edges, alerts = load_state()
node_ids = [n["id"] for n in nodes]

st.markdown('<div class="eyebrow">NODE INSPECTOR & ENFORCEMENT</div>', unsafe_allow_html=True)
c1, c2 = st.columns([1, 2])

with c1:
    selected = st.selectbox("Select node", node_ids)
    node = next(n for n in nodes if n["id"] == selected)
    color = STATUS_COLOR.get(node["status"])
    st.markdown(f'''<div class="panel">
        <div class="status-pill" style="background:{color}22;color:{color};border:1px solid {color};">{node["status"]}</div>
        <p class="mono" style="margin-top:10px;font-size:0.8rem;">
        VENDOR &nbsp;{node["vendor"]}<br>
        MODEL &nbsp;{node["model"]}<br>
        GOLDEN &nbsp;{node["golden_hash"][:16]}…<br>
        CURRENT&nbsp;{node["current_hash"][:16]}…<br>
        MATCH &nbsp;{"YES" if node["golden_hash"]==node["current_hash"] else "NO — MISMATCH"}
        </p></div>''', unsafe_allow_html=True)

with c2:
    st.markdown("**Enforcement action** — quarantine changes the *system's model* of the node; "
                "actual isolation would be a separate SDN/switch-port action (see architecture doc). "
                "Human-in-the-loop by design: ICS prioritizes availability, so nothing disruptive fires automatically.")
    if node["status"] == "QUARANTINED":
        st.success(f"{selected} is currently quarantined.")
        if st.button("Restore node to service"):
            conn = get_conn()
            conn.execute("UPDATE nodes SET status='HEALTHY', current_hash=golden_hash WHERE id=?", (selected,))
            conn.execute("UPDATE attacks SET active=0 WHERE node_id=?", (selected,))
            conn.commit(); conn.close()
            append_event("NODE_RESTORED", {"node_id": selected})
            st.rerun()
    else:
        confirm = st.checkbox(f"I confirm I want to quarantine {selected}")
        if st.button("Quarantine node", type="primary", disabled=not confirm):
            conn = get_conn()
            conn.execute("UPDATE nodes SET status='QUARANTINED' WHERE id=?", (selected,))
            conn.commit(); conn.close()
            append_event("NODE_QUARANTINED", {"node_id": selected, "operator_confirmed": True})
            st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# TELEMETRY & RISK HISTORY — Feature 1
# Own fragment so it auto-refreshes without disturbing the node inspector's
# button/checkbox state above it.
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">TELEMETRY & RISK HISTORY — ' + selected + '</div>', unsafe_allow_html=True)
window_min = st.select_slider("Window", options=[1, 2, 5, 10, 30], value=5, format_func=lambda m: f"{m} min")


@st.fragment(run_every=1)
def history_charts(node_id, minutes):
    telemetry, risk = load_history(node_id, minutes)
    ch1, ch2 = st.columns(2)

    with ch1:
        if telemetry:
            df = pd.DataFrame(telemetry)
            df["time"] = pd.to_datetime(df["ts"], unit="s")
            fig = _dark_line_chart(df, ["voltage", "current", "temp"],
                                    [COLORS["accent"], COLORS["warn"], COLORS["critical"]],
                                    "TELEMETRY")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};">No telemetry yet in this window.</div>',
                        unsafe_allow_html=True)

    with ch2:
        if risk:
            df = pd.DataFrame(risk)
            df["time"] = pd.to_datetime(df["ts"], unit="s")
            fig = _dark_line_chart(df, ["risk_score"], [COLORS["critical"]], "RISK SCORE", y_suffix="")
            fig.update_yaxes(range=[0, 100])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(f'<div class="mono" style="color:{COLORS["text_dim"]};">No risk history yet — '
                        f'make sure detection.py is running.</div>', unsafe_allow_html=True)


history_charts(selected, window_min)

st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# LEDGER VIEWER
# ----------------------------------------------------------------------------
st.markdown('<div class="eyebrow">AUDIT LEDGER — HASH-CHAINED (MVP STAND-IN FOR HYPERLEDGER FABRIC)</div>',
            unsafe_allow_html=True)
valid, broken_id = verify_chain()
chain_color = COLORS["healthy"] if valid else COLORS["critical"]
chain_label = "CHAIN VERIFIED — INTACT" if valid else f"CHAIN BROKEN AT ENTRY #{broken_id}"
st.markdown(f'<span class="status-pill mono" style="background:{chain_color}22;color:{chain_color};'
            f'border:1px solid {chain_color};">{chain_label}</span>', unsafe_allow_html=True)

with st.expander("Show ledger entries"):
    entries = get_ledger(limit=50)
    for e in entries:
        ts = time.strftime("%H:%M:%S", time.localtime(e["ts"]))
        st.markdown(f'<div class="mono" style="font-size:0.75rem;color:{COLORS["text_dim"]};">'
                    f'[{ts}] {e["event_type"]} · hash={e["entry_hash"][:16]}…</div>', unsafe_allow_html=True)
