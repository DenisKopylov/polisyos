# Runtime HTTP Services (`polisyos.runtime.http.services`)

`runtime.http.services` contains the application logic behind the runtime API. It owns run indexing,
timeline/debug views, artifact inspection, lineage traversal, and control-plane orchestration.

## Purpose

Use this package for route-adjacent runtime API behavior that needs shared
business logic, CAS/artifact access, run lifecycle orchestration, or read-side
projections. Route handlers should stay thin and delegate behavior here.

Ordinary NL compilation binds every factory client to the live job's logical run,
actual attempt, producer ledger and cache dependencies. `control/producer_basis.py`
reopens each actual returned pending ledger begin before dispatch and persists its typed
version2.0 receipt. The parent attaches those independent refs to the existing Core trace;
only a closed, complete admission basis can support fresh monetary reconciliation.
Closure never waits on timed-out factory callbacks, trace writers or the monetary I/O
mutex. Dependency unavailability/timeout preserves the existing typed retryable boundary
and cannot authorize replacement provider work.

Fresh job status joins the current terminal Core source, exact selected V3 proposal ref
and manifest profile, Core run and attempt, then compares the complete reopened begin set
with the current ledger. This includes actual sibling factory dispatches without a
proposal observer. Missing/extra/drifted rows or a different source withhold the cost
projection. It preserves the selected NL queue payload reader and cancelled-job
verification; historical jobs without the exact source basis are explicitly limited.

Legacy unknown tenant/actor scope remains candidate state, but ordinary queued NL work
that would create LLM producers now has an explicit costed refusal:
`nl_producer_ownership_not_established`, with authenticated scoped resubmission as the
path forward. No tenant or producer owner is synthesized from ambient context. This does
not change an unknown target-world profile into execution authority or alter pure candidate
calculations outside this protected physical-work route.

The research NL POST's existing provider preflight is a direct consumer of the shared
prepared-cache request. Its digest check and physical completion use the same real gateway
plan. Preflight retains only the cache resource/origin reference and creates fresh wrappers
per invocation; it does not share mutable tracing hooks or infer a digest from a report.
The existing pre-admission actor/run/profile/ledger and origin checks remain in force.
The actual research POST pre-admission replay, distinct same-binding reuse event, altered
or missing origin controls and late physical settlement are mandatory verification inputs.

## Role in System

- **Depends on:** `core.artifacts`, `core.contracts`, `core.trace`, `core.security`, and the domain packages used by control-plane calls.
- **Used by:** `runtime.http.routes` and the FastAPI app.
- **Boundary function:** keeps request handlers thin while centralizing runtime business logic.

## NL JSON admission

The NL request owner separates raw candidate JSON from declared closed nested DTOs before
snapshot/body serialization. Open `Any` fields retain Python-mode finite/representability
validation; only closed model subtrees use their existing typed JSON serializers. This admits
normalized typed temporal instants without laundering raw candidate datetime, byte, decimal,
unknown or non-finite values. Authorization digest and snapshot profile rules stay unchanged.
Runtime HTTP errors remain structured problems, but their exception state is mutable so ordinary
context-manager and middleware propagation cannot replace the intended status/code with a frozen
instance error.

## Selected NL temporal intent

`control/temporal_scope.py` owns materialization and exact-profile replay of a caller-selected
NL request cursor. The existing intake, durable `job_created` record, admitted worker, and fenced
`job_progress` transaction carry its queue identity and typed request binding. Scope payloads
preserve unset axes and explicit nulls under Core canonical JSON 0.2; the selected manifest carries
Runtime producer, request-payload input, tenant/cell, and candidate-only job/run provenance.
`runtime_quality_artifact_refs.time_context_ref` exposes the selected cursor view through the
existing job response. This is requested-view identity only; actual data-view consumption and
policy/legal admissibility require their independent owners and remain limited until admitted.

## Observational source custody

