from __future__ import annotations

import datetime as datetime_module
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.read_api import catalog
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionServiceError,
)
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
    WorldBankWDIRouteExecutionBinding,
    resolve_world_bank_wdi_route_execution_bindings,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_planner
from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionStrategy,
    NativeDerivationLeafCostProfile,
    NativeDerivationLeafCostProfileScope,
    load_native_derivation_leaf_cost_profile,
    persist_native_derivation_leaf_cost_profile,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
    NativeDerivationRouteConfiguration,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests._helpers.acquisition_production import (
    _ATTEMPT_ID,
    _entry,
    _family_receipt,
    _resolver,
    _write_family_receipt,
)


def _route_closure() -> SimpleNamespace:
    """Build the exact minimal typed projection consumed by the route resolver."""
    return SimpleNamespace(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-acquisition",
        route_id="sha256:" + "1" * 64,
        design_problem_basis=SimpleNamespace(
            jurisdiction_time=SimpleNamespace(region="UKR", data_time="2024")
        ),
        planner_record=SimpleNamespace(
            gap_type="data_snapshot_release",
            requirement_family="data_requirement",
            requirement_schema_version="policyos.runtime.l1_variable_availability_gap.v1",
            missing_requirement_fields=("canonical_variable_observations:government.balance",),
            recommended_strategy="production_snapshot_build",
        ),
    )


def _port_fixture(
    tmp_path: Path, *, with_bridge: bool = False
) -> tuple[
    WorldBankWDIAcquisitionExecutionPort,
    WorldBankWDIRouteExecutionBinding,
    Path,
    AcquisitionWorldGrowthBridge | None,
]:
    repo_root = tmp_path / "repo"
    entry = _entry()
    receipt = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=_family_receipt(),
    )
    authority, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt,),
    )
    registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    store = FileSystemCAS(tmp_path / "cas")
    runtime_root = tmp_path / "runtime-state"
    bridge = None
    if with_bridge:
        bridge = AcquisitionWorldGrowthBridge(
            config=AcquisitionWorldGrowthConfig(),
            repo_root=authority.repo_root,
            runtime_root=tmp_path / "bridge-runtime",
            authority=authority,
            artifact_store=store,
            event_log=RuntimeDiagnosticEventLog(
                store=ControlPlaneStore(
                    backend="sqlite",
                    sqlite_path=tmp_path / "events.sqlite3",
                ),
                artifact_store=store,
            ),
            epoch_deployment=None,
        )
    port = WorldBankWDIAcquisitionExecutionPort(
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
        runtime_state_root=runtime_root,
        artifact_store=store,
        world_growth_bridge=bridge,
    )
    (binding,) = resolve_world_bank_wdi_route_execution_bindings(
        closure=_route_closure(),
        authority=authority,
        registry=registry,
        provision=authority.provision,
        provision_content_sha256=authority.provision_content_sha256,
    )
    return port, binding, runtime_root, bridge


