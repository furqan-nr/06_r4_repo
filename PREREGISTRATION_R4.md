# Pre-registration R4: input-feature coverage and pass-level testing on held-out real Qiskit faults

**Status:** approved by the authors on 2026-10-31. Becomes a registration when this file and the files listed in `PREREGISTRATION_R4.sha256` are pushed, before any R4 session has run. Push times and the SHA-256 of every Kaggle dataset are recorded in `REGISTRATION_RECORD.md` (not frozen).

**Authors:** Furqan Nasir (CUSIT; FAST-NUCES), Muhammad Arif Shah (CUSIT), Iftikhar Alam (CUSIT).

## 1. Why a fourth registration

Registration R3 (furqan-nr/cart, commit `198c867`) re-injected 15 real Qiskit bugs, each selected because its fixed code runs on the 116-unit corpus. None of the 15 changed any corpus compilation. The post hoc diagnosis (cart `docs/R3_DIAGNOSIS.md`) named three causes:

1. The corpus never supplies the inputs the bugs need.
2. Seven of the 15 are not compilation-output faults.
3. End-to-end compilation hides some faults that pass-level tests reveal.

R4 tests the remedy on real faults that played no part in the design:

- a corpus generated for **input-feature coverage**;
- **pass-level test units** beside end-to-end compilation.

## 2. What is new

**Corpus** (`reveal/features.py`, `reveal/generator.py`, `reveal/corpus.py`, `data/corpus.json`).
- **Features:** ten feature dimensions from Qiskit's public interface and the R3 diagnosis. Each replicate is a strength-2 covering array, and there are six replicates (seeds 20261031 to 20261036).
- **Validity rule (clean builds only):** a unit is kept if it compiles on all three clean bases and gives the same fingerprint in five fresh interpreters on each.
- **Result:** 357 units. Pair coverage is 0.938 to 0.978 per replicate.
- **Identity:** every unit's circuit, once its parameters are bound, is byte-identical on Qiskit 1.4.6, 2.3.1 and 2.6.1 (`tests/identity.py`).

**Pass-level items** (`reveal/passlevel.py`).
- **Catalogue:** 16 optimisation and synthesis passes present in all three bases.
- **Inputs:** each pass runs on raw inputs (the corpus circuit) and on snapshot inputs (the circuit entering that pass in a clean preset compilation).
- **Validity:** the same rule as for units.

**Comparators** (`reveal/comparators.py`).
- **S1:** Qiskit's `random_circuit`.
- **S2:** the instruction grammar of Qiskit's randomized transpiler test, without measurement and reset.
- **S4:** S1 with pass-level items.
- **Shared rules:** all comparators use the same option grid, the same validity rule, and identical circuits on all bases.

**Suites and budget** (`reveal/suites.py`).
- **The six suites:** S0 is the R3 corpus. S1 and S2 are the random corpora. S3 is the feature corpus end to end. S4 is S1 with pass-level items. S5 is the feature corpus with pass-level items, the proposed suite.
- **Budget:** the common budget is S5's full estimated cost on the base. S1 to S4 are cut to it, and S0 keeps its full cost (about 1,420 s). S5 therefore competes with S0 at a much smaller budget, which works against S5.

