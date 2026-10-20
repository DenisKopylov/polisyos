# LA-021: two bounded CAN decisions for G

**Status:** proposal only; not adjudicated, admitted, or closed. **Requested scope:** decide the persisted Core/IR canonical-profile identity law and the treatment of profileless historical JSON. Do not treat this as whole LA-021 acceptance.

## Decision requests

### LA-021-1 — what does `polisyos.canon.json@0.2.0` identify?

**Recommended choice:** the label identifies shared canonicalization mechanics/settings; Core and IR retain their contextual, strict tag allowlists. A matching name/version does not make every Core payload portable to IR. Preserve the current refusal at the narrow IR reader; do not widen IR, rename/version existing profile identities, rewrite CAS IDs, or change stored bytes on this proposal.

**Alternative:** require a persisted identity/version for each accepted tag family. This makes cross-reader grammar explicit, but changes the persisted-format contract. Before implementation, G must ratify the exact additive identity/schema and compatibility law. Preserve old references and bytes; demonstrate old/new writers and readers, byte/hash identity, and typed refusal for unknown or mismatched profile families. Do not infer the field name or create a migration default here.

**Concrete discriminator:** a real `FileSystemCAS.put_json` writes `{"_type":"array_digest",...}` under Core's selected profile; the fresh Core read accepts it, while a fresh IR reader refuses the exact same persisted bytes as an unknown canonical tag. This is already represented by `tests/unit/core/artifacts/test_ir_adapter.py::test_core_put_json_preserves_array_digest_mapping_but_raw_ir_reader_refuses_it`. The source audit also identifies Core-only `bytes_hex` and `float_hex`; do not turn that static codec set into a claim that every production writer emits them.

### LA-021-2 — what happens to historical JSON with no profile?

**Recommended choice:** keep default semantic refusal and do not infer a profile from reader defaults. Where the existing API explicitly serves a raw representation, it may return the exact selected bytes after its existing tenant, integrity, and surface-admission checks. That raw response does not become a semantic candidate or authority-bearing value by itself. Keep the Ukraine path's explicitly typed profile-absent snapshot as candidate-only, with exact payload identity and `producer_attestation_status=not_established`. Absence, malformed-present, unsupported/unknown, and declared-and-conformant remain distinct states.

**Alternative:** allow a bounded legacy compatibility route only after a named source owner provides a real artifact discriminator: exact store/namespace and artifact reference, original payload and sidecar/manifest bytes or digests, provenance for the historical encoding rule, actual consumer/use/audience, status and relevant time, and custody/reissue evidence. The path must preserve the old bytes and reference. If the source owner reissues through the existing writer, that creates a new immutable output/reference; it does not retroactively attest an old object. Do not request a corpus scan or invent an issuer contract before there is a named affected consumer and artifact.

**Concrete falsifier:** hold bytes and markers constant while removing the declared profile. The ordinary semantic reader and JSON semantic view must still refuse before treating the payload as a declared-profile value; the raw representation path must retain byte identity. A malformed-present profile must refuse as malformed/unsupported, not be downgraded to absence. Existing tests name these boundaries in `test_profileless_historical_cas_artifact_is_refused_before_bytes`, `test_core_json_missing_profile_is_refused_before_selected_semantics`, `test_semantic_views_refuse_selected_profile_mismatch_and_raw_accept_preserves_bytes`, and `test_profileless_stage_json_is_a_typed_candidate_with_exact_raw_identity`.

## Actual contract and end-to-end path

The two decisions above do not ask G to redo routine owner behavior. `ArtifactWriteOptions` is the existing 12-field write contract. The Core-to-IR adapter normalizes both typed and Mapping carriers to the current field set, validates nested canonical options, and rejects unknown or invalid options. Preserve that interface and its existing field-drift/negative tests; do not reopen a field-by-field repair ladder.

