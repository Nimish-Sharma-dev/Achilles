# ListFunctions.py — Ghidra headless post-script.
#
# Runs inside Ghidra's Jython environment after analyzeHeadless finishes
# auto-analysis on an imported binary. Walks the FunctionManager and dumps
# every defined function's name, entry address, and body size to a JSON
# file, which firmware_forensics.py then diffs between the baseline and
# current firmware imports.
#
# Invoked automatically by firmware_forensics.py via:
#   analyzeHeadless <project> <name> -import <elf> -scriptPath ghidra_scripts
#       -postScript ListFunctions.py <output.json>
#
# Can also be run manually from Ghidra's GUI Script Manager for a live
# on-stage walkthrough of a single binary.

import json

# getState(), currentProgram, getScriptArgs() are injected by Ghidra's
# script environment — this is not standalone Python.
args = getScriptArgs()
out_path = args[0] if args else "/tmp/ghidra_functions.json"

fm = currentProgram.getFunctionManager()
functions = []
for func in fm.getFunctions(True):
    if func.isThunk():
        continue
    functions.append({
        "name": func.getName(),
        "entry": str(func.getEntryPoint()),
        "body_size": int(func.getBody().getNumAddresses()),
    })

with open(out_path, "w") as f:
    json.dump(functions, f, indent=2)

print("ListFunctions.py: wrote %d functions to %s" % (len(functions), out_path))
