#!/usr/bin/env python3
"""Export Policy Evidence Capability Index lineage as PROV-O Turtle."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation.inspect_policy_evidence_capability_index import (
    active_capabilities,
    load_capability_index_snapshot,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

if TYPE_CHECKING:
    from collections.abc import Sequence

SCHEMA_VERSION = "policyos.capability_index.prov_export.v1"
_URI_SAFE_RE = re.compile(r"[^A-Za-z0-9._:-]+")


def build_prov_export(capability_index_path: str | Path) -> str:
    """Build a compact PROV-O Turtle lineage projection."""

    snapshot = load_capability_index_snapshot(capability_index_path)
    metadata = snapshot["metadata"]
    release_ref = str(metadata.get("release_ref") or "policyos-capability-index-v1")
    compiler_version = str(metadata.get("compiler_version") or "unknown")
    index_uri = _uri("capability-index", release_ref)
    activity_uri = _uri("activity", f"compile:{release_ref}")
    agent_uri = _uri("agent", "team-runtime-quality")
    lines = [
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix policyos: <https://policyos.local/ns#> .",
        "",
        f"{index_uri} a prov:Entity ;",
        f'  dct:identifier "{_literal(release_ref)}" ;',
        f'  policyos:schemaVersion "{SCHEMA_VERSION}" ;',
        f"  prov:wasGeneratedBy {activity_uri} .",
        "",
        f"{activity_uri} a prov:Activity ;",
        '  dct:identifier "compile-policy-evidence-capability-index" ;',
        f'  policyos:compilerVersion "{_literal(compiler_version)}" ;',
        f"  prov:wasAssociatedWith {agent_uri} .",
        "",
        f"{agent_uri} a prov:Agent ;",
        '  dct:identifier "team-runtime-quality" .',
        "",
    ]
    for capability in active_capabilities(snapshot):
        capability_uri = _uri("capability", capability.capability_id)
        lines.extend(
            [
                f"{capability_uri} a prov:Entity ;",
                f'  dct:identifier "{_literal(capability.capability_id)}" ;',
                f'  dct:title "{_literal(capability.construct_id)}" ;',
                f"  prov:wasDerivedFrom {index_uri} ;",
                f"  prov:wasGeneratedBy {activity_uri} .",
                "",
            ]
        )
        for asset in capability.source_assets:
            asset_uri = _uri("source-asset", asset.ref)
            lines.extend(
                [
                    f"{asset_uri} a prov:Entity ;",
                    f'  dct:identifier "{_literal(asset.ref)}" ;',
                    f'  policyos:sourceLayer "{_literal(asset.source_layer)}" .',
                    "",
                    f"{capability_uri} prov:wasDerivedFrom {asset_uri} .",
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def validate_prov_turtle(payload: str) -> dict[str, object]:
    """Validate the minimal PROV-O Turtle expectations used by Phase 7."""

    issues: list[dict[str, str]] = []
    rdf_graph_triple_count = 0
    prov_entity_triple_count = 0
    prov_activity_triple_count = 0
    prov_agent_triple_count = 0
    required = {
        "prov:Entity": "prov_entity_triples_missing",
        "prov:Activity": "prov_activity_triple_missing",
        "prov:Agent": "prov_agent_triple_missing",
        "prov:wasDerivedFrom": "prov_lineage_missing",
        "prov:wasGeneratedBy": "prov_generation_missing",
        "prov:wasAssociatedWith": "prov_agent_association_missing",
    }
    for marker, code in required.items():
        if marker not in payload:
            issues.append(
                {
                    "code": code,
                    "severity": "fail",
                    "message": f"PROV-O Turtle is missing {marker}.",
                }
            )
    if "@prefix prov:" not in payload:
        issues.append(
            {
                "code": "prov_prefix_missing",
                "severity": "fail",
                "message": "PROV-O Turtle must declare the prov prefix.",
            }
        )
    try:
        graph = Graph()
        graph.parse(data=payload, format="turtle")
        prov_ns = Namespace("http://www.w3.org/ns/prov#")
        rdf_graph_triple_count = len(graph)
        prov_entity_triple_count = sum(
            1 for _subject in graph.subjects(RDF.type, prov_ns.Entity)
        )
        prov_activity_triple_count = sum(
            1 for _subject in graph.subjects(RDF.type, prov_ns.Activity)
        )
        prov_agent_triple_count = sum(
            1 for _subject in graph.subjects(RDF.type, prov_ns.Agent)
        )
        if prov_entity_triple_count < 1:
            issues.append(
                {
                    "code": "prov_entity_rdf_triples_missing",
                    "severity": "fail",
                    "message": "Parsed Turtle must contain prov:Entity triples.",
                }
            )
        if prov_activity_triple_count < 1:
            issues.append(
                {
                    "code": "prov_activity_rdf_triple_missing",
                    "severity": "fail",
                    "message": "Parsed Turtle must contain a prov:Activity triple.",
                }
            )
        if prov_agent_triple_count < 1:
            issues.append(
                {
                    "code": "prov_agent_rdf_triple_missing",
                    "severity": "fail",
                    "message": "Parsed Turtle must contain a prov:Agent triple.",
                }
            )
    except Exception as exc:
        issues.append(
            {
                "code": "prov_turtle_parse_error",
                "severity": "fail",
                "message": "PROV-O export must parse as Turtle RDF.",
                "error": str(exc),
            }
        )
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "rdf_graph_triple_count": rdf_graph_triple_count,
        "prov_entity_triple_count": prov_entity_triple_count,
        "prov_activity_triple_count": prov_activity_triple_count,
        "prov_agent_triple_count": prov_agent_triple_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    ttl = build_prov_export(args.capability_index)
    validation = validate_prov_turtle(ttl)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(ttl, encoding="utf-8")
    sys.stdout.write(f'{{"status": "{validation["status"]}", "output": "{args.output}"}}\n')
    return 0 if validation["status"] == "pass" else 1


def _uri(kind: str, value: str) -> str:
    return f"<urn:policyos:{kind}:{_URI_SAFE_RE.sub('_', value).strip('_')}>"


def _literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
