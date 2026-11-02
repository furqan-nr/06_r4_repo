# Results of registration R4

Registration: `PREREGISTRATION_R4.md`, pushed 2026-10-31 07:51:18 UTC (commit `64eeca9`), before any session ran.
Analysis: the frozen `reveal/analyze.py`, run on 2026-11-02 on the outputs of the nine Kaggle sessions.
Deviations: `DEVIATIONS.md` (D1 to D3).

This file has two parts. Part 1 is the registered result, decided by the frozen analysis. Part 2 is post hoc. It was done after the registered result was known and decides nothing.

## Part 1. Registered results

### Sessions

| Session | Base | Mode | Faults | Benchmark drift (max) |
|---|---|---|---|---|
| NR4a | 2.6.1 | calibration | none | 3.5% |
| NR4b | 1.4.6 | calibration | none | 2.1% |
| NR4c | 2.3.1 | calibration | none | 8.2% |
| R4-B1, R4-B2 | 2.6.1 | labeling | B, 36 | 1.4%, 2.2% |
| R4-C1 | 1.4.6 | labeling | C24, 12 | 17.0% (see D1) |
| R4-C1b | 1.4.6 | labeling (rerun, D1) | 3 of R4-C1's 12 | 4.4% |
| R4-C2 | 1.4.6 | labeling | C24, 12 | 1.4% |
| R4-A | 2.3.1 | labeling | A231, 11 | 7.4% |

- Every calibration session finished before the labeling sessions of its base.
- All sessions ran on the same CPU class. Every session holds all 22,379 items.
- All 71 faults import from their fault site (rule E1). None was excluded.

### Claims

Faults: pool F has 35 (C24 24, A231 11). Pool B has 36. Pooled: 71.

| Claim | Statement | Result | Numbers |
|---|---|---|---|
| **A4** (primary) | On F, S5 detects more faults than S0, p < 0.05 | **Not supported** | S5 only 4, S0 only 0. 4 discordant faults, p = 0.0625. Fewer than 5 discordant faults is inconclusive by the registered rule |
| B4 | Pooled, S5 detects at least as many as S1 and as S2 | Supported | S5 5, S1 5, S2 1 |
| C4 | Pooled, S5 detects more than S3, p < 0.05 | Not supported | 2 to 0, p = 0.25 |
| D4 | Pooled, S5 with all checks detects more than with output and quality checks only | Not supported | 5 and 5 |
| E4 | At 5% of S5's estimated cost, OA detects at least as many of S5's detectable faults as OO, AC, AC-cost and CH | Supported | 5 detectable. OA 4, OO 4, AC 1, AC-cost 3, CH 3 |
| F4 | OA's real spend over budget: mean at most 1.25, max at most 2.0 | Supported | Mean 0.94, 0.91, 0.92 and max 1.06, 1.06, 1.06 at 2%, 5%, 10% |

The registered "reported" test of A4 on F and B pooled: S5 only 5, S0 only 0, p = 0.031.

### Detections by suite (registered detection rule)

| Suite | F at 1x | B at 1x | All at 1x | All at 3x |
|---|---|---|---|---|
| S0, R3 corpus (never cut) | 0 | 0 | 0 | 0 |
| S1, `random_circuit` | 4 | 1 | 5 | 5 |
| S2, randomized-test grammar | 1 | 0 | 1 | 2 |
| S3, feature corpus end to end | 2 | 1 | 3 | 3 |
| S4, S1 with pass-level items | 1 | 1 | 2 | 5 |
| S5, feature corpus with pass-level items (never cut) | 4 | 1 | 5 | 5 |

S5 detects #13121, #13067, #14934, #15642 (pool F) and #16834 (pool B). Per-fault rows: `results/per_fault.json`.

### Strategies (reported)

Faults of S5 detected by each strategy, at a share of S5's estimated full cost:

| Strategy | 2% | 5% | 10% |
|---|---|---|---|
| OA (observability-aware) | 3 | 4 | 5 |
| OO (output only) | 2 | 4 | 5 |
| AC (all checks) | 0 | 1 | 1 |
| AC-cost | 2 | 3 | 4 |
| CH (cheapest items) | 3 | 3 | 5 |
| CH lane first | 3 | 3 | 5 |
| Random items | 1 | 2 | 3 |

S5's estimated full cost is 909 s (2.6.1), 1,516 s (1.4.6) and 851 s (2.3.1) of CPU time. OA at 10% therefore spends 85 to 152 s and finds all five faults. S0 spends about 1,450 to 1,670 s per base and finds none.

