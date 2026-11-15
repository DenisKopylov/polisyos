"""Stored singleton semantic execution facts through an actual read-only CAS."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    ExecuteRequest,
    FoundryExecConfig,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    SemanticHorizonStepContext,
    SimulationResult,
    SimulationResultRef,
    load_model_input_obligation_set,
    load_resolved_input_binding_manifest,
)
from polisyos.foundry.data_plane.bindings import (
    load_input_bindings,
    reconcile_selected_method_input_bindings,
)
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.actuation import create_program_graph_actuation_selection
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.runtime.quality.model_input_routing import materialize_derived_model_input
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import (
    _cas_file_content_identity,
)
from tests.unit.runtime.quality.test_model_input_requirements import _interface, _preflight


def _core_ref(ref):
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))


def _scope_variant(store, result_ref, basis, *, omit_set_edge=False):
    """Append an adversarial selected view; retain the original result bytes."""
    result = validate_core_model_json_artifact(SimulationResult, store, _core_ref(result_ref))
    basis_manifest = store.get_manifest(result.execution_input_basis_ref)
    inventory = execute_api._execution_input_basis_inventory(store, basis)
    if omit_set_edge:
        inventory = [
            edge for edge in inventory if edge.role != "basis.source.semantic_obligation_set"
        ]
    basis_ref = store.put_json(
        basis,
        PutOptions(
            kind=basis_manifest.kind,
            media_type=basis_manifest.media_type,
            schema=basis_manifest.artifact_schema,
            inputs=inventory,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    variant = result.model_copy(
        update={
            "execution_input_basis_ref": FoundryExecutionInputBasisRef.model_validate(
                basis_ref.model_dump(mode="python")
            )
        }
    )
    result_manifest = store.get_manifest(result_ref)
    ref = store.put_json(
        variant.to_artifact_payload(),
        PutOptions(
            kind=result_manifest.kind,
            media_type=result_manifest.media_type,
            schema=result_manifest.artifact_schema,
            inputs=[
                input_ref_from_artifact_ref(basis_ref, role="execution_input_basis")
                if edge.role == "execution_input_basis"
                else edge
                for edge in result_manifest.inputs
            ],
        ),
        return_selected_profile=True,
    )
    return SimulationResultRef.model_validate(ref.model_dump(mode="python"))


def _verify_singleton_semantic_history(
    store, result_ref, foreign_set_ref, monkeypatch, *, expected_step=None, expected_source_ref=None
):
    """Verify stored bytes; a retained-run instrument can reuse this same tail."""
    result = validate_core_model_json_artifact(SimulationResult, store, _core_ref(result_ref))
    stored_basis = validate_core_model_json_artifact(
        FoundryExecutionInputBasis, store, _core_ref(result.execution_input_basis_ref)
    )
    step = stored_basis.semantic_horizon_step if expected_step is None else expected_step
    assert step is not None
    input_bindings_ref = stored_basis.input_bindings_ref
    opening_ref = stored_basis.bound_state_snapshot_ref
    registry = MethodRegistry.get_instance()
    try:
        source_input = next(iter(PeriodFlowToStock.signature.input_slots))

        class ChangedCurrentABI(PeriodFlowToStock):
            signature = replace(
                PeriodFlowToStock.signature,
                input_slots=frozenset(
                    (
                        *PeriodFlowToStock.signature.input_slots,
                        replace(source_input, name="history_only"),
                    )
                ),
            )

        # Historical replay joins the captured ABI; today's method cannot
        # impose a new argument on the immutable executed invocation.
        registry.register(ChangedCurrentABI, override=True)
        calls = []

        def forbidden_execution(*_args, **_kwargs):
            calls.append(True)
            raise AssertionError("A historical reader attempted new graph execution")

        monkeypatch.setattr(execute_api, "execute_program_graph", forbidden_execution)
        monkeypatch.setattr(execute_api, "execute", forbidden_execution)
        monkeypatch.setattr(execute_api, "execute_semantic_horizon_step", forbidden_execution)

        readonly = FileSystemCAS.open_existing_read_only(store.root)
        before = _cas_file_content_identity(store.root)
        (admission,) = execute_api.admit_semantic_horizon_step_chain(readonly, (result_ref,))
        basis = admission.basis
        assert basis is not None and basis.schema_version == "1.4"
        assert basis.semantic_horizon_step is not None
        assert basis.semantic_horizon_step.model_dump(mode="json") == step.model_dump(mode="json")
        assert artifact_ref_identity_key(
            basis.base_state_snapshot_ref
        ) == artifact_ref_identity_key(opening_ref)
        assert float(
            load_state_snapshot(readonly, snapshot_ref=opening_ref).government_balance
        ) == (10_000_000_000.0)
        poststate_ref = admission.simulation_result.state_snapshot_ref
        assert poststate_ref is not None
        actual_stock = float(
            load_state_snapshot(readonly, snapshot_ref=poststate_ref).government_balance
        )
        assert actual_stock == 4_000_000_000.0

        bindings = load_input_bindings(readonly, input_bindings_ref)
        assert bindings.resolved_binding_manifest_ref is not None
        manifest = load_resolved_input_binding_manifest(
            readonly, bindings.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            readonly, manifest.model_input_obligation_set_ref
        )
        if expected_source_ref is not None:
            actual_source = selected_set.invocation.context.candidate_source_ref
            assert actual_source is not None
            assert artifact_ref_identity_key(actual_source) == artifact_ref_identity_key(
                expected_source_ref
            )
            assert artifact_ref_identity_key(actual_source) != artifact_ref_identity_key(
                basis.candidate_ref
            )
            assert [
                edge
                for edge in readonly.get_manifest(manifest.model_input_obligation_set_ref).inputs
                if edge.role == "selected_candidate_source"
            ] == [
                input_ref_from_artifact_ref(expected_source_ref, role="selected_candidate_source")
            ]

        def replay(context=step, result_ref=result_ref):
            return reconcile_selected_method_input_bindings(
                readonly,
                input_bindings_ref=input_bindings_ref,
                effective_step=0,
                semantic_horizon_step=context,
                historical_execution_ref=result_ref,
            )

        facts = replay()
        (record,) = facts.records
        value = facts.values["period_flow"]
        assert record.canonical_value == Decimal("-6000000000")
        assert value.shape == () and value.dtype == np.dtype("float64")
        assert float(value) == -6_000_000_000.0 and not value.flags.writeable
        digest = hashlib.sha256()
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
        digest.update(value.tobytes(order="C"))
        assert digest.hexdigest() == record.value_sha256
        assert _cas_file_content_identity(store.root) == before

        # A real producer emits another valid set for another context. Its
        # source bytes cannot be relabeled as this historical invocation.
        wrong_contexts = (
            step.model_copy(update={"obligation_set_ref": foreign_set_ref}),
            step.model_copy(update={"replication_seed": step.replication_seed + 1}),
            step.model_copy(update={"previous_result_ref": result_ref}),
            step.model_copy(update={"steps": (0, 1)}),
        )
        for wrong in wrong_contexts:
            with pytest.raises(
                ValueError, match="^foundry_selected_method_input_historical_horizon_mismatch$"
            ):
                replay(wrong)
        assert _cas_file_content_identity(store.root) == before

        if expected_source_ref is not None:
            # The opaque source remains a Core-selected provenance parent;
            # it cannot replace the separately compiled policy candidate.
            wrong_compiled_ref = _scope_variant(
                store,
                result_ref,
                basis.model_copy(update={"candidate_ref": expected_source_ref}),
            )
            before_wrong_compiled = _cas_file_content_identity(store.root)
            with pytest.raises(
                ValueError, match="^execution_source_edge_payload_disagrees:policy_candidate$"
            ):
                replay(result_ref=wrong_compiled_ref)
            assert _cas_file_content_identity(store.root) == before_wrong_compiled

            set_manifest = store.get_manifest(manifest.model_input_obligation_set_ref)
            wrong_source_view = store.put_json(
                selected_set,
                PutOptions(
                    kind=set_manifest.kind,
                    media_type=set_manifest.media_type,
                    schema=set_manifest.artifact_schema,
                    inputs=[
                        input_ref_from_artifact_ref(
                            basis.candidate_ref, role="selected_candidate_source"
                        )
                        if edge.role == "selected_candidate_source"
                        else edge
                        for edge in set_manifest.inputs
                    ],
                ),
                return_selected_profile=True,
            )
            before_wrong_source = _cas_file_content_identity(store.root)
            with pytest.raises(ValueError, match="^model_input_artifact_lineage_mismatch$"):
                load_model_input_obligation_set(readonly, wrong_source_view)
            assert _cas_file_content_identity(store.root) == before_wrong_source

        bad_opening_ref = _scope_variant(
            store,
            result_ref,
            basis.model_copy(update={"base_state_snapshot_ref": poststate_ref}),
        )
        before_bad_opening = _cas_file_content_identity(store.root)
        with pytest.raises(
            ValueError, match="^foundry_selected_method_input_historical_invocation_mismatch$"
        ):
            replay(result_ref=bad_opening_ref)
        assert _cas_file_content_identity(store.root) == before_bad_opening

        multi_step_ref = _scope_variant(
            store,
            result_ref,
            basis.model_copy(
                update={"semantic_horizon_step": step.model_copy(update={"steps": (0, 1)})}
            ),
        )
        before_multi_step = _cas_file_content_identity(store.root)
        with pytest.raises(
            ValueError, match="^foundry_selected_method_input_historical_horizon_mismatch$"
        ):
            replay(result_ref=multi_step_ref)
        assert _cas_file_content_identity(store.root) == before_multi_step

        missing_edge_ref = _scope_variant(store, result_ref, basis, omit_set_edge=True)
        before_negatives = _cas_file_content_identity(store.root)
        with pytest.raises(
            ValueError,
            match=(
                r"^foundry_selected_method_input_historical_horizon_lineage_mismatch:"
                r"basis\.source\.semantic_obligation_set$"
            ),
        ):
            replay(result_ref=missing_edge_ref)
        replay()
        assert _cas_file_content_identity(store.root) == before_negatives
        assert calls == []
        return {
            "stock": actual_stock,
            "value_sha256": digest.hexdigest(),
            "scope_controls": [
                "set",
                "seed",
                "predecessor",
                "requested_steps",
                "opening",
                "stored_steps",
                "edge",
                *([] if expected_source_ref is None else ["compiled_candidate", "selected_source"]),
            ],
            "new_graph_calls": len(calls),
        }
    finally:
        registry.register(PeriodFlowToStock, override=True)


def test_singleton_semantic_method_history_replays_readonly_and_refuses_scope_substitution(
    tmp_path, monkeypatch
):
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
    )
    try:
        materialized = materialize_selected_method_input_case(case, metadata)
        manifest = load_resolved_input_binding_manifest(
            case.store, materialized.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            case.store, manifest.model_input_obligation_set_ref
        )
        # Core consumes this persisted N4-type parent as opaque selected
        # provenance. The fixture makes no claim about Runtime N4 authority.
        source_ref = case.store.put_json(
            {"fixture": "opaque_selected_candidate_source", "authority": "not_established"},
            PutOptions(
                kind="runtime.generation_source_handoff",
                media_type="application/json",
                inputs=[input_ref_from_artifact_ref(case.policy_candidate_ref, role="candidate")],
            ),
            return_selected_profile=True,
        )
        context = selected_set.invocation.context.model_copy(
            update={"candidate_source_ref": _core_ref(source_ref)}
        )
        selected_preflight = _preflight(case, _interface(case), context, steps=(0,))
        selected_set, _ = load_model_input_obligation_set(
            case.store, selected_preflight.obligation_set_ref
        )
        (obligation_ref,) = selected_set.obligation_refs
        # Reuse the one actually admitted native derivation; only the Core
        # obligation/source selection changes, through its real producer.
        materialized = materialize_derived_model_input(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=selected_preflight.obligation_set_ref,
            model_input_obligation_ref=obligation_ref,
            profile_ref=metadata["derived_profile_ref"],
            source_context_ref=metadata["source_context_ref"],
            recipe_ref=metadata["recipe_ref"],
            certificate_ref=metadata["certificate_ref"],
            output_ref=metadata["output_ref"],
            roles=metadata["roles"],
            year=2024,
            binding_id="selected-period-flow-n4-source",
        )
        manifest = load_resolved_input_binding_manifest(
            case.store, materialized.resolved_binding_manifest_ref
        )
        step = SemanticHorizonStepContext(
            obligation_set_ref=manifest.model_input_obligation_set_ref,
            steps=selected_set.invocation.steps,
            step_index=0,
            replication_seed=23,
        )
        assert step.steps == (0,)
        baseline_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=(),
        )
        request = ExecuteRequest(
            schema_version="1.1",
            exec_plan_ref=case.exec_plan_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            actuation_selection_ref=baseline_ref,
            exec_config=FoundryExecConfig(seed=23),
            return_selected_profile=True,
        )
        # One actual Foundry producer. Later negative setup appends selected
        # artifact views; verification performs no further graph execution.
        executed = execute_api.execute_semantic_horizon_step(
            case.store, request, expected_invocation=selected_set.invocation, step=step
        )
        assert executed.ok and executed.simulation_result_ref is not None
        foreign = _preflight(
            case,
            _interface(case),
            selected_set.invocation.context.model_copy(update={"run_id": "history-other-scope"}),
            steps=(0,),
        )
        _verify_singleton_semantic_history(
            case.store,
            executed.simulation_result_ref,
            foreign.obligation_set_ref,
            monkeypatch,
            expected_step=step,
            expected_source_ref=source_ref,
        )
    finally:
        case.close()
