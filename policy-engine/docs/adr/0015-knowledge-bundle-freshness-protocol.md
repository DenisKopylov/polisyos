# ADR-0015: KnowledgeBundle Freshness Protocol

## Status

Accepted

## Context

Scholar knowledge bundles were immutable CAS artifacts without explicit temporal metadata.
Workflow-level idempotency caching could reuse old enrichment outcomes without re-checking
whether source data was stale.

## Decision

- Add `freshness` metadata to Scholar bundle payloads (`KnowledgeBundlePayloadV1`) and
  contracts (`KnowledgeBundle`).

- Introduce freshness statuses (`fresh`, `stale`, `expired`) and policy checks with
  domain-specific thresholds.

- Disable DAG idempotency cache bypass for `scientist.node_enrich_knowledge@1.1.0` and
  move to semantic temporal reuse logic inside the node.

- Add cooldown-based refresh guard to reduce re-enrichment storms.
- Emit freshness metrics for age, ratio, status, checks, and refresh attempts.

## Consequences

- Bundle payloads become temporally auditable while staying backward compatible.
- Enrichment node always executes and decides reuse/refresh based on freshness semantics.
- Failed refresh attempts no longer trigger immediate repeated retries.
