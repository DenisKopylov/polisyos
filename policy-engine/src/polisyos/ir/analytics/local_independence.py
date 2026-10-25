"""Local-independence certificates for continuous-time event-process queries.

These contracts make Stage 4.5 first-class in the proof kernel: they capture
the sufficient graphical and filtration-based conditions under which a policy
effect for a continuous-time event process is identified via intensity
reweighting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import LocalIndependenceWeightingCertificateRef

if TYPE_CHECKING:
    from polisyos.ir.artifacts import ArtifactStore, InputRef
    from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration


def _clean_string(value: object, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _clean_tuple(value: object, *, field_name: str) -> tuple[str, ...]:
    if value in (None, (), []):
        return ()
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{field_name} must be a tuple/list of strings")
    cleaned = tuple(_clean_string(item, field_name=field_name) for item in value)
    return cleaned


class LocalIndependenceTarget(BaseModel):
    """Target causal functional identified by the certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["marginal_event_process_effect"] = "marginal_event_process_effect"
    functional: str
    outcome_process: str
    horizon_start: float
    horizon_end: float
    time_scale: str
    contrast_policy: str = "pi"
    contrast_baseline: str = "natural_or_pi0"

    @field_validator(
        "functional",
        "outcome_process",
        "time_scale",
        "contrast_policy",
        "contrast_baseline",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: object, info: ValidationInfo) -> str:
        return _clean_string(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_horizon(self) -> LocalIndependenceTarget:
        if self.horizon_start >= self.horizon_end:
            raise ValueError("horizon_start must be strictly less than horizon_end")
        return self


class LocalIndependenceEdge(BaseModel):
    """Directed edge in a local-independence graph or latent projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str
    dst: str
    edge_type: Literal["directed"] = "directed"

    @field_validator("src", "dst", mode="before")
    @classmethod
    def _validate_nodes(cls, value: object, info: ValidationInfo) -> str:
        return _clean_string(value, field_name=str(info.field_name))


class LocalIndependenceGraphSpec(BaseModel):
    """Graph object used for delta/mu-separation reasoning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    process_family: Literal["counting_process", "marked_point_process", "event_log"]
    representation: Literal["LIG", "muDMG", "LIG_or_muDMG"] = "LIG_or_muDMG"
    separation_criterion: Literal["delta", "mu", "delta_or_mu"] = "delta_or_mu"
    graph_ref: str | None = None
    latent_projection_ref: str | None = None
    nodes: tuple[str, ...] = ()
    edges: tuple[LocalIndependenceEdge, ...] = ()
    latent_nodes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator("nodes", "latent_nodes", "notes", mode="before")
    @classmethod
    def _validate_tuple_fields(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))


class TreatmentIntensityInterventionSpec(BaseModel):
    """Policy intervention on the treatment intensity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    policy_type: Literal["intensity_replacement"] = "intensity_replacement"
    predictable_wrt: tuple[str, ...] = ()
    lambda_pi_ref: str | None = None
    absolute_continuity_assumed: bool = True
    bound_note: str | None = None

    @field_validator("node", "bound_note", mode="before")
    @classmethod
    def _validate_strings(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return _clean_string(value, field_name=str(info.field_name))

    @field_validator("predictable_wrt", mode="before")
    @classmethod
    def _validate_predictable(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="predictable_wrt")


class CensoringInterventionSpec(BaseModel):
    """Intervention on censoring used for de-censoring / IPC weighting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str = "C"
    mode: Literal["prevent", "randomize", "prevent_or_randomize"] = "prevent_or_randomize"
    lambda_c_ref: str | None = None
    value: float | None = None

    @field_validator("node", mode="before")
    @classmethod
    def _validate_node(cls, value: object) -> str:
        return _clean_string(value, field_name="node")


class LocalIndependenceIdentificationSpec(BaseModel):
    """Proof-kernel-readable identification recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: Literal["continuous_time_reweighting"] = "continuous_time_reweighting"
    theorem_reference: tuple[str, ...] = ()
    weight_components: tuple[str, ...] = ("W_treatment", "W_censoring")
    formula_hint: str | None = None
    marginalize_over: tuple[str, ...] = ()
    decensoring_map_used: bool = True
    decensoring_note: str | None = None

    @field_validator("theorem_reference", "weight_components", "marginalize_over", mode="before")
    @classmethod
    def _validate_tuple_fields(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @field_validator("formula_hint", "decensoring_note", mode="before")
    @classmethod
    def _validate_optional_strings(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return _clean_string(value, field_name=str(info.field_name))


class IndependentCensoringCheck(BaseModel):
    """Machine-readable witness for local independent censoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checked: bool = False
    criterion: Literal["delta_separation", "mu_separation", "graph_structure", "unknown"] = (
        "unknown"
    )
    statement: str | None = None
    conditioning_set: tuple[str, ...] = ()
    blocked_trails: tuple[str, ...] = ()

    @field_validator("statement", mode="before")
    @classmethod
    def _validate_statement(cls, value: object) -> str | None:
        if value is None:
            return None
        return _clean_string(value, field_name="statement")

    @field_validator("conditioning_set", "blocked_trails", mode="before")
    @classmethod
    def _validate_tuple_fields(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))


