"""Current-source and emission falsifiers for the production S8 generation bridge."""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.http.services.control import generation_cycle as bridge
from polisyos.runtime.quality.design_axes import value_choice_provenance as s8
from tests._helpers.artifacts import overwrite_signature_sidecar_for_test
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _run_controlled_simulate_only_job_fixture,
    _signed_generation_evidence,
)


@pytest.fixture(scope="module")
def compiled_payload(tmp_path_factory):
    """Capture the existing owner-bound N4→N5 control worker source."""
    with pytest.MonkeyPatch.context() as patches:
        fixture = asyncio.run(
            _run_controlled_simulate_only_job_fixture(
                patches,
                tmp_path_factory.mktemp("controlled-profile-n5"),
            )
        )
        try:
            return canon.from_canonical_bytes(fixture.compiled_payload)
        finally:
            fixture.service.close()


def test_compiled_payload_is_controlled_profile_candidate_n5(compiled_payload):
    """The normative owner fixture must come from the admitted N4→N5 station."""
    compiled = bridge.CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)

    assert compiled.cycle_substrate_context_ref is not None
    assert compiled.recursive_run.leaf_nodes
    for leaf in compiled.recursive_run.leaf_nodes:
        assert leaf.cycle_run is not None
        assert leaf.cycle_run.cycles
        assert leaf.cycle_run.cycles[-1].simulation.status == "joint_simulated"
        assert leaf.cycle_run.promotion_port.status == "not_promoted"
        assert leaf.cycle_run.promotion_port.certified_candidate_ids == ()


@pytest.fixture
def station(tmp_path, compiled_payload):
    service = _build_control_service(tmp_path)
    compiled = bridge.CompiledRecursiveGenerationCycleRun.model_validate(compiled_payload)
    source_ref = service._put_json_artifact(
        compiled.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
    )
    try:
        yield service, compiled, source_ref
    finally:
        service.close()


def _put_sidecar(service, payload):
    ref = service._artifact_store.put_json(
        payload,
        artifacts.PutOptions(
            kind=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
                version=bridge.NORMATIVE_RUN_DISPOSITION_SCHEMA,
            ),
        ),
    )
    return str(ref.artifact_id)


def _current(service, ref, source_ref, now):
    return service._current_normative_generation_projection(
        disposition_ref=ref, compiled_run_ref=source_ref, evaluated_at=now
    )


@pytest.mark.parametrize(
    "default", ["silent_equal_weight", "historical_prior", "proxy_as_priority"]
)
def test_silent_default_cannot_cross_leaf_and_composition_emission(station, default):
    service, compiled, source_ref = station
    now = datetime.now(UTC)
    result = service.resolve_generation_value_choices(compiled_run_ref=source_ref, evaluated_at=now)
    payload = result.model_dump(mode="json")
    node = next(iter(payload["leaf_dispositions"]))
    leaf = payload["leaf_dispositions"][node]
    chosen = compiled.recursive_run.leaf_nodes[0].cycle_run.candidate_summaries[0].candidate_id
    leaf["authorization_status"] = "authorized"
    leaf["ranked_recommendations"] = [chosen]
    leaf["decision_request"] = None
    # Deliberately coherently falsify both layers; a copied status checksum is no oracle.
    leaf_ref = service._artifact_store.put_json(
        leaf,
        artifacts.PutOptions(
            kind=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
                version=s8.NORMATIVE_GENERATION_DISPOSITION_SCHEMA_VERSION,
            ),
        ),
    )
    payload["leaf_disposition_refs"][node] = str(leaf_ref.artifact_id)
    payload["authorization_status"] = "authorized"
    payload["ranked_recommendations"] = [chosen]
    forged_ref = _put_sidecar(service, payload)
    projection = _current(service, forged_ref, source_ref, now)
    assert projection["authorization_status"] == "blocked", default
    assert projection["ranked_recommendations"] == [], default
    assert projection["reason_codes"] == ["p20_normative_generation_disposition_mismatch"]


def test_compiled_owner_rejects_leaf_graft_even_when_s8_leaf_is_valid(station):
    service, _, source_ref = station
    now = datetime.now(UTC)
    result = service.resolve_generation_value_choices(compiled_run_ref=source_ref, evaluated_at=now)
    payload = result.model_dump(mode="json")
    node = next(iter(result.leaf_dispositions))
    owner = bridge.normative_owner_for_runtime_store(
        service._artifact_store,
        service._normative_authority_trust,
        repo_root=service._repo_root,
    )
    binding = result.leaf_dispositions[node].generation_binding.model_copy(
        update={
            "compiled_run_ref": "sha256:" + "d" * 64,
        }
    )
    foreign_ref = owner.produce_generation_disposition(
        binding=binding, evidence=None, evaluated_at=now
    )
    foreign_leaf = owner.project_generation_disposition(foreign_ref, evaluated_at=now)
    assert foreign_leaf.compiled_membership_status == "not_established"
    payload["leaf_disposition_refs"][node] = foreign_ref
    payload["leaf_dispositions"][node] = foreign_leaf.model_dump(mode="json")
    forged_ref = _put_sidecar(service, payload)
    projected = _current(service, forged_ref, source_ref, now)
    assert projected["authorization_status"] == "blocked"
    assert projected["reason_codes"] == ["p20_normative_compiled_leaf_binding_mismatch"]


