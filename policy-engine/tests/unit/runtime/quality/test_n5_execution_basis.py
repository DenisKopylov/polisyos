"""Retain actionable, bounded diagnostics without granting N5 reuse authority."""

from __future__ import annotations

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
