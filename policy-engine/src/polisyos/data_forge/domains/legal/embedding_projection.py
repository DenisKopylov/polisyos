"""Shared legal text projections for embedding producers and consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


# v2 binds the normalized raw-query encoder call to Legal index generations.
# A v1 artifact has no such query-side compatibility rule and is not searchable.
LEGAL_EMBEDDING_PROJECTION_RULE_VERSION = "policyos.legal.embedding.v2"


def entity_embedding_text(row: Sequence[object]) -> str:
    """Project one legal entity row into the indexed text representation."""
    if len(row) != 5:
        raise ValueError("legal entity embedding row must contain five text fields")
    name_en, name_uk, entity_type, aliases_en, aliases_uk = row
    parts = ["ENTITY", f"en: {name_en}", f"uk: {name_uk or ''}", f"type: {entity_type}"]
    aliases: list[str] = []
    if aliases_en:
        aliases.extend(str(aliases_en).split("; ")[:6])
    if aliases_uk:
        aliases.extend(str(aliases_uk).split("; ")[:6])
    if aliases:
        parts.append("aliases: " + "; ".join(aliases))
    return "\n".join(parts)


def fact_embedding_text(row: Sequence[object]) -> str:
    """Project one legal fact row into the indexed text representation."""
    if len(row) != 14:
        raise ValueError("legal fact embedding row must contain fourteen text fields")
    (
        subject_en,
        subject_uk,
        predicate,
        object_en,
        object_uk,
        fact_text,
        norm_type,
        action_canon,
        norm_type_canon,
        condition_text_uk,
        exception_text_uk,
        procedure_text_uk,
        thresholds_json,
        source_quote_uk,
    ) = row

    parts = [
        "FACT",
        f"norm_type: {norm_type_canon or norm_type or 'unknown'}",
        f"action: {action_canon or predicate or 'unknown'}",
        f"spo: {subject_en} ({subject_uk or ''}) {predicate} {object_en} ({object_uk or ''})",
        f"fact_en: {fact_text}",
    ]
    if condition_text_uk:
        parts.append(f"condition_uk: {condition_text_uk}")
    if exception_text_uk:
        parts.append(f"exception_uk: {exception_text_uk}")
    if procedure_text_uk:
        parts.append(f"procedure_uk: {procedure_text_uk}")
    if thresholds_json:
        parts.append(f"thresholds: {thresholds_json}")
    if source_quote_uk:
        parts.append(f"quote_uk: {str(source_quote_uk)[:400]}")
    return "\n".join(parts)


def provision_embedding_text(row: Sequence[object]) -> str:
    """Project one legal provision row into the indexed text representation."""
    if len(row) != 1:
        raise ValueError("legal provision embedding row must contain one text field")
    (provision_text,) = row
    return str(provision_text or "")


__all__ = [
    "LEGAL_EMBEDDING_PROJECTION_RULE_VERSION",
    "entity_embedding_text",
    "fact_embedding_text",
    "provision_embedding_text",
]
