"""Integration entrypoint for the canonical real served-acquisition fixture."""

from __future__ import annotations

from tests._helpers.acquisition_served_history import (
    _produce_served_acquisition_history,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_served_acquisition_selects_committed_human_authority_and_reopens_worker(
    tmp_path, monkeypatch, served_recorded_candidate_gateway
):
    _produce_served_acquisition_history(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
    )
