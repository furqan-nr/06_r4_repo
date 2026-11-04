#!/usr/bin/env python3
"""R5 session driver: one Qiskit base per session.

Stages, in order:
  1. clean reference: every item of every suite in fresh interpreters with PYTHONHASHSEED 0, 1 and 2. An item that
     crashes or hangs on clean is dropped. The clean result set of an item is the set of its fingerprints.
  2. events, in an order fixed by EVENT_ORDER_SEED: every held-out fault, the null control (clean Qiskit copied
     through the same fault-site machinery) and the benign events. Each event runs every item once
     (PYTHONHASHSEED 0) and records, per item: changed (fingerprint outside the clean set), crash or hang where clean
     succeeded, and the output and quality checks on changed outputs (rule L1: a check counts only if it passes on
     the clean output).
  3. clean screen: every item that changed under any event runs on clean Qiskit in 20 more interpreters
     (PYTHONHASHSEED 5 to 24). An item that ever leaves its clean set or fails is flaky.
Benchmark readings (R4's reference benchmark) are taken before stage 1, between events and at the end.

    python -m r5.session5 --base 2.1.2 --site <clean site> --builds <build dir> --out <dir> [--events a,b]
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import shelve
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT_ORDER_SEED = 20261105
CLEAN_HASHSEEDS = (0, 1, 2)
SCREEN_HASHSEEDS = tuple(range(5, 25))
HANG_S = 120            # an item that makes no progress for this long is a hang


# ------------------------------------------------------------------------------------------------ suites
def suites(base_spec: dict) -> dict[str, list[str]]:
    """Items of every suite, from data/suites_r5.json (frozen). RX pairs stay inside their suite."""
    from r5 import items5 as I
    s = json.loads(Path(os.environ.get("R5_SUITES", ROOT / "data" / "suites_r5.json")).read_text())   # override: rehearsal only
    out = {"S0": [f"TX|{u}|default" for u in s["S0"]]}
    from r5 import gen5
    g_ids = []
    for seed in s["G_seeds"]:
        n = len(gen5.covering_array(int(seed)))
        g_ids += [f"G{seed}.{i}" for i in range(min(n, s.get("G_max", n)))]     # G_max: rehearsal only
    out["S5"] = I.enumerate_items(s["F"]) + I.enumerate_items(g_ids)
    out["S1"] = I.enumerate_items(s["S1"])
    return out


# ------------------------------------------------------------------------------------------------ running
def _stream(pk: Path):
    if pk.exists():
        with open(pk, "rb") as f:
            while True:
                try:
                    yield pickle.load(f)
                except (EOFError, pickle.UnpicklingError):
                    return


def _env(site: Path, hs: int) -> dict:
    pp = [str(site), str(ROOT)] + [p for p in os.environ.get("R5_CODE_PATH", "").split(":") if p]
    return dict(os.environ, PYTHONPATH=":".join(pp), PYTHONHASHSEED=str(hs), RUST_BACKTRACE="0")


def run_chunk(items, site, hs, tmp, k, expect):
    files, dead, seg, todo = [], [], 0, list(items)
    while todo:
        pk = Path(tmp) / f"o_{hs}_{k}_{seg}.pkl"
        seg += 1
        cur = Path(str(pk) + ".cur")
        proc = subprocess.Popen([sys.executable, "-m", "r5.worker5"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=_env(site, hs), text=True, cwd=str(ROOT))
        proc.stdin.write(json.dumps(dict(items=todo, pickle=str(pk), expect=expect)))
        proc.stdin.close()
        last, size = time.time(), -1
        while proc.poll() is None:
            time.sleep(1)
            s = pk.stat().st_size if pk.exists() else 0
            if s != size:
                size, last = s, time.time()
            elif time.time() - last > HANG_S:
                proc.kill()
                proc.wait()
                break
        files.append(pk)
        done = {it for it, _ in _stream(pk)}
        rest = [it for it in todo if it not in done]
        if rest and proc.returncode != 0:
            c = cur.read_text() if cur.exists() else rest[0]
            dead.append(c)
            rest = [it for it in rest if it != c]
        todo = rest
    return files, dead


def run(items, site, hs, tmp, expect, consume, npar):
    chunks = [items[i::npar] for i in range(npar)]
    t0 = os.times()
    with ThreadPoolExecutor(npar) as ex:
        res = list(ex.map(lambda k: run_chunk(chunks[k], site, hs, tmp, k, expect), range(npar)))
    for files, dead in res:
        for pk in files:
            for it, r in _stream(pk):
                consume(it, r)
            pk.unlink(missing_ok=True)
            Path(str(pk) + ".cur").unlink(missing_ok=True)
        for it in dead:
            consume(it, ("crash", "hang or interpreter death", None, None, None, None))
    t1 = os.times()
    return (t1.children_user - t0.children_user) + (t1.children_system - t0.children_system)


def bench(out: Path, tag: str) -> None:
    from obsaware.bench import reference_benchmark
    r = reference_benchmark()
    r["tag"] = tag
    with (out / "benchmark.jsonl").open("a") as f:
        f.write(json.dumps(r) + "\n")
    print(f"[bench {tag}] median {r['median_s']:.3f}s", flush=True)


def make_site(overlay_dir: Path | None, clean_site: Path, dest: Path) -> Path:
    """Clean Qiskit copied, with the event's overlay files on top (no overlay: the null control)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copytree(clean_site / "qiskit", dest / "qiskit")
    if overlay_dir is not None:
        for p in overlay_dir.rglob("*"):
            if p.is_file():
                t = dest / p.relative_to(overlay_dir)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t)
    for p in clean_site.iterdir():
        if p.name != "qiskit" and not (dest / p.name).exists():
            os.symlink(p, dest / p.name)
    return dest


