# ADR-0159: Production Evidence Producer Contracts For Lex, Fabric, Scholar, And Data Forge

## Status

Accepted

## Date

2026-05-16

## Context

Pass 1A diagnostics found that production data, legal stores, datasets,
academic records, and source manifests exist, but serious runtime evidence does
not yet consistently expose the producer-owned contracts needed by final
claims. Lex can have a populated legal corpus without runtime candidate norms.
Fabric can see broad manifest roles instead of scenario source families.
Scholar can build CAS-first knowledge bundles without being treated as a
first-class policy evidence producer. Data Forge can own offline corpus builds
and snapshots while runtime evidence fails to bind to those snapshot contracts.

If those responsibilities remain implicit, the claim compiler and scorecard
will keep seeing generic evidence blobs instead of legal, source, literature,
and corpus authority.

## Decision

1. Lex, Fabric, Scholar, and Data Forge are distinct production evidence
   producers with distinct serious-run duties.
2. Lex owns legal retrieval and norm binding evidence: legal corpus snapshot,
   query terms, concept refs, jurisdiction/time filters, candidate norms,
   selected norms, rejected norms, conflicts, competence, and no-norm or
   retrieval-failure blockers.
3. Fabric owns source and data evidence: source family, source rights, dataset,
   dictionary, schema, fields, units, geography, time coverage, quality,
   missingness, freshness, lineage, transformations, selected and rejected
   candidates, and data-gap blockers.
4. Scholar owns academic and grey-literature evidence: research intent, query
   graph, provider traces, source scoring, snippets, citations, freshness,
   corpus lineage, support/conflict links, selected and rejected candidates,
   and literature-deficit blockers.
5. Data Forge owns offline corpus build and snapshot evidence for production
   legal, catalog, academic, and domain data. Runtime evidence must bind to
   Data Forge snapshot manifests, quality gates, artifact ids, and
   `src/polisyos/data_forge/read_api` surfaces when those corpora are in scope.
6. Static inventory, local file presence, broad manifest roles, or narrative
   citations cannot substitute for producer-owned runtime evidence.
7. Scorecard and readiness gates must fail when final claims use legal, data,
   literature, or corpus evidence that lacks producer-owned refs, snapshot
   identity, semantic bindings, freshness, rights, quality, or blockers.

## Consequences

Positive:

- Legal, data, literature, and corpus evidence become separate authority
  families rather than generic payloads.
- Scholar becomes a real producer for academic evidence instead of a narrative
  helper.
- Data Forge snapshot provenance becomes visible to runtime closeout.
- Final claims can distinguish "no relevant source exists" from "producer did
  not retrieve or bind the source."

Negative:

- Existing source and literature reports need more metadata before they can
  satisfy serious gates.
- Runtime integration must respect Data Forge snapshot/read-API boundaries.
- More candidate/rejected-source records must be retained for audit.

## Concrete impact

This ADR requires future implementation work to introduce or update:

- Lex legal retrieval and norm-binding evidence schemas;
- Fabric source-family, field-binding, quality, rights, and lineage schemas;
- Scholar retrieval, scoring, freshness, citation, and support/conflict
  evidence schemas;
- Data Forge snapshot/read-API binding records;
- scorecard/readiness checks for producer duty, snapshot identity, source
  rights, freshness, quality, semantic binding, and selected/rejected candidate
  evidence;
- negative tests for static inventory substitution, manifest-role false pass,
  legal-shaped payload without retrieval, narrative citation without Scholar
  provenance, and local corpus path leakage.

## Related Decisions

- Extends: ADR-0015 KnowledgeBundle Freshness Protocol.
- Extends: ADR-0021 Connector Schema Contracts And Storage Port.
- Extends: ADR-0112 Data Forge Consolidation.
- Extends: ADR-0122 Lakehouse Snapshot Semantics.
- Extends: ADR-0152 Semantic Binding, Lineage, And Claim Evidence.
- Related: ADR-0156 Policy Design Case Runtime Quality Assurance Profile.
- Related: ADR-0158 Concept Spine And Multi-Jurisdiction Reconciliation.
- Related: ADR-0160 Evidence Portfolio, Independence Map, Multiverse, And
  Synthesis.
