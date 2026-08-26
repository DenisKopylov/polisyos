from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import FoundryInputBindings, StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import UkraineFoundryIntakeResult
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.observation.bundles import ProxyIdentificationBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins.data.bind_foundry_inputs import BindFoundryInputsNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_INPUT_BINDING_REPORT_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _put_trinity_bundle(
    store: FileSystemCAS,
    *,
    registry_bundle_ref,
    data_snapshot_ref: str,
) -> object:
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="p8_bind", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_bind",
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
            model_id="model_bind",
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        ),
    )
    return store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )


def _setup_ctx(store: FileSystemCAS):
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_bind")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.bind"))
    return ctx, registry_bundle


def _put_data_snapshot(
    store: FileSystemCAS,
    *,
    stats: dict[str, int | str] | None = None,
) -> DataSnapshotRef:
    base_state = GlobalState.empty(n_agents=5, n_firms=2)
    state_snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
            stats=stats or {},
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)


def _verified_ukraine_intake(
    store: FileSystemCAS,
    data_snapshot_ref: DataSnapshotRef,
) -> UkraineFoundryIntakeResult:
    return UkraineFoundryIntakeResult(
        data_snapshot_ref=data_snapshot_ref,
        proxy_identification_bundle=ProxyIdentificationBundle.model_validate(
            {
                "contract_target": {
                    "contract_id": "foundry.causal.proxy_measurement_data.v1",
                    "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                },
                "proxy_channels": [
                    {
                        "family": "distress_enforcement",
                        "proxy_variable": "C_star",
                        "latent_variable": "C",
                        "target_contract": {
                            "contract_id": "foundry.causal.proxy_measurement_data.v1",
                            "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                        },
                    }
                ],
                "proxy_map": {"C": "C_star"},
            }
        ).model_dump(mode="json"),
        method_contracts={"d2_dynamic_treatment": object()},
        receipt_ref=store.put_json(
            {
            "schema_version": "polisyos.foundry.ukraine_intake_receipt.v1",
            "authority_purpose": "producer_artifact_content_binding",
            "stage_receipts": {"d0_p0": {"content_binding_provenance": "recomputed"}},
            "validated_contracts": {"d2_dynamic_treatment": {"sha256": "a" * 64}},
            },
            PutOptions(kind="foundry.ukraine_intake_receipt", media_type="application/json"),
        ),
    )


def test_bind_foundry_inputs_node_consumes_intake_and_persists_inspectable_receipt(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    intake = _verified_ukraine_intake(store, data_snapshot_ref)
    state = ExperimentState(
        run_id="R_bind_ukraine_intake",
        inputs={
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={
            "ukraine_foundry_intake": {
                "allowed_root": str(tmp_path),
                "stage_manifests": {"d0_p0": "unused"},
            }
        },
    )

    with patch(
        "polisyos.scientist.nodes.builtins.data.bind_foundry_inputs.load_ukraine_foundry_intake",
        return_value=intake,
    ) as load_intake:
        outcome = BindFoundryInputsNode().execute(ctx, state)

    assert outcome.status == "ok"
    load_intake.assert_called_once()
    receipt_ref = outcome.state.artifacts_index["ukraine_foundry_intake_receipt_ref"]
    receipt = from_canonical_bytes(store.get_bytes(receipt_ref.artifact_id))
    assert receipt["authority_purpose"] == "producer_artifact_content_binding"
    assert "d2_dynamic_treatment" in receipt["validated_contracts"]
    assert outcome.state.params["proxy_identification_bundle"]["proxy_map"] == {"C": "C_star"}


def test_bind_foundry_inputs_node_fails_closed_when_intake_rejects_an_artifact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    state = ExperimentState(
        run_id="R_bind_ukraine_intake_failure",
        inputs={
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        params={
            "ukraine_foundry_intake": {
                "allowed_root": str(tmp_path),
                "stage_manifests": {"d0_p0": "unused"},
            }
        },
    )

    with patch(
        "polisyos.scientist.nodes.builtins.data.bind_foundry_inputs.load_ukraine_foundry_intake",
        side_effect=ValueError("content hash mismatch for output survival_contract.json"),
    ):
        outcome = BindFoundryInputsNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "foundry.input_bindings_failed"
    assert "ukraine_foundry_intake_receipt_ref" not in outcome.state.artifacts_index


def test_bind_foundry_inputs_node_builds_bindings_and_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    trinity_ref = _put_trinity_bundle(
        store,
        registry_bundle_ref=registry_bundle_ref,
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
    )

    state = ExperimentState(
        run_id="R_bind",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )

    outcome = BindFoundryInputsNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert INPUT_INPUT_BINDINGS_REF in outcome.state.inputs
    assert ARTIFACT_STATE_SNAPSHOT_REF in outcome.state.artifacts_index
    assert ARTIFACT_INPUT_BINDING_REPORT_REF in outcome.state.artifacts_index

    bindings_ref = outcome.state.inputs[INPUT_INPUT_BINDINGS_REF]
    payload = from_canonical_bytes(store.get_bytes(bindings_ref.artifact_id))
    bindings = FoundryInputBindings.model_validate(payload)
    assert (
        bindings.bound_state_snapshot_ref.artifact_id
        == outcome.state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF].artifact_id
    )


def test_bind_foundry_inputs_node_is_deterministic_for_identical_inputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    trinity_ref = _put_trinity_bundle(
        store,
        registry_bundle_ref=registry_bundle_ref,
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
    )

    base_state = ExperimentState(
        run_id="R_bind_det",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )

    node = BindFoundryInputsNode()
    outcome_a = node.execute(ctx, base_state)
    outcome_b = node.execute(ctx, base_state.model_copy(deep=True))

    ref_a = outcome_a.state.inputs[INPUT_INPUT_BINDINGS_REF]
    ref_b = outcome_b.state.inputs[INPUT_INPUT_BINDINGS_REF]
    assert ref_a.artifact_id == ref_b.artifact_id
    assert (
        outcome_a.state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF].artifact_id
        == outcome_b.state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF].artifact_id
    )


def test_bind_foundry_inputs_node_blocks_on_model_spec_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    trinity_ref = _put_trinity_bundle(
        store,
        registry_bundle_ref=registry_bundle_ref,
        data_snapshot_ref="sha256:" + ("1" * 64),
    )

    state = ExperimentState(
        run_id="R_bind_mismatch",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )
    outcome = BindFoundryInputsNode(strict_model_spec_match=True).execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"


def test_bind_foundry_inputs_node_carries_shape_warning_for_survey_snapshots(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(
        store,
        stats={
            "data_shape": "survey_repeated_cross_section",
            "survey_year_field": "survey_year",
            "wave_field": "wave",
            "sample_weight_field": "sample_weight",
        },
    )
    trinity_ref = _put_trinity_bundle(
        store,
        registry_bundle_ref=registry_bundle_ref,
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
    )

    state = ExperimentState(
        run_id="R_bind_shape",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )

    outcome = BindFoundryInputsNode().execute(ctx, state)
    assert outcome.status == "ok"

    bindings_ref = outcome.state.inputs[INPUT_INPUT_BINDINGS_REF]
    payload = from_canonical_bytes(store.get_bytes(bindings_ref.artifact_id))
    bindings = FoundryInputBindings.model_validate(payload)
    assert "snapshot.data_shape=survey_repeated_cross_section" in bindings.notes
    assert any(
        "panel SCM/DiD/econometrics" in note
        for note in bindings.notes
        if note.startswith("warning:")
    )


def test_bind_foundry_inputs_build_assertion_is_not_swallowed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    ctx, registry_bundle_ref = _setup_ctx(store)
    data_snapshot_ref = _put_data_snapshot(store)
    trinity_ref = _put_trinity_bundle(
        store,
        registry_bundle_ref=registry_bundle_ref,
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
    )

    state = ExperimentState(
        run_id="R_bind_assert",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
    )

    with (
        patch(
            "polisyos.scientist.nodes.builtins.data.bind_foundry_inputs.build_input_bindings",
            side_effect=AssertionError("binding invariant"),
        ),
        pytest.raises(AssertionError, match="binding invariant"),
    ):
        BindFoundryInputsNode().execute(ctx, state)
