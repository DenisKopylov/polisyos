from __future__ import annotations

import json

from polisyos.data_forge.domains.legal.batch.temporal_parser import parse_temporal_constraints
from polisyos.data_forge.domains.legal.batch.temporal_resolver import (
    coerce_doc_temporal,
    resolve_document_temporal,
    resolve_fact_temporal,
)


def test_parse_temporal_constraints_supports_interval_and_relative_publication() -> None:
    constraints = parse_temporal_constraints(
        "Цей Закон набирає чинності через 3 місяці з дня опублікування та діє з 1 січня 2024 року до 31 грудня 2024 року.",
        publication_date_iso="2024-02-01",
    )

    assert any(item.constraint_type == "closed_interval" for item in constraints)
    relative = next(item for item in constraints if item.constraint_type == "relative_to_anchor")
    assert relative.resolved is True
    assert relative.effective_from_iso == "2024-05-01"


def test_parse_temporal_constraints_supports_start_end_repeal_and_suspension() -> None:
    constraints = parse_temporal_constraints(
        "Дія акта з 1 січня 2024 року. Норма діє до 31 грудня 2024 року. "
        "Закон втрачає чинність з 15 січня 2025 року. Дію документа зупинено до 1 березня 2025 року."
    )

    fixed_start = next(item for item in constraints if item.constraint_type == "fixed_start")
    fixed_end = next(item for item in constraints if item.constraint_type == "fixed_end")
    repeal = next(item for item in constraints if item.constraint_type == "loss_of_force")
    suspension = next(item for item in constraints if item.constraint_type == "suspension")

    assert fixed_start.effective_from_iso == "2024-01-01"
    assert fixed_end.effective_to_iso == "2024-12-31"
    assert repeal.effective_to_iso == "2025-01-15"
    assert suspension.effective_to_iso == "2025-03-01"
    assert suspension.state_hint == "suspended"


def test_parse_temporal_constraints_leaves_publication_relative_unresolved_without_publication_date() -> (
    None
):
    constraints = parse_temporal_constraints(
        "Цей Закон набирає чинності через 30 днів з дня опублікування."
    )

    relative = next(item for item in constraints if item.constraint_type == "relative_to_anchor")
    assert relative.resolved is False
    assert relative.effective_from_iso is None
    assert relative.anchor_date_kind == "publication"


def test_parse_temporal_constraints_supports_relative_to_adoption_without_date_fallback() -> None:
    constraints = parse_temporal_constraints(
        "Цей Закон набирає чинності через 2 місяці з дня прийняття.",
        adoption_date_iso="2024-01-15",
    )

    relative = next(item for item in constraints if item.constraint_type == "relative_to_anchor")
    assert relative.resolved is True
    assert relative.effective_from_iso == "2024-03-15"
    assert relative.anchor_date_kind == "adoption"


def test_resolve_document_temporal_uses_publication_metadata_without_date_acc_fallback() -> None:
    envelope = resolve_document_temporal(
        {
            "status": "Не набрав чинності",
            "date_acc": "2024-01-15",
            "publication": ["Офіційний вісник України#10.02.2024#52#23"],
        },
        text="Цей Закон набирає чинності з дня його опублікування.",
    )

    assert envelope.published_at == "2024-02-10"
    assert envelope.effective_from == "2024-02-10"
    assert envelope.temporal_resolution_status == "resolved"
    provenance = json.loads(envelope.temporal_provenance_json)
    assert provenance["date_acc"] == "2024-01-15"


def test_resolve_document_temporal_keeps_future_state_when_publication_anchor_is_missing() -> None:
    envelope = resolve_document_temporal(
        {
            "status": "Не набрав чинності",
            "date_acc": "2024-01-15",
            "publication": [],
        },
        text="Цей Закон набирає чинності через 30 днів з дня опублікування.",
    )

    assert envelope.published_at == ""
    assert envelope.effective_from == ""
    assert envelope.temporal_state == "future"
    assert envelope.temporal_resolution_status == "partial"
    assert envelope.temporal_source_kind == "relative_to_anchor"


