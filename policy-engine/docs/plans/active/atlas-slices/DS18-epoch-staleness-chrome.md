---
plan_id: atlas-ds18-epoch-staleness-chrome
title: "DS18 - Epoch and Staleness Chrome"
type: slice-plan
status: proposed_execution_approval_required
created: 2026-08-27
last_verified: 2026-08-27
stability: proposed
slice: DS18
baseline_commit: 2525da7306d329ae28fa394690e1c39133eb0d55
branch: codex/ds18-epoch-staleness-chrome-plan
master_plan: ../POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md
surface_constitution: ../../../system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md
identity_boundary: ../../../system-design-decisions/policyos-identity-and-custody-boundary.md
failure_register: ../../../reference/policy-design-case-failure-patterns.md
gy_n12_plan: ../layer3-slices/GY-engine-subordination.md
disposition_register: ../../../../architecture/atlas_surfaces/frontend-disposition-register.json
audiences: [PUBLIC, REVIEWER, EXPERT, MACHINE]
depends_on:
  - DS4 merged at 7f450eb7b
  - GY-N12 merged at c6fbfa388
blocks_on:
  - DS11 must land before any apps/runtime-dashboard or architecture/atlas_surfaces implementation
laws:
  - 3
  - 6
  - 7
---

# DS18 — Epoch & Staleness Chrome

> **For implementing agents:** execute this plan cluster by cluster with red-first
> behavioral tests and verification-before-completion. This file authorizes no
> implementation by itself. Do not start the post-WAIT clusters until the DS11
> landing receipt is an ancestor of the execution base.

## 1. Outcome

Close the epoch family's `surface_missing` state without laundering the upstream
authority gaps. Every decision-bearing surface must expose declared `as_of`, epoch,
validity, and staleness semantics; a stale item must look stale; a replay crossing an
epoch boundary must show the boundary. The internal run surface must include a stale-
certificate view, dependency inheritance and recompute posture, OpenWorldRisk freeze
state, visible supersession lineage, and an exact-byte MACHINE twin.

The steady-state demo on the current production composition is **not** a green epoch.
It is a designed, useful, non-error `not_established` state showing the exact missing
authority and its consequence. The two deliberately unappointed institutional roles
remain unappointed:

- `epoch_predicate_policy_signer` → `policy_admission_missing`;
- `epoch_transition_signer` → `epoch_transition_signer_not_established`.

DS18 renders those typed refusals. It does not appoint either role, self-sign, infer an
epoch, or substitute a demo credential.

## 2. Binding sources and laws

- Atlas master DS18: `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:2005-2033`.
- Surface Constitution laws 3, 6, and 7:
  `docs/system-design-decisions/policyos-atlas-surface-constitution-and-frontend-vision.md:176-193`.
- GY-N12 owner plan: `docs/plans/active/layer3-slices/GY-engine-subordination.md:2284-2332`.
- GY-N12 closure basis: `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-closure-basis.md:131-187`.
- DS4 temporal primitive: `apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx:8-89`.
- Capability allocation history:
  `architecture/production_quality/chronology_capability_allocation.toml`.
- Failure/repair register:
  `docs/reference/policy-design-case-failure-patterns.md`.

The laws are operational here:

1. **Law 3 — fail closed and downgrade.** Missing epoch data, a missing signer,
   unresolved scope, stale support, or limited OpenWorldRisk is a typed blocker or
   limitation, never an empty/error screen.
2. **Law 6 — untested is out of envelope.** An unadmitted epoch, unknown dependency
   denominator, or unresolved recompute owner cannot render as current.
3. **Law 7 — closed cases replay immutably.** New facts produce annotation,
   revalidation, reissue, supersession, or withdrawal with visible lineage; they do
   not rewrite the closed record.

## 3. Planning coordinate and census discipline

All planning reads were taken from the attached worktree branch named in the
frontmatter. Every path-bearing command first ran `git rev-parse --show-prefix`; every
measured command had an `uptime` pair and `/usr/bin/time -p`; pipe statuses were read
before results were admitted.

No count below is single-derived.

### 3.1 GY-N12 landing receipt

The admitted N12 range is
`715c25f1e48859a6b1b932b3db81199c8beeadfc..b99152069797a6f0e3fb10432a97015432dd8a50`,
merged by `c6fbfa3881c2444091598eb6cd301d158826e938`.

| Set-level fact | Derivation A | Derivation B | Result |
| --- | --- | --- | --- |
| N12 commits | `git rev-list --count` | count of `git log --format=%H` records | `24 = 24` |
| N12 changed paths | count of `git diff --name-only` records | `git diff --shortstat` file denominator | `174 = 174` |

The path comparison is against the N12 branch merge base, not the merge commit's first
parent. Comparing merge parents measures unrelated mainline divergence and is not an
N12 census.

### 3.2 Complete source and route denominators

| Set-level fact | Derivation A | Derivation B | Result / disagreement |
| --- | --- | --- | --- |
| Python source denominator | `rg --files src/polisyos -g '*.py'` | union of root and recursive `git ls-files` Python pathspecs | `2,600 = 2,600`; the first recursive-only git pathspec returned `2,599` because it omitted root `src/polisyos/__init__.py`; that rejected denominator is recorded, not hidden |
| HTTP route files / decorated operations | Python AST over `runtime/http/routes/*.py` | anchored decorator census over the same complete glob | `17 / 105 = 17 / 105` |
| visible source operations | AST excludes the two `include_in_schema=False` SSE routes | `105 - 2` using the two exact decorators at `routes/runs.py:799,1143` | `103 = 103` |
| frozen OpenAPI paths / operations | `jq` structured traversal | independent Python JSON traversal | `100 / 102 = 100 / 102` |
| registered generated client outputs | TOML parse of the runtime-client and dashboard-type families | exact tracked-file census of the registered paths | `6 = 6`; with the OpenAPI snapshot, the generated bridge transaction has `7` outputs |

One rejected lexical OpenAPI proxy counted `98` path-looking lines and `116`
`operationId` tokens because examples and schema fields share those markers. It is a
P38 witness, not a usable derivation. The structured comparison finds exactly one
visible source operation absent from the frozen OpenAPI set:

`POST /api/v1/control/decision-validity/epoch-batches`.

An independent exact-literal scan over the snapshot plus all six registered generated
outputs finds neither that path nor `EpochValidityBatchResponse`, while the source
route/DTO scan finds both. Thus the singleton set difference is not inferred from the
operation-count arithmetic alone.

### 3.3 DS4 and current decision-bearing lower bound

`TimeSemanticsLabel` currently accepts `validAt`, `txAt`, `payloadAsOf`,
`ProjectionFreshness`, caller-owned cache age, and children. It has no epoch ref,
epoch-resolution status, validity status, stale-certificate trigger, dependency,
recompute, perturbation, supersession, or OpenWorldRisk input. Missing time roles
render `unknown`; DS4 correctly forbids substituting one clock for another.

Two complete production-tree identifier walks (`rg` and `git grep`, excluding tests and
stories, then excluding the definition/barrel/contrast metadata) both found **zero
production call sites** for `TimeSemanticsLabel` on the planning base. DS18 therefore
extends and consumes the existing primitive; it does not create a parallel badge
vocabulary.

The DS5 baseline manifest supplies only a lower bound, not an exhaustive surface
denominator:

| Set-level fact | Derivation A | Derivation B | Result |
| --- | --- | --- | --- |
| recorded `decision_bearing` resolutions / unique origin paths | `jq` over `lint.resolutions` | independent Python JSON traversal | `21 / 10 = 21 / 10` |

`apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts:820-833` explicitly says
the owner lacks an exhaustive decision-bearing-render → DS4-primitive relation. The
`21 / 10` result must therefore be described as a lower bound. Cluster C06 establishes
the complete relation before the universal claim may become green.

### 3.4 DS11 live conflict fence

The brief's **63** is the tracked DS11 holding set. The live DS11 worktree has since
acquired one untracked visual snapshot, so the collision set used for scheduling is
**64**.

| Set-level fact | Derivation A | Derivation B | Result |
| --- | --- | --- | --- |
| live DS11 changed-path union | `diff base..working-tree` union untracked | committed diff union working diff union untracked | `64 = 64`, symmetric difference `0` |
| tracked / untracked split | tracked diff from `f935e0c2e` plus `ls-files --others` | partition of either union above | `63 tracked + 1 untracked snapshot` |

The additional path is
`apps/runtime-dashboard/e2e/ds11-runtime-dashboard.visual.spec.ts-snapshots/ds11-trust-posture-chromium-darwin.png`.
The live set includes shared UI, locales, route registration, the frontend disposition
register, the DS11 visual spec, and its snapshot root. This plan does not edit or
borrow DS11 evidence. It waits.

### 3.5 Planning measurement receipt

The load values were captured by the surrounding `uptime` pair; the admitted command
receipts below record the requested CPU basis explicitly.

