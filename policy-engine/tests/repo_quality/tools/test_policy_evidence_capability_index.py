from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import build_policy_evidence_capability_index as builder

REPO_ROOT = Path(__file__).resolve().parents[3]
PHASE1_PROFILE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/capability_index_phase1_artifact_profile.json"
)
CAPABILITY_REALITY_REPORT_PATH = (
    REPO_ROOT / "architecture/policy_design_case/capability_reality_report.json"
)
FULL_MODE_CAPABILITY_FLOORS = {
    "fabric_data": 1,
    "lex_norm": 1,
    "scholar_claim": 1,
    "foundry_method_contract": 1,
    "compatibility_only": 1,
}


def test_fixture_cli_emits_all_capability_index_outputs(tmp_path: Path) -> None:
    output_dir = tmp_path / "capability-index"
    exit_code = builder.main(["--mode", "fixture", "--output-dir", str(output_dir)])

    assert exit_code == 0
    for filename in (
        "capability_index_v1.duckdb",
        "capability_index_v1.manifest.json",
        "capability_index_v1.sha256",
        "capability_index_v1.summary.json",
        "capability_index_v1.dcat.jsonld",
        "capability_index_v1.prov.ttl",
        "capability_white_space_report_v1.json",
        "capability_conflict_report_v1.json",
    ):
        assert (output_dir / filename).exists(), filename

    summary = json.loads((output_dir / "capability_index_v1.summary.json").read_text())
    assert summary["primary_runtime_output"] == "capability_index_v1.duckdb"
    assert summary["exports_are_summary_only"] is True
    assert summary["duckdb_table_row_counts"]["capabilities"] >= 1
    assert summary["performance_budget"]["status"] == "pass"
    assert (output_dir / "capability_conflict_report_v1.json").read_text()


def test_fixture_cli_determinism_matches_phase_verification_cmp(tmp_path: Path) -> None:
    output_a = tmp_path / "fixture-a"
    output_b = tmp_path / "fixture-b"

    assert builder.main(["--mode", "fixture", "--output-dir", str(output_a)]) == 0
    assert builder.main(["--mode", "fixture", "--output-dir", str(output_b)]) == 0

    assert (output_a / "capability_index_v1.sha256").read_text() == (
        output_b / "capability_index_v1.sha256"
    ).read_text()
    assert _manifest_without_generated_at(output_a) == _manifest_without_generated_at(output_b)

    assert builder.main(["--mode", "fixture", "--output-dir", str(output_a)]) == 0
    assert builder.main(["--mode", "fixture", "--output-dir", str(output_b)]) == 0
    assert _manifest_without_generated_at(output_a) == _manifest_without_generated_at(output_b)


def test_incremental_mode_reports_unchanged_inputs_and_reuses_previous_index(
    tmp_path: Path,
) -> None:
    output_a = tmp_path / "fixture-a"
    output_b = tmp_path / "fixture-b"

    assert builder.main(["--mode", "fixture", "--output-dir", str(output_a)]) == 0
    assert (
        builder.main(
            [
                "--mode",
                "incremental",
                "--production-data-root",
                str(output_a / "_fixture_inputs"),
                "--previous-manifest",
                str(output_a / "capability_index_v1.manifest.json"),
                "--output-dir",
                str(output_b),
            ]
        )
        == 0
    )

    summary = json.loads((output_b / "capability_index_v1.summary.json").read_text())
    assert summary["incremental"]["changed_input_count"] == 0
    assert summary["incremental"]["reused_previous_index"] is True
    assert summary["performance_budget"]["status"] == "pass"


def test_full_mode_floors_and_artifact_profile_are_committed() -> None:
    profile = json.loads(PHASE1_PROFILE_PATH.read_text())

    assert profile["schema_version"] == "policyos.capability_index.phase1_artifact_profile.v1"
    assert profile["full_mode_capability_floors"] == FULL_MODE_CAPABILITY_FLOORS
    assert profile["duckdb_table_row_counts"]["capabilities"] >= sum(
        FULL_MODE_CAPABILITY_FLOORS.values()
    )
    assert "capability_index_v1.duckdb" in profile["artifact_size_profile"]
    assert profile["performance_budget"]["full"]["budget_seconds"] == 600
    assert profile["performance_budget"]["incremental"]["budget_seconds"] == 120


def test_capability_reality_report_marks_compiler_implemented_after_phase7() -> None:
    report = json.loads(CAPABILITY_REALITY_REPORT_PATH.read_text())
    claims = {claim["capability_id"]: claim for claim in report["capability_claims"]}

    assert claims["capability_index_compiler"]["reality_state"] == "implemented"
    assert claims["capability_index_compiler"]["graduation_allowed"] is True
    assert claims["capability_index_compiler"]["evidence_refs"]["producer_ref"] == (
        "repo://tools/quality/validation/build_policy_evidence_capability_index.py"
    )
    assert claims["policy_evidence_capability_graph"]["reality_state"] == "implemented"
    assert claims["legacy_scenario_family_authority"]["reality_state"] == (
        "surface_out_of_scope"
    )


def _manifest_without_generated_at(output_dir: Path) -> dict[str, object]:
    payload = json.loads((output_dir / "capability_index_v1.manifest.json").read_text())
    payload.pop("generated_at", None)
    return payload
