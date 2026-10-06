# Search Methods (`polisyos.scientist.methods.search`)

## Purpose

`polisyos.scientist.methods.search` implements the iterative policy-optimization layer
for Scientist: candidate generation, staged evaluation, readiness and promotion
gating, lesson and benchmark registries, and optional funnel/strategy/frontier
logic used by policy-design and promotion workflows.

## Where to Start

- Root facade and lazy exports: [`__init__.py`](__init__.py)
- Legacy ask/evaluate controller: [`controller.py`](controller.py)
- Native internal service bridge: [`service.py`](service.py)
- Root contracts and evaluation primitives: [`contracts.py`](contracts.py), [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py)
- Promotion funnel and rollout logic: [`funnel/`](funnel/), [`readiness.py`](readiness.py), and [`promotion_evidence.py`](promotion_evidence.py)
- Strategy implementations: [`strategies/`](strategies/)

## Internal Entrypoints

This child package and `polisyos.scientist.methods.autotune` are internal under
the [public-surface manifest](../../../../../architecture/public_surface/contract.toml).
Their `__all__` exports support internal callers and do not make the child
packages public. The public `polisyos.scientist` facade exposes three specific
search aliases: `NativeSearchService`, `SearchServiceCheckpoint`, and
`SearchLoopRunner`. Those aliases do not change the classification of the
remaining child entrypoints below.

- Root contract surface in [`contracts.py`](contracts.py): `SearchService`, `CandidateProposal`, `EvaluationBundle`, and `TellResult`
- Legacy controller in [`controller.py`](controller.py): `SearchController`, `SearchConfig`, `SearchResult`, and `SearchIteration`
- Evaluation primitives in [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py): `CompositeObjective`, `CheapStage`, `ExpensiveStage`, and `StoppingPresets`
- Registry and lesson surfaces in [`benchmark_registry.py`](benchmark_registry.py), [`lessons.py`](lessons.py), [`pareto_registry.py`](pareto_registry.py), and [`registry_contracts.py`](registry_contracts.py)
- Rollout helpers in [`adversarial.py`](adversarial.py), [`latent_governance.py`](latent_governance.py), [`promotion_evidence.py`](promotion_evidence.py), and [`compliance_audit.py`](compliance_audit.py)
- Search strategies in [`strategies/`](strategies/): random, grid, Bayesian, multi-objective, neural, and arbitration helpers

## Pareto Assessment Projection (B111)

The registry's typed `view_assessments` supplies assessment status for each
projection; `eligible_candidate_hashes` identifies that projection's
assessment denominator. The v3 `PolicyFrontierReport` DTO validator compares
the supplied source-feasible set with the global projection's eligible
identities, checks for duplicates within each supplied set and overlap
between the source-feasible and unknown sets, and requires the projection
assessment status to be `denominator_limited` exactly when the source-feasible
set differs from
projected eligible identities or the supplied unknown set is nonempty. It
does not check unknown identities for projection membership or independently
reconcile them against the projection. However, the ordinary
`PolicyArtifactBuilder._build_frontier_report` path sets the report's source
identities from the same projection and leaves
the unknown set empty. That self-derived equality is not an independent source
observation: it cannot detect a candidate omitted before registry projection
or establish upstream population completeness. The independent producer input
and bridge are not established. A missing registry remains basis-limited and
unranked. See the [policy-design package README](../../policy_design/README.md#persisted-frontier-artifacts)
for artifact versions and rollout limits.

## Plateau and Stress Evidence

`ImprovementPlateau` profile `1.0` requires an explicit `objective_unit`.
Its default absolute tolerance is 0.01 of those units and its relative
tolerance (`min_improvement`) is 0.01. It stops when direction-normalized
gain is at most the larger tolerance, including equality and deterioration.
Missing units/profile or missing, invalid, and nonfinite observations cannot
establish a plateau. `StoppingPresets.default` accepts the unit and direction;
without a unit its iteration and wall-time limits still operate. Convert the
absolute tolerance when converting objective units. This profile is an
engineering tolerance, not statistical significance.
Version `1.0` identifies the formula; custom coefficients are recorded in
the stopping details and do not assert equivalence to the default coefficient
pair. `patience` must be an integer of at least one; booleans are rejected.

`run_stress_test` reports `(finite_evaluated - violated_scenarios) /
finite_evaluated` over observed finite scenarios. A repeated issue still
counts once for each violated scenario; grouping and `collect_top_k` select
examples only. Metadata distinguishes `attempted`, `finite_evaluated`,
`violated_scenarios`, `unknown_or_nonfinite`, `planned_scenarios`, and
`completeness`. `total_scenarios_evaluated` counts finite admitted outcomes.
A zero finite denominator leaves the score unavailable; an incomplete or
unknown stream has partial adequacy and a conditional score when available.
Even a complete planned stream supplies an observed sample fraction, not a
population failure probability or calibrated model uncertainty.

Retained full vulnerability payloads are bounded by `collect_top_k` plus
one transient object. Digest identities still require O(unique issues)
memory; initial sampling and adaptive history are outside that payload bound.
Typed objective direction, the physical worst case, and these metadata survive
the existing CAS report serialization without a shared DTO schema change.

## Depends On / Depended On By

- Depends on: [`../../governance/README.md`](../../governance/README.md), `doe`, policy-design/search-specific runtime helpers, and artifact persistence surfaces
- Depended on by: policy-design workflows, builtin planning/decision nodes, frontier rollout gates, and benchmark/promotion flows described in [`../../orchestration/workflows/README.md`](../../orchestration/workflows/README.md) and [`../../nodes/README.md`](../../nodes/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.methods.search import CompositeObjective, StoppingPresets; from polisyos.scientist.methods.search.controller import SearchConfig, SearchController; print(CompositeObjective.__name__, SearchConfig.__name__, SearchController.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/unit/scientist/methods tests/unit/scientist/search -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/unit/scientist/search/test_controller_api.py tests/unit/scientist/search/test_search_loop.py tests/unit/scientist/search/test_benchmark_registry.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../../docs/reference/scientist/index.md`](../../../../../docs/reference/scientist/index.md)
- Agent/search reasoning reference: [`../../../../../docs/reference/scientist/agent-search-reasoning.md`](../../../../../docs/reference/scientist/agent-search-reasoning.md)
- Frontier rollout contract: [`../../../../../docs/reference/scientist/frontier-runtime.md`](../../../../../docs/reference/scientist/frontier-runtime.md)
- Reliability gate context: [`../../../../../docs/reference/scientist/reliability-scorecard.md`](../../../../../docs/reference/scientist/reliability-scorecard.md)
- Cross-package navigation: [`../../orchestration/workflows/README.md`](../../orchestration/workflows/README.md), [`../../governance/README.md`](../../governance/README.md), and [`../../../../../tests/unit/scientist/README.md`](../../../../../tests/unit/scientist/README.md)

## Last Updated

- Last updated: 2026-05-05
