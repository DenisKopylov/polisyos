from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tools.quality.validation.architecture_report_surface import _inline_override_counts


def _counts(repo_root: Path) -> dict[str, int]:
    return _inline_override_counts(repo_root, _services=cast("Any", None))


def test_counter_uses_comment_tokens_and_preserves_inline_scope(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    tests_root = tmp_path / "tests"
    tools_root = tmp_path / "tools"
    source_root.mkdir()
    tests_root.mkdir()
    tools_root.mkdir()
    quote = "'" * 3
    (source_root / "policy.py").write_text(
        "value: int = 'wrong'  # type: ignore[assignment] # type: ignore[return-value]\n"
        "import optional_module  # noqa: F401  # noqa: E402\n"
        "fixture = " + quote + "\n"
        "# type: ignore[attr-defined]\n"
        "# noqa: F821\n"
        + quote
        + "\n"
        + "message = '# type: ignore[assignment] and # noqa: F401'\n"
        + "# ruff: noqa: S101\n",
        encoding="utf-8",
    )
    (tests_root / "fixture.py").write_text(
        "example = '# noqa: F401 and # type: ignore[assignment]'\n",
        encoding="utf-8",
    )
    (tools_root / "actual.py").write_text("value = 1  # noqa\n", encoding="utf-8")
    (source_root / "__pycache__").mkdir()
    (source_root / "__pycache__" / "ignored.py").write_text(
        "value = 1  # noqa: F401\n",
        encoding="utf-8",
    )

    assert _counts(tmp_path) == {
        "inline_type_ignore_count": 1,
        "inline_noqa_count": 2,
    }


def test_removing_comment_directive_while_retaining_marker_text_removes_signal(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src" / "candidate.py"
    source.parent.mkdir()
    source.write_text(
        "value: int = 'wrong'  # type: ignore[assignment]\nimport optional_module  # noqa: F401\n",
        encoding="utf-8",
    )
    tools = tmp_path / "tools" / "candidate.py"
    tools.parent.mkdir()
    tools.write_text("value = 1  # noqa: F401\n", encoding="utf-8")
    assert _counts(tmp_path) == {
        "inline_type_ignore_count": 1,
        "inline_noqa_count": 2,
    }

    quote = "'" * 3
    source.write_text(
        "fixture = " + quote + "\n"
        "value: int = 'wrong'  # type: ignore[assignment]\n"
        "import optional_module  # noqa: F401\n" + quote + "\n",
        encoding="utf-8",
    )
    tools.write_text(
        "fixture = " + quote + "\nvalue = 1  # noqa: F401\n" + quote + "\n",
        encoding="utf-8",
    )
    assert _counts(tmp_path) == {
        "inline_type_ignore_count": 0,
        "inline_noqa_count": 0,
    }


def test_counter_surfaces_tokenization_errors_with_source_path(tmp_path: Path) -> None:
    broken = tmp_path / "src" / "broken.py"
    broken.parent.mkdir()
    broken.write_text('value = """unterminated\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"src/broken\.py"):
        _counts(tmp_path)
