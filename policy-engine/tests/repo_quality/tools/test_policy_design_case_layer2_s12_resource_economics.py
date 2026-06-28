from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
S12_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s12_resource_economics_manifest.json"
)
S12_MANIFEST_PATH = "architecture/policy_design_case/layer2_s12_resource_economics_manifest.json"
S12_REQUIRED_ARTIFACTS = {
    "KnowledgeGovernanceThroughputLedger",
    "EnvelopeGrowthLedger",
    "ResourceAllocationPolicy",
    "GrowthThermometerRecord",
    "ResourceEconomicsIntegrityReport",
}
S12_REQUIRED_AUTHORITY_SCOPE = {
    "value_of_information_allocation",
    "explore_exploit_posture",
    "envelope_growth_ledger",
    "growth_thermometers",
    "knowledge_governance_throughput",
    "allocation_priority_input",
}
S12_REQUIRED_DENY = {
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "mdp_bandit_optimizer_authority",
    "budget_interchangeability",
    "mission_or_value_self_authorization",
    "floor_relaxation",
    "s13_envelope_shrink",
    "s13_accountability_closure",
    "s14_universality",
}
S12_FALSE_CLEAR_FIELDS = (
    "bespoke_one_off_growth",
    "allocation_gaming_internal_metrics",
    "floor_lowering_for_useful_design_rate",
    "b_faster_than_a_growth",
    "meta_regress_past_principal",
    "interchangeable_budget",
    "growth_without_envelope_delta",
)
NEGATIVE_CONTROL_DIR = REPO_ROOT / "tests/fixtures/layer2/s12/negative_controls"


def _manifest() -> dict[str, Any]:
    assert S12_MANIFEST.exists()
    return json.loads(S12_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s12_resource_economics_manifest"])


def _cluster_map() -> dict[str, Any]:
    return tomllib.loads(
        (REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml")
        .read_text(encoding="utf-8")
    )


def test_layer2_s12_manifest_exists_and_open_count_drops_to_0() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s12_resource_economics_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "principal-governance"
    assert manifest["slice"] == "S12"
    assert manifest["depends_on"] == ["S3", "S7"]
    assert manifest["cells_closed"] == ["DESIGNER_ITSELF.envelope_growth"]
    assert manifest["expected_current_open_cell_count"] == 0
    assert manifest["remaining_open_cells"] == []
    assert manifest["burn_down_complete"] is True

    summary = validation["summary"]
    assert summary["current_open_cell_count"] == 0
    assert summary["remaining_open_cells"] == []
    assert summary["s12_case_count"] == 13
    assert summary["s12_expected_current_open_cell_count"] == 0


def test_layer2_s12_closes_envelope_growth_cell() -> None:
    cluster_map = _cluster_map()
    cell = cluster_map["cell"]["DESIGNER_ITSELF"]["envelope_growth"]

    assert cell["owner_module"] == (
        "src/polisyos/runtime/quality/design_axes/resource_economics.py"
    )
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert cell["gap"] == "none_for_s12_resource_economics_scope"
    assert "DESIGNER_ITSELF" not in cluster_map.get("open_cell_closure", {})


def test_layer2_s12_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    manifest = _manifest()
    trace_s12_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S12"
    }
    trace_s12_maturity = {
        str(row["name"]): row.get("maturity")
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S12"
    }

    assert set(manifest["required_artifacts"]) == S12_REQUIRED_ARTIFACTS
    assert trace_s12_artifacts == S12_REQUIRED_ARTIFACTS
    assert set(trace_s12_maturity.values()) == {"implemented"}
    for artifact_name in S12_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s12_floor_is_governed_and_growth_requires_envelope_delta() -> None:
    payloads = _payloads()
    manifest = _manifest()
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s12_growth_thermometers"
    )

    assert floor["slice"] == "S12"
    assert floor["metric"] == "reuse_rate_and_override_rate_trend"
    assert floor["floor_owner"] == "principal-governance"
    assert floor["revision_rule"] == "growth_counting_requires_envelope_delta"
    assert manifest["floor_id"] == "s12_growth_thermometers"
    assert manifest["floor_metric"] == "reuse_rate_and_override_rate_trend"
    assert manifest["growth_without_envelope_delta_count"] == 0
    for false_clear_field in S12_FALSE_CLEAR_FIELDS:
        flat_field = f"{false_clear_field}_false_clear_count"
        assert manifest[flat_field] == 0
        assert manifest["false_clear_counts"][false_clear_field] == 0


