from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    PhaseTransition,
    load_abm_alignment_report,
    persist_abm_alignment_report,
)
from polisyos.ir.refs import ABMAlignmentReportRef


def test_macro_micro_mapping_accepts_supported_values() -> None:
    mapping = MacroMicroMapping(
        macro_variable="income_level",
        abm_aggregation="mean(agent.income)",
        aggregation_function="mean",
        agent_property="income",
        tolerance=0.15,
        tolerance_method="fixed",
    )

    assert mapping.aggregation_function.value == "mean"
    assert mapping.tolerance_method.value == "fixed"
    assert mapping.tolerance == pytest.approx(0.15)


def test_macro_micro_mapping_rejects_invalid_aggregation_or_tolerance() -> None:
    with pytest.raises(ValueError):
        MacroMicroMapping(
            macro_variable="x",
            abm_aggregation="foo",
            aggregation_function="avg",
            agent_property="income",
        )

    with pytest.raises(ValueError):
        MacroMicroMapping(
            macro_variable="x",
            abm_aggregation="foo",
            aggregation_function="mean",
            agent_property="income",
            tolerance=-0.1,
        )


def test_abm_alignment_report_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)

    report = ABMAlignmentReport(
        mappings=[
            MacroMicroMapping(
                macro_variable="income_level",
                abm_aggregation="mean(agent.income)",
                aggregation_function="mean",
                agent_property="income",
                tolerance_method="adaptive",
            )
        ],
        alignment_results={
            "income_level": AlignmentResult(
                scm_effect=0.4,
                abm_effect=0.35,
                status=AlignmentStatus.CONSISTENT,
                tolerance_used=0.12,
                delta=0.05,
                n_runs=6,
                metadata={"aggregation_function": "mean"},
            )
        },
        overall_consistent=True,
        phase_transitions=[
            PhaseTransition(
                variable="income_level",
                threshold_value=0.3,
                pre_regime="slope=0.2",
                post_regime="slope=1.1",
                jump_value=0.9,
            )
        ],
        warnings=["income_level: wide_tolerance_consistent_warning"],
    )

    ref = persist_abm_alignment_report(store, report)
    loaded = load_abm_alignment_report(store, ref)

    assert isinstance(ref, ABMAlignmentReportRef)
    assert ref.kind == "ir.abm_alignment_report"
    assert loaded == report


def test_alignment_result_serializes_status_enum() -> None:
    result = AlignmentResult(
        scm_effect=0.2,
        abm_effect=0.1,
        status=AlignmentStatus.INCONSISTENT,
        tolerance_used=0.05,
        delta=0.1,
        n_runs=5,
    )

    payload = result.model_dump(mode="json")
    assert payload["status"] == "inconsistent"
