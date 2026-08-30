from __future__ import annotations

import ast
import datetime
import json
import keyword
import textwrap
from pathlib import Path

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from tools.quality.lint import collect_arch_metrics, lint_imports


def _write_policy(path: Path, src_root: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            [policy]
            version = "1.0"
            internal_prefix = "polisyos"
            src_root = "{src_root.as_posix()}"

            [roots]
            known = ["ir", "foundry"]

            [internal.allow]
            ir = []
            foundry = ["ir"]

            [external.allow]
            ir = []
            foundry = []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _write_narrowed_policy(path: Path, src_root: Path) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            [policy]
            version = "2"
            contract_role = "enforced_direction_matrix"
            package_boundaries = "boundaries.toml"
            internal_prefix = "polisyos"
            src_root = "{src_root.as_posix()}"

            [roots]
            known = ["fabric", "data_forge"]

            [internal.allow]
            fabric = ["fabric", "data_forge"]
            data_forge = ["data_forge"]

            [external.allow]
            fabric = []
            data_forge = []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (path.parent / "boundaries.toml").write_text(
        textwrap.dedent(
            """
            [package_boundaries]
            version = 2
            contract_role = "ownership_and_narrowing_register"

            [[package]]
            module = "polisyos.fabric"
            owner = "team-fabric"
            public_facade = "polisyos.fabric"
            allowed_dependencies = ["polisyos.data_forge.read_api"]
            forbidden_dependencies = ["polisyos.data_forge.kernel"]

            [[package]]
            module = "polisyos.data_forge"
            owner = "team-data-forge"
            public_facade = "polisyos.data_forge"
            allowed_dependencies = []
            forbidden_dependencies = []
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _run_narrowed_import_case(tmp_path: Path, statement: str) -> tuple[int, dict[str, object]]:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "fabric" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text(statement + "\n", encoding="utf-8")
    data_forge = src_root / "polisyos" / "data_forge"
    data_forge.mkdir(parents=True)
    (data_forge / "__init__.py").write_text("", encoding="utf-8")

    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)
    output = tmp_path / "report.json"
    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing-exceptions.toml"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
    )
    return exit_code, json.loads(output.read_text(encoding="utf-8"))


def test_lint_imports_allows_only_the_registered_submodule_of_an_allowed_root(
    tmp_path: Path,
) -> None:
    exit_code, payload = _run_narrowed_import_case(
        tmp_path,
        "from polisyos.data_forge.read_api import catalog",
    )

    assert exit_code == 0
    assert payload["data"]["violation_count"] == 0


def test_lint_imports_resolves_parent_from_import_to_registered_submodule(
    tmp_path: Path,
) -> None:
    exit_code, payload = _run_narrowed_import_case(
        tmp_path,
        "from polisyos.data_forge import read_api",
    )

    assert exit_code == 0
    assert payload["data"]["violation_count"] == 0


@pytest.mark.parametrize(
    "statement",
    [
        "from polisyos.data_forge import kernel",
        "from polisyos.data_forge import read_api, kernel",
    ],
)
def test_lint_imports_rejects_disallowed_names_from_narrowed_parent(
    tmp_path: Path,
    statement: str,
) -> None:
    exit_code, payload = _run_narrowed_import_case(tmp_path, statement)

    assert exit_code == 1
    assert payload["data"]["violation_count"] == 1
    assert payload["messages"][0]["rule_id"] == "ARCH007"


def test_lint_imports_rejects_sibling_of_registered_narrowing(tmp_path: Path) -> None:
    exit_code, payload = _run_narrowed_import_case(
        tmp_path,
        "from polisyos.data_forge.kernel import compile_dataset",
    )

    assert exit_code == 1
    assert payload["data"]["violation_count"] == 1
    assert payload["messages"][0]["rule_id"] == "ARCH007"
    assert payload["messages"][0]["message"].endswith(
        "[ARCH007] forbidden narrowed internal import: fabric -> data_forge "
        "via polisyos.data_forge.kernel "
        "(allowed_prefixes=polisyos.data_forge.read_api)"
    )


def test_version_two_policy_fails_closed_on_missing_governance_disposition(
    tmp_path: Path,
) -> None:
    src_root = tmp_path / "src"
    for root in ("fabric", "data_forge"):
        package = src_root / "polisyos" / root
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)
    boundaries = tmp_path / "boundaries.toml"
    content = boundaries.read_text(encoding="utf-8")
    content = content.split(
        '\n[[package]]\nmodule = "polisyos.data_forge"',
        maxsplit=1,
    )[0]
    boundaries.write_text(content.rstrip() + "\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="package governance missing for direction roots: data_forge",
    ):
        lint_imports.read_policy(policy)


def test_version_two_policy_fails_closed_on_nonexistent_direction_root(
    tmp_path: Path,
) -> None:
    src_root = tmp_path / "src"
    fabric = src_root / "polisyos" / "fabric"
    fabric.mkdir(parents=True)
    (fabric / "__init__.py").write_text("", encoding="utf-8")
    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)

    with pytest.raises(
        ValueError,
        match="direction matrix roots without directories: data_forge",
    ):
        lint_imports.read_policy(policy)


def test_import_policy_fails_closed_on_unsupported_version(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    for root in ("fabric", "data_forge"):
        package = src_root / "polisyos" / root
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)
    policy.write_text(
        policy.read_text(encoding="utf-8").replace('version = "2"', 'version = "2.0"'),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"unsupported import policy version '2\.0'; supported versions: 1\.0, 2",
    ):
        lint_imports.read_policy(policy)


def test_version_two_policy_fails_closed_on_undeclared_source_package(
    tmp_path: Path,
) -> None:
    src_root = tmp_path / "src"
    for root in ("fabric", "data_forge", "rogue"):
        package = src_root / "polisyos" / root
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)

    with pytest.raises(
        ValueError,
        match="direction matrix missing source package roots: rogue",
    ):
        lint_imports.read_policy(policy)


def test_version_two_policy_rejects_extra_exact_root_boundary(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    for root in ("fabric", "data_forge"):
        package = src_root / "polisyos" / root
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    policy = tmp_path / "policy.toml"
    _write_narrowed_policy(policy, src_root)
    boundaries = tmp_path / "boundaries.toml"
    boundaries.write_text(
        boundaries.read_text(encoding="utf-8")
        + textwrap.dedent(
            """

            [[package]]
            module = "polisyos.rogue"
            owner = "team-rogue"
            public_facade = "polisyos.rogue"
            allowed_dependencies = []
            forbidden_dependencies = []
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="package boundary root rogue is not in direction matrix",
    ):
        lint_imports.read_policy(policy)


def test_lint_imports_emits_structured_json_and_sarif(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("import pandas\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)

    json_output = tmp_path / "report.json"
    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing_exceptions.toml"),
            "--output-format",
            "json",
            "--output",
            str(json_output),
        ]
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["data"]["violation_count"] == 1
    assert payload["data"]["lapsed_cover_count"] == 0
    assert payload["data"]["unadjudicated_count"] == 1
    assert any(message["rule_id"] == "ARCH002" for message in payload["messages"])

    sarif_output = tmp_path / "report.sarif"
    lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(tmp_path / "missing_exceptions.toml"),
            "--output-format",
            "sarif",
            "--output",
            str(sarif_output),
        ]
    )
    sarif_payload = json.loads(sarif_output.read_text(encoding="utf-8"))
    assert sarif_payload["runs"][0]["results"][0]["ruleId"] == "ARCH002"


def test_lint_imports_reports_lapsed_cover_and_unadjudicated_populations(
    tmp_path: Path,
    capsys,
) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("import numpy\nimport pandas\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    exceptions = tmp_path / "import_exceptions.toml"
    exceptions.write_text(
        textwrap.dedent(
            """
            [[exception]]
            id = "expired-pandas-cover"
            owner = "team-architecture"
            reason = "Exercise the lapsed-cover population."
            expires = "2026-01-01"
            source_glob = "*"
            external_module = "pandas"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Lapsed cover (1):" in output
    assert "expired-pandas-cover" in output
    assert "Unadjudicated (1):" in output
    assert "Violation populations: lapsed cover=1 + unadjudicated=1 = total=2" in output
    assert collect_arch_metrics._count_import_violations(output) == 2


def test_lint_imports_exception_expiring_today_is_allowed_not_lapsed(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("import pandas\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    exceptions = tmp_path / "import_exceptions.toml"
    exceptions.write_text(
        textwrap.dedent(
            f"""
            [[exception]]
            id = "expires-today"
            owner = "team-architecture"
            reason = "Pin the inclusive final day of valid cover."
            expires = "{datetime.date.today().isoformat()}"
            source_glob = "*"
            external_module = "pandas"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    json_output = tmp_path / "report.json"

    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
            "--output-format",
            "json",
            "--output",
            str(json_output),
        ]
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["data"]["violation_count"] == 0
    assert payload["data"]["lapsed_cover_count"] == 0
    assert payload["data"]["unadjudicated_count"] == 0
    assert payload["data"]["allowed_exception_count"] == 1


def test_lint_imports_nonmatching_exception_does_not_adjudicate_violation(tmp_path: Path) -> None:
    src_root = tmp_path / "src"
    module_path = src_root / "polisyos" / "ir" / "sample.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("import pandas\n", encoding="utf-8")

    policy = tmp_path / "import_policy.toml"
    _write_policy(policy, src_root)
    exceptions = tmp_path / "import_exceptions.toml"
    exceptions.write_text(
        textwrap.dedent(
            """
            [[exception]]
            id = "exists-but-does-not-match"
            owner = "team-architecture"
            reason = "An id alone is not cover for a different edge."
            expires = "2026-01-01"
            source_glob = "*"
            external_module = "numpy"
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    json_output = tmp_path / "report.json"

    exit_code = lint_imports.main(
        [
            "--policy",
            str(policy),
            "--exceptions",
            str(exceptions),
            "--output-format",
            "json",
            "--output",
            str(json_output),
        ]
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["data"]["violation_count"] == 1
    assert payload["data"]["lapsed_cover_count"] == 0
    assert payload["data"]["unadjudicated_count"] == 1
    assert payload["data"]["allowed_exception_count"] == 0


_IDENTIFIER = st.from_regex(r"[a-z][a-z0-9_]{0,7}", fullmatch=True).filter(
    lambda value: not keyword.iskeyword(value)
)


@given(
    current_parts=st.lists(_IDENTIFIER, min_size=2, max_size=5),
    is_package=st.booleans(),
    level=st.integers(min_value=1, max_value=5),
    suffix_parts=st.lists(_IDENTIFIER, max_size=3),
)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_resolve_import_module_matches_relative_import_semantics(
    current_parts: list[str],
    is_package: bool,
    level: int,
    suffix_parts: list[str],
) -> None:
    package_parts = current_parts if is_package else current_parts[:-1]
    assume(package_parts)
    assume(level - 1 <= len(package_parts))

    import_target = "." * level + ".".join(suffix_parts)
    node = ast.parse(f"from {import_target} import target").body[0]
    assert isinstance(node, ast.ImportFrom)

    expected_parts = package_parts[: len(package_parts) - (level - 1)]
    expected_parts.extend(suffix_parts)
    expected = ".".join(expected_parts)

    resolved = lint_imports.resolve_import_module(".".join(current_parts), is_package, node)

    assert resolved == expected


def test_resolve_import_module_rejects_overflowing_relative_import() -> None:
    node = ast.parse("from ....foo import bar").body[0]
    assert isinstance(node, ast.ImportFrom)

    resolved = lint_imports.resolve_import_module("polisyos.ir.sample", False, node)

    assert resolved is None
