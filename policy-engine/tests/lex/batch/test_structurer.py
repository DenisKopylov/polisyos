from __future__ import annotations

from polisyos.lex.batch.structurer import extract_provisions


def test_extract_provisions_structured_fallback_extracts_appendix_and_table_rows() -> None:
    text = """
Додаток 1
до Порядку подання звітності

Перелік показників
Назва   Значення   Примітка
Викиди   10   так
Відходи  20   ні
""".strip()

    spans = extract_provisions(
        text,
        doc_name="Додаток до Порядку подання звітності",
        publisher="Кабінет Міністрів України",
    )

    assert spans
    assert all(span.kind != "full_text" for span in spans)
    assert any(span.struct_kind == "appendix" for span in spans)
    table_rows = [span for span in spans if span.struct_kind == "table_row"]
    assert len(table_rows) == 3
    assert all(span.appendix_id == "1" for span in table_rows)
    assert all(bool(span.table_id) for span in table_rows)
    assert all(span.anchor_path.startswith("appendix:1/") for span in table_rows)


def test_extract_provisions_structured_fallback_extracts_numbered_list_items() -> None:
    text = """
Перелік вимог до заявника

1) Подати заяву встановленої форми.
2) Надати копію договору
   та підтвердження оплати.
3) Повідомити орган протягом п'яти днів.
""".strip()

    spans = extract_provisions(text, doc_name="Перелік вимог")

    items = [span for span in spans if span.struct_kind == "enumeration_item"]
    assert len(items) == 3
    assert all(span.kind in {"point", "subpoint"} for span in items)
    assert all(not span.is_fallback_chunk for span in items)
    assert all(span.fallback_allowed_for_reasoning for span in items)
    assert "копію договору" in items[1].text
    assert "підтвердження оплати" in items[1].text


def test_extract_provisions_structured_fallback_extracts_column_clauses_under_appendix_section() -> (
    None
):
    text = """
Додаток 2
Розділ I. Порядок заповнення

Колонка 10 - зазначається вид забезпечення кредиту.
Колонка 11 - зазначається загальна вартість забезпечення
  згідно з договором застави.
""".strip()

    spans = extract_provisions(
        text,
        doc_name="Додаток до Порядку заповнення форми",
        publisher="Національний банк України",
    )

    section_spans = [span for span in spans if span.section_role == "appendix_section"]
    assert len(section_spans) == 1
    assert section_spans[0].anchor_path.startswith("appendix:2/sec:001-")

    column_spans = [span for span in spans if span.section_role == "table_clause"]
    assert len(column_spans) == 2
    assert all(span.anchor_path.startswith(section_spans[0].anchor_path) for span in column_spans)
    assert column_spans[0].citation_label == "Колонка 10"
    assert "згідно з договором застави" in column_spans[1].text


def test_extract_provisions_structured_fallback_merges_multiline_table_rows_and_marks_headers() -> (
    None
):
    text = """
Додаток 1
Назва   Опис   Поріг
Викиди   Детальний опис показника
  що продовжується на наступному рядку
Відходи  Інший показник  20
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до форми звіту")

    header_spans = [span for span in spans if span.section_role == "table_header"]
    assert len(header_spans) == 1
    assert not header_spans[0].fallback_allowed_for_reasoning

    data_rows = [
        span
        for span in spans
        if span.struct_kind == "table_row" and span.section_role == "table_row"
    ]
    assert len(data_rows) == 2
    assert "що продовжується на наступному рядку" in data_rows[0].text


def test_extract_provisions_marks_form_and_questionnaire_appendix_units_as_search_only() -> None:
    text = """
Додаток 3
Керівнику органу з сертифікації

1) чи здійснюється контроль виробництва?
2) чи ведеться облік рекламацій?
""".strip()

    spans = extract_provisions(
        text,
        doc_name="Додаток до наказу",
        publisher="Міністерство економіки України",
    )

    appendix_header = next(span for span in spans if span.struct_kind == "appendix")
    assert appendix_header.section_role == "form_header"
    assert appendix_header.fallback_allowed_for_reasoning is False

    questionnaire_items = [span for span in spans if span.section_role == "questionnaire_item"]
    assert len(questionnaire_items) == 2
    assert all(span.fallback_allowed_for_reasoning is False for span in questionnaire_items)


def test_extract_provisions_marks_attachment_inventory_and_signature_blocks_as_search_only() -> (
    None
):
    attachments_text = """
Додаток 2

1) Копії контрактів додаються.
2) Перелік документів, що подаються.
""".strip()
    attachment_spans = extract_provisions(attachments_text, doc_name="Додаток до наказу")

    inventories = [span for span in attachment_spans if span.section_role == "attachment_inventory"]
    assert len(inventories) == 2
    assert all(span.fallback_allowed_for_reasoning is False for span in inventories)

    signature_text = """
