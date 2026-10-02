"""Actual WDI/default executor and native owner chain through same-case re-entry."""

import hashlib
import json
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
from tests._helpers.acquisition_chain import make_wdi_port_case
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service
from tests.unit.runtime.quality import test_generation_cycle as cycle_fixtures


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

    same_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(
            same_basis_view
        )
    )
    revised_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(
            revised_basis_view
        )
    )

    assert (same_constraints.country_code, same_constraints.start_year, same_constraints.end_year) == (
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
    committed = case.port.execute(closure)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store

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
        assert con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref "
            "FROM acquisition_epochs WHERE epoch_id = ?",
            [selected.epoch_id],
        ).fetchone() == owner_markers
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
    assert closure.design_problem_basis == closure.generation_run.cycles[0].revision_request.revised_problem
    assert closure.generation_run.cycles[1].design_problem_basis_ref == basis

    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    committed = case.port.execute(closure)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store

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
    # A revised-source route does not currently resolve to one costed route. Isolate
    # the live binding owner with a typed S/B view; this is not a served N6 producer.
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


async def _run_actual_wdi_admits_delta_and_reenters_same_case(
    tmp_path,
    monkeypatch,
    request,
    *,
    guarded_cas: bool,
    tenant_id: str = "tenant-a",
    cell_id: str = "cell-a",
):
    # This is a downstream owner-chain witness: persist_wdi_route seeds its
    # run through for_contract_testing. The protected-intent production
    # recursive-leaf boundary is exercised by the paired unit test.
    if guarded_cas:
        from polisyos.runtime.http.resilience import guard_runtime_cas
        from tests.unit.runtime.http import test_control_service_di as control_fixture

        def build_guarded_store(path):
            store = guard_runtime_cas(artifacts.FileSystemCAS(path))
            request.addfinalizer(store.close)
            return store

        monkeypatch.setattr(control_fixture, "FileSystemCAS", build_guarded_store)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(
        control,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
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
    result = case.port.execute(closure)
    assert result.disposition == "world_committed"
    assert tuple(case.transport_calls) == fetched
    assert all(control._artifact_store.get_bytes(ref) == raw for ref, raw in original_bytes.items())
    assert result.admitted_observation_delta == 1
    assert len(case.transport_calls) > 0
    assert len(case.appointments) == 1
    before = tuple(case.transport_calls)
    # Lose only the post-activation acknowledgement; recover from native owner bytes.
    case.bridge._growth_pointer(case.selected).unlink()
    assert case.port.recover_owned_result(closure) == result
    assert tuple(case.transport_calls) == before
    assert case.port.project_world_growth(closure).admitted_observation_delta == 1
    ref = case.port.reenter(closure, result)
    receipt = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(ref))
    )
    assert receipt.source_run_id == closure.generation_run.run_id
    assert receipt.design_problem_ref == closure.design_problem_ref
    assert receipt.new_cycle.cycle_index == closure.source_cycle.cycle_index + 1
    before = tuple(case.transport_calls)
    assert case.port.resume_reentry(closure, result.owner_receipt_refs) == ref
    assert case.port.recover_owned_result(closure) == result
    assert tuple(case.transport_calls) == before
    with pytest.raises(AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"):
        case.port.execute(closure)
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
    return SimpleNamespace(
        control=control,
        closure=closure,
        case=case,
        committed=result,
        reentry=receipt,
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
    tmp_path, monkeypatch, request, *, baseline_country_code="UKR"
):
    """Create the real WDI admission and return its verified active projection."""
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionOverlay,
    )
    from polisyos.runtime.quality.substrate_registry import DEFAULT_L1_DCAT_PATH
    from tests._helpers import acquisition_chain
    from tests.unit.data_forge.domains.catalog.knowledge import (
        test_acquisition_authority as authority_fixture,
    )

    original_baseline = authority_fixture._baseline

    def baseline_with_owner_rows(repo_path, *, license_id="CC-BY-4.0"):
        baseline_path = original_baseline(repo_path, license_id=license_id)
        base_observations = (
            ("fixture-government-balance-2021", 2021, -18.4),
            ("fixture-government-balance-2022", 2022, -17.8),
            ("fixture-government-balance-2023", 2023, -18.2),
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
        l1_path = repo_path / DEFAULT_L1_DCAT_PATH
        l1_path.parent.mkdir(parents=True, exist_ok=True)
        l1_path.symlink_to(baseline_path)
        digest = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
        manifest_path = repo_path / "production_data" / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "kind": "policyos.production_data_root",
                    "fixture_catalog": {
                        "path": DEFAULT_L1_DCAT_PATH.as_posix(),
                        "sha256": digest,
                    },
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return baseline_path

    monkeypatch.setattr(authority_fixture, "_baseline", baseline_with_owner_rows)

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

    monkeypatch.setattr(
        acquisition_chain, "AcquisitionWorldGrowthRoute", route_with_n8_test_budget
    )

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
    from dataclasses import replace
    from datetime import UTC, datetime

    import numpy as np

    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionOverlay,
        content_sha256,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.data_state_substrate import (
        ACQUIRED_DATA_STATE_LIMITATION_CODES,
        ControlledAcquisitionSlotBinding,
        build_acquired_observation_candidate_world,
        materialize_acquired_observation_snapshot,
    )
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import build_world_model_record
    from tests.unit.runtime.quality import test_world_model_record as wmr_fixture

    admitted = await _admit_served_wdi_projection(tmp_path, monkeypatch, request)
    served = admitted.served
    case = served.case
    closure = served.closure
    store = served.control._artifact_store
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

    materialized = materialize_acquired_observation_snapshot(
        store,
        base_data_snapshot_ref=base_snapshot_ref,
        overlay=overlay,
        receipt_ref=growth.activation.overlay_admission_receipt_ref,
        passport=passport,
        authority=case.bridge.authority,
        observation_id=selected.observation.observation_id,
        slot_binding=ControlledAcquisitionSlotBinding(
            profile_selection_ref="sha256:" + "7" * 64,
            canonical_variable_id="government.balance",
            target_slot_id="government.balance",
        ),
        workspace_dir=tmp_path / "candidate-data-forge",
        transaction_time=datetime(2026, 10, 2, 12, 0, tzinfo=UTC),
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
    assert built.world_model.record.skg_causal_prior_ref == base_world.record.skg_causal_prior_ref
    assert (
        built.world_model.record.skg_causal_prior_ref.source_data_snapshot_id
        == base_world.record.skg_causal_prior_ref.source_data_snapshot_id
    )

    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(materialized.data_snapshot_ref))
    )
    payload = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
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
    assert persisted_admission["passport_content_sha256"] == (
        admitted.projection.passport_content_sha256
    ) == content_sha256(passport_payload)
    payload["acquisition"]["selected"].pop("value")
    removed_payload_ref = store.put_json(
        payload,
        wmr_fixture.PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=wmr_fixture.SchemaInfo(
                name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                version="policyos.runtime.acquisition_data_state.v1",
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
                version="0.2.0",
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
        row for row in projection.observations if row.observation.observation_id == selected.observation_id
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
    assert cycle.value_port.authority_blockers == (
        "eval_safety_simulation_provenance_mismatch",
    )
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
        assert con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
            "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
            [projection.epoch_id],
        ).fetchone() == marker_snapshot
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
    selected_profile_rows = tuple(
        row for row in profile.rows if row.period_id == 2024
    )
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
        wrong_passport_payload["passport_id"] = (
            "passport:" + content_sha256(wrong_identity)
        )
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
        assert con.execute(
            "SELECT passport_id, admission_content_sha256, admitted_observation_count, "
            "pending_overlay_receipt_ref, admitted_boundary_evidence_ref, "
            "semantic_epoch_production_receipt_ref, activated_overlay_receipt_ref, "
            "epoch_activation_state FROM acquisition_epochs WHERE epoch_id = ?",
            [projection.epoch_id],
        ).fetchone() == marker_snapshot

    with tenant_scope(
        None,
        tenant_id=served.closure.tenant_id,
        cell_id=served.closure.cell_id,
    ), pytest.raises(ValueOwnerAccessError) as after_tamper:
        gateway.load_value_data_profile(
            candidate=object(),
            problem=served.closure.design_problem_basis,
            world_record=object(),
        )
    assert after_tamper.value.code == "acquire_data:active_observation_projection_drift"
    assert len(admitted.profile_calls) == 3
    assert len(admitted.profile_errors) == 2
    assert "registered WDI ISO3 source code" in admitted.profile_errors[0]
    assert "N8 query rows differ from the Data Forge verified active member" in (
        admitted.profile_errors[1]
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
