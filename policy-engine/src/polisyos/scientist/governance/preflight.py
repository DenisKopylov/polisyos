"""Public governance preflight module API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.ir.governance.gate import GateContext, GateRequest
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.error_semantics import emit_degraded_path

from .pass_registry import build_governance_pipeline

logger = get_logger(__name__)
_PREFLIGHT_LOAD_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore

    from .pipeline import ValidationPipeline


def build_default_pipeline() -> ValidationPipeline:
    """Build default pipeline."""
    return cast("ValidationPipeline", build_governance_pipeline())


DEFAULT_PIPELINE = build_default_pipeline()


def _build_store(cas_root: Path) -> ArtifactStore:
    return cast(
        "ArtifactStore",
        build_artifact_store(ArtifactStoreConfig(root=str(cas_root))),
    )


def preflight_checks(
    state: dict[str, Any],
    profile: ValidationProfile | None = None,
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> tuple[dict[str, Any], GateRequest | None]:
    """
    Pre-flight governance with configurable validation profile.

    Returns:
        tuple: (updated_state, gate_request)
            - updated_state: State with validation_trace attached
            - gate_request: None if validation passed, GateRequest if blockers found
    """

    profile = profile or ValidationProfile.mvp()
    run_id = state.get("run_id", "unknown")

    updated_state = state
    registry_bundle = None
    trinity_bundle = _extract_trinity_bundle(updated_state)

    if "safety" in profile.pass_ids:
        updated_state = _ensure_registry_bundle(updated_state, store_factory=store_factory)
        registry_bundle = _load_registry_bundle(
            updated_state,
            trinity_bundle,
            store_factory=store_factory,
        )
        updated_state = _ensure_policy_registry_ref(updated_state)
        trinity_bundle = _extract_trinity_bundle(updated_state)

    ctx = PassContext(
        ir=trinity_bundle,
        state=updated_state,
        registry_bundle=registry_bundle,
        profile=profile,
        run_id=run_id,
    )

    issues, trace = DEFAULT_PIPELINE.validate(ctx, profile)

    issue_payload = [issue.to_dict() for issue in issues]
    updated_state = {
        **updated_state,
        "validation_trace": trace.to_dict(),
        "validation_issues": issue_payload,
    }

    blockers = [issue for issue in issues if issue.severity == IssueSeverity.BLOCKER]

    if blockers:
        blocker_payload = [issue.to_dict() for issue in blockers]
        updated_state["validation_blockers"] = blocker_payload
        gate_request = GateRequest(
            schema_version="1.1",
            request_id=f"gov-preflight-{run_id}",
            run_id=run_id,
            reason=f"Validation failed: {len(blockers)} blocker(s) found",
            context=GateContext(
                workflow_id="scientist_governance",
                node_alias="governance.preflight",
                phase="PREFLIGHT_GOV",
                iteration=1,
                governance_profile=profile.level.value,
                risk_indicators=sorted(
                    {
                        str(issue.code or issue.pass_id)
                        for issue in blockers
                        if (issue.code or issue.pass_id)
                    }
                ),
            ),
        )
        return updated_state, gate_request

    if issues:
        updated_state["validation_warnings"] = issue_payload

    return updated_state, None


def _runtime_base_dir(state: dict[str, Any]) -> Path:
    runtime_base_dir = state.get("runtime_base_dir")
    return Path(runtime_base_dir) if runtime_base_dir else Path("runs")


def _cas_root(state: dict[str, Any]) -> Path:
    if state.get("cas_root"):
        return Path(state["cas_root"])
    runtime_base = _runtime_base_dir(state)
    return runtime_base.parent / ".polisyos"


def _ensure_registry_bundle(
    state: dict[str, Any],
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> dict[str, Any]:
    if state.get("registry_bundle_ref"):
        return state
    store = (store_factory or _build_store)(_cas_root(state))
    bundle = build_default_registry_bundle(store)
    return {
        **state,
        "registry_bundle_ref": bundle.bundle_ref.model_dump(),
        "cas_root": str(_cas_root(state)),
    }


def _resolve_registry_bundle_id(
    state: dict[str, Any],
    policy: TrinityBundle | None,
) -> str | None:
    if policy is not None and policy.model_spec.registry_bundle_ref:
        return str(policy.model_spec.registry_bundle_ref)
    bundle_ref = state.get("registry_bundle_ref")
    if isinstance(bundle_ref, dict):
        artifact_id = bundle_ref.get("artifact_id")
        if isinstance(artifact_id, str):
            return artifact_id
    return None


def _load_registry_bundle(
    state: dict[str, Any],
    policy: TrinityBundle | None,
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> object | None:
    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        return None
    try:
        store = (store_factory or _build_store)(_cas_root(state))
        return cast("object", load_registry_bundle_content(store, bundle_id))
    except _PREFLIGHT_LOAD_ERRORS as exc:
        emit_degraded_path(
            component="scientist.governance_preflight",
            operation="load_registry_bundle",
            reason="registry_bundle_unreadable",
            exc=exc,
            details={
                "bundle_id": bundle_id,
                "run_id": str(state.get("run_id") or "unknown"),
            },
            log=logger,
        )
        return None


def _ensure_policy_registry_ref(state: dict[str, Any]) -> dict[str, Any]:
    policy = _extract_trinity_bundle(state)
    if policy is None:
        return state

    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        return state

    if policy.model_spec.registry_bundle_ref is None:
        updated_policy = policy.model_copy(
            update={
                "model_spec": policy.model_spec.model_copy(
                    update={"registry_bundle_ref": bundle_id}
                )
            }
        )
        return _update_state_bundle(state, updated_policy)

    return state


def _extract_trinity_bundle(state: dict[str, Any]) -> TrinityBundle | None:
    value = state.get("trinity_bundle", state.get("ir"))
    if value is None:
        return None
    if isinstance(value, TrinityBundle):
        return value
    if isinstance(value, dict):
        try:
            return TrinityBundle.model_validate(value)
        except _PREFLIGHT_LOAD_ERRORS as exc:
            emit_degraded_path(
                component="scientist.governance_preflight",
                operation="extract_trinity_bundle",
                reason="invalid_trinity_bundle",
                exc=exc,
                details={"run_id": str(state.get("run_id") or "unknown")},
                log=logger,
            )
            return None
    return None


def _update_state_bundle(
    state: dict[str, Any],
    bundle: TrinityBundle,
) -> dict[str, Any]:
    if "trinity_bundle" in state:
        return {**state, "trinity_bundle": bundle}
    if "ir" in state:
        return {**state, "ir": bundle}
    return {**state, "trinity_bundle": bundle}
