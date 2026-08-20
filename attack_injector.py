"""
attack_injector.py — the button you press live on stage.

Usage:
    python attack_injector.py --list
    python attack_injector.py --node RELAY-02 --attack firmware_tamper
    python attack_injector.py --node METER-03 --attack sensor_spike
    python attack_injector.py --node BCU-01   --attack replay_flood
    python attack_injector.py --clear RELAY-02      # heal it back for a re-run

This is deliberately a dumb CLI, not part of the dashboard — during a live
demo you want a fast, reliable, muscle-memory command in a terminal, not a
dropdown you might fumble on stage. Once comfortable, you can wire a hidden
Streamlit control to call inject() directly (see dashboard.py TODO).
"""

import argparse
from db import get_conn, now
from ledger import append_event

ATTACK_TYPES = ["firmware_tamper", "sensor_spike", "replay_flood"]


def inject(node_id: str, attack_type: str):
    if attack_type not in ATTACK_TYPES:
        raise ValueError(f"attack_type must be one of {ATTACK_TYPES}")
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not exists:
        conn.close()
        raise ValueError(f"No such node: {node_id}")
    conn.execute(
        "INSERT INTO attacks (ts, node_id, attack_type, active) VALUES (?,?,?,1)",
        (now(), node_id, attack_type),
    )
    conn.commit()
    conn.close()
    append_event("ATTACK_INJECTED", {"node_id": node_id, "attack_type": attack_type})
    print(f"[INJECTED] {attack_type} -> {node_id}")


def clear(node_id: str):
    conn = get_conn()
    conn.execute("UPDATE attacks SET active=0 WHERE node_id=?", (node_id,))
    conn.commit()
    conn.close()
    append_event("ATTACK_CLEARED", {"node_id": node_id})
    print(f"[CLEARED] attacks on {node_id}")


def list_nodes():
    conn = get_conn()
    rows = conn.execute("SELECT id, type, status FROM nodes ORDER BY id").fetchall()
    conn.close()
    for r in rows:
        print(f"  {r['id']:<12} {r['type']:<8} status={r['status']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--node")
    p.add_argument("--attack", choices=ATTACK_TYPES)
    p.add_argument("--clear")
    p.add_argument("--list", action="store_true")
    args = p.parse_args()

    if args.list:
        list_nodes()
    elif args.clear:
        clear(args.clear)
    elif args.node and args.attack:
        inject(args.node, args.attack)
    else:
        p.print_help()
