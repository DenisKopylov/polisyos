"""Keep historical rollout traces separate from current optimizer results."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

import pytest

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.plugins import cli
from polisyos.foundry.plugins.api import TrainingCapabilityReason, TrainingResult
from polisyos.foundry.plugins.composite import CompositeState


def _result(policy: object | None = None) -> TrainingResult:
    return TrainingResult(
        cast("ActorCritic | None", policy), [2.0, 2.0], cast("CompositeState", object())
    )


def _present(monkeypatch: pytest.MonkeyPatch, result: TrainingResult, output: Path) -> int:
    class ResultSimulator:
        def add_domain(self, *_args: object) -> None:
            return None

        def train(self, **_kwargs: object) -> TrainingResult:
            return result

    monkeypatch.setattr(cli, "PolisySimulator", ResultSimulator)
    return cli.cmd_train(
        argparse.Namespace(config=None, domain=["economics"], n_episodes=1, output=output)
    )


@pytest.mark.parametrize("policy", [None, object()], ids=["no-policy", "legacy-actor"])
def test_three_positional_fields_do_not_assert_optimizer_training(policy: object | None) -> None:
    result = _result(policy)
    assert result.status != "trained"
    assert result.loss_history == [2.0, 2.0]
    assert result.trained_policy is policy


@pytest.mark.parametrize("old_layout", [False, True], ids=["constructor", "old-layout"])
def test_cli_preserves_legacy_trace_without_success_or_training_plot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    old_layout: bool,
) -> None:
    result = _result(object())
    if old_layout:
        # A trusted local compatibility fixture, never an untrusted pickle load.
        result = TrainingResult.__new__(TrainingResult)
        result.trained_policy = cast("ActorCritic", object())
        result.loss_history = [2.0, 2.0]
        result.final_state = cast("CompositeState", object())

    def unexpected_plot(*_args: object) -> None:
        raise AssertionError("an unqualified historical trace reached the optimizer plot")

    monkeypatch.setattr(result, "plot_losses", unexpected_plot)
    output = tmp_path / "not-created"
    assert _present(monkeypatch, result, output) == 1
    text = capsys.readouterr().out
    assert "Training complete!" not in text
    assert "PPO loss:" not in text
    assert not output.exists()
    assert result.loss_history == [2.0, 2.0]


@pytest.mark.parametrize("invalid", ["no-role", "wrong-role", "no-policy", "reason"])
def test_trained_status_alone_does_not_qualify_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid: str,
) -> None:
    result = _result(object())
    result.status = "trained"
    if invalid != "no-role":
        result.result_role = "native_training_v1" if invalid != "wrong-role" else "evaluation"
    if invalid == "no-policy":
        result.trained_policy = None
    if invalid == "reason":
        result.reason = TrainingCapabilityReason("not-qualified", "bridge_pending", "not qualified")
    monkeypatch.setattr(
        result, "plot_losses", lambda *_args: pytest.fail("unqualified output was plotted")
    )
    assert _present(monkeypatch, result, tmp_path / "not-created") == 1
    assert "Training complete!" not in capsys.readouterr().out


def test_explicit_current_role_supports_in_memory_presentation_without_cas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Presentation only: the real producer/update witness is test_plg_03.
    result = _result(object())
    result.status = "trained"
    result.result_role = "native_training_v1"
    observed: list[str] = []
    monkeypatch.setattr(result, "plot_losses", lambda path: observed.append(path))
    assert _present(monkeypatch, result, tmp_path / "output") == 0
    assert "PPO loss: 2.0000" in capsys.readouterr().out
    assert result.artifact_refs is None
    assert observed == [str(tmp_path / "output" / "training_loss.png")]
