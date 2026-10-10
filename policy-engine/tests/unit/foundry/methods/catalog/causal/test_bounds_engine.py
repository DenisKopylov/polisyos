"""Tests for BoundsEngineMethod and OptimizationBasedBoundsEstimator."""

from __future__ import annotations

import numpy as np

from polisyos.ir.analytics.dual_certificate import (
    StratifiedLPDualCertificateBundle,
    coerce_bounds_certificate_bundle,
    validate_bounds_certificate_bundle,
)
from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsBundle,
    BoundSoundnessLevel,
    PartialIdentificationResult,
    TighteningStatus,
    TighteningStopReason,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(n: int = 200, *, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    T = rng.integers(0, 2, size=n).astype(float)
    Y = 0.4 * T + 0.3 + rng.normal(0, 0.2, size=n)
    Y = np.clip(Y, 0.0, 1.0)
    return {"outcome": Y, "treatment": T}


def _make_iv_state(n: int = 300, *, seed: int = 7) -> dict:
    """Binary IV, binary treatment, binary outcome."""
    rng = np.random.default_rng(seed)
    Z = rng.integers(0, 2, size=n).astype(float)
    T = (rng.random(size=n) < 0.3 + 0.4 * Z).astype(float)
    Y = (rng.random(size=n) < 0.2 + 0.35 * T).astype(float)
    return {"outcome": Y, "treatment": T, "instrument": Z}


def _make_exact_lp_state(n: int = 300, *, seed: int = 17) -> dict:
    del n, seed
    return {
        "outcome": np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
        "treatment": np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
    }


def _make_selection_state(n: int = 300, *, seed: int = 13) -> dict:
    rng = np.random.default_rng(seed)
    T = rng.integers(0, 2, size=n).astype(float)
    S = (rng.random(size=n) < 0.6 + 0.2 * T).astype(float)
    Y_full = 0.5 * T + rng.normal(0, 0.1, size=n)
    Y_full = np.clip(Y_full, 0.0, 1.0)
    Y = Y_full * S  # observed only for selected
    return {"outcome": Y, "treatment": T, "selected": S}


def _make_invalid_iv_family_state() -> dict:
    z_binary = np.array(
        [1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1],
        dtype=float,
    )
    z = np.where(
        z_binary > 0.5,
        np.where(np.arange(z_binary.size) % 2 == 0, 0.8, 0.9),
        np.where(np.arange(z_binary.size) % 2 == 0, 0.1, 0.2),
    )
    t = np.array(
        [1, 1, 1, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1],
        dtype=float,
    )
    y = np.array(
        [1, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1],
        dtype=float,
    )
    return {"outcome": y, "treatment": t, "instrument": z}


def _make_incompatible_binary_iv_state() -> dict:
    rows: list[list[float]] = []
    rows.extend([[1.0, 0.0, 0.0]] * 360)
    rows.extend([[1.0, 1.0, 0.0]] * 20)
    rows.extend([[1.0, 1.0, 1.0]] * 20)
    rows.extend([[0.0, 0.0, 1.0]] * 260)
    rows.extend([[0.0, 1.0, 0.0]] * 140)
    arr = np.asarray(rows, dtype=float)
    return {"instrument": arr[:, 0], "treatment": arr[:, 1], "outcome": arr[:, 2]}


# ---------------------------------------------------------------------------
# BoundsEngineMethod — unit tests
# ---------------------------------------------------------------------------


class TestBoundsEngineMethodDefault:
    def test_runs_without_error(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        assert "bounds_report" in result

    def test_returns_at_least_two_results(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        report_dict = result["bounds_report"]
        assert len(report_dict["method_summaries"]) >= 2

    def test_tightest_method_is_narrowest(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        report = BoundsBundle.model_validate(result["bounds_report"])
        assert report.lower_bound is not None
        assert report.upper_bound is not None
        if len(report.method_summaries) > 1:
            widths = [r.bound_width for r in report.method_summaries]
            tightest_width = min(widths)
            assert abs((report.upper_bound - report.lower_bound) - tightest_width) < 1e-9

    def test_consensus_is_intersection(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        report = BoundsBundle.model_validate(result["bounds_report"])
        if len(report.method_summaries) > 1:
            expected_lo = max(r.lower_bound for r in report.method_summaries)
            expected_hi = min(r.upper_bound for r in report.method_summaries)
            assert abs(report.consensus_lower - expected_lo) < 1e-9
            assert abs(report.consensus_upper - expected_hi) < 1e-9

    def test_default_includes_manski(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        report = BoundsBundle.model_validate(result["bounds_report"])
        methods = {r.method for r in report.method_summaries}
        assert BoundMethod.MANSKI in methods

    def test_bounds_report_round_trip(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(state, {})
        report = BoundsBundle.model_validate(result["bounds_report"])
        dumped = report.model_dump(mode="json")
        reloaded = BoundsBundle.model_validate(dumped)
        assert reloaded.lower_bound == report.lower_bound
        assert len(reloaded.method_summaries) == len(report.method_summaries)

    def test_exact_auto_bounds_returns_certificate_payload_but_bundle_stays_unknown_until_persisted(
        self,
    ):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_exact_lp_state()
        result = BoundsEngineMethod.pure_step(
            state,
            {"use_auto_bounds": True, "has_monotone": True},
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert "dual_certificate_payload" in result
        assert report.sharpness_status == "unknown"

    def test_tighten_bounds_emits_certified_improvement_claim_for_exact_auto_bounds(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_exact_lp_state()
        result = BoundsEngineMethod.pure_step(
            state,
            {"use_auto_bounds": True, "tighten_bounds": True, "has_monotone": True},
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert report.tightening_status is TighteningStatus.IMPROVED
        assert report.best_in_class_claim is not None
        assert report.best_in_class_claim.selected_method is BoundMethod.GENERAL_LP_BOUNDS
        assert any(
            summary.soundness_level is BoundSoundnessLevel.CERTIFIED
            for summary in report.method_summaries
            if summary.method is BoundMethod.GENERAL_LP_BOUNDS
        )

    def test_tighten_bounds_accepts_conditioning_only_with_aggregate_certificate(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = {
            "outcome": np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            "treatment": np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]),
            "metadata": {
                "conditioning_variables": {
                    "risk_stratum": [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
                }
            },
        }

        result = BoundsEngineMethod.pure_step(
            state,
            {"use_auto_bounds": False, "tighten_bounds": True, "has_monotone": True},
        )
        report = BoundsBundle.model_validate(result["bounds_report"])
        cert = coerce_bounds_certificate_bundle(result["dual_certificate_payload"])
        validation = validate_bounds_certificate_bundle(cert)

        assert report.tightening_status is TighteningStatus.IMPROVED
        assert isinstance(cert, StratifiedLPDualCertificateBundle)
        assert validation.ok, validation.errors
        assert any(
            summary.certificate_kind == "stratified_lp_primal_dual"
            for summary in report.method_summaries
        )

    def test_tighten_bounds_supports_assumption_family_candidates(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_exact_lp_state()
        result = BoundsEngineMethod.pure_step(
            state,
            {
                "use_auto_bounds": False,
                "tighten_bounds": True,
                "tightening_assumptions": ["mtr"],
            },
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert report.tightening_status is TighteningStatus.IMPROVED
        assert report.best_in_class_claim is not None
        assert report.best_in_class_claim.selected_method is BoundMethod.GENERAL_LP_BOUNDS
        assert any(
            "assumption_card:monotone_treatment_response" in summary.assumptions_used
            for summary in report.method_summaries
            if summary.method is BoundMethod.GENERAL_LP_BOUNDS
        )

    def test_tighten_bounds_marks_budget_exhaustion_when_candidate_limit_hits(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = {
            "outcome": np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            "treatment": np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]),
            "metadata": {
                "conditioning_variables": {
                    "risk_stratum": [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
                }
            },
        }

        result = BoundsEngineMethod.pure_step(
            state,
            {
                "use_auto_bounds": False,
                "tighten_bounds": True,
                "tightening_candidate_limit": 0,
            },
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert report.tightening_status is TighteningStatus.INCOMPLETE
        assert report.tightening_stop_reason is TighteningStopReason.BUDGET_EXCEEDED
        assert report.best_in_class_claim is not None
        assert any(entry.reason == "budget_exceeded" for entry in report.best_in_class_claim.log)

    def test_tighten_bounds_reports_infeasible_instrument_family_candidates(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_invalid_iv_family_state()
        result = BoundsEngineMethod.pure_step(
            state,
            {
                "has_iv": True,
                "use_auto_bounds": False,
                "tighten_bounds": True,
                "instrument_family_thresholds": [0.5],
            },
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert report.tightening_status is TighteningStatus.BLOCKED
        assert (
            report.tightening_stop_reason
            is TighteningStopReason.MODEL_INFEASIBLE_UNDER_ALL_TIGHTENERS
        )
        assert report.best_in_class_claim is not None
        assert any(entry.status == "infeasible" for entry in report.best_in_class_claim.log)

    def test_tighten_bounds_blocks_when_no_certified_candidates_exist(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_state()
        result = BoundsEngineMethod.pure_step(
            state,
            {"use_auto_bounds": True, "tighten_bounds": True},
        )
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert "auto_bounds_excluded_from_headline_bundle_without_certificate" in report.warnings
        assert report.tightening_status is TighteningStatus.BLOCKED
        assert (
            report.tightening_stop_reason is TighteningStopReason.CLASS_NOT_CERTIFIABLE_WITH_BACKEND
        )


class TestBoundsEngineMethodWithIV:
    def test_with_binary_iv_runs_balke_pearl(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_iv_state()
        result = BoundsEngineMethod.pure_step(state, {"has_iv": True})
        report = BoundsBundle.model_validate(result["bounds_report"])
        methods = {r.method for r in report.method_summaries}
        assert BoundMethod.LP_BALKE_PEARL in methods

    def test_with_binary_iv_emits_dual_certificate_payload_for_tightest_exact_lp(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_iv_state()
        result = BoundsEngineMethod.pure_step(state, {"has_iv": True})
        report = BoundsBundle.model_validate(result["bounds_report"])

        assert "dual_certificate_payload" in result
        assert report.sharpness_status == "unknown"

    def test_with_binary_iv_blocks_balke_pearl_when_model_class_is_falsified(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_incompatible_binary_iv_state()
        result = BoundsEngineMethod.pure_step(state, {"has_iv": True})
        report = BoundsBundle.model_validate(result["bounds_report"])
        methods = {r.method for r in report.method_summaries}
        negative = NegativeCertificate.model_validate(result["negative_certificate"])

        assert BoundMethod.LP_BALKE_PEARL not in methods
        assert negative.blocking_type is BlockingType.MODEL_CLASS_INCOMPATIBLE
        assert result["model_class_compatibility"]["compatibility_status"] == "incompatible"
        assert any("binary_iv_model_class_incompatible" in warning for warning in report.warnings)

    def test_with_iv_reports_tighter_than_manski(self):
        """Balke-Pearl bounds should be at most as wide as Manski (typically tighter)."""
        from polisyos.foundry.methods.catalog.causal.bounds import ManskiBoundsEstimator
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_iv_state()
        base_state = {"outcome": state["outcome"], "treatment": state["treatment"]}
        manski_out = ManskiBoundsEstimator.pure_step(base_state, {})
        manski_width = manski_out["result"]["bound_width"]

        result = BoundsEngineMethod.pure_step(state, {"has_iv": True})
        report = BoundsBundle.model_validate(result["bounds_report"])
        # Tightest method should have width <= Manski width + epsilon
        assert report.lower_bound is not None
        assert report.upper_bound is not None
        tightest_width = report.upper_bound - report.lower_bound
        assert tightest_width <= manski_width + 0.01  # allow tiny numerical slack


class TestBoundsEngineMethodWithSelection:
    def test_with_selection_includes_lee_bounds(self):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        state = _make_selection_state()
        result = BoundsEngineMethod.pure_step(state, {"has_selection": True})
        report = BoundsBundle.model_validate(result["bounds_report"])
        methods = {r.method for r in report.method_summaries}
        # Lee bounds use IV_BOUNDS method tag
        assert BoundMethod.IV_BOUNDS in methods


class TestBoundsEngineRegistration:
    def test_registered_fqn(self):
        from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
        from polisyos.foundry.methods.registry import MethodRegistry

        MethodRegistry.reset_instance()
        ensure_causal_methods_registered()
        registry = MethodRegistry.get_instance()
        bounds_names = {sig.name for sig in registry.query(namespace="causal.bounds")}
        assert "bounds_engine" in bounds_names
        assert "optimization" in bounds_names

    def test_optimization_registered(self):
        from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
        from polisyos.foundry.methods.registry import MethodRegistry

        MethodRegistry.reset_instance()
        ensure_causal_methods_registered()
        registry = MethodRegistry.get_instance()
        bounds_names = {sig.name for sig in registry.query(namespace="causal.bounds")}
        assert "optimization" in bounds_names


# ---------------------------------------------------------------------------
# OptimizationBasedBoundsEstimator — unit tests
# ---------------------------------------------------------------------------


class TestOptimizationBasedBoundsEstimator:
    def test_mtr_runs(self):
        from polisyos.foundry.methods.catalog.causal.bounds import OptimizationBasedBoundsEstimator

        state = _make_state()
        result = OptimizationBasedBoundsEstimator.pure_step(state, {"assumption": "mtr"})
        inner = result["result"]
        assert "ate_lower_bound" in inner
        assert "ate_upper_bound" in inner
        assert inner["ate_lower_bound"] <= inner["ate_upper_bound"]

    def test_mtr_tightens_manski_on_positive_dgp(self):
        """Under a strongly positive DGP (Y(1) >> Y(0)), MTR should not widen Manski."""
        from polisyos.foundry.methods.catalog.causal.bounds import (
            ManskiBoundsEstimator,
            OptimizationBasedBoundsEstimator,
        )

        rng = np.random.default_rng(99)
        n = 500
        T = rng.integers(0, 2, size=n).astype(float)
        # Strongly positive effect — satisfies MTR
        Y = 0.7 * T + 0.1 + rng.normal(0, 0.05, size=n)
        Y = np.clip(Y, 0.0, 1.0)
        state = {"outcome": Y, "treatment": T}

        manski = ManskiBoundsEstimator.pure_step(state, {})
        mtr = OptimizationBasedBoundsEstimator.pure_step(state, {"assumption": "mtr"})

        manski_width = manski["result"]["bound_width"]
        mtr_width = mtr["result"]["bound_width"]
        # MTR should be at least as tight as Manski (or tighter)
        assert mtr_width <= manski_width + 0.01

    def test_miv_with_proxy(self):
        from polisyos.foundry.methods.catalog.causal.bounds import OptimizationBasedBoundsEstimator

        rng = np.random.default_rng(11)
        n = 400
        Z = rng.uniform(0, 10, size=n)  # non-binary MIV proxy
        T = (rng.random(size=n) < 0.2 + 0.05 * Z / 10).astype(float)
        Y = 0.3 * T + rng.normal(0, 0.1, size=n)
        Y = np.clip(Y, 0.0, 1.0)
        state = {"outcome": Y, "treatment": T, "miv_proxy": Z}

        result = OptimizationBasedBoundsEstimator.pure_step(
            state, {"assumption": "miv", "n_strata": 4}
        )
        inner = result["result"]
        assert inner["ate_lower_bound"] <= inner["ate_upper_bound"]
        assert inner.get("assumption") == "miv"

    def test_mts_via_lp(self):
        from polisyos.foundry.methods.catalog.causal.bounds import OptimizationBasedBoundsEstimator

        state = _make_state()
        result = OptimizationBasedBoundsEstimator.pure_step(state, {"assumption": "mts"})
        inner = result["result"]
        assert inner["ate_lower_bound"] <= inner["ate_upper_bound"]

    def test_partial_id_result_in_output(self):
        from polisyos.foundry.methods.catalog.causal.bounds import OptimizationBasedBoundsEstimator

        state = _make_state()
        result = OptimizationBasedBoundsEstimator.pure_step(state, {"assumption": "mtr"})
        pid = result["result"]["partial_id_result"]
        reconstructed = PartialIdentificationResult.model_validate(pid)
        assert reconstructed.method == BoundMethod.MTR_BOUNDS
