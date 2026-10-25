"""Persisted Phase 3 decision-layer artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.artifacts.io import (
    _get_owned_json_artifact,
    _put_owned_json_artifact,
    _validate_return_selected_profile_flag,
)
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
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


_OPTIMIZATION_AMBIGUITY_CERTIFICATE_OWNER = declare_model_owner(
    OptimizationAmbiguityCertificate,
    contract_id="ir.analytics.ir_optimization_ambiguity_certificate.owner.v1",
    dto_fqn="polisyos.ir.analytics.decision_layer.OptimizationAmbiguityCertificate",
    abi_key="ir.analytics.ir_optimization_ambiguity_certificate.owner.v1.dto-abi.v1",
    registry_key="ir.optimization_ambiguity_certificate",
    kind="ir.optimization_ambiguity_certificate",
    media_type="application/json",
    purpose="optimization_ambiguity_certificate",
    policy_revision="ir.analytics.ir_optimization_ambiguity_certificate.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.ir_optimization_ambiguity_certificate.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name="ir.optimization_ambiguity_certificate",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ir_optimization_ambiguity_certificate.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


_SOCIAL_WEIGHT_MANIFEST_OWNER = declare_model_owner(
    SocialWeightManifestArtifact,
    contract_id="ir.analytics.ir_social_weight_manifest.owner.v1",
    dto_fqn="polisyos.ir.analytics.decision_layer.SocialWeightManifestArtifact",
    abi_key="ir.analytics.ir_social_weight_manifest.owner.v1.dto-abi.v1",
    registry_key="ir.social_weight_manifest",
    kind="ir.social_weight_manifest",
    media_type="application/json",
    purpose="social_weight_manifest",
    policy_revision="ir.analytics.ir_social_weight_manifest.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.ir_social_weight_manifest.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name="ir.social_weight_manifest",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ir_social_weight_manifest.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


_FISCAL_FEEDBACK_LINK_OWNER = declare_model_owner(
    FiscalFeedbackLink,
    contract_id="ir.analytics.ir_fiscal_feedback_link.owner.v1",
    dto_fqn="polisyos.ir.analytics.decision_layer.FiscalFeedbackLink",
    abi_key="ir.analytics.ir_fiscal_feedback_link.owner.v1.dto-abi.v1",
    registry_key="ir.fiscal_feedback_link",
    kind="ir.fiscal_feedback_link",
    media_type="application/json",
    purpose="fiscal_feedback_link",
    policy_revision="ir.analytics.ir_fiscal_feedback_link.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.ir_fiscal_feedback_link.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name="ir.fiscal_feedback_link",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ir_fiscal_feedback_link.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def persist_optimization_ambiguity_certificate(
    store: ArtifactStore,
    certificate: OptimizationAmbiguityCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> OptimizationAmbiguityCertificateRef:
    """Persist an optimization ambiguity certificate through its exact owner."""
    ref = _put_owned_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        owner=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_OWNER,
        schema_name=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_NAME,
        schema_version=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return OptimizationAmbiguityCertificateRef.from_selected_write(ref)


def load_optimization_ambiguity_certificate(
    store: ArtifactStore,
    ref: OptimizationAmbiguityCertificateRef,
) -> OptimizationAmbiguityCertificate:
    """Load an ambiguity certificate after owner and profile admission."""
    return _get_owned_json_artifact(
        store,
        ref,
        owner=_OPTIMIZATION_AMBIGUITY_CERTIFICATE_OWNER,
    )


def persist_social_weight_manifest(
    store: ArtifactStore,
    artifact: SocialWeightManifestArtifact,
    *,
    inputs: list[InputRef] | None = None,
    return_selected_profile: bool = False,
) -> SocialWeightManifestRef:
    """Persist a social-weight manifest through its exact typed owner.

    The default retains the historical profileless inspection result. A caller
    carrying the ref as evidence must request the selected profile explicitly.
    """
    return_selected_profile = _validate_return_selected_profile_flag(return_selected_profile)
    ref = _put_owned_json_artifact(
        store,
        artifact.model_dump(mode="json"),
        owner=_SOCIAL_WEIGHT_MANIFEST_OWNER,
        schema_name=_SOCIAL_WEIGHT_MANIFEST_SCHEMA_NAME,
        schema_version=_SOCIAL_WEIGHT_MANIFEST_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = SocialWeightManifestRef.from_selected_write(ref)
    if not return_selected_profile:
        return selected_ref.model_copy(update={"manifest_profile_sha256": None})
    return selected_ref


def load_social_weight_manifest(
    store: ArtifactStore,
    ref: SocialWeightManifestRef,
) -> SocialWeightManifestArtifact:
    """Load a social-weight manifest after owner and profile admission."""
    return _get_owned_json_artifact(store, ref, owner=_SOCIAL_WEIGHT_MANIFEST_OWNER)


def persist_fiscal_feedback_link(
    store: ArtifactStore,
    link: FiscalFeedbackLink,
    *,
    inputs: list[InputRef] | None = None,
) -> FiscalFeedbackLinkRef:
    """Persist a fiscal-feedback link through its exact typed owner."""
    ref = _put_owned_json_artifact(
        store,
        link.model_dump(mode="json"),
        owner=_FISCAL_FEEDBACK_LINK_OWNER,
        schema_name=_FISCAL_FEEDBACK_LINK_SCHEMA_NAME,
        schema_version=_FISCAL_FEEDBACK_LINK_SCHEMA_VERSION,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FiscalFeedbackLinkRef.from_selected_write(ref)


def load_fiscal_feedback_link(
    store: ArtifactStore,
    ref: FiscalFeedbackLinkRef,
) -> FiscalFeedbackLink:
    """Load a fiscal-feedback link after owner and profile admission."""
    return _get_owned_json_artifact(store, ref, owner=_FISCAL_FEEDBACK_LINK_OWNER)


def _mapping_to_json_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> object:
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
