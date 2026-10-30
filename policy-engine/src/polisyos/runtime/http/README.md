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

The DS17 OpenAPI example is packaged at `src/polisyos/runtime/http/_resources/` as a pinned historical documentation fixture. It records the source commit, artifact, dependency aggregate, worker receipt, and example time in the OpenAPI description; it makes no claim about current availability or freshness. OpenAPI rendering reads this package resource without consulting the live owner. The real GET continues to resolve and validate the current owner source for every request.

Registered SQL source, cancellation, and method-metric comparison success examples
are synthetic documentation fixtures checked against the actual response DTOs.
Their placeholder identifiers are not issuer, authorization, artifact ownership,
source currentness, candidate authority, or physical worker-stop evidence. The
materialization example keeps current use `not_checked` and external database
currentness `not_established`; cancellation keeps physical stop `not_established`;
the comparison remains `candidate_only` with verification missing. Real routes
continue to apply their own authorization and owner checks.

- `src/polisyos/runtime/http/permissions.py` for the server-owned action
  permission vocabulary and immutable role grants projected by `/auth/me`.

- `src/polisyos/runtime/http/cancellation_admission.py` scopes a single current
  cancellation permission proof to its request; the control store binds the
  request body and attempt and owns the durable event/outbox. The cancellation
  route defaults to disabled; a rollout switch is not proof of installed-reader
  readiness, and physical effects outside the cooperating owner remain unknown.
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

## Observational input worker binding

For direct observational method jobs, the worker reconciles the complete
selection marker from the durable payload with the marker persisted in the
job-created event, then resolves the selected immutable CAS intent and checks
its source ref and digest. The method request comes from that typed intent. A
removed or malformed marker, or drift in the selected source/profile, is
refused before method work is constructed or submitted. The worker checks the
immutable creation event as well as the loaded payload, so deleting the mutable
marker cannot bypass that check. This preserves the accepted request across the queue boundary; it does not establish source
authenticity or scientific admissibility.

The requested-intent producer, content-admitted producer, and fresh completion consumer share
typed-intent lineage recipes. The admitted recipe includes every selected Search binding snapshot
ref when present and checks each input edge by role, artifact ID, profile, and multiplicity. Repeated
refs remain separate edges when their semantic roles differ; the check does not grant additional
read authority or change the admission status.

The fresh direct-method evidence consumer admits the complete decoded candidate
summary through `MethodExecutionCandidateOutcome.from_json_payload()`. This
preserves the producer's JSON-array representation while retaining strict scalar,
candidate-only and limitation validation; it does not cast individual fields.
Selected manifest/profile, resource, source, intent, result-ref and lineage checks
still precede completion. A valid but mismatched summary remains refused. The
transport repair establishes neither a scientifically valid estimate nor a
cancel-during-native-work result.

## Controlled local Legal runtime profile

For a local Legal vector-search candidate, run the module entrypoint with the
same operator-selected profile root used by the Legal batch producer:

```bash
python -m polisyos.runtime.http.profiled_server \
  --runtime-material-profile-root /path/to/legal-runtime-profile
```

The root must contain the fixed `hf-cache/` and `asset-file-manifest.txt`
members. The source-owned Legal material owner validates the pinned manifest
and model members before query encoding. An invalid explicit root fails startup
with a typed refusal; omitting the root preserves the ordinary profileless app
composition. The root is process configuration and is not accepted from an
HTTP request. Use the same Python environment, source checkout, working
directory, and module invocation context for producer and server because the
runtime fingerprint includes the active module search path. This local
candidate profile establishes neither Legal authority nor production
currentness.

## Candidate catalog input selection

Deployments may pass a typed CatalogServingSourceSelection to
create_runtime_api_app(catalog_source_selection=...) to choose the candidate
L1 catalog below its declared snapshot owner. The default member is
snapshot_root/datasets/graph/dataset_catalog.duckdb. The optional
`database_relative_path` admits an existing native layout without moving or
copying its bytes; absolute/traversing paths and redirected member symlinks
refuse. Optional `source_owner_root` selects the physical production-data
owner while code-owned epoch registries remain rooted at `repo_root`.
If the selector is omitted, the repository-default input remains in use. The selector's
catalog_run_profile must match the app's catalog_run_profile; when the latter
is omitted, the selector supplies it.

