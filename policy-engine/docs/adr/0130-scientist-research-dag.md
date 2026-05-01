# ADR-0130: Scientist Research DAG Boundary

## Status

Accepted

## Date

2026-04-28

## Context

Wave 1 introduced `src/polisyos/scientist/research_dag/**` and a CAS-persisted
`ResearchDAGArtifact` so research process can be represented as a replayable
graph rather than as a raw transcript. Decision packets can now carry
`research_dag_ref` and render `research_dag_status = "legacy_missing"` for old
artifacts.

Wave 2 will add stronger replay, comparison and source-invalidation behavior.
Those features need one package boundary and one artifact evolution policy so
research explanations do not diverge between provenance, tool loops and packet
renderers.

## Decision

`src/polisyos/scientist/research_dag/**` is the canonical Scientist package for
research-path nodes, dependency/support/refutation edges, DAG persistence, DAG
replay, DAG diff and public redaction rules.

The Wave 1 `ResearchDAGArtifact` schema remains readable. Wave 2 replay and
comparison artifacts must be additive sidecars such as
`research_dag_replay_ref`, `research_dag_diff_ref`,
`research_source_invalidation_ref` and `research_dag_comparison_ref`. Decision
packets keep `research_dag_ref`, `research_dag_status` and old packet payload
fields.

Research DAG replay reconstructs the high-level research path without storing
raw LLM transcripts or instruction-bearing untrusted source text. Source text
belongs in evidence/snippet artifacts with explicit safety metadata, not in DAG
node summaries.

## Compatibility

- Old decision packets without `research_dag_ref` remain loadable and render
  `research_dag_status = "legacy_missing"`.
- Existing workflow specs, checkpoint records and provenance DAGs remain their
  own contracts; Research DAG is a sidecar projection over those surfaces.
- Public DAG exports must preserve redaction and must not expose hidden
  benchmark content or private review notes.
- New replay/diff fields must be optional until the Wave 2 closeout gate makes
  them required for selected publication paths.

## Rollout

Phase 2.0 freezes names and package boundaries only. Phase 2.2 may add replay
and comparison behavior behind
`scientist.best_in_class.wave2.phase2_2.research_dag_replay`. The production
default is off; staging may run in shadow mode after Wave 2 compatibility gates
pass.

## Rollback

Disable the Wave 2 replay flag and continue writing the Wave 1
`research_dag_ref` sidecar. Packet rendering falls back to
`research_dag_status = "legacy_missing"` when old artifacts have no DAG ref.

## Consequences

- Replay and diff code has a single home.
- Workflow/provenance traces can project into the research DAG without replacing
  engine checkpoint contracts.
- Public exports keep a bright boundary between graph summaries and untrusted
  raw evidence text.

## Concrete impact

- Phase 2.2 owns stronger replay, diff and invalidation propagation under the
  existing research DAG package.
- Decision packets can gain replay/comparison refs, but only as optional
  additive sidecars.
- CI gates must reject any Research DAG export fixture that leaks hidden eval
  refs or private data.

## Related Decisions

- [ADR-0009: DecisionPacket Replay Protocol](0009-decision-packet-replay-protocol.md)
- [ADR-0011: Scientist DAG Checkpoint/Resume](0011-scientist-checkpoint-resume.md)
- [ADR-0058: Only additive schema changes](0058-compatibility-policy-additive-changes-only.md)
- [ADR-0123: ArtifactRef Governance Metadata](0123-artifact-ref-governance.md)
