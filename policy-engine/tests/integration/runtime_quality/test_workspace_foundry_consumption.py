from __future__ import annotations

import hashlib

import pytest

from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.pdc import OperationClass
from polisyos.runtime.quality.workspace.foundry_consumption import (
    ConstraintStoreIngestor,
    FoundryMethodOutputConsumer,
)
from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
    _constraint_canonical_problem,
    _method_owner_case,
)
from tests.unit.runtime.quality.test_workspace_foundry_consumption import (
    recorded_panel_owner as _recorded_panel_owner,
)

pytestmark = pytest.mark.integration
recorded_panel_owner = _recorded_panel_owner


@pytest.fixture(autouse=True)
def _reset_foundry_method_singletons():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodDispatcher.reset_instance()
    MethodRegistry.reset_instance()


def test_phase2_method_consumption_binds_real_source_and_reconciled_constraint_refusal(
    recorded_panel_owner,
) -> None:
    """Direct method custody is limited; this is not guarded-node or institutional admission."""
    store, binding, state = _method_owner_case(recorded_panel_owner)
    constraint_owner = ConstraintStoreIngestor(store=store)
    admission = constraint_owner.produce(
        workspace_id="ws-phase2-foundry",
        design_problem=_constraint_canonical_problem(),
    )
    preflight = from_canonical_bytes(
        constraint_owner.require(admission, workspace_id=admission.workspace_id)
    )
    assert preflight["evaluation_phase"] == "requirement_preflight"
    assert preflight["missing_basis"] == ["constraint_requirement_basis_missing"]
    assert preflight["decision"]["blocks_promotion"] is True

    consumer = FoundryMethodOutputConsumer(store=store)
    consumed = consumer.consume_from_state(
        workspace_id=admission.workspace_id,
        operation_invocation_id="invoke-estimate",
        operation_class=OperationClass.ESTIMATE,
        state=state,
        measurement_root_ref=binding.observational_data_ref,
        binding_receipt_ref=binding.binding_receipt_ref,
        constraint_store_ref=str(admission.artifact_ref.artifact_id),
        constraint_owner=constraint_owner,
        constraint_admission=admission,
    )

    assert {ref.artifact_id for ref in consumed.record.consumed_method_output_refs} == {
        str(state.artifacts_index["causal_method_result_ref"].artifact_id)
    }
    assert {ref.artifact_id for ref in consumed.record.consumed_method_evidence_refs} == {
        str(state.artifacts_index["causal_method_evidence_ref"].artifact_id)
    }
    assert consumed.record.dag_consumed_method_outputs_count == len(
        consumed.record.consumed_method_output_refs
    )
    assert consumed.input_provenance == "measurement_rooted"
    assert consumed.authority_boundary.evidence_kind == "measurement"
    assert consumed.authority_boundary.decision_grade == "descriptive_only"
    assert "causal_identification" in consumed.authority_boundary.may_not_use_for
    assert "production_recommendation" in consumed.authority_boundary.may_not_use_for
    assert consumed.constraint_decision is not None
    assert consumed.constraint_decision.blocks_promotion is True

    persisted_ref = consumer.persist_consumption(store=store, consumption=consumed)
    raw = store.get_bytes(persisted_ref.artifact_id)
    assert persisted_ref.content_hash == "sha256:" + hashlib.sha256(raw).hexdigest()
    payload = from_canonical_bytes(raw)
    assert payload["input_binding_receipt_ref"] == consumed.input_binding_receipt_ref.model_dump(
        mode="json"
    )
    assert payload["constraint_decision"] == consumed.constraint_decision.model_dump(mode="json")
    post_ref = consumed.record.constraint_store_ref
    assert post_ref is not None
    assert post_ref != str(admission.artifact_ref.artifact_id)
    post = from_canonical_bytes(store.get_bytes(post_ref))
    assert post["evaluation_phase"] == "post_execution_reconciliation"
    assert post["method_consumption_hash"] is not None
    assert post["method_report_ref"] is not None
    assert post["missing_basis"] == preflight["missing_basis"]
    assert post["decision"]["blocks_promotion"] is True
    assert post["decision"] == payload["constraint_decision"]
    manifest = store.get_manifest(persisted_ref.artifact_id)
    assert {str(ref.artifact_id) for ref in manifest.inputs if ref.role == "constraint_store"} == {
        post_ref
    }
    for ref in (
        *consumed.record.consumed_method_output_refs,
        *consumed.record.consumed_method_evidence_refs,
        *consumed.record.measurement_root_refs,
    ):
        assert (
            ref.content_hash
            == "sha256:" + hashlib.sha256(store.get_bytes(ref.artifact_id)).hexdigest()
        )


def test_foundry_consumer_rejects_untyped_synthetic_string_as_measurement_root(
    recorded_panel_owner,
) -> None:
    store, binding, state = _method_owner_case(recorded_panel_owner)
    consumer = FoundryMethodOutputConsumer(store=store)
    with pytest.raises(ValueError, match="foundry_consumption_unverified"):
        consumer.consume_from_state(
            workspace_id="ws-phase2-foundry",
            operation_invocation_id="invoke-estimate-string",
            operation_class=OperationClass.ESTIMATE,
            state=state,
            measurement_root_ref="direct_synthetic_string",
            binding_receipt_ref=binding.binding_receipt_ref,
        )
