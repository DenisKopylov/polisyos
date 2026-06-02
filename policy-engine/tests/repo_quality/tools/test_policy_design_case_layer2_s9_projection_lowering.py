from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
import polisyos.runtime.quality.projection_semantics as projection_semantics
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S9_MANIFEST = REPO_ROOT / "architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json"
S9_MANIFEST_PATH = "architecture/policy_design_case/layer2_s9_projection_lowering_manifest.json"
PDC_DESIGN_SEARCH = REPO_ROOT / "src/polisyos/pdc/_impl/layer2_design_search.py"
S9_REQUIRED_ARTIFACTS = {
    "CanonicalDesignRecord",
    "ProjectionAlgebraRequest",
    "ProjectionRenderRecord",
    "ProjectionFaithfulnessRecord",
    "LoweringRequestRecord",
    "LoweringAuthorityGateRecord",
    "LoweringArtifactRecord",
    "LoweringAppendReceipt",
    "DesignRecordMaturityReport",
    "ProjectionLoweringIntegrityReport",
}
S9_FALSE_CLEAR_FIELDS = {
    "public_limitation_omission_false_clear_count": "public_limitation_omission",
    "added_prose_claim_false_clear_count": "added_prose_claim",
    "tradeoff_inversion_false_clear_count": "tradeoff_inversion",
    "shadow_candidate_approval_false_clear_count": "shadow_candidate_approval",
    "legal_lowering_without_grounding_false_clear_count": "legal_lowering_without_grounding",
    "projection_authority_laundering_false_clear_count": "projection_authority_laundering",
    "redaction_hides_blocker_false_clear_count": "redaction_hides_blocker",
    "post_closeout_lowering_without_reissue_false_clear_count": (
        "post_closeout_lowering_without_reissue"
    ),
    "machine_ref_omission_false_clear_count": "machine_ref_omission",
    "revision_mismatch_false_clear_count": "revision_mismatch",
    "universal_self_claim_without_s14_false_clear_count": (
        "universal_self_claim_without_s14"
    ),
}
S9_REQUIRED_DENY = {
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
EXPECTED_LIVE_OPEN_CELLS = {
    "DESIGNER_ITSELF.envelope_growth",
}


def _manifest() -> dict[str, Any]:
    return json.loads(S9_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s9_projection_lowering_manifest"])


def test_layer2_s9_manifest_is_valid_and_open_count_stays_3() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s9_projection_lowering_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "team-runtime-quality"
    assert manifest["slice"] == "S9"
    assert manifest["depends_on"] == ["S2", "S5", "S8"]
    assert manifest["cells_closed"] == []
    assert manifest["layer_cells_advanced"] == [
        "DESIGNER_ITSELF.closeout_projection_ratchet"
    ]
    assert manifest["expected_current_open_cell_count"] == 3
    summary = validation["summary"]
    assert summary["current_open_cell_count"] >= 1
    assert summary["s9_case_count"] == 13
    assert summary["s9_projection_render_count"] >= 52
    assert summary["s9_projection_faithfulness_denominator"] >= 52
    assert summary["s9_projection_faithfulness_numerator"] == (
        summary["s9_projection_faithfulness_denominator"]
    )
    assert summary["s9_projection_faithfulness_pass_rate"] == 1.0
    assert summary["s9_lowering_gate_count"] >= 13
    assert summary["s9_lowering_append_receipt_count"] >= 1
    assert summary["s9_expected_current_open_cell_count"] == 3


def test_layer2_s9_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    manifest = _manifest()
    trace_s9_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S9"
    }

    assert set(manifest["required_artifacts"]) == S9_REQUIRED_ARTIFACTS
    assert trace_s9_artifacts == S9_REQUIRED_ARTIFACTS
    for artifact_name in S9_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s9_inventory_registration_exists() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s9_projection_lowering_manifest"
    assert artifact["path"] == S9_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s9_projection_lowering_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "team-runtime-quality"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]


def test_layer2_s9_floor_is_governed_without_denominator_change() -> None:
    payloads = _payloads()
    manifest = _manifest()
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s9_projection_faithfulness"
    )

    assert floor["slice"] == "S9"
    assert floor["metric"] == "projection_faithfulness_pass_rate"
    assert floor["floor_owner"] == "team-runtime-quality"
    assert floor["revision_rule"] == "faithfulness_negative_controls_required"
    assert manifest["projection_faithfulness_denominator"] >= 52
    assert manifest["projection_faithfulness_numerator"] == (
        manifest["projection_faithfulness_denominator"]
    )
    assert manifest["projection_faithfulness_pass_rate"] == 1.0
    assert manifest["lowering_gate_count"] >= 13
    assert manifest["lowering_append_receipt_count"] >= 1


def test_layer2_s9_inventory_count_is_at_least_post_s10_floor() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["summary"]["inventory_artifact_count"] >= 18


def test_layer2_s9_b_side_does_not_import_projection_lowering_producer() -> None:
    b_side = PDC_DESIGN_SEARCH.read_text(encoding="utf-8")

    assert "runtime.quality.layer2_projection_lowering" not in b_side
    assert "layer2_projection_lowering" not in b_side
    assert "build_canonical_design_record" not in b_side
    assert "verify_projection_faithfulness" not in b_side


def test_layer2_s9_projection_laundering_negative_controls_fail_closed() -> None:
    manifest = _manifest()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]

    for flat_field, nested_field in S9_FALSE_CLEAR_FIELDS.items():
        assert manifest[flat_field] == 0
        assert summary[f"s9_{flat_field}"] == 0
        assert summary["s9_false_clear_counts"][nested_field] == 0


def test_layer2_s9_verifier_reuse_blocks_universal_self_claim_without_s14_refs() -> None:
    verifier = (
        projection_semantics.verify_s9_projection_faithfulness_for_pdc_consumer_contract
    )

    result = verifier(
        projections={
            "public": {
                "authority_role": "projection_only",
                "projection_policy": "reads_canonical_design_record",
                "self_description_claim_refs": ["claim://policyos/universal-policy-designer"],
                "s14_universality_assurance_refs": [],
                "s9_projection_faithfulness": {
                    "faithfulness_status": "fail",
                    "issue_codes": ["s9_universal_self_claim_without_s14_refs"],
                },
                "may_not_be_used_for": [
                    "claim_authority",
                    "scorecard_authority",
                    "runtime_closeout_authority",
                    "s14_universality",
                ],
            }
        },
        expected_closeout_truth={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "blocker_codes": [],
            "omission_codes": [],
        },
    )

    assert result["status"] == "fail"
    assert "s9_universal_self_claim_without_s14_refs" in {
        issue["code"] for issue in result["issues"]
    }


def test_layer2_s9_keeps_future_authority_denied_after_s11_burn_down() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    current_open_cells = readiness._open_cell_refs(payload)  # type: ignore[attr-defined]
    manifest = _manifest()

    assert current_open_cells == EXPECTED_LIVE_OPEN_CELLS
    assert set(manifest["may_not_use_for"]) >= S9_REQUIRED_DENY
    forbidden_terms = {
        "s11_calibration",
        "s12_envelope_growth",
        "s13_accountability",
        "s14_universality",
        "production_authority",
    }
    rendered_manifest = json.dumps(manifest, sort_keys=True)
    for term in forbidden_terms:
        assert term in rendered_manifest
        assert f'"{term}": "implemented"' not in rendered_manifest
