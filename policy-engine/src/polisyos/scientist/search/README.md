# Search (`polisyos.scientist.search`)

## Purpose

`polisyos.scientist.search` implements the iterative policy-optimization layer
for Scientist: candidate generation, staged evaluation, readiness and promotion
gating, lesson and benchmark registries, and optional funnel/strategy/frontier
logic used by policy-design and promotion workflows.

## Where to Start

- Root facade and lazy exports: [`__init__.py`](__init__.py)
- Legacy ask/evaluate controller: [`controller.py`](controller.py)
- Root contracts and evaluation primitives: [`contracts.py`](contracts.py), [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py)
- Promotion funnel and rollout logic: [`funnel/`](funnel/), [`readiness.py`](readiness.py), and [`promotion_evidence.py`](promotion_evidence.py)
- Strategy implementations: [`strategies/`](strategies/)

## Public Entrypoints

- Root contract surface in [`contracts.py`](contracts.py): `SearchService`, `CandidateProposal`, `EvaluationBundle`, and `TellResult`
- Legacy controller in [`controller.py`](controller.py): `SearchController`, `SearchConfig`, `SearchResult`, and `SearchIteration`
- Evaluation primitives in [`objective.py`](objective.py), [`stages.py`](stages.py), and [`stopping.py`](stopping.py): `CompositeObjective`, `CheapStage`, `ExpensiveStage`, and `StoppingPresets`
- Registry and lesson surfaces in [`benchmark_registry.py`](benchmark_registry.py), [`lessons.py`](lessons.py), [`pareto_registry.py`](pareto_registry.py), and [`registry_contracts.py`](registry_contracts.py)
- Rollout helpers in [`adversarial.py`](adversarial.py), [`latent_governance.py`](latent_governance.py), [`promotion_evidence.py`](promotion_evidence.py), and [`compliance_audit.py`](compliance_audit.py)
- Search strategies in [`strategies/`](strategies/): random, grid, Bayesian, multi-objective, neural, and arbitration helpers

## Depends On / Depended On By

- Depends on: [`../governance/README.md`](../governance/README.md), `doe`, policy-design/search-specific runtime helpers, and artifact persistence surfaces
- Depended on by: policy-design workflows, builtin planning/decision nodes, frontier rollout gates, and benchmark/promotion flows described in [`../workflows/README.md`](../workflows/README.md) and [`../nodes/README.md`](../nodes/README.md)

## Common Commands

Run from the repository root (`policy-engine/`).

- Smoke-tested import check: `uv run python -c "from polisyos.scientist.search import CompositeObjective, StoppingPresets; from polisyos.scientist.search.controller import SearchConfig, SearchController; print(CompositeObjective.__name__, SearchConfig.__name__, SearchController.__name__)"`
- Conceptual full-slice test run: `uv run pytest tests/scientist/search -q`

## Test / Verification Commands

Smoke-tested:

```bash
uv run pytest tests/scientist/search/test_controller_api.py tests/scientist/search/test_search_loop.py tests/scientist/search/test_benchmark_registry.py -q
```

## Reference Docs

- Scientist reference index: [`../../../../docs/reference/scientist/index.md`](../../../../docs/reference/scientist/index.md)
- Agent/search reasoning reference: [`../../../../docs/reference/scientist/agent-search-reasoning.md`](../../../../docs/reference/scientist/agent-search-reasoning.md)
- Frontier rollout contract: [`../../../../docs/reference/scientist/frontier-runtime.md`](../../../../docs/reference/scientist/frontier-runtime.md)
- Reliability gate context: [`../../../../docs/reference/scientist/reliability-scorecard.md`](../../../../docs/reference/scientist/reliability-scorecard.md)
- Cross-package navigation: [`../workflows/README.md`](../workflows/README.md), [`../governance/README.md`](../governance/README.md), and [`../../../../tests/scientist/README.md`](../../../../tests/scientist/README.md)

## Last Updated

- Last updated: 2026-04-17
