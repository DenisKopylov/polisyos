"""Actual WDI/default executor and native owner chain through same-case re-entry."""

import json
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services import (
    acquisition_surface_execution as acquisition_surface_execution_module,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.quality.acquisition_executor import (
    LiveAcquisitionExecutionError,
    SemanticEpochAdmissionResolutionError,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleController,
    RealValueOwnerGateway,
    ValueOwnerAccessError,
    currentness_for_generation_cycle_run,
    validate_generation_cycle_candidate_run,
    validate_generation_cycle_run,
)
from tests._helpers import controlled_candidate_profile as cycle_fixtures
from tests._helpers.acquisition_chain import (
    begin_current_wdi_action,
    make_wdi_port_case,
    select_current_wdi_action_outcome,
)
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests._helpers.runtime_http import _build_control_service

# The served ingestion sidecar contract requires UUID-form tenant identities.
_SERVED_WDI_FIXTURE_TENANT_ID = "7cf3b2a8-0d6b-4d25-a01c-f248e933e1f0"


def _closure_with_synthetic_revised_basis(closure):
    """Give the real binding seam a typed S/B divergence without forging route closure."""

    basis = closure.design_problem_basis
    revised_basis = basis.model_copy(
        update={
            "jurisdiction_time": basis.jurisdiction_time.model_copy(
                update={"region": "USA", "data_time": "2025"}
            )
        }
    )
    return SimpleNamespace(
        **{
            **closure.__dict__,
            "design_problem_basis": revised_basis,
            "design_problem_basis_ref": gy_content_hash(revised_basis.model_dump(mode="json")),
        }
    )


def _executor_probe_port(case):
    """Stop at the executor boundary and record any attempted authorized fetch."""

    attempted_constraints = []

    def stop_at_executor(**kwargs):
        attempted_constraints.append(kwargs["constraints"])
        raise AssertionError("live acquisition executor boundary was reached")

    port = acquisition_surface_execution_module.WorldBankWDIAcquisitionExecutionPort(
        authority=case.port._authority,
        registry=case.port._registry,
        provision=case.port._provision,
        provision_content_sha256=case.port._provision_content_sha256,
        runtime_state_root=case.port._runtime_state_root,
        artifact_store=case.port._artifact_store,
        executor=stop_at_executor,
    )
    return port, attempted_constraints


def test_ordinary_l4_data_state_writer_keeps_legacy_snapshot_valid(tmp_path, monkeypatch):
    """The ordinary producer schema remains readable under its registered contract."""
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.runtime.quality import data_state_substrate
    from polisyos.runtime.quality.data_snapshot_lineage import (
        validate_data_snapshot_owner_lineage,
    )

    store = FileSystemCAS(tmp_path / "cas")
    source_paths = data_state_substrate._DataStatePaths(
        l1_dcat_path=tmp_path / "l1.parquet",
        agent_registry_full=tmp_path / "agent-registry.parquet",
        firm_fundamentals_annual=tmp_path / "firm-fundamentals.parquet",
        budget_flows_monthly_sparse=tmp_path / "budget-flows.parquet",
        corrected_firm_panels=tmp_path / "corrected-firm-panels.parquet",
        calibrated_household_cells=tmp_path / "calibrated-household-cells.parquet",
    )
    monkeypatch.setattr(
        data_state_substrate,
        "_default_data_state_paths",
        lambda *_args, **_kwargs: source_paths,
    )
    monkeypatch.setattr(data_state_substrate, "_require_paths", lambda *_a, **_k: None)
    monkeypatch.setattr(
        data_state_substrate,
        "build_l5_family_binding_profile",
        lambda *_a, **_k: SimpleNamespace(
            schema_regime_status="single_regime",
            model_dump=lambda **_kwargs: {"schema_version": "controlled-test"},
        ),
    )
    monkeypatch.setattr(
        data_state_substrate,
        "_project_real_l4_payload",
        lambda *_a, **_k: (
            {"agents": {"income": [1200.0]}},
            {
                "bound_agent_count": 1,
                "l4_total_rows": {
                    "agent_registry_full": 1,
                    "budget_flows_monthly_sparse": 0,
                },
            },
        ),
    )

    result = data_state_substrate.materialize_l4_data_state_snapshot(
        store,
        repo_root=tmp_path,
        workspace_dir=tmp_path / "workspace",
        agent_limit=1,
        required_l1_variables=(),
        families=("firm_fundamentals",),
        substrate_registry=SimpleNamespace(substrate_version_id="controlled-test"),
        period_start="2026-01",
        period_end="2026-02",
    )
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(result.data_snapshot_ref))
    )
    payload_manifest = store.get_manifest(snapshot.data_ref)
    assert payload_manifest.artifact_schema.name == "polisyos.runtime.quality.DataStatePayload"
    assert payload_manifest.artifact_schema.version == (
        data_state_substrate.DATA_STATE_SUBSTRATE_SCHEMA_VERSION
    )
    assert snapshot.source_lineage is None
    validate_data_snapshot_owner_lineage(store, result.data_snapshot_ref, snapshot)


def _assert_exact_native_appointment_repeat(case, store):
    """Prove a repeated exact appointment reuses its custodian and envelope."""
    first_appointment = case.appoint_native_policy()
    first_signature_bytes = store.get_signature_bytes(first_appointment.signed.artifact_ref)
    first_record_bytes = first_appointment.signed.evidence.record_bytes
    first_key_bytes = first_appointment.custodian.public_key_path.read_bytes()

    repeated_appointment = case.appoint_native_policy()
    assert repeated_appointment.custodian is first_appointment.custodian
    assert repeated_appointment.signed.artifact_ref == first_appointment.signed.artifact_ref
    assert (
        repeated_appointment.signed.evidence.evidence_record_ref
        == first_appointment.signed.evidence.evidence_record_ref
    )
    assert repeated_appointment.signed.evidence.record_bytes == first_record_bytes
    assert store.get_signature_bytes(repeated_appointment.signed.artifact_ref) == (
        first_signature_bytes
    )
    assert first_appointment.custodian.public_key_path.read_bytes() == first_key_bytes
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    verifier.load_trusted_key_file(
        first_appointment.custodian.public_key_path,
        identity=first_appointment.custodian.issuer_identity,
    )
    assert (
        store.verify_signature(
            first_appointment.signed.artifact_ref,
            verifier,
            strict_identity=True,
        ).status
        is artifacts.SignatureVerificationStatus.VALID
    )


def test_wdi_constraints_use_revised_basis_year_with_same_basis_control():
    """The WDI binding owner selects B's year while preserving the S=B control."""

    subject = cycle_fixtures._problem("r13_wdi_basis_year_selector")
    subject = subject.model_copy(
        update={
            "jurisdiction_time": subject.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2024"}
            )
        }
    )
    revised_basis = subject.model_copy(
        update={
            "jurisdiction_time": subject.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2023"}
            )
        }
    )
    same_basis_view = SimpleNamespace(
        design_problem=subject,
        design_problem_basis=subject,
    )
    revised_basis_view = SimpleNamespace(
        design_problem=subject,
        design_problem_basis=revised_basis,
    )

    same_constraints = acquisition_surface_execution_module._constraints_from_live_variable_route(
        same_basis_view
    )
    revised_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(
            revised_basis_view
        )
    )

    assert (
        same_constraints.country_code,
        same_constraints.start_year,
        same_constraints.end_year,
    ) == (
        "UKR",
        2024,
        2024,
    )
    assert (
        revised_constraints.country_code,
        revised_constraints.start_year,
        revised_constraints.end_year,
    ) == ("UKR", 2023, 2023)


@pytest.mark.asyncio
async def test_native_policy_appointment_reuses_custodian_on_exact_repeat(tmp_path, monkeypatch):
    """Re-appointment preserves the exact admission and first issuer trust key."""

    def reject_local_route_rebuild(*args, **kwargs):
        del args, kwargs
        raise AssertionError("native bridge must not enter the contract-test ACQ-01 helper")

    monkeypatch.setattr(
        GenerationCycleController,
        "_rebuild_n7_acq01_route_context",
        reject_local_route_rebuild,
    )
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
    )
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)

    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    _ref, deferral, _attempt = case.bridge._load_deferral(closure)
    assert deferral.negative_receipt.failure_codes == ("policy_admission_missing",), (
        deferral.negative_receipt.failure_codes
    )
    _assert_exact_native_appointment_repeat(case, control._artifact_store)


