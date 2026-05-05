from __future__ import annotations

from polisyos.data_forge.domains.legal.batch.doc_family import classify_doc_family


def test_doc_family_keeps_law_as_primary_family_even_with_appendix_like_units() -> None:
    family = classify_doc_family(
        doc_type_category_value="law",
        provision_rows=[
            {
                "kind": "article",
                "struct_kind": "article",
                "section_role": "normative_unit",
            },
            {
                "kind": "table_row",
                "struct_kind": "table_row",
                "section_role": "table_clause",
                "appendix_id": "1",
                "table_id": "t1",
            },
            {
                "kind": "table_row",
                "struct_kind": "table_row",
                "section_role": "table_clause",
                "appendix_id": "1",
                "table_id": "t1",
            },
        ],
    )

    assert family == "law"


def test_doc_family_marks_appendix_heavy_for_order_with_appendix_dominated_units() -> None:
    family = classify_doc_family(
        doc_type_category_value="order",
        provision_rows=[
            {
                "kind": "table_row",
                "struct_kind": "table_row",
                "section_role": "table_clause",
                "appendix_id": "1",
                "table_id": "t1",
            },
            {
                "kind": "enumeration_item",
                "struct_kind": "enumeration_item",
                "section_role": "catalog_entry",
                "appendix_id": "1",
            },
        ],
    )

    assert family == "appendix_heavy"
