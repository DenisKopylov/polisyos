# Run Causal Analysis

This how-to shows the current programmatic causal-analysis entry points. The
examples are intentionally small and local. Use the full Scientist workflow when
you need decision governance and policy report assembly.

## Input

- a local environment with the causal or test extras installed;
- a focused causal task: discovery, identification, bounds, sensitivity, or DTR;
- the understanding that these snippets validate entry points, not full policy
  governance workflows.

## Output

- a working local example for the relevant causal-analysis surface;
- a clear next step into Foundry or Scientist when the workflow must become
  governed, reproducible, or report-bearing.

## Commands

```bash
cd policy-engine
uv sync --frozen --extra causal --extra test
uv run pytest \
  tests/foundry/methods/catalog/causal/test_discovery_pipeline.py \
  tests/foundry/methods/catalog/causal/test_causal_engine.py \
  tests/foundry/methods/catalog/causal/test_bounds_engine.py -q
```

## Install Surface

For the broad causal stack:

```bash
uv sync --frozen --extra causal --extra test
```

For lean local smoke checks, the base test environment is enough for many
Foundry catalog examples.

## 1. Discovery

The unified discovery entry point lives in
`polisyos.foundry.methods.catalog.causal.discovery_pipeline`.

```python
import numpy as np

from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.protocols import UnifiedDiscoveryData

rng = np.random.default_rng(7)
x = rng.normal(size=200)
y = 0.8 * x + rng.normal(scale=0.1, size=200)
z = 0.5 * x + 0.5 * y + rng.normal(scale=0.1, size=200)

state = UnifiedDiscoveryData(
    data=np.column_stack([x, y, z]),
    variable_names=["X", "Y", "Z"],
)

report = UnifiedCausalDiscovery.pure_step(
    state,
    {"force_algorithms": ["pc"], "significance_level": 0.05},
)["report"]

print(report.unified_pag.graph_type)
print(report.unified_pag.nodes)
```

On macOS or Python versions that spawn multiprocessing workers by default, run
discovery examples from a normal `.py` file with `if __name__ == "__main__":`
rather than from `python - <<'PY'`.

## 2. Identification

The identification engine lives in
`polisyos.foundry.methods.catalog.causal.id_engine`.

```python
from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType

graph = CausalGraphModel(
    graph_type=GraphType.DAG,
    nodes=["X", "Y"],
    edges=[CausalEdge(src="X", dst="Y")],
)

identified = id_algorithm(treatment={"X"}, outcome={"Y"}, graph=graph)
print(identified.status)
print(identified.estimand_ast is not None)
```

Current status values include `IDENTIFIED`, `HEDGE_FOUND`, `PAG_AMBIGUOUS`,
`ORACLE_NEEDED`, and `NOT_RECOVERABLE`.

## 3. Bounds Estimation

Use bounds when point identification is not defensible.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.observation.bundles import BoundsChannelSpec, BoundsEstimationBundle
from polisyos.ir.observation.causal_execution import BoundsEstimationTask
from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
from polisyos.ir.observation.contracts import ObservationFamily
from polisyos.scientist.causal import BoundsEstimationRunner

