"""Behavioral witnesses for native membership growth and empty deployment slots."""

from types import SimpleNamespace

import pytest

from polisyos.runtime.quality import acquisition_world_growth as growth


def _epoch(*, count=3, active="active", passport="passport"):
    return SimpleNamespace(
        epoch_id=7,
        passport_id=passport,
        epoch_activation_state=active,
        admitted_observation_count=count,
    )


@pytest.mark.parametrize(
    ("before", "expected"),
    [
        ((), 3),
        ((_epoch(),), 0),
        ((_epoch(active="pending_semantic_epoch"),), 3),
    ],
)
def test_membership_delta_counts_only_new_active_native_membership(before, expected):
    assert (
        growth.admitted_membership_delta(
            before=before, after=(_epoch(),), epoch_id=7, passport_id="passport"
        )
        == expected
    )


@pytest.mark.parametrize(
    "after",
    [
        (),
        (_epoch(active="pending_semantic_epoch"),),
        (_epoch(), _epoch()),
        (_epoch(passport="other"),),
    ],
)
def test_membership_delta_refuses_absent_ambiguous_or_other_passport(after):
    with pytest.raises(ValueError, match="acquisition_active_membership_unresolved"):
        growth.admitted_membership_delta(before=(), after=after, epoch_id=7, passport_id="passport")


def test_membership_delta_refuses_prior_epoch_replacement():
    with pytest.raises(ValueError, match="acquisition_prior_membership_changed"):
        growth.admitted_membership_delta(
            before=(_epoch(passport="other"),),
            after=(_epoch(),),
            epoch_id=7,
            passport_id="passport",
        )
