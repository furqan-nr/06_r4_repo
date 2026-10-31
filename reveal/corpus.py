"""The feature corpus: covering-array rows turned into units that compile on every clean base.

Replicates. Replicate r is a covering array built with seed CORPUS_SEED + r, and its units are drawn with the same
seed. Replicate 0 alone covers every allowed value pair. Later replicates give new circuits over the same pairs,
so the suite can be cut to any cost budget by taking whole replicates in order (the cut is made in suites.py).

Clean-validity rule (fault-blind, uses clean Qiskit only): for each row, attempts 0, 1, ... MAX_ATTEMPTS-1 are
drawn in order. The row's unit is the first attempt that (a) compiles without error on the clean build of every
base and (b) gives the same fingerprint in five fresh interpreters (hash seeds 0 to 4) on every base. A row with
no valid attempt is dropped and reported. Pair coverage is reported per replicate after dropping.

    python -m reveal.corpus rounds --pythons <py per base> --valid valid_<base>.json ... --work <dir>
    python -m reveal.corpus select --valid valid_*.json --out data/corpus.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import warnings
from functools import lru_cache
from pathlib import Path

CORPUS_SEED = 20261031
REPLICATES = 6
MAX_ATTEMPTS = 5
# Clean Qiskit 1.4.6 compiled three rzz-basis units to one of two results in about 1 run in 6, so stability
# is checked over five interpreters, not two.
STABILITY_HASHSEEDS = ("0", "1", "2", "3", "4")


def unit_id(r: int, i: int) -> str:
    return f"F{r}.{i:03d}"


@lru_cache(maxsize=None)
def _rows(seed: int) -> tuple:
    from reveal.features import covering_array
    return tuple(covering_array(seed=seed).as_dicts())


def load_unit(entry: dict):
    """Rebuild a selected unit from its corpus.json entry."""
    from reveal.generator import build_unit
    seed = CORPUS_SEED + entry["replicate"]
    rows = _rows(seed)
    u = build_unit(rows[entry["row"]], entry["row"], seed, entry["attempt"])
    u.unit_id = entry["unit"]
    return u


_WORKER = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
from qiskit.transpiler import generate_preset_pass_manager
from reveal.corpus import CORPUS_SEED, REPLICATES, unit_id
from reveal.features import covering_array
from reveal.generator import build_unit
from obsaware.oracles import fingerprint
out = {}
keys = json.load(open(sys.argv[2]))
arrays = {}
for key in keys:
    uid, a = key.rsplit(":", 1)
    r, i, a = int(uid[1:].split(".")[0]), int(uid.split(".")[1]), int(a)
    if r not in arrays:
        arrays[r] = covering_array(seed=CORPUS_SEED + r).as_dicts()
    row = arrays[r][i]
    if True:
        if True:
            try:
                u = build_unit(row, i, CORPUS_SEED + r, a)
                tq = generate_preset_pass_manager(**u.config).run(u.circuit)
                if u.bind:      # symbols are compiled unbound, then bound to the unit's values before any check
                    tq = tq.assign_parameters({p: u.bind[p.name] for p in tq.parameters})
                out[key] = {"ok": True, "fp": fingerprint(tq)}
            except Exception as e:
                out[key] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:200]}"}
print(json.dumps(out))
'''


def validate(out: Path, keys_file: Path, attempts: int = MAX_ATTEMPTS) -> None:
    """Validate the given keys ("<unit>:<attempt>") under this interpreter's Qiskit and MERGE into `out`."""
    import qiskit
    root = str(Path(__file__).resolve().parents[1])
    runs = []
    for hs in STABILITY_HASHSEEDS:  # fresh interpreters, different hash seeds
        env = dict(os.environ, PYTHONHASHSEED=hs, RAYON_NUM_THREADS="1", QISKIT_IN_PARALLEL="TRUE")
        p = subprocess.run([sys.executable, "-c", _WORKER, root, str(keys_file)], capture_output=True, text=True,
                           env=env)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-3000:])
        runs.append(json.loads(p.stdout.strip().splitlines()[-1]))
    res = {}
    for k in runs[0]:
        rs = [r[k] for r in runs]
        compiles = all(r["ok"] for r in rs)
        stable = len({r.get("fp") for r in rs}) == 1
        res[k] = {"ok": compiles and stable, "compiles": compiles, "stable": stable,
                  "err": next((r["err"] for r in rs if r.get("err")), None)}
    if out.exists():
        old = json.loads(out.read_text())["units"]
        old.update(res)
        res = old
    out.write_text(json.dumps({"qiskit": qiskit.__version__, "seed": CORPUS_SEED, "replicates": REPLICATES,
                               "attempts": attempts, "units": res}, indent=1))
    print(qiskit.__version__, sum(v["ok"] for v in res.values()), "of", len(res), "attempts valid so far")


