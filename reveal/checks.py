"""The checks applied to one item, built from the frozen check functions by import (never edited).

End-to-end items: cart's output check (check_semantic), cart's quality check (evaluate_quality against the clean
output), obsaware's statevector probe (state_probe, with phase, simulated with Qiskit's reference Statevector through
the probe's own fallback; see _probe_reference_simulator) and obsaware's contract check (contract_v2). This is
the composition of obsaware/scripts/label_cohort.py::alarms_and_costs, with one change: each check runs on its own
and a check that raises is "not assessable" for that item, instead of failing every check of the item.

Pass-level items: output, quality and probe as above (input = the pass's input, no layout), and a pass contract
check: the property set entries the pass writes must equal the clean pass's entries.

Clean-result guard (non-determinism of clean Qiskit): the clean reference of an item is the SET of results seen in
repeated clean runs. A candidate whose fingerprint is in that set detects nothing. A quality alarm counts only if
the candidate is worse than every clean result.
"""
from __future__ import annotations

import time
from typing import Any

from qiskit import QuantumCircuit

CHECKS_E2E = ("output", "quality", "probe", "contract")
CHECKS_PASS = ("output", "quality", "probe", "pass_contract")


def _bound(qc: QuantumCircuit, bind: dict[str, float]) -> QuantumCircuit:
    if bind and qc.parameters:
        return qc.assign_parameters({p: bind[p.name] for p in qc.parameters if p.name in bind})
    return qc


def _probe_reference_simulator(state_probe, qi, qo):
    """The frozen state probe, run through its own documented fallback: Qiskit's reference Statevector instead of
    Aer. Aer rejects many gate kinds that the feature corpus contains on purpose (cs, csdg, xx_plus_yy, dcx,
    Clifford objects, Pauli evolutions, permutations, Python-defined gates), while Statevector simulates every
    gate that has a matrix or a definition. Hiding qiskit_aer makes the probe's `import qiskit_aer` raise
    ImportError, which is the branch the probe already has."""
    import sys
    saved = sys.modules.get("qiskit_aer", None)
    had = "qiskit_aer" in sys.modules
    sys.modules["qiskit_aer"] = None
    try:
        return state_probe(qi, qo, k=2)
    finally:
        if had:
            sys.modules["qiskit_aer"] = saved
        else:
            del sys.modules["qiskit_aer"]


def _timed(fn):
    t0 = time.process_time()
    try:
        return fn(), time.process_time() - t0, None
    except Exception as exc:
        return None, time.process_time() - t0, f"{type(exc).__name__}: {str(exc)[:120]}"


def verdicts(kind: str, inp: QuantumCircuit, out: QuantumCircuit, ref_outs: list[QuantumCircuit],
             cfg: dict[str, Any], bind: dict[str, float], th, *, props=None, ref_props=None) -> dict[str, dict]:
    """Alarm (True = property violated), assessable flag and CPU cost of every check on one output.

    `ref_outs` are the clean outputs of the item (the clean result set). For the clean output itself pass the
    clean outputs too: quality is then judged against them and does not alarm on a member of the set."""
    from cart.oracles.quality import evaluate_quality
    from cart.oracles.semantic import check_semantic
    from obsaware.oracles import PROBE_MAX_QUBITS, contract_v2, state_probe

    qi, qo = _bound(inp, bind), _bound(out, bind)
    refs = [_bound(r, bind) for r in ref_outs]
    res: dict[str, dict] = {}
    e2e = kind == "e2e"
    sem, c, err = _timed(lambda: check_semantic(qi, qo, coupling_map=cfg.get("coupling_map") if e2e else None,
                                                basis_gates=cfg.get("basis_gates") if e2e else None))
    res["output"] = dict(assessable=err is None, cost=c, error=err,
                         alarm=None if err else bool((sem.equivalent is False) or (
                             sem.strength == "structural" and sem.details.get("structural_ok") is False)))
    quals = [_timed(lambda r=r: evaluate_quality(r, qo, th)) for r in refs]
    qerr = next((q[2] for q in quals if q[2]), None)
    res["quality"] = dict(assessable=qerr is None, cost=sum(q[1] for q in quals) / max(len(quals), 1), error=qerr,
                          alarm=None if qerr else all(bool(q[0].is_regression) for q in quals))
    if qo.num_qubits <= PROBE_MAX_QUBITS:
        pr, c, err = _timed(lambda: _probe_reference_simulator(state_probe, qi, qo))
        ok = err is None and pr.assessable
        res["probe"] = dict(assessable=ok, cost=c, error=err,
                            alarm=bool(pr.record_ok is False or pr.phase_ok is False) if ok else None)
    else:
        res["probe"] = dict(assessable=False, cost=0.0, error="too_wide", alarm=None)
    if e2e:
        ct, c, err = _timed(lambda: contract_v2(qi, qo))
        ok = err is None and ct.holds is not None
        res["contract"] = dict(assessable=ok, cost=c, error=err, alarm=(ct.holds is False) if ok else None)
    else:
        t0 = time.process_time()
        ok = props is not None and ref_props is not None
        res["pass_contract"] = dict(assessable=ok, cost=time.process_time() - t0, error=None,
                                    alarm=(props not in ref_props) if ok else None)
    return res


def detections(clean: dict[str, dict], cand: dict[str, dict]) -> dict[str, bool]:
    """Rule L1: a check detects the fault on an item when it alarms on the candidate, was assessable there, and
    passed (assessable, no alarm) on the clean output."""
    return {c: bool(cand[c]["assessable"] and cand[c]["alarm"] and clean[c]["assessable"]
                    and clean[c]["alarm"] is False) for c in clean}
