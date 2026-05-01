from __future__ import annotations

from polisyos.scientist.evals.challenge_factory import REQUIRED_CHALLENGE_CLASSES
from polisyos.scientist.evals.red_team import (
    default_red_team_scenario_registry,
    red_team_registry_missing_classes,
)


def test_default_red_team_registry_covers_all_required_challenge_classes() -> None:
    registry = default_red_team_scenario_registry()

    assert red_team_registry_missing_classes(registry) == []
    assert {item.challenge_class for item in registry} == set(REQUIRED_CHALLENGE_CLASSES)
    assert all(item.risk_tags for item in registry)
