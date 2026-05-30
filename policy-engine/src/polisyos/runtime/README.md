# Runtime (`polisyos.runtime`)

## Purpose

`polisyos.runtime` is the runtime-facing boundary for replay planning,
completeness checks, verification, and the committed runtime API package under
`polisyos.runtime.http`. It bridges CAS-backed run state to HTTP, generated
clients, dashboards, and operator tooling.

## Where to Start

- `src/polisyos/runtime/__init__.py` for the stable replay facade.
- `src/polisyos/runtime/replay.py` for replay planning and verification logic.
- `src/polisyos/runtime/quality/closeout_reader.py` for the fail-closed
  Universal Policy Design Case closeout reader skeleton.
- `src/polisyos/runtime/quality/concept_spine.py` for W2.A hybrid concept-spine
  carriers, producer handshake/liveness records, and boundary-scoped bridge
  authority helpers.
- `src/polisyos/runtime/quality/producer_pipeline.py` for W7.F eight-stage
  producer orchestration over run carrier, spine bootstrap, producer preflight,
  first-pass context/blocker emission, provisional claim registry, second-pass
  bindings, semantic closure, and closeout/projection surfaces.
- `src/polisyos/runtime/quality/argument_graph.py` for W8.B argument/warrant
  graph emission, machine-readable warrant inspection, and SACM/CAE/GSN export
  over runtime Policy Design Case claim surfaces.
- `src/polisyos/runtime/quality/rule_evolution.py` for W2.B rule/taxonomy
  logic-hash registries, replay context, and public annotation state.
- `src/polisyos/runtime/quality/rule_replay_engine.py` for W9.F actual
  original-rule/new-rule replay execution, C33 change-class comparison, and
  claim-lifecycle revalidation triggers for closed Policy Design Cases.
- `src/polisyos/runtime/quality/complexity_governance.py` for W10.E Net-MAV
  gating, periodic prune/merge review, and self-application over W2.D
  self-FMEA telemetry.
- `src/polisyos/runtime/quality/wave2_walking_skeleton.py` for the Wave 2 I2
  vertical proof over request, concept spine, producer handshake, claim
  registry, closeout reader, typed projection, and semantic negative control.
- `src/polisyos/runtime/quality/ir_analytics_bridge.py` for the W3.A bridge
  that turns proof-carrying IR analytics certificates, proof statuses,
  uncertainty, negative certificates, conflicts, baselines, and
  proof-composability refs into claim-bound registry evidence.
- `src/polisyos/runtime/quality/calibration_ledger.py` for W2.E longitudinal
  calibration history and historical-prior influence records.
- `src/polisyos/runtime/quality/memory_influence.py` for W2.F balanced-memory
  influence records that guide future search/review without becoming current
  claim evidence.
- `src/polisyos/runtime/quality/acquisition_planner.py` for W3.G ADR-0166
  evidence acquisition planning, where eligibility and mandatory gates dominate
  VOI ranking before runtime blockers, deficits, or limitations are emitted.
- `src/polisyos/runtime/quality/cost_gate.py` for W10.D authority-level
  run-cost enforcement over W2.C cost/degradation telemetry, where production
  authority may receive typed blockers and research authority receives
  limitations only.
- `src/polisyos/runtime/quality/hypothesis_ledger.py` and
  `src/polisyos/runtime/quality/candidate_firewall.py` for W6.F candidate
  persistence and the LLM candidate-to-authority firewall over claim registry,
  semantic binding, public projection, export, and dashboard scorecard reads.
- `src/polisyos/runtime/http/README.md` for the FastAPI app, route layout, and
  service layer.

- `docs/reference/api/index.md` for the committed runtime API surface.
- `tools/ops_runners/runtime/check_runtime_api_contract.py` for OpenAPI drift checks.

## Public API

- Supported package entrypoint: `polisyos.runtime`
- Lazy exports from `src/polisyos/runtime/__init__.py`: `ReplayStrategy`,
  `ReplayPlan`, `CompletenessLevel`, `CompletenessReport`, `VerificationMode`,
  `VerificationConfig`, `VerificationResult`, `build_replay_plan`,
  `completeness_check`, `verify_replay`

- `polisyos.runtime.http` owns the runtime API assembly and OpenAPI snapshot
  inputs. Use its README when working on HTTP wiring, security middleware, or
  generated-client drift.

## Internal Layout

