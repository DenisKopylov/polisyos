"""Distinguishing witnesses for honest PolisySimulator training results."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

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
    monkeypatch: pytest.MonkeyPatch,
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
    original_train = PolisySimulator.train
    observed_results: list[TrainingResult] = []

    def observe_train_result(
        simulator: PolisySimulator,
        n_episodes: int = 100,
        training_config=None,
        seed: int = 42,
        output_dir: Path | None = None,
        artifact_store=None,
    ) -> TrainingResult:
        result = original_train(
            simulator,
            n_episodes=n_episodes,
            training_config=training_config,
            seed=seed,
            output_dir=output_dir,
            artifact_store=artifact_store,
        )
        observed_results.append(result)
        return result

    monkeypatch.setattr(PolisySimulator, "train", observe_train_result)
    cmd_train(
        argparse.Namespace(
            config=config_path,
            domain=None,
            n_episodes=1,
            output=output_dir,
        )
    )

    output = capsys.readouterr().out
    assert len(observed_results) == 1
    result = observed_results[0]
    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.status == "bridge_pending"
    assert result.reason.code == "training_composite_profile_unsupported"
    assert result.trained_policy is None
    assert result.loss_history == []
    assert result.artifact is None
    assert result.artifact_refs is None
    assert "Training complete!" not in output
    assert "PPO loss:" not in output
    assert "Final loss:" not in output
    assert "Artifact:" not in output
    assert "bridge_pending" in output
    assert "training_composite_profile_unsupported" in output
    assert not output_dir.exists()


@pytest.mark.parametrize("usage_error", [False, True], ids=["unsupported", "invalid-usage"])
def test_real_cli_process_distinguishes_unsupported_training_from_usage(
    tmp_path: Path, usage_error: bool
) -> None:
    """The actual CLI process preserves refusal and argparse exit semantics."""
    config_path = tmp_path / "unsupported.json"
    config_path.write_text(
        json.dumps(
            {
                "domains": {
                    "economics": {
                        "n_agents": 10,
                        "max_agents": 10,
                        "enabled_mechanisms": ["taxation", "transfers", "consumption", "savings"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "not-created"
    command = [
        sys.executable,
        "-B",
        "-m",
        "polisyos.foundry.plugins.cli",
        "train",
        "--config",
        str(config_path),
        "--n-episodes",
        "invalid" if usage_error else "1",
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=45)
    assert completed.returncode == (2 if usage_error else 1), completed.stdout + completed.stderr
    if usage_error:
        assert "invalid int value" in completed.stderr
    else:
        assert "training_composite_profile_unsupported" in completed.stdout
        assert "bridge_pending" in completed.stdout
        assert "Training complete!" not in completed.stdout
        assert "PPO loss:" not in completed.stdout
    assert not output.exists()
