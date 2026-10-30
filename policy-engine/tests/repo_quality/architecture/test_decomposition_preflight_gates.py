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


def test_dynamic_import_rejects_called_source_helper_rebinding_pep562_hook(
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

def install_hook():
    namespace = globals()
    namespace["__getattr__"] = replace_hook(__getattr__)

install_hook_alias = install_hook
install_hook_alias()
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
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "ambiguous or unresolved" in finding.detail
        for finding in findings
    )

    facade_path = tmp_path / "src/polisyos/probe/facade.py"
    consumer_path = tmp_path / "src/polisyos/probe/consumer.py"
    facade_source = facade_path.read_text(encoding="utf-8")
    consumer_source = consumer_path.read_text(encoding="utf-8")
    assert 'namespace["__getattr__"] = replace_hook(__getattr__)' in facade_source
    assert 'loader("json")' in consumer_source
    facade_path.write_text(
        facade_source.replace(
            'namespace["__getattr__"] = replace_hook(__getattr__)',
            "replace_hook(__getattr__)",
        ),
        encoding="utf-8",
    )
    assert "replace_hook(__getattr__)" in facade_path.read_text(encoding="utf-8")
    assert 'loader("json")' in consumer_path.read_text(encoding="utf-8")
    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def test_dynamic_import_ignores_uncalled_pep562_hook_mutator_and_safe_module_calls(
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

def install_hook():
    namespace = globals()
    namespace["__getattr__"] = replace_hook(__getattr__)

def safe_helper():
    return None

class Safe:
    pass

safe_helper()
Safe()
""",
            "polisyos.probe.consumer": """from .facade import loader

loader("json")
""",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

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


_UNSUPPORTED_SUBSCRIPT_SOURCE = (
    "import importlib\n"
    "unknown_index = len(())\n"
    "loader = (importlib,)[unknown_index].import_module\n"
    "loader('unsupported_subscript_origin')\n"
)


def test_dynamic_import_validator_refuses_guarded_value_through_unsupported_expression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = _dynamic_import_validator_refusal(
        _UNSUPPORTED_SUBSCRIPT_SOURCE,
        tmp_path,
        monkeypatch,
    )

    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
        for finding in findings
    )


def test_dynamic_import_exact_subscript_is_inventoried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A known tuple index uses the existing exact-selection transfer."""
    registry = _dynamic_import_fixture(
        tmp_path,
        monkeypatch,
        "import importlib\n"
        "loader = (importlib,)[0].import_module\n"
        "loader('unsupported_subscript_origin')\n",
    )
    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["unsupported_subscript_origin"]
    registry.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    assert any(
        finding.message == "dynamic import call is not registered"
        and "unsupported_subscript_origin" in finding.detail
        for finding in preflight.validate_dynamic_imports()
    )


def test_dynamic_import_unsupported_subscript_fixture_reaches_real_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unresolved-index fixture reaches an actual controlled import."""
    name = "unsupported_subscript_origin"
    module_path = tmp_path / f"{name}.py"
    module_path.write_text("fixture_executed = True\n", encoding="utf-8")
    fixture = tmp_path / "unsupported_fixture.py"
    fixture.write_text(_UNSUPPORTED_SUBSCRIPT_SOURCE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, name, raising=False)
    try:
        namespace = runpy.run_path(str(fixture))
        module = sys.modules[name]
        assert module.__spec__ is not None
        assert module.__spec__.origin == str(module_path)
        assert module.fixture_executed is True
        assert namespace["unknown_index"] == 0
    finally:
        sys.modules.pop(name, None)


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


def test_dynamic_import_deferred_summary_resolves_actual_template_source_functions() -> None:
    source_paths = preflight._dynamic_source_paths("src")
    selected_modules = {
        "polisyos.common.canonical",
        "polisyos.common.canonical_profile",
        "polisyos.common.hashing",
        "polisyos.common.serialization",
        "polisyos.common.serialization._strict_json",
        "polisyos.core.audit.standalone_verifier_template",
        "polisyos.core.canon",
        "polisyos.core.canon.canon_json",
        "polisyos.core.canon.hashing",
    }
    selected_paths = [
        path for path in source_paths if preflight.module_fqn_from_path(path) in selected_modules
    ]
    assert {preflight.module_fqn_from_path(path) for path in selected_paths} == selected_modules
    source_context = preflight._dynamic_read_source_context(selected_paths)
    source_bindings = preflight._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    module = "polisyos.core.audit.standalone_verifier_template"
    member = next(
        candidate
        for candidate in source_context.members
        if preflight.module_fqn_from_path(candidate.path) == module
    )
    scanner = preflight._DynamicImportSourceScanner(
        member.path,
        relative_path=member.relative_path,
        source_bindings=source_bindings,
        source_context=source_context,
    )
    scanner.scan(member.tree)
    streaming_hash = scanner._module_environment["streaming_hash"]
    assert streaming_hash.kind == "union"
    assert streaming_hash.items is not None
    assert {item.kind for item in streaming_hash.items} == {"other", "source_function"}


def test_dynamic_import_source_bindings_resolve_berl_lazy_facade_reference() -> None:
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))
    reference = source_bindings.import_binding(
        "polisyos.ir.analytics",
        "ExplanationBundleRef",
        current_module="polisyos.berl.persistence",
    )
    assert reference.kind == "other"
    assert reference.origin_name == "polisyos.ir.registry.refs.ExplanationBundleRef"
    assert not reference.guarded

    module = "polisyos.berl.persistence"
    path = source_bindings.module_paths[module]
    tree = source_bindings._module_tree(module)
    assert tree is not None
    scanner = preflight._DynamicImportSourceScanner(
        path,
        relative_path="src/polisyos/berl/persistence.py",
        source_bindings=source_bindings,
    )
    scanner.scan(tree)
    resolved = scanner._module_environment["ExplanationBundleRef"]
    assert resolved.origin_name == "polisyos.ir.registry.refs.ExplanationBundleRef"
    assert not resolved.guarded


def test_dynamic_import_lazy_export_resolver_requires_source_owned_map() -> None:
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))
    module = "polisyos.ir.analytics"
    tree = source_bindings._module_tree(module)
    environment = source_bindings._module_environment(module, ())
    assert tree is not None
    assert environment is not None
    hook = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__"
    )
    call = next(
        node
        for node in ast.walk(hook)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve_lazy_export"
    )
    callee = source_bindings._expression_binding(
        call.func,
        environment,
        module,
        (),
    )
    assert (
        source_bindings._lazy_export_call_contract(
            call,
            environment,
            module,
            (),
            callee=callee,
        )
        is not None
    )

    import copy

    unowned_call = copy.deepcopy(call)
    exports_keyword = next(keyword for keyword in unowned_call.keywords if keyword.arg == "exports")
    exports_keyword.value = ast.Name(id="unowned_exports", ctx=ast.Load())
    assert (
        source_bindings._lazy_export_call_contract(
            unowned_call,
            environment,
            module,
            (),
            callee=callee,
        )
        is None
    )


@pytest.mark.parametrize(
    "source_effect",
    ["subscript-write", "mutable-method", "opaque-exposure"],
)
def test_dynamic_import_lazy_export_map_requires_source_proven_read_only_effects(
    source_effect: str,
) -> None:
    import copy

    source_paths = preflight._dynamic_source_paths("src")
    source_bindings = preflight._DynamicImportSourceBindings(source_paths)
    module = "polisyos.ir.api"
    tree = source_bindings._module_tree(module)
    assert tree is not None
    tree = copy.deepcopy(tree)
    map_name = "ANALYTICS_FACADE_EXPORTS"
    assignment_index = next(
        index
        for index, statement in enumerate(tree.body)
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == map_name
    )
    map_name_node = ast.Name(id=map_name, ctx=ast.Load())
    if source_effect == "subscript-write":
        effect: ast.stmt = ast.Assign(
            targets=[
                ast.Subscript(
                    value=map_name_node,
                    slice=ast.Constant("ExplanationBundleRef"),
                    ctx=ast.Store(),
                )
            ],
            value=ast.Tuple(
                elts=[ast.Constant("importlib"), ast.Constant("import_module")],
                ctx=ast.Load(),
            ),
        )
    elif source_effect == "mutable-method":
        effect = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(value=map_name_node, attr="update", ctx=ast.Load()),
                args=[
                    ast.Dict(
                        keys=[ast.Constant("ExplanationBundleRef")],
                        values=[
                            ast.Tuple(
                                elts=[ast.Constant("importlib"), ast.Constant("import_module")],
                                ctx=ast.Load(),
                            )
                        ],
                    )
                ],
                keywords=[],
            )
        )
    else:
        effect = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="opaque_map_consumer", ctx=ast.Load()),
                args=[map_name_node],
                keywords=[],
            )
        )
    tree.body.insert(assignment_index + 1, effect)
    ast.fix_missing_locations(tree)
    source_bindings.trees[module] = tree
    source_bindings.environments.clear()
    source_bindings._module_execution_snapshots.clear()

    result = source_bindings.import_binding(
        "polisyos.ir.analytics",
        "ExplanationBundleRef",
        current_module="polisyos.ir.analytics",
        is_package=True,
    )
    assert result.kind == "ambiguous"
    assert result.guarded


@pytest.mark.parametrize(
    "source_effect",
    [
        "opaque-module-attribute",
        "opaque-from-import",
        "opaque-nested-list-dict",
        "subscript-assignment",
        "subscript-augmented-assignment",
        "subscript-delete",
        "subscript-annotated-assignment",
        "for-target",
        "with-target",
        "comprehension-target",
        "tuple-target",
        "list-target",
        "starred-target",
        "named-expression-name-rebind",
        "mapping-inplace-merge",
    ],
    ids=(
        "opaque-module-attribute",
        "opaque-from-import",
        "opaque-nested-list-dict",
        "subscript-assignment",
        "subscript-augmented-assignment",
        "subscript-delete",
        "subscript-annotated-assignment",
        "for-target",
        "with-target",
        "comprehension-target",
        "tuple-target",
        "list-target",
        "starred-target",
        "named-expression-name-rebind",
        "mapping-inplace-merge",
    ),
)
@pytest.mark.parametrize(
    "owner_map_resolved_first",
    [True, False],
    ids=("owner-map-resolved-before-sibling-effect", "sibling-effect-before-owner-map-resolution"),
)
def test_dynamic_import_lazy_export_map_tracks_selected_sibling_effects(
    source_effect: str,
    owner_map_resolved_first: bool,
) -> None:
    import copy
    from dataclasses import replace

    source_modules = {
        "polisyos.ir.api",
        "polisyos.ir.analytics",
        "polisyos.ir.registry",
        "polisyos.ir.registry.refs",
    }
    selected_paths = [
        path
        for path in preflight._dynamic_source_paths("src")
        if preflight.module_fqn_from_path(path) in source_modules
    ]
    assert {preflight.module_fqn_from_path(path) for path in selected_paths} == source_modules
    source_context = preflight._dynamic_read_source_context(selected_paths)
    source_bindings = preflight._DynamicImportSourceBindings(
        selected_paths,
        source_context=source_context,
    )

    api_module = "polisyos.ir.api"
    consumer_module = "polisyos.ir.registry"
    api_tree = source_bindings._module_tree(api_module)
    consumer_tree = source_bindings._module_tree(consumer_module)
    assert api_tree is not None
    assert consumer_tree is not None
    consumer_tree = copy.deepcopy(consumer_tree)
    insert_at = (
        1
        if consumer_tree.body
        and isinstance(consumer_tree.body[0], ast.Expr)
        and isinstance(consumer_tree.body[0].value, ast.Constant)
        and isinstance(consumer_tree.body[0].value.value, str)
        else 0
    )
    while (
        insert_at < len(consumer_tree.body)
        and isinstance(consumer_tree.body[insert_at], ast.ImportFrom)
        and consumer_tree.body[insert_at].module == "__future__"
    ):
        insert_at += 1
    consumer_tree.body[insert_at:insert_at] = [
        ast.Import(names=[ast.alias(name=api_module, asname="api")]),
        ast.Assign(
            targets=[ast.Name(id="exports", ctx=ast.Store())],
            value=ast.Attribute(
                value=ast.Name(id="api", ctx=ast.Load()),
                attr="ANALYTICS_FACADE_EXPORTS",
                ctx=ast.Load(),
            ),
        ),
        ast.ImportFrom(
            module=api_module,
            names=[ast.alias(name="ANALYTICS_FACADE_EXPORTS", asname="imported_exports")],
            level=0,
        ),
        ast.Assign(
            targets=[ast.Name(id="alias", ctx=ast.Store())],
            value=ast.Name(id="exports", ctx=ast.Load()),
        ),
    ]
    source_effects = {
        "opaque-module-attribute": "opaque_map_consumer(alias)",
        "opaque-from-import": "opaque_map_consumer(imported_exports)",
        "opaque-nested-list-dict": "opaque_map_consumer([{'nested': alias}])",
        "subscript-assignment": "alias['Probe'] = ('importlib', 'import_module')",
        "subscript-augmented-assignment": "alias['Probe'] += ('importlib', 'import_module')",
        "subscript-delete": "del alias['Probe']",
        "subscript-annotated-assignment": (
            "alias['Probe']: tuple[str, str] = ('importlib', 'import_module')"
        ),
        "for-target": "for alias['Probe'] in (('importlib', 'import_module'),):\n    pass",
        "with-target": "with opaque_context() as alias['Probe']:\n    pass",
        "comprehension-target": (
            "[(item) for alias['Probe'] in (('importlib', 'import_module'),)]"
        ),
        "tuple-target": "(alias['Probe'], unused) = (('importlib', 'import_module'), None)",
        "list-target": "[alias['Probe'], unused] = [('importlib', 'import_module'), None]",
        "starred-target": "*alias['Probe'], = [('importlib', 'import_module')]",
        "named-expression-name-rebind": "result = (alias := {})",
        "mapping-inplace-merge": "alias |= {'Probe': ('importlib', 'import_module')}",
    }
    consumer_tree.body[insert_at + 4 : insert_at + 4] = ast.parse(
        source_effects[source_effect]
    ).body
    ast.fix_missing_locations(consumer_tree)

    if owner_map_resolved_first:
        clean_map = source_bindings.import_binding(api_module, "ANALYTICS_FACADE_EXPORTS")
        assert clean_map.kind == "mapping"
        assert source_bindings._source_literal_mapping_is_current(clean_map)
        clean_target = source_bindings.import_binding(
            "polisyos.ir.analytics",
            "ExplanationBundleRef",
        )
        assert clean_target.kind == "other"
        assert not clean_target.guarded

    scan_order = (
        ((api_module, api_tree), (consumer_module, consumer_tree))
        if owner_map_resolved_first
        else ((consumer_module, consumer_tree), (api_module, api_tree))
    )
    for module, tree in scan_order:
        path = source_bindings.module_paths[module]
        scanner = preflight._DynamicImportSourceScanner(
            path,
            relative_path=preflight._dynamic_source_label(path),
            source_bindings=source_bindings,
            source_context=source_context,
        )
        scanner.scan(tree)

    map_identity = f"{api_module}.ANALYTICS_FACADE_EXPORTS"
    if source_effect == "named-expression-name-rebind":
        assert map_identity not in source_bindings._source_mapping_effects
        complete_context = replace(
            source_context,
            source_mapping_effects=frozenset(source_bindings._source_mapping_effects),
        )
        complete_bindings = preflight._DynamicImportSourceBindings(
            selected_paths,
            source_context=complete_context,
        )
        preserved_map = complete_bindings.import_binding(api_module, "ANALYTICS_FACADE_EXPORTS")
        assert preserved_map.kind == "mapping"
        assert complete_bindings._source_literal_mapping_is_current(preserved_map)
        unchanged_target = complete_bindings.import_binding(
            "polisyos.ir.analytics", "ExplanationBundleRef"
        )
        assert unchanged_target.kind == "other"
        assert not unchanged_target.guarded
        return
    assert map_identity in source_bindings._source_mapping_effects
    complete_context = replace(
        source_context,
        source_mapping_effects=frozenset(source_bindings._source_mapping_effects),
    )
    complete_bindings = preflight._DynamicImportSourceBindings(
        selected_paths,
        source_context=complete_context,
    )
    refused = complete_bindings.import_binding(
        "polisyos.ir.analytics",
        "ExplanationBundleRef",
    )
    assert refused.kind == "ambiguous"
    assert refused.guarded


@pytest.mark.parametrize(
    "mutator_module",
    ["a_mutator", "z_mutator"],
    ids=("sibling-before-owner-module", "sibling-after-owner-module"),
)
def test_dynamic_import_collector_refuses_selected_sibling_map_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator_module: str,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.catalog.__init__": "",
            "polisyos.catalog.contracts": """ROUTE_TABLE = {
    ("catalog", "loader"): ("importlib", "import_module"),
}
""",
            f"polisyos.catalog.{mutator_module}": (
                "from .contracts import ROUTE_TABLE\n"
                'ROUTE_TABLE[("catalog", "probe")] = '
                '("polisyos.catalog", "public_builder")\n'
            ),
            "polisyos.catalog.route_consumer": _dynamic_import_internal_map_consumer(
                "from .contracts import ROUTE_TABLE as ROUTE_TABLE"
            ),
        },
    )

    with pytest.raises(preflight.DynamicImportCollectionError) as error:
        preflight.collect_dynamic_imports()

    assert "ambiguous" in str(error.value) or "unresolved" in str(error.value)


@pytest.mark.parametrize(
    ("mutator_module", "nested_map_escape"),
    [
        ("a_mutator", True),
        ("z_mutator", True),
        ("a_mutator", False),
    ],
    ids=(
        "nested-map-before-owner-resolution",
        "nested-map-after-owner-resolution",
        "unrelated-scalar-control",
    ),
)
def test_dynamic_import_collector_tracks_nested_selected_map_opaque_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator_module: str,
    nested_map_escape: bool,
) -> None:
    mutation_argument = (
        "[{'nested': ANALYTICS_FACADE_EXPORTS}]" if nested_map_escape else "'unrelated scalar'"
    )
    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        f"polisyos.ir.{mutator_module}": (
            f"from .api import ANALYTICS_FACADE_EXPORTS\nopaque_map_consumer({mutation_argument})\n"
        ),
        "polisyos.ir.consumer": """from polisyos.ir.analytics import load

load("polisyos.nested_map_hidden_import")
""",
        "polisyos.nested_map_hidden_import": "VALUE = 1\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    if nested_map_escape:
        with pytest.raises(preflight.DynamicImportCollectionError):
            preflight.collect_dynamic_imports()
    else:
        entries = preflight.collect_dynamic_imports()
        assert "polisyos.nested_map_hidden_import" in [entry["pattern"] for entry in entries]


@pytest.mark.parametrize(
    "transfer",
    ["setdefault", "update", "subscript-store", "attribute-store", "list-append", "list-extend"],
    ids=(
        "mapping-setdefault",
        "mapping-update",
        "subscript-store",
        "attribute-store",
        "list-append",
        "list-extend",
    ),
)
@pytest.mark.parametrize(
    "payload_kind",
    ["direct-map", "nested-map", "unrelated-scalar"],
    ids=("direct-source-map", "nested-source-map", "unrelated-scalar"),
)
@pytest.mark.parametrize(
    "mutator_module",
    ["a_mutator", "z_mutator"],
    ids=("sibling-before-owner-module", "sibling-after-owner-module"),
)
def test_dynamic_import_collector_tracks_unmodeled_source_mapping_transfers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transfer: str,
    payload_kind: str,
    mutator_module: str,
) -> None:
    if payload_kind == "unrelated-scalar":
        payload = "'unrelated scalar'"
    elif payload_kind == "nested-map":
        payload = "{'deep': [source_map]}"
    else:
        payload = "source_map"

    if transfer == "setdefault":
        operation = f"wrapper = {{}}\nwrapper.setdefault('nested', {payload})"
    elif transfer == "update":
        operation = f"wrapper = {{}}\nwrapper.update({{'nested': {payload}}})"
    elif transfer == "subscript-store":
        operation = f"wrapper = {{}}\nwrapper['nested'] = {payload}"
    elif transfer == "attribute-store":
        operation = f"wrapper = object()\nwrapper.nested = {payload}"
    elif transfer == "list-append":
        operation = f"wrapper = []\nwrapper.append({payload})"
    elif transfer == "list-extend":
        extended = "['unrelated scalar']" if payload_kind == "unrelated-scalar" else f"[{payload}]"
        operation = f"wrapper = []\nwrapper.extend({extended})"
    else:
        pytest.fail(f"unrecognized transfer fixture: {transfer}")

    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        f"polisyos.ir.{mutator_module}": (
            "from .api import ANALYTICS_FACADE_EXPORTS as source_map\n"
            f"{operation}\n"
            "opaque(wrapper)\n"
        ),
        "polisyos.ir.consumer": """from .analytics import load

load("polisyos.nested_map_hidden_import")
""",
        "polisyos.nested_map_hidden_import": "VALUE = 1\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    if payload_kind == "unrelated-scalar":
        entries = preflight.collect_dynamic_imports()
        assert "polisyos.nested_map_hidden_import" in [entry["pattern"] for entry in entries]
    else:
        with pytest.raises(preflight.DynamicImportCollectionError):
            preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    "mutator_module",
    ["a_mutator", "z_mutator"],
    ids=("sibling-before-owner-module", "sibling-after-owner-module"),
)
def test_dynamic_import_modeled_literal_map_and_pure_length_read_preserve_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutator_module: str,
) -> None:
    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        f"polisyos.ir.{mutator_module}": """from .api import ANALYTICS_FACADE_EXPORTS as source_map
wrapper = {"nested": [source_map]}
observed_size = len(wrapper)
""",
        "polisyos.ir.consumer": """from .analytics import load

load("polisyos.nested_map_hidden_import")
""",
        "polisyos.nested_map_hidden_import": "VALUE = 1\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    entries = preflight.collect_dynamic_imports()
    assert "polisyos.nested_map_hidden_import" in [entry["pattern"] for entry in entries]


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


@pytest.mark.parametrize(
    "cross_module_type_checking_write",
    [False, True],
    ids=("typed-sentinel-stays-prunable", "cross-module-write-keeps-sentinel-open"),
)
def test_dynamic_import_type_checking_source_effect_keeps_ordinary_if_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cross_module_type_checking_write: bool,
) -> None:
    source = (
        "import typing as typing_alias\n"
        "import importlib as importlib_alias\n"
        "if False:\n"
        '    importlib_alias.import_module("polisyos.literal_false_only")\n'
        "if typing_alias.TYPE_CHECKING:\n"
        '    importlib_alias.import_module("polisyos.typed_guard_only")\n'
    )
    _dynamic_import_fixture(tmp_path, monkeypatch, source)
    if cross_module_type_checking_write:
        (tmp_path / "src" / "unrelated_mutator.py").write_text(
            "import typing as typing_alias\ntyping_alias.TYPE_CHECKING = True\n",
            encoding="utf-8",
        )

    patterns = [entry["pattern"] for entry in preflight.collect_dynamic_imports()]
    assert "polisyos.literal_false_only" in patterns
    assert ("polisyos.typed_guard_only" in patterns) is cross_module_type_checking_write


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
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
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


def test_dynamic_import_source_backed_factory_result_matches_method_annotation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.storage": """from pathlib import Path

class PathLookingFactory:
    def path(self) -> Path:
        return Path("/tmp")
""",
            "polisyos.consumer": """from polisyos.storage import PathLookingFactory

path_value = PathLookingFactory().path()
path_value.exists()
""",
        },
    )

    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_source_method_transfer_uses_actual_annotated_artifact_id() -> None:
    from polisyos.core.artifacts.ids import ArtifactID

    validation_schema = ArtifactID.model_json_schema(mode="validation")
    serialization_schema = ArtifactID.model_json_schema(mode="serialization")
    assert validation_schema["pattern"] == r"^sha256:[0-9A-Fa-f]{64}$"
    assert serialization_schema["pattern"] == r"^sha256:[0-9a-f]{64}$"
    assert validation_schema["minLength"] == validation_schema["maxLength"] == 71
    assert serialization_schema["minLength"] == serialization_schema["maxLength"] == 71
    assert ArtifactID.prefix == "sha256:"
    assert str(ArtifactID.model_validate("sha256:" + "a" * 64)) == "sha256:" + "a" * 64

    source_paths = preflight._dynamic_source_paths("src")
    source_bindings = preflight._DynamicImportSourceBindings(source_paths)
    artifact_id_name = "polisyos.core.artifacts.ids.ArtifactID"
    assert source_bindings._source_pydantic_root_model_string(artifact_id_name) is not None
    assert source_bindings._source_pydantic_root_model_class_effects_are_safe(artifact_id_name)

    source = """
from pathlib import Path
from polisyos.core import artifacts

store = artifacts.FileSystemCAS(Path("/tmp/cas"))
record_ref = artifacts.ArtifactID.model_validate(
    "sha256:" + "a" * 64
)
signature_path = store._sig_path(record_ref)
signature_path.stat().st_mode & 0o777
"""
    source_path = REPO_ROOT / "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py"
    scanner = preflight._DynamicImportSourceScanner(
        source_path,
        relative_path="apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py",
        source_bindings=source_bindings,
    )

    assert scanner.scan(ast.parse(source)) == []


def test_dynamic_import_annotated_root_model_requires_schema_only_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.models": """from typing import Annotated
from pydantic import AfterValidator, RootModel

def opaque_transform(value):
    return value

class Token(RootModel[Annotated[str, AfterValidator(opaque_transform)]]):
    pass
""",
        },
    )
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))

    assert source_bindings._source_pydantic_root_model_string("polisyos.models.Token") is None


@pytest.mark.parametrize(
    "shadowed_name",
    [
        "RootModel",
        "Annotated",
        "WithJsonSchema",
        "ConfigDict",
        "ClassVar",
        "field_validator",
        "str",
    ],
)
def test_dynamic_import_root_model_requires_class_definition_time_import_identities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shadowed_name: str,
) -> None:
    imports = """from typing import Annotated as _real_Annotated, ClassVar as _real_ClassVar
from pydantic import (
    ConfigDict as _real_ConfigDict,
    RootModel as _real_RootModel,
    WithJsonSchema as _real_WithJsonSchema,
    field_validator as _real_field_validator,
)
from builtins import str as _real_str
"""
    real_name = f"_real_{shadowed_name}"
    module_source = (
        imports
        + f"{shadowed_name} = {real_name}\n"
        + """
def _schema_callback(schema, model):
    return None

class Token(
    RootModel[
        Annotated[
            str,
            WithJsonSchema({"type": "string"}),
        ]
    ]
):
    model_config = ConfigDict(json_schema_extra=_schema_callback)
    prefix: ClassVar[str] = "token:"

    @field_validator("root", mode="before")
    @classmethod
    def before(cls, value):
        return value

from typing import Annotated, ClassVar
from pydantic import ConfigDict, RootModel, WithJsonSchema, field_validator
from builtins import str
"""
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.models": module_source,
        },
    )
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))

    assert source_bindings._source_pydantic_root_model_string("polisyos.models.Token") is None


@pytest.mark.parametrize(
    "shadowed_class_name",
    [
        "ConfigDict",
        "ClassVar",
        "field_validator",
        "str",
        "_schema_callback",
        "classmethod",
        "property",
    ],
)
def test_dynamic_import_root_model_checks_class_local_bindings_at_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shadowed_class_name: str,
) -> None:
    class_bindings = {
        "ConfigDict": "    ConfigDict = _real_ConfigDict\n",
        "ClassVar": "    ClassVar = _real_ClassVar\n",
        "field_validator": "    field_validator = _real_field_validator\n",
        "str": "    str = _real_str\n",
        "_schema_callback": "    _schema_callback = lambda schema, model: None\n",
        "classmethod": "    classmethod = _real_classmethod\n",
        "property": "    property = _real_property\n",
    }
    module_source = """from typing import Annotated, ClassVar
from pydantic import ConfigDict, RootModel, WithJsonSchema, field_validator
from builtins import (
    classmethod as _real_classmethod,
    property as _real_property,
    str as _real_str,
)

def _schema_callback(schema, model):
    return None

class Token(RootModel[Annotated[str, WithJsonSchema({"type": "string"})]]):
@@CLASS_BINDING@@
    model_config = ConfigDict(json_schema_extra=_schema_callback)
    prefix: ClassVar[str] = "token:"

    @field_validator("root", mode="before")
    @classmethod
    def before(cls, value):
        return value

    @property
    def display(self):
        return self.root
""".replace("@@CLASS_BINDING@@", class_bindings[shadowed_class_name])
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.models": module_source,
        },
    )
    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))

    assert source_bindings._source_pydantic_root_model_string("polisyos.models.Token") is None


def test_dynamic_import_root_model_rejects_executable_late_reimport_schema_lookalike(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.models": """from typing import Annotated
from pydantic import RootModel
from opaque_vendor.schema import schema_lookalike

WithJsonSchema = schema_lookalike

class Token(RootModel[Annotated[str, WithJsonSchema({"type": "string"})]]):
    pass

from pydantic import WithJsonSchema
""",
            "polisyos.consumer": """from .models import Token

loaded_module = Token.model_validate("ordinary-string").root("polisyos.hidden_target").__name__
""",
            "polisyos.hidden_target": "class HiddenTarget: pass\n",
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    external_root = tmp_path / "deps"
    external_package = external_root / "opaque_vendor"
    external_package.mkdir(parents=True)
    (external_package / "__init__.py").write_text("", encoding="utf-8")
    external_module = external_package / "schema.py"
    external_module.write_text(
        """from importlib import import_module
from pydantic import AfterValidator

def schema_lookalike(schema, *, mode=None):
    return AfterValidator(lambda _value: import_module)
""",
        encoding="utf-8",
    )
    selected_paths = set(preflight._dynamic_source_paths("src"))
    assert external_module not in selected_paths

    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from importlib import import_module; "
                "from polisyos.models import Token; "
                "value = Token.model_validate('ordinary-string').root; "
                "print(value is import_module); "
                "print(value('json').__name__)"
            ),
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
    assert runtime.stdout.splitlines() == ["True", "json"]

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


@pytest.mark.parametrize(
    "include_shared_hashing",
    [False, True],
    ids=["three-selected-files", "four-selected-files"],
)
def test_dynamic_import_collector_scans_template_hash_functions_in_source_context(
    include_shared_hashing: bool,
) -> None:
    # Resolve the template fallback and canonical function from selected source members.
    template = preflight.SRC_ROOT / "polisyos/core/audit/standalone_verifier_template.py"
    source_paths = [
        template,
        preflight.SRC_ROOT / "polisyos/core/canon/__init__.py",
        preflight.SRC_ROOT / "polisyos/core/canon/hashing.py",
    ]
    if include_shared_hashing:
        source_paths.append(preflight.SRC_ROOT / "polisyos/common/hashing.py")
    context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(source_paths, source_context=context)
    template_member = next(member for member in context.members if member.path == template)
    scanner = preflight._DynamicImportSourceScanner(
        template,
        source_bindings=bindings,
        source_context=context,
    )

    assert scanner.scan(template_member.tree) == []
    assert "polisyos.core.canon.hashing" in scanner._source_function_scanners


def test_dynamic_import_allows_pure_recursive_module_time_function_return_unknown() -> None:
    source = """\
def descend(values: list[list[int]]) -> bool:
    if values:
        return descend(values[1:])
    return False

result = descend([[1], [2]])
"""
    namespace: dict[str, object] = {}
    exec(compile(source, "src/probe.py", "exec"), namespace)  # noqa: S102
    assert namespace["result"] is False  # noqa: S101

    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    entries = scanner.scan(ast.parse(source))

    assert entries == []  # noqa: S101
    result = scanner._module_environment["result"]
    assert not preflight._is_guarded_importer_binding(result)  # noqa: S101


def test_dynamic_import_same_state_recursive_backedge_preserves_importer_refusal() -> None:
    source = """\
import importlib

def repeat(loader):
    if recursive_condition:
        return repeat(loader)
    return loader

result = repeat(importlib.import_module)
"""
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="guarded importer value escapes through a function return",
    ):
        scanner.scan(ast.parse(source))


def test_dynamic_import_recursive_function_call_stays_in_inventory() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    entries = scanner.scan(
        ast.parse(
            """
import importlib

def load(depth):
    if depth:
        return load(depth - 1)
    return importlib.import_module("json")

result = load(1)
"""
        )
    )

    assert any(  # noqa: S101
        entry["call"] == "importlib.import_module" and entry["pattern"] == "json"
        for entry in entries
    )


def test_dynamic_import_recursive_function_importer_write_still_refuses() -> None:
    source = """
from importlib import import_module

def replace_importer(depth):
    global import_module
    if depth:
        return replace_importer(depth - 1)
    import_module = None

replace_importer(1)
"""
    namespace: dict[str, object] = {"__name__": "probe"}
    exec(compile(source, "src/probe.py", "exec"), namespace)  # noqa: S102
    assert namespace["import_module"] is None  # noqa: S101

    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="cross-scope write changes guarded importer binding",
    ):
        scanner.scan(ast.parse(source))


def test_dynamic_import_scans_actual_chronology_anchor_recursive_closure() -> None:
    relative_paths = (
        "polisyos/core/security/chronology_anchor.py",
        "polisyos/core/security/full_prefix.py",
        "polisyos/core/contracts/__init__.py",
        "polisyos/core/contracts/chronology.py",
        "polisyos/core/artifacts/__init__.py",
        "polisyos/core/artifacts/ids.py",
        "polisyos/core/artifacts/manifest.py",
    )
    paths = [preflight.SRC_ROOT / path for path in relative_paths]
    context = preflight._dynamic_read_source_context(paths)
    bindings = preflight._DynamicImportSourceBindings(paths, source_context=context)
    target = paths[0]
    member = next(item for item in context.members if item.path == target)
    scanner = preflight._DynamicImportSourceScanner(
        target,
        source_bindings=bindings,
        source_context=context,
    )

    assert scanner.scan(member.tree) == []  # noqa: S101


def test_dynamic_import_recursive_argument_transition_stays_in_inventory() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    entries = scanner.scan(
        ast.parse(
            """
import importlib

def select(name):
    if name == "json":
        return importlib.import_module("json")
    return select("json")

result = select("other")
"""
        )
    )

    assert any(  # noqa: S101
        entry["call"] == "importlib.import_module" and entry["pattern"] == "json"
        for entry in entries
    )


def test_dynamic_import_recursive_module_state_transition_stays_in_inventory() -> None:
    source = """
from importlib import import_module

ready = False

def select(depth):
    global ready
    if ready:
        return import_module("json")
    ready = True
    return select(depth)

result = select(None)
"""
    namespace: dict[str, object] = {}
    exec(compile(source, "src/probe.py", "exec"), namespace)  # noqa: S102
    assert namespace["result"].__name__ == "json"  # noqa: S101

    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    entries = scanner.scan(ast.parse(source))

    assert any(  # noqa: S101
        entry["call"] == "importlib.import_module" and entry["pattern"] == "json"
        for entry in entries
    )


def test_dynamic_import_same_module_mutual_recursion_keeps_importer_call() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    entries = scanner.scan(
        ast.parse(
            """
import importlib

def left(value):
    if value is None:
        return importlib.import_module("json")
    return right(None)

def right(value):
    return left(value)

result = left("start")
"""
        )
    )

    assert any(  # noqa: S101
        entry["call"] == "importlib.import_module" and entry["pattern"] == "json"
        for entry in entries
    )


def test_dynamic_import_collector_joins_finite_function_returns_and_global_writes() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )
    scanner.scan(
        ast.parse(
            """
state = "initial"

def left():
    global state
    state = "left"
    return "left-result"

def right():
    global state
    state = "right"
    return "right-result"

if condition:
    selected = left
else:
    selected = right

result = selected()
"""
        )
    )

    state = scanner._module_environment["state"]
    result = scanner._module_environment["result"]
    assert state.kind == "union"
    assert {binding.name for binding in state.items or () if binding.kind == "string"} == {
        "left",
        "right",
    }
    assert result.kind == "union"
    assert {binding.name for binding in result.items or () if binding.kind == "string"} == {
        "left-result",
        "right-result",
    }


def test_dynamic_import_collector_keeps_foreign_function_globals_separate_from_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.core.__init__": "",
            "polisyos.core.canon.__init__": """from .hashing import selected
""",
            "polisyos.core.canon.hashing": """from importlib import import_module
state = "foreign-initial"
def selected():
    global state
    state = "json"
    return state
""",
        },
    )
    template = tmp_path / "src/polisyos/template.py"
    template.write_text(
        """from importlib import import_module
state = "consumer-initial"
try:
    from polisyos.core.canon import selected
except ImportError:
    def selected():
        global state
        state = "consumer"
        return state
module_name = selected()
result = import_module(module_name)
""",
        encoding="utf-8",
    )

    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, polisyos.template as consumer, polisyos.core.canon.hashing as foreign; print(json.dumps({'module_name': consumer.module_name, 'result': consumer.result.__name__, 'consumer_state': consumer.state, 'foreign_state': foreign.state}))",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(runtime.stdout) == {  # noqa: S101
        "module_name": "json",
        "result": "json",
        "consumer_state": "consumer-initial",
        "foreign_state": "json",
    }

    entries = preflight.collect_dynamic_imports()
    assert len(entries) == 1  # noqa: S101
    entry = entries[0]
    assert entry["source_file"] == "src/polisyos/template.py"  # noqa: S101
    assert entry["call"] == "importlib.import_module"  # noqa: S101
    assert entry["pattern"] == "module_name"  # noqa: S101
    assert entry["allowed_targets"] == []  # noqa: S101


def test_dynamic_import_collector_refuses_mixed_known_and_opaque_function_targets() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="module-time local function target is ambiguous",
    ):
        scanner.scan(
            ast.parse(
                """
def known():
    return "known"

if condition:
    selected = known
else:
    selected = opaque_target

selected()
"""
            )
        )


def test_dynamic_import_collector_refuses_mixed_source_and_reflected_function_targets() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="computed reflection has unresolved importer provenance",
    ):
        scanner.scan(
            ast.parse(
                """
import importlib

def known():
    return "known"

if condition:
    selected = known
else:
    selected = getattr(importlib, unresolved_member)

selected()
"""
            )
        )


def test_dynamic_import_collector_preserves_aliased_importer_in_foreign_function(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.core.__init__": "",
            "polisyos.core.canon.__init__": "from .hashing import selected\n",
            "polisyos.core.canon.hashing": (
                "from importlib import import_module as load_module\n\n"
                "def selected(name):\n"
                "    return load_module(name)\n"
            ),
        },
    )
    template = tmp_path / "src/polisyos/template.py"
    template.write_text(
        "try:\n"
        "    from polisyos.core.canon import selected\n"
        "except ImportError:\n"
        "    def selected(name):\n"
        "        return name\n"
        'result = selected("foreign_alias_target")\n',
        encoding="utf-8",
    )
    paths = [
        template,
        tmp_path / "src/polisyos/__init__.py",
        tmp_path / "src/polisyos/core/__init__.py",
        tmp_path / "src/polisyos/core/canon/__init__.py",
        tmp_path / "src/polisyos/core/canon/hashing.py",
    ]
    context = preflight._dynamic_read_source_context(paths)
    bindings = preflight._DynamicImportSourceBindings(paths, source_context=context)
    scanner = preflight._DynamicImportSourceScanner(
        template,
        source_bindings=bindings,
        source_context=context,
    )

    assert (
        scanner.scan(next(member.tree for member in context.members if member.path == template))
        == []
    )
    foreign = scanner._source_function_scanners["polisyos.core.canon.hashing"]
    assert any(entry["call"] == "importlib.import_module" for entry in foreign.entries)


@pytest.mark.parametrize(
    "mutation",
    [
        'globals()["__getattr__"] = replace_hook(__getattr__)',
        'setattr(sys.modules[__name__], "__getattr__", replace_hook(__getattr__))',
    ],
    ids=("globals-hook-store", "sys-modules-hook-store"),
)
def test_dynamic_import_pep562_hook_mutation_is_the_decisive_property(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    facade_source = (
        "import sys\n"
        "from external_decorators import replace_hook\n"
        "def __getattr__(name):\n"
        '    if name == "loader":\n'
        '        return "ordinary value"\n'
        "    raise AttributeError(name)\n"
        f"{mutation}\n"
    )
    registry_path = _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": facade_source,
            "polisyos.probe.consumer": 'from .facade import loader\nloader("json")\n',
        },
    )
    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()

    facade_path = tmp_path / "src/polisyos/probe/facade.py"
    consumer_path = tmp_path / "src/polisyos/probe/consumer.py"
    without_mutation = facade_source.replace(f"{mutation}\n", "", 1)
    assert without_mutation != facade_source
    facade_path.write_text(without_mutation, encoding="utf-8")
    assert "from external_decorators import replace_hook" in facade_path.read_text(encoding="utf-8")
    assert 'loader("json")' in consumer_path.read_text(encoding="utf-8")
    assert preflight.collect_dynamic_imports() == []
    assert preflight.validate_dynamic_imports() == []


def _ensure_pep562_runtime_packages(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    for package in ("polisyos", "polisyos/probe"):
        package_path = source_root.joinpath(*package.split("/"))
        package_path.mkdir(parents=True, exist_ok=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")


def _write_pep562_external_importer(tmp_path: Path) -> Path:
    external_root = tmp_path / "external"
    external_root.mkdir()
    (external_root / "external_decorators.py").write_text(
        "from importlib import import_module\n"
        "def facade_module_name():\n"
        '    return "polisyos.probe.facade"\n'
        "def hook_name():\n"
        '    return "__getattr__"\n'
        "def replacement(name):\n"
        "    if name == 'loader':\n"
        "        return import_module\n"
        "    if name == 'json':\n"
        "        return import_module(name)\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    return external_root


@pytest.mark.parametrize(
    "mutation",
    [
        'def install():\n    namespace = globals()\n    namespace["__getattr__"] = replacement\ninstall()',
        'def install():\n    setattr(sys.modules[__name__], "__getattr__", replacement)\ninstall()',
        'def install():\n    sys.modules[__name__].__dict__["__getattr__"] = replacement\ninstall()',
        'def install():\n    getattr(sys.modules[__name__], "__dict__")["__getattr__"] = replacement\ninstall()',
        'def install():\n    vars(sys.modules[__name__])["__getattr__"] = replacement\ninstall()',
        'def install():\n    globals().update({"__getattr__": replacement})\ninstall()',
        'namespace = locals()\nnamespace["__getattr__"] = replacement',
        'namespace = vars()\nnamespace["__getattr__"] = replacement',
    ],
    ids=(
        "called-globals-alias",
        "called-setattr-sys-modules",
        "called-module-dict-subscript",
        "called-getattr-dict-subscript",
        "called-vars-module-dict",
        "called-globals-update",
        "module-locals-alias",
        "module-vars-alias",
    ),
)
def test_dynamic_import_fails_closed_for_reached_selected_module_namespace_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    external_root = _write_pep562_external_importer(tmp_path)
    facade_source = (
        "import sys\n"
        "from external_decorators import replacement\n"
        "def __getattr__(name):\n"
        '    if name == "loader":\n'
        '        return "ordinary value"\n'
        "    raise AttributeError(name)\n"
        f"{mutation}\n"
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": facade_source,
            "polisyos.probe.consumer": ('from .facade import loader\nloader("json")\n'),
        },
    )

    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; assert loader('json').__name__ == 'json'",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr

    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()

    facade_path = tmp_path / "src/polisyos/probe/facade.py"
    without_mutation = facade_source.replace(f"{mutation}\n", "", 1)
    assert without_mutation != facade_source
    facade_path.write_text(without_mutation, encoding="utf-8")
    assert 'loader("json")' in (tmp_path / "src/polisyos/probe/consumer.py").read_text(
        encoding="utf-8"
    )
    assert preflight.collect_dynamic_imports() == []


def test_dynamic_import_refuses_unresolved_selected_module_namespace_write_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_root = _write_pep562_external_importer(tmp_path)
    facade_source = (
        "from external_decorators import hook_name, replacement\n"
        "def __getattr__(name):\n"
        '    if name == "loader":\n'
        '        return "ordinary value"\n'
        "    raise AttributeError(name)\n"
        "def install():\n"
        "    namespace = globals()\n"
        "    namespace[hook_name()] = replacement\n"
        "install()\n"
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": facade_source,
            "polisyos.probe.consumer": ('from .facade import loader\nloader("json")\n'),
        },
    )
    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; assert loader('json').__name__ == 'json'",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    ("setup_prefix", "mutation"),
    [
        ("", 'setattr(sys.modules[facade_module_name()], "__getattr__", replacement)'),
        ("", 'setattr(sys.modules.get(facade_module_name()), "__getattr__", replacement)'),
        ("", "sys.modules[facade_module_name()].__getattr__ = replacement"),
        ("", 'sys.modules[facade_module_name()].__dict__["__getattr__"] = replacement'),
        ("", 'getattr(sys.modules[facade_module_name()], "__dict__")["__getattr__"] = replacement'),
        ("", 'vars(sys.modules[facade_module_name()])["__getattr__"] = replacement'),
        (
            "",
            'vars(sys.modules[facade_module_name()]).update({"__getattr__": replacement})',
        ),
        (
            "registry = sys.modules\nfacade_module = registry[facade_module_name()]\n",
            'setattr(facade_module, "__getattr__", replacement)',
        ),
        (
            "if facade_module_name():\n"
            "    facade_module = sys.modules[facade_module_name()]\n"
            "else:\n"
            "    facade_module = sys.modules.get(facade_module_name())\n",
            'setattr(facade_module, "__getattr__", replacement)',
        ),
    ],
    ids=(
        "setattr-subscript",
        "setattr-get",
        "attribute-assignment",
        "module-dict-subscript",
        "getattr-dict-subscript",
        "vars-module-dict",
        "module-dict-update",
        "aliased-registry-selection",
        "conditional-registry-selection-join",
    ),
)
def test_dynamic_import_refuses_reached_unresolved_sys_modules_namespace_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    setup_prefix: str,
    mutation: str,
) -> None:
    external_root = _write_pep562_external_importer(tmp_path)
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": (
                'loader_target = "ordinary value"\n'
                "def __getattr__(name):\n"
                '    if name == "loader":\n'
                "        return loader_target\n"
                "    raise AttributeError(name)\n"
            ),
            "polisyos.probe.setup": (
                "import sys\n"
                "from . import facade\n"
                "from external_decorators import facade_module_name, replacement\n"
                f"{setup_prefix}"
                "def install():\n"
                f"    {mutation}\n"
                "install()\n"
            ),
            "polisyos.probe.consumer": ('from .facade import loader\nloader("json")\n'),
        },
    )
    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "import polisyos.probe.setup; "
            "from polisyos.probe.facade import loader; "
            "assert loader('json').__name__ == 'json'",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match=r"unresolved sys\.modules owner",
    ):
        preflight.collect_dynamic_imports()

    setup_path = tmp_path / "src/polisyos/probe/setup.py"
    setup_source = setup_path.read_text(encoding="utf-8")
    without_write = setup_source.replace(f"    {mutation}\n", "    pass\n", 1)
    assert without_write != setup_source
    setup_path.write_text(without_write, encoding="utf-8")
    assert 'loader("json")' in (tmp_path / "src/polisyos/probe/consumer.py").read_text(
        encoding="utf-8"
    )
    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize("owner", ["sys.modules['json']", "sys.modules.get('json')"])
def test_dynamic_import_keeps_known_nonselected_sys_modules_owner_nonblocking(
    owner: str,
) -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    entries = scanner.scan(ast.parse(f"import sys\nsetattr({owner}, 'fixture_marker', True)\n"))

    assert entries == []


def test_dynamic_import_keeps_nonnamespace_setattr_receiver_positive() -> None:
    scanner = preflight._DynamicImportSourceScanner(
        REPO_ROOT / "src" / "probe.py",
        relative_path="src/probe.py",
    )

    entries = scanner.scan(
        ast.parse(
            "from importlib import import_module\n"
            "holder = object()\n"
            "setattr(holder, 'marker', True)\n"
            "import_module('nonnamespace_receiver_positive')\n"
        )
    )

    assert [entry["pattern"] for entry in entries] == ["nonnamespace_receiver_positive"]


def test_dynamic_import_rejects_changed_ambiguous_hook_global_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_root = _write_pep562_external_importer(tmp_path)
    facade_source = (
        "from external_decorators import replacement\n"
        'loader_target = "ordinary value"\n'
        "def __getattr__(name):\n"
        '    if name == "loader":\n'
        "        return loader_target\n"
        "    raise AttributeError(name)\n"
        "def install():\n"
        "    global loader_target\n"
        "    loader_target = replacement\n"
        "install()\n"
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": facade_source,
            "polisyos.probe.consumer": ('from .facade import loader\nloader("json")\n'),
        },
    )
    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; assert loader('json').__name__ == 'json'",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()

    facade_path = tmp_path / "src/polisyos/probe/facade.py"
    facade_path.write_text(
        facade_source.replace(
            "    global loader_target\n    loader_target = replacement\n",
            "    return None\n",
        ),
        encoding="utf-8",
    )
    assert 'loader("json")' in (tmp_path / "src/polisyos/probe/consumer.py").read_text(
        encoding="utf-8"
    )
    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "future_annotations",
    [True, False],
    ids=("postponed-annotation", "eager-annotation"),
)
def test_dynamic_import_ignores_hook_annotation_only_global_rebinding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    future_annotations: bool,
) -> None:
    annotation_mode = "from __future__ import annotations\n" if future_annotations else ""
    facade_source = (
        annotation_mode
        + "from typing import Any\n"
        + 'loader_target = "ordinary value"\n'
        + "def __getattr__(name: Any) -> Any:\n"
        + '    if name == "loader":\n'
        + "        return loader_target\n"
        + "    raise AttributeError(name)\n"
        + "Any = None\n"
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": facade_source,
            "polisyos.probe.consumer": "from .facade import loader\n",
        },
    )
    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.probe.facade import loader; assert loader == 'ordinary value'",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr
    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "target_write",
    [
        'setattr(facade, "__getattr__", replacement)',
        "facade.loader_target = replacement",
    ],
    ids=("cross-module-hook-write", "cross-module-hook-global-write"),
)
def test_dynamic_import_refuses_reached_cross_selected_module_hook_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target_write: str,
) -> None:
    external_root = _write_pep562_external_importer(tmp_path)
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.probe.facade": (
                'loader_target = "ordinary value"\n'
                "def __getattr__(name):\n"
                '    if name == "loader":\n'
                "        return loader_target\n"
                "    raise AttributeError(name)\n"
            ),
            "polisyos.probe.setup": (
                "from . import facade\n"
                "from external_decorators import replacement\n"
                "def install():\n"
                f"    {target_write}\n"
                "install()\n"
            ),
            "polisyos.probe.consumer": ('from .facade import loader\nloader("json")\n'),
        },
    )
    _ensure_pep562_runtime_packages(tmp_path)
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "import polisyos.probe.setup; "
            "from polisyos.probe.facade import loader; "
            "assert loader('json').__name__ == 'json'",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(external_root), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert runtime.returncode == 0, runtime.stderr
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()

    setup_path = tmp_path / "src/polisyos/probe/setup.py"
    setup_source = setup_path.read_text(encoding="utf-8")
    without_write = setup_source.replace(f"    {target_write}\n", "    pass\n", 1)
    assert without_write != setup_source
    setup_path.write_text(without_write, encoding="utf-8")
    assert 'loader("json")' in (tmp_path / "src/polisyos/probe/consumer.py").read_text(
        encoding="utf-8"
    )
    assert preflight.collect_dynamic_imports() == []


@pytest.mark.parametrize(
    "mutation",
    ["store-new-slot", "replace-unrelated-slot", "replace-map-slot", "delete-unrelated-slot"],
    ids=("exact-store", "exact-replace-unrelated", "exact-replace-map", "exact-delete"),
)
@pytest.mark.parametrize(
    "mutator_module",
    ["a_mutator", "z_mutator"],
    ids=("sibling-before-owner-module", "sibling-after-owner-module"),
)
def test_dynamic_import_exact_local_mapping_slot_write_preserves_nested_source_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    mutator_module: str,
) -> None:
    mutation_source = {
        "store-new-slot": "wrapper = {'nested': source_map}\nwrapper['unrelated'] = 1",
        "replace-unrelated-slot": (
            "wrapper = {'nested': source_map, 'unrelated': 0}\nwrapper['unrelated'] = 1"
        ),
        "replace-map-slot": "wrapper = {'nested': source_map}\nwrapper['nested'] = 1",
        "delete-unrelated-slot": (
            "wrapper = {'nested': source_map, 'unrelated': 0}\ndel wrapper['unrelated']"
        ),
    }[mutation]
    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        f"polisyos.ir.{mutator_module}": (
            "from .api import ANALYTICS_FACADE_EXPORTS as source_map\n" + mutation_source + "\n"
        ),
        "polisyos.ir.consumer": """from .analytics import load

load("polisyos.nested_map_hidden_import")
""",
        "polisyos.nested_map_hidden_import": "VALUE = 1\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)
    entries = preflight.collect_dynamic_imports()
    assert "polisyos.nested_map_hidden_import" in [entry["pattern"] for entry in entries]


@pytest.mark.parametrize(
    "transfer",
    ["aliased-source-map-update", "unknown-local-map-key", "opaque-local-wrapper"],
    ids=("actual-source-map-alias", "unknown-key-refuses", "opaque-wrapper-refuses"),
)
@pytest.mark.parametrize(
    "mutator_module",
    ["a_mutator", "z_mutator"],
    ids=("sibling-before-owner-module", "sibling-after-owner-module"),
)
def test_dynamic_import_unknown_or_source_owned_mapping_effects_still_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transfer: str,
    mutator_module: str,
) -> None:
    transfer_source = {
        "aliased-source-map-update": "source_alias = source_map\nsource_alias['unrelated'] = 1",
        "unknown-local-map-key": ("wrapper = {'nested': source_map}\nwrapper[unknown_key] = 1"),
        "opaque-local-wrapper": "wrapper = {'nested': source_map}\nopaque(wrapper)",
    }[transfer]
    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        f"polisyos.ir.{mutator_module}": (
            "from .api import ANALYTICS_FACADE_EXPORTS as source_map\n" + transfer_source + "\n"
        ),
        "polisyos.ir.consumer": """from .analytics import load

load("polisyos.nested_map_hidden_import")
""",
        "polisyos.nested_map_hidden_import": "VALUE = 1\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    "reverse_source_order",
    [False, True],
    ids=("canonical-source-order", "reverse-source-order"),
)
@pytest.mark.parametrize(
    "mutate_selected_namespace",
    [False, True],
    ids=("unmutated-source-map-positive", "selected-namespace-mutation-refuses"),
)
def test_dynamic_import_collector_maps_only_importable_source_members_in_mixed_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reverse_source_order: bool,
    mutate_selected_namespace: bool,
) -> None:
    modules = {
        "polisyos.__init__": "",
        "polisyos.ir.__init__": "",
        "polisyos.ir.api": """import importlib

ANALYTICS_FACADE_EXPORTS = {
    "load": ("importlib", "import_module"),
}

def resolve_lazy_export(name, *, namespace, exports):
    try:
        module_name, attr_name = exports[name]
    except KeyError as exc:
        module_name = namespace.get("__name__", "<unknown>")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from exc
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    namespace[name] = value
    return value
""",
        "polisyos.ir.analytics": """from .api import ANALYTICS_FACADE_EXPORTS, resolve_lazy_export

def __getattr__(name):
    return resolve_lazy_export(name, namespace=globals(), exports=ANALYTICS_FACADE_EXPORTS)
""",
        "polisyos.ir.consumer": """from .analytics import load

load("polisyos.hidden_lazy_import")
""",
        "polisyos.hidden_lazy_import": "VALUE = 1\n",
        "polisyos.ambiguous_identity": "VALUE = 'module-file'\n",
        "polisyos.ambiguous_identity.__init__": "VALUE = 'package-initializer'\n",
    }
    _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    root_sources = {
        "tools/polisyos/shared.py": (
            'import importlib\nimportlib.import_module("polisyos.tools_root_hidden_import")\n'
        ),
        "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py": (
            'import importlib\nimportlib.import_module("polisyos.apps_script_hidden_import")\n'
        ),
        "packages/polisyos/shared.py": (
            'import importlib\nimportlib.import_module("polisyos.packages_root_hidden_import")\n'
        ),
    }
    if mutate_selected_namespace:
        root_sources["apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py"] += (
            "\nimport polisyos.ir.api as selected_api\n"
            "selected_api.ANALYTICS_FACADE_EXPORTS = {"
            "'load': ('polisyos.changed_hidden_import', 'VALUE')}\n"
        )
    for relative_path, source in root_sources.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    original_paths = preflight._dynamic_source_paths
    selected_paths = original_paths("src", "tools", "apps", "packages")
    context = preflight._dynamic_read_source_context(selected_paths)
    bindings = preflight._DynamicImportSourceBindings(selected_paths, source_context=context)
    bindings_without_context = preflight._DynamicImportSourceBindings(selected_paths)
    labels = {member.relative_path for member in context.members}
    assert {
        "src/polisyos/ambiguous_identity.py",
        "src/polisyos/ambiguous_identity/__init__.py",
        "tools/polisyos/shared.py",
        "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py",
        "packages/polisyos/shared.py",
    } <= labels
    selected_modules = bindings._selected_source_module_names()
    assert "polisyos.ir.api" in selected_modules
    assert (
        "polisyos.ambiguous_identity"
        not in bindings_without_context._selected_source_module_names()
    )
    assert "polisyos.ambiguous_identity" not in selected_modules
    assert "polisyos.shared" not in selected_modules
    assert not any(name.startswith(("tools.", "apps.", "packages.")) for name in selected_modules)

    monkeypatch.setattr(
        preflight,
        "_dynamic_source_paths",
        lambda *scopes: (
            list(reversed(original_paths(*scopes)))
            if reverse_source_order
            else original_paths(*scopes)
        ),
    )

    if mutate_selected_namespace:
        with pytest.raises(preflight.DynamicImportCollectionError):
            preflight.collect_dynamic_imports()
        return

    entries = preflight.collect_dynamic_imports()
    patterns_by_source = {(entry["source_file"], entry["pattern"]) for entry in entries}
    assert {
        (
            "src/polisyos/ir/consumer.py",
            "polisyos.hidden_lazy_import",
        ),
        ("tools/polisyos/shared.py", "polisyos.tools_root_hidden_import"),
        (
            "apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py",
            "polisyos.apps_script_hidden_import",
        ),
        ("packages/polisyos/shared.py", "polisyos.packages_root_hidden_import"),
    } <= patterns_by_source


@pytest.mark.parametrize(
    ("callback_kind", "callback_body"),
    [
        ("schema", "    mutate(model)\n"),
        ("schema", "    target = model\n    mutate(target)\n"),
        ("schema", '    mutate({"model": model})\n'),
        ("validator", "        mutate(cls)\n"),
    ],
    ids=["schema-direct", "schema-alias", "schema-nested-argument", "validator-classmethod"],
)
def test_dynamic_import_root_model_refuses_opaque_class_effect_callbacks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    callback_kind: str,
    callback_body: str,
) -> None:
    if callback_kind == "schema":
        imports = """from typing import Annotated, ClassVar
from pydantic import ConfigDict, RootModel, WithJsonSchema
from opaque_vendor import mutate
"""
        callback = "def _schema_callback(schema, model):\n" + callback_body
        class_body = """class Token(RootModel[Annotated[str, WithJsonSchema({"type": "string"})]]):
    model_config = ConfigDict(json_schema_extra=_schema_callback)
    prefix: ClassVar[str] = "token:"
"""
        trigger = "Token.model_json_schema()\n"
    else:
        imports = """from typing import Annotated, ClassVar
from pydantic import RootModel, WithJsonSchema, field_validator
from opaque_vendor import mutate
"""
        callback = ""
        class_body = """class Token(RootModel[Annotated[str, WithJsonSchema({"type": "string"})]]):
    prefix: ClassVar[str] = "token:"

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value):
@@CALLBACK@@        return value
""".replace("@@CALLBACK@@", callback_body)
        trigger = """Token.model_validate("ordinary")
