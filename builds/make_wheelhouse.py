#!/usr/bin/env python3
"""Offline wheelhouse for one base, in the format of cart's R3 wheelhouse (MANIFEST.json + requirements file).

Our clean Qiskit wheel (builds/BUILD.md) plus Qiskit Aer and every dependency, downloaded for CPython 3.13 on
manylinux x86_64 (Kaggle's Python), then installed once with --target to check that the set is complete and imports.

    python builds/make_wheelhouse.py --qiskit-wheel <our wheel> --aer 0.17.2 --out <dir>/wheelhouse
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXTRA = ["scipy", "pyyaml", "psutil", "pandas"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qiskit-wheel", required=True, type=Path)
    ap.add_argument("--aer", required=True)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    shutil.copy(a.qiskit_wheel, a.out)
    qv = a.qiskit_wheel.name.split("-")[1]
    plat = ["--only-binary=:all:", "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313",
            "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux2014_x86_64", "--platform", "linux_x86_64"]
    subprocess.run([sys.executable, "-m", "pip", "download", "-q", "-d", str(a.out), *plat, "--find-links", str(a.out),
                    f"qiskit=={qv}", f"qiskit-aer=={a.aer}", *EXTRA], check=True)
    for p in a.out.glob("qiskit-*.whl"):              # keep ONLY our build of Qiskit, never a PyPI wheel
        if p.name != a.qiskit_wheel.name:
            p.unlink()
    wheels = sorted(p.name for p in a.out.glob("*.whl"))
    reqs = []
    for w in wheels:
        name, ver = w.split("-")[:2]
        reqs.append(f"{name.replace('_', '-')}=={ver}")
    (a.out / "requirements.txt").write_text("\n".join(reqs) + "\n")
    with tempfile.TemporaryDirectory() as site:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", str(a.out),
                        "--target", site, "-r", str(a.out / "requirements.txt")], check=True)
        chk = subprocess.run([sys.executable, "-c", "import qiskit, qiskit_aer; print(qiskit.__version__, qiskit_aer.__version__)"],
                             capture_output=True, text=True, env={"PYTHONPATH": site, "PATH": "/usr/bin:/bin"}).stdout.strip()
        import zipfile
        so = next(n for n in zipfile.ZipFile(a.qiskit_wheel).namelist() if n.startswith("qiskit/_accelerate"))
        ours = hashlib.sha256(zipfile.ZipFile(a.qiskit_wheel).read(so)).hexdigest()
        inst = hashlib.sha256((Path(site) / so).read_bytes()).hexdigest()
        if ours != inst:
            raise SystemExit("the installed Qiskit is not our build")
        chk += " (installed _accelerate equals our build)"
    man = {"qiskit_requested": qv, "aer_requested": a.aer, "import_check": chk,
           "qiskit_source": f"built from the Qiskit {qv} source tag (builds/BUILD.md), not the PyPI wheel",
           "python": platform.python_version(), "platform": platform.platform(),
           "install_method": "pip install --no-index --find-links <wheelhouse> --target <site> -r requirements.txt",
           "files": {w: hashlib.sha256((a.out / w).read_bytes()).hexdigest() for w in wheels}}
    (a.out / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(qv, "wheelhouse:", len(wheels), "wheels; import check:", chk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
