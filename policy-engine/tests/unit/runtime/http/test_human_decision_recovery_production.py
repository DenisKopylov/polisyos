"""The production-basis arm uses the same custody recovery owner, without publication."""

from pathlib import Path

from tests.unit.runtime.http import test_human_decision_service as cases
from tests.unit.runtime.http.test_human_decision_recovery import _create, _permission


def test_production_basis_record_is_recovered_without_publication_authority(tmp_path: Path):
    production = cases._signed_current_production_gate_fixture(tmp_path)
    fixture = production.base
    command = cases._contracts().HumanDecisionCreateCommand(
        gate_input=production.gate_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept this exact bounded production decision.",
        dissent_statement="Limitations and disconfirming evidence remain material.",
    )
    receipt = _create(fixture, command)
    result = fixture.service.recover_record(
        command,
        bound_permission=_permission(fixture, command),
        cell_id=fixture.write_context.cell_id,
    )
    assert receipt.record.source_kind == "production_approval"
    assert result.status == "committed", result
    assert str(result.record_ref.artifact_id) == receipt.record_ref
    assert result.durable_event_id == receipt.durable_event_id
    assert result.operational_authority is False
    assert fixture.effects == []