| Planning command | `real` | `user` | `sys` | `user + sys` |
| --- | ---: | ---: | ---: | ---: |
| N12 commit/path double census | `0.08 s` | `0.05 s` | `0.01 s` | `0.06 s` |
| complete Python AST call census | `9.43 s` | `9.01 s` | `0.30 s` | `9.31 s` |
| source-route versus OpenAPI structured set comparison | `0.14 s` | `0.12 s` | `0.01 s` | `0.13 s` |
| DS11 two-union collision census | `0.16 s` | `0.07 s` | `0.16 s` | `0.23 s` |
| mechanism-table parser/readback | `0.11 s` | `0.06 s` | `0.02 s` | `0.08 s` |

## 4. What exists: typed-result census and reachability partition

This table is an enumeration, not a claim that every row is complete. No aggregate
row count is used.

| Partition | Existing typed result and load-bearing fields | Actual producer/consumer path | Opening capability state |
| --- | --- | --- | --- |
| HTTP + frozen OpenAPI, canonical temporal owner | `TemporalRef`, `TemporalScope`, `TemporalCapabilitiesView/Response`: independent valid/transaction coordinates, ranges, event points, gaps and supported surfaces (`core/contracts/runtime.py:596-711`) | `GET /api/v1/temporal/capabilities?run_id=...` returns `200` with or without a decision packet, enforces run/tenant access when bound, and delegates to `TemporalService` (`routes/temporal.py:29-80`, `services/temporal.py:115-386`) | temporal contract/route/service implemented; semantic epoch, validity, staleness and reviewer action permission are not yet composed |
| HTTP + frozen OpenAPI | `DecisionValiditySummaryResponse`: packet/run ref, `status`, `lifecycle_status`, `checked_at`, reasons, triggers, review flag, supersession refs, lineage key, recommended action, events/transitions/reviews/jobs/reissue candidates (`core/contracts/control.py:236-270`) | `GET /api/v1/control/runs/{run_id}/decision-validity` and packet-ref twin; replay hash bound in `routes/control.py:550-625` | implemented generic lifecycle; epoch chrome fields `surface_missing` |
| HTTP + frozen OpenAPI | `DecisionValidityEventRequest/Response`: append-only event request, affected packets and status counts (`core/contracts/control.py:174-200`) | `POST /api/v1/control/decision-validity/events` | implemented generic lifecycle; the six perturbation source classes are not represented |
| In-process/artifact canonical perturbation owner | `GovernanceMonitorEvent`: event id/type, decision ref, severity, exact claim/DAG scope, reason, occurrence time and metadata; current `MonitorEventType` has five detector kinds, including `incident`, but not the complete six-class M36 taxonomy (`scientist/governance/continuous/monitors.py:33-108`) | `incident_monitor_event(...)`, validity-report persistence and `bridge_governance_events_to_claim_lifecycle(...)` exist, but a 2,600-file AST census finds one definition and zero production calls for each named function; an independent literal call-site scan finds only unit/smoke-test calls (`incident.py:91`, `reports.py:25-109`, `lifecycle_bridge.py:505`) | `implemented_but_not_orchestrated`; complete class taxonomy, standalone exact event persistence, production intake, evidence-validity chain and surface are incomplete |
| Source route, absent frozen bridge | `EpochValidityBatchRequest`: transition ref + query-context ref; `EpochValidityBatchResponse`: batch id, completed state, transition, completion receipt, affected packets, claim-bridge refs (`core/contracts/control.py:202-225`) | source route at `routes/control.py:521`; owner intake then claim bridge at `run_lifecycle.py:2122`; absent from schema and all generated clients | `bridge_missing`; standard container also uses `NoEpochTransitionVerifier`, so the positive path remains `producer_missing` / unallocated |
| Public contract, no dedicated route | `SemanticEpochProductionReceiptStatement`: production mode, `appended|no_change|not_established|contested`, prepared/admitted/epoch/manifest/history/chronology refs, query context, `failure_codes` (`core/contracts/epoch.py:884-925`) | acquisition finalization persists `epoch.production_receipt`; no typed read projection | producer/artifact implemented; API/consumer/surface missing |
| In-process service results | `EpochResolutionResult`, `EpochHistoryAppendReceipt`, `PreparedSemanticEpoch`, `PersistedSemanticEpochProductionReceipt`: resolution/reconciliation, manifest/head/history refs and hashes, query/stamp, receipt bytes (`runtime/quality/semantic_epoch.py:646,849,1196,1246`) | acquisition bridge calls finalization at `acquisition_executor.py:1745,1774` | implemented but only indirectly reachable |
| Public contract, no dedicated route | pending/completion/receipt/persisted batch evidence; gate receipt/nonreceipt; pre-N9 subject/admitted candidate/N9 projection (`core/contracts/decision_validity.py:228-602`) | Decision Validity persists an admitted batch and claim bridge consumes completion; other gate DTOs remain internal | contract + partial producer/consumer; surface missing |
| In-process only | `EpochValidityTransitionArtifact`: previous/current epoch, certificate bindings, dependency graph, complete target vector, denominator refs, query context, purpose, content hash (`epoch_validity_cascade.py:535-563`) | an exact literal census finds the sole `produce_and_persist(` occurrence at its definition; an independent AST census finds one definition and zero calls in the complete 2,600-file source denominator | `implemented_but_not_orchestrated`; positive signer/producer identity absent |
| In-process typed refusal | `EpochTransitionSigningNonReceipt`: `not_established|rejected`, exact code, predicate class (`epoch_validity_cascade.py:711-750`) | `NoEpochTransitionSigningAuthority` returns `epoch_transition_signer_not_established`; not externally routed | contract exists; bridge/consumer/surface missing |
| In-process typed refusal | `EpochValidityGateNonReceipt`: status/code/subject/query refs (`core/contracts/decision_validity.py:470-501`) | gate returns `policy_admission_missing` at `epoch_validity_cascade.py:2096-2108` | contract exists; bridge/consumer/surface missing |
| In-process staleness | `CertificateStalenessDecision`: `current|stale|revalidation_required`, reasons, stale edge keys (`credal_reference.py:389-397`) | its sole producer at `credal_reference.py:498-526` currently returns only `current` or `stale` | `revalidation_required` producer path missing; surface missing |
| In-process dependency inheritance | `EpochCertificateBinding`, `EpochDependencyGraph`, `TargetDispositionVector`: immutable recipe binding, input refs, source→target edges, full target denominator and dispositions (`epoch_validity_cascade.py:222-357`) | advisory events traverse descendants before the independently reconciled target vector is built (`epoch_validity_cascade.py:404-530`) | inheritance semantics implemented; no read projection and no recompute lifecycle result |
| No admitted epoch/recompute model | `DerivedObservationSeries` and derivation certificates carry content-addressed recipe facts but no epoch inheritance/recompute-status projection (`derived_observations.py:618-784`) | no semantic-epoch read bridge into the derived-observation owner was found | `absent/unallocated` for recompute execution/status producer; DS18 may render this honestly, not invent completion |
| In-process/artifact only | `OpenWorldRiskVector`, persisted/verified vector, production and resolution nonreceipts, public limitation: complete component denominators, `established|limited|not_established`, limitation code/hash (`open_world_risk.py:272-500`) | promotion and public export consume it; generic artifact download can expose bytes only when a ref is already known | producer/artifact implemented; typed API/dashboard bridge missing |

Adjacent scenario staleness and human-decision verifier epochs remain distinct systems.
They are not evidence that semantic-epoch chrome is already routed, and DS18 must not
collapse them into one status.

### 4.1 The six-class contract gap

The canonical intake is already `GovernanceMonitorEvent`, not
`DecisionDependencyEvent` and not `AdvisoryPerturbationEvent`. The existing
`incident_monitor_event(...)` producer, persisted validity report, and lifecycle bridge
prove the typed/mechanism pieces in isolation, not a production chain: both named
entry/bridge functions currently have zero production callers. `MonitorEventType`
names five detector kinds and does not preserve the complete
`incident / appeal / correction / retraction / legal-change / discovered-bias`
taxonomy. `AdvisoryPerturbationEvent.event_kind` separately carries the prospective
**actions** (`annotation_only`, `invalidate`, `reissue`, `supersede`, `withdraw`); it is
not the source-class owner.

C01 therefore extends the existing continuous-governance owner with a strict
six-class perturbation arm and exact standalone event persistence. The existing
incident producer remains the producer for the incident arm and is exercised without a
second incident contract. The existing invalidation owner gains the typed
`EvidenceValidityEvent` binding source → evidence-line → claim → publication for
correction/retraction propagation. Rule-evolution records, appeal lifecycle provenance,
and fairness evidence are content-bound inputs to the canonical monitor event; they do
not become new lifecycle owners.

The live orchestration entry is the existing
`POST /api/v1/control/decision-validity/events`: its request gains a mutually exclusive
`monitor_event_ref` arm. That arm accepts no caller status, class, trigger or scope; the
control service resolves and verifies exact monitor-event bytes, invokes and persists
the existing lifecycle bridge, then derives the generic Decision Validity event and
epoch advisory binding from those owner bytes. The legacy caller-shaped request arm
remains generic Decision Validity input and cannot issue a six-class identity. The read
projection reloads the canonical monitor event and persisted bridge result.

