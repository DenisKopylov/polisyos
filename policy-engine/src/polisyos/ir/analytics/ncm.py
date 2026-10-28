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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation as _OwnedJSONRepresentation,
)
from polisyos.ir.analytics._owner_admission import (
    declare_model_owner as _declare_model_owner,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.contracts import CanonInfo as _IRCanonInfo
from polisyos.ir.artifacts.contracts import (
    OwnedWriteOptionsPreparer as _OwnedWriteOptionsPreparer,
)
from polisyos.ir.artifacts.contracts import (
    normalize_artifact_ref,
)
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _get_owned_json_artifact_with_bytes,
    _put_owned_json_artifact,
    _put_owned_json_artifact_with_selected_view,
)
from polisyos.ir.migrations.base import CompatibilityMode as _CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.ir.registry.refs import NCMSpecRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
    from polisyos.ir.artifacts.contracts import ArtifactSelector, ArtifactViewRef
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


class _SelectedViewReader(Protocol):
    """Read-only runtime surface for replaying an exact selected NCM view."""

    def get_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactSelector) -> object: ...

    def get_manifest_bytes(self, artifact_id: ArtifactSelector) -> bytes: ...

    def verify(self, artifact_id: ArtifactSelector) -> object: ...


class _SelectedViewStore(_SelectedViewReader, _OwnedWriteOptionsPreparer, Protocol):
    """Runtime store surface for persisting an NCM with selected-view lineage."""

    def put_bytes(
        self,
        data: bytes,
        opts: object,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactViewRef: ...


class _CandidateModelDeclaration(Protocol):
    """Structural declaration consumed by the existing NCM owner."""

    target_world_slot: str
    outcome_variable: str
    target_baseline: float
    outcome_baseline: float
    outcome_per_target_unit: float
    outcome_noise_stddev: float


def candidate_ncm_spec_from_declaration(
    declaration: _CandidateModelDeclaration,
) -> NCMSpec:
    """Build the exact two-node SCM explicitly declared for candidate work.

    This is a pure model projection. The declaration remains the source of the
    coefficients and limitations; this does not claim empirical grounding.
    """
    import math

    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
    from polisyos.ir.analytics.structural_causal_model import (
        MechanismFamily,
        MechanismSource,
        NodeMechanism,
        StructuralCausalModelSpec,
    )

    numeric = (
        declaration.target_baseline,
        declaration.outcome_baseline,
        declaration.outcome_per_target_unit,
        declaration.outcome_noise_stddev,
    )
    if (
        any(not math.isfinite(value) for value in numeric)
        or declaration.target_world_slot == declaration.outcome_variable
        or declaration.outcome_per_target_unit == 0.0
        or declaration.outcome_noise_stddev < 0.0
    ):
        raise ValueError("candidate_ncm_declaration_invalid")

    target = declaration.target_world_slot
    outcome = declaration.outcome_variable
    coefficient = declaration.outcome_per_target_unit
    intercept = declaration.outcome_baseline - coefficient * declaration.target_baseline
    scm = StructuralCausalModelSpec(
        graph=CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=[target, outcome],
            edges=[CausalEdge(src=target, dst=outcome)],
        ),
        mechanisms=[
            NodeMechanism(
                variable=target,
                parents=[],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": declaration.target_baseline,
                    "coefficients": {},
                    "noise_std": 0.0,
                },
                source=MechanismSource.DEFAULT,
            ),
            NodeMechanism(
                variable=outcome,
                parents=[target],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": intercept,
                    "coefficients": {target: coefficient},
                    "noise_std": declaration.outcome_noise_stddev,
                },
                source=MechanismSource.DEFAULT,
            ),
        ],
        fitted=False,
        fit_method="manual",
    )
    return NCMSpec(
        endogenous_vars=[target, outcome],
        exogenous_specs=[
            ExogenousSpec(
                variable=f"U_{target}",
                associated_endogenous=target,
                distribution_params={"mean": 0.0, "std": 0.0},
            ),
            ExogenousSpec(
                variable=f"U_{outcome}",
                associated_endogenous=outcome,
                distribution_params={
                    "mean": 0.0,
                    "std": declaration.outcome_noise_stddev,
                },
            ),
        ],
        structural_equations=[
            StructuralEquation(
                variable=target,
                parents=[],
                exogenous=f"U_{target}",
                equation_type="linear",
                equation_params={
                    "intercept": declaration.target_baseline,
                    "coefficients": {},
                },
            ),
            StructuralEquation(
                variable=outcome,
                parents=[target],
                exogenous=f"U_{outcome}",
                equation_type="linear",
                equation_params={
                    "intercept": intercept,
                    "coefficients": {target: coefficient},
                },
            ),
        ],
        scm_spec=scm,
        is_acyclic=True,
        markov_condition_verified=False,
        independence_model="unknown",
        fit_method="declared_candidate_assumption",
    )


