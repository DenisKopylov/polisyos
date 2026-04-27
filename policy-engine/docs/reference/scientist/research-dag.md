# Scientist Research DAG

Related references: [Scientist](index.md), [Claims](claims.md), [Workflows](workflows.md), [Best-in-class readiness](best-in-class-readiness.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/research_dag/**`, `src/polisyos/scientist/engine/executor.py`, `src/polisyos/scientist/provenance/run_dag.py`, `src/polisyos/scientist/agent/tools/tool_loop.py`, `tests/scientist/research_dag/**`, and `tools/ci/check_scientist_best_in_class_phase1_2.py`

The Research DAG is the Phase 1.2 sidecar that turns a Scientist research run
into a typed, replayable graph. It is not a raw LLM transcript. It records the
high-level path from question, plan, source acquisition, source read,
extraction, verification, synthesis, critique, governance and publication.

## Contract

`ResearchDAGArtifact` is CAS-persisted with `kind="scientist.research_dag"` and
is linked from runtime state as `research_dag_ref`.

Core types:

- `ResearchDAGNode`: typed research action with producer, summary,
  artifact refs, claim ids, fingerprints, safety labels and redacted metadata.
- `ResearchDAGEdge`: typed dependency/support/refutation/gating edge.
- `ResearchDAGArtifact`: run/workflow envelope with optional `claim_ledger_ref`
  and `hidden_content_redacted=true`.

The initial sidecar is additive. Existing runs without `research_dag_ref` remain
loadable and render `research_dag_status = "legacy_missing"`.

## Integrations

Phase 1.2 integrates the sidecar through:

- workflow finalization in `engine/executor.py`;
- selected workflow dispatch in `workflows/builder.py`;
- trace attributes in `engine/trace_attributes.py`;
- checkpoint metadata compatibility in `engine/checkpoint.py`;
- provenance projection in `provenance/run_dag.py`;
- tool-loop projection adapter in `agent/tools/tool_loop.py`;
- planning and decide hot paths through policy request planning, policy output
  bundles and decision packets.

When the feature flag
`scientist.best_in_class.wave1.phase1_2.research_dag` is enabled,
`scientist_policy_design`, `scientist_policy_verified` and
`scientist_causal_full` can persist a minimal `research_dag_ref`.

## Replay And Diff

DAG replay reconstructs the high-level research path with public-safe fields:
node type, producer, summary, artifact ids, claim ids and safety labels. It does
not include raw transcript text or raw untrusted tool output.

DAG diff compares:

- changed sources;
- changed claim ids;
- changed governance or publication outcomes;
- added and removed nodes.

This is the Phase 1.2 minimum. Wave 2 expands invalidation and comparison depth.

## Untrusted Text

Raw untrusted web/page text is never stored as instruction-bearing context in
the Research DAG. Tool and source projections store:

- content fingerprint;
- content character count;
- redaction flag;
- safety labels such as `untrusted_tool_output`,
  `raw_content_redacted` and `prompt_injection_candidate`.

Hidden benchmark, private eval, hidden eval and raw transcript metadata are
removed from the public DAG path. Hidden benchmark/private eval artifact refs
are also excluded from builder output and rejected by the model validator if
they reach a public artifact.

The artifact validator enforces unique node ids, matching run/workflow ids,
non-orphaned edges and acyclic edges. This keeps the sidecar replayable as a
DAG rather than a loose event log.

## Feature Flags

| Flag | Default | Role |
| --- | --- | --- |
| `scientist.best_in_class.wave1.phase1_2.research_dag` | off | Persist Research DAG sidecar for selected workflows. |
| `scientist.best_in_class.wave1.phase1_2.require_research_dag_for_publication` | off | Fail decision packet publication when `research_dag_ref` is missing. |

Production starts with sidecar off. Staging can enable shadow sidecar writes.
The publication requirement remains opt-in until Wave 1 closeout.

## Validation

```bash
uv run pytest tests/scientist/research_dag -q
uv run python tools/ci/check_scientist_best_in_class_phase1_2.py --repo-root . --output-format json --require-passing
uv run pytest tests/tools/test_scientist_best_in_class_phase1_2.py -q
```
