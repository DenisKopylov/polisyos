# ADR-0085: PAG to Identification: CONSERVATIVE policy (identify iff identifiable in all DAGs in PAG)

## Status
Proposed

## Date
2026-02-28

## Context
Causal discovery algorithms (FCI, RFCI, BCCD) often produce a Partial Ancestral Graph
(PAG) rather than a single DAG, representing an equivalence class of DAGs consistent
with the data and background knowledge. Identification algorithms (backdoor criterion,
do-calculus) are defined on DAGs, not PAGs. The naive approach -- picking one DAG from
the equivalence class and identifying on it -- risks reporting an effect as identifiable
when it is only identifiable under a subset of compatible DAGs. This creates a false
sense of precision that undermines the governance guarantees of the pipeline.

## Decision
1. Adopt a CONSERVATIVE identification policy: a causal effect is reported as
   identifiable if and only if it is identifiable in every DAG consistent with the PAG.
2. Implement `pag_conservative_identify` in `foundry/methods/causal/` that enumerates
   the Markov equivalence class (for small PAGs, <=12 nodes) or applies Zhang's
   complete PAG identification rules (for larger PAGs) to determine universal
   identifiability.
3. When the effect is identifiable in some but not all DAGs, return a
   `PartialIdentificationResult` with bounds derived from the identifiable subset,
   clearly flagged as `PARTIALLY_IDENTIFIED`.
4. The `CausalEvaluationNode` treats `PARTIALLY_IDENTIFIED` as a soft pass: estimation
   proceeds using the tightest available bounds, but the governance report carries a
   warning.
5. Analysts may override the policy to `OPTIMISTIC` (identify if identifiable in any
   DAG) via a `ProblemFrame` flag, with mandatory justification logged in the audit
   trail.

## Consequences
### Positive
- Eliminates false-positive identification claims arising from DAG selection ambiguity.
- Partial identification bounds give policy-makers honest uncertainty ranges.
- Override mechanism preserves flexibility for exploratory analysis.
### Negative
- Equivalence class enumeration is exponential in the worst case; the 12-node
  threshold may be too conservative or too generous depending on PAG density.
- Many real-world PAGs will yield `PARTIALLY_IDENTIFIED`, which may frustrate
  analysts expecting point estimates.
- Zhang's PAG identification rules are complex to implement and test correctly.
