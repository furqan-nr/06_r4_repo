# Pre-registration R5: input and interface reach for revealing real Qiskit compiler faults

**Status:** draft for the authors' approval. This registration lives in the same repository as R4, beside it: R4's files and manifest are unchanged. Becomes a registration when this file and the files listed in `PREREGISTRATION_R5.sha256` are pushed, before any R5 session has run. Push times and the SHA-256 of every Kaggle dataset go into `REGISTRATION_RECORD.md` (not frozen).

**Authors:** Furqan Nasir (CUSIT and FAST-NUCES), Muhammad Arif Shah (CUSIT), Iftikhar Alam (CUSIT).

## 1. Why a fifth registration

R4 (this repository, `PREREGISTRATION_R4.md`, results in `RESULTS_R4.md`) tested a feature-coverage corpus with pass-level items on 71 held-out real Qiskit faults.
- **Registered result:** the primary claim A4 was not supported (4 to 0 on pool F, p = 0.0625). On all 71 faults the suite detected 5 and the R3 corpus 0.
- **Post hoc diagnosis:** 64 of the 71 faults changed no output of any item. The fixes' own regression tests showed why. The faults need inputs and interfaces the R4 suite never used: public passes outside the preset pipelines, compilation options, Targets with durations, reuse of a pass manager, gates built through `inverse`, `power`, `control` and `repeat`, and library objects inside circuits.

R5 tests a suite built to reach those inputs and interfaces, on 52 real faults that played no part in any design.

## 2. What is new

**Items** (`r5/items5.py`). Every unit of a suite runs as these items. Each family is enumerated from Qiskit's public interface on the base being tested.

| Family | Item |
|---|---|
| `TX default` | the unit's preset compilation (as R4) |
| `TX variants` | the preset compilation with one public option changed: a Target without coupling map, a Target with durations and ALAP or ASAP scheduling, a Target with error rates, a disjoint coupling map, dense or trivial layout, basic routing, synthesis translation, approximation degree 0.9 |
| `PX raw` | every public pass class in `qiskit.transpiler.passes`, alone, on the unit's circuit, with its required arguments filled from the unit's configuration |
| `PX low` | the same for layout, routing and scheduling passes, on the circuit lowered to the unit's basis and coupling |
| `HX` | `HighLevelSynthesis` with each registered plugin, for each high-level operation in the unit |
| `RX` | one preset pass manager run on another unit's circuit and then on this unit's |

Passes that need a preceding pass get it (a layout before routing, a schedule before padding). Standalone passes that take a seed get the unit's transpiler seed, and wall-clock time limits are off, so a result never depends on the run or on machine speed.

**Input model** (`r5/gen5.py`). R4's dimensions plus:
- **construction method:** plain, `inverse()`, `power(k)`, `power(-x)`, `control(1, ctrl_state)`, inverse then control, control then inverse, `QuantumCircuit.repeat`.
- **high-level object:** Clifford, LinearFunction, PermutationGate, QFTGate, parameterised PauliEvolutionGate, MCX, StatePreparation, and on bases that have them a modular adder, a multiplier, a phase oracle and a Pauli product measurement.
- **qubits:** one register, anonymous qubits, two registers.
- **parameters:** none, bound, symbolic, a reused expression family.
- **control flow:** none, if/else, for, while with break.
- **gate mix:** one gate group or all groups.

Each array is a strength-2 covering array (AETG greedy, as R4).

**Suites** (`data/suites_r5.json`).

| Suite | Units | Items |
|---|---|---|
| S0 | the R3 corpus (116 units) | `TX default` only |
| **S5** (proposed) | R4 feature corpus replicates 1 and 2 (119 units) and two R5 covering arrays (seeds 20261202 and 20261203) | all families |
| S1' | Qiskit `random_circuit` units of R4 (the first 800 of R4's S1 pool, in R4's order) | all families |

S1' is cut, in that order and by whole units, at S5's measured clean cost on the same base. S0 keeps its full cost, which is far below S5's.

**Checks and levels.**
- **exposed:** an item's output fingerprint lies outside its clean result set, or the item crashes or hangs where clean succeeded.
- **detected:** the item crashes or hangs where clean succeeded, or cart's output check (equivalence with the input) or quality check alarms on its output, under rule L1 (the check passes on the clean output).
- The probe, contract check and determinism lane of R4 are not used. In R4 they added no detection, the probe took 73% to 76% of all checking cost, and the lane raised false alarms (R4 `RESULTS_R4.md`, P1 and P4).

**False-alarm controls** (applied to every suite alike).
1. **Clean result set:** three fresh interpreters (hash seeds 0, 1, 2). An item with more than one clean result is excluded.
2. **Clean screen:** every item that differs under any event runs on clean Qiskit in 20 more interpreters (hash seeds 5 to 24). An item that ever leaves its clean set, or fails, is excluded.
3. **Null control:** clean Qiskit copied through the same fault-site machinery. Every item that differs under it is excluded.
4. **Benign events:** per base, two reverted commits that the project did not mark as fixes (no release note, no fix wording, compilation Python files only), drawn with a fixed seed (`selection/mine_benign.py`). Exposure and detection of them are reported as false-alarm rates.

**Hang rule:** an item that makes no progress for 120 s is a hang.

## 3. Held-out faults

Selection (`selection/mine_r5.py`): R3's rule steps 1 to 4, as R4, on every fix not used in R3 or R4 and not contacted in earlier work. Each fix goes to the newest listed release on which its patch reverts cleanly.

