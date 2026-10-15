# First Policy Analysis: Demonstrations and Boundaries

English edition: 2026-10-14 (translation only; not a source-freshness or execution claim).

Related references: [Compile Execute](../reference/foundry/compile-execute.md), [Scientist Workflows](../reference/scientist/workflows.md), [Problem Framing](../reference/ir/problem-framing.md).

> A learning map of several separate surfaces, not a functional end-to-end
> policy analysis. No step here derives a causal effect, an admissible
> recommendation, or a publishable result.

!!! info "Review basis (2026-10-14)"
    Source inspected at `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`; production implementation under
    `src/polisyos/` has not changed since this pin. Code and test entry points were read, but tests,
    snippets, package build, runtime, provider/network calls, and services were not run for this
    documentation refresh.

!!! note "Historical record (2026-04-17)"
    The previous revision recorded import checks for `ProblemFrame` / `PolicySpec` / `ModelSpec`,
    `WorldBankConnector`, `run_trivial_compile_execute`, and `run_experiment` in the tree at that
    time, on macOS with Python 3.14 and `uv`. It did not record execution of the complete walkthrough.
    The date remains historical and does not indicate source verification or execution for this update.

!!! info "Important note about the model shape"
    In the source snapshot above, `ProblemFrame` has no fields such as `outcome_kpi`, `treatment`,
    `entity_scope=EntityScope(region_codes=[...])` or `temporal_window=(...)`.
    In the reviewed source, this semantics is split across:
    `ProblemFrame` for objectives and KPIs;
    `PolicySpec` for interventions and regional targeting;
    Fabric queries for selecting the country and period; and
    causal-observation contracts for identification details.

## Three independent parts of the walkthrough

The examples below do not form one connected run:

1. **Framing demonstration:** `ProblemFrame` / `PolicySpec` describe an education question, while
   a separate optional World Bank fetch returns raw country-year observations.
2. **Bounded Foundry smoke:** a different `TrinityBundle` with the registry-backed `income_tax`
   mechanism and a synthetic empty `GlobalState` illustrates compile → execute.
3. **Draft Scientist handoff:** the proposed transfer of the education question/data to Scientist
   remains unverified and is blocked in this example by missing links between these objects.

Successful smoke execution does not connect the World Bank panel to the model, verify causal
identification, or establish admissibility, authority, or publishability of a policy claim.

## Problem framing

Learning scenario: consider how a researcher might study the relationship between public education
spending and GDP growth in Ukraine from 2015 to 2023. The question and KPI are candidate framing
only: this tutorial does not estimate the relationship or claim that a policy intervention caused
growth.

## Step 1: Define `ProblemFrame`

Use the real fields from `polisyos.ir.governance.problem_frame`:

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

What the fields mean in the current schema:

- `problem_id`: stable identifier for the problem;
- `domain`: broad policy area; here, `ProblemDomain.EDUCATION`;
- `kpis`: measurable outcomes to improve;
- `objectives`: optimization goals linked to KPIs.

In the current repository version, the country and time window are not stored directly in
`ProblemFrame`. They are carried in the data query and policy metadata.

This object is a framing example and is not passed to the Foundry smoke below. Creating the object
does not establish that the `education_spending_increase` mechanism is registered or executable.

## Step 2: Create `PolicySpec`

Use the real `PolicySpec` and governance `InterventionSpec` types:

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

Key fields in the current schema:

- `kind`: intervention family;
- `target`: selector expression
- `schedule`: step-based activation window;
- `params`: intervention parameters;
- `target_region_ids`: regional metadata carried with the intervention.

## Step 3: Bind data through Fabric

Use the production `WorldBankConnector` and real indicator codes:

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

When the API is available, this step shows a raw country-year panel. It does not turn observations
into causal evidence, connect them to the intervention in Step 2, or compute a treatment effect. No
World Bank request was made for this documentation refresh.

## Step 4: Compile and execute

!!! warning "Bounded smoke; not connected to the education demonstration"
    The Trinity linker requires a registry-backed mechanism and metric IDs. Therefore, the code
    below uses a separate bundle with `income_tax`, created for a compile/execute demonstration. It
    does not use the `frame`, `spec`, or World Bank `panel` from the previous steps.
    `GlobalState.empty(...)` and the zero placeholder in `ModelSpec.data_snapshot_ref` are smoke
    scaffolding, not policy data or evidence. `TemporaryDirectory` removes the CAS and its artifacts
    when the block exits. The source entry point was inspected at the pin above; this example was not
    run for this documentation refresh. If a contributor runs it locally and it succeeds, that
    establishes only that this synthetic bundle passed the bounded Foundry smoke path.

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

## What this walkthrough actually shows

It shows candidate framing, optional raw data retrieval, and a separate bounded
`compile_ok` / `execute_ok` Foundry smoke. Causal graphs, effect estimates, backtest metrics,
sensitivity reports, or governance outcomes are produced by these steps. Their descriptions on
other reference/how-to pages apply to separate surfaces, not to the result shown on this page.

## Draft handoff to Scientist: not yet verified

The previous version of this page presented `run_experiment()` as a continuation using the same
inputs. The steps shown here do not provide that:

- the education `frame` and `spec` are not serialized into the bundle compiled below;
- the World Bank result remains a DataFrame; the smoke does not create a Fabric `DataSnapshot` from it;
- the bundle and bound state in the Foundry smoke concern `income_tax` and a synthetic empty state,
  not the education panel;
- the CAS lives inside `TemporaryDirectory`, so its references become unavailable after the block;
- merely specifying `scientist_causal_full` or the `research` profile does not prove that the
  required inputs are permitted, bound to a claim, or sufficient for causal inference.

Therefore, this page has no copy-paste call to `run_experiment()` and no expected Scientist outputs.
It is a **draft intended handoff**, not a runnable continuation. Before calling this tutorial
instance current, build and verify a bridge from the education framing and source-bound data
snapshot to a registry-backed compiled policy, workflow-required evidence, and permitted Scientist
inputs. See [Scientist Workflows](../reference/scientist/workflows.md) for the existing workflow
contracts; the link does not claim that this tutorial connects them already.

## Complete demonstration code

For a stable run on Apple Silicon, explicitly switch JAX to CPU:

```bash
JAX_PLATFORM_NAME=cpu JAX_PLATFORMS=cpu python first_policy_analysis.py
```

The script below combines only two demonstrations: an optional World Bank fetch and a separate
synthetic Foundry smoke. It does not connect the panel to a policy bundle. If the network fetch is
unavailable, the script exits with an error and does not substitute fabricated observations. The
script and tests were not run for this documentation refresh.

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

The script prints the real observations obtained during a local run and the smoke-path flags; this
page does not give expected numeric values or retained artifact IDs. The CAS is created in
`TemporaryDirectory` and removed when the context exits, so the printed artifact IDs are not
persistent references. To inspect them after execution, choose a persistent CAS path explicitly
and manage its cleanup.

## Next steps

- [Getting Started](getting-started.md) — the smallest Foundry smoke
- [Run Causal Analysis](../how-to/run-causal-analysis.md) — current causal runner APIs
- [Installation](../how-to/install.md) — extras and runtime/causal setup
- [Scientist Workflows](../reference/scientist/workflows.md) — routing and required bindings
