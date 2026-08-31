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

## Key Concepts

- **Run index** - caches run records from `core_runs_root` and handles pagination/filtering.
- **Timeline/debug** - converts trace records into ordered, inspectable runtime views.
- **Artifact inspection** - renders CAS manifest/content/schema/lineage views with redaction hooks.
- **Lineage traversal** - builds lineage graphs and completeness summaries.
- **Control-plane orchestration** - launches or reissues runs and bridges into `scientist`, `fabric`, and `lex`.
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
- [`control.py`](control.py), [`control_worker.py`](control_worker.py), and
  [`control_plane_store.py`](control_plane_store.py) own control-plane run
  lifecycle behavior and are intentionally kept behind route-layer adapters.
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
  acquisition-only admission producer. Its production signer slot is intentionally empty; a
  configured signer persists, signs, reconciles, reads back, and maps one bundle for the existing
  agent-action gateway, while institutional delegation and current-mandate resolution remain
  gateway-owned.
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

- [Runtime component SLO](../../../../../ops/components/runtime/slo.yaml)
- [Runtime component runbooks](../../../../../ops/components/runtime/runbooks.md)
- [Runtime API outage runbook](../../../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Use control plane how-to](../../../../../docs/how-to/use-control-plane.md)

## Known Shims/Deprecations

- There are no active package-local shims for `runtime.http.services` in
  `architecture/shims.toml` as of 2026-05-06.
- [`control.py`](control.py) is a high-complexity module tracked in
  [architecture/module_size_budget.toml](../../../../../architecture/module_size_budget.toml)
  with owner `team-runtime` and sunset `2026-12-31`.
- Public response changes must go through OpenAPI snapshot checks and generated
  client compatibility notes before old fields are removed.

## Current State

- Last updated: 2026-08-29
- The tree still centers on `artifact_inspector.py`, `debug.py`, `lineage.py`, `run_index.py`, and `timeline.py`.
- The control service continues to support feedback evaluation, reissue, and data/Lex orchestration surfaces.
