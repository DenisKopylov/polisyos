# Scientist (`polisyos.scientist`)

## Purpose

`polisyos.scientist` is the orchestration layer that turns an
`ExperimentState` into a routed workflow run, executes builtin nodes, applies
governance, and publishes replayable decision artifacts across the `ir`,
`foundry`, `fabric`, `lex`, `scholar`, and `core` stacks.

## Where to Start

- Stable facade and top-level entrypoint: [`__init__.py`](__init__.py) and [`api.py`](api.py)
- Supported compute and bridge facades: [`compute/README.md`](compute/README.md) and [`adapters/README.md`](adapters/README.md)
- Workflow assembly and routing: [`orchestration/workflows/README.md`](orchestration/workflows/README.md) and [`orchestration/workflows/builder.py`](orchestration/workflows/builder.py)
- DAG execution semantics: [`orchestration/engine/README.md`](orchestration/engine/README.md)
- Method lanes for search, discovery, and research DAG: [`methods/README.md`](methods/README.md)
- Policy-design candidate, objective, critique, claim-decomposition, and
  baseline-comparison contracts:
  [`policy_design/`](policy_design/)
- Builtin runtime nodes: [`nodes/README.md`](nodes/README.md)
- Governance, calibration, human review, and continuous governance: [`governance/README.md`](governance/README.md)
- Validation, decision validity, verified policy, and IC verification: [`validation/README.md`](validation/README.md)
- Decision-grade publishing facade: [`publishing/README.md`](publishing/README.md)
- Extension contracts: [`extensions/`](extensions/)

## Public API

- `run_experiment(...)` in [`api.py`](api.py): top-level execution entrypoint used by the package facade
  Its optional `on_run_finalized` callback receives the selected run-manifest
  reference produced by the actual workflow, while the returned state shape is unchanged.
- `ExperimentState` in [`orchestration/engine/state.py`](orchestration/engine/state.py): boundary model passed across nodes and checkpoints
- Workflow launchers in [`orchestration/workflows/builder.py`](orchestration/workflows/builder.py): `run_default_workflow(...)`, `run_causal_full_workflow(...)`, `run_policy_verified_workflow(...)`, `run_policy_design_workflow(...)`, and `run_discovery_workflow(...)`
- Workflow specs in [`orchestration/workflows/`](orchestration/workflows/): inspect builtin DAG layouts before changing routing or nodes
- Search, discovery, and research-DAG implementations live under
  `src/polisyos/scientist/methods/`. Use the `polisyos.scientist.methods.*`
  namespace for new imports. Scientist causal graph discovery is distinct from
  Core plugin and entry-point discovery in `polisyos.core.discovery`; keep each
  route package-qualified. The retired `polisyos.scientist.discovery` root is
  negative-tested and is not declared as an active compatibility root.
- Governance helpers in [`governance/preflight.py`](governance/preflight.py) and [`governance/postflight.py`](governance/postflight.py): pre/post-flight validation surfaces
- Governance pass discovery via `load_governance_passes()` and `build_governance_pipeline()` in [`api.py`](api.py): explicit `polisyos.scientist_governance_passes` extension path with builtin fallbacks
- Bounded agent adapter support via the root facade: `ToolRegistry`,
  `ToolDefinition`, `run_tool_loop`, `ToolLoopResult`,
  `create_traced_gateway_client`, and tool-contract summary helpers
- Legal-knowledge benchmark composition via `ScientistLegalBenchmarkRunner`:
  consumes the content-bound Lex semantic receipt and adds an explicitly
  non-authoritative Scientist retrieval diagnostic over Data Forge fixtures
- Governance lifecycle hubs in [`governance/continuous/`](governance/continuous/) and [`governance/human_review/`](governance/human_review/): post-publication validity, reissue, withdrawal, and human oversight
- Validation hubs in [`validation/decision_validity.py`](validation/decision_validity.py), [`validation/policy_verified/`](validation/policy_verified/), and [`validation/verification/`](validation/verification/): decision lifecycle validation, verified-policy models/services, and proof-carrying verification
- `builtin_nodes()` and `discover_scientist_nodes()` in [`nodes/__init__.py`](nodes/__init__.py): builtin node inventory and explicit `polisyos.scientist_nodes` component discovery
- Publishing helpers in [`publishing/`](publishing/): canonical decision-grade export surface; legacy `publisher` imports are compatibility shims

## Internal Layout

- [`api.py`](api.py) and [`__init__.py`](__init__.py) own the stable root
  facade.
- [`orchestration/`](orchestration/README.md) owns engine, workflow, LLM, and
  runtime lanes.
- [`nodes/`](nodes/README.md) owns builtin node registration and stage-specific
  node implementations.
- [`methods/`](methods/README.md) owns search, discovery, causal, DOE,
  backtesting, and research DAG method lanes.
- [`policy_design/`](policy_design/) owns typed policy candidate schemas,
  objective extraction, deterministic critics, W6.D claim-decomposition seed
  records, and W8.C baseline/alternative comparison records for superiority
  claim gating.
