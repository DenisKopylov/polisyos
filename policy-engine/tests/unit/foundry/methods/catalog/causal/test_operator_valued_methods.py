from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.causal.operator_valued import (
    OperatorApplyProbeMethod,
    OperatorCMEKRREstimator,
    OperatorExportBasisMethod,
    OperatorKIVEstimator,
    OperatorProximalMinimaxEstimator,
    OperatorRLearnerEstimator,
    OperatorUnsupportedTargetMethod,
)
from polisyos.ir.analytics.causal import EstimationStatus


def _operator_state() -> dict[str, object]:
    covariates = np.array(
        [
            [0.0, 0.2],
            [0.1, 0.0],
            [0.2, 0.1],
            [0.4, 0.3],
            [0.5, 0.4],
            [0.6, 0.5],
            [0.8, 0.6],
            [1.0, 0.7],
        ],
        dtype=float,
    )
    treatment = np.array([0, 0, 0, 1, 1, 1, 0, 1], dtype=float)
    outcome_1 = 1.0 + 0.5 * covariates[:, 0] + 1.3 * treatment
    outcome_2 = -0.2 + 0.4 * covariates[:, 1] + 0.8 * treatment
    outcome = np.column_stack([outcome_1, outcome_2])
    instrument = np.array([0, 0, 0, 1, 1, 1, 0, 1], dtype=float).reshape(-1, 1)
    return {
        "outcome": outcome,
        "treatment": treatment,
        "covariates": covariates,
        "effect_modifier": covariates[:, :1],
        "instrument": instrument,
        "treatment_proxy": np.column_stack([covariates[:, :1], instrument]),
        "outcome_proxy": np.column_stack([covariates[:, 1:], 1.0 - instrument]),
    }


def test_operator_cme_krr_emits_bundle_and_probe_exports() -> None:
    result = OperatorCMEKRREstimator.pure_step(
        _operator_state(),
        {
            "reference_treatment": 0.0,
            "probe_space": {"space_id": "hy"},
            "codomain_space": {"space_id": "hv"},
            "max_evaluation_points": 4,
        },
    )

    assert result["report"].status is EstimationStatus.SUCCESS
    bundle = result["operator_effect_bundle"]
    assert bundle["estimator_family"] == "cme_krr"
    assert len(bundle["probe_basis"]) == 2
    assert len(bundle["applied_probe_exports"]) == 2
    assert bundle["operator_norm_error_bound"] >= 0.0


def test_operator_r_learner_returns_successful_operator_payload() -> None:
    result = OperatorRLearnerEstimator.pure_step(
        _operator_state(),
        {"reference_treatment": 0.0, "max_evaluation_points": 5},
    )

    assert result["report"].status is EstimationStatus.SUCCESS
    assert result["result"]["family"] == "operator_r_learner"
    assert result["result"]["n_probes"] == 2


def test_operator_kiv_uses_instrument_and_emits_iv_family() -> None:
    result = OperatorKIVEstimator.pure_step(
        _operator_state(),
        {"reference_treatment": 0.0, "max_evaluation_points": 3},
    )

    assert result["report"].status is EstimationStatus.SUCCESS
    assert result["operator_effect_bundle"]["estimator_family"] == "kiv"
    assert result["result"]["n_evaluation_points"] == 3


def test_operator_proximal_minimax_emits_proxy_augmented_bundle() -> None:
    result = OperatorProximalMinimaxEstimator.pure_step(
        _operator_state(),
        {"reference_treatment": 0.0, "max_evaluation_points": 3},
    )

    assert result["report"].status is EstimationStatus.SUCCESS
    assert result["operator_effect_bundle"]["estimator_family"] == "proximal_minimax"


def test_apply_probe_and_export_basis_replay_bundle() -> None:
    fitted = OperatorCMEKRREstimator.pure_step(
        _operator_state(),
        {"reference_treatment": 0.0, "max_evaluation_points": 4},
    )
    bundle = fitted["operator_effect_bundle"]

    applied = OperatorApplyProbeMethod.pure_step(
        {"operator_effect_bundle": bundle},
        {"probe_ref": "coord_0"},
    )
    exported = OperatorExportBasisMethod.pure_step(
        {"operator_effect_bundle": bundle},
        {},
    )

    assert applied["applied_probe"]["probe_ref"] == "coord_0"
    assert len(applied["applied_probe"]["values"]) == 4
    assert exported["result"]["n_exports"] == 2
    assert len(exported["probe_exports"]) == 2


def test_unsupported_operator_target_returns_failure_payload() -> None:
    result = OperatorUnsupportedTargetMethod.pure_step({}, {"degraded_reason": "unsupported_combo"})

    assert result["report"].status is EstimationStatus.INPUT_INVALID
    assert result["result"]["reason"] == "unsupported_combo"
