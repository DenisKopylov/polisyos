"""Standard Fairness Model (SFM) for causal fairness decomposition.

This module adds the Phase-9 fairness pipeline on top of the existing Phase-8
estimators.  It focuses on a practical slice of the Standard Fairness Model:

- a typed SFM container (`StandardFairnessModel`);
- identification checks for counterfactual fairness contrasts;
- TV = Ctf-DE + Ctf-IE + Ctf-SE decomposition using the existing EIF-style
  mediation helpers where possible;
- conservative partial-identification bounds when point identification fails.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability import DeterminismTier
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
from polisyos.foundry.methods.catalog.causal.fairness import (
    CounterfactualFairnessEstimator,
    PathSpecificFairnessEstimator,
    TVFairnessDecomposer,
    _aipw_ate,
    _build_fairness_report,
    _nde_nie_cross_fit,
)
from polisyos.foundry.methods.catalog.causal.id_engine import (
    CtfQuery,
    IdentificationResult,
    IdentificationStatus,
    id_star_algorithm,
)
from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.fairness import FairnessDecomposition
from polisyos.ir.analytics.partial_identification import PartialIdentificationResult


class StandardFairnessModel(BaseModel):
    """Typed Standard Fairness Model definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    protected_attribute: str
    mediators: list[str] = Field(default_factory=list)
    outcome: str
    confounders: list[str] = Field(default_factory=list)
    graph: CausalGraphModel


def _as_numpy_1d(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float).ravel()


def _as_numpy_2d(value: Any) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return arr


def _build_query(
    sfm: StandardFairnessModel,
    *,
    kind: str,
) -> CtfQuery:
    return CtfQuery(
        outcome=sfm.outcome,
        intervention=((sfm.protected_attribute, 1.0),),
        conditioning=tuple(sfm.confounders),
        evidence=(),
        kind=kind,  # type: ignore[arg-type]
        mediators=tuple(sfm.mediators),
        protected_attribute=sfm.protected_attribute,
    )


def identify_fairness_effects(
    sfm: StandardFairnessModel,
) -> dict[str, IdentificationResult]:
    """Identify which fairness contrasts are point-identifiable."""

    return {
        "ctf_de": id_star_algorithm(_build_query(sfm, kind="ctf_de"), sfm.graph),
        "ctf_ie": id_star_algorithm(_build_query(sfm, kind="ctf_ie"), sfm.graph),
        "ctf_se": id_star_algorithm(_build_query(sfm, kind="ctf_se"), sfm.graph),
    }


