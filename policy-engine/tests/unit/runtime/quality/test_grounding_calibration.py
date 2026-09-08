"""Pre-outcome declarations cannot acquire correctness authority."""

from __future__ import annotations

import importlib
from datetime import UTC

import pytest


def test_frame_tier_is_blind_to_binding_outcomes_and_shared_sources_cluster() -> None:
    """The same inputs and shared source remain one cluster after outcome changes."""
    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    inputs = tuple(
        owner.CalibrationFrameInput(
            input_id=f"synthetic-input-{index}",
            synthetic=True,
            operator_family="tax_relief_rate",
            target_type="policy_slot",
            domain="synthetic_domain",
            signature={
                "X_do": ["global.tax_rate"],
                "modal_claims": {"L6": {"target": "global.tax_rate"}, "WMR": {}},
                "admissibility": outcome,
            },
            source_units=("synthetic-source:shared",),
        )
        for index, outcome in enumerate(("passed", "failed"))
    )
    assert owner.difficulty_tier(inputs[0]) == owner.difficulty_tier(inputs[1])
    assert owner.source_clusters(inputs) == ((inputs[0].input_id, inputs[1].input_id),)


def _frame(reference=None):
    from datetime import datetime

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    row = owner.CalibrationFrameInput(
        input_id="synthetic-tax-input",
        synthetic=True,
        operator_family="tax_relief_rate",
        target_type="policy_slot",
        domain="synthetic_domain",
        signature={"X_do": ["global.tax_rate"], "modal_claims": {"L6": {}, "WMR": {}}},
        source_units=("synthetic-source:shared",),
    )
    return owner.declare_calibration_frame(
        [row],
        source_refs={"synthetic": "synthetic-source:shared"},
        selected_stratum=(
            row.operator_family,
            row.target_type,
            row.domain,
            owner.difficulty_tier(row),
        ),
        declared_at=datetime(2026, 9, 8, tzinfo=UTC),
        epoch_scope=owner.GroundingEpochScope(
            proposer_model="synthetic-model",
            prompt_version="synthetic-prompt",
            atom_birth_cohort="synthetic-cohort",
            reference_epoch=reference.reference_epoch if reference else "synthetic-epoch",
        ),
    )


def test_frame_scope_stales_on_each_epoch_component_and_never_grants_synthetic_authority() -> None:
    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    frame = _frame()
    result = owner.calibration_frame_scope(
        frame, epoch_scope=frame.epoch_scope, stratum=frame.selected_stratum
    )
    assert result["reason"] == "synthetic_frame_cannot_grant_authority"
    assert result["authority_band"] == "candidate"
    assert result["correctness_bound"] is None
    for key in type(frame.epoch_scope).model_fields:
        changed = frame.epoch_scope.model_copy(update={key: "changed-before-next-bind"})
        result = owner.calibration_frame_scope(
            frame, epoch_scope=changed, stratum=frame.selected_stratum
        )
        assert result["reason"] == "certificate_epoch_scope_stale", key
    assert (
        owner.calibration_frame_scope(
            frame, epoch_scope=frame.epoch_scope, stratum=("new", "stratum", "candidate", "only")
        )["reason"]
        == "stratum_outside_predeclared_campaign"
    )


def test_source_clusters_follow_transitive_support_not_row_identity() -> None:
    import pytest

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    row = _frame().inputs[0]
    rows = [
        row.model_copy(update={"input_id": name, "source_units": refs})
        for name, refs in (
            ("a", ("a-source",)),
            ("b", ("a-source", "b-source")),
            ("c", ("b-source",)),
            ("d", ("d-source",)),
        )
    ]
    assert owner.source_clusters(rows) == (("a", "b", "c"), ("d",))
    with pytest.raises(ValueError, match="independence_not_established"):
        owner.source_clusters([row.model_copy(update={"source_units": ()})])


def test_declaration_content_mutation_is_refused_and_growth_is_data_only() -> None:
    import pytest

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    frame = _frame()
    payload = frame.model_dump(mode="json")
    payload["inputs"][0]["operator_family"] = "present-but-fake"
    with pytest.raises(ValueError, match="content_hash_mismatch"):
        owner.CalibrationFrame.model_validate(payload)
    grown = owner.declare_calibration_frame(
        [
            *frame.inputs,
            frame.inputs[0].model_copy(
                update={"input_id": "novel-input", "operator_family": "novel-operator"}
            ),
        ],
        source_refs=frame.input_source_refs,
        selected_stratum=frame.selected_stratum,
        epoch_scope=frame.epoch_scope,
        declared_at=frame.declared_at,
    )
    assert {row.input_id for row in grown.inputs} == {"synthetic-tax-input", "novel-input"}
    assert owner.source_clusters(grown.inputs) == (("novel-input", "synthetic-tax-input"),)


