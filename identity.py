"""
identity.py — Person A helper module.

Simulates "external SPI flash" as a real file on disk per node, and provides
the SHA-256(firmware + hardware identity) function used to boot-hash every
node and re-derive its current_hash on every tick.

This is intentionally its own small module (not part of the db.py/topology.py
integration contract) so ied_simulator.py and attack_injector.py share one
source of truth for how firmware is generated/read/written and how the
identity hash is computed. Person B/C never need to import this directly —
they only ever read nodes.golden_hash / nodes.current_hash from the DB.
"""

import hashlib
import os
import random

FIRMWARE_DIR = os.path.join(os.path.dirname(__file__), "firmware")


def firmware_path(node_id: str) -> str:
    return os.path.join(FIRMWARE_DIR, f"{node_id}.bin")


def generate_firmware(node_id: str, size: int = 256, seed=None) -> bytes:
    """Deterministic 'clean' firmware per node_id by default (so re-seeding
    without an active attack always reproduces the same golden image).
    Pass a unique seed (e.g. a timestamp) to generate a *different* image —
    that's how attack_injector simulates a trojan swap."""
    rnd = random.Random(seed if seed is not None else node_id)
    return bytes(rnd.getrandbits(8) for _ in range(size))


def write_firmware(node_id: str, data: bytes) -> None:
    os.makedirs(FIRMWARE_DIR, exist_ok=True)
    with open(firmware_path(node_id), "wb") as f:
        f.write(data)


def read_firmware(node_id: str) -> bytes:
    path = firmware_path(node_id)
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as f:
        return f.read()


def make_serial(node_id: str) -> str:
    rnd = random.Random(f"{node_id}-serial")
    return f"SN-{rnd.randint(100000, 999999)}"


def compute_identity_hash(node_id: str, vendor: str, model: str, serial: str,
                           firmware_bytes: bytes = None) -> str:
    """golden_hash / current_hash = SHA-256(firmware binary + hardware identity).
    Hardware identity = vendor|model|serial, matching the doc: this hash changes
    on EITHER firmware tampering OR a physical device swap (serial change)."""
    if firmware_bytes is None:
        firmware_bytes = read_firmware(node_id)
    hw_identity = f"{vendor}|{model}|{serial}".encode()
    h = hashlib.sha256()
    h.update(firmware_bytes)
    h.update(hw_identity)
    return h.hexdigest()