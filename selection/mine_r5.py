"""R5 fresh fault pools (fault-blind: prints counts only). R3/R4 rule steps 1 to 4 via selection/mine_pools.py;
excludes every R3, R4 and contacted fault. Each candidate goes to the newest listed release on which its patch
reverts cleanly. Pools are written with patches outside the repository."""
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, "/home/claude/repo/selection")
import mine_pools as M
OUT = Path("/home/claude/r5pools")
pools = json.load(open("/home/claude/repo/selection/pools.json"))["pools"]
used = {c["id"] for v in pools.values() for c in v} | M.CONTACTED | M.R3_FAULTS
T = lambda t: f"/home/claude/tree_{t}"
LATE = ("2.5.2", "2.4.2", "2.2.3", "2.1.2", "2.0.3")
MID = ("1.4.6", "1.3.3", "1.2.4", "1.1.2")
res = {b: [] for b in LATE + MID}
(OUT / "patches").mkdir(exist_ok=True)
import tempfile
with tempfile.TemporaryDirectory() as tmp:
    for rng, bases in ((f"2.0.0..{M.R3_HEAD}", LATE), ("1.0.0..2.0.0", MID)):
        for c in M.mine("/home/claude/qiskit", rng, tmp):
            if c["id"] in used or not M.compilation_related(c["files"]):
                continue
            for b in bases:
                if M.revertible(c["patch"], T(b)):
                    p = OUT / "patches" / f"{c['id']}.diff"
                    shutil.copy(c["patch"], p)
                    res[b].append(dict(id=c["id"], commit=c["commit"], date=c["date"], rust=c["rust"],
                                       files=c["files"], patch=str(p)))
                    break
for b, lst in res.items():
    (OUT / f"faults_{b}.json").write_text(json.dumps(dict(pool=f"R5_{b}", faults=lst), indent=1))
print({b: len(v) for b, v in res.items()}, "rust:", {b: sum(c["rust"] for c in v) for b, v in res.items()})
