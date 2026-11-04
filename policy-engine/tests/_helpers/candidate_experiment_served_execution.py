"""Compose the real test-owned WDI execution port for served experiments."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionCandidateSourceRoute,
        AcquisitionWorldGrowthBridge,
    )


@dataclass(frozen=True)
class CandidateExperimentServedExecutionOwner:
    """Actual fixture-owned execution owners and controlled WDI calls."""

    bridge: AcquisitionWorldGrowthBridge
    port: WorldBankWDIAcquisitionExecutionPort
    selection: AcquisitionCandidateSourceRoute
    transport_calls: list[tuple[str, str, dict[str, str]]]


@contextmanager
def candidate_experiment_served_execution_owner(
    *,
    action_service: AcquisitionActionService,
    origin: VerifiedCandidateExperimentOrigin,
    policy_owner: object,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[CandidateExperimentServedExecutionOwner]:
    """Install a real WDI port and exact source route for one served experiment.

    The WDI authority, registry, provision, source profile, and candidate policy
    template come from the same test-owned policy issuer. The bridge binds to the
    existing Control, CAS, event, and action-head owners. The supported fixture
    transport supplies a declared synthetic WDI response and rejects external
    network access; this helper does not run N5.
    """
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService as AcquisitionActionServiceType,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService as ControlPlaneServiceType,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin as VerifiedCandidateExperimentOriginType,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
    )
    from tests._helpers.lane01_candidate_action_served import _transport

    if type(action_service) is not AcquisitionActionServiceType:
        raise TypeError("candidate_experiment_test_action_service_untyped")
    control = action_service.control_service
    if type(control) is not ControlPlaneServiceType:
        raise TypeError("candidate_experiment_test_control_service_untyped")
    if type(origin) is not VerifiedCandidateExperimentOriginType:
        raise TypeError("candidate_experiment_test_origin_untyped")

    issuer = getattr(policy_owner, "issuer", None)
    template = getattr(policy_owner, "template", None)
    source_profiles = getattr(policy_owner, "source_profiles", None)
    if issuer is None or template is None or source_profiles is None:
        raise TypeError("candidate_experiment_test_policy_owner_incomplete")
    authority = getattr(issuer, "authority", None)
    registry = getattr(issuer, "registry", None)
    issuer_port = getattr(issuer, "port", None)
    if (
        authority is None
        or registry is None
        or type(issuer_port) is not WorldBankWDIAcquisitionExecutionPort
        or issuer_port._authority is not authority
        or issuer_port._registry != registry
        or issuer_port._provision != authority.provision
        or issuer_port._artifact_store is not control._artifact_store
        or issuer_port._executor is not None
        or template.authority_registry_sha256 != registry.content_sha256
        or template.authority_provision_sha256 != authority.provision_content_sha256
    ):
        raise TypeError("candidate_experiment_test_wdi_issuer_owner_mismatch")

    providers = control._registry_providers
    if (
        providers.source_profiles is not source_profiles
        or template not in providers.candidate_unpriced_policy_templates
        or providers.candidate_unpriced_policy_bindings
    ):
        raise ValueError("candidate_experiment_test_policy_owner_not_current")

    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(candidate_source_routes=()),
        repo_root=Path(authority.repo_root),
        runtime_root=Path(control._cas_root),
        authority=authority,
        artifact_store=control._artifact_store,
        event_log=control._diagnostic_event_log,
        epoch_deployment=None,
        promotion_runtime=control._promotion_runtime,
        cycle_substrate_context_admission_owner=(control._cycle_substrate_context_admission_owner),
        control_store=control._control_store,
        action_head_sink=control.acquisition_route_sink,
        source_control_service=control,
    )
    port = WorldBankWDIAcquisitionExecutionPort(
        world_growth_bridge=bridge,
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=Path(control._cas_root),
        artifact_store=control._artifact_store,
    )
    previous_execution_port = action_service._execution_port
    previous_production_port = action_service._production_execution_port

    with monkeypatch.context() as scoped:

        def build_current_test_port(*, control_service: ControlPlaneService):
            if control_service is not control:
                raise AssertionError("candidate experiment reopened a different Control owner")
            return port

        scoped.setattr(
            acquisition_surface_execution,
            "build_production_world_bank_wdi_execution_port",
            build_current_test_port,
        )
        transport_calls = _transport(scoped)
        try:
            action_service._execution_port = port
            action_service._production_execution_port = port
            from polisyos.runtime.quality.candidate_acquisition_action import (
                _candidate_experiment_source_selection,
            )

            selection = _candidate_experiment_source_selection(bridge, origin)
            if (
                selection.tenant_id != origin.tenant_id
                or selection.cell_id != origin.cell_id
                or selection.run_id != origin.run_id
                or selection.route_id != origin.route_id
                or selection.candidate_digest != origin.policy_scope.candidate_digest
            ):
                raise ValueError("candidate_experiment_test_selection_scope_mismatch")
            bridge.config = AcquisitionWorldGrowthConfig(candidate_source_routes=(selection,))
            yield CandidateExperimentServedExecutionOwner(
                bridge=bridge,
                port=port,
                selection=selection,
                transport_calls=transport_calls,
            )
        finally:
            action_service._execution_port = previous_execution_port
            action_service._production_execution_port = previous_production_port
