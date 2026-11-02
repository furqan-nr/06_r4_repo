"""Repeat the clean determinism lane n times. Usage: python lane_repeat.py <units,comma,separated> <n> <clean site> <session dir>"""
import os, sys, json
from pathlib import Path
from reveal import label as L
items = sys.argv[1].split(",")
n = int(sys.argv[2])
res = {it: 0 for it in items}
for i in range(n):
    r = L.lane(items, Path(sys.argv[4]) / "snapshot_inputs.pkl", Path(os.environ.get("TMPDIR", "/tmp")), site=Path(sys.argv[3]))
    for it in items:
        res[it] += (not r["per_unit"][it]["deterministic"])
print(json.dumps(dict(runs=n, nondeterministic=res)))
