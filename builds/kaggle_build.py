#!/usr/bin/env python3
"""R5 fault builds on Kaggle, one base per call. Uses R4's builds/make_faults.py UNCHANGED (imported), with one
substitution: the Rust toolchain is pinned, instead of the moving "stable" channel that make_faults.build names.
Toolchain rule: 1.97.0, the toolchain of every R4 build. If 1.97.0 cannot compile the tag's clean source (newer
compilers reject some old dependencies, e.g. Qiskit 1.1.2 and 1.2.4), the toolchain the tag itself pins in
rust-toolchain.toml is used instead, for the clean build and every fault of that base.
Then: an import check of every fault, and a record of the toolchain.

    python kaggle_build.py <base> <input dir> <work dir> <output dir>
"""
import hashlib, json, os, platform, shutil, subprocess, sys, zipfile
from pathlib import Path

PACKAGING = {"1": ("74.1.3", "1.10.2"), "2.0": ("80.9.0", "1.11.1"), "2.1": ("80.9.0", "1.11.1"),
             "2.2": ("80.9.0", "1.11.1"), "2.3": ("80.9.0", "1.11.1"), "2.4": ("80.9.0", "1.11.1"),
             "2.5": ("80.9.0", "1.13.0")}
TOOLCHAIN = os.environ.get("R5_TOOLCHAIN", "1.97.0")   # local tests: "stable", which is 1.97.0 there


def run(*a, **k):
    print("+", " ".join(map(str, a)), flush=True)
    subprocess.run(a, check=True, **k)


def make_venv(path):
    """virtualenv, not venv: Kaggle's Python has no ensurepip, so `python -m venv` fails there."""
    try:
        import virtualenv  # noqa: F401
    except ImportError:
        run(sys.executable, "-m", "pip", "install", "-q", "virtualenv")
    run(sys.executable, "-m", "virtualenv", "-q", str(path))


def main():
    base, inp, work, outd = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    st, sr = PACKAGING.get(base[:3], PACKAGING.get(base[:1]))
    work.mkdir(parents=True, exist_ok=True)
    out = outd / f"r5build_{base}"
    if (out / "DONE").exists():
        print("already built", base); return
    # source: the release tag
    tree = work / f"tree_{base}"
    if not tree.exists():
        src_url = os.environ.get("R5_QISKIT_GIT", "https://github.com/Qiskit/qiskit.git")
        run("git", "clone", "-q", "--depth", "1", "--branch", base, src_url, str(tree))
    # packaging environment
    venv = work / f"venv_{base}"
    if not venv.exists():
        make_venv(venv)
        run(str(venv / "bin/pip"), "install", "-q", f"setuptools=={st}", f"setuptools-rust=={sr}", "wheel")
    # R4's build script, imported unchanged; the toolchain pinned
    sys.path.insert(0, str(inp))
    import make_faults as M

    tc = {"name": TOOLCHAIN}

    def build(src, target, o, pip):
        env = dict(os.environ, RUSTUP_TOOLCHAIN=tc["name"], CARGO_TARGET_DIR=str(target))
        o.mkdir(parents=True, exist_ok=True)
        M.sh(pip, "wheel", "--no-deps", "--no-build-isolation", "-w", str(o), ".", cwd=src, env=env)
        return next(o.glob("qiskit-*.whl"))
    M.build = build
    faults = json.loads((inp / f"faults_{base}.json").read_text())
    for f in faults["faults"]:
        f["patch"] = str(inp / f["patch"])
    fj = work / f"faults_{base}.json"
    fj.write_text(json.dumps(faults))
    (out / "faults").mkdir(parents=True, exist_ok=True)
    sys.argv = ["make_faults.py", "--source", str(tree), "--faults", str(fj), "--out", str(out / "faults"),
                "--work", str(work / f"w_{base}"), "--pip", str(venv / "bin/pip")]
    try:
        M.main()
    except RuntimeError as exc:
        if list((work / f"w_{base}" / "wheel_clean").glob("qiskit-*.whl")):
            raise                   # the clean build worked: a fault build failed, which is not a toolchain issue
        # the clean build failed with 1.97.0: switch to the tag's pinned toolchain and start the base again
        import re
        pinned = re.search(r'channel\s*=\s*"([^"]+)"', (tree / "rust-toolchain.toml").read_text()).group(1)
        print(f"clean build failed with {tc['name']}; using the tag's pinned toolchain {pinned}", flush=True)
        (out / "toolchain_fallback.txt").write_text(f"1.97.0 failed: {str(exc)[-1500:]}\nused: {pinned}\n")
        run("rustup", "toolchain", "install", pinned, "--profile", "minimal")
        tc["name"] = pinned
        shutil.rmtree(work / f"w_{base}", ignore_errors=True)
        shutil.rmtree(out / "faults", ignore_errors=True)
        (out / "faults").mkdir(parents=True)
        M.main()
    whl = next((out).glob("qiskit-*.whl"), None) or next((work / f"w_{base}" / "wheel_clean").glob("qiskit-*.whl"))
    if whl.parent != out:
        shutil.copy(whl, out / whl.name)
        whl = out / whl.name
    shutil.rmtree(work / f"w_{base}")            # the cargo target directories are large
    # import check (rule E1 in advance): clean Qiskit installed with its dependencies, each fault overlaid
    chk = work / f"check_{base}"
    if not chk.exists():
        make_venv(chk)
        run(str(chk / "bin/pip"), "install", "-q", str(whl))
    site = Path(subprocess.check_output([str(chk / "bin/python"), "-c",
                                         "import qiskit,os;print(os.path.dirname(os.path.dirname(qiskit.__file__)))"],
                                        text=True).strip())
    code = ("import qiskit,sys;from qiskit import QuantumCircuit,transpile;q=QuantumCircuit(3);q.h(0);q.cx(0,1);"
            "q.ccx(0,1,2);transpile(q,basis_gates=['cx','rz','sx','x'],optimization_level=2,seed_transpiler=1);"
            "print(qiskit.__file__)")
    res = {}
    for fdir in sorted((out / "faults").iterdir()):
        if not fdir.is_dir():
            continue
        fs = work / "fsite"
        if fs.exists():
            shutil.rmtree(fs)
        shutil.copytree(site / "qiskit", fs / "qiskit")
        for p in (fdir / "overlay").rglob("*"):
            if p.is_file():
                t = fs / p.relative_to(fdir / "overlay")
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t)
        r = subprocess.run([str(chk / "bin/python"), "-c", code], env=dict(os.environ, PYTHONPATH=str(fs)),
                           capture_output=True, text=True)
        res[fdir.name] = dict(imports=r.returncode == 0 and str(fs) in r.stdout, error=r.stderr[-300:])
    rustc = subprocess.check_output(["rustc", f"+{tc['name']}", "--version"], text=True).strip()
    (out / "build_info.json").write_text(json.dumps(dict(
        base=base, toolchain=rustc, setuptools=st, setuptools_rust=sr, python=platform.python_version(),
        machine=platform.machine(), clean_wheel=whl.name,
        clean_wheel_sha256=hashlib.sha256(whl.read_bytes()).hexdigest(),
        make_faults_sha256=hashlib.sha256((inp / "make_faults.py").read_bytes()).hexdigest(),
        import_check=res), indent=1))
    (out / "DONE").write_text("ok")
    print(base, "faults:", len(res), "import ok:", sum(v["imports"] for v in res.values()), flush=True)


if __name__ == "__main__":
    main()
