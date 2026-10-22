> Use accepted verifier/index mechanisms and implement only remaining allocations/consumers. External-foundations R9 is distinct from publication INT-R9. [tasks.json](../tasks.json) is the scheduling source.

# Atlas / R9 surface design

Date: 2026-10-22. This is a source-review design for the post-E02 program, not an implementation or a readiness receipt. The execution hard stop is E02 acceptance. G documents are read from `d40bca270ef5c456e8233196e4d8d65e099777a7`; code anchors below were inspected only from C=`dccea950845cda5b38f026e7770c07819d31f4d9` with `git show`. No tests, builds, imports, installs, production-data reads, or Git changes were made.

## Decision and current evidence boundary

Build publication and verification with a typed-empty slot while actual records/signatures remain gated by `GY-PR1`, evidence and applicable signer authority. Institutional absence gates the act/claim, never the reusable capability.

The public verifier response already distinguishes report authentication from a public decision's authority. At C, `PublicDecisionVerificationDimensions` in `src/polisyos/runtime/http/services/public_decision_verification_contracts.py` fixes seven authority dimensions at `not_established`, while `PublicDecisionVerificationResponse.report_authentication` may be `verified`, `invalid` or `not_established`. Preserve that separation. `verified` must never be used as a synonym for admissible, promoted, current or authorized.

The [source inventory](../inventory/atlas.md) is standing, not runtime proof. DS19's 261-row register carries 179 rebind and 138 pending-strangle dimensions (overlapping); DS20 authz is closed while DS1-N010 remains DS4/DS5 `consumer_missing`. Re-measure readiness after E02 and owner closure.

The 2026-10-01 R9 receipts remain partial: integrated replay failed, browser/TypeScript/four-base coverage was unrun, and selected-reference delivery is not anonymous-read/current-head closure. E02 does not close those gates.

## Reuse anchors at C

| Seam | Existing owner to extend |
| --- | --- |
| Public verification / issuance | `src/polisyos/runtime/http/routes/public_decisions.py`: `verify_public_decision_record`, `issue_public_decision_record`; tenant-check, CAS packet read and governed readback. |
| Public artifact production | `src/polisyos/runtime/quality/public_export.py`: `build_public_export_bundle`, `assert_public_export_official_use_limits`; keep candidate firewall here. |
| Verification lifecycle | `src/polisyos/runtime/http/services/public_decision_verification.py`: `issue`, `verify`, `_verify_entry`; governed owner delegation. |
| Typed response | `src/polisyos/runtime/http/services/public_decision_verification_contracts.py`: strict report response + seven dimensions; no UI-only status. |
| Global case index | `src/polisyos/runtime/quality/global_case_index.py`: `GlobalCaseIndexProducer.produce`; `src/polisyos/runtime/quality/capability_discovery.py`: `GlobalCaseIndexCapabilityDiscoveryProvider.search` persists the fresh snapshot and `GlobalCaseIndexOwnerReceipt`. Producer and default provider are accepted; allocate/install and DS13 consumption remain. |
| Generated API client | `packages/runtime-api-client/canonicalRuntimeApiClient.ts`; regenerate from `schemas/runtime_api_v1.openapi.json` via `tools/ops_runners/runtime/generate_runtime_client.py`. |
| Browser verification | `apps/runtime-dashboard/src/features/runs/routes/PublicDecisionViewerPage.tsx#GovernedPublicRecordView`; `apps/runtime-dashboard/src/features/runs/api/publicDecisionVerification.ts#fetchPublicDecisionVerification` (strict parse, no-store, omit credentials, redirect refusal). |
| Acquisition API / UI | `src/polisyos/runtime/http/routes/acquisitions.py`, `src/polisyos/runtime/http/services/acquisition_action_service.py`, `src/polisyos/runtime/http/services/acquisition_surface_projection.py`; reuse `apps/runtime-dashboard/src/features/runs/components/acquisitionRouteExport.ts` and `apps/runtime-dashboard/src/features/runs/domain/acquisitionRoutePresentation.ts`. |
| Machine projections | `src/polisyos/runtime/http/routes/governed_projections.py`: `list_governed_projections`, `get_governed_projection`, Cycle Board and risk-spend projections. |
| Bounded Clerk strangle | `src/polisyos/runtime/http/routes/control.py#launch_nl_run`, `src/polisyos/runtime/http/services/control/nl_pipeline.py`; existing `apps/runtime-dashboard/src/features/clerk/routes/ClerkChatPage.tsx`, `apps/runtime-dashboard/src/features/clerk/hooks/useClerkNlRun.ts`, `apps/runtime-dashboard/src/features/clerk/components/ClerkStructuredResponse.tsx`, `apps/runtime-dashboard/src/features/clerk/components/AIDiffView.tsx`. |
| Audit | `src/polisyos/runtime/http/access_audit.py`: `RuntimeDataAccessAuditTrail`, `RuntimeAuthorizationAuditEvent`, `emit_runtime_authorization_audit`; extend append-only records, not browser telemetry. |
| Exact artifact view | `src/polisyos/core/artifacts/manifest.py#ArtifactRef.manifest_profile_sha256`, `src/polisyos/core/artifacts/store.py#FileSystemCAS.get_bytes/get_manifest`; carry full ref; no second CAS. |
| Product CLI | `tools/ops_runners/runtime_cli.py#_build_parser`; reuse audit export/verify/runtime-query, separate from maintenance CLI. |

