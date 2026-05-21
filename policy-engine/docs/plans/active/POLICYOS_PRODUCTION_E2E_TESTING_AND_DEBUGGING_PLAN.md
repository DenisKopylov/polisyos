---
title: PolicyOS Production End-To-End Testing And Debugging Plan
status: active
owner: team-runtime
created: 2026-05-10
last_verified: 2026-05-10
stability: draft
scope:
  - runtime-api
  - control-plane
  - nl-pipeline
  - scientist
  - fabric
  - foundry
  - cas
  - dashboard
---

# PolicyOS Production End-To-End Testing And Debugging Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` for sequential execution and
> `superpowers:systematic-debugging` for every failed gate. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Prove that PolicyOS works end-to-end in a production-like and then
real production canary run, with real LLM and data-provider dependencies,
durable control-plane execution, complete artifacts, actionable failure
surfaces, and dashboard visibility.

**Architecture:** Testing is organized as progressive evidence lanes. Each lane
keeps the previous deterministic checks green, then adds one production risk at
a time: real gateway, real data providers, durable state, external workers,
object storage, authz, observability, concurrency, failure injection, and
dashboard verification.

**Tech Stack:** Python/pytest/uv, FastAPI runtime API, durable control-plane
jobs, CAS/artifact stores, Scientist/Fabric/Foundry workflows, LLM gateway,
Playwright/Vite runtime dashboard, OpenAPI contract checks, logs, metrics, and
distributed traces.

---

## Executive Summary

The no-network simulation lane proves that PolicyOS logic is internally
consistent. It does not prove production readiness by itself. Production
readiness requires proving four additional facts:

- The system can call a real LLM gateway without implicit mock or simulated
  fallback.
- The system can retrieve and materialize real external data into immutable
  artifacts.
- Durable control-plane execution survives slow dependencies, worker restarts,
  retries, and terminal failures.
- Operators can explain every completed or failed run from API responses,
  control jobs, artifacts, traces, logs, metrics, and dashboard views.

The plan therefore has two kinds of gates:

- **Release blockers:** failures that prevent a production canary or release.
- **Operational follow-ups:** non-blocking observations that must be filed with
  owner, severity, evidence, and proposed fix path.

No fix is accepted without a reproducing command, observed vs expected behavior,
root-cause evidence, a focused regression test, and a rerun of the closest broad
gate.

## Definitions

| Term | Meaning |
| --- | --- |
| Fast deterministic lane | No real network LLM calls; uses `POLISYOS_LLM_SIMULATION_MODE=1` and deterministic fixtures. |
| Prod-like lane | Uses production profile policies, durable state, external workers, production authz shape, and isolated staging infrastructure. |
| Real canary | A small controlled run using real LLM and at least one real external data provider. |
| Truth gate | A gate whose failure blocks further rollout until root cause is known. |
| Evidence bundle | A human-readable record containing command, environment, run IDs, job IDs, artifact IDs, logs, traces, metrics, and dashboard screenshots or Playwright traces. |
| Actionable error | A failed job response that tells the operator what failed, where it failed, and the next owning layer to inspect. |

## Non-Negotiable Principles

- Reproduce first, then fix.
- Add diagnostics at component boundaries before changing behavior.
- Fix the owning layer, not the rendering or retry symptom.
- Use deterministic simulation for fast debug loops; use real LLM only in
  controlled canary lanes.
- Never let `mock_fallback`, simulated providers, or route-mocked frontend tests
  count as production proof.
- Every failure gets a scenario name, exact command, layer classification,
  observed result, expected result, root-cause hypothesis, evidence, and next
  owner.
- If three fixes fail for the same class of issue, stop and reassess the
  architecture before adding another patch.
- A green happy path is not enough. Production readiness requires one controlled
  failure canary that ends in a clear failed job with an actionable error.

## Required Environments

### Environment A: Fast Local Deterministic

Purpose: fastest debug loop, no external LLM latency or cost.

Required properties:

- `POLISYOS_LLM_SIMULATION_MODE=1`
- deterministic `SimulatedGatewayLLMClient`
- fixture runtime API for dashboard smoke
- local CAS and local runtime state
- no real LLM network traffic

Blocking proof:

