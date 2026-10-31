"""Input-feature model and a strength-2 covering array over it.

Every dimension and value comes from Qiskit's public interface (the standard gate library, `transpile` and
preset pass manager options) and from the post hoc R3 diagnosis. No held-out fault is consulted.

The covering array is built greedily (AETG style): each new row is the best of a fixed number of seeded random
candidates, scored by how many not-yet-covered value pairs it adds. Rows that violate a constraint are never
proposed. The result depends only on the dimensions, the constraints and the seed.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

DIMENSIONS: dict[str, tuple[str, ...]] = {
    # circuit content
    "gate_group": ("clifford1", "rot1", "ctrl2", "inter2", "multi3"),
    "block": ("none", "unitary1", "unitary2", "unitary3", "clifford_obj", "pauli_evo", "permutation",
              "custom_gate", "annotated"),
    "params": ("none", "bound", "symbolic", "vector", "expr_same_symbol"),
    "angles": ("generic", "pi4_multiples", "sum_2pi", "negative", "near_zero"),
    "structure": ("plain", "inverse_pairs", "barrier_measure", "control_flow", "idle_qubits", "global_phase"),
    # compilation options
    "level": ("0", "1", "2", "3"),
    "basis": ("cx_rz_sx_x", "cz_rz_sx_x", "ecr_rz_sx_x", "cx_p_u", "cx_rz_sx_sxdg_x", "clifford_t", "with_rzz"),
    "coupling": ("all_to_all", "line", "ring", "heavy_hex", "one_way_line"),
    "layout_routing": ("default", "sabre", "trivial_basic"),
    "approx_threads": ("exact_1", "approx_1", "exact_par", "approx_par"),
}

# Gate kinds per group, as names in qiskit.circuit.library (present in Qiskit 1.4 and 2.x).
GATE_GROUPS: dict[str, tuple[str, ...]] = {
    "clifford1": ("h", "s", "sdg", "x", "y", "z", "sx", "sxdg"),
    "rot1": ("p", "u1", "u", "rx", "ry", "rz", "r"),
    "ctrl2": ("cx", "cz", "cs", "csdg", "csx", "cp", "crx", "cu"),
    "inter2": ("swap", "iswap", "ecr", "rxx", "ryy", "rzz", "rzx", "xx_plus_yy", "dcx"),
    "multi3": ("ccx", "ccz", "cswap", "mcx", "mcphase"),
}

BASES: dict[str, tuple[str, ...]] = {
    "cx_rz_sx_x": ("cx", "rz", "sx", "x"),
    "cz_rz_sx_x": ("cz", "rz", "sx", "x"),
    "ecr_rz_sx_x": ("ecr", "rz", "sx", "x"),
    "cx_p_u": ("cx", "p", "u"),
    "cx_rz_sx_sxdg_x": ("cx", "rz", "sx", "sxdg", "x"),
    "clifford_t": ("cx", "h", "s", "sdg", "t", "tdg", "x", "y", "z"),
    "with_rzz": ("cz", "rz", "sx", "x", "rzz"),
}


def allowed(row: dict[str, str]) -> bool:
    """Constraints. A partial row (a dict with some dimensions) is checked on the dimensions it has."""
    g = row.get
    if g("basis") == "clifford_t":
        # Clifford+T needs every rotation to be a multiple of pi/4 and no block that is resynthesised as a
        # general unitary (permutations are, at levels 2 and 3, on the clean builds).
        if g("angles") not in (None, "pi4_multiples"):
            return False
        if g("block") not in (None, "none", "clifford_obj", "annotated"):
            return False
        if g("params") not in (None, "none", "bound"):
            return False
        if g("approx_threads") in ("approx_1", "approx_par"):
            return False
    if g("structure") == "control_flow" and g("layout_routing") == "trivial_basic":
        return False        # Qiskit rejects basic routing on circuits with control flow
    if g("coupling") == "all_to_all" and g("layout_routing") == "trivial_basic":
        return False        # routing has nothing to do without a coupling map
    return True


@dataclass(frozen=True)
class CoveringArray:
    rows: tuple[tuple[tuple[str, str], ...], ...]
    seed: int

    def as_dicts(self) -> list[dict[str, str]]:
        return [dict(r) for r in self.rows]


def _pairs(row: dict[str, str]):
    names = sorted(row)
    for a, b in itertools.combinations(names, 2):
        yield (a, row[a], b, row[b])


def allowed_pairs() -> set[tuple[str, str, str, str]]:
    out = set()
    names = sorted(DIMENSIONS)
    for a, b in itertools.combinations(names, 2):
        for va in DIMENSIONS[a]:
            for vb in DIMENSIONS[b]:
                if allowed({a: va, b: vb}):
                    out.add((a, va, b, vb))
    return out


def covering_array(seed: int = 20261031, candidates: int = 60, max_rows: int = 400) -> CoveringArray:
    rng = random.Random(seed)
    names = sorted(DIMENSIONS)
    todo = allowed_pairs()
    rows: list[dict[str, str]] = []
    while todo and len(rows) < max_rows:
        best, best_gain = None, -1
        for _ in range(candidates):
            # start from an uncovered pair, fill the rest greedily in a random dimension order
            a, va, b, vb = rng.choice(sorted(todo))
            row = {a: va, b: vb}
            for d in rng.sample(names, len(names)):
                if d in row:
                    continue
                opts = [v for v in DIMENSIONS[d] if allowed({**row, d: v})]
                scored = [(sum((p in todo) for p in _pairs({**row, d: v}) if d in (p[0], p[2])), v) for v in opts]
                top = max(s for s, _ in scored)
                row[d] = rng.choice(sorted(v for s, v in scored if s == top))
            gain = sum(p in todo for p in _pairs(row))
            if allowed(row) and gain > best_gain:
                best, best_gain = row, gain
        rows.append(best)
        todo -= set(_pairs(best))
    return CoveringArray(tuple(tuple(sorted(r.items())) for r in rows), seed)


def pair_coverage(rows: list[dict[str, str]]) -> float:
    """Share of allowed value pairs that at least one row covers (the adequacy measure reported per suite)."""
    allp = allowed_pairs()
    got = set()
    for r in rows:
        got |= {p for p in _pairs(r) if p in allp}
    return len(got) / len(allp)
