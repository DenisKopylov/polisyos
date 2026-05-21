from __future__ import annotations

import json
from pathlib import Path

from tools.ops_runners.runtime import replay_canary_bundle

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    REPO_ROOT
    / "tests/fixtures/production_quality/cloud_debug_20260520/root_cause_summary.json"
)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_cloud_prod_debug_fixture_preserves_root_causes() -> None:
    fixture_json = _load_fixture()

    assert fixture_json["expected_source_families"] == [
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    ]
    assert "datasets" in fixture_json["selected_source_families"]
    assert fixture_json["lex_candidate_norm_count"] == 0
    assert fixture_json["direct_lex_probe"]["підприєм"] > 0
    assert fixture_json["semantic_binding_error"] == "runtime_report_status.extra_forbidden"
    assert "hds_unknown_provenance" in fixture_json["scorecard_codes"]


def test_cloud_prod_debug_fixture_keeps_all_shared_failure_axes() -> None:
    fixture_json = _load_fixture()

    assert fixture_json["blocking_quality_failure_count"] == 32
    assert fixture_json["hds_unknown_provenance_count"] == 10
    assert fixture_json["lex_retrieval_status"] == "no_relevant_norm_found"
    assert fixture_json["semantic_binding_runtime_report_status"] == "blocked"
    assert fixture_json["policy_design_case_status"] == "pass"
    assert {"selected_source_family_not_admissible", "semantic_binding_ledger_invalid"} <= set(
        fixture_json["scorecard_codes"]
    )
    assert {
        "source_rights",
        "dictionary_ref",
        "schema_ref",
        "field_refs",
        "lineage_refs",
        "derived_feature_bindings",
    } <= set(fixture_json["selected_source_missing_facets"])
    assert {
        "policy_design_substrate_residual_verification_record_missing",
        "policy_design_pass1b_hardening_record_missing",
    } <= set(fixture_json["policy_design_case_missing_record_family_codes"])


def test_replay_canary_bundle_root_cause_fixture_mode_preserves_failure_envelope(
    tmp_path: Path,
) -> None:
    output = tmp_path / "root_cause_replay.json"

    exit_code = replay_canary_bundle.main(
        [
            "--root-cause-fixture",
            str(FIXTURE_PATH),
            "--json-output",
            str(output),
        ]
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert result["schema_version"] == "policyos.replay_canary_bundle.v1"
    assert result["status"] == "root_cause_fixture"
    assert result["production_readiness"] == "fail"
    assert result["failure_envelope"]["code"] == "cloud_prod_debug_root_causes_preserved"
    assert result["failure_envelope"]["readiness_state"] == "not_ready"
    assert result["summary"]["scorecard_failure_count"] == 32
    assert result["summary"]["hds_unknown_provenance_count"] == 10
    assert "hds_unknown_provenance" in result["root_cause_summary"]["scorecard_codes"]
