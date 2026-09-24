"""Independent source census and runtime-removal falsifiers for VC1."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from polisyos.runtime.quality import vocabulary_crosswalk as runtime
from tools.quality.validation import check_canonical_vocabulary_crosswalk as checker

ROOT = Path(__file__).resolve().parents[3]


def test_reference_is_total_and_recomputed_from_all_declared_owners() -> None:
    assert checker.validate(ROOT) == []
    vocabularies = checker.source_vocabularies(ROOT)
    artifact = checker.read_reference(ROOT)
    assert sum(len(item["terms"]) for item in vocabularies) == artifact["row_count"]


def test_missing_extra_and_corrupt_semantic_rows_fail() -> None:
    original = checker.read_reference(ROOT)
    missing = deepcopy(original)
    missing["entries"].pop()
    assert "reference_drift" in checker.validate(ROOT, artifact=missing)
    extra = deepcopy(original)
    extra["entries"].append({**extra["entries"][0], "source_term": "invented"})
    assert "reference_drift" in checker.validate(ROOT, artifact=extra)
    corrupt = deepcopy(original)
    corrupt["entries"][0]["losses"]["source_identity"] = "tolerable"
    assert "reference_drift" in checker.validate(ROOT, artifact=corrupt)


def test_removing_anti_fork_property_keep_markers_is_detected(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "validate_movement_registry", lambda _: None)
    assert "movement_fork_admitted" in checker.runtime_probe_failures()


def test_removing_loss_refusal_keep_marker_contract_is_detected(monkeypatch) -> None:
    actual = runtime.project_term

    def without_property(entry, *, current_status, losses=()):
        return actual(entry, current_status=current_status, losses=())

    monkeypatch.setattr(runtime, "project_term", without_property)
    assert any(
        code.startswith("blocking_loss_admitted:") for code in checker.runtime_probe_failures()
    )


def test_changed_source_denominator_and_unreadable_source_are_not_zero(tmp_path) -> None:
    docs = checker.source_vocabularies(ROOT)
    assert docs
    errors = checker.validate(tmp_path)
    assert any(error.startswith("source_unreadable:") for error in errors)


def test_institutional_reconciliation_preserves_candidate_and_unallocated_boundaries() -> None:
    artifact = checker.read_reference(ROOT)
    obligations = artifact["ceiling_vocabulary_rulings"]
    assert set(obligations) == {
        "relation_claim_strength",
        "capacity_stages",
        "estimand_binding_strength",
        "legal_normative_write_operations",
        "assurance_levels",
    }
    for key in (
        "estimand_binding_strength",
        "legal_normative_write_operations",
        "assurance_levels",
    ):
        assert obligations[key]["registered_terms"] == []
        assert obligations[key]["semantic_owner"] is None
        assert obligations[key]["owner_must_supply"]
    assert (
        artifact["institutional_family_reconciliation"]["CoAuthentic"]["equivalence_claimed"]
        is False
    )


def test_actual_production_caller_refuses_a_second_namespace_and_removal_is_red(
    monkeypatch,
) -> None:
    from polisyos.runtime.quality import constrained_response as consumer

    assert checker.production_probe_failures() == []
    monkeypatch.setattr(
        consumer,
        "require_canonical_movement",
        lambda *args: runtime.MovementClass.EXPECTED_VARIATION,
    )
    assert "production_namespace_fork_admitted" in checker.production_probe_failures()


def test_independent_source_parser_keeps_digit_bearing_lifecycle_members() -> None:
    primary = {v["vocabulary_id"]: set(v["terms"]) for v in checker.source_vocabularies(ROOT)}
    independent = checker.independently_tokenized_sources(ROOT)
    assert primary == independent
    assert {"PAO_R4_required", "PAO_R4_received"} <= independent["int-r5.lifecycle@0.1.0-candidate"]


def test_qualified_reason_identity_keeps_digits_and_complete_namespace() -> None:
    primary = {v["vocabulary_id"]: set(v["terms"]) for v in checker.source_vocabularies(ROOT)}
    expected = "polisyos.int_r5.reason.pao_r4_receipt_missing@0.1.0-candidate"
    assert expected in primary["int-r5.reason@0.1.0-candidate"]
    assert (
        expected in checker.independently_tokenized_sources(ROOT)["int-r5.reason@0.1.0-candidate"]
    )
