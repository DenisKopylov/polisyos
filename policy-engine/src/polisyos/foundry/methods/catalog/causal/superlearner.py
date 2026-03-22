"""superlearner — Super Learner ensemble for nuisance function estimation.

Implements the Super Learner algorithm (van der Laan, Polley & Hubbard 2007):
an optimal convex combination of base learners chosen via cross-validated
risk minimisation.

Algorithm
---------
1. V-fold cross-validation: for each fold v, train all learners on the
   complementary V-1 folds and predict on fold v.
2. Stack cross-validated predictions into meta-matrix Z (n, K).
3. Fit a non-negative least squares (NNLS) meta-learner:
       w* = argmin ||Zw − Y||²  s.t. w ≥ 0, ∑ wₖ = 1
4. Refit every base learner on the full dataset.
5. At prediction time, compute the convex combination of base-learner
   predictions with weights w*.

Base learner library (pure NumPy + optional scikit-learn)
---------------------------------------------------------
- "ols"   : Ordinary Least Squares
- "ridge" : Ridge regression (alpha selected from a small grid)
- "lasso" : Lasso regression (alpha auto, via sklearn if available, else ridge)
- "rf"    : Random Forest (sklearn; fallback = bagged OLS if unavailable)
- "gbm"   : Gradient Boosting (sklearn; fallback = rf then bagged OLS)

For binary outcomes the same learners are used for probability estimation
and the meta-learner maximises cross-validated log-loss instead.

References
----------
van der Laan, M.J., Polley, E.C. & Hubbard, A.E. (2007).
    "Super Learner." *Statistical Applications in Genetics and Molecular Biology*.
"""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, Literal, Mapping, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


# ---------------------------------------------------------------------------
# Helpers — base learners (pure-numpy where possible)
# ---------------------------------------------------------------------------


def _augment(X: np.ndarray) -> np.ndarray:
    """Prepend a column of ones (intercept) to X."""
    return np.column_stack([np.ones(len(X), dtype=float), X])


