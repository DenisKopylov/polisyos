"""Outer-artifact replay witness for an N6 source-custody-limited run."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.resilience import guard_runtime_cas
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    AcquisitionRouteLoop,
)
from tests.unit.runtime.http.test_control_service_di import (
    _build_registry_providers,
    _NoOpRetrievalService,
)
from tests.unit.runtime.quality.test_acquisition_route_loop import _compiled


@pytest.mark.asyncio
async def test_source_limited_n6_v4_replays_through_guarded_compiled_artifact_owner(
    tmp_path: Path,
) -> None:
    """Persist/reopen v4 through runtime owners, then deny a foreign tenant."""
    compiled = await _compiled()
    leaf_runs = tuple(
        node.cycle_run
        for node in compiled.recursive_run.leaf_nodes
        if node.cycle_run is not None
    )
    assert len(leaf_runs) == 1
    produced_run = leaf_runs[0]
    assert produced_run.schema_version == "policyos.runtime.generation_cycle_controller.v4"
    assert produced_run.source_custody_limitation is not None
    assert produced_run.source_custody_limitation.status == "not_established"
    assert produced_run.source_custody_limitation.reason_code == "source_store_unavailable"

    runtime_root = tmp_path / "runtime-cas"
    tenant_store = guard_runtime_cas(
        FileSystemCAS(runtime_root).with_ambient_ownership_enforcement()
    )
    service = ControlPlaneService(
        cas_root=runtime_root,
        core_runs_root=runtime_root / "runs",
        artifact_store=tenant_store,
        retrieval_service=_NoOpRetrievalService(),
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=_build_registry_providers(),
    )
    owner_reader = AcquisitionRouteLoop(
        control_store=service._control_store,
        artifact_store=tenant_store,
        event_log=service._diagnostic_event_log,
        tenant_id="tenant-a",
        cell_id="cell-a",
    )
    expected_kind = "runtime.compiled_recursive_generation_cycle"
    expected_schema = "polisyos.runtime.CompiledRecursiveGenerationCycleRun"

    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            compiled_ref = service._put_json_artifact(
                compiled.model_dump(mode="json"),
                kind=expected_kind,
                schema_name=expected_schema,
            )
            artifact_manifest = tenant_store.get_manifest(compiled_ref)
            assert artifact_manifest.kind == expected_kind
            assert artifact_manifest.artifact_schema is not None
            assert artifact_manifest.artifact_schema.name == expected_schema
            assert artifact_manifest.artifact_schema.version == "1.0"

            # This is the production acquisition-route reader: it rechecks bytes,
            # content address, kind, and schema before the compiled model replays.
            persisted_payload = owner_reader._read_json_artifact(
                compiled_ref,
                expected_kind=expected_kind,
                expected_schema_name=expected_schema,
            )
            replayed = CompiledRecursiveGenerationCycleRun.model_validate(
                persisted_payload
            )
            assert replayed.schema_version == (
                COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
            )
            replayed_leaf_runs = tuple(
                node.cycle_run
                for node in replayed.recursive_run.leaf_nodes
                if node.cycle_run is not None
            )
            assert len(replayed_leaf_runs) == 1
            replayed_run = replayed_leaf_runs[0]
            assert replayed_run == produced_run
            assert replayed_run.schema_version == produced_run.schema_version
            assert replayed_run.source_custody_limitation == (
                produced_run.source_custody_limitation
            )

        foreign_reader = AcquisitionRouteLoop(
            control_store=service._control_store,
            artifact_store=tenant_store,
            event_log=service._diagnostic_event_log,
            tenant_id="tenant-b",
            cell_id="cell-b",
        )
        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            assert tenant_store.has(compiled_ref) is False
            with pytest.raises(
                AcquisitionRouteClosureError,
                match="source_artifact_unverified",
            ):
                foreign_reader._read_json_artifact(
                    compiled_ref,
                    expected_kind=expected_kind,
                    expected_schema_name=expected_schema,
                )
    finally:
        service.close()
        tenant_store.close()