`control/observational_source_access.py` reconciles an authenticated request,
current admitted job, or authorized Direct reader with the actual enforcing
Core read owner before source bytes transfer. Core retains responsibility for
current blob and exact selected-view permission checks. Source tenant metadata
remains provenance; derived candidate artifacts use the actual admitted writer
context. This scoped software check does not establish protected TC authority,
external permission issuance, source suitability, or production currentness.
See [the source-access boundary](../../../../../docs/reference/runtime-observational-source-access.md)
for supported carriers, compatibility, and verification requirements.

## Key Concepts

- **Run index** - caches run records from `core_runs_root` and handles pagination/filtering.
- **Timeline/debug** - converts trace records into ordered, inspectable runtime views.
- **Artifact inspection** - renders CAS manifest/content/schema/lineage views with redaction hooks.
- **Lineage traversal** - builds lineage graphs and completeness summaries.
- **Control-plane orchestration** - launches or reissues runs and bridges into `scientist`, `fabric`, and `lex`.
- **Search HTE completion delivery** - persists a Search-specific outbox event after a completed HTE job and retries pending rows through embedded-worker maintenance. A delivery left pending while the worker holds the job execution fence becomes eligible at the next due maintenance iteration after the handler releases that fence, while the worker remains active. The default 60-second maintenance cadence is not a delivery deadline. An injected CAS establishes filesystem delivery only through an exact `FileSystemCAS` or the `RuntimeApiContext` verifier bound to that same store; unknown backends remain pending.
- **Legacy/private selected NL final claims** - in the legacy `_execute_nl_pipeline` path, a
  selected CAS reference is resolved through its exact producer-selected Core profile before the
  inline report is admitted. When both are present, the private consumer requires their decoded
  reports to agree; a missing, corrupt, malformed, or item-level refused selected reference
  becomes a typed refusal that blocks citation/grounding admission. An inline-only report remains
  supported only when the variant has no selected reference. This private-path description does
  not establish consumption by the ordinary `/runs/nl` route. Separately, the tested normal
  POST/worker job boundary projects a shared CAS availability failure as a dependency failure; it
  is not treated as selected-artifact absence.
- **Atomic control-job admission publication** - the request owner freezes a candidate
  creation basis and prepares diagnostic payload/CAS bytes before the creation writer runs.
  The existing SQL owner records the job, actual `job_created` event/outbox, reconciles those
  facts against the prepared v2 admission bindings, and commits diagnostic rows plus their
  initial progress references together. A terminal admission refusal is initialized once;
  after publication request code only wakes the worker and cannot overwrite its progress.
  There is no reserved global event ID, staged job state or new activation owner.
- **Control-job diagnostic binding** - new creation-time diagnostics use
  `polisyos.runtime.control_job_admission_binding.v2`: exact creation-payload content, job/run,
  original artifact references, preparation time and diagnostic-only purpose. Preparation is
  not a delivered event, current-source proof, worker lease or authorization. The fresh
  `get_job_admission_diagnostic_source_event_record` reader reconciles a resolved/hash-bound
  payload with the actual unique creation event/outbox and returns its real event ID/row time.
  `RuntimeDiagnosticEventLog.load_payload` performs CAS I/O before this SQL-only reconciliation.
  Old v1 admission records and running/completed/failed bindings keep their original meaning;
  a strict v1 parser refuses the distinct v2 profile, and unknown v2 profiles refuse admission.
  Running/terminal diagnostics read their v1 source proof, prepare CAS outside the writer lock,
  then re-read the same scope/attempt/event-content binding before SQL-only append. A current
  lease loss or changed source after I/O refuses publication. Nested preparation under an
  existing Store transaction refuses before CAS.
  `prepared_at`, diagnostic `event_time` and the diagnostic/source row `created_at` retain
  separate roles: a job phase transition receives the actual recorded creation-event time,
  while its prepared CAS body is unchanged. Payload/CAS-write observations retain their own
  occurrence time; row `created_at` is recorded during actual SQL publication at
  the Store's existing whole-second UTC precision. That row time is not a total
  ordering against a source event's more precise timestamp. Readers preserve the
  actual stored value and keep the phase event's exact source time separately.
  The generic top-level `attempt` remains the control-worker lease attempt; evaluation-step
  attempts stay in their own nested rows. Dev diagnostic preparation stays best effort with
  an explicit initial limitation and only real diagnostic IDs; serious-profile failure refuses
  before job publication. A rolled-back SQL publication may leave unreferenced CAS candidates.
