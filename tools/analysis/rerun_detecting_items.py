#!/usr/bin/env python3
"""Post hoc (not registered): rerun up to N detecting items of each detected R5 fault on clean Qiskit and on the
fault build, each in a fresh interpreter. Records the outcome, the fingerprint, and for a crash the exception, the
innermost Qiskit frames and the innermost r5 frames (to tell input construction from compilation).

    python tools/analysis/rerun_detecting_items.py --channels results/r5/posthoc/per_fault_channels.json \
        --sites <folder with <base>/ clean sites> --builds <folder with <base>/faults/<id>/overlay> \
        --code <r5-code folder> --out results/r5/posthoc/item_reruns.json [--n 3]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROBE = r'''
import json, sys, traceback, warnings
warnings.filterwarnings("ignore")
import r5.compat
from obsaware.oracles import fingerprint
from r5 import items5 as I
it = sys.argv[1]
try:
    kind, inp, res = I.run_item(it)
    try:
        fp = fingerprint(res)
    except Exception as e:
        fp = "unfingerprintable:" + type(e).__name__
    print(json.dumps(dict(status="ok", fp=fp)))
except BaseException as exc:
    tb = traceback.extract_tb(exc.__traceback__)
    q = [f"{fr.filename.split('site-packages/')[-1].split('/fsite/')[-1]}:{fr.lineno}:{fr.name}" for fr in tb if "/qiskit/" in fr.filename]
    g = [f"{fr.filename.split('/')[-1]}:{fr.lineno}:{fr.name}" for fr in tb if "/r5/" in fr.filename]
    print(json.dumps(dict(status="crash", exc=f"{type(exc).__name__}: {str(exc)[:200]}", qiskit_frames=q[-4:], r5_frames=g[-3:])))
'''


def main():
    ap = argparse.ArgumentParser()
    for x in ("--channels", "--sites", "--builds", "--code", "--out"):
        ap.add_argument(x, required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()
    code = a.code
    cp = f"{code}:{code}/cart/cart/src:{code}/cart/obsaware/src"

    def run(site, it):
        env = dict(os.environ, PYTHONPATH=f"{site}:{cp}", PYTHONHASHSEED="0", RUST_BACKTRACE="0", REVEAL_DATA=f"{code}/data")
        try:
            p = subprocess.run([sys.executable, "-c", PROBE, it], cwd=code, env=env, capture_output=True, text=True,
                               timeout=a.timeout)
            line = [ln for ln in p.stdout.splitlines() if ln.startswith("{")]
            return json.loads(line[-1]) if line else dict(status="died", stderr=p.stderr[-300:])
        except subprocess.TimeoutExpired:
            return dict(status="hang")

    res = []
    for r in json.loads(Path(a.channels).read_text()):
        for s in ("S0", "S5", "S1p"):
            if not r[f"det:{s}"]:
                continue
            b, fid = r["base"], r["fault"]
            site = Path(a.sites) / b
            with tempfile.TemporaryDirectory() as tmp:
                fs = Path(tmp) / "fsite"
                shutil.copytree(site / "qiskit", fs / "qiskit")
                ov = Path(a.builds) / b / "faults" / fid / "overlay"
                for p in ov.rglob("*"):
                    if p.is_file():
                        t = fs / p.relative_to(ov)
                        t.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, t)
                for p in site.iterdir():
                    if p.name != "qiskit":
                        os.symlink(p, fs / p.name)
                for it in r[f"example_items:{s}"][:a.n]:
                    c, f = run(site, it), run(fs, it)
                    res.append(dict(base=b, fault=fid, suite=s, item=it, clean=c, fault_run=f,
                                    reproduced=c["status"] == "ok" and (f["status"] != "ok" or f.get("fp") != c.get("fp"))))
                    print(b, fid, s, it, c["status"], "->", f["status"], flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
