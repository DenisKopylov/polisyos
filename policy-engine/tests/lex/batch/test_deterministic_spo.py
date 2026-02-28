from __future__ import annotations

from polisyos.lex.batch.deterministic_spo import extract_deterministic_spo


def test_deterministic_spo_extracts_entry_into_force() -> None:
    result = extract_deterministic_spo(
        text="Цей акт набирає чинності з дня офіційного опублікування.",
        citation_label="Стаття 1",
        doc_title="Тестовий закон",
    )
    assert result.candidates
    assert any(candidate.predicate == "enters_into_force" for candidate in result.candidates)
    assert "entry_into_force_pattern" in result.reason_codes
    assert result.confidence > 0.7


def test_deterministic_spo_extracts_thresholds() -> None:
    result = extract_deterministic_spo(
        text="Ставка податку становить 18% для платників податку.",
        citation_label="Стаття 2",
        doc_title="Податковий закон",
    )
    assert result.candidates
    assert any(candidate.predicate == "sets_threshold" for candidate in result.candidates)
    assert any(candidate.thresholds for candidate in result.candidates)

