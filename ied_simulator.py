"""
ied_simulator.py — Person A: Simulation & Identity layer.

Spins up one thread per IED (relay/BCU/meter/RTU) from topology.py. Each node:
  1. "Boots" once: generates fake firmware + hardware identity (vendor/model/
     serial), computes SHA-256(firmware + identity) as its golden_hash, and
     writes that as the initial current_hash too.
  2. Every tick: samples noisy voltage/current/temp telemetry around its type's
     baseline range and writes a row to `telemetry`; re-reads whatever bytes
     are currently on its "flash" (firmware/<node_id>.bin) and recomputes
     current_hash, so if attack_injector.py overwrites that file, the mismatch
     shows up in the DB on the very next tick — no coordination needed.

This process owns identity + physical telemetry only. It does NOT decide
alerts/status/risk_score — that's detection.py (Person B)'s job, reading the
same DB. It also checks the `attacks` table each tick so it can honestly
misbehave (spike / freeze telemetry) when a demo attack is active on a node.

Usage:
    python db.py              # once, to create gridsentinel.db
    python ied_simulator.py   # start streaming (Ctrl+C to stop)
"""

import argparse
import random
import threading
import time

import db
import identity
import topology

TICK_INTERVAL = 1.0  # seconds between telemetry samples per node


def seed_node(node_id, ntype, vendor, model, x, y):
    """Boot a node: generate identity + clean firmware, compute golden_hash,
    upsert into `nodes`. Safe to call repeatedly (idempotent on node_id)."""
    serial = identity.make_serial(node_id)
    firmware = identity.generate_firmware(node_id)
    identity.write_firmware(node_id, firmware)
    golden = identity.compute_identity_hash(node_id, vendor, model, serial, firmware)

    conn = db.get_conn()
    conn.execute(
        """
        INSERT INTO nodes (id, type, vendor, model, serial, golden_hash, current_hash,
                            status, risk_score, x, y, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'HEALTHY', 0.0, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            type=excluded.type, vendor=excluded.vendor, model=excluded.model,
            serial=excluded.serial, golden_hash=excluded.golden_hash,
            current_hash=excluded.current_hash, status='HEALTHY', risk_score=0.0,
            x=excluded.x, y=excluded.y, last_seen=excluded.last_seen
        """,
        (node_id, ntype, vendor, model, serial, golden, golden, x, y, db.now()),
    )
    conn.commit()
    conn.close()
    return serial, golden


def seed_edges():
    conn = db.get_conn()
    conn.execute("DELETE FROM edges")
    for source, target, protocol in topology.EDGES:
        conn.execute(
            "INSERT INTO edges (source, target, protocol) VALUES (?, ?, ?)",
            (source, target, protocol),
        )
    conn.commit()
    conn.close()


def get_active_attack(node_id):
    conn = db.get_conn()
    row = conn.execute(
        "SELECT * FROM attacks WHERE node_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (node_id,),
    ).fetchone()
    conn.close()
    return row


class IEDNode(threading.Thread):
    def __init__(self, node_id, ntype, stop_event):
        super().__init__(daemon=True, name=node_id)
        self.node_id = node_id
        self.ntype = ntype
        self.stop_event = stop_event
        self._frozen_reading = None  # used by replay_flood

    def sample_telemetry(self):
        ranges = topology.BASELINE_RANGES[self.ntype]
        v_lo, v_hi = ranges["voltage"]
        c_lo, c_hi = ranges["current"]
        t_lo, t_hi = ranges["temp"]
        v = random.gauss((v_lo + v_hi) / 2, (v_hi - v_lo) / 6)
        c = random.gauss((c_lo + c_hi) / 2, (c_hi - c_lo) / 6)
        t = random.gauss((t_lo + t_hi) / 2, (t_hi - t_lo) / 6)
        return v, c, t

    def run(self):
        while not self.stop_event.is_set():
            attack = get_active_attack(self.node_id)
            attack_type = attack["attack_type"] if attack else None

            if attack_type == "sensor_spike":
                v, c, t = self.sample_telemetry()
                channel = random.choice(["voltage", "current", "temp"])
                if channel == "voltage":
                    v *= random.uniform(1.4, 1.9)
                elif channel == "current":
                    c *= random.uniform(1.6, 2.5)
                else:
                    t *= random.uniform(1.8, 2.6)
                self._frozen_reading = None
            elif attack_type == "replay_flood":
                # freeze the first captured reading and keep re-emitting it —
                # real sensor noise never repeats bit-for-bit, so an exact
                # repeat is itself the network-anomaly signal for detection.py
                if self._frozen_reading is None:
                    self._frozen_reading = self.sample_telemetry()
                v, c, t = self._frozen_reading
            else:
                self._frozen_reading = None
                v, c, t = self.sample_telemetry()

            conn = db.get_conn()
            conn.execute(
                "INSERT INTO telemetry (node_id, ts, voltage, current, temp) VALUES (?, ?, ?, ?, ?)",
                (self.node_id, db.now(), v, c, t),
            )

            row = conn.execute(
                "SELECT vendor, model, serial FROM nodes WHERE id = ?", (self.node_id,)
            ).fetchone()
            if row:
                current_hash = identity.compute_identity_hash(
                    self.node_id, row["vendor"], row["model"], row["serial"]
                )
                conn.execute(
                    "UPDATE nodes SET current_hash = ?, last_seen = ? WHERE id = ?",
                    (current_hash, db.now(), self.node_id),
                )
            conn.commit()
            conn.close()

            # replay_flood also bursts frequency, not just freezes values
            sleep_for = TICK_INTERVAL / 4 if attack_type == "replay_flood" else TICK_INTERVAL
            self.stop_event.wait(sleep_for)


def main():
    parser = argparse.ArgumentParser(description="GridSentinel IED simulator (Person A)")
    parser.add_argument(
        "--reset-db", action="store_true",
        help="wipe gridsentinel.db and recreate schema before seeding (fresh demo run)",
    )
    args = parser.parse_args()

    db.init_db(reset=args.reset_db)

    print(f"[simulator] seeding {len(topology.NODES)} nodes...")
    for node_id, ntype, vendor, model, x, y in topology.NODES:
        serial, golden = seed_node(node_id, ntype, vendor, model, x, y)
        print(f"  {node_id:<10} {ntype:<6} {vendor:<12} serial={serial}  golden={golden[:12]}...")
    seed_edges()
    print(f"[simulator] seeded {len(topology.EDGES)} edges")

    stop_event = threading.Event()
    threads = [IEDNode(node_id, ntype, stop_event) for node_id, ntype, *_ in topology.NODES]
    for t in threads:
        t.start()

    print(f"[simulator] {len(threads)} nodes streaming telemetry every {TICK_INTERVAL}s. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[simulator] stopping...")
        stop_event.set()
        for t in threads:
            t.join(timeout=2)
        print("[simulator] stopped.")


if __name__ == "__main__":
    main()