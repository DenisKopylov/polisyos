"""Validation-stage fairness audit estimators and deployment gate helpers."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from statistics import NormalDist
from typing import Literal, Protocol, Self

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.fairness_audit_report import FairnessAuditReport

ArrayInput = Sequence[object] | np.ndarray | pd.Series
TaskType = Literal["binary", "multiclass", "regression", "ranking"]
CheckStatus = Literal["PASS", "WARN", "FAIL", "INSUFFICIENT_N", "NOT_COMPUTABLE"]

_EPS = 1e-12
_DEFAULT_BLOCK_MESSAGE = (
    "Automated decision is unavailable because the latest fairness audit found a "
    "protected-group or causal-fairness gap above the configured threshold."
)
_PROPORTION_METRICS = {
    "selection_rate",
    "base_rate",
    "true_positive_rate",
    "false_positive_rate",
    "false_negative_rate",
    "true_negative_rate",
    "positive_predictive_value",
    "negative_predictive_value",
    "accuracy",
}


class ProtectedAttributeConfig(BaseModel):
    """Declared protected attribute used for audit and governance."""

    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["categorical", "binary", "ordinal"] = "categorical"
    values: list[object] | None = None
    reference: Literal["configured", "largest_group"] = "largest_group"
    reference_value: object | None = None
    required: bool = True


class IntersectionalConfig(BaseModel):
    """Controls configured intersectional group construction."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    max_order: int = Field(default=2, ge=1, le=4)
    min_group_n: int = Field(default=100, ge=1)


class FairnessThreshold(BaseModel):
    """Thresholds and blocking behavior for one fairness check family."""

    model_config = ConfigDict(extra="forbid")

    max_abs_gap: float | None = None
    min_ratio: float | None = None
    mean_abs_score_delta_max: float | None = None
    p95_abs_score_delta_max: float | None = None
    flip_rate_max: float | None = None
    max_forbidden_path_effect: float | None = None
    max_direct_effect: float | None = None
    blocking: bool = True


class StatisticalTestsConfig(BaseModel):
    """Statistical settings for parity and causal-threshold tests."""

    model_config = ConfigDict(extra="forbid")

    alpha: float = Field(default=0.05, gt=0.0, lt=1.0)
    multiple_comparison_correction: Literal["none", "bonferroni", "holm", "fdr_bh"] = "holm"
    bootstrap_resamples: int = Field(default=2000, ge=0)
    random_seed: int = 1729


class CausalFairnessSpec(BaseModel):
    """Declared causal audit inputs; no causal columns are inferred from features."""

    model_config = ConfigDict(extra="forbid")

    protected_attribute: str | None = None
    outcome: str = "automated_decision"
    causal_graph_id: str | None = None
    graph_dot: str | None = None
    estimator: Literal[
        "declared",
        "residual_scm",
        "g_formula_plugin",
        "aipw_crossfit",
    ] = "declared"
    protected_reference_value: object | None = None
    protected_target_value: object | None = None
    covariate_columns: list[str] = Field(default_factory=list)
    mediator_columns: list[str] = Field(default_factory=list)
    counterfactual_pairs: list[tuple[object, object]] = Field(default_factory=list)
    counterfactual_scores: dict[str, list[float]] = Field(default_factory=dict)
    counterfactual_predictions: dict[str, list[object]] = Field(default_factory=dict)
    allowed_paths: list[list[str]] = Field(default_factory=list)
    forbidden_paths: list[list[str]] = Field(default_factory=list)
    pre_treatment_covariates: list[str] = Field(default_factory=list)
    allowed_mediators: list[str] = Field(default_factory=list)
    blocked_mediators: list[str] = Field(default_factory=list)
    path_effects: list[dict[str, object]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)


def _default_thresholds() -> dict[str, FairnessThreshold]:
    return {
        "demographic_parity_gap": FairnessThreshold(max_abs_gap=0.05, min_ratio=0.80),
        "selection_rate": FairnessThreshold(max_abs_gap=0.05, min_ratio=0.80),
        "equalized_odds_gap": FairnessThreshold(max_abs_gap=0.05),
        "equalized_odds": FairnessThreshold(max_abs_gap=0.05),
        "equal_opportunity_gap": FairnessThreshold(max_abs_gap=0.05),
        "false_positive_rate": FairnessThreshold(max_abs_gap=0.05, blocking=False),
        "false_negative_rate": FairnessThreshold(max_abs_gap=0.03),
        "false_negative_rate_gap": FairnessThreshold(max_abs_gap=0.03),
        "true_positive_rate": FairnessThreshold(max_abs_gap=0.05, blocking=False),
        "positive_predictive_value": FairnessThreshold(max_abs_gap=0.05, blocking=False),
        "calibration_error_by_group": FairnessThreshold(max_abs_gap=0.05, blocking=False),
        "counterfactual_fairness": FairnessThreshold(
            mean_abs_score_delta_max=0.02,
            p95_abs_score_delta_max=0.05,
            flip_rate_max=0.01,
        ),
        "path_specific_fairness": FairnessThreshold(max_forbidden_path_effect=0.02),
    }


