# Causal Runtime (`polisyos.scientist.methods.causal`)

`causal` is a Scientist package for execution/readiness runners that process
observation-plane causal contracts and publish transportability,
strategic-response, counterfactual, and bounds artifacts.

## Role in the system

- **Depends on:** `foundry.methods.catalog.causal`, `ir.observation`, `ir.analytics`
- **Used by:** `nodes.builtins.causal.run_causal_readiness`,
  `nodes.builtins.causal.run_causal_contract_execution`

- The package separates orchestration-level nodes from domain-specific causal runners.

## Key concepts

- **Proxy identification** — readiness checks for proxy-based identification bundles.
- **Transportability** — transport proof/status evaluation using selection diagrams.
- **Strategic response** — strategic payoff/SCM solving and artifact publication.
- **Counterfactual queries** — ID*/IDC* based readiness evaluation.
- **Interference readiness** — family-aware interference loss requirements.
- **Bounds execution** — contract-driven bounds estimation runner for C4b tasks.

## Public API

- `BoundsEstimationRunner`
- `CounterfactualQueryRunner`
- `ProxyIdentificationRunner`
- `StrategicResponseRunner`
- `TransportabilityChecker`
- `build_interference_readiness_entries(...)`

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-14
- Python modules: 4 (excluding `__init__.py`, tree inventory)
- Exports: 6
- README created for a new package that had not previously been covered by the module documentation.
