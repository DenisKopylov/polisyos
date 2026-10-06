"""Distinguishing witnesses for honest PolisySimulator training results."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.foundry.agent_sim.training import TrainingConfig
from polisyos.foundry.plugins.api import PolisySimulator, SimulationResult, TrainingResult
from polisyos.foundry.plugins.cli import cmd_train
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin


@pytest.fixture
def simulator() -> PolisySimulator:
    """Build a composite with labor-market training intentionally unsupported."""

    registry = PluginRegistry()
    registry.clear()
    registry.register(EconomicsPlugin())
    return PolisySimulator(registry, auto_discover=False).add_domain(
        "economics",
        DomainConfig(
            n_agents=10,
            enabled_mechanisms=("taxation", "transfers", "consumption", "savings"),
        ),
    )


def test_train_with_labor_market_disabled_is_typed_bridge_pending(
    simulator: PolisySimulator,
) -> None:
    """Preserve rollout evaluation for an unsupported composite profile."""

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
    assert getattr(reason, "code", None) == "training_composite_profile_unsupported"
    assert result.trained_policy is None
    assert result.loss_history == []


def test_cmd_train_reports_unsupported_labor_market_profile_as_bridge_pending(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI exposes an unsupported labor-market profile without fake metrics."""

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "domains": {
                    "economics": {
                        "n_agents": 10,
                        "enabled_mechanisms": [
                            "taxation",
                            "transfers",
                            "consumption",
                            "savings",
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"

    exit_code = cmd_train(
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
    assert "training_composite_profile_unsupported" in output
    assert exit_code != 0


def test_module_cli_returns_nonzero_for_bridge_pending(
    tmp_path: Path,
) -> None:
    """The executable CLI process fails when a requested training bridge is pending."""

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "domains": {
                    "economics": {
                        "n_agents": 10,
                        "enabled_mechanisms": [
                            "taxation",
                            "transfers",
                            "consumption",
                            "savings",
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polisyos.foundry.plugins.cli",
            "train",
            "--config",
            str(config_path),
            "--n-episodes",
            "1",
            "--output",
            str(tmp_path / "output"),
        ],
        cwd=Path(__file__).parents[3],
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).parents[3] / "src"),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "bridge_pending" in completed.stdout
    assert "training_composite_profile_unsupported" in completed.stdout


def test_cmd_train_keeps_optimizer_loss_and_artifact_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The success line names optimizer loss and the persisted policy artifact."""

    class TrainedSimulator:
        def add_domain(self, _name, _config):
            return self

        def train(self, *, n_episodes, output_dir):
            assert n_episodes == 1
            assert output_dir == tmp_path / "output"
            return SimpleNamespace(
                status="trained",
                reason=None,
                loss_history=[0.25],
                artifact=SimpleNamespace(artifact_id="policy-test"),
                plot_losses=lambda _path: None,
            )

    monkeypatch.setattr(
        "polisyos.foundry.plugins.cli.PolisySimulator",
        TrainedSimulator,
    )
    output_dir = tmp_path / "output"
    exit_code = cmd_train(
        argparse.Namespace(
            config=None,
            domain=["economics"],
            n_episodes=1,
            output=output_dir,
        )
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "PPO loss: 0.2500" in output
    assert "Artifact: policy-test" in output
    assert "Final loss:" not in output
