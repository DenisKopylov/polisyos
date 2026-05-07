# Authoring Scientist Methods

## Import Rules

- New search, discovery, and research DAG code imports canonical modules from
  `polisyos.scientist.methods.*`.
- Legacy `polisyos.scientist.search`, `polisyos.scientist.discovery`, and
  `polisyos.scientist.research_dag` imports are compatibility-only and carry a
  shim sunset of `2027-03-02`.
- Preserve public artifact schema names unless a separate schema migration is
  accepted.

## Placement

- Candidate generation, search objectives, funnels, VOI, promotion evidence,
  and strategy implementations live under [`search/`](search/).
- Graph discovery priors, portfolio runners, active disambiguation, stability,
  and discovery workers live under [`discovery/`](discovery/).
- Research DAG models, persistence, diffing, invalidation, projections, and
  replay live under [`research_dag/`](research_dag/).
- Workflow routing rules that select method-heavy builtins live under
  [`../orchestration/workflows/selection.py`](../orchestration/workflows/selection.py).

## Tests

Add canonical-path tests under `tests/unit/scientist/methods/**`. Keep
compatibility assertions for old public imports whenever a legacy import path is
changed or extended.
