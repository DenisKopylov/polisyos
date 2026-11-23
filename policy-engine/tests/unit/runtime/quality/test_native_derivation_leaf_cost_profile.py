from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality import acquisition_planner as acquisition_owner
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCostBasisRecord,
    AcquisitionStrategy,
    NativeDerivationLeafCostProfile,
    NativeDerivationLeafCostProfileScope,
    load_native_derivation_leaf_cost_profile,
    persist_native_derivation_leaf_cost_profile,
    produce_acquisition_cost_basis_record,
    validate_native_derivation_leaf_cost_profile_for_scope,
)


def _put_selected_fact(
    store: FileSystemCAS,
    *,
    kind: str,
    name: str,
) -> artifacts.ArtifactRef:
    spec = canon.CanonSpec(forbid_floats=False, forbid_nan_inf=True)
    return store.put_json(
        {"selected_fact": name},
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=f"test.{name}", version="1.0"),
            producer=artifacts.ProducerInfo(component="tests.native_leaf_cost", version="1.0"),
            canon=artifacts.CanonInfo.from_spec(spec),
            inputs=[],
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def _profile_scope(
    store: FileSystemCAS,
) -> tuple[NativeDerivationLeafCostProfileScope, artifacts.ArtifactRef]:
    configured_port = _put_selected_fact(
        store,
        kind="runtime.quality.n7_configured_candidate_port_source",
        name="configured_port",
    )
    planner_report = _put_selected_fact(
        store,
        kind="runtime.acquisition_planner_report",
        name="planner_report",
    )
    derivation_bundle = _put_selected_fact(
        store,
        kind="runtime.quality.n7_derivation_bundle",
        name="derivation_bundle",
    )
    obligation_set = _put_selected_fact(
        store,
        kind="runtime.quality.model_input_obligation_set",
        name="obligation_set",
    )
    supplier = _put_selected_fact(
        store,
        kind="external.source_supplier_fact",
        name="supplier",
    )
    quote = _put_selected_fact(
        store,
        kind="external.owner_quote_fact",
        name="quote",
    )
    scope = NativeDerivationLeafCostProfileScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-a",
        configured_port_source_ref=configured_port,
        planner_report_ref=planner_report,
        derivation_bundle_ref=derivation_bundle,
        obligation_set_ref=obligation_set,
        source_node_id="source:metric-a",
        requirement_gap_id="gap:metric-a",
        compiled_requirement_ref="compiled:metric-a",
        planner_record_id="record:metric-a",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        selected_supplier_ref=supplier,
        missing_distribution="metric-a",
    )
    return scope, quote


def _profile(
    scope: NativeDerivationLeafCostProfileScope,
    quote_ref: artifacts.ArtifactRef,
    *,
    now: datetime,
) -> NativeDerivationLeafCostProfile:
    payload = {
        "schema_version": "polisyos.runtime.native_derivation_leaf_cost_profile.v1",
        "authority_purpose": "costing_and_provenance_only",
        "scope": scope.model_dump(mode="json"),
        "quote_evidence_ref": quote_ref.model_dump(mode="json"),
        "effective_at": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "rule_version": "supplier-rate-card:2026-11",
        "collection_mode": "owner quoted registry request",
        "currency": "USD",
        "line_items": [
            {
                "line_item_id": "source_request",
                "quantity": 4.0,
                "rate_name": "supplier_quote",
                "unit_rate": 17.5,
                "amount": 70.0,
            }
        ],
        "quantity_unit_by_line_item": {"source_request": "registry-request"},
        "calendar_days": 3,
        "expert_hours": 1.5,
    }
    return NativeDerivationLeafCostProfile.model_validate(
        {
            **payload,
            "content_hash": acquisition_owner._stable_content_hash(payload),
        }
    )


def test_native_leaf_cost_profile_persists_binds_scope_and_produces_record(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)

    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)
    loaded = load_native_derivation_leaf_cost_profile(store, profile_ref)
    assert loaded == profile
    assert len(store.get_manifest(profile_ref).inputs) == 6
    assert (
        validate_native_derivation_leaf_cost_profile_for_scope(
            loaded, expected_scope=scope, now=now
        )
        == profile
    )

    record = produce_acquisition_cost_basis_record(
        missing_distribution="metric-a",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        owner_declared_profile_ref=profile_ref,
        store=store,
        expected_scope=scope,
        now=now,
    )
    assert isinstance(record, AcquisitionCostBasisRecord)
    assert record.schema_version == "AcquisitionCostBasisRecord@1.1"
    assert record.owner_declared_profile_ref == profile_ref
    assert record.line_items == profile.line_items
    assert record.total_amount == 70.0
    assert record.calendar_days == 3
    assert record.expert_hours == 1.5


