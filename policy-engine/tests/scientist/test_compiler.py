import jax.numpy as jnp
import pytest
from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import apply_state_delta_and_snapshot, execute_program_graph
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator


def _bundle_with_subsidy(registry_bundle_ref: str, *, rate: Decimal) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_1",
            interventions=[
                InterventionSpec(
                    intervention_id="subsidy_2025",
                    kind="tax_subsidy",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": rate},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=registry_bundle_ref,
        ),
    )


def test_compile_trinity_policy_roundtrip_rate(tmp_path) -> None:
    """
    Trinity smoke-test:
    TrinityBundle -> foundry compile -> foundry execute -> apply patches to GlobalState.
    """

    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    trinity_bundle = _bundle_with_subsidy(
        str(bundle.bundle_ref.artifact_id),
        rate=Decimal("0.15"),
    )
    policy_ref = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version),
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
    assert compile_result.ok is True
    program_ref = next(ref.ref for ref in compile_result.derived_refs if ref.role == "program_graph")
    exec_plan_ref = compile_result.exec_plan_ref
    assert exec_plan_ref is not None

    n_agents = 100
    base_state = GlobalState.empty(n_agents=n_agents, n_firms=5)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.ones(n_agents, dtype=jnp.float32) * 1000.0)
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        selector_field_registry=registries.selector_field_registry,
        step=0,
        seed=0,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    avg_income = jnp.mean(next_state.agents.income)
    assert float(avg_income) == pytest.approx(1150.0, abs=1e-3)
