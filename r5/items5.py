"""R5 development prototype: extended-reach items over the R4 feature corpus.

Every extension is enumerated from Qiskit's public interface on the base being tested:
  PX|uid|Pass|raw|low   every public pass class in qiskit.transpiler.passes whose required constructor arguments
                        can be filled from the unit's configuration, run alone on the raw circuit or on the
                        circuit lowered to the unit's basis and coupling (optimization level 0)
  HX|uid|op|plugin      HighLevelSynthesis with each registered plugin for each high-level operation in the unit
  TX|uid|variant        the unit's preset compilation with one public option changed (Target forms, scheduling,
                        layout, routing and translation methods)
  RX|uidA|uidB          one preset pass manager (unit B's options) run on unit A and then on unit B
"""
from __future__ import annotations

import inspect
import warnings

warnings.filterwarnings("ignore")

TX_VARIANTS = ("default", "target_nocm", "target_durations_alap", "target_durations_asap", "target_errors",
               "disjoint", "layout_dense", "layout_trivial", "routing_basic",
               "translation_synthesis", "approx_09")


_UNITS = {}


_ROWS = {}


def _unit(uid):
    from reveal import units as U
    if uid not in _UNITS:
        if uid.startswith("G"):            # R5 development unit: G<seed>.<index>
            from r5 import gen5
            seed, idx = uid[1:].split(".")
            if seed not in _ROWS:
                _ROWS[seed] = gen5.covering_array(int(seed))
            _UNITS[uid] = gen5.build_unit(_ROWS[seed][int(idx)], int(idx), int(seed))
        else:
            _UNITS[uid] = U.load(uid)
    return _UNITS[uid]


def _bound(qc, bind):
    if bind and qc.parameters:
        return qc.assign_parameters({p: bind[p.name] for p in qc.parameters if p.name in bind})
    return qc


def _cmap(cfg, n):
    from qiskit.transpiler import CouplingMap
    cm = cfg.get("coupling_map")
    return cm if cm is not None else CouplingMap.from_full(max(n, 2))


def _target(cfg, n, *, durations=False, errors=False, coupling=True):
    """A Target with the unit's basis on the unit's coupling (or on every qubit pair when coupling is False)."""
    from qiskit.circuit import Measure, Delay
    from qiskit.circuit.library import get_standard_gate_name_mapping
    from qiskit.transpiler import InstructionProperties, Target
    names = get_standard_gate_name_mapping()
    cm = _cmap(cfg, n)
    nq = max(cm.size(), n)
    t = Target(num_qubits=nq, dt=1e-9 if durations else None)
    edges = list(cm.get_edges())
    for k, g in enumerate(cfg.get("basis_gates") or ["cx", "rz", "sx", "x"]):
        gate = names[g]
        if gate.num_qubits == 1:
            qargs = [(q,) for q in range(nq)]
        elif gate.num_qubits == 2:
            qargs = edges
        else:
            continue
        props = {}
        for i, qa in enumerate(qargs):
            d = (32e-9 if gate.num_qubits == 1 else 320e-9) if durations else None
            e = (1e-4 * (1 + (i * 7 + k) % 5)) if errors else None
            props[qa] = InstructionProperties(duration=d, error=e) if (d or e) else None
        if not coupling:
            t.add_instruction(gate, None if gate.num_qubits > 1 else props)
        else:
            t.add_instruction(gate, props)
    t.add_instruction(Measure(), {(q,): InstructionProperties(duration=1e-6 if durations else None)
                                  for q in range(nq)})
    if durations:
        from qiskit.circuit import Parameter
        t.add_instruction(Delay(Parameter("t")), {(q,): None for q in range(nq)})
    return t


def _arg(name, cfg, n):
    """Fill one required constructor argument from the unit's configuration, or raise KeyError."""
    from qiskit.circuit.equivalence_library import SessionEquivalenceLibrary
    from qiskit.circuit.library import XGate
    if name in ("coupling_map",):
        return _cmap(cfg, n)
    if name in ("target",):
        return _target(cfg, n, durations=True)
    if name in ("basis_gates", "basis", "target_basis"):
        return list(cfg.get("basis_gates") or ["cx", "rz", "sx", "x"])
    if name in ("equivalence_library",):
        return SessionEquivalenceLibrary
    if name in ("durations", "instruction_durations"):
        return _target(cfg, n, durations=True).durations()
    if name in ("dd_sequence",):
        return [XGate(), XGate()]
    raise KeyError(name)