Додаток 1
Виконавець: Іваненко
Телефон: 123-45-67
""".strip()
    signature_spans = extract_provisions(signature_text, doc_name="Додаток до наказу")

    assert len(signature_spans) == 1
    assert signature_spans[0].section_role == "signature_block"
    assert signature_spans[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_form_fields_and_salary_headers_as_search_only() -> None:
    form_text = """
Додаток 1
Заявник   просить провести сертифікацію   на відповідність вимогам
""".strip()
    form_spans = extract_provisions(form_text, doc_name="Додаток до наказу")

    form_fields = [span for span in form_spans if span.section_role == "form_field"]
    assert len(form_fields) == 1
    assert form_fields[0].fallback_allowed_for_reasoning is False

    salary_text = """
Додаток 1
Найменування посад   Місячні посадові оклади
Ректор   300
""".strip()
    salary_spans = extract_provisions(salary_text, doc_name="Додаток до постанови")

    table_headers = [
        span for span in salary_spans if span.section_role in {"table_header", "form_header"}
    ]
    assert len(table_headers) == 1
    assert table_headers[0].fallback_allowed_for_reasoning is False
    data_rows = [span for span in salary_spans if span.anchor_path.endswith("/row:0001")]
    assert len(data_rows) == 1
    assert data_rows[0].fallback_allowed_for_reasoning is True


def test_extract_provisions_marks_form_continuation_and_footer_rows_as_search_only() -> None:
    continuation_text = """
Додаток N
Продукція   та просить провести сертифікацію цієї продукції на відповідність
НД   вимогам зазначених нормативних документів за правилами Системи
""".strip()
    continuation_spans = extract_provisions(continuation_text, doc_name="Додаток до наказу")

    continuation_rows = [span for span in continuation_spans if span.struct_kind == "table_row"]
    assert len(continuation_rows) == 2
    assert all(span.section_role == "form_field" for span in continuation_rows)
    assert all(span.fallback_allowed_for_reasoning is False for span in continuation_rows)

    footer_text = """
Додаток N
Печатка                                        Дата
""".strip()
    footer_spans = extract_provisions(footer_text, doc_name="Додаток до наказу")

    signature_rows = [span for span in footer_spans if span.struct_kind == "table_row"]
    assert len(signature_rows) == 1
    assert signature_rows[0].section_role == "signature_block"
    assert signature_rows[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_table_scaffold_and_decorative_rows_as_search_only() -> None:
    scaffold_text = """
