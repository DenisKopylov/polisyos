from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

import build_academic_gold_candidates as candidate_scripts  # noqa: E402
import build_expert_review_bundle as bundle_scripts  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _snapshot_root(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    (root / "academic").mkdir(parents=True, exist_ok=True)
    return root


def _selected_work_row(work_id: str) -> dict:
    return {
        "work_id": work_id,
        "work": {
            "id": work_id,
            "title": "Paper Title",
            "abstract_inverted_index": {
                "Tax": [0],
                "audits": [1],
                "increase": [2],
                "compliance.": [3],
            },
        },
        "topic_ids": ["T1"],
        "topic_display_names": ["Topic 1"],
        "run_ids": ["run-1"],
    }


def test_candidate_pool_uses_real_abstract(tmp_path: Path) -> None:
    snapshot_root = _snapshot_root(tmp_path)
    _write_jsonl(
        snapshot_root / "academic" / "topic_selection" / "selected_global_works.jsonl",
        [_selected_work_row("https://openalex.org/W1")],
    )
    _write_jsonl(
        snapshot_root / "academic" / "article_extraction_results.jsonl",
        [
            {
                "openalex_id": "https://openalex.org/W1",
                "title": "Paper Title",
                "citation_summary": "",
                "source_basis": "fulltext",
                "causal_claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Tax audits increase compliance.",
                        "cause_variable": "tax_audits",
                        "effect_variable": "compliance",
                        "direction": "positive",
                        "supporting_spans": [
                            {"text": "Tax audits increase compliance.", "section": "abstract"}
                        ],
                        "design_family_hint": "rct",
                    }
                ],
            }
        ],
    )

    out_dir = snapshot_root / "academic" / "gold_candidates"
    screen_path, claim_path = candidate_scripts.build_candidate_pools(snapshot_root, out_dir)
    screen_row = candidate_scripts.load_jsonl(screen_path)[0]
    claim_row = candidate_scripts.load_jsonl(claim_path)[0]

    assert screen_row["abstract"] == "Tax audits increase compliance."
    assert claim_row["paper_abstract"] == "Tax audits increase compliance."


def test_bundle_validation_recovers_legacy_claim_grounding(tmp_path: Path) -> None:
    snapshot_root = _snapshot_root(tmp_path)
    _write_jsonl(
        snapshot_root / "academic" / "topic_selection" / "selected_global_works.jsonl",
        [_selected_work_row("https://openalex.org/W2")],
    )
    _write_jsonl(
        snapshot_root / "academic" / "article_extraction_results.jsonl",
        [
            {
                "openalex_id": "https://openalex.org/W2",
                "title": "Paper Title",
                "citation_summary": "fallback summary",
                "source_basis": "abstract_only",
                "causal_claims": [
                    {
                        "claim_id": "c2",
                        "claim_text": "",
                        "cause_variable": "tax_audits",
                        "effect_variable": "compliance",
                        "direction": "positive",
                        "supporting_spans": [],
                        "design_family_hint": "",
                    }
                ],
            }
        ],
    )

    out_dir = snapshot_root / "academic" / "gold_candidates"
    bundle_path = out_dir / "expert_review_bundle.json"
    validation_path = out_dir / "expert_review_bundle_validation.json"

    bundle_scripts.build_bundle(
        snapshot_root,
        out_dir,
        bundle_path,
        REPO_ROOT / "data" / "academic_gold" / "guidelines.md",
        validation_path,
        source_basis_filter=None,
        min_claim_text_coverage_pct=100.0,
        min_supporting_span_coverage_pct=85.0,
        min_source_basis_coverage_pct=100.0,
        min_design_family_hint_coverage_pct=100.0,
        max_abstract_only_share_pct=None,
        fail_on_validation=True,
    )

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    claim_item = bundle["tasks"]["claim_gold"]["items"][0]
    assert claim_item["claim_text"] == "Tax audits increase compliance."
    assert claim_item["supporting_spans"][0]["text"] == "Tax audits increase compliance."
    assert claim_item["source_basis"] == "abstract_only"
    assert claim_item["design_family_hint"] == "unclear"
    assert validation["claims_without_claim_text"] == 0
    assert validation["claims_without_supporting_spans"] == 0
    assert validation["abstract_only_claims"] == 1
    assert validation["claims_without_source_basis"] == 0
    assert validation["claims_without_design_family_hint"] == 0
    assert validation["ready_for_expert_review"] is True


