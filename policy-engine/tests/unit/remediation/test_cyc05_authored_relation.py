"""CYC-05 witnesses for authored candidate relations over persisted N4 source."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality.recursive_generation_cycle as recursive_cycle
from polisyos.core.artifacts import ArtifactRef, read_core_json_artifact
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.cycle_substrate import VerifiedNLJobScope
from polisyos.runtime.quality.generation_cycle import JointSimulationRequest
from polisyos.runtime.quality.recursive_generation_cycle import (
    ParentJointAuthoredRelationV1,
    ParentJointCandidateSelectionV3,
    ParentJointCandidateSourceMember,
    RecursiveGenerationCycleError,
    load_authored_joint_components,
)
from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Serve controlled compiler/N4 responses through the real HTTP worker."""

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


def _expect_refusal(call: Callable[[], object]) -> Exception:
    """Require a typed-owner refusal without constraining its transport class."""

    try:
        call()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        return exc
    pytest.fail("owner accepted a missing or mismatched authored relation input")


def _rehashed_relation_variant(
    *,
    relation: ParentJointAuthoredRelationV1,
    store: Any,
    update: dict[str, object],
) -> ArtifactRef:
    """Persist one correctly rehashed adversarial relation under the real closure."""

    fields = relation.model_dump(mode="json", exclude={"content_hash"})
    fields.update(update)
    draft_hash = gy_content_hash(fields)
    forged = ParentJointAuthoredRelationV1.model_validate({**fields, "content_hash": draft_hash})
    return store.put_json(
        forged.model_dump(mode="json"),
        recursive_cycle._authored_joint_relation_options(forged),
        canon_spec=recursive_cycle._N4_CHILD_PROFILE_SET_CANON,
        return_selected_profile=True,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_authored_joint_relation_replays_real_source_request_and_selected_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """The served worker persists and replays a candidate-only authored N5 relation."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationAdmissionOwner,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    fixture_identity = build_fixture_identity_claims()
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=fixture_identity.tenant_id,
        cell_id=fixture_identity.cell_id,
        child_count=2,
        recording_mode="original_second_capture",
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
    )
    assert len(prepared.children) == 2

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    span_support_clients: list[_DeterministicSpanSupportClient] = []

    async def run_deterministic_compiler(**kwargs: Any) -> Any:
        span_support_client = _DeterministicSpanSupportClient()
        span_support_clients.append(span_support_client)
        kwargs["span_support_client"] = span_support_client
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_deterministic_compiler,
    )

    persist_calls: list[dict[str, Any]] = []
    persisted: list[tuple[ParentJointAuthoredRelationV1, CASArtifactRef]] = []
    real_persist = recursive_cycle.persist_authored_joint_components

    def observed_persist(**kwargs: Any) -> tuple[ParentJointAuthoredRelationV1, CASArtifactRef]:
        if persist_calls:
            return real_persist(**kwargs)
        persist_calls.append(dict(kwargs))
        scope = kwargs["verified_nl_job_scope"]
        assert type(scope) is VerifiedNLJobScope
        assert scope._was_issued_by_verified_nl_execution_owner
        assert kwargs["admission_owner"].store is kwargs["store"]

        def expect_code(code: str, **updates: object) -> None:
            with pytest.raises(RecursiveGenerationCycleError) as refusal:
                real_persist(**{**kwargs, **updates})
            assert refusal.value.code == code

        expect_code("recursive_authored_joint_request_ref_invalid", request_payload_ref=None)
        expect_code(
            "recursive_authored_joint_request_ref_invalid",
            request_payload_ref=kwargs["source_ref"],
        )
        expect_code(
            "recursive_authored_joint_materialization_mismatch",
            component_materializations=tuple(reversed(kwargs["component_materializations"])),
        )
        original_request = kwargs["request"]
        assert type(original_request) is JointSimulationRequest
        altered_request = original_request.model_copy(update={"seed": original_request.seed + 1})
        expect_code(
            "recursive_authored_joint_request_replay_mismatch",
            request=altered_request,
        )

        members = kwargs["members"]
        assert len(members) == 2
        foreign_member = members[0].model_copy(
            update={
                "source_candidate_id": "candidate:foreign-rehashed",
                "source_candidate_content_hash": "sha256:" + "f" * 64,
            }
        )
        expect_code(
            "recursive_authored_joint_source_member_mismatch",
            members=(foreign_member, *members[1:]),
        )

        _expect_refusal(
            lambda: real_persist(
                **{
                    **kwargs,
                    "source_ref": kwargs["request_payload_ref"],
                }
            )
        )
        result = real_persist(**kwargs)
        persisted.append(result)
        return result

    monkeypatch.setattr(recursive_cycle, "persist_authored_joint_components", observed_persist)
    request_payload = {
        **prepared.request_json,
        "joint_interaction_candidate_intent": "authored_joint_components.v1",
    }
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        request_json = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
        idempotency_key = (
            "test-cyc05-authored-" + hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        )
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            content=request_json,
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
        fresh_response = client.get(f"/api/v1/runs/{run_id}")
        assert fresh_response.status_code == 200, fresh_response.text
        projection = fresh_response.json()["run"]["generic_cycle_simulation"]

        assert len(persist_calls) == 1
        assert len(persisted) == 1
        assert span_support_clients
        route_inputs = persist_calls[0]
        relation, relation_ref = persisted[0]
        assert relation.authority_purpose == "candidate_only"
        assert relation.candidate_intent == "authored_joint_components.v1"
        assert relation.composition_status == "authored_candidate"
        assert relation.child_to_parent_refinement_status == "not_established"
        assert relation.request_payload_ref == route_inputs["request_payload_ref"]
        assert relation.n4_source_ref == route_inputs["source_ref"]
        assert relation.intent_digest == route_inputs["verified_nl_job_scope"].intent_digest
        assert len(relation.members) == len(relation.component_materializations) == 2
        assert tuple(item.candidate_id for item in relation.component_materializations) == tuple(
            member.source_candidate_id for member in relation.members
        )
        assert tuple(
            item.original_atom_hash for item in relation.component_materializations
        ) == tuple(member.source_atom_content_hash for member in relation.members)
        assert relation.joint_simulation_request_content_hash == gy_content_hash(
            route_inputs["request"].model_dump(mode="json")
        )
        assert relation_ref.kind == "runtime.quality.recursive_authored_joint_relation"
        assert projection["n4_source_status"] == "resolved"
        parent_rows = [
            row
            for row in projection["n5_observations"]
            if row["node_ref"]
            == "design-problem://" + relation.parent_design_problem_ref.removeprefix("sha256:")
        ]
        assert parent_rows
        assert parent_rows[0]["n8_candidate_joint_selection_status"] == "resolved"
        assert parent_rows[0]["n8_candidate_joint_selection_content_hash"].startswith("sha256:")

        store = service._artifact_store
        compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(store, compiled_ref).value
        )
        selected_nodes = [
            node
            for node in compiled.recursive_run.nodes
            if isinstance(node.joint_candidate_selection, ParentJointCandidateSelectionV3)
        ]
        assert len(selected_nodes) == 1
        selected_node = selected_nodes[0]
        selection = selected_node.joint_candidate_selection
        request = selected_node.joint_simulation_request
        handoff = compiled.generic_cycle_simulation_handoff
        assert type(selection) is ParentJointCandidateSelectionV3
        assert request is not None and handoff is not None
        assert selection.relation_ref == relation_ref
        assert selection.request_payload_ref == relation.request_payload_ref
        assert selection.joint_simulation_request_content_hash == (
            relation.joint_simulation_request_content_hash
        )

        source_repository = GenerationSourceRepository(store)
        admission_owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
        source = source_repository.load(
            relation.n4_source_ref,
            run_id=relation.source_run_id,
            expected_run_id=relation.run_id,
            expected_job_id=relation.job_id,
            expected_tenant_id=relation.tenant_id,
            expected_cell_id=relation.cell_id,
            context_job_ref=handoff.context_job_ref,
            profile_ref=handoff.profile_ref,
            n4_child_profile_family_ref=handoff.n4_child_profile_family_ref,
        )
        assert source.generation_result.status == "generated"
        assert source.generation_result.design_problem_ref == relation.parent_design_problem_ref
        assert {candidate.candidate_id for candidate in source.generation_result.candidates} == {
            member.source_candidate_id for member in relation.members
        }
        assert relation.n4_source_content_hash == source.content_hash
        assert relation.n4_source_result_content_hash == gy_content_hash(
            source.generation_result.model_dump(mode="json")
        )
        recursive_cycle._authored_joint_request_payload(
            store=store,
            ref=relation.request_payload_ref,
            handoff=handoff,
            intent_digest=relation.intent_digest,
        )
        assert gy_content_hash(request.model_dump(mode="json")) == (
            relation.joint_simulation_request_content_hash
        )
        loaded = load_authored_joint_components(
            store=store,
            relation_ref=selection.relation_ref,
            source_repository=source_repository,
            parent_handoff=handoff,
            admission_owner=admission_owner,
            request=request,
            selection=selection,
        )
        assert loaded == relation
        assert loaded.members == selection.members
        assert tuple(
            item.derived_n5_atom.atom_id for item in loaded.component_materializations
        ) == (selection.derived_atom_ids)
        assert (
            tuple(item.derived_n5_atom.content_hash for item in loaded.component_materializations)
            == selection.derived_atom_content_hashes
        )

        missing_relation_ref = ArtifactRef.model_validate(
            {
                **relation_ref.model_dump(mode="json"),
                "artifact_id": "sha256:" + "0" * 64,
            }
        )
        with pytest.raises(RecursiveGenerationCycleError) as missing_relation:
            load_authored_joint_components(
                store=store,
                relation_ref=missing_relation_ref,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
                selection=selection,
            )
        assert missing_relation.value.code == "recursive_authored_joint_relation_ref_invalid"

        foreign_selection = selection.model_copy(update={"relation_ref": missing_relation_ref})
        with pytest.raises(RecursiveGenerationCycleError) as wrong_selection:
            load_authored_joint_components(
                store=store,
                relation_ref=relation_ref,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
                selection=foreign_selection,
            )
        assert wrong_selection.value.code == "recursive_authored_joint_selection_replay_mismatch"

        missing_source_ref = ArtifactRef.model_validate(
            {
                **relation.n4_source_ref.model_dump(mode="json"),
                "artifact_id": "sha256:" + "0" * 64,
            }
        )
        missing_source_variant = _rehashed_relation_variant(
            relation=relation,
            store=store,
            update={"n4_source_ref": missing_source_ref.model_dump(mode="json")},
        )
        _expect_refusal(
            lambda: load_authored_joint_components(
                store=store,
                relation_ref=missing_source_variant,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
            )
        )

        foreign_source_ref = route_inputs["request_payload_ref"].model_copy(
            update={"kind": "runtime.generation_source_handoff"}
        )
        source_variant = _rehashed_relation_variant(
            relation=relation,
            store=store,
            update={"n4_source_ref": foreign_source_ref.model_dump(mode="json")},
        )
        _expect_refusal(
            lambda: load_authored_joint_components(
                store=store,
                relation_ref=source_variant,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
            )
        )

        foreign_request_ref = route_inputs["source_ref"].model_copy(
            update={"kind": "runtime.control_job_payload.natural_language_run"}
        )
        request_variant = _rehashed_relation_variant(
            relation=relation,
            store=store,
            update={"request_payload_ref": foreign_request_ref.model_dump(mode="json")},
        )
        with pytest.raises(RecursiveGenerationCycleError) as wrong_request:
            load_authored_joint_components(
                store=store,
                relation_ref=request_variant,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
            )
        assert wrong_request.value.code == "recursive_authored_joint_request_profile_mismatch"

        missing_request_ref = ArtifactRef.model_validate(
            {
                **relation.request_payload_ref.model_dump(mode="json"),
                "artifact_id": "sha256:" + "0" * 64,
            }
        )
        missing_request_variant = _rehashed_relation_variant(
            relation=relation,
            store=store,
            update={"request_payload_ref": missing_request_ref.model_dump(mode="json")},
        )
        _expect_refusal(
            lambda: load_authored_joint_components(
                store=store,
                relation_ref=missing_request_variant,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
            )
        )

        first_member = relation.members[0].model_dump(mode="json")
        first_member["source_candidate_id"] = "candidate:foreign-rehashed"
        first_member["source_candidate_content_hash"] = "sha256:" + "f" * 64
        foreign_member = ParentJointCandidateSourceMember.model_validate(first_member)
        first_materialization = relation.component_materializations[0].model_dump(mode="json")
        first_materialization["candidate_id"] = foreign_member.source_candidate_id
        first_materialization["original_candidate_hash"] = (
            foreign_member.source_candidate_content_hash
        )
        first_materialization["content_hash"] = gy_content_hash(
            {key: value for key, value in first_materialization.items() if key != "content_hash"}
        )
        forged_materialization = type(relation.component_materializations[0]).model_validate(
            first_materialization
        )
        foreign_member_variant = _rehashed_relation_variant(
            relation=relation,
            store=store,
            update={
                "members": (foreign_member, *relation.members[1:]),
                "component_materializations": (
                    forged_materialization,
                    *relation.component_materializations[1:],
                ),
            },
        )
        foreign_member_error = _expect_refusal(
            lambda: load_authored_joint_components(
                store=store,
                relation_ref=foreign_member_variant,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=request,
            )
        )
        assert "recursive_authored_joint_source_member_mismatch" in str(foreign_member_error)

        altered_request = request.model_copy(update={"seed": request.seed + 1})
        with pytest.raises(RecursiveGenerationCycleError) as wrong_request_replay:
            load_authored_joint_components(
                store=store,
                relation_ref=relation_ref,
                source_repository=source_repository,
                parent_handoff=handoff,
                admission_owner=admission_owner,
                request=altered_request,
                selection=selection,
            )
        assert wrong_request_replay.value.code == "recursive_authored_joint_relation_scope_mismatch"
