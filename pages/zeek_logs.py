"""
pages/zeek_logs.py

Streamlit auto-discovers this file next to dashboard.py and adds
"zeek logs" to the sidebar nav.
"""

import os
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db import get_conn, ensure_schema
from zeek_sensor import LOG_DIR, ZEEK_ROOT

st.set_page_config(
    page_title="GridSentinel — Zeek Logs",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "bg": "#0A0E14", "panel": "#12161F", "border": "#1F2733",
    "text": "#E6EDF3", "text_dim": "#6B7684",
    "healthy": "#00D9A3", "warn": "#F5A623", "critical": "#FF4757",
    "accent": "#3DA5FF", "quarantined": "#64748B",
}

PROTO_COLOR = {
    "DNP3": COLORS["accent"],
    "Modbus": COLORS["warn"],
    "IEC61850-GOOSE": COLORS["healthy"],
    "tcp": COLORS["critical"],
}

ensure_schema()

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=JetBrains+Mono:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ background-color: {COLORS['bg']} !important; color: {COLORS['text']}; }}
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
.wordmark {{ font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:1.8rem; }}
.eyebrow {{ font-family:'JetBrains Mono',monospace; color:{COLORS['accent']}; letter-spacing:.15em;
            font-size:.75rem; text-transform:uppercase; }}