- **Control-job cancellation projection** - durable job `state` and response
  `execution_status` carry the cancellation disposition. The existing owner
  preserves the last worker progress and adds its verified `cancellation` record;
  a generic `progress.state` can retain the earlier pending/running observation.
  The job-status reader reconciles the cancelled row, source event and outbox
  and exposes `publication_fenced` with `physical_stop_status=not_established`.
  Generic progress does not establish current job authority or physical termination.
- **Guarded confidence risk spend** - resolves the governed N11 source through
  its real isolated owner validator, preserves source/dependency/registry and
  semantic identities, and composes the strict reviewer-only four-arm packet.
  The generic dynamic-ID projection service cannot emit this guarded source.
- **Human-decision custody** - resolves signed delegation, principal,
  reviewer-separation, presentation, and evidence-exposure inputs before using
  the existing CAS/event writer and durable one-live-record reservation. Public
  gate results remain non-authoritative projections; operational consumers
  must re-resolve the concrete deployment-attested packet.
- **Pre-N9 epoch-validity strangle** - after the candidate denominator is frozen, the control
  service persists an owner-derived subject, reconciles it through the same Decision Validity
  owner used by direct generation, and passes only sealed positive gate evidence to N9. Missing
  predicate-policy admission remains the exact typed negative `policy_admission_missing`.
- **Attempted-evaluation safety custody** - `control/evaluation_safety.py` composes the pure C01
  owners, persists the eight fixed artifact families through the shared CAS/event writer, replays
  public DTOs through canonical owner procedures, and emits complete-denominator informational
  metrics. `EvaluationSafetyAdmissionVerifier` is the dedicated verification-only consumer port:
  every call re-reads the certificate, decision, request, intake, and complete revision lineage from
  CAS, replays C01 with current appointed evidence, and returns C01's challenge-bound receipt
  unchanged. Initial composition and replay share one owner state machine for the complete typed
  absence lattice. Authority reuse/readback binds the exact manifest inputs and complete declared
  envelope/event context plus the deterministically derived CAS-writer attestation ref, so
  identical payload bytes cannot cross request lineage or accept a substituted attestation.
  Resolver and inaccessible-CAS failures fail closed at typed read boundaries; programmer defects
  from canonical authority owners remain visible. Challenges and consumer admission receipts
  remain non-durable and consumer-owned.
- **Attempt admission at the control lifecycle** - `control/run_lifecycle.py` recognizes only the
  strict nested `evaluation_safety_attempt` intake in workflow params or natural-language context.
  Non-simulation attempts are composed, persisted, reduced, and projected before WorkspaceLoop or
  recursive compilation; a blocked attempt terminates with the informational projection as the
  sole business output in the Core run manifest. The container constructs one verifier over its
  own store and event log, ignores promotion state, and exposes no evaluation callback. Explicit
  `simulate_only` transport remains certificate-free and is still rechecked by the evaluator owner.
- **Acquisition-growth custody** - `acquisition-growth` is one non-public,
  read-only governed projection over the complete N13a/N13b owner family. It
  separates structural routes from independently reconciled data gaps, keeps
  ranking distinct from VOI, and exposes historical non-growth and pending
  qualification without executing acquisition or publishing raw quarantine
  bodies.
