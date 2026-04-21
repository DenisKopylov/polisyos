from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.model_class_compatibility import (
    check_model_class_compatibility,
)
from polisyos.ir.analytics.negative_certificate import BlockingType


def _compatible_binary_iv_data(n: int = 4000, seed: int = 13) -> tuple[np.ndarray, list[str]]:
    rng = np.random.default_rng(seed)
    z = rng.integers(0, 2, size=n)
    u = rng.integers(0, 2, size=n)
    d = (z | u).astype(int)
    y = (d | u).astype(int)
    data = np.column_stack([z, d, y]).astype(float)
    return data, ["Z", "D", "Y"]


def _compatible_conditional_binary_iv_data() -> tuple[np.ndarray, list[str]]:
    data_a, _ = _compatible_binary_iv_data(n=2000, seed=13)
    data_b, _ = _compatible_binary_iv_data(n=2000, seed=17)
    v0 = np.zeros((data_a.shape[0], 1), dtype=float)
    v1 = np.ones((data_b.shape[0], 1), dtype=float)
    data = np.vstack(
        [
            np.column_stack([data_a, v0]),
            np.column_stack([data_b, v1]),
        ]
    )
    return data, ["Z", "D", "Y", "V"]


def _incompatible_conditional_binary_iv_data() -> tuple[np.ndarray, list[str]]:
    compatible, _ = _compatible_binary_iv_data(n=1200, seed=23)
    incompatible, _ = _incompatible_binary_iv_data()
    v0 = np.zeros((compatible.shape[0], 1), dtype=float)
    v1 = np.ones((incompatible.shape[0], 1), dtype=float)
    data = np.vstack(
        [
            np.column_stack([compatible, v0]),
            np.column_stack([incompatible, v1]),
        ]
    )
    return data, ["Z", "D", "Y", "V"]


def _incompatible_binary_iv_data() -> tuple[np.ndarray, list[str]]:
    rows: list[list[float]] = []
    rows.extend([[1.0, 0.0, 0.0]] * 360)
    rows.extend([[1.0, 1.0, 0.0]] * 20)
    rows.extend([[1.0, 1.0, 1.0]] * 20)
    rows.extend([[0.0, 0.0, 1.0]] * 260)
    rows.extend([[0.0, 1.0, 0.0]] * 140)
    return np.asarray(rows, dtype=float), ["Z", "D", "Y"]


def test_binary_iv_model_class_compatibility_accepts_valid_scm_draws() -> None:
    data, variable_names = _compatible_binary_iv_data()

    verdict = check_model_class_compatibility(
        model_class_id="iv.binary.unconditional",
        data=data,
        variable_names=variable_names,
        observed_variables=["Z", "D", "Y"],
        alpha=0.05,
    )

    assert verdict.status == "compatible"
    assert verdict.negative_certificate is None
    assert verdict.report.compatibility_status == "compatible"
    assert verdict.report.model_class_id == "iv.binary.unconditional"
    assert len(verdict.report.constraints) == 4
    assert all(not constraint.rejected for constraint in verdict.report.constraints)


def test_binary_iv_model_class_compatibility_emits_negative_certificate_when_falsified() -> None:
    data, variable_names = _incompatible_binary_iv_data()

    verdict = check_model_class_compatibility(
        model_class_id="iv.binary.unconditional",
        data=data,
        variable_names=variable_names,
        observed_variables=["Z", "D", "Y"],
        alpha=0.05,
    )

    assert verdict.status == "incompatible"
    assert verdict.negative_certificate is not None
    assert verdict.negative_certificate.blocking_type is BlockingType.MODEL_CLASS_INCOMPATIBLE
    assert verdict.negative_certificate.model_class_compatibility == verdict.report
    assert any(constraint.rejected for constraint in verdict.report.constraints)
    assert verdict.report.evidence_summary["max_violation_margin"] > 0.0
    assert verdict.report.finite_sample_test.rejection_set


def test_conditional_binary_iv_model_class_compatibility_supports_stratified_v() -> None:
    data, variable_names = _compatible_conditional_binary_iv_data()

    verdict = check_model_class_compatibility(
        model_class_id="iv.binary.conditional_on_v",
        data=data,
        variable_names=variable_names,
        observed_variables=["Z", "D", "Y", "V"],
        alpha=0.05,
    )

    assert verdict.status == "compatible"
    assert verdict.report.model_class_id == "iv.binary.conditional_on_v"
    assert len(verdict.report.constraints) == 8
    assert (
        verdict.report.finite_sample_test.test_name
        == "gail_simon_style_fisher_union_intersection"
    )
    assert verdict.report.finite_sample_test.family_test_name is not None
    assert len(verdict.report.finite_sample_test.family_p_values) == 4
    scopes = {tuple(sorted(constraint.scope.items())) for constraint in verdict.report.constraints}
    assert scopes == {(("V", 0.0),), (("V", 1.0),)}


def test_conditional_binary_iv_model_class_compatibility_rejects_familywise_violation() -> None:
    data, variable_names = _incompatible_conditional_binary_iv_data()

    verdict = check_model_class_compatibility(
        model_class_id="iv.binary.conditional_on_V",
        data=data,
        variable_names=variable_names,
        observed_variables=["Z", "D", "Y", "V"],
        alpha=0.05,
    )

    assert verdict.status == "incompatible"
    assert verdict.negative_certificate is not None
    assert verdict.report.finite_sample_test.family_rejection_set
    assert any(constraint.witness_for_rejected_family for constraint in verdict.report.constraints)
    assert any(
        (constraint.family_adjusted_p_value or 1.0) < 0.05
        for constraint in verdict.report.constraints
        if constraint.witness_for_rejected_family
    )
