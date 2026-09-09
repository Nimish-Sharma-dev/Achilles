"""
detection.py — PERSON B's file.

Runs continuously alongside the simulator. Each tick:
  1. pulls latest telemetry per node
  2. checks integrity (current_hash vs golden_hash) -> CRITICAL alert
  3. checks behavioral anomaly (z-score vs rolling baseline) -> WARN/CRITICAL
  4. on CRITICAL, computes blast radius via graph traversal and writes it
     into the alert message so the dashboard can highlight the subgraph
  5. writes every alert to the ledger (tamper-evident audit trail)

Deliberately uses simple statistical thresholds, not a trained ML model.
For a 24h demo, threshold logic is what you can *guarantee* fires
correctly live on stage. Isolation Forest/LSTM are real upgrades — wire
them in behind the same interface (see score_anomaly()) after the
threshold version works end-to-end, only if time allows.

Run standalone:  python detection.py
"""

import time
import statistics
import networkx as nx

from db import get_conn, now, ensure_schema
from ledger import append_event
from topology import BASELINE_RANGES
from temporal import analyze_node

TICK_SECONDS = 1.5
ROLLING_WINDOW = 20          # telemetry samples used for baseline stats
MIN_SAMPLES = 15             # don't score until the baseline has enough history to be stable
Z_WARN = 4.5
Z_CRITICAL = 6.5
TEMPORAL_WINDOW = 45
TEMPORAL_WARN = 68.0
TEMPORAL_CRITICAL = 85.0
TEMPORAL_WARMUP = 30
TEMPORAL_CONFIRMATIONS = 3
TEMPORAL_STREAKS = {}  # node_id -> count of consecutive abnormal windows
# ------------------------------------------------------------
#  NEW: overall threat level (used by dashboard.py)
# ------------------------------------------------------------
def overall_threat_level(nodes):
    """
    Determine overall threat level from all node statuses.
    Returns (level_string, color_hex).
    """
    severity_map = {
        'CRITICAL': 4,
        'HIGH': 3,
        'WARNING': 2,
        'MEDIUM': 2,
        'LOW': 1,
        'OK': 0,
        'UNKNOWN': 0
    }
    level_colors = {
        4: ('CRITICAL', '#ff4b4b'),   # red
        3: ('HIGH', '#ff9f43'),       # orange
        2: ('WARNING', '#feca57'),    # yellow
        1: ('LOW', '#54a0ff'),        # blue
        0: ('OK', '#10ac84')          # green
    }
    max_sev = 0
    for node in nodes:
        status = node.get('status', 'OK').upper()
        sev = severity_map.get(status, 0)
        if sev > max_sev:
            max_sev = sev
    return level_colors.get(max_sev, ('UNKNOWN', '#95a5a6'))
# ------------------------------------------------------------


def build_graph(conn):
    g = nx.DiGraph()
    for row in conn.execute("SELECT id FROM nodes"):
        g.add_node(row["id"])
    for row in conn.execute("SELECT source, target FROM edges"):
        g.add_edge(row["source"], row["target"])
        g.add_edge(row["target"], row["source"])  # comms are effectively bidirectional for blast-radius purposes
    return g


def blast_radius(g: nx.DiGraph, node_id: str, hops=2):
    """Everything reachable within `hops` of a compromised node — this is
    what would need to be isolated/inspected, and what the dashboard
    highlights on the graph."""
    if node_id not in g:
        return []
    lengths = nx.single_source_shortest_path_length(g, node_id, cutoff=hops)
    return [n for n in lengths if n != node_id]


def score_anomaly(values):
    """z-score of the latest reading vs the rolling window. Swap this out
    for an IsolationForest.decision_function call later if time allows —
    keep the same (mean, std, latest) -> score shape.

    Requires MIN_SAMPLES of history before scoring at all — with only a
    handful of samples the std estimate is too noisy and produces false
    positives on perfectly healthy random telemetry (this is the exact
    "baseline drift / false-positive fatigue" problem called out in the
    architecture doc; the fix there is periodic re-baselining, the fix
    here for a 24h demo is just: don't trust a tiny window)."""
    if len(values) < MIN_SAMPLES:
        return 0.0
    baseline = values[:-1]
    latest = values[-1]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline) or 1e-6
    return abs(latest - mean) / std


def raise_alert(conn, node_id, severity, category, message):
    conn.execute(
        "INSERT INTO alerts (node_id, ts, severity, category, message) VALUES (?,?,?,?,?)",
        (node_id, now(), severity, category, message),
    )
    status = "CRITICAL" if severity == "CRITICAL" else "WARN"
    conn.execute("UPDATE nodes SET status=? WHERE id=? AND status != 'QUARANTINED'", (status, node_id))
    conn.commit()
    append_event("ALERT", {"node_id": node_id, "severity": severity, "category": category, "message": message})


