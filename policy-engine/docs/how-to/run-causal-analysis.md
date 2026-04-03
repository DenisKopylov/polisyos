# Запуск causal analysis

> Используйте текущие discovery, identification, bounds, sensitivity, DTR и strategic-response поверхности в проверенном коде.

## 1. Causal Discovery Pipeline

Текущий discovery stack находится в:

- `src/polisyos/foundry/methods/catalog/causal/discovery_pipeline.py`
- `src/polisyos/foundry/methods/catalog/causal/constraint_discovery.py`
- `src/polisyos/foundry/methods/catalog/causal/dagma_discovery.py`

Публичная unified discovery entry point:

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
    {
        "force_algorithms": ["pc"],
        "significance_level": 0.05,
    },
)["report"]

pag = report.unified_pag
print(pag.graph_type)
print(pag.nodes)
```

Что делает этот пример:

- идёт через текущий unified discovery API
- принудительно использует constraint-based PC path для детерминированного docs-примера
- возвращает `DiscoveryPipelineReport`, в котором `unified_pag` уже готов для identification

!!! note
    На macOS и Python 3.14 discovery-методы с multiprocessing надёжнее запускать из обычного `.py` файла с нормальным `if __name__ == "__main__":`.
    Запуск через `python - <<'PY'` может падать, потому что spawned workers пытаются переимпортировать `<stdin>`.

## 2. Causal Identification

Identification engine находится в:

```text
src/polisyos/foundry/methods/catalog/causal/id_engine.py
```

Текущий status enum:

- `IDENTIFIED`
- `HEDGE_FOUND`
- `PAG_AMBIGUOUS`
- `ORACLE_NEEDED`
- `NOT_RECOVERABLE`

Текущий observation-layer enum `IdentificationMode`:

- `point_identified`
- `partially_identified`
- `bounds_only`
- `proxy_identified`
- `interference_aware`
- `sequential`

Минимальный пример:

```python
from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType

graph = CausalGraphModel(
    graph_type=GraphType.DAG,
    nodes=["X", "Y"],
    edges=[CausalEdge(src="X", dst="Y")],
)

identified = id_algorithm(
    treatment={"X"},
    outcome={"Y"},
    graph=graph,
)
print(identified.status)
print(identified.estimand_ast is not None)
```

Именно этот engine покрывает:

- back-door identification
- front-door identification
- IV-like strategies, если граф и запрос это позволяют

Связанный proxy и measurement-error код находится в:

```text
src/polisyos/foundry/methods/catalog/causal/measurement_error.py
```

## 3. Bounds Estimation

Новый bounds-oriented execution surface находится в:

- `src/polisyos/foundry/methods/catalog/causal/bounds_engine.py`
- `src/polisyos/scientist/causal/execution.py`

Programmatic runner:

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
    task = BoundsEstimationTask(
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

    [entry] = runner.run([task])
    print(entry.status)
    print(entry.interval)
    print(entry.width)
    print(entry.bounds_bundle_ref)
```

Ожидаемый вывод из реального запуска:

```text
ok
(0.6375, 0.6375)
0.0
artifact_id=ArtifactID(root='sha256:...') kind='ir.bounds_bundle' media_type='application/json'
```

## 4. Sensitivity Analysis

Здесь сейчас важны две поверхности:

- `SpecificationCurveBundle` в `polisyos.ir.observation.bundles`
- `SensitivityResult` в `polisyos.ir.analytics.sensitivity`

Самый portable programmatic path — сохранить и потом загрузить `SensitivityResult` как artifact:

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
print(sensitivity.rosenbaum_gamma)
```

Что обычно смотрят downstream:

- `sensitivity_result.is_robust`
- `sensitivity_result.e_value`
- `sensitivity_result.rosenbaum_gamma`
- `SpecificationCurveBundle`, если нужен structured specification-curve sweep

## 5. Dynamic Treatment Regimes (DTR)

Сейчас есть два важных слоя.

IR scheduling objects:

- `TemporalInterventionSequence`
- `TemporalInterventionStep`

Method implementations:

- `QLearningDTR`
- `ALearningDTR`
- `DoublyRobustDTR`
- `estimate_dtr_trajectory`
- `OptimalPolicyLearner` для budget-constrained targeting и policy learning

Пример scheduling-объекта:

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

## 6. Strategic Response

Strategic-response modeling живёт в:

- `src/polisyos/foundry/methods/catalog/causal/strategic.py`
- `src/polisyos/scientist/causal/readiness.py`

Проверенный runner example:

```python
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.strategic import FiniteStrategicPayoffTable, StrategicSCM
from polisyos.ir.observation.bundles import StrategicResponseSpecsBundle
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.causal import StrategicResponseRunner
from polisyos.scientist.kernel.budgets import ComputeBudget


def artifact_ref(seed: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}",
            "kind": kind,
            "media_type": "application/json",
        }
    )