class FairnessAuditConfig(BaseModel):
    """Configuration surface for the validation-stage fairness audit."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    task_type: TaskType = "binary"
    positive_label: object = 1
    protected_attributes: list[ProtectedAttributeConfig] = Field(default_factory=list)
    intersectional: IntersectionalConfig = Field(default_factory=IntersectionalConfig)
    thresholds: dict[str, FairnessThreshold] = Field(default_factory=_default_thresholds)
    statistical_tests: StatisticalTestsConfig = Field(default_factory=StatisticalTestsConfig)
    required_group_metrics: list[str] = Field(
        default_factory=lambda: [
            "selection_rate",
            "false_positive_rate",
            "false_negative_rate",
            "true_positive_rate",
            "positive_predictive_value",
            "calibration_error_by_group",
        ]
    )
    min_group_n: int = Field(default=100, ge=1)
    min_effective_n: int = Field(default=50, ge=1)
    missing_protected_attribute_max_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    positivity_min_propensity: float = Field(default=0.02, ge=0.0, le=1.0)
    positivity_max_propensity: float = Field(default=0.98, ge=0.0, le=1.0)
    causal_spec_required: bool = True
    high_impact: bool = True
    require_pass_to_deploy: bool = True
    model_id: str | None = None
    dataset_id: str | None = None
    audit_id: str | None = None


@dataclass(frozen=True)
class FairnessAuditInput:
    """Explicit fairness audit frame."""

    y_true: ArrayInput | None
    y_pred: ArrayInput
    y_score: ArrayInput | None
    protected: pd.DataFrame
    features: pd.DataFrame | None = None
    sample_weight: ArrayInput | None = None
    decision_threshold: float | dict[str, float] | None = None
    task_type: TaskType = "binary"


@dataclass(frozen=True)
class FairnessAuditResult:
    """Runner result wrapper with the validation-report embedding shape."""

    report: FairnessAuditReport

    def to_validation_report(self) -> dict[str, object]:
        return self.report.to_validation_report_payload()


class FairnessAuditEstimator(Protocol):
    """Common estimator interface for validation-stage fairness audit components."""

    def fit(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        sample_weight: ArrayInput | None = None,
        causal_spec: CausalFairnessSpec | None = None,
        config: FairnessAuditConfig,
    ) -> Self:
        """Fit or bind the estimator to an explicit audit frame."""

    def estimate(self) -> dict[str, object]:
        """Return descriptive estimates."""

    def test(self) -> dict[str, object]:
        """Return test decisions."""

    def to_validation_report(self) -> dict[str, object]:
        """Return the report fragment for ``ValidationReport.fairness_audit``."""


class GroupMetricBreakdownEstimator:
    """Compute group-wise parity and error metrics for protected groups."""

    def fit(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        sample_weight: ArrayInput | None = None,
        causal_spec: CausalFairnessSpec | None = None,
        config: FairnessAuditConfig,
    ) -> Self:
        del features, causal_spec
        self.config = config
        self.audit_input = _coerce_audit_input(
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            protected=protected,
            sample_weight=sample_weight,
            task_type=config.task_type,
        )
        self.result = self._build()
        return self

    def estimate(self) -> dict[str, object]:
        return self.result

    def test(self) -> dict[str, object]:
        return {"diagnostics": self.result.get("diagnostics", [])}

    def to_validation_report(self) -> dict[str, object]:
        return self.result

    def _build(self) -> dict[str, object]:
        audit_input = self.audit_input
        config = self.config
        n = len(audit_input.protected)
        y_pred_bin = _binary_array(audit_input.y_pred, config.positive_label)
        y_true_bin = (
            _binary_array(audit_input.y_true, config.positive_label)
            if audit_input.y_true is not None
            else None
        )
        y_score = _score_array(audit_input.y_score)
        weights = _weight_array(audit_input.sample_weight, n)
        attribute_configs = _attribute_configs(config, audit_input.protected)
        attribute_frames, diagnostics = _build_attribute_frames(
            audit_input.protected,
            attribute_configs,
            config,
        )
        missingness = _protected_missingness(audit_input.protected, attribute_configs)
        groups_summary: list[dict[str, object]] = []
        group_metrics: list[dict[str, object]] = []

        for attr_name, values in attribute_frames.items():
            attr_config = _config_for_attribute(attr_name, attribute_configs)
            reference = _reference_group(values, attr_config)
            for group_value in _stable_unique(values):
                mask = values == group_value
                n_group = int(mask.sum())
                effective_n = _effective_n(weights[mask])
                min_group_n = _min_group_n_for_attribute(attr_name, config)
                groups_summary.append(
                    {
                        "attribute": attr_name,
                        "value": group_value,
                        "n": n_group,
                        "effective_n": float(effective_n),
                    }
                )
                if n_group < min_group_n:
                    diagnostics.append(
                        {
                            "code": "MIN_GROUP_N",
                            "attribute": attr_name,
                            "group": group_value,
                            "value": n_group,
                            "threshold": min_group_n,
                            "status": "INSUFFICIENT_N",
                            "blocking": True,
                            "required": True,
                        }
                    )
                if effective_n < config.min_effective_n:
                    diagnostics.append(
                        {
                            "code": "MIN_EFFECTIVE_N",
                            "attribute": attr_name,
                            "group": group_value,
                            "value": float(effective_n),
                            "threshold": config.min_effective_n,
                            "status": "INSUFFICIENT_N",
                            "blocking": True,
                            "required": True,
                        }
                    )

                metrics = _binary_group_metrics(
                    mask=mask,
                    y_pred_bin=y_pred_bin,
                    y_true_bin=y_true_bin,
                    y_score=y_score,
                    weights=weights,
                    alpha=config.statistical_tests.alpha,
                    task_type=config.task_type,
                )
                group_metrics.append(
                    {
                        "attribute": attr_name,
                        "group": group_value,
                        "reference_group": reference,
                        "n": n_group,
                        "effective_n": float(effective_n),
                        "metrics": metrics,
                    }
                )

        diagnostics.extend(_missingness_diagnostics(missingness, config))
        diagnostics.extend(_declared_value_diagnostics(audit_input.protected, attribute_configs))
        diagnostics.extend(_missingness_by_group_diagnostics(audit_input.protected, attribute_configs))
        diagnostics.append(
            {
                "code": "LABEL_BIAS_WARNING",
                "message": (
                    "Fairness metrics use observed labels when provided; label bias remains a "
                    "domain assumption and must be reviewed separately."
                ),
                "status": "WARN",
            }
        )

        return {
            "input_summary": {
                "n": n,
                "weighted": audit_input.sample_weight is not None,
                "has_y_true": audit_input.y_true is not None,
                "has_y_score": audit_input.y_score is not None,
                "decision_threshold": audit_input.decision_threshold,
                "protected_attribute_missingness": missingness,
                "groups": groups_summary,
            },
            "group_metrics": group_metrics,
            "attribute_values": {key: values.tolist() for key, values in attribute_frames.items()},
            "diagnostics": diagnostics,
        }


class ParityGapTestEstimator:
    """Run parity-gap tests with CIs, p-values, and multiplicity adjustment."""

    def fit(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        sample_weight: ArrayInput | None = None,
        causal_spec: CausalFairnessSpec | None = None,
        config: FairnessAuditConfig,
        group_result: Mapping[str, object] | None = None,
    ) -> Self:
        del features, causal_spec
        self.config = config
        self.audit_input = _coerce_audit_input(
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            protected=protected,
            sample_weight=sample_weight,
            task_type=config.task_type,
        )
        self.group_result = dict(group_result or {})
        self.result = self._build()
        return self

    def estimate(self) -> dict[str, object]:
        return self.result

    def test(self) -> dict[str, object]:
        return self.result

    def to_validation_report(self) -> dict[str, object]:
        return self.result

    def _build(self) -> dict[str, object]:
        group_metrics = _as_list_of_dicts(self.group_result.get("group_metrics"))
        tests: list[dict[str, object]] = []
        tests.extend(self._pairwise_metric_tests(group_metrics))
        tests.extend(self._aggregate_gap_tests(group_metrics))
        _apply_test_multiplicity(tests, self.config)
        for test in tests:
            _finalize_parity_status(test, self.config)
            _decorate_test_decision(test, self.config)
        return {"parity_tests": tests}

    def _pairwise_metric_tests(self, group_metrics: list[dict[str, object]]) -> list[dict[str, object]]:
        tests: list[dict[str, object]] = []
        by_attr: dict[str, list[dict[str, object]]] = {}
        for entry in group_metrics:
            by_attr.setdefault(str(entry["attribute"]), []).append(entry)
        for attr, entries in by_attr.items():
            reference_group = str(entries[0].get("reference_group", ""))
            ref_entry = next((entry for entry in entries if str(entry["group"]) == reference_group), None)
            if ref_entry is None:
                continue
            for entry in entries:
                group = str(entry["group"])
                if group == reference_group:
                    continue
                for metric in self.config.required_group_metrics:
                    tests.append(_pairwise_metric_test(attr, entry, ref_entry, metric, self.config))
        return tests

    def _aggregate_gap_tests(self, group_metrics: list[dict[str, object]]) -> list[dict[str, object]]:
        tests: list[dict[str, object]] = []
        by_attr: dict[str, list[dict[str, object]]] = {}
        for entry in group_metrics:
            by_attr.setdefault(str(entry["attribute"]), []).append(entry)
        for attr, entries in by_attr.items():
            tests.append(
                self._aggregate_gap_test(
                    attr=attr,
                    entries=entries,
                    test_metric="demographic_parity_gap",
                    component_metrics=("selection_rate",),
                )
            )
            tests.append(
                self._aggregate_gap_test(
                    attr=attr,
                    entries=entries,
                    test_metric="equal_opportunity_gap",
                    component_metrics=("true_positive_rate",),
                )
            )
            tests.append(
                self._aggregate_gap_test(
                    attr=attr,
                    entries=entries,
                    test_metric="equalized_odds_gap",
                    component_metrics=("true_positive_rate", "false_positive_rate"),
                )
            )
            tests.append(
                self._aggregate_gap_test(
                    attr=attr,
                    entries=entries,
                    test_metric="false_negative_rate_gap",
                    component_metrics=("false_negative_rate",),
                )
            )
        return tests

    def _aggregate_gap_test(
        self,
        *,
        attr: str,
        entries: list[dict[str, object]],
        test_metric: str,
        component_metrics: tuple[str, ...],
    ) -> dict[str, object]:
        best_component: str | None = None
        best_gap = -math.inf
        best_pair: tuple[dict[str, object], dict[str, object]] | None = None
        for component in component_metrics:
            computable = [
                entry
                for entry in entries
                if _metric_status(entry, component) == "PASS"
                and _metric_estimate(entry, component) is not None
            ]
            if len(computable) < 2:
                continue
            ordered = sorted(computable, key=lambda entry: _metric_estimate(entry, component) or 0.0)
            gap = (_metric_estimate(ordered[-1], component) or 0.0) - (
                _metric_estimate(ordered[0], component) or 0.0
            )
            if gap > best_gap:
                best_gap = gap
                best_component = component
                best_pair = (ordered[0], ordered[-1])

        threshold_config = _threshold_for(test_metric, self.config)
        threshold = _max_abs_threshold(test_metric, threshold_config)
        if best_component is None or best_pair is None:
            return {
                "test_id": f"{attr}.{test_metric}",
                "attribute": attr,
                "metric": test_metric,
                "component_metric": None,
                "gap_type": "max_minus_min",
                "estimate": None,
                "abs_estimate": None,
                "threshold": threshold,
                "p_value": None,
                "p_value_adjusted": None,
                "test_name": "not_computable",
                "multiple_comparison_correction": self.config.statistical_tests.multiple_comparison_correction,
                "status": "NOT_COMPUTABLE",
                "blocking": threshold_config.blocking,
                "required": True,
            }

        low_entry, high_entry = best_pair
        ci_low, ci_high = _bootstrap_aggregate_gap_ci(
            attr=attr,
            component_metrics=component_metrics,
            audit_input=self.audit_input,
            attribute_values=self.group_result.get("attribute_values"),
            config=self.config,
        )
        pair_test = _two_sample_metric_difference(
            high_entry,
            low_entry,
            best_component,
            self.config.statistical_tests.alpha,
        )
        ratio = _safe_ratio(
            _metric_estimate(low_entry, best_component),
            _metric_estimate(high_entry, best_component),
        )
        return {
            "test_id": f"{attr}.{test_metric}",
            "attribute": attr,
            "metric": test_metric,
            "component_metric": best_component,
            "group": str(high_entry["group"]),
            "reference_group": str(low_entry["group"]),
            "gap_type": "max_minus_min",
            "estimate": float(best_gap),
            "abs_estimate": float(abs(best_gap)),
            "threshold": threshold,
            "ratio": ratio,
            "ratio_threshold": threshold_config.min_ratio,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "p_value": pair_test.get("p_value"),
            "p_value_adjusted": None,
            "test_name": f"aggregate_gap_{pair_test.get('test_name', 'difference_test')}",
            "multiple_comparison_correction": self.config.statistical_tests.multiple_comparison_correction,
            "status": "PASS",
            "blocking": threshold_config.blocking,
            "required": True,
        }


class CounterfactualFairnessEstimator:
    """Audit individual-level counterfactual prediction invariance."""

    def fit(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        sample_weight: ArrayInput | None = None,
        causal_spec: CausalFairnessSpec | None = None,
        config: FairnessAuditConfig,
    ) -> Self:
        del y_true, sample_weight
        self.config = config
        self.y_pred = y_pred
        self.y_score = y_score
        self.protected = protected
        self.features = features
        self.causal_spec = causal_spec
        self.result = self._build()
        return self

    def estimate(self) -> dict[str, object]:
        return self.result

    def test(self) -> dict[str, object]:
        return self.result

    def to_validation_report(self) -> dict[str, object]:
        return self.result

    def _build(self) -> dict[str, object]:
        threshold = _threshold_for("counterfactual_fairness", self.config)
        spec = self.causal_spec
        if spec is None or (
            not spec.counterfactual_scores and not spec.counterfactual_predictions
        ):
            if spec is not None and self.features is not None:
                scm_result = _counterfactual_residual_scm_result(
                    y_pred=self.y_pred,
                    y_score=self.y_score,
                    protected=self.protected,
                    features=self.features,
                    spec=spec,
                    config=self.config,
                )
                if scm_result is not None:
                    return scm_result
            return {
                "enabled": self.config.causal_spec_required,
                "status": "NOT_COMPUTABLE",
                "definition": "counterfactual_prediction_invariance",
                "estimator": "declared_counterfactual_outcomes",
                "scores": {},
                "required": self.config.causal_spec_required,
                "blocking": threshold.blocking,
                "assumptions": [],
                "diagnostics": {
                    "reason": "counterfactual fairness requires an SCM or declared counterfactual outcomes"
                },
            }

        attr = spec.protected_attribute or _first_protected_attribute(self.config, self.protected)
        pairs = spec.counterfactual_pairs or _counterfactual_pairs_from_keys(
            spec.counterfactual_scores,
            spec.counterfactual_predictions,
        )
        pair_payloads: list[dict[str, object]] = []
        score_deltas: list[np.ndarray] = []
        flip_indicators: list[np.ndarray] = []
        for from_value, to_value in pairs:
            key = _counterfactual_key(attr, from_value, to_value)
            alt_score = _lookup_counterfactual_vector(spec.counterfactual_scores, key)
            alt_pred = _lookup_counterfactual_vector(spec.counterfactual_predictions, key)
            mask = _protected_pair_mask(self.protected, attr, from_value)
            pair_result = _counterfactual_pair_result(
                key=key,
                from_value=from_value,
                to_value=to_value,
                mask=mask,
                y_score=self.y_score,
                y_pred=self.y_pred,
                alt_score=alt_score,
                alt_pred=alt_pred,
                config=self.config,
            )
            pair_payloads.append(pair_result["payload"])
            if pair_result["score_deltas"].size:
                score_deltas.append(pair_result["score_deltas"])
            if pair_result["flip_indicators"].size:
                flip_indicators.append(pair_result["flip_indicators"])

        all_score_deltas = np.concatenate(score_deltas) if score_deltas else np.asarray([])
        all_flips = np.concatenate(flip_indicators) if flip_indicators else np.asarray([])
        scores = _counterfactual_scores_payload(
            score_deltas=all_score_deltas,
            flip_indicators=all_flips,
            threshold=threshold,
            config=self.config,
        )
        status = _worst_status(
            [str(payload.get("status", "PASS")) for payload in scores.values()]
        )
        return {
            "enabled": True,
            "status": status,
            "definition": "counterfactual_prediction_invariance",
            "protected_attribute": attr,
            "estimator": "declared_counterfactual_outcomes_bootstrap",
            "counterfactual_pairs": [[str(left), str(right)] for left, right in pairs],
            "pair_results": pair_payloads,
            "scores": scores,
            "required": self.config.causal_spec_required,
            "blocking": threshold.blocking,
            "assumptions": spec.assumptions
            or [
                "structural causal model or counterfactual generator supplied externally",
                "counterfactual outcomes align row-wise with the validation data",
            ],
            "diagnostics": {
                "bootstrap_resamples": self.config.statistical_tests.bootstrap_resamples,
                **spec.diagnostics,
            },
        }


class PathSpecificFairnessEstimator:
    """Audit forbidden causal path effects declared by a causal fairness spec."""

    def fit(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        sample_weight: ArrayInput | None = None,
        causal_spec: CausalFairnessSpec | None = None,
        config: FairnessAuditConfig,
    ) -> Self:
        del y_true, sample_weight
        self.config = config
        self.y_pred = y_pred
        self.y_score = y_score
        self.protected = protected
        self.features = features
        self.causal_spec = causal_spec
        self.result = self._build()
        return self

    def estimate(self) -> dict[str, object]:
        return self.result

    def test(self) -> dict[str, object]:
        return self.result

    def to_validation_report(self) -> dict[str, object]:
        return self.result

    def _build(self) -> dict[str, object]:
        threshold = _threshold_for("path_specific_fairness", self.config)
        spec = self.causal_spec
        if spec is None:
            return {
                "enabled": self.config.causal_spec_required,
                "status": "NOT_COMPUTABLE",
                "definition": "forbidden_path_specific_effect",
                "estimator": "declared_path_specific_effects",
                "effects": [],
                "required": self.config.causal_spec_required,
                "blocking": threshold.blocking,
                "diagnostics": {
                    "reason": "path-specific fairness requires a causal DAG and path effects"
                },
            }
        if not spec.path_effects:
            if self.features is not None and spec.graph_dot:
                catalog_result = _path_specific_catalog_result(
                    y_pred=self.y_pred,
                    y_score=self.y_score,
                    protected=self.protected,
                    features=self.features,
                    spec=spec,
                    threshold=threshold,
                    config=self.config,
                )
                if catalog_result is not None:
                    return catalog_result
        if not spec.path_effects and not spec.forbidden_paths:
            return {
                "enabled": self.config.causal_spec_required,
                "status": "NOT_COMPUTABLE",
                "definition": "forbidden_path_specific_effect",
                "estimator": "declared_path_specific_effects",
                "effects": [],
                "required": self.config.causal_spec_required,
                "blocking": threshold.blocking,
                "diagnostics": {
                    "reason": "path-specific fairness requires a causal DAG and path effects"
                },
            }
        effects = _path_effect_payloads(spec, threshold, self.config)
        status = _worst_status([str(effect.get("status", "PASS")) for effect in effects])
        diagnostics = {
            "nuisance_models": ["declared_or_external"],
            **_causal_overlap_diagnostics(spec, self.config),
            **spec.diagnostics,
        }
        status = _worst_status([status, str(diagnostics.get("overlap_status", "PASS"))])
        return {
            "enabled": True,
            "status": status,
            "definition": "forbidden_path_specific_effect",
            "protected_attribute": spec.protected_attribute,
            "outcome": spec.outcome,
            "causal_graph_id": spec.causal_graph_id,
            "allowed_paths": spec.allowed_paths,
            "forbidden_paths": spec.forbidden_paths,
            "estimator": "declared_path_specific_effects",
            "effects": effects,
            "required": self.config.causal_spec_required,
            "blocking": threshold.blocking,
            "diagnostics": diagnostics,
        }


class FairnessAuditEstimatorFamily:
    """Estimator family orchestrating group, parity, and causal fairness audits."""

    estimators: tuple[type[object], ...] = (
        GroupMetricBreakdownEstimator,
        ParityGapTestEstimator,
        CounterfactualFairnessEstimator,
        PathSpecificFairnessEstimator,
    )

    def __init__(self, config: FairnessAuditConfig | Mapping[str, object] | None = None) -> None:
        self.config = _coerce_config(config)

    def run(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None = None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        causal_spec: CausalFairnessSpec | Mapping[str, object] | None = None,
        sample_weight: ArrayInput | None = None,
        decision_threshold: float | dict[str, float] | None = None,
    ) -> FairnessAuditResult:
        return FairnessAuditRunner(self.config).run(
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            protected=protected,
            features=features,
            causal_spec=causal_spec,
            sample_weight=sample_weight,
            decision_threshold=decision_threshold,
        )


class FairnessAuditRunner:
    """Build a full ``ValidationReport.fairness_audit`` payload."""

    def __init__(self, config: FairnessAuditConfig | Mapping[str, object] | None = None) -> None:
        self.config = _coerce_config(config)

    def run(
        self,
        *,
        y_true: ArrayInput | None,
        y_pred: ArrayInput,
        y_score: ArrayInput | None = None,
        protected: pd.DataFrame,
        features: pd.DataFrame | None = None,
        causal_spec: CausalFairnessSpec | Mapping[str, object] | None = None,
        sample_weight: ArrayInput | None = None,
        decision_threshold: float | dict[str, float] | None = None,
    ) -> FairnessAuditResult:
        config = self.config
        audit_id = config.audit_id or _audit_id()
        if not config.enabled:
            report = FairnessAuditReport(
                status="NOT_APPLICABLE",
                deployable=True,
                auto_decision_allowed=True,
                audit_id=audit_id,
                model_id=config.model_id,
                dataset_id=config.dataset_id,
                config=config.model_dump(mode="json"),
                refusal_policy=_refusal_policy_payload("NOT_APPLICABLE", [], []),
            )
            return FairnessAuditResult(report)

        causal = _coerce_causal_spec(causal_spec)
        group_estimator = GroupMetricBreakdownEstimator().fit(
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            protected=protected,
            features=features,
            sample_weight=sample_weight,
            causal_spec=causal,
            config=config,
        )
        group_result = group_estimator.estimate()
        audit_input = _coerce_audit_input(
            y_true=y_true,
            y_pred=y_pred,
            y_score=y_score,
            protected=protected,
            features=features,
            sample_weight=sample_weight,
            decision_threshold=decision_threshold,
            task_type=config.task_type,
        )
        parity_result = ParityGapTestEstimator().fit(
            y_true=audit_input.y_true,
            y_pred=audit_input.y_pred,
            y_score=audit_input.y_score,
            protected=audit_input.protected,
            features=audit_input.features,
            sample_weight=audit_input.sample_weight,
            causal_spec=causal,
            config=config,
            group_result=group_result,
        ).test()
        counterfactual = CounterfactualFairnessEstimator().fit(
            y_true=audit_input.y_true,
            y_pred=audit_input.y_pred,
            y_score=audit_input.y_score,
            protected=audit_input.protected,
            features=audit_input.features,
            sample_weight=audit_input.sample_weight,
            causal_spec=causal,
            config=config,
        ).test()
        path_specific = PathSpecificFairnessEstimator().fit(
            y_true=audit_input.y_true,
            y_pred=audit_input.y_pred,
            y_score=audit_input.y_score,
            protected=audit_input.protected,
            features=audit_input.features,
            sample_weight=audit_input.sample_weight,
            causal_spec=causal,
            config=config,
        ).test()
        causal_audits = {
            "counterfactual_fairness": counterfactual,
            "path_specific_fairness": path_specific,
        }
        diagnostics = _as_list_of_dicts(group_result.get("diagnostics"))
        diagnostics.extend(_causal_setup_diagnostics(causal, config))
        checks = _blocking_checks(
            parity_tests=_as_list_of_dicts(parity_result.get("parity_tests")),
            causal_audits=causal_audits,
            diagnostics=diagnostics,
            config=config,
        )
        status, reason_codes, blocking_ids = fairness_refusal_decision(checks, config)
        deployable = status == "PASS" or (status == "WARN" and not config.require_pass_to_deploy)
        auto_decision_allowed = status == "PASS" or (
            status == "WARN" and not config.require_pass_to_deploy
        )
        report = FairnessAuditReport(
            status=status,
            deployable=deployable,
            auto_decision_allowed=auto_decision_allowed,
            audit_id=audit_id,
            model_id=config.model_id,
            dataset_id=config.dataset_id,
            config=config.model_dump(mode="json"),
            input_summary=dict(group_result.get("input_summary", {})),
            group_metrics=_as_list_of_dicts(group_result.get("group_metrics")),
            parity_tests=_as_list_of_dicts(parity_result.get("parity_tests")),
            causal_audits=causal_audits,
            diagnostics=diagnostics,
            refusal_policy=_refusal_policy_payload(status, reason_codes, blocking_ids),
            required_actions=_required_actions(status),
            limitations=_limitations(causal, config),
        )
        return FairnessAuditResult(report)


def fairness_refusal_decision(
    checks: Sequence[Mapping[str, object]],
    config: FairnessAuditConfig,
) -> tuple[Literal["PASS", "WARN", "REFUSE"], list[str], list[str]]:
    """Apply the deterministic deployment/refusal policy over blocking checks."""

    warn = False
    refuse = False
    reason_codes: list[str] = []
    blocking_ids: list[str] = []
    for check in checks:
        if not bool(check.get("blocking", False)):
            continue
        status = str(check.get("status", "PASS"))
        required = bool(check.get("required", True))
        check_id = str(check.get("test_id") or check.get("check_id") or check.get("code"))
        if status == "NOT_COMPUTABLE" and required:
            reason_codes.append("REQUIRED_FAIRNESS_CHECK_NOT_COMPUTABLE")
            blocking_ids.append(check_id)
            refuse = True
            continue
        if status == "INSUFFICIENT_N" and config.high_impact:
            reason_codes.append("FAIRNESS_AUDIT_UNDERPOWERED")
            blocking_ids.append(check_id)
            refuse = True
            continue
        if status == "FAIL":
            reason_codes.append(str(check.get("reason_code", "PARITY_GAP_EXCEEDS_THRESHOLD")))
            blocking_ids.append(check_id)
            refuse = True
            continue
        if _numeric_check_refuses(check, config):
            reason_codes.append(str(check.get("reason_code", "PARITY_GAP_EXCEEDS_THRESHOLD")))
            blocking_ids.append(check_id)
            refuse = True
            continue
        if _numeric_check_warns(check, config):
            warn = True
            reason_codes.append(str(check.get("reason_code", "FAIRNESS_AUDIT_WARN")))
            blocking_ids.append(check_id)
            continue
        if status in {"WARN", "INSUFFICIENT_N"}:
            warn = True
            reason_codes.append(str(check.get("reason_code", "FAIRNESS_AUDIT_WARN")))
            blocking_ids.append(check_id)
    if refuse:
        return "REFUSE", list(dict.fromkeys(reason_codes)), list(dict.fromkeys(blocking_ids))
    if warn:
        return "WARN", list(dict.fromkeys(reason_codes)), list(dict.fromkeys(blocking_ids))
    return "PASS", [], []


def fairness_gate_response(
    latest_validation_report: Mapping[str, object] | FairnessAuditReport,
    *,
    report_id: str | None = None,
) -> dict[str, object] | None:
    """Return a runtime refusal response when the latest audit blocks automation."""

    audit = _extract_fairness_audit(latest_validation_report)
    if audit is None:
        return None
    status = str(audit.get("status", ""))
    auto_allowed = bool(audit.get("auto_decision_allowed", True))
    if status != "REFUSE" and auto_allowed:
        return None
    refusal_policy = audit.get("refusal_policy")
    runtime_behavior = (
        refusal_policy.get("runtime_behavior", {})
        if isinstance(refusal_policy, Mapping)
        else {}
    )
    fallback = str(
        runtime_behavior.get("fallback", "human_review_or_approved_fallback_policy")
    )
    return {
        "decision": None,
        "status": "refused",
        "code": str(runtime_behavior.get("message_code", "FAIRNESS_AUDIT_BLOCK")),
        "message": _DEFAULT_BLOCK_MESSAGE,
        "fallback": fallback,
        "report_id": report_id or str(audit.get("audit_id", "")),
    }


def predict_with_fairness_gate(
    model: object,
    request: object,
    latest_validation_report: Mapping[str, object] | FairnessAuditReport,
) -> object:
    """Run ``model.predict`` unless the latest fairness audit blocks automation."""

    blocked = fairness_gate_response(latest_validation_report)
    if blocked is not None:
        return blocked
    features = getattr(request, "features", None)
    if features is None and isinstance(request, Mapping):
        features = request.get("features")
    predict = model.predict
    if not callable(predict):
        raise TypeError("model must expose a callable predict method")
    return predict(features)


def _coerce_config(config: FairnessAuditConfig | Mapping[str, object] | None) -> FairnessAuditConfig:
    if config is None:
        return FairnessAuditConfig()
    if isinstance(config, FairnessAuditConfig):
        return config
    return FairnessAuditConfig.model_validate(config)


def _coerce_causal_spec(
    causal_spec: CausalFairnessSpec | Mapping[str, object] | None,
) -> CausalFairnessSpec | None:
    if causal_spec is None:
        return None
    if isinstance(causal_spec, CausalFairnessSpec):
        return causal_spec
    return CausalFairnessSpec.model_validate(causal_spec)


def _coerce_audit_input(
    *,
    y_true: ArrayInput | None,
    y_pred: ArrayInput,
    y_score: ArrayInput | None,
    protected: pd.DataFrame,
    features: pd.DataFrame | None = None,
    sample_weight: ArrayInput | None = None,
    decision_threshold: float | dict[str, float] | None = None,
    task_type: TaskType,
) -> FairnessAuditInput:
    if not isinstance(protected, pd.DataFrame):
        protected = pd.DataFrame(protected)
    n = len(protected)
    if len(_object_array(y_pred)) != n:
        raise ValueError("y_pred length must match protected rows")
    if y_true is not None and len(_object_array(y_true)) != n:
        raise ValueError("y_true length must match protected rows")
    if y_score is not None and len(_score_array(y_score)) != n:
        raise ValueError("y_score length must match protected rows")
    if sample_weight is not None and len(_object_array(sample_weight)) != n:
        raise ValueError("sample_weight length must match protected rows")
    if features is not None and len(features) != n:
        raise ValueError("features length must match protected rows")
    return FairnessAuditInput(
        y_true=y_true,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
        features=features,
        sample_weight=sample_weight,
        decision_threshold=decision_threshold,
        task_type=task_type,
    )


def _object_array(values: ArrayInput) -> np.ndarray:
    if isinstance(values, pd.Series):
        return values.to_numpy()
    return np.asarray(values)


def _score_array(values: ArrayInput | None) -> np.ndarray | None:
    if values is None:
        return None
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 2:
        if arr.shape[1] < 2:
            return arr[:, 0]
        return arr[:, 1]
    return arr.ravel()


def _binary_array(values: ArrayInput | None, positive_label: object) -> np.ndarray:
    if values is None:
        return np.asarray([], dtype=bool)
    arr = _object_array(values)
    return arr == positive_label


def _weight_array(sample_weight: ArrayInput | None, n: int) -> np.ndarray:
    if sample_weight is None:
        return np.ones(n, dtype=float)
    weights = np.asarray(sample_weight, dtype=float).ravel()
    if len(weights) != n:
        raise ValueError("sample_weight length must match protected rows")
    return weights


def _attribute_configs(
    config: FairnessAuditConfig,
    protected: pd.DataFrame,
) -> list[ProtectedAttributeConfig]:
    if config.protected_attributes:
        return config.protected_attributes
    return [ProtectedAttributeConfig(name=str(column)) for column in protected.columns]


def _build_attribute_frames(
    protected: pd.DataFrame,
    attribute_configs: Sequence[ProtectedAttributeConfig],
    config: FairnessAuditConfig,
) -> tuple[dict[str, np.ndarray], list[dict[str, object]]]:
    frames: dict[str, np.ndarray] = {}
    diagnostics: list[dict[str, object]] = []
    declared_names = [attr.name for attr in attribute_configs]
    for attr in attribute_configs:
        if attr.name not in protected.columns:
            diagnostics.append(
                {
                    "code": "PROTECTED_ATTRIBUTE_MISSING",
                    "attribute": attr.name,
                    "status": "NOT_COMPUTABLE",
                    "blocking": attr.required,
                    "required": attr.required,
                }
            )
            continue
        series = protected[attr.name]
        non_missing = series[~series.isna()].astype(str)
        frames[attr.name] = non_missing.reindex(protected.index, fill_value=np.nan).to_numpy()

    if config.intersectional.enabled and len(declared_names) > 1:
        max_order = min(config.intersectional.max_order, len(declared_names))
        for order in range(2, max_order + 1):
            for names in combinations(declared_names, order):
                if any(name not in protected.columns for name in names):
                    continue
                key = " x ".join(names)
                values = []
                subset = protected.loc[:, list(names)]
                for _, row in subset.iterrows():
                    if row.isna().any():
                        values.append(np.nan)
                    else:
                        values.append("|".join(f"{name}={row[name]}" for name in names))
                frames[key] = np.asarray(values, dtype=object)
    return frames, diagnostics


def _protected_missingness(
    protected: pd.DataFrame,
    attribute_configs: Sequence[ProtectedAttributeConfig],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for attr in attribute_configs:
        if attr.name in protected.columns:
            out[attr.name] = float(protected[attr.name].isna().mean())
        else:
            out[attr.name] = 1.0
    return out


def _missingness_diagnostics(
    missingness: Mapping[str, float],
    config: FairnessAuditConfig,
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for attr, rate in missingness.items():
        status = "FAIL" if rate > config.missing_protected_attribute_max_rate else "PASS"
        diagnostics.append(
            {
                "code": "MISSING_PROTECTED_ATTRIBUTE_RATE",
                "attribute": attr,
                "value": float(rate),
                "threshold": config.missing_protected_attribute_max_rate,
                "status": status,
                "blocking": True,
                "required": True,
            }
        )
    return diagnostics


def _min_group_n_for_attribute(attr_name: str, config: FairnessAuditConfig) -> int:
    if " x " in attr_name:
        return config.intersectional.min_group_n
    return config.min_group_n


def _declared_value_diagnostics(
    protected: pd.DataFrame,
    attribute_configs: Sequence[ProtectedAttributeConfig],
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    for attr in attribute_configs:
        if not attr.values or attr.name not in protected.columns:
            continue
        allowed = {str(value) for value in attr.values}
        observed = {
            str(value)
            for value in protected[attr.name].dropna().unique().tolist()
            if str(value) not in allowed
        }
        if observed:
            diagnostics.append(
                {
                    "code": "PROTECTED_ATTRIBUTE_UNDECLARED_VALUES",
                    "attribute": attr.name,
                    "values": sorted(observed),
                    "status": "WARN",
                    "blocking": False,
                    "required": attr.required,
                }
            )
    return diagnostics


def _missingness_by_group_diagnostics(
    protected: pd.DataFrame,
    attribute_configs: Sequence[ProtectedAttributeConfig],
) -> list[dict[str, object]]:
    diagnostics: list[dict[str, object]] = []
    names = [attr.name for attr in attribute_configs if attr.name in protected.columns]
    for group_attr in names:
        group_values = protected[group_attr]
        for group_value in group_values.dropna().astype(str).unique().tolist():
            mask = group_values.astype(str) == group_value
            rates = {
                attr: float(protected.loc[mask, attr].isna().mean())
                for attr in names
                if attr in protected.columns
            }
            diagnostics.append(
                {
                    "code": "MISSINGNESS_BY_GROUP",
                    "attribute": group_attr,
                    "group": group_value,
                    "missingness": rates,
                    "status": "PASS",
                    "blocking": False,
                    "required": True,
                }
            )
    return diagnostics


def _config_for_attribute(
    attr_name: str,
    configs: Sequence[ProtectedAttributeConfig],
) -> ProtectedAttributeConfig | None:
    for config in configs:
        if config.name == attr_name:
            return config
    return None


def _reference_group(values: np.ndarray, config: ProtectedAttributeConfig | None) -> str | None:
    if config is not None and config.reference == "configured" and config.reference_value is not None:
        return str(config.reference_value)
    if (
        config is not None
        and config.reference_value is not None
        and str(config.reference_value) != "largest_group"
    ):
        return str(config.reference_value)
    unique, counts = np.unique(values[~pd.isna(values)], return_counts=True)
    if len(unique) == 0:
        return None
    return str(unique[int(np.argmax(counts))])


def _stable_unique(values: np.ndarray) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if pd.isna(value):
            continue
        seen.setdefault(str(value), None)
    return list(seen)


def _effective_n(weights: np.ndarray) -> float:
    if weights.size == 0:
        return 0.0
    denom = float(np.sum(weights**2))
    if denom <= 0.0:
        return 0.0
    return float(np.sum(weights) ** 2 / denom)


def _binary_group_metrics(
    *,
    mask: np.ndarray,
    y_pred_bin: np.ndarray,
    y_true_bin: np.ndarray | None,
    y_score: np.ndarray | None,
    weights: np.ndarray,
    alpha: float,
    task_type: TaskType,
) -> dict[str, object]:
    metrics: dict[str, object] = {
        "selection_rate": _rate_metric(mask, y_pred_bin, weights, alpha),
    }
    if y_true_bin is None:
        for metric in (
            "base_rate",
            "true_positive_rate",
            "false_positive_rate",
            "false_negative_rate",
            "true_negative_rate",
            "positive_predictive_value",
            "negative_predictive_value",
            "accuracy",
            "calibration_error_by_group",
        ):
            metrics[metric] = _not_computable_metric("y_true is required")
    else:
        y_positive = y_true_bin
        y_negative = ~y_true_bin
        pred_positive = y_pred_bin
        pred_negative = ~y_pred_bin
        metrics.update(
            {
                "base_rate": _rate_metric(mask, y_positive, weights, alpha),
                "true_positive_rate": _conditional_rate_metric(
                    mask, pred_positive & y_positive, y_positive, weights, alpha
                ),
                "false_positive_rate": _conditional_rate_metric(
                    mask, pred_positive & y_negative, y_negative, weights, alpha
                ),
                "false_negative_rate": _conditional_rate_metric(
                    mask, pred_negative & y_positive, y_positive, weights, alpha
                ),
                "true_negative_rate": _conditional_rate_metric(
                    mask, pred_negative & y_negative, y_negative, weights, alpha
                ),
                "positive_predictive_value": _conditional_rate_metric(
                    mask, pred_positive & y_positive, pred_positive, weights, alpha
                ),
                "negative_predictive_value": _conditional_rate_metric(
                    mask, pred_negative & y_negative, pred_negative, weights, alpha
                ),
                "accuracy": _rate_metric(mask, pred_positive == y_positive, weights, alpha),
            }
        )
        metrics["calibration_error_by_group"] = _calibration_metric(
            mask=mask,
            y_true_bin=y_true_bin,
            y_score=y_score,
            weights=weights,
            alpha=alpha,
        )
    if y_score is not None:
        metrics.update(_score_metrics(mask, y_score, y_true_bin, weights, alpha, task_type))
    return metrics


def _rate_metric(
    group_mask: np.ndarray,
    event_mask: np.ndarray,
    weights: np.ndarray,
    alpha: float,
) -> dict[str, object]:
    return _conditional_rate_metric(group_mask, event_mask, np.ones_like(event_mask, dtype=bool), weights, alpha)


def _conditional_rate_metric(
    group_mask: np.ndarray,
    event_mask: np.ndarray,
    denom_mask: np.ndarray,
    weights: np.ndarray,
    alpha: float,
) -> dict[str, object]:
    valid = group_mask & denom_mask
    count_denominator = int(valid.sum())
    if count_denominator == 0:
        return _not_computable_metric("denominator is zero")
    numerator_mask = valid & event_mask
    numerator = float(np.sum(weights[numerator_mask]))
    denominator = float(np.sum(weights[valid]))
    estimate = numerator / denominator if denominator > 0.0 else math.nan
    count_numerator = int(numerator_mask.sum())
    ci_low, ci_high = _wilson_ci(count_numerator, count_denominator, alpha)
    return {
        "estimate": float(estimate),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "numerator": numerator,
        "denominator": denominator,
        "count_numerator": count_numerator,
        "count_denominator": count_denominator,
        "status": "PASS",
    }


def _not_computable_metric(reason: str) -> dict[str, object]:
    return {
        "estimate": None,
        "ci_low": None,
        "ci_high": None,
        "status": "NOT_COMPUTABLE",
        "reason": reason,
    }


def _calibration_metric(
    *,
    mask: np.ndarray,
    y_true_bin: np.ndarray,
    y_score: np.ndarray | None,
    weights: np.ndarray,
    alpha: float,
) -> dict[str, object]:
    if y_score is None:
        return _not_computable_metric("y_score is required")
    values = y_score[mask] - y_true_bin[mask].astype(float)
    if values.size == 0:
        return _not_computable_metric("group is empty")
    group_weights = weights[mask]
    mean_residual = _weighted_mean(values, group_weights)
    estimate = abs(mean_residual)
    se = _weighted_standard_error(values, group_weights)
    z = _z_value(alpha)
    return {
        "estimate": float(estimate),
        "ci_low": float(max(0.0, estimate - z * se)),
        "ci_high": float(estimate + z * se),
        "mean_residual": float(mean_residual),
        "standard_error": float(se),
        "count_denominator": int(values.size),
        "status": "PASS",
    }


def _score_metrics(
    mask: np.ndarray,
    y_score: np.ndarray,
    y_true_bin: np.ndarray | None,
    weights: np.ndarray,
    alpha: float,
    task_type: TaskType,
) -> dict[str, object]:
    del alpha
    scores = y_score[mask]
    if scores.size == 0:
        return {}
    group_weights = weights[mask]
    metrics: dict[str, object] = {
        "mean_score": {"estimate": _weighted_mean(scores, group_weights), "status": "PASS"},
        "median_score": {"estimate": float(np.median(scores)), "status": "PASS"},
        "quantiles_score": {
            "estimate": {
                "q05": float(np.quantile(scores, 0.05)),
                "q25": float(np.quantile(scores, 0.25)),
                "q50": float(np.quantile(scores, 0.50)),
                "q75": float(np.quantile(scores, 0.75)),
                "q95": float(np.quantile(scores, 0.95)),
            },
            "status": "PASS",
        },
    }
    if task_type == "regression" and y_true_bin is not None:
        residuals = scores - y_true_bin[mask].astype(float)
        metrics["bias"] = {"estimate": _weighted_mean(residuals, group_weights), "status": "PASS"}
        metrics["mae"] = {
            "estimate": _weighted_mean(np.abs(residuals), group_weights),
            "status": "PASS",
        }
        metrics["rmse"] = {
            "estimate": math.sqrt(_weighted_mean(residuals**2, group_weights)),
            "status": "PASS",
        }
    return metrics


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    denominator = float(np.sum(weights))
    if denominator <= 0.0:
        return float(np.mean(values))
    return float(np.sum(values * weights) / denominator)


def _weighted_standard_error(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size <= 1:
        return 0.0
    mean = _weighted_mean(values, weights)
    variance = _weighted_mean((values - mean) ** 2, weights)
    return math.sqrt(max(variance, 0.0) / max(_effective_n(weights), 1.0))


def _wilson_ci(successes: int, total: int, alpha: float) -> tuple[float | None, float | None]:
    if total <= 0:
        return None, None
    z = _z_value(alpha)
    p_hat = successes / total
    denom = 1.0 + z**2 / total
    center = (p_hat + z**2 / (2.0 * total)) / denom
    half = z * math.sqrt((p_hat * (1.0 - p_hat) + z**2 / (4.0 * total)) / total) / denom
    return float(max(0.0, center - half)), float(min(1.0, center + half))


def _z_value(alpha: float) -> float:
    return float(NormalDist().inv_cdf(1.0 - alpha / 2.0))


def _as_list_of_dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _metric_payload(entry: Mapping[str, object], metric: str) -> Mapping[str, object] | None:
    metrics = entry.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    payload = metrics.get(metric)
    return payload if isinstance(payload, Mapping) else None


def _metric_status(entry: Mapping[str, object], metric: str) -> str:
    payload = _metric_payload(entry, metric)
    if payload is None:
        return "NOT_COMPUTABLE"
    return str(payload.get("status", "PASS"))


def _metric_estimate(entry: Mapping[str, object], metric: str) -> float | None:
    payload = _metric_payload(entry, metric)
    if payload is None:
        return None
    estimate = payload.get("estimate")
    if estimate is None:
        return None
    return float(estimate)


def _pairwise_metric_test(
    attr: str,
    entry: Mapping[str, object],
    ref_entry: Mapping[str, object],
    metric: str,
    config: FairnessAuditConfig,
) -> dict[str, object]:
    threshold_config = _threshold_for(metric, config)
    threshold = _max_abs_threshold(metric, threshold_config)
    group = str(entry["group"])
    ref_group = str(ref_entry["group"])
    base = {
        "test_id": f"{attr}.{metric}.{group}_vs_{ref_group}",
        "attribute": attr,
        "metric": metric,
        "group": group,
        "reference_group": ref_group,
        "gap_type": "absolute_difference",
        "threshold": threshold,
        "ratio_threshold": threshold_config.min_ratio,
        "multiple_comparison_correction": config.statistical_tests.multiple_comparison_correction,
        "blocking": threshold_config.blocking,
        "required": True,
    }
    if _metric_status(entry, metric) != "PASS" or _metric_status(ref_entry, metric) != "PASS":
        return {
            **base,
            "estimate": None,
            "abs_estimate": None,
            "ratio": None,
            "ci_low": None,
            "ci_high": None,
            "p_value": None,
            "p_value_adjusted": None,
            "test_name": "not_computable",
            "status": "NOT_COMPUTABLE",
        }
    diff = (_metric_estimate(entry, metric) or 0.0) - (_metric_estimate(ref_entry, metric) or 0.0)
    ratio = _safe_ratio(_metric_estimate(entry, metric), _metric_estimate(ref_entry, metric))
    test = _two_sample_metric_difference(entry, ref_entry, metric, config.statistical_tests.alpha)
    status = "INSUFFICIENT_N" if _insufficient_pair_n(entry, ref_entry, metric, config) else "PASS"
    return {
        **base,
        "estimate": float(diff),
        "abs_estimate": float(abs(diff)),
        "ratio": ratio,
        "ci_low": test.get("ci_low"),
        "ci_high": test.get("ci_high"),
        "p_value": test.get("p_value"),
        "p_value_adjusted": None,
        "test_name": test.get("test_name"),
        "status": status,
    }


def _threshold_for(metric: str, config: FairnessAuditConfig) -> FairnessThreshold:
    aliases = {
        "selection_rate": ("selection_rate", "demographic_parity_gap"),
        "false_negative_rate": ("false_negative_rate", "false_negative_rate_gap"),
        "true_positive_rate": ("true_positive_rate", "equal_opportunity_gap"),
        "equalized_odds_gap": ("equalized_odds_gap", "equalized_odds"),
    }
    for key in aliases.get(metric, (metric,)):
        threshold = config.thresholds.get(key)
        if threshold is not None:
            return threshold
    return FairnessThreshold(max_abs_gap=0.05, blocking=False)


def _max_abs_threshold(metric: str, threshold: FairnessThreshold) -> float | None:
    if threshold.max_abs_gap is not None:
        return threshold.max_abs_gap
    if metric == "counterfactual_flip_rate":
        return threshold.flip_rate_max
    if threshold.max_forbidden_path_effect is not None:
        return threshold.max_forbidden_path_effect
    return None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or abs(denominator) <= _EPS:
        return None
    return float(numerator / denominator)


def _two_sample_metric_difference(
    entry: Mapping[str, object],
    ref_entry: Mapping[str, object],
    metric: str,
    alpha: float,
) -> dict[str, object]:
    payload = _metric_payload(entry, metric)
    ref_payload = _metric_payload(ref_entry, metric)
    if payload is None or ref_payload is None:
        return {"test_name": "not_computable", "p_value": None}
    estimate = float(payload.get("estimate") or 0.0)
    ref_estimate = float(ref_payload.get("estimate") or 0.0)
    diff = estimate - ref_estimate
    if metric in _PROPORTION_METRICS:
        x1 = int(payload.get("count_numerator", 0))
        n1 = int(payload.get("count_denominator", 0))
        x2 = int(ref_payload.get("count_numerator", 0))
        n2 = int(ref_payload.get("count_denominator", 0))
        if n1 <= 0 or n2 <= 0:
            return {"test_name": "not_computable", "p_value": None}
        p_pool = (x1 + x2) / (n1 + n2)
        se = math.sqrt(max(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2), 0.0))
        z_stat = diff / se if se > 0.0 else 0.0
        p_value = 2.0 * (1.0 - NormalDist().cdf(abs(z_stat)))
        ci1 = _wilson_ci(x1, n1, alpha)
        ci2 = _wilson_ci(x2, n2, alpha)
        ci_low = None if ci1[0] is None or ci2[1] is None else ci1[0] - ci2[1]
        ci_high = None if ci1[1] is None or ci2[0] is None else ci1[1] - ci2[0]
        return {
            "test_name": "two_proportion_z_test_newcombe_ci",
            "statistic": float(z_stat),
            "p_value": float(max(0.0, min(1.0, p_value))),
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
    se1 = float(payload.get("standard_error", 0.0) or 0.0)
    se2 = float(ref_payload.get("standard_error", 0.0) or 0.0)
    se = math.sqrt(se1**2 + se2**2)
    z_stat = diff / se if se > 0.0 else 0.0
    p_value = 2.0 * (1.0 - NormalDist().cdf(abs(z_stat))) if se > 0.0 else None
    z = _z_value(alpha)
    return {
        "test_name": "welch_normal_approximation",
        "statistic": float(z_stat),
        "p_value": p_value,
        "ci_low": float(diff - z * se),
        "ci_high": float(diff + z * se),
    }


def _insufficient_pair_n(
    entry: Mapping[str, object],
    ref_entry: Mapping[str, object],
    metric: str,
    config: FairnessAuditConfig,
) -> bool:
    payload = _metric_payload(entry, metric)
    ref_payload = _metric_payload(ref_entry, metric)
    if payload is None or ref_payload is None:
        return False
    n1 = int(payload.get("count_denominator", entry.get("n", 0)) or 0)
    n2 = int(ref_payload.get("count_denominator", ref_entry.get("n", 0)) or 0)
    return n1 < config.min_group_n or n2 < config.min_group_n or min(n1, n2) < 5


def _apply_test_multiplicity(tests: list[dict[str, object]], config: FairnessAuditConfig) -> None:
    indices = [index for index, test in enumerate(tests) if test.get("p_value") is not None]
    raw = [float(tests[index]["p_value"]) for index in indices]
    adjusted = _adjust_pvalues(raw, config.statistical_tests.multiple_comparison_correction)
    for index, p_adj in zip(indices, adjusted, strict=True):
        tests[index]["p_value_adjusted"] = float(p_adj)


def _adjust_pvalues(p_values: Sequence[float], method: str) -> list[float]:
    if not p_values:
        return []
    m = len(p_values)
    if method == "none":
        return [float(min(max(p, 0.0), 1.0)) for p in p_values]
    if method == "bonferroni":
        return [float(min(1.0, p * m)) for p in p_values]
    order = sorted(range(m), key=lambda index: p_values[index])
    adjusted = [1.0] * m
    if method == "fdr_bh":
        running = 1.0
        for rank, index in reversed(list(enumerate(order, start=1))):
            running = min(running, p_values[index] * m / rank)
            adjusted[index] = float(min(1.0, running))
        return adjusted
    running_max = 0.0
    for rank, index in enumerate(order, start=1):
        running_max = max(running_max, (m - rank + 1) * p_values[index])
        adjusted[index] = float(min(1.0, running_max))
    return adjusted


def _finalize_parity_status(test: dict[str, object], config: FairnessAuditConfig) -> None:
    if test.get("status") in {"NOT_COMPUTABLE", "INSUFFICIENT_N"}:
        return
    threshold = test.get("threshold")
    if threshold is None:
        test["status"] = "PASS"
        return
    abs_estimate = float(test.get("abs_estimate") or 0.0)
    p_adj = test.get("p_value_adjusted")
    ratio = test.get("ratio")
    ratio_threshold = test.get("ratio_threshold")
    ci_low = test.get("ci_low")
    ci_high = test.get("ci_high")
    fails_ratio = (
        ratio is not None and ratio_threshold is not None and float(ratio) < float(ratio_threshold)
    )
    statistically_supported = p_adj is not None and float(p_adj) < config.statistical_tests.alpha
    if (abs_estimate > float(threshold) and statistically_supported) or fails_ratio:
        test["status"] = "FAIL"
        return
    if (
        config.require_pass_to_deploy
        and ci_low is not None
        and ci_high is not None
        and max(abs(float(ci_low)), abs(float(ci_high))) > float(threshold)
    ):
        test["status"] = "WARN"
        return
    test["status"] = "PASS"


def _decorate_test_decision(test: dict[str, object], config: FairnessAuditConfig) -> None:
    status = str(test.get("status", "PASS"))
    decision = {
        "PASS": "pass",
        "WARN": "warn",
        "FAIL": "fail",
        "INSUFFICIENT_N": "insufficient_n",
        "NOT_COMPUTABLE": "not_computable",
    }.get(status, status.lower())
    test["alpha"] = config.statistical_tests.alpha
    test["correction"] = config.statistical_tests.multiple_comparison_correction
    test["decision"] = decision


def _numeric_check_refuses(check: Mapping[str, object], config: FairnessAuditConfig) -> bool:
    threshold = check.get("threshold")
    if threshold is None:
        return False
    point = check.get("abs_estimate", check.get("point_estimate", check.get("estimate")))
    p_value_adjusted = check.get("p_value_adjusted")
    ci_low = check.get("ci_low")
    try:
        threshold_float = float(threshold)
    except (TypeError, ValueError):
        return False
    if point is not None and p_value_adjusted is not None:
        if abs(float(point)) > threshold_float and float(p_value_adjusted) < config.statistical_tests.alpha:
            return True
    ci_high = check.get("ci_high")
    if ci_low is None:
        return False
    if ci_high is None:
        return float(ci_low) > threshold_float
    return float(ci_low) > threshold_float or float(ci_high) < -threshold_float


def _numeric_check_warns(check: Mapping[str, object], config: FairnessAuditConfig) -> bool:
    threshold = check.get("threshold")
    ci_high = check.get("ci_high")
    if not config.require_pass_to_deploy or threshold is None or ci_high is None:
        return False
    return abs(float(ci_high)) > float(threshold)


def _bootstrap_aggregate_gap_ci(
    *,
    attr: str,
    component_metrics: tuple[str, ...],
    audit_input: FairnessAuditInput,
    attribute_values: object,
    config: FairnessAuditConfig,
) -> tuple[float | None, float | None]:
    resamples = config.statistical_tests.bootstrap_resamples
    if resamples <= 0 or not isinstance(attribute_values, Mapping) or attr not in attribute_values:
        return None, None
    values = np.asarray(attribute_values[attr], dtype=object)
    n = len(values)
    if n == 0:
        return None, None
    rng = np.random.default_rng(config.statistical_tests.random_seed)
    y_pred_bin = _binary_array(audit_input.y_pred, config.positive_label)
    y_true_bin = (
        _binary_array(audit_input.y_true, config.positive_label)
        if audit_input.y_true is not None
        else None
    )
    gaps: list[float] = []
    for _ in range(resamples):
        idx = rng.integers(0, n, size=n)
        gap = _aggregate_gap_from_indices(
            values=values,
            idx=idx,
            y_pred_bin=y_pred_bin,
            y_true_bin=y_true_bin,
            component_metrics=component_metrics,
        )
        if gap is not None:
            gaps.append(gap)
    if not gaps:
        return None, None
    alpha = config.statistical_tests.alpha
    return (
        float(np.quantile(gaps, alpha / 2.0)),
        float(np.quantile(gaps, 1.0 - alpha / 2.0)),
    )


def _aggregate_gap_from_indices(
    *,
    values: np.ndarray,
    idx: np.ndarray,
    y_pred_bin: np.ndarray,
    y_true_bin: np.ndarray | None,
    component_metrics: tuple[str, ...],
) -> float | None:
    sampled_values = values[idx]
    sampled_pred = y_pred_bin[idx]
    sampled_true = y_true_bin[idx] if y_true_bin is not None else None
    component_gaps: list[float] = []
    for metric in component_metrics:
        estimates: list[float] = []
        for group in _stable_unique(sampled_values):
            mask = sampled_values == group
            estimate = _simple_metric_estimate(metric, mask, sampled_pred, sampled_true)
            if estimate is not None:
                estimates.append(estimate)
        if len(estimates) >= 2:
            component_gaps.append(float(max(estimates) - min(estimates)))
    if not component_gaps:
        return None
    return max(component_gaps)


def _simple_metric_estimate(
    metric: str,
    mask: np.ndarray,
    y_pred_bin: np.ndarray,
    y_true_bin: np.ndarray | None,
) -> float | None:
    if not mask.any():
        return None
    if metric == "selection_rate":
        return float(np.mean(y_pred_bin[mask]))
    if y_true_bin is None:
        return None
    if metric == "true_positive_rate":
        denom = mask & y_true_bin
        return float(np.mean(y_pred_bin[denom])) if denom.any() else None
    if metric == "false_positive_rate":
        denom = mask & ~y_true_bin
        return float(np.mean(y_pred_bin[denom])) if denom.any() else None
    if metric == "false_negative_rate":
        denom = mask & y_true_bin
        return float(np.mean(~y_pred_bin[denom])) if denom.any() else None
    return None


def _first_protected_attribute(config: FairnessAuditConfig, protected: pd.DataFrame) -> str:
    if config.protected_attributes:
        return config.protected_attributes[0].name
    return str(protected.columns[0])


def _counterfactual_pairs_from_keys(
    score_map: Mapping[str, object],
    pred_map: Mapping[str, object],
) -> list[tuple[object, object]]:
    pairs: list[tuple[object, object]] = []
    for key in [*score_map.keys(), *pred_map.keys()]:
        pair = _parse_counterfactual_key(key)
        if pair is not None and pair not in pairs:
            pairs.append(pair)
    return pairs


def _parse_counterfactual_key(key: str) -> tuple[object, object] | None:
    pair_text = key.split(":", 1)[-1]
    if "->" not in pair_text:
        return None
    left, right = pair_text.split("->", 1)
    return left, right


def _counterfactual_key(attr: str, from_value: object, to_value: object) -> str:
    return f"{attr}:{from_value}->{to_value}"


def _lookup_counterfactual_vector(
    vector_map: Mapping[str, list[object] | list[float]],
    key: str,
) -> np.ndarray | None:
    if key in vector_map:
        return np.asarray(vector_map[key])
    short_key = key.split(":", 1)[-1]
    if short_key in vector_map:
        return np.asarray(vector_map[short_key])
    return None


def _protected_pair_mask(protected: pd.DataFrame, attr: str, from_value: object) -> np.ndarray:
    if attr not in protected.columns:
        return np.ones(len(protected), dtype=bool)
    return protected[attr].astype(str).to_numpy() == str(from_value)


def _counterfactual_pair_result(
    *,
    key: str,
    from_value: object,
    to_value: object,
    mask: np.ndarray,
    y_score: ArrayInput | None,
    y_pred: ArrayInput,
    alt_score: np.ndarray | None,
    alt_pred: np.ndarray | None,
    config: FairnessAuditConfig,
) -> dict[str, object]:
    score_deltas = np.asarray([], dtype=float)
    flip_indicators = np.asarray([], dtype=float)
    if alt_score is not None:
        observed_scores = _score_array(y_score)
        if observed_scores is not None:
            alt = _aligned_counterfactual_values(alt_score.astype(float), mask)
            obs = observed_scores[mask]
            if len(alt) == len(obs):
                score_deltas = alt - obs
    if alt_pred is not None:
        obs_pred = _binary_array(y_pred, config.positive_label)[mask]
        alt = _aligned_counterfactual_values(alt_pred, mask)
        if len(alt) == len(obs_pred):
            alt_bin = alt == config.positive_label
            flip_indicators = (alt_bin != obs_pred).astype(float)
    elif score_deltas.size and y_score is not None:
        observed_scores = _score_array(y_score)
        if observed_scores is not None:
            threshold = 0.5
            obs_decision = observed_scores[mask] >= threshold
            alt_decision = observed_scores[mask] + score_deltas >= threshold
            flip_indicators = (alt_decision != obs_decision).astype(float)
    payload = {
        "pair_id": key,
        "from": str(from_value),
        "to": str(to_value),
        "n": int(mask.sum()),
        "mean_abs_delta": float(np.mean(np.abs(score_deltas))) if score_deltas.size else None,
        "flip_rate": float(np.mean(flip_indicators)) if flip_indicators.size else None,
    }
    return {
        "payload": payload,
        "score_deltas": np.abs(score_deltas),
        "flip_indicators": flip_indicators,
    }


def _default_causal_pairs(
    protected: pd.DataFrame,
    attr: str,
    spec: CausalFairnessSpec,
) -> list[tuple[object, object]]:
    if spec.protected_reference_value is not None and spec.protected_target_value is not None:
        return [(spec.protected_reference_value, spec.protected_target_value)]
    if attr not in protected.columns:
        return []
    values = [str(value) for value in protected[attr].dropna().astype(str).unique().tolist()]
    if len(values) < 2:
        return []
    return [(values[0], values[1])]


def _encode_protected_pair(
    values: pd.Series,
    from_value: object,
    to_value: object,
) -> tuple[np.ndarray, np.ndarray] | None:
    string_values = values.astype(str).to_numpy()
    valid_mask = (string_values == str(from_value)) | (string_values == str(to_value))
    if int(valid_mask.sum()) < 6:
        return None
    encoded = np.where(string_values[valid_mask] == str(to_value), 1.0, 0.0)
    if len(np.unique(encoded)) < 2:
        return None
    return encoded, valid_mask


def _numeric_feature_matrix(
    features: pd.DataFrame,
    columns: Sequence[str],
) -> np.ndarray | None:
    selected_columns = [column for column in columns if column in features.columns]
    selected = features.loc[:, selected_columns] if selected_columns else features
    if selected.empty:
        return np.zeros((len(features), 1), dtype=float)
    encoded = pd.get_dummies(selected, dummy_na=True)
    if encoded.empty:
        return np.zeros((len(features), 1), dtype=float)
    encoded = encoded.astype(float)
    filled = encoded.fillna(encoded.mean(numeric_only=True)).fillna(0.0)
    return filled.to_numpy(dtype=float)


def _counterfactual_residual_scm_result(
    *,
    y_pred: ArrayInput,
    y_score: ArrayInput | None,
    protected: pd.DataFrame,
    features: pd.DataFrame,
    spec: CausalFairnessSpec,
    config: FairnessAuditConfig,
) -> dict[str, object] | None:
    attr = spec.protected_attribute or _first_protected_attribute(config, protected)
    pairs = spec.counterfactual_pairs or _default_causal_pairs(protected, attr, spec)
    outcome = _score_array(y_score)
    if outcome is None:
        outcome = _object_array(y_pred).astype(float)
    matrix = _numeric_feature_matrix(features, spec.covariate_columns)
    if matrix is None or not pairs or attr not in protected.columns:
        return None

    pair_payloads: list[dict[str, object]] = []
    score_deltas: list[np.ndarray] = []
    flip_indicators: list[np.ndarray] = []
    for from_value, to_value in pairs:
        encoded = _encode_protected_pair(protected[attr], from_value, to_value)
        if encoded is None:
            continue
        a_values, valid_mask = encoded
        y_valid = outcome[valid_mask]
        x_valid = matrix[valid_mask]
        design = np.column_stack([np.ones(len(y_valid)), a_values, x_valid])
        try:
            coef = np.linalg.lstsq(design, y_valid, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        beta_a = float(coef[1])
        from_mask = (protected[attr].astype(str).to_numpy() == str(from_value)) & valid_mask
        observed_scores = outcome[from_mask]
        if observed_scores.size == 0:
            continue
        delta = np.full(observed_scores.size, beta_a, dtype=float)
        score_deltas.append(np.abs(delta))
        threshold = 0.5
        observed_decisions = observed_scores >= threshold
        counterfactual_decisions = (observed_scores + delta) >= threshold
        flips = (counterfactual_decisions != observed_decisions).astype(float)
        flip_indicators.append(flips)
        pair_payloads.append(
            {
                "pair_id": _counterfactual_key(attr, from_value, to_value),
                "from": str(from_value),
                "to": str(to_value),
                "n": int(from_mask.sum()),
                "mean_abs_delta": float(np.mean(np.abs(delta))),
                "flip_rate": float(np.mean(flips)),
            }
        )

    if not score_deltas and not flip_indicators:
        return None
    threshold = _threshold_for("counterfactual_fairness", config)
    all_score_deltas = np.concatenate(score_deltas) if score_deltas else np.asarray([])
    all_flips = np.concatenate(flip_indicators) if flip_indicators else np.asarray([])
    scores = _counterfactual_scores_payload(
        score_deltas=all_score_deltas,
        flip_indicators=all_flips,
        threshold=threshold,
        config=config,
    )
    status = _worst_status([str(payload.get("status", "PASS")) for payload in scores.values()])
    return {
        "enabled": True,
        "status": status,
        "definition": "counterfactual_prediction_invariance",
        "protected_attribute": attr,
        "estimator": "residual_scm_linear_bootstrap",
        "counterfactual_pairs": [[str(left), str(right)] for left, right in pairs],
        "pair_results": pair_payloads,
        "scores": scores,
        "required": config.causal_spec_required,
        "blocking": threshold.blocking,
        "assumptions": spec.assumptions
        or [
            "linear residual structural equation for prediction outcome",
            "protected attribute encoded as binary intervention for each pair",
            "observed numeric covariates are sufficient for the residual SCM approximation",
        ],
        "diagnostics": {
            "scm_fit_quality": "linear_residual_approximation",
            "bootstrap_resamples": config.statistical_tests.bootstrap_resamples,
            **spec.diagnostics,
        },
    }


def _aligned_counterfactual_values(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if len(values) == len(mask):
        return values[mask]
    if len(values) == int(mask.sum()):
        return values
    return np.asarray([])


def _counterfactual_scores_payload(
    *,
    score_deltas: np.ndarray,
    flip_indicators: np.ndarray,
    threshold: FairnessThreshold,
    config: FairnessAuditConfig,
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    if score_deltas.size:
        out["mean_abs_score_delta"] = _threshold_metric_payload(
            values=score_deltas,
            estimate=float(np.mean(score_deltas)),
            threshold=threshold.mean_abs_score_delta_max,
            config=config,
        )
        out["p95_abs_score_delta"] = _threshold_metric_payload(
            values=score_deltas,
            estimate=float(np.quantile(score_deltas, 0.95)),
            threshold=threshold.p95_abs_score_delta_max,
            config=config,
            statistic=lambda sample: np.quantile(sample, 0.95),
        )
        out["max_abs_score_delta"] = {
            "estimate": float(np.max(score_deltas)),
            "threshold": threshold.p95_abs_score_delta_max,
            "status": "PASS",
        }
    else:
        out["mean_abs_score_delta"] = {
            "estimate": None,
            "threshold": threshold.mean_abs_score_delta_max,
            "status": "NOT_COMPUTABLE",
        }
    if flip_indicators.size:
        out["flip_rate"] = _threshold_metric_payload(
            values=flip_indicators,
            estimate=float(np.mean(flip_indicators)),
            threshold=threshold.flip_rate_max,
            config=config,
        )
    else:
        out["flip_rate"] = {
            "estimate": None,
            "threshold": threshold.flip_rate_max,
            "status": "NOT_COMPUTABLE",
        }
    return out


def _threshold_metric_payload(
    *,
    values: np.ndarray,
    estimate: float,
    threshold: float | None,
    config: FairnessAuditConfig,
    statistic: Callable[[np.ndarray], np.floating] = np.mean,
) -> dict[str, object]:
    ci_low, ci_high = _bootstrap_stat_ci(values, statistic, config)
    status = _threshold_status(estimate, ci_low, ci_high, threshold)
    return {
        "estimate": estimate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "threshold": threshold,
        "status": status,
    }


def _bootstrap_stat_ci(
    values: np.ndarray,
    stat: Callable[[np.ndarray], np.floating],
    config: FairnessAuditConfig,
) -> tuple[float | None, float | None]:
    resamples = config.statistical_tests.bootstrap_resamples
    if values.size == 0 or resamples <= 0:
        return None, None
    rng = np.random.default_rng(config.statistical_tests.random_seed)
    draws = []
    for _ in range(resamples):
        idx = rng.integers(0, values.size, size=values.size)
        draws.append(float(stat(values[idx])))
    alpha = config.statistical_tests.alpha
    return float(np.quantile(draws, alpha / 2.0)), float(np.quantile(draws, 1.0 - alpha / 2.0))


def _threshold_status(
    estimate: float,
    ci_low: float | None,
    ci_high: float | None,
    threshold: float | None,
) -> CheckStatus:
    if threshold is None:
        return "PASS"
    if ci_high is not None and ci_high <= threshold:
        return "PASS"
    if ci_low is not None and ci_low > threshold:
        return "FAIL"
    if estimate > threshold:
        return "FAIL"
    return "WARN"


def _path_effect_payloads(
    spec: CausalFairnessSpec,
    threshold: FairnessThreshold,
    config: FairnessAuditConfig,
) -> list[dict[str, object]]:
    effects: list[dict[str, object]] = []
    if spec.path_effects:
        raw_effects = spec.path_effects
    else:
        raw_effects = [
            {"path": path, "estimate": None, "status": "NOT_COMPUTABLE"}
            for path in spec.forbidden_paths
        ]
    for raw in raw_effects:
        path_value = raw.get("path", [])
        path = [str(item) for item in path_value] if isinstance(path_value, list) else [str(path_value)]
        estimate_raw = raw.get("estimate")
        threshold_value = raw.get("threshold")
        if threshold_value is None:
            threshold_value = (
                threshold.max_direct_effect
                if len(path) == 2 and threshold.max_direct_effect is not None
                else threshold.max_forbidden_path_effect
            )
        if estimate_raw is None:
            status = "NOT_COMPUTABLE"
            estimate = None
        else:
            estimate = float(estimate_raw)
            ci_low = _maybe_float(raw.get("ci_low"))
            ci_high = _maybe_float(raw.get("ci_high"))
            status = _path_status(
                estimate=estimate,
                ci_low=ci_low,
                ci_high=ci_high,
                threshold=threshold_value,
                p_value_adjusted=_maybe_float(raw.get("p_value_adjusted")),
                alpha=config.statistical_tests.alpha,
            )
        effects.append(
            {
                "path": path,
                "effect_type": str(raw.get("effect_type", "path_specific_effect")),
                "estimate": estimate,
                "ci_low": _maybe_float(raw.get("ci_low")),
                "ci_high": _maybe_float(raw.get("ci_high")),
                "threshold": threshold_value,
                "p_value": _maybe_float(raw.get("p_value")),
                "p_value_adjusted": _maybe_float(raw.get("p_value_adjusted")),
                "status": status,
                "blocking": bool(raw.get("blocking", threshold.blocking)),
                "required": True,
            }
        )
    return effects


def _path_specific_catalog_result(
    *,
    y_pred: ArrayInput,
    y_score: ArrayInput | None,
    protected: pd.DataFrame,
    features: pd.DataFrame,
    spec: CausalFairnessSpec,
    threshold: FairnessThreshold,
    config: FairnessAuditConfig,
) -> dict[str, object] | None:
    attr = spec.protected_attribute or _first_protected_attribute(config, protected)
    if attr not in protected.columns:
        return None
    pairs = spec.counterfactual_pairs or _default_causal_pairs(protected, attr, spec)
    if not pairs:
        return None
    from_value, to_value = pairs[0]
    encoded = _encode_protected_pair(protected[attr], from_value, to_value)
    if encoded is None:
        return None
    a_values, valid_mask = encoded
    outcome = _score_array(y_score)
    if outcome is None:
        outcome = _object_array(y_pred).astype(float)
    mediator_column_set = set(spec.mediator_columns)
    covariate_columns = (
        [column for column in spec.covariate_columns if column not in mediator_column_set]
        if spec.covariate_columns
        else [column for column in features.columns if column not in mediator_column_set]
    )
    x_matrix = _numeric_feature_matrix(features, covariate_columns)
    if x_matrix is None:
        return None
    mediator_matrix = (
        _numeric_feature_matrix(features, spec.mediator_columns)
        if spec.mediator_columns
        else None
    )
    try:
        from polisyos.foundry.methods.catalog.causal.fairness import (
            PathSpecificFairnessEstimator as CatalogPathSpecificFairnessEstimator,
        )

        state: dict[str, object] = {
            "outcome": outcome[valid_mask],
            "protected": a_values,
            "covariates": x_matrix[valid_mask],
            "graph_dot": spec.graph_dot,
        }
        if mediator_matrix is not None:
            state["mediators"] = mediator_matrix[valid_mask]
        report = CatalogPathSpecificFairnessEstimator.pure_step(
            state,
            {
                "graph_dot": spec.graph_dot or "",
                "protected_node": attr,
                "outcome_node": spec.outcome,
                "legitimate_mediators": spec.allowed_mediators,
                "mediator_node_names": spec.mediator_columns,
                "effect_threshold": threshold.max_forbidden_path_effect or 0.02,
                "__seed__": config.statistical_tests.random_seed,
            },
        ).get("fairness_report", {})
    except (ImportError, ValueError, TypeError, np.linalg.LinAlgError):
        return None
    if not isinstance(report, Mapping):
        return None
    metadata = report.get("metadata", {})
    if not isinstance(metadata, Mapping):
        return None
    path_effects = metadata.get("path_effects", {})
    path_fairness = report.get("path_specific_fairness", {})
    if not isinstance(path_effects, Mapping):
        return None
    raw_effects: list[dict[str, object]] = []
    for path_label, effect in path_effects.items():
        fair = bool(path_fairness.get(path_label, True)) if isinstance(path_fairness, Mapping) else True
        raw_effects.append(
            {
                "path": _split_path_label(str(path_label)),
                "estimate": float(effect),
                "status": "PASS" if fair else "FAIL",
                "effect_type": "path_specific_effect",
                "blocking": not fair,
            }
        )
    effects = _path_effect_payloads(
        spec.model_copy(update={"path_effects": raw_effects}),
        threshold,
        config,
    )
    diagnostics = {
        "estimator_source": "causal_catalog_path_specific",
        "nuisance_models": ["outcome_model", "propensity_model", "mediator_model"],
        **_causal_overlap_diagnostics(spec, config),
        **spec.diagnostics,
        **{key: value for key, value in metadata.items() if key != "path_effects"},
    }
    status = _worst_status(
        [str(effect.get("status", "PASS")) for effect in effects]
        + [str(diagnostics.get("overlap_status", "PASS"))]
    )
    return {
        "enabled": True,
        "status": status,
        "definition": "forbidden_path_specific_effect",
        "protected_attribute": attr,
        "outcome": spec.outcome,
        "causal_graph_id": spec.causal_graph_id,
        "allowed_paths": spec.allowed_paths,
        "forbidden_paths": spec.forbidden_paths,
        "estimator": "aipw_crossfit_catalog",
        "effects": effects,
        "required": config.causal_spec_required,
        "blocking": threshold.blocking,
        "diagnostics": diagnostics,
    }


def _split_path_label(path_label: str) -> list[str]:
    if "→" in path_label:
        return [part.strip() for part in path_label.split("→")]
    if "->" in path_label:
        return [part.strip() for part in path_label.split("->")]
    return [path_label]


def _path_status(
    *,
    estimate: float,
    ci_low: float | None,
    ci_high: float | None,
    threshold: object,
    p_value_adjusted: float | None,
    alpha: float,
) -> CheckStatus:
    if threshold is None:
        return "PASS"
    threshold_float = float(threshold)
    abs_estimate = abs(estimate)
    abs_ci_high = max(abs(ci_low or 0.0), abs(ci_high or 0.0)) if ci_high is not None else None
    abs_ci_low = min(abs(ci_low or 0.0), abs(ci_high or 0.0)) if ci_low is not None and ci_high is not None else None
    if abs_ci_high is not None and abs_ci_high <= threshold_float:
        return "PASS"
    if abs_ci_low is not None and abs_ci_low > threshold_float:
        return "FAIL"
    if abs_estimate > threshold_float and (p_value_adjusted is None or p_value_adjusted < alpha):
        return "FAIL"
    if abs_estimate > threshold_float:
        return "WARN"
    return "WARN" if abs_ci_high is not None and abs_ci_high > threshold_float else "PASS"


def _maybe_float(value: object) -> float | None:
    return None if value is None else float(value)


def _worst_status(statuses: Sequence[str]) -> str:
    order = {
        "FAIL": 4,
        "NOT_COMPUTABLE": 3,
        "INSUFFICIENT_N": 3,
        "WARN": 2,
        "PASS": 1,
        "NOT_APPLICABLE": 0,
    }
    if not statuses:
        return "PASS"
    return max(statuses, key=lambda status: order.get(status, 0))


def _blocking_checks(
    *,
    parity_tests: Sequence[Mapping[str, object]],
    causal_audits: Mapping[str, object],
    diagnostics: Sequence[Mapping[str, object]],
    config: FairnessAuditConfig,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for test in parity_tests:
        checks.append(dict(test))
    for diagnostic in diagnostics:
        if diagnostic.get("code") in {
            "MISSING_PROTECTED_ATTRIBUTE_RATE",
            "PROTECTED_ATTRIBUTE_MISSING",
            "MIN_GROUP_N",
            "MIN_EFFECTIVE_N",
            "CAUSAL_SPEC_REQUIRED",
        }:
            checks.append(dict(diagnostic))
    for name, audit_obj in causal_audits.items():
        if not isinstance(audit_obj, Mapping):
            continue
        audit = dict(audit_obj)
        checks.append(
            {
                "check_id": name,
                "status": audit.get("status", "PASS"),
                "blocking": audit.get("blocking", True),
                "required": audit.get("required", config.causal_spec_required),
                "reason_code": _causal_reason_code(name),
            }
        )
        diagnostics_obj = audit.get("diagnostics")
        if isinstance(diagnostics_obj, Mapping) and diagnostics_obj.get("overlap_status") == "FAIL":
            checks.append(
                {
                    "check_id": f"{name}.positivity",
                    "status": "FAIL",
                    "blocking": audit.get("blocking", True),
                    "required": audit.get("required", config.causal_spec_required),
                    "reason_code": "CAUSAL_OVERLAP_DIAGNOSTIC_FAILED",
                }
            )
        scores = audit.get("scores")
        if isinstance(scores, Mapping):
            for score_name, score_obj in scores.items():
                if isinstance(score_obj, Mapping):
                    checks.append(
                        {
                            "check_id": f"{name}.{score_name}",
                            "status": score_obj.get("status", "PASS"),
                            "blocking": audit.get("blocking", True),
                            "required": audit.get("required", config.causal_spec_required),
                            "reason_code": _causal_reason_code(name),
                        }
                    )
        effects = audit.get("effects")
        if isinstance(effects, list):
            for index, effect in enumerate(effects):
                if isinstance(effect, Mapping):
                    checks.append(
                        {
                            "check_id": f"{name}.effect_{index}",
                            "status": effect.get("status", "PASS"),
                            "blocking": effect.get("blocking", audit.get("blocking", True)),
                            "required": effect.get("required", audit.get("required", True)),
                            "reason_code": _causal_reason_code(name),
                        }
                    )
    return checks


def _causal_reason_code(name: str) -> str:
    if name == "path_specific_fairness":
        return "FORBIDDEN_PATH_EFFECT_EXCEEDS_THRESHOLD"
    if name == "counterfactual_fairness":
        return "COUNTERFACTUAL_FAIRNESS_EXCEEDS_THRESHOLD"
    return "CAUSAL_FAIRNESS_CHECK_EXCEEDS_THRESHOLD"


def _causal_setup_diagnostics(
    causal_spec: CausalFairnessSpec | None,
    config: FairnessAuditConfig,
) -> list[dict[str, object]]:
    if causal_spec is None:
        return [
            {
                "code": "CAUSAL_SPEC_REQUIRED",
                "message": "Causal fairness scores require a declared causal specification.",
                "status": "NOT_COMPUTABLE" if config.causal_spec_required else "NOT_APPLICABLE",
                "blocking": config.causal_spec_required,
                "required": config.causal_spec_required,
            }
        ]
    return [
        {
            "code": "CAUSAL_SPEC_REQUIRED",
            "message": "Causal fairness specification supplied.",
            "status": "PASS",
            "blocking": False,
            "required": config.causal_spec_required,
        }
    ]


def _causal_overlap_diagnostics(
    spec: CausalFairnessSpec,
    config: FairnessAuditConfig,
) -> dict[str, object]:
    positivity_min = _maybe_float(spec.diagnostics.get("positivity_min"))
    positivity_max = _maybe_float(spec.diagnostics.get("positivity_max"))
    propensities = spec.diagnostics.get("propensity_scores")
    if isinstance(propensities, Sequence) and not isinstance(propensities, str):
        propensity_arr = np.asarray(propensities, dtype=float)
        if propensity_arr.size:
            positivity_min = float(np.min(propensity_arr))
            positivity_max = float(np.max(propensity_arr))
    overlap_status = "PASS"
    if positivity_min is not None and positivity_min < config.positivity_min_propensity:
        overlap_status = "FAIL"
    if positivity_max is not None and positivity_max > config.positivity_max_propensity:
        overlap_status = "FAIL"
    return {
        "positivity_min": positivity_min,
        "positivity_max": positivity_max,
        "positivity_min_threshold": config.positivity_min_propensity,
        "positivity_max_threshold": config.positivity_max_propensity,
        "overlap_status": overlap_status,
    }


def _refusal_policy_payload(
    status: str,
    reason_codes: Sequence[str],
    blocking_ids: Sequence[str],
) -> dict[str, object]:
    return {
        "status": status,
        "auto_decision_allowed": status == "PASS",
        "reason_codes": list(reason_codes),
        "blocking_checks": list(blocking_ids),
        "runtime_behavior": {
            "mode": "block_automated_decision",
            "fallback": "human_review_or_approved_fallback_policy",
            "message_code": "FAIRNESS_AUDIT_BLOCK",
        },
        "clearance_requirements": [
            "mitigate model or decision threshold",
            "rerun fairness audit on validation split",
            "obtain PASS or governance override",
            "log override with accountable owner and expiry",
        ],
    }


def _required_actions(status: str) -> list[str]:
    if status == "REFUSE":
        return [
            "block automated decisions for this model/task",
            "route decisions to human review or approved fallback policy",
            "rerun fairness audit after mitigation",
        ]
    if status == "WARN":
        return ["obtain governance approval before automated deployment"]
    return []


def _limitations(
    causal_spec: CausalFairnessSpec | None,
    config: FairnessAuditConfig,
) -> list[str]:
    limitations = [
        "Group fairness metrics are descriptive and can conflict across criteria.",
        "Absence of statistically significant disparity is not evidence of fairness when underpowered.",
    ]
    if causal_spec is None and config.causal_spec_required:
        limitations.append(
            "Causal fairness cannot be computed without a declared causal graph, SCM, or path effects."
        )
    return limitations


def _extract_fairness_audit(
    latest_validation_report: Mapping[str, object] | FairnessAuditReport,
) -> dict[str, object] | None:
    if isinstance(latest_validation_report, FairnessAuditReport):
        return latest_validation_report.to_validation_report_payload()
    if "fairness_audit" in latest_validation_report:
        audit = latest_validation_report.get("fairness_audit")
        return dict(audit) if isinstance(audit, Mapping) else None
    if "status" in latest_validation_report and "auto_decision_allowed" in latest_validation_report:
        return dict(latest_validation_report)
    return None


def _audit_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"fairness_audit_{stamp}"


__all__ = [
    "CausalFairnessSpec",
    "CounterfactualFairnessEstimator",
    "FairnessAuditConfig",
    "FairnessAuditEstimator",
    "FairnessAuditEstimatorFamily",
    "FairnessAuditInput",
    "FairnessAuditResult",
    "FairnessAuditRunner",
    "FairnessThreshold",
    "GroupMetricBreakdownEstimator",
    "IntersectionalConfig",
    "ParityGapTestEstimator",
    "PathSpecificFairnessEstimator",
    "ProtectedAttributeConfig",
    "StatisticalTestsConfig",
    "fairness_gate_response",
    "fairness_refusal_decision",
    "predict_with_fairness_gate",
]