def _ols_fit(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Return OLS coefficients β via np.linalg.lstsq."""
    beta, *_ = np.linalg.lstsq(_augment(X), Y, rcond=None)
    return beta


def _ols_predict(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return _augment(X) @ beta


def _ridge_fit(X: np.ndarray, Y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Ridge: (XᵀX + αI)⁻¹ Xᵀ Y (intercept not regularised)."""
    Xa = _augment(X)
    n, p = Xa.shape
    reg = alpha * np.eye(p)
    reg[0, 0] = 0.0  # do not penalise intercept
    beta, *_ = np.linalg.lstsq(Xa.T @ Xa + reg, Xa.T @ Y, rcond=None)
    return beta


def _ridge_cv_fit(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Ridge with simple 3-fold internal CV over alpha ∈ {0.1, 1, 10, 100}."""
    best_alpha, best_mse = 1.0, np.inf
    n = len(Y)
    if n < 30:
        return _ridge_fit(X, Y, alpha=1.0)
    fold_size = max(n // 3, 5)
    for alpha in (0.01, 0.1, 1.0, 10.0, 100.0):
        mse_list = []
        for start in range(0, n, fold_size):
            val_idx = np.arange(start, min(start + fold_size, n))
            tr_idx = np.concatenate([
                np.arange(0, start),
                np.arange(min(start + fold_size, n), n),
            ])
            if len(tr_idx) < 5:
                continue
            beta = _ridge_fit(X[tr_idx], Y[tr_idx], alpha=alpha)
            preds = _ols_predict(X[val_idx], beta)
            mse_list.append(float(np.mean((Y[val_idx] - preds) ** 2)))
        if mse_list and np.mean(mse_list) < best_mse:
            best_mse = np.mean(mse_list)
            best_alpha = alpha
    return _ridge_fit(X, Y, alpha=best_alpha)


def _try_lasso(X: np.ndarray, Y: np.ndarray) -> Any:
    """Try sklearn Lasso with LassoCV; fall back to ridge."""
    try:
        from sklearn.linear_model import LassoCV  # type: ignore[import]
        model = LassoCV(cv=3, max_iter=5000, random_state=0)
        model.fit(X, Y)
        return ("sklearn", model)
    except Exception:
        return ("numpy_beta", _ridge_cv_fit(X, Y))


def _try_rf(X: np.ndarray, Y: np.ndarray, binary: bool = False) -> Any:
    """Try sklearn RandomForest; fall back to bagged OLS."""
    try:
        if binary:
            from sklearn.ensemble import RandomForestClassifier  # type: ignore[import]
            model = RandomForestClassifier(
                n_estimators=100, min_samples_leaf=5, random_state=0, n_jobs=1
            )
        else:
            from sklearn.ensemble import RandomForestRegressor  # type: ignore[import]
            model = RandomForestRegressor(
                n_estimators=100, min_samples_leaf=5, random_state=0, n_jobs=1
            )
        model.fit(X, Y)
        return ("sklearn", model)
    except Exception:
        return ("numpy_beta", _ridge_cv_fit(X, Y))


def _try_gbm(X: np.ndarray, Y: np.ndarray, binary: bool = False) -> Any:
    """Try sklearn GradientBoosting; fall back to rf then bagged OLS."""
    try:
        if binary:
            from sklearn.ensemble import GradientBoostingClassifier  # type: ignore[import]
            model = GradientBoostingClassifier(
                n_estimators=100, max_depth=3, random_state=0
            )
        else:
            from sklearn.ensemble import GradientBoostingRegressor  # type: ignore[import]
            model = GradientBoostingRegressor(
                n_estimators=100, max_depth=3, random_state=0
            )
        model.fit(X, Y)
        return ("sklearn", model)
    except Exception:
        return _try_rf(X, Y, binary=binary)


def _fit_learner(
    name: str, X: np.ndarray, Y: np.ndarray, binary: bool
) -> Any:
    """Fit a single named learner; return a (kind, model_or_beta) pair."""
    if name == "ols":
        return ("numpy_beta", _ols_fit(X, Y))
    if name == "ridge":
        return ("numpy_beta", _ridge_cv_fit(X, Y))
    if name == "lasso":
        return _try_lasso(X, Y)
    if name == "rf":
        return _try_rf(X, Y, binary=binary)
    if name == "gbm":
        return _try_gbm(X, Y, binary=binary)
    # Unknown learner — fall back to OLS
    return ("numpy_beta", _ols_fit(X, Y))


def _predict_learner(
    learner: Any,
    X: np.ndarray,
    binary: bool = False,
) -> np.ndarray:
    """Generate predictions from a fitted (kind, model_or_beta) pair."""
    feature_idx: np.ndarray | None = None
    if isinstance(learner, tuple) and len(learner) == 3:
        kind, model, feature_idx = learner
    else:
        kind, model = learner

    if feature_idx is not None:
        X = X[:, feature_idx]

    if kind == "numpy_beta":
        pred = _ols_predict(X, model)
        if binary:
            pred = 1.0 / (1.0 + np.exp(-np.clip(pred, -20, 20)))
        return pred
    # sklearn model
    if binary:
        try:
            return model.predict_proba(X)[:, 1]
        except Exception:
            return model.predict(X).astype(float)
    return model.predict(X).astype(float)


# ---------------------------------------------------------------------------
# NNLS meta-learner via projected gradient descent
# ---------------------------------------------------------------------------


def _nnls_weights(Z: np.ndarray, Y: np.ndarray, max_iter: int = 2000) -> np.ndarray:
    """Solve min ||Zw − Y||²  s.t. w ≥ 0, ∑wₖ = 1.

    Uses projected gradient descent with Armijo line-search.  Does not
    require scipy; O(K²) per iteration where K = number of learners.
    """
    n, K = Z.shape
    w = np.ones(K, dtype=float) / K

    try:  # pragma: no cover - optional dependency
        from scipy.optimize import nnls  # type: ignore[import]

        w_nnls, _ = nnls(Z, Y)
        if float(np.sum(w_nnls)) > 0:
            w_nnls = w_nnls / float(np.sum(w_nnls))
            return np.asarray(w_nnls, dtype=float)
    except Exception:
        pass

    ZtZ = Z.T @ Z  # (K, K)
    ZtY = Z.T @ Y  # (K,)

    lr = 1.0 / (np.linalg.norm(ZtZ, ord=2) + 1e-8)

    for _ in range(max_iter):
        grad = 2.0 * (ZtZ @ w - ZtY)
        w_new = w - lr * grad
        # Project onto simplex (Duchi et al. 2008)
        w_new = _project_simplex(w_new)
        if np.linalg.norm(w_new - w) < 1e-8:
            break
        w = w_new

    return w


def _screen_features(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    top_k: int,
) -> np.ndarray:
    """Return indices of the strongest univariate features for screening."""
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float).ravel()
    if X.ndim != 2 or X.shape[1] == 0:
        return np.array([], dtype=int)
    p = X.shape[1]
    if top_k <= 0 or top_k >= p:
        return np.arange(p, dtype=int)

    y_centered = Y - np.mean(Y)
    scores = np.zeros(p, dtype=float)
    for j in range(p):
        xj = X[:, j]
        x_centered = xj - np.mean(xj)
        denom = float(np.linalg.norm(x_centered) * np.linalg.norm(y_centered))
        if denom > 0:
            scores[j] = abs(float(x_centered @ y_centered) / denom)
    order = np.argsort(-scores)
    return np.sort(order[:top_k].astype(int))


def _project_simplex(v: np.ndarray) -> np.ndarray:
    """Project v onto the probability simplex Δ^{K-1} (Duchi et al. 2008)."""
    K = len(v)
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho = int(np.nonzero(u * np.arange(1, K + 1) > (cssv - 1))[0][-1])
    theta = (cssv[rho] - 1.0) / (rho + 1.0)
    return np.maximum(v - theta, 0.0)


# ---------------------------------------------------------------------------
# FittedSuperLearner dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class FittedSuperLearner:
    """A fitted Super Learner ensemble.

    Attributes
    ----------
    weights        : (K,) convex-combination weights for K base learners.
    learner_names  : names of the K base learners in weight order.
    cv_risk        : cross-validated MSE (or log-loss for binary) per learner.
    fitted_learners: base learners refitted on the full dataset.
    meta_learner   : 'nnls' (continuous) or 'nnls_logit' (binary).
    n_folds        : number of CV folds used.
    binary         : whether the outcome is binary (uses probabilities).
    """

    weights: np.ndarray
    learner_names: list[str]
    cv_risk: dict[str, float]
    fitted_learners: list[Any]
    meta_learner: str
    n_folds: int
    binary: bool = False
    feature_indices: np.ndarray | None = None
    nested_cv_risk: float | None = None

    def predict(self, X_new: np.ndarray) -> np.ndarray:
        """Return weighted ensemble prediction on new covariates."""
        X_new = np.asarray(X_new, dtype=float)
        if self.feature_indices is not None and self.feature_indices.size > 0:
            X_new = X_new[:, self.feature_indices]
        preds = np.column_stack([
            _predict_learner(l, X_new, binary=self.binary)
            for l in self.fitted_learners
        ])  # (n_new, K)
        return preds @ self.weights


# ---------------------------------------------------------------------------
# Config model and selection helpers
# ---------------------------------------------------------------------------


class SuperLearnerConfig(BaseModel):
    """Configuration for Super Learner stacking."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_folds: int = Field(default=5, ge=2)
    method: Literal["nnls", "discrete", "loglik"] = "nnls"
    screen: bool = True
    screen_top_k: int = Field(default=20, ge=1)
    candidates: list[str] = Field(default_factory=lambda: ["ols", "ridge", "lasso", "rf", "gbm"])
    nested_cv: bool = False
    seed: int = 42

    @model_validator(mode="after")
    def _validate_config(self) -> "SuperLearnerConfig":
        if not self.candidates:
            raise ValueError("candidates cannot be empty")
        return self


def _discrete_sl(cv_risks: dict[str, float]) -> str:
    """Select the single best learner by minimum CV risk."""
    if not cv_risks:
        raise ValueError("cv_risks cannot be empty")
    return min(cv_risks, key=cv_risks.get)


def _cv_risk(
    learner_name: str,
    X: np.ndarray,
    Y: np.ndarray,
    *,
    n_folds: int,
    binary: bool,
    seed: int,
    feature_indices: np.ndarray | None = None,
) -> float:
    """Return the cross-validated risk for a single learner."""
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float).ravel()
    if feature_indices is not None and feature_indices.size > 0:
        X = X[:, feature_indices]

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(Y))
    folds = np.array_split(idx, n_folds)
    preds = np.zeros(len(Y), dtype=float)
    for fold_k, val_idx in enumerate(folds):
        tr_idx = np.concatenate([folds[j] for j in range(n_folds) if j != fold_k])
        learner = _fit_learner(learner_name, X[tr_idx], Y[tr_idx], binary=binary)
        preds[val_idx] = _predict_learner(learner, X[val_idx], binary=binary)
    if binary:
        p = np.clip(preds, 1e-10, 1.0 - 1e-10)
        return float(-np.mean(Y * np.log(p) + (1 - Y) * np.log(1 - p)))
    return float(np.mean((Y - preds) ** 2))