def check_integrity(conn):
    rows = conn.execute("SELECT id, golden_hash, current_hash, status FROM nodes").fetchall()
    for r in rows:
        # skip nodes already flagged/quarantined — don't re-alert every tick for an ongoing issue
        if r["status"] in ("CRITICAL", "QUARANTINED"):
            continue
        if r["current_hash"] != r["golden_hash"]:
            g = build_graph(conn)
            radius = blast_radius(g, r["id"])
            msg = (f"Firmware/identity hash mismatch on {r['id']}. "
                   f"Blast radius ({len(radius)} nodes): {', '.join(radius) if radius else 'none'}")
            raise_alert(conn, r["id"], "CRITICAL", "INTEGRITY", msg)


def check_zeek(conn):
    """Raise NETWORK alerts from Zeek notice.log. De-dupes per node for 20s."""
    cutoff = now() - TICK_SECONDS * 4
    rows = conn.execute(
        """SELECT node_id, notice_type, msg, orig_h, resp_h FROM zeek_logs
           WHERE log_type='notice' AND anomaly=1 AND ts>=?
           ORDER BY id DESC""",
        (cutoff,),
    ).fetchall()
    seen = set()
    for r in rows:
        node_id = r["node_id"]
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        status_row = conn.execute("SELECT status FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not status_row or status_row["status"] in ("CRITICAL", "QUARANTINED"):
            continue
        recent = conn.execute(
            "SELECT 1 FROM alerts WHERE node_id=? AND category='NETWORK' AND ts>? LIMIT 1",
            (node_id, now() - 20),
        ).fetchone()
        if recent:
            continue
        note = r["notice_type"] or "ICS::NetworkAnomaly"
        critical = note in ("ICS::ReplayFlood", "ICS::FirmwareC2Beacon", "ICS::GOOSEStorm")
        severity = "CRITICAL" if critical else "WARN"
        g = build_graph(conn)
        radius = blast_radius(g, node_id)
        msg = (f"Zeek {note} on {node_id} ({r['orig_h']} → {r['resp_h']}). {r['msg']} "
               f"Blast radius ({len(radius)} nodes): {', '.join(radius) if radius else 'none'}")
        raise_alert(conn, node_id, severity, "NETWORK", msg)


def check_behavioral(conn):
    node_rows = conn.execute("SELECT id, status FROM nodes").fetchall()
    for nr in node_rows:
        node_id, current_status = nr["id"], nr["status"]
        if current_status in ("CRITICAL", "QUARANTINED"):
            continue
        rows = conn.execute(
            "SELECT voltage, current, temp FROM telemetry WHERE node_id=? ORDER BY id DESC LIMIT ?",
            (node_id, ROLLING_WINDOW),
        ).fetchall()
        if len(rows) < MIN_SAMPLES:
            continue
        rows = list(reversed(rows))  # oldest -> newest
        for field in ("voltage", "current", "temp"):
            values = [r[field] for r in rows]
            z = score_anomaly(values)
            if z >= Z_CRITICAL:
                g = build_graph(conn)
                radius = blast_radius(g, node_id)
                msg = (f"{field} deviates {z:.1f}\u03c3 from baseline on {node_id}. "
                       f"Blast radius ({len(radius)} nodes): {', '.join(radius) if radius else 'none'}")
                raise_alert(conn, node_id, "CRITICAL", "BEHAVIORAL", msg)
            elif z >= Z_WARN:
                raise_alert(conn, node_id, "WARN", "BEHAVIORAL", f"{field} drifting ({z:.1f}\u03c3) on {node_id}")

def check_temporal(conn):
    """
    Sequence-aware detector.

    WARN requires repeated abnormal windows.
    CRITICAL can fire immediately for a very strong anomaly.
    """

    node_rows = conn.execute(
        "SELECT id, status FROM nodes"
    ).fetchall()

    for nr in node_rows:

        node_id = nr["id"]

        if nr["status"] in ("CRITICAL", "QUARANTINED"):
            continue

        rows = conn.execute(
            """
            SELECT voltage, current, temp
            FROM telemetry
            WHERE node_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (node_id, TEMPORAL_WINDOW),
        ).fetchall()

        # Do not trust temporal analysis during startup.
        if len(rows) < TEMPORAL_WARMUP:
            TEMPORAL_STREAKS[node_id] = 0
            continue

        rows = list(reversed(rows))

        analysis = analyze_node(rows)
        score = analysis["score"]

        channel_scores = {
            field: result["score"]
            for field, result in analysis["channels"].items()
        }

        dominant_channel = max(
            channel_scores,
            key=channel_scores.get,
        )

        dominant_score = channel_scores[dominant_channel]

        # --------------------------------------------------
        # CRITICAL
        # Strong anomalies do not require confirmation.
        # --------------------------------------------------
        if score >= TEMPORAL_CRITICAL:

            TEMPORAL_STREAKS[node_id] = 0

            g = build_graph(conn)
            radius = blast_radius(g, node_id)

            msg = (
                f"Temporal anomaly on {node_id}: "
                f"{dominant_channel} sequence score "
                f"{dominant_score:.1f}/100. "
                f"Blast radius ({len(radius)} nodes): "
                f"{', '.join(radius) if radius else 'none'}"
            )

            raise_alert(
                conn,
                node_id,
                "CRITICAL",
                "TEMPORAL",
                msg,
            )

            continue

        # --------------------------------------------------
        # WARNING
        # Require persistence to avoid noisy one-window alerts.
        # --------------------------------------------------
        if score >= TEMPORAL_WARN:

            TEMPORAL_STREAKS[node_id] = (
                TEMPORAL_STREAKS.get(node_id, 0) + 1
            )

            if TEMPORAL_STREAKS[node_id] >= TEMPORAL_CONFIRMATIONS:

                msg = (
                    f"Persistent temporal drift on {node_id}: "
                    f"{dominant_channel} sequence score "
                    f"{dominant_score:.1f}/100 "
                    f"across {TEMPORAL_CONFIRMATIONS} windows"
                )

                raise_alert(
                    conn,
                    node_id,
                    "WARN",
                    "TEMPORAL",
                    msg,
                )

                TEMPORAL_STREAKS[node_id] = 0

        else:
            # Healthy window breaks the anomaly streak.
            TEMPORAL_STREAKS[node_id] = 0
        
def compute_and_record_risk(conn):
    """
    Continuous explainable 0-100 risk score.

    Risk currently combines:
        - temporal telemetry behaviour
        - firmware integrity
        - recent network evidence

    Persona deviation will be added in the next phase.
    """

    node_rows = conn.execute(
        """
        SELECT id, golden_hash, current_hash
        FROM nodes
        """
    ).fetchall()

    for nr in node_rows:

        node_id = nr["id"]

        # --------------------------------------------------
        # TEMPORAL COMPONENT
        # --------------------------------------------------

        rows = conn.execute(
            """
            SELECT voltage, current, temp
            FROM telemetry
            WHERE node_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (node_id, TEMPORAL_WINDOW),
        ).fetchall()

        temporal_score = 0.0

        if len(rows) >= TEMPORAL_WARMUP:

            rows = list(reversed(rows))

            analysis = analyze_node(rows)

            temporal_score = analysis["score"]

        # Temporal behaviour contributes at most 55 points.
        temporal_component = (
            temporal_score / 100.0
        ) * 55.0


        # --------------------------------------------------
        # INTEGRITY COMPONENT
        # --------------------------------------------------

        integrity_mismatch = (
            nr["current_hash"] != nr["golden_hash"]
        )

        integrity_component = (
            35.0 if integrity_mismatch else 0.0
        )


        # --------------------------------------------------
        # NETWORK COMPONENT
        # --------------------------------------------------

        recent_network = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM zeek_logs
            WHERE node_id=?
              AND anomaly=1
              AND ts > ?
            """,
            (
                node_id,
                now() - 30,
            ),
        ).fetchone()

        network_count = (
            recent_network["count"]
            if recent_network
            else 0
        )

        network_component = min(
            network_count * 5.0,
            10.0
        )


        # --------------------------------------------------
        # FINAL RISK
        # --------------------------------------------------

        risk = (
            temporal_component
            + integrity_component
            + network_component
        )

        # Suppress meaningless low-level stochastic noise.
        if (
            not integrity_mismatch
            and network_count == 0
            and temporal_score < 35
        ):
            risk *= 0.35

        risk = round(
            min(100.0, risk),
            1,
        )


        conn.execute(
            """
            UPDATE nodes
            SET risk_score=?
            WHERE id=?
            """,
            (
                risk,
                node_id,
            ),
        )

        conn.execute(
            """
            INSERT INTO risk_history
                (node_id, ts, risk_score)
            VALUES
                (?, ?, ?)
            """,
            (
                node_id,
                now(),
                risk,
            ),
        )

    conn.commit()

def main():
    ensure_schema()
    print("Detection engine running. Ctrl+C to stop.")
    try:
        while True:
            conn = get_conn()
            check_integrity(conn)

            # Legacy single-point z-score detector.
            # Retained for comparison, disabled in Achilles V2 because
            # temporal/persona analysis supersedes it.
            # check_behavioral(conn)

            check_temporal(conn)
            check_zeek(conn)
            compute_and_record_risk(conn)
            conn.close()
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()