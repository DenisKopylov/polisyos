"""Reconcile actual persisted WMR bodies before diagnosing scaffold time drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path.cwd().resolve()
CAS = ROOT / ".tmp/gy-s-composed-wmr-cas"
REPORT = ROOT / "architecture/policy_design_case/grounding_admission_contract.json"


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _nodes(value: object, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    found: dict[tuple[str, ...], object] = {path: {"type": type(value).__name__}}
    if isinstance(value, dict):
        found.update(
            {p: v for key, child in value.items() for p, v in _nodes(child, (*path, key)).items()}
        )
    elif isinstance(value, list):
        found.update(
            {
                p: v
                for index, child in enumerate(value)
                for p, v in _nodes(child, (*path, str(index))).items()
            }
        )
    else:
        found[path] = {"type": type(value).__name__, "value": value}
    return found


def _iterative_nodes(value: object) -> dict[tuple[str, ...], object]:
    pending: list[tuple[tuple[str, ...], object]] = [((), value)]
    found: dict[tuple[str, ...], object] = {}
    while pending:
        path, child = pending.pop()
        found[path] = {"type": type(child).__name__}
        if isinstance(child, dict):
            pending.extend(((*path, key), entry) for key, entry in child.items())
        elif isinstance(child, list):
            pending.extend(((*path, str(index)), entry) for index, entry in enumerate(child))
        else:
            found[path] = {"type": type(child).__name__, "value": child}
    return found


def main() -> None:
    """Inspect complete stored identities; optional runtime mode uses only real inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    manifests = set(CAS.rglob("*.manifest.json"))
    rg = shutil.which("rg")
    if rg is None:
        raise ValueError("independent_file_enumerator_unavailable")
    listing = subprocess.run(  # noqa: S603 - explicit read-only file inventory.
        [rg, "--files", "--hidden", "--no-ignore", "--glob", "*.manifest.json", str(CAS)],
        check=True,
        capture_output=True,
        text=True,
    )
    independent = {Path(name) for name in listing.stdout.splitlines()}
    if manifests != independent:
        raise ValueError("manifest_file_identity_sets_differ")
    report = json.loads(REPORT.read_bytes())
    logical_hash = report["reference"]["component_versions"]["WMR"]
    worlds: dict[str, dict[str, Any]] = {}
    for path in sorted(manifests):
        metadata = json.loads(path.read_bytes())
        if metadata["kind"] != "runtime.quality.world_model_record":
            continue
        blob = path.with_name(path.name.removesuffix(".manifest.json") + ".blob")
        raw = blob.read_bytes()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        if digest != metadata["artifact_id"]:
            raise ValueError(f"actual_blob_identity_invalid:{path}")
        body = json.loads(raw)
        if digest in worlds:
            raise ValueError("duplicate_world_artifact_identity")
        worlds[digest] = body
    selected = {key: body for key, body in worlds.items() if body["content_hash"] == logical_hash}
    if not selected:
        raise ValueError("declared_logical_world_version_unresolved")
    baseline_ref = min(selected)
    baseline = _nodes(selected[baseline_ref])
    rows = []
    difference_paths: set[tuple[str, ...]] = set()
    for artifact_ref, body in sorted(selected.items()):
        actual = _nodes(body)
        independently_walked = _iterative_nodes(body)
        if actual != independently_walked:
            raise ValueError("complete_body_leaf_identities_or_values_differ")
        missing, unexpected = set(baseline) - set(actual), set(actual) - set(baseline)
        changed = {path for path in set(actual) & set(baseline) if actual[path] != baseline[path]}
        difference_paths.update(missing | unexpected | changed)
        rows.append(
            {
                "identity": artifact_ref,
                "node_identity_hash": _hash(sorted(actual)),
                "changed": sorted(changed),
                "missing": sorted(missing),
                "unexpected": sorted(unexpected),
            }
        )
    evidence: dict[str, Any] = {
        "manifest_denominator": "all *.manifest.json under actual composed WMR CAS",
        "manifest_count": len(manifests),
        "manifest_identity_hash": _hash(sorted(str(path.relative_to(CAS)) for path in manifests)),
        "independent_manifest_identity_hash": _hash(
            sorted(str(path.relative_to(CAS)) for path in independent)
        ),
        "complete_wmr_artifact_count": len(worlds),
        "complete_wmr_artifact_identity_hash": _hash(sorted(worlds)),
        "selected_denominator": "all actual WMR artifacts with the report's logical content_hash",
        "logical_world_content_hash": logical_hash,
        "selected_artifact_count": len(selected),
        "selected_artifact_identity_hash": _hash(sorted(selected)),
        "every_selected_body_independently_reconciled": True,
        "complete_body_node_count": len(baseline),
        "body_node_identity_hashes": sorted({row["node_identity_hash"] for row in rows}),
        "changed_node_paths_across_complete_selected_set": sorted(difference_paths),
        "empty_containers_and_container_types_retained": True,
        "identity_omissions_or_additions": any(row["missing"] or row["unexpected"] for row in rows),
        "stored_report_reference": report["reference"],
        "writer_then_check_checkpoint": "930b8e10fb09332ed2a1cb9df38e3e1a5ad1460c",
    }
    if args.replay:
        from polisyos.core.artifacts import FileSystemCAS
        from polisyos.runtime.quality.grounding_calibration import build_refusal_reference_scaffold
        from polisyos.runtime.quality.world_model_record import load_world_model_record

        store = FileSystemCAS(CAS)
        reference_rows = []
        baseline_reference = None
        reference_differences: set[tuple[str, ...]] = set()
        edge_identity_hashes = set()
        expected_epochs = {
            "writer": report["reference"]["reference_epoch"],
            "check": "synthetic-refusal:05d21171df2dc2fa",
        }
        matches = {}
        for artifact_ref in sorted(selected):
            world = load_world_model_record(store, artifact_ref)
            reference = build_refusal_reference_scaffold(ROOT, world)
            snapshot = {
                "schema_version": reference.schema_version,
                "reference_epoch": reference.reference_epoch,
                "reference_hash": reference.reference_hash,
                "as_of": reference.as_of,
                "component_versions": dict(reference.component_versions),
                "essential_edges": {
                    json.dumps(key): edge.to_payload()
                    for key, edge in reference.essential_edges.items()
                },
            }
            flattened = _nodes(snapshot)
            if flattened != _iterative_nodes(snapshot):
                raise ValueError("reference_node_enumerations_disagree")
            if baseline_reference is None:
                baseline_reference = flattened
            reference_differences.update(set(baseline_reference) ^ set(flattened))
            reference_differences.update(
                key
                for key in set(flattened) & set(baseline_reference)
                if flattened[key] != baseline_reference[key]
            )
            if set(reference.essential_edges) != {
                edge.key for edge in reference.essential_edges.values()
            }:
                raise ValueError("reference_index_and_value_edge_identities_disagree")
            edge_identity_hashes.add(_hash(sorted(reference.essential_edges)))
            row = {
                "artifact_ref": artifact_ref,
                "created_at": world.created_at,
                "logical_world_content_hash": world.content_hash,
                "reference_epoch": reference.reference_epoch,
                "reference_hash": reference.reference_hash,
                "edge_count": len(reference.essential_edges),
            }
            reference_rows.append(row)
            for label, epoch in expected_epochs.items():
                if row["reference_epoch"] == epoch:
                    if label in matches:
                        raise ValueError("multiple_actual_sources_match_capture_epoch")
                    matches[label] = row
        evidence["actual_owner_replay_count"] = len(reference_rows)
        evidence["actual_owner_input_identity_hash"] = _hash(
            sorted(row["artifact_ref"] for row in reference_rows)
        )
        evidence["actual_owner_reference_identity_hash"] = _hash(
            sorted(row["reference_hash"] for row in reference_rows)
        )
        evidence["actual_owner_reference_node_count"] = len(baseline_reference or {})
        evidence["actual_owner_reference_changed_paths"] = sorted(reference_differences)
        evidence["actual_owner_edge_identity_hashes"] = sorted(edge_identity_hashes)
        evidence["actual_owner_edge_counts"] = sorted({row["edge_count"] for row in reference_rows})
        evidence["actual_source_matches_to_two_captures"] = matches
        if set(matches) != set(expected_epochs):
            raise ValueError("actual_sources_for_both_report_epochs_not_established")
    sys.stdout.write(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
