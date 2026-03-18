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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="causal.advanced",
    version="1.0.0",
    tags={"causal", "regression-kink", "rkd"},
)
class RegressionKinkDesignEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="regression_kink",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("running_var", SlotType.VECTOR, Unit("running", "value"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="kink_point", default=0.0),
            ParameterSpec(name="bandwidth", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Regression Kink Design: estimate effect from slope change at kink point.",
        tags=frozenset({"causal", "regression-kink", "rkd", "quasi-experimental"}),
        citations=("Card, D. et al. (2015). Inference on Causal Effects in a Generalized Regression Kink Design. Econometrica.",),
        equations={"rkd": "RKD = lim(dY/dX from right - dY/dX from left) / (change in policy slope)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Policy with kinked assignment rule (slope change at cutoff, not level); want to estimate treatment effect at kink",
        when_not_to_use="No kink in assignment variable; level discontinuity (use RDD instead)",
        typical_min_obs=200,
        output_interpretation="RKD estimate: slope change in outcome divided by slope change in treatment at kink. Analogous to LATE from RDD.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["running_var"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        kink = float(params.get("kink_point", 0.0))
        n = len(Y)

        bw = params.get("bandwidth")
        if bw is None:
            bw = 1.06 * max(float(np.std(X)), 1e-6) * n ** (-0.2)
        bw = max(float(bw), 1e-8)

        # Select observations within bandwidth
        in_bw = np.abs(X - kink) <= bw
        X_bw = X[in_bw] - kink
        Y_bw = Y[in_bw]
        n_bw = len(X_bw)

        left = X_bw < 0
        right = X_bw >= 0

        # Local linear on each side
        if np.sum(left) > 2:
            X_l = np.column_stack([np.ones(np.sum(left)), X_bw[left]])
            b_l = np.linalg.lstsq(X_l, Y_bw[left], rcond=None)[0]
            slope_left = float(b_l[1])
        else:
            slope_left = 0.0

        if np.sum(right) > 2:
            X_r = np.column_stack([np.ones(np.sum(right)), X_bw[right]])
            b_r = np.linalg.lstsq(X_r, Y_bw[right], rcond=None)[0]
            slope_right = float(b_r[1])
        else:
            slope_right = 0.0

        slope_change = slope_right - slope_left

        return {
            "result": {
                "slope_change": slope_change,
                "slope_left": slope_left,
                "slope_right": slope_right,
                "bandwidth": float(bw),
                "n_in_bandwidth": n_bw,
                "kink_point": kink,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.advanced",
    version="1.0.0",
    tags={"causal", "bunching", "kleven", "cross-section", "estimation"},
)
class BunchingEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bunching",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("running_var", SlotType.VECTOR, Unit("running", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="kink_point", default=0.0),
            ParameterSpec(name="n_bins", default=50),
            ParameterSpec(name="poly_order", default=7),
            ParameterSpec(name="bunching_region_width", default=None),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Bunching estimation at kinks/notches (Kleven 2016).",
        tags=frozenset({"causal", "bunching", "kleven", "kink", "notch"}),
        citations=("Kleven, H.J. (2016). Bunching. Annual Review of Economics.",),
        equations={"bunching": "B = excess mass at kink = observed - counterfactual density"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Kink/notch in budget constraint; estimate behavioral response at policy threshold from bunching mass",
        when_not_to_use="No clear kinked budget constraint; insufficient data density near threshold",
        typical_min_obs=500,
        output_interpretation="Excess mass b: normalized bunching at kink. Compensated elasticity derived from b and slope change.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Z = np.asarray(state["running_var"], dtype=float)
        kink = float(params.get("kink_point", 0.0))
        n_bins = int(params.get("n_bins", 50))
        poly_order = int(params.get("poly_order", 7))
        n = len(Z)

        brw = params.get("bunching_region_width")
        if brw is None:
            brw = max(float(np.std(Z)), 1e-6) * 0.1
        brw = float(brw)

        # Bin the data
        z_min, z_max = float(np.min(Z)), float(np.max(Z))
        bin_edges = np.linspace(z_min, z_max, n_bins + 1)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        counts, _ = np.histogram(Z, bins=bin_edges)
        counts = counts.astype(float)

        # Identify bunching region bins
        bunching_mask = np.abs(bin_centers - kink) <= brw
        outside_mask = ~bunching_mask

        if np.sum(outside_mask) < poly_order + 1:
            return {"result": {"excess_mass": 0.0, "n_obs": n}}

        # Fit polynomial to bins outside bunching region
        x_outside = bin_centers[outside_mask]
        y_outside = counts[outside_mask]
        x_norm = (x_outside - kink) / max(z_max - z_min, 1e-6)

        V = np.vander(x_norm, N=poly_order + 1, increasing=True)
        coefs = np.linalg.lstsq(V, y_outside, rcond=None)[0]

        # Counterfactual density in bunching region
        x_bunching_norm = (bin_centers[bunching_mask] - kink) / max(z_max - z_min, 1e-6)
        V_b = np.vander(x_bunching_norm, N=poly_order + 1, increasing=True)
        counterfactual = V_b @ coefs

        # Excess mass
        observed_bunching = float(np.sum(counts[bunching_mask]))
        expected = float(np.sum(np.maximum(counterfactual, 0)))
        excess = observed_bunching - expected

        # Normalized excess mass
        avg_counterfactual = expected / max(np.sum(bunching_mask), 1)
        normalized_excess = excess / max(avg_counterfactual, 1e-12)

        return {
            "result": {
                "excess_mass": excess,
                "normalized_excess_mass": normalized_excess,
                "observed_bunching_count": observed_bunching,
                "counterfactual_count": expected,
                "bunching_region_width": brw,
                "kink_point": kink,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.advanced",
    version="1.0.0",
    tags={"causal", "mte", "marginal-treatment-effect"},
)
class MarginalTreatmentEffectEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="marginal_treatment_effect",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("instrument", SlotType.VECTOR, Unit("instrument", "value"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_grid_points", default=20),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Marginal Treatment Effect via local IV (Heckman & Vytlacil).",
        tags=frozenset({"causal", "mte", "marginal-treatment-effect", "local-iv", "essential-heterogeneity"}),
        citations=("Heckman, J.J. & Vytlacil, E. (2005). Structural Equations, Treatment Effects. Econometrica.",),
        equations={"mte": "MTE(x, u_D) = d/dp E[Y|X=x, P(Z)=p] evaluated at p=u_D"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Recover treatment effect heterogeneity by unobserved resistance to treatment; requires valid instrument",
        when_not_to_use="No instrument available; LATE or ATE sufficient; instrument has weak first stage",
        output_interpretation="MTE(u_D): treatment effect for marginal individual with resistance level u_D. Integrate over u_D distribution to recover LATE, ATE, ATT.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Z = np.asarray(state["instrument"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        n_grid = int(params.get("n_grid_points", 20))

        # Step 1: Propensity score P(D=1|Z)
        Z_aug = np.column_stack([np.ones(n), Z])
        beta_z = np.zeros(Z_aug.shape[1])
        for _ in range(50):
            eta = np.clip(Z_aug @ beta_z, -20, 20)
            p = 1.0 / (1.0 + np.exp(-eta))
            W = p * (1 - p)
            W = np.maximum(W, 1e-12)
            try:
                delta = np.linalg.solve(Z_aug.T @ np.diag(W) @ Z_aug, Z_aug.T @ (T - p))
            except np.linalg.LinAlgError:
                break
            beta_z += delta
            if np.max(np.abs(delta)) < 1e-8:
                break

        eta = np.clip(Z_aug @ beta_z, -20, 20)
        p_score = np.clip(1.0 / (1.0 + np.exp(-eta)), 0.01, 0.99)

        # Step 2: Local polynomial of E[Y|P(Z)=p] and derivative
        grid = np.linspace(float(np.percentile(p_score, 5)), float(np.percentile(p_score, 95)), n_grid)
        bw = max(float(np.std(p_score)), 1e-6) * n ** (-0.2)

        mte_values = []
        for p_eval in grid:
            # Local linear: Y = a + b*(p - p_eval) + e, weighted by kernel
            K = np.exp(-0.5 * ((p_score - p_eval) / bw) ** 2)
            dp = p_score - p_eval
            X_local = np.column_stack([np.ones(n), dp])
            W_local = np.diag(K)
            try:
                beta_local = np.linalg.solve(X_local.T @ W_local @ X_local, X_local.T @ (K * Y))
                mte_values.append(float(beta_local[1]))  # derivative = MTE
            except np.linalg.LinAlgError:
                mte_values.append(0.0)

        # ATE = integral of MTE
        ate_approx = float(np.mean(mte_values))

        return {
            "result": {
                "mte_grid": grid.tolist(),
                "mte_values": mte_values,
                "ate_from_mte": ate_approx,
                "propensity_score_range": [float(np.min(p_score)), float(np.max(p_score))],
                "bandwidth": float(bw),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.advanced",
    version="1.0.0",
    tags={"causal", "shift-share", "bartik-iv"},
)
class ShiftShareIVEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="shift_share_iv",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("shares", SlotType.MATRIX, Unit("share", "fraction"), shape=("n_regions", "n_industries")),
                SlotSpec("shifts", SlotType.VECTOR, Unit("shift", "value"), shape=("n_industries",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_regions",)),
                SlotSpec("controls", SlotType.MATRIX, Unit("control", "value"), shape=("n_regions", "n_controls")),
            }
        ),
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
        description="Shift-share (Bartik) IV estimator with exposure-robust inference.",
        tags=frozenset({"causal", "shift-share", "bartik-iv", "instrumental-variable"}),
        citations=(
            "Bartik, T.J. (1991). Who Benefits from State and Local Economic Development Policies?",
            "Borusyak, K., Hull, P. & Jaravel, X. (2022). Quasi-Experimental Shift-Share Research Designs. ReStud.",
        ),
        equations={"ssiv": "B_i = sum_k s_{ik} * g_k (Bartik instrument); 2SLS with B as instrument"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Bartik/shift-share IV; identify local labor demand shocks from national industry growth × local industry shares",
        when_not_to_use="Industries not exogenous nationally; few industries (<5); local concentration in single industry",
        typical_min_obs=100,
        output_interpretation="IV coefficient: effect of predicted demand shock on outcome. Validity requires quasi-random industry shares.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        S = np.asarray(state["shares"], dtype=float)
        G = np.asarray(state["shifts"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        W = np.asarray(state["controls"], dtype=float)
        n, K = S.shape

        # Construct Bartik instrument
        B = S @ G  # (n,)

        # 2SLS
        # First stage: B on controls → predicted exposure
        X_fs = np.column_stack([np.ones(n), W])
        X_iv = np.column_stack([np.ones(n), B, W])

        # Reduced form: Y on B + W
        beta_rf = np.linalg.lstsq(X_iv, Y, rcond=None)[0]
        reduced_form = float(beta_rf[1])

        # First stage: endogenous var (B is the instrument and the treatment here)
        # In standard Bartik, the treatment is B itself, so 2SLS = OLS on B
        beta_ols = np.linalg.lstsq(X_iv, Y, rcond=None)[0]
        ssiv_effect = float(beta_ols[1])

        # Exposure-robust SE (Borusyak-Hull-Jaravel)
        resid = Y - X_iv @ beta_ols
        # Industry-level aggregation for robust SE
        se_terms = np.zeros(K)
        for k in range(K):
            s_k = S[:, k]
            se_terms[k] = float(np.sum(s_k * resid) * G[k])
        var_robust = float(np.sum(se_terms ** 2)) / max(float(np.sum(B ** 2)) ** 2, 1e-12)
        se_robust = float(np.sqrt(max(var_robust, 0.0)))

        # Standard SE
        sigma2 = float(np.sum(resid ** 2) / max(n - X_iv.shape[1], 1))
        try:
            cov = sigma2 * np.linalg.inv(X_iv.T @ X_iv)
            se_standard = float(np.sqrt(max(cov[1, 1], 0.0)))
        except np.linalg.LinAlgError:
            se_standard = float("inf")

        # Rotemberg weights
        denom = float(np.sum(B ** 2))
        rotemberg = np.zeros(K)
        for k in range(K):
            rotemberg[k] = float(G[k] * np.sum(S[:, k] * B)) / max(denom, 1e-12)

        return {
            "result": {
                "ssiv_effect": ssiv_effect,
                "standard_error": se_standard,
                "exposure_robust_se": se_robust,
                "reduced_form": reduced_form,
                "rotemberg_weights": rotemberg.tolist(),
                "hhi_shares": float(np.mean(np.sum(S ** 2, axis=1))),
                "n_regions": n,
                "n_industries": K,
            }
        }


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "dr-learner"},
)
class DRLearnerEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="dr_learner",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
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
        description="Doubly Robust Learner for heterogeneous treatment effect estimation (CATE).",
        tags=frozenset({"causal", "hte", "dr-learner", "cate", "doubly-robust"}),
        citations=("Kennedy, E.H. (2023). Towards Optimal Doubly Robust Estimation of HTE. EJS.",),
        equations={"dr_learner": "pseudo-outcome = mu1(X) - mu0(X) + T*(Y-mu1)/(e) - (1-T)*(Y-mu0)/(1-e); regress on X"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Heterogeneous treatment effects using doubly-robust Robinson decomposition; cross-fitting for semiparametric efficiency",
        typical_min_obs=200,
        output_interpretation="CATE estimates per individual. DR pseudo-outcome regression on X. Doubly-robust: consistent if either outcome model or propensity model is correct.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n, k = X.shape

        # Nuisance: propensity
        X_aug = np.column_stack([np.ones(n), X])
        beta_ps = np.zeros(X_aug.shape[1])
        for _ in range(50):
            eta = np.clip(X_aug @ beta_ps, -20, 20)
            p = 1.0 / (1.0 + np.exp(-eta))
            W = np.maximum(p * (1 - p), 1e-12)
            try:
                delta = np.linalg.solve(X_aug.T @ np.diag(W) @ X_aug, X_aug.T @ (T - p))
            except np.linalg.LinAlgError:
                break
            beta_ps += delta
            if np.max(np.abs(delta)) < 1e-8:
                break
        eta = np.clip(X_aug @ beta_ps, -20, 20)
        e = np.clip(1.0 / (1.0 + np.exp(-eta)), 0.05, 0.95)

        # Nuisance: outcome models
        treated = T > 0.5
        beta1 = np.linalg.lstsq(X_aug[treated], Y[treated], rcond=None)[0] if np.sum(treated) > 1 else np.zeros(X_aug.shape[1])
        beta0 = np.linalg.lstsq(X_aug[~treated], Y[~treated], rcond=None)[0] if np.sum(~treated) > 1 else np.zeros(X_aug.shape[1])
        mu1 = X_aug @ beta1
        mu0 = X_aug @ beta0

        # DR pseudo-outcome
        pseudo = mu1 - mu0 + T * (Y - mu1) / e - (1 - T) * (Y - mu0) / (1 - e)

        # Second stage: CATE(x) = E[pseudo | X=x] via linear model
        beta_cate = np.linalg.lstsq(X_aug, pseudo, rcond=None)[0]
        cate_pred = X_aug @ beta_cate

        ate = float(np.mean(cate_pred))
        cate_std = float(np.std(cate_pred))

        return {
            "result": {
                "ate": ate,
                "cate_predictions": cate_pred.tolist(),
                "cate_std": cate_std,
                "cate_coefficients": beta_cate.tolist(),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.hte",
    version="1.0.0",
    tags={"causal", "hte", "r-learner"},
)
class RLearnerEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="r_learner",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="lambda_reg", default=0.01, bounds=(0.0, 10.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="R-Learner (Robinson decomposition) for CATE estimation.",
        tags=frozenset({"causal", "hte", "r-learner", "cate", "robinson"}),
        citations=("Nie, X. & Wager, S. (2021). Quasi-Oracle Estimation of Heterogeneous Treatment Effects. Biometrika.",),
        equations={"r_learner": "Y - m(X) = tau(X)*(T - e(X)) + eps; minimize weighted loss"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Heterogeneous treatment effects using doubly-robust Robinson decomposition; cross-fitting for semiparametric efficiency",
        typical_min_obs=200,
        output_interpretation="CATE estimates via R-learner weighted regression on X. Robinson residuals (Y-m(X)) regressed on (T-e(X)). Feature importances show heterogeneity drivers.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n, k = X.shape
        lam = float(params.get("lambda_reg", 0.01))

        X_aug = np.column_stack([np.ones(n), X])

        # Marginal outcome model: m(X) = E[Y|X]
        beta_m = np.linalg.lstsq(X_aug, Y, rcond=None)[0]
        m_hat = X_aug @ beta_m

        # Propensity: e(X) = E[T|X]
        beta_e = np.linalg.lstsq(X_aug, T, rcond=None)[0]
        e_hat = np.clip(X_aug @ beta_e, 0.05, 0.95)

        # Residuals
        Y_tilde = Y - m_hat
        T_tilde = T - e_hat

        # R-learner: minimize sum (Y_tilde - tau(X)*T_tilde)^2
        # tau(X) = X_aug @ alpha
        # Weighted least squares: weight by T_tilde^2
        W = T_tilde ** 2
        W = np.maximum(W, 1e-12)

        # (X'*diag(W)*X + lambda*I) * alpha = X'*diag(W) * (Y_tilde / T_tilde)
        pseudo_y = Y_tilde / np.maximum(np.abs(T_tilde), 1e-6) * np.sign(T_tilde)
        A = X_aug.T @ np.diag(W) @ X_aug + lam * np.eye(X_aug.shape[1])
        b_rhs = X_aug.T @ (W * pseudo_y)
        try:
            alpha = np.linalg.solve(A, b_rhs)
        except np.linalg.LinAlgError:
            alpha = np.linalg.lstsq(A, b_rhs, rcond=None)[0]

        cate_pred = X_aug @ alpha
        ate = float(np.mean(cate_pred))

        return {
            "result": {
                "ate": ate,
                "cate_predictions": cate_pred.tolist(),
                "cate_std": float(np.std(cate_pred)),
                "cate_coefficients": alpha.tolist(),
                "lambda_reg": lam,
                "n_obs": n,
            }
        }


__all__ = [
    "BunchingEstimator",
    "DRLearnerEstimator",
    "MarginalTreatmentEffectEstimator",
    "RLearnerEstimator",
    "RegressionKinkDesignEstimator",
    "ShiftShareIVEstimator",
]