def test_layer2_s12_inventory_registration_exists() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s12_resource_economics_manifest"
    assert artifact["path"] == S12_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s12_resource_economics_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "principal-governance"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]


def test_layer2_s12_inventory_count_accepts_post_s14_registration() -> None:
    payloads = _payloads()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert readiness._inventory_layer2_artifact_count(payloads["inventory"]) in {20, 21, 22}
    assert validation["summary"]["inventory_artifact_count"] in {20, 21, 22}


def test_layer2_s12_snapshot_allows_registered_s13_artifacts() -> None:
    payloads = _payloads()
    trace_s13_maturity = {
        str(row["name"]): row.get("maturity")
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S13"
    }
    inventory_ids = {
        str(artifact["id"])
        for artifact in payloads["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }

    assert set(trace_s13_maturity) == {
        "DeploymentDossier",
        "DivergenceRecord",
        "LearningUpdateProposal",
        "EnvelopeRevision",
        "CertifiedEnvelopeDelta",
        "AssuranceCaseDelta",
    }
    assert set(trace_s13_maturity.values()) == {"implemented"}
    assert "layer2_s13_post_deploy_accountability_manifest" in inventory_ids


def test_layer2_s12_b_side_does_not_import_resource_economics_producer() -> None:
    source = (
        REPO_ROOT / "src/polisyos/pdc/_impl/layer2_design_search.py"
    ).read_text(encoding="utf-8")

    assert "polisyos.runtime.quality.design_axes.resource_economics" not in source
    assert "layer2_resource_economics" not in source
    assert "build_s12_resource_economics_posture" not in source


def test_layer2_s12_negative_controls_fail_closed() -> None:
    assert {path.name for path in NEGATIVE_CONTROL_DIR.glob("*.json")} == {
        "bespoke_one_off_growth_probe.json",
        "allocation_gaming_internal_metrics_probe.json",
        "floor_lowering_for_useful_design_rate_probe.json",
        "b_faster_than_a_growth_probe.json",
        "meta_regress_past_principal_probe.json",
        "interchangeable_budget_probe.json",
        "growth_without_envelope_delta_probe.json",
    }
    for path in NEGATIVE_CONTROL_DIR.glob("*.json"):
        probe = json.loads(path.read_text(encoding="utf-8"))
        assert probe["false_clear_field"] in S12_FALSE_CLEAR_FIELDS
        assert probe["expected_false_clear_count"] == 0
        assert probe["expected_disposition"] in {
            "blocked",
            "blocked_no_envelope_delta",
            "flagged_bespoke_one_off",
        }


def test_layer2_s12_manifest_metrics_match_generated_corpus_summary(tmp_path: Path) -> None:
    manifest = _manifest()
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )
    summary = report["s12_resource_economics_summary"]

    assert manifest["case_count"] == summary["case_count"] == 13
    assert manifest["voi_site_count"] == summary["voi_site_count"]
    assert manifest["typed_budget_count"] == summary["typed_budget_count"] == 5
    assert manifest["override_rate_trend"] == summary["override_rate_trend"]
    assert manifest["reuse_rate_trend"] == summary["reuse_rate_trend"]
    assert manifest["held_out_status"] == summary["held_out_status"] == "pending_s14"
    assert manifest["growth_without_envelope_delta_count"] == (
        summary["growth_without_envelope_delta_count"]
    )
    assert manifest["false_clear_counts"] == summary["false_clear_counts"]


def test_layer2_s12_manifest_denies_s13_s14_and_production_authority() -> None:
    manifest = _manifest()
    rendered_manifest = json.dumps(manifest, sort_keys=True)

    assert set(manifest["authority_scope"]) == S12_REQUIRED_AUTHORITY_SCOPE
    assert set(manifest["may_not_use_for"]) >= S12_REQUIRED_DENY
    for future_term in (
        "s13_envelope_shrink",
        "s13_accountability_closure",
        "s14_universality",
        "production_authority",
        "production_recommendation",
        "preference_learning",
        "mdp_bandit_optimizer_authority",
    ):
        assert future_term in rendered_manifest
        assert f'"{future_term}": "implemented"' not in rendered_manifest


def test_layer2_s12_burn_down_complete_zero_open_cells() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    cluster_map = _cluster_map()
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["current_open_cell_count"] == 0
    assert validation["summary"]["remaining_open_cells"] == []
    assert manifest["burn_down_complete"] is True
    assert manifest["remaining_open_cells"] == []
    assert cluster_map.get("open_cell_closure", {}) == {}
