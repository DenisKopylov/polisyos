"""Small contracts and helpers for the runtime control-plane service."""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Literal, Protocol, cast, get_args

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import DataSnapshotRef, DataViewRequestRef
from polisyos.core.contracts.control import (
    ControlJobKind,
    DataSourceBinding,
    ExecutionProfile,
    RetrievalMode,
    WorkflowDataSourceBinding,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver

_CONTROL_JOB_KINDS = frozenset(get_args(ControlJobKind))
_RETRIEVAL_MODES = frozenset({"fastlane", "explorelane", "hybrid"})
_WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY = "data_view_request_intent"


class WorkflowDataViewRequestIntent(BaseModel):
    """Immutable server-recorded origin of a workflow data-view selector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.workflow_data_view_request_intent.v1"] = (
        "polisyos.runtime.workflow_data_view_request_intent.v1"
    )
    profile_origin: Literal["caller_selected", "worker_default"]


class _MethodCatalogSnapshotAware(Protocol):
    def set_method_catalog_snapshot(self, payload: dict[str, Any] | None) -> None: ...


def _coerce_control_job_kind(value: str) -> ControlJobKind:
    normalized = value.strip()
    if normalized not in _CONTROL_JOB_KINDS:
        raise ValueError(f"Unsupported control job kind: {normalized!r}")
    return cast("ControlJobKind", normalized)


def _build_api_meta(request_id: str | None = None) -> ApiMeta:
    return ApiMeta(request_id=request_id or uuid.uuid4().hex)


def _make_artifact_ref(
    ref_str: str,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef:
    """Lazily import ArtifactRef and ArtifactID to avoid heavy startup cost."""
    from polisyos.core.artifacts.ids import ArtifactID

    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(ref_str),
        kind=kind,
        media_type=media_type,
    )


def _typed_artifact_ref[ArtifactRefModelT: BaseModel](
    ref_str: str,
    *,
    kind: str,
    ref_type: type[ArtifactRefModelT],
    media_type: str = "application/json",
) -> ArtifactRefModelT:
    return ref_type.model_validate(
        _make_artifact_ref(ref_str, kind=kind, media_type=media_type).model_dump(mode="json")
    )


def _artifact_ref_from_summary_payload(
    payload: object,
    *,
    kind: str,
    media_type: str = "application/json",
) -> ArtifactRef | None:
    if not isinstance(payload, dict):
        return None
    artifact_id = payload.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    return _make_artifact_ref(artifact_id, kind=kind, media_type=media_type)


_DATA_SOURCE_KEYS = {
    "data_snapshot_ref": "fabric.data_snapshot",
    "input_bindings_ref": "foundry.input_bindings",
    "data_view_request_ref": "ir.data_view_request",
}

_OPTIONAL_INPUT_KEYS = {
    "trinity_bundle_ref": "ir.trinity_bundle",
    "registry_bundle_ref": "core.registry_bundle",
    "policy_spec_ref": "ir.policy_spec",
    "model_spec_ref": "ir.model_spec",
    "research_intent_ref": "scholar.research_intent",
    "knowledge_bundle_ref": "scholar.knowledge_bundle",
    "norm_pack_ref": "lex.norm_pack",
    "calibration_report_ref": "foundry.calibration_report",
    "production_case_intake_ref": "gy.loop.proof.root",
}


def _resolve_data_source(binding: DataSourceBinding) -> tuple[str, str | DataSnapshotRef]:
    """Return the selected source while retaining a typed snapshot view."""
    for field_name, _kind in _DATA_SOURCE_KEYS.items():
        value = getattr(binding, field_name, None)
        if value:
            return field_name, value
    raise ValueError(
        "At least one data source must be provided: "
        "data_snapshot_ref, input_bindings_ref, or data_view_request_ref"
    )


def _resolve_workflow_data_source(
    binding: WorkflowDataSourceBinding,
) -> tuple[str, ArtifactRef, WorkflowDataViewRequestIntent | None]:
    """Preserve the exact typed request through workflow job creation."""
    if binding.data_snapshot_ref is not None:
        reference = binding.data_snapshot_ref
        return (
            "data_snapshot_ref",
            reference
            if isinstance(reference, DataSnapshotRef)
            else _make_artifact_ref(
                reference,
                kind=_DATA_SOURCE_KEYS["data_snapshot_ref"],
            ),
            None,
        )
    if binding.input_bindings_ref is not None:
        return (
            "input_bindings_ref",
            _make_artifact_ref(
                binding.input_bindings_ref,
                kind=_DATA_SOURCE_KEYS["input_bindings_ref"],
            ),
            None,
        )
    value = binding.data_view_request_ref
    if isinstance(value, DataViewRequestRef):
        request_ref = ArtifactRef.model_validate(value.model_dump(mode="python"))
    elif isinstance(value, str):
        request_ref = _typed_artifact_ref(
            value,
            kind=_DATA_SOURCE_KEYS["data_view_request_ref"],
            ref_type=DataViewRequestRef,
        )
    else:
        raise ValueError("workflow_data_source_must_select_exactly_one")
    if request_ref.kind != "ir.data_view_request" or request_ref.media_type != "application/json":
        raise ValueError("workflow_data_view_request_ref_kind_or_media_type_invalid")
    intent = WorkflowDataViewRequestIntent(
        profile_origin=(
            "caller_selected"
            if request_ref.manifest_profile_sha256 is not None
            else "worker_default"
        )
    )
    return "data_view_request_ref", request_ref, intent


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_retrieval_mode(value: str) -> RetrievalMode:
    normalized = value.strip().lower()
    if normalized not in _RETRIEVAL_MODES:
        raise ValueError(f"Unsupported retrieval mode: {value!r}")
    return cast("RetrievalMode", normalized)


def _coerce_optional_execution_profile(value: str | None) -> ExecutionProfile | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    supported_profiles = RuntimeExecutionPolicyResolver.supported_profiles()
    if normalized not in supported_profiles:
        raise ValueError(f"Unsupported execution profile: {value!r}")
    return cast("ExecutionProfile", normalized)


def _is_multimodel_enabled() -> bool:
    return _as_bool(
        os.getenv("POLISYOS_LLM_MULTIMODEL_ENABLED"),
        default=True,
    )


def _is_required_preflight_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_REQUIRED_PREFLIGHT_ENABLED"), default=True)


def _is_auto_materialization_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_AUTO_MATERIALIZATION_ENABLED"), default=True)


def _is_unified_dag_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_UNIFIED_DAG_ENABLED"), default=True)


def _is_scientist_v2_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_V2_ENABLED"), default=False)


def _is_scientist_shadow_mode() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_SHADOW_MODE"), default=False)


def _is_scientist_web_search_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_WEB_SEARCH_ENABLED"), default=False)


def _is_scientist_swarm_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_SWARM_ENABLED"), default=False)


def _is_scientist_reflexion_enabled() -> bool:
    return _as_bool(os.getenv("POLISYOS_SCIENTIST_REFLEXION_ENABLED"), default=False)


def _normalize_model_variant_id(model_name: str, index: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", model_name.strip().lower()).strip("_")
    if not base:
        base = "model"
    return f"{base}_{index + 1}"


def _dedupe_models(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _now_ms() -> int:
    return int(time.time() * 1000)


__all__ = [
    "_DATA_SOURCE_KEYS",
    "_OPTIONAL_INPUT_KEYS",
    "_WORKFLOW_DATA_VIEW_REQUEST_INTENT_KEY",
    "WorkflowDataViewRequestIntent",
    "_MethodCatalogSnapshotAware",
    "_artifact_ref_from_summary_payload",
    "_as_bool",
    "_build_api_meta",
    "_coerce_control_job_kind",
    "_coerce_optional_execution_profile",
    "_coerce_retrieval_mode",
    "_dedupe_models",
    "_is_auto_materialization_enabled",
    "_is_multimodel_enabled",
    "_is_required_preflight_enabled",
    "_is_scientist_reflexion_enabled",
    "_is_scientist_shadow_mode",
    "_is_scientist_swarm_enabled",
    "_is_scientist_v2_enabled",
    "_is_scientist_web_search_enabled",
    "_is_unified_dag_enabled",
    "_make_artifact_ref",
    "_normalize_model_variant_id",
    "_now_ms",
    "_resolve_data_source",
    "_resolve_workflow_data_source",
    "_typed_artifact_ref",
]
