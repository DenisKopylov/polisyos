from __future__ import annotations

import ast
import hashlib
import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tools.quality.validation import decomposition_preflight as preflight
from tools.quality.validation.decomposition_preflight import (
    REPO_ROOT,
    validate_dynamic_imports,
    validate_import_cycles,
    validate_import_time_regression,
    validate_reexport_shim_shapes,
)

_TEST_DYNAMIC_IMPORT_REVIEW_METADATA = {
    "review_owner": "test-architecture-owner",
    "reviewed_at": "2025-01-02",
    "review_expires": "2025-12-31",
}


def _render_dynamic_imports_toml(entries: list[dict[str, object]]) -> str:
    return preflight.render_dynamic_imports_toml(
        entries,
        review_metadata=_TEST_DYNAMIC_IMPORT_REVIEW_METADATA,
    )


def test_dynamic_import_renderer_separates_owner_review_metadata() -> None:
    metadata = {
        "review_owner": "owner-supplied-reviewer",
        "reviewed_at": "2001-02-03",
        "review_expires": "2001-04-05",
    }
    rendered = preflight.render_dynamic_imports_toml([], review_metadata=metadata)
    header = tomllib.loads(rendered)["dynamic_imports"]
    assert {field: header[field] for field in metadata} == metadata

    omitted = tomllib.loads(preflight.render_dynamic_imports_toml([]))["dynamic_imports"]
    assert set(omitted).isdisjoint(preflight.DYNAMIC_IMPORT_REVIEW_FIELDS)
    assert "2026-05-06" not in rendered
    assert "2026-08-04" not in rendered


@pytest.mark.parametrize(
    "metadata",
    [
        {"review_owner": "owner"},
        {
            "review_owner": "owner",
            "reviewed_at": "2026-8-4",
            "review_expires": "2027-08-04",
        },
        {
            "review_owner": "   ",
            "reviewed_at": "2026-08-04",
            "review_expires": "2027-08-04",
        },
    ],
)
def test_dynamic_import_renderer_rejects_malformed_review_metadata(metadata) -> None:
    with pytest.raises(preflight.DynamicImportReviewMetadataError):
        preflight.render_dynamic_imports_toml([], review_metadata=metadata)


def test_dynamic_import_validator_requires_valid_owner_review_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: [])

    registry_path.write_text(preflight.render_dynamic_imports_toml([]), encoding="utf-8")
    missing = preflight.validate_dynamic_imports()
    assert {
        finding.detail.rsplit(".", 1)[-1]
        for finding in missing
        if finding.message == "dynamic import registry header field is missing"
        and finding.detail
        in {f"dynamic_imports.{field}" for field in preflight.DYNAMIC_IMPORT_REVIEW_FIELDS}
    } == set(preflight.DYNAMIC_IMPORT_REVIEW_FIELDS)

    malformed_registry = (
        '[dynamic_imports]\nversion = 1\nstatus = "fail_closed"\n'
        'owner = "team-architecture"\nphase = "3A"\n'
        'review_owner = "owner-supplied-reviewer"\nreviewed_at = "2026-08-04"\n'
        'review_expires = "not-a-date"\n'
    )
    registry_path.write_text(malformed_registry, encoding="utf-8")
    malformed = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import review metadata is malformed"
        and finding.detail == "dynamic_imports.review_expires"
        for finding in malformed
    )


def _stub_phase3a_writer_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    registry_path: Path,
) -> Path:
    repo_root = tmp_path / "repo"
    baseline = repo_root / "architecture/baselines/structure_remediation"
    monkeypatch.setattr(preflight, "REPO_ROOT", repo_root)
    monkeypatch.setattr(preflight, "BASELINE_DIR", baseline)
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(
        preflight, "LAZY_IMPORTS_PATH", repo_root / "architecture/imports/lazy.toml"
    )
    monkeypatch.setattr(preflight, "SCHEMA_BASELINE_PATH", baseline / "schema.json")
    monkeypatch.setattr(preflight, "PUBLIC_SURFACE_BASELINE_PATH", baseline / "public.json")
    monkeypatch.setattr(preflight, "IMPORT_GRAPH_BASELINE_PATH", baseline / "graph.json")
    monkeypatch.setattr(preflight, "IMPORT_TIME_BASELINE_PATH", baseline / "time.json")
    monkeypatch.setattr(preflight, "PICKLE_INVENTORY_PATH", baseline / "pickle.json")
    monkeypatch.setattr(preflight, "BLUEPRINT_PATH", repo_root / "docs/blueprint.md")
    monkeypatch.setattr(preflight, "CHECKPOINT_FIXTURE_ROOT", tmp_path / "fixtures")
    snapshot = object()
    monkeypatch.setattr(preflight, "_collect_import_source_snapshot", lambda: snapshot)
    monkeypatch.setattr(preflight, "collect_import_graph", lambda **_: {})
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: [])
    monkeypatch.setattr(preflight, "create_checkpoint_fixtures", lambda: None)
    monkeypatch.setattr(preflight, "collect_pickle_inventory", lambda: {})
    monkeypatch.setattr(preflight, "collect_public_surface_snapshot", lambda: {})
    monkeypatch.setattr(preflight, "collect_schema_baseline", lambda: {})
    monkeypatch.setattr(preflight, "_import_graph_input_receipt", lambda _: {})
    monkeypatch.setattr(preflight, "generate_blueprint", lambda **_: "")
    return baseline


def test_phase3a_generator_preserves_existing_review_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "repo/architecture/imports/dynamic.toml"
    registry_path.parent.mkdir(parents=True)
    metadata = {
        "review_owner": "owner-supplied-reviewer",
        "reviewed_at": "2001-02-03",
        "review_expires": "2001-04-05",
    }
    registry_path.write_text(
        preflight.render_dynamic_imports_toml([], review_metadata=metadata),
        encoding="utf-8",
    )
    _stub_phase3a_writer_inputs(monkeypatch, tmp_path, registry_path)

    preflight.write_phase3a_artifacts(include_import_time=False)

    generated = tomllib.loads(registry_path.read_text(encoding="utf-8"))["dynamic_imports"]
    assert {field: generated[field] for field in metadata} == metadata


def test_phase3a_generator_refuses_malformed_review_before_any_artifact_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "repo/architecture/imports/dynamic.toml"
    registry_path.parent.mkdir(parents=True)
    malformed_registry = '[dynamic_imports]\nreview_owner = "partial-owner-only"\n'
    registry_path.write_text(malformed_registry, encoding="utf-8")
    baseline = _stub_phase3a_writer_inputs(monkeypatch, tmp_path, registry_path)

    with pytest.raises(preflight.DynamicImportReviewMetadataError):
        preflight.write_phase3a_artifacts(include_import_time=False)

    assert not baseline.exists()
    assert registry_path.read_text(encoding="utf-8") == malformed_registry


def test_dynamic_imports_gate_resolves_registered_targets() -> None:
    findings = validate_dynamic_imports()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_dynamic_imports_gate_rejects_registry_and_target_corruption(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_entries = preflight.collect_dynamic_imports()
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: source_entries)

    def validate_entries(entries: list[dict[str, object]]):
        registry_path.write_text(
            _render_dynamic_imports_toml(entries),
            encoding="utf-8",
        )
        return preflight.validate_dynamic_imports()

    assert validate_entries(source_entries) == []

    corrupt_field_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    corrupt_field_entries[0]["line"] = int(corrupt_field_entries[0]["line"]) + 100_000
    corrupt_field_findings = validate_entries(corrupt_field_entries)
    assert any(
        finding.message == "dynamic import call is not registered"
        for finding in corrupt_field_findings
    )
    assert any(
        finding.message == "registered dynamic import call no longer exists"
        for finding in corrupt_field_findings
    )

    missing_call_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    missing_call = missing_call_entries.pop(0)
    missing_call_signature = (
        missing_call["source_file"],
        missing_call["line"],
        missing_call["call"],
        missing_call["pattern"],
    )
    missing_call_findings = validate_entries(missing_call_entries)
    assert any(
        finding.message == "dynamic import call is not registered"
        and finding.detail == repr(missing_call_signature)
        for finding in missing_call_findings
    )

    invalid_target_entries = [
        {**entry, "allowed_targets": list(entry["allowed_targets"])} for entry in source_entries
    ]
    target_entry = next(entry for entry in invalid_target_entries if entry["allowed_targets"])
    target_entry["allowed_targets"] = ["polisyos.__not_a_real_dynamic_catalog_target__"]
    target_findings = validate_entries(invalid_target_entries)
    assert any(
        finding.message == "allowed dynamic import target does not resolve"
        for finding in target_findings
    )


def _dynamic_toml_literal(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if type(value) is int:
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_dynamic_toml_literal(item) for item in value) + "]"
    raise AssertionError(f"unsupported canonical TOML value: {value!r}")


def _corrupt_dynamic_value(value: object) -> object:
    if isinstance(value, str):
        return value + " (corrupt)"
    if type(value) is int:
        return value + 1
    if isinstance(value, list):
        return [*value, "__corrupt__"]
    raise AssertionError(f"unsupported canonical dynamic field: {value!r}")


def test_dynamic_imports_gate_rejects_every_canonical_row_field_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_entries = preflight.collect_dynamic_imports()
    canonical_text = _render_dynamic_imports_toml(source_entries)
    canonical_rows = tomllib.loads(canonical_text)["pattern"]
    assert canonical_rows
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: source_entries)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    registry_path.write_text(canonical_text, encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    signature_fields = {"source_file", "line", "call", "pattern"}
    for field, value in canonical_rows[0].items():
        corrupted_rows = [dict(entry) for entry in canonical_rows]
        corrupted_rows[0][field] = _corrupt_dynamic_value(value)
        registry_path.write_text(
            _render_dynamic_imports_toml(corrupted_rows),
            encoding="utf-8",
        )
        findings = preflight.validate_dynamic_imports()
        assert findings, f"corrupting canonical row field {field!r} stayed green"
        if field in signature_fields:
            assert any(
                finding.message
                in {
                    "dynamic import call is not registered",
                    "registered dynamic import call no longer exists",
                }
                for finding in findings
            ), field
        else:
            assert any(
                finding.message == "registered dynamic import row differs from canonical collector"
                and field in finding.detail
                for finding in findings
            ), field


def test_dynamic_imports_gate_rejects_every_stable_header_field_corruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_entries = preflight.collect_dynamic_imports()
    canonical_text = _render_dynamic_imports_toml(source_entries)
    canonical_header = tomllib.loads(canonical_text)["dynamic_imports"]
    external_review_fields = {"review_owner", "reviewed_at", "review_expires"}
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: source_entries)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    for field, value in canonical_header.items():
        if field in external_review_fields:
            continue
        original_line = f"{field} = {_dynamic_toml_literal(value)}"
        corrupted_line = f"{field} = {_dynamic_toml_literal(_corrupt_dynamic_value(value))}"
        assert original_line in canonical_text
        registry_path.write_text(
            canonical_text.replace(original_line, corrupted_line, 1),
            encoding="utf-8",
        )
        findings = preflight.validate_dynamic_imports()
        assert any(
            finding.message
            == "dynamic import registry header field differs from canonical contract"
            and f"dynamic_imports.{field}" in finding.detail
            for finding in findings
        ), field

    missing_header_line = f"status = {_dynamic_toml_literal(canonical_header['status'])}\n"
    registry_path.write_text(
        canonical_text.replace(missing_header_line, "", 1),
        encoding="utf-8",
    )
    missing_header_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import registry header field is missing"
        and "dynamic_imports.status" in finding.detail
        for finding in missing_header_findings
    )

    registry_path.write_text(
        canonical_text.replace(
            "[dynamic_imports]\n",
            '[dynamic_imports]\nunowned_header = "unexpected"\n',
            1,
        ),
        encoding="utf-8",
    )
    unexpected_header_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import registry header has an unexpected field"
        and "dynamic_imports.unowned_header" in finding.detail
        for finding in unexpected_header_findings
    )

    for field in external_review_fields:
        original_line = f"{field} = {_dynamic_toml_literal(canonical_header[field])}"
        registry_path.write_text(
            canonical_text.replace(original_line, f'{field} = ""', 1),
            encoding="utf-8",
        )
        findings = preflight.validate_dynamic_imports()
        assert any(
            finding.message == "dynamic import review metadata is malformed"
            and f"dynamic_imports.{field}" in finding.detail
            for finding in findings
        ), field


def _assert_diagnostic_identifies_path(
    detail: str,
    expected_path: Path,
    repo_root: Path,
    *,
    expected_relative: bool,
) -> str:
    """Check reported path identity without calling the formatter under test."""
    rendered_path, separator, suffix = detail.partition(": ")
    assert rendered_path
    observed = Path(rendered_path)
    assert observed.is_absolute() is (not expected_relative)
    if not observed.is_absolute():
        observed = repo_root / observed
    assert observed.resolve() == expected_path.resolve()
    return suffix if separator else ""


@pytest.mark.parametrize(
    "relative_to_repo",
    [True, False],
    ids=["inside-selected-root", "outside-selected-root"],
)
def test_dynamic_imports_gate_distinguishes_absent_and_malformed_registry(
    relative_to_repo: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "selected-repository"
    inside_path = repo_root / "architecture/imports/dynamic.toml"
    outside_path = tmp_path / "outside/architecture/imports/dynamic.toml"
    registry_path = inside_path if relative_to_repo else outside_path
    registry_path.parent.mkdir(parents=True)
    monkeypatch.setattr(preflight, "REPO_ROOT", repo_root)
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: [])

    missing_findings = preflight.validate_dynamic_imports()
    assert [finding.message for finding in missing_findings] == [
        "dynamic import registry is missing"
    ]
    _assert_diagnostic_identifies_path(
        missing_findings[0].detail,
        registry_path,
        repo_root,
        expected_relative=relative_to_repo,
    )

    registry_path.mkdir()
    unreadable_findings = preflight.validate_dynamic_imports()
    assert [finding.message for finding in unreadable_findings] == [
        "dynamic import registry cannot be read"
    ]
    unreadable_suffix = _assert_diagnostic_identifies_path(
        unreadable_findings[0].detail,
        registry_path,
        repo_root,
        expected_relative=relative_to_repo,
    )
    assert unreadable_suffix.startswith("IsADirectoryError:")
    registry_path.rmdir()

    registry_path.write_text("[dynamic_imports\n", encoding="utf-8")
    malformed_findings = preflight.validate_dynamic_imports()
    assert [finding.message for finding in malformed_findings] == [
        "dynamic import registry is malformed"
    ]
    malformed_suffix = _assert_diagnostic_identifies_path(
        malformed_findings[0].detail,
        registry_path,
        repo_root,
        expected_relative=relative_to_repo,
    )
    assert malformed_suffix

    registry_path.write_text("[unrelated]\nvalue = 1\n", encoding="utf-8")
    missing_header_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import registry header is missing or malformed"
        for finding in missing_header_findings
    )


def test_dynamic_imports_gate_rejects_incomplete_and_open_row_schemas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_entries = preflight.collect_dynamic_imports()
    canonical_text = _render_dynamic_imports_toml(source_entries)
    canonical_rows = tomllib.loads(canonical_text)["pattern"]
    registry_path = tmp_path / "dynamic.toml"
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    monkeypatch.setattr(preflight, "collect_dynamic_imports", lambda: source_entries)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    removed_id = f"id = {_dynamic_toml_literal(canonical_rows[0]['id'])}\n"
    registry_path.write_text(canonical_text.replace(removed_id, "", 1), encoding="utf-8")
    missing_field_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import row differs from canonical collector"
        and "id" in finding.detail
        for finding in missing_field_findings
    )

    first_notes = f"notes = {_dynamic_toml_literal(canonical_rows[0]['notes'])}\n"
    registry_path.write_text(
        canonical_text.replace(first_notes, first_notes + 'unowned_field = "unexpected"\n', 1),
        encoding="utf-8",
    )
    unexpected_field_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import row differs from canonical collector"
        and "unowned_field" in finding.detail
        for finding in unexpected_field_findings
    )


def test_import_cycles_gate_allows_only_phase3a_lazy_cycles() -> None:
    findings = validate_import_cycles()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def _write_runtime_import_fixture(
    root: Path,
    sources: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src_root = root / "src"
    (src_root / "polisyos" / "foundry").mkdir(parents=True, exist_ok=True)
    for relative_path, source in sources.items():
        path = src_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(preflight, "REPO_ROOT", root)
    monkeypatch.setattr(preflight, "SRC_ROOT", src_root)


def _write_current_full_scc_registry(path: Path) -> str:
    """Register this fixture's canonical full-graph SCC signatures."""
    full_graph = preflight.collect_import_graph()
    assert full_graph["cycles"], "registered-cycle fixture must contain a full-graph SCC"
    registry_text = preflight.render_lazy_toml(full_graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(registry_text, encoding="utf-8")
    return registry_text


def test_import_cycle_gate_rejects_guard_removal_even_when_markers_remain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    assert validate_import_cycles() == []

    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "if TYPE_ONLY:\n"
        "    pass  # Keep the marker while removing the runtime guard.\n"
        "from polisyos.scientist.b import B\n"
    )
    (tmp_path / "src/polisyos/scientist/a.py").write_text(source, encoding="utf-8")
    findings = validate_import_cycles()
    assert len(findings) == 1
    assert (
        findings[0].message == "registered deferred-cycle signature contains a module-eager cycle"
    )
    assert "polisyos.scientist.a" in findings[0].detail
    assert "polisyos.scientist.b" in findings[0].detail


def test_import_cycle_gate_does_not_trust_shadowed_type_checking_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = {
        "module": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "TYPE_ONLY = True\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "class": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "class Scope:\n"
            "    TYPE_ONLY = True\n"
            "    if TYPE_ONLY:\n"
            "        from polisyos.scientist.b import B\n"
        ),
        "called_function": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def bootstrap():\n"
            "    TYPE_ONLY = True\n"
            "    if TYPE_ONLY:\n"
            "        from polisyos.scientist.b import B\n"
            "bootstrap()\n"
        ),
        "ambiguous_branch": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "if runtime_flag:\n"
            "    TYPE_ONLY = True\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
    }
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    for label, a_source in cases.items():
        case_root = tmp_path / label
        _write_runtime_import_fixture(
            case_root,
            {
                "polisyos/scientist/a.py": a_source,
                "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            },
            monkeypatch,
        )
        _write_current_full_scc_registry(registry)
        findings = validate_import_cycles()
        assert any(
            finding.message == "registered deferred-cycle signature contains a module-eager cycle"
            for finding in findings
        ), label


def test_unused_function_type_checking_binding_does_not_shadow_module_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "def unused():\n"
                "    TYPE_ONLY = True\n"
                "    if TYPE_ONLY:\n"
                "        from polisyos.scientist import deferred_edge\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist import guarded_edge\n"
            ),
            "polisyos/scientist/deferred_edge.py": "Value = object()\n",
            "polisyos/scientist/guarded_edge.py": "Value = object()\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.guarded_edge") not in edges
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") not in edges


def test_runtime_import_graph_includes_only_evaluated_function_annotations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = (
        ("eager", False, True),
        ("deferred", True, False),
    )
    for name, future_annotations, expect_cycle in cases:
        root = tmp_path / name
        prefix = "from __future__ import annotations\n" if future_annotations else ""
        _write_runtime_import_fixture(
            root,
            {
                "polisyos/scientist/a.py": (
                    prefix + "def annotation_import():\n"
                    "    from polisyos.scientist import b\n"
                    "    return int\n"
                    "def declared(value: annotation_import()):\n"
                    "    return value\n"
                ),
                "polisyos/scientist/b.py": "from polisyos.scientist.a import declared\n",
            },
            monkeypatch,
        )
        graph = preflight.collect_import_graph(runtime_only=True)
        cycle_modules = {module for cycle in graph["cycles"] for module in cycle["modules"]}
        has_cycle = {
            "polisyos.scientist.a",
            "polisyos.scientist.b",
        }.issubset(cycle_modules)
        assert has_cycle is expect_cycle, name


def test_function_local_variable_annotations_are_not_evaluated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def annotation_import():\n"
                "    from polisyos.scientist import b\n"
                "    return int\n"
                "def declared():\n"
                "    value: annotation_import()\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import declared\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    cycle_modules = {module for cycle in graph["cycles"] for module in cycle["modules"]}
    assert "polisyos.scientist.a" not in cycle_modules


def test_runtime_import_graph_follows_module_time_calls_and_class_bodies_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist import module_bootstrap\n"
                "def _bootstrap():\n"
                "    from polisyos.scientist import direct_call_edge\n"
                "_bootstrap()\n"
                "def _decorate(value):\n"
                "    from polisyos.scientist import decorator_edge\n"
                "    return value\n"
                "@_decorate\n"
                "def decorated():\n"
                "    return None\n"
                "def _default_factory():\n"
                "    from polisyos.scientist import default_edge\n"
                "    return object()\n"
                "def configured(value=_default_factory()):\n"
                "    return value\n"
                "class Registry:\n"
                "    from polisyos.scientist import class_body_edge\n"
                "def _deferred():\n"
                "    from polisyos.scientist import deferred_edge\n"
                "module_bootstrap.register()\n"
            ),
            "polisyos/scientist/module_bootstrap.py": (
                "def register():\n    from polisyos.scientist import imported_call_edge\n"
            ),
            "polisyos/scientist/direct_call_edge.py": "from polisyos.scientist.a import _bootstrap\n",
            "polisyos/scientist/decorator_edge.py": "from polisyos.scientist.a import decorated\n",
            "polisyos/scientist/default_edge.py": "from polisyos.scientist.a import configured\n",
            "polisyos/scientist/class_body_edge.py": "from polisyos.scientist.a import Registry\n",
            "polisyos/scientist/imported_call_edge.py": "from polisyos.scientist.a import configured\n",
            "polisyos/scientist/deferred_edge.py": "from polisyos.scientist.a import configured\n",
        },
        monkeypatch,
    )
    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    source_module = "polisyos.scientist.a"
    assert (source_module, "polisyos.scientist.direct_call_edge") in edges
    assert (source_module, "polisyos.scientist.class_body_edge") in edges
    assert (source_module, "polisyos.scientist.default_edge") in edges
    assert (source_module, "polisyos.scientist.module_bootstrap") in edges
    assert ("polisyos.scientist.module_bootstrap", "polisyos.scientist.imported_call_edge") in edges
    assert (source_module, "polisyos.scientist.deferred_edge") not in edges
    assert "polisyos.scientist.deferred_edge" not in {
        module for cycle in graph["cycles"] for module in cycle["modules"]
    }


def test_runtime_import_graph_normalizes_package_import_spellings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edge_sets: list[set[tuple[str, str]]] = []
    for index, import_statement in enumerate(
        (
            "import polisyos.scientist.pkg.child",
            "from polisyos.scientist.pkg import child",
        )
    ):
        root = tmp_path / str(index)
        _write_runtime_import_fixture(
            root,
            {
                "polisyos/scientist/a.py": f"{import_statement}\nValue = object()\n",
                "polisyos/scientist/pkg/__init__.py": "from ..a import Value\n",
                "polisyos/scientist/pkg/child.py": "Value = object()\n",
            },
            monkeypatch,
        )
        graph = preflight.collect_import_graph(runtime_only=True)
        edge_sets.append({(row["source"], row["target"]) for row in graph["edges"]})
    assert edge_sets[0] == edge_sets[1]
    assert ("polisyos.scientist.a", "polisyos.scientist.pkg") in edge_sets[0]
    assert ("polisyos.scientist.a", "polisyos.scientist.pkg.child") in edge_sets[0]