"""
    modules = {
        "polisyos.__init__": "",
        "polisyos.models": imports + "\n" + callback + "\n" + class_body,
        "polisyos.consumer": """from .models import Token

@@TRIGGER@@
loaded_module = Token.model_validate("ordinary").root("json").__name__
""".replace("@@TRIGGER@@", trigger),
    }
    registry_path = _dynamic_import_internal_modules_fixture(tmp_path, monkeypatch, modules)

    external_root = tmp_path / "deps"
    external_root.mkdir()
    (external_root / "opaque_vendor.py").write_text(
        """from importlib import import_module
from types import SimpleNamespace

def mutate(value):
    if isinstance(value, dict):
        model = value["model"]
    elif isinstance(value, list):
        model = value[0]
    else:
        model = value

    def replacement(cls, value):
        return SimpleNamespace(root=import_module)

    model.model_validate = classmethod(replacement)
""",
        encoding="utf-8",
    )
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            ("from polisyos.consumer import loaded_module; print(loaded_module)"),
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
    assert runtime.stdout.splitlines() == ["json"]

    source_bindings = preflight._DynamicImportSourceBindings(preflight._dynamic_source_paths("src"))
    source_name = "polisyos.models.Token"
    assert source_bindings._source_pydantic_root_model_string(source_name) is None
    assert source_name in source_bindings.invalidated_source_classes
    assert source_bindings._source_pydantic_root_model_candidate(source_name)

    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()

    registry_path.write_text(_render_dynamic_imports_toml([]), encoding="utf-8")
    findings = preflight.validate_dynamic_imports()
    assert any(
        finding.message == "dynamic import source inventory is incomplete"
        and "dynamic importer binding is ambiguous or unresolved" in finding.detail
        for finding in findings
    ), findings


def test_dynamic_import_resolves_core_lazy_exports_after_finite_owner_updates() -> None:
    """A Core facade reads its completed source-owned map after literal module initialization."""
    source_paths = [
        REPO_ROOT / relative
        for relative in (
            "src/polisyos/runtime/quality/epoch_deployment.py",
            "src/polisyos/core/__init__.py",
            "src/polisyos/core/artifacts/__init__.py",
            "src/polisyos/core/artifacts/signed_evidence.py",
            "src/polisyos/core/artifacts/protocol.py",
            "src/polisyos/core/artifacts/manifest.py",
            "src/polisyos/core/artifacts/ownership.py",
        )
    ]
    source_context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(
        source_paths,
        source_context=source_context,
    )
    epoch_path = source_paths[0].resolve()
    epoch_member = next(member for member in source_context.members if member.path == epoch_path)
    scanner = preflight._DynamicImportSourceScanner(
        epoch_path,
        relative_path=epoch_member.relative_path,
        source_bindings=bindings,
        source_context=source_context,
    )
    scanner.scan(epoch_member.tree)
    core_snapshot = bindings._module_execution_snapshot("polisyos.core")
    assert core_snapshot is not None  # noqa: S101
    core_exports = dict(core_snapshot.namespace)["_LAZY_EXPORTS"]
    assert core_exports.values is not None  # noqa: S101
    assert all(value.sequence_type == "tuple" for value in core_exports.values)  # noqa: S101
    symbol = "FileSystemSignedArtifactEvidenceRepository"
    direct = bindings.import_binding(
        "polisyos.core.artifacts.signed_evidence",
        symbol,
        current_module="polisyos.runtime.quality.epoch_deployment",
    )
    facade = bindings.import_binding(
        "polisyos.core",
        symbol,
        current_module="polisyos.runtime.quality.epoch_deployment",
        is_package=True,
    )

    assert direct.kind == "other"  # noqa: S101
    assert facade == direct  # noqa: S101


def test_dynamic_import_resolves_finite_mutable_pep562_export_map_updates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = """import importlib

