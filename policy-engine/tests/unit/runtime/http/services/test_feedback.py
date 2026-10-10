from __future__ import annotations

from polisyos.core.security import tenant_scope
from polisyos.runtime.http.services.feedback import FeedbackService


def test_feedback_evaluation_does_not_change_a_sibling_runs_packet_or_feedback(
    runtime_api_env,
) -> None:
    context = runtime_api_env["app"].state.runtime_api_ctx
    run_index = context.run_index
    selected_run = run_index.get_run(runtime_api_env["core_run_id"])
    sibling_run = run_index.get_run(runtime_api_env["core_run_id_secondary"])
    assert selected_run.decision_packet_ref is not None
    assert sibling_run.decision_packet_ref is not None
    assert selected_run.decision_packet_ref.artifact_id != (
        sibling_run.decision_packet_ref.artifact_id
    )
    owner_tenant_id = sibling_run.summary.tenant_id
    owner_cell_id = sibling_run.summary.cell_id
    assert owner_tenant_id is not None
    assert owner_cell_id is not None
    assert selected_run.summary.tenant_id == owner_tenant_id
    assert selected_run.summary.cell_id == owner_cell_id

    service = FeedbackService(store=context.store, run_index=run_index)
    with tenant_scope(None, tenant_id=owner_tenant_id, cell_id=owner_cell_id):
        sibling_packet_before = context.store.get_bytes(sibling_run.decision_packet_ref)
        sibling_feedback_before = service.get_run_feedback(sibling_run)
        selected_feedback, monitoring_ref, compare_ref, reissue_ref = service.evaluate_run_feedback(
            selected_run
        )
        sibling_feedback_after = service.get_run_feedback(sibling_run)
        sibling_packet_after = context.store.get_bytes(sibling_run.decision_packet_ref)

    assert selected_feedback.run_id == selected_run.run_id
    assert monitoring_ref is not None
    assert compare_ref is not None
    assert reissue_ref is not None
    assert sibling_packet_after == sibling_packet_before
    assert sibling_feedback_after.run_id == sibling_run.run_id
    assert sibling_feedback_after.feedback_loop == sibling_feedback_before.feedback_loop
    assert sibling_feedback_after.monitoring_contract == sibling_feedback_before.monitoring_contract
    assert sibling_feedback_after.monitoring_report == sibling_feedback_before.monitoring_report
    assert sibling_feedback_after.compare_report == sibling_feedback_before.compare_report
    assert sibling_feedback_after.reissue_plan == sibling_feedback_before.reissue_plan
