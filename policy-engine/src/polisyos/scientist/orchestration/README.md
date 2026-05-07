# Scientist Orchestration (`polisyos.scientist.orchestration`)

## Purpose

`polisyos.scientist.orchestration` is the canonical home for workflow runtime
infrastructure: DAG execution, workflow specs, LLM gateway orchestration,
reflexive memory, kernel phase guards, and presentation-oriented run outputs.

## Boundaries

- `engine/`: execution contracts, checkpoints, retries, locks, metrics, and runner backends.
- `workflows/`: built-in workflow specs and workflow runner selection.
- `llm/`: gateway clients, budget enforcement, prompt cache, provider profiles, and LLM-cycle planning.
- `memory/`: reflexive memory retrieval, contamination checks, consolidation, and lesson applicability.
- `kernel/`: phase FSM, compute budgets, and human gate contracts.
- `orchestrator/`: decision-card and publishable run summaries.

## Compatibility

Legacy imports under `polisyos.scientist.engine`, `polisyos.scientist.workflows`,
`polisyos.scientist.llm`, `polisyos.scientist.memory`,
`polisyos.scientist.kernel`, and `polisyos.scientist.orchestrator` are
time-boxed shims. New first-party code should import from
`polisyos.scientist.orchestration.*`.

## Last Updated

2026-05-05