class EliminabilityStep(BaseModel):
    """One step in the latent-process elimination witness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: int = Field(ge=1)
    removed: tuple[str, ...]
    justification_kind: str
    witness: str | None = None

    @field_validator("removed", mode="before")
    @classmethod
    def _validate_removed(cls, value: object) -> tuple[str, ...]:
        cleaned = _clean_tuple(value, field_name="removed")
        if not cleaned:
            raise ValueError("removed must be non-empty")
        return cleaned

    @field_validator("justification_kind", "witness", mode="before")
    @classmethod
    def _validate_strings(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        return _clean_string(value, field_name=str(info.field_name))


class EliminabilityCheck(BaseModel):
    """Sequence witness for eliminating latent event processes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checked: bool = False
    target_node: str | None = None
    eliminate_set: tuple[str, ...] = ()
    elimination_sequence: tuple[EliminabilityStep, ...] = ()

    @field_validator("target_node", mode="before")
    @classmethod
    def _validate_target(cls, value: object) -> str | None:
        if value is None:
            return None
        return _clean_string(value, field_name="target_node")

    @field_validator("eliminate_set", mode="before")
    @classmethod
    def _validate_eliminate_set(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="eliminate_set")


class LocalIndependenceGraphicalChecks(BaseModel):
    """All theorem-side graphical obligations used by the certificate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    independent_censoring: IndependentCensoringCheck = Field(
        default_factory=IndependentCensoringCheck
    )
    eliminability: EliminabilityCheck = Field(default_factory=EliminabilityCheck)


class IntensityModelRequirement(BaseModel):
    """Intensity model the estimator/runtime must provide."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    process: str
    conditioning: tuple[str, ...] = ()
    estimation: str

    @field_validator("process", "estimation", mode="before")
    @classmethod
    def _validate_strings(cls, value: object, info: ValidationInfo) -> str:
        return _clean_string(value, field_name=str(info.field_name))

    @field_validator("conditioning", mode="before")
    @classmethod
    def _validate_conditioning(cls, value: object) -> tuple[str, ...]:
        return _clean_tuple(value, field_name="conditioning")


