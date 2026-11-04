# Registration record R5 (not frozen)

- **Approved:** the authors approved the claims of `PREREGISTRATION_R5.md` on 2026-11-04.
- **Pushed:** commit `44b2f482137fc22851b18eea28cf56ab53873a9b`, committed 2026-11-04 09:27:34 UTC and visible on `origin/main` by 2026-11-04 09:35 UTC, before any R5 session ran.
- **Frozen files:** `PREREGISTRATION_R5.sha256`, SHA-256 `d2942dfd938d7f3325327b89df1994bc9214eb04a758f634efd49fbebbbbfab0`. `python tools/freeze_r5.py --check` verifies them. R4's manifest is unchanged (`python tools/freeze.py --check`).

## Kaggle datasets (SHA-256 of the uploaded zips)

| Dataset | SHA-256 |
|---|---|
| r5-code | `7858fb779539e38e56b8e1c83e17047df8925fb6dcfb351f051df380b4cd8e4f` |
| r5-deps | `eca1945f2c698f2a1c8d308a70979c5d2c456783d9f1c59ff7614bfde0e0de3b` |
| r5-base-1.1.2 | `8a6872009e48fd796aa3fe7c153fd0da74a51cddc6dfb6e76e69a2dc2bb8da94` |
| r5-base-1.2.4 | `fdb56642c03837ccba2e27a7eb580659ed5f2b80d79342ce58a803624d94b313` |
| r5-base-1.3.3 | `6fc2d48ed32b1208a823b093bb8bbb7b63e5dacfb935d52d25395d49b3c0d5d8` |
| r5-base-1.4.6 | `df218939bf94b231658e1748c39bdfa85b056a31a51e37f9555349292e1001bc` |
| r5-base-2.0.3 | `4ee1ccc22e5b0eeb199eb968cc28ec3f93fa184f86bc8302882172925fc030c9` |
| r5-base-2.1.2 | `932aceb399e8150220505887cfcb367a4346b6360d64caac6104ffaed6cb9587` |
| r5-base-2.2.3 | `cea03f597d13a0b80589d7895b77ee5bb796ce360817ab964c2a396ee491c4e1` |
| r5-base-2.4.2 | `b717a5fe7f440b57794843af034792b1bdb49ce270bd5455e565a83a701c8de8` |
| r5-base-2.5.2 | `afd45bb8f3b031fa523ce43c5f05d4aa9493be7f15a9c38dadc5e50673196cfc` |

`r5-code` holds this repository's R4 and R5 code, its data, and cart's code at commit `198c867`. Both manifests check inside it.
