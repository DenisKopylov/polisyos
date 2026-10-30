"""Real generic handoff admission and fresh HTTP projection for bounded TC.

The compiler is stopped after invoking the real configured generic resolver.
This does not claim N4/N5 numerical execution or full TC closure.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay

_STOP = "tc_generic_fixture_stopped_after_real_handoff_admission"


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["legacy", "matching", "wrong_snapshot"])
async def test_real_generic_context_uses_same_temporal_gate_and_fresh_http_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
    selection: str,
) -> None:
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import (
        artifact_manifest_profile_sha256,
        read_core_json_artifact,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        CycleSubstrateContextOwnerError,
        _has_context_job_owner_profile,
        parse_cycle_substrate_context_job_artifact,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.control_worker import dispatch_one_control_job

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "tc-generic-context-fixture"
    source = build_candidate_cycle_substrate_route_inputs(tmp_path / "source")
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        recording_mode="original_second_capture",
        child_count=2,
        source_root=source.root,
    )
    fabric = prepared.root_profile.context_inputs.world_model_record.fabric_world_ref
    selected_scope = {
        "snapshot_id": fabric.snapshot_id,
        "valid_at": fabric.as_of_valid_time,
        "tx_at": fabric.as_of_tx_time,
    }
    assert all(
        (
            profile.context_inputs.world_model_record.fabric_world_ref.snapshot_id,
            profile.context_inputs.world_model_record.fabric_world_ref.as_of_valid_time,
            profile.context_inputs.world_model_record.fabric_world_ref.as_of_tx_time,
        )
        == (fabric.snapshot_id, fabric.as_of_valid_time, fabric.as_of_tx_time)
        for profile in prepared.generic_profiles
    )
    request_json = deepcopy(prepared.request_json)
    if selection != "legacy":
        request_json["temporal_scope"] = selected_scope
        if selection == "wrong_snapshot":
            request_json["temporal_scope"]["snapshot_id"] = "unselected-fixture-world"
    observed = {"writer_refs": []}
    original_persist = CycleSubstrateContextArtifactOwner.persist_for_current_job

    def capture_writer_ref(owner, *args, **kwargs):
        ref = original_persist(owner, *args, **kwargs)
        observed["writer_refs"].append((args[0].content_hash, ref))
        return ref

    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "persist_for_current_job",
        capture_writer_ref,
    )
    app = create_runtime_api_app(**prepared.app_kwargs)
    with (
        tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
        TestClient(app) as client,
    ):
        service = app.state._control_service

        async def resolve_actual_generic_handoff(**kwargs):
            # Exercise the actual generic-only branch. No candidate owner or
            # direct gate call can stand in for this independently chosen route.
            resolver = kwargs["generic_cycle_simulation_handoff_resolver"]
            assert resolver is not None
            handoff = resolver(prepared.recorded_problem)
            observed["handoff"] = handoff
            if selection == "matching":
                assert handoff is not None
                leaf = kwargs["recursive_leaf_context_owner"]
                assert leaf is not None
                generic_owner = leaf._generic_admission_owner
                context_owner = leaf._context_owner
                scope = leaf._verified_nl_job_scope
                assert generic_owner is not None and scope is not None
                store = leaf._store
                selected_ref = handoff.context_job_ref
                assert selected_ref.manifest_profile_sha256 is not None
                assert (handoff.context.content_hash, selected_ref) in observed["writer_refs"]
                binding = next(
                    row
                    for row in service._control_store.current_execution_job_admission()
                    .job.progress["temporal_scope_context_world_read_bindings"]
                    .values()
                    if row["context_content_hash"] == handoff.context.content_hash
                )
                assert binding["context_job_ref"] == selected_ref.model_dump(mode="json")
                assert handoff.n4_child_profile_family_ref is not None
                family = read_core_json_artifact(store, handoff.n4_child_profile_family_ref).value
                assert family["parent_context_job_ref"] == selected_ref.model_dump(mode="json")

                # Import a real, valid second view over identical bytes. It has
                # the same write-option fields, but differs in v3 integrity
                # metadata and therefore in the selected profile identity.
                raw = store.get_bytes(selected_ref)
                manifest = store.get_manifest(selected_ref)
                alternate = manifest.model_copy(
                    update={
                        "integrity": manifest.integrity.model_copy(
                            update={"optional": {"fixture": "different-view"}}
                        )
                    }
                )
                wrong_ref = selected_ref.model_copy(
                    update={"manifest_profile_sha256": artifact_manifest_profile_sha256(alternate)}
                )
                assert wrong_ref.artifact_id == selected_ref.artifact_id
                assert wrong_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
                store.import_exact_view(
                    raw,
                    alternate.model_dump_json(by_alias=True, exclude_none=True).encode(),
                    artifact_id=wrong_ref,
                )
                assert store.verify(wrong_ref).ok
                assert store.get_bytes(wrong_ref) == raw
                record = parse_cycle_substrate_context_job_artifact(
                    read_core_json_artifact(store, wrong_ref).value
                )
                assert _has_context_job_owner_profile(store.get_manifest(wrong_ref), record)
                before = deepcopy(
                    service._control_store.current_execution_job_admission().job.progress[
                        "temporal_scope_context_world_read_bindings"
                    ]
                )
                for forged_ref, error in (
                    (
                        wrong_ref,
                        "cycle_substrate_context_job_selected_profile_mismatch",
                    ),
                    (
                        selected_ref.model_copy(update={"manifest_profile_sha256": None}),
                        "cycle_substrate_context_job_selected_profile_required",
                    ),
                ):
                    forged = handoff.model_copy(update={"context_job_ref": forged_ref})
                    with pytest.raises(CycleSubstrateContextOwnerError) as refused:
                        generic_owner.resolve_handoff(
                            handoff=forged,
                            problem=prepared.recorded_problem,
                            verified_nl_job_scope=scope,
                            context_owner=context_owner,
                            repo_root=prepared.source_root,
                        )
                    assert refused.value.code == error
                assert (
                    service._control_store.current_execution_job_admission().job.progress[
                        "temporal_scope_context_world_read_bindings"
                    ]
                    == before
                )

                # Exercise the real recursive consumer: it reloads a source
                # artifact whose lineage binds the selected parent and then
                # produces and replays the exact derived child handoffs.
                repository = GenerationSourceRepository(store)
                source_ref = repository.persist_ref(
                    run_id=handoff.run_id,
                    cycle_index=0,
                    problem=prepared.recorded_problem,
                    organ=replace(prepared.organ_run, cycle_substrate_context=handoff.context),
                    job_id=handoff.job_id,
                    expected_run_id=handoff.run_id,
                    tenant_id=handoff.tenant_id,
                    cell_id=handoff.cell_id,
                    context_job_ref=selected_ref,
                    profile_ref=handoff.profile_ref,
                    n4_child_profile_family_ref=handoff.n4_child_profile_family_ref,
                )
                source_manifest = store.get_manifest(source_ref)
                context_edge = next(
                    edge
                    for edge in source_manifest.inputs
                    if edge.role == "cycle_substrate_context_job"
                )
                assert context_edge.artifact_id == selected_ref.artifact_id
                assert context_edge.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
                _children, child_handoffs = leaf.admit_n4_child_profile_family(
                    parent_problem=prepared.recorded_problem,
                    parent_handoff=handoff,
                    source_ref=source_ref,
                    source_run_id=handoff.run_id,
                    source_repository=repository,
                )
                assert child_handoffs
                observed["child_handoffs"] = child_handoffs
                observed["family"] = family
            raise RuntimeError(_STOP)

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            resolve_actual_generic_handoff,
        )
        accepted = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid4().hex},
            json=request_json,
        )
        assert accepted.status_code == 200, accepted.text
        job_id = accepted.json()["job_id"]
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        response = client.get(f"/api/v1/control/jobs/{job_id}")
        assert response.status_code == 200, response.text
        status = response.json()
        assert status["error_message"] == _STOP
        bindings = status["progress"].get("temporal_scope_context_world_read_bindings", {})
        if selection == "legacy":
            assert observed["handoff"] is not None
            assert bindings == {}
        elif selection == "matching":
            handoffs = [observed["handoff"], *observed["child_handoffs"].values()]
            for handoff in handoffs:
                matching = [
                    row
                    for row in bindings.values()
                    if row["context_content_hash"] == handoff.context.content_hash
                ]
                assert len(matching) == 1
                binding = matching[0]
                assert binding["consumer_stage"] == "cycle_substrate_context_admission"
                assert binding["status"] == "verified"
                assert binding["content_query_digest"] == fabric.content_query_digest
                assert binding["context_job_ref"] == handoff.context_job_ref.model_dump(mode="json")
                assert (
                    handoff.context.content_hash,
                    handoff.context_job_ref,
                ) in observed["writer_refs"]
                assert handoff.context_job_ref.manifest_profile_sha256 is not None
                assert (
                    handoff.n4_child_profile_family_ref
                    == observed["handoff"].n4_child_profile_family_ref
                )
        else:
            assert len(bindings) == 1
            binding = next(iter(bindings.values()))
            assert observed["handoff"] is None, "generic sibling bypassed temporal gate"
            assert binding["status"] == "not_established"
            assert binding["limitation_codes"] == ["nl_temporal_scope_context_snapshot_mismatch"]

    reopened_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    reopened_kwargs = dict(prepared.app_kwargs)
    reopened_kwargs["container_overrides"] = RuntimeContainerOverrides(
        runtime_api_context=reopened_context
    )
    fresh_app = create_runtime_api_app(**reopened_kwargs)
    with (
        tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
        TestClient(fresh_app) as fresh,
    ):
        response = fresh.get(f"/api/v1/control/jobs/{job_id}")
        assert response.status_code == 200, response.text
        assert (
            response.json()["progress"].get("temporal_scope_context_world_read_bindings", {})
            == bindings
        )
        for key, binding in bindings.items():
            ref = response.json()["runtime_quality_artifact_refs"][
                "temporal_context_candidate:" + key
            ]
            assert ref == binding["context_job_ref"]
            manifest = fresh.get(
                f"/api/v1/artifacts/{ref['artifact_id']}",
                params={"manifest_profile_sha256": ref["manifest_profile_sha256"]},
            )
            assert manifest.status_code == 200, manifest.text
            assert (
                manifest.json()["artifact"]["manifest_profile_sha256"]
                == (ref["manifest_profile_sha256"])
            )
