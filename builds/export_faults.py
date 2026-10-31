#!/usr/bin/env python3
"""Write the build list of one held-out pool for builds/make_faults.py: per fault, its patch (the fix commit's diff
restricted to qiskit/ and crates/), its changed files and whether it changes Rust.

Patches go to a work directory OUTSIDE the repository and are not committed before the registered results exist:
only their SHA-256 values are recorded (in the build record). Nothing is printed except counts, so no held-out
patch is displayed.

    python builds/export_faults.py --repo <qiskit clone> --pool C24 --out <work>/faults_C24.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--pool", required=True, choices=["C24", "A231", "B"])
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    pools = json.loads((ROOT / "selection" / "pools.json").read_text())["pools"]
    pdir = a.out.parent / f"patches_{a.pool}"
    pdir.mkdir(parents=True, exist_ok=True)
    faults = []
    for f in pools[a.pool]:
        diff = subprocess.run(["git", "diff", f"{f['commit']}^", f["commit"], "--", "qiskit/", "crates/"],
                              cwd=a.repo, capture_output=True, text=True, check=True).stdout
        p = pdir / f"{f['id']}.diff"
        p.write_text(diff)
        files = [l[6:] for l in diff.splitlines() if l.startswith("+++ b/")]
        faults.append(dict(id=f["id"], commit=f["commit"], date=f["date"], rust=f["rust"], files=files,
                           patch=str(p), patch_sha256=hashlib.sha256(diff.encode()).hexdigest()))
    a.out.write_text(json.dumps({"pool": a.pool, "faults": faults}, indent=1))
    print(a.pool, len(faults), "faults,", sum(f["rust"] for f in faults), "with Rust changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