_EXPORTS = {
    "existing": ("polisyos.catalog.implementation", "existing"),
}
_NAMES = ("added_by_comprehension",)
_EXPORTS.update(
    {name: ("polisyos.catalog.implementation", name) for name in _NAMES}
)
_EXPORTS.update(
    {"added_by_literal": ("polisyos.catalog.implementation", "added_by_literal")}
)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    implementation_source = """def existing():
    return None

def added_by_comprehension():
    return None

def added_by_literal():
    return None
"""
    consumer_source = """from .facade import added_by_comprehension

added_by_comprehension()
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.facade": facade_source,
            "polisyos.catalog.implementation": implementation_source,
            "polisyos.catalog.consumer": consumer_source,
        },
    )
    source_paths = preflight._dynamic_source_paths("src")
    source_context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(source_paths, source_context=source_context)

    direct = bindings.import_binding(
        "polisyos.catalog.implementation",
        "added_by_comprehension",
        current_module="polisyos.catalog.consumer",
    )
    facade = bindings.import_binding(
        "polisyos.catalog.facade",
        "added_by_comprehension",
        current_module="polisyos.catalog.consumer",
        is_package=True,
    )

    assert direct.kind == "other"  # noqa: S101
    assert facade == direct  # noqa: S101
    snapshot = bindings._module_execution_snapshot("polisyos.catalog.facade")
    assert snapshot is not None  # noqa: S101
    entries = preflight._dynamic_source_lazy_export_map_entries(
        dict(snapshot.namespace)["_EXPORTS"]
    )
    assert entries is not None  # noqa: S101
    assert len(entries) == 3  # noqa: S101
    export_map = dict(snapshot.namespace)["_EXPORTS"]
    assert export_map.values is not None  # noqa: S101
    assert all(value.sequence_type == "tuple" for value in export_map.values)  # noqa: S101


@pytest.mark.parametrize(
    "mutator_source",
    [
        """from .facade import _EXPORTS as exports