def test_native_leaf_cost_profile_recomputes_quantity_and_profile_hash(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    changed = profile.model_dump(mode="json")
    changed["line_items"][0]["quantity"] = 5.0

    with pytest.raises(ValidationError, match="cost_line_item_amount_mismatch"):
        NativeDerivationLeafCostProfile.model_validate(changed)

    changed["line_items"][0]["amount"] = 87.5
    with pytest.raises(
        ValidationError, match="native_derivation_leaf_cost_profile_content_hash_mismatch"
    ):
        NativeDerivationLeafCostProfile.model_validate(changed)


def test_native_leaf_cost_profile_rejects_foreign_scope_supplier_strategy_and_expiry(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)

    foreign_tenant = scope.model_copy(update={"tenant_id": "tenant-b"})
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_scope_mismatch"):
        validate_native_derivation_leaf_cost_profile_for_scope(
            profile, expected_scope=foreign_tenant, now=now
        )

    foreign_supplier_ref = _put_selected_fact(
        store,
        kind="external.source_supplier_fact",
        name="foreign_supplier",
    )
    foreign_supplier = scope.model_copy(update={"selected_supplier_ref": foreign_supplier_ref})
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_scope_mismatch"):
        produce_acquisition_cost_basis_record(
            missing_distribution="metric-a",
            strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
            owner_declared_profile_ref=profile_ref,
            store=store,
            expected_scope=foreign_supplier,
            now=now,
        )

    with pytest.raises(
        ValueError, match="native_derivation_leaf_cost_profile_cost_selection_mismatch"
    ):
        produce_acquisition_cost_basis_record(
            missing_distribution="metric-a",
            strategy=AcquisitionStrategy.AGENCY_REQUEST,
            owner_declared_profile_ref=profile_ref,
            store=store,
            expected_scope=scope,
            now=now,
        )

    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_not_current"):
        validate_native_derivation_leaf_cost_profile_for_scope(
            profile,
            expected_scope=scope,
            now=datetime(2026, 11, 14, 15, 0, tzinfo=UTC),
        )


def test_native_leaf_cost_profile_rejects_missing_profile_and_removed_quote_bytes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)

    missing_profile_ref = artifacts.ArtifactRef.model_validate(
        {
            **profile_ref.model_dump(mode="json"),
            "artifact_id": f"sha256:{'0' * 64}",
        }
    )
    with pytest.raises(FileNotFoundError):
        load_native_derivation_leaf_cost_profile(store, missing_profile_ref)

    store._paths(quote_ref.artifact_id)[0].unlink()
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_input_unverified"):
        load_native_derivation_leaf_cost_profile(store, profile_ref)


def test_canonical_cost_producer_keeps_legacy_record_profile_free() -> None:
    record = produce_acquisition_cost_basis_record(
        missing_distribution="administrative_tax_receipts",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
    )

    assert isinstance(record, AcquisitionCostBasisRecord)
    assert record.schema_version == "AcquisitionCostBasisRecord@1.0"
    assert record.owner_declared_profile_ref is None
    assert "owner_declared_profile_ref" not in record.model_dump(mode="json")


