from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map

REPO_ROOT = Path(__file__).resolve().parents[3]


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in validation["issues"]  # type: ignore[index]
    }


def test_cluster_ownership_map_is_governed_and_valid() -> None:
    validation = cluster_map.validate_cluster_ownership_map(REPO_ROOT)

    assert validation["status"] == "pass"
    assert validation["map_path"] == cluster_map.DEFAULT_MAP_PATH.as_posix()
    assert validation["summary"]["cell_count"] >= 24  # type: ignore[index]
    assert validation["summary"]["open_or_incomplete_count"] == 0  # type: ignore[index]
    architecture_core = validation["summary"]["architecture_core"]  # type: ignore[index]
    assert architecture_core["top_level_package_count"] == 25
    assert architecture_core["assigned_top_level_package_count"] == 25
    assert architecture_core["split_required_package_count"] >= 12
    assert architecture_core["assigned_subpackage_count"] >= 100
    handshake_graph = validation["summary"]["handshake_graph"]  # type: ignore[index]
    assert handshake_graph["edge_count"] >= 100
    assert handshake_graph["required_flow_count"] == 1
    open_cell_closure = validation["summary"]["open_cell_closure"]  # type: ignore[index]
    assert open_cell_closure["closure_contract_count"] == (  # type: ignore[index]
        validation["summary"]["open_or_incomplete_count"]  # type: ignore[index]
    )
    assert open_cell_closure["open_cell_count"] == 0


def test_cluster_ownership_map_uses_capability_ratchet_state_vocabulary() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    ratchet_states = cluster_map._load_ratchet_states(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_RATCHET_REPORT_PATH,
        [],
    )

    for axes in payload["cell"].values():
        for cell in axes.values():
            assert cell["ratchet_state"] in ratchet_states
            assert cell["p01_chain"] in ratchet_states


def test_cluster_ownership_firewall_patterns_are_registered() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    registered_patterns = cluster_map._load_failure_pattern_ids(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
        [],
    )

    assert {f"P{number}" for number in range(16, 25)} <= registered_patterns
    for axes in payload["cell"].values():
        for cell in axes.values():
            pattern_ids = {
                token
                for token in cell["firewall"].replace("_", " ").split()
                if token.startswith("P")
            }
            assert pattern_ids <= registered_patterns


def test_cluster_ownership_map_keeps_known_blind_spots_explicit() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)

    for cluster, axis in (
        ("SYSTEM", "measurability"),
        ("SYSTEM", "subject_granularity"),
        ("ACTOR", "state_capacity_feasibility"),
        ("ACTOR", "mandate_legitimacy"),
        ("OTHER_AGENTS", "strategic_response"),
    ):
        cell = payload["cell"][cluster][axis]
        assert cell["owner_module"] == (
            "src/polisyos/runtime/quality/design_axes/blind_spot_firewalls.py"
        )
        assert cell["ratchet_state"] == "implemented"
        assert cell["p01_chain"] == "implemented"
        assert cell["gap"] == "none_for_s6_fail_closed_scope"
        assert "S11" in cell["action"]
        assert "predictive" in cell["action"]

    assert (
        "OTHER_AGENTS" not in payload["open_cell_closure"]
        or "strategic_response" not in payload["open_cell_closure"]["OTHER_AGENTS"]
    )
    assert payload["cell"]["SYSTEM"]["connectivity_modularity"]["ratchet_state"] == (
        "implemented"
    )
    assert payload["cell"]["SYSTEM"]["connectivity_modularity"]["p01_chain"] == (
        "implemented"
    )
    assert payload["cell"]["SYSTEM"]["dynamics_feedback"]["ratchet_state"] == (
        "implemented"
    )
    assert payload["cell"]["SYSTEM"]["dynamics_feedback"]["p01_chain"] == (
        "implemented"
    )
    assert payload["cell"]["INTERVENTION"]["scale_composition"]["ratchet_state"] == (
        "implemented"
    )
    assert payload["cell"]["INTERVENTION"]["scale_composition"]["p01_chain"] == (
        "implemented"
    )
    assert payload["cell"]["INTERVENTION"]["design_candidate"]["firewall"].startswith(
        "P15"
    )
    assert payload["cell"]["INTERVENTION"]["design_candidate"]["ratchet_state"] == (
        "implemented"
    )

    scientist = payload["cell"]["CROSS_CUTTING"]["scientist_orchestration"]
    assert scientist["owner_module"] == "src/polisyos/runtime/quality/design_axes/mandate_bounded_delegation.py"
    assert scientist["ratchet_state"] == "implemented"
    assert scientist["p01_chain"] == "implemented"
    assert scientist["authority_dim"] == "cluster_orchestration_integrity"
    assert scientist["firewall"] == "P26_responsibility_integrity_laundering"
    assert scientist["gap"] == "none_for_s7_delegation_scope"
    assert "ACTOR.mandate_legitimacy" in scientist["consumes"]
    assert (
        "CROSS_CUTTING" not in payload["open_cell_closure"]
        or "scientist_orchestration" not in payload["open_cell_closure"]["CROSS_CUTTING"]
    )


