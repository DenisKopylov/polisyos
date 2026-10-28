# Runtime HTTP Services (`polisyos.runtime.http.services`)

`runtime.http.services` contains the application logic behind the runtime API. It owns run indexing,
timeline/debug views, artifact inspection, lineage traversal, and control-plane orchestration.

## Purpose

Use this package for route-adjacent runtime API behavior that needs shared
business logic, CAS/artifact access, run lifecycle orchestration, or read-side
projections. Route handlers should stay thin and delegate behavior here.

## Role in System

- **Depends on:** `core.artifacts`, `core.contracts`, `core.trace`, `core.security`, and the domain packages used by control-plane calls.
- **Used by:** `runtime.http.routes` and the FastAPI app.
- **Boundary function:** keeps request handlers thin while centralizing runtime business logic.

## Selected NL temporal intent

`control/temporal_scope.py` owns materialization and exact-profile replay of a caller-selected
NL request cursor. The existing intake, durable `job_created` record, admitted worker, and fenced
`job_progress` transaction carry its queue identity and typed request binding. Scope payloads
preserve unset axes and explicit nulls under Core canonical JSON 0.2; the selected manifest carries
Runtime producer, request-payload input, tenant/cell, and candidate-only job/run provenance.
`runtime_quality_artifact_refs.time_context_ref` exposes the selected cursor view through the
existing job response. This is requested-view identity only; actual data-view consumption and
policy/legal admissibility require their independent owners and remain limited until admitted.

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
- **Control-job diagnostic binding** - admission diagnostics bind only to the persisted
  `job_created` record and carry no worker attempt; running, completed, and failed diagnostics
  bind to the exact persisted lifecycle event, its row time and raw-payload digest, and the job's
  stored artifact references. The generic top-level `attempt` remains the control-worker lease
  attempt; evaluation-step attempts stay in their own nested rows.
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