exports.update({"foreign": ("polisyos.catalog.implementation", "existing")})
""",
        """from .facade import _EXPORTS as exports
def mutate_late():
    exports.update({"foreign": ("polisyos.catalog.implementation", "existing")})
""",
    ],
    ids=["outside-owner-update", "late-alias-update"],
)
def test_dynamic_import_refuses_mutable_pep562_export_map_alias_effects(
    mutator_source: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = """import importlib

_EXPORTS = {
    "existing": ("polisyos.catalog.implementation", "existing"),
}

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.facade": facade_source,
            "polisyos.catalog.aaa_mutator": mutator_source,
            "polisyos.catalog.implementation": "def existing():\n    return None\n",
            "polisyos.catalog.consumer": "from .facade import existing\n",
        },
    )
    source_paths = preflight._dynamic_source_paths("src")
    source_context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(source_paths, source_context=source_context)
    mutator_path = (tmp_path / "src/polisyos/catalog/aaa_mutator.py").resolve()
    mutator = next(member for member in source_context.members if member.path == mutator_path)
    scanner = preflight._DynamicImportSourceScanner(
        mutator.path,
        relative_path=mutator.relative_path,
        source_bindings=bindings,
        source_context=source_context,
    )
    scanner.scan(mutator.tree)

    assert "polisyos.catalog.facade._EXPORTS" in bindings._source_mapping_effects  # noqa: S101
    facade = bindings.import_binding(
        "polisyos.catalog.facade",
        "existing",
        current_module="polisyos.catalog.consumer",
        is_package=True,
    )
    assert facade.kind == "ambiguous"  # noqa: S101
    assert facade.guarded  # noqa: S101


