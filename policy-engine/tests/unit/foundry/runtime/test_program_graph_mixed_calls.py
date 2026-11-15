"""Bounded mixed calls retain simultaneous patch and per-node Treasury semantics."""

from __future__ import annotations

import hashlib
import json
import stat
from decimal import Decimal

import jax
import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactIntegrityError,
    ArtifactRef,
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecuteRequest,
    FoundryExecConfig,
    ProgramGraph,
)
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import (
    load_input_bindings,
    reconcile_selected_method_input_bindings,
)
from polisyos.foundry.execute._internal.graph import (
    _program_graph_call_inventory,
    prepare_program_graph_mechanism_calls,
    prepare_program_graph_method_calls,
)
from polisyos.foundry.execute.actuation import (
    create_program_graph_actuation_selection,
    resolve_program_graph_actuation,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.execute.mechanisms.fiscal import TaxSubsidy
from polisyos.foundry.execute.mechanisms.labor import LaborMarketMechanism
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob
from tests.unit.foundry.runtime.test_selected_method_inputs import _fresh_process_read

_EXECUTION_SEED = 7


def _joint_policy():
    target = SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all")
    return PolicySpec(
        policy_id="selected_method_input",
        interventions=[
            InterventionSpec(
                intervention_id=node_id,
                kind=kind,
                target=target,
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params=params,
            )
            for node_id, kind, params in (
                ("fixture_labor", "labor_market", {"employment_threshold": Decimal("0.5")}),
                ("fixture_subsidy", "tax_subsidy", {"rate": Decimal("0.25")}),
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id=f"{node_id}_binding", mechanism_id=kind, intervention_ids=[node_id]
            )
            for node_id, kind in (
                ("fixture_labor", "labor_market"),
                ("fixture_subsidy", "tax_subsidy"),
            )
        ],
    )


def _joint_case(tmp_path, *, missing_initial_slot=None):
    initial = {
        "agents.skill_level": [1] * 64,
        "agents.is_employed": [False] * 64,
        # This is the canonical signed no-employer sentinel, explicitly
        # supplied as synthetic input rather than inferred from a default.
        "agents.employer_id": [-1] * 64,
        "firms.wage_offer": [10],
    }
    if missing_initial_slot is not None:
        del initial[missing_initial_slot]
    return prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=_joint_policy(),
        income_values=(4,) * 64,
        opening_balance_usd=4096,
        explicit_initial_slot_values=initial,
    )


def _selection(case, selected_ids):
    selected_ref = create_program_graph_actuation_selection(
        case.store,
        program_ref=case.program_graph_ref,
        exec_plan_ref=case.exec_plan_ref,
        selected_intervention_ids=selected_ids,
    )
    resolution = resolve_program_graph_actuation(
        case.store,
        program_ref=case.program_graph_ref,
        exec_plan_ref=case.exec_plan_ref,
        actuation_selection_ref=selected_ref,
    )
    return selected_ref, resolution


def _oracle_step_key(node_id, *, compilation_seed, execution_seed):
    """Derive V1 keys from its documented hash/fold law, outside the executor."""
    key = jax.random.PRNGKey(execution_seed)
    for label in ("stream:default", f"node:{node_id}"):
        value = label if compilation_seed == 0 else f"{compilation_seed}:{label}"
        salt = int(hashlib.sha256(value.encode()).hexdigest()[:16], 16)
        key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
        key = jax.random.fold_in(key, salt >> 32)
    return jax.random.split(key)[1]


def test_mixed_preparation_supports_multiple_real_policy_calls(tmp_path):
    case, _metadata = _joint_case(tmp_path)
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        assert {node.mechanism_type for node in graph.nodes if node.mechanism_type} == {
            "labor_market",
            "tax_subsidy",
        }
        assert sum(node.node_kind == "method" for node in graph.nodes) == 1
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        base = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        np.testing.assert_array_equal(base.agents.income, np.full(64, 4))
        np.testing.assert_array_equal(base.agents.skill_level, np.ones(64))
        np.testing.assert_array_equal(base.firms.wage_offer, [10])
        for selected_ids in (
            (),
            ("fixture_labor",),
            ("fixture_subsidy",),
            ("fixture_labor", "fixture_subsidy"),
        ):
            selected_ref, resolution = _selection(case, selected_ids)
            calls = prepare_program_graph_mechanism_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                base_state=base,
                mechanism_registry=registry.mechanism_registry,
                steps=(0,),
                actuation_selection_ref=selected_ref,
            )
            expected = [node_id for node_id in plan.order if node_id in selected_ids]
            assert [node_id for _, node_id, _, _ in calls] == expected
            assert [index for index, _, _, _ in calls] == [
                plan.order.index(node_id) for node_id in expected
            ]
            assert all(step == 0 for _, _, step, _ in calls)
            assert set(resolution.active_apply_node_ids) == set(expected)
            assert set(resolution.inactive_apply_node_ids) == {
                "fixture_labor",
                "fixture_subsidy",
            } - set(expected)
            for _, node_id, _, selected_call in calls:
                if node_id == "fixture_labor":
                    assert isinstance(selected_call.__self__, LaborMarketMechanism)
                    assert float(selected_call.__self__.employment_threshold) == 0.5
                else:
                    assert isinstance(selected_call.__self__, TaxSubsidy)
                    assert float(selected_call.__self__.rate) == 0.25

        legacy = prepare_program_graph_mechanism_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            base_state=base,
            mechanism_registry=registry.mechanism_registry,
            steps=(0,),
        )
        assert [node_id for _, node_id, _, _ in legacy] == [
            node_id for node_id in plan.order if node_id in {"fixture_labor", "fixture_subsidy"}
        ]
    finally:
        case.close()


