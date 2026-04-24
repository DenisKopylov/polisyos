# ADR-0032: LLM as Context Interpreter, Not Structural Source

## Status

Proposed

## Date

2026-02-28

## Context

Phase 9 introduces LLM-assisted causal graph construction. Large language models
can suggest plausible causal edges based on their training corpus, but their
confidence estimates are not calibrated against empirical evidence. Over-reliance
on LLM-suggested structure risks embedding hallucinated causal claims into policy
analyses, violating the evidentiary standards required by governance (Law L).

The Structured Knowledge Graph (SKG) provides empirically grounded causal priors
extracted from peer-reviewed literature with explicit confidence and provenance.

## Decision

1. LLMs serve as **context interpreters**: they help classify study contexts,
   resolve variable semantics, and suggest candidate edges for human review.
2. LLMs do **not** serve as structural sources: edges suggested solely by an LLM
   without SKG or empirical backing receive `unsupported_by_evidence=True`.
3. LLM-only edges receive a **confidence ceiling of 0.3**, regardless of the
   model's self-reported certainty.
4. Primary causal structure must originate from one of:

   - SKG literature priors,
   - Data-driven discovery (PCMCI, constraint-based methods),
   - Expert-specified domain knowledge with audit trail.
5. The `CausalEdge.source` field must distinguish `llm_suggested` from
   `skg_prior`, `data_driven`, and `expert_specified`.

## Consequences

### Positive

- Prevents false confidence from LLM hallucinations propagating into policy
  recommendations.

- Maintains clear provenance for every edge in the causal graph.
- Compatible with governance Law L enforcement in STRICT profile.

### Negative

- Limits LLM utility in data-sparse domains where SKG coverage is thin.
- Requires human review workflow for promoting LLM-suggested edges to
  supported status.
