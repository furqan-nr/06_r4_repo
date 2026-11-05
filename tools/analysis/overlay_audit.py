#!/usr/bin/env python3
"""Post hoc audit (errata E9): list fix commits that add, delete or rename files under qiskit/ or crates/. A fault
overlay only adds or replaces files, so such a commit would not be reverted completely.

    python tools/analysis/overlay_audit.py --qiskit-src <qiskit git clone> --events events.json --out overlay_audit.json
events.json: a list of {"registration", "base", "id", "commit"}.
"""
import argparse
import json
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
for x in ("--qiskit-src", "--events", "--out"):
    ap.add_argument(x, required=True)
a = ap.parse_args()
events = json.loads(Path(a.events).read_text())
hits = []
for e in events:
    out = subprocess.run(["git", "show", "--name-status", "-M", "--format=", e["commit"], "--", "qiskit/", "crates/"],
                         capture_output=True, text=True, cwd=a.qiskit_src).stdout
    odd = [ln for ln in out.splitlines() if ln and ln[0] in "ADR"]
    if odd:
        hits.append(dict(e, non_modify=odd))
Path(a.out).write_text(json.dumps(dict(n_events=len(events), events_with_add_delete_rename=hits), indent=1))
print(len(events), "events,", len(hits), "with added, deleted or renamed files")