- NL pipeline uses simulated gateway client.
- Tests fail if the pipeline constructs a real `GatewayLLMClient` while
  simulation mode is enabled.

### Environment B: Staging Prod-Like

Purpose: production behavior without production blast radius.

Required properties:

- `POLISYOS_LLM_SIMULATION_MODE` unset or set to `0`
- `POLISYOS_EXECUTION_PROFILE=governed` or `research`
- `POLISYOS_CONTROL_WORKER_BACKEND=external`
- durable control-plane state store
- production-like CAS or object storage
- production-like authn/authz claims
- real LLM gateway credentials from the staging secret store
- real external data-provider access where allowed
- isolated tenant and low budget caps

Blocking proof:

- `allow_mock_fallback=False` is enforced.
- non-privileged callers cannot enable privileged policy flags.
- control jobs are leased and processed by an external worker.
- run artifacts remain readable after runtime API process restart.

### Environment C: Production Canary

Purpose: minimal real production proof.

Required properties:

- real production runtime endpoint
- production identity and tenant isolation
- real LLM gateway
- real external data provider
- strict cost, token, and wall-clock limits
- canary input that is safe, small, and reversible
- full evidence capture enabled

Blocking proof:

- one run completes end-to-end with no mock or simulated provider
- one intentionally failed run fails cleanly with an actionable error
- dashboard can inspect both runs against the real backend

## Canonical Canary Request

Use one small request across staging and production so results are comparable:

```text
Design a targeted policy package to support Ukrainian micro, small, and medium
enterprises under wartime constraints. Use available macroeconomic and labor
market indicators, identify required data sources, propose interventions, and
produce an auditable decision bundle.
```

Expected run shape:

- NL request creates a durable control job.
- LLM agents produce a problem frame, draft, formalized bundle, critique, and
  data needs.
- Retrieval resolves at least one real external source.
- Materialization persists source payload or normalized data into CAS.
- Trinity bundle and registry bundle are referenced by the Scientist workflow.
- Scientist workflow creates a workflow report and decision artifacts.
- Run index exposes the run.
- Dashboard opens overview, timeline, artifacts, evidence context, lineage, and
  audit/deck views.

## Evidence Capture Contract

Every production-like or production canary run must record:

| Evidence | Required fields |
| --- | --- |
| Command record | command, cwd, timestamp, operator, git revision, environment lane |
| Runtime request | endpoint, method, sanitized body, request headers excluding secrets |
| Control job | `job_id`, `run_id`, state transitions, attempts, lease owner, error message |
| Payload artifact | artifact ID, kind, media type, referenced input artifacts |
| LLM calls | provider, model, variant, request ID, latency, token usage, cost, status |
| Retrieval | provider/profile, query, selected dataset, materialization artifact IDs |
| Workflow | workflow ID, node statuses, report artifact ID, failure card if any |
| CAS | put/get latency, artifact IDs, content kind, integrity verification result |
| Run index | run list entry, run detail, timeline, lineage, evidence context |
| Frontend | Playwright trace or screenshots, failed network responses, console errors |
| Observability | trace ID, logs, metrics snapshot, alerts fired or suppressed |

Evidence is stored after the run under `docs/archive/reports/` or the
release-owner-approved evidence location. Large raw traces and videos remain in
ignored `_build/**` paths unless promoted by owner decision.

## Debugging Protocol

For every failed scenario, write a short incident note before editing code:

```markdown
### Failure Note

- Scenario:
- Command:
- Environment:
- Layer: API | control-plane | NL | LLM | retrieval | CAS | Scientist | Fabric | Foundry | dashboard | observability
- Observed:
- Expected:
- First bad boundary:
- Root-cause hypothesis:
- Evidence:
- Regression test to add:
- Owner layer:
- Fix path:
- Rerun gate:
```

Boundary-first diagnostics:

- At API boundary, capture sanitized request and response.
- At job boundary, inspect `/api/v1/control/jobs/{job_id}`.
- At payload boundary, inspect payload artifact references.
- At LLM boundary, inspect call events and provider/model identity.
- At retrieval boundary, inspect provider selection and materialization report.
- At workflow boundary, inspect workflow report status and node errors.
- At CAS boundary, inspect artifact `put`, `get`, and integrity verification.
- At run-index boundary, inspect run detail, timeline, lineage, and evidence
  context endpoints.