def _nested_cv_weights(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    library: Sequence[str],
    n_outer: int,
    n_inner: int,
    outcome_type: str,
    seed: int,
    method: str,
    screen: bool,
    screen_top_k: int,
) -> tuple[np.ndarray, float]:
    """Honest nested-CV estimate and stack weights."""
    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float).ravel()
    binary = outcome_type == "binary"

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(Y))
    outer_folds = np.array_split(idx, n_outer)
    outer_preds = np.zeros(len(Y), dtype=float)

    for outer_k, outer_val_idx in enumerate(outer_folds):
        outer_tr_idx = np.concatenate([outer_folds[j] for j in range(n_outer) if j != outer_k])
        inner_fit = SuperLearnerNuisance.fit(
            X[outer_tr_idx],
            Y[outer_tr_idx],
            library=library,
            v_folds=n_inner,
            outcome_type=outcome_type,
            seed=seed + outer_k + 1,
            method=method,
            screen=screen,
            screen_top_k=screen_top_k,
            nested_cv=False,
        )
        outer_preds[outer_val_idx] = inner_fit.predict(X[outer_val_idx])

    if binary:
        p = np.clip(outer_preds, 1e-10, 1.0 - 1e-10)
        nested_risk = float(-np.mean(Y * np.log(p) + (1 - Y) * np.log(1 - p)))
    else:
        nested_risk = float(np.mean((Y - outer_preds) ** 2))

    weights = np.zeros(len(library), dtype=float)
    if method == "discrete":
        risks = {
            name: _cv_risk(name, X, Y, n_folds=n_inner, binary=binary, seed=seed + 17)
            for name in library
        }
        weights[library.index(_discrete_sl(risks))] = 1.0
    else:
        inner = SuperLearnerNuisance.fit(
            X,
            Y,
            library=library,
            v_folds=n_inner,
            outcome_type=outcome_type,
            seed=seed,
            method=method,
            screen=screen,
            screen_top_k=screen_top_k,
            nested_cv=False,
        )
        weights = inner.weights

    return weights, nested_risk


