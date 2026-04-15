# Operations Reference

Related reference: [Ownership](../ownership.md). Related runbooks:
[Runbooks](../../runbooks/index.md).

> Общая operational vocabulary для runtime, control plane, observability,
> retention и handoff.

## Documents

| Page | Purpose |
|---|---|
| [Platform Architecture Diagrams](platform-architecture-diagrams.md) | C4 container view, request path, control-plane lifecycle, CAS/integrity flow, and observability topology in one operator-facing page |
| [SLO and Error Budget Policy](slo-error-budget.md) | Общий язык reliability: service view, SLOs, error budget response, freeze policy |
| [Observability Topology](observability-topology.md) | Signal taxonomy, dashboard/alert ownership, correlation policy, validation strategy |
| [Retention and Recovery Policy](retention-and-recovery.md) | Artifact lifecycle, retention classes, restore drills, recovery posture |
| [CAS Async I/O Roadmap](cas-async-io-roadmap.md) | Staged adapter/shared-executor/async-native plan for CAS hot paths |
| [Handoff and Platform Review](handoff-and-platform-review.md) | Handoff template, retirement checklist, quarterly review ritual, scorecard |
| [Platform Acceptance Audit](platform-acceptance-audit.md) | Phase 7 closeout checklist, automated audit command, contributor-path rehearsals, and manual evidence expectations |
| [Scientist Reliability Scorecard](../scientist/reliability-scorecard.md) | Scientist-specific release gate: required workflow scenarios, benchmarks, and operational signals |

## Operating Assumptions

- `policy-engine/` остаётся canonical product root.
- Alert ownership routed by logical owner groups from
  [Ownership](../ownership.md), even if current GitHub reviewer is still one
  human account.
- Runbooks are executable documentation: incident responders should not need
  chat archaeology before they can act.
- ADRs in `docs/adr/` are part of the platform contract when they describe
  accepted runtime, storage, security, or operator-facing policy.
