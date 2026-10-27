from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from tools.quality.validation import check_extension_examples, extension_example_build_tools

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase1_6_public_entry_point_groups_have_examples_or_internal_exception() -> None:
    errors = check_extension_examples.validate_pyproject(
        REPO_ROOT,
        check_extension_examples.EXAMPLES,
    )

    assert errors == []


def test_phase1_6_new_public_entry_point_group_requires_example(tmp_path: Path) -> None:
    _write_extension_contract(
        tmp_path,
        """
[[extension_point]]
name = "polisyos.uncovered_plugins"
entry_point_group = "polisyos.uncovered_plugins"
component_kind = "uncovered_plugin"
contract = "polisyos.example.Plugin"
contract_version = "1.0"
    owner = "team-example"
    """,
        pyproject_entry_points="""
[project.entry-points."polisyos.uncovered_plugins"]
""",
    )

    errors = check_extension_examples.validate_pyproject(tmp_path, ())

    assert errors == [
        "polisyos.uncovered_plugins: public entry-point group must declare "
        "example_package under examples/extensions/** or internal_only = true"
    ]


def test_phase1_6_pyproject_only_entry_point_group_requires_contract(
    tmp_path: Path,
) -> None:
    _write_extension_contract(
        tmp_path,
        """
""",
        pyproject_entry_points="""
[project.entry-points."polisyos.pyproject_only_plugins"]
"demo" = "example_plugin:factory"
""",
    )

    errors = check_extension_examples.validate_pyproject(tmp_path, ())

    assert errors == [
        "polisyos.pyproject_only_plugins: entry-point group in pyproject.toml must "
        "be declared in architecture/extension_points.toml"
    ]


def test_phase1_6_internal_only_exception_requires_review_date(tmp_path: Path) -> None:
    _write_extension_contract(
        tmp_path,
        """
[[extension_point]]
name = "polisyos.internal_plugins"
entry_point_group = "polisyos.internal_plugins"
component_kind = "internal_plugin"
contract = "polisyos.example.InternalPlugin"
contract_version = "1.0"
owner = "team-example"
internal_only = true
""",
        pyproject_entry_points="""
[project.entry-points."polisyos.internal_plugins"]
""",
    )

    errors = check_extension_examples.validate_pyproject(tmp_path, ())

    assert errors == [
        "polisyos.internal_plugins: internal_only exception requires internal_only_review_date"
    ]


def _write_extension_contract(
    tmp_path: Path,
    extension_points_toml: str,
    *,
    pyproject_entry_points: str | None = None,
) -> None:
    (tmp_path / "architecture").mkdir()
    (tmp_path / "architecture" / "extension_points.toml").write_text(
        extension_points_toml,
        encoding="utf-8",
    )
    entry_points = (
        pyproject_entry_points
        or """
[project.entry-points."polisyos.uncovered_plugins"]

[project.entry-points."polisyos.internal_plugins"]
"""
    )
    (tmp_path / "pyproject.toml").write_text(
        f"""
[project]
name = "policy-engine-test"
version = "0.0.0"

{entry_points}
""",
        encoding="utf-8",
    )


def test_phase1_6_owner_install_modes_route_wheel_and_keep_editable_examples(
    monkeypatch,
) -> None:
    events: list[tuple[str, object]] = []

    def build_wheel(repo_root: Path, example_path: str) -> dict[str, object]:
        events.append(("wheel", (repo_root.resolve(), example_path)))
        return {"status": "test-double", "wheel_identity": {"filename": "example.whl", "files": {}}}

    def install_editable(example_path: Path) -> None:
        events.append(("editable", example_path.resolve()))

    monkeypatch.setattr(
        extension_example_build_tools,
        "build_and_install_example",
        build_wheel,
    )
    monkeypatch.setattr(check_extension_examples, "_install_editable", install_editable)

    selected = check_extension_examples.EXAMPLES[:2]
    receipts = check_extension_examples.install_examples(REPO_ROOT, selected)

    assert receipts == {"polisyos.fabric_connectors": {"filename": "example.whl", "files": {}}}
    assert events == [
        ("wheel", (REPO_ROOT.resolve(), selected[0].path)),
        ("editable", (REPO_ROOT / selected[1].path).resolve()),
    ]


def test_phase1_6_unknown_owner_install_mode_fails_closed(tmp_path: Path) -> None:
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    example = check_extension_examples.EXAMPLES[0]
    (architecture / "extension_points.toml").write_text(
        '[defaults]\nexample_install_mode = "editable"\n\n'
        "[[extension_point]]\n"
        f'name = "{example.group}"\n'
        f'entry_point_group = "{example.group}"\n'
        f'example_package = "{example.path}"\n'
        'example_install_mode = "unknown"\n'
        'example_smoke_command = "python -m pip install -e example"\n',
        encoding="utf-8",
    )

    modes, errors = check_extension_examples._resolve_example_install_modes(tmp_path, (example,))

    assert modes == {}
    assert errors == [f"{example.group}: missing or unsupported example_install_mode"]


