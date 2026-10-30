"""Process-level exit semantics for the legacy plugin CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim.training import TrainingConfig
from polisyos.foundry.plugins.api import PolisySimulator, TrainingResult
from polisyos.foundry.plugins.cli import main


def _run_plugins_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the actual module CLI against this checkout's source tree."""
    product_root = Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    pythonpath = [str(product_root / "src"), str(product_root)]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return subprocess.run(
        [sys.executable, "-m", "polisyos.foundry.plugins.cli", *args],
        cwd=product_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
    )


def test_list_command_exits_successfully() -> None:
    """A valid non-training command retains the ordinary success exit code."""
    completed = _run_plugins_cli("list")

    assert completed.returncode == 0
    assert "Available Plugins (" in completed.stdout


def test_invalid_training_argument_exits_with_usage_error() -> None:
    """Argument errors remain distinguishable from a typed training refusal."""
    completed = _run_plugins_cli("train", "--n-episodes", "not-an-integer")

    assert completed.returncode == 2
    assert "usage:" in completed.stderr
    assert "invalid int value" in completed.stderr


def test_supported_training_returns_success_after_real_native_update(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLI success status follows a real admitted native training result."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"domains": {"economics": {"n_agents": 10, "max_agents": 10}}}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "output"
    original_train = PolisySimulator.train
    observed_results: list[TrainingResult] = []

    def train_supported_profile(
        simulator: PolisySimulator,
        n_episodes: int = 100,
        training_config=None,
        seed: int = 42,
        output_dir: Path | None = None,
        artifact_store=None,
    ) -> TrainingResult:
        if simulator._state is None:
            simulator.initialize(7)
        state = simulator.get_state()
        domain = state.get_domain("economics")
        agents = domain.agents
        wealth = jnp.full_like(agents.wealth, 1_000_000.0)
        agents = agents.replace(wealth=jnp.where(agents.active, wealth, agents.wealth))
        domain = domain.replace(agents=agents).update_aggregates()
        assert domain.validate()
        simulator._state = state.update_domain("economics", domain)

        result = original_train(
            simulator,
            n_episodes=n_episodes,
            training_config=TrainingConfig(
                n_episodes=n_episodes,
                steps_per_episode=2,
                horizon=12,
                ppo_epochs=1,
                learning_rate=1e-2,
            ),
            seed=7,
            output_dir=output_dir,
            artifact_store=artifact_store,
        )
        observed_results.append(result)
        return result

    monkeypatch.setattr(PolisySimulator, "train", train_supported_profile)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "polisy",
            "train",
            "--config",
            str(config_path),
            "--n-episodes",
            "1",
            "--output",
            str(output_dir),
        ],
    )

    exit_code = main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert len(observed_results) == 1
    result = observed_results[0]
    assert result.status == "trained"
    assert result.reason is None
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.loss_history
    assert "Training complete!" in output
    assert "PPO loss:" in output
    assert "Artifact:" in output
    assert "Final loss:" not in output


def test_blocked_training_exits_unsuccessfully_without_claiming_a_model(
    tmp_path: Path,
) -> None:
    """An unsupported composite remains bridge_pending at the real CLI boundary."""
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

    completed = _run_plugins_cli(
        "train",
        "--config",
        str(config_path),
        "--n-episodes",
        "1",
        "--output",
        str(output_dir),
    )

    assert completed.returncode == 1
    assert "Training bridge pending." in completed.stdout
    assert "bridge_pending" in completed.stdout
    assert "training_composite_profile_unsupported" in completed.stdout
    assert "Training complete!" not in completed.stdout
    assert "PPO loss:" not in completed.stdout
    assert "Artifact:" not in completed.stdout
    assert not output_dir.exists()
