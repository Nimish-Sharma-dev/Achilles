"""
detection.py — Person B: the "brain".

Runs continuously alongside ied_simulator.py, polling the same DB every
tick. Three independent checks per node, matching the three demo attacks:

  INTEGRITY   golden_hash vs current_hash, straight comparison. No
              thresholding needed — any mismatch is unambiguous, so this
              is always CRITICAL. (Triggered by attack_injector.py
              firmware-tamper.)

  BEHAVIORAL  rolling z-score per node/channel against that node's OWN
              telemetry history (not a hardcoded global threshold — a
              relay and a meter have different normal ranges, and this
              adapts per node automatically). (Triggered by sensor-spike.)

  NETWORK     exact-repeat detection on consecutive telemetry rows — real
              sensor noise never lands on the identical float twice, so a
              run of identical readings is itself the anomaly signal.
              (Triggered by replay-flood.)

For every alert: writes one row to `alerts`, computes a blast radius via
graph.py, and writes one ledger entry (append-only audit trail) carrying
that blast radius in its payload. Also bumps/decays each node's
risk_score and derives HEALTHY/WARN/CRITICAL status from it.

Deliberately never sets status to QUARANTINED — that's a human-confirmed
action reserved for the dashboard's enforcement layer (Person C), per the
architecture doc's split between "the graph's model" and "real network
state." If a node is already QUARANTINED, this engine keeps computing its
risk_score for display but leaves status alone.

Usage:
    python detection.py
"""

import statistics
import time

import db
import graph
import ledger

TICK_INTERVAL = 1.0

# --- behavioral z-score tuning ---
HISTORY_WINDOW = 30       # ticks of history considered per node
MIN_HISTORY = 10          # need at least this many baseline points before scoring
WARN_Z = 3.0
CRIT_Z = 5.0

# --- network/replay tuning ---
REPLAY_REPEAT_THRESHOLD = 3   # this many bit-identical consecutive readings = flag

# --- risk score / status tuning ---
RISK_DECAY = 0.9              # per-tick decay toward 0 when nothing is wrong
RISK_BUMP = {"INFO": 0.10, "WARN": 0.35, "CRITICAL": 0.75}
RISK_WARN_THRESHOLD = 0.30
RISK_CRIT_THRESHOLD = 0.65

# --- alert de-dup, so an ongoing attack doesn't flood the alert feed with
# one row per second — risk_score still keeps climbing every tick either way
ALERT_DEBOUNCE_SECONDS = 5


def fetch_node_ids(conn):
    return [r["id"] for r in conn.execute("SELECT id FROM nodes")]


def fetch_history(conn, node_id, limit=HISTORY_WINDOW):
    rows = conn.execute(
        "SELECT ts, voltage, current, temp FROM telemetry WHERE node_id=? ORDER BY id DESC LIMIT ?",
        (node_id, limit),
    ).fetchall()
    return list(reversed(rows))  # oldest -> newest


def channel_zscore(history, channel):
    """z-score of the latest reading against every earlier reading in the
    window. Returns None until there's enough history to trust the baseline."""
    if len(history) < MIN_HISTORY + 1:
        return None
    baseline = [r[channel] for r in history[:-1]]
    latest = history[-1][channel]
    mean = statistics.mean(baseline)
    std = statistics.pstdev(baseline) or 1e-6
    return abs(latest - mean) / std


def is_replay(history):
    if len(history) < REPLAY_REPEAT_THRESHOLD:
        return False
    tail = history[-REPLAY_REPEAT_THRESHOLD:]
    v0 = (tail[0]["voltage"], tail[0]["current"], tail[0]["temp"])
    return all((r["voltage"], r["current"], r["temp"]) == v0 for r in tail)


def recent_duplicate(conn, node_id, category, window_seconds=ALERT_DEBOUNCE_SECONDS):
    row = conn.execute(
        "SELECT id FROM alerts WHERE node_id=? AND category=? AND ts > ? ORDER BY id DESC LIMIT 1",
        (node_id, category, db.now() - window_seconds),
    ).fetchone()
    return row is not None


def raise_alert(conn, node_id, severity, category, message, extra=None, debounce=True):
    """Writes the alert row + matching ledger entry as one unit. Returns
    False (no-op) if an alert of the same node+category fired within the
    debounce window — the situation is still reflected in risk_score even
    when the alert row itself is suppressed."""
    if debounce and recent_duplicate(conn, node_id, category):
        return False
    conn.execute(
        "INSERT INTO alerts (node_id, ts, severity, category, message, resolved) "
        "VALUES (?, ?, ?, ?, ?, 0)",
        (node_id, db.now(), severity, category, message),
    )
    payload = {"node_id": node_id, "severity": severity, "category": category, "message": message}
    if extra:
        payload.update(extra)
    ledger.append_entry("ALERT", payload, conn=conn)
    return True


