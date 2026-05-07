# Scientist Methods (`polisyos.scientist.methods`)

## Purpose

`polisyos.scientist.methods` is the canonical home for Scientist method lanes:
policy search, graph discovery, research DAG projection/replay, and adjacent
domain method families such as causal, DOE, autotune, and backtesting. Workflow
selection now lives with the workflow runtime under
`polisyos.scientist.orchestration.workflows`.

## Where to Start

- Search and promotion methods: [`search/README.md`](search/README.md)
- Graph discovery methods: [`discovery/README.md`](discovery/README.md)
- Research DAG methods: [`research_dag/README.md`](research_dag/README.md)
- Causal method runners: [`causal/README.md`](causal/README.md)
- DOE and sensitivity methods: [`doe/README.md`](doe/README.md)
- Autotune/search-loop methods: [`autotune/`](autotune/)
- Backtesting and challenge suites: [`backtesting/README.md`](backtesting/README.md)
- Advanced C7 method bundles: [`advanced.py`](advanced.py)
- Workflow selection:
  [`../orchestration/workflows/selection.py`](../orchestration/workflows/selection.py)

## Compatibility

The legacy packages `polisyos.scientist.search`,
`polisyos.scientist.discovery`, `polisyos.scientist.research_dag`,
`polisyos.scientist.causal`, `polisyos.scientist.doe`,
`polisyos.scientist.autotune`, `polisyos.scientist.backtesting`, and
`polisyos.scientist.compute.advanced_methods` remain time-boxed shims. New
first-party code should import from `polisyos.scientist.methods.*`.

## Common Commands

Run from `policy-engine/`.

```bash
uv run python -c "from polisyos.scientist.methods.search import CompositeObjective; from polisyos.scientist.methods.discovery import GraphHypothesis; print(CompositeObjective.__name__, GraphHypothesis.__name__)"
uv run pytest tests/unit/scientist/methods -q
```

## Last Updated

2026-05-05
