# L5 relation-provenance reference: G decision request

**Status:** author proposal pending G; not a ruling, implementation approval, acceptance, or closure. `closure_ids: []`. No product files changed.

## Decision and recommendation

Does `L5SchemaRegimeScopeRelation.relation_provenance_ref` identify owner-custodied provenance bytes that must resolve before supporting an acquisition/source claim, or is it only an opaque declaration that remains unresolved? Current code deliberately chooses fail-closed unresolved behavior. G should settle whether that is the whole intended meaning or whether a producer/bridge is missing.

**Recommendation:** keep the existing refusal. Treat relation declaration and owner-snapshot membership as declaration-level evidence only; do not infer resolved provenance, completeness, authenticity, currentness, or authority. If an owner supplies exact bytes at the old ref, reuse them through the existing L5 owner and strict reader. If no such payload exists or the ID is not content-addressed, use a genuinely versioned identity and leave historical refs unresolved. Never change only the codec or rewrite old production records.

## Original route and callers

At source cut `3991d7c113090fab17a8374588c1a772964c9dc9`, current executable-queue reconciliation routes V3, “Source-driven same-candidate reissue and acquisition,” through B09, B12, B27, B28, and LA-046. This proposal covers only the L5 reference boundary encountered in that route; it closes none of those occurrences. B09 is the closest original criterion: change owner source content for the same candidate, rerun, then vary ID/UUID/order/write-time only and prove no reissue.

Observed route: `tests/_helpers/acquisition_epoch_production.py::production_admission_inputs` supplies an isolated owner repo and L5 registries; `tests/integration/core_runtime/test_acquisition_world_growth_chain.py::_admit_served_wdi_projection` invokes the served route; `load_l5_catalog_authority` parses the L5 scope file; `L5EpochBoundaryOwnerAdapter.resolve_complete_batch` persists the owner results; `_resolve_selected_reference_graph` consumes selected typed refs. Existing `test_real_l5_owner_rows_and_registry_files_round_trip_through_cas` pins the current negative: registry/regime rows resolve, relation-provenance ref raises `no registered content resolver`.

## Source frame and evidence

Source frame: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, HEAD `0be2acdec09f4d4c224602bbad052bc6fe507cbe`, tree `190a14043e2ae1619b0f72430399c2917900e41a`.

- `src/polisyos/core/contracts/epoch.py` `64528b1c…`; `runtime/quality/semantic_epoch.py` `fbc6e829…`; `runtime/quality/substrate_registry.py` `487f88a2…`.
- Selected registry `architecture/policy_design_case/layer3_gy_l5_schema_regime_scope_registry.json` `eaba4682…`; canonical negative test `tests/unit/runtime/quality/test_semantic_epoch.py` `5e447811…`; route fixture helper `tests/_helpers/acquisition_epoch_production.py` `6a5e0331…`.
- Full pins and source-cut references are in the accompanying `manifest.json`.

The selected registry has two distinct temporal rows (`ukraine_schema_v1` and `_v2`) sharing `sha256:b35defc2e3214b6baf41ed33e2fff808639059cb0f0ba31d56125765e74548ca`. The ref differs from the whole registry digest `sha256:eaba4682…` and each row’s canonical-JSON digest (`sha256:1c0cfcd2…`, `sha256:ebee13a4…`). `load_schema_regime_source_artifact_bytes` returns exact bytes for the owner’s regime and scope registry files only. The L5 adapter persists those files, owner snapshot, regime rows, receipt, and projection, but no standalone payload at `b35defc2…`.

The bounded direct-graph probe input/freeze/result/stdout/stderr are pinned in `manifest.json` and under `raw/v3-same-candidate-source-discriminator-r4-direct-graph-20261017/`. It walked 49 typed refs and completed 107 CAS reads without read errors, then returned `None` at `semantic_epoch.py:607` because `epoch.py` registers this relation kind as `application/json` / `unresolved_reference`. This is an explicit refusal, not a traversal or decode error, and is not a full served V3 acceptance.

Denominator: `git ls-tree -r --name-only HEAD` counts 2,782 tracked Python files in `policy-engine/src` and 3,067 in `policy-engine/tests`; `git grep -n -E 'relation_provenance_ref|l5\.schema_regime_scope_relation' HEAD -- policy-engine/src policy-engine/tests` finds only the typed model/codec, two reader role maps, relation grouping, and test fixtures/assertions. Exact ID search finds `b35defc2…` only in the two selected registry rows. This bounds tracked source/tests and that selected registry, not all external or untracked artifacts.

## Evidence planes and gate classification

| Plane | What current code proves | What remains unestablished |
| --- | --- | --- |
| Declaration | Typed rows and shared ref are present in selected registry and owner snapshot. | Whether the ref denotes payload bytes or a logical key. |
| Evidence | Registry/snapshot bytes are owner-loaded and hashed. | Target payload at `b35defc2…`; target issuer/provenance. |
| Emission | Adapter stores registry files, snapshot, regime rows, receipt, projection. | Separate relation-provenance artifact. |
| Verification | Snapshot membership and denominator hashes are recomputed. | Ref-to-target binding, target schema/profile, target time/currentness. |
| Claim | Existing graph consumer refuses unresolved ref. | Any positive provenance/completeness/currentness claim. |

For P37, snapshot membership is `recomputed`; ref-to-target binding and target authenticity/currentness are `not_established`. The declared `visibility_knowledge_from` and `purpose_admission_from` values do not establish the target’s publication, valid time, issuer, or currentness. For P38, a marker/hash-only gate would diverge: the embedded row is present and hash-bound while the target ref still cannot resolve.

Current positive-capability labels: `producer_missing` (target payload), `bridge_missing` (owner-backed resolver), `verification_missing` (fresh resolved consumer); a positive semantic test is `semantic_test_missing`. The existing fail-closed negative test is present and valid.

## Alternatives

1. **Reuse old ref:** if the genuine owner supplies exact bytes and proves how the old ID is issued, reuse it; add no declaration-derived alias.
2. **New versioned identity:** if the old ref has no payload or is a logical key, introduce a distinct typed/versioned ref and migration policy; old records retain unresolved meaning and bytes.
3. **Extend the L5 resolver:** after option 1 or 2 and G’s meaning decision, wire exact owner bytes through the existing L5 adapter and fresh graph consumer. No “embedded row means resolved” shortcut: the ref is neither row hash and is shared across different rows.
4. **Preserve refusal (recommended now):** no semantic or source change until the owner packet exists; do not claim provenance-dependent completeness from ref presence.

## Minimum supplier packet and next check

Require the actual source owner/API; exact raw target bytes and recomputed digest; whether the ID is a digest or logical key; artifact kind/media/schema/canonical profile; scope and regime binding; provenance/issuer evidence; separate publication, valid, visibility, and purpose-admission time roles; currentness limits; and missing/malformed/foreign/stale behavior. Synthetic fixtures may test plumbing but cannot stand in for external authority, legal truth, or currentness.

After G chooses meaning and the packet is available, run real owner → typed payload → exact CAS bytes/profile → L5 adapter → fresh graph reader. Test valid resolution and missing, malformed, wrong-hash, same-ID/different-bytes, foreign-scope/profile, and time-mismatch controls; preserve the current negative and remove-the-resolver control. Until then, keep the dependent claim limited/refused.

Pattern pass: P01/P02, P04/P05, P07/P08, P10/P14, P29/P32/P33, P35/P36, P37/P38, P40. This is the existing owner-reference/custody class widened across this field, not a new per-ID finding. Do not decide law, external authority, validity, or currentness here. B09/B12/B27/B28/LA-046 remain separately governed; `closure_ids: []`.