For a JSON write, `FileSystemCAS.put_json` encodes under the selected `CanonSpec`, validates the bytes against that spec, then persists them. `return_selected_profile=True` can return the writer-selected manifest-view hash. That hash binds a selected view; it is not a signature or producer identity. The store also exposes `put_bytes`, where caller-provided bytes and options can be paired. On reads, the raw manifest is parsed before typed admission, the exact selected manifest view/profile and payload hash are checked, and decode/re-encode is performed under the selected facade's law.

`ArtifactRef` is strict (`extra="forbid"`) and carries an optional `manifest_profile_sha256` selector. It has no producer-attestation field. The API's `GET /api/v1/artifacts/{artifact_id}` resolves a manifest view; `GET /api/v1/artifacts/{artifact_id}/content` chooses a raw byte response only for the existing raw-representation request, otherwise resolves the selected typed view. JSON semantic selection rejects absent profile as `canon_profile_absent` and malformed, unknown, or unverified declarations as `canon_profile_not_verified`. Do not describe raw delivery as semantic admission.

The inspector's predictive-coverage diagnostic is a separate reader projection: `PredictiveCoverageDiagnosticPreview` fixes `source_materialization="reader_materialized"` and `producer_attestation_status="not_established"`, carries other unestablished authority/time/calibration statuses, and restricts promotion, publication, policy selection, and causal-effect use. `artifact_inspector.py` constructs those values; API tests verify the limited status and an authority-bearing request is refused. The dashboard Zod validator requires the same literal statuses and `ArtifactInspectorPage` displays materialization, canon-read status, producer-attestation status, and `may_not_use_for`. The page also displays `manifest.producer_component` as declared manifest metadata; that display must not be conflated with a verified producer attestation. Source code and API tests establish the contract, not deployed-runtime status.

The Ukraine snapshot reader is a narrow example of a candidate path, not a general legacy rule: it records the exact raw payload digest/size, labels absent profile as `profile_absent_raw_snapshot_candidate`, preserves raw bytes, and leaves producer attestation and currentness unestablished. No owner-qualified history population or damaged production artifact is established by the current evidence.

## Whole original criterion and the stopping boundary

Original LA-021 (E45/E46/E47/E48/E64; P06/P07/P10) requires preservation of stored bytes and hash behavior, strictness/depth/numeric/date/null/tag behavior, hashing warnings/variants, and distinct exception identities/imports. It says the ten-value ordinary corpus is only characterization, not full bidirectional legacy compatibility. It identifies duplicated Core/IR codecs but does not declare Core the universally correct law, and no damaged production object is established. Q1's current task still requires profile/content conformance plus G's law choices; source-DAG selection alone is explicitly insufficient.

The current CAN audit is a read-only whole-set source selection, not a test run: 2,787 maintained source Python files; 3,113 maintained test Python files; 21 current CAN whole-module test files and 693 AST test-function definitions; 48 files in the direct profile-API test/helper caller superset. These denominators are pinned in the audit manifest. They do not establish history prevalence, all production consumers, or runtime/deployment behavior. The audit reports no tests executed and `source_freeze=false`.

The existing G admission is narrower: strict presented-profile IR read only. Its review/admission explicitly leave Core/IR conformance, history rollout, and producer attestation outside that bounded admission. Existing G records and the prior LA-021 packet are requests/proposals, not an adjudication: no G choice or formal closure IDs were found. Keep `G_acceptance=false`, `formal_closure_ids=[]`, and LA-021 `execution_remaining` until the authorized decision and whole criterion are actually satisfied.

## Reuse-first implementation consequences

- **Reuse:** keep the existing `common/canonical.py` mechanics and common hashing primitives; preserve Core and IR facade contracts, exception identities, typed write options, strict raw-sidecar parsing, and the current raw/semantic API split.
- **Extend:** only if G chooses an additive tag-family identity, extend the shared profile contract and all actual writers/readers in one versioned compatibility step. Only if a named owner shows a real consumer/history need, extend a scoped legacy reader or use the existing writer for a new, separately identified artifact.
- **Consolidate:** continue to place shared mechanics in Common while facade-specific policy remains explicit. Do not fork a third canonicalizer or hide facade divergence behind a common name.
- **Build new:** no universal tag language, bulk historical retagger, new producer-attestation field, or migration subsystem is justified by current evidence.