These are reuse anchors, not a claim that every vertical slice is complete. The latest inventory reconciles two older statements: `public-decision-verified-badge-is-client-computed` and its `atlas-public-verification-record-bridge` successor are closed; do not rebuild them. The two DS8 scope/signal rows require architect reconciliation at P0; a publication build cannot adjudicate them, and `ds10-public-decision-rendering` remains an outstanding consumer. `global-case-index-producer-missing` is closed; `ds10-global-case-index-producer-allocation` and `ds8-global-case-index` remain blocked on allocation/installation and DS13 consumption. Keep these distinct.

## Public semantics and R9 constraints

The public record and its machine twin should project one owner-issued artifact. Bind at least: canonical case identity; exact source decision packet `ArtifactRef` including selected manifest profile; record ID; publication class; signer/key reference and verification outcome; rule/schema version; issue time and status-snapshot time; authority purpose and audience; provenance; evidence/obligation references; currentness/epoch and visible supersession/revocation lineage. Any field not established by an admitted producer stays an explicit unavailable/`not_established` fact. Do not infer currentness from a timestamp, signature validity from a self-asserted field, independence from multiple sources, or authority from a cryptographic signature alone.

Issuance is tenant- and permission-bound. Public retrieval exposes only the approved public projection, not the underlying run, tenant, private artifact, bearer, or raw proof metadata. Preserve `no-store` for verifier responses. The append-only access audit records authorization admission/denial without credentials or request-body values. A public status snapshot must name its as-of epoch; revocation/supersession changes current authority while preserving the historical fact that an earlier report was issued. A missing, stale, revoked, or conflicting trust/currentness input returns an honest refusal or partial state, never a green default.

Use the existing CAS and exact view identity. R9's selected-reference receipt establishes the reuse rule: same blob bytes do not prove that a requested manifest view is present, owned, authorized or current. Anonymous public reads remain a separate owner-bound closure; the receipt does not authorize a public byte path. Acquisition sources likewise need exact source/version/capture/query/pagination/time facts, rights and allowed purpose before caching or reuse. A URL or hash alone is neither lawful reuse nor evidence of permission. Rights loss/revocation must trigger a dependency reaction and surface invalidation/staleness. Do not add a generic second storage owner.