@pytest.mark.asyncio
async def test_bridge_resume_reenters_after_current_source_passport_and_epoch(
    tmp_path, monkeypatch
):
    """A source-bound candidate re-enters while N6 authority stays typed UNRUN."""

    def reject_local_route_rebuild(*args, **kwargs):
        del args, kwargs
        raise AssertionError("native bridge must not enter the contract-test ACQ-01 helper")

    monkeypatch.setattr(
        GenerationCycleController,
        "_rebuild_n7_acq01_route_context",
        reject_local_route_rebuild,
    )
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
    )
    run = closure.generation_run
    assert run.deployment_identity_status == "established"
    assert run.deployment_identity is not None
    currentness = currentness_for_generation_cycle_run(run)
    assert currentness.status == "not_established"
    assert currentness.census_verdict == "UNRUN"
    assert currentness.reason_code == "n6_census_issuer_not_appointed"
    assert currentness.unresolved_by_construction == (
        "packaged_build_identity_issuer_not_appointed",
        "n6_strangle_census_not_established",
        "deployment_authority_issuer_not_appointed",
    )
    assert run.strangle_receipt.status == "not_established"
    assert {
        "n6_census_issuer_not_appointed",
        "deployment_authority_issuer_not_appointed",
        "source_census_is_tooling_evidence_only",
    }.issubset(set(run.strangle_receipt.limitation_refs))
    assert validate_generation_cycle_candidate_run(run) == ()
    strict_issues = validate_generation_cycle_run(run)
    currentness_issue = next(
        issue
        for issue in strict_issues
        if issue["code"] == "strangle_receipt_currentness_not_established"
    )
    assert currentness_issue == {
        "code": "strangle_receipt_currentness_not_established",
        "reason": "n6_census_issuer_not_appointed",
        "census_verdict": "UNRUN",
        "unresolved_by_construction": currentness.unresolved_by_construction,
    }
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.receipts == ()
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)

    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    action = begin_current_wdi_action(
        control, closure, job_id=f"direct-bridge-action-{uuid.uuid4().hex}"
    )
    committed = case.port.execute(closure, action_phase_ref=action.executing_head.receipt_ref)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store
    assert case.port.project_world_growth_outcome(closure) == ("not_established", None)
    selected_head = select_current_wdi_action_outcome(control, action, committed)
    assert selected_head.receipt_phase == "outcome_selected"

    reentry_ref = case.bridge.resume(closure, committed.owner_receipt_refs)
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(reentry_ref))
    )
    growth = case.bridge.project_growth(closure)
    assert growth is not None
    assert reentry.source_run_id == closure.generation_run.run_id
    assert reentry.design_problem_ref == closure.design_problem_ref
    assert reentry.source_cycle_index == closure.source_cycle.cycle_index
    assert reentry.new_cycle.cycle_index == closure.source_cycle.cycle_index + 1
    assert reentry.passport_id == growth.passport_id
    assert reentry.epoch_id == growth.selection.epoch_id
    assert reentry.overlay_receipt_ref == committed.overlay_admission_receipt_ref
    assert reentry.admitted_observation_count == (
        growth.previously_active_observations + growth.admitted_observation_delta
    )
    assert reentry.admitted_observation_count > 0
    assert reentry.semantic_epoch_ref == str(growth.activation.semantic_epoch_stamp.epoch_ref)
    assert reentry.semantic_epoch_production_receipt_content_hash


@pytest.mark.asyncio
async def test_served_resume_refuses_selected_value_drift_with_receipt_markers_retained(
    tmp_path, monkeypatch
):
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=Path(__file__).resolve().parents[3],
    )
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    committed = case.port.execute(closure)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1

    selected = case.bridge.selection(closure)
    assert selected is not None
    overlay_path, _ = case.bridge._paths(selected)
    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        owner_markers = con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
            "FROM acquisition_epochs WHERE epoch_id = ?",
            [selected.epoch_id],
        ).fetchone()
        assert owner_markers is not None
        member_key = con.execute(
            "SELECT canonical_primary_key_bytes FROM acquisition_epoch_members "
            "WHERE epoch_id = ? AND passport_id = ? AND table_name = 'ds_observations' "
            "ORDER BY canonical_primary_key_hash LIMIT 1",
            [selected.epoch_id, owner_markers[0]],
        ).fetchone()
        selected_member_count = con.execute(
            "SELECT count(*) FROM acquisition_epoch_members "
            "WHERE epoch_id = ? AND passport_id = ? AND table_name = 'ds_observations'",
            [selected.epoch_id, owner_markers[0]],
        ).fetchone()
    finally:
        con.close()
    assert owner_markers[2] == committed.admitted_observation_delta == 1
    assert member_key is not None
    assert selected_member_count == (committed.admitted_observation_delta,)
    member_text = bytes(member_key[0]).decode("ascii")
    prefix = "ds_observations|observation_id="
    assert member_text.startswith(prefix)
    observation_id = bytes.fromhex(member_text.removeprefix(prefix)).decode("utf-8")

    con = duckdb.connect(str(overlay_path))
    try:
        original_row = con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone()
        assert original_row is not None
        con.execute(
            "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
            [float(original_row[1]) + 1.0, observation_id],
        )
    finally:
        con.close()

    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        assert con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE observation_id = ?",
            [observation_id],
        ).fetchone() == (observation_id, float(original_row[1]) + 1.0)
        assert (
            con.execute(
                "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
                "FROM acquisition_epochs WHERE epoch_id = ?",
                [selected.epoch_id],
            ).fetchone()
            == owner_markers
        )
        assert con.execute(
            "SELECT count(*) FROM acquisition_epoch_members WHERE epoch_id = ? "
            "AND table_name = 'ds_observations' AND canonical_primary_key_bytes = ?",
            [selected.epoch_id, member_key[0]],
        ).fetchone() == (1,)
    finally:
        con.close()

    with pytest.raises(SemanticEpochAdmissionResolutionError) as refused:
        case.bridge.resume(closure, committed.owner_receipt_refs)
    assert refused.value.code == "basis_mismatch"
    assert "active_epoch_observation_content_mismatch" in refused.value.detail


@pytest.mark.asyncio
async def test_revised_cycle_basis_survives_served_native_admission_and_reentry(
    tmp_path, monkeypatch
):
    """A costed cycle N>0 re-enters on its exact revision basis, under stable subject S."""

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
        revised_source=True,
    )
    subject = closure.design_problem_ref
    basis = closure.design_problem_basis_ref
    assert closure.source_cycle.cycle_index == 1
    assert subject == closure.generation_run.design_problem_ref
    assert subject == closure.source_cycle.design_problem_ref
    assert subject != basis
    assert (
        closure.design_problem_basis
        == closure.generation_run.cycles[0].revision_request.revised_problem
    )
    assert closure.generation_run.cycles[1].design_problem_basis_ref == basis

    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    action = begin_current_wdi_action(
        control, closure, job_id=f"direct-bridge-action-{uuid.uuid4().hex}"
    )
    committed = case.port.execute(closure, action_phase_ref=action.executing_head.receipt_ref)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store
    assert case.port.project_world_growth_outcome(closure) == ("not_established", None)
    selected_head = select_current_wdi_action_outcome(control, action, committed)
    assert selected_head.receipt_phase == "outcome_selected"

    reentry_ref = case.bridge.resume(closure, committed.owner_receipt_refs)
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(reentry_ref))
    )
    growth = case.bridge.project_growth(closure)
    assert growth is not None
    assert reentry.source_run_id == closure.generation_run.run_id
    assert reentry.design_problem_ref == subject
    assert reentry.source_cycle_index == 1
    assert reentry.new_cycle.cycle_index == 2
    assert reentry.new_cycle.design_problem_ref == subject
    assert reentry.new_cycle.design_problem_basis_ref == basis
    assert reentry.passport_id == growth.passport_id
    assert reentry.epoch_id == growth.selection.epoch_id
    assert reentry.overlay_receipt_ref == committed.overlay_admission_receipt_ref
    assert reentry.admitted_observation_count == (
        growth.previously_active_observations + growth.admitted_observation_delta
    )
    assert reentry.semantic_epoch_ref == str(growth.activation.semantic_epoch_stamp.epoch_ref)

    prior = closure.generation_run.cycles[0]
    revised = prior.revision_request.revised_problem
    changed_basis = revised.model_copy(
        update={
            "runtime_hints": {
                **revised.runtime_hints,
                "r13_basis_removal_probe": "changed-with-subject-and-receipt-markers-retained",
            }
        }
    )
    changed_request = prior.revision_request.model_copy(update={"revised_problem": changed_basis})
    changed_prior = prior.model_copy(update={"revision_request": changed_request})
    changed_run = closure.generation_run.model_copy(
        update={"cycles": (changed_prior, *closure.generation_run.cycles[1:])}
    )
    changed_closure = closure.model_copy(update={"generation_run": changed_run})
    assert changed_closure.design_problem_ref == subject
    assert changed_closure.route_id == closure.route_id
    assert changed_closure.source_cycle.design_problem_basis_ref == basis
    with pytest.raises(AcquisitionRouteClosureError, match="source_cycle_basis_chain_invalid"):
        case.bridge._validate_reentry(changed_closure, growth, reentry)


