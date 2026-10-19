"""Candidate-only Legal threshold math tests; these confer no source authority."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.lex.knowledge.types import LegalRuleThresholdRow


@pytest.mark.parametrize("operator", ["between", "in"])
@pytest.mark.parametrize("lower_bound", [0.0, 1e-5])
@pytest.mark.parametrize("candidate_value", [-1.0, 0.0, 1e-5, 2.0, 5.0, 6.0])
def test_candidate_threshold_math_retains_double_precision_and_units(
    tmp_path: Path,
    operator: str,
    lower_bound: float,
    candidate_value: float,
) -> None:
    """Exercise the existing numerical primitives without an authority claim."""
    db_path = tmp_path / "threshold-candidate-math.duckdb"
    with duckdb.connect(str(db_path)) as connection:
        connection.execute(
            "CREATE TABLE lex_rule_thresholds ("
            "threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR, operator VARCHAR, "
            "value_decimal DOUBLE, value_text VARCHAR, unit VARCHAR, applies_to VARCHAR)"
        )
        connection.execute(
            "INSERT INTO lex_rule_thresholds VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ["threshold-zero", "fact-zero", "distance", operator, lower_bound, "5", "km", "firms"],
        )
        stored_value, stored_type = connection.execute(
            "SELECT value_decimal, typeof(value_decimal) "
            "FROM lex_rule_thresholds WHERE threshold_id = ?",
            ["threshold-zero"],
        ).fetchone()

    assert stored_type == "DOUBLE"
    assert type(stored_value) is float
    assert type(candidate_value) is float
    assert type(lower_bound) is float

    threshold = LegalRuleThresholdRow(
        threshold_id="threshold-zero",
        fact_id="fact-zero",
        metric="distance",
        operator=operator,
        value_decimal=stored_value,
        value_text="5",
        unit="km",
        applies_to="firms",
        trust_tier="search_candidate",
    )
    store = LegalKnowledgeStore(db_path=db_path, index_dir=tmp_path)
    try:
        threshold_values = store._threshold_operator_values(threshold)
        candidate_normalized = store._normalize_unit_value(candidate_value, "km")
        normalized_thresholds = [
            store._normalize_unit_value(value, threshold.unit) for value in threshold_values
        ]
        operator_fn = store._operator_registry().get(operator)
    finally:
        store.close()

    assert threshold.value_decimal == lower_bound
    assert threshold_values == (lower_bound, 5.0)
    assert candidate_normalized is not None
    assert candidate_normalized == (candidate_value, "length", "km")
    assert all(value is not None for value in normalized_thresholds)
    assert normalized_thresholds == [
        (lower_bound, "length", "km"),
        (5.0, "length", "km"),
    ]
    assert operator_fn is not None
    actual = operator_fn(
        candidate_normalized[0],
        tuple(value[0] for value in normalized_thresholds if value is not None),
    )
    expected = (
        lower_bound <= candidate_value <= 5.0
        if operator == "between"
        else candidate_value in {lower_bound, 5.0}
    )
    assert actual is expected
