from __future__ import annotations

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    PhaseTransition,
    load_abm_alignment_report,
    persist_abm_alignment_report,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation as IRCanonViolation
from polisyos.ir.registry.refs import ABMAlignmentReportRef


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

    ref = persist_abm_alignment_report(_ensure_ir_artifact_store(store), report)
    loaded = load_abm_alignment_report(_ensure_ir_artifact_store(store), ref)

    assert isinstance(ref, ABMAlignmentReportRef)
    assert ref.kind == "ir.abm_alignment_report"
    assert loaded == report


def test_abm_alignment_rejects_malformed_embedded_version_before_cas_write(tmp_path) -> None:
    class CountingCAS(FileSystemCAS):
        def __init__(self, root):
            super().__init__(root)
            self.put_calls = 0

        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            self.put_calls += 1
            return super().put_json(
                obj, opts, canon_spec, return_selected_profile=return_selected_profile
            )

    store = CountingCAS(tmp_path)
    malformed = ABMAlignmentReport().model_copy(update={"schema_version": 1.0})
    with pytest.raises(IRCanonViolation, match="ir_owned_artifact_payload_version_invalid"):
        persist_abm_alignment_report(_ensure_ir_artifact_store(store), malformed)
    assert store.put_calls == 0


def test_abm_alignment_rejects_malformed_override_before_cas_write(tmp_path) -> None:
    class CountingCAS(FileSystemCAS):
        def __init__(self, root):
            super().__init__(root)
            self.put_calls = 0

        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            self.put_calls += 1
            return super().put_json(
                obj, opts, canon_spec, return_selected_profile=return_selected_profile
            )

    store = CountingCAS(tmp_path)
    with pytest.raises(IRCanonViolation, match="ir_owned_artifact_write_override_invalid"):
        persist_abm_alignment_report(
            _ensure_ir_artifact_store(store),
            ABMAlignmentReport(),
            schema_name="ir.abm_alignment_report",
            schema_version=[],
        )
    assert store.put_calls == 0


def test_abm_alignment_keeps_unknown_history_opaque_and_typed_read_strict(tmp_path) -> None:
    class CountingCAS(FileSystemCAS):
        def __init__(self, root):
            super().__init__(root)
            self.payload_reads = 0

        def get_bytes(self, artifact_id):
            self.payload_reads += 1
            return super().get_bytes(artifact_id)

    store = CountingCAS(tmp_path)
    payload = ABMAlignmentReport().model_dump(mode="json")
    raw_ref = store.put_json(
        payload,
        PutOptions(
            kind="ir.abm_alignment_report",
            media_type="application/json",
            schema=SchemaInfo(name="ir.abm_alignment_report", version="1.5"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    selected_ref = ABMAlignmentReportRef.model_validate(raw_ref.model_dump(mode="python"))
    assert get_json_artifact(_ensure_ir_artifact_store(store), selected_ref) == payload
    store.payload_reads = 0

    with pytest.raises(IRCanonViolation, match="ir_owned_artifact_representation_unregistered"):
        load_abm_alignment_report(_ensure_ir_artifact_store(store), selected_ref)
    assert store.payload_reads == 0


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
