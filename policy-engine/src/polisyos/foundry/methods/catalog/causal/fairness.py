"""Causal Fairness Methods: TV decomposition, path-specific, and counterfactual fairness.

Phase 8 — Pearl-Bareinboim Causal Engine SOTA

Three foundry methods:

1. **TVFairnessDecomposer** — Plecko & Bareinboim (2022) TV = DE + IE + SE decomposition.
   Doubly-robust AIPW estimation of each component.

2. **PathSpecificFairnessEstimator** — Zhang & Bareinboim (2018) path-specific fairness.
   Classifies causal paths into fair/unfair and estimates path-specific effects.

3. **CounterfactualFairnessEstimator** — Kusner et al. (2017) counterfactual fairness.
   Tests whether predictions are invariant to counterfactual changes to the protected attribute.

References
----------
Plecko, D. & Bareinboim, E. (2022). Causal Fairness Analysis. ICML.
Zhang, J. & Bareinboim, E. (2018). Fairness in Decision-Making — The Causal
    Explanation Formula. AAAI.
Kusner, M.J., Loftus, J., Russell, C. & Silva, R. (2017). Counterfactual
    Fairness. NeurIPS.
"""
from __future__ import annotations

import math
import re
import time
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
from polisyos.ir.analytics.fairness import CausalFairnessReport, FairnessDecomposition


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _fit_logistic(
    T: np.ndarray,
    X: np.ndarray,
    *,
    min_propensity: float = 1e-3,
    n_iter: int = 10,
) -> np.ndarray:
    """Fit P(T=1 | X) via Newton-IRLS logistic regression.

    Returns clipped propensity scores in [min_propensity, 1 - min_propensity].
    """
    n = len(T)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    X_aug = np.column_stack([np.ones(n), X])
    p = np.full(n, float(np.clip(np.mean(T), min_propensity, 1.0 - min_propensity)))
    for _ in range(n_iter):
        w = p * (1.0 - p)
        z = np.log(p / (1.0 - p)) + (T - p) / np.maximum(w, 1e-10)
        try:
            beta = np.linalg.solve(
                X_aug.T @ (w[:, None] * X_aug) + 1e-4 * np.eye(X_aug.shape[1]),
                X_aug.T @ (w * z),
            )
            p = 1.0 / (1.0 + np.exp(-X_aug @ beta))
        except np.linalg.LinAlgError:
            break
        p = np.clip(p, min_propensity, 1.0 - min_propensity)
    return p


def _fit_ols_outcome(
    Y_train: np.ndarray,
    A_train: np.ndarray,
    X_train: np.ndarray,
    a_val: float,
    X_test: np.ndarray,
    Y_full: np.ndarray,
) -> np.ndarray:
    """Fit E[Y | A=a_val, X] via OLS on training subset, predict on test."""
    n_te = len(X_test)
    mask = np.abs(A_train - a_val) < 0.5
    if int(mask.sum()) < 3:
        return np.full(n_te, float(np.mean(Y_full)))
    if X_train.ndim == 1:
        X_train = X_train.reshape(-1, 1)
    if X_test.ndim == 1:
        X_test = X_test.reshape(-1, 1)
    X_fit = np.column_stack([np.ones(int(mask.sum())), X_train[mask]])
    X_pred = np.column_stack([np.ones(n_te), X_test])
    Y_sub = Y_train[mask]
    try:
        coef = np.linalg.lstsq(X_fit, Y_sub, rcond=None)[0]
        return X_pred @ coef
    except np.linalg.LinAlgError:
        return np.full(n_te, float(np.mean(Y_sub)))


def _aipw_ate(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    *,
    n_folds: int = 3,
    min_propensity: float = 1e-3,
    rng: np.random.Generator,
) -> tuple[float, float, tuple[float, float]]:
    """Cross-fitted AIPW ATE estimator (doubly-robust).

    Returns (ate, se, (ci_lower, ci_upper)).
    """
    n = len(Y)
    if X.ndim == 1:
        X = X.reshape(-1, 1)

    idx = rng.permutation(n)
    folds = np.array_split(idx, n_folds)
    scores = np.zeros(n)

    for k in range(n_folds):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(n_folds) if j != k])
        Y_tr, T_tr, X_tr = Y[train_idx], T[train_idx], X[train_idx]
        Y_te, T_te, X_te = Y[test_idx], T[test_idx], X[test_idx]

        e_te = _fit_logistic(T_tr, X_tr, min_propensity=min_propensity)
        # Re-fit on training, predict on test
        X_tr_aug = np.column_stack([np.ones(len(T_tr)), X_tr])
        X_te_aug = np.column_stack([np.ones(len(T_te)), X_te])
        p_tr = np.full(len(T_tr), float(np.clip(np.mean(T_tr), min_propensity, 1.0 - min_propensity)))
        p_te = np.full(len(T_te), float(np.clip(np.mean(T_tr), min_propensity, 1.0 - min_propensity)))
        for _ in range(10):
            w = p_tr * (1.0 - p_tr)
            z = np.log(p_tr / (1.0 - p_tr)) + (T_tr - p_tr) / np.maximum(w, 1e-10)
            try:
                beta = np.linalg.solve(
                    X_tr_aug.T @ (w[:, None] * X_tr_aug) + 1e-4 * np.eye(X_tr_aug.shape[1]),
                    X_tr_aug.T @ (w * z),
                )
                p_tr = np.clip(1.0 / (1.0 + np.exp(-X_tr_aug @ beta)), min_propensity, 1.0 - min_propensity)
                p_te = np.clip(1.0 / (1.0 + np.exp(-X_te_aug @ beta)), min_propensity, 1.0 - min_propensity)
            except np.linalg.LinAlgError:
                break

        mu1_te = _fit_ols_outcome(Y_tr, T_tr, X_tr, 1.0, X_te, Y)
        mu0_te = _fit_ols_outcome(Y_tr, T_tr, X_tr, 0.0, X_te, Y)

        psi = (
            (mu1_te - mu0_te)
            + T_te * (Y_te - mu1_te) / p_te
            - (1.0 - T_te) * (Y_te - mu0_te) / (1.0 - p_te)
        )
        scores[test_idx] = psi

    ate = float(np.mean(scores))
    se = float(np.std(scores, ddof=1) / math.sqrt(n))
    ci = (ate - 1.96 * se, ate + 1.96 * se)
    return ate, se, ci


