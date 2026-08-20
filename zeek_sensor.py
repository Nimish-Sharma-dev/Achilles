"""
zeek_sensor.py — SPAN stand-in. Emits Zeek-format TSV into zeek/logs/
and the same rows into the zeek_logs SQLite table.

Called from ied_simulator.tick(). Do not run as its own process.
"""

import os
import random
import string

from db import now
from topology import EDGES, NODE_IPS, PROTO_PORTS

ZEEK_ROOT = os.path.join(os.path.dirname(__file__), "zeek")
LOG_DIR = os.path.join(ZEEK_ROOT, "logs")

C2_HOST = "185.244.25.77"
C2_PORT = 443

_HEADERS = {
    "conn": (
        "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
        "proto", "service", "duration", "orig_bytes", "resp_bytes", "conn_state",
        "orig_pkts", "resp_pkts",
    ),
    "notice": (
        "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
        "proto", "note", "msg", "src", "dst", "p", "actions",
    ),
    "dnp3": (
        "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
        "fc_request", "fc_reply", "iin",
    ),
    "modbus": (
        "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
        "func", "exception",
    ),
    "goose": (
        "ts", "uid", "id.orig_h", "id.resp_h", "go_id", "stNum", "sqNum", "ttl_ms",
    ),
    "weird": (
        "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p",
        "name", "addl", "notice",
    ),
}

_DNP3_FC = ["READ", "WRITE", "SELECT", "OPERATE", "DIRECT_OPERATE", "CONFIRM"]
_MODBUS_FC = ["READ_HOLDING", "READ_INPUT", "WRITE_SINGLE", "WRITE_MULTIPLE"]

_headers_ready = False
_emitted_notices = set()


def reset_log_files():
    global _headers_ready, _emitted_notices
    _headers_ready = False
    _emitted_notices = set()
    os.makedirs(LOG_DIR, exist_ok=True)
    for name in _HEADERS:
        path = os.path.join(LOG_DIR, f"{name}.log")
        if os.path.exists(path):
            os.remove(path)


def _uid():
    alphabet = string.ascii_letters + string.digits
    return "C" + "".join(random.choice(alphabet) for _ in range(17))


def _ephemeral_port():
    return random.randint(41000, 60999)


def _ensure_files():
    global _headers_ready
    if _headers_ready:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    for log_type, fields in _HEADERS.items():
        path = os.path.join(LOG_DIR, f"{log_type}.log")
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", encoding="utf-8") as f:
                f.write("#separator \\x09\n")
                f.write("#set_separator\t,\n")
                f.write("#empty_field\t(empty)\n")
                f.write("#unset_field\t-\n")
                f.write(f"#path\t{log_type}\n")
                f.write(f"#open\t{now():.6f}\n")
                f.write("#fields\t" + "\t".join(fields) + "\n")
                f.write("#types\t" + "\t".join(["time" if x == "ts" else "string" for x in fields]) + "\n")
    _headers_ready = True