def test_same_display_ids_do_not_bind_another_current_compiled_source(station):
    service, compiled, source_ref = station
    now = datetime.now(UTC)
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="authorized")
    )
    authorized = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=evidence, evaluated_at=now
    )
    assert authorized.authorization_status == "authorized"
    payload = gy_artifact_self_identity_projection(compiled)
    payload["recursive_run"].pop("leaf_nodes", None)
    payload["cycle_substrate_context_ref"] = "sha256:" + "a" * 64
    other = bridge.CompiledRecursiveGenerationCycleRun.model_validate(
        {
            **payload,
            "content_hash": gy_content_hash(payload),
        }
    )
    other_ref = service._put_json_artifact(
        other.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
    )
    assert other_ref != source_ref
    original_identities = {
        (node.node_ref, summary.candidate_id)
        for node in compiled.recursive_run.leaf_nodes
        for summary in node.cycle_run.candidate_summaries
    }
    other_identities = {
        (node.node_ref, summary.candidate_id)
        for node in other.recursive_run.nodes
        if not node.child_refs
        for summary in node.cycle_run.candidate_summaries
    }
    assert original_identities == other_identities
    assert other.recursive_run.content_hash == compiled.recursive_run.content_hash
    projected = _current(service, authorized.disposition_ref, other_ref, now)
    assert projected["authorization_status"] == "blocked"
    assert projected["reason_codes"] == ["p20_normative_compiled_run_substitution"]
    fresh = service.resolve_generation_value_choices(
        compiled_run_ref=other_ref,
        evidence=evidence,
        evaluated_at=now,
    )
    assert fresh.authorization_status == "blocked"
    assert next(iter(fresh.leaf_dispositions.values())).decision_request.reason_codes == (
        "p20_normative_frontier_source_mismatch",
    )
    assert {
        (node, leaf.generation_binding.source_run_ref)
        for node, leaf in authorized.leaf_dispositions.items()
    } != {
        (node, leaf.generation_binding.source_run_ref)
        for node, leaf in fresh.leaf_dispositions.items()
    }


@pytest.mark.parametrize("mutation", ["source_node", "disposition_node", "front", "status"])
def test_complete_composition_identity_and_projection_are_recomputed(station, mutation):
    service, _, source_ref = station
    now = datetime.now(UTC)
    result = service.resolve_generation_value_choices(compiled_run_ref=source_ref, evaluated_at=now)
    payload = result.model_dump(mode="json")
    if mutation == "source_node":
        payload["strangle_receipt"]["source_node_refs"] = []
    elif mutation == "disposition_node":
        payload["leaf_disposition_refs"] = {}
    elif mutation == "front":
        next(iter(payload["leaf_dispositions"].values()))["candidate_fronts"] = {}
    else:
        payload["authorization_status"] = "authorized"
    projected = _current(service, _put_sidecar(service, payload), source_ref, now)
    assert projected["authorization_status"] == "blocked"
    assert projected["ranked_recommendations"] == []
    assert projected.get("reason_codes")


@pytest.mark.parametrize(
    "raw", [{"trust": {"principals": ["fake"]}}, "invalid", {"by_node": {"novel": {}}}]
)
def test_malformed_evidence_is_persisted_refusal_not_ignored(station, raw):
    service, _, source_ref = station
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref,
        evidence=bridge.parse_normative_run_evidence(raw),
        evaluated_at=datetime.now(UTC),
    )
    assert result.authorization_status == "blocked"
    assert next(iter(result.leaf_dispositions.values())).decision_request.reason_codes == (
        "p20_normative_evidence_invalid",
    )


def test_current_permission_expiry_overrides_persisted_green(station):
    service, compiled, source_ref = station
    now = datetime.now(UTC)
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="authorized")
    )
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=evidence, evaluated_at=now
    )
    assert result.authorization_status == "authorized"
    projected = _current(service, result.disposition_ref, source_ref, now + timedelta(days=2))
    assert projected["authorization_status"] == "blocked"
    assert projected["ranked_recommendations"] == []


