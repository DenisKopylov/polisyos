# Scientist Research DAG Replay

Related references: [Research DAG](research-dag.md), [Claim Ledger](claim-ledger.md), [Deep research evidence](deep-research-evidence.md), [Wave 2 runtime contracts](wave2-runtime-contracts.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/methods/research_dag/replay.py`, `src/polisyos/scientist/methods/research_dag/comparison.py`, `src/polisyos/scientist/methods/research_dag/invalidation.py`, `src/polisyos/scientist/methods/research_dag/diff.py`, `src/polisyos/scientist/evidence/claims/lifecycle.py`, `tests/unit/scientist/methods/research_dag/test_replay_plan.py`, `tests/unit/scientist/methods/research_dag/test_comparison.py`, `tests/unit/scientist/methods/research_dag/test_invalidation.py`, and `tools/ci/check_scientist_best_in_class_phase2_2.py`.

Research DAG replay explains and compares runs from pinned artifacts and
summarized research nodes. It does not regenerate LLM tokens, call live web, or
rebuild external pages.

## Replay Contracts

| Contract | Module | Role |
| --- | --- | --- |
| `ReplayMode` | `methods/research_dag/replay.py` | `audit_reconstruction`, `pinned_input_replay`, and `variance_envelope` modes. |
| `ResearchReplayPlan` | `methods/research_dag/replay.py` | Required CAS inputs, unsupported steps, live-fetch guard and replay status. |
| `ResearchDAGReplay` | `methods/research_dag/replay.py` | Audit-safe ordered path through question, source, extraction, synthesis, governance and publication nodes. |
| `ResearchTrajectoryComparisonReport` | `methods/research_dag/comparison.py` | Changed queries, sources, snippets, claims, governance outcomes and node ids. |
| `SourceInvalidationEvent` | `methods/research_dag/invalidation.py` | Source stale/withdrawn/contradicted/unavailable events with explicit source refs. |

## Replay Semantics

- `audit_reconstruction` rejects any plan that requires live web or provider
  fetches.
- `pinned_input_replay` uses CAS artifact refs, fingerprints, snippet ids and
  summarized untrusted content fingerprints.
- `variance_envelope` records non-deterministic LLM/web/tool nodes without
  promising deterministic token replay.
- Phase 1.2 DAGs without enough replay metadata render
  `replay_status = "legacy_minimal"`.
- Hidden benchmark/private refs and hidden-eval text tokens are removed from
  public replay and comparison exports, including node ids, producer labels and
  fallback diff signatures.

## Comparison

Research trajectory comparison reports:

```text
changed_queries
changed_sources
changed_snippets
changed_claim_ids
changed_governance_outcomes
added_node_ids
removed_node_ids
```

The comparison report is intended to answer why a decision changed without
requiring raw transcripts or live web access.

## Source Invalidation

Source invalidation starts from a concrete `source_ref` present in the Research
DAG. The propagation walks downstream nodes and returns affected node ids plus
dependent claim ids. Stale/unavailable sources create `marked_stale` Claim
Ledger lifecycle events; withdrawn or contradicted sources create `invalidated`
events. Orphaned node or claim targets fail validation.

## Safety

- Replay does not fetch live URLs.
- Public replay and comparison exports omit hidden/private artifact refs and
  redact hidden-eval producer/node/fallback text.
- Raw untrusted web/page text is not exported.
- Invalidation cannot mark claims stale without source-ref lineage in the DAG.

## Feature Flags

```text
scientist.best_in_class.wave2.phase2_2.replay_plan
scientist.best_in_class.wave2.phase2_2.source_invalidation
```

Both start as shadow/read-only controls. Phase 2.6 may later consume source
invalidation reports for review and reissue triggers.

## Validation

```bash
uv run pytest tests/unit/scientist/methods/research_dag/test_replay_plan.py tests/unit/scientist/methods/research_dag/test_comparison.py tests/unit/scientist/methods/research_dag/test_invalidation.py -q
uv run python tools/ci/check_scientist_best_in_class_phase2_2.py --repo-root . --output-format json --require-passing
```
