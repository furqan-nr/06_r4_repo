#!/usr/bin/env python3
"""Registered analysis of R4 (draft until frozen). Decides claims A4 to F4 from the session outputs.

Inputs, per base (1.4.6, 2.3.1, 2.6.1): the calibration session directory (clean cost ESTIMATE, used to cut the
suites and to budget the strategies) and the labeling session directory (events, and the clean costs measured in
that session, which are the REAL costs charged).

Pools: F = C24 (base 1.4.6) + A231 (base 2.3.1), primary. B = pool B (base 2.6.1), secondary.

Detection. A suite detects a fault when any of its items detects it under rule L1 (any check), or when the
determinism lane detects it on one of the suite's end-to-end items.

Claims (sign tests are one-sided exact tests on discordant faults; fewer than 5 discordant faults cannot reach
p < 0.05 and the claim is then inconclusive and not supported):
  A4  S5 detects more faults than S0 on pool F: p < 0.05.             Reported: the same on F and B pooled.
  B4  On F and B pooled, S5 detects at least as many faults as S1 and as many as S2.
  C4  On F and B pooled, S5 detects more faults than S3: p < 0.05.
  D4  On F and B pooled, S5 with all checks detects more faults than S5 with output and quality checks only
      (the checks of the output-only strategy).
  E4  At 5% of S5's estimated full cost, OA detects at least as many of S5's detectable faults (F and B pooled) as
      each of OO, AC, AC-cost and CH. With fewer than 5 detectable faults: inconclusive, not supported.
  F4  OA's real spend over budget has mean <= 1.25 and maximum <= 2.0 over all faults, at 2%, 5% and 10%.

    python -m reveal.analyze --items items.json --sessions sessions.json --out results/
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# Budgets at which the strategies run: the ones the claims use (E4: 5%; F4: 2%, 5%, 10%). The frozen strategies
# re-sort the whole item pool on every pick, which at R4's scale (about 35,000 selection items) makes R3's
# ten-budget grid take hours, so the grid is limited to these three.
GRID = (0.02, 0.05, 0.10)
CHECK_MAP = {"output": "output", "quality": "quality", "probe": "probe", "contract": "contract",
             "pass_contract": "contract"}


# ------------------------------------------------------------------------------------------------ loading
def load_cal(d: Path) -> tuple[dict, dict]:
    cal = {}
    for p in (d / "items").glob("*.json"):
        r = json.loads(p.read_text())
        cal[r["item"]] = r
    return cal, json.loads((d / "determinism_lane.json").read_text())


def load_events(d: Path) -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted((d / "events").glob("*.json"))}


# ------------------------------------------------------------------------------------------------ detection
def item_detects(ev: dict, it: str, checks=None) -> bool:
    r = ev["per_item"].get(it)
    if r is None:
        return False
    return any(v for k, v in r["detects"].items() if checks is None or k in checks)


def lane_detects(ev: dict, it: str) -> bool:
    return bool(ev["determinism"]["per_unit"].get(it, {}).get("detects"))


def suite_detects(ev: dict, items: list[str], *, checks=None, lane=True) -> bool:
    return any(item_detects(ev, it, checks) or (lane and it.startswith("U:") and lane_detects(ev, it)) for it in items)


def sign_test(a: list[bool], b: list[bool]) -> dict:
    """One-sided exact sign test that `a` detects more than `b` (paired by fault)."""
    up = sum(x and not y for x, y in zip(a, b))
    down = sum(y and not x for x, y in zip(a, b))
    n = up + down
    p = sum(math.comb(n, k) for k in range(up, n + 1)) / 2 ** n if n else 1.0
    return dict(a_only=up, b_only=down, discordant=n, p=p, decisive=n >= 5)


# ------------------------------------------------------------------------------------------------ selection
def meta_of(it: str, unit_meta: dict) -> tuple[str, str]:
    parts = it.split(":")
    uid = it[2:] if parts[0] == "U" else ":".join(parts[1:-2])
    return unit_meta.get(uid, "other"), ("e2e" if parts[0] == "U" else parts[-2])


def cost_table(items: list[str], cal: dict, lane: dict, unit_meta: dict, *, event: dict | None = None):
    """Frozen obsaware.selection structures for R4 items. With an event, check costs are that event's charged
    costs (real); without, the calibration's (estimate)."""
    from obsaware.selection import CostTable, Unit
    units, compile_s, check_s, appl = [], {}, {}, {}
    for it in items:
        c = cal.get(it)
        if not c or not c.get("usable"):
            continue
        fam, backend = meta_of(it, unit_meta)
        units.append(Unit(it, fam, backend, 0, 0, "na"))
        compile_s[it] = c["compile_s"]
        ks = []
        charged = (event or {}).get("per_item", {}).get(it, {}).get("cost", {})
        for k, v in c["checks"].items():
            if v["clean_pass"]:
                kk = CHECK_MAP[k]
                check_s[(it, kk)] = float(charged.get(k, v["cost"]))
                ks.append(kk)
        if it.startswith("U:") and lane["per_unit"].get(it, {}).get("deterministic"):
            check_s[(it, "determinism")] = sum(lane["per_unit"][it]["compile_s"])
            ks.append("determinism")
        appl[it] = tuple(ks)
    return units, CostTable(compile_s, check_s, sum(lane["fixed_cpu_per_launch_s"]), appl)


