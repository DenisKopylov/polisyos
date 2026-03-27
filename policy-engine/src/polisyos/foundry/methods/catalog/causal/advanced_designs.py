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
from polisyos.foundry.methods.catalog.causal.nuisance_layer import (
    CrossFitNuisanceOutputs,
    bootstrap_mean_interval,
    build_nuisance_config,
    crossfit_nuisances,
    fit_dr_tau_model,
    fit_r_tau_model,
)
from polisyos.foundry.methods.catalog.causal.tmle_core import (
    ATENuisanceBundle,
    ATENuisanceContract,
    fit_crossfit_nuisance_bundle,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


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


def _suppress_importances_if_homogeneous(
    cate_pred: np.ndarray,
    importances: list[dict[str, Any]] | None,
    *,
    threshold: float = 1e-8,
) -> list[dict[str, Any]]:
    cate_arr = np.asarray(cate_pred, dtype=float).ravel()
    if cate_arr.size == 0 or float(np.nanstd(cate_arr)) <= threshold:
        return []
    if not importances:
        return []
    total = float(np.sum([float(item.get("importance_score", 0.0)) for item in importances]))
    if total <= threshold:
        return []
    return importances


def _coerce_shared_nuisance(
    bundle: ATENuisanceBundle,
    *,
    params: Mapping[str, Any],
) -> CrossFitNuisanceOutputs:
    config = build_nuisance_config(dict(params))
    diagnostics = bundle.diagnostics()
    return CrossFitNuisanceOutputs(
        propensity=np.asarray(bundle.propensity, dtype=float),
        mu1=np.asarray(bundle.mu1, dtype=float),
        mu0=np.asarray(bundle.mu0, dtype=float),
        trim_mask=np.asarray(bundle.trim_mask, dtype=bool),
        scaler=bundle.scaler,
        config=config,
        split_manifest=None,
        backend_info={
            "propensity_backend": next(iter(bundle.propensity_backends), None),
            "outcome_backend": next(iter(bundle.outcome_backends), None),
            "calibration_mode": next(iter(bundle.calibration_modes), None),
            "effective_sample_size": diagnostics.get("effective_sample_size"),
        },
    )


def _resolve_nuisance_outputs(
    X: np.ndarray,
    T: np.ndarray,
    Y: np.ndarray,
    *,
    params: Mapping[str, Any],
) -> CrossFitNuisanceOutputs:
    shared = params.get("__shared_nuisance_bundle")
    if isinstance(shared, ATENuisanceBundle):
        return _coerce_shared_nuisance(shared, params=params)

    try:
        contract = ATENuisanceContract.from_params(params)
        bundle = fit_crossfit_nuisance_bundle(X, T, Y, contract, params)
        return _coerce_shared_nuisance(bundle, params=params)
    except Exception:
        config = build_nuisance_config(dict(params))
        return crossfit_nuisances(X, T, Y, config)


def _truncate_pseudo_outcome(
    pseudo: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    sigma_multiple: float = 5.0,
) -> np.ndarray:
    arr = np.asarray(pseudo, dtype=float).reshape(-1)
    clipped = np.array(arr, copy=True)
    valid_mask = np.isfinite(arr)
    if mask is not None:
        valid_mask &= np.asarray(mask, dtype=bool).reshape(-1)
    if not np.any(valid_mask):
        return clipped
    center = float(np.mean(arr[valid_mask]))
    scale = float(np.std(arr[valid_mask]))
    if not np.isfinite(scale) or scale <= 1e-8:
        return clipped
    half_width = max(float(sigma_multiple) * scale, 1e-6)
    return np.clip(clipped, center - half_width, center + half_width)


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
        parameters=(
            ParameterSpec(name="estimation_backend", default="custom"),
            ParameterSpec(name="nuisance_model_family", default="competitive"),
            ParameterSpec(name="crossfit_folds", default=5),
            ParameterSpec(name="n_repeats", default=3),
            ParameterSpec(name="propensity_clipping", default=0.01),
            ParameterSpec(name="propensity_trimming", default=0.02),
            ParameterSpec(name="overlap_trim", default=0.02),
            ParameterSpec(name="outcome_scaling", default="raw+standardized"),
            ParameterSpec(name="bootstrap_draws", default=100),
            ParameterSpec(name="random_seed", default=None),
            ParameterSpec(name="random_seed_manifest", default=()),
            ParameterSpec(name="feature_importance_mode", default="permutation"),
        ),
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
        parameters=(
            ParameterSpec(name="nuisance_model_family", default="competitive"),
            ParameterSpec(name="crossfit_folds", default=5),
            ParameterSpec(name="n_repeats", default=3),
            ParameterSpec(name="propensity_clipping", default=0.01),
            ParameterSpec(name="propensity_trimming", default=0.02),
            ParameterSpec(name="overlap_trim", default=0.02),
            ParameterSpec(name="outcome_scaling", default="raw+standardized"),
            ParameterSpec(name="bootstrap_draws", default=100),
            ParameterSpec(name="random_seed", default=None),
            ParameterSpec(name="random_seed_manifest", default=()),
            ParameterSpec(name="feature_importance_mode", default="permutation"),
        ),
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
        n, _k = X.shape
        estimation_backend = str(params.get("estimation_backend", "custom")).strip().lower()
        if estimation_backend in {"econml", "econml_direct"}:
            from polisyos.foundry.methods.catalog.causal.forest_dr import ForestDRLearnerEstimator

            # Adapt forest parameters to sample size to avoid degenerate fits
            # on small DGPs that would otherwise produce N/A results.
            n_est_default = min(int(params.get("n_estimators", 160)), max(20, n // 10))
            min_leaf_default = max(5, min(int(params.get("min_samples_leaf", 20)), n // 20))
            delegate_params = {
                "n_estimators": n_est_default,
                "min_samples_leaf": min_leaf_default,
                "max_depth": params.get("max_depth"),
                "max_samples": float(params.get("max_samples", 0.45)),
                "honest": bool(params.get("honest", True)),
                "subforest_size": int(params.get("subforest_size", 4)),
                "min_propensity": float(params.get("propensity_clipping", 0.025)),
                "cv_folds": int(params.get("crossfit_folds", 3)),
                "mc_iters": int(params.get("mc_iters", 1)),
                "confidence_level": float(params.get("confidence_level", 0.95)),
                "feature_importance_method": "tree_based",
                "random_state": int(params.get("random_seed", params.get("__seed__", 0)) or 0),
            }
            delegated = ForestDRLearnerEstimator.pure_step(
                {
                    "outcome": Y,
                    "treatment": T,
                    "covariates": X,
                },
                delegate_params,
            )
            if getattr(delegated.get("report"), "point_estimate", None) is not None:
                return delegated
        effective_params = dict(params)
        effective_params.setdefault("nuisance_model_family", "competitive")
        effective_params.setdefault("crossfit_folds", 5)
        effective_params.setdefault("n_repeats", 3)
        effective_params.setdefault("propensity_clipping", 0.01)
        effective_params.setdefault("propensity_trimming", 0.02)
        effective_params.setdefault("overlap_trim", 0.02)
        effective_params.setdefault("outcome_scaling", "raw+standardized")
        effective_params.setdefault("bootstrap_draws", 100)
        effective_params.setdefault("feature_importance_mode", "permutation")
        try:
            config = build_nuisance_config(effective_params)
            nuisance = _resolve_nuisance_outputs(X, T, Y, params=effective_params)
            pseudo = _truncate_pseudo_outcome(
                nuisance.aipw_scores(Y, T),
                mask=nuisance.trim_mask,
            )
            valid_pseudo = pseudo[np.isfinite(pseudo)]
            if valid_pseudo.size < 10:
                raise ValueError(
                    f"DRLearner: only {valid_pseudo.size} finite pseudo-outcomes "
                    f"out of {pseudo.size} total"
                )
            tau_fit = fit_dr_tau_model(X, pseudo, config)
            cate_pred = tau_fit.cate_predictions
            feature_importances = tau_fit.feature_importances

            ate = float(np.mean(cate_pred[nuisance.trim_mask]))
            cate_std = float(np.std(cate_pred[nuisance.trim_mask]))
            ci_lower, ci_upper = bootstrap_mean_interval(
                pseudo[nuisance.trim_mask],
                seed=config.random_seed + 71,
                draws=config.bootstrap_draws,
            )
            feature_importance_payload = _suppress_importances_if_homogeneous(
                cate_pred,
                _feature_importances_from_array(
                    feature_importances if feature_importances is not None else np.array([]),
                    [f"x{i}" for i in range(X.shape[1])],
                    method="permutation" if config.feature_importance_mode == "permutation" else "model_based",
                ),
            )

            return {
                "result": {
                    "ate": ate,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                    "cate_predictions": cate_pred.tolist(),
                    "cate_std": cate_std,
                    "feature_importances": feature_importance_payload,
                    "n_obs": n,
                    "nuisance_diagnostics": nuisance.diagnostics(),
                    "nuisance_config": {
                        "nuisance_model_family": config.nuisance_model_family,
                        "crossfit_folds": config.crossfit_folds,
                        "n_repeats": config.n_repeats,
                        "random_seed_manifest": list(config.random_seed_manifest),
                        "propensity_clipping": config.propensity_clipping,
                        "propensity_trimming": config.propensity_trimming,
                        "outcome_scaling": config.outcome_scaling,
                        "inference_backend": config.inference_backend,
                        "bootstrap_draws": config.bootstrap_draws,
                        "feature_importance_mode": config.feature_importance_mode,
                    },
                    "heterogeneity_signal": float(np.std(cate_pred, ddof=1)) if cate_pred.size > 1 else 0.0,
                }
            }
        except Exception as exc:
            return {
                "result": {
                    "ate": float("nan"),
                    "ci_lower": float("nan"),
                    "ci_upper": float("nan"),
                    "cate_predictions": [],
                    "cate_std": float("nan"),
                    "feature_importances": {},
                    "n_obs": n,
                    "nuisance_diagnostics": {},
                    "nuisance_config": {},
                    "heterogeneity_signal": 0.0,
                    "failed": True,
                    "fail_reason": f"DRLearner custom backend: {exc}",
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
            ParameterSpec(name="estimation_backend", default="custom"),
            ParameterSpec(name="nuisance_model_family", default="competitive"),
            ParameterSpec(name="crossfit_folds", default=5),
            ParameterSpec(name="n_repeats", default=3),
            ParameterSpec(name="propensity_clipping", default=0.01),
            ParameterSpec(name="propensity_trimming", default=0.02),
            ParameterSpec(name="overlap_trim", default=0.02),
            ParameterSpec(name="outcome_scaling", default="raw+standardized"),
            ParameterSpec(name="bootstrap_draws", default=100),
            ParameterSpec(name="random_seed", default=None),
            ParameterSpec(name="random_seed_manifest", default=()),
            ParameterSpec(name="feature_importance_mode", default="permutation"),
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
        n, _k = X.shape
        estimation_backend = str(params.get("estimation_backend", "custom")).strip().lower()
        if estimation_backend in {"econml", "econml_direct"}:
            from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning

            delegate_params = {
                "model_type": str(params.get("direct_model_type", "linear")).strip().lower(),
                "cv_folds": int(params.get("crossfit_folds", 3)),
                "confidence_level": float(params.get("confidence_level", 0.95)),
                "feature_importance_method": "tree_based",
                "random_state": int(params.get("random_seed", params.get("__seed__", 0)) or 0),
            }
            delegated = DoubleMachineLearning.pure_step(
                {
                    "outcome": Y,
                    "treatment": T,
                    "covariates": X,
                },
                delegate_params,
            )
            if getattr(delegated.get("report"), "point_estimate", None) is not None:
                return delegated
        effective_params = dict(params)
        effective_params.setdefault("nuisance_model_family", "competitive")
        effective_params.setdefault("crossfit_folds", 5)
        effective_params.setdefault("n_repeats", 3)
        effective_params.setdefault("propensity_clipping", 0.01)
        effective_params.setdefault("propensity_trimming", 0.02)
        effective_params.setdefault("overlap_trim", 0.02)
        effective_params.setdefault("outcome_scaling", "raw+standardized")
        effective_params.setdefault("bootstrap_draws", 100)
        effective_params.setdefault("feature_importance_mode", "permutation")
        config = build_nuisance_config(effective_params)
        nuisance = _resolve_nuisance_outputs(X, T, Y, params=effective_params)
        m_hat = 0.5 * (nuisance.mu1 + nuisance.mu0)
        y_residual = Y - m_hat
        t_residual = T - nuisance.propensity
        tau_fit = fit_r_tau_model(X, y_residual, t_residual, config)
        cate_pred = tau_fit.cate_predictions
        ate = float(np.mean(cate_pred[nuisance.trim_mask]))
        ci_lower, ci_upper = bootstrap_mean_interval(
            cate_pred[nuisance.trim_mask],
            seed=config.random_seed + 89,
            draws=config.bootstrap_draws,
        )
        feature_importance_payload = _suppress_importances_if_homogeneous(
            cate_pred,
            _feature_importances_from_array(
                tau_fit.feature_importances if tau_fit.feature_importances is not None else np.array([]),
                [f"x{i}" for i in range(X.shape[1])],
                method="permutation" if config.feature_importance_mode == "permutation" else "model_based",
            ),
        )

        return {
            "result": {
                "ate": ate,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "cate_predictions": cate_pred.tolist(),
                "cate_std": float(np.std(cate_pred)),
                "feature_importances": feature_importance_payload,
                "lambda_reg": float(params.get("lambda_reg", 0.01)),
                "n_obs": n,
                "nuisance_diagnostics": nuisance.diagnostics(),
                "nuisance_config": {
                    "nuisance_model_family": config.nuisance_model_family,
                    "crossfit_folds": config.crossfit_folds,
                    "n_repeats": config.n_repeats,
                    "random_seed_manifest": list(config.random_seed_manifest),
                    "propensity_clipping": config.propensity_clipping,
                    "propensity_trimming": config.propensity_trimming,
                    "outcome_scaling": config.outcome_scaling,
                    "inference_backend": config.inference_backend,
                    "bootstrap_draws": config.bootstrap_draws,
                    "feature_importance_mode": config.feature_importance_mode,
                },
                "heterogeneity_signal": float(np.std(cate_pred, ddof=1)) if cate_pred.size > 1 else 0.0,
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
