"""Deterministic temporal resolution for Lex documents and facts."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from polisyos.lex.batch.doc_identity import parse_doc_date
from polisyos.lex.batch.temporal_parser import TemporalConstraint, parse_temporal_constraints

_PUBLICATION_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{4})"
)

_STATUS_CURRENT_RE = re.compile(r"\bчинн", re.IGNORECASE)
_STATUS_FUTURE_RE = re.compile(r"не\s+наб(рав|ула|ули)\s+чинності", re.IGNORECASE)
_STATUS_HISTORICAL_RE = re.compile(r"втратив(?:ши)?\s+чинність", re.IGNORECASE)
_STATUS_HISTORICAL_PARTIAL_RE = re.compile(r"втратив(?:ши)?\s+чинність\s+частково", re.IGNORECASE)
_STATUS_SUSPENDED_RE = re.compile(r"дію\s+призупинено", re.IGNORECASE)

_HISTORICAL_STATES = {"historical", "historical_partial", "suspended"}
_NOW_ISO = datetime.now(UTC).date().isoformat()


@dataclass(frozen=True)
class DocTemporalEnvelope:
    """Resolved temporal metadata for a legal document version.

    The envelope normalizes publication/effective dates and classifies the
    document into UA legislative states such as `current`, `historical`,
    `suspended`, or `future`.
    """

    published_at: str = ""
    effective_from: str = ""
    effective_to: str = ""
    temporal_state: str = "unknown"
    temporal_resolution_status: str = "unknown"
    temporal_source_kind: str = ""
    temporal_confidence: float = 0.0
    temporal_provenance_json: str = "{}"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "published_at": self.published_at,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "temporal_state": self.temporal_state,
            "temporal_resolution_status": self.temporal_resolution_status,
            "temporal_source_kind": self.temporal_source_kind,
            "temporal_confidence": round(float(self.temporal_confidence or 0.0), 3),
            "temporal_provenance_json": self.temporal_provenance_json,
        }


@dataclass(frozen=True)
class FactTemporalEnvelope:
    """Resolved temporal metadata for one fact or provision-level statement."""

    effective_from: str = ""
    effective_to: str = ""
    temporal_state: str = "unknown"
    temporal_resolution_status: str = "unknown"
    temporal_source_scope: str = ""
    temporal_source_kind: str = ""
    temporal_confidence: float = 0.0
    temporal_provenance_json: str = "{}"


def _normalize_doc_temporal_envelope(envelope: DocTemporalEnvelope) -> DocTemporalEnvelope:
    resolution_status = str(envelope.temporal_resolution_status or "unknown")
    source_kind = str(envelope.temporal_source_kind or "")
    if (
        resolution_status == "resolved"
        and envelope.temporal_state in _HISTORICAL_STATES
        and not envelope.effective_to
    ):
        resolution_status = "partial"
        if not source_kind:
            source_kind = "status_semantics"
    if (
        resolution_status == "resolved"
        and envelope.effective_from
        and envelope.effective_to
        and envelope.effective_to < envelope.effective_from
    ):
        resolution_status = "conflict"
    return DocTemporalEnvelope(
        published_at=envelope.published_at,
        effective_from=envelope.effective_from,
        effective_to=envelope.effective_to,
        temporal_state=envelope.temporal_state,
        temporal_resolution_status=resolution_status,
        temporal_source_kind=source_kind,
        temporal_confidence=envelope.temporal_confidence,
        temporal_provenance_json=envelope.temporal_provenance_json,
    )


def _distinct_non_empty(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)
    return ordered


def _status_semantics(status: str) -> tuple[str, str, float]:
    raw = str(status or "").strip()
    if not raw:
        return "unknown", "unknown", 0.0
    if _STATUS_HISTORICAL_PARTIAL_RE.search(raw):
        return "historical_partial", "partial", 0.75
    if _STATUS_HISTORICAL_RE.search(raw):
        return "historical", "partial", 0.8
    if _STATUS_SUSPENDED_RE.search(raw):
        return "suspended", "partial", 0.8
    if _STATUS_FUTURE_RE.search(raw):
        return "future", "partial", 0.85
    if _STATUS_CURRENT_RE.search(raw):
        return "current", "partial", 0.7
    return "unknown", "unknown", 0.0


def extract_publication_date(metadata: Mapping[str, Any]) -> str:
    """Extract and normalize a publication date from document metadata."""

    explicit = str(metadata.get("published_at") or "").strip()
    if explicit:
        parsed = parse_doc_date(explicit)
        if parsed is not None:
            return parsed.isoformat()
    publication = metadata.get("publication")
    values: list[str] = []
    if isinstance(publication, str):
        values = [publication]
    elif isinstance(publication, (list, tuple)):
        values = [str(item) for item in publication if str(item).strip()]
    for item in values:
        match = _PUBLICATION_DATE_RE.search(item)
        if match is None:
            continue
        try:
            parsed = parse_doc_date(
                f"{int(match.group('day')):02d}.{int(match.group('month')):02d}.{match.group('year')}"
            )
            if parsed is not None:
                return parsed.isoformat()
        except Exception:
            continue
    return ""


def _temporal_scan_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    if len(raw) <= 6000:
        return raw
    head = raw[:2000]
    tail = raw[-4000:]
    return f"{head}\n{tail}"


def _resolved_constraint_dates(
    constraints: list[TemporalConstraint],
) -> tuple[list[str], list[str], float, str]:
    effective_from_candidates = _distinct_non_empty([item.effective_from_iso for item in constraints if item.resolved])
    effective_to_candidates = _distinct_non_empty([item.effective_to_iso for item in constraints if item.resolved])
    confidence = max((float(item.confidence or 0.0) for item in constraints), default=0.0)
    source_kind = ",".join(
        sorted({str(item.constraint_type or "").strip() for item in constraints if str(item.constraint_type or "").strip()})
    )
    return effective_from_candidates, effective_to_candidates, confidence, source_kind


def resolve_document_temporal(
    metadata: Mapping[str, Any],
    *,
    text: str = "",
) -> DocTemporalEnvelope:
    """Resolve publication/effective dates and legal status for a document."""

    publication_date_iso = extract_publication_date(metadata)
    adoption_date = parse_doc_date(str(metadata.get("date_acc") or ""))
    adoption_date_iso = adoption_date.isoformat() if adoption_date is not None else ""
    state_from_status, resolution_from_status, status_confidence = _status_semantics(str(metadata.get("status") or ""))

    scan_text = _temporal_scan_text(text)
    constraints = parse_temporal_constraints(
        scan_text,
        publication_date_iso=publication_date_iso or None,
        adoption_date_iso=adoption_date_iso or None,
    )
    effective_from_candidates, effective_to_candidates, text_confidence, source_kind = _resolved_constraint_dates(constraints)

    conflict = len(effective_from_candidates) > 1 or len(effective_to_candidates) > 1
    effective_from = effective_from_candidates[0] if len(effective_from_candidates) == 1 else ""
    effective_to = effective_to_candidates[0] if len(effective_to_candidates) == 1 else ""

    resolution_status = "unknown"
    temporal_state = state_from_status
    temporal_source_kind = ""
    temporal_confidence = 0.0

    if conflict:
        resolution_status = "conflict"
        temporal_source_kind = source_kind or "document_text_conflict"
        temporal_confidence = text_confidence
    elif effective_from:
        resolution_status = "resolved"
        temporal_source_kind = source_kind or "document_text"
        temporal_confidence = text_confidence
        if effective_to and effective_to < effective_from:
            resolution_status = "conflict"
    elif effective_to or publication_date_iso or resolution_from_status != "unknown" or constraints:
        resolution_status = "partial"
        temporal_source_kind = source_kind or ("status_semantics" if resolution_from_status != "unknown" else "publication_metadata")
        temporal_confidence = max(text_confidence, status_confidence, 0.6 if publication_date_iso else 0.0)

    if temporal_state == "unknown":
        if resolution_status == "resolved":
            temporal_state = "current"
        elif constraints:
            temporal_state = next((item.state_hint for item in constraints if item.state_hint), "unknown")

    # A historical/suspended status without a bounded end should not look fully resolved,
    # otherwise downstream checks may treat the document as still active.
    if resolution_status == "resolved" and temporal_state in _HISTORICAL_STATES and not effective_to:
        resolution_status = "partial"
        if not temporal_source_kind:
            temporal_source_kind = source_kind or "status_semantics"

    provenance = {
        "status": str(metadata.get("status") or ""),
        "date_acc": str(metadata.get("date_acc") or ""),
        "reg_date": str(metadata.get("reg_date") or ""),
        "reestr_date": str(metadata.get("reestr_date") or ""),
        "published_at": publication_date_iso,
        "publication_raw": (
            [str(item) for item in metadata.get("publication", [])]
            if isinstance(metadata.get("publication"), (list, tuple))
            else ([str(metadata.get("publication"))] if str(metadata.get("publication") or "").strip() else [])
        ),
        "resolved_constraints": [asdict(item) for item in constraints[:8]],
    }

    return _normalize_doc_temporal_envelope(
        DocTemporalEnvelope(
        published_at=publication_date_iso,
        effective_from=effective_from,
        effective_to=effective_to,
        temporal_state=temporal_state,
        temporal_resolution_status=resolution_status,
        temporal_source_kind=temporal_source_kind,
        temporal_confidence=temporal_confidence,
        temporal_provenance_json=json.dumps(provenance, ensure_ascii=False, sort_keys=True),
        )
    )


def coerce_doc_temporal(metadata: Mapping[str, Any] | Any) -> DocTemporalEnvelope:
    """Coerce persisted temporal metadata or derive it from raw document metadata."""

    if not isinstance(metadata, Mapping):
        return resolve_document_temporal({})
    temporal = metadata.get("temporal")
    if isinstance(temporal, Mapping):
        return _normalize_doc_temporal_envelope(
            DocTemporalEnvelope(
                published_at=str(temporal.get("published_at") or ""),
                effective_from=str(temporal.get("effective_from") or ""),
                effective_to=str(temporal.get("effective_to") or ""),
                temporal_state=str(temporal.get("temporal_state") or "unknown"),
                temporal_resolution_status=str(temporal.get("temporal_resolution_status") or "unknown"),
                temporal_source_kind=str(temporal.get("temporal_source_kind") or ""),
                temporal_confidence=float(temporal.get("temporal_confidence") or 0.0),
                temporal_provenance_json=str(temporal.get("temporal_provenance_json") or "{}"),
            )
        )
    return resolve_document_temporal(metadata)


def resolve_fact_temporal(
    *,
    doc_temporal: DocTemporalEnvelope,
    temporal_text_uk: str = "",
    provision_text_uk: str = "",
    adoption_date_iso: str | None = None,
) -> FactTemporalEnvelope:
    """Resolve statement-level temporal bounds from fact and provision text."""

    statement_constraints = parse_temporal_constraints(
        str(temporal_text_uk or ""),
        publication_date_iso=doc_temporal.published_at or None,
        adoption_date_iso=adoption_date_iso,
    )
    provision_constraints = []
    if not statement_constraints and provision_text_uk.strip():
        provision_constraints = parse_temporal_constraints(
            provision_text_uk,
            publication_date_iso=doc_temporal.published_at or None,
            adoption_date_iso=adoption_date_iso,
        )

    candidates = statement_constraints or provision_constraints
    effective_from_candidates, effective_to_candidates, candidate_confidence, source_kind = _resolved_constraint_dates(candidates)
    conflict = len(effective_from_candidates) > 1 or len(effective_to_candidates) > 1

    if conflict:
        return FactTemporalEnvelope(
            temporal_state=next((item.state_hint for item in candidates if item.state_hint), doc_temporal.temporal_state),
            temporal_resolution_status="conflict",
            temporal_source_scope="statement" if statement_constraints else "provision",
            temporal_source_kind=source_kind or "statement_conflict",
            temporal_confidence=candidate_confidence,
            temporal_provenance_json=json.dumps(
                {
                    "scope": "statement" if statement_constraints else "provision",
                    "temporal_text_uk": temporal_text_uk,
                    "resolved_constraints": [asdict(item) for item in candidates[:6]],
                    "doc_temporal": doc_temporal.to_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    if effective_from_candidates:
        effective_from = effective_from_candidates[0]
        effective_to = effective_to_candidates[0] if len(effective_to_candidates) == 1 else ""
        resolution_status = "resolved"
        if effective_to and effective_to < effective_from:
            resolution_status = "conflict"
        if (
            resolution_status == "resolved"
            and doc_temporal.temporal_state in _HISTORICAL_STATES
            and not effective_to
        ):
            resolution_status = "partial"
        return FactTemporalEnvelope(
            effective_from=effective_from if resolution_status == "resolved" else "",
            effective_to=effective_to if resolution_status == "resolved" else "",
            temporal_state=(
                doc_temporal.temporal_state
                if doc_temporal.temporal_state in _HISTORICAL_STATES and resolution_status != "conflict"
                else next((item.state_hint for item in candidates if item.state_hint), doc_temporal.temporal_state)
            ),
            temporal_resolution_status=resolution_status,
            temporal_source_scope="statement" if statement_constraints else "provision",
            temporal_source_kind=source_kind or ("statement_temporal_text" if statement_constraints else "provision_text"),
            temporal_confidence=candidate_confidence,
            temporal_provenance_json=json.dumps(
                {
                    "scope": "statement" if statement_constraints else "provision",
                    "temporal_text_uk": temporal_text_uk,
                    "resolved_constraints": [asdict(item) for item in candidates[:6]],
                    "doc_temporal": doc_temporal.to_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    if candidates:
        return FactTemporalEnvelope(
            temporal_state=next((item.state_hint for item in candidates if item.state_hint), doc_temporal.temporal_state),
            temporal_resolution_status="partial",
            temporal_source_scope="statement" if statement_constraints else "provision",
            temporal_source_kind=source_kind or ("statement_temporal_text" if statement_constraints else "provision_text"),
            temporal_confidence=candidate_confidence,
            temporal_provenance_json=json.dumps(
                {
                    "scope": "statement" if statement_constraints else "provision",
                    "temporal_text_uk": temporal_text_uk,
                    "resolved_constraints": [asdict(item) for item in candidates[:6]],
                    "doc_temporal": doc_temporal.to_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    if doc_temporal.temporal_resolution_status == "resolved" and doc_temporal.effective_from:
        if doc_temporal.temporal_state in _HISTORICAL_STATES and not doc_temporal.effective_to:
            return FactTemporalEnvelope(
                temporal_state=doc_temporal.temporal_state,
                temporal_resolution_status="partial",
                temporal_source_scope="document",
                temporal_source_kind="doc_temporal_inheritance_historical",
                temporal_confidence=doc_temporal.temporal_confidence,
                temporal_provenance_json=json.dumps(
                    {
                        "scope": "document",
                        "doc_temporal": doc_temporal.to_metadata(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            )
        return FactTemporalEnvelope(
            effective_from=doc_temporal.effective_from,
            effective_to=doc_temporal.effective_to,
            temporal_state=doc_temporal.temporal_state,
            temporal_resolution_status="resolved",
            temporal_source_scope="document",
            temporal_source_kind="doc_temporal_inheritance",
            temporal_confidence=doc_temporal.temporal_confidence,
            temporal_provenance_json=json.dumps(
                {
                    "scope": "document",
                    "doc_temporal": doc_temporal.to_metadata(),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

    resolution_status = doc_temporal.temporal_resolution_status if doc_temporal.temporal_resolution_status != "resolved" else "unknown"
    if (
        doc_temporal.temporal_state in _HISTORICAL_STATES
        and resolution_status == "resolved"
        and (not doc_temporal.effective_to or doc_temporal.effective_to >= _NOW_ISO)
    ):
        resolution_status = "partial"
    return FactTemporalEnvelope(
        temporal_state=doc_temporal.temporal_state,
        temporal_resolution_status=resolution_status,
        temporal_source_scope="document",
        temporal_source_kind=doc_temporal.temporal_source_kind or "doc_temporal_inheritance",
        temporal_confidence=doc_temporal.temporal_confidence,
        temporal_provenance_json=json.dumps(
            {
                "scope": "document",
                "doc_temporal": doc_temporal.to_metadata(),
                "temporal_text_uk": temporal_text_uk,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )


__all__ = [
    "DocTemporalEnvelope",
    "FactTemporalEnvelope",
    "coerce_doc_temporal",
    "extract_publication_date",
    "resolve_document_temporal",
    "resolve_fact_temporal",
]
