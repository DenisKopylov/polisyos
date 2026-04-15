"""Public causal meta learners module API."""
from __future__ import annotations

import inspect
from typing import Any, Callable, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal._common import (
    build_failure_report,
    build_success_report,
    wrap_causal_output,
)
from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    build_cate_quantile_subgroups,
    build_hte_data,
    extract_cate_from_estimator,
    require_econml,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus
from polisyos.ir.analytics.hte import FeatureImportance, HTEResult, SubgroupEffect


def _supports_fit_inference_kwarg(model: Any) -> bool:
    try:
        return "inference" in inspect.signature(model.fit).parameters
    except (TypeError, ValueError, AttributeError):
        return False


def _build_bootstrap_inference(params: Mapping[str, Any]) -> Any | None:
    n_samples = int(params.get("bootstrap_inference_samples", 0) or 0)
    if n_samples < 2:
        return None
    try:
        from econml.inference import BootstrapInference
    except Exception:
        return None
    return BootstrapInference(
        n_bootstrap_samples=n_samples,
        n_jobs=max(1, int(params.get("bootstrap_inference_n_jobs", 1))),
        bootstrap_type=str(params.get("bootstrap_inference_type", "pivot")),
        verbose=0,
    )


def _feature_importances_from_array(
    values: np.ndarray,
    feature_names: list[str],
    *,
    method: str,
    minimum_total: float = 1e-10,
) -> list[dict[str, Any]]:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return []
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    total = float(np.sum(np.abs(arr)))
    if total <= minimum_total:
        return []
    order = np.argsort(-np.abs(arr))
    payload: list[dict[str, Any]] = []
    for rank, idx in enumerate(order, start=1):
        name = feature_names[int(idx)] if int(idx) < len(feature_names) else f"x{int(idx)}"
        payload.append(
            {
                "feature_name": name,
                "importance_score": float(abs(arr[int(idx)])),
                "importance_rank": rank,
                "method": method,
                "metadata": {},
            }
        )
    return payload


def _permutation_feature_importances(
    estimator: Any,
    X: np.ndarray,
    *,
    seed: int,
    feature_names: list[str],
    repeats: int = 5,
    max_rows: int = 256,
) -> list[dict[str, Any]]:
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] == 0 or X.shape[0] == 0:
        return []
    rng = np.random.default_rng(seed)
    if X.shape[0] > max_rows:
        subset = np.sort(rng.choice(X.shape[0], size=max_rows, replace=False))
        X_eval = X[subset]
    else:
        X_eval = X
    try:
        baseline = np.asarray(estimator.effect(X_eval), dtype=float).reshape(-1)
    except Exception:
        return []
    if baseline.shape[0] != X_eval.shape[0] or not np.isfinite(baseline).all():
        return []

    scores = np.zeros(X_eval.shape[1], dtype=float)
    n_repeats = max(1, int(repeats))
    for column_idx in range(X_eval.shape[1]):
        deltas: list[float] = []
        for _ in range(n_repeats):
            permuted = np.array(X_eval, copy=True)
            permuted[:, column_idx] = permuted[rng.permutation(permuted.shape[0]), column_idx]
            try:
                perm_pred = np.asarray(estimator.effect(permuted), dtype=float).reshape(-1)
            except Exception:
                continue
            if perm_pred.shape[0] != baseline.shape[0] or not np.isfinite(perm_pred).all():
                continue
            deltas.append(float(np.mean((perm_pred - baseline) ** 2)))
        if deltas:
            scores[column_idx] = max(0.0, float(np.mean(deltas)))

    if float(np.sum(scores)) <= 1e-12:
        return []
    return _feature_importances_from_array(scores, feature_names, method="permutation")


