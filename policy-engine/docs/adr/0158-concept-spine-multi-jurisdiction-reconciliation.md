# ADR-0158: Concept Spine And Multi-Jurisdiction Reconciliation

## Status

Accepted

## Date

2026-05-16

## Context

Pass 1A diagnostics found that policy concepts fragment across request payloads,
metric catalogs, dataset catalogs, legal stores, method contracts, semantic
binding ledgers, and final claims. When that happens, a final claim can look
grounded while its legal, data, method, and objective records are actually
talking about different populations, geographies, periods, units, or legal
concepts.

The repository already has several relevant reconciliation surfaces:
`src/polisyos/fabric/entity_resolution`, `src/polisyos/scientist/cross_graph`,
`src/polisyos/ir/linker`, `src/polisyos/ir/registry`,
`src/polisyos/ir/world`, and IR analytics for cross-graph and normative
arbitration. The right first move is to project a per-run authority spine over
those surfaces, not to create another standalone registry by default.

Policy cases can also span supranational, national, regional, and local legal
authority. A single-corpus legal assumption is not sufficient for serious
policy design.

## Decision

1. Every serious policy run must produce a per-run concept and jurisdiction
   spine or typed blockers.
2. The concept spine records canonical concept ids, aliases, source terms,
   metric bindings, dataset and column bindings, legal concept bindings,
   method requirement bindings, objective and tradeoff bindings, geography,
   population, time, unit, currency, and calendar semantics.
3. The jurisdiction spine records applicable jurisdictions, authority levels,
   temporal validity, hierarchy, delegation, competence, pre-emption, conflict
   rules, and unresolved legal blockers.
4. Lex, Fabric, Scholar, Foundry, Scientist, and the claim compiler must
   consume the run spine. They may add candidate bindings, but they may not
   silently create incompatible local concepts.
5. The initial implementation surface is a reconciled authority artifact over
   Fabric entity resolution, Scientist cross-graph, IR linker/registry/world,
   and IR legal/normative analytics.
6. A new monolithic concept registry is allowed only after implementation
   records which existing reconciliation surfaces failed and why.
7. Scorecard and readiness gates must fail when final claims rely on concepts,
   jurisdictions, units, periods, or populations that do not close over the
   same run spine.

## Consequences

Positive:

- A1, A2, and A3 domain remediation can share one concept authority result.
- Legal, data, method, objective, and claim evidence can be checked for
  semantic closure.
- Multi-jurisdiction conflicts become explicit policy evidence instead of
  prose caveats.
- Existing entity-resolution and graph-reconciliation machinery is reused.

Negative:

- The spine becomes a high-leverage artifact and needs compatibility discipline.
- Some cross-domain or vague requests will block until concepts and
  jurisdictions can be reconciled.
- Producers must carry concept refs even when their local APIs currently use
  labels or raw strings.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- per-run concept spine schema;
- jurisdiction spine and conflict-record schema;
- projection adapters over Fabric entity resolution, Scientist cross-graph,
  IR linker/registry/world, and normative arbitration;
- producer APIs that accept or emit spine refs;
- scorecard/readiness checks for concept mismatch, jurisdiction mismatch,
  unit/time/geography mismatch, and local-concept leakage;
- tests for multi-jurisdiction conflict, stale spine refs, and claim evidence
  bound to incompatible concepts.

## Related Decisions

- Extends: ADR-0036 Variable Canonizer Hierarchical Names.
- Extends: ADR-0051 Legal To DAG Mapping Types.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0147 Production Evidence Authority Ordering.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0157 Policy Intent Envelope, Capability Ledger, And Authority
  Profile Mapping.
- Related: ADR-0159 Production Evidence Producer Contracts For Lex, Fabric,
  Scholar, And Data Forge.