def test_resolve_document_temporal_marks_status_only_historical_as_partial() -> None:
    envelope = resolve_document_temporal(
        {
            "status": "Втратив чинність",
            "date_acc": "2024-01-15",
            "publication": [],
        }
    )

    assert envelope.effective_from == ""
    assert envelope.effective_to == ""
    assert envelope.temporal_state == "historical"
    assert envelope.temporal_resolution_status == "partial"


def test_resolve_document_temporal_downgrades_historical_start_only_to_partial() -> None:
    envelope = resolve_document_temporal(
        {
            "status": "Втратив чинність",
            "publication": ["Офіційний вісник України#01.02.2024#52#23"],
        },
        text="Цей Закон діє з 1 січня 2024 року.",
    )

    assert envelope.effective_from == "2024-01-01"
    assert envelope.effective_to == ""
    assert envelope.temporal_state == "historical"
    assert envelope.temporal_resolution_status == "partial"


def test_coerce_doc_temporal_normalizes_historical_start_only_metadata() -> None:
    envelope = coerce_doc_temporal(
        {
            "temporal": {
                "published_at": "2024-02-01",
                "effective_from": "2024-01-01",
                "effective_to": "",
                "temporal_state": "historical",
                "temporal_resolution_status": "resolved",
                "temporal_source_kind": "fixed_start",
                "temporal_confidence": 0.95,
                "temporal_provenance_json": "{}",
            }
        }
    )

    assert envelope.effective_from == "2024-01-01"
    assert envelope.temporal_state == "historical"
    assert envelope.temporal_resolution_status == "partial"


def test_resolve_fact_temporal_prefers_statement_override_over_doc_envelope() -> None:
    doc_temporal = resolve_document_temporal(
        {
            "status": "Чинний",
            "publication": ["Офіційний вісник України#01.02.2024#52#23"],
        },
        text="Цей Закон набирає чинності з дня його опублікування.",
    )

    fact_temporal = resolve_fact_temporal(
        doc_temporal=doc_temporal,
        temporal_text_uk="до 31 грудня 2024 року",
        provision_text_uk="Норма діє до 31 грудня 2024 року.",
    )

    assert fact_temporal.effective_from == ""
    assert fact_temporal.effective_to == ""
    assert fact_temporal.temporal_resolution_status == "partial"

    inherited = resolve_fact_temporal(
        doc_temporal=doc_temporal,
        temporal_text_uk="",
        provision_text_uk="",
    )
    assert inherited.effective_from == "2024-02-01"
    assert inherited.temporal_resolution_status == "resolved"


def test_resolve_fact_temporal_downgrades_historical_start_only_to_partial() -> None:
    doc_temporal = resolve_document_temporal(
        {
            "status": "Втратив чинність",
            "publication": ["Офіційний вісник України#01.02.2024#52#23"],
        },
        text="Цей Закон діє з 1 січня 2024 року.",
    )

    fact_temporal = resolve_fact_temporal(
        doc_temporal=doc_temporal,
        temporal_text_uk="з 1 січня 2024 року",
        provision_text_uk="Норма діє з 1 січня 2024 року.",
    )

    assert fact_temporal.effective_from == ""
    assert fact_temporal.effective_to == ""
    assert fact_temporal.temporal_state == "historical"
    assert fact_temporal.temporal_resolution_status == "partial"


def test_resolve_fact_temporal_does_not_inherit_resolved_historical_start_only_doc_window() -> None:
    fact_temporal = resolve_fact_temporal(
        doc_temporal=coerce_doc_temporal(
            {
                "temporal": {
                    "published_at": "2024-02-01",
                    "effective_from": "2024-01-01",
                    "effective_to": "",
                    "temporal_state": "historical",
                    "temporal_resolution_status": "resolved",
                    "temporal_source_kind": "fixed_start",
                    "temporal_confidence": 0.95,
                    "temporal_provenance_json": "{}",
                }
            }
        ),
        temporal_text_uk="",
        provision_text_uk="",
    )

    assert fact_temporal.effective_from == ""
    assert fact_temporal.effective_to == ""
    assert fact_temporal.temporal_state == "historical"
    assert fact_temporal.temporal_resolution_status == "partial"