def _suppress_importances_if_homogeneous(
    cate_values: np.ndarray,
    importances: list[dict[str, Any]],
    *,
    threshold: float = 1e-8,
) -> list[dict[str, Any]]:
    cate_arr = np.asarray(cate_values, dtype=float).ravel()
    if cate_arr.size == 0 or float(np.nanstd(cate_arr)) <= threshold:
        return []
    total = float(np.sum([float(item.get("importance_score", 0.0)) for item in importances]))
    if total <= threshold:
        return []
    return importances


def _make_base_model(name: str, seed: int):
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import ElasticNet, LassoCV

    key = name.lower()
    if key == "random_forest":
        return RandomForestRegressor(n_estimators=200, random_state=seed)
    if key == "linear":
        return LassoCV(cv=3, random_state=seed)
    if key in {"elastic_net_sparse", "elastic_net"}:
        return ElasticNet(alpha=0.01, l1_ratio=0.9, max_iter=3000, random_state=seed)
    return GradientBoostingRegressor(n_estimators=200, random_state=seed)


def _selection_propensity(
    X_train: np.ndarray,
    t_train: np.ndarray,
    X_eval: np.ndarray,
) -> np.ndarray:
    try:
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=500, solver="lbfgs")
        model.fit(X_train, t_train)
        return np.clip(np.asarray(model.predict_proba(X_eval)[:, 1], dtype=float), 0.025, 0.975)
    except Exception:
        mean_prop = float(np.clip(np.mean(t_train), 0.025, 0.975))
        return np.full(X_eval.shape[0], mean_prop, dtype=float)


def _selection_outcome_main(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
) -> np.ndarray:
    try:
        from sklearn.linear_model import Ridge

        model = Ridge(alpha=1.0)
        model.fit(X_train, y_train)
        return np.asarray(model.predict(X_eval), dtype=float)
    except Exception:
        mean_outcome = float(np.mean(y_train))
        return np.full(X_eval.shape[0], mean_outcome, dtype=float)


def _selection_r_risk(
    y_eval: np.ndarray,
    t_eval: np.ndarray,
    outcome_main: np.ndarray,
    propensity: np.ndarray,
    cate_pred: np.ndarray,
) -> float:
    residual = np.asarray(y_eval, dtype=float) - np.asarray(outcome_main, dtype=float)
    treatment_residual = np.asarray(t_eval, dtype=float) - np.asarray(propensity, dtype=float)
    cate = np.asarray(cate_pred, dtype=float)
    if not (
        residual.size
        and residual.size == treatment_residual.size == cate.size
        and np.isfinite(residual).all()
        and np.isfinite(treatment_residual).all()
        and np.isfinite(cate).all()
    ):
        return float("inf")
    return float(np.mean(np.square(residual - cate * treatment_residual) * np.square(treatment_residual)))


def _selection_overlap_penalty(
    propensity: np.ndarray,
    treatment: np.ndarray,
    *,
    clip: float = 0.05,
    ess_floor: float = 48.0,
) -> float:
    prop = np.clip(np.asarray(propensity, dtype=float).reshape(-1), 1e-6, 1.0 - 1e-6)
    treat = np.asarray(treatment, dtype=float).reshape(-1)
    if prop.size == 0 or prop.size != treat.size:
        return 1.0
    support_mismatch = float(np.mean((prop <= clip) | (prop >= 1.0 - clip)))
    weights = np.where(treat > 0.5, 1.0 / prop, 1.0 / (1.0 - prop))
    denom = float(np.sum(np.square(weights)))
    ess = float(np.square(np.sum(weights)) / denom) if denom > 1e-12 else 0.0
    ess_penalty = max(0.0, (ess_floor - ess) / max(ess_floor, 1.0))
    return support_mismatch + ess_penalty