def test_import_cycle_gate_handles_global_and_match_type_checking_rebindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = {
        "global_write": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def bootstrap():\n"
            "    global TYPE_ONLY\n"
            "    TYPE_ONLY = True\n"
            "bootstrap()\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "nested_global_write": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "def set_type_only():\n"
            "    global TYPE_ONLY\n"
            "    TYPE_ONLY = True\n"
            "def bootstrap():\n"
            "    set_type_only()\n"
            "bootstrap()\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
        "match_capture": (
            "from typing import TYPE_CHECKING as TYPE_ONLY\n"
            "match value:\n"
            "    case TYPE_ONLY:\n"
            "        pass\n"
            "if TYPE_ONLY:\n"
            "    from polisyos.scientist.b import B\n"
        ),
    }
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    for label, a_source in cases.items():
        case_root = tmp_path / label
        _write_runtime_import_fixture(
            case_root,
            {
                "polisyos/scientist/a.py": a_source,
                "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            },
            monkeypatch,
        )
        registry_text = _write_current_full_scc_registry(registry)
        findings = validate_import_cycles()
        assert any(
            finding.message == "registered deferred-cycle signature contains a module-eager cycle"
            for finding in findings
        ), label
        if label != "match_capture":
            edges_before = {
                (row["source"], row["target"])
                for row in preflight.collect_import_graph(runtime_only=True)["edges"]
            }
            assert ("polisyos.scientist.a", "polisyos.scientist.b") in edges_before
            source_path = case_root / "src/polisyos/scientist/a.py"
            source_path.write_text(a_source.replace("bootstrap()\n", "", 1), encoding="utf-8")
            assert "from polisyos.scientist.b import B" in source_path.read_text(encoding="utf-8")
            assert registry.read_text(encoding="utf-8") == registry_text
            edges_after = {
                (row["source"], row["target"])
                for row in preflight.collect_import_graph(runtime_only=True)["edges"]
            }
            assert ("polisyos.scientist.a", "polisyos.scientist.b") not in edges_after
            assert not any(
                finding.message
                == "registered deferred-cycle signature contains a module-eager cycle"
                for finding in validate_import_cycles()
            ), label


def test_runtime_import_graph_revisits_function_after_module_binding_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "def bootstrap():\n"
                "    if TYPE_ONLY:\n"
                "        from polisyos.scientist import edge\n"
                "bootstrap()\n"
                "TYPE_ONLY = True\n"
                "bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import bootstrap\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_resolves_nested_local_calls_by_lexical_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def bootstrap():\n"
                "    def local():\n"
                "        from polisyos.scientist import edge\n"
                "    local()\n"
                "bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import bootstrap\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_joins_all_branch_callable_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    from polisyos.scientist.one import launch as selected\n"
                "else:\n"
                "    from polisyos.scientist.two import launch as selected\n"
                "selected()\n"
            ),
            "polisyos/scientist/one.py": (
                "def launch():\n    from polisyos.scientist import first_edge\n"
            ),
            "polisyos/scientist/two.py": (
                "def launch():\n    from polisyos.scientist import second_edge\n"
            ),
            "polisyos/scientist/first_edge.py": "VALUE = 1\n",
            "polisyos/scientist/second_edge.py": "VALUE = 2\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.one", "polisyos.scientist.first_edge") in edges
    assert ("polisyos.scientist.two", "polisyos.scientist.second_edge") in edges


def test_runtime_import_graph_joins_all_branch_local_function_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def left():\n"
                "    from polisyos.scientist import left_edge\n"
                "def right():\n"
                "    from polisyos.scientist import right_edge\n"
                "if runtime_flag:\n"
                "    selected = left\n"
                "else:\n"
                "    selected = right\n"
                "selected()\n"
            ),
            "polisyos/scientist/left_edge.py": "VALUE = 1\n",
            "polisyos/scientist/right_edge.py": "VALUE = 2\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") in edges


def test_runtime_import_graph_resolves_local_class_method_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        cls.load()\n"
                "    @classmethod\n"
                "    def load(cls):\n"
                "        from polisyos.scientist import edge\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_keeps_same_name_branch_definitions_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    def selected():\n"
                "        from polisyos.scientist import edge\n"
                "else:\n"
                "    def selected():\n"
                "        return\n"
                "selected()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import selected\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_resolves_branch_definition_set_across_module_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import selected\nselected()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "if runtime_flag:\n"
                "    def selected():\n"
                "        from polisyos.scientist import edge\n"
                "else:\n"
                "    def selected():\n"
                "        return\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.implementation") in edges
    assert ("polisyos.scientist.implementation", "polisyos.scientist.edge") in edges


def test_runtime_import_graph_resolves_cross_module_source_order_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import selected\nselected()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "def selected():\n"
                "    from polisyos.scientist import edge\n"
                "def selected():\n"
                "    return\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.implementation") in edges
    assert ("polisyos.scientist.implementation", "polisyos.scientist.edge") not in edges


def test_runtime_import_graph_applies_proven_unconditional_definition_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "def selected():\n"
                "    from polisyos.scientist import edge\n"
                "def selected():\n"
                "    return\n"
                "selected()\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") not in edges


def test_runtime_import_graph_preserves_class_receiver_in_noarg_nested_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        def nested():\n"
                "            cls.load()\n"
                "        nested()\n"
                "    @classmethod\n"
                "    def load(cls):\n"
                "        from polisyos.scientist import edge\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


@pytest.mark.parametrize(
    "entry_call",
    [
        "Entry().boot()\n",
        "entry = Entry()\nentry.boot()\n",
        "EntryAlias = Entry\nentry = EntryAlias()\nentry.boot()\n",
    ],
)
def test_import_cycle_gate_rejects_named_instance_method_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_call: str,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import edge\n"
                f"{entry_call}"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        and "polisyos.scientist.a" in finding.detail
        and "polisyos.scientist.edge" in finding.detail
        for finding in findings
    )

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "class Entry:\n    def boot(self):\n        from polisyos.scientist import edge\n",
        encoding="utf-8",
    )
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_resolves_imported_class_instances_and_constructors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cycle_modules = [
        "polisyos.scientist.a",
        "polisyos.scientist.implementation",
        "polisyos.scientist.init_edge",
        "polisyos.scientist.method_edge",
        "polisyos.scientist.new_edge",
    ]
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from polisyos.scientist.implementation import Entry as CandidateEntry\n"
                "candidate = CandidateEntry()\n"
                "candidate.boot()\n"
            ),
            "polisyos/scientist/implementation.py": (
                "class Entry:\n"
                "    def __new__(cls):\n"
                "        from polisyos.scientist import new_edge\n"
                "        return object.__new__(cls)\n"
                "    def __init__(self):\n"
                "        from polisyos.scientist import init_edge\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import method_edge\n"
            ),
            "polisyos/scientist/init_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
            "polisyos/scientist/method_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
            "polisyos/scientist/new_edge.py": "from polisyos.scientist.a import CandidateEntry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    runtime_edges = {(row["source"], row["target"]) for row in runtime_graph["edges"]}
    assert runtime_edges >= {
        ("polisyos.scientist.a", "polisyos.scientist.implementation"),
        ("polisyos.scientist.implementation", "polisyos.scientist.new_edge"),
        ("polisyos.scientist.implementation", "polisyos.scientist.init_edge"),
        ("polisyos.scientist.implementation", "polisyos.scientist.method_edge"),
        ("polisyos.scientist.new_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.init_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.method_edge", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    eager = [
        finding
        for finding in findings
        if finding.message == "registered deferred-cycle signature contains a module-eager cycle"
    ]
    assert len(eager) == 1
    assert all(module in eager[0].detail for module in cycle_modules)

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "from polisyos.scientist.implementation import Entry as CandidateEntry\n",
        encoding="utf-8",
    )
    source_after = (tmp_path / "src/polisyos/scientist/a.py").read_text(encoding="utf-8")
    assert "from polisyos.scientist.implementation import Entry as CandidateEntry" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_joins_named_instance_sets_and_follows_both_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Left:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import left_edge\n"
                "class Right:\n"
                "    def boot(self):\n"
                "        from polisyos.scientist import right_edge\n"
                "if runtime_flag:\n"
                "    selected = Left()\n"
                "else:\n"
                "    selected = Right()\n"
                "selected.boot()\n"
            ),
            "polisyos/scientist/left_edge.py": "from polisyos.scientist.a import Left\n",
            "polisyos/scientist/right_edge.py": "from polisyos.scientist.a import Right\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()
    assert [(finding.message, finding.detail) for finding in findings] == [
        (
            "registered deferred-cycle signature contains a module-eager cycle",
            "polisyos.scientist.a, polisyos.scientist.left_edge, polisyos.scientist.right_edge",
        )
    ]
    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    eager_targets = {
        edge["target"]
        for edge in runtime_graph["edges"]
        if edge["source"] == "polisyos.scientist.a"
    }
    assert eager_targets == {
        "polisyos.scientist.left_edge",
        "polisyos.scientist.right_edge",
    }

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_text = source_path.read_text(encoding="utf-8")
    source_path.write_text(source_text.replace("selected.boot()\n", "", 1), encoding="utf-8")
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in source_after
    assert "from polisyos.scientist import right_edge" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_follows_source_defined_new_and_init_constructors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    def __new__(cls):\n"
                "        from polisyos.scientist import new_edge\n"
                "        return object.__new__(cls)\n"
                "    def __init__(self):\n"
                "        from polisyos.scientist import init_edge\n"
                "Entry()\n"
            ),
            "polisyos/scientist/new_edge.py": "from polisyos.scientist.a import Entry\n",
            "polisyos/scientist/init_edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    runtime_graph = preflight.collect_import_graph(runtime_only=True)
    runtime_edges = {(row["source"], row["target"]) for row in runtime_graph["edges"]}
    assert runtime_edges >= {
        ("polisyos.scientist.a", "polisyos.scientist.new_edge"),
        ("polisyos.scientist.a", "polisyos.scientist.init_edge"),
        ("polisyos.scientist.new_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.init_edge", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    eager_details = [
        finding.detail
        for finding in findings
        if finding.message == "registered deferred-cycle signature contains a module-eager cycle"
    ]

    assert eager_details == [
        "polisyos.scientist.a, polisyos.scientist.init_edge, polisyos.scientist.new_edge"
    ]

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "class Entry:\n"
        "    def __new__(cls):\n"
        "        from polisyos.scientist import new_edge\n"
        "        return object.__new__(cls)\n"
        "    def __init__(self):\n"
        "        from polisyos.scientist import init_edge\n",
        encoding="utf-8",
    )
    source_after = (tmp_path / "src/polisyos/scientist/a.py").read_text(encoding="utf-8")
    assert "from polisyos.scientist import new_edge" in source_after
    assert "from polisyos.scientist import init_edge" in source_after
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_runtime_import_graph_joins_same_name_branch_class_methods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Entry:\n"
                "    if runtime_flag:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            from polisyos.scientist import edge\n"
                "    else:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            return\n"
                "    @classmethod\n"
                "    def bootstrap(cls):\n"
                "        cls.load()\n"
                "Entry.bootstrap()\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges
    assert ("polisyos.scientist.edge", "polisyos.scientist.a") in edges


def test_runtime_import_graph_joins_branch_defined_class_method_sets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "if runtime_flag:\n"
                "    class Entry:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            from polisyos.scientist import edge\n"
                "else:\n"
                "    class Entry:\n"
                "        @classmethod\n"
                "        def load(cls):\n"
                "            return\n"
                "Entry.load()\n"
            ),
            "polisyos/scientist/edge.py": "VALUE = 1\n",
        },
        monkeypatch,
    )

    graph = preflight.collect_import_graph(runtime_only=True)
    edges = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in edges


def test_import_cycle_gate_rejects_new_unregistered_deferred_scc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    from polisyos.scientist.a import A\n"
            ),
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text("[lazy_imports]\nversion = 1\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    findings = validate_import_cycles()
    assert any(
        finding.message == "new import cycle without deferred-cycle registration"
        and "polisyos.scientist.a" in finding.detail
        and "polisyos.scientist.b" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    ("bad_bytes", "expected_outcome"),
    [
        (b"def broken(:\n    pass\n", "parse_error"),
        (b"value = \xff\n", "decode_error"),
    ],
)
def test_import_cycle_scan_preserves_partial_cycles_and_parse_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_bytes: bytes,
    expected_outcome: str,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
        },
        monkeypatch,
    )
    bad_path = tmp_path / "src/polisyos/scientist/broken.py"
    bad_path.write_bytes(bad_bytes)
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text(
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    snapshot = preflight._collect_import_source_snapshot()
    graph = preflight.collect_import_graph(
        source_snapshot=snapshot,
        allow_incomplete=True,
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.b"] in [
        cycle["modules"] for cycle in graph["cycles"]
    ]
    finding = next(
        finding
        for finding in validate_import_cycles(source_snapshot=snapshot)
        if finding.message == "selected source input is incomplete"
    )
    assert "src/polisyos/scientist/broken.py" in finding.detail
    assert f"[{expected_outcome}]" in finding.detail
    manifest_row = next(
        row for row in snapshot.input_manifest if row["path"] == "src/polisyos/scientist/broken.py"
    )
    assert manifest_row["outcome"] == expected_outcome
    assert manifest_row["sha256"] == hashlib.sha256(bad_bytes).hexdigest()


def test_import_cycle_scan_records_portable_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "from typing import TYPE_CHECKING as TYPE_ONLY\n"
                "if TYPE_ONLY:\n"
                "    from polisyos.scientist.b import B\n"
            ),
            "polisyos/scientist/b.py": "from polisyos.scientist.a import A\n",
            "polisyos/scientist/unreadable.py": "VALUE = 1\n",
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text(
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    real_reader = preflight._read_import_source_bytes
    unreadable = tmp_path / "src/polisyos/scientist/unreadable.py"

    def controlled_reader(path: Path) -> bytes:
        if path == unreadable:
            raise OSError("controlled read failure")
        return real_reader(path)

    monkeypatch.setattr(preflight, "_read_import_source_bytes", controlled_reader)
    snapshot = preflight._collect_import_source_snapshot()
    graph = preflight.collect_import_graph(source_snapshot=snapshot, allow_incomplete=True)

    assert ["polisyos.scientist.a", "polisyos.scientist.b"] in [
        cycle["modules"] for cycle in graph["cycles"]
    ]
    finding = next(
        finding
        for finding in validate_import_cycles(source_snapshot=snapshot)
        if finding.message == "selected source input is incomplete"
    )
    assert "src/polisyos/scientist/unreadable.py [read_error]" in finding.detail
    assert "controlled read failure" in finding.detail


def test_gate_cli_emits_complete_import_input_receipt_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": "VALUE = 1\n",
            "polisyos/scientist/b.py": "VALUE = 2\n",
        },
        monkeypatch,
    )
    bad_path = tmp_path / "src/polisyos/scientist/b.py"
    bad_bytes = b"def broken(:\n    pass\n"
    bad_path.write_bytes(bad_bytes)
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    lazy_registry.write_text("[lazy_imports]\nversion = 1\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)
    monkeypatch.setattr(preflight, "validate_dynamic_imports", lambda: [])
    monkeypatch.setattr(preflight, "validate_pickle_fixtures", lambda: [])
    monkeypatch.setattr(preflight, "validate_public_surface_snapshot", lambda: [])
    monkeypatch.setattr(preflight, "validate_schema_diff", lambda: [])
    monkeypatch.setattr(preflight, "validate_reexport_shim_shapes", lambda: [])
    monkeypatch.setattr(preflight, "validate_import_time_regression", lambda **_: [])
    output_path = tmp_path / "gate-output.json"

    exit_code = preflight.main(["gate", "--output-json", str(output_path)])

    assert exit_code == 1
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    receipt = payload["import_graph_input_receipt"]
    assert payload["status"] == "failed"
    assert receipt["coverage_status"] == "partial"
    assert receipt["selected_count"] == 2
    assert receipt["outcome_counts"] == {"parse_error": 1, "parsed": 1}
    assert {row["path"] for row in receipt["input_manifest"]} == {
        "src/polisyos/scientist/a.py",
        "src/polisyos/scientist/b.py",
    }
    bad_row = next(row for row in receipt["input_manifest"] if row["path"].endswith("/b.py"))
    assert bad_row["sha256"] == hashlib.sha256(bad_bytes).hexdigest()
    assert bad_row["outcome"] == "parse_error"
    stdout = capsys.readouterr().out
    assert "input_manifest_sha256" in stdout
    assert all(row["path"] in stdout for row in receipt["input_manifest"])
    assert all(row["sha256"] in stdout for row in receipt["input_manifest"])


def test_phase3a_generator_refuses_incomplete_import_input_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {"polisyos/scientist/broken.py": "def broken(:\n    pass\n"},
        monkeypatch,
    )
    generated_root = tmp_path / "generated"
    monkeypatch.setattr(preflight, "BASELINE_DIR", generated_root)

    with pytest.raises(preflight.ImportGraphInputError, match="parse_error"):
        preflight.write_phase3a_artifacts(include_import_time=False)
    assert not generated_root.exists()

    exit_code = preflight.main(["generate", "--skip-import-time"])
    stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "NOT generated" in stdout
    assert "src/polisyos/scientist/broken.py" in stdout
    assert "parse_error" in stdout
    assert hashlib.sha256(b"def broken(:\n    pass\n").hexdigest() in stdout
    assert not generated_root.exists()


def test_reexport_shim_shape_gate_forbids_star_import_shims() -> None:
    findings = validate_reexport_shim_shapes()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_import_time_regression_gate_has_phase3a_baseline() -> None:
    baseline = (
        REPO_ROOT
        / "architecture"
        / "baselines"
        / "structure_remediation"
        / "import_time_pre_decomp.json"
    )

    assert baseline.exists()
    if os.environ.get("POLISYOS_RUN_IMPORT_TIME_GATE") == "1":
        findings = validate_import_time_regression(live=True)
        assert findings == [], "\n".join(finding.render() for finding in findings)


def test_phase5_scientist_root_facade_has_no_loose_python_modules() -> None:
    scientist_root = REPO_ROOT / "src" / "polisyos" / "scientist"
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text())
    registered_root_shims = {
        Path(shim["source_path"]).name
        for shim in shims["shim"]
        if shim.get("type") == "python_reexport"
        and Path(shim.get("source_path", "")).parent == Path("src/polisyos/scientist")
    }
    root_py_files = sorted(path.name for path in scientist_root.glob("*.py"))
    non_shim_root_py_files = [name for name in root_py_files if name not in registered_root_shims]
    top_level_entries = [path for path in scientist_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "scientist",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert non_shim_root_py_files == ["__init__.py", "api.py"]
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_phase6_foundry_root_facade_stays_within_loose_python_budget() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    root_py_files = sorted(path.name for path in foundry_root.glob("*.py"))
    top_level_entries = [path for path in foundry_root.iterdir() if path.name != "__pycache__"]
    gate_result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "loose_files",
            "--mode",
            "fail-closed",
            "--package",
            "foundry",
            "--scope",
            "root",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert "__init__.py" in root_py_files
    assert "api.py" in root_py_files
    assert len(root_py_files) <= 5
    assert len(top_level_entries) <= 250
    assert gate_result.returncode == 0, gate_result.stdout + gate_result.stderr


def test_import_graph_baseline_records_phase3a_collector_contract() -> None:
    baseline = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "import_graph_pre_decomp.json"
        ).read_text(encoding="utf-8")
    )

    assert baseline["collector_mode"] == "internal_ast_import_graph"
    assert "pydeps_available" in baseline
    assert "import_linter_available" in baseline


def test_pickle_inventory_includes_canonical_checkpoint_fixtures() -> None:
    inventory = json.loads(
        (
            REPO_ROOT
            / "architecture"
            / "baselines"
            / "structure_remediation"
            / "pickle_checkpoint_inventory.json"
        ).read_text(encoding="utf-8")
    )
    artifacts = {artifact["path"] for artifact in inventory["live_artifacts"]}
    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "tests" / "_data" / "checkpoint_compat").glob("*/*.json"))
    ]

    assert "tests/_data/checkpoint_compat/foundry/agent_sim_experiment_result.pkl" in artifacts
    assert "tests/_data/checkpoint_compat/scientist/engine_checkpoint_artifact.pkl" in artifacts
    assert {manifest["producer"] for manifest in manifests} == {
        "polisyos.foundry.agent_sim.experiment.ExperimentRun.log_artifact",
        "polisyos.scientist.orchestration.engine.checkpoint.create_checkpoint/load_checkpoint",
    }


def test_phase3a_gate_registry_lists_new_decomposition_gates() -> None:
    gates = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "structure_remediation.toml").read_text(
            encoding="utf-8"
        )
    )
    gate_ids = {gate["id"] for gate in gates["gate"]}

    assert {
        "dynamic_imports_gate",
        "pickle_compat_gate",
        "public_surface_snapshot_gate",
        "import_cycles_gate",
        "import_time_regression_gate",
        "reexport_shim_shape_gate",
    } <= gate_ids


def test_phase4_1_foundry_executor_lane_closes_legacy_private_siblings() -> None:
    foundry_root = REPO_ROOT / "src" / "polisyos" / "foundry"
    removed_private_siblings = {
        "_execution_posture",
        "_executor_graph",
        "_executor_models",
        "_executor_ops",
        "_executor_patching",
        "_executor_snapshots",
        "_numeric",
    }

    assert {
        path.name for path in foundry_root.iterdir() if path.name in removed_private_siblings
    } == set()

    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))[
        "shim"
    ]
    shim_sources = {shim["source_path"] for shim in shims}
    dynamic_sources = {
        entry["source_file"]
        for entry in tomllib.loads(
            (REPO_ROOT / "architecture" / "imports" / "dynamic.toml").read_text(encoding="utf-8")
        )["pattern"]
    }
    removed_source_paths = {
        f"src/polisyos/foundry/{name}/__init__.py" for name in removed_private_siblings
    }
    executor_cycle_markers = (
        "polisyos.foundry.execute",
        "polisyos.foundry.runtime.numeric",
    )

    assert shim_sources.isdisjoint(removed_source_paths)
    assert dynamic_sources.isdisjoint(removed_source_paths)
    assert [
        finding
        for finding in validate_dynamic_imports()
        if "src/polisyos/foundry/execute" in finding.detail
        or "src/polisyos/foundry/executor" in finding.detail
        or any(path in finding.detail for path in removed_source_paths)
    ] == []
    assert [
        finding
        for finding in validate_import_cycles()
        if any(marker in finding.detail for marker in executor_cycle_markers)
    ] == []


def test_move_module_codemod_dry_run_plans_synthetic_world_move() -> None:
    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            str(script),
            "--from",
            "polisyos.foundry.agent_sim.world.world",
            "--to",
            "polisyos.foundry.agent_sim.world.runtime.world",
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "polisyos.foundry.agent_sim.world.runtime.world" in result.stdout
    assert '"src/polisyos/foundry/agent_sim/world/runtime/__init__.py"' in result.stdout


