from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
S6_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json"
)
S6_MANIFEST_PATH = (
    "architecture/policy_design_case/layer2_s6_blind_spot_firewalls_manifest.json"
)
S6_CELLS = {
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
    "ACTOR.state_capacity_feasibility",
    "ACTOR.mandate_legitimacy",
    "OTHER_AGENTS.strategic_response",
}
S6_REQUIRED_ARTIFACTS = {
    "MeasurabilityAdequacyRecord",
    "AggregationValidityRecord",
    "CapacityFeasibilityRecord",
    "MandateLegitimacyRecord",
    "StrategicResponseRecord",
    "ClusterAuthorityDimensionRecord",
}
S6_REQUIRED_FIREWALLS = {"P18", "P19", "P21", "P22", "P24"}
S6_REQUIRED_BRIDGE_CONSUMERS = {
    "KNOWLEDGE.epistemic_regime",
    "ACTOR.value_choice_provenance",
    "INTERVENTION.targeting",
    "INTERVENTION.feasibility",
    "DESIGNER_ITSELF.envelope_membership",
    "PUBLIC.legitimacy_disclosure",
    "INTERVENTION.design_candidate",
    "SYSTEM.post_intervention_dgp",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.robustness",
}
S6_C3_AUTHORITY_DIMENSIONS = {
    "measurability_adequacy",
    "aggregation_validity",
    "capacity_feasibility",
    "mandate_legitimacy",
    "strategic_robustness",
    "response_model_validity",
}
S6_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "delegation_authority",
    "value_choice_authority",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "rich_response_model_authority",
    "capacity_transfer_authority",
    "mandate_authority_from_llm",
    "proxy_construct_equivalence_without_disclosure",
    "aggregation_scope_transfer_without_validity",
    "post_policy_effect_claim_without_response_model",
}


@pytest.fixture(scope="module")
def w12d_s6_summary(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp_path = tmp_path_factory.mktemp("w12d-s6-corpus")
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )
    return dict(report["s6_blind_spot_summary"])


def _s6() -> dict[str, Any]:
    return json.loads(S6_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    payloads = _payloads()
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in payloads["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s6_blind_spot_firewalls_manifest"])


def _s6_cells_from_cluster_map() -> dict[str, dict[str, Any]]:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cells: dict[str, dict[str, Any]] = {}
    for cell_ref in S6_CELLS:
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cells[cell_ref] = dict(payload["cell"][cluster][axis])
    return cells


def test_layer2_s6_manifest_is_valid_and_live_open_count_is_3() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _s6()

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]
    assert summary["current_open_cell_count"] == 3
    assert summary["inventory_artifact_count"] >= 18
    assert summary["s6_expected_current_open_cell_count"] == 5
    assert summary["s6_fail_closed_coverage"] == 1.0
    assert summary["s6_false_clear_count"] == 0
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["maturity"] == "fail_closed"


def test_layer2_s6_closes_five_cells_with_fail_closed_maturity() -> None:
    manifest = _s6()
    cells = _s6_cells_from_cluster_map()

    assert set(manifest["cells_closed"]) == S6_CELLS
    assert manifest["expected_current_open_cell_count"] == 5
    assert manifest["floor_id"] == "s6_fail_closed_coverage"
    assert manifest["floor_metric"] == (
        "per_axis_fail_closed_negative_control_pass_rate"
    )
    assert manifest["floor_expected_minimum"] == 1.0
    for cell in cells.values():
        assert cell["owner_module"] == (
            "src/polisyos/runtime/quality/layer2_blind_spot_firewalls.py"
        )
        assert cell["ratchet_state"] == "implemented"
        assert cell["p01_chain"] == "implemented"
        assert cell["gap"] == "none_for_s6_fail_closed_scope"
        assert "S11" in cell["action"]
        assert "predictive" in cell["action"]


def test_layer2_s6_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    trace_s6_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S6"
    }

    assert set(_s6()["required_artifacts"]) == S6_REQUIRED_ARTIFACTS
    assert trace_s6_artifacts >= S6_REQUIRED_ARTIFACTS
    for artifact_name in S6_REQUIRED_ARTIFACTS:
        assert hasattr(runtime_quality, artifact_name), artifact_name


def test_layer2_s6_firewalls_are_registered_and_all_five_axes_required() -> None:
    payloads = _payloads()
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s6_fail_closed_coverage"
    )
    registered_patterns = cluster_map._load_failure_pattern_ids(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
        [],
    )

    assert set(_s6()["required_firewalls"]) == S6_REQUIRED_FIREWALLS
    assert registered_patterns >= S6_REQUIRED_FIREWALLS
    assert floor["slice"] == "S6"
    assert floor["metric"] == "per_axis_fail_closed_negative_control_pass_rate"
    assert floor["revision_rule"] == "all_five_blind_spot_axes_required"
    assert floor["floor_owner"] == "team-runtime-quality"