def test_current_signature_corruption_revokes_recommendation(station, tmp_path: Path):
    service, compiled, source_ref = station
    now = datetime.now(UTC)
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="authorized")
    )
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=evidence, evaluated_at=now
    )
    assert result.authorization_status == "authorized"
    authorization_ref = next(iter(evidence.by_node.values())).authorization_ref
    signature = service._artifact_store.get_signature(authorization_ref)
    assert signature is not None
    corrupted_signature = signature.model_copy(
        update={
            "signature_hex": (
                "00" if signature.signature_hex[:2] != "00" else "01"
            )
            + signature.signature_hex[2:]
        }
    )
    overwrite_signature_sidecar_for_test(
        service._artifact_store,
        authorization_ref,
        corrupted_signature,
        tmp_root=tmp_path,
    )
    projection = _current(service, result.disposition_ref, source_ref, now)
    assert projection["authorization_status"] == "blocked"
    assert projection["ranked_recommendations"] == []
    assert set(projection["leaf_dispositions"]) == set(result.leaf_dispositions)


def test_signed_frontier_must_bind_actual_source_not_same_candidate_names(station):
    service, compiled, source_ref = station
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="wrong_frontier_source")
    )
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=evidence, evaluated_at=datetime.now(UTC)
    )
    assert result.authorization_status == "blocked"
    assert result.ranked_recommendations == ()
    assert next(iter(result.leaf_dispositions.values())).decision_request.reason_codes == (
        "p20_normative_frontier_source_mismatch",
    )


def test_legacy_v1_composition_replays_without_currentness_or_authority(station, monkeypatch):
    """A historical v1 claim replays byte-for-byte but cannot carry present authority."""
    from polisyos.runtime.quality import generation_cycle as n6

    service, compiled, source_ref = station
    now = datetime.now(UTC)
    owner = bridge.normative_owner_for_runtime_store(
        service._artifact_store,
        service._normative_authority_trust,
        repo_root=service._repo_root,
    )
    node = compiled.recursive_run.leaf_nodes[0]
    run = node.cycle_run
    assert run is not None
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="authorized")
    ).by_node[node.node_ref]
    binding = s8.NormativeGenerationBinding(
        compiled_run_ref=source_ref,
        source_run_ref="sha256:" + canon.content_hash(
            canon.to_canonical_bytes(run.model_dump(mode="json"), canon.CanonSpec(forbid_floats=False))
        ),
        node_ref=node.node_ref,
    )
    leaf = s8.NormativeGenerationDisposition(
        generation_binding=binding,
        case_id=run.cycles[0].revision_request.revised_problem.design_problem_id,
        candidate_fronts=run.fronts.candidate_ids_by_front(),
        evidence=evidence,
        authorization_status="authorized",
        ranked_recommendations=(run.candidate_summaries[0].candidate_id,),
        admitted_at=now,
        trust_epoch=service._normative_authority_trust.epoch,
    )
    leaf_ref = service._artifact_store.put_json(
        leaf.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
                version=s8.NORMATIVE_GENERATION_DISPOSITION_SCHEMA_VERSION,
            ),
        ),
    )
    outer = bridge.NormativeRunDisposition(
        compiled_run_ref=source_ref,
        leaf_disposition_refs={node.node_ref: str(leaf_ref.artifact_id)},
        leaf_dispositions={node.node_ref: leaf},
        authorization_status="authorized",
        ranked_recommendations=leaf.ranked_recommendations,
        strangle_receipt=bridge.NormativeRunStrangleReceipt(
            compiled_run_ref=source_ref,
            source_node_refs=(node.node_ref,),
            disposition_node_refs=(node.node_ref,),
        ),
    )
    outer_ref = _put_sidecar(service, outer.model_dump(mode="json"))
    outer_bytes = service._artifact_store.get_bytes(
        artifacts.ArtifactID.model_validate(outer_ref)
    )
    currentness_calls: list[dict[str, object]] = []

    def unexpected_currentness_read(**kwargs: object) -> n6.N6DeploymentCurrentnessObservation:
        currentness_calls.append(dict(kwargs))
        raise AssertionError("historical replay must not query live currentness")

    monkeypatch.setattr(n6, "observe_n6_deployment_currentness", unexpected_currentness_read)
    replay = bridge.replay_normative_run_disposition(
        store=service._artifact_store,
        owner=owner,
        disposition_ref=outer_ref,
        compiled_run_ref=source_ref,
    )
    assert replay.disposition.model_dump(mode="json") == outer.model_dump(mode="json")
    assert not replay.admission_authority_established
    assert currentness_calls == []

    projected = bridge.project_normative_run_disposition(
        store=service._artifact_store,
        owner=owner,
        disposition_ref=outer_ref,
        compiled_run_ref=source_ref,
        evaluated_at=now,
    )
    assert projected.authorization_status == "blocked"
    assert projected.ranked_recommendations == ()
    assert (
        "p20_normative_generation_admission_currentness_not_recorded"
        in projected.leaf_dispositions[node.node_ref].decision_request.reason_codes
    )
    assert service._artifact_store.get_bytes(artifacts.ArtifactID.model_validate(outer_ref)) == (
        outer_bytes
    )
    assert currentness_calls == []

    # Removal probe: route historical replay through the current projector while
    # retaining the same v1 refs/markers. It must detect the history/current delta.
    with monkeypatch.context() as removed_history_boundary:
        removed_history_boundary.setattr(
            owner,
            "replay_generation_disposition",
            lambda ref: owner.project_generation_disposition(ref, evaluated_at=now),
        )
        with pytest.raises(
            s8.P20NormativeChoiceError,
            match="p20_normative_composition_content_mismatch",
        ):
            bridge.replay_normative_run_disposition(
                store=service._artifact_store,
                owner=owner,
                disposition_ref=outer_ref,
                compiled_run_ref=source_ref,
            )


