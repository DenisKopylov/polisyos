# ADR-0039: Context Profile Distance and Inference Level

## Status

Proposed

## Date

2026-02-28

## Context

Phase 12 transportability analysis requires quantified assessment of how
"different" a source context is from a target context. Without a structured
context representation and distance metric, transport analysis cannot produce
meaningful confidence scores.

Context profiles may be constructed at different levels of detail: some are
inferred from basic metadata (country, year), others are enriched with
covariate distributions from datasets, and some are manually specified by
domain experts. The precision of the distance estimate depends on the
enrichment level.

## Decision

1. `ContextProfile` (in `polisyos.ir.analytics.transportability`) includes
   a **`distance_to(other: ContextProfile) -> float`** method that returns
   a normalized distance in [0.0, 1.0].
2. Distance computation aggregates differences across:

   - Geographic/institutional features,
   - Temporal distance,
   - Covariate distribution divergence (when available).
3. Each `ContextProfile` tracks its **`inference_level`** with one of:

   - `INFERRED_BASIC`: derived from metadata only (country code, year).
   - `ENRICHED`: augmented with covariate statistics from linked datasets.
   - `MANUAL`: expert-specified with full covariate detail.
4. Transport confidence is **capped** based on inference level:

   - `INFERRED_BASIC`: max transport confidence 0.5,
   - `ENRICHED`: max transport confidence 0.8,
   - `MANUAL`: no cap.
5. The inference level and distance components are persisted in the
   `TransportabilityResult` artifact for auditability.

## Consequences

### Positive

- Quantified transport gap assessment replaces subjective "similar enough"
  judgments.

- Inference level caps prevent over-confident transport claims from sparse
  context data.

- Full persistence of distance components enables governance audit of
  transport decisions.

### Negative

- Context distance is inherently approximate; the metric may not capture
  all relevant contextual differences.

- Enriched profiles require linked dataset availability, which may not
  exist for all contexts of interest.
