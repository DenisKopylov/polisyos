from __future__ import annotations

from polisyos.lex.batch.amendment_detector import detect_amendments


def test_detect_amendments_keeps_act_context_in_replace_text_signal() -> None:
    amendments = detect_amendments(
        'У статті 5 Закону України "Про базовий акт" слова «старий текст» замінити словами «новий текст».'
    )

    assert len(amendments) == 1
    amendment = amendments[0]
    assert amendment.amendment_type == "replace_text"
    assert amendment.target_anchor == "article:5"
    assert 'Закону України "Про базовий акт"' in amendment.source_text


def test_detect_amendments_skips_bare_low_signal_fallbacks() -> None:
    amendments = detect_amendments("Виключено")

    assert amendments == []
