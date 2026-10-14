# Первый policy-анализ: демонстрации и границы

Related references: [Compile Execute](../reference/foundry/compile-execute.md), [Scientist Workflows](../reference/scientist/workflows.md), [Problem Framing](../reference/ir/problem-framing.md).

> Учебная карта нескольких раздельных surfaces, а не функциональный end-to-end policy-анализ.
> Ни один шаг здесь не выводит причинный эффект, допустимую рекомендацию или publishable result.

!!! info "Основание этого обновления (2026-10-14)"
    Source inspected at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; production implementation under
    `src/polisyos/` после этого pin не менялась. Кодовые и test entrypoints прочитаны, но tests,
    snippets, package build, runtime, provider/network calls и services для этого docs refresh не запускались.

!!! note "Историческая запись от 2026-04-17"
    Предыдущая редакция отмечала проверку imports `ProblemFrame` / `PolicySpec` / `ModelSpec`,
    `WorldBankConnector`, `run_trivial_compile_execute` и `run_experiment` на тогдашнем дереве,
    macOS, Python 3.14 и `uv`. Она не фиксировала выполнение полного walkthrough. Дата остаётся
    исторической и не обозначает проверку источника или запуск в этом обновлении.

!!! info "Важное замечание про форму модели"
    В source snapshot выше `ProblemFrame` нет полей вида `outcome_kpi`, `treatment`,
    `entity_scope=EntityScope(region_codes=[...])` или `temporal_window=(...)`.
    В просмотренном source эта семантика разделена между:
    `ProblemFrame` для целей и KPI,
    `PolicySpec` для интервенций и таргетинга по регионам,
    Fabric-запросами для выбора страны и периода,
    и causal-observation contracts для деталей идентификации.

## Три независимые части walkthrough

Примеры ниже не образуют один связанный run:

1. **Демонстрация постановки:** `ProblemFrame` / `PolicySpec` описывают вопрос об образовании,
   а отдельный optional World Bank fetch возвращает raw country-year observations.
2. **Ограниченный Foundry smoke:** другой `TrinityBundle` с registry-backed `income_tax`
   механизмом и синтетическим пустым `GlobalState` иллюстрирует compile → execute.
3. **Draft Scientist handoff:** предполагаемая передача education question/data в Scientist
   остаётся непроверенной и в данном примере заблокирована отсутствующими связями между этими
   объектами.

Успех smoke не связывает World Bank panel с моделью, не проверяет causal identification и не
подтверждает admissibility, authority или publishability policy claim.

## Постановка задачи

Учебная постановка: проверить, как исследователь мог бы изучать связь государственных расходов
на образование и GDP growth в Украине в 2015–2023 годах. Сам вопрос и KPI — только candidate
framing: этот tutorial не оценивает связь и не утверждает, что policy intervention вызвала рост.

## Шаг 1: определить `ProblemFrame`

Используйте реальные поля из `polisyos.ir.governance.problem_frame`:

```python
from polisyos.ir import KPISpec, ProblemDomain, ProblemFrame
from polisyos.ir.governance.problem_frame import ObjectiveSpec
from polisyos.ir.model_layer.types import OptimizationDirection

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

Этот объект служит framing-примером и не передаётся в Foundry smoke ниже. Создание объекта не
подтверждает регистрацию механизма `education_spending_increase` или его исполнимость.

## Шаг 2: создать `PolicySpec`

Используйте реальные `PolicySpec` и governance `InterventionSpec`:

```python
from decimal import Decimal

from polisyos.ir import PolicySpec
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator

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

При доступном API этот шаг показывает raw country-year panel. Он не превращает observations в
causal evidence, не связывает их с intervention из шага 2 и не вычисляет treatment effect. В
этом docs refresh запрос к World Bank не выполнялся.

## Шаг 4: compile и execute

