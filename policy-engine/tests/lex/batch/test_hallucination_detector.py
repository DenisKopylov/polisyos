from __future__ import annotations

from polisyos.lex.batch.hallucination_detector import detect_hallucination_flags
from polisyos.lex.knowledge.types import SPOCandidate


def _statement(**overrides: object) -> SPOCandidate:
    payload = {
        "subject_en": "subject",
        "subject_uk": "суб'єкт правовідносин",
        "predicate": "requires",
        "object_en": "permit",
        "object_uk": "дозвіл",
        "fact_text": "Вимагається: отримати дозвіл",
        "fact_text_uk": "Вимагається: отримати дозвіл",
        "confidence": 0.8,
        "norm_type": "obligation",
        "source_quote_uk": "Забороняється порушувати встановлений порядок.",
    }
    payload.update(overrides)
    return SPOCandidate.model_validate(payload)


def test_hallucination_detector_skips_synthetic_subject_grounding_noise() -> None:
    flags = detect_hallucination_flags(
        statement=_statement(),
        provision_text="Забороняється порушувати встановлений порядок.",
    )

    assert not any(flag["type"] == "ungrounded_subject" for flag in flags)


def test_hallucination_detector_only_flags_norm_type_mismatch_for_explicit_modal_fact() -> None:
    flags = detect_hallucination_flags(
        statement=_statement(
            subject_uk="орган",
            fact_text="Орган застосовує встановлений порядок.",
            fact_text_uk="Орган застосовує встановлений порядок.",
        ),
        provision_text="Порядок застосовується відповідно до закону.",
    )

    assert not any(flag["type"] == "norm_type_mismatch" for flag in flags)
