from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

from tools.quality.validation import check_universal_corpus_annotations as checker

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_w11b_repo_owned_cases_have_claim_evidence_decomposition_annotations() -> None:
    report = checker.build_report(repo_root=REPO_ROOT)

    assert report["schema_version"] == checker.SCHEMA_VERSION
    assert report["status"] == "pass", report["findings"]
    assert report["summary"]["case_count"] >= 1
    assert report["summary"]["claim_count"] >= 1
    assert report["summary"]["obligation_count"] >= 1
    assert report["summary"]["known_outcome_or_failure_count"] >= 1
    assert report["capability_trace"]["capability_id"] == (
        "w11b_claim_evidence_decomposition_annotations"
    )
    assert report["capability_trace"]["capability_reality_label"] == "implemented"
    assert report["capability_trace"]["missing_capability_labels"] == []
    assert {
        "P01",
        "P02",
        "P03",
        "P05",
        "P10",
        "P13",
        "P14",
        "P15",
    } <= set(report["pattern_pass"]["relevant_patterns"])


def test_w11b_checker_rejects_case_without_claim_decomposition_annotation(
    tmp_path: Path,
) -> None:
    corpus_dir = tmp_path / "outcome-corpus"
    corpus_dir.mkdir()
    (corpus_dir / "structural-only-case.md").write_text(
        """---
case_id: structural-only-case
jurisdiction: Testland
policy_time: "2026"
policy_instrument:
  instrument_type: grant
  delivery_channel: portal
  funding_channel: budget
targeting:
  targeting_type: application_based
  beneficiary_classes: [small_firms]
  affected_populations: [taxpayers]
references:
  - ref_id: text:case:summary
    ref_type: source
    source_ref: repo://tmp/structural-only-case.md#summary
    title: Summary
claims: []
obligations:
  - obligation_id: obligation:data-check
    generated_from_facets: [facet:instrument.grant]
    required_evidence_family: administrative_data
    status: missing
    reviewer_notes: Needs claim-bound evidence.
known_outcomes_or_failures:
  - finding_id: outcome:unknown
    source_ref: text:case:summary
    would_prior_obligation_have_flagged:
annotation_provenance:
  reviewer_role: policy_generalist
  expertise_basis: smoke fixture
  conflicts: []
  reviewed_at: "2026-05-24"
---

# Structural-only case
""",
        encoding="utf-8",
    )

    report = checker.build_report(repo_root=REPO_ROOT, corpus_dir=corpus_dir)

    assert report["status"] == "fail"
    assert report["summary"]["case_count"] == 0
    assert any(finding["code"] == "annotation_invalid" for finding in report["findings"])
