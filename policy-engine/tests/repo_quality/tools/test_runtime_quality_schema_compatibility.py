# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

from polisyos.runtime.quality.schema_compat import ReaderSchemaRange, stable_payload_sha256
from tools.quality.validation import check_runtime_quality_schema_compatibility as compat_report


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row_map(payload: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["path"]), str(row["reader"])): row
        for row in payload["entries"]  # type: ignore[index]
    }


def _declarations() -> dict[str, tuple[ReaderSchemaRange, ...]]:
    return {
        "bundle_assembler": (
            ReaderSchemaRange(
                reader="bundle_assembler",
                schema_family="policyos.example_bundle",
                min_version="2",
                max_version="2",
                current_version="2",
            ),
        ),
        "scorecard": (
            ReaderSchemaRange(
                reader="scorecard",
                schema_family="policyos.example_report",
                min_version="1",
                max_version="2",
                current_version="2",
                migration_versions=("1",),
            ),
        ),
    }


def test_report_classifies_stale_unknown_renamed_missing_status_and_semantic_loss(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path
    stale_bundle = {
        "schema_version": "policyos.example_bundle.v1",
        "status": "pass",
    }
    unknown_report = {
        "schema_version": "policyos.unregistered_report.v99",
        "status": "pass",
    }
    legacy_renamed = {
        "schema_version": "policyos.example_report.v1",
        "quality_status": "pass",
        "artifact_ref": "cas://sha256/" + "a" * 64,
    }
    migrated_renamed = {
        "schema_version": "policyos.example_report.v2",
        "status": "pass",
        "artifact_ref": "cas://sha256/" + "a" * 64,
    }
    missing_status_source = {
        "schema_version": "policyos.example_report.v1",
        "quality_status": "pass",
    }
    missing_status_target = {
        "schema_version": "policyos.example_report.v2",
    }
    semantic_loss_source = {
        "schema_version": "policyos.example_report.v1",
        "quality_status": "pass",
        "artifact_ref": "cas://sha256/" + "b" * 64,
    }
    semantic_loss_target = {
        "schema_version": "policyos.example_report.v2",
        "status": "pass",
    }

    _write_json(repo_root / "_build/runtime_quality/stale_bundle.json", stale_bundle)
    _write_json(repo_root / "_build/runtime_quality/unknown_schema_report.json", unknown_report)
    _write_json(
        repo_root / "_build/runtime_quality/renamed_field_report.json",
        {
            **legacy_renamed,
            "schema_migration": {
                "source_payload_sha256": stable_payload_sha256(legacy_renamed),
                "target_payload_sha256": stable_payload_sha256(migrated_renamed),
                "target_payload": migrated_renamed,
                "field_mappings": {"quality_status": "status"},
                "required_semantic_fields": ["status", "artifact_ref"],
            },
        },
    )
    _write_json(
        repo_root / "_build/runtime_quality/missing_status_report.json",
        {
            **missing_status_source,
            "schema_migration": {
                "source_payload_sha256": stable_payload_sha256(missing_status_source),
                "target_payload_sha256": stable_payload_sha256(missing_status_target),
                "target_payload": missing_status_target,
                "field_mappings": {"quality_status": "status"},
                "required_semantic_fields": ["status"],
            },
        },
    )
    _write_json(
        repo_root / "_build/runtime_quality/semantic_loss_report.json",
        {
            **semantic_loss_source,
            "schema_migration": {
                "source_payload_sha256": stable_payload_sha256(semantic_loss_source),
                "target_payload_sha256": stable_payload_sha256(semantic_loss_target),
                "target_payload": semantic_loss_target,
                "semantic_loss": True,
                "lost_fields": ["artifact_ref"],
                "required_semantic_fields": ["status", "artifact_ref"],
            },
        },
    )

    payload = compat_report.build_compatibility_report(
        repo_root=repo_root,
        root_paths=("_build/runtime_quality",),
        readers=("bundle_assembler", "scorecard"),
        declarations=_declarations(),
    )
    rows = _row_map(payload)

    assert rows[("_build/runtime_quality/stale_bundle.json", "bundle_assembler")][
        "decision"
    ] == "stale_schema_blocked"
    assert rows[("_build/runtime_quality/unknown_schema_report.json", "scorecard")][
        "decision"
    ] == "unknown_schema_blocked"
    assert rows[("_build/runtime_quality/renamed_field_report.json", "scorecard")][
        "decision"
    ] == "compatible_with_migration"
    assert rows[("_build/runtime_quality/renamed_field_report.json", "scorecard")][
        "migration_verified"
    ] is True
    assert rows[("_build/runtime_quality/missing_status_report.json", "scorecard")][
        "reason"
    ] == "missing_required_semantic_fields"
    assert rows[("_build/runtime_quality/semantic_loss_report.json", "scorecard")][
        "reason"
    ] == "legacy_migration_semantic_loss"
    assert payload["summary"]["production_closeout_blocked_count"] >= 4  # type: ignore[index]


def test_cli_writes_runtime_quality_schema_compatibility_report(tmp_path: Path) -> None:
    repo_root = tmp_path
    output_dir = repo_root / "_build/honest-diagnostics/schema-compatibility"
    _write_json(
        repo_root / "_build/runtime_quality/scorecard.json",
        {
            "schema_version": "policyos.quality_scorecard.v1",
            "status": "pass",
        },
    )

    exit_code = compat_report.main(
        [
            "--repo-root",
            str(repo_root),
            "--root-path",
            "_build/runtime_quality",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    json_output = output_dir / "runtime_quality_schema_compatibility.json"
    markdown_output = output_dir / "runtime_quality_schema_compatibility.md"
    assert json_output.exists()
    assert markdown_output.exists()
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == compat_report.SCHEMA_VERSION
    assert payload["summary"]["entry_count"] >= 1
    assert "| `_build/runtime_quality/scorecard.json` |" in markdown_output.read_text(
        encoding="utf-8"
    )
