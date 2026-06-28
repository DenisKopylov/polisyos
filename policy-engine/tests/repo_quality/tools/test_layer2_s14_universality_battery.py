from __future__ import annotations

# ruff: noqa: S101
import importlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SEALED_BATTERY_ROOT = (
    REPO_ROOT
    / "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
    "layer2-sealed-universality-battery"
)
S14_SKEPTIC_DEFEATER_IDS = {
    "bespoke_disguise_defeater",
    "confident_theater_defeater",
    "failure_boundary_defeater",
    "single_axis_universality_defeater",
    "frozen_once_defeater",
    "first_call_defeater",
}
S14_REQUIRED_SUBSTRATE_REUSE_REFS = {
    "src/polisyos/runtime/quality/assurance_case.py#build_universality_assurance_case",
    "src/polisyos/runtime/quality/assurance_case.py#build_assurance_case_for_scorecard",
    "src/polisyos/runtime/quality/capability_ratchet.py#build_capability_reality_report",
    "src/polisyos/runtime/quality/design_axes/resource_economics.py#GrowthThermometerRecord",
    "src/polisyos/runtime/quality/design_axes/resource_economics.py#EnvelopeGrowthLedger",
    "src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#EnvelopeRevision",
    "src/polisyos/runtime/quality/design_axes/post_deploy_accountability.py#CertifiedEnvelopeDelta",
    "src/polisyos/runtime/quality/case_lifecycle.py#status_lattice",
    "src/polisyos/runtime/quality/approval.py#closeout_status_composition",
}


def _runner() -> Any:
    return importlib.import_module("tools.quality.validation.run_layer2_s14_universality_battery")


def _run_battery(**overrides: object) -> dict[str, Any]:
    kwargs: dict[str, object] = {
        "repo_root": REPO_ROOT,
        "battery_root": SEALED_BATTERY_ROOT,
        "allow_sealed_battery": True,
    }
    kwargs.update(overrides)
    return dict(_runner().run_layer2_s14_universality_battery(**kwargs))


def test_s14_battery_runner_refuses_sealed_pack_without_allow_flag() -> None:
    result = _run_battery(allow_sealed_battery=False)

    assert result["status"] == "fail"
    assert result["sealed_battery_integrity_status"] == "blocked"
    assert "sealed_battery_access_requires_explicit_allow" in {
        issue["code"] for issue in result["issues"]
    }


def test_s14_battery_runner_verifies_freeze_hash() -> None:
    result = _run_battery()
    partition = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer2_corpus_partition.json")
        .read_text(encoding="utf-8")
    )["sealed_universality_battery"]

    assert result["status"] == "pass"
    assert result["sealed_universality_battery_run"]["partition_path"] == partition["path"]
    assert result["sealed_universality_battery_run"]["owner"] == "governance-board"
    assert result["sealed_universality_battery_run"]["access_mode"] == "ci_gate_only"
    assert result["sealed_universality_battery_run"]["computed_freeze_hash"] == (
        partition["freeze_hash"]
    )
    assert result["sealed_battery_freeze_hash_match"] is True


def test_s14_battery_runner_emits_d4_oracle_breadth_scorecard_skeptic_defeaters_and_summary(
) -> None:
    result = _run_battery()
    summary = result["s14_universality_assurance_summary"]

    assert summary["d4_corpus_track_count"] == 19
    assert summary["expert_oracle_layer_count"] == 4
    assert summary["breadth_floor_status"] == "pass"
    assert summary["axis_scorecard_row_count"] == 27
    assert summary["sealed_battery_case_count"] >= 6
    assert summary["skeptic_defeater_count"] == 6
    assert summary["skeptic_defeater_pass_rate"] == 1.0
    assert {row["defeater_id"] for row in result["skeptic_defeater_records"]} == (
        S14_SKEPTIC_DEFEATER_IDS
    )
    assert len(result["d4_corpus_track_coverage"]["track_rows"]) == 19
    assert len(result["expert_oracle_bootstrap"]["oracle_layers"]) == 4


def test_s14_battery_runner_emits_baseline_grounded_authority_and_status_composition(
) -> None:
    result = _run_battery()

    assert result["universality_baseline_comparison"]["comparison_status"] == "pass"
    assert {
        row["baseline_family"]
        for row in result["universality_baseline_comparison"]["baseline_rows"]
    } == {"bespoke_tool", "raw_llm", "expert_panel"}
    assert result["grounded_authority_coverage"]["coverage_status"] == "pass"
    assert result["grounded_authority_coverage"]["a_firewall_refs"]
    assert result["evaluation_status_composition"]["composition_status"] == "pass"
    status_effects = {
        row["d4_label"]: row["effect"]
        for row in result["evaluation_status_composition"]["status_cases"]
    }
    assert status_effects["weak_gold"] == "seed_only"
    assert status_effects["bespoke_growth_detected"] == "blocks_claim"