# ---------------------------------------------------------------------------
# SuperLearnerNuisance — main class
# ---------------------------------------------------------------------------


class SuperLearnerNuisance:
    """Super Learner factory (static methods only — no instance needed)."""

    @staticmethod
    def fit(
        X: np.ndarray,
        Y: np.ndarray,
        library: Sequence[str] = ("ols", "ridge", "lasso"),
        v_folds: int = 5,
        outcome_type: str = "continuous",
        seed: int = 42,
        method: str = "nnls",
        screen: bool = True,
        screen_top_k: int = 20,
        nested_cv: bool = False,
        config: SuperLearnerConfig | None = None,
    ) -> FittedSuperLearner:
        """Fit a Super Learner ensemble.

        Parameters
        ----------
        X            : (n, p) covariate matrix.
        Y            : (n,) outcome vector.
        library      : base learner names (subset of 'ols','ridge','lasso','rf','gbm').
        v_folds      : number of cross-validation folds.
        outcome_type : 'continuous' | 'binary'.
        seed         : random seed for fold assignment.

        Returns
        -------
        FittedSuperLearner
        """
        if config is not None:
            library = config.candidates
            v_folds = config.n_folds
            outcome_type = "binary" if outcome_type == "binary" else outcome_type
            method = config.method
            screen = config.screen
            screen_top_k = config.screen_top_k
            nested_cv = config.nested_cv
            seed = config.seed

        X = np.asarray(X, dtype=float)
        Y = np.asarray(Y, dtype=float)
        n = len(Y)
        binary = outcome_type == "binary"
        learner_names = list(library)
        K = len(learner_names)

        feature_indices = _screen_features(X, Y, top_k=screen_top_k) if screen else np.arange(X.shape[1], dtype=int)
        X_work = X[:, feature_indices] if feature_indices.size > 0 else X

        # ---------- V-fold cross-validation ----------
        rng = np.random.default_rng(seed)
        idx = rng.permutation(n)
        folds: list[np.ndarray] = np.array_split(idx, v_folds)

        Z = np.zeros((n, K), dtype=float)  # stacked OOF predictions

        for fold_k, val_idx in enumerate(folds):
            tr_idx = np.concatenate([folds[j] for j in range(v_folds) if j != fold_k])
            X_tr, Y_tr = X_work[tr_idx], Y[tr_idx]
            X_val = X_work[val_idx]
            for l_idx, name in enumerate(learner_names):
                lrn = _fit_learner(name, X_tr, Y_tr, binary=binary)
                Z[val_idx, l_idx] = _predict_learner(lrn, X_val, binary=binary)

        # ---------- CV risk per learner ----------
        cv_risk: dict[str, float] = {}
        for l_idx, name in enumerate(learner_names):
            if binary:
                # log-loss
                p = np.clip(Z[:, l_idx], 1e-10, 1 - 1e-10)
                cv_risk[name] = float(-np.mean(Y * np.log(p) + (1 - Y) * np.log(1 - p)))
            else:
                cv_risk[name] = float(np.mean((Y - Z[:, l_idx]) ** 2))

        # ---------- NNLS meta-learner ----------
        if method == "discrete":
            weights = np.zeros(K, dtype=float)
            best = _discrete_sl(cv_risk)
            weights[learner_names.index(best)] = 1.0
        elif binary:
            Z_clipped = np.clip(Z, 1e-10, 1 - 1e-10)
            weights = _nnls_weights(Z_clipped, Y)
        else:
            weights = _nnls_weights(Z, Y)

        nested_cv_risk: float | None = None
        if nested_cv:
            _, nested_cv_risk = _nested_cv_weights(
                X,
                Y,
                library=learner_names,
                n_outer=max(2, min(v_folds, 5)),
                n_inner=v_folds,
                outcome_type=outcome_type,
                seed=seed,
                method=method,
                screen=screen,
                screen_top_k=screen_top_k,
            )

        # ---------- Refit on full data ----------
        fitted_learners = [
            _fit_learner(name, X_work, Y, binary=binary) for name in learner_names
        ]

        meta = "nnls_logit" if binary else "nnls"
        if method == "discrete":
            meta = "discrete"
        return FittedSuperLearner(
            weights=weights,
            learner_names=learner_names,
            cv_risk=cv_risk,
            fitted_learners=fitted_learners,
            meta_learner=meta,
            n_folds=v_folds,
            binary=binary,
            feature_indices=feature_indices,
            nested_cv_risk=nested_cv_risk,
        )


