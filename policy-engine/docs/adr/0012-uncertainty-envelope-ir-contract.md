# ADR-0012: UncertaintyEnvelope IR Contract

## Status

Accepted

## Date

2026-02-07

## Context

Policy OS produces uncertainty from multiple independent subsystems with incompatible shapes:

- Foundry calibration exposes Hessian-derived parameter uncertainty.
- Fabric trust exposes non-statistical bounds (`UncertaintyBounds`).
- Conflict resolution exposes a scalar confidence score.

This fragmentation blocks end-to-end propagation (Epoch III, Phases 9-10), weakens governance
gates, and makes DecisionPacket uncertainty payloads inconsistent.

## Decision

Introduce a single IR contract `UncertaintyEnvelope` in `polisyos.ir.analytics.uncertainty` with:

- core numeric fields: `point_estimate`, `confidence_interval`
- semantics metadata: `interval_semantics`, `distribution_family`, `source`, `propagation_method`
- policy metadata: `is_heuristic_ci`, `gate_eligible`
- optional statistical field: `confidence_level` (required only for statistical intervals)

Add typed artifact reference `UncertaintyEnvelopeRef` in `polisyos.core.contracts.uncertainty`
and persist envelopes as CAS JSON artifacts with `CanonSpec(forbid_floats=False)`.

Use adapter pattern to preserve subsystem internals:

- `foundry.calibration.uncertainty_adapter`
- `fabric.trust_adapter`
- `fabric.claims.conflicts.uncertainty_adapter`

## Consequences

- Existing contracts remain backward-compatible (`UncertaintyBounds`, conflict `confidence`).
- New consumers can rely on one uncertainty shape across Foundry/Fabric/Conflict flows.
- Heuristic intervals are explicitly marked and can be excluded from strict governance.
- DecisionPacket now includes structured uncertainty references (`schema_version=3.1`).

## Notes

- `TRIANGULAR` distribution is supported but opt-in for trust bounds (`assume_triangular=True`).
- Conflict uncertainty defaults to non-statistical bounds and uses heuristic semantics only when
  candidate ranking cannot form an interval.
