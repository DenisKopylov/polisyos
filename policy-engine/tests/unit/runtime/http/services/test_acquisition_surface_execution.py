from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

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
from polisyos.runtime.quality.acquisition_route_loop import (
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
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
