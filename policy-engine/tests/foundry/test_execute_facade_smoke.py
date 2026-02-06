from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import CompileRequest, ExecuteRequest, StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.schedule import ScheduleSpec
from polisyos.ir.selector_expr import SelectorPredicate
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def test_execute_facade_smoke(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert compile_result.ok
    assert compile_result.exec_plan_ref is not None

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)

    exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            state_snapshot_ref=state_snapshot_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert exec_result.ok is True
    assert exec_result.simulation_result_ref is not None
    assert exec_result.simulation_result_ref.kind == "foundry.simulation_result"
