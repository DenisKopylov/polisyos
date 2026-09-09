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


def _actual_proof_world_declaration():
    from pathlib import Path

    owner = importlib.import_module("polisyos.runtime.quality.grounding_calibration")
    root = Path(__file__).resolve().parents[4]
    declaration = owner.produce_grounding_proof_world_input(
        root,
        world_cas=root / ".tmp/gy-s-composed-wmr-cas",
        world_ref="sha256:e96949676a6f0c9278cc8a82bf083d34f982e90b1c071097e953b2ffbb585bb5",
    )
    return owner, root, declaration


def _rehashed_proof_declaration(owner, declaration, **updates):
    from polisyos.pdc import gy_content_hash

    payload = declaration.model_dump(mode="json")
    payload.update(updates)
    payload.pop("content_hash")
    payload["content_hash"] = gy_content_hash(payload)
    return owner.GroundingProofWorldInput.model_validate(payload)


def test_actual_proof_world_pin_replays_original_bytes_time_and_structural_reference() -> None:
    owner, root, declaration = _actual_proof_world_declaration()
    first = owner.resolve_grounding_proof_world_input(root, declaration)
    second = owner.resolve_grounding_proof_world_input(root, declaration)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.created_at == declaration.world_created_at == "2026-09-08T16:59:01.685331+00:00"
    assert first.content_hash == declaration.world_content_hash
    assert str(declaration.source_ref.artifact_id) != first.content_hash
    assert declaration.synthetic is True
    assert declaration.purpose == "structural_grounding_proof_only"
    a = owner.build_refusal_reference_scaffold(root, first)
    b = owner.build_refusal_reference_scaffold(root, second)
    assert a.reference_hash == b.reference_hash
    assert a.as_of == b.as_of == first.created_at
    assert a.essential_edges == b.essential_edges


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("world_created_at", "2026-09-09T00:00:00+00:00"),
        ("world_content_hash", "sha256:" + "a" * 64),
        ("source_schema_version", "policyos.runtime.world_model_record.invalid"),
    ],
)
def test_proof_world_pin_refuses_rehashed_false_source_metadata(field, replacement) -> None:
    owner, root, declaration = _actual_proof_world_declaration()
    invalid = _rehashed_proof_declaration(owner, declaration, **{field: replacement})
    with pytest.raises(ValueError, match="grounding_proof_world_binding_mismatch"):
        owner.resolve_grounding_proof_world_input(root, invalid)


@pytest.mark.parametrize("field", ["kind", "media_type", "artifact_id"])
def test_proof_world_pin_refuses_fake_source_identity_or_role(field) -> None:
    owner, root, declaration = _actual_proof_world_declaration()
    source = declaration.source_ref.model_dump(mode="json")
    source[field] = "sha256:" + "f" * 64 if field == "artifact_id" else "present-but-fake"
    invalid = _rehashed_proof_declaration(owner, declaration, source_ref=source)
    with pytest.raises((ValueError, FileNotFoundError)):
        owner.resolve_grounding_proof_world_input(root, invalid)


def test_another_actual_proof_world_pin_is_data_only_and_changes_epoch() -> None:
    owner, root, declaration = _actual_proof_world_declaration()
    # This is a diagnostic/control source, never the official pre-outcome pin.
    alternate = owner.produce_grounding_proof_world_input(
        root,
        world_cas=root / declaration.cas_root,
        world_ref="sha256:6476888e5fb6b8b7ac9d4389dbc7d0dfa9a0d0ea3095a217355214e85ede1d62",
    )
    original_world = owner.resolve_grounding_proof_world_input(root, declaration)
    alternate_world = owner.resolve_grounding_proof_world_input(root, alternate)
    assert original_world.content_hash == alternate_world.content_hash
    assert declaration.source_ref != alternate.source_ref
    a = owner.build_refusal_reference_scaffold(root, original_world)
    b = owner.build_refusal_reference_scaffold(root, alternate_world)
    assert a.essential_edges == b.essential_edges
    assert a.as_of != b.as_of
    assert a.reference_hash != b.reference_hash


def test_proof_source_matching_removal_is_decisive_with_original_positive(monkeypatch) -> None:
    owner, root, declaration = _actual_proof_world_declaration()
    invalid = _rehashed_proof_declaration(
        owner, declaration, world_created_at="2026-09-09T00:00:00+00:00"
    )
    assert owner.resolve_grounding_proof_world_input(root, declaration).created_at == declaration.world_created_at
    with pytest.raises(ValueError, match="grounding_proof_world_binding_mismatch"):
        owner.resolve_grounding_proof_world_input(root, invalid)
    monkeypatch.setattr(owner, "_world_matches_proof_input", lambda *_args: True)
    assert owner.resolve_grounding_proof_world_input(root, declaration).created_at == declaration.world_created_at
    # The unchanged refusal gate, when invoked with the guard removed, must red.
    assert owner.resolve_grounding_proof_world_input(root, invalid).created_at != invalid.world_created_at


def test_proof_world_pin_uses_core_integrity_for_bytes_outside_logical_hash() -> None:
    import json
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
    from polisyos.core.canon import CanonSpec

    owner, root, declaration = _actual_proof_world_declaration()
    original = owner.resolve_grounding_proof_world_input(root, declaration)
    with TemporaryDirectory(dir=root / ".tmp", prefix="proof-input-integrity-") as directory:
        store = FileSystemCAS(Path(directory))
        ref = store.put_json(
            original,
            PutOptions(
                kind=declaration.source_ref.kind,
                media_type=declaration.source_ref.media_type,
                schema=SchemaInfo(
                    name="polisyos.runtime.quality.WorldModelRecord",
                    version=declaration.source_schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        assert ref.artifact_id == declaration.source_ref.artifact_id
        copied = owner.produce_grounding_proof_world_input(
            root, world_cas=Path(directory), world_ref=str(ref.artifact_id)
        )
        assert owner.resolve_grounding_proof_world_input(root, copied) == original
        blob, _manifest = store._paths(ref.artifact_id)
        original_bytes = blob.read_bytes()
        altered = json.loads(original_bytes)
        # WMR's logical hash excludes this field; full Core byte identity does not.
        altered["producer_ref"] = "unverified_changed_producer"
        try:
            blob.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")))
            with pytest.raises(ValueError, match="Blob sha256 mismatch"):
                owner.resolve_grounding_proof_world_input(root, copied)
        finally:
            blob.write_bytes(original_bytes)
