"""Local canonical variable resolver for academic SKG synthesis."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import duckdb
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.academic.knowledge.runtime_canonical_registry import (
    RuntimeCanonicalEntry,
    runtime_approved_synonyms,
    runtime_canonical_entries,
    runtime_canonical_names,
)
from polisyos.academic.knowledge.skg_store import parent_canonical_name

_AUTO_APPROVE_THRESHOLD = 0.90
_PENDING_REVIEW_THRESHOLD = 0.75


@dataclass(frozen=True)
class ResolutionResult:
    raw_name: str
    canonical_name: str | None
    method: str
    confidence: float
    approved: bool
    review_required: bool


@dataclass
class CanonizationStats:
    exact_matches: int = 0
    synonym_matches: int = 0
    hierarchy_matches: int = 0
    embedding_matches: int = 0
    auto_approved: int = 0
    pending_review: int = 0
    unresolved: int = 0
    total: int = 0

    @property
    def resolution_rate(self) -> float:
        resolved = self.exact_matches + self.synonym_matches + self.hierarchy_matches + self.auto_approved
        return resolved / max(1, self.total)


def _seed_canonical_names() -> set[str]:
    names: set[str] = set()
    for parent, children in CANONICAL_VARIABLES.items():
        names.add(parent)
        for child_key in children:
            if child_key == "_root":
                continue
            names.add(f"{parent}.{child_key}")
    return names


def _seed_approved_synonyms() -> dict[str, str]:
    synonyms: dict[str, str] = {}
    for parent, children in CANONICAL_VARIABLES.items():
        for child_key, alias_list in children.items():
            canonical = parent if child_key == "_root" else f"{parent}.{child_key}"
            for alias in alias_list:
                clean_alias = str(alias or "").strip().lower()
                if clean_alias:
                    synonyms.setdefault(clean_alias, canonical)
    return synonyms


def _canonical_display_text(name: str) -> str:
    return str(name or "").strip().replace(".", " ").replace("_", " ")


def _normalize_text(name: str) -> str:
    return re.sub(r"\s+", " ", _canonical_display_text(name).strip().lower())


def _normalize_token(token: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "", str(token or "").strip().lower())
    if len(clean) > 4 and clean.endswith("ies"):
        return clean[:-3] + "y"
    if len(clean) > 4 and clean.endswith("s"):
        return clean[:-1]
    return clean


def _tokenize(name: str) -> tuple[str, ...]:
    tokens = [_normalize_token(match) for match in re.findall(r"[a-z0-9_]+", _normalize_text(name))]
    return tuple(token for token in tokens if token)


def _token_overlap_score(query_tokens: set[str], candidate_tokens: set[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0
    intersection = len(query_tokens & candidate_tokens)
    union = len(query_tokens | candidate_tokens)
    if union == 0:
        return 0.0
    score = intersection / union
    if query_tokens <= candidate_tokens or candidate_tokens <= query_tokens:
        score = max(score, intersection / max(1, min(len(query_tokens), len(candidate_tokens))))
    return min(score, 1.0)


def _dot_to_seed_alias(name: str) -> str | None:
    clean = str(name or "").strip()
    if clean.count(".") != 1:
        return None
    left, right = clean.split(".", 1)
    if not left or not right:
        return None
    return f"{left}_{right}"


class CanonicalVariableResolver:
    """Resolve raw variable names to approved canonical names using local similarity."""

    def __init__(
        self,
        *,
        approved_names: Iterable[str],
        approved_synonyms: dict[str, str] | None = None,
        runtime_entries: dict[str, RuntimeCanonicalEntry] | None = None,
    ) -> None:
        self._approved_names = sorted({str(item).strip() for item in approved_names if str(item).strip()})
        self._approved_set = set(self._approved_names)
        self._runtime_entries = dict(runtime_entries or {})
        self._runtime_canonical_names = set(self._runtime_entries)
        self._approved_synonyms = {
            str(key).strip().lower(): str(value).strip()
            for key, value in (approved_synonyms or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._stats = CanonizationStats()
        self._unresolved_mentions: Counter[str] = Counter()
        self._synonyms_by_canonical: dict[str, set[str]] = {}
        for synonym, canonical_name in self._approved_synonyms.items():
            self._synonyms_by_canonical.setdefault(canonical_name, set()).add(synonym)
        self._search_texts = [self._search_text_for(name) for name in self._approved_names]
        self._candidate_tokens = [set(_tokenize(text)) for text in self._search_texts]
        self._char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        self._word_vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_]+\b",
        )
        self._char_matrix = (
            self._char_vectorizer.fit_transform(self._search_texts)
            if self._approved_names
            else None
        )
        self._word_matrix = (
            self._word_vectorizer.fit_transform(self._search_texts)
            if self._approved_names
            else None
        )

    @classmethod
    def from_connection(cls, con: duckdb.DuckDBPyConnection) -> "CanonicalVariableResolver":
        approved_names = _seed_canonical_names()
        approved_names.update(runtime_canonical_names())
        try:
            approved_names.update(
                str(row[0])
                for row in con.execute(
                    "SELECT canonical_name FROM ac_skg_canonization_cache WHERE approved = TRUE"
                ).fetchall()
                if row and row[0]
            )
        except duckdb.Error:
            pass
        approved_synonyms = _seed_approved_synonyms()
        approved_synonyms.update(runtime_approved_synonyms())
        try:
            approved_synonyms.update(
                {
                    str(row[0]).strip().lower(): str(row[1]).strip()
                    for row in con.execute(
                        """
                        SELECT synonym, canonical_name
                        FROM ac_skg_variable_synonyms
                        WHERE approved = TRUE
                        """
                    ).fetchall()
                    if row and row[0] and row[1]
                }
            )
        except duckdb.Error:
            pass
        return cls(
            approved_names=approved_names,
            approved_synonyms=approved_synonyms,
            runtime_entries=runtime_canonical_entries(),
        )

    @property
    def stats(self) -> CanonizationStats:
        return self._stats

    @property
    def unresolved_mentions(self) -> Counter[str]:
        return self._unresolved_mentions

    def _search_text_for(self, canonical_name: str) -> str:
        candidates = {
            _normalize_text(canonical_name),
            _normalize_text(_dot_to_seed_alias(canonical_name) or ""),
        }
        candidates.update(_normalize_text(alias) for alias in self._synonyms_by_canonical.get(canonical_name, set()))
        return " ".join(sorted(candidate for candidate in candidates if candidate))

    def _runtime_candidate_boost(
        self,
        candidate_name: str,
        *,
        need_type: str | None,
        runtime_priority: bool | None,
    ) -> float:
        entry = self._runtime_entries.get(candidate_name)
        if entry is None:
            return 0.0
        if runtime_priority:
            return 0.08
        if need_type and need_type in entry.need_types:
            return 0.05
        return 0.02

    def resolve(
        self,
        raw_name: str,
        *,
        need_type: str | None = None,
        runtime_priority: bool | None = None,
    ) -> ResolutionResult:
        clean_raw = str(raw_name or "").strip()
        normalized = clean_raw.lower()
        self._stats.total += 1
        if not clean_raw:
            self._stats.unresolved += 1
            return ResolutionResult(
                raw_name=clean_raw,
                canonical_name=None,
                method="empty",
                confidence=0.0,
                approved=False,
                review_required=True,
            )

        if clean_raw in self._approved_set:
            self._stats.exact_matches += 1
            return ResolutionResult(clean_raw, clean_raw, "exact", 1.0, True, False)

        alias = _dot_to_seed_alias(clean_raw)
        if alias and alias in self._approved_set:
            self._stats.exact_matches += 1
            return ResolutionResult(clean_raw, alias, "exact_alias", 0.99, True, False)

        synonym_match = self._approved_synonyms.get(normalized)
        if synonym_match:
            self._stats.synonym_matches += 1
            return ResolutionResult(clean_raw, synonym_match, "synonym", 1.0, True, False)

        parent = parent_canonical_name(clean_raw)
        while parent:
            if parent in self._approved_set:
                self._stats.hierarchy_matches += 1
                return ResolutionResult(clean_raw, parent, "hierarchy", 0.98, True, False)
            parent = parent_canonical_name(parent)

        if self._char_matrix is not None and self._word_matrix is not None and self._approved_names:
            query_text = _normalize_text(clean_raw)
            query_tokens = set(_tokenize(clean_raw))
            char_query = self._char_vectorizer.transform([query_text])
            word_query = self._word_vectorizer.transform([query_text])
            char_scores = (self._char_matrix @ char_query.T).toarray().reshape(-1)
            word_scores = (self._word_matrix @ word_query.T).toarray().reshape(-1)
            if char_scores.size and word_scores.size:
                combined_scores = []
                for idx, candidate_name in enumerate(self._approved_names):
                    token_score = _token_overlap_score(query_tokens, self._candidate_tokens[idx])
                    char_score = float(char_scores[idx])
                    word_score = float(word_scores[idx])
                    combined = (0.45 * char_score) + (0.35 * word_score) + (0.20 * token_score)
                    if query_tokens and query_tokens <= self._candidate_tokens[idx]:
                        combined += 0.05
                    if query_text and query_text in self._search_texts[idx]:
                        combined += 0.05
                    combined += self._runtime_candidate_boost(
                        candidate_name,
                        need_type=need_type,
                        runtime_priority=runtime_priority,
                    )
                    combined_scores.append(min(combined, 1.0))
                best_idx = int(np.argmax(np.asarray(combined_scores)))
                best_score = float(combined_scores[best_idx])
                best_name = self._approved_names[best_idx]
                pending_threshold = _PENDING_REVIEW_THRESHOLD - (
                    0.05 if runtime_priority and best_name in self._runtime_canonical_names else 0.0
                )
                if best_score >= _AUTO_APPROVE_THRESHOLD:
                    self._stats.embedding_matches += 1
                    self._stats.auto_approved += 1
                    return ResolutionResult(clean_raw, best_name, "embedding", best_score, True, False)
                if best_score >= pending_threshold:
                    self._stats.embedding_matches += 1
                    self._stats.pending_review += 1
                    return ResolutionResult(clean_raw, best_name, "embedding", best_score, False, True)

        self._stats.unresolved += 1
        self._unresolved_mentions[clean_raw] += 1
        return ResolutionResult(clean_raw, None, "unresolved", 0.0, False, True)

    def persist_resolution(
        self,
        con: duckdb.DuckDBPyConnection,
        result: ResolutionResult,
    ) -> None:
        if not result.raw_name:
            return
        if result.canonical_name:
            con.execute(
                """
                INSERT OR REPLACE INTO ac_skg_canonization_cache(raw_name, canonical_name, approved)
                VALUES (?, ?, ?)
                """,
                [result.raw_name.lower(), result.canonical_name, bool(result.approved)],
            )
        if result.method == "embedding" and result.canonical_name:
            con.execute(
                """
                INSERT OR REPLACE INTO ac_skg_variable_synonyms(
                    synonym, canonical_name, method, confidence, approved
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    result.raw_name.lower(),
                    result.canonical_name,
                    "embedding",
                    float(result.confidence),
                    bool(result.approved),
                ],
            )


__all__ = [
    "CanonicalVariableResolver",
    "CanonizationStats",
    "ResolutionResult",
]
