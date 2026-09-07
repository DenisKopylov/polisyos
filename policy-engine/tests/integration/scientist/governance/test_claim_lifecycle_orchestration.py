"""Production Claim owner-event producer, consumer, persistence, and export witness."""

from __future__ import annotations

from tests.unit.scientist.governance.continuous.test_owner_event_producer import (
    _assert_signed_owner_event_round_trip,
)
from tests.unit.scientist.governance.continuous.test_owner_event_producer import (
    owner_event_case as _owner_event_case,
)

owner_event_case = _owner_event_case


def test_monitor_event_persists_claim_supersession_without_in_place_edit(
    owner_event_case,
) -> None:
    """A signed owner act reaches the current export while its predecessor stays immutable.

    The shared witness exercises the production monitor bridge and Claim CAS owner
    with explicit test-only institutional keys. Caller metadata alone remains a
    separate negative test and cannot produce this authority-bearing outcome.
    """

    _assert_signed_owner_event_round_trip(owner_event_case)
