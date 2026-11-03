"""N7 ACQ-01 bridge regressions with compiler-owned WDI evidence."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.mark.parametrize(
    ("case", "expected_family", "compiled_geography", "expected_refusal"),
    [
        ("positive", "gdp_per_capita", "DE", None),
        (
            "wrong_metric",
            "unemployment_rate",
            "DE",
            "measurement_requirement_metric_mismatch",
        ),
        ("wrong_scope", "gdp_per_capita", "PL", "measurement_requirement_scope_mismatch"),
        ("missing_compiler_report", "gdp_per_capita", "DE", "n7_compiler_report_readback_failed"),
    ],
    ids=("positive", "wrong-metric", "wrong-scope", "removed-compiler-cas"),
)
@pytest.mark.asyncio
async def test_n7_controller_rebuilds_wdi_context_from_persisted_compiler_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_family: str,
    compiled_geography: str,
    expected_refusal: str | None,
) -> None:
    """The N7 controller consumes its persisted compiler report and preserves limits."""

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.control import NaturalLanguageRunRequest
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionReceipt,
        RecordedAcquisitionOwnerGateway,
        l1_variable_availability_requirement_gap,
        validate_persisted_data_requirement_compilation_report,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner
    from polisyos.runtime.quality.data_forge_binding import bind_measurement_root_execution_scope
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from polisyos.runtime.quality.design_problem import (
        DESIGN_PROBLEM_V3_SCHEMA_VERSION,
        DesignProblem,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        ValuePortObservation,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from tests._helpers.runtime_http import _build_control_service, _valid_intake_for_mode
    from tests.unit.remediation.test_acq_01 import (
        _compiled_data_requirement_spec,
        _ContextRecordingSimulation,
        _fixture_candidate,
        _FixtureAcquisitionGrounding,
        _problem,
        _published_worldbank_owner,
        _real_acq01_before_context,
        _real_acq01_route,
    )
    from tests.unit.runtime.http.control_service_test_support import bound_nl_authorization_proof
    from tests.unit.runtime.http.test_control_service_di import _fixture_claims

    problem_id = f"acq01_compiled_wdi_{case}"
    scope_profile = {
        "profile_id": f"{problem_id}-scope",
        "jurisdiction": compiled_geography,
        "time_window": {"start": "2020", "end": "2020"},
        "time_role": "observation_time",
        "granularity": "annual",
    }
    problem = _problem(
        problem_id=problem_id,
        statement="Examine synthetic GDP per capita observations for German firms in 2020.",
        domain="fiscal_credit",
        runtime_hints={"n7_scope_profile": scope_profile},
    )
    lever = problem.candidate_lever_space.candidate_levers[0].model_copy(
        update={"target_slot": "agents.income"}
    )
    problem = problem.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_V3_SCHEMA_VERSION,
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={"region": "DE", "valid_time": "2020", "data_time": "2020"}
            ),
            "candidate_lever_space": problem.candidate_lever_space.model_copy(
                update={"candidate_levers": [lever]}
            ),
        }
    )
    problem = DesignProblem.model_validate(problem.model_dump(mode="python"))
    assert "n7_data_requirement_specs" not in problem.runtime_hints

    tenant_id, cell_id = "tenant-fixture", "cell-fixture"
    store = FileSystemCAS(tmp_path / "cas").for_tenant(tenant_id, cell_id)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        service = _build_control_service(tmp_path / "control", artifact_store=store)

    try:
        request = NaturalLanguageRunRequest(
            request=problem.nl_provenance.raw_request,
            llm_model="simulated-qwen",
            context={
                "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                    mode="json"
                )
            },
            max_iterations=1,
        )
        claims = _fixture_claims()
        launch = await service.launch_nl_run(
            request,
            principal=RuntimePrincipal.from_user_claims(claims),
            authorization_proof=bound_nl_authorization_proof(claims, request),
        )
        lease = service._control_store.lease_next_job(
            worker_id="acq01-compiled-wdi", lease_seconds=600
        )
        assert lease is not None and lease.job_id == launch.job_id

        with service._control_store.job_execution_fence(
            job_id=lease.job_id, worker_id=lease.lease_owner, attempt=lease.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                payload = service._load_control_nl_job_payload(admission.job)
                payload = service._payload_for_execution_scope(
                    payload, job=admission.job, execution_scope=admission.scope
                )
                manifest_ref, manifest = service._resolve_capability_manifest_for_execution(
                    job=admission.job,
                    admission=admission,
                    execution_scope=admission.scope,
                )
                intent_binding = service._bind_control_job_execution_intent(
                    job=admission.job,
                    admission=admission,
                    execution_scope=admission.scope,
                    payload=payload,
                    capability_manifest_ref=manifest_ref,
                    capability_manifest=manifest,
                )
                assert intent_binding is not None
                verified_scope = intent_binding["_verified_nl_job_scope"]
                assert verified_scope._was_issued_by_verified_nl_execution_owner
                execution_scope_binding = bind_measurement_root_execution_scope(
                    admission=admission,
                    job=admission.job,
                    execution_scope=admission.scope,
                )
                assert execution_scope_binding.authority_eligible

                prior_context = _real_acq01_before_context(
                    tmp_path / "prior-context", problem, artifact_store=store
                )
                candidate = _fixture_candidate(
                    problem,
                    world_ref=prior_context.world_model_record.world_model_record_id,
                    target_world_slots=("agents.income",),
                    candidate_id="candidate_metric_test",
                )
                compiler_spec = _compiled_data_requirement_spec(problem, family=expected_family)
                context_owner = CycleSubstrateContextArtifactOwner(
                    store=store, control_store=service._control_store
                )

                with (
                    _published_worldbank_owner(
                        tmp_path / "published-wdi", monkeypatch, artifact_store=store
                    ) as selected_owner,
                    _real_acq01_route(
                        tmp_path / "selected-wdi-route",
                        problem,
                        candidate_content_hash=candidate.atom.content_hash,
                        requirement_ref=compiler_spec.requirement_id,
                        target_world_slots=("agents.income",),
                        artifact_store=store,
                        execution_scope_binding=execution_scope_binding,
                        prior_context=prior_context,
                        selected_metric="gdp_per_capita",
                        selected_owner=selected_owner,
                    ) as route,
                ):
                    gateway = RecordedAcquisitionOwnerGateway(
                        artifacts_by_requirement={
                            compiler_spec.requirement_id: route.owner_artifact,
                        }
                    )
                    gateway.catalog = route.catalog
                    gateway.providers = route.providers

                    class _CandidatePort:
                        async def __call__(self, current: Any, *, cycle_index: int) -> Any:
                            del current, cycle_index
                            return SimpleNamespace(
                                status="generated",
                                candidates=(candidate,),
                                surrogate_rankings=(
                                    SimpleNamespace(
                                        candidate_id=candidate.candidate_id,
                                        score=0.2,
                                        voi_estimate=0.2,
                                    ),
                                ),
                                grounding_dispositions=(),
                            )

                    class _AvailabilityValuePort:
                        def __call__(
                            self,
                            *,
                            candidate: Any,
                            problem: Any,
                            **_kwargs: Any,
                        ) -> ValuePortObservation:
                            gap = l1_variable_availability_requirement_gap(
                                candidate_id=candidate.candidate_id,
                                candidate_content_hash=candidate.atom.content_hash,
                                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                                availability=L1VariableAvailability(
                                    variable_id=expected_family,
                                    status="unavailable",
                                    dataset_count=0,
                                    metric_binding_count=0,
                                    observation_count=0,
                                    coverage_ref=(
                                        "repo://production_data/dataset_catalog.duckdb"
                                        f"#variable/{expected_family}"
                                    ),
                                ),
                                authority_level=(
                                    problem.authority_profile.requested_authority_level
                                ),
                            )
                            driver = f"acquire_data:{expected_family}"
                            return ValuePortObservation(
                                status="value_blocked",
                                candidate_id=candidate.candidate_id,
                                authority_blockers=(driver,),
                                reason=("The selected L1 owner reports the variable unavailable."),
                                decision_grade="blocked",
                                acquisition_requirement=gap,
                            )

                    simulation = _ContextRecordingSimulation()
                    controller = GenerationCycleController(
                        generation_port=_CandidatePort(),
                        grounding_port=_FixtureAcquisitionGrounding(
                            issue_code=f"acquire_data:{expected_family}"
                        ),
                        simulation_port=simulation,
                        value_port=_AvailabilityValuePort(),
                        acquisition_owner_gateway=gateway,
                        repo_root=tmp_path,
                        artifact_store=store,
                        cycle_substrate_context=prior_context,
                        candidate_cycle_context_artifact_owner=context_owner,
                        candidate_cycle_verified_nl_job_scope=verified_scope,
                        measurement_root_execution_binding=execution_scope_binding,
                        authority_scope="contract_testing",
                    )
                    simulation.controller = controller
                    prior_context_ref = (
                        controller._persist_resolve_and_bind_cycle_substrate_context(
                            prior_context,
                            previous_problem=problem,
                            problem=problem,
                        )
                    )
                    prior_readback = context_owner.resolve_for_current_job(
                        prior_context_ref,
                        problem=problem,
                        repo_root=tmp_path,
                        verified_nl_job_scope=verified_scope,
                    )
                    assert prior_readback.context == prior_context

                    observed_reentry_errors: list[GenerationCycleError] = []
                    if case == "missing_compiler_report":
                        original_reentry = controller._reenter_cycle_after_n7_acquisition
                        original_get_bytes = type(store).get_bytes

                        def reenter_without_compiler_report(
                            current_problem: Any,
                            **kwargs: Any,
                        ) -> Any:
                            receipt = kwargs["acquisition_receipt"]
                            basis_binding = receipt.requirement_basis_binding
                            assert basis_binding is not None
                            report_ref = basis_binding.compiler_report_ref
                            report_payload = load_core_json_artifact(store, report_ref)
                            removed_report["ref"] = report_ref
                            removed_report["payload"] = report_payload

                            def get_bytes_without_report(
                                selected_store: Any,
                                ref: Any,
                                *args: Any,
                                **read_kwargs: Any,
                            ) -> bytes:
                                selected_id = getattr(ref, "artifact_id", ref)
                                if selected_store is store and str(selected_id) == str(
                                    report_ref.artifact_id
                                ):
                                    raise FileNotFoundError("compiler report CAS bytes removed")
                                return original_get_bytes(selected_store, ref, *args, **read_kwargs)

                            monkeypatch.setattr(type(store), "get_bytes", get_bytes_without_report)
                            try:
                                return original_reentry(current_problem, **kwargs)
                            except GenerationCycleError as exc:
                                observed_reentry_errors.append(exc)
                                raise

                        removed_report: dict[str, Any] = {}
                        monkeypatch.setattr(
                            controller,
                            "_reenter_cycle_after_n7_acquisition",
                            reenter_without_compiler_report,
                        )
                    elif case in {"wrong_metric", "wrong_scope"}:
                        original_rebuild = controller._rebuild_n7_acq01_route_context

                        def capture_rebuild_error(*args: Any, **kwargs: Any) -> Any:
                            try:
                                return original_rebuild(*args, **kwargs)
                            except GenerationCycleError as exc:
                                observed_reentry_errors.append(exc)
                                raise

                        monkeypatch.setattr(
                            controller,
                            "_rebuild_n7_acq01_route_context",
                            capture_rebuild_error,
                        )

                    run = await controller.run(
                        problem,
                        budget_state=BudgetState(
                            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
                        ),
                        min_cycles=1,
                        max_cycles=1,
                    )
                    assert len(run.acquisition_receipts) == 1
                    receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
                    assert len(receipt.owner_artifacts) == 1
                    assert (
                        receipt.owner_artifacts[0].content_hash == route.owner_artifact.content_hash
                    )
                    assert (
                        receipt.owner_artifacts[0].requirement_ref == compiler_spec.requirement_id
                    )
                    assert receipt.requirement_basis_binding is not None
                    assert route.owner_artifact.requirement_ref == compiler_spec.requirement_id
                    assert (
                        receipt.requirement_basis_binding.scenario_id == problem.design_problem_id
                    )
                    assert receipt.requirement_basis_binding.compiler_report_ref.kind == (
                        "runtime.data_requirement_compilation_report"
                    )

                    if case == "missing_compiler_report":
                        assert removed_report
                        persisted_report = DataRequirementCompilationReport.model_validate(
                            removed_report["payload"]
                        )
                        binding = receipt.requirement_basis_binding
                        report_ref = removed_report["ref"]
                        assert report_ref == binding.compiler_report_ref
                        assert (
                            persisted_report.metadata.get("producer") == "data_requirement_compiler"
                        )
                        assert persisted_report.scenario_id == binding.scenario_id
                        assert persisted_report.producer_report_ref == binding.producer_report_ref
                        assert persisted_report.input_content_hash == binding.input_content_hash
                        assert persisted_report.requirement_basis == binding.resolution
                        assert (
                            tuple(spec.model_dump(mode="json") for spec in persisted_report.specs)
                            == receipt.compiled_requirement_specs
                        )
                        assert run.blocked_reason == "n7_compiler_report_replay_mismatch"
                        assert len(observed_reentry_errors) == 1
                        assert expected_refusal in str(observed_reentry_errors[0])
                        assert len(simulation.observations) == 1
                        assert controller._candidate_cycle_context_job_ref == prior_context_ref
                        assert controller._cycle_substrate_context is prior_context
                        assert validate_persisted_data_requirement_compilation_report(
                            store, receipt.requirement_basis_binding
                        )
                    else:
                        compiler_report_payload = load_core_json_artifact(
                            store, receipt.requirement_basis_binding.compiler_report_ref
                        )
                        compiler_report = DataRequirementCompilationReport.model_validate(
                            compiler_report_payload
                        )
                        assert (
                            compiler_report.metadata.get("producer") == "data_requirement_compiler"
                        )
                        assert compiler_report.scenario_id == problem.design_problem_id
                        binding = receipt.requirement_basis_binding
                        assert compiler_report.producer_report_ref == binding.producer_report_ref
                        assert compiler_report.input_content_hash == binding.input_content_hash
                        assert compiler_report.requirement_basis == binding.resolution
                        assert (
                            validate_persisted_data_requirement_compilation_report(
                                store, receipt.requirement_basis_binding
                            )
                            == ()
                        )
                        receipt_specs = tuple(receipt.compiled_requirement_specs)
                        report_specs = tuple(
                            spec.model_dump(mode="json") for spec in compiler_report.specs
                        )
                        assert report_specs == receipt_specs
                        selected_specs = tuple(
                            spec
                            for spec in compiler_report.specs
                            if spec.requirement_id == route.owner_artifact.requirement_ref
                        )
                        assert len(selected_specs) == 1
                        selected_spec = selected_specs[0]
                        assert selected_spec.model_dump(mode="json") == compiler_spec.model_dump(
                            mode="json"
                        )
                        assert selected_spec.required_data_families == (expected_family,)
                        assert (
                            selected_spec.metadata["scope_profile"]["jurisdiction"]
                            == compiled_geography
                        )
                        assert (
                            selected_spec.metadata["scope_profile"]["time_role"]
                            == "observation_time"
                        )
                        assert store.verify(route.data_snapshot_ref).ok
                        assert store.verify(route.evidence.measurement_root_ref).ok

                        if expected_refusal is None:
                            assert run.synthetic is True
                            assert len(simulation.observations) == 2
                            before, after = simulation.observations
                            assert before[0] is prior_context
                            assert after[0] is controller._cycle_substrate_context
                            assert after[0] is not prior_context
                            assert after[0].world_model_record.world_model_record_id == after[1]
                            assert after[1] == route.world_build.record.world_model_record_id
                            assert controller._candidate_cycle_context_job_ref is not None
                            assert controller._candidate_cycle_context_job_ref != prior_context_ref

                            old_denials = set(prior_context.may_not_use_for)
                            assert old_denials
                            measurement_denials = {
                                "unverified_measurement_requirement:"
                                "catalog_resolution_is_candidate_only",
                                "unverified_measurement_requirement:"
                                "catalog_quality_score_is_source_asserted",
                                "unverified_measurement_requirement:"
                                "worldbank_indicator_id_may_be_request_fallback",
                            }
                            assert old_denials.issubset(after[0].may_not_use_for)
                            assert measurement_denials.issubset(after[0].may_not_use_for)
                            readback = context_owner.resolve_for_current_job(
                                controller._candidate_cycle_context_job_ref,
                                problem=problem,
                                repo_root=tmp_path,
                                verified_nl_job_scope=verified_scope,
                            )
                            assert readback.context == after[0]
                            assert old_denials.issubset(readback.context.may_not_use_for)
                            assert measurement_denials.issubset(readback.context.may_not_use_for)
                        else:
                            assert run.blocked_reason == "n7_acq01_measurement_root_custody_invalid"
                            assert len(observed_reentry_errors) == 1
                            assert expected_refusal in str(observed_reentry_errors[0])
                            assert len(simulation.observations) == 1
                            assert controller._candidate_cycle_context_job_ref == prior_context_ref
                            assert controller._cycle_substrate_context is prior_context

                service._control_store.complete_job(
                    job_id=admission.job.job_id,
                    run_id=admission.job.run_id,
                )
    finally:
        service.close()