def _nde_nie_cross_fit(
    Y: np.ndarray,
    A: np.ndarray,
    M: np.ndarray,
    X: np.ndarray,
    *,
    n_folds: int = 3,
    min_propensity: float = 1e-3,
    rng: np.random.Generator,
) -> tuple[float, float, float, float, float, float]:
    """Cross-fitted NDE and NIE using regression-imputation + AIPW correction.

    A (protected attribute) plays the role of "treatment" (binary {a0, a1}).
    Assumes A is already binarized to {0, 1} before calling.

    Returns (nde, nde_se, nie, nie_se, ate, ate_se).
    """
    n = len(Y)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    if M.ndim == 1:
        M = M.reshape(-1, 1)
    # Use first mediator column for NDE/NIE if multiple mediators
    M1 = M[:, 0]

    idx = rng.permutation(n)
    folds = np.array_split(idx, n_folds)
    nde_scores = np.zeros(n)
    nie_scores = np.zeros(n)
    ate_scores = np.zeros(n)

    for k in range(n_folds):
        test_idx = folds[k]
        train_idx = np.concatenate([folds[j] for j in range(n_folds) if j != k])
        Y_tr, A_tr, M_tr, X_tr = Y[train_idx], A[train_idx], M1[train_idx], X[train_idx]
        Y_te, A_te, M_te, X_te = Y[test_idx], A[test_idx], M1[test_idx], X[test_idx]
        n_te = len(Y_te)

        # --- Propensity on training, evaluate on test ---
        X_tr_aug = np.column_stack([np.ones(len(A_tr)), X_tr])
        X_te_aug = np.column_stack([np.ones(n_te), X_te])
        p_tr = np.full(len(A_tr), float(np.clip(np.mean(A_tr), min_propensity, 1.0 - min_propensity)))
        p_te = np.full(n_te, float(np.clip(np.mean(A_tr), min_propensity, 1.0 - min_propensity)))
        for _ in range(10):
            w = p_tr * (1.0 - p_tr)
            z = np.log(p_tr / (1.0 - p_tr)) + (A_tr - p_tr) / np.maximum(w, 1e-10)
            try:
                beta_e = np.linalg.solve(
                    X_tr_aug.T @ (w[:, None] * X_tr_aug) + 1e-4 * np.eye(X_tr_aug.shape[1]),
                    X_tr_aug.T @ (w * z),
                )
                p_tr = np.clip(1.0 / (1.0 + np.exp(-X_tr_aug @ beta_e)), min_propensity, 1.0 - min_propensity)
                p_te = np.clip(1.0 / (1.0 + np.exp(-X_te_aug @ beta_e)), min_propensity, 1.0 - min_propensity)
            except np.linalg.LinAlgError:
                break

        # --- Outcome models E[Y | A=a, M, X] on training, predict at reference mediator ---
        def _predict_outcome(
            Y_sub: np.ndarray, A_sub: np.ndarray, M_sub: np.ndarray, X_sub: np.ndarray,
            a_val: float, M_pred: np.ndarray, X_pred: np.ndarray,
        ) -> np.ndarray:
            mask = np.abs(A_sub - a_val) < 0.5
            n_p = len(M_pred)
            default = float(np.mean(Y_sub[mask])) if int(mask.sum()) > 0 else float(np.mean(Y_sub))
            if int(mask.sum()) < 3:
                return np.full(n_p, default)
            Xf_fit = np.column_stack([np.ones(int(mask.sum())), M_sub[mask].reshape(-1, 1), X_sub[mask]])
            Xf_pred = np.column_stack([np.ones(n_p), M_pred.reshape(-1, 1), X_pred])
            try:
                coef = np.linalg.lstsq(Xf_fit, Y_sub[mask], rcond=None)[0]
                return Xf_pred @ coef
            except np.linalg.LinAlgError:
                return np.full(n_p, default)

        # E[M | A=a, X] on training
        def _predict_mediator_mean(
            M_sub: np.ndarray, A_sub: np.ndarray, X_sub: np.ndarray,
            a_val: float, X_pred: np.ndarray,
        ) -> np.ndarray:
            mask = np.abs(A_sub - a_val) < 0.5
            n_p = len(X_pred)
            M_filt = M_sub[mask]
            if len(M_filt) < 3:
                return np.full(n_p, float(np.mean(M_filt)) if len(M_filt) > 0 else 0.0)
            Xf = np.column_stack([np.ones(int(mask.sum())), X_sub[mask]])
            Xp = np.column_stack([np.ones(n_p), X_pred])
            try:
                coef = np.linalg.lstsq(Xf, M_filt, rcond=None)[0]
                return Xp @ coef
            except np.linalg.LinAlgError:
                return np.full(n_p, float(np.mean(M_filt)))

        m0_pred = _predict_mediator_mean(M_tr, A_tr, X_tr, 0.0, X_te)
        m1_pred = _predict_mediator_mean(M_tr, A_tr, X_tr, 1.0, X_te)

        mu1_at_m0 = _predict_outcome(Y_tr, A_tr, M_tr, X_tr, 1.0, m0_pred, X_te)
        mu0_at_m0 = _predict_outcome(Y_tr, A_tr, M_tr, X_tr, 0.0, m0_pred, X_te)
        mu1_at_m1 = _predict_outcome(Y_tr, A_tr, M_tr, X_tr, 1.0, m1_pred, X_te)

        # Outcome at observed mediator (for AIPW correction)
        mu1_obs = _predict_outcome(Y_tr, A_tr, M_tr, X_tr, 1.0, M_te, X_te)
        mu0_obs = _predict_outcome(Y_tr, A_tr, M_tr, X_tr, 0.0, M_te, X_te)

        nde_plugin = mu1_at_m0 - mu0_at_m0
        nie_plugin = mu1_at_m1 - mu1_at_m0
        correction = (
            A_te / p_te * (Y_te - mu1_obs)
            - (1.0 - A_te) / (1.0 - p_te) * (Y_te - mu0_obs)
        )

        nde_scores[test_idx] = nde_plugin + correction
        nie_scores[test_idx] = nie_plugin

        # ATE for reference
        ate_plugin = mu1_obs - mu0_obs
        ate_scores[test_idx] = ate_plugin + correction

    nde = float(np.mean(nde_scores))
    nde_se = float(np.std(nde_scores, ddof=1) / math.sqrt(n))
    nie = float(np.mean(nie_scores))
    nie_se = float(np.std(nie_scores, ddof=1) / math.sqrt(n))
    ate = float(np.mean(ate_scores))
    ate_se = float(np.std(ate_scores, ddof=1) / math.sqrt(n))
    return nde, nde_se, nie, nie_se, ate, ate_se