def _lease_state(lease_root: Path) -> tuple[tuple[str, bytes, int, int, int], ...] | None:
    if not lease_root.exists():
        return None
    return tuple(
        (
            path.name,
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(lease_root.iterdir())
    )


def _put_selected_native_cost_fact(
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
            producer=artifacts.ProducerInfo(component="tests.native_quote_expiry", version="1.0"),
            canon=artifacts.CanonInfo.from_spec(spec),
            inputs=[],
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def test_candidate_attempt_preflight_allows_unused_and_exact_reusable_lease_read_only(
    tmp_path: Path,
) -> None:
    port, binding, runtime_root, _bridge = _port_fixture(tmp_path)
    lease_root = runtime_root / "runtime/acquisition/worldbank-wdi/attempt-leases"

    assert _lease_state(lease_root) is None
    port._require_candidate_experiment_attempt_available(binding)
    assert _lease_state(lease_root) is None

    assert port._reserve_first_fresh((binding,)) == binding
    before = _lease_state(lease_root)
    assert before is not None and len(before) == 1
    port._require_candidate_experiment_attempt_available(binding)
    assert _lease_state(lease_root) == before


@pytest.mark.parametrize("spent_state", ["claim", "non_reusable_lease"])
def test_candidate_attempt_preflight_rejects_spent_binding_without_mutation(
    tmp_path: Path,
    spent_state: str,
) -> None:
    port, binding, runtime_root, _bridge = _port_fixture(tmp_path)
    lease_root = runtime_root / "runtime/acquisition/worldbank-wdi/attempt-leases"
    assert port._reserve_first_fresh((binding,)) == binding
    lease_path = port._lease_path(binding)
    if spent_state == "claim":
        port._claim_reserved_binding(binding)
    else:
        lease_path.chmod(0o600)
        lease_path.write_bytes(b"not a canonical attempt lease\n")
        lease_path.chmod(0o400)
    before = _lease_state(lease_root)

    with pytest.raises(AcquisitionActionServiceError) as refused:
        port._require_candidate_experiment_attempt_available(binding)

    assert refused.value.code == "acquisition_live_attempt_exhausted"
    assert _lease_state(lease_root) == before


def test_candidate_worker_preserves_exhausted_code_before_budget_or_source_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port, binding, runtime_root, bridge = _port_fixture(tmp_path, with_bridge=True)
    assert bridge is not None
    assert port._reserve_first_fresh((binding,)) == binding
    port._claim_reserved_binding(binding)
    lease_root = runtime_root / "runtime/acquisition/worldbank-wdi/attempt-leases"
    before = _lease_state(lease_root)
    bridge._source_control_service = object()
    selection = object()
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-acquisition",
        source_job_id="job-candidate",
        source_payload_ref="sha256:" + "2" * 64,
        capability_manifest_ref="sha256:" + "3" * 64,
        request_content_hash="sha256:" + "4" * 64,
        route_id="sha256:" + "1" * 64,
        policy_ref=object(),
        policy_scope=object(),
        generation_run=object(),
        source_cycle=object(),
        design_problem_basis=object(),
        planner_report=object(),
        planner_record=object(),
    )
    phase = SimpleNamespace(receipt_phase="executing")
    monkeypatch.setattr(port, "preflight_candidate_experiment", lambda **_kwargs: selection)
    monkeypatch.setattr(
        port,
        "_candidate_experiment_binding",
        lambda **_kwargs: (binding, SimpleNamespace(authorization=object())),
    )
    monkeypatch.setattr(
        "polisyos.runtime.quality.candidate_acquisition_action._current_candidate_experiment_action",
        lambda *_args, **_kwargs: (selection, phase, object()),
    )
    monkeypatch.setattr(
        bridge,
        "prepare_candidate_experiment_source_budget_window",
        lambda **_kwargs: pytest.fail("spent attempt reached budget-window preparation"),
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_surface_execution.execute_live_catalog_acquisition",
        lambda **_kwargs: pytest.fail("spent attempt reached source dispatch"),
    )

    with pytest.raises(AcquisitionActionServiceError) as refused:
        port.execute_candidate_experiment(origin=origin, action_phase_ref="phase:candidate")

    assert refused.value.code == "acquisition_live_attempt_exhausted"
    assert _lease_state(lease_root) == before


@pytest.mark.parametrize(
    "failure_mode",
    ["quote_expiry", "inventory_raises", "inventory_unrun", "inventory_fail", "inventory_empty"],
)
def test_native_quote_expiry_during_binding_resolution_blocks_lease_and_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    port, binding, runtime_root, _bridge = _port_fixture(tmp_path)
    store = port._artifact_store
    refs = {
        name: _put_selected_native_cost_fact(store, kind=kind, name=name)
        for name, kind in (
            ("configured_port", "runtime.quality.n7_configured_candidate_port_source"),
            ("planner_report", "runtime.acquisition_planner_report"),
            ("derivation_bundle", "runtime.quality.n7_derivation_bundle"),
            ("obligation_set", "runtime.quality.model_input_obligation_set"),
            ("supplier", "external.source_supplier_fact"),
            ("quote", "external.owner_quote_fact"),
        )
    }
    start = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    scope = NativeDerivationLeafCostProfileScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-acquisition",
        source_job_id="source-native-a",
        configured_port_source_ref=refs["configured_port"],
        planner_report_ref=refs["planner_report"],
        derivation_bundle_ref=refs["derivation_bundle"],
        obligation_set_ref=refs["obligation_set"],
        source_node_id="source:metric-a",
        requirement_gap_id="gap:metric-a",
        compiled_requirement_ref="compiled:metric-a",
        planner_record_id="record:metric-a",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        selected_supplier_ref=refs["supplier"],
        missing_distribution="government.balance",
    )
    profile_payload = {
        "schema_version": "polisyos.runtime.native_derivation_leaf_cost_profile.v1",
        "authority_purpose": "costing_and_provenance_only",
        "scope": scope.model_dump(mode="json"),
        "quote_evidence_ref": refs["quote"].model_dump(mode="json"),
        "effective_at": (start - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (start + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "rule_version": "supplier-rate-card:test",
        "collection_mode": "owner quoted registry request",
        "currency": "USD",
        "line_items": [
            {
                "line_item_id": "source_request",
                "quantity": 1.0,
                "rate_name": "supplier_quote",
                "unit_rate": 5.0,
                "amount": 5.0,
            }
        ],
        "quantity_unit_by_line_item": {"source_request": "registry-request"},
        "calendar_days": 1,
        "expert_hours": 0.5,
    }
    profile = NativeDerivationLeafCostProfile.model_validate(
        {
            **profile_payload,
            "content_hash": acquisition_planner._stable_content_hash(profile_payload),
        }
    )
    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)
    assert load_native_derivation_leaf_cost_profile(store, profile_ref) == profile

    native_config = NativeDerivationRouteConfiguration(
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        configured_port_source_ref=scope.configured_port_source_ref,
        owner_declared_cost_profile_refs=(profile_ref,),
    )
    bridge = SimpleNamespace(
        config=AcquisitionWorldGrowthConfig(native_derivation_routes=(native_config,)),
        candidate_source_selection=lambda _closure: None,
        require_native_derivation_provider_bindings=lambda _closure, _bindings: None,
        has_admission_attempt=lambda _closure: False,
    )
    inventory_calls: list[artifacts.ArtifactID] = []
    if failure_mode != "quote_expiry":

        class UnusableInventoryStore:
            def __getattr__(self, name):
                return getattr(store, name)

            def inventory_snapshot(self, *, artifact_id):
                inventory_calls.append(artifact_id)
                if failure_mode == "inventory_raises":
                    raise TypeError("filtered inventory is unsupported by this fixture backend")
                actual = store.inventory_snapshot(artifact_id=artifact_id)
                if failure_mode == "inventory_unrun":
                    return replace(actual, verdict="UNRUN", reason="fixture inventory unavailable")
                if failure_mode == "inventory_fail":
                    return replace(actual, verdict="fail", reason="fixture inventory invalid")
                return replace(actual, entries=())

        actual_bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        actual_bridge.config = bridge.config
        actual_bridge.artifact_store = UnusableInventoryStore()
        bridge = actual_bridge
    port._world_growth_bridge = bridge
    closure = SimpleNamespace(
        **vars(_route_closure()),
        source_job_id=scope.source_job_id,
        owner_declared_profile_ref=profile_ref,
        native_derivation_leaf_scope=scope,
    )

    current_time = [start]

    class _ControlledDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = current_time[0]
            if tz is None:
                return value.replace(tzinfo=None)
            return value.astimezone(tz)

    monkeypatch.setattr(datetime_module, "datetime", _ControlledDateTime)
    real_resolver_calls = 0

    def _expire_after_reservation_resolution(**kwargs):
        nonlocal real_resolver_calls
        bindings = resolve_world_bank_wdi_route_execution_bindings(**kwargs)
        real_resolver_calls += 1
        if real_resolver_calls == 2 and failure_mode == "quote_expiry":
            current_time[0] = profile.expires_at
        return bindings

    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_surface_execution.resolve_world_bank_wdi_route_execution_bindings",
        _expire_after_reservation_resolution,
    )
    monkeypatch.setattr(
        "polisyos.runtime.http.services.acquisition_surface_execution.execute_live_catalog_acquisition",
        lambda **_kwargs: pytest.fail("expired native quote reached provider execution"),
    )
    lease_open_attempts: list[Path] = []
    lease_path = port._lease_path(binding)
    real_os_open = os.open

    def _record_lease_open(path, *args, **kwargs):
        if isinstance(path, str | bytes | os.PathLike) and Path(os.fsdecode(path)) == lease_path:
            lease_open_attempts.append(lease_path)
        return real_os_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", _record_lease_open)

    if failure_mode == "quote_expiry":
        with pytest.raises(LiveAcquisitionExecutionError) as refused:
            port.execute(closure)
        assert refused.value.code == "native_leaf_quote_expired_before_fetch"
        assert real_resolver_calls == 2
        assert inventory_calls == []
    else:
        expected_code = (
            "acquisition_world_growth_profile_inventory_unavailable"
            if failure_mode == "inventory_raises"
            else "acquisition_world_growth_profile_inventory_unverified"
        )
        with pytest.raises(ValueError, match=expected_code):
            port.execute(closure)
        assert real_resolver_calls == 1
        assert inventory_calls == [profile_ref.artifact_id]
    assert lease_open_attempts == []
    lease_root = runtime_root / "runtime/acquisition/worldbank-wdi/attempt-leases"
    expected_lease_state = () if failure_mode == "quote_expiry" else None
    assert _lease_state(lease_root) == expected_lease_state