def test_layer2_s6_inventory_registration_exists() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    artifact = _inventory_artifact()

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["inventory_artifact_count"] >= 18
    assert artifact["id"] == "layer2_s6_blind_spot_firewalls_manifest"
    assert artifact["path"] == S6_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s6_blind_spot_firewalls_manifest"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer2_s6_blind_spot_firewalls_manifest.v1"
    )
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["maturity"] == "fail_closed"
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    )
    assert artifact["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )


def test_layer2_s6_inventory_and_manifest_authority_boundaries_match() -> None:
    manifest = _s6()
    artifact = _inventory_artifact()

    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]
    assert manifest["producer_module"] == (
        "src/polisyos/runtime/quality/layer2_blind_spot_firewalls.py"
    )
    assert manifest["consumer_module"] == "src/polisyos/pdc/_impl/layer2_design_search.py"
    assert manifest["canonical_route"] == artifact["canonical_route"]
    assert manifest["validator"] == artifact["validator"]


def test_layer2_s6_c3_authority_dimensions_are_canonical() -> None:
    manifest = _s6()
    c3_coverage = manifest["c3_authority_dimension_coverage"]

    assert set(manifest["c3_authority_dimensions"]) == S6_C3_AUTHORITY_DIMENSIONS
    assert set(c3_coverage) == S6_C3_AUTHORITY_DIMENSIONS
    assert all(c3_coverage[dimension] is True for dimension in S6_C3_AUTHORITY_DIMENSIONS)
    assert "strategic_robustness" in manifest["authority_scope"]
    assert "response_model_validity" in manifest["authority_scope"]


def test_layer2_s6_bridge_consumers_cover_cluster_map_contracts() -> None:
    manifest = _s6()
    cells = _s6_cells_from_cluster_map()
    cluster_consumers = {
        str(consumer)
        for cell in cells.values()
        for consumer in cell.get("publishes", [])
    }
    bridge_coverage = manifest["bridge_consumer_coverage"]

    assert set(manifest["required_bridge_consumers"]) == S6_REQUIRED_BRIDGE_CONSUMERS
    assert cluster_consumers >= S6_REQUIRED_BRIDGE_CONSUMERS
    assert set(bridge_coverage) >= S6_REQUIRED_BRIDGE_CONSUMERS
    assert all(
        bridge_coverage[consumer] is True
        for consumer in S6_REQUIRED_BRIDGE_CONSUMERS
    )


def test_layer2_s6_cluster_map_marks_cells_implemented_and_unlisted_as_open() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    current_open_cells = readiness._open_cell_refs(payload)  # type: ignore[attr-defined]

    assert S6_CELLS.isdisjoint(current_open_cells)
    for cell_ref, cell in _s6_cells_from_cluster_map().items():
        assert cell["ratchet_state"] == "implemented", cell_ref
        assert cell["p01_chain"] == "implemented", cell_ref
        cluster, axis = cell_ref.split(".", maxsplit=1)
        assert axis not in payload.get("open_cell_closure", {}).get(cluster, {})


def test_layer2_s6_may_not_use_for_blocks_prediction_delegation_value_and_production_authority() -> None:
    deny = set(_s6()["may_not_use_for"])

    assert deny >= S6_REQUIRED_DENY
    assert {
        "production_claim_authority",
        "rollout_authority",
        "publication_authority",
        "delegation_authority",
        "value_choice_authority",
        "outcome_prediction_authority",
    } <= deny


def test_layer2_s6_manifest_metrics_match_generated_corpus_summary(
    w12d_s6_summary: dict[str, Any],
) -> None:
    manifest = _s6()

    for field in (
        "case_count",
        "axis_coverage_count",
        "all_five_axes_covered",
        "per_axis_fail_closed_negative_control_pass_rate",
        "false_clear_count",
        "bridge_consumer_coverage",
        "c3_authority_dimension_coverage",
    ):
        assert manifest[field] == w12d_s6_summary[field]


def test_layer2_s6_corpus_summary_records_zero_false_clear(
    w12d_s6_summary: dict[str, Any],
) -> None:
    assert w12d_s6_summary["case_count"] == 13
    assert w12d_s6_summary["axis_coverage_count"] == 5
    assert w12d_s6_summary["all_five_axes_covered"] is True
    assert w12d_s6_summary["per_axis_fail_closed_negative_control_pass_rate"] == 1.0
    assert w12d_s6_summary["false_clear_count"] == 0
    assert set(w12d_s6_summary["bridge_consumer_coverage"]) >= (
        S6_REQUIRED_BRIDGE_CONSUMERS
    )
    assert all(
        w12d_s6_summary["bridge_consumer_coverage"][consumer] is True
        for consumer in S6_REQUIRED_BRIDGE_CONSUMERS
    )
    assert set(w12d_s6_summary["c3_authority_dimension_coverage"]) == (
        S6_C3_AUTHORITY_DIMENSIONS
    )
