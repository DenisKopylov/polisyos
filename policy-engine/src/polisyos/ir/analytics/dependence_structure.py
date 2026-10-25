"""Shared persisted dependence primitive for Phase 1 consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import ConfigDict, Field

from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from polisyos.ir.artifacts.contracts import ArtifactStore, InputRef
    from polisyos.ir.registry.refs import DependenceStructureRef


class DependenceStructure(KernelModel):
    """Canonical dependence artifact shared across econometrics, SAE, and spatial estimators."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_name: Literal["dependence_structure_v1.json"] = "dependence_structure_v1.json"
    regime: Literal["panel", "areal", "network_adjacent"]
    class_label: str
    calibrated: bool
    recommended_covariance: str
    metrics: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    source_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_dependence_structure(
    *,
    regime: Literal["panel", "areal", "network_adjacent"],
    class_label: str,
    calibrated: bool,
    recommended_covariance: str,
    source_method: str,
    metrics: dict[str, float] | None = None,
    warnings: list[str] | None = None,
    blocking_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DependenceStructure:
    """Build a dependence structure payload directly."""

    return DependenceStructure(
        regime=regime,
        class_label=str(class_label),
        calibrated=bool(calibrated),
        recommended_covariance=str(recommended_covariance),
        metrics=dict(metrics or {}),
        warnings=[str(item).strip() for item in warnings or () if str(item).strip()],
        blocking_reasons=[
            str(item).strip() for item in blocking_reasons or () if str(item).strip()
        ],
        source_method=str(source_method),
        metadata=dict(metadata or {}),
    )


def dependence_structure_from_econometrics(
    diagnostic: object,
    *,
    source_method: str,
) -> DependenceStructure:
    """Normalize an econometrics dependence routing diagnostic into the shared primitive."""

    class_label = _enum_or_string(getattr(diagnostic, "class_label", None), default="inconclusive")
    recommended_covariance = _enum_or_string(
        getattr(diagnostic, "recommended_covariance", None),
        default="none",
    )
    estimator_status = _enum_or_string(
        getattr(diagnostic, "estimator_status", None), default="unsafe"
    )
    regime: Literal["panel", "areal", "network_adjacent"] = "panel"
    if class_label == "network_local":
        regime = "network_adjacent"
    elif class_label == "spatial_local":
        regime = "areal"

    evidence = dict(getattr(diagnostic, "evidence", {}) or {})
    tests = list(getattr(diagnostic, "tests", ()) or ())
    metrics: dict[str, float] = {}
    for key in ("factor_count", "alpha_hat"):
        value = getattr(diagnostic, key, None)
        if value is not None:
            metrics[key] = float(value)
    for key, value in evidence.items():
        if isinstance(value, bool):
            metrics[key] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            metrics[key] = float(value)
    warnings: list[str] = []
    blocking_reasons: list[str] = []
    calibrated = estimator_status in {"ok", "ok_conservative"}
    if estimator_status == "ok_conservative":
        warnings.append("dependence_requires_conservative_inference")
    elif estimator_status in {"reroute_required", "unsafe_for_default_inference"}:
        blocking_reasons.append(f"estimator_status:{estimator_status}")

    metadata = {
        "used_time_dummies": bool(getattr(diagnostic, "used_time_dummies", False)),
        "dependence_removed_by_time_effects": getattr(
            diagnostic, "dependence_removed_by_time_effects", None
        ),
        "shared_artifacts_ref": getattr(diagnostic, "shared_artifacts_ref", None),
        "tests": [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in tests
        ],
    }
    return build_dependence_structure(
        regime=regime,
        class_label=class_label,
        calibrated=calibrated,
        recommended_covariance=recommended_covariance,
        source_method=source_method,
        metrics=metrics,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata=metadata,
    )


def dependence_structure_from_graph_diagnostic(
    diagnostic: object,
    *,
    regime: Literal["areal", "network_adjacent"] = "areal",
    source_method: str,
) -> DependenceStructure:
    """Normalize graph-aware dependence diagnostics emitted by SAE/spatial lanes."""

    payload = (
        diagnostic.model_dump(mode="python")
        if hasattr(diagnostic, "model_dump")
        else dict(cast("Mapping[str, object] | Iterable[tuple[str, object]]", diagnostic))
    )
    decision = str(payload.get("decision", "fallback_independent") or "fallback_independent")
    identifiable = bool(payload.get("identifiable", False))
    class_label = str(payload.get("class_label", "inconclusive") or "inconclusive")
    selected_graph_id = payload.get("selected_graph_id")
    recommended_covariance = "network_hac" if regime == "network_adjacent" else "conley_spatial_hac"
    warnings: list[str] = []
    blocking_reasons: list[str] = []
    if not identifiable:
        blocking_reasons.append(f"decision:{decision}")
    elif decision != "identified":
        warnings.append(f"decision:{decision}")
    metrics: dict[str, float] = {}
    for key in (
        "moran_i",
        "geary_c",
        "moran_p_value",
        "geary_p_value",
        "pesaran_cd",
        "pesaran_cd_p_value",
        "lm_error",
        "lm_error_p_value",
        "lm_lag",
        "lm_lag_p_value",
        "profile_curvature",
        "information_eigen_min",
        "information_condition_number",
    ):
        value = payload.get(key)
        if value is not None:
            metrics[key] = float(value)
    return build_dependence_structure(
        regime=regime,
        class_label=class_label,
        calibrated=identifiable and decision == "identified",
        recommended_covariance=recommended_covariance,
        source_method=source_method,
        metrics=metrics,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
        metadata={
            "selected_graph_id": selected_graph_id,
            "strength": payload.get("strength"),
            "fallback_reason": payload.get("fallback_reason"),
            "graph_diagnostics": payload.get("graph_diagnostics", ()),
        },
    )


_OWNER_SCHEMA_NAME = "ir.dependence_structure"
_OWNER_SCHEMA_VERSION = "1.0"
_OWNER_WIRE_POLICY = ("ir.owner.dependencestructure.wire", "1")


def _owner_payload_version(payload: object) -> str:
    """Require an embedded source version; a DTO default is not historical evidence."""
    if not isinstance(payload, dict):
        raise TypeError("Owned DependenceStructure payload must be a JSON object")
    version = payload.get("schema_version")
    if type(version) is not str or not version.strip():
        raise ValueError("Owned DependenceStructure payload requires an explicit schema_version")
    return version


def _validate_owner_source(
    payload: object, admission: ResolvedSchemaAdmission
) -> DependenceStructure:
    """Validate bytes only under this owner exact registered source representation."""
    registration = admission.source_registration
    if registration.schema_name != _OWNER_SCHEMA_NAME:
        raise ValueError("Owned DependenceStructure source has the wrong schema name")
    if registration.payload_version != _owner_payload_version(payload):
        raise ValueError(
            "Owned DependenceStructure payload version disagrees with its representation"
        )
    return DependenceStructure.model_validate(payload)


def _project_owner_source(
    source: DependenceStructure,
    admission: ResolvedSchemaAdmission,
) -> DependenceStructure:
    """Preserve the validated source value when no semantic projection is declared."""
    if not isinstance(source, DependenceStructure):
        raise TypeError("Owned DependenceStructure source was not validated by its owner")
    if admission.source_registration.payload_version != source.schema_version:
        raise ValueError("Owned DependenceStructure projection would change the source version")
    return source


def _validate_owner_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Accept only the canonical profile used by this family real writer."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_dependencestructure_owner = ArtifactOwnerDeclaration(
    contract_id="ir.analytics.dependence_structure.v1",
    dto_fqn="polisyos.ir.analytics.dependence_structure.DependenceStructure",
    abi_key="ir.dependence_structure",
    registry_key="ir.dependence_structure",
    kind="ir.dependence_structure",
    media_type="application/json",
    purpose="ir.dependence_structure.typed_consumer",
    policy_revision="ir.analytics.dependence_structure.v1.owner-admission.v1",
    accepted_wire_policies=(_OWNER_WIRE_POLICY,),
    payload_version_of=_owner_payload_version,
    validate_source=_validate_owner_source,
    project_for_consumer=_project_owner_source,
    validate_profile=_validate_owner_profile,
)