Offline verification is a distinct mode, never an offline approval/action. Bundle exact record bytes, signature, permitted evidence refs and a bounded trust snapshot. Offline output may establish byte/signature authenticity relative to that snapshot; it cannot establish live revocation, current authority, tenant permission or freshness unless the bundle contains a separately verified, policy-valid snapshot. Otherwise it must say currentness is `not_established`. No offline issuance, acquisition execution, dispute resolution, mutation, or promotion.

## Vertical slices

The detailed compact rows, per-slice negative and removal probes, locks and rollback/migration notes are in [tasks.json](../tasks.json). The local ordering below is provisional; the root resolves the full DAG after its inventory.

| Slice | End-to-end cut | Acceptance signal |
| --- | --- | --- |
| UI-01 — verification consumers | Accepted server-issued verification-record bridge → typed response → generated client → remaining DS12 browser/CLI/MACHINE consumers; audit for authorized reads. | A valid report signature with all decision-authority dimensions `not_established` renders as report-authenticated only. Forged, stale/revoked, foreign-tenant or unavailable inputs remain refused/unknown. This finishes consumer parity; it does not rebuild the closed badge/verifier mechanism. |
| UI-02 — publication capability / first practice | Existing `public_export` producer → exact CAS record/view + typed-empty slot → accepted issue/verify route → generated client → citizen viewer, MACHINE bundle and offline verifier; append-only audit. | The empty state is typed refusal/chronology. A data-only record waits for `GY-PR1`; an actual signature waits for its signer policy. `INT-K02` obligation set and `INT-K06` no-number wording survive each projection; refusal chronology may publish under `INT-K08`. It also owns the DS11 public-signature-population consumer route. |
| UI-03 — canonical index allocation and DS13 handoff | Accepted `GlobalCaseIndexProducer` + default capability-discovery provider → allocate/install the one existing snapshot → existing public/MACHINE projection waist → DS13 browser/CLI readers. | One canonical case maps to public record IDs and exact versions. Duplicate/ambiguous identity, missing/foreign-tenant source, non-public rights or stale status refuses. No producer rebuild or second store. |
| UI-04 — accountability/history | DS13 ledger producer → append-only comment/response and supersession/revocation events → history API/client → browser, CLI, MACHINE feed and audit export. | Closed records are immutable; new evidence adds visible supersession lineage; no automated dispute resolution or silently erased history. |
| UI-05 — bounded Clerk | GY-I/G6 session + orchestration choice producers → typed session/choice/loss artifacts → endpoints/generated client → re-grounded existing Clerk UI, candidate-only MACHINE/CLI and audit view. | Independent of UI-01. A candidate cannot fill authority/approval slots; `authoritative_for=∅` stays visible; dropping a retained limitation blocks the summary. PUBLIC remains out of scope. |
| UI-06 — DS16 core grammar | DS4 canonical vocabulary/value owner → set/interval/unknown/incomparable artifacts → projection + regenerated client → Cycle Board/acquisition/public surfaces. | Mixed values preserve set membership, incomparable/unknown and provenance across API and DOM; no nearest-neighbour status. |
| UI-07 — derived-data bridge | GY-N13b derivation/certificate producers → exact input refs, lineage and epoch artifact → existing governed projection/API/client → reviewer/MACHINE consumers. | Revoke/change a parent and the derived view becomes stale/refused; byte equality or a copied field cannot keep it green. |
| UI-08 — DS21 learning readout | GY-O1 confirmatory updater + GY-O3 versioned world write-back → cause-classed effect/world records → governed projection/API/client → reviewer readout, MACHINE twin and audit. | Only `prediction_error` updates an effect; O2 anomaly remains `candidate_unverified`; protective action never reads as confirmation. No deployment control, rollback or recommendation. |

Additional routes keep closed mechanisms closed while assigning their named residuals:

- **UI-09 / DS19:** dispatch full `entries` census by named owner. Rebind pending (179): DS1:25, DS10:5, DS11:2, DS12:7, DS14:7, DS15:6, DS18:1, DS3:12, DS4:36, DS5:9, DS6:10, DS7:3, DS8:44, DS9:12. Strangle pending (138): DS1:25, DS11:2, DS12:7, DS14:7, DS15:6, DS18:1, DS3:12, DS4:5, DS5:7, DS6:10, DS7:3, DS8:42, DS9:11. Dimensions overlap. Keep rows blocked/`absent/unallocated` until each owner accepts a successor; no blanket 261 rebuild or disposition-only deletion.
- **UI-10 / N010:** DS4/DS5 rebinds the dashboard fallback/identity consumer; DS20 HTTP authz stays closed. **UI-11 / B3:** GY/Fabric/N13b owns public revision-CAS and consumer wiring. **UI-12 / B5:** cloud verification runs the exact two-instance proof on real PostgreSQL; until then it stays environment-blocked, distinct from DS9 reservation proof.
- **UI-13 / scorecard/N012:** reuse DS9 intake/effect, keep producer trust at ops config, and reconcile source-cut receipt. N012 exposure receipt and final signed mandate/dissent remain DS9 `artifact_missing`/`consumer_missing`. **UI-14 / Helm:** ops/deploy mirrors `ops/policy/policies/**` to `ops/cloud/helm/polisyos-cell/policies/**`, outside DS20 authz.
- **UI-15 / DS11 Trust Center + docs IA:** prepare an explicit Atlas-versus-marketing successor decision for unique old-plan Phase 2.11/2.15 content: claim/evidence posture, dated/versioned downloads, canonical-source docs landing/article IA. DS11 claim/MACHINE posture is authority; keep scope/owner blocked until architect resolution; no W0–W10 carryover. **UI-16 / performance:** remain blocked until substantive promoted-design evidence is content-bound; never infer it from report auth or Trust Center copy.
- **UI-17 / DS15:** existing acquisition API/UI and N13b owner; positive-route debt stays blocked on cost basis, native policy, exact route/cutoff/facet. No guessed gaps/VOI, automatic or offline acquisition.
- **UI-18 / DS17:** retain closed negative ledger; route positive coverage/scope/N12 artifacts and over-spend/Bayesian witnesses to GY-N11. No public delta before DS12/13 or INT-R9 sequence/family claim. **UI-19 / DS18:** reconcile debt closure vs unconfigured GY-CR4 reader; producer stays open, lineage blocked and signers empty until source-proven E2E.

DS15 is closed and remains the acquisition reuse path; do not add another acquisition owner. DS17's confidence/risk-spend surface and DS18's currentness/epoch chrome are closed reuse obligations, not reasons to reopen their slices. DS19 disposition is not a readiness receipt. DS20 remains the server authorization base; carry N010's outstanding UI rebind to its assigned DS4/DS5 owner rather than confusing authorization closure with consumer closure.

## First practice, later expansion, and hard gates

First practice is **one narrow data-only public case**: one exact source view, one clear refusal or governed record, one MACHINE twin, one browser view, and one read-only CLI verification path. Wire the remaining consumers to the accepted server-issued verifier and keep the typed-empty promoted slot honest. The client-computed badge and its verifier bridge are closed mechanisms; preserve their forged-packet negative. Show `not_established` authority dimensions until producers establish them. If the data-only `GY-PR1` predicate is not ready, the first public item can be refusal chronology, never a promoted policy. Institutional signer absence does not block building the publication capability.

Then add the canonical case index and DS13's contest/history ledger. DS14 can proceed on its adjudicated `GY-I` + DS9 gate independently of the Phase-6 O-block, but shares the generated contract/generator locks; it must retain candidate clothing and stay REVIEWER/EXPERT. DS16 grammar definition can follow DS4; landing a value consumer requires actual real-DS7-capstone quantity/basis evidence rather than the DS7 closed label; only derived-data work waits on live GY-N13b. DS21 starts only once both GY-O1 and GY-O3 exist; GY-O2 may follow, never lead. None of those slices may claim closure from a contract, API schema, mock, or dashboard alone.

