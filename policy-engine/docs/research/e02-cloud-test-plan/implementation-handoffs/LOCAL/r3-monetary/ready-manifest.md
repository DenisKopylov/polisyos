# R3 readiness manifest

This manifest records the R3 source boundary, current deciding checks, and the
held F numerical wave. It is a candidate handoff, not a G acceptance or finding
closure. Root owns Git operations and final source freezing.

## R3 change surface

The monetary implementation boundary is:

- Provider status, producer event and response extraction:
  `src/polisyos/core/llm/{response.py,traced_client.py,settlement.py}` and
  `src/polisyos/scientist/orchestration/llm/{gateway_client.py,prompt_cache.py,factory.py}`.
- Durable local settlement and request budgets:
  `src/polisyos/scientist/orchestration/engine/{budget_ledger.py,budget_middleware.py}` and
  `src/polisyos/scientist/orchestration/llm/budget_enforcer.py`.
- Ordinary NL event collection and per-call projection:
  `src/polisyos/runtime/http/services/control/{response_shapes.py,nl_pipeline.py,run_lifecycle.py,generation_cycle.py}`;
  funnel origin setters/consumers in `src/polisyos/scientist/methods/search/funnel/`
  (`types.py`, `orchestrator.py`, `level2_causal.py`, `level3_medium.py`,
  `level4_full.py`, `level5_refutation_governance.py`, and `level6_promotion.py`);
  `src/polisyos/scientist/methods/search/voi_scheduler.py`;
  `src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py`;
  and `src/polisyos/runtime/quality/design_generation.py`.
- Runtime composition: the R3 monetary hunk in
  `src/polisyos/runtime/http/container.py` adds a typed durable-store override,
  default app-scoped `FileBudgetLedger(core_runs_root / ".runtime" /
  "llm-cost-ledger.json")`, and service binding. This file is shared with R4:
  preserve R4's `process_worker_capacity`, `process_worker_profile_revision`,
  and early shared-executor profile configuration independently. The same
  app-scoped store reaches the served request context through
  `src/polisyos/runtime/http/dependencies.py`.
- Companion V1-owned public bridge: `src/polisyos/core/contracts/runtime.py`,
  `src/polisyos/runtime/http/services/debug.py`,
  `src/polisyos/runtime/http/routes/runs.py`,
  `src/polisyos/runtime/quality/design_generation.py`, and the control-plane
  lifecycle/generation-cycle files listed above. The dashboard consumer is
  `apps/runtime-dashboard/src/shared/lib/domain/agents.ts` and its test, plus
  `apps/runtime-dashboard/src/api/validators.ts` and its test. V1 owns those
  DTO, route, and dashboard source hunks.

Documentation/release companions:

- `src/polisyos/core/llm/README.md`
- `src/polisyos/scientist/orchestration/llm/README.md`
- `src/polisyos/scientist/orchestration/engine/README.md`
- `src/polisyos/runtime/http/README.md`
- `docs/reference/api/runs.md`
- `release-fragments/unreleased/2026-10-09-e02-r3-llm-cost-status.toml`

## Exact R3 light verification

Run from `policy-engine/`. The full output is retained at
`LOCAL/r3-monetary/final-integrated.log`; JUnit XML is
`LOCAL/r3-monetary/final-integrated.xml`.

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/final-integrated.xml \
  tests/unit/core/llm/test_response.py \
  tests/unit/core/llm/test_traced_client_settlement.py \
  tests/unit/scientist/orchestration/llm/test_gateway_client_retry.py \
  tests/unit/scientist/orchestration/llm/test_prompt_cache_scope_admission.py \
  tests/unit/scientist/orchestration/llm/test_factory.py \
  tests/unit/scientist/orchestration/engine/test_budget_ledger_producer_events.py \
  tests/unit/runtime/http/services/test_response_shapes_monetary.py \
  tests/unit/runtime/http/test_nl_pipeline_cost_projection.py \
  tests/unit/runtime/http/test_insights_api.py \
  tests/unit/runtime/http/test_runtime_service_container.py::test_runtime_container_wires_durable_llm_producer_settlement_store \
  tests/unit/runtime/http/test_debug_api.py::test_debug_artifact_reads_preserve_selected_manifest_profile \
  > docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/final-integrated.log 2>&1
```

The latest integrated candidate run passed **160 tests**, with **0 failures, 0
errors, and 0 skips**; two upstream Torch/Python 3.14 deprecation warnings were
reported. The exact duration, counts, and per-test output are retained in the
XML and log above. The raw gateway decoder matrix was run separately:

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  --junitxml=docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/gateway-raw-contract.xml \
  tests/unit/scientist/orchestration/llm/test_gateway_client_retry.py::TestUsageParsing \
  > docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r3-monetary/gateway-raw-contract.log 2>&1
```