@pytest.mark.asyncio
async def test_revised_basis_scope_refuses_before_egress_and_selector_removal_is_red(
    tmp_path, monkeypatch
):
    """B=USA/2025 cannot inherit S=UKR/2024's otherwise-valid WDI authority."""

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    served_closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
    )
    assert served_closure.source_cycle.cycle_index == 0
    assert served_closure.design_problem_basis_ref == served_closure.design_problem_ref
    # Keep this as a boundary-only negative: the mutated B is deliberately not
    # an admitted source record or an external authority input. It must be refused
    # before the live executor or transport sees a request.
    closure = _closure_with_synthetic_revised_basis(served_closure)
    subject = closure.design_problem_ref
    basis = closure.design_problem_basis_ref
    assert closure.design_problem.jurisdiction_time.region == "UKR"
    assert closure.design_problem.jurisdiction_time.data_time == "2024"
    assert closure.design_problem_basis.jurisdiction_time.region == "USA"
    assert closure.design_problem_basis.jurisdiction_time.data_time == "2025"
    assert served_closure.source_cycle.design_problem_ref == subject
    assert served_closure.design_problem_basis_ref != basis
    assert subject == closure.generation_run.design_problem_ref
    assert subject != basis

    case = make_wdi_port_case(
        tmp_path / "wdi", monkeypatch, control=control, closure=served_closure
    )
    probe_port, attempted_constraints = _executor_probe_port(case)
    with pytest.raises(LiveAcquisitionExecutionError) as refused:
        probe_port.execute(closure)
    assert refused.value.code == "live_request_outside_authority_countries"
    assert attempted_constraints == [], "out-of-authority basis reached the executor boundary"
    assert case.transport_calls == [], "out-of-authority revised basis reached WDI egress"

    # Marker-retaining removal probe: restore the old subject selector while the
    # stable subject, revised-basis ref, and route identity remain unchanged.
    subject_only = SimpleNamespace(
        design_problem=closure.design_problem,
        design_problem_basis=closure.design_problem,
    )
    old_subject_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(subject_only)
    )
    with monkeypatch.context() as removal:
        removal.setattr(
            acquisition_surface_execution_module,
            "_constraints_from_live_variable_route",
            lambda _closure: old_subject_constraints,
        )
        assert closure.design_problem_ref == subject
        assert closure.design_problem_basis_ref == basis
        with pytest.raises(AssertionError, match="executor boundary was reached"):
            probe_port.execute(closure)
    assert closure.route_id == served_closure.route_id
    assert len(attempted_constraints) == 1
    assert attempted_constraints[0].country_code == "UKR"
    assert attempted_constraints[0].start_year == 2024
    assert attempted_constraints[0].end_year == 2024
    assert case.transport_calls == []  # the injected boundary records but never sends requests


async def _run_actual_wdi_admits_delta_and_reenters_same_case_impl(
    tmp_path,
    monkeypatch,
    request,
    *,
    guarded_cas: bool,
    tenant_id: str = _SERVED_WDI_FIXTURE_TENANT_ID,
    cell_id: str = "cell-a",
    revised_source: bool = False,
    generation_cycle_repo_root: Path | None = None,
    artifact_store: artifacts.FileSystemCAS | None = None,
):
    # This is a downstream owner-chain witness: the candidate parent and leaf
    # use for_contract_testing and share the app CAS. The recursive result stays
    # synthetic; the protected-intent production leaf boundary is tested in the
    # paired unit suite.
    selected_artifact_store = None
    if guarded_cas:
        from polisyos.runtime.http.resilience import guard_runtime_cas

        base_store = artifact_store or artifacts.FileSystemCAS(tmp_path / "control" / ".polisyos")
        selected_artifact_store = guard_runtime_cas(
            base_store.for_tenant(tenant_id, cell_id=cell_id)
        )
        request.addfinalizer(selected_artifact_store.close)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(
        tmp_path / "control",
        artifact_store=selected_artifact_store,
    )
    if generation_cycle_repo_root is not None:
        # Use one real, isolated owner repo for recursive generation and the
        # later WDI gateway. The existing fixture recipe binds the catalog
        # bytes and supplies the required owner files in this scratch root.
        from tests._helpers import acquisition_production
        from tests._helpers.acquisition_epoch_production import (
            production_admission_inputs,
        )

        authority, _ = acquisition_production._resolver(generation_cycle_repo_root)
        production_admission_inputs(
            tmp_path / "wdi" / "generation-inputs",
            store=control._artifact_store,
            authority=authority,
            overlay_path=tmp_path / "wdi" / "overlay.duckdb",
            epoch_history_root=tmp_path / "wdi" / "epochs",
        )
    closure, _ = await persist_wdi_route(
        control,
        tenant_id=tenant_id,
        cell_id=cell_id,
        revised_source=revised_source,
        generation_cycle_repo_root=generation_cycle_repo_root,
    )
    if revised_source:
        from polisyos.runtime.quality.acquisition_planner import (
            load_acquisition_planner_report,
        )

        route_source_cycle = closure.route_source_cycle
        source_requirement = route_source_cycle.value_port.acquisition_requirement
        planner_report_ref = route_source_cycle.acquisition_routing_report_ref
        assert route_source_cycle.grounding.acquisition_requirement is None
        assert source_requirement is not None
        assert planner_report_ref is not None
        persisted_report = load_acquisition_planner_report(
            control._artifact_store,
            planner_report_ref,
        )
        assert persisted_report == closure.planner_report
        assert route_source_cycle.acquisition_routing_report == persisted_report
        assert len(persisted_report.acquisition_records) == 1
        persisted_record = persisted_report.acquisition_records[0]
        # The typed owner serializer preserves additive-field presence; compare the loaded
        # DTO values instead of requiring an identical fields-set wire projection.
        assert persisted_record == closure.planner_record
        assert (
            persisted_record.gap_type.value
            == source_requirement.gap_type.value
            == "data_snapshot_release"
        )
        assert (
            persisted_record.requirement_family
            == source_requirement.requirement_family.value
            == "data_requirement"
        )
        assert (
            persisted_record.requirement_schema_version
            == source_requirement.requirement_schema_version
            == "policyos.runtime.l1_variable_availability_gap.v1"
        )
        assert persisted_record.compiled_requirement_ref == (
            source_requirement.compiled_requirement_ref
        )
        assert (
            persisted_record.missing_requirement_fields
            == (source_requirement.missing_requirement_fields)
            == ("canonical_variable_observations:government.balance",)
        )
        assert persisted_record.recommended_strategy.value == "production_snapshot_build"
    assert (closure.tenant_id, closure.cell_id) == (tenant_id, cell_id)
    run = closure.generation_run
    currentness = currentness_for_generation_cycle_run(run)
    assert currentness.status == "not_established"
    assert currentness.census_verdict == "UNRUN"
    assert run.strangle_receipt.status == "not_established"
    assert "n6_census_issuer_not_appointed" in run.strangle_receipt.limitation_refs
    assert validate_generation_cycle_candidate_run(run) == ()
    strict_issue_codes = {issue["code"] for issue in validate_generation_cycle_run(run)}
    assert "strangle_receipt_currentness_not_established" in strict_issue_codes
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.receipts == ()
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    assert case.bridge.has_deferred_admission(closure)
    original_bytes = {
        ref: control._artifact_store.get_bytes(ref) for ref in quarantined.owner_receipt_refs
    }
    fetched = tuple(case.transport_calls)
    # A new attempt without appointment remains a known negative, without another fetch.
    repeated = case.port.execute(closure)
    assert repeated.disposition == "quarantined_no_growth"
    assert tuple(case.transport_calls) == fetched
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    action_job_id = f"direct-owner-action-{uuid.uuid4().hex}"
    action = begin_current_wdi_action(control, closure, job_id=action_job_id)
    executing_head = action.executing_head
    result = case.port.execute(closure, action_phase_ref=executing_head.receipt_ref)
    assert result.disposition == "world_committed"
    assert tuple(case.transport_calls) == fetched
    assert all(control._artifact_store.get_bytes(ref) == raw for ref, raw in original_bytes.items())
    assert result.admitted_observation_delta == 1
    assert len(case.transport_calls) > 0
    assert len(case.appointments) == 1
    before = tuple(case.transport_calls)
    # Lose only the post-activation acknowledgement; recover from native owner bytes.
    case.bridge._growth_pointer(case.selected).unlink()
    with pytest.raises(
        AcquisitionActionServiceError, match="acquisition_live_evidence_not_admitted"
    ):
        case.port.recover_owned_result(closure)
    assert (
        case.port.recover_owned_result(closure, action_phase_ref=executing_head.receipt_ref)
        == result
    )
    tampered_closure = closure.model_copy(update={"compiled_ref": "sha256:" + "0" * 64})
    with pytest.raises(ValueError, match="acquisition_action_phase_source_binding_mismatch"):
        case.port.recover_owned_result(
            tampered_closure, action_phase_ref=executing_head.receipt_ref
        )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthConfig,
    )

    changed_selection = case.selected.model_copy(update={"epoch_id": case.selected.epoch_id + 1})
    changed_config = case.bridge.config.model_copy(update={"routes": (changed_selection,)})
    changed_epoch_bridge = type(case.bridge)(
        config=changed_config,
        repo_root=case.bridge.repo_root,
        runtime_root=case.bridge.runtime_root,
        authority=case.bridge.authority,
        artifact_store=control._artifact_store,
        event_log=case.bridge.event_log,
        epoch_deployment=case.bridge.epoch_deployment,
        promotion_runtime=case.bridge.promotion_runtime,
        cycle_substrate_context_admission_owner=(
            case.bridge.cycle_substrate_context_admission_owner
        ),
        control_store=case.bridge.control_store,
    )
    assert type(changed_config) is AcquisitionWorldGrowthConfig
    with pytest.raises(ValueError, match="acquisition_world_growth_case_mismatch"):
        changed_epoch_bridge.recover_admission(closure, executing_head.receipt_ref)
    assert tuple(case.transport_calls) == before
    assert case.port.project_world_growth_outcome(closure) == ("not_established", None)
    selected_head = select_current_wdi_action_outcome(control, action, result)
    assert selected_head.receipt_phase == "outcome_selected"
    growth_status, selected_growth = case.port.project_world_growth_outcome(closure)
    assert growth_status == "admitted_delta"
    assert selected_growth is not None
    assert selected_growth.admitted_observation_delta == 1
    ref = case.port.reenter(closure, result)
    receipt = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(ref))
    )
    assert receipt.source_run_id == closure.generation_run.run_id
    assert receipt.design_problem_ref == closure.design_problem_ref
    assert receipt.new_cycle.cycle_index == closure.source_cycle.cycle_index + 1
    before = tuple(case.transport_calls)
    assert case.port.resume_reentry(closure, result.owner_receipt_refs) == ref
    assert (
        case.port.recover_owned_result(closure, action_phase_ref=executing_head.receipt_ref)
        == result
    )
    assert tuple(case.transport_calls) == before
    growth_refs = tuple(
        ref
        for ref in result.owner_receipt_refs
        if control._artifact_store.get_manifest(ref).kind
        == "runtime_quality.acquisition_world_growth_receipt"
    )
    assert len(growth_refs) == 1
    growth_ref = growth_refs[0]
    attempt_pointer = case.bridge._growth_pointer(case.selected, create=False).with_suffix(
        ".attempt.json"
    )
    attempt_ref = json.loads(attempt_pointer.read_text())["receipt_ref"]
    overlay_path, _ = case.bridge._paths(case.selected, create=False)
    reentry_pointer = overlay_path.parent / (growth_ref.removeprefix("sha256:") + ".reentry.json")
    reentry_pointer_before = reentry_pointer.read_bytes()
    reentry_ref = json.loads(reentry_pointer_before)["receipt_ref"]
    reentry_bytes_before = control._artifact_store.get_bytes(reentry_ref)

    no_growth = case.port.execute(closure)
    assert no_growth.disposition == "quarantined_no_growth"
    assert no_growth.admitted_observation_delta == 0
    assert no_growth.overlay_admission_receipt_ref is None
    assert no_growth.post_epoch_event_ref is None
    assert set(no_growth.owner_receipt_refs) == set(result.owner_receipt_refs) | {attempt_ref} | {
        ref
        for ref in no_growth.owner_receipt_refs
        if control._artifact_store.get_manifest(ref).kind
        == "runtime_quality.acquisition_world_growth_no_growth_receipt"
    }
    no_growth_refs = tuple(
        ref
        for ref in no_growth.owner_receipt_refs
        if control._artifact_store.get_manifest(ref).kind
        == "runtime_quality.acquisition_world_growth_no_growth_receipt"
    )
    assert len(no_growth_refs) == 1
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthAttempt,
        AcquisitionWorldGrowthNoGrowthReceipt,
    )

    no_growth_receipt = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(no_growth_refs[0]))
    )
    attempt = AcquisitionWorldGrowthAttempt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(attempt_ref))
    )
    assert no_growth_receipt.selection == case.selected
    assert no_growth_receipt.growth_receipt_ref == growth_ref
    assert no_growth_receipt.attempt_ref == attempt_ref
    assert no_growth_receipt.binding_id == attempt.binding_id
    assert no_growth_receipt.live_evidence_refs == attempt.owner_receipt_refs
    assert no_growth_receipt.before == no_growth_receipt.after
    assert no_growth_receipt.admitted_observation_delta == 0
    assert json.loads(attempt_pointer.read_text())["receipt_ref"] == attempt_ref
    assert reentry_pointer.read_bytes() == reentry_pointer_before
    assert control._artifact_store.get_bytes(reentry_ref) == reentry_bytes_before
    assert tuple(case.transport_calls) == before
    # Exercise the real list/detail projection reader with the already verified port.
    service = object.__new__(AcquisitionActionService)
    service._execution_port = case.port
    service._production_execution_port = case.port
    service._authority_provider = None
    assert service._projection(closure).admitted_observation_delta == 1
    blob, _ = control._artifact_store._paths(
        artifacts.ArtifactID.model_validate(result.overlay_admission_receipt_ref)
    )
    native = blob.read_bytes()
    blob.unlink()
    try:
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_native_admission_unverified"
        ):
            service._projection(closure)
    finally:
        blob.write_bytes(native)
    if guarded_cas:
        from polisyos.core.artifacts.ownership import ArtifactOwnershipError
        from polisyos.core.security.tenant_context import tenant_scope

        growth = case.port.project_world_growth(closure)
        passport_ref = growth.activation.passport_ref
        assert (
            control._artifact_store.get_manifest(passport_ref).kind
            == "epoch.acquisition_passport_snapshot"
        )
        assert control._artifact_store.get_bytes(passport_ref)
        foreign_store = guard_runtime_cas(
            artifacts.FileSystemCAS(tmp_path / "control" / ".polisyos").for_tenant(
                "89b6f3a7-e34c-4ea7-9c01-9a8a9d801fe4",
                cell_id=cell_id,
            )
        )
        request.addfinalizer(foreign_store.close)
        with (
            tenant_scope(
                None,
                tenant_id="89b6f3a7-e34c-4ea7-9c01-9a8a9d801fe4",
                cell_id=cell_id,
            ),
            pytest.raises(ArtifactOwnershipError),
        ):
            foreign_store.get_bytes(passport_ref)
    return SimpleNamespace(
        control=control,
        closure=closure,
        case=case,
        committed=result,
        reentry=receipt,
    )


