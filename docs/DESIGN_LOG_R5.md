# R5 design log

Every step of R5's design, in order, with what was known at the time. Not frozen: it keeps growing.

## 2026-11-02: after R4's results were final

1. **R4 fix tests** (`docs/dev/r4_fix_tests/`): each R4 fault's own regression tests (the test files its fix changed) ran on the clean build and on the fault build.
   - **Outcome:** 56 of 71 faults have a test that passes on clean and fails on the fault build. 11 have none, and 4 fixes added no test.
   - **Classification:** the trigger tests were read and classified (`docs/dev/classification_r4_faults.json`): 26 compilation faults, 14 gate-semantics faults, 16 other.
2. **Prototype round 1:** R4 replicate 1 (F0, 60 units) with every public pass, synthesis plugins, option variants and pass-manager reuse, on the 40 compilation and gate-semantics faults. Development runs only (`docs/dev/prototype_dev_runs.json`).
   - **First problem found:** standalone layout passes gave varying outputs, and five clean runs did not catch this. A 20-run clean screen was added.
3. **Prototype round 2:** one covering array of the new input dimensions (seed 20261201) on the faults round 1 missed.
   - **Problems found:**
     - `QuantumCircuit.repeat` named its instruction from a process-wide counter, which made units depend on the interpreter's history. Circuits are now named explicitly.
     - Some items differed under every fault, an artifact of the fault-site setup. A null control was added: clean Qiskit through the same machinery.
   - **Combined, after the screen and the null control:** 9 of 40 detected, 15 exposed. R4's suite on the same 40 faults: 4 detected, 6 exposed.

## 2026-11-03: fresh faults and builds

1. **Fault pools** (`selection/mine_r5.py`): 52 faults on nine bases, mined and built by scripts that print counts only. No title, patch or test was displayed.
2. **1.4.6:** built on the development machine. Its clean build is file-identical to R4's 1.4.6 build.
3. **Other bases:** built on Kaggle with `builds/kaggle_build.py`, which imports R4's `make_faults.py` unchanged and pins the Rust toolchain.
   - **Toolchain fallback:** Rust 1.97.0 cannot compile a dependency of 1.1.2 and 1.2.4 (crate `ra_ap_stdx`). Those bases use the toolchain the release pins (1.70).
   - **Kaggle environment:** Kaggle's Python lacks `ensurepip`, so the build uses `virtualenv`.
   - **Checks:** every base passed the null check, all 52 faults import, and the 1.3.3 builds on Kaggle and on the development machine are file-identical.
4. **Benign events** (`selection/mine_benign.py`): 2 per base.

## 2026-11-04: method and rehearsals

1. **Item catalogue:** every public pass class, with a lowered input for layout, routing and scheduling passes.
2. **Clean Qiskit 2.6.1 panic:** while sizing the suites, clean Qiskit 2.6.1 panicked ("parameter table is in an inconsistent state", in `assign_parameters`) on every item of development unit G20261202.3. The unit fails on clean, so the validity rule drops it.
3. **Rehearsal on base 2.4.2** (small item subset, 1,734 items, of which 1,272 run on clean). It ran 2.4.2's 4 held-out faults, its 2 benign events and the null control.
   - **First run:** about 40 items differed under every event, the null control included. All were standalone layout and routing passes (SabreLayout, SabreSwap, VF2Layout, CSPLayout), which draw a random seed or use a wall-clock limit.
   - **Fix:** standalone passes now get the unit's transpiler seed, and time limits are off.
   - **Second run:** 2 to 5 items differed per event. All were flagged by the clean screen, so after the exclusions no item differed under any held-out fault.
   - **Disclosure:** this is disclosed as contact with held-out faults. Later rehearsals used only development faults, the null control and benign events.
4. **Rehearsal on 1.1.2** (null control and benign events only):
   - **Requirements file:** the wheelhouse requirements named the Qiskit wheel by its file path, which pip resolves from the working folder. It now pins `qiskit==<version>`.
   - **Compatibility shim:** Qiskit 1.1 and 1.2 export `generate_preset_pass_manager` only from a submodule. `r5/compat.py` adds it under the newer name before frozen code is imported.
5. **Rehearsal on 1.4.6** with R4 development fault #13067: exposed and detected (quality alarm) by S5 after the exclusions.
6. **Size:** a full clean pass of all suites on 2.4.2 (137,657 items) took 1,353 s on two cores.