Додаток N
*        *не число (відношення *кінцевої передачі    *передаваль-*
******************************************************************
Головний бухгалтер                  *       97-122
""".strip()
    spans = extract_provisions(scaffold_text, doc_name="Додаток до наказу")

    table_scaffold_rows = [span for span in spans if span.section_role == "table_scaffold"]
    assert len(table_scaffold_rows) == 1
    assert table_scaffold_rows[0].fallback_allowed_for_reasoning is False

    decorative_rows = [span for span in spans if span.section_role == "decorative_separator"]
    assert len(decorative_rows) == 1
    assert decorative_rows[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_fragmented_multi_column_rows_as_search_only() -> None:
    text = """
Додаток N
бів категорії С * лів, обладна-  * бів категорії С   * бів категорії С    *бів будь-якої * 1 місяць на-  
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до наказу")

    rows = [span for span in spans if span.struct_kind == "table_row"]
    assert len(rows) == 1
    assert rows[0].section_role == "table_scaffold"
    assert rows[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_form_instruction_rows_as_search_only() -> None:
    text = """
Додаток 5
Прийнято справу до свого провадження. (потрібне підкреслити)
    """.strip()

    spans = extract_provisions(text, doc_name="Додаток до інструкції")

    appendix_span = next(span for span in spans if span.struct_kind == "appendix")
    assert appendix_span.section_role == "form_field"
    assert appendix_span.fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_nominal_appendix_list_items_as_catalog_items() -> None:
    text = """
Додаток N
- схему сертифікації (за узгодженням із заявником);
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до правил сертифікації")

    items = [span for span in spans if span.struct_kind == "enumeration_item"]
    assert len(items) == 1
    assert items[0].section_role == "catalog_item"
    assert items[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_short_two_column_headers_as_search_only() -> None:
    text = """
Додаток N
Підлягає                                                Оплачено
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до інструкції")

    rows = [span for span in spans if span.struct_kind == "table_row"]
    assert len(rows) == 1
    assert rows[0].section_role == "table_header"
    assert rows[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_catalog_appendix_items_as_search_only() -> None:
    text = """
Додаток N
ПЕРЕЛІК СУДІВ,
розташованих в аварійних приміщеннях

1. Сімферопольський районний суд
2. Залізничний районний суд м. Сімферополя
""".strip()

    spans = extract_provisions(text, doc_name="Про забезпечення судів приміщеннями")

    catalog_headers = [span for span in spans if span.section_role == "catalog_header"]
    assert catalog_headers
    assert all(span.fallback_allowed_for_reasoning is False for span in catalog_headers)

    catalog_items = [span for span in spans if span.struct_kind == "enumeration_item"]
    assert len(catalog_items) == 2
    assert all(span.section_role == "catalog_item" for span in catalog_items)
    assert all(span.fallback_allowed_for_reasoning is False for span in catalog_items)


def test_extract_provisions_marks_appendix_heading_blocks_as_search_only() -> None:
    text = """
Додаток 1
СХЕМИ ОБОВ'ЯЗКОВОЇ СЕРТИФІКАЦІЇ ПІДІЙМАЛЬНИХ СПОРУД У СИСТЕМІ УкрСЕПРО

Форма N 1
ЖУРНАЛ РЕЄСТРАЦІЇ ВХІДНОЇ КОРЕСПОНДЕНЦІЇ
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до Правил")

    heading_blocks = [span for span in spans if span.section_role == "catalog_header"]
    assert heading_blocks
    assert all(span.fallback_allowed_for_reasoning is False for span in heading_blocks)


def test_extract_provisions_marks_placeholder_rows_and_stamps_as_search_only() -> None:
    text = """
Додаток N
Реєстраційний N __________
"___" _____________ 199_ р.
М. П.
""".strip()

    spans = extract_provisions(text, doc_name="Заява на одержання Свідоцтва")

    search_only_headers = [
        span for span in spans if span.section_role in {"appendix_header", "form_header"}
    ]
    assert len(search_only_headers) == 1
    assert search_only_headers[0].fallback_allowed_for_reasoning is False

    stamp_spans = [span for span in spans if span.section_role == "signature_block"]
    assert len(stamp_spans) == 1
    assert stamp_spans[0].fallback_allowed_for_reasoning is False


def test_extract_provisions_marks_numeric_table_index_rows_as_search_only() -> None:
    text = """
Додаток 1
1 * 2 * 3 * 4 * 5 * 6
Ректор * 300
""".strip()

    spans = extract_provisions(text, doc_name="Додаток до постанови")

    scaffold_rows = [span for span in spans if span.section_role == "table_scaffold"]
    assert len(scaffold_rows) == 1
    assert scaffold_rows[0].fallback_allowed_for_reasoning is False

    data_rows = [span for span in spans if "Ректор" in span.text]
    assert len(data_rows) == 1
    assert data_rows[0].fallback_allowed_for_reasoning is True


def test_extract_provisions_strict_catalog_docs_demote_cost_tables_to_search_only() -> None:
    text = """
Додаток N
Стаття витрат    *            Зміст і характеристика витрат
5. Витрати на    витрати на перевезення працівників до місця роботи
відрахування     на державне пенсійне страхування
""".strip()

    spans = extract_provisions(
        text,
        doc_name="Типове положення з планування, обліку і калькулювання собівартості продукції",
    )

    catalog_rows = [span for span in spans if span.struct_kind == "table_row"]
    assert catalog_rows
    assert all(
        span.section_role in {"table_header", "catalog_header", "catalog_item"}
        for span in catalog_rows
    )
    assert all(span.fallback_allowed_for_reasoning is False for span in catalog_rows)


def test_extract_provisions_marks_form_context_labels_as_search_only() -> None:
    text = """
Додаток N
(дата реєстрації заяви)
Державна комісія з цінних паперів та фондового ринку
Ідентифікаційний код заявника по ЄДРПОУ *****************
Телефон            Телефакс                   Телекс
""".strip()

    spans = extract_provisions(text, doc_name="Заява на одержання Свідоцтва")

    assert all(span.fallback_allowed_for_reasoning is False for span in spans)


def test_extract_provisions_marks_payment_form_rows_as_search_only() -> None:
    text = """
Додаток 1
Сума літерами
Призначення платежу
Керівник підприємства  підпис
Головний бухгалтер     підпис
""".strip()

    spans = extract_provisions(text, doc_name="Форма платіжного документа")

    assert spans
    assert all(span.fallback_allowed_for_reasoning is False for span in spans)


def test_extract_provisions_fallback_chunks_have_unique_anchors() -> None:
    # No article headers -> fallback chunking path.
    text = ("Тестовий суцільний текст без структури.\n" * 300).strip()

    spans = extract_provisions(
        text,
        enable_paragraphs=True,
        fallback_chunk_chars=600,
        fallback_chunk_overlap=100,
    )

    assert len(spans) > 1
    anchors = [s.anchor_path for s in spans]
    assert len(set(anchors)) == len(anchors)
    assert all(s.kind == "full_text" for s in spans)
    assert all(s.is_fallback_chunk for s in spans)
    assert all(s.parent_anchor == "full" for s in spans)
    assert all(s.token_est > 0 for s in spans)
    assert all(bool(s.text_hash) for s in spans)