No caller-authored `source_class` is added to generic `DecisionDependencyEvent`; that
would be a parallel P27 owner/bypass. The epoch advisory object continues to reference
the exact persisted monitor event and action hint. The projection reloads the canonical
event bytes to render the class, and it refuses a duplicated/mismatched class. Rendering
classes only in React, deriving `discovered_bias` from an unadmitted fairness metric, or
leaving the producer/bridge callable only from tests would be P01/P02/P05/P15/P32.

### 4.2 Partition consequence

DS18 is therefore not “add badges.” It contains:

1. producer/contract work for the six-class and dependency/recompute projection;
2. a typed read bridge for existing persisted epoch, Decision Validity, lineage, and
   OpenWorldRisk artifacts plus the real typed absences;
3. OpenAPI/client repair, including the already-live epoch-batch source route;
4. dashboard admission, chrome, detailed view, exact-byte MACHINE twin, and universal
   semantic enforcement.

## 5. Architecture ruling: one owner projection, no authority in React

### 5.1 Reuse the existing run and owner seams

Extend the canonical temporal owner with a read-only run subroute:

`GET /api/v1/temporal/runs/{run_id}/epoch-staleness`

The placement is deliberate: `TemporalScope`, `TemporalRef`,
`TemporalCapabilitiesView`, `TemporalService` and `/api/v1/temporal/capabilities`
already own the runtime's valid/tx grammar and capability gaps. The new route composes
that service with Decision Validity storage, epoch history, the claim lifecycle bridge,
artifact CAS, OpenWorldRisk public limitation projection, and export-replay headers. A
dedicated subroute keeps the compact capabilities manifest compact, but it is
implemented by the same `TemporalService` and uses the same canonical `TemporalScope`;
a sibling control-plane time grammar is forbidden and tested. It adds no permission
enum, signing authority, mutation action, public unauthenticated route, or second
lifecycle owner.

The existing Decision Validity GET and POST remain the generic packet lifecycle/read
and monitor-event intake surfaces. The epoch-staleness temporal subroute composes
several owner artifacts and returns a typed absence even when a run has no decision
packet, matching the existing temporal capabilities behavior rather than the control
GET's intentional `decision_packet_missing`. The response mints no authority artifact.
Its capability chain is grounded in persisted production receipts, batch evidence,
monitor/lifecycle events, transitions, lineage and OWR artifacts; the server projection
is replay-bound composition over those bytes.

The response is a strict nested `EpochStalenessProjectionResponse` with at least:

- `meta`, `run_id`, optional decision packet ref, query-context ref;
- optional owner-validity `as_of` plus a typed `owner_time_not_established` reason when
  the source/nonreceipt carries no owner timestamp; never use `now()` as a validity
  substitute;
- required server `observed_at`/read time for the replay header, explicitly separate
  from owner validity and excluded from the semantic projection hash;
- current/scope epoch status, ref, semantic facets, valid/transaction/observation
  coordinates, and boundary lineage;
- decision validity and `revalidation_required` posture;
- certificate rows with bound/current epoch, stale reasons, exact trigger/event refs,
  recipe/input refs, authority purpose, and revalidation/recompute posture;
- dependency rows showing revised input → affected derivations, target disposition,
  recompute status, and the evidence that established that status;
- perturbation rows with the six-class source taxonomy separate from advisory and
  adjudicated disposition;
- predecessor/successor/reissue/supersession lineage;
- OpenWorldRisk vector/public limitation and whether promotion is frozen;
- authority-availability rows with role, exact refusal code, predicate provenance,
  consequence, source refs, and closure condition;
- typed limitations for unresolved scope, missing artifacts, absent recompute producer,
  and unavailable whole-history holder.

Every gate-driving predicate is labelled `recomputed`,
`independently_reconciled`, `consumer_asserted`, `institutionally_supplied`, or
`not_established`. The last three never turn an authority-grade gate green. The
projector resolves exact persisted bytes and verifier provenance; it does not inspect a
class name, config flag, field presence, or allocation prose and call that evidence.

### 5.2 Projection rules

- `policy_admission_missing` is read from the actual qualified semantic-epoch result or
  persisted production receipt for the requested scope.
- `epoch_transition_signer_not_established` is the actual typed nonreceipt returned by
  the configured transition-signing seam. It is not inferred from a missing key.
- A certificate may render `current` only when the bound epoch, input hashes, and
  applicable target disposition all reconcile current.
- A verified input revision propagates through the complete dependency graph. A
  dependent derivation renders `revalidation_required` only when the deterministic
  recipe/recompute obligation is established. Otherwise it renders `stale` plus
  `recompute_status=not_established` / `producer_missing`.
- `limited` and `not_established` OpenWorldRisk freeze promotion. No numeric “risk is
  low” projection is introduced.
- An advisory event is downgrade-only. Only a content-bound canonical-owner
  disposition can emit `annotation_only`, `invalidate`, `reissue`, `supersede`, or
  `withdraw` as adjudicated effect.
- The six-class identity is accepted only from the exact persisted
  `GovernanceMonitorEvent`; Decision Validity and epoch rows bind its artifact ref and
  cannot restate a caller-supplied class.
- Closed records stay immutable. The response carries visible predecessor/successor
  refs and epoch boundaries rather than a rewritten record.
- `bind_export_replay(..., as_of=observed_at)` receives the server observation time
  because the signer/gate nonreceipts have no timestamp. Its projection hash identifies
  narrow owner semantics only; it is never described as the identity of exact response
  bytes.

### 5.3 Audience boundary

- The endpoint directly depends on the existing
  `require_action_permission(RuntimePermission.RUNS_REVIEW, ResourceBindingSpec(...))`
  seam, in addition to tenant/run binding. REVIEWER and EXPERT may receive the typed
  response; VIEWER is denied even if it knows a run id.
- MACHINE receives the exact response bytes described below under that same
  `RUNS_REVIEW` permission.
- DS18 adds no public API permission. Existing public-decision surfaces show only
  already-public-safe time fields and explicit unknown/not-established posture.
  Publication authority and public signature changes remain DS12 work.

## 6. MACHINE twin: exact bytes, then strict admission

The dashboard loader must follow the DS11 rule exactly:

1. call the generated runtime client with an intercepting fetch;
2. capture `response.clone().arrayBuffer()` into a copied `Uint8Array` **before** JSON
   validation or view-model construction;
3. fatal-decode and JSON-parse the captured bytes;
4. apply strict recursive validation (`extra`/unknown fields fail at every object
   level), then semantic validation of hashes, denominators, status composition,
   lineage, event class, and `as_of` roles;
5. render the admitted raw object;
6. download the original copied bytes as MACHINE output.

No `JSON.stringify`, object normalization, key sorting, regenerated payload, or
view-model serialization may produce the twin. The API URL plus replay projection
hash is the stable **semantic replay address**, not an exact-body identity:
`meta.request_id` and server `observed_at` may differ while owner semantics do not. The
MACHINE guarantee is scoped to one captured HTTP response, and a parity test compares
its downloaded bytes with that captured body byte-for-byte. DS18 claims no immutable
cross-request body identity; adding one would require a separately budgeted raw-body
digest/binding owner.

## 7. Surface design

### 7.1 Universal chrome

Extend `TimeSemanticsLabel`; do not fork it. The DS18 extension adds explicitly typed
epoch ref/status, validity status, boundary, and revalidation inputs. It retains DS4's
independent roles:

- policy `valid_at`;
- knowledge transaction time;
- response/payload `as_of`;
- source `as_of`;
- producer observation time/state;
- cache age;
- semantic epoch and validity/revalidation state.

The compact chrome always shows `as_of`, epoch, and validity. Missing values show a
typed reason (`epoch_scope_unresolved`, producer missing, authority missing), not a
blank dash interpreted as current. Text and shape/icon carry the meaning; color is
secondary.

| State | Required visual treatment |
| --- | --- |
| `current` | canonical current/verified token, explicit epoch and `as_of`; no celebratory green-only shorthand |
| `stale` | persistent `STALE` text, canonical warning boundary plus patterned/shape cue, old/current epoch comparison, reason and trigger |
| `revalidation_required` | review/revalidation glyph and action requirement distinct from generic stale; never a disabled blank control |
| `contested` / `review_required` | canonical weakest-boundary token with dissent/adjudication reason |
| `superseded` / `reissued` | readable historical record plus explicit successor link and epoch boundary; no destructive overwrite styling |
| `not_established` / authority absent | neutral limitation panel with structural pattern and exact code; visually distinct from transport/error red |

The run detail layout supplies a typed epoch context; run list, comparison, public
decision, and the central decision-bearing chart evidence path consume the same
primitive. The detailed certificate/dependency/cascade/replay view expands inline from
the run layout; DS18 does not create a second run-tab or route-registry owner.

