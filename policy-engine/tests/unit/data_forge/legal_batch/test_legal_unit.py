from __future__ import annotations

import re

from polisyos.data_forge.domains.legal.batch.jurisdictions.protocol import (
    NormativeSignalPatterns,
    StructurePatterns,
)
from polisyos.data_forge.domains.legal.batch.legal_unit import build_legal_unit_signals


class _EnglishPlugin:
    @property
    def jurisdiction_code(self) -> str:
        return "EN"

    @property
    def language_codes(self) -> list[str]:
        return ["en"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^Article\s+\d+", re.IGNORECASE),
            part_re=None,
            point_res=(),
            subpoint_re=None,
            paragraph_re=None,
            section_heading_re=None,
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=re.compile(r"\bshall\b|\bmust\b", re.IGNORECASE),
            prohibition_re=re.compile(r"\bshall not\b|\bmust not\b", re.IGNORECASE),
            permission_re=re.compile(r"\bmay\b", re.IGNORECASE),
            approval_re=re.compile(r"\bapprove\b|\badopt\b", re.IGNORECASE),
            amendment_re=re.compile(r"\bamend\b|\breplace\b", re.IGNORECASE),
            temporal_re=re.compile(r"\benters into force\b|\bwithin \d+ days\b", re.IGNORECASE),
            reference_re=re.compile(r"\barticle\s+\d+\b|\bregulation\s+\d+\b", re.IGNORECASE),
            threshold_re=re.compile(r"\b\d+(?:[.,]\d+)?\s*%\b", re.IGNORECASE),
        )

    def reference_patterns(self) -> tuple[tuple[str, re.Pattern[str], float], ...]:
        return ()

    def document_type_hierarchy(self) -> dict[str, int]:
        return {"Act": 1}


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
    assert signals.route_class == "deterministic_then_llm_retry"
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


def test_build_legal_unit_signals_does_not_mark_general_obligation_as_application_requirement() -> (
    None
):
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


def test_build_legal_unit_signals_demotes_appendix_reference_explanation_to_scaffold() -> None:
    signals = build_legal_unit_signals(
        text="У графі 12 зазначаються реквізити документа відповідно до статті 5 цього Порядку.",
        struct_kind="paragraph",
        section_role="table_clause",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Додаток до Порядку",
        citation_label="Примітка 1",
    )

    assert signals.legal_unit_subtype == "table_scaffold"


def test_build_legal_unit_signals_routes_appendix_heavy_cnc_through_deterministic_retry() -> None:
    """appendix_heavy + core_normative_clause should now use deterministic_then_llm_retry."""
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
    assert signals.route_class == "deterministic_then_llm_retry"


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


def test_build_legal_unit_signals_routes_amendment_packaging_leads_out_of_core_normative_clause() -> (
    None
):
    signals = build_legal_unit_signals(
        text='Назву розділу IV Закону викласти в такій редакції: "Прикінцеві положення".',
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="law",
        doc_title="Про внесення змін до Закону України",
        citation_label="Пункт 3",
    )

    assert signals.legal_unit_subtype == "amendment_bundle"
    assert signals.route_class == "deterministic_only"


def test_build_legal_unit_signals_marks_form_section_heading_as_search_only() -> None:
    signals = build_legal_unit_signals(
        text="Вимоги щодо порядку підготовки і подання заяви, повідомлення та документів, що додаються до них",
        struct_kind="paragraph",
        section_role="procedure",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Форма заяви",
        citation_label="Додаток 1",
    )

    assert signals.legal_unit_subtype == "form_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_marks_fee_schedule_as_threshold_not_application() -> None:
    signals = build_legal_unit_signals(
        text="1. Із заяв і скарг, що подаються до суду: а) із позивних заяв 5 відсотків ціни позову",
        struct_kind="paragraph",
        section_role="table_clause",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Декрет про державне мито",
        citation_label="Пункт 1",
    )

    assert signals.legal_unit_subtype == "tariff_threshold_row"
    assert signals.route_class == "deterministic_then_llm_retry"


def test_build_legal_unit_signals_does_not_treat_bare_dopovnennia_as_amendment() -> None:
    signals = build_legal_unit_signals(
        text="Якщо заява подається більше ніж однією особою, інформацію можна подавати окремо і посилатись на неї як на доповнення.",
        struct_kind="enumeration_item",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Форма заяви",
        citation_label="Пункт 8",
    )

    assert signals.legal_unit_subtype != "amendment_bundle"