def test_refusal_suite_predeclared_complete_and_refusal_reason_is_structural() -> None:
    from dataclasses import replace
    from datetime import timedelta

    from polisyos.pdc import gy_content_hash
    from tests.unit.runtime.quality.test_grounding_bind import _reference

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    original = _reference()
    edges = {
        key: replace(edge, provenance={**edge.provenance, "synthetic": True}).with_content_hash()
        for key, edge in original.essential_edges.items()
    }
    reference = replace(
        original,
        essential_edges=edges,
        reference_hash=gy_content_hash([edge.to_payload() for edge in edges.values()]),
    )
    frame = _frame(reference)
    suite = owner.declare_refusal_suite(frame, reference, declared_at=frame.declared_at)
    report = owner.run_refusal_suite(
        suite, frame, reference, executed_at=frame.declared_at + timedelta(seconds=1)
    )
    assert not report["issues"]
    assert {row["case_id"] for row in report["outcomes"]} == {
        row.case_id for row in suite.mismatches
    }
    assert report["binder_refused"] == len(suite.mismatches)
    assert all(row["decision_reason"] == "false_analog_hard_abstain" for row in report["outcomes"])
    assert all(not row["governed_authority"] for row in report["outcomes"])
    assert all(
        row["reason"] == "synthetic_input_candidate_only"
        for row in report["matched_controls_outside_denominator"]
    )
    assert owner.REFUSAL_LIMITATION in report["statement"]


def test_suite_refuses_execution_before_declaration_and_keeps_novel_input_ambiguous() -> None:
    from datetime import timedelta

    import pytest

    from tests.unit.runtime.quality.test_grounding_bind import _reference

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    reference = _reference()
    frame = _frame(reference)
    suite = owner.declare_refusal_suite(frame, reference, declared_at=frame.declared_at)
    with pytest.raises(ValueError, match="not_declared_before_execution"):
        owner.run_refusal_suite(
            suite, frame, reference, executed_at=frame.declared_at - timedelta(seconds=1)
        )
    novel = frame.inputs[0].model_copy(update={"input_id": "novel", "operator_family": "novel-op"})
    grown = owner.declare_calibration_frame(
        [*frame.inputs, novel],
        source_refs=frame.input_source_refs,
        selected_stratum=frame.selected_stratum,
        epoch_scope=frame.epoch_scope,
        declared_at=frame.declared_at,
    )
    grown_suite = owner.declare_refusal_suite(grown, reference, declared_at=frame.declared_at)
    assert grown_suite.ambiguous_inputs == ("novel",)
    assert {row.case_id for row in grown_suite.mismatches} == {
        row.case_id for row in suite.mismatches
    }
    assert len(grown_suite.mismatches) + len(grown_suite.ambiguous_inputs) == len(grown.inputs)


def test_refusal_report_rejects_fallback_when_binder_structural_guard_is_removed(
    monkeypatch,
) -> None:
    from datetime import timedelta

    from polisyos.runtime.quality import grounding_bind
    from tests.unit.runtime.quality.test_grounding_bind import _reference

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    reference = _reference()
    frame = _frame(reference)
    suite = owner.declare_refusal_suite(frame, reference, declared_at=frame.declared_at)
    monkeypatch.setattr(grounding_bind, "_has_selected_critical_veto", lambda _certificate: False)
    report = owner.run_refusal_suite(
        suite, frame, reference, executed_at=frame.declared_at + timedelta(seconds=1)
    )
    assert report["outcomes"][0]["refused"]
    assert report["outcomes"][0]["mismatch_detected"]
    assert report["outcomes"][0]["decision_reason"] != "false_analog_hard_abstain"
    assert "constructed_mismatch_not_structurally_refused" in report["issues"]


@pytest.mark.parametrize("intake", ["declaration", "execution"])
def test_frame_intakes_recompute_mutable_nested_content(intake: str) -> None:
    from datetime import timedelta
    from functools import partial

    from tests.unit.runtime.quality.test_grounding_bind import _reference

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    reference = _reference()
    frame = _frame(reference)
    suite = owner.declare_refusal_suite(frame, reference, declared_at=frame.declared_at)
    # Neither the selectors nor the declared hash change. This is the source
    # property the gate promises to bind, beyond its convenient selector proxy.
    frame.inputs[0].signature["params"] = {"synthetic": True, "maximum": 200}
    action = (
        partial(owner.declare_refusal_suite, frame, reference, declared_at=frame.declared_at)
        if intake == "declaration"
        else partial(
            owner.run_refusal_suite,
            suite,
            frame,
            reference,
            executed_at=frame.declared_at + timedelta(seconds=1),
        )
    )
    with pytest.raises(ValueError, match="content_hash_mismatch"):
        action()
