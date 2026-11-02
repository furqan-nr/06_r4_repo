"""Post hoc analyses of R4 (not registered). Reuses the frozen analysis code by import.

P1  Lane audit: a determinism-lane alarm is discounted when the unit is non-deterministic on the CLEAN build in
    extra clean lane runs (lane_flaky.json).
P2  Item audit: a 'changed' item is discounted when the clean build itself leaves the session's 5-run clean set in
    20 extra clean interpreters (flaky_<session>.json).
P3  Change level: a suite 'exposes' a fault when one of its items has an output outside the clean set (after P2),
    whether or not a check alarms. This is the golden-output regression oracle.
P4  Costs: per suite, item count and estimated cost by component (compile, output, quality, probe, contract).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import os

import reveal.analyze as A
from reveal.suites import build_suites

# OUT: session outputs (one folder per session; R4-C1 with the three superseded records moved out), REPO: this
# repository. Usage: OUT=... REPO=... python tools/analysis/posthoc_r4.py
OUT, REPO = Path(os.environ["OUT"]), Path(os.environ["REPO"])
SESS = json.loads((REPO / "results/sessions.json").read_text())
for s in SESS.values():
    s["cal"], s["label"] = str(OUT / s["cal"]), str(OUT / s["label"].split(" ")[0])
SPEC = json.loads((REPO / "data/items.json").read_text())
LANE_FLAKY = json.loads((REPO / "results/posthoc/lane_flaky.json").read_text())   # {base: [units]}
FLAKY = {}
for k, s in SESS.items():
    p = REPO / f"results/posthoc/clean_rerun_{Path(s['label']).name}.json"
    # flaky: the clean build left its own clean set in some but not all of the 20 reruns. 20 of 20 means the
    # fingerprint differs between the rerun machine and Kaggle (each such item changed under one fault only).
    FLAKY[k] = {it for it, n in json.loads(p.read_text()).items() if 0 < n < 20} if p.exists() else set()
# an item flaky on the clean build in any session of a base is flaky on that base
for k in list(FLAKY):
    FLAKY[k] = set().union(*(FLAKY[j] for j in FLAKY if j.split("/")[0] == k.split("/")[0]))

passes = {it for it in SPEC["items"] if it.startswith("P:")}
rows, costs = [], {}
for key, s in SESS.items():
    base = key.split("/")[0]
    est_cal, est_lane = A.load_cal(Path(s["cal"]))
    suites = {f: build_suites(SPEC["unit_ids"], passes, est_cal, est_lane, factor=f) for f in (1.0, 3.0)}
    if base not in costs:
        costs[base] = {}
        for sn, its in suites[1.0].items():
            c = Counter()
            for it in its:
                r = est_cal.get(it, {})
                if not r.get("usable"):
                    continue
                c["compile"] += r["compile_s"]
                for ck, v in r["checks"].items():
                    c[ck] += v["cost"]
            costs[base][sn] = dict(items=len(its), units=len({it.split(":")[1] if it.startswith("P:") else it[2:]
                                                              for it in its}),
                                   **{k: round(v, 1) for k, v in c.items()}, total=round(sum(c.values()), 1))
    for name, ev in A.load_events(Path(s["label"])).items():
        row = dict(fault=name, base=key, pool=s["pool"])
        clean_ev = json.loads(json.dumps(ev))
        for u in LANE_FLAKY.get(base, []):
            if u in clean_ev["determinism"]["per_unit"]:
                clean_ev["determinism"]["per_unit"][u]["detects"] = False
        for f, ss in suites.items():
            for sn, its in ss.items():
                row[f"reg:{sn}@{f:g}x"] = A.suite_detects(ev, its)
                row[f"aud:{sn}@{f:g}x"] = A.suite_detects(clean_ev, its)
                row[f"aud_oq:{sn}@{f:g}x"] = A.suite_detects(clean_ev, its, checks={"output", "quality"}, lane=False)
                row[f"chg:{sn}@{f:g}x"] = any(ev["per_item"][it]["status"] in ("changed", "crash")
                                              and it not in FLAKY[key] for it in its if it in ev["per_item"])
        row["changed_items"] = sorted(it for it, r in ev["per_item"].items()
                                      if r["status"] in ("changed", "crash") and it not in FLAKY[key])
        rows.append(row)

out = REPO / "results/posthoc"
out.mkdir(exist_ok=True)
(out / "posthoc_per_fault.json").write_text(json.dumps(rows, indent=1))
(out / "suite_costs.json").write_text(json.dumps(costs, indent=1))
tab = defaultdict(dict)
for lvl in ("reg", "aud", "aud_oq", "chg"):
    for sn in ("S0", "S1", "S2", "S3", "S4", "S5"):
        for f in ("1x", "3x"):
            for pool, rs in (("F", [r for r in rows if r["pool"] == "F"]), ("B", [r for r in rows if r["pool"] == "B"]),
                             ("all", rows)):
                tab[f"{lvl}@{f}"][f"{sn}/{pool}"] = sum(r[f"{lvl}:{sn}@{f}"] for r in rs)
(out / "posthoc_tables.json").write_text(json.dumps(tab, indent=1))
for k, v in tab.items():
    print(k, {s: v[f"{s}/all"] for s in ("S0", "S1", "S2", "S3", "S4", "S5")},
          "| F:", {s: v[f"{s}/F"] for s in ("S0", "S5")})
F = [r for r in rows if r["pool"] == "F"]
tests = {}
for lvl in ("reg", "aud", "chg"):
    for pool, rs in (("F", F), ("all", rows)):
        t = A.sign_test([r[f"{lvl}:S5@1x"] for r in rs], [r[f"{lvl}:S0@1x"] for r in rs])
        t1 = A.sign_test([r[f"{lvl}:S5@1x"] for r in rs], [r[f"{lvl}:S1@1x"] for r in rs])
        print(lvl, pool, "S5 vs S0", t, "| S5 vs S1", t1)
        tests[f"{lvl}/{pool}"] = {"S5 vs S0": t, "S5 vs S1": t1}
(out / "posthoc_sign_tests.json").write_text(json.dumps(tests, indent=1))
print(json.dumps(costs, indent=1))
