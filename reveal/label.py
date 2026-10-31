#!/usr/bin/env python3
"""Calibration and labeling sessions for registration R4 (run on Kaggle), on one Qiskit base.

Follows cart's r3/label_faults.py (fault sites, separate interpreters for candidates, crash and hang rule, rule E1,
event order, benchmark readings). Differences, all forced by the new items:

  * Items are end-to-end units of any source (R3, feature corpus, S1, S2) and pass-level items (reveal.worker).
  * Clean reference: every item is run by the clean build in five fresh interpreters (hash seeds 0 to 4). The set
    of clean results is the item's reference (reveal.checks: clean-result guard).
  * Checks run one at a time through reveal.checks.verdicts, so an unreadable gate makes one check not assessable.
  * The determinism lane uses reveal.worker (the frozen lane's worker can only build cart's corpus units). Its
    method is the frozen one: hash seeds 0, 1, 2 in fresh interpreters, a unit is non-deterministic when its
    fingerprints differ, and the lane detects a fault on a unit that was deterministic on the clean build.

    python -m reveal.label calibrate --items items.json --out out_NR4x
    python -m reveal.label label --items items.json --faults <dir> --site <clean site> --out out_R4x
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import shutil
import statistics as st
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
for _k, _v in {"RAYON_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "TRUE",
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}.items():
    os.environ.setdefault(_k, _v)

ROOT = Path(__file__).resolve().parents[1]
REF_HASHSEEDS = ("0", "1", "2", "3", "4")
LANE_HASHSEEDS = ("0", "1", "2")
EVENT_ORDER_SEED = 20261201
ITEM_ORDER_SEED = 20261202
REPEATS = 3


# ------------------------------------------------------------------------------------------------ helpers
def hardware() -> dict:
    import platform

    import qiskit
    info = {"python": sys.version, "platform": platform.platform(), "qiskit": qiskit.__version__,
            "qiskit_file": qiskit.__file__, "cpu_count": os.cpu_count()}
    try:
        info["cpu"] = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
    except Exception:
        pass
    return info


def bench(out: Path, tag: str) -> None:
    from obsaware.bench import reference_benchmark
    r = reference_benchmark()
    r["tag"] = tag
    with (out / "benchmark.jsonl").open("a") as f:
        f.write(json.dumps(r) + "\n")
    print(f"[bench {tag}] median {r['median_s']:.3f}s", flush=True)


def site_env(site: Path | None) -> dict:
    pp = [str(ROOT)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
    if site is not None:
        pp.insert(0, str(site))
    return {"PYTHONPATH": ":".join(pp)}


def run_worker(items: list[str], inputs: Path | None, tmp: Path, *, site: Path | None = None, hashseed="0",
               timeout: float | None = None) -> tuple[dict, dict, float]:
    """Returns (outputs, info, child CPU seconds)."""
    pk = tmp / f"out_{os.getpid()}_{hashseed}.pkl"
    env = dict(os.environ, PYTHONHASHSEED=hashseed, **site_env(site))
    k0 = os.times()
    proc = subprocess.run([sys.executable, "-m", "reveal.worker"], input=json.dumps(
        dict(items=items, inputs=str(inputs) if inputs else None, pickle=str(pk),
             expect_site=str(site) if site else None)), capture_output=True, text=True, env=env, timeout=timeout,
        cwd=str(ROOT))
    k1 = os.times()
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-3000:])
    with open(pk, "rb") as f:
        outs = pickle.load(f)
    pk.unlink()
    cpu = (k1.children_user - k0.children_user) + (k1.children_system - k0.children_system)
    return outs, json.loads(proc.stdout.strip().splitlines()[-1]), cpu


def item_kind(it: str) -> str:
    return "e2e" if it.startswith("U:") else "pass"


def fp_of(it: str, res, props, bind) -> str:
    from obsaware.oracles import fingerprint
    from reveal.checks import _bound
    from reveal.passlevel import pass_fingerprint
    r = _bound(res, bind)
    return fingerprint(r) if item_kind(it) == "e2e" else pass_fingerprint(r, props)


def unit_of(it: str):
    from reveal import units as U
    parts = it.split(":")
    return U.load(it[2:] if parts[0] == "U" else ":".join(parts[1:-2]))


# ------------------------------------------------------------------------------------------------ clean side
def snapshot_inputs(items: list[str], path: Path) -> None:
    from reveal.passlevel import snapshot_inputs as snap
    need: dict[str, list[str]] = {}
    for it in items:
        if it.startswith("P:") and it.endswith(":snap"):
            need.setdefault(":".join(it.split(":")[1:-2]), []).append(it)
    out = {}
    for uid, its in need.items():
        u = unit_of(its[0])
        s = snap(u.circuit, u.config)
        for it in its:
            if it.split(":")[-2] in s:
                out[it] = s[it.split(":")[-2]]
    with open(path, "wb") as f:
        pickle.dump(out, f)


def clean_reference(items: list[str], inputs: Path, out: Path, tmp: Path) -> dict:
    """Clean results of every item in five fresh interpreters. Stored: per item, the distinct fingerprints and
    one output per distinct fingerprint."""
    path = out / "clean_reference.pkl"
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    ref: dict[str, dict] = {it: {"fps": [], "outs": [], "props": [], "inps": [], "crash": None} for it in items}
    for hs in REF_HASHSEEDS:
        outs, _, _ = run_worker(items, inputs, tmp, hashseed=hs)
        for it, (status, res, props, _, inp) in outs.items():
            if status != "ok":
                ref[it]["crash"] = res
                continue
            fp = fp_of(it, res, props, unit_of(it).bind)
            if fp not in ref[it]["fps"]:
                ref[it]["fps"].append(fp)
                ref[it]["outs"].append(res)
                ref[it]["props"].append(props)
                ref[it]["inps"].append(inp)
    with open(path, "wb") as f:
        pickle.dump(ref, f)
    return ref


def calibrate_items(items: list[str], inputs: Path, ref: dict, out: Path, th) -> dict:
    """Per item: compile (or pass) CPU time, median of REPEATS after a warm-up, and every check's CPU time and
    clean verdict on the clean output."""
    from reveal.checks import CHECKS_E2E, CHECKS_PASS, verdicts
    from reveal.worker import run_items
    with open(inputs, "rb") as f:
        snaps = pickle.load(f)
    d = out / "items"
    d.mkdir(exist_ok=True)
    order = list(items)
    random.Random(ITEM_ORDER_SEED).shuffle(order)
    for i, it in enumerate(order, 1):
        p = d / (it.replace(":", "__").replace("/", "_") + ".json")
        if p.exists():
            continue
        r = ref[it]
        rec = dict(item=it, kind=item_kind(it), clean_results=len(r["fps"]), clean_crash=r["crash"])
        if r["crash"] or not r["outs"]:
            rec.update(usable=False)
            p.write_text(json.dumps(rec))
            continue
        run_items([it], snaps)                                          # warm-up
        rec["compile_s"] = st.median(run_items([it], snaps)[it][3] for _ in range(REPEATS))
        u = unit_of(it)
        inp = r["inps"][0]
        kind = item_kind(it)
        runs = [verdicts(kind, inp, r["outs"][0], r["outs"], u.config, u.bind, th, props=r["props"][0],
                         ref_props=r["props"]) for _ in range(REPEATS)]
        checks = CHECKS_E2E if kind == "e2e" else CHECKS_PASS
        rec["checks"] = {c: dict(cost=st.median(x[c]["cost"] for x in runs), assessable=runs[0][c]["assessable"],
                                 clean_pass=bool(runs[0][c]["assessable"] and runs[0][c]["alarm"] is False),
                                 error=runs[0][c]["error"]) for c in checks}
        rec["usable"] = True
        p.write_text(json.dumps(rec))
        if i % 100 == 0:
            print(f"calibrated {i}/{len(order)}", flush=True)
    return {json.loads(p.read_text())["item"]: json.loads(p.read_text()) for p in d.glob("*.json")}


def lane(items: list[str], inputs: Path, tmp: Path, *, site: Path | None = None, timeout=None) -> dict:
    """Determinism lane over the end-to-end items: LANE_HASHSEEDS fresh interpreters."""
    e2e = [it for it in items if it.startswith("U:")]
    fps: dict[str, set] = {it: set() for it in e2e}
    cpu, ctime = [], {it: [] for it in e2e}
    for hs in LANE_HASHSEEDS:
        outs, _, c = run_worker(e2e, inputs, tmp, site=site, hashseed=hs, timeout=timeout)
        cpu.append(c)
        for it, (status, res, props, t, _) in outs.items():
            fps[it].add(fp_of(it, res, props, unit_of(it).bind) if status == "ok" else f"crash:{res}")
            ctime[it].append(t or 0.0)
    fixed = [c - sum(ctime[it][j] for it in e2e) for j, c in enumerate(cpu)]
    return dict(launch_cpu_s=cpu, fixed_cpu_per_launch_s=fixed,
                per_unit={it: dict(deterministic=len(fps[it]) == 1, compile_s=ctime[it]) for it in e2e})


# ------------------------------------------------------------------------------------------------ sessions
def session_clean(items: list[str], out: Path, tmp: Path, th) -> tuple[dict, dict, dict, Path]:
    inputs = out / "snapshot_inputs.pkl"
    if not inputs.exists():
        snapshot_inputs(items, inputs)
    with open(inputs, "rb") as f:
        have = set(pickle.load(f))
    # a snapshot item exists only if its pass ran in the clean preset compilation of its unit
    items[:] = [it for it in items if not it.endswith(":snap") or it in have]
    ref = clean_reference(items, inputs, out, tmp)
    cal = calibrate_items(items, inputs, ref, out, th)
    lp = out / "determinism_lane.json"
    if not lp.exists():
        lp.write_text(json.dumps(lane(items, inputs, tmp), indent=1))
    return ref, cal, json.loads(lp.read_text()), inputs


def make_fault_site(fault_dir: Path, clean_site: Path, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(clean_site / "qiskit", dest / "qiskit")
    overlay = fault_dir / "overlay"
    for p in overlay.rglob("*"):
        if p.is_file():
            t = dest / p.relative_to(overlay)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, t)
    return dest


def candidates(items, inputs, site, tmp, cal) -> tuple[dict, dict]:
    """As R3: one interpreter for all items, limit 3x the clean time plus 600 s; on death or timeout, one
    interpreter per item with a limit of 10x its clean time plus 60 s."""
    total = sum(cal[it].get("compile_s", 0.0) for it in items)
    try:
        outs, info, _ = run_worker(items, inputs, tmp, site=site, timeout=3 * total + 600)
        return outs, info
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    outs, info = {}, {"per_item_fallback": True}
    for it in items:
        try:
            o, info0, _ = run_worker([it], inputs, tmp, site=site, timeout=10 * cal[it].get("compile_s", 1.0) + 60)
            outs.update(o)
            info.update(info0)
        except subprocess.TimeoutExpired:
            outs[it] = ("crash", "timeout", None, None, None)
        except RuntimeError as exc:
            outs[it] = ("crash", f"interpreter died: {str(exc)[-200:]}", None, None, None)
    return outs, info


def label_event(name, fault, items, inputs, ref, cal, lane_clean, site, tmp, th) -> dict:
    from reveal.checks import detections, verdicts
    outs, info = candidates(items, inputs, site, tmp, cal)
    with open(inputs, "rb") as f:
        snaps = pickle.load(f)
    per = {}
    for it in items:
        c = cal[it]
        if not c.get("usable"):
            continue
        appl = [k for k, v in c["checks"].items() if v["clean_pass"]]
        clean_cost = {k: c["checks"][k]["cost"] for k in appl}
        status, res, props, _, cinp = outs[it]
        if status == "crash":
            per[it] = dict(status="crash", error=res, detects={k: True for k in appl}, cost=clean_cost)
            continue
        u = unit_of(it)
        if fp_of(it, res, props, u.bind) in ref[it]["fps"]:
            per[it] = dict(status="unchanged", detects={k: False for k in appl}, cost=clean_cost)
            continue
        kind = item_kind(it)
        r = ref[it]
        # each output is checked against the input circuit it was pickled with (see reveal.worker)
        clean_v = verdicts(kind, r["inps"][0], r["outs"][0], r["outs"], u.config, u.bind, th, props=r["props"][0],
                           ref_props=r["props"])
        cand_v = verdicts(kind, cinp, res, r["outs"], u.config, u.bind, th, props=props, ref_props=r["props"])
        det = detections(clean_v, cand_v)
        per[it] = dict(status="changed", detects={k: det[k] for k in appl},
                       alarms={k: cand_v[k]["alarm"] for k in cand_v},
                       cost={k: cand_v[k]["cost"] for k in appl})
    try:
        total = sum(cal[it].get("compile_s", 0.0) for it in items if it.startswith("U:"))
        lf = lane(items, inputs, tmp, site=site, timeout=3 * total + 600)
        det_lane = dict(fixed_cpu_per_launch_s=lf["fixed_cpu_per_launch_s"],
                        per_unit={it: dict(detects=(not v["deterministic"]) and lane_clean["per_unit"][it]["deterministic"]
                                           and len(ref[it]["fps"]) == 1, cost=sum(v["compile_s"]))
                                  for it, v in lf["per_unit"].items()})
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        det_lane = dict(fixed_cpu_per_launch_s=lane_clean["fixed_cpu_per_launch_s"], crash=str(exc)[-500:],
                        per_unit={it: dict(detects=outs.get(it, ("ok",))[0] == "crash", cost=sum(v["compile_s"]))
                                  for it, v in lane_clean["per_unit"].items()})
    return dict(event=name, fault=fault, imported=info, per_item=per, determinism=det_lane)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["calibrate", "label"])
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--faults")
    ap.add_argument("--site")
    ap.add_argument("--work", default="/kaggle/working/fault_sites")
    ap.add_argument("--only-events", default=None, help="dry runs only")
    ap.add_argument("--shard", default=None, help="k/n: run the k-th of n parts of the event order (k from 1)")
    a = ap.parse_args()
    from cart.oracles.quality import QualityThresholds
    out, work = Path(a.out), Path(a.work)
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    tmp = work / "_tmp"
    tmp.mkdir(exist_ok=True)
    items = json.loads(Path(a.items).read_text())["items"]
    hw = hardware()
    hw["session"] = a.cmd
    (out / "hardware.json").write_text(json.dumps(hw, indent=1))
    th = QualityThresholds.load()
    bench(out, "start")
    ref, cal, lane_clean, inputs = session_clean(items, out, tmp, th)
    bench(out, "after_clean")
    if a.cmd == "calibrate":
        bench(out, "end")
        print("calibration done", flush=True)
        return 0

    fdir, site = Path(a.faults), Path(a.site)
    faults = {p.name: json.loads((p / "fault.json").read_text())
              for p in sorted(fdir.iterdir()) if (p / "fault.json").exists()}
    if a.only_events:
        faults = {k: v for k, v in faults.items() if k in a.only_events.split(",")}
    cons_path = out / "construction_check.json"
    if not cons_path.exists():
        cons = {}
        for name in faults:
            fs = make_fault_site(fdir / name, site, work / name)
            proc = subprocess.run([sys.executable, "-c", "import qiskit, qiskit.transpiler, qiskit._accelerate; "
                                   "print(qiskit.__version__, qiskit.__file__)"], capture_output=True, text=True,
                                  env=dict(os.environ, **site_env(fs)))
            ok = proc.returncode == 0 and str(fs) in proc.stdout
            cons[name] = {"constructible": ok, "error": None if ok else (proc.stderr or proc.stdout)[-500:]}
        cons_path.write_text(json.dumps(cons, indent=1))
    cons = json.loads(cons_path.read_text())
    excluded = sorted(k for k, v in cons.items() if not v["constructible"])
    print("excluded by rule E1:", excluded, flush=True)
    (out / "events").mkdir(exist_ok=True)
    names = sorted(faults)
    random.Random(EVENT_ORDER_SEED).shuffle(names)
    if a.shard:     # fixed split of the registered event order; every shard redoes the clean stage itself
        k, n = (int(x) for x in a.shard.split("/"))
        names = names[k - 1::n]
        print(f"shard {k}/{n}:", names, flush=True)
    for name in names:
        ev = out / "events" / f"{name}.json"
        if ev.exists() or name in excluded:
            continue
        t0 = time.time()
        fs = make_fault_site(fdir / name, site, work / name)
        rec = label_event(name, faults[name], items, inputs, ref, cal, lane_clean, fs, tmp, th)
        rec["wall_s"] = time.time() - t0
        ev.write_text(json.dumps(rec, indent=1))
        shutil.rmtree(fs, ignore_errors=True)
        n = sum(any(v["detects"].values()) for v in rec["per_item"].values())
        print(f"event {name:10s} items detecting {n:4d} ({rec['wall_s']:.0f}s)", flush=True)
        bench(out, f"after_{name}")
    bench(out, "end")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
