"""Pass-level test units: one transpiler pass run on one input, compared between clean and faulty Qiskit.

Why: in R3, two faults were caught when the faulty pass was tested on its own but never reached through the
preset compiler, because earlier passes rewrote the triggering gates or the pass is not scheduled by default.

Catalogue: optimisation and synthesis passes that exist in Qiskit 1.4.6, 2.3.1 and 2.6.1 and can run without the
layout state of a full compilation. Each entry builds the pass from the unit's basis and coupling, using only
constructor arguments that all three versions accept.

Inputs, both from the feature corpus:
  raw   the feature circuit itself (after binding nothing: symbols stay symbols, as in end-to-end units)
  snap  the circuit entering the same pass during a clean preset compilation of that feature circuit, captured
        once with the pass manager callback. Passes the preset does not schedule have no snap input.
"""
from __future__ import annotations

from typing import Any, Callable

from qiskit import QuantumCircuit
from qiskit.circuit.library import (CXGate, CZGate, HGate, SGate, SdgGate, TGate, TdgGate, CSGate, CSdgGate,
                                    XGate, SwapGate, ECRGate)
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler import CouplingMap, PassManager
from qiskit.transpiler import passes as P


def _basis(cfg):
    return list(cfg["basis_gates"])


def _cancel_set():
    return [CXGate(), CZGate(), HGate(), XGate(), SwapGate(), ECRGate(), (SGate(), SdgGate()), (TGate(), TdgGate()),
            (CSGate(), CSdgGate())]


# name -> builder(config) -> pass instance
CATALOGUE: dict[str, Callable[[dict[str, Any]], Any]] = {
    "Optimize1qGatesDecomposition": lambda c: P.Optimize1qGatesDecomposition(basis=_basis(c)),
    "Optimize1qGatesSimpleCommutation": lambda c: P.Optimize1qGatesSimpleCommutation(basis=_basis(c)),
    "CommutativeCancellation": lambda c: P.CommutativeCancellation(basis_gates=_basis(c)),
    "CommutativeInverseCancellation": lambda c: P.CommutativeInverseCancellation(),
    "InverseCancellation": lambda c: P.InverseCancellation(_cancel_set()),
    "ConsolidateBlocks": lambda c: P.ConsolidateBlocks(basis_gates=_basis(c)),
    "UnitarySynthesis": lambda c: P.UnitarySynthesis(basis_gates=_basis(c)),
    "HighLevelSynthesis": lambda c: P.HighLevelSynthesis(basis_gates=_basis(c)),
    "Split2QUnitaries": lambda c: P.Split2QUnitaries(),
    "RemoveIdentityEquivalent": lambda c: P.RemoveIdentityEquivalent(),
    "OptimizeCliffords": lambda c: P.OptimizeCliffords(),
    "Unroll3qOrMore": lambda c: P.Unroll3qOrMore(basis_gates=_basis(c)),
    "RemoveDiagonalGatesBeforeMeasure": lambda c: P.RemoveDiagonalGatesBeforeMeasure(),
    "OptimizeAnnotated": lambda c: P.OptimizeAnnotated(basis_gates=_basis(c)),
    "Decompose": lambda c: P.Decompose(),
    "Optimize1qGates": lambda c: P.Optimize1qGates(basis=_basis(c)),
}
# Passes that need a preceding pass in the same unit (the pair is the unit).
PRECEDED_BY = {
    "OptimizeCliffords": lambda c: P.CollectCliffords(),
}


def run_pass(name: str, cfg: dict[str, Any], qc: QuantumCircuit) -> tuple[QuantumCircuit, dict[str, Any]]:
    """Run one catalogue pass on a copy of `qc`. Returns the output circuit and the property set entries the
    pass wrote (as text), for the pass contract comparison."""
    tasks = []
    if name in PRECEDED_BY:
        tasks.append(PRECEDED_BY[name](cfg))
    tasks.append(CATALOGUE[name](cfg))
    pm = PassManager(tasks)
    out = pm.run(qc.copy())
    return out, canonical_props(dict(pm.property_set))


def canonical_props(ps: dict[str, Any]) -> dict[str, Any]:
    """Property set entries in a form that is equal across runs: plain values as they are, layouts as index maps,
    anything else by type name only (its repr may hold memory addresses)."""
    out: dict[str, Any] = {}
    for k in sorted(ps):
        v = ps[k]
        if v is None:
            continue
        if isinstance(v, (bool, int, float, str)):
            out[k] = v
        elif isinstance(v, (list, tuple)) and all(isinstance(x, (bool, int, float, str)) for x in v):
            out[k] = list(v)
        elif hasattr(v, "get_virtual_bits"):
            try:
                out[k] = sorted((str(getattr(q, "_index", "")), p) for q, p in v.get_virtual_bits().items())
            except Exception:
                out[k] = type(v).__name__
        else:
            out[k] = type(v).__name__
    return out


def snapshot_inputs(qc: QuantumCircuit, cfg: dict[str, Any]) -> dict[str, QuantumCircuit]:
    """The circuit entering each catalogue pass during a clean preset compilation (first occurrence)."""
    from qiskit.transpiler import generate_preset_pass_manager
    pm = generate_preset_pass_manager(**cfg)
    seen: dict[str, QuantumCircuit] = {}
    prev = {"circ": qc.copy()}

    # The callback sees the DAG after each pass. The input of a pass is the output of the previous one, kept as
    # a circuit copy because passes may change the DAG in place.
    def cb(pass_, dag, **_):
        n = type(pass_).__name__
        if n in CATALOGUE and n not in seen:
            seen[n] = prev["circ"]
        prev["circ"] = dag_to_circuit(dag)

    pm.run(qc, callback=cb)
    return seen


def pass_fingerprint(out: QuantumCircuit, props: dict[str, Any]) -> str:
    """Fingerprint of a pass-level result: the version-independent circuit description (which, unlike the
    frozen end-to-end fingerprint, can read Clifford and annotated objects that a pass leaves in place) plus the
    canonical property set."""
    import hashlib
    import json
    from reveal.generator import describe
    return hashlib.sha256((describe(out) + json.dumps(props, sort_keys=True)).encode()).hexdigest()