Result: **77 passed**, with no failures or skips. Raw-wire cases cover cost
number/string/bool/null/array/object values, missing fields, alias shadowing,
`usage.cost`, reported zero, underflow, malformed usage/status values, and
response model/provider spoofing through gateway/traced-client/ledger.

The nonempty Ruff path guard passed; complete output is
`LOCAL/r3-monetary/final-ruff-ready.log`:

```bash
.venv/bin/python -m ruff check \
  src/polisyos/core/llm/response.py \
  src/polisyos/core/llm/traced_client.py \
  src/polisyos/core/llm/settlement.py \
  src/polisyos/scientist/orchestration/llm/gateway_client.py \
  src/polisyos/scientist/orchestration/llm/prompt_cache.py \
  src/polisyos/scientist/orchestration/llm/factory.py \
  src/polisyos/scientist/orchestration/llm/budget_enforcer.py \
  src/polisyos/scientist/orchestration/engine/budget_ledger.py \
  src/polisyos/scientist/orchestration/engine/budget_middleware.py \
  src/polisyos/scientist/methods/search/funnel/types.py \
  src/polisyos/scientist/methods/search/funnel/orchestrator.py \
  src/polisyos/scientist/methods/search/funnel/level2_causal.py \
  src/polisyos/scientist/methods/search/funnel/level3_medium.py \
  src/polisyos/scientist/methods/search/funnel/level4_full.py \
  src/polisyos/scientist/methods/search/funnel/level5_refutation_governance.py \
  src/polisyos/scientist/methods/search/funnel/level6_promotion.py \
  src/polisyos/scientist/methods/search/voi_scheduler.py \
  src/polisyos/scientist/nodes/builtins/decide/run_policy_blueprint_runtime.py \
  src/polisyos/runtime/http/services/control/response_shapes.py \
  src/polisyos/runtime/http/services/control/nl_pipeline.py \
  src/polisyos/runtime/http/services/control/run_lifecycle.py \
  src/polisyos/runtime/http/services/control/generation_cycle.py \
  src/polisyos/runtime/http/services/debug.py \
  src/polisyos/runtime/http/container.py \
  src/polisyos/runtime/http/dependencies.py \
  src/polisyos/runtime/http/routes/runs.py \
  src/polisyos/runtime/quality/design_generation.py \
  src/polisyos/core/contracts/runtime.py \
  tests/unit/core/llm/test_response.py \
  tests/unit/core/llm/test_traced_client_settlement.py \
  tests/unit/scientist/orchestration/llm/test_gateway_client_retry.py \
  tests/unit/scientist/orchestration/llm/test_prompt_cache_scope_admission.py \
  tests/unit/scientist/orchestration/llm/test_factory.py \
  tests/unit/scientist/orchestration/engine/test_budget_ledger_producer_events.py \
  tests/unit/scientist/search/funnel/test_types.py \
  tests/unit/scientist/search/funnel/test_orchestrator.py \
  tests/unit/scientist/search/funnel/test_level2_causal.py \
  tests/unit/scientist/search/funnel/test_level3_medium.py \
  tests/unit/scientist/search/funnel/test_level4_full.py \
  tests/unit/scientist/search/funnel/test_level6_promotion.py \
  tests/unit/scientist/search/test_voi_scheduler.py \
  tests/unit/runtime/http/services/test_response_shapes_monetary.py \
  tests/unit/runtime/http/test_nl_pipeline_cost_projection.py \
  tests/unit/runtime/http/test_insights_api.py \
  tests/unit/runtime/http/test_runtime_service_container.py \
  tests/unit/runtime/http/test_debug_api.py
```

The executed Ruff command used an explicit nonempty file list; it did not depend
on shell glob expansion. No install, full backend suite, DoWhy fit, GCM fit,
DiD, RDD, Monte Carlo, explainability, or other heavy numerical test was run.

## R3 consumer and remaining composition boundary

The actual route witness is
`test_nl_pipeline_cost_projection.py::test_ordinary_nl_post_persists_and_serves_durable_cost_events_after_reopen`.
It submits a real NL POST, checks the persisted created-event/outbox, dispatches
the worker, binds the indexed run to its persisted ControlJob owner, reopens the
app ledger, and reads the fresh `/agents` route. It also inserts a durable
begin-only event at the crash boundary and confirms fresh GET serves it as
pending/unknown with a null amount and ledger durability. This simulates the
crash boundary; it does not kill a process between filesystem operations.

`test_insights_api.py` now uses the same real POST/job/run owner helper before
writing typed reported/estimated/reuse/unknown ledger events. Strict reader
reconciliation still refuses foreign owner rows, payload conflicts, and
ledger-durable DTO markers without a matching durable event. CAS readers retain
selected refs; job payload reads resolve manifest profile from persisted CAS
metadata only after matching the expected kind from the server-owned job row.

