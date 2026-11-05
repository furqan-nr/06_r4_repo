# Errata and validation for registrations R4 and R5

**Date:** 2026-11-05.

**What this file does:**
- It corrects and qualifies statements in `RESULTS_R4.md`, `RESULTS_R5.md`, `DEVIATIONS.md`, `DEVIATIONS_R5.md` and `PREREGISTRATION_R5.md`.
- It adds validation evidence produced after the results were final.

**What it does not change:**
- Frozen files are not changed.
- No registered claim decision changes. A4 remains not supported. A5 and C5 remain supported. B5 and D5 remain not supported.

**Status:** everything below is post hoc. It decides nothing.

**Source:** an independent review of R4 and R5 (5 November 2026) raised findings F01 to F10 (implementation and reporting) and M01 to M10 (method). Each entry gives the finding, our check, and the correction.

Scripts: `tools/analysis/validate_fix_tests.py`, `tools/analysis/posthoc_r5.py`, `tools/analysis/rerun_detecting_items.py`, `tools/analysis/overlay_audit.py`, `tools/analysis/r4_strict_exposure.py`. Outputs: `results/r5/posthoc/` and `results/posthoc/`.

---

## Part A. Corrections

### E1 (F01). R5 compared failed fingerprints as equal

**What happened.** In `r5/worker5.py` a fingerprint that raises is stored as the label `unfingerprintable:<exception>`. Two different outputs that both raise the same exception therefore compare as the same output, and the item is not checked.

**How many items.**
- Between 2,179 and 3,338 S5 items per base have such a label on clean Qiskit.
- In S1', between 306 and 720 per base are affected. S0 has none.
- Most are standalone passes on circuits with Clifford objects that lack a `params` attribute.

**Sensitivity.** We removed every item with a label clean fingerprint from every suite and recomputed every decision (`results/r5/posthoc/posthoc_summary_r5.json`):
- S5 still detects 7 faults and exposes 10.
- S0 and S1' are unchanged.
- Every sign test is unchanged.

**What this shows and does not show.**
- No reported detection or exposure rests on a label item.
- It does not show what a correct fingerprint would have found on those items.
- R5's exposure is therefore exposure "under the implemented fingerprint". R5 exposure figures are lower bounds on output change.

### E2 (F02). The fingerprint does not see every output property

**Blind spots.** The fingerprint (cart `obsaware.oracles.fingerprint`) records operation names, parameters, qubit arguments, global phase and layout. It omits:
- classical bit arguments
- custom gate definitions
- condition metadata
- the pass property set.

**Wording.** "Exposed" in R4 and R5 means "differs under this fingerprint". It does not mean "any output difference".

### E3 (F03). R4's thread dimension was not executed

**What happened.**
- R4's feature model has a thread dimension, and units carry a thread value.
- The worker never applies it, and the sessions fix `RAYON_NUM_THREADS=1`.

**What this means.**
- Feature pairs that involve threads were requested, not executed.
- R4's pair-coverage figures (0.938 to 0.978) count the thread dimension and therefore overstate realised coverage.
- No detection count is affected.

### E4 (F04). R4's "real spend" is a charged cost

**Definition.** F4's real spend combines several measurements:
- clean compile times from the labelling session
- clean costs for unchanged items and crashes
- measured candidate costs for some changed outputs.

It is a charged cost under that rule, not measured end-to-end runtime of the faulty executions.

**Correction.** F4 is supported as registered, under this definition. It does not show that faulty executions stayed within budget.

### E5 (F05). R5's cost is clean item-execution cost

**What the cost covers.** S1' was cut at S5's clean item-execution cost: the CPU time of running items on clean Qiskit.

**What it leaves out:**
- fingerprinting
- output and quality checks
- interpreter launches
- screening.

**Correction.**
- Where `RESULTS_R5.md` and the registration say "clean cost", read "clean item-execution cost".
- No statement about total testing time follows from these figures.

### E6 (F06). R4's probe percentage and the "quarter of its cost" statement were wrong

`RESULTS_R4.md` P4 states two things:
- the probe takes 73% to 76% of checking cost
- dropping probe and contract leaves S5 at "about a quarter of its cost".

`PREREGISTRATION_R5.md` repeats the first figure. Both figures are wrong for the cited table.

**From the cited table** (`results/posthoc/suite_costs.json`, S5, which sums recorded check costs and leaves out the determinism lane):

| Base | Probe share of the table's total | Probe share of check cost (total minus compile) | Cost left after dropping probe and contract |
|---|---|---|---|
| 2.6.1 | 87.6% | 89.4% | 12.4% |
| 1.4.6 | 91.3% | 93.5% | 8.7% |
| 2.3.1 | 87.2% | 89.3% | 12.8% |

