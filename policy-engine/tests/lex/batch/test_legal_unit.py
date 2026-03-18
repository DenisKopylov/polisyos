from __future__ import annotations

from polisyos.lex.batch.legal_unit import build_legal_unit_signals


def test_build_legal_unit_signals_marks_amendment_bundle_as_deterministic_only() -> None:
    signals = build_legal_unit_signals(
        text='У статті 4 слова "центральний орган" замінити словами "уповноважений орган".',
        struct_kind="enumeration_item",
        section_role="table_clause",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Про внесення змін до Порядку",
        citation_label="Пункт 2",
    )

    assert signals.legal_unit_subtype == "amendment_bundle"
    assert signals.route_class == "deterministic_only"
    assert signals.reference_bearing is True
    assert signals.audit_miss_prone is True


def test_build_legal_unit_signals_marks_threshold_row() -> None:
    signals = build_legal_unit_signals(
        text="Ректор   300 грн",
        struct_kind="table_row",
        section_role="table_row",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Додаток до постанови",
        citation_label="Рядок 1",
    )

    assert signals.legal_unit_subtype == "tariff_threshold_row"
    assert signals.route_class == "deterministic_only"
    assert signals.threshold_bearing is True


def test_build_legal_unit_signals_marks_form_scaffold_as_search_only() -> None:
    signals = build_legal_unit_signals(
        text="Виконавець: Іваненко",
        struct_kind="table_row",
        section_role="signature_block",
        fallback_allowed_for_reasoning=False,
        doc_family="appendix_heavy",
        doc_title="Додаток до наказу",
        citation_label="Додаток 1",
    )

    assert signals.legal_unit_subtype == "form_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_rescues_appendix_requirement_bullet() -> None:
    signals = build_legal_unit_signals(
        text="- виконувати усі вимоги сертифікації;",
        struct_kind="enumeration_item",
        section_role="catalog_item",
        fallback_allowed_for_reasoning=False,
        doc_family="appendix_heavy",
        doc_title="Форма заявки на сертифікацію",
        citation_label="Додаток 1, пункт 4",
    )

    assert signals.legal_unit_subtype == "application_requirement"
    assert signals.route_class == "deterministic_only"


def test_build_legal_unit_signals_marks_placeholder_row_as_form_scaffold() -> None:
    signals = build_legal_unit_signals(
        text="** Вноситься потрібне.",
        struct_kind="table_row",
        section_role="table_row",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Додаток до наказу",
        citation_label="Рядок 1",
    )

    assert signals.legal_unit_subtype == "form_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_does_not_mark_general_obligation_as_application_requirement() -> None:
    signals = build_legal_unit_signals(
        text=(
            "Перевізник зобов'язується безпечно перевезти пасажира до пункту призначення, "
            "а пасажир зобов'язується внести установлену плату за проїзд."
        ),
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Правила перевезення",
        citation_label="Пункт 19",
    )

    assert signals.legal_unit_subtype == "core_normative_clause"
    assert signals.route_class in {"deterministic_then_llm_retry", "llm_primary"}


def test_build_legal_unit_signals_does_not_mark_mandate_paragraph_as_threshold_row() -> None:
    signals = build_legal_unit_signals(
        text=(
            "Емісійно-кредитному департаменту надіслати зазначені нормативні документи "
            "обласним управлінням та підготувати на січень - лютий 1996 року регіональні семінари."
        ),
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Постанова Національного банку України",
        citation_label="Пункт 6",
    )

    assert signals.legal_unit_subtype == "core_normative_clause"


def test_build_legal_unit_signals_marks_settlement_registry_as_search_only() -> None:
    signals = build_legal_unit_signals(
        text="1 с. Довгий Ліс 2 с. Мотилі 3 с. Нове Шарне",
        struct_kind="paragraph",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Перелік населених пунктів",
        citation_label="Додаток 1",
    )

    assert signals.legal_unit_subtype == "registry_catalog_row"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_marks_appendix_header_as_search_only() -> None:
    signals = build_legal_unit_signals(
        text="Додаток до Положення про план приватизації майна, затвердженого наказом Фонду державного майна України",
        struct_kind="appendix",
        section_role="appendix_header",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Додаток до Положення",
        citation_label="Додаток",
    )

    assert signals.legal_unit_subtype == "table_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_marks_amendment_wording_item_as_deterministic() -> None:
    signals = build_legal_unit_signals(
        text='25. У додатках NN 1, 2, 4 слова "карбованці" замінити на слово "гривні".',
        struct_kind="enumeration_item",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Про внесення змін",
        citation_label="Пункт 25",
    )

    assert signals.legal_unit_subtype == "amendment_bundle"
    assert signals.route_class == "deterministic_only"