def test_component_discovery_generated_program_verifies_nonempty_wheel_identity(
    tmp_path: Path, monkeypatch
) -> None:
    example = check_extension_examples.EXAMPLES[0]
    wheel_identity = {
        "filename": "fabric_connector-1.0.0-py3-none-any.whl",
        "wheel_sha256": "a" * 64,
        "files": {"fabric_connector/__init__.py": {"sha256": "b" * 64, "bytes": 1}},
    }
    binding_payload = {"wheel_sha256": "b" * 64, "provider": "fixture"}
    verifier_calls: list[tuple[object, object, str, str]] = []
    discovery_calls: list[tuple[list[str], bool]] = []
    probe_calls: list[str] = []

    class _Binding:
        def as_dict(self) -> dict[str, object]:
            return binding_payload

    created = SimpleNamespace(
        fetch_preview=lambda: probe_calls.append("fetch_preview") or [{"value": 42}]
    )
    item = SimpleNamespace(
        metadata=SimpleNamespace(
            component_id=example.component_id,
            kind=SimpleNamespace(value=example.kind),
            abi_targets={example.abi_key},
        ),
        source=SimpleNamespace(
            source_type="entry_point",
            group=example.group,
            entry_point=example.entry_point,
            provider_origin_binding=_Binding(),
        ),
        component=SimpleNamespace(create=lambda: created),
    )

    def _module(name: str, *, package: bool = False) -> ModuleType:
        module = ModuleType(name)
        if package:
            module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
        return module

    polisyos = _module("polisyos", package=True)
    core = _module("polisyos.core", package=True)
    components = _module("polisyos.core.components")
    scientist = _module("polisyos.scientist", package=True)
    orchestration = _module("polisyos.scientist.orchestration", package=True)
    engine = _module("polisyos.scientist.orchestration.engine", package=True)
    state = _module("polisyos.scientist.orchestration.engine.state")
    polisyos.core = core
    core.components = components
    polisyos.scientist = scientist
    scientist.orchestration = orchestration
    orchestration.engine = engine
    engine.state = state
    components.discover_components = lambda **kwargs: (
        discovery_calls.append((kwargs["groups"], kwargs["include_dev_scan"]))
        or SimpleNamespace(errors=[], components=[item])
    )
    state.ExperimentState = type("ExperimentState", (), {})

    tools = _module("tools", package=True)
    quality = _module("tools.quality", package=True)
    validation = _module("tools.quality.validation", package=True)
    helper = _module("tools.quality.validation.extension_example_build_tools")
    tools.quality = quality
    quality.validation = validation

    def _verify(
        identity: object,
        provider_binding: object,
        *,
        group: str,
        entry_point_name: str,
    ) -> None:
        verifier_calls.append((identity, provider_binding, group, entry_point_name))

    helper._verify_installed_wheel_identity = _verify
    validation.extension_example_build_tools = helper

    def _run_generated(argv: list[str], *, check: bool) -> SimpleNamespace:
        assert check is True
        assert argv[:2] == [sys.executable, "-c"]
        generated_path = tmp_path / "component-discovery.py"
        generated_path.write_text(argv[2], encoding="utf-8")
        old_argv = sys.argv
        monkeypatch.setattr(sys, "argv", ["-c", argv[3]])
        try:
            runpy.run_path(generated_path, run_name="__main__")
        finally:
            monkeypatch.setattr(sys, "argv", old_argv)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(check_extension_examples.subprocess, "run", _run_generated)
    check_extension_examples.verify_discovery(
        (example,),
        {example.group: wheel_identity},
        repo_root=REPO_ROOT,
    )

    assert discovery_calls == [([example.group], False)]
    assert verifier_calls == [(wheel_identity, binding_payload, example.group, example.entry_point)]
    assert probe_calls == ["fetch_preview"]


def test_wheel_discovery_refuses_without_same_run_artifact_identity() -> None:
    with pytest.raises(RuntimeError, match="exact wheel identities from this install run"):
        check_extension_examples.verify_discovery(
            (check_extension_examples.EXAMPLES[0],), {}, repo_root=REPO_ROOT
        )


def test_selected_example_validation_retains_global_owner_coverage() -> None:
    selected = (check_extension_examples.EXAMPLES[0],)

    assert (
        check_extension_examples.validate_pyproject(
            REPO_ROOT, selected, coverage_examples=check_extension_examples.EXAMPLES
        )
        == []
    )


