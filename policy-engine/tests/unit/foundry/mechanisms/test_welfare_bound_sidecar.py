from __future__ import annotations

from decimal import Decimal

import jax.numpy as jnp
import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ObservedRange,
    ObservedRangeBundle,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.welfare.bounds import (
    load_welfare_bound_report,
    persist_observed_range_bundle,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator

CTX_REF = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def _compile_policy(
    store: FileSystemCAS,
    *,
    registry_bundle_ref,
    intervention: InterventionSpec,
    domain: ProblemDomain,
):
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_1", domain=domain),
        policy_spec=PolicySpec(policy_id="policy_1", interventions=[intervention]),
        model_spec=ModelSpec(
            model_id="model_1",
            data_snapshot_ref=CTX_REF,
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=bundle.schema_version),
        ),
    )
    result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert result.ok
    assert result.exec_plan_ref is not None
    return result


def _input_bindings_ref(
    store: FileSystemCAS,
    *,
    registry_bundle_ref,
    state: GlobalState,
) -> FoundryInputBindingsRef:
    snapshot_ref = put_state_snapshot(store, state=state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    return FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id)


def _execute_single_intervention(
    store: FileSystemCAS,
    *,
    registry_bundle_ref,
    state: GlobalState,
    intervention: InterventionSpec,
    domain: ProblemDomain,
    observed_range_bundle: ObservedRangeBundle | None = None,
    welfare_bound_mode: str = "ex_ante",
    welfare_bound_required: bool = False,
):
    compile_result = _compile_policy(
        store,
        registry_bundle_ref=registry_bundle_ref,
        intervention=intervention,
        domain=domain,
    )
    input_bindings_ref = _input_bindings_ref(
        store,
        registry_bundle_ref=registry_bundle_ref,
        state=state,
    )
    observed_range_bundle_ref = None
    if observed_range_bundle is not None:
        observed_range_bundle_ref = persist_observed_range_bundle(store, observed_range_bundle)
    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=registry_bundle_ref,
            observed_range_bundle_ref=observed_range_bundle_ref,
            welfare_bound_mode=welfare_bound_mode,
            welfare_bound_required=welfare_bound_required,
        ),
    )
    assert result.ok is True
    report_ref = next(
        item.ref for item in result.derived_refs if item.role.startswith("welfare_bound_report:")
    )
    return result, load_welfare_bound_report(store, report_ref)


def test_execute_emits_exact_labor_market_welfare_bound(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)

    base = GlobalState.empty(n_agents=2, n_firms=2)
    state = base.replace(
        agents=base.agents.replace(skill_level=jnp.array([1.0, 2.0], dtype=jnp.float32)),
        firms=base.firms.replace(wage_offer=jnp.array([50.0, 60.0], dtype=jnp.float32)),
    )
    intervention = InterventionSpec(
        intervention_id="labor_policy",
        kind="labor_market",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"employment_threshold": Decimal("0.5")},
    )

    exec_result, report = _execute_single_intervention(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        state=state,
        intervention=intervention,
        domain=ProblemDomain.LABOR,
    )

    assert any(item.role.startswith("welfare_bound_report:") for item in exec_result.derived_refs)
    assert report.mechanism_type == "labor_market"
    assert report.status == "ok"
    assert report.mode == "ex_ante"
    assert report.mechanism_value == pytest.approx(82.5)
    assert report.first_best_lower == pytest.approx(180.0)
    assert report.first_best_upper == pytest.approx(180.0)
    assert report.welfare_loss_lower == pytest.approx(97.5)
    assert report.welfare_loss_upper == pytest.approx(97.5)


