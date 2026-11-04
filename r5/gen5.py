"""R5 development generator: input dimensions added to the R4 feature model.

Every value is a construction from Qiskit's public interface:
  method     how body gates are built: plain, Gate.inverse(), Gate.power(k), Gate.power(-x), Gate.control(k, ctrl_state),
             inverse-then-control, control-then-inverse, QuantumCircuit.repeat(n) of the body
  hl_object  a library operation placed in the circuit: none, Clifford, LinearFunction, PermutationGate, QFTGate,
             parameterised PauliEvolutionGate, MCX with ancillas, StatePreparation, and on bases that have them
             adder, multiplier, phase oracle, Pauli product measurement
  qubits     register, anonymous qubits (no register), two registers
  params     the R4 values, plus a reused expression family (g, 2g, g + c)
  cflow      none, if/else with a copy of part of the body and its inverse, for loop, while loop with break
  mix        one gate group (R4) or gates from all groups
The R4 dimensions (basis, coupling, level, ...) are kept, so R4's configuration builder is reused.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

DIMS = {
    "method": ("plain", "inverse", "power_int", "power_neg", "control_state", "inv_ctrl", "ctrl_inv", "repeat"),
    "hl_object": ("none", "clifford", "linear_function", "permutation", "qft", "pauli_evo_param", "mcx_ancilla",
                  "state_prep", "adder", "multiplier", "phase_oracle", "ppm"),
    "qubits": ("register", "anonymous", "two_registers"),
    "params": ("none", "bound", "symbolic", "reused_expr"),
    "cflow": ("none", "if_else", "for_loop", "while_break"),
    "mix": ("one_group", "all_groups"),
    "level": ("0", "1", "2", "3"),
    "basis": ("cx_rz_sx_x", "cz_rz_sx_x", "ecr_rz_sx_x", "cx_p_u", "clifford_t", "with_rzz"),
    "coupling": ("all_to_all", "line", "ring", "heavy_hex"),
}


def available(value: str) -> bool:
    """High-level objects that a base's public library does not have are not available on that base."""
    import qiskit.circuit.library as L
    need = {"adder": "ModularAdderGate", "multiplier": "MultiplierGate", "phase_oracle": "PhaseOracleGate",
            "ppm": "PauliProductMeasurement", "qft": "QFTGate"}
    if value == "ppm":
        try:
            from qiskit.circuit.library import PauliProductMeasurement  # noqa: F401
            return True
        except ImportError:
            return False
    return value not in need or hasattr(L, need[value])


def allowed(row: dict) -> bool:
    g = row.get
    if g("basis") == "clifford_t":
        if g("params") not in (None, "none", "bound"):
            return False
        if g("hl_object") in ("pauli_evo_param", "state_prep", "multiplier", "phase_oracle"):
            return False
    if g("cflow") not in (None, "none") and g("hl_object") == "ppm":
        return False
    for k in ("hl_object",):
        if g(k) is not None and not available(g(k)):
            return False
    return True


def covering_array(seed: int, dims=DIMS, candidates: int = 60):
    """Strength-2 covering array (AETG greedy), as R4's features.covering_array."""
    rng = random.Random(seed)
    names = list(dims)
    vals = {k: [v for v in dims[k] if allowed({k: v})] for k in names}
    todo = {(a, va, b, vb) for i, a in enumerate(names) for b in names[i + 1:] for va in vals[a] for vb in vals[b]
            if allowed({a: va, b: vb})}
    rows = []
    while todo:
        best, gain = None, -1
        for _ in range(candidates):
            r = {k: rng.choice(vals[k]) for k in names}
            if not allowed(r):
                continue
            gn = sum(1 for (a, va, b, vb) in todo if r[a] == va and r[b] == vb)
            if gn > gain:
                best, gain = r, gn
        if gain <= 0:
            a, va, b, vb = next(iter(sorted(todo)))
            for _ in range(500):
                r = {k: rng.choice(vals[k]) for k in names}
                r[a], r[b] = va, vb
                if allowed(r):
                    best = r
                    break
            else:
                todo.discard((a, va, b, vb))
                continue
        rows.append(best)
        todo = {(a, va, b, vb) for (a, va, b, vb) in todo if not (best[a] == va and best[b] == vb)}
    return rows


@dataclass
class Unit5:
    unit_id: str
    row: dict
    circuit: object
    config: dict
    bind: dict


