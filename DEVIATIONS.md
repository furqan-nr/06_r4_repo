# Deviations from registration R4

Each deviation is listed with its reason, when it was decided, and what was known at that moment.

## D1. Session R4-C1: benchmark drift above 15%; three faults rerun in session R4-C1b

**What happened.**
- Session R4-C1 (Qiskit 1.4.6, the first shard of pool C24, 12 faults) reached Kaggle's 12-hour limit and was resumed as the registration allows.
- The resumed run started on a faster machine.
- Measured from the session's first reading, the reference benchmark then drifted by up to -17.0%, beyond the registered limit of 15% (Section 5).
- Within each part of the session the drift stayed small: at most +3.6% in the first part, measured from the first reading.
- The faults run on the faster machine were the last three in the registered event order: #12469, #13643 and #12952.

**What the rule requires.** Section 5 says a session whose benchmark drifts by more than 15% at any reading is rerun.

**What was done.**
- **Decision:** on 2026-11-01, before any detection result of any session had been looked at, the authors chose to rerun only the three affected faults. A full rerun of R4-C1 would again exceed 12 hours (its clean stage alone took 7.4 hours on Qiskit 1.4.6), so Kaggle would force another resume and the same problem could recur.
- **What had been inspected:** only hardware records, benchmark readings, item and event counts, and the rule E1 import check. No detection was inspected.
- **Session:** R4-C1b runs the registered driver unchanged, with a fresh clean stage, on the same base and datasets. It uses the driver's existing `--only-events` option for the three faults (`kaggle/nb_r4_rerun_c1b.ipynb`). The frozen session notebook is not changed.
- **Analysis input:** R4-C1's event records for the three faults are kept but marked as superseded, in `superseded/`. The registered analysis uses R4-C1b's records for them, with R4-C1b's own clean costs, and R4-C1's records for the other nine.

**Effect.**
- Detection does not depend on machine speed.
- The rerun affects the measured costs (claims E4 and F4) of three faults, and the hang limit, which is a multiple of the clean time.

## D2. The "reported" block of the registered analysis shows only the 3x counts

**What happened.** In `reveal/analyze.py`, the dictionary `res["reported"]` is keyed by suite name only, inside a loop over the two budgets. The 3x count therefore overwrites the 1x count, and `registered_analysis_r4.json` shows 3x counts under plain suite names.

**Effect.**
- No claim is affected. Claims A4 to F4 read the per-fault rows directly.
- The per-fault rows (`results/per_fault.json`) hold both budgets. `RESULTS_R4.md` reports the 1x and 3x counts from them.

**What was done.** The frozen file is not changed. Found on 2026-11-02, after the analysis had run.

## D3. The registered analysis was run through a caching wrapper

**What happened.**
- The first run of `reveal/analyze.py` was stopped by the analysis machine's 30-minute limit for background jobs, before it wrote any output.
- The frozen script runs every selection strategy once per session record. Records of the same base share one calibration session, so it repeats the same selections (B1 and B2 use NR4a, and C1, C1b and C2 use NR4b).

**What was done.**
- The second run used `tools/analysis/run_analysis_cached.py`. It imports the frozen module unchanged, keeps the result of each strategy call, and returns it when the same call recurs.
- The strategies are seeded and pure, so the output is the same as an uncached run.
- The run took 4,233 s.

**Effect.** None on any result.
