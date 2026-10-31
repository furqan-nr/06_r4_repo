"""Clean-validity rule for every item, end to end and pass level (fault-blind: clean Qiskit only).

An item is valid on a base if it runs without error and gives the same fingerprint in five fresh interpreters
(hash seeds 0 to 4). An item enters a suite only if it is valid on every base. Feature-corpus units are already
selected this way in corpus.py (with redraws per row). Comparator units are not redrawn: an invalid one is
dropped and the pool keeps its order.

    python -m reveal.validity e2e  --units S1,S2 --out v_e2e_<base>.json
    python -m reveal.validity pass --units F,S1 --out v_pass_<base>.json
    python -m reveal.validity select --valid v_*_<base>.json ... --out valid_items.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from reveal.corpus import STABILITY_HASHSEEDS

_WORKER = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
from qiskit.transpiler import generate_preset_pass_manager
from reveal import units as U
from obsaware.oracles import fingerprint
mode, ids = sys.argv[2], json.load(open(sys.argv[3]))
out = {}
if mode == "e2e":
    for uid in ids:
        try:
            u = U.load(uid)
            tq = generate_preset_pass_manager(**u.config).run(u.circuit)
            if u.bind:
                tq = tq.assign_parameters({p: u.bind[p.name] for p in tq.parameters})
            out[uid] = {"ok": True, "fp": fingerprint(tq)}
        except Exception as e:
            out[uid] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:150]}"}
else:
    from reveal.passlevel import CATALOGUE, pass_fingerprint, run_pass, snapshot_inputs
    for uid in ids:
        u = U.load(uid)
        try:
            snaps = snapshot_inputs(u.circuit, u.config)
        except Exception:
            snaps = {}
        for name in CATALOGUE:
            for kind, qc in (("raw", u.circuit), ("snap", snaps.get(name))):
                if qc is None:
                    continue
                key = f"P:{uid}:{name}:{kind}"
                try:
                    o, props = run_pass(name, u.config, qc)
                    if u.bind and o.parameters:
                        o = o.assign_parameters({p: u.bind[p.name] for p in o.parameters})
                    out[key] = {"ok": True, "fp": pass_fingerprint(o, props)}
                except Exception as e:
                    out[key] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:150]}"}
print(json.dumps(out))
'''


def _ids(spec: str) -> list[str]:
    from reveal import units as U
    out = []
    for src in spec.split(","):          # "S1" or "S1:600" (the first 600 units of the pool)
        name, _, n = src.partition(":")
        out += U.all_ids(name, int(n) if n else None)
    return out


def validate(mode: str, ids: list[str], out_path: Path) -> None:
    import qiskit
    import tempfile
    root = str(Path(__file__).resolve().parents[1])
    idf = Path(tempfile.mkstemp(suffix=".json")[1])
    idf.write_text(json.dumps(ids))
    runs = []
    for hs in STABILITY_HASHSEEDS:
        env = dict(os.environ, PYTHONHASHSEED=hs, RAYON_NUM_THREADS="1", QISKIT_IN_PARALLEL="TRUE")
        p = subprocess.run([sys.executable, "-c", _WORKER, root, mode, str(idf)], capture_output=True,
                           text=True, env=env)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-3000:])
        runs.append(json.loads(p.stdout.strip().splitlines()[-1]))
    res = {}
    for k in sorted(set().union(*runs)):
        rs = [r.get(k, {"ok": False, "err": "missing in a run"}) for r in runs]
        compiles = all(r["ok"] for r in rs)
        stable = len({r.get("fp") for r in rs}) == 1
        res[k] = {"ok": compiles and stable, "compiles": compiles, "stable": stable,
                  "err": next((r["err"] for r in rs if r.get("err")), None)}
    out_path.write_text(json.dumps({"qiskit": qiskit.__version__, "mode": mode, "items": res}, indent=1))
    print(qiskit.__version__, mode, sum(v["ok"] for v in res.values()), "of", len(res), "valid")


def select(files: list[Path], out_path: Path) -> None:
    """Items valid on every base. Files are grouped by base (the 'qiskit' field); within a base, files merge."""
    by_base: dict[str, dict] = {}
    for f in files:
        d = json.loads(f.read_text())
        by_base.setdefault(d["qiskit"], {}).update(d["items"])
    bases = sorted(by_base)
    keys = set.intersection(*[set(v) for v in by_base.values()])
    kept = sorted(k for k in keys if all(by_base[b][k]["ok"] for b in bases))
    out_path.write_text(json.dumps({"bases": bases, "items": kept}, indent=1))
    print(len(kept), "items valid on", bases)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["e2e", "pass", "select"])
    ap.add_argument("--units")
    ap.add_argument("--valid", nargs="*", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    if a.cmd == "select":
        select(a.valid, a.out)
    else:
        validate(a.cmd, _ids(a.units), a.out)