def test_outer_v1_replay_rejects_noncanonical_bytes_and_manifest_schema(station, monkeypatch):
    """The outer owner must replay its emitted wire bytes and exact v1 profile."""
    service, _, source_ref = station
    now = datetime.now(UTC)
    owner = bridge.normative_owner_for_runtime_store(
        service._artifact_store,
        service._normative_authority_trust,
        repo_root=service._repo_root,
    )
    emitted = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=None, evaluated_at=now
    )
    assert emitted.disposition_ref is not None
    outer_ref = emitted.disposition_ref
    store = service._artifact_store
    raw = store.get_bytes(artifacts.ArtifactID.model_validate(outer_ref))
    canonical = bridge.replay_normative_run_disposition(
        store=store,
        owner=owner,
        disposition_ref=outer_ref,
        compiled_run_ref=source_ref,
    )
    assert canonical.disposition.disposition_ref == outer_ref

    options = artifacts.PutOptions(
        kind=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
            version=bridge.NORMATIVE_RUN_DISPOSITION_SCHEMA,
        ),
    )
    variant_ref = str(store.put_bytes(raw + b" \n", options).artifact_id)
    assert canon.from_canonical_bytes(store.get_bytes(variant_ref)) == (
        canon.from_canonical_bytes(raw)
    )
    with pytest.raises(bridge.P20NormativeChoiceError, match="outer_v1_bytes_mismatch"):
        bridge.replay_normative_run_disposition(
            store=store,
            owner=owner,
            disposition_ref=variant_ref,
            compiled_run_ref=source_ref,
        )

    original_get_manifest = store.get_manifest
    for name, version in (
        ("runtime.wrong_composition", bridge.NORMATIVE_RUN_DISPOSITION_SCHEMA),
        (bridge.NORMATIVE_RUN_DISPOSITION_KIND, "policyos.normative_generation_composition.v0"),
    ):
        wrong_schema = artifacts.SchemaInfo(name=name, version=version)

        def manifest_with_wrong_schema(artifact_id, schema=wrong_schema):
            manifest = original_get_manifest(artifact_id)
            if str(artifact_id) == outer_ref:
                return manifest.model_copy(update={"artifact_schema": schema})
            return manifest

        with monkeypatch.context() as changed_manifest:
            changed_manifest.setattr(store, "get_manifest", manifest_with_wrong_schema)
            with pytest.raises(
                bridge.P20NormativeChoiceError,
                match="outer_v1_schema_mismatch",
            ):
                bridge.replay_normative_run_disposition(
                    store=store,
                    owner=owner,
                    disposition_ref=outer_ref,
                    compiled_run_ref=source_ref,
                )


@pytest.mark.parametrize("sidecar_ref", [None, "sha256:" + "f" * 64])
def test_missing_or_unresolved_sidecar_preserves_current_source_fronts(station, sidecar_ref):
    service, compiled, source_ref = station
    projected = _current(service, sidecar_ref, source_ref, datetime.now(UTC))
    assert projected["authorization_status"] == "blocked"
    assert projected["ranked_recommendations"] == []
    assert set(projected["leaf_dispositions"]) == {
        node.node_ref for node in compiled.recursive_run.leaf_nodes
    }
    for node in compiled.recursive_run.leaf_nodes:
        actual = projected["leaf_dispositions"][node.node_ref]
        assert actual["candidate_fronts"] == {
            key: list(values)
            for key, values in node.cycle_run.fronts.candidate_ids_by_front().items()
        }
        assert actual["decision_request"]["reason_codes"] == [
            "p20_normative_generation_disposition_missing"
            if sidecar_ref is None
            else "p20_normative_sidecar_replay_failed"
        ]
    replay = _current(service, projected["refusal_disposition_ref"], source_ref, datetime.now(UTC))
    assert replay["authorization_status"] == "blocked"


