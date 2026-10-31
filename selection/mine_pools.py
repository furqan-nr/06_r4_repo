#!/usr/bin/env python3
"""Held-out fault pools for registration R4 (feasibility step; the rule is frozen in the registration).

Candidates are mined exactly as in cart's R3 rule, steps 1 to 4 (cart: r3/SELECTION.md):
a commit with a release note, a subject matching fix|bug|incorrect|wrong, changes under qiskit/ or crates/,
compilation-related files, and not contacted in earlier work. For each candidate the patch (restricted to
qiskit/ and crates/) is tested for clean reverse application on release tags.

Pools:
  B    : R3 window (2.0.0..5f9bf19d4), revertible on 2.6.1, compilation-related, not contacted, not an R3 fault.
         These are the fixes R3 rejected only because the R3 corpus did not run their changed code.
  C24  : window 1.0.0..2.0.0, revertible on 1.4.6, and every changed file still exists in 2.6.1.
  A231 : R3 window, not revertible on 2.6.1, revertible on 2.3.1.

Fault-blind: the script reads commit metadata, file paths and whether a patch applies. It never prints or
stores commit subjects, never opens a patch for reading by a person, and never compiles a circuit.

    python mine_pools.py --repo <qiskit clone with tags> --trees <dir with tree_<tag> checkouts> --out pools.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

R3_HEAD = "5f9bf19d4"
CONTACTED = {"11399", "13094", "14603", "14621", "14622", "14623", "14730", "14734", "14919", "14920", "14939",
             "14941", "14956", "14961", "14997", "15024", "15025", "15040", "15057", "16201", "16215", "16237",
             "16238", "16285"}
R3_FAULTS = {"13945", "14943", "15623", "16153", "16283", "16402", "16476", "16599", "16637", "16656", "16752",
             "16884", "16963", "16988", "17163"}
COMPILATION = ("qiskit/transpiler/", "qiskit/synthesis/", "qiskit/circuit/", "qiskit/dagcircuit/",
               "qiskit/passmanager/", "qiskit/compiler/", "qiskit/converters/", "crates/transpiler/",
               "crates/synthesis/", "crates/circuit/", "crates/accelerate/", "crates/quantum_info/")
NOT_COMPILATION = ("visualization", "qpy", "qasm", "primitives", "drawer", "result")


def sh(*a, cwd=None):
    return subprocess.run(a, capture_output=True, text=True, cwd=cwd)


def compilation_related(files):
    return any(f.startswith(COMPILATION) and not any(e in f for e in NOT_COMPILATION) for f in files)


def mine(repo, rng, tmp):
    log = sh("git", "log", "--format=@@%h|%ad|%s", "--date=short", "--name-only", rng, cwd=repo).stdout
    out = []
    for blk in log.split("@@")[1:]:
        lines = blk.strip().split("\n")
        h, d, s = lines[0].split("|", 2)
        f = lines[1:]
        if not any(x.startswith("releasenotes/notes/") for x in f) or not re.search(r"fix|bug|incorrect|wrong", s, re.I):
            continue
        if not any((x.startswith("qiskit/") and x.endswith(".py")) or x.startswith("crates/") for x in f):
            continue
        pr = (re.findall(r"#(\d+)\)?$", s) or [""])[-1]
        diff = sh("git", "diff", f"{h}^", h, "--", "qiskit/", "crates/", cwd=repo).stdout
        p = Path(tmp) / f"{pr or h}.diff"
        p.write_text(diff)
        files = [l[6:] for l in diff.splitlines() if l.startswith("+++ b/")]
        out.append(dict(id=pr or h, commit=h, date=d, rust=any(x.startswith("crates/") for x in f),
                        files=files, patch=str(p)))
    return out


def revertible(patch, tree):
    rv = sh("git", "apply", "-R", "--check", patch, cwd=tree).returncode == 0
    fw = sh("git", "apply", "--check", patch, cwd=tree).returncode == 0
    return rv and not fw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--trees", required=True, help="directory holding tree_1.4.6, tree_2.3.1, tree_2.6.1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t = lambda tag: os.path.join(a.trees, f"tree_{tag}")
    pools = {"B": [], "C24": [], "A231": []}
    with tempfile.TemporaryDirectory() as tmp:
        for c in mine(a.repo, f"2.0.0..{R3_HEAD}", tmp):
            if c["id"] in CONTACTED or c["id"] in R3_FAULTS or not compilation_related(c["files"]):
                continue
            if revertible(c["patch"], t("2.6.1")):
                pools["B"].append(c)
            elif revertible(c["patch"], t("2.3.1")):
                pools["A231"].append(c)
        for c in mine(a.repo, "1.0.0..2.0.0", tmp):
            if c["id"] in CONTACTED or not compilation_related(c["files"]):
                continue
            if revertible(c["patch"], t("1.4.6")) and all(os.path.exists(os.path.join(t("2.6.1"), f)) for f in c["files"]):
                pools["C24"].append(c)
    res = {name: [dict(id=c["id"], commit=c["commit"], date=c["date"], rust=c["rust"]) for c in lst]
           for name, lst in pools.items()}
    Path(a.out).write_text(json.dumps(dict(rule="selection/mine_pools.py", r3_head=R3_HEAD, pools=res), indent=1))
    print({k: len(v) for k, v in res.items()}, "| with Rust:", {k: sum(c["rust"] for c in v) for k, v in res.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
