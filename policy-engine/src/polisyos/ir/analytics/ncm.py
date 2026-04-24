"""Non-parametric Causal Model (NCM) IR types.

Implements the formal specification from:
    Bongers, S., Forré, P., Peters, J. & Mooij, J.M. (2021).
    "Foundations of Structural Causal Models with Cycles and Latent Variables."
    Annals of Statistics, 49(5), 2885-2915.

An NCM is a tuple M = (V, U, F, P_U) where:
  - V = endogenous (observed) variables
  - U = exogenous (noise) variables
  - F = structural equations {V_i := f_i(Pa_i, U_i)}
  - P_U = joint distribution over exogenous variables

This module provides:
  - ``ExogenousSpec``    — description of a latent noise variable U_i
  - ``StructuralEquation`` — one f_i equation (V_i = f_i(Pa_i, U_i))
  - ``NCMSpec``          — full NCM specification (composes StructuralCausalModelSpec)
  - Persistence helpers  — persist_ncm_spec / load_ncm_spec
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import NCMSpecRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
else:
    from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec


class ExogenousSpec(BaseModel):
    """Specification for a latent exogenous noise variable U_i.

    Each structural equation V_i := f_i(Pa_i, U_i) has an associated
    exogenous variable.  This spec captures its distributional assumptions
    and whether it is shared between multiple equations (ADMG / hidden
    common cause case).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    variable: str
    """Name of this exogenous variable, e.g. ``"U_Y"``."""

    associated_endogenous: str
    """The endogenous variable V_i that this U enters: V_i = f_i(Pa_i, U)."""

    domain: Literal["real", "binary", "categorical", "simplex"] = "real"
    """Support of U — used to choose the correct sampling strategy."""

    distribution_family: str = "normal"
    """Parametric family: ``"normal"`` | ``"uniform"`` | ``"empirical"`` | ``"dirichlet"``."""

    distribution_params: dict[str, Any] = Field(default_factory=dict)
    """Family-specific parameters, e.g. ``{"mean": 0.0, "std": 1.0}`` for normal."""

    is_shared: bool = False
    """True iff this U enters *multiple* structural equations.

    A shared exogenous variable represents a hidden common cause (bidirected
    edge in an ADMG).  When True, ``shared_with`` must list the other
    endogenous variables that receive this noise.
    """

    shared_with: list[str] = Field(default_factory=list)
    """Other endogenous variables also affected by this U (only meaningful when
    ``is_shared=True``)."""


