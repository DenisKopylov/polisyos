from __future__ import annotations

import importlib
from datetime import date

from polisyos.common import text as common_text
from polisyos.common.timestamps import parse_iso_date

collapse_ws = common_text.collapse_ws


def test_common_collapses_whitespace_without_touching_words() -> None:
    assert collapse_ws("  legal\n\ttext   with   gaps ") == "legal text with gaps"


def test_common_parses_iso_date_and_datetime_strings() -> None:
    assert parse_iso_date("2026-05-06") == date(2026, 5, 6)
    assert parse_iso_date("2026-05-06T14:30:00Z") == date(2026, 5, 6)
    assert parse_iso_date("not-a-date") is None


def test_lex_consumers_keep_the_common_function_object() -> None:
    """The four existing consumers retain the canonical collapse_ws object."""
    consumers = (
        "polisyos.lex.legal_evaluation.backends.simple_v1",
        "polisyos.lex.legal_evaluation.context_builder",
        "polisyos.lex.normpack.assemble_pack",
        "polisyos.lex.normpack.extract_norm_claims",
    )
    for module_name in consumers:
        consumer = importlib.import_module(module_name)
        assert consumer.collapse_ws is common_text.collapse_ws