- **Run-bound acquisition actions** - `AcquisitionActionService` resolves one
  verified completed natural-language run and its exact costed route, composes
  the existing PA2/DS9 gateway, reserves a durable acquisition job, and exposes
  only a strict external owner port. Recovery resumes direct re-entry from the
  persisted action head; it never repeats owner activation or treats the
  fixture badge as production authority.
- **Distinct deferred acquisition actions** - an actual terminal quarantine can
  precede a new, independently authorized job over the saved live evidence after
  policy appointment. The phase-head owner verifies the prior terminal's CAS and
  event custody before allocating the next action generation; the original terminal
  remains immutable. Pending, positive, corrupt, or unknown-effect state cannot
  authorize a fresh fetch or overlapping effect.

- **Public-decision verification reports** - `PublicDecisionVerificationService`
  serializes retained documents and signed reports with the Core encoder under
  the exact profile declared in their manifests. Finite floats therefore use
  Core's typed representation and pass strict fresh reads. Signed records
  preserve aware datetimes through Core's datetime tag so strict readers receive
  typed values; byte conformance alone does not establish DTO validity. A valid
  report authenticates its retained report bytes only; it does not confer publication
  or decision authority.

## Public API

- `ArtifactInspectorService`
- `AcquisitionActionService`
- `AttractorAnalysisService`
- `DebugService`
- `IndexedRunRecord`
- `LineageService`
- `MobilityService`
- `RunIndexService`
- `ScenarioService`
- `TemporalService`
- `TimelineService`

## Internal Layout

- [`__init__.py`](__init__.py) exports the documented service classes used by
  runtime HTTP routes.
- [`run_index.py`](run_index.py), [`timeline.py`](timeline.py),
  [`debug.py`](debug.py), [`artifact_inspector.py`](artifact_inspector.py),
  and [`lineage.py`](lineage.py) own core read-side API behavior.
- [`control/__init__.py`](control/__init__.py) is the lazy package boundary for
  the existing public control API; direct child-module imports do not load the
  public API aggregator.
- [`control/api.py`](control/api.py), [`control/run_lifecycle.py`](control/run_lifecycle.py),
  [`control_worker.py`](control_worker.py), and
  [`control_plane_store.py`](control_plane_store.py) own the public service
  aggregation, run lifecycle, worker, and durable control state behind
  route-layer adapters.
- `control/run_lifecycle.py` retains the canonical service class and worker
  entrypoints. The `control/job_*.py` modules split diagnostics, scope
  admission, attempt publication, and natural-language admission, execution,
  and publication; `control/job_nl_context.py` carries typed state across those
  internal facets.
- [`control/evaluation_safety.py`](control/evaluation_safety.py) owns the typed evaluation-safety
  persistence/reconciliation adapter, the single-operation admission verifier, and the public
  metrics-projection read-identity accessor. The verifier exposes only
  `require_admission(context, challenge)` and has no route, executor, scheduler, callback,
  transport, cache, or broad control-store dependency.
- [`control/run_lifecycle.py`](control/run_lifecycle.py) owns the fail-closed composition boundary
  that invokes that adapter before an attempted evaluation can enter a runtime executor and records
  only its informational projection in control progress and terminal Core output.
- [`human_decision_contracts.py`](human_decision_contracts.py) defines strict
  route/service contracts, while [`human_decisions.py`](human_decisions.py)
  owns signed-input reconciliation, append-only record custody, reservation
  recovery, and operational revalidation. They reuse the access-audit trail and
  control-plane artifact/event path; they do not establish a second log.
- [`acquisition_surface_contracts.py`](acquisition_surface_contracts.py) owns
  the strict DS15 DTOs and sole `GapClass` enum;
  [`acquisition_surface_projection.py`](acquisition_surface_projection.py)
  recomputes the composite read projection and raw-sibling strangle. The
  governed projection service and its isolated validation worker content-bind
  all 3 N13a and 43 N13b files before serving it.
