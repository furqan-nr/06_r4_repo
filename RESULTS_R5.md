# Results of registration R5

**Registration:** `PREREGISTRATION_R5.md`, pushed 2026-11-04 09:27:34 UTC (commit `44b2f48`), before any session ran.

**Deviation:** `DEVIATIONS_R5.md` (R5-D1, benchmark drift). Pushed in commit `f032af4` before any detection result was looked at.

**Analysis:** the frozen `r5/analyze5.py`, run on 2026-11-05 on the nine sessions listed in `results/r5/sessions.json`. Outputs: `results/r5/`.

## Sessions

- All nine bases ran on Kaggle, CPU, Internet off, with 4 cores each.
- Every session finished every stage and event:
  - 52 held-out faults;
  - 18 benign events;
  - one null control per base.
- For 1.1.2 and 2.0.3, the single-session reruns are used (R5-D1).

## Registered claims

All 52 faults are pooled. The tests are one-sided exact sign tests.

| Claim | Statement | Result | Numbers |
|---|---|---|---|
| **A5** (primary) | S5 detects more faults than S0 | **Supported** | S5 7, S0 1. Discordant 6 to 0, p = 0.016 |
| B5 | S5 detects more faults than S1' | Not supported | S5 7, S1' 3. Discordant 5 to 1, p = 0.109 |
| C5 | S5 exposes more faults than S0 | **Supported** | S5 10, S0 1. Discordant 9 to 0, p = 0.002 |
| D5 | S5 exposes more faults than S1' | Not supported | S5 10, S1' 5. Discordant 6 to 1, p = 0.0625 |

**S1' cost condition:** B5 and D5 would also count as not supported under the registered condition on S1' cost.
- On 2.1.2 and 2.2.3, the 800 frozen random-circuit units ran out before reaching S5's clean cost: S1' reached 62% and 57% of it.
- On the other seven bases, S1' reached 100%.

## Reported without decision

**False alarms.**
- **Benign events:** no suite detected any of the 18 benign events. Exposure was 1 of 18 for S5 and 1 of 18 for S1' (different events), and 0 for S0.
- **Null control:** every item that differed under the null control is excluded by the registered rule.

**Faults per suite.**

| | S0 | S5 | S1' |
|---|---|---|---|
| Detected (of 52) | 1 | 7 | 3 |
| Exposed (of 52) | 1 | 10 | 5 |

**Faults detected by each part of S5.** A fault can be detected by more than one part.

| R4 units | R5 units | `TX default` | `TX variants` | `PX raw` | `PX low` | `HX` | `RX` |
|---|---|---|---|---|---|---|---|
| 5 | 6 | 3 | 4 | 4 | 2 | 1 | 4 |

Preset compilation alone (`TX default`, the R4 and R3 style of item) detects 3 of S5's 7. The other 4 need the new item families.

**Per fault** (D = detected, E = exposed only):

| Base | Fault | S0 | S5 | S1' |
|---|---|---|---|---|
| 1.2.4 | #13186 | | D | |
| 1.4.6 | #13606 | D | D | |
| 1.4.6 | #13591 | | D | |
| 1.4.6 | #11787 | | D | D |
| 1.4.6 | #12752 | | D | |
| 1.4.6 | #13762 | | D | D |
| 1.4.6 | #13439 | | E | |
| 2.0.3 | #14217 | | E | E |
| 2.2.3 | #15147 | | D | |
| 2.5.2 | #16362 | | E | E |
| 2.5.2 | #16592 | | | D |

**Reproducibility.**
- The superseded first runs of 1.1.2 and 2.0.3 give the same detection and exposure of every fault as the reruns.
- The only difference is one benign event exposed by S1' in the first 2.0.3 run (`results/r5/superseded_check/`).

**Forecast.** The forecast was S5 detecting 3 to 8 faults and exposing 5 to 12, with A5 at about 0.5 and C5 at about 0.75. The result: 7 detected and 10 exposed.

## What the results show and do not show

- **Shown:**
  - On 52 held-out real faults, the R5 suite detects more faults than the R3 corpus (registered, p = 0.016).
  - It exposes more as well (registered, p = 0.002).
  - It raises no detection on 18 benign changes.
- **Not shown:**
  - It does not show that the R5 input model beats random circuits given the same items (B5, D5).
  - Random circuits with R5's item catalogue detected 3 faults. One of them (#16592) the R5 suite missed.
  - Much of the gain over the R3 corpus comes from the item families (passes, options, pass-manager reuse), which S1' shares.


## Part 2. Post hoc analyses (not registered)

These analyses were done after the registered result was final. They decide nothing. Scripts: `tools/analysis/`. Outputs: `results/r5/posthoc/`. Corrections to earlier statements: `ERRATA_R4_R5.md`.

### Q1. Are the faults active?

Each fault's own regression tests (the test files its fix changed, taken at the fix commit) ran on clean Qiskit and on the fault build (`fix_test_validation.json`).

| Status | Faults |
|---|---|
| Active: a fix test passes on clean and fails on the fault | 43 |
| No trigger | 4 (#13114, #13655, #15436, #15782) |
| The fix changed no test file | 4 (#12410, #13337, #13439, #15967) |
| The fix test hung on the fault for 30 minutes, passed on clean | 1 (#16592) |

- **S5's detections:** all seven are active faults.
- **Rates on the active faults:** on the 43 active faults, S5 detects 7 and exposes 9, S0 detects 1, and S1' detects 2.

### Q2. What raised each detection

**Alarm channels.** `per_fault_channels.json` gives, per detected fault and suite, the number of items that crashed, hung, or raised the output or quality check, and the item families involved.

**Reruns of detecting items.** `item_reruns.json` reruns up to three detecting items per fault in fresh interpreters, clean and fault, with the exception and innermost Qiskit frame.

**Crashes.** Three of S5's seven detections rest on crashes alone (#13591, #13762, #15147). Only #13186, #13606 and #11787 raise the output check.

### Q3. Sensitivity to failed fingerprints

**The problem.** Items whose clean fingerprint is an `unfingerprintable:` label (errata E1) compare equal whenever the fingerprint fails again.

**The check.** We removed every such item from every suite (`posthoc_summary_r5.json`).

**The result.** Every count and every sign test is unchanged: S5 7 detected and 10 exposed, S0 1 and 1, S1' 3 and 5.

### Q4. Concentration on one base

Five of S5's seven detections are on 1.4.6. Without that base, S5 against S0 is 2:0 (p = 0.25).