def test_native_route_history_reopens_selected_receipt_and_rejects_advanced_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The early fold never substitutes for a fresh, exact late history read."""
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRoutePhaseReceipt,
        NativeDerivationLeafProviderSelection,
        VerifiedAcquisitionRouteClosure,
        _NativeRouteHistoryRead,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
    )
    from tests._helpers.runtime_http import _build_control_service
    from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job

    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile_ref = persist_native_derivation_leaf_cost_profile(
        store, _profile(scope, quote_ref, now=now)
    )
    cost = produce_acquisition_cost_basis_record(
        missing_distribution=scope.missing_distribution,
        strategy=scope.strategy,
        owner_declared_profile_ref=profile_ref,
        store=store,
        expected_scope=scope,
        now=now,
    )
    assert isinstance(cost, AcquisitionCostBasisRecord)
    provider = NativeDerivationLeafProviderSelection(
        source_node_id=scope.source_node_id,
        supplier_ref=scope.selected_supplier_ref,
        authority_entry_id="acquisition-authority:sha256:" + "a" * 64,
        connector_id="fixture.native",
    )
    phase = AcquisitionRoutePhaseReceipt(
        schema_version="AcquisitionRoutePhaseReceipt@1.3",
        receipt_id="native-selected.requested",
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        route_id="sha256:" + "1" * 64,
        action_generation=1,
        job_id="native-selected",
        compiled_ref="sha256:" + "2" * 64,
        planner_report_hash="sha256:" + "3" * 64,
        cost_basis_hash=cost.record_content_hash,
        decision_ref="sha256:" + "4" * 64,
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        owner_declared_profile_ref=profile_ref,
        native_leaf_provider_selection=provider,
        generated_at=now,
    )
    service = _build_control_service(tmp_path / "runtime", artifact_store=store)
    try:
        control = service._control_store
        _create_job(control, job_id=phase.job_id, kind="acquisition", run_id=phase.run_id)
        sink = service.acquisition_route_sink
        assert type(sink) is AcquisitionRouteLoopAuthoritySink
        head = sink.persist_phase(phase)
        subject = {
            "tenant_id": phase.tenant_id,
            "cell_id": phase.cell_id,
            "run_id": phase.run_id,
            "source_job_id": phase.source_job_id,
        }
        route = {**subject, "route_id": phase.route_id}
        actual_reads = []
        read_phase = sink._read_verified_action_phase

        def observe_phase(receipt_ref, *, selected_ref=None):
            actual_reads.append(receipt_ref)
            return read_phase(receipt_ref, selected_ref=selected_ref)

        with monkeypatch.context() as observe:
            observe.setattr(
                AcquisitionRouteLoopAuthoritySink,
                "_read_verified_action_phase",
                lambda _sink, *args, **kwargs: observe_phase(*args, **kwargs),
            )
            outcomes = sink.action_outcomes(**route)
        assert actual_reads == [head.receipt_ref]
        assert len(outcomes) == 1 and outcomes[0].latest_receipt == phase
        history = _NativeRouteHistoryRead(
            reader=sink,
            control_store=control,
            scope=(
                phase.tenant_id,
                phase.cell_id,
                phase.run_id,
                phase.source_job_id,
                phase.route_id,
            ),
            heads=control.list_acquisition_action_heads_for_source(**subject),
            outcomes=outcomes,
        )
        # No paid route is configured or exercised. The late read must still
        # independently verify the selected history consumed by the early fold.
        bridge = AcquisitionWorldGrowthBridge(
            config=AcquisitionWorldGrowthConfig(),
            repo_root=tmp_path,
            runtime_root=tmp_path / "growth",
            authority=None,
            artifact_store=service._artifact_store,
            event_log=service._diagnostic_event_log,
            epoch_deployment=None,
            control_store=control,
            action_head_sink=sink,
            source_control_service=service,
        )
        closure = VerifiedAcquisitionRouteClosure.model_construct(
            **route,
            native_derivation_leaf_scope=scope,
            native_derivation_leaf_provider=provider,
            design_problem_ref="sha256:" + "5" * 64,
        )

        def reopen():
            return bridge.select_prior_paid_native_input_admission(
                closure, selected_history=history
            )

        assert reopen() is None
        selected = artifacts.ArtifactID.model_validate(head.receipt_ref)
        assert head.receipt_manifest_profile_sha256 is not None
        sidecar = store._manifest_path_for_ref(selected, head.receipt_manifest_profile_sha256)
        original = sidecar.read_bytes()
        sidecar.unlink()
        try:
            assert store.has(selected)
            assert control.list_acquisition_action_heads_for_source(**subject) == history.heads
            with pytest.raises(FileNotFoundError):
                reopen()
        finally:
            sidecar.write_bytes(original)
        assert reopen() is None

        lease = control.lease_next_job(worker_id="fixture-native", lease_seconds=60)
        assert lease is not None and lease.job_id == phase.job_id
        with control.job_execution_fence(
            job_id=lease.job_id, worker_id="fixture-native", attempt=lease.attempt
        ):
            advanced = sink.persist_phase(
                phase.model_copy(
                    update={
                        "receipt_id": "native-selected.executing",
                        "coarse_phase": "executing",
                        "receipt_phase": "executing",
                        "predecessor_receipt_ref": head.receipt_ref,
                    }
                )
            )
        assert advanced.head_generation == head.head_generation + 1
        assert sink.action_outcomes(**route)[-1].head == advanced
        with pytest.raises(ValueError, match="native_paid_input_admission_source_history_changed"):
            reopen()
    finally:
        service.close()