If a binding A-side producer/custody contract already exists, reuse and cite that contract; do not ask G to create a duplicate or treat a reader-materialized profile as satisfying it. If no such binding applies to the selected consumer, keep producer origin `not_established` and request only the smallest owner-supplied provenance needed by that named consumer.

If G selects a new persisted identity law, the smallest useful prototype is a real CAS write followed by fresh Core and IR reads over retained old bytes, shared values, Core-only tags, malformed tags, and mismatched/unknown identities; assert exact old hashes/bytes and each facade's typed refusal. If G selects a scoped legacy path, prototype one owner-identified artifact through raw resolution, declared legacy/candidate status, and the real named consumer; keep the old artifact unchanged and include a no-provenance or malformed-present refusal. Neither prototype alone closes all LA-021 values, all callers, or history prevalence.

## Predicate labels and pattern pass

- **Recomputed:** exact selected manifest view/profile comparison, payload hash, and selected-profile encode/decode checks; explicit API refusal for malformed/absent profile in the named tests.
- **Institutionally supplied:** what the shared persisted profile identity promises about Core-versus-IR tag grammar. G has not adjudicated it.
- **Not established:** producer identity from selected profile/manifest metadata; historical absent-profile population and migration necessity; deployed surface status. Do not infer these from source calls or reader defaults.
- **P38 divergence:** the property is “profile identity must not promise a grammar the selected reader does not enforce.” The implementation shares a `0.2.0` label while supplying different strict allowlists. The Core `array_digest` artifact accepted by Core and refused by IR is the concrete divergence case that supports the recommended contextual-law choice and rejects a universal-grammar inference. For history, a profile hash selects a manifest view; it is not CanonInfo content or provenance. The semantic JSON route refuses absence while the raw representation route returns exact bytes under its separate checks.
- **P40:** this is one bounded decision packet for the existing persisted-profile/history class, not a third per-tag/per-caller repair. The two questions are separate decision/input classes. Do not patch individual tags or historical artifacts before the relevant choice and evidence.
- **Relevant register IDs:** P06, P07, P10, P29, P32, P35, P36, P37, P38, P40. Target pattern: one shared mechanics owner, explicit facade policies, recomputed content/profile conformance, and typed unknown/refusal where authority or provenance is absent. Missing capability labels remain `verification_missing` for the full original golden/history criterion and `not_established` for G identity law, producer attestation, and any legacy-history rollout.

## Decision text requested

1. For LA-021-1, choose either **shared mechanics/settings with contextual strict tag law** (recommended) or **additive persisted tag-family identity** (only with an explicit migration and compatibility law).
2. For LA-021-2, choose either **semantic refusal plus existing exact-raw/candidate-only paths** (recommended) or **a named-owner, evidence-bounded legacy route** after the minimum source packet above.

If the minimum evidence for an alternative is absent, record that question as not adjudicated rather than converting a proposal into permission. These choices resolve only the two G semantics; they do not close LA-021 or grant authority to publish, promote, or attest a producer.

## Evidence frame

This packet is bound to branch `codex/e02-unified-local-20261009`, HEAD `ab222d06f42a7bd97ac1dc92c92b91616206a462`, tree `18835f5445e1e10d02bb7a14a260404b53417f0a`. The bound whole-set audit records two other tracked dirty test paths (`test_generation_cycle.py`, `test_orchestrator.py`), no source/test paths changed by that audit, and no runtime execution. A sibling CAN R4 RAW candidate at the same base is unadopted; its manifest SHA is recorded in this packet's receipt manifest. It is not treated as current canonical behavior or as a runtime pass.

The audit, prior proposal, canonical decisions table, task binding, original criterion, CAN-01, G admission/review, source APIs, DTO, GET routes, dashboard receiver, and named existing negative tests are pinned in `manifest-v1.json`. No tests were run for this packet.
