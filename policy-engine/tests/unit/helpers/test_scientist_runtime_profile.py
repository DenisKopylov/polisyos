"""Behavioral source-origin regression tests; no Scientist/backend discovery is run."""

from __future__ import annotations

import hashlib
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest
from _helpers.scientist_runtime_profile import collect_loaded_module_sources


def _module(name: str, filename: str | None, spec_origin: str | None = None) -> ModuleType:
    module = ModuleType(name)
    if filename is not None:
        module.__file__ = filename
    module.__spec__ = ModuleSpec(name, loader=None, origin=spec_origin)
    return module


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    (tmp_path / "policy-engine/src/polisyos").mkdir(parents=True)
    (tmp_path / "policy-engine/tests").mkdir()
    return tmp_path


def test_relative_external_origin_never_becomes_checkout_source(source_root, monkeypatch):
    cwd = source_root / "policy-engine"
    (cwd / "_classes.py").write_text("this is a decoy, not the imported module\n")
    monkeypatch.chdir(cwd)
    result = collect_loaded_module_sources(
        {"external.virtual": _module("external.virtual", "_classes.py")}, repo_root=source_root
    )
    assert result["loaded_project_python"] == []
    assert result["product_source_origin_errors"] == []
    row = result["not_established_nonproduct_origins"][0]
    assert (row["module"], row["raw_file"], row["status"]) == (
        "external.virtual",
        "_classes.py",
        "not_established",
    )
    candidate = row["origin_candidates"][1]
    assert candidate["is_absolute"] is False and candidate["status"] == "not_established"


def test_real_spec_origin_precedes_a_relative_or_conflicting_file(source_root, tmp_path):
    installed = tmp_path / "external-install" / "implementation.py"
    installed.parent.mkdir()
    installed.write_text("installed = True\n")
    decoy = source_root / "policy-engine/tests/decoy.py"
    decoy.write_text("decoy = True\n")
    result = collect_loaded_module_sources(
        {
            "external.relative": _module("external.relative", "_classes.py", str(installed)),
            "external.conflict": _module("external.conflict", str(decoy), str(installed)),
        },
        repo_root=source_root,
    )
    assert result["loaded_project_python"] == []
    assert result["external_regular_file_module_count"] == 2
    assert result["not_established_nonproduct_origins"][0]["module"] == "external.relative"


def test_absolute_product_and_test_sources_are_content_bound(source_root):
    product = source_root / "policy-engine/src/polisyos/example.py"
    helper = source_root / "policy-engine/tests/helper.py"
    product.write_text("value = 1\n")
    helper.write_text("value = 2\n")
    result = collect_loaded_module_sources(
        {
            "polisyos.example": _module("polisyos.example", str(product), str(product)),
            "local_helper": _module("local_helper", str(helper)),
        },
        repo_root=source_root,
    )
    assert not result["product_source_origin_errors"]
    assert {row["path"]: row["sha256"] for row in result["loaded_project_python"]} == {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (product, helper)
    }
    assert {row["origin_basis"] for row in result["loaded_project_python"]} == {
        "absolute_file",
        "module_spec_origin",
    }


@pytest.mark.parametrize("origin", [None, "_classes.py", "<virtual>", "missing-absolute"])
def test_missing_or_virtual_product_origin_is_not_silently_skipped(source_root, origin):
    if origin == "missing-absolute":
        origin = str(source_root / "policy-engine/src/polisyos/missing.py")
    result = collect_loaded_module_sources(
        {"polisyos.missing": _module("polisyos.missing", origin)}, repo_root=source_root
    )
    assert result["loaded_project_python"] == []
    assert result["product_source_origin_errors"][0]["module"] == "polisyos.missing"
    assert result["product_source_origin_errors"][0]["status"] == "not_established"


def test_foreign_conflicting_and_symlink_escape_product_origins_refuse(source_root, tmp_path):
    bound = source_root / "policy-engine/src/polisyos"
    first, second = bound / "first.py", bound / "second.py"
    first.write_text("first = True\n")
    second.write_text("second = True\n")
    foreign = tmp_path / "outside.py"
    foreign.write_text("outside = True\n")
    escape = bound / "escape.py"
    escape.symlink_to(foreign)
    result = collect_loaded_module_sources(
        {
            "polisyos.foreign": _module("polisyos.foreign", str(foreign)),
            "polisyos.conflict": _module("polisyos.conflict", str(first), str(second)),
            "polisyos.escape": _module("polisyos.escape", str(escape)),
        },
        repo_root=source_root,
    )
    assert result["loaded_project_python"] == []
    assert {row["module"] for row in result["product_source_origin_errors"]} == {
        "polisyos.foreign",
        "polisyos.conflict",
        "polisyos.escape",
    }


