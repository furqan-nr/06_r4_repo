"""Comparator corpora for RQ1: two strong simple baselines, generated without any feature design.

S1  Qiskit's own `random_circuit` (qiskit.circuit.random), full standard gate set with random parameters,
    3 to 5 qubits, depth 3 to 8, operations on up to 3 qubits, no measurement. The circuits are generated
    once with Qiskit 2.6.1 and stored as OpenQASM 2 (data/s1.json), so that every base compiles the same circuits.
S2  The circuit grammar of Qiskit's randomized transpiler test (test/randomized/test_transpiler_equivalence.py
    at 2.6.1): up to 3 quantum registers, the same instruction table and parameter range (-10 pi to 10 pi),
    and barriers. Measurement and reset are left out, because the frozen checks compare unitaries. The test's
    hypothesis search is replaced by a seeded random walk over the same grammar.

Compile options for both are drawn uniformly from the same option grid as the feature corpus (level, basis,
coupling, layout and routing, approximation and threads), subject to the same constraints, with a fixed seed.
Each corpus is an ordered pool. The cut to a cost budget is made in suites.py.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from qiskit import QuantumCircuit, QuantumRegister
from qiskit.circuit.library import (CCXGate, CPhaseGate, CSwapGate, CUGate, CXGate, CYGate, CZGate, HGate, IGate,
                                    PhaseGate, RXGate, RYGate, RZGate, RZZGate, SdgGate, SGate, SwapGate, TdgGate,
                                    TGate, UGate, XGate, YGate, ZGate)

from reveal.features import DIMENSIONS, allowed
from reveal.generator import Unit, _config

S1_SEED = 20261101
S2_SEED = 20261102
OPTION_DIMS = ("level", "basis", "coupling", "layout_routing", "approx_threads")
# Content of a comparator circuit, stated in feature terms so the shared constraints apply (arbitrary angles,
# no designed blocks or structure).
CONTENT = {"angles": "generic", "block": "none", "params": "none", "structure": "plain"}

S2_INSTRUCTIONS = {      # copied from BASE_INSTRUCTIONS of the Qiskit test, without Reset and Measure
    (1, 0): [HGate, IGate, SGate, SdgGate, TGate, TdgGate, XGate, YGate, ZGate],
    (2, 0): [CXGate, CYGate, CZGate, SwapGate],
    (3, 0): [CCXGate, CSwapGate],
    (1, 1): [PhaseGate, RXGate, RYGate, RZGate],
    (1, 3): [UGate],
    (2, 1): [RZZGate, CPhaseGate],
    (2, 4): [CUGate],
}


def draw_options(rng: random.Random) -> dict[str, str]:
    while True:
        row = dict(CONTENT, **{d: rng.choice(DIMENSIONS[d]) for d in OPTION_DIMS})
        if allowed(row):
            return row


# ------------------------------------------------------------------------------------------------ S1
def generate_s1(n_units: int, out: Path) -> None:
    """Run once, under Qiskit 2.6.1. Stores OpenQASM 2 text and the option row of every unit."""
    import qiskit
    from qiskit import qasm2
    from qiskit.circuit.random import random_circuit
    rng = random.Random(S1_SEED)
    units = []
    for i in range(n_units):
        n, depth = rng.randint(3, 5), rng.randint(3, 8)
        qc = random_circuit(n, depth, max_operands=3, measure=False, seed=rng.randrange(2**31))
        units.append({"unit": f"S1.{i:04d}", "qasm": qasm2.dumps(qc.decompose(reps=0)), "options": draw_options(rng),
                      "option_seed": rng.randrange(2**31)})
    out.write_text(json.dumps({"generated_with": qiskit.__version__, "seed": S1_SEED, "units": units}, indent=1))


def load_s1(entry: dict) -> Unit:
    from qiskit import qasm2
    qc = qasm2.loads(entry["qasm"], custom_instructions=qasm2.LEGACY_CUSTOM_INSTRUCTIONS)
    cfg = _config(entry["options"], qc.num_qubits, random.Random(entry["option_seed"]))
    threads = 2 if entry["options"]["approx_threads"].endswith("par") else 1
    return Unit(entry["unit"], entry["options"], qc, cfg, threads, {})


# ------------------------------------------------------------------------------------------------ S2
def build_s2(i: int) -> Unit:
    rng = random.Random(f"{S2_SEED}:{i}")
    qc = QuantumCircuit()
    for _ in range(rng.randint(1, 3)):                     # 1 to 3 registers, at most 5 qubits in total
        room = 5 - qc.num_qubits
        if room <= 0:
            break
        qc.add_register(QuantumRegister(rng.randint(1, room)))
    while qc.num_qubits < 3:
        qc.add_register(QuantumRegister(3 - qc.num_qubits))
    n = qc.num_qubits
    for _ in range(rng.randint(5, 25)):
        if rng.random() < 0.08:
            qs = rng.sample(range(n), rng.randint(1, n))
            qc.barrier(qs)
            continue
        nq, npar = rng.choice(sorted(S2_INSTRUCTIONS))
        gate = rng.choice(S2_INSTRUCTIONS[(nq, npar)])
        params = [rng.uniform(-10 * math.pi, 10 * math.pi) for _ in range(npar)]
        qc.append(gate(*params), rng.sample(range(n), nq))
    opts = draw_options(rng)
    cfg = _config(opts, n, rng)
    threads = 2 if opts["approx_threads"].endswith("par") else 1
    return Unit(f"S2.{i:04d}", opts, qc, cfg, threads, {})


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--s1-units", type=int, default=600)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    generate_s1(a.s1_units, a.out)
    print("S1 written:", a.out)
