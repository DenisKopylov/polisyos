# ADR-0094: Confidence as Ordinal Quality Score

## Status
Proposed

## Date
2026-02-28

## Context
The system pervasively uses "confidence" values in [0, 1] -- attached to literature
priors, proxy validations, transportability assessments, and governance checks.
Without a shared definition, different subsystems interpret these values
inconsistently: some treat them as calibrated probabilities, others as subjective
quality ratings. This inconsistency corrupts composition and aggregation operations.
This cross-cutting ADR establishes a single semantic definition and specifies the
two canonical operations for combining confidence values.

## Decision
1. Define "confidence" throughout PolicyOS as an **ordinal quality score** on [0, 1],
   where 0 means "no evidence / completely unreliable" and 1 means "highest
   achievable quality for this evidence type". It is explicitly **not** a calibrated
   probability and must not be used in Bayesian updating as a likelihood.
2. **Serial composition** (chained dependencies, e.g., proxy chains): use the
   harmonic mean, as specified in ADR-0092. This penalises the weakest link.
3. **Parallel aggregation** (independent evidence for the same claim): use
   Noisy-OR: combined = 1 - product(1 - c_i). This yields a score that increases
   with each additional independent piece of evidence but never exceeds 1.
4. All IR models carrying a confidence field must include a `confidence_basis: str`
   annotation describing the evidence type (e.g., "meta_analysis", "proxy_chain",
   "expert_elicitation") to support auditability.
5. Subsystem-specific calibration (e.g., LLM ceiling in ADR-0087) is applied
   **before** the value enters the composition pipeline.

## Consequences
### Positive
- Eliminates ambiguity in what "confidence = 0.7" means across the entire system.
- Harmonic-mean and Noisy-OR are closed on [0, 1], preventing out-of-range results.
- The `confidence_basis` annotation enables downstream consumers to weight or
  filter by evidence type.
### Negative
- Ordinal scores cannot be directly compared across evidence types without
  normalisation conventions, which this ADR does not fully specify.
- Noisy-OR assumes independence; correlated evidence sources will produce
  inflated aggregated scores.
- Retrofitting existing models with `confidence_basis` requires a migration across
  multiple IR schemas.