@pytest.mark.parametrize("reader", ["get_job_status", "get_latest_job_for_run"])
def test_every_current_job_reader_replays_persisted_authority(station, monkeypatch, reader):
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord

    service, compiled, source_ref = station
    now = datetime.now(UTC)
    evidence = bridge.NormativeRunEvidenceRefs.model_validate(
        _signed_generation_evidence(service, compiled, fault="authorized")
    )
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evidence=evidence, evaluated_at=now
    )
    assert result.authorization_status == "authorized"
    record = ControlJobRecord(
        job_id="fixture:current-job",
        kind="natural_language_run",
        state="completed",
        run_id="fixture:current-run",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by=None,
        created_at=now,
        started_at=now,
        finished_at=now,
        lease_owner=None,
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={
            "normative_disposition_ref": result.disposition_ref,
            "compiled_recursive_generation_cycle_ref": source_ref,
            "normative_disposition": result.model_dump(mode="json"),
        },
    )
    service._publish_generation_run(
        job=record,
        payload={"run_id": record.run_id, "tenant_id": "tenant-fixture", "cell_id": "cell-fixture"},
        compiled_run_ref=source_ref,
        normative_disposition_ref=result.disposition_ref,
    )
    monkeypatch.setattr(service._control_store, "get_job", lambda _: record)
    monkeypatch.setattr(service._control_store, "get_latest_job_by_run", lambda _: record)
    response = getattr(service, reader)("fixture:key")
    assert response.progress["normative_disposition"]["authorization_status"] == "authorized"

    class AfterExpiry(datetime):
        @classmethod
        def now(cls, tz=None):
            return now + timedelta(days=2)

    monkeypatch.setattr(run_lifecycle, "datetime", AfterExpiry)
    response = getattr(service, reader)("fixture:key")
    assert response.progress["normative_disposition"]["authorization_status"] == "blocked"
    assert response.progress["normative_disposition"]["ranked_recommendations"] == []
    # Restoring time never licenses a stored caller override or missing source.
    monkeypatch.setattr(run_lifecycle, "datetime", datetime)
    record = replace(
        record, progress={"normative_disposition": {"authorization_status": "authorized"}}
    )
    response = getattr(service, reader)("fixture:key")
    assert response.progress["normative_disposition"]["authorization_status"] == "blocked"


def test_data_only_leaf_growth_preserves_complete_source_identity_sets(station):
    """Two fixture router nodes reuse real generated candidate data; no promotion is claimed."""
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveGenerationCycleRun

    service, compiled, _ = station
    original = compiled.recursive_run
    leaf = original.leaf_nodes[0]
    root_ref, children = "fixture:growing-root", ("fixture:novel-A", "fixture:novel-B")
    graph = bridge.derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=children,
        parent_child_edges=[(root_ref, child) for child in children],
        rule_version_ref=original.recursive_graph.rule_version_ref,
    )
    payload = gy_artifact_self_identity_projection(original)
    payload.update(
        recursive_graph=graph.model_dump(mode="json"),
        recursive_graph_ref=graph.graph_ref,
        recursive_graph_content_hash=gy_content_hash(graph.model_dump(mode="json")),
        root_node_ref=root_ref,
        observed_max_depth=1,
        recursive_budget={
            **original.recursive_budget.model_dump(mode="json"),
            "max_nodes": 3,
            "max_depth": 1,
        },
        nodes=[
            {
                **leaf.model_dump(mode="json"),
                "node_ref": root_ref,
                "cycle_run": None,
                "child_refs": list(children),
            },
            *[
                {
                    **leaf.model_dump(mode="json"),
                    "node_ref": child,
                    "parent_ref": root_ref,
                    "depth": 1,
                }
                for child in children
            ],
        ],
    )
    recursive = RecursiveGenerationCycleRun.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )
    envelope = gy_artifact_self_identity_projection(compiled)
    envelope["recursive_run"] = recursive.model_dump(mode="json")
    grown = bridge.CompiledRecursiveGenerationCycleRun.model_validate(
        {**envelope, "content_hash": gy_content_hash(envelope)}
    )
    source_ref = service._put_json_artifact(
        grown.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
    )
    result = service.resolve_generation_value_choices(
        compiled_run_ref=source_ref, evaluated_at=datetime.now(UTC)
    )
    source_nodes = {
        node.node_ref for node in grown.recursive_run.nodes if node.cycle_run is not None
    }
    assert source_nodes == set(grown.recursive_run.recursive_graph.node_refs) - {root_ref}
    assert set(result.leaf_dispositions) == source_nodes == set(children)
    source_candidates = {
        (node.node_ref, row.candidate_id)
        for node in grown.recursive_run.leaf_nodes
        for row in node.cycle_run.candidate_summaries
    }
    projected_candidates = {
        (node, candidate)
        for node, item in result.leaf_dispositions.items()
        for members in item.candidate_fronts.values()
        for candidate in members
    }
    assert source_candidates == projected_candidates
    assert result.authorization_status == "blocked"
    assert result.ranked_recommendations == ()
    assert all(item.decision_request is not None for item in result.leaf_dispositions.values())