.mono {{ font-family:'JetBrains Mono',monospace; }}
.zeek-row {{
    border-left: 3px solid {COLORS['border']};
    padding: 4px 10px; margin-bottom: 4px;
    font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
    background: rgba(255,255,255,0.02); color: {COLORS['text_dim']};
}}
.zeek-anomaly {{ border-left-color: {COLORS['critical']}; color: {COLORS['text']}; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="eyebrow">GRIDSENTINEL // SPAN SENSOR — OT LAN</div>', unsafe_allow_html=True)
st.markdown('<div class="wordmark">ZEEK LOGS</div>', unsafe_allow_html=True)
st.caption(f"Policy: `{ZEEK_ROOT}`  ·  TSV: `{LOG_DIR}`  ·  tables: conn / notice / dnp3 / modbus / goose / weird")


def _dark_layout(fig, title, height=260, y_title=""):
    fig.update_layout(
        title=dict(text=title, font=dict(family="JetBrains Mono", size=13, color=COLORS["text_dim"])),
        paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
        font=dict(family="JetBrains Mono", size=11, color=COLORS["text"]),
        margin=dict(l=48, r=16, t=40, b=32), height=height,
        legend=dict(orientation="h", y=1.12, font=dict(size=10)),
        xaxis=dict(gridcolor=COLORS["border"], showgrid=True, title="time"),
        yaxis=dict(gridcolor=COLORS["border"], showgrid=True, title=y_title),
    )
    return fig


def load_zeek(minutes=5):
    conn = get_conn()
    cutoff = time.time() - minutes * 60
    try:
        rows = conn.execute(
            """SELECT ts, log_type, uid, node_id, peer_id, proto, notice_type, msg,
                      orig_h, orig_p, resp_h, resp_p, orig_bytes, resp_bytes, conn_state, anomaly
               FROM zeek_logs WHERE ts>=? ORDER BY id ASC""",
            (cutoff,),
        ).fetchall()
    except Exception:
        conn.close()
        return []
    conn.close()
    return [dict(r) for r in rows]


window_min = st.select_slider("Window", options=[1, 2, 5, 10, 30], value=5, format_func=lambda m: f"{m} min")


@st.fragment(run_every=1)
def zeek_view(minutes):
    rows = load_zeek(minutes)
    if not rows:
        st.markdown(
            f'<div class="mono" style="color:{COLORS["text_dim"]};margin-top:12px;">'
            f"No Zeek rows yet. Restart <code>ied_simulator.py</code> so it emits into "
            f"<code>zeek/logs/</code> every tick.</div>",
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["ts"], unit="s")
    df["anomaly"] = df["anomaly"].fillna(0).astype(int)
    df["orig_bytes"] = pd.to_numeric(df["orig_bytes"], errors="coerce").fillna(0)
    df["resp_bytes"] = pd.to_numeric(df["resp_bytes"], errors="coerce").fillna(0)

    conn_df = df[df["log_type"] == "conn"]
    notice_df = df[df["log_type"] == "notice"]
    n_conn = len(conn_df)
    n_notice = len(notice_df)
    n_anom = int((df["anomaly"] == 1).sum())
    n_nodes = df["node_id"].nunique()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("conn.log rows", n_conn)
    k2.metric("notice.log rows", n_notice)
    k3.metric("anomalous rows", n_anom)
    k4.metric("talkers", n_nodes)

    # --- connections over time ---
    g1, g2 = st.columns(2)
    with g1:
        if not conn_df.empty:
            ts_bin = conn_df.set_index("time").resample("1s").size().rename("connections")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=ts_bin.index, y=ts_bin.values, mode="lines", name="connections / s",
                line=dict(color=COLORS["accent"], width=2),
            ))
            st.plotly_chart(_dark_layout(fig, "CONNECTIONS PER SECOND", y_title="count"),
                            use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No conn.log rows in this window.")

    with g2:
        proto_counts = df[df["log_type"].isin(["conn", "dnp3", "modbus", "goose"])].groupby("proto").size()
        if proto_counts.empty:
            proto_counts = conn_df.groupby("proto").size()
        fig = go.Figure()
        colors = [PROTO_COLOR.get(p, COLORS["text_dim"]) for p in proto_counts.index]
        fig.add_trace(go.Bar(
            x=list(proto_counts.index), y=list(proto_counts.values),
            marker_color=colors, name="protocol",
        ))
        fig.update_layout(
            title=dict(text="PROTOCOL MIX", font=dict(family="JetBrains Mono", size=13, color=COLORS["text_dim"])),
            paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
            font=dict(family="JetBrains Mono", size=11, color=COLORS["text"]),
            margin=dict(l=48, r=16, t=40, b=32), height=260,
            xaxis=dict(gridcolor=COLORS["border"], title="protocol"),
            yaxis=dict(gridcolor=COLORS["border"], title="log rows"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    g3, g4 = st.columns(2)
    with g3:
        anom = df[df["anomaly"] == 1]
        if not anom.empty:
            series = anom.set_index("time").resample("1s").size().rename("anomalies")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=series.index, y=series.values, mode="lines", name="anomalies / s",
                line=dict(color=COLORS["critical"], width=2),
                fill="tozeroy", fillcolor="rgba(255,71,87,0.12)",
            ))
            st.plotly_chart(_dark_layout(fig, "ANOMALOUS LOGS PER SECOND", y_title="count"),
                            use_container_width=True, config={"displayModeBar": False})
        else:
            fig = go.Figure()
            fig.add_annotation(text="No Zeek notices / weird / flood rows in this window",
                               xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                               font=dict(color=COLORS["healthy"], family="JetBrains Mono"))
            st.plotly_chart(_dark_layout(fig, "ANOMALOUS LOGS PER SECOND"),
                            use_container_width=True, config={"displayModeBar": False})

    with g4:
        if not conn_df.empty:
            binned = conn_df.set_index("time").resample("1s")[["orig_bytes", "resp_bytes"]].sum()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=binned.index, y=binned["orig_bytes"], mode="lines", name="orig_bytes",
                line=dict(color=COLORS["accent"], width=2),
            ))
            fig.add_trace(go.Scatter(
                x=binned.index, y=binned["resp_bytes"], mode="lines", name="resp_bytes",
                line=dict(color=COLORS["warn"], width=2),
            ))
            st.plotly_chart(_dark_layout(fig, "BYTES ON THE WIRE", y_title="bytes / s"),
                            use_container_width=True, config={"displayModeBar": False})

    g5, g6 = st.columns(2)
    with g5:
        talkers = df.dropna(subset=["node_id"]).groupby("node_id").size().sort_values(ascending=False)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=list(talkers.index), y=list(talkers.values),
            marker_color=COLORS["accent"], name="rows",
        ))
        fig.update_layout(
            title=dict(text="TOP TALKERS (log rows by origin IED)",
                       font=dict(family="JetBrains Mono", size=13, color=COLORS["text_dim"])),
            paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
            font=dict(family="JetBrains Mono", size=11, color=COLORS["text"]),
            margin=dict(l=48, r=16, t=40, b=32), height=260,
            xaxis=dict(gridcolor=COLORS["border"], title="node"),
            yaxis=dict(gridcolor=COLORS["border"], title="rows"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with g6:
        if not conn_df.empty and conn_df["conn_state"].notna().any():
            states = conn_df["conn_state"].fillna("-").value_counts()
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=list(states.index), y=list(states.values),
                marker_color=[COLORS["healthy"] if s == "SF" else COLORS["critical"] for s in states.index],
            ))
            fig.update_layout(
                title=dict(text="CONN STATE (SF = normal close)",
                           font=dict(family="JetBrains Mono", size=13, color=COLORS["text_dim"])),
                paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"],
                font=dict(family="JetBrains Mono", size=11, color=COLORS["text"]),
                margin=dict(l=48, r=16, t=40, b=32), height=260,
                xaxis=dict(gridcolor=COLORS["border"], title="conn_state"),
                yaxis=dict(gridcolor=COLORS["border"], title="count"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown('<div class="eyebrow" style="margin-top:8px;">LIVE TAIL</div>', unsafe_allow_html=True)
    types = ["all"] + sorted(df["log_type"].unique().tolist())
    f1, f2 = st.columns(2)
    with f1:
        log_filter = st.selectbox("Log type", types, key="zeek-type")
    with f2:
        nodes = ["all"] + sorted([n for n in df["node_id"].dropna().unique().tolist()])
        node_filter = st.selectbox("Origin node", nodes, key="zeek-node")

    tail = df.sort_values("ts", ascending=False)
    if log_filter != "all":
        tail = tail[tail["log_type"] == log_filter]
    if node_filter != "all":
        tail = tail[tail["node_id"] == node_filter]
    show_anom_only = st.checkbox("Anomalies only", value=False, key="zeek-anom")
    if show_anom_only:
        tail = tail[tail["anomaly"] == 1]

    for _, z in tail.head(24).iterrows():
        ts = z["time"].strftime("%H:%M:%S")
        label = z["notice_type"] or z["log_type"]
        klass = "zeek-row zeek-anomaly" if z["anomaly"] else "zeek-row"
        orig = f"{z['orig_h']}:{z['orig_p']}" if pd.notna(z["orig_p"]) else (z["orig_h"] or "")
        resp = f"{z['resp_h']}:{z['resp_p']}" if pd.notna(z["resp_p"]) else (z["resp_h"] or "")
        st.markdown(
            f'<div class="{klass}">[{ts}] {z["log_type"]:<6} {label} · {orig} → {resp}<br>'
            f'<span style="color:{COLORS["text_dim"]}">{z["msg"]}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="eyebrow" style="margin-top:16px;">FILES IN zeek/logs/</div>', unsafe_allow_html=True)
    if os.path.isdir(LOG_DIR):
        files = sorted(f for f in os.listdir(LOG_DIR) if f.endswith(".log"))
        if not files:
            st.caption("Folder exists but no .log files yet.")
        else:
            pick = st.selectbox("Open TSV", files, key="zeek-file")
            path = os.path.join(LOG_DIR, pick)
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.readlines()
                st.code("".join(lines[-40:]), language="text")
            except OSError as e:
                st.error(str(e))
    else:
        st.caption("zeek/logs/ not created yet — start the simulator.")


zeek_view(window_min)
