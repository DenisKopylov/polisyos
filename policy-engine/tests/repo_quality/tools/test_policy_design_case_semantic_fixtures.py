# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.semantic_fixtures import (
    SEMANTIC_GOLD_CARD_SCHEMA_VERSION,
    evaluate_semantic_gold_card_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "policy_design_case" / "semantic_false_passes"
README_PATH = FIXTURE_ROOT / "README.md"

REQUIRED_FIXTURES = {
    "projection_laundering_semantic_fail.json": "projection_laundering",
    "participation_laundering_semantic_fail.json": "participation_laundering",
    "raw_count_inflation_semantic_fail.json": "raw_count_inflation",
    "method_mismatch_semantic_fail.json": "method_mismatch",
    "stale_evidence_semantic_fail.json": "stale_evidence",
    "llm_speculation_semantic_fail.json": "llm_speculation",
    "unsupported_claim_semantic_fail.json": "unsupported_claim",
}


def _read_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.relative_to(REPO_ROOT)} must be a JSON object"
    return payload


def test_w1b_semantic_false_pass_gold_cards_are_frozen() -> None:
    assert README_PATH.is_file()
    readme = README_PATH.read_text(encoding="utf-8")
    assert "P10" in readme
    assert "P15" in readme

    fixture_paths = sorted(FIXTURE_ROOT.glob("*.json"))
    assert {path.name for path in fixture_paths} >= set(REQUIRED_FIXTURES)

    seen_failure_modes: set[str] = set()
    seen_pattern_ids: set[str] = set()
    for path in fixture_paths:
        fixture = _read_fixture(path)
        result = evaluate_semantic_gold_card_fixture(fixture)
        expected_mode = REQUIRED_FIXTURES[path.name]
        seen_failure_modes.add(str(fixture["failure_mode"]))
        seen_pattern_ids.update(str(pattern_id) for pattern_id in fixture["pattern_ids"])

        assert fixture["schema_version"] == SEMANTIC_GOLD_CARD_SCHEMA_VERSION
        assert fixture["fixture_id"] == path.stem
        assert fixture["expected_status"] == "semantic_fail"
        assert fixture["failure_mode"] == expected_mode
        assert fixture["structural_pass_claimed"] is True
        assert fixture["structural_verdict"]["status"] == "pass"
        assert "P10" in fixture["pattern_ids"]
        assert fixture["semantic_probes"]
        assert result["fixture_status"] == "valid", result["issues"]
        assert result["structural_status"] == "pass"
        assert result["semantic_status"] == "fail"
        assert result["expected_failure_code"] in result["detected_failure_codes"]
        assert fixture["fixture_id"] in readme
        assert expected_mode in readme

    assert seen_failure_modes == set(REQUIRED_FIXTURES.values())
    assert {"P10", "P15"} <= seen_pattern_ids
