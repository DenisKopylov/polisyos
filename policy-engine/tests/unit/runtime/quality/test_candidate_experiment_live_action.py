"""Owner-bound refusal tests for the candidate experiment live action seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.quality.candidate_acquisition_action import (
    _current_candidate_experiment_action,
)
from tests._helpers.lane01_candidate_action_served import build_candidate_port_owners


def test_candidate_experiment_action_requires_canonical_control_owner_before_replay(
    tmp_path: Path,
) -> None:
    """A real SQLite-backed bridge without its composed Control owner cannot admit a phase."""
    owners = build_candidate_port_owners(tmp_path)
    try:
        with pytest.raises(TypeError, match="candidate_action_canonical_bridge_required"):
            _current_candidate_experiment_action(
                owners.bridge,
                None,
                "sha256:" + "a" * 64,
            )
    finally:
        owners.control_store.close()