with TemporaryDirectory(prefix="polisyos-strategic-") as tmp:
    store = FileSystemCAS(Path(tmp))
    runner = StrategicResponseRunner(
        store=store,
        causal_component_ref=artifact_ref("causal", "ir.causal_effect_report"),
        run_metadata={"run_id": "docs_demo"},
    )

    action_spaces = {"leader": ("low", "high"), "follower": ("stay", "switch")}
    payload = {
        "baseline_policy_value": 5.0,
        "strategic_scm": StrategicSCM(
            base_graph_ref=artifact_ref("graph", "ir.causal_graph_model"),
            strategic_agents=("leader", "follower"),
            utility_refs={
                "leader": artifact_ref("leader-payoff", "ir.strategic_payoff_table"),
                "follower": artifact_ref("follower-payoff", "ir.strategic_payoff_table"),
            },
            policy_rule_ref=artifact_ref("policy", "ir.policy_recommendation"),
            equilibrium_concept="stackelberg",
            compute_budget=ComputeBudget(
                max_llm_calls=0.0,
                max_sim_runs=16.0,
                max_wall_time_s=30.0,
            ),
        ).model_dump(mode="json"),
        "strategic_payoff_tables": {
            "leader": FiniteStrategicPayoffTable(
                agent="leader",
                strategic_agents=("leader", "follower"),
                action_spaces=action_spaces,
                payoffs={
                    "leader=low|follower=stay": 1.0,
                    "leader=low|follower=switch": 0.0,
                    "leader=high|follower=stay": 2.0,
                    "leader=high|follower=switch": 3.0,
                },
            ).model_dump(mode="json"),
            "follower": FiniteStrategicPayoffTable(
                agent="follower",
                strategic_agents=("leader", "follower"),
                action_spaces=action_spaces,
                payoffs={
                    "leader=low|follower=stay": 2.0,
                    "leader=low|follower=switch": 1.0,
                    "leader=high|follower=stay": 0.0,
                    "leader=high|follower=switch": 3.0,
                },
            ).model_dump(mode="json"),
        },
    }

    [entry] = runner.run(
        StrategicResponseSpecsBundle(
            expectations=[
                {
                    "intervention_kind": "procurement_threshold_change",
                    "channels": ["procurement_channel"],
                }
            ]
        ),
        channel_payloads={"procurement_channel": payload},
    )

    print(entry.status)
    print(entry.fallback_mode)
    print(entry.performative_shift)
    print(entry.strategic_response_bundle_ref)
```

Ожидаемый вывод из реального запуска:

```text
ready
exact_equilibrium
3.0
artifact_id=ArtifactID(root='sha256:...') kind='ir.strategic_response_bundle' media_type='application/json'
```

## 7. Полный workflow

Скрипт ниже — минимальный проверенный end-to-end walkthrough для текущего дерева. Он выполняет:

1. discovery
2. identification
3. bounds estimation
4. сохранение и загрузку sensitivity artifact
5. strategic response
6. governance pass поверх итогового strategic summary

```python
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
from polisyos.foundry.methods.catalog.causal.protocols import UnifiedDiscoveryData
from polisyos.ir.analytics.sensitivity import (
    SensitivityResult,
    load_sensitivity_result,
    persist_sensitivity_result,
)
from polisyos.ir.analytics.strategic import FiniteStrategicPayoffTable, StrategicSCM
from polisyos.ir.observation.bundles import (
    BoundsChannelSpec,
    BoundsEstimationBundle,
    StrategicResponseSpecsBundle,
)
from polisyos.ir.observation.causal_execution import BoundsEstimationTask
from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.causal import BoundsEstimationRunner, StrategicResponseRunner
from polisyos.scientist.governance.passes.strategic_response_pass import StrategicResponsePass
from polisyos.scientist.kernel.budgets import ComputeBudget


def artifact_ref(seed: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}",
            "kind": kind,
            "media_type": "application/json",
        }
    )