def strategies():
    import importlib.util
    import os
    from obsaware.selection import STRATEGIES, random_items
    cart = Path(os.environ.get("CART_ROOT", "."))
    spec = importlib.util.spec_from_file_location("strategies_r3", cart / "r3" / "strategies_r3.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    s = dict(m.R3_STRATEGIES)
    s["random_items"] = random_items
    return s


def selection_detects(sel: list[tuple[str, str]], ev: dict) -> bool:
    for it, k in sel:
        if k == "determinism":
            if lane_detects(ev, it):
                return True
        elif any(v for kk, v in ev["per_item"].get(it, {}).get("detects", {}).items() if CHECK_MAP[kk] == k):
            return True
    return False


# ------------------------------------------------------------------------------------------------ main
def main() -> int:
    from obsaware.selection import real_spend
    from reveal.suites import build_suites
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True, help="items.json from reveal.suites")
    ap.add_argument("--sessions", required=True,
                    help='JSON: {"1.4.6": {"cal": dir, "label": dir, "pool": "F"}, "2.3.1": {...}, "2.6.1": {..., "pool": "B"}}')
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(a.items).read_text())
    sessions = json.loads(Path(a.sessions).read_text())
    from reveal import units as U
    unit_meta = {}
    for uid in spec["unit_ids"]["F"]:
        r = U._corpus_index()[uid]["values"]
        unit_meta[uid] = f"{r['gate_group']}/{r['block']}"
    for uid in spec["unit_ids"]["R3"]:
        unit_meta[uid] = "R3/" + uid.split(":")[1].split("-")[0]
    for src in ("S1", "S2"):
        for uid in spec["unit_ids"][src]:
            unit_meta[uid] = src
    passes = {it for it in spec["items"] if it.startswith("P:")}
    strat = strategies()

    rows = []       # one row per fault
    for base, s in sessions.items():
        est_cal, est_lane = load_cal(Path(s["cal"]))
        real_cal, real_lane = load_cal(Path(s["label"]))
        suites = {f: build_suites(spec["unit_ids"], passes, est_cal, est_lane, factor=f) for f in (1.0, 3.0)}
        s5_full = suites[3.0]["S5"]          # S5 strategies select within the 3x suite (reported) ...
        s5 = suites[1.0]["S5"]               # ... and within the registered 1x suite
        units_est, ct_est = cost_table(s5, est_cal, est_lane, unit_meta)
        budget_full = ct_est.total()
        sels = {(name, b): fn(units_est, ct_est, b * budget_full) for name, fn in strat.items() for b in GRID}
        for name, ev in load_events(Path(s["label"])).items():
            row = dict(fault=name, base=base, pool=s["pool"])
            for f, ss in suites.items():
                for sn, its in ss.items():
                    row[f"{sn}@{f:g}x"] = suite_detects(ev, its)
            row["S5_oq@1x"] = suite_detects(ev, s5, checks={"output", "quality"}, lane=False)
            _, ct_real = cost_table(s5, real_cal, real_lane, unit_meta, event=ev)
            for (sname, b), sel in sels.items():
                row[f"sel:{sname}@{b}"] = selection_detects(sel, ev)
                row[f"spend:{sname}@{b}"] = real_spend(sel, ct_real) / (b * budget_full)
            rows.append(row)
    (out / "per_fault.json").write_text(json.dumps(rows, indent=1))

    F = [r for r in rows if r["pool"] == "F"]
    ALL = rows
    col = lambda rs, k: [bool(r[k]) for r in rs]
    res = {}
    a4 = sign_test(col(F, "S5@1x"), col(F, "S0@1x"))
    res["A4"] = dict(test=a4, supported=a4["decisive"] and a4["p"] < 0.05,
                     pooled=sign_test(col(ALL, "S5@1x"), col(ALL, "S0@1x")))
    n = lambda rs, k: sum(col(rs, k))
    res["B4"] = dict(S5=n(ALL, "S5@1x"), S1=n(ALL, "S1@1x"), S2=n(ALL, "S2@1x"),
                     supported=n(ALL, "S5@1x") >= n(ALL, "S1@1x") and n(ALL, "S5@1x") >= n(ALL, "S2@1x"))
    c4 = sign_test(col(ALL, "S5@1x"), col(ALL, "S3@1x"))
    res["C4"] = dict(test=c4, supported=c4["decisive"] and c4["p"] < 0.05)
    res["D4"] = dict(all_checks=n(ALL, "S5@1x"), output_quality=n(ALL, "S5_oq@1x"),
                     supported=n(ALL, "S5@1x") > n(ALL, "S5_oq@1x"))
    det = [r for r in ALL if r["S5@3x"] or r["S5@1x"]]
    e = {k: n(det, f"sel:{k}@0.05") for k in ("observability", "output_only", "all_checks", "ac_costaware",
                                              "cheapest_items")}
    res["E4"] = dict(detectable=len(det), detected_at_5pct=e,
                     supported=len(det) >= 5 and all(e["observability"] >= v for v in e.values()))
    f4 = {}
    for b in (0.02, 0.05, 0.10):
        xs = [r[f"spend:observability@{b}"] for r in ALL]
        f4[str(b)] = dict(mean=sum(xs) / len(xs) if xs else None, max=max(xs) if xs else None)
    res["F4"] = dict(per_budget=f4, supported=bool(ALL) and all(v["mean"] <= 1.25 and v["max"] <= 2.0
                                                                for v in f4.values()))
    res["reported"] = {k: {s: n(rs, f"{s}@{f}") for s in ("S0", "S1", "S2", "S3", "S4", "S5") for f in ("1x", "3x")}
                       for k, rs in (("F", F), ("B", [r for r in ALL if r["pool"] == "B"]), ("all", ALL))}
    (out / "registered_analysis_r4.json").write_text(json.dumps(res, indent=1))
    for k in ("A4", "B4", "C4", "D4", "E4", "F4"):
        print(k, "SUPPORTED" if res[k]["supported"] else "NOT SUPPORTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
