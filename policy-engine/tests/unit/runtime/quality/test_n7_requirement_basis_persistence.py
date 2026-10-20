"""N7 compiler-basis persistence and replay bindings."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_requirement import DataRequirementCompilationReport


def _compile_report(scenario_id: str) -> DataRequirementCompilationReport:
    from polisyos.data_requirement import DataRequirementCompiler

    return DataRequirementCompiler().compile_for_scenario(
        {
            "scenario_id": scenario_id,
            "text": "Assess a candidate public policy and identify the evidence it needs.",
            "domain": "public_policy",
        }
    )


def test_n7_persists_exact_compiler_report_and_replay_rejects_binding_drift(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.acquisition_planner import (
        persist_and_verify_data_requirement_compilation_report,
        validate_persisted_data_requirement_compilation_report,
    )

    store = FileSystemCAS(tmp_path / "compiler-report-cas")
    report = _compile_report("n7-basis-persistence")
    binding = persist_and_verify_data_requirement_compilation_report(
        store,
        report,
        expected_scenario_id="n7-basis-persistence",
    )

    assert binding.resolution == report.requirement_basis
    assert binding.producer_report_ref == report.producer_report_ref
    assert binding.input_content_hash == report.input_content_hash
    assert (
        validate_persisted_data_requirement_compilation_report(
            store,
            binding,
            expected_report=report,
        )
        == ()
    )

    forged_input = binding.model_copy(update={"input_content_hash": "sha256:" + "e" * 64})
    input_issues = validate_persisted_data_requirement_compilation_report(store, forged_input)
    assert "n7_compiler_report_binding_mismatch" in {issue["code"] for issue in input_issues}

    forged_digest = binding.model_copy(update={"compiler_report_digest": "sha256:" + "f" * 64})
    digest_issues = validate_persisted_data_requirement_compilation_report(store, forged_digest)
    assert "n7_compiler_report_digest_mismatch" in {issue["code"] for issue in digest_issues}


def test_n7_present_malformed_or_foreign_compiler_basis_is_a_refusal(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.acquisition_planner import (
        persist_and_verify_data_requirement_compilation_report,
    )

    store = FileSystemCAS(tmp_path / "compiler-report-cas")
    report = _compile_report("n7-basis-subject")

    with pytest.raises(TypeError, match="n7_compiler_report_untyped"):
        persist_and_verify_data_requirement_compilation_report(
            store,
            {"scenario_id": "n7-basis-subject"},
            expected_scenario_id="n7-basis-subject",
        )
    with pytest.raises(ValueError, match="n7_compiler_report_subject_or_input_binding_mismatch"):
        persist_and_verify_data_requirement_compilation_report(
            store,
            report,
            expected_scenario_id="foreign-scenario",
        )
