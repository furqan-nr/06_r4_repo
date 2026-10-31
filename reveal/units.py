"""One loader for every end-to-end unit, by id prefix.

  R3:<test_id>   a unit of the frozen R3 corpus (cart), compiled with cart's frozen baseline transpiler config
  F<r>.<row>     a feature-corpus unit (data/corpus.json)
  S1.<i>         a Qiskit random_circuit unit (data/s1.json)
  S2.<i>         a unit of the randomized-test grammar (generated from its index)

Every loader returns a reveal.generator.Unit, whose `config` holds keyword arguments for
generate_preset_pass_manager and whose `bind` holds values for symbolic parameters.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from reveal.generator import Unit

DATA = Path(os.environ.get("REVEAL_DATA", Path(__file__).resolve().parents[1] / "data"))


@lru_cache(maxsize=None)
def _json(name: str) -> dict:
    return json.loads((DATA / name).read_text())


@lru_cache(maxsize=None)
def _corpus_index() -> dict:
    return {e["unit"]: e for e in _json("corpus.json")["units"]}


@lru_cache(maxsize=None)
def _s1_index() -> dict:
    return {e["unit"]: e for e in _json("s1.json")["units"]}


@lru_cache(maxsize=None)
def _r3_index() -> dict:
    from cart.manifest.static_manifest import enumerate_costhet_units
    return {u.test_id: u for u in enumerate_costhet_units()}


def load(uid: str) -> Unit:
    if uid.startswith("R3:"):
        from cart.labels.ground_truth import _base_config
        from cart.manifest.circuits import build
        u = _r3_index()[uid[3:]]
        cfg = _base_config(u)
        # cart's baseline transpiler is generate_preset_pass_manager with exactly these keys
        keys = ("optimization_level", "coupling_map", "basis_gates", "seed_transpiler")
        return Unit(uid, {"family": u.circuit_family}, build(u.circuit_family, u.n_qubits, seed=1234),
                    {k: cfg[k] for k in keys if k in cfg}, 1, {})
    if uid.startswith("F"):
        from reveal.corpus import load_unit
        return load_unit(_corpus_index()[uid])
    if uid.startswith("S1."):
        from reveal.comparators import load_s1
        return load_s1(_s1_index()[uid])
    if uid.startswith("S2."):
        from reveal.comparators import build_s2
        return build_s2(int(uid[3:]))
    raise KeyError(uid)


def all_ids(source: str, n: int | None = None) -> list[str]:
    if source == "R3":
        return [f"R3:{k}" for k in _r3_index()]
    if source == "F":
        return list(_corpus_index())
    if source == "S1":
        return list(_s1_index())[:n]
    if source == "S2":
        return [f"S2.{i:04d}" for i in range(n or 6000)]
    raise KeyError(source)
