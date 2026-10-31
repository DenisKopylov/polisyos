"""Exercise the real OpenAPI generator's assigned output boundary."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.ops_runners.runtime import export_runtime_openapi as exporter


def test_real_openapi_export_confines_app_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep the complete live schema while confining app construction writes."""
    from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract

    output_root = tmp_path / "assigned"
    output = output_root / "runtime_api_v1.openapi.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["export_runtime_openapi", "--output", str(output)])
    assert exporter.main() == 0
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert not validate_runtime_openapi_contract(schema)

    operation_ids = (
        "get_control_pre_admission_attempt_by_idempotency_key",
        "get_control_pre_admission_attempt_status",
        "create_run_predictive_calibration",
        "get_run_predictive_calibration",
    )

    def find_operation(document: dict[str, object], operation_id: str):
        paths = document["paths"]
        assert isinstance(paths, dict)
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                    return str(path), str(method), operation
        raise AssertionError(f"missing operation: {operation_id}")

    missing_examples = deepcopy(schema)
    for operation_id in operation_ids:
        _path, _method, operation = find_operation(missing_examples, operation_id)
        responses = operation["responses"]
        status_code = min(
            (
                status
                for status in responses
                if isinstance(status, str) and status.isdigit() and 200 <= int(status) < 300
            ),
            key=int,
        )
        json_payload = responses[status_code]["content"]["application/json"]
        json_payload.pop("examples", None)
        json_payload.pop("example", None)
    missing_violations = validate_runtime_openapi_contract(missing_examples)
    for operation_id in operation_ids:
        path, method, _operation = find_operation(schema, operation_id)
        assert f"{method.upper()} {path}: missing 2xx success response example" in (
            missing_violations
        )

    malformed_examples = deepcopy(schema)
    for operation_id in operation_ids:
        _path, _method, operation = find_operation(malformed_examples, operation_id)
        responses = operation["responses"]
        status_code = min(
            (
                status
                for status in responses
                if isinstance(status, str) and status.isdigit() and 200 <= int(status) < 300
            ),
            key=int,
        )
        examples = responses[status_code]["content"]["application/json"]["examples"]
        example_value = next(iter(examples.values()))["value"]
        if operation_id.startswith("get_control_pre_admission_attempt_"):
            example_value["status"] = "completed"
        else:
            example_value["association"]["assessment"] = "supported"
    malformed_violations = validate_runtime_openapi_contract(malformed_examples)
    for operation_id in operation_ids:
        path, method, operation = find_operation(schema, operation_id)
        status_code = min(
            (
                status
                for status in operation["responses"]
                if isinstance(status, str) and status.isdigit() and 200 <= int(status) < 300
            ),
            key=int,
        )
        assert any(
            f"{method.upper()} {path}: {status_code} success example " in violation
            and "does not match registered response model" in violation
            for violation in malformed_violations
        )

    outside = sorted(
        str(path.relative_to(tmp_path))
        for path in tmp_path.rglob("*")
        if path.is_file() and not path.is_relative_to(output_root)
    )
    assert outside == [], f"openapi_app_artifacts_escaped_assigned_output: {outside}"
    assert sorted(
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    ) == [output.name]


def test_predictive_coverage_openapi_example_uses_canonical_read() -> None:
    """Keep the exported candidate bound to a conformant, explicitly limited read."""
    from polisyos.runtime.http.openapi_contract import (
        _predictive_coverage_diagnostic_success_examples,
    )

    candidate = _predictive_coverage_diagnostic_success_examples()[
        "limited_not_measured_candidate"
    ]["value"]

    assert candidate["canon_read_status"] == "declared_bytes_conformant"
    assert candidate["source_materialization"] == "reader_materialized"
    assert candidate["assessment"] == "limited"
    assert candidate["producer_attestation_status"] == "not_established"
    assert candidate["measurement_status"] == "not_measured"
    assert candidate["reason_code"] == "unsupported_report_scope"
    assert candidate["scenarios"] == []
    assert candidate["counterfactual_credibility_status"] == "not_established"
    assert candidate["causal_effect_status"] == "not_established"
    assert candidate["source_manifest_profile_sha256"].startswith("sha256:")
    assert candidate["source_artifact_id"].startswith("sha256:")
    assert candidate["source_artifact_id"] != "sha256:" + "a" * 64


