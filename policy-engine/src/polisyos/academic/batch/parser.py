"""Stage: parse OpenAlex raw payloads into normalized academic WorkRecord rows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.academic.knowledge.types import EstimateCandidate, SourceTopicRef, WorkRecord
from polisyos.academic.trust import compute_trust_score
from polisyos.batch_common.manifest import write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.academic.batch.config import AcademicBatchConfig

# ---------------------------------------------------------------------------
# Abstract reconstruction
# ---------------------------------------------------------------------------


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Reconstruct plain text from OpenAlex's inverted abstract index."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in inverted_index.items():
        if not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            if isinstance(pos, int):
                positions.append((pos, word))
    positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in positions)


# ---------------------------------------------------------------------------
# Numerical estimate extraction (regex)
# ---------------------------------------------------------------------------

_ESTIMATE_PATTERNS: list[tuple[str, re.Pattern, dict[str, int]]] = [
    (
        "value_with_confidence_interval",
        re.compile(
            r"(?:effect|coefficient|estimate|impact|change|difference|increase|decrease|reduction|"
            r"odds ratio|risk ratio|hazard ratio)?"
            r"\s*(?:of|is|was|=|:|by)?\s*([+-]?\d+\.?\d*)"
            r"\s*(?:percent|%|pp|percentage\s*points?)?"
            r"\s*\(\s*(?:95%|90%)\s*C[Ii]\s*[:\[{(]?\s*([+-]?\d+\.?\d*)\s*(?:,|;|to|[-–])\s*([+-]?\d+\.?\d*)\s*[\]})]?\s*\)",
            re.IGNORECASE,
        ),
        {"value": 1, "ci_low": 2, "ci_high": 3},
    ),
    (
        "odds_ratio",
        re.compile(
            r"\bOR\s*=?\s*([+-]?\d+\.?\d*)\s*(?:\(\s*95%\s*CI[:\s]*([+-]?\d+\.?\d*)\s*[–\-]\s*([+-]?\d+\.?\d*)\s*\))?",
            re.IGNORECASE,
        ),
        {"value": 1, "ci_low": 2, "ci_high": 3},
    ),
    (
        "risk_ratio",
        re.compile(
            r"\bRR\s*=?\s*([+-]?\d+\.?\d*)\s*(?:\(\s*95%\s*CI[:\s]*([+-]?\d+\.?\d*)\s*[–\-]\s*([+-]?\d+\.?\d*)\s*\))?",
            re.IGNORECASE,
        ),
        {"value": 1, "ci_low": 2, "ci_high": 3},
    ),
    (
        "hazard_ratio",
        re.compile(r"\bHR\s*=?\s*([+-]?\d+\.?\d*)", re.IGNORECASE),
        {"value": 1},
    ),
    (
        "elasticity_of",
        re.compile(
            r"(?:elasticity|effect|coefficient|impact|estimate)[s]?\s+(?:of|is|=|:)\s*([+-]?\d+\.?\d*)",
            re.IGNORECASE,
        ),
        {"value": 1},
    ),
    (
        "beta",
        re.compile(r"(?:β|\bbeta\b)\s*=?\s*([+-]?\d+\.?\d*)", re.IGNORECASE),
        {"value": 1},
    ),
    (
        "beta_se",
        re.compile(
            r"(?:\(?\s*(?:β|\bbeta\b|[bB])\s*=\s*([+-]?\d+\.?\d*)\s*[,;]?\s*"
            r"(?:SE|s\.e\.|std\.?\s*err(?:or)?)\s*=\s*([+-]?\d+\.?\d*)\s*\)?)",
            re.IGNORECASE,
        ),
        {"value": 1, "std_error": 2},
    ),
    (
        "coefficient_se",
        re.compile(
            r"(?:coefficient|coef\.?|estimate|effect|impact)\s*(?:of|is|was|=|:)?\s*([+-]?\d+\.?\d*)"
            r"\s*\(\s*(?:SE|s\.e\.|std\.?\s*err(?:or)?)?\s*=?\s*([+-]?\d+\.?\d*)\s*\)",
            re.IGNORECASE,
        ),
        {"value": 1, "std_error": 2},
    ),
    (
        "value_with_standard_error",
        re.compile(
            r"(?:effect|coefficient|coef\.?|estimate|impact|change|difference|semi-elasticity|elasticity)?"
            r"\s*(?:of|is|was|=|:|by)?\s*([+-]?\d+\.?\d*)"
            r"\s*(?:percent|%|pp|percentage\s*points?)?"
            r"\s*\(\s*(?:standard\s*error|std\.?\s*err(?:or)?|s\.e\.|SE)\s*=?\s*([+-]?\d+\.?\d*)\s*\)",
            re.IGNORECASE,
        ),
        {"value": 1, "std_error": 2},
    ),
    (
        "change_by",
        re.compile(
            r"(?:increase|decrease|reduce|raise|decline|grow)[sd]?\s+by\s+([+-]?\d+\.?\d*)\s*(?:percent|%|pp|percentage\s*points?)",
            re.IGNORECASE,
        ),
        {"value": 1},
    ),
    (
        "change_by_with_standard_error",
        re.compile(
            r"(?:increase|decrease|reduce|raise|decline|grow)[sd]?\s+(?:[a-z][a-z\s-]{0,40}\s+)?by\s+([+-]?\d+\.?\d*)\s*"
            r"(?:percent|%|pp|percentage\s*points?)\s*\(\s*(?:standard\s*error|std\.?\s*err(?:or)?|s\.e\.|SE)\s*=?\s*([+-]?\d+\.?\d*)\s*\)",
            re.IGNORECASE,
        ),
        {"value": 1, "std_error": 2},
    ),
    (
        "change_by_with_confidence_interval",
        re.compile(
            r"(?:increase|decrease|reduce|raise|decline|grow)[sd]?\s+(?:[a-z][a-z\s-]{0,40}\s+)?by\s+([+-]?\d+\.?\d*)\s*"
            r"(?:percent|%|pp|percentage\s*points?)\s*\(\s*(?:95%|90%)\s*C[Ii]\s*[:\[{(]?\s*([+-]?\d+\.?\d*)\s*(?:,|;|to|[-–])\s*([+-]?\d+\.?\d*)\s*[\]})]?\s*\)",
            re.IGNORECASE,
        ),
        {"value": 1, "ci_low": 2, "ci_high": 3},
    ),
    (
        "confidence_interval",
        re.compile(
            r"(?:95%|90%)\s*C[Ii]\s*[\[({:]\s*([+-]?\d+\.?\d*)\s*[,;to ]+\s*([+-]?\d+\.?\d*)\s*[\])}]?",
            re.IGNORECASE,
        ),
        {"ci_low": 1, "ci_high": 2},
    ),
    (
        "range_from_to",
        re.compile(r"ranging\s+from\s+([+-]?\d+\.?\d*)\s+to\s+([+-]?\d+\.?\d*)", re.IGNORECASE),
        {"ci_low": 1, "ci_high": 2},
    ),
]

_TABLE_STDERR_HEADER_RE = re.compile(
    r"(?:estimate\s*\(\s*std\.?\s*error\s*\)|estimated\s+parameters?(?:\s+symbol)?\s+estimate\s*\(\s*std\.?\s*error\s*\)|"
    r"std\.?\s*errors?\s+reported\s+in\s+parentheses)",
    re.IGNORECASE,
)

_TABLE_STDERR_ROW_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9&/,\-–()'\s]{3,80}?)\s+"
    r"(?:[A-Za-zα-ωΑ-Ωβγδφρλμστ]{1,6}\s+)?"
    r"([+-]?\d+\.\d{2,})\s*\(\s*([+-]?\d+\.\d{2,})\s*\)",
    re.IGNORECASE,
)

_SAMPLE_SIZE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bn\s*=\s*([0-9][0-9,_.]*)", re.IGNORECASE),
    re.compile(r"\bN\s*=\s*([0-9][0-9,_.]*)"),
    re.compile(r"sample\s+of\s+([0-9][0-9,_.]*)", re.IGNORECASE),
)

_BOUNDARY_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"in\s+(low|middle|high)[- ]income\s+countries", re.IGNORECASE),
    re.compile(r"in\s+countries\s+with\s+([a-z\-\s]{3,40})", re.IGNORECASE),
    re.compile(
        r"when\s+([a-z\-\s]{2,30})\s+(?:exceeds?|is\s+above|is\s+below)\s+([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    ),
    re.compile(r"effects?\s+are\s+larger\s+during\s+([a-z\-\s]{3,30})", re.IGNORECASE),
)


def extract_sample_size(abstract: str) -> int | None:
    """Extract sample size helper."""
    if not abstract:
        return None
    for pattern in _SAMPLE_SIZE_PATTERNS:
        m = pattern.search(abstract)
        if not m:
            continue
        raw = m.group(1).replace(",", "").replace("_", "")
        try:
            return int(float(raw))
        except ValueError:
            continue
    return None


def extract_numerical_estimates(
    abstract: str, concepts: list[str] | None = None
) -> list[EstimateCandidate]:
    """Extract numerical estimates from an abstract using regex patterns."""
    if not abstract:
        return []

    estimates: list[EstimateCandidate] = []
    for pattern_name, pattern, groups in _ESTIMATE_PATTERNS:
        for match in pattern.finditer(abstract):
            value = None
            ci_low = None
            ci_high = None
            std_error = None

            if "value" in groups:
                try:
                    value = float(match.group(groups["value"]))
                except (ValueError, IndexError, TypeError):
                    value = None
            if "ci_low" in groups:
                try:
                    ci_low = float(match.group(groups["ci_low"]))
                except (ValueError, IndexError, TypeError):
                    ci_low = None
            if "ci_high" in groups:
                try:
                    ci_high = float(match.group(groups["ci_high"]))
                except (ValueError, IndexError, TypeError):
                    ci_high = None
            if "std_error" in groups:
                try:
                    std_error = float(match.group(groups["std_error"]))
                except (ValueError, IndexError, TypeError):
                    std_error = None

            if value is None and ci_low is not None and ci_high is not None:
                value = (ci_low + ci_high) / 2
            if value is None:
                continue

            start = max(0, match.start() - 120)
            end = min(len(abstract), match.end() + 120)
            context = abstract[start:end]
            unit = _detect_unit(context)
            estimates.append(
                EstimateCandidate(
                    value=value,
                    ci_low=ci_low,
                    ci_high=ci_high,
                    std_error=std_error,
                    unit=unit,
                    context_snippet=context,
                    pattern_name=pattern_name,
                    confidence=0.75 if ci_low is not None and ci_high is not None else 0.55,
                    variable_hint=concepts[0] if concepts else "",
                )
            )
    estimates.extend(_extract_table_estimates(abstract, concepts=concepts))
    return estimates


def _extract_table_estimates(
    text: str, concepts: list[str] | None = None
) -> list[EstimateCandidate]:
    if not text or not _TABLE_STDERR_HEADER_RE.search(text):
        return []

    estimates: list[EstimateCandidate] = []
    seen: set[tuple[str, float, float]] = set()
    for match in _TABLE_STDERR_ROW_RE.finditer(text):
        label = re.sub(r"\s+", " ", str(match.group(1) or "")).strip(" ,;:-")
        if not label:
            continue
        lowered = label.lower()
        if lowered.startswith(("table ", "panel ", "column ", "col ")):
            continue
        try:
            value = float(match.group(2))
            std_error = float(match.group(3))
        except (TypeError, ValueError):
            continue
        key = (label.lower(), value, std_error)
        if key in seen:
            continue
        seen.add(key)
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        context = text[start:end]
        unit = _detect_unit(context)
        estimates.append(
            EstimateCandidate(
                value=value,
                std_error=std_error,
                unit=unit,
                context_snippet=context,
                pattern_name="table_estimate_std_error",
                confidence=0.72,
                variable_hint=label or (concepts[0] if concepts else ""),
            )
        )
    return estimates


def _detect_unit(context: str) -> str:
    lowered = context.lower()
    if "odds ratio" in lowered or re.search(r"\bOR\b", context):
        return "odds_ratio"
    if "risk ratio" in lowered or re.search(r"\bRR\b", context):
        return "risk_ratio"
    if "hazard ratio" in lowered or re.search(r"\bHR\b", context):
        return "hazard_ratio"
    if "percentage point" in lowered or " pp" in lowered:
        return "pp"
    if "semi-elasticity" in lowered or "semi elasticity" in lowered:
        return "semi_elasticity"
    if "elasticity" in lowered:
        return "elasticity"
    if "beta" in lowered or "standardized" in lowered or "standardised" in lowered:
        return "standardized_effect"
    if "percent" in lowered or "%" in context:
        return "percent"
    return ""


# ---------------------------------------------------------------------------
# Study design + causal claims
# ---------------------------------------------------------------------------

_DESIGN_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("meta-analysis", re.compile(r"meta.?analy", re.IGNORECASE)),
    ("systematic_review", re.compile(r"systematic\s+review", re.IGNORECASE)),
    ("rct", re.compile(r"randomiz|RCT|random\s+assignment|random\s+allocation", re.IGNORECASE)),
    ("iv", re.compile(r"instrumental\s+variable|\bIV\b\s+estimat|2SLS|TSLS", re.IGNORECASE)),
    ("did", re.compile(r"difference.?in.?difference|\bDiD\b|diff.?in.?diff", re.IGNORECASE)),
    ("rdd", re.compile(r"regression\s+discontinuity|\bRDD\b|\bRD\s+design", re.IGNORECASE)),
    ("fe", re.compile(r"fixed\s+effect|panel\s+data|within.?estimator", re.IGNORECASE)),
    ("ols", re.compile(r"\bOLS\b|ordinary\s+least\s+squares|linear\s+regression", re.IGNORECASE)),
]

_CAUSAL_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"effect\s+of\s+([A-Za-z\s\-]{3,40})\s+on\s+([A-Za-z\s\-]{3,40})", re.IGNORECASE),
    re.compile(
        r"([A-Za-z][A-Za-z\s\-]{3,30})\s+(increases?|decreases?|reduces?|raises?|lowers?)\s+([A-Za-z\s\-]{3,40})",
        re.IGNORECASE,
    ),
)


def classify_study_design(abstract: str) -> str:
    """Classify study design from abstract text. Returns most rigorous match."""
    if not abstract:
        return ""
    for design, pattern in _DESIGN_PATTERNS:
        if pattern.search(abstract):
            return design
    return ""


def extract_causal_claims(abstract: str) -> list[dict]:
    """Extract causal claims helper."""
    if not abstract:
        return []
    claims: list[dict] = []
    for pattern in _CAUSAL_PATTERNS:
        for m in pattern.finditer(abstract):
            groups = [g.strip() for g in m.groups() if g and g.strip()]
            if len(groups) < 2:
                continue
            if len(groups) == 2:
                cause, effect = groups
                verb = ""
            else:
                cause, verb, effect = groups[0], groups[1], groups[2]
            verb_l = verb.lower()
            if any(v in verb_l for v in ("decrease", "reduce", "lower")):
                direction = "negative"
            elif any(v in verb_l for v in ("increase", "raise", "boost")):
                direction = "positive"
            else:
                direction = "mixed"
            claims.append(
                {
                    "cause": cause,
                    "effect": effect,
                    "direction": direction,
                    "strength": "moderate",
                    "mechanism": "",
                }
            )
    return claims


def extract_boundary_conditions(abstract: str) -> list[dict]:
    """Extract boundary conditions helper."""
    if not abstract:
        return []
    rows: list[dict] = []
    for pattern in _BOUNDARY_PATTERNS:
        for m in pattern.finditer(abstract):
            text = m.group(0)
            rows.append(
                {
                    "variable": "",
                    "operator": "",
                    "threshold_value": "",
                    "scope_text": text,
                    "confidence": 0.45,
                }
            )
    return rows


# ---------------------------------------------------------------------------
# Context inference
# ---------------------------------------------------------------------------

_HIGH_INCOME_CODES = {
    "US",
    "CA",
    "GB",
    "DE",
    "FR",
    "NL",
    "SE",
    "NO",
    "FI",
    "DK",
    "CH",
    "AT",
    "BE",
    "AU",
    "NZ",
    "JP",
    "KR",
    "SG",
    "IE",
}


def infer_context_profile(work: dict[str, Any], abstract: str) -> dict:
    """Infer context profile helper."""
    countries: list[str] = []
    authorships = work.get("authorships")
    if isinstance(authorships, list):
        for a in authorships:
            if not isinstance(a, dict):
                continue
            institutions = a.get("institutions")
            if not isinstance(institutions, list):
                continue
            for inst in institutions:
                if not isinstance(inst, dict):
                    continue
                cc = str(inst.get("country_code") or "").upper()
                if cc and cc not in countries:
                    countries.append(cc)

    context_id = countries[0] if countries else ""
    income_level = "unknown"
    if context_id:
        income_level = "high" if context_id in _HIGH_INCOME_CODES else "non_high"

    return {
        "context_id": context_id,
        "context_label": context_id,
        "countries": countries,
        "income_level": income_level,
        "publication_year": int(work.get("publication_year") or 0),
        "inference_level": "inferred_basic",
        "data_sources": ["openalex_affiliations", "openalex_metadata"],
    }


# ---------------------------------------------------------------------------
# Parser stage
# ---------------------------------------------------------------------------


def _latest_snapshot_dir(root: Path) -> Path | None:
    if not root.exists():
        return None
    dirs = sorted([p for p in root.iterdir() if p.is_dir()])
    return dirs[-1] if dirs else None


def _iter_payloads(config: AcademicBatchConfig) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    # Topic mode: any raw topic folder.
    for root in sorted([p for p in config.raw_dir.iterdir() if p.is_dir()]):
        latest = _latest_snapshot_dir(root)
        if latest is None:
            continue
        payload = latest / "payload.jsonl"
        if payload.exists():
            out.append((root.name, payload))
    return out


def _build_source_topic(row: dict[str, Any]) -> SourceTopicRef | None:
    topic_id = str(row.get("topic_id") or "")
    if not topic_id:
        return None
    return SourceTopicRef(
        topic_id=topic_id,
        topic_display_name=str(row.get("topic_display_name") or ""),
        policy_block=str(row.get("topic_policy_block") or ""),
        policy_subblock=str(row.get("topic_policy_subblock") or ""),
        source_file=str(row.get("source_file") or ""),
        rank=int(row.get("rank") or 0),
        selection_score=float(row.get("selection_score") or 0.0),
        batch_origin=str(row.get("batch_origin") or ""),
        selected_at=str(row.get("selected_at") or ""),
    )


def _method_signal_score(
    study_design: str, estimates: list[EstimateCandidate], causal_claims: list[dict]
) -> float:
    base = {
        "meta-analysis": 1.0,
        "meta_analysis": 1.0,
        "systematic_review": 0.95,
        "rct": 0.9,
        "iv": 0.8,
        "did": 0.75,
        "rdd": 0.75,
        "fe": 0.6,
        "ols": 0.4,
    }.get(study_design, 0.25)
    if estimates:
        base += 0.1
    if causal_claims:
        base += 0.05
    return min(base, 1.0)


def _extraction_confidence(
    study_design: str,
    estimates: list[EstimateCandidate],
    context_profile: dict,
    causal_claims: list[dict],
) -> float:
    score = 0.0
    if study_design:
        score += 0.4
    if estimates:
        score += 0.2
        if any(e.ci_low is not None and e.ci_high is not None for e in estimates):
            score += 0.1
    if causal_claims:
        score += 0.15
    if context_profile.get("context_id"):
        score += 0.15
    return min(score, 1.0)


def parse_raw_sources(config: AcademicBatchConfig) -> dict[str, int]:
    """Parse latest raw snapshots into normalized work records."""
    started_at = datetime.now(UTC).isoformat()
    counts: dict[str, int] = {}
    artifacts: list[Path] = []

    for slug, payload in _iter_payloads(config):
        parsed_path = config.parsed_dir / f"{slug}.jsonl"

        records: list[WorkRecord] = []
        with open(payload, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue

                source_topic: SourceTopicRef | None = None
                work = row
                if isinstance(row.get("work"), dict):
                    work = row["work"]
                    source_topic = _build_source_topic(row)

                abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                study_design = classify_study_design(abstract)
                estimates = extract_numerical_estimates(
                    abstract, [source_topic.topic_display_name] if source_topic else None
                )
                sample_size = extract_sample_size(abstract)
                causal_claims = extract_causal_claims(abstract)
                boundary_conditions = extract_boundary_conditions(abstract)
                context_profile = infer_context_profile(work, abstract)
                trust = compute_trust_score(
                    study_design=study_design,
                    cited_by_count=int(work.get("cited_by_count") or 0),
                    publication_year=int(work.get("publication_year") or 2000),
                    sample_size=sample_size,
                )
                method_signal = _method_signal_score(study_design, estimates, causal_claims)
                extraction_conf = _extraction_confidence(
                    study_design, estimates, context_profile, causal_claims
                )

                primary_location = work.get("primary_location") or {}
                source = (
                    primary_location.get("source") if isinstance(primary_location, dict) else {}
                )
                source = source if isinstance(source, dict) else {}
                open_access = (
                    work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
                )
                best_oa = (
                    work.get("best_oa_location")
                    if isinstance(work.get("best_oa_location"), dict)
                    else {}
                )
                citation_norm = (
                    work.get("citation_normalized_percentile")
                    if isinstance(work.get("citation_normalized_percentile"), dict)
                    else {}
                )

                full_text_url = str(open_access.get("oa_url") or best_oa.get("pdf_url") or "")
                fwci_value = work.get("fwci")
                fwci = float(fwci_value) if isinstance(fwci_value, (int, float)) else None
                citation_percentile_val = citation_norm.get("value")
                citation_percentile = (
                    float(citation_percentile_val)
                    if isinstance(citation_percentile_val, (int, float))
                    else None
                )

                records.append(
                    WorkRecord(
                        id=str(work.get("id") or ""),
                        title=str(work.get("title") or ""),
                        doi=str(work.get("doi") or ""),
                        abstract=abstract,
                        year=work.get("publication_year"),
                        publication_date=str(work.get("publication_date") or ""),
                        language=str(work.get("language") or ""),
                        work_type=str(work.get("type") or ""),
                        is_retracted=bool(work.get("is_retracted", False)),
                        cited_by_count=int(work.get("cited_by_count") or 0),
                        fwci=fwci,
                        citation_normalized_percentile=citation_percentile,
                        citation_is_top_1_percent=bool(
                            citation_norm.get("is_in_top_1_percent", False)
                        ),
                        citation_is_top_10_percent=bool(
                            citation_norm.get("is_in_top_10_percent", False)
                        ),
                        journal=str(source.get("display_name") or ""),
                        source_id=str(source.get("id") or ""),
                        is_oa=bool(open_access.get("is_oa", False)),
                        has_fulltext=bool(work.get("has_fulltext", False)),
                        full_text_url=full_text_url,
                        concepts=list(work.get("topics") or []),
                        source_topics=[source_topic] if source_topic else [],
                        study_design=study_design,
                        trust_score=trust,
                        estimates=estimates,
                        causal_claims=causal_claims,
                        boundary_conditions=boundary_conditions,
                        context_profile=context_profile,
                        extraction_mode="deterministic",
                        extraction_confidence=extraction_conf,
                        method_signal_score=method_signal,
                        metadata={
                            "sample_size": sample_size,
                            "run_id": config.run_id,
                            "pass_name": config.pass_name,
                        },
                    )
                )

        with open(parsed_path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(rec.model_dump_json() + "\n")

        counts[slug] = len(records)
        artifacts.append(parsed_path)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "parse.json",
        stage="parse",
        status="ok",
        metrics={"sources": len(counts), "records": sum(counts.values())},
        artifacts=artifacts,
        started_at=started_at,
    )
    return counts