def test_dynamic_import_refuses_unresolved_owner_export_comprehension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = """import importlib

_EXPORTS = {
    "existing": ("polisyos.catalog.implementation", "existing"),
}
_EXPORTS.update(
    {
        name: ("polisyos.catalog.implementation", name)
        for name in runtime_names
    }
)

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.catalog.facade": facade_source,
            "polisyos.catalog.implementation": "def existing():\n    return None\n",
            "polisyos.catalog.consumer": "from .facade import existing\n",
        },
    )
    source_paths = preflight._dynamic_source_paths("src")
    source_context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(source_paths, source_context=source_context)

    facade = bindings.import_binding(
        "polisyos.catalog.facade",
        "existing",
        current_module="polisyos.catalog.consumer",
        is_package=True,
    )

    assert "polisyos.catalog.facade._EXPORTS" in bindings._source_mapping_effects  # noqa: S101
    assert facade.kind == "ambiguous"  # noqa: S101
    assert facade.guarded  # noqa: S101


@pytest.mark.parametrize(
    ("map_setup", "expected_runtime"),
    [
        (
            """_EXPORTS = {
    "added": ["polisyos.catalog.implementation", "existing"],
}
""",
            "existing",
        ),
        (
            """_EXPORTS = {
    "existing": ("polisyos.catalog.implementation", "existing"),
}
_PAIR = ["polisyos.catalog.implementation", "existing"]
_EXPORTS.update({"added": _PAIR})
_PAIR[1] = "other"
""",
            "other",
        ),
    ],
    ids=["list-literal-pair", "list-alias-mutated-after-update"],
)
def test_dynamic_import_refuses_list_valued_lazy_export_pairs(
    map_setup: str,
    expected_runtime: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = (
        "import importlib\n\n"
        + map_setup
        + """