| Base | Window | Faults | Rust faults | Benign |
|---|---|---|---|---|
| 1.1.2 | 1.0.0 to 2.0.0 | 3 | 0 | 2 |
| 1.2.4 | 1.0.0 to 2.0.0 | 7 | 2 | 2 |
| 1.3.3 | 1.0.0 to 2.0.0 | 3 | 1 | 2 |
| 1.4.6 | 1.0.0 to 2.0.0 | 11 | 9 | 2 |
| 2.0.3 | R3 window | 4 | 2 | 2 |
| 2.1.2 | R3 window | 7 | 3 | 2 |
| 2.2.3 | R3 window | 7 | 4 | 2 |
| 2.4.2 | R3 window | 4 | 3 | 2 |
| 2.5.2 | R3 window | 6 | 4 | 2 |
| **Total** | | **52** | **28** | **18** |

**Builds** (`builds/`, records in `builds/records/`).
- **Script:** R4's `builds/make_faults.py`, unchanged: isolated fault builds, and a null build that must reproduce the clean wheel file for file. All nine bases passed the null check, and all 52 faults import.
- **Toolchain:** Rust 1.97.0, as R4. For 1.1.2 and 1.2.4, where 1.97.0 cannot compile the release's dependencies, the toolchain the release pins (1.70).
- **Where:** 1.4.6 was built on the authors' development machine. The other bases were built on Kaggle, and a Kaggle build and a local build of 1.3.3 are identical in every Qiskit file.

## 4. Disclosure: what is known before registration

1. Everything disclosed in R1 to R4, all their data, results and post hoc analyses.
2. **Development set:** R3's 15 faults and R4's 71. After R4's results were final, the fixes' own regression tests were run on R4's faults and read, and an R5 prototype was run on the 40 of them whose tests show a compilation or gate-semantics fault (`docs/DESIGN_LOG_R5.md`). On those 40, at about half of S5's size, the prototype detected 9 and exposed 15. R4's suite detected 4 and exposed 6. The prototype was designed after reading these faults' tests, so these figures are optimistic.
3. **R5's held-out faults:** their commit subjects in the R3 window were read for R3 (as disclosed in R4). No title, patch or test of any R5 fault was displayed or read for R5. The pools were mined and built by scripts that print counts only.
4. **Contact with held-out faults before registration** (`docs/DESIGN_LOG_R5.md`). A pipeline rehearsal on base 2.4.2 ran its 4 faults on 1,272 items (4 R4 units, 5 R5 units, 5 random units). After the clean screen and the null control, no item differed under any of them. The only design change after it (seeds for standalone layout and routing passes) was prompted by differences that appeared equally under every event, the null control included. All later rehearsals used only development faults, the null control and benign events.
5. **Clean-build observations:** clean Qiskit 2.6.1 panics ("parameter table is in an inconsistent state") on one R5 development unit (`docs/DESIGN_LOG_R5.md`).

## 5. Sessions

| Account | Sessions (one base each) |
|---|---|
| 1 | 1.4.6, 1.1.2, 1.3.3 |
| 2 | 1.2.4, 2.0.3, 2.1.2 |
| 3 | 2.2.3, 2.4.2, 2.5.2 |

- **Platform:** Kaggle, CPU, Internet off, `kaggle/nb_r5_session.ipynb`, the `r5-code` dataset and the base's `r5-base-<version>` dataset.
- **Contents:** each session runs the clean reference, then every event of its base in the order fixed by `EVENT_ORDER_SEED`, then the clean screen.
- **Benchmark rule:** as R3 and R4, a session whose reference benchmark drifts by more than 15% at any reading is rerun.

## 6. Claims (decided by `r5/analyze5.py`, frozen)

- **Pool:** all 52 faults pooled.
- **Test:** one-sided exact sign tests on discordant faults. With fewer than 5 discordant faults, p < 0.05 cannot be reached, and the claim is then inconclusive and counted as not supported.

| Claim | Statement |
|---|---|
| **A5** (primary) | S5 detects more faults than S0: p < 0.05 |
| B5 | S5 detects more faults than S1': p < 0.05 |
| C5 | S5 exposes more faults than S0: p < 0.05 |
| D5 | S5 exposes more faults than S1': p < 0.05 |

B5 and D5 are counted as not supported if S1' reaches less than 90% of S5's clean cost on any base.

**Reported without decision:**
- per-base counts.
- detection and exposure of the 18 benign events by every suite.
- the contribution of every item family and of the R4 and R5 units inside S5.
- the cost of every suite.

## 7. Forecast (registered judgement)

- **Fault mix:** in R4, 40 of 71 faults were compilation or gate-semantics faults by their own tests. About 29 of R5's 52 are expected to be.
- **S5:** expected to detect 3 to 8 faults and expose 5 to 12. The prototype's rates are discounted, because it was designed after reading its faults' tests.
- **S0:** expected to detect 0 or 1.
- **S1':** S1' gets the same items. Its random circuits lack the R5 input dimensions, but much of S5's development gain came from the item families, which S1' shares.

| Claim | P(supported) |
|---|---|
| A5 | about 0.5 |
| B5 | about 0.25 |
| C5 | about 0.75 |
| D5 | about 0.35 |

## 8. Deviations

As in R1 to R4. A deviation is reported with its reason. No result is reported without the registered analysis.
