from __future__ import annotations

import csv
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import benchmarks.estimation.lbidd_benchmark as lbidd_benchmark
import benchmarks.hte.interpretable_hte_benchmark as hte_benchmark
from benchmarks.estimation.acic_benchmark import DGPResult, _check_acic_results
from benchmarks.estimation.acic_benchmark import _make_method_fns as make_acic_method_fns
from benchmarks.estimation.lbidd_benchmark import _lbidd_causal_forest_params, _try_load_lbidd
from benchmarks.estimation.lbidd_benchmark import _make_method_fns as make_lbidd_method_fns
from benchmarks.estimation.realcause_benchmark import _discover_realcause_real_datasets
from benchmarks.estimation.realcause_benchmark import _make_method_fns as make_realcause_method_fns
from benchmarks.estimator_profiles import policyos_nuisance_params
from benchmarks.hte.interpretable_hte_benchmark import (
    HTECaseResult,
    _hte_causal_bcf_params,
    _hte_causal_forest_params,
    build_interpretable_hte_harness,
)
from benchmarks.hte.interpretable_hte_benchmark import _make_method_fns as make_hte_method_fns
from benchmarks.policyos_runner import extract_policyos_result
from benchmarks.runtime import BenchmarkTier


def test_realcause_discovers_upstream_flat_samples(tmp_path: Path) -> None:
    root = tmp_path / "realcause"
    data_dir = root / "realcause_datasets"
    data_dir.mkdir(parents=True)
    sample_file = data_dir / "demo_sample0.csv"

    fieldnames = ["x1", "x2", "t", "y", "y0", "y1", "ite"]
    with sample_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(40):
            y0 = float(idx) * 0.1
            ite = 1.0 + 0.01 * idx
            t = float(idx % 2)
            y1 = y0 + ite
            y = y1 if t > 0.5 else y0
            writer.writerow(
                {
                    "x1": float(idx),
                    "x2": float(idx % 3),
                    "t": t,
                    "y": y,
                    "y0": y0,
                    "y1": y1,
                    "ite": ite,
                }
            )

    discovered = _discover_realcause_real_datasets(root)
    assert len(discovered) == 1
    name, data, cate_true, ate_true = discovered[0]
    assert name == "demo_sample0"
    assert data.covariates.shape == (40, 2)
    assert cate_true.shape == (40,)
    assert ate_true > 1.0


def test_lbidd_loader_supports_normalized_sampleid_layout(tmp_path: Path) -> None:
    root = tmp_path / "lbidd_root" / "lbidd_normalized"
    root.mkdir(parents=True)

    with (root / "x.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "x1", "x2"])
        writer.writeheader()
        for idx in range(50):
            writer.writerow({"sample_id": idx, "x1": idx * 0.1, "x2": idx * 0.2})

    with (root / "zy_demo.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample_id", "z", "y", "mu1", "mu0"])
        writer.writeheader()
        for idx in range(40):
            writer.writerow(
                {
                    "sample_id": idx,
                    "z": idx % 2,
                    "y": 1.0 + idx * 0.05,
                    "mu1": 2.0 + idx * 0.05,
                    "mu0": 1.0 + idx * 0.05,
                }
            )

    loaded = _try_load_lbidd(root.parent)
    assert loaded is not None
    assert len(loaded) == 1
    name, data, cate_true = loaded[0]
    assert name == "zy_demo"
    assert data.covariates.shape == (40, 2)
    assert cate_true.shape == (40,)


def test_acic_benchmark_has_local_policyos_methods() -> None:
    production_fns = make_acic_method_fns(seed_offset=7, method_profile="production_estimation")
    assert "policy_os_aipw_cf" in production_fns
    assert "policy_os_tmle_cf" in production_fns
    assert "policy_os_causal_forest" in production_fns
    assert "policy_os_xlearner_cf" in production_fns
    assert "policy_os_drlearner_cf" not in production_fns
    assert "policy_os_forestdr_cf" not in production_fns

    full_matrix_fns = make_acic_method_fns(seed_offset=7, method_profile="full_matrix_estimation")
    assert "policy_os_drlearner_cf" in full_matrix_fns
    assert "policy_os_forestdr_cf" in full_matrix_fns


