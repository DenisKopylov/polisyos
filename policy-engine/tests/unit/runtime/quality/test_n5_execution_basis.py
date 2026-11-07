"""Retain actionable, bounded diagnostics without granting N5 reuse authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality import confidence_ledger as ledger
from polisyos.runtime.quality import n5_execution_basis as basis


def _missing_selected_module() -> dict[str, Any]:
    """Exercise the actual source reader's typed error, without a numerical run."""
    ledger._loaded_code_manifest_body(
        Path(__file__).parent,
        (("polisyos._n5_missing_selected_module", "not_read.py"),),
    )
    raise AssertionError("the missing selected module must be refused")


def test_capture_preserves_actual_source_error_target_and_throw_site(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture = object.__new__(basis.N5ImplementationCapture)
    capture._supported = True
    capture._admission = object()
    capture._observer = SimpleNamespace(active=True, _observe=sys.getprofile(), suspended=False)
    capture._reasons = []
    monkeypatch.setattr(capture, "_current_implementation", _missing_selected_module)

    assert capture.__enter__() is capture
    assert capture._observer.suspended is False
    assert capture._reasons[0] == "canonical_loaded_runtime_mismatch"
    assert "n5_implementation_failure_target:polisyos._n5_missing_selected_module" in (
        capture._reasons
    )
    assert any(
        reason.startswith(
            "n5_implementation_failure_site:"
            "polisyos.runtime.quality.confidence_ledger._loaded_code_manifest_body:"
        )
        for reason in capture._reasons
    )
    assert not any(str(Path(__file__).parent) in reason for reason in capture._reasons)


def test_sealed_failed_capture_keeps_diagnostic_and_never_issues_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="n5_input",
        media_type="application/json",
    )
    capture = object.__new__(basis.N5ImplementationCapture)
    capture._admission = SimpleNamespace(input_ref=input_ref)
    capture._sealed = None
    capture._reasons = []
    capture._observer = SimpleNamespace(completed=True, reason=None)
    capture._entry = _missing_selected_module
    capture._codes = {0: SimpleNamespace(code=_missing_selected_module.__code__)}
    capture._trajectory_hash = basis.exact_n5_content_hash([])
    capture._trajectory_bytes = basis.exact_n5_content_bytes([])
    capture._request = {}
    capture._request_bytes = basis.exact_n5_content_bytes({})
    capture.request_hash = basis.exact_n5_content_hash({})
    capture._controller = object()
    capture._configuration_start = None
    monkeypatch.setattr(capture, "_current_implementation", _missing_selected_module)
    result = SimpleNamespace(trajectories=(), content_bound_payload=lambda: {"result": []})

    witness = capture.seal(input_ref=input_ref, result=result)

    assert witness.predicate_provenance == "not_established"
    assert "canonical_loaded_runtime_mismatch" in witness.reason_codes
    assert "n5_implementation_failure_target:polisyos._n5_missing_selected_module" in (
        witness.reason_codes
    )
    assert witness.implementation == {}
    assert witness.content_hash not in basis._ISSUED
    assert (
        basis.N5ExecutionImplementationWitness.model_validate_json(witness.model_dump_json())
        == witness
    )


@pytest.mark.parametrize(
    "detail",
    [
        "source invalid: /private/secret.py",
        "source invalid: https://example.invalid/token",
        "source invalid: polisyos.module\nsecret",
        "source invalid: polisyos.module?token=secret",
        "source invalid: " + "polisyos." + "x" * 512,
        "arbitrary credential or payload",
    ],
)
def test_unsafe_error_detail_is_not_persisted(detail: str) -> None:
    error = ledger.ConfidenceLedgerError("canonical_loaded_runtime_mismatch", detail)
    assert basis._implementation_failure_reasons(error) == ("canonical_loaded_runtime_mismatch",)


def test_detail_prefix_is_discarded_and_noncanonical_error_is_not_enriched() -> None:
    error = ledger.ConfidenceLedgerError(
        "canonical_loaded_runtime_mismatch", "private payload: polisyos.runtime.selected_slot"
    )
    assert basis._implementation_failure_reasons(error) == (
        "canonical_loaded_runtime_mismatch",
        "n5_implementation_failure_target:polisyos.runtime.selected_slot",
    )
    assert basis._implementation_failure_reasons(ValueError("ordinary refusal")) == (
        "ordinary refusal",
    )


