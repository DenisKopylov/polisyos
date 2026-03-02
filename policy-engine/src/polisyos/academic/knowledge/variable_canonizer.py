"""Deterministic hierarchical variable canonization for academic SKG."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES

_CANONICAL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){0,3}$")


class VariableCanonizer:
    """Deterministic variable canonizer with optional DuckDB-backed cache."""

    def __init__(
        self,
        *,
        db_path: Path | None = None,
        initial_cache: dict[str, str] | None = None,
    ) -> None:
        self._reverse: dict[str, str] = {}
        self._cache: dict[str, str] = dict(initial_cache or {})
        self._pending_review: list[tuple[str, str]] = []
        self._db_path = db_path

        self._build_reverse_index()
        if self._db_path is not None:
            self._load_cache_from_db()

    def _build_reverse_index(self) -> None:
        for parent, children in CANONICAL_VARIABLES.items():
            for child_key, synonyms in children.items():
                canonical = parent if child_key == "_root" else f"{parent}.{child_key}"
                self._reverse[canonical.lower()] = canonical
                for syn in synonyms:
                    normalized_syn = self._normalize(syn)
                    if normalized_syn:
                        self._reverse[normalized_syn] = canonical

    @staticmethod
    def _normalize(raw_name: str) -> str:
        return str(raw_name or "").strip().lower()

    @staticmethod
    def _slugify(raw_name: str) -> str:
        slug = str(raw_name or "").lower().strip()
        slug = re.sub(r"[^a-z0-9._]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        slug = slug.replace("..", ".")
        if not slug:
            return "unknown_variable"

        # Keep hierarchical names up to depth 4.
        parts = [part for part in slug.split(".") if part]
        if not parts:
            return "unknown_variable"

        sanitized: list[str] = []
        for part in parts[:4]:
            part_s = re.sub(r"[^a-z0-9_]+", "_", part)
            part_s = re.sub(r"_+", "_", part_s).strip("_")
            if not part_s:
                continue
            if not re.match(r"^[a-z]", part_s):
                part_s = f"v_{part_s}"
            sanitized.append(part_s[:40])

        if not sanitized:
            return "unknown_variable"

        candidate = ".".join(sanitized)
        if not _CANONICAL_NAME_RE.match(candidate):
            # Last-resort normal form.
            candidate = re.sub(r"[^a-z0-9_]+", "_", candidate)
            candidate = re.sub(r"_+", "_", candidate).strip("_")
            if not candidate:
                candidate = "unknown_variable"
            if not re.match(r"^[a-z]", candidate):
                candidate = f"v_{candidate}"
        return candidate

    def _load_cache_from_db(self) -> None:
        assert self._db_path is not None
        con = duckdb.connect(str(self._db_path))
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ac_skg_canonization_cache (
                    raw_name        VARCHAR PRIMARY KEY,
                    canonical_name  VARCHAR NOT NULL,
                    approved        BOOLEAN DEFAULT FALSE,
                    created_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            rows = con.execute(
                "SELECT raw_name, canonical_name FROM ac_skg_canonization_cache"
            ).fetchall()
            for raw_name, canonical_name in rows:
                if raw_name and canonical_name:
                    self._cache[str(raw_name)] = str(canonical_name)
        finally:
            con.close()

    def _persist_mapping(self, raw_name: str, canonical_name: str, *, approved: bool) -> None:
        if self._db_path is None:
            return
        con = duckdb.connect(str(self._db_path))
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ac_skg_canonization_cache (
                    raw_name        VARCHAR PRIMARY KEY,
                    canonical_name  VARCHAR NOT NULL,
                    approved        BOOLEAN DEFAULT FALSE,
                    created_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            con.execute(
                """
                INSERT OR REPLACE INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
                VALUES (?, ?, ?)
                """,
                [raw_name, canonical_name, approved],
            )
        finally:
            con.close()

    def _fuzzy_match(self, normalized: str, *, threshold: float = 0.85) -> str | None:
        best_score = 0.0
        best_match: str | None = None
        for synonym, canonical in self._reverse.items():
            score = SequenceMatcher(None, normalized, synonym).ratio()
            if score > best_score and score >= threshold:
                best_score = score
                best_match = canonical
        return best_match

    def canonize(self, raw_name: str) -> tuple[str, bool]:
        """Return (canonical_name, is_new)."""
        normalized = self._normalize(raw_name)

        if normalized in self._reverse:
            return self._reverse[normalized], False

        cached = self._cache.get(normalized)
        if cached:
            return cached, False

        fuzzy = self._fuzzy_match(normalized)
        if fuzzy:
            self._cache[normalized] = fuzzy
            self._persist_mapping(normalized, fuzzy, approved=False)
            return fuzzy, True

        fallback = self._slugify(raw_name)
        self._cache[normalized] = fallback
        self._pending_review.append((raw_name, fallback))
        self._persist_mapping(normalized, fallback, approved=False)
        return fallback, True

    def approve_mapping(self, raw_name: str, canonical_name: str) -> None:
        normalized = self._normalize(raw_name)
        canonical = self._slugify(canonical_name)
        self._cache[normalized] = canonical
        self._persist_mapping(normalized, canonical, approved=True)
        self._pending_review = [
            (raw, suggested)
            for raw, suggested in self._pending_review
            if self._normalize(raw) != normalized
        ]

    def get_pending_review(self) -> list[tuple[str, str]]:
        return list(self._pending_review)

    def cache_snapshot(self) -> dict[str, str]:
        return dict(self._cache)


__all__ = ["VariableCanonizer"]
