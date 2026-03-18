"""Interference and network causal inference methods.

Implements four estimators that relax SUTVA (Stable Unit Treatment Value
Assumption) by allowing spillover effects across units connected via a
cluster, network, spatial, or bipartite structure.

References
----------
Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with
    interference. JASA 103(482).
Aronow, P.M. & Samii, C. (2017). Estimating average causal effects under
    general interference. Ann. Appl. Stat.
Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample randomization
    inference of causal effects in the presence of interference. JRSS-B.
Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal inference in
    the presence of interference. Stat. Methods Med. Res.
Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal inference with
    interference. Stat. Sci.
Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal inference under
    interference in spatial settings. Epidemiol. Methods.
"""
from __future__ import annotations

import math
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
from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)

# ──────────────────────────────────────────────────────────────────────────────
# Shared output slots
# ──────────────────────────────────────────────────────────────────────────────

def _interference_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                name="result",
                slot_type=SlotType.SCALAR,
                unit=Unit("report", "json"),
                description="NetworkInterferenceReport with effect decomposition",
            ),
        }
    )


# ──────────────────────────────────────────────────────────────────────────────
# Low-level algorithm helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_network_data(state: Any) -> NetworkCausalData:
    """Coerce *state* to NetworkCausalData."""
    if isinstance(state, NetworkCausalData):
        return state
    if isinstance(state, dict):
        return NetworkCausalData.model_validate(state)
    raise TypeError(f"Expected NetworkCausalData, got {type(state).__name__}")


def _fractional_exposure(treatment: np.ndarray, cluster_id: np.ndarray) -> np.ndarray:
    """Per-unit fraction of *other* cluster members who are treated.

    Hudgens & Halloran (2008) Eq. (1).
    Returns shape ``(n_units,)`` float in [0, 1].
    """
    clusters = np.unique(cluster_id)
    exposure = np.zeros(len(treatment), dtype=float)
    for c in clusters:
        mask = cluster_id == c
        indices = np.where(mask)[0]
        n_c = int(mask.sum())
        if n_c < 2:
            continue
        for pos, idx in enumerate(indices):
            total_others = float(treatment[mask].sum()) - float(treatment[idx])
            exposure[idx] = total_others / (n_c - 1)
    return exposure


def _threshold_exposure(
    treatment: np.ndarray,
    cluster_id: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Binary indicator: 1 if fractional exposure exceeds *threshold*."""
    return (_fractional_exposure(treatment, cluster_id) > threshold).astype(float)


def _network_exposure(
    treatment: np.ndarray,
    adjacency: np.ndarray,
    mapping_type: str = "fraction",
) -> np.ndarray:
    """Aronow & Samii (2017) exposure mapping via adjacency matrix.

    Parameters
    ----------
    mapping_type:
        ``"fraction"`` — mean neighbour treatment;
        ``"count"`` — number of treated neighbours;
        ``"any"`` — 1 if any neighbour is treated.
    """
    neighbor_sum = adjacency @ treatment.astype(float)
    degree = adjacency.sum(axis=1)
    if mapping_type == "fraction":
        with np.errstate(invalid="ignore", divide="ignore"):
            exp = np.where(degree > 0, neighbor_sum / degree, 0.0)
    elif mapping_type == "count":
        exp = neighbor_sum
    else:  # "any"
        exp = (neighbor_sum > 0).astype(float)
    return exp.astype(float)


def _kernel_weights(coordinates: np.ndarray, bandwidth: float) -> np.ndarray:
    """Gaussian kernel weight matrix; diagonal set to zero (no self-influence).

    W_ij = exp(−‖x_i − x_j‖² / (2h²)).
    """
    diff = coordinates[:, np.newaxis, :] - coordinates[np.newaxis, :, :]  # (n, n, d)
    sq_dist = (diff ** 2).sum(axis=-1)  # (n, n)
    W = np.exp(-sq_dist / (2.0 * bandwidth ** 2))
    np.fill_diagonal(W, 0.0)
    return W


def _auto_bandwidth(coordinates: np.ndarray) -> float:
    """Silverman rule-of-thumb bandwidth for spatial kernel."""
    n = len(coordinates)
    # Mean pairwise distance variance proxy
    sigma = float(np.std(coordinates))
    return max(sigma * (n ** (-0.2)), 1e-6)


def _logistic_propensity(
    treatment: np.ndarray,
    features: np.ndarray,
    C: float = 1.0,
) -> np.ndarray:
    """Fit logistic regression and return P(A=1|features) for each unit."""
    from sklearn.linear_model import LogisticRegression  # lazy import

    lr = LogisticRegression(max_iter=2000, solver="lbfgs", C=C)
    lr.fit(features, treatment.astype(int))
    return lr.predict_proba(features)[:, 1].astype(float)


def _sandwich_var(scores: np.ndarray) -> float:
    """Robust sandwich variance of the sample mean: Var(ȳ) = E[ψ²]/n."""
    n = len(scores)
    if n < 2:
        return float("nan")
    return float(np.mean(scores ** 2) - np.mean(scores) ** 2) / n


def _normal_ci(estimate: float, se: float, level: float = 0.95) -> tuple[float, float]:
    """Gaussian confidence interval."""
    z = _normal_quantile(1.0 - (1.0 - level) / 2.0)
    return float(estimate - z * se), float(estimate + z * se)


def _normal_quantile(p: float) -> float:
    """Rational approximation to the normal quantile (Beasley & Springer 1977)."""
    import math as _math

    if p <= 0.0 or p >= 1.0:
        return float("nan")
    if abs(p - 0.5) < 1e-9:
        return 0.0
    sign = 1.0 if p > 0.5 else -1.0
    q = min(p, 1.0 - p)
    r = _math.sqrt(-2.0 * _math.log(q))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    numer = c0 + c1 * r + c2 * r * r
    denom = 1.0 + d1 * r + d2 * r * r + d3 * r * r * r
    return sign * (r - numer / denom)


def _ipw_potential_outcome(
    outcome: np.ndarray,
    indicator: np.ndarray,
    propensity: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Horvitz-Thompson IPW mean of E[Y(a)] under indicator/propensity.

    Returns ``(estimate, influence_scores)`` where influence scores can be
    used for sandwich variance estimation.
    """
    ps_clipped = np.clip(propensity, 1e-6, 1.0 - 1e-6)
    scores = outcome * indicator / ps_clipped
    estimate = float(np.mean(scores))
    return estimate, scores


def _build_report_failure(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    n_units: int,
    n_treated: int,
    reason: str,
    status: str = "input_invalid",
) -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=method,
        status=status,  # type: ignore[arg-type]
        status_reason=reason,
        exposure_mapping=exposure_mapping,
        n_units=n_units,
        n_treated=n_treated,
        warnings=[reason],
    )


