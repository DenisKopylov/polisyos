# ADR-0152: Semantic Binding, Lineage, And Claim Evidence

## Status

Accepted

## Date

2026-05-14

## Context

Production diagnostics found a deeper domain problem behind the authority
substrate: a policy intent can lose meaning while moving through Lex, Fabric,
Foundry, Scientist, and final artifact compilation. A Ukraine/MSME intent can
arrive at Lex with no applicable norms, Fabric with manifest roles instead of
domain-relevant source families, Foundry with generic execution methods, and
final claims with no data, method, or norm refs.

An honest authority substrate can prove that evidence was runtime-owned, but it
does not by itself prove that the evidence is semantically relevant. PolicyOS
therefore needs an accepted design rule for how policy intent becomes legal
queries, data/source bindings, method selections, and claim support.

## Decision

1. Every serious run must produce a semantic binding ledger or typed semantic
   blocker.
2. The semantic binding ledger records policy intent ref, canonical concepts,
   jurisdiction, as-of time, policy domain, population, intervention, outcomes,
   time horizon, legal query refs, dataset query refs, method expectation refs,
   and claim binding refs.
3. Lex must emit candidate norm refs, selected norm refs, rejected norm refs,
   legal snapshot refs, jurisdiction/time filters, and no-norm-vs-retrieval
   error blockers.
4. Fabric must emit candidate dataset/source refs, selected dataset/source refs,
   rejected dataset/source refs, metric bindings, column bindings, unit
   bindings, geography bindings, time coverage, freshness, and data-gap
   blockers.
5. Foundry must emit selected method refs, rejected method refs, scenario method
   expectation refs, assumptions, input coverage, power/sample adequacy,
   sensitivity, uncertainty, and method-incompatibility blockers.
6. Scientist and final decision artifacts must bind every major claim,
   recommendation, legal assertion, budget/feasibility statement,
   distributional-impact statement, implementation-risk statement, monitoring
   statement, and residual-uncertainty statement to data refs, method refs,
   norm refs, uncertainty refs, or typed blockers.
7. A domain-specific intent cannot silently collapse into generic metrics,
   generic datasets, generic methods, or a no-law/no-data conclusion. Such a
   collapse is a serious semantic blocker.
8. Lineage and claim evidence are connected. A claim that uses derived data
   must be traceable to source dataset facets, transformations, feature
   derivations, validation results, method inputs, and interpretation limits.
9. Scorecard and readiness must treat semantic relevance as separate from data
   presence. A present dataset, present legal report, or present method report
   does not satisfy a claim unless the semantic binding ledger connects it to
   the claim.

## Consequences

Positive:

- Lex/Fabric/Foundry fixes become measurable by claim support, not only by
  emitted refs.
- The system can distinguish "no relevant law/data exists" from "retrieval or
  binding failed".
- Final policy artifacts become compiler-grade: each major claim is supported,
  blocked, or explicitly out of scope.
- Cross-domain runs can expose semantic collapse instead of producing generic
  evidence.

Negative:

- Every serious run must carry more domain-binding metadata.
- Some broad or vague user intents will block until canonical concepts,
  jurisdiction, time, and claim scope are clarified or inferred with evidence.
- Fabric and Foundry need stronger rejected-candidate evidence, not only final
  selections.

## Concrete impact

This ADR does not define an implementation plan. It requires future
implementation work to introduce or update:

- semantic binding ledger schema;
- legal query/norm selection/rejection evidence;
- dataset/source/metric/column/unit/geography binding evidence;
- method expectation, selection, rejection, and assumption evidence;
- claim-to-data/method/norm/uncertainty/blocker refs;
- scorecard/readiness checks for semantic relevance;
- negative tests for no-norm false pass, generic metric collapse, manifest-role
  source selection, generic method selection, unsupported final claim, and
  data-present-but-irrelevant pass.

## Related Decisions

- Extends: ADR-0015 KnowledgeBundle Freshness Protocol.
- Extends: ADR-0021 Connector Schema Contracts And Storage Port.
- Extends: ADR-0043 SKG Versioning and Retraction Handling.
- Extends: ADR-0123 ArtifactRef Governance Metadata.
- Extends: ADR-043 Provenance Law Through QuantityValue.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0148 Serious Run State Machine And Phase Barriers.
- Related: ADR-0150 Scorecard, Readiness, Approval, And Projection Boundaries.
- Related: ADR-0151 Evidence Schema Compatibility And Legacy Quarantine.