R9 hard gates are separate: (1) finish current-head/four-base attribution and full relevant consumer denominator; (2) close anonymous public-read authority and exact selected-view owner checks; (3) carry R9 pending-intent/refusal semantics through the served surface; (4) preserve the accepted V2 production-approval refusal. Existing bounded R9 receipts remain evidence for their recorded cuts only. Unknown R9 status is `not_established`, not a green sign-off.

## Accessibility, latency, size and offline budgets (measure after E02)

Budgets are proposed, not measured. After E02, pin a low-end mobile browser/network, server fixture and offline device; measure baseline and record an owner-approved adjustment before release.

- Accessibility: WCAG 2.2 AA; keyboard/focus and screen-reader flow; no color-only status; text/name for each authority/currentness field; zero critical/serious automated findings plus manual keyboard/screen-reader review. No comprehension claim from component conformance.
- Browser candidate: on pinned mobile, P75 LCP ≤2.5s, INP ≤200ms, CLS ≤0.1, route JS ≤200 KiB gzip. API warm p95 ≤500ms; verifier JSON ≤1 MiB. Report cache, payload and p50/p95/p99. Public evidence projection target ≤1 MiB; link large authorized sources.
- Offline candidate: bundle ≤25 MiB, verify ≤5s, no network. No live-currentness assertion; absent/expired trust is `not_established`. Probe valid/tampered/revoked/stale/partial/wrong-view bundles. No offline write, promotion, acquisition or dispute.

Measure after E02; a miss is assigned to its owner and never reduces evidence, authority checks or accessibility.

## Conflict graph and rollout

Serialize OpenAPI DTO, generator and generated client edits; regenerate once per frozen source cut. UI-02/03 share case identity/CAS; UI-04 owns history; UI-01/02/04 share audit; DS6 owns shared i18n. UI-05 is independent of UI-01. Other slices use named owner locks; DS19 register edits serialize there, while DS20/DS11/DS15/DS17/DS18 stay with their owners.

After E02: freeze refs/DAG; bind UI-01 to accepted verifier; land UI-02 empty and gated; verify the data-only/refusal path in isolation, keeping actual public first use behind FINAL-USE; reuse index for DS13; dispatch DS19/20/11/15/17/18 to owners; schedule DS14/16/21 by independent gates.

Rollback disables projection/issue and returns unavailable; preserve immutable records/history/audit. Re-enable only through the same gates. Migration maps old links to preview, binds aliases only by owner, preserves issue time and appends supersession; never rewrite hashes/status/history.

## Pattern pass and acceptance

Relevant register classes: P01–P10, P14/P15, P26/P27, P31–P41: full chain, status/authority, replay/time, candidate firewall, complete denominator, substantive probes and red attribution. Register reread before closeout.

Found: badge/verifier closure is preserved by a forged-packet negative (P05/P32/P38); report authentication remains distinct from authority (P04/P10); R9 remains partial (P34/P41); DS12/13 reuse one index owner (P27). Target one exact artifact/owner, full provenance/status/time/audience, lifecycle, browser/CLI/MACHINE parity, audit and property-level negatives. Open: DS12 bridge/render consumer; index allocation and DS13 consumer; DS1-N010 consumer. DS19 stays owner-sliced; DS20 authz stays closed with named residuals.

Acceptance requires `condition→producer→persisted artifact→bridge→API/client→browser/CLI/MACHINE→audit/egress`, positive/adversarial/removal probes, and P37 labels on each gate premise; fail closed on consumer/institution/not-established premises. No tests/builds were run.

## Source references

