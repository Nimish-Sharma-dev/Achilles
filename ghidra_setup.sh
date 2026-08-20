#!/usr/bin/env bash
# ghidra_setup.sh — run ONCE on the actual demo machine before presenting,
# not live on stage. Pre-imports both firmware binaries into a persistent
# Ghidra project so the GUI opens instantly during the demo instead of
# sitting through cold-start auto-analysis in front of judges.
#
# Usage:
#   export GHIDRA_HOME=/path/to/ghidra_11.x_PUBLIC
#   ./ghidra_setup.sh
set -euo pipefail

if [ -z "${GHIDRA_HOME:-}" ]; then
  echo "GHIDRA_HOME is not set."
  echo "Download Ghidra (free, NSA/GitHub releases): https://github.com/NationalSecurityAgency/ghidra/releases"
  echo "Needs a JDK 17+ on PATH. Then:"
  echo "  export GHIDRA_HOME=/path/to/extracted/ghidra_11.x_PUBLIC"
  echo "  ./ghidra_setup.sh"
  exit 1
fi

ANALYZE="$GHIDRA_HOME/support/analyzeHeadless"
if [ ! -x "$ANALYZE" ]; then
  echo "Can't find analyzeHeadless at $ANALYZE — check GHIDRA_HOME."
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$HERE/ghidra_project"
PROJECT_NAME="GridSentinelDemo"
mkdir -p "$PROJECT_DIR"

echo "== Importing + auto-analyzing baseline firmware =="
"$ANALYZE" "$PROJECT_DIR" "$PROJECT_NAME" \
  -import "$HERE/firmware/firmware_baseline.elf" -overwrite

echo "== Importing + auto-analyzing tampered firmware =="
"$ANALYZE" "$PROJECT_DIR" "$PROJECT_NAME" \
  -import "$HERE/firmware/firmware_tampered.elf" -overwrite

echo
echo "Done. Project at $PROJECT_DIR/$PROJECT_NAME.gpr"
echo "During the demo: open Ghidra GUI (ghidraRun), open that project,"
echo "double-click firmware_tampered.elf, and use Window > Function Graph"
echo "or the Decompile panel to show diag_selftest_ext() live to judges —"
echo "compare it side by side with firmware_baseline.elf, which won't have it."
