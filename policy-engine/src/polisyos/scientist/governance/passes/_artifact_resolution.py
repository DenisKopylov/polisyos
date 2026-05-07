"""Shared artifact/model resolution helpers for governance passes."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

T = TypeVar("T", bound=BaseModel)
module_logger = get_logger(__name__)

_RESOLUTION_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


@dataclass(frozen=True)
class ArtifactResolution(Generic[T]):
    """Typed optional artifact resolution result for governance passes."""

    value: T | None
    issues: list[ComplianceIssue]


def resolve_optional_artifact_model(
    *,
    ctx: PassContext,
    pass_id: str,
    direct_key: str,
    ref_key: str,
    model_cls: type[T],
    ref_model: type[BaseModel] | None,
    load_model: Callable[[Any, Any], T],
    severity: IssueSeverity,
    code: str,
    message: str,
    suggestion: str,
    log: Any,
) -> ArtifactResolution[T]:
    """Resolve an optional governance artifact from state or CAS with typed failures."""

    direct = ctx.state.get(direct_key)
    if isinstance(direct, model_cls):
        return ArtifactResolution(value=direct, issues=[])
    if isinstance(direct, dict):
        try:
            return ArtifactResolution(value=model_cls.model_validate(direct), issues=[])
        except _RESOLUTION_ERRORS as exc:
            return ArtifactResolution(
                value=None,
                issues=[
                    _build_resolution_issue(
                        pass_id=pass_id,
                        path=[direct_key],
                        code=code,
                        message=message,
                        suggestion=suggestion,
                        severity=severity,
                        log=log,
                        operation=f"resolve_{direct_key}_direct",
                        exc=exc,
                        details={"run_id": ctx.run_id, "source": "state"},
                    )
                ],
            )

    artifacts_index = ctx.state.get("artifacts_index")
    if not isinstance(artifacts_index, dict):
        return ArtifactResolution(value=None, issues=[])
    raw_ref = artifacts_index.get(ref_key)
    if raw_ref is None:
        return ArtifactResolution(value=None, issues=[])
    store = ctx.state.get("_store")
    if store is None:
        return ArtifactResolution(value=None, issues=[])

    try:
        normalized_ref = _normalize_ref(raw_ref=raw_ref, ref_model=ref_model)
        return ArtifactResolution(value=load_model(store, normalized_ref), issues=[])
    except _RESOLUTION_ERRORS as exc:
        return ArtifactResolution(
            value=None,
            issues=[
                _build_resolution_issue(
                    pass_id=pass_id,
                    path=["artifacts_index", ref_key],
                    code=code,
                    message=message,
                    suggestion=suggestion,
                    severity=severity,
                    log=log,
                    operation=f"resolve_{direct_key}_artifact",
                    exc=exc,
                    details={"run_id": ctx.run_id, "source": "artifact_ref"},
                )
            ],
        )


def _normalize_ref(
    *,
    raw_ref: Any,
    ref_model: type[BaseModel] | None,
) -> Any:
    if ref_model is None:
        return raw_ref
    if isinstance(raw_ref, ref_model):
        return raw_ref
    if hasattr(raw_ref, "model_dump"):
        payload = raw_ref.model_dump(mode="json")
    elif hasattr(raw_ref, "artifact_id"):
        payload = {"artifact_id": raw_ref.artifact_id}
        if hasattr(raw_ref, "kind"):
            payload["kind"] = raw_ref.kind
        if hasattr(raw_ref, "media_type"):
            payload["media_type"] = raw_ref.media_type
    else:
        payload = raw_ref
    return ref_model.model_validate(payload)


def _build_resolution_issue(
    *,
    pass_id: str,
    path: list[str | int],
    code: str,
    message: str,
    suggestion: str,
    severity: IssueSeverity,
    log: Any,
    operation: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> ComplianceIssue:
    envelope = emit_degraded_path(
        component="governance.pass_artifact_resolution",
        operation=operation,
        reason="artifact_resolution_failed",
        exc=exc,
        details=details,
        log=log or module_logger,
    )
    return ComplianceIssue(
        pass_id=pass_id,
        path=path,
        message=message,
        severity=severity,
        code=code,
        suggestion=suggestion,
        input_value=json.dumps(envelope, sort_keys=True, default=str),
    )


__all__ = ["ArtifactResolution", "resolve_optional_artifact_model"]
