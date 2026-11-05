# Revealing real Qiskit compiler faults: registrations R4 and R5

**Archived release:** v1.0.0, Zenodo [10.5281/zenodo.23988421](https://doi.org/10.5281/zenodo.23988421). Cite this DOI for the R4 and R5 registrations, code, data and post hoc analyses.

Status: **registration R4** (`PREREGISTRATION_R4.md`, frozen files listed in `PREREGISTRATION_R4.sha256`). No R4 session had run when it was pushed. The held-out faults were built, but none had compiled a corpus unit or been seen by any check.

**Results** (2026-11-02): `RESULTS_R4.md`. The primary claim A4 is not supported (4 to 0 on pool F, p = 0.0625). Claims B4, E4 and F4 are supported. Deviations: `DEVIATIONS.md`. Post hoc analyses, which decide nothing: `RESULTS_R4.md` Part 2, `results/posthoc/`, `tools/analysis/`.

## Purpose

Registration R3 (in [furqan-nr/cart](https://github.com/furqan-nr/cart), commit `198c867`) re-injected 15 real Qiskit bugs and revealed none of them, although every bug's changed code ran on the corpus. This repository tests the remedy that the R3 diagnosis suggests:

1. a corpus generated to cover **input features** (gate kinds, blocks, parameters, angle classes, structure, options), not only code;
2. **pass-level test units** beside end-to-end compilation;
3. a new registration, R4, on real faults never used in R3 or in the design.

## Relation to cart

The checks (output, quality, statevector probe, contract, determinism lane) and the selection strategies are imported from cart at commit `198c867`, unchanged. They are never copied or edited here.

## Layout

| Folder | What |
|---|---|
| `results/` | registered analysis output, per-fault rows, session map, and `posthoc/` |
| `reveal/` | the package: feature model, corpus generator, pass-level units (in development) |
| `selection/` | held-out fault pools: `mine_pools.py` and its output `pools.json` (ids, commits and dates only) |
| `builds/` | how the clean Qiskit builds are made, and their hashes |
| `docs/` | `DESIGN_LOG.md`: every design decision and everything known before registration; `dev/`: development observations on R3's faults |
| `kaggle/` | the session notebook and the code-zip script |
| `tests/`, `tools/` | the cross-version identity test and the freeze script |

## Held-out faults

`selection/pools.json` lists the held-out faults by pull-request number. **Do not open these pull requests, their patches or their tests before registration.** Doing so would have to be disclosed and weakens the held-out claim.

## Registration R5

`PREREGISTRATION_R5.md` (frozen files in `PREREGISTRATION_R5.sha256`, written by `tools/freeze_r5.py`). R5 tests a suite that reaches more of Qiskit's public compilation interface and more kinds of input, on 52 new held-out real faults from nine Qiskit versions. Its files sit beside R4's, which are unchanged:

| Path | What |
|---|---|
| `r5/` | input model (`gen5.py`), item catalogue (`items5.py`), session driver (`session5.py`, `worker5.py`), registered analysis (`analyze5.py`), compatibility for older Qiskit (`compat.py`) |
| `data/suites_r5.json`, `data/pools_r5.json` | suites, and the fault and benign pools without titles |
| `selection/mine_r5.py`, `selection/mine_benign.py` | fault-blind mining |
| `builds/kaggle_build.py`, `builds/make_wheelhouse5.py`, `builds/split_deps.py`, `builds/records/build_*.json` | builds and their records |
| `kaggle/nb_r5_session.ipynb` | the session notebook |
| `docs/DESIGN_LOG_R5.md`, `docs/dev/` | design log and development evidence |

## Errata and post hoc validation

`ERRATA_R4_R5.md` corrects and qualifies statements in the R4 and R5 reports, after an independent review of the code and data. No registered decision changes. It also reports post hoc validation:

| Path | What |
|---|---|
| `tools/analysis/validate_fix_tests.py` | runs each fault's own regression tests on the clean and fault builds |
| `tools/analysis/posthoc_r5.py` | detection channels per fault, the failed-fingerprint sensitivity, validation joined to detections |
| `tools/analysis/rerun_detecting_items.py` | reruns detecting items clean and fault, with the exception and Qiskit frame |
| `tools/analysis/overlay_audit.py` | checks that no evaluated fix adds, deletes or renames a compilation file |
| `tools/analysis/r4_strict_exposure.py` | R4 exposure with every clean-unstable item excluded |
| `results/r5/posthoc/` | R5 outputs of the above |
| `results/posthoc/fix_test_validation_r4.json`, `overlay_audit.json`, `m05_strict_exposure.json` | R4 outputs of the above |
