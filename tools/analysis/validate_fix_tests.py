#!/usr/bin/env python3
"""Post hoc fault validation (not registered). For each fault, the test files changed by its fix are taken at the
fix commit and run twice: on the clean Qiskit site, and on a copy of it with the fault's overlay. A triggering test
passes on clean and fails on the fault. A fault with a triggering test is "active".

    python tools/analysis/validate_fix_tests.py --qiskit-src <qiskit git clone> --faults faults.json \
        --site <clean site-packages folder> --overlays <folder with <id>/overlay> --tests <qiskit test tree of the base> \
        --base <version> --out <folder>

faults.json: a list of {"id", "commit"}, or {"faults": [...]}. One output file per fault: <base>_<id>.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def run_tests(site, troot, files, xml, timeout):
    env = dict(os.environ, PYTHONPATH=f"{site}:{troot}", PYTHONHASHSEED="0", RUST_BACKTRACE="0")
    try:
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"] + files,
                       cwd=troot, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    res = {}
    if Path(xml).exists():
        for tc in ET.parse(xml).getroot().iter("testcase"):
            bad = [c.tag for c in tc if c.tag in ("failure", "error")]
            skip = any(c.tag == "skipped" for c in tc)
            res[f"{tc.get('classname')}::{tc.get('name')}"] = "skip" if skip else ("fail" if bad else "pass")
    return res


def main():
    ap = argparse.ArgumentParser()
    for a in ("--qiskit-src", "--faults", "--site", "--overlays", "--tests", "--base", "--out"):
        ap.add_argument(a, required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--only", nargs="*", default=[])
    a = ap.parse_args()
    out, site = Path(a.out), Path(a.site)
    out.mkdir(parents=True, exist_ok=True)
    git = lambda *x: subprocess.run(["git", *x], capture_output=True, text=True, cwd=a.qiskit_src).stdout
    faults = json.loads(Path(a.faults).read_text())
    faults = faults["faults"] if isinstance(faults, dict) else faults
    for f in faults:
        if a.only and f["id"] not in a.only:
            continue
        o = out / f"{a.base}_{f['id']}.json"
        if o.exists():
            continue
        tests = [t for t in git("show", "--name-only", "--format=", f["commit"], "--", "test/").split() if t.endswith(".py")]
        rec = dict(id=f["id"], base=a.base, commit=f["commit"], test_files=tests)
        if not tests:
            rec["status"] = "no test files in fix"
        else:
            with tempfile.TemporaryDirectory() as tmp:
                troot = Path(tmp) / "t"
                shutil.copytree(Path(a.tests), troot / "test")
                have = []
                for t in tests:
                    src = git("show", f"{f['commit']}:{t}")
                    if src:
                        (troot / t).parent.mkdir(parents=True, exist_ok=True)
                        (troot / t).write_text(src)
                        have.append(t)
                fs = Path(tmp) / "fsite"
                shutil.copytree(site / "qiskit", fs / "qiskit")
                ov = Path(a.overlays) / f["id"] / "overlay"
                for p in ov.rglob("*"):
                    if p.is_file():
                        t = fs / p.relative_to(ov)
                        t.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, t)
                for p in site.iterdir():
                    if p.name != "qiskit":
                        os.symlink(p, fs / p.name)
                clean = run_tests(site, troot, have, Path(tmp) / "c.xml", a.timeout)
                fault = run_tests(fs, troot, have, Path(tmp) / "f.xml", a.timeout)
            rec["clean"], rec["fault"] = clean, fault
            if clean is None or fault is None:
                rec["status"] = "timeout"
            else:
                rec["triggers"] = sorted(t for t, v in fault.items() if v == "fail" and clean.get(t) == "pass")
                rec["status"] = ("active" if rec["triggers"] else
                                 "no clean-passing tests" if not any(v == "pass" for v in clean.values()) else "no trigger")
        o.write_text(json.dumps(rec, indent=1))
        print(a.base, f["id"], rec["status"], len(rec.get("triggers", [])), flush=True)


if __name__ == "__main__":
    main()
