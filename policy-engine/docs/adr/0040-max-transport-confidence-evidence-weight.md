# ADR-0040: Parameter Selection by Max Transport Confidence x Evidence Weight

## Status
Proposed

## Date
2026-02-28

## Context
Phase 15 parameter resolution must select the best available causal effect
parameter for a given policy question and target context. When multiple studies
have estimated the same causal effect, each with different transport confidence
(how well it generalizes to the target context) and evidence weight (study
quality, sample size, methodology rigor), a principled selection criterion is
needed.

Ad-hoc selection (e.g., most recent study, largest sample) ignores either
transportability or evidence quality, leading to suboptimal parameter choices.

## Decision
1. Select the parameter that maximizes **`transport_confidence x evidence_weight`**
   where both factors are in [0.0, 1.0].
2. Parameters with **`transport_confidence < 0.3`** are excluded from
   consideration entirely, regardless of evidence weight (consistent with
   ADR-0038 Law T).
3. `evidence_weight` is derived from study metadata: sample size, methodology
   tier, publication quality, and refutation survival (ADR-0028).
4. When multiple parameters have identical selection scores, prefer the one
   with the **narrower confidence interval** (lower uncertainty).
5. The selection rationale (scores, excluded parameters, tie-breaking) is
   recorded in the `ContextAdaptiveParameterBundle` artifact for audit.

## Consequences
### Positive
- Principled parameter selection that jointly optimizes for contextual
  relevance and evidence quality.
- Uncertainty propagation: low-confidence transport or weak evidence
  naturally down-weights parameters.
- Full audit trail of selection decisions supports governance review.

### Negative
- May exclude valid but poorly-transported parameters, reducing available
  evidence in data-sparse target contexts.
- The multiplicative scoring assumes independence between transport
  confidence and evidence weight, which may not always hold.
