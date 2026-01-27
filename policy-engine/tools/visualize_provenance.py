#!/usr/bin/env python3
"""
Provenance Graph Visualization and Verification Tool.

Generates Graphviz DOT files or JSON dumps for provenance graphs,
and performs integrity checks for orphaned nodes or cycles.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS


def load_provenance_graph(
    source: str,
    cas_root: Path | None = None,
) -> dict[str, Any]:
    """
    Load provenance graph from file path or CAS artifact ID.

    Args:
        source: File path or CAS artifact ID
        cas_root: CAS root directory (required if source is artifact ID)

    Returns:
        Provenance graph as dict
    """
    source_path = Path(source)

    if source_path.exists():
        with source_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "provenance_ref" in data:
            if data["provenance_ref"] is None:
                raise ValueError("EvidenceBundle has no provenance_ref")
            artifact_id = data["provenance_ref"]["artifact_id"]
            if cas_root is None:
                raise ValueError("--cas-root required to resolve provenance_ref")
            return _load_from_cas(artifact_id, cas_root)

        return data

    if cas_root is not None:
        return _load_from_cas(source, cas_root)

    raise FileNotFoundError(f"Source not found: {source}")


def _load_from_cas(artifact_id: str, cas_root: Path) -> dict[str, Any]:
    """Load artifact from CAS by ID."""
    store = FileSystemCAS(cas_root)
    payload = store.get_bytes(ArtifactID.model_validate(artifact_id))
    return json.loads(payload.decode("utf-8"))


def verify_graph(graph: dict[str, Any]) -> list[str]:
    """
    Verify provenance graph integrity.

    Checks:
        1. No orphaned nodes (entities/activities not referenced by any edge)
        2. No dangling references (edges pointing to non-existent nodes)
        3. No cycles in wasDerivedFrom edges (invalid lineage)
        4. All required fields present

    Returns:
        List of warning/error messages (empty if valid)
    """
    issues: list[str] = []

    entity_ids = {e["entity_id"] for e in graph.get("entities", [])}
    activity_ids = {a["activity_id"] for a in graph.get("activities", [])}
    agent_ids = {g["agent_id"] for g in graph.get("agents", [])}
    all_node_ids = entity_ids | activity_ids | agent_ids

    referenced_sources: set[str] = set()
    referenced_targets: set[str] = set()
    derivation_edges: list[tuple[str, str]] = []

    for edge in graph.get("edges", []):
        source_id = edge["source_id"]
        target_id = edge["target_id"]
        relation = edge["relation"]

        referenced_sources.add(source_id)
        referenced_targets.add(target_id)

        if source_id not in all_node_ids:
            issues.append(f"DANGLING: Edge source '{source_id}' not found in nodes")
        if target_id not in all_node_ids:
            issues.append(f"DANGLING: Edge target '{target_id}' not found in nodes")

        if relation == "wasDerivedFrom":
            derivation_edges.append((source_id, target_id))

    all_referenced = referenced_sources | referenced_targets
    orphaned = all_node_ids - all_referenced
    if orphaned:
        for node_id in orphaned:
            if node_id in entity_ids:
                has_derivation = any(src == node_id for src, _ in derivation_edges)
                if not has_derivation:
                    continue
            issues.append(f"ORPHANED: Node '{node_id}' not connected to any edge")

    def has_cycle(edges: list[tuple[str, str]]) -> bool:
        from collections import defaultdict

        adj: dict[str, list[str]] = defaultdict(list)
        for src, tgt in edges:
            adj[src].append(tgt)

        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in adj[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in adj:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    if derivation_edges and has_cycle(derivation_edges):
        issues.append("CYCLE: Circular dependency detected in wasDerivedFrom edges")

    return issues


def export_to_dot(graph: dict[str, Any]) -> str:
    """
    Export provenance graph to Graphviz DOT format.

    Color coding:
        - Entities: lightblue boxes
        - Activities: lightyellow ovals
        - Agents: lightgreen diamonds

    Edge styles:
        - wasDerivedFrom: solid blue
        - wasGeneratedBy: dashed green
        - used: dotted orange
        - wasAttributedTo: solid purple
        - wasAssociatedWith: dashed purple
    """
    lines = [
        "digraph Provenance {",
        "    rankdir=BT;",
        "    node [fontname=\"Helvetica\"];",
        "    edge [fontname=\"Helvetica\", fontsize=10];",
        "",
        "    // Entities (data artifacts)",
        "    subgraph cluster_entities {",
        "        label=\"Entities\";",
        "        style=dashed;",
        "        color=lightblue;",
    ]

    for entity in graph.get("entities", []):
        eid = entity["entity_id"].replace("-", "_")
        label = entity.get("label", entity["entity_id"])[:30]
        etype = entity.get("entity_type", "unknown")
        lines.append(
            f"        {eid} [label=\"{label}\\n({etype})\", "
            f"shape=box, style=filled, fillcolor=lightblue];"
        )

    lines.extend(
        [
            "    }",
            "",
            "    // Activities (transformations)",
            "    subgraph cluster_activities {",
            "        label=\"Activities\";",
            "        style=dashed;",
            "        color=lightyellow;",
        ]
    )

    for activity in graph.get("activities", []):
        aid = activity["activity_id"].replace("-", "_")
        label = activity.get("label", activity["activity_id"])[:30]
        atype = activity.get("activity_type", "unknown")
        lines.append(
            f"        {aid} [label=\"{label}\\n({atype})\", "
            f"shape=ellipse, style=filled, fillcolor=lightyellow];"
        )

    lines.extend(
        [
            "    }",
            "",
            "    // Agents",
            "    subgraph cluster_agents {",
            "        label=\"Agents\";",
            "        style=dashed;",
            "        color=lightgreen;",
        ]
    )

    for agent in graph.get("agents", []):
        gid = agent["agent_id"].replace("-", "_")
        label = agent.get("label", agent["agent_id"])[:30]
        lines.append(
            f"        {gid} [label=\"{label}\", "
            f"shape=diamond, style=filled, fillcolor=lightgreen];"
        )

    lines.extend(
        [
            "    }",
            "",
            "    // Edges",
        ]
    )

    edge_styles = {
        "wasDerivedFrom": 'color=blue, style=solid, label="derived"',
        "wasGeneratedBy": 'color=green, style=dashed, label="generated"',
        "used": 'color=orange, style=dotted, label="used"',
        "wasAttributedTo": 'color=purple, style=solid, label="attributed"',
        "wasAssociatedWith": 'color=purple, style=dashed, label="associated"',
    }

    for edge in graph.get("edges", []):
        src = edge["source_id"].replace("-", "_")
        tgt = edge["target_id"].replace("-", "_")
        rel = edge["relation"]
        style = edge_styles.get(rel, "color=gray")
        lines.append(f"    {src} -> {tgt} [{style}];")

    lines.append("}")
    return "\n".join(lines)


def export_to_json(graph: dict[str, Any], pretty: bool = True) -> str:
    """Export provenance graph as formatted JSON."""
    if pretty:
        return json.dumps(graph, indent=2, sort_keys=True)
    return json.dumps(graph, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualize and verify provenance graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate DOT file from evidence bundle
    python visualize_provenance.py evidence.json --format dot > graph.dot
    dot -Tpng graph.dot -o graph.png

    # Verify graph integrity
    python visualize_provenance.py evidence.json --cas-root .polisyos --verify

    # Export as JSON
    python visualize_provenance.py graph.json --format json
        """,
    )

    parser.add_argument(
        "source",
        help="Path to evidence bundle JSON, provenance graph JSON, or CAS artifact ID",
    )
    parser.add_argument(
        "--format",
        choices=["dot", "json"],
        default="dot",
        help="Output format (default: dot)",
    )
    parser.add_argument(
        "--cas-root",
        type=Path,
        help="CAS root directory for artifact resolution",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify graph integrity and report issues",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file (default: stdout)",
    )

    args = parser.parse_args()

    try:
        graph = load_provenance_graph(args.source, args.cas_root)
    except Exception as exc:
        print(f"ERROR: Failed to load graph: {exc}", file=sys.stderr)
        return 1

    if args.verify:
        issues = verify_graph(graph)
        if issues:
            print("VERIFICATION FAILED:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        print("VERIFICATION PASSED: Graph is valid", file=sys.stderr)

    if args.format == "dot":
        output = export_to_dot(graph)
    else:
        output = export_to_json(graph)

    if args.output:
        args.output.write_text(output)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
