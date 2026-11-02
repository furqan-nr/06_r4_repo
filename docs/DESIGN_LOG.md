# Design log and disclosure record

This file records, in order, every design decision and everything the authors knew before registration R4. The registration's disclosure section is written from it.

## 2026-10-30: study plan

- Plan drafted and shared with the authors. Research questions RQ1 to RQ4, suites S0 to S5, claims A4 to F4.
- Known at this point: everything disclosed in cart's registrations R1 to R3, R3's data and results, and the post hoc R3 diagnosis (cart: `docs/R3_DIAGNOSIS.md`, `posthoc/r3_triggers.py`). The R3 faults' patches and regression tests were read for R3.

## 2026-10-30: feasibility count of held-out faults

- A Qiskit clone (main at `0f2d7ddfd`) was mined with R3's rule steps 1 to 4 on two windows, and patches were tested for reverse application on release tags.
- Only counts were displayed. No commit subject, patch or test of a held-out fault was displayed or read. The 154 subjects of the R3 window had already been read for R3.
- A crude automated scan of the fixes' added tests (counts only) was run once and is not used.

## 2026-10-31: fault pools decided

- Primary pool F = C24 (24 fixes from 1.0.0..2.0.0, re-injected on 1.4.6, every changed file still present in 2.6.1) plus A231 (11 fixes after 2.0.0, absent from 2.6.1, revertible on 2.3.1). Secondary pool B = 36 fixes on 2.6.1 that R3 rejected because the R3 corpus did not run their changed code. Reserve: 39 further fixes.
- The file-survival rule for C24 uses file paths only.
- Why R3 started at 2.0.0: no written reason survives. The cut-off was part of R3's frozen rule, set before any R3 data existed. Only 7 of the 35 pre-2.0 candidates revert cleanly on 2.6.1, which is the likely practical reason.

## Development set (may be used freely for design and debugging)

- R3's 15 faults (cart: `r3/faults.json`).
- The fixes listed as contacted in cart's R3 selection (the faults of the earlier historical-fault study and their backports, the models of the R1 operators, the case study faults).

## Order of work that protects the held-out claim

1. Clean builds of 1.4.6 and 2.3.1, and the port check, use clean Qiskit only.
2. The feature model, corpus generator and pass-level units are developed on the development set only.
3. They are frozen and hashed.
4. Only then are held-out fault overlays built.

## 2026-10-31: corpus generator and pass-level units (clean Qiskit only)

All results in this entry come from clean Qiskit (PyPI 1.4.6, 2.3.1 and 2.6.1). No held-out fault was built.

- **Feature model** (`reveal/features.py`): ten dimensions. The angle class "multiples of pi/2" became "multiples of pi/4", so that the Clifford+T basis can use T angles.
- **Constraints added after clean compile failures:**
  - Clifford+T rows allow only multiples of pi/4, no unitary, Pauli-evolution, custom or permutation blocks, no symbols and no approximation. Permutations are resynthesised as general unitaries at levels 2 and 3.
  - Control flow never goes with basic routing, which Qiskit rejects.
- **Covering array:** strength 2, seed 20261031. It has 64 rows and covers all allowed value pairs.
- **Generator** (`reveal/generator.py`): every random draw comes from its own seeded Python and NumPy sources, never from Qiskit's random helpers, so a row gives the same circuit on every version.
- **Symbols:** circuits with symbolic parameters are compiled unbound. Their values are bound to the original and the compiled circuit before any check, because the frozen checks need numbers.
- **Clean-validity rule** (`reveal/corpus.py`): for each row, the first of up to 5 attempts is kept that compiles on all three clean bases and gives the same fingerprint in two fresh interpreters (hash seeds 0 and 1). This keeps 63 units, drops 1 row, and gives pair coverage 0.996.
- **Observations on clean Qiskit, kept for the paper's discussion and not used as evidence:**
  - Qiskit 1.4.6 crashes in BasicSwap on annotated operations ("'AnnotatedOperation' object has no attribute 'mutable'").
  - Qiskit 1.4.6 raises AttributeError in CommutativeInverseCancellation on 16 corpus inputs where 2.3.1 and 2.6.1 do not.
  - A few attempts compile to different fingerprints under different hash seeds on clean 2.3.1 and 2.6.1. The rule drops them.
- **Pass-level catalogue** (`reveal/passlevel.py`): 16 optimisation and synthesis passes available in all three versions, with raw and snapshot inputs. A first run on the 63 units ran about 880 raw and 340 snapshot (pass, input) pairs per version. Failing pairs fail on clean builds too and will be dropped by the same validity rule.