- At dashboard boundary, inspect browser network responses, console errors, and
  Playwright trace.

## Test Lanes

### Lane 0: Repository And Fixture Truth Gate

Purpose: prove the local fast debug harness is healthy before spending time on
real dependencies.

- [ ] Run backend collection gate.

```bash
uv run pytest --collect-only \
  tests/unit/runtime/http/test_control_api.py \
  tests/unit/runtime/http/test_nl_pipeline_materialization.py \
  tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py \
  -q
```

Expected result:

- collection succeeds
- no import error from fixture runtime API helper
- no missing dynamic import registry target

- [ ] Run runtime contract gate.

```bash
uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
```

Expected result:

- `Runtime API contract check passed.`
- generated client compiles
- no public API shape drift

- [ ] Run fixture local stack smoke.

```bash
uv run python tools/quality/testing/local_integration_stack.py smoke
```

Expected result:

- runtime fixture API health passes
- dashboard proxy health passes
- Playwright smoke journeys pass on desktop and mobile

Release blocker examples:

- fixture server imports a stale helper
- dashboard smoke route calls real backend when using fixture mode
- OpenAPI contract generation fails

### Lane 1: Deterministic NL Logic Gate

Purpose: exercise real LLM-agent classes, JSON parsing, accounting, workflow
logic, materialization, and error propagation without real LLM network calls.

- [ ] Run simulated NL unit gate.

```bash
POLISYOS_LLM_SIMULATION_MODE=1 \
uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q
```

Expected result:

- simulated single-model run completes
- simulated multi-model run respects budget guard
- no real `GatewayLLMClient` is constructed
- workflow failure propagates to failed job with actionable error

- [ ] Run LLM factory and agent JSON contract gate.

```bash
POLISYOS_LLM_SIMULATION_MODE=1 \
uv run pytest tests/unit/scientist/orchestration/llm/test_factory.py -q
```

Expected result:

- simulation mode returns `SimulatedGatewayLLMClient`
- real gateway unit tests explicitly opt out of simulation env
- PI, Drafter, Formalizer, and Critic JSON contracts are exercised

Release blocker examples:

- simulation env accidentally creates real gateway client
- malformed LLM response becomes a successful job
- token or cost accounting disappears in simulated mode

### Lane 2: Policy And Control Hardening Gate

Purpose: prove production profiles fail closed and durable control-plane
behavior is diagnosable.

- [ ] Run hardening lane.

```bash
POLISYOS_LLM_SIMULATION_MODE=1 \
uv run pytest \
  tests/unit/runtime/http/test_control_hardening.py \
  tests/unit/runtime/http/test_runtime_api_write_path_hardening.py \
  tests/unit/runtime/http/test_debug_api.py \
  tests/unit/runtime/http/test_control_plane_store.py \
  -q
```

Expected result:

- dev profile permits explicit mock fallback only where intended
- research/governed reject implicit mock fallback
- non-privileged callers cannot enable privileged policy flags
- rate limits and idempotency work on write paths
- control store timeout opens circuit and returns `503` or `504`
- worker shutdown does not leak heartbeat warnings across tests
- debug error endpoint aggregates manifest and workflow failures

Release blocker examples:

- governed profile permits `allow_mock_fallback=True` from an unprivileged caller
- embedded worker is accepted for a profile requiring external worker
- circuit breaker creates zombie workers or teardown failures

### Lane 3: Cross-Subsystem Spine Gate

Purpose: prove representative runtime, Data Forge, Scientist, Fabric, Foundry,
and dashboard bridge tests work together.

- [ ] Run the cross-subsystem spine.

```bash
POLISYOS_LLM_SIMULATION_MODE=1 \
uv run pytest \
  tests/unit/runtime/http/test_control_api.py \
  tests/unit/runtime/http/test_nl_pipeline_materialization.py \
  tests/unit/runtime/http/test_run_evidence_context_promotions.py \
  tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py \
  tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py \
  tests/integration/core_runtime/test_config_security_startup_bridge.py \
  tests/integration/foundry_scientist/test_method_node_bridge.py \
  tests/integration/scientist/test_workflow_reliability_scenarios.py \
  tests/integration/scientist/test_workflow_tracing.py \
  tests/integration/fabric_ir/test_connector_observation_bridge.py \
  tests/integration/foundry_calibration/test_method_calibration_bridge.py \
  -q --maxfail=1
```