- [`acquisition_action_service.py`](acquisition_action_service.py) owns the
  run-bound costed-route projection and deferred PA2/worker composition. It
  consumes the control-plane phase-head sink and strict owner port without
  becoming a passport, overlay, epoch, or world writer.
- [`acquisition_admission_bundle.py`](acquisition_admission_bundle.py) owns the deterministic,
  acquisition-only admission producer. Its default production signer slot is empty; a
  configured signer persists, signs, reconciles, reads back, and maps one bundle for the existing
  agent-action gateway, while institutional delegation and current-mandate resolution remain
  gateway-owned.
- [`acquisition_authority_configuration.py`](acquisition_authority_configuration.py)
  defines the internal, purpose-scoped deployment selectors and separate admission
  and decision signing slots. [`acquisition_authority_provider.py`](acquisition_authority_provider.py)
  composes those captured inputs with the existing PA2/DS9 owners for both HTTP
  requests and durable workers. Each use reopens exact signed delegation,
  independent currentness, action permission, and human-decision custody; an empty
  or mismatched slot refuses. Neither configuration nor an LLM appoints an owner.
  Selected decision-information failures now preserve the owner’s exact finite
  refusal code and selected plain CAS-ID replay refs through the existing decision
  writer. Whole-store read failures from this preflight or signed-source resolver
  remain dependency failures; the change does not fabricate manifest profiles or
  extend into the admission producer’s separate persistence/error path.
- [`confidence_ledger_risk_spend_contracts.py`](confidence_ledger_risk_spend_contracts.py)
  owns the four-arm transport and replay binding;
  [`confidence_ledger_risk_spend_projection.py`](confidence_ledger_risk_spend_projection.py)
  composes only worker-admitted owner facts into the C01 domain projection.
  [`governed_projection_validation_worker.py`](governed_projection_validation_worker.py)
  remains the sole `tools.*` validator import boundary.
- [`adapters/`](adapters/) contains service adapters for core runtime state and
  should stay thin.
- Scenario, temporal, mobility, attractor, feedback, and rendering services own
  domain-specific API projections without adding route logic.

## Extension Points

- Runtime middleware extensions are declared at the parent HTTP layer through
  the `polisyos.runtime_middlewares` entry-point group in
  [architecture/extension_points.toml](../../../../../architecture/extension_points.toml).
- This service package is not itself an extension host. New service behavior
  should be route-owned, covered by OpenAPI tests, and exposed through
  [`../routes/README.md`](../routes/README.md) when public.

## Tests

Run from the repository root:

```bash
uv run pytest tests/unit/runtime/http -q
uv run pytest tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_api_maturity.py -q
```

Focused service tests live under
[tests/unit/runtime/http/](../../../../../tests/unit/runtime/http/). Update the
OpenAPI contract tests whenever response shape or route-visible behavior
changes.

## Operability Links

The migration owner for acquisition runtime composition is `team-runtime`.
Before enabling a route, supply its canonical owner cost-schedule row, exact
deployment-selected route/cutoff inputs and finite re-entry budget, and the
independently signed mandate, currentness, human-decision and epoch/GY admissions.
Check the route and durable job projections after each closing act. A supplier
receipt alone establishes neither GY admission nor debt-register closure.

DS9 custody runs as one guarded operation while holding the durable write fence.
A dependency timeout reports unknown acknowledgement: the original worker may
still commit a valid signed record. Preserve the fence, read the exact reservation
and signed record through their existing owners, and reconcile known committed or
recovery-required state before another action. Do not clear reservations or retry
an effect merely because its caller timed out. The same rule applies to unknown
admission/re-entry outcomes; automatic recovery only reconstructs verified known
results. Rollback must preserve these durable receipts and fences.

