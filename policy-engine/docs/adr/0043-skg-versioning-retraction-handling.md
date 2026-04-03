# ADR-0043: SKG Versioning and Retraction Handling

## Status
Proposed

## Date
2026-02-28

## Context
Scientific knowledge evolves: new studies may revise effect estimates, and retractions must
invalidate derived artifacts (edges, confidence scores, downstream transport decisions).
Without explicit versioning, stale or retracted data could silently persist in the SKG and
propagate incorrect causal claims through the policy engine pipeline.

## Decision
1. A `skg_versions` table tracks the full version history of each causal edge, recording the
   contributing article set, aggregated confidence, and timestamp for each version.
2. Retracted articles are marked with `status = 'retracted'` and a `retraction_date` in the
   `skg_articles` table. Retraction detection runs as part of the weekly OpenAlex sync.
3. When an article is retracted, all edges that included it are automatically re-aggregated
   with the retracted article excluded, producing a new version entry.
4. Downstream artifacts (TransportabilityResult, CausalEnsemble) that referenced a now-stale
   edge version are flagged with `stale_dependency = True` in the IR.
5. A `propagation_log` table records every cascade triggered by a retraction for audit
   purposes.

## Consequences
### Positive
- Full audit trail of how scientific knowledge evolved over time.
- Retractions are handled automatically rather than requiring manual intervention.
- Downstream consumers can detect and react to stale dependencies.

### Negative
- Re-aggregation on retraction adds computational cost to the weekly sync cycle.
- The propagation cascade may invalidate a large number of downstream artifacts, requiring
  re-runs of transport analysis.
- Version history storage grows linearly with the number of edge updates over time.