Expected result:

- all non-gated tests pass
- tracing test skips only when `POLISYOS_RUN_INTEGRATION=1` is absent
- no leaked worker or fixture runtime state affects later tests

Release blocker examples:

- Scientist reliability scenarios fail after runtime changes
- run evidence promotion decisions are not visible through runtime API
- Foundry or Fabric bridge tests fail due to contract drift

### Lane 4: Frontend Deterministic Smoke Gate

Purpose: prove dashboard journeys work against deterministic backend fixtures
and that standalone Playwright uses the same no-real-LLM lane.

- [ ] Run standalone smoke.

```bash
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
```

Expected result:

- Playwright webServer starts fixture runtime API with
  `POLISYOS_LLM_SIMULATION_MODE=1`
- evidence flow passes
- knowledge flow passes
- run flow passes
- desktop and mobile smoke projects pass

- [ ] Run frontend lint on touched e2e/config files after frontend changes.

```bash
corepack pnpm --dir apps/runtime-dashboard exec eslint \
  playwright.config.ts \
  e2e/helpers/runtime-dashboard.ts \
  e2e/journeys/evidence-flow.spec.ts \
  e2e/journeys/knowledge-flow.spec.ts
```

Expected result:

- no lint errors
- no route-mocked journey performs unintended upstream mutation

Release blocker examples:

- smoke passes only because routes are mocked and fixture backend is unused
- dashboard cannot open real artifact links
- mobile navigation hides the intended route target

### Lane 5: Prod-Like Staging Canary

Purpose: prove production policies and infrastructure shape without production
blast radius.

Required preflight:

- [ ] Confirm simulation is disabled.

```bash
test "${POLISYOS_LLM_SIMULATION_MODE:-0}" = "0"
```

- [ ] Confirm production-like execution profile and external worker.

```bash
test "${POLISYOS_EXECUTION_PROFILE}" = "governed" -o \
     "${POLISYOS_EXECUTION_PROFILE}" = "research"
test "${POLISYOS_CONTROL_WORKER_BACKEND}" = "external"
test "${POLISYOS_CONTROL_STATE_STORE_BACKEND}" != "sqlite"
```

- [ ] Confirm gateway and runtime endpoint variables are available in the
  operator shell. Values must come from the secret manager and must not be
  committed.

```bash
test -n "${RUNTIME_BASE_URL}"
test -n "${RUNTIME_AUTH_HEADER}"
test -n "${POLISYOS_LLM_GATEWAY_BASE_URL}"
test -n "${POLISYOS_LLM_GATEWAY_API_KEY}"
```

Submit canary:

```bash
curl -sS -X POST "${RUNTIME_BASE_URL}/api/v1/control/runs" \
  -H "${RUNTIME_AUTH_HEADER}" \
  -H "Content-Type: application/json" \
  -H "X-Idempotency-Key: policyos-prodlike-canary-2026-05-10-001" \
  --data @- <<'JSON'
{
  "prompt": "Design a targeted policy package to support Ukrainian micro, small, and medium enterprises under wartime constraints. Use available macroeconomic and labor market indicators, identify required data sources, propose interventions, and produce an auditable decision bundle.",
  "execution_profile": "governed",
  "allow_mock_fallback": false,
  "llm_models": ["primary-governed-canary"],
  "max_parallel_models": 1,
  "budget": {
    "max_llm_calls": 16,
    "max_tokens": 24000,
    "max_cost_usd": 5.0,
    "timeout_seconds": 900
  }
}
JSON
```

Expected response:

- HTTP `200` or accepted response defined by runtime contract
- response contains `job_id`
- response contains `run_id` or job endpoint later resolves `run_id`
- no field indicates mock or simulated fallback

Poll job:

```bash
curl -sS "${RUNTIME_BASE_URL}/api/v1/control/jobs/${JOB_ID}" \
  -H "${RUNTIME_AUTH_HEADER}"
```

Expected terminal state:

- `completed`
- or `failed` only when the error is actionable and belongs to an expected
  injected failure scenario