def test_joint_mixed_method_side_input_preserves_exact_discrete_prestate(tmp_path):
    from polisyos.core.contracts import StateSnapshot

    case, metadata = _joint_case(tmp_path)
    try:
        initial = load_input_bindings(case.store, case.input_bindings_ref)
        materialized = materialize_selected_method_input_case(
            case, metadata, ratio_value=Decimal("-0.03125"), denominator_value=Decimal("2048")
        )
        bound = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bound.schema_version == "1.4"
        assert artifact_ref_identity_key(
            bound.bound_state_snapshot_ref
        ) == artifact_ref_identity_key(case.bound_state_snapshot_ref)
        assert bound.rules == initial.rules
        resolution = reconcile_selected_method_input_bindings(
            case.store, input_bindings_ref=materialized.input_bindings_ref, effective_step=0
        )
        assert float(resolution.values["period_flow"]) == -64
        state = load_state_snapshot(case.store, snapshot_ref=bound.bound_state_snapshot_ref)
        assert np.asarray(state.agents.is_employed).dtype == np.dtype("bool")
        assert np.asarray(state.agents.employer_id).dtype == np.dtype("int32")
        np.testing.assert_array_equal(state.agents.is_employed, np.zeros(64, dtype=bool))
        np.testing.assert_array_equal(state.agents.employer_id, np.full(64, -1))
        with (
            _removed_blob(case.store, case.source_ref),
            pytest.raises(
                ValueError,
                match=r"^DataSnapshot selected nested reference profile does not resolve: data_ref$",
            ) as missing,
        ):
            reconcile_selected_method_input_bindings(
                case.store, input_bindings_ref=materialized.input_bindings_ref, effective_step=0
            )
        assert isinstance(missing.value.__cause__, FileNotFoundError)
        assert str(case.source_ref.artifact_id).removeprefix("sha256:") in str(
            missing.value.__cause__
        )
        snapshot = validate_core_model_json_artifact(
            StateSnapshot, case.store, case.bound_state_snapshot_ref
        )
        blob, _ = case.store._paths(snapshot.state_ref.artifact_id)
        content, mode = blob.read_bytes(), stat.S_IMODE(blob.stat().st_mode)
        blob.unlink()
        blob.write_bytes(b"corrupted actual predecessor NPZ")
        try:
            with pytest.raises(
                ValueError, match=r"^Snapshot checksum mismatch: Blob sha256 mismatch for "
            ) as corrupt:
                reconcile_selected_method_input_bindings(
                    case.store, input_bindings_ref=materialized.input_bindings_ref, effective_step=0
                )
            assert isinstance(corrupt.value.__cause__, ArtifactIntegrityError)
            assert str(snapshot.state_ref.artifact_id) in str(corrupt.value.__cause__)
        finally:
            blob.unlink()
            blob.write_bytes(content)
            blob.chmod(mode)
        restored = reconcile_selected_method_input_bindings(
            case.store, input_bindings_ref=materialized.input_bindings_ref, effective_step=0
        )
        assert float(restored.values["period_flow"]) == -64
    finally:
        case.close()


class _JointObserver:
    def __init__(self):
        self.graphs = []
        self.methods = []
        self.mechanisms = []
        self.nodes = []
        self.finishes = []

    def graph_started(self, **values):
        self.graphs.append((values["step"], values["seed"]))

    def graph_finished(self, **_values):
        self.finishes.append(("graph", "returned"))

    def method_started(self, **values):
        self.methods.append(values["prepared_call"])

    def method_finished(self, **values):
        self.finishes.append(("method", values["status"]))

    def mechanism_started(self, **values):
        self.mechanisms.append(values)

    def mechanism_finished(self, **values):
        self.finishes.append(("mechanism", values["status"]))

    def node_finished(self, **values):
        self.nodes.append((values["node_id"], values["status"]))


