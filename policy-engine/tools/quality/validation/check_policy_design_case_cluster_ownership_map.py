#!/usr/bin/env python3
"""Validate the Policy Design Case cluster ownership map."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.cluster_ownership_map.v1"
TOOL_NAME = "quality.validation.check-policy-design-case-cluster-ownership-map"
DEFAULT_MAP_PATH = Path("architecture/policy_design_case/cluster_ownership_map.toml")
DEFAULT_INVENTORY_PATH = Path("architecture/policy_design_case/inventory.json")
DEFAULT_RATCHET_REPORT_PATH = Path(
    "architecture/policy_design_case/capability_reality_report.json"
)
DEFAULT_FAILURE_PATTERN_REGISTER_PATH = Path(
    "docs/reference/policy-design-case-failure-patterns.md"
)
REQUIRED_CLUSTERS = frozenset(
    {
        "SYSTEM",
        "KNOWLEDGE",
        "ACTOR",
        "INTERVENTION",
        "OTHER_AGENTS",
        "DESIGNER_ITSELF",
        "CROSS_CUTTING",
    }
)
REQUIRED_FIELDS = frozenset(
    {
        "owner_module",
        "seed_files",
        "ratchet_state",
        "p01_chain",
        "authority_dim",
        "firewall",
        "publishes",
        "consumes",
        "gap",
        "action",
    }
)
REQUIRED_OPEN_CELL_CLOSURE_FIELDS = frozenset(
    {
        "cell_ref",
        "owner",
        "reuse_classification",
        "current_state",
        "target_state",
        "missing_chain",
        "producer_artifact",
        "persisted_artifact",
        "bridge_consumer",
        "surface",
        "semantic_test",
        "negative_test",
        "acceptance_signal",
        "next_action",
    }
)
CAPABILITY_CHAIN_STEPS = frozenset(
    {
        "typed_contract",
        "producer",
        "persisted_artifact",
        "orchestration_bridge",
        "consumer",
        "verification",
        "surface",
        "semantic_test",
    }
)
REUSE_CLASSIFICATIONS = frozenset(
    {
        "wire_existing",
        "extend_existing",
        "consolidate_existing",
        "build_new",
    }
)
REQUIRED_SEED_CELLS = frozenset(
    {
        ("SYSTEM", "connectivity_modularity"),
        ("SYSTEM", "measurability"),
        ("ACTOR", "state_capacity_feasibility"),
        ("ACTOR", "mandate_legitimacy"),
        ("OTHER_AGENTS", "strategic_response"),
        ("DESIGNER_ITSELF", "envelope_growth"),
    }
)
REQUIRED_ARCHITECTURE_CORE_ROOT = Path("src/polisyos")
ARCHITECTURE_CORE_REQUIRED_FIELDS = frozenset(
    {
        "cell_ref",
        "paths",
        "coverage_mode",
        "ratchet_state",
        "p01_chain",
        "gap",
        "action",
    }
)
OPEN_OR_INCOMPLETE_STATES = frozenset(
    {
        "implemented_but_not_orchestrated",
        "bridge_missing",
        "producer_missing",
        "contract_only",
        "artifact_missing",
        "consumer_missing",
        "verification_missing",
        "surface_missing",
        "semantic_test_missing",
    }
)


def load_cluster_ownership_map(
    repo_root: Path | str = REPO_ROOT,
    *,
    map_path: Path | str = DEFAULT_MAP_PATH,
) -> dict[str, Any]:
    """Load the governed cluster ownership map from TOML."""

    root = Path(repo_root)
    path = root / Path(map_path)
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    payload["_path"] = str(Path(map_path))
    return payload


def validate_cluster_ownership_map(
    repo_root: Path | str = REPO_ROOT,
    *,
    map_path: Path | str = DEFAULT_MAP_PATH,
    inventory_path: Path | str = DEFAULT_INVENTORY_PATH,
    ratchet_report_path: Path | str = DEFAULT_RATCHET_REPORT_PATH,
    failure_pattern_register_path: Path | str = DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
) -> dict[str, Any]:
    """Validate map shape, ratchet vocabulary, ownership gaps, and seed refs."""

    root = Path(repo_root)
    map_rel = Path(map_path)
    inventory_rel = Path(inventory_path)
    ratchet_rel = Path(ratchet_report_path)
    pattern_rel = Path(failure_pattern_register_path)
    issues: list[dict[str, str]] = []

    if not (root / map_rel).exists():
        return _validation_result(
            map_path=map_rel,
            issues=[
                {
                    "code": "cluster_ownership_map_missing",
                    "message": f"{map_rel.as_posix()} does not exist.",
                }
            ],
            cells=[],
        )

    payload = load_cluster_ownership_map(root, map_path=map_rel)
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "cluster_ownership_schema_version_invalid",
                f"Expected schema_version={SCHEMA_VERSION}.",
            )
        )

    ratchet_states = _load_ratchet_states(root / ratchet_rel, issues)
    declared_states = set(payload.get("ratchet_state_vocabulary", []))
    unknown_declared_states = declared_states - ratchet_states
    if unknown_declared_states:
        issues.append(
            _issue(
                "cluster_ownership_declares_non_ratchet_state",
                "Map declares states not present in capability ratchet vocabulary: "
                + ", ".join(sorted(unknown_declared_states)),
            )
        )

    required_fields = set(payload.get("required_cell_fields", []))
    missing_declared_required_fields = REQUIRED_FIELDS - required_fields
    if missing_declared_required_fields:
        issues.append(
            _issue(
                "cluster_ownership_required_fields_missing",
                "required_cell_fields omits: "
                + ", ".join(sorted(missing_declared_required_fields)),
            )
        )

    closure_fields = set(payload.get("required_open_cell_closure_fields", []))
    missing_declared_closure_fields = REQUIRED_OPEN_CELL_CLOSURE_FIELDS - closure_fields
    if missing_declared_closure_fields:
        issues.append(
            _issue(
                "cluster_ownership_required_closure_fields_missing",
                "required_open_cell_closure_fields omits: "
                + ", ".join(sorted(missing_declared_closure_fields)),
            )
        )

    declared_chain_steps = set(payload.get("capability_chain_steps", []))
    unknown_declared_chain_steps = declared_chain_steps - CAPABILITY_CHAIN_STEPS
    if unknown_declared_chain_steps:
        issues.append(
            _issue(
                "cluster_ownership_unknown_capability_chain_step_declared",
                "capability_chain_steps declares unknown steps: "
                + ", ".join(sorted(unknown_declared_chain_steps)),
            )
        )

    declared_reuse = set(payload.get("reuse_classification_vocabulary", []))
    unknown_declared_reuse = declared_reuse - REUSE_CLASSIFICATIONS
    if unknown_declared_reuse:
        issues.append(
            _issue(
                "cluster_ownership_unknown_reuse_classification_declared",
                "reuse_classification_vocabulary declares unknown classifications: "
                + ", ".join(sorted(unknown_declared_reuse)),
            )
        )

    cells = _flatten_cells(payload.get("cell", {}), issues)
    cells_by_id = {f"{cell['cluster']}.{cell['axis']}": cell for cell in cells}
    seen_clusters = {cell["cluster"] for cell in cells}
    missing_clusters = REQUIRED_CLUSTERS - seen_clusters
    if missing_clusters:
        issues.append(
            _issue(
                "cluster_ownership_required_cluster_missing",
                "Map omits required clusters: " + ", ".join(sorted(missing_clusters)),
            )
        )

    seen_cell_keys = {(cell["cluster"], cell["axis"]) for cell in cells}
    missing_seed_cells = REQUIRED_SEED_CELLS - seen_cell_keys
    if missing_seed_cells:
        issues.append(
            _issue(
                "cluster_ownership_required_seed_cell_missing",
                "Map omits required seed cells: "
                + ", ".join(f"{cluster}.{axis}" for cluster, axis in sorted(missing_seed_cells)),
            )
        )

    for cell in cells:
        _validate_cell(
            cell,
            issues,
            repo_root=root,
            ratchet_states=ratchet_states,
        )

    open_cell_closure_summary = _validate_open_cell_closures(
        payload,
        cells_by_id,
        issues,
        ratchet_states=ratchet_states,
    )
    architecture_core_summary = _validate_architecture_core_assignments(
        payload,
        issues,
        repo_root=root,
        ratchet_states=ratchet_states,
        cell_keys=seen_cell_keys,
    )
    handshake_summary = _validate_handshake_graph(payload, cells_by_id, issues)
    registered_patterns = _load_failure_pattern_ids(root / pattern_rel, issues)
    _validate_firewall_refs(cells, registered_patterns, issues)

    _validate_inventory(
        root / inventory_rel,
        issues,
        map_path=map_rel,
        validator_path=Path("tools/quality/validation/check_policy_design_case_cluster_ownership_map.py"),
    )

    return _validation_result(
        map_path=map_rel,
        issues=issues,
        cells=cells,
        architecture_core_summary=architecture_core_summary,
        handshake_summary=handshake_summary,
        open_cell_closure_summary=open_cell_closure_summary,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the cluster ownership map validator CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--map-path", default=str(DEFAULT_MAP_PATH))
    parser.add_argument("--inventory-path", default=str(DEFAULT_INVENTORY_PATH))
    parser.add_argument("--ratchet-report-path", default=str(DEFAULT_RATCHET_REPORT_PATH))
    parser.add_argument(
        "--failure-pattern-register-path",
        default=str(DEFAULT_FAILURE_PATTERN_REGISTER_PATH),
    )
    parser.add_argument("--json-output", default="")
    args = parser.parse_args(argv)

    result = validate_cluster_ownership_map(
        args.repo_root,
        map_path=args.map_path,
        inventory_path=args.inventory_path,
        ratchet_report_path=args.ratchet_report_path,
        failure_pattern_register_path=args.failure_pattern_register_path,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "pass" else 1


def _flatten_cells(raw_cells: object, issues: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not isinstance(raw_cells, dict):
        issues.append(_issue("cluster_ownership_cells_missing", "Map has no [cell.*] tables."))
        return []

    cells: list[dict[str, Any]] = []
    for cluster, axes in raw_cells.items():
        if cluster not in REQUIRED_CLUSTERS:
            issues.append(
                _issue(
                    "cluster_ownership_unknown_cluster",
                    f"Unknown cluster {cluster!r}; use the governed cluster vocabulary.",
                )
            )
            continue
        if not isinstance(axes, dict):
            issues.append(
                _issue(
                    "cluster_ownership_cluster_axes_invalid",
                    f"Cluster {cluster!r} must contain axis tables.",
                )
            )
            continue
        for axis, fields in axes.items():
            if not isinstance(fields, dict):
                issues.append(
                    _issue(
                        "cluster_ownership_cell_invalid",
                        f"Cell {cluster}.{axis} must be a table.",
                    )
                )
                continue
            cell = dict(fields)
            cell["cluster"] = str(cluster)
            cell["axis"] = str(axis)
            cells.append(cell)
    return cells


def _validate_cell(
    cell: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    repo_root: Path,
    ratchet_states: set[str],
) -> None:
    cell_id = f"{cell['cluster']}.{cell['axis']}"
    missing_fields = REQUIRED_FIELDS - set(cell)
    if missing_fields:
        issues.append(
            _issue(
                "cluster_ownership_cell_required_field_missing",
                f"{cell_id} omits fields: {', '.join(sorted(missing_fields))}.",
            )
        )
        return

    ratchet_state = str(cell["ratchet_state"])
    p01_chain = str(cell["p01_chain"])
    if ratchet_state not in ratchet_states:
        issues.append(
            _issue(
                "cluster_ownership_cell_unknown_ratchet_state",
                f"{cell_id} uses ratchet_state={ratchet_state!r}, not a capability-ratchet state.",
            )
        )
    if p01_chain not in ratchet_states:
        issues.append(
            _issue(
                "cluster_ownership_cell_unknown_p01_chain_state",
                f"{cell_id} uses p01_chain={p01_chain!r}, not a capability-ratchet state.",
            )
        )

    owner_module = str(cell["owner_module"]).strip()
    if ratchet_state == "implemented" and not owner_module:
        issues.append(
            _issue(
                "cluster_ownership_implemented_owner_missing",
                f"{cell_id} is implemented but has no owner_module.",
            )
        )
    if not owner_module and ratchet_state not in OPEN_OR_INCOMPLETE_STATES:
        issues.append(
            _issue(
                "cluster_ownership_owner_missing_without_open_state",
                f"{cell_id} has no owner_module but is not in an open or incomplete state.",
            )
        )

    seed_files = cell["seed_files"]
    if not isinstance(seed_files, list) or not seed_files:
        issues.append(
            _issue(
                "cluster_ownership_seed_files_missing",
                f"{cell_id} must name at least one seed file or README substrate.",
            )
        )
    else:
        for seed in seed_files:
            seed_path = repo_root / str(seed)
            if not seed_path.exists():
                issues.append(
                    _issue(
                        "cluster_ownership_seed_file_missing",
                        f"{cell_id} seed file does not exist: {seed}.",
                    )
                )

    for list_field in ("publishes", "consumes"):
        value = cell[list_field]
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            issues.append(
                _issue(
                    "cluster_ownership_handshake_field_invalid",
                    f"{cell_id} {list_field} must be a non-empty list of strings.",
                )
            )

    for text_field in ("authority_dim", "firewall", "gap", "action"):
        value = str(cell[text_field]).strip()
        if not value:
            issues.append(
                _issue(
                    "cluster_ownership_text_field_missing",
                    f"{cell_id} {text_field} must be populated.",
                )
            )

    if ratchet_state in OPEN_OR_INCOMPLETE_STATES:
        if str(cell["gap"]).strip().startswith("none"):
            issues.append(
                _issue(
                    "cluster_ownership_open_cell_gap_missing",
                    f"{cell_id} is open or incomplete but does not name a real gap.",
                )
            )
        if p01_chain == "implemented":
            issues.append(
                _issue(
                    "cluster_ownership_open_cell_p01_chain_implausible",
                    f"{cell_id} is open or incomplete but p01_chain is implemented.",
                )
            )


def _validate_handshake_graph(
    payload: dict[str, Any],
    cells_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
) -> dict[str, Any]:
    graph = payload.get("handshake_graph")
    if not isinstance(graph, dict):
        issues.append(
            _issue(
                "cluster_ownership_handshake_graph_missing",
                "Map must declare [handshake_graph] ports, buses, audiences, and required flows.",
            )
        )
        return {}

    audiences = _string_set(graph.get("audiences"))
    ports = _string_set(graph.get("ports"))
    buses = _string_set(graph.get("buses"))
    cell_ids = set(cells_by_id)
    allowed_nodes = cell_ids | ports | buses
    for port in sorted(ports & cell_ids):
        issues.append(
            _issue(
                "cluster_ownership_handshake_port_collides_with_cell",
                f"Handshake port {port!r} collides with a cell id.",
            )
        )
    for bus in sorted(buses & cell_ids):
        issues.append(
            _issue(
                "cluster_ownership_handshake_bus_collides_with_cell",
                f"Handshake bus {bus!r} collides with a cell id.",
            )
        )

    edge_count = 0
    direct_cell_edge_count = 0
    for source_id, cell in cells_by_id.items():
        for field in ("publishes", "consumes"):
            for target in cell.get(field, []) or []:
                edge_count += 1
                target_id = str(target)
                if not _handshake_target_resolves(
                    target_id,
                    allowed_nodes=allowed_nodes,
                    audiences=audiences,
                ):
                    issues.append(
                        _issue(
                            "cluster_ownership_handshake_target_dangling",
                            f"{source_id}.{field} references undeclared node {target_id!r}.",
                        )
                    )
                if field == "publishes" and target_id in cell_ids:
                    direct_cell_edge_count += 1
                    target_consumes = {
                        str(value) for value in cells_by_id[target_id].get("consumes", []) or []
                    }
                    if source_id not in target_consumes:
                        issues.append(
                            _issue(
                                "cluster_ownership_handshake_cell_edge_not_reciprocal",
                                f"{source_id} publishes to {target_id}, but {target_id}.consumes does not include {source_id}.",
                            )
                        )

    for flow in _list_of_dicts(graph.get("required_flow")):
        flow_id = str(flow.get("id", "unnamed_required_flow"))
        producer = str(flow.get("producer", ""))
        target = str(flow.get("target", ""))
        consumer = str(flow.get("consumer", ""))
        if producer not in cell_ids:
            issues.append(
                _issue(
                    "cluster_ownership_required_flow_producer_missing",
                    f"{flow_id} producer {producer!r} is not a cell.",
                )
            )
            continue
        if consumer not in cell_ids:
            issues.append(
                _issue(
                    "cluster_ownership_required_flow_consumer_missing",
                    f"{flow_id} consumer {consumer!r} is not a cell.",
                )
            )
            continue
        if not _handshake_target_resolves(target, allowed_nodes=allowed_nodes, audiences=audiences):
            issues.append(
                _issue(
                    "cluster_ownership_required_flow_target_dangling",
                    f"{flow_id} target {target!r} is not declared.",
                )
            )
        producer_publishes = {str(value) for value in cells_by_id[producer].get("publishes", []) or []}
        consumer_consumes = {str(value) for value in cells_by_id[consumer].get("consumes", []) or []}
        if target not in producer_publishes:
            issues.append(
                _issue(
                    "cluster_ownership_required_flow_not_published",
                    f"{flow_id} requires {producer} to publish {target!r}.",
                )
            )
        if target not in consumer_consumes:
            issues.append(
                _issue(
                    "cluster_ownership_required_flow_not_consumed",
                    f"{flow_id} requires {consumer} to consume {target!r}.",
                )
            )

    return {
        "audience_count": len(audiences),
        "port_count": len(ports),
        "bus_count": len(buses),
        "edge_count": edge_count,
        "direct_cell_edge_count": direct_cell_edge_count,
        "required_flow_count": len(_list_of_dicts(graph.get("required_flow"))),
    }


def _flatten_open_cell_closures(
    raw_closures: object, issues: list[dict[str, str]]
) -> list[dict[str, Any]]:
    if not isinstance(raw_closures, dict):
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closures_missing",
                "Map must define [open_cell_closure.*] entries for every open cell.",
            )
        )
        return []

    closures: list[dict[str, Any]] = []
    for cluster, axes in raw_closures.items():
        if not isinstance(axes, dict):
            issues.append(
                _issue(
                    "cluster_ownership_open_cell_closure_cluster_invalid",
                    f"open_cell_closure.{cluster} must contain axis tables.",
                )
            )
            continue
        for axis, fields in axes.items():
            if not isinstance(fields, dict):
                issues.append(
                    _issue(
                        "cluster_ownership_open_cell_closure_invalid",
                        f"open_cell_closure.{cluster}.{axis} must be a table.",
                    )
                )
                continue
            closure = dict(fields)
            closure["cluster"] = str(cluster)
            closure["axis"] = str(axis)
            closures.append(closure)
    return closures


def _validate_open_cell_closures(
    payload: dict[str, Any],
    cells_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
    *,
    ratchet_states: set[str],
) -> dict[str, Any]:
    closures = _flatten_open_cell_closures(payload.get("open_cell_closure"), issues)
    closures_by_id = {
        f"{closure['cluster']}.{closure['axis']}": closure for closure in closures
    }
    open_cells_by_id = {
        cell_id: cell
        for cell_id, cell in cells_by_id.items()
        if str(cell.get("ratchet_state")) in OPEN_OR_INCOMPLETE_STATES
    }

    missing_closures = set(open_cells_by_id) - set(closures_by_id)
    if missing_closures:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_missing",
                "Open cells without closure contracts: "
                + ", ".join(sorted(missing_closures)),
            )
        )

    extra_closures = set(closures_by_id) - set(open_cells_by_id)
    if extra_closures:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_extra",
                "Closure contracts exist for non-open or unknown cells: "
                + ", ".join(sorted(extra_closures)),
            )
        )

    for closure_id, closure in closures_by_id.items():
        _validate_open_cell_closure(
            closure_id,
            closure,
            open_cells_by_id.get(closure_id),
            issues,
            ratchet_states=ratchet_states,
        )

    chain_counts: Counter[str] = Counter()
    for closure in closures:
        for step in closure.get("missing_chain", []) or []:
            chain_counts[str(step)] += 1

    return {
        "closure_contract_count": len(closures),
        "open_cell_count": len(open_cells_by_id),
        "missing_chain_counts": dict(sorted(chain_counts.items())),
    }


def _validate_open_cell_closure(
    closure_id: str,
    closure: dict[str, Any],
    cell: dict[str, Any] | None,
    issues: list[dict[str, str]],
    *,
    ratchet_states: set[str],
) -> None:
    missing_fields = REQUIRED_OPEN_CELL_CLOSURE_FIELDS - set(closure)
    if missing_fields:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_field_missing",
                f"{closure_id} closure omits fields: {', '.join(sorted(missing_fields))}.",
            )
        )
        return

    if str(closure["cell_ref"]) != closure_id:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_ref_mismatch",
                f"{closure_id} closure has cell_ref={closure['cell_ref']!r}.",
            )
        )

    reuse = str(closure["reuse_classification"])
    if reuse not in REUSE_CLASSIFICATIONS:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_reuse_invalid",
                f"{closure_id} uses reuse_classification={reuse!r}.",
            )
        )

    current_state = str(closure["current_state"])
    target_state = str(closure["target_state"])
    if current_state not in ratchet_states:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_current_state_invalid",
                f"{closure_id} current_state={current_state!r} is not a ratchet state.",
            )
        )
    if target_state not in ratchet_states:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_target_state_invalid",
                f"{closure_id} target_state={target_state!r} is not a ratchet state.",
            )
        )
    if target_state != "implemented":
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_target_not_implemented",
                f"{closure_id} target_state must be 'implemented' for closure contracts.",
            )
        )
    if cell is not None and current_state != str(cell.get("ratchet_state")):
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_state_mismatch",
                f"{closure_id} current_state={current_state!r} does not match cell ratchet_state={cell.get('ratchet_state')!r}.",
            )
        )

    missing_chain = closure["missing_chain"]
    if (
        not isinstance(missing_chain, list)
        or not missing_chain
        or not all(isinstance(item, str) and item for item in missing_chain)
    ):
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_missing_chain_invalid",
                f"{closure_id} missing_chain must be a non-empty list of capability chain steps.",
            )
        )
        chain_steps: set[str] = set()
    else:
        chain_steps = {str(item) for item in missing_chain}
        unknown_steps = chain_steps - CAPABILITY_CHAIN_STEPS
        if unknown_steps:
            issues.append(
                _issue(
                    "cluster_ownership_open_cell_closure_unknown_chain_step",
                    f"{closure_id} missing_chain has unknown steps: {', '.join(sorted(unknown_steps))}.",
                )
            )

    if current_state in {"contract_only", "producer_missing"} and "producer" not in chain_steps:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_producer_gap_missing",
                f"{closure_id} state={current_state!r} must name producer in missing_chain.",
            )
        )
    if (
        cell is not None
        and str(cell.get("p01_chain")) in {"bridge_missing", "implemented_but_not_orchestrated"}
        and "orchestration_bridge" not in chain_steps
    ):
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_bridge_gap_missing",
                f"{closure_id} p01_chain={cell.get('p01_chain')!r} must name orchestration_bridge in missing_chain.",
            )
        )
    if "semantic_test" not in chain_steps:
        issues.append(
            _issue(
                "cluster_ownership_open_cell_closure_semantic_gap_missing",
                f"{closure_id} closure must keep semantic_test in missing_chain until content-level adequacy is proven.",
            )
        )

    for text_field in (
        "owner",
        "producer_artifact",
        "persisted_artifact",
        "bridge_consumer",
        "surface",
        "semantic_test",
        "negative_test",
        "acceptance_signal",
        "next_action",
    ):
        if not str(closure[text_field]).strip():
            issues.append(
                _issue(
                    "cluster_ownership_open_cell_closure_text_field_missing",
                    f"{closure_id} closure field {text_field} must be populated.",
                )
            )


def _handshake_target_resolves(
    target: str,
    *,
    allowed_nodes: set[str],
    audiences: set[str],
) -> bool:
    if target in allowed_nodes:
        return True
    head = target.split(".", 1)[0]
    return target in audiences or head in audiences


def _validate_firewall_refs(
    cells: list[dict[str, Any]],
    registered_patterns: set[str],
    issues: list[dict[str, str]],
) -> None:
    for cell in cells:
        cell_id = f"{cell['cluster']}.{cell['axis']}"
        firewall = str(cell.get("firewall", ""))
        pattern_ids = set(re.findall(r"P\d{2}", firewall))
        if not pattern_ids and firewall != "N/A":
            issues.append(
                _issue(
                    "cluster_ownership_firewall_pattern_missing",
                    f"{cell_id} firewall={firewall!r} does not cite a P-pattern id.",
                )
            )
        missing = pattern_ids - registered_patterns
        if missing:
            issues.append(
                _issue(
                    "cluster_ownership_firewall_pattern_unregistered",
                    f"{cell_id} firewall cites unregistered patterns: {', '.join(sorted(missing))}.",
                )
            )


def _validate_architecture_core_assignments(
    payload: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    repo_root: Path,
    ratchet_states: set[str],
    cell_keys: set[tuple[str, str]],
) -> dict[str, Any]:
    core = payload.get("architecture_core")
    if not isinstance(core, dict):
        issues.append(
            _issue(
                "cluster_ownership_architecture_core_missing",
                "Map must define [architecture_core] for src/polisyos coverage.",
            )
        )
        return {}

    root_value = str(core.get("root", ""))
    if root_value != REQUIRED_ARCHITECTURE_CORE_ROOT.as_posix():
        issues.append(
            _issue(
                "cluster_ownership_architecture_core_root_invalid",
                f"architecture_core.root must be {REQUIRED_ARCHITECTURE_CORE_ROOT.as_posix()}.",
            )
        )

    package_groups = _list_of_dicts(core.get("package_group"))
    subpackage_groups = _list_of_dicts(core.get("subpackage_group"))
    if not package_groups:
        issues.append(
            _issue(
                "cluster_ownership_architecture_core_package_groups_missing",
                "architecture_core.package_group entries are required.",
            )
        )
        return {}

    package_paths = _validate_assignment_groups(
        package_groups,
        issues,
        repo_root=repo_root,
        ratchet_states=ratchet_states,
        cell_keys=cell_keys,
        group_kind="package",
    )
    subpackage_paths = _validate_assignment_groups(
        subpackage_groups,
        issues,
        repo_root=repo_root,
        ratchet_states=ratchet_states,
        cell_keys=cell_keys,
        group_kind="subpackage",
    )

    actual_packages = {
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / REQUIRED_ARCHITECTURE_CORE_ROOT).iterdir()
        if path.is_dir() and not path.name.startswith("__")
    }
    missing_packages = actual_packages - package_paths
    extra_packages = package_paths - actual_packages
    if missing_packages:
        issues.append(
            _issue(
                "cluster_ownership_architecture_core_package_missing",
                "Missing architecture-core package assignments: "
                + ", ".join(sorted(missing_packages)),
            )
        )
    if extra_packages:
        issues.append(
            _issue(
                "cluster_ownership_architecture_core_package_unknown",
                "Unknown architecture-core package assignments: "
                + ", ".join(sorted(extra_packages)),
            )
        )

    split_required = {str(package) for package in core.get("split_required_packages", [])}
    actual_package_names = {Path(path).name for path in actual_packages}
    unknown_split_required = split_required - actual_package_names
    if unknown_split_required:
        issues.append(
            _issue(
                "cluster_ownership_split_required_package_unknown",
                "split_required_packages names unknown packages: "
                + ", ".join(sorted(unknown_split_required)),
            )
        )

    package_mode_by_path = _coverage_mode_by_path(package_groups)
    for package in sorted(split_required & actual_package_names):
        package_path = REQUIRED_ARCHITECTURE_CORE_ROOT / package
        package_path_str = package_path.as_posix()
        mode = package_mode_by_path.get(package_path_str, "")
        if mode in {"root_package", "whole_package"}:
            issues.append(
                _issue(
                    "cluster_ownership_split_package_wholesale_assignment",
                    f"{package_path_str} is split-required but coverage_mode={mode!r}.",
                )
            )
        actual_subpackages = {
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / package_path).iterdir()
            if path.is_dir() and not path.name.startswith("__")
        }
        assigned_subpackages = {
            path for path in subpackage_paths if path.startswith(package_path_str + "/")
        }
        missing_subpackages = actual_subpackages - assigned_subpackages
        extra_subpackages = assigned_subpackages - actual_subpackages
        if missing_subpackages:
            issues.append(
                _issue(
                    "cluster_ownership_architecture_core_subpackage_missing",
                    f"{package_path_str} missing subpackage assignments: "
                    + ", ".join(sorted(missing_subpackages)),
                )
            )
        if extra_subpackages:
            issues.append(
                _issue(
                    "cluster_ownership_architecture_core_subpackage_unknown",
                    f"{package_path_str} has unknown subpackage assignments: "
                    + ", ".join(sorted(extra_subpackages)),
                )
            )
    return {
        "scope": str(core.get("scope", "")),
        "top_level_package_count": len(actual_packages),
        "assigned_top_level_package_count": len(package_paths),
        "split_required_package_count": len(split_required),
        "assigned_subpackage_count": len(subpackage_paths),
    }


def _validate_assignment_groups(
    groups: list[dict[str, Any]],
    issues: list[dict[str, str]],
    *,
    repo_root: Path,
    ratchet_states: set[str],
    cell_keys: set[tuple[str, str]],
    group_kind: str,
) -> set[str]:
    assigned_paths: set[str] = set()
    for index, group in enumerate(groups):
        group_id = f"architecture_core.{group_kind}_group[{index}]"
        missing = ARCHITECTURE_CORE_REQUIRED_FIELDS - set(group)
        if missing:
            issues.append(
                _issue(
                    "cluster_ownership_architecture_core_group_field_missing",
                    f"{group_id} omits fields: {', '.join(sorted(missing))}.",
                )
            )
            continue
        cell_ref = str(group["cell_ref"])
        if "." not in cell_ref:
            issues.append(
                _issue(
                    "cluster_ownership_architecture_core_cell_ref_invalid",
                    f"{group_id} cell_ref must be CLUSTER.axis.",
                )
            )
        else:
            cluster, axis = cell_ref.split(".", 1)
            if (cluster, axis) not in cell_keys:
                issues.append(
                    _issue(
                        "cluster_ownership_architecture_core_cell_ref_missing",
                        f"{group_id} references unknown cell_ref={cell_ref!r}.",
                    )
                )

        for state_field in ("ratchet_state", "p01_chain"):
            state = str(group[state_field])
            if state not in ratchet_states:
                issues.append(
                    _issue(
                        "cluster_ownership_architecture_core_unknown_state",
                        f"{group_id} {state_field}={state!r} is not a ratchet state.",
                    )
                )

        for text_field in ("coverage_mode", "gap", "action"):
            if not str(group[text_field]).strip():
                issues.append(
                    _issue(
                        "cluster_ownership_architecture_core_text_field_missing",
                        f"{group_id} {text_field} must be populated.",
                    )
                )

        paths = group["paths"]
        if not isinstance(paths, list) or not paths:
            issues.append(
                _issue(
                    "cluster_ownership_architecture_core_paths_missing",
                    f"{group_id} must name one or more paths.",
                )
            )
            continue
        for path_value in paths:
            path = Path(str(path_value))
            assigned_paths.add(path.as_posix())
            if not (repo_root / path).exists():
                issues.append(
                    _issue(
                        "cluster_ownership_architecture_core_path_missing",
                        f"{group_id} path does not exist: {path.as_posix()}.",
                    )
                )
    return assigned_paths


def _coverage_mode_by_path(groups: list[dict[str, Any]]) -> dict[str, str]:
    modes: dict[str, str] = {}
    for group in groups:
        mode = str(group.get("coverage_mode", ""))
        for path in group.get("paths", []) or []:
            modes[str(path)] = mode
    return modes


def _list_of_dicts(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _validate_inventory(
    inventory_path: Path,
    issues: list[dict[str, str]],
    *,
    map_path: Path,
    validator_path: Path,
) -> None:
    if not inventory_path.exists():
        issues.append(
            _issue(
                "cluster_ownership_inventory_missing",
                f"{inventory_path.as_posix()} does not exist.",
            )
        )
        return
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "cluster_ownership_inventory_invalid_json",
                f"Inventory JSON could not be parsed: {exc}.",
            )
        )
        return
    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, list):
        issues.append(
            _issue(
                "cluster_ownership_inventory_artifacts_missing",
                "Inventory must contain an artifacts list.",
            )
        )
        return
    matching = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("path") == map_path.as_posix()
    ]
    if not matching:
        issues.append(
            _issue(
                "cluster_ownership_inventory_ref_missing",
                f"Inventory must list {map_path.as_posix()}.",
            )
        )
        return
    artifact = matching[0]
    if artifact.get("validator") != validator_path.as_posix():
        issues.append(
            _issue(
                "cluster_ownership_inventory_validator_mismatch",
                f"Inventory validator for {map_path.as_posix()} must be {validator_path.as_posix()}.",
            )
        )


def _load_ratchet_states(path: Path, issues: list[dict[str, str]]) -> set[str]:
    if not path.exists():
        issues.append(
            _issue(
                "cluster_ownership_ratchet_report_missing",
                f"Capability ratchet report missing: {path}.",
            )
        )
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    base_points = payload.get("debt_algebra", {}).get("base_points", {})
    if not isinstance(base_points, dict):
        issues.append(
            _issue(
                "cluster_ownership_ratchet_vocabulary_missing",
                "Capability ratchet report has no debt_algebra.base_points vocabulary.",
            )
        )
        return set()
    return {str(state) for state in base_points}


def _load_failure_pattern_ids(path: Path, issues: list[dict[str, str]]) -> set[str]:
    if not path.exists():
        issues.append(
            _issue(
                "cluster_ownership_failure_pattern_register_missing",
                f"Failure pattern register missing: {path}.",
            )
        )
        return set()
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*(P\d{2})\s*\|", text, flags=re.MULTILINE))


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str) and item}


def _validation_result(
    *,
    map_path: Path,
    issues: list[dict[str, str]],
    cells: list[dict[str, Any]],
    architecture_core_summary: dict[str, Any] | None = None,
    handshake_summary: dict[str, Any] | None = None,
    open_cell_closure_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clusters = Counter(str(cell["cluster"]) for cell in cells)
    states = Counter(str(cell.get("ratchet_state", "")) for cell in cells)
    open_or_incomplete_count = sum(
        count for state, count in states.items() if state in OPEN_OR_INCOMPLETE_STATES
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": "pass" if not issues else "fail",
        "map_path": map_path.as_posix(),
        "summary": {
            "cell_count": len(cells),
            "cluster_counts": dict(sorted(clusters.items())),
            "state_counts": dict(sorted(states.items())),
            "open_or_incomplete_count": open_or_incomplete_count,
            "architecture_core": architecture_core_summary or {},
            "handshake_graph": handshake_summary or {},
            "open_cell_closure": open_cell_closure_summary or {},
        },
        "issues": issues,
    }


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


if __name__ == "__main__":
    sys.exit(main())