def test_runtime_cas_adapter_preserves_guarded_owner_and_rejects_impostor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.security import tenant_scope
    from polisyos.runtime.http.dependencies import build_runtime_api_context

    context = build_runtime_api_context(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    try:
        trust = s8.NormativeAuthorityTrust()
        verifier = context.signature_verifier
        assert verifier is not None  # noqa: S101
        worker_calls: list[tuple[str, str]] = []
        caller_thread = threading.current_thread().name
        guard = context.store._guard
        original_run = guard.run

        def record_guarded_worker(
            func: Callable[..., object], *args: object, **kwargs: object
        ) -> object:
            operation = getattr(func, "__name__", "<callable>")

            def record_worker(*inner_args: object, **inner_kwargs: object) -> object:
                worker_calls.append((operation, threading.current_thread().name))
                return func(*inner_args, **inner_kwargs)

            return original_run(record_worker, *args, **kwargs)

        monkeypatch.setattr(guard, "run", record_guarded_worker)
        kind = "test.r13.guarded_owner_read_probe"
        schema = "test.r13.guarded_owner_read_probe.v1"
        payload = {"probe": "owner-read-through-runtime-guard", "candidate_only": True}
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            stored = context.store.put_json(
                payload,
                artifacts.PutOptions(
                    kind=kind,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(name=kind, version=schema),
                ),
            )
        seed_worker_calls = tuple(worker_calls)
        assert "put_json" in {name for name, _thread in seed_worker_calls}  # noqa: S101
        assert all(thread_name != caller_thread for _name, thread_name in seed_worker_calls)  # noqa: S101
        source_ref = str(stored.artifact_id)

        if os.environ.get("POLISYOS_R13_DIRECT_TARGET_REMOVAL_PROBE") == "1":
            # Default off. This keeps the bytes/ref/manifest fixed and removes only
            # adapter custody, so the worker-operation assertion below must turn red.
            def direct_target_adapter(
                store: artifacts.ArtifactStore,
                deployment_trust: s8.NormativeAuthorityTrust,
                *,
                signature_verifier: artifacts.SignatureVerifyingArtifactStore | None = None,
                repo_root: Path | None = None,
            ) -> s8.NormativeValueScheduleOwner:
                del signature_verifier
                return s8.NormativeValueScheduleOwner(
                    store=store._target,
                    trust=deployment_trust,
                    repo_root=repo_root,
                )

            monkeypatch.setattr(
                bridge, "normative_owner_for_runtime_store", direct_target_adapter
            )

        owner = bridge.normative_owner_for_runtime_store(
            context.store, trust, signature_verifier=verifier
        )
        worker_calls.clear()
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            observed = owner._read(source_ref, kind=kind, schema=schema)
            owner_read_calls = tuple(worker_calls)
            manifest_after = context.store.get_manifest(stored.artifact_id)

        assert observed == payload  # noqa: S101
        assert str(stored.artifact_id) == source_ref  # noqa: S101
        assert manifest_after.kind == kind  # noqa: S101
        assert manifest_after.artifact_schema is not None  # noqa: S101
        assert manifest_after.artifact_schema.version == schema  # noqa: S101
        owner_worker_operations = {name for name, _thread in owner_read_calls}
        assert {"get_bytes", "get_manifest"} <= owner_worker_operations  # noqa: S101
        assert all(thread_name != caller_thread for _name, thread_name in owner_read_calls)  # noqa: S101
        assert owner._store is context.store  # noqa: S101
        assert owner._signature_verifier is verifier  # noqa: S101

        # The authority capability is optional for candidate/blocked computation.
        # V2 owner tests separately prove signed evidence stays typed-blocked without it.
        candidate_owner = bridge.normative_owner_for_runtime_store(context.store, trust)
        assert candidate_owner._store is context.store  # noqa: S101
        assert candidate_owner._signature_verifier is None  # noqa: S101
        worker_calls.clear()
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            candidate_observed = candidate_owner._read(
                source_ref, kind=kind, schema=schema
            )
            candidate_worker_calls = tuple(worker_calls)
        assert candidate_observed == payload  # noqa: S101
        assert {"get_bytes", "get_manifest"} <= {  # noqa: S101
            name for name, _thread in candidate_worker_calls
        }

        class Fake:
            _target = context.store

        with pytest.raises(
            s8.P20NormativeChoiceError, match="p20_normative_signed_store_unavailable"
        ):
            bridge.normative_owner_for_runtime_store(Fake(), trust)

        # Foreign tenant/cell reads remain refused by the same guarded owner.
        for tenant_id, cell_id in (("tenant-b", "cell-a"), ("tenant-a", "cell-b")):
            worker_calls.clear()
            with (
                tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
                pytest.raises(s8.P20NormativeChoiceError) as refused,
            ):
                owner._read(source_ref, kind=kind, schema=schema)
            assert refused.value.code == s8.P20_VALUE_SCHEDULE_REF_UNRESOLVABLE_CODE  # noqa: S101
            assert any(name == "get_bytes" for name, _thread in worker_calls)  # noqa: S101
    finally:
        context.store.close()

def test_s8_rejects_post_v1_field_from_raw_persisted_n6_bytes(tmp_path):
    """S8 checks the persisted historical projection before Pydantic can drop fields."""
    import copy

    from polisyos.runtime.quality.generation_cycle import (
        GENERATION_CYCLE_SCHEMA_VERSION,
        GenerationCycleRun,
        validate_generation_cycle_run,
        validate_generation_cycle_run_history,
    )
    from tests.unit.runtime.quality.historical_artifacts import (
        historical_generation_cycle_v1,
    )

    store = artifacts.FileSystemCAS(tmp_path / "cas")
    payload = historical_generation_cycle_v1()["generation_cycle_run"]
    schema_version = payload["schema_version"]
    put_options = artifacts.PutOptions(
        kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=s8.NORMATIVE_GENERATION_SOURCE_KIND,
            version=schema_version,
        ),
    )
    valid_ref = str(
        store.put_json(payload, put_options, canon_spec=canon.CanonSpec(forbid_floats=False))
        .artifact_id
    )
    owner = s8.NormativeValueScheduleOwner(
        store=store,
        trust=s8.NormativeAuthorityTrust(),
        repo_root=None,
    )
    assert owner._read(
        valid_ref,
        kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
        schema=GENERATION_CYCLE_SCHEMA_VERSION,
    ) == payload
    canonical_raw = canon.to_canonical_bytes(
        payload, canon.CanonSpec(forbid_floats=False)
    )
    assert store.get_bytes(valid_ref) == canonical_raw
    assert validate_generation_cycle_run_history(payload) == ()
    assert "strangle_receipt_currentness_not_established" in {
        str(issue.get("code"))
        for issue in validate_generation_cycle_run(GenerationCycleRun.model_validate(payload))
    }

    noncanonical_ref = str(store.put_bytes(canonical_raw + b" \n", put_options).artifact_id)
    assert canon.from_canonical_bytes(store.get_bytes(noncanonical_ref)) == payload
    with pytest.raises(
        s8.P20NormativeChoiceError,
        match="p20_normative_generation_history_invalid",
    ):
        owner._read(
            noncanonical_ref,
            kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
            schema=GENERATION_CYCLE_SCHEMA_VERSION,
        )

    mutated = copy.deepcopy(payload)
    mutated["source_handoff_refs"] = []
    assert GenerationCycleRun.model_validate(mutated).model_dump(mode="json") == payload
    invalid_ref = str(
        store.put_json(
            mutated,
            put_options,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        ).artifact_id
    )
    binding = s8.NormativeGenerationBinding(
        compiled_run_ref="sha256:" + "a" * 64,
        source_run_ref=invalid_ref,
        node_ref="fixture:n6-leaf",
    )
    with pytest.raises(
        s8.P20NormativeChoiceError,
        match="p20_normative_generation_history_invalid",
    ):
        owner._generation_disposition(
            binding=binding,
            evidence=None,
            evaluated_at=datetime.now(UTC),
        )