**Under the registered suite budgets** (clean-passing checks plus the determinism lane, 909 s, 1,516 s and 851 s), the probe accounts for 70.2%, 78.4% and 65.4%.

**Corrected statement:** the probe was the largest cost component of S5, at 65% to 78% of the registered budget and 87% to 91% of the summed check costs. Dropping the probe and contract checks kept all five detections.

**Effect on R5's design:** R5's reason for dropping the probe stands, because the probe was the largest cost and added no detection.

### E7 (F07). R4's reported block shows 3x counts

This is already disclosed as deviation D2. No change.

### E8 (F08). The R5 build check compiled a circuit

**What happened.** `builds/kaggle_build.py` checked each fault build by compiling one 3-qubit circuit (H, CX, CCX, optimisation level 2) under the fault, not only by importing it. This ran on the eight bases built on Kaggle, before registration.
- **What it recorded:** only whether the compilation succeeded, and the site path.
- **What it did not record:** no output, fingerprint or check result was recorded or inspected.

**Correction.** `PREREGISTRATION_R5.md` Section 4 should list this scripted pre-registration compilation beside the 2.4.2 rehearsal. "All 52 faults import" should read "all 52 fault builds import and compile one fixed 3-qubit circuit".

### E9 (F09). Fault overlays cannot delete or rename files

**Risk.** An overlay only adds or replaces files. A fix that added, deleted or renamed a source file would not be reverted correctly.

**Audit.** We listed the file status of every fix commit under `qiskit/` and `crates/` (`results/posthoc/overlay_audit.json`). The audit covered R4's 71 faults, R5's 52 faults and R5's 18 benign events.

**Result.** None of the 141 commits adds, deletes or renames a file there. Every evaluated event only modifies files, so this limitation did not affect any event.

### E10 (F10). Resume and multi-directory consistency are not checked at analysis entry

**What the analysis does not check.** `r5/analyze5.py` takes the first clean record of a base and merges event records without checking that clean references agree.

**Check of the analysed sessions.**
- Each of the nine analysed sessions is a single directory with its own clean stage.
- Each session has all expected events, screen entries and the completion marker.
- The superseded first runs of 1.1.2 and 2.0.3 were analysed separately and give the same fault decisions.

**Effect.** No result is affected. A future runner should validate these invariants at analysis entry.

### E11 (M02). "Never reached" is wrong wording

**Correction.** `RESULTS_R4.md` P3 says 64 faults were "never reached". Read instead: "64 faults changed no item output under the implemented fingerprint". The same applies to "the limit is therefore reach, not the checks".

**Why "reach" cannot be inferred.** Execution, activation, propagation, representation and checking are separate stages. An unchanged fingerprint does not show that the faulty code did not run, which is R3's own lesson.

**What R4's fix-test runs do show.** The triggers need inputs and interfaces outside R4's suite. That supports an input and interface explanation for most misses, without proving it for each fault.

### E12 (M03). Two absolute statements in the deviations

**Statements and corrections:**
- `DEVIATIONS_R5.md` "No rerun can meet the rule as written". Read: "two reruns, of 1.1.2 and 2.0.3, did not meet the rule".
- `DEVIATIONS.md` D1 and `DEVIATIONS_R5.md` "Detection (and exposure) do not depend on machine speed". Read: "Detection and exposure of completed items do not depend on machine speed. The hang limit and the cost-based cut of S1' do."

### E13 (M04). Benign events give an observed rate, not a proven zero

**Observation.** No suite detected any of the 18 benign events.

**Bound.** Under a binomial model, the one-sided 95% upper bound on the detection rate is about 15.3%.

**Sampling caveat.** The benign events were chosen by the absence of fix wording and release notes. Their semantic neutrality was not verified.

**Correction.** Report "0 of 18", not "no false alarms".

### E14 (M05). R4 items that differed in all 20 clean reruns

**What happened.** R4's post hoc P2 treated 13 items that differed from the Kaggle clean set in all 20 reruns as real effects.

**Sensitivity.** We excluded every item that left its clean set in any rerun, 1 to 20 (`results/posthoc/m05_strict_exposure.json`). R4's post hoc exposure counts are unchanged: S0 0, S1 3, S2 2, S3 4, S4 4, S5 7. No fault loses exposure in any suite.

---

## Part B. Validation of the faults

### B1. Each fault's own regression test

**Method.** For every R5 fault, we ran the test files changed by the fix, taken at the fix commit:
- once on clean Qiskit
- once with the fault's overlay (`results/r5/posthoc/fix_test_validation.json`).

A fault is **active** when a test passes on clean and fails on the fault. We applied the same method to R4's five detected faults and its two "changed but not detected" faults (`results/posthoc/fix_test_validation_r4.json`).