def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    )
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.catalog.__init__": "",
            "polisyos.catalog.facade": facade_source,
            "polisyos.catalog.implementation": """def existing():
    return "existing"

def other():
    return "other"
""",
            "polisyos.catalog.consumer": """from .facade import added

print(added())
""",
        },
    )
    runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "import polisyos.catalog.consumer",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    assert runtime.stdout.splitlines() == [expected_runtime]  # noqa: S101

    source_paths = preflight._dynamic_source_paths("src")
    source_context = preflight._dynamic_read_source_context(source_paths)
    bindings = preflight._DynamicImportSourceBindings(source_paths, source_context=source_context)
    facade = bindings.import_binding(
        "polisyos.catalog.facade",
        "added",
        current_module="polisyos.catalog.consumer",
        is_package=True,
    )

    assert facade.kind == "ambiguous"  # noqa: S101
    assert facade.guarded  # noqa: S101


@pytest.mark.parametrize(
    ("module_mutation", "runtime_should_fail"),
    [
        ("importlib.import_module = None", True),
        ("_importlib_alias = importlib\n_importlib_alias.import_module = None", True),
        ("setattr(importlib, 'import_module', None)", True),
        ("importlib.__dict__['import_module'] = None", True),
        (
            "_importlib_namespace = importlib.__dict__\n"
            "_importlib_namespace['import_module'] = None",
            True,
        ),
        ("vars(importlib)['import_module'] = None", True),
        ("getattr(importlib, '__dict__')['import_module'] = None", True),
        ("importlib.__dict__.update({'import_module': None})", True),
        ("importlib.__dict__['unrelated_member'] = None", False),
        ("vars(importlib)['unrelated_member'] = None", False),
        ("getattr(importlib, '__dict__')['unrelated_member'] = None", False),
        ("importlib.__dict__.update({'unrelated_member': None})", False),
        (
            "import os\nimportlib.__dict__[os.getenv('EFFECT_MEMBER')] = None",
            True,
        ),
        ("importlib.unrelated_member = None", False),
        (
            "_module_namespace = vars(importlib)\n_module_namespace |= {'import_module': None}",
            True,
        ),
        (
            "_module_namespace = vars(importlib)\n_module_namespace |= {'unrelated_member': None}",
            False,
        ),
        (
            "_module_namespace = vars(importlib)\n"
            "_module_namespace |= (('unrelated_member', None),)",
            False,
        ),
        (
            "_pairs = [['unrelated_member', None]]\n"
            "_pairs[0][0] = 'import_module'\n"
            "_module_namespace = vars(importlib)\n"
            "_module_namespace |= _pairs",
            True,
        ),
        (
            "_module_namespace = vars(importlib)\n_module_namespace |= [('import_module', None)]",
            True,
        ),
        (
            "_module_namespace = vars(importlib)\n"
            "_module_namespace |= {('unrelated_member', None)}",
            False,
        ),
        (
            "from external_updates import member_name\n"
            "_module_namespace = vars(importlib)\n"
            "_module_namespace |= {member_name: None}",
            True,
        ),
        (
            "from external_updates import updates\n"
            "_module_namespace = vars(importlib)\n"
            "_module_namespace |= updates",
            True,
        ),
    ],
    ids=[
        "mutated-importer",
        "mutated-importer-alias",
        "setattr-mutated-importer",
        "module-dict-mutated-importer",
        "module-dict-alias-mutated-importer",
        "vars-mutated-importer",
        "getattr-dict-mutated-importer",
        "module-dict-update-mutated-importer",
        "module-dict-unrelated-member-write",
        "vars-unrelated-member-write",
        "getattr-dict-unrelated-member-write",
        "module-dict-update-unrelated-member-write",
        "module-dict-unresolved-key",
        "unrelated-member-write",
        "module-namespace-ior-mutated-importer",
        "module-namespace-ior-unrelated-member",
        "module-namespace-ior-tuple-pair-unrelated-member",
        "module-namespace-ior-mutated-list-pair-alias",
        "module-namespace-ior-list-pair-mutated-importer",
        "module-namespace-ior-set-pair-unrelated-member",
        "module-namespace-ior-unresolved-key",
        "module-namespace-ior-unresolved-mapping",
    ],
)
def test_dynamic_import_tracks_imported_module_attribute_effects(
    module_mutation: str,
    runtime_should_fail: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = """import importlib

_EXPORTS = {"load_module": ("importlib", "import_module")}

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.mutator": "import importlib\n" + module_mutation + "\n",
            "polisyos.facade": facade_source,
            "polisyos.consumer": (
                "from . import mutator\n"
                "from .facade import load_module\n"
                'result = load_module("json")\n'
            ),
        },
    )
    (tmp_path / "external_updates.py").write_text(
        "updates = {'import_module': None}\nmember_name = 'import_module'\n",
        encoding="utf-8",
    )
    runtime = subprocess.run(
        [sys.executable, "-c", "import polisyos.consumer"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(tmp_path), str(tmp_path / "src"))),
            "EFFECT_MEMBER": "import_module",
        },
        capture_output=True,
        text=True,
    )
    if runtime_should_fail:
        assert runtime.returncode != 0  # noqa: S101
        assert "TypeError" in runtime.stderr  # noqa: S101
        with pytest.raises(
            preflight.DynamicImportCollectionError,
            match="dynamic importer binding is ambiguous or unresolved",
        ):
            preflight.collect_dynamic_imports()
    else:
        assert runtime.returncode == 0, runtime.stderr  # noqa: S101
        entries = preflight.collect_dynamic_imports()
        assert any(entry["call"] == "importlib.import_module" for entry in entries), entries  # noqa: S101


def test_dynamic_import_refuses_mutable_pair_sequence_namespace_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse mutable pair lists even when their current contents look harmless."""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.mutator": (
                "import importlib\n"
                'pairs = [["unrelated_member", None]]\n'
                "_module_namespace = vars(importlib)\n"
                "_module_namespace |= pairs\n"
            ),
            "polisyos.facade": (
                "import importlib\n"
                '_EXPORTS = {"load_module": ("importlib", "import_module")}\n'
                "def __getattr__(name):\n"
                "    if name not in _EXPORTS:\n"
                "        raise AttributeError(name)\n"
                "    module_name, attribute_name = _EXPORTS[name]\n"
                "    value = getattr(importlib.import_module(module_name), attribute_name)\n"
                "    globals()[name] = value\n"
                "    return value\n"
            ),
            "polisyos.consumer": (
                "from . import mutator\n"
                "from .facade import load_module\n"
                'result = load_module("json")\n'
            ),
        },
    )
    runtime = subprocess.run(
        [sys.executable, "-c", "import polisyos.consumer"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
    )
    assert runtime.returncode == 0, runtime.stderr  # noqa: S101
    with pytest.raises(
        preflight.DynamicImportCollectionError,
        match="dynamic importer binding is ambiguous or unresolved",
    ):
        preflight.collect_dynamic_imports()


@pytest.mark.parametrize(
    ("module_mutation", "runtime_should_fail"),
    [
        ("importlib.import_module = None", True),
        ("importlib.__dict__['unrelated_member'] = None", False),
    ],
    ids=("changed-imported-symbol", "unrelated-module-member"),
)
def test_dynamic_import_tracks_module_effects_through_from_import(
    module_mutation: str,
    runtime_should_fail: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade_source = """from importlib import import_module

_EXPORTS = {"load_module": ("importlib", "import_module")}

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.mutator": "import importlib\n" + module_mutation + "\n",
            "polisyos.facade": facade_source,
            "polisyos.consumer": (
                "from . import mutator\n"
                "from .facade import load_module\n"
                'result = load_module("json")\n'
            ),
        },
    )
    runtime = subprocess.run(
        [sys.executable, "-c", "import polisyos.consumer"],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        capture_output=True,
        text=True,
    )
    if runtime_should_fail:
        assert runtime.returncode != 0  # noqa: S101
        assert "TypeError" in runtime.stderr  # noqa: S101
        with pytest.raises(preflight.DynamicImportCollectionError):
            preflight.collect_dynamic_imports()
    else:
        assert runtime.returncode == 0, runtime.stderr  # noqa: S101
        entries = preflight.collect_dynamic_imports()
        assert any(entry["call"] == "importlib.import_module" for entry in entries), entries  # noqa: S101


@pytest.mark.parametrize(
    "namespace_argument",
    ["importlib", "vars(importlib)"],
    ids=("module-object-escape", "module-namespace-escape"),
)
def test_dynamic_import_refuses_opaque_module_namespace_escape(
    namespace_argument: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "external_sink.py").write_text(
        "def disable_importer(value):\n"
        "    if isinstance(value, dict):\n"
        "        value['import_module'] = None\n"
        "    else:\n"
        "        value.import_module = None\n",
        encoding="utf-8",
    )
    facade_source = """import importlib

_EXPORTS = {"load_module": ("importlib", "import_module")}

def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value
"""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.mutator": (
                "import importlib\n"
                "from external_sink import disable_importer\n"
                f"disable_importer({namespace_argument})\n"
            ),
            "polisyos.facade": facade_source,
            "polisyos.consumer": (
                "from . import mutator\n"
                "from .facade import load_module\n"
                'result = load_module("json")\n'
            ),
        },
    )
    runtime = subprocess.run(
        [sys.executable, "-c", "import polisyos.consumer"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(tmp_path), str(tmp_path / "src"))),
        },
        capture_output=True,
        text=True,
    )
    assert runtime.returncode != 0  # noqa: S101
    assert "TypeError" in runtime.stderr  # noqa: S101
    with pytest.raises(preflight.DynamicImportCollectionError):
        preflight.collect_dynamic_imports()


def test_dynamic_deferred_escaped_class_keeps_known_inventory_without_field_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nominal exception constructor is not a mutable field-summary authority."""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.refusal": """from importlib import import_module
from opaque_vendor import inspect_class

class RefusalError(ValueError):
    pass

inspect_class(RefusalError)

def refuse():
    raise RefusalError("declared_refusal")

def selected():
    return import_module("deferred_escaped_class_selected_target")
""",
        },
    )

    entries = preflight.collect_dynamic_imports()
    assert [entry["pattern"] for entry in entries] == ["deferred_escaped_class_selected_target"]

    identity_lookup = preflight._DynamicImportSourceBindings._source_class_identity_definition
    bridge_removal_calls = []

    def old_summary_proxy(source_bindings, source_name: str, **context):
        invalidated = source_name in source_bindings.invalidated_source_classes
        bridge_removal_calls.append(
            {"source_name": source_name, "summary_invalidated": invalidated}
        )
        if invalidated:
            return None
        return identity_lookup(source_bindings, source_name, **context)

    with monkeypatch.context() as removed:
        removed.setattr(
            preflight._DynamicImportSourceBindings,
            "_source_class_identity_definition",
            old_summary_proxy,
        )
        with pytest.raises(
            preflight.DynamicImportCollectionError,
            match="source-owned call target is neither a selected function nor a selected class",
        ) as removed_bridge:
            preflight.collect_dynamic_imports()

    assert any(
        call["source_name"] == "polisyos.refusal.RefusalError" and call["summary_invalidated"]
        for call in bridge_removal_calls
    )
    assert (
        preflight._DynamicImportSourceBindings._source_class_identity_definition is identity_lookup
    )
    restored_entries = preflight.collect_dynamic_imports()
    assert restored_entries == entries
    (tmp_path / "nominal-bridge-removal.json").write_text(
        json.dumps(
            {
                "positive_patterns": [entry["pattern"] for entry in entries],
                "removed_property": "nominal identity separated from mutable-summary validity",
                "removed_bridge_refusal": str(removed_bridge.value),
                "actual_lookup_calls": bridge_removal_calls,
                "identity_lookup_object_restored": True,
                "restored_patterns": [entry["pattern"] for entry in restored_entries],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    paths = preflight._dynamic_source_paths("src")
    context = preflight._dynamic_read_source_context(paths)
    bindings = preflight._DynamicImportSourceBindings(paths, source_context=context)
    source_module = "polisyos.refusal"
    identity = source_module + ".RefusalError"
    environment = bindings._module_environment(source_module, ())
    assert environment is not None
    bindings.invalidate_source_classes((identity,))
    assert (
        bindings._source_class_definition(
            identity,
            current_module=source_module,
            current_environment=environment,
            stack=(),
        )
        is None
    )
    assert (
        bindings._source_class_identity_definition(
            identity,
            current_module=source_module,
            current_environment=environment,
            stack=(),
        )
        is not None
    )


@pytest.mark.parametrize("changed_root", ["importlib", "selected_alias"])
@pytest.mark.parametrize(
    ("class_declarations", "escaped_class"),
    [
        ("class RefusalError: pass", "RefusalError"),
        ("class Parent: pass\nclass RefusalError(Parent): pass", "Parent"),
        (
            "class Parent: pass\nclass Middle(Parent): pass\nclass RefusalError(Middle): pass",
            "Parent",
        ),
        (
            "class Left: pass\nclass Right: pass\nclass RefusalError(Left, Right): pass",
            "Right",
        ),
        (
            "class Parent: pass\nclass Other: pass\n"
            "if uncertain:\n    Base = Parent\nelse:\n    Base = Other\n"
            "class RefusalError(Base): pass",
            "Parent",
        ),
    ],
    ids=["direct", "inherited", "transitive", "multiple", "joined-base"],
)
def test_dynamic_deferred_escaped_class_refuses_changed_importer_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_root: str,
    class_declarations: str,
    escaped_class: str,
) -> None:
    """A changed root refuses with both the full path and its independent fallback."""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.refusal": """import importlib
from importlib import import_module as selected_alias
from opaque_vendor import inspect_class

@@DECLARATIONS@@

inspect_class(@@ESCAPED@@)

def refuse():
    raise RefusalError("declared_refusal")

@@ROOT@@ = inspect_class
""".replace("@@ROOT@@", changed_root)
            .replace("@@DECLARATIONS@@", class_declarations)
            .replace("@@ESCAPED@@", escaped_class),
        },
    )

    with pytest.raises(
        preflight.DynamicImportCollectionError, match="proven importer rebind"
    ) as original_refusal:
        preflight.collect_dynamic_imports()

    with monkeypatch.context() as removed:
        removed.setattr(
            preflight._DynamicImportSourceScanner,
            "_deferred_scope_importer_names",
            lambda _self, _deferred, _environment: frozenset(),
        )
        with pytest.raises(
            preflight.DynamicImportCollectionError,
            match="unmodeled call has an unproven module-time dynamic-import namespace",
        ) as fallback_refusal:
            preflight.collect_dynamic_imports()
        assert f"namespace ({changed_root});" in str(fallback_refusal.value)

    with pytest.raises(
        preflight.DynamicImportCollectionError, match="proven importer rebind"
    ) as restored_refusal:
        preflight.collect_dynamic_imports()
    (tmp_path / "redundant-root-guards.json").write_text(
        json.dumps(
            {
                "changed_root": changed_root,
                "escaped_class": escaped_class,
                "original_refusal": str(original_refusal.value),
                "removed_helper": "_deferred_scope_importer_names",
                "independent_guard_refusal": str(fallback_refusal.value),
                "restored_refusal": str(restored_refusal.value),
                "single_helper_removal_is_not_whole_property_removal": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_dynamic_deferred_unescaped_class_keeps_precise_unrelated_root_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source-known constructor need not read every unrelated importer alias."""
    _dynamic_import_internal_modules_fixture(
        tmp_path,
        monkeypatch,
        {
            "polisyos.__init__": "",
            "polisyos.refusal": """from importlib import import_module as selected_alias
from opaque_vendor import inspect_class

class RefusalError:
    pass

def refuse():
    raise RefusalError("declared_refusal")

selected_alias = inspect_class
""",
        },
    )

    assert preflight.collect_dynamic_imports() == []