class LocalIndependenceRuntimeRequirements(BaseModel):
    """Estimator/runtime obligations downstream of identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    needed_intensity_models: tuple[IntensityModelRequirement, ...] = ()
    data_contract: str = "event_log_or_counting_process_panel"
    positivity_assumed: bool = True
    diagnostics_required: bool = True

    @field_validator("data_contract", mode="before")
    @classmethod
    def _validate_data_contract(cls, value: object) -> str:
        return _clean_string(value, field_name="data_contract")


class LocalIndependenceWeightingCertificate(BaseModel):
    """Constructive Stage-4.5 certificate for local-independence identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verification_status: Literal["identified", "oracle_needed"] = "oracle_needed"
    theorem_family: str = "local_independence_weighting_v1"
    completeness_regime: Literal["sound_incomplete"] = "sound_incomplete"
    target: LocalIndependenceTarget
    graph: LocalIndependenceGraphSpec
    treatment_intervention: TreatmentIntensityInterventionSpec
    censoring_intervention: CensoringInterventionSpec = Field(
        default_factory=CensoringInterventionSpec
    )
    identification: LocalIndependenceIdentificationSpec = Field(
        default_factory=LocalIndependenceIdentificationSpec
    )
    graphical_checks: LocalIndependenceGraphicalChecks = Field(
        default_factory=LocalIndependenceGraphicalChecks
    )
    runtime_requirements: LocalIndependenceRuntimeRequirements = Field(
        default_factory=LocalIndependenceRuntimeRequirements
    )
    assumptions: tuple[str, ...] = ()
    proof_trace: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("theorem_family", mode="before")
    @classmethod
    def _validate_theorem_family(cls, value: object) -> str:
        return _clean_string(value, field_name="theorem_family")

    @field_validator("assumptions", "proof_trace", mode="before")
    @classmethod
    def _validate_tuple_fields(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_status_requirements(self) -> LocalIndependenceWeightingCertificate:
        if self.verification_status == "identified":
            if not self.graphical_checks.eliminability.checked:
                raise ValueError("identified certificates require eliminability.checked = True")
            if not self.graphical_checks.independent_censoring.checked:
                raise ValueError(
                    "identified certificates require independent_censoring.checked = True"
                )
        return self

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact JSON summary for metadata embedding."""

        return {
            "schema_version": self.schema_version,
            "verification_status": self.verification_status,
            "theorem_family": self.theorem_family,
            "completeness_regime": self.completeness_regime,
            "target": self.target.model_dump(mode="json"),
            "graph": {
                "process_family": self.graph.process_family,
                "representation": self.graph.representation,
                "separation_criterion": self.graph.separation_criterion,
                "graph_ref": self.graph.graph_ref,
                "latent_projection_ref": self.graph.latent_projection_ref,
                "node_count": len(self.graph.nodes),
                "edge_count": len(self.graph.edges),
                "latent_count": len(self.graph.latent_nodes),
            },
            "identification": {
                "method": self.identification.method,
                "theorem_reference": list(self.identification.theorem_reference),
                "weight_components": list(self.identification.weight_components),
                "decensoring_map_used": self.identification.decensoring_map_used,
            },
            "graphical_checks": {
                (
                    "independent_censoring_checked"
                ): self.graphical_checks.independent_censoring.checked,
                "eliminability_checked": self.graphical_checks.eliminability.checked,
                "eliminated_processes": list(self.graphical_checks.eliminability.eliminate_set),
            },
            "runtime_requirements": {
                "data_contract": self.runtime_requirements.data_contract,
                "positivity_assumed": self.runtime_requirements.positivity_assumed,
                "diagnostics_required": self.runtime_requirements.diagnostics_required,
                "needed_intensity_models": [
                    item.model_dump(mode="json")
                    for item in self.runtime_requirements.needed_intensity_models
                ],
            },
            "assumptions": list(self.assumptions),
            "proof_trace": list(self.proof_trace),
        }


_ANALYTICS_ARTIFACT_CANON_SPEC = CanonSpec(forbid_floats=False)


def _declare_owned_model(
    model: type[BaseModel],
    *,
    contract_id: str,
    dto_fqn: str,
    abi_key: str,
    registry_key: str,
    kind: str,
    schema_name: str,
    schema_version: str,
    payload_version: str,
    purpose: str,
    notes: tuple[str, ...],
    compatibility: CompatibilityMode = CompatibilityMode.NONE,
) -> ArtifactOwnerDeclaration[Any, Any]:
    """Declare one exact source-proven DTO/artifact representation."""
    wire_policy_ref = f"{contract_id}.wire"
    return declare_model_owner(
        model,
        contract_id=contract_id,
        dto_fqn=dto_fqn,
        abi_key=abi_key,
        registry_key=registry_key,
        kind=kind,
        media_type="application/json",
        purpose=purpose,
        policy_revision=f"{contract_id}.owner-admission.v1",
        accepted_wire_policies=((wire_policy_ref, "1"),),
        payload_version_field="schema_version",
        validate_profile=owner_profile_for_spec(_ANALYTICS_ARTIFACT_CANON_SPEC, profile_ref=None),
        representations=(
            OwnedJSONRepresentation(
                schema_name=schema_name,
                schema_version=schema_version,
                payload_version=payload_version,
                wire_policy_ref=wire_policy_ref,
                wire_policy_revision="1",
                profile_ref=None,
                compatibility=compatibility,
                notes=notes,
                readable=True,
                writable=True,
                current=True,
                default_write=True,
                readable_from=(),
            ),
        ),
    )


_LOCAL_INDEPENDENCE_OWNER = _declare_owned_model(
    LocalIndependenceWeightingCertificate,
    contract_id="ir.analytics.local_independence.local_independence_weighting_certificate",
    dto_fqn="polisyos.ir.analytics.local_independence.LocalIndependenceWeightingCertificate",
    abi_key="ir.local_independence_weighting_certificate",
    registry_key="ir.local_independence_weighting_certificate",
    kind="ir.local_independence_weighting_certificate",
    schema_name="ir.local_independence_weighting_certificate",
    schema_version="1.0",
    payload_version="1.0",
    purpose="ir_local_independence_weighting_certificate",
    notes=(
        "LocalIndependenceWeightingCertificate 1.0 is the source-proven current representation; unsupported tuples remain closed.",
    ),
)


def persist_local_independence_weighting_certificate(
    store: ArtifactStore,
    certificate: LocalIndependenceWeightingCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.local_independence_weighting_certificate",
    schema_version: str = "1.0",
) -> LocalIndependenceWeightingCertificateRef:
    """Persist LocalIndependenceWeightingCertificate through its exact owner declaration."""
    ref = _put_owned_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        owner=_LOCAL_INDEPENDENCE_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return LocalIndependenceWeightingCertificateRef.model_validate(ref)


def load_local_independence_weighting_certificate(
    store: ArtifactStore,
    ref: LocalIndependenceWeightingCertificateRef,
) -> LocalIndependenceWeightingCertificate:
    """Load LocalIndependenceWeightingCertificate through its exact owner declaration."""
    return _get_owned_json_artifact(store, ref, owner=_LOCAL_INDEPENDENCE_OWNER)


__all__ = [
    "CensoringInterventionSpec",
    "EliminabilityCheck",
    "EliminabilityStep",
    "IndependentCensoringCheck",
    "IntensityModelRequirement",
    "LocalIndependenceEdge",
    "LocalIndependenceGraphSpec",
    "LocalIndependenceGraphicalChecks",
    "LocalIndependenceIdentificationSpec",
    "LocalIndependenceRuntimeRequirements",
    "LocalIndependenceTarget",
    "LocalIndependenceWeightingCertificate",
    "LocalIndependenceWeightingCertificateRef",
    "TreatmentIntensityInterventionSpec",
    "load_local_independence_weighting_certificate",
    "persist_local_independence_weighting_certificate",
]
