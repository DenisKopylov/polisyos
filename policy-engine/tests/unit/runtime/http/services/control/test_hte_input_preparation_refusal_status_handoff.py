"""Exercise the retained HTE source-usage status at the Runtime handoff."""

from __future__ import annotations

import pytest

from polisyos.foundry.data_plane.bindings import HTEInputPreparationRefusal
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    _refusal_capture_from_exception,
)


@pytest.mark.parametrize(
    ("source_usage_complete", "expected_source_bytes"),
    [(True, 23), (False, None)],
)
def test_runtime_capture_preserves_producer_usage_completeness(
    source_usage_complete: bool,
    expected_source_bytes: int | None,
) -> None:
    refusal = HTEInputPreparationRefusal(
        "selected_source_read_refused",
        observed_manifest_selection_bytes=5,
        observed_manifest_verification_bytes=7,
        observed_payload_bytes=11,
        payload_integrity_verified=False,
        source_usage_complete=source_usage_complete,
        failure_stage="hte_selected_source_read",
    )

    capture = _refusal_capture_from_exception(refusal)

    assert refusal.source_usage_complete is source_usage_complete
    assert capture.source_usage_complete is source_usage_complete
    assert capture.observed_source_bytes == expected_source_bytes
    assert capture.observed_manifest_selection_bytes == 5
    assert capture.observed_manifest_verification_bytes == 7
    assert capture.observed_payload_bytes == 11


def test_runtime_capture_refuses_missing_usage_completeness_status() -> None:
    refusal = HTEInputPreparationRefusal("selected_source_read_refused")
    del refusal.source_usage_complete

    with pytest.raises(ValueError, match="owned_attempt_refusal_usage_status_invalid"):
        _refusal_capture_from_exception(refusal)


def test_runtime_capture_refuses_non_bool_usage_completeness_status() -> None:
    refusal = HTEInputPreparationRefusal("selected_source_read_refused")
    refusal.source_usage_complete = 1

    with pytest.raises(ValueError, match="owned_attempt_refusal_usage_status_invalid"):
        _refusal_capture_from_exception(refusal)
