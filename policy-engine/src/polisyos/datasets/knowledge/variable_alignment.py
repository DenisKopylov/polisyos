"""Variable alignment utilities for canonical SKG vars -> dataset vars."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

import yaml
from pydantic import BaseModel, ConfigDict


class AlignmentMethod(str, Enum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    META_ANALYTIC = "meta_analytic"


class VariableAlignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_var: str
    dataset_var: str
    dataset_id: str
    method: AlignmentMethod
    confidence: float
    evidence: str
    is_proxy: bool = False
    proxy_penalty: float = 0.0


def load_seed_alignments(path: Path) -> list[VariableAlignment]:
    """Load exact seed alignments from YAML."""
    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    if not isinstance(payload, dict):
        raise ValueError("seed alignments payload must be a mapping")

    raw = payload.get("alignments", [])
    if not isinstance(raw, list):
        raise ValueError("'alignments' must be a list")

    out: list[VariableAlignment] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            VariableAlignment(
                canonical_var=str(item.get("canonical_var", "")).strip(),
                dataset_var=str(item.get("dataset_var", "")).strip(),
                dataset_id=str(item.get("dataset_id", "")).strip(),
                method=AlignmentMethod(str(item.get("method", "exact")).strip().lower()),
                confidence=float(item.get("confidence", 0.0)),
                evidence=str(item.get("evidence", "")).strip(),
                is_proxy=bool(item.get("is_proxy", False)),
                proxy_penalty=float(item.get("proxy_penalty", 0.0)),
            )
        )
    return out


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "of",
        "to",
        "in",
        "on",
        "rate",
        "index",
        "value",
        "score",
        "level",
    }
)
_SEMANTIC_SYNONYMS: dict[str, tuple[str, ...]] = {
    "gdp": ("gross", "domestic", "product"),
    "growth": ("increase", "expansion"),
    "trust": ("confidence", "belief"),
    "institutional": ("institution", "governance"),
    "quality": ("effectiveness", "capacity"),
    "corruption": ("bribery", "graft"),
    "inflation": ("cpi", "price"),
    "unemployment": ("jobless",),
    "informal": ("shadow",),
    "economy": ("economic",),
}
_EVIDENCE_STRENGTH_WEIGHTS: dict[str, float] = {
    "meta_analysis": 0.95,
    "systematic_review": 0.9,
    "rct": 0.9,
    "iv": 0.8,
    "did": 0.75,
    "rdd": 0.75,
    "observational": 0.6,
    "expert": 0.45,
    "unknown": 0.35,
}


def align_semantic(
    *,
    canonical_var: str,
    dataset_id: str,
    candidates: Iterable[str],
    threshold: float = 0.35,
    max_results: int = 5,
) -> list[VariableAlignment]:
    """Deterministic lexical-semantic alignment for dataset variable candidates."""
    canonical_clean = str(canonical_var).strip()
    if not canonical_clean:
        return []

    canonical_tokens = _expand_tokens(_tokenize(canonical_clean))
    scored: list[tuple[float, str]] = []
    for raw in candidates:
        dataset_var = str(raw).strip()
        if not dataset_var:
            continue
        score = _semantic_similarity(
            canonical_tokens=canonical_tokens,
            candidate_tokens=_expand_tokens(_tokenize(dataset_var)),
            canonical_var=canonical_clean,
            dataset_var=dataset_var,
        )
        if score >= float(threshold):
            scored.append((score, dataset_var))

    scored.sort(key=lambda item: (-item[0], item[1]))
    out: list[VariableAlignment] = []
    for score, dataset_var in scored[: max(1, int(max_results))]:
        out.append(
            VariableAlignment(
                canonical_var=canonical_clean,
                dataset_var=dataset_var,
                dataset_id=str(dataset_id).strip(),
                method=AlignmentMethod.SEMANTIC,
                confidence=round(_clamp01(score), 6),
                evidence=(
                    "semantic_jaccard+char_overlap;"
                    f"threshold={float(threshold):.3f};"
                    f"score={float(score):.6f}"
                ),
            )
        )
    return out


def align_meta_analytic(
    *,
    canonical_var: str,
    dataset_id: str,
    candidates: Iterable[dict[str, Any] | tuple[str, float]],
    min_confidence: float = 0.3,
    max_results: int = 5,
) -> list[VariableAlignment]:
    """Rank alignments using deterministic meta-analytic evidence features."""
    canonical_clean = str(canonical_var).strip()
    if not canonical_clean:
        return []

    scored: list[tuple[float, str, str]] = []
    for item in candidates:
        parsed = _parse_meta_candidate(item)
        if parsed is None:
            continue
        dataset_var, corr, evidence_strength, n_studies, trust_score = parsed
        strength_weight = _EVIDENCE_STRENGTH_WEIGHTS.get(
            evidence_strength,
            _EVIDENCE_STRENGTH_WEIGHTS["unknown"],
        )
        study_bonus = min(0.1, max(0.0, float(n_studies)) / 50.0)
        trust_clamped = _clamp01(float(trust_score))
        confidence = _clamp01(
            (0.55 * abs(float(corr)))
            + (0.25 * strength_weight)
            + (0.15 * trust_clamped)
            + study_bonus
        )
        if confidence < float(min_confidence):
            continue
        evidence = (
            "meta_analytic_score;"
            f"corr={float(corr):.4f};"
            f"strength={evidence_strength};"
            f"n_studies={int(n_studies)};"
            f"trust={trust_clamped:.4f}"
        )
        scored.append((confidence, dataset_var, evidence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    out: list[VariableAlignment] = []
    for confidence, dataset_var, evidence in scored[: max(1, int(max_results))]:
        out.append(
            VariableAlignment(
                canonical_var=canonical_clean,
                dataset_var=dataset_var,
                dataset_id=str(dataset_id).strip(),
                method=AlignmentMethod.META_ANALYTIC,
                confidence=round(_clamp01(confidence), 6),
                evidence=evidence,
            )
        )
    return out


def _tokenize(text: str) -> set[str]:
    tokens = {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token and token not in _STOPWORDS
    }
    return tokens


def _expand_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        expanded.update(_SEMANTIC_SYNONYMS.get(token, ()))
    return expanded


def _semantic_similarity(
    *,
    canonical_tokens: set[str],
    candidate_tokens: set[str],
    canonical_var: str,
    dataset_var: str,
) -> float:
    if canonical_var.strip().lower() == dataset_var.strip().lower():
        return 1.0
    if not canonical_tokens or not candidate_tokens:
        return 0.0
    intersect = canonical_tokens.intersection(candidate_tokens)
    union = canonical_tokens.union(candidate_tokens)
    jaccard = float(len(intersect)) / float(len(union))
    char_overlap = _char_overlap_ratio(canonical_var, dataset_var)
    return _clamp01(0.7 * jaccard + 0.3 * char_overlap)


def _char_overlap_ratio(left: str, right: str) -> float:
    left_clean = "".join(ch for ch in left.lower() if ch.isalnum())
    right_clean = "".join(ch for ch in right.lower() if ch.isalnum())
    if not left_clean or not right_clean:
        return 0.0
    right_set = set(right_clean)
    overlap = sum(1 for ch in left_clean if ch in right_set)
    return float(overlap) / float(len(left_clean))


def _parse_meta_candidate(
    item: dict[str, Any] | tuple[str, float],
) -> tuple[str, float, str, int, float] | None:
    if isinstance(item, tuple):
        if len(item) < 2:
            return None
        dataset_var = str(item[0]).strip()
        if not dataset_var:
            return None
        try:
            corr = float(item[1])
        except Exception:
            return None
        return dataset_var, corr, "unknown", 0, 0.5

    if not isinstance(item, dict):
        return None

    dataset_var = str(item.get("dataset_var") or item.get("raw_variable") or "").strip()
    if not dataset_var:
        return None

    corr_raw = item.get("correlation", item.get("corr", item.get("effect_size")))
    if corr_raw is None and item.get("confidence") is not None:
        # Fallback for candidates that provide only confidence-like score.
        corr_raw = item.get("confidence")
    try:
        corr = float(corr_raw)
    except Exception:
        return None

    evidence_strength = str(item.get("evidence_strength", "unknown")).strip().lower() or "unknown"
    n_studies_raw = item.get("n_studies", item.get("study_count", 0))
    trust_raw = item.get("trust_score", item.get("quality", 0.5))
    try:
        n_studies = int(n_studies_raw)
    except Exception:
        n_studies = 0
    try:
        trust_score = float(trust_raw)
    except Exception:
        trust_score = 0.5
    return dataset_var, corr, evidence_strength, max(0, n_studies), trust_score


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


__all__ = [
    "AlignmentMethod",
    "VariableAlignment",
    "load_seed_alignments",
    "align_semantic",
    "align_meta_analytic",
]
