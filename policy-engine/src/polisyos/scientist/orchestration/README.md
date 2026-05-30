# Scientist Orchestration (`polisyos.scientist.orchestration`)

## Purpose

`polisyos.scientist.orchestration` is the canonical home for workflow runtime
infrastructure: DAG execution, workflow specs, LLM gateway orchestration,
reflexive memory, kernel phase guards, and presentation-oriented run outputs.

## Boundaries

- `engine/`: execution contracts, checkpoints, retries, locks, metrics, and runner backends.
- `workflows/`: built-in workflow specs and workflow runner selection.
- `llm/`: gateway clients, budget enforcement, prompt cache, provider profiles, and LLM-cycle planning.
- `memory/`: reflexive memory retrieval, balanced success/failure/opportunity
  memory schema, TTL/decay controls, contamination checks, scope revocation,
  conservative-bias metrics, consolidation, and lesson applicability.
- `kernel/`: phase FSM, compute budgets, and human gate contracts.
- `orchestrator/`: decision-card and publishable run summaries.

## Compatibility

Legacy imports under `polisyos.scientist.engine` and
`polisyos.scientist.workflows` were retired after reaching tiny non-compat
usage. The old `llm`, `memory`, `kernel`, and `orchestrator` first-level roots
were removed after reaching zero non-compat callers. New first-party code should
import from `polisyos.scientist.orchestration.*`.

## Last Updated

2026-05-24
