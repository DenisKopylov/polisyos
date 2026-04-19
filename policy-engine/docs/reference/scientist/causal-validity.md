# Scientist Causal Validity
Related references: [Scientist Causal Runners](causal.md), [Reliability scorecard](reliability-scorecard.md).

Owner: `@scientist-owners`
Backup owner: `@platform-owners`
Source of truth: `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`, `src/polisyos/scientist/frontier_runtime.py`, `tests/scientist/test_causal_evaluation_node.py`, `tests/scientist/test_decision_packet_node_v3.py`, and `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py`

> Owner lane: `L6 Scientist`  
> Type: Manual reference (not generated).  
> Source of truth: `src/polisyos/scientist/causal/validity.py`, `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py`, `src/polisyos/scientist/frontier_runtime.py`, `tests/scientist/test_causal_evaluation_node.py`, `tests/scientist/test_decision_packet_node_v3.py`, and `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py`.

`RunCausalEvaluationNode` persists a best-effort
`scientist.causal_validity_bundle` artifact through
`persist_causal_validity_bundle(...)`. The bundle exists to keep default-path
validity diagnostics visible in CAS artifacts and downstream decision surfaces
instead of hiding them inside method-local metadata.

## When The Bundle Is Written

| Condition | Current behavior |
|---|---|
| `state.params["causal_validity"].enabled` or `observational_data.metadata["causal_validity"].enabled` is explicitly `false` | No validity bundle is written. |
| Bundle enabled and the base estimate succeeds | Persist the bundle and store its ref under `artifacts_index.causal_validity_bundle_ref`. |
| Optional inputs for a check are missing | The check is recorded as `skipped`; the base estimate still succeeds. |

## Artifact Contract

The persisted JSON payload currently contains:

| Field | Meaning |
|---|---|
| `base_method_fqn` | Method fqdn used for the primary estimate. |
| `base_method` | `CausalMethod` enum value for the base estimate. |
| `base_status` | Base `EstimationStatus`. |
| `confidence` | Confidence interval and inference metadata for the base estimate, including honest-HTE metadata for forest methods. |
| `checks.sensitivity` | Sensitivity artifact linkage and summary metrics. |
| `checks.icp_invariance` | ICP-style multi-domain invariance result when domain labels are available. |
| `checks.proximal_bridge` | Proximal bridge result when proxy inputs are available. |
| `checks.recoverability` | Recoverability / missing-data result when recoverability inputs are available. |
| `checks.pag_refinement` | PAG/CPDAG refinement result when a suitable graph is available. |
| `capability_matrix` | Availability/status summary derived from the checks. |
| `experimental_methods` | Frontier capability summaries mirrored from `build_frontier_runtime_report(...)`. |
| `frontier_runtime` | Serialized frontier-runtime rollout report. |
| `warnings` | Typed skipped/failed check summaries. |

## Check Activation Rules

| Check | Inputs required by the helper | Current default |
|---|---|---|
| Sensitivity | Successful estimate plus sensitivity-compatible data | Enabled when causal sensitivity is available. |
| ICP invariance | `domain_labels` with at least two domains | Best-effort and skipped otherwise. |
| Proximal bridge | Proxy configuration in state/data metadata | Best-effort and skipped otherwise. |
| Recoverability | Recoverability config or M-graph style inputs | Best-effort and skipped otherwise. |
| PAG refinement | Reconciled/prior graph ref or explicit graph in validity settings | Best-effort and skipped otherwise. |

## Configuration Surface

Validity settings are merged from observational-data metadata and
`state.params["causal_validity"]`. The helper currently recognizes:

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

## Frontier/Phase 4 Interaction

The validity bundle also mirrors the current frontier rollout report. Today this
means:

- wired validity checks can surface as part of the bundle without becoming
  default-on beyond the current helper logic;
- frontier capability ids and statuses come from `build_frontier_runtime_report(...)`;
- Phase 4 methods still need explicit offline validation and benchmark evidence
  before they become default-enable eligible.

## Decision-Packet Surface

When the relevant artifacts are present, the decision-packet node can surface
causal-validity and sensitivity material alongside the base causal report. The
authoritative contract for that surfacing is the decision-packet artifact schema
plus the linked decision-packet tests.

## Validation

```bash
uv run pytest tests/scientist/test_causal_evaluation_node.py tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q
```
