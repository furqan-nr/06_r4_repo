"""Run items in this interpreter and return their outputs pickled. Started by the driver in a fresh interpreter,
with a fault's Qiskit first on PYTHONPATH (or the clean Qiskit for clean reference runs).

Item ids:
  U:<unit id>                      end to end: generate_preset_pass_manager(**config).run(circuit)
  P:<unit id>:<pass>:raw|snap      pass level: one catalogue pass on a fixed input. Snapshot inputs are captured
                                   once from the CLEAN build and handed in pickled, so every build sees the same
                                   input.

stdin: JSON {"items": [...], "inputs": <path of pickled snapshot inputs or null>, "pickle": <out path>,
             "expect_site": <path or null>}
"""
from __future__ import annotations

import json
import os
import pickle
import sys
import time
import warnings


def run_items(items: list[str], snap_inputs: dict) -> dict:
    from qiskit.transpiler import generate_preset_pass_manager
    from reveal import units as U
    from reveal.passlevel import run_pass
    out = {}
    cache = {}
    for it in items:
        parts = it.split(":")
        uid = it[2:] if parts[0] == "U" else ":".join(parts[1:-2])
        try:
            u = cache.get(uid) or U.load(uid)
            cache[uid] = u
            t0 = time.process_time()
            if parts[0] == "U":
                res = generate_preset_pass_manager(**u.config).run(u.circuit)
                out[it] = ("ok", res, None, time.process_time() - t0, u.circuit)
            else:
                name, kind = parts[-2], parts[-1]
                inp = u.circuit if kind == "raw" else snap_inputs[it]
                res, props = run_pass(name, u.config, inp)
                out[it] = ("ok", res, props, time.process_time() - t0, inp)
        except BaseException as exc:          # a Rust panic surfaces as PanicException (a BaseException)
            if isinstance(exc, KeyboardInterrupt):
                raise
            out[it] = ("crash", f"{type(exc).__name__}: {str(exc)[:200]}", None, None, None)
    # Each result carries the input circuit it was made from, pickled together with the output. Checks that relate
    # the output to its input (cart's contract check K3 looks up the output's input qubits in the input circuit)
    # need the input's own bit objects: on Qiskit 1.4 bits compare by identity, so an input rebuilt in another
    # process does not match.
    return out


def main() -> None:
    warnings.filterwarnings("ignore")
    spec = json.loads(sys.stdin.read())
    import qiskit
    if spec.get("expect_site"):
        assert os.path.realpath(qiskit.__file__).startswith(os.path.realpath(spec["expect_site"])), qiskit.__file__
    snaps = {}
    if spec.get("inputs"):
        with open(spec["inputs"], "rb") as f:
            snaps = pickle.load(f)
    out = run_items(spec["items"], snaps)
    with open(spec["pickle"], "wb") as f:
        pickle.dump(out, f)
    print(json.dumps({"qiskit": qiskit.__version__, "file": qiskit.__file__}))


if __name__ == "__main__":
    main()