# ------------------------------------------------------------------------------------------------ stages
def clean_reference(items, site, out, tmp, npar):
    lp = out / "clean.json"
    # the clean outputs stay in the temporary folder (they are large); after a resume on a new machine they are
    # gone, and the clean reference is rebuilt
    if lp.exists() and list(Path(tmp).glob("clean_outputs*")):
        return json.loads(lp.read_text())
    light = {}
    with shelve.open(str(Path(tmp) / "clean_outputs")) as sh:
        def first(it, r):
            st, kind, f, inp, res, c = r
            light[it] = dict(fps=[f] if st == "ok" else [], kind=kind, cost=[c] if c is not None else [],
                             fail=None if st == "ok" else str(kind)[:200])
            if st == "ok":
                sh[it] = (inp, [res])
        cpu = run(items, site, CLEAN_HASHSEEDS[0], tmp, None, first, npar)
        print(f"clean hs={CLEAN_HASHSEEDS[0]}: {len(light)} items, {cpu:.0f}s cpu", flush=True)
        ex = Path(tmp) / "expect_clean.json"
        for hs in CLEAN_HASHSEEDS[1:]:
            ex.write_text(json.dumps({it: d["fps"] for it, d in light.items() if not d["fail"]}))

            def more(it, r):
                st, kind, f, inp, res, c = r
                d = light[it]
                if c is not None:
                    d["cost"].append(c)
                if d["fail"] or st == "same":
                    return
                if st != "ok":
                    d["fail"] = str(kind)[:200]
                    return
                if f not in d["fps"]:
                    d["fps"].append(f)
                    i0, outs = sh[it]
                    sh[it] = (i0, outs + [res])
            live = [it for it, d in light.items() if not d["fail"]]
            cpu = run(live, site, hs, tmp, str(ex), more, npar)
            print(f"clean hs={hs}: {cpu:.0f}s cpu", flush=True)
    for d in light.values():
        d["cost"] = statistics.median(d["cost"]) if d["cost"] else None
    lp.write_text(json.dumps(light))
    return light