def test_joint_mixed_actuation_uses_opening_state_and_per_node_treasury(tmp_path):
    case, metadata = _joint_case(tmp_path)
    try:
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        base = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        materialized = materialize_selected_method_input_case(
            case, metadata, ratio_value=Decimal("-0.03125"), denominator_value=Decimal("2048")
        )
        labor_key = _oracle_step_key(
            "fixture_labor", compilation_seed=plan.random_seed or 0, execution_seed=_EXECUTION_SEED
        )
        employment_key = jax.random.split(labor_key, 3)[0]
        employment = np.asarray(jax.random.uniform(employment_key, shape=(64,))) < 0.5
        q = float(np.mean(employment))
        outcomes = {}
        method_keys = []
        for selected_ids in (
            (),
            ("fixture_labor",),
            ("fixture_subsidy",),
            ("fixture_labor", "fixture_subsidy"),
        ):
            selected_ref, resolution = _selection(case, selected_ids)
            (method,) = prepare_program_graph_method_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                base_state=base,
                steps=(0,),
                seed=_EXECUTION_SEED,
                actuation_selection_ref=selected_ref,
            )
            assert float(method.input_values["period_flow"]) == -64
            assert method.root_seed == _EXECUTION_SEED
            method_keys.append((method.seed, method.key_words))
            prepared = prepare_program_graph_mechanism_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                base_state=base,
                mechanism_registry=registry.mechanism_registry,
                steps=(0,),
                actuation_selection_ref=selected_ref,
            )
            observer = _JointObserver()
            request = ExecuteRequest(
                schema_version="1.1",
                exec_plan_ref=case.exec_plan_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                actuation_selection_ref=selected_ref,
                exec_config=FoundryExecConfig(seed=_EXECUTION_SEED),
                return_selected_profile=True,
            )
            executed = execute_foundry(case.store, request, observer=observer)
            assert executed.ok and executed.simulation_result_ref is not None
            assert observer.graphs == [(0, _EXECUTION_SEED)]
            assert observer.nodes == [
                (node_id, "succeeded" if mode == "execute" else "skipped")
                for node_id, mode in resolution.node_execution
            ]
            assert len(observer.methods) == 1
            actual_method = observer.methods[0]
            assert (actual_method.seed, actual_method.key_words) == (method.seed, method.key_words)
            assert actual_method.method_abi_digest == method.method_abi_digest
            np.testing.assert_array_equal(actual_method.input_values["period_flow"], -64)
            assert len(observer.mechanisms) == len(prepared) == len(selected_ids)
            for actual, (index, node_id, step, selected_call) in zip(
                observer.mechanisms, prepared, strict=True
            ):
                assert (actual["plan_index"], actual["node_id"], actual["step"]) == (
                    index,
                    node_id,
                    step,
                )
                assert actual["selected_call"].__func__ is selected_call.__func__
                np.testing.assert_array_equal(
                    actual["key"],
                    _oracle_step_key(
                        node_id,
                        compilation_seed=plan.random_seed or 0,
                        execution_seed=_EXECUTION_SEED,
                    ),
                )
                # Both real mechanisms read the same opening income; their
                # patches combine at the existing merge, not by forced order.
                np.testing.assert_array_equal(actual["state"].agents.income, np.full(64, 4))
                assert float(actual["state"].government_balance) == 4096
            assert all(status == "returned" for _, status in observer.finishes)
            fresh = case.store.open_existing_read_only(case.store_root)
            admitted = admit_execution_source(fresh, executed.simulation_result_ref)
            assert admitted.basis.request.exec_config.seed == _EXECUTION_SEED
            assert "seed_source:exec_config.seed" in admitted.simulation_result.notes
            state = load_state_snapshot(
                fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
            )
            expected_income = (
                np.where(employment, 10, 0) if "fixture_labor" in selected_ids else np.full(64, 4)
            ) + (1 if "fixture_subsidy" in selected_ids else 0)
            np.testing.assert_array_equal(state.agents.income, expected_income)
            expected_stock = 4032 - (64 if "fixture_subsidy" in selected_ids else 0)
            assert np.asarray(state.government_balance).dtype == np.dtype("float32")
            assert float(state.government_balance) == expected_stock
            outcomes[selected_ids] = float(np.mean(np.asarray(state.agents.income)))
            cold = _fresh_process_read(case, executed.simulation_result_ref)
            assert cold["stock"] == expected_stock and cold["occurrences"] == 1
        assert len(set(method_keys)) == 1
        y0, ya, yb, yab = outcomes.values()
        assert (y0, ya, yb, yab) == (4, 10 * q, 5, 10 * q + 1)
        assert yab - ya - yb + y0 == 0
        print(
            "mixed_call_oracle",
            json.dumps(
                {
                    "seed": _EXECUTION_SEED,
                    "employment_fraction": q,
                    "income_means": [y0, ya, yb, yab],
                    "interaction": yab - ya - yb + y0,
                    "common_method_flow": -64,
                    "common_method_seed": method_keys[0][0],
                }
            ),
        )
    finally:
        case.close()