def _selection_dr_ate_overlap_score(
    y_eval: np.ndarray,
    t_eval: np.ndarray,
    outcome_main: np.ndarray,
    propensity: np.ndarray,
    cate_pred: np.ndarray,
) -> float:
    prop = np.clip(np.asarray(propensity, dtype=float).reshape(-1), 0.025, 0.975)
    treatment = np.asarray(t_eval, dtype=float).reshape(-1)
    outcome = np.asarray(y_eval, dtype=float).reshape(-1)
    mu = np.asarray(outcome_main, dtype=float).reshape(-1)
    cate = np.asarray(cate_pred, dtype=float).reshape(-1)
    if not (
        outcome.size
        and outcome.size == treatment.size == mu.size == prop.size == cate.size
        and np.isfinite(outcome).all()
        and np.isfinite(mu).all()
        and np.isfinite(prop).all()
        and np.isfinite(cate).all()
    ):
        return float("inf")
    dr_signal = mu + treatment * (outcome - mu) / prop - (1.0 - treatment) * (outcome - mu) / (1.0 - prop)
    target_ate = float(np.mean(dr_signal))
    ate_gap = abs(float(np.mean(cate)) - target_ate)
    rrisk = _selection_r_risk(outcome, treatment, mu, prop, cate)
    overlap_penalty = _selection_overlap_penalty(prop, treatment)
    return ate_gap + 0.25 * rrisk + overlap_penalty


def _selection_complexity_penalty(candidate_name: str) -> float:
    key = str(candidate_name).strip().lower()
    if key == "linear":
        return 0.0
    if key in {"elastic_net_sparse", "elastic_net"}:
        return 0.01
    if key == "gradient_boosting":
        return 0.03
    if key == "random_forest":
        return 0.06
    return 0.02


