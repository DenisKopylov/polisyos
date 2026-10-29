"""Real-owner witnesses for write-free world preparation and immutable source replay."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import duckdb
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.foundry.data_plane import prepare_json_input_binding_values
from polisyos.runtime.quality import data_state_substrate as owner
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import (
    SkgCausalPriorRef,
    WorldModelRecord,
    load_world_model_record,
    world_model_artifact_views,
)
from tests._helpers import world_model_record as world_fixture
from tests.integration.core_runtime.test_acquisition_data_preparation import _observe_store_writes
from tests.integration.core_runtime.test_acquisition_observation_semantics import _case


def test_historical_source_preparation_replays_without_current_overlay_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(tmp_path)
    expected = case.prepared
    writes = _observe_store_writes(monkeypatch)

    def no_current_owner(**_kwargs: object) -> None:
        raise AssertionError("historical replay requested a current native permit")

    monkeypatch.setattr(
        case.scenario.overlay, "read_activated_semantic_epoch_observations", no_current_owner
    )
    observed = owner.replay_acquired_observation_snapshot_preparation(
        FileSystemCAS(case.scenario.store.root),
        base_data_snapshot_ref=expected.base_data_snapshot_ref,
        receipt_ref=expected.receipt_ref,
        passport_ref=expected.observation_projection.passport_ref,
        boundary_candidate_ref=case.scenario.candidate.candidate_ref,
        source_ref=case.scenario.candidate.statement.source_record_ref,
        observation_id=expected.selected_observation_id,
        slot_binding=expected.selected_profile,
        transaction_time=case.args["transaction_time"],
    )
    assert observed == expected
    assert writes == []
    assert not case.workspace.exists()


def test_historical_source_replay_requires_exact_boundary_source_join(tmp_path: Path) -> None:
    case = _case(tmp_path)
    prepared = case.prepared
    wrong = case.scenario.candidate.statement.source_record_ref.model_copy(
        update={"kind": "foreign.opaque"}
    )
    with pytest.raises(owner.DataStateSubstrateError, match="source_binding_mismatch"):
        owner.replay_acquired_observation_snapshot_preparation(
            case.scenario.store,
            base_data_snapshot_ref=prepared.base_data_snapshot_ref,
            receipt_ref=prepared.receipt_ref,
            passport_ref=prepared.observation_projection.passport_ref,
            boundary_candidate_ref=case.scenario.candidate.candidate_ref,
            source_ref=wrong,
            observation_id=prepared.selected_observation_id,
            slot_binding=prepared.selected_profile,
            transaction_time=case.args["transaction_time"],
        )


@pytest.mark.parametrize("link", ["verifier_provenance", "native_member", "passport"])
def test_historical_consumers_refuse_changed_owner_default_view(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, link: str
) -> None:
    """The owner default must resolve to the admitted selected CAS view."""
    from polisyos.core.artifacts import ArtifactRef, ProducerInfo, artifact_ref_for_manifest
    from polisyos.core.artifacts._layout import CASPathLayout
    from polisyos.core.contracts import epoch
    from tests.integration.core_runtime.test_acquisition_data_preparation import _same_write_options

    case = _case(tmp_path)
    prepared = case.prepared
    store = case.scenario.store
    issued = owner.materialize_acquired_observation_snapshot(
        store, **case.args, workspace_dir=case.workspace, prepared=prepared
    )
    receipt = epoch.ActivatedOverlayAdmissionStatement.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=prepared.receipt_ref,
            expected_kind="epoch.activated_overlay_admission_receipt",
        )
    )
    admitted = epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=receipt.admitted_boundary_evidence_ref,
            expected_kind="epoch.admitted_acquisition_boundary_evidence",
        )
    )
    native = epoch.AcquisitionNativeMembershipReceipt.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=admitted.native_membership_receipt_ref,
            expected_kind="epoch.acquisition_native_membership",
        )
    )
    projection = epoch.AcquisitionSemanticProjectionVerificationReceipt.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=admitted.semantic_projection_verification_receipt_ref,
            expected_kind="epoch.acquisition_semantic_projection_verification_receipt",
        )
    )
    matching = [
        row
        for row in native.assessments
        if row.operational_epoch_id == case.scenario.passport.epoch_id
        and row.semantic_candidate_ref == admitted.semantic_candidate_ref
    ]
    assert len(matching) == 1
    row = matching[0]
    pairs = {
        "verifier_provenance": (
            projection.verifier_provenance_ref,
            admitted.verifier_provenance_ref,
        ),
        "native_member": (row.native_member_ref, admitted.native_member_ref),
        "passport": (row.passport_ref, admitted.passport_ref),
    }
    embedded, selected = pairs[link]
    assert isinstance(embedded, ArtifactRef) and isinstance(selected, ArtifactRef)
    assert embedded.manifest_profile_sha256 is None
    assert selected.manifest_profile_sha256 is not None
    assert embedded.artifact_id == selected.artifact_id
    assert embedded.kind == selected.kind and embedded.media_type == selected.media_type

    def snapshot_read() -> object:
        return owner.read_acquired_observation_semantic_values(
            FileSystemCAS(store.root), issued.data_snapshot_ref
        )

    def preparation_read() -> object:
        return owner.replay_acquired_observation_snapshot_preparation(
            FileSystemCAS(store.root),
            base_data_snapshot_ref=prepared.base_data_snapshot_ref,
            receipt_ref=prepared.receipt_ref,
            passport_ref=prepared.observation_projection.passport_ref,
            boundary_candidate_ref=case.scenario.candidate.candidate_ref,
            source_ref=case.scenario.candidate.statement.source_record_ref,
            observation_id=prepared.selected_observation_id,
            slot_binding=prepared.selected_profile,
            transaction_time=case.args["transaction_time"],
        )

    expected_values = owner.prepare_acquired_observation_semantic_values(prepared)
    assert snapshot_read() == expected_values
    assert preparation_read() == prepared
    manifest = store.get_manifest(selected)
    alternate = store.put_bytes(
        store.get_bytes(selected),
        _same_write_options(
            manifest, producer=ProducerInfo(component="fixture.changed-default", version="1.0")
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert store.verify(alternate).ok and store.verify(selected).ok

    layout = CASPathLayout(store.root)
    _blob, default_path = layout.paths(selected.artifact_id)
    assert alternate.manifest_profile_sha256 is not None
    alternate_path = layout.view_manifest_path(
        alternate.artifact_id, alternate.manifest_profile_sha256
    )
    original_default = default_path.read_bytes()
    try:
        # Change only the owner-default view in the test-owned CAS. Keep the
        # same blob, selected manifest, receipt, hashes, status and markers.
        default_path.write_bytes(alternate_path.read_bytes())
        assert artifact_ref_for_manifest(store.get_manifest(embedded)) == alternate
        assert epoch.load_verified_epoch_statement(
            store=store,
            ref=embedded,
            expected_kind=embedded.kind,
            expected_media_type=embedded.media_type,
        ) == epoch.load_verified_epoch_statement(
            store=store,
            ref=selected,
            expected_kind=selected.kind,
            expected_media_type=selected.media_type,
        )
        with pytest.raises(
            owner.DataStateSubstrateError, match="historical_projection_binding_mismatch"
        ):
            snapshot_read()
        with pytest.raises(
            owner.DataStateSubstrateError, match="historical_projection_binding_mismatch"
        ):
            preparation_read()
        actual_reconciler = owner._historical_owner_ref_matches_selected_view
        with monkeypatch.context() as removed:
            # Remove the real shared predicate only. With the same divergent
            # view and every receipt/status/hash marker intact, both actual
            # consumers now accept; restoring it must reinstate both refusals.
            removed.setattr(
                owner, "_historical_owner_ref_matches_selected_view", lambda *_args, **_kwargs: True
            )
            assert snapshot_read() == expected_values
            assert preparation_read() == prepared
        assert owner._historical_owner_ref_matches_selected_view is actual_reconciler
        with pytest.raises(
            owner.DataStateSubstrateError, match="historical_projection_binding_mismatch"
        ):
            snapshot_read()
        with pytest.raises(
            owner.DataStateSubstrateError, match="historical_projection_binding_mismatch"
        ):
            preparation_read()
    finally:
        default_path.write_bytes(original_default)
    assert default_path.read_bytes() == original_default
    assert snapshot_read() == expected_values
    assert preparation_read() == prepared


def _seed_selected_skg(tmp_path: Path, *, edge_confidence: float | None) -> SkgCausalPriorRef:
    """Select actual owner-query rows from a test-owned Academic SKG database."""
    from polisyos.data_forge.domains.academic.knowledge.skg_store import (
        ensure_skg_schema,
        next_skg_version,
    )
    from polisyos.data_forge.read_api.academic import SKGQuery

    db_path = tmp_path / "academic-skg.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        ensure_skg_schema(con)
        version_id = next_skg_version(con, description="acquisition-world test fixture")
        if edge_confidence is not None:
            con.execute(
                "INSERT INTO ac_skg_edges "
                "(edge_id, src, dst, direction, n_articles, article_refs, "
                "evidence_strength, confidence, scope_conditions) "
                "VALUES ('test-edge', 'credit', 'survival', 'positive', 1, "
                "'[]', 'observational', ?, '[]')",
                [edge_confidence],
            )
        row_count = con.execute("SELECT COUNT(*) FROM ac_skg_edges").fetchone()
        assert row_count == (0 if edge_confidence is None else 1,)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "index")
    try:
        assert query.latest_skg_version_id() == version_id
        snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
        rows = query.query_edge_priors(min_confidence=0.0, limit=2)
    finally:
        query.close()
    assert snapshot_ref is not None
    assert len(rows) == (0 if edge_confidence is None else 1)
    return SkgCausalPriorRef(
        skg_snapshot_ref=snapshot_ref,
        skg_version_id=str(version_id),
        source_data_snapshot_id=world_fixture.SNAPSHOT_ID,
        edge_prior_refs=tuple(f"skg-edge://{row['edge_id']}" for row in rows),
    )


def _empty_selected_skg(tmp_path: Path) -> SkgCausalPriorRef:
    return _seed_selected_skg(tmp_path, edge_confidence=None)


def _active_selected_skg(tmp_path: Path) -> SkgCausalPriorRef:
    return _seed_selected_skg(tmp_path, edge_confidence=0.8)


def _read_skg_edges(db_path: Path) -> list[dict[str, object]]:
    from polisyos.data_forge.read_api.academic import SKGQuery

    query = SKGQuery(db_path=db_path, index_dir=db_path.parent / "index")
    try:
        return query.query_edge_priors(min_confidence=0.0, limit=2)
    finally:
        query.close()


def _world_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    skg_ref_factory: Callable[[Path], SkgCausalPriorRef] = _empty_selected_skg,
):
    case = _case(tmp_path / "source")
    monkeypatch.setattr(world_fixture, "FileSystemCAS", lambda _path: case.scenario.store)
    store, base, _model, _registry = world_fixture._build_record(
        tmp_path / "base", skg_ref_factory=skg_ref_factory
    )
    substrate = world_fixture._substrate_registry()
    views = world_model_artifact_views(base.record)
    plan = owner._prepare_acquired_observation_world(
        store,
        base_world_model_record=base.record,
        acquired_rule=case.prepared.foundry_binding_rule,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    numerical = prepare_json_input_binding_values(
        store,
        payload_json=case.prepared.payload_json,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=list(plan.rules),
    )
    return case, base, substrate, views, numerical


def test_prospective_world_values_write_nothing_and_match_the_actual_produced_world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, base, substrate, views, numerical = _world_case(tmp_path, monkeypatch)
    # Only this WMR's selected-prior facet is empty. Sibling consumers can
    # independently query the SKG; this fixture makes no claim about them.
    assert _read_skg_edges(tmp_path / "base" / "academic-skg.duckdb") == []
    assert base.record.skg_causal_prior_ref.edge_prior_refs == ()
    assert base.record.skg_causal_prior_ref.transport_score_refs == ()
    assert base.record.skg_causal_prior_ref.query_trace_refs == ()
    writes = _observe_store_writes(monkeypatch)
    before = owner.prepare_acquired_observation_world_semantic_values(
        store=case.scenario.store,
        base_world_model_record=base.record,
        data_preparation=case.prepared,
        prepared_state_values=numerical,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    assert before["status"] == "established", before
    assert before["predicate_provenance"] == "recomputed"
    assert writes == []
    materialized = owner.materialize_acquired_observation_snapshot(
        case.scenario.store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    substrate_ref = persist_substrate_registry(case.scenario.store, substrate)
    actual = owner.build_acquired_observation_candidate_world(
        case.scenario.store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        materialization=materialized,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    fresh_store = FileSystemCAS(case.scenario.store.root)
    persisted_world = load_world_model_record(fresh_store, actual.world_model.record_ref)
    assert persisted_world == actual.world_model.record
    assert persisted_world is not actual.world_model.record
    after = owner.read_acquired_observation_world_semantic_values(
        store=fresh_store,
        world_model_record=persisted_world,
        registry_bundle_ref=views.registry_bundle_ref,
    )
    assert after["status"] == "established", after
    assert before["effective_values"] == after["effective_values"]
    # Keep every CAS ref and producer marker, but falsify the actual quality output.
    binding_path = Path(persisted_world.data_forge_binding_ref.binding_path)
    original = binding_path.read_bytes()
    altered = json.loads(original)
    altered["bindings"][0]["quality_gates"][0]["status"] = "fail"
    try:
        binding_path.write_text(json.dumps(altered), encoding="utf-8")
        refused = owner.read_acquired_observation_world_semantic_values(
            store=fresh_store,
            world_model_record=persisted_world,
            registry_bundle_ref=views.registry_bundle_ref,
        )
        assert refused["status"] == "not_established"
    finally:
        binding_path.write_bytes(original)


def test_active_skg_change_stays_unknown_when_same_wmr_ref_is_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live changed owner quantity cannot be equated using WMR refs alone."""
    case, base, substrate, views, numerical = _world_case(
        tmp_path, monkeypatch, skg_ref_factory=_active_selected_skg
    )
    store = case.scenario.store
    db_path = tmp_path / "base" / "academic-skg.duckdb"
    selected = base.record.skg_causal_prior_ref
    assert selected.edge_prior_refs == ("skg-edge://test-edge",)
    assert selected.transport_score_refs == () and selected.query_trace_refs == ()
    original_rows = _read_skg_edges(db_path)
    assert len(original_rows) == 1
    assert original_rows[0]["edge_id"] == "test-edge"
    assert original_rows[0]["confidence"] == pytest.approx(0.8)
    original_digest = hashlib.sha256(db_path.read_bytes()).hexdigest()

    materialized = owner.materialize_acquired_observation_snapshot(
        store, **case.args, workspace_dir=case.workspace, prepared=case.prepared
    )
    substrate_ref = persist_substrate_registry(store, substrate)
    actual = owner.build_acquired_observation_candidate_world(
        store,
        base_world_model=base.record,
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        materialization=materialized,
        workspace_dir=tmp_path / "world",
        transaction_time=case.args["transaction_time"],
    )
    assert actual.world_model.record.skg_causal_prior_ref == selected
    record_before = actual.world_model.record.model_dump(mode="json")

    def prospective() -> dict[str, object]:
        return owner.prepare_acquired_observation_world_semantic_values(
            store=store,
            base_world_model_record=base.record,
            data_preparation=case.prepared,
            prepared_state_values=numerical,
            registry_bundle_ref=views.registry_bundle_ref,
            substrate_registry=substrate,
        )

    def historical() -> dict[str, object]:
        fresh_store = FileSystemCAS(store.root)
        persisted_world = load_world_model_record(fresh_store, actual.world_model.record_ref)
        assert persisted_world == actual.world_model.record
        assert persisted_world is not actual.world_model.record
        return owner.read_acquired_observation_world_semantic_values(
            store=fresh_store,
            world_model_record=persisted_world,
            registry_bundle_ref=views.registry_bundle_ref,
        )

    def assert_unknown(result: dict[str, object]) -> None:
        assert result["status"] == "not_established", result
        assert result["predicate_provenance"] == "not_established"
        assert result["reason_codes"] == ("acquisition_world_skg_consumed_values_not_established",)

    def shallow_dependency(_store: object, world: WorldModelRecord) -> dict[str, object]:
        # Counterfactual removal: preserve the exact selected WMR references but
        # omit the actual active SKG quantity, keeping the rest of the producer
        # and reader intact. This is not a replacement production backend.
        assert world.simulation_model_ref.ncm_refs == ()
        assert world.simulation_model_ref.mechanism_refs == ()
        assert world.simulation_model_ref.gcm_refs == ()
        assert world.simulation_model_ref.program_graph_refs == ()
        return {
            "ncm_values": (),
            "skg_causal_prior": world.skg_causal_prior_ref.model_dump(mode="json"),
        }

    assert_unknown(prospective())
    assert_unknown(historical())
    with monkeypatch.context() as removed:
        removed.setattr(owner, "_acquired_model_dependency_values", shallow_dependency)
        shallow_before = prospective()
        shallow_before_read = historical()
        assert shallow_before["status"] == "established", shallow_before
        assert shallow_before_read["status"] == "established", shallow_before_read
        assert shallow_before["effective_values"] == shallow_before_read["effective_values"]

    con = duckdb.connect(str(db_path))
    try:
        con.execute("UPDATE ac_skg_edges SET confidence = 0.2 WHERE edge_id = 'test-edge'")
        con.execute("CHECKPOINT")
    finally:
        con.close()
    changed_rows = _read_skg_edges(db_path)
    from polisyos.data_forge.read_api.academic import SKGQuery

    query = SKGQuery(db_path=db_path, index_dir=db_path.parent / "index")
    try:
        assert query.latest_skg_version_id() == int(selected.skg_version_id)
        assert query.skg_snapshot_ref(version_id=int(selected.skg_version_id)) == (
            selected.skg_snapshot_ref
        )
    finally:
        query.close()
    assert len(changed_rows) == 1 and changed_rows[0]["edge_id"] == "test-edge"
    assert changed_rows[0]["confidence"] == pytest.approx(0.2)
    assert changed_rows != original_rows
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() != original_digest
    assert actual.world_model.record.model_dump(mode="json") == record_before
    assert actual.world_model.record.skg_causal_prior_ref == selected
    assert_unknown(prospective())
    assert_unknown(historical())

    with monkeypatch.context() as removed:
        removed.setattr(owner, "_acquired_model_dependency_values", shallow_dependency)
        shallow_after = prospective()
        shallow_after_read = historical()
        assert shallow_after["status"] == "established", shallow_after
        assert shallow_after_read["status"] == "established", shallow_after_read
        # The removed gate would report unchanged effective values despite the
        # real owner's changed source bytes and selected edge confidence.
        assert shallow_before["effective_values"] == shallow_after["effective_values"]
        assert shallow_before_read["effective_values"] == shallow_after_read["effective_values"]
    assert_unknown(prospective())
    assert_unknown(historical())


def test_supplied_state_plan_cannot_self_attest_completeness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case, base, substrate, views, _numerical = _world_case(tmp_path, monkeypatch)
    result = owner.prepare_acquired_observation_world_semantic_values(
        store=case.scenario.store,
        base_world_model_record=base.record,
        data_preparation=case.prepared,
        prepared_state_values={"complete": True},
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=substrate,
    )
    assert result["status"] == "not_established"
    assert result["reason_codes"]