def test_execute_emits_exact_labor_market_ex_post_welfare_bound(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)

    base = GlobalState.empty(n_agents=2, n_firms=2)
    state = base.replace(
        agents=base.agents.replace(skill_level=jnp.array([1.0, 2.0], dtype=jnp.float32)),
        firms=base.firms.replace(wage_offer=jnp.array([50.0, 60.0], dtype=jnp.float32)),
    )
    intervention = InterventionSpec(
        intervention_id="labor_policy",
        kind="labor_market",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"employment_threshold": Decimal("0.0")},
    )

    exec_result, report = _execute_single_intervention(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        state=state,
        intervention=intervention,
        domain=ProblemDomain.LABOR,
        welfare_bound_mode="ex_post",
    )

    assert exec_result.simulation_result_ref is not None
    sim_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(exec_result.simulation_result_ref.artifact_id))
    )
    assert sim_result.welfare_bound_refs is not None
    assert report.node_id in sim_result.welfare_bound_refs
    assert report.mechanism_type == "labor_market"
    assert report.status == "ok"
    assert report.mode == "ex_post"
    assert report.mechanism_value == pytest.approx(0.0)
    assert report.first_best_lower == pytest.approx(180.0)
    assert report.first_best_upper == pytest.approx(180.0)
    assert report.welfare_loss_lower == pytest.approx(180.0)
    assert report.welfare_loss_upper == pytest.approx(180.0)
    assert "exact_ex_post_bound" in report.notes


def test_execute_emits_income_tax_welfare_bound_from_observed_ranges(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)

    base = GlobalState.empty(n_agents=2, n_firms=1)
    state = base.replace(
        agents=base.agents.replace(
            income=jnp.array([100.0, 200.0], dtype=jnp.float32),
            reported_income=jnp.array([100.0, 200.0], dtype=jnp.float32),
        )
    )
    intervention = InterventionSpec(
        intervention_id="tax_policy",
        kind="income_tax",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.2")},
    )
    observed_range_bundle = ObservedRangeBundle(
        ranges={
            "income_tax.eti_effective": ObservedRange(lower=0.1, upper=0.3),
        }
    )

    _, report = _execute_single_intervention(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        state=state,
        intervention=intervention,
        domain=ProblemDomain.FISCAL,
        observed_range_bundle=observed_range_bundle,
    )

    assert report.mechanism_type == "income_tax"
    assert report.status == "ok"
    assert report.welfare_loss_lower == pytest.approx(0.6943065, rel=1e-6)
    assert report.welfare_loss_upper == pytest.approx(2.0829196, rel=1e-6)
    assert report.required_observables == ("income_tax.eti_effective",)


def test_execute_hard_fails_when_required_income_tax_observables_are_missing(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)

    base = GlobalState.empty(n_agents=2, n_firms=1)
    state = base.replace(
        agents=base.agents.replace(
            income=jnp.array([100.0, 200.0], dtype=jnp.float32),
            reported_income=jnp.array([100.0, 200.0], dtype=jnp.float32),
        )
    )
    intervention = InterventionSpec(
        intervention_id="tax_policy",
        kind="income_tax",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.2")},
    )
    compile_result = _compile_policy(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        intervention=intervention,
        domain=ProblemDomain.FISCAL,
    )
    input_bindings_ref = _input_bindings_ref(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        state=state,
    )

    exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=bundle.bundle_ref,
            welfare_bound_required=True,
        ),
    )

    assert exec_result.ok is False
    assert exec_result.simulation_result_ref is None
    assert any(
        note.startswith("required_welfare_bound_failed:income_tax:") for note in exec_result.notes
    )
    report_ref = next(
        item.ref
        for item in exec_result.derived_refs
        if item.role.startswith("welfare_bound_report:")
    )
    report = load_welfare_bound_report(store, report_ref)
    assert report.status == "insufficient_observables"
    assert "missing_observable:income_tax.eti_effective" in report.notes


def test_execute_keeps_running_when_tax_subsidy_observables_are_missing(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)

    base = GlobalState.empty(n_agents=2, n_firms=1)
    state = base.replace(
        agents=base.agents.replace(
            income=jnp.array([100.0, 200.0], dtype=jnp.float32),
        )
    )
    intervention = InterventionSpec(
        intervention_id="subsidy_policy",
        kind="tax_subsidy",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.2")},
    )

    exec_result, report = _execute_single_intervention(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        state=state,
        intervention=intervention,
        domain=ProblemDomain.FISCAL,
    )

    assert exec_result.ok is True
    assert report.mechanism_type == "tax_subsidy"
    assert report.status == "insufficient_observables"
    assert "missing_observable:tax_subsidy.first_best_transfer" in report.notes
    assert "missing_observable:tax_subsidy.curvature" in report.notes