def test_build_legal_unit_signals_marks_core_micro_subtypes() -> None:
    condition = build_legal_unit_signals(
        text="Якщо перевізник порушує умови договору, він зобов'язаний повідомити орган.",
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="law",
        doc_title="Закон України про перевезення",
        citation_label="Стаття 12",
    )
    scope = build_legal_unit_signals(
        text="Ця Інструкція поширюється на всі державні підприємства.",
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Інструкція з обліку",
        citation_label="Пункт 2",
    )

    assert condition.legal_unit_subtype == "core_normative_clause"
    assert condition.legal_unit_micro_subtype == "condition_tail"
    assert scope.legal_unit_subtype == "core_normative_clause"
    assert scope.legal_unit_micro_subtype == "scope_tail"


def test_build_legal_unit_signals_inherits_appendix_remove_action_from_context() -> None:
    signals = build_legal_unit_signals(
        text="імені 40-річчя Радянської України",
        struct_kind="enumeration_item",
        section_role="catalog_item",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Про внесення змін до переліку",
        citation_label="Додаток 1",
        context_prefix="I. Виключаються з переліку колгоспи:",
    )

    assert signals.legal_unit_subtype == "amendment_bundle"
    assert signals.route_class == "deterministic_only"


def test_build_legal_unit_signals_demotes_front_matter_to_search_only() -> None:
    signals = build_legal_unit_signals(
        text="ЗАРЕЄСТРОВАНО в Міністерстві юстиції України 11.03.1996 р. № 121/1146 НАКАЗУЮ:",
        struct_kind="paragraph",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Наказ Міністерства фінансів України",
        citation_label="Повний текст",
    )

    assert signals.legal_unit_subtype == "table_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_demotes_short_form_label_to_scaffold() -> None:
    signals = build_legal_unit_signals(
        text="Назва об'єднання фінансових установ",
        struct_kind="paragraph",
        section_role="procedure",
        fallback_allowed_for_reasoning=True,
        doc_family="appendix_heavy",
        doc_title="Форма заяви",
        citation_label="Додаток 2",
    )

    assert signals.legal_unit_subtype == "form_scaffold"
    assert signals.route_class == "search_only"


def test_build_legal_unit_signals_does_not_mark_treaty_temporal_clause_as_threshold_tail() -> None:
    signals = build_legal_unit_signals(
        text=(
            "Чорноморський флот Російської Федерації використовує об'єкти "
            "на умовах та протягом строку дії Угоди від 28 травня 1997 року."
        ),
        struct_kind="point",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="treaty_protocol",
        doc_title="Угода між Україною і Російською Федерацією",
        citation_label="Стаття 1",
    )

    assert signals.legal_unit_subtype == "core_normative_clause"
    assert signals.legal_unit_micro_subtype != "threshold_tail"


def test_build_legal_unit_signals_uses_plugin_specific_normative_and_reference_patterns() -> None:
    signals = build_legal_unit_signals(
        text="Article 5. The authority shall notify the regulator under Regulation 7.",
        struct_kind="article",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="law",
        doc_title="Foreign Act",
        citation_label="Article 5",
        jurisdiction_plugin=_EnglishPlugin(),
    )

    assert signals.legal_unit_subtype == "core_normative_clause"
    assert signals.legal_unit_micro_subtype == "reference_tail"
    assert signals.reference_bearing is True


def test_build_legal_unit_signals_keeps_incidental_approval_article_out_of_bundle() -> None:
    signals = build_legal_unit_signals(
        text=(
            "Стаття 123. Доручення на провадження дій у справі про порушення митних правил "
            "Службова особа митного органу України має право доручити провадження окремих дій "
            "службовій особі іншого митного органу України. Доручення повинно бути виконано "
            "у строк не більше п'яти днів з дня його одержання."
        ),
        struct_kind="article",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="law",
        doc_title="Митний кодекс України",
        citation_label="Стаття 123",
    )

    assert signals.legal_unit_subtype != "approval_bundle"
    assert signals.legal_unit_subtype in {"core_normative_clause", "temporal_clause"}


def test_build_legal_unit_signals_keeps_editorial_amendment_note_out_of_bundle() -> None:
    signals = build_legal_unit_signals(
        text=(
            "Стаття 2. Платником податку є особа, обсяг оподатковуваних операцій якої "
            "перевищував 600 неоподатковуваних мінімумів доходів громадян. "
            "(статтю 2 доповнено пунктом 2.6 згідно із Законом України від 26.09.97 р. N 550/97-ВР)"
        ),
        struct_kind="article",
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
        doc_family="law",
        doc_title="Закон про податок на додану вартість",
        citation_label="Стаття 2",
    )

    assert signals.legal_unit_subtype != "amendment_bundle"
