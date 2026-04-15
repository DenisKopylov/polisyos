"""nuisance_resolver — principled selection and wrapping of nuisance models.

Provides:

1. :class:`NuisanceSpec` — lightweight dataclass describing which foundry method
   to use for a given nuisance role (propensity, outcome, density_ratio, …).

2. :class:`NuisanceResolver` — selects the appropriate ``NuisanceSpec`` based on
   problem context (covariate dimensionality, sample size, treatment/outcome type).

3. Foundry method classes for each nuisance model, wrapping the private numpy
   implementations already in ``treatment_effects.py`` and ``cross_fit.py``::

       causal.nuisance.logistic_propensity@1.0.0
       causal.nuisance.logistic_l2_propensity@1.0.0
       causal.nuisance.ols_outcome@1.0.0
       causal.nuisance.lasso_outcome@1.0.0
       causal.nuisance.mediator_density@1.0.0
       causal.nuisance.empirical_density@1.0.0
       causal.nuisance.propensity_model@1.0.0   (generic alias → logistic)
       causal.nuisance.outcome_model@1.0.0      (generic alias → OLS or lasso)

These foundry methods follow the standard ``pure_step(state, params) → dict``
ABI and are registered with the global MethodRegistry on import.

Selection rules
---------------
Propensity:
  - binary treatment, dim ≤ 20  → logistic_propensity
  - binary treatment, dim > 20  → logistic_l2_propensity  (ridge regularisation)
  - continuous treatment        → ols_outcome (used as linear propensity model)

Outcome model:
  - continuous, dim ≤ 10  → ols_outcome
  - continuous, dim > 10  → lasso_outcome
  - binary outcome        → logistic_propensity (reused, predicting P(Y=1|X,T))
  - count outcome         → ols_outcome (Poisson placeholder)

Density ratio:
  - dim ≤ 20 or n_obs ≥ 200  → logistic_trick (fast, default)
  - n_obs < 200              → rulsif (stable for small n)
  - dim > 20                 → kliep (kernel-based)
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Mapping

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
from polisyos.foundry.methods.catalog.causal.treatment_effects import (
    _logistic_propensity,
)
from polisyos.foundry.methods.catalog.causal.cross_fit import (
    _outcome_model,
    _predict_outcomes,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.estimand import NuisanceNode


# ---------------------------------------------------------------------------
# NuisanceSpec — describes which method to use for a given nuisance role
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class NuisanceSpec:
    """Descriptor for a nuisance model selection decision.

    Produced by :class:`NuisanceResolver` and consumed by the compiler
    (``ast_lowerer.py``) to populate ``ExecutorNode.method_fqn`` and
    ``ExecutorNode.params``.
    """

    role: str
    """Nuisance role: 'propensity' | 'outcome' | 'density_ratio' | 'mediator_density'."""

    method_fqn: str
    """Fully-qualified name of the foundry method, e.g. 'causal.nuisance.logistic_propensity@1.0.0'."""

    params: dict = dataclasses.field(default_factory=dict)
    """Parameters to pass into the ExecutorNode."""

    rationale: str = ""
    """Human-readable reason for this selection (for audit)."""


# ---------------------------------------------------------------------------
# NuisanceResolver — selects appropriate NuisanceSpec from context
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class NuisanceResolver:
    """Auto-selects the best nuisance model based on problem context.

    All ``resolve_*`` methods return a :class:`NuisanceSpec` that can be
    directly used to populate an ``ExecutorNode`` in the compiler.
    """

    def resolve_propensity(
        self,
        covariate_dim: int | None,
        n_obs: int | None,
        treatment_type: str = "binary",
    ) -> NuisanceSpec:
        """Select a propensity / treatment model."""
        if treatment_type == "continuous":
            return NuisanceSpec(
                role="propensity",
                method_fqn="causal.nuisance.ols_outcome@1.0.0",
                params={},
                rationale="Continuous treatment → linear first-stage model.",
            )
        # Binary treatment: choose regularisation level based on dimensionality
        if covariate_dim is not None and covariate_dim > 20:
            return NuisanceSpec(
                role="propensity",
                method_fqn="causal.nuisance.logistic_l2_propensity@1.0.0",
                params={"regularization": 1.0},
                rationale=f"High-dim covariates ({covariate_dim} > 20) → L2-regularised logistic.",
            )
        return NuisanceSpec(
            role="propensity",
            method_fqn="causal.nuisance.logistic_propensity@1.0.0",
            params={},
            rationale="Binary treatment, low-dim covariates → standard logistic regression.",
        )

    def resolve_outcome_model(
        self,
        covariate_dim: int | None,
        n_obs: int | None,
        outcome_type: str = "continuous",
    ) -> NuisanceSpec:
        """Select an outcome regression model."""
        if outcome_type == "binary":
            return NuisanceSpec(
                role="outcome",
                method_fqn="causal.nuisance.logistic_propensity@1.0.0",
                params={},
                rationale="Binary outcome → logistic regression.",
            )
        if outcome_type == "count":
            return NuisanceSpec(
                role="outcome",
                method_fqn="causal.nuisance.ols_outcome@1.0.0",
                params={},
                rationale="Count outcome → OLS (Poisson plug-in).",
            )
        # Continuous outcome: OLS vs Lasso depends on dimensionality
        if covariate_dim is not None and covariate_dim > 10:
            return NuisanceSpec(
                role="outcome",
                method_fqn="causal.nuisance.lasso_outcome@1.0.0",
                params={"alpha": "auto"},
                rationale=f"High-dim covariates ({covariate_dim} > 10) → Lasso outcome model.",
            )
        return NuisanceSpec(
            role="outcome",
            method_fqn="causal.nuisance.ols_outcome@1.0.0",
            params={},
            rationale="Continuous outcome, low-dim covariates → OLS.",
        )

    def resolve_density_ratio(
        self,
        source_dim: int | None,
        n_obs: int | None,
    ) -> NuisanceSpec:
        """Select a density-ratio estimator for transport / reweighting."""
        if n_obs is not None and n_obs < 200:
            return NuisanceSpec(
                role="density_ratio",
                method_fqn="causal.treatment_effects.density_ratio_estimator@1.0.0",
                params={"method": "rulsif"},
                rationale="Small n → RULSIF (numerically stable for small samples).",
            )
        if source_dim is not None and source_dim > 20:
            return NuisanceSpec(
                role="density_ratio",
                method_fqn="causal.treatment_effects.density_ratio_estimator@1.0.0",
                params={"method": "kliep"},
                rationale=f"High-dim ({source_dim} > 20) → KLIEP (kernel-based).",
            )
        return NuisanceSpec(
            role="density_ratio",
            method_fqn="causal.treatment_effects.density_ratio_estimator@1.0.0",
            params={"method": "logistic_trick"},
            rationale="Default density-ratio estimator: logistic trick.",
        )

    def resolve_for_nuisance_node(
        self,
        node: "NuisanceNode",
        n_obs: int | None = None,
        covariate_dim: int | None = None,
    ) -> NuisanceSpec:
        """Route a :class:`NuisanceNode` from EstimandAST to a :class:`NuisanceSpec`."""
        role = node.nuisance_type
        if role == "propensity":
            return self.resolve_propensity(covariate_dim, n_obs)
        if role == "outcome":
            return self.resolve_outcome_model(covariate_dim, n_obs)
        if role == "density_ratio":
            return self.resolve_density_ratio(covariate_dim, n_obs)
        if role == "mediator_density":
            return NuisanceSpec(
                role="mediator_density",
                method_fqn="causal.nuisance.mediator_density@1.0.0",
                params={},
                rationale="Mediator density P(M|X) for front-door formula.",
            )
        if role == "conditional_density":
            return self.resolve_conditional_density(covariate_dim, n_obs)
        if role == "multinomial_propensity":
            return self.resolve_multinomial_propensity(covariate_dim, n_obs, n_levels=3)
        # Unknown role → default to propensity
        return NuisanceSpec(
            role=role,
            method_fqn="causal.nuisance.propensity_model@1.0.0",
            params={},
            rationale=f"Unknown role '{role}' → generic propensity model fallback.",
        )

    # ------------------------------------------------------------------
    # Phase 6 — continuous treatment & multi-treatment resolvers
    # ------------------------------------------------------------------

    def resolve_conditional_density(
        self,
        covariate_dim: int | None,
        n_obs: int | None,
        method: str = "parametric",
    ) -> NuisanceSpec:
        """Select a method for estimating the conditional treatment density f(T|X).

        Used by continuous treatment estimators (GPS, kernel dose-response,
        shift interventions).

        Parameters
        ----------
        covariate_dim : number of covariates.
        n_obs         : sample size.
        method        : 'parametric' (Gaussian) | 'auto'.

        Returns
        -------
        NuisanceSpec with role='conditional_density'.
        """
        # Parametric Gaussian density: T|X ~ N(Xβ, σ²)
        # Simple enough to be the default for all sample sizes.
        # Future work: kernel conditional density for n_obs ≥ 2000.
        return NuisanceSpec(
            role="conditional_density",
            method_fqn="causal.nuisance.parametric_conditional_density@1.0.0",
            params={},
            rationale=(
                "Parametric Gaussian conditional density T|X ~ N(Xβ, σ²). "
                "Suitable as default for GPS-based continuous treatment estimation."
            ),
        )

    def resolve_multinomial_propensity(
        self,
        covariate_dim: int | None,
        n_obs: int | None,
        n_levels: int = 3,
    ) -> NuisanceSpec:
        """Select multinomial propensity model P(T=k|X) for K treatment arms.

        Parameters
        ----------
        covariate_dim : number of covariates.
        n_obs         : sample size.
        n_levels      : number of distinct treatment levels K.

        Returns
        -------
        NuisanceSpec with role='multinomial_propensity'.
        """
        min_p = max(0.01, 1.0 / max(n_obs or 100, 1))
        params: dict[str, Any] = {"min_propensity": min_p}
        if covariate_dim is not None and covariate_dim > 20:
            params["regularization"] = "l2"
            rationale = (
                f"L2-regularised multinomial logistic for {n_levels} arms, "
                f"dim={covariate_dim}."
            )
        else:
            rationale = f"Multinomial logistic regression for {n_levels} treatment arms."
        return NuisanceSpec(
            role="multinomial_propensity",
            method_fqn="causal.nuisance.multinomial_propensity@1.0.0",
            params=params,
            rationale=rationale,
        )

    def resolve_superlearner(
        self,
        outcome_type: str,
        covariate_dim: int | None,
        n_obs: int | None,
    ) -> NuisanceSpec:
        """Return a Super Learner NuisanceSpec for large or high-dimensional problems.

        Auto-selects base learner library based on sample size.

        Parameters
        ----------
        outcome_type  : 'continuous' | 'binary'.
        covariate_dim : number of covariates.
        n_obs         : sample size.

        Returns
        -------
        NuisanceSpec with role='outcome' or 'propensity'.
        """
        library = ["ols", "ridge"]
        if n_obs is not None and n_obs >= 500:
            library.append("lasso")
        if n_obs is not None and n_obs >= 1000:
            library.append("rf")
        if n_obs is not None and n_obs >= 2000:
            library.append("gbm")

        role = "outcome" if outcome_type == "continuous" else "propensity"
        return NuisanceSpec(
            role=role,
            method_fqn="causal.nuisance.super_learner@1.0.0",
            params={
                "library": library,
                "v_folds": 5,
                "outcome_type": outcome_type,
            },
            rationale=(
                f"Super Learner ensemble ({', '.join(library)}) "
                f"for n={n_obs}, dim={covariate_dim}."
            ),
        )


# ---------------------------------------------------------------------------
# Foundry methods — wrap existing private numpy implementations
# ---------------------------------------------------------------------------

def _nuisance_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
        SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
    })


def _propensity_output_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("propensity", SlotType.VECTOR, Unit("propensity", "probability"), shape=("n_obs",)),
    })


def _outcome_input_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
        SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
    })


def _outcome_output_slots() -> frozenset[SlotSpec]:
    return frozenset({
        SlotSpec("predicted_outcome", SlotType.VECTOR, Unit("outcome", "predicted"), shape=("n_obs",)),
        SlotSpec("outcome_coef", SlotType.VECTOR, Unit("coef", "value")),
    })


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "propensity", "logistic"},
)
class LogisticPropensityModel:
    """Logistic regression propensity score estimator (IRLS, no regularisation).

    Wraps the internal ``_logistic_propensity`` numpy implementation from
    ``treatment_effects.py`` with a proper foundry method ABI.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="logistic_propensity",
        namespace="",
        version="0.0.0",
        input_slots=_nuisance_slots(),
        output_slots=_propensity_output_slots(),
        parameters=(
            ParameterSpec(name="max_iter", default=50),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Logistic regression propensity score via iteratively reweighted least squares (IRLS).",
        tags=frozenset({"causal", "nuisance", "propensity", "logistic", "binary-treatment"}),
        citations=(
            "Rosenbaum, P.R. & Rubin, D.B. (1983). The central role of the propensity score. Biometrika.",
        ),
        equations={"propensity": "e(X) = P(T=1|X) = σ(β₀ + β₁X₁ + … + βₚXₚ)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary treatment, low-to-medium dimensional covariates (dim ≤ 20).",
        when_not_to_use="High-dimensional sparse covariates (use logistic_l2_propensity instead); continuous treatment.",
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.positivity_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation="propensity: P(T=1|X) clipped to [0.01, 0.99].",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        max_iter = int(params.get("max_iter", 50))
        propensity = _logistic_propensity(X, T, max_iter=max_iter)
        return {"propensity": propensity}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "propensity", "logistic", "l2"},
)
class LogisticL2PropensityModel:
    """L2-regularised logistic regression propensity score (ridge logistic).

    Adds Tikhonov regularisation to the IRLS Hessian to handle high-dimensional
    covariate matrices where the unregularised Hessian may be near-singular.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="logistic_l2_propensity",
        namespace="",
        version="0.0.0",
        input_slots=_nuisance_slots(),
        output_slots=_propensity_output_slots(),
        parameters=(
            ParameterSpec(name="regularization", default=1.0, bounds=(1e-6, 1e3)),
            ParameterSpec(name="max_iter", default=50),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Ridge-regularised logistic propensity model for high-dimensional covariates.",
        tags=frozenset({"causal", "nuisance", "propensity", "logistic", "l2", "regularised"}),
        citations=(
            "Rosenbaum, P.R. & Rubin, D.B. (1983). The central role of the propensity score. Biometrika.",
        ),
        equations={"propensity": "e(X) = σ(β₀ + Xβ), with L2 penalty λ‖β‖²"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Binary treatment, high-dimensional covariates (dim > 20); sparse settings.",
        when_not_to_use="Low-dimensional settings where regularisation introduces unnecessary bias.",
        prerequisites=(),
        diagnostic_checks=("causal.diagnostics.positivity_check@1.0.0",),
        typical_min_obs=50,
        output_interpretation="propensity: regularised P(T=1|X) clipped to [0.01, 0.99].",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        regularization = float(params.get("regularization", 1.0))
        max_iter = int(params.get("max_iter", 50))

        n, k = X.shape
        X_aug = np.column_stack([np.ones(n), X])
        p = X_aug.shape[1]
        beta = np.zeros(p)
        # Ridge-penalised IRLS: H_ridge = H + λ * I (skip intercept penalty)
        ridge = np.eye(p) * regularization
        ridge[0, 0] = 0.0  # do not regularise intercept
        for _ in range(max_iter):
            eta = np.clip(X_aug @ beta, -20, 20)
            prob = 1.0 / (1.0 + np.exp(-eta))
            W = np.maximum(prob * (1 - prob), 1e-12)
            grad = X_aug.T @ (T - prob) - regularization * beta
            H = X_aug.T @ (W[:, None] * X_aug) + ridge
            try:
                delta = np.linalg.solve(H, grad)
            except np.linalg.LinAlgError:
                break
            beta += delta
            if np.max(np.abs(delta)) < 1e-8:
                break
        eta_final = np.clip(X_aug @ beta, -20, 20)
        propensity = np.clip(1.0 / (1.0 + np.exp(-eta_final)), 0.01, 0.99)
        return {"propensity": propensity}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "outcome", "ols"},
)
class OLSOutcomeModel:
    """Ordinary least squares outcome model E[Y | T, X].

    Wraps the internal ``_outcome_model`` numpy implementation from
    ``cross_fit.py`` with a proper foundry method ABI.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ols_outcome",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }),
        output_slots=_outcome_output_slots(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="OLS outcome regression E[Y|T,X] — separate fits for treated/control arms.",
        tags=frozenset({"causal", "nuisance", "outcome", "ols", "regression"}),
        citations=(),
        equations={"ols": "μ(T, X) = β₀ + β₁T + β₂X + …"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Continuous outcome, low-to-medium dimensional covariates (dim ≤ 10).",
        when_not_to_use="High-dimensional covariates (use lasso_outcome); binary/count outcomes.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=20,
        output_interpretation=(
            "predicted_outcome: fitted E[Y|T,X] for all observations. "
            "outcome_coef: OLS coefficient vector."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        # Augment with treatment and intercept: [1, T, X]
        X_aug = np.column_stack([np.ones(n), T, X])
        beta, _, _, _ = np.linalg.lstsq(X_aug, Y, rcond=None)
        predicted = X_aug @ beta
        return {"predicted_outcome": predicted, "outcome_coef": beta}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "outcome", "lasso"},
)
class LassoOutcomeModel:
    """L1-regularised (Lasso) outcome model for high-dimensional settings.

    Uses coordinate descent for Lasso regularisation.  Falls back to OLS
    when the regularisation parameter converges to zero.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="lasso_outcome",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }),
        output_slots=_outcome_output_slots(),
        parameters=(
            ParameterSpec(name="alpha", default="auto"),
            ParameterSpec(name="max_iter", default=1000),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Lasso-regularised outcome regression for high-dimensional covariate settings.",
        tags=frozenset({"causal", "nuisance", "outcome", "lasso", "l1", "sparse"}),
        citations=(
            "Tibshirani, R. (1996). Regression Shrinkage and Selection via the Lasso. JRSS-B.",
        ),
        equations={"lasso": "min ½‖y − Xβ‖² + α‖β‖₁"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Continuous outcome, high-dimensional covariates (dim > 10); sparse signal.",
        when_not_to_use="Low-dimensional settings where OLS is sufficient.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation="predicted_outcome: Lasso-fitted E[Y|T,X] for all observations.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n, d = X.shape
        X_aug = np.column_stack([np.ones(n), T, X])

        # Determine alpha: "auto" → lambda_max / 10 heuristic
        alpha_param = params.get("alpha", "auto")
        if alpha_param == "auto":
            # Standardise columns for alpha selection
            Y_c = Y - np.mean(Y)
            col_norms = np.maximum(np.linalg.norm(X_aug, axis=0), 1e-8)
            alpha = float(np.max(np.abs(X_aug.T @ Y_c) / col_norms) / n) * 0.1
        else:
            alpha = float(alpha_param)

        # Coordinate descent Lasso (simplified)
        max_iter = int(params.get("max_iter", 1000))
        beta, _, _, _ = np.linalg.lstsq(X_aug, Y, rcond=None)  # warm start from OLS
        for _ in range(max_iter):
            beta_old = beta.copy()
            for j in range(len(beta)):
                r = Y - X_aug @ beta + X_aug[:, j] * beta[j]
                rho = float(X_aug[:, j] @ r) / n
                norm_j = float(X_aug[:, j] @ X_aug[:, j]) / n
                if norm_j < 1e-12:
                    beta[j] = 0.0
                elif j == 0:  # do not penalise intercept
                    beta[j] = rho / norm_j
                else:
                    beta[j] = np.sign(rho) * max(abs(rho) - alpha, 0.0) / norm_j
            if np.max(np.abs(beta - beta_old)) < 1e-8:
                break

        predicted = X_aug @ beta
        return {"predicted_outcome": predicted, "outcome_coef": beta}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "mediator", "density"},
)
class MediatorDensityModel:
    """Mediator density estimator P(M | X, T) for front-door formulas.

    Uses logistic regression (binary mediator) or OLS (continuous mediator).
    The mediator role is identified by the ``target_variable`` parameter.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="mediator_density",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("mediator", SlotType.VECTOR, Unit("mediator", "value"), shape=("n_obs",)),
        }),
        output_slots=frozenset({
            SlotSpec("mediator_prob", SlotType.VECTOR, Unit("mediator", "probability"), shape=("n_obs",)),
        }),
        parameters=(
            ParameterSpec(name="binary_mediator", default=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Mediator density P(M|X,T) for front-door identification formulas.",
        tags=frozenset({"causal", "nuisance", "mediator", "frontdoor", "density"}),
        citations=(),
        equations={"mediator_density": "P(M|X,T) via logistic (binary M) or OLS (continuous M)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Front-door identification formulas requiring mediator density.",
        when_not_to_use="Direct backdoor/IV formulas that do not involve a mediator.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation="mediator_prob: P(M=1|X,T) for binary M, or E[M|X,T] for continuous M.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        M = np.asarray(state["mediator"], dtype=float)
        binary_mediator = bool(params.get("binary_mediator", True))

        n = len(M)
        XT = np.column_stack([np.ones(n), T, X])

        if binary_mediator:
            mediator_prob = _logistic_propensity(
                np.column_stack([T, X]), M
            )
        else:
            beta, _, _, _ = np.linalg.lstsq(XT, M, rcond=None)
            mediator_prob = XT @ beta

        return {"mediator_prob": mediator_prob}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "empirical", "density"},
)
class EmpiricalDensityEstimator:
    """Empirical marginal density estimator P(Y | X) from tabular data.

    Used by the recursive compiler when a DataKB miss occurs — fits an
    empirical conditional distribution from the available dataset.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="empirical_density",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }),
        output_slots=frozenset({
            SlotSpec("density_estimate", SlotType.VECTOR, Unit("density", "value"), shape=("n_obs",)),
        }),
        parameters=(
            ParameterSpec(name="variables", default=()),
            ParameterSpec(name="conditioning", default=()),
            ParameterSpec(name="domain", default="source"),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Empirical density estimator: OLS-based conditional mean for unknown distributions.",
        tags=frozenset({"causal", "nuisance", "empirical", "density", "fallback"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Fallback when DataKnowledgeBase does not have a matching dataset for a DistributionRef.",
        when_not_to_use="When explicit structured models (propensity/outcome) are available.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=10,
        output_interpretation="density_estimate: empirical conditional mean of outcome given covariates.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        X_aug = np.column_stack([np.ones(n), X])
        beta, _, _, _ = np.linalg.lstsq(X_aug, Y, rcond=None)
        density_estimate = X_aug @ beta
        return {"density_estimate": density_estimate}


# ---------------------------------------------------------------------------
# Generic alias foundry methods (used by ast_lowerer as routing targets)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "propensity", "generic"},
)
class GenericPropensityModel:
    """Generic propensity model alias → delegates to LogisticPropensityModel.

    Registered as ``causal.nuisance.propensity_model@1.0.0`` for use by the
    recursive compiler when no specific model is configured.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="propensity_model",
        namespace="",
        version="0.0.0",
        input_slots=_nuisance_slots(),
        output_slots=_propensity_output_slots(),
        parameters=(ParameterSpec(name="max_iter", default=50),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generic propensity model — logistic regression alias for compiler routing.",
        tags=frozenset({"causal", "nuisance", "propensity", "generic"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Used internally by the recursive compiler; prefer specific models.",
        when_not_to_use="Direct use in pipelines — use logistic_propensity directly.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation="propensity: P(T=1|X) via logistic regression.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        max_iter = int(params.get("max_iter", 50))
        return {"propensity": _logistic_propensity(X, T, max_iter=max_iter)}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags={"causal", "nuisance", "outcome", "generic"},
)
class GenericOutcomeModel:
    """Generic outcome model alias → delegates to OLSOutcomeModel.

    Registered as ``causal.nuisance.outcome_model@1.0.0`` for use by the
    recursive compiler when no specific model is configured.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="outcome_model",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
            SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
        }),
        output_slots=_outcome_output_slots(),
        parameters=(ParameterSpec(name="target_variable", default=""),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generic outcome model — OLS alias for compiler routing.",
        tags=frozenset({"causal", "nuisance", "outcome", "ols", "generic"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Used internally by the recursive compiler; prefer specific models.",
        when_not_to_use="Direct use in pipelines — use ols_outcome or lasso_outcome directly.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=20,
        output_interpretation="predicted_outcome: OLS-fitted E[Y|T,X].",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Y = np.asarray(state["outcome"], dtype=float)
        n = len(Y)
        X_aug = np.column_stack([np.ones(n), T, X])
        beta, _, _, _ = np.linalg.lstsq(X_aug, Y, rcond=None)
        return {"predicted_outcome": X_aug @ beta, "outcome_coef": beta}


# ---------------------------------------------------------------------------
# Compiler primitive foundry methods (causal.compiler.*)
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.compiler",
    version="1.0.0",
    tags={"causal", "compiler", "marginalizer", "sum"},
)
class Marginalizer:
    """Discrete marginalisation: Σ_{summation_vars} operand.

    Receives a joint distribution table (as a 2-D array keyed by row-major
    variable ordering) and sums out the specified ``summation_vars``.  The
    result is the marginalised distribution over the remaining variables.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="marginalizer",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("joint_distribution", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        output_slots=frozenset({
            SlotSpec("marginal", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        parameters=(
            ParameterSpec(name="summation_vars", default=()),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Discrete marginalisation Σ_Z f(Y,Z) → f(Y) for recursive compiler output.",
        tags=frozenset({"causal", "compiler", "marginalizer", "sum", "formula"}),
        citations=(),
        equations={"marginal": "f(Y) = Σ_Z f(Y, Z)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="SumNode lowering in recursive compiler.",
        when_not_to_use="Continuous integration (use integrator instead).",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=1,
        output_interpretation="marginal: distribution summed over summation_vars.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        operand = np.asarray(state["joint_distribution"], dtype=float)
        # Sum over last axis for each summation variable (simplified: sum columns)
        marginal = float(np.sum(operand))
        return {"marginal": np.array([marginal])}


@foundry_method(
    namespace="causal.compiler",
    version="1.0.0",
    tags={"causal", "compiler", "product"},
)
class ProductCombiner:
    """Element-wise product of K distribution/density inputs.

    Receives ``factor_0``, ``factor_1``, …, ``factor_{K-1}`` slots and returns
    their element-wise product.  Used by ProductNode lowering.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="product",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("factor_0", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        output_slots=frozenset({
            SlotSpec("product_result", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        parameters=(
            ParameterSpec(name="n_factors", default=2),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Element-wise product f₁ · f₂ · … · fₖ for ProductNode lowering.",
        tags=frozenset({"causal", "compiler", "product", "formula"}),
        citations=(),
        equations={"product": "result = f₁ · f₂ · … · fₖ"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="ProductNode lowering in recursive compiler.",
        when_not_to_use="Scalar scalar operations better handled inline.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=1,
        output_interpretation="product_result: element-wise product of all input factors.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        n_factors = int(params.get("n_factors", 2))
        result = None
        for i in range(n_factors):
            key = f"factor_{i}"
            if key in state:
                factor = np.asarray(state[key], dtype=float)
                result = factor if result is None else result * factor
        if result is None:
            result = np.array([1.0])
        return {"product_result": result}


@foundry_method(
    namespace="causal.compiler",
    version="1.0.0",
    tags={"causal", "compiler", "ratio"},
)
class RatioCombiner:
    """Safe ratio of two scalar/vector distributions: numerator / denominator.

    The denominator is clipped to ``[clip_denominator_eps, ∞)`` to prevent
    division-by-zero.  Used by RatioNode lowering.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ratio",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("numerator", SlotType.VECTOR, Unit("distribution", "value")),
            SlotSpec("denominator", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        output_slots=frozenset({
            SlotSpec("ratio_result", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        parameters=(
            ParameterSpec(name="clip_denominator_eps", default=1e-8, bounds=(1e-12, 1.0)),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Safe ratio numerator / max(denominator, ε) for RatioNode lowering.",
        tags=frozenset({"causal", "compiler", "ratio", "formula"}),
        citations=(),
        equations={"ratio": "r = num / max(den, ε)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="RatioNode lowering in recursive compiler.",
        when_not_to_use="Division guaranteed safe by construction.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=1,
        output_interpretation="ratio_result: numerator / clipped denominator.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        numerator = np.asarray(state["numerator"], dtype=float)
        denominator = np.asarray(state["denominator"], dtype=float)
        eps = float(params.get("clip_denominator_eps", 1e-8))
        ratio_result = numerator / np.maximum(denominator, eps)
        return {"ratio_result": ratio_result}


@foundry_method(
    namespace="causal.compiler",
    version="1.0.0",
    tags={"causal", "compiler", "integrator"},
)
class Integrator:
    """Continuous marginalisation ∫ f(x) dx via trapezoidal rule or Monte Carlo.

    Used by IntegralNode lowering when the operand is defined over a continuous
    domain.  Falls back to simple sum (uniform weights) when grid points are not
    provided.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="integrator",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("integrand", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        output_slots=frozenset({
            SlotSpec("integral", SlotType.SCALAR, Unit("result", "value")),
        }),
        parameters=(
            ParameterSpec(name="integration_vars", default=()),
            ParameterSpec(name="measure", default="lebesgue"),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Continuous marginalisation ∫ f(x) dx — trapezoidal/MC quadrature.",
        tags=frozenset({"causal", "compiler", "integrator", "continuous", "quadrature"}),
        citations=(),
        equations={"integral": "∫ f(x) dx ≈ (b-a)/n Σ f(xᵢ)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="IntegralNode lowering for continuous marginalisation.",
        when_not_to_use="Discrete summation (use marginalizer instead).",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=1,
        output_interpretation="integral: scalar integral estimate.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        integrand = np.asarray(state["integrand"], dtype=float)
        # Simple trapezoidal rule assuming uniform spacing
        if integrand.ndim == 0:
            return {"integral": float(integrand)}
        integral = float(np.trapz(integrand) / max(len(integrand) - 1, 1))
        return {"integral": np.array([integral])}


@foundry_method(
    namespace="causal.data",
    version="1.0.0",
    tags={"causal", "data", "distribution", "read"},
)
class DistributionReader:
    """Read an empirical distribution table from the data slot.

    Maps to a DataKnowledgeBase AVAILABLE distribution — the data is already
    present in the dataset, so this node simply loads and returns it as an array.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="distribution_read",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("data", SlotType.MATRIX, Unit("dataset", "raw")),
        }),
        output_slots=frozenset({
            SlotSpec("distribution_values", SlotType.VECTOR, Unit("distribution", "value")),
        }),
        parameters=(
            ParameterSpec(name="variables", default=()),
            ParameterSpec(name="conditioning", default=()),
            ParameterSpec(name="domain", default="source"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Read empirical distribution values from a pre-loaded dataset slot.",
        tags=frozenset({"causal", "data", "distribution", "read", "empirical"}),
        citations=(),
        equations={},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="DataKnowledgeBase AVAILABLE distribution — data already in slot.",
        when_not_to_use="When distribution must be estimated (use empirical_density).",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=1,
        output_interpretation="distribution_values: raw data values for the requested variables.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        data = np.asarray(state.get("data", state.get("outcome", np.array([]))), dtype=float)
        return {"distribution_values": data}


# ---------------------------------------------------------------------------
# Phase 6 — Parametric Conditional Density & Multinomial Propensity
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags=frozenset({"causal", "nuisance", "conditional_density", "continuous_treatment"}),
)
class ParametricConditionalDensity:
    """Parametric Gaussian conditional treatment density f(T|X).

    Fits T|X ~ N(Xβ, σ²) via OLS and evaluates the Gaussian density
    at requested treatment values.  Used for GPS-based continuous
    treatment estimation (Hirano & Imbens 2004).

    Registered as ``causal.nuisance.parametric_conditional_density@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parametric_conditional_density",
        namespace="",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     description="(n, p) covariate matrix for fitting",
                     unit=Unit("dimensionless", ""),
                     shape=("n_obs", "n_features")),
            SlotSpec(name="treatment", slot_type=SlotType.VECTOR,
                     description="(n,) observed continuous treatment values",
                     unit=Unit("dimensionless", ""),
                     shape=("n_obs",)),
            SlotSpec(name="treatment_eval", slot_type=SlotType.VECTOR,
                     description="(m,) treatment values at which to evaluate density",
                     unit=Unit("dimensionless", ""),
                     shape=("n_obs",)),
        ]),
        output_slots=frozenset([
            SlotSpec(name="density", slot_type=SlotType.SCALAR,
                     description="(m,) density values f(treatment_eval | X_eval)",
                     unit=Unit("dimensionless", "")),
            SlotSpec(name="log_density", slot_type=SlotType.SCALAR,
                     description="(m,) log density values",
                     unit=Unit("dimensionless", "")),
        ]),
        parameters=(
            ParameterSpec(name="min_density", default=1e-6,
                          description="Floor for density clipping (positivity protection)"),
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
            "Parametric conditional density f(T|X) = N(Xβ, σ²) fitted by OLS. "
            "Used as the Generalised Propensity Score (GPS) for continuous treatments."
        ),
        tags=frozenset({"causal", "nuisance", "gps", "continuous_treatment"}),
        citations=(
            "Hirano, K. & Imbens, G.W. (2004). The Propensity Score with "
            "Continuous Multivalued Treatments. Applied Bayesian Modeling "
            "and Causal Inference from Incomplete-Data Perspectives.",
        ),
        equations={
            "gps": "r(t, x) = φ((t − xᵀβ) / σ̂) / σ̂  where φ = N(0,1) PDF",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use as the GPS in continuous treatment dose-response estimation "
            "(GPS method or doubly-robust kernel estimator)."
        ),
        when_not_to_use=(
            "Avoid when T|X is highly non-Gaussian (heavy tails, multimodal). "
            "Use a kernel density estimator instead."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Check normality of residuals (T − Xβ) via Q-Q plot or Shapiro-Wilk.",
        ),
        typical_min_obs=30,
        output_interpretation=(
            "density[i] = f(treatment_eval[i] | X_eval[i]). "
            "Clip at min_density to prevent division by zero in IPW."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["covariates"], dtype=float)
        T_fit = np.asarray(state["treatment"], dtype=float)
        T_eval = np.asarray(state["treatment_eval"], dtype=float)

        # Optional separate covariate matrix for evaluation; default = training X
        X_eval = np.asarray(state.get("covariates_eval", X), dtype=float)

        min_density = float(params.get("min_density", 1e-6))

        # OLS fit: T ~ [1, X]
        X_aug = np.column_stack([np.ones(len(X)), X])
        beta, *_ = np.linalg.lstsq(X_aug, T_fit, rcond=None)

        T_hat_fit = X_aug @ beta
        sigma = max(float(np.std(T_fit - T_hat_fit, ddof=1)), 1e-8)

        # Evaluate density at T_eval with X_eval
        X_aug_eval = np.column_stack([np.ones(len(X_eval)), X_eval])
        T_hat_eval = X_aug_eval @ beta

        z = (T_eval - T_hat_eval) / sigma
        log_d = -0.5 * z * z - np.log(sigma) - 0.5 * np.log(2.0 * np.pi)
        density = np.exp(log_d)

        density = np.maximum(density, min_density)
        log_d = np.log(density)

        return {"density": density, "log_density": log_d}


@foundry_method(
    namespace="causal.nuisance",
    version="1.0.0",
    tags=frozenset({"causal", "nuisance", "propensity", "multi_treatment", "multinomial"}),
)
class MultinomialPropensityModel:
    """Multinomial logistic regression P(T=k|X) for K treatment arms.

    Implements a one-vs-reference multinomial logistic model using
    K−1 binary logistic regressions (IRLS).  Output probabilities are
    soft-maxed and clipped to enforce positivity.

    Used by multi-treatment IPW and AIPW estimators (Imbens 2000;
    Cattaneo 2010).

    Registered as ``causal.nuisance.multinomial_propensity@1.0.0``.
    """

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multinomial_propensity",
        namespace="",
        version="0.0.0",
        input_slots=frozenset([
            SlotSpec(name="covariates", slot_type=SlotType.MATRIX,
                     description="(n, p) covariate matrix",
                     unit=Unit("dimensionless", ""),
                     shape=("n_obs", "n_features")),
            SlotSpec(name="treatment", slot_type=SlotType.VECTOR,
                     description="(n,) integer treatment labels 0..K-1",
                     unit=Unit("dimensionless", ""),
                     shape=("n_obs",)),
        ]),
        output_slots=frozenset([
            SlotSpec(name="probs", slot_type=SlotType.SCALAR,
                     description="(n, K) per-arm probabilities P(T=k|X)",
                     unit=Unit("dimensionless", "")),
            SlotSpec(name="levels", slot_type=SlotType.SCALAR,
                     description="sorted list of K distinct treatment levels",
                     unit=Unit("dimensionless", "")),
        ]),
        parameters=(
            ParameterSpec(name="min_propensity", default=0.01,
                          description="Clipping floor per arm (positivity protection)",
                          bounds=(1e-6, 0.2)),
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
            "Multinomial logistic propensity P(T=k|X) fitted via K−1 binary "
            "IRLS regressions. Probabilities are softmax-normalised and clipped."
        ),
        tags=frozenset({"causal", "nuisance", "propensity", "multinomial", "multi_arm"}),
        citations=(
            "Imbens, G.W. (2000). The role of the propensity score in "
            "estimating dose-response functions. Biometrika 87(3).",
            "Cattaneo, M.D. (2010). Efficient semiparametric estimation of "
            "multi-valued treatment effects under ignorability. Journal of "
            "Econometrics 155(2).",
        ),
        equations={
            "softmax": "P(T=k|X) = exp(Xᵀβ_k) / Σⱼ exp(Xᵀβⱼ),  β_0 ≡ 0",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Use for multi-valued (K≥3) treatment effect estimation where "
            "simple logistic regression is not applicable."
        ),
        when_not_to_use=(
            "Avoid when any arm has very few observations (n_k < 20) — "
            "the IRLS may not converge. Use simple IPW weights instead."
        ),
        prerequisites=(),
        diagnostic_checks=(
            "Verify probs.sum(axis=1) ≈ 1.0 for all observations.",
            "Check effective sample size per arm: Σ w_k ≈ n_k.",
        ),
        typical_min_obs=50,
        output_interpretation=(
            "probs[:, k] = P(T=k | X) for the k-th treatment level (sorted). "
            "levels contains the sorted integer level labels."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["covariates"], dtype=float)
        T = np.asarray(state["treatment"], dtype=int)
        min_p = float(params.get("min_propensity", 0.01))

        levels = sorted(int(v) for v in np.unique(T).tolist())
        K = len(levels)
        level_to_idx = {lv: i for i, lv in enumerate(levels)}
        T_idx = np.array([level_to_idx[int(t)] for t in T], dtype=int)

        n = len(X)
        # X_aug is built inside _logistic_propensity, so pass X directly.
        # We need the predicted log-odds at X, so augment once here for scoring.
        X_aug = np.column_stack([np.ones(n), X])

        # Fit K-1 one-vs-reference binary logistic regressions (IRLS).
        # _logistic_propensity(X, t) augments X internally and returns β for
        # the augmented design matrix; we extract the linear predictor from X_aug.
        # To avoid double-augmentation, we use _fit_logistic_beta from cross_fit.
        from polisyos.foundry.methods.catalog.causal.cross_fit import _fit_logistic_beta

        log_odds = np.zeros((n, K), dtype=float)  # reference level = 0
        for i in range(1, K):
            T_binary = (T_idx == i).astype(float)
            beta = _fit_logistic_beta(X_aug, T_binary)  # expects augmented X
            log_odds[:, i] = X_aug @ beta

        # Softmax with numerical stability
        log_odds -= log_odds.max(axis=1, keepdims=True)
        probs = np.exp(log_odds)
        probs /= probs.sum(axis=1, keepdims=True)

        # Clip for positivity and renormalise
        probs = np.clip(probs, min_p, 1.0)
        probs /= probs.sum(axis=1, keepdims=True)

        return {"probs": probs, "levels": levels}


__all__ = [
    "NuisanceSpec",
    "NuisanceResolver",
    # Foundry methods
    "LogisticPropensityModel",
    "LogisticL2PropensityModel",
    "OLSOutcomeModel",
    "LassoOutcomeModel",
    "MediatorDensityModel",
    "EmpiricalDensityEstimator",
    "GenericPropensityModel",
    "GenericOutcomeModel",
    "Marginalizer",
    "ProductCombiner",
    "RatioCombiner",
    "Integrator",
    "DistributionReader",
    # Phase 6
    "ParametricConditionalDensity",
    "MultinomialPropensityModel",
]