def test_lbidd_and_realcause_use_production_estimation_profiles() -> None:
    lbidd_production = make_lbidd_method_fns(seed_offset=7, method_profile="production_estimation")
    assert "policy_os_causal_forest" in lbidd_production
    assert "policy_os_xlearner_cf" in lbidd_production
    assert "policy_os_causal_bcf" not in lbidd_production
    assert "policy_os_drlearner_cf" not in lbidd_production

    lbidd_full = make_lbidd_method_fns(seed_offset=7, method_profile="full_matrix_estimation")
    assert "policy_os_causal_bcf" in lbidd_full
    assert "policy_os_drlearner_cf" in lbidd_full

    realcause_production = make_realcause_method_fns(
        seed_offset=7,
        dataset_name="lalonde_cps_sample0",
        method_profile="production_estimation",
    )
    assert "policy_os_xlearner_cf" in realcause_production
    assert "policy_os_causal_forest" in realcause_production
    assert "policy_os_causal_bcf" not in realcause_production
    assert "policy_os_drlearner_cf" not in realcause_production


def test_hte_benchmark_has_local_policyos_methods() -> None:
    production_fns = make_hte_method_fns(seed_offset=7, method_profile="production_hte")
    assert "policy_os_causal_bcf" in production_fns
    assert "policy_os_causal_forest" in production_fns
    assert "policy_os_xlearner_cf" in production_fns
    assert "policy_os_drlearner_cf" not in production_fns
    assert "policy_os_rlearner_cf" not in production_fns

    exploratory_fns = make_hte_method_fns(seed_offset=7, method_profile="exploratory_hte")
    assert "policy_os_drlearner_cf" in exploratory_fns
    assert "policy_os_rlearner_cf" in exploratory_fns
    assert "policy_os_xlearner_cf" in exploratory_fns


def test_local_nuisance_profile_uses_smoke_friendly_crossfit_defaults() -> None:
    params = policyos_nuisance_params(BenchmarkTier.LOCAL_EVIDENCE, seed=7)
    assert params["crossfit_folds"] == 3
    assert params["n_repeats"] == 1
    assert params["propensity_clipping"] == 0.025
    assert params["propensity_trimming"] == 0.025
    assert params["parallel_folds"] is True


def test_local_benchmark_overrides_do_not_force_overly_coarse_hte_trees() -> None:
    lbidd_forest = _lbidd_causal_forest_params(BenchmarkTier.LOCAL_EVIDENCE, seed=7)
    hte_forest = _hte_causal_forest_params(BenchmarkTier.LOCAL_EVIDENCE, seed=7)
    hte_bcf = _hte_causal_bcf_params(BenchmarkTier.LOCAL_EVIDENCE, seed=7)

    assert lbidd_forest["min_samples_leaf"] <= 8
    assert max(lbidd_forest["min_samples_leaf_candidates"]) <= 12
    assert hte_forest["min_samples_leaf"] <= 8
    assert max(hte_forest["min_samples_leaf_candidates"]) <= 12
    assert hte_forest["model_y_backend"] == "elastic_net"
    assert hte_forest["model_t_backend"] == "logistic_regression"
    assert hte_forest["cate_refinement_backend"] == "ridge_blend"
    assert hte_forest["cate_refinement_weight"] == pytest.approx(0.67)
    assert hte_bcf["backend"] == "stochtree"
    assert hte_bcf["cate_refinement_backend"] == "elastic_net_blend"
    assert hte_bcf["cate_refinement_weight"] == pytest.approx(0.5)
    assert hte_bcf["num_trees_tau"] >= 80


def test_extract_policyos_result_normalizes_dict_feature_importances() -> None:
    class DummyMethod:
        __name__ = "DummyMethod"

    data = SimpleNamespace(
        covariates=[[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]],
        feature_names=["age", "income", "risk"],
    )
    extracted = extract_policyos_result(
        DummyMethod,
        data,
        {
            "result": {
                "ate": 1.0,
                "ci_lower": 0.5,
                "ci_upper": 1.5,
                "feature_importances": [
                    {"feature_name": "age", "importance_score": 2.0},
                    {"feature_name": "risk", "importance_score": 1.0},
                ],
            }
        },
    )

    assert extracted.failed is False
    assert extracted.feature_importances is not None
    assert extracted.feature_importances.tolist() == [2.0 / 3.0, 0.0, 1.0 / 3.0]