!!! warning "Bounded smoke; не соединён с education demo"
    Trinity linker требует registry-backed mechanism и metric ids. Поэтому код ниже использует
    отдельный bundle с `income_tax`, созданный для compile/execute demonstration. Он не использует
    `frame`, `spec` или World Bank `panel` из предыдущих шагов. `GlobalState.empty(...)` и нулевой
    placeholder в `ModelSpec.data_snapshot_ref` — smoke scaffolding, не policy data и не evidence.
    `TemporaryDirectory` удаляет CAS и его artifacts при выходе из блока.
    Source entrypoint просмотрен на pin выше; этот пример не запускался в docs refresh. Его
    успешное выполнение, если contributor запустит его локально, докажет только прохождение
    ограниченного Foundry smoke path для этого синтетического bundle.

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
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir import ModelSpec, ProblemDomain, ProblemFrame, PolicySpec
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator

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

## Что этот walkthrough фактически показывает

Он показывает candidate framing, optional raw data retrieval и отдельный bounded
`compile_ok` / `execute_ok` Foundry smoke. Causal graphs, effect estimates, backtest metrics,
sensitivity reports и governance outcomes из этих шагов не производятся. Их описания в других
reference/how-to страницах относятся к отдельным поверхностям, а не к результату этой страницы.

## Draft handoff в Scientist: пока не подтверждён

Предыдущий вариант страницы представлял `run_experiment()` как продолжение тех же входов.
Приведённые шаги этого не обеспечивают:

- education `frame` и `spec` не сериализуются в bundle, который компилируется ниже;
- World Bank результат остаётся DataFrame; smoke не создаёт из него Fabric `DataSnapshot`;
- bundle и bound state в Foundry smoke относятся к `income_tax` и синтетическому пустому
  состоянию, а не к education panel;
- CAS находится внутри `TemporaryDirectory`, поэтому ссылки становятся недоступны после блока;
- само указание `scientist_causal_full` или профиля `research` не доказывает, что нужные
  входы разрешены, связаны с claim или достаточны для причинного вывода.

Поэтому здесь нет copy-paste вызова `run_experiment()` и нет ожидаемых Scientist outputs. Это
**draft intended handoff**, а не runnable continuation: для этого tutorial instance, прежде чем
называть его current, нужно построить и проверить bridge от education framing и source-bound
data snapshot к registry-backed compiled policy, workflow-required evidence и разрешённым
Scientist inputs.
См. [Scientist Workflows](../reference/scientist/workflows.md) для описания существующих
workflow contracts; ссылка не утверждает, что этот tutorial уже их связывает.

## Полный код демонстрации

Для стабильного запуска на Apple Silicon лучше явно переключить JAX на CPU:

```bash
JAX_PLATFORM_NAME=cpu JAX_PLATFORMS=cpu python first_policy_analysis.py
```

Скрипт ниже объединяет только две демонстрации: optional World Bank fetch и отдельный
synthetic Foundry smoke. Он не соединяет панель с policy bundle. Если сетевой fetch недоступен,
скрипт завершится ошибкой и не подставит fabricated observations. Скрипт и tests в docs refresh
не запускались.

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
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir import KPISpec, ModelSpec, ProblemDomain, ProblemFrame, PolicySpec
from polisyos.ir.connectors import FetchRequest
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.governance.problem_frame import ObjectiveSpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator


async def load_panel() -> pd.DataFrame:
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
        return frame
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

    panel = await load_panel()
    print("panel_source: World Bank API")
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

Скрипт печатает реальные observations, полученные при локальном запуске, и flags smoke path;
здесь нет ожидаемых числовых значений или сохранённых artifact IDs. CAS создаётся в
`TemporaryDirectory` и удаляется при выходе из контекста, поэтому распечатанные artifact IDs не
являются сохраняемыми ссылками. Чтобы осматривать их после выполнения, нужен явно выбранный
persistent CAS path с собственным cleanup.

## Что дальше

- [Getting Started](getting-started.md) — самый маленький Foundry smoke
- [Run Causal Analysis](../how-to/run-causal-analysis.md) — новые causal runner API
- [Installation](../how-to/install.md) — extras и runtime/causal setup
- [Scientist Workflows](../reference/scientist/workflows.md) — routing и required binds
