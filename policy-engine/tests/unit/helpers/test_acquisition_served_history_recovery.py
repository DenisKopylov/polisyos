"""The served caller retains its exact submission across a missing receipt.

These are transport/lifetime controls for the test caller. The real signed
custody owner and public endpoint are qualified by the maintained HTTP cases.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from tests._helpers.acquisition_served_history import (
    TENANT,
    _recover_served_human_decision,
    _submit_served_human_decision,
)

RECORD_REF = "sha256:" + "a" * 64
EXPOSURE_REF = "sha256:" + "e" * 64


def _response(status_code: int, payload: dict):
    return SimpleNamespace(status_code=status_code, json=lambda: payload, text=json.dumps(payload))


def _committed() -> dict:
    return {
        "schema_version": "policyos.runtime.human_decision_recovery.v1",
        "tenant_id": TENANT,
        "cell_id": None,
        "run_id": "run-original",
        "operational_authority": False,
        "authority_purpose": "historical_human_decision_custody_only",
        "status": "committed",
        "record_ref": {
            "artifact_id": RECORD_REF,
            "kind": "runtime_quality.agent_action_human_decision",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        },
        "record_digest": RECORD_REF,
        "durable_event_id": "event-original",
        "reservation_id": "reservation-original",
        "reservation_version": 1,
        "binding_sha256": "sha256:" + "c" * 64,
        "binding_rule": "policyos.runtime.human_decision_submission_binding.v2",
        "reservation_state": "committed",
        "record_valid_until": "2026-11-15T17:56:41Z",
    }


class _ReaderClient:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        return next(self.responses)


def _checkpoint(path: Path, body: dict) -> None:
    path.write_text(
        json.dumps({"run_id": "run-original", "body": body, "exposure_session_ref": EXPOSURE_REF})
    )


def test_saved_submission_precedes_create_and_lost_ack_never_repeats_create(tmp_path: Path):
    checkpoint = tmp_path / "request.json"
    body = {"accountability_statement": "The original submitted statement."}
    create_calls = []

    def post(_client, path, submitted, **kwargs):
        saved = json.loads(checkpoint.read_text())
        assert saved["body"] == submitted == body
        assert saved["exposure_session_ref"] == EXPOSURE_REF
        create_calls.append((path, kwargs))
        return _response(503, {"code": "human_decision_custody_nonreceipt"}), "unused"

    committed = _committed()
    pending = {
        name: value
        for name, value in committed.items()
        if name
        in {
            "schema_version",
            "tenant_id",
            "cell_id",
            "run_id",
            "operational_authority",
            "authority_purpose",
            "reservation_id",
            "reservation_version",
            "binding_sha256",
            "binding_rule",
        }
    } | {"status": "pending"}
    trust = SimpleNamespace(post=post, authorization_header=lambda subject: f"Bearer {subject}")
    client = _ReaderClient(_response(200, pending), _response(200, committed))
    result = _submit_served_human_decision(
        client,
        run_id="run-original",
        body=body,
        exposure_session_ref=EXPOSURE_REF,
        trust=trust,
        submission_checkpoint=checkpoint,
    )
    assert result == RECORD_REF
    assert len(create_calls) == 1
    saved_bytes = checkpoint.read_bytes()
    restarted = _ReaderClient(_response(200, committed))
    assert (
        _recover_served_human_decision(restarted, submission_checkpoint=checkpoint, trust=trust)
        == result
    )
    assert checkpoint.read_bytes() == saved_bytes
    assert len(create_calls) == 1
    for path, call in client.calls + restarted.calls:
        assert path == "/api/v1/runs/run-original/human-decisions/recovery"
        assert call["json"] == body
        assert call["headers"]["X-PolicyOS-Human-Decision-Exposure"] == EXPOSURE_REF
        assert "X-PolicyOS-Step-Up" not in call["headers"]


@pytest.mark.parametrize("status_code", [201, 503])
def test_default_caller_keeps_its_original_create_expectation(status_code: int):
    client = _ReaderClient()
    payload = (
        {"record_ref": RECORD_REF}
        if status_code == 201
        else {"code": "human_decision_custody_nonreceipt"}
    )
    trust = SimpleNamespace(
        post=lambda *args, **kwargs: (_response(status_code, payload), "unused")
    )

    def call():
        return _submit_served_human_decision(
            client,
            run_id="run-original",
            body={},
            exposure_session_ref=EXPOSURE_REF,
            trust=trust,
        )

    if status_code == 201:
        assert call() == RECORD_REF
    else:
        with pytest.raises(AssertionError, match="human_decision_custody_nonreceipt"):
            call()
    assert client.calls == []


def test_existing_submission_is_never_overwritten_or_sent_again(tmp_path: Path):
    checkpoint = tmp_path / "request.json"
    _checkpoint(checkpoint, {"original": "body"})
    before = checkpoint.read_bytes()
    create_calls = []
    trust = SimpleNamespace(post=lambda *args, **kwargs: create_calls.append(args))
    with pytest.raises(FileExistsError):
        _submit_served_human_decision(
            _ReaderClient(),
            run_id="run-original",
            body={"different": "body"},
            exposure_session_ref=EXPOSURE_REF,
            trust=trust,
            submission_checkpoint=checkpoint,
        )
    assert create_calls == []
    assert checkpoint.read_bytes() == before


def test_other_unavailable_response_is_not_a_recoverable_custody_nonreceipt(tmp_path: Path):
    client = _ReaderClient()
    trust = SimpleNamespace(
        post=lambda *args, **kwargs: (
            _response(503, {"code": "different_unavailable_boundary"}),
            "unused",
        )
    )
    with pytest.raises(AssertionError, match="different_unavailable_boundary"):
        _submit_served_human_decision(
            client,
            run_id="run-original",
            body={},
            exposure_session_ref=EXPOSURE_REF,
            trust=trust,
            submission_checkpoint=tmp_path / "request.json",
        )
    assert client.calls == []


@pytest.mark.parametrize("state", ["not_established", "profile_missing"])
def test_recovery_cannot_turn_an_unestablished_or_unselected_result_into_receipt(
    tmp_path: Path, state: str
):
    checkpoint = tmp_path / "request.json"
    _checkpoint(checkpoint, {"original": "body"})
    if state == "profile_missing":
        result = _committed()
        result["record_ref"].pop("manifest_profile_sha256")
        expected = ValidationError
    else:
        result = {
            name: value
            for name, value in _committed().items()
            if name
            in {
                "schema_version",
                "tenant_id",
                "cell_id",
                "run_id",
                "operational_authority",
                "authority_purpose",
            }
        } | {"status": "not_established", "reason_code": "custody_missing"}
        expected = AssertionError
    trust = SimpleNamespace(authorization_header=lambda subject: f"Bearer {subject}")
    client = _ReaderClient(_response(200, result))
    with pytest.raises(expected):
        _recover_served_human_decision(client, submission_checkpoint=checkpoint, trust=trust)
    assert len(client.calls) == 1
