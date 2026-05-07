"""
Semantic Slot Schema Registry.

Provides a global catalogue of *named slot schemas* that give each slot name
a stable semantic meaning beyond its dtype and shape.  Two slots may have the
same dtype/shape yet be semantically incompatible (e.g. ``"outcome"`` and
``"instrument"`` are both float64 vectors but connecting one to the other is a
modelling error).

The ``SlotLinker`` uses this registry in *strict semantic mode* to reject
connections where the source output slot and the target input slot carry
different ``semantics`` labels.

Design
------
- ``SlotSchema`` is a frozen dataclass — schemas are immutable once defined.
- ``SLOT_SCHEMA_REGISTRY`` is the canonical source of truth and ships ~40
  entries covering all standard slots used in the PolicyOS catalog.
- Third-party plugins can extend the registry via
  ``register_slot_schema()`` before their methods are registered.
- Semantic compatibility is checked in ``is_semantically_compatible()``.

Semantic groups
---------------
Slots in the same ``semantics`` group are interchangeable.  Slots in different
groups are incompatible unless an explicit ``allowed_targets`` override is set.

Example
-------
::

    from polisyos.foundry.methods.components.slot_schema import (
        SLOT_SCHEMA_REGISTRY,
        is_semantically_compatible,
    )

    compatible = is_semantically_compatible("outcome", "treatment_effect")
    # → False (different semantics)

    compatible = is_semantically_compatible("outcome", "residual")
    # → True (both belong to "continuous_outcome" or "residual" which is
    #   sub-compatible with "continuous_outcome")
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "SLOT_SCHEMA_REGISTRY",
    "SemanticCompatibilityError",
    "SlotSchema",
    "get_slot_schema",
    "is_semantically_compatible",
    "register_slot_schema",
]


# ---------------------------------------------------------------------------
# SlotSchema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SlotSchema:
    """
    Describes the canonical meaning of a slot name.

    Attributes
    ----------
    name:
        Canonical slot name used in ``SlotSpec.name``.
    dtype:
        Expected NumPy dtype.  ``None`` means dtype is unconstrained.
    semantics:
        Semantic group label.  Two slots are *compatible* iff they share the
        same label or one is listed in the other's ``allowed_targets``.
    description:
        Human-readable description for documentation and CLI tooling.
    allowed_targets:
        Set of *other* semantics labels this slot can be connected to.
        For example, ``"continuous_outcome"`` can target ``"residual"``
        because residuals are derived from outcomes.
    nullable:
        Whether the slot can carry NaN values.
    """

    name: str
    dtype: np.dtype | None
    semantics: str
    description: str
    allowed_targets: frozenset[str] = field(default_factory=frozenset)
    nullable: bool = False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_registry: dict[str, SlotSchema] = {}

# Public alias — read-only view exposed via __all__
SLOT_SCHEMA_REGISTRY: dict[str, SlotSchema] = _registry


def get_slot_schema(name: str) -> SlotSchema | None:
    """Return the schema for *name*, or None if not registered."""
    return _registry.get(name)


def register_slot_schema(schema: SlotSchema, *, override: bool = False) -> None:
    """
    Add *schema* to the global registry.

    Parameters
    ----------
    schema:
        The schema to register.
    override:
        If True, replace an existing schema with the same name.
        If False (default), raise ``ValueError`` on duplicates.
    """
    if schema.name in _registry and not override:
        raise ValueError(
            f"SlotSchema '{schema.name}' is already registered. Pass override=True to replace it."
        )
    if schema.name in _registry and override and _registry[schema.name] != schema:
        warnings.warn(
            f"Overwriting SlotSchema '{schema.name}' with a new definition.",
            stacklevel=2,
        )
    _registry[schema.name] = schema


def is_semantically_compatible(source_slot: str, target_slot: str) -> bool:
    """
    Return True if *source_slot* can be connected to *target_slot*.

    Rules (in order):
    1. If either slot is unknown → compatible (unknown = unconstrained).
    2. If both have the same semantics → compatible.
    3. If source.allowed_targets contains target.semantics → compatible.
    4. If target.allowed_targets contains source.semantics → compatible.
    5. Otherwise → incompatible.
    """
    src = _registry.get(source_slot)
    tgt = _registry.get(target_slot)

    if src is None or tgt is None:
        return True  # unknown slot → no constraint

    if src.semantics == tgt.semantics:
        return True

    if tgt.semantics in src.allowed_targets:
        return True

    if src.semantics in tgt.allowed_targets:
        return True

    return False


class SemanticCompatibilityError(Exception):
    """Raised by linker when source and target slots are semantically incompatible."""

    def __init__(self, source: str, target: str) -> None:
        src_schema = _registry.get(source)
        tgt_schema = _registry.get(target)
        src_sem = src_schema.semantics if src_schema else "unknown"
        tgt_sem = tgt_schema.semantics if tgt_schema else "unknown"
        super().__init__(
            f"Semantic slot incompatibility: '{source}' ({src_sem}) "
            f"→ '{target}' ({tgt_sem}). "
            "These slots carry different semantic meanings and cannot be linked. "
            "Use an explicit mapping or register an allowed_target override."
        )
        self.source = source
        self.target = target


# ---------------------------------------------------------------------------
# Canonical slot schemas
# ---------------------------------------------------------------------------

_F64 = np.dtype("float64")
_I64 = np.dtype("int64")
_BOOL = np.dtype("bool")

# -- Observational outcome slots --
register_slot_schema(
    SlotSchema(
        name="outcome",
        dtype=_F64,
        semantics="continuous_outcome",
        description="Continuous dependent variable (Y) in an observational or experimental study.",
        allowed_targets=frozenset({"residual", "predicted_outcome", "counterfactual_outcome"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="binary_outcome",
        dtype=_F64,
        semantics="binary_outcome",
        description="Binary (0/1) dependent variable.",
        allowed_targets=frozenset({"predicted_probability"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="count_outcome",
        dtype=_F64,
        semantics="count_outcome",
        description="Non-negative integer count dependent variable.",
    )
)

# -- Treatment / intervention slots --
register_slot_schema(
    SlotSchema(
        name="treatment",
        dtype=_F64,
        semantics="binary_treatment",
        description="Binary or continuous treatment indicator (D).",
        allowed_targets=frozenset({"treatment_prob", "propensity_score"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="binary_treatment",
        dtype=_BOOL,
        semantics="binary_treatment",
        description="Strict binary treatment assignment.",
    )
)
register_slot_schema(
    SlotSchema(
        name="treatment_timing",
        dtype=_F64,
        semantics="treatment_timing",
        description="Period in which the unit first received treatment (staggered DiD).",
        nullable=True,
    )
)
register_slot_schema(
    SlotSchema(
        name="treatment_prob",
        dtype=_F64,
        semantics="propensity_score",
        description="Estimated probability of treatment assignment (propensity score).",
    )
)
register_slot_schema(
    SlotSchema(
        name="propensity_score",
        dtype=_F64,
        semantics="propensity_score",
        description="Propensity score P(D=1|X).",
    )
)

# -- Design matrix / covariates --
register_slot_schema(
    SlotSchema(
        name="covariates",
        dtype=_F64,
        semantics="design_matrix",
        description="Matrix of pre-treatment covariates (confounders).",
    )
)
register_slot_schema(
    SlotSchema(
        name="design_matrix",
        dtype=_F64,
        semantics="design_matrix",
        description="Full design matrix including intercept column.",
    )
)
register_slot_schema(
    SlotSchema(
        name="lagged_covariates",
        dtype=_F64,
        semantics="design_matrix",
        description="One-period-lagged covariate matrix for dynamic models.",
    )
)

# -- Panel data identifiers --
register_slot_schema(
    SlotSchema(
        name="entity_id",
        dtype=_I64,
        semantics="panel_entity",
        description="Integer identifier for the cross-sectional unit (person, firm, region).",
    )
)
register_slot_schema(
    SlotSchema(
        name="unit_id",
        dtype=_I64,
        semantics="panel_entity",
        description="Alias for entity_id.",
    )
)
register_slot_schema(
    SlotSchema(
        name="time_id",
        dtype=_I64,
        semantics="panel_time",
        description="Integer period index (year, quarter, month).",
    )
)
register_slot_schema(
    SlotSchema(
        name="period",
        dtype=_I64,
        semantics="panel_time",
        description="Alias for time_id.",
    )
)

# -- Instrument / IV slots --
register_slot_schema(
    SlotSchema(
        name="instrument",
        dtype=_F64,
        semantics="iv_instrument",
        description="Instrumental variable Z (excluded from outcome equation).",
    )
)
register_slot_schema(
    SlotSchema(
        name="instruments",
        dtype=_F64,
        semantics="iv_instrument",
        description="Matrix of instrumental variables.",
    )
)

# -- RDD running variable --
register_slot_schema(
    SlotSchema(
        name="running_var",
        dtype=_F64,
        semantics="rdd_running",
        description="Continuous running variable for RDD (e.g. test score, birth date offset).",
    )
)
register_slot_schema(
    SlotSchema(
        name="forcing_var",
        dtype=_F64,
        semantics="rdd_running",
        description="Alias for running_var.",
    )
)

# -- Estimation output slots --
register_slot_schema(
    SlotSchema(
        name="treatment_effect",
        dtype=_F64,
        semantics="treatment_effect_estimate",
        description="Point estimate of the average treatment effect (ATE/ATT/LATE).",
    )
)
register_slot_schema(
    SlotSchema(
        name="ate",
        dtype=_F64,
        semantics="treatment_effect_estimate",
        description="Average Treatment Effect (ATE).",
    )
)
register_slot_schema(
    SlotSchema(
        name="att",
        dtype=_F64,
        semantics="treatment_effect_estimate",
        description="Average Treatment Effect on the Treated (ATT).",
    )
)
register_slot_schema(
    SlotSchema(
        name="local_ate",
        dtype=_F64,
        semantics="treatment_effect_estimate",
        description="Local ATE at regression discontinuity threshold.",
    )
)
register_slot_schema(
    SlotSchema(
        name="cate",
        dtype=_F64,
        semantics="heterogeneous_treatment_effect",
        description="Conditional (heterogeneous) Average Treatment Effect.",
    )
)
register_slot_schema(
    SlotSchema(
        name="coefficients",
        dtype=_F64,
        semantics="regression_coefficients",
        description="OLS / IV / panel regression coefficient vector.",
    )
)
register_slot_schema(
    SlotSchema(
        name="standard_errors",
        dtype=_F64,
        semantics="regression_se",
        description="Standard errors of regression coefficients.",
        allowed_targets=frozenset({"confidence_interval_width"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="conf_int_lower",
        dtype=_F64,
        semantics="confidence_interval",
        description="Lower bound of a 95% confidence interval.",
    )
)
register_slot_schema(
    SlotSchema(
        name="conf_int_upper",
        dtype=_F64,
        semantics="confidence_interval",
        description="Upper bound of a 95% confidence interval.",
    )
)
register_slot_schema(
    SlotSchema(
        name="p_value",
        dtype=_F64,
        semantics="hypothesis_test_pvalue",
        description="Two-sided p-value for a null hypothesis test.",
    )
)
register_slot_schema(
    SlotSchema(
        name="residual",
        dtype=_F64,
        semantics="residual",
        description="Regression residuals ε = Y − Ŷ.",
        allowed_targets=frozenset({"continuous_outcome"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="predicted_outcome",
        dtype=_F64,
        semantics="predicted_outcome",
        description="In-sample or out-of-sample prediction Ŷ.",
        allowed_targets=frozenset({"continuous_outcome"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="counterfactual_outcome",
        dtype=_F64,
        semantics="counterfactual_outcome",
        description="Counterfactual potential outcome Y(0) under no-treatment.",
        allowed_targets=frozenset({"continuous_outcome"}),
    )
)

# -- Spatial / graph slots --
register_slot_schema(
    SlotSchema(
        name="spatial_weights",
        dtype=_F64,
        semantics="spatial_weights_matrix",
        description="Row-standardised spatial weights matrix W.",
    )
)
register_slot_schema(
    SlotSchema(
        name="coordinates",
        dtype=_F64,
        semantics="geographic_coordinates",
        description="(lon, lat) coordinate matrix for spatial methods.",
    )
)
register_slot_schema(
    SlotSchema(
        name="adjacency_matrix",
        dtype=_F64,
        semantics="graph_adjacency",
        description="Adjacency matrix A for network/graph methods.",
    )
)

# -- Causal graph slots --
register_slot_schema(
    SlotSchema(
        name="dag",
        dtype=None,
        semantics="causal_dag",
        description="Directed Acyclic Graph object (networkx.DiGraph or similar).",
    )
)
register_slot_schema(
    SlotSchema(
        name="discovered_dag",
        dtype=None,
        semantics="causal_dag",
        description="DAG discovered by a structure-learning algorithm.",
    )
)
register_slot_schema(
    SlotSchema(
        name="cpdag",
        dtype=None,
        semantics="causal_cpdag",
        description="Completed Partially Directed Acyclic Graph from PC/FCI.",
    )
)

# -- Optimisation slots --
register_slot_schema(
    SlotSchema(
        name="objective_value",
        dtype=_F64,
        semantics="optimisation_objective",
        description="Optimal value of the objective function.",
    )
)
register_slot_schema(
    SlotSchema(
        name="optimal_allocation",
        dtype=_F64,
        semantics="optimisation_solution",
        description="Optimal primal solution vector x*.",
    )
)
register_slot_schema(
    SlotSchema(
        name="dual_values",
        dtype=_F64,
        semantics="optimisation_dual",
        description="Dual variable (shadow price) vector.",
    )
)

# -- Simulation / welfare slots --
register_slot_schema(
    SlotSchema(
        name="welfare_change",
        dtype=_F64,
        semantics="welfare_metric",
        description="Change in social welfare from a policy intervention.",
    )
)
register_slot_schema(
    SlotSchema(
        name="gini_coefficient",
        dtype=_F64,
        semantics="inequality_metric",
        description="Gini coefficient ∈ [0, 1].",
    )
)

# -- Bayesian / uncertainty slots --
register_slot_schema(
    SlotSchema(
        name="posterior_samples",
        dtype=_F64,
        semantics="mcmc_posterior",
        description="MCMC / VI posterior samples (n_samples × n_params).",
    )
)
register_slot_schema(
    SlotSchema(
        name="posterior_mean",
        dtype=_F64,
        semantics="bayesian_point_estimate",
        description="Posterior mean of parameter vector.",
        allowed_targets=frozenset({"regression_coefficients"}),
    )
)
register_slot_schema(
    SlotSchema(
        name="posterior_std",
        dtype=_F64,
        semantics="bayesian_uncertainty",
        description="Posterior standard deviation.",
        allowed_targets=frozenset({"regression_se"}),
    )
)