Post-run API checks:

```bash
curl -sS "${RUNTIME_BASE_URL}/api/v1/runs/${RUN_ID}" \
  -H "${RUNTIME_AUTH_HEADER}"

curl -sS "${RUNTIME_BASE_URL}/api/v1/runs/${RUN_ID}/timeline" \
  -H "${RUNTIME_AUTH_HEADER}"

curl -sS "${RUNTIME_BASE_URL}/api/v1/runs/${RUN_ID}/evidence-context" \
  -H "${RUNTIME_AUTH_HEADER}"
```

Expected result:

- run detail includes execution profile and control job link
- timeline contains NL, retrieval/materialization, and Scientist workflow steps
- evidence context references materialized artifacts
- LLM events identify real provider/model, not `simulated_gateway`
- token/cost accounting is present

Release blocker examples:

- run completes while using simulation or mock fallback
- job remains `running` after timeout without a failure reason
- artifacts exist in job report but cannot be fetched through runtime API
- dashboard shows completed run but API contract shape is invalid

### Lane 6: Real Production Canary

Purpose: prove the production deployment can complete one small real run.

Controls:

- one isolated canary tenant or owner-approved tenant
- one canary request
- cost cap no higher than the approved canary budget
- explicit idempotency key
- alerting owner watching logs and metrics during the run
- rollback decision owner identified before launch

Execution:

- [ ] Run production preflight from Lane 5 against production endpoint.
- [ ] Submit the canonical canary request.
- [ ] Poll job until terminal state.
- [ ] Open dashboard against production backend.
- [ ] Inspect run overview, timeline, artifacts, evidence context, lineage, and
  audit/deck views.
- [ ] Export evidence bundle.

Production canary acceptance:

- terminal state is `completed`
- no mock fallback
- no simulated gateway
- real data provider is visible in retrieval/materialization evidence
- workflow report is persisted and readable
- decision artifacts are persisted and readable
- dashboard can inspect all required views
- trace/log/metric evidence can explain the run from request to artifact
- cost and token usage are below canary budget

Immediate stop conditions:

- unexpected cross-tenant access
- real LLM call volume exceeds budget
- job queue stops processing unrelated production work
- CAS integrity check fails
- runtime API returns successful status for corrupt or missing artifacts
- dashboard triggers destructive control mutation unintentionally

### Lane 7: Production Failure Canary

Purpose: prove that production failures are safe, actionable, and observable.

Run one controlled failure after the happy canary succeeds. Prefer the least
expensive failure injection available in the deployment:

| Failure | Injection method | Expected result |
| --- | --- | --- |
| LLM budget exceeded | set canary budget below required token/call budget | failed job with budget error and no partial success |
| Unknown model | request a disabled canary model variant | failed job naming model policy or gateway config owner |
| Retrieval unavailable | use an approved invalid canary provider/profile | failed job naming retrieval/materialization layer |
| Missing artifact ref | submit or inject a canary payload with a missing artifact reference in staging first | failed job naming artifact ref and owning boundary |
| Workflow report failure | use staging-only workflow failure injection, then production only if owner-approved | failed job with workflow report `status=fail` |

Acceptance:

- job reaches `failed`
- error is visible through `/api/v1/control/jobs/{job_id}`
- timeline or debug endpoint can explain failure boundary
- no dashboard blank state
- no silent fallback to mock, simulation, or stale artifact
- no leaked worker lease after terminal failure

## Security And Authorization Gates

Run before production canary and after authz changes:

- [ ] Tenant-scoped access permits own run.
- [ ] Cross-tenant run access returns forbidden.
- [ ] Cross-tenant artifact access returns forbidden.
- [ ] Missing claims fail closed.
- [ ] Privileged policy flags require privileged caller.
- [ ] Review websocket rejects anonymous connect.
- [ ] Control mutations append audit trail.

Representative command:

```bash
uv run pytest tests/unit/runtime/http/test_runtime_api_authz.py -q
```

Production proof:

- capture one authorized run detail request
- capture one forbidden cross-tenant request
- capture one mutation audit entry for canary launch

Release blocker examples:

- missing claims are accepted
- cross-tenant artifact is readable
- audit trail is missing for canary control mutation

## Performance And Bottleneck Gates

