from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    _abm_result_stub,
    build_abm_result_from_simulation,
    build_content_bound_abm_result,
)
from polisyos.ir.analytics.phase4_dynamics import (
    ABMResult,
    load_abm_result,
    persist_abm_result,
    verify_strangle_receipt,
)

_TYPED_SIMULATION_REF_KINDS = (
    ("exec_plan_ref", None, "foundry.exec_plan"),
    ("metrics_ref", None, "foundry.metrics"),
    ("metric_observation_bundle_ref", None, "foundry.metric_observation_bundle"),
    ("state_snapshot_ref", None, "foundry.state_snapshot"),
    ("environment_ref", None, "foundry.environment_manifest"),
    ("trace_slice_ref", None, "foundry.trace_slice"),
    ("uncertainty_envelopes", "outcome", "ir.uncertainty_envelope"),
    ("distributional_report_ref", None, "ir.distributional_report"),
    ("welfare_bundle_ref", None, "ir.welfare_bundle"),
    ("welfare_bound_refs", "aggregate", "foundry.welfare_bound_report"),
    ("metric_validation_report_ref", None, "scientist.metric_validation_report"),
    ("fairness_audit_report_ref", None, "scientist.fairness_audit_report"),
    ("feedback_result_ref", None, "foundry.feedback_result"),
    ("identifiability_diagnostic_ref", None, "foundry.identifiability_diagnostic"),
)


def _artifact_id(char: str) -> str:
    return f"sha256:{char * 64}"


def _ref(char: str, kind: str, *, media_type: str = "application/json") -> dict[str, str]:
    return {
        "artifact_id": _artifact_id(char),
        "kind": kind,
        "media_type": media_type,
    }


def _fully_populated_simulation_payload() -> dict[str, object]:
    return {
        "schema_version": "1.3",
        "exec_plan_ref": _ref("0", "foundry.exec_plan"),
        "metrics_ref": _ref("1", "foundry.metrics"),
        "metric_observation_bundle_ref": _ref("2", "foundry.metric_observation_bundle"),
        "state_snapshot_ref": _ref("3", "foundry.state_snapshot"),
        "environment_ref": _ref("4", "foundry.environment_manifest"),
        "environment_fingerprint": "test-environment",
        "trace_slice_ref": _ref("5", "foundry.trace_slice", media_type="application/jsonl"),
        "uncertainty_envelopes": {
            "outcome": _ref("6", "ir.uncertainty_envelope"),
        },
        "distributional_report_ref": _ref("7", "ir.distributional_report"),
        "welfare_bundle_ref": _ref("8", "ir.welfare_bundle"),
        "welfare_bound_refs": {
            "aggregate": _ref("9", "foundry.welfare_bound_report"),
        },
        "metric_validation_report_ref": _ref("a", "scientist.metric_validation_report"),
        "fairness_audit_report_ref": _ref("b", "scientist.fairness_audit_report"),
        "propagation_config_ref": _ref("c", "foundry.propagation_config"),
        "propagation_report_ref": _ref("d", "foundry.propagation_report"),
        "feedback_result_ref": _ref("e", "foundry.feedback_result"),
        "identifiability_diagnostic_ref": _ref("f", "foundry.identifiability_diagnostic"),
        "notes": ["fully_populated_core_result"],
    }