## 2026-10-31: clean builds, port check and determinism (clean Qiskit only)

- **Clean wheels built.** The hashes and packaging tools are in `builds/BUILD.md`. Both builds give the same fingerprints as PyPI on the 116 R3 units.
- **Port check, Qiskit 1.4.6 (PyPI).** cart's frozen clean-side measurements ran on all 116 R3 units with no errors: cost calibration, output, quality, probe and contract checks, the determinism lane and the reference benchmark. The frozen code therefore runs on 1.4.6 and pool C24 is usable. Clean verdicts pass on 113 of 116 units. On the other 3, the contract check fails on qft-n12-heavy_hex-opt1 and the probe fails on qft-n18-line-opt3 and qft-n18-heavy_hex-opt3. Under rule L1, a check that fails on the clean build cannot detect a fault on that unit.
- **Cross-version input identity.** Two generator changes make every corpus circuit, once its parameters are bound, identical on 1.4.6, 2.3.1 and 2.6.1 (`tests/identity.py`, 63 of 63):
  - Annotated operations are now built explicitly, because `control(annotated=True)` gives a standard controlled gate on 2.x but an annotated operation on 1.4.
  - Symbolic angles in angle pairs that sum to 2pi are now evaluated numerically, because versions print expressions differently.
- **Clean non-determinism.** Clean Qiskit gave two different compiled results for some units across fresh interpreters. Fixing the hash seed did not stop this, and it appeared in about 1 run in 6 on 1.4.6 with an rzz basis. Two consequences:
  1. The validity rule now uses five fresh interpreters (hash seeds 0 to 4). On our own 1.4.6 and 2.3.1 builds and PyPI 2.6.1 it keeps 63 units and drops 1 row, with pair coverage 0.996.
  2. Filtering cannot remove a rare effect completely, so the labeling driver will add a guard. The clean result of each unit is the SET of fingerprints from repeated clean runs. A candidate whose fingerprint is in that set detects nothing. A quality alarm counts only if the candidate is worse than every clean result. This rule must be stated in the R4 registration.

## 2026-10-31 (continued): full corpus, comparators, driver (clean Qiskit and development faults only)

**Corpus.**
- **Coupling width:** line, ring and one-way couplings are now as wide as the circuit (previously one qubit wider). Without ancilla qubits the frozen output check can be exact rather than structural.
- **Replicates:** the corpus now has 6 replicates, each a covering array with its own seed (20261031 to 20261036). Replicate 0 alone covers every allowed pair. Later replicates add new circuits over the same pairs.
- **Lazy validity rounds:** a row's next redraw is tried only if earlier ones failed on some base.
- **Result:** 357 units kept and 44 rows dropped. Pair coverage per replicate is 0.938 to 0.978.
- **Instability found on a rerun:** a rerun found units that had passed five stability runs before but failed them now (the kept set fell from 383 to 357). Rare clean non-determinism is therefore real and not fully caught by five runs. A further recheck of the 357 kept units, five more interpreters per base, found no failures. The labeling guard (clean result sets) stays essential.
- **Cross-version identity:** two more fixes keep the 357 units byte-identical on all three bases.
  - The inverse of a Pauli-evolution gate is built explicitly, because `inverse()` differs between 1.4 and 2.x.
  - The description normalises -0.0 to 0.0.

**Comparators** (`reveal/comparators.py`).
- **S1:** Qiskit's `random_circuit`, generated once with 2.6.1 and stored as OpenQASM 2, so that all bases compile the same circuits.
- **S2:** a seeded walk over the instruction grammar of Qiskit's randomized transpiler test, without measurement and reset, because the frozen checks compare unitaries.
- **Options:** both draw compile options from the same grid as the feature corpus.
- **Identity:** S1 and S2 circuits are identical on all three bases (160 of 160 checked).

**Pass-level items.**
- **Fingerprint:** pass-level items use their own fingerprint, the version-independent description plus the canonical property set, because the frozen fingerprint cannot read Clifford objects that a pass leaves in place.
- **Validity:** the same rule as for units, in `reveal/validity.py`.