def test_cluster_ownership_envelope_growth_documents_s12_and_s13_without_open_cell() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cell = payload["cell"]["DESIGNER_ITSELF"]["envelope_growth"]

    assert cell["owner_module"] == (
        "src/polisyos/runtime/quality/design_axes/resource_economics.py"
    )
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert cell["gap"] == "none_for_s12_resource_economics_scope"
    assert "S12" in cell["action"]
    assert "S13" in cell["action"]
    assert "allocation" in cell["action"]
    assert "bidirectional" in cell["action"]
    assert "DESIGNER_ITSELF" not in payload.get("open_cell_closure", {})


def test_cluster_ownership_handshake_edges_are_declared_nodes() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cell_ids = {
        f"{cluster}.{axis}"
        for cluster, axes in payload["cell"].items()
        for axis in axes
    }
    graph = payload["handshake_graph"]
    allowed_nodes = cell_ids | set(graph["ports"]) | set(graph["buses"])
    audiences = set(graph["audiences"])

    for cluster, axes in payload["cell"].items():
        for axis, cell in axes.items():
            for field in ("publishes", "consumes"):
                for target in cell[field]:
                    head = str(target).split(".", 1)[0]
                    assert target in allowed_nodes or head in audiences, (
                        cluster,
                        axis,
                        field,
                        target,
                    )


def test_architecture_core_top_level_packages_are_all_mapped() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    actual_packages = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "src/polisyos").iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    mapped_packages = {
        str(path)
        for group in payload["architecture_core"]["package_group"]
        for path in group["paths"]
    }

    assert mapped_packages == actual_packages
    assert {
        "src/polisyos/calibration",
        "src/polisyos/data_requirement",
        "src/polisyos/evidence",
        "src/polisyos/ir",
    } <= mapped_packages


def test_architecture_core_split_required_packages_cover_immediate_subpackages() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    split_required = set(payload["architecture_core"]["split_required_packages"])
    mapped_subpackages = {
        str(path)
        for group in payload["architecture_core"]["subpackage_group"]
        for path in group["paths"]
    }

    for package in split_required:
        package_path = REPO_ROOT / "src/polisyos" / package
        actual_subpackages = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in package_path.iterdir()
            if path.is_dir() and not path.name.startswith("__")
        }
        assert actual_subpackages <= mapped_subpackages, package


def test_cluster_ownership_validator_rejects_open_cell_without_gap() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    cluster, axis, _closure = _remaining_open_closure(payload)
    payload["cell"][cluster][axis]["gap"] = "none_for_seed_scope"

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_open_cell_gap_missing" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_dangling_handshake_target() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["cell"]["SYSTEM"]["domain_data"]["publishes"].append("KNOWLEDGE.missing")

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_handshake_target_dangling" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_non_reciprocal_cell_edge() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["cell"]["INTERVENTION"]["design_candidate"]["consumes"].remove(
        "INTERVENTION.design_grammar"
    )

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_handshake_cell_edge_not_reciprocal" in _issue_codes(
        validation
    )


def test_cluster_ownership_validator_rejects_unregistered_firewall_pattern() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["cell"]["SYSTEM"]["domain_data"]["firewall"] = "P99_unknown_pattern"

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_firewall_pattern_unregistered" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_broken_reflexive_response_flow() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    payload["cell"]["SYSTEM"]["dynamics_feedback"]["consumes"].remove(
        "SYSTEM.post_intervention_dgp"
    )

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_required_flow_not_consumed" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_missing_open_cell_closure() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    cluster, axis, _closure = _remaining_open_closure(payload)
    del payload["open_cell_closure"][cluster][axis]

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_open_cell_closure_missing" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_closure_state_mismatch() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    _cluster, _axis, closure = _remaining_open_closure(payload)
    closure["current_state"] = "producer_missing"

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_open_cell_closure_state_mismatch" in _issue_codes(
        validation
    )


def test_cluster_ownership_validator_rejects_closure_without_semantic_gap() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    _cluster, _axis, closure = _remaining_open_closure(payload)
    closure["missing_chain"].remove("semantic_test")

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_open_cell_closure_semantic_gap_missing" in _issue_codes(
        validation
    )


def test_cluster_ownership_validator_rejects_missing_architecture_core_package() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    for group in payload["architecture_core"]["package_group"]:
        if "src/polisyos/calibration" in group["paths"]:
            group["paths"].remove("src/polisyos/calibration")
            break

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_architecture_core_package_missing" in _issue_codes(validation)


def test_cluster_ownership_validator_rejects_missing_required_subpackage() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    payload = copy.deepcopy(payload)
    for group in payload["architecture_core"]["subpackage_group"]:
        if group["parent"] == "src/polisyos/runtime":
            group["paths"].remove("src/polisyos/runtime/http")
            break

    validation = _validate_payload_without_inventory_mutation(payload)

    assert validation["status"] == "fail"
    assert "cluster_ownership_architecture_core_subpackage_missing" in _issue_codes(
        validation
    )


