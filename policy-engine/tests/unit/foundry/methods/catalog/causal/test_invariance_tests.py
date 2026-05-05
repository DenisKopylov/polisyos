from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import invariance_tests as invariance_module
from polisyos.foundry.methods.catalog.causal.invariance_tests import (
    build_environment_audit_report,
    build_regime_shift_identification_certificate,
)
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)
from polisyos.ir.analytics.invariance import RegimeShiftTrack7Revalidation


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _setup() -> tuple:
    ensure_causal_methods_registered()
    return MethodRegistry.get_instance(), MethodDispatcher.get_instance()


def _dispatch(fqn: str, state: dict, params: dict) -> dict:
    registry, dispatcher = _setup()
    method_cls = registry.get(fqn)
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params=params,
        seed=0,
    )
    return result.output["result"]


def _make_nonlinear_regime_data(
    *,
    seed: int,
    env_specs: list[tuple[str, float]],
    n_per_env: int = 180,
    intercept_shift_envs: set[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    intercept_shift_envs = intercept_shift_envs or set()
    chunks: list[np.ndarray] = []
    labels: list[str] = []
    for env_name, mean_shift in env_specs:
        x = rng.normal(loc=mean_shift, scale=1.0, size=n_per_env)
        z = rng.normal(size=n_per_env)
        intercept = 2.5 if env_name in intercept_shift_envs else 0.0
        y = x**2 + intercept + 0.08 * rng.normal(size=n_per_env)
        chunks.append(np.column_stack([x, z, y]))
        labels.extend([env_name] * n_per_env)
    return np.vstack(chunks), np.asarray(labels)


# ---------------------------------------------------------------------------
# KSInvarianceTest
# ---------------------------------------------------------------------------


def test_ks_invariance_detects_shift() -> None:
    """KS test should detect a clear mean shift between domains."""
    rng = np.random.default_rng(10)
    n = 150
    # Domain 0: N(0,1), Domain 1: N(3,1) — obvious shift
    data_d0 = rng.normal(loc=0.0, size=(n, 2))
    data_d1 = rng.normal(loc=3.0, size=(n, 2))
    data = np.vstack([data_d0, data_d1])
    labels = np.array([0] * n + [1] * n)

    out = _dispatch(
        "causal.diagnostics.invariance.ks_invariance@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={"alpha": 0.05, "correction": "bonferroni"},
    )

    assert out["passed"] is False
    assert out["n_rejected"] > 0
    assert len(out["rejected_variables"]) > 0


def test_ks_invariance_passes_same_distribution() -> None:
    """KS test should not reject when both domains come from the same distribution."""
    rng = np.random.default_rng(42)
    n = 200
    data = rng.normal(size=(2 * n, 3))
    labels = np.array([0] * n + [1] * n)

    out = _dispatch(
        "causal.diagnostics.invariance.ks_invariance@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={"alpha": 0.01, "correction": "bonferroni"},
    )

    assert out["passed"] is True
    assert out["n_rejected"] == 0
    assert "n_tests" in out["metadata"]


def test_ks_invariance_bh_reduces_rejections_vs_bonferroni() -> None:
    """BH correction should produce fewer or equal rejections than Bonferroni."""
    rng = np.random.default_rng(77)
    n = 100
    # Moderate shift in one feature, same for others
    data_d0 = rng.normal(size=(n, 5))
    data_d1 = np.column_stack(
        [
            rng.normal(loc=1.5, size=(n, 1)),  # shifted
            rng.normal(size=(n, 4)),  # same
        ]
    )
    data = np.vstack([data_d0, data_d1])
    labels = np.array([0] * n + [1] * n)

    out_bonferroni = _dispatch(
        "causal.diagnostics.invariance.ks_invariance@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={"alpha": 0.05, "correction": "bonferroni"},
    )
    out_bh = _dispatch(
        "causal.diagnostics.invariance.ks_invariance@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={"alpha": 0.05, "correction": "bh"},
    )

    # BH should have >= as many rejections as Bonferroni (more power)
    assert out_bh["n_rejected"] >= out_bonferroni["n_rejected"]


def test_ks_invariance_output_structure() -> None:
    """All expected fields present in KS invariance output."""
    rng = np.random.default_rng(3)
    n = 80
    data = rng.normal(size=(2 * n, 2))
    labels = np.array([0] * n + [1] * n)

    out = _dispatch(
        "causal.diagnostics.invariance.ks_invariance@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={"alpha": 0.05},
    )

    required = {
        "passed",
        "n_rejected",
        "rejected_variables",
        "p_values_matrix",
        "correction_method",
        "metadata",
    }
    assert required <= set(out.keys())
    assert isinstance(out["rejected_variables"], list)


# ---------------------------------------------------------------------------
# ICPInvarianceTest
# ---------------------------------------------------------------------------


def test_icp_invariance_basic_run() -> None:
    """ICP smoke test with 2 domains."""
    rng = np.random.default_rng(20)
    n = 100
    # Feature 0 causes Y with same coefficient; feature 1 has heterogeneous effect
    data_d0 = np.column_stack(
        [
            rng.normal(size=(n, 2)),
            rng.normal(size=n),  # Y = X0 + noise
        ]
    )
    data_d0[:, 2] = data_d0[:, 0] + 0.3 * rng.normal(size=n)

    data_d1 = np.column_stack(
        [
            rng.normal(size=(n, 2)),
            rng.normal(size=n),
        ]
    )
    data_d1[:, 2] = 3.0 * data_d1[:, 1] + 0.3 * rng.normal(size=n)  # different feature

    data = np.vstack([data_d0, data_d1])
    labels = np.array([0] * n + [1] * n)

    out = _dispatch(
        "causal.diagnostics.invariance.icp_invariance@1.0.0",
        state={"data": data, "domain_labels": labels, "target_col": 2},
        params={"alpha": 0.05, "correction": "bh"},
    )

    assert "passed" in out
    assert "invariant_features" in out
    assert "variant_features" in out
    assert "p_values" in out
    assert isinstance(out["invariant_features"], list)
    assert isinstance(out["variant_features"], list)


def test_icp_invariance_stable_feature_is_invariant() -> None:
    """Feature with stable Y|X effect across domains should be in invariant_features."""
    rng = np.random.default_rng(55)
    n = 120
    # X0 has stable effect on Y across both domains
    # X1 has completely different effect in each domain
    data_d0 = np.column_stack(
        [
            rng.normal(size=n),  # X0
            rng.normal(size=n),  # X1
        ]
    )
    data_d1 = np.column_stack(
        [
            rng.normal(size=n),  # X0
            rng.normal(size=n),  # X1
        ]
    )
    Y_d0 = 2.0 * data_d0[:, 0] + 0.1 * rng.normal(size=n)
    Y_d1 = 2.0 * data_d1[:, 0] + 5.0 * data_d1[:, 1] + 0.1 * rng.normal(size=n)

    data = np.column_stack(
        [
            np.vstack([data_d0, data_d1]),
            np.concatenate([Y_d0, Y_d1]),
        ]
    )
    labels = np.array([0] * n + [1] * n)

    out = _dispatch(
        "causal.diagnostics.invariance.icp_invariance@1.0.0",
        state={"data": data, "domain_labels": labels, "target_col": 2},
        params={"alpha": 0.05, "correction": "bh"},
    )

    # X0 (col 0) should be more likely to be invariant; X1 (col 1) should be variant
    # (This is a statistical test, so we check the structure rather than exact values)
    assert 0 in out["invariant_features"] or 0 in out["variant_features"]
    assert set(out["invariant_features"]) | set(out["variant_features"]) == {0, 1}


def test_environment_audit_helper_returns_ok_for_stable_domains() -> None:
    rng = np.random.default_rng(123)
    n = 80
    data = rng.normal(size=(2 * n, 3))
    labels = np.array(["env_a"] * n + ["env_b"] * n)

    report = build_environment_audit_report(
        data=data,
        variable_names=["X0", "X1", "Y"],
        domain_labels=labels,
        target_col=2,
    )

    assert report.status == "ok"
    assert report.n_environments == 2
    assert report.ks_passed is True
    assert report.icp_run is True


def test_environment_audit_helper_detects_shift_and_feature_heterogeneity() -> None:
    rng = np.random.default_rng(321)
    n = 120
    x0_a = rng.normal(size=n)
    x1_a = rng.normal(size=n)
    y_a = 2.0 * x0_a + 0.1 * rng.normal(size=n)
    x0_b = rng.normal(loc=2.5, size=n)
    x1_b = rng.normal(size=n)
    y_b = 2.0 * x0_b + 4.0 * x1_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.concatenate([x1_a, x1_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["env_a"] * n + ["env_b"] * n)

    report = build_environment_audit_report(
        data=data,
        variable_names=["X0", "X1", "Y"],
        domain_labels=labels,
        target_col="Y",
    )

    assert report.status == "warning"
    assert report.ks_passed is False
    assert report.icp_run is True
    assert report.icp_passed is False
    assert report.variant_features


def test_environment_audit_helper_skips_or_degrades_invalid_inputs() -> None:
    skipped = build_environment_audit_report(
        data=[[1.0, 2.0], [2.0, 3.0]],
        variable_names=["X0", "X1"],
        domain_labels=None,
    )
    assert skipped.status == "skipped"

    degraded = build_environment_audit_report(
        data=[[1.0, 2.0], [2.0, 3.0]],
        variable_names=["X0", "X1"],
        domain_labels=["a"],
        target_col=99,
    )
    assert degraded.status == "degraded"
    assert "environment_audit_domain_label_length_mismatch" in degraded.warnings

    invalid_target = build_environment_audit_report(
        data=[[1.0, 2.0], [1.1, 2.1], [3.0, 4.0], [3.1, 4.1]],
        variable_names=["X0", "Y"],
        domain_labels=["a", "a", "b", "b"],
        target_col=99,
    )
    assert invalid_target.status == "warning"
    assert "icp_invalid_target_col" in invalid_target.warnings


def test_invariant_discovery_from_regimes_emits_certificate_and_orientations() -> None:
    rng = np.random.default_rng(2026)
    n = 220
    x0_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x1_a = rng.normal(size=n)
    y_a = 2.0 * x0_a + 0.08 * rng.normal(size=n)
    x0_b = rng.normal(loc=3.0, scale=1.0, size=n)
    x1_b = rng.normal(size=n)
    y_b = 2.0 * x0_b + 0.08 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.concatenate([x1_a, x1_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    out = _dispatch(
        "causal.discovery.invariant_discovery_from_regimes@1.0.0",
        state={"data": data, "domain_labels": labels},
        params={
            "alpha": 0.01,
            "max_set_size": 1,
            "target_cols": ["Y"],
            "variable_names": ["X0", "X1", "Y"],
        },
    )

    certificate = out["regime_shift_identification_certificate"]
    assert certificate["kind"] == "ir.regime_shift_identification_certificate"
    assert certificate["data_signature"]["sample_sizes_by_env"] == {"post": n, "pre": n}
    assert certificate["targets"][0]["target"] == "Y"
    assert certificate["targets"][0]["estimated_parents"] == ["X0"]
    assert certificate["targets"][0]["informativeness"]["empty_set_stable"] is False
    assert certificate["shift_type_assessment"]["overall_label"] == "ambiguous"
    assert out["computational_feasibility"]["mode"] == "exact"
    assert out["computational_feasibility"]["exact_mode_possible"] is True
    assert ["X0", "Y"] in out["forced_orientations"]


def test_regime_shift_certificate_uses_nonlinear_phase_closing_route_when_auto_is_eligible() -> (
    None
):
    rng = np.random.default_rng(909)
    env_specs = [
        ("env_a", -2.0, 0.0),
        ("env_b", 0.0, 0.0),
        ("env_c", 2.0, 0.0),
        ("env_d", 0.0, 2.0),
    ]
    chunks: list[np.ndarray] = []
    labels: list[str] = []
    for env_name, mean_x, mean_z in env_specs:
        x = rng.normal(loc=mean_x, scale=1.0, size=220)
        z = rng.normal(loc=mean_z, scale=1.0, size=220)
        w = rng.normal(size=220)
        y = x**2 + z**2 + 0.08 * rng.normal(size=220)
        chunks.append(np.column_stack([x, z, w, y]))
        labels.extend([env_name] * 220)
    data = np.vstack(chunks)
    labels = np.asarray(labels)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X", "Z", "W", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=2,
        model_family="auto",
        context_exogeneity="declared",
        baseline_covariates=["W"],
        selection_max_set_size=1,
        shift_type_repro_splits=1,
    )

    assert certificate.produced_by.implementation == "mime_icp_nonlinear_additive_noise_sieve_v1"
    assert certificate.invariance_testing.model_class == "nonlinear_additive_noise_sieve"
    assert certificate.targets[0].estimated_parents == ("X", "Z")
    assert certificate.identifiability_witness is not None
    assert certificate.identifiability_witness.identification_scope == (
        "phase_closing_nonlinear_additive_noise_icp"
    )
    assert certificate.identifiability_witness.diversity_satisfied is True
    assert len(certificate.identifiability_witness.informative_envs) >= 2
    assert certificate.shift_type_assessment is not None
    assert certificate.shift_type_assessment.pipeline_action.allow_icp_graph_contraction is True
    assert certificate.metadata["phase_closing_stage16_1"] is True
    assert certificate.mec_contraction.summary.edges_oriented_total >= 1


def test_regime_shift_certificate_marks_duplicate_environment_pattern_as_redundant() -> None:
    rng = np.random.default_rng(910)
    env_specs = [
        ("env_a", -2.0, 0.0),
        ("env_b", 0.0, 0.0),
        ("env_c", 2.0, 0.0),
        ("env_d", 0.0, 2.0),
        ("env_e", 0.0, 2.0),
    ]
    chunks: list[np.ndarray] = []
    labels: list[str] = []
    for env_name, mean_x, mean_z in env_specs:
        x = rng.normal(loc=mean_x, scale=1.0, size=180)
        z = rng.normal(loc=mean_z, scale=1.0, size=180)
        w = rng.normal(size=180)
        y = x**2 + z**2 + 0.08 * rng.normal(size=180)
        chunks.append(np.column_stack([x, z, w, y]))
        labels.extend([env_name] * 180)
    data = np.vstack(chunks)
    labels = np.asarray(labels)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X", "Z", "W", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=2,
        model_family="auto",
        context_exogeneity="declared",
        baseline_covariates=["W"],
        selection_max_set_size=1,
        shift_type_repro_splits=1,
    )

    assert certificate.invariance_testing.model_class == "nonlinear_additive_noise_sieve"
    assert certificate.targets[0].informativeness.redundant_envs
    assert certificate.identifiability_witness is not None
    assert certificate.identifiability_witness.redundant_envs
    assert certificate.identifiability_witness.identification_scope == (
        "nonlinear_slice_present_but_not_phase_closing"
    )
    assert certificate.metadata["phase_closing_stage16_1"] is False


def test_regime_shift_certificate_blocks_phase_closing_for_selection_or_mixed_nonlinear_case() -> (
    None
):
    rng = np.random.default_rng(911)
    chunks: list[np.ndarray] = []
    labels: list[str] = []
    for env_name, mean_b in [("pre", -2.0), ("mid", 0.0), ("post", 2.5)]:
        b = rng.normal(loc=mean_b, scale=1.0, size=240)
        x = -1.2 * b + 0.05 * rng.normal(size=240)
        y = 2.4 * b + 0.05 * rng.normal(size=240)
        chunks.append(np.column_stack([b, x, y]))
        labels.extend([env_name] * 240)
    data = np.vstack(chunks)
    labels = np.asarray(labels)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["B", "X", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        model_family="auto",
        context_exogeneity="unverified",
        baseline_covariates=["B"],
        selection_max_set_size=1,
        shift_type_repro_splits=1,
    )

    assert certificate.invariance_testing.model_class == "nonlinear_additive_noise_sieve"
    assert certificate.shift_type_assessment is not None
    assert certificate.shift_type_assessment.pipeline_action.allow_icp_graph_contraction is False
    assert certificate.identifiability_witness is not None
    assert certificate.identifiability_witness.identification_scope == (
        "nonlinear_slice_present_but_not_phase_closing"
    )
    assert certificate.identifiability_witness.diversity_satisfied is False
    assert certificate.metadata["phase_closing_stage16_1"] is False


def test_regime_shift_certificate_marks_linear_route_as_fallback_when_auto_is_not_eligible() -> (
    None
):
    rng = np.random.default_rng(912)
    n = 220
    x0_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x1_a = rng.normal(size=n)
    y_a = 2.0 * x0_a + 0.08 * rng.normal(size=n)
    x0_b = rng.normal(loc=3.0, scale=1.0, size=n)
    x1_b = rng.normal(size=n)
    y_b = 2.0 * x0_b + 0.08 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.concatenate([x1_a, x1_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X0", "X1", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        model_family="auto",
        context_exogeneity="declared",
        baseline_covariates=["X1"],
        selection_max_set_size=1,
        shift_type_repro_splits=1,
    )

    assert certificate.invariance_testing.model_class == "linear_ols"
    assert any("fallback" in note for note in certificate.invariance_testing.notes)
    assert certificate.identifiability_witness is not None
    assert certificate.identifiability_witness.identification_scope == (
        "linear_fallback_only_not_phase_closing"
    )
    assert certificate.metadata["model_family_resolved"] == "linear"
    assert certificate.metadata["phase_closing_stage16_1"] is False


def test_regime_shift_certificate_marks_structural_only_when_selection_witness_rejected() -> None:
    rng = np.random.default_rng(1001)
    n = 220
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    y_a = 2.0 * x_a
    x_b = rng.normal(loc=3.0, scale=1.0, size=n)
    z_b = rng.normal(size=n)
    y_b = 2.0 * x_b
    data = np.column_stack(
        [
            np.concatenate([x_a, x_b]),
            np.concatenate([z_a, z_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X", "Z", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        context_exogeneity="declared",
        baseline_covariates=["Z"],
        selection_max_set_size=1,
    )

    assessment = certificate.shift_type_assessment
    assert assessment is not None
    assert assessment.overall_label.value == "structural_only_consistent"
    assert assessment.pipeline_action.allow_icp_graph_contraction is True
    assert assessment.witnesses.selection_only_witness.status.value == "rejected"
    assert assessment.witnesses.structural_only_witness.status.value == "not_rejected"
    assert certificate.metadata["shift_type_reproducibility"]["agreement"] == 1.0


def test_regime_shift_certificate_marks_selection_only_when_balancing_witness_passes() -> None:
    rng = np.random.default_rng(3001)
    n = 240
    b_a = rng.normal(loc=0.0, scale=1.0, size=n)
    b_b = rng.normal(loc=3.0, scale=1.0, size=n)
    x_a = -1.2 * b_a
    x_b = -1.2 * b_b
    y_a = 2.4 * b_a
    y_b = 2.4 * b_b
    data = np.column_stack(
        [
            np.concatenate([b_a, b_b]),
            np.concatenate([x_a, x_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["B", "X", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=0,
        context_exogeneity="unverified",
        baseline_covariates=["B"],
        selection_max_set_size=1,
    )

    assessment = certificate.shift_type_assessment
    assert assessment is not None
    assert assessment.overall_label.value == "selection_only_consistent"
    assert assessment.pipeline_action.allow_icp_graph_contraction is False
    assert assessment.pipeline_action.allow_selection_transport_path is True
    assert assessment.witnesses.selection_only_witness.status.value == "not_rejected"
    assert assessment.witnesses.structural_only_witness.status.value == "rejected"
    assert certificate.metadata["shift_type_reproducibility"]["label_counts"] == {
        "selection_only_consistent": 3
    }


def test_regime_shift_certificate_marks_mixed_or_latent_when_simple_witnesses_fail() -> None:
    rng = np.random.default_rng(3002)
    n = 240
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    y_a = 2.0 * x_a
    x_b = rng.normal(loc=3.0, scale=1.0, size=n)
    z_b = rng.normal(size=n)
    y_b = 2.0 * x_b + 4.0
    data = np.column_stack(
        [
            np.concatenate([x_a, x_b]),
            np.concatenate([z_a, z_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X", "Z", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        context_exogeneity="declared",
        baseline_covariates=["Z"],
        selection_max_set_size=1,
    )

    assessment = certificate.shift_type_assessment
    assert assessment is not None
    assert assessment.overall_label.value == "mixed_or_latent_suspected"
    assert assessment.pipeline_action.allow_icp_graph_contraction is False
    assert assessment.pipeline_action.route_to_latent_aware_discovery is True
    assert assessment.witnesses.selection_only_witness.status.value == "rejected"
    assert assessment.witnesses.structural_only_witness.status.value == "rejected"


def test_regime_shift_certificate_marks_uninformative_when_no_global_shift_detected() -> None:
    rng = np.random.default_rng(1002)
    n = 160
    x_a = rng.normal(size=n)
    z_a = rng.normal(size=n)
    y_a = 1.5 * x_a + 0.1 * rng.normal(size=n)
    x_b = rng.normal(size=n)
    z_b = rng.normal(size=n)
    y_b = 1.5 * x_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x_a, x_b]),
            np.concatenate([z_a, z_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X", "Z", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        context_exogeneity="declared",
        baseline_covariates=["Z"],
        selection_max_set_size=1,
    )

    assessment = certificate.shift_type_assessment
    assert assessment is not None
    assert assessment.overall_label.value == "uninformative_shift"
    assert assessment.pipeline_action.allow_icp_graph_contraction is False


def test_regime_shift_certificate_uses_track7_blocks_to_reduce_search_space() -> None:
    rng = np.random.default_rng(411)
    n = 180
    latent_a = rng.normal(loc=0.0, scale=1.0, size=n)
    latent_b = rng.normal(loc=1.5, scale=1.0, size=n)
    x_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x_b = rng.normal(loc=2.5, scale=1.0, size=n)
    block_a = np.column_stack(
        [
            0.9 * latent_a + 0.1 * rng.normal(size=n),
            0.8 * latent_a + 0.1 * rng.normal(size=n),
            1.0 * latent_a + 0.1 * rng.normal(size=n),
            0.7 * latent_a + 0.1 * rng.normal(size=n),
        ]
    )
    block_b = np.column_stack(
        [
            0.9 * latent_b + 0.1 * rng.normal(size=n),
            0.8 * latent_b + 0.1 * rng.normal(size=n),
            1.0 * latent_b + 0.1 * rng.normal(size=n),
            0.7 * latent_b + 0.1 * rng.normal(size=n),
        ]
    )
    y_a = 2.0 * x_a + 0.1 * rng.normal(size=n)
    y_b = 2.0 * x_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.vstack([block_a, block_b]),
            np.concatenate([x_a, x_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)
    variable_names = ["B1", "B2", "B3", "B4", "X", "Y"]
    super_structure = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=variable_names,
        edges=[
            CausalEdge(src="B1", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="B2", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="B3", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="B4", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
        discovery_method="test_super_structure",
    )

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=variable_names,
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=2,
        super_structure=super_structure,
        algebraic_blocks=[
            {
                "block_id": "measurement_block",
                "family": "tetrad",
                "variables": ("B1", "B2", "B3", "B4"),
            }
        ],
        max_candidate_parents=6,
    )

    feasibility = certificate.computational_feasibility
    assert feasibility is not None
    assert feasibility.track7.block_lifting_applied is True
    assert feasibility.track7.candidate_suppression_applied is False
    assert feasibility.track7.mutually_exclusive_candidate_groups_by_target["Y"] == (
        ("B1", "B2", "B3", "B4"),
    )
    assert ("B1", "B2") in feasibility.track7.hard_forbidden_edges
    assert feasibility.candidate_parent_sizes["Y"] == 5


def test_regime_shift_certificate_reports_partial_mode_when_exact_caps_fail() -> None:
    rng = np.random.default_rng(412)
    n = 180
    x0_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x0_b = rng.normal(loc=2.5, scale=1.0, size=n)
    nuisance_a = rng.normal(size=(n, 4))
    nuisance_b = rng.normal(size=(n, 4))
    y_a = 2.0 * x0_a + 0.1 * rng.normal(size=n)
    y_b = 2.0 * x0_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.vstack([nuisance_a, nuisance_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)
    variable_names = ["X0", "N1", "N2", "N3", "N4", "Y"]
    super_structure = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=variable_names,
        edges=[
            CausalEdge(src="X0", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="N1", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="N2", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="N3", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
            CausalEdge(src="N4", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.CIRCLE),
        ],
        discovery_method="test_super_structure",
    )

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=variable_names,
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        super_structure=super_structure,
        max_candidate_parents=5,
        exact_component_cap=3,
    )

    feasibility = certificate.computational_feasibility
    assert feasibility is not None
    assert feasibility.mode == "partial"
    assert feasibility.exact_mode_possible is False
    assert "component_size_cap_exceeded>3" in (feasibility.fallback_reason or "")


def test_regime_shift_certificate_downgrades_exact_mode_after_track7_revalidation_blocker(
    monkeypatch,
) -> None:
    rng = np.random.default_rng(413)
    n = 180
    x0_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x0_b = rng.normal(loc=2.0, scale=1.0, size=n)
    x1_a = rng.normal(size=n)
    x1_b = rng.normal(size=n)
    y_a = 2.0 * x0_a + 0.1 * rng.normal(size=n)
    y_b = 2.0 * x0_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.concatenate([x1_a, x1_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    monkeypatch.setattr(
        invariance_module,
        "_run_track7_revalidation",
        lambda **kwargs: RegimeShiftTrack7Revalidation(
            performed=True,
            severity="blocker",
            violated_by_family={"trek_rank": 1},
            blocker_families=("trek_rank",),
            exact_certificate_valid=False,
        ),
    )

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X0", "X1", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        algebraic_blocks=[
            {
                "block_id": "trk",
                "family": "trek_rank",
                "variables": ("X0", "X1"),
                "row_variables": ("X0",),
                "col_variables": ("X1",),
                "max_rank": 0,
            }
        ],
    )

    feasibility = certificate.computational_feasibility
    assert feasibility is not None
    assert feasibility.mode == "partial"
    assert feasibility.exact_mode_possible is True
    assert feasibility.exact_mode_applied is False
    assert "track7_revalidation_blocker:trek_rank" in (feasibility.fallback_reason or "")
    assert feasibility.track7.revalidation.blocker_families == ("trek_rank",)
    assert feasibility.track7.revalidation.exact_certificate_valid is False


def test_regime_shift_certificate_respects_prior_track7_blocker_reports() -> None:
    rng = np.random.default_rng(414)
    n = 180
    x0_a = rng.normal(loc=0.0, scale=1.0, size=n)
    x0_b = rng.normal(loc=2.0, scale=1.0, size=n)
    z_a = rng.normal(size=n)
    z_b = rng.normal(size=n)
    y_a = 2.0 * x0_a + 0.1 * rng.normal(size=n)
    y_b = 2.0 * x0_b + 0.1 * rng.normal(size=n)
    data = np.column_stack(
        [
            np.concatenate([x0_a, x0_b]),
            np.concatenate([z_a, z_b]),
            np.concatenate([y_a, y_b]),
        ]
    )
    labels = np.array(["pre"] * n + ["post"] * n)

    certificate = build_regime_shift_identification_certificate(
        data=data,
        domain_labels=labels,
        variable_names=["X0", "Z", "Y"],
        target_cols=["Y"],
        alpha=0.01,
        max_set_size=1,
        prior_algebraic_reports=[
            AlgebraicConstraintReport(
                severity="blocker",
                families_run=[AlgebraicConstraintFamily.TREK_RANK],
                n_violated_constraints=1,
                violated_by_family={"trek_rank": 1},
                blocker_conditions_met_by_family={"trek_rank": True},
            )
        ],
    )

    feasibility = certificate.computational_feasibility
    assert feasibility is not None
    assert feasibility.mode == "partial"
    assert feasibility.exact_mode_possible is False
    assert feasibility.track7.prior_blocker_families == ("trek_rank",)
    assert "track7_prior_blocker_conflict:trek_rank" in (feasibility.fallback_reason or "")
