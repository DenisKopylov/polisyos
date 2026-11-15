"""History failures preserve a previously resolved generic numerical projection.

These controls exercise the new read-only bridge, not numerical truth. The
served native action test supplies the actual source/receipt/history oracle.
"""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.contracts.runtime import RunGenericCycleSimulationProjection
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.runtime.http.routes import runs
from tests.unit.core.contracts.test_runtime_n5_bodies import (
    _artifact_ref,
    _generic_observation,
    _result_body_payload,
)


def _resolved_projection() -> RunGenericCycleSimulationProjection:
    observation = _generic_observation(_result_body_payload(candidate=False))
    return RunGenericCycleSimulationProjection(
        run_id="generic-source-history",
        artifact_status="resolved",
        source_ref=_artifact_ref("runtime.compiled_recursive_generation_cycle", "1"),
        source_content_hash="sha256:" + "2" * 64,
        n4_source_ref=observation.n4_source_ref,
        n4_source_status="resolved",
        parent_context_job_ref=observation.context_job_ref,
        parent_profile_ref=observation.profile_ref,
        parent_profile_id="configured-history-test",
        child_profile_status="not_attempted",
        n5_observations=(observation,),
    )


def test_missing_history_source_keeps_the_resolved_numerical_projection(tmp_path) -> None:
    projection = _resolved_projection()
    original = projection.model_dump(mode="json")
    store = FileSystemCAS(tmp_path / "cas")

    limited = runs._generic_acquisition_history_projection(
        projection,
        run_id=projection.run_id,
        tenant_id="tenant-a",
        cell_id="cell-a",
        store=store,
        control_service=None,
    )

    assert limited.acquisition_history is None
    assert limited.acquisition_history_limitation_code == (
        "acquisition_action_history_integrity_not_established"
    )
    unchanged_fields = set(RunGenericCycleSimulationProjection.model_fields) - {
        "acquisition_history",
        "acquisition_history_limitation_code",
        "n4_source_status",
        "n4_source_limitation_code",
    }
    assert {name: getattr(limited, name) for name in unchanged_fields} == {
        name: getattr(projection, name) for name in unchanged_fields
    }
    assert limited.n4_source_status == "not_established"
    assert limited.n4_source_limitation_code == "generic_n4_source_reference_not_established"
    assert projection.model_dump(mode="json") == original
    assert limited.n5_observations[0].simulation_result_body == (
        projection.n5_observations[0].simulation_result_body
    )
    assert limited.publication_authority is False
    assert limited.currentness_status == "not_established"


@pytest.mark.parametrize(
    ("error_type", "expected_status", "expected_code"),
    [
        (ArtifactOwnershipError, 403, "generic_cycle_artifact_scope_refused"),
        (PermissionError, 503, "generic_cycle_artifact_reader_permission_unavailable"),
    ],
)
def test_history_bridge_propagates_owner_and_storage_access_refusals(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    expected_status: int,
    expected_code: str,
) -> None:
    projection = _resolved_projection()
    store = FileSystemCAS(tmp_path / "cas")

    def refuse_read(*_args: Any, **_kwargs: Any) -> None:
        raise error_type("selected history source access refused")

    monkeypatch.setattr(runs, "read_core_json_artifact", refuse_read)
    with pytest.raises(RuntimeHTTPError) as denied:
        runs._generic_acquisition_history_projection(
            projection,
            run_id=projection.run_id,
            tenant_id="tenant-a",
            cell_id="cell-a",
            store=store,
            control_service=None,
        )
    assert denied.value.status_code == expected_status
    assert denied.value.code == expected_code
