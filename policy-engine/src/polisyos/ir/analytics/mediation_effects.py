"""Mediation effects IR types.

Covers:
1. **Natural Direct Effect (NDE)** and **Natural Indirect Effect (NIE)**
   via semiparametric cross-fitting (Tchetgen Tchetgen & Shpitser 2012).

2. **Path-Specific Effects (PSE)**
   via the Avin-Shpitser-Pearl recanting witness criterion (2005).

3. **MediationDecomposition** — unified result container for NDE/NIE/CDE.

All models: ``ConfigDict(extra="forbid", frozen=True)``, ``schema_version="1.0"``.

References
----------
Tchetgen Tchetgen, E.J. & Shpitser, I. (2012). Semiparametric Theory for
    Causal Mediation Analysis. Ann. Stat.
Avin, C., Shpitser, I. & Pearl, J. (2005). Identifiability of Path-Specific
    Effects. IJCAI.
Pearl, J. (2001). Direct and Indirect Effects. UAI.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._internal.validation import (
    ensure_confidence_interval,
    ensure_disjoint_sets,
    ensure_finite_numeric,
    ensure_non_empty_path,
    ensure_unique_ids,
)

MAX_MEDIATION_PATH_DEPTH = 16


class PathSpecificQuery(BaseModel):
    """Query specification for path-specific effects.

    Identifies which causal paths from ``treatment`` to ``outcome`` are
    "active" (allowed to vary) vs. "fixed" (blocked to their natural values
    under a reference treatment level).

    For NDE (Natural Direct Effect):
        - active_paths: [("treatment", "outcome")]  ← direct path only
        - fixed_paths: any mediator paths

    For NIE (Natural Indirect Effect):
        - active_paths: all paths through mediators
        - fixed_paths: ["treatment", "outcome"] ← direct path
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    treatment: str
    """Treatment variable name."""

    outcome: str
    """Outcome variable name."""

    mediators: tuple[str, ...] = ()
    """Mediator variable(s) on the causal path."""

    active_paths: tuple[tuple[str, ...], ...] = ()
    """Paths that are allowed to vary with treatment.

    Each path is a tuple of variable names from treatment to outcome.
    Empty tuple means all paths are active (= ATE estimand).
    """

    fixed_paths: tuple[tuple[str, ...], ...] = ()
    """Paths that are blocked (frozen to reference-treatment levels)."""

    reference_treatment: float = 0.0
    """Reference (control) value of treatment."""

    active_treatment: float = 1.0
    """Active (treated) value of treatment."""

    conditioning: tuple[str, ...] = ()
    """Observed conditioning variables for conditional path-specific queries."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_query(self) -> PathSpecificQuery:
        treatment = self.treatment.strip()
        outcome = self.outcome.strip()
        if not treatment:
            raise ValueError("treatment must be non-empty")
        if not outcome:
            raise ValueError("outcome must be non-empty")
        if treatment == outcome:
            raise ValueError("treatment and outcome must be distinct")

        ensure_unique_ids(self.mediators, key_fn=lambda item: item, label="mediators")
        ensure_unique_ids(
            self.conditioning,
            key_fn=lambda item: item,
            label="conditioning",
        )
        ensure_disjoint_sets(
            self.mediators,
            (treatment, outcome),
            label="mediators and treatment/outcome",
        )
        ensure_disjoint_sets(
            self.conditioning,
            (treatment, outcome),
            label="conditioning and treatment/outcome",
        )
        ensure_finite_numeric(self.reference_treatment, field_name="reference_treatment")
        ensure_finite_numeric(self.active_treatment, field_name="active_treatment")
        if self.active_treatment == self.reference_treatment:
            raise ValueError("active_treatment and reference_treatment must differ")

        normalized_active = _normalize_paths(
            self.active_paths,
            label="active_paths",
            treatment=treatment,
            outcome=outcome,
        )
        normalized_fixed = _normalize_paths(
            self.fixed_paths,
            label="fixed_paths",
            treatment=treatment,
            outcome=outcome,
        )
        ensure_disjoint_sets(
            normalized_active,
            normalized_fixed,
            label="active_paths and fixed_paths",
        )
        return self


class MediationDecomposition(BaseModel):
    """Full mediation decomposition: NDE, NIE, total effect.

    Estimates are obtained via cross-fitted EIF (Tchetgen Tchetgen &
    Shpitser 2012, Eq. 3) which is doubly-robust and locally efficient.

    Decomposition identity:
        ATE = NDE + NIE

    In practice: nde + nie ≈ total_effect (small discrepancy from
    finite-sample cross-fitting noise is normal).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    # Core estimates
    nde: float
    """Natural Direct Effect: E[Y(1, M(0))] - E[Y(0, M(0))]."""

    nie: float
    """Natural Indirect Effect: E[Y(1, M(1))] - E[Y(1, M(0))]."""

    total_effect: float
    """ATE = NDE + NIE."""

    cde: float | None = None
    """Controlled Direct Effect at mediator_reference_level (optional)."""

    # Standard errors
    nde_se: float | None = None
    """Standard error of NDE estimate."""

    nie_se: float | None = None
    """Standard error of NIE estimate."""

    # Confidence intervals (95%)
    nde_ci: tuple[float, float] | None = None
    """95% Wald CI for NDE."""

    nie_ci: tuple[float, float] | None = None
    """95% Wald CI for NIE."""

    # Estimation metadata
    n_folds: int = 2
    """Number of cross-fitting folds used."""

    n_obs: int = 0
    """Number of observations."""

    estimation_method: str = "eif_cross_fit"
    """Estimation approach used: ``'eif_cross_fit'`` | ``'ols_baron_kenny'``."""

    # Sensitivity
    sensitivity_rho_range: tuple[float, ...] | None = None
    """ρ values used in sensitivity analysis, if any."""

    sensitivity_nde: tuple[float, ...] | None = None
    """Sensitivity-corrected NDE for each ρ in ``sensitivity_rho_range``."""

    sensitivity_nie: tuple[float, ...] | None = None
    """Sensitivity-corrected NIE for each ρ in ``sensitivity_rho_range``."""

    # Interpretation helpers
    proportion_mediated: float | None = None
    """NIE / ATE — fraction of total effect via mediator (None if ATE ≈ 0)."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, payload: Any) -> Any:
        return cls.normalize_payload(payload)

    @classmethod
    def normalize_payload(cls, payload: Any) -> Any:
        """Return a decomposition payload with explicit derived ratios filled."""

        if not isinstance(payload, dict):
            return payload
        normalized = dict(payload)
        if normalized.get("proportion_mediated") is not None:
            return normalized
        try:
            total_effect = float(normalized.get("total_effect"))
            nie = float(normalized.get("nie"))
        except (TypeError, ValueError):
            return normalized
        if abs(total_effect) > 1.0e-12:
            normalized["proportion_mediated"] = max(-10.0, min(10.0, nie / total_effect))
        return normalized

    @classmethod
    def from_effects(cls, **payload: Any) -> MediationDecomposition:
        """Construct a decomposition after applying explicit derived defaults."""

        return cls.model_validate(cls.normalize_payload(payload))

    @model_validator(mode="after")
    def validate_decomposition(self) -> MediationDecomposition:
        ensure_finite_numeric(self.nde, field_name="nde")
        ensure_finite_numeric(self.nie, field_name="nie")
        ensure_finite_numeric(self.total_effect, field_name="total_effect")
        if self.cde is not None:
            ensure_finite_numeric(self.cde, field_name="cde")
        if self.nde_se is not None:
            ensure_finite_numeric(self.nde_se, field_name="nde_se")
        if self.nie_se is not None:
            ensure_finite_numeric(self.nie_se, field_name="nie_se")
        if self.proportion_mediated is not None:
            ensure_finite_numeric(self.proportion_mediated, field_name="proportion_mediated")

        if self.nde_ci is not None:
            ensure_confidence_interval(
                self.nde_ci,
                label="nde_ci",
                point_estimate=self.nde,
                point_label="nde",
            )
        if self.nie_ci is not None:
            ensure_confidence_interval(
                self.nie_ci,
                label="nie_ci",
                point_estimate=self.nie,
                point_label="nie",
            )

        tolerance = max(
            1.0e-9,
            1.0e-6 * max(abs(self.nde + self.nie), abs(self.total_effect), 1.0),
        )
        if abs((self.nde + self.nie) - self.total_effect) > tolerance:
            raise ValueError("nde + nie must equal total_effect within numerical tolerance")

        if self.sensitivity_rho_range is None:
            if self.sensitivity_nde is not None or self.sensitivity_nie is not None:
                raise ValueError(
                    "sensitivity_rho_range is required when sensitivity_nde "
                    "or sensitivity_nie is provided"
                )
        else:
            if self.sensitivity_nde is None or self.sensitivity_nie is None:
                raise ValueError(
                    "sensitivity_nde and sensitivity_nie are required when "
                    "sensitivity_rho_range is provided"
                )
            _ensure_finite_tuple(self.sensitivity_rho_range, label="sensitivity_rho_range")
            _ensure_finite_tuple(self.sensitivity_nde, label="sensitivity_nde")
            _ensure_finite_tuple(self.sensitivity_nie, label="sensitivity_nie")
            expected_len = len(self.sensitivity_rho_range)
            if (
                len(self.sensitivity_nde) != expected_len
                or len(self.sensitivity_nie) != expected_len
            ):
                raise ValueError(
                    "sensitivity_nde and sensitivity_nie must align with "
                    "sensitivity_rho_range length"
                )
        return self


def _normalize_paths(
    paths: tuple[tuple[str, ...], ...],
    *,
    label: str,
    treatment: str,
    outcome: str,
) -> tuple[tuple[str, ...], ...]:
    ensure_unique_ids(paths, key_fn=lambda path: tuple(path), label=label)
    normalized: list[tuple[str, ...]] = []
    for index, path in enumerate(paths):
        candidate = ensure_non_empty_path(
            path,
            label=f"{label}[{index}]",
            max_depth=MAX_MEDIATION_PATH_DEPTH,
        )
        if candidate[0] != treatment:
            raise ValueError(f"{label}[{index}] must start with treatment")
        if candidate[-1] != outcome:
            raise ValueError(f"{label}[{index}] must end with outcome")
        ensure_unique_ids(candidate, key_fn=lambda node: node, label=f"{label}[{index}]")
        normalized.append(candidate)
    return tuple(normalized)


def _ensure_finite_tuple(values: tuple[float, ...], *, label: str) -> None:
    for index, value in enumerate(values):
        ensure_finite_numeric(value, field_name=f"{label}[{index}]")


__all__ = [
    "MediationDecomposition",
    "PathSpecificQuery",
]
