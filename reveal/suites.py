"""Suites S0 to S5 as ordered item lists, cut to a common cost budget with calibrated clean costs.

  S0  R3 corpus, end to end                       (anchor, all 116 units, never cut)
  S1  Qiskit random_circuit units, end to end     (pool order)
  S2  randomized-test grammar units, end to end   (pool order)
  S3  feature corpus, end to end                  (replicate order: whole replicate 0 first, then 1, ...)
  S4  S1 units, each followed by its pass-level items
  S5  feature units, each followed by its pass-level items   (the proposed suite)

Cost of an item = its compile (or pass) cost + every check that passed on the clean build. A suite that contains
end-to-end items also pays the determinism lane: the fixed cost per launch times the number of launches, plus each
end-to-end unit's lane compilations. A suite is cut by walking its order and keeping each item that still fits
(the walk does not stop at the first item that does not fit, as in obsaware.selection._take).

The common budget is S5's full estimated cost on the same base (registered: the 1x level), and 3 times that
(reported). S5 and S0 are never cut. S0 costs far more than S5 (about 1,420 s against about 150 s), which works
against S5 in claim A4.
"""
from __future__ import annotations

import json
from pathlib import Path

from reveal.passlevel import CATALOGUE

SOURCES = {"S0": "R3", "S1": "S1", "S2": "S2", "S3": "F", "S4": "S1", "S5": "F"}
WITH_PASS = {"S4", "S5"}


def ordered_items(suite: str, unit_ids: list[str], pass_items: set[str]) -> list[str]:
    out = []
    for uid in unit_ids:
        out.append(f"U:{uid}")
        if suite in WITH_PASS:
            for name in CATALOGUE:
                for kind in ("raw", "snap"):
                    it = f"P:{uid}:{name}:{kind}"
                    if it in pass_items:
                        out.append(it)
    return out


def item_cost(cal: dict, lane: dict, it: str) -> float:
    c = cal.get(it)
    if not c or not c.get("usable"):
        return 0.0
    cost = c["compile_s"] + sum(v["cost"] for v in c["checks"].values() if v["clean_pass"])
    if it.startswith("U:") and it in lane["per_unit"]:
        cost += sum(lane["per_unit"][it]["compile_s"])
    return cost


def lane_fixed(lane: dict) -> float:
    return sum(lane["fixed_cpu_per_launch_s"])


def cut(order: list[str], cal: dict, lane: dict, budget: float) -> list[str]:
    spent, out, lane_open = 0.0, [], False
    for it in order:
        c = item_cost(cal, lane, it)
        if c == 0.0:
            continue
        extra = lane_fixed(lane) if (it.startswith("U:") and not lane_open) else 0.0
        if spent + c + extra <= budget + 1e-12:
            spent += c + extra
            lane_open = lane_open or it.startswith("U:")
            out.append(it)
    return out


def full_cost(order: list[str], cal: dict, lane: dict) -> float:
    c = sum(item_cost(cal, lane, it) for it in order)
    return c + (lane_fixed(lane) if any(it.startswith("U:") for it in order) else 0.0)


def build_suites(unit_ids: dict[str, list[str]], pass_items: set[str], cal: dict, lane: dict,
                 factor: float = 1.0) -> dict[str, list[str]]:
    """unit_ids: source -> ordered unit ids (R3, S1, S2, F). Returns suite -> item list. S1 to S4 are cut to
    `factor` x S5's full estimated cost (registered: 1x; reported: 3x). S5 and S0 are never cut."""
    orders = {s: ordered_items(s, unit_ids[src], pass_items) for s, src in SOURCES.items()}
    budget = factor * full_cost(orders["S5"], cal, lane)
    out = {"S0": orders["S0"], "S5": orders["S5"]}      # S0 and S5 are never cut
    for s in ("S1", "S2", "S3", "S4"):
        out[s] = cut(orders[s], cal, lane, budget)
    return out


def all_items(unit_ids: dict[str, list[str]], pass_items: set[str]) -> list[str]:
    """Every item any suite may use (the calibration and labeling sessions run all of them)."""
    seen, out = set(), []
    for s, src in SOURCES.items():
        for it in ordered_items(s, unit_ids[src], pass_items):
            if it not in seen:
                seen.add(it)
                out.append(it)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="write the item list of all suites for the sessions")
    ap.add_argument("--valid-items", required=True, help="reveal.validity select output (S1, S2 units and pass items)")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pool", type=int, default=2500, help="valid S1 and S2 units kept, in pool order")
    a = ap.parse_args()
    from reveal import units as U
    valid = set(json.loads(Path(a.valid_items).read_text())["items"])
    ids = {"R3": U.all_ids("R3"), "F": [e["unit"] for e in json.loads(Path(a.corpus).read_text())["units"]],
           "S1": [u for u in U.all_ids("S1") if u in valid][:a.pool],
           "S2": [u for u in U.all_ids("S2") if u in valid][:a.pool]}
    passes = {k for k in valid if k.startswith("P:")}
    items = all_items(ids, passes)
    Path(a.out).write_text(json.dumps({"unit_ids": ids, "items": items}, indent=1))
    print(len(items), "items;", {k: len(v) for k, v in ids.items()})
