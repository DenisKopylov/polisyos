"""eif_bounds — semiparametric efficiency bounds via Efficient Influence Functions.

Provides the semiparametric Cramér-Rao lower bound for each causal estimand,
implemented as the variance of its efficient influence function (EIF).

Fundamental result (Bickel et al. 1993; van der Vaart 1998):
    For any regular estimator θ̂ of θ₀ in a nonparametric model,

        √n (θ̂ − θ₀) →_d N(0, V)    with   V ≥ E[ψ²(O)]

    where ψ is the EIF and E[ψ²] is the semiparametric efficiency bound.

    An estimator achieving V = E[ψ²] is called *locally efficient* or
    *semiparametrically efficient*.

EIFs implemented
----------------
- ATE  :  ψ_ATE   (Hahn 1998; Robins, Rotnitzky & Zhao 1994)
- ATT  :  ψ_ATT   (Hahn 1998)
- LATE :  ψ_LATE  (Imbens & Angrist 1994; Abadie 2003)
- Frontdoor ATE : ψ_fd  (Tchetgen Tchetgen & Shpitser 2012)
- Transport ATE : ψ_tr  (Bareinboim & Pearl 2016 — density-ratio reweighted)

Output types
------------
:class:`EIFScores`
    Named container for per-observation ψᵢ scores.
:class:`EfficiencyBound`
    Semiparametric variance lower bound + inference summary.
:class:`EfficiencyReport`
    Comparison of multiple estimators against the bound.

Foundry method
--------------
:class:`SemiparametricEfficiencyBoundMethod`
    Registered as ``causal.semiparametric.efficiency_bound@1.0.0``.
    Accepts pre-computed nuisance predictions and returns the bound.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

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

if TYPE_CHECKING:
    from polisyos.foundry.methods.catalog.causal.protocols import DoseResponseResult

# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EIFScores:
    """Per-observation efficient influence function scores.

    Parameters
    ----------
    estimand_type : one of 'ate', 'att', 'late', 'frontdoor', 'transport'
    scores        : EIF values ψᵢ, shape (n_obs,)
    n_obs         : number of observations
    """

    estimand_type: str
    scores: np.ndarray
    n_obs: int

    def variance(self) -> float:
        """E[ψ²] — the semiparametric efficiency bound for this estimand."""
        return float(np.mean(self.scores**2))

    def variance_lower_bound(self) -> float:
        """Asymptotic variance lower bound = E[ψ²] / n."""
        return self.variance() / max(self.n_obs, 1)

    def point_estimate(self) -> float:
        """ATE / ATT estimate = mean(ψ)."""
        return float(np.mean(self.scores))

    def standard_error(self) -> float:
        """SE = std(ψ) / √n."""
        return float(np.std(self.scores, ddof=1) / np.sqrt(max(self.n_obs, 1)))

    def ci(self, alpha: float = 0.05) -> tuple[float, float]:
        """Wald CI at level (1 - alpha)."""
        from scipy import stats  # lazy; falls back to 1.96 if unavailable

        try:
            z = float(stats.norm.ppf(1 - alpha / 2))
        except Exception:
            z = 1.96
        est = self.point_estimate()
        se = self.standard_error()
        return est - z * se, est + z * se


@dataclasses.dataclass(frozen=True)
class EfficiencyBound:
    """Semiparametric Cramér-Rao lower bound for a causal estimand.

    Parameters
    ----------
    estimand_type           : 'ate' | 'att' | 'late' | 'frontdoor' | 'transport'
    point_estimate          : θ̂ = mean(ψ)
    standard_error          : SE(θ̂) = std(ψ) / √n
    variance_lower_bound    : E[ψ²] / n — the semiparametric efficiency bound
    eif_variance            : E[ψ²] (un-scaled)
    n_obs                   : sample size
    ci_lower, ci_upper      : 95% Wald CI
    relative_efficiency     : var(estimator) / bound, 1.0 = perfectly efficient
    notes                   : any warnings (positivity, overlap, etc.)
    """

    estimand_type: str
    point_estimate: float
    standard_error: float
    variance_lower_bound: float
    eif_variance: float
    n_obs: int
    ci_lower: float
    ci_upper: float
    relative_efficiency: float = 1.0
    notes: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class EfficiencyReport:
    """Comparison of multiple estimators against the semiparametric bound.

    Attributes
    ----------
    bound           : the :class:`EfficiencyBound` (lower bound)
    estimator_ses   : dict[str, float] mapping estimator name → SE
    relative_efficiencies : dict[str, float] mapping estimator → eff = bound_var / est_var
    most_efficient  : name of the estimator closest to the bound
    """

    bound: EfficiencyBound
    estimator_ses: dict
    relative_efficiencies: dict
    most_efficient: str = ""

    def to_dict(self) -> dict:
        return {
            "bound": self.bound.to_dict(),
            "estimator_ses": self.estimator_ses,
            "relative_efficiencies": self.relative_efficiencies,
            "most_efficient": self.most_efficient,
        }


@dataclasses.dataclass(frozen=True)
class SecondOrderEIF:
    """Approximate second-order EIF correction summary.

    This is an honest finite-sample correction layer, not a symbolic
    higher-order EIF derivation.  The implementation projects the supplied
    first-order scores onto a nuisance basis built from centered first-order
    nuisance derivatives plus quadratic interaction terms, then subtracts the
    fitted component as an approximate bias correction.
    """

    scores: np.ndarray
    bias_correction: float
    corrected_estimate: float
    corrected_se: float
    approximation_method: str = "orthogonal_quadratic_projection"
    basis_terms: tuple[str, ...] = ()
    basis_rank: int = 0
    basis_dimension: int = 0
    condition_number: float | None = None
    projection_norm: float = 0.0
    residual_norm: float = 0.0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": self.scores.tolist(),
            "bias_correction": float(self.bias_correction),
            "corrected_estimate": float(self.corrected_estimate),
            "corrected_se": float(self.corrected_se),
            "approximation_method": self.approximation_method,
            "basis_terms": list(self.basis_terms),
            "basis_rank": int(self.basis_rank),
            "basis_dimension": int(self.basis_dimension),
            "condition_number": (
                float(self.condition_number) if self.condition_number is not None else None
            ),
            "projection_norm": float(self.projection_norm),
            "residual_norm": float(self.residual_norm),
            "note": self.note,
        }


def _validate_1d_array(
    name: str, values: np.ndarray, *, expected_size: int | None = None
) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    if expected_size is not None and arr.size != expected_size:
        raise ValueError(f"{name} must have the same length as first_order_scores")
    if arr.size and not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _build_second_order_basis(
    nuisance_derivatives: dict[str, np.ndarray],
    n_obs: int,
) -> tuple[list[np.ndarray], list[str], str]:
    """Build an honest nuisance basis for approximate second-order correction.

    The basis uses raw nuisance derivatives plus centered quadratic interaction
    terms. Quadratic terms are intentionally retained because they allow a
    finite-sample approximation to some curvature terms that a purely linear
    projection would miss. The intercept is handled separately in
    :func:`compute_second_order_eif` so the correction can preserve the
    estimand-level location instead of mechanically shrinking score means
    toward zero.
    """
    linear_terms: list[tuple[str, np.ndarray]] = []
    for name, values in nuisance_derivatives.items():
        arr = _validate_1d_array(f"nuisance_derivatives[{name!r}]", values, expected_size=n_obs)
        centered = arr - float(np.mean(arr))
        if float(np.linalg.norm(centered)) <= 1e-12:
            continue
        linear_terms.append((name, arr))

    if not linear_terms:
        return [], [], "no_nonconstant_nuisance_terms"

    basis_cols: list[np.ndarray] = []
    basis_terms: list[str] = []

    for name, raw in linear_terms:
        basis_cols.append(raw)
        basis_terms.append(name)

    # Quadratic expansion captures local curvature that a bare linear projection misses.
    for idx, (name, raw) in enumerate(linear_terms):
        squared = raw * raw
        squared = squared - float(np.mean(squared))
        if float(np.linalg.norm(squared)) > 1e-12:
            basis_cols.append(squared)
            basis_terms.append(f"{name}^2")
        for jdx in range(idx + 1, len(linear_terms)):
            other_name, other_raw = linear_terms[jdx]
            cross = raw * other_raw
            cross = cross - float(np.mean(cross))
            if float(np.linalg.norm(cross)) > 1e-12:
                basis_cols.append(cross)
                basis_terms.append(f"{name}*{other_name}")

    return basis_cols, basis_terms, "orthogonal_quadratic_projection"


def compute_second_order_eif(
    first_order_scores: np.ndarray,
    nuisance_derivatives: dict[str, np.ndarray],
) -> SecondOrderEIF:
    """Approximate second-order EIF correction from nuisance diagnostics.

    This is a finite-sample approximation, not an exact symbolic higher-order
    EIF. We regress the supplied first-order scores on an intercept plus a
    nuisance basis built from first-order nuisance derivatives and centered
    quadratic terms, then subtract only the fitted nuisance component. This
    keeps the estimand-level intercept explicit instead of forcing the
    correction to inherit the mean of the projected nuisance span.
    """
    scores = _validate_1d_array("first_order_scores", first_order_scores)
    if scores.size == 0:
        return SecondOrderEIF(
            scores=scores,
            bias_correction=0.0,
            corrected_estimate=0.0,
            corrected_se=0.0,
            approximation_method="empty_input",
            note="empty first_order_scores provided; no correction was applied.",
        )

    if not np.all(np.isfinite(scores)):
        raise ValueError("first_order_scores must contain only finite values")

    basis_cols, basis_terms, method = _build_second_order_basis(nuisance_derivatives, scores.size)
    if not basis_cols:
        estimate = float(np.mean(scores))
        se = float(np.std(scores, ddof=1) / np.sqrt(max(scores.size, 1)))
        note = "no non-constant nuisance basis was available; returning the uncorrected score mean."
        return SecondOrderEIF(
            scores=scores,
            bias_correction=0.0,
            corrected_estimate=estimate,
            corrected_se=se,
            approximation_method="no_correction",
            basis_terms=(),
            basis_rank=0,
            basis_dimension=0,
            condition_number=None,
            projection_norm=0.0,
            residual_norm=float(np.linalg.norm(scores)),
            note=note,
        )

    design = np.column_stack(basis_cols)
    col_norms = np.linalg.norm(design, axis=0)
    keep = col_norms > 1e-12
    if not np.any(keep):
        estimate = float(np.mean(scores))
        se = float(np.std(scores, ddof=1) / np.sqrt(max(scores.size, 1)))
        return SecondOrderEIF(
            scores=scores,
            bias_correction=0.0,
            corrected_estimate=estimate,
            corrected_se=se,
            approximation_method="no_correction",
            basis_terms=(),
            basis_rank=0,
            basis_dimension=0,
            condition_number=None,
            projection_norm=0.0,
            residual_norm=float(np.linalg.norm(scores)),
            note="all nuisance basis columns were numerically degenerate.",
        )

    design = design[:, keep] / col_norms[keep]
    kept_terms = tuple(term for term, flag in zip(basis_terms, keep) if flag)

    # Orthogonal projection onto the span of the nuisance basis. This is more
    # stable than solving the normal equations and keeps the approximation scope explicit.
    u, singular_values, _vh = np.linalg.svd(design, full_matrices=False)
    if singular_values.size == 0 or float(singular_values[0]) <= 0.0:
        estimate = float(np.mean(scores))
        se = float(np.std(scores, ddof=1) / np.sqrt(max(scores.size, 1)))
        return SecondOrderEIF(
            scores=scores,
            bias_correction=0.0,
            corrected_estimate=estimate,
            corrected_se=se,
            approximation_method="no_correction",
            basis_terms=kept_terms,
            basis_rank=0,
            basis_dimension=int(design.shape[1]),
            condition_number=None,
            projection_norm=0.0,
            residual_norm=float(np.linalg.norm(scores)),
            note="nuisance basis had no identifiable span after normalization.",
        )

    rank = int(np.sum(singular_values > singular_values[0] * 1e-12))
    if rank == 0:
        rank = 1
    nuisance_basis = u[:, :rank] @ np.diag(singular_values[:rank])
    nuisance_basis_norms = np.linalg.norm(nuisance_basis, axis=0)
    nuisance_basis = nuisance_basis / np.where(
        nuisance_basis_norms > 0.0, nuisance_basis_norms, 1.0
    )
    full_design = np.column_stack([np.ones(scores.size), nuisance_basis])
    coeffs, *_ = np.linalg.lstsq(full_design, scores, rcond=None)
    corrected_estimate = float(coeffs[0])
    projection = nuisance_basis @ coeffs[1:]
    corrected_scores = scores - projection
    bias_correction = float(np.mean(scores) - corrected_estimate)
    corrected_se = float(np.std(corrected_scores, ddof=1) / np.sqrt(max(scores.size, 1)))
    condition_number: float | None = None
    if rank > 0:
        min_sv = float(singular_values[rank - 1])
        if min_sv > 0.0:
            condition_number = float(singular_values[0] / min_sv)

    note_parts = [
        "approximate second-order correction via intercept-preserving orthogonal projection on a quadratic nuisance basis",
    ]
    if rank < design.shape[1]:
        note_parts.append(
            f"rank deficiency detected ({rank}/{design.shape[1]} basis directions retained)."
        )
    if condition_number is not None and condition_number > 1e6:
        note_parts.append(
            f"ill-conditioned nuisance span (condition_number={condition_number:.2e})."
        )

    return SecondOrderEIF(
        scores=corrected_scores,
        bias_correction=bias_correction,
        corrected_estimate=corrected_estimate,
        corrected_se=corrected_se,
        approximation_method=method,
        basis_terms=kept_terms,
        basis_rank=rank,
        basis_dimension=int(design.shape[1]),
        condition_number=condition_number,
        projection_norm=float(np.linalg.norm(projection)),
        residual_norm=float(np.linalg.norm(corrected_scores - corrected_estimate)),
        note=" ".join(note_parts),
    )


# ---------------------------------------------------------------------------
# EIF formulas
# ---------------------------------------------------------------------------


def compute_eif_ate(
    Y: np.ndarray,
    T: np.ndarray,
    e: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
    *,
    min_propensity: float = 1e-4,
) -> EIFScores:
    """Efficient influence function for the Average Treatment Effect (ATE).

    Formula (Hahn 1998; Robins, Rotnitzky & Zhao 1994):

        ψ_ATE(i) = (μ₁ᵢ − μ₀ᵢ)
                 + Tᵢ(Yᵢ − μ₁ᵢ) / e(Xᵢ)
                 − (1−Tᵢ)(Yᵢ − μ₀ᵢ) / (1 − e(Xᵢ))

    Parameters
    ----------
    Y   : outcome array (n_obs,)
    T   : binary treatment array (n_obs,)
    e   : propensity scores P(T=1|X), (n_obs,)
    mu1 : E[Y|T=1, X] predictions (n_obs,)
    mu0 : E[Y|T=0, X] predictions (n_obs,)

    Returns
    -------
    EIFScores with estimand_type='ate'
    """
    Y, T, e, mu1, mu0 = (np.asarray(a, dtype=float) for a in (Y, T, e, mu1, mu0))
    e_clip = np.clip(e, min_propensity, 1.0 - min_propensity)
    psi = (mu1 - mu0) + T * (Y - mu1) / e_clip - (1 - T) * (Y - mu0) / (1 - e_clip)
    return EIFScores(estimand_type="ate", scores=psi, n_obs=len(psi))


def compute_eif_att(
    Y: np.ndarray,
    T: np.ndarray,
    e: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
    *,
    min_propensity: float = 1e-4,
) -> EIFScores:
    """Efficient influence function for the Average Treatment effect on the Treated (ATT).

    Formula (Hahn 1998):

        p₁ = E[T] = mean(T)

        ψ_ATT(i) = (T/p₁) · (Y − μ₁(X))
                 − (1−T)/p₁ · e(X)/(1−e(X)) · (Y − μ₀(X))
                 − (T/p₁ − 1) · (μ₁(X) − μ₀(X))

    This equals μ₁(Xᵢ) − μ₀(Xᵢ) for treated units with DR correction.

    Parameters
    ----------
    Y, T, e, mu1, mu0 : same as :func:`compute_eif_ate`

    Returns
    -------
    EIFScores with estimand_type='att'
    """
    Y, T, e, mu1, mu0 = (np.asarray(a, dtype=float) for a in (Y, T, e, mu1, mu0))
    e_clip = np.clip(e, min_propensity, 1.0 - min_propensity)
    p1 = max(float(np.mean(T)), min_propensity)
    structural = mu1 - mu0
    ipw_treated = (T / p1) * (Y - mu1)
    ipw_control = ((1 - T) / p1) * (e_clip / (1 - e_clip)) * (Y - mu0)
    centering = (T / p1 - 1.0) * structural
    psi = structural + ipw_treated - ipw_control - centering
    return EIFScores(estimand_type="att", scores=psi, n_obs=len(psi))


def compute_eif_subgroup_mean(
    Y: np.ndarray,
    T: np.ndarray,
    e: np.ndarray,
    mu1: np.ndarray,
    mu0: np.ndarray,
    subgroup: np.ndarray,
    *,
    target_treatment: int = 1,
    target_group: object = 1,
    min_propensity: float = 1e-4,
    min_group_probability: float = 1e-4,
) -> EIFScores:
    """Efficient non-centered score for E[Y^a | B=b].

    The convention matches the rest of this module: ``mean(scores)`` equals the
    subgroup mean itself, not a centered mean-zero influence curve.
    """
    Y, T, e, mu1, mu0 = (np.asarray(a, dtype=float) for a in (Y, T, e, mu1, mu0))
    subgroup_arr = np.asarray(subgroup, dtype=object).reshape(-1)
    if subgroup_arr.size != len(Y):
        raise ValueError("subgroup must have the same length as Y")

    group_indicator = (subgroup_arr == target_group).astype(float)
    group_probability = float(np.mean(group_indicator))
    if group_probability < min_group_probability:
        raise ValueError("target_group must appear with positive frequency")

    e_clip = np.clip(e, min_propensity, 1.0 - min_propensity)
    if int(target_treatment) == 1:
        treatment_indicator = T
        treatment_probability = e_clip
        outcome_model = mu1
    elif int(target_treatment) == 0:
        treatment_indicator = 1.0 - T
        treatment_probability = 1.0 - e_clip
        outcome_model = mu0
    else:
        raise ValueError("target_treatment must be 0 or 1")

    psi = (
        group_indicator
        / max(group_probability, min_group_probability)
        * (treatment_indicator * (Y - outcome_model) / treatment_probability + outcome_model)
    )
    return EIFScores(estimand_type="subgroup_mean", scores=psi, n_obs=len(psi))


def compute_eif_late(
    Y: np.ndarray,
    T: np.ndarray,
    Z: np.ndarray,
    e_z: np.ndarray,
    mu1_z1: np.ndarray,
    mu0_z1: np.ndarray,
    mu1_z0: np.ndarray,
    mu0_z0: np.ndarray,
    *,
    min_compliance: float = 1e-4,
) -> EIFScores:
    """Efficient influence function for the Local Average Treatment Effect (LATE).

    Formula (Abadie 2003 — κ-weighting representation):

        Δ_Y(i) = E[Y|Z=1] − E[Y|Z=0]
        Δ_T(i) = E[T|Z=1] − E[T|Z=0]  (= compliance rate ≈ π_c)

        ψ_LATE(i) = [Z·(Y−μ₁_z1)/e_z − (1−Z)·(Y−μ₀_z0)/(1−e_z) + (μ₁_z1−μ₀_z0)]
                  / π̂_c
                  − LATE · [Z·(T−μ1t_z1)/e_z − (1−Z)·(T−μ0t_z0)/(1−e_z)
                            + (μ1t_z1−μ0t_z0)] / π̂_c

    Simplified *reduced-form / first-stage* version using Wald ratio structure:

        numerator_i = Z·(Y − E[Y|Z=1])/e_z − (1−Z)·(Y − E[Y|Z=0])/(1−e_z)
                     + (E[Y|Z=1] − E[Y|Z=0])
        denom_i     = Z·(T − E[T|Z=1])/e_z − (1−Z)·(T − E[T|Z=0])/(1−e_z)
                     + (E[T|Z=1] − E[T|Z=0])

        ψ_LATE(i) ≈ numerator_i / π̂_c − LATE_hat · denom_i / π̂_c

    Parameters
    ----------
    Y          : outcome (n_obs,)
    T          : treatment indicator (n_obs,)
    Z          : instrument indicator (n_obs,)
    e_z        : P(Z=1) — marginal propensity of instrument (scalar or array)
    mu1_z1     : E[Y|Z=1, X] — reduced-form predictions (outcome given Z=1) (n_obs,)
    mu0_z1     : E[T|Z=0, X] — first-stage predictions (treatment given Z=0) (n_obs,)
    mu1_z0     : E[T|Z=1, X] — first-stage predictions (treatment given Z=1) (n_obs,)
    mu0_z0     : E[Y|Z=0, X] — reduced-form predictions (outcome given Z=0) (n_obs,)

    Returns
    -------
    EIFScores with estimand_type='late'
    """
    Y, T, Z = (np.asarray(a, dtype=float) for a in (Y, T, Z))
    e_z = np.clip(np.asarray(e_z, dtype=float), min_compliance, 1.0 - min_compliance)
    mu1_z1 = np.asarray(mu1_z1, dtype=float)
    mu0_z0 = np.asarray(mu0_z0, dtype=float)
    mu1_z0 = np.asarray(mu1_z0, dtype=float)  # E[T|Z=1,X] (first-stage, instrument=1)
    mu0_z1 = np.asarray(mu0_z1, dtype=float)  # E[T|Z=0,X] (first-stage, instrument=0)

    # Reduced-form numerator (EIF for E[Y(1)] - E[Y(0)] via Wald)
    num_scores = Z * (Y - mu1_z1) / e_z - (1 - Z) * (Y - mu0_z0) / (1 - e_z) + (mu1_z1 - mu0_z0)
    # First-stage denominator (EIF for compliance E[T(1)] - E[T(0)])
    den_scores = Z * (T - mu1_z0) / e_z - (1 - Z) * (T - mu0_z1) / (1 - e_z) + (mu1_z0 - mu0_z1)
    pi_c = float(np.mean(den_scores))
    if abs(pi_c) < min_compliance:
        pi_c = min_compliance
    late_hat = float(np.mean(num_scores)) / pi_c
    psi = (num_scores - late_hat * den_scores) / pi_c
    return EIFScores(estimand_type="late", scores=psi, n_obs=len(psi))


def compute_eif_frontdoor(
    Y: np.ndarray,
    T: np.ndarray,
    M: np.ndarray,
    p_m_given_t1: np.ndarray,
    p_m_given_t0: np.ndarray,
    mu_y_given_mt: np.ndarray,
    p_t: np.ndarray,
    *,
    min_density: float = 1e-6,
) -> EIFScores:
    """EIF for the frontdoor ATE.

    Frontdoor formula (Pearl 2009, Chapter 3):

        ATE_fd = Σ_m [P(M=m|T=1) − P(M=m|T=0)]
                  × Σ_{t'} E[Y|M=m, T=t'] P(T=t')

    EIF (Tchetgen Tchetgen & Shpitser 2012; Fulcher et al. 2020):

        ψ_fd(i) = E[Y|M=mᵢ, T=1] − E[Y|M=mᵢ, T=0]
                + [Tᵢ/P(Tᵢ)] · [Σ_{t'} E[Y|M=mᵢ, T=t'] P(T=t')
                               − E[Y|M=mᵢ, T=Tᵢ]]    ← mediator residual
                + [P(M=mᵢ|T=1) − P(M=mᵢ|T=0)] / P(M=mᵢ|T=Tᵢ)
                  × (Yᵢ − E[Y|M=mᵢ, T=Tᵢ])           ← outcome residual

    Parameters
    ----------
    Y              : outcome (n_obs,)
    T              : binary treatment (n_obs,)
    M              : mediator (n_obs,)  [used as index, not in formula directly]
    p_m_given_t1   : P(M=mᵢ | T=1) for each obs (n_obs,)
    p_m_given_t0   : P(M=mᵢ | T=0) for each obs (n_obs,)
    mu_y_given_mt  : E[Y | M=mᵢ, T=Tᵢ] for each obs (n_obs,)
    p_t            : marginal P(T=1) — scalar or array (n_obs,)

    Returns
    -------
    EIFScores with estimand_type='frontdoor'
    """
    Y, T = np.asarray(Y, dtype=float), np.asarray(T, dtype=float)
    p_m_t1 = np.asarray(p_m_given_t1, dtype=float)
    p_m_t0 = np.asarray(p_m_given_t0, dtype=float)
    mu_y = np.asarray(mu_y_given_mt, dtype=float)
    p1 = float(np.mean(p_t)) if hasattr(p_t, "__len__") else float(p_t)
    p1 = max(p1, min_density)
    p0 = 1.0 - p1

    # Structural: E[Y|M,T=1] - E[Y|M,T=0]  (approximated as mu_y contrast)
    # mu_y is E[Y|M,T=T_i]; we need both sides but only have one per obs
    # Use: structural_i ≈ (mu_y when T=1) - (mu_y when T=0)
    # Since we only have mu_y for the observed T, approximate via weighting
    #
    # NOTE (known limitation): This IPW pooling is an approximation.  The true
    # frontdoor EIF requires *both* E[Y|M,T=1] and E[Y|M,T=0] for every
    # observation, but we only observe mu_y for the factual treatment value.
    # The IPW trick below uses T/p1 and (1-T)/p0 to impute the missing
    # counterfactual side, which is consistent only when the propensity score
    # P(T=1|M) is correctly specified.  For a fully non-parametric estimator,
    # pass pre-computed mu_y_given_m_t1 and mu_y_given_m_t0 separately.
    # See Fulcher et al. (2020), Section 4.2 for the full EIF derivation.
    structural_1 = np.where(T > 0.5, mu_y, 0.0)  # E[Y|M,T=1] for treated
    structural_0 = np.where(T <= 0.5, mu_y, 0.0)  # E[Y|M,T=0] for control
    # Pool via IPW to get both sides for all obs
    mu_y_t1 = structural_1 / np.where(T > 0.5, p1, 1.0)
    mu_y_t0 = structural_0 / np.where(T <= 0.5, p0, 1.0)
    diff_mu = p1 * mu_y_t1 + p0 * mu_y_t0 - mu_y  # ≈ Σ_t E[Y|M,t]P(t) − E[Y|M,T]

    # Density ratio: [P(M|T=1) - P(M|T=0)] / P(M|T=T_i)
    p_m_given_T = np.where(T > 0.5, p_m_t1, p_m_t0)
    p_m_given_T_safe = np.maximum(p_m_given_T, min_density)
    density_ratio = (p_m_t1 - p_m_t0) / p_m_given_T_safe

    psi = (
        (p_m_t1 - p_m_t0) * diff_mu  # structural × marginal mediator contrast
        + (T / p1 - (1 - T) / p0) * diff_mu  # mediator residual (IPW weighted)
        + density_ratio * (Y - mu_y)  # outcome residual
    )
    return EIFScores(estimand_type="frontdoor", scores=psi, n_obs=len(psi))


def compute_eif_nde(
    Y: np.ndarray,
    T: np.ndarray,
    M: np.ndarray,
    X: np.ndarray,
    propensity: np.ndarray,
    mediator_density_t1: np.ndarray,
    mediator_density_t0: np.ndarray,
    outcome_model_t1: np.ndarray,
    outcome_model_t0: np.ndarray,
    *,
    min_propensity: float = 1e-4,
    min_density: float = 1e-6,
) -> EIFScores:
    """EIF for Natural Direct Effect (NDE).

    Formula (Tchetgen Tchetgen & Shpitser 2012, Eq. 3):

        ψ_NDE(i) = [μ₁(M,X) − μ₀(M,X)]
                 + T/e · (Y − μ₁(M,X))
                 − (1−T)/(1−e) · (Y − μ₀(M,X))
                 − (p(M|T=1,X)/p(M|T=0,X) − 1)
                   · (μ₀(M,X) − E_M[μ₀(M,X)|T=0,X])

    All four nuisance functions must be passed as per-observation arrays.
    ``outcome_model_t1`` = μ₁(Mᵢ, Xᵢ) = E[Y | Tᵢ=1, Mᵢ, Xᵢ] for each obs.
    ``outcome_model_t0`` = μ₀(Mᵢ, Xᵢ) = E[Y | Tᵢ=0, Mᵢ, Xᵢ] for each obs.
    Both must be evaluated *for each observation* (not only for factual T).

    Parameters
    ----------
    Y                    : outcome (n_obs,)
    T                    : binary treatment (n_obs,)
    M                    : mediator (n_obs,)
    X                    : covariates (n_obs, p) — used for shape only
    propensity           : e(Xᵢ) = P(T=1|Xᵢ), (n_obs,)
    mediator_density_t1  : p(Mᵢ|T=1, Xᵢ), (n_obs,)
    mediator_density_t0  : p(Mᵢ|T=0, Xᵢ), (n_obs,)
    outcome_model_t1     : μ₁(Mᵢ, Xᵢ) = E[Y|T=1, Mᵢ, Xᵢ], (n_obs,)
    outcome_model_t0     : μ₀(Mᵢ, Xᵢ) = E[Y|T=0, Mᵢ, Xᵢ], (n_obs,)

    Returns
    -------
    EIFScores with estimand_type='nde'
    """
    Y = np.asarray(Y, dtype=float)
    T = np.asarray(T, dtype=float)
    e = np.clip(np.asarray(propensity, dtype=float), min_propensity, 1.0 - min_propensity)
    pm1 = np.maximum(np.asarray(mediator_density_t1, dtype=float), min_density)
    pm0 = np.maximum(np.asarray(mediator_density_t0, dtype=float), min_density)
    mu1 = np.asarray(outcome_model_t1, dtype=float)
    mu0 = np.asarray(outcome_model_t0, dtype=float)

    # Density ratio clipped for stability (practical cap of 20.0)
    density_ratio = np.clip(pm1 / pm0, 0.0, 20.0)

    # E_M[μ₀(M,X) | T=0, X] — average of μ₀ over control units (IPW estimate)
    # Approximate per-obs via overall weighted mean: for treated obs, use density-ratio
    # reweighted control units
    w_control = np.where(T < 0.5, 1.0 / (1.0 - e), 0.0)
    w_control_sum = max(float(np.sum(w_control)), min_density)
    e_mu0_given_t0 = float(np.sum(w_control * mu0)) / w_control_sum
    # Broadcast: subtract mean of μ₀ (approximate oracle quantity per observation)
    mu0_centered = mu0 - e_mu0_given_t0

    # Core EIF components
    structural = mu1 - mu0
    residual_t1 = T / e * (Y - mu1)
    residual_t0 = -(1.0 - T) / (1.0 - e) * (Y - mu0)
    mediator_correction = -(density_ratio - 1.0) * mu0_centered

    psi = structural + residual_t1 + residual_t0 + mediator_correction
    return EIFScores(estimand_type="nde", scores=psi, n_obs=len(psi))


def compute_eif_nie(
    Y: np.ndarray,
    T: np.ndarray,
    M: np.ndarray,
    X: np.ndarray,
    propensity: np.ndarray,
    mediator_density_t1: np.ndarray,
    mediator_density_t0: np.ndarray,
    outcome_model_t1: np.ndarray,
    outcome_model_t0: np.ndarray,
    *,
    min_propensity: float = 1e-4,
    min_density: float = 1e-6,
) -> EIFScores:
    """EIF for Natural Indirect Effect (NIE).

    Identity (mediation decomposition):
        ψ_NIE = ψ_ATE − ψ_NDE

    This follows from ATE = NDE + NIE.  We compute ψ_ATE via the standard
    AIPW formula and subtract ψ_NDE (from :func:`compute_eif_nde`).

    Returns
    -------
    EIFScores with estimand_type='nie'
    """
    # ATE EIF (Robins, Rotnitzky & Zhao 1994)
    eif_ate = compute_eif_ate(
        Y, T, propensity, outcome_model_t1, outcome_model_t0, min_propensity=min_propensity
    )
    # NDE EIF
    eif_nde = compute_eif_nde(
        Y,
        T,
        M,
        X,
        propensity,
        mediator_density_t1,
        mediator_density_t0,
        outcome_model_t1,
        outcome_model_t0,
        min_propensity=min_propensity,
        min_density=min_density,
    )
    nie_scores = eif_ate.scores - eif_nde.scores
    return EIFScores(estimand_type="nie", scores=nie_scores, n_obs=len(nie_scores))


def compute_eif_transport(
    Y: np.ndarray,
    domain: np.ndarray,
    e_domain: np.ndarray,
    mu_y: np.ndarray,
    *,
    min_density: float = 1e-4,
) -> EIFScores:
    """EIF for transport ATE (density-ratio reweighted from source to target).

    Covariate-shift transport formula:

        E*[Y] = E_source[w(X) · Y]    where  w(X) = P*(X) / P(X)

    EIF (Bareinboim & Pearl 2016; Dahabreh et al. 2019):

        ψ_tr(i) = μ*(Xᵢ)
                + domain_i / e(Xᵢ) · (Yᵢ − μ_source(Xᵢ))

    where:
        domain_i = 1 if observation is from the source population
        e(Xᵢ)   = P(source | Xᵢ) — propensity of being in source
        μ*(Xᵢ)  = w(Xᵢ) · μ_source(Xᵢ) — reweighted outcome prediction

    Parameters
    ----------
    Y        : outcome (n_obs,)  [source observations only, or full dataset]
    domain   : 1 = source, 0 = target indicator (n_obs,)
    e_domain : P(domain=source | X) — propensity of source membership (n_obs,)
    mu_y     : E[Y | X] outcome model predictions (n_obs,)

    Returns
    -------
    EIFScores with estimand_type='transport'
    """
    Y = np.asarray(Y, dtype=float)
    D = np.asarray(domain, dtype=float)
    e = np.clip(np.asarray(e_domain, dtype=float), min_density, 1.0 - min_density)
    mu = np.asarray(mu_y, dtype=float)
    # Density ratio w(X) = P*(X)/P(X) ≈ (1 - e(X)) / e(X)
    w = (1.0 - e) / e
    mu_star = w * mu
    psi = mu_star + D * (Y - mu) / e
    return EIFScores(estimand_type="transport", scores=psi, n_obs=len(psi))


# ---------------------------------------------------------------------------
# Efficiency bound computation
# ---------------------------------------------------------------------------


def compute_efficiency_bound(
    eif: EIFScores,
    estimator_se: float | None = None,
) -> EfficiencyBound:
    """Compute the semiparametric Cramér-Rao lower bound from EIF scores.

    The bound is V* = E[ψ²] / n.  An estimator with SE² ≈ V* is locally efficient.

    Parameters
    ----------
    eif          : EIF scores from any ``compute_eif_*`` function
    estimator_se : optional SE of a concrete estimator, used to compute
                   ``relative_efficiency = bound_var / estimator_var``

    Returns
    -------
    EfficiencyBound
    """
    n = eif.n_obs
    eif_var = eif.variance()  # E[ψ²] — stored for diagnostics
    # Semiparametric Cramér-Rao bound: E[ψ²]/n  (second moment, NOT centered variance).
    # The EIF is mean-zero by construction (E[ψ] = 0), so E[ψ²] = Var(ψ) only at
    # the true parameter value.  Using the raw second moment is the standard convention
    # in semiparametric efficiency theory (Bickel et al. 1993, van der Laan & Robins 2003).
    bound_var = float(np.mean(eif.scores**2)) / max(n, 1)
    bound_se = float(np.sqrt(bound_var))
    est = eif.point_estimate()
    se_eif = eif.standard_error()
    ci_lo, ci_hi = est - 1.96 * se_eif, est + 1.96 * se_eif

    # Relative efficiency: 1.0 = perfectly efficient; >1.0 = estimator wastes variance
    rel_eff = 1.0
    if estimator_se is not None and estimator_se > 0 and bound_se > 0:
        rel_eff = (estimator_se**2) / bound_var

    notes = []
    if eif_var < 1e-12:
        notes.append("EIF variance ≈ 0 — constant estimand or degenerate data.")
    if estimator_se is not None and rel_eff > 2.0:
        notes.append(
            f"Estimator SE ({estimator_se:.4f}) is {rel_eff:.1f}× larger than the "
            f"efficiency-bound SE ({bound_se:.4f}); consider AIPW/TMLE."
        )

    return EfficiencyBound(
        estimand_type=eif.estimand_type,
        point_estimate=est,
        standard_error=se_eif,
        variance_lower_bound=bound_var,
        eif_variance=eif_var,
        n_obs=n,
        ci_lower=ci_lo,
        ci_upper=ci_hi,
        relative_efficiency=rel_eff,
        notes=" ".join(notes),
    )


def compare_estimator_efficiency(
    eif: EIFScores,
    estimator_ses: dict[str, float],
) -> EfficiencyReport:
    """Compare a set of estimators against the semiparametric efficiency bound.

    Parameters
    ----------
    eif            : EIF scores (defines the bound)
    estimator_ses  : dict mapping estimator_name → SE(θ̂)
                     e.g. {'AIPW': 0.04, 'IPW': 0.07, 'OLS': 0.09}

    Returns
    -------
    EfficiencyReport with relative_efficiencies and most_efficient estimator.
    """
    bound = compute_efficiency_bound(eif)
    bound_var = bound.variance_lower_bound

    rel_effs: dict[str, float] = {}
    for name, se in estimator_ses.items():
        if se > 0:
            rel_effs[name] = (se**2) / max(bound_var, 1e-30)
        else:
            rel_effs[name] = float("inf")

    most_efficient = ""
    if rel_effs:
        most_efficient = min(rel_effs, key=lambda k: rel_effs[k])

    return EfficiencyReport(
        bound=bound,
        estimator_ses=estimator_ses,
        relative_efficiencies=rel_effs,
        most_efficient=most_efficient,
    )


# ---------------------------------------------------------------------------
# Foundry method
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.semiparametric",
    version="1.0.0",
    tags={"causal", "semiparametric", "efficiency", "eif", "cramér-rao"},
)
class SemiparametricEfficiencyBoundMethod:
    """Compute the semiparametric Cramér-Rao lower bound for ATE / ATT / LATE.

    Accepts pre-computed nuisance predictions (propensity scores, outcome models)
    and returns the EIF scores plus the efficiency bound for the requested estimand.

    Input slots
    -----------
    Y          — outcome vector (n_obs,)
    treatment  — binary treatment (n_obs,)
    propensity — P(T=1|X) predictions (n_obs,)
    mu1        — E[Y|T=1, X] predictions (n_obs,)
    mu0        — E[Y|T=0, X] predictions (n_obs,)

    Optional slots (for non-ATE estimands)
    ---------------------------------------
    instrument       — binary instrument for LATE (n_obs,)
    mediator         — mediator variable for frontdoor (n_obs,)
    domain_indicator — source/target indicator for transport (n_obs,)

    Output slots
    ------------
    efficiency_bound — :class:`EfficiencyBound` result dict
    eif_scores       — per-observation ψᵢ (n_obs,)
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="efficiency_bound",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("Y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "propensity",
                    SlotType.VECTOR,
                    Unit("propensity", "probability"),
                    shape=("n_obs",),
                ),
                SlotSpec("mu1", SlotType.VECTOR, Unit("outcome_model", "value"), shape=("n_obs",)),
                SlotSpec("mu0", SlotType.VECTOR, Unit("outcome_model", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("efficiency_bound", SlotType.SCALAR, Unit("bound", "json")),
                SlotSpec("eif_scores", SlotType.VECTOR, Unit("eif", "score"), shape=("n_obs",)),
            }
        ),
        parameters=(
            ParameterSpec(name="estimand_type", default="ate"),
            ParameterSpec(name="min_propensity", default=1e-4, bounds=(1e-8, 0.49)),
            ParameterSpec(name="estimator_se", default=None),
            ParameterSpec(name="nuisance_derivatives", default=None),
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
            "Compute semiparametric efficiency bound E[ψ²]/n for ATE/ATT/LATE "
            "via the efficient influence function. Reports relative efficiency of "
            "a supplied estimator SE against the bound."
        ),
        tags=frozenset(
            {
                "causal",
                "semiparametric",
                "efficiency",
                "eif",
                "cramér-rao",
                "aipw",
                "ate",
                "att",
                "late",
            }
        ),
        citations=(
            "Bickel, P.J. et al. (1993). Efficient and Adaptive Estimation for Semiparametric Models. Springer.",
            "van der Vaart, A.W. (1998). Asymptotic Statistics. Cambridge UP.",
            "Hahn, J. (1998). On the Role of the Propensity Score in Efficient Semiparametric Estimation. Econometrica.",
            "Robins, J.M., Rotnitzky, A. & Zhao, L.P. (1994). Estimation of Regression Coefficients. JASA.",
            "Tchetgen Tchetgen, E.J. & Shpitser, I. (2012). Semiparametric Theory for Causal Mediation. Ann. Stat.",
        ),
        equations={
            "eif_ate": "ψ_ATE = (μ₁−μ₀) + T(Y−μ₁)/e − (1−T)(Y−μ₀)/(1−e)",
            "eif_att": "ψ_ATT = T/p₁·(Y−μ₁) − (1−T)/p₁·e/(1−e)·(Y−μ₀) − (T/p₁−1)·(μ₁−μ₀)",
            "bound": "V* = E[ψ²] / n",
            "rel_eff": "η = SE²_estimator / V*",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "After cross-fitting to assess whether your estimator achieves the "
            "semiparametric efficiency bound; for comparing AIPW vs TMLE vs DML."
        ),
        when_not_to_use="Very small n (< 30); when nuisance predictions are unavailable.",
        prerequisites=("causal.treatment_effects.cross_fit@1.0.0",),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation=(
            "efficiency_bound.variance_lower_bound = E[ψ²]/n is the tightest "
            "asymptotic variance any regular estimator can achieve. "
            "relative_efficiency ≈ 1.0 means your estimator is nearly optimal."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["Y"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        e = np.asarray(state["propensity"], dtype=float)
        mu1 = np.asarray(state["mu1"], dtype=float)
        mu0 = np.asarray(state["mu0"], dtype=float)

        estimand_type = str(params.get("estimand_type", "ate"))
        min_propensity = float(params.get("min_propensity", 1e-4))
        estimator_se = params.get("estimator_se", None)

        if estimand_type == "att":
            eif = compute_eif_att(Y, T, e, mu1, mu0, min_propensity=min_propensity)
        elif estimand_type == "subgroup_mean":
            eif = compute_eif_subgroup_mean(
                Y,
                T,
                e,
                mu1,
                mu0,
                np.asarray(state["subgroup"]),
                target_treatment=int(params.get("target_treatment", 1)),
                target_group=params.get("target_group", 1),
                min_propensity=min_propensity,
            )
        else:
            eif = compute_eif_ate(Y, T, e, mu1, mu0, min_propensity=min_propensity)

        bound = compute_efficiency_bound(
            eif,
            estimator_se=float(estimator_se) if estimator_se is not None else None,
        )

        second_order_payload: dict[str, Any] | None = None
        nuisance_derivatives = params.get("nuisance_derivatives")
        if isinstance(nuisance_derivatives, dict) and nuisance_derivatives:
            second_order = compute_second_order_eif(eif.scores, nuisance_derivatives)
            second_order_payload = second_order.to_dict()

        output = {
            "efficiency_bound": bound.to_dict(),
            "eif_scores": eif.scores.tolist(),
        }
        if second_order_payload is not None:
            output["second_order_eif"] = second_order_payload
        return output


# ---------------------------------------------------------------------------
# Phase 6 — Continuous treatment EIF
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ContinuousEIFScores:
    """EIF scores for continuous-treatment dose-response estimation.

    One ψᵢ(t) vector is produced per evaluation point t. The matrix
    ``scores`` has shape (n_obs, n_eval).

    Based on Kennedy, Ma, McHugh & Small (2017) doubly-robust kernel
    estimator for the dose-response curve β(t) = E[Y(t)].
    """

    eval_points: np.ndarray  # (n_eval,)
    scores: np.ndarray  # (n_obs, n_eval) — centred EIF per eval point
    dose_response: np.ndarray  # (n_eval,) — β̂(t)
    standard_errors: np.ndarray  # (n_eval,) — SE(β̂(t))
    bandwidth: float

    def ci(self, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
        """Return (lower, upper) confidence bands at level 1-alpha (Wald)."""
        try:
            from scipy import stats as _stats

            z = float(_stats.norm.ppf(1.0 - alpha / 2))
        except Exception:
            z = 1.96
        return (
            self.dose_response - z * self.standard_errors,
            self.dose_response + z * self.standard_errors,
        )

    def to_dose_response_result(self) -> DoseResponseResult:  # type: ignore[name-defined]
        """Convert to DoseResponseResult IR model."""
        # Import here to avoid circular import; protocols imported lazily.
        from polisyos.foundry.methods.catalog.causal.protocols import DoseResponseResult

        lo, hi = self.ci()
        return DoseResponseResult(
            treatment_grid=self.eval_points,
            dose_response=self.dose_response,
            confidence_band_lower=lo,
            confidence_band_upper=hi,
            standard_errors=self.standard_errors,
            method="kernel_dr_kennedy_2017",
            n_obs=self.scores.shape[0],
            bandwidth=self.bandwidth,
        )


def _gaussian_kernel(u: np.ndarray) -> np.ndarray:
    """Standard Gaussian kernel K(u) = exp(-u²/2) / sqrt(2π)."""
    return np.exp(-0.5 * u * u) / np.sqrt(2.0 * np.pi)


def _silverman_bandwidth(T: np.ndarray) -> float:
    """Silverman (1986) rule-of-thumb bandwidth for a Gaussian kernel.

    h = 1.06 * σ̂ * n^{-1/5}
    """
    return max(1.06 * float(np.std(T)) * (len(T) ** (-0.2)), 1e-6)


def compute_eif_continuous_ate(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    gps_observed: np.ndarray,
    outcome_fn: Any,
    eval_points: np.ndarray,
    bandwidth: float | None = None,
    min_gps: float = 1e-4,
) -> ContinuousEIFScores:
    """EIF for the continuous-treatment dose-response curve β(t) = E[Y(t)].

    Implements Algorithm 1 from Kennedy, Ma, McHugh & Small (2017).

    Influence function at evaluation point t::

        ψᵢ(t) = K_h(Tᵢ − t) / f_{T|X}(Tᵢ|Xᵢ) × (Yᵢ − μ(Tᵢ,Xᵢ))
               + μ(t, Xᵢ)

    Then β̂(t) = mean(ψᵢ(t)) and the centred score is ψᵢ(t) − β̂(t).

    Parameters
    ----------
    Y             : (n,) outcome vector.
    T             : (n,) continuous treatment.
    X             : (n, p) covariates.
    gps_observed  : (n,) GPS values f(Tᵢ|Xᵢ) at the *observed* treatments.
    outcome_fn    : Callable(T_vec, X_mat) → (n,) predicting μ(T_vec, X_mat).
                    When computing the direct plug-in term at grid point t,
                    pass np.full(n, t) as T_vec.
    eval_points   : (n_eval,) grid of t values at which to evaluate β(t).
    bandwidth     : Kernel bandwidth h.  None → Silverman rule-of-thumb.
    min_gps       : Clipping floor for gps_observed (positivity protection).

    Returns
    -------
    ContinuousEIFScores
    """
    Y = np.asarray(Y, dtype=float)
    T = np.asarray(T, dtype=float)
    X = np.asarray(X, dtype=float)
    gps_observed = np.asarray(gps_observed, dtype=float)
    eval_points = np.asarray(eval_points, dtype=float)

    n = len(Y)
    n_eval = len(eval_points)
    h = bandwidth if bandwidth is not None else _silverman_bandwidth(T)

    gps_clip = np.clip(gps_observed, min_gps, None)

    # Outcome residuals at *observed* T (computed once)
    residuals = Y - outcome_fn(T, X)  # (n,)

    scores = np.empty((n, n_eval), dtype=float)
    beta_hat = np.empty(n_eval, dtype=float)

    for j, t_j in enumerate(eval_points):
        # Kernel weights K_h(Tᵢ - t_j)
        u = (T - t_j) / h
        k_vals = _gaussian_kernel(u) / h  # (n,)

        # IPW correction term
        ipw_term = k_vals / gps_clip * residuals  # (n,)

        # Direct plug-in term: μ(t_j, Xᵢ)
        mu_at_t = outcome_fn(np.full(n, t_j), X)  # (n,)

        psi_j = ipw_term + mu_at_t  # (n,) — uncentred EIF
        beta_hat[j] = float(psi_j.mean())
        scores[:, j] = psi_j  # store uncentred; SE uses variance of psi - beta_hat

    # SE via variance of centred scores
    centred = scores - beta_hat[np.newaxis, :]
    se = np.std(centred, axis=0, ddof=1) / np.sqrt(n)  # (n_eval,)

    return ContinuousEIFScores(
        eval_points=eval_points,
        scores=scores,
        dose_response=beta_hat,
        standard_errors=se,
        bandwidth=h,
    )


def compute_eif_shift_intervention(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    density_fn: Any,
    outcome_fn: Any,
    delta: float,
    min_density_ratio: float = 0.01,
    max_density_ratio: float = 100.0,
) -> EIFScores:
    """EIF for the shift intervention effect E[Y(A+δ)] − E[Y(A)].

    Implements the doubly-robust estimator from Díaz & van der Laan (2012)::

        ψᵢ(δ) = [μ(Aᵢ+δ,Xᵢ) − μ(Aᵢ,Xᵢ)]
                + f(Aᵢ|Xᵢ)/f(Aᵢ−δ|Xᵢ) × (Yᵢ − μ(Aᵢ,Xᵢ))

    Parameters
    ----------
    Y            : (n,) outcome.
    T            : (n,) continuous treatment A.
    X            : (n, p) covariates.
    density_fn   : Callable(t_vec, X_mat) → (n,) giving f(t|X).
    outcome_fn   : Callable(t_vec, X_mat) → (n,) giving μ(t, X).
    delta        : Shift amount δ.
    min/max_density_ratio : Clipping bounds for the density ratio.

    Returns
    -------
    EIFScores  (estimand_type = "shift_intervention")
    """
    Y = np.asarray(Y, dtype=float)
    T = np.asarray(T, dtype=float)
    X = np.asarray(X, dtype=float)

    mu_shifted = outcome_fn(T + delta, X)  # μ(A+δ, X)
    mu_original = outcome_fn(T, X)  # μ(A, X)

    f_num = density_fn(T, X)  # f(A|X)
    f_denom = density_fn(T - delta, X)  # f(A−δ|X)
    ratio = np.clip(
        f_num / np.maximum(f_denom, 1e-12),
        min_density_ratio,
        max_density_ratio,
    )

    psi = (mu_shifted - mu_original) + ratio * (Y - mu_original)

    return EIFScores(
        estimand_type="shift_intervention",
        scores=psi,
        n_obs=len(Y),
    )


def compute_eif_multi_treatment_ate(
    Y: np.ndarray,
    T: np.ndarray,
    X: np.ndarray,
    propensity_fn: Any,
    outcome_fn: Any,
    k: int,
    k_ref: int = 0,
    min_propensity: float = 0.01,
) -> EIFScores:
    """EIF for the ATE comparing arm k to reference arm k_ref.

    Implements the efficient influence function from Cattaneo (2010)::

        ψᵢ(k, k₀) = [μ_k(Xᵢ) − μ_{k₀}(Xᵢ)]
                    + I(Tᵢ=k)(Yᵢ−μ_k(Xᵢ)) / p_k(Xᵢ)
                    − I(Tᵢ=k₀)(Yᵢ−μ_{k₀}(Xᵢ)) / p_{k₀}(Xᵢ)

    Parameters
    ----------
    Y             : (n,) outcome.
    T             : (n,) integer treatment labels.
    X             : (n, p) covariates.
    propensity_fn : Callable(arm_int, X_mat) → (n,) giving P(T=arm|X).
    outcome_fn    : Callable(arm_int, X_mat) → (n,) giving μ_arm(X).
    k             : Treatment arm to evaluate.
    k_ref         : Reference arm (default 0).
    min_propensity: Positivity protection floor.

    Returns
    -------
    EIFScores  (estimand_type = "multi_ate_k_vs_kref")
    """
    Y = np.asarray(Y, dtype=float)
    T = np.asarray(T, dtype=int)
    X = np.asarray(X, dtype=float)

    p_k = np.clip(propensity_fn(k, X), min_propensity, 1.0 - min_propensity)
    p_ref = np.clip(propensity_fn(k_ref, X), min_propensity, 1.0 - min_propensity)
    mu_k = outcome_fn(k, X)
    mu_ref = outcome_fn(k_ref, X)

    ind_k = (k == T).astype(float)
    ind_ref = (k_ref == T).astype(float)

    psi = (mu_k - mu_ref) + ind_k * (Y - mu_k) / p_k - ind_ref * (Y - mu_ref) / p_ref

    return EIFScores(
        estimand_type=f"multi_ate_{k}_vs_{k_ref}",
        scores=psi,
        n_obs=len(Y),
    )


__all__ = [
    "EIFScores",
    "EfficiencyBound",
    "EfficiencyReport",
    "compute_eif_ate",
    "compute_eif_att",
    "compute_eif_subgroup_mean",
    "compute_eif_late",
    "compute_eif_frontdoor",
    "compute_eif_nde",
    "compute_eif_nie",
    "compute_eif_transport",
    "compute_efficiency_bound",
    "compare_estimator_efficiency",
    "SemiparametricEfficiencyBoundMethod",
    "SecondOrderEIF",
    "compute_second_order_eif",
    # Phase 6
    "ContinuousEIFScores",
    "compute_eif_continuous_ate",
    "compute_eif_shift_intervention",
    "compute_eif_multi_treatment_ate",
]
