"""Distinguishing witnesses for honest PolisySimulator training results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from polisyos.foundry.agent_sim.training import TrainingConfig
from polisyos.foundry.plugins.api import PolisySimulator, SimulationResult, TrainingResult
from polisyos.foundry.plugins.cli import cmd_train
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin


@pytest.fixture
def simulator() -> PolisySimulator:
    """Build a real composite simulator with no compatible trainer adapter."""

    registry = PluginRegistry()
    registry.clear()
    registry.register(EconomicsPlugin())
    return PolisySimulator(registry, auto_discover=False).add_domain(
        "economics",
        DomainConfig(n_agents=10),
    )


def test_train_without_execution_adapter_is_typed_bridge_pending(
    simulator: PolisySimulator,
) -> None:
    """Preserve rollout evaluation without claiming a learned policy or loss."""

    rollout = simulator.run(n_steps=2, seed=7)
    result = simulator.train(
        n_episodes=1,
        training_config=TrainingConfig(n_episodes=1, steps_per_episode=1),
        seed=7,
    )

    assert isinstance(rollout, SimulationResult)
    assert rollout.n_steps == 2
    assert rollout.trajectory is not None
    assert len(rollout.trajectory) == 3
    assert isinstance(result, TrainingResult)
    assert getattr(result, "status", None) == "bridge_pending"
    reason = getattr(result, "reason", None)
    assert reason is not None
    assert getattr(reason, "status", None) == "bridge_pending"
    assert getattr(reason, "code", None) == "training_execution_adapter_missing"
    assert result.trained_policy is None
    assert result.loss_history == []


def test_cmd_train_does_not_report_success_for_bridge_pending_training(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI output must expose the capability boundary, not fake completion metrics."""

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"domains": {"economics": {"n_agents": 10}}}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    cmd_train(
        argparse.Namespace(
            config=config_path,
            domain=None,
            n_episodes=1,
            output=output_dir,
        )
    )

    output = capsys.readouterr().out
    assert "Training complete!" not in output
    assert "Final loss:" not in output
    assert "bridge_pending" in output
    assert "training_execution_adapter_missing" in output
