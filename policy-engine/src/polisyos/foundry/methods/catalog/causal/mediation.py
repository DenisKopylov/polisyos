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
    namespace="causal.mediation",
    version="1.0.0",
    tags={"causal", "mediation", "causal-mediation"},
)
class CausalMediationEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_mediation",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("mediator", SlotType.VECTOR, Unit("mediator", "value"), shape=("n_obs",)),
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
        description="Causal mediation analysis: ACME and ADE via sequential ignorability.",
        tags=frozenset({"causal", "mediation", "acme", "ade", "baron-kenny"}),
        citations=(
            "Imai, K., Keele, L. & Tingley, D. (2010). A General Approach to Causal Mediation Analysis. Psych Methods.",
        ),
        equations={
            "total": "TE = ADE + ACME",
            "acme": "ACME = E[Y(t, M(1)) - Y(t, M(0))]",
            "ade": "ADE = E[Y(1, M(t)) - Y(0, M(t))]",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Decompose total treatment effect into direct and indirect (through mediator); mediation analysis",
        when_not_to_use="No mediator measured; unmeasured mediator-outcome confounders; cross-world independence implausible",
        typical_min_obs=100,
        output_interpretation="ACME: Average Causal Mediation Effect (indirect path). ADE: Average Direct Effect. Total = ACME + ADE. Proportion mediated = ACME/Total.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        M = np.asarray(state["mediator"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)

        # Mediator model: M = a0 + a1*T + a2*X + e_m
        X_m = np.column_stack([np.ones(n), T, X])
        a = np.linalg.lstsq(X_m, M, rcond=None)[0]
        a_T = float(a[1])  # effect of T on M

        # Outcome model: Y = b0 + b1*T + b2*M + b3*X + e_y
        X_y = np.column_stack([np.ones(n), T, M, X])
        b = np.linalg.lstsq(X_y, Y, rcond=None)[0]
        b_T = float(b[1])  # direct effect
        b_M = float(b[2])  # effect of M on Y

        # ACME (indirect effect) = a_T * b_M
        acme = a_T * b_M
        # ADE (direct effect) = b_T
        ade = b_T
        # Total effect
        total = acme + ade
        # Proportion mediated
        prop_mediated = acme / total if abs(total) > 1e-12 else 0.0

        # Standard errors via delta method (simplified)
        resid_m = M - X_m @ a
        resid_y = Y - X_y @ b
        sigma_m = float(np.std(resid_m))
        sigma_y = float(np.std(resid_y))

        # Approximate SE of ACME
        var_a_T = sigma_m ** 2 / max(float(np.sum((T - np.mean(T)) ** 2)), 1e-12)
        var_b_M = sigma_y ** 2 / max(float(np.sum((M - np.mean(M)) ** 2)), 1e-12)
        se_acme = float(np.sqrt(a_T ** 2 * var_b_M + b_M ** 2 * var_a_T))

        return {
            "result": {
                "acme": acme,
                "ade": ade,
                "total_effect": total,
                "proportion_mediated": float(np.clip(prop_mediated, 0.0, 1.0)),
                "se_acme": se_acme,
                "a_treatment_to_mediator": a_T,
                "b_mediator_to_outcome": b_M,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.mediation",
    version="1.0.0",
    tags={"causal", "mediation", "controlled-direct-effect"},
)
class ControlledDirectEffectEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="controlled_direct_effect",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
                SlotSpec("mediator", SlotType.VECTOR, Unit("mediator", "value"), shape=("n_obs",)),
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="mediator_level", default=0.0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Controlled Direct Effect: effect of T on Y holding M at a fixed level.",
        tags=frozenset({"causal", "mediation", "controlled-direct-effect", "cde"}),
        citations=("Pearl, J. (2001). Direct and Indirect Effects. UAI.",),
        equations={"cde": "CDE(m) = E[Y(1,m) - Y(0,m)]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Controlled direct effect with mediator fixed at specific level m; policy-relevant direct effect",
        typical_min_obs=100,
        output_interpretation="CDE(m): direct effect of T on Y with M fixed at m.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        M = np.asarray(state["mediator"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        m_level = float(params.get("mediator_level", 0.0))
        n = len(Y)

        # Outcome model with interaction: Y = b0 + b1*T + b2*M + b3*T*M + b4*X + e
        TM = T * M
        X_y = np.column_stack([np.ones(n), T, M, TM, X])
        b = np.linalg.lstsq(X_y, Y, rcond=None)[0]

        # CDE(m) = b1 + b3 * m
        cde = float(b[1]) + float(b[3]) * m_level

        # SE
        resid = Y - X_y @ b
        sigma2 = float(np.sum(resid ** 2) / max(n - len(b), 1))
        try:
            cov = sigma2 * np.linalg.inv(X_y.T @ X_y)
            se_cde = float(np.sqrt(max(cov[1, 1] + m_level ** 2 * cov[3, 3] + 2 * m_level * cov[1, 3], 0.0)))
        except np.linalg.LinAlgError:
            se_cde = float("inf")

        return {
            "result": {
                "cde": cde,
                "standard_error": se_cde,
                "mediator_level": m_level,
                "direct_effect_coef": float(b[1]),
                "interaction_coef": float(b[3]),
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.mediation",
    version="1.0.0",
    tags={"causal", "mediation", "nde", "nie", "natural_effects", "semiparametric"},
)
class NaturalEffectEstimator:
    """Natural Direct and Indirect Effect estimator via cross-fitted EIF.

    Entry point for NDE/NIE within the ``causal.mediation`` namespace,
    delegating to ``_nde_cross_fit`` from ``path_specific.py``.

    Implements the Tchetgen Tchetgen & Shpitser (2012) doubly-robust
    estimator.  For path-specific effects with custom active/frozen paths,
    use ``PathSpecificEffectEstimator`` (causal.counterfactual namespace).

    Input slots
    -----------
    X         : covariates (n_obs, p)
    treatment : binary treatment (n_obs,)
    mediator  : mediator variable (n_obs,)
    outcome   : outcome variable (n_obs,)

    Output slots
    ------------
    result : MediationDecomposition JSON dict
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="natural_effects",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("mediator", SlotType.VECTOR, Unit("mediator", "value"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_folds", default=2),
            ParameterSpec(name="min_propensity", default=1e-4),
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
            "Natural Direct Effect (NDE) and Natural Indirect Effect (NIE) via "
            "semiparametric EIF cross-fitting. Decomposes ATE = NDE + NIE."
        ),
        tags=frozenset({"causal", "mediation", "nde", "nie", "natural_effects", "eif"}),
        citations=(
            "Tchetgen Tchetgen, E.J. & Shpitser, I. (2012). Semiparametric Theory for "
            "Causal Mediation Analysis. Ann. Stat. 40(4), 1816–1845.",
        ),
        equations={
            "nde": "NDE = E[Y(1, M(0))] - E[Y(0, M(0))]",
            "nie": "NIE = E[Y(1, M(1))] - E[Y(1, M(0))]",
            "decomp": "ATE = NDE + NIE",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "Estimate natural direct and indirect effects with semiparametric efficiency; "
            "equivalent to PathSpecificEffectEstimator but in the causal.mediation namespace."
        ),
        when_not_to_use="Unmeasured mediator-outcome confounders (use sensitivity analysis).",
        typical_min_obs=200,
        output_interpretation="NDE = direct effect; NIE = indirect via mediator; NDE+NIE ≈ ATE.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.path_specific import _nde_cross_fit

        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        M = np.asarray(state["mediator"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)

        n_folds = int(params.get("n_folds", 2))
        min_propensity = float(params.get("min_propensity", 1e-4))

        nde, nde_se, nie, nie_se = _nde_cross_fit(
            Y, T, M, X,
            n_folds=n_folds,
            rng=rng,
            min_propensity=min_propensity,
        )

        total = nde + nie
        prop_med = float(np.clip(nie / total, -10.0, 10.0)) if abs(total) > 1e-12 else None

        return {
            "result": {
                "nde": nde,
                "nie": nie,
                "total_effect": total,
                "nde_se": nde_se,
                "nie_se": nie_se,
                "nde_ci": (nde - 1.96 * nde_se, nde + 1.96 * nde_se),
                "nie_ci": (nie - 1.96 * nie_se, nie + 1.96 * nie_se),
                "proportion_mediated": prop_med,
                "n_obs": len(Y),
                "n_folds": n_folds,
                "estimation_method": "eif_cross_fit",
            }
        }


__all__ = [
    "CausalMediationEstimator",
    "ControlledDirectEffectEstimator",
    "NaturalEffectEstimator",
]