def test_extract_policyos_result_carries_selection_manifest_and_hte_intervals() -> None:
    class DummyMethod:
        __name__ = "DummyMethod"

    data = SimpleNamespace(
        covariates=[[1.0, 2.0], [2.0, 1.0], [0.5, -1.0]],
        feature_names=["age", "income"],
    )
    extracted = extract_policyos_result(
        DummyMethod,
        data,
        {
            "result": {
                "ate": 0.8,
                "ci_lower": 0.3,
                "ci_upper": 1.2,
                "cate_predictions": [0.4, 0.9, 1.1],
                "cate_ci_lower_values": [0.1, 0.4, 0.7],
                "cate_ci_upper_values": [0.7, 1.2, 1.5],
                "nuisance_diagnostics": {
                    "calibration_modes": ["isotonic"],
                    "effective_sample_size": 75.0,
                },
                "nuisance_contract": {
                    "propensity_backend": "lightgbm",
                    "outcome_backend": "lightgbm",
                    "propensity_backend_candidates": ["lightgbm", "rf"],
                    "outcome_backend_candidates": ["lightgbm", "elastic_net"],
                    "selection_objective": "causal_risk",
                    "overlap_diagnostic_policy": "crossfit",
                },
                "selection_manifest": {
                    "selected_propensity_backend": "lightgbm",
                    "selected_outcome_backend": "lightgbm",
                    "tested_propensity_backends": ["lightgbm", "rf"],
                    "tested_outcome_backends": ["lightgbm", "elastic_net"],
                    "selection_objective": "causal_risk",
                    "split_policy": "crossfit",
                    "calibration_modes": ["isotonic"],
                },
            }
        },
    )

    assert extracted.selection_manifest["selected_propensity_backend"] == "lightgbm"
    assert extracted.selection_manifest["selection_objective"] == "causal_risk"
    assert extracted.cate_ci_lower_values.tolist() == [0.1, 0.4, 0.7]
    assert extracted.cate_ci_upper_values.tolist() == [0.7, 1.2, 1.5]