def _holdout_split(treatment: np.ndarray, *, seed: int) -> tuple[np.ndarray, np.ndarray]:
    treatment = np.asarray(treatment, dtype=float).reshape(-1)
    rng = np.random.default_rng(seed)
    indices = np.arange(treatment.size)
    treated = indices[treatment > 0.5]
    control = indices[treatment <= 0.5]
    rng.shuffle(treated)
    rng.shuffle(control)
    treated_eval = treated[: max(1, int(round(0.2 * treated.size)))] if treated.size else np.array([], dtype=int)
    control_eval = control[: max(1, int(round(0.2 * control.size)))] if control.size else np.array([], dtype=int)
    eval_idx = np.sort(np.concatenate([treated_eval, control_eval]))
    if eval_idx.size >= treatment.size:
        eval_idx = np.sort(indices[: max(1, treatment.size // 5)])
    train_idx = np.setdiff1d(indices, eval_idx, assume_unique=False)
    if train_idx.size < 8 or eval_idx.size < 4:
        midpoint = max(1, treatment.size // 5)
        eval_idx = np.sort(indices[:midpoint])
        train_idx = np.sort(indices[midpoint:])
    return train_idx, eval_idx


def _select_base_model_name(
    data: Any,
    *,
    learner_type: str,
    primary_name: str,
    candidate_names: list[str],
    seed: int,
    alpha: float,
    selection_objective: str = "r_risk",
) -> tuple[str, dict[str, float]]:
    normalized_candidates = []
    for name in [primary_name, *candidate_names]:
        candidate = str(name).strip().lower()
        if candidate and candidate != "auto" and candidate not in normalized_candidates:
            normalized_candidates.append(candidate)
    if not normalized_candidates:
        normalized_candidates = ["random_forest"]
    if len(normalized_candidates) == 1 or data.x.shape[0] < 32:
        return normalized_candidates[0], {}

    train_idx, eval_idx = _holdout_split(data.t, seed=seed + 17)
    X_train = np.asarray(data.x[train_idx], dtype=float)
    X_eval = np.asarray(data.x[eval_idx], dtype=float)
    y_train = np.asarray(data.y[train_idx], dtype=float)
    y_eval = np.asarray(data.y[eval_idx], dtype=float)
    t_train = np.asarray(data.t[train_idx], dtype=float)
    t_eval = np.asarray(data.t[eval_idx], dtype=float)
    propensity_eval = _selection_propensity(X_train, t_train, X_eval)
    outcome_eval = _selection_outcome_main(X_train, y_train, X_eval)
    objective = str(selection_objective or "r_risk").strip().lower()

    scores: dict[str, float] = {}
    best_name = normalized_candidates[0]
    best_score = float("inf")
    for offset, candidate_name in enumerate(normalized_candidates):
        try:
            base_model = _make_base_model(candidate_name, seed + 101 * (offset + 1))
            candidate_model, _method_enum, _estimator_fqn = _build_learner(
                learner_type,
                base_model,
                seed=seed + 101 * (offset + 1),
            )
            candidate_model.fit(y_train, t_train, X=X_train)
            extracted = extract_cate_from_estimator(
                candidate_model,
                X_eval,
                alpha=alpha,
                feature_names=list(data.feature_names),
                feature_importance_method="model_based",
                rng=np.random.default_rng(seed + 1009 + offset),
            )
            cate_eval = np.asarray(extracted["cate_values"], dtype=float).reshape(-1)
            score = _selection_r_risk(y_eval, t_eval, outcome_eval, propensity_eval, cate_eval)
            if objective in {"dr_ate_overlap", "dr_ate_overlap_guarded"}:
                score = _selection_dr_ate_overlap_score(
                    y_eval,
                    t_eval,
                    outcome_eval,
                    propensity_eval,
                    cate_eval,
                )
                score = score + _selection_complexity_penalty(candidate_name)
            elif objective in {"r_risk_overlap_guarded", "r_risk_sparse_guarded"}:
                score = score + _selection_overlap_penalty(propensity_eval, t_eval)
                if objective == "r_risk_sparse_guarded":
                    score = score + _selection_complexity_penalty(candidate_name)
                else:
                    score = score + 0.5 * _selection_complexity_penalty(candidate_name)
        except Exception:
            score = float("inf")
        scores[candidate_name] = score
        if np.isfinite(score) and score < best_score - 1e-12:
            best_name = candidate_name
            best_score = score
    return best_name, scores


def _build_learner(
    learner_type: str,
    base_model: Any,
    *,
    seed: int,
) -> tuple[Any, CausalMethod, str]:
    from econml.metalearners import SLearner, TLearner, XLearner

    kind = learner_type.lower()
    if kind == "s":
        try:
            return (
                SLearner(overall_model=base_model),
                CausalMethod.S_LEARNER,
                "econml.metalearners.SLearner",
            )
        except TypeError:
            return (
                SLearner(model=base_model),
                CausalMethod.S_LEARNER,
                "econml.metalearners.SLearner",
            )
    if kind == "t":
        try:
            return (
                TLearner(models=base_model),
                CausalMethod.T_LEARNER,
                "econml.metalearners.TLearner",
            )
        except TypeError:
            return (
                TLearner(model=base_model),
                CausalMethod.T_LEARNER,
                "econml.metalearners.TLearner",
            )
    if kind == "x":
        try:
            return (
                XLearner(models=base_model),
                CausalMethod.X_LEARNER,
                "econml.metalearners.XLearner",
            )
        except TypeError:
            return (
                XLearner(model=base_model),
                CausalMethod.X_LEARNER,
                "econml.metalearners.XLearner",
            )
    if kind == "forestdr":
        try:
            from econml.dr import ForestDRLearner
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ValueError(f"ForestDRLearner unavailable: {exc}") from exc
        try:
            learner = ForestDRLearner(
                model_regression=base_model,
                model_propensity=base_model,
                random_state=seed,
            )
        except TypeError:
            try:
                learner = ForestDRLearner(
                    model_regression=base_model,
                    model_propensity=base_model,
                )
            except TypeError:
                learner = ForestDRLearner()
        return (
            learner,
            CausalMethod.DOUBLE_ML,
            "econml.dr.ForestDRLearner",
        )
    raise ValueError(f"Unknown learner_type={learner_type!r}; expected one of: s, t, x, forestdr")


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "meta-learner"},
)
class MetaLearnerEstimator:
    """Meta-learners (S/T/X) for CATE estimation via EconML."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="meta_learner",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="hte_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="causal_effect_report",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
                SlotSpec(
                    name="hte_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="learner_type", default="x"),
            ParameterSpec(name="base_model", default="auto"),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="subgroup_quantiles", default=4),
            ParameterSpec(name="feature_importance_method", default="permutation"),
            ParameterSpec(name="random_state", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Meta-learner family (S/T/X) for heterogeneous treatment effects.",
        tags=frozenset({"causal", "hte", "meta-learner"}),
        citations=(
            "Künzel, S.R., et al. (2019). Metalearners for estimating heterogeneous "
            "treatment effects using machine learning.",
        ),
        equations={
            "s_learner": "tau(x) = mu(x, 1) - mu(x, 0)",
            "t_learner": "tau(x) = mu_1(x) - mu_0(x)",
            "x_learner": "tau(x) = g(x) * tau_1(x) + (1 - g(x)) * tau_0(x)",
        },
        assumptions={
            "unconfoundedness": "No unobserved confounders conditional on observed variables.",
            "overlap": "Positive probability of treatment/control across covariate support.",
        },
        when_to_use="Heterogeneous treatment effects via ML metalearners (S/T/X/R)",
        typical_min_obs=100,
        output_interpretation="CATE: Conditional Average Treatment Effect for each unit. Mean CATE ≈ ATE.",
    )

    @staticmethod
    def pure_step(state: HTEObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        try:
            require_econml()
        except Exception as exc:
            report = build_failure_report(
                method=CausalMethod.X_LEARNER,
                status=EstimationStatus.NUMERICAL_FAILURE,
                reason=f"Meta-learner backend unavailable: {exc}",
                estimand="ATE_from_CATE",
                sample_size=0,
                n_treated=0,
                n_control=0,
                pre_periods=0,
                post_periods=0,
                assumptions=dict(MetaLearnerEstimator.metadata.assumptions),
            )
            return wrap_causal_output(
                report,
                warnings=[report.status_reason or "backend unavailable"],
            )

        data = build_hte_data(state)
        alpha = 1.0 - float(params.get("confidence_level", 0.95))
        seed = params.get("random_state")
        if seed is None:
            seed = params.get("__seed__", 0)
        seed_int = int(seed)
        rng = np.random.default_rng(seed_int)

        learner_type = str(params.get("learner_type", "x")).lower()
        base_model_name = str(params.get("base_model", "auto"))
        selected_base_model, selection_scores = _select_base_model_name(
            data,
            learner_type=learner_type,
            primary_name=base_model_name,
            candidate_names=[str(value) for value in params.get("base_model_candidates", []) or []],
            seed=seed_int,
            alpha=alpha,
            selection_objective=str(params.get("selection_objective", "r_risk")),
        )
        base_model = _make_base_model(selected_base_model, seed_int)
        model, method_enum, estimator_fqn = _build_learner(learner_type, base_model, seed=seed_int)
        fit_kwargs: dict[str, Any] = {"X": data.x}
        bootstrap_inference = _build_bootstrap_inference(params)
        if bootstrap_inference is not None and _supports_fit_inference_kwarg(model):
            fit_kwargs["inference"] = bootstrap_inference
        try:
            model.fit(data.y, data.t, **fit_kwargs)
        except TypeError:
            model.fit(data.y, data.t, X=data.x)

        extracted = extract_cate_from_estimator(
            model,
            data.x,
            alpha=alpha,
            feature_names=data.feature_names,
            feature_importance_method=str(params.get("feature_importance_method", "permutation")),
            rng=rng,
        )
        feature_importance_method = str(params.get("feature_importance_method", "permutation")).strip().lower()
        feature_importances = extracted["feature_importances"]
        if feature_importance_method == "permutation":
            feature_importances = _permutation_feature_importances(
                model,
                data.x,
                seed=seed_int + 211,
                feature_names=list(data.feature_names),
                repeats=max(3, int(params.get("feature_importance_repeats", 5))),
                max_rows=max(64, int(params.get("feature_importance_rows", 256))),
            )
        feature_importances = _suppress_importances_if_homogeneous(
            np.asarray(extracted["cate_values"], dtype=float),
            list(feature_importances),
        )
        subgroup_payloads = build_cate_quantile_subgroups(
            cate_values=extracted["cate_values"],
            n_quantiles=int(params.get("subgroup_quantiles", 4)),
            alpha=alpha,
        )

        hte_result = HTEResult(
            method=method_enum,
            ate=extracted["ate"],
            ate_ci_lower=extracted["ate_ci_lower"],
            ate_ci_upper=extracted["ate_ci_upper"],
            ate_p_value=extracted["ate_p_value"],
            confidence_level=float(params.get("confidence_level", 0.95)),
            cate_values=extracted["cate_values"],
            cate_std_values=extracted["cate_std_values"],
            cate_ci_lower_values=extracted["cate_ci_lower_values"],
            cate_ci_upper_values=extracted["cate_ci_upper_values"],
            subgroup_effects=[SubgroupEffect.model_validate(item) for item in subgroup_payloads],
            feature_importances=[
                FeatureImportance.model_validate(item) for item in feature_importances
            ],
            n_samples=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            n_features=int(data.x.shape[1]),
            feature_names=list(data.feature_names),
            econml_estimator_class=estimator_fqn,
            econml_params={
                "learner_type": learner_type,
                "base_model": selected_base_model,
                "base_model_candidates": [str(value) for value in params.get("base_model_candidates", []) or []],
            },
            feature_display_map={name: name for name in data.feature_names},
            metadata={
                "warnings": list(extracted["warnings"]),
                "feature_importance_method": feature_importance_method,
                "heterogeneity_signal": float(np.std(extracted["cate_values"], ddof=1)) if len(extracted["cate_values"]) > 1 else 0.0,
                "selection_objective": str(params.get("selection_objective", "r_risk")),
                "split_policy": str(params.get("split_policy", "holdout_r_risk")),
                "selected_outcome_backend": selected_base_model,
                "tested_outcome_backends": [
                    str(value)
                    for value in (
                        params.get("base_model_candidates")
                        or [selected_base_model]
                    )
                ],
                "candidate_r_risk": selection_scores,
            },
        )

        report = build_success_report(
            method=method_enum,
            estimand="ATE_from_CATE",
            point_estimate=extracted["ate"],
            confidence_interval=(extracted["ate_ci_lower"], extracted["ate_ci_upper"]),
            confidence_level=float(params.get("confidence_level", 0.95)),
            p_value=extracted["ate_p_value"],
            inference_method=f"meta_learner_{learner_type}",
            sample_size=int(data.y.shape[0]),
            n_treated=int(np.sum(data.t == 1)),
            n_control=int(np.sum(data.t == 0)),
            pre_periods=0,
            post_periods=0,
            assumptions=dict(MetaLearnerEstimator.metadata.assumptions),
            method_params={
                "learner_type": learner_type,
                "base_model": selected_base_model,
                "base_model_candidates": [str(value) for value in params.get("base_model_candidates", []) or []],
                "selection_objective": str(params.get("selection_objective", "r_risk")),
                "split_policy": str(params.get("split_policy", "holdout_r_risk")),
                "feature_importance_method": str(
                    params.get("feature_importance_method", "permutation")
                ),
            },
            metadata={
                "hte_result_present": True,
                "n_features": int(data.x.shape[1]),
            },
        )
        return wrap_causal_output(
            report,
            warnings=list(extracted["warnings"]),
            extras={"hte_result": hte_result},
        )


__all__ = ["MetaLearnerEstimator"]
