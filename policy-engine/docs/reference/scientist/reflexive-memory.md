# Scientist Reflexive Memory

Related references: [Scientist](index.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md), [VOI scheduler](voi-scheduler.md), [Research DAG replay](research-dag-replay.md), [Benchmark authority](benchmark-authority.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/orchestration/memory/**`, `src/polisyos/scientist/methods/search/failure_cards.py`, `src/polisyos/scientist/methods/search/lessons.py`, `src/polisyos/scientist/methods/research_dag/projections.py`, `src/polisyos/scientist/evals/leakage.py`, `tests/unit/scientist/memory/**`, and `tools/ci/check_scientist_best_in_class_phase2_4.py`.

Phase 2.4 makes failure intelligence reusable without making it silent
evidence. Reflexive memory wraps the existing failure-card and lesson-card
registry. Retrieved lessons are warnings/anti-patterns, not claim support, and
memory influence must be visible in the Research DAG.

## Runtime Contract

| Contract | Owner | Purpose |
| --- | --- | --- |
| `MemoryVisibility` | `memory.failure_lessons` | Defines local-run, tenant, domain and global-public visibility. |
| `LessonApplicability` | `memory.failure_lessons` | Records whether a lesson applies, why it applies or does not apply, scope and expiry. |
| `ReflexiveMemoryEvent` | `memory.failure_lessons` | Audits retrieved, applied, rejected and revoked lesson actions. |
| `MemoryApplicabilityContext` | `memory.applicability` | Target-run context: run id, tenant, domain, workflow, method family and time. |
| `MemoryContaminationPolicy` | `memory.contamination` | Blocks hidden benchmark refs, hidden suite ids and canary tokens from reusable memory. |
| `MemoryRetrievalResult` | `memory.retrieval` | Returns retrieved warning-only lessons, rejected lessons and memory events. |
| `ConsolidatedLessonSet` | `memory.consolidation` | Deduplicates lessons while preserving source lesson ids. |
| `ReflexionRecoveryEvalReport` | `memory.failure_lessons` | Measures held-out recovery delta before default influence is allowed. |
| `format_warning_only_memory_context` | `memory.retrieval` | Renders retrieved memory for prompting as warnings, not evidence, and rejects revoked influence. |
| `build_reflexion_memory_recovery_eval_report` | `memory.failure_lessons` | Converts existing Reflexion replay/eval outputs into the Phase 2.4 recovery report. |

## Reuse Rules

- Hidden eval and hidden benchmark content never enters reusable memory.
- Hidden holdout ids, hidden suite ids, hidden benchmark metadata keys and
  canary tokens are hard blockers.
- Lessons carry scope: `tenant_hash`, `domain`, `workflow_id`,
  `method_family`, `visibility` and optional `expires_at`.
- Expired, out-of-scope or revoked lessons are returned as non-applicable with
  reasons.
- Failure lessons can be retrieved only as warnings/anti-patterns.
- Reusable memory is not evidence for public claims and cannot advance claim
  readiness by itself.
- A retrieved or applied memory event must be represented in the Research DAG
  with `memory_influence_visible = true`.

## Contamination Posture

The hidden eval rule is fail-closed: reusable memory may describe that a hidden
or private evaluation failed, but it may not store hidden eval answers,
identifiers, canaries or suite internals.

`memory.contamination.detect_memory_contamination(...)` reuses the benchmark
leakage checks from `scientist.evals.leakage` and adds canary/key scanning for
reusable memory. The block list includes `hidden_benchmark`, `hidden_eval`,
`hidden_holdout`, `private_eval`, `hidden_suite`, `sentinel_answer` and
`canary` metadata keys.

When a payload fails the contamination check, `assert_reusable_memory_clean(...)`
raises before the lesson is recorded or retrieved as applicable. Retrieval
still emits a rejected `ReflexiveMemoryEvent` so the failed attempt remains
auditable.

## Applicability

Applicability is deterministic and reasoned:

- `LOCAL_RUN` requires the lesson source run to match the target run.
- `TENANT` requires a matching tenant hash.
- `DOMAIN` requires a matching domain.
- `GLOBAL_PUBLIC` is allowed only after contamination checks and optional
  workflow/method constraints still apply.
- `workflow_id` and `method_family` are explicit filters when present.
- `expires_at` turns an otherwise matching lesson into non-applicable after
  expiry.

Every applicability result must include reasons. A memory retrieval without
reasons fails validation.

## Reflexion Recovery Evals

Phase 2.4 does not call an LLM to measure recovery. It consumes existing
offline Reflexion replay/eval outputs, including `ReflexionReplayEvaluation`
from `agent.reflexion_evaluator` and benchmark-style metric dictionaries with
`reflexion_recovery_rate` or `retry_success_rate`. The helper
`build_reflexion_memory_recovery_eval_report(...)` compares the baseline and
memory-assisted recovery rates and records the held-out scenario count.

Default memory influence remains blocked unless the measured memory-assisted
rate improves on held-out failure scenarios and contamination checks remain
green.

## Research DAG Projection

`project_reflexive_memory_events_to_research_dag(...)` creates critique nodes
for memory events. The node metadata stores event id, lesson id, action,
applicability reasons, sanitized scope, `memory_influence_visible = true` and
`influence_mode = "warning_anti_pattern"`.

`validate_memory_influence_dag_attribution(...)` reports
`memory_influence_missing_dag_node:<event_id>` when retrieved/applied memory
events are not represented in the DAG.

## Rollout

```text
scientist.best_in_class.wave2.phase2_4.reflexive_memory
scientist.best_in_class.wave2.phase2_4.memory_influence_shadow
scientist.best_in_class.wave2.phase2_4.memory_influence_default
```

Start read-only: retrieve lessons and render warnings without changing
decisions. Advisory influence may be enabled only after held-out failure
recovery improves and contamination tests remain green. High-risk workflows
remain non-default until Wave 2 closeout accepts memory influence rules.

## Validation

```bash
uv run pytest tests/unit/scientist/memory tests/repo_quality/tools/test_scientist_best_in_class_phase2_4.py -q
uv run python tools/ci/check_scientist_best_in_class_phase2_4.py --repo-root . --output-format json --require-passing
```