def test_move_module_codemod_rewrites_parent_leaf_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "polisyos" / "example"
    source_dir.mkdir(parents=True)
    (repo / "architecture").mkdir()
    (repo / "src" / "polisyos" / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("class Public:\n    pass\n", encoding="utf-8")
    (source_dir / "consumer.py").write_text(
        "from polisyos.example import old\nfrom polisyos.example.old import Public\n",
        encoding="utf-8",
    )
    (repo / "architecture" / "shims.toml").write_text("", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo),
            "--from",
            "polisyos.example.old",
            "--to",
            "polisyos.example.new.old",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (source_dir / "new" / "__init__.py").exists()
    assert (source_dir / "new" / "old.py").exists()
    assert "from polisyos.example.new import old" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert "from polisyos.example.new.old import Public" in (source_dir / "consumer.py").read_text(
        encoding="utf-8"
    )
    assert not (source_dir / "old.py").exists()
    shim = (source_dir / "old" / "__init__.py").read_text(encoding="utf-8")
    assert "import *" not in shim


@pytest.mark.skipif(
    os.name != "posix", reason="POSIX subprocess lookup honors cwd for PATH entries"
)
@pytest.mark.parametrize(
    ("path_mode", "expected_shim"),
    [
        ("relative", "repo-bin"),
        ("empty", "repo-root"),
        ("absolute", "absolute-first"),
        ("unset", None),
    ],
)
def test_move_module_git_lookup_preserves_child_cwd_path_search(
    tmp_path: Path, path_mode: str, expected_shim: str | None
) -> None:
    real_git_command = shutil.which("git")
    if real_git_command is None:
        pytest.skip("git is required for the move-module integration test")
    real_git = str(Path(real_git_command).resolve(strict=True))
    if path_mode == "unset" and shutil.which("git", path=os.defpath) is None:
        pytest.skip("git is not available on the platform default PATH")

    repo = tmp_path / "repo"
    caller = tmp_path / "caller"
    caller.mkdir()
    source_dir = repo / "src" / "polisyos" / "example"
    source_dir.mkdir(parents=True)
    (repo / "architecture").mkdir()
    (repo / "src" / "polisyos" / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")
    (source_dir / "old.py").write_text("class Public:\n    pass\n", encoding="utf-8")
    (repo / "architecture" / "shims.toml").write_text("", encoding="utf-8")

    marker = tmp_path / "selected-git-shim.txt"

    def install_git_shim(directory: Path, label: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        executable = directory / "git"
        executable.write_text(
            "#!/bin/sh\n"
            f"printf '%s' {shlex.quote(label)} > \"$GIT_SHIM_MARKER\"\n"
            f'exec {shlex.quote(real_git)} "$@"\n',
            encoding="utf-8",
        )
        executable.chmod(0o755)

    env = os.environ.copy()
    env["GIT_SHIM_MARKER"] = str(marker)
    if path_mode == "relative":
        install_git_shim(repo / "bin", "repo-bin")
        install_git_shim(caller / "bin", "caller-bin")
        env["PATH"] = "bin"
    elif path_mode == "empty":
        install_git_shim(repo, "repo-root")
        install_git_shim(caller, "caller-root")
        env["PATH"] = ""
    elif path_mode == "absolute":
        install_git_shim(repo / "absolute-first", "absolute-first")
        install_git_shim(caller / "absolute-second", "absolute-second")
        env["PATH"] = os.pathsep.join(
            (str(repo / "absolute-first"), str(caller / "absolute-second"))
        )
    else:
        env.pop("PATH", None)

    subprocess.run([real_git, "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run([real_git, "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    script = REPO_ROOT / "tools" / "devx" / "refactor" / "move_module.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo-root",
            str(repo),
            "--from",
            "polisyos.example.old",
            "--to",
            "polisyos.example.new.old",
        ],
        cwd=caller,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (repo / "src" / "polisyos" / "example" / "new" / "old.py").exists()
    if expected_shim is None:
        assert not marker.exists()
    else:
        assert marker.read_text(encoding="utf-8") == expected_shim


@pytest.mark.parametrize(
    ("scenario", "class_source", "property_call", "expected_reason"),
    [
        (
            "factory_return",
            "class Entry:\n"
            "    def boot(self):\n"
            "        from polisyos.scientist import edge\n"
            "def make():\n"
            "    return Entry()\n",
            "make().boot()",
            "source_callable_return_not_summarized",
        ),
        (
            "custom_new_replacement",
            "class Replacement:\n"
            "    def boot(self):\n"
            "        from polisyos.scientist import edge\n"
            "class Entry:\n"
            "    def __new__(cls):\n"
            "        return Replacement()\n",
            "Entry().boot()",
            "source_derived_receiver_not_summarized",
        ),
    ],
)
def test_import_cycle_gate_fails_closed_for_unresolved_source_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    class_source: str,
    property_call: str,
    expected_reason: str,
) -> None:
    a_source = (
        class_source
        + "class ResolvedReceiver:\n"
        + "    def ping(self):\n"
        + "        return None\n"
        + property_call
        + "\nResolvedReceiver().ping()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    eager_graph = preflight.collect_import_graph(runtime_only=True)
    receipt = eager_graph["dispatch_resolution"]
    assert receipt["status"] == "not_established", scenario
    assert receipt["unmodeled_dispatch_forms"] == [
        {
            "form": "reflective_or_callback_valued_receiver",
            "status": "not_established",
            "reason": "no source-resolved target is available for enumeration",
        }
    ], scenario
    assert receipt["unresolved_count"] == 1, scenario
    assert receipt["resolved_count"] == 1, scenario
    assert {row["status"] for row in receipt["observations"]} == {
        "resolved",
        "not_established",
    }, scenario
    unresolved = receipt["unresolved"][0]
    assert unresolved["status"] == "not_established", scenario
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py", scenario
    assert unresolved["expression"] == property_call, scenario
    assert unresolved["reason"] == expected_reason, scenario

    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ], scenario
    findings = validate_import_cycles()
    unresolved_findings = [
        finding
        for finding in findings
        if finding.message == "module-time source-known dispatch is not established"
    ]
    assert len(unresolved_findings) == 1, scenario
    assert expected_reason in unresolved_findings[0].detail, scenario

    # Remove only the module-time dispatch. The cycle source, reciprocal edge, and
    # exact deferred-SCC registration remain in place as the negative control.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace(property_call + "\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after_graph = preflight.collect_import_graph(runtime_only=True)
    after_receipt = after_graph["dispatch_resolution"]
    assert after_receipt["status"] == "resolved_within_scope", scenario
    assert after_receipt["unresolved_count"] == 0, scenario
    assert after_receipt["resolved_count"] == 1, scenario
    assert after_receipt["observations"][0]["status"] == "resolved", scenario
    assert after_receipt["unresolved"] == [], scenario
    assert validate_import_cycles() == [], scenario
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ], scenario


def test_import_cycle_gate_resolves_source_inherited_method_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Base:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry(Base):\n"
        "    pass\n"
        "Entry().boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    inherited = next(
        row for row in receipt["observations"] if row["expression"] == "Entry().boot()"
    )
    assert inherited["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Base.boot@")
        for target in inherited["known_source_targets"]
    )
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in {
        (row["source"], row["target"]) for row in graph["edges"]
    }
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Remove only the inherited method invocation; keep both import markers and
    # the exact full-AST SCC registration to prove the gate's runtime edge.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry().boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") not in {
        (row["source"], row["target"]) for row in after["edges"]
    }
    assert after["dispatch_resolution"]["unresolved"] == []
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


@pytest.mark.parametrize(
    ("binding_setup", "property_call"),
    [
        ("", "make().child.boot()"),
        ("selected = make()\n", "selected.child.boot()"),
        ("selected = [make()]\n", "selected[0].boot()"),
        (
            "if runtime_flag:\n    selected = Entry()\nelse:\n    selected = make()\n",
            "selected.boot()",
        ),
        (
            "class Namespace:\n    selected = make()\n",
            "Namespace.selected.child.boot()",
        ),
    ],
)
def test_import_cycle_gate_preserves_source_origins_through_expression_transforms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_setup: str,
    property_call: str,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Entry()\n"
        "runtime_flag = False\n" + binding_setup + property_call + "\n"
    )
    edge_source = "from polisyos.scientist.a import make\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    unresolved = next(row for row in receipt["unresolved"] if row["expression"] == property_call)
    assert receipt["status"] == "not_established"
    assert unresolved["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
    }
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py"
    if "selected = Entry()" in binding_setup:
        assert any(
            target.startswith("polisyos.scientist.a.Entry.boot@")
            for target in unresolved["known_source_targets"]
        )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace(property_call + "\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved"] == []
    assert after["status"] == "resolved_within_scope"
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


@pytest.mark.parametrize(
    ("setup", "property_statement", "without_property_statement", "property_call"),
    [
        (
            "selected = [(make(), None)]\n",
            "for item, ignored in selected:\n    item.boot()\n",
            "for item, ignored in selected:\n    pass\n",
            "item.boot()",
        ),
        (
            "import asyncio\nasync def values():\n    yield make()\nasync def exercise():\n",
            "    async for item in values():\n        item.boot()\nasyncio.run(exercise())\n",
            "    async for item in values():\n        pass\nasyncio.run(exercise())\n",
            "item.boot()",
        ),
        (
            "",
            "with Manager() as item:\n    item.boot()\n",
            "with Manager() as item:\n    pass\n",
            "item.boot()",
        ),
        (
            "import asyncio\nasync def exercise():\n",
            "    async with AsyncManager() as item:\n        item.boot()\n"
            "asyncio.run(exercise())\n",
            "    async with AsyncManager() as item:\n        pass\nasyncio.run(exercise())\n",
            "item.boot()",
        ),
        (
            "",
            "try:\n    pass\nexcept EntryError as item:\n    item.boot()\n",
            "try:\n    pass\nexcept EntryError as item:\n    pass\n",
            "item.boot()",
        ),
        (
            "",
            "match make():\n    case item:\n        item.boot()\n",
            "match make():\n    case item:\n        pass\n",
            "item.boot()",
        ),
        (
            "",
            "match [make()]:\n    case [item]:\n        item.boot()\n",
            "match [make()]:\n    case [item]:\n        pass\n",
            "item.boot()",
        ),
        (
            "selected = [make()]\n",
            "selected += []\nselected[0].boot()\n",
            "selected += []\nselected[0]\n",
            "selected[0].boot()",
        ),
        (
            "selected: list[object] = [make()]\n",
            "selected[0].boot()\n",
            "selected[0]\n",
            "selected[0].boot()",
        ),
        (
            "",
            "if (selected := [make()]):\n    selected[0].boot()\n",
            "if (selected := [make()]):\n    selected[0]\n",
            "selected[0].boot()",
        ),
        (
            "class KnownOwner:\n    def ready(self):\n        return None\n"
            "holder = KnownOwner()\nholder.value = make()\n",
            "holder.ready()\nholder.value.boot()\n",
            "holder.ready()\nholder.value\n",
            "holder.value.boot()",
        ),
        (
            "holder = {}\nholder['value'] = make()\n",
            "holder['value'].boot()\n",
            "holder['value']\n",
            "holder['value'].boot()",
        ),
        (
            "from types import SimpleNamespace\n",
            "SimpleNamespace().value = make()\n",
            "pass\n",
            "SimpleNamespace().value",
        ),
        (
            "",
            "calls = {0: item.boot() for item in [make()]}\n",
            "calls = {0: item for item in [make()]}\n",
            "item.boot()",
        ),
        (
            "",
            "calls = [item.boot() for item in [make()]]\nitem.boot()\n",
            "calls = [item for item in [make()]]\nitem.boot()\n",
            "item.boot()",
        ),
    ],
)
def test_import_cycle_gate_preserves_provenance_at_unknown_binding_sinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    setup: str,
    property_statement: str,
    without_property_statement: str,
    property_call: str,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Entry()\n"
        "class Manager:\n"
        "    def __enter__(self):\n"
        "        return Entry()\n"
        "    def __exit__(self, *args):\n"
        "        return False\n"
        "class AsyncManager:\n"
        "    async def __aenter__(self):\n"
        "        return Entry()\n"
        "    async def __aexit__(self, *args):\n"
        "        return False\n"
        "class EntryError(Exception):\n"
        "    pass\n" + setup + property_statement
    )
    edge_source = "from polisyos.scientist.a import make\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    unresolved = [row for row in receipt["unresolved"] if row["expression"] == property_call]
    assert len(unresolved) == 1
    assert receipt["status"] == "not_established"
    assert unresolved[0]["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
        "source_derived_binding_target_not_summarized",
    }
    if "holder = KnownOwner()" in setup:
        ready = next(
            row for row in receipt["observations"] if row["expression"] == "holder.ready()"
        )
        assert ready["status"] == "resolved"
        assert any(
            target.startswith("polisyos.scientist.a.KnownOwner.ready@")
            for target in ready["known_source_targets"]
        )
    assert unresolved[0]["source_path"] == "src/polisyos/scientist/a.py"
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace(property_statement, without_property_statement, 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved"] == []
    assert after["status"] == "resolved_within_scope"
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_rejects_rebound_method_receiver_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def boot(self):\n"
        "        def nested():\n"
        "            self = make()\n"
        "            self.load()\n"
        "        nested()\n"
        "    def load(self):\n"
        "        return None\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make():\n"
        "    return Replacement()\n"
        "Entry().boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["resolved_count"] == 1
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["expression"] == "self.load()"
    assert unresolved["reason"] == "source_callable_return_not_summarized"
    assert not any(
        target.startswith("polisyos.scientist.a.make@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        origin.startswith("polisyos.scientist.a.make@")
        for origin in unresolved["source_value_origins"]
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "source_callable_return_not_summarized" in finding.detail
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("            self.load()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["status"] == "resolved_within_scope"
    assert after["unresolved_count"] == 0
    assert after["resolved_count"] == 1
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_executes_both_joined_known_receiver_methods_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import left_edge\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import right_edge\n"
        "def nested(flag, inherited):\n"
        "    if flag:\n"
        "        selected = Entry()\n"
        "    else:\n"
        "        selected = inherited\n"
        "    selected.load()\n"
        "nested(False, Replacement())\n"
    )
    left_edge_source = "from polisyos.scientist.a import Entry\n"
    right_edge_source = "from polisyos.scientist.a import Replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert before["dispatch_resolution"]["status"] == "resolved_within_scope"
    assert before["dispatch_resolution"]["unresolved"] == []
    assert {
        ("polisyos.scientist.a", "polisyos.scientist.left_edge"),
        ("polisyos.scientist.a", "polisyos.scientist.right_edge"),
        ("polisyos.scientist.left_edge", "polisyos.scientist.a"),
        ("polisyos.scientist.right_edge", "polisyos.scientist.a"),
    } <= edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("    selected.load()\n", "    pass\n", 1), encoding="utf-8"
    )
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in source_after
    assert "from polisyos.scientist import right_edge" in source_after
    assert left_edge_source == (tmp_path / "src/polisyos/scientist/left_edge.py").read_text(
        encoding="utf-8"
    )
    assert right_edge_source == (tmp_path / "src/polisyos/scientist/right_edge.py").read_text(
        encoding="utf-8"
    )
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert after["dispatch_resolution"]["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_binds_callee_before_argument_side_effects_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def first():\n"
        "    global handler\n"
        "    handler = replacement\n"
        "    return None\n"
        "def handler(value=None):\n"
        "    from polisyos.scientist import first_edge\n"
        "def replacement(value=None):\n"
        "    from polisyos.scientist import second_edge\n"
        "handler(first())\n"
        "handler()\n"
    )
    first_edge_source = "from polisyos.scientist.a import handler\n"
    second_edge_source = "from polisyos.scientist.a import replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/first_edge.py": first_edge_source,
            "polisyos/scientist/second_edge.py": second_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.first_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.second_edge") in edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    after_source = a_source.replace("handler(first())\n", "", 1)
    after_source = after_source.replace("handler()\n", "replacement()\n", 1)
    source_path.write_text(after_source, encoding="utf-8")
    source_after = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import first_edge" in source_after
    assert "from polisyos.scientist import second_edge" in source_after
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.first_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.second_edge") in edges_after
    assert ("polisyos.scientist.first_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.second_edge", "polisyos.scientist.a") in edges_after


def test_import_cycle_gate_rejects_unresolved_source_base_constructor_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Base:\n"
        "    def __init__(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry(Base):\n"
        "    pass\n"
        "Entry()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["expression"] == "Entry()"
    assert unresolved["reason"] == "source_class_base_constructor_lookup_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.a.Base.__init__@")
        for target in unresolved["known_source_targets"]
    )
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "source_class_base_constructor_lookup_not_summarized" in finding.detail
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["status"] == "resolved_within_scope"
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_rejects_joined_known_and_unknown_receiver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def load(self):\n"
        "        return None\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import edge\n"
        "def nested(flag, inherited):\n"
        "    if flag:\n"
        "        selected = Entry()\n"
        "    else:\n"
        "        selected = inherited\n"
        "    selected.load()\n"
        "def source_factory():\n"
        "    return Replacement()\n"
        "nested(False, source_factory())\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert receipt["status"] == "not_established"
    assert receipt["unresolved_count"] == 1
    unresolved = receipt["unresolved"][0]
    assert unresolved["source_path"] == "src/polisyos/scientist/a.py"
    assert unresolved["expression"] == "selected.load()"
    assert unresolved["reason"] in {
        "source_possible_unknown_target",
        "source_callable_return_not_summarized",
    }
    assert any(
        target.startswith("polisyos.scientist.a.Entry.load@")
        for target in unresolved["known_source_targets"]
    )
    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ]
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and finding.message == "module-time source-known dispatch is not established"
        and unresolved["source_path"] in finding.detail
        and unresolved["expression"] in finding.detail
        and f"[{unresolved['reason']}]" in finding.detail
        for finding in findings
    )

    # Keep both imports and the exact SCC registration while removing only the
    # dispatch whose joined binding carries an unknown possibility.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("    selected.load()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_preserves_complete_exported_member_knowledge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def inert():\n"
        "    return None\n"
        "class Handler:\n"
        "    def __call__(self):\n"
        "        from polisyos.scientist import edge\n"
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def invoke_callback(callback):\n"
        "    callback()\n"
        "runtime_flag = False\n"
        "class Entry:\n"
        "    if runtime_flag:\n"
        "        load = inert\n"
        "    else:\n"
        "        load = Handler()\n"
    )
    relay_source = "from polisyos.scientist.a import Entry as RoutedEntry\n"
    caller_source = (
        "from polisyos.scientist.relay import RoutedEntry\n"
        "from polisyos.scientist.a import Handler\n"
        "def inert():\n"
        "    return None\n"
        "class Opaque:\n"
        "    pass\n"
        "runtime_flag = False\n"
        "class Partial:\n"
        "    if runtime_flag:\n"
        "        load = inert\n"
        "    else:\n"
        "        load = Opaque()\n"
        "RoutedEntry().load()\n"
        "Handler()()\n"
        "Partial().load()\n"
    )
    edge_source = "from polisyos.scientist.a import Entry\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/relay.py": relay_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    routed = next(
        row for row in receipt["observations"] if row["expression"] == "RoutedEntry().load()"
    )
    assert routed["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Handler.__call__@")
        for target in routed["known_source_targets"]
    )
    direct = next(row for row in receipt["observations"] if row["expression"] == "Handler()()")
    assert direct["status"] == "resolved"
    partial = next(row for row in receipt["unresolved"] if row["expression"] == "Partial().load()")
    assert partial["reason"] == "source_member_call_target_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.caller.inert@")
        for target in partial["known_source_targets"]
    )
    assert {(row["source"], row["target"]) for row in graph["edges"]} >= {
        ("polisyos.scientist.a", "polisyos.scientist.edge"),
        ("polisyos.scientist.caller", "polisyos.scientist.a"),
    }
    findings = validate_import_cycles()
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in findings
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "Partial().load()" in finding.detail
        for finding in findings
    )
    full_graph = preflight.collect_import_graph()
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in full_graph["cycles"]
    ]

    # Remove only the actual source calls. Keep the class-suite candidates, both
    # import markers, and the exact deferred-SCC registration intact.
    source_path = tmp_path / "src/polisyos/scientist/caller.py"
    after_source = (
        caller_source.replace("RoutedEntry().load()\n", "", 1)
        .replace("Handler()()\n", "", 1)
        .replace("Partial().load()\n", "", 1)
    )
    source_path.write_text(after_source, encoding="utf-8")
    edge_marker = (tmp_path / "src/polisyos/scientist/a.py").read_text(encoding="utf-8")
    assert "from polisyos.scientist import edge" in edge_marker
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["dispatch_resolution"]["unresolved_count"] == 0
    assert after["dispatch_resolution"]["status"] == "resolved_within_scope"
    assert after["dispatch_resolution"]["unresolved"] == []
    assert not any(
        row["source"] == "polisyos.scientist.a" and row["target"] == "polisyos.scientist.edge"
        for row in after["edges"]
    )
    # Removing the three actual dispatches leaves the callback and __call__
    # import markers plus the same SCC registry, but no eager source edge.
    assert "from polisyos.scientist import edge" in edge_marker
    assert "def __call__(self):" in edge_marker
    assert validate_import_cycles() == []
    assert ["polisyos.scientist.a", "polisyos.scientist.edge"] in [
        cycle["modules"] for cycle in preflight.collect_import_graph()["cycles"]
    ]