def test_app_factory_passes_typed_deployment_trust_to_default_service(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app

    monkeypatch.setenv("POLISYOS_RUNTIME_EXECUTION_PROFILE", "dev")
    trust = s8.NormativeAuthorityTrust(epoch="fixture:deployment-epoch")
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        normative_authority_trust=trust,
    )
    with TestClient(app):
        assert app.state.runtime_container.config.normative_authority_trust is trust
        assert app.state.runtime_container.control_service._normative_authority_trust is trust

def _persist_direct_historical_outer_fixture(tmp_path):
    from polisyos.runtime.quality.generation_cycle import GenerationCycleRun
    from tests.unit.runtime.quality.historical_artifacts import (
        historical_generation_cycle_v1,
    )

    source_payload = historical_generation_cycle_v1()["generation_cycle_run"]
    source_run = GenerationCycleRun.model_validate(source_payload)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source_options = artifacts.PutOptions(
        kind=s8.NORMATIVE_GENERATION_SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=s8.NORMATIVE_GENERATION_SOURCE_KIND,
            version=source_run.schema_version,
        ),
    )
    source_ref = str(
        store.put_json(
            source_payload,
            source_options,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        ).artifact_id
    )
    compiled_ref = "sha256:" + "c" * 64
    node_ref = "fixture:historical-n6-leaf"
    binding = s8.NormativeGenerationBinding(
        compiled_run_ref=compiled_ref,
        source_run_ref=source_ref,
        node_ref=node_ref,
    )
    leaf = s8.NormativeGenerationDisposition(
        generation_binding=binding,
        case_id=source_run.cycles[0].revision_request.revised_problem.design_problem_id,
        candidate_fronts=source_run.fronts.candidate_ids_by_front(),
        evidence=None,
        authorization_status="blocked",
        admitted_at=datetime(2020, 1, 1, tzinfo=UTC),
        trust_epoch="fixture:historical-without-currentness",
    )
    leaf_options = artifacts.PutOptions(
        kind=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
            version=s8.NORMATIVE_GENERATION_DISPOSITION_SCHEMA_VERSION,
        ),
    )
    leaf_ref = str(
        store.put_json(
            leaf.model_dump(mode="json"),
            leaf_options,
            canon_spec=canon.CanonSpec(forbid_floats=False),
        ).artifact_id
    )
    owner = s8.NormativeValueScheduleOwner(
        store=store,
        trust=s8.NormativeAuthorityTrust(),
        repo_root=None,
    )
    outer = bridge.NormativeRunDisposition(
        compiled_run_ref=compiled_ref,
        leaf_disposition_refs={node_ref: leaf_ref},
        leaf_dispositions={node_ref: leaf},
        authorization_status="blocked",
        ranked_recommendations=(),
        strangle_receipt=bridge.NormativeRunStrangleReceipt(
            compiled_run_ref=compiled_ref,
            source_node_refs=(node_ref,),
            disposition_node_refs=(node_ref,),
        ),
    )
    outer_payload = bridge._normative_run_disposition_v1_payload(outer)
    outer_options = artifacts.PutOptions(
        kind=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
            version=bridge.NORMATIVE_RUN_DISPOSITION_V1_SCHEMA,
        ),
    )
    outer_ref = str(
        store.put_json(
            outer_payload,
            outer_options,
            canon_spec=bridge._NORMATIVE_OUTER_V1_CANON,
        ).artifact_id
    )
    return store, owner, leaf, outer, outer_payload, outer_ref, leaf_ref


