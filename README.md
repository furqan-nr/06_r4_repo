# Input-feature coverage and pass-level testing for quantum compiler regression tests

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