One external billing fact remains outside local custody: a configured gateway
can retry HTTP requests under one idempotency key, and no provider idempotency
or final invoice receipt is present. Local settlement records configured
logical route/model intent only. Raw response model/provider labels are
non-authoritative metadata and cannot alter event identity or pricing basis.

## Held F numerical wave

Read the complete occurrence-level source matrix in
`LOCAL/reviews/f-original-criteria/F-original-criteria-review.md` before
running this wave. It binds the F proposed-closed Q0 queue at 33 IDs / 34
occurrences (LA-016 occurs twice) to the pinned original source cut and
separates old receipt equality from current-candidate verification. No item in
that matrix is formally closed here. Do not invent law, a source issuer,
training law, target population, calibration, or a backend profile.

After the Linux profile is frozen and root releases the single native slot, the
minimum real-worker/cross-boundary probe is this exact selector set from
`policy-engine/`:

```bash
: "${E02_TEST_DOWHY_WORKER_PYTHON:?set to the frozen selected DoWhy worker Python}"
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py::test_real_worker_job_cas_fresh_python314_reader \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py::test_real_estimate_point_only_survives_parent_cas_and_reader \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py::test_actual_estimator_malformed_ci_refused_in_parent \
  tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py::test_selected_profile_does_not_relabel_unsupported_requests
```

The worker path must be the frozen Python 3.12 / DoWhy 0.14 profile; the parent
reader is Python 3.14. Existing fixtures generate the explicit synthetic SCM
`X → A`, `X → Y`, `A → Y`, with `X ~ Normal(0,1)`, `A ~ Bernoulli(logit(X))`,
and `Y = 2A + 1.5X + Normal(0,1)`. The full positive uses `dgp(seed=19, n=500)`;
point-only uses `n=100`; source-binding refusal uses `n=80`; malformed-CI
refusals use `n=100`. The input is persisted to CAS before worker execution,
and the fresh reader validates the exact source ref. This synthetic known-DGP
positive verifies backend execution and bridge behavior only; it is not real
population evidence or a causal-authority claim.

For the masked-view handoff, the existing exact selectors are:

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  tests/unit/scientist/methods/backtesting/test_backtesting.py::test_scientist_dispatch_binds_masked_view_to_backend_input \
  tests/unit/scientist/methods/backtesting/test_backtesting.py::test_scientist_backtest_runs_and_reads_back_each_requested_replica
```

The first fixture starts with `metric=[1,2,900,901]` and times `t0..t3`, then
requires the CAS-bound backend input to contain only values `[1,2]` and times
`[t0,t1]`. The replica test requests three replicas and requires three distinct
run IDs, seeds 12/13/14, and persisted result/metric refs. Both current unit
tests replace the native Foundry execution producer; they are not a positive
native-method run. A source-bound native-method consumer positive is still
required if the original F discriminator requires the masked data to reach a
real numerical method.

The existing DoWhy unit selector above does not exercise a supported
non-default target/estimand request through the installed worker; its positive
uses the test's default request. `test_dowhy_v2_linear_confounding_matches_ground_truth`
does test `method_name="backdoor.linear_regression"` and
`estimand_type="nonparametric-ate"`, but routes through the explicit legacy
in-process profile and is not a substitute for the installed-worker bridge.
Carry B213 as a bounded `verification_missing` discriminator until a
source-bound supported request is executed by the selected worker and verified
by the fresh consumer. The exact next check is a genuine worker job whose
bound request and `identified_estimand`/target parameters are asserted across
the worker response, CAS artifact, and fresh Python 3.14 reader, paired with
the existing unsupported-request refusal selector.

For the remaining F IDs, use the exact per-ID discriminator/fixture/authority
notes in the cited F review table; rerun old receipts only when the original
source, profile, lock, inputs, producer, bridge, and consumer match. The F
queue covers B204–B213, B215–B225, B54, LA-001–004, LA-007, LA-016 (two source
occurrences), LA-017, LA-019, LA-020, LA-035, and LA-037. B214 and B56 remain
outside this proposed-closed queue. Preserve `G_code_acceptance=not_inferred`
and `G_finding_acceptance=not_issued`.

## Authority-envelope selected-view implementation delta

This delta extends the source boundary above with producer-selected authority
envelope manifest profiles and one canonical resolver. The exact touched source
paths, current hashes, selected-ref receiver hashes, focused command, complete
log/JUnit hashes, scoped red, and public-surface generation boundary are
recorded in `LOCAL/r3-monetary/receipt.md` under “Authority-envelope
selected-view delta.” Documentation/release companions are
`src/polisyos/core/artifacts/README.md` and
`release-fragments/unreleased/2026-10-09-e02-authority-envelope-selected-view.toml`.
The core facade exports the resolver and fixed contract constants. The optional
manifest-link profile remains absent from old serialized records. This is a
candidate delta, not a global freeze or a G closure.
