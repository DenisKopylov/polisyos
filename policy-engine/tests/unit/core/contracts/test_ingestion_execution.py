"""Load-bearing execution and selected-session compatibility boundaries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.contracts.control import IngestRequest
from polisyos.core.contracts.fabric import EvidenceBundle, IngestionExecutionContext


def test_selected_replay_context_and_request_refuse_unbound_or_conflicting_views() -> None:
    selected = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="fabric.record_session",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    context = IngestionExecutionContext(
        mode="replay", capture_session_id="session", selected_record_session_ref=selected
    )
    assert IngestionExecutionContext.model_validate_json(context.model_dump_json()) == context
    with pytest.raises(ValidationError, match="selected_record_session"):
        IngestionExecutionContext(mode="replay", capture_session_id="session")
    with pytest.raises(ValidationError, match="completed_session"):
        IngestionExecutionContext(
            mode="record", capture_session_id="session", selected_record_session_ref=selected
        )
    request_inputs = {"datasets": [{"connector_id": "source", "dataset_id": "rows"}]}
    admitted = IngestRequest(
        **request_inputs,
        replay_ref=str(selected.artifact_id),
        replay_selected_ref=selected,
    )
    assert admitted.replay_selected_ref == selected
    with pytest.raises(ValidationError, match="conflict"):
        IngestRequest(
            **request_inputs,
            replay_ref="sha256:" + "c" * 64,
            replay_selected_ref=selected,
        )
    with pytest.raises(ValidationError, match="profile"):
        IngestRequest(
            **request_inputs,
            replay_selected_ref=selected.model_copy(update={"manifest_profile_sha256": None}),
        )


def test_ordinary_legacy_wire_omits_new_optional_execution_and_selector_fields() -> None:
    request = IngestRequest(datasets=[{"connector_id": "source", "dataset_id": "rows"}])
    assert "replay_selected_ref" not in request.model_dump(mode="json")
    assert "execution_context" not in EvidenceBundle().model_dump(mode="json")
