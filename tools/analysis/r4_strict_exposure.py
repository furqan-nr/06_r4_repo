#!/usr/bin/env python3
"""Post hoc sensitivity (errata E14): R4 exposure when every item that left its clean set in ANY of the 20 clean
reruns (1 to 20, not only 1 to 19) is excluded.

    OUT=<R4 session outputs> REPO=. python tools/analysis/r4_strict_exposure.py
"""
import json, os
from pathlib import Path
import reveal.analyze as A
from reveal.suites import build_suites
OUT, REPO = Path(os.environ["OUT"]), Path(os.environ["REPO"])
SESS = json.loads((REPO / "results/sessions.json").read_text())
SPEC = json.loads((REPO / "data/items.json").read_text())
passes = {it for it in SPEC["items"] if it.startswith("P:")}
rows = json.loads((REPO / "results/posthoc/posthoc_per_fault.json").read_text())
ANY = {}
for k, s in SESS.items():
    p = REPO / f"results/posthoc/clean_rerun_{s['label'].split(' ')[0]}.json"
    ANY[k] = {it for it, n in json.loads(p.read_text()).items() if n > 0} if p.exists() else set()
for k in list(ANY):
    ANY[k] = set().union(*(ANY[j] for j in ANY if j.split("/")[0] == k.split("/")[0]))
suites = {}
for k, s in SESS.items():
    est_cal, est_lane = A.load_cal(OUT / s["cal"])
    suites[k] = build_suites(SPEC["unit_ids"], passes, est_cal, est_lane, factor=1.0)
res = []
for r in rows:
    k = r["base"]
    ch = set(r["changed_items"])
    out = dict(fault=r["fault"], base=k, pool=r["pool"])
    for sn, its in suites[k].items():
        its = set(its)
        out[f"chg:{sn}"] = r[f"chg:{sn}@1x"]
        out[f"chg_strict:{sn}"] = bool((ch & its) - ANY[k])
    res.append(out)
names = sorted({k.split(":")[1] for k in res[0] if k.startswith("chg:")})
summ = {n: dict(registered_posthoc=sum(x[f"chg:{n}"] for x in res), strict=sum(x[f"chg_strict:{n}"] for x in res)) for n in names}
dropped = [dict(fault=x["fault"], base=x["base"], suites=[n for n in names if x[f"chg:{n}"] and not x[f"chg_strict:{n}"]]) for x in res if any(x[f"chg:{n}"] and not x[f"chg_strict:{n}"] for n in names)]
json.dump(dict(summary=summ, faults_losing_exposure=dropped, per_fault=res), open(REPO / "results/posthoc/m05_strict_exposure.json", "w"), indent=1)
print(json.dumps(summ, indent=1)); print(dropped)
