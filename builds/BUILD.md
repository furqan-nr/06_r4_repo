# Clean Qiskit builds

As in cart's R3 (`r3/BUILD.md`): Qiskit's release profile, default features, stable `rustc 1.97.0` (the repository's pinned toolchain is overridden with `RUSTUP_TOOLCHAIN=stable`), Python 3.13, x86_64 Linux. Command, run in a copy of the tag's source tree:

    RUSTUP_TOOLCHAIN=stable pip wheel --no-deps --no-build-isolation .

| Base | Tag | Use | Wheel SHA-256 |
|---|---|---|---|
| 2.6.1 | `2.6.1` | pool B, as R3 | in cart `r3/wheelhouse.sha256` |
| 1.4.6 | `1.4.6` | pool C24 | `8c8df09b9d638aa82e4b24f2c2d51916ed27d21f9139c5e229209a72b4fc249b` |
| 2.3.1 | `2.3.1` | pool A231 | `81a9a23c10f080c420e40dacd42ab0ddfb2e1a3d6b721cd168ad8438c91aac37` |

**Packaging tools.** Current setuptools rejects the packaging metadata of both older tags, so each is built in its own environment, with no build isolation:
- 1.4.6: setuptools 74.1.3 and setuptools-rust 1.10.2;
- 2.3.1: setuptools 80.9.0 and setuptools-rust 1.11.1 (its `project.license` needs setuptools 77 or later).

These tools only package the wheel. The Rust compiler, profile and features are the same as R3's.

**Check against PyPI (2026-10-31, `PYTHONHASHSEED=0`).**
- 2.3.1: our build gives the same fingerprints as the PyPI wheel on all 116 R3 units and all 63 feature units.
- 1.4.6: our build gives the same fingerprints on all 116 R3 units. Three feature units with an rzz basis differed between runs. Repeated runs showed that the PyPI wheel gives the same two alternative results, so this is non-determinism of clean Qiskit 1.4.6, not a build difference. These checks must be repeated on the frozen corpus.


## Session builds (the builds every R4 session uses)

The first 1.4.6 and 2.3.1 wheels above were checks of the toolchain. The wheels the sessions use come from `builds/make_faults.py`, which builds the clean wheel and every fault in one isolated pipeline per base, so that each fault library pairs with the clean build it came from. 2.6.1 is built the same way (R3's 2.6.1 wheelhouse is not reused).

| Base | Pool | Clean wheel SHA-256 | Null check | Faults | Import check |
|---|---|---|---|---|---|
| 1.4.6 | C24 | `fdca9548fd2866c924e0019704e5d0191876e7e6d5319f45aa616f3437738a18` | passed | 24 | 24 of 24 |
| 2.3.1 | A231 | `1b65b1e9ae111a21695ebd0be85d9ad83ba37e5f7638b2b8121499bc3754ec05` | passed | 11 | 11 of 11 |
| 2.6.1 | B | `6fc6bbf8cfb05daf0a50e6110ca4d736bd3cfa17a7a7cf064e65c9a06a28219a` | passed | 36 | 36 of 36 |

- **PyPI check:** each session clean wheel compiles all 116 R3 units and all 357 feature units to the same fingerprints as the PyPI wheel of the same version (473 of 473 per base, `PYTHONHASHSEED=0`).
- **Records:** the overlay hashes, patch hashes and import checks are in `builds/records/build_<pool>.json`.
- **Patches:** the patches themselves stay outside the repository until the registered results exist.