def test_import_cycle_gate_binds_callback_arguments_across_signature_forms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def invoke_posonly(callback, /):\n"
        "    callback()\n"
        "def invoke_keyword_only(*, callback):\n"
        "    callback()\n"
        "def invoke_varargs(*callbacks):\n"
        "    callbacks[0]()\n"
        "def invoke_kwargs(**callbacks):\n"
        '    callbacks["callback"]()\n'
        "invoke_posonly(callback_target)\n"
        "invoke_keyword_only(callback=callback_target)\n"
        "invoke_varargs(*(callback_target,))\n"
        'invoke_kwargs(**{"callback": callback_target})\n'
    )
    edge_source = "from polisyos.scientist.a import callback_target\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callback_rows = [
        row
        for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert receipt["unresolved_count"] == 2
    assert len(callback_rows) == 2
    assert all(row["status"] == "not_established" for row in callback_rows)
    assert {row["expression"].split("(", maxsplit=1)[0] for row in callback_rows} == {
        "invoke_varargs",
        "invoke_kwargs",
    }
    assert all(
        any(
            target.startswith("polisyos.scientist.a.callback_target@")
            for target in row["known_source_targets"]
        )
        for row in callback_rows
    )
    assert any(
        row["source"] == "polisyos.scientist.a" and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )

    # Remove only the actual callback calls, preserving the callback's import
    # marker, its source consumer, and the exact deferred-cycle registration.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    after_source = a_source
    for call in (
        "invoke_posonly(callback_target)\n",
        "invoke_keyword_only(callback=callback_target)\n",
        "invoke_varargs(*(callback_target,))\n",
        'invoke_kwargs(**{"callback": callback_target})\n',
    ):
        after_source = after_source.replace(call, "", 1)
    source_path.write_text(after_source, encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_uses_definition_time_callback_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "def inert():\n"
        "    return None\n"
        "positional_capture = callback_target\n"
        "def invoke_positional(request, callback=positional_capture, /):\n"
        "    callback()\n"
        "positional_capture = inert\n"
        "keyword_capture = callback_target\n"
        "def invoke_keyword_only(*, mode, callback=keyword_capture):\n"
        "    callback()\n"
        "keyword_capture = inert\n"
    )
    caller_source = (
        "from polisyos.scientist.a import inert, invoke_positional, invoke_keyword_only\n"
        "invoke_positional(None)\n"
        "invoke_positional(None, inert)\n"
        "invoke_keyword_only(mode='run')\n"
    )
    edge_source = "from polisyos.scientist.a import callback_target\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callbacks = [
        row
        for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert callbacks == []
    assert receipt["unresolved_count"] == 0
    assert any(
        row["source"] == "polisyos.scientist.a" and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Definition-time defaults keep the original callback after the names used
    # to construct them are rebound. Remove only the calls; retain both default
    # expressions, callback import markers, and the registered deferred SCC.
    after_source = (
        caller_source.replace("invoke_positional(None)\n", "", 1)
        .replace("invoke_positional(None, inert)\n", "", 1)
        .replace("invoke_keyword_only(mode='run')\n", "", 1)
    )
    caller_path = tmp_path / "src/polisyos/scientist/caller.py"
    caller_path.write_text(after_source, encoding="utf-8")
    assert "from polisyos.scientist import edge" in (
        tmp_path / "src/polisyos/scientist/a.py"
    ).read_text(encoding="utf-8")
    assert "from polisyos.scientist.a import inert" in caller_path.read_text(encoding="utf-8")
    assert edge_source == (tmp_path / "src/polisyos/scientist/edge.py").read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert after["unresolved"] == []
    assert validate_import_cycles() == []


def test_import_cycle_gate_tracks_member_values_by_shared_owner_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from builtins import setattr as write_member\n"
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "holder_alias = Holder\n"
        "stable_owner = holder_alias\n"
        "holder_alias = object()\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    stable_owner.item = Entry()\n"
        "else:\n"
        '    write_member(Holder, "item", Entry())\n'
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(lazy_registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["observations"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "resolved"
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert ("polisyos.scientist.a", "polisyos.scientist.edge") in {
        (row["source"], row["target"]) for row in graph["edges"]
    }
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    # Remove only the dispatch; retain the alias chain, both branch writes, the
    # method's source import marker, and the exact deferred-SCC registration.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []


def test_import_cycle_gate_joins_possible_owner_member_mutator_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from builtins import setattr as write_member\n"
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "def noop(owner, name, value):\n"
        "    return None\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    write_member = noop\n"
        'write_member(Holder, "item", Entry())\n'
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    receipt = graph["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["observations"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "Holder.item.boot()" in finding.detail
        for finding in validate_import_cycles()
    )
    assert "from polisyos.scientist import edge" in a_source
    assert lazy_registry.read_text(encoding="utf-8") == registry_text

    # The setter may be the imported builtin or the source no-op. Remove only
    # the actual member dispatch; the old/new candidates, import markers, and
    # exact deferred-SCC registration remain present.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    after = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert after["unresolved_count"] == 0
    assert validate_import_cycles() == []
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_preserves_owner_member_across_optional_loop_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "candidates = [Entry()]\n"
        "for Holder.item in candidates:\n"
        "    pass\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    dispatch = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert dispatch["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert validate_import_cycles()

    # The possible loop write is not itself a dispatch. Removing the member call
    # must clear the finding while all source import markers remain in place.
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Holder.item.boot()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert lazy_registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_marks_source_member_store_without_owner_identity_unestablished(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "def make_holder():\n"
        "    return Holder()\n"
        "owner = make_holder()\n"
        "owner.item = Entry()\n"
        "owner.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "owner.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert unresolved["reason"] in {
        "source_callable_return_not_summarized",
        "source_derived_receiver_not_summarized",
    }
    findings = validate_import_cycles()
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        and "owner.item.boot()" in finding.detail
        for finding in findings
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_exports_owner_member_knowledge_as_uncertain_cross_module_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder_source = "class Holder:\n    pass\n"
    writer_source = (
        "from polisyos.scientist.holder import Holder\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "alias = Holder\n"
        "alias.item = Entry()\n"
    )
    caller_source = "from polisyos.scientist.holder import Holder\nHolder.item.boot()\n"
    edge_source = "from polisyos.scientist.holder import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/holder.py": holder_source,
            "polisyos/scientist/writer.py": writer_source,
            "polisyos/scientist/caller.py": caller_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.caller", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert any(
        target.startswith("polisyos.scientist.writer.Entry.boot@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_keeps_joined_possible_owners_unestablished_after_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class HolderA:\n"
        "    pass\n"
        "class HolderB:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "runtime_flag = False\n"
        "if runtime_flag:\n"
        "    owner = HolderA\n"
        "else:\n"
        "    owner = HolderB\n"
        "owner.item = Entry()\n"
        "HolderA.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import HolderA\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "HolderA.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_marks_deleted_owner_member_not_established(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Holder:\n"
        "    pass\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "owner = Holder\n"
        "owner.item = Entry()\n"
        'delattr(owner, "item")\n'
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert unresolved["status"] == "not_established"
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_rejects_dynamic_builtin_member_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Prior:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "class Holder:\n"
        "    item = Prior()\n"
        "class Entry:\n"
        "    def boot(self):\n"
        "        from polisyos.scientist import edge\n"
        "owner = Holder\n"
        'member_name = "item"\n'
        "setattr(owner, member_name, Entry())\n"
        "Holder.item.boot()\n"
    )
    edge_source = "from polisyos.scientist.a import Holder\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": edge_source,
        },
        monkeypatch,
    )
    lazy_registry = tmp_path / "architecture/imports/lazy.toml"
    lazy_registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    lazy_registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", lazy_registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    assert any(
        row["status"] == "not_established" and row["expression"].startswith("setattr(")
        for row in receipt["unresolved"]
    )
    dispatch = next(
        row for row in receipt["unresolved"] if row["expression"] == "Holder.item.boot()"
    )
    assert any(
        target.startswith("polisyos.scientist.a.Prior.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert any(
        target.startswith("polisyos.scientist.a.Entry.boot@")
        for target in dispatch["known_source_targets"]
    )
    assert validate_import_cycles()
    assert lazy_registry.read_text(encoding="utf-8") == registry_text


def test_import_cycle_gate_models_builtin_dir_values_and_module_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "from polisyos.scientist import artifacts as _artifacts\n"
        "globals().update({name: getattr(_artifacts, name) for name in dir(_artifacts) "
        "if not name.startswith('__')})\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/artifacts.py": (
                "def __dir__():\n"
                "    from polisyos.scientist import a\n"
                "    return ['Exported']\n"
                "class Exported:\n"
                "    pass\n"
            ),
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    graph = preflight.collect_import_graph(runtime_only=True)
    edge_pairs = {(row["source"], row["target"]) for row in graph["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.artifacts") in edge_pairs
    assert ("polisyos.scientist.artifacts", "polisyos.scientist.a") in edge_pairs
    assert not any(
        row["expression"] == "name.startswith('__')"
        and row["reason"] == "source_derived_receiver_not_summarized"
        for row in graph["dispatch_resolution"]["unresolved"]
    )
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    (tmp_path / "src/polisyos/scientist/a.py").write_text(
        "from polisyos.scientist import artifacts as _artifacts\n", encoding="utf-8"
    )
    assert "from polisyos.scientist import a" in (
        tmp_path / "src/polisyos/scientist/artifacts.py"
    ).read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_follows_source_owned_startswith_method_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "class Entry:\n"
        "    def startswith(self):\n"
        "        from polisyos.scientist import edge\n"
        "Entry().startswith()\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("Entry().startswith()\n", "", 1), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_binds_method_receiver_before_callback_formals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a_source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    def accept(self, payload):\n"
        "        return None\n"
        "    def invoke(self, callback):\n"
        "        callback()\n"
        "Entry().accept(callback_target)\n"
        "Entry().invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    callback_rows = [
        row
        for row in receipt["unresolved"]
        if row["reason"] == "source_callback_argument_not_summarized"
    ]
    assert callback_rows == []
    assert receipt["unresolved_count"] == 0
    assert any(
        row["source"] == "polisyos.scientist.a" and row["target"] == "polisyos.scientist.edge"
        for row in preflight.collect_import_graph(runtime_only=True)["edges"]
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("Entry().invoke(callback_target)\n", "", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    after_graph = preflight.collect_import_graph(runtime_only=True)
    after = after_graph["dispatch_resolution"]
    assert not any(
        row["reason"] == "source_callback_argument_not_summarized" for row in after["unresolved"]
    )
    assert not any(
        row["source"] == "polisyos.scientist.a" and row["target"] == "polisyos.scientist.edge"
        for row in after_graph["edges"]
    )
    assert not any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_follows_source_metaclass_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": (
                "class Meta(type):\n"
                "    def __dir__(cls):\n"
                "        from polisyos.scientist import edge\n"
                "        return []\n"
                "class Entry(metaclass=Meta):\n"
                "    pass\n"
                "dir(Entry)\n"
            ),
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )


def test_import_cycle_gate_resolves_inherited_metaclass_dir_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "class RootMeta(type):\n"
        "    def __dir__(cls):\n"
        "        from polisyos.scientist import edge\n"
        "        return []\n"
        "class Meta(RootMeta):\n"
        "    pass\n"
        "class Base(metaclass=Meta):\n"
        "    pass\n"
        "class Child(Base):\n"
        "    pass\n"
        "dir(Child)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Child\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(source.replace("dir(Child)\n", ""), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_resolves_builtin_descriptor_alias_not_custom_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "from builtins import staticmethod as exact_static\n"
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Entry:\n"
        "    @exact_static\n"
        "    def invoke(callback):\n"
        "        callback()\n"
        "Entry.invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )
    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(source.replace("Entry.invoke(callback_target)\n", ""), encoding="utf-8")
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_keeps_custom_descriptor_suffix_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "def callback_target():\n"
        "    from polisyos.scientist import edge\n"
        "class Decorators:\n"
        "    @staticmethod\n"
        "    def staticmethod(function):\n"
        "        return function\n"
        "class Entry:\n"
        "    @Decorators.staticmethod\n"
        "    def invoke(self, callback):\n"
        "        callback()\n"
        "Entry().invoke(callback_target)\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Entry\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row
        for row in receipt["unresolved"]
        if row["expression"] == "Entry().invoke(callback_target)"
    )
    assert unresolved["reason"] == "source_callback_argument_not_summarized"
    assert any(
        target.startswith("polisyos.scientist.a.callback_target@")
        for target in unresolved["known_source_targets"]
    )
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        source.replace("Entry().invoke(callback_target)\n", ""), encoding="utf-8"
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_preserves_source_dir_string_subclass_dispatch_and_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (
        "class Name(str):\n"
        "    def startswith(self, prefix):\n"
        "        from polisyos.scientist import edge\n"
        "        return True\n"
        "class Entry:\n"
        "    def __dir__(self):\n"
        "        return [Name('entry')]\n"
        "for name in dir(Entry()):\n"
        "    name.startswith('e')\n"
    )
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": source,
            "polisyos/scientist/edge.py": "from polisyos.scientist.a import Name\n",
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry_text = (
        "[lazy_imports]\nversion = 1\n[[allowed_cycle]]\n"
        'modules = ["polisyos.scientist.a", "polisyos.scientist.edge"]\n'
    )
    registry.write_text(registry_text, encoding="utf-8")
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    receipt = preflight.collect_import_graph(runtime_only=True)["dispatch_resolution"]
    unresolved = next(
        row for row in receipt["unresolved"] if row["expression"] == "name.startswith('e')"
    )
    assert unresolved["reason"] == "source_callable_return_not_summarized"
    assert any(
        finding.message == "module-time source-known dispatch is not established"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        source.replace("    name.startswith('e')\n", "    pass\n", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_captures_bound_receiver_before_argument_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "class Entry:\n"
        "    def invoke(self, marker):\n"
        "        self.load()\n"
        "    def load(self):\n"
        "        from polisyos.scientist import left_edge\n"
        "class Replacement:\n"
        "    def load(self):\n"
        "        from polisyos.scientist import right_edge\n"
        "def rebind_selected():\n"
        "    global selected\n"
        "    selected = Replacement()\n"
        "    return None\n"
        "selected = Entry()\n"
        "selected.invoke(rebind_selected())\n"
    )
    left_edge_source = "from polisyos.scientist.a import Entry\n"
    right_edge_source = "from polisyos.scientist.a import Replacement\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_before
    eager_cycle = next(
        cycle["modules"]
        for cycle in before["cycles"]
        if "polisyos.scientist.left_edge" in cycle["modules"]
    )
    eager_component = frozenset(eager_cycle)
    assert eager_component == frozenset({"polisyos.scientist.a", "polisyos.scientist.left_edge"})
    registered_components = {
        frozenset(row["modules"]) for row in tomllib.loads(registry_text)["allowed_cycle"]
    }
    assert any(eager_component < registered for registered in registered_components)
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and "module-eager" in finding.message
        and finding.detail == ", ".join(eager_cycle)
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("selected.invoke(rebind_selected())\n", "", 1),
        encoding="utf-8",
    )
    assert "from polisyos.scientist import left_edge" in source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import right_edge" in source_path.read_text(encoding="utf-8")
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["cycles"] == []
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_captures_callback_before_later_argument_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "def original_callback():\n"
        "    from polisyos.scientist import left_edge\n"
        "def replacement_callback():\n"
        "    from polisyos.scientist import right_edge\n"
        "callback_target = original_callback\n"
        "def rebind_callback():\n"
        "    global callback_target\n"
        "    callback_target = replacement_callback\n"
        "    return None\n"
        "def invoke(callback, marker):\n"
        "    callback()\n"
        "invoke(callback_target, rebind_callback())\n"
        "callback_target = original_callback\n"
        "invoke(callback=callback_target, marker=rebind_callback())\n"
    )
    left_edge_source = "from polisyos.scientist.a import original_callback\n"
    right_edge_source = "from polisyos.scientist.a import replacement_callback\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/left_edge.py": left_edge_source,
            "polisyos/scientist/right_edge.py": right_edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") in edges_before
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_before
    eager_cycle = next(
        cycle["modules"]
        for cycle in before["cycles"]
        if "polisyos.scientist.left_edge" in cycle["modules"]
    )
    eager_component = frozenset(eager_cycle)
    assert eager_component == frozenset({"polisyos.scientist.a", "polisyos.scientist.left_edge"})
    registered_components = {
        frozenset(row["modules"]) for row in tomllib.loads(registry_text)["allowed_cycle"]
    }
    assert any(eager_component < registered for registered in registered_components)
    findings = validate_import_cycles()
    assert any(
        finding.gate == "import_cycles_gate"
        and "module-eager" in finding.message
        and finding.detail == ", ".join(eager_cycle)
        for finding in findings
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(
        a_source.replace("invoke(callback_target, rebind_callback())\n", "", 1).replace(
            "invoke(callback=callback_target, marker=rebind_callback())\n", "", 1
        ),
        encoding="utf-8",
    )
    after_source = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import left_edge" in after_source
    assert "from polisyos.scientist import right_edge" in after_source
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    assert after["cycles"] == []
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.left_edge") not in edges_after
    assert ("polisyos.scientist.a", "polisyos.scientist.right_edge") not in edges_after
    assert ("polisyos.scientist.left_edge", "polisyos.scientist.a") in edges_after
    assert ("polisyos.scientist.right_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def test_import_cycle_gate_joins_effects_from_same_call_alternatives(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a_source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "def a_false():\n"
        "    global TYPE_ONLY\n"
        "    TYPE_ONLY = False\n"
        "def z_true():\n"
        "    global TYPE_ONLY\n"
        "    from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "if choose_target:\n"
        "    selected = a_false\n"
        "else:\n"
        "    selected = z_true\n"
        "selected()\n"
        "if TYPE_ONLY:\n"
        "    from polisyos.scientist import deferred_edge\n"
    )
    edge_source = "from polisyos.scientist.a import a_false\n"
    _write_runtime_import_fixture(
        tmp_path,
        {
            "polisyos/scientist/a.py": a_source,
            "polisyos/scientist/deferred_edge.py": edge_source,
        },
        monkeypatch,
    )
    registry = tmp_path / "architecture/imports/lazy.toml"
    registry_text = _write_current_full_scc_registry(registry)
    monkeypatch.setattr(preflight, "LAZY_IMPORTS_PATH", registry)

    before = preflight.collect_import_graph(runtime_only=True)
    edges_before = {(row["source"], row["target"]) for row in before["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") in edges_before
    assert any(
        finding.message == "registered deferred-cycle signature contains a module-eager cycle"
        for finding in validate_import_cycles()
    )

    source_path = tmp_path / "src/polisyos/scientist/a.py"
    source_path.write_text(a_source.replace("selected()\n", "", 1), encoding="utf-8")
    after_source = source_path.read_text(encoding="utf-8")
    assert "from polisyos.scientist import deferred_edge" in after_source
    assert registry.read_text(encoding="utf-8") == registry_text
    after = preflight.collect_import_graph(runtime_only=True)
    edges_after = {(row["source"], row["target"]) for row in after["edges"]}
    assert ("polisyos.scientist.a", "polisyos.scientist.deferred_edge") not in edges_after
    assert ("polisyos.scientist.deferred_edge", "polisyos.scientist.a") in edges_after
    assert registry.read_text(encoding="utf-8") == registry_text
    assert validate_import_cycles() == []


def _dynamic_import_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> Path:
    """Build a minimal source root for exercising the production collector."""
    for scope in ("src", "tools", "apps", "packages"):
        (tmp_path / scope).mkdir()
    source_path = tmp_path / "src" / "dynamic_fixture.py"
    source_path.write_text(source, encoding="utf-8")
    registry_path = tmp_path / "architecture" / "imports" / "dynamic.toml"
    registry_path.parent.mkdir(parents=True)
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(preflight, "DYNAMIC_IMPORTS_PATH", registry_path)
    return registry_path


def test_dynamic_imports_gate_derives_targets_from_immutable_finite_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
from importlib import import_module
from types import MappingProxyType

_EXPORTS = MappingProxyType({
    "one": ("polisyos.demo.alpha", "Alpha"),
    "two": ("polisyos.demo.beta", "Beta"),
})

def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    source_path = tmp_path / "src" / "dynamic_fixture.py"

    entries = preflight.collect_dynamic_imports()

    assert len(entries) == 1
    entry = entries[0]
    assert entry["allowed_targets"] == [
        "polisyos.demo.alpha",
        "polisyos.demo.beta",
    ]
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path.write_text(
        source.replace('"polisyos.demo.beta"', '"polisyos.demo.gamma"'),
        encoding="utf-8",
    )
    assert preflight.validate_dynamic_imports()

    # Keep all registry and facade markers while deleting the runtime importer.
    source_path.write_text(
        source.replace("    module = import_module(module_name)\n", ""),
        encoding="utf-8",
    )
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists" for finding in findings
    )


def test_dynamic_imports_gate_leaves_mutable_unknown_maps_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.mkdir(exist_ok=True)
    source = """\
from importlib import import_module

_EXPORTS = {
    "one": ("polisyos.demo.alpha", "Alpha"),
    "two": ("polisyos.demo.beta", "Beta"),
}

def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    return import_module(module_name)
"""
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    assert len(entries) == 1
    assert entries[0]["allowed_targets"] == []


def test_dynamic_imports_gate_derives_all_core_security_finite_targets() -> None:
    source_path = REPO_ROOT / "src" / "polisyos" / "core" / "security" / "__init__.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    export_assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "_EXPORTS"
    )
    exports = ast.literal_eval(export_assignment.value.args[0])
    expected = sorted({module for module, _attribute in exports.values()})

    source_paths = preflight._dynamic_source_paths("src", "tools", "apps", "packages")
    source_bindings = preflight._DynamicImportSourceBindings(source_paths)
    scanner = preflight._DynamicImportSourceScanner(
        source_path,
        relative_path="src/polisyos/core/security/__init__.py",
        source_bindings=source_bindings,
    )
    entries = scanner.scan(tree)
    rows = [
        entry
        for entry in entries
        if entry["source_file"] == "src/polisyos/core/security/__init__.py"
        and entry["call"] == "importlib.import_module"
    ]

    assert len(rows) == 1
    assert rows[0]["allowed_targets"] == expected


def _dynamic_import_validator_refusal(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> list[preflight.Finding]:
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    return preflight.validate_dynamic_imports()


def test_dynamic_import_type_parameter_fields_reach_inventory_and_registry_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """
import importlib

def function_bound[T: importlib.import_module("math")]():
    pass

class class_bound[T: importlib.import_module("json")]:
    pass

type alias_bound[T: importlib.import_module("pathlib")] = int

def function_default[T = importlib.import_module("collections")]():
    pass

def function_constraint[T: (int, importlib.import_module("re"))]():
    pass

def parameter_spec[**P = importlib.import_module("itertools")]():
    pass

def variable_tuple[*Ts = importlib.import_module("functools")]():
    pass

"""
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        source,
    )

    entries = preflight.collect_dynamic_imports()
    expected_patterns = {
        "math",
        "json",
        "pathlib",
        "collections",
        "re",
        "itertools",
        "functools",
    }
    assert {str(entry["pattern"]) for entry in entries} == expected_patterns

    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    for entry in entries:
        remaining = [candidate for candidate in entries if candidate["id"] != entry["id"]]
        registry_path.write_text(_render_dynamic_imports_toml(remaining), encoding="utf-8")
        findings = preflight.validate_dynamic_imports()
        assert any(
            finding.message == "dynamic import call is not registered"
            and str(entry["pattern"]) in finding.detail
            for finding in findings
        )

    namespace = runpy.run_path(str(tmp_path / "src" / "dynamic_fixture.py"))
    assert namespace["function_bound"].__type_params__[0].__bound__.__name__ == "math"
    assert namespace["class_bound"].__type_params__[0].__bound__.__name__ == "json"
    assert namespace["alias_bound"].__type_params__[0].__bound__.__name__ == "pathlib"
    assert namespace["function_default"].__type_params__[0].__default__.__name__ == "collections"
    constraints = namespace["function_constraint"].__type_params__[0].__constraints__
    assert constraints[1].__name__ == "re"
    assert namespace["parameter_spec"].__type_params__[0].__default__.__name__ == "itertools"
    assert namespace["variable_tuple"].__type_params__[0].__default__.__name__ == "functools"


def test_dynamic_import_type_parameter_fields_resolve_late_module_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "def late_bound[T: importlib.import_module('itertools')]():\n    pass\nimport importlib\n"
    )
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        source,
    )

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["itertools"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []
    namespace = runpy.run_path(str(tmp_path / "src" / "dynamic_fixture.py"))
    assert namespace["late_bound"].__type_params__[0].__bound__.__name__ == "itertools"


def test_dynamic_import_type_parameter_annotation_scope_shadows_outer_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        "import importlib\ndef shadowed[importlib: importlib.import_module('math')]():\n    pass\n",
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_method_type_parameter_uses_enclosing_class_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "import importlib\n"
        "class Example:\n"
        "    import json as importlib\n"
        "    def method[T: importlib.import_module('math')]():\n"
        "        pass\n"
    )
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        source,
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []
    namespace = runpy.run_path(str(tmp_path / "src" / "dynamic_fixture.py"))
    with pytest.raises(AttributeError, match="import_module"):
        _ = namespace["Example"].method.__type_params__[0].__bound__


def test_dynamic_import_type_parameter_refuses_guarded_bare_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(
        "import importlib\ndef guarded[T: importlib.import_module]():\n    pass\n",
        tmp_path,
        monkeypatch,
    )

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "type parameter bound" in finding.detail
        for finding in findings
    )


def test_dynamic_import_type_parameter_scanner_refuses_unknown_ast_carrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnknownTypeParameter(ast.AST):
        _fields = ("value",)

    parameter = UnknownTypeParameter()
    parameter.value = ast.Call(
        func=ast.Name(id="__import__", ctx=ast.Load()),
        args=[ast.Constant(value="unknown_type_parameter")],
        keywords=[],
    )
    function = ast.FunctionDef(
        name="unknown_parameter",
        args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=[ast.Pass()],
        decorator_list=[],
        type_params=[parameter],
    )
    tree = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    with monkeypatch.context() as parser_patch:
        parser_patch.setattr(preflight.ast, "parse", lambda *_args, **_kwargs: tree)
        findings = preflight.validate_dynamic_imports()

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "unsupported type parameter" in finding.detail
        for finding in findings
    )


def test_dynamic_import_collector_resolves_aliases_through_real_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import builtins
import importlib
from importlib import import_module as imported_loader

loader = importlib.import_module
chained_loader = loader
loader("direct_alias")
chained_loader("chained_alias")
imported_loader("imported_alias")
reflected_loader = getattr(importlib, "import_module")
reflected_loader("reflected_alias")
builtin_loader = getattr(builtins, "__import__")
builtin_loader("builtin_alias")

if condition:
    branch_loader = importlib.import_module
else:
    branch_loader = importlib.import_module
branch_loader("unanimous_branch")

def closes_over_alias():
    captured_loader = importlib.import_module

    def inner():
        captured_loader("closure_alias")

    inner()
