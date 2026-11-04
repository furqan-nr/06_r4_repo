"""Offline wheelhouse for one R5 base: our clean Qiskit wheel and its dependencies plus the extras the R5 driver and
cart's checks import, for CPython 3.13 manylinux x86_64 (Kaggle). The probe is not used in R5, so Qiskit Aer is
not included. The set is installed once with --target to check that it is complete and imports."""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
EXTRA = ["scipy", "pyyaml", "psutil", "pandas", "sympy", "python-constraint", "z3-solver"]
whl, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
shutil.copy(whl, out / whl.name)
plat = ["--only-binary=:all:", "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313",
        "--platform", "manylinux_2_28_x86_64", "--platform", "manylinux_2_17_x86_64", "--platform", "manylinux2014_x86_64",
        "--platform", "any", "--platform", "linux_x86_64"]
subprocess.run([sys.executable, "-m", "pip", "download", "-q", "-d", str(out), "--find-links", str(out), *plat,
                str(out / whl.name), *EXTRA], check=True)
with tempfile.TemporaryDirectory() as t:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", str(out), "--target", t,
                    str(out / whl.name), *EXTRA], check=True)
    v = subprocess.run([sys.executable, "-c", "import qiskit, scipy, sympy, constraint, z3, yaml, psutil, pandas;"
                        "print(qiskit.__version__, qiskit.__file__)"], env={"PYTHONPATH": t, "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True)
    assert v.returncode == 0 and t in v.stdout, v.stderr[-500:]
    print(v.stdout.strip().split()[0])
files = sorted(p.name for p in out.glob("*.whl"))
(out / "requirements.txt").write_text("\n".join([f"qiskit=={whl.name.split('-')[1]}"] + EXTRA) + "\n")
(out / "MANIFEST.json").write_text(json.dumps({f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in files}, indent=1))