def test_s14_battery_runner_emits_required_substrate_reuse_refs() -> None:
    result = _run_battery()

    assert set(result["substrate_reuse_refs"]) >= S14_REQUIRED_SUBSTRATE_REUSE_REFS
    assert result["universality_axis_scorecard"]["capability_reality_report_ref"]
    assert result["mechanism_generality_report"]["growth_thermometer_ref"]
    assert result["envelope_revision_dynamics"]["s12_expansion_evidence_refs"]
    assert result["envelope_revision_dynamics"]["s13_shrink_or_split_refs"]
    assert result["universality_claim_assurance_case"]["cae_defeater_refs"]


def test_s14_battery_runner_reports_claim_disposition_not_capability_gate_status(
) -> None:
    result = _run_battery()
    summary = result["s14_universality_assurance_summary"]
    public_summary = result["public_summary"]
    gate_record = result["universality_claim_gate_record"]

    assert "universal_claim_gate_status" not in summary
    assert "universal_claim_gate_status" not in public_summary
    assert summary["universal_claim_disposition"] == gate_record["disposition"]
    assert public_summary["universal_claim_disposition"] == gate_record["disposition"]
    assert summary["universal_claim_disposition"] in {
        "universal_claim_blocked",
        "universal_claim_limited",
    }
    assert summary["universal_claim_disposition"] != "universal_claim_allowed"


def test_s14_battery_runner_rejects_dev_corpus_as_sealed_result() -> None:
    result = _run_battery(battery_root=REPO_ROOT / "tests/fixtures/universal-corpus")

    assert result["status"] == "fail"
    assert "sealed_battery_path_mismatch" in {issue["code"] for issue in result["issues"]}


def test_s14_battery_runner_redacts_hidden_case_content_from_public_summary() -> None:
    result = _run_battery()
    public_summary = result["public_summary"]
    serialized = json.dumps(public_summary)

    assert "sealed_gold_label_ref" not in serialized
    assert "expected_boundary_disposition" not in serialized
    assert "input_condition_ref" not in serialized
    assert public_summary["sealed_battery_case_count"] >= 6
    assert public_summary["sealed_battery_run_ref"]


def test_s14_battery_runner_reads_g7_manifest_without_mutating_freeze_hash(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "g7_s14_input_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "s14_battery_input_manifest_id": "g7-s14-input:test",
                "grounded_breadth_feed_ref": "layer3-g7://s14/grounded-breadth-feed",
                "mechanism_generality_projection_ref": (
                    "layer3-g7://s14/mechanism-generality-projection"
                ),
                "grounded_authority_coverage_ref": (
                    "layer3-g7://s14/grounded-authority-coverage"
                ),
                "envelope_revision_dynamics_ref": (
                    "layer3-g7://s14/envelope-revision-dynamics"
                ),
                "certified_envelope_delta_refs": [
                    "s13-envelope-delta://ua-msme/expand-region"
                ],
                "visible_limitation_refs": ["limitation://g7/s14/region-only"],
                "sealed_battery_mutation_status": "not_mutated",
                "hidden_case_access_status": "not_accessed_by_g7",
                "may_not_use_for": ["s14_universality", "production_authority"],
            }
        ),
        encoding="utf-8",
    )

    without_manifest = _run_battery()
    with_manifest = _run_battery(g7_grounded_breadth_input_manifest=manifest_path)

    assert with_manifest["sealed_battery_freeze_hash"] == without_manifest[
        "sealed_battery_freeze_hash"
    ]
    assert with_manifest["sealed_battery_computed_freeze_hash"] == without_manifest[
        "sealed_battery_computed_freeze_hash"
    ]
    assert with_manifest["sealed_universality_battery_run"] == without_manifest[
        "sealed_universality_battery_run"
    ]
    hook = with_manifest["external_grounded_breadth_input"]
    assert hook == {
        "status": "present",
        "manifest_ref": str(manifest_path),
        "issue_codes": [],
    }
    assert "external_grounded_breadth_input" not in without_manifest
    assert "sealed_case_rows" not in with_manifest
    assert with_manifest["grounded_authority_coverage"] == without_manifest[
        "grounded_authority_coverage"
    ]