def apply_risk(conn, node_id, severity):
    """Bump risk_score toward 1.0 on an active anomaly and derive status
    from the new score. Never overrides a human-confirmed QUARANTINED."""
    row = conn.execute("SELECT risk_score, status FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not row:
        return
    new_score = min(1.0, row["risk_score"] * RISK_DECAY + RISK_BUMP.get(severity, 0.0))
    _write_risk(conn, node_id, new_score, row["status"])


def decay_risk(conn, node_id):
    """No anomaly this tick — risk_score relaxes back toward HEALTHY."""
    row = conn.execute("SELECT risk_score, status FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not row:
        return
    new_score = row["risk_score"] * RISK_DECAY
    _write_risk(conn, node_id, new_score, row["status"])


def _write_risk(conn, node_id, new_score, current_status):
    if current_status == "QUARANTINED":
        new_status = "QUARANTINED"
    elif new_score >= RISK_CRIT_THRESHOLD:
        new_status = "CRITICAL"
    elif new_score >= RISK_WARN_THRESHOLD:
        new_status = "WARN"
    else:
        new_status = "HEALTHY"
    conn.execute("UPDATE nodes SET risk_score=?, status=? WHERE id=?", (new_score, new_status, node_id))


def check_node(conn, G, node_id):
    node = conn.execute("SELECT golden_hash, current_hash, status FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not node:
        return
    flagged = False

    # --- INTEGRITY (always wins — an unambiguous hash mismatch) ---
    if node["golden_hash"] and node["current_hash"] and node["golden_hash"] != node["current_hash"]:
        radius = graph.blast_radius(G, node_id)
        raise_alert(
            conn, node_id, "CRITICAL", "INTEGRITY",
            f"{node_id}: identity hash mismatch — firmware or hardware identity "
            f"changed since golden baseline.",
            extra={"blast_radius": radius},
        )
        apply_risk(conn, node_id, "CRITICAL")
        flagged = True

    history = fetch_history(conn, node_id)

    # --- NETWORK (replay/jamming) ---
    if not flagged and is_replay(history):
        radius = graph.blast_radius(G, node_id)
        raise_alert(
            conn, node_id, "WARN", "NETWORK",
            f"{node_id}: identical telemetry across {REPLAY_REPEAT_THRESHOLD} consecutive "
            f"ticks — possible replay/jamming.",
            extra={"blast_radius": radius},
        )
        apply_risk(conn, node_id, "WARN")
        flagged = True

    # --- BEHAVIORAL (per-node z-score) ---
    if not flagged:
        worst_z, worst_channel = 0.0, None
        for channel in ("voltage", "current", "temp"):
            z = channel_zscore(history, channel)
            if z is not None and z > worst_z:
                worst_z, worst_channel = z, channel

        if worst_z >= CRIT_Z:
            radius = graph.blast_radius(G, node_id)
            raise_alert(
                conn, node_id, "CRITICAL", "BEHAVIORAL",
                f"{node_id}: {worst_channel} is {worst_z:.1f} std devs from its own baseline.",
                extra={"blast_radius": radius, "z_score": worst_z, "channel": worst_channel},
            )
            apply_risk(conn, node_id, "CRITICAL")
            flagged = True
        elif worst_z >= WARN_Z:
            raise_alert(
                conn, node_id, "WARN", "BEHAVIORAL",
                f"{node_id}: {worst_channel} is {worst_z:.1f} std devs from its own baseline.",
                extra={"z_score": worst_z, "channel": worst_channel},
            )
            apply_risk(conn, node_id, "WARN")
            flagged = True

    if not flagged:
        decay_risk(conn, node_id)


def main():
    print(f"[detection] brain online, polling every {TICK_INTERVAL}s. Ctrl+C to stop.")
    try:
        while True:
            conn = db.get_conn()
            G = graph.build_graph()
            for node_id in fetch_node_ids(conn):
                check_node(conn, G, node_id)
            conn.commit()
            conn.close()
            time.sleep(TICK_INTERVAL)
    except KeyboardInterrupt:
        print("\n[detection] stopping.")


if __name__ == "__main__":
    main()