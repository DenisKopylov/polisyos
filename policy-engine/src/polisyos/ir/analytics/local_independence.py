"""Local-independence certificates for continuous-time event-process queries.

These contracts make Stage 4.5 first-class in the proof kernel: they capture
the sufficient graphical and filtration-based conditions under which a policy
effect for a continuous-time event process is identified via intensity
reweighting.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import LocalIndependenceWeightingCertificateRef


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
    def _validate_strings(cls, value: object, info: Any) -> str:
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
    def _validate_nodes(cls, value: object, info: Any) -> str:
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
    def _validate_tuple_fields(cls, value: object, info: Any) -> tuple[str, ...]:
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
    def _validate_strings(cls, value: object, info: Any) -> str | None:
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
    def _validate_tuple_fields(cls, value: object, info: Any) -> tuple[str, ...]:
        return _clean_tuple(value, field_name=str(info.field_name))

    @field_validator("formula_hint", "decensoring_note", mode="before")
    @classmethod
    def _validate_optional_strings(cls, value: object, info: Any) -> str | None:
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
    def _validate_tuple_fields(cls, value: object, info: Any) -> tuple[str, ...]:
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
    def _validate_strings(cls, value: object, info: Any) -> str | None:
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
    def _validate_strings(cls, value: object, info: Any) -> str:
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
    def _validate_tuple_fields(cls, value: object, info: Any) -> tuple[str, ...]:
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
                "independent_censoring_checked": self.graphical_checks.independent_censoring.checked,
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


def persist_local_independence_weighting_certificate(
    store: ArtifactStore,
    certificate: LocalIndependenceWeightingCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.local_independence_weighting_certificate",
    schema_version: str = "1.0",
) -> LocalIndependenceWeightingCertificateRef:
    """Persist a local-independence weighting certificate."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.local_independence_weighting_certificate",
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
    """Load a persisted local-independence weighting certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return LocalIndependenceWeightingCertificate.model_validate(payload)


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
