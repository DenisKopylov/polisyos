# Scientist Causal Validity Bundle
Related reference: [Scientist Causal Runners](causal.md), [Reliability scorecard](reliability-scorecard.md).

`run_causal_evaluation` now persists an auxiliary `scientist.causal_validity_bundle`
artifact whenever the causal estimate succeeds and the input surface supports at
least one validity check. The bundle is designed to keep statistical and causal
diagnostics visible on the default Scientist path instead of leaving them inside
method-local metadata or notebook-only workflows.

## Artifact Contract

| Field | Meaning |
|------|---------|
| `base_method_fqn` | Foundry method used for the primary estimate |
| `base_status` | Success/failure status of the primary causal estimate |
| `confidence` | Confidence surface for the base estimate, including honest-HTE metadata for forest estimators |
| `checks.sensitivity` | E-value / Rosenbaum summary and sensitivity artifact linkage |
| `checks.icp_invariance` | Multi-domain invariance check when domain labels are supplied |
| `checks.proximal_bridge` | Proximal bridge diagnostic when negative-control proxies are available |
| `checks.recoverability` | Selection-bias / M-graph recoverability result when an M-graph is available |
| `checks.pag_refinement` | PAG or CPDAG refinement output and refined graph artifact |
| `capability_matrix` | Runtime-visible matrix of available vs experimental causal-validity capabilities |
| `warnings` | Typed skipped/failed checks that should remain operator-visible |

## When Checks Run

| Check | Required inputs | Default behavior |
|------|------------------|------------------|
| Sensitivity metrics | successful estimate plus graph/HDE-coercible input | enabled |
| ICP invariance | `domain_labels` with at least two domains | enabled when inputs are present |
| Proximal bridge | treatment/outcome proxies or named proxy columns | enabled when inputs are present |
| Recoverability | M-graph artifact or explicit `mgraph_data` | enabled when inputs are present |
| PAG refinement | PAG/CPDAG artifact in state or explicit causal graph | enabled when inputs are present |

All checks are best-effort. Missing optional inputs produce typed `skipped`
statuses instead of breaking the base estimate.

## Decision Packet Surface

`build_decision_packet` now exposes two explicit sections for WS-3A:

- `payload["sensitivity"]`: persisted sensitivity artifact plus a short
  robustness summary.
- `payload["causal_validity"]`: the causal-validity bundle artifact and content.

The diagnostics summary also mirrors high-signal states such as:

- `sensitivity_status`
- `sensitivity_robust`
- `icp_status`
- `proximal_status`
- `recoverability_status`
- `pag_refinement_status`

This keeps confidence and sensitivity visible on the default decision path.

## Configuration

Runtime toggles live under `state.params["causal_validity"]` or
`observational_data.metadata["causal_validity"]`.

Supported knobs:

- `enabled`
- `enable_icp`
- `enable_proximal`
- `enable_recoverability`
- `enable_pag_refinement`
- `domain_labels`
- `proximal`
- `recoverability`
- `mgraph_data`
- `causal_graph`

## Current Coverage

The bundle is intentionally explicit about what is not yet production-ready.
These capabilities are emitted as `experimental_not_wired` in the
`capability_matrix` until a separate Phase 3 validation program lands:

- `anchor_regression`
- `bayesian_causal_discovery`
- `neural_causal_discovery`
- `causal_representation_learning`

## Regression Evidence

Core regression coverage for the bundle and decision-path surfacing lives in:

- `tests/scientist/test_causal_evaluation_node.py`
- `tests/scientist/test_decision_packet_node_v3.py`
- `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py`