def test_predictive_coverage_openapi_example_rejects_payload_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matching manifest/status shape cannot admit bytes with a different content ID."""
    from polisyos.common.canonical_profile import (
        CanonicalProfileRead,
        CanonicalProfileRefusalError,
    )
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore, canonical_profile
    from polisyos.runtime.http.openapi_contract import (
        _predictive_coverage_diagnostic_success_examples,
    )

    reader = canonical_profile.read_core_json_artifact

    def read_corrupted_payload(store: ArtifactStore, selector: ArtifactRef) -> CanonicalProfileRead:
        raw = store.get_bytes(selector)
        corrupted = raw[:-1] + bytes([raw[-1] ^ 1])
        return reader(store, selector, raw_payload_bytes=corrupted)

    monkeypatch.setattr(canonical_profile, "read_core_json_artifact", read_corrupted_payload)
    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_selected_payload_identity_mismatch",
    ):
        _predictive_coverage_diagnostic_success_examples()


def test_pre_admission_openapi_examples_use_current_owner_readback() -> None:
    """Require both recovery routes to use the producer's actor-scoped typed projection."""
    from pydantic import TypeAdapter

    from polisyos.core.contracts.control_admission_attempt import (
        ControlPreAdmissionAttemptResponse,
    )
    from polisyos.runtime.http.openapi_contract import (
        _pre_admission_attempt_response_examples,
        _pre_admission_by_attempt_id_success_examples,
        _pre_admission_by_idempotency_success_examples,
    )

    by_key = _pre_admission_by_idempotency_success_examples()["controlled_no_call_refusal"]
    by_attempt = _pre_admission_by_attempt_id_success_examples()["controlled_no_call_refusal"]
    response_adapter = TypeAdapter(ControlPreAdmissionAttemptResponse)
    key_wire = json.dumps(by_key["value"], ensure_ascii=False, allow_nan=False)
    attempt_wire = json.dumps(by_attempt["value"], ensure_ascii=False, allow_nan=False)
    key_response = response_adapter.validate_json(key_wire, strict=True)
    attempt_response = response_adapter.validate_json(attempt_wire, strict=True)

    assert key_response.model_dump(mode="json") == json.loads(key_wire)
    assert attempt_response.model_dump(mode="json") == json.loads(attempt_wire)
    assert key_response.model_dump(mode="json") == attempt_response.model_dump(mode="json")
    assert key_response.status == "refused"
    assert key_response.producer_event_observation == "no_call"
    assert key_response.producer_no_call_reason == "provider_preflight_not_started"
    assert key_response.failure_code == "provider_preflight_not_started"
    assert key_response.producer_event_ids == []
    assert [event.event_type for event in key_response.history] == ["started", "refused"]
    assert key_response.owner_binding.purpose == "control.nl_pre_admission.v1"
    assert "no provider call" in by_key["description"]
    assert "production attempt" in by_key["description"]
    assert "deterministic event IDs" in by_key["description"]

    _pre_admission_attempt_response_examples.cache_clear()
    repeated = _pre_admission_by_idempotency_success_examples()["controlled_no_call_refusal"][
        "value"
    ]
    assert repeated == json.loads(key_wire)


def test_openapi_renderer_uses_the_assigned_runtime_store_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check and exporter must build equivalent apps without default CAS writes."""
    from tools.ops_runners.runtime import export_runtime_openapi as exporter

    observed: dict[str, object] = {}

    class _FakeApp:
        def openapi(self) -> dict[str, object]:
            return {"paths": {}}

    def build_app(**kwargs: object) -> _FakeApp:
        observed.update(kwargs)
        return _FakeApp()

    monkeypatch.setattr(
        "polisyos.runtime.http.app.create_runtime_api_app",
        build_app,
    )
    assert exporter.render_runtime_openapi(tmp_path) == {"paths": {}}
    assert observed == {
        "enable_security_middlewares": False,
        "cas_root": tmp_path / "cas",
    }


def test_predictive_calibration_openapi_example_is_limited_and_unresolved(tmp_path: Path) -> None:
    """Do not turn placeholder calibration handles into current or authoritative evidence."""
    from pydantic import TypeAdapter

    from polisyos.runtime.http.openapi_contract import _predictive_calibration_success_examples
    from polisyos.runtime.http.services.predictive_calibration import (
        PredictiveCalibrationResponse,
    )

    example = _predictive_calibration_success_examples()[
        "controlled_insufficient_history_candidate"
    ]
    response_wire = json.dumps(example["value"], ensure_ascii=False, allow_nan=False)
    candidate = TypeAdapter(PredictiveCalibrationResponse).validate_json(response_wire, strict=True)

    assert candidate.model_dump(mode="json") == json.loads(response_wire)
    assert candidate.association.assessment == "limited"
    assert candidate.association.authority_scope == "predictive_only"
    assert candidate.association.s10.calibration_status == "blocked"
    assert candidate.association.s10.forecast_tier == "blocked"
    assert candidate.association.observed_numerator is None
    assert candidate.association.observed_denominator is None
    assert candidate.association.observed_hit_rate is None
    assert candidate.association.s10.numerator is None
    assert candidate.association.s10.denominator is None
    assert candidate.association.s10.observed_pass_rate is None
    assert candidate.association.s10.calibration_record_ref is None
    assert "backtest_source_not_established" in candidate.association.evidence_reason_codes
    assert (
        "s10://calibration/fail-closed/backtest_source_not_established"
        in candidate.association.s10.limitation_refs
    )
    assert candidate.association.issuer_status == "not_established"
    assert candidate.association.source_time_status == "not_established"
    assert candidate.association.population_scope_status == "not_established"
    assert candidate.association.counterfactual_credibility_status == "not_established"
    assert candidate.association_ref.manifest_profile_sha256 is not None
    for reference in (
        candidate.association.run_manifest_ref,
        candidate.association.candidate_source_ref,
        candidate.association.observed_source_ref,
        candidate.association.model_spec_ref,
        candidate.association.policy_spec_ref,
        candidate.association.calibration_rule_ref,
        candidate.association.backtest_report_ref,
        candidate.association.empirical_evidence_ref,
        candidate.association.uncertainty_bundle_ref,
    ):
        assert reference.manifest_profile_sha256 is not None
    assert "deterministic synthetic" in example["description"]
    assert "no stored profile or provenance" in example["description"]
    assert "not persisted or reopenable evidence" in example["description"]
    # Retain this compact actual owner wire for cross-language parser verification.
    (tmp_path / "predictive-calibration-example.json").write_text(response_wire, encoding="utf-8")
