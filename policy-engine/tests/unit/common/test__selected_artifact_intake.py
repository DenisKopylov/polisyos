from __future__ import annotations

import pytest


def test_optional_selected_artifact_distinguishes_absence_and_refusal() -> None:
    from polisyos.common._selected_artifact_intake import (
        read_optional_selected_artifact,
    )
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError

    assert (
        read_optional_selected_artifact(
            None,
            lambda _selector: {"status": "pass"},
            refusal_code="selected_payload_unavailable",
            expected_errors=(OSError, ValueError),
        )
        is None
    )
    assert read_optional_selected_artifact(
        "selected",
        lambda selector: {"selector": selector},
        refusal_code="selected_payload_unavailable",
        expected_errors=(OSError, ValueError),
    ) == {"selector": "selected"}

    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        read_optional_selected_artifact(
            "selected",
            lambda _selector: (_ for _ in ()).throw(ValueError("bad selected bytes")),
            refusal_code="selected_payload_unavailable",
            expected_errors=(OSError, ValueError),
        )
    assert refusal.value.code == "selected_payload_unavailable"
    assert isinstance(refusal.value.__cause__, ValueError)

    with pytest.raises(CanonicalProfileRefusalError) as missing_payload:
        read_optional_selected_artifact(
            "selected",
            lambda _selector: None,
            refusal_code="selected_payload_unavailable",
            expected_errors=(OSError, ValueError),
        )
    assert missing_payload.value.code == "selected_payload_unavailable"


def test_optional_selected_artifact_does_not_relabel_unexpected_internal_errors() -> None:
    from polisyos.common._selected_artifact_intake import (
        read_optional_selected_artifact,
    )

    class InternalInvariantError(Exception):
        pass

    try:
        read_optional_selected_artifact(
            "selected",
            lambda _selector: (_ for _ in ()).throw(InternalInvariantError("bug")),
            refusal_code="selected_payload_unavailable",
            expected_errors=(OSError, ValueError),
        )
    except InternalInvariantError:
        pass
    else:
        raise AssertionError("unexpected internal errors must keep their original type")
