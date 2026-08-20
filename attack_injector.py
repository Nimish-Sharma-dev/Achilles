"""
attack_injector.py — Person A: the CLI trigger fired live on stage.

Three attack types, matching the three detection layers the pitch talks about:

  firmware-tamper  <node_id>   supply-chain trojan swap -> overwrites the node's
                                 "flash" file, so current_hash diverges from
                                 golden_hash on the simulator's next tick
                                 (INTEGRITY alert, detection.py)

  sensor-spike     <node_id>   physical anomaly -> simulator pushes that node's
                                 voltage/current/temp outside baseline
                                 (BEHAVIORAL alert, z-score, detection.py)

  replay-flood     <node_id>   network anomaly -> simulator freezes and re-emits
                                 one reading at high frequency instead of fresh
                                 noisy samples
                                 (NETWORK alert, detection.py)

  reset            <node_id>   clear the active attack and restore clean
                                 firmware (does not touch QUARANTINED status —
                                 that's the enforcement layer's call)

Writes to the shared `attacks` table only — ied_simulator.py polls that table
every tick per-node, so this script never talks to the simulator directly and
can be run from a separate terminal (or hidden dashboard button) at any time.

Usage:
    python attack_injector.py list
    python attack_injector.py firmware-tamper RELAY-02
    python attack_injector.py sensor-spike METER-03
    python attack_injector.py replay-flood BCU-01
    python attack_injector.py reset RELAY-02
"""

import argparse
import time

import db
import identity
import topology

NODE_IDS = [n[0] for n in topology.NODES]


def log_attack(node_id, attack_type):
    conn = db.get_conn()
    conn.execute("UPDATE attacks SET active = 0 WHERE node_id = ? AND active = 1", (node_id,))
    conn.execute(
        "INSERT INTO attacks (ts, node_id, attack_type, active) VALUES (?, ?, ?, 1)",
        (db.now(), node_id, attack_type),
    )
    conn.commit()
    conn.close()


def clear_attack(node_id):
    conn = db.get_conn()
    conn.execute("UPDATE attacks SET active = 0 WHERE node_id = ? AND active = 1", (node_id,))
    conn.commit()
    conn.close()


def firmware_tamper(node_id):
    tampered = identity.generate_firmware(node_id, seed=f"TROJAN-{time.time()}")
    identity.write_firmware(node_id, tampered)
    log_attack(node_id, "firmware_tamper")
    print(f"[attack] firmware-tamper injected on {node_id} — flash overwritten, "
          f"hash mismatch will surface on the next simulator tick (~1s).")


def sensor_spike(node_id):
    log_attack(node_id, "sensor_spike")
    print(f"[attack] sensor-spike active on {node_id} — telemetry will spike out of baseline.")


def replay_flood(node_id):
    log_attack(node_id, "replay_flood")
    print(f"[attack] replay-flood active on {node_id} — telemetry will freeze/replay at burst rate.")


def reset_node(node_id):
    clean = identity.generate_firmware(node_id)  # same deterministic seed as boot -> restores golden image
    identity.write_firmware(node_id, clean)
    clear_attack(node_id)
    print(f"[attack] {node_id} restored: clean firmware rewritten, active attack cleared.")


def list_nodes():
    print("Available nodes:")
    for n in NODE_IDS:
        print(f"  {n}")


def main():
    parser = argparse.ArgumentParser(description="GridSentinel attack injector")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("firmware-tamper", help="trojan swap -> identity hash mismatch")
    p1.add_argument("node_id", choices=NODE_IDS)

    p2 = sub.add_parser("sensor-spike", help="physical anomaly -> z-score behavioral alert")
    p2.add_argument("node_id", choices=NODE_IDS)

    p3 = sub.add_parser("replay-flood", help="network anomaly -> frozen/duplicate telemetry")
    p3.add_argument("node_id", choices=NODE_IDS)

    p4 = sub.add_parser("reset", help="clear an attack and restore clean firmware on a node")
    p4.add_argument("node_id", choices=NODE_IDS)

    sub.add_parser("list", help="list available node ids")

    args = parser.parse_args()

    {
        "firmware-tamper": lambda: firmware_tamper(args.node_id),
        "sensor-spike": lambda: sensor_spike(args.node_id),
        "replay-flood": lambda: replay_flood(args.node_id),
        "reset": lambda: reset_node(args.node_id),
        "list": list_nodes,
    }[args.command]()


if __name__ == "__main__":
    main()