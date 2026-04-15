# Scientist Frontier Runtime

Related reference: [Agent Search And Reasoning](agent-search-reasoning.md).

> Phase 4 runtime contract for frontier capabilities. The default path stays
> conservative: frontier methods remain feature-flagged until offline validation
> and benchmark packs show they are safe to evaluate outside the baseline path.

## Capability Statuses

| Status | Meaning |
|--------|---------|
| `disabled` | The feature flag is off and the capability cannot affect runtime behavior. |
| `offline_gated` | The capability is wired enough to run offline, but it is blocked until validation and benchmark refs are present. |
| `available_offline` | The capability has the evidence required for offline evaluation, but it is still not eligible to replace the baseline by default. |
| `experimental_not_wired` | The contract surface exists, but the runtime wiring or evaluation support is still incomplete. |

## Current Families

- Causal frontier methods:
  - proximal causal inference
  - Bayesian causal discovery
  - neural DAG learners
  - causal representation learning
- Search / governance frontier methods:
  - adversarial scenario discovery
  - continuous governance loop

## Rollout Contract

Every frontier capability must publish:

- a capability id
- a feature flag
- a module path
- a method or artifact identifier
- an offline validation reference
- a benchmark pack reference
- an explicit baseline-replacement posture
- a rationale explaining why the capability is still gated

## Default-On Rule

Frontier methods are not allowed to become default-on merely because they are
implemented. They must remain behind a feature flag until:

1. Offline validation exists.
2. A benchmark pack exists.
3. Baseline replacement is explicitly approved.

## Source Of Truth

- Runtime report builder: `polisyos.scientist.frontier_runtime`
- Tests: `tests/scientist/test_frontier_runtime.py`
- Related acceptance surface: [remediation-status.md](remediation-status.md)