The dashboard's nongenerated acquisition route adapter accepts the current strict
negative/positive wire union. Native qualification and positive observation delta
remain independent of action authority and publication eligibility. The canonical
generated client is unchanged; consumers of its older strict route decoder must
adopt the current adapter/DTO before consuming these projections. See the
[acquisition movement release fragment](../../../../../release-fragments/unreleased/2026-09-13-acquisition-movement.toml)
for the compatibility and rollout boundary.

- [Runtime component SLO](../../../../../ops/components/runtime/slo.yaml)
- [Runtime component runbooks](../../../../../ops/components/runtime/runbooks.md)
- [Runtime API outage runbook](../../../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Use control plane how-to](../../../../../docs/how-to/use-control-plane.md)

## Known Shims/Deprecations

- There are no active package-local shims for `runtime.http.services` in
  `architecture/shims.toml` as of 2026-05-06. `control/__init__.py` is the real
  package initializer, not a compatibility module layered beside the package.
- The bounded lazy `control/__init__.py` package boundary is tracked in
  [architecture/module_size_budget.toml](../../../../../architecture/module_size_budget.toml)
  with owner `team-runtime` and sunset `2026-12-31`. The former `control.py`
  bytes are retained as a non-importable historical record.
- Public response changes must go through OpenAPI snapshot checks and generated
  client compatibility notes before old fields are removed.

## Current State

- Last updated: 2026-08-29
- The tree still centers on `artifact_inspector.py`, `debug.py`, `lineage.py`, `run_index.py`, and `timeline.py`.
- The control service continues to support feedback evaluation, reissue, and data/Lex orchestration surfaces.

## Run-bound predictive calibration

`predictive_calibration.py` binds the selected Core manifest to its completed control job, reopens exact candidate and observed run-root profiles, runs the existing `ForecastOwner` and empirical bridge, passes persisted evidence through the real S10 consumer, persists an exact-profile association, and appends its ref to the existing diagnostic event log. GET replay recomputes the event payload hash, reopens the association and evidence, verifies the complete run/job/control-run/manifest binding, and recomputes S10 against the selected manifest view. The projection remains limited and predictive-only with issuer, source-time, population, and counterfactual credibility marked `not_established`.

The association copies the evidence artifact's typed `failure_codes` into `evidence_reason_codes`; GET replay checks that projection against reopened evidence.

The POST producer and GET reader run inside the exact catalog source context
owned by the app's `ControlPlaneService`. Profile validation resolves its
canonical Data Forge owner from that source's configured repository and overlay
paths; absent request context fails closed for a selected profile. This path
selection establishes neither source provenance nor currentness, and the
profileless legacy request remains a candidate-only path.

The shared runtime operation owner uses the purpose-neutral `run_operation_idempotency.py` contract and a shared SQLite/PostgreSQL owner table in `ControlPlaneStore`. Its unique scope is purpose, tenant, cell, authenticated-principal digest, typed `scope_kind`/`scope_id`, and caller intent; run-bound Forecast uses the actual run id as `scope_id`, while route-owned NL pre-admission uses a fixed route scope and retains the actual candidate run id as provenance. The body digest separately binds full selected refs and the exact run-manifest profile or launch intent. Same-scope concurrent callers share one database claim across app instances, changed bodies conflict, and the Forecast publication event plus exact association ref and completed row commit in one database transaction. An interrupted process can leave `pending`; the owner does not automatically transfer or rerun ambiguous work, and requires manual reconciliation. This is local database admission, not external provider exactly-once execution. Previously published pre-R229 events do not carry the principal scope, so matching legacy retries fail with `legacy_intent_scope_unverifiable` instead of being replayed or silently duplicated. SQLite two-instance and process-race tests are authored but UNRUN; PostgreSQL runtime behavior also remains UNRUN.



