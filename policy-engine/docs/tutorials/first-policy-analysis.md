# Первый policy-анализ

Related references: [Compile Execute](../reference/foundry/compile-execute.md), [Scientist Workflows](../reference/scientist/workflows.md), [Problem Framing](../reference/ir/problem-framing.md).

> Практический первый проход по текущей analytical surface в PolicyOS: сформулировать задачу, привязать данные World Bank и проверить локальный execution toolchain.

!!! info "Verified with"
Эта страница была перепроверена 2026-04-17 на текущем дереве, macOS,
Python 3.14 и `uv`.
Были реально проверены импорты
`ProblemFrame` / `PolicySpec` / `ModelSpec`,
`WorldBankConnector`,
`run_trivial_compile_execute`
и `run_experiment`.

!!! info "Важное замечание про форму модели"
В текущей схеме `ProblemFrame` нет полей вида `outcome_kpi`, `treatment`,
`entity_scope=EntityScope(region_codes=[...])` или `temporal_window=(...)`.
В проверенном коде эта семантика разделена между:
`ProblemFrame` для целей и KPI,
`PolicySpec` для интервенций и таргетинга по регионам,
Fabric-запросами для выбора страны и периода,
и causal-observation contracts для деталей идентификации.

## Поток в текущем дереве

В текущем D4 workflow первый анализ лучше читать как один и тот же поток через
четыре слоя:

1. IR / Trinity:
   `ProblemFrame`, `PolicySpec` и `ModelSpec` собираются в `TrinityBundle`.
2. Fabric:
   данные приходят через connector и превращаются в `data_snapshot_ref`.
3. Foundry:
   `compile_program()` и `execute()` подтверждают, что bundle и bindings реально
   проходят compile/execute путь.
4. Scientist:
   тот же `trinity_bundle_ref`, `registry_bundle_ref` и `data_snapshot_ref`
   передаются в `run_experiment()`, если нужен governed или causal workflow.

## Постановка задачи

Мы хотим понять, связано ли увеличение государственных расходов на образование с более высоким GDP growth в Украине в период 2015-2023, а затем связать эту аналитическую постановку с текущими causal и execution-поверхностями PolicyOS.

## Шаг 1: определить `ProblemFrame`

Используйте реальные поля из `polisyos.ir.governance.problem_frame`:

```python
from polisyos.ir import KPISpec, ProblemDomain, ProblemFrame
from polisyos.ir.governance.problem_frame import ObjectiveSpec
from polisyos.ir.types import OptimizationDirection

frame = ProblemFrame(
    problem_id="ukr_education_growth",
    domain=ProblemDomain.EDUCATION,
    kpis=[
        KPISpec(
            kpi_id="gdp_growth",
            metric_id="gdp_growth",
            direction=OptimizationDirection.MAXIMIZE,
        )
    ],
    objectives=[
        ObjectiveSpec(
            objective_id="increase_growth",
            metric_id="gdp_growth",
            direction=OptimizationDirection.MAXIMIZE,
            kpi_refs=["gdp_growth"],
        )
    ],
)
```

Что означают поля в текущей схеме:

- `problem_id`: стабильный идентификатор задачи
- `domain`: крупная policy-область; здесь `ProblemDomain.EDUCATION`
- `kpis`: измеримые outcomes, которые мы хотим улучшить
- `objectives`: optimization goals, привязанные к KPI

В текущей версии репозитория страна и временное окно не лежат прямо в `ProblemFrame`. Мы переносим их в data query и в policy metadata.

## Шаг 2: создать `PolicySpec`

Используйте реальные `PolicySpec` и governance `InterventionSpec`:

```python
from decimal import Decimal

from polisyos.ir import PolicySpec
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.types import SelectorOperator

spec = PolicySpec(
    policy_id="education_spending_increase",
    interventions=[
        InterventionSpec(
            intervention_id="education_spending_increase",
            kind="education_spending_increase",
            target=SelectorPredicate(
                field="country",
                operator=SelectorOperator.EQUALS,
                value="UKR",
            ),
            schedule=ScheduleSpec(start_step=0, duration_steps=1),
            params={"delta_pct_gdp": Decimal("0.5")},
            target_region_ids=["UKR"],
            notes=["Analytical framing object; execution smoke uses a registry-backed mechanism below."],
        )
    ],
)
```

Ключевые текущие поля:

- `kind`: семейство интервенции
- `target`: selector expression
- `schedule`: step-based окно активации
- `params`: параметры интервенции
- `target_region_ids`: региональная metadata, идущая вместе с интервенцией

## Шаг 3: привязать данные через Fabric

Используйте production `WorldBankConnector` и реальные indicator codes:

- GDP growth, annual percent: `NY.GDP.MKTP.KD.ZG`
- Government expenditure on education, percent of GDP: `SE.XPD.TOTL.GD.ZS`

```python
import asyncio

from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources import WorldBankConnector
from polisyos.ir.connectors import FetchRequest


async def fetch_world_bank_panel():
    connector = WorldBankConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url="https://api.worldbank.org/v2",
            timeout_seconds=15,
        )
    )
    try:
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="NY.GDP.MKTP.KD.ZG;SE.XPD.TOTL.GD.ZS",
                filters=(("country", ("UKR",)),),
                page_size=500,
            ),
        )
        frame = result.data.copy()
        frame = frame[frame["date"].astype(int).between(2015, 2023)]
        return frame.sort_values(["indicator_id", "date"])
    finally:
        await connector.disconnect(handle)


panel = asyncio.run(fetch_world_bank_panel())
print(panel[["country_code", "indicator_id", "date", "value"]].tail())
```

На выходе вы получаете raw country-year panel. В текущем дереве treatment/outcome semantics задаются кодом анализа, а не зашиваются напрямую в `ProblemFrame`.

## Шаг 4: compile и execute

!!! warning
Текущий Trinity linker компилирует только registry-backed mechanism и metric ids.
Богато аннотированный аналитический `ProblemFrame`, как выше, полезен для анализа,
но сам по себе пока не является гарантированным compile target.
Поэтому проверенный compile/execute путь ниже использует минимальный registry-backed smoke bundle,
а analytical framing и Fabric panel остаются отдельным слоем.

```python
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry import compile_program, execute
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir import ModelSpec, ProblemDomain, ProblemFrame, PolicySpec
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator

with TemporaryDirectory(prefix="polisyos-first-analysis-") as tmp:
    store = FileSystemCAS(Path(tmp))
    registry = build_default_registry_bundle(store)
    load_registry_bundle_content(store, registry.bundle_ref)

    execution_bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="execution_smoke",
            domain=ProblemDomain.EDUCATION,
        ),
        policy_spec=PolicySpec(
            policy_id="execution_smoke_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="execution_smoke_intervention",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.02")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="execution_smoke_model",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )

    policy_ref = store.put_json(
        execution_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle",
                version=execution_bundle.schema_version,
            ),
        ),
    )

    compile_result = compile_program(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
        ),
    )

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)

    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )

    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )

    exec_result = execute(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(
                artifact_id=input_bindings_ref.artifact_id
            ),
            registry_bundle_ref=registry.bundle_ref,
        ),
    )

    print("compile_ok:", compile_result.ok)
    print("execute_ok:", exec_result.ok)
```

## Шаг 5: чтение результатов

После шагов выше обычно читают четыре типа результатов:

- Causal graph:
  - discovery pipelines возвращают `DiscoveryPipelineReport` с `unified_pag`
  - дальше поверх этого графа можно запускать identification
- Effect estimates:
  - point-ID пути дают estimands и effect reports вроде ATE/CATE
  - partial-ID пути дают bounds bundles и интервалы
- Backtest metrics:
  - historical validation живёт в `BacktestPlanBundle` и связанных governance runners
- Sensitivity diagnostics:
  - robustness outputs обычно приходят как `sensitivity_result`
  - specification-curve данные упакованы в `SpecificationCurveBundle`

Для первого walkthrough самые простые concrete outputs для просмотра:

- World Bank panel, который вы получили через Fabric
- `compile_ok` / `execute_ok` из Foundry smoke path
- CAS artifacts, созданные execution smoke run

## Шаг 6: передайте тот же bundle в Scientist

`run_experiment()` — это orchestration boundary поверх того же Trinity/Fabric
контекста. В примере выше `policy_ref` уже указывает на `ir.trinity_bundle`, а
`data_snapshot_ref` и `registry.bundle_ref` готовы для Scientist.

