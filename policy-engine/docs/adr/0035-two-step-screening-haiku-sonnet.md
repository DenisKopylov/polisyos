# ADR-0035: Two-Step Article Screening (Haiku / Sonnet)

## Status

Proposed

Status note (2026-05-02): superseded for code ownership by Data Forge; use
`polisyos.data_forge.domains.academic.batch.article_extractor` and
`polisyos.data_forge.domains.academic.batch.prompts`.

## Date

2026-02-28

## Context

Phase 0 academic batch pipeline ingests articles from OpenAlex for causal claim
extraction into the Structured Knowledge Graph. Full extraction with a capable
LLM (Sonnet-class) is expensive, and the majority of candidate articles are
irrelevant to the policy domain under analysis.

Running detailed extraction on all articles wastes compute budget and increases
pipeline latency without proportional knowledge gain.

## Decision

1. Implement **two-step screening** in `polisyos.academic.batch.article_extractor`:

   - **Step 1 (Haiku)**: Fast relevance screening using a small, cheap model.
     Classifies each article as `relevant`, `maybe`, or `irrelevant` based on
     title, abstract, and keyword overlap with the query domain.
   - **Step 2 (Sonnet)**: Detailed causal claim extraction on articles that
     pass screening (`relevant` or `maybe`).
2. Screening prompts are maintained in `polisyos.academic.batch.prompts/` and
   versioned alongside the pipeline.
3. The `context_classifier` module assigns domain context tags during Step 1
   to enable downstream filtering.
4. Screening decisions are logged with the model ID and prompt version for
   reproducibility.

## Consequences

### Positive

- Approximately **10x cost reduction** compared to running Sonnet on all
  candidate articles.

- Faster pipeline throughput: Haiku screening is sub-second per article.
- Screening metadata enables quality analysis of false-negative rates over time.

### Negative

- Risk of **false negatives** in the screening step: relevant articles may be
  incorrectly classified as irrelevant by the cheaper model.

- Requires periodic calibration of screening prompts against golden-set
  extraction results.