R3 pre-admission is a route-owned consumer of the same SQL claim table. Its typed attempt row is a read projection; the original authenticated scope and immutable request digest bind the route identity, while append-only observation rows bind provider settlement references and admitted/refused/cancelled/failed outcomes. Initial shared claim and attempt projection commit atomically. R3 duplicate route requests cannot bypass the owner through the generic `X-Idempotency-Key` response cache; rate limiting and mutation audit still apply. Legacy Forecast rows alone receive `run` scope migration from stored `run_id`; unknown scope rows fail closed.

## Selected final-policy-claims lineage

Natural-language model variants retain the producer-selected `ArtifactRef` for their Trinity
bundle and final-policy-claims artifact alongside the legacy artifact-ID fields. The claims
artifact manifest is written with the exact selected Trinity profile as its input. The citation,
grounding, claim-registry, conflict, security, and adjudication report inputs carry the selected
claims profile through `InputRef`, so equal payload bytes from different variant lineages do not
collapse to an ambiguous artifact ID.

The current run binds each variant to the exact `ArtifactRef` returned by that variant's
producer, keyed by its immutable `model_variant_id`. It validates every legacy or typed projection
that is present against that map before downstream consumer manifests are written. A valid typed
projection can carry the edge when the legacy ID projection is absent; a matching legacy ID can
carry it when the typed projection is absent. If both projections are absent while the producer
map contains an artifact, or any supplied projection is malformed or disagrees, the selected edge
is refused. When the producer map has no entry and neither projection is supplied, the dependency
is genuinely absent; a stray typed projection is refused and legacy-only history still requires
Core to resolve one exact profile. An inline report is compared with the selected persisted report
before it is consumed. These refs identify selected stored views; they do not establish citation
quality or policy authority.

Each serious-run prompt/tool ledger is emitted for one model variant. Its CAS manifest records
same-variant producer-selected Trinity and final-policy-claims refs as `InputRef` edges derived from
the producer map, retaining each selected manifest profile even when sibling variants share an
artifact ID. The existing ledger payload keeps its strict v1 ID-string fields for rendered inputs,
outputs, and authority handoffs. The scorecard validates that payload and its runtime ledger ref; it
does not resolve those nested strings against the ledger manifest. Do not treat those legacy strings
or the ledger's reported handoff status as independent profile-qualified authority evidence.

## Bounded method-sidecar inspection

Fresh content and schema previews obtain the first selected manifest through
Core's bounded owner port at the existing `INSPECTOR_MANIFEST_MAX_BYTES` limit,
before a JSON parser or payload loader. An over-cap header or backend lacking
that bounded port refuses; there is no unbounded load fallback. Qualified `.2`
content keeps its existing interpretation.

Only `.3` MethodArtifactOutputPayload sidecars route through the public Foundry
source-owned reader. The kind is a dispatch hint; full actual selected owner,
media/schema/profile, producer revision, source roles and primitive value domain
are rechecked before the payload is interpreted. The actual Method kind or
source schema identifies that cohort even when kind and media are jointly
substituted; malformed full selectors refuse before payload load. Unknown JSON
`.3` owners refuse semantic inspection. Truly unrelated non-JSON cohorts retain
raw byte/text inspection with `canon_read_status="not_evaluated"`; that is an
unqualified projection, not canonical value or producer admission. This is a content/schema read projection, not producer authenticity,
method-result adequacy, G acceptance or a change to authority surfaces.

The fresh schema consumer oracle compares its top-level keys with the producer DTO's
actual fields and requires declared byte conformance. A schema-only dispatch removal
is a separate behavioral control; its intact/red/restored runtime checks remain UNRUN.

## Technical inspection evidence

Content and schema previews accept an explicit exact evidence artifact ID and
manifest profile through the HTTP query. The evidence is independently resolved
and rechecked against the selected source and current guarded owner scope at each
consumer gate. This authorizes only technical inspection; it does not confer
closeout, publication, claim, or raw-download authority. Requests without the
selector retain the existing authority path. Responses using the selector require
cache revalidation so a previously admitted scope is not treated as current.
