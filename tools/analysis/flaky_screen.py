"""Usage: python flaky_screen.py <session dir> <clean site> <out json> <items json>

Post hoc screen: rerun the CLEAN build in 20 more fresh interpreters (hash seeds 5..24) on every item that was
'changed' or 'crash' under some fault, and record whether clean itself ever leaves the session's 5-run clean set."""
import os, sys, json, pickle, collections
from pathlib import Path
from reveal import label as L
sessdir, site, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
items = json.loads(Path(sys.argv[4]).read_text())
ref = pickle.load(open(sessdir / "clean_reference.pkl", "rb"))
tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "r4screen"; tmp.mkdir(exist_ok=True)
outside = collections.Counter()
for hs in range(5, 25):
    outs, _, _ = L.run_worker(items, sessdir / "snapshot_inputs.pkl", tmp, site=site, hashseed=str(hs))
    for it, (status, res, props, t, _) in outs.items():
        fp = L.fp_of(it, res, props, L.unit_of(it).bind) if status == "ok" else f"crash:{res}"
        if fp not in ref[it]["fps"]:
            outside[it] += 1
json.dump({it: outside[it] for it in items}, open(out, "w"))
print(sessdir.name, len(items), "items,", sum(1 for v in outside.values() if v), "flaky on clean")