**Driver** (`reveal/label.py`, `reveal/worker.py`, `reveal/checks.py`).
- **Kept from R3:** fault sites, separate interpreters, the crash and hang rule, rule E1 and benchmark readings.
- **Clean reference:** the set of results from five clean interpreters.
- **Checks:** each check runs separately, and a check that raises is not assessable.
- **Lane:** the determinism lane follows the frozen method with a worker that can build every item.
- **Dry run:** a dry run on 90 items with a null fault and two development faults ran end to end. The null fault detected nothing.

**Budget (changes the study plan).**
- **Costs measured on clean 2.6.1:**
  - An end-to-end feature or random unit costs about 0.01 to 0.05 s with all checks.
  - A pass-level item costs about 0.02 s.
  - The R3 suite costs about 1,420 s.
- **Why the plan changes:** cutting S1 to S5 to S0's cost would need tens of thousands of items.
- **Proposed instead:** the common budget is S5's full estimated cost. S1 to S4 are cut to it. S0 keeps its full cost. A4 therefore compares S5 with an S0 that spends far more, which works against our method.
- **Pool sizes:** the S1 and S2 pools must be large enough to fill S5's cost, about 0.02 to 0.05 s per unit.

**Probe simulator.**
- **Problem:** in the first full development calibration (2.6.1, 8,112 items), the probe was not assessable on 5,557 of 7,123 usable items. About 2,800 of those failed because Aer rejects gate kinds the feature corpus contains on purpose (cs, csdg, xx_plus_yy, dcx, Clifford objects, Pauli evolutions, permutations, the Python-defined gate). The rest were measured or control-flow circuits, which the probe cannot assess.
- **Change:** `reveal.checks` now calls the frozen probe with `qiskit_aer` hidden, so the probe takes its own documented fallback, Qiskit's reference Statevector, which simulates every gate with a matrix or definition. No frozen file is changed.
- **Effect:** on a sample of raw pass items, the probe passes on the clean build for 104 of 179 items, up from a small minority. The remaining items are measured or control-flow circuits, plus 7 whose clean pass already alarms; rule L1 excludes those.
- **For the registration:** this is a stated difference from R3, where the probe ran on Aer.

## 2026-10-31: development run on R3's 15 faults (development set, base 2.6.1)

**Setup.** The full feature suite ran on R3's own clean 2.6.1 wheelhouse against R3's 15 fault overlays and a null fault:
- 357 end-to-end units and 7,755 pass-level items, 8,112 in all;
- 7,123 items usable;
- no item had more than one clean result.

These faults informed the design, so the results below are **development observations, not evidence**. They are biased in the suite's favour.

| Fault | Detected (items) | Where |
|---|---|---|
| null | 0 | none (no false alarm on 8,112 items) |
| #16402 global phase, CommutativeCancellation | 4 | pass level only (raw and snap), probe only |
| #16599 sx resynthesis of negative angles | 5 | pass level only, output and probe |
| #17163 TwoQubitBasisDecomposer | 2 | end to end, probe only |
| #16884, #16963 | 2 each | **not their own bugs**: they contain #17163's bug (see below) |
| the other 10 | 0 | 7 are not compilation-output faults; #13945 is not readable by any check; #16153 needs csdg before cs, which the corpus never produces |

R3's corpus revealed 0 of the 15.