### Local Hot Path Baseline

```bash
uv run pytest tests/performance/test_runtime_hot_paths.py -q
```

Track these values on every release candidate:

- control job lease time
- NL step durations
- LLM call latency and retry count
- CAS put/get latency
- retrieval/materialization duration
- run index refresh/list latency
- timeline build latency
- lineage build latency
- dashboard first meaningful route render

Initial blocking thresholds for canary readiness:

| Surface | Threshold |
| --- | ---: |
| Runtime health response | p95 <= 2 s |
| Control job accepted response | p95 <= 5 s |
| First job lease after submit | p95 <= 15 s |
| CAS small artifact get | p95 <= 1 s |
| Run detail response | p95 <= 3 s |
| Timeline response | p95 <= 5 s |
| Dashboard first meaningful route render | p95 <= 8 s |
| Canary total wall-clock | <= 15 min |

If a threshold fails:

- classify whether the bottleneck is expected external latency or internal work
- add boundary metrics before optimizing
- optimize the owning layer
- preserve contract shape
- rerun the smallest hot path and then the broad canary gate

### Staging Soak

Run after one staging canary succeeds:

- [ ] Submit 10 sequential canary-sized jobs.
- [ ] Submit 5 jobs with controlled concurrency of 2.
- [ ] Confirm no leaked worker leases.
- [ ] Confirm no stuck jobs.
- [ ] Confirm CAS artifact count and run index count match completed jobs.
- [ ] Confirm p95 latencies remain within staging thresholds.

Release blocker examples:

- worker leases remain active after terminal states
- run index loses completed runs
- dashboard cannot list recent canary runs
- retries create duplicate external LLM work without idempotency evidence

## Dashboard Against Real Backend

Fixture-backed smoke is necessary but not sufficient. For staging and production
canary proof:

- [ ] Run dashboard against the real runtime backend.
- [ ] Disable route-mocked e2e helpers.
- [ ] Use a canary run created by the real runtime API.
- [ ] Open these views:
  - run overview
  - timeline
  - artifacts
  - artifact detail
  - evidence context
  - lineage
  - audit report
  - generated deck or export surface when present
- [ ] Save Playwright trace on failure and screenshots on success for release
  evidence.

Expected result:

- no unhandled console errors
- no failed API response hidden by client fallback
- no stale fixture data appears in production mode
- all artifact links resolve through runtime API

## Observability Proof

For each staging and production canary, the operator must be able to follow one
correlation chain:

```text
HTTP request id
  -> control job id
  -> run id
  -> payload artifact id
  -> LLM call events
  -> retrieval/materialization artifact ids
  -> workflow report artifact id
  -> run index record
  -> dashboard network request
```

Required dashboards or logs:

- API request count and error rate
- control job states and lease age
- external worker heartbeat state
- LLM calls by provider/model/status
- token and cost counters
- CAS put/get error rate and latency
- retrieval/materialization status
- dashboard API error rate

Release blocker examples:

- completed canary cannot be correlated across API, job, and artifacts
- LLM cost is visible only in logs and not in metrics or job evidence
- failed run has no trace or missing job error

## Data Integrity And Artifact Verification

After every canary:

- [ ] Verify each artifact ID referenced by job payload exists.
- [ ] Verify each workflow report artifact exists.
- [ ] Verify each decision/audit/deck artifact linked by dashboard exists.
- [ ] Verify artifact content kind and media type match the runtime contract.
- [ ] Verify missing artifact refs fail closed in staging failure injection.
- [ ] Verify artifact access obeys tenant and scope rules.

Acceptance:

- all referenced artifacts are retrievable
- immutable content IDs are stable
- artifact inspector can render or safely summarize supported artifact types
- unsupported or missing artifacts produce typed errors

## Regression Test Policy

For every production-like failure:

- write the smallest failing automated regression test at the owning layer
- verify it fails before the fix when practical
- implement one root-cause fix
- rerun the targeted test
- rerun the closest broader gate
- record evidence in the failure note

Regression placement guide:

