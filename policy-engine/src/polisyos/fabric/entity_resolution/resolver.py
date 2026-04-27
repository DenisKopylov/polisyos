"""Probabilistic entity resolution across heterogeneous statistical sources."""

from __future__ import annotations

import re
from itertools import combinations

from .models import EntityMatchCandidate, EntityMatchEvidence, EntityRecord

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {"the", "of", "and", "for", "in", "on"}


def _normalize_tokens(value: str) -> set[str]:
    return {
        match.group(0)
        for match in _TOKEN_RE.finditer(value.lower())
        if match.group(0) not in _STOPWORDS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


class ProbabilisticEntityResolver:
    """Explainable pairwise entity resolver for small-to-medium multi-source batches."""

    def __init__(
        self,
        *,
        method: str = "probabilistic_name_identifier_v1",
        max_pairs: int = 100_000,
        max_candidates: int = 10_000,
    ) -> None:
        self._method = method
        self._max_pairs = max(1, max_pairs)
        self._max_candidates = max(1, max_candidates)

    @property
    def method(self) -> str:
        return self._method

    def resolve(
        self,
        records: list[EntityRecord],
        *,
        min_confidence: float = 0.55,
        max_pairs: int | None = None,
        max_candidates: int | None = None,
    ) -> list[EntityMatchCandidate]:
        matches: list[EntityMatchCandidate] = []
        pair_limit = self._max_pairs if max_pairs is None else max(1, max_pairs)
        candidate_limit = (
            self._max_candidates if max_candidates is None else max(1, max_candidates)
        )
        pairs_seen = 0
        for left, right in combinations(records, 2):
            if pairs_seen >= pair_limit:
                break
            pairs_seen += 1
            if left.source == right.source:
                continue
            candidate = self._compare_pair(left, right)
            if candidate.confidence < min_confidence:
                continue
            self._retain_candidate(matches, candidate, candidate_limit)
        matches.sort(key=lambda item: (-item.confidence, item.match_id))
        return matches

    @staticmethod
    def _retain_candidate(
        matches: list[EntityMatchCandidate],
        candidate: EntityMatchCandidate,
        limit: int,
    ) -> None:
        if len(matches) < limit:
            matches.append(candidate)
            return
        worst_index, worst = max(
            enumerate(matches),
            key=lambda item: (-item[1].confidence, item[1].match_id),
        )
        if (-candidate.confidence, candidate.match_id) < (-worst.confidence, worst.match_id):
            matches[worst_index] = candidate

    def _compare_pair(self, left: EntityRecord, right: EntityRecord) -> EntityMatchCandidate:
        left_names = {left.canonical_name, *left.aliases}
        right_names = {right.canonical_name, *right.aliases}
        left_name_tokens = set().union(*(_normalize_tokens(value) for value in left_names if value))
        right_name_tokens = set().union(
            *(_normalize_tokens(value) for value in right_names if value)
        )
        name_score = _jaccard(left_name_tokens, right_name_tokens)

        identifier_pairs = {
            (key.lower(), value.strip().lower())
            for key, value in left.identifiers.items()
            if value.strip()
        }
        right_identifier_pairs = {
            (key.lower(), value.strip().lower())
            for key, value in right.identifiers.items()
            if value.strip()
        }
        shared_identifiers = sorted(identifier_pairs & right_identifier_pairs)
        identifier_score = 1.0 if shared_identifiers else 0.0

        left_attributes = {
            (key.lower(), value.strip().lower())
            for key, value in left.attributes.items()
            if value.strip()
        }
        right_attributes = {
            (key.lower(), value.strip().lower())
            for key, value in right.attributes.items()
            if value.strip()
        }
        shared_attributes = sorted(left_attributes & right_attributes)
        attribute_score = min(1.0, len(shared_attributes) / 3.0) if shared_attributes else 0.0

        confidence = min(1.0, name_score * 0.55 + identifier_score * 0.35 + attribute_score * 0.10)
        evidence: list[EntityMatchEvidence] = [
            EntityMatchEvidence(
                evidence_type="name_similarity",
                detail="shared_tokens="
                + ",".join(sorted(left_name_tokens & right_name_tokens)[:8]),
                score=name_score,
            )
        ]
        if shared_identifiers:
            evidence.append(
                EntityMatchEvidence(
                    evidence_type="identifier_overlap",
                    detail="shared_identifiers="
                    + ",".join(f"{key}:{value}" for key, value in shared_identifiers),
                    score=identifier_score,
                )
            )
        if shared_attributes:
            evidence.append(
                EntityMatchEvidence(
                    evidence_type="attribute_overlap",
                    detail="shared_attributes="
                    + ",".join(f"{key}:{value}" for key, value in shared_attributes),
                    score=attribute_score,
                )
            )

        return EntityMatchCandidate(
            match_id=EntityMatchCandidate.build_match_id(
                left.entity_id,
                right.entity_id,
                method=self._method,
            ),
            left_entity_id=left.entity_id,
            right_entity_id=right.entity_id,
            left_source=left.source,
            right_source=right.source,
            confidence=confidence,
            method=self._method,
            evidence=evidence,
        )


__all__ = ["ProbabilisticEntityResolver"]