def _body_gate(qc, qubits, rng, row, P, gates):
    from qiskit.circuit.library import get_standard_gate_name_mapping
    names = gates
    name = rng.choice(names)
    gate = get_standard_gate_name_mapping()[name]
    k = gate.num_qubits
    if len(gate.params):
        vals = []
        for _ in gate.params:
            vals.append(P.next() if row["params"] != "none" else rng.uniform(-math.pi, math.pi))
        gate = type(gate)(*vals)
    m = row["method"]
    n = len(qubits)
    try:
        if m == "inverse":
            gate = gate.inverse()
        elif m == "power_int":
            gate = gate.power(rng.choice([2, 3]))
        elif m == "power_neg":
            gate = gate.power(-rng.choice([0.5, 1.0, 1.5]))
        elif m in ("control_state", "inv_ctrl", "ctrl_inv") and k + 1 <= n:
            cs = rng.randrange(2)
            if m == "inv_ctrl":
                gate = gate.inverse().control(1, ctrl_state=cs)
            elif m == "ctrl_inv":
                gate = gate.control(1, ctrl_state=cs).inverse()
            else:
                gate = gate.control(1, ctrl_state=cs)
            k += 1
    except Exception:
        pass
    qc.append(gate, rng.sample(qubits, k))


class _Params:
    def __init__(self, kind, rng):
        from qiskit.circuit import Parameter
        self.kind, self.rng, self.bind = kind, rng, {}
        self.g = Parameter("g")
        self.c = Parameter("c")
        self.i = 0

    def next(self):
        from qiskit.circuit import Parameter
        x = self.rng.uniform(-math.pi, math.pi)
        if self.kind in ("none",):
            return x
        if self.kind == "reused_expr":
            self.bind.setdefault("g", self.rng.uniform(-math.pi, math.pi))
            self.bind.setdefault("c", self.rng.uniform(-math.pi, math.pi))
            j = self.i % 3
            self.i += 1
            return (self.g, 2 * self.g, self.g + self.c)[j]
        p = Parameter(f"t{self.i}")
        self.i += 1
        self.bind[p.name] = x
        return p


def _hl_object(name, n, rng, rs, P):
    """Returns (operation, number of qubits) or None."""
    import qiskit.circuit.library as L
    from qiskit.quantum_info import Clifford, random_clifford, SparsePauliOp, Pauli
    if name == "clifford":
        k = min(3, n)
        return Clifford(random_clifford(k, seed=int(rs.integers(1 << 30)))), k
    if name == "linear_function":
        k = min(3, n)
        mat = np.eye(k, dtype=bool)
        for _ in range(4):
            a, b = rng.sample(range(k), 2)
            mat[a] ^= mat[b]
        return L.LinearFunction(mat), k
    if name == "permutation":
        perm = list(range(n)); rng.shuffle(perm)
        return L.PermutationGate(perm), n
    if name == "qft":
        return L.QFTGate(min(3, n)), min(3, n)
    if name == "pauli_evo_param":
        labels = ["".join(rng.choice("IXYZ") for _ in range(3)) for _ in range(3)]
        labels = [lab if lab != "III" else "ZZI" for lab in labels]
        t = P.next() if P.kind != "none" else rng.uniform(-1, 1)
        return L.PauliEvolutionGate(SparsePauliOp(labels, coeffs=[rng.uniform(-1, 1) for _ in labels]), time=t), 3
    if name == "mcx_ancilla":
        return L.MCXGate(min(3, n - 1)), min(4, n)
    if name == "state_prep":
        k = 2
        v = rs.normal(size=2 ** k) + 1j * rs.normal(size=2 ** k)
        return L.StatePreparation(v / np.linalg.norm(v)), k
    if name == "adder":
        return L.ModularAdderGate(2), 4 if n >= 4 else None
    if name == "multiplier":
        return (L.MultiplierGate(1), 4) if n >= 4 else None
    if name == "phase_oracle":
        return L.PhaseOracleGate("(a & b) | c"), 3
    if name == "ppm":
        from qiskit.circuit.library import PauliProductMeasurement
        return PauliProductMeasurement(Pauli(rng.choice(["Z", "X", "Y", "-Z"]) if True else "Z")), 1
    return None