| Failure location | Preferred test location |
| --- | --- |
| Runtime API contract shape | `tests/unit/runtime/http/` or contract bridge |
| Control job lifecycle | `tests/unit/runtime/http/test_control_plane_store.py` or control service tests |
| NL orchestration | `tests/unit/runtime/http/test_nl_pipeline_materialization.py` |
| LLM factory/client behavior | `tests/unit/scientist/orchestration/llm/` |
| Scientist workflow | `tests/integration/scientist/` or `tests/unit/scientist/orchestration/` |
| Fabric/Foundry bridge | `tests/integration/fabric_ir/`, `tests/integration/foundry_*` |
| Dashboard route behavior | `apps/runtime-dashboard/e2e/journeys/` |
| Tooling/local stack | `tests/repo_quality/tools/` |

## Go/No-Go Criteria

### Go To Staging Canary

- Lane 0 green
- Lane 1 green
- Lane 2 green
- Lane 3 green
- Lane 4 green
- runtime contract green
- no unresolved release-blocking warnings from recent debug loop

### Go To Production Canary

- staging prod-like happy canary completed
- staging failure canary failed cleanly
- security/authz gate green
- observability correlation proof complete
- owner accepted cost and timeout budgets
- rollback owner and stop conditions acknowledged

### Production E2E Proven

Production e2e is proven only when all are true:

- one production real LLM canary completed
- one production or owner-approved staging failure canary failed cleanly
- real external data provider was used in happy canary
- durable control-plane and external worker were used
- no mock fallback or simulation appeared in evidence
- artifacts, timeline, lineage, evidence context, and dashboard views were
  inspectable
- authz and audit evidence exists
- token/cost accounting exists
- run can be explained from request to final artifact through logs, metrics,
  traces, and API records

## Known Follow-Up Risks

These are not automatic blockers unless they affect the canary acceptance
criteria:

- Prometheus exporter port conflicts in local smoke can hide observability
  hygiene issues. File an observability follow-up if this appears in staging.
- Deprecated compatibility imports add warning noise. They should not block e2e
  proof unless they hide real failures.
- Full repository Ruff may flag existing test-style rules such as `S101 assert`
  and missing annotations. Use targeted lint for changed files unless the
  release owner requests a broader style cleanup lane.

## Execution Checklist

- [ ] Record git revision and environment lane.
- [ ] Run Lane 0.
- [ ] Run Lane 1.
- [ ] Run Lane 2.
- [ ] Run Lane 3.
- [ ] Run Lane 4.
- [ ] Run runtime contract check.
- [ ] Run hot path baseline.
- [ ] Prepare staging secrets and budget caps.
- [ ] Run staging happy canary.
- [ ] Run staging failure canary.
- [ ] Run security/authz proof.
- [ ] Run dashboard against staging real backend.
- [ ] Export staging evidence bundle.
- [ ] Review go/no-go with owner.
- [ ] Run production preflight.
- [ ] Run production happy canary.
- [ ] Run owner-approved production or staging failure canary.
- [ ] Export production evidence bundle.
- [ ] Archive final report under `docs/archive/reports/`.
- [ ] Create follow-up issues for non-blocking risks.

## Appendix A: Current Fast-Lane Commands

```bash
uv run pytest --collect-only \
  tests/unit/runtime/http/test_control_api.py \
  tests/unit/runtime/http/test_nl_pipeline_materialization.py \
  tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py \
  -q

POLISYOS_LLM_SIMULATION_MODE=1 \
uv run pytest tests/unit/runtime/http/test_nl_pipeline_materialization.py -q

uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract

uv run python tools/quality/testing/local_integration_stack.py smoke

corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke

uv run pytest tests/performance/test_runtime_hot_paths.py -q
```

## Appendix B: Minimal Evidence Summary Template

```markdown
# PolicyOS E2E Evidence Summary

- Date:
- Environment lane:
- Git revision:
- Runtime endpoint:
- Execution profile:
- Worker backend:
- State store backend:
- Artifact backend:
- LLM provider/model:
- Data provider/profile:
- Job ID:
- Run ID:
- Terminal state:
- Cost:
- Tokens:
- Wall-clock duration:
- Request trace ID:
- Workflow report artifact:
- Decision artifact:
- Evidence context artifact:
- Dashboard trace path:

## Result

- Happy canary:
- Failure canary:
- Release blockers:
- Operational follow-ups:

## Root-Cause Notes

- Failure note links:
```
