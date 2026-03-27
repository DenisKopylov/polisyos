from __future__ import annotations

from polisyos.scientist.nodes.builtins.planning.ready_to_run import ReadyToRunNode


def test_ready_to_run_passes(execution_context, minimal_state):
    state = minimal_state.model_copy(update={"params": {"preflight_ready": True}})
    outcome = ReadyToRunNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert any("passed" in e.message.lower() for e in outcome.events)


def test_ready_to_run_blocks_when_not_ready(execution_context, minimal_state):
    state = minimal_state.model_copy(update={"params": {"preflight_ready": False}})
    outcome = ReadyToRunNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"


def test_ready_to_run_blocks_when_key_missing(execution_context, minimal_state):
    outcome = ReadyToRunNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    assert outcome.error.details["preflight_diagnostics"] == []
