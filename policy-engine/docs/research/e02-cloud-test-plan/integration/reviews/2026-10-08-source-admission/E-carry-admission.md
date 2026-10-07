# E bounded code-carry admission — 2026-10-07

**Recommendation: GO to carry the E source history as a candidate by an ordinary, non-squash merge, with G `dac9d700fe684d5b4c0ae3fbcff66f5d05b2f6f2` first parent.** This is a reviewer recommendation for bounded code integration, not G's formal source-acceptance record, a finding closure, or a scientific/policy authority claim. Keep the original E history intact.

## Immutable identity and carry scope

E candidate `8d8e7b319e7eb6b57bc4ab3c4db5ca3070393f8c` has tree `192e584c646ee6df303b8793e7b92aa741dcaebb`; it descends from the earlier reviewed E root `b2f2f65ea8884a6e2ffa3fc444cdf4bbb9157641` and `df5258b7ddfade5b952e3b21ef28116ced40fa68`, but is not yet an ancestor of G. G and E share `75ccf4dd211ad7fffa9430a84848b59d5ebf0886`. The full G-base-to-E-candidate `git diff --name-only` set is **8,718 paths**: 68 under `policy-engine/src/` (55 `.py` plus 13 non-Python), 67 under `policy-engine/tests/` (59 `.py` plus 8 non-Python), 34 release fragments, and 8,547 paths under E implementation handoffs. The complete extension distribution is recorded in the adjacent JSON. This is the denominator for the whole original-history carry; nested `.py.txt` postimages remain handoff evidence, not product source.

The post-b2 delta is 901 paths: two runtime Python files plus the IR README, three IR test files, one release fragment, and 894 handoff-evidence paths. There is no changed handoff JSON in the 8d delta. The full b2 source set is preserved through E history; prior evidence is slice-bound in the G review set and E handoffs, not collapsed into one package PASS. The latest delta changes two runtime Python files for raw Profile2 admission and multi-profile join behavior, with the adjacent scalar diagnostic conversion bounded as documented in `E-delta.md`.

G changed 198 paths since the same common base; the complete Git path intersection with E is zero, and G changed no `src/`, test, or release paths in that interval. The shared V11 executor remains blob `fe0aadf975873aa54d35008d5020b66c6c6778fa` at the common base, E candidate and current G. A normal merge therefore has no source/test path conflict in this intake. After merge, read back the five changed runtime/test blobs against the exact 8d tree before reusing the candidate receipts.

## Exact new property evidence and prior coverage

G's independent current receipt binds 8d/tree `192e584c` and runs exactly `test_uncertainty_profile_ingress.py`, `test_posterior_summary.py`, and `test_uncertainty_posterior_composition.py`: **165 PASS, 0 failures, 0 errors, 0 skips**. The full JUnit SHA-256 is `fe15ea3cd25055dce1262123287816995731098cab96e64c888ba732a2109c4d`; runtime stdout is `2dd2622599a0ff937604a6aea5bc42089ec265642b8da65ddda4b85c08a64bbe`; run receipt `c2753a7e7575064ad31fd3e3ec0afc92ec717c22fc163bceaa978aeaccba721e`; parent receipt SHA-256 `1ae333e4c6ab2b9d885618b09e6325d4d3f27bd733417ceb13df2fa3243807bf`. It is a focused candidate-bound unit wave, not broad regression, fit replay, backend/data replay, or closure.

Reuse only the scoped prior evidence on unchanged blobs: `E-posterior-math.md` and `E-law-composition.md` support the finite binary64-ratio law and already-admitted Profile2 transformations; `E-fit-inlet.md` records the bounded synthetic configured HMC/NUTS→CAS→Node path and its 28 normal, 28 optimized, and 23 consumer receipts; `E-native-diagnostics.md` records the real legacy raw-CAS bypass and lossy join that the 8d delta now repairs; `E-API.md` identifies the still-missing generated public companion. These are candidate-specific receipts and reviewer scopes, not a single full-head PASS.

## Remaining dependencies and the smallest next checks

The code carry is supportable while two cross-owner boundaries remain explicit:

- **Generated Profile2 ABI and inventory (`surface_missing`, G-owned):** the Profile2 facade/schema declarations exist, but the candidate does not contain the generated v2 snapshots/manifest, and the inventory/reference remains stale. After source freeze, use the canonical G writers: `uv run --extra ml polisyos-tools diagnostics gen-schema`; `uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline`; then `uv run --extra ml polisyos-tools diagnostics gen-schema --check` and `uv run polisyos-tools architecture guardrails check`. Verify both Profile2 snapshots and all four facade exports. Do not hand-edit generated files.
- **Canonical float-tag fit input (`verification_missing`, Scientist writer with G/B coordination):** E did not change `scientist/compute/runner.py::_load_input_refs`; the configured HMC/NUTS fixture is integer-valued. After the canonical Core decoder is applied, the smallest witness is the existing configured `run_job` path on finite float-tag feature/target CAS refs plus malformed-tag and source-kind/view mismatch controls that assert no evaluator/envelope publication. This is a separate input-materializer dependency, not a reason to block the bounded E carry or to require production data.

B194/B197 real evaluator/model/fit inputs remain owner-specific held evidence, and the nine E limited proposals remain limited. Neither changes whether this generic implementation can be carried. The new 165-case PASS resolves only the changed raw-ingress/join behavior at exact 8d; it does not close B201/B202 or establish source-law, sampler, noise, or policy authority.

Preserve the current G first parent and merge E history normally; do not squash/cherry-pick as a history substitute, rewrite E, or publish to `main`. No Git refs, source, tests, or tracked files were changed for this read-only review.

## Evidence pointers

- Exact native receipt: `policy-engine/_build/e02-g-continuation-20261006/R/next-intake-20261007-2018/native-E/native-receipt.json` and `native-E/results/runtime/{junit.xml,stdout.txt,receipt.json}`.
- Prior G review set: `integration/reviews/2026-10-07-thirteenth-wave/{identity.md,owners-companions.md,E-posterior-math.md,E-law-composition.md,E-fit-inlet.md,E-native-diagnostics.md,E-API.md}`.