def rounds(pythons: list[str], outs: list[Path], work: Path) -> None:
    """Lazy validation on several bases: round a tries attempt a only for rows that have no attempt valid on
    every base yet. One interpreter per base runs in parallel."""
    from reveal.features import covering_array
    allrows = [unit_id(r, i) for r in range(REPLICATES)
               for i in range(len(covering_array(seed=CORPUS_SEED + r).rows))]
    for a in range(MAX_ATTEMPTS):
        done = set()
        if all(o.exists() for o in outs):
            vs = [json.loads(o.read_text())["units"] for o in outs]
            done = {u for u in allrows if any(all(v.get(f"{u}:{b}", {}).get("ok") for v in vs) for b in range(a))}
        have = set.intersection(*[set(json.loads(o.read_text())["units"]) for o in outs]) if all(
            o.exists() for o in outs) else set()
        keys = [f"{u}:{a}" for u in allrows if u not in done and f"{u}:{a}" not in have]
        if not keys:
            break
        kf = work / f"keys_{a}.json"
        kf.write_text(json.dumps(keys))
        procs = [subprocess.Popen([py, "-m", "reveal.corpus", "validate", "--out", str(o), "--keys", str(kf)],
                                  cwd=str(Path(__file__).resolve().parents[1])) for py, o in zip(pythons, outs)]
        for pr in procs:
            if pr.wait() != 0:
                raise RuntimeError("validation failed")
        print(f"round {a}: {len(keys)} keys", flush=True)


def select(valid_files: list[Path], out: Path) -> None:
    from reveal.features import covering_array, pair_coverage
    vs = [json.loads(p.read_text()) for p in valid_files]
    attempts = vs[0]["attempts"]
    chosen, dropped, coverage = [], [], {}
    for r in range(vs[0]["replicates"]):
        rows = covering_array(seed=CORPUS_SEED + r).as_dicts()
        kept_rows = []
        for i, row in enumerate(rows):
            uid = unit_id(r, i)
            a = next((a for a in range(attempts) if all(v["units"].get(f"{uid}:{a}", {}).get("ok") for v in vs)),
                     None)
            if a is None:
                dropped.append({"unit": uid, "values": row})
            else:
                chosen.append({"unit": uid, "replicate": r, "row": i, "attempt": a, "values": row})
                kept_rows.append(row)
        coverage[r] = pair_coverage(kept_rows)
    out.write_text(json.dumps({"seed": CORPUS_SEED, "bases": [v["qiskit"] for v in vs], "units": chosen,
                               "dropped": dropped, "pair_coverage_per_replicate": coverage}, indent=1))
    print(len(chosen), "units kept,", len(dropped), "dropped; pair coverage per replicate",
          {k: round(v, 3) for k, v in coverage.items()})


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "rounds", "select"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--keys", type=Path)
    ap.add_argument("--valid", nargs="*", type=Path)
    ap.add_argument("--pythons", nargs="*")
    ap.add_argument("--work", type=Path)
    a = ap.parse_args()
    if a.cmd == "validate":
        validate(a.out, a.keys)
    elif a.cmd == "rounds":
        rounds(a.pythons, a.valid, a.work)
    else:
        select(a.valid, a.out)
