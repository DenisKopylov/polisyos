# Nodes (`polisyos.scientist.nodes`)

## Purpose

`polisyos.scientist.nodes` contains the builtin Scientist nodes that the engine
registers and executes inside workflow DAGs. This is the practical runtime
surface for the `data`, `planning`, `compile`, `causal`, `simulate`,
`governance`, and `decide` stages.

## Where to Start

- Stable root export: [`__init__.py`](__init__.py)
- Component-provider declarations: [`components.py`](components.py)
- Builtin registry assembly: [`builtins/__init__.py`](builtins/__init__.py)
- Canonical state aliases: [`builtins/state_keys.py`](builtins/state_keys.py)
- Shared validation, tracing, guards, and error helpers: [`builtins/validation.py`](builtins/validation.py), [`builtins/tracing.py`](builtins/tracing.py), [`builtins/guards.py`](builtins/guards.py), and [`builtins/errors.py`](builtins/errors.py)
- Family implementations: [`builtins/data/`](builtins/data/), [`builtins/planning/`](builtins/planning/), [`builtins/compile/`](builtins/compile/), [`builtins/causal/`](builtins/causal/), [`builtins/simulate/`](builtins/simulate/), [`builtins/governance/`](builtins/governance/), and [`builtins/decide/`](builtins/decide/)

## Public API

- `builtin_nodes()` in [`__init__.py`](__init__.py): canonical builtin node inventory
- `builtin_node_components()` in [`components.py`](components.py): builtin nodes as `ComponentProvider` instances loaded through the same discovery path as external nodes
- `discover_scientist_nodes()` in [`__init__.py`](__init__.py): explicit node discovery for builtin and `polisyos.scientist_nodes` providers
- `NodeSpec`, `NodeOutcome`, `NodeError`, and `NodeEvent` in [`../orchestration/engine/protocol.py`](../orchestration/engine/protocol.py): contracts every builtin node must honor
- State alias registry in [`builtins/state_keys.py`](builtins/state_keys.py): canonical input/artifact/report keys reused by workflows and decision outputs
- Family-specific node implementations in [`builtins/`](builtins/): import concrete node classes directly from their family modules when editing behavior

## Internal Layout

- [`__init__.py`](__init__.py) exposes the builtin inventory and extension discovery helpers.
- [`components.py`](components.py) wraps builtin nodes in component providers for
  registry bootstrap and `polisyos.scientist_nodes` parity.
- [`builtins/__init__.py`](builtins/__init__.py) assembles the builtin registry
  consumed by workflow builders.
- [`builtins/state_keys.py`](builtins/state_keys.py) owns canonical state and
  artifact aliases shared across nodes and decision outputs.
- [`builtins/validation.py`](builtins/validation.py),
  [`builtins/tracing.py`](builtins/tracing.py),
  [`builtins/guards.py`](builtins/guards.py), and
  [`builtins/errors.py`](builtins/errors.py) are shared node-runtime helpers.
- Family directories under `builtins/` own one workflow stage each:
  `data`, `planning`, `compile`, `causal`, `simulate`, `governance`, and
  `decide`.
- `builtins/simulate/propagate_welfare.py` consumes an existing empirical
  posterior carrier as its finite weighted support. Multiple empirical inputs
  are sampled as paired rows only when their declared row identity, nonempty
  axis, length, and normalized weights agree; otherwise the welfare interval is
  withheld as partial. The joint identity is recorded as non-authoritative.
  Propagation reports and sample bundles bind selected PE envelope references,
  including their selected manifest profiles. Monte Carlo reports record one
  terminal outcome per requested draw. Incomplete runs retain only a conditional
  successful-draw summary, withhold the credible interval, and keep bounded
  exception diagnostics plus a hash of the sampled inputs rather than the raw
  inputs. The Welfare bundle point estimate remains the nominal-input evaluation;
  partial Monte Carlo bundles warn that the report mean is conditional on
  successful draws. Retries apply only to explicitly transient PolicyOS errors,
  at most once on the same sampled vector. A typed `WelfareSampleDomainError`
  marks one sampled point unavailable and records that declaration as
  consumer-asserted. Access, validation, and unclassified failures fail the node;
  incomplete draw sets retain the conditional summary and no Monte Carlo interval.

The registered welfare node and its public sample-domain error remain in
`simulate/propagate_welfare.py`. Adjacent `welfare_*` modules own context, GE,
covariance, draws, propagation, reports, and orchestration. The facade forwards
its evaluator and sampler callbacks; the draw path shares Foundry's bounded
evaluation-failure classifier rather than maintaining another cause traversal.

`simulate/run_distributional_analysis.py` retains the registered node and
orchestration contract. Adjacent `distributional_analysis_*` modules group its
ordinal, justification, bounds, artifact, and subgroup helpers. Existing helper
imports remain available through the canonical node module.