def judge_event(name, site, ref, items, out, tmp, npar, th):
    from cart.oracles.quality import evaluate_quality
    from cart.oracles.semantic import check_semantic
    ex = Path(tmp) / "expect.json"
    if not ex.exists():
        ex.write_text(json.dumps({it: ref[it]["fps"] for it in items}))
    sh = shelve.open(str(Path(tmp) / "clean_outputs"), "r")
    per = {}

    def bad(cin, o):
        s = check_semantic(cin, o, coupling_map=None, basis_gates=None)
        return bool((s.equivalent is False) or (s.strength == "structural" and s.details.get("structural_ok") is False))

    def judge(it, r):
        st, kind, f, inp, res, c = r
        if st == "same":
            return
        if st != "ok":
            per[it] = dict(status="hang" if str(kind).startswith("hang") else "crash", detail=str(kind)[:200])
            return
        cin, couts = sh[it]
        rec = dict(status="changed", output=None, quality=None)
        try:
            rec["output"] = bad(cin, res) and not bad(cin, couts[0])
        except Exception as exc:
            rec["output_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        try:
            rec["quality"] = bool(all(evaluate_quality(ro, res, th).is_regression for ro in couts))
        except Exception as exc:
            rec["quality_error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        per[it] = rec
    t0 = time.time()
    cpu = run(items, str(site), 0, tmp, str(ex), judge, npar)
    sh.close()
    return dict(event=name, per_item=per, cpu_s=cpu, wall_s=time.time() - t0)


def screen(items, site, ref, out, tmp, npar):
    sp = out / "screen.json"
    done = json.loads(sp.read_text()) if sp.exists() else {}
    todo = [it for it in items if it not in done]
    if not todo:
        return done
    ex = Path(tmp) / "expect_screen.json"
    ex.write_text(json.dumps({it: ref[it]["fps"] for it in todo}))
    bad = {it: 0 for it in todo}
    for hs in SCREEN_HASHSEEDS:
        def c(it, r):
            if r[0] != "same":
                bad[it] += 1
        run(todo, site, hs, tmp, str(ex), c, npar)
    done.update(bad)
    sp.write_text(json.dumps(done, indent=0))
    return done


# ------------------------------------------------------------------------------------------------ main
def main() -> int:
    import r5.compat  # noqa: F401  (older Qiskit bases)
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--site", required=True, type=Path, help="clean Qiskit installed with --target")
    ap.add_argument("--builds", required=True, type=Path, help="r5 build set of the base (faults/, benign/)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--events", default="", help="comma-separated event ids (a shard); default: all")
    ap.add_argument("--npar", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--tmp", type=Path, default=Path("/tmp/r5tmp"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    a.tmp.mkdir(parents=True, exist_ok=True)
    (a.out / "events").mkdir(exist_ok=True)
    import platform
    hw = dict(cpu=next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), ""),
              cores=os.cpu_count(), python=platform.python_version(), base=a.base, npar=a.npar, start=time.time())
    (a.out / "hardware.json").write_text(json.dumps(hw, indent=1))
    bench(a.out, "start")
    S = suites({})
    items = sorted({it for v in S.values() for it in v})
    (a.out / "items.json").write_text(json.dumps(S))
    ref = clean_reference(items, a.site, a.out, a.tmp, a.npar)
    live = [it for it in items if not ref[it]["fail"]]
    print(f"{a.base}: {len(items)} items, {len(live)} clean-ok", flush=True)
    bench(a.out, "after_clean")
    events = {}
    for d in sorted((a.builds / "faults").iterdir()):
        if d.is_dir():
            events[d.name] = d / "overlay"
    for d in sorted((a.builds / "benign").iterdir()):
        if d.is_dir():
            events[d.name] = d / "overlay"
    events["NULL"] = None
    names = sorted(events)
    random.Random(EVENT_ORDER_SEED).shuffle(names)
    if a.events:
        want = set(a.events.split(","))
        names = [n for n in names if n in want]
    from cart.oracles.quality import QualityThresholds
    th = QualityThresholds.load()
    for n in names:
        o = a.out / "events" / f"{n}.json"
        if o.exists():
            continue
        site = make_site(events[n], a.site, a.tmp / "esite")
        rec = judge_event(n, site, ref, live, a.out, a.tmp, a.npar, th)
        o.write_text(json.dumps(rec))
        shutil.rmtree(site)
        print(f"event {n}: {len(rec['per_item'])} items differ, {rec['wall_s']:.0f}s", flush=True)
        bench(a.out, f"after_{n}")
    changed = sorted({it for p in (a.out / "events").glob("*.json") for it in json.loads(p.read_text())["per_item"]})
    screen(changed, a.site, ref, a.out, a.tmp, a.npar)
    bench(a.out, "end")
    (a.out / "DONE").write_text(json.dumps(dict(end=time.time())))
    print("session done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