- **Confirmed detections:** at least 3 of the 8 compilation faults (#16402, #16599, #17163). #16884 and #16963 are open until their builds are redone.
- **Pass level:** two of the three confirmed detections (#16402, #16599) are pass level only, which is the RQ2 mechanism.
- **Probe:** two of them (#16402, #17163) are seen only by the probe, which is the RQ3 mechanism.

**#16153 is a known design gap.** The generator's inverse pairs always place a gate before its inverse. We do **not** change the generator to catch this one fault, because that would tune the design on a known fault, even a development one. If ordering is added as a feature later, it must be justified independently of #16153.

## 2026-10-31: defect found in R3's fault builds (affects R3, reported, not hidden)

- **What the development run showed:** #16884, #16963 and #17163 produced byte-identical candidates on two units, all with the global phase shifted by exactly pi.
- **Cause:** cart's `r3/make_faults.py` built every fault with one shared `CARGO_TARGET_DIR`, starting each time from `shutil.copytree` of the pristine source, which keeps old modification times. Cargo therefore did not rebuild a crate whose restored files were older than its last build.
  - The build order began 17163, 16988 (Python only), 16963, 16884, 16752.
  - The synthesis crate reverted for #17163 stayed in the #16963 and #16884 builds.
  - It was rebuilt when #16752 changed the circuit crate, on which the synthesis crate depends.
- **Confirmation:** #17163's own regression tests (`test_zsx*`, from its fix commit) pass on the clean build, and one fails on each of #17163, #16884 and #16963. All pass on #16402, which was built later.
- **Consequences:**
  - **R3's registered result** is not changed in substance. It found 0 of 15, and extra bugs in two builds could only have made detection easier. It must be reported as a deviation: the events for #16884 and #16963 were not single-fault events.
  - **R3's post hoc diagnosis must be rechecked.** It counted #16884 as caught at pass level ("output, probe" on its ConsolidateBlocks trigger), and that may be #17163's bug. The "5 of 8 at pass level, 3 of 8 end to end" figures are under review until #16884 and #16963 are rebuilt in isolation.
  - **R4:** `builds/make_faults.py` builds each fault in a fresh copy of the clean target directory, and a null build must reproduce the clean wheel file for file before any fault is built.

**Resolution (same day).**
- **Isolated rebuilds:** #16884 and #16963 were rebuilt from a copy of a fresh clean target directory.
  - #17163's tests now pass on both.
  - Each fails or hangs its own regression test: `test_toffoli_is_not_removed` fails, and `test_custom_gates_sharing_wire` hangs, which is the deadlock.
  - The two units that "detected" them now give the clean result.
- **Development run, final:**
  - With the isolated builds, the feature suite detects neither #16884 nor #16963.
  - The development result is therefore **3 of 15: #16402, #16599 and #17163**. All three are compilation-output faults, so this is 3 of 8 such faults. R3's corpus detected 0.
  - Summary: `docs/dev/dev_run_r3_faults.json`.
- **R3 trigger experiment on the isolated builds** (cart `posthoc/r3_triggers.py`, unchanged):
  - #16884 is still caught at pass level by the output and probe checks and not reached end to end, exactly as R3's diagnosis reported.
  - #16963 is still not reproduced under the harness.
  - **R3's diagnosis figures (5 of 8 at pass level, 3 of 8 end to end) therefore stand.**
  - Output: `docs/dev/r3_triggers_isolated_16884_16963.json`. Only these two faults had overlays in that run, so the rows for the other faults are not meaningful.
- **What still has to be reported for R3:** its #16884 and #16963 events were not single-fault events. Its registered result (0 of 15) is unchanged.

## 2026-10-31: comparator pools validated (clean builds only)

- **Pools checked:** S1 (6,000 random_circuit units) and S2 (6,000 test-grammar units), five fresh interpreters per base.

| Base | Valid | Unstable across interpreters | Compile error |
|---|---|---|---|
| 1.4.6 (our build) | 11,179 | 813 (6.8%) | 8 |
| 2.3.1 (our build) | 11,963 | 22 | 15 |
| 2.6.1 (PyPI) | 11,963 | 23 | 14 |

- **Clean 1.4.6 non-determinism:** clean Qiskit 1.4.6 compiles about 7% of random circuits to different results in different fresh interpreters, against about 0.2% for 2.3.1 and 2.6.1. This is a clean-build observation for the paper's discussion of the determinism channel. It also supports the clean-result guard.
- **Compile errors:** a few S1 units with an ECR basis on a one-way coupling fail on every base ("ecr would be supported on ..."), a direction rule of Qiskit.

## 2026-10-31: item list and analysis checks (before freezing)

- **Comparator costs:** on clean 2.6.1, a sample of 150 S1 and 150 S2 units costs 0.23 s and 0.31 s per unit, with all checks and the lane.
- **Pool sizes:** S5's full cost is about 146 s, so the pools are trimmed to their first 2,500 valid units each, which is enough for the reported 3x level.
- **Pass-level items for S4:** validated for the first 600 S1 units.
- **Item list** (`data/items.json`): 22,379 items, all valid on the three bases:
  - 116 R3 units, 357 feature units, 2,500 S1 units and 2,500 S2 units;
  - pass-level items for the feature and S1 units.
- **Smoke test of the analysis on the development output found a bug:** `reveal/suites.py` still cut every suite to S0's cost (the original plan). Fixed to the registered rule:
  - S5 is never cut;
  - S1 to S4 are cut to 1x (registered) or 3x (reported) S5's full estimated cost;
  - S0 is never cut.
- **Strategy grid:** the strategies run only at the budgets the claims use (2%, 5%, 10%). The frozen strategies re-sort the item pool on every pick, and R3's ten-budget grid did not finish in 50 minutes at this scale.

## 2026-10-31T00:22Z: design freeze 1 (before any held-out fault is built)

`tools/freeze.py` wrote `PREREGISTRATION_R4.sha256` over the design files (package, corpus, comparator data, item list, pools, build scripts, notebook). Its SHA-256 is `ed7357f0567f8373d69ff58537d6785e76b9cd5516e7d3e33a3513b5bd5a856c`.

- **No held-out fault has been built** at this point.
- **Allowed changes before registration:** the registration text (claims and forecast, pending the authors' approval).
- **Any other change to a frozen file** before registration is listed here with its reason.

## 2026-10-31: changes to frozen files after design freeze 1 (before registration, before any fault data)

1. **`builds/make_faults.py`: source copy bug.**
   - **Bug:** the copy skipped any folder named `target` or `build` at any depth. Qiskit 2.3.1 and 2.6.1 have a source module folder `crates/transpiler/src/target`, so their clean build failed to compile. Now only the top of the tree is filtered.
   - **Effect on C24:** none. Qiskit 1.4.6 has no such folder, so the C24 builds, already finished, are unaffected. Their null check passed, and all 24 overlays are non-empty.
   - **Same file, earlier change:** every build now uses one fixed source path and one fixed target path, because compiled code embeds source paths. This was made before any fault build.
2. **`builds/export_faults.py`** (new): writes each held-out pool's build list and patches outside the repository, printing counts only. It is added to the frozen list.

No change uses any fault's behaviour or result. A second freeze follows when all builds are done.

## 2026-10-31: held-out builds done, rehearsal, design freeze 3

**Held-out builds** (`builds/records/`):
- C24: 24 faults on 1.4.6;
- A231: 11 faults on 2.3.1;
- B: 36 faults on 2.6.1.

All three pools pass the null check, every overlay is non-empty, and all 71 faults import (rule E1). Each pool's clean wheel compiles all 116 R3 units and 357 feature units to the same fingerprints as PyPI (473 of 473 per base). No fault build has compiled a corpus unit or been seen by any check.

**Rehearsal from the packaged Kaggle datasets** (code zip, each wheelhouse, a null fault, 19 items of every kind) found one more bug:
- **Bug:** cart's contract check K3 looks up the compiled circuit's input qubits in the original circuit. The original was rebuilt in the checking process, and on Qiskit 1.4 bits compare by identity, so K3 alarmed on every clean output. The contract channel would have been lost for all of C24.
- **Fix:** the worker now returns the input circuit pickled together with each output, and the checks use that pair (`reveal/worker.py`, `reveal/label.py`). No fault was involved.
- **Result after the fix:** on all three bases, every item is usable, the contract check passes on the clean build for the end-to-end units where it applies, and the null fault detects nothing.

**Frozen files changed** (before registration, fault-blind): `reveal/worker.py`, `reveal/label.py`, `PREREGISTRATION_R4.md` (check difference 4), `tools/freeze.py` (adds `builds/records`), `builds/BUILD.md` (session builds).
Design freeze 3: manifest SHA-256 `a9c7596cd7c3c78b7bdd5db07e69bb6d64deb36f8099feb541abfbe40f9d4bb3`.
Final freeze (approved registration): manifest SHA-256 `7656ffda371b753122d8e6e2a2e39495a04257ccb7c720a167904c12b0e0b96a`.

## 2026-11-02: registered analysis and post hoc audit of R4

**Registered analysis.**
- **Run:** the frozen `reveal/analyze.py`, from the code in the registered `r4-code.zip` (`freeze --check` passes), through the caching wrapper of D3.
- **Results:** A4 not supported (4 to 0 on F, p = 0.0625). B4, E4 and F4 supported. C4 and D4 not supported. Details in `RESULTS_R4.md`.
- **Reporting bug:** the "reported" block of the analysis keeps only the 3x counts (D2).

**Post hoc audit** (`tools/analysis/`, `results/posthoc/`).
- **P1:** the three faults S1 detected alone come from one unit whose clean 1.4.6 lane is non-deterministic in 2 of 20 reruns.
- **P2:** 806 changed items were rerun on their clean builds in 20 more interpreters. 12 are flaky on the clean build.
- **P3:** 64 of the 71 faults changed no output on any item.
- **P4:** the probe takes 73% to 76% of checking cost and adds no detection.
- **P5:** at the change level, S5 exposes 7 faults and S0 none.

**Status of these findings:** they inform the design of a next registration and decide nothing in R4.