def _parse_dot_adjacency(graph_dot: str) -> dict[str, list[str]]:
    """Parse a DOT graph string into a forward adjacency dict.

    Handles simple patterns like ``A -> B`` and ``A -> B [label="weight"]``.
    """
    adjacency: dict[str, list[str]] = {}
    for match in re.finditer(r'(\w+)\s*->\s*(\w+)', graph_dot):
        src, dst = match.group(1), match.group(2)
        if src not in adjacency:
            adjacency[src] = []
        adjacency[src].append(dst)
    return adjacency


def _all_simple_paths(
    adjacency: dict[str, list[str]],
    source: str,
    target: str,
    max_paths: int = 50,
) -> list[list[str]]:
    """Enumerate all simple paths from source to target via DFS."""
    paths: list[list[str]] = []
    stack = [(source, [source])]
    while stack and len(paths) < max_paths:
        node, path = stack.pop()
        if node == target:
            paths.append(path)
            continue
        for neighbor in adjacency.get(node, []):
            if neighbor not in path:
                stack.append((neighbor, path + [neighbor]))
    return paths


def _build_fairness_report(
    tv: float,
    tv_se: float,
    de: float,
    de_se: float,
    ie: float,
    ie_se: float,
    n_obs: int,
    protected_attribute: str,
    outcome: str,
    mediators: tuple[str, ...],
    estimation_method: str,
    path_specific_fairness: dict[str, bool],
    cf_fairness: bool,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Assemble a CausalFairnessReport from computed components."""
    se_val = tv - de - ie
    residual = abs(tv - (de + ie + se_val))

    z = 1.96
    de_ci: tuple[float, float] = (de - z * de_se, de + z * de_se)
    ie_ci: tuple[float, float] = (ie - z * de_se, ie + z * de_se)
    tv_ci: tuple[float, float] = (tv - z * tv_se, tv + z * tv_se)
    # SE CI by error propagation (sum of variances, assuming independence)
    se_se = math.sqrt(tv_se ** 2 + de_se ** 2 + (de_se if ie_se == 0.0 else ie_se) ** 2)
    se_ci: tuple[float, float] = (se_val - z * se_se, se_val + z * se_se)

    decomp = FairnessDecomposition(
        tv=tv,
        direct_effect=de,
        indirect_effect=ie,
        spurious_effect=se_val,
        decomposition_residual=residual,
        tv_ci=tv_ci,
        de_ci=de_ci,
        ie_ci=ie_ci,
        se_ci=se_ci,
        n_obs=n_obs,
        protected_attribute=protected_attribute,
        outcome=outcome,
        mediators=mediators,
        estimation_method=estimation_method,
        metadata=metadata,
    )

    direct_disc = abs(de)
    indirect_disc = abs(ie)

    # Primary unfair pathway: largest |effect| among unfair paths
    unfair_effects: list[tuple[str, float]] = [
        (path, abs(v)) for path, v in metadata.get("path_effects", {}).items()
        if not path_specific_fairness.get(path, True)
    ]
    primary_unfair: str | None = None
    if unfair_effects:
        primary_unfair = max(unfair_effects, key=lambda x: x[1])[0]

    # Build human-readable recommendation
    if abs(tv) < 0.01:
        rec = "No meaningful disparity detected (|TV| < 0.01)."
    elif direct_disc < 0.05 and indirect_disc < 0.05:
        rec = (
            f"Disparity (TV={tv:.3f}) is primarily spurious/confounded (SE={se_val:.3f}). "
            "No evidence of direct or indirect causal discrimination."
        )
    elif direct_disc >= indirect_disc:
        rec = (
            f"Direct causal discrimination detected (DE={de:.3f}, |TV|={abs(tv):.3f}). "
            "The protected attribute has a direct causal effect on the outcome. "
            "Consider removing or constraining the direct pathway."
        )
    else:
        rec = (
            f"Indirect causal discrimination via mediators detected (IE={ie:.3f}, |TV|={abs(tv):.3f}). "
            "The protected attribute influences the outcome through mediating variables. "
            "Consider fairness-constrained learning on mediators."
        )

    report = CausalFairnessReport(
        decomposition=decomp,
        counterfactual_fairness_satisfied=cf_fairness,
        path_specific_fairness=path_specific_fairness,
        direct_discrimination=direct_disc,
        indirect_discrimination=indirect_disc,
        primary_unfair_pathway=primary_unfair,
        recommendation=rec,
        metadata=metadata,
    )
    return report.model_dump()


# ---------------------------------------------------------------------------
# Foundry method 1: TVFairnessDecomposer
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.fairness",
    version="1.0.0",
    tags={"causal", "fairness", "tv_decomposition", "aipw", "semiparametric"},
)
class TVFairnessDecomposer:
    """TV = DE + IE + SE decomposition (Plecko & Bareinboim 2022).

    Decomposes the total observational disparity between protected groups
    into three causal components:

    - **DE** (Direct Effect): disparity flowing directly A → Y
    - **IE** (Indirect Effect): disparity via mediators A → M → Y
    - **SE** (Spurious Effect): non-causal confounded association

    Estimation
    ----------
    - With mediators: cross-fitted regression-imputation + AIPW correction
      (doubly-robust, tolerates misspecification of propensity OR outcome model)
    - Without mediators: AIPW ATE (DE = ATE, IE = 0, SE = TV - DE)

    Input slots
    -----------
    outcome    : outcome variable (n_obs,)
    protected  : protected attribute, binarized to {a0, a1} (n_obs,)
    covariates : background features (n_obs, n_features)
    mediators  : optional mediating variables (n_obs, n_mediators)

    Output slots
    ------------
    fairness_report : :class:`CausalFairnessReport` as JSON dict
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tv_fairness_decomposer",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec("protected", SlotType.VECTOR, Unit("protected", "binary"), shape=("n_obs",)),
            SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("mediators", SlotType.MATRIX, Unit("mediator", "value"), shape=("n_obs", "n_mediators")),
        }),
        output_slots=frozenset({
            SlotSpec("fairness_report", SlotType.SCALAR, Unit("report", "json")),
        }),
        parameters=(
            ParameterSpec(name="protected_a0", default=0),
            ParameterSpec(name="protected_a1", default=1),
            ParameterSpec(name="n_folds", default=3),
            ParameterSpec(name="min_propensity_clip", default=1e-3),
            ParameterSpec(name="protected_attribute_name", default="A"),
            ParameterSpec(name="outcome_name", default="Y"),
            ParameterSpec(name="mediator_names", default=[]),
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
            "TV = DE + IE + SE causal fairness decomposition via doubly-robust AIPW. "
            "Plecko & Bareinboim (2022)."
        ),
        tags=frozenset({
            "causal", "fairness", "tv_decomposition", "aipw", "semiparametric",
            "phase8", "discrimination",
        }),
        citations=(
            "Plecko, D. & Bareinboim, E. (2022). Causal Fairness Analysis. ICML.",
            "Zhang, J. & Bareinboim, E. (2018). Fairness in Decision-Making. AAAI.",
        ),
        equations={
            "tv": "TV = E[Y|A=a1] - E[Y|A=a0]",
            "decomp": "TV = DE + IE + SE",
            "de_aipw": (
                "DE = (1/n) Σ_i [(μ₁(Xᵢ) − μ₀(Xᵢ)) "
                "+ Aᵢ(Yᵢ−μ₁(Xᵢ))/e(Xᵢ) − (1−Aᵢ)(Yᵢ−μ₀(Xᵢ))/(1−e(Xᵢ))]"
            ),
            "ie": "IE = NDE_nde_cross_fit (via mediator-conditional outcome)",
            "se": "SE = TV - DE - IE",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Decompose disparity between protected groups into causal components; "
            "audit decisions for direct vs. indirect discrimination."
        ),
        when_not_to_use=(
            "When protected attribute has more than 2 levels (use multinomial extension); "
            "when hidden confounders between A and M are suspected without sensitivity analysis."
        ),
        typical_min_obs=200,
        output_interpretation=(
            "TV: total observational gap. "
            "DE: direct causal discrimination (path A→Y). "
            "IE: indirect via mediators (A→M→Y). "
            "SE: spurious/confounded. "
            "DE + IE + SE ≈ TV."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        t0 = time.time()
        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        Y = np.asarray(state["outcome"], dtype=float).ravel()
        A_raw = np.asarray(state["protected"], dtype=float).ravel()
        X = np.asarray(state["covariates"], dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        M_raw = state.get("mediators")
        M: np.ndarray | None = None
        if M_raw is not None:
            M = np.asarray(M_raw, dtype=float)
            if M.ndim == 1:
                M = M.reshape(-1, 1)

        a0 = float(params.get("protected_a0", 0))
        a1 = float(params.get("protected_a1", 1))
        n_folds = int(params.get("n_folds", 3))
        min_prop = float(params.get("min_propensity_clip", 1e-3))
        attr_name = str(params.get("protected_attribute_name", "A"))
        outcome_name = str(params.get("outcome_name", "Y"))
        mediator_names_param = list(params.get("mediator_names", []))

        n = len(Y)

        # Binarize A: map a0 → 0, a1 → 1
        A_bin = np.where(np.abs(A_raw - a1) < np.abs(A_raw - a0), 1.0, 0.0)

        # TV: raw observational gap
        mask1 = A_bin > 0.5
        mask0 = A_bin <= 0.5
        n1 = int(mask1.sum())
        n0 = int(mask0.sum())
        if n1 < 3 or n0 < 3:
            raise ValueError(
                f"Not enough observations for each group: n(a1)={n1}, n(a0)={n0}. "
                "Ensure both groups have at least 3 observations."
            )
        tv = float(np.mean(Y[mask1]) - np.mean(Y[mask0]))

        # TV SE via Welch approximation
        tv_se = math.sqrt(
            float(np.var(Y[mask1], ddof=1)) / n1
            + float(np.var(Y[mask0], ddof=1)) / n0
        )

        if M is not None:
            # With mediators: NDE/NIE cross-fitting
            mediator_names = (
                mediator_names_param
                if mediator_names_param
                else [f"M{j}" for j in range(M.shape[1])]
            )
            de, de_se, ie, ie_se, ate, ate_se = _nde_nie_cross_fit(
                Y, A_bin, M, X,
                n_folds=n_folds,
                min_propensity=min_prop,
                rng=rng,
            )
        else:
            # Without mediators: AIPW ATE
            mediator_names = []
            de, de_se, ci = _aipw_ate(Y, A_bin, X, n_folds=n_folds, min_propensity=min_prop, rng=rng)
            ie = 0.0
            ie_se = 0.0

        meta = {
            "elapsed_seconds": time.time() - t0,
            "n_a1": n1,
            "n_a0": n0,
            "n_folds": n_folds,
            "has_mediators": M is not None,
        }

        report = _build_fairness_report(
            tv=tv,
            tv_se=tv_se,
            de=de,
            de_se=de_se,
            ie=ie,
            ie_se=ie_se,
            n_obs=n,
            protected_attribute=attr_name,
            outcome=outcome_name,
            mediators=tuple(mediator_names),
            estimation_method="tv_decomposition",
            path_specific_fairness={},
            cf_fairness=(abs(de) < 0.05 and abs(ie) < 0.05),
            metadata=meta,
        )
        return {"fairness_report": report}


# ---------------------------------------------------------------------------
# Foundry method 2: PathSpecificFairnessEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.fairness",
    version="1.0.0",
    tags={"causal", "fairness", "path_specific", "graph"},
)
class PathSpecificFairnessEstimator:
    """Path-Specific Fairness via causal graph decomposition (Zhang & Bareinboim 2018).

    Enumerates all causal paths from the protected attribute to the outcome
    in the provided causal graph, classifies them as fair or unfair based on
    the ``legitimate_mediators`` parameter, and estimates the path-specific
    effect (PSE) for each unfair path.

    A path is **fair** if every intermediate node belongs to ``legitimate_mediators``
    (e.g., "Qualification", "Merit"). A path is **unfair** if it contains a
    direct edge A → Y or passes through an illegitimate mediator.

    Input slots
    -----------
    outcome    : outcome variable (n_obs,)
    protected  : protected attribute (n_obs,)
    covariates : background features (n_obs, n_features)
    mediators  : mediating variables (n_obs, n_mediators); required

    Output slots
    ------------
    fairness_report : :class:`CausalFairnessReport` as JSON dict
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="path_specific_fairness",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec("protected", SlotType.VECTOR, Unit("protected", "binary"), shape=("n_obs",)),
            SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("mediators", SlotType.MATRIX, Unit("mediator", "value"), shape=("n_obs", "n_mediators")),
        }),
        output_slots=frozenset({
            SlotSpec("fairness_report", SlotType.SCALAR, Unit("report", "json")),
        }),
        parameters=(
            ParameterSpec(name="graph_dot", default=""),
            ParameterSpec(name="protected_node", default="A"),
            ParameterSpec(name="outcome_node", default="Y"),
            ParameterSpec(name="legitimate_mediators", default=[]),
            ParameterSpec(name="effect_threshold", default=0.05),
            ParameterSpec(name="n_folds", default=3),
            ParameterSpec(name="min_propensity_clip", default=1e-3),
            ParameterSpec(name="mediator_node_names", default=[]),
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
            "Path-specific fairness: classify causal paths into fair/unfair and "
            "estimate path-specific effects (Zhang & Bareinboim 2018)."
        ),
        tags=frozenset({
            "causal", "fairness", "path_specific", "graph", "discrimination",
            "phase8",
        }),
        citations=(
            "Zhang, J. & Bareinboim, E. (2018). Fairness in Decision-Making — "
            "The Causal Explanation Formula. AAAI.",
            "Avin, C., Shpitser, I. & Pearl, J. (2005). Identifiability of "
            "Path-Specific Effects. IJCAI.",
        ),
        equations={
            "pse": "PSE(path) = E[Y_{A=a1, frozen(other_paths)=A(a0)}] - E[Y_{A=a0}]",
            "fair": "|PSE(path)| < threshold for all unfair paths → fairness satisfied",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "When you have a causal graph and can classify paths into legitimate "
            "(fair) and illegitimate (unfair) based on domain knowledge."
        ),
        when_not_to_use=(
            "When no causal graph is available; use TVFairnessDecomposer instead."
        ),
        typical_min_obs=200,
        output_interpretation=(
            "path_specific_fairness: dict of path → bool (True = fair). "
            "direct_discrimination: |effect| of direct A→Y path. "
            "primary_unfair_pathway: most impactful unfair path."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        t0 = time.time()
        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        Y = np.asarray(state["outcome"], dtype=float).ravel()
        A_raw = np.asarray(state["protected"], dtype=float).ravel()
        X = np.asarray(state["covariates"], dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        n = len(Y)

        # Parameters
        graph_dot = str(params.get("graph_dot", state.get("graph_dot", "")))
        protected_node = str(params.get("protected_node", "A"))
        outcome_node = str(params.get("outcome_node", "Y"))
        legitimate_mediators: list[str] = list(params.get("legitimate_mediators", []))
        threshold = float(params.get("effect_threshold", 0.05))
        n_folds = int(params.get("n_folds", 3))
        min_prop = float(params.get("min_propensity_clip", 1e-3))
        mediator_node_names: list[str] = list(params.get("mediator_node_names", []))

        # Binarize A
        a0, a1 = 0.0, 1.0
        A_bin = np.where(np.abs(A_raw - a1) < np.abs(A_raw - a0), 1.0, 0.0)

        # TV
        mask1 = A_bin > 0.5
        mask0 = A_bin <= 0.5
        n1, n0 = int(mask1.sum()), int(mask0.sum())
        if n1 < 3 or n0 < 3:
            raise ValueError(f"Not enough observations: n(a1)={n1}, n(a0)={n0}")
        tv = float(np.mean(Y[mask1]) - np.mean(Y[mask0]))
        tv_se = math.sqrt(
            float(np.var(Y[mask1], ddof=1)) / max(n1, 1)
            + float(np.var(Y[mask0], ddof=1)) / max(n0, 1)
        )

        # Parse graph and enumerate paths
        path_effects: dict[str, float] = {}
        path_fairness: dict[str, bool] = {}

        if graph_dot:
            adjacency = _parse_dot_adjacency(graph_dot)
            all_paths = _all_simple_paths(adjacency, protected_node, outcome_node)

            for path in all_paths:
                path_label = " → ".join(path)
                intermediate = [node for node in path[1:-1]]

                # Classify path:
                # - Direct path (no intermediates): UNFAIR by default (direct discrimination)
                # - Mediated path: FAIR only if every intermediate node is a legitimate mediator
                is_fair = bool(intermediate) and all(
                    node in legitimate_mediators for node in intermediate
                )
                path_fairness[path_label] = is_fair

                # Estimate effect for this path (use NDE/NIE if we have mediators)
                M_raw = state.get("mediators")
                if not is_fair and M_raw is not None and intermediate:
                    M = np.asarray(M_raw, dtype=float)
                    if M.ndim == 1:
                        M = M.reshape(-1, 1)
                    # Find mediator column index
                    col_idx = 0
                    if mediator_node_names and intermediate[0] in mediator_node_names:
                        col_idx = mediator_node_names.index(intermediate[0])
                    M_path = M[:, min(col_idx, M.shape[1] - 1)].reshape(-1, 1)
                    de, de_se, ie, ie_se, _, _ = _nde_nie_cross_fit(
                        Y, A_bin, M_path, X,
                        n_folds=n_folds,
                        min_propensity=min_prop,
                        rng=rng,
                    )
                    path_effect = de  # NDE captures direct contribution for this path
                elif not is_fair:
                    # Direct path A → Y: use AIPW ATE
                    ate, ate_se, _ = _aipw_ate(
                        Y, A_bin, X, n_folds=n_folds, min_propensity=min_prop, rng=rng
                    )
                    path_effect = ate
                else:
                    path_effect = 0.0

                path_effects[path_label] = path_effect
                # Re-evaluate fairness based on estimated effect size
                if not is_fair:
                    path_fairness[path_label] = abs(path_effect) < threshold
        else:
            # No graph: fall back to TV-only analysis
            ate, ate_se, _ = _aipw_ate(
                Y, A_bin, X, n_folds=n_folds, min_propensity=min_prop, rng=rng
            )
            direct_label = f"{protected_node} → {outcome_node}"
            path_effects[direct_label] = ate
            path_fairness[direct_label] = abs(ate) < threshold

        # Compute DE and IE from path effects
        unfair_effects = {k: v for k, v in path_effects.items() if not path_fairness.get(k, True)}
        fair_effects = {k: v for k, v in path_effects.items() if path_fairness.get(k, True)}
        de_total = float(sum(v for v in unfair_effects.values()))
        ie_total = float(sum(abs(v) for v in fair_effects.values()))

        meta = {
            "elapsed_seconds": time.time() - t0,
            "n_paths_found": len(path_effects),
            "n_unfair_paths": len(unfair_effects),
            "path_effects": path_effects,
            "n_folds": n_folds,
        }

        report = _build_fairness_report(
            tv=tv,
            tv_se=tv_se,
            de=de_total,
            de_se=0.0,
            ie=ie_total,
            ie_se=0.0,
            n_obs=n,
            protected_attribute=protected_node,
            outcome=outcome_node,
            mediators=tuple(mediator_node_names),
            estimation_method="path_specific",
            path_specific_fairness=path_fairness,
            cf_fairness=all(path_fairness.values()) if path_fairness else (abs(tv) < threshold),
            metadata=meta,
        )
        return {"fairness_report": report}


# ---------------------------------------------------------------------------
# Foundry method 3: CounterfactualFairnessEstimator
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.fairness",
    version="1.0.0",
    tags={"causal", "fairness", "counterfactual", "ncm", "l3"},
)
class CounterfactualFairnessEstimator:
    """Counterfactual Fairness test (Kusner et al. 2017).

    Tests whether a system's predictions are invariant to counterfactual
    changes to the protected attribute, holding the latent noise (U) fixed:

        Y is counterfactually fair iff P(Ŷ_{A=a}=y | X, A=a) = P(Ŷ_{A=a'}=y | X, A=a)
        for all (a, a', y, X).

    Implementation
    --------------
    **Linear approximation (default):** Fits a linear SCM ``Y = β_A·A + β_X·X + ε``,
    recovers ``ε_i = Y_i - β_A·A_i - β_X·X_i`` (latent noise), then predicts
    ``Ŷᵢ(A=a') = β_A·a' + β_X·Xᵢ + εᵢ`` and measures the counterfactual gap.

    **Full NCM (when ``ncm_spec_json`` provided):** Delegates to NCMEngineMethod
    for exact abduction-action-prediction with general structural equations.

    Input slots
    -----------
    outcome    : outcome variable (n_obs,)
    protected  : protected attribute (n_obs,)
    covariates : background features (n_obs, n_features)

    Output slots
    ------------
    fairness_report : :class:`CausalFairnessReport` as JSON dict
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="counterfactual_fairness",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            SlotSpec("protected", SlotType.VECTOR, Unit("protected", "binary"), shape=("n_obs",)),
            SlotSpec("covariates", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
        }),
        output_slots=frozenset({
            SlotSpec("fairness_report", SlotType.SCALAR, Unit("report", "json")),
        }),
        parameters=(
            ParameterSpec(name="ncm_spec_json", default=None),
            ParameterSpec(name="counterfactual_gap_threshold", default=0.05),
            ParameterSpec(name="ks_alpha", default=0.05),
            ParameterSpec(name="abduction_method", default="linear_approx"),
            ParameterSpec(name="protected_attribute_name", default="A"),
            ParameterSpec(name="outcome_name", default="Y"),
            ParameterSpec(name="protected_a0", default=0),
            ParameterSpec(name="protected_a1", default=1),
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
            "Counterfactual fairness test: measure invariance of predictions to "
            "counterfactual changes in the protected attribute (Kusner et al. 2017)."
        ),
        tags=frozenset({
            "causal", "fairness", "counterfactual", "ncm", "l3",
            "abduction", "individual_fairness", "phase8",
        }),
        citations=(
            "Kusner, M.J., Loftus, J., Russell, C. & Silva, R. (2017). "
            "Counterfactual Fairness. NeurIPS.",
            "Pearl, J. (2000). Causality, Ch. 7 (Counterfactuals). Cambridge.",
        ),
        equations={
            "cf_fairness": (
                "Y counterfactually fair iff "
                "P(Ŷ_{A=a}=y | X, A=a) = P(Ŷ_{A=a'}=y | X, A=a) ∀(a, a', y, X)"
            ),
            "linear_scm": "Y = β_A·A + β_X·X + ε → ε_i = Y_i - β_A·A_i - β_X·X_i",
            "cf_pred": "Ŷᵢ(A=a') = β_A·a' + β_X·Xᵢ + εᵢ",
            "gap": "gap = mean|Ŷ(A=a1) - Ŷ(A=a0)|",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Individual-level fairness audits; when a structural causal model is "
            "available or a linear SCM approximation is acceptable."
        ),
        when_not_to_use=(
            "Non-linear SCMs without a fitted NCMSpec; highly non-linear relationships "
            "may require full NCM abduction rather than linear approximation."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "counterfactual_fairness_satisfied: True if gap < threshold AND KS test non-significant. "
            "direct_discrimination: |gap| between counterfactual predictions. "
            "metadata.counterfactual_gap: mean absolute counterfactual difference."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        t0 = time.time()

        Y = np.asarray(state["outcome"], dtype=float).ravel()
        A_raw = np.asarray(state["protected"], dtype=float).ravel()
        X = np.asarray(state["covariates"], dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        a0 = float(params.get("protected_a0", 0))
        a1 = float(params.get("protected_a1", 1))
        gap_threshold = float(params.get("counterfactual_gap_threshold", 0.05))
        ks_alpha = float(params.get("ks_alpha", 0.05))
        abduction_method = str(params.get("abduction_method", "linear_approx"))
        attr_name = str(params.get("protected_attribute_name", "A"))
        outcome_name = str(params.get("outcome_name", "Y"))
        ncm_spec_json = params.get("ncm_spec_json", None)

        n = len(Y)

        # Binarize A
        A_bin = np.where(np.abs(A_raw - a1) < np.abs(A_raw - a0), 1.0, 0.0)
        mask1 = A_bin > 0.5
        mask0 = A_bin <= 0.5
        n1, n0 = int(mask1.sum()), int(mask0.sum())

        tv = float(np.mean(Y[mask1]) - np.mean(Y[mask0])) if n1 > 0 and n0 > 0 else 0.0
        tv_se = math.sqrt(
            float(np.var(Y[mask1], ddof=1)) / max(n1, 1)
            + float(np.var(Y[mask0], ddof=1)) / max(n0, 1)
        ) if n1 > 1 and n0 > 1 else abs(tv) * 0.1

        warnings: list[str] = []

        if ncm_spec_json is not None and abduction_method != "linear_approx":
            # Full NCM path: delegate to NCMEngineMethod
            try:
                from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
                ncm_state: dict[str, Any] = {
                    "ncm_spec": ncm_spec_json,
                    "evidence": {attr_name: A_raw.tolist(), "Y": Y.tolist()},
                    "interventions": [{attr_name: a1}, {attr_name: a0}],
                }
                ncm_result = NCMEngineMethod.pure_step(ncm_state, {"__seed__": params.get("__seed__")})
                y_cf_a1 = np.asarray(ncm_result.get("cf_mean_0", Y), dtype=float)
                y_cf_a0 = np.asarray(ncm_result.get("cf_mean_1", Y), dtype=float)
            except Exception as e:
                warnings.append(f"NCM abduction failed ({e}); falling back to linear_approx")
                ncm_spec_json = None

        if ncm_spec_json is None or abduction_method == "linear_approx":
            # Linear SCM approximation:
            # Y = β_A * A + β_X * X + ε  (OLS)
            n_obs = len(Y)
            X_aug = np.column_stack([np.ones(n_obs), A_bin.reshape(-1, 1), X])
            try:
                coef = np.linalg.lstsq(X_aug, Y, rcond=None)[0]
            except np.linalg.LinAlgError:
                coef = np.zeros(X_aug.shape[1])
            beta_a = float(coef[1])
            beta_x = coef[2:]

            # Residuals (abducted latent noise)
            epsilon = Y - X_aug @ coef

            # Counterfactual predictions
            y_cf_a1 = beta_a * a1 + X @ beta_x + epsilon  # Ŷ(A←a1)
            y_cf_a0 = beta_a * a0 + X @ beta_x + epsilon  # Ŷ(A←a0)
            if "linear SCM approximation" not in " ".join(warnings):
                warnings.append("Using linear SCM approximation for counterfactual abduction.")

        # Counterfactual gap
        cf_gap = float(np.mean(np.abs(y_cf_a1 - y_cf_a0)))
        cf_gap_se = float(np.std(np.abs(y_cf_a1 - y_cf_a0), ddof=1) / math.sqrt(n))

        # KS test: do distributions of Ŷ(a1) and Ŷ(a0) differ?
        ks_p_value = 1.0
        try:
            from scipy import stats as scipy_stats
            ks_stat, ks_p_value = scipy_stats.ks_2samp(y_cf_a1, y_cf_a0)
        except ImportError:
            # Fallback: approximate via mean difference
            ks_p_value = 1.0 if cf_gap < gap_threshold else 0.01
            warnings.append("scipy not available; KS test approximated from gap magnitude.")

        cf_fair = (cf_gap < gap_threshold) and (ks_p_value >= ks_alpha)

        # Direct effect = counterfactual gap (how much A causally affects Y)
        de = cf_gap if not cf_fair else 0.0
        de_se = cf_gap_se

        meta: dict[str, Any] = {
            "elapsed_seconds": time.time() - t0,
            "counterfactual_gap": cf_gap,
            "counterfactual_gap_se": cf_gap_se,
            "ks_p_value": ks_p_value,
            "gap_threshold": gap_threshold,
            "ks_alpha": ks_alpha,
            "abduction_method": "linear_approx" if ncm_spec_json is None else "ncm",
            "warnings": warnings,
            "n1": n1,
            "n0": n0,
        }

        report = _build_fairness_report(
            tv=tv,
            tv_se=tv_se,
            de=de,
            de_se=de_se,
            ie=0.0,
            ie_se=0.0,
            n_obs=n,
            protected_attribute=attr_name,
            outcome=outcome_name,
            mediators=(),
            estimation_method="counterfactual",
            path_specific_fairness={},
            cf_fairness=cf_fair,
            metadata=meta,
        )
        return {"fairness_report": report}


__all__ = [
    "TVFairnessDecomposer",
    "PathSpecificFairnessEstimator",
    "CounterfactualFairnessEstimator",
]
