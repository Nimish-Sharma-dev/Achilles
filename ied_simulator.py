"""
ied_simulator.py — PERSON A's file.

Simulates every IED in topology.py as a "live" device: generates realistic
telemetry (voltage/current/temp), computes a SHA-256 identity hash at boot,
and continuously writes readings to the shared DB. Checks the `attacks`
table each tick and — if a node has an active attack — misbehaves
accordingly (firmware hash mismatch / sensor spike / message flood).

Run standalone:  python ied_simulator.py
Leave this running in its own terminal throughout the demo.
"""

import hashlib
import random
import time

from db import get_conn, init_db, now
from ledger import append_event
from topology import NODES, EDGES, BASELINE_RANGES
from zeek_sensor import emit_tick, reset_log_files

TICK_SECONDS = 1.0
# ------------------------------------------------------------------
# STATEFUL TELEMETRY MODEL
# ------------------------------------------------------------------

DEVICE_STATE = {}


def midpoint(bounds):
    return (bounds[0] + bounds[1]) / 2


def initialise_device_state(node_id, rng):
    """Create the initial operating state for an IED."""
    DEVICE_STATE[node_id] = {
        "voltage": midpoint(rng["voltage"]),
        "current": midpoint(rng["current"]),
        "temp": midpoint(rng["temp"]),
    }


def evolve_value(previous, bounds, noise_fraction=0.025, reversion=0.08):
    """
    Generate temporally correlated telemetry.

    The next observation depends on the previous observation rather than
    being independently sampled from the entire operating range.
    """
    low, high = bounds
    centre = midpoint(bounds)
    span = high - low

    mean_reversion = reversion * (centre - previous)
    noise = random.gauss(0, span * noise_fraction)

    value = previous + mean_reversion + noise

    # Allow a little natural operating variation while preventing
    # unrealistic runaway values during normal operation.
    margin = span * 0.05

    return max(low - margin, min(high + margin, value))


def generate_normal_telemetry(node_id, rng):
    """Return the next stateful telemetry observation for an IED."""

    if node_id not in DEVICE_STATE:
        initialise_device_state(node_id, rng)

    state = DEVICE_STATE[node_id]

    voltage = evolve_value(
        state["voltage"],
        rng["voltage"],
        noise_fraction=0.018,
        reversion=0.10,
    )

    current = evolve_value(
        state["current"],
        rng["current"],
        noise_fraction=0.035,
        reversion=0.07,
    )

    # Temperature reacts more slowly than electrical measurements.
    temp = evolve_value(
        state["temp"],
        rng["temp"],
        noise_fraction=0.012,
        reversion=0.025,
    )

    state["voltage"] = voltage
    state["current"] = current
    state["temp"] = temp

    return voltage, current, temp

def compute_identity_hash(node_id, vendor, model, serial, firmware_blob="v1.0.0-stable"):
    """SHA-256 of firmware + hardware identity. NOT physical params — those
    are noisy sensor data and would break the hash constantly (this was a
    deliberate design decision, see architecture doc)."""
    blob = f"{node_id}|{vendor}|{model}|{serial}|{firmware_blob}".encode()
    return hashlib.sha256(blob).hexdigest()


def seed_nodes():
    conn = get_conn()
    for node_id, ntype, vendor, model, x, y in NODES:
        serial = f"SN-{abs(hash(node_id)) % 100000:05d}"
        golden = compute_identity_hash(node_id, vendor, model, serial)
        conn.execute(
            """INSERT OR REPLACE INTO nodes
               (id, type, vendor, model, serial, golden_hash, current_hash, status, risk_score, x, y, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (node_id, ntype, vendor, model, serial, golden, golden, "HEALTHY", 0.0, x, y, now()),
        )
    for source, target, protocol in EDGES:
        conn.execute("INSERT INTO edges (source, target, protocol) VALUES (?,?,?)", (source, target, protocol))
    conn.commit()
    conn.close()
    append_event("SYSTEM_BOOT", {"node_count": len(NODES), "edge_count": len(EDGES)})
    print(f"Seeded {len(NODES)} nodes, {len(EDGES)} edges.")


def get_active_attack(conn, node_id):
    row = conn.execute(
        "SELECT * FROM attacks WHERE node_id=? AND active=1 ORDER BY id DESC LIMIT 1", (node_id,)
    ).fetchone()
    return dict(row) if row else None


def tick(conn):
    node_rows = conn.execute("SELECT * FROM nodes").fetchall()
    for node in node_rows:
        node = dict(node)
        rng = BASELINE_RANGES[node["type"]]
        attack = get_active_attack(conn, node["id"])

        voltage, current, temp = generate_normal_telemetry(
            node["id"],
            rng,
        )
        new_hash = node["golden_hash"]

        if attack:
            atype = attack["attack_type"]
            if atype == "firmware_tamper":
                # trojan swap: identity hash no longer matches golden baseline
                new_hash = hashlib.sha256(f"TAMPERED-{node['id']}-{now()}".encode()).hexdigest()
            elif atype == "sensor_spike":
                # physical anomaly: current/temp blow past normal range (simulates
                # a logic bomb triggering unsafe relay behavior)
                current = current * random.uniform(3.5, 5.0)
                temp = temp * random.uniform(1.8, 2.4)
            elif atype == "replay_flood":
                # network anomaly: erratic voltage from replayed/injected messages
                voltage = voltage + random.choice([-1, 1]) * random.uniform(20, 40)

        conn.execute(
            "INSERT INTO telemetry (node_id, ts, voltage, current, temp) VALUES (?,?,?,?,?)",
            (node["id"], now(), voltage, current, temp),
        )
        conn.execute(
            "UPDATE nodes SET current_hash=?, last_seen=? WHERE id=?",
            (new_hash, now(), node["id"]),
        )

    attacks_by_node = {}
    for row in conn.execute("SELECT * FROM attacks WHERE active=1").fetchall():
        attacks_by_node[row["node_id"]] = dict(row)
    emit_tick(conn, attacks_by_node)
    conn.commit()


def main():
    init_db(reset=True)
    reset_log_files()
    seed_nodes()
    conn = get_conn()
    print("Simulator running. Ctrl+C to stop.")
    try:
        while True:
            tick(conn)
            time.sleep(TICK_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()


if __name__ == "__main__":
    main()