- `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` — Slice Sequence, DS12, DS13, DS14, DS21, DS15/16/17/18 closures and gates.
- `docs/reference/frontend/atlas-surface-readiness-reconciliation.md`; `docs/reference/frontend/atlas-frontend-disposition-register.md` — claim-level readiness scope and DS19/DS20/N010 boundary.
- `docs/plans/active/agent-packages/PolicyOS_E02R2/R9_PUBLICATION_INTEGRATION_RECEIPT.md`, `R9_SELECTED_REFERENCE_INTEGRATION.md`, `R9_CANONICAL_ID_RECEIPT.md`, `R9_BATCH_SNAPSHOT_RECEIPT.md` — bounded R9 evidence and open gates.
- `docs/research/universal-policy-design/external-foundations/acquisition/01-acquisition-routes.md`, `03-storage-and-reuse.md` — rights, source capture, exact reuse/view identity and dependency reaction.
- `docs/reference/policy-design-case-failure-patterns.md` — pattern labels above.
- `_build/post-e02-r9-program-20261022/atlas-inventory.md` and `.json` — pinned source-reported standing and routes; see also `architecture/atlas_surfaces/frontend-disposition-register.json#entries` (261-row DS19 denominator, as-of 2026-08-09).

## Root reconciliation of complete source criteria

UI-12 must prove all four DS20-B5 PostgreSQL cases at master lines731–734: step-up replay one-winner, scenario mutation plus409, corrupted-head denial before OPA, fresh-app refusal of unheaded CAS. Existing DS9 reservation proof is distinct. UI-05 reuses the source-recorded satisfied GY-I+DS9 prerequisite; no O-block gate and no unconditional GYD-27 wait. Exact debt residuals in inventory/debt-inventory.json control over older producer-missing labels, including current C13 captures, built DS18 verifier and built DS15 route/admission bundle.

## R11: complete estate and retained acceptance

[Auxiliary obligations](../inventory/atlas-auxiliary-obligations.json) give explicit decisions for2 subunits,60 supplemental findings and23 seeded-negative lifecycle rows, separately from261 entries. UI-09 binds all four arrays. A source-recorded repaired/closed row is reused; an open-looking stale supplemental is reconciled, not rebuilt. In particular DS7 terminal-fact and DS16 C23 refusal binding have later source closure evidence. Original register/generator changes happen only in the future owner task.

UI-06 separates grammar definition from real-value landing and derives all eight AQ1 algebras from the canonical set. UI-02 explicitly consumes N020 telemetry-egress and N023 pre-sign privacy negatives, plus the original public operational bar. UI-04 records retained Phase5.5/5.7 privacy/consent, formal/informal provenance, consultation-versus-binding, removal audit and accessibility; institutional decisions remain integrate-evidence. A claimed Phase6.6 regulator feed needs its actual schema/signature/verifier contract; generic history is not parity.

UI-05 consumes DS9's bounded PA2 gate only for actual outward actions; proposal-only action scope remains out_of_scope. PA3 compression-loss and cross-projection disclosure remain its own surface properties. UI-08 proves all four cause classes and same-world provenance; current WP-01/WP-02 permit no posterior mutation; after actual scoped activation, only the active policy’s admitted cause/profile may change it. UI never supplies that activation.

**UI-20** assigns the remaining DS5→DS15 generated promotion-union/private-issuer property. Here private issuer is an internal exhaustive/branded presentation boundary, not an appointment of an institution. Canonical generator, actual issuer and consumer plus original named negative travel together. Novel union values cannot acquire green clothing. UI-17 remains acquisition surface owner; both use the one generated-family lease.

No real public launch is sequenced here ahead of FINAL-USE. Early data-only/refusal demonstrations are controlled verification; actual publication requires the final programme disposition and its separate authorization.

UI-04 retained Phase5.7 also requires large-text, screen-reader and plain-language checks, with audience-qualified semantic review. Its older Ukrainian/Russian-register wording is interpreted through the later ratified D4-A1: en authored primary, uk translation, ru legacy_continuity_frozen. It does not reactivate ru. If a specific actual use requires active Russian presentation, resolve that conflict with the competent locale owner or an admitted external translated-evidence path before making the claim; no silent waiver, no global block on unrelated locales.