def test_installed_product_root_must_be_explicit_and_namespace_paths_bounded(source_root, tmp_path):
    installation = tmp_path / "site-packages/polisyos"
    installation.mkdir(parents=True)
    implementation = installation / "installed.py"
    implementation.write_text("installed = True\n")
    namespace = _module("polisyos.namespace", None)
    namespace.__spec__.submodule_search_locations = [str(installation)]
    modules = {
        "polisyos.installed": _module("polisyos.installed", str(implementation)),
        "polisyos.namespace": namespace,
    }
    refused = collect_loaded_module_sources(modules, repo_root=source_root)
    assert len(refused["product_source_origin_errors"]) == 2
    admitted = collect_loaded_module_sources(
        modules, repo_root=source_root, product_roots=(installation,)
    )
    assert admitted["product_source_origin_errors"] == []
    assert admitted["loaded_project_python"][0]["path"] == str(implementation)
    assert admitted["bounded_product_namespaces"][0]["search_roots"] == [str(installation)]


def test_unknown_product_file_kind_and_empty_admitted_roots_refuse(source_root):
    product = source_root / "policy-engine/src/polisyos/not_code.txt"
    product.write_text("shape is not source evidence\n")
    modules = {"polisyos.unknown": _module("polisyos.unknown", str(product))}
    result = collect_loaded_module_sources(modules, repo_root=source_root)
    assert result["product_source_origin_errors"][0]["reason"] == "product_origin_kind_unknown"
    empty = collect_loaded_module_sources(modules, repo_root=source_root, product_roots=())
    assert empty["product_source_origin_errors"]


def test_external_virtual_origins_are_named_without_becoming_product_errors(source_root):
    result = collect_loaded_module_sources(
        {
            "external.frozen": _module("external.frozen", None, "frozen"),
            "external.missing": _module("external.missing", str(source_root / "absent.py")),
        },
        repo_root=source_root,
    )
    assert result["loaded_project_python"] == []
    assert result["product_source_origin_errors"] == []
    assert {row["module"] for row in result["not_established_nonproduct_origins"]} == {
        "external.frozen",
        "external.missing",
    }


def test_opaque_module_metadata_remains_named_and_product_is_refused(source_root):
    class OpaqueModule:
        @property
        def __spec__(self):
            raise RuntimeError("origin metadata unavailable")

    result = collect_loaded_module_sources(
        {"external.opaque": OpaqueModule(), "polisyos.opaque": OpaqueModule()},
        repo_root=source_root,
    )
    assert result["product_source_origin_errors"][0]["module"] == "polisyos.opaque"
    assert result["not_established_nonproduct_origins"][0]["module"] == "external.opaque"
    assert result["enumerated_module_count"] == 2


def test_admitted_product_roots_cannot_be_relative_or_regular_files(source_root):
    with pytest.raises(ValueError, match="must_be_absolute"):
        collect_loaded_module_sources({}, repo_root=source_root, product_roots=(Path("polisyos"),))
    file = source_root / "not-a-directory.py"
    file.write_text("value = True\n")
    with pytest.raises(ValueError, match="must_be_directory"):
        collect_loaded_module_sources({}, repo_root=source_root, product_roots=(file,))


@pytest.mark.parametrize("missing_field", ["spec", "file"])
def test_missing_absolute_product_claim_cannot_be_erased_by_valid_fallback(
    source_root, missing_field
):
    valid = source_root / "policy-engine/src/polisyos/valid.py"
    valid.write_text("actual = True\n")
    missing = source_root / "policy-engine/src/polisyos/missing.py"
    module = _module(
        "polisyos.example",
        str(valid if missing_field == "spec" else missing),
        str(missing if missing_field == "spec" else valid),
    )
    result = collect_loaded_module_sources({"polisyos.example": module}, repo_root=source_root)
    assert result["loaded_project_python"] == []
    row = result["product_source_origin_errors"][0]
    assert row["reason"] == "product_origin_claim_invalid"
    assert any(
        c["is_absolute"] and c["status"] == "not_established" for c in row["origin_candidates"]
    )


