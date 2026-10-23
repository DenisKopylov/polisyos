# Implementation handoff, external inputs and verification order

This package selects architecture for IR-Q1, IR-Q2, PAG and R4. It is documentation only. Product tests, imports, builds, numerical work, source acceptance and formal finding adjudication were not performed. Existing AD01–06 and N818 remain selected. No new `system-design-decisions` document or amendment is applied.

## Work that can start without another architecture question

| Lane | Concrete deliverable | Dependencies and sole writers |
|---|---|---|
| IR owner/admission | One immutable owner descriptor resolution; shared pre-write and pre-read enforcement; explicit context after ref serialization | One writer for `ir/artifacts/contracts.py`, `io.py`, shared `refs.py` declarations. IR-Q1/Q2 semantic contract is selected here |
| Compatibility/migration | Exact owned representations, payload/manifest tuple relation, deterministic registry initialization and migration, rollout/rollback matrix | Same descriptor snapshot; one writer for `ir/migrations/*`; reconcile shared public negotiation users before changing behavior |
| Artifact families | Producers/loaders/generic selectors wired to owner contract; source-qualified current/historical evidence | Parallel by nonoverlapping family after the shared internal interface is fixed; new interface design and independent tests can proceed earlier |
| PAG/R4 computation | Real bounded candidate operation, graph/context/query binding, validated finite-family semantics and unchanged protected refusal | One writer for resolver/transport node and result helpers; algorithm research independent of IR wiring |
| Result/report/surfaces | Nested candidate, coordinated 2.2/1.1 reader/writer rollout; protected consumers and public projections | One writer for shared DTO/facades/schema generators; depends on shared representation admission at composition |
| Verification/review | Independent discriminators and source review on frozen exact candidates | Separate authors and reviewers. Run only affected checks after source freeze; broad replay once at the later E02 closeout |

These are logical lanes, not mandated agent counts. Serialize only shared files, generators or scarce compute. No dependency on a complete historical-production inventory, positive legal relation, universal PAG algorithm, all six Welfare producers or unrelated families may block independent completed mechanisms. Conversely a leaf cannot claim an authority-positive result without its actual required basis.

The complete CSV-to-lane partition is in `callsite-disposition.json`; it references ordinals of the immutable input CSV, not copied source or a permanent allowlist. The 33-path R4 seed inventory is referenced by exact packet and path-set names in `inputs.json`. At implementation freeze reconcile changed/added consumers and the actual code/test/companion footprint. Shared negotiation clients outside those two seed sets are mandatory if their semantics change.

## Extension and maintenance bar

The shared owner resolution must be generic over the owner declarations; no `if kind == mobility`, per-producer dispatch table in I/O, guessed `latest`, domain-specific fallback or parser selected by untrusted schema metadata. Add a resource to the existing corpus under a supported representation and discover/consume it with zero admission-core or per-resource owner-registry change. Register a new representation using existing validator primitives without core changes. A genuinely new semantic decoder may need a reviewed adapter, but still no new dispatch branch in the shared mechanism.

Use the current IR reflection/catalog owner (ADR-0108) to expose/generate supported views from declarations; do not add a hand-maintained second inventory. Package-tree reflection imports are tooling work, not a hot request path. Compile/index a trusted declaration snapshot once and use bounded lookups during reads. Each load pins one snapshot; a new deployment/registration yields a new revision for new operations. No online registry/network schema retrieval or interpreter execution from artifact content.

Resources such as methods, variables, data, jurisdictions and policy alternatives remain discoverable corpus content. Schema/grammar/rule versions specify how a resource is interpreted; they must not enumerate which substantive resources may exist. Tests must include a third unseen resource in the same admitted grammar and a newly registered compatible representation, not merely the two named report fixtures.

Keep generic JSON custody/inspection and typed admission distinct in API naming, documentation and call contracts. No universal rewrite of every numeric dictionary, no new global evidence envelope, no new scheduler or storage platform. Reuse existing canonical profiles, CAS lineage, attempts, authority boundaries, resource admission and current-head publication.

## Genuine inputs versus work the implementer owns

