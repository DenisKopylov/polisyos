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
from polisyos.foundry.methods.catalog.causal.tmle_core import (
    fit_aipw_ate,
    fit_tmle_ate,
    result_payload,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _treatment_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }
    )


def _logistic_propensity(X: np.ndarray, t: np.ndarray, max_iter: int = 50) -> np.ndarray:
    """Fit logistic regression for propensity scores."""
    n, k = X.shape
    X_aug = np.column_stack([np.ones(n), X])
    beta = np.zeros(X_aug.shape[1])
    for _ in range(max_iter):
        eta = np.clip(X_aug @ beta, -20, 20)
        p = 1.0 / (1.0 + np.exp(-eta))
        W = p * (1 - p)
        W = np.maximum(W, 1e-12)
        grad = X_aug.T @ (t - p)
        H = X_aug.T @ np.diag(W) @ X_aug
        try:
            delta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta += delta
        if np.max(np.abs(delta)) < 1e-8:
            break
    eta = np.clip(X_aug @ beta, -20, 20)
    return np.clip(1.0 / (1.0 + np.exp(-eta)), 0.01, 0.99)


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "aipw", "doubly-robust"},
)
class AIPWEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="aipw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="estimation_backend", default="custom"),
            ParameterSpec(name="direct_model_type", default="linear"),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Augmented Inverse Probability Weighting (AIPW) — doubly robust ATE estimator.",
        tags=frozenset({"causal", "treatment-effects", "aipw", "doubly-robust", "ate"}),
        citations=("Robins, J.M., Rotnitzky, A. & Zhao, L.P. (1994). Estimation of Regression Coefficients. JASA.",),
        equations={"aipw": "ATE = E[mu1(X) - mu0(X) + T*(Y-mu1(X))/e(X) - (1-T)*(Y-mu0(X))/(1-e(X))]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Observational study with binary treatment, rich covariate set, and strong overlap; want doubly-robust ATE/ATT",
        when_not_to_use="Weak overlap (propensity scores near 0 or 1); no valid outcome model or propensity model; <50 obs",
        prerequisites=(),
        diagnostic_checks=("causal.validation.overlap_check@1.0.0",),
        typical_min_obs=100,
        output_interpretation="ATE: Average Treatment Effect in full population. ATT: effect on treated units. Doubly robust: consistent if either outcome or propensity model is correct.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        fit_result, nuisance = fit_aipw_ate(X, T, Y, params)
        payload = result_payload(fit_result, nuisance)

        return {
            "result": {
                "ate": fit_result.ate,
                "standard_error": fit_result.standard_error,
                "t_statistic": fit_result.ate / max(fit_result.standard_error, 1e-12),
                "ci_lower": fit_result.ci_lower,
                "ci_upper": fit_result.ci_upper,
                "interval_method": fit_result.interval_method,
                "eif_mean": fit_result.eif_mean,
                "eif_standard_deviation": fit_result.eif_standard_deviation,
                "n_treated": int(np.sum(T > 0.5)),
                "n_control": int(np.sum(T <= 0.5)),
                "n_obs": int(len(Y)),
                "n_trimmed": int(np.sum(~nuisance.trim_mask)),
                **payload,
            }
        }


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "tmle"},
)
class TMLEEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tmle",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Targeted Maximum Likelihood Estimation for ATE with semiparametric efficiency.",
        tags=frozenset({"causal", "treatment-effects", "tmle", "semiparametric", "efficient"}),
        citations=("van der Laan, M.J. & Rose, S. (2011). Targeted Learning. Springer.",),
        equations={"tmle": "Update initial Q via clever covariate H(A,W) = A/g(W) - (1-A)/(1-g(W))"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Semiparametric efficient estimation of ATE; when Super Learner / ML for nuisance functions; targeted towards specific estimand",
        when_not_to_use="Very small samples (<100); when exact closed-form estimator is required; computational budget constraints",
        prerequisites=(),
        diagnostic_checks=("causal.validation.overlap_check@1.0.0",),
        typical_min_obs=200,
        output_interpretation="TMLE ATE: semiparametrically efficient, locally doubly-robust. CI based on efficient influence function.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        fit_result, nuisance = fit_tmle_ate(X, T, Y, params)
        payload = result_payload(fit_result, nuisance)

        return {
            "result": {
                "ate": fit_result.ate,
                "standard_error": fit_result.standard_error,
                "ci_lower": fit_result.ci_lower,
                "ci_upper": fit_result.ci_upper,
                "interval_method": fit_result.interval_method,
                "eif_mean": fit_result.eif_mean,
                "eif_standard_deviation": fit_result.eif_standard_deviation,
                "targeting_summary": fit_result.targeting_summary,
                "n_obs": int(len(Y)),
                "n_trimmed": int(np.sum(~nuisance.trim_mask)),
                **payload,
            }
        }


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "ipw"},
)
class IPWEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ipw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="trimming", default=0.01, bounds=(0.0, 0.2)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Inverse Probability Weighting (Horvitz-Thompson) for ATE estimation.",
        tags=frozenset({"causal", "treatment-effects", "ipw", "horvitz-thompson"}),
        citations=("Horvitz, D.G. & Thompson, D.J. (1952). A Generalization of Sampling. JASA.",),
        equations={"ipw": "ATE = E[T*Y/e(X)] - E[(1-T)*Y/(1-e(X))]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Observational study with known/estimable propensity score; weighting approach; ATE or ATT",
        when_not_to_use="Extreme propensity scores (near 0 or 1); no covariate overlap; propensity model severely misspecified",
        prerequisites=(),
        diagnostic_checks=("causal.validation.overlap_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation="IPW-ATE: reweights treated and control to represent target population. Sensitive to extreme weights.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        trim = float(params.get("trimming", 0.01))

        e = _logistic_propensity(X, T)
        e = np.clip(e, trim, 1.0 - trim)

        # Hajek (normalized) IPW
        w1 = T / e
        w0 = (1 - T) / (1 - e)

        ate_ht = float(np.mean(w1 * Y) - np.mean(w0 * Y))
        ate_hajek = float(np.sum(w1 * Y) / np.sum(w1) - np.sum(w0 * Y) / np.sum(w0))

        # SE via influence function
        psi = w1 * Y - w0 * Y - ate_ht
        se = float(np.std(psi) / np.sqrt(n))

        return {
            "result": {
                "ate_horvitz_thompson": ate_ht,
                "ate_hajek": ate_hajek,
                "standard_error": se,
                "ci_lower": ate_ht - 1.96 * se,
                "ci_upper": ate_ht + 1.96 * se,
                "effective_sample_size_treated": float(np.sum(w1) ** 2 / np.sum(w1 ** 2)),
                "effective_sample_size_control": float(np.sum(w0) ** 2 / np.sum(w0 ** 2)),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "propensity-matching"},
)
class PropensityScoreMatchingEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="propensity_matching",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_matches", default=1),
            ParameterSpec(name="caliper", default=0.2, bounds=(0.01, 1.0)),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Nearest-neighbor propensity score matching for ATE/ATT estimation.",
        tags=frozenset({"causal", "treatment-effects", "propensity-matching", "nearest-neighbor"}),
        citations=("Rosenbaum, P.R. & Rubin, D.B. (1983). The Central Role of the Propensity Score. Biometrika.",),
        equations={"psm": "Match treated i to control j minimizing |e(X_i) - e(X_j)|"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Observational study requiring matched comparison group; ATT estimation; when covariate balance is goal",
        when_not_to_use="Many binary/categorical covariates; high-dimensional covariate space; continuous treatment; <30 treated units",
        prerequisites=(),
        diagnostic_checks=("causal.validation.balance_check@1.0.0",),
        typical_min_obs=60,
        output_interpretation="ATT: Average Treatment Effect on the Treated. Check post-matching covariate balance (SMD < 0.1).",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        n_matches = int(params.get("n_matches", 1))
        caliper = float(params.get("caliper", 0.2))

        e = _logistic_propensity(X, T)
        ps_std = max(float(np.std(e)), 1e-6)
        caliper_abs = caliper * ps_std

        treated_idx = np.where(T > 0.5)[0]
        control_idx = np.where(T <= 0.5)[0]

        matched_diffs = []
        n_matched = 0

        for i in treated_idx:
            dists = np.abs(e[control_idx] - e[i])
            within_caliper = dists <= caliper_abs
            if not np.any(within_caliper):
                continue
            eligible = control_idx[within_caliper]
            eligible_dists = dists[within_caliper]
            k = min(n_matches, len(eligible))
            best_k = eligible[np.argsort(eligible_dists)[:k]]
            matched_diffs.append(Y[i] - float(np.mean(Y[best_k])))
            n_matched += 1

        if n_matched == 0:
            return {"result": {"att": 0.0, "n_matched": 0, "n_obs": n}}

        att = float(np.mean(matched_diffs))
        se = float(np.std(matched_diffs) / np.sqrt(n_matched))

        return {
            "result": {
                "att": att,
                "standard_error": se,
                "ci_lower": att - 1.96 * se,
                "ci_upper": att + 1.96 * se,
                "n_matched": n_matched,
                "n_unmatched": len(treated_idx) - n_matched,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "entropy-balancing"},
)
class EntropyBalancingEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="entropy_balancing",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=200),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Entropy balancing weights for exact covariate balance in causal inference.",
        tags=frozenset({"causal", "treatment-effects", "entropy-balancing", "reweighting"}),
        citations=("Hainmueller, J. (2012). Entropy Balancing for Causal Effects. Political Analysis.",),
        equations={"ebal": "min KL(w, q) s.t. sum(w_i * X_i) = X_bar_treated for control units"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Observational study; want exact covariate balance up to specified moments without discarding observations",
        when_not_to_use="Very small control group (relative to treated); many continuous covariates requiring high-order moment matching",
        prerequisites=(),
        diagnostic_checks=("causal.validation.balance_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation="ATT with entropy-balanced weights. Weights minimize KL-divergence subject to exact moment constraints.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        max_iter = int(params.get("max_iter", 200))

        treated = T > 0.5
        control = ~treated
        n_t = int(np.sum(treated))
        n_c = int(np.sum(control))

        X_t = X[treated]
        X_c = X[control]
        target_means = np.mean(X_t, axis=0)

        # Initialize uniform weights
        lam = np.zeros(X.shape[1])
        base_w = np.ones(n_c) / n_c

        for _ in range(max_iter):
            # Exponential tilting
            w = base_w * np.exp(X_c @ lam)
            w /= np.sum(w)

            # Moment condition
            achieved = X_c.T @ w
            gap = achieved - target_means

            if np.max(np.abs(gap)) < 1e-6:
                break

            # Newton update
            H = X_c.T @ np.diag(w) @ X_c
            try:
                delta = np.linalg.solve(H, gap)
            except np.linalg.LinAlgError:
                break
            lam -= delta

        # Final weights
        w_final = base_w * np.exp(X_c @ lam)
        w_final /= np.sum(w_final)

        # ATT
        y_t_mean = float(np.mean(Y[treated]))
        y_c_weighted = float(np.sum(w_final * Y[control]))
        att = y_t_mean - y_c_weighted

        # Balance check
        balanced_means = X_c.T @ w_final
        max_imbalance = float(np.max(np.abs(balanced_means - target_means)))

        return {
            "result": {
                "att": att,
                "y_treated_mean": y_t_mean,
                "y_control_weighted": y_c_weighted,
                "max_covariate_imbalance": max_imbalance,
                "effective_sample_size": float(1.0 / np.sum(w_final ** 2)),
                "n_treated": n_t,
                "n_control": n_c,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.treatment_effects",
    version="1.0.0",
    tags={"causal", "treatment-effects", "cbps"},
)
class CBPSEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="cbps",
        namespace="placeholder",
        version="0.0.0",
        input_slots=_treatment_slots(),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="max_iter", default=100),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Covariate Balancing Propensity Score: propensity model optimized for balance.",
        tags=frozenset({"causal", "treatment-effects", "cbps", "covariate-balance"}),
        citations=("Imai, K. & Ratkovic, M. (2014). Covariate Balancing Propensity Score. JRSS-B.",),
        equations={"cbps": "Solve E[X*(T - e(X;beta))] = 0 (score) and E[X*(T/e - (1-T)/(1-e))] = 0 (balance)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Observational study where propensity score model may be misspecified; want covariate balance by construction",
        when_not_to_use="Treatment mechanism well-known and simple; very large datasets where CBPS optimization is slow",
        prerequisites=(),
        diagnostic_checks=("causal.validation.balance_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation="ATE/ATT via covariate balancing propensity score. More robust to propensity misspecification than standard IPW.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n, k = X.shape
        max_iter = int(params.get("max_iter", 100))

        X_aug = np.column_stack([np.ones(n), X])
        p_dim = X_aug.shape[1]
        beta = np.zeros(p_dim)

        for _ in range(max_iter):
            eta = np.clip(X_aug @ beta, -20, 20)
            e = 1.0 / (1.0 + np.exp(-eta))
            e = np.clip(e, 0.01, 0.99)

            # Combined score + balance moment conditions
            score = X_aug.T @ (T - e) / n
            w1 = T / e
            w0 = (1 - T) / (1 - e)
            balance = X_aug.T @ (w1 - w0) / n

            g = np.concatenate([score, balance])

            # Jacobian
            W = e * (1 - e)
            J_score = -X_aug.T @ np.diag(W) @ X_aug / n
            dw1 = -T * W / (e ** 2)
            dw0 = -(1 - T) * W / ((1 - e) ** 2)
            J_balance = X_aug.T @ np.diag(dw1 - dw0) @ X_aug / n
            J = np.vstack([J_score, J_balance])

            # GMM-style update
            try:
                delta = np.linalg.lstsq(J, g, rcond=None)[0]
            except np.linalg.LinAlgError:
                break
            beta -= delta
            if np.max(np.abs(delta)) < 1e-8:
                break

        eta = np.clip(X_aug @ beta, -20, 20)
        e_final = np.clip(1.0 / (1.0 + np.exp(-eta)), 0.01, 0.99)

        # IPW with CBPS weights
        w1 = T / e_final
        w0 = (1 - T) / (1 - e_final)
        ate = float(np.sum(w1 * Y) / np.sum(w1) - np.sum(w0 * Y) / np.sum(w0))

        # Balance diagnostics
        std_diffs = []
        for j in range(k):
            mean_t = float(np.sum(w1 * X[:, j]) / np.sum(w1))
            mean_c = float(np.sum(w0 * X[:, j]) / np.sum(w0))
            pooled_sd = max(float(np.std(X[:, j])), 1e-6)
            std_diffs.append(abs(mean_t - mean_c) / pooled_sd)

        return {
            "result": {
                "ate": ate,
                "max_standardized_diff": max(std_diffs) if std_diffs else 0.0,
                "mean_standardized_diff": float(np.mean(std_diffs)) if std_diffs else 0.0,
                "n_obs": n,
            }
        }


__all__ = [
    "AIPWEstimator",
    "CBPSEstimator",
    "EntropyBalancingEstimator",
    "IPWEstimator",
    "PropensityScoreMatchingEstimator",
    "TMLEEstimator",
]