def public_passes():
    """Every public pass class of qiskit.transpiler.passes on this base. Analysis passes cannot change the circuit,
    but a fault can make them crash or hang, which the hang and crash rule detects."""
    from qiskit.transpiler import passes as P
    from qiskit.transpiler.basepasses import BasePass
    return sorted(n for n in dir(P) if inspect.isclass(getattr(P, n)) and issubclass(getattr(P, n), BasePass))


def physical_pass(name):
    """Passes that act on physical circuits (layout, routing, scheduling) also get the lowered input."""
    from qiskit.transpiler import passes as P
    mod = getattr(P, name).__module__
    return any(k in mod for k in (".layout.", ".routing.", ".scheduling.", ".padding."))


SKIP_PASSES = {"Error", "FixedPoint", "MinimumPoint", "FilterOpNodes", "CollectAndCollapse", "ContainsInstruction",
               "LayoutTransformation", "SetLayout",
               "LookaheadSwap"}   # LookaheadSwap: does not terminate on some inputs (a known limit of the pass)   # need an argument that is not a configuration value


_SK = {}


def make_pass(name, cfg, n, *, scheduled=False):
    from qiskit.transpiler import passes as P
    if name == "SolovayKitaev":      # its basic approximations take seconds to build on 1.x, so one instance
        if "sk" not in _SK:
            _SK["sk"] = P.SolovayKitaev()
        return _SK["sk"]
    cls = getattr(P, name)
    sig = inspect.signature(cls.__init__)
    kw = {}
    for p in list(sig.parameters.values())[1:]:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        if p.default is p.empty:
            kw[p.name] = _arg(p.name, cfg, n)
        elif p.name == "target":
            kw[p.name] = _target(cfg, n, durations=scheduled)
        elif p.name in ("dd_sequence", "supported_gates") or (p.name == "durations" and scheduled):
            kw[p.name] = _arg("basis_gates" if p.name == "supported_gates" else p.name, cfg, n)
        elif p.name in ("seed", "seed_transpiler"):
            # determinism: standalone layout and routing passes otherwise draw a random seed per run, so they get the
            # unit's transpiler seed, as the preset pass managers give them
            kw[p.name] = cfg.get("seed_transpiler", 1234)
        elif p.name == "time_limit":
            # a wall-clock limit makes the result depend on machine speed: off, the pass's call limits stay
            kw[p.name] = None
        elif p.name == "swap_strategy":
            from qiskit.transpiler.passes.routing.commuting_2q_gate_routing import SwapStrategy
            kw[p.name] = SwapStrategy.from_line(list(range(n)))
    if name == "InverseCancellation":
        from reveal.passlevel import _cancel_set
        kw = {"gates_to_cancel": _cancel_set()}
    return cls(**kw)


LAYOUT_FIRST = {"BasicSwap", "LookaheadSwap", "SabreSwap", "StochasticSwap", "ApplyLayout", "EnlargeWithAncilla",
                "FullAncillaAllocation", "GateDirection", "CheckGateDirection", "CheckMap", "Layout2qDistance"}
PRECEDED = {"Commuting2qGateRouter": "FindCommutingPauliEvolutions", "OptimizeCliffords": "CollectCliffords",
            "OptimizeCliffordT": None}


def preamble(name, cfg, n, kind):
    """Public passes a pass needs before it in the same pass manager."""
    from qiskit.transpiler import passes as P
    if name in LAYOUT_FIRST and kind == "raw":
        cm = _cmap(cfg, n)
        return [P.TrivialLayout(cm), P.FullAncillaAllocation(cm), P.EnlargeWithAncilla(), P.ApplyLayout()]
    if name in SCHEDULING_PASSES and kind == "low":
        return [P.ALAPScheduleAnalysis(target=_target(cfg, n, durations=True))]
    pre = PRECEDED.get(name)
    if pre and hasattr(P, pre):
        return [getattr(P, pre)()]
    return []


SCHEDULING_PASSES = {"PadDelay", "PadDynamicalDecoupling", "ConstrainedReschedule", "InstructionDurationCheck",
                     "SetIOLatency", "ContextAwareDynamicalDecoupling", "AlignMeasures", "ValidatePulseGates"}


_LOW = {}


def lowered(u):
    from qiskit import transpile
    key = id(u)
    if key in _LOW:
        return _LOW[key]
    qc = _bound(u.circuit, u.bind)
    _LOW[key] = transpile(qc, basis_gates=u.config.get("basis_gates"), coupling_map=u.config.get("coupling_map"),
                          optimization_level=0, seed_transpiler=1234)
    return _LOW[key]


