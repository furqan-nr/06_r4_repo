#!/usr/bin/env python3
"""Registered analysis of R5. Decides claims A5 to D5 from the session outputs.

Per base (one or more session directories, each with clean.json, screen.json and events/):
  excluded items: items with more than one clean result, items the clean screen marks flaky, and every item that
                  differs under the null control in a session of that base.
  exposed:   a suite exposes an event when one of its non-excluded items differs from its clean result set, crashes
             or hangs.
  detected:  a suite detects an event when one of its non-excluded items crashes or hangs where clean succeeded, or
             its output check or quality check alarms (rule L1).
Suites: S0 (R3 corpus, preset compilation), S5 (proposed), S1' (random_circuit units with S5's catalogue, cut in
the frozen unit order at S5's measured clean cost on that base).

Claims (pooled over all held-out faults; one-sided exact sign tests on discordant faults; fewer than 5 discordant
faults cannot reach p < 0.05 and the claim is then not supported):
  A5  S5 detects more faults than S0, p < 0.05.                                         (primary)
  B5  S5 detects more faults than S1', p < 0.05.
  C5  S5 exposes more faults than S0, p < 0.05.
  D5  S5 exposes more faults than S1', p < 0.05.
  B5 and D5 are inconclusive (not supported) on the pooled data if S1' reaches less than 90% of S5's clean cost on
  any base.
Reported without decision: per base and pooled counts, the benign events (false alarms of each level), the
contributions of item families inside S5, and the cost of every suite.

    python -m r5.analyze5 --sessions sessions.json --out results/
sessions.json: {"<base>": ["<session dir>", ...], ...}
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FAMILIES = {"TX_default": lambda it: it.startswith("TX|") and it.endswith("|default"),
            "TX_variants": lambda it: it.startswith("TX|") and not it.endswith("|default"),
            "PX_raw": lambda it: it.startswith("PX|") and it.endswith("|raw"),
            "PX_low": lambda it: it.startswith("PX|") and it.endswith("|low"),
            "HX": lambda it: it.startswith("HX|"),
            "RX": lambda it: it.startswith("RX|")}


def sign_test(a: list[bool], b: list[bool]) -> dict:
    ao = sum(1 for x, y in zip(a, b) if x and not y)
    bo = sum(1 for x, y in zip(a, b) if y and not x)
    n = ao + bo
    p = sum(math.comb(n, k) for k in range(ao, n + 1)) / 2 ** n if n else 1.0
    return dict(a_only=ao, b_only=bo, discordant=n, p=p, decisive=n >= 5)


def unit_of(it: str) -> str:
    return it.split("|")[1]


def load_base(dirs: list[Path]):
    clean, screen, events, suites = {}, {}, {}, None
    for d in dirs:
        c = json.loads((d / "clean.json").read_text())
        for it, v in c.items():
            clean.setdefault(it, v)
        if (d / "screen.json").exists():
            for it, v in json.loads((d / "screen.json").read_text()).items():
                screen[it] = max(screen.get(it, 0), v)
        for p in (d / "events").glob("*.json"):
            e = json.loads(p.read_text())
            events.setdefault(e["event"], []).append(e["per_item"])
        suites = suites or json.loads((d / "items.json").read_text())
    return clean, screen, events, suites


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = json.loads(Path(a.sessions).read_text())
    rows, costs = [], {}
    for base, dirs in sessions.items():
        clean, screen, events, S = load_base([Path(d) for d in dirs])
        null = set()
        for per in events.get("NULL", []):
            null |= set(per)
        excluded = {it for it, v in clean.items() if len(v["fps"]) > 1} | {it for it, v in screen.items() if v} | null
        ok = {it for it, v in clean.items() if not v["fail"]} - excluded
        cost = lambda its: sum(clean[it]["cost"] or 0.0 for it in its if it in clean and not clean[it]["fail"])
        s5 = [it for it in S["S5"] if it in ok]
        s5_cost = cost(S["S5"])
        # S1': whole units in the frozen order until S5's clean cost is reached
        by_unit, order = {}, []
        for it in S["S1"]:
            u = unit_of(it)
            if u not in by_unit:
                by_unit[u] = []
                order.append(u)
            by_unit[u].append(it)
        s1, c1 = [], 0.0
        for u in order:
            if c1 >= s5_cost:
                break
            s1 += by_unit[u]
            c1 += cost(by_unit[u])
        suites = {"S0": [it for it in S["S0"] if it in ok], "S5": s5, "S1p": [it for it in s1 if it in ok]}
        for fam, f in FAMILIES.items():
            suites[f"S5:{fam}"] = [it for it in s5 if f(it)]
        suites["S5:F_units"] = [it for it in s5 if unit_of(it).startswith("F")]
        suites["S5:G_units"] = [it for it in s5 if unit_of(it).startswith("G")]
        costs[base] = dict(S0=cost(S["S0"]), S5=s5_cost, S1p=c1, S1p_ratio=c1 / s5_cost if s5_cost else None,
                           excluded=len(excluded), clean_ok=len(ok))
        for ev, pers in events.items():
            if ev == "NULL":
                continue
            per = {}
            for p in pers:
                per.update(p)
            row = dict(event=ev, base=base, kind="benign" if ev.startswith("N") else "fault")
            for name, its in suites.items():
                hit = [it for it in its if it in per]
                row[f"exp:{name}"] = bool(hit)
                row[f"det:{name}"] = any(per[it]["status"] in ("crash", "hang") or per[it].get("output")
                                         or per[it].get("quality") for it in hit)
                row[f"items:{name}"] = len(hit)
            rows.append(row)
    (out / "per_event.json").write_text(json.dumps(rows, indent=1))
    F = [r for r in rows if r["kind"] == "fault"]
    col = lambda k: [bool(r[k]) for r in F]
    cost_ok = all((v["S1p_ratio"] or 0) >= 0.9 for v in costs.values())
    res = {}
    for name, lvl, other in (("A5", "det", "S0"), ("B5", "det", "S1p"), ("C5", "exp", "S0"), ("D5", "exp", "S1p")):
        t = sign_test(col(f"{lvl}:S5"), col(f"{lvl}:{other}"))
        sup = t["decisive"] and t["p"] < 0.05 and (other != "S1p" or cost_ok)
        res[name] = dict(test=t, supported=sup, S5=sum(col(f"{lvl}:S5")), other=sum(col(f"{lvl}:{other}")))
    res["S1p_cost_ok"] = cost_ok
    names = sorted({k.split(":", 1)[1] for k in rows[0] if k.startswith("det:")}) if rows else []
    res["reported"] = {kind: {lvl: {n: sum(r[f"{lvl}:{n}"] for r in rows if r["kind"] == kind) for n in names}
                              for lvl in ("det", "exp")} for kind in ("fault", "benign")}
    res["n_faults"], res["n_benign"] = len(F), len(rows) - len(F)
    res["costs"] = costs
    (out / "registered_analysis_r5.json").write_text(json.dumps(res, indent=1))
    for k in ("A5", "B5", "C5", "D5"):
        print(k, "SUPPORTED" if res[k]["supported"] else "NOT SUPPORTED", res[k]["test"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
