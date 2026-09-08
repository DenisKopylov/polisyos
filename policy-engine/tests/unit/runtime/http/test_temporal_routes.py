from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import EpochValidityGateNonReceipt
from polisyos.core.contracts.runtime import TemporalScope
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.services import temporal as temporal_runtime
from polisyos.runtime.http.services.temporal import TemporalService
from polisyos.runtime.quality import derived_observations as derived_observations_runtime
from polisyos.runtime.quality import epoch_validity_cascade as epoch_validity_runtime
from polisyos.runtime.quality.epoch_staleness_projection import (
    compile_epoch_staleness_projection,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    EpochTransitionSigningNonReceipt,
    NoEpochTransitionSigningAuthority,
)
from polisyos.runtime.quality.semantic_epoch import SemanticEpochService
from polisyos.scientist.governance.continuous.monitors import (
    GOVERNANCE_MONITOR_EVENT_KIND,
    GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME,
    GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION,
)
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)
from tests.unit.runtime.quality.test_derived_observations import (
    _epoch_recompute_fixture,
    _EpochRecomputeFixture,
    _produce_epoch_recompute,
)


def _digest(seed: str) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _absence_projection(*, run_id: str, scope: TemporalScope, observed_at: datetime):
    query_ref = _digest(f"{run_id}:query")
    subject_ref = ArtifactRef(
        artifact_id=_digest(f"{run_id}:subject"),
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    return compile_epoch_staleness_projection(
        run_id=run_id,
        decision_packet_ref=subject_ref,
        temporal_scope=scope,
        requested_query_context_ref=query_ref,
        owner_as_of=None,
        observed_at=observed_at,
        epoch_gate=EpochValidityGateNonReceipt(
            status="not_established",
            code="policy_admission_missing",
            subject_ref=subject_ref,
            requested_query_context_ref=query_ref,
        ),
        transition=EpochTransitionSigningNonReceipt(
            status="not_established",
            code="epoch_transition_signer_not_established",
            predicate_class="not_established",
        ),
    )


def _review_client(
    runtime_api_env,
    *,
    bearer_suffix: str,
    raise_server_exceptions: bool = False,
):
    bearer = _fixture_bearer(bearer_suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=raise_server_exceptions,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-{bearer_suffix}",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    return client, bearer, cell


@dataclass(frozen=True)
class _TemporalRecomputeSetup:
    run: SimpleNamespace
    scope: TemporalScope
    requested_query_context_ref: str
    fixture: _EpochRecomputeFixture
    persisted: derived_observations_runtime.PersistedEpochInheritanceRecomputeReceipt
    temporal: TemporalService


def _temporal_recompute_setup(
    tmp_path: Path,
    *,
    run_id: str,
) -> _TemporalRecomputeSetup:
    run = SimpleNamespace(run_id=run_id, decision_packet_ref=None)
    scope = TemporalScope(valid_at=datetime(2026, 8, 30, tzinfo=UTC))
    scope_payload = {
        "run_id": run.run_id,
        "decision_packet_ref": None,
        "temporal_scope": scope.model_dump(mode="json"),
    }
    scope_ref = temporal_runtime._semantic_digest(
        "polisyos.runtime.epoch-staleness.scope.v1",
        scope_payload,
    )
    requested_cutoff_ref = temporal_runtime._semantic_digest(
        "polisyos.runtime.epoch-staleness.run-cutoff.v1",
        {"run_id": run.run_id},
    )
    requested_query_context_ref = temporal_runtime._semantic_digest(
        "polisyos.runtime.epoch-staleness.query.v1",
        {
            **scope_payload,
            "scope_ref": scope_ref,
            "requested_cutoff_ref": requested_cutoff_ref,
        },
    )
    fixture = _epoch_recompute_fixture(
        tmp_path,
        authority_purpose="decision_validity",
    )
    transition_payload = fixture.transition.model_dump(
        mode="python",
        exclude={"transition_content_hash"},
    )
    transition_payload["requested_query_context_ref"] = requested_query_context_ref
    transition = epoch_validity_runtime.EpochValidityTransitionArtifact(
        **transition_payload,
        transition_content_hash=epoch_validity_runtime._semantic_hash(
            "polisyos.epoch.validity-transition.v1",
            transition_payload,
        ),
    )
    transition_ref = fixture.store.put_bytes(
        epoch_validity_runtime._canonical_bytes(transition),
        ArtifactWriteOptions(
            kind=derived_observations_runtime.EPOCH_VALIDITY_TRANSITION_KIND,
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )
    rebound = replace(
        fixture,
        transition=transition,
        transition_ref=transition_ref,
        query_ref=requested_query_context_ref,
    )
    persisted = _produce_epoch_recompute(rebound)
    temporal = TemporalService(
        artifact_store=fixture.store,
        semantic_epoch_service=SemanticEpochService.for_unallocated_policy_query(
            artifact_store=fixture.store
        ),
        transition_signing_authority=NoEpochTransitionSigningAuthority(),
    )
    return _TemporalRecomputeSetup(
        run=run,
        scope=scope,
        requested_query_context_ref=requested_query_context_ref,
        fixture=rebound,
        persisted=persisted,
        temporal=temporal,
    )


def test_fabric_decision_data_route_wraps_decision_values_and_echoes_temporal_scope(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    capabilities = client.get(
        "/api/v1/temporal/capabilities",
        params={"run_id": run_id},
    ).json()["capabilities"]
    params = {
        "valid_at": capabilities["valid_range"]["latest"],
        "tx_at": capabilities["tx_range"]["latest"],
        "branch": "main",
    }

    response = client.get(f"/api/v1/runs/{run_id}/fabric-decision-data", params=params)

    assert response.status_code == 200
    assert response.headers["x-temporal-scope"] != "current"
    payload = response.json()
    assert payload["temporal_scope"]["branch"] == "main"
    assert payload["coverage"]["naked_decision_values"] == 0
    assert payload["coverage"]["decision"] >= 1
    assert payload["decision_data"]
    for item in payload["decision_data"]:
        assert item["kind"] == "quantity"
        assert set(item) >= {
            "value",
            "source_contract",
            "quality",
            "lineage",
            "access",
            "time",
            "replay",
            "gaps",
        }
        assert item["time"]["branch"] == "main"
        assert item["source_contract"] == {
            "id": "worldbank.wdi.generic",
            "version": "1.1.0",
        }
        assert item["quality"]["status"] in {"passed", "warning", "failed", "unknown_quality"}
        assert item["lineage"]["compact_summary_ref"].startswith("/api/v1/lineage/")
        assert item["lineage"]["full_graph_ref"].endswith("?view=full")
        assert item["lineage"]["raw_evidence_refs"]
        assert set(item["lineage"]["export_links"]) == {"openlineage", "prov"}


def test_runtime_batches_quality_and_trust_refs_without_n_plus_one(runtime_api_env) -> None:
    container = runtime_api_env["app"].state.runtime_container
    ctx = container.runtime_api_context
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])

    decision_data, coverage = ctx.lineage.build_fabric_decision_data_for_run(run)
    quality_refs = ctx.lineage.build_quality_refs_batch(decision_data)
    trust_refs = ctx.lineage.build_trust_refs_batch(decision_data)

    assert coverage.decision == len(decision_data)
    assert set(quality_refs) == {item.id for item in decision_data}
    assert set(trust_refs) == {item.id for item in decision_data}
    assert all(ref.status == "passed" for ref in quality_refs.values())
    assert all(
        {"quality", "lineage", "access", "replay", "time"} <= set(row)
        for row in trust_refs.values()
    )


def test_fabric_trust_metadata_is_stable_for_same_valid_time_and_different_tx_time(
    runtime_api_env,
) -> None:
    container = runtime_api_env["app"].state.runtime_container
    ctx = container.runtime_api_context
    run = ctx.run_index.get_run(runtime_api_env["core_run_id"])
    valid_at = datetime(2026, 4, 15, 12, tzinfo=UTC)
    early_scope = TemporalScope(
        valid_at=valid_at,
        tx_at=datetime(2026, 4, 16, 9, 20, tzinfo=UTC),
        branch="main",
    )
    late_scope = TemporalScope(
        valid_at=valid_at,
        tx_at=datetime(2026, 4, 26, 10, tzinfo=UTC),
        branch="main",
    )

    early_data, _early_coverage = ctx.lineage.build_fabric_decision_data_for_run(
        run,
        temporal_scope=early_scope,
    )
    late_data, _late_coverage = ctx.lineage.build_fabric_decision_data_for_run(
        run,
        temporal_scope=late_scope,
    )
    early_trust = ctx.lineage.build_trust_refs_batch(early_data)
    late_trust = ctx.lineage.build_trust_refs_batch(late_data)

    assert early_data and late_data
    assert {item.id for item in early_data} == {item.id for item in late_data}
    for item_id in early_trust:
        assert early_trust[item_id]["time"]["valid_at"] == late_trust[item_id]["time"]["valid_at"]
        assert early_trust[item_id]["time"]["tx_at"] != late_trust[item_id]["time"]["tx_at"]
        assert early_trust[item_id]["quality"]["status"] == late_trust[item_id]["quality"]["status"]
        assert early_trust[item_id]["lineage"]["id"] == late_trust[item_id]["lineage"]["id"]


def test_temporal_capabilities_include_fabric_decision_data_surface(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]

    response = client.get("/api/v1/temporal/capabilities", params={"run_id": run_id})

    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    surfaces = {item["surface"]: item for item in capabilities["surfaces"]}
    assert surfaces["run_fabric_decision_data"]["supported"] is True
    assert capabilities["branch_support"] is True
    assert capabilities["snapshot_support"] is True
    assert capabilities["graph_temporal_scope"] == "partial"
    assert "world.world_facts" in capabilities["supported_tables"]


def test_epoch_staleness_route_invokes_canonical_temporal_service(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the service result must change the route, even with markers fixed."""

    client, bearer, _cell = _review_client(
        runtime_api_env,
        bearer_suffix="epoch-staleness-service-dispatch",
        raise_server_exceptions=True,
    )
    run_id = runtime_api_env["core_run_id"]
    calls: list[tuple[str, TemporalScope]] = []

    def project(*, run, scope: TemporalScope, observed_at: datetime):
        calls.append((run.run_id, scope))
        return _absence_projection(run_id=run.run_id, scope=scope, observed_at=observed_at)

    with client:
        temporal = client.app.state.runtime_container.runtime_api_context.temporal
        monkeypatch.setattr(
            temporal,
            "build_epoch_staleness_projection",
            project,
            raising=False,
        )
        response = client.get(
            f"/api/v1/temporal/runs/{run_id}/epoch-staleness",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
            params={"branch": "review-branch"},
        )

    assert response.status_code == 200
    assert calls == [(run_id, TemporalScope(branch="review-branch"))]
    assert response.json()["projection"]["temporal_scope"]["branch"] == "review-branch"


def test_epoch_staleness_route_renders_real_declared_absences_as_usable_state(
    runtime_api_env,
) -> None:
    client, bearer, _cell = _review_client(
        runtime_api_env,
        bearer_suffix="epoch-staleness-declared-absence",
    )
    run_id = runtime_api_env["core_run_id"]

    with client:
        response = client.get(
            f"/api/v1/temporal/runs/{run_id}/epoch-staleness",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )

    assert response.status_code == 200
    projection = response.json()["projection"]
    assert projection["status"] == "not_established"
    assert projection["owner_as_of"] is None
    assert projection["owner_time_reason"] == "owner_time_not_established"
    assert projection["open_world_risk"]["promotion_frozen"] is True
    assert projection["fixture_only"] is False
    institutional = projection["institutional_absences"]
    engineering = projection["engineering_absences"]
    assert {row["title"] for row in institutional} == {"Authority not appointed"}
    assert {row["refusal_code"] for row in institutional} == {
        "policy_admission_missing",
        "epoch_transition_signer_not_established",
    }
    assert all(row["appointment_is_closure_precondition"] is False for row in institutional)
    assert all("MACHINE" in row["inspectable_capabilities"] for row in institutional)
    assert engineering == []


def test_temporal_service_exact_reads_completed_recompute_at_requested_coordinate(
    tmp_path: Path,
) -> None:
    """A persisted owner receipt changes only its exact dependency recompute status."""

    setup = _temporal_recompute_setup(tmp_path, run_id="run-exact-recompute")
    projection = setup.temporal.build_epoch_staleness_projection(
        run=setup.run,
        scope=setup.scope,
        observed_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
    )

    assert projection.status == "not_established"
    assert projection.current_epoch_ref is None
    assert projection.decision_validity_status is None
    assert projection.revalidation_required is False
    assert projection.engineering_absences == ()
    assert {row.refusal_code for row in projection.institutional_absences} == {
        "policy_admission_missing",
        "epoch_transition_signer_not_established",
    }
    assert len(projection.dependencies) == 1
    dependency = projection.dependencies[0]
    assert dependency.disposition == setup.fixture.disposition
    assert dependency.source_classes == ()
    assert dependency.advisory_event_refs == ()
    assert dependency.owner_evidence_refs == ()
    recompute = dependency.recompute
    assert recompute.status == "completed"
    assert recompute.predicate_provenance == "recomputed"
    assert recompute.evidence_ref == setup.persisted.receipt_artifact_ref
    assert recompute.evidence_content_hash == setup.persisted.receipt_content_hash
    assert "derived_recompute_status_not_established" not in projection.limitations

    other_coordinate = setup.temporal.build_epoch_staleness_projection(
        run=setup.run,
        scope=TemporalScope(valid_at=datetime(2026, 8, 31, tzinfo=UTC)),
        observed_at=datetime(2026, 8, 31, 12, tzinfo=UTC),
    )
    assert other_coordinate.dependencies == ()
    assert other_coordinate.current_epoch_ref is None
    assert other_coordinate.decision_validity_status is None
    assert other_coordinate.revalidation_required is False
    assert "derived_recompute_status_not_established" in other_coordinate.limitations


def test_temporal_service_rejects_corrupt_same_coordinate_recompute_receipt(
    tmp_path: Path,
) -> None:
    setup = _temporal_recompute_setup(tmp_path, run_id="run-corrupt-recompute")
    blob_path, _ = setup.fixture.store.get_paths(
        setup.persisted.receipt_artifact_ref.artifact_id
    )
    blob_path.write_bytes(blob_path.read_bytes() + b"corrupt")

    with pytest.raises(RuntimeHTTPError) as exc_info:
        setup.temporal.build_epoch_staleness_projection(
            run=setup.run,
            scope=setup.scope,
            observed_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "epoch_staleness_recompute_receipt_invalid"


def test_temporal_service_rejects_ambiguous_same_coordinate_recompute_receipts(
    tmp_path: Path,
) -> None:
    setup = _temporal_recompute_setup(tmp_path, run_id="run-ambiguous-recompute")
    transition_payload = setup.fixture.transition.model_dump(
        mode="python",
        exclude={"transition_content_hash"},
    )
    transition_payload["current_epoch_ref"] = _digest("ambiguous-current-epoch")
    transition = epoch_validity_runtime.EpochValidityTransitionArtifact(
        **transition_payload,
        transition_content_hash=epoch_validity_runtime._semantic_hash(
            "polisyos.epoch.validity-transition.v1",
            transition_payload,
        ),
    )
    transition_ref = setup.fixture.store.put_bytes(
        epoch_validity_runtime._canonical_bytes(transition),
        ArtifactWriteOptions(
            kind=derived_observations_runtime.EPOCH_VALIDITY_TRANSITION_KIND,
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )
    _produce_epoch_recompute(
        replace(
            setup.fixture,
            transition=transition,
            transition_ref=transition_ref,
        )
    )

    with pytest.raises(RuntimeHTTPError) as exc_info:
        setup.temporal.build_epoch_staleness_projection(
            run=setup.run,
            scope=setup.scope,
            observed_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "epoch_staleness_recompute_receipt_invalid"


def test_epoch_staleness_route_requires_review_and_exact_run_tenant(
    runtime_api_env,
) -> None:
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    reviewer_bearer = _fixture_bearer("epoch-staleness-reviewer")
    viewer_bearer = _fixture_bearer("epoch-staleness-viewer")
    cross_tenant_bearer = _fixture_bearer("epoch-staleness-cross-tenant")
    provider.put_claim(
        reviewer_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-epoch-staleness-reviewer",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    provider.put_claim(
        viewer_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-epoch-staleness-viewer",
            roles=frozenset({PolicyOSRole.VIEWER}),
        ),
    )
    provider.put_claim(
        cross_tenant_bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_b"],
            cell_id=cell.cell_id,
            jti="jwt-epoch-staleness-cross-tenant",
            roles=frozenset({PolicyOSRole.ANALYST}),
        ),
    )
    path = f"/api/v1/temporal/runs/{runtime_api_env['core_run_id']}/epoch-staleness"

    with client:
        reviewer = client.get(
            path,
            headers={
                "Authorization": f"Bearer {reviewer_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )
        viewer = client.get(
            path,
            headers={
                "Authorization": f"Bearer {viewer_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )
        cross_tenant = client.get(
            path,
            headers={
                "Authorization": f"Bearer {cross_tenant_bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_b"],
            },
        )

    assert reviewer.status_code == 200
    assert viewer.status_code == 403
    assert viewer.json()["code"] == "action_permission_denied"
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["code"] == "authorization_binding_run_tenant_mismatch"


def test_epoch_staleness_route_rejects_malformed_owner_artifact(
    runtime_api_env,
) -> None:
    client, bearer, cell = _review_client(
        runtime_api_env,
        bearer_suffix="epoch-staleness-malformed-monitor",
    )
    store = FileSystemCAS(runtime_api_env["cas_root"])
    malformed_ref = store.put_json(
        {"schema_version": "1.0", "event_id": "present-but-incomplete"},
        ArtifactWriteOptions(
            kind=GOVERNANCE_MONITOR_EVENT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=GOVERNANCE_MONITOR_EVENT_SCHEMA_NAME,
                version=GOVERNANCE_MONITOR_EVENT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    store.record_artifact_owner(
        malformed_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.ds18.malformed-monitor",
    )

    with client:
        response = client.get(
            f"/api/v1/temporal/runs/{runtime_api_env['core_run_id']}/epoch-staleness",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
            },
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "epoch_staleness_monitor_artifact_invalid"


def test_epoch_staleness_route_replay_pin_excludes_server_observation_time(
    runtime_api_env,
) -> None:
    client, bearer, _cell = _review_client(
        runtime_api_env,
        bearer_suffix="epoch-staleness-replay",
    )
    path = f"/api/v1/temporal/runs/{runtime_api_env['core_run_id']}/epoch-staleness"
    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }

    with client:
        first = client.get(path, headers=headers)
        projection_hash = first.headers["x-policyos-export-projection-hash"]
        replay = client.get(
            path,
            headers=headers,
            params={"export_projection_hash": projection_hash},
        )
        stale_pin = client.get(
            path,
            headers=headers,
            params={"export_projection_hash": "sha256:" + "0" * 64},
        )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.headers["x-policyos-export-projection-hash"] == projection_hash
    assert first.json()["projection"]["observed_at"] != replay.json()["projection"]["observed_at"]
    assert (
        first.json()["projection"]["projection_semantic_hash"]
        == replay.json()["projection"]["projection_semantic_hash"]
    )
    assert stale_pin.status_code == 409
    assert stale_pin.json()["code"] == "export_replay_pin_mismatch"


def test_epoch_staleness_semantics_do_not_substitute_server_read_time(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    temporal = TemporalService(
        artifact_store=store,
        semantic_epoch_service=SemanticEpochService.for_unallocated_policy_query(
            artifact_store=store
        ),
        transition_signing_authority=NoEpochTransitionSigningAuthority(),
    )
    run = SimpleNamespace(run_id="run-time-role-proof", decision_packet_ref=None)
    scope = TemporalScope(branch="same-owner-state")

    first = temporal.build_epoch_staleness_projection(
        run=run,
        scope=scope,
        observed_at=datetime(2026, 8, 28, 8, 0, tzinfo=UTC),
    )
    second = temporal.build_epoch_staleness_projection(
        run=run,
        scope=scope,
        observed_at=datetime(2026, 8, 28, 9, 0, tzinfo=UTC),
    )

    assert first.observed_at != second.observed_at
    assert first.owner_as_of is None and second.owner_as_of is None
    assert first.projection_semantic_hash == second.projection_semantic_hash
