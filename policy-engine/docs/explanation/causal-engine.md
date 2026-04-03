# Causal Engine: Design Rationale

## Why a dedicated causal engine

The PolicyOS causal engine exists because policy analysis needs more than a standalone estimator. In this codebase, causal work is not a single `estimate()` call but a governed pipeline that starts with graph discovery, moves through identification and estimation, and ends with transport, strategic adaptation, and publication gates. Libraries such as DoWhy and EconML remain useful reference points, but they do not natively cover the full policy workflow that PolicyOS requires: discovery, identification, estimation, bounds, sensitivity, strategic response, transportability, and governance in one auditable stack.

The second reason is honesty under incomplete evidence. Public-policy data is frequently censored, proxy-based, regime-shifted, or only partially measured. In those cases the system should not pretend that a point estimate exists. PolicyOS therefore treats partial identification as a first-class outcome: if the query is not point-identified, the engine routes toward bounds, proxy checks, or transport diagnostics and carries those limits downstream as part of the decision record.

## Pipeline Architecture

```mermaid
flowchart LR
  A["Discovery"] --> B["Graph Reconciliation"]
  B --> C["Identification"]
  C --> D["Estimation"]
  D --> E["Bounds"]
  E --> F["Sensitivity and Specification Curves"]
  F --> G["Strategic Response"]
  G --> H["Transportability"]
  H --> I["Dynamic Treatment Regimes"]
  I --> J["Governance"]
```

The long-form predecessor for this document is `docs/CAUSAL_ENGINE_ARCHITECTURE.md`. That file is still the most exhaustive architectural dump, but the current runtime now includes new Scientist-side readiness, execution, strategic, and transport stages that make the end-to-end story broader than the original Foundry-only write-up.

## Stage 1: Causal Discovery

PolicyOS uses a dual discovery strategy instead of betting on one family of algorithms.

- Constraint-based discovery lives in ``constraint_discovery.py`` (`../../src/polisyos/foundry/methods/catalog/causal/constraint_discovery.py`) and covers PC, FCI, and GES. This path is good at exposing conditional-independence structure, latent-confounding warnings, and algebraic audit traces.
- Continuous optimization lives in ``dagma_discovery.py`` (`../../src/polisyos/foundry/methods/catalog/causal/dagma_discovery.py`). DAGMA gives the engine a complementary search path when smooth score-based optimization is more stable than discrete CI search.
- ``discovery_pipeline.py`` (`../../src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py`) wraps both into `UnifiedCausalDiscovery`, characterizes the data, selects candidate algorithms, and builds a consensus PAG/DAG view.

Discovery is not trusted on its own. ``ReconcileCausalGraphNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py`) merges four evidence channels into a single `CausalGraphModel`.

- A data-derived graph from discovery.
- A literature prior built by ``BuildLiteraturePriorNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/build_literature_prior.py`).
- User or LLM structural hints.
- SCM fragments and optional query-preservation hooks.

The ensemble layer is new on the Scientist side. ``RunCausalEnsembleNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/run_causal_ensemble.py`) resolves multiple member graphs, runs bootstrap-style stability scoring, rejects unstable members, and emits a consensus graph only if the merged edge set stays structurally coherent.

## Stage 2: Identification

Identification answers the real causal question: can the requested quantity be written as a function of observables, or do we need a fallback?

- ``id_engine.py`` (`../../src/polisyos/foundry/methods/catalog/causal/id_engine.py`) implements the routing core: standard ID/IDC, counterfactual `id*`/`idc*`, transportability, z-identification, multi-domain identification, stochastic interventions, conditional interventions, and dynamic intervention identification.
- ``CounterfactualIdentificationGateNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/counterfactual_identification_gate.py`) is the explicit pass/fail gate for counterfactual readiness before downstream execution.
- The engine still recognizes standard patterns such as back-door, front-door, and IV, but it exposes them through symbolic identification and compilation rather than through a single estimator-specific shortcut.

Observation contracts influence routing before estimation even starts. ``IdentificationMode`` (`../../src/polisyos/ir/observation/contracts.py`) and ``IdentificationModeRouter`` (`../../src/polisyos/ir/observation/measurement.py`) let the system downgrade a family from point identification to proxy or bounds mode when coverage, censoring, measurement bias, or shock conditions make a stronger claim unsafe.

