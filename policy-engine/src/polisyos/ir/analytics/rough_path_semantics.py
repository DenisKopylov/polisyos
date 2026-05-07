"""Typed proof artifacts for rough-path and irregular-sampling semantics.

These contracts implement the Stage 4.1 research result as a machine-checkable
surface. They intentionally separate:

- the proof artifact that justifies a trajectory-level causal claim; and
- the lightweight metadata attachment stored on ``EffectTrajectoryBundle``.

The runtime can therefore distinguish representation-level identification from
latent-path identification without pretending that every irregular-sampling
backend already has production execution support.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import ArtifactRefModel, RoughPathInterventionCertificateRef

_ROUGH_PATH_INTERVENTION_CERTIFICATE_SCHEMA_NAME = "ir.rough_path_intervention_certificate"
_ROUGH_PATH_INTERVENTION_CERTIFICATE_SCHEMA_VERSION = "1.0"


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


class TemporalPathSemanticsScope(str, Enum):
    """Scope of the causal claim carried by a temporal path representation."""

    REPRESENTED_PATH = "represented_path"
    LATENT_PATH = "latent_path"
    SIGNATURE_EQUIVALENCE_CLASS = "signature_equivalence_class"


class RoughPathModelFamily(str, Enum):
    """Dynamic model family used by a rough-path identification certificate."""

    HYBRID_RDE = "hybrid_rde"
    CADLAG_RDE = "cadlag_rde"
    LOCAL_INDEPENDENCE_COUNTING_PROCESS = "local_independence_counting_process"
    HYBRID_ROUGH_EVENT = "hybrid_rough_event"


class RoughPathTopology(str, Enum):
    """Topology in which well-posedness and continuity claims are stated."""

    P_VARIATION = "p_variation"
    HOLDER = "holder"
    SKOROKHOD = "skorokhod"


class RoughPathGraphCriterion(str, Enum):
    """Graphical criterion used by the irregular-sampling proof path."""

    D_SEP = "d_sep"
    SIGMA_SEP = "sigma_sep"
    DELTA_SEP = "delta_sep"
    MU_SEP = "mu_sep"
    NONE = "none"


class RoughPathInterventionType(str, Enum):
    """Intervention semantics supported by the rough-path contract."""

    POLICY_OVERRIDE = "policy_override"
    RESET_AT_STOPPING_TIME = "reset_at_stopping_time"
    INTENSITY_OVERRIDE = "intensity_override"


class RoughPathIdentificationStrategy(str, Enum):
    """Identification route used by the theorem-backed proof artifact."""

    GENERATOR_IDENTIFICATION = "generator_identification"
    CONTINUOUS_TIME_G_FORMULA = "continuous_time_g_formula"
    LIKELIHOOD_RATIO_REWEIGHTING = "likelihood_ratio_reweighting"
    DO_CALCULUS_REDUCTION = "do_calculus_reduction"
    SIGNATURE_DETERMINING_CLASS = "signature_determining_class"
    BOUNDS_ONLY = "bounds_only"


class RoughPathIdentificationStatus(str, Enum):
    """Final identification verdict for the rough-path proof artifact."""

    IDENTIFIED = "identified"
    IDENTIFIED_REPRESENTATION_ONLY = "identified_representation_only"
    PARTIALLY_IDENTIFIED = "partially_identified"
    BLOCKED = "blocked"


class PathLiftMethod(str, Enum):
    """Canonical lift or interpolation used to build the represented path."""

    PIECEWISE_LINEAR = "piecewise_linear"
    RECTILINEAR = "rectilinear"
    LEAD_LAG = "lead_lag"
    CADLAG_PATH_FUNCTION = "cadlag_path_function"
    LOGSIGNATURE = "logsignature"


class RoughPathInterventionCertificate(BaseModel):
    """Proof-carrying artifact for irregular-sampling causal trajectory claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    semantics_scope: TemporalPathSemanticsScope
    model_family: RoughPathModelFamily
    topology: RoughPathTopology
    graph_criterion: RoughPathGraphCriterion = RoughPathGraphCriterion.NONE
    observation_operator_ref: ArtifactRefModel
    lift_operator_ref: ArtifactRefModel
    interpolation_is_adapted: bool
    future_leakage_ruled_out: bool
    intervention_type: RoughPathInterventionType
    intervention_operator_ref: ArtifactRefModel
    actuatable_component: str = Field(min_length=1)
    filtration_ref: ArtifactRefModel
    well_posedness_ref: ArtifactRefModel
    identification_strategy: RoughPathIdentificationStrategy
    positivity_ref: ArtifactRefModel | None = None
    sampling_ignorability_ref: ArtifactRefModel | None = None
    lift_faithfulness_ref: ArtifactRefModel | None = None
    target_functional_ref: ArtifactRefModel
    proof_trace_ref: ArtifactRefModel
    counterexample_ref: ArtifactRefModel | None = None
    status: RoughPathIdentificationStatus
    scope_notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_refs_and_scope(self) -> RoughPathInterventionCertificate:
        for field_name in (
            "observation_operator_ref",
            "lift_operator_ref",
            "intervention_operator_ref",
            "filtration_ref",
            "well_posedness_ref",
            "target_functional_ref",
            "proof_trace_ref",
        ):
            _validate_artifact_ref(getattr(self, field_name), field_name=field_name)
        for optional_field in (
            "positivity_ref",
            "sampling_ignorability_ref",
            "lift_faithfulness_ref",
            "counterexample_ref",
        ):
            ref = getattr(self, optional_field)
            if ref is not None:
                _validate_artifact_ref(ref, field_name=optional_field)
        if self.semantics_scope is TemporalPathSemanticsScope.LATENT_PATH:
            if self.lift_faithfulness_ref is None:
                raise ValueError("latent_path certificates require lift_faithfulness_ref")
            if self.status is RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY:
                raise ValueError(
                    "latent_path certificates cannot use identified_representation_only status"
                )
        if (
            self.identification_strategy is RoughPathIdentificationStrategy.BOUNDS_ONLY
            and self.status is RoughPathIdentificationStatus.IDENTIFIED
        ):
            raise ValueError("bounds_only certificates cannot claim fully identified status")
        return self