def tv_decomposition(
    sfm: StandardFairnessModel,
    data: Mapping[str, Any],
) -> FairnessDecomposition:
    """Estimate TV, counterfactual DE, IE and SE for an SFM."""

    Y = _as_numpy_1d(data["outcome"])
    A_raw = _as_numpy_1d(data["protected"])
    X = _as_numpy_2d(data["covariates"])
    mediator_data = data.get("mediators")
    A = np.where(A_raw >= 0.5, 1.0, 0.0)
    rng = np.random.default_rng(int(data.get("__seed__", 0)))

    identified = identify_fairness_effects(sfm)
    id_status = {name: result.status.value for name, result in identified.items()}

    mask1 = A > 0.5
    mask0 = ~mask1
    tv = float(np.mean(Y[mask1]) - np.mean(Y[mask0])) if mask1.any() and mask0.any() else 0.0
    tv_se = (
        math.sqrt(
            float(np.var(Y[mask1], ddof=1)) / max(int(mask1.sum()), 1)
            + float(np.var(Y[mask0], ddof=1)) / max(int(mask0.sum()), 1)
        )
        if mask1.sum() > 1 and mask0.sum() > 1
        else 0.0
    )
    tv_ci = (tv - 1.96 * tv_se, tv + 1.96 * tv_se)

    if mediator_data is not None and sfm.mediators:
        M = _as_numpy_2d(mediator_data)
        de, de_se, ie, ie_se, _, _ = _nde_nie_cross_fit(
            Y,
            A,
            M[:, 0].reshape(-1, 1),
            X,
            n_folds=3,
            min_propensity=1e-3,
            rng=rng,
        )
    else:
        de, de_se, de_ci = _aipw_ate(Y, A, X, n_folds=3, min_propensity=1e-3, rng=rng)
        ie = 0.0
        ie_se = 0.0
        return FairnessDecomposition(
            tv=tv,
            direct_effect=de,
            indirect_effect=ie,
            spurious_effect=tv - de,
            decomposition_residual=abs(tv - de),
            tv_ci=tv_ci,
            de_ci=de_ci,
            ie_ci=(0.0, 0.0),
            se_ci=(tv - de - 1.96 * tv_se, tv - de + 1.96 * tv_se),
            n_obs=len(Y),
            protected_attribute=sfm.protected_attribute,
            outcome=sfm.outcome,
            mediators=tuple(sfm.mediators),
            estimation_method="standard_fairness_model",
            metadata={
                "decomposition_valid": abs(tv - de - ie - (tv - de - ie)) < 0.02,
                "identification_status": id_status,
                "total_variation": tv,
                "ctf_direct_effect": de,
                "ctf_indirect_effect": ie,
                "ctf_spurious_effect": tv - de,
            },
        )

    se = float(tv - de - ie)
    se_se = math.sqrt(max(tv_se**2 + de_se**2 + ie_se**2, 0.0))
    de_ci = (de - 1.96 * de_se, de + 1.96 * de_se)
    ie_ci = (ie - 1.96 * ie_se, ie + 1.96 * ie_se)
    se_ci = (se - 1.96 * se_se, se + 1.96 * se_se)
    residual = abs(tv - de - ie - se)
    return FairnessDecomposition(
        tv=tv,
        direct_effect=de,
        indirect_effect=ie,
        spurious_effect=se,
        decomposition_residual=residual,
        tv_ci=tv_ci,
        de_ci=de_ci,
        ie_ci=ie_ci,
        se_ci=se_ci,
        n_obs=len(Y),
        protected_attribute=sfm.protected_attribute,
        outcome=sfm.outcome,
        mediators=tuple(sfm.mediators),
        estimation_method="standard_fairness_model",
        metadata={
            "decomposition_valid": residual < 0.02,
            "identification_status": id_status,
            "total_variation": tv,
            "ctf_direct_effect": de,
            "ctf_indirect_effect": ie,
            "ctf_spurious_effect": se,
        },
    )


def fairness_bounds(
    sfm: StandardFairnessModel,
    data: Mapping[str, Any],
) -> dict[str, tuple[float, float]]:
    """Return partial-identification bounds for non-identified fairness effects."""

    Y = _as_numpy_1d(data["outcome"])
    A = _as_numpy_1d(data["protected"])
    identified = identify_fairness_effects(sfm)
    bounds: dict[str, tuple[float, float]] = {}
    for name, result in identified.items():
        if result.status is IdentificationStatus.IDENTIFIED:
            bounds[name] = (0.0, 0.0)
            continue
        pid: PartialIdentificationResult = auto_bounds(Y, A)
        bounds[name] = (float(pid.lower_bound), float(pid.upper_bound))
    return bounds


def _decomposition_to_report(
    sfm: StandardFairnessModel,
    decomposition: FairnessDecomposition,
) -> dict[str, Any]:
    id_status = decomposition.metadata.get("identification_status", {})
    primary = None
    if abs(decomposition.direct_effect) >= abs(decomposition.indirect_effect):
        primary = f"{sfm.protected_attribute} -> {sfm.outcome}"
    elif sfm.mediators:
        primary = f"{sfm.protected_attribute} -> {sfm.mediators[0]} -> {sfm.outcome}"
    return _build_fairness_report(
        tv=decomposition.tv,
        tv_se=(decomposition.tv_ci[1] - decomposition.tv_ci[0]) / 3.92
        if decomposition.tv_ci
        else 0.0,
        de=decomposition.direct_effect,
        de_se=(decomposition.de_ci[1] - decomposition.de_ci[0]) / 3.92
        if decomposition.de_ci
        else 0.0,
        ie=decomposition.indirect_effect,
        ie_se=(decomposition.ie_ci[1] - decomposition.ie_ci[0]) / 3.92
        if decomposition.ie_ci
        else 0.0,
        n_obs=decomposition.n_obs,
        protected_attribute=sfm.protected_attribute,
        outcome=sfm.outcome,
        mediators=tuple(sfm.mediators),
        estimation_method="standard_fairness_model",
        path_specific_fairness={
            name: status == IdentificationStatus.IDENTIFIED.value
            for name, status in id_status.items()
        },
        cf_fairness=(
            abs(decomposition.direct_effect) < 0.05 and abs(decomposition.indirect_effect) < 0.05
        ),
        metadata={
            **decomposition.metadata,
            "primary_unfair_pathway": primary,
        },
    )