Known export consumers have two deficient input seams and must be repaired before they
render. Extend the existing `PublicShareSummary` owner (despite its historical
`email-fixtures.ts` filename) with a strict admitted-epoch-or-typed-nonreceipt arm;
`OGCard`, every `generate-og` arm, React email, and plain-text email consume that arm.
Replace `BureaucraticDocumentAST.temporal_scope?: Record<string, unknown>` with a strict
admission result that either carries the canonical epoch projection or the exact
`epoch_projection_not_bound_to_document` nonreceipt. Its validator/export path produces
that nonreceipt when the server document contains no bound projection; it never infers
epoch or owner `as_of` from `render_timestamp`. The signed public packet likewise binds
the admitted temporal arm into the packet hash/signature, or records
`packet_epoch_binding_not_received`; `PublicationPacketPanel` renders the bound arm in
both operator and public modes. `RunDetailLayout` is the single live packet producer:
it passes the same signed packet to publication readiness, operator craft, and ambient
telemetry, replacing their three sibling calls to the builder. Thus an admitted
projection reaches the packet hash; the fallback nonreceipt is emitted only when that
run-scoped producer truly did not receive one. Public OG React/Satori/HTML/SVG/PNG output,
HTML/plain-text email, and bureaucratic HTML therefore render epoch/validity directly
or render a precise first-class absence. `shared/export/printExport.ts` is an
inherited-DOM consumer: it is classified and tested to preserve the already-admitted
temporal node, but it does not become a second temporal renderer. C06's complete
relation decides any additional migration; the ten currently recorded DS5 paths are
not treated as the denominator.

### 7.2 Stale-certificates view

Each row shows:

- certificate and authority purpose;
- bound epoch versus current/requested epoch;
- current/stale/revalidation-required status and exact stale reason;
- revision trigger class/ref and its adjudication state;
- input/recipe/native-coordinate refs;
- affected downstream derivations;
- what revalidation requires;
- recompute state (`not_established`, `pending`, `running`, `completed`, `failed`) only
  when emitted by an owner; absence of a recompute owner is shown as
  `producer_missing`, never as pending;
- successor/reissue/supersession link when one exists.

Sorting is presentation only. It cannot decide severity, currentness, or authority.

### 7.3 Replay and lineage

Replay is segmented by semantic epoch. Crossing the boundary inserts a labelled,
keyboard-reachable divider with previous/current epoch refs, the trigger, and the
validity consequence. Lines or chart series never visually blend across that divider.
An unchanged logic hash may produce annotation-only semantics, but the boundary and
annotation remain visible.

### 7.4 OpenWorldRisk freeze

Render the actual vector state and limitation:

- `established`: show the declared scope/obligation basis and refs;
- `limited`: freeze promotion and name outside-scope components;
- `not_established`: freeze promotion and name unresolved components/owner evidence;
- resolution nonreceipt: show the exact code and rejected/unresolved evidence.

Do not compute a local severity or display an unconditional `risk ≤ δ` claim.

## 8. Six perturbation classes — distinct input, shared downgrade law

Event class, advisory posture, and adjudicated disposition are three separate fields.
All classes use an initial downgrade-only authority treatment, but each gets a stable
text label, non-color-only glyph/shape, scope statement, and class-specific detail.

| Event class | Distinct rendering | Forbidden flattening |
| --- | --- | --- |
| Incident | `Incident` label; hazard glyph; observed time; exact affected scope; incident evidence ref; advisory `review_required` until owner disposition | no automatic withdrawal and no generic “changed” badge |
| Appeal | `Appeal` label; case/claim-bound glyph; explicit `this instance` scope; appeal ref and outcome state | one upheld appeal never becomes class-wide invalidity |
| Correction | `Correction` label; before/after fact or rule refs; logic-hash comparison; annotation lineage when semantics are unchanged | no reopen-all; a renumbered unchanged rule is not supersession |
| Retraction | `Retraction` label; broken-support glyph; visible source → evidence-line → claim → publication path; affected support relation | no hidden narrative note and no invented source-level `partial_retraction` type |
| Legal change | `Legal change` label; previous/current legal regime and epoch; revalidation obligation and effective/valid times | no silent history rewrite and no use of observation time as legal validity time |
| Discovered bias | `Discovered bias` label; protected-group/scope statement; evidence and replication posture; review/contested state until owner adjudication | no automatic withdrawal from one metric anomaly and no generic incident styling |

After adjudication the exact owner result is shown separately as
`annotation_only|invalidate|reissue|supersede|withdraw|contested|review_required`.
The event-class glyph remains visible so the cause is not lost in the consequence.

## 9. Declared-absence state — the default production demo

The surface remains fully inspectable when no institutional signer is appointed.
It renders a first-class **Authority not appointed** panel, not an error boundary,
empty state, spinner, disabled page, or retry loop.

Each role row contains:

- role name and authority purpose;
- state `absent/unallocated` / `not_established`;
- exact refusal code;
- affected scope and query-context ref;
- evidence/receipt refs when available;
- what remains inspectable (history, stale bindings, candidate/replay information,
  limitations, MACHINE bytes);
- exact consequence for the claim;
- closure condition, phrased as an institutional dependency rather than an “appoint”
  UI action.

The current two rows are:

| Missing authority | Exact state shown | Consequence shown |
| --- | --- | --- |
| Epoch predicate-policy signer | `policy_admission_missing` | epoch qualification/currentness is not established; candidate/history data may be inspected, but the claim cannot be represented as current or publishable |
| Epoch transition signer | `epoch_transition_signer_not_established` | transition issuance and revalidation completion are unavailable; stale lineage remains inspectable and promotion stays frozen |

`epoch_scope_unresolved` is a separate data/scope state, not a synonym for either
institutional absence. OpenWorldRisk `not_established` is also separate.

Inspection, replay, and MACHINE download controls remain available. There is no
production button to appoint, bypass, self-sign, or force currentness. Positive visual
fixtures are allowed only in tests/Storybook, carry an explicit `fixture_only` marker,
and are barred from authority slots.

## 10. Closure contract

| ID | Closure obligation | Acceptance signal |
| --- | --- | --- |
| DS18-CC01 | Exact typed projection | strict response carries epoch, as-of roles, validity, certificate/dependency rows, event class, lineage, OWR, authority absence, provenance, rule/schema version |
| DS18-CC02 | Real producer readback | projector resolves exact persisted bytes/receipts and real typed nonreceipts; forged/present-only evidence fails closed |
| DS18-CC03 | Six-class preservation | persisted monitor-event ref enters through the live Decision Validity POST, exact bytes drive the persisted lifecycle/transition, and class survives read API → client → DOM → MACHINE; free-standing class/status input fails |
| DS18-CC04 | Dependency inheritance | revised input flags every complete-denominator descendant; missing edge/denominator fails closed; recompute status is owner-emitted or explicitly not established |
| DS18-CC05 | Route and generated bridge | epoch-staleness GET plus the already-live epoch-batch POST appear in frozen OpenAPI and every registered generated output |
| DS18-CC06 | DS4 extension | one `TimeSemanticsLabel` grammar renders independent clocks plus epoch/validity; no local status vocabulary or time substitution |
| DS18-CC07 | Universal coverage | complete production `.ts`/`.tsx` source-file denominator is recomputed; every file's render/export roots and every root's decision-bearing status are independently reconciled with fresh evidence, every decision-bearing member behaviorally renders `as_of`, epoch and validity, and unknown/stale classification fails closed |
| DS18-CC08 | Stale truthfulness | stale/revalidation-required certificates cannot render current; current cannot inherit stale styling accidentally |
| DS18-CC09 | Replay boundary | cross-epoch replay visibly segments the record and preserves immutable predecessor/successor lineage |
| DS18-CC10 | Declared absence | both exact signer absences render as useful first-class states and constrain the claim; no blank/error/disabled substitute |
| DS18-CC11 | OpenWorldRisk freeze | `limited` and `not_established` freeze promotion and show basis/limitations; no local numeric authority |
| DS18-CC12 | Exact MACHINE | downloaded bytes equal captured response bytes; strict recursive and semantic admission precede render |
| DS18-CC13 | Audience and replay | temporal subroute has a direct `RUNS_REVIEW` action dependency, tenant/run binding and semantic replay hash; VIEWER is denied and REVIEWER/EXPERT are allowed; owner-validity time, server observation time and exact bytes are not conflated |
| DS18-CC14 | Accessibility and visual identity | keyboard, zoom, contrast, reduced motion, text+shape semantics, absence and positive views pass; DS18 owns its spec/snapshot root |
| DS18-CC15 | Pattern and history discipline | P39/P40/P41 receipts, branch attachment, cap/readback, no unrelated path, no register/evidence/deep-import drift |

## 11. Red-first behavioral falsifiers

Tests are written before their implementation cluster. Holding a marker, field name,
component name, or route string constant is not enough to keep a test green.

