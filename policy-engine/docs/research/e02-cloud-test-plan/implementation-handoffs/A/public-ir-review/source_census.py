"""Reproduce the Public IR owner/ref and serialized-source census.

The script consumes an explicit JSON manifest of immutable Git refs. It does not
select refs by glob or infer ratification from keywords. Each listed ref must
resolve to its declared commit. No product module is imported or executed.

Example manifest shape (one entry per reviewed ref)::

    {"refs": [{"ref": "origin/codex/e02-E-example-20261006",
               "commit": "<full commit sha>", "tree": "<full tree sha>"}]}

Run this only with an explicit exact-ref manifest and when local source-census
resources are available. Large compressed invocation payloads are inventoried
but deliberately left opaque above the bounded decompression threshold.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import subprocess
import zipfile
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any


STRUCTURED_SUFFIXES = {
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".txt",
    ".csv",
    ".blob",
    ".typed",
    ".fixture",
    ".zip",
    ".whl",
    ".duckdb",
    ".sqlite",
    ".sqlite-wal",
}

SERIALIZED_SUFFIXES = STRUCTURED_SUFFIXES | {
    ".cfg",
    ".docx",
    ".example",
    ".gz",
    ".ini",
    ".jsonc",
    ".log",
    ".md",
    ".mdc",
    ".patch",
    ".pkl",
    ".reproducible",
    ".retired",
    ".sql",
    ".stderr",
    ".stdout",
    ".toml",
    ".tsv",
    ".xml",
}

TEXT_SCAN_SUFFIXES = SERIALIZED_SUFFIXES - {
    ".blob",
    ".docx",
    ".duckdb",
    ".fixture",
    ".gz",
    ".pkl",
    ".sqlite",
    ".sqlite-wal",
    ".whl",
    ".zip",
}

ARCHIVE_SUFFIXES = {".docx", ".whl", ".zip"}
OPAQUE_SERIALIZED_SUFFIXES = {".blob", ".duckdb", ".pkl", ".sqlite", ".sqlite-wal"}

OWNER_PATHS = (
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/semantic-decisions.md",
    "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json",
    "policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/DECISION_RECORDS.md",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/RESIDUAL_LEDGER.md",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/CROSSWALK.md",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/OPEN_PREMISES.md",
    "policy-engine/docs/research/development-programs/2026-09-30-post-e02/decisions.md",
    "policy-engine/docs/research/development-programs/2026-09-30-post-e02/decisions.json",
    "policy-engine/docs/research/development-programs/2026-09-30-post-e02/source_disposition.json",
    "policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md",
)


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    """Run a read-only Git command and return its stdout."""

    return subprocess.check_output(["git", *args], input=input_bytes)


def tree_entries(commit: str) -> list[tuple[str, str, str]]:
    """Return path, object type, and object ID for every recursive tree entry."""

    raw = git("ls-tree", "-r", "-z", "--full-tree", commit)
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        _mode, object_type, object_id = metadata.decode("ascii").split(" ")
        entries.append(
            (
                raw_path.decode("utf-8", errors="surrogateescape"),
                object_type,
                object_id,
            )
        )
    return entries


def blob_batch_bytes(object_ids: set[str]) -> dict[str, bytes]:
    """Read unique Git blobs in bounded batches, preserving each object identity."""

    result: dict[str, bytes] = {}
    ordered = sorted(object_ids)
    for offset in range(0, len(ordered), 64):
        batch = ordered[offset : offset + 64]
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            input=b"".join(object_id.encode("ascii") + b"\n" for object_id in batch),
            stdout=subprocess.PIPE,
            check=True,
        )
        output = proc.stdout
        cursor = 0
        for expected_id in batch:
            header_end = output.find(b"\n", cursor)
            if header_end < 0:
                raise RuntimeError("truncated git cat-file batch header")
            object_id, object_type, size_text = output[cursor:header_end].decode("ascii").split(" ")
            if object_id != expected_id or object_type != "blob":
                raise RuntimeError(f"unexpected Git object identity: {object_id} {object_type}")
            size = int(size_text)
            start = header_end + 1
            body = output[start : start + size]
            if len(body) != size or output[start + size : start + size + 1] != b"\n":
                raise RuntimeError(f"truncated Git blob body: {object_id}")
            result[object_id] = body
            cursor = start + size + 1
    return result


def blob_sizes(object_ids: set[str]) -> dict[str, int]:
    """Return the stored byte size for each unique Git blob."""

    result: dict[str, int] = {}
    ordered = sorted(object_ids)
    for offset in range(0, len(ordered), 1000):
        batch = ordered[offset : offset + 1000]
        proc = subprocess.run(
            ["git", "cat-file", "--batch-check"],
            input=b"".join(object_id.encode("ascii") + b"\n" for object_id in batch),
            stdout=subprocess.PIPE,
            check=True,
        )
        for expected_id, record in zip(batch, proc.stdout.splitlines(), strict=True):
            object_id, object_type, size_text = record.decode("ascii").split(" ")
            if object_id != expected_id or object_type != "blob":
                raise RuntimeError(f"unexpected Git object identity: {object_id} {object_type}")
            result[object_id] = int(size_text)
    return result


def envelope_shapes(
    value: Any,
    pointer: str = "",
    inherited_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Collect v1.1 envelope-shaped mappings without assigning authority."""

    found: list[dict[str, Any]] = []
    inherited_context = inherited_context or {}
    if isinstance(value, dict):
        required = {
            "schema_version",
            "point_estimate",
            "confidence_interval",
            "confidence_level",
            "source",
            "interval_semantics",
        }
        context = dict(inherited_context)
        for key in (
            "authority_scope",
            "production_value_eligible",
            "proof_scope",
            "status",
            "execution_evidence_authority",
            "scientific_authority",
            "authority_purpose",
            "authoritative_for",
            "may_not_use_for",
            "persisted_result_ref",
            "source_ref",
            "method_result_ref",
        ):
            if key in value:
                context[key] = value[key]
        report = value.get("report")
        if isinstance(report, dict):
            for key in ("authority_purpose", "authoritative_for", "may_not_use_for", "method_fqn"):
                if key in report:
                    context[f"report_{key}"] = report[key]
            report_metadata = report.get("metadata")
            if isinstance(report_metadata, dict):
                context["report_authority"] = report_metadata.get("authority")
                context["report_scientific_scope"] = report_metadata.get("scientific_scope")
                context["report_execution_profile"] = report_metadata.get("execution_profile")
        if required.issubset(value) and str(value.get("schema_version")) == "1.1":
            found.append(
                {
                    "json_pointer": pointer or "/",
                    "schema_version": value.get("schema_version"),
                    "point_estimate": value.get("point_estimate"),
                    "confidence_interval": value.get("confidence_interval"),
                    "confidence_level": value.get("confidence_level"),
                    "interval_semantics": value.get("interval_semantics"),
                    "source": value.get("source"),
                    "gate_eligible": value.get("gate_eligible"),
                    "authority_scope": context.get("authority_scope"),
                    "production_value_eligible": context.get("production_value_eligible"),
                    "proof_scope": context.get("proof_scope"),
                    "status": context.get("status"),
                    "execution_evidence_authority": context.get("execution_evidence_authority"),
                    "scientific_authority": context.get("scientific_authority"),
                    "authority_purpose": context.get("authority_purpose"),
                    "authoritative_for": context.get("authoritative_for"),
                    "may_not_use_for": context.get("may_not_use_for"),
                    "persisted_result_ref": context.get("persisted_result_ref"),
                    "source_ref": context.get("source_ref"),
                    "method_result_ref": context.get("method_result_ref"),
                    "report_authority": context.get("report_authority"),
                    "report_scientific_scope": context.get("report_scientific_scope"),
                    "report_execution_profile": context.get("report_execution_profile"),
                    "report_authority_purpose": context.get("report_authority_purpose"),
                    "report_authoritative_for": context.get("report_authoritative_for"),
                    "report_may_not_use_for": context.get("report_may_not_use_for"),
                    "report_method_fqn": context.get("report_method_fqn"),
                }
            )
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            found.extend(envelope_shapes(child, f"{pointer}/{escaped}", context))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(envelope_shapes(child, f"{pointer}/{index}", inherited_context))
    return found