def _historical_n5_result(
    input_ref: ArtifactRef,
    *,
    consumed_configuration: dict[str, Any] | None,
    predicate_provenance: str = "not_established",
    reason_codes: tuple[str, ...] = ("canonical_loaded_runtime_mismatch",),
) -> tuple[SimpleNamespace, basis.N5ExecutionImplementationWitness]:
    """Build an owner-reader compatible result and its content-bound witness."""
    from polisyos.core.artifacts import artifact_ref_identity_key
    from polisyos.runtime.quality.joint_simulation_horizon import (
        build_content_bound_simulation_receipt,
    )

    trajectory = {"run_level": "individual", "outcome": 0.5}
    without_witness = {
        "schema_version": "policyos.runtime.joint_simulation_horizon.v5",
        "trajectories": [trajectory],
        "diagnostics": {},
    }
    payload: dict[str, Any] = {
        "schema_version": "N5ExecutionImplementationWitness@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_scope": "same_live_process_loaded_implementation",
        "process_session": "historical-test-session",
        "input_ref_identity": artifact_ref_identity_key(input_ref),
        "request_content_hash": "sha256:" + "b" * 64,
        "result_without_witness_hash": basis.exact_n5_content_hash(without_witness),
        "trajectory_hash": basis.exact_n5_content_hash([trajectory]),
        "implementation": {},
        "consumed_configuration_values": consumed_configuration,
        "predicate_provenance": predicate_provenance,
        "reason_codes": reason_codes,
    }
    persisted = json.loads(json.dumps(payload))
    witness = basis.N5ExecutionImplementationWitness.model_validate(
        {
            **persisted,
            "content_hash": basis.exact_n5_content_hash(persisted),
        }
    )
    diagnostics = {basis._DIAGNOSTIC_KEY: witness.model_dump(mode="json")}
    result_payload = {**without_witness, "diagnostics": diagnostics}
    receipt = build_content_bound_simulation_receipt(
        engine_kind="ncm_parallel_worlds",
        payload=result_payload,
        diagnostics=diagnostics,
    )
    result = SimpleNamespace(
        receipt=receipt,
        diagnostics=diagnostics,
        trajectories=(SimpleNamespace(model_dump=lambda mode: dict(trajectory)),),
        content_bound_payload=lambda: result_payload,
    )
    return result, witness


def test_candidate_historical_configuration_matches_with_unknown_implementation() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, expected = _historical_n5_result(
        input_ref,
        consumed_configuration=basis._exact_native_content(prepared),
    )
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert witness.predicate_provenance == "not_established"
    assert witness == expected
    assert basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert basis._candidate_n5_experiment_observation_supported(witness, prepared)


@pytest.mark.parametrize("observation", [None, {}, {"unrelated": True}])
def test_candidate_historical_configuration_requires_exact_descriptor(
    observation: dict[str, Any] | None,
) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, _ = _historical_n5_result(input_ref, consumed_configuration=observation)
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert not basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert not basis._candidate_n5_experiment_observation_supported(witness, prepared)


@pytest.mark.parametrize(
    "reason",
    [
        "n5_execution_observer_conflict",
        "n5_execution_observer_interrupted",
        "n5_execution_observer_completion_not_established",
        "n5_selected_implementation_or_input_unsupported",
        "n5_selected_entry_not_observed",
        "n5_observed_trajectory_mismatch",
        "n5_input_changed_during_execution",
        "n5_implementation_changed_during_execution",
        "n5_consumed_configuration_not_established",
    ],
)
def test_candidate_experiment_rejects_physical_observation_failures_even_when_snapshots_match(
    reason: str,
) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    result, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=basis._exact_native_content(prepared),
        reason_codes=("canonical_loaded_runtime_mismatch", reason),
    )
    witness = basis.read_n5_execution_implementation_witness(result, input_ref=input_ref)

    assert basis._candidate_n5_historical_configuration_matches(witness, prepared)
    assert not basis._candidate_n5_experiment_observation_supported(witness, prepared)


def test_candidate_experiment_accepts_only_bounded_source_failure_diagnostics() -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    prepared = prepare_joint_simulation_configuration()
    input_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.quality.candidate_simulation_n5_input",
        media_type="application/json",
    )
    config = basis._exact_native_content(prepared)
    allowed, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=config,
        reason_codes=(
            "canonical_loaded_runtime_mismatch",
            "n5_implementation_failure_site:polisyos.runtime.quality.n5_execution_basis._current_implementation:123",
            "n5_implementation_failure_target:polisyos.runtime.quality.confidence_ledger",
        ),
    )
    unsupported, _ = _historical_n5_result(
        input_ref,
        consumed_configuration=config,
        reason_codes=(
            "canonical_loaded_runtime_mismatch",
            "n5_implementation_failure_site:external.module.function:123",
        ),
    )

    assert basis._candidate_n5_experiment_observation_supported(
        basis.read_n5_execution_implementation_witness(allowed, input_ref=input_ref), prepared
    )
    assert not basis._candidate_n5_experiment_observation_supported(
        basis.read_n5_execution_implementation_witness(unsupported, input_ref=input_ref), prepared
    )