**Checks** (`reveal/checks.py`). The frozen checks, imported unchanged, with three differences from R3, each forced by the new items:
1. Each check runs on its own, so a check that raises is "not assessable" for that item instead of failing every check.
2. The probe runs through its own documented fallback simulator (Qiskit's reference Statevector), because Aer rejects many gate kinds the corpus contains on purpose.
3. Pass-level items use a pass contract check (property set entries equal to the clean pass's) and a version-independent fingerprint.
4. Every output is checked against the input circuit it was pickled with in the worker, not against a copy rebuilt in the checking process. On Qiskit 1.4, qubits compare by identity, so cart's contract check K3 failed on every rebuilt input, on clean builds too.

**Clean-result guard.**
- Clean Qiskit was observed to compile some units to one of two results across fresh interpreters, even with fixed hash seeds (`docs/DESIGN_LOG.md`).
- The clean reference of an item is therefore the set of results from five clean interpreters.
- A candidate in that set detects nothing.
- A quality alarm counts only if the candidate is worse than every clean result.

**Driver** (`reveal/label.py`, `reveal/worker.py`). As cart's `r3/label_faults.py`: fault sites, candidates in separate interpreters, the crash and hang rule, rule E1, event order seed and benchmark readings. The determinism lane follows the frozen method (hash seeds 0, 1, 2) with a worker that can build every item.

**Fault builds** (`builds/make_faults.py`).
- **Isolation:** each fault is built in a fresh copy of the clean build's cargo target directory.
- **Clean bases:** all three are our own builds from the same pipeline, including 2.6.1. R3's 2.6.1 wheelhouse is not reused, because the fault libraries must pair with the clean build they were derived from.
- **Null check:** a null build must reproduce the clean wheel file for file before any fault is built.
- **Why:** this corrects a defect found in R3's builds (Section 7).

## 3. Held-out faults

- **Selection:** `selection/mine_pools.py` applies R3's rule steps 1 to 4 (a fix with a release note, compilation-related, not contacted before) and reverse application on the base. R3's step 5 (exercised by the corpus) is dropped, because the point is to measure what each corpus reveals.

| Pool | Base | Faults | Use |
|---|---|---|---|
| F: C24 | 1.4.6 | 24 fixes merged between 1.0.0 and 2.0.0, every changed file still present in 2.6.1 | primary |
| F: A231 | 2.3.1 | 11 fixes after 2.0.0, absent from 2.6.1, revertible on 2.3.1 | primary |
| B | 2.6.1 | 36 fixes that R3 rejected because the R3 corpus did not run their changed code | secondary, reported separately |

- **Exclusions:** R3's 15 faults and the contacted list are excluded from every pool.

## 4. Disclosure: what is known before registration

1. Everything disclosed in R1 to R3, all their data and results, and R3's post hoc diagnosis and trigger experiment.
2. The 154 commit subjects of R3's mining window, read for R3. These include the titles of pool B and pool A231 fixes. **No title, patch or test of any held-out fault was displayed or read for R4.** Pool C24's titles have never been read.
3. **Development set**, used freely for design and debugging:
   - R3's 15 faults;
   - the fixes contacted in earlier work.

   A development run of the full feature suite on R3's faults (base 2.6.1) detected 3 of 15 (#16402, #16599, #17163). The R3 corpus detected 0. This is a development observation, biased in the suite's favour (`docs/dev/dev_run_r3_faults.json`).
4. **Clean-build observations** recorded in `docs/DESIGN_LOG.md`:
   - non-determinism;
   - crashes of clean 1.4.6;
   - Aer limits;
   - costs.
5. **Held-out fault builds:** the overlays are built after the design is frozen (`PREREGISTRATION_R4.sha256` lists the frozen design files). No fault build has compiled a corpus unit or been seen by any check before registration. The only exception is the null-build check, which uses no fault.

## 5. Sessions

| Order | Session | Base | Mode | Faults |
|---|---|---|---|---|
| 1 | NR4a | 2.6.1 | calibration | none |
| 2 | NR4b | 1.4.6 | calibration | none |
| 3 | NR4c | 2.3.1 | calibration | none |
| 4, 5 | R4-C1, R4-C2 | 1.4.6 | labeling | C24 (two shards) |
| 6 | R4-A | 2.3.1 | labeling | A231 |
| 7, 8 | R4-B1, R4-B2 | 2.6.1 | labeling | B (two shards) |

- **Order:** a labeling session on a base starts only after that base's calibration session has finished.
- **Platform:** Kaggle, CPU, Internet off, pinned environment, one core (`kaggle/nb_r4_session.ipynb`).
- **Benchmark rule:** a session whose reference benchmark drifts by more than 15% at any reading is rerun, as in R3.

## 6. Claims (decided by `reveal/analyze.py`, frozen)

- **Detection:** a suite detects a fault when any of its items detects it under rule L1, or when the determinism lane detects it on one of its end-to-end items.
- **Sign tests:** one-sided exact tests on discordant faults. With fewer than 5 discordant faults, p < 0.05 cannot be reached, and such a claim is inconclusive and counted as not supported.

| Claim | Statement |
|---|---|
| **A4** (primary) | On pool F, S5 detects more faults than S0: p < 0.05. Reported: the same test on F and B pooled. |
| B4 | On F and B pooled, S5 detects at least as many faults as S1 and as many as S2. |
| C4 | On F and B pooled, S5 detects more faults than S3: p < 0.05. |
| D4 | On F and B pooled, S5 with all checks detects more faults than S5 with the output and quality checks only. |
| E4 | At 5% of S5's estimated full cost, OA detects at least as many of S5's detectable faults (F and B pooled) as each of OO, AC, AC-cost and CH. With fewer than 5 detectable faults: inconclusive, not supported. |
| F4 | OA's real spend over budget has mean at most 1.25 and maximum at most 2.0 over all faults, at 2%, 5% and 10%. |

**Strategies:** the strategies are cart's, imported unchanged. Each item maps onto the frozen structures:
- **family:** the unit's gate group and block, or for R3 units their circuit family;
- **backend:** "e2e" or the pass name;
- **channel:** the frozen channel of each check, with the pass contract counted as the contract channel.

**Reported without decision:**
- every suite at 1 times and 3 times the budget, for F, B and pooled;
- per-fault channels and items;
- feature-pair coverage of every suite;
- detection of every strategy at 2%, 5% and 10% of S5's estimated full cost. R3's ten-budget grid is not repeated: the frozen strategies re-sort the item pool on every pick, which at R4's scale (about 35,000 selection items) takes hours per budget.

## 7. Deviation carried over from R3

R3's fault builds shared one cargo target directory. As a result, R3's #16884 and #16963 builds also contain #17163's bug:
- **Evidence:** #17163's own regression tests fail on both. On isolated rebuilds they pass, and each still fails its own test (`docs/DESIGN_LOG.md`).
- **Effect on R3's result:** none in substance. R3 detected 0 of 15, and extra bugs could only have helped detection.
- **Effect on R3's diagnosis:** rerunning the R3 trigger experiment on the isolated rebuilds gives the same figures (5 of 8 at pass level, 3 of 8 end to end).
- **Reporting:** this is reported with R3's results.

## 8. Forecast (registered judgement)

- **Revealable faults:** about half of the faults in each pool are compilation-output faults (R3: 8 of 15), so about 17 in F and about 18 in B.
- **S5 detections:** about 4 to 9 of F's 35 and 3 to 8 of B's 36. The development rate (3 of 8 compilation faults) is optimistic, because those faults informed the design.
- **S0 detections:** 0 to 2 on F, and almost surely 0 on B.

| Claim | P(supported) | Reason |
|---|---|---|
| A4 | about 0.5 | p < 0.05 needs at least 5 discordant faults, nearly all in S5's favour |
| B4 | about 0.4 | random corpora at equal cost have many more circuits |
| C4 | about 0.3 | in development, pass level added 2 of 3 detections, but the sign test needs 5 |
| D4 | about 0.6 | in development, 2 of 3 detections were probe-only |
| E4 | about 0.5 | |
| F4 | about 0.8 | |

## 9. Deviations

As in R1 to R3. A deviation is reported with its reason. No result is reported without the registered analysis.
