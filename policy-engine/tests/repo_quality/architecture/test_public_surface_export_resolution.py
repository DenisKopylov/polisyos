"""Actual export reader controls, independent of runtime authority or backend fit."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from tools.devx.architecture import guardrails


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    source = tmp_path / "src"
    package = source / "polisyos" / "fixture"
    package.mkdir(parents=True)
    monkeypatch.setattr(guardrails, "SRC_ROOT", source)
    monkeypatch.setattr(guardrails, "REPO_ROOT", tmp_path)
    facade = package / "__init__.py"
    mapping = package / "exports.py"
    facade.write_text(
        "from .exports import PUBLIC_NAMES as names\n__all__ = sorted(names)\n",
        encoding="utf-8",
    )
    mapping.write_text('PUBLIC_NAMES = {"Old": ("owner", "Old")}\n', encoding="utf-8")
    return facade, mapping


def test_actual_analytics_mapping_is_not_reported_as_empty() -> None:
    from polisyos.ir import analytics
    from polisyos.ir.api import ANALYTICS_FACADE_EXPORTS

    result = guardrails._entrypoint_inventory("polisyos.ir.analytics")
    assert result.exports == tuple(analytics.__all__) == tuple(sorted(ANALYTICS_FACADE_EXPORTS))
    inputs = result.export_resolution["inputs"]
    paths = {row["path"] for row in inputs if row["operation"] == "read_bytes"}
    assert paths == {
        "src/polisyos/ir/api.py",
        "src/polisyos/ir/analytics/__init__.py",
    }
    for row in inputs:
        if row["operation"] == "read_bytes":
            raw = (guardrails.REPO_ROOT / row["path"]).read_bytes()
            assert row["bytes"] == len(raw)
            assert row["sha256"] == hashlib.sha256(raw).hexdigest()


def test_reader_follows_owner_mapping_change_without_facade_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade, mapping = _fixture(tmp_path, monkeypatch)
    facade_before = facade.read_bytes()
    first = guardrails._entrypoint_inventory("polisyos.fixture")
    mapping.write_text('PUBLIC_NAMES = {"New": None, "Old": None}\n', encoding="utf-8")
    second = guardrails._entrypoint_inventory("polisyos.fixture")
    assert facade.read_bytes() == facade_before
    assert first.exports == ("Old",)
    assert second.exports == ("New", "Old")
    assert first.export_resolution != second.export_resolution
    # Real serialization observes the changed dependency, not a facade marker.
    policy = guardrails.PackagePolicy(
        module="polisyos.fixture",
        classification="public_experimental",
        facade_mode="eager_exports",
        owner="test-owner",
        readme=facade,
        reference_doc=facade,
        supported_entrypoints=("polisyos.fixture",),
        major_subsystem=False,
        notes="fixture",
    )
    rendered = json.loads(
        guardrails.render_public_surface_json(guardrails.build_public_surface_inventory([policy]))
    )
    assert rendered["packages"][0]["entrypoints"][0]["exports"] == ["New", "Old"]


def test_outside_selector_is_disclosed_and_does_not_become_export(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    outside = mapping.with_name("unselected.py")
    outside.write_text('PUBLIC_NAMES = {"Outside": None}\nraise RuntimeError("never run")\n')
    result = guardrails._entrypoint_inventory("polisyos.fixture")
    assert result.exports == ("Old",)
    assert all(
        row["path"] != str(outside.relative_to(tmp_path))
        for row in result.export_resolution["inputs"]
    )
    assert "No module execution or runtime dispatch" in result.export_resolution["selector"]
    assert result.export_resolution["unresolved_by_construction"]


@pytest.mark.parametrize("problem", ["missing", "unreadable", "cycle", "computed", "mutated", "subscript", "conditional"])
def test_unresolved_mapping_never_becomes_empty_manifest(
    problem: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    if problem == "missing":
        mapping.rename(mapping.with_suffix(".retained"))
        error = FileNotFoundError
    elif problem == "unreadable":
        original = guardrails.admitted_read_bytes

        def read(path, root):
            if path == mapping:
                raise PermissionError("actual reader refused fixture")
            return original(path, root)

        monkeypatch.setattr(guardrails, "admitted_read_bytes", read)
        error = PermissionError
    elif problem == "cycle":
        mapping.write_text("from . import __all__ as PUBLIC_NAMES\n")
        error = ValueError
    elif problem == "computed":
        mapping.write_text("PUBLIC_NAMES = choose_runtime_exports()\n")
        error = ValueError
    elif problem == "subscript":
        mapping.write_text('PUBLIC_NAMES = {"Old": None}\nPUBLIC_NAMES["New"] = None\n')
        error = ValueError
    elif problem == "conditional":
        mapping.write_text('if backend_available():\n    PUBLIC_NAMES = {"Old": None}\n')
        error = ValueError
    else:
        mapping.write_text('PUBLIC_NAMES = {"Old": None}\nPUBLIC_NAMES.update({"New": None})\n')
        error = ValueError
    with pytest.raises(error):
        guardrails._entrypoint_inventory("polisyos.fixture")


def test_static_literal_mapping_is_read_without_executing_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, mapping = _fixture(tmp_path, monkeypatch)
    mapping.write_text(
        'raise RuntimeError("module execution forbidden")\n'
        'BASE = {"A": unknown_runtime_owner()}\n'
        'PUBLIC_NAMES = {**BASE, "B": object()}\n',
    )
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("A", "B")


def test_local_names_and_sequence_concat_share_same_reader() -> None:
    tree = ast.parse('M = {"B": None, "A": None}\nN = sorted(M)\n__all__ = tuple(N) + ("C",)\n')
    assert guardrails._extract_exports(tree) == ("A", "B", "C")


def test_removed_import_resolution_keeps_facade_markers_but_original_oracle_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _ = _fixture(tmp_path, monkeypatch)
    original = guardrails._extract_exports
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)
    monkeypatch.setattr(guardrails, "_extract_exports", lambda tree, source=None: ())
    assert guardrails._entrypoint_inventory("polisyos.fixture").has___getattr__ is False
    with pytest.raises(AssertionError):
        assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)
    monkeypatch.setattr(guardrails, "_extract_exports", original)
    assert guardrails._entrypoint_inventory("polisyos.fixture").exports == ("Old",)


def test_conditional_all_is_unresolved_instead_of_absent() -> None:
    with pytest.raises(ValueError, match="conditional export"):
        guardrails._extract_exports(ast.parse('if runtime():\n    __all__ = ["A"]\n'))