def high_level_ops(qc):
    from qiskit.transpiler.passes.synthesis.plugin import high_level_synthesis_plugin_names
    from qiskit.circuit.library import get_standard_gate_name_mapping
    std = set(get_standard_gate_name_mapping())
    out = {}
    for inst in qc.data:
        op = inst.operation
        if op.name in std:
            continue
        try:
            names = high_level_synthesis_plugin_names(op.name)
        except Exception:
            names = []
        if len(names) > 0:
            out[op.name] = list(names)
    return out


def enumerate_items(uids):
    out = []
    passes = [p for p in public_passes() if p not in SKIP_PASSES]
    for uid in uids:
        u = _unit(uid)
        n = u.circuit.num_qubits
        for p in passes:
            out.append(f"PX|{uid}|{p}|raw")
            if physical_pass(p):
                out.append(f"PX|{uid}|{p}|low")
        for op, plugins in high_level_ops(u.circuit).items():
            for pl in plugins:
                out.append(f"HX|{uid}|{op}|{pl}")
        for v in TX_VARIANTS:
            out.append(f"TX|{uid}|{v}")
    for a, b in zip(uids, uids[1:] + uids[:1]):
        out.append(f"RX|{a}|{b}")
    return out


def run_item(spec):
    """Returns (kind, input circuit (bound), output circuit (bound), bind)."""
    from qiskit import transpile
    from qiskit.transpiler import PassManager, generate_preset_pass_manager
    parts = spec.split("|")
    t = parts[0]
    u = _unit(parts[1])
    n = u.circuit.num_qubits
    if t == "PX":
        name, kind = parts[2], parts[3]
        qc = u.circuit if kind == "raw" else lowered(u)
        pm = PassManager(preamble(name, u.config, n, kind) + [make_pass(name, u.config, n, scheduled=kind == "low")])
        out = pm.run(qc.copy())
        return "pass", _bound(qc, u.bind), _bound(out, u.bind)
    if t == "HX":
        from qiskit.transpiler.passes import HighLevelSynthesis
        from qiskit.transpiler.passes.synthesis import HLSConfig
        op, pl = parts[2], parts[3]
        hls = HighLevelSynthesis(hls_config=HLSConfig(**{op: [pl]}))
        out = PassManager([hls]).run(u.circuit.copy())
        return "pass", _bound(u.circuit, u.bind), _bound(out, u.bind)
    if t == "TX":
        v = parts[2]
        cfg = dict(u.config)
        lvl, seed = cfg.get("optimization_level", 1), cfg.get("seed_transpiler", 1234)
        qc = _bound(u.circuit, u.bind)
        kw = dict(optimization_level=lvl, seed_transpiler=seed)
        if v == "target_nocm":
            kw["target"] = _target(cfg, n, coupling=False)
        elif v in ("target_durations_alap", "target_durations_asap"):
            kw["target"] = _target(cfg, n, durations=True)
            kw["scheduling_method"] = v.rsplit("_", 1)[1]
        elif v == "target_errors":
            kw["target"] = _target(cfg, n, errors=True)
        elif v == "disjoint":
            from qiskit.transpiler import CouplingMap
            cm = CouplingMap.from_line(n + 1)
            cm2 = CouplingMap(list(cm.get_edges()) + [(a + n + 1, b + n + 1) for a, b in cm.get_edges()])
            kw.update(basis_gates=cfg.get("basis_gates"), coupling_map=cm2)
        else:
            kw.update(basis_gates=cfg.get("basis_gates"), coupling_map=cfg.get("coupling_map"))
            if v == "layout_dense":
                kw["layout_method"] = "dense"
            elif v == "layout_trivial":
                kw["layout_method"] = "trivial"
            elif v == "routing_basic":
                kw["routing_method"] = "basic"
            elif v == "routing_lookahead":
                kw["routing_method"] = "lookahead"
            elif v == "translation_synthesis":
                kw["translation_method"] = "synthesis"
            elif v == "approx_09":
                kw["approximation_degree"] = 0.9
        out = generate_preset_pass_manager(**kw).run(qc)
        return "e2e_" + v, qc, out
    if t == "RX":
        b = _unit(parts[2])
        pm = generate_preset_pass_manager(**b.config)
        try:
            pm.run(_bound(u.circuit, u.bind))
        except Exception:
            pass
        qc = _bound(b.circuit, b.bind)
        return "e2e", qc, pm.run(qc)
    raise ValueError(spec)