@pytest.mark.parametrize("owner_count", [0, 2])
def test_selected_example_install_mode_requires_exactly_one_owner(
    tmp_path: Path, owner_count: int
) -> None:
    example = check_extension_examples.EXAMPLES[0]
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    rows = "".join(
        "[[extension_point]]\n"
        f'name = "{example.group}"\n'
        f'entry_point_group = "{example.group}"\n'
        f'example_package = "{example.path}"\n'
        'example_smoke_command = "python -m pip install -e example"\n'
        for _ in range(owner_count)
    )
    (architecture / "extension_points.toml").write_text(
        '[defaults]\nexample_install_mode = "editable"\n\n' + rows,
        encoding="utf-8",
    )

    modes, errors = check_extension_examples._resolve_example_install_modes(tmp_path, (example,))

    assert modes == {}
    assert errors == [f"{example.group}: expected exactly one install-policy owner row"]


def _write_complete_extension_example_registry(
    root: Path,
    *,
    duplicate_group: str | None = None,
    omitted_group: str | None = None,
    package_overrides: dict[str, str] | None = None,
) -> None:
    package_overrides = package_overrides or {}
    architecture = root / "architecture"
    architecture.mkdir()
    rows: list[str] = []
    for example in check_extension_examples.EXAMPLES:
        if example.group == omitted_group:
            continue
        package = package_overrides.get(example.group, example.path)
        row = (
            "[[extension_point]]\n"
            f'name = "{example.group}"\n'
            f'entry_point_group = "{example.group}"\n'
            f'example_package = "{package}"\n'
            'example_install_mode = "editable"\n'
            f'example_smoke_command = "python -m pip install -e {example.path}"\n\n'
        )
        rows.append(row)
        if example.group == duplicate_group:
            rows.append(row)
    (architecture / "extension_points.toml").write_text(
        '[defaults]\nexample_install_mode = "editable"\n\n' + "".join(rows),
        encoding="utf-8",
    )
    entry_point_tables = "".join(
        f'[project.entry-points."{example.group}"]\n'
        for example in check_extension_examples.EXAMPLES
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "registry-fixture"\nversion = "0.0.0"\n\n' + entry_point_tables,
        encoding="utf-8",
    )
    selected = check_extension_examples.EXAMPLES[0]
    package_root = root / selected.path
    (package_root / "tests").mkdir(parents=True)
    (package_root / "README.md").write_text("fixture\n", encoding="utf-8")
    (package_root / "tests" / "test_smoke.py").write_text(
        "def test_smoke():\n    assert True\n", encoding="utf-8"
    )
    (package_root / "pyproject.toml").write_text(
        '[project]\nname = "selected-example"\nversion = "0.0.0"\n\n'
        f'[project.entry-points."{selected.group}"]\n'
        f'"{selected.entry_point}" = "fixture:factory"\n',
        encoding="utf-8",
    )


def test_selected_example_census_rejects_duplicate_unselected_owner(tmp_path: Path) -> None:
    selected = check_extension_examples.EXAMPLES[0]
    unselected = check_extension_examples.EXAMPLES[1]
    _write_complete_extension_example_registry(tmp_path, duplicate_group=unselected.group)

    errors = check_extension_examples.validate_pyproject(
        tmp_path, (selected,), coverage_examples=check_extension_examples.EXAMPLES
    )

    assert any(
        error.startswith(f"{unselected.group}: expected exactly one owner row") for error in errors
    )


def test_selected_example_census_rejects_missing_unselected_owner(tmp_path: Path) -> None:
    selected = check_extension_examples.EXAMPLES[0]
    unselected = check_extension_examples.EXAMPLES[1]
    _write_complete_extension_example_registry(tmp_path, omitted_group=unselected.group)

    errors = check_extension_examples.validate_pyproject(
        tmp_path, (selected,), coverage_examples=check_extension_examples.EXAMPLES
    )

    assert any(
        error.startswith(f"{unselected.group}: expected exactly one owner row") for error in errors
    )


def test_selected_example_census_rejects_known_package_paths_swapped_between_groups(
    tmp_path: Path,
) -> None:
    selected = check_extension_examples.EXAMPLES[0]
    left, right = check_extension_examples.EXAMPLES[1:3]
    _write_complete_extension_example_registry(
        tmp_path,
        package_overrides={
            left.group: right.path,
            right.group: left.path,
        },
    )

    errors = check_extension_examples.validate_pyproject(
        tmp_path, (selected,), coverage_examples=check_extension_examples.EXAMPLES
    )

    assert any(
        error
        == f"{left.group}: example_package {right.path} does not match checker path {left.path}"
        for error in errors
    )
    assert any(
        error
        == f"{right.group}: example_package {left.path} does not match checker path {right.path}"
        for error in errors
    )
