"""Full bound-mutation consumption, with unchanged signed DS9 owner evidence."""

from pathlib import Path

import pytest

from tests.unit.runtime.http.test_human_decision_service import (
    _bound_mutation_permission,
    _contracts,
    _human_decision_record_ids,
    _service_module,
    _signed_current_gate_fixture,
)


def _case(tmp_path: Path):
    fixture = _signed_current_gate_fixture(tmp_path)
    command = _contracts().HumanDecisionCreateCommand(
        gate_input=fixture.adapter_input,
        decision_action="approve",
        decision_mode="ordinary",
        accountability_statement="I accept accountability for this exact action.",
        dissent_statement="Disconfirming evidence remains retained.",
    )
    return fixture, command


def test_complete_binder_mutation_reaches_actual_custody_writer(tmp_path: Path) -> None:
    fixture, command = _case(tmp_path)
    receipt = fixture.service.create_record(
        command,
        bound_permission=_bound_mutation_permission(fixture.bound_permission, command),
        write_context=fixture.write_context,
    )
    assert receipt.record.source_ref == command.gate_input.source_ref
    assert receipt.record_ref in _human_decision_record_ids(fixture.store)


@pytest.mark.parametrize(
    "field", ["source_ref", "exposure_session_ref", "accountability_statement", "decision_action"]
)
def test_changed_bound_mutation_cannot_create_original_signed_decision(
    tmp_path: Path, field: str
) -> None:
    fixture, command = _case(tmp_path)
    if field in {"source_ref", "exposure_session_ref"}:
        different = command.model_copy(
            update={
                "gate_input": command.gate_input.model_copy(update={field: "sha256:" + "0" * 64})
            }
        )
    else:
        different = command.model_copy(
            update={
                field: "reject"
                if field == "decision_action"
                else "A different accountability statement."
            }
        )
    proof = _bound_mutation_permission(fixture.bound_permission, different)
    before = _human_decision_record_ids(fixture.store)
    with pytest.raises(
        _service_module().HumanDecisionOperationalResolutionError,
        match="DS9-DECISION-PERMISSION-UNVERIFIED",
    ):
        fixture.service.create_record(
            command,
            bound_permission=proof,
            write_context=fixture.write_context,
        )
    assert _human_decision_record_ids(fixture.store) == before