""",
    )

    entries = preflight.collect_dynamic_imports()
    expected_patterns = {
        "direct_alias",
        "chained_alias",
        "imported_alias",
        "reflected_alias",
        "builtin_alias",
        "unanimous_branch",
        "closure_alias",
    }
    assert {str(entry["pattern"]) for entry in entries} >= expected_patterns
    assert all(
        entry["call"] == "importlib.import_module"
        for entry in entries
        if entry["pattern"] in expected_patterns - {"builtin_alias"}
    )
    builtin_entry = next(entry for entry in entries if entry["pattern"] == "builtin_alias")
    assert builtin_entry["call"] == "__import__"

    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(
        _render_dynamic_imports_toml(
            [entry for entry in entries if entry["pattern"] != "direct_alias"]
        ),
        encoding="utf-8",
    )
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "direct_alias" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    ("source", "expected_call"),
    [
        ('import builtins\nbuiltins.__import__("private.module")', "__import__"),
        ('__builtins__.__import__("private.module")', "__import__"),
        ('__builtins__["__import__"]("private.module")', "__import__"),
        (
            'import builtins\nvars(builtins)["__import__"]("private.module")',
            "__import__",
        ),
        (
            'import importlib\ng = getattr\ng(importlib, "import_module")("private.module")',
            "importlib.import_module",
        ),
        (
            'import importlib\ngetattr(importlib, "import_module")("private.module")',
            "importlib.import_module",
        ),
        (
            'import importlib\nglobals()["importlib"].import_module("private.module")',
            "importlib.import_module",
        ),
        (
            'import importlib\nglobals().get("importlib").import_module("private.module")',
            "importlib.import_module",
        ),
        (
            'import sys\nsys.modules["importlib"].import_module("private.module")',
            "importlib.import_module",
        ),
        (
            'import importlib\nnames = set(globals())\nimportlib.import_module("private.module")',
            "importlib.import_module",
        ),
        (
            "import importlib\nfrom builtins import getattr as reflect\n"
            'reflect(importlib, "import_module")("private.module")',
            "importlib.import_module",
        ),
    ],
)
def test_dynamic_import_collector_resolves_reflection_roots(
    source: str,
    expected_call: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    entries = scanner.scan(ast.parse(source))

    assert [entry["pattern"] for entry in entries] == ["private.module"]
    assert [entry["call"] for entry in entries] == [expected_call]


@pytest.mark.parametrize(
    "source",
    [
        'import sys\nsys.modules["importlib.metadata"].entry_points()',
        'import sys\nsys.modules["importlib"].metadata.entry_points()',
    ],
)
def test_dynamic_import_collector_resolves_registry_submodule_names(source: str) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    entries = scanner.scan(ast.parse(source))

    assert len(entries) == 1
    assert entries[0]["call"] == "metadata.entry_points"


def test_dynamic_import_scanner_returns_exact_sink_ast_nodes() -> None:
    tree = ast.parse(
        "import builtins\n"
        "import importlib\n"
        "from builtins import getattr as reflect\n"
        "loader = reflect(importlib, 'import_module')\n"
        "loader('private.module')\n"
        "builtins.__import__('private.module')\n"
    )
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    entries, sites = scanner.scan_with_sites(tree)

    call_by_line = {
        node.lineno: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and node.lineno in {5, 6}
    }
    assert [site.call_name for site in sites] == [
        "importlib.import_module",
        "__import__",
    ]
    assert [site.node.lineno for site in sites] == [5, 6]
    assert all(site.node is call_by_line[site.node.lineno] for site in sites)
    assert [entry["call"] for entry in entries] == [site.call_name for site in sites]


def test_dynamic_import_scanner_does_not_treat_plain_root_words_as_capabilities() -> None:
    tree = ast.parse(
        "from pathlib import Path\n"
        "def make(root: Path) -> None:\n"
        "    for child in ('provenance', 'metadata'):\n"
        "        (root / child).mkdir(parents=True, exist_ok=True)\n"
    )
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    assert scanner.scan(tree) == []


@pytest.mark.parametrize(
    "source",
    [
        "eval(\"__import__(\\'private.module\\')\")",
        "exec(\"__import__(\\'private.module\\')\")",
        "import importlib\nconsume(importlib.import_module)",
        "import builtins\nname = supplied_name\ngetattr(builtins, name)",
    ],
)
def test_dynamic_import_collector_refuses_dynamic_code_or_unknown_capability_flow(
    source: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    with pytest.raises(RuntimeError, match=r"dynamic|guarded|importer|escapes|unresolved"):
        scanner.scan(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    [
        """
def shadowed_module(importlib):
    importlib.import_module("shadowed")
""",
        """
def shadowed_builtin(__import__):
    __import__("shadowed")
""",
        """
def assigned_shadow():
    importlib = supplied_value
    importlib.import_module("shadowed")
""",
    ],
)
def test_dynamic_import_collector_ignores_shadowed_candidate_roots(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_collector_refuses_conflicting_alias_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib
import pkgutil

if condition:
    loader = importlib.import_module
else:
    loader = pkgutil.iter_modules
loader("ambiguous_alias")
""",
    )

    with pytest.raises(RuntimeError, match=r"ambiguous|conflicting|unresolved"):
        preflight.collect_dynamic_imports()


def test_dynamic_import_collector_tracks_comprehension_scope_and_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib

loader = importlib.import_module
[loader("comprehension_alias") for item in paths]
loader = ordinary_function
loader("overwritten_alias")
deleted_loader = importlib.import_module
del deleted_loader
deleted_loader("deleted_alias")
""",
    )

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["comprehension_alias"]


def test_dynamic_import_collector_ignores_shadow_inside_comprehension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib

[importlib.import_module("shadowed_comprehension") for importlib in modules]
""",
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_collector_joins_nested_closure_mutations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib

def outer():
    loader = importlib.import_module

    def inner():
        loader("possibly_dynamic_closure")

    inner()
    loader = ordinary_function
""",
    )

    with pytest.raises(RuntimeError, match=r"ambiguous|conflicting|unresolved"):
        preflight.collect_dynamic_imports()


def test_dynamic_import_collector_refuses_cross_scope_alias_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib
loader = importlib.import_module

def replace_global_loader():
    global loader
    loader = ordinary_function
""",
    )

    with pytest.raises(RuntimeError, match=r"cross-scope|guarded importer"):
        preflight.collect_dynamic_imports()


def test_dynamic_import_collector_refuses_transformed_guarded_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib

loader = transform(importlib.import_module)
loader("transformed_alias")
""",
    )

    with pytest.raises(RuntimeError, match=r"alias|binding|unresolved|escapes"):
        preflight.collect_dynamic_imports()


def test_dynamic_import_collector_refuses_incomplete_source_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for scope in ("src", "tools", "apps"):
        (tmp_path / scope).mkdir()
    monkeypatch.setattr(preflight, "REPO_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match=r"packages|root|incomplete"):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize("scope", ["src", "tools", "apps", "packages"])
@pytest.mark.parametrize("target_kind", ["outside", "internal", "ancestor_cycle"])
def test_dynamic_import_validator_fails_closed_on_nonignored_directory_symlinks(
    scope: str,
    target_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    registry_path = _dynamic_import_fixture(repository, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    source_root = repository / scope

    if target_kind == "outside":
        target_root = tmp_path / "external-source"
    elif target_kind == "internal":
        target_root = repository / "unselected-source"
    else:
        target_root = repository
    target_root.mkdir(parents=True, exist_ok=True)
    (target_root / "hidden_dynamic_source.py").write_text(
        'import importlib\nimportlib.import_module("hidden_dynamic_import")\n',
        encoding="utf-8",
    )
    link = source_root / f"linked_{scope}_{target_kind}"
    link.symlink_to(target_root, target_is_directory=True)

    findings = preflight.validate_dynamic_imports()

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and scope in finding.detail
        and "directory symlink" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize("scope", ["src", "tools", "apps", "packages"])
def test_dynamic_import_validator_keeps_named_ignored_symlink_subtrees_excluded(
    scope: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    registry_path = _dynamic_import_fixture(repository, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    ignored_target = tmp_path / "ignored-source"
    ignored_target.mkdir()
    (ignored_target / "hidden_dynamic_source.py").write_text(
        'import importlib\nimportlib.import_module("ignored_hidden_import")\n',
        encoding="utf-8",
    )
    (repository / scope / "node_modules").symlink_to(
        ignored_target,
        target_is_directory=True,
    )

    assert preflight.validate_dynamic_imports() == []


@pytest.mark.parametrize("scope", ["src", "tools", "apps", "packages"])
def test_dynamic_import_validator_fails_closed_when_selected_root_is_symlink(
    scope: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    registry_path = _dynamic_import_fixture(repository, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    source_root = repository / scope
    shutil.rmtree(source_root)
    external_root = tmp_path / "external-source-root"
    external_root.mkdir()
    (external_root / "hidden_dynamic_source.py").write_text(
        'import importlib\nimportlib.import_module("hidden_root_import")\n',
        encoding="utf-8",
    )
    source_root.symlink_to(external_root, target_is_directory=True)

    findings = preflight.validate_dynamic_imports()

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "source root" in finding.detail
        and "directory symlink" in finding.detail
        for finding in findings
    )


def test_dynamic_import_validator_reports_typed_source_traversal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    def failed_walk(*_args, onerror, **_kwargs):
        onerror(PermissionError("fixture subtree is unreadable"))
        return iter(())

    monkeypatch.setattr(preflight.os, "walk", failed_walk)

    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "fixture subtree is unreadable" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    "source",
    [
        """
import importlib
loader = ordinary_function
(loader := importlib.import_module) if condition else (loader := ordinary_function)
loader("call_after_ifexp")
""",
        """
import importlib
loader = importlib.import_module
condition and (loader := ordinary_function)
loader("call_after_and")
""",
        """
import importlib
loader = importlib.import_module
condition or (loader := ordinary_function)
loader("call_after_or")
""",
        """
import importlib
loader = importlib.import_module
left < (loader := ordinary_function) < (loader := importlib.import_module)
loader("call_after_chained_compare")
""",
        """
import importlib
loader = importlib.import_module
condition and ((loader := ordinary_function) if branch else (loader := importlib.import_module))
loader("call_after_nested_expression")
""",
    ],
)
def test_dynamic_import_validator_refuses_guarded_values_across_expression_paths(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(source, tmp_path, monkeypatch)

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
        for finding in findings
    )


def test_dynamic_import_expression_path_join_preserves_same_origin_alias_and_removal_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """
import importlib
loader = ordinary_function
(loader := importlib.import_module) if condition else (loader := importlib.import_module)
condition and (loader := importlib.import_module)
loader("same_origin_expression_branch")
""",
    )

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["same_origin_expression_branch"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "same_origin_expression_branch" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    ("registry_name", "proxy_import", "proxy_expression"),
    [
        ("ROUTES", "from types import MappingProxyType", "MappingProxyType"),
        ("RENAMED_BINDINGS", "import types as types_alias", "types_alias.MappingProxyType"),
    ],
)
def test_dynamic_import_registry_tuple_membership_refines_reflective_lookup(
    registry_name: str,
    proxy_import: str,
    proxy_expression: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = f"""
from importlib import import_module
{proxy_import}

{registry_name} = {proxy_expression}({{
    ("catalog", "alpha"): ("polisyos.catalog.alpha", "alpha"),
    ("catalog", "beta"): ("polisyos.catalog.beta", "beta"),
}})
COMPATIBILITY_ROUTES = {proxy_expression}({{
    ("legacy", "gamma"): ("polisyos.catalog.legacy", "gamma"),
}})

def resolve(owner, name):
    binding_key = (owner, name)
    if binding_key in {registry_name}:
        module_name, target_name = {registry_name}[binding_key]
    elif binding_key in COMPATIBILITY_ROUTES:
        module_name, target_name = COMPATIBILITY_ROUTES[binding_key]
    else:
        raise LookupError(binding_key)
    return globals().get(target_name)
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_registry_tracks_importer_capabilities_in_tuple_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """
from importlib import import_module
from types import MappingProxyType

ROUTES = MappingProxyType({
    ("catalog", "loader"): ("polisyos.catalog", "import_module"),
})

def resolve(owner, name):
    binding_key = (owner, name)
    if binding_key not in ROUTES:
        raise LookupError(binding_key)
    module_name, target_name = ROUTES[binding_key]
    return globals().get(target_name)("registry_hidden_importer")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["registry_hidden_importer"]
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "registry_hidden_importer" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    "source",
    [
        """
from importlib import import_module
from types import MappingProxyType
ROUTES = MappingProxyType({("catalog", "alpha"): ("polisyos.catalog", "alpha")})
ROUTES[("catalog", "loader")] = ("polisyos.catalog", "import_module")
def resolve(owner, name):
    binding_key = (owner, name)
    if binding_key in ROUTES:
        _, target_name = ROUTES[binding_key]
        return globals().get(target_name)("mutated_registry_importer")
    raise LookupError(binding_key)
""",
        """
from importlib import import_module
from types import MappingProxyType
mutable_routes = {("catalog", "loader"): ("polisyos.catalog", "import_module")}
ROUTES = MappingProxyType(mutable_routes)
def resolve(owner, name):
    binding_key = (owner, name)
    if binding_key in ROUTES:
        _, target_name = ROUTES[binding_key]
        return globals().get(target_name)("aliased_mutable_registry")
    raise LookupError(binding_key)
""",
    ],
    ids=["immutable-mapping-mutation", "mutable-backing-map"],
)
def test_dynamic_import_registry_mutation_and_mutable_backing_fail_closed(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(source, tmp_path, monkeypatch)

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "importer provenance" in finding.detail
        for finding in findings
    )


def test_dynamic_import_nonimporter_globals_lookup_is_an_explicit_no_import_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """
from importlib import import_module
from types import MappingProxyType
ROUTES = MappingProxyType({("catalog", "alpha"): ("polisyos.catalog", "alpha")})
def resolve(owner, name):
    binding_key = (owner, name)
    _, target_name = ROUTES[binding_key]
    return globals().get(target_name)("unguarded_registry_lookup")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []

    namespace = runpy.run_path(str(tmp_path / "src" / "dynamic_fixture.py"))
    import_calls: list[str] = []

    def import_trap(target: str) -> object:
        import_calls.append(target)
        return object()

    namespace["resolve"].__globals__["import_module"] = import_trap
    assert "alpha" not in namespace
    with pytest.raises(TypeError):
        namespace["resolve"]("catalog", "alpha")
    assert import_calls == []


def test_dynamic_import_unchecked_lookup_of_importer_requires_canonical_registry_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """
from importlib import import_module
from types import MappingProxyType
ROUTES = MappingProxyType({("catalog", "loader"): ("polisyos.catalog", "import_module")})
def resolve(owner, name):
    binding_key = (owner, name)
    _, target_name = ROUTES[binding_key]
    return globals().get(target_name)("unchecked_registry_lookup")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["unchecked_registry_lookup"]

    namespace = runpy.run_path(str(tmp_path / "src" / "dynamic_fixture.py"))
    import_calls: list[str] = []
    expected_result = object()

    def import_trap(target: str) -> object:
        import_calls.append(target)
        return expected_result

    namespace["resolve"].__globals__["import_module"] = import_trap
    assert namespace["resolve"]("catalog", "loader") is expected_result
    assert import_calls == ["unchecked_registry_lookup"]

    missing_row_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "unchecked_registry_lookup" in finding.detail
        for finding in missing_row_findings
    )

    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    removed_row_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "unchecked_registry_lookup" in finding.detail
        for finding in removed_row_findings
    )


def _dynamic_import_internal_modules_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: dict[str, str],
) -> Path:
    """Build an internal ``polisyos`` source tree for import-binding tests."""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, "")
    source_root = tmp_path / "src"
    monkeypatch.setattr(preflight, "SRC_ROOT", source_root)
    for module, source in modules.items():
        module_path = source_root.joinpath(*module.split(".")).with_suffix(".py")
        module_path.parent.mkdir(parents=True, exist_ok=True)
        module_path.write_text(source, encoding="utf-8")
    return registry_path


def test_dynamic_import_collector_ignores_ambiguous_class_call_and_keeps_import_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.core.__init__": "from . import artifacts\n",
            "polisyos.core.artifacts": "from pydantic import BaseModel\n\nclass ArtifactID(BaseModel):\n    value: str\n",
        },
    )
    source = """
from importlib import import_module as load_module
from polisyos.core import artifacts

record_ref = artifacts.ArtifactID.model_validate({"value": "fixture"})
load_module("collector_alias_positive")
"""
    source_path = tmp_path / "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source, encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["collector_alias_positive"]
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path.write_text(
        source.replace('load_module("collector_alias_positive")', ""),
        encoding="utf-8",
    )
    stale_source_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists"
        and "collector_alias_positive" in finding.detail
        for finding in stale_source_findings
    )

    source_path.write_text(source, encoding="utf-8")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    removed_row_findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and "collector_alias_positive" in finding.detail
        for finding in removed_row_findings
    )


@pytest.mark.parametrize(
    ("source", "expected_patterns"),
    [
        (
            """
import subprocess

def _run_git(*args):
    return subprocess.run(
        ("/usr/bin/git", *args),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

head = _run_git("rev-parse", "HEAD")
""",
            [],
        ),
        (
            """
from importlib import import_module

def invoke(*callbacks):
    callbacks[0]("variadic_body_importer")

invoke(import_module)
""",
            ["variadic_body_importer"],
        ),
        (
            """
from importlib import import_module

def invoke(*callbacks):
    callbacks[0]("starred_forwarded_varargs_body")

def forward(*callbacks):
    invoke(*callbacks)

forward(*(import_module,))
""",
            ["starred_forwarded_varargs_body"],
        ),
        (
            """
from importlib import import_module

def invoke(**callbacks):
    callbacks["loader"]("keyword_variadic_body_importer")

invoke(loader=import_module)
""",
            ["keyword_variadic_body_importer"],
        ),
        (
            """
from importlib import import_module

def invoke(**callbacks):
    callbacks["loader"]("expanded_kwargs_forwarded_body")

def forward(**callbacks):
    invoke(**callbacks)

forward(**{"loader": import_module})
""",
            ["expanded_kwargs_forwarded_body"],
        ),
        (
            """
from importlib import import_module

def invoke(label, callback):
    callback("dict_star_duplicate_keys")

invoke(*{"label": "first", "label": "last"}, import_module)
""",
            ["dict_star_duplicate_keys"],
        ),
        (
            """
from importlib import import_module

def invoke(**callbacks):
    callbacks["loader"]("dict_double_star_last_value")

invoke(**{"loader": None, "loader": import_module})
""",
            ["dict_double_star_last_value"],
        ),
        (
            """
from importlib import import_module

def invoke(**callbacks):
    callbacks["loader"]("overwritten_importer_is_not_called")

invoke(**{"loader": import_module, "loader": None})
""",
            [],
        ),
        (
            """
from importlib import import_module

routes = {"loader": None, "loader": import_module}
routes["loader"]("dict_subscript_last_value")
""",
            ["dict_subscript_last_value"],
        ),
        (
            """
from importlib import import_module

routes = {1: None, True: import_module}
routes[1]("dict_python_bool_int_key_alias")
""",
            ["dict_python_bool_int_key_alias"],
        ),
        (
            """
from importlib import import_module

routes = {"loader": import_module, "loader": None}
routes["loader"]("dict_subscript_overwritten_importer")
""",
            [],
        ),
        (
            """
from importlib import import_module

def invoke(label, /, callback):
    callback("positional_only_callback")

invoke("local", import_module)
""",
            ["positional_only_callback"],
        ),
        (
            """
from importlib import import_module

def invoke(callback, mode="safe"):
    callback("positional_or_keyword_default")

invoke(import_module)
""",
            ["positional_or_keyword_default"],
        ),
        (
            """
from importlib import import_module

def invoke(*, mode="safe", loader):
    loader("keyword_only_importer")

invoke(loader=import_module)
""",
            ["keyword_only_importer"],
        ),
    ],
    ids=[
        "benign-git-helper-varargs",
        "varargs-body-importer",
        "starred-varargs-forward-to-body",
        "kwargs-body-importer",
        "expanded-kwargs-forward-to-body",
        "dict-star-collapses-duplicate-keys",
        "dict-double-star-last-value-wins",
        "dict-double-star-overwrites-importer",
        "dict-subscript-last-value",
        "dict-python-bool-int-key-alias",
        "dict-subscript-overwritten-importer",
        "positional-only-callback",
        "positional-or-keyword-default",
        "keyword-only-with-default",
    ],
)
def test_dynamic_import_collector_binds_complete_local_call_argument_shapes(
    source: str,
    expected_patterns: list[str],
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    entries = scanner.scan(ast.parse(source))

    assert [entry["pattern"] for entry in entries] == expected_patterns


@pytest.mark.parametrize(
    "source",
    [
        """
def invoke(*callbacks):
    callbacks[0]("unknown_starred_importer")

invoke(*unresolved_values)
""",
        """
def invoke(**callbacks):
    callbacks["loader"]("unknown_keyword_importer")

invoke(**unresolved_mapping)
""",
    ],
    ids=["unknown-star-expansion", "unknown-double-star-expansion"],
)
def test_dynamic_import_collector_refuses_unbounded_local_call_expansions(
    source: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=r"starred local function argument|expanded local function keyword mapping",
    ):
        scanner.scan(ast.parse(source))


@pytest.mark.parametrize(
    "source",
    [
        """
from importlib import import_module

def identity(*callbacks):
    return callbacks[0]

selected = identity(*(import_module,))
""",
        """
from importlib import import_module

def identity(**callbacks):
    return callbacks["loader"]

selected = identity(**{"loader": import_module})
""",
    ],
    ids=["varargs-return", "kwargs-return"],
)
def test_dynamic_import_collector_keeps_local_importer_return_escape_guard(
    source: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="guarded importer value escapes through a function return",
    ):
        scanner.scan(ast.parse(source))


def test_dynamic_import_collector_refuses_unresolved_literal_mapping_key() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved through reflective subscript access",
    ):
        scanner.scan(
            ast.parse(
                "from importlib import import_module\n"
                "routes = {unresolved_name: import_module}\n"
                "routes['loader']('unknown_literal_mapping_key')\n"
            )
        )


def test_dynamic_import_collector_allows_ambiguous_nonimporter_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """VALUES = ("one", "two")

def choose(index):
    return VALUES[index]
""",
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_collector_ignores_sys_path_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """import sys

sys.path.insert(0, "fixture-root")
""",
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_collector_allows_unrelated_importlib_utility_call() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    entries = scanner.scan(
        ast.parse("import importlib.util\nimportlib.util.find_spec('polisyos.core')")
    )

    assert entries == []


def test_dynamic_import_collector_rejects_reflection_from_importer_namespace_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """import importlib

attribute_name = unresolved_name
getattr(vars(importlib), attribute_name)("reflected_dynamic_target")
""",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="computed reflection has unresolved importer provenance",
    ):
        preflight.collect_dynamic_imports()


def test_dynamic_import_collector_rejects_reflection_from_importer_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        """import importlib

attribute_name = unresolved_name
getattr(importlib, attribute_name)("reflected_dynamic_target")
""",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="computed reflection has unresolved importer provenance",
    ):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    "source",
    [
        'import sys\nmodule_name = unresolved_name\nsys.modules[module_name].import_module("private.module")',
        "import sys\nmodule_name = unresolved_name\nsys.modules[module_name].metadata.entry_points()",
        'import sys\nmodule_name = unresolved_name\nsys.modules[module_name].eval("unmodeled code")',
        'import sys\nmodule_name = unresolved_name\nsys.modules[module_name].getattr(None, "import_module")',
    ],
)
def test_dynamic_import_collector_rejects_unresolved_registry_callable_members(
    source: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        scanner.scan(ast.parse(source))


def test_dynamic_import_collector_ignores_unknown_registry_nonimporter_method() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py", relative_path="src/probe.py"
    )

    entries = scanner.scan(
        ast.parse("import sys\nmodule_name = unresolved_name\nsys.modules[module_name].get_name()")
    )

    assert entries == []


def _dynamic_import_internal_map_consumer(source: str) -> str:
    return f"""from importlib import import_module
{source}

def resolve(owner, name):
    binding_key = (owner, name)
    if binding_key in ROUTE_TABLE:
        module_name, target_name = ROUTE_TABLE[binding_key]
    else:
        raise LookupError(binding_key)
    return globals().get(target_name)("cross-module-map-hidden-import")
"""


def test_dynamic_import_constructed_source_object_field_preserves_importer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.carrier": """from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
""",
            "polisyos.consumer": """from importlib import import_module
from polisyos.carrier import Carrier

carrier = Carrier(loader=import_module)
carrier.loader("constructed_object_hidden_import")
""",
        },
    )

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["constructed_object_hidden_import"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and finding.detail.endswith("'constructed_object_hidden_import')")
        for finding in findings
    )


def test_dynamic_import_constructed_local_source_object_field_preserves_importer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object

carrier = Carrier(loader=import_module)
carrier.loader("local_constructed_object_hidden_import")
""",
        },
    )

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["local_constructed_object_hidden_import"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and finding.detail.endswith("'local_constructed_object_hidden_import')")
        for finding in findings
    )


