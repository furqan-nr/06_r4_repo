#!/usr/bin/env python3
"""Write PREREGISTRATION_R4.sha256: the SHA-256 of every frozen file of registration R4.

Frozen: the registration text, every module of the package, the selected corpus and comparator data, the item list,
the fault pools and their rule, the build and wheelhouse scripts, the Kaggle notebook and code-zip script, and the
identity test. The design log is not frozen: it keeps growing and is the source of the disclosure.

    python tools/freeze.py            (writes the manifest)
    python tools/freeze.py --check    (verifies every file against the manifest)
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ["PREREGISTRATION_R4.md", "pyproject.toml",
          "reveal/*.py", "data/corpus.json", "data/s1.json", "data/items.json",
          "selection/mine_pools.py", "selection/pools.json",
          "builds/make_faults.py", "builds/export_faults.py", "builds/make_wheelhouse.py", "builds/BUILD.md", "builds/records/*.json",
          "kaggle/nb_r4_session.ipynb", "kaggle/make_code_zip.py", "tests/identity.py", "tools/freeze.py"]
MANIFEST = ROOT / "PREREGISTRATION_R4.sha256"


def files() -> list[Path]:
    out = []
    for pat in FROZEN:
        hits = sorted(ROOT.glob(pat))
        if not hits:
            raise SystemExit(f"frozen file missing: {pat}")
        out += hits
    return out


def main() -> int:
    if "--check" in sys.argv:
        bad = 0
        for line in MANIFEST.read_text().splitlines():
            h, name = line.split("  ", 1)
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != h:
                print("CHANGED:", name)
                bad += 1
        print("all frozen files unchanged" if not bad else f"{bad} frozen files changed")
        return 1 if bad else 0
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}" for p in files()]
    MANIFEST.write_text("\n".join(lines) + "\n")
    print(len(lines), "files frozen in", MANIFEST.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