def embedded_envelope_shapes(value: Any, pointer: str = "") -> list[dict[str, Any]]:
    """Find envelope-shaped JSON objects embedded in tracked log/string text."""

    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            found.extend(embedded_envelope_shapes(child, f"{pointer}/{escaped}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(embedded_envelope_shapes(child, f"{pointer}/{index}"))
    elif isinstance(value, str):
        if "schema_version" not in value or "confidence_interval" not in value:
            return found
        candidates: list[tuple[str, Any]] = []
        try:
            candidates.append(("whole_string", json.loads(value)))
        except json.JSONDecodeError:
            pass
        for line_number, line in enumerate(value.splitlines(), 1):
            if not line.lstrip().startswith("{"):
                continue
            try:
                candidates.append((f"line:{line_number}", json.loads(line)))
            except json.JSONDecodeError:
                continue
        for source, candidate in candidates:
            for shape in envelope_shapes(candidate):
                found.append({"embedded_source": source, "json_pointer": pointer, **shape})
    return found


def census(manifest: dict[str, Any]) -> dict[str, Any]:
    """Scan the explicitly listed refs and complete tracked path union."""

    refs = manifest.get("refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("manifest must contain a nonempty refs array")

    ref_rows: list[dict[str, str]] = []
    for item in refs:
        ref = str(item["ref"])
        expected_commit = str(item["commit"])
        actual_commit = git("rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip()
        if actual_commit != expected_commit:
            raise ValueError(f"ref moved: {ref} expected {expected_commit} got {actual_commit}")
        tree = git("rev-parse", f"{actual_commit}^{{tree}}").decode().strip()
        expected_tree = item.get("tree")
        if expected_tree is not None and tree != str(expected_tree):
            raise ValueError(f"tree moved: {ref} expected {expected_tree} got {tree}")
        ref_rows.append({"ref": ref, "commit": actual_commit, "tree": tree})

    all_path_versions: set[tuple[str, str]] = set()
    path_versions: set[tuple[str, str]] = set()
    serialized_path_versions: set[tuple[str, str]] = set()
    blobs: set[str] = set()
    json_versions: set[tuple[str, str]] = set()
    jsonl_versions: set[tuple[str, str]] = set()
    test_versions: set[tuple[str, str]] = set()
    archive_versions: set[tuple[str, str]] = set()
    owner_doc_refs: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)

    for row in ref_rows:
        for path, object_type, object_id in tree_entries(row["commit"]):
            if object_type != "blob":
                continue
            suffix = PurePosixPath(path).suffix.lower()
            all_path_versions.add((path, object_id))
            if suffix in SERIALIZED_SUFFIXES:
                serialized_path_versions.add((path, object_id))
            if path in OWNER_PATHS:
                owner_doc_refs[path][row["ref"]] = {
                    "commit": row["commit"],
                    "tree": row["tree"],
                    "blob": object_id,
                }
            if suffix in ARCHIVE_SUFFIXES:
                archive_versions.add((path, object_id))
            if suffix not in STRUCTURED_SUFFIXES:
                continue
            path_versions.add((path, object_id))
            blobs.add(object_id)
            if suffix == ".json":
                json_versions.add((path, object_id))
            if suffix == ".jsonl":
                jsonl_versions.add((path, object_id))
            if path.startswith("policy-engine/tests/"):
                test_versions.add((path, object_id))

    bytes_suffixes = SERIALIZED_SUFFIXES
    required_blob_ids = {
        object_id
        for path, object_id in serialized_path_versions
        if PurePosixPath(path).suffix.lower() in bytes_suffixes
    }
    cached_blobs = blob_batch_bytes(required_blob_ids)
    all_blob_ids = {object_id for _, object_id in all_path_versions}
    object_sizes = blob_sizes(all_blob_ids)

    parsed_json_versions = 0
    envelope_objects: list[dict[str, Any]] = []
    malformed_json: list[dict[str, str]] = []
    test_json_envelope_shapes: list[dict[str, Any]] = []
    for path, object_id in sorted(json_versions):
        raw = cached_blobs[object_id]
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            malformed_json.append({"path": path, "blob": object_id, "error": str(exc)})
            continue
        parsed_json_versions += 1
        for shape in envelope_shapes(value):
            envelope_objects.append({"path": path, "blob": object_id, **shape})
        if path.startswith("policy-engine/tests/"):
            for shape in envelope_shapes(value):
                test_json_envelope_shapes.append({"path": path, "blob": object_id, **shape})

    parsed_jsonl_records = 0
    malformed_jsonl_records: list[dict[str, Any]] = []
    for path, object_id in sorted(jsonl_versions):
        raw = cached_blobs[object_id]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            malformed_jsonl_records.append({"path": path, "blob": object_id, "error": str(exc)})
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                malformed_jsonl_records.append(
                    {"path": path, "blob": object_id, "line": line_number, "error": str(exc)}
                )
                continue
            parsed_jsonl_records += 1
            for shape in envelope_shapes(value):
                envelope_objects.append(
                    {"path": path, "blob": object_id, "line": line_number, **shape}
                )

    marker_re = re.compile(rb"ir\.uncertainty_envelope", re.IGNORECASE)
    schema_v1_1_re = re.compile(rb"schema_version.{0,16}1\.1", re.IGNORECASE | re.DOTALL)
    serialized_text_markers: list[dict[str, str]] = []
    for path, object_id in sorted(serialized_path_versions):
        if PurePosixPath(path).suffix.lower() not in TEXT_SCAN_SUFFIXES:
            continue
        raw = cached_blobs[object_id]
        if marker_re.search(raw) or (
            schema_v1_1_re.search(raw)
            and b"confidence_interval" in raw
            and b"point_estimate" in raw
        ):
            serialized_text_markers.append({"path": path, "blob": object_id})

    embedded_json_envelopes: list[dict[str, Any]] = []
    for item in serialized_text_markers:
        path = item["path"]
        object_id = item["blob"]
        raw = cached_blobs[object_id]
        try:
            value = json.loads(raw) if PurePosixPath(path).suffix.lower() == ".json" else raw.decode("utf-8")
        except (UnicodeDecodeError, json.JSONDecodeError):
            value = raw.decode("utf-8", errors="replace")
        for shape in embedded_envelope_shapes(value):
            embedded_json_envelopes.append({"path": path, "blob": object_id, **shape})

    test_marker_re = re.compile(rb"ir\.uncertainty_envelope", re.IGNORECASE)
    test_marker_matches: list[dict[str, str]] = []
    serialized_test_versions = {
        (path, object_id)
        for path, object_id in serialized_path_versions
        if path.startswith("policy-engine/tests/")
    }
    for path, object_id in sorted(serialized_test_versions):
        if PurePosixPath(path).suffix.lower() not in TEXT_SCAN_SUFFIXES:
            continue
        raw = cached_blobs[object_id]
        if test_marker_re.search(raw):
            test_marker_matches.append({"path": path, "blob": object_id})

    blob_versions = [
        (path, object_id)
        for path, object_id in path_versions
        if PurePosixPath(path).suffix.lower() == ".blob"
    ]
    all_versions_by_path: dict[str, set[str]] = defaultdict(set)
    for path, object_id in path_versions:
        all_versions_by_path[path].add(object_id)
    binary_cas_manifest_inventory: list[dict[str, Any]] = []
    for payload_path, payload_blob in sorted(blob_versions):
        manifest_path = payload_path[:-5] + ".manifest.json"
        manifest_ids = sorted(all_versions_by_path.get(manifest_path, set()))
        manifest_rows: list[dict[str, Any]] = []
        for manifest_blob in manifest_ids:
            manifest_value = json.loads(cached_blobs[manifest_blob])
            manifest_rows.append(
                {
                    "manifest_blob": manifest_blob,
                    "kind": manifest_value.get("kind"),
                    "artifact_schema": manifest_value.get("artifact_schema")
                    or manifest_value.get("schema"),
                }
            )
        binary_cas_manifest_inventory.append(
            {
                "payload_path": payload_path,
                "payload_blob": payload_blob,
                "manifest_path": manifest_path,
                "manifest_versions": manifest_rows,
            }
        )

    archive_scan: list[dict[str, Any]] = []
    archive_marker_re = re.compile(rb"ir\.uncertainty_envelope", re.IGNORECASE)
    for archive_path, archive_blob in sorted(archive_versions):
        raw = cached_blobs[archive_blob]
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.namelist()
                marker_members = []
                envelope_shape_marker_members = []
                for member in members:
                    member_bytes = archive.read(member)
                    if archive_marker_re.search(member_bytes):
                        marker_members.append(member)
                    if (
                        schema_v1_1_re.search(member_bytes)
                        and b"confidence_interval" in member_bytes
                        and b"point_estimate" in member_bytes
                    ):
                        envelope_shape_marker_members.append(member)
                archive_scan.append(
                    {
                        "path": archive_path,
                        "blob": archive_blob,
                        "member_count": len(members),
                        "uncertainty_envelope_marker_members": marker_members,
                        "v1_1_envelope_shape_marker_members": envelope_shape_marker_members,
                    }
                )
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            archive_scan.append(
                {"path": archive_path, "blob": archive_blob, "error": str(exc)}
            )

    gzip_scan: list[dict[str, Any]] = []
    for archive_path, archive_blob in sorted(serialized_path_versions):
        if PurePosixPath(archive_path).suffix.lower() != ".gz":
            continue
        raw = cached_blobs[archive_blob]
        uncompressed_size = int.from_bytes(raw[-4:], "little") if len(raw) >= 4 else None
        row: dict[str, Any] = {
            "path": archive_path,
            "blob": archive_blob,
            "compressed_bytes": object_sizes[archive_blob],
            "uncompressed_size_from_gzip_trailer": uncompressed_size,
        }
        if uncompressed_size is not None and uncompressed_size <= 5_000_000:
            try:
                expanded = gzip.decompress(raw)
                row["decompressed_bytes"] = len(expanded)
                row["content_scan"] = "scanned; bounded to at most 5 MB by trailer size"
                row["marker_present"] = bool(marker_re.search(expanded))
                row["v1_1_envelope_shapes"] = []
                if ".json" in archive_path.lower():
                    try:
                        value = json.loads(expanded)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        value = expanded.decode("utf-8", errors="replace")
                else:
                    value = expanded.decode("utf-8", errors="replace")
                if isinstance(value, (dict, list)):
                    row["v1_1_envelope_shapes"] = envelope_shapes(value)
                else:
                    row["v1_1_envelope_shapes"] = embedded_envelope_shapes(value)
            except (OSError, EOFError, gzip.BadGzipFile) as exc:
                row["content_scan"] = "ERROR"
                row["error"] = str(exc)
        else:
            row["content_scan"] = "UNRUN; large compressed source left opaque during this review"
        gzip_scan.append(row)

    opaque_serialized_scan: list[dict[str, Any]] = []
    for path, object_id in sorted(serialized_path_versions):
        if PurePosixPath(path).suffix.lower() not in OPAQUE_SERIALIZED_SUFFIXES:
            continue
        raw = cached_blobs[object_id]
        opaque_serialized_scan.append(
            {
                "path": path,
                "blob": object_id,
                "content_bytes": object_sizes[object_id],
                "marker_present_in_raw_bytes": bool(marker_re.search(raw)),
                "v1_1_shape_markers_present_in_raw_bytes": bool(
                    schema_v1_1_re.search(raw)
                    and b"confidence_interval" in raw
                    and b"point_estimate" in raw
                ),
                "interpretation": "byte scan only; database/pickle/blob was not deserialized",
            }
        )

    owner_identity: dict[str, Any] = {}
    for path in OWNER_PATHS:
        per_ref = owner_doc_refs.get(path, {})
        by_blob: dict[str, list[str]] = defaultdict(list)
        for ref, identity in per_ref.items():
            by_blob[identity["blob"]].append(ref)
        owner_identity[path] = {
            "per_ref": dict(sorted(per_ref.items())),
            "distinct_blobs_with_refs": [
                {"blob": blob, "refs": sorted(blob_refs)}
                for blob, blob_refs in sorted(by_blob.items())
            ],
            "present_in_every_listed_ref": len(per_ref) == len(ref_rows),
            "byte_identical_across_listed_refs": len(by_blob) == 1 and len(per_ref) == len(ref_rows),
        }

    source_snapshot = manifest.get("review_source_snapshot")
    source_snapshot_result: dict[str, Any] | None = None
    if isinstance(source_snapshot, dict):
        source_commit = str(source_snapshot["commit"])
        source_tree = git("rev-parse", f"{source_commit}^{{tree}}").decode().strip()
        if source_tree != str(source_snapshot["tree"]):
            raise ValueError("review source root tree does not match manifest")
        comparison_commit = str(source_snapshot["comparison_commit"])
        changed_source_paths = git(
            "diff", "--name-only", comparison_commit, source_commit, "--", "policy-engine/src"
        ).decode().splitlines()
        compared_paths: dict[str, dict[str, str]] = {}
        for path in source_snapshot.get("compared_paths", []):
            compared_paths[str(path)] = {
                "comparison_blob": git(
                    "rev-parse", f"{comparison_commit}:{path}"
                ).decode().strip(),
                "review_blob": git("rev-parse", f"{source_commit}:{path}").decode().strip(),
            }
        source_snapshot_result = {
            "review_commit": source_commit,
            "review_tree": source_tree,
            "comparison_commit": comparison_commit,
            "comparison_source_subtree": git(
                "rev-parse", f"{comparison_commit}:policy-engine/src"
            ).decode().strip(),
            "review_source_subtree": git(
                "rev-parse", f"{source_commit}:policy-engine/src"
            ).decode().strip(),
            "changed_source_paths_since_comparison": changed_source_paths,
            "compared_paths": compared_paths,
        }

    suffix_inventory: dict[str, dict[str, int]] = {}
    for suffix in sorted(
        {PurePosixPath(path).suffix.lower() or "[no suffix]" for path, _ in all_path_versions}
    ):
        versions = [
            (path, object_id)
            for path, object_id in all_path_versions
            if (PurePosixPath(path).suffix.lower() or "[no suffix]") == suffix
        ]
        suffix_blob_ids = {object_id for _, object_id in versions}
        suffix_inventory[suffix] = {
            "distinct_paths": len({path for path, _ in versions}),
            "path_blob_versions": len(versions),
            "distinct_git_blobs": len(suffix_blob_ids),
            "path_blob_version_bytes": sum(object_sizes[object_id] for _, object_id in versions),
            "distinct_git_blob_bytes": sum(object_sizes[object_id] for object_id in suffix_blob_ids),
        }

    serialized_versions = {
        (path, object_id)
        for path, object_id in all_path_versions
        if PurePosixPath(path).suffix.lower() in SERIALIZED_SUFFIXES
    }
    serialized_suffix_counts = Counter(
        PurePosixPath(path).suffix.lower() for path, _ in serialized_versions
    )
    serialized_test_suffix_counts = Counter(
        PurePosixPath(path).suffix.lower() for path, _ in serialized_test_versions
    )
    serialized_test_opaque_markers = [
        item
        for item in opaque_serialized_scan
        if item["path"].startswith("policy-engine/tests/")
        and (item["marker_present_in_raw_bytes"] or item["v1_1_shape_markers_present_in_raw_bytes"])
    ]

    return {
        "refs": ref_rows,
        "review_source_snapshot": source_snapshot_result,
        "distinct_tree_count": len({row["tree"] for row in ref_rows}),
        "complete_tracked_file_denominator": {
            "distinct_paths": len({path for path, _ in all_path_versions}),
            "path_blob_versions": len(all_path_versions),
            "distinct_git_blobs": len({object_id for _, object_id in all_path_versions}),
            "distinct_git_blob_bytes": sum(object_sizes.values()),
            "path_blob_version_bytes": sum(
                object_sizes[object_id] for _, object_id in all_path_versions
            ),
            "suffix_counts_by_path_blob_version": dict(
                sorted(
                    Counter(
                        PurePosixPath(path).suffix.lower() or "[no suffix]"
                        for path, _ in all_path_versions
                    ).items()
                )
            ),
            "complete_suffix_inventory": suffix_inventory,
        },
        "serialized_source_denominator": {
            "suffix_set": sorted(SERIALIZED_SUFFIXES),
            "distinct_paths": len({path for path, _ in serialized_versions}),
            "path_blob_versions": len(serialized_versions),
            "distinct_git_blobs": len({object_id for _, object_id in serialized_versions}),
            "path_blob_version_bytes": sum(
                object_sizes[object_id] for _, object_id in serialized_versions
            ),
            "distinct_git_blob_bytes": sum(
                object_sizes[object_id] for object_id in {oid for _, oid in serialized_versions}
            ),
            "suffix_counts_by_path_blob_version": dict(sorted(serialized_suffix_counts.items())),
        },
        "structured_source_denominator": {
            "distinct_paths": len({path for path, _ in path_versions}),
            "path_blob_versions": len(path_versions),
            "distinct_git_blobs": len(blobs),
            "suffix_counts_by_path_blob_version": dict(
                sorted(
                    Counter(PurePosixPath(path).suffix.lower() for path, _ in path_versions).items()
                )
            ),
        },
        "json": {
            "path_blob_versions": len(json_versions),
            "parsed_versions": parsed_json_versions,
            "malformed_versions": malformed_json,
        },
        "jsonl": {
            "path_blob_versions": len(jsonl_versions),
            "parsed_records": parsed_jsonl_records,
            "malformed_records": malformed_jsonl_records,
        },
        "serialized_text_marker_candidates": serialized_text_markers,
        "embedded_json_v1_1_envelope_objects": embedded_json_envelopes,
        "test_source_denominator": {
            "distinct_paths": len({path for path, _ in test_versions}),
            "path_blob_versions": len(test_versions),
            "suffix_counts_by_path_blob_version": dict(
                sorted(Counter(PurePosixPath(path).suffix.lower() for path, _ in test_versions).items())
            ),
            "uncertainty_envelope_marker_matches": test_marker_matches,
            "v1_1_envelope_shaped_json_objects": test_json_envelope_shapes,
        },
        "serialized_test_source_denominator": {
            "distinct_paths": len({path for path, _ in serialized_test_versions}),
            "path_blob_versions": len(serialized_test_versions),
            "distinct_git_blobs": len({object_id for _, object_id in serialized_test_versions}),
            "suffix_counts_by_path_blob_version": dict(sorted(serialized_test_suffix_counts.items())),
            "text_marker_matches": test_marker_matches,
            "opaque_byte_marker_matches": serialized_test_opaque_markers,
            "v1_1_envelope_shaped_json_objects": test_json_envelope_shapes,
        },
        "v1_1_envelope_shaped_objects": envelope_objects,
        "tracked_blob_payloads_and_manifests": binary_cas_manifest_inventory,
        "database_and_opaque_serialized_path_versions": [
            {"path": path, "blob": object_id, "suffix": PurePosixPath(path).suffix.lower()}
            for path, object_id in sorted(path_versions)
            if PurePosixPath(path).suffix.lower()
            in {".duckdb", ".sqlite", ".sqlite-wal", ".typed", ".fixture"}
        ],
        "archive_member_scan": archive_scan,
        "gzip_source_scan": gzip_scan,
        "opaque_serialized_byte_scan": opaque_serialized_scan,
        "owner_decision_source_identities": owner_identity,
        "interpretation": (
            "This is a source/path inventory, not an authority oracle. Owner appointment and "
            "ratification require explicit tracked declaration by the appointed owner; keyword "
            "presence, status adjacency, and source shape do not establish either."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refs-json", required=True, help="explicit immutable ref manifest")
    parser.add_argument("--output", required=True, help="receipt output path")
    args = parser.parse_args()
    with open(args.refs_json, encoding="utf-8") as stream:
        manifest = json.load(stream)
    result = census(manifest)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
