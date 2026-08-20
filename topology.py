"""
topology.py — defines the demo substation: nodes + edges + layout positions.

Keep this small and readable for a demo: ~10-12 nodes is plenty to show a
convincing blast-radius on the graph without cluttering the screen.

Edit NODES/EDGES here if you want to change the story (e.g. add a second
substation), everything else reads from this file.
"""

# type: relay | bcu | meter | rtu
NODES = [
    # id            type      vendor        model        x     y
    ("RTU-01",      "rtu",    "GE",         "D400",      50,   50),
    ("BCU-01",      "bcu",    "Siemens",    "SICAM",     200,  50),
    ("BCU-02",      "bcu",    "Siemens",    "SICAM",     350,  50),
    ("RELAY-01",    "relay",  "ABB",        "REF615",    150,  180),
    ("RELAY-02",    "relay",  "ABB",        "REF615",    280,  180),
    ("RELAY-03",    "relay",  "SEL",        "SEL-751",   410,  180),
    ("METER-01",    "meter",  "Landis+Gyr", "E650",      100,  310),
    ("METER-02",    "meter",  "Landis+Gyr", "E650",      230,  310),
    ("METER-03",    "meter",  "Itron",      "OpenWay",   360,  310),
    ("METER-04",    "meter",  "Itron",      "OpenWay",   470,  310),
]

# (source, target, protocol)
EDGES = [
    ("RTU-01", "BCU-01", "DNP3"),
    ("RTU-01", "BCU-02", "DNP3"),
    ("BCU-01", "RELAY-01", "IEC61850-GOOSE"),
    ("BCU-01", "RELAY-02", "IEC61850-GOOSE"),
    ("BCU-02", "RELAY-03", "IEC61850-GOOSE"),
    ("RELAY-01", "METER-01", "Modbus"),
    ("RELAY-01", "METER-02", "Modbus"),
    ("RELAY-02", "METER-03", "Modbus"),
    ("RELAY-03", "METER-04", "Modbus"),
]

# OT LAN addresses used by the Zeek sensor (SPAN stand-in).
NODE_IPS = {
    "RTU-01":    "10.4.1.10",
    "BCU-01":    "10.4.1.21",
    "BCU-02":    "10.4.1.22",
    "RELAY-01":  "10.4.2.31",
    "RELAY-02":  "10.4.2.32",
    "RELAY-03":  "10.4.2.33",
    "METER-01":  "10.4.3.41",
    "METER-02":  "10.4.3.42",
    "METER-03":  "10.4.3.43",
    "METER-04":  "10.4.3.44",
}

PROTO_PORTS = {
    "DNP3": 20000,
    "Modbus": 502,
    "IEC61850-GOOSE": 102,
}

# Baseline "normal" telemetry ranges per node type — simulator samples around these
BASELINE_RANGES = {
    "rtu":   {"voltage": (228, 232), "current": (10, 14),  "temp": (30, 40)},
    "bcu":   {"voltage": (228, 232), "current": (8, 12),   "temp": (28, 38)},
    "relay": {"voltage": (225, 235), "current": (15, 25),  "temp": (35, 50)},
    "meter": {"voltage": (220, 240), "current": (5, 20),   "temp": (20, 35)},
}
