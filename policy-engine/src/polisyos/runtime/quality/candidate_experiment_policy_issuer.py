"""Prepare candidate experiment policies from completed, independently owned inputs.

This producer selects no action and performs no HTTP call, quota allocation,
USD reservation or publication. Its policy remains subject to the live action,
source, lease and budget owners at every subsequent effect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.core import artifacts
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
    _persist_owned_candidate_unpriced_policy,
    issue_candidate_unpriced_experiment_policy,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import _VerifiedAcquisitionOrigin
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedAcquisitionPolicy,
        CandidateUnpricedExperimentPolicyTemplate,
    )
    from polisyos.scientist.orchestration.engine import BudgetLedgerInvocationProfile


def _source_scope(
    *,
    service: ControlPlaneService,
    origin: _VerifiedAcquisitionOrigin,
    port: WorldBankWDIAcquisitionExecutionPort,
    entry_id: str,
    variable_id: str,
    country_code: str,
    year: int,
) -> CandidateUnpricedPolicyScope:
    """Join the exact compiler-selected spec and source descriptor, not an N4 digest."""
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
    from polisyos.runtime.quality.candidate_acquisition_source import (
        validate_candidate_acquisition_selection,
    )

    report = origin.report
    basis, lineage = report.requirement_basis_binding, report.candidate_lineage
    source = origin.configured_port_source
    planner_ref = origin.source_cycle.acquisition_routing_report_ref
    if basis is None or lineage is None or source is None or planner_ref is None:
        raise ValueError("candidate_experiment_issuer_source_incomplete")
    compilation = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(service._artifact_store, basis.compiler_report_ref)
    )
    specs = tuple(
        spec
        for spec in compilation.specs
        if spec.requirement_id == origin.planner_record.compiled_requirement_ref
    )
    if len(specs) != 1:
        raise ValueError("candidate_experiment_issuer_spec_not_unique")
    spec = specs[0]
    selected: list[tuple[str, str]] = []
    for resolution in compilation.capability_requirement_resolutions or ():
        discovery = resolution.candidate_discovery
        if discovery is None:
            continue
        for candidate in discovery.candidates:
            try:
                validate_candidate_acquisition_selection(
                    service._artifact_store,
                    requirement_basis_binding=basis,
                    compiled_requirement_ref=spec.requirement_id,
                    requirement_id=resolution.query.requirement_id,
                    candidate_digest=candidate.content_digest,
                    authority=port._authority,
                    entry_id=entry_id,
                    target_slot_id=variable_id,
                    country_code=country_code,
                    year=year,
                    population=spec.scope.population,
                )
            except ValueError as exc:
                from polisyos.common.canonical_profile import CanonicalProfileRefusalError
                from polisyos.core.artifacts import raise_artifact_read_access_error

                raise_artifact_read_access_error(exc)
                if isinstance(exc, CanonicalProfileRefusalError):
                    raise
                continue
            selected.append((resolution.query.requirement_id, candidate.content_digest))
    if len(selected) != 1:
        raise ValueError("candidate_experiment_issuer_descriptor_not_unique")
    requirement_id, candidate_digest = selected[0]
    return CandidateUnpricedPolicyScope(
        tenant_id=source.tenant_id,
        cell_id=source.cell_id,
        run_id=origin.job.run_id,
        source_job_id=origin.job.job_id,
        design_problem_ref=origin.compiled.design_problem_ref,
        design_problem_basis_ref=source.design_problem_basis_ref,
        source_cycle_index=origin.source_cycle.cycle_index,
        candidate_id=origin.source_cycle.selected_candidate_ref,
        candidate_content_hash=origin.source_cycle.selected_candidate_content_hash,
        requirement_id=requirement_id,
        compiled_requirement_ref=spec.requirement_id,
        candidate_digest=candidate_digest,
        planner_report_hash=agent_action_content_hash(report),
        compiled_ref=origin.selected_compiled_ref,
        planner_report_ref=planner_ref,
        compiler_report_ref=basis.compiler_report_ref,
        configured_port_source_ref=lineage.port_source_ref,
    )


def _prepare_policy(
    *,
    service: ControlPlaneService,
    origin: _VerifiedAcquisitionOrigin,
    port: WorldBankWDIAcquisitionExecutionPort,
    template: CandidateUnpricedExperimentPolicyTemplate,
    quota: BudgetLedgerInvocationProfile,
    source_payload_ref: str,
    request_content_hash: str,
    original_metered_budget_usd: Decimal,
) -> CandidateUnpricedAcquisitionPolicy:
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        _resolve_world_bank_wdi_source_attempts,
    )
    from polisyos.runtime.quality.acquisition_executor import (
        LiveCatalogExecutionConstraints,
        _prepare_live_catalog_authorization,
    )

    if (
        template.authority_registry_sha256 != port._registry.content_sha256
        or template.authority_provision_sha256 != port._provision_content_sha256
    ):
        raise ValueError("candidate_experiment_issuer_authority_identity_mismatch")
    variable, entry_id, constraints, attempts = _resolve_world_bank_wdi_source_attempts(
        source=origin,
        authority=port._authority,
        registry=port._registry,
        provision=port._provision,
        provision_content_sha256=port._provision_content_sha256,
    )
    selected_attempt_ids = (template.attempt_id, *template.subsequent_attempt_ids)
    provisioned_attempt_ids = tuple(attempt.attempt_id for attempt, _receipt in attempts)
    if entry_id != template.authority_entry_id or any(
        provisioned_attempt_ids.count(attempt_id) != 1 for attempt_id in selected_attempt_ids
    ):
        raise ValueError("candidate_experiment_issuer_attempt_not_selected")
    bounded = LiveCatalogExecutionConstraints.model_validate(
        {
            **constraints.model_dump(),
            "max_response_bytes": min(
                constraints.max_response_bytes, template.max_http_response_bytes
            ),
            "max_decompressed_bytes": min(
                constraints.max_decompressed_bytes, template.max_http_decompressed_bytes
            ),
            "timeout_cap_seconds": min(
                constraints.timeout_cap_seconds, template.max_http_timeout_seconds
            ),
        }
    )
    authorizations = tuple(
        _prepare_live_catalog_authorization(
            authority=port._authority,
            entry_id=entry_id,
            attempt_id=attempt_id,
            constraints=bounded,
            registry_providers=service._registry_providers,
        ).authorization
        for attempt_id in selected_attempt_ids
    )
    scope = _source_scope(
        service=service,
        origin=origin,
        port=port,
        entry_id=entry_id,
        variable_id=variable,
        country_code=bounded.country_code,
        year=bounded.start_year,
    )
    return issue_candidate_unpriced_experiment_policy(
        scope=scope,
        live_authorization=authorizations[0],
        subsequent_live_authorizations=authorizations[1:],
        n5_quota_profile=quota,
        source_payload_ref=source_payload_ref,
        request_content_hash=request_content_hash,
        original_metered_budget_usd=original_metered_budget_usd,
        limitations=(
            "acquisition_monetary_cost_not_established",
            "n5_monetary_cost_not_established",
            "per_call_usd_reservation_not_established",
            "candidate_only_no_publication_authority",
            "candidate_experiment_voi_not_established",
        ),
        configured_template=template,
    )


def prepare_candidate_experiment_policies_for_completed_job(
    *, control_service: ControlPlaneService, source_job_id: str
) -> tuple[artifacts.ArtifactRef, ...]:
    """Reopen actual owners and persist one uniquely configured candidate policy.

    Empty configuration is a no-op. Missing signed intent, compiler relation,
    source rights or an existing physical quota is a refusal; no owner is
    synthesized and the source job remains completed.
    """
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
        build_production_world_bank_wdi_execution_port,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoop,
        _CandidateExperimentSourceIdentity,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerInvocationProfile,
        BudgetMiddleware,
    )

    if type(control_service) is not ControlPlaneService:
        raise TypeError("candidate_experiment_issuer_control_owner_missing")
    providers = control_service._registry_providers
    if not providers.candidate_unpriced_policy_templates:
        return ()
    job = control_service._control_store.get_job(source_job_id)
    if (
        job is None
        or job.state != "completed"
        or job.kind != "natural_language_run"
        or job.run_id is None
    ):
        raise ValueError("candidate_experiment_issuer_source_not_completed")
    execution_scope = control_service._control_store.historical_completed_job_execution_scope(
        job_id=job.job_id, expected_run_id=job.run_id
    )
    if (
        execution_scope.status != "established"
        or execution_scope.actor_authenticated is not True
        or not execution_scope.tenant_id
        or not execution_scope.cell_id
    ):
        raise ValueError("candidate_experiment_issuer_scope_not_established")
    tenant_id, cell_id = execution_scope.tenant_id, execution_scope.cell_id
    templates = tuple(
        item
        for item in providers.candidate_unpriced_policy_templates
        if (item.tenant_id, item.cell_id) == (tenant_id, cell_id)
    )
    if not templates:
        return ()
    origin = AcquisitionRouteLoop(
        control_store=control_service._control_store,
        artifact_store=control_service._artifact_store,
        event_log=control_service._diagnostic_event_log,
        core_source_resolver=control_service.resolve_completed_control_job_core_run_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )._resolve_verified_origin(run_id=job.run_id, experiment=True)
    if origin.job != job or (
        origin.source_cycle.voi_decision.scheduler_action,
        origin.source_cycle.voi_decision.scheduler_reason,
    ) != ("reject", "roi_below_threshold"):
        raise ValueError("candidate_experiment_issuer_origin_mismatch")
    identity = _CandidateExperimentSourceIdentity(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=job.run_id,
        source_job_id=job.job_id,
        source_payload_ref=origin.payload_ref,
        capability_manifest_ref=origin.manifest_ref,
    )
    intent = control_service.verify_candidate_experiment_intent(closure=identity)
    binding = control_service.verify_acquisition_source_budget_owner(closure=identity)
    store = control_service.llm_producer_settlement_store
    if type(store) is not BudgetMiddleware:
        raise ValueError("candidate_experiment_issuer_quota_owner_missing")
    quota = store.snapshot_safe().invocation_profiles.get(job.run_id)
    if type(quota) is not BudgetLedgerInvocationProfile or quota.run_binding != binding:
        raise ValueError("candidate_experiment_issuer_quota_not_established")
    port = build_production_world_bank_wdi_execution_port(control_service=control_service)
    if type(port) is not WorldBankWDIAcquisitionExecutionPort or (
        port._artifact_store is not control_service._artifact_store
    ):
        raise ValueError("candidate_experiment_issuer_source_owner_missing")
    if intent.request_content_hash is None or intent.run_budget_usd is None:
        raise ValueError("candidate_experiment_issuer_signed_request_missing")
    if len(templates) != 1:
        raise ValueError("candidate_experiment_issuer_template_not_unique")
    policy = _prepare_policy(
        service=control_service,
        origin=origin,
        port=port,
        template=templates[0],
        quota=quota,
        source_payload_ref=origin.payload_ref,
        request_content_hash=intent.request_content_hash,
        original_metered_budget_usd=intent.run_budget_usd,
    )
    # Recheck the source/configuration immediately before this producer's only write.
    if control_service._control_store.get_job(job.job_id) != job or (
        control_service._registry_providers is not providers
    ):
        raise ValueError("candidate_experiment_issuer_source_changed")
    return (
        _persist_owned_candidate_unpriced_policy(
            store=control_service._artifact_store,
            event_log=control_service._diagnostic_event_log,
            policy=policy,
        ),
    )
