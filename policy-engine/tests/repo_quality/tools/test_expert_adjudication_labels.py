from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from polisyos.corpus import load_outcome_corpus_annotations
from polisyos.corpus import (
    EXPERT_ADJUDICATION_SCHEMA_VERSION,
    build_expert_adjudication_useful_design_gate,
    evaluate_expert_adjudication_manifest,
)
from tools.quality.validation import check_expert_adjudication_labels as checker

REPO_ROOT = Path(__file__).resolve().parents[3]
ADJUDICATION_ROOT = (
    REPO_ROOT
    / "docs"
    / "research"
    / "universal-policy-design"
    / "outcome-corpus"
    / "adjudications"
)
README_PATH = ADJUDICATION_ROOT / "README.md"


def _read_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.relative_to(REPO_ROOT)} must be a JSON object"
    return payload


def test_w11c_expert_adjudication_artifacts_are_committed_and_valid() -> None:
    assert README_PATH.is_file()
    readme = README_PATH.read_text(encoding="utf-8")
    assert "C30" in readme
    assert "P10" in readme
    assert "reviewer_disagreement" in readme

    manifests = sorted(ADJUDICATION_ROOT.glob("*.json"))
    assert manifests, "W11.C needs repo-owned expert adjudication label manifests"

    seen_labels: set[str] = set()
    seen_topologies: set[str] = set()
    for path in manifests:
        manifest = _read_manifest(path)
        result = evaluate_expert_adjudication_manifest(manifest)

        assert manifest["schema_version"] == EXPERT_ADJUDICATION_SCHEMA_VERSION
        assert manifest["phase_id"] == "W11.C"
        assert result["status"] == "pass", result["issues"]
        assert result["claim_coverage_status"] == "complete"
        assert result["gold_card_count"] == result["rejected_structural_pass_count"]
        assert "C30" in manifest["research_refs"]
        assert "P10" in manifest["pattern_ids"]
        assert path.name in readme
        seen_labels.update(str(label) for label in result["labels"])
        seen_topologies.add(str(result["topology_mode"]))

    assert {
        "semantic_pass",
        "limitation_required",
        "false_pass",
        "reviewer_disagreement",
    } <= seen_labels
    assert {"deep_pilot_overlap", "partial_disjoint"} <= seen_topologies


def test_w11c_expert_adjudication_covers_every_outcome_corpus_case_and_claim() -> None:
    corpus_root = REPO_ROOT / "docs/research/universal-policy-design/outcome-corpus"
    annotations = load_outcome_corpus_annotations(corpus_root)
    manifests_by_case: dict[str, dict[str, object]] = {}
    for path in sorted(ADJUDICATION_ROOT.glob("*.json")):
        manifest = _read_manifest(path)
        result = evaluate_expert_adjudication_manifest(manifest)
        if result["status"] == "pass":
            manifests_by_case[str(manifest["case_id"])] = manifest

    missing_case_ids = sorted(
        annotation.case_id
        for annotation in annotations
        if annotation.case_id not in manifests_by_case
    )
    assert missing_case_ids == []

    for annotation in annotations:
        manifest = manifests_by_case[annotation.case_id]
        assert annotation.expert_adjudication_status == "adjudicated_w11c"
        assert set(manifest["expected_claim_ids"]) == {
            claim.claim_id for claim in annotation.claims
        }


def test_w11c_missing_adjudication_cannot_enter_useful_design_metric() -> None:
    gate = build_expert_adjudication_useful_design_gate(
        case_id="structurally-complete-without-label",
        structural_complete=True,
        adjudication_result=None,
    )

    assert gate["status"] == "blocked"
    assert gate["counts_toward_useful_design"] is False
    assert gate["blocker_code"] == "expert_adjudication_missing"


def test_w11c_cli_reports_label_and_topology_coverage(tmp_path: Path) -> None:
    output_path = tmp_path / "w11c-adjudication-validation.json"

    exit_code = checker.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--json-output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "pass", payload["issues"]
    assert payload["manifest_count"] >= 2
    assert payload["topology_modes"]["deep_pilot_overlap"] >= 1
    assert payload["topology_modes"]["partial_disjoint"] >= 1
    assert payload["label_counts"]["reviewer_disagreement"] >= 1
    assert payload["useful_design_gate"]["missing_adjudication_blocks"] is True