## Stage 3: Estimation and Bounds

Once a query is identified, ``CausalEngine`` (`../../src/polisyos/foundry/methods/catalog/causal/causal_engine.py`) compiles symbolic estimands into execution plans and hands them to the estimator catalog. That catalog includes the usual policy-evaluation tools, but the important architectural point is that point estimation is only one branch of execution.

- ``BoundsEngineMethod`` (`../../src/polisyos/foundry/methods/catalog/causal/bounds_engine.py`) is the Foundry-side orchestrator for partial-identification methods.
- ``BoundsEstimationRunner`` (`../../src/polisyos/scientist/causal/execution.py`) is the Scientist-side executor that turns `BoundsEstimationTask` records into `BoundsEstimationEntry` results inside a `CausalExecutionBundle`.
- ``ProxyIdentificationRunner`` (`../../src/polisyos/scientist/causal/readiness.py`) evaluates `ProxyIdentificationBundle` channels against the reconciled graph and emits typed `ProxyIdentificationEntry` evidence when latent constructs can be rescued through observed proxies instead of dropped outright.
- Measurement-error rescue lives in ``measurement_error.py`` (`../../src/polisyos/foundry/methods/catalog/causal/measurement_error.py`), including `identify_with_proxy()`, `bounds_with_measurement_error()`, and `_proxy_boundary_metadata()` / `latent_proxy_boundary_notes()` propagation.

This proxy path sits between clean point identification and generic fallback. If a query cannot be defended with direct observables but a proxy channel is structurally admissible, the engine records that as a proxy-identified route first and only falls through to wider bounds when the proxy rescue also fails.

This is the core reason partial identification matters in PolicyOS. If the system cannot defensibly identify a point effect, it prefers an honest interval or fallback certificate to a falsely precise scalar. Bounds become a first-class artifact, not an afterthought.

## Stage 4: Sensitivity and Specification Curves

Policy recommendations should not depend on one lucky specification. The causal stack therefore exposes robustness artifacts instead of hiding them inside notebooks.

- ``SpecificationCurveBundle`` (`../../src/polisyos/ir/observation/bundles.py`) packages many admissible specifications into one contract-level input.
- `SensitivityResult` lives in ``scientist/doe/designs.py`` (`../../src/polisyos/scientist/doe/designs.py`) and is used for downstream robustness diagnostics.
- Calibration governance later turns specification-curve robustness into a scored leaderboard dimension rather than leaving it as an unstructured appendix.

## Stage 5: Strategic Response

Naive policy evaluation assumes the world stays still after intervention. Real agents adapt. Suppliers change bids, households re-time behavior, and regulated actors search for loopholes. If the model ignores that adaptation, a policy can look effective on paper and fail in deployment.

PolicyOS models this explicitly through ``StrategicSCM`` (`../../src/polisyos/ir/analytics/strategic.py`) and `FiniteStrategicPayoffTable` contracts. The solver in ``strategic.py`` (`../../src/polisyos/foundry/methods/catalog/causal/strategic.py`) supports exact Stackelberg and best-response fixed-point closures, reports multiplicity and selection dependence, and falls back to strategic bounds or macro abstraction when exact equilibrium is too expensive or unsupported. The IR also defines a `NASH` equilibrium concept, but the current runtime marks that mode as research-gated and blocks or downgrades it rather than silently pretending to solve it.

This matters in policy context because equilibrium is not just game theory jargon. It is the mechanism for representing how agents jointly re-optimize after a policy change. In practical terms, it is the difference between "the subsidy raises uptake in a static dataset" and "the subsidy still works after providers, firms, or households adapt their strategies."

