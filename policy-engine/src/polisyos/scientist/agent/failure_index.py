"""Failure pattern index for cross-run critic memory."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes

FAILURE_INDEX_KIND = "scientist.failure_pattern_index"
FAILURE_INDEX_SCHEMA = SchemaInfo(name=FAILURE_INDEX_KIND, version="1.1")
_MAX_CARD_REFS = 20

_WORD_RE = re.compile(r"[a-z0-9_]{3,}")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_PATH_INDEX_RE = re.compile(r"\[\d+\]")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class FailureIndexEntry:
    """A recurring failure signature with aggregate statistics."""

    signature_id: str
    error_code: str
    category: str
    domain: str
    source_step: str
    normalized_location: str
    normalized_message: str
    remediation_advice: str
    occurrence_count: int = 1
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    card_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FailureIndexEntry":
        return cls(
            signature_id=str(payload.get("signature_id", "")),
            error_code=str(payload.get("error_code", "unknown")),
            category=str(payload.get("category", "unknown")),
            domain=str(payload.get("domain", "general")),
            source_step=str(payload.get("source_step", "critic")),
            normalized_location=str(payload.get("normalized_location", "")),
            normalized_message=str(payload.get("normalized_message", "")),
            remediation_advice=str(payload.get("remediation_advice", "")),
            occurrence_count=int(payload.get("occurrence_count", 1)),
            first_seen=str(payload.get("first_seen", datetime.now(timezone.utc).isoformat())),
            last_seen=str(payload.get("last_seen", datetime.now(timezone.utc).isoformat())),
            card_refs=[str(ref) for ref in payload.get("card_refs", []) if ref],
        )

    def similarity_score(
        self,
        *,
        domain: str,
        error_code: str,
        category: str,
        normalized_location: str,
        normalized_message: str,
    ) -> float:
        score = 0.0
        if self.domain == domain:
            score += 0.35
        if error_code and self.error_code == error_code:
            score += 0.25
        if category and self.category == category:
            score += 0.15
        if normalized_location and self.normalized_location == normalized_location:
            score += 0.15

        if normalized_message and self.normalized_message:
            current_tokens = set(_WORD_RE.findall(normalized_message.lower()))
            entry_tokens = set(_WORD_RE.findall(self.normalized_message.lower()))
            if current_tokens and entry_tokens:
                overlap = len(current_tokens & entry_tokens)
                denom = max(1, min(len(current_tokens), len(entry_tokens)))
                score += 0.10 * (overlap / denom)
        return min(1.0, score)


@dataclass(slots=True)
class FailurePatternIndex:
    """In-memory failure pattern index persisted as canonical JSON in CAS."""

    entries: list[FailureIndexEntry] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_failure(
        self,
        *,
        signature_id: str,
        error_code: str,
        category: str,
        domain: str,
        source_step: str,
        normalized_location: str,
        normalized_message: str,
        remediation_advice: str,
        card_ref: str,
    ) -> FailureIndexEntry:
        now = datetime.now(timezone.utc).isoformat()
        for entry in self.entries:
            if entry.signature_id != signature_id:
                continue
            entry.occurrence_count += 1
            entry.last_seen = now
            if card_ref and card_ref not in entry.card_refs:
                entry.card_refs.append(card_ref)
                if len(entry.card_refs) > _MAX_CARD_REFS:
                    entry.card_refs = entry.card_refs[-_MAX_CARD_REFS:]
            if remediation_advice and not entry.remediation_advice:
                entry.remediation_advice = remediation_advice[:500]
            self.updated_at = now
            return entry

        entry = FailureIndexEntry(
            signature_id=signature_id,
            error_code=error_code,
            category=category,
            domain=domain,
            source_step=source_step,
            normalized_location=normalized_location,
            normalized_message=normalized_message,
            remediation_advice=remediation_advice[:500],
            card_refs=[card_ref] if card_ref else [],
        )
        self.entries.append(entry)
        self.updated_at = now
        return entry

    def search(
        self,
        *,
        domain: str,
        error_code: str = "",
        category: str = "",
        location: str = "",
        message: str = "",
        min_similarity: float = 0.25,
        top_k: int = 5,
        min_occurrence: int = 1,
    ) -> list[tuple[FailureIndexEntry, float]]:
        normalized_location = normalize_location(location)
        normalized_message = normalize_message(message)

        scored: list[tuple[FailureIndexEntry, float]] = []
        for entry in self.entries:
            if entry.occurrence_count < min_occurrence:
                continue
            score = entry.similarity_score(
                domain=domain,
                error_code=error_code,
                category=category,
                normalized_location=normalized_location,
                normalized_message=normalized_message,
            )
            if score >= min_similarity:
                scored.append((entry, score))

        scored.sort(key=lambda item: (-item[1], -item[0].occurrence_count, item[0].last_seen))
        return scored[:top_k]

    def top_patterns(self, n: int = 10) -> list[FailureIndexEntry]:
        return sorted(self.entries, key=lambda item: (-item.occurrence_count, item.last_seen))[:n]

    def garbage_collect(self, *, max_age_days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, max_age_days))
        before = len(self.entries)
        kept: list[FailureIndexEntry] = []
        for entry in self.entries:
            try:
                ts = datetime.fromisoformat(entry.last_seen)
            except ValueError:
                continue
            if ts >= cutoff:
                kept.append(entry)
        self.entries = kept
        removed = before - len(kept)
        if removed:
            self.updated_at = datetime.now(timezone.utc).isoformat()
        return removed

    def persist(self, cas: FileSystemCAS) -> str:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "updated_at": self.updated_at,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
        }
        artifact_ref = cas.put_json(
            payload,
            PutOptions(
                kind=FAILURE_INDEX_KIND,
                media_type="application/json",
                schema=FAILURE_INDEX_SCHEMA,
            ),
        )
        return str(artifact_ref.artifact_id)

    @classmethod
    def load(cls, cas: FileSystemCAS, artifact_id: str) -> "FailurePatternIndex":
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
        if not isinstance(payload, dict):
            return cls()
        entries_payload = payload.get("entries", [])
        entries = [
            FailureIndexEntry.from_dict(item)
            for item in entries_payload
            if isinstance(item, dict)
        ]
        return cls(entries=entries, updated_at=str(payload.get("updated_at", "")))

    @classmethod
    def load_or_create(
        cls,
        cas: FileSystemCAS,
        artifact_id: str | None,
    ) -> "FailurePatternIndex":
        if artifact_id:
            try:
                return cls.load(cas, artifact_id)
            except Exception:
                pass
        return cls()


def normalize_location(location: str) -> str:
    if not location:
        return ""
    normalized = _PATH_INDEX_RE.sub("[]", location)
    normalized = _WHITESPACE_RE.sub("", normalized)
    return normalized[:200]


def normalize_message(message: str) -> str:
    if not message:
        return ""
    lowered = message.lower()
    without_numbers = _NUMBER_RE.sub("<n>", lowered)
    normalized = _WHITESPACE_RE.sub(" ", without_numbers).strip()
    return normalized[:500]


def build_failure_signature(
    *,
    error_code: str,
    category: str,
    location: str,
    message: str,
    source_step: str,
    domain: str,
) -> str:
    material = "|".join(
        [
            error_code.strip().lower() or "unknown",
            category.strip().lower() or "unknown",
            normalize_location(location),
            normalize_message(message),
            source_step.strip().lower() or "critic",
            domain.strip().lower() or "general",
        ]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"sig_{digest[:20]}"


__all__ = [
    "FAILURE_INDEX_KIND",
    "FAILURE_INDEX_SCHEMA",
    "FailureIndexEntry",
    "FailurePatternIndex",
    "build_failure_signature",
    "normalize_location",
    "normalize_message",
]
