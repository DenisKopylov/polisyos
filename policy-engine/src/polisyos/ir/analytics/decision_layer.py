"""Persisted Phase 3 decision-layer artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import (
    ArtifactRefModel,
    FiscalFeedbackLinkRef,
    OptimizationAmbiguityCertificateRef,
    SocialWeightManifestRef,
)

_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_NAME = "ir.optimization_ambiguity_certificate"
_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_VERSION = "1.0"
_SOCIAL_WEIGHT_MANIFEST_SCHEMA_NAME = "ir.social_weight_manifest"
_SOCIAL_WEIGHT_MANIFEST_SCHEMA_VERSION = "1.0"
_FISCAL_FEEDBACK_LINK_SCHEMA_NAME = "ir.fiscal_feedback_link"
_FISCAL_FEEDBACK_LINK_SCHEMA_VERSION = "1.0"


class OptimizationAmbiguityCertificate(BaseModel):
    """Canonical persisted ambiguity artifact consumed by Phase 3 gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mode: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    overall_status: str | None = None
    note: str | None = None
    certificate_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SocialWeightManifestArtifact(BaseModel):
    """Persisted state-dependent social-weight schedule for decision-layer welfare."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    manifest_ref: str | None = None
    method_fqn: str | None = None
    normalization: str | None = None
    income_grid: tuple[float, ...] = ()
    weights_on_grid: tuple[float, ...] = ()
    state_keys: tuple[str, ...] = ()
    regime_ids: tuple[str, ...] = ()
    manifest_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FiscalFeedbackLink(BaseModel):
    """Minimal typed link between behavioral microsim and optimization under ambiguity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    linkage_mode: str = Field(default="behavioral_dro", min_length=1)
    microsim_result_ref: ArtifactRefModel | None = None
    behavior_model_ref: ArtifactRefModel | None = None
    channel_decomposition_ref: ArtifactRefModel | None = None
    optimization_ref: ArtifactRefModel | None = None
    ambiguity_certificate_ref: OptimizationAmbiguityCertificateRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_optimization_ambiguity_certificate(
    payload: Mapping[str, Any] | None,
    *,
    mode: str,
    source_kind: str,
    overall_status: str | None = None,
    note: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> OptimizationAmbiguityCertificate:
    """Build a canonical optimization ambiguity artifact from a raw payload."""

    return OptimizationAmbiguityCertificate(
        mode=str(mode).strip() or "not_applicable",
        source_kind=str(source_kind).strip() or "unknown",
        overall_status=None if overall_status is None else str(overall_status),
        note=None if note is None else str(note),
        certificate_payload=_mapping_to_json_dict(payload),
        metadata=_mapping_to_json_dict(metadata),
    )


def persist_optimization_ambiguity_certificate(
    store: ArtifactStore,
    certificate: OptimizationAmbiguityCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> OptimizationAmbiguityCertificateRef:
    """Persist an optimization ambiguity certificate."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_NAME,
        schema_name=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_NAME,
        schema_version=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OptimizationAmbiguityCertificateRef.model_validate(ref)


def load_optimization_ambiguity_certificate(
    store: ArtifactStore,
    ref: OptimizationAmbiguityCertificateRef,
) -> OptimizationAmbiguityCertificate:
    """Load a persisted optimization ambiguity certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return OptimizationAmbiguityCertificate.model_validate(payload)


def persist_social_weight_manifest(
    store: ArtifactStore,
    artifact: SocialWeightManifestArtifact,
    *,
    inputs: list[InputRef] | None = None,
) -> SocialWeightManifestRef:
    """Persist a state-dependent social-weight manifest."""

    ref = put_json_artifact(
        store,
        artifact.model_dump(mode="json"),
        kind=_SOCIAL_WEIGHT_MANIFEST_SCHEMA_NAME,
        schema_name=_SOCIAL_WEIGHT_MANIFEST_SCHEMA_NAME,
        schema_version=_SOCIAL_WEIGHT_MANIFEST_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SocialWeightManifestRef.model_validate(ref)


def load_social_weight_manifest(
    store: ArtifactStore,
    ref: SocialWeightManifestRef,
) -> SocialWeightManifestArtifact:
    """Load a persisted state-dependent social-weight manifest."""

    payload = get_json_artifact(store, ref.artifact_id)
    return SocialWeightManifestArtifact.model_validate(payload)


def persist_fiscal_feedback_link(
    store: ArtifactStore,
    link: FiscalFeedbackLink,
    *,
    inputs: list[InputRef] | None = None,
) -> FiscalFeedbackLinkRef:
    """Persist a behavioral microsim fiscal-feedback linkage artifact."""

    ref = put_json_artifact(
        store,
        link.model_dump(mode="json"),
        kind=_FISCAL_FEEDBACK_LINK_SCHEMA_NAME,
        schema_name=_FISCAL_FEEDBACK_LINK_SCHEMA_NAME,
        schema_version=_FISCAL_FEEDBACK_LINK_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FiscalFeedbackLinkRef.model_validate(ref)


def load_fiscal_feedback_link(
    store: ArtifactStore,
    ref: FiscalFeedbackLinkRef,
) -> FiscalFeedbackLink:
    """Load a persisted fiscal-feedback linkage artifact."""

    payload = get_json_artifact(store, ref.artifact_id)
    return FiscalFeedbackLink.model_validate(payload)


def _mapping_to_json_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_value(value.model_dump(mode="json"))
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return _json_value(value.to_payload())
    return value


__all__ = [
    "FiscalFeedbackLink",
    "OptimizationAmbiguityCertificate",
    "SocialWeightManifestArtifact",
    "build_optimization_ambiguity_certificate",
    "load_fiscal_feedback_link",
    "load_optimization_ambiguity_certificate",
    "load_social_weight_manifest",
    "persist_fiscal_feedback_link",
    "persist_optimization_ambiguity_certificate",
    "persist_social_weight_manifest",
]
