# GridSentinel — MVP scaffold

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

## New features added

### 1. Telemetry + risk-score history charts
- `db.py` — new `risk_history(id, node_id, ts, risk_score)` table
- `detection.py` — new `compute_and_record_risk()`, called every tick from
  `main()`. Blends the worst active behavioral z-score (0-70 pts) with a
  flat +30 pt penalty on hash mismatch into a single 0-100 risk score,
  writes it to both `nodes.risk_score` (current value) and `risk_history`
  (time series).
- `dashboard.py` — new auto-refreshing charts section between the node
  inspector and the ledger viewer: telemetry (voltage/current/temp) and
  risk score over a selectable time window, both live plotly charts.

Nothing to build — this is done and tested (0 false spikes on healthy
data, correctly climbs to 30+ within one tick of a firmware mismatch).

### 2. Firmware Forensics page — real Ghidra + QEMU pipeline
This is genuinely wired, not simulated: `firmware/main_baseline.c` and
`firmware/main_tampered.c` are real bare-metal ARM Cortex-M3 C, cross-
compiled with `arm-none-eabi-gcc` into real ELF/bin files that actually
boot under QEMU's `lm3s6965evb` machine. The tampered variant differs by
exactly one injected function (`diag_selftest_ext`, a disguised logic
bomb that force-closes the relay at tick 3) — everything below is a real
tool finding a real difference, not a scripted result.

New files:
- `firmware/` — source + compiled `.elf`/`.bin` for both variants, `build.sh`
  to recompile if you change the C
- `firmware_forensics.py` — static analysis (Ghidra headless if available,
  automatic fallback to real `arm-none-eabi-nm` symbol diff + byte/entropy
  diff) and dynamic analysis (real QEMU boot, UART transcript diff).
  Writes to a new `firmware_scans` table, raises alerts into the *same*
  `alerts` table the telemetry detectors use (so a firmware finding flips
  the main dashboard's threat level too), and logs a ledger entry.
- `ghidra_scripts/ListFunctions.py` — real Ghidra headless script (Jython,
  runs inside Ghidra) that dumps the decompiled function list to JSON
- `ghidra_setup.sh` — **run this once before the demo**, not live. Pre-
  imports both binaries into a persistent Ghidra project so the GUI opens
  instantly on stage instead of sitting through cold auto-analysis.
- `pages/1_🔬_Firmware_Forensics.py` — new Streamlit page (auto-appears in
  the sidebar nav next to the main dashboard). Tool-status panel, target
  selector, quick attack-trigger buttons, "Launch Ghidra GUI" button (opens
  the real native app in its own window), Run Static / Run Dynamic buttons
  with live verdicts and transcripts, scan history.

**On Ghidra specifically:** Ghidra's GUI is a native Java desktop app — it
cannot render inside a browser tab, so "a different page" for this one
piece means a real separate window the Streamlit button launches, not an
embedded panel. Everything else (the verdict, the diff, the transcripts)
does render inline in the new Streamlit page.

**Setup required on the actual demo machine, ahead of time:**
```bash
# Already verified working via apt in this sandbox — same commands should
# work on Ubuntu/Debian demo machines:
sudo apt install gcc-arm-none-eabi binutils-arm-none-eabi qemu-system-arm binwalk

# Ghidra is optional — the app runs and detects correctly without it,
# using the nm/entropy fallback tier. To enable the preferred Ghidra tier
# and the GUI walkthrough button:
#   1. Install a JDK 17+
#   2. Download Ghidra: https://github.com/NationalSecurityAgency/ghidra/releases
#   3. export GHIDRA_HOME=/path/to/extracted/ghidra_11.x_PUBLIC
#   4. ./ghidra_setup.sh    (pre-imports both binaries — do this before judges arrive)
```
If your demo machine is Windows/Mac, `apt` won't apply — install QEMU and
the ARM toolchain via your platform's package manager (`brew`, or MSYS2 on
Windows) ahead of time and verify `qemu-system-arm --version` and
`arm-none-eabi-gcc --version` work before the demo starts. Ghidra itself
is cross-platform (it's a JAR-based Java app) either way.

## Work division for these two features

**Person A** — already owns the simulator/attack side, so: verify the
`ghidra_setup.sh`/toolchain install on whichever laptop is actually
presenting, and rehearse the "quick trigger" buttons on the new page.

**Person B** — already owns detection: nothing new required, but review
`compute_and_record_risk()`'s weighting (70/30 split) and tune if the
risk chart doesn't feel dramatic enough on stage.

**Person C** — already owns the dashboard: review `pages/1_🔬_Firmware_Forensics.py`
styling matches the main dashboard's look, and rehearse the full click
path (inject → static scan → dynamic scan → Ghidra GUI) at least twice.



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