def test_bundle_validation_fails_when_no_real_text_exists(tmp_path: Path) -> None:
    snapshot_root = _snapshot_root(tmp_path)
    _write_jsonl(
        snapshot_root / "academic" / "topic_selection" / "selected_global_works.jsonl",
        [
            {
                "work_id": "https://openalex.org/W3",
                "work": {
                    "id": "https://openalex.org/W3",
                    "title": "",
                    "abstract_inverted_index": {},
                },
                "topic_ids": ["T1"],
                "topic_display_names": ["Topic 1"],
                "run_ids": ["run-1"],
            }
        ],
    )
    _write_jsonl(
        snapshot_root / "academic" / "article_extraction_results.jsonl",
        [
            {
                "openalex_id": "https://openalex.org/W3",
                "title": "",
                "citation_summary": "",
                "source_basis": "abstract_only",
                "causal_claims": [
                    {
                        "claim_id": "c3",
                        "claim_text": "",
                        "cause_variable": "tax_audits",
                        "effect_variable": "compliance",
                        "direction": "positive",
                        "supporting_spans": [],
                        "design_family_hint": "",
                    }
                ],
            }
        ],
    )

    out_dir = snapshot_root / "academic" / "gold_candidates"
    bundle_path = out_dir / "expert_review_bundle.json"
    validation_path = out_dir / "expert_review_bundle_validation.json"

    with pytest.raises(SystemExit) as excinfo:
        bundle_scripts.build_bundle(
            snapshot_root,
            out_dir,
            bundle_path,
            REPO_ROOT / "data" / "academic_gold" / "guidelines.md",
            validation_path,
            source_basis_filter=None,
            min_claim_text_coverage_pct=100.0,
            min_supporting_span_coverage_pct=85.0,
            min_source_basis_coverage_pct=100.0,
            min_design_family_hint_coverage_pct=100.0,
            max_abstract_only_share_pct=None,
            fail_on_validation=True,
        )

    assert excinfo.value.code == 2
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    assert validation["claims_without_supporting_spans"] == 1
    assert validation["ready_for_expert_review"] is False


def test_bundle_source_basis_filter_splits_claims(tmp_path: Path) -> None:
    snapshot_root = _snapshot_root(tmp_path)
    _write_jsonl(
        snapshot_root / "academic" / "topic_selection" / "selected_global_works.jsonl",
        [
            _selected_work_row("https://openalex.org/W10"),
            _selected_work_row("https://openalex.org/W11"),
        ],
    )
    _write_jsonl(
        snapshot_root / "academic" / "article_extraction_results.jsonl",
        [
            {
                "openalex_id": "https://openalex.org/W10",
                "title": "Paper A",
                "citation_summary": "",
                "source_basis": "fulltext",
                "causal_claims": [
                    {
                        "claim_id": "c10",
                        "claim_text": "Tax audits increase compliance.",
                        "cause_variable": "tax_audits",
                        "effect_variable": "compliance",
                        "direction": "positive",
                        "supporting_spans": [
                            {"text": "Tax audits increase compliance.", "section": "abstract"}
                        ],
                        "design_family_hint": "rct",
                        "source_basis": "fulltext",
                    }
                ],
            },
            {
                "openalex_id": "https://openalex.org/W11",
                "title": "Paper B",
                "citation_summary": "",
                "source_basis": "abstract_only",
                "causal_claims": [
                    {
                        "claim_id": "c11",
                        "claim_text": "Taxes affect growth.",
                        "cause_variable": "taxes",
                        "effect_variable": "growth",
                        "direction": "mixed",
                        "supporting_spans": [
                            {"text": "Taxes affect growth.", "section": "abstract"}
                        ],
                        "design_family_hint": "unclear",
                        "source_basis": "abstract_only",
                    }
                ],
            },
        ],
    )

    out_dir = snapshot_root / "academic" / "gold_candidates"

    fulltext_bundle = out_dir / "fulltext_bundle.json"
    fulltext_validation = out_dir / "fulltext_validation.json"
    bundle_scripts.build_bundle(
        snapshot_root,
        out_dir,
        fulltext_bundle,
        REPO_ROOT / "data" / "academic_gold" / "guidelines.md",
        fulltext_validation,
        source_basis_filter="fulltext",
        min_claim_text_coverage_pct=100.0,
        min_supporting_span_coverage_pct=85.0,
        min_source_basis_coverage_pct=100.0,
        min_design_family_hint_coverage_pct=100.0,
        max_abstract_only_share_pct=None,
        fail_on_validation=True,
    )

    abstract_bundle = out_dir / "abstract_bundle.json"
    abstract_validation = out_dir / "abstract_validation.json"
    bundle_scripts.build_bundle(
        snapshot_root,
        out_dir,
        abstract_bundle,
        REPO_ROOT / "data" / "academic_gold" / "guidelines.md",
        abstract_validation,
        source_basis_filter="abstract_only",
        min_claim_text_coverage_pct=100.0,
        min_supporting_span_coverage_pct=85.0,
        min_source_basis_coverage_pct=100.0,
        min_design_family_hint_coverage_pct=100.0,
        max_abstract_only_share_pct=None,
        fail_on_validation=True,
    )

    fulltext_obj = json.loads(fulltext_bundle.read_text(encoding="utf-8"))
    abstract_obj = json.loads(abstract_bundle.read_text(encoding="utf-8"))
    assert fulltext_obj["tasks"]["claim_gold"]["count"] == 1
    assert abstract_obj["tasks"]["claim_gold"]["count"] == 1
    assert fulltext_obj["tasks"]["claim_gold"]["items"][0]["source_basis"] == "fulltext"
    assert abstract_obj["tasks"]["claim_gold"]["items"][0]["source_basis"] == "abstract_only"
