"""N7's live SKG owner must use a store supplied by its caller."""

from pathlib import Path
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.acquisition_planner import (
    RealAcquisitionOwnerGateway,
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from tests.unit.runtime.quality.test_acquisition_planner import _compiled_requirement_specs


def _skg_owner_request() -> tuple[dict[str, Any], Any]:
    spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    spec.update(
        {
            "requirement_id": "data-requirement:skg-runtime-store",
            "claim_id": "claim-skg-runtime-store",
            "required_data_families": ("owner_panel_missing",),
            "required_method_families": ("skg_schema_probe",),
        }
    )
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-skg-runtime-store",
        requirement_gaps=(gap,),
    )
    return spec, report.acquisition_records[0]


def test_skg_capture_without_supplied_store_does_not_rebuild_local_cas(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "checkout"
    spec, record = _skg_owner_request()
    gateway = RealAcquisitionOwnerGateway(repo_root=repo_root)

    artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)

    assert artifact is None
    assert not (repo_root / ".n7-live-cas").exists()


def test_default_production_gateway_requires_runtime_store(tmp_path: Path) -> None:
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.runtime.quality.design_problem import DesignProblem

    controller = GenerationCycleController(
        repo_root=tmp_path,
        authority_scope="production",
    )

    problem = DesignProblem.model_construct(runtime_hints={})
    assert controller._n7_owner_gateway(problem) is None


def test_default_gateway_uses_exact_tenant_store_for_skg_produce_and_replay(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "checkout"
    store_root = tmp_path / "owner-cas"
    store = artifacts.FileSystemCAS(store_root).with_ambient_ownership_enforcement()
    spec, record = _skg_owner_request()
    controller = GenerationCycleController(
        repo_root=repo_root,
        promotion_runtime=PromotionRuntime(store=store),
    )
    gateway = controller._n7_owner_gateway(DesignProblem.model_construct(runtime_hints={}))
    assert isinstance(gateway, RealAcquisitionOwnerGateway)
    assert gateway._artifact_store is store
    tenant_store = artifacts.FileSystemCAS(store_root).for_tenant("tenant-a", "cell-a")
    foreign_store = artifacts.FileSystemCAS(store_root).for_tenant("tenant-b", "cell-b")

    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)
            assert artifact is not None
            assert artifact.owner_component == "data_forge.skg"
            assert gateway._skg_calibration_source is not None
            assert gateway._skg_calibration_source._store is store
            ref = artifacts.ArtifactRef.model_validate(
                artifact.payload["owner_response"]["resolution_ref"]
            )
            assert tenant_store.get_manifest(ref).kind == (
                "runtime.production_grounding_source_resolution"
            )
            assert tenant_store.get_bytes(ref)

        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            with pytest.raises(ArtifactOwnershipError):
                foreign_store.get_bytes(ref)

        assert not (repo_root / ".n7-live-cas").exists()
    finally:
        for opened_store in (store, tenant_store, foreign_store):
            close = getattr(opened_store, "close", None)
            if callable(close):
                close()
