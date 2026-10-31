"""Turn one covering-array row into a test unit: a circuit, compile settings and parameter values.

The generator draws everything from its own seeded random sources (Python `random` and NumPy), never from
Qiskit's random helpers, so the same row and seed give the same circuit on Qiskit 1.4.6, 2.3.1 and 2.6.1.
`describe(circuit)` gives a version-independent text form that tests compare across versions.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.circuit import AnnotatedOperation, Gate, Parameter, ParameterVector
from qiskit.circuit.annotated_operation import ControlModifier, InverseModifier, PowerModifier
from qiskit.circuit.library import (
    PermutationGate, UnitaryGate, PauliEvolutionGate,
    TGate, TdgGate, HGate, SGate, SdgGate, XGate, YGate, ZGate, SXGate, SXdgGate,
    PhaseGate, U1Gate, UGate, RXGate, RYGate, RZGate, RGate,
    CXGate, CZGate, CSGate, CSdgGate, CSXGate, CPhaseGate, CRXGate, CUGate,
    SwapGate, iSwapGate, ECRGate, RXXGate, RYYGate, RZZGate, RZXGate, XXPlusYYGate, DCXGate,
    CCXGate, CCZGate, CSwapGate, MCXGate, MCPhaseGate,
)
from qiskit.quantum_info import Clifford, SparsePauliOp
from qiskit.transpiler import CouplingMap

from reveal.features import BASES

SEED_TRANSPILER = 1234
TWO_PI = 2 * math.pi

# name -> (constructor, number of qubits, number of angle parameters)
GATES: dict[str, tuple[Any, int, int]] = {
    "t": (TGate, 1, 0), "tdg": (TdgGate, 1, 0),
    "h": (HGate, 1, 0), "s": (SGate, 1, 0), "sdg": (SdgGate, 1, 0), "x": (XGate, 1, 0), "y": (YGate, 1, 0),
    "z": (ZGate, 1, 0), "sx": (SXGate, 1, 0), "sxdg": (SXdgGate, 1, 0),
    "p": (PhaseGate, 1, 1), "u1": (U1Gate, 1, 1), "u": (UGate, 1, 3), "rx": (RXGate, 1, 1), "ry": (RYGate, 1, 1),
    "rz": (RZGate, 1, 1), "r": (RGate, 1, 2),
    "cx": (CXGate, 2, 0), "cz": (CZGate, 2, 0), "cs": (CSGate, 2, 0), "csdg": (CSdgGate, 2, 0),
    "csx": (CSXGate, 2, 0), "cp": (CPhaseGate, 2, 1), "crx": (CRXGate, 2, 1), "cu": (CUGate, 2, 4),
    "swap": (SwapGate, 2, 0), "iswap": (iSwapGate, 2, 0), "ecr": (ECRGate, 2, 0), "rxx": (RXXGate, 2, 1),
    "ryy": (RYYGate, 2, 1), "rzz": (RZZGate, 2, 1), "rzx": (RZXGate, 2, 1), "xx_plus_yy": (XXPlusYYGate, 2, 2),
    "dcx": (DCXGate, 2, 0),
    "ccx": (CCXGate, 3, 0), "ccz": (CCZGate, 3, 0), "cswap": (CSwapGate, 3, 0),
}
GROUP_GATES = {
    "clifford1": ("h", "s", "sdg", "x", "y", "z", "sx", "sxdg"),
    "rot1": ("p", "u1", "u", "rx", "ry", "rz", "r"),
    "ctrl2": ("cx", "cz", "cs", "csdg", "csx", "cp", "crx", "cu"),
    "inter2": ("swap", "iswap", "ecr", "rxx", "ryy", "rzz", "rzx", "xx_plus_yy", "dcx"),
    "multi3": ("ccx", "ccz", "cswap", "mcx", "mcphase"),
}
# Gates that are exact in Clifford+T, used when the basis is clifford_t.
# (gates whose translation to Clifford+T is in the equivalence library of Qiskit 1.4 and 2.x).
CLIFFORD_T_SAFE = {"h", "s", "sdg", "x", "y", "z", "t", "tdg", "cx", "cz", "swap", "ccx"}
CLIFFORD_T_FOR_GROUP = {"rot1": ("t", "tdg", "s", "z")}


class CustomPythonGate(Gate):
    """A gate defined in Python with its own definition (the kind of gate behind multithreaded commutation
    issues). Two qubits, one angle."""

    def __init__(self, theta, label=None):
        super().__init__("pycustom", 2, [theta], label=label)

    def _define(self):
        q = QuantumRegister(2, "q")
        qc = QuantumCircuit(q, name=self.name)
        qc.h(0)
        qc.cx(0, 1)
        qc.rz(self.params[0], 1)
        qc.cx(0, 1)
        qc.h(0)
        self.definition = qc


@dataclass
class Unit:
    unit_id: str
    row: dict[str, str]
    circuit: QuantumCircuit
    config: dict[str, Any]                 # arguments for generate_preset_pass_manager
    threads: int                           # 1 or 2 (RAYON_NUM_THREADS for the compile)
    bind: dict[str, float] = field(default_factory=dict)   # values for unbound parameters, by name


# ------------------------------------------------------------------------------------------------ angles
def _angle(cls: str, rng: random.Random) -> float:
    if cls == "generic":
        return rng.uniform(0.05, TWO_PI - 0.05)
    if cls == "pi4_multiples":
        return rng.randint(-8, 8) * math.pi / 4
    if cls == "negative":
        return -rng.uniform(0.05, TWO_PI - 0.05)
    if cls == "near_zero":
        e = 10 ** rng.uniform(-9, -5)
        return rng.choice([e, -e, TWO_PI - e])
    if cls == "sum_2pi":            # single draws are generic, pairs that sum to 2pi are added by _body
        return rng.uniform(0.05, TWO_PI - 0.05)
    raise ValueError(cls)


def _haar_unitary(dim: int, rs: np.random.Generator) -> np.ndarray:
    z = (rs.standard_normal((dim, dim)) + 1j * rs.standard_normal((dim, dim))) / math.sqrt(2)
    q, r = np.linalg.qr(z)
    d = np.diag(r)
    return q * (d / np.abs(d))


def _clifford_object(k: int, rng: random.Random) -> Clifford:
    qc = QuantumCircuit(k)
    for _ in range(4 * k):
        c = rng.random()
        if c < 0.35:
            qc.h(rng.randrange(k))
        elif c < 0.7:
            qc.s(rng.randrange(k))
        else:
            a, b = rng.sample(range(k), 2)
            qc.cx(a, b)
    return Clifford(qc)


# ------------------------------------------------------------------------------------------------ build
class _Angles:
    """Hands out angle arguments according to the `params` and `angles` dimensions."""

    def __init__(self, params: str, cls: str, rng: random.Random):
        self.params, self.cls, self.rng = params, cls, rng
        self.bind: dict[str, float] = {}
        self._vec = ParameterVector("v", 12) if params == "vector" else None
        self._vi = 0
        self._n = 0

    def value(self, x: float | None = None):
        x = _angle(self.cls, self.rng) if x is None else x
        if self.params == "none":
            return x
        if self.params == "vector" and self._vi < len(self._vec):
            p = self._vec[self._vi]
            self._vi += 1
            self.bind[p.name] = x
            return p
        self._n += 1
        p = Parameter(f"t{self._n}")
        self.bind[p.name] = x
        if self.params == "expr_same_symbol":
            k = self._n % 3
            self.bind[p.name] = x / 2 if k == 0 else (x if k == 1 else x + 0.5)
            return p + p if k == 0 else (2 * p - p if k == 1 else p - 0.5 + p - p)
        return p


def _append_gate(qc: QuantumCircuit, name: str, qubits: list[int], ang: _Angles, cls: str):
    n = qc.num_qubits
    if name == "mcx":
        k = min(n, 4)
        qc.append(MCXGate(k - 1), qubits[:k] if len(qubits) >= k else list(range(k)))
        return
    if name == "mcphase":
        k = min(n, 4)
        qc.append(MCPhaseGate(ang.value(), k - 1), list(range(k)))
        return
    ctor, nq, npar = GATES[name]
    qc.append(ctor(*[ang.value() for _ in range(npar)]), qubits[:nq])


def build_unit(row: dict[str, str], index: int, seed: int, attempt: int = 0) -> Unit:
    """`attempt` > 0 redraws the unit for the same row (used only by the clean-validity rule in corpus.py)."""
    rng = random.Random(f"{seed}:{index}:{attempt}")
    rs = np.random.default_rng(abs(hash_int(f"{seed}:{index}:{attempt}:np")))
    n = rng.randint(3, 5)
    extra_idle = 2 if row["structure"] == "idle_qubits" else 0
    qr = QuantumRegister(n + extra_idle, "q")
    qc = QuantumCircuit(qr)
    ang = _Angles(row["params"], row["angles"], rng)
    names = list(GROUP_GATES[row["gate_group"]])
    if row["basis"] == "clifford_t":
        names = list(CLIFFORD_T_FOR_GROUP.get(row["gate_group"], [g for g in names if g in CLIFFORD_T_SAFE]))
        names = names or ["h", "s", "cx"]
    width_gates = [g for g in names if g in ("mcx", "mcphase") or GATES[g][1] <= n]

    # body: 3n gates of the group, with a background of h/cx so the circuit is entangling
    for i in range(3 * n):
        g = rng.choice(width_gates)
        k = 3 if g in ("mcx", "mcphase") else GATES[g][1]
        qs = rng.sample(range(n), k)
        _append_gate(qc, g, qs, ang, row["angles"])
        if row["angles"] == "sum_2pi" and g in ("p", "u1", "rz", "rx", "ry", "cp", "rzz", "rxx", "crx") and i % 2 == 0:
            # a second gate of the same kind on the same qubits so the two angles sum to 2pi (or 4pi)
            first = qc.data[-1].operation.params[0]
            try:
                x = float(first)
            except TypeError:       # a symbol or expression: evaluate it at the unit's bound values
                x = float(first.bind({q: ang.bind[q.name] for q in first.parameters}))
            ctor, nq, npar = GATES[g]
            qc.append(ctor(ang.value(rng.choice([TWO_PI, 2 * TWO_PI]) - x)), qs[:nq])
        if i % 3 == 2 and row["basis"] != "clifford_t":
            a, b = rng.sample(range(n), 2)
            qc.cx(a, b)

    # one block, placed in the middle of the circuit
    blk = row["block"]
    mid = QuantumCircuit(qr)
    if blk.startswith("unitary"):
        k = int(blk[-1])
        mid.append(UnitaryGate(_haar_unitary(2 ** k, rs)), rng.sample(range(n), k))
    elif blk == "clifford_obj":
        k = min(3, n)
        mid.append(_clifford_object(k, rng), rng.sample(range(n), k))
    elif blk == "pauli_evo":
        labels = ["".join(rng.choice("IXYZ") for _ in range(3)) for _ in range(3)]
        labels = [lab if lab != "III" else "XZI" for lab in labels]
        op = SparsePauliOp(labels, coeffs=[rng.uniform(-1, 1) for _ in labels])
        mid.append(PauliEvolutionGate(op, time=ang.value()), rng.sample(range(n), 3))
    elif blk == "permutation":
        perm = list(range(n))
        rng.shuffle(perm)
        mid.append(PermutationGate(perm), list(range(n)))
    elif blk == "custom_gate":
        mid.append(CustomPythonGate(ang.value()), rng.sample(range(n), 2))
    elif blk == "annotated":
        base = XGate() if row["basis"] == "clifford_t" else RYGate(ang.value())
        # explicit AnnotatedOperation objects: base.control(annotated=True) returns a standard controlled gate
        # on Qiskit 2.x but an annotated operation on 1.4, so the explicit form keeps every version's input equal
        mid.append(AnnotatedOperation(base, InverseModifier()), [rng.randrange(n)])
        mid.append(AnnotatedOperation(base, ControlModifier(1)), rng.sample(range(n), 2))
        mid.append(AnnotatedOperation(base, PowerModifier(2)), [rng.randrange(n)])
    half = len(qc.data) // 2
    head = QuantumCircuit(qr)
    for ins in qc.data[:half]:
        head.append(ins.operation, ins.qubits, ins.clbits)
    tail = QuantumCircuit(qr)
    for ins in qc.data[half:]:
        tail.append(ins.operation, ins.qubits, ins.clbits)
    qc = head.compose(mid).compose(tail)

    # structure
    st = row["structure"]
    if st == "inverse_pairs":
        out = QuantumCircuit(qr)
        for j, ins in enumerate(qc.data):
            out.append(ins.operation, ins.qubits)
            if j % 3 == 0:
                try:
                    op = ins.operation
                    # PauliEvolutionGate.inverse() differs between versions (a "_dg" gate on 1.4, negated time on
                    # 2.x), so its inverse is built explicitly
                    inv = (PauliEvolutionGate(op.operator, time=-op.time) if isinstance(op, PauliEvolutionGate)
                           else op.inverse())
                    out.append(inv, ins.qubits)
                    out.append(ins.operation, ins.qubits)
                except Exception:
                    pass
        qc = out
    elif st == "barrier_measure":
        qc.barrier()
        qc.measure_all()
    elif st == "control_flow":
        cr = ClassicalRegister(1, "c")
        qc.add_register(cr)
        qc.measure(0, cr[0])
        with qc.if_test((cr, 1)) as else_:
            qc.x(1)
            qc.cx(1, 2)
        with else_:
            qc.h(1)
        with qc.for_loop(range(2)):
            qc.cx(0, 2)
            qc.rz(ang.value(), 2) if row["basis"] != "clifford_t" else qc.s(2)
    elif st == "global_phase":
        qc.global_phase = _angle("generic", rng)

    bind = dict(ang.bind)
    if row["params"] == "bound":
        # built with symbols, then bound before compilation: the compiler sees numbers that passed through
        # the parameter machinery
        qc = qc.assign_parameters({p: bind[p.name] for p in qc.parameters})
        bind = {}

    config = _config(row, qc.num_qubits, rng)
    threads = 2 if row["approx_threads"].endswith("par") else 1
    return Unit(f"F{index:03d}", dict(row), qc, config, threads, bind)


def _config(row: dict[str, str], width: int, rng: random.Random) -> dict[str, Any]:
    cm = None
    c = row["coupling"]
    if c == "line":
        cm = CouplingMap.from_line(width)
    elif c == "ring":
        cm = CouplingMap.from_ring(width)
    elif c == "heavy_hex":
        cm = CouplingMap.from_heavy_hex(3)
    elif c == "one_way_line":
        cm = CouplingMap.from_line(width, bidirectional=False)
    cfg: dict[str, Any] = dict(optimization_level=int(row["level"]), basis_gates=list(BASES[row["basis"]]),
                               coupling_map=cm, seed_transpiler=SEED_TRANSPILER)
    if row["layout_routing"] == "sabre":
        cfg.update(layout_method="sabre", routing_method="sabre")
    elif row["layout_routing"] == "trivial_basic":
        cfg.update(layout_method="trivial", routing_method="basic")
    if row["approx_threads"].startswith("approx"):
        cfg["approximation_degree"] = 0.99
    return cfg


def hash_int(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:15], 16)


def describe(qc: QuantumCircuit, bind: dict[str, float] | None = None) -> str:
    """Version-independent text form of a circuit (for cross-version identity tests). Symbolic parameters are
    bound first, because Qiskit versions print the same expression differently."""
    if bind and qc.parameters:
        qc = qc.assign_parameters({p: bind[p.name] for p in qc.parameters})
    parts = [f"n={qc.num_qubits};c={qc.num_clbits};gp={qc.global_phase}"]
    for ins in qc.data:
        op = ins.operation
        ps = []
        if isinstance(op, Clifford):
            ps.append(hashlib.sha256(op.tableau.tobytes()).hexdigest()[:12])
        for p in getattr(op, "params", []):
            if isinstance(p, np.ndarray):
                ps.append(hashlib.sha256(np.round(p, 12).tobytes()).hexdigest()[:12])
            elif isinstance(p, QuantumCircuit):
                ps.append(describe(p))
            else:
                try:
                    ps.append(f"{round(float(p), 12) + 0.0:.12f}")    # rounding first, so -1e-15 and -0.0 print as 0
                except (TypeError, ValueError):
                    ps.append(str(p))
        if isinstance(op, AnnotatedOperation):
            ps.append(f"{op.base_op.name}{[str(m) for m in op.modifiers]}{[str(x) for x in op.base_op.params]}")
        if getattr(op, "blocks", None):
            ps.extend(describe(b) for b in op.blocks)
        qs = [qc.find_bit(q).index for q in ins.qubits]
        parts.append(f"{op.name}({','.join(ps)}){qs}")
    return "|".join(parts)