**R5, 52 faults:**

| Status | Faults |
|---|---|
| Active | 43 |
| No trigger: every fix test passes on the fault build | 4 (#13114, #13655, #15436, #15782) |
| The fix changed no test file | 4 (#12410, #13337, #13439, #15967) |
| The fix test file hung on the fault build for 30 minutes and passed on clean | 1 (#16592) |

**R5 detections:**
- All seven S5 detections are active faults: #13186, #13606, #13591, #11787, #12752, #13762 and #15147.
- Of the three S5 exposure-only faults, #14217 and #16362 are active. #13439 has no fix test.
- #16592, detected by S1' only, hangs both its fix test and the detecting S1' items (`Optimize1qGatesDecomposition`). That is consistent with the fix, which removes a deadlock.

**On the 43 confirmed active faults:** S5 detects 7 and exposes 9. S0 detects 1. S1' detects 2.

**R4, seven faults:**
- All seven are active: the five S5 detections (#13121, #13067, #14934, #15642, #16834) and the two changed-but-undetected faults (#13538, #13545).
- **Correction to the development record:** `docs/dev/r4_fix_tests/A231_15642.json` recorded #15642 as "no trigger". The new run, on the same 21,107 tests, finds two triggering tests: `test_sympify_reverse_operations` and `test_sympify_rpow_operand_order`. Run three more times with different hash seeds, both pass on clean and fail on the fault every time. The cause of the earlier record was not traced.

### B2. What raised each R5 detection

`results/r5/posthoc/per_fault_channels.json` lists, for each detected fault and suite, which channel fired and in which item families. `results/r5/posthoc/item_reruns.json` reruns up to three detecting items per fault on clean Qiskit and on the fault, each in a fresh interpreter, and records the exception and innermost Qiskit frame.

| Base | Fault | Suite | Crash items | Hang items | Output-check items | Quality items | Families |
|---|---|---|---|---|---|---|---|
| 1.2.4 | #13186 | S5 | 0 | 0 | 3 | 1 | PX raw |
| 1.4.6 | #11787 | S5 | 63 | 0 | 21 | 11 | RX |
| 1.4.6 | #11787 | S1' | 49 | 0 | 100 | 8 | RX |
| 1.4.6 | #12752 | S5 | 15 | 0 | 0 | 70 | PX raw, RX, TX default, TX variants |
| 1.4.6 | #13591 | S5 | 482 | 0 | 0 | 0 | PX low, RX, TX default, TX variants |
| 1.4.6 | #13606 | S0 | 0 | 0 | 6 | 2 | TX default |
| 1.4.6 | #13606 | S5 | 0 | 0 | 33 | 8 | HX, PX low, PX raw, RX, TX default, TX variants |
| 1.4.6 | #13762 | S5 | 101 | 0 | 0 | 0 | PX raw |
| 1.4.6 | #13762 | S1' | 134 | 0 | 0 | 0 | PX raw |
| 2.2.3 | #15147 | S5 | 2 | 0 | 0 | 0 | TX variants |
| 2.5.2 | #16592 | S1' | 0 | 120 | 0 | 0 | PX raw |

**Stage (item reruns).** Every rerun reproduced its detection: 32 of 32 items. No crash happened while a unit's input was built.
- **Pass run:** crashes of #12752 and #13762 are raised inside the run of the named pass.
- **Preset compilation:** crashes of #15147 (Target with durations and ALAP or ASAP scheduling) are raised inside it.
- **Reused pass manager:** crashes of #11787 are raised in the second run of a reused pass manager (layout composition).
- **Lowering, not the named pass:** the crashes of #13591 are raised while the circuit is lowered to the basis by a level-0 preset compilation, in unitary synthesis, before the named scheduling pass runs. These PX low detections therefore do not localise the fault to the named pass (review M06).
- **Output-check and quality detections:** for #13186 and #13606, the fault rerun gives a fingerprint different from clean, without a crash.
- **#16592 in S1':** all three items hang under the fault and finish on clean.

---

## Part C. Statements to use

| Use | Avoid |
|---|---|
| On 52 held-out real faults, S5 detected 7 and the R3 corpus 1 (registered, p = 0.016) | The method detects quantum compiler bugs in general |
| All seven detections are faults whose own regression test fails | Every detection is a rediscovered bug in the exact historical form |
| Random circuits with the same items were not shown to be worse (B5, D5) | The feature model beats random generation |
| No suite detected any of 18 benign events | The method has no false positives |
| No item output changed for 64 of R4's 71 faults under our fingerprint | Those faults were never reached |
| S1' was cut at S5's clean item-execution cost | The suites had equal testing cost |
