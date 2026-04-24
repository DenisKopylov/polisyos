#!/usr/bin/env python3
"""
Provenance visualization / validation utility.

Supports:
- Core Provenance graph format (ProvenanceCoreGraph.to_dict())
- W3C PROV-JSON format
- Loading from audit package (.polisyos-audit.tar.gz)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.audit.prov_json import prov_json_to_dot


def _load_from_cas(artifact_id: str, cas_root: Path) -> dict[str, Any]:
    store = FileSystemCAS(cas_root)
    payload = store.get_bytes(ArtifactID.model_validate(artifact_id))
    return json.loads(payload.decode("utf-8"))


def _load_from_package(package: Path) -> dict[str, Any]:
    if package.is_dir():
        path = package / "provenance" / "prov.json"
        return json.loads(path.read_text("utf-8"))

    with tarfile.open(package, "r:*") as tar:
        member = tar.getmember("provenance/prov.json")
        handle = tar.extractfile(member)
        if handle is None:
            raise FileNotFoundError("provenance/prov.json not found in package")
        with handle:
            return json.loads(handle.read().decode("utf-8"))


def detect_format(payload: dict[str, Any], requested: str) -> str:
    if requested != "auto":
        return requested
    if isinstance(payload.get("prefix"), dict) and isinstance(payload.get("entity"), dict):
        return "prov-json"
    if {"entities", "activities", "agents", "edges"}.issubset(payload.keys()):
        return "core-graph"
    raise ValueError("Could not auto-detect provenance input format")


def load_provenance_payload(
    *,
    source: str | None,
    cas_root: Path | None,
    from_package: Path | None,
) -> dict[str, Any]:
    if from_package is not None:
        return _load_from_package(from_package)
    if source is None:
        raise ValueError("source is required unless --from-package is used")

    source_path = Path(source)
    if source_path.exists():
        data = json.loads(source_path.read_text("utf-8"))
        if "provenance_ref" in data:
            provenance_ref = data.get("provenance_ref")
            if provenance_ref is None:
                raise ValueError("EvidenceBundle has no provenance_ref")
            artifact_id = provenance_ref["artifact_id"]
            if cas_root is None:
                raise ValueError("--cas-root required to resolve provenance_ref")
            return _load_from_cas(artifact_id, cas_root)
        return data

    if cas_root is not None:
        return _load_from_cas(source, cas_root)

    raise FileNotFoundError(f"Source not found: {source}")


def verify_core_graph(graph: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    entity_ids = {e["entity_id"] for e in graph.get("entities", [])}
    activity_ids = {a["activity_id"] for a in graph.get("activities", [])}
    agent_ids = {g["agent_id"] for g in graph.get("agents", [])}
    all_node_ids = entity_ids | activity_ids | agent_ids

    derivation_edges: list[tuple[str, str]] = []
    for edge in graph.get("edges", []):
        source_id = edge["source_id"]
        target_id = edge["target_id"]
        if source_id not in all_node_ids:
            issues.append(f"DANGLING: Edge source '{source_id}' not found")
        if target_id not in all_node_ids:
            issues.append(f"DANGLING: Edge target '{target_id}' not found")
        if edge.get("relation") == "wasDerivedFrom":
            derivation_edges.append((source_id, target_id))
    if derivation_edges and _has_cycle(derivation_edges):
        issues.append("CYCLE: Circular dependency detected in wasDerivedFrom")
    return issues


def verify_prov_json(prov_json: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(prov_json.get("prefix"), dict):
        issues.append("INVALID: missing prefix")
    entities = prov_json.get("entity", {})
    if not isinstance(entities, dict):
        issues.append("INVALID: entity section is missing or invalid")
        return issues
    deriv = prov_json.get("wasDerivedFrom", {})
    edges: list[tuple[str, str]] = []
    if isinstance(deriv, dict):
        for item in deriv.values():
            if not isinstance(item, dict):
                continue
            src = item.get("prov:generatedEntity")
            tgt = item.get("prov:usedEntity")
            if isinstance(src, str) and isinstance(tgt, str):
                edges.append((src, tgt))
    if edges and _has_cycle(edges):
        issues.append("CYCLE: Circular dependency detected in wasDerivedFrom")
    return issues


def export_core_to_dot(graph: dict[str, Any]) -> str:
    lines = [
        "digraph Provenance {",
        "    rankdir=BT;",
        '    node [fontname="Helvetica"];',
        '    edge [fontname="Helvetica", fontsize=10];',
        "",
    ]
    for entity in graph.get("entities", []):
        eid = str(entity["entity_id"]).replace("-", "_")
        label = str(entity.get("label", entity["entity_id"]))[:30]
        lines.append(f'    {eid} [label="{label}", shape=box, style=filled, fillcolor=lightblue];')
    for activity in graph.get("activities", []):
        aid = str(activity["activity_id"]).replace("-", "_")
        label = str(activity.get("label", activity["activity_id"]))[:30]
        lines.append(
            f'    {aid} [label="{label}", shape=ellipse, style=filled, fillcolor=lightyellow];'
        )
    for agent in graph.get("agents", []):
        gid = str(agent["agent_id"]).replace("-", "_")
        label = str(agent.get("label", agent["agent_id"]))[:30]
        lines.append(
            f'    {gid} [label="{label}", shape=diamond, style=filled, fillcolor=lightgreen];'
        )
    for edge in graph.get("edges", []):
        src = str(edge["source_id"]).replace("-", "_")
        tgt = str(edge["target_id"]).replace("-", "_")
        rel = str(edge.get("relation", ""))
        lines.append(f'    {src} -> {tgt} [label="{rel}"];')
    lines.append("}")
    return "\n".join(lines)


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for src, tgt in edges:
        graph.setdefault(src, []).append(tgt)
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for nxt in graph.get(node, []):
            if nxt not in visited:
                if dfs(nxt):
                    return True
            elif nxt in stack:
                return True
        stack.remove(node)
        return False

    for node in graph:
        if node not in visited and dfs(node):
            return True
    return False


def render_svg(dot_content: str, output_path: Path) -> None:
    if shutil.which("dot") is None:
        raise RuntimeError("Graphviz 'dot' binary is not available")
    dot_path = output_path.with_suffix(".dot")
    dot_path.write_text(dot_content, encoding="utf-8")
    subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(output_path)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualize and verify provenance graphs")
    parser.add_argument(
        "source",
        nargs="?",
        help="Path to provenance JSON / EvidenceBundle / CAS artifact id",
    )
    parser.add_argument(
        "--from-package",
        type=Path,
        help="Load provenance from audit package directory or .tar.gz",
    )
    parser.add_argument(
        "--input-format",
        choices=["auto", "core-graph", "prov-json"],
        default="auto",
        help="Input format auto-detection (default: auto)",
    )
    parser.add_argument(
        "--format",
        choices=["dot", "json", "svg"],
        default="dot",
        help="Output format (default: dot)",
    )
    parser.add_argument("--cas-root", type=Path, help="CAS root for artifact resolution")
    parser.add_argument("--verify", action="store_true", help="Run integrity checks")
    parser.add_argument("--output", "-o", type=Path, help="Output file (default: stdout)")
    args = parser.parse_args()

    try:
        payload = load_provenance_payload(
            source=args.source,
            cas_root=args.cas_root,
            from_package=args.from_package,
        )
        input_format = detect_format(payload, args.input_format)
    except Exception as exc:
        print(f"ERROR: Failed to load payload: {exc}", file=sys.stderr)
        return 1

    if args.verify:
        issues = (
            verify_prov_json(payload) if input_format == "prov-json" else verify_core_graph(payload)
        )
        if issues:
            print("VERIFICATION FAILED", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        print("VERIFICATION PASSED", file=sys.stderr)

    if args.format == "json":
        output = json.dumps(payload, indent=2, sort_keys=True)
    else:
        if input_format == "prov-json":
            dot = prov_json_to_dot(payload)
        else:
            dot = export_core_to_dot(payload)

        if args.format == "dot":
            output = dot
        else:
            if args.output is None:
                print("ERROR: --output is required for --format svg", file=sys.stderr)
                return 2
            try:
                render_svg(dot, args.output)
            except Exception as exc:
                print(f"ERROR: Failed to render SVG: {exc}", file=sys.stderr)
                return 1
            print(f"Written to {args.output}", file=sys.stderr)
            return 0

    if args.output:
        args.output.write_text(output, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