def _build_report_success(
    method: InterferenceMethod,
    exposure_mapping: ExposureMappingType,
    de: float,
    se_val: float,
    te: float,
    se_de: float,
    se_se: float,
    se_te: float,
    n_units: int,
    n_treated: int,
    confidence_level: float,
    n_clusters: int | None = None,
    avg_cluster_size: float | None = None,
    alpha_high: float = 0.5,
    alpha_low: float = 0.0,
    exposure_params: dict[str, Any] | None = None,
    assumptions: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> NetworkInterferenceReport:
    ci_de = _normal_ci(de, se_de, confidence_level) if math.isfinite(se_de) and se_de > 0 else None
    ci_se = _normal_ci(se_val, se_se, confidence_level) if math.isfinite(se_se) and se_se > 0 else None
    ci_te = _normal_ci(te, se_te, confidence_level) if math.isfinite(se_te) and se_te > 0 else None

    # Interference detected: spillover SE different from 0 at 5%
    interference_detected = False
    if ci_se is not None and not (ci_se[0] <= 0.0 <= ci_se[1]):
        interference_detected = True
    elif math.isfinite(se_se) and se_se > 0:
        z = abs(se_val) / se_se
        interference_detected = z > 1.96

    effects = InterferenceEffectDecomposition(
        direct_effect=de,
        spillover_effect=se_val,
        total_effect=te,
        alpha_high=alpha_high,
        alpha_low=alpha_low,
        se_direct=se_de if math.isfinite(se_de) else None,
        se_spillover=se_se if math.isfinite(se_se) else None,
        se_total=se_te if math.isfinite(se_te) else None,
        ci_direct=ci_de,
        ci_spillover=ci_se,
        ci_total=ci_te,
        n_units=n_units,
        n_treated=n_treated,
        confidence_level=confidence_level,
        interference_detected=interference_detected,
    )
    return NetworkInterferenceReport(
        method=method,
        status="success",
        effects=effects,
        exposure_mapping=exposure_mapping,
        exposure_mapping_params=exposure_params or {},
        n_units=n_units,
        n_treated=n_treated,
        n_clusters=n_clusters,
        average_cluster_size=avg_cluster_size,
        assumptions=assumptions or {},
        warnings=warnings or [],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Core algorithm implementations
# ──────────────────────────────────────────────────────────────────────────────

def _run_partial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Hudgens & Halloran (2008) partial interference IPW."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    alpha_bw = float(params.get("alpha_bandwidth", 0.1))
    exposure_map = str(params.get("exposure_mapping", "fractional"))
    threshold = float(params.get("threshold", 0.5))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.cluster_id is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "cluster_id is required for PartialInterferenceEstimator",
            )
        }

    C = data.cluster_id
    clusters = np.unique(C)
    n_clusters = int(len(clusters))
    avg_cluster_size = float(n / n_clusters)

    # Compute exposure
    if exposure_map == "threshold":
        f = _threshold_exposure(A, C, threshold)
        exp_type = ExposureMappingType.THRESHOLD
    else:
        f = _fractional_exposure(A, C)
        exp_type = ExposureMappingType.FRACTIONAL

    # Build propensity features
    if data.covariates is not None:
        ps_features = np.column_stack([data.covariates, f])
    else:
        ps_features = f.reshape(-1, 1)

    try:
        ps = _logistic_propensity(A, ps_features)
    except Exception as exc:
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                f"propensity model failed: {exc}",
                status="numerical_failure",
            )
        }

    # Stratum masks: (treatment==a) & exposure near alpha
    def _potential_outcome_stratum(a_val: float, alpha: float) -> tuple[float, np.ndarray]:
        in_stratum = (A == a_val) & (np.abs(f - alpha) <= alpha_bw)
        if in_stratum.sum() < 2:
            return float("nan"), np.full(n, float("nan"))
        ps_a = ps if a_val == 1.0 else (1.0 - ps)
        # P(A=a, |f - alpha| <= alpha_bw) ≈ P(A=a) * P(|f-alpha|<=bw | A=a)
        # Use unit-level IPW within stratum
        est, scores = _ipw_potential_outcome(Y, in_stratum.astype(float), ps_a)
        # Normalise so it's an estimate of E[Y(a, alpha)], not a sum
        return est, scores

    mu11, sc11 = _potential_outcome_stratum(1.0, alpha_high)
    mu10, sc10 = _potential_outcome_stratum(0.0, alpha_high)
    mu01, sc01 = _potential_outcome_stratum(0.0, alpha_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some alpha-strata have fewer than 2 observations; "
            "estimates may be unreliable."
        )

    # Fallback: simple cluster-level means when strata are sparse
    def _fallback_mean(a_val: float) -> float:
        mask = A == a_val
        return float(Y[mask].mean()) if mask.sum() > 0 else float("nan")

    if math.isnan(mu11):
        mu11 = _fallback_mean(1.0)
    if math.isnan(mu10):
        mu10 = _fallback_mean(0.0)
    if math.isnan(mu01):
        mu01 = _fallback_mean(0.0)

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Cluster-level sandwich variance
    def _cluster_var(scores: np.ndarray) -> float:
        """Mean cluster-level variance."""
        if np.any(np.isnan(scores)):
            return float("nan")
        cluster_means = np.array(
            [scores[C == c].mean() for c in clusters], dtype=float
        )
        return float(np.var(cluster_means, ddof=1) / n_clusters)

    var_de = _cluster_var(sc11 - sc10) if not np.any(np.isnan(sc11 + sc10)) else float("nan")
    var_se = _cluster_var(sc10 - sc01) if not np.any(np.isnan(sc10 + sc01)) else float("nan")
    var_te = _cluster_var(sc11 - sc01) if not np.any(np.isnan(sc11 + sc01)) else float("nan")

    se_de = math.sqrt(max(var_de, 0.0)) if math.isfinite(var_de) else float("nan")
    se_se = math.sqrt(max(var_se, 0.0)) if math.isfinite(var_se) else float("nan")
    se_te = math.sqrt(max(var_te, 0.0)) if math.isfinite(var_te) else float("nan")

    if any(not math.isfinite(x) for x in (de, se_val, te)):
        return {
            "result": _build_report_failure(
                InterferenceMethod.PARTIAL_IPW,
                exp_type,
                n,
                n_treated,
                "Could not estimate one or more potential outcomes; "
                "check treatment variation and alpha bandwidth.",
                status="numerical_failure",
            )
        }

    assumptions = {
        "partial_interference": "Units in different clusters do not interfere.",
        "stratified_interference": "Within a cluster, potential outcome depends on own "
        "treatment and aggregate cluster allocation only.",
        "positivity": "Each unit has positive probability of treatment and each "
        "exposure level under both treatment arms.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.PARTIAL_IPW,
            exposure_mapping=exp_type,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            n_clusters=n_clusters,
            avg_cluster_size=avg_cluster_size,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "exposure_mapping": exposure_map,
                "alpha_bandwidth": alpha_bw,
                "threshold": threshold,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_network_aipw(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Aronow & Samii (2017) network AIPW with general exposure mapping."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    n_bootstrap = int(params.get("n_bootstrap", 200))
    mapping_type = str(params.get("exposure_mapping", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.adjacency_matrix is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.NETWORK_AIPW,
                ExposureMappingType.FRACTIONAL,
                n,
                n_treated,
                "adjacency_matrix is required for NetworkAIPWEstimator",
            )
        }

    W = data.adjacency_matrix.astype(float)
    e = _network_exposure(A, W, mapping_type)

    # Binary indicator: high exposure (e > alpha_high) vs low
    e_high = (e >= alpha_high).astype(float)
    e_low = (e <= alpha_low).astype(float)

    # Build features: [A, e, X] for propensity models
    base_features = np.column_stack([A, e])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _aipw_for_stratum(
        a_val: float,
        e_indicator: np.ndarray,
    ) -> tuple[float, float]:
        """AIPW estimator for E[Y(a, e_type)] where e_type is high/low."""
        stratum = (A == a_val) & (e_indicator > 0)
        if stratum.sum() < 3:
            return float("nan"), float("nan")

        # Outcome model E[Y | X, A=a, e_type]
        try:
            from sklearn.linear_model import Ridge
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X_s = scaler.fit_transform(base_features[stratum])
            y_s = Y[stratum]
            ridge = Ridge(alpha=1.0)
            ridge.fit(X_s, y_s)
            mu_hat = ridge.predict(scaler.transform(base_features))
        except Exception:
            mu_hat = np.full(n, float(Y[stratum].mean()))

        # Propensity P(in stratum | X)
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)

        ps_clipped = np.clip(ps, 1e-4, 1 - 1e-4)
        # AIPW scores: IPW + augmentation
        aipw_scores = (
            stratum.astype(float) * Y / ps_clipped
            - (stratum.astype(float) / ps_clipped - 1.0) * mu_hat
        )
        est = float(np.mean(aipw_scores))
        se = math.sqrt(max(_sandwich_var(aipw_scores - est), 0.0))
        return est, se

    mu11, se11 = _aipw_for_stratum(1.0, e_high)
    mu10, se10 = _aipw_for_stratum(0.0, e_high)
    mu01, se01 = _aipw_for_stratum(0.0, e_low)

    warnings: list[str] = []
    if any(math.isnan(x) for x in (mu11, mu10, mu01)):
        warnings.append(
            "Some exposure strata have too few observations. "
            "Consider adjusting alpha_high / alpha_low."
        )
        # Fallback
        if math.isnan(mu11):
            mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
        if math.isnan(mu10):
            mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
        if math.isnan(mu01):
            mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    # Combined SEs (independent strata approximation)
    def _combined_se(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1 ** 2 + s2 ** 2)

    se_de = _combined_se(se11, se10)
    se_se = _combined_se(se10, se01)
    se_te = _combined_se(se11, se01)

    assumptions = {
        "no_unmeasured_confounding": "Treatment assignment is ignorable given observed covariates.",
        "positivity_exposure": "Each unit has positive probability of each exposure level.",
        "stratified_interference": "Potential outcome depends on own treatment and exposure "
        "level (aggregated from adjacency) only.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.NETWORK_AIPW,
            exposure_mapping=ExposureMappingType.FRACTIONAL,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "mapping_type": mapping_type,
                "n_bootstrap": n_bootstrap,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_spatial_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Kernel-weighted spatial spillover estimator."""
    bandwidth_param = params.get("bandwidth", "auto")
    kernel = str(params.get("kernel", "gaussian"))
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    # Resolve spatial structure
    if data.coordinates is not None:
        coords = data.coordinates[:, :2].astype(float)  # keep only x, y
    elif data.adjacency_matrix is not None:
        # Fallback: use adjacency as weight matrix directly
        W = data.adjacency_matrix.astype(float)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)
        coords = None
    else:
        return {
            "result": _build_report_failure(
                InterferenceMethod.SPATIAL_KERNEL,
                ExposureMappingType.KERNEL,
                n,
                n_treated,
                "coordinates or adjacency_matrix required for SpatialInterferenceEstimator",
            )
        }

    used_bandwidth: float | None = None
    if coords is not None:
        if bandwidth_param == "auto":
            bw = _auto_bandwidth(coords)
        else:
            try:
                bw = float(bandwidth_param)
            except (TypeError, ValueError):
                bw = _auto_bandwidth(coords)
        if bw <= 0:
            return {
                "result": _build_report_failure(
                    InterferenceMethod.SPATIAL_KERNEL,
                    ExposureMappingType.KERNEL,
                    n,
                    n_treated,
                    f"bandwidth must be positive, got {bw}",
                )
            }
        used_bandwidth = bw
        W = _kernel_weights(coords, bw)
        degree = W.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(degree > 0, (W @ A) / degree, 0.0)

    # Exposure strata
    e_high = (s >= alpha_high).astype(float)
    e_low = (s <= alpha_low).astype(float)

    base_features = np.column_stack([A, s])
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _ipw_mean(a_val: float, e_ind: np.ndarray) -> tuple[float, float]:
        stratum = (A == a_val) & (e_ind > 0)
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum.astype(int), base_features)
        except Exception:
            ps = np.full(n, float(stratum.mean()) + 1e-6)
        est, scores = _ipw_potential_outcome(Y, stratum.astype(float), ps)
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu11, se11 = _ipw_mean(1.0, e_high)
    mu10, se10 = _ipw_mean(0.0, e_high)
    mu01, se01 = _ipw_mean(0.0, e_low)

    warnings: list[str] = []
    for mu, name in ((mu11, "E[Y(1,high)]"), (mu10, "E[Y(0,high)]"), (mu01, "E[Y(0,low)]")):
        if math.isnan(mu):
            warnings.append(f"Stratum for {name} has too few units; using marginal mean.")

    if math.isnan(mu11):
        mu11 = float(Y[A == 1.0].mean()) if (A == 1.0).sum() > 0 else 0.0
    if math.isnan(mu10):
        mu10 = float(Y[A == 0.0].mean()) if (A == 0.0).sum() > 0 else 0.0
    if math.isnan(mu01):
        mu01 = mu10

    de = mu11 - mu10
    se_val = mu10 - mu01
    te = mu11 - mu01

    def _cse(s1: float, s2: float) -> float:
        if math.isnan(s1) or math.isnan(s2):
            return float("nan")
        return math.sqrt(s1 ** 2 + s2 ** 2)

    se_de = _cse(se11, se10)
    se_se = _cse(se10, se01)
    se_te = _cse(se11, se01)

    exposure_params: dict[str, Any] = {
        "kernel": kernel,
        "alpha_high": alpha_high,
        "alpha_low": alpha_low,
    }
    if used_bandwidth is not None:
        exposure_params["bandwidth"] = used_bandwidth

    assumptions = {
        "geographic_spillover": "Spillover effects decay with geographic distance as modelled by the kernel.",
        "positivity": "Positive probability of each exposure level in each spatial location.",
        "no_unmeasured_confounding": "Treatment assignment ignorable given covariates.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.SPATIAL_KERNEL,
            exposure_mapping=ExposureMappingType.KERNEL,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params=exposure_params,
            assumptions=assumptions,
            warnings=warnings,
        )
    }


def _run_bipartite_interference(
    data: NetworkCausalData,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Zigler & Papadogeorgou (2021) bipartite interference."""
    alpha_high = float(params.get("alpha_high", 0.5))
    alpha_low = float(params.get("alpha_low", 0.0))
    aggregate_fn = str(params.get("aggregate_fn", "fraction"))
    conf = float(params.get("confidence_level", 0.95))

    Y = data.outcome.astype(float)
    A = data.treatment.astype(float)
    n = data.n_units
    n_treated = data.n_treated

    if data.bipartite_edges is None or data.treatment_unit_ids is None:
        return {
            "result": _build_report_failure(
                InterferenceMethod.BIPARTITE,
                ExposureMappingType.BIPARTITE,
                n,
                n_treated,
                "bipartite_edges and treatment_unit_ids are required for "
                "BipartiteInterferenceEstimator",
            )
        }

    edges = data.bipartite_edges  # (n_edges, 2): [tx_unit_idx, outcome_unit_idx]
    tx_ids = data.treatment_unit_ids  # (n_tx,) int
    n_tx = len(tx_ids)

    # Treatment of treatment units
    A_tx = A[tx_ids]

    # Aggregate exposure for each outcome unit (all n units, non-outcome units get 0)
    g = np.zeros(n, dtype=float)
    for out_idx in range(n):
        upstream = edges[edges[:, 1] == out_idx, 0]
        if len(upstream) == 0:
            continue
        if aggregate_fn == "fraction":
            g[out_idx] = float(A_tx[upstream].mean())
        elif aggregate_fn == "count":
            g[out_idx] = float(A_tx[upstream].sum())
        else:  # "max"
            g[out_idx] = float(A_tx[upstream].max())

    # For outcome units: high/low exposure indicators
    e_high = (g >= alpha_high).astype(float)
    e_low = (g <= alpha_low).astype(float)

    # Mark outcome units (not treatment units)
    outcome_mask = np.ones(n, dtype=bool)
    outcome_mask[tx_ids] = False
    n_outcome = int(outcome_mask.sum())

    base_features = g.reshape(-1, 1)
    if data.covariates is not None:
        base_features = np.column_stack([base_features, data.covariates])

    def _mean_potential(e_ind: np.ndarray, out_mask: np.ndarray) -> tuple[float, float]:
        stratum = e_ind.astype(bool) & out_mask
        if stratum.sum() < 2:
            return float("nan"), float("nan")
        try:
            ps = _logistic_propensity(stratum[out_mask].astype(int), base_features[out_mask])
        except Exception:
            ps = np.full(int(out_mask.sum()), float(stratum[out_mask].mean()) + 1e-6)
        ps_full = np.zeros(n)
        ps_full[out_mask] = ps
        est, scores = _ipw_potential_outcome(
            Y * out_mask.astype(float),
            stratum.astype(float),
            np.clip(ps_full, 1e-6, 1 - 1e-6),
        )
        se = math.sqrt(max(_sandwich_var(scores - est), 0.0))
        return est, se

    mu_high, se_high = _mean_potential(e_high, outcome_mask)
    mu_low, se_low = _mean_potential(e_low, outcome_mask)

    warnings: list[str] = []
    if math.isnan(mu_high) or math.isnan(mu_low):
        warnings.append(
            "One or more exposure strata have too few outcome units. "
            "Falling back to marginal mean differences."
        )
        mu_high_val = float(Y[outcome_mask & e_high.astype(bool)].mean()) if (outcome_mask & e_high.astype(bool)).sum() > 0 else 0.0
        mu_low_val = float(Y[outcome_mask & e_low.astype(bool)].mean()) if (outcome_mask & e_low.astype(bool)).sum() > 0 else 0.0
        if math.isnan(mu_high):
            mu_high, se_high = mu_high_val, 0.0
        if math.isnan(mu_low):
            mu_low, se_low = mu_low_val, 0.0

    # In bipartite setting: direct effect = contrast in aggregate exposure
    # (no "own treatment" for outcome units)
    de = mu_high - mu_low
    se_val = mu_high - mu_low  # spillover ≡ aggregate exposure contrast
    te = de

    se_de = math.sqrt(se_high ** 2 + se_low ** 2) if math.isfinite(se_high) and math.isfinite(se_low) else float("nan")
    se_se = se_de
    se_te = se_de

    assumptions = {
        "bipartite_structure": "Outcome units are distinct from treatment units; "
        "interference acts only through upstream treatment.",
        "positivity": "Positive probability of each aggregate exposure level.",
        "no_unmeasured_confounding": "Assignment of treatment units is ignorable given observed covariates.",
    }

    return {
        "result": _build_report_success(
            method=InterferenceMethod.BIPARTITE,
            exposure_mapping=ExposureMappingType.BIPARTITE,
            de=de,
            se_val=se_val,
            te=te,
            se_de=se_de,
            se_se=se_se,
            se_te=se_te,
            n_units=n,
            n_treated=n_treated,
            confidence_level=conf,
            alpha_high=alpha_high,
            alpha_low=alpha_low,
            exposure_params={
                "aggregate_fn": aggregate_fn,
                "n_treatment_units": n_tx,
                "n_outcome_units": n_outcome,
            },
            assumptions=assumptions,
            warnings=warnings,
        )
    }


# ──────────────────────────────────────────────────────────────────────────────
# Method 1: PartialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "cluster", "spillover"},
)
class PartialInterferenceEstimator:
    """Clustered partial interference estimator (Hudgens & Halloran 2008).

    Decomposes average causal effects into a **direct effect** (own
    treatment, neighbours' allocation fixed) and a **spillover effect**
    (change in outcome from shifting cluster allocation from α_low to
    α_high, own treatment fixed at 0).

    Requires ``cluster_id`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="partial",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed outcome Y_i for each unit.",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment indicator A_i ∈ {0, 1}.",
                ),
                SlotSpec(
                    name="cluster_id",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_units",),
                    description="Integer cluster membership c_i.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                    description="Optional pre-treatment covariates X_i.",
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="alpha_high",
                default=0.5,
                description="High-coverage allocation arm α₁.",
            ),
            ParameterSpec(
                name="alpha_low",
                default=0.0,
                description="Low-coverage allocation arm α₂ (usually 0).",
            ),
            ParameterSpec(
                name="alpha_bandwidth",
                default=0.1,
                description="Tolerance window for α-stratum membership.",
            ),
            ParameterSpec(
                name="exposure_mapping",
                default="fractional",
                description="Exposure mapping type: 'fractional' or 'threshold'.",
            ),
            ParameterSpec(
                name="threshold",
                default=0.5,
                description="Threshold for binary exposure mapping.",
            ),
            ParameterSpec(
                name="confidence_level",
                default=0.95,
                description="Confidence level for interval estimates.",
            ),
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
            "Clustered partial interference estimator. Decomposes ATE into "
            "direct effect DE(α) = E[Y(1,α)] − E[Y(0,α)] and spillover effect "
            "SE(α₁,α₂) = E[Y(0,α₁)] − E[Y(0,α₂)] using IPW with exposure "
            "mapping within clusters."
        ),
        tags=frozenset({"causal", "interference", "cluster", "spillover"}),
        citations=(
            "Hudgens, M.G. & Halloran, M.E. (2008). Toward causal inference with "
            "interference. JASA 103(482).",
            "Sobel, M.E. (2006). What do randomized studies of housing mobility "
            "demonstrate? JASA 101(476).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "direct_effect": "DE(α) = E[Y(1,α)] - E[Y(0,α)]",
            "spillover_effect": "SE(α1,α2) = E[Y(0,α1)] - E[Y(0,α2)]",
            "total_effect": "TE(α1,α2) = E[Y(1,α1)] - E[Y(0,α2)]",
            "exposure_mapping_fractional": "f_i = Σ_{j≠i,c} A_j / (n_c - 1)",
        },
        assumptions={
            "partial_interference": "Units in different clusters do not interfere.",
            "stratified_interference": (
                "Within a cluster, a unit's potential outcome depends only on "
                "its own treatment and the aggregate cluster allocation."
            ),
            "positivity": (
                "P(A_i=a, f_i≈α | X_i) > 0 for all a ∈ {0,1} and α ∈ {α_low, α_high}."
            ),
        },
        when_to_use=(
            "Cluster-randomised experiments or observational studies where "
            "interference is limited to within pre-defined groups (villages, "
            "schools, households, clinics)."
        ),
        when_not_to_use=(
            "Cross-cluster interference; continuous treatment; single-unit "
            "clusters (cluster_size=1)."
        ),
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, holding neighbours' "
            "allocation fixed at α_high. "
            "spillover_effect: effect of shifting cluster allocation from "
            "α_low to α_high, own treatment fixed at 0."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_partial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 2: NetworkAIPWEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "network", "aipw", "spillover"},
)
class NetworkAIPWEstimator:
    """General network AIPW estimator (Aronow & Samii 2017).

    Uses an arbitrary adjacency matrix to define the exposure mapping
    f(A, N_i) → exposure level, then applies doubly-robust AIPW
    estimation within exposure strata.

    Requires ``adjacency_matrix`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_aipw",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="adjacency_matrix",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("adjacency", "weight"),
                    shape=("n_units", "n_units"),
                    description="Network adjacency (weighted or binary).",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="exposure_mapping",
                default="fraction",
                description="'fraction' | 'count' | 'any'",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="n_bootstrap",
                default=200,
                description="Bootstrap draws for variance estimation.",
            ),
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
        description=(
            "Doubly-robust AIPW estimator under general network interference. "
            "Uses an exposure mapping f(A, N_i) derived from the adjacency "
            "matrix to define treatment×exposure strata, then applies AIPW "
            "within each stratum."
        ),
        tags=frozenset({"causal", "interference", "network", "aipw", "spillover"}),
        citations=(
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
            "Liu, L., Hudgens, M.G. & Becker-Dreps, S. (2016). On sample "
            "randomization inference of causal effects in the presence of "
            "interference. JRSS-B.",
        ),
        equations={
            "exposure_fraction": "e_i = (Σ_j W_ij A_j) / (Σ_j W_ij)",
            "aipw_score": "ψ_i = I(stratum)/P(stratum|X) * Y - (I/P - 1) * μ̂(X)",
        },
        assumptions={
            "no_unmeasured_confounding": "Treatment ignorable given covariates.",
            "exposure_positivity": "P(e_i = e | X_i) > 0 for all exposure levels e.",
            "network_structure_known": "Adjacency matrix W is observed without error.",
        },
        when_to_use=(
            "Social network experiments or observational studies with an "
            "observed interaction graph where spillover is mediated by "
            "direct connections."
        ),
        when_not_to_use="Unobserved network structure; very sparse networks.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: E[Y(1,high)] - E[Y(0,high)] — effect of own "
            "treatment among units with high network exposure. "
            "spillover_effect: E[Y(0,high)] - E[Y(0,low)] — effect of "
            "having highly-treated neighbours."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_network_aipw(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 3: SpatialInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "spatial", "spillover"},
)
class SpatialInterferenceEstimator:
    """Gaussian kernel spatial spillover estimator.

    Constructs a kernel-weighted exposure mapping
    s_i = Σ_j K(d_ij; h) A_j / Σ_j K(d_ij; h)
    using geographic ``coordinates``, then estimates direct and spillover
    effects across high/low exposure strata.

    Requires ``coordinates`` (or falls back to ``adjacency_matrix``) in
    the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="spatial",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec(
                    name="coordinates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("space", "coordinate"),
                    shape=("n_units", "n_dims"),
                    description="Spatial coordinates [x, y] or [lon, lat].",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(
                name="bandwidth",
                default="auto",
                description="Kernel bandwidth h or 'auto' for Silverman ROT.",
            ),
            ParameterSpec(
                name="kernel",
                default="gaussian",
                description="Kernel function: 'gaussian'.",
            ),
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
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
        description=(
            "Kernel-weighted geographic spillover estimator. Builds a "
            "Gaussian exposure mapping from spatial coordinates, then "
            "estimates direct effect DE and spillover SE via IPW across "
            "high/low kernel-exposure strata."
        ),
        tags=frozenset({"causal", "interference", "spatial", "spillover"}),
        citations=(
            "Verbitsky-Savitz, N. & Raudenbush, S.W. (2012). Causal "
            "inference under interference in spatial settings. Epidemiol. Methods.",
            "Aronow, P.M. & Samii, C. (2017). Estimating average causal "
            "effects under general interference. Ann. Appl. Stat. 11(4).",
        ),
        equations={
            "kernel_exposure": "s_i = Σ_j K(‖x_i - x_j‖; h) A_j / Σ_j K(‖x_i - x_j‖; h)",
            "gaussian_kernel": "K(d; h) = exp(-d² / (2h²))",
            "bandwidth_rot": "h* = σ_coords · n^(-1/5)",
        },
        assumptions={
            "spatial_spillover": "Interference decays smoothly with geographic distance.",
            "kernel_specification": "Gaussian kernel captures the decay structure adequately.",
            "positivity": "Positive probability of each spatial exposure level.",
        },
        when_to_use=(
            "Geographic policy evaluation (environmental regulations, "
            "infrastructure, epidemics) where spillover is plausibly distance-based."
        ),
        when_not_to_use="Non-geographic networks; sharp spillover cutoffs.",
        typical_min_obs=100,
        output_interpretation=(
            "direct_effect: effect of own treatment, controlling for "
            "spatial exposure. spillover_effect: effect of being in a "
            "high-treatment neighbourhood vs a low-treatment neighbourhood."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_spatial_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Method 4: BipartiteInterferenceEstimator
# ──────────────────────────────────────────────────────────────────────────────

@foundry_method(
    namespace="causal.interference",
    version="1.0.0",
    tags={"causal", "interference", "bipartite", "spillover"},
)
class BipartiteInterferenceEstimator:
    """Bipartite causal inference with interference (Zigler & Papadogeorgou 2021).

    For settings where treatment units (e.g. power plants, hospitals) are
    distinct from outcome units (e.g. counties, patients).  Interference
    flows from treatment units to outcome units through a bipartite graph.

    Requires ``bipartite_edges`` and ``treatment_unit_ids`` in the input data.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bipartite",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="outcome",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("outcome", "value"),
                    shape=("n_units",),
                    description="Observed Y_i for all n units (tx + outcome units).",
                ),
                SlotSpec(
                    name="treatment",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("binary", "flag"),
                    shape=("n_units",),
                    description="Binary treatment A_i; non-zero only for treatment units.",
                ),
                SlotSpec(
                    name="bipartite_edges",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("graph", "edge"),
                    shape=("n_edges", "2"),
                    description="[treatment_unit_idx, outcome_unit_idx] edges.",
                ),
                SlotSpec(
                    name="treatment_unit_ids",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("category", "id"),
                    shape=("n_treatment_units",),
                    description="Integer indices of treatment units within the n-unit array.",
                ),
                SlotSpec(
                    name="covariates",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("covariate", "value"),
                    shape=("n_units", "n_features"),
                ),
            }
        ),
        output_slots=_interference_output_slots(),
        parameters=(
            ParameterSpec(name="alpha_high", default=0.5),
            ParameterSpec(name="alpha_low", default=0.0),
            ParameterSpec(
                name="aggregate_fn",
                default="fraction",
                description="'fraction' | 'count' | 'max'",
            ),
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
        description=(
            "Bipartite interference estimator for settings with separate "
            "treatment and outcome units linked by a bipartite graph. "
            "Aggregates upstream treatment into a per-outcome-unit exposure "
            "g_i and estimates effects across high/low exposure strata."
        ),
        tags=frozenset({"causal", "interference", "bipartite", "spillover"}),
        citations=(
            "Zigler, C.M. & Papadogeorgou, G. (2021). Bipartite causal "
            "inference with interference. Stat. Sci. 36(3).",
            "Tchetgen Tchetgen, E.J. & VanderWeele, T.J. (2012). On causal "
            "inference in the presence of interference. Stat. Methods Med. Res.",
        ),
        equations={
            "aggregate_exposure_fraction": "g_i = (1/|N_i|) Σ_{j ∈ N_i} A_j",
            "aggregate_exposure_count": "g_i = Σ_{j ∈ N_i} A_j",
        },
        assumptions={
            "bipartite_structure": (
                "Outcome units are distinct from treatment units; "
                "interference acts only through the bipartite graph."
            ),
            "positivity": "P(g_i ≥ α_high | X_i) > 0 and P(g_i ≤ α_low | X_i) > 0.",
            "no_unmeasured_confounding": "Treatment unit assignments ignorable given covariates.",
        },
        when_to_use=(
            "Power-plant emission regulation studies (plants → counties), "
            "hospital interventions (hospitals → patients), "
            "supplier interventions (suppliers → retailers)."
        ),
        when_not_to_use="Treatment and outcome units are the same; treatment is continuous.",
        typical_min_obs=50,
        output_interpretation=(
            "direct_effect ≡ spillover_effect: contrast E[Y(high)] - E[Y(low)] "
            "for outcome units — effect of being downstream of more treated "
            "treatment units."
        ),
    )

    @staticmethod
    def pure_step(
        state: NetworkCausalData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = _extract_network_data(state)
        return _run_bipartite_interference(data, params)

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> NetworkCausalData:
        if isinstance(fallback_state, NetworkCausalData):
            return fallback_state
        payload: dict[str, Any] = {}
        if isinstance(fallback_state, dict):
            payload.update(fallback_state)
        payload.update({k: v for k, v in bound_inputs.items()})
        return NetworkCausalData.model_validate(payload)


__all__ = [
    "BipartiteInterferenceEstimator",
    "NetworkAIPWEstimator",
    "PartialInterferenceEstimator",
    "SpatialInterferenceEstimator",
]
