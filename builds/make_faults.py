#!/usr/bin/env python3
"""Build fault overlays for one base: each fault is the base's source with ONE merged fix reverted.

Isolation (lesson from cart's R3 builds, docs/DESIGN_LOG.md 2026-10-31): R3 built all faults in one shared cargo
target directory from copies of the pristine source that kept their old modification times. Cargo then kept a crate
reverted for one fault inside later faults' builds (R3's #16884 and #16963 builds also contain #17163). Here:

  1. the clean wheel is built once, and its target directory T0 is saved;
  2. every fault builds in a fresh COPY of T0 and a fresh copy of the source, at the same paths as the clean build
     (compiled code embeds source paths), with only the fault's files changed,
     so the only crates cargo recompiles are those the revert touches, and they are recompiled from the reverted
     source;
  3. a NULL fault (no revert) goes through the same pipeline first, and its wheel must equal the clean wheel in every
     file under qiskit/. If it does not, the build stops.
  4. Python-only faults need no build: their overlay is the reverted Python files.

The overlay of a fault is every file of its wheel (under qiskit/) that differs from the clean wheel.

    python builds/make_faults.py --source <tag checkout> --faults faults.json --out <dir> --work <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path


def sh(*a, cwd=None, env=None):
    p = subprocess.run(a, cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{a}: {p.stderr[-2000:]}")
    return p.stdout


def wheel_files(whl: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(whl) as z:
        return {n: z.read(n) for n in z.namelist() if n.startswith("qiskit/")}


def build(src: Path, target: Path, out: Path, pip: str) -> Path:
    env = dict(os.environ, RUSTUP_TOOLCHAIN="stable", CARGO_TARGET_DIR=str(target))
    out.mkdir(parents=True, exist_ok=True)
    sh(pip, "wheel", "--no-deps", "--no-build-isolation", "-w", str(out), ".", cwd=src, env=env)
    return next(out.glob("qiskit-*.whl"))


def fresh_source(source: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    root = str(source)

    def skip(d, names):         # build products are skipped at the TOP of the tree only: Qiskit 2.x has a source
        if d != root:           # module folder crates/transpiler/src/target that must be kept
            return set()
        return {n for n in names if n in (".git", "build", "target") or n.endswith(".egg-info")}
    shutil.copytree(source, dest, ignore=skip)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--faults", required=True, type=Path, help='JSON {"faults": [{"id", "patch", "rust"}, ...]}')
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--pip", default="pip")
    a = ap.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    a.out.mkdir(parents=True, exist_ok=True)
    # Every build uses the SAME source path and the SAME target path, because compiled code embeds source paths:
    # different paths alone would make a null build differ from the clean one. The clean target directory is saved
    # after the clean build and restored before every fault.
    src, tgt, t0 = a.work / "src", a.work / "target", a.work / "target_clean_saved"
    fresh_source(a.source, src)
    if tgt.exists():
        shutil.rmtree(tgt)
    clean_whl = build(src, tgt, a.work / "wheel_clean", a.pip)
    clean = wheel_files(clean_whl)
    if t0.exists():
        shutil.rmtree(t0)
    shutil.copytree(tgt, t0)
    record = {"clean_wheel_sha256": hashlib.sha256(clean_whl.read_bytes()).hexdigest(), "faults": {}}

    def fault_build(fid: str, patch: Path | None) -> dict[str, bytes]:
        fresh_source(a.source, src)
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(t0, tgt)
        if patch is not None:
            sh("git", "apply", "-R", str(patch.resolve()), cwd=src)
        out = a.work / f"wheel_{fid}"
        if out.exists():
            shutil.rmtree(out)
        whl = build(src, tgt, out, a.pip)
        files = wheel_files(whl)
        shutil.rmtree(out)
        return files

    null = fault_build("null", None)
    diff = sorted(n for n in set(clean) | set(null) if clean.get(n) != null.get(n))
    record["null_check"] = {"differing_files": diff}
    if diff:
        (a.out / "build_record.json").write_text(json.dumps(record, indent=1))
        raise SystemExit(f"null build differs from clean in {len(diff)} files: the build is not reproducible")

    for f in json.loads(a.faults.read_text())["faults"]:
        fid, patch = f["id"], Path(f["patch"])
        if f.get("rust"):
            files = fault_build(fid, patch)
            overlay = {n: b for n, b in files.items() if clean.get(n) != b}
        else:
            fresh_source(a.source, src)
            sh("git", "apply", "-R", str(patch.resolve()), cwd=src)
            overlay = {n: (src / n).read_bytes() for n in f["files"] if n.startswith("qiskit/") and (src / n).exists()}
        d = a.out / fid / "overlay"
        for n, b in overlay.items():
            (d / n).parent.mkdir(parents=True, exist_ok=True)
            (d / n).write_bytes(b)
        (a.out / fid / "fault.json").write_text(json.dumps({k: f[k] for k in f if k != "patch"}, indent=1))
        shutil.copy(clean_whl, a.out.parent / clean_whl.name) if not (a.out.parent / clean_whl.name).exists() else None
        record["faults"][fid] = {n: hashlib.sha256(b).hexdigest() for n, b in sorted(overlay.items())}
        print(fid, len(overlay), "overlay files", flush=True)
    (a.out / "build_record.json").write_text(json.dumps(record, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
