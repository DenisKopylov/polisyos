# ADR-0087: LLM Prior Calibration Ceiling

## Status
Proposed

## Date
2026-02-28

## Context
The literature prior pipeline uses LLM-extracted effect sizes and directions as
Bayesian priors for causal estimation. However, LLM outputs are derived from the same
published corpus that human reviewers consult, meaning they are not an independent
source of evidence. Treating LLM priors with high confidence leads to over-confident
posteriors and double-counting when combined with human-curated literature reviews.
Phase 9 formalises calibration limits for LLM-sourced priors.

## Decision
1. Cap the maximum confidence weight of any single LLM-extracted prior at 0.3
   (on the [0, 1] ordinal quality scale defined in ADR-0094).
2. When an LLM prior overlaps with a human-curated literature finding on the same
   treatment-outcome pair, apply an overlap discount of 0.05 to the LLM prior's
   weight before composition, reflecting shared information content.
3. Document in the `LiteratureCausalPrior` IR model that the LLM is not an
   independent evidence source; the `source_type` field must be set to
   `"llm_extracted"` to distinguish it from `"expert_elicited"` or `"meta_analysis"`.
4. The `literature_prior` foundry method enforces the ceiling at construction time;
   any upstream value exceeding 0.3 is clamped and a warning is logged.

## Consequences
### Positive
- Prevents inflated posterior confidence from non-independent LLM evidence.
- Makes the epistemic status of LLM priors explicit and auditable.
- The overlap discount mitigates double-counting with human reviews.
### Negative
- The 0.3 ceiling is a conservative heuristic; well-calibrated LLM extractions
  from high-quality meta-analyses may be unfairly down-weighted.
- The fixed discount of 0.05 does not account for varying degrees of overlap
  between LLM and human sources.
- Requires all downstream consumers to check `source_type`, adding coupling.