| Falsifier | Hold constant | Mutate the underlying property | Required red |
| --- | --- | --- | --- |
| stale-as-current | certificate refs, labels, component tree | bound/current epoch or input content hash diverges | DOM/MACHINE must change to stale/revalidation; current styling is a failure |
| authority laundering | refusal-shaped DTO and panel markup | remove actual owner nonreceipt or replace predicate provenance with consumer assertion | projection admission fails; panel cannot show a positive/current claim |
| six-class flattening | target/disposition and card layout | `incident` ↔ `appeal` ↔ `correction` while outcome stays `review_required` | class label, icon/shape, scope copy, and MACHINE field must change |
| free-standing class bypass | exact monitor-event ref and route markers remain | submit a caller class/status that disagrees with reloaded monitor bytes, or skip lifecycle-bridge persistence | write intake fails; no Decision Validity/epoch event is emitted |
| appeal overbreadth | upheld result and claim family | scope switches one instance → class | class-wide invalidation is rejected unless exact owner evidence establishes it |
| lineage break | source/claim/publication refs remain present | delete or substitute one propagation edge | compiler/validator fails; a list of refs is not a lineage proof |
| dependency omission | same target count/labels | remove one real graph edge or revise one input hash | denominator validation or descendant coverage fails |
| fake recompute | `recompute_status="completed"` marker | remove executor receipt/content binding | strict semantic admission fails; completed cannot survive |
| OWR proxy | status label and component count | flip one component `established` → `outside_scope`/`not_established` | vector/freeze posture recomputes to limited/not-established |
| epoch blend | same chart values/timestamps | move one point across the epoch ref | visible boundary is required; one continuous series fails |
| time-role substitution | same ISO timestamp text | move value from owner `as_of` to observation/cache field | label must show owner `as_of` unknown, not reuse the other clock |
| byte reserialization | parsed object equality | reorder JSON keys/whitespace in server body | MACHINE matches new response bytes, never a normalized stringify |
| recursive extra field | all expected fields/hashes remain | add an unknown nested field | strict admission fails before render |
| route marker proxy | route/operation ID strings remain | remove projector invocation or response binding | live-route integration fails |
| schema marker proxy | response class name remains | remove nested epoch field or change enum semantics | generated-contract semantic test fails |
| semantic-classification drift | component identity, imports and scanner markers remain | move a render from non-authority copy to a decision recommendation, then reverse it | bound classification becomes stale/not-established until independently reconciled; metric cannot stay green |
| chart coverage | decision quantity/component marker remains | add a decision-bearing chart without admitted temporal chrome | DS5/DS18 lint and rendered-harness test fail |
| census bypass | direct registered members remain | add a `.ts` or `.tsx` sibling using JSX, plain props, `React.createElement`, Satori/server rendering, HTML/SVG template output, or DOM clone/serialization | complete source-file denominator grows and its unreconciled render inventory fails; no marker/allowlist escape |
| export-input laundering | renderer names and temporal-looking strings remain | remove the admitted epoch arm from `PublicShareSummary`, the signed packet, or `BureaucraticDocumentAST`, leaving only trust status, `validAt`, or render time | admission yields the exact typed nonreceipt and no renderer may claim a current epoch |
| packet-producer omission | signed-packet types, panel and hash markers remain | withhold the admitted run projection from the single layout producer while a positive projection exists | positive wiring test fails; a fallback nonreceipt cannot substitute for the omitted bridge |
| non-JSX export omission | export function/file identity remains | remove epoch/validity from OG Satori output, plain-text email, or bureaucratic HTML while React-page chrome stays present | export behavioral harness fails; `.ts` output cannot inherit a `.tsx` pass |

## 12. Execution clusters, path fences, and WAIT

### Cluster overview

| Cluster | Purpose | Declared mechanisms | Hard cluster ceiling | May run before DS11? |
| --- | --- | ---: | ---: | --- |
| C00 | rebase-free readback, baseline reds, exact denominators | 0 | 0 | yes |
| C01 | canonical monitor contracts, six-class/lineage preservation, projection compiler | 7 | 9 | yes |
| C02 | live monitor intake, temporal read owner, DI, OpenAPI contract | 5 | 6 | yes |
| C03 | frozen schema + package-client regeneration receipt | 0 | 0 | yes, but no dashboard output |
| WAIT-DS11 | prove DS11 landed; re-census post-landing frontend owners | 0 | 0 | mandatory boundary |
| C04 | dashboard strict admission and exact-byte MACHINE | 3 | 4 | no |
| C05 | DS4 extension, detailed surface, universal consumers, active locales | 19 | 19 | no |
| C06 | complete render/export census and semantic lint | 5 | 6 | no |
| C07 | visual/a11y/replay/closeout verification | 0 | 0 | no |
| **Total** | unique production/tooling mechanisms | **39** | **44** | — |

The total is independently derived in two ways at plan closeout:

- cluster arithmetic: `7 + 5 + 0 + 3 + 19 + 5 = 39`;
- parser union of the Add/Modify mechanism table below, excluding mandatory P39
  companions: `39` unique paths, no duplicates.

The hard ceiling is the 39-path declared union plus **5** paths of reserve: two for
backend owner/readback seams, one HTTP/ABI seam, one raw-byte admission seam, and one
census/lint seam. The three post-DS11 packet-producer seams originally identified as
reserve were resolved during plan review and moved into the declared set; retaining
them as reserve as well would double-count them. The ceiling is therefore not a
round-number guess. Tests, generated outputs, the plan/journal, release fragment, receipts,
snapshots, and tests pinning a changed constant are mandatory companions outside the
mechanism cap under P39.

**Planning-owner revision.** The pre-review `36`-path union was an estimate, not a
user-supplied stop condition. Independent review enumerated three live sibling packet
producers that the property must change. They are now declared mechanisms, so the
admitted contract is `39 / 44`. P38 forbids treating the old number as a proxy for the
property, and P40 requires widening to the real producer set after the repeated
same-class finding. Do not delete or hide unrelated mechanisms merely to recreate
`36`; any later contraction must prove a canonical owner makes the removed path
behaviorally unnecessary.

### Declared mechanism paths

