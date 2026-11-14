from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.foundry import (
    FeedbackExecutionContext,
    FoundryExecutionInputBasis,
    FoundryExecutionInputBasisRef,
    SimulationResult,
)


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


def _ref_payload(marker: str, kind: str | None = None) -> dict[str, str]:
    payload = {
        "artifact_id": _artifact_id(marker),
        "kind": kind or "foundry.test",
        "media_type": "application/json",
    }
    return payload


def _feedback_context_payload(*, captured: bool = True) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "final_injected_state_snapshot_ref": _ref_payload("e", "foundry.state_snapshot"),
        "final_parameter_override_bundle_ref": _ref_payload(
            "f", "foundry.parameter_override_bundle"
        ),
        "final_method_execution_bundle_ref": (
            _ref_payload("1", "foundry.method_execution_bundle") if captured else None
        ),
        "feedback_result_ref": _ref_payload("2", "foundry.feedback_result"),
        "feedback_trace_ref": _ref_payload("3", "foundry.feedback_trace"),
        "final_map_evaluation_id": "map-eval-final",
        "final_graph_invocation_id": "graph-invocation-final" if captured else None,
        "execution_link_status": "captured" if captured else "not_established",
    }


def _basis_payload(*, schema_version: str, feedback: bool) -> dict[str, object]:
    def registry_members(marker: str) -> dict[str, object]:
        return {
            key: _ref_payload(marker, f"foundry.{key}")
            for key in ("slot_registry", "merge_registry", "constraint_registry", "mechanism_registry")
        }

    request: dict[str, object] = {
        "exec_plan_ref": _ref_payload("4", "foundry.exec_plan"),
        "input_bindings_ref": _ref_payload("5", "foundry.input_bindings"),
    }
    if feedback:
        request["feedback_config_ref"] = _ref_payload("6", "foundry.feedback_config")
    return {
        "schema_version": schema_version,
        "execution_mode": "feedback" if feedback else "single_step",
        "request": request,
        "exec_plan_ref": _ref_payload("4", "foundry.exec_plan"),
        "program_graph_ref": _ref_payload("7", "foundry.program_graph"),
        "trinity_bundle_ref": _ref_payload("8"),
        "candidate_ref": _ref_payload("9"),
        "candidate_data_snapshot_ref": _ref_payload("a"),
        "candidate_registry_bundle_ref": _ref_payload("b"),
        "input_bindings_ref": _ref_payload("5", "foundry.input_bindings"),
        "data_snapshot_ref": _ref_payload("c"),
        "bound_state_snapshot_ref": _ref_payload("d", "foundry.state_snapshot"),
        "binding_registry_ref": _ref_payload("e"),
        "compile_registry_ref": _ref_payload("f"),
        "runtime_registry_ref": _ref_payload("1"),
        "binding_registry_members": registry_members("2"),
        "compile_registry_members": registry_members("3"),
        "runtime_registry_members": registry_members("4"),
        "base_state_snapshot_ref": _ref_payload("5", "foundry.state_snapshot"),
        "effective_step": 0,
        "effective_seed": 17,
        "effective_seed_source": "request",
        "effective_mode": "dev",
        "effective_nan_guard_enabled": True,
        "effective_jit": False,
        "effective_capture_env": False,
        **({"feedback_execution_context": _feedback_context_payload()} if feedback else {}),
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


def test_core_simulation_result_projects_only_fields_declared_by_its_artifact_version() -> None:
    legacy_payload = _simulation_result_payload(
        None,
        schema_version="1.3",
        execution_source_status="not_recorded",
    )
    legacy_payload.pop("execution_input_basis_ref")
    legacy_payload.pop("execution_source_status")
    legacy = SimulationResult.model_validate(legacy_payload)

    legacy_artifact = legacy.to_artifact_payload()

    assert legacy_artifact["schema_version"] == "1.3"
    assert set(legacy_artifact) == set(SimulationResult.model_fields) - {
        "execution_input_basis_ref",
        "execution_source_status",
    }

    selected = SimulationResult.model_validate(_simulation_result_payload(_basis_ref_payload()))
    selected_artifact = selected.to_artifact_payload()

    assert selected_artifact["schema_version"] == "1.4"
    assert selected_artifact["execution_source_status"] == "single_step_basis"
    assert selected_artifact["execution_input_basis_ref"] == _basis_ref_payload()


@pytest.mark.parametrize(
    ("schema_version", "basis_ref", "source_status"),
    [
        ("1.3", None, "single_step_basis"),
        ("1.3", _basis_ref_payload(), "not_recorded"),
        ("1.2", None, "not_recorded"),
    ],
)
def test_core_simulation_result_refuses_unrepresentable_artifact_versions(
    schema_version: str,
    basis_ref: dict[str, str] | None,
    source_status: str,
) -> None:
    payload = _simulation_result_payload(
        basis_ref,
        schema_version=schema_version,
        execution_source_status=source_status,
    )

    if schema_version == "1.3" and (source_status != "not_recorded" or basis_ref is not None):
        with pytest.raises(ValidationError):
            SimulationResult.model_validate(payload)
        return

    result = SimulationResult.model_validate(payload)
    with pytest.raises(ValueError, match="unsupported_simulation_result_artifact_schema_version"):
        result.to_artifact_payload()


def test_feedback_execution_context_requires_truthful_graph_link_status() -> None:
    captured = FeedbackExecutionContext.model_validate(_feedback_context_payload())
    assert captured.execution_link_status == "captured"
    assert captured.final_graph_invocation_id == "graph-invocation-final"

    unavailable = FeedbackExecutionContext.model_validate(_feedback_context_payload(captured=False))
    assert unavailable.execution_link_status == "not_established"
    assert unavailable.final_graph_invocation_id is None

    malformed = _feedback_context_payload(captured=False)
    malformed["final_graph_invocation_id"] = "invented-invocation"
    with pytest.raises(ValidationError, match="feedback_execution_context_invocation_status_mismatch"):
        FeedbackExecutionContext.model_validate(malformed)


def test_feedback_basis_v1_3_is_typed_without_changing_prior_basis_wire_shapes() -> None:
    basis = FoundryExecutionInputBasis.model_validate(
        _basis_payload(schema_version="1.3", feedback=True)
    )
    assert basis.execution_mode == "feedback"
    assert basis.feedback_execution_context is not None
    assert basis.model_dump(mode="json")["feedback_execution_context"][
        "final_map_evaluation_id"
    ] == "map-eval-final"

    prior = FoundryExecutionInputBasis.model_validate(
        _basis_payload(schema_version="1.0", feedback=False)
    )
    prior_wire = prior.model_dump(mode="json")
    assert "feedback_execution_context" not in prior_wire
    assert prior_wire["execution_mode"] == "single_step"

    invalid = _basis_payload(schema_version="1.3", feedback=False)
    with pytest.raises(ValidationError, match="execution_input_basis_v1_3_requires_feedback_context"):
        FoundryExecutionInputBasis.model_validate(invalid)


def test_simulation_result_v1_5_requires_both_feedback_basis_and_solve_result() -> None:
    payload = _simulation_result_payload(
        _basis_ref_payload(), schema_version="1.5", execution_source_status="feedback_basis"
    )
    payload["feedback_result_ref"] = _ref_payload("6", "foundry.feedback_result")
    result = SimulationResult.model_validate(payload)
    assert result.to_artifact_payload()["execution_source_status"] == "feedback_basis"

    missing_basis = dict(payload)
    missing_basis["execution_input_basis_ref"] = None
    with pytest.raises(ValidationError, match="feedback_basis_status_requires_schema_1_5_basis_and_result"):
        SimulationResult.model_validate(missing_basis)

    wrong_version = dict(payload)
    wrong_version["schema_version"] = "1.4"
    with pytest.raises(ValidationError, match="feedback_basis_status_requires_schema_1_5_basis_and_result"):
        SimulationResult.model_validate(wrong_version)
