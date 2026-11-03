"""Source-backed CYC-05 parent stop after a real child N5 quota boundary."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleNode,
    RecursiveCyclePendingNode,
    RecursiveGenerationCyclePartialRunV4,
    verify_recursive_standard_n5_capacity_partial_run,
)
from polisyos.scientist.orchestration.engine.budget_ledger import BudgetInvocationQuotaPolicy


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Serve controlled candidate compiler/N4 responses from a local gateway."""

    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


def _selected_quota_profile(profile: Any, policy: BudgetInvocationQuotaPolicy) -> Any:
    """Rehash a selected test profile with a real finite standard N5 allocation."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV3,
    )
    from tests._helpers.generic_n4_served_replay import _hashed_model

    if type(profile.n5) is not GenericCycleN5RequestProfileV3:
        raise AssertionError("capacity_fixture_requires_selected_n5_v3")
    n5_fields = profile.n5.model_dump(mode="python")
    n5_fields.update(
        invocation_quota_policy=policy,
        invocation_purpose="standard",
    )
    selected_n5 = GenericCycleN5RequestProfileV3.model_validate(n5_fields)
    profile_fields = profile.model_dump(mode="python", exclude={"content_hash"})
    profile_fields["n5"] = selected_n5
    return _hashed_model(type(profile), profile_fields, hash_fn=gy_content_hash)


def _self_bound_capacity_variant(
    partial: RecursiveGenerationCyclePartialRunV4,
) -> RecursiveGenerationCyclePartialRunV4:
    """Add a fake terminal operation and coherently rehash the enclosing partial."""

    witness = partial.invocation_exhaustion_witness
    fake_id = "f" * 64
    while any(operation_id == fake_id for operation_id, _ in witness.terminal_witnesses):
        fake_id = "e" * 64
    terminal_witnesses = tuple(
        sorted((*witness.terminal_witnesses, (fake_id, witness.source_revision)))
    )
    forged_witness = witness.model_copy(
        update={
            "standard_limit_units": witness.standard_limit_units + 1,
            "terminal_witnesses": terminal_witnesses,
        }
    )
    fields = partial.model_dump(mode="python", exclude={"content_hash"})
    fields["invocation_exhaustion_witness"] = forged_witness
    draft = RecursiveGenerationCyclePartialRunV4.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    payload = gy_artifact_self_identity_projection(draft)
    payload.pop("leaf_nodes", None)
    payload.pop("pending_node_refs", None)
    return RecursiveGenerationCyclePartialRunV4.model_validate(
        {**fields, "content_hash": gy_content_hash(payload)}
    )


class _ProfilelessSelectedRefStore:
    """Delegate reads while simulating a writer that drops its selected view."""

    def __init__(self, delegate: Any, profileless_ref: ArtifactRef) -> None:
        self._delegate = delegate
        self._profileless_ref = profileless_ref

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def put_json(
        self,
        obj: object,
        opts: object,
        canon_spec: object | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        assert return_selected_profile is True
        return self._profileless_ref


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_two_child_run_stops_before_second_child_on_standard_n5_capacity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Persist child one's actual N5, then keep child two pending at the owner cap."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as cycle_service
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    identity = build_fixture_identity_claims()

    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=identity.tenant_id,
        cell_id=identity.cell_id,
        child_count=2,
        recording_mode="original_second_capture",
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
    )
    assert len(prepared.children) == 2

    first_child_n5 = prepared.generic_child_profiles[0].n5
    # The selected singleton request reuses its physical N5 work between the
    # individual and joint views. Cap the exact per-replication work, not the
    # number of semantic scopes, so the next leaf is genuinely denied.
    standard_limit = first_child_n5.replications
    policy = BudgetInvocationQuotaPolicy(
        allocation_id=f"cyc05-two-child-{uuid.uuid4().hex}",
        total_units=standard_limit,
        protected_units=0,
    )
    configured_profiles = tuple(
        _selected_quota_profile(profile, policy) for profile in prepared.generic_profiles
    )
    prepared.app_kwargs["generic_cycle_simulation_profiles"] = configured_profiles

    original_compiler = cycle_service.build_design_problem_from_nl_request
    span_support_clients: list[_DeterministicSpanSupportClient] = []

    async def run_deterministic_compiler(**kwargs: Any) -> Any:
        span_support_client = _DeterministicSpanSupportClient()
        span_support_clients.append(span_support_client)
        kwargs["span_support_client"] = span_support_client
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        cycle_service,
        "build_design_problem_from_nl_request",
        run_deterministic_compiler,
    )

    observed_budget_owners: list[Any] = []
    original_budget_owner_builder = run_lifecycle._build_control_nl_producer_budget_reconciler

    def capture_budget_owner(**kwargs: Any) -> Any:
        observer = original_budget_owner_builder(**kwargs)
        observed_budget_owners.append(observer)
        return observer

    monkeypatch.setattr(
        run_lifecycle,
        "_build_control_nl_producer_budget_reconciler",
        capture_budget_owner,
    )

    request_json = {
        **prepared.request_json,
        "joint_interaction_candidate_intent": "authored_joint_components.v1",
    }
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "cyc05-capacity-"
                + hashlib.sha256(
                    json.dumps(request_json, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
            },
            json=request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        run_id = str(job.progress["core_run_id"])
        response_before = client.get(f"/api/v1/runs/{run_id}")
        assert response_before.status_code == 200, response_before.text
        run_payload = response_before.json()["run"]
        projection = run_payload["generic_cycle_simulation"]
        checkpoint = projection["recursive_cycle_checkpoint"]
        assert span_support_clients
        assert len(observed_budget_owners) == 1
        compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(service._artifact_store, compiled_ref).value
        )
        control_run_id = str(job.run_id)
        assert compiled.n4_recursive_source_run_id == control_run_id
        assert compiled.generic_cycle_simulation_handoff is not None
        assert compiled.generic_cycle_simulation_handoff.run_id == control_run_id
        assert control_run_id != run_id
        partial = compiled.recursive_run
        assert type(partial) is RecursiveGenerationCyclePartialRunV4
        assert partial.traversal_status == "capacity_stopped"
        assert partial.traversal_stop_reason == "standard_n5_invocation_capacity_exhausted"
        assert partial.limitation_code == "physical_need_not_established"
        assert checkpoint["schema_version"] == ("policyos.runtime.recursive_cycle_checkpoint.v3")
        assert checkpoint["capacity_source_content_hash"] == partial.content_hash
        assert checkpoint["capacity_limitation_code"] == "physical_need_not_established"
        assert checkpoint["capacity_stop_parent_node_ref"] == partial.root_node_ref
        assert checkpoint["capacity_pending_child_node_ref"] == partial.pending_child_node_ref
        assert checkpoint["capacity_pending_child_index"] == partial.pending_child_index

        by_ref = {node.node_ref: node for node in partial.nodes}
        root = by_ref[partial.root_node_ref]
        assert isinstance(root, RecursiveCyclePendingNode)
        assert len(root.child_refs) == 2
        assert partial.stop_parent_node_ref == partial.root_node_ref
        assert partial.pending_child_index == 1
        assert partial.pending_child_node_ref == root.child_refs[1]
        assert partial.frontier_node_refs == (root.child_refs[1],)
        first = by_ref[root.child_refs[0]]
        second = by_ref[root.child_refs[1]]
        assert isinstance(first, RecursiveCycleNode)
        assert isinstance(second, RecursiveCyclePendingNode)
        assert first.cycle_run is not None
        assert first.leaf_context_ref is not None
        assert first.leaf_context_ref.manifest_profile_sha256 is not None
        assert first.parent_ref is not None
        assert compiled.generic_cycle_simulation_handoff is not None
        assert compiled.n4_child_profile_set_ref is not None
        assert compiled.n4_child_profile_set_ref.manifest_profile_sha256 is not None
        assert any(
            cycle.simulation.status == "joint_simulated"
            and cycle.simulation.simulation_result_ref is not None
            for cycle in first.cycle_run.cycles
        )
        assert len(partial.invocation_exhaustion_witness.terminal_witnesses) == standard_limit
        assert (
            service.verify_completed_recursive_capacity_partial(
                source_job_id=accepted["job_id"],
                run_id=control_run_id,
                tenant_id=identity.tenant_id,
                cell_id=identity.cell_id,
                partial=partial,
            )
            is True
        )

        from polisyos.runtime.quality.cycle_substrate import (
            CycleSubstrateContextArtifactOwner,
        )
        from polisyos.runtime.quality.generation_source import GenerationSourceRepository
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner,
        )
        from polisyos.runtime.quality.recursive_generation_cycle import (
            RecursiveLeafContextOwner,
        )

        source_repository = GenerationSourceRepository(service._artifact_store)
        capsule_owner = RecursiveLeafContextOwner(
            store=service._artifact_store,
            context_owner=CycleSubstrateContextArtifactOwner(store=service._artifact_store),
            admission_owner=None,
            generic_admission_owner=GenericCycleSimulationAdmissionOwner(
                profiles=(), store=service._artifact_store
            ),
        )
        root_family = capsule_owner.load_n4_child_profile_set(
            compiled.n4_child_profile_set_ref,
            expected_job_id=compiled.generic_cycle_simulation_handoff.job_id,
            expected_run_id=compiled.generic_cycle_simulation_handoff.run_id,
            expected_tenant_id=compiled.generic_cycle_simulation_handoff.tenant_id,
            expected_cell_id=compiled.generic_cycle_simulation_handoff.cell_id,
            expected_parent_handoff=compiled.generic_cycle_simulation_handoff,
            source_repository=source_repository,
        )
        family_rows = tuple(row for row in root_family.children if row.node_ref == first.node_ref)
        assert len(family_rows) == 1
        capsule = capsule_owner.resolve_generic_capsule_historical(
            first.leaf_context_ref,
            expected_node_ref=first.node_ref,
            expected_parent_ref=first.parent_ref,
            expected_problem=family_rows[0].problem,
            expected_parent_handoff=compiled.generic_cycle_simulation_handoff,
            expected_child_profile_set_ref=compiled.n4_child_profile_set_ref,
            source_repository=source_repository,
        )
        assert capsule.node_ref == first.node_ref
        with pytest.raises(
            ValueError,
            match="recursive_generic_capsule_historical_inputs_invalid",
        ):
            capsule_owner.resolve_generic_capsule_historical(
                first.leaf_context_ref.model_copy(update={"manifest_profile_sha256": None}),
                expected_node_ref=first.node_ref,
                expected_parent_ref=first.parent_ref,
                expected_problem=family_rows[0].problem,
                expected_parent_handoff=compiled.generic_cycle_simulation_handoff,
                expected_child_profile_set_ref=compiled.n4_child_profile_set_ref,
                source_repository=source_repository,
            )

        profileless_store = _ProfilelessSelectedRefStore(
            service._artifact_store,
            first.leaf_context_ref.model_copy(update={"manifest_profile_sha256": None}),
        )
        profileless_owner = RecursiveLeafContextOwner(
            store=profileless_store,
            context_owner=CycleSubstrateContextArtifactOwner(store=profileless_store),
            admission_owner=None,
            generic_admission_owner=GenericCycleSimulationAdmissionOwner(
                profiles=(), store=profileless_store
            ),
        )
        monkeypatch.setattr(
            profileless_owner,
            "require_current_n4_child_profile_set",
            lambda *args, **kwargs: root_family,
        )
        with pytest.raises(
            ValueError,
            match="recursive_generic_capsule_selected_ref_not_returned",
        ):
            profileless_owner.persist_generic_capsule(
                capsule,
                parent_handoff=compiled.generic_cycle_simulation_handoff,
                source_repository=GenerationSourceRepository(profileless_store),
            )

        observer = observed_budget_owners[0]
        assert (
            verify_recursive_standard_n5_capacity_partial_run(
                partial,
                observer=observer,
                store=service._artifact_store,
            )
            is True
        )
        tampered_cap = _self_bound_capacity_variant(partial)
        with pytest.raises(ValueError, match="recursive_capacity_partial_owner"):
            verify_recursive_standard_n5_capacity_partial_run(
                tampered_cap,
                observer=observer,
                store=service._artifact_store,
            )

        from polisyos.runtime.quality.generation_cycle import (
            resolve_generic_n5_historical_cycle_join,
            verify_recursive_standard_n5_capacity_partial_run_historical,
        )
        from polisyos.scientist.orchestration.engine.budget_ledger import (
            BudgetLedgerProducerRunBinding,
        )

        first_simulated_cycle = next(
            cycle
            for cycle in first.cycle_run.cycles
            if cycle.simulation.simulation_result_ref is not None
        )
        selected_join = resolve_generic_n5_historical_cycle_join(
            artifact_store=service._artifact_store,
            cycle_run=first.cycle_run,
            cycle_index=first_simulated_cycle.cycle_index,
            node_ref=first.node_ref,
            leaf_context_ref=first.leaf_context_ref,
            child_profile_set_ref=compiled.n4_child_profile_set_ref,
            expected_parent_handoff=compiled.generic_cycle_simulation_handoff,
            expected_parent_problem=compiled.design_problem,
            expected_parent_n4_source_ref=compiled.n4_recursive_source_ref,
            expected_job_id=accepted["job_id"],
            expected_run_id=control_run_id,
            expected_tenant_id=identity.tenant_id,
            expected_cell_id=identity.cell_id,
        )
        assert selected_join.status == "resolved"
        assert selected_join.input_record is not None
        selected_policy = selected_join.input_record.profile.n5.invocation_quota_policy
        assert selected_policy == policy
        historical_binding = BudgetLedgerProducerRunBinding(
            run_id=control_run_id,
            tenant_id=identity.tenant_id,
            cell_id=identity.cell_id,
            profile_id=job.effective_execution_profile,
            control_job_id=accepted["job_id"],
        )
        with pytest.raises(ValueError, match="recursive_capacity_partial_owner_not_established"):
            verify_recursive_standard_n5_capacity_partial_run_historical(
                tampered_cap,
                settlement_store=service._llm_producer_settlement_store,
                expected_run_binding=historical_binding,
                expected_policy=selected_policy,
                store=service._artifact_store,
            )

    # Reopen the persisted CAS and Core run index after the producer client has
    # closed. The fresh GET must reconstruct the same candidate-only checkpoint
    # from the completed job, selected input, and durable quota witness.
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context

    reader_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    assert reader_context is not prepared.runtime_api_context
    assert reader_context.store is not prepared.runtime_api_context.store
    reader_kwargs = {
        **prepared.app_kwargs,
        "container_overrides": RuntimeContainerOverrides(runtime_api_context=reader_context),
        "generic_cycle_simulation_profiles": (),
        "generic_cycle_simulation_root_profile_id": None,
    }

    # Build a real same-tenant Core run that roots the exact selected compiled
    # artifact under a different public run id. The consumer must refuse this
    # cross-run graft even though tenant, cell, artifact bytes, and manifest
    # profile all match.
    from polisyos.core.artifacts.manifest import ProducerInfo
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.tenant_context import tenant_scope

    foreign_public_run_id = f"R-cyc05-foreign-{uuid.uuid4().hex}"
    with tenant_scope(None, tenant_id=identity.tenant_id, cell_id=identity.cell_id):
        registry_bundle = build_default_registry_bundle(
            reader_context.store,
            return_selected_profile=True,
        )
        assert registry_bundle.bundle_ref.manifest_profile_sha256 is not None
        foreign_public_run = RunContext.start(
            store=reader_context.store,
            registry_bundle=registry_bundle.bundle_ref,
            producer=ProducerInfo(
                component="polisyos.tests.runtime_quality.cyc05_capacity_frontier",
                version="1.0.0",
            ),
            run_dir=reader_context.core_runs_root / foreign_public_run_id,
            run_id=foreign_public_run_id,
            tenant_id=identity.tenant_id,
            cell_id=identity.cell_id,
        )
        foreign_public_run.add_output(compiled_ref)
        foreign_public_run.finalize(status="completed")
    reader_context.run_index.refresh(force=True)

    from dataclasses import replace

    def get_projection(reader: Any, target_run_id: str) -> dict[str, Any]:
        response = reader.get(f"/api/v1/runs/{target_run_id}")
        assert response.status_code == 200, response.text
        projection = response.json()["run"]["generic_cycle_simulation"]
        assert isinstance(projection, dict)
        return projection

    def assert_historical_refusal(projection: dict[str, Any]) -> None:
        assert projection["artifact_status"] == "not_established"
        assert (
            projection["limitation_code"]
            == "recursive_capacity_historical_verification_not_established"
        )
        assert projection.get("recursive_cycle_checkpoint") is None

    with TestClient(create_runtime_api_app(**reader_kwargs)) as reader:
        reader_service = reader.app.state._control_service
        assert reader_service is not service
        assert reader_service._artifact_store is not service._artifact_store
        assert reader_service._control_store is not service._control_store

        fresh_projection = get_projection(reader, run_id)
        assert fresh_projection["artifact_status"] == "resolved"
        fresh_checkpoint = fresh_projection["recursive_cycle_checkpoint"]
        assert fresh_checkpoint["schema_version"] == (
            "policyos.runtime.recursive_cycle_checkpoint.v3"
        )
        assert fresh_checkpoint["capacity_source_content_hash"] == partial.content_hash
        assert fresh_checkpoint["capacity_limitation_code"] == "physical_need_not_established"
        assert fresh_checkpoint["root_n9_status"] == "not_run"

        cross_run_projection = get_projection(reader, foreign_public_run_id)
        assert_historical_refusal(cross_run_projection)

        # A selected compiled artifact with the same bytes but no selected
        # manifest profile must not acquire a current/default profile on GET.
        run_index = reader_context.run_index
        original_get_run = run_index.get_run

        def get_run_with_profileless_compiled_view(requested_run_id: str):
            indexed = original_get_run(requested_run_id)
            if requested_run_id != run_id:
                return indexed
            root_artifacts = tuple(
                ref.model_copy(update={"manifest_profile_sha256": None})
                if ref.artifact_id == compiled_ref.artifact_id
                else ref
                for ref in indexed.details.root_artifacts
            )
            assert sum(ref.artifact_id == compiled_ref.artifact_id for ref in root_artifacts) == 1
            return replace(
                indexed,
                details=indexed.details.model_copy(update={"root_artifacts": root_artifacts}),
            )

        with monkeypatch.context() as profileless_index:
            profileless_index.setattr(run_index, "get_run", get_run_with_profileless_compiled_view)
            assert_historical_refusal(get_projection(reader, run_id))

        def assert_missing_artifact_refusal(blob_path: Path, name: str) -> None:
            hidden_path = blob_path.with_name(f"{blob_path.name}.cyc05-held-{name}")
            assert blob_path.is_file()
            assert not hidden_path.exists()
            blob_path.rename(hidden_path)
            try:
                assert_historical_refusal(get_projection(reader, run_id))
            finally:
                hidden_path.rename(blob_path)
            assert blob_path.is_file()
            assert get_projection(reader, run_id)["artifact_status"] == "resolved"

        capsule_blob, _capsule_manifest = service._artifact_store._paths(
            first.leaf_context_ref.artifact_id
        )
        assert_missing_artifact_refusal(capsule_blob, "capsule")

        selected_result_ref = first_simulated_cycle.simulation.simulation_result_ref
        assert selected_result_ref is not None
        assert selected_result_ref.manifest_profile_sha256 is not None
        result_blob, _result_manifest = service._artifact_store._paths(
            selected_result_ref.artifact_id
        )
        assert_missing_artifact_refusal(result_blob, "result")

        ledger_store = reader_service._llm_producer_settlement_store
        producer_ledger_store = service._llm_producer_settlement_store
        assert ledger_store is not producer_ledger_store
        ledger_path = ledger_store._ledger._path
        assert ledger_path == producer_ledger_store._ledger._path
        assert_missing_artifact_refusal(ledger_path, "ledger")