@foundry_method(
    namespace="causal.fairness",
    version="1.0.0",
    tags={"causal", "fairness", "standard_fairness_model", "counterfactual"},
)
class CausalFairnessEngine:
    """Foundry dispatcher for the Standard Fairness Model pipeline."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_fairness_engine",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "protected", SlotType.VECTOR, Unit("protected", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "covariates",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_obs", "n_features"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec("fairness_report", SlotType.SCALAR, Unit("report", "json")),
                SlotSpec("bounds", SlotType.SCALAR, Unit("bounds", "json")),
            }
        ),
        parameters=(
            ParameterSpec(name="method", default="tv_decomposition"),
            ParameterSpec(name="protected_attribute", default="A"),
            ParameterSpec(name="outcome_variable", default="Y"),
            ParameterSpec(name="mediators", default=[]),
            ParameterSpec(name="confounders", default=[]),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Standard Fairness Model pipeline for causal fairness decomposition and bounds.",
        tags=frozenset({"causal", "fairness", "standard_fairness_model", "phase9"}),
        citations=("Plecko, D. & Bareinboim, E. (2024). Causal Fairness Analysis. FnTML.",),
        equations={
            "tv": "TV(a,a') = Ctf-DE(a,a') + Ctf-IE(a,a') + Ctf-SE(a,a')",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use="When a causal graph and mediators are available and the audit needs a counterfactual fairness decomposition.",
        when_not_to_use="When no graph is available; prefer the simpler phase-8 fairness estimators.",
        output_interpretation="Returns a fairness report plus optional nonparametric bounds for non-identified contrasts.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        method = str(params.get("method", "tv_decomposition"))
        graph = params.get("graph") or state.get("graph")
        if not isinstance(graph, CausalGraphModel):
            raise ValueError(
                "CausalFairnessEngine requires a CausalGraphModel via params['graph'] or state['graph']"
            )

        sfm = StandardFairnessModel(
            protected_attribute=str(
                params.get("protected_attribute", params.get("protected_variable", "A"))
            ),
            mediators=list(params.get("mediators", [])),
            outcome=str(params.get("outcome_variable", params.get("outcome", "Y"))),
            confounders=list(params.get("confounders", [])),
            graph=graph,
        )

        if method == "tv_decomposition":
            decomp = tv_decomposition(sfm, state)
            report = _decomposition_to_report(sfm, decomp)
            return {
                "fairness_report": report,
                "decomposition": decomp.model_dump(mode="json"),
            }
        if method == "bounds":
            decomp = tv_decomposition(sfm, state)
            report = _decomposition_to_report(sfm, decomp)
            return {
                "fairness_report": report,
                "decomposition": decomp.model_dump(mode="json"),
                "bounds": fairness_bounds(sfm, state),
            }
        if method == "path_specific":
            return PathSpecificFairnessEstimator.pure_step(state, params)
        if method == "counterfactual":
            return CounterfactualFairnessEstimator.pure_step(state, params)
        if method == "tv_legacy":
            return TVFairnessDecomposer.pure_step(state, params)
        raise ValueError(f"Unknown fairness method {method!r}")


__all__ = [
    "CausalFairnessEngine",
    "StandardFairnessModel",
    "fairness_bounds",
    "identify_fairness_effects",
    "tv_decomposition",
]
