# Independent review: C CAN-01 JSON-mode Mapping delta

## Decision

**Bounded GO** for the candidate's IR JSON-mode Mapping reader property. The change makes a JSON-decoded `CanonInfo` Mapping (whose `separators` field is a two-string list) readable through the strict typed profile path before payload bytes are fetched. The existing cross-Core/IR canonical-profile finding **LA-021 remains HELD**; this slice does not establish its full closure.

This is the same profile-intake mechanism class as the earlier Mapping failure, one representation deeper (P40), not a new class. The old failure is explained by unchanged source: the failing candidate at `55b45d9a5c95c3b773fc3b4d8679786b3993eb1e` and the C4 base `79cbb05c90026973a32022ca02c63877b2cde1a5` have the same `io.py` blob `bdf14cf60f3c6e832d43c8704c42e2bc3da9029d`, test blob `2459535b5ca22ea3ec4386ff130f744156bbf206`, and README blob `a30e07b874bf371a4917c0a3b20ae71bfd3170`. The candidate delta changes those paths and directly tests the previously failing representation.

## Immutable source identity and footprint

- Candidate source: `e3cb3fafc847b94a5d4b3adc03b814b4c711920c`, tree `2d27c9c182cf550088c5a8c072dc2f36df84e20d`.
- C4 source base / candidate parent: `79cbb05c90026973a32022ca02c63877b2cde1a5`, tree `e494bbace790b9e5d15e253ac4a4834479774318`.
- Committed intake receipt: `60b523c2d0e1a587f2f1d4b92a0ac9a89a1f49db`, path `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/C/current-canonical-json-mapping-20261007.json`.
- Receipt disposition is bounded candidate-only, `closure_ids: []`, with LA-021 explicitly held. The source delta is four paths, 130 insertions:

| Path | Delta | Candidate blob |
|---|---:|---|
| `policy-engine/src/polisyos/ir/artifacts/io.py` | +7 | `00a9b82ae827cae69acc2420ac887ae82802f5c5` |
| `policy-engine/src/polisyos/ir/artifacts/README.md` | +2 | `4972213bcffd1f117370d161dbbf21226631384d` |
| `policy-engine/tests/unit/core/artifacts/test_ir_adapter.py` | +107 | `eadf0f52778561418dd77e64945f084d855d4beb` |
| release fragment | +14 | `6ca6d2bbfac10afd73dd2c7d4d8af875329cb89b` |

The source change is narrow: copy a Mapping to a dict, normalize only `separators` when it is exactly a two-element list of exact strings into the tuple required by the strict `CanonInfo.model_validate(..., strict=True)` profile, then retain the existing profile name/version/depth validation and read ordering. It does not relax other profile fields or modify payload decoding/canonical byte generation.

## Property and independent discriminator

The defining property is that a real JSON-mode typed-manifest Mapping is admitted as the same strict IR canonical profile, without mutating the caller's Mapping, and only then reads the referenced CAS payload. The committed focused test wraps a real CAS manifest in a Mapping, uses its typed `CoreArtifactRef`, checks the JSON-mode list representation, asserts the Mapping is unchanged, and checks payload equality plus exactly one manifest and one byte read. Negative cases reject malformed separator lists and malformed/missing/extra profile fields before payload access.

Independent evidence at the exact candidate is substantive rather than marker-based: the recorded probe writes and reads a real depth-129 artifact through `FileSystemCAS`, binds the typed `CoreArtifactRef`, supplies the full `ArtifactManifest.model_dump(mode="json")` Mapping and exact profile, and checks byte equality, no Mapping mutation, and one manifest/one payload read. It reports 19 strict-negative variants refused before a payload-byte read. Its removal control executes the exact candidate module with only this Mapping normalizer removed while leaving marker files in place; the valid Mapping then fails before bytes are read. This distinguishes runtime behavior from source strings (P29) and names the old proxy/property gap (P38): before the patch a marker and an otherwise valid typed manifest could still leave the JSON Mapping unreadable.

The source receipt records the author's frozen selector as 46 passed, 0 failures/errors/skips (18.212 seconds) and a focused independent selector as 14 passed, 30 deselected (0.14 seconds). These are receipts for the exact source, not tests run during this review. The prior G receipt at `83e7c0e934d0b40644dec8a24264a0602ef013e7` records the earlier JSON Mapping failure against the unchanged pre-fix source; its read probe observed zero payload-byte reads. Together these support acceptance of this bounded fix, not broader codec equivalence.

## Consumers and compatibility

The function signature and call sites are unchanged. Direct imports of `polisyos.ir.artifacts.io.get_json_artifact` at the candidate include `fabric/entity_resolution/store.py`, IR analytics `dependence_structure.py`, `microsim_calibration.py`, `mobility.py`, `survey_quality.py`, and `ir/governance/phase1.py`. Existing package exports and callers continue to resolve the same function; no consumer migration is needed. This does not fix the separate Core writer path that can persist profile values IR does not admit.

The changed implementation is inside `polisyos.ir.artifacts.io`; the repository public-surface contract marks `polisyos.ir` stable and lists its supported entrypoints separately. Treat the delta as an internal helper behavior repair, not evidence that every internal submodule is independently promised as a stable public API.

## Limits and follow-up

- **LA-021 remains HELD.** The Core/IR supplier/profile boundary is not ratified or verified end to end. In particular, Core `put_json` can emit a `float_hex` representation under a profile name/version that IR rejects; this slice does not change that writer or establish a shared profile contract.
- Historical profile-less payload compatibility/readability is not established. Do not claim persisted-data migration or broad old-payload support.
- The recorded installed-wheel check is **UNRUN** because the offline environment lacks a cached compatible Hatchling build dependency. Source-level acceptance does not establish installed-wheel module origin or packaging behavior.
- The production invocation diagnostic in the receipt is not candidate-bound evidence and is not counted as a pass.
- No production data is required for this bounded reader property. Do not run a broad replay solely for this change.

If packaging closure is required, the smallest useful check is an offline wheel build/install when the pinned builder is available, followed by an installed-origin assertion and the focused JSON-Mapping positive, strict-negative, and exact-byte CAS readback selectors. Include provenance that imports resolve to the installed wheel rather than the checkout. If Hatchling remains unavailable, retain `UNRUN` as a tooling limitation. Full LA-021 needs its separate canonical profile/writer owner to define and verify the supported cross-boundary profile, including the Core producer path and historical compatibility decision.

## Review scope

Reviewed the exact committed receipt and full relevant source, README, release note, test additions, prior Mapping failure evidence, independent actual-CAS oracle/removal control, and named consumer imports. No tests, installs, environment setup, source/ref changes, or tracked-file changes were made for this review.