GROUPS = {
    "clifford1": ("h", "s", "sdg", "x", "y", "z", "sx", "sxdg"),
    "rot1": ("p", "u", "rx", "ry", "rz", "r"),
    "ctrl2": ("cx", "cz", "cs", "csdg", "csx", "cp", "crx", "cu"),
    "inter2": ("swap", "iswap", "ecr", "rxx", "ryy", "rzz", "rzx", "xx_plus_yy", "dcx"),
    "multi3": ("ccx", "ccz", "cswap"),
}
CLIFFORD_T = ("h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap", "t", "tdg")


def build_unit(row, index, seed):
    from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
    from qiskit.circuit import Qubit, Clbit
    from reveal.generator import _config
    rng = random.Random(f"{seed}:{index}")
    from reveal.generator import hash_int
    rs = np.random.default_rng(hash_int(f"{seed}:{index}:np"))
    n = rng.randint(4, 5)
    if row["qubits"] == "anonymous":
        qc = QuantumCircuit([Qubit() for _ in range(n)], name=f"G{index}")
    elif row["qubits"] == "two_registers":
        qc = QuantumCircuit(QuantumRegister(2, "a"), QuantumRegister(n - 2, "b"), name=f"G{index}")
    else:
        qc = QuantumCircuit(QuantumRegister(n, "q"), name=f"G{index}")
    P = _Params(row["params"], rng)
    if row["basis"] == "clifford_t":
        gates = list(CLIFFORD_T)
    elif row["mix"] == "all_groups":
        gates = [g for grp in GROUPS.values() for g in grp]
    else:
        gates = list(GROUPS[rng.choice(list(GROUPS))])
    qs = list(range(n))
    for i in range(3 * n):
        _body_gate(qc, qs, rng, row, P, gates)
        if i % 3 == 2 and row["basis"] != "clifford_t":
            a, b = rng.sample(qs, 2)
            qc.cx(a, b)
    if row["method"] == "repeat":
        # QuantumCircuit.repeat names its instruction after the circuit, and an unnamed circuit is named from a
        # process-wide counter, so the unit would depend on what the interpreter built before: name it
        qc.name = f"body{index}"
        qc = qc.repeat(2)
    hl = _hl_object(row["hl_object"], n, rng, rs, P) if row["hl_object"] != "none" else None
    if hl:
        op, k = hl
        if op.num_clbits:
            qc.add_bits([Clbit() for _ in range(op.num_clbits)])
            qc.append(op, rng.sample(qs, op.num_qubits), qc.clbits[-op.num_clbits:])
        else:
            qc.append(op, rng.sample(qs, op.num_qubits))
    cf = row["cflow"]
    if cf != "none":
        cr = ClassicalRegister(1, "c")
        qc.add_register(cr)
        qc.measure(0, cr[0])
        part = qc.data[: max(2, len(qc.data) // 4)]
        part = [ins for ins in part if not ins.clbits and getattr(ins.operation, "_directive", False) is False]
        if cf == "if_else":
            with qc.if_test((cr, 1)) as else_:
                for ins in part:
                    qc.append(ins.operation, ins.qubits)
                    try:
                        qc.append(ins.operation.inverse(), ins.qubits)
                    except Exception:
                        pass
                if hl and hl[0].num_clbits == 0 and row["hl_object"] == "mcx_ancilla":
                    qc.append(hl[0], qc.qubits[: hl[0].num_qubits])
            with else_:
                qc.h(1)
                qc.cx(1, 2)
                qc.cx(1, 2)
        elif cf == "for_loop":
            with qc.for_loop(range(2)):
                for ins in part:
                    qc.append(ins.operation, ins.qubits)
        elif cf == "while_break":
            with qc.while_loop((cr, 0)):
                qc.h(0)
                qc.measure(0, cr[0])
                with qc.if_test((cr, 1)):
                    qc.break_loop()
    r4row = dict(basis={"clifford_t": "clifford_t"}.get(row["basis"], row["basis"]), coupling=row["coupling"],
                 level=row["level"], layout_routing="default", approx_threads="exact_1")
    config = _config(r4row, qc.num_qubits, rng)
    bind = dict(P.bind)
    if row["params"] == "bound" and qc.parameters:
        qc = qc.assign_parameters({p: bind[p.name] for p in qc.parameters})
        bind = {}
    return Unit5(f"G{index:03d}", dict(row), qc, config, bind)