| Cluster | Action | Mechanism path | Purpose |
| --- | --- | --- | --- |
| C01 | Modify | `src/polisyos/core/contracts/runtime.py` | strict temporal response envelope reusing canonical epoch artifacts, `TemporalScope`, and time roles; no parallel epoch owner |
| C01 | Modify | `src/polisyos/core/contracts/control.py` | mutually exclusive content-bound monitor-event intake arm and bridge refs in response |
| C01 | Modify | `src/polisyos/scientist/governance/continuous/monitors.py` | canonical strict six-class monitor-event arm plus exact event persistence/readback; no external adjudication authority |
| C01 | Modify | `src/polisyos/scientist/governance/continuous/invalidation.py` | typed `EvidenceValidityEvent` and correction/retraction source → evidence-line → claim → publication binding |
| C01 | Modify | `src/polisyos/runtime/quality/epoch_validity_cascade.py` | preserve six source classes separately from disposition and dependency propagation |
| C01 | Add | `src/polisyos/runtime/quality/epoch_staleness_projection.py` | read-only exact-artifact projection compiler; no new authority owner |
| C01 | Modify | `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py` | preserve canonical event class, source/claim/successor bindings and downgrade law; no parallel lifecycle |
| C02 | Modify | `src/polisyos/runtime/http/services/control/run_lifecycle.py` | resolve exact monitor-event ref, invoke/persist lifecycle bridge, then derive generic Decision Validity/epoch bindings |
| C02 | Modify | `src/polisyos/runtime/http/services/temporal.py` | canonical run-scoped epoch-staleness projection method over `TemporalScope` and owner readers |
| C02 | Modify | `src/polisyos/runtime/http/routes/temporal.py` | `RUNS_REVIEW`-authorized replay-bound GET route |
| C02 | Modify | `src/polisyos/runtime/http/dependencies.py` | compose `TemporalService` with exact readers/providers, including real typed absences |
| C02 | Modify | `src/polisyos/runtime/http/openapi_contract.py` | live success/absence contract examples and semantic contract checks |
| C04 | Add | `apps/runtime-dashboard/src/features/runs/domain/epochStaleness.ts` | strict recursive schema plus semantic admission |
| C04 | Add | `apps/runtime-dashboard/src/features/runs/api/useEpochStaleness.ts` | generated-client fetch with pre-parse byte capture |
| C04 | Add | `apps/runtime-dashboard/src/features/runs/export/epochStalenessTwin.ts` | download copied captured bytes, never reserialize |
| C05 | Modify | `apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx` | DS4-compatible epoch/validity/revalidation chrome plus typed context/provider; no inference |
| C05 | Add | `apps/runtime-dashboard/src/features/runs/components/EpochStalenessView.tsx` | compact chrome and full stale-certificate/dependency/cascade/replay view exported from one owner module |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/routes/RunDetailLayout.tsx` | one run-scoped provider, always-visible compact chrome, and the single temporal-aware signed-packet producer |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/routes/RunsListPage.tsx` | per-decision validity/time chrome or honest unresolved state |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/routes/RunComparePage.tsx` | separate epoch/as-of per side; never blend epochs |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts` | bind admitted epoch state or exact nonreceipt into signed packet hash; never infer from generated time |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/components/PublicationPacketPanel.tsx` | render signed time/epoch posture in operator and public modes |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/components/PublicationReadinessPanel.tsx` | consume the layout-produced signed packet; remove sibling packet construction |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/components/OperatorCraftPanel.tsx` | consume the same layout-produced packet for reviewer artifacts; remove sibling construction |
| C05 | Modify | `apps/runtime-dashboard/src/features/runs/components/AmbientTelemetryHud.tsx` | consume the same layout-produced packet for threshold/onboarding events; remove sibling construction |
| C05 | Modify | `apps/runtime-dashboard/src/shared/charts/quantityChartSemantics.tsx` | central chart evidence path consumes temporal chrome |
| C05 | Modify | `apps/runtime-dashboard/src/features/export/social/email-fixtures.ts` | extend the existing `PublicShareSummary` owner with strict epoch/admission state and explicit demo nonreceipt |
| C05 | Modify | `apps/runtime-dashboard/src/features/export/social/OGCard.tsx` | public share card renders epoch and validity with canonical temporal scope |
| C05 | Modify | `apps/runtime-dashboard/src/features/export/social/generate-og.ts` | HTML/Satori/SVG/PNG paths preserve the same epoch/validity semantics |
| C05 | Modify | `apps/runtime-dashboard/src/features/export/social/EmailSummary.tsx` | React and plain-text email preserve admitted epoch/validity or exact nonreceipt |
| C05 | Modify | `apps/runtime-dashboard/src/features/artifacts/bureaucratic/ast/bureaucratic-document-ast.ts` | replace open temporal record with strict admitted epoch/nonreceipt arm and validate before export |
| C05 | Modify | `apps/runtime-dashboard/src/features/artifacts/bureaucratic/export/export-html.ts` | operator HTML export renders packet as-of, epoch and validity instead of render time alone |
| C05 | Modify | `apps/runtime-dashboard/src/shared/i18n/locales/en.json` | exact state/event copy |
| C05 | Modify | `apps/runtime-dashboard/src/shared/i18n/locales/uk.json` | exact state/event copy |
| C06 | Modify | `architecture/atlas_surfaces/frontend-disposition-register.schema.json` | complete source-file → render/export root → temporal obligation relation |
| C06 | Modify | `architecture/atlas_surfaces/frontend-disposition-register.json` | DS18-owned classifications/bindings after DS11 lands |
| C06 | Modify | `architecture/atlas_surfaces/check_frontend_disposition_register.py` | complete denominator and recomputing validation |
| C06 | Add | `architecture/atlas_surfaces/decision_time_semantics_scan.mjs` | complete TS/TSX file census plus AST render/export candidates; semantic classification remains independently reconciled |
| C06 | Modify | `apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts` | promote metric from `not_established` only after exhaustive relation exists |

### Mandatory companions outside the cap

- This plan and execution journal:
  `docs/plans/active/atlas-slices/DS18-epoch-staleness-chrome.md` and
  `docs/superpowers/journals/2026-08-27-ds18-epoch-staleness-chrome.md`.
- Release record:
  `release-fragments/unreleased/2026-08-27-ds18-epoch-staleness-chrome.toml`; record
  `surface_classification="public_stable"`; include structured additive
  `python-public-api`, `schema-openapi-abi`, and `js-package-api` compatibility
  changes for the public DTO signature, runtime OpenAPI, generated runtime client,
  and dashboard API types; set every schema/client
  `generated_client_compatibility="requires_regeneration"` (never
  `not_applicable`); and set `public_surface_inventory_reviewed=true` only after
  regeneration and owner/reviewer acknowledgement. The release checker must prove
  all three classes are present before promotion.
- Generated contract family: `schemas/runtime_api_v1.openapi.json`, all five
  `packages/runtime-api-client` outputs registered in
  `architecture/generated_artifacts.toml:724-771`, and
  `apps/runtime-dashboard/src/api/types.ts` registered at `:778-805`.
- Public-stable facade outputs required by the changed
  `polisyos.core.contracts.DecisionValidityEventRequest` signature:
  `architecture/public_surface/inventory.json` and
  `docs/reference/public-surface.md`. Regenerate with the registered canonical command
  using `--skip-deep-import-baseline`, accept only the two declared output diffs, and
  obtain the required reviewer acknowledgement; never hand-edit them.
- Nearest-package documentation for the new runtime-quality module:
  `src/polisyos/runtime/quality/README.md`.
- Mirrored backend/unit/integration/OpenAPI tests, frontend domain/hook/export/component/
  route/a11y tests, checker corruption tests, health-metric tests, and focused public-
  surface inventory/facade snapshot checks.
- DS18-only visual spec and root:
  `apps/runtime-dashboard/e2e/ds18-runtime-dashboard.visual.spec.ts` and
  `apps/runtime-dashboard/e2e/ds18-runtime-dashboard.visual.spec.ts-snapshots/`.

No DS11 plan, journal, receipts, spec, or snapshot is a DS18 companion.

### C00 — re-read and establish red

1. Verify attached branch and prefix before every path coordinate.
2. Re-run the two census derivations above on the execution base.
3. Run `corepack pnpm install --frozen-lockfile` before any TypeScript scanner or
   generator; installation is tooling setup, not dashboard implementation.
4. Run the named behavioral falsifiers and record their pre-implementation red.
5. Re-open the failure/repair register.

**Red first:** real signer nonreceipt renders no epoch surface; a stale/current epoch
mutation leaves the existing view unchanged; a decision-bearing chart omits `as_of`;
and a replay fixture crossing epochs remains visually blended. Each baseline must fail
for the semantic property, not merely because a future component or route name is absent.

**May not:** edit any source, register, generated output, DS11 path, debt register, or
deep-import baseline.

### C01 — contracts and real projection inputs

1. Extend `GovernanceMonitorEvent` as the single typed six-class intake and persist/load
   its exact bytes. Reuse `incident_monitor_event(...)`; do not create a second event
   owner.
2. Add the typed `EvidenceValidityEvent` chain in the existing invalidation module and
   bind correction/retraction through source → evidence-line → claim → publication.
   Appeal provenance, rule-evolution logic hashes, and bias evidence enter only as
   content-bound source refs; absent external adjudicators remain absent.
3. Extend the existing control request/response contract with a mutually exclusive
   `monitor_event_ref` arm and lifecycle-bridge refs; no caller class/status is admitted
   on that arm.
4. Bind the exact monitor-event ref through the existing lifecycle and epoch-cascade
   owners. Reuse Decision Validity's existing `source_ref` event field and
   `enumerate_completed_epoch_batch_evidence(...)` reader; those modules need no new
   class contract. A duplicated source-class value is forbidden rather than reconciled.
5. Build the read-only compiler over exact epoch production receipts, completed batch
   evidence, transition bytes, dependency/target denominators, claim lifecycle lineage,
   canonical temporal scope/capability evidence, and OWR limitations.
6. Preserve typed negative results. Do not turn lack of a recompute executor into
   `pending` or lack of a signer into an exception.
7. Prove positive, mixed, contested, stale, missing-denominator, and both declared-
   absence paths.

**Red first:** stale-as-current, six-class flattening, class-wide appeal, missing
propagation edge, fake recompute receipt, caller-supplied OWR status, consumer-asserted
gate predicate.

**May not:** appoint a signer/verifier/holder; create a second claim lifecycle; add UI;
use architecture allocation prose as runtime evidence; infer status from field/class
presence; add a caller-authored class to `DecisionDependencyEvent`; infer a legal change,
appeal outcome, retraction/correction, or discovered bias from unbound strings/metrics.

### C02 — live intake, temporal HTTP bridge, and owner composition

1. Wire the existing Decision Validity POST's `monitor_event_ref` arm to exact event
   readback, lifecycle-bridge invocation/persistence, and derived generic event/epoch
   binding. Prove definition-only/test-only reachability becomes a production call.
2. Add the `RUNS_REVIEW`-authorized replay-bound GET under the temporal router.
3. Extend canonical `TemporalService`; compose the projector from its `TemporalScope`
   and existing owner repositories/providers. Prove the control and temporal routes do
   not create sibling time grammars.
4. Ensure a run with absent authority returns `200` with a typed first-class state. A
   malformed/unresolvable artifact still receives the existing problem response.
5. Add live OpenAPI examples for positive fixture-only and real production absence.

**Red first:** keep POST/GET markers but remove the lifecycle/projector call; submit a
free-standing/mismatched class; replace exact artifact readback with a shaped object;
mutate nested enum/hash; call with another tenant's run; call as VIEWER and as REVIEWER;
vary server read time while owner-validity time is absent; bypass `TemporalService` with
locally reconstructed valid/tx fields.

**May not:** add a new permission, unauthenticated public endpoint, mutation, local
signer, or UI-derived authority.

### C03 — pre-WAIT schema/package bridge

Regenerate the frozen OpenAPI snapshot and the five package-client outputs from the
canonical generator. The receipt must show both the new GET and the already-live epoch-
batch POST. Do not hand-edit JSON and do not touch the dashboard generated type yet.
Regenerate the public-stable inventory/reference pair with the registered guardrails
generator and `--skip-deep-import-baseline`; reject any diff outside the two declared
public-surface outputs and keep `public_surface_inventory_reviewed` false until owner
review.

This checkpoint is explicitly `bridge_missing` until C04 regenerates the dashboard
family. It is not a closure point.

**Red first:** corrupt one generated operation/enum in harness scratch and require the
drift gate to fail.

**May not:** touch `apps/runtime-dashboard/**`, suppress generated drift, or weaken the
contract checker.

### WAIT-DS11 — mandatory serialized boundary

Stop before the first C04 path. Frontend work may begin only when all are true:

1. DS11 is landed on the designated integration branch and its landing commit is
   identified from that branch, not from the live DS11 worktree;
2. if C01-C03 already produced append-only DS18 commits, perform one ordinary
   **source-sync merge** from that DS11-containing integration branch into the attached
   DS18 feature branch. This merge is required integration input, never publication of
   DS18; rebase/reset/cherry-pick substitution is forbidden. If it conflicts in a
   DS11-owned path, stop for owner adjudication rather than invent a resolution;
3. after the source-sync merge, the DS11 landing commit is an ancestor of DS18 `HEAD`,
   the branch is attached, and the tree is clean. If execution did not begin before
   DS11, start from the post-landing integration head and no source-sync merge is needed;
4. DS11's branch/worktree no longer owns an unlanded frontend path set;
5. derive the complete final `DS11 base..landing` path set twice and report its set
   difference from the planning-time 63-tracked/64-live union. The planning numbers are
   historical evidence, not a stop predicate: the formerly untracked snapshot may be
   tracked at landing and new owner paths must be reported rather than forced away;
6. DS11's exact-byte loader and strict recursive admission are read from the landed
   branch, not copied from an unmerged worktree;
7. the frozen install is revalidated against the landed lockfile, and repeated if that
   lockfile changed; no TypeScript scanner result predating the landed dependency graph
   is trusted;
8. the C04-C06 declared path fence is re-read against landed owners. A moved owner path
   spends one widening round; it is not silently substituted.

The frontend slice base for P41 is the DS11 landing base, not the original DS18 planning
base and not the cluster entry from C01.

### C04 — strict client admission and MACHINE

1. Atomically regenerate `apps/runtime-dashboard/src/api/types.ts`; all seven generated
   contract outputs must now agree.
2. Capture response bytes before parse/validation.
3. Strictly and recursively validate the captured payload and recompute semantic
   invariants.
4. Expose the admitted object plus copied raw bytes to the UI.
5. Download only the captured bytes.

**Red first:** semantically equal key reorder, unknown nested field, omitted dynamic
source class, altered denominator/hash, and reserialized twin.

**May not:** hand-fetch around the generated client, use a shallow
`Record<string, unknown>` validator, normalize twin bytes, or start before WAIT-DS11.

### C05 — DS4 primitive, details, and truthful default state

1. Extend `TimeSemanticsLabel` and add its explicitly typed provider.
2. Mount compact chrome in the run layout and central decision-bearing chart evidence.
3. Add one inline expandable certificate/dependency/cascade/replay view; do not create a
   second tab/route-registration mechanism.
4. Migrate the declared run list and compare surfaces. Bind the temporal arm into the
   signed public packet and render it through the shared packet panel in both modes.
   Build that packet once in `RunDetailLayout`, after strict epoch admission, and pass
   the same instance to publication readiness, operator craft, and ambient telemetry;
   delete their three direct builder calls.
5. Repair the typed inputs before extending non-page consumers: the existing
   `PublicShareSummary` owner supplies OG and both email forms; the bureaucratic AST
   admission owner supplies HTML. Each accepts canonical admitted state or produces an
   exact typed nonreceipt; trust status, valid-at and render time are never proxies.
6. Extend `OGCard.tsx`, every `generate-og.ts` HTML/Satori/SVG/PNG arm, React and
   plain-text `EmailSummary`, and bureaucratic HTML. Classify `printExport.ts` as
   inherited-DOM and prove it preserves the source temporal node.
7. Render all six classes and the two authority absences as specified above.
8. Add complete active-locale copy (`en` authored primary, `uk` translation) and
   accessibility semantics. Keep the `ru` catalog byte-identical: D4-A1 classifies it
   `legacy_continuity_frozen`, and its key/value hashes are pinned by the parity test.

**Red first:** change underlying as-of/epoch/validity while keeping component markers;
stale-as-current; epoch blend; missing signer as error/empty/disabled; one class rendered
with another's scope treatment; strip the admitted export/packet arm while leaving a
temporal-looking timestamp; keep a positive projection in the hook but omit it from the
single packet producer; OWR freeze removed while label remains.

**May not:** create a second status enum, derive authority in React, use one generic
“changed” badge, hide absence, expose internal refs publicly, use color alone, or reuse
DS6/DS11 visual specs; edit or add keys to the frozen `ru` catalog.

### C06 — complete structural denominator and semantic reconciliation

1. State the property exactly: every production render/export root that communicates a
   recommendation, decision status, limitation or quantity whose interpretation can
   change admissibility consumes admitted temporal context and behaviorally renders
   `as_of`, epoch and validity, regardless of React/page/file extension.
2. Recompute the complete production `.ts`/`.tsx` **source-file** denominator twice.
   For every file, the AST scanner inventories JSX, `React.createElement`,
   React/server/Satori render calls, HTML/SVG template emitters and DOM
   clone/serialization/raster/print roots. Tests, stories and generated files are
   excluded by typed path rule, not a semantic allowlist. Every file—including one for
   which the scanner finds no candidate—needs an independently reconciled
   `render_roots_complete|no_render_root` receipt bound to its source digest. Thus a new
   rendering idiom cannot hide behind the scanner's known-call list.
3. Independently reconcile every render/export root in the landed frontend register as
   `decision_bearing`, `non_decision_bearing`, or `inherits_admitted_dom`. Each
   classification freezes
   `predicate_provenance=independently_reconciled`, component/node identity, source
   digest, owner-contract/render evidence and reviewer receipt. A source digest is only
   a staleness tripwire, never semantic proof. `consumer_asserted`, stale or unclassified
   files/roots keep the metric `not_established`.
4. For every decision-bearing member require both structural ownership and a
   behavioral render harness. An import, DTO name, numeric marker or
   `TimeSemanticsLabel` token alone is not closure.
5. Change the health metric from `not_established` only when structural enumeration,
   independent semantic reconciliation, consumer behavior and fresh source receipts
   all reconcile.

**Red first:** add an unclassified sibling/plain-props JSX helper; add a `.ts` HTML/SVG
template or Satori root with no JSX; keep imports/markers fixed while changing
non-authority copy into a recommendation and then reverse it; remove epoch/validity from
OG, email, or bureaucratic HTML only; mark a DOM-cloning export as inherited while
deleting the source temporal node; keep a `TimeSemanticsLabel` import but delete its
render; render it with fixed values that ignore changed context; delete one registry
member while source remains.

**May not:** edit the DS5 baseline debt manifest, borrow another slice's evidence, use
an enumerated filename allowlist as completeness, or make a marker-based semantic gate.

### C07 — freeze, visual/a11y, and closeout

1. Freeze source before review.
2. Run backend, contract, frontend, checker, visual, and accessibility waves with
   measured budgets.
3. Capture DS18-only snapshots for real declared absence, content-bound positive test
   fixture, stale certificate/dependency cascade, six event classes, OWR freeze, and
   cross-epoch replay.
4. Run delta-only re-review after the first full review.
5. Re-open the failure register, read back the branch, and issue the final capability
   labels.

**Red first:** snapshot root absent; visual uses only color; keyboard cannot reach epoch
boundary/lineage; fixture marker disappears; MACHINE bytes differ.

**May not:** make post-freeze cosmetic source edits, rerun an unscoped `guardrails sync`,
substitute a full suite for focused property tests, rewrite a failing baseline, push,
merge, or rebase. The scoped pre-freeze public-surface regeneration in C03 is mandatory,
not a closeout repair.

## 13. Widening budget and bucket rule

The slice has **7 widening rounds**, one for each independent uncertainty seam exposed
by the census:

1. an additional persisted epoch-result family needed by the compiler;
2. a missing canonical source→claim/publication lineage read seam;
3. a missing OpenWorldRisk public-limitation read seam;
4. a DS11 landing owner-path change;
5. a newly discovered decision-bearing surface family;
6. a changed generated-client owner/command;
7. an accessibility/visual owner seam not reachable from the declared test harness.

A round is spent only when the capability or owner/path family expands. A narrowing
repair inside the declared family does not spend a round. On the **second** finding of
one class, apply P40: widen to the true quantity or declare a bounded residual with its
falsifier and smallest missing capability. Do not patch another instance. A finding
already covered by that bounded residual is a worked example, not a new round.

Any out-of-list mechanism path requires all of:

- the DS18 closure item it serves;
- the existing declared seam that was tried and why it is insufficient;
- the source evidence identifying the canonical owner;
- the widening round and remaining path ceiling;
- a branch receipt before edit.

## 14. Pattern pass

| Pattern | Opening finding | Target correct pattern / acceptance |
| --- | --- | --- |
| P01/P02/P12 | rich contracts and one source-only route do not make the surface chain real | exact producer/readback → route → frozen schema → all clients → strict consumer → DOM/MACHINE |
| P03 | epoch/cascade/OWR richness is mostly in-process | one typed authorized read projection exposes it without flattening |
| P04/P09 | generic lifecycle, certificate staleness, OWR and UI interaction states can diverge | one composed projection keeps source states distinct and weakest-boundary behavior explicit |
| P05/P15 | React could invent currentness, event class, or positive demo authority | UI is projection-only; typed absence is the production default; positive fixtures are marked and barred |
| P07/P08 | replay and multiple time roles can blend | rule/schema/epoch refs plus independent valid/tx/source/payload/observed/cache roles; visible boundary test |
| P10/P29 | badges or marker checks can pass without semantics | real artifact resolution, recursive semantic validation, rendered mutation tests |
| P14 | one source/event can be visually inflated into independent support | show exact source/lineage and denominator; no count-based confidence |
| P27/P31 | a control-local time grammar, caller-authored class, or three sibling packet builders would bypass canonical owners; per-page badges repeat the defect | canonical `TemporalService` + persisted monitor-event intake + one DS4 primitive + one generated boundary + one run-scoped signed-packet producer |
| P32/P33/P38 | presence, class name, route marker, import, or status string could proxy authority | remove-property-keep-marker and adversarial sibling/alias/malformed variants |
| P35/P36 | sampled paths or adjacent prose could become a universal claim | complete source/register denominator and finding-ID/source anchors; unresolved denominator stays not established |
| P37 | caller/config could declare the predicate that turns the gate | provenance class frozen at admission; consumer assertion never establishes authority |
| P39 | tests/generated records could make the mechanism cap arithmetically false | mandatory companions named and excluded; one mechanism never split to fit cap |
| P40 | repeated chart/page patches could climb the same ladder | second same-class finding widens the mechanism or declares a bounded residual |
| P41 | DS11/main reds could be misattributed | replay exact command from the correct slice/cluster base and prove zero input-denominator intersection |

Opening capability labels:

- semantic epoch production: `implemented` with positive authority still
  `absent/unallocated`;
- epoch-transition production: `implemented_but_not_orchestrated` and signer/producer
  identity `absent/unallocated`;
- epoch-batch HTTP: source route implemented, generated bridge missing, standard
  verifier producer missing;
- monitor-event source-class/propagation: contracts/producers/bridge are
  `implemented_but_not_orchestrated`; C01-C02 must establish exact event persistence and
  a live POST → persisted bridge → read projection chain;
- derived recompute execution/status: `absent/unallocated`;
- family audit/API/dashboard: `surface_missing`;
- DS4 consumption and universal coverage: `consumer_missing` and
  `semantic_test_missing`;
- MACHINE twin: `surface_missing`.

The slice closes only the labels actually demonstrated. It does not round upstream
institutional absence or a missing recompute executor up to implemented.

## 15. Verification and measurement protocol

Before every command, record `uptime`; run with `/usr/bin/time -p`; record exit status
before any pipe; then record `uptime` again. The journal records `real`, `user`, `sys`,
`user + sys`, and load before/after. Measure every suite once before assigning its
timeout. A timeout is derived from the measured maximum plus observed contention; an
unmeasured default is a tooling nonreceipt.

Focused commands, adjusted only to the landed package scripts:

```text
uv run pytest tests/unit/runtime/quality/test_epoch_staleness_projection.py \
  tests/unit/runtime/quality/test_epoch_validity_cascade.py \
  tests/unit/scientist/validation/test_decision_validity_service.py \
  tests/unit/scientist/governance/continuous/test_monitors.py \
  tests/unit/scientist/governance/continuous/test_incident.py \
  tests/unit/scientist/governance/continuous/test_invalidation.py \
  tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py -q

uv run pytest tests/unit/runtime/http/test_decision_validity_api.py \
  tests/unit/runtime/http/test_temporal_api.py \
  tests/unit/runtime/http/test_control_service_di.py \
  tests/integration/runtime_quality/test_monitor_event_lifecycle_intake.py \
  tests/integration/runtime_quality/test_chronology_protocol_conformance.py -q

uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
uv run polisyos-tools architecture guardrails check
uv run pytest \
  tests/repo_quality/architecture/test_public_surface_supported_entrypoint_inventory.py \
  tests/repo_quality/architecture/test_public_api_facades.py \
  tests/repo_quality/tools/test_docs_gate.py -q

corepack pnpm --filter @polisyos/runtime-api-client run generate
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api

python3 architecture/atlas_surfaces/check_frontend_disposition_register.py --check

corepack pnpm --dir apps/runtime-dashboard exec vitest run \
  src/features/runs/domain/epochStaleness.test.ts \
  src/features/runs/domain/publicationPacket.test.ts \
  src/features/runs/components/EpochStalenessView.test.tsx \
  src/features/runs/components/PublicationPacketPanel.test.tsx \
  src/features/runs/routes/RunDetailLayout.test.tsx \
  src/features/export/social/OGCard.test.tsx \
  src/features/export/social/EmailSummary.test.tsx \
  src/features/artifacts/bureaucratic/ast/bureaucratic-document-ast.test.ts \
  src/features/artifacts/bureaucratic/export/parity-check.test.ts \
  src/shared/export/printExport.test.ts \
  src/shared/ui/temporal/TimeSemanticsLabel.test.tsx \
  src/shared/charts/quantityChartSemantics.test.tsx

corepack pnpm --dir apps/runtime-dashboard run typecheck
corepack pnpm --dir apps/runtime-dashboard run lint
corepack pnpm --dir apps/runtime-dashboard run test:a11y:components
corepack pnpm --dir apps/runtime-dashboard exec playwright test \
  e2e/ds18-runtime-dashboard.visual.spec.ts \
  --config=playwright.visual.config.ts --project=chromium
```

Run changed modules plus importer tests, recomputing validators with a corrupt-field
probe, Ruff, and architecture guardrails during iteration. Freeze source, complete all
reviews, then run the expensive backend verify/CI-parity wave once. Serialize only
Playwright/Storybook/fixed-port/shared governed-artifact work; run lint, typecheck,
logic tests, and read-only censuses in parallel.

For P41, a red is inherited only when the exact command reproduces on the correct
pre-slice base and the changed paths intersect its complete input denominator at zero.
If replay cannot be done, provenance is `not_established`.

## 16. Explicit non-closure and forbidden work

DS18 does not:

- appoint the epoch predicate-policy signer, transition signer, independent holder, or
  Decision Validity verifier;
- make an institutional appointment a UI action or defect ticket;
- build a global derived-data recomputation executor; it reports the actual executor
  status and typed absence;
- establish whole-history authenticity when the independent holder remains absent;
- create a new claim/case/publication lifecycle owner;
- publish or resign public records; DS12 remains the public-signature owner;
- create a second temporal/status/event vocabulary or a generic “changed” class;
- expose protected reviewer evidence through a public endpoint;
- modify `docs/plans/active/DEBT-REGISTER.md`, another slice's plan/journal/receipts/
  snapshots, the DS5 baseline debt manifest, or the deep-import baseline;
- hand-edit generated artifacts, run unscoped `guardrails sync`, push, merge DS18 into
  an integration/publication branch, rebase, reset, or detach HEAD. The scoped C03
  public-surface regeneration with `--skip-deep-import-baseline` is mandatory; the one
  append-only DS11-containing source-sync merge required by WAIT-DS11 is the only inward
  merge. Neither is performed during this read-only planning task.

## 17. Hand-back summary

### Census, independently derived

- N12: `24` commits and `174` paths, each derived twice.
- Runtime routes: `17` files / `105` decorated operations, twice derived; two SSE
  operations are deliberately hidden from OpenAPI.
- Frozen OpenAPI: `100` paths / `102` operations, twice structured-derived.
- Exact drift: the visible source set has one extra operation — epoch-batch admission.
- Source denominator: `2,600` Python files, twice derived; the rejected 2,599 pathspec
  and its missing root file are recorded.
- DS4 production consumers: zero, from two complete identifier walks.
- Existing DS5 decision-bearing data: 21 resolutions / 10 paths by two parsers, explicitly
  only a lower bound because the owner says the exhaustive relation is not established.
- DS11: 63 tracked held paths; 64 live collision paths after one untracked snapshot;
  both live-union methods agree.

### Reachable versus in-process

- Routed and frozen canonical time owner: temporal capabilities and
  `TemporalScope`/`TemporalRef`; no epoch-staleness composition yet.
- Routed and frozen: generic Decision Validity event and run/packet summary surfaces.
- Routed in source but absent from schema/clients: epoch-batch admission.
- Public typed contracts without a dedicated read route: semantic production receipt,
  batch/gate/pre-N9 artifacts and nonreceipts.
- In-process/artifact only: semantic resolution/history details, transition artifact and
  signer nonreceipt, dependency/target vector, OWR vector/replay/limitations; canonical
  monitor-event producers and lifecycle bridge exist but each has zero production calls
  by AST and literal derivations.
- Absent/unallocated: epoch-aware derived recompute execution/status producer and the
  two institutional signers.

### Six-class rendering

Incident, appeal, correction, retraction, legal change, and discovered bias retain
distinct labels, shapes/glyphs, scope language, evidence detail, and MACHINE values.
They share only the downgrade-before-adjudication law. Event class never collapses into
disposition; one upheld appeal stays instance-scoped; supersession lineage is visible.

### Declared absence

The default screen is a useful `Authority not appointed` state with exact role, refusal
code, scope, refs, consequence, remaining inspectable data, and closure condition. It
is not error/empty/loading/disabled, and it offers no appointment/bypass action.

### Frontend wait point

C00-C03 may execute without DS11 and touch only backend/schema/package-client paths.
The hard stop is immediately before C04's first `apps/runtime-dashboard/**` path.
C04-C07 begin only after the WAIT-DS11 receipt above is satisfied.