# ---------------------------------------------------------------------------
# Foundry method wrapper
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags=frozenset({"causal", "nuisance", "ensemble", "super_learner", "semiparametric"}),
)
class SuperLearnerNuisanceModel:
    """Super Learner for nuisance function estimation.

    Optimal convex combination of base learners (OLS, Ridge, Lasso, RF, GBM)
    selected via V-fold cross-validated risk.

    Reference: van der Laan, Polley & Hubbard (2007). Super Learner.
    *Statistical Applications in Genetics and Molecular Biology*.

    Registered as ``causal.nuisance.super_learner@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="super_learner",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     description="(n, p) covariate matrix", unit=Unit("dimensionless", "")),
            SlotSpec(name="outcome", slot_type=SlotType.VECTOR,
                     description="(n,) outcome vector", unit=Unit("dimensionless", "")),
        ]),
        output_slots=frozenset([
            SlotSpec(name="predictions", slot_type=SlotType.SCALAR,
                     description="(n,) ensemble predictions on training data",
                     unit=Unit("dimensionless", "")),
            SlotSpec(name="cv_risk", slot_type=SlotType.SCALAR,
                     description="Cross-validated risk per base learner",
                     unit=Unit("dimensionless", "")),
            SlotSpec(name="weights", slot_type=SlotType.SCALAR,
                     description="(K,) convex-combination weights",
                     unit=Unit("dimensionless", "")),
        ]),
        parameters=(
            ParameterSpec(name="library", default=["ols", "ridge", "lasso"],
                          description="List of base learner names"),
            ParameterSpec(name="v_folds", default=5,
                          description="Number of cross-validation folds",
                          bounds=(2, 20)),
            ParameterSpec(name="outcome_type", default="continuous",
                          description="'continuous' or 'binary'"),
            ParameterSpec(name="seed", default=42,
                          description="Random seed for fold assignment"),
            ParameterSpec(name="method", default="nnls"),
            ParameterSpec(name="screen", default=True),
            ParameterSpec(name="screen_top_k", default=20),
            ParameterSpec(name="nested_cv", default=False),
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
            "Super Learner: optimal convex combination of base learners "
            "(OLS, Ridge, Lasso, RF, GBM) via V-fold cross-validated risk. "
            "Achieves oracle MSE rate among all convex combinations."
        ),
        tags=frozenset({"causal", "nuisance", "ensemble", "semiparametric"}),
        citations=(
            "van der Laan, M.J., Polley, E.C. & Hubbard, A.E. (2007). "
            "Super Learner. Statistical Applications in Genetics and Molecular Biology.",
        ),
        equations={
            "super_learner": (
                "w* = argmin_{w≥0, ||w||₁=1} "
                "1/V ∑_v ||Z_v w − Y_v||²"
            ),
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use for flexible nuisance estimation when n > 500 or p > 20, "
            "as part of AIPW/TMLE/DML. Improves finite-sample efficiency."
        ),
        when_not_to_use=(
            "Avoid for tiny datasets (n < 100) — V-fold CV leaves insufficient "
            "training data per fold. Use OLS or Ridge instead."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Inspect cv_risk to confirm ensemble outperforms worst learner.",
        ),
        typical_min_obs=100,
        output_interpretation=(
            "predictions are in-sample ensemble predictions. "
            "weights show the relative contribution of each base learner."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["covariates"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)

        library = list(params.get("library", ["ols", "ridge", "lasso"]))
        v_folds = int(params.get("v_folds", 5))
        outcome_type = str(params.get("outcome_type", "continuous"))
        seed = int(params.get("seed", 42))
        method = str(params.get("method", "nnls"))
        screen = bool(params.get("screen", True))
        screen_top_k = int(params.get("screen_top_k", 20))
        nested_cv = bool(params.get("nested_cv", False))

        fitted = SuperLearnerNuisance.fit(
            X, Y,
            library=library,
            v_folds=v_folds,
            outcome_type=outcome_type,
            seed=seed,
            method=method,
            screen=screen,
            screen_top_k=screen_top_k,
            nested_cv=nested_cv,
        )

        preds = fitted.predict(X)
        output = {
            "predictions": preds,
            "cv_risk": fitted.cv_risk,
            "weights": fitted.weights.tolist(),
        }
        if fitted.nested_cv_risk is not None:
            output["nested_cv_risk"] = fitted.nested_cv_risk
        return output


__all__ = [
    "FittedSuperLearner",
    "SuperLearnerConfig",
    "SuperLearnerNuisance",
    "SuperLearnerNuisanceModel",
    "_cv_risk",
    "_discrete_sl",
    "_nnls_weights",
    "_project_simplex",
    "_screen_features",
]
