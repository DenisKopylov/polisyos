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
- [`components.py`](components.py) wraps builtin nodes in the existing
  `ComponentProvider` contract. Core discovery consumes its architecture-declared
  loader target, keeping source-checkout registration available when external
  entry points are disabled.
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

`simulate/propagate_uncertainty.py` can opt into an execute-backed state-slot
projection with `propagation_response_basis`. It freshly validates the
selected Foundry response candidate and calibration report/input-basis chain,
then projects only the requested persisted state slots. It carries the complete
response source identity map into the report and output-envelope lineage. The
fresh IR reader reconciles that roster and the selected CAS byte identities;
it does not recompute the Foundry matrix or verify successful draw identities.
The output and projection remain candidate-only and gate-ineligible.

The Science-owned bridge module at
[simulate/uncertainty_source_projection.py](builtins/simulate/uncertainty_source_projection.py)
exposes fixed Science-owned metric-admission and subject-projection entrypoints.
Each takes only a store, the selected SimulationResult ref, and the requested
subject; it hardwires Core's selected-profile SimulationResult validator and the
full strict Science PropagationReport 1.1 DTO validator before calling generic
IR inspection on the exact profile-bound ref. Generic IR APIs accept no source
carrier and retain source_owner_validation_not_performed. The Science bridge
reconciles only that IR-stage limitation after both validators succeed.
Uncertainty remains limited because successful-draw identities and trusted
response-basis revalidation are not established.

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
facade. Its re-export surface is assembled dynamically in
`src/polisyos/scientist/nodes/builtins/decide/decision_packet/api.py`, so this
guide does not pin an exported-name count.

The node returns the CAS writer's selected manifest profile in its
`DecisionPacketRef`. Run outputs should forward that complete reference rather
than rebuilding it from an artifact ID, so profile-bound readers can select the
same persisted view.

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

Previously recorded smoke-test command; it was not rerun for this
documentation correction:

```bash
uv run pytest tests/unit/scientist/nodes/builtins/test_state_builtins.py tests/unit/scientist/nodes/test_build_policy_output_bundle.py tests/unit/scientist/methods/causal/test_causal_evaluation_node.py -q
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

- Last updated: 2026-10-14

`compile/compile_foundry.py` consumes `params.method_metric_bindings` as a bounded
JSON array. The real engine supplies admitted arrays through journaled list
views, so the node accepts the list contract rather than the exact builtin
class. Each row still passes the strict `MethodMetricBindingRequest` DTO;
non-list inventories, boolean fields, extra fields, conflicting selections and
the existing inventory cap remain fail-closed. Selected policy/plan profiles,
method ABI, metric law and actual compiler provenance remain required. The
candidate comparison reads the exact source plan, lowering and constraint registry
and replays the complete compiler graph/order through the public Foundry facade;
method-only graph counts cannot replace the mandatory operator closure. The state-view compatibility fix grants no metric value,
completed-source selection, calibration or publication authority.

Observed ex-ante source fixtures derive their arithmetic oracle from the actual
selected pre-dispatch baseline/scenario rows, independently of producer output
and any caller-provided expected number. A positive fixture must remain inside
the existing exact-float mean profile: the rational mean 2/3 is honestly
unavailable rather than rounded into admissibility. Baseline-comparability
controls use supported explicit inputs; the captured rows and independent mean
remain checked. Constructor-forwarding tests use selected policy/typed-plan refs
and CompileRequest1.2; a mock forwarding result is not real compiler or Runtime
completion evidence. These test repairs do not widen production admission.

### Response projection JSON params

`simulate/propagate_uncertainty.py` reads `propagation_response_basis` from the
JSON-compatible `ExperimentState.params` plane. The existing strict projection DTO
is validated through Pydantic's public strict JSON method, so a JSON array becomes
its declared internal tuple without number-to-text coercion or manual field casts.
Literal version, extra-field, required/nonempty/unique ID and StrictStr constraints
remain the same. An absent projection remains optional; an invalid supplied one
returns a typed response-basis failure before a simulation skip or artifact I/O.

This validates syntax only. Nonempty text IDs, including numeric text, still need
the existing selected execute-response source and slot mapping; no source/issuer,
causal law or publication authority is inferred. The real scalar response test
supplies that later path. A phase0 admission fix does not establish that the later
source intake, join or MC consumer has succeeded until its actual execution.

### State-slot envelope publication

The response projection marker returns an `UncertaintyEnvelope` already; the
public uncertainty node persists that value directly through the existing envelope
writer. `PropagationResult` owns the initial `.envelope` projection, while the
marked envelope has no second wrapper. The fresh subject reader must retain its
state-slot subject, exact selected calibration/source refs and candidate-only,
non-gating status. This repair changes neither propagation arithmetic nor source
qualification; later report/consumer outcomes still need actual verification.
