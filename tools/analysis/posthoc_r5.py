#!/usr/bin/env python3
"""Post hoc analyses of R5 (not registered). Imports the frozen r5.analyze5 and rebuilds its suites and exclusions.

The suites and exclusions are rebuilt with the same rules as r5/analyze5.py, which does not expose them as a
function. The rebuilt decisions reproduce the registered ones exactly.

1. Detection channel per fault and suite: crash, hang, output check, quality check, and the item families involved.
2. Sentinel sensitivity: the same decisions with every item whose clean fingerprint is an `unfingerprintable:` label
   removed from every suite (errata E1).
3. Fix-test validation joined to the detections (results/r5/posthoc/fix_test_validation.json).

    PYTHONPATH=. python tools/analysis/posthoc_r5.py --sessions sessions.json --validation fix_test_validation.json --out results/r5/posthoc
"""
import argparse
import json
from pathlib import Path

from r5.analyze5 import FAMILIES, load_base, sign_test, unit_of


def suites_for(clean, screen, events, S):
    null = set()
    for per in events.get("NULL", []):
        null |= set(per)
    excluded = {it for it, v in clean.items() if len(v["fps"]) > 1} | {it for it, v in screen.items() if v} | null
    ok = {it for it, v in clean.items() if not v["fail"]} - excluded
    cost = lambda its: sum(clean[it]["cost"] or 0.0 for it in its if it in clean and not clean[it]["fail"])
    s5_cost = cost(S["S5"])
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
    return {"S0": [it for it in S["S0"] if it in ok], "S5": [it for it in S["S5"] if it in ok],
            "S1p": [it for it in s1 if it in ok]}


def family(it):
    return next(f for f, g in FAMILIES.items() if g(it))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", required=True)
    ap.add_argument("--validation", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    val = {(r["base"], r["fault"]): r for r in json.loads(Path(a.validation).read_text())}
    rows, sentinel_counts = [], {}
    for base, dirs in json.loads(Path(a.sessions).read_text()).items():
        clean, screen, events, S = load_base([Path(d) for d in dirs])
        suites = suites_for(clean, screen, events, S)
        sent = {it for it, v in clean.items() if any(str(fp).startswith("unfingerprintable:") for fp in v["fps"])}
        sentinel_counts[base] = {k: sum(it in sent for it in v) for k, v in suites.items()}
        for ev, pers in events.items():
            if ev == "NULL" or ev.startswith("N"):
                continue
            per = {}
            for p in pers:
                per.update(p)
            row = dict(base=base, fault=ev, validation=val.get((base, ev), {}).get("status"),
                       fix_triggers=len(val.get((base, ev), {}).get("triggering", [])))
            for name, its in suites.items():
                for tag, keep in (("", its), ("no_sentinel:", [it for it in its if it not in sent])):
                    hit = [it for it in keep if it in per]
                    ch = dict(crash=[it for it in hit if per[it]["status"] == "crash"],
                              hang=[it for it in hit if per[it]["status"] == "hang"],
                              output=[it for it in hit if per[it].get("output")],
                              quality=[it for it in hit if per[it].get("quality")])
                    det = sorted({it for v in ch.values() for it in v})
                    row[f"{tag}exp:{name}"] = bool(hit)
                    row[f"{tag}det:{name}"] = bool(det)
                    if not tag:
                        row[f"channels:{name}"] = {k: len(v) for k, v in ch.items()}
                        row[f"families:{name}"] = sorted({family(it) for it in det})
                        row[f"example_items:{name}"] = det[:5]
            rows.append(row)
    rows.sort(key=lambda r: (r["base"], r["fault"]))
    (out / "per_fault_channels.json").write_text(json.dumps(rows, indent=1))
    summary = {"sentinel_items_in_suite": sentinel_counts}
    for tag in ("", "no_sentinel:"):
        for lvl in ("det", "exp"):
            for other in ("S0", "S1p"):
                t = sign_test([r[f"{tag}{lvl}:S5"] for r in rows], [r[f"{tag}{lvl}:{other}"] for r in rows])
                summary[f"{tag}{lvl}:S5_vs_{other}"] = dict(S5=sum(r[f"{tag}{lvl}:S5"] for r in rows),
                                                            other=sum(r[f"{tag}{lvl}:{other}"] for r in rows), **t)
    act = [r for r in rows if r["validation"] == "active"]
    summary["validation_counts"] = {s: sum(r["validation"] == s for r in rows) for s in sorted({r["validation"] for r in rows if r["validation"]})}
    summary["on_active_faults"] = {f"{lvl}:{n}": sum(r[f"{lvl}:{n}"] for r in act) for lvl in ("det", "exp") for n in ("S0", "S5", "S1p")}
    summary["on_active_faults"]["n"] = len(act)
    (out / "posthoc_summary_r5.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