@pytest.mark.parametrize("relative_root", ["src", "tests", "tools"])
def test_declared_absolute_project_source_cannot_become_external_unknown(
    source_root, relative_root
):
    missing = source_root / "policy-engine" / relative_root / "missing.py"
    external = source_root / "external.py"
    external.write_text("external = True\n")
    result = collect_loaded_module_sources(
        {"local.helper": _module("local.helper", str(external), str(missing))},
        repo_root=source_root,
    )
    assert result["loaded_project_python"] == []
    row = result["project_source_origin_errors"][0]
    assert row["module"] == "local.helper" and row["status"] == "not_established"
    assert row["origin_candidates"][0]["lexical_project_claim"] is True
    assert result["not_established_nonproduct_origins"] == []


def test_unreadable_required_origin_preserves_scope_before_fallback(source_root, monkeypatch):
    claimed = source_root / "policy-engine/tests/claimed.py"
    claimed.write_text("value = True\n")
    fallback = source_root / "fallback.py"
    fallback.write_text("fallback = True\n")
    original = Path.resolve

    def denied(path, *args, **kwargs):
        if path == claimed:
            raise PermissionError("controlled origin denial")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", denied)
    result = collect_loaded_module_sources(
        {"local.helper": _module("local.helper", str(fallback), str(claimed))},
        repo_root=source_root,
    )
    candidate = result["project_source_origin_errors"][0]["origin_candidates"][0]
    assert candidate["lexical_project_claim"] is True
    assert candidate["error_type"] == "PermissionError"
    assert result["loaded_project_python"] == []


def test_opaque_metadata_cannot_erase_a_known_project_claim(source_root):
    local = source_root / "policy-engine/tests/local.py"
    local.write_text("local = True\n")

    class OpaqueLocal:
        __file__ = str(local)

        @property
        def __spec__(self):
            raise RuntimeError("controlled metadata error")

    result = collect_loaded_module_sources({"local.helper": OpaqueLocal()}, repo_root=source_root)
    assert result["project_source_origin_errors"][0]["module"] == "local.helper"
    assert result["not_established_nonproduct_origins"] == []


@pytest.mark.parametrize("unresolved", ["relative.py", "frozen", "<virtual>"])
def test_present_unresolved_product_alternative_is_not_ignored(source_root, unresolved):
    valid = source_root / "policy-engine/src/polisyos/valid.py"
    valid.write_text("value = True\n")
    result = collect_loaded_module_sources(
        {"polisyos.example": _module("polisyos.example", str(valid), unresolved)},
        repo_root=source_root,
    )
    assert result["loaded_project_python"] == []
    assert result["product_source_origin_errors"][0]["reason"] == "product_origin_claim_invalid"


@pytest.mark.parametrize("scope", ["product", "project"])
def test_physical_origin_keeps_symlink_parent_operand_instead_of_local_decoy(
    source_root, monkeypatch, scope
):
    bound = source_root / (
        "policy-engine/src/polisyos" if scope == "product" else "policy-engine/tests"
    )
    local = bound / "a"
    local.mkdir()
    outside = source_root / "outside"
    (outside / "subdir").mkdir(parents=True)
    (local / "bridge").symlink_to(outside / "subdir", target_is_directory=True)
    decoy = local / "candidate.py"
    decoy.write_text("decoy = True\n")
    actual = outside / "candidate.py"
    actual.write_text("outside = True\n")
    raw = local / "bridge" / ".." / "candidate.py"
    # Actual OS opening is the independent oracle for the raw operand's meaning.
    assert raw.read_text() == "outside = True\n"
    name = "polisyos.example" if scope == "product" else "local.helper"
    touched = []
    original = Path.read_bytes

    def tracked(path):
        touched.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", tracked)
    result = collect_loaded_module_sources(
        {name: _module(name, str(raw), str(raw))}, repo_root=source_root
    )
    errors = result[
        "product_source_origin_errors" if scope == "product" else "project_source_origin_errors"
    ]
    assert errors and result["loaded_project_python"] == []
    assert all(row["resolved_path"] == str(actual) for row in errors[0]["origin_candidates"])
    assert all(row["lexical_project_claim"] for row in errors[0]["origin_candidates"])
    assert all(not row["resolved_project_scope"] for row in errors[0]["origin_candidates"])
    assert decoy not in touched and actual not in touched
