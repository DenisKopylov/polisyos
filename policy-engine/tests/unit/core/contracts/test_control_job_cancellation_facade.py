"""Public cancellation request identity and supported input boundaries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import polisyos.core.contracts as contracts
import polisyos.core.contracts.control as control
from polisyos.core.contracts import ControlJobCancellationRequest
from polisyos.core.contracts.control import (
    ControlJobCancellationRequest as ControlJobCancellationRequestOwner,
)


def test_cancellation_request_resolves_from_the_stable_public_facade() -> None:
    """The public import and canonical contract name are the same real class."""
    assert ControlJobCancellationRequest is ControlJobCancellationRequestOwner
    assert contracts.ControlJobCancellationRequest is control.ControlJobCancellationRequest
    assert "ControlJobCancellationRequest" in contracts.__all__
    assert "ControlJobCancellationRequest" in control.__all__

    request = ControlJobCancellationRequest(
        operation_id="cancel-operation",
        expected_lease_owner="worker-a",
        expected_attempt=7,
    )
    assert request.model_dump(mode="json") == {
        "operation_id": "cancel-operation",
        "expected_lease_owner": "worker-a",
        "expected_attempt": 7,
    }
    assert (
        ControlJobCancellationRequestOwner.model_validate_json(
            request.model_dump_json(), strict=True
        )
        == request
    )
    with pytest.raises(ValidationError, match="frozen"):
        setattr(request, "operation_id", "changed")  # noqa: B010 - exercise frozen assignment


@pytest.mark.parametrize(
    "payload",
    [
        {"operation_id": ""},
        {"operation_id": "x" * 257},
        {"operation_id": "cancel", "expected_lease_owner": "worker-a"},
        {"operation_id": "cancel", "expected_attempt": 1},
        {"operation_id": "cancel", "expected_lease_owner": "", "expected_attempt": 1},
        {"operation_id": "cancel", "expected_lease_owner": "worker-a", "expected_attempt": -1},
        {"operation_id": "cancel", "tenant_id": "claimed-tenant"},
        {"operation_id": "cancel", "authorized_actor": "claimed-actor"},
    ],
)
def test_cancellation_request_rejects_incomplete_or_untrusted_fields(
    payload: dict[str, object],
) -> None:
    """The ordinary request parser forbids extra fields and incomplete identity."""
    with pytest.raises(ValidationError):
        ControlJobCancellationRequest.model_validate(payload)


@pytest.mark.parametrize("attempt", ["1", True])
def test_explicit_strict_validation_does_not_coerce_attempt(attempt: object) -> None:
    """Strict mode rejects string and boolean attempts; this is not an HTTP-mode claim."""
    with pytest.raises(ValidationError):
        ControlJobCancellationRequest.model_validate(
            {
                "operation_id": "cancel",
                "expected_lease_owner": "worker-a",
                "expected_attempt": attempt,
            },
            strict=True,
        )


def test_pending_cancellation_request_has_no_attempt_precondition() -> None:
    """A pending job request retains the paired absent attempt fields."""
    pending = ControlJobCancellationRequest.model_validate({"operation_id": "cancel-pending"})
    assert pending.expected_lease_owner is None
    assert pending.expected_attempt is None