This setting selects candidate input only. It does not prove catalog
provenance, publisher lineage, profile coverage, freshness/currentness, or
publication authority. It does not add an HTTP request field or change the
OpenAPI contract. See the [Runtime API migration guide](../../../../docs/reference/api/migration-guide.md#optional-deployment-catalog-input)
for the operator configuration example and boundary.


## Owner-bound source-root selection

The create_runtime_api_app(repo_root=...) setting selects an optional server-side Path for owner-bound source reads. The configured path must be absolute and point to an existing directory; composition rejects malformed supplied values instead of falling back. Omitting it preserves the existing module-derived source root. The setting is fixed at application composition and cannot be selected by an HTTP request.

This source root is separate from cas_root and core_runs_root, which still select runtime artifact and job outputs. It also leaves product code imports and package-resource resolution attached to the installed PolicyOS package. A selected source root supplies candidate inputs to owner readers; it does not establish source authenticity, freshness, currentness, complete L3/L6 source basis, causal grounding, recommendation admissibility, or publication authority.

The selected repository root is passed explicitly to the S0/L5 catalog owner. Every emitted `repo://` reference is the canonical path of a resolved file beneath that same root; L5 references retain the `production_data/` prefix instead of deriving a shorter root from `root_manifest_path.parent`. A missing or mismatched root, parent traversal, or symlink that resolves outside the selected checkout is refused. The candidate source resolver applies the same descendant check to both `repo://` and absolute `duckdb://` selectors; it has no outside-root fallback. These checks bind paths only and do not upgrade candidate status or source-basis, authenticity, or currentness labels.

## Candidate cycle source-profile handoff (prototype)

A typed candidate source-profile selector is handled on the normal recursive N5 route. The controller rebuilds a candidate-only context from owner inputs, persists it as context-job V5 under the issued NL job scope, freshly resolves that artifact, and binds the returned V2 context at the N4 boundary. Historical context V1 and context-job V1–V4 formats remain unchanged; absent selector preserves the legacy route, while malformed supplied selection fails closed.

This is a bounded internal engineering prototype. The profile is candidate-only (`cycle_input_candidate_only`); source basis, authenticity, and currentness remain `not_established`. K_ref stays V3 and does not bind all zero-row L3/L6 reads. The focused route test is designed to stop at N4 invocation and verify the exact fresh-resolved context; its execution is pending for this composition. It does not prove a generated/refused N4 result, GenerationSource persistence, fresh N6 behavior, or meaningful simulation children. No law, external source authority, recommendation admissibility, or publication authority is established.

## Authorization contract

`RuntimePermission` is the only hand-authored permission vocabulary for the
runtime API. Role grants consume enum members, and DS20's route-admission
dependency will consume the same members. The HTTP-local `AuthMeResponse`
projects the enum into OpenAPI for generated clients. Unknown string literals
do not become permissions by appearing in a client.

The required `ActionPermissionDependency` owns the executable authorization
evaluator called by the middleware before binding and again after the exact
resource is frozen. `OptionalActionPermissionDependency` only returns the typed
projection decision produced by that middleware; it does not authorize by
itself. A required permission denial blocks the handler, while an optional
permission or policy denial withholds only its protected projection. On the run
details route, a denied optional method-selection binding also reuses the canonical
run-owner guard when that guard confirms a cross-tenant or unscoped run, preserving
the typed owner refusal and caller-scoped data-access audit. If the run is unresolved
or the owner recheck cannot confirm the refusal, the original binding refusal remains
fail-closed. A route marker declares the requirement but cannot substitute for the
executable evaluator.

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

### Observational source access at run admission

POST /api/v1/control/runs reads the selected observational manifest through the bounded Core CAS reader under the request tenant. A source manifest must still explicitly classify itself as public and omit tenant context for candidate execution; that classification does not grant CAS access. A missing current tenant owner for the selected CAS view returns the existing 403 observational_source_current_access_not_established response before enqueue. Malformed, integrity-failing, or over-bound source manifests remain 422 observational_source_manifest_not_admitted. On worker execution, the mutable job marker is reconciled with the selected immutable intent before method work is constructed or submitted; only the intent-bound selected source ref reaches method work.

Typed intent readers retain the bounded Core read and validate persisted model payloads through Core's JSON-aware validator. This preserves strict field validation while reifying serialized timestamps and other JSON-native forms; the worker does not weaken intent validation or hand-parse individual fields.

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

## Selected MeasurementRoot output profiles

The workspace-loop producer captures the exact Core CAS `ArtifactRef` profile
selected during each MeasurementRoot write before the mutable SearchExit
contract is assembled. Before emitting the run and replay proofs, the control
transition joins every declared `output_artifacts` ref to exactly one
`artifact_envelopes` member by the complete typed ref. Intermediate envelopes
remain available to the workflow but do not enter the output-profile proof;
missing, duplicate, or substituted output refs make the result
`repair_required` before the V2 proof artifacts are written.

For a MeasurementRoot output, resolution reads the selected immutable Core
manifest and payload. The persisted Core kind and producer component identify
the owner; the shared BaseDataset schema is not sufficient because generic
WorkspaceLoop fallback outputs use that same schema. PDC creator/root fields
claiming MeasurementRoot are checked against the resolved Core owner. Generic
profileless fallback outputs remain candidate/refusal results and emit no
MeasurementRoot profile proof. A true MeasurementRoot with no selected profile
remains a typed refusal. Unscoped writes must match the source-owned producer
`PutOptions` over the exact stored bytes. Scoped writes additionally resolve the
existing authority envelope and diagnostic event, bind them to the current
run/job and selected CAS ref, and call the existing runtime identity verifier.
The checker repeats this durable CAS resolution from the stored contract and
proofs; it does not treat a profile string, producer label, or in-memory
invocation witness as historical evidence. A missing or mismatched selected
view is a typed refusal, while legacy V1 replay history remains parseable and
does not gain a V2 profile claim. This verifies a producer-selected content
view only. An unscoped Core profile binds its bytes and complete producer
configuration, but not a run/job authority subject; the existing execution-scope
gate remains responsible for withholding authority when that subject is not
established. Neither path establishes source authenticity, currentness,
recommendation admissibility, or publication authority.

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

The dashboard form selects full refs from the run's candidate projection and root inputs. It requires explicit parameters and temporal roles, invalidates the read after a write, and preserves the intent for retry after an uncertain response. The association remains limited and predictive_only. The held-out observed-series pass/fail grade and counts remain visible, but S10 keeps the N4 outcome forecast blocked until a selected source-owned relation binds the candidate outcome variable to the observed snapshot metric. The persisted binding record keeps the N4 target variable, N4 metric id, and observed metric as separate identities; it does not equate their names. Issuer, source-time currentness, population scope, and counterfactual credibility remain not_established; the diagnostic does not establish a causal effect, recommendation, or publication authority. See the Runs API reference and the release fragment at release-fragments/unreleased/2026-10-12-e02-empirical-predictive-calibration.toml. The canonical OpenAPI/client generation and runtime integration execution remain pending.



## Shared operation-intent ownership

`ControlPlaneStore.runtime_operation_intents` is the single SQL claim table used by run-bound Predictive Calibration and route-owned natural-language pre-admission. Its identity includes purpose, tenant, cell, authenticated-principal digest, typed `scope_kind`/`scope_id`, and caller intent; request-body digests remain conflict checks. Run-scoped Forecast records use `scope_kind="run"` with `scope_id == run_id`. The NL launch owner uses `scope_kind="route"` for the fixed launch route while preserving the actual generated candidate `run_id` as row provenance; it never substitutes a route sentinel for a run id.

The R3 attempt row is a typed read projection joined to this claim, and its immutable status history remains append-only. A route claim and initial projection are created in one SQL transaction; subsequent producer settlement/admission/refusal/cancellation/failure observations transition the shared claim and projection together. Only provider-preflight code that returns before completion may attest `no_call`; an empty event list or empty ledger is never evidence of no call. Unreadable or missing settlement evidence remains `unavailable`, keeps the shared key unresolved, and cannot be replaced by a no-call label. An ambiguous cancellation or failure requires recovery and is never treated as zero cost or retried as a fresh operation. A started owner does not transfer after process loss. The generated R3 attempt handle is a digest over the authenticated tenant/cell/subject and idempotency-key digest; raw keys are not persisted.

The generic mutation response cache is skipped for both route-owned NL launch and run predictive-calibration POSTs. Middleware request-rate controls and mutation audit remain active. Other supported mutation routes keep their existing `X-Idempotency-Key` cache behavior. Typed scope is part of the shared table primary key. SQLite rebuilds a legacy-keyed table transactionally; PostgreSQL replaces the legacy primary-key constraint transactionally. Only known Forecast rows are backfilled from their stored `run_id`, and only known NL owner rows receive the fixed route scope. Unclassified or malformed rows and duplicate identities after rekeying abort migration; rows are never assigned a synthetic run id.


## Pre-admission provider attempt custody

Every natural-language launch with requested models first records its immutable caller intent, authenticated tenant/cell/actor scope, actual candidate run binding, and an opaque attempt handle. The generic SQL `runtime_operation_intents` row is the unique route-scope claim; the typed control-attempt row and its append-only started/settled/admitted/refused/cancelled/failed history are a read projection of that owner. Research/governed/production profiles must append a settled event with complete producer refs before admission or a complete-evidence terminal outcome. Provider-preflight code may report the canonical producer-call state `no_call` only on source-controlled exits before the completion request begins (for example, simulation skip, missing credentials, health/model/pricing failure, or model absence). It carries a finite `producer_no_call_reason` joined to the source-owned failure code in the append-only event and fresh response. That typed refusal remains distinct from an empty/unreadable ledger, which stays `unavailable` and blocks retry cleanup. Dev skips provider preflight and records `started → admitted` with `not_applicable` producer evidence; it does not fabricate settlement. The completed job and attempt observation link in one transaction. Exact provider ledger event IDs are retained; a null amount remains unknown and a token-price estimate remains estimated. This mechanism proves local database ownership, not an external invoice, provider-side idempotency, permission authority, or production currentness.

`GET /api/v1/control/admission-attempts/{attempt_id}` and the same-scope `.../by-idempotency-key` lookup are uncached. The server derives tenant, cell, and actor from verified authentication. After a lost reply, reuse the same `Idempotency-Key` and exact request intent; changed intent conflicts, and 404 means unknown rather than no provider work. Composer and Clerk persist the opaque key plus scope/body digests in the dedicated IndexedDB record and retain it while the attempt is started, settled, or unresolved. Recovery validates the shared-owner purpose/route/body digest, authenticated principal/scope, the complete append-only status sequence, and profile-specific producer observations before clearing that key. A refused `no_call` with zero producer refs and its exact typed reason joined to the failure code is resolved; `failed`, `cancelled`, or `refused` with an unavailable observation remains unresolved. Missing or malformed persisted intent, producer refs, event payloads, observation states, owner tokens, and completed-job joins fail closed; they are never materialized as an empty/default observation. Generated state is never used to change the selected profile. Generic response replay is skipped for both NL launch and run predictive-calibration POSTs, while middleware rate limiting and audit remain active. The local debug CLI cannot perform a billable preflight without an authenticated scope and stable idempotency intent.

## WorkspaceLoop selected MeasurementRoot profile

`MeasurementRootProducer` persists the payload and returns the selected CAS manifest
profile with its `BaseDataset` envelope. Before writing the ordinary V2 exit-contract
and replay-proof artifacts, WorkspaceLoop resolves that exact profile through the
Core artifact store. The shared authority helper checks the selected manifest digest,
kind, schema, producer component, payload integrity, envelope content hash, and the
`MeasurementRoot` reference derived from the selected payload. A missing selector,
unavailable manifest, substituted profile, or mismatched root becomes a typed
non-authority workflow failure with `repair_required`; it cannot produce a verifier
stamped V2 proof. The offline live-observation verifier calls the same resolver on
the actual CAS store before comparing the proof and GET projection.

These checks bind the emitted CAS view and its producer-declared root to exact stored
bytes. They do not independently establish producer signing authority, custody beyond
this CAS, legal authority, source truth, freshness, or production currentness.

The completed job keeps the contract and both versioned proofs in the existing open
`ControlJobResponse.progress` projection. `ControlPlaneStore` persists the full progress
snapshot for the job, and the existing `GET /api/v1/control/jobs/{job_id}` route maps it
back to the response. The composed verifier checks the actual fresh GET's contract ref,
content hash, and selected profile view against the persisted proof and CAS manifest;
the proof itself records the selected view and does not claim that a GET was observed.
The generated `progress` schema remains generic; these nested evidence payloads are
validated by their own versions and are not an authority declaration. Profileless v1
proof history remains parseable but cannot establish a current selected-profile chain.
This CAS profile binds the selected bytes and manifest view only; it does not establish
producer authority, custody outside this CAS, legal authority, freshness, or production
currentness.


Selected Catalog checkpoint/unavailable/readmission errors retain their actual
source cause at predictive-calibration admission. A ValueOwner source refusal
is carried by its typed error field rather than inferred from a code prefix.
No HTTP request or persisted response DTO changes; the existing error surface
continues to refuse rather than fabricate an empty/available source.


Selected method metric reads preserve two run identities. The requested control-run ID
remains the completed selection key; the existing scoped lifecycle resolver supplies its
actual Core attempt for authorization and run ownership. Both method-metrics and
method-metric-comparison bind the requested selection key, canonical Core run, control
job, selected Core manifest, tenant and cell into the existing immutable authorization
context. The consumer rederives that complete context before owner lookup and again
before emission. A changed alias, attempt, manifest or scope refuses the read; a URL ID
is never rewritten into a different selection key. A valid direct-method selection still
returns verification_missing with no graph metric vector. These checks add no source
currentness, scientific, institutional or publication authority.


A populated method-metric comparison additionally requires an independent runs.review
policy decision for EVERY source selected by its actual immutable terminal-state basis.
Same tenant and cell establish scope, not permission. The existing authorization binding
freezes the complete basis, ordered member set and each source's requested/Core/job/ref/
vector/scope context, and the canonical OPA middleware checks each exact bound source.
The complete set is rederived after policy, at consumer entry and before selected audit
or response emission. A denied source fails the whole comparison; rows are never silently
omitted as a complete ranking. A missing policy service cannot admit populated sources.
Empty comparisons on verified direct selections still carry no related-source authority.
The response must match every owner-basis member. These are checkpoint reconciliations,
not an atomic exclusion of outside writers or a promise that external policy never changes.


The authorization trail still writes one terminal decision per request. Populated
comparison admission uses authorization_audit.v2: the frozen complete owner context
and a bounded typed tuple of actual target-policy decisions accompany the primary
resource digest. Ordinary admissions keep the v1 serialized shape. A request cannot
emit an ALLOW audit with a missing, foreign or denied required target decision.
This audit admission is not a handler-success or external-currentness assertion.
The distinct artifact-content/download policy plane is not changed by this repair;
a generic signed-derived-artifact inheritance rule remains an explicit architectural
boundary, rather than an implicit new runs.review grant or denial.


Every related-target admission failure, including changed or unresolved owner sets,
seals one terminal DENY against the original frozen binding and the complete prefix
of usable policy results actually obtained before failure. The newest result is
recorded before re-resolution. A target policy dependency failure cannot silently
clear that basis; an unavailable audit append withholds admission with 503.
Ordinary unrelated denial policy is preserved.

The same strict v2 event parser now runs on the actual read-only access-trail scan.
It parses the complete comparison context, derives its ordered source set from the
typed immutable request, recomputes primary and source digests with the live binding
owner, and reconciles every recorded permission and outcome. A receipt checksum
binds the request identity and the serialized context/decision tuple. The cold API
can additionally match a separately held request ID and selected run ID. Invalid
receipts remain counted and make review-effectiveness coverage incomplete; a
runs.review event cannot become human-decision review success. Historical v1 wire
fields and typed reads remain compatible.

This is content consistency and exact tuple reconciliation, not authenticated audit
history: the existing local trail has no MAC or signature that prevents an actor
with file-write access from replacing all bytes and recomputing checksums. Cold
parsing also does not reauthorize historical decisions or establish live CAS/source
availability. The distinct generic artifact permission boundary remains unchanged.


Related policy evaluation and the later sealed dependency phase share one generic
process-live admission boundary. Returned typed failures and any ordinary Exception
escaping the complete operation or its cleanup reach the same single sealed DENY
terminalizer. This includes deployment-component re-attestation before an OPA call;
no exception-name allowlist defines coverage. The terminalizer preserves the original
binding and only policy results actually obtained, and audit failure refuses with
503 after one append attempt. Cancellation and other BaseException exits, interpreter
termination, process failure and audit crash durability remain outside this property.
The defining test changes an ordinary secure app's deployment-security alias after
primary policy, exercising the unmodified guard's real unregistered-installation
refusal. It does not claim coverage of every genuine factory configuration.


An authorized cancellation request whose optimistic attempt/lease identity or
operation disposition conflicts with durable job state returns the existing typed
409 problem surface (`control_job_cancellation_conflict`). Only cancellation's
specific precondition/race conflict subtype receives this translation. General
worker publication lease loss and post-write integrity failures retain their
internal-error behavior. A conflict does not mutate the job/progress/event/outbox
state or assert physical process termination. The current cancellation and its
identical retry retain their existing behavior.

For an already cancelled job, the existing durable receipt verifier reconciles the
complete row, creation identity, cancellation progress, source event and outbox
before a new request is compared. A malformed or inconsistent persisted receipt
remains an internal error even when a different client request would otherwise
conflict; it is never reclassified as409 from plausible progress fields.