```python
from polisyos.scientist import run_experiment

scientist_state = run_experiment(
    {
        "run_id": "R_first_analysis",
        "execution_profile": "research",
        "inputs": {
            "trinity_bundle_ref": policy_ref.model_dump(mode="json"),
            "registry_bundle_ref": registry.bundle_ref.model_dump(mode="json"),
            "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
        },
        "params": {
            "workflow_id": "scientist_causal_full",
            "policy_request": (
                "Estimate whether higher public education spending is associated "
                "with stronger GDP growth in Ukraine between 2015 and 2023."
            ),
        },
    },
    store=store,
)

print("artifact_keys:", sorted(scientist_state["artifacts_index"])[:5])
print("report_keys:", sorted(scientist_state["reports_index"])[:5])
```

Практические правила маршрутизации:

- если у вас уже есть `trinity_bundle_ref` и нужен baseline governed path, можно
  опустить `workflow_id` и дать `run_experiment()` выбрать `scientist_default`;

- если нужен явный causal escalation path, задайте
  `params.workflow_id="scientist_causal_full"` или `execution_profile="research"`;

- если у вас только policy question и ещё нет Trinity bundle, используйте
  verified-policy path, описанный в [Scientist Workflows](../reference/scientist/workflows.md).

## Полный код

Для стабильного запуска на Apple Silicon лучше явно переключить JAX на CPU:

```bash
JAX_PLATFORM_NAME=cpu JAX_PLATFORMS=cpu python first_policy_analysis.py
```

Скрипт ниже — самый практичный copy-pasteable вариант для текущего дерева. Он сначала пробует World Bank, потом падает обратно на маленький synthetic panel, если сеть недоступна, и затем запускает проверенный путь `compile_program` + `execute`.

