"""R5 benign-change events (fault-blind: prints counts only). Per base, commits merged before the base's release
that (1) have NO release note, (2) do not match fix|bug|incorrect|wrong in the subject, (3) change only Python files
under the compilation folders of selection/mine_pools.py, and (4) revert cleanly on the base. Two are drawn per
base with a fixed seed. Reverting such a commit is a code change that the project did not mark as a bug fix, so an
alarm on it is counted as a false alarm (the rule cannot exclude every behaviour change; that is reported)."""
import json, random, re, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/claude/repo/selection")
import mine_pools as M
OUT = Path("/home/claude/r5pools")
SEED = 20261104
WIN = {"1.1.2": "1.0.0..1.1.2", "1.2.4": "1.1.0..1.2.4", "1.3.3": "1.2.0..1.3.3", "1.4.6": "1.3.0..1.4.6",
       "2.0.3": "1.4.0..2.0.3", "2.1.2": "2.0.0..2.1.2", "2.2.3": "2.1.0..2.2.3", "2.4.2": "2.3.0..2.4.2",
       "2.5.2": "2.4.0..2.5.2"}
res = {}
(OUT / "benign_patches").mkdir(exist_ok=True)
for base, rng in WIN.items():
    log = M.sh("git", "log", "--format=@@%h|%s", "--name-only", "--no-merges", rng, cwd="/home/claude/qiskit").stdout
    cands = []
    for blk in log.split("@@")[1:]:
        lines = blk.strip().split("\n")
        h, s = lines[0].split("|", 1)
        f = [x for x in lines[1:] if x]
        if any(x.startswith("releasenotes/") for x in f) or re.search(r"fix|bug|incorrect|wrong", s, re.I):
            continue
        code = [x for x in f if x.startswith(("qiskit/", "crates/"))]
        if not code or not all(x.endswith(".py") and x.startswith(M.COMPILATION) for x in code):
            continue
        cands.append(h)
    rnd = random.Random(f"{SEED}:{base}")
    rnd.shuffle(cands)
    picked = []
    for h in cands:
        diff = M.sh("git", "diff", f"{h}^", h, "--", "qiskit/", cwd="/home/claude/qiskit").stdout
        p = OUT / "benign_patches" / f"{base}_{h}.diff"
        p.write_text(diff)
        if diff and M.revertible(str(p), f"/home/claude/tree_{base}"):
            files = [l[6:] for l in diff.splitlines() if l.startswith("+++ b/")]
            picked.append(dict(id=f"N{h}", commit=h, rust=False, files=files, patch=str(p)))
        else:
            p.unlink()
        if len(picked) == 2:
            break
    res[base] = picked
    (OUT / f"benign_{base}.json").write_text(json.dumps(dict(pool=f"benign_{base}", faults=picked), indent=1))
print({b: len(v) for b, v in res.items()})