- ``StrategicResponseRunner`` (`../../src/polisyos/scientist/causal/readiness.py`) builds and persists the strategic closure artifacts used by governance.
- ``RunABMConsistencyCheckNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/run_abm_consistency.py`) cross-checks strategic predictions against agent-based model behavior, so strategic claims are not left unvalidated.
- ``StrategicResponsePass`` (`../../src/polisyos/scientist/governance/passes/strategic_response_pass.py`) blocks missing evidence and escalates multiplicity or approximation to human review.

## Stage 6: Transportability

Even a well-identified estimate may fail when moved across domains or regimes. PolicyOS treats transportability as a dedicated stage rather than a footnote.

- ``TransportabilityChecker`` (`../../src/polisyos/scientist/causal/readiness.py`) runs preflight checks from contract bundles and produces readiness entries.
- ``RunTransportabilityNode`` (`../../src/polisyos/scientist/nodes/builtins/causal/resolve_transport.py`) executes a multi-round resolution loop, synthesizes legal and regime mismatch into `S`-nodes, and emits certificates or degraded fallbacks.
- Temporal mismatch handling is grounded in ``RegimeCalendar`` (`../../src/polisyos/ir/observation/measurement.py`), ``SchemaRegimeRegistry`` (`../../src/polisyos/ir/observation/measurement.py`), and `ShockCalendar`, so transport failure can be traced to actual regime boundaries rather than hand-waved as "external validity."

Transportability is therefore not only cross-country transfer. It also covers cross-regime, cross-schema, and shock-boundary movement inside the same policy domain.

## Stage 7: Dynamic Treatment Regimes

Many policies are sequential by design: a rule changes in month one, targeting changes in month two, and eligibility changes again in month three. PolicyOS represents this directly through temporal intervention artifacts instead of flattening everything into one treatment flag.

- ``TemporalInterventionSequencer`` (`../../src/polisyos/lex/interventions.py`) and `TemporalInterventionSequenceCompiler` translate policy timelines into causal execution inputs.
- ``TemporalDTRTask`` (`../../src/polisyos/ir/observation/causal_execution.py`) and `TemporalDTRExecutionEntry` carry those tasks through Scientist execution.
- Foundry-side DTR methods live in ``dtr.py`` (`../../src/polisyos/foundry/methods/catalog/causal/dtr.py`) and include Q-learning, A-learning, outcome-weighted learning, and doubly robust variants.

## Integration with Foundry

The Foundry catalog is where the statistical work happens. Relevant modules include:

- ``discovery_pipeline.py`` (`../../src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py`)
- ``dagma_discovery.py`` (`../../src/polisyos/foundry/methods/catalog/causal/dagma_discovery.py`)
- ``constraint_discovery.py`` (`../../src/polisyos/foundry/methods/catalog/causal/constraint_discovery.py`)
- ``causal_engine.py`` (`../../src/polisyos/foundry/methods/catalog/causal/causal_engine.py`)
- ``id_engine.py`` (`../../src/polisyos/foundry/methods/catalog/causal/id_engine.py`)
- ``bounds_engine.py`` (`../../src/polisyos/foundry/methods/catalog/causal/bounds_engine.py`)
- ``measurement_error.py`` (`../../src/polisyos/foundry/methods/catalog/causal/measurement_error.py`)
- ``strategic.py`` (`../../src/polisyos/foundry/methods/catalog/causal/strategic.py`)
- ``dtr.py`` (`../../src/polisyos/foundry/methods/catalog/causal/dtr.py`)
- ``policy_learning.py`` (`../../src/polisyos/foundry/methods/catalog/causal/policy_learning.py`)

`OptimalPolicyLearner` sits on the policy-learning side of this interface and turns CATE-style heterogeneity into budget-constrained targeting decisions instead of stopping at average effects.

## Integration with Scientist

The new Scientist-side causal package adds orchestration layers on top of the Foundry catalog.

- ``scientist/causal/`` (`../../src/polisyos/scientist/causal/`) now provides three runner modules: execution, readiness, and package exports.
- ``causal_full_workflow_spec()`` (`../../src/polisyos/scientist/workflows/causal_full.py`) wires the end-to-end workflow, including reconciliation, readiness, ensemble, ABM consistency, transportability, normative arbitration, and governance.
- The causal builtins package contains ten concrete nodes: literature prior, graph reconciliation, counterfactual gate, readiness, contract execution, ensemble, ABM consistency, query execution, transportability, and parameter resolution.

That split is intentional. Foundry owns causal methods. Scientist owns workflow orchestration, contract execution, and governance-facing disclosure. Together they make causal inference a reproducible policy pipeline rather than a single estimation primitive.
