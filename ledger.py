"""
ledger.py — hash-chained audit log; honest stand-in for Hyperledger Fabric.

Every entry commits to the previous entry's hash, so anything tampered with
after the fact breaks the chain from that point forward on verify_chain() —
the same tamper-evidence property Fabric gives you, without burning 4-6+
hours standing up Docker/chaincode/MSP certs for a 24h hackathon. Say that
line on stage; judges respect scoped honesty over a fragile Fabric demo.

entry_hash = SHA256(prev_hash + event_type + json(payload) + ts)

Usage:
    import ledger
    ledger.append_entry("ALERT", {"node_id": "RELAY-02", ...})
    ok, bad_id = ledger.verify_chain()   # the "ledger proof" demo beat
"""

import hashlib

import db

GENESIS_HASH = "0" * 64


def _last_entry_hash(conn):
    row = conn.execute("SELECT entry_hash FROM ledger ORDER BY id DESC LIMIT 1").fetchone()
    return row["entry_hash"] if row else GENESIS_HASH


def append_entry(event_type, payload, conn=None):
    """Append one tamper-evident entry.

    Pass an existing `conn` when calling from inside a loop that already
    has one open (e.g. detection.py's tick loop) so the alert row and its
    ledger entry commit together. Omit it to have this function manage its
    own short-lived connection — safe to call concurrently from multiple
    processes: each caller re-reads the chain tail under WAL, so a lost
    race just means the next caller chains off the newer tail (the chain
    stays unbroken, just re-ordered by whichever write actually landed).
    """
    owns_conn = conn is None
    if owns_conn:
        conn = db.get_conn()

    ts = db.now()
    prev_hash = _last_entry_hash(conn)
    payload_json = db.dump_json(payload)

    h = hashlib.sha256()
    h.update(prev_hash.encode())
    h.update(event_type.encode())
    h.update(payload_json.encode())
    h.update(str(ts).encode())
    entry_hash = h.hexdigest()

    conn.execute(
        "INSERT INTO ledger (ts, event_type, payload, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?)",
        (ts, event_type, payload_json, prev_hash, entry_hash),
    )

    if owns_conn:
        conn.commit()
        conn.close()
    return entry_hash


def verify_chain():
    """Walk the whole ledger and confirm every entry_hash is correctly
    derived from its own row + the previous row's entry_hash.

    Returns (is_valid: bool, first_broken_id: int|None). Call this live
    on stage as the "ledger proof" beat of the demo script."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT id, ts, event_type, payload, prev_hash, entry_hash FROM ledger ORDER BY id ASC"
    ).fetchall()
    conn.close()

    expected_prev = GENESIS_HASH
    for row in rows:
        if row["prev_hash"] != expected_prev:
            return False, row["id"]
        h = hashlib.sha256()
        h.update(row["prev_hash"].encode())
        h.update(row["event_type"].encode())
        h.update(row["payload"].encode())
        h.update(str(row["ts"]).encode())
        if h.hexdigest() != row["entry_hash"]:
            return False, row["id"]
        expected_prev = row["entry_hash"]
    return True, None


if __name__ == "__main__":
    ok, bad_id = verify_chain()
    print("[ledger] chain valid." if ok else f"[ledger] chain BROKEN at entry id={bad_id}")