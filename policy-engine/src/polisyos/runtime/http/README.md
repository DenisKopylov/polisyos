# Runtime HTTP (`polisyos.runtime.http`)

## Purpose

`polisyos.runtime.http` is the FastAPI assembly layer for runtime API v1. It
owns the app factory, auth and tenant middleware chain, thin route handlers,
service composition, OpenAPI enrichment, and the write-path protections around
runtime mutations and live streams.

## Where to start

- `src/polisyos/runtime/http/__init__.py` for the exported package surface.
- `src/polisyos/runtime/http/app.py` for app assembly, middleware order, and
  lifecycle wiring.

- `src/polisyos/runtime/http/routes/README.md` for endpoint-by-endpoint local
  navigation.

- `src/polisyos/runtime/http/services/README.md` for the application logic
  behind routes.

- `src/polisyos/runtime/http/openapi_contract.py` for examples, links, and
  contract hardening hooks.

- `src/polisyos/runtime/http/permissions.py` for the server-owned action
  permission vocabulary and immutable role grants projected by `/auth/me`.

- `src/polisyos/runtime/http/mutation_policy.py` for rate limits, idempotency,
  audit trail, and live-stream budgets.

- `src/polisyos/runtime/http/fail_closed_middleware.py` and
  `src/polisyos/runtime/http/security.py` for perimeter enforcement.

## Public entrypoints

- Package exports from `src/polisyos/runtime/http/__init__.py`:
  `create_runtime_api_app`, `export_runtime_openapi_schema`,
  `AuthzMiddleware`, `CellRouterMiddleware`, `JWTAuthMiddleware`,
  `TENANT_HEADER`, `get_current_user`

- Repo-level public-surface docs still anchor on `polisyos.runtime`; use this
  README when you need the actual HTTP assembly boundary, route/service
  navigation, or contract generation inputs.

- Internal local-navigation surfaces worth checking first: `routes/*`,
  `services/*`, `container.py`, `dependencies.py`, `execution_policy.py`,
  `mutation_policy.py`, `openapi_contract.py`, `permissions.py`

## Candidate catalog input selection

Deployments may pass a typed CatalogServingSourceSelection to
create_runtime_api_app(catalog_source_selection=...) to choose the candidate
L1 catalog at the fixed path
snapshot_root/datasets/graph/dataset_catalog.duckdb. If omitted, the
existing repository-default input remains in use. The selector's
catalog_run_profile must match the app's catalog_run_profile; when the latter
is omitted, the selector supplies it.

This setting selects candidate input only. It does not prove catalog
provenance, publisher lineage, profile coverage, freshness/currentness, or
publication authority. It does not add an HTTP request field or change the
OpenAPI contract. See the [Runtime API migration guide](../../../../docs/reference/api/migration-guide.md#optional-deployment-catalog-input)
for the operator configuration example and boundary.

## Authorization contract

`RuntimePermission` is the only hand-authored permission vocabulary for the
runtime API. Role grants consume enum members, and DS20's route-admission
dependency will consume the same members. The HTTP-local `AuthMeResponse`
projects the enum into OpenAPI for generated clients. Unknown string literals
do not become permissions by appearing in a client.

`GET /api/v1/auth/me` returns only claims installed by verified identity
middleware. It never synthesizes a fixture identity; the explicit development
fixture middleware may still install development-only claims before the route
executes.

The shared run and artifact tenant guards append ownership refusals to the
existing `runtime/audit/access.jsonl` trail before returning their existing
403. Each entry binds the attempted resource id and guard reason to the
request id, timestamp, method, route, and verified request actor/tenant; it
does not copy the resource owner's tenant or manifest details. If an append
fails, the guard logs the audit failure and keeps the access refusal in force.
When a verified owner tenant differs from the requester, the same guards also
record the existing Core tenant-boundary counter with requester tenant, owner
tenant, and resource type labels. A refusal caused by missing owner scope is
not counted as a cross-tenant mismatch because no target tenant is established.
Metric recording is best-effort and cannot change the 403 decision.

The runtime container appoints one Decision Validity service for control and promotion. Read-only
run-index/debug adapters may open their own service view, but every view resolves the same locked
persistent owner state. Direct, recursive, HTTP, and offline promotion paths resolve the same
persisted epoch-validity subject and gate evidence; a route-local state or caller-shaped projection
cannot bypass that owner.

## NL run cost events

The runtime container supplies an app-scoped durable LLM settlement ledger at
`core_runs_root/.runtime/llm-cost-ledger.json`, unless a typed store override is provided. Each
ordinary NL run uses `nl-run:{run_id}` as its accounting key; this records provider outcomes and
does not add a spend limit. Provider-reported cost, token-price estimate, authenticated cache
reuse, and unknown amount remain separate event origins. Unknown amounts stay null, and token-price
estimates remain heuristics.

The durable event's model and logical provider route are pinned from the configured pre-dispatch
intent. Response-declared labels cannot change the local accounting identity or estimate basis.

Persisted compiler/preflight and model-variant events project to their own steps in
`GET /api/v1/runs/{run_id}/agents`. The read model deduplicates identical event IDs across those
sources and rejects conflicting payloads. The local ledger acknowledges local settlement only; it
does not establish an external invoice or provider billing receipt.

## Depends on / depended on by

Depends on: `polisyos.common.async_tools`, `polisyos.core.artifacts`,
`polisyos.core.contracts`, `polisyos.core.security`,
`polisyos.core.observability`, and local `routes/` plus `services/` packages.

Depended on by: `polisyos.runtime`, `packages/runtime-api-client`,
`apps/runtime-dashboard`, `apps/runtime-reference-shell`, operator
runbooks, and runtime contract/drift checks.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python -c "import polisyos.runtime.http as runtime_http; print(sorted(runtime_http.__all__))"`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`

- Conceptual regeneration:
  `corepack pnpm --dir packages/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json`

## Test/verification commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_observability.py tests/unit/runtime/http/test_api_maturity.py tests/unit/runtime/http/test_access_invariants_properties.py tests/unit/runtime/http/test_control_service_di.py tests/unit/runtime/http/test_resilience_guards.py`

## Reference docs

- [Routes](routes/README.md)
- [Services](services/README.md)
- [REST API Reference](../../../../docs/reference/api/index.md)
- [Runtime Auth and Tenant Model](../../../../docs/reference/api/auth-tenant-model.md)
- [Runtime API Versioning and Deprecation Policy](../../../../docs/reference/api/versioning.md)
- [Runtime API Migration Guide](../../../../docs/reference/api/migration-guide.md)
- [Security and Compliance](../../../../docs/reference/security-compliance.md)
- [Runtime API outage runbook](../../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Runtime API client](../../../../packages/runtime-api-client/README.md)
- [Runtime dashboard](../../../../apps/runtime-dashboard/README.md)
- [Runtime reference shell](../../../../apps/runtime-reference-shell/README.md)

## Last updated date

2026-10-12

## Source-bound value selection

The default `natural_language_run` worker persists an additive normative composition
sidecar after the compiled generation run. Each leaf preserves the actual candidate
fronts with `dominance_status=not_established`; an absent or unauthorized schedule
produces zero recommendations and a persisted `NormativeDecisionRequest`.
`get_job_status` and `get_latest_job_for_run` share current replay: compiled membership,
leaf source bytes, signatures, deployment scope and expiry are checked at each read.
A missing or invalid sidecar produces a fresh refusal from the available compiled
source. An unresolved source is reported explicitly as `not_established`.

Deployment code may pass a typed `NormativeAuthorityTrust` through
`create_runtime_api_app(normative_authority_trust=...)`; the default slot is empty.
Request context accepts only `normative_evidence.by_node` references to a genuine S8
frontier and a signed `policyos.normative_authorization.v2` record binding the exact
compiled source, leaf source and node. This permission authorizes the recorded
selection; it confers no empirical, Pareto, legal or publication authority. The
canonical ambient filesystem CAS is reused with its ownership checks. Other CAS
backends require an independently verified signed-store adapter.

The sidecar contracts are internal Python owner surfaces; the existing HTTP
`ControlJobResponse.progress` carries their additive projection and CAS references.
Existing generation DTOs and standalone S8 authorization v1 artifacts retain their
epochs. Targeted replay and removal controls live in
`tests/unit/runtime/http/test_normative_generation_bridge.py`.

After the worker completes, `POST /api/v1/control/runs/{run_id}/normative-evidence`
accepts the exact `job_id`, required nullable `expected_prior_head_ref`, and typed
`evidence.by_node` references. The existing owned-run resolver and `evidence.resolve`
permission govern this intake. The worker publishes its candidate computation
through the canonical core `RunContext`, preserving tenant/cell ownership; a core
`ok` execution manifest does not confer policy promotion authority.

Successful admission appends an immutable `policyos.normative_generation_head.v1`
CAS record and a `normative_evidence_admitted` job event. The store compares the exact
prior head inside a SQLite write transaction or a PostgreSQL owning-job row lock.
A signed but invalid input persists a refusal and returns HTTP 422; a stale expected
head returns HTTP 409. Neither replaces the admitted head. The response carries the
attempted disposition, current head and current job projection. Both job readers
bind the head to the exact job, run and immutable compiled output, then replay S8
source/signature/scope/time checks. General progress updates cannot rewrite this
append-only head. Requests accept no source, deployment-trust or signature overrides.

The immutable core-run outputs own both the initial default and later head lookup.
A copied `progress` projection cannot supply a current head or change its source.
A missing event or mismatched progress reference produces a fresh refusal using the
known canonical source, preserving its candidate fronts and typed request. If that
owned source itself cannot be resolved, current authority is `blocked` with an
explicit source limitation; standalone historical sidecar replay remains available.

## Run-bound predictive calibration

POST /api/v1/runs/{run_id}/predictive-calibration takes an explicit intent, full selected refs, split, method parameters, seed, threshold, and caller-declared temporal roles. The route requires the existing run feedback-evaluation permission bound to ownership of that exact run; it does not add a role grant. The selected N5 candidate source must be in the resolved candidate projection, the observed snapshot must be an exact run input, and model, policy, and calibration-rule refs must each be exact full-profile views in this run’s root outputs or inputs. Every selected profile is re-resolved from CAS and carried into the report and association manifests. The service joins the Core manifest to the completed control job, invokes ForecastOwner, persists the empirical bridge and S10 projection, then appends the immutable association ref to the run's diagnostic event log.

GET /api/v1/runs/{run_id}/predictive-calibration uses the existing run-review permission with the same exact owner binding. It verifies the event payload hash, reopens the association and evidence, checks the run/control/job/manifest join, and recomputes S10. A same-intent retry with the same body reopens the existing association; changing the body under that intent returns a conflict. Use a new intent for a distinct calculation. The shared SQL owner serializes a local purpose/run/principal/intent claim; it does not claim external provider exactly-once execution.

The normal application/container configuration exposes `allow_candidate_run_predictive_calibration_surface` (default `True`); set it to `False` to refuse the run-level POST and GET before producer execution. This run-level gate is distinct from the existing artifact-preview diagnostic gate, which remains disabled by default. Neither setting grants a permission or changes the existing ownership-bound authorization checks.

The dashboard form selects full refs from the run's candidate projection and root inputs. It requires explicit parameters and temporal roles, invalidates the read after a write, and preserves the intent for retry after an uncertain response. The association remains limited and predictive_only. Issuer, source-time currentness, population scope, and counterfactual credibility remain not_established; the diagnostic does not establish a causal effect, recommendation, or publication authority. See the Runs API reference and the release fragment at release-fragments/unreleased/2026-10-12-e02-empirical-predictive-calibration.toml. The canonical OpenAPI/client generation and runtime integration execution remain pending.



## Shared operation-intent ownership

`ControlPlaneStore.runtime_operation_intents` is the single SQL claim table used by run-bound Predictive Calibration and route-owned natural-language pre-admission. Its identity includes purpose, tenant, cell, authenticated-principal digest, typed `scope_kind`/`scope_id`, and caller intent; request-body digests remain conflict checks. Run-scoped Forecast records use `scope_kind="run"` with `scope_id == run_id`. The NL launch owner uses `scope_kind="route"` for the fixed launch route while preserving the actual generated candidate `run_id` as row provenance; it never substitutes a route sentinel for a run id.

The R3 attempt row is a typed read projection joined to this claim, and its immutable status history remains append-only. A route claim and initial projection are created in one SQL transaction; subsequent producer settlement/admission/refusal/cancellation/failure observations transition the shared claim and projection together. Only provider-preflight code that returns before completion may attest `no_call`; an empty event list or empty ledger is never evidence of no call. Unreadable or missing settlement evidence remains `unavailable`, keeps the shared key unresolved, and cannot be replaced by a no-call label. An ambiguous cancellation or failure requires recovery and is never treated as zero cost or retried as a fresh operation. A started owner does not transfer after process loss. The generated R3 attempt handle is a digest over the authenticated tenant/cell/subject and idempotency-key digest; raw keys are not persisted.

The generic mutation response cache is skipped for both route-owned NL launch and run predictive-calibration POSTs. Middleware request-rate controls and mutation audit remain active. Other supported mutation routes keep their existing `X-Idempotency-Key` cache behavior. Typed scope is part of the shared table primary key. SQLite rebuilds a legacy-keyed table transactionally; PostgreSQL replaces the legacy primary-key constraint transactionally. Only known Forecast rows are backfilled from their stored `run_id`, and only known NL owner rows receive the fixed route scope. Unclassified or malformed rows and duplicate identities after rekeying abort migration; rows are never assigned a synthetic run id.


## Pre-admission provider attempt custody

Every natural-language launch with requested models first records its immutable caller intent, authenticated tenant/cell/actor scope, actual candidate run binding, and an opaque attempt handle. The generic SQL `runtime_operation_intents` row is the unique route-scope claim; the typed control-attempt row and its append-only started/settled/admitted/refused/cancelled/failed history are a read projection of that owner. Research/governed/production profiles must append a settled event with complete producer refs before admission or a complete-evidence terminal outcome. Provider-preflight code may report the canonical producer-call state `no_call` only on source-controlled exits before the completion request begins (for example, simulation skip, missing credentials, health/model/pricing failure, or model absence). It carries a finite `producer_no_call_reason` joined to the source-owned failure code in the append-only event and fresh response. That typed refusal remains distinct from an empty/unreadable ledger, which stays `unavailable` and blocks retry cleanup. Dev skips provider preflight and records `started → admitted` with `not_applicable` producer evidence; it does not fabricate settlement. The completed job and attempt observation link in one transaction. Exact provider ledger event IDs are retained; a null amount remains unknown and a token-price estimate remains estimated. This mechanism proves local database ownership, not an external invoice, provider-side idempotency, permission authority, or production currentness.

`GET /api/v1/control/admission-attempts/{attempt_id}` and the same-scope `.../by-idempotency-key` lookup are uncached. The server derives tenant, cell, and actor from verified authentication. After a lost reply, reuse the same `Idempotency-Key` and exact request intent; changed intent conflicts, and 404 means unknown rather than no provider work. Composer and Clerk persist the opaque key plus scope/body digests in the dedicated IndexedDB record and retain it while the attempt is started, settled, or unresolved. Recovery validates the shared-owner purpose/route/body digest, authenticated principal/scope, the complete append-only status sequence, and profile-specific producer observations before clearing that key. A refused `no_call` with zero producer refs and its exact typed reason joined to the failure code is resolved; `failed`, `cancelled`, or `refused` with an unavailable observation remains unresolved. Missing or malformed persisted intent, producer refs, event payloads, observation states, owner tokens, and completed-job joins fail closed; they are never materialized as an empty/default observation. Generated state is never used to change the selected profile. Generic response replay is skipped for both NL launch and run predictive-calibration POSTs, while middleware rate limiting and audit remain active. The local debug CLI cannot perform a billable preflight without an authenticated scope and stable idempotency intent.
