# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.semantic_fixtures import (
    SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION,
    evaluate_semantic_evaluation_pack,
)
from tools.quality.validation import check_policy_design_case_capability_ratchet as ratchet

REPO_ROOT = Path(__file__).resolve().parents[3]
PACK_ROOT = REPO_ROOT / "tests/fixtures/policy_design_case/semantic_evaluation_packs"
MANIFEST_PATH = PACK_ROOT / "w5b_false_pass_pack_manifest.json"
README_PATH = PACK_ROOT / "README.md"

REQUIRED_SPLITS = {"public", "hidden", "rotating"}
REQUIRED_FAILURE_MODES = {
    "participation_prevalence_negative",
    "projection_laundering",
    "unreachable_recourse_pointer",
    "tuned_threshold_hardcoding",
    "raw_count_inflation",
    "llm_speculation",
    "unsupported_claim",
}
REQUIRED_PATTERN_IDS = {"P10", "P14", "P15"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict), f"{path.relative_to(REPO_ROOT)} must be a JSON object"
    return payload


def _repo_path(ref: str) -> Path:
    assert ref.startswith("repo://"), ref
    return REPO_ROOT / ref.removeprefix("repo://").split("#", maxsplit=1)[0]


def test_w5b_semantic_evaluation_pack_manifest_is_reproducible_and_split_aware() -> None:
    manifest = _read_json(MANIFEST_PATH)
    fixture_payloads = {
        fixture["fixture_ref"]: _read_json(_repo_path(fixture["fixture_ref"]))
        for split in manifest["splits"]
        for fixture in split["fixtures"]
    }

    result = evaluate_semantic_evaluation_pack(manifest, fixture_payloads)

    assert manifest["schema_version"] == SEMANTIC_EVALUATION_PACK_SCHEMA_VERSION
    assert manifest["phase_id"] == "W5.B"
    assert {"E22", "C30"} <= set(manifest["research_refs"])
    assert set(manifest["pattern_ids"]) >= REQUIRED_PATTERN_IDS
    assert {split["split"] for split in manifest["splits"]} == REQUIRED_SPLITS
    assert set(manifest["required_failure_modes"]) >= REQUIRED_FAILURE_MODES
    assert result["status"] == "pass", result["issues"]
    assert result["split_summary"]["public"] >= 1
    assert result["split_summary"]["hidden"] >= 1
    assert result["split_summary"]["rotating"] >= 1
    assert set(result["detected_failure_modes"]) >= REQUIRED_FAILURE_MODES
    assert set(result["detected_pattern_ids"]) >= REQUIRED_PATTERN_IDS
    _assert_repo_refs_resolve(manifest)


def test_w5b_hidden_and_rotating_fixtures_are_not_public_detail_surfaces() -> None:
    manifest = _read_json(MANIFEST_PATH)
    readme = README_PATH.read_text(encoding="utf-8")

    assert "public/hidden/rotating" in readme
    assert "P10" in readme
    assert "P14" in readme
    assert "P15" in readme
    assert "aggregate-only" in readme

    for split in manifest["splits"]:
        if split["split"] == "public":
            continue
        assert split["public_export_visibility"] == "aggregate_only"
        for fixture in split["fixtures"]:
            assert fixture["fixture_id"] not in readme


def test_w5b_pack_is_registered_as_closed_capability_chain() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    claim = claims["w5b_semantic_evaluation_packs"]

    assert claim["reality_state"] == "implemented"
    assert claim["graduation_allowed"] is True
    assert claim["release_blocker"] is False
    assert claim["traceability"]["research_refs"] == [
        "E22",
        "C30",
        "P10",
        "P14",
        "P15",
    ]
    assert claim["traceability"]["reuse_classification"] == "extend_existing"
    assert {
        "typed_contract_ref",
        "producer_ref",
        "artifact_ref",
        "bridge_ref",
        "consumer_ref",
        "verification_ref",
        "surface_ref",
        "semantic_test_ref",
    } <= set(claim["evidence_refs"])


def _assert_repo_refs_resolve(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_repo_refs_resolve(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_repo_refs_resolve(item, f"{path}[{index}]")
        return
    if isinstance(value, str) and value.startswith("repo://"):
        assert (
            ratchet.validate_repo_reference(
                value,
                repo_root=REPO_ROOT,
                path=path,
            )
            is None
        )
