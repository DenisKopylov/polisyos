from __future__ import annotations

from pathlib import Path

from tools.quality.validation import check_extension_examples

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
        "polisyos.internal_plugins: internal_only exception requires "
        "internal_only_review_date"
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
    entry_points = pyproject_entry_points or """
[project.entry-points."polisyos.uncovered_plugins"]

[project.entry-points."polisyos.internal_plugins"]
"""
    (tmp_path / "pyproject.toml").write_text(
        f"""
[project]
name = "policy-engine-test"
version = "0.0.0"

{entry_points}
""",
        encoding="utf-8",
    )