register_schema_version(
    _OWNER_SCHEMA_NAME,
    _OWNER_SCHEMA_VERSION,
    compatibility=CompatibilityMode.NONE,
    notes=(
        "DependenceStructure current owner-admitted representation; historical predecessors are not registered.",
    ),
)
register_ir_representation(
    registry_key=_dependencestructure_owner.registry_key,
    owner_ref=_dependencestructure_owner.contract_id,
    dto_abi=_dependencestructure_owner.dto_fqn,
    wire_policy_ref=_OWNER_WIRE_POLICY[0],
    wire_policy_revision=_OWNER_WIRE_POLICY[1],
    schema_name=_OWNER_SCHEMA_NAME,
    schema_version=_OWNER_SCHEMA_VERSION,
    payload_version=_OWNER_SCHEMA_VERSION,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
)


def persist_dependence_structure(
    store: ArtifactStore,
    report: DependenceStructure,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dependence_structure",
    schema_version: str = "1.0",
) -> DependenceStructureRef:
    """Persist a source-validated DependenceStructure under its exact owned representation."""
    selected = _put_owned_json_artifact(
        store,
        report.model_dump(mode="json"),
        owner=_dependencestructure_owner,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    from polisyos.ir.registry.refs import DependenceStructureRef

    return DependenceStructureRef.model_validate(selected)


def load_dependence_structure(
    store: ArtifactStore, ref: DependenceStructureRef
) -> DependenceStructure:
    """Read DependenceStructure only after its trusted owner admits the stored representation."""
    return _get_owned_json_artifact(store, ref, owner=_dependencestructure_owner)


def _enum_or_string(value: object, *, default: str) -> str:
    if value is None:
        return default
    resolved = getattr(value, "value", value)
    text = str(resolved).strip()
    return text or default


__all__ = [
    "DependenceStructure",
    "build_dependence_structure",
    "dependence_structure_from_econometrics",
    "dependence_structure_from_graph_diagnostic",
    "load_dependence_structure",
    "persist_dependence_structure",
]
