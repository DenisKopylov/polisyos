"""Variable alignment utilities for canonical SKG vars -> dataset vars."""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Iterable


class AlignmentMethod(str, Enum):
    """Alignment method public type."""

    EXACT = "exact"
    SEMANTIC = "semantic"
    META_ANALYTIC = "meta_analytic"


class VariableAlignment(BaseModel):
    """Variable alignment public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_var: str
    dataset_var: str
    dataset_id: str
    method: AlignmentMethod
    confidence: float
    evidence: str
    is_proxy: bool = False
    proxy_penalty: float = 0.0


class VariablePairAlignmentScore(BaseModel):
    """Variable pair alignment score public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left_variable: str
    right_variable: str
    exact_name_match: bool = False
    semantic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    definition_score: float = Field(default=0.0, ge=0.0, le=1.0)
    unit_compatibility_score: float = Field(default=0.0, ge=0.0, le=1.0)
    seed_support_score: float = Field(default=0.0, ge=0.0, le=1.0)
    shared_canonical_vars: list[str] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


def default_seed_alignments_path() -> Path:
    """Default seed alignments path helper."""
    return (
        Path(__file__).resolve().parents[4]
        / "data"
        / "dataset_catalog"
        / "seed_variable_alignments.yaml"
    )


_LEGACY_CANONICAL_VAR_ALIASES: dict[str, str] = {
    "alcohol_consumption": "health.alcohol_consumption",
    "at_risk_of_poverty": "social.at_risk_of_poverty",
    "avg_income": "economic.average_income",
    "fdi_inflows": "economic.fdi_inflows",
    "gdp": "economic.gdp",
    "gov_balance": "economic.fiscal_balance",
    "population": "demographic.population",
    "r_and_d_spending": "economic.r_and_d_spending",
    "urbanization_rate": "demographic.urbanization_rate",
}


@lru_cache(maxsize=1)
def _approved_canonical_registry() -> tuple[frozenset[str], frozenset[str], dict[str, str]]:
    from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
    from polisyos.academic.knowledge.runtime_canonical_registry import (
        runtime_approved_synonyms,
        runtime_canonical_names,
    )

    seed_names: set[str] = set()
    for root, children in CANONICAL_VARIABLES.items():
        seed_names.add(root)
        for child in children:
            if child == "_root":
                continue
            seed_names.add(f"{root}.{child}")

    runtime_names = runtime_canonical_names()
    namespace = frozenset(seed_names | runtime_names)
    return namespace, frozenset(runtime_names), runtime_approved_synonyms()


def _normalize_seed_canonical_var(name: str) -> str:
    clean = str(name or "").strip()
    if not clean:
        return ""

    namespace, runtime_names, runtime_synonyms = _approved_canonical_registry()
    if clean in namespace:
        return clean

    if clean in _LEGACY_CANONICAL_VAR_ALIASES:
        return _LEGACY_CANONICAL_VAR_ALIASES[clean]

    lowered = clean.lower()
    spaced = lowered.replace("_", " ")
    if lowered in runtime_synonyms:
        return runtime_synonyms[lowered]
    if spaced in runtime_synonyms:
        return runtime_synonyms[spaced]

    suffix_matches = sorted(
        candidate for candidate in runtime_names if candidate.endswith(f".{clean}")
    )
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    return clean


def calibrate_alignment_confidence(alignment: VariableAlignment) -> float:
    """Normalize confidence values across alignment methods."""
    if alignment.method is AlignmentMethod.EXACT:
        return 1.0
    if alignment.method is AlignmentMethod.SEMANTIC:
        return round(_clamp01(0.5 + 0.5 * float(alignment.confidence)), 6)
    if alignment.method is AlignmentMethod.META_ANALYTIC:
        return round(_clamp01(float(alignment.confidence)), 6)
    return round(_clamp01(float(alignment.confidence)), 6)


def load_seed_alignments(path: Path) -> list[VariableAlignment]:
    """Load exact seed alignments from YAML."""
    with open(path, encoding="utf-8") as fh:
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
                canonical_var=_normalize_seed_canonical_var(
                    str(item.get("canonical_var", "")).strip()
                ),
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


