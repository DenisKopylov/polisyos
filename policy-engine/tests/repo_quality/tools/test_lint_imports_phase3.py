from __future__ import annotations

import ast
import datetime
import json
import keyword
import textwrap
from pathlib import Path

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