- [`cross_graph/`](cross_graph/) owns cross-graph evidence need compilation,
  detector backstops, and W8.E conflict-to-portfolio materialization.
- [`governance/`](governance/README.md), [`validation/`](validation/README.md),
  [`evidence/`](evidence/README.md), [`feedback/`](feedback/README.md), and
  [`replay/`](replay/README.md) own decision validity, oversight, and replay
  contracts.
- [`publishing/`](publishing/README.md) owns decision-grade export and
  publication helpers.

## Extension Points

- External nodes use `polisyos.scientist_nodes`; see
  [nodes/README.md](nodes/README.md) and
  [architecture/extension_points.toml](../../../architecture/extension_points.toml).
  Builtin nodes are exposed through
  `polisyos.scientist.nodes.components:__polisyos_components__`.
- External governance passes use `polisyos.scientist_governance_passes`; see
  [governance/passes/README.md](governance/passes/README.md).

## Depends On / Depended On By

- Depends on: [`../core/README.md`](../core/README.md), [`../ir/README.md`](../ir/README.md), [`../foundry/README.md`](../foundry/README.md), [`../fabric/README.md`](../fabric/README.md), [`../lex/README.md`](../lex/README.md), and [`../scholar/README.md`](../scholar/README.md)
- Depended on by: runtime/control flows, policy-design entrypoints, and the Scientist verification surface in [`../../../tests/unit/scientist/README.md`](../../../tests/unit/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Historical inherited import-check entry; the prior README labeled it smoke-tested, but no qualified receipt is retained and it was not rerun for this refresh: `uv run python -c "from polisyos.scientist import ExperimentState, run_experiment; print(ExperimentState.__name__, callable(run_experiment))"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist -q`

## Tests

Historical inherited test command. The prior README labeled it smoke-tested,
but no qualified receipt is retained and it was not rerun for this refresh.

```bash
uv run pytest tests/unit/scientist/orchestration/workflows/test_workflow_selection.py tests/unit/scientist/governance/test_reliability_scorecard.py -q
```

Package test ownership is documented in
[`../../../tests/unit/scientist/README.md`](../../../tests/unit/scientist/README.md).
Run node and workflow tests together when state aliases or DAG routing change.

## Operability Links

- [Scientist component SLO](../../../ops/components/scientist/slo.yaml)
- [Scientist component runbooks](../../../ops/components/scientist/runbooks.md)
- [Reliability scorecard](../../../docs/reference/scientist/reliability-scorecard.md)
- [Research DAG replay](../../../docs/reference/scientist/research-dag-replay.md)
- [Runtime API outage runbook](../../../docs/runbooks/runtime-api-outage.md)

## Known Shims/Deprecations

- The status of first-level Scientist method roots is inconsistent across
  `architecture/packages/scientist.toml`, `architecture/shims.toml`, and the
  checked-in `tests/unit/scientist/methods/test_import_shims.py`.
  The import-contract test asserts that old `search`, `discovery`, and
  `research_dag` roots are unavailable, while package metadata declares a
  different compatibility-root set. Use `polisyos.scientist.methods.*` for new
  imports; reconcile those registries before documenting the old roots as
  supported.
- High-complexity Scientist nodes and validation modules are tracked in
  [architecture/module_size_budget.toml](../../../architecture/module_size_budget.toml)
  with owner `team-scientist` and sunset `2026-12-31`.
- Deprecate node IDs, workflow names, and state aliases through workflow
  migration notes and compatibility tests before deletion.

## Reference Docs

- Reference index: [`../../../docs/reference/scientist/index.md`](../../../docs/reference/scientist/index.md)
- Workflow catalog: [`../../../docs/reference/scientist/workflows.md`](../../../docs/reference/scientist/workflows.md)
- Builtin node reference: [`../../../docs/reference/scientist/nodes.md`](../../../docs/reference/scientist/nodes.md)
- Reliability and release gates: [`../../../docs/reference/scientist/reliability-scorecard.md`](../../../docs/reference/scientist/reliability-scorecard.md)
- Lane source plan: [`../../../docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md`](../../../docs/plans/active/SCIENTIST_AUDIT_REMEDIATION_PLAN.md)

## Last Updated

- Last updated: 2026-10-14

Canonical epoch issuance uses a neutral port in `validation/epoch_certificate_issuance.py`.
The actual decision-packet builder owns invocation/completion emission; Runtime
supplies complete-source admission and persistence through privileged composition.
The root facade exposes these port/readback types, the existing Decision Validity
owner and the exact governance-monitor reader. It exposes no completion minting
operation. Empty authority/environment slots retain typed nonreceipts.

## Candidate Protocol Facade\n\nThe root facade exports the existing typed `CritiqueReport` and `DraftResult` protocols for runtime consumers. Both are same-object aliases; a candidate protocol does not grant validation or publication authority.
