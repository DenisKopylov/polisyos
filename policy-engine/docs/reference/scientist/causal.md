# Scientist Causal Runners
Related explanation: [Causal Engine](../../explanation/causal-engine.md).
Additional reference: [Causal validity bundle](causal-validity.md), [WS-3A acceptance report](causal-validity-acceptance.md).

Owner: `@scientist-owners`
Source of truth: `src/polisyos/scientist/causal/**`, `src/polisyos/scientist/nodes/builtins/causal/**`, and the linked causal-validity acceptance evidence

The `polisyos.scientist.causal` package provides pure runner-style APIs used by builtin nodes to transform observation-plane bundles into readiness entries, transportability artifacts, and bounded-execution outputs.

## Runner Catalog

| API | Input IR | Output IR / entries | Role |
|-----|----------|---------------------|------|
| `BoundsEstimationRunner` | `BoundsEstimationTask` | bounds-estimation entries and bundle refs | Execute bounded-identification tasks and persist bundle artifacts |
| `ProxyIdentificationRunner` | `ProxyIdentificationBundle` | proxy readiness entries | Score proxy validity against the reconciled graph |
| `TransportabilityChecker` | `TransportabilityCheckBundle` | transportability readiness entries and result refs | Compile transportability checks against calendars and regime metadata |
| `StrategicResponseRunner` | `StrategicResponseSpecsBundle` | strategic readiness entries and strategic-response bundle refs | Evaluate adaptation channels and strategic closure readiness |
| `CounterfactualQueryRunner` | `CounterfactualCheckBundle` | counterfactual readiness entries | Determine whether required counterfactual queries are identified |
| `build_interference_readiness_entries()` | `InterferenceLossSpecBundle` | interference readiness entries | Normalize interference-loss requirements into readiness metadata |

## Default-Path Validity Surface

The builtin causal execution path now also persists a `scientist.causal_validity_bundle`
artifact. This is the operator-facing validity surface that aggregates:

- sensitivity metrics and robustness summaries
- ICP invariance when domain labels are available
- proximal bridge diagnostics when proxy variables are available
- recoverability checks for M-graphs
- PAG refinement lineage for CPDAG/PAG inputs

See [causal-validity.md](causal-validity.md) for the contract and
[causal-validity-acceptance.md](causal-validity-acceptance.md) for the current
acceptance evidence.

## D1 Causal Claim Discipline

Phase 3 causal claims map to persisted artifacts or explicit tests. If a method
is implemented but lacks validation and benchmark evidence, it remains
experimental or offline-gated and must not be described as a default-path SOTA
capability.

| Claim | Required artifact or status | Evidence |
|-------|-----------------------------|----------|
| Default-path causal estimate is confidence-visible | `scientist.causal_validity_bundle.confidence` and decision-packet `causal_validity` section | `tests/scientist/test_causal_evaluation_node.py`, `tests/scientist/test_decision_packet_node_v3.py` |
| Sensitivity and robustness are auditable | `checks.sensitivity`, sensitivity result ref, robustness summary | `tests/foundry/methods/catalog/causal/test_validity_eval_pack.py` |
| Transportability, proxy, strategic, interference, and counterfactual readiness are explicit | Readiness entries and `run_causal_readiness` outputs, including blocker summaries where required | `tests/scientist/nodes/builtins/causal/test_run_causal_readiness.py`, `tests/scientist/nodes/builtins/causal/test_counterfactual_identification_gate.py` |
| Frontier causal methods are not default-on | `FrontierRuntimeReport.capabilities[*].status` plus `offline_validation_ref` and `benchmark_pack_ref` before offline availability | `tests/scientist/test_frontier_runtime.py`, [frontier-runtime.md](frontier-runtime.md) |

## Phase 2 Research-Result Closure Notes

Stage 9.2 latent separation is now computed from raw `separation_diagnostic_inputs`
when present. The computed payload has precedence over prefilled
`metadata["separation_diagnostics"]`.

Stage 9.3 adds judge-derived promotion semantics on top of that research lane.
Bundles without structured `promotion_evidence` still stay
`readiness_cap="proof_only"` with `claim_mode="proof_only"`. Bundles that pass
the conditional promotion gate surface `claim_mode="bounded_latent"` /
`degradation_mode="bounds_only"` and can influence bounds-grade reasoning.
Only narrow reflective measurement scopes that also pass the validated gate can
surface `claim_mode="validated_measurement_latent"` /
`degradation_mode="measurement_ready"`. Human review remains mandatory at every
latent trust level; the frontier module never self-certifies promotion on its
own.

Stage 13.2 intentionally keeps multi-target modified treatment policies as a v1
limitation. Single-target stochastic interventions and single-target MTPs have
the executable Phase 2 path; multi-target MTP queries return
`oracle_needed` with an explicit non-executable reason and are deferred to
post-Phase-2 composition work.

## Phase 4 Stage 2.5 — Composition Completeness Scope

`CompositionCertificate` now carries an explicit completeness-scope annotation.
The certificate is complete (theorem-backed) only for the
`exact_observed_dag_adjustment_v1` subclass: DAG fragments, `exact` or
human-verified `exact` alignments (no proxy / latent-bridge), observed
bindings, cleared review status, acyclic composition, and single-world
`INTERVENTIONAL`/`SOFT_INTERVENTION` queries that identify via covariate
adjustment. Within that scope `status == "preserved"` is an iff statement on
adjustment preservation (Perković et al.). Outside that scope `preserved` is
an engineering verdict only, reflecting the general impossibility of
completeness for a certificate language that checks only
`backdoor_adjustment` obligations (Shpitser–Pearl ID with hedge
counter-examples).

The composition node records the classification under
`metadata.completeness_scope`, `metadata.completeness_basis`, and
`metadata.non_completeness_reason`; see
`polisyos.ir.analytics.cross_graph.completeness_scope_for_composition` for the
classifier and the `CompositionCertificate` docstring for the full theorem
statement, scope list, and the out-of-scope impossibility result.

## Validation Commands

```bash
uv run pytest tests/scientist/nodes/builtins/causal -q
uv run pytest tests/scientist/test_causal_evaluation_node.py tests/scientist/test_decision_packet_node_v3.py -q
uv run pytest tests/foundry/methods/catalog/causal/test_validity_eval_pack.py -q
```

## Execution API

::: polisyos.scientist.causal

::: polisyos.scientist.causal.execution

::: polisyos.scientist.causal.readiness