| Boundary | Implement now / establish independently | Cannot be manufactured by G or code |
|---|---|---|
| IR current representations | Read actual producers, schemas, validators and callers; define intended current law and conformance; register exact versions/aliases with owner tests | Evidence that a prior arbitrary override was officially supported, or that a particular historical object was actually emitted by a claimed producer |
| IR history | Recover retained schemas/normalizers and source-qualified fixtures; implement explicit source→target routes; keep unresolved objects opaque | Lost historical payloads, issuer intent or undocumented meaning cannot be inferred from a default/regex |
| Welfare six roles | Trace each actual consumer and existing producer, reuse/extend a real owner; design missing typed mapping where semantics are known; implement shared role binding | Data, behavioral/fiscal laws or normatively selected bases absent from the system. Names alone do not define six contracts |
| T1/T2, B61/B148 | Read-only reconcile exact selected serving root/profile/context and minimal paired manifests/member inputs when available; wire runtime selection and receipts | Current live serving/custody/issuer facts, matching historical bytes or genuine replacement reference that has not been supplied |
| PAG/B33 | Candidate diagnostics and refusal; actual named model/identification-plan bridge; legal receipt intake and purpose-specific verifier plumbing | Authenticated operative provision/issuer/scope/time and legal applicability to this claim. A manual SCM is not a substitute |
| B31, LA-036, B190/B197 | Reuse method-output/estimand/unit bridge, record all missing dimensions; bind uncertainty to the same subject/estimand/unit | Actual calibration/conditional law, population, coefficients/Jacobian/covariance and independent validity evidence |
| B194/B200 | Full attempted/succeeded/failed/unattempted draw ledger and actual source/seed/evaluator binding; preserve non-narrowing | True overlap/replication/dependence design or independence evidence not recoverable from source records |
| B161 later refinement | Implement already selected first same-basis unassessed→assessed transition and preserve history/other risks | No universal assessed→assessed refinement law is selected; reopen only for a concrete consumer relation and falsifier |
| LA-023 | Reuse actual method owner and expose declared domain/limitations | Signed-wealth convention or negative-value law cannot be inferred from an unrelated Economics training pass |

Welfare roles are `baseline_microdata_ref`, `policy_basis_ref`, `mechanical_inputs_ref`, `behavior_model_ref`, `fiscal_state_model_ref`, `instrument_set_ref`. Proof/uncertainty refs remain separate. For each unresolved role, deliver an explicit attempted reuse/extension analysis, required semantic predicate, smallest missing input and a proposed binding. “Owner input missing” alone is insufficient when the implementation team can define a current programming contract itself.

External evidence acquisition can continue independently using existing source-search/admission mechanisms. Findings stay held/limited where genuinely required facts remain absent. A candidate path may carry an unknown legal/scientific premise with a known parser; it may not guess an unknown schema or falsely assert custody/currentness.

## Resource and performance design

- **Metadata first:** resolve a bounded manifest/declaration before payload fetch. Refuse obvious owner/version/profile mismatches without reading content. Do not promise zero-byte I/O for a payload-conformance defect.
- **One semantic pass:** share one selected manifest, one bounded decode and one source validation/projection per read. Reuse existing canonical hash/conformance mechanics; avoid duplicating full payload dictionaries or repeatedly hydrating children through wrappers. A DTO/model copy is not a substitute for binding actual source bytes.
- **Cache exactly what was established:** identity/profile/owner-policy/validator/purpose/epoch in the key; immutable input/output identity remains reusable, live access/authority eligibility is rechecked. Never promote a byte-cache hit to typed owner admission.
- **Bound graphs and histories:** actual existing resource owner caps payload, depth, candidate attempts, elapsed work and retained trace; report truncation and effective budget. Count sampling work and invalid/duplicate proposals, not just successes. No full-PAG enumeration or broad production scan in ordinary GET.
- **Immutable, lazy migration:** new derivation only when requested and permitted; retain original refs. Large corpora do not need bulk conversion to deploy a compatible reader. History retention and caches follow their existing owners, without automatic deletion.

## Completion signal and stop rules

Deliver small finished source commits with all mandatory companions, then a separate handoff referencing exact implementation SHA/tree and source/input/backend identities. One mechanism is not split to fit a path budget. The deciding output includes the actual bounded positive, negative, removal probe, installed/public consumers and migration matrix, not counts alone.

For each requested property distinguish `PASS`, `FAIL`, `ERROR`, `SKIP`, `UNRUN`, declared algorithmic limitation and genuine missing input. Do not label unrelated gates inherited without P41 base proof. New implementation that simply returns refusal on every case fails the candidate positive; non-null values alone fail the semantic adequacy test.

Before escalating a stop, state: (1) the property and actual divergent case, (2) current canonical owner, (3) reuse/extension tried, (4) whether a programming-contract choice is already authorized here, (5) exact unavailable external fact or unresolved substantive rule, (6) independent work that can still finish. The questions resolved here are not grounds for another generic request to G. A new scientific/authority law or conflict with a ratified rule is grounds for a precise new decision packet.

Code acceptance and formal per-occurrence adjudication remain separate. No existing B198 or other historical closure is reopened or multiplied. Follow P40: classify a finding as a new class or a deeper example; on the second same-class escape widen the mechanism or state/test an honest residual rather than continue instance patches.
