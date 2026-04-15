"""cross_fit — K-fold cross-fitting orchestrator for semiparametric efficiency.

Implements the cross-fitting procedure required by DML / AIPW to avoid
overfitting bias from nuisance function estimation (Chernozhukov et al. 2018).

Pipeline per fold k::

    1. Train propensity e(·) and outcome models μ₁(·), μ₀(·) on {1..K}∖{k}
    2. Predict out-of-fold e_k, μ1_k, μ0_k on fold k
    3. Compute EIF score: ψᵢ = (μ1ᵢ - μ0ᵢ) + Tᵢ(Yᵢ−μ1ᵢ)/eᵢ − (1−Tᵢ)(Yᵢ−μ0ᵢ)/(1−eᵢ)

ATE = mean(ψ),  SE = std(ψ) / √n.
"""

from __future__ import annotations

from typing import Any, ClassVar, Mapping

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
from polisyos.foundry.methods.catalog.causal.treatment_effects import (
    _logistic_propensity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _outcome_model(X_train: np.ndarray, Y_train: np.ndarray) -> np.ndarray:
    """Fit OLS outcome model; return coefficient vector (including intercept)."""
    n, k = X_train.shape
    X_aug = np.column_stack([np.ones(n), X_train])
    beta, _, _, _ = np.linalg.lstsq(X_aug, Y_train, rcond=None)
    return beta


def _predict_outcomes(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    """Predict outcomes using OLS coefficients (intercept + features)."""
    n = X.shape[0]
    X_aug = np.column_stack([np.ones(n), X])
    return X_aug @ beta


def _const_outcome(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Constant outcome model (fit): returns zero-coefficient vector.

    Used for IPW where no outcome model is needed. Matches the
    (X_train, Y_train) -> beta signature of _outcome_model so it can be
    passed as mu1_fn / mu0_fn to _cross_fit_fold. _predict_outcomes(X, beta)
    then returns a zero vector for any X.
    """
    return np.zeros(X.shape[1] + 1)


def _cross_fit_fold(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    train_mask: np.ndarray,
    eval_mask: np.ndarray,
    min_propensity: float,
    *,
    prop_fn=None,
    mu1_fn=None,
    mu0_fn=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Train nuisance on train_mask, predict on eval_mask.

    Returns:
        e_fold:   propensity scores on eval fold,  shape (n_eval,)
        mu1_fold: E[Y|T=1,X] predictions on eval fold
        mu0_fold: E[Y|T=0,X] predictions on eval fold

    Args:
        prop_fn: Reserved for future pluggable propensity strategies.  Currently
                 the propensity is always estimated via the internal IRLS beta path
                 (_fit_logistic_beta) so this parameter is accepted but not yet
                 dispatched; the beta path is the only implemented strategy.
        mu1_fn:  Outcome model fit function (X_tr, Y_tr) → beta.
                 Defaults to _outcome_model. Pass _const_outcome for IPW.
        mu0_fn:  Outcome model fit function (X_tr, Y_tr) → beta.
                 Defaults to _outcome_model. Pass _const_outcome for IPW.
    """
    if mu1_fn is None:
        mu1_fn = _outcome_model
    if mu0_fn is None:
        mu0_fn = _outcome_model

    X_tr, T_tr, Y_tr = X[train_mask], T[train_mask], Y[train_mask]
    X_ev = X[eval_mask]

    # Propensity model: always use internal IRLS beta-fit path.
    n_tr = X_tr.shape[0]
    X_tr_aug = np.column_stack([np.ones(n_tr), X_tr])
    beta_e = _fit_logistic_beta(X_tr_aug, T_tr)

    n_ev = X_ev.shape[0]
    X_ev_aug = np.column_stack([np.ones(n_ev), X_ev])
    eta_ev = np.clip(X_ev_aug @ beta_e, -20.0, 20.0)
    e_fold_eval = np.clip(1.0 / (1.0 + np.exp(-eta_ev)), min_propensity, 1.0 - min_propensity)

    # Outcome models (separately for treated / control)
    treated_tr = T_tr > 0.5
    control_tr = ~treated_tr

    beta1 = (
        mu1_fn(X_tr[treated_tr], Y_tr[treated_tr])
        if np.sum(treated_tr) > 1
        else np.zeros(X_ev.shape[1] + 1)
    )
    beta0 = (
        mu0_fn(X_tr[control_tr], Y_tr[control_tr])
        if np.sum(control_tr) > 1
        else np.zeros(X_ev.shape[1] + 1)
    )

    mu1_fold = _predict_outcomes(X_ev, beta1)
    mu0_fold = _predict_outcomes(X_ev, beta0)

    return e_fold_eval, mu1_fold, mu0_fold


def _fit_logistic_beta(X_aug: np.ndarray, T: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """Return logistic regression coefficient vector (IRLS), same as _logistic_propensity
    but returns beta instead of predictions."""
    beta = np.zeros(X_aug.shape[1])
    for _ in range(max_iter):
        eta = np.clip(X_aug @ beta, -20, 20)
        p = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(p * (1 - p), 1e-12)
        grad = X_aug.T @ (T - p)
        H = X_aug.T @ (W[:, None] * X_aug)
        try:
            delta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta += delta
        if np.max(np.abs(delta)) < 1e-8:
            break
    return beta


def _aipw_scores(
    Y: np.ndarray,
    T: np.ndarray,
    e: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
) -> np.ndarray:
    """Efficient Influence Function (EIF) scores for AIPW ATE.

    ψᵢ = (μ1ᵢ − μ0ᵢ) + Tᵢ(Yᵢ−μ1ᵢ)/eᵢ − (1−Tᵢ)(Yᵢ−μ0ᵢ)/(1−eᵢ)
    """
    return (mu1 - mu0) + T * (Y - mu1) / e - (1 - T) * (Y - mu0) / (1 - e)


# ---------------------------------------------------------------------------
# Inner-method dispatch table
# ---------------------------------------------------------------------------

# Maps FQN prefix to (propensity_fn, outcome_1_fn, outcome_0_fn).
# All functions must be pure-numpy implementations (no external imports needed).
_INNER_DISPATCH: dict = {
    "causal.treatment_effects.aipw": (_logistic_propensity, _outcome_model, _outcome_model),
    "causal.hte.double_ml":          (_logistic_propensity, _outcome_model, _outcome_model),
    "causal.treatment_effects.tmle": (_logistic_propensity, _outcome_model, _outcome_model),
    "causal.treatment_effects.ipw":  (_logistic_propensity, _const_outcome, _const_outcome),
}
_DEFAULT_DISPATCH = (_logistic_propensity, _outcome_model, _outcome_model)


# ---------------------------------------------------------------------------
# Foundry method
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "cross-fitting", "dml", "semiparametric", "aipw"},
)
class CrossFitOrchestrator:
    """K-fold cross-fitting wrapper for semiparametric efficiency.

    Implements the cross-fitting procedure from Chernozhukov et al. (2018)
    to eliminate first-order bias from nuisance function estimation in AIPW
    and DML estimators.

    Input slots:
        X         — covariate matrix  (n_obs, n_features)
        treatment — binary treatment  (n_obs,)
        outcome   — outcome variable  (n_obs,)

    Output slots:
        result            — ATE point estimate and inference
        influence_function — per-observation EIF scores  (n_obs,)
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cross_fit",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
                SlotSpec("influence_function", SlotType.VECTOR, Unit("eif", "score"), shape=("n_obs",)),
            }
        ),
        parameters=(
            ParameterSpec(name="n_folds", default=5),
            ParameterSpec(name="seed", default=42),
            ParameterSpec(name="min_propensity", default=0.01, bounds=(1e-4, 0.49)),
            ParameterSpec(name="inner_method_fqn", default="causal.treatment_effects.aipw@1.0.0"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "K-fold cross-fitting for AIPW / DML: trains nuisance functions on K−1 folds "
            "and evaluates on the held-out fold, then reports the cross-fit AIPW ATE."
        ),
        tags=frozenset({"causal", "cross-fitting", "dml", "semiparametric", "aipw", "eif"}),
        citations=(
            "Chernozhukov, V. et al. (2018). Double/Debiased Machine Learning for Treatment and Structural Parameters. Econometrics Journal.",
            "Robins, J.M., Rotnitzky, A. & Zhao, L.P. (1994). Estimation of Regression Coefficients. JASA.",
        ),
        equations={
            "eif": "ψᵢ = (μ1ᵢ−μ0ᵢ) + Tᵢ(Yᵢ−μ1ᵢ)/eᵢ − (1−Tᵢ)(Yᵢ−μ0ᵢ)/(1−eᵢ)",
            "ate": "ATE = mean(ψ)",
            "se": "SE = std(ψ) / √n",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Whenever ML / flexible nuisance models are used for propensity and outcome; "
            "DML pipeline; want valid inference despite complex nuisance estimation."
        ),
        when_not_to_use="Very small samples (n < 5 × n_folds); linear nuisance models with known OLS inference.",
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.positivity_check@1.0.0",),
        typical_min_obs=100,
        output_interpretation=(
            "Cross-fit AIPW ATE: asymptotically normal, semiparametrically efficient. "
            "SE based on efficient influence function. influence_function slot provides "
            "per-observation EIF scores for downstream variance estimation."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)

        n_folds = int(params.get("n_folds", 5))
        seed = int(params.get("seed", 42))
        min_propensity = float(params.get("min_propensity", 0.01))

        # Clamp n_folds to [2, n]
        n_folds = max(2, min(n_folds, n))

        # Dispatch based on inner_method_fqn
        inner_fqn = str(params.get("inner_method_fqn", ""))
        fqn_prefix = inner_fqn.split("@")[0] if inner_fqn else ""
        prop_fn, mu1_fn, mu0_fn = _INNER_DISPATCH.get(fqn_prefix, _DEFAULT_DISPATCH)

        # ---------------------------------------------------------------
        # Build K-fold partition (stratified by treatment for balance)
        # ---------------------------------------------------------------
        rng = np.random.default_rng(seed)

        # Stratified K-fold: shuffle treated and control separately
        treated_idx = np.where(T > 0.5)[0]
        control_idx = np.where(T <= 0.5)[0]

        rng.shuffle(treated_idx)
        rng.shuffle(control_idx)

        # Assign fold IDs
        fold_ids = np.empty(n, dtype=int)
        for grp in (treated_idx, control_idx):
            g_n = len(grp)
            for i, idx in enumerate(grp):
                fold_ids[idx] = i % n_folds

        # ---------------------------------------------------------------
        # Cross-fitting: accumulate out-of-fold predictions
        # ---------------------------------------------------------------
        e_oof = np.empty(n)
        mu1_oof = np.empty(n)
        mu0_oof = np.empty(n)

        for k in range(n_folds):
            train_mask = fold_ids != k
            eval_mask = fold_ids == k

            if not np.any(eval_mask):
                continue

            e_k, mu1_k, mu0_k = _cross_fit_fold(
                X, T, Y, train_mask, eval_mask, min_propensity,
                prop_fn=prop_fn, mu1_fn=mu1_fn, mu0_fn=mu0_fn,
            )
            e_oof[eval_mask] = e_k
            mu1_oof[eval_mask] = mu1_k
            mu0_oof[eval_mask] = mu0_k

        # ---------------------------------------------------------------
        # AIPW EIF scores and ATE inference
        # ---------------------------------------------------------------
        psi = _aipw_scores(Y, T, e_oof, mu1_oof, mu0_oof)

        ate = float(np.mean(psi))
        se = float(np.std(psi, ddof=1) / np.sqrt(n))
        t_stat = ate / max(se, 1e-12)

        # Diagnostic: effective sample sizes
        w1 = T / np.clip(e_oof, min_propensity, 1.0 - min_propensity)
        w0 = (1 - T) / np.clip(1 - e_oof, min_propensity, 1.0 - min_propensity)
        ess_treated = float(np.sum(w1) ** 2 / max(np.sum(w1 ** 2), 1e-12))
        ess_control = float(np.sum(w0) ** 2 / max(np.sum(w0 ** 2), 1e-12))

        return {
            "result": {
                "ate": ate,
                "standard_error": se,
                "t_statistic": t_stat,
                "ci_lower": ate - 1.96 * se,
                "ci_upper": ate + 1.96 * se,
                "n_folds": n_folds,
                "n_obs": n,
                "n_treated": int(np.sum(T > 0.5)),
                "n_control": int(np.sum(T <= 0.5)),
                "effective_sample_size_treated": ess_treated,
                "effective_sample_size_control": ess_control,
                "propensity_range": [float(np.min(e_oof)), float(np.max(e_oof))],
                "inner_method_fqn": inner_fqn,
            },
            "influence_function": psi.tolist(),
        }


# ---------------------------------------------------------------------------
# Phase 6 — CrossFitContinuousOrchestrator
# ---------------------------------------------------------------------------


def _fit_and_predict_gps(
    X_tr: np.ndarray,
    T_tr: np.ndarray,
    X_val: np.ndarray,
    T_val: np.ndarray,
) -> np.ndarray:
    """Fit GPS on training fold and predict f(T_val | X_val)."""
    X_aug_tr = np.column_stack([np.ones(len(X_tr)), X_tr])
    beta, *_ = np.linalg.lstsq(X_aug_tr, T_tr, rcond=None)
    T_hat_tr = X_aug_tr @ beta
    sigma = max(float(np.std(T_tr - T_hat_tr, ddof=1)), 1e-8)

    X_aug_val = np.column_stack([np.ones(len(X_val)), X_val])
    T_hat_val = X_aug_val @ beta

    z = (T_val - T_hat_val) / sigma
    log_d = -0.5 * z * z - np.log(sigma) - 0.5 * np.log(2.0 * np.pi)
    return np.exp(log_d)


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags=frozenset({"causal", "cross-fitting", "continuous-treatment", "gps"}),
)
class CrossFitContinuousOrchestrator:
    """K-fold cross-fitting for continuous treatment estimators.

    Produces out-of-fold nuisance estimates used by downstream estimators
    such as ``KernelDoseResponseEstimator`` and ``ShiftInterventionEstimator``:

    - ``gps_oof``     : f(Tᵢ|Xᵢ) evaluated at observed treatment.
    - ``outcome_oof`` : μ(Tᵢ, Xᵢ) from a linear outcome model [1, T, X]β.
    - ``fold_assignments`` : fold index per observation (for downstream split).

    Registered as ``causal.treatment_effects.cross_fit_continuous@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cross_fit_continuous",
        namespace="",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     unit=Unit("covariates", "matrix"), shape=("n_obs", "n_features")),
            SlotSpec(name="treatment", slot_type=SlotType.VECTOR,
                     unit=Unit("treatment", "continuous"), shape=("n_obs",)),
            SlotSpec(name="outcome", slot_type=SlotType.VECTOR,
                     unit=Unit("outcome", "observed"), shape=("n_obs",)),
        ]),
        output_slots=frozenset([
            SlotSpec(name="gps_oof", slot_type=SlotType.VECTOR,
                     unit=Unit("gps", "density"), shape=("n_obs",)),
            SlotSpec(name="outcome_oof", slot_type=SlotType.VECTOR,
                     unit=Unit("outcome", "predicted"), shape=("n_obs",)),
            SlotSpec(name="fold_assignments", slot_type=SlotType.VECTOR,
                     unit=Unit("fold", "index"), shape=("n_obs",)),
        ]),
        parameters=(
            ParameterSpec(name="n_folds", default=5,
                          description="Number of cross-fitting folds", bounds=(2, 20)),
            ParameterSpec(name="seed", default=42,
                          description="Random seed for fold assignment"),
            ParameterSpec(name="min_gps", default=1e-4,
                          description="GPS clipping floor"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "K-fold cross-fitting for continuous treatment nuisance functions. "
            "Fits GPS and linear outcome model on K-1 folds, predicts on held-out fold."
        ),
        tags=frozenset({"causal", "cross-fitting", "continuous", "gps", "nuisance"}),
        citations=(
            "Kennedy, E.H. et al. (2017). Non-parametric methods for doubly "
            "robust estimation of continuous treatment effects. JRSS-B.",
        ),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Use upstream of KernelDoseResponseEstimator / ShiftInterventionEstimator.",
        when_not_to_use="Not needed when GPS and outcome model are fitted externally.",
        prerequisites=(),
        diagnostic_checks=("Verify gps_oof > min_gps for all observations.",),
        typical_min_obs=50,
        output_interpretation=(
            "gps_oof[i] = out-of-fold f(T_i|X_i). "
            "outcome_oof[i] = out-of-fold μ(T_i, X_i)."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["covariates"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)

        n = len(Y)
        n_folds = int(params.get("n_folds", 5))
        seed = int(params.get("seed", 42))
        min_gps = float(params.get("min_gps", 1e-4))

        rng = np.random.default_rng(seed)
        idx = rng.permutation(n)
        folds = np.array_split(idx, n_folds)

        gps_oof = np.zeros(n, dtype=float)
        outcome_oof = np.zeros(n, dtype=float)
        fold_assignments = np.zeros(n, dtype=int)

        for k, val_idx in enumerate(folds):
            train_idx = np.concatenate([folds[j] for j in range(n_folds) if j != k])
            fold_assignments[val_idx] = k

            # GPS
            gps_oof[val_idx] = _fit_and_predict_gps(
                X[train_idx], T[train_idx], X[val_idx], T[val_idx]
            )

            # Linear outcome model: Y ~ [1, T, X] beta
            feat_tr = np.column_stack([
                np.ones(len(train_idx)), T[train_idx], X[train_idx]
            ])
            feat_val = np.column_stack([
                np.ones(len(val_idx)), T[val_idx], X[val_idx]
            ])
            beta_y, *_ = np.linalg.lstsq(feat_tr, Y[train_idx], rcond=None)
            outcome_oof[val_idx] = feat_val @ beta_y

        gps_oof = np.clip(gps_oof, min_gps, None)

        return {
            "gps_oof": gps_oof,
            "outcome_oof": outcome_oof,
            "fold_assignments": fold_assignments,
        }


__all__ = ["CrossFitOrchestrator", "CrossFitContinuousOrchestrator"]