### Comparison with the forecast

- **Forecast:** S5 would detect 4 to 9 of F's 35 faults and 3 to 8 of B's 36, and S0 0 to 2 on F.
- **Observed:** S5 detected 4 of F, at the bottom of the forecast range, and 1 of B, below it. S0 detected 0 on both pools, inside its forecast range.
- **Claims:** the forecast gave A4 a probability of about 0.5, and A4 failed by one discordant fault.

## Part 2. Post hoc analyses (not registered)

Scripts: `tools/analysis/`. Outputs: `results/posthoc/`. Each analysis applies the same rule to every suite.

### P1. A determinism-lane false alarm

S1's detections of #13417, #13643 and #11907 all come from one unit, `S1.2201`, and only from the determinism lane.
- **No other evidence:** under #11907, not a single item changed. Under #13417 and #13643, the only changed items are ones that P2 shows are flaky on the clean build.
- **Clean behaviour:** `S1.2201` is non-deterministic on clean Qiskit 1.4.6. In 20 more clean lane runs (each 3 fresh interpreters, as registered) it was non-deterministic in 2 (`results/posthoc/lane_rerun_1.4.6.json`). Its single item also left its clean set under a fourth fault, #12986.
- **Cause:** the registered lane compares 3 interpreters per build, which cannot catch a unit that varies in about one run in ten.

With this unit's lane alarms removed, S1 detects 2 faults (#16834, #13121). S5 detects both, plus #13067, #14934 and #15642: 3 to 0, not decisive. No other suite's detections change.

### P2. Clean flakiness of changed items

Every item that was changed or crashed under any fault (806 item and base pairs) was rerun on its clean build in 20 more fresh interpreters (`results/posthoc/clean_rerun_*.json`).
- **Flaky:** 12 items left their own clean set in some but not all of the 20 runs. Most are `CommutativeCancellation` items on snapshot inputs on 1.4.6.
- **Machine-dependent:** 13 items differed from their Kaggle clean set in all 20 runs. Each changed under one fault only, and their fingerprint differs between the rerun machine and Kaggle, so they are counted as real effects.

No registered detection rests on a flaky item.

### P3. Where the faults are, and whether they were reached

| Level | Faults (of 71) |
|---|---|
| Output changed on at least one item of any suite (after P2) | 7 |
| Detected by at least one check of any suite (after P1) | 5 |
| No item of any suite changed | 64 |

- **Changed but not detected:** two faults (#13538, #13545) changed many pass-level outputs (56 and 49 items, mostly `Decompose`) with no check alarm.
- **Never reached:** 64 faults changed no output on any of the 22,379 items. For R4's faults, the limit is therefore reach, not the checks.
- **Where the faults are:** 29 faults change transpiler passes (21 in Python, 8 in Rust), and none was detected. Many of these passes are run neither by the preset pass managers nor by the 16-pass catalogue, for example:
  - the Litinski transformation, Clifford+T optimisation, pi/4 rotation substitution and Hoare optimisation.
  - template matching, the commuting two-qubit gate router, dynamical decoupling and rescheduling.
  - four synthesis plugins that run only when chosen through an option.

### P4. The extra checks

- **No added detection:** the probe and contract checks add no detection over the output and quality checks (D4, also true after P1).
- **Probe cost:** the probe takes 73% to 76% of all estimated checking cost on every base (`results/posthoc/suite_costs.json`).
- **Effect of dropping both:** S5 keeps all five detections at about a quarter of its cost.

### P5. Change level

A suite **exposes** a fault when one of its items gives an output outside the clean set (after P2), whether or not a check alarms. This is the golden-output regression oracle. It is not the registered detection rule, and it does not show that the changed output is wrong.

| Suite | S0 | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|---|
| Faults exposed, all 71, 1x | 0 | 3 | 2 | 4 | 4 | 7 |
| Pool F | 0 | 2 | 1 | 3 | 3 | 6 |

Sign tests at this level (post hoc):
- S5 vs S0: 6 to 0 on F (p = 0.016) and 7 to 0 pooled (p = 0.008).
- S5 vs S1: 4 to 0 (p = 0.0625).

### What the post hoc analyses do and do not show

- **They show:**
  - with the lane's false alarm removed, the feature suite detects every fault the random corpus detects, and three more.
  - the probe is the most expensive check and added nothing here.
  - most held-out faults were never reached.
- **They do not change a registered claim.** A4 remains not supported, and B4 remains supported as registered.
- **Their status:** every redesign they suggest is a hypothesis for a new registration on faults that were not used here.
