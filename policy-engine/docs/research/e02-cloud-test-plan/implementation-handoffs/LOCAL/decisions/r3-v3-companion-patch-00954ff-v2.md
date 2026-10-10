# R3/V3 test companion patch v2

Prepared as an unapplied, patch-only companion for base 00954ff836642ca3c2dca4032fcd1b83019bdfd0 (tree cf422a9a79c3ffd43bd09817edbcd806db1d7570). No source/test target files were modified and no tests were run. This v2 replaces the R3 verifier approach rejected in v1 while preserving the reviewed V3 fixture/history companion.

Patch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r3-v3-companion-patch-00954ff-v2.patch`
SHA-256: `460973918615c8f59dfdf7973e317c29b5d408d0118de4718f430b5d0fec50da`
Bytes: 10385

Exact target pre-patch SHA-256 values:

- `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py`: `ab6cbd59aef5c43a02fbdbe1daba64cf4633279b7e4b22adf0dcaba6829a9388`
- `tests/_helpers/acquisition_production.py`: `a01e4b527be21135abfaf4d07b4d77c538431937346cbabef09c3e7b4a2b14d3`
- `tests/integration/core_runtime/test_acquisition_authority_served.py`: `7430db9ece5f564c81d09b5e2d862fd1ac810fce7bca3b06e3bb535e0dc8c0d9`

The in-memory post-patch hashes are:

- `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py`: `8e905902c436706e8232f83f276e32db1fd2df94dbcd9a4ade6bed7c005ec074`
- `tests/_helpers/acquisition_production.py`: `b3d6d8f8aa6a666d33ff56aa284a3499e45cd677f965e7c686bb947d983d1806`
- `tests/integration/core_runtime/test_acquisition_authority_served.py`: `73991b22a09d76f0135a5b1f87f039430e4af2e13a92cf0364acc807df9927c4`

## R3: reuse the canonical strict identity verifier

The v1 patch's bespoke local manifest/envelope projection is removed. The existing real owner `verify_runtime_authority_artifact_identity` is imported and called inside the test's actual `_run_blocking_with_sibling_manifest` wrapper for every real `write_runtime_authority_artifact` invocation. The call uses the original producer store and `ArtifactWriteOptions`, the actual returned `result.cas_ref`, and the producer-returned `result.identity_context`; the returned CAS ref, selected envelope ref, and identity context must equal the producer result. This exercises the complete canonical readback owner against actual producer artifacts instead of enumerating a test-only subset of fields.

The witness retains all actual resolved refs, including the observed six valid profileless/default views and the first explicit profile-bound view. A foreign sidecar is created with a distinct profile, foreign tenant/cell, no producer/governance/closure, and deliberately incompatible schema. The test then changes only the root artifact's persisted authority-link view in a minimal read adapter and asks the canonical verifier to resolve that sibling profile; it must refuse the selected wrong-schema sidecar. A second falsifier substitutes the actual wrong-schema default view under the same root authority link with the profile removed; the canonical verifier must refuse that default resolution too. The unmodified producer result is always verified before either negative control, so a fabricated link cannot serve as the positive.

P38: v1's unconditional selected-profile requirement rejected legitimate profileless/default views. P40: same class, deeper whole-identity resolution; v1's local field list was a second instance-sized oracle. This patch reuses the source-of-truth verifier for actual positive readback and wrong-link/default controls. No authority or producer semantics change.

## V3: preserve the approved served-history companion

The fixture's compiled-cycle artifact receives `tenant_context` only from its already-issued `admission.scope` when that scope is established; it does not use client-provided tenant/cell data. The fresh authenticated GET must expose the two matching persisted action-generation heads: generation 1 remains a quarantined no-growth observation with no reentry/candidate IDs, while generation 2 remains the actual completed reentry and selected N4 source. Both preserve `currentness_status=not_established`, `authority_purpose=candidate_observation_only`, and `publication_authority=false`; the separate unauthenticated `401/missing_bearer_token` check remains.

## Evidence limits

This patch has not been applied or tested. The earlier observed R3/V3 failure outputs remain at `LOCAL/raw/composed-mac-current-source-20261010/`; the source-bound observer and CAS/head readback remain at `LOCAL/raw/r3-v3-observer-wave-20261010/`. The exact observer stdin was not retained and is recorded as `not_established`; it was not reconstructed. Existing v1 artifacts remain preserved at `LOCAL/raw/r3-v3-companion-patch-00954ff-v1.patch` and `LOCAL/decisions/r3-v3-companion-patch-00954ff-v1.md`.

The capability demonstrated by this proposal is a test companion only, pending application and focused execution. It makes no claim of acquisition authority, candidate relevance, currentness, or publication authority.