```python
import asyncio
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources import WorldBankConnector
from polisyos.foundry import compile_program, execute
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir import KPISpec, ModelSpec, ProblemDomain, ProblemFrame, PolicySpec
from polisyos.ir.connectors import FetchRequest
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import OptimizationDirection, SelectorOperator


async def load_panel() -> tuple[pd.DataFrame, str]:
    connector = WorldBankConnector()
    handle = await connector.connect(
        ConnectionConfig(url="https://api.worldbank.org/v2", timeout_seconds=15)
    )
    try:
        result = await connector.fetch(
            handle,
            FetchRequest(
                dataset_id="NY.GDP.MKTP.KD.ZG;SE.XPD.TOTL.GD.ZS",
                filters=(("country", ("UKR",)),),
                page_size=500,
            ),
        )
        frame = result.data.copy()
        frame = frame[frame["date"].astype(int).between(2015, 2023)]
        frame = frame.sort_values(["indicator_id", "date"])
        return frame, "world_bank"
    except Exception as exc:
        return (
            pd.DataFrame(
                [
                    {
                        "country_code": "UKR",
                        "indicator_id": "NY.GDP.MKTP.KD.ZG",
                        "date": "2019",
                        "value": 3.2,
                    },
                    {
                        "country_code": "UKR",
                        "indicator_id": "NY.GDP.MKTP.KD.ZG",
                        "date": "2020",
                        "value": -3.8,
                    },
                    {
                        "country_code": "UKR",
                        "indicator_id": "SE.XPD.TOTL.GD.ZS",
                        "date": "2019",
                        "value": 5.4,
                    },
                    {
                        "country_code": "UKR",
                        "indicator_id": "SE.XPD.TOTL.GD.ZS",
                        "date": "2020",
                        "value": 5.8,
                    },
                ]
            ),
            f"synthetic_fallback ({type(exc).__name__})",
        )
    finally:
        await connector.disconnect(handle)


async def main() -> None:
    frame = ProblemFrame(
        problem_id="ukr_education_growth",
        domain=ProblemDomain.EDUCATION,
        kpis=[
            KPISpec(
                kpi_id="gdp_growth",
                metric_id="gdp_growth",
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
        objectives=[
            ObjectiveSpec(
                objective_id="increase_growth",
                metric_id="gdp_growth",
                direction=OptimizationDirection.MAXIMIZE,
                kpi_refs=["gdp_growth"],
            )
        ],
    )

    spec = PolicySpec(
        policy_id="education_spending_increase",
        interventions=[
            InterventionSpec(
                intervention_id="education_spending_increase",
                kind="education_spending_increase",
                target=SelectorPredicate(
                    field="country",
                    operator=SelectorOperator.EQUALS,
                    value="UKR",
                ),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"delta_pct_gdp": Decimal("0.5")},
                target_region_ids=["UKR"],
            )
        ],
    )

    panel, panel_source = await load_panel()
    print("panel_source:", panel_source)
    print("analysis_problem:", frame.problem_id)
    print("analysis_policy:", spec.policy_id)
    print("panel_tail_rows:", len(panel[["country_code", "indicator_id", "date", "value"]].tail(4)))
    print(panel[["country_code", "indicator_id", "date", "value"]].tail(4).to_string(index=False))

    with TemporaryDirectory(prefix="polisyos-first-analysis-") as tmp:
        store = FileSystemCAS(Path(tmp))
        registry = build_default_registry_bundle(store)
        load_registry_bundle_content(store, registry.bundle_ref)

        execution_bundle = TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="execution_smoke",
                domain=ProblemDomain.EDUCATION,
            ),
            policy_spec=PolicySpec(
                policy_id="execution_smoke_policy",
                interventions=[
                    InterventionSpec(
                        intervention_id="execution_smoke_intervention",
                        kind="income_tax",
                        target=SelectorPredicate(
                            field="id",
                            operator=SelectorOperator.EQUALS,
                            value="all",
                        ),
                        schedule=ScheduleSpec(start_step=0, duration_steps=1),
                        params={"rate": Decimal("0.02")},
                    )
                ],
            ),
            model_spec=ModelSpec(
                model_id="execution_smoke_model",
                data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                registry_bundle_ref=str(registry.bundle_ref.artifact_id),
            ),
        )

        policy_ref = store.put_json(
            execution_bundle,
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.TrinityBundle",
                    version=execution_bundle.schema_version,
                ),
            ),
        )

        compile_result = compile_program(
            store,
            CompileRequest(
                input_kind="trinity",
                policy_ref=policy_ref,
                registry_bundle_ref=registry.bundle_ref,
            ),
        )

        base_state = GlobalState.empty(n_agents=2, n_firms=1)
        snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
        state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)

        data_snapshot_ref = store.put_json(
            DataSnapshot(data_ref=state_snapshot_ref),
            PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
        )

        input_bindings_ref = store.put_json(
            FoundryInputBindings(
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry.bundle_ref,
                rules=[],
                bound_state_snapshot_ref=state_snapshot_ref,
            ),
            PutOptions(kind="foundry.input_bindings", media_type="application/json"),
        )

        exec_result = execute(
            store,
            ExecuteRequest(
                exec_plan_ref=compile_result.exec_plan_ref,
                input_bindings_ref=FoundryInputBindingsRef(
                    artifact_id=input_bindings_ref.artifact_id
                ),
                registry_bundle_ref=registry.bundle_ref,
            ),
        )

        print("compile_ok:", compile_result.ok)
        print("execute_ok:", exec_result.ok)
        print("exec_plan_artifact:", compile_result.exec_plan_ref.artifact_id)
        print("simulation_result_artifact:", exec_result.simulation_result_ref.artifact_id)


if __name__ == "__main__":
    asyncio.run(main())
```

Ожидаемый вывод из реального запуска:

```text
panel_source: synthetic_fallback (RetryExhaustedError)
analysis_problem: ukr_education_growth
analysis_policy: education_spending_increase
panel_tail_rows: 4
country_code         indicator_id date  value
         UKR NY.GDP.MKTP.KD.ZG 2019    3.2
         UKR NY.GDP.MKTP.KD.ZG 2020   -3.8
         UKR SE.XPD.TOTL.GD.ZS 2019    5.4
         UKR SE.XPD.TOTL.GD.ZS 2020    5.8
compile_ok: True
execute_ok: True
exec_plan_artifact: sha256:0e86d9c8545e9c188b9dbb855739161926fb568ed73dfa5b28cf4249319bcc1f
simulation_result_artifact: sha256:bb034dfbb3680d3cdf33315964fccdb80b105eff6eeab9463993de043afdba77
```

В нормальном networked-окружении строка `panel_source` может быть `world_bank`, а не synthetic fallback, но остальная структура сценария не меняется.

## Что дальше

- [Getting Started](getting-started.md) — самый маленький Foundry smoke
- [Run Causal Analysis](../how-to/run-causal-analysis.md) — новые causal runner API
- [Installation](../how-to/install.md) — extras и runtime/causal setup
- [Scientist Workflows](../reference/scientist/workflows.md) — routing и required binds