def test_cluster_ownership_inventory_lists_map_and_validator() -> None:
    inventory = json.loads(
        (REPO_ROOT / cluster_map.DEFAULT_INVENTORY_PATH).read_text(encoding="utf-8")
    )
    artifacts = {artifact["id"]: artifact for artifact in inventory["artifacts"]}

    artifact = artifacts["cluster_ownership_map"]
    assert artifact["path"] == cluster_map.DEFAULT_MAP_PATH.as_posix()
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_cluster_ownership_map.py"
    )
    assert artifact["authority_boundary"] == "architecture_diagnostic_and_gap_ratcheting_only"


def test_cluster_ownership_cli_can_write_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "cluster-ownership-validation.json"

    exit_code = cluster_map.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--json-output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["map_path"] == cluster_map.DEFAULT_MAP_PATH.as_posix()


def _remaining_open_closure(
    payload: dict[str, object],
) -> tuple[str, str, dict[str, object]]:
    closures = [
        (str(cluster), str(axis), closure)
        for cluster, axes in payload["open_cell_closure"].items()  # type: ignore[index,union-attr]
        for axis, closure in axes.items()
    ]
    if not closures:
        cluster = "DESIGNER_ITSELF"
        axis = "synthetic_open_cell_probe"
        cell_ref = f"{cluster}.{axis}"
        payload["cell"].setdefault(cluster, {})[axis] = {  # type: ignore[index,union-attr]
            "owner_module": "",
            "seed_files": ["docs/reference/policy-design-case-failure-patterns.md"],
            "ratchet_state": "implemented_but_not_orchestrated",
            "p01_chain": "bridge_missing",
            "authority_dim": "synthetic_cluster_validator_probe",
            "firewall": "P01_contract_only_capability",
            "publishes": ["DESIGNER_ITSELF.certified_envelope_delta"],
            "consumes": ["SYSTEM.nonstationarity"],
            "gap": "synthetic_open_cell_for_empty_burn_down_negative_control",
            "action": "Exercise open-cell validator behavior after S12 burns the real open set to zero.",
        }
        payload["open_cell_closure"].setdefault(cluster, {})[axis] = {  # type: ignore[index,union-attr]
            "cell_ref": cell_ref,
            "owner": "team-architecture",
            "reuse_classification": "extend_existing",
            "current_state": "implemented_but_not_orchestrated",
            "target_state": "implemented",
            "missing_chain": [
                "producer",
                "persisted_artifact",
                "orchestration_bridge",
                "consumer",
                "verification",
                "surface",
                "semantic_test",
            ],
            "producer_artifact": "Synthetic producer artifact used only by cluster validator negative controls.",
            "persisted_artifact": "Synthetic persisted artifact used only by cluster validator negative controls.",
            "bridge_consumer": "Synthetic bridge consumer used only by cluster validator negative controls.",
            "surface": "Synthetic surface used only by cluster validator negative controls.",
            "semantic_test": "Synthetic semantic test used only by cluster validator negative controls.",
            "negative_test": "Synthetic open-cell closure mutation must still fail validation.",
            "acceptance_signal": "Cluster negative controls pass with an empty live open-cell set.",
            "next_action": "No production action; remove only if validator no longer needs synthetic probes.",
        }
        closures = [
            (
                cluster,
                axis,
                payload["open_cell_closure"][cluster][axis],  # type: ignore[index]
            )
        ]
    assert len(closures) == 1
    return closures[0]


def _validate_payload_without_inventory_mutation(payload: dict[str, object]) -> dict[str, object]:
    issues: list[dict[str, str]] = []
    ratchet_states = cluster_map._load_ratchet_states(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_RATCHET_REPORT_PATH,
        issues,
    )
    cells = cluster_map._flatten_cells(payload["cell"], issues)  # type: ignore[attr-defined,index]
    for cell in cells:
        cluster_map._validate_cell(  # type: ignore[attr-defined]
            cell,
            issues,
            repo_root=REPO_ROOT,
            ratchet_states=ratchet_states,
        )
    cell_keys = {(str(cell["cluster"]), str(cell["axis"])) for cell in cells}
    cluster_map._validate_architecture_core_assignments(  # type: ignore[attr-defined]
        payload,
        issues,
        repo_root=REPO_ROOT,
        ratchet_states=ratchet_states,
        cell_keys=cell_keys,
    )
    cells_by_id = {f"{cell['cluster']}.{cell['axis']}": cell for cell in cells}
    open_cell_closure_summary = cluster_map._validate_open_cell_closures(  # type: ignore[attr-defined]
        payload,
        cells_by_id,
        issues,
        ratchet_states=ratchet_states,
    )
    handshake_summary = cluster_map._validate_handshake_graph(  # type: ignore[attr-defined]
        payload,
        cells_by_id,
        issues,
    )
    registered_patterns = cluster_map._load_failure_pattern_ids(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
        issues,
    )
    cluster_map._validate_firewall_refs(  # type: ignore[attr-defined]
        cells,
        registered_patterns,
        issues,
    )
    return cluster_map._validation_result(  # type: ignore[attr-defined]
        map_path=cluster_map.DEFAULT_MAP_PATH,
        issues=issues,
        cells=cells,
        handshake_summary=handshake_summary,
        open_cell_closure_summary=open_cell_closure_summary,
    )
