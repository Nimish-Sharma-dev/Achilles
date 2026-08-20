"""
db.py — shared state store for GridSentinel.

Every process (simulator, detection engine, attack injector, dashboard)
talks to the SAME sqlite file. This is the "integration contract" —
if you're on Person A/B/C's task, you only need to read/write these
tables correctly and everything else just works.

Run this once to create the DB:  python db.py
"""

import sqlite3
import time
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "gridsentinel.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")  # allow concurrent read/write across processes
    conn.row_factory = sqlite3.Row
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id           TEXT PRIMARY KEY,
    type         TEXT,        -- relay | bcu | meter | rtu
    vendor       TEXT,
    model        TEXT,
    serial       TEXT,
    golden_hash  TEXT,        -- baseline SHA-256 (firmware + hw identity)
    current_hash TEXT,        -- latest computed SHA-256
    status       TEXT DEFAULT 'HEALTHY',   -- HEALTHY | WARN | CRITICAL | QUARANTINED
    risk_score   REAL DEFAULT 0.0,
    x            REAL,        -- fixed layout position for the schematic view
    y            REAL,
    last_seen    REAL
);

CREATE TABLE IF NOT EXISTS edges (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    source   TEXT,
    target   TEXT,
    protocol TEXT             -- DNP3 | Modbus | IEC61850-GOOSE
);

CREATE TABLE IF NOT EXISTS telemetry (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT,
    ts      REAL,
    voltage REAL,
    current REAL,
    temp    REAL
);

CREATE TABLE IF NOT EXISTS alerts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id  TEXT,
    ts       REAL,
    severity TEXT,            -- INFO | WARN | CRITICAL
    category TEXT,            -- INTEGRITY | BEHAVIORAL | NETWORK
    message  TEXT,
    resolved INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ledger (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         REAL,
    event_type TEXT,
    payload    TEXT,          -- JSON string
    prev_hash  TEXT,
    entry_hash TEXT
);

CREATE TABLE IF NOT EXISTS attacks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL,
    node_id     TEXT,
    attack_type TEXT,         -- firmware_tamper | sensor_spike | replay_flood
    active      INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS risk_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id    TEXT,
    ts         REAL,
    risk_score REAL
);

CREATE TABLE IF NOT EXISTS firmware_scans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT,
    ts          REAL,
    scan_type   TEXT,        -- STATIC | DYNAMIC
    tool        TEXT,        -- ghidra | nm_fallback | qemu
    verdict     TEXT,        -- CLEAN | SUSPICIOUS | TROJAN_DETECTED
    details     TEXT         -- JSON string
);
"""


def init_db(reset=False):
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"DB ready at {DB_PATH}")


def now():
    return time.time()


def dump_json(d):
    return json.dumps(d, default=str)


if __name__ == "__main__":
    init_db(reset=True)
