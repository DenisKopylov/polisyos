"""Behavioral tests for the candidate experiment policy issuer boundary.

These cases exercise the control service and SQLite job owner, but deliberately
do not claim a completed source route or a fetch permit.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedExperimentPolicyTemplate,
)
from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
    _prepare_policy,
    prepare_candidate_experiment_policies_for_completed_job,
)
from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, build_fixture_wdi_authority
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_candidate_unpriced_experiment_policy import (
    _selected_mixed_report,
)
from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import _owner


def _wdi_component(tmp_path: Path):
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )

    service = _build_control_service(tmp_path / "control")
    cas = service._artifact_store
    authority, entry = build_fixture_wdi_authority(tmp_path / "source", UNEMPLOYMENT_PROFILE)
    registry = authority._load_registry()
    port = WorldBankWDIAcquisitionExecutionPort(
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=tmp_path / "runtime",
        artifact_store=cas,
    )
    ledger, _middleware, observer = _owner(tmp_path / "quota-ledger.json", total=2, protected=1)
    quota = observer.invocation_quota_profile
    assert quota is not None
    scope, report = _selected_mixed_report(cas, _component_scope(cas, quota))
    record = next(
        row
        for row in report.acquisition_records
        if row.compiled_requirement_ref == scope.compiled_requirement_ref
    )
    origin = SimpleNamespace(
        planner_record=record,
        report=report,
        job=SimpleNamespace(run_id=scope.run_id, job_id=scope.source_job_id),
        compiled=SimpleNamespace(design_problem_ref=scope.design_problem_ref),
        selected_compiled_ref=scope.compiled_ref,
        source_cycle=SimpleNamespace(
            cycle_index=scope.source_cycle_index,
            selected_candidate_ref=scope.candidate_id,
            selected_candidate_content_hash=scope.candidate_content_hash,
            acquisition_routing_report_ref=scope.planner_report_ref,
        ),
        configured_port_source=SimpleNamespace(
            tenant_id=scope.tenant_id,
            cell_id=scope.cell_id,
            design_problem_basis_ref=scope.design_problem_basis_ref,
        ),
        design_problem_basis=SimpleNamespace(
            jurisdiction_time=SimpleNamespace(region="USA", data_time="2024")
        ),
    )
    template = CandidateUnpricedExperimentPolicyTemplate(
        **{
            **_template().model_dump(),
            "tenant_id": scope.tenant_id,
            "cell_id": scope.cell_id,
            "authority_entry_id": entry.entry_id,
            "authority_registry_sha256": registry.content_sha256,
            "authority_provision_sha256": authority.provision_content_sha256,
            "attempt_id": "wrong-attempt-issuer",
        }
    )
    return service, cas, port, quota, ledger, origin, template, report


def _component_scope(cas, quota):
    from tests.unit.runtime.quality.test_candidate_unpriced_policy import _component_policy

    return _component_policy(cas, quota)[0]


@pytest.mark.parametrize(
    "identity_field",
    ["authority_registry_sha256", "authority_provision_sha256"],
)
def test_prepare_policy_checks_canonical_authority_identity_and_attempt_before_effects(
    tmp_path, identity_field: str
):
    """Component source/compiler fixture; it does not claim a verified NL job route."""
    service, _cas, port, quota, ledger, origin, template, _report = _wdi_component(tmp_path)
    baseline = ledger.snapshot()
    with pytest.raises(ValueError, match="candidate_experiment_issuer_authority_identity_mismatch"):
        _prepare_policy(
            service=service,
            origin=origin,
            port=port,
            template=template.model_copy(update={identity_field: "sha256:" + "9" * 64}),
            quota=quota,
            source_payload_ref="sha256:" + "3" * 64,
            request_content_hash="sha256:" + "4" * 64,
            original_metered_budget_usd=Decimal("1.00"),
        )

    with pytest.raises(ValueError, match="candidate_experiment_issuer_attempt_not_selected"):
        _prepare_policy(
            service=service,
            origin=origin,
            port=port,
            template=template,
            quota=quota,
            source_payload_ref="sha256:" + "3" * 64,
            request_content_hash="sha256:" + "4" * 64,
            original_metered_budget_usd=Decimal("1.00"),
        )

    assert ledger.snapshot() == baseline
    assert not (tmp_path / "journal.jsonl").exists()
    assert not (tmp_path / "runtime").exists()


def test_prepare_policy_produces_bounded_real_authorization_without_source_effects(
    tmp_path,
):
    """Component fixture proves Fabric authorization, not a completed NL source route."""
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )

    service, _cas, port, quota, ledger, origin, template, _report = _wdi_component(tmp_path)
    service._registry_providers = resolve_control_registry_providers()
    template = template.model_copy(
        update={
            "attempt_id": port._provision.live_harness_receipts[0].attempt_id,
            "max_http_response_bytes": 8_192,
            "max_http_decompressed_bytes": 4_096,
            "max_http_timeout_seconds": 5.0,
        }
    )
    baseline = ledger.snapshot()

    policy = _prepare_policy(
        service=service,
        origin=origin,
        port=port,
        template=template,
        quota=quota,
        source_payload_ref="sha256:" + "3" * 64,
        request_content_hash="sha256:" + "4" * 64,
        original_metered_budget_usd=Decimal("1.00"),
    )

    assert policy.live_authorization.attempt_id == template.attempt_id
    assert policy.live_authorization.budget.max_response_bytes == 8_192
    assert policy.live_authorization.budget.max_decompressed_bytes == 4_096
    assert policy.live_authorization.budget.timeout_seconds <= 5.0
    assert policy.publication_authority is False
    assert ledger.snapshot() == baseline
    assert not (tmp_path / "journal.jsonl").exists()
    assert not (tmp_path / "runtime").exists()


def _template() -> CandidateUnpricedExperimentPolicyTemplate:
    return CandidateUnpricedExperimentPolicyTemplate(
        tenant_id="tenant-issuer",
        cell_id="cell-issuer",
        authority_entry_id="worldbank.wdi.unemployment",
        authority_registry_sha256="sha256:" + "1" * 64,
        authority_provision_sha256="sha256:" + "2" * 64,
        attempt_id="issuer-attempt-001",
        max_http_response_bytes=65_536,
        max_http_decompressed_bytes=65_536,
        max_http_timeout_seconds=30,
        max_standard_n5_invocations=2,
        max_metered_reentry_usd=Decimal("0.20"),
    )


def _configured_service(tmp_path):
    service = _build_control_service(tmp_path)
    service._registry_providers = replace(
        service._registry_providers,
        candidate_unpriced_policy_templates=(_template(),),
    )
    return service


def _create_job(service, *, job_id: str, state: str, scope: dict[str, object] | None):
    event: dict[str, object] = {"job_id": job_id}
    if scope is not None:
        event["execution_scope"] = scope
    job = service._control_store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id="issuer-run-001",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="issuer-user",
        creation_event_payload=event,
    )
    if state == "completed":
        leased = service._control_store.lease_next_job(worker_id="issuer-fixture-worker")
        assert leased is not None and leased.job_id == job_id
        service._control_store.complete_job(
            job_id=job_id,
            run_id="issuer-run-001",
            progress={"state": "completed", "phase": "natural_language_run"},
            expected_lease_owner=leased.lease_owner,
            expected_attempt=leased.attempt,
        )
    return job


def test_empty_templates_are_a_noop_without_job_or_source_owner_access(tmp_path, monkeypatch):
    service = _build_control_service(tmp_path)

    def _unexpected(*_args, **_kwargs):
        pytest.fail("empty policy configuration accessed a source owner")

    monkeypatch.setattr(service._control_store, "get_job", _unexpected)
    assert (
        prepare_candidate_experiment_policies_for_completed_job(
            control_service=service,
            source_job_id="absent-job",
        )
        == ()
    )


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing", "candidate_experiment_issuer_source_not_completed"),
        ("pending", "candidate_experiment_issuer_source_not_completed"),
        ("unknown_scope", "control_job_execution_scope_not_established"),
    ],
)
def test_ineligible_source_refuses_before_source_port_or_quota_owner(
    tmp_path, monkeypatch, case: str, expected: str
):
    service = _configured_service(tmp_path)
    scope = (
        None
        if case == "unknown_scope"
        else {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "tenant_id": "tenant-issuer",
            "cell_id": "cell-issuer",
            "actor_subject": "issuer-user",
            "actor_authenticated": True,
            "actor_roles": ["operator"],
        }
    )
    if case != "missing":
        _create_job(
            service,
            job_id="issuer-job",
            state="pending" if case == "pending" else "completed",
            scope=scope,
        )

    def _unexpected(*_args, **_kwargs):
        pytest.fail("ineligible source reached source port configuration")

    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_surface_execution.build_production_world_bank_wdi_execution_port",
        _unexpected,
    )
    source_job_id = "absent-job" if case == "missing" else "issuer-job"
    with pytest.raises((ValueError, RuntimeError), match=expected):
        prepare_candidate_experiment_policies_for_completed_job(
            control_service=service,
            source_job_id=source_job_id,
        )

    assert service._artifact_store.root.exists()