`causal/resolve_transport.py` retains the registered transportability node and
integration seams. `transport_resolution_inputs.py` owns input, context,
registry, and query selection; `transport_resolution_results.py` owns result
alignment, lineage, and projection helpers.

`decide/run_policy_blueprint_runtime.py` remains the canonical node and workflow
adapter. Its adjacent `policy_blueprint_runtime_*` modules group engine,
strategy, benchmark, and reporting operations. Reporting validates the whole
funnel projection before attaching state; an unrepresentable graph returns a
typed refusal and preserves prior state and CAS references.

`decide/policy_runtime_support.py` remains the caller-facing facade for typed
contracts, backend entry points, promotion, and compatibility wrappers.
`policy_runtime_artifacts.py` owns artifact and evidence operations;
`policy_runtime_metrics.py` owns metric projections. Import these operations
through the facade when instrumenting its safety and lifecycle seams.

The governance nodes retain their canonical entry points. Their calculation and
request helpers live in `normative_arbitration_calculations.py` and
`governance_gate_requests.py`. The shared governance artifact resolver adapts
Core CAS only at IR loader calls; Core-only consumers keep their original store.

The canonical decision-packet producer remains
`decision_packet.builder.BuildDecisionPacketNode.execute`. It captures the
invocation before payload construction, prepares validity and epochs before
publication gates, and persists to CAS after those gates. The five section
owners are `causal_sections`, `strategic_sections`, `outcome_sections`,
`basis_sections`, and `uncertainty_sections`; `validation` owns validation and
validity preparation. `enrichment` retains compatibility re-exports and
`_build_policy_summary`. `build_decision_packet.py` remains the compatibility
facade. The existing 296-name API is retained.

## Extension Points

- External nodes use the `polisyos.scientist_nodes` entry-point group declared
  in
  [`architecture/extension_points.toml`](../../../../architecture/extension_points.toml).
- Builtin nodes remain package-owned and must register through
  [`components.py`](components.py) while honoring
  [`../orchestration/engine/protocol.py`](../orchestration/engine/protocol.py).
- Use [AUTHORING.md](AUTHORING.md) before adding or renaming node families.

## Depends On / Depended On By

- Depends on: [`../orchestration/engine/README.md`](../orchestration/engine/README.md), [`../compute/README.md`](../compute/README.md), [`../governance/README.md`](../governance/README.md), `adapters`, `kernel`, and cross-layer IR/Fabric/Foundry/Lex surfaces
- Depended on by: workflow builders and specs in [`../orchestration/workflows/README.md`](../orchestration/workflows/README.md), plus integration and node-contract tests in [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested registry check: `uv run python -c "from polisyos.scientist.nodes import discover_scientist_nodes; registry, report = discover_scientist_nodes(include_dev_scan=False); print(len(registry.list()), report.errors)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/nodes -q`

## Tests

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/nodes/builtins/test_state_builtins.py tests/unit/scientist/nodes/test_build_policy_output_bundle.py tests/unit/scientist/causal/test_causal_evaluation_node.py -q
```

Full node coverage is organized under
[`tests/unit/scientist/nodes/`](../../../../tests/unit/scientist/nodes/). Run
the broader Scientist workflow tests when a node changes state keys, workflow
routing, or decision artifact shape.

## Operability Links

- [Scientist component SLO](../../../../ops/components/scientist/slo.yaml)
- [Scientist component runbooks](../../../../ops/components/scientist/runbooks.md)
- [Scientist workflow catalog](../../../../docs/reference/scientist/workflows.md)
- [Scientist reliability scorecard](../../../../docs/reference/scientist/reliability-scorecard.md)
- [Runtime API outage runbook](../../../../docs/runbooks/runtime-api-outage.md)

## Known Shims/Deprecations

- There are no active package-local shims for `polisyos.scientist.nodes` in
  `architecture/shims.toml` as of 2026-05-06.
- Node IDs, state aliases, and output artifact names are workflow contracts.
  Deprecate them through workflow migration notes and compatibility tests
  before removal.
- The high-complexity decision-packet node is tracked in
  [`architecture/module_size_budget.toml`](../../../../architecture/module_size_budget.toml)
  with owner `team-scientist` and sunset `2026-12-31`.

## Reference Docs

- [Selected causal method consumers](../../../../docs/reference/scientist/causal-selected-consumers.md)
  describes the numerical source/result reconciliation and the separate
  evaluation-admission requirement.

- Builtin node reference: [`../../../../docs/reference/scientist/nodes.md`](../../../../docs/reference/scientist/nodes.md)
- Workflow catalog: [`../../../../docs/reference/scientist/workflows.md`](../../../../docs/reference/scientist/workflows.md)
- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Cross-package navigation: [`../orchestration/workflows/README.md`](../orchestration/workflows/README.md), [`../orchestration/engine/README.md`](../orchestration/engine/README.md), and [`../../../../tests/unit/scientist/README.md`](../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-10-10
