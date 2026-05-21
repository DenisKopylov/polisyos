from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AUTHORITY_MODULE_PATH = (
    REPO_ROOT / "tools" / "ops_runners" / "runtime" / "quality_benchmark_authority.py"
)
REQUIRED_PACK_KINDS = {"public", "regression", "adversarial", "hidden", "rotating"}
PUBLIC_SURFACES = ("public_export", "reusable_memory", "dashboard_fixture")


def _authority_module():
    if not AUTHORITY_MODULE_PATH.is_file():
        pytest.fail("Phase 3.1 requires tools/ops_runners/runtime/quality_benchmark_authority.py")
    return importlib.import_module("tools.ops_runners.runtime.quality_benchmark_authority")


def test_catalog_declares_authority_packs_with_evidence_thresholds() -> None:
    authority = _authority_module()

    catalog = authority.load_quality_benchmark_catalog()
    packs = catalog["scenario_packs"]
    scenarios = catalog["scenarios"]

    assert {pack["pack_kind"] for pack in packs} == REQUIRED_PACK_KINDS
    assert {pack["pack_id"] for pack in packs}
    assert authority.validate_quality_benchmark_catalog(catalog) == []

    scenario_ids = {scenario["scenario_id"] for scenario in scenarios}
    assigned_ids = [
        scenario_id for pack in packs for scenario_id in pack["scenario_ids"]
    ]
    assert set(assigned_ids) == scenario_ids
    assert len(assigned_ids) == len(scenario_ids)

    for pack in packs:
        evidence = pack["expected_evidence_contract"]
        thresholds = pack["pass_fail_thresholds"]
        assert set(evidence) >= set(authority.REQUIRED_EVIDENCE_CONTRACT_FIELDS)
        assert thresholds["min_contract_coverage"] > 0
        assert thresholds["min_admissible_source_hits"] >= 1
        assert thresholds["max_unacceptable_recommendations"] == 0


def test_public_export_includes_only_inspectable_public_scenarios() -> None:
    authority = _authority_module()

    export = authority.export_public_scenario_pack()
    rendered = json.dumps(export, sort_keys=True)
    public_scenarios = export["scenarios"]
    quarantined_ids = set(authority.quarantined_scenario_ids())

    assert export["pack_kind"] == "public"
    assert public_scenarios
    assert all(scenario["pack_kind"] == "public" for scenario in public_scenarios)
    assert not any(scenario["scenario_id"] in quarantined_ids for scenario in public_scenarios)
    assert "hidden_answer" not in rendered
    assert "sentinel_strings" not in rendered
    assert export["quarantined_pack_counts"]["hidden"] >= 1
    assert export["quarantined_pack_counts"]["rotating"] >= 1
    assert not any(scenario_id in rendered for scenario_id in quarantined_ids)

    authority.assert_no_benchmark_contamination(export, surface="public_export")


def test_hidden_and_rotating_packs_require_explicit_quarantine_access() -> None:
    authority = _authority_module()

    with pytest.raises(authority.QuarantinedScenarioAccessError, match="hidden"):
        authority.load_scenario_pack("hidden_holdout")

    with pytest.raises(authority.QuarantinedScenarioAccessError, match="rotating"):
        authority.load_scenario_pack("rotating_challenge")

    hidden_pack = authority.load_scenario_pack(
        "hidden_holdout",
        include_quarantined=True,
    )
    rotating_pack = authority.load_scenario_pack(
        "rotating_challenge",
        include_quarantined=True,
    )

    assert hidden_pack["quarantine"]["reason"]
    assert rotating_pack["quarantine"]["rotation_policy"]
    assert any("hidden_answer" in scenario for scenario in hidden_pack["scenarios"])
    assert any("sentinel_strings" in scenario for scenario in rotating_pack["scenarios"])


def test_contamination_guard_blocks_hidden_answers_and_sentinels_on_public_surfaces() -> None:
    authority = _authority_module()

    policy = authority.contamination_policy_from_catalog()
    hidden_answer = next(iter(policy.hidden_answers))
    sentinel_string = next(iter(policy.sentinel_strings))

    for surface in PUBLIC_SURFACES:
        with pytest.raises(authority.BenchmarkContaminationError) as exc_info:
            authority.assert_no_benchmark_contamination(
                {
                    "surface": surface,
                    "answer": hidden_answer,
                    "canary": sentinel_string,
                },
                surface=surface,
            )

        assert surface in str(exc_info.value)
        token_kinds = {finding["token_kind"] for finding in exc_info.value.findings}
        assert {"hidden_answer", "sentinel_string"}.issubset(token_kinds)


def test_public_export_guard_fails_if_quarantined_answer_is_injected() -> None:
    authority = _authority_module()

    public_export = authority.export_public_scenario_pack()
    hidden_answer = next(iter(authority.contamination_policy_from_catalog().hidden_answers))
    public_export["scenarios"].append(
        {
            "scenario_id": "leaky_fixture",
            "pack_kind": "public",
            "answer_key": hidden_answer,
        }
    )

    with pytest.raises(authority.BenchmarkContaminationError, match="public_export"):
        authority.assert_no_benchmark_contamination(public_export, surface="public_export")
