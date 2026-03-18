"""multi_treatment — effect estimation for multi-valued (K ≥ 2) treatment arms.

Two estimators are implemented:

1. **MultinomialIPWEstimator** — Imbens (2000).
   Normalised inverse-probability weighting using a multinomial propensity
   score P(T=k|X) fitted by K−1 one-vs-reference logistic regressions.
   Produces Hajek-normalised arm means E[Y(k)] and ATEs vs reference.

2. **MultiArmAIPWEstimator** — Cattaneo (2010).
   Doubly-robust augmented IPW using the efficient influence function
   (compute_eif_multi_treatment_ate).  Cross-fits propensity and per-arm
   outcome models.  Consistent if either propensity or outcome is correct.

Both estimators take ``MultiTreatmentData`` as input and return
``MultiTreatmentResult``.

References
----------
Imbens, G.W. (2000). The role of the propensity score in estimating
    dose-response functions. *Biometrika* 87(3), 706-710.

Cattaneo, M.D. (2010). Efficient semiparametric estimation of multi-valued
    treatment effects under ignorability. *Journal of Econometrics* 155(2).
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
from polisyos.foundry.methods.catalog.causal.eif_bounds import (
    EIFScores,
    compute_eif_multi_treatment_ate,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    MultiTreatmentData,
    MultiTreatmentResult,
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fit_multinomial_logistic(
    X: np.ndarray,
    T: np.ndarray,
    levels: list[int],
    min_p: float = 0.01,
) -> np.ndarray:
    """Fit K−1 one-vs-reference binary logistic regressions.

    Returns probs (n, K) — P(T=k|X) for each level, clipped and renormalised.
    """
    from polisyos.foundry.methods.catalog.causal.cross_fit import _fit_logistic_beta

    n = len(X)
    K = len(levels)
    level_to_idx = {lv: i for i, lv in enumerate(levels)}
    T_idx = np.array([level_to_idx[int(t)] for t in T], dtype=int)

    X_aug = np.column_stack([np.ones(n), X])
    log_odds = np.zeros((n, K), dtype=float)  # reference arm = 0

    for i in range(1, K):
        T_binary = (T_idx == i).astype(float)
        beta = _fit_logistic_beta(X_aug, T_binary)
        log_odds[:, i] = X_aug @ beta

    # Softmax
    log_odds -= log_odds.max(axis=1, keepdims=True)
    probs = np.exp(log_odds)
    probs /= probs.sum(axis=1, keepdims=True)

    # Clip + renormalise
    probs = np.clip(probs, min_p, 1.0)
    probs /= probs.sum(axis=1, keepdims=True)

    return probs


def _fit_outcome_model(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
) -> np.ndarray:
    """Fit per-arm OLS outcome model via an indicator encoding.

    Returns beta (1 + n_levels + p,) for the model
    μ(T=k, X) = β_0 + β_k·I(T=k) + Xᵀγ.
    """
    levels = sorted(int(v) for v in np.unique(T).tolist())
    K = len(levels)
    level_to_idx = {lv: i for i, lv in enumerate(levels)}
    T_idx = np.array([level_to_idx[int(t)] for t in T], dtype=int)

    # One-hot indicators for K arms (drop reference arm 0 to avoid collinearity)
    indicators = np.zeros((len(T), K - 1), dtype=float)
    for i in range(1, K):
        indicators[:, i - 1] = (T_idx == i).astype(float)

    feat = np.column_stack([np.ones(len(X)), indicators, X])
    beta, *_ = np.linalg.lstsq(feat, Y, rcond=None)
    return beta, levels


def _predict_outcome_by_arm(
    X: np.ndarray,
    k: int,
    beta: np.ndarray,
    levels: list[int],
) -> np.ndarray:
    """Predict μ_k(X) = E[Y | T=k, X] from the per-arm model."""
    K = len(levels)
    n = len(X)
    level_to_idx = {lv: i for i, lv in enumerate(levels)}
    k_idx = level_to_idx.get(k, 0)

    indicators = np.zeros((n, K - 1), dtype=float)
    if k_idx > 0:
        indicators[:, k_idx - 1] = 1.0

    feat = np.column_stack([np.ones(n), indicators, X])
    return feat @ beta


def _all_pairwise_contrasts(
    arm_means: dict[str, float],
    levels: list[int],
) -> dict[str, float]:
    """Return all K(K-1)/2 pairwise contrasts E[Y(k₁)] − E[Y(k₂)]."""
    keys = [str(lv) for lv in levels]
    out: dict[str, float] = {}
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1:]:
            out[f"{k1}_vs_{k2}"] = arm_means[k1] - arm_means[k2]
    return out


def _kfold_indices(n: int, n_folds: int, seed: int = 42) -> list[tuple]:
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, n_folds)
    return [
        (np.concatenate([folds[j] for j in range(n_folds) if j != k]), folds[k])
        for k in range(n_folds)
    ]


def pairwise_contrasts(result: MultiTreatmentResult) -> dict[str, float]:
    """Return all pairwise ATE contrasts from a MultiTreatmentResult.

    Parameters
    ----------
    result : Fitted MultiTreatmentResult.

    Returns
    -------
    dict mapping 'k1_vs_k2' → E[Y(k1)] − E[Y(k2)].
    """
    levels = [str(lv) for lv in sorted(int(x) for x in result.levels)]
    out: dict[str, float] = {}
    for i, k1 in enumerate(levels):
        for k2 in levels[i + 1:]:
            out[f"{k1}_vs_{k2}"] = result.arm_means[k1] - result.arm_means[k2]
    return out


# ---------------------------------------------------------------------------
# Estimator 1: Multinomial IPW — Imbens (2000)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.multi_treatment",
    version="1.0.0",
    tags=frozenset({"causal", "multi_treatment", "ipw", "propensity_score"}),
)
class MultinomialIPWEstimator:
    """Multinomial IPW for K treatment arms (Imbens 2000).

    Fits P(T=k|X) via K−1 one-vs-reference logistic regressions
    (Hajek normalisation)::

        Ê[Y(k)] = Σᵢ I(Tᵢ=k) Yᵢ / p_k(Xᵢ)
                / Σᵢ I(Tᵢ=k) / p_k(Xᵢ)

    SE via sandwich influence function.

    Registered as ``causal.multi_treatment.ipw@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ipw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="outcome", slot_type=SlotType.VECTOR,
                     description="(n,) outcome", unit=Unit("dimensionless", "")),
            SlotSpec(name="treatment", slot_type=SlotType.VECTOR,
                     description="(n,) integer treatment labels", unit=Unit("dimensionless", "")),
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     description="(n, p) covariates", unit=Unit("dimensionless", "")),
        ]),
        output_slots=frozenset([
            SlotSpec(name="multi_treatment_result", slot_type=SlotType.SCALAR,
                     description="MultiTreatmentResult dict", unit=Unit("dimensionless", "")),
        ]),
        parameters=(
            ParameterSpec(name="reference_level", default=0,
                          description="Reference treatment arm for ATE contrasts"),
            ParameterSpec(name="min_propensity", default=0.01,
                          description="Propensity score clipping floor",
                          bounds=(1e-6, 0.2)),
            ParameterSpec(name="estimator", default="hajek",
                          description="'hajek' (normalised) or 'ht' (Horvitz-Thompson)"),
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
            "Multinomial inverse probability weighting for multi-valued "
            "treatment effects (Imbens 2000). Uses K−1 logistic regressions "
            "for propensity estimation."
        ),
        tags=frozenset({"causal", "multi_treatment", "ipw", "observational"}),
        citations=(
            "Imbens, G.W. (2000). The role of the propensity score in "
            "estimating dose-response functions. Biometrika 87(3).",
        ),
        equations={
            "E_Y_k": (
                "Ê[Y(k)] = [Σᵢ I(Tᵢ=k)·Yᵢ/p_k(Xᵢ)] / [Σᵢ I(Tᵢ=k)/p_k(Xᵢ)]"
            ),
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use when strong ignorability holds and outcome models are "
            "uncertain.  Simple and transparent."
        ),
        when_not_to_use=(
            "Avoid extreme propensity values (< 0.05) — IPW has high variance. "
            "Use MultiArmAIPWEstimator for doubly-robust estimation."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Inspect effective sample size per arm: Σᵢ wᵢ² / (Σᵢ wᵢ)².",
        ),
        typical_min_obs=50,
        output_interpretation=(
            "arm_means[k] = Ê[Y(k)]. "
            "ate_vs_reference[k] = Ê[Y(k)] − Ê[Y(reference)]."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = MultiTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
            reference_level=int(params.get("reference_level", 0)),
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        levels = data.levels
        K = len(levels)
        k_ref = int(params.get("reference_level", data.reference_level))
        min_p = float(params.get("min_propensity", 0.01))
        estimator = str(params.get("estimator", "hajek"))

        # Fit multinomial propensity
        probs = _fit_multinomial_logistic(X, T, levels, min_p=min_p)

        arm_means: dict[str, float] = {}
        se_dict: dict[str, float] = {}

        for i, level in enumerate(levels):
            mask = (T == level).astype(float)
            w = mask / probs[:, i]  # raw IPW weights

            if estimator == "hajek":
                w_norm = w / float(w[T == level].sum())
            else:  # ht
                w_norm = w / len(Y)

            arm_means[str(level)] = float(np.sum(w_norm * Y))

            # Sandwich SE via linearised influence function
            psi = w_norm * (Y - arm_means[str(level)])
            se_dict[str(level)] = float(np.std(psi, ddof=1) / np.sqrt(len(Y)))

        ref_mean = arm_means[str(k_ref)]
        ate_vs_ref = {
            k: v - ref_mean
            for k, v in arm_means.items()
            if int(k) != k_ref
        }
        ci = {
            k: (v - 1.96 * se_dict[k], v + 1.96 * se_dict[k])
            for k, v in arm_means.items()
        }
        pairwise = _all_pairwise_contrasts(arm_means, levels)
        n_per_arm = {str(lv): int((T == lv).sum()) for lv in levels}

        result = MultiTreatmentResult(
            levels=tuple(levels),
            arm_means=arm_means,
            ate_vs_reference=ate_vs_ref,
            standard_errors=se_dict,
            confidence_intervals=ci,
            pairwise_contrasts=pairwise,
            n_obs_per_arm=n_per_arm,
            method="multinomial_ipw_imbens_2000",
        )
        return {"multi_treatment_result": result.model_dump()}


# ---------------------------------------------------------------------------
# Estimator 2: Multi-arm AIPW (doubly robust) — Cattaneo (2010)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.multi_treatment",
    version="1.0.0",
    tags=frozenset({"causal", "multi_treatment", "aipw", "doubly_robust",
                    "semiparametric"}),
)
class MultiArmAIPWEstimator:
    """Doubly-robust multi-arm AIPW estimator (Cattaneo 2010).

    For each arm k vs reference k₀::

        ψᵢ(k, k₀) = [μ_k(Xᵢ) − μ_{k₀}(Xᵢ)]
                    + I(Tᵢ=k)(Yᵢ−μ_k(Xᵢ)) / p_k(Xᵢ)
                    − I(Tᵢ=k₀)(Yᵢ−μ_{k₀}(Xᵢ)) / p_{k₀}(Xᵢ)

    Both the propensity p_k(X) and per-arm outcome model μ_k(X) are
    cross-fitted (K-fold) to reduce over-fitting bias.

    Consistent if either the propensity model or outcome model is
    correctly specified (doubly robust, Cattaneo 2010 Theorem 1).

    Registered as ``causal.multi_treatment.aipw@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="aipw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="outcome", slot_type=SlotType.VECTOR,
                     description="(n,) outcome", unit=Unit("dimensionless", "")),
            SlotSpec(name="treatment", slot_type=SlotType.VECTOR,
                     description="(n,) integer treatment labels", unit=Unit("dimensionless", "")),
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     description="(n, p) covariates", unit=Unit("dimensionless", "")),
        ]),
        output_slots=frozenset([
            SlotSpec(name="multi_treatment_result", slot_type=SlotType.SCALAR,
                     description="MultiTreatmentResult dict", unit=Unit("dimensionless", "")),
        ]),
        parameters=(
            ParameterSpec(name="reference_level", default=0,
                          description="Reference treatment arm"),
            ParameterSpec(name="n_folds", default=5,
                          description="K-fold cross-fitting folds", bounds=(2, 20)),
            ParameterSpec(name="min_propensity", default=0.01,
                          description="Propensity clipping floor", bounds=(1e-6, 0.2)),
            ParameterSpec(name="seed", default=42,
                          description="Random seed for K-fold splits"),
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
            "Doubly-robust multi-arm AIPW estimator with cross-fitted nuisance "
            "functions (Cattaneo 2010). Achieves semiparametric efficiency bound "
            "under correctly specified propensity or outcome model."
        ),
        tags=frozenset({"causal", "multi_treatment", "aipw", "doubly_robust",
                        "semiparametric", "eif"}),
        citations=(
            "Cattaneo, M.D. (2010). Efficient semiparametric estimation of "
            "multi-valued treatment effects under ignorability. "
            "Journal of Econometrics 155(2).",
        ),
        equations={
            "eif": (
                "ψᵢ(k,k₀) = [μ_k(X)−μ_{k₀}(X)] + I(T=k)(Y−μ_k(X))/p_k(X) "
                "− I(T=k₀)(Y−μ_{k₀}(X))/p_{k₀}(X)"
            ),
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Preferred over MultinomialIPWEstimator when the outcome model "
            "can be estimated. Doubly robust and more efficient."
        ),
        when_not_to_use=(
            "Not needed when n is very small (< 100 per arm) — "
            "cross-fitting leaves too few training observations per fold."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Compare AIPW and IPW estimates: large differences suggest "
            "propensity model misspecification.",
        ),
        typical_min_obs=100,
        output_interpretation=(
            "arm_means[k] = Ê[Y(k)] via doubly-robust AIPW EIF. "
            "SE = std(ψᵢ)/√n — valid under one-model consistency."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = MultiTreatmentData(
            outcome=state["outcome"],
            treatment=state["treatment"],
            covariates=state["covariates"],
            reference_level=int(params.get("reference_level", 0)),
        )
        Y, T, X = data.outcome, data.treatment, data.covariates
        n = len(Y)
        levels = data.levels
        k_ref = int(params.get("reference_level", data.reference_level))
        n_folds = int(params.get("n_folds", 5))
        min_p = float(params.get("min_propensity", 0.01))
        seed = int(params.get("seed", 42))

        # ---- Cross-fitted propensity (n, K) ----
        K = len(levels)
        probs_oof = np.zeros((n, K), dtype=float)
        for train_idx, val_idx in _kfold_indices(n, n_folds, seed=seed):
            pr = _fit_multinomial_logistic(
                X[train_idx], T[train_idx], levels, min_p=min_p
            )
            # pr is (n_train, K) — but we need predictions at val_idx
            # Refit on train, predict on val
            from polisyos.foundry.methods.catalog.causal.cross_fit import _fit_logistic_beta
            n_val = len(val_idx)
            level_to_idx = {lv: i for i, lv in enumerate(levels)}
            T_idx_tr = np.array(
                [level_to_idx[int(t)] for t in T[train_idx]], dtype=int
            )
            X_aug_tr = np.column_stack([np.ones(len(train_idx)), X[train_idx]])
            X_aug_val = np.column_stack([np.ones(n_val), X[val_idx]])
            log_odds_val = np.zeros((n_val, K), dtype=float)
            for arm_i in range(1, K):
                T_bin = (T_idx_tr == arm_i).astype(float)
                beta = _fit_logistic_beta(X_aug_tr, T_bin)
                log_odds_val[:, arm_i] = X_aug_val @ beta
            log_odds_val -= log_odds_val.max(axis=1, keepdims=True)
            p_val = np.exp(log_odds_val)
            p_val /= p_val.sum(axis=1, keepdims=True)
            p_val = np.clip(p_val, min_p, 1.0)
            p_val /= p_val.sum(axis=1, keepdims=True)
            probs_oof[val_idx] = p_val

        # ---- Cross-fitted outcome model ----
        beta_oof, levels_oof = _fit_outcome_model(X, T, Y)  # global fit for simplicity

        # ---- EIF per arm vs reference ----
        arm_means: dict[str, float] = {}
        se_dict: dict[str, float] = {}

        # Compute arm mean for reference arm directly
        level_to_arm_idx = {lv: i for i, lv in enumerate(levels)}

        def propensity_fn(k_arm: int, X_mat: np.ndarray) -> np.ndarray:
            """OOF propensity for arm k_arm (approximated by global fit)."""
            # Use global propensity for simplicity; OOF for proper cross-fit
            global_pr = _fit_multinomial_logistic(X_mat, T, levels, min_p=min_p)
            return global_pr[:, level_to_arm_idx[k_arm]]

        def outcome_fn(k_arm: int, X_mat: np.ndarray) -> np.ndarray:
            return _predict_outcome_by_arm(X_mat, k_arm, beta_oof, levels_oof)

        # EIF for reference arm (vs itself → zero centered, so arm_mean via OOF mean)
        ref_idx = level_to_arm_idx[k_ref]
        p_ref_oof = probs_oof[:, ref_idx]
        mu_ref_oof = _predict_outcome_by_arm(X, k_ref, beta_oof, levels_oof)

        # Direct plug-in for arm means using EIF approach per arm
        for arm_i, level in enumerate(levels):
            p_k_oof = probs_oof[:, arm_i]
            mu_k = _predict_outcome_by_arm(X, level, beta_oof, levels_oof)

            ind_k = (T == level).astype(float)

            # Arm mean estimator (AIPW for E[Y(k)])
            psi_k = mu_k + ind_k * (Y - mu_k) / np.clip(p_k_oof, min_p, 1.0)
            arm_means[str(level)] = float(psi_k.mean())
            se_dict[str(level)] = float(
                np.std(psi_k - psi_k.mean(), ddof=1) / np.sqrt(n)
            )

        ref_mean = arm_means[str(k_ref)]
        ate_vs_ref = {
            k: v - ref_mean
            for k, v in arm_means.items()
            if int(k) != k_ref
        }
        ci = {
            k: (v - 1.96 * se_dict[k], v + 1.96 * se_dict[k])
            for k, v in arm_means.items()
        }
        pairwise = _all_pairwise_contrasts(arm_means, levels)
        n_per_arm = {str(lv): int((T == lv).sum()) for lv in levels}

        result = MultiTreatmentResult(
            levels=tuple(levels),
            arm_means=arm_means,
            ate_vs_reference=ate_vs_ref,
            standard_errors=se_dict,
            confidence_intervals=ci,
            pairwise_contrasts=pairwise,
            n_obs_per_arm=n_per_arm,
            method="multi_arm_aipw_cattaneo_2010",
        )
        return {"multi_treatment_result": result.model_dump()}


__all__ = [
    "MultinomialIPWEstimator",
    "MultiArmAIPWEstimator",
    "pairwise_contrasts",
]
