from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.foundry import FoundryExecutionInputBasisRef, SimulationResult


def _artifact_id(marker: str) -> str:
    """Return a deterministic artifact ID for a focused contract test."""
    return f"sha256:{marker * 64}"


def _basis_ref_payload() -> dict[str, str]:
    return {
        "artifact_id": _artifact_id("a"),
        "kind": "foundry.execution_input_basis",
        "media_type": "application/json",
        "manifest_profile_sha256": _artifact_id("b"),
    }


def _simulation_result_payload(
    basis_ref: dict[str, str] | None,
    *,
    schema_version: str = "1.4",
    execution_source_status: str = "single_step_basis",
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "exec_plan_ref": {"artifact_id": _artifact_id("c")},
        "metrics_ref": {"artifact_id": _artifact_id("d")},
        "execution_input_basis_ref": basis_ref,
        "execution_source_status": execution_source_status,
    }


def test_named_basis_ref_keeps_legacy_defaults_and_pins_its_schema_identity() -> None:
    legacy_ref = FoundryExecutionInputBasisRef.model_validate({"artifact_id": _artifact_id("a")})
    assert legacy_ref.kind == "foundry.execution_input_basis"
    assert legacy_ref.media_type == "application/json"
    assert legacy_ref.manifest_profile_sha256 is None

    properties = SimulationResult.model_json_schema()["$defs"]["FoundryExecutionInputBasisRef"][
        "properties"
    ]
    assert properties["kind"]["const"] == "foundry.execution_input_basis"
    assert properties["media_type"]["const"] == "application/json"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "foundry.exec_plan"),
        ("media_type", "application/jsonl"),
    ],
)
def test_core_simulation_result_rejects_wrong_basis_ref_identity(
    field: str,
    value: str,
) -> None:
    basis_ref = _basis_ref_payload()
    basis_ref[field] = value

    with pytest.raises(ValidationError) as exc_info:
        SimulationResult.model_validate(_simulation_result_payload(basis_ref))

    assert any(
        error["loc"][:2] == ("execution_input_basis_ref", field)
        for error in exc_info.value.errors()
    )


def test_core_simulation_result_preserves_legacy_status_and_profiled_api_roundtrip() -> None:
    legacy_payload = _simulation_result_payload(
        None,
        schema_version="1.3",
        execution_source_status="not_recorded",
    )
    legacy_payload.pop("execution_input_basis_ref")
    legacy_payload.pop("execution_source_status")
    legacy_result = SimulationResult.model_validate(legacy_payload)
    assert legacy_result.execution_source_status == "not_recorded"
    assert legacy_result.execution_input_basis_ref is None

    result = SimulationResult.model_validate(_simulation_result_payload(_basis_ref_payload()))
    serialized = result.model_dump(mode="json")
    serialized_basis_ref = serialized["execution_input_basis_ref"]
    assert isinstance(serialized_basis_ref, dict)
    assert serialized_basis_ref["manifest_profile_sha256"] == _artifact_id("b")

    received = SimulationResult.model_validate(serialized)
    assert received.execution_source_status == "single_step_basis"
    assert received.execution_input_basis_ref == result.execution_input_basis_ref
    assert received == result
