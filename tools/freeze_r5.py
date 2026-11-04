#!/usr/bin/env python3
"""Write PREREGISTRATION_R5.sha256 (python tools/freeze_r5.py) or verify it (python tools/freeze_r5.py --check).
R4's own manifest (PREREGISTRATION_R4.sha256, tools/freeze.py) is separate and unchanged."""
import hashlib, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FROZEN = ["PREREGISTRATION_R5.md", "r5/*.py", "data/suites_r5.json", "data/pools_r5.json", "selection/mine_r5.py",
          "selection/mine_benign.py", "builds/kaggle_build.py", "builds/make_wheelhouse5.py", "builds/split_deps.py",
          "builds/build_base_local.sh", "builds/records/build_[12].*.json", "builds/records/build_info_*.json",
          "kaggle/nb_r5_session.ipynb", "tools/freeze_r5.py"]
MANIFEST = ROOT / "PREREGISTRATION_R5.sha256"


def files():
    out = []
    for pat in FROZEN:
        hits = sorted(ROOT.glob(pat))
        if not hits:
            raise SystemExit(f"frozen file missing: {pat}")
        out += hits
    return out


if "--check" in sys.argv:
    bad = [n for h, n in (l.split("  ", 1) for l in MANIFEST.read_text().splitlines())
           if hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != h]
    print("all frozen files unchanged" if not bad else f"CHANGED: {bad}")
    raise SystemExit(1 if bad else 0)
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}" for p in files()]
MANIFEST.write_text("\n".join(lines) + "\n")
print(len(lines), "files frozen")
