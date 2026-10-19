from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest


class _ServedAcquisitionGrounding:
    """Issue one controlled acquisition gap from the actual selected candidate."""

    def __call__(
        self,
        *,
        candidate: Any,
        problem: Any,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> Any:
        del problem, cycle_index, generation_result
        from polisyos.runtime.quality.generation_cycle import (
            CandidateGroundingObservation,
        )

        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=("acquire_data:controlled_test_fixture_missing",),
            current_valid=False,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_n7_acquisition_captures_selected_local_fabric_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An admitted simulate-only NL POST reaches typed N7 and concrete Fabric capture."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.data_requirement import (
        DataQualityMinimums,
        DataRequirementScope,
        DataRequirementSpec,
    )
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.retrieval.service import RetrievalService
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionReceipt,
        RealAcquisitionOwnerGateway,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN8ValuePort,
    )
    from polisyos.runtime.quality.substrate_registry import (
        resolve_catalog_serving_source,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway
    from tests._helpers.generic_n4_served_replay import (
        REPO_ROOT,
        prepare_generic_n4_served_replay,
    )
    from tests.unit.fabric.test_retrieval_fetch_custody import (
        build_recorded_file_fetch_owner,
    )

    requirement = DataRequirementSpec(
        requirement_id="data-requirement:served-n7-metric-test",
        claim_id="claim-served-n7-metric-test",
        required_data_families=("metric.test",),
        scope=DataRequirementScope(
            population="msmes",
            geography="state_or_region",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:msme",),
        authority_profile_refs=("authority_profile.production",),
        metadata={
            "fabric_capture_mode": "persisted_payload",
            "scope_profile": {
                "profile_id": "fixture:catalog-capture:ua-2026",
                "jurisdiction": None,
                "time_window": {"start": None, "end": None},
                "time_role": "observation_time",
                "granularity": "annual",
                "required_constructs": [],
                "candidate_construct_proposals": [],
            },
        },
    )
    source_context = resolve_catalog_serving_source(
        REPO_ROOT,
        selection=None,
        requested_profile="prod_full",
    )
    identity = build_fixture_identity_claims()
    tenant_id, cell_id = identity.tenant_id, identity.cell_id
    assert tenant_id and cell_id

    n7_route_observations: list[dict[str, Any]] = []
    gateways: list[RealAcquisitionOwnerGateway] = []
    resolve_observations: list[tuple[Any, Any, Any]] = []
    capture_plan_counts: list[int] = []
    services: list[RetrievalService] = []

    with (
        ControlledCandidateGateway() as candidate_gateway,
        build_recorded_file_fetch_owner(
            tmp_path / "fabric-owner",
            canonicalize_catalog_source=True,
            catalog_connector_params={},
            publish_current_catalog=True,
        ) as owner,
    ):
        owner.providers.registry.set_default_config(
            "files.tabular",
            ConnectionConfig(url="https://remote.invalid/unused-default.csv"),
        )
        selected_bindings = owner.graph.resolve_metric_bindings("metric.test", top_k=1)
        assert len(selected_bindings) == 1
        selected_binding = selected_bindings[0]
        assert selected_binding.source == "recorded_file"
        assert selected_binding.connector_id == "files.tabular"

        prepared = await prepare_generic_n4_served_replay(
            tmp_path=tmp_path / "served-replay",
            controlled_candidate_gateway=candidate_gateway,
            monkeypatch=monkeypatch,
            tenant_id=tenant_id,
            cell_id=cell_id,
            catalog_serving_source=source_context,
            child_count=1,
            recording_mode="served_wdi_global_scalar",
            runtime_hints_overlay={"n7_data_requirement_specs": (requirement,)},
        )
        assert prepared.recorded_problem.domain == "fiscal"
        assert prepared.recorded_problem.outcome_of_interest.target_variable == "global.tax_rate"
        selected_levers = prepared.recorded_problem.candidate_lever_space.candidate_levers
        assert len(selected_levers) == 1
        assert selected_levers[0].operator_kind == "budget_allocation_multiplier"
        assert selected_levers[0].target_slot == "government.balance"
        assert prepared.base_profile.rule.operator_kind == "budget_allocation_multiplier"
        assert prepared.base_profile.rule.target_world_slot == "government.balance"
        assert prepared.generic_child_profiles[0].rule.target_world_slot == "government.balance"
        assert prepared.recording["derived_from_recording_id"] == prepared.source_recording_id
        assert (
            prepared.recording["derived_from_content_hash"]
            == prepared.source_recording_content_hash
        )

        class _ObservedRetrievalService(RetrievalService):
            def resolve(self, request: Any, *, run_profile: Any = None) -> Any:
                response = super().resolve(request, run_profile=run_profile)
                resolve_observations.append((request, run_profile, response))
                return response

            def execute_persisted_fetch_capture(
                self,
                plans: Sequence[Any],
                *,
                preflight: Any,
                postflight: Any,
            ) -> Any:
                capture_plan_counts.append(len(plans))
                return super().execute_persisted_fetch_capture(
                    plans,
                    preflight=preflight,
                    postflight=postflight,
                )

        def _retrieval_service_factory(
            curated_dir: Path,
            artifact_store: Any,
            dataset_catalog: Any,
        ) -> RetrievalService:
            assert artifact_store is prepared.runtime_api_context.store
            assert dataset_catalog is owner.graph
            service = _ObservedRetrievalService(
                curated_dir=curated_dir,
                artifact_store=artifact_store,
                dataset_catalog=dataset_catalog,
                providers=owner.providers,
            )
            services.append(service)
            return service

        original_init = GenerationCycleController.__init__

        def _init_served_gap_ports(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            self._grounding_port = _ServedAcquisitionGrounding()
            self._value_port = PendingN8ValuePort()

        monkeypatch.setattr(GenerationCycleController, "__init__", _init_served_gap_ports)

        def _real_fixture_owner_gateway(self: Any, problem: Any) -> RealAcquisitionOwnerGateway:
            del problem
            binding = self._measurement_root_execution_binding
            assert binding is not None and binding.authority_eligible
            gateway = RealAcquisitionOwnerGateway(
                repo_root=REPO_ROOT,
                artifact_store=self._artifact_store,
                dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
                retrieval_service_factory=_retrieval_service_factory,
                catalog_run_profile=self._catalog_run_profile,
                catalog_serving_source=self._catalog_serving_source,
            )
            gateways.append(gateway)
            return gateway

        monkeypatch.setattr(
            GenerationCycleController,
            "_n7_owner_gateway",
            _real_fixture_owner_gateway,
        )

        original_run_n7 = GenerationCycleController._run_n7_acquisition_if_requested

        def _observe_actual_n7_route(
            self: Any,
            problem: Any,
            *,
            cycle: Any,
        ) -> Any:
            if cycle.terminal_kind == "acquisition_required":
                binding = self._measurement_root_execution_binding
                request = cycle.revision_request.strategy_payload.get("acquisition_request")
                assert binding is not None and binding.authority_eligible
                assert isinstance(request, Mapping)
                specs, _ = self._n7_data_requirement_basis(
                    problem,
                    acquisition_request=request,
                )
                n7_route_observations.append(
                    {
                        "measurement_binding": binding,
                        "acquisition_request": dict(request),
                        "data_requirement_specs": specs,
                    }
                )
            return original_run_n7(self, problem, cycle=cycle)

        monkeypatch.setattr(
            GenerationCycleController,
            "_run_n7_acquisition_if_requested",
            _observe_actual_n7_route,
        )

        app = create_runtime_api_app(
            **{**prepared.app_kwargs, "catalog_run_profile": "prod_full"},
            enable_contract_testing_credal_source_attempts=True,
        )
        with TestClient(app) as client:
            accepted_response = client.post(
                "/api/v1/control/runs/nl",
                headers={"Idempotency-Key": "served-n7-fabric-capture-20261020"},
                json=prepared.request_json,
            )
            assert accepted_response.status_code == 200, accepted_response.text
            accepted = accepted_response.json()
            control_service = app.state._control_service
            assert (
                dispatch_one_control_job(
                    store=control_service._control_store,
                    handler=control_service._process_control_job,
                    expected_job_id=accepted["job_id"],
                )
                == accepted["job_id"]
            )
            job = control_service._control_store.get_job(accepted["job_id"])
            assert job is not None and job.state == "completed"

            fresh_job = client.get(f"/api/v1/control/jobs/{accepted['job_id']}")
            assert fresh_job.status_code == 200, fresh_job.text
            run_id = job.progress.get("core_run_id")
            assert isinstance(run_id, str) and run_id
            fresh_run = client.get(f"/api/v1/runs/{run_id}")
            assert fresh_run.status_code == 200, fresh_run.text

            assert n7_route_observations
            observed_route = n7_route_observations[0]
            assert observed_route["measurement_binding"].authority_eligible
            request = observed_route["acquisition_request"]
            assert str(request.get("driver", "")).startswith("acquire_data:")
            assert "requirement_gap" not in request
            assert len(observed_route["data_requirement_specs"]) == 1
            assert gateways and services
            assert len(resolve_observations) == 1
            assert capture_plan_counts == [1]
            assert len(owner.requests) == 1

            request_sent, run_profile, response = resolve_observations[0]
            assert run_profile == "prod_full"
            assert tuple(need.metric for need in request_sent.data_needs) == ("metric.test",)
            assert len(response.fetch_plans) == 1
            selected_plan = response.fetch_plans[0]
            assert selected_plan.metric_id == "metric.test"
            assert selected_plan.connector_id == "files.tabular"
            assert selected_plan.dataset_id == str(owner.csv_path)
            assert selected_plan.profile_id == "recorded_file_local"

            compiled_ref = job.progress.get("compiled_recursive_generation_cycle_ref")
            assert compiled_ref is not None
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                raw_compiled = control_service._artifact_store.get_bytes(compiled_ref)
                from polisyos.runtime.http.services.control.generation_cycle import (
                    CompiledRecursiveGenerationCycleRun,
                )

                compiled_run = CompiledRecursiveGenerationCycleRun.model_validate(
                    canon.from_canonical_bytes(raw_compiled)
                )
                root_node = next(
                    node
                    for node in compiled_run.recursive_run.leaf_nodes
                    if node.node_ref == compiled_run.recursive_run.root_node_ref
                )
                assert root_node.cycle_run is not None
                n7_cycles = tuple(
                    cycle
                    for cycle in root_node.cycle_run.cycles
                    if cycle.acquisition_receipt is not None
                )
                assert n7_cycles
                receipt = AcquisitionReceipt.model_validate(n7_cycles[0].acquisition_receipt)

                assert receipt.compiled_spec_count == 1
                assert receipt.compiled_requirement_specs[0]["requirement_id"] == (
                    requirement.requirement_id
                )
                assert receipt.acquisition_request == request
                assert len(receipt.owner_artifacts) == 1
                artifact = receipt.owner_artifacts[0]
                assert artifact.owner_component == "fabric.retrieval"
                owner_response = artifact.payload["owner_response"]
                assert owner_response["owner_response_kind"] == "fabric_fetch_capture"
                assert owner_response["candidate_only"] is True
                assert owner_response["captured_fetch_count"] == 1
                assert artifact.payload["acquired_substrate_registrations"] == []
                assert artifact.payload["candidate_bindings"] == []
                captured = owner_response["captured_fetches"][0]
                binding_ref = ArtifactRef.model_validate(captured["catalog_binding_ref"])
                assert control_service._artifact_store.has(binding_ref)
                binding = catalog_read_api.CatalogFetchBinding.model_validate(
                    canon.from_canonical_bytes(
                        control_service._artifact_store.get_bytes(binding_ref)
                    )
                )
                assert binding.binding is not None
                assert binding.binding.source == selected_binding.source
                assert binding.binding.metric_id == "metric.test"
                assert binding.binding.connector_id == "files.tabular"
                assert binding.binding.request_dataset_id == selected_plan.dataset_id
                assert receipt.grown_world_added_slots == ()
                assert receipt.cost_summary_usd == sum(
                    item.cost_usd for item in receipt.owner_artifacts
                )
                assert receipt.cost_summary_usd == 0.0
                selected_record = receipt.planner_report.acquisition_records[0]
                selected_strategy = next(
                    record
                    for record in selected_record.strategy_records
                    if record.strategy == selected_record.recommended_strategy
                )
                assert selected_strategy.voi_expected_cost is not None
                assert selected_strategy.voi_expected_cost > receipt.cost_summary_usd