def test_abm_stub_is_fixture_only_and_default_path_is_content_bound() -> None:
    payload = {
        "trajectory": [{"step": 0, "final_queue_length": 1.0}],
        "metrics": {"completed_count": 2},
    }
    diagnostics = {"warnings": [], "engine": "simulation.coupled_policy.des_abm"}

    with pytest.raises(RuntimeError, match="abm_result_stub_strangled"):
        _abm_result_stub(method_id="simulation.coupled_policy.des_abm", horizon=3)
    fixture = _abm_result_stub(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        fixture_only=True,
    )
    assert "phase4_abm_result_stub" in fixture.model_dump_json()

    first = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )
    second = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )

    assert first == second
    assert first.identifiability_certificate is not None
    assert first.identifiability_certificate.status == "diagnostic_attached"
    assert first.notes
    assert "phase4_abm_result_stub" not in first.model_dump_json()
    receipt_note = next(note for note in first.notes if note.startswith("strangle_receipt:"))
    receipt = receipt_note.removeprefix("strangle_receipt:")
    verify_strangle_receipt(
        receipt,
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload=payload,
        diagnostics=diagnostics,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "exec_plan_ref": {
                "artifact_id": "sha256:" + ("a" * 64),
                "kind": "foundry.exec_plan",
                "media_type": "application/json",
            }
        },
        {
            "exec_plan_ref": {
                "artifact_id": "sha256:" + ("a" * 64),
                "kind": "foundry.exec_plan",
                "media_type": "application/json",
            },
            "metrics_ref": {
                "artifact_id": "not-a-content-address",
                "kind": "foundry.metrics",
                "media_type": "application/json",
            },
        },
    ],
)
def test_core_simulation_conversion_rejects_malformed_or_incomplete_payload(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        build_abm_result_from_simulation(payload)


@pytest.mark.parametrize(
    ("field_name", "mapping_key", "expected_kind"),
    _TYPED_SIMULATION_REF_KINDS,
)
def test_core_simulation_conversion_rejects_every_swapped_typed_ref_kind(
    field_name: str,
    mapping_key: str | None,
    expected_kind: str,
) -> None:
    typed_fields = {field for field, _, _ in _TYPED_SIMULATION_REF_KINDS}
    assert typed_fields == set(SimulationResult.model_fields) - {
        "schema_version",
        "environment_fingerprint",
        "propagation_config_ref",
        "propagation_report_ref",
        "notes",
    }
    kinds = [kind for _, _, kind in _TYPED_SIMULATION_REF_KINDS]
    swapped_kind = kinds[(kinds.index(expected_kind) + 1) % len(kinds)]
    payload = deepcopy(_fully_populated_simulation_payload())
    ref_payload = payload[field_name]
    if mapping_key is not None:
        assert isinstance(ref_payload, dict)
        ref_payload = ref_payload[mapping_key]
    assert isinstance(ref_payload, dict)
    ref_payload["kind"] = swapped_kind

    with pytest.raises(ValidationError, match="kind"):
        build_abm_result_from_simulation(payload)


@pytest.mark.parametrize(
    ("override_name", "wrong_kind"),
    [
        ("identifiability_diagnostic_ref", "foundry.attractor_analysis_result"),
        ("attractor_analysis_ref", "foundry.identifiability_diagnostic"),
    ],
)
def test_core_simulation_conversion_rejects_swapped_override_ref_kind(
    override_name: str,
    wrong_kind: str,
) -> None:
    simulation = SimulationResult.model_validate(_fully_populated_simulation_payload())
    override = _ref("a", wrong_kind)

    with pytest.raises(ValidationError, match="kind"):
        build_abm_result_from_simulation(simulation, **{override_name: override})


def test_fully_populated_core_result_converts_and_persists_with_wire_equivalence(
    tmp_path,
) -> None:
    simulation = SimulationResult.model_validate(_fully_populated_simulation_payload())
    result = build_abm_result_from_simulation(
        simulation,
        attractor_analysis_ref=_ref("a", "foundry.attractor_analysis_result"),
        bifurcation_count=2,
        attractor_count=3,
    )
    store = FileSystemCAS(tmp_path)

    ref = persist_abm_result(store, result)
    loaded = load_abm_result(store, ref)

    assert SimulationResult not in ABMResult.__mro__
    assert loaded == result
    assert result.model_dump(
        mode="json",
        exclude={"identifiability_certificate", "bifurcation_report"},
    ) == simulation.model_dump(mode="json")
    assert type(result.exec_plan_ref) is not type(simulation.exec_plan_ref)
    assert type(result.metrics_ref) is not type(simulation.metrics_ref)
    assert type(result.state_snapshot_ref) is not type(simulation.state_snapshot_ref)
    assert result.identifiability_certificate is not None
    assert result.identifiability_certificate.diagnostic_ref is not None
    assert result.bifurcation_report is not None
    assert result.bifurcation_report.attractor_analysis_ref is not None


def test_foundry_producer_persists_for_ir_result_consumer(tmp_path) -> None:
    result = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=3,
        payload={
            "trajectory": [{"step": 0, "final_queue_length": 1.0}],
            "metrics": {"completed_count": 2},
        },
        diagnostics={"engine": "simulation.coupled_policy.des_abm", "warnings": []},
    )
    store = FileSystemCAS(tmp_path)

    ref = persist_abm_result(store, result)
    loaded = load_abm_result(store, ref)

    assert not isinstance(result, SimulationResult)
    assert loaded == result
    assert loaded.identifiability_certificate is not None
    assert loaded.identifiability_certificate.status == "diagnostic_attached"


def test_production_simulation_modules_have_zero_abm_stub_callers() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    relative_paths = (
        Path("src/polisyos/foundry/methods/catalog/simulation/dynamics.py"),
        Path("src/polisyos/foundry/methods/catalog/simulation/coupled.py"),
    )

    callers: list[str] = []
    for relative_path in relative_paths:
        module = ast.parse((repo_root / relative_path).read_text(encoding="utf-8"))
        callers.extend(
            f"{relative_path}:{node.lineno}"
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_abm_result_stub"
        )

    assert callers == []
