"""Control-plane capability manifest surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core.contracts.control import CapabilityManifestResponse, PolicyFlags
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.runtime.http.services.control.production_data import (
    production_data_evidence_context,
)

from .._control_contracts import (
    _build_api_meta,
    _is_auto_materialization_enabled,
    _is_multimodel_enabled,
    _is_required_preflight_enabled,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver


class CapabilityManifestMixin:
    """Capability-manifest endpoint behavior for the control-plane service."""

    _policy_resolver: RuntimeExecutionPolicyResolver

    def get_capabilities(self, *, request_id: str | None = None) -> CapabilityManifestResponse:
        """Return platform posture without author-authored feature claims."""
        causal_contract = build_causal_capability_contract()
        production_data_context = production_data_evidence_context(None, allow_default=True)
        resolved_policy = self._policy_resolver.resolve(
            requested_profile=None,
            policy_flags=PolicyFlags(),
            principal=None,
        )

        execution_policy = {
            "auto_materialization": _is_auto_materialization_enabled(),
            "multimodel_nl": _is_multimodel_enabled(),
            "producer_ref": "runtime/http/services/_control_contracts.py",
            "required_preflight": _is_required_preflight_enabled(),
        }

        return CapabilityManifestResponse(
            meta=_build_api_meta(request_id),
            default_execution_profile=self._policy_resolver.default_profile,
            supported_execution_profiles=list(self._policy_resolver.supported_profiles()),
            worker_backend=self._policy_resolver.worker_backend,
            state_store_backend=self._policy_resolver.state_store_backend,
            security_posture=dict(resolved_policy.security_posture),
            fallback_rules={
                **dict(resolved_policy.fallback_rules),
                "execution_policy": execution_policy,
            },
            workspaces=[],
            features=[],
            constraints={
                "max_parallel_models": 16,
                "max_nl_iterations": 10,
                "artifact_preview_max_bytes": 2_000_000,
                "task_runner": "durable_control_worker",
                "default_locale": "en",
                "supported_locales": ["en", "uk"],
                "durable_control_profiles": ["research", "governed", "production"],
                "local_control_plane_waiver_active": bool(
                    resolved_policy.fallback_rules.get("local_control_plane_waiver_active")
                ),
                "causal_runtime": causal_contract.model_dump(mode="json"),
                **(
                    {"production_data": production_data_context}
                    if production_data_context is not None
                    else {}
                ),
            },
        )
