#!/usr/bin/env python3
"""Packaging for Kaggle: the dependency wheels of every base's wheelhouse (builds/make_wheelhouse5.py) go into one
shared folder (dataset r5-deps), and each base keeps its Qiskit wheel and requirements_exact.txt, which pins every
package to the version its own wheelhouse was checked with.

    python builds/split_deps.py <folder with one <base>/wheelhouse per base> <deps folder>
"""
import shutil, sys
from pathlib import Path
final, deps = Path(sys.argv[1]), Path(sys.argv[2])
deps.mkdir(parents=True, exist_ok=True)
for wh in sorted(final.glob("*/wheelhouse")):
    pins = []
    for w in sorted(wh.glob("*.whl")):
        name, ver = w.name.split("-")[:2]
        pins.append(f"{name.replace('_', '-')}=={ver}")
        if not w.name.startswith("qiskit-") and not (deps / w.name).exists():
            shutil.copy(w, deps / w.name)
    (wh / "requirements_exact.txt").write_text("\n".join(pins) + "\n")