- `__init__.py` and `replay.py` own the root replay facade.
- [`quality/`](quality/) owns runtime quality contracts, including the W1.D
  closeout reader skeleton that reads module evidence without letting
  readiness, dashboard, packaging, or public-export projections mint closeout
  authority. It owns the W2.A concept-spine and producer-handshake kernel that
  lets producers share governed concept scope without turning bridge records
  into producer domain evidence. It owns the W2.B rule evolution registry that distinguishes
  lossless alias migration from semantic rule changes and preserves old-logic
  replay for closed Policy Design Cases. It also owns W2.C cost/degradation
  telemetry for local production-debug bundles, W2.D soft-gate telemetry for
  warning owner/TTL lifecycle, bounded-liveness hooks, repair-decision FMEA
  annotations, advisory review telemetry, telemetry-derived complexity-budget
  reads, the Wave 2 I2 walking skeleton, the W3.A IR analytics bridge into
  runtime claim-registry entries, W2.E calibration-ledger influence records,
  W2.F balanced-memory influence records, the W3.G acquisition planner
  that turns evidence gaps into eligible next actions, accepted deficits,
  visible limitations, or closeout blockers without letting VOI rank around
  mandatory gates, the W10.D run-cost enforcement gate that turns governed
  cost budgets into authority-scoped blockers or limitations, and the W9.F rule
  replay engine that compares closed PDCs
  under original and new rule logic before triggering public revalidation. It
  also owns the W6.F hypothesis ledger and
  candidate-firewall reader checks that keep LLM/formulator candidates out of
  authority slots until producer or reader validation admits them, plus the
  W7.F eight-stage producer pipeline bridge that drives W7.A-E producers
  through the C40 liveness state machine without letting bridge records become
  producer-domain evidence, and the W8.B argument/warrant graph surface that
  exposes claim-to-readiness paths and typed warrant semantics without minting
  claim, evidence, projection, or closeout authority. W10.E complexity
  governance reads the W2.D self-FMEA telemetry surface to require expected
  Net-MAV plus telemetry refs before new controls enter the blocking frontier,
  and to mark controls, including complexity governance itself, for retire or
  merge when they stop affecting decisions after a measurement window.
- [`http/`](http/README.md) owns the FastAPI app, route/service layout,
  OpenAPI inputs, middleware, and generated-client compatibility surface.
- [`extensions/`](extensions/) owns runtime extension ABI helpers.
- Runtime-state migrations and retention policy live under
  [`../../../ops/migrations/runtime_state/README.md`](../../../ops/migrations/runtime_state/README.md)
  and [`../../../architecture/local_runtime_state.toml`](../../../architecture/local_runtime_state.toml).

## Extension Points

Runtime middleware plugins use the `polisyos.runtime_middlewares` entry-point
group declared in
[architecture/extension_points.toml](../../../architecture/extension_points.toml).
HTTP service behavior should be exposed through routes and OpenAPI contracts,
not by deep-importing service internals.

## Depends on / depended on by

Depends on: `polisyos.common`, `polisyos.core.contracts`,
`polisyos.core.artifacts`, `polisyos.core.security`, and the
`polisyos.runtime.http` subpackage for API assembly.

Depended on by: `packages/runtime-api-client`,
`apps/runtime-dashboard`, `apps/runtime-reference-shell`, runtime
runbooks, contract checks, and control-plane tooling.

## Common commands

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run python -c "import polisyos.runtime as runtime; print(sorted(runtime.__all__))"`

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python -c "import polisyos.runtime.http as runtime_http; print(sorted(runtime_http.__all__))"`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`

- Conceptual regeneration:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js`

## Tests

Run commands from the repository root `policy-engine/`.

- Smoke-tested:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/test_replay_runtime.py tests/unit/runtime/test_replay_input_bindings_completeness.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/quality/test_rule_evolution.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/quality/test_rule_replay_engine.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/quality/test_complexity_governance.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/quality/test_replay.py`

- Smoke-tested:
  `uv run pytest -q tests/unit/runtime/http/test_runtime_api_contract_hardening.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_api_maturity.py`

## Operability Links

- [Runtime component SLO](../../../ops/components/runtime/slo.yaml)
- [Runtime component runbooks](../../../ops/components/runtime/runbooks.md)
- [Runtime API outage runbook](../../../docs/runbooks/runtime-api-outage.md)
- [Runtime graceful shutdown and stuck worker runbook](../../../docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md)
- [Deploy runtime how-to](../../../docs/how-to/deploy-runtime.md)

## Known Shims/Deprecations

There are no active package-local root shims for `polisyos.runtime` in
[architecture/shims.toml](../../../architecture/shims.toml) as of 2026-05-06.
`runtime/http/services/control.py` and `runtime/http/openapi_contract.py` are
tracked in [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml)
with owner `team-runtime` and sunset `2026-12-31`.

## Reference docs

- [Runtime HTTP](http/README.md)
- [REST API Reference](../../../docs/reference/api/index.md)
- [Runs API](../../../docs/reference/api/runs.md)
- [Control Plane API](../../../docs/reference/api/control.md)
- [Artifact Inspection API](../../../docs/reference/api/artifacts.md)
- [Generated Artifacts](../../../docs/reference/generated-artifacts.md)
- [Cost And Degradation Telemetry](../../../docs/reference/runtime/cost-degradation-telemetry.md)
- [Runtime API client](../../../packages/runtime-api-client/README.md)
- [Runtime dashboard](../../../apps/runtime-dashboard/README.md)
- [Runtime reference shell](../../../apps/runtime-reference-shell/README.md)
- [Calibration ledger](../../../docs/reference/runtime/calibration-ledger.md)

- Last updated: 2026-05-24
