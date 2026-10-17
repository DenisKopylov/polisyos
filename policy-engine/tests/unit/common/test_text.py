from __future__ import annotations

from polisyos.common import text as common_text

collapse_ws = common_text.collapse_ws


def test_common_collapses_whitespace_without_touching_words() -> None:
    assert collapse_ws("  legal\n\ttext   with   gaps ") == "legal text with gaps"