def main() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(size=200)
    y = 0.8 * x + rng.normal(scale=0.1, size=200)
    z = 0.5 * x + 0.5 * y + rng.normal(scale=0.1, size=200)

    discovery_state = UnifiedDiscoveryData(
        data=np.column_stack([x, y, z]),
        variable_names=["X", "Y", "Z"],
    )
    discovery_report = UnifiedCausalDiscovery.pure_step(
        discovery_state,
        {"force_algorithms": ["pc"], "significance_level": 0.05},
    )["report"]
    graph = discovery_report.unified_pag

    identified = id_algorithm(
        treatment={"X"},
        outcome={"Y"},
        graph=graph,
    )

    with TemporaryDirectory(prefix="polisyos-causal-docs-") as tmp:
        store = FileSystemCAS(Path(tmp))

        [bounds_entry] = BoundsEstimationRunner(store=store).run(
            [
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
            ]
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

        strategic_runner = StrategicResponseRunner(
            store=store,
            causal_component_ref=artifact_ref("causal", "ir.causal_effect_report"),
            run_metadata={"run_id": "docs_demo"},
        )

        action_spaces = {"leader": ("low", "high"), "follower": ("stay", "switch")}
        strategic_payload = {
            "baseline_policy_value": 5.0,
            "strategic_scm": StrategicSCM(
                base_graph_ref=artifact_ref("graph", "ir.causal_graph_model"),
                strategic_agents=("leader", "follower"),
                utility_refs={
                    "leader": artifact_ref("leader-payoff", "ir.strategic_payoff_table"),
                    "follower": artifact_ref("follower-payoff", "ir.strategic_payoff_table"),
                },
                policy_rule_ref=artifact_ref("policy", "ir.policy_recommendation"),
                equilibrium_concept="stackelberg",
                compute_budget=ComputeBudget(
                    max_llm_calls=0.0,
                    max_sim_runs=16.0,
                    max_wall_time_s=30.0,
                ),
            ).model_dump(mode="json"),
            "strategic_payoff_tables": {
                "leader": FiniteStrategicPayoffTable(
                    agent="leader",
                    strategic_agents=("leader", "follower"),
                    action_spaces=action_spaces,
                    payoffs={
                        "leader=low|follower=stay": 1.0,
                        "leader=low|follower=switch": 0.0,
                        "leader=high|follower=stay": 2.0,
                        "leader=high|follower=switch": 3.0,
                    },
                ).model_dump(mode="json"),
                "follower": FiniteStrategicPayoffTable(
                    agent="follower",
                    strategic_agents=("leader", "follower"),
                    action_spaces=action_spaces,
                    payoffs={
                        "leader=low|follower=stay": 2.0,
                        "leader=low|follower=switch": 1.0,
                        "leader=high|follower=stay": 0.0,
                        "leader=high|follower=switch": 3.0,
                    },
                ).model_dump(mode="json"),
            },
        }

        [strategic_entry] = strategic_runner.run(
            StrategicResponseSpecsBundle(
                expectations=[
                    {
                        "intervention_kind": "procurement_threshold_change",
                        "channels": ["procurement_channel"],
                    }
                ]
            ),
            channel_payloads={"procurement_channel": strategic_payload},
        )

        strategic_summary = {
            "fallback_mode": getattr(
                strategic_entry.fallback_mode,
                "value",
                str(strategic_entry.fallback_mode),
            ),
            "equilibrium_selection_dependence": "deterministic",
            "multiplicity_note": None,
        }
        governance_issues = StrategicResponsePass().validate(
            PassContext(
                ir=None,
                state={
                    "strategic_response": strategic_summary,
                    "strategic_response_required": True,
                },
                registry_bundle=None,
                profile=ValidationProfile.mvp(),
                run_id="docs_demo",
            )
        )

        print("DISCOVERY_GRAPH_TYPE", graph.graph_type)
        print("DISCOVERY_NODES", graph.nodes)
        print("IDENT_STATUS", identified.status)
        print("IDENT_HAS_ESTIMAND", identified.estimand_ast is not None)
        print("IDENT_MODE", IdentificationMode.POINT_IDENTIFIED.value)
        print("BOUNDS_STATUS", bounds_entry.status)
        print("BOUNDS_INTERVAL", bounds_entry.interval)
        print("SENSITIVITY_ROBUST", sensitivity.is_robust)
        print("SENSITIVITY_E_VALUE", sensitivity.e_value)
        print("STRATEGIC_STATUS", strategic_entry.status)
        print("STRATEGIC_FALLBACK", strategic_entry.fallback_mode)
        print("STRATEGIC_SHIFT", strategic_entry.performative_shift)
        print("GOVERNANCE_ISSUES", len(governance_issues))
        print(
            "GOVERNANCE_BLOCKERS",
            sum(1 for issue in governance_issues if issue.severity.value == "blocker"),
        )


if __name__ == "__main__":
    main()
```

Ожидаемый вывод из реального запуска:

```text
DISCOVERY_GRAPH_TYPE GraphType.PAG
DISCOVERY_NODES ['X', 'Y', 'Z']
IDENT_STATUS IdentificationStatus.IDENTIFIED
IDENT_HAS_ESTIMAND True
IDENT_MODE point_identified
BOUNDS_STATUS ok
BOUNDS_INTERVAL (0.6375, 0.6375)
SENSITIVITY_ROBUST True
SENSITIVITY_E_VALUE 2.4
STRATEGIC_STATUS ready
STRATEGIC_FALLBACK exact_equilibrium
STRATEGIC_SHIFT 3.0
GOVERNANCE_ISSUES 0
GOVERNANCE_BLOCKERS 0
```

## Связанные модули

- `foundry/methods/catalog/causal/discovery_pipeline.py`
- `foundry/methods/catalog/causal/constraint_discovery.py`
- `foundry/methods/catalog/causal/dagma_discovery.py`
- `foundry/methods/catalog/causal/id_engine.py`
- `foundry/methods/catalog/causal/bounds_engine.py`
- `foundry/methods/catalog/causal/measurement_error.py`
- `foundry/methods/catalog/causal/policy_learning.py`
- `foundry/methods/catalog/causal/dtr.py`
- `foundry/methods/catalog/causal/strategic.py`
- `scientist/causal/execution.py`
- `scientist/causal/readiness.py`
