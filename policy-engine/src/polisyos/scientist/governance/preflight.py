from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.runtime import log_artifact
from polisyos.scientist.kernel.human_gate import GateRequest

from .pipeline import ValidationPipeline
from .profiles import ValidationProfile
from .passes.base import PassContext, IssueSeverity
from .passes.schema_pass import SchemaPass
from .passes.safety_pass import SafetyPass
from .passes.privacy_pass import PrivacyPass
from .passes.budget_pass import BudgetPass
from .passes.legal_pass import LegalPass
from .passes.quality_gate_pass import QualityGatePass
from .legal.backends.stub import StubBackend


DEFAULT_PIPELINE = ValidationPipeline([
    BudgetPass(),
    SchemaPass(),
    PrivacyPass(),
    SafetyPass(),
    LegalPass(backend=StubBackend()),
    QualityGatePass(),
])


def preflight_checks(
    state: dict,
    profile: Optional[ValidationProfile] = None,
) -> Tuple[dict, Optional[GateRequest]]:
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

    if "safety" in profile.pass_ids:
        updated_state = _ensure_registry_bundle(updated_state)
        registry_bundle = _load_registry_bundle(updated_state, updated_state.get("ir"))
        updated_state = _ensure_policy_registry_ref(updated_state)

    ctx = PassContext(
        ir=updated_state.get("ir"),
        state=updated_state,
        registry_bundle=registry_bundle,
        profile=profile,
        run_id=run_id,
    )

    issues, trace = DEFAULT_PIPELINE.validate(ctx, profile)

    updated_state = {**updated_state, "validation_trace": trace.to_dict()}

    blockers = [issue for issue in issues if issue.severity == IssueSeverity.BLOCKER]

    if blockers:
        gate_request = GateRequest(
            run_id=run_id,
            reason=f"Validation failed: {len(blockers)} blocker(s) found",
            details={
                "issues": [issue.to_dict() for issue in issues],
                "profile": profile.level.value,
                "short_circuited": trace.short_circuited,
            },
        )
        return updated_state, gate_request

    if issues:
        updated_state["validation_warnings"] = [issue.to_dict() for issue in issues]

    return updated_state, None


def _runtime_base_dir(state: dict) -> Path:
    runtime_base_dir = state.get("runtime_base_dir")
    return Path(runtime_base_dir) if runtime_base_dir else Path("runs")


def _cas_root(state: dict) -> Path:
    if state.get("cas_root"):
        return Path(state["cas_root"])
    runtime_base = _runtime_base_dir(state)
    return runtime_base.parent / ".polisyos"


def _ensure_registry_bundle(state: dict) -> dict:
    if state.get("registry_bundle_ref"):
        return state
    store = FileSystemCAS(_cas_root(state))
    bundle = build_default_registry_bundle(store)
    run_id = state.get("run_id")
    if run_id:
        log_artifact(
            run_id=run_id,
            artifact_type="registry_bundle_ref",
            payload=bundle.bundle_ref.model_dump(),
            media_type="application/json",
            step="runtime",
            base_dir=_runtime_base_dir(state),
        )
    return {
        **state,
        "registry_bundle_ref": bundle.bundle_ref.model_dump(),
        "cas_root": str(_cas_root(state)),
    }


def _resolve_registry_bundle_id(state: dict, policy) -> str | None:
    if policy and getattr(policy, "semantic", None) and policy.semantic.registry_bundle_ref:
        return policy.semantic.registry_bundle_ref
    bundle_ref = state.get("registry_bundle_ref")
    if isinstance(bundle_ref, dict):
        return bundle_ref.get("artifact_id")
    return None


def _load_registry_bundle(state: dict, policy) -> object | None:
    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        return None
    try:
        store = FileSystemCAS(_cas_root(state))
        return load_registry_bundle_content(store, bundle_id)
    except Exception:
        return None


def _ensure_policy_registry_ref(state: dict) -> dict:
    policy = state.get("ir")
    if not policy or not getattr(policy, "semantic", None):
        return state

    bundle_id = _resolve_registry_bundle_id(state, policy)
    if not bundle_id:
        return state

    if policy.semantic.registry_bundle_ref is None:
        updated_policy = policy.model_copy(
            update={
                "semantic": policy.semantic.model_copy(
                    update={"registry_bundle_ref": bundle_id}
                )
            }
        )
        return {**state, "ir": updated_policy}

    return state
