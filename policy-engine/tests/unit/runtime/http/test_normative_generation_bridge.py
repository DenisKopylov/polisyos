"""Current-source and emission falsifiers for the production S8 generation bridge."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.http.services.control import generation_cycle as bridge
from polisyos.runtime.quality.design_axes import value_choice_provenance as s8
from tests.unit.runtime.http.test_control_service_di import (
    _build_control_service,
    _signed_generation_evidence,
)
from tests.unit.runtime.http.test_control_service_di import (
    test_process_nl_job_enters_persisted_tenant_scope as _worker_example,
)


@pytest.fixture(scope="module")
def compiled_payload(tmp_path_factory):
    """Capture a real generated fixture run at the existing production worker boundary."""
    captured = {}
    service_type = _build_control_service.__globals__["ControlPlaneService"]
    original = service_type.resolve_generation_value_choices

    def capture(self, **kwargs):
        ref = artifacts.ArtifactID.model_validate(kwargs["compiled_run_ref"])
        captured["source"] = canon.from_canonical_bytes(self._artifact_store.get_bytes(ref))
        return original(self, **kwargs)

    with pytest.MonkeyPatch.context() as patches:
        patches.setattr(service_type, "resolve_generation_value_choices", capture)
        asyncio.run(_worker_example(patches, tmp_path_factory.mktemp("pa1-worker"), "missing"))
    return captured["source"]


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
        service._artifact_store, service._normative_authority_trust
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


def test_current_signature_corruption_revokes_recommendation(station):
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
    signature.signature_hex = (
        "00" if signature.signature_hex[:2] != "00" else "01"
    ) + signature.signature_hex[2:]
    service._artifact_store.put_signature(authorization_ref, signature)
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


def test_runtime_cas_adapter_reuses_ambient_owner_and_rejects_impostor(tmp_path):
    from polisyos.runtime.http.dependencies import build_runtime_api_context

    context = build_runtime_api_context(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    try:
        owner = bridge.normative_owner_for_runtime_store(
            context.store, s8.NormativeAuthorityTrust()
        )
        assert owner._store is context.store._target

        class Fake:
            _target = owner._store

        with pytest.raises(s8.P20NormativeChoiceError, match="signed_store_unavailable"):
            bridge.normative_owner_for_runtime_store(Fake(), s8.NormativeAuthorityTrust())
    finally:
        context.store.close()


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