with TemporaryDirectory(prefix="polisyos-bounds-") as tmp:
    store = FileSystemCAS(Path(tmp))
    runner = BoundsEstimationRunner(store=store)
    [entry] = runner.run([
        BoundsEstimationTask(
            task_id="bounds_demo",
            bounds_input=BoundsEstimationInput(
                outcome=[0.1, 0.2, 0.15, 0.3, 0.75, 0.8, 0.85, 0.9],
                treatment=[0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
                instrument=[0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
                selected=[1.0] * 8,
            ),
            bundle=BoundsEstimationBundle(
                channels=[
                    BoundsChannelSpec(
                        family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                        bound_strategy="selection_bounds",
                        fallback_reason="docs_demo",
                    )
                ]
            ),
            params={"has_selection": True},
        )
    ])

    print(entry.status)
    print(entry.interval)
```

## 4. Sensitivity Artifact

Sensitivity results should be persisted when they are used in downstream
governance.

```python
from polisyos.ir.analytics.sensitivity import (
    SensitivityResult,
    load_sensitivity_result,
    persist_sensitivity_result,
)

sensitivity_ref = persist_sensitivity_result(
    store,
    SensitivityResult(
        e_value=2.4,
        e_value_ci_lower=1.8,
        robustness_value=0.22,
        rosenbaum_gamma=1.6,
        interpretation="Moderately robust to unobserved confounding.",
        is_robust=True,
    ),
)

sensitivity = load_sensitivity_result(store, sensitivity_ref)
print(sensitivity.is_robust)
print(sensitivity.e_value)
```

## 5. Dynamic Treatment Regimes

Scheduling contracts live in the IR. Estimators live in the Foundry causal
catalog.

```python
from polisyos.ir.governance.policy_spec import (
    TemporalInterventionSequence,
    TemporalInterventionStep,
)

sequence = TemporalInterventionSequence(
    sequence_id="education_sequence",
    dynamic_intervention_id="education_spending_path",
    steps=[
        TemporalInterventionStep(
            step_id="step_2025",
            effective_date="2025-01-01",
            intervention_id="education_spending_increase",
            parameter_overrides={"delta_pct_gdp": 0.3},
        ),
        TemporalInterventionStep(
            step_id="step_2026",
            effective_date="2026-01-01",
            intervention_id="education_spending_increase",
            parameter_overrides={"delta_pct_gdp": 0.5},
        ),
    ],
)
```

## 6. ERGM Structural Null for Diffusion

Use the Phase 2 network-generative surface when you need a pre-treatment
structural null for diffusion or spillover diagnostics.

```python
import numpy as np

from polisyos.foundry.methods.network import (
    DiffusionNullTestEstimator,
    ERGMNullModelEstimator,
    NetworkData,
)

rng = np.random.default_rng(21)
labels = np.array([0] * 8 + [1] * 8, dtype=int)
n = labels.shape[0]
adjacency = np.zeros((n, n), dtype=float)
for i in range(n):
    for j in range(i + 1, n):
        p = 0.65 if labels[i] == labels[j] else 0.10
        edge = float(rng.uniform() < p)
        adjacency[i, j] = edge
        adjacency[j, i] = edge

state = NetworkData(
    adjacency=adjacency,
    node_features=np.column_stack([labels.astype(float), rng.normal(size=n)]),
    node_states=np.where(np.arange(n) < 3, 1.0, 0.0),
    metadata={"ergm_group_labels": labels.tolist()},
)

ergm = ERGMNullModelEstimator.pure_step(
    state,
    {"n_simulations": 16, "save_graphs": 4, "__seed__": 21},
)["result"]
null_test = DiffusionNullTestEstimator.pure_step(
    state,
    {"n_simulations": 16, "diffusion_rate": 0.35, "decay": 0.04, "__seed__": 21},
)["result"]

print(ergm.fit_status)
print(ergm.degeneracy_alarm)
print(null_test.p_value)
```

Treat this as a pre-treatment structural-null workflow. If `degeneracy_alarm` is
raised, do not interpret the diffusion-null result as strong evidence without
revisiting the graph specification or fit diagnostics.

## 7. SBM Strata for Interference-Aware Causal Design

Use SBM strata as a design-stage object only: fit on the pre-treatment network
and pre-treatment node covariates, then bridge the labels into the existing
`cluster_id`-based interference estimators.

```python
import numpy as np

from polisyos.foundry.methods.causal import (
    PartialInterferenceEstimator,
    build_block_stratified_network_causal_data,
)
from polisyos.foundry.methods.network import NetworkData, SBMStratificationEstimator

rng = np.random.default_rng(9)
truth = np.array([0] * 12 + [1] * 12, dtype=int)
n = truth.shape[0]
adjacency = np.zeros((n, n), dtype=float)
for i in range(n):
    for j in range(i + 1, n):
        p = 0.75 if truth[i] == truth[j] else 0.08
        edge = float(rng.uniform() < p)
        adjacency[i, j] = edge
        adjacency[j, i] = edge

node_features = np.column_stack(
    [truth.astype(float) + rng.normal(scale=0.08, size=n), rng.normal(size=n)]
)
treatment = rng.binomial(1, 0.5, size=n).astype(float)
outcome = 1.1 * treatment + rng.normal(scale=0.25, size=n)

network_state = NetworkData(adjacency=adjacency, node_features=node_features)
strata = SBMStratificationEstimator.pure_step(
    network_state,
    {
        "n_blocks": 2,
        "bootstrap_samples": 6,
        "covariate_scale": 0.5,
        "min_block_size": 4,
        "__seed__": 9,
    },
)["result"]

causal_data, bridge = build_block_stratified_network_causal_data(
    outcome=outcome,
    treatment=treatment,
    covariates=node_features,
    adjacency_matrix=adjacency,
    stratification=strata,
)

report = PartialInterferenceEstimator.pure_step(
    causal_data,
    {"alpha_high": 0.5, "alpha_low": 0.0, "alpha_bandwidth": 0.2},
)["result"]

print(bridge.positivity_passed)
print(strata.stability["overall_stability"])
print(report.direct_effect)
```

If the bridge reports low support or unstable assignments, merge or simplify the
design strata before interpreting partial-interference estimates.

## 8. Strategic Response

Strategic-response compute lives in
`polisyos.foundry.methods.catalog.causal.strategic`; Scientist readiness wraps
that evidence for policy governance.

Use this path when a policy can trigger agent adaptation, equilibrium selection,
or performative shifts. Do not treat a static treatment effect as deployment
evidence when strategic response is required by the governance profile.

## Rollback

- if a demo change was exploratory and should not become part of the supported
  causal surface, revert the snippet or helper before updating reference docs;

- if a new method requires broader governance semantics than this page assumes,
  move the workflow into Scientist-oriented docs instead of stretching this
  how-to beyond its scope.

## Troubleshooting

- If discovery examples hang or fork badly on your host, move them into a normal
  `.py` file and use the platform-appropriate `__main__` guard.

- If identification returns a non-identified status, treat that as a modeling
  result, not necessarily as a code failure.

- If you need policy-facing evidence, bounds/sensitivity artifacts should be
  persisted and passed forward rather than read only from notebook memory.

## Validation Anchors

Run focused tests for the surfaces above:

```bash
uv run pytest \
  tests/foundry/methods/catalog/causal/test_discovery_pipeline.py \
  tests/foundry/methods/catalog/causal/test_causal_engine.py \
  tests/foundry/methods/catalog/causal/test_bounds_engine.py \
  tests/foundry/methods/catalog/network/test_ergm.py \
  tests/foundry/methods/catalog/network/test_sbm.py \
  tests/foundry/methods/catalog/network/test_diffusion_null.py \
  tests/foundry/methods/catalog/network/test_block_causal_bridge.py \
  tests/foundry/methods/catalog/causal/test_sensitivity_metrics.py \
  tests/foundry/methods/catalog/causal/test_dtr.py \
  tests/foundry/methods/catalog/causal/test_strategic.py \
  tests/ir/analytics/test_network_generative.py -q
```

For the full architecture rationale, read
[Causal Engine](../explanation/causal-engine.md).