def test_lbidd_posthoc_calibration_preserves_estimator_ate_and_ci(monkeypatch) -> None:
    class DummyMethod:
        __name__ = "DummyMethod"

    n_obs = 40
    data = SimpleNamespace(
        covariates=np.column_stack([np.linspace(0.0, 1.0, n_obs), np.linspace(1.0, 2.0, n_obs)]),
        treatment=np.array([0, 1] * (n_obs // 2), dtype=float),
        outcome=np.linspace(0.0, 4.0, n_obs),
    )
    extracted = SimpleNamespace(
        failed=False,
        fail_reason="",
        ate_pred=1.25,
        ate_ci_lower=0.9,
        ate_ci_upper=1.6,
        cate_pred=np.linspace(0.1, 0.9, n_obs),
        selection_manifest={"calibration_modes": []},
        nuisance_diagnostics={"effective_sample_size": 80.0},
    )

    monkeypatch.setattr(
        lbidd_benchmark, "invoke_policyos_method", lambda *args, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(
        lbidd_benchmark, "extract_policyos_result", lambda *args, **kwargs: extracted
    )
    monkeypatch.setattr(
        lbidd_benchmark,
        "posthoc_cate_calibration",
        lambda *args, **kwargs: (
            np.full(n_obs, 9.0, dtype=float),
            {"calibration_mode": "causal_isotonic"},
        ),
    )

    metrics = lbidd_benchmark._run_policy_os_method(DummyMethod, data, {})

    assert metrics.ate_pred == 1.25
    assert metrics.ate_ci_lower == 0.9
    assert metrics.ate_ci_upper == 1.6
    assert metrics.cate_pred is not None
    assert metrics.cate_pred.tolist() == [9.0] * n_obs


def test_acic_quartile_floor_uses_absolute_reference_for_near_oracle_best() -> None:
    results = {
        "ols": DGPResult(
            dgp_name="strong_overlap_rct_like",
            method_name="ols",
            n_reps=1,
            ate_true=0.5,
            ate_biases=[0.002],
            ci_covers=[True],
            ci_widths=[0.2],
            pehe_values=[],
            n_failed=0,
        ),
        "policy_os_aipw_cf": DGPResult(
            dgp_name="strong_overlap_rct_like",
            method_name="policy_os_aipw_cf",
            n_reps=1,
            ate_true=0.5,
            ate_biases=[0.12],
            ci_covers=[True],
            ci_widths=[0.6],
            pehe_values=[],
            n_failed=0,
        ),
    }

    assert _check_acic_results(
        case_name="strong_overlap_rct_like",
        results=results,
        ate_bias_threshold=0.25,
        min_ci_coverage=0.85,
    )


def test_run_policy_os_hte_sparse_refinement_updates_cate_raw_and_pred(monkeypatch) -> None:
    class DummyMethod:
        __name__ = "DummyMethod"

    gt = SimpleNamespace(
        data=SimpleNamespace(
            covariates=np.array(
                [
                    [0.0, 1.0],
                    [1.0, 0.0],
                    [2.0, 1.0],
                    [3.0, 0.5],
                ],
                dtype=float,
            ),
            treatment=np.array([0.0, 1.0, 0.0, 1.0], dtype=float),
            outcome=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
        )
    )
    extracted = SimpleNamespace(
        failed=False,
        fail_reason="",
        selection_manifest={"calibration_modes": []},
        cate_pred=np.array([1.0, 2.0, 3.0, 4.0], dtype=float),
        cate_raw=np.array([1.0, 2.0, 3.0, 4.0], dtype=float),
        cate_calibrated=None,
        ate_pred=2.5,
        ate_ci_lower=2.0,
        ate_ci_upper=3.0,
        hte_metadata={},
        cate_ci_lower_values=np.array([0.5, 1.5, 2.5, 3.5], dtype=float),
        cate_ci_upper_values=np.array([1.5, 2.5, 3.5, 4.5], dtype=float),
        feature_importances=np.array([0.7, 0.3], dtype=float),
    )
    refined = np.array([0.5, 1.5, 2.5, 3.5], dtype=float)

    monkeypatch.setattr(
        hte_benchmark, "invoke_policyos_method", lambda *args, **kwargs: {"ok": True}
    )
    monkeypatch.setattr(hte_benchmark, "extract_policyos_result", lambda *args, **kwargs: extracted)
    monkeypatch.setattr(
        hte_benchmark,
        "_maybe_refine_cate_with_sparse_surrogate",
        lambda *args, **kwargs: (
            refined,
            {
                "backend": "ridge_blend",
                "applied": True,
                "surrogate_r2": 0.82,
                "weight": 0.67,
            },
        ),
    )

    result = hte_benchmark._run_policy_os_hte(
        DummyMethod,
        gt,
        {"cate_refinement_backend": "ridge_blend", "cate_refinement_weight": 0.67},
    )

    assert result.cate_pred.tolist() == refined.tolist()
    assert result.cate_raw.tolist() == refined.tolist()
    assert result.cate_calibrated.tolist() == refined.tolist()
    assert result.ate_pred == pytest.approx(2.0)
    assert result.ate_ci_lower == pytest.approx(1.5)
    assert result.ate_ci_upper == pytest.approx(2.5)
    assert result.cate_ci_lower_values is None
    assert result.cate_ci_upper_values is None
    assert "sparse_surrogate_refinement" in result.selection_manifest["calibration_modes"]
    assert result.hte_metadata["cate_refinement_applied"] is True
    assert result.hte_metadata["cate_refinement_backend"] == "ridge_blend"
    assert result.hte_metadata["cate_refinement_surrogate_r2"] == pytest.approx(0.82)


def test_fast_local_hte_harness_keeps_standard_relative_pehe_bar(monkeypatch) -> None:
    monkeypatch.setenv("BENCH_TEST_FAST", "1")
    harness = build_interpretable_hte_harness(
        n_obs=200,
        n_reps=1,
        tier=BenchmarkTier.LOCAL_EVIDENCE,
        seed=42,
        method_profile="production_hte",
    )
    cate_case = next(case for case in harness._cases if case.name == "hte_cate::sparse_linear_2mod")

    def _case(pehe: float) -> HTECaseResult:
        return HTECaseResult(
            method_name="synthetic",
            pehe=pehe,
            cate_rms=0.4,
            ate_bias=0.01,
            ate_bias_abs=0.01,
            ate_bias_relative=0.02,
            precision_k=1.0,
            recall_k=1.0,
            ate_ci_covers=True,
            ate_ci_width=0.5,
            eceth=0.05,
            r_risk=0.05,
            rate=0.3,
            policy_value_top_q=1.0,
            calibration_mode="causal_isotonic",
            failed=False,
            elapsed_s=0.1,
        )

    synthetic_results = {
        "s_learner_linear": [_case(0.225)],
        "t_learner_rf": [_case(0.512)],
        "policy_os_causal_bcf": [_case(0.532)],
        "policy_os_causal_forest": [_case(0.515)],
        "policy_os_xlearner_cf": [_case(0.131)],
    }

    with pytest.raises(AssertionError):
        cate_case.checker(synthetic_results)
