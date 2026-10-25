from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.runtime import LineageRef as CoreLineageRef
from polisyos.fabric.evidence.decision_data import (
    AccessRef,
    FabricDecisionData,
    FabricQuantityValue,
    QualityRef,
    ReplayRef,
    SourceContractRef,
    TemporalRef,
    UnitRef,
    to_runtime_quantity_value,
)
from polisyos.fabric.evidence.decision_data import (
    LineageRef as FabricLineageRef,
)

_PROFILE = "sha256:" + "b" * 64
_ARTIFACT_REF = {
    "artifact_id": "sha256:" + "a" * 64,
    "kind": "runtime.test.result",
    "media_type": "application/json",
    "manifest_profile_sha256": _PROFILE,
}


@pytest.mark.parametrize(
    ("case", "context", "accepted"),
    [
        ("legacy_all_optional_absent", {}, True),
        ("selected_profile_without_run_binding", {"artifact_ref": _ARTIFACT_REF}, True),
        (
            "reader_materialized_profile_without_run_binding",
            {
                "artifact_ref": _ARTIFACT_REF,
                "artifact_ref_provenance": "reader_materialized",
            },
            True,
        ),
        (
            "reader_materialized_profile_with_run_binding",
            {
                "artifact_ref": _ARTIFACT_REF,
                "artifact_ref_provenance": "reader_materialized",
                "source_run_id": "run:test",
            },
            True,
        ),
        (
            "run_output_profile_with_run_binding",
            {
                "artifact_ref": _ARTIFACT_REF,
                "artifact_ref_provenance": "run_output_ref",
                "source_run_id": "run:test",
            },
            True,
        ),
        ("run_id_without_profile", {"source_run_id": "run:test"}, False),
        (
            "run_id_with_profile_but_without_provenance",
            {"artifact_ref": _ARTIFACT_REF, "source_run_id": "run:test"},
            False,
        ),
        ("provenance_without_profile", {"artifact_ref_provenance": "reader_materialized"}, False),
        (
            "profile_without_manifest_selection",
            {
                "artifact_ref": {
                    "artifact_id": "sha256:" + "a" * 64,
                    "kind": "runtime.test.result",
                    "media_type": "application/json",
                }
            },
            False,
        ),
        (
            "run_output_provenance_without_run_id",
            {
                "artifact_ref": _ARTIFACT_REF,
                "artifact_ref_provenance": "run_output_ref",
            },
            False,
        ),
    ],
)
def test_fabric_lineage_profile_context_matches_core_contract(
    case: str,
    context: dict[str, Any],
    accepted: bool,
) -> None:
    values = {"id": "lineage:test", "status": "verified", **context}
    observed: list[bool] = []
    for contract in (CoreLineageRef, FabricLineageRef):
        try:
            contract.model_validate(values)
        except ValidationError:
            observed.append(False)
        else:
            observed.append(True)

    assert observed == [accepted, accepted], case


def _decision_envelope(lineage: FabricLineageRef) -> FabricDecisionData:
    return FabricDecisionData(
        id="fabric_decision_data:test:lineage",
        kind="quantity",
        value=FabricQuantityValue(
            point=1.0,
            unit=UnitRef(code="1", system="ucum"),
            metric_id="metric:test",
        ),
        source_contract=SourceContractRef(id="source:test", version="1"),
        quality=QualityRef(status="passed"),
        lineage=lineage,
        access=AccessRef(),
        time=TemporalRef(),
        replay=ReplayRef(status="replayable", manifest_ref="cas://sha256/replay"),
    )


def test_profiled_lineage_fields_survive_fabric_wire_and_runtime_projection() -> None:
    lineage = FabricLineageRef(
        id="lineage:run-output",
        status="verified",
        artifact_ref=_ARTIFACT_REF,
        artifact_ref_provenance="run_output_ref",
        source_run_id="run:test",
    )
    wire = _decision_envelope(lineage).model_dump(mode="json")
    decoded = FabricDecisionData.model_validate(wire)

    runtime = to_runtime_quantity_value(decoded)
    assert runtime.lineage.artifact_ref is not None
    assert runtime.lineage.artifact_ref.manifest_profile_sha256 == _PROFILE
    assert runtime.lineage.artifact_ref_provenance == "run_output_ref"
    assert runtime.lineage.source_run_id == "run:test"


def test_legacy_lineage_without_optional_profile_context_survives_projection() -> None:
    lineage = FabricLineageRef(id="lineage:legacy", status="verified")
    wire = _decision_envelope(lineage).model_dump(mode="json")
    decoded = FabricDecisionData.model_validate(wire)

    runtime = to_runtime_quantity_value(decoded)
    assert runtime.lineage.artifact_ref is None
    assert runtime.lineage.artifact_ref_provenance is None
    assert runtime.lineage.source_run_id is None