def _append_file(log_type, values):
    _ensure_files()
    line = "\t".join(str(v) for v in values)
    with open(os.path.join(LOG_DIR, f"{log_type}.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def _insert(conn, *, ts, log_type, uid, node_id, peer_id, proto, notice_type, msg,
            orig_h, orig_p, resp_h, resp_p, orig_bytes, resp_bytes, conn_state, anomaly, raw):
    conn.execute(
        """INSERT INTO zeek_logs
           (ts, log_type, uid, node_id, peer_id, proto, notice_type, msg,
            orig_h, orig_p, resp_h, resp_p, orig_bytes, resp_bytes, conn_state, anomaly, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ts, log_type, uid, node_id, peer_id, proto, notice_type, msg,
         orig_h, orig_p, resp_h, resp_p, orig_bytes, resp_bytes, conn_state,
         1 if anomaly else 0, raw),
    )


def _write_conn(conn, ts, uid, orig_id, resp_id, proto, service, anomaly=False, orig_bytes=None):
    orig_h, resp_h = NODE_IPS[orig_id], NODE_IPS[resp_id]
    orig_p = _ephemeral_port()
    resp_p = PROTO_PORTS.get(proto, 0)
    duration = round(random.uniform(0.04, 0.35), 6)
    orig_bytes = orig_bytes if orig_bytes is not None else random.randint(64, 480)
    resp_bytes = random.randint(48, 640)
    orig_pkts = max(1, orig_bytes // 80)
    resp_pkts = max(1, resp_bytes // 80)
    state = "SF" if not anomaly else random.choice(["SF", "RSTO", "S0", "REJ"])
    raw = _append_file("conn", [
        f"{ts:.6f}", uid, orig_h, orig_p, resp_h, resp_p,
        "tcp", service, duration, orig_bytes, resp_bytes, state, orig_pkts, resp_pkts,
    ])
    _insert(conn, ts=ts, log_type="conn", uid=uid, node_id=orig_id, peer_id=resp_id,
            proto=proto, notice_type=None,
            msg=f"{orig_h}:{orig_p} -> {resp_h}:{resp_p} {service} {state}",
            orig_h=orig_h, orig_p=orig_p, resp_h=resp_h, resp_p=resp_p,
            orig_bytes=orig_bytes, resp_bytes=resp_bytes, conn_state=state,
            anomaly=anomaly, raw=raw)
    return orig_p, resp_p, orig_bytes, resp_bytes


def _write_notice(conn, ts, uid, orig_id, resp_id, proto, note, msg, orig_p, resp_p):
    orig_h, resp_h = NODE_IPS[orig_id], NODE_IPS[resp_id]
    raw = _append_file("notice", [
        f"{ts:.6f}", uid, orig_h, orig_p, resp_h, resp_p,
        "tcp", note, msg, orig_h, resp_h, resp_p, "Notice::ACTION_LOG",
    ])
    _insert(conn, ts=ts, log_type="notice", uid=uid, node_id=orig_id, peer_id=resp_id,
            proto=proto, notice_type=note, msg=msg,
            orig_h=orig_h, orig_p=orig_p, resp_h=resp_h, resp_p=resp_p,
            orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=True, raw=raw)


def _write_weird(conn, ts, uid, orig_id, resp_id, proto, name, addl, orig_p, resp_p):
    orig_h, resp_h = NODE_IPS[orig_id], NODE_IPS[resp_id]
    raw = _append_file("weird", [
        f"{ts:.6f}", uid, orig_h, orig_p, resp_h, resp_p, name, addl, "F",
    ])
    _insert(conn, ts=ts, log_type="weird", uid=uid, node_id=orig_id, peer_id=resp_id,
            proto=proto, notice_type=name, msg=addl,
            orig_h=orig_h, orig_p=orig_p, resp_h=resp_h, resp_p=resp_p,
            orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=True, raw=raw)


def _write_protocol(conn, ts, uid, orig_id, resp_id, proto, orig_p, resp_p, attack=None):
    orig_h, resp_h = NODE_IPS[orig_id], NODE_IPS[resp_id]
    flood = bool(attack and attack["attack_type"] == "replay_flood")
    if proto == "DNP3":
        fc = random.choice(["OPERATE", "DIRECT_OPERATE", "COLD_RESTART"]) if flood else random.choice(_DNP3_FC)
        raw = _append_file("dnp3", [f"{ts:.6f}", uid, orig_h, orig_p, resp_h, resp_p, fc, "CONFIRM", "0x0000"])
        _insert(conn, ts=ts, log_type="dnp3", uid=uid, node_id=orig_id, peer_id=resp_id,
                proto=proto, notice_type=fc, msg=f"DNP3 {fc}",
                orig_h=orig_h, orig_p=orig_p, resp_h=resp_h, resp_p=resp_p,
                orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=flood, raw=raw)
    elif proto == "Modbus":
        func = "WRITE_MULTIPLE" if flood else random.choice(_MODBUS_FC)
        exception = "ILLEGAL_FUNCTION" if flood else "-"
        raw = _append_file("modbus", [f"{ts:.6f}", uid, orig_h, orig_p, resp_h, resp_p, func, exception])
        _insert(conn, ts=ts, log_type="modbus", uid=uid, node_id=orig_id, peer_id=resp_id,
                proto=proto, notice_type=func, msg=f"Modbus {func} {exception}",
                orig_h=orig_h, orig_p=orig_p, resp_h=resp_h, resp_p=resp_p,
                orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=flood, raw=raw)
    else:
        st_num = random.randint(40, 90) if flood else random.randint(1, 8)
        sq_num = random.randint(200, 800) if flood else random.randint(0, 40)
        raw = _append_file("goose", [f"{ts:.6f}", uid, orig_h, resp_h, f"{orig_id}-GOOSE", st_num, sq_num, 1000])
        _insert(conn, ts=ts, log_type="goose", uid=uid, node_id=orig_id, peer_id=resp_id,
                proto=proto, notice_type=f"stNum={st_num}",
                msg=f"GOOSE stNum={st_num} sqNum={sq_num}",
                orig_h=orig_h, orig_p=0, resp_h=resp_h, resp_p=0,
                orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=flood, raw=raw)


def _attack_notices(conn, ts, orig_id, resp_id, proto, orig_p, resp_p, uid, attack):
    if not attack:
        return
    atype = attack["attack_type"]
    if atype == "replay_flood":
        if proto == "DNP3":
            note, msg = "ICS::ReplayFlood", f"DNP3 ASDU replay/injection {orig_id} -> {resp_id}"
            weird, addl = "dnp3_unexpected_asdu_repeat", "duplicate sequence"
        elif proto == "Modbus":
            note, msg = "ICS::ModbusExceptionFlood", f"Modbus ILLEGAL_FUNCTION burst {orig_id} -> {resp_id}"
            weird, addl = "modbus_exception_flood", "func=WRITE_MULTIPLE"
        else:
            note, msg = "ICS::GOOSEStorm", f"IEC61850 GOOSE stNum/sqNum storm {orig_id} -> {resp_id}"
            weird, addl = "goose_stnum_jump", "stNum jumped >20"
        _write_notice(conn, ts, uid, orig_id, resp_id, proto, note, msg, orig_p, resp_p)
        _write_weird(conn, ts, uid, orig_id, resp_id, proto, weird, addl, orig_p, resp_p)
        return

    if atype != "firmware_tamper":
        return
    key = (attack["id"], "firmware_tamper")
    if key in _emitted_notices:
        return
    _emitted_notices.add(key)
    c2_uid = _uid()
    orig_h = NODE_IPS[orig_id]
    c2_port = _ephemeral_port()
    raw = _append_file("conn", [
        f"{ts:.6f}", c2_uid, orig_h, c2_port, C2_HOST, C2_PORT,
        "tcp", "ssl", "12.400000", 4096, 512, "S1", 18, 4,
    ])
    _insert(conn, ts=ts, log_type="conn", uid=c2_uid, node_id=orig_id, peer_id=None,
            proto="tcp", notice_type=None,
            msg=f"{orig_h}:{c2_port} -> {C2_HOST}:{C2_PORT} ssl S1",
            orig_h=orig_h, orig_p=c2_port, resp_h=C2_HOST, resp_p=C2_PORT,
            orig_bytes=4096, resp_bytes=512, conn_state="S1", anomaly=True, raw=raw)
    notice_raw = _append_file("notice", [
        f"{ts:.6f}", c2_uid, orig_h, c2_port, C2_HOST, C2_PORT,
        "tcp", "ICS::FirmwareC2Beacon",
        f"Unexpected outbound SSL from {orig_id} to {C2_HOST}:{C2_PORT}",
        orig_h, C2_HOST, C2_PORT, "Notice::ACTION_LOG",
    ])
    _insert(conn, ts=ts, log_type="notice", uid=c2_uid, node_id=orig_id, peer_id=None,
            proto="tcp", notice_type="ICS::FirmwareC2Beacon",
            msg=f"Unexpected outbound SSL from {orig_id} to {C2_HOST}:{C2_PORT}",
            orig_h=orig_h, orig_p=c2_port, resp_h=C2_HOST, resp_p=C2_PORT,
            orig_bytes=0, resp_bytes=0, conn_state=None, anomaly=True, raw=notice_raw)


def emit_tick(conn, attacks_by_node):
    _ensure_files()
    ts = now()
    for orig_id, resp_id, proto in EDGES:
        attack = attacks_by_node.get(orig_id) or attacks_by_node.get(resp_id)
        n_copies = random.randint(6, 11) if attack and attack["attack_type"] == "replay_flood" else 1
        extra_bytes = random.randint(800, 2400) if n_copies > 1 else None
        for i in range(n_copies):
            uid = _uid()
            orig_p, resp_p, _, _ = _write_conn(
                conn, ts, uid, orig_id, resp_id, proto,
                service=proto.lower().split("-")[0],
                anomaly=n_copies > 1,
                orig_bytes=extra_bytes,
            )
            _write_protocol(conn, ts, uid, orig_id, resp_id, proto, orig_p, resp_p, attack)
            if i == 0:
                _attack_notices(conn, ts, orig_id, resp_id, proto, orig_p, resp_p, uid, attack)