def test_joint_mixed_inventory_preserves_scope_write_and_treasury_refusals(tmp_path, monkeypatch):
    case, _metadata = _joint_case(tmp_path)
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        arguments = dict(
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            graph=graph,
            plan=plan,
            mechanism_registry=registry.mechanism_registry,
            steps=(0,),
        )
        numeric_calls = []

        def forbidden_numeric_call(*_args, **_kwargs):
            numeric_calls.append("numerical_call")
            raise AssertionError("bounded call inventory executed a numerical provider")

        monkeypatch.setattr(LaborMarketMechanism, "emit_patches", forbidden_numeric_call)
        monkeypatch.setattr(TaxSubsidy, "emit_patches", forbidden_numeric_call)
        labor_node = next(node for node in graph.nodes if node.node_id == "fixture_labor")
        for changes, reason in (
            ({"steps": (0, 1)}, "program_graph_mixed_call_profile_not_established"),
            ({"steps": (1,)}, "program_graph_mixed_active_mechanism_required"),
            (
                {"plan": plan.model_copy(update={"notes": []})},
                "program_graph_mixed_treasury_profile_required",
            ),
            (
                {"parameter_overrides": {"fixture_subsidy": {"rate": Decimal("0.5")}}},
                "program_graph_mixed_parameter_override_profile_not_established",
            ),
            (
                {
                    "graph": graph.model_copy(
                        update={
                            "nodes": [
                                node.model_copy(update={"node_kind": "mechanism", "op": None})
                                if node.node_id == "fixture_labor"
                                else node
                                for node in graph.nodes
                            ]
                        }
                    )
                },
                "program_graph_mixed_call_profile_not_established",
            ),
            (
                {
                    "graph": graph.model_copy(
                        update={
                            "nodes": [
                                node.model_copy(
                                    update={"outputs": [*labor_node.outputs, "foreign.write"]}
                                )
                                if node.node_id == "fixture_labor"
                                else node
                                for node in graph.nodes
                            ]
                        }
                    )
                },
                "program_graph_mixed_mechanism_writes_not_established",
            ),
            (
                {
                    "mechanism_registry": registry.mechanism_registry.model_copy(
                        update={
                            "mechanisms": {
                                name: spec
                                for name, spec in registry.mechanism_registry.mechanisms.items()
                                if name != "labor_market"
                            }
                        }
                    )
                },
                "program_graph_mixed_mechanism_writes_not_established",
            ),
        ):
            with pytest.raises(ValueError, match=f"^{reason}$"):
                _program_graph_call_inventory(case.store, **(arguments | changes))

        manifest = case.store.get_manifest(case.exec_plan_ref)
        edge = next(item for item in manifest.inputs if item.role == "treasury_plan")
        duplicate_treasury_plan_ref = case.store.put_json(
            plan,
            PutOptions(
                kind=ExecPlan.ARTIFACT_KIND,
                media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ExecPlan.ARTIFACT_SCHEMA_NAME, version=ExecPlan.ARTIFACT_SCHEMA_VERSION
                ),
                inputs=[*manifest.inputs, edge],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="^treasury_requires_one_treasury_plan_input$"):
            _program_graph_call_inventory(
                case.store,
                **(arguments | {"exec_plan_ref": duplicate_treasury_plan_ref}),
            )
        treasury_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind="foundry.treasury_plan",
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        )
        blob, _ = case.store._paths(treasury_ref.artifact_id)
        content, mode = blob.read_bytes(), stat.S_IMODE(blob.stat().st_mode)
        blob.unlink()
        try:
            with pytest.raises(
                FileNotFoundError, match=str(treasury_ref.artifact_id).removeprefix("sha256:")
            ):
                _program_graph_call_inventory(case.store, **arguments)
        finally:
            blob.write_bytes(content)
            blob.chmod(mode)
        restored = _program_graph_call_inventory(case.store, **arguments)
        assert set(restored.active_mechanisms) == {(0, "fixture_labor"), (0, "fixture_subsidy")}
        assert numeric_calls == []
    finally:
        case.close()