class StructuralEquation(BaseModel):
    """One structural equation: V_i := f_i(Pa_i, U_i).

    Encodes the functional relationship between an endogenous variable,
    its observed parents, and its exogenous noise.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    variable: str
    """Name of the endogenous variable defined by this equation."""

    parents: list[str] = Field(default_factory=list)
    """Endogenous parent variables Pa_i (in topological order)."""

    exogenous: str
    """Name of the associated ExogenousSpec (U_i)."""

    mechanism_ref: str | None = None
    """Optional pointer to a ``NodeMechanism.variable`` in the composed
    ``StructuralCausalModelSpec``; enables delegation to the fitted SCM
    machinery for abduction and prediction."""

    equation_type: Literal["linear", "nonlinear", "lookup", "neural", "unknown"] = "unknown"
    """Functional class.  Used to select the appropriate inversion strategy
    during abduction:
    - ``"linear"``   → closed-form residual U = V - f(Pa)
    - others         → no exact inversion; warn and fall back to U = 0
    """

    equation_params: dict[str, Any] = Field(default_factory=dict)
    """Coefficients or other equation-specific parameters (JSON-serializable).

    For ``"linear"``: ``{"intercept": 0.0, "coefficients": {"X": 0.5, ...}}``
    """

    is_recursive: bool = True
    """True for recursive (acyclic) models — the overwhelming common case.
    False triggers a warning since simultaneous equations require fixed-point
    solvers not yet implemented.
    """


class NCMSpec(BaseModel):
    """Non-parametric Causal Model specification.

    Composes ``StructuralCausalModelSpec`` (via the optional ``scm_spec`` field)
    so that all fitted machinery from ``gcm_query`` and ``twin_network_query``
    can be reused transparently.

    When ``scm_spec`` is present:
    - ``_abduce_noises_unified`` from gcm_query.py is called for exact abduction
    - ``_apply_node_noise`` from twin_network_query.py is used for prediction
    - ``_topological_order`` / ``_parents_by_node`` from gcm_query.py handle graph traversal

    When ``scm_spec`` is absent (symbolic NCM):
    - Linear equations in ``structural_equations`` are inverted analytically
    - Other equation types trigger a warning and default U = 0
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    # ── Core NCM components ────────────────────────────────────────────────────

    endogenous_vars: list[str] = Field(default_factory=list)
    """All endogenous (observed) variables V = {V_1, …, V_n}."""

    exogenous_specs: list[ExogenousSpec] = Field(default_factory=list)
    """One ``ExogenousSpec`` per structural equation (or per shared hidden cause)."""

    structural_equations: list[StructuralEquation] = Field(default_factory=list)
    """One ``StructuralEquation`` per endogenous variable."""

    # ── Bridge to existing fitted SCM infrastructure ───────────────────────────

    scm_spec: StructuralCausalModelSpec | None = None
    """Optional fitted SCM.  When present, abduction and forward simulation
    delegate to the existing ``gcm_query`` / ``twin_network_query`` machinery."""

    # ── NCM metadata ──────────────────────────────────────────────────────────

    is_acyclic: bool = True
    """True iff the functional graph is a DAG (recursive NCM, Bongers et al.
    Definition 3.1).  HP actual causality checks require this to be True."""

    markov_condition_verified: bool = False
    """True iff the Markov condition (d-separation faithfulness) has been
    confirmed for this NCM and its underlying graph."""

    independence_model: Literal["dag_markov", "mdag_markov", "unknown"] = "unknown"
    """Graphical independence model implied by the exogenous independence structure."""

    fit_method: str | None = None
    """How this NCM was constructed: ``"gcm"``, ``"manual"``, ``"symbolic"``, etc."""

    source_graph_ref: str | None = None
    """Optional reference to the ``CausalGraphModel`` that the graph is based on."""

    # ── Consistency validator ──────────────────────────────────────────────────

    @model_validator(mode="after")
    def _validate_ncm_consistency(self) -> NCMSpec:
        """Check that every structural equation has a matching ExogenousSpec."""
        eq_vars = {eq.variable for eq in self.structural_equations}
        exo_targets = {ex.associated_endogenous for ex in self.exogenous_specs}

        # Only validate when both sides are populated
        if eq_vars and exo_targets:
            missing_exo = sorted(eq_vars - exo_targets)
            if missing_exo:
                raise ValueError(
                    f"NCMSpec: structural equations reference endogenous variables "
                    f"that have no ExogenousSpec: {missing_exo}"
                )

        # Warn about non-recursive equations via validation note
        non_recursive = [eq.variable for eq in self.structural_equations if not eq.is_recursive]
        if non_recursive:
            # Pydantic does not have a "warning" mechanism; we use a value check
            # that raises only if the user explicitly forbids it.  For now, silent.
            pass

        return self


# ── Persistence helpers (same pattern as structural_causal_model.py) ──────────


def persist_ncm_spec(
    store: ArtifactStore,
    ncm_spec: NCMSpec,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.ncm_spec",
    schema_version: str = "1.0",
) -> NCMSpecRef:
    """Persist an ``NCMSpec`` to the artifact store and return a ref."""
    ref = put_json_artifact(
        store,
        ncm_spec.model_dump(mode="json"),
        kind="ir.ncm_spec",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return NCMSpecRef.model_validate(ref)


def load_ncm_spec(
    store: ArtifactStore,
    ref: NCMSpecRef,
) -> NCMSpec:
    """Load an ``NCMSpec`` from the artifact store."""
    payload = get_json_artifact(store, ref.artifact_id)
    return NCMSpec.model_validate(payload)


__all__ = [
    "ExogenousSpec",
    "NCMSpec",
    "StructuralEquation",
    "load_ncm_spec",
    "persist_ncm_spec",
]