def score_variable_pair(
    *,
    left_name: str,
    right_name: str,
    left_definition: str = "",
    right_definition: str = "",
    left_unit: str | None = None,
    right_unit: str | None = None,
    seed_alignments: Iterable[VariableAlignment] | None = None,
    seed_path: Path | None = None,
) -> VariablePairAlignmentScore:
    """Score variable pair helper."""
    left_clean = str(left_name).strip()
    right_clean = str(right_name).strip()
    if not left_clean or not right_clean:
        return VariablePairAlignmentScore(left_variable=left_clean, right_variable=right_clean)

    exact_name_match = left_clean.lower() == right_clean.lower()
    semantic_score = _semantic_similarity(
        canonical_tokens=_expand_tokens(_tokenize(left_clean)),
        candidate_tokens=_expand_tokens(_tokenize(right_clean)),
        canonical_var=left_clean,
        dataset_var=right_clean,
    )
    definition_score = _definition_similarity(left_definition, right_definition)
    unit_compatibility_score = _unit_compatibility_score(left_unit, right_unit)
    canonical_vars, seed_support_score, seed_evidence = _seed_alignment_support(
        left_name=left_clean,
        right_name=right_clean,
        seed_alignments=seed_alignments,
        seed_path=seed_path,
    )
    overall_score = _clamp01(
        (0.5 * semantic_score)
        + (0.2 * definition_score)
        + (0.15 * unit_compatibility_score)
        + (0.15 * seed_support_score)
    )

    evidence: list[str] = []
    if exact_name_match:
        evidence.append("exact_name_match")
    if definition_score > 0.0:
        evidence.append(f"definition_overlap={definition_score:.3f}")
    if unit_compatibility_score > 0.0:
        evidence.append(f"unit_compatibility={unit_compatibility_score:.3f}")
    if seed_evidence:
        evidence.extend(seed_evidence)

    return VariablePairAlignmentScore(
        left_variable=left_clean,
        right_variable=right_clean,
        exact_name_match=exact_name_match,
        semantic_score=round(_clamp01(semantic_score), 6),
        definition_score=round(_clamp01(definition_score), 6),
        unit_compatibility_score=round(_clamp01(unit_compatibility_score), 6),
        seed_support_score=round(_clamp01(seed_support_score), 6),
        shared_canonical_vars=canonical_vars,
        overall_score=round(_clamp01(overall_score), 6),
        evidence=evidence,
    )


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
        token for token in _TOKEN_RE.findall(text.lower()) if token and token not in _STOPWORDS
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


def _definition_similarity(left_definition: str, right_definition: str) -> float:
    left_tokens = _expand_tokens(_tokenize(str(left_definition).strip()))
    right_tokens = _expand_tokens(_tokenize(str(right_definition).strip()))
    if not left_tokens or not right_tokens:
        return 0.0
    return _semantic_similarity(
        canonical_tokens=left_tokens,
        candidate_tokens=right_tokens,
        canonical_var=str(left_definition),
        dataset_var=str(right_definition),
    )


def _normalize_unit(value: str | None) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "%": "percent",
        "pct": "percent",
        "percentage": "percent",
        "yrs": "years",
        "yr": "years",
    }
    return aliases.get(text, text)


def _unit_compatibility_score(left_unit: str | None, right_unit: str | None) -> float:
    left = _normalize_unit(left_unit)
    right = _normalize_unit(right_unit)
    if not left or not right:
        return 0.5 if (left or right) else 0.25
    if left == right:
        return 1.0
    return 0.0


def _seed_alignment_support(
    *,
    left_name: str,
    right_name: str,
    seed_alignments: Iterable[VariableAlignment] | None,
    seed_path: Path | None,
) -> tuple[list[str], float, list[str]]:
    alignments = (
        list(seed_alignments)
        if seed_alignments is not None
        else load_seed_alignments((seed_path or default_seed_alignments_path()).resolve())
    )
    alias_index = _seed_alias_index(alignments)
    left_aliases = alias_index.get(_normalize_alias(left_name), [])
    right_aliases = alias_index.get(_normalize_alias(right_name), [])
    shared = sorted(set(left_aliases).intersection(right_aliases))
    if not shared:
        return [], 0.0, []

    proxy_supported = any(
        item.is_proxy
        for item in alignments
        if item.canonical_var in shared
        and _normalize_alias(item.dataset_var)
        in {_normalize_alias(left_name), _normalize_alias(right_name)}
    )
    support_score = 0.85 if proxy_supported else 1.0
    evidence = [f"seed_canonical={canonical}" for canonical in shared]
    if proxy_supported:
        evidence.append("seed_proxy_support")
    return shared, support_score, evidence


def _normalize_alias(value: str) -> str:
    tokens = sorted(_tokenize(str(value)))
    if not tokens:
        return str(value).strip().lower()
    return "_".join(tokens)


def _seed_alias_index(alignments: Iterable[VariableAlignment]) -> dict[str, list[str]]:
    index: dict[str, set[str]] = {}
    for item in alignments:
        index.setdefault(_normalize_alias(item.canonical_var), set()).add(item.canonical_var)
        index.setdefault(_normalize_alias(item.dataset_var), set()).add(item.canonical_var)
    return {key: sorted(values) for key, values in index.items()}


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
        except (TypeError, ValueError):
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
    except (TypeError, ValueError):
        return None

    evidence_strength = str(item.get("evidence_strength", "unknown")).strip().lower() or "unknown"
    n_studies_raw = item.get("n_studies", item.get("study_count", 0))
    trust_raw = item.get("trust_score", item.get("quality", 0.5))
    try:
        n_studies = int(n_studies_raw)
    except (TypeError, ValueError):
        n_studies = 0
    try:
        trust_score = float(trust_raw)
    except (TypeError, ValueError):
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
    "VariablePairAlignmentScore",
    "align_meta_analytic",
    "align_semantic",
    "default_seed_alignments_path",
    "load_seed_alignments",
    "score_variable_pair",
]
