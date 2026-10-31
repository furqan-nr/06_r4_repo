#!/usr/bin/env python3
"""Build the `r4-code` Kaggle dataset: this repository (at its registered commit) plus cart's frozen code at commit
198c867, taken with `git archive` so that nothing of cart is copied by hand or edited.

Layout inside the zip:
  reveal/  data/  builds/  kaggle/  docs/ ...      this repository
  cart/cart/  cart/obsaware/  cart/r3/             cart at 198c867 (only these three folders)

    python kaggle/make_code_zip.py --cart <cart clone> --out r4-code.zip
"""
from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import tarfile
import zipfile
from pathlib import Path

CART_COMMIT = "198c867"
CART_PATHS = ("cart", "obsaware", "r3")
SKIP = ("__pycache__", ".git", ".pyc")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cart", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    tar = subprocess.run(["git", "archive", "--format=tar", CART_COMMIT, *CART_PATHS], cwd=a.cart,
                         capture_output=True, check=True).stdout
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if p.is_file() and not any(s in str(rel) for s in SKIP):
                z.write(p, str(rel))
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            for m in t.getmembers():
                if m.isfile():
                    z.writestr(f"cart/{m.name}", t.extractfile(m).read())
    print(a.out, hashlib.sha256(a.out.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
