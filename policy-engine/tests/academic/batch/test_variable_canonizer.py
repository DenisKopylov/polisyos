from __future__ import annotations

from pathlib import Path

from polisyos.academic.knowledge.variable_canonizer import VariableCanonizer


def test_canonizer_merges_gdp_synonyms() -> None:
    canonizer = VariableCanonizer()

    c1, is_new_1 = canonizer.canonize("gdp growth")
    c2, is_new_2 = canonizer.canonize("economic growth")

    assert c1 == "gdp_growth"
    assert c2 == "gdp_growth"
    assert is_new_1 is False
    assert is_new_2 is False


def test_canonizer_fallback_and_pending_review() -> None:
    canonizer = VariableCanonizer()

    canonical, is_new = canonizer.canonize("rare indicator 2026")

    assert is_new is True
    assert canonical == "rare_indicator_2026"
    pending = canonizer.get_pending_review()
    assert pending
    assert pending[0][0] == "rare indicator 2026"


def test_canonizer_duckdb_cache_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "canon.duckdb"

    canonizer_a = VariableCanonizer(db_path=db_path)
    canonical_a, _ = canonizer_a.canonize("strange growth metric")

    canonizer_b = VariableCanonizer(db_path=db_path)
    canonical_b, is_new_b = canonizer_b.canonize("strange growth metric")

    assert canonical_b == canonical_a
    assert is_new_b is False