def test_dynamic_import_external_constructor_does_not_admit_importer_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from external_package import Carrier

carrier = Carrier(loader=import_module)
carrier.loader("external_constructed_object_hidden_import")
""",
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="guarded importer value escapes through a call argument",
    ):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    "class_extension",
    [
        "    def __getattribute__(self, name):\n        return super().__getattribute__(name)\n",
        "    def __getattr__(self, name):\n        return None\n",
        "    def __init__(self, **values):\n        self.__dict__.update(values)\n",
        "    def __new__(cls, **values):\n        return super().__new__(cls)\n",
        "    def __call__(self, *args, **kwargs):\n        return None\n",
    ],
)
def test_dynamic_import_constructed_source_object_hooks_defer_without_selector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_extension: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
"""
            + class_extension
            + "\ncarrier = Carrier(loader=import_module)\n"
        },
    )

    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "class_extension",
    [
        "    def __getattribute__(self, name):\n        return super().__getattribute__(name)\n",
        "    def __getattr__(self, name):\n        return None\n",
        "    def __init__(self, **values):\n        self.__dict__.update(values)\n",
        "    def __new__(cls, **values):\n        return super().__new__(cls)\n",
        "    def __call__(self, *args, **kwargs):\n        return None\n",
    ],
)
def test_dynamic_import_constructed_source_object_hooks_refuse_selected_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_extension: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
"""
            + class_extension
            + '\ncarrier = Carrier(loader=import_module)\ncarrier.loader("hook_hidden_import")\n'
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    "class_declaration",
    [
        """def decorate(cls):
    return cls

@decorate
class Carrier(BaseModel):
    loader: object
""",
        """class Carrier(BaseModel, metaclass=type):
    loader: object
""",
    ],
)
def test_dynamic_import_constructed_source_class_metadata_defers_without_selector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_declaration: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": (
                "from importlib import import_module\n"
                "from pydantic import BaseModel\n\n"
                + class_declaration
                + "\ncarrier = Carrier(loader=import_module)\n"
            )
        },
    )

    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "class_declaration",
    [
        """def decorate(cls):
    return cls

@decorate
class Carrier(BaseModel):
    loader: object
""",
        """class Carrier(BaseModel, metaclass=type):
    loader: object
""",
    ],
)
def test_dynamic_import_constructed_source_class_metadata_refuses_selected_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_declaration: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": (
                "from importlib import import_module\n"
                "from pydantic import BaseModel\n\n"
                + class_declaration
                + '\ncarrier = Carrier(loader=import_module)\ncarrier.loader("metadata_hidden_import")\n'
            )
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize("select_importer", [False, True])
@pytest.mark.parametrize(
    "class_effect",
    [
        "Alias.__getattribute__ = replacement",
        "setattr(Alias, '__getattribute__', replacement)",
        "Alias.model_rebuild()",
        "opaque_effect([Alias])",
    ],
)
@pytest.mark.parametrize("constructed_class", ["Carrier", "Child"])
def test_dynamic_import_source_class_effects_invalidate_field_summaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    class_effect: str,
    constructed_class: str,
    select_importer: bool,
) -> None:
    selected_call = (
        'carrier.loader("source_class_effect_hidden_import")\n' if select_importer else ""
    )
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.a_consumer": (
                "from importlib import import_module\n"
                f"from polisyos.z_model import {constructed_class} as Carrier\n\n"
                'carrier = Carrier(loader="safe", spare=import_module)\n' + selected_call
            ),
            "polisyos.z_model": """from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
    spare: object

class Child(Carrier):
    pass
""",
            "polisyos.zz_effect": """from polisyos.z_model import Carrier as SourceClass

Alias = SourceClass

def replacement(self, name):
    if name == "loader":
        return object.__getattribute__(self, "spare")
    return object.__getattribute__(self, name)

"""
            + class_effect
            + "\n",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    findings = preflight.validate_dynamic_imports()

    if select_importer:
        assert any(
            finding.message == "dynamic import source inventory is incomplete"
            and "dynamic importer binding is ambiguous or unresolved" in finding.detail
            for finding in findings
        ), findings
    else:
        assert findings == []


def test_dynamic_import_constructed_source_object_unknown_field_is_ambiguous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object

carrier = Carrier()
""",
        },
    )
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))
    environment = source_bindings._module_environment("polisyos.consumer", ())

    assert environment is not None
    carrier = environment["carrier"]
    assert carrier.kind == "object"
    unknown = preflight._dynamic_attribute_binding(carrier, "not_a_declared_field")
    assert unknown.kind == "ambiguous"
    assert unknown.guarded


def test_dynamic_import_opaque_dataclass_return_without_selector_is_not_a_source_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class RawExplanation:
    method_id: str
    attributions: Mapping[str, float]
    params: Mapping[str, object] = field(default_factory=dict)

def explain() -> RawExplanation:
    return RawExplanation(method_id="ale", attributions={"feature": 0.0})
""",
        },
    )

    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize("select_importer", [False, True])
def test_dynamic_import_deferred_object_is_target_relevant_through_alias_and_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    select_importer: bool,
) -> None:
    selected_call = (
        'owners["primary"].loader("deferred_object_hidden_import")\n' if select_importer else ""
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
    def __getattribute__(self, name):
        return super().__getattribute__(name)

loader_alias = import_module
carrier = Carrier(loader=loader_alias)
alias = carrier
owners = {"primary": alias}
"""
            + selected_call
        },
    )

    if select_importer:
        with pytest.raises(
            preflight.DynamicImportCollectionError,
            match="dynamic importer binding is ambiguous or unresolved",
        ):
            preflight.collect_dynamic_imports()
    else:
        assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "projection",
    [
        'b.inner.loader("nested_deferred_selected")',
        'aliases["owner"].owner.inner.loader("mapping_alias_selected")',
        'sequence[0].owner.inner.loader("sequence_unpack_selected")',
        'list_copy[0].owner.inner.loader("container_copy_selected")',
        'joined.loader("expression_join_selected")',
        ('getattr(getattr(getattr(c, "owner"), "inner"), "loader")("getattr_chain_selected")'),
    ],
    ids=(
        "reviewer-two-class-chain",
        "mapping-alias",
        "sequence-alias",
        "container-copy",
        "expression-join",
        "getattr-chain",
    ),
)
def test_dynamic_import_guarded_origin_survives_nested_deferred_projections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection: str,
) -> None:
    source = (
        "from importlib import import_module\n"
        "from pydantic import BaseModel\n\n"
        "class CarrierA(BaseModel):\n"
        "    loader: object\n"
        "    def __getattribute__(self, name):\n"
        "        return super().__getattribute__(name)\n\n"
        "class CarrierB(BaseModel):\n"
        "    inner: object\n"
        "    def __getattribute__(self, name):\n"
        "        return super().__getattribute__(name)\n\n"
        "class CarrierC(BaseModel):\n"
        "    owner: object\n"
        "    def __getattribute__(self, name):\n"
        "        return super().__getattribute__(name)\n\n"
        "a = CarrierA(loader=import_module)\n"
        "b = CarrierB(inner=a)\n"
        "c = CarrierC(owner=b)\n"
        'aliases = {"owner": c}\n'
        "sequence = (c,)\n"
        "list_copy = list(sequence)\n"
        "joined = b.inner if unknown_condition else a\n"
        f"{projection}\n"
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {"polisyos.consumer": source},
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=r"dynamic importer binding is ambiguous or unresolved|computed reflection has unresolved importer provenance",
    ):
        preflight.collect_dynamic_imports()


def test_dynamic_import_guarded_origin_nested_deferred_no_sink_stays_nonfailing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class CarrierA(BaseModel):
    loader: object
    def __getattribute__(self, name):
        return super().__getattribute__(name)

class CarrierB(BaseModel):
    inner: object
    def __getattribute__(self, name):
        return super().__getattribute__(name)

a = CarrierA(loader=import_module)
b = CarrierB(inner=a)
""",
        },
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_operator_results_keep_unknown_callable_origin_ambiguous(
    tmp_path: Path,
) -> None:
    class RichCarrier:
        def __eq__(self, other: object) -> object:
            del other
            return __import__

    class ContainsCarrier:
        def __contains__(self, other: object) -> object:
            del other
            return __import__

    # Python rich-comparison methods may return any object, including an importer.
    assert (RichCarrier() == object())("json").__name__ == "json"
    assert type(RichCarrier() is None) is bool
    assert type(1 in ContainsCarrier()) is bool
    assert type(1 not in ContainsCarrier()) is bool

    scanner = preflight._DynamicImportSourceScanner(
        tmp_path / "consumer.py",
        relative_path="src/polisyos/consumer.py",
    )
    environment = {
        "left": preflight._DYNAMIC_OTHER,
        "right": preflight._DYNAMIC_OTHER,
        "container": preflight._DYNAMIC_OTHER,
        "importer": preflight._DynamicImportBinding(
            "callable", "importlib.import_module", guarded=True
        ),
    }

    def bind(expression: str):
        node = ast.parse(expression, mode="eval").body
        return scanner._expression_binding(node, environment.copy(), [], {})

    rich_result = bind("left == right")
    binary_result = bind("left + right")
    unary_result = bind("-left")
    assert all(result.kind == "ambiguous" for result in (rich_result, binary_result, unary_result))
    selected_call = ast.parse('selected("operator_returned_importer")').body[0].value
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        scanner._record_call(selected_call, rich_result)

    # Identity, membership, and exact literal comparisons have builtin bool results.
    assert bind("importer is None").kind == "boolean"
    assert bind("importer is not None").kind == "boolean"
    assert bind("1 in container").kind == "boolean"
    assert bind("1 not in container").kind == "boolean"
    assert bind("1 == 2").kind == "boolean"
    assert bind("not importer").kind == "boolean"


def test_dynamic_import_importer_in_deferred_object_refuses_opaque_call_argument(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.consumer": """from importlib import import_module
from pydantic import BaseModel

class Carrier(BaseModel):
    loader: object
    def __getattribute__(self, name):
        return super().__getattribute__(name)

def opaque_consumer(value):
    return None

opaque_consumer(Carrier(loader=import_module))
""",
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="guarded importer value escapes through a call argument",
    ):
        preflight.collect_dynamic_imports()


def test_dynamic_import_resolves_source_owned_immutable_mapping_through_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.contract_contracts": """from types import MappingProxyType as FrozenMap

ROUTE_DECLARATIONS = FrozenMap({
    ("catalog", "loader"): ("polisyos.catalog", "import_module"),
})
""",
            "polisyos.catalog.route_facade": """from .contract_contracts import ROUTE_DECLARATIONS as DECLARED_ROUTES

ROUTE_TABLE = DECLARED_ROUTES
""",
            "polisyos.catalog.route_consumer": _dynamic_import_internal_map_consumer(
                "from .route_facade import ROUTE_TABLE as ROUTE_TABLE"
            ),
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["cross-module-map-hidden-import"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []


@pytest.mark.parametrize(
    "modules",
    [
        {
            "polisyos.catalog.contracts": """from types import MappingProxyType

mutable_routes = {
    ("catalog", "loader"): ("polisyos.catalog", "import_module"),
}
ROUTE_TABLE = MappingProxyType(mutable_routes)
""",
            "polisyos.catalog.consumer": _dynamic_import_internal_map_consumer(
                "from .contracts import ROUTE_TABLE"
            ),
        },
        {
            "polisyos.catalog.cycle_a": "from .cycle_b import ROUTE_TABLE\n",
            "polisyos.catalog.cycle_b": "from .cycle_a import ROUTE_TABLE\n",
            "polisyos.catalog.consumer": _dynamic_import_internal_map_consumer(
                "from .cycle_a import ROUTE_TABLE"
            ),
        },
        {
            "polisyos.catalog.contracts": """from types import MappingProxyType

ROUTE_TABLE = MappingProxyType({
    ("catalog", "loader"): ("polisyos.catalog", "import_module"),
})
""",
            "polisyos.catalog.reexport": "from .contracts import *\n",
            "polisyos.catalog.consumer": _dynamic_import_internal_map_consumer(
                "from .reexport import ROUTE_TABLE"
            ),
        },
    ],
    ids=["mutable-backing", "reexport-cycle", "star-reexport"],
)
def test_dynamic_import_unresolved_internal_mapping_never_defaults_to_absence(
    modules: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_import_source_binding_cannot_escape_selected_source_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.consumer": _dynamic_import_internal_map_consumer(
                "from .contracts import ROUTE_TABLE"
            ),
        },
    )
    outside_path = tmp_path / "unselected" / "polisyos" / "catalog" / "contracts.py"
    outside_path.parent.mkdir(parents=True)
    outside_path.write_text(
        """from types import MappingProxyType

ROUTE_TABLE = MappingProxyType({
    ("catalog", "loader"): ("polisyos.catalog", "import_module"),
})
""",
        encoding="utf-8",
    )

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_import_resolves_literal_pep562_exports_without_overtaint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.implementation": """def public_builder():
    return None
""",
            "polisyos.catalog.lazy_facade": """from typing import Any

def __getattr__(name: str) -> Any:
    if name in {"public_builder"}:
        from . import implementation as _implementation
        return getattr(_implementation, name)
    raise AttributeError(name)
""",
            "polisyos.catalog.lazy_consumer": """from .lazy_facade import public_builder

public_builder()
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert entries == []


def test_dynamic_import_resolves_immutable_mapping_pep562_facade_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.contracts": """from types import MappingProxyType

EXPORTS = MappingProxyType({
    "public_builder": ("polisyos.catalog.implementation", "public_builder"),
})
""",
            "polisyos.catalog.implementation": """def public_builder():
    return None
""",
            "polisyos.catalog.facade": """from importlib import import_module as _import_module
from typing import Any

from .contracts import EXPORTS

def __getattr__(name: str) -> Any:
    target = EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    target_module = _import_module(module_name)
    value = getattr(target_module, attribute_name)
    globals()[name] = value
    return value
""",
            "polisyos.catalog.consumer": """from .facade import public_builder

public_builder()
""",
        },
    )
    source_root = tmp_path / "src"
    for package_dir in (source_root / "polisyos", source_root / "polisyos/catalog"):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    entries = preflight.collect_dynamic_imports()
    assert len(entries) == 1
    assert entries[0]["source_file"] == "src/polisyos/catalog/facade.py"
    assert entries[0]["call"] == "importlib.import_module"
    assert entries[0]["pattern"] == "module_name"
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")

    child_probe = """import importlib.util
import json
import sys
from pathlib import Path
from tools.quality.validation import decomposition_preflight as preflight
root = Path(sys.argv[1])
preflight.REPO_ROOT = root
preflight.SRC_ROOT = root / "src"
preflight.DYNAMIC_IMPORTS_PATH = root / "architecture/imports/dynamic.toml"
target = "polisyos.catalog.implementation"
try:
    spec = importlib.util.find_spec(target)
except (ImportError, ModuleNotFoundError, ValueError):
    spec = None
findings = preflight.validate_dynamic_imports()
print(json.dumps({
    "target_origin": None if spec is None else spec.origin,
    "findings": [{"message": finding.message, "detail": finding.detail} for finding in findings],
}, sort_keys=True))
"""
    base_environment = os.environ.copy()

    def run_fresh_runtime_validator(*, target_on_pythonpath: bool) -> dict[str, object]:
        environment = base_environment.copy()
        pythonpath = [str(source_root)] if target_on_pythonpath else []
        if environment.get("PYTHONPATH"):
            pythonpath.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
        completed = subprocess.run(
            [sys.executable, "-c", child_probe, str(tmp_path)],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(completed.stdout)
        assert isinstance(result, dict)
        return result

    target_path = source_root / "polisyos/catalog/implementation.py"
    positive = run_fresh_runtime_validator(target_on_pythonpath=True)
    assert target_path.is_file()
    assert positive["target_origin"] == str(target_path)
    assert positive["findings"] == []

    negative = run_fresh_runtime_validator(target_on_pythonpath=False)
    assert target_path.is_file()
    assert negative["target_origin"] is None
    assert any(
        finding["message"] == "allowed dynamic import target does not resolve"
        for finding in negative["findings"]
    ), negative


def test_dynamic_import_pep562_map_preserves_importer_capability_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.contracts": """from types import MappingProxyType

EXPORTS = MappingProxyType({
    "loader": ("importlib", "import_module"),
})
""",
            "polisyos.catalog.facade": """from importlib import import_module as _import_module
from typing import Any

from .contracts import EXPORTS

def __getattr__(name: str) -> Any:
    target = EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    target_module = _import_module(module_name)
    value = getattr(target_module, attribute_name)
    globals()[name] = value
    return value
""",
            "polisyos.catalog.consumer": """from .facade import loader

loader("pep562-mapped-importer")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert {entry["pattern"] for entry in entries} == {
        "module_name",
        "pep562-mapped-importer",
    }
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_rejects_external_decorated_pep562_hook_and_removal_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": """from external_decorators import replace_hook

@replace_hook
def __getattr__(name):
    if name == "loader":
        return "ordinary value"
    raise AttributeError(name)
""",
            "polisyos.probe.consumer": """from .facade import loader

loader("json")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    external_root = tmp_path / "external"
    external_root.mkdir()
    (tmp_path / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/polisyos/probe/__init__.py").write_text("", encoding="utf-8")
    (external_root / "external_decorators.py").write_text(
        "from importlib import import_module\n"
        "def replace_hook(original):\n"
        "    def replacement(name):\n"
        "        if name == 'loader':\n"
        "            return import_module\n"
        "        raise AttributeError(name)\n"
        "    return replacement\n",
        encoding="utf-8",
    )
    selected_labels = [
        preflight._dynamic_source_label(path)
        for path in preflight._dynamic_source_paths("src", "tools", "apps", "packages")
    ]
    assert not any("external_decorators.py" in label for label in selected_labels)

    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; print(loader('json').__name__)",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert runtime.stdout.strip() == "json"

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()
    findings_with_property = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "ambiguous or unresolved" in finding.detail
        for finding in findings_with_property
    )

    facade_path = tmp_path / "src/polisyos/probe/facade.py"
    consumer_path = tmp_path / "src/polisyos/probe/consumer.py"
    facade_source = facade_path.read_text(encoding="utf-8")
    consumer_path.write_text("from .facade import loader\n", encoding="utf-8")
    assert "@replace_hook" in facade_source
    assert 'return "ordinary value"' in facade_source
    assert "from .facade import loader" in consumer_path.read_text(encoding="utf-8")
    assert 'loader("json")' not in consumer_path.read_text(encoding="utf-8")
    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_rejects_externally_rebound_pep562_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": """from external_decorators import replace_hook

def __getattr__(name):
    if name == "loader":
        return "ordinary value"
    raise AttributeError(name)

__getattr__ = replace_hook(__getattr__)
""",
            "polisyos.probe.consumer": """from .facade import loader