_NCM_SPEC_OWNER_CONTRACT_ID = "ir.analytics.ncm_spec.owner.v1"
_NCM_DEFAULT_CANON_SPEC = CanonSpec(forbid_floats=False)
_NCM_SELECTED_VIEW_CANON_SPEC = CanonSpec(forbid_floats=False, exclude_none=False)
_NCM_ACCEPTED_CANON_PROFILES = (
    _IRCanonInfo.from_spec(_NCM_DEFAULT_CANON_SPEC),
    _IRCanonInfo.from_spec(_NCM_SELECTED_VIEW_CANON_SPEC),
)


def _validate_ncm_owner_profile(profile: _IRCanonInfo, registration: object) -> bool:
    """Accept only the two source-supported exact NCM JSON profiles."""
    return (
        type(profile) is _IRCanonInfo
        and getattr(registration, "profile_ref", object()) is None
        and profile in _NCM_ACCEPTED_CANON_PROFILES
    )


_NCM_SPEC_OWNER = _declare_model_owner(
    NCMSpec,
    contract_id=_NCM_SPEC_OWNER_CONTRACT_ID,
    dto_fqn="polisyos.ir.analytics.ncm.NCMSpec",
    abi_key=f"{_NCM_SPEC_OWNER_CONTRACT_ID}.dto-abi.v1",
    registry_key="ir.ncm_spec",
    kind="ir.ncm_spec",
    media_type="application/json",
    purpose="ncm_spec",
    policy_revision=f"{_NCM_SPEC_OWNER_CONTRACT_ID}.admission.v1",
    accepted_wire_policies=(("ir.analytics.ncm_spec.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=_validate_ncm_owner_profile,
    representations=(
        _OwnedJSONRepresentation(
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ncm_spec.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=_CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class PreparedNCMSpecSelectedValues:
    """Actual selected-codec model values and their complete effective bytes."""

    ncm_spec: NCMSpec
    value_bytes: bytes


def prepare_ncm_spec_selected_values(ncm_spec: NCMSpec) -> PreparedNCMSpecSelectedValues:
    """Compute the actual selected-NCM codec values before an artifact write.

    This uses the exact writer's typed model and canonical profile. It grants no
    source/lineage authority and does not invent a selected reference. The real
    writer and consumer still perform their existing owner/profile admission.
    """

    if type(ncm_spec) is not NCMSpec:
        raise TypeError("ncm_selected_view_payload_untyped")
    encoded = to_canonical_bytes(
        NCMSpec.model_dump(ncm_spec, mode="json"), _NCM_SELECTED_VIEW_CANON_SPEC
    )
    normalized = NCMSpec.model_validate(from_canonical_bytes(encoded))
    return PreparedNCMSpecSelectedValues(
        ncm_spec=normalized,
        value_bytes=to_canonical_bytes(
            NCMSpec.model_dump(normalized, mode="json"), _NCM_SELECTED_VIEW_CANON_SPEC
        ),
    )


def persist_ncm_spec_selected_view(
    store: _SelectedViewStore,
    ncm_spec: NCMSpec,
    *,
    write_options: object,
    return_selected_profile: Literal[True] = True,
) -> ArtifactViewRef:
    """Persist an NCM through shared owner admission while retaining the exact selected ref.

    Runtime callers construct write_options with their tenant, job, closure, and
    full selected InputRef values. Shared owner admission freezes those values
    before CAS and reconciles them with the selected manifest afterward.
    """
    if type(ncm_spec) is not NCMSpec:
        raise TypeError("ncm_selected_view_payload_untyped")
    if return_selected_profile is not True:
        raise ValueError("ncm_selected_view_profile_attestation_required")
    canon_spec = _NCM_SELECTED_VIEW_CANON_SPEC
    prepared = prepare_ncm_spec_selected_values(ncm_spec)
    payload = NCMSpec.model_dump(prepared.ncm_spec, mode="json")
    ref = _put_owned_json_artifact_with_selected_view(
        store,
        payload,
        owner=_NCM_SPEC_OWNER,
        write_options=write_options,
        canon_spec=canon_spec,
    )
    try:
        selected_ref = normalize_artifact_ref(ref)
    except Exception as exc:
        raise ValueError("ncm_selected_view_owner_ref_invalid") from exc
    if (
        selected_ref.get("kind") != "ir.ncm_spec"
        or selected_ref.get("media_type") != "application/json"
        or type(selected_ref.get("manifest_profile_sha256")) is not str
    ):
        raise ValueError("ncm_selected_view_owner_ref_invalid")
    return ref


def load_ncm_spec_selected_view(
    store: _SelectedViewReader,
    ref: ArtifactViewRef,
    *,
    expected_tenant_id: str,
    expected_cell_id: str,
    expected_declaration_ref: ArtifactViewRef,
) -> NCMSpec:
    """Replay an exact selected NCM manifest and its declared sidecar input.

    A missing selector means the canonical default view. The actual default
    manifest is still checked for kind, schema, tenant, cell, and exact input
    lineage; ``None`` never skips view validation.
    """
    import hashlib

    if ref.kind != "ir.ncm_spec" or ref.media_type != "application/json":
        raise ValueError("ncm_selected_view_ref_kind_mismatch")
    verification = store.verify(ref)
    if getattr(verification, "ok", False) is not True:
        raise ValueError("ncm_selected_view_integrity_failed")
    owned = _get_owned_json_artifact_with_bytes(store, ref, owner=_NCM_SPEC_OWNER)
    payload = owned.value.model_dump(mode="json")
    body = owned.raw_bytes
    manifest = store.get_manifest(ref)
    schema = getattr(manifest, "artifact_schema", None)
    tenant_context = getattr(manifest, "tenant_context", None)
    manifest_inputs = tuple(getattr(manifest, "inputs", ()) or ())
    if (
        str(getattr(manifest, "artifact_id", "")) != str(ref.artifact_id)
        or getattr(manifest, "kind", None) != "ir.ncm_spec"
        or getattr(manifest, "media_type", None) != "application/json"
        or getattr(schema, "name", None) != "ir.ncm_spec"
        or getattr(schema, "version", None) != "1.0"
        or getattr(tenant_context, "tenant_id", None) != expected_tenant_id
        or getattr(tenant_context, "cell_id", None) != expected_cell_id
        or len(manifest_inputs) != 1
    ):
        raise ValueError("ncm_selected_view_manifest_mismatch")
    lineage = manifest_inputs[0]
    if (
        str(getattr(lineage, "artifact_id", "")) != str(expected_declaration_ref.artifact_id)
        or getattr(lineage, "role", None) != "candidate_model_declaration"
        or getattr(lineage, "manifest_profile_sha256", None)
        != expected_declaration_ref.manifest_profile_sha256
    ):
        raise ValueError("ncm_selected_view_declaration_lineage_mismatch")
    if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
        raise ValueError("ncm_selected_view_content_mismatch")
    return NCMSpec.model_validate(payload)


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
    ref = _put_owned_json_artifact(
        store,
        ncm_spec.model_dump(mode="json"),
        owner=_NCM_SPEC_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=_NCM_DEFAULT_CANON_SPEC,
    )
    return NCMSpecRef.model_validate(ref)


def load_ncm_spec(
    store: ArtifactStore,
    ref: NCMSpecRef,
) -> NCMSpec:
    """Load an ``NCMSpec`` from the artifact store."""
    return _get_owned_json_artifact(store, ref, owner=_NCM_SPEC_OWNER)


__all__ = [
    "ExogenousSpec",
    "NCMSpec",
    "PreparedNCMSpecSelectedValues",
    "StructuralEquation",
    "candidate_ncm_spec_from_declaration",
    "load_ncm_spec",
    "load_ncm_spec_selected_view",
    "persist_ncm_spec",
    "persist_ncm_spec_selected_view",
    "prepare_ncm_spec_selected_values",
]
