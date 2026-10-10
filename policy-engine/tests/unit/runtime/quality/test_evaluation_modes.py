from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.evaluation_modes import (
    ExecutionIntentBand,
    resolve_evaluation_mode,
    resolve_execution_intent_band,
)


def test_canonical_modes_resolve_to_owner_bands_without_creating_authority() -> None:
    expected = {
        "simulate_only": ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
        "retrospective": ExecutionIntentBand.DATA_TRUST_REQUIRED,
        "measurement_audit": ExecutionIntentBand.DATA_TRUST_REQUIRED,
        "sandbox_pilot": ExecutionIntentBand.EVAL_SAFETY_REQUIRED,
        "field_pilot": ExecutionIntentBand.EVAL_SAFETY_REQUIRED,
        "deployment": ExecutionIntentBand.EVAL_SAFETY_REQUIRED,
    }

    for mode, band in expected.items():
        resolution = resolve_evaluation_mode(mode)
        assert resolution.status == "accepted"
        assert resolution.canonical_mode == mode
        assert (
            resolve_execution_intent_band(
                attempt_present=True,
                mode_resolution=resolution,
            )
            == band
        )

    deployment = resolve_evaluation_mode("deployment")
    assert (
        resolve_execution_intent_band(
            attempt_present=False,
            mode_resolution=deployment,
        )
        == ExecutionIntentBand.CANDIDATE_ONLY
    )
    assert (
        resolve_execution_intent_band(
            attempt_present=True,
            mode_resolution=resolve_evaluation_mode(" deployment "),
        )
        == ExecutionIntentBand.NOT_ESTABLISHED
    )