loader("json")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    external_root = tmp_path / "external"
    external_root.mkdir()
    (tmp_path / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/polisyos/probe/__init__.py").write_text("", encoding="utf-8")
    (external_root / "external_decorators.py").write_text(
        "from importlib import import_module\n"
        "def replace_hook(original):\n"
        "    def replacement(name):\n"
        "        if name == 'loader':\n"
        "            return import_module\n"
        "        raise AttributeError(name)\n"
        "    return replacement\n",
        encoding="utf-8",
    )
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; print(loader('json').__name__)",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert runtime.stdout.strip() == "json"

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    ("mutation", "removal_is_resolvable"),
    [
        ('globals()["__getattr__"] = replace_hook(__getattr__)', True),
        ('setattr(sys.modules[__name__], "__getattr__", replace_hook(__getattr__))', True),
        (
            'import builtins as _builtins\n_builtins.setattr(sys.modules[__name__], "__getattr__", replace_hook(__getattr__))',
            True,
        ),
        (
            'from builtins import globals as _globals\n_namespace = _globals()\n_namespace["__getattr__"] = replace_hook(__getattr__)',
            True,
        ),
        (
            'from builtins import setattr as _setattr\n_setattr(sys.modules[__name__], "__getattr__", replace_hook(__getattr__))',
            True,
        ),
        ('locals()["__getattr__"] = replace_hook(__getattr__)', True),
        (
            'from builtins import locals as _locals\n_locals()["__getattr__"] = replace_hook(__getattr__)',
            True,
        ),
        (
            'namespace = locals()\nnamespace_alias = namespace\nnamespace_alias["__getattr__"] = replace_hook(__getattr__)',
            True,
        ),
        ('vars()["__getattr__"] = replace_hook(__getattr__)', True),
        (
            'from builtins import vars as _vars\n_namespace = _vars()\n_namespace["__getattr__"] = replace_hook(__getattr__)',
            True,
        ),
        (
            'vars(sys.modules[__name__])["__getattr__"] = replace_hook(__getattr__)',
            False,
        ),
        (
            'sys.modules[__name__].__dict__["__getattr__"] = replace_hook(__getattr__)',
            False,
        ),
        (
            'getattr(sys.modules[__name__], "__dict__")["__getattr__"] = replace_hook(__getattr__)',
            False,
        ),
        (
            'namespace = getattr(sys.modules[__name__], "__dict__")\nnamespace["__getattr__"] = replace_hook(__getattr__)',
            False,
        ),
        # These operations are also rejected by the main AST walker before it
        # can prove that removing the consumer eliminates the route. Keep their
        # removal controls separate from the supported reflection grammar.
        ('locals().update({"__getattr__": replace_hook(__getattr__)})', False),
        (
            "from external_decorators import mutate_namespace as _mutate_namespace\n_mutate_namespace(locals(), replace_hook(__getattr__))",
            False,
        ),
    ],
)
def test_dynamic_import_rejects_reflectively_rebound_pep562_hook(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    removal_is_resolvable: bool,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": f"""import sys
from external_decorators import replace_hook

def __getattr__(name):
    if name == "loader":
        return "ordinary value"
    raise AttributeError(name)

{mutation}
""",
            "polisyos.probe.consumer": """from .facade import loader

loader("json")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    external_root = tmp_path / "external"
    external_root.mkdir()
    (tmp_path / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/polisyos/probe/__init__.py").write_text("", encoding="utf-8")
    (external_root / "external_decorators.py").write_text(
        "from importlib import import_module\n"
        "def replace_hook(original):\n"
        "    def replacement(name):\n"
        "        if name == 'loader':\n"
        "            return import_module\n"
        "        raise AttributeError(name)\n"
        "    return replacement\n"
        "def mutate_namespace(namespace, replacement):\n"
        "    namespace['__getattr__'] = replacement\n",
        encoding="utf-8",
    )
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; print(loader('json').__name__)",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert runtime.stdout.strip() == "json"

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "ambiguous or unresolved" in finding.detail
        for finding in findings
    )

    if removal_is_resolvable:
        facade_path = tmp_path / "src/polisyos/probe/facade.py"
        consumer_path = tmp_path / "src/polisyos/probe/consumer.py"
        facade_source = facade_path.read_text(encoding="utf-8")
        consumer_path.write_text("from .facade import loader\n", encoding="utf-8")
        assert "replace_hook" in facade_source
        assert 'return "ordinary value"' in facade_source
        assert 'loader("json")' not in consumer_path.read_text(encoding="utf-8")
        assert preflight.collect_dynamic_imports() == []
        assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_rejects_pep562_hook_with_default_namespace_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": """import importlib
from builtins import str as import_module

def _install_importer():
    globals()["import_module"] = importlib.import_module

def __getattr__(name, _installed=_install_importer()):
    if name == "loader":
        return import_module
    raise AttributeError(name)
""",
            "polisyos.probe.consumer": """from .facade import loader

loader("json")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    (tmp_path / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/polisyos/probe/__init__.py").write_text("", encoding="utf-8")

    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; print(loader('json').__name__)",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    assert runtime.stdout.strip() == "json"
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_import_rejects_unresolved_or_mutable_pep562_export_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.facade": """from importlib import import_module as _import_module

EXPORTS = {"loader": ("importlib", "import_module")}

def __getattr__(name: str):
    target = EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    target_module = _import_module(module_name)
    return getattr(target_module, attribute_name)
""",
            "polisyos.catalog.consumer": """from .facade import loader

loader("polisyos.catalog.private_target")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_import_scope_setdefault_preserves_importer_provenance_and_removal_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """from importlib import import_module

globals().setdefault("_selected_importer", import_module)
globals().setdefault("_selected_importer", __import__)

def resolve():
    return globals().get("_selected_importer")("scope-setdefault-hidden-import")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["scope-setdefault-hidden-import"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    removed_source = source.replace(
        'globals().setdefault("_selected_importer", import_module)\n',
        "",
    ).replace(
        'globals().setdefault("_selected_importer", __import__)\n',
        "",
    )
    (tmp_path / "src" / "dynamic_fixture.py").write_text(removed_source, encoding="utf-8")
    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "source",
    [
        """
import importlib
def make_loader():
    return importlib.import_module
""",
        """
import importlib
consume(importlib.import_module)
""",
        """
import importlib
holder.loader = importlib.import_module
""",
        """
import importlib
consume([importlib.import_module])
""",
        """
import importlib
def make_loader(loader=importlib.import_module):
    return None
""",
        """
import importlib
class ImportHooks:
    loader = importlib.import_module
""",
        """
import importlib
def make_loader():
    yield importlib.import_module
""",
    ],
)
def test_dynamic_import_validator_refuses_guarded_importer_escape_boundaries(
    source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(source, tmp_path, monkeypatch)

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "guarded importer" in finding.detail
        for finding in findings
    )


def test_dynamic_import_validator_reports_outside_source_symlink_as_typed_input_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    registry_path = _dynamic_import_fixture(repository, monkeypatch, "")
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    outside_path = tmp_path / "outside.py"
    outside_path.write_text(
        'import importlib\nimportlib.import_module("outside_symlink_call")\n',
        encoding="utf-8",
    )
    selected_path = repository / "src" / "linked.py"
    selected_path.symlink_to(outside_path)

    findings = preflight.validate_dynamic_imports()

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "src/linked.py" in finding.detail
        and "outside repository" in finding.detail
        for finding in findings
    )


@pytest.mark.parametrize(
    ("source", "expected_pattern"),
    [
        (
            "import importlib\n"
            "for loader in [importlib.import_module]:\n"
            "    loader('for_target_origin')\n",
            "for_target_origin",
        ),
        (
            "import importlib\n"
            "match (importlib.import_module,):\n"
            "    case (loader,):\n"
            "        loader('match_capture_origin')\n",
            "match_capture_origin",
        ),
        (
            "import importlib\n"
            "[loader('comprehension_target_origin') "
            "for loader in (importlib.import_module,)]\n",
            "comprehension_target_origin",
        ),
        (
            "import importlib\n"
            "for loader in {importlib.import_module: None}:\n"
            "    loader('mapping_key_origin')\n",
            "mapping_key_origin",
        ),
        (
            "import importlib\n"
            "for ((loader,),) in [((importlib.import_module,),)]:\n"
            "    loader('nested_sequence_origin')\n",
            "nested_sequence_origin",
        ),
    ],
)
def test_dynamic_import_guarded_provenance_survives_container_consumers(
    source: str,
    expected_pattern: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == [expected_pattern]

    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import call is not registered"
        and expected_pattern in finding.detail
        for finding in findings
    )


def test_dynamic_import_validator_refuses_lambda_implicit_guarded_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(
        "import importlib\n"
        "loader_factory = lambda: importlib.import_module\n"
        "loader_factory()('lambda_implicit_return')\n",
        tmp_path,
        monkeypatch,
    )

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "lambda implicit return" in finding.detail
        for finding in findings
    )


def test_dynamic_import_guarded_transfer_allows_unrelated_callable_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        "def ordinary_loader():\n"
        "    return None\n"
        "ordinary_loaders = [ordinary_loader for item in ordinary_values]\n"
        "for loader in ordinary_loaders:\n"
        "    loader()\n",
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_validator_refuses_guarded_value_through_unsupported_expression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(
        "import importlib\n"
        "loader = (importlib,)[0].import_module\n"
        "loader('unsupported_subscript_origin')\n",
        tmp_path,
        monkeypatch,
    )

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
        for finding in findings
    )


def test_dynamic_import_match_capture_refuses_cross_scope_guarded_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(
        "import importlib\n"
        "loader = ordinary_loader\n"
        "def replace_global_loader():\n"
        "    global loader\n"
        "    match (importlib.import_module,):\n"
        "        case (loader,):\n"
        "            loader('cross_scope_match_capture')\n",
        tmp_path,
        monkeypatch,
    )

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "cross-scope" in finding.detail
        for finding in findings
    )


def _immutable_import_map_source(map_body: str) -> str:
    return f"""\
from importlib import import_module
from types import MappingProxyType

_EXPORTS = MappingProxyType({{
{map_body}
}})

def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    return import_module(module_name)
"""


def test_dynamic_imports_gate_uses_effective_duplicate_literal_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _immutable_import_map_source(
        '    "same": ("polisyos.demo.alpha", "Alpha"),\n    "same": ("polisyos.demo.beta", "Beta"),'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    source_path = tmp_path / "src" / "dynamic_fixture.py"

    entries = preflight.collect_dynamic_imports()

    assert len(entries) == 1
    assert entries[0]["allowed_targets"] == ["polisyos.demo.beta"]
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    reordered = _immutable_import_map_source(
        '    "same": ("polisyos.demo.beta", "Beta"),\n    "same": ("polisyos.demo.alpha", "Alpha"),'
    )
    source_path.write_text(reordered, encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert findings
    assert entries[0]["allowed_targets"] == ["polisyos.demo.beta"]


def test_dynamic_imports_gate_folds_known_unpack_before_duplicate_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
from importlib import import_module
from types import MappingProxyType

_EXPORTS = MappingProxyType({
    **{"same": ("polisyos.demo.alpha", "Alpha")},
    "same": ("polisyos.demo.beta", "Beta"),
})

def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    return import_module(module_name)
"""
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    assert len(entries) == 1
    assert entries[0]["allowed_targets"] == ["polisyos.demo.beta"]


@pytest.mark.parametrize(
    ("map_body", "expected_targets"),
    [
        (
            '    1: ("polisyos.demo.numeric", "Hidden"),\n'
            '    "named": ("polisyos.demo.visible", "Visible"),',
            ["polisyos.demo.numeric", "polisyos.demo.visible"],
        ),
        (
            '    1: ("polisyos.demo.numeric", "Hidden"),\n    "named": (42, "Visible"),',
            [],
        ),
    ],
)
def test_dynamic_imports_gate_finite_targets_require_string_module_values(
    map_body: str,
    expected_targets: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _immutable_import_map_source(map_body)
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    assert len(entries) == 1
    assert entries[0]["allowed_targets"] == expected_targets


@pytest.mark.parametrize(
    "map_body",
    [
        '    **external_exports,\n    "same": ("polisyos.demo.alpha", "Alpha"),',
        '    "same": ("polisyos.demo.alpha", "Alpha"),\n    computed_name: ("polisyos.demo.beta", "Beta"),',
        '    ["not_hashable"]: ("polisyos.demo.alpha", "Alpha"),',
    ],
)
def test_dynamic_imports_gate_refuses_nonprovable_immutable_map_keys(
    map_body: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _immutable_import_map_source(map_body)
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    ("first_key", "last_key", "lookup_key", "first_target", "last_target", "expects_importer"),
    [
        ("True", "1", "1", "ordinary_loader", "import_module", True),
        ("1", "True", "1", "import_module", "ordinary_loader", False),
        ("1", "1.0", "1.0", "ordinary_loader", "import_module", True),
        ("1.0", "1", "1", "import_module", "ordinary_loader", False),
        ('"1"', "1", '"1"', "ordinary_loader", "import_module", False),
        ("1", '"1"', '"1"', "import_module", "ordinary_loader", False),
        (
            '("catalog", True)',
            '("catalog", 1)',
            '("catalog", 1)',
            "ordinary_loader",
            "import_module",
            True,
        ),
        (
            '("catalog", 1)',
            '("catalog", True)',
            '("catalog", 1)',
            "import_module",
            "ordinary_loader",
            False,
        ),
    ],
)
def test_dynamic_import_mapping_normalizer_uses_python_hashable_key_collisions(
    first_key: str,
    last_key: str,
    lookup_key: str,
    first_target: str,
    last_target: str,
    expects_importer: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = f"""\
from importlib import import_module
from types import MappingProxyType

ROUTES = MappingProxyType({{
    {first_key}: {first_target!r},
    {last_key}: {last_target!r},
}})
def ordinary_loader(name):
    return name
route_key = {lookup_key}
target_name = ROUTES[route_key]
globals().get(target_name)(\"python_hashable_collision_import\")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    if expects_importer:
        assert [entry["pattern"] for entry in entries] == ["python_hashable_collision_import"]
        registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
        assert preflight.validate_dynamic_imports() == []
    else:
        assert entries == []


@pytest.mark.parametrize(
    ("mapping_body", "expects_importer"),
    [
        (
            '\n    **{True: "ordinary_loader"},\n    1: "import_module",',
            True,
        ),
        (
            '\n    1: "import_module",\n    **{True: "ordinary_loader"},',
            False,
        ),
    ],
)
def test_dynamic_import_mapping_normalizer_folds_python_key_collisions_across_unpack(
    mapping_body: str,
    expects_importer: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = f"""\
from importlib import import_module
from types import MappingProxyType

ROUTES = MappingProxyType({{{mapping_body}
}})
def ordinary_loader(name):
    return name
target_name = ROUTES[1]
globals().get(target_name)(\"python_hashable_unpack_collision\")
"""
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    if expects_importer:
        assert [entry["pattern"] for entry in entries] == ["python_hashable_unpack_collision"]
    else:
        assert entries == []


def test_dynamic_import_mapping_normalizer_does_not_treat_unhashable_keys_as_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
from importlib import import_module
from types import MappingProxyType

ROUTES = MappingProxyType({["not_hashable"]: "import_module"})
globals().get(ROUTES[["not_hashable"]])("unhashable_mapping_key")
"""
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_import_mapping_get_selects_exact_default_importer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
from importlib import import_module

routes = {None: None}
routes.get(False, import_module)("exact_mapping_default_importer")
"""
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["exact_mapping_default_importer"]


_DYNAMIC_MAPPING_LITERAL_CROSSPRODUCT_VALUES: tuple[object, ...] = (
    None,
    False,
    True,
    0,
    1,
    -1,
    0.0,
    -0.0,
    1.0,
    0j,
    1 + 0j,
    "",
    "catalog",
    b"catalog",
    Ellipsis,
    ("catalog", True),
    ("catalog", 1),
    ("catalog", 2),
    ("catalog", 1.0),
    ("other", 1),
)


def test_dynamic_mapping_ast_constants_resolve_subscript_and_get() -> None:
    source = """\
from importlib import import_module

routes = {0: import_module}
routes[False]("polisyos.literal.bool_subscript")
routes.get(False, print)("polisyos.literal.bool_get")

none_routes = {None: import_module}
none_routes[None]("polisyos.literal.none_subscript")
none_routes.get(None, print)("polisyos.literal.none_get")

tuple_routes = {("key", None, False): import_module}
tuple_routes[("key", None, 0)]("polisyos.literal.tuple_alias")

empty_routes = {}
empty_routes.get(False, import_module)("polisyos.literal.bool_default")
empty_routes.get(None, import_module)("polisyos.literal.none_default")
"""
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    entries = scanner.scan(ast.parse(source))

    assert sorted(entry["pattern"] for entry in entries) == [
        "polisyos.literal.bool_default",
        "polisyos.literal.bool_get",
        "polisyos.literal.bool_subscript",
        "polisyos.literal.none_default",
        "polisyos.literal.none_get",
        "polisyos.literal.none_subscript",
        "polisyos.literal.tuple_alias",
    ]


@pytest.mark.parametrize("lookup", ["routes[query]", "routes.get(query, print)"])
def test_dynamic_mapping_lookup_does_not_treat_computed_boolean_as_literal(
    lookup: str,
) -> None:
    source = f"""\
from importlib import import_module

query = isinstance(unresolved_value, int)
routes = {{0: import_module}}
{lookup}("polisyos.literal.computed_boolean")
"""
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=r"ambiguous|unresolved",
    ):
        scanner.scan(ast.parse(source))


def test_dynamic_mapping_lookup_source_literal_crossproduct_matches_python_dict() -> None:
    values = _DYNAMIC_MAPPING_LITERAL_CROSSPRODUCT_VALUES
    source_lines = ["from importlib import import_module"]
    expected_patterns: list[str] = []
    case_index = 0
    for first_value in values:
        for second_value in values:
            for query_value in values:
                first_literal = "..." if first_value is Ellipsis else repr(first_value)
                second_literal = "..." if second_value is Ellipsis else repr(second_value)
                query_literal = "..." if query_value is Ellipsis else repr(query_value)
                target = f"polisyos.literal_crossproduct.case_{case_index}"
                expected = {
                    first_value: "importer",
                    second_value: "ordinary",
                }.get(query_value, "ordinary")
                source_lines.append(
                    f"({{{first_literal}: import_module, {second_literal}: print}})"
                    f".get({query_literal}, print)({target!r})"
                )
                if expected == "importer":
                    expected_patterns.append(target)
                case_index += 1

    source = "\n".join(source_lines)
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    entries = scanner.scan(ast.parse(source))
    observed_patterns = [entry["pattern"] for entry in entries]

    assert case_index == len(values) ** 3
    assert len(observed_patterns) == len(expected_patterns)
    assert set(observed_patterns) == set(expected_patterns)


def test_dynamic_mapping_lookup_exact_literal_crossproduct_matches_python_dict() -> None:
    """Exact literal lookup agrees with Python dict selection across the bounded key domain."""
    literal_values = _DYNAMIC_MAPPING_LITERAL_CROSSPRODUCT_VALUES
    importer = preflight._DynamicImportBinding("callable", "polisyos.demo.importer", guarded=True)
    ordinary = preflight._DynamicImportBinding("callable", "ordinary_loader")
    default = preflight._DynamicImportBinding("callable", "ordinary_default")

    def key_binding(value: object) -> preflight._DynamicImportBinding:
        assert preflight._dynamic_value_is_safe_hashable_literal(value)
        return preflight._DynamicImportBinding("other", literal_key=value, literal_key_known=True)

    comparisons = 0
    for first_value in literal_values:
        for second_value in literal_values:
            for query_value in literal_values:
                source_mapping = preflight._dynamic_mapping_binding(
                    (key_binding(first_value), key_binding(second_value)),
                    (ordinary, importer),
                    guarded=True,
                )
                immutable_mapping = preflight._dynamic_immutable_literal_mapping_binding(
                    source_mapping
                )
                assert immutable_mapping.kind == "mapping"
                expected = {first_value: ordinary, second_value: importer}.get(query_value, default)
                actual = preflight._dynamic_mapping_lookup(
                    immutable_mapping, key_binding(query_value), default=default
                )
                assert actual == expected, (
                    f"source lookup differed from Python dict for {first_value!r}, "
                    f"{second_value!r}, query {query_value!r}: "
                    f"expected {expected.name}, got {actual.name}"
                )
                comparisons += 1
    assert comparisons == len(literal_values) ** 3

    default_importer = preflight._DynamicImportBinding(
        "callable",
        "polisyos.demo.default_importer",
        guarded=True,
    )
    exact_mapping = preflight._dynamic_immutable_literal_mapping_binding(
        preflight._dynamic_mapping_binding(
            (key_binding(None),),
            (ordinary,),
            guarded=True,
        )
    )
    assert (
        preflight._dynamic_mapping_lookup(
            exact_mapping,
            key_binding(False),
            default=default_importer,
        )
        == default_importer
    )

    unknown_key_importer = preflight._DynamicImportBinding(
        "callable",
        "importlib.import_module",
        guarded=True,
    )
    unknown_key_mapping = preflight._dynamic_mapping_binding(
        (preflight._DYNAMIC_UNKNOWN,),
        (unknown_key_importer,),
        guarded=True,
    )
    unknown_key_result = preflight._dynamic_mapping_lookup(
        unknown_key_mapping,
        key_binding("missing"),
        default=default,
    )
    assert preflight._is_unresolved_importer_binding(unknown_key_result)

    abstract_mapping = preflight._dynamic_immutable_literal_mapping_binding(
        preflight._dynamic_mapping_binding(
            (key_binding(None), key_binding(1)),
            (ordinary, importer),
            guarded=True,
        )
    )
    abstract_result = preflight._dynamic_mapping_lookup(
        abstract_mapping, preflight._DYNAMIC_UNKNOWN, default=default
    )
    assert abstract_result.kind == "union"
    assert set(preflight._dynamic_binding_alternatives(abstract_result) or ()) == {
        ordinary,
        importer,
        default,
    }


@pytest.mark.parametrize(
    ("initial_body", "changed_body", "lookup"),
    [
        (
            "1: import_module, None: ordinary_loader,",
            "1: ordinary_loader, None: import_module,",
            "1",
        ),
        (
            "('catalog', 1): import_module, ('catalog', 2): ordinary_loader,",
            "('catalog', 1): ordinary_loader, ('catalog', 2): import_module,",
            "('catalog', 1)",
        ),
    ],
)
def test_dynamic_imports_gate_rejects_stale_registry_after_exact_lookup_changes(
    initial_body: str,
    changed_body: str,
    lookup: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def source_for(mapping_body: str) -> str:
        return (
            "from importlib import import_module\n"
            "from types import MappingProxyType\n\n"
            "def ordinary_loader(name):\n    return name\n\n"
            f"ROUTES = MappingProxyType({{{mapping_body}}})\n"
            f"selected = ROUTES.get({lookup}, ordinary_loader)\n"
            "selected('polisyos.demo.selected')\n"
        )

    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source_for(initial_body))
    source_path = tmp_path / "src" / "dynamic_fixture.py"
    entries = preflight.collect_dynamic_imports()
    assert len(entries) == 1
    assert entries[0]["allowed_targets"] == ["polisyos.demo.selected"]
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path.write_text(source_for(changed_body), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert findings, "a stale registry must fail after the exact selected value changes"


@pytest.mark.parametrize(
    ("mutation_scope", "expected_pattern", "removed_write"),
    [
        (
            "def rebind():\n    global typing_alias\n    typing_alias = RuntimeOn\nrebind()\n",
            "polisyos.fixture_only",
            "    typing_alias = RuntimeOn\n",
        ),
        (
            "class RebindNow: \n    global typing_alias\n    typing_alias = RuntimeOn\n",
            "polisyos.fixture_only",
            "    typing_alias = RuntimeOn\n",
        ),
        (
            "class Deferred: \n    def rebind(self):\n        global typing_alias\n        typing_alias = RuntimeOn\n",
            "polisyos.fixture_only",
            "        typing_alias = RuntimeOn\n",
        ),
        (
            'def outer():\n    local_alias = typing_alias\n    def rebind():\n        nonlocal local_alias\n        local_alias = RuntimeOn\n    rebind()\n    if local_alias.TYPE_CHECKING:\n        from importlib import import_module as nested_loader\n        nested_loader("polisyos.fixture_nested")\nouter()\n',
            "polisyos.fixture_nested",
            "        local_alias = RuntimeOn\n",
        ),
        (
            "def outer():\n    def inner():\n        global typing_alias\n        typing_alias = RuntimeOn\n    inner()\nouter()\n",
            "polisyos.fixture_only",
            "        typing_alias = RuntimeOn\n",
        ),
    ],
    ids=(
        "function-global",
        "class-global",
        "deferred-method-global",
        "closure-nonlocal",
        "nested-deferred-global",
    ),
)
def test_dynamic_import_type_checking_does_not_prune_scope_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_scope: str,
    expected_pattern: str,
    removed_write: str,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "class RuntimeOn:\n    TYPE_CHECKING = True\n"
        "from importlib import import_module as source_loader\n"
        f"{mutation_scope}"
        "if typing_alias.TYPE_CHECKING:\n"
        '    source_loader("polisyos.fixture_only")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    assert any(entry["pattern"] == expected_pattern for entry in entries)
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path = tmp_path / "src" / "dynamic_fixture.py"
    indent = removed_write[: len(removed_write) - len(removed_write.lstrip())]
    source_path.write_text(source.replace(removed_write, f"{indent}pass\n"), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists" for finding in findings
    )


def test_dynamic_import_type_checking_scalar_snapshot_remains_prunable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = """\
import typing as typing_alias
TYPE_ONLY = typing_alias.TYPE_CHECKING
typing_alias.TYPE_CHECKING = True
from importlib import import_module as source_loader
if TYPE_ONLY:
    source_loader("polisyos.snapshot_only")
"""
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_type_checking_imported_value_is_pruned_only_with_source_origin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "from importlib import import_module as loader\n"
        'if TYPE_ONLY:\n    loader("polisyos.type_only")\n',
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_type_checking_lookalike_is_not_pruned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "TYPE_CHECKING = True\n"
        "from importlib import import_module as loader\n"
        'if TYPE_CHECKING:\n    loader("polisyos.runtime_branch")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["polisyos.runtime_branch"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []


@pytest.mark.parametrize(
    ("effect", "expected_pattern"),
    [
        ("typing_alias.TYPE_CHECKING = True\n", "polisyos.fixture_only"),
        (
            "module_alias = typing_alias\nmodule_alias.TYPE_CHECKING = True\n",
            "polisyos.fixture_only",
        ),
        (
            "def mutate(module):\n    module.TYPE_CHECKING = True\nmutate(typing_alias)\n",
            "polisyos.fixture_only",
        ),
        (
            "module_box = [typing_alias]\nmutate(module_box)\n",
            "polisyos.fixture_only",
        ),
        (
            'typing_alias.__dict__["TYPE_CHECKING"] = True\n',
            "polisyos.fixture_only",
        ),
        (
            'globals()["typing_alias"] = RuntimeOn\n',
            "polisyos.fixture_only",
        ),
        (
            'import sys as system\nsystem.modules["typing"].TYPE_CHECKING = True\n',
            "polisyos.fixture_only",
        ),
        (
            'import sys as system\nsystem.modules["typing"] = RuntimeOn\n',
            "polisyos.fixture_only",
        ),
        (
            'import sys as system\nsys_modules = system.modules\nsys_modules["typing"] = RuntimeOn\n',
            "polisyos.fixture_only",
        ),
    ],
    ids=(
        "direct-attribute-write",
        "alias-attribute-write",
        "deferred-mutator",
        "container-escape",
        "module-dict-write",
        "global-namespace-write",
        "sys-modules-attribute-write",
        "sys-modules-rebind",
        "aliased-sys-modules-rebind",
    ),
)
def test_dynamic_import_type_checking_module_effects_are_not_pruned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    effect: str,
    expected_pattern: str,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "from importlib import import_module as source_loader\n"
        f"{effect}"
        "if typing_alias.TYPE_CHECKING:\n"
        '    source_loader("polisyos.fixture_only")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == [expected_pattern]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path = tmp_path / "src" / "dynamic_fixture.py"
    source_path.write_text(source.replace(effect, "", 1), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists" for finding in findings
    )


def test_dynamic_import_type_checking_scalar_reflection_does_not_prune(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "from importlib import import_module as source_loader\n"
        'globals()["TYPE_ONLY"] = True\n'
        "if TYPE_ONLY:\n"
        '    source_loader("polisyos.reflected_binding")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["polisyos.reflected_binding"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path = tmp_path / "src" / "dynamic_fixture.py"
    source_path.write_text(
        source.replace('globals()["TYPE_ONLY"] = True\n', "", 1), encoding="utf-8"
    )
    assert any(
        finding.message == "registered dynamic import call no longer exists"
        for finding in preflight.validate_dynamic_imports()
    )


def test_dynamic_import_type_checking_builtins_namespace_access_does_not_prune(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "from importlib import import_module as source_loader\n"
        '__builtins__["globals"]()["TYPE_ONLY"] = True\n'
        "if TYPE_ONLY:\n"
        '    source_loader("polisyos.builtins_reflection")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["polisyos.builtins_reflection"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_type_checking_reflection_builtin_shadow_is_not_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "def globals():\n    return {}\n"
        "import typing as typing_alias\n"
        "from importlib import import_module as source_loader\n"
        "globals()\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    source_loader("polisyos.type_only")\n'
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, source)

    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    ("mutation", "removed_line"),
    [
        (
            "def rebind():\n    global TYPE_ONLY\n    TYPE_ONLY = RuntimeOn\nrebind()\n",
            "    TYPE_ONLY = RuntimeOn\n",
        ),
        (
            'def outer():\n    local_flag = TYPE_ONLY\n    def rebind():\n        nonlocal local_flag\n        local_flag = RuntimeOn\n    rebind()\n    if local_flag:\n        source_loader("polisyos.closure_scalar")\nouter()\n',
            "        local_flag = RuntimeOn\n",
        ),
    ],
    ids=("global-scalar-write", "nonlocal-scalar-write"),
)
def test_dynamic_import_type_checking_scalar_cross_scope_writes_are_not_pruned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    removed_line: str,
) -> None:
    module = "polisyos.closure_scalar" if "local_flag" in mutation else "polisyos.global_scalar"
    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "class RuntimeOn:\n    TYPE_CHECKING = True\n"
        "from importlib import import_module as source_loader\n"
        f"{mutation}"
    )
    if "local_flag" not in mutation:
        source += f"if TYPE_ONLY:\n    source_loader({module!r})\n"
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == [module]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    source_path = tmp_path / "src" / "dynamic_fixture.py"
    source_path.write_text(source.replace(removed_line, "", 1), encoding="utf-8")
    assert any(
        finding.message == "registered dynamic import call no longer exists"
        for finding in preflight.validate_dynamic_imports()
    )


@pytest.mark.parametrize(
    ("foreign_count", "local_effect_after_guard", "expected_importer"),
    [
        (0, False, False),
        (0, True, False),
        (1, False, True),
        (1, True, True),
        (2, False, True),
        (2, True, True),
    ],
    ids=(
        "no-effects",
        "local-only",
        "foreign-only",
        "local-and-foreign",
        "multiple-foreign",
        "local-and-multiple-foreign",
    ),
)
def test_dynamic_import_type_checking_source_effect_origin_union(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    foreign_count: int,
    local_effect_after_guard: bool,
    expected_importer: bool,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.origin_union")\n'
    )
    if local_effect_after_guard:
        source += "typing_alias.TYPE_CHECKING = True\n"
    _dynamic_import_fixture(tmp_path, monkeypatch, source)
    for index in range(foreign_count):
        (tmp_path / "src" / f"foreign_mutator_{index}.py").write_text(
            "import typing as typing_alias\ntyping_alias.TYPE_CHECKING = True\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    if expected_importer:
        assert [entry["pattern"] for entry in entries] == ["polisyos.origin_union"]
    else:
        assert entries == []


def test_dynamic_import_type_checking_origin_union_removal_keeps_registry_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.origin_union_removal")\n'
        "typing_alias.TYPE_CHECKING = True\n"
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    mutators = [tmp_path / "src" / f"foreign_{index}.py" for index in range(2)]
    for mutator in mutators:
        mutator.write_text(
            "import typing as typing_alias\ntyping_alias.TYPE_CHECKING = True\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["polisyos.origin_union_removal"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    registered_bytes = registry_path.read_bytes()
    assert preflight.validate_dynamic_imports() == []

    mutators[0].write_text("import typing as typing_alias\n", encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []
    assert registry_path.read_bytes() == registered_bytes

    mutators[1].write_text("import typing as typing_alias\n", encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists" for finding in findings
    )
    assert registry_path.read_bytes() == registered_bytes


def test_dynamic_import_type_checking_foreign_first_runtime_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import typing

    mutator_source = "import typing as typing_alias\ntyping_alias.TYPE_CHECKING = True\n"
    consumer_source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.foreign_first_runtime")\n'
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, consumer_source)
    consumer_path = tmp_path / "src" / "dynamic_fixture.py"
    consumer_path.write_text(consumer_source, encoding="utf-8")
    mutator_path = tmp_path / "src" / "foreign_runtime_mutator.py"
    mutator_path.write_text(mutator_source, encoding="utf-8")
    calls: list[str] = []
    with monkeypatch.context() as runtime_patch:
        runtime_patch.setattr(typing, "TYPE_CHECKING", False)
        runtime_patch.setattr(importlib, "import_module", calls.append)
        runpy.run_path(str(mutator_path))
        runpy.run_path(str(consumer_path))
        assert typing.TYPE_CHECKING is True
        assert calls == ["polisyos.foreign_first_runtime"]

    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["polisyos.foreign_first_runtime"]


@pytest.mark.parametrize("module_name", ["typing", "typing_extensions"])
def test_dynamic_import_type_checking_effect_summary_spans_source_set_and_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
) -> None:
    guarded_source = (
        f"import {module_name} as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.cross_module_only")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, guarded_source)
    mutation_path = tmp_path / "src" / "unreachable_mutator.py"
    mutation_path.write_text(
        f"import {module_name} as typing_alias\ntyping_alias.TYPE_CHECKING = True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["polisyos.cross_module_only"]
    # The guard consumer does not import the mutator. The whole selected set
    # deliberately overcounts a possible shared-singleton effect rather than
    # silently assuming that module is unreachable.
    assert "unreachable_mutator" not in guarded_source
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    mutation_path.write_text(f"import {module_name} as typing_alias\n", encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "registered dynamic import call no longer exists" for finding in findings
    )


def test_dynamic_import_type_checking_complete_source_set_without_effect_still_prunes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from typing import TYPE_CHECKING as TYPE_ONLY\n"
        "from importlib import import_module as loader\n"
        'if TYPE_ONLY:\n    loader("polisyos.type_only_sibling")\n'
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    (tmp_path / "src" / "unrelated.py").write_text(
        "from typing import TYPE_CHECKING as TYPE_ONLY\nSNAPSHOT = TYPE_ONLY\n",
        encoding="utf-8",
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_type_checking_without_complete_source_context_does_not_prune(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.context_missing")\n'
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, source)
    source_path = tmp_path / "src" / "dynamic_fixture.py"
    scanner = preflight._DynamicImportSourceScanner(source_path)

    entries = scanner.scan(preflight.ast.parse(source, filename=str(source_path)))

    assert [entry["pattern"] for entry in entries] == ["polisyos.context_missing"]


def test_dynamic_import_postponed_annotations_allow_lazy_type_resolution_and_removal_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from __future__ import annotations\n"
        "from polisyos.lazy_types import TypeRef\n"
        "import importlib\n"
        "def accepts(value: TypeRef) -> TypeRef:\n"
        "    return value\n"
        "def reflected() -> importlib.import_module('json'):\n"
        "    return None\n"
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    package_path = tmp_path / "src" / "polisyos"
    package_path.mkdir()
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "lazy_types.py").write_text(
        "def _make_type(name):\n"
        "    return type(name, (), {})\n\n"
        "def __getattr__(name):\n"
        "    return _make_type(name)\n",
        encoding="utf-8",
    )
    source_path = tmp_path / "src" / "dynamic_fixture.py"

    entries = preflight.collect_dynamic_imports()

    assert [entry["pattern"] for entry in entries] == ["json"]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    import importlib
    import sys
    import typing

    import_calls: list[str] = []
    original_import_module = importlib.import_module

    def record_import_module(name: str, package: str | None = None) -> object:
        if name == "json":
            import_calls.append(name)
        return original_import_module(name, package)

    with monkeypatch.context() as isolated_imports:
        for module_name in tuple(sys.modules):
            if module_name == "polisyos" or module_name.startswith("polisyos."):
                isolated_imports.delitem(sys.modules, module_name, raising=False)
        isolated_imports.syspath_prepend(str(tmp_path / "src"))
        isolated_imports.setattr(importlib, "import_module", record_import_module)
        namespace = runpy.run_path(str(source_path))
        assert import_calls == []
        resolved_hints = typing.get_type_hints(namespace["accepts"])
        assert resolved_hints == {"value": namespace["TypeRef"], "return": namespace["TypeRef"]}
        reflected_hints = typing.get_type_hints(namespace["reflected"])
        assert reflected_hints["return"].__name__ == "json"
        assert import_calls == ["json"]

    registered_bytes = registry_path.read_bytes()
    source_path.write_text(
        source.replace("from __future__ import annotations\n", "", 1), encoding="utf-8"
    )
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "guarded importer value escapes through a function annotation" in finding.detail
        for finding in findings
    )
    assert registry_path.read_bytes() == registered_bytes


def test_dynamic_import_postponed_annotated_assignment_preserves_fail_closed_control(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from __future__ import annotations\n"
        "from polisyos.lazy_types import TypeRef\n"
        "annotated_value: TypeRef\n"
    )
    registry_path = _dynamic_import_fixture(tmp_path, monkeypatch, source)
    package_path = tmp_path / "src" / "polisyos"
    package_path.mkdir()
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "lazy_types.py").write_text(
        "def __getattr__(name):\n    return type(name, (), {})\n",
        encoding="utf-8",
    )
    source_path = tmp_path / "src" / "dynamic_fixture.py"

    entries = preflight.collect_dynamic_imports()
    assert entries == []
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    assert preflight.validate_dynamic_imports() == []

    registered_bytes = registry_path.read_bytes()
    source_path.write_text(
        source.replace("from __future__ import annotations\n", "", 1), encoding="utf-8"
    )
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "guarded importer value escapes through an annotation" in finding.detail
        for finding in findings
    )
    assert registry_path.read_bytes() == registered_bytes


def test_dynamic_import_source_bindings_map_every_curated_lazy_facade_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_path = REPO_ROOT / "src" / "polisyos" / "ir" / "api.py"
    api_tree = ast.parse(api_path.read_text(encoding="utf-8"), filename=str(api_path))
    package_assignment = next(
        node
        for node in api_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "PACKAGE_FACADE_EXPORTS"
    )
    assert isinstance(package_assignment.value, ast.Dict)
    facade_maps = {
        key.value: value.id
        for key, value in zip(
            package_assignment.value.keys,
            package_assignment.value.values,
            strict=True,
        )
        if isinstance(key, ast.Constant)
        and isinstance(key.value, str)
        and isinstance(value, ast.Name)
    }
    assert facade_maps
    source_paths = preflight._dynamic_source_paths("src")
    source_bindings = preflight._DynamicImportSourceBindings(source_paths)
    constructed_targets: list[tuple[str, str, str]] = []

    for package, map_name in facade_maps.items():
        assignment = next(
            node
            for node in api_tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == map_name
        )
        exports = ast.literal_eval(assignment.value)
        facade_module = f"polisyos.ir.{package}"
        for name, (target_module, target_symbol) in exports.items():
            facade_binding = source_bindings.import_binding(
                facade_module,
                name,
                current_module=facade_module,
                is_package=True,
            )
            target_binding = source_bindings.import_binding(
                target_module,
                target_symbol,
                current_module=facade_module,
                is_package=True,
            )
            assert facade_binding == target_binding, f"{facade_module}.{name}"
            target_tree = source_bindings._module_tree(target_module)
            target_environment = source_bindings._module_environment(target_module, ())
            target_assignment = None
            if target_tree is not None and target_environment is not None:
                target_assignment = next(
                    (
                        statement
                        for statement in target_tree.body
                        if isinstance(statement, ast.Assign | ast.AnnAssign)
                        and target_symbol
                        in source_bindings._simple_target_names(
                            statement.targets[0]
                            if isinstance(statement, ast.Assign)
                            else statement.target
                        )
                    ),
                    None,
                )
            if target_assignment is not None and isinstance(target_assignment.value, ast.Call):
                assert target_environment is not None
                constructor = source_bindings._expression_binding(
                    target_assignment.value.func,
                    target_environment,
                    target_module,
                    (),
                )
                if (
                    constructor.origin_name is not None
                    and source_bindings._source_class_definition(
                        constructor.origin_name,
                        current_module=target_module,
                        current_environment=target_environment,
                        stack=(),
                    )
                    is not None
                ):
                    assert target_binding.kind == "object", f"{target_module}.{target_symbol}"
                    assert target_binding.origin_name == constructor.origin_name
                    constructed_targets.append(
                        (target_module, target_symbol, constructor.origin_name)
                    )

    assert len(constructed_targets) == 8

    import importlib
    import sys

    with monkeypatch.context() as isolated_imports:
        for module_name in tuple(sys.modules):
            if module_name == "polisyos" or module_name.startswith("polisyos."):
                isolated_imports.delitem(sys.modules, module_name, raising=False)
        isolated_imports.syspath_prepend(str(REPO_ROOT / "src"))
        facade_module = importlib.import_module("polisyos.ir.analytics")
        registry_refs = importlib.import_module("polisyos.ir.registry.refs")
        assert facade_module.ExplanationBundleRef is registry_refs.ExplanationBundleRef


def test_dynamic_import_source_bindings_keep_lazy_facade_importers_guarded() -> None:
    import copy

    source_paths = preflight._dynamic_source_paths("src")
    source_bindings = preflight._DynamicImportSourceBindings(source_paths)
    api_tree = source_bindings._module_tree("polisyos.ir.api")
    assert api_tree is not None
    api_tree = copy.deepcopy(api_tree)
    assignment = next(
        node
        for node in api_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ANALYTICS_FACADE_EXPORTS"
    )
    assert isinstance(assignment.value, ast.Dict)
    name = "ExplanationBundleRef"
    index = next(
        index
        for index, key in enumerate(assignment.value.keys)
        if isinstance(key, ast.Constant) and key.value == name
    )
    assignment.value.values[index] = ast.Tuple(
        elts=[ast.Constant("importlib"), ast.Constant("import_module")],
        ctx=ast.Load(),
    )
    ast.fix_missing_locations(api_tree)
    source_bindings.trees["polisyos.ir.api"] = api_tree
    source_bindings.environments.clear()

    imported = source_bindings.import_binding(
        "polisyos.ir.analytics",
        name,
        current_module="polisyos.ir.analytics",
        is_package=True,
    )
    assert imported.kind == "callable"
    assert imported.name == "importlib.import_module"
    assert imported.guarded

    rebound_bindings = preflight._DynamicImportSourceBindings(source_paths)
    rebound_api_tree = rebound_bindings._module_tree("polisyos.ir.api")
    assert rebound_api_tree is not None
    rebound_api_tree = copy.deepcopy(rebound_api_tree)
    resolver = next(
        node
        for node in rebound_api_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_lazy_export"
    )
    resolver.body[-1] = ast.Return(value=ast.Name(id="name", ctx=ast.Load()))
    ast.fix_missing_locations(rebound_api_tree)
    rebound_bindings.trees["polisyos.ir.api"] = rebound_api_tree
    rebound_bindings.environments.clear()

    unresolved = rebound_bindings.import_binding(
        "polisyos.ir.analytics",
        name,
        current_module="polisyos.ir.analytics",
        is_package=True,
    )
    assert unresolved.kind == "ambiguous"
    assert unresolved.guarded


def test_dynamic_import_postponed_annotation_shadow_does_not_disable_runtime_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "from polisyos.lazy_types import TypeRef\n"
        "TypeRef = object\n"
        "def accepts(value: TypeRef) -> TypeRef:\n"
        "    return value\n"
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, source)
    package_path = tmp_path / "src" / "polisyos"
    package_path.mkdir()
    (package_path / "__init__.py").write_text("", encoding="utf-8")
    (package_path / "lazy_types.py").write_text(
        "def __getattr__(name):\n    return type(name, (), {})\n",
        encoding="utf-8",
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_type_checking_source_effect_keeps_ordinary_if_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if False:\n"
        '    importlib_alias.import_module("polisyos.literal_false_only")\n'
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, source)
    (tmp_path / "src" / "unrelated_mutator.py").write_text(
        "import typing as typing_alias\ntyping_alias.TYPE_CHECKING = True\n",
        encoding="utf-8",
    )

    assert [entry["pattern"] for entry in preflight.collect_dynamic_imports()] == [
        "polisyos.literal_false_only"
    ]


@pytest.mark.parametrize(
    ("store_kind", "source_store"),
    [
        ("setdefault", 'registry.setdefault("Carrier", SourceClass)'),
        ("subscript", 'registry["Carrier"] = SourceClass'),
    ],
)
def test_dynamic_import_source_class_identity_escape_to_mutable_mapping_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    store_kind: str,
    source_store: str,
) -> None:
    from importlib import import_module

    from pydantic import BaseModel

    class RuntimeCarrier(BaseModel):
        loader: object
        spare: object

    def replacement(self, name):
        if name == "loader":
            return object.__getattribute__(self, "spare")
        return object.__getattribute__(self, name)

    runtime_registry = {}
    if store_kind == "setdefault":
        runtime_registry.setdefault("Carrier", RuntimeCarrier)
    else:
        runtime_registry["Carrier"] = RuntimeCarrier
    runtime_registry["Carrier"].__getattribute__ = replacement
    runtime_carrier = RuntimeCarrier(loader="safe", spare=import_module)
    assert runtime_carrier.loader is import_module

    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.a_consumer": (
                "from importlib import import_module\n"
                "from polisyos.z_model import Carrier\n\n"
                'carrier = Carrier(loader="safe", spare=import_module)\n'
                'carrier.loader("class_identity_escape_hidden_import")\n'
            ),
            "polisyos.z_model": (
                "from pydantic import BaseModel\n\n"
                "class Carrier(BaseModel):\n"
                "    loader: object\n"
                "    spare: object\n"
            ),
            "polisyos.zz_effect": (
                "from polisyos.z_model import Carrier as SourceClass\n"
                "registry = {}\n"
                + source_store
                + "\n\n"
                + "def replacement(self, name):\n"
                + '    if name == "loader":\n'
                + '        return object.__getattribute__(self, "spare")\n'
                + "    return object.__getattribute__(self, name)\n\n"
                + 'setattr(registry["Carrier"], "__getattribute__", replacement)\n'
            ),
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    findings = preflight.validate_dynamic_imports()

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "guarded importer value escapes through a call argument" in finding.detail
        for finding in findings
    ), findings


def test_dynamic_import_typed_path_argparse_and_source_method_transfers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.storage": """from pathlib import Path

class FileSystemCAS:
    def _sig_path(self, artifact_id: object) -> Path:
        return Path("/tmp")
""",
            "polisyos.fixture_target": "class FixtureTarget: pass\n",
            "polisyos.consumer": """import argparse
import tempfile
from importlib import import_module
from pathlib import Path
from polisyos.storage import FileSystemCAS

parser = argparse.ArgumentParser()
parser.add_argument("--fixture-root", type=Path, required=True)
parser.add_argument("--port", type=int, default=8017)
args = parser.parse_args()
root = args.fixture_root.resolve().parents[0]
station = Path(tempfile.mkdtemp(dir=root))
signature_path = FileSystemCAS(root)._sig_path(object())
original_mode = signature_path.stat().st_mode & 0o777
signature_path.chmod(original_mode)
runtime_url = f"http://127.0.0.1:{args.port}/fixture"
trace_label = f"selected:{import_module('polisyos.fixture_target').__name__}"
import_module("polisyos.fixture_target")
""",
        },
    )

    entries = preflight.collect_dynamic_imports()

    assert [(entry["call"], entry["pattern"]) for entry in entries] == [
        ("importlib.import_module", "polisyos.fixture_target"),
        ("importlib.import_module", "polisyos.fixture_target"),
    ]
    registry_path.write_text(_render_dynamic_imports_toml(entries), encoding="utf-8")
    monkeypatch.setattr(preflight.importlib.util, "find_spec", lambda _module: object())
    assert preflight.validate_dynamic_imports() == []


@pytest.mark.parametrize(
    ("return_expression", "imports", "escape_boundary"),
    [
        ("import_module", "from importlib import import_module\n", "function return"),
        (
            "cast(Path, import_module)",
            "from importlib import import_module\nfrom typing import cast\n",
            "call argument",
        ),
    ],
)
def test_dynamic_import_path_annotation_cannot_hide_importer_return_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    return_expression: str,
    imports: str,
    escape_boundary: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.storage": (
                imports
                + "from pathlib import Path\n\n"
                + "class MisleadingPathFactory:\n"
                + "    def path(self) -> Path:\n"
                + f"        return {return_expression}\n"
            ),
            "polisyos.consumer": (
                "from polisyos.storage import MisleadingPathFactory\n\n"
                "path_value = MisleadingPathFactory().path()\n"
                'path_value("polisyos.dynamic_importer_hidden_by_path_annotation")\n'
            ),
            "polisyos.target": "class Target: pass\n",
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=f"guarded importer value escapes through a {escape_boundary}",
    ):
        preflight.collect_dynamic_imports()


def test_dynamic_import_annotated_method_does_not_ground_external_factory_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.storage": """from pathlib import Path
from opaque_vendor.factory import make_value

class PathLookingFactory:
    def path(self) -> Path:
        return make_value()
""",
            "polisyos.consumer": """from polisyos.storage import PathLookingFactory

path_value = PathLookingFactory().path()
imported_target = path_value("polisyos.hidden_target").__name__
""",
            "polisyos.hidden_target": "class HiddenTarget: pass\n",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    (tmp_path / "src/polisyos/__init__.py").write_text("", encoding="utf-8")

    external_root = tmp_path / "deps"
    (external_root / "opaque_vendor").mkdir(parents=True)
    (external_root / "opaque_vendor/__init__.py").write_text("", encoding="utf-8")
    external_module = external_root / "opaque_vendor" / "factory.py"
    external_module.write_text(
        "from importlib import import_module\n\ndef make_value():\n    return import_module\n",
        encoding="utf-8",
    )
    selected_paths = set(preflight._dynamic_source_paths("src", "tools", "apps", "packages"))
    assert external_module not in selected_paths

    previous_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "polisyos" or name.startswith("polisyos.")
    }
    for name in previous_modules:
        del sys.modules[name]
    try:
        monkeypatch.syspath_prepend(str(external_root))
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        preflight.importlib.invalidate_caches()
        runtime_namespace = runpy.run_path(str(tmp_path / "src/polisyos/consumer.py"))
    finally:
        for name in tuple(sys.modules):
            if name == "polisyos" or name.startswith("polisyos."):
                del sys.modules[name]
        sys.modules.update(previous_modules)
    assert runtime_namespace["imported_target"] == "polisyos.hidden_target"

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()

    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
        for finding in findings
    ), findings


def test_dynamic_import_source_method_transfers_use_body_proven_path_stat_and_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.storage": """import argparse
import os
from pathlib import Path

class SourceReader:
    def path(self) -> Path:
        return Path("/tmp")

    def stat(self) -> os.stat_result:
        return Path("/tmp").stat()

    def namespace(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        parser.add_argument("--module")
        return parser.parse_args()
""",
            "polisyos.consumer": """from importlib import import_module
from polisyos.storage import SourceReader

reader = SourceReader()
path = reader.path()
mode = reader.stat().st_mode & 0o777
options = reader.namespace()
import_module(options.module)
""",
        },
    )

    entries = preflight.collect_dynamic_imports()

    assert [(entry["pattern"], entry["allowed_targets"]) for entry in entries] == [
        ("options.module", [])
    ]