async def _run_actual_wdi_admits_delta_and_reenters_same_case(
    tmp_path,
    monkeypatch,
    request,
    *,
    guarded_cas: bool,
    tenant_id: str = _SERVED_WDI_FIXTURE_TENANT_ID,
    cell_id: str = "cell-a",
    revised_source: bool = False,
    generation_cycle_repo_root: Path | None = None,
    artifact_store: artifacts.FileSystemCAS | None = None,
):
    if not guarded_cas:
        return await _run_actual_wdi_admits_delta_and_reenters_same_case_impl(
            tmp_path,
            monkeypatch,
            request,
            guarded_cas=False,
            tenant_id=tenant_id,
            cell_id=cell_id,
            revised_source=revised_source,
            generation_cycle_repo_root=generation_cycle_repo_root,
            artifact_store=artifact_store,
        )

    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        return await _run_actual_wdi_admits_delta_and_reenters_same_case_impl(
            tmp_path,
            monkeypatch,
            request,
            guarded_cas=True,
            tenant_id=tenant_id,
            cell_id=cell_id,
            revised_source=revised_source,
            generation_cycle_repo_root=generation_cycle_repo_root,
            artifact_store=artifact_store,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("guarded_cas", [False, True])
async def test_actual_wdi_admits_delta_and_reenters_same_case(
    tmp_path, monkeypatch, request, guarded_cas
):
    served = await _run_actual_wdi_admits_delta_and_reenters_same_case(
        tmp_path,
        monkeypatch,
        request,
        guarded_cas=guarded_cas,
    )
    assert served.reentry.new_cycle.value_port.authority_blockers == (
        "budget_exhausted_for_next_level",
    )
    assert served.reentry.new_cycle.value_port.selected_method_fqn is None


async def _admit_served_wdi_projection(
    tmp_path,
    monkeypatch,
    request,
    *,
    baseline_country_code="UKR",
    baseline_period_count: int = 3,
    tenant_id: str = _SERVED_WDI_FIXTURE_TENANT_ID,
    cell_id: str = "cell-a",
    revised_source: bool = False,
    artifact_store: artifacts.FileSystemCAS | None = None,
):
    """Create the real WDI admission and return its verified active projection."""
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionOverlay,
    )
    from tests._helpers import acquisition_chain, acquisition_production

    original_baseline = acquisition_production._baseline
    prepared_baselines: set[Path] = set()

    def baseline_with_owner_rows(repo_path, *, license_id="CC-BY-4.0"):
        expected_path = (Path(repo_path) / "catalog" / "catalog.duckdb").resolve()
        if expected_path in prepared_baselines:
            return expected_path
        baseline_path = original_baseline(repo_path, license_id=license_id)
        if baseline_period_count < 3:
            raise ValueError("fixture baseline period count must be at least three")
        if baseline_period_count == 3:
            base_observations = (
                ("fixture-government-balance-2021", 2021, -18.4),
                ("fixture-government-balance-2022", 2022, -17.8),
                ("fixture-government-balance-2023", 2023, -18.2),
            )
        else:
            first_year = 2024 - baseline_period_count
            base_observations = tuple(
                (
                    f"fixture-government-balance-{year}",
                    year,
                    -18.4 + (year - first_year) * 0.1,
                )
                for year in range(first_year, 2024)
            )
        with duckdb.connect(str(baseline_path)) as con:
            con.executemany(
                """
                INSERT INTO ds_observations (
                    observation_id, dataset_id, raw_variable, canonical_var,
                    country_code, year, value, condition_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        observation_id,
                        "acquisition.worldbank.government_balance",
                        "GC.BAL.CASH.GD.ZS",
                        "government.balance",
                        baseline_country_code,
                        year,
                        value,
                        '{"unit":"percent_gdp"}',
                    )
                    for observation_id, year, value in base_observations
                ],
            )
        acquisition_production.bind_fixture_l1_catalog_source(
            repo_path,
            baseline_path,
        )
        prepared_baselines.add(baseline_path.resolve())
        return baseline_path

    monkeypatch.setattr(acquisition_production, "_baseline", baseline_with_owner_rows)

    original_problem = cycle_fixtures._problem

    def government_balance_problem(problem_id="served_wdi_acquisition"):
        payload = original_problem(problem_id).model_dump(mode="json")
        payload["schema_version"] = "policyos.runtime.design_problem.v3"
        payload["problem_statement"] = (
            "Improve Ukraine's government cash balance using grounded evidence."
        )
        payload["jurisdiction_time"].update(
            {
                "region": "UKR",
                "valid_time": "2024",
                "policy_time": "2024",
                "data_time": "2024",
            }
        )
        payload["objectives"][0].update(
            {
                "objective_id": "government_balance",
                "description": "Improve government cash balance.",
                "metric_id": "government_balance",
            }
        )
        payload["outcome_of_interest"].update(
            {
                "target_variable": "government.balance",
                "metric_id": "government_balance",
                "estimand": "Government cash balance for Ukraine.",
            }
        )
        for lever in payload["candidate_lever_space"]["candidate_levers"]:
            lever["target_slot"] = "government.balance"
        return DesignProblem.model_validate(payload)

    monkeypatch.setattr(cycle_fixtures, "_problem", government_balance_problem)
    route_factory = acquisition_chain.AcquisitionWorldGrowthRoute

    def route_with_n8_test_budget(**kwargs):
        kwargs["reentry_budget_usd"] = Decimal("1.00")
        return route_factory(**kwargs)

    monkeypatch.setattr(acquisition_chain, "AcquisitionWorldGrowthRoute", route_with_n8_test_budget)

    projections = []
    original_projection_read = CatalogAcquisitionOverlay.read_activated_semantic_epoch_observations

    def capture_projection(self, **kwargs):
        projection = original_projection_read(self, **kwargs)
        projections.append(projection)
        return projection

    monkeypatch.setattr(
        CatalogAcquisitionOverlay,
        "read_activated_semantic_epoch_observations",
        capture_projection,
    )
    profile_calls = []
    profile_errors = []
    original_profile_load = RealValueOwnerGateway.load_value_data_profile

    def capture_profile(self, **kwargs):
        profile_calls.append(kwargs)
        try:
            profile = original_profile_load(self, **kwargs)
        except Exception as exc:
            profile_errors.append(f"{type(exc).__name__}: {exc}")
            raise
        return profile

    monkeypatch.setattr(RealValueOwnerGateway, "load_value_data_profile", capture_profile)

    served = await _run_actual_wdi_admits_delta_and_reenters_same_case(
        tmp_path,
        monkeypatch,
        request,
        guarded_cas=True,
        tenant_id=tenant_id,
        cell_id=cell_id,
        revised_source=revised_source,
        generation_cycle_repo_root=tmp_path / "wdi" / "repo",
        artifact_store=artifact_store,
    )

    assert len(projections) == 1
    return SimpleNamespace(
        served=served,
        projection=projections[0],
        profile_calls=profile_calls,
        profile_errors=profile_errors,
    )


@pytest.mark.asyncio
async def test_active_dataforge_row_builds_limited_candidate_world_with_source_time_unknown(
    tmp_path, monkeypatch, request
):
    """Owner-read-back WDI data reaches Foundry without inventing source time or SKG."""
    from copy import deepcopy
    from dataclasses import replace
    from datetime import UTC, datetime

    import numpy as np

    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.core.contracts.fabric import (
        DataSnapshot,
        data_snapshot_owner_input_requirements,
    )
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionOverlay,
        content_sha256,
    )
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotLineageError,
        validate_data_snapshot_owner_lineage,
    )
    from polisyos.runtime.quality.data_state_substrate import (
        ACQUIRED_DATA_STATE_LIMITATION_CODES,
        ControlledAcquisitionSlotBinding,
        build_acquired_observation_candidate_world,
        materialize_acquired_observation_snapshot,
        prepare_acquired_observation_snapshot,
    )
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import build_world_model_record
    from tests._helpers import world_model_record as wmr_fixture

    admitted = await _admit_served_wdi_projection(tmp_path, monkeypatch, request)
    served = admitted.served
    closure = served.closure
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
        case = served.case
        store = guard_runtime_cas(
            served.control._artifact_store.for_tenant(closure.tenant_id, closure.cell_id)
        )
        request.addfinalizer(store.close)
        growth = case.port.project_world_growth(closure)
        assert growth is not None

        observation_matches = tuple(
            row
            for row in admitted.projection.observations
            if row.observation.canonical_var == "government.balance"
        )
        assert len(observation_matches) == 1
        selected = observation_matches[0]
        overlay_path, _ = case.bridge._paths(growth.selection, create=False)
        overlay = CatalogAcquisitionOverlay(
            case.bridge.authority.baseline_path,
            overlay_path=overlay_path,
        )
        passport_payload = epoch_contract.load_verified_epoch_statement(
            store=store,
            ref=growth.activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
        passport = AdmissionPassport.model_validate(passport_payload)

        base_snapshot_ref = wmr_fixture._data_snapshot_ref(store)
        base_snapshot_payload = DataSnapshot.model_validate(
            from_canonical_bytes(store.get_bytes(base_snapshot_ref))
        )
        base_snapshot_manifest = store.get_manifest(base_snapshot_ref)
        base_snapshot_ref = store.put_json(
            base_snapshot_payload,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=base_snapshot_manifest.inputs,
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert base_snapshot_ref.manifest_profile_sha256 is not None
        registry = wmr_fixture._substrate_registry()
        registry_ref = persist_substrate_registry(store, registry)
        registry_bundle = build_default_registry_bundle(store)
        base_model_spec = wmr_fixture._model_spec(
            base_snapshot_ref,
            registry_bundle.bundle_ref,
        )
        wmr_fixture._write_fabric_world_snapshot(tmp_path)
        base_world = build_world_model_record(
            store,
            fabric_world_ref=wmr_fixture._fabric_ref(tmp_path),
            data_forge_snapshot_binding_path=wmr_fixture._write_data_forge_binding(tmp_path),
            data_snapshot_ref=base_snapshot_ref,
            model_spec=base_model_spec,
            skg_causal_prior_ref=wmr_fixture._skg_ref(tmp_path),
            substrate_registry=registry,
            region_or_jurisdiction="UA-30",
            population_scope="controlled_candidate_fixture",
            policy_domain="fiscal_credit",
            valid_time_scope="2026-05-24/2026-12-31",
            tx_time_scope="2026-05-24T12:00:00+00:00",
            resolution="firm_month",
            branch_mode=wmr_fixture.BranchMode.OBSERVED,
            policy_slot_ids=("agents.income", "government.balance"),
            producer_ref="test.world_model_record_builder",
            required_substrate_families=("firm_fundamentals",),
            substrate_registry_artifact_ref=registry_ref,
        )
        assert base_world.record.authority_status == "bound"
        assert float(np.asarray(base_world.bound_global_state.government_balance)) == 0.0

        slot_binding = ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id="government.balance",
            target_slot_id="government.balance",
        )
        transaction_time = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
        cas_files_before = frozenset(path for path in store.root.rglob("*") if path.is_file())
        prepared = prepare_acquired_observation_snapshot(
            store,
            base_data_snapshot_ref=base_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=case.bridge.authority,
            observation_id=selected.observation.observation_id,
            slot_binding=slot_binding,
            transaction_time=transaction_time,
        )
        assert frozenset(path for path in store.root.rglob("*") if path.is_file()) == (
            cas_files_before
        )
        assert not (tmp_path / "candidate-data-forge").exists()
        materialized = materialize_acquired_observation_snapshot(
            store,
            base_data_snapshot_ref=base_snapshot_ref,
            overlay=overlay,
            receipt_ref=growth.activation.overlay_admission_receipt_ref,
            passport=passport,
            authority=case.bridge.authority,
            observation_id=selected.observation.observation_id,
            slot_binding=slot_binding,
            workspace_dir=tmp_path / "candidate-data-forge",
            transaction_time=transaction_time,
            prepared=prepared,
        )
        assert materialized.observation_projection.projection_content_sha256 == (
            admitted.projection.projection_content_sha256
        )
        assert materialized.source_time_status == "not_established"
        built = build_acquired_observation_candidate_world(
            store,
            base_world_model=base_world.record,
            substrate_registry=registry,
            substrate_registry_artifact_ref=registry_ref,
            materialization=materialized,
            workspace_dir=tmp_path / "candidate-fabric-world",
            transaction_time=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
        )
        base_balance = np.asarray(base_world.bound_global_state.government_balance)
        bound_balance = np.asarray(built.world_model.bound_global_state.government_balance)
        assert base_balance.dtype == bound_balance.dtype == np.dtype(np.float32)
        assert base_balance.shape == bound_balance.shape == ()
        expected_bound_balance = np.asarray(
            selected.observation.value, dtype=base_balance.dtype
        ).item()
        assert bound_balance.item() == expected_bound_balance
        assert built.world_model.record.authority_status == "limited"
        assert set(ACQUIRED_DATA_STATE_LIMITATION_CODES).issubset(
            built.world_model.record.limitations.admissibility_blockers
        )
        assert (
            built.world_model.record.skg_causal_prior_ref == base_world.record.skg_causal_prior_ref
        )
        assert (
            built.world_model.record.skg_causal_prior_ref.source_data_snapshot_id
            == base_world.record.skg_causal_prior_ref.source_data_snapshot_id
        )

        snapshot = DataSnapshot.model_validate(
            from_canonical_bytes(store.get_bytes(materialized.data_snapshot_ref))
        )
        payload = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
        assert snapshot.source_lineage is not None
        assert snapshot.source_lineage.owner == "acquired_observation_overlay"
        assert snapshot.source_lineage.base_data_snapshot_ref == base_snapshot_ref
        assert materialized.data_snapshot_ref.manifest_profile_sha256 is not None
        assert snapshot.data_ref.manifest_profile_sha256 is not None
        assert snapshot.source_lineage.base_data_snapshot_ref.manifest_profile_sha256 is not None
        assert (
            snapshot.source_lineage.overlay_admission_receipt_ref.manifest_profile_sha256
            is not None
        )
        assert snapshot.source_lineage.passport_ref.manifest_profile_sha256 is not None
        validate_data_snapshot_owner_lineage(
            store, materialized.data_snapshot_ref, snapshot, candidate_only=True
        )

        legacy_payload = snapshot.model_dump(mode="json")
        legacy_payload.pop("source_lineage")
        legacy_snapshot = DataSnapshot.model_validate(legacy_payload)
        current_manifest = store.get_manifest_by_profile(
            materialized.data_snapshot_ref.artifact_id,
            materialized.data_snapshot_ref.manifest_profile_sha256,
        )
        legacy_snapshot_ref = store.put_json(
            legacy_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=list(current_manifest.inputs),
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        validate_data_snapshot_owner_lineage(
            store, legacy_snapshot_ref, legacy_snapshot, candidate_only=True
        )

        unmarked_owner_payload = deepcopy(payload)
        unmarked_owner_payload.pop("_policyos_acquisition")
        malformed_owner_payload_ref = store.put_json(
            unmarked_owner_payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.UnknownPayload",
                    version="1.0",
                ),
                inputs=(),
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        malformed_owner_snapshot = legacy_snapshot.model_copy(
            update={"data_ref": malformed_owner_payload_ref}
        )
        malformed_owner_snapshot_ref = store.put_json(
            malformed_owner_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=[
                    input_ref_from_artifact_ref(
                        malformed_owner_payload_ref,
                        role="data_ref",
                    )
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(DataSnapshotLineageError, match="owner_source_schema_invalid"):
            validate_data_snapshot_owner_lineage(
                store,
                malformed_owner_snapshot_ref,
                malformed_owner_snapshot,
            )

        relabeled_owner_payload_ref = store.put_json(
            payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.DataStatePayload",
                    version="policyos.runtime.data_state_substrate.v1",
                ),
                inputs=(),
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        relabeled_owner_snapshot = legacy_snapshot.model_copy(
            update={"data_ref": relabeled_owner_payload_ref}
        )
        relabeled_owner_snapshot_ref = store.put_json(
            relabeled_owner_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=[
                    input_ref_from_artifact_ref(
                        relabeled_owner_payload_ref,
                        role="payload.real_l4",
                    )
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(DataSnapshotLineageError, match="owner_parent_inputs_mismatch"):
            validate_data_snapshot_owner_lineage(
                store,
                relabeled_owner_snapshot_ref,
                relabeled_owner_snapshot,
            )

        profileless_marker_payload_ref = relabeled_owner_payload_ref.model_copy(
            update={"manifest_profile_sha256": None}
        )
        profileless_marker_snapshot = legacy_snapshot.model_copy(
            update={"data_ref": profileless_marker_payload_ref}
        )
        profileless_marker_snapshot_ref = store.put_json(
            profileless_marker_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=[
                    artifacts.input_ref_from_artifact_ref(
                        profileless_marker_payload_ref,
                        role="payload.real_l4",
                    )
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        marker_reads: list[object] = []
        marker_verifications: list[object] = []
        store_type = type(store)
        original_get_bytes = store_type.get_bytes
        original_verify = store_type.verify

        def _track_marker_reads(instance, ref):
            if instance is store:
                marker_reads.append(ref)
            return original_get_bytes(instance, ref)

        def _track_marker_verifications(instance, ref):
            if instance is store:
                marker_verifications.append(ref)
            return original_verify(instance, ref)

        monkeypatch.setattr(store_type, "get_bytes", _track_marker_reads)
        monkeypatch.setattr(store_type, "verify", _track_marker_verifications)
        with pytest.raises(DataSnapshotLineageError, match="owner_profile_unselected"):
            validate_data_snapshot_owner_lineage(
                store,
                profileless_marker_snapshot_ref,
                profileless_marker_snapshot,
            )
        assert marker_reads == []
        assert marker_verifications == []
        monkeypatch.setattr(store_type, "get_bytes", original_get_bytes)
        monkeypatch.setattr(store_type, "verify", original_verify)

        legacy_missing_passport_ref = store.put_json(
            legacy_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
                inputs=[
                    edge
                    for edge in current_manifest.inputs
                    if edge.role != "evidence.acquisition_passport"
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="owner_parent_inputs_mismatch"):
            validate_data_snapshot_owner_lineage(
                store,
                legacy_missing_passport_ref,
                legacy_snapshot,
            )

        persisted_selected = payload["acquisition"]["selected"]
        assert persisted_selected["value"] == selected.observation.value
        assert persisted_selected["observation_id"] == selected.observation.observation_id
        assert persisted_selected["row_content_sha256"] == selected.row_content_sha256
        persisted_admission = payload["_policyos_acquisition"]
        assert persisted_admission["selected_row_content_sha256"] == selected.row_content_sha256
        assert persisted_admission["projection_content_sha256"] == (
            admitted.projection.projection_content_sha256
        )
        assert persisted_admission["passport_ref"] == admitted.projection.passport_ref.model_dump(
            mode="json"
        )
        assert (
            persisted_admission["passport_content_sha256"]
            == (admitted.projection.passport_content_sha256)
            == content_sha256(passport_payload)
        )

        payload_manifest = store.get_manifest_by_profile(
            snapshot.data_ref.artifact_id,
            snapshot.data_ref.manifest_profile_sha256,
        )
        assert all(edge.manifest_profile_sha256 is not None for edge in payload_manifest.inputs)
        profileless_base_ref = base_snapshot_ref.model_copy(
            update={"manifest_profile_sha256": None}
        )
        profileless_payload = deepcopy(payload)
        profileless_payload["_policyos_acquisition"]["base_data_snapshot_ref"] = (
            profileless_base_ref.model_dump(mode="json")
        )
        profileless_payload_inputs = [
            input_ref_from_artifact_ref(
                profileless_base_ref,
                role="input.base_data_snapshot",
            ),
            *(edge for edge in payload_manifest.inputs if edge.role != "input.base_data_snapshot"),
        ]
        profileless_payload_ref = store.put_json(
            profileless_payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                    version="policyos.runtime.acquisition_data_state.v2",
                ),
                inputs=profileless_payload_inputs,
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        profileless_lineage = snapshot.source_lineage.model_copy(
            update={"base_data_snapshot_ref": profileless_base_ref}
        )
        profileless_snapshot = snapshot.model_copy(
            update={
                "data_ref": profileless_payload_ref,
                "source_lineage": profileless_lineage,
            }
        )
        profileless_snapshot_ref = store.put_json(
            profileless_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.3.0",
                ),
                inputs=[
                    input_ref_from_artifact_ref(ref, role=role)
                    for ref, role in data_snapshot_owner_input_requirements(profileless_snapshot)
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        payload_reads: list[object] = []
        verifications: list[object] = []
        store_type = type(store)
        original_get_bytes = store_type.get_bytes
        original_verify = store_type.verify

        def _track_payload_reads(instance, ref):
            if instance is store:
                payload_reads.append(ref)
            return original_get_bytes(instance, ref)

        def _track_verifications(instance, ref):
            if instance is store:
                verifications.append(ref)
            return original_verify(instance, ref)

        monkeypatch.setattr(store_type, "get_bytes", _track_payload_reads)
        monkeypatch.setattr(store_type, "verify", _track_verifications)
        with pytest.raises(DataSnapshotLineageError, match="owner_profile_unselected"):
            validate_data_snapshot_owner_lineage(
                store,
                profileless_snapshot_ref,
                profileless_snapshot,
            )
        assert payload_reads == []
        assert verifications == []
        monkeypatch.setattr(store_type, "get_bytes", original_get_bytes)
        monkeypatch.setattr(store_type, "verify", original_verify)
        assert payload_manifest.artifact_schema == wmr_fixture.SchemaInfo(
            name="polisyos.runtime.quality.AcquisitionDataStatePayload",
            version="policyos.runtime.acquisition_data_state.v2",
        )
        omitted_owner_payload = deepcopy(payload)
        omitted_owner_payload["_policyos_acquisition"].pop("base_data_snapshot_ref")
        omitted_payload_ref = store.put_json(
            omitted_owner_payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                    version="policyos.runtime.acquisition_data_state.v2",
                ),
                inputs=[
                    edge
                    for edge in payload_manifest.inputs
                    if edge.role != "input.base_data_snapshot"
                ],
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        omitted_owner_snapshot = snapshot.model_copy(update={"data_ref": omitted_payload_ref})
        omitted_parent_inputs = [
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in data_snapshot_owner_input_requirements(omitted_owner_snapshot)
        ]
        omitted_owner_snapshot_ref = store.put_json(
            omitted_owner_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.3.0",
                ),
                inputs=omitted_parent_inputs,
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(DataSnapshotLineageError, match="owner_refs_invalid"):
            validate_data_snapshot_owner_lineage(
                store,
                omitted_owner_snapshot_ref,
                omitted_owner_snapshot,
            )

        missing_base_ref = ArtifactRef.model_validate(
            base_snapshot_ref.model_dump(mode="json") | {"artifact_id": "sha256:" + "f" * 64}
        )
        missing_base_lineage = snapshot.source_lineage.model_copy(
            update={"base_data_snapshot_ref": missing_base_ref}
        )
        missing_base_payload = deepcopy(payload)
        missing_base_payload["_policyos_acquisition"]["base_data_snapshot_ref"] = (
            missing_base_ref.model_dump(mode="json")
        )
        missing_base_payload["_policyos_acquisition"]["base_data_snapshot_id"] = str(
            missing_base_ref.artifact_id
        )
        missing_base_payload_inputs = [
            input_ref_from_artifact_ref(
                missing_base_ref,
                role="input.base_data_snapshot",
            ),
            *(edge for edge in payload_manifest.inputs if edge.role != "input.base_data_snapshot"),
        ]
        missing_base_payload_ref = store.put_json(
            missing_base_payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                    version="policyos.runtime.acquisition_data_state.v2",
                ),
                inputs=missing_base_payload_inputs,
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        missing_base_snapshot = snapshot.model_copy(
            update={
                "data_ref": missing_base_payload_ref,
                "source_lineage": missing_base_lineage,
            }
        )
        missing_base_snapshot_inputs = [
            input_ref_from_artifact_ref(ref, role=role)
            for ref, role in data_snapshot_owner_input_requirements(missing_base_snapshot)
        ]
        missing_base_snapshot_ref = store.put_json(
            missing_base_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.3.0",
                ),
                inputs=missing_base_snapshot_inputs,
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(
            DataSnapshotLineageError,
            match="acquired_observation_base_snapshot_unavailable",
        ):
            validate_data_snapshot_owner_lineage(
                store,
                missing_base_snapshot_ref,
                missing_base_snapshot,
            )

        payload["acquisition"]["selected"].pop("value")
        removed_payload_ref = store.put_json(
            payload,
            wmr_fixture.PutOptions(
                kind="fabric.production_data_state_payload",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                    version="policyos.runtime.acquisition_data_state.v2",
                ),
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
        )
        removed_snapshot = snapshot.model_copy(update={"data_ref": removed_payload_ref})
        removed_snapshot_ref = store.put_json(
            removed_snapshot,
            wmr_fixture.PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=wmr_fixture.SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.3.0",
                ),
            ),
            canon_spec=wmr_fixture.CanonSpec(forbid_floats=False),
        )
        removed = replace(
            materialized,
            data_snapshot_ref=removed_snapshot_ref,
            payload_content_hash=str(removed_payload_ref.artifact_id),
        )
        with pytest.raises(ValueError, match="required source_path missing"):
            build_acquired_observation_candidate_world(
                store,
                base_world_model=base_world.record,
                substrate_registry=registry,
                substrate_registry_artifact_ref=registry_ref,
                materialization=removed,
                workspace_dir=tmp_path / "removed-candidate-fabric-world",
                transaction_time=datetime(2026, 10, 2, 12, 1, tzinfo=UTC),
            )


@pytest.mark.asyncio
async def test_served_wdi_admits_selected_row_but_n5_refusal_prevents_n8(
    tmp_path, monkeypatch, request
):
    """The served path admits WDI, then keeps N5/EvalSafety refusal explicit."""
    from polisyos.data_forge.domains.catalog.knowledge.overlay import content_sha256

    admitted = await _admit_served_wdi_projection(tmp_path, monkeypatch, request)
    served = admitted.served
    projection = admitted.projection

    assert served.case.bridge.artifact_store is served.control._artifact_store
    assert served.closure.design_problem.outcome_of_interest.target_variable == (
        "government.balance"
    )
    selected_rows = tuple(
        row.observation
        for row in projection.observations
        if row.observation.country_code == "UKR" and row.observation.year == 2024
    )
    assert len(selected_rows) == 1
    selected = selected_rows[0]
    assert projection.variable_id == "government.balance"
    assert projection.activation_state == "active"
    assert projection.predicate_provenance == "recomputed"
    assert projection.source_time_status == "not_established"
    assert selected.canonical_var == "government.balance"
    assert selected.value == pytest.approx(-17.1)
    projected_selected = tuple(
        row
        for row in projection.observations
        if row.observation.observation_id == selected.observation_id
    )
    assert len(projected_selected) == 1
    assert projected_selected[0].row_content_sha256
    assert projected_selected[0].row_content_sha256 == content_sha256(
        selected.model_dump(mode="json")
    )

    cycle = served.reentry.new_cycle
    assert cycle.simulation.status == "simulation_blocked"
    assert cycle.simulation.authority_blockers == (
        "joint_simulation_request_missing",
        "production_data_bundle_missing",
    )
    assert cycle.value_port.status == "value_blocked"
    assert cycle.value_port.authority_blockers == ("eval_safety_simulation_provenance_mismatch",)
    assert admitted.profile_calls == []
    assert admitted.profile_errors == []


@pytest.mark.asyncio
async def test_real_value_owner_gateway_projects_selected_wdi_iso3_row_into_iso2_profile(
    tmp_path, monkeypatch, request
):
    """Only the active verified WDI member may bridge ISO3 source to ISO2 profile."""
    admitted = await _admit_served_wdi_projection(
        tmp_path, monkeypatch, request, baseline_country_code="UA"
    )
    served = admitted.served
    projection = admitted.projection
    selected_rows = tuple(
        row.observation
        for row in projection.observations
        if row.observation.country_code == "UKR" and row.observation.year == 2024
    )
    assert len(selected_rows) == 1
    selected = selected_rows[0]
    gateway = RealValueOwnerGateway(
        repo_root=served.case.authority.repo_root,
        catalog_overlay_path=served.case.call_args["overlay_path"],
        artifact_store=served.case.bridge.artifact_store,
        activated_observation_projection=projection,
    )

    # This calls the real owner API directly with the verified active projection.
    # The three L1 ISO2 rows and selected WDI ISO3 row form one four-period profile.
    # The served N5/EvalSafety path remains a separate typed refusal witness.
    from polisyos.runtime.quality.generation_cycle import _resolve_owner_scope_region

    assert _resolve_owner_scope_region("UKR", owner_access_ref="test://scope") == "UA"
    assert selected.country_code == "UKR"
    overlay_path = served.case.call_args["overlay_path"]
    with duckdb.connect(str(overlay_path), read_only=True) as con:
        marker_snapshot = con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
            "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
            [projection.epoch_id],
        ).fetchone()
    assert marker_snapshot is not None
    with duckdb.connect(str(overlay_path)) as con:
        con.execute(
            "INSERT INTO ds_observations (observation_id, dataset_id, raw_variable, "
            "canonical_var, country_code, year, value, condition_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                "unselected-ukr-collision-2025",
                selected.dataset_id,
                "GC.BAL.CASH.GD.ZS",
                "government.balance",
                "UKR",
                2025,
                -999.0,
                '{"unit":"percent_gdp"}',
            ],
        )
    with duckdb.connect(str(overlay_path), read_only=True) as con:
        assert (
            con.execute(
                "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
                "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
                [projection.epoch_id],
            ).fetchone()
            == marker_snapshot
        )
    from polisyos.core.security.tenant_context import tenant_scope

    with tenant_scope(
        None,
        tenant_id=served.closure.tenant_id,
        cell_id=served.closure.cell_id,
    ):
        profile = gateway.load_value_data_profile(
            candidate=object(),
            problem=served.closure.design_problem_basis,
            world_record=object(),
        )
    assert profile.unit_count == 1
    assert profile.period_count == 4
    assert profile.owner_row_count == 4
    selected_profile_rows = tuple(row for row in profile.rows if row.period_id == 2024)
    assert len(selected_profile_rows) == 1
    selected_profile_row = selected_profile_rows[0]
    assert selected_profile_row.unit_id == "UA"
    assert selected_profile_row.outcome_value == pytest.approx(selected.value)
    assert selected_profile_row.source_row_content_hashes == (
        gy_content_hash(
            {
                "outcome": "government.balance",
                "unit_id": "UA",
                "period_id": 2024,
                "value": selected.value,
                "dataset_id": selected.dataset_id,
                "observation_id": selected.observation_id,
                "measurement_unit": "percent_gdp",
            }
        ),
    )
    assert all(row.period_id != 2025 for row in profile.rows)

    # A content-valid CAS passport for a different connector must not authorize
    # ISO3→ISO2 normalization, even when the active-row and epoch markers remain.
    from polisyos.core import contracts
    from polisyos.fabric.data_plane import canonical_json_bytes, content_sha256

    store = served.case.bridge.artifact_store
    with tenant_scope(
        None,
        tenant_id=served.closure.tenant_id,
        cell_id=served.closure.cell_id,
    ):
        wrong_passport_payload = contracts.epoch.load_verified_epoch_statement(
            store=store,
            ref=projection.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
        wrong_registration = dict(wrong_passport_payload["registration"])
        wrong_registration["connector_id"] = "unregistered.country-code-source"
        wrong_passport_payload["registration"] = wrong_registration
        wrong_identity = {
            key: value
            for key, value in wrong_passport_payload.items()
            if key not in {"passport_id", "status", "rejection_codes"}
        }
        wrong_passport_payload["passport_id"] = "passport:" + content_sha256(wrong_identity)
        encoded_passport = canonical_json_bytes(wrong_passport_payload)
        wrong_passport_ref = store.put_bytes(
            len(encoded_passport).to_bytes(8, "big") + encoded_passport,
            artifacts.PutOptions(
                kind="epoch.acquisition_passport_snapshot",
                media_type="application/vnd.polisyos.epoch+json",
            ),
        )
        wrong_projection = type(projection).issue(
            receipt_ref=projection.receipt_ref,
            receipt_content_sha256=projection.receipt_content_sha256,
            passport_ref=wrong_passport_ref,
            passport_content_sha256=content_sha256(wrong_passport_payload),
            variable_id=projection.variable_id,
            epoch_id=projection.epoch_id,
            passport_id=wrong_passport_payload["passport_id"],
            admission_content_sha256=projection.admission_content_sha256,
            observations=tuple(row.observation for row in projection.observations),
        )
        wrong_registration_gateway = RealValueOwnerGateway(
            repo_root=served.case.authority.repo_root,
            catalog_overlay_path=overlay_path,
            artifact_store=store,
            activated_observation_projection=wrong_projection,
        )
        with pytest.raises(ValueOwnerAccessError) as wrong_registration_refusal:
            wrong_registration_gateway.load_value_data_profile(
                candidate=object(),
                problem=served.closure.design_problem_basis,
                world_record=object(),
            )
    assert (
        wrong_registration_refusal.value.code
        == "acquire_data:active_observation_country_scheme_not_established"
    )

    with duckdb.connect(str(overlay_path)) as con:
        physical_before = con.execute(
            "SELECT observation_id, value FROM ds_observations WHERE observation_id = ?",
            [selected.observation_id],
        ).fetchone()
        assert physical_before == (selected.observation_id, selected.value)
        con.execute(
            "UPDATE ds_observations SET value = ? WHERE observation_id = ?",
            [selected.value + 0.25, selected.observation_id],
        )
    with duckdb.connect(str(overlay_path), read_only=True) as con:
        assert (
            con.execute(
                "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
                "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
                "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
                "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
                [projection.epoch_id],
            ).fetchone()
            == marker_snapshot
        )

    with (
        tenant_scope(
            None,
            tenant_id=served.closure.tenant_id,
            cell_id=served.closure.cell_id,
        ),
        pytest.raises(ValueOwnerAccessError) as after_tamper,
    ):
        gateway.load_value_data_profile(
            candidate=object(),
            problem=served.closure.design_problem_basis,
            world_record=object(),
        )
    assert after_tamper.value.code == "acquire_data:active_observation_projection_drift"
    assert len(admitted.profile_calls) == 3
    assert len(admitted.profile_errors) == 2
    assert "registered WDI ISO3 source code" in admitted.profile_errors[0]
    assert (
        "N8 query rows differ from the Data Forge verified active member"
        in (admitted.profile_errors[1])
    )


@pytest.mark.asyncio
async def test_both_reentry_paths_keep_empty_selection_refusal(tmp_path, monkeypatch):
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthConfig

    case.bridge.config = AcquisitionWorldGrowthConfig()
    result = case.port.execute(closure)
    assert result.disposition == "quarantined_no_growth"
    assert result.admitted_observation_delta == 0
    assert case.appointments == []
    for action in (
        lambda: case.port.reenter(closure, result),
        lambda: case.port.resume_reentry(closure, result.owner_receipt_refs),
    ):
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_evidence_not_admitted"
        ):
            action()


@pytest.mark.asyncio
async def test_default_wdi_cost_selection_is_absent_before_served_execution(tmp_path):
    control = _build_control_service(tmp_path / "control")
    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        await persist_wdi_route(control)


@pytest.mark.asyncio
async def test_deferred_admission_refuses_unknown_outcome_and_missing_negative(
    tmp_path, monkeypatch
):
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    negative = case.port.execute(closure)
    assert negative.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    fetched = tuple(case.transport_calls)
    pointer = case.bridge._growth_pointer(case.selected)
    fence = pointer.with_suffix(".admission.started")
    fence.write_text("unknown outcome; fixture before any deferred effect")
    try:
        assert case.bridge.has_admission_attempt(closure)
        assert not case.bridge.has_deferred_admission(closure)
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"
        ):
            case.port.execute(closure)
    finally:
        fence.unlink()  # Restore this fixture before any actual deferred effect.
    ref = negative.owner_receipt_refs[-1]
    blob, _ = control._artifact_store._paths(artifacts.ArtifactID.model_validate(ref))
    raw = blob.read_bytes()
    blob.unlink()
    try:
        assert case.bridge.has_admission_attempt(closure)
        assert not case.bridge.has_deferred_admission(closure)
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"
        ):
            case.port.execute(closure)
    finally:
        blob.write_bytes(raw)
    assert tuple(case.transport_calls) == fetched
    assert case.bridge.has_deferred_admission(closure)


@pytest.mark.asyncio
async def test_current_world_growth_receipt_rejects_wrong_schema_with_markers_intact(
    tmp_path, monkeypatch, request
):
    """A wrong schema cannot pass while the live action/CAS/event markers stay intact."""
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthReceipt,
    )

    served = await _run_actual_wdi_admits_delta_and_reenters_same_case(
        tmp_path,
        monkeypatch,
        request,
        guarded_cas=False,
    )
    control = served.control
    closure = served.closure
    sink = control.acquisition_route_sink
    snapshot = sink.current_action_outcome(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
    )
    assert snapshot is not None
    assert snapshot.selection_phase is not None
    assert snapshot.selection_phase_ref is not None
    assert len(snapshot.selection_phase.owner_receipt_refs) == 1
    growth_ref = snapshot.selection_phase.owner_receipt_refs[0]
    owner_manifest = control._artifact_store.get_manifest(growth_ref)
    assert owner_manifest.kind == "runtime_quality.acquisition_world_growth_receipt"
    assert owner_manifest.artifact_schema is not None
    assert owner_manifest.artifact_schema.name == AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME
    assert owner_manifest.artifact_schema.version == "1.1"
    sink.verify_action_head(snapshot.head)

    import polisyos.runtime.http.services.control.run_lifecycle as run_lifecycle_module

    read_manifest = run_lifecycle_module.read_core_manifest_profile
    forged_manifests = []

    def wrong_schema_only(store, ref):
        manifest, *remaining = read_manifest(store, ref)
        if ref != growth_ref:
            return (manifest, *remaining)
        assert manifest.artifact_schema is not None
        wrong_schema = manifest.artifact_schema.model_copy(
            update={"name": "polisyos.runtime.AcquisitionWorldGrowthReceipt"}
        )
        forged = manifest.model_copy(update={"artifact_schema": wrong_schema})
        forged_manifests.append(forged)
        return (forged, *remaining)

    with monkeypatch.context() as forged_readback:
        forged_readback.setattr(
            run_lifecycle_module, "read_core_manifest_profile", wrong_schema_only
        )
        with pytest.raises(ValueError, match="acquisition_action_owner_receipt_binding_mismatch"):
            sink.verify_action_head(snapshot.head)

    assert len(forged_manifests) == 1
    assert (
        forged_manifests[0].model_copy(update={"artifact_schema": owner_manifest.artifact_schema})
        == owner_manifest
    )
    sink.verify_action_head(snapshot.head)
    assert (
        control._artifact_store.get_manifest(growth_ref).artifact_schema.name
        == AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME
    )
