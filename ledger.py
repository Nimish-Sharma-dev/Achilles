"""
ledger.py — lightweight tamper-evident audit log.

Every hash change / alert / quarantine event gets appended here as a
hash-chained record: entry_hash = SHA256(prev_hash + payload). Any edit to
a past row breaks every hash after it, which is the same tamper-evidence
property you want to demo from Hyperledger Fabric, without needing to
stand up a Fabric network in 24 hours.

Say this explicitly on stage: "hash-chained ledger for the MVP; production
target is Hyperledger Fabric per our architecture doc." Judges respect
honest scoping.
"""

import hashlib
from db import get_conn, now, dump_json

GENESIS_HASH = "0" * 64


def _compute_hash(prev_hash: str, ts: float, event_type: str, payload_json: str) -> str:
    blob = f"{prev_hash}|{ts}|{event_type}|{payload_json}".encode()
    return hashlib.sha256(blob).hexdigest()


def append_event(event_type: str, payload: dict):
    conn = get_conn()
    cur = conn.execute("SELECT entry_hash FROM ledger ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["entry_hash"] if row else GENESIS_HASH

    ts = now()
    payload_json = dump_json(payload)
    entry_hash = _compute_hash(prev_hash, ts, event_type, payload_json)

    conn.execute(
        "INSERT INTO ledger (ts, event_type, payload, prev_hash, entry_hash) VALUES (?,?,?,?,?)",
        (ts, event_type, payload_json, prev_hash, entry_hash),
    )
    conn.commit()
    conn.close()
    return entry_hash


def verify_chain():
    """Walk the whole ledger and confirm every entry_hash matches its recomputation.
    Returns (is_valid, first_broken_id_or_None). Nice to run live on stage."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ledger ORDER BY id ASC").fetchall()
    conn.close()

    prev_hash = GENESIS_HASH
    for row in rows:
        expected = _compute_hash(prev_hash, row["ts"], row["event_type"], row["payload"])
        if expected != row["entry_hash"]:
            return False, row["id"]
        prev_hash = row["entry_hash"]
    return True, None


def get_ledger(limit=200):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