class TemporalPathSemanticsAttachment(BaseModel):
    """Validated metadata contract attached to ``EffectTrajectoryBundle``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantics_scope: TemporalPathSemanticsScope
    lift_method: PathLiftMethod
    topology: RoughPathTopology
    p_variation_order: float | None = Field(default=None, gt=0.0)
    signature_level: int | None = Field(default=None, ge=1)
    interpolation_is_adapted: bool
    future_leakage_ruled_out: bool
    intervention_type: RoughPathInterventionType
    graph_criterion: RoughPathGraphCriterion = RoughPathGraphCriterion.NONE
    proof_artifact_ref: RoughPathInterventionCertificateRef
    sampling_ignorability_checked: bool
    lift_faithfulness_checked: bool = False

    @model_validator(mode="after")
    def _validate_attachment(self) -> TemporalPathSemanticsAttachment:
        _validate_artifact_ref(self.proof_artifact_ref, field_name="proof_artifact_ref")
        if self.topology is RoughPathTopology.P_VARIATION and self.p_variation_order is None:
            raise ValueError("p_variation topology requires p_variation_order")
        if self.lift_method is PathLiftMethod.LOGSIGNATURE and self.signature_level is None:
            raise ValueError("logsignature lift_method requires signature_level")
        if (
            self.semantics_scope is TemporalPathSemanticsScope.LATENT_PATH
            and not self.lift_faithfulness_checked
        ):
            raise ValueError("latent_path semantics require lift_faithfulness_checked=true")
        return self


def persist_rough_path_intervention_certificate(
    store: ArtifactStore,
    certificate: RoughPathInterventionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _ROUGH_PATH_INTERVENTION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _ROUGH_PATH_INTERVENTION_CERTIFICATE_SCHEMA_VERSION,
) -> RoughPathInterventionCertificateRef:
    """Persist a rough-path intervention certificate as a JSON artifact."""

    return RoughPathInterventionCertificateRef.model_validate(
        put_json_artifact(
            store,
            certificate.model_dump(mode="json"),
            kind="ir.rough_path_intervention_certificate",
            schema_name=schema_name,
            schema_version=schema_version,
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )


def load_rough_path_intervention_certificate(
    store: ArtifactStore,
    ref: RoughPathInterventionCertificateRef,
) -> RoughPathInterventionCertificate:
    """Load a previously persisted rough-path intervention certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return RoughPathInterventionCertificate.model_validate(payload)


__all__ = [
    "PathLiftMethod",
    "RoughPathGraphCriterion",
    "RoughPathIdentificationStatus",
    "RoughPathIdentificationStrategy",
    "RoughPathInterventionCertificate",
    "RoughPathInterventionType",
    "RoughPathModelFamily",
    "RoughPathTopology",
    "TemporalPathSemanticsAttachment",
    "TemporalPathSemanticsScope",
    "load_rough_path_intervention_certificate",
    "persist_rough_path_intervention_certificate",
]
