# Achilles— MVP scaffold

A working, integration-ready skeleton so the three of you can split work
immediately without stepping on each other. It runs end-to-end right now:
simulated substation → live telemetry → integrity + behavioral detection
→ graph blast-radius → human-confirmed quarantine → hash-chained audit log
→ all visualized in a live Streamlit dashboard.

## How the pieces fit together

Everything shares **one SQLite file** (`gridsentinel.db`) as the integration
contract. As long as you read/write the tables in `db.py` correctly, you can
develop your piece independently of the other two.

```
ied_simulator.py  ──writes──▶  gridsentinel.db  ◀──reads/writes──  detection.py
attack_injector.py ─writes──▶       (nodes,                              │
                                     telemetry,                          │
                                     edges,                        writes alerts,
                                     alerts,                       updates status,
                                     ledger,                       writes ledger
                                     attacks)                            │
                                        ▲                                │
                                        └──────── reads everything ──────┘
                                                        │
                                                  dashboard.py (Streamlit)
```

## Setup (do this first, together)

```bash
pip install -r requirements.txt
python db.py          # creates gridsentinel.db with the schema
```

Then, **three separate terminals**, left running throughout the hackathon:

```bash
# Terminal 1
python ied_simulator.py     # seeds nodes + streams telemetry every second

# Terminal 2
python detection.py         # scores telemetry, raises alerts, writes ledger

# Terminal 3
streamlit run dashboard.py  # the visual you show the judges
```

To inject an attack live:

```bash
python attack_injector.py --node RELAY-02 --attack firmware_tamper
python attack_injector.py --node METER-03 --attack sensor_spike
python attack_injector.py --node BCU-01   --attack replay_flood
python attack_injector.py --clear RELAY-02   # heal it, reset for a re-run
```

## Work division

**Person A — `ied_simulator.py` + `attack_injector.py` + `topology.py`**
Already scaffolded and working. Your job for the remaining time:
- Tune `BASELINE_RANGES` in `topology.py` so telemetry looks realistic for
  your node types
- Add a second/third attack variant if time allows (e.g. `replay_flood`
  currently only perturbs voltage — could also duplicate telemetry rows to
  simulate a real replay)
- Make sure `--list`/`--clear` are muscle-memory before the live demo

**Person B — `detection.py`**
Already scaffolded and working (integrity check, z-score behavioral check,
blast radius via NetworkX, writes to `ledger.py`). Your job:
- If time allows, swap `score_anomaly()` for a real `IsolationForest` —
  the function signature is designed so this is a drop-in change
- Tune `Z_WARN` / `Z_CRITICAL` / `MIN_SAMPLES` against Person A's actual
  telemetry ranges so nothing false-positives live on stage
- Own the "why did it flag this" explanation for Q&A

**Person C — `dashboard.py`**
Already scaffolded and working (schematic graph, alert feed, node
inspector, quarantine flow, ledger viewer). Your job:
- Polish pass: check it looks right on the actual demo machine/projector
  (dark backgrounds can wash out under bad lighting — test early)
- Own the demo flow/script below and rehearse clicking through it
- Optional stretch: wire a hidden "inject attack" button in the sidebar
  that calls `attack_injector.inject()` directly, so you don't need to
  alt-tab to a terminal mid-pitch

## Live demo script (~2-3 min)

1. **Open on NOMINAL.** Dashboard shows all 10 nodes green, threat level
   NOMINAL, empty alert feed. Narrate the architecture in one sentence:
   "every IED is a node in a live graph, cryptographically fingerprinted
   at boot."
2. **Trigger the attack** (Terminal, or hidden button):
   `python attack_injector.py --node RELAY-02 --attack firmware_tamper`
3. **Within ~1-2 seconds** the dashboard should show: RELAY-02 glowing red
   on the schematic, a CRITICAL alert in the feed naming the blast radius,
   threat level flipping to CRITICAL, dashed red pulse along the affected
   edges.
4. **Point at blast radius**, explain: "this is graph traversal, not a
   guess — these are the nodes actually reachable from the compromised
   relay within 2 hops, that's what would need containment."
5. **Human-in-the-loop quarantine**: select RELAY-02 in the node
   inspector, check the confirm box, click Quarantine. Explain *why* it's
   a checkbox+button and not automatic: "ICS prioritizes availability —
   we never want an automated system tripping a live relay without a
   human confirming."
6. **Show the ledger**: expand the audit log, point at the hash chain,
   say the one honest-scoping line: *"production target is Hyperledger
   Fabric per our architecture doc — for the 24-hour MVP we implemented
   the same tamper-evidence property with a hash chain."*
7. **Reset for Q&A**: `python attack_injector.py --clear RELAY-02`, then
   click "Restore node to service" in the dashboard.

Rehearse this exact sequence at least twice before the actual demo slot —
know the two commands cold, and know how long steps 2→3 take on the actual
machine you'll present from.

## Honest scoping notes for judges/Q&A

Say these out loud if asked — it reads as engineering maturity, not a gap:
- Detection is threshold/z-score based for demo reliability, not the
  trained IsolationForest/LSTM from the architecture doc — swappable later
  behind the same interface
- Ledger is a hash chain, not Hyperledger Fabric — same tamper-evidence
  property, without a 4-6hr Fabric network setup
- No real side-channel (power/EM) detection, no PUF/TPM, no hardware
  interlock circuit — these are architecturally scoped but out of a
  24-hour MVP's reach; mention them as the roadmap, not the demo
