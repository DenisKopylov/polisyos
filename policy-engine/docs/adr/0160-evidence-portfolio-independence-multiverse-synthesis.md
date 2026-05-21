# ADR-0160: Evidence Portfolio, Independence Map, Multiverse, And Synthesis

## Status

Accepted

## Date

2026-05-16

## Context

The PolicyOS repository contains a large evidence and method surface: legal
facts, dataset catalogs, academic records, Foundry methods, Scientist DOE and
discovery machinery, IR analytics, Scholar evidence, and Data Forge corpus
snapshots. A serious policy claim that relies on one dataset and one method by
default wastes that capacity and can create a fragile or misleading result.

The inverse mistake is also dangerous. Hundreds of runs that share the same
primary source, lineage, identification strategy, author pool, preprocessing
assumption, or equivalent method family may provide little independent support.
Raw evidence count is not evidence strength.

The repository already has much of the machinery needed for a better model:
Scientist DOE and discovery, Foundry sensitivity, method consensus and
equivalence, IR causal ensembles and falsification, Scholar retrieval, Data
Forge snapshots, and backtesting. The missing decision is the production
contract that makes these outputs a predeclared evidence portfolio for each
major claim.

## Decision

1. A major empirical policy claim requires a predeclared evidence portfolio per
   evidence strand, unless the active profile accepts an explicit
   single-line-evidence assurance deficit.
2. The portfolio contract is declared before producer execution. It records
   strands, candidate data/source families, candidate method families,
   defensible specifications, inclusion and exclusion rules, disconfirming
   lines, synthesis rules, stopping rules, and run-cost proportionality.
3. An evidence line is a specific combination of source or dataset, method,
   assumptions, specification, producer, and execution context.
4. Evidence strength is measured through effective independent evidence count,
   not raw evidence-line count. Lines must collapse when they share primary
   source lineage, corpus ancestry, author/institution pool, preprocessing,
   assumptions, identification strategy, equivalent method family, or other
   common failure modes.
5. Foundry method consensus and equivalence modules are the first surface for
   method convergence and method-equivalence collapse. Additional lineage and
   assumption collapse may extend them.
6. Scientist DOE, Scientist discovery, Foundry sensitivity, IR causal ensemble,
   IR falsification, Scholar evidence, Data Forge snapshots, and backtesting
   are the first implementation surfaces for portfolio execution and
   projection.
7. The portfolio must emit multiverse or specification-curve evidence when
   defensible analytical choices can affect the claim.
8. The portfolio must include disconfirming evidence lines or record why severe
   tests are not available for the active profile.
9. Evidence disagreement is an output. The case records convergence,
   divergence clusters, heterogeneity, publication or selection bias,
   certainty rating, and sensitivity to synthesis rules.
10. Evidence synthesis is itself a method. Its weighting, heterogeneity model,
    certainty framework, publication-bias treatment, and inclusion/exclusion
    policy require refs and sensitivity checks.
11. Post-hoc selection of only agreeing lines after execution is prohibited for
    serious closeout unless recorded as an assurance deficit that the active
    profile permits.

## Consequences

Positive:

- PolicyOS can become stronger as its method, data, legal, and academic
  surfaces grow.
- Major claims become robust or explicitly fragile instead of accidentally
  overconfident.
- Effective independence prevents false confidence from correlated evidence.
- Existing DOE, discovery, Foundry, IR, Scholar, and Data Forge capabilities
  are reused as portfolio machinery.

Negative:

- High-authority cases may require more compute, storage, and review time.
- Portfolio design introduces a new class of blockers before analysis starts.
- Synthesis and independence rules require governance and calibration because
  they can materially affect recommendations.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- evidence portfolio design schema;
- evidence strand and evidence line schemas;
- independence map and effective independent count records;
- method-equivalence and source-lineage collapse projections;
- multiverse/specification-curve records;
- disconfirming evidence ledger;
- convergence/divergence cluster report;
- evidence synthesis report and certainty rating;
- stopping-rule and information-saturation report;
- run-cost proportionality linkage;
- scorecard/readiness checks for missing portfolio, post-hoc cherry-picking,
  missing independence map, missing severe test, missing synthesis sensitivity,
  and unsupported single-line major claims.

## Related Decisions

- Extends: ADR-0020 Robustness, Sensitivity, And Stress.
- Extends: ADR-0028 Refutation Mandatory For Observational Estimates.
- Extends: ADR-0041 Confidence Aggregation Quality Score Replication Bonus.
- Extends: ADR-0129 Scientist Claim Ledger.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
- Related: ADR-0161 Claim Argument, Warrant Reliability, And Compiler Closeout
  Gate.
