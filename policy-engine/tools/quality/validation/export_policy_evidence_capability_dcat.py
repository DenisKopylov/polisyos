#!/usr/bin/env python3
"""Export the Policy Evidence Capability Index as DCAT-compatible JSON-LD."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation.inspect_policy_evidence_capability_index import (
    active_capabilities,
    load_capability_index_snapshot,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.runtime.quality.capability_index import EvidenceCapability

SCHEMA_VERSION = "policyos.capability_index.dcat_export.v1"


def build_dcat_export(capability_index_path: str | Path) -> dict[str, Any]:
    """Build a DCAT 3 compatible JSON-LD projection from a capability index."""

    snapshot = load_capability_index_snapshot(capability_index_path)
    metadata = snapshot["metadata"]
    release_ref = str(metadata.get("release_ref") or "policyos-capability-index-v1")
    capabilities = active_capabilities(snapshot)
    return {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "prov": "http://www.w3.org/ns/prov#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "policyos": "https://policyos.local/ns#",
        },
        "@id": f"urn:policyos:capability-index:{_slug(release_ref)}",
        "@type": "dcat:Catalog",
        "dct:identifier": release_ref,
        "dct:title": "PolicyOS Policy Evidence Capability Index",
        "dct:description": (
            "Release-time compiled, authority-scoped capability graph over "
            "producer-backed policy evidence capabilities."
        ),
        "dct:conformsTo": [
            "https://www.w3.org/TR/vocab-dcat-3/",
            SCHEMA_VERSION,
        ],
        "policyos:authorityBoundary": {
            "authoritative_for": ["external_metadata_interoperability"],
            "may_not_use_for": ["claim_evidence_satisfaction", "scenario_family_authority"],
        },
        "dcat:dataset": [_dataset(capability) for capability in capabilities],
    }


def validate_dcat_export(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the local DCAT 3 JSON-LD expectations used by Phase 7."""

    issues: list[dict[str, Any]] = []
    rdf_graph_triple_count = 0
    dcat_dataset_triple_count = 0
    context = payload.get("@context")
    if not isinstance(context, Mapping) or "dcat" not in context or "dct" not in context:
        issues.append(_issue("dcat_context_missing", "DCAT JSON-LD context is incomplete."))
    if payload.get("@type") != "dcat:Catalog":
        issues.append(_issue("dcat_catalog_type_missing", "Root node must be dcat:Catalog."))
    datasets = payload.get("dcat:dataset")
    if not isinstance(datasets, list) or not datasets:
        issues.append(_issue("dcat_dataset_missing", "Catalog must expose datasets."))
        datasets = []
    for index, dataset in enumerate(datasets):
        if not isinstance(dataset, Mapping):
            issues.append(_issue("dcat_dataset_invalid", "Dataset must be an object.", index=index))
            continue
        for key in ("@id", "@type", "dct:identifier", "dct:title", "dcat:distribution"):
            if not dataset.get(key):
                issues.append(
                    _issue(
                        "dcat_dataset_field_missing",
                        f"Dataset is missing {key}.",
                        index=index,
                        field=key,
                    )
                )
        if dataset.get("@type") != "dcat:Dataset":
            issues.append(
                _issue(
                    "dcat_dataset_type_invalid",
                    "Capability dataset nodes must be dcat:Dataset.",
                    index=index,
                )
            )
    try:
        graph = Graph()
        graph.parse(data=json.dumps(dict(payload)), format="json-ld")
        dcat_ns = Namespace("http://www.w3.org/ns/dcat#")
        rdf_graph_triple_count = len(graph)
        dcat_dataset_triple_count = sum(
            1 for _subject in graph.subjects(RDF.type, dcat_ns.Dataset)
        )
        catalog_count = sum(1 for _subject in graph.subjects(RDF.type, dcat_ns.Catalog))
        if catalog_count != 1:
            issues.append(
                _issue(
                    "dcat_catalog_rdf_type_invalid",
                    "Parsed JSON-LD must contain exactly one dcat:Catalog node.",
                    observed_count=catalog_count,
                )
            )
        if dcat_dataset_triple_count != len(datasets):
            issues.append(
                _issue(
                    "dcat_dataset_rdf_count_mismatch",
                    "Parsed JSON-LD dataset count must match the catalog payload.",
                    observed_count=dcat_dataset_triple_count,
                    expected_count=len(datasets),
                )
            )
    except Exception as exc:  # pragma: no cover - exercised by malformed payloads
        issues.append(
            _issue(
                "dcat_jsonld_parse_error",
                "DCAT export must parse as JSON-LD RDF.",
                error=str(exc),
            )
        )
    return {
        "status": "fail" if issues else "pass",
        "issues": issues,
        "rdf_graph_triple_count": rdf_graph_triple_count,
        "dcat_dataset_triple_count": dcat_dataset_triple_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = build_dcat_export(args.capability_index)
    validation = validate_dcat_export(payload)
    payload["policyos:validation"] = validation
    atomic_write_json(args.output, payload)
    json.dump({"status": validation["status"], "output": str(args.output)}, sys.stdout)
    sys.stdout.write("\n")
    return 0 if validation["status"] == "pass" else 1


def _dataset(capability: EvidenceCapability) -> dict[str, Any]:
    source_assets = capability.source_assets or ()
    return {
        "@id": f"urn:policyos:{_slug(capability.capability_id)}",
        "@type": "dcat:Dataset",
        "dct:identifier": capability.capability_id,
        "dct:title": capability.construct_id,
        "dct:description": _capability_description(capability),
        "dct:type": list(capability.modality),
        "dct:spatial": capability.scope.geography,
        "dct:temporal": {
            "dcat:startDate": capability.scope.time_start,
            "dcat:endDate": capability.scope.time_end,
        },
        "dct:conformsTo": capability.schema_version,
        "dct:rights": capability.rights_envelope.public_export_allowed,
        "dct:license": capability.rights_envelope.license,
        "prov:wasDerivedFrom": list(capability.lineage_refs),
        "policyos:construct": capability.construct_id,
        "policyos:evidenceMode": capability.evidence_mode,
        "policyos:authorityEnvelope": capability.authority_envelope.model_dump(mode="json"),
        "policyos:compatibilityOnly": capability.compatibility_only,
        "dcat:distribution": [
            {
                "@id": f"urn:policyos:{_slug(capability.capability_id)}:asset:{index}",
                "@type": "dcat:Distribution",
                "dct:identifier": asset.ref,
                "dct:title": asset.role,
                "dct:format": asset.asset_type,
                "dcat:accessURL": asset.path or asset.ref,
                "policyos:sourceLayer": asset.source_layer,
                "policyos:compatibilityOnly": asset.compatibility_only,
            }
            for index, asset in enumerate(source_assets, start=1)
        ]
        or [
            {
                "@id": f"urn:policyos:{_slug(capability.capability_id)}:asset:none",
                "@type": "dcat:Distribution",
                "dct:identifier": f"{capability.capability_id}:no_source_asset_recorded",
                "dct:title": "No source asset recorded",
                "dct:format": "capability_metadata_only",
                "dcat:accessURL": capability.capability_id,
            }
        ],
    }


def _capability_description(capability: EvidenceCapability) -> str:
    return (
        f"{capability.evidence_mode} capability for construct "
        f"{capability.construct_id} in {capability.scope.geography}; production "
        f"authority is {capability.authority_envelope.production}."
    )


def _issue(code: str, message: str, **extra: object) -> dict[str, Any]:
    return {"code": code, "severity": "fail", "message": message, **extra}


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