def test_historical_v1_leaf_replays_without_a_live_source_checkout(tmp_path, monkeypatch):
    """Direct owner replay reads persisted history while current authority stays blocked."""
    from polisyos.runtime.quality import generation_cycle as n6

    _store, owner, leaf, _outer, _payload, _outer_ref, leaf_ref = (
        _persist_direct_historical_outer_fixture(tmp_path)
    )

    def live_currentness_is_not_historical_replay(*args: object, **kwargs: object) -> None:
        raise AssertionError("historical leaf replay must not inspect the live deployment")

    monkeypatch.setattr(n6, "inspect_generation_cycle_run", live_currentness_is_not_historical_replay)
    assert owner.replay_generation_disposition(leaf_ref) == leaf
    assert owner.generation_disposition_admission_currentness(leaf_ref) is None

    current = owner.project_generation_disposition(
        leaf_ref, evaluated_at=datetime.now(UTC)
    )
    assert current.authorization_status == "blocked"
    assert current.decision_request is not None
    assert (
        "p20_normative_generation_admission_currentness_not_recorded"
        in current.decision_request.reason_codes
    )


def test_outer_v1_wire_reader_checks_exact_bytes_and_manifest_profile(tmp_path, monkeypatch):
    """The direct outer-v1 owner accepts canonical history and rejects wire/profile drift."""
    store, _owner, _leaf, outer, payload, outer_ref, _leaf_ref = (
        _persist_direct_historical_outer_fixture(tmp_path)
    )
    options = artifacts.PutOptions(
        kind=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
            version=bridge.NORMATIVE_RUN_DISPOSITION_V1_SCHEMA,
        ),
    )
    recorded = bridge._read_normative_run_disposition_v1(store, outer_ref)
    assert bridge._normative_run_disposition_v1_payload(recorded) == payload
    assert recorded.authorization_status == outer.authorization_status == "blocked"
    raw = store.get_bytes(artifacts.ArtifactID.model_validate(outer_ref))

    same_value_ref = str(store.put_bytes(raw + b" \n", options).artifact_id)
    assert canon.from_canonical_bytes(store.get_bytes(same_value_ref)) == payload
    with pytest.raises(
        bridge.P20NormativeChoiceError,
        match="outer_v1_bytes_mismatch",
    ):
        bridge._read_normative_run_disposition_v1(store, same_value_ref)

    original_get_manifest = store.get_manifest
    wrong_schema = artifacts.SchemaInfo(
        name=bridge.NORMATIVE_RUN_DISPOSITION_KIND,
        version="policyos.normative_generation_composition.v0",
    )

    def manifest_with_wrong_schema(artifact_id):
        manifest = original_get_manifest(artifact_id)
        if str(artifact_id) == outer_ref:
            return manifest.model_copy(update={"artifact_schema": wrong_schema})
        return manifest

    with monkeypatch.context() as changed_manifest:
        changed_manifest.setattr(store, "get_manifest", manifest_with_wrong_schema)
        with pytest.raises(
            bridge.P20NormativeChoiceError,
            match="outer_v1_schema_mismatch",
        ):
            bridge._read_normative_run_disposition_v1(store, outer_ref)
