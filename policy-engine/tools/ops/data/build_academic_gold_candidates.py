#!/usr/bin/env python3
"""Build seed candidate pools for manual academic gold annotation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def component_roots(snapshot_root: Path) -> list[Path]:
    roots = [snapshot_root]
    shard_glob = f"{snapshot_root.name}_shard*"
    shard_roots = sorted(path for path in snapshot_root.parent.glob(shard_glob) if path.is_dir())
    roots.extend(shard_roots)
    return roots


def reconstruct_abstract(work: dict[str, Any]) -> str:
    inverted = work.get("abstract_inverted_index")
    if not isinstance(inverted, dict) or not inverted:
        return ""
    tokens: dict[int, str] = {}
    for term, positions in inverted.items():
        if not isinstance(term, str) or not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                tokens[pos] = term
    if not tokens:
        return ""
    return " ".join(tokens[index] for index in sorted(tokens))


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _split_sentences(text: str) -> list[str]:
    cleaned = _normalized_text(text)
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def _claim_tokens(*values: Any) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-z0-9_]{3,}", _normalized_text(value).lower()):
            if token in {"the", "and", "for", "with", "from", "that", "this"}:
                continue
            tokens.add(token)
    return tokens


def _stable_claim_id(
    *, paper_id: str, cause: str, effect: str, direction: str, claim_text: str
) -> str:
    payload = "|".join(
        [
            _normalized_text(paper_id).lower(),
            _normalized_text(cause).lower(),
            _normalized_text(effect).lower(),
            _normalized_text(direction).lower(),
            _normalized_text(claim_text).lower(),
        ]
    )
    return "claim_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


_RESULT_CUE_RE = re.compile(
    r"\b(we find|our results|results indicate|results show|estimate|estimated|increase|decrease|effect|impact|causes?|leads to|reduces?|raises?)\b",
    re.IGNORECASE,
)


def _supporting_spans(
    *,
    title: str,
    abstract: str,
    claim_text: str,
    cause_text: str,
    effect_text: str,
    direction: str,
    limit: int = 2,
) -> list[dict[str, Any]]:
    tokens = _claim_tokens(claim_text, cause_text, effect_text, direction)
    sentences = _split_sentences(abstract)
    scored: list[tuple[float, dict[str, Any]]] = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        overlap = sum(1 for token in tokens if token in lower)
        cue_bonus = 1.5 if _RESULT_CUE_RE.search(sentence) else 0.0
        direction_bonus = 0.5 if _normalized_text(direction).lower() in lower else 0.0
        score = overlap + cue_bonus + direction_bonus
        if score <= 0 and not _RESULT_CUE_RE.search(sentence):
            continue
        scored.append(
            (
                score,
                {
                    "section": "abstract",
                    "text": sentence,
                    "sentence_index": index,
                    "score": round(min(1.0, 0.35 + 0.1 * score), 3),
                },
            )
        )

    if not scored and sentences:
        fallback = sentences[:limit]
        return [
            {
                "section": "abstract",
                "text": sentence,
                "sentence_index": index,
                "score": 0.4,
            }
            for index, sentence in enumerate(fallback)
        ]

    scored.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for _, span in scored:
        text = span["text"]
        if text in seen:
            continue
        seen.add(text)
        out.append(span)
        if len(out) >= limit:
            break

    if out:
        return out
    if _normalized_text(title):
        return [
            {
                "section": "title",
                "text": _normalized_text(title),
                "sentence_index": 0,
                "score": 0.25,
            }
        ]
    return []


def _infer_design_family(*values: Any) -> str:
    text = " ".join(_normalized_text(value).lower() for value in values if _normalized_text(value))
    if not text:
        return "unclear"
    if any(
        term in text
        for term in ("randomized", "randomised", "field experiment", "random tax audit", "rct")
    ):
        return "rct"
    if any(
        term in text
        for term in ("instrumental variable", "instrumental variables", "2sls", "tsls", "iv ")
    ):
        return "iv"
    if any(
        term in text
        for term in (
            "difference-in-differences",
            "difference in differences",
            " did ",
            "(did)",
            "did)",
        )
    ):
        return "did"
    if any(
        term in text
        for term in ("regression discontinuity", "rdd", "fuzzy regression discontinuity")
    ):
        return "rdd"
    if "synthetic control" in text:
        return "synthetic_control"
    if any(
        term in text
        for term in (
            "fixed effects",
            "fixed effect",
            "panel data",
            "panel regression",
            "panel model",
        )
    ):
        return "panel_fe"
    if any(
        term in text
        for term in ("ordinary least squares", "ols", "cross-sectional", "cross sectional")
    ):
        return "ols"
    if any(term in text for term in ("meta-analysis", "meta analysis")):
        return "meta_analysis"
    if any(term in text for term in ("critical review", "narrative review", "survey", "review")):
        return "review"
    if any(
        term in text
        for term in (
            "theoretical",
            "dsge",
            "keynesian",
            "structural model",
            "structural estimation",
        )
    ):
        return "theoretical"
    return "unclear"


def _claim_text_from_fields(
    *,
    title: str,
    abstract: str,
    cause_text: str,
    effect_text: str,
    direction: str,
    effect_size: Any,
    extracted_claim_text: Any,
) -> str:
    extracted = _normalized_text(extracted_claim_text)
    if extracted:
        return extracted

    spans = _supporting_spans(
        title=title,
        abstract=abstract,
        claim_text="",
        cause_text=cause_text,
        effect_text=effect_text,
        direction=direction,
        limit=1,
    )
    if spans:
        return _normalized_text(spans[0].get("text"))

    cause = _normalized_text(cause_text) or "the treatment"
    effect = _normalized_text(effect_text) or "the outcome"
    direction_norm = _normalized_text(direction).lower()
    templates = {
        "positive": f"{cause} increases {effect}.",
        "negative": f"{cause} decreases {effect}.",
        "null": f"{cause} has no clear effect on {effect}.",
        "mixed": f"{cause} has mixed effects on {effect}.",
        "ambiguous": f"The effect of {cause} on {effect} is ambiguous.",
        "non_linear": f"The effect of {cause} on {effect} appears non-linear.",
    }
    text = templates.get(direction_norm, f"{cause} affects {effect}.")
    size = _normalized_text(effect_size)
    if size:
        text = f"{text[:-1]} Estimated effect size: {size}."
    return text


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def claim_bucket(claim: dict, adjudication: dict | None) -> str:
    source_basis = str((adjudication or {}).get("source_basis") or claim.get("source_basis") or "")
    design = str((adjudication or {}).get("design_family") or claim.get("design_family_hint") or "")
    claim_type = str((adjudication or {}).get("claim_type") or "")
    publishable = bool((adjudication or {}).get("publishable_edge") or False)

    if source_basis == "abstract_only":
        return "abstract_only"
    if design in {"rct", "iv", "did", "rdd", "synthetic_control"}:
        return "strong_design"
    if design in {"panel_fe", "ols"}:
        return "observational_ambiguous"
    if claim_type in {"review_summary", "mechanism"}:
        return "review_or_mechanism"
    if not publishable:
        return "hard_failure"
    return "other"


def _dedupe_rows(rows: list[dict], key_field: str) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get(key_field) or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(row)
    return deduped


def _load_component_rows(snapshot_root: Path, filename: str, key_field: str) -> list[dict]:
    rows: list[dict] = []
    for root in component_roots(snapshot_root):
        rows.extend(load_jsonl(root / "academic" / filename))
    return _dedupe_rows(rows, key_field)


def _selected_work_lookup(snapshot_root: Path) -> dict[str, dict[str, Any]]:
    rows = _load_component_rows(
        snapshot_root, "topic_selection/selected_global_works.jsonl", "work_id"
    )
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        work_id = str(row.get("work_id") or "")
        work = row.get("work")
        if work_id and isinstance(work, dict):
            lookup[work_id] = work
    return lookup


def _work_record_lookup(snapshot_root: Path) -> dict[str, dict[str, Any]]:
    rows = _load_component_rows(snapshot_root, "extracted/article_extract.jsonl", "id")
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        work_id = str(row.get("id") or "")
        if work_id:
            lookup[work_id] = row
    return lookup


def build_candidate_pools(snapshot_root: Path, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    article_rows = _load_component_rows(
        snapshot_root, "article_extraction_results.jsonl", "openalex_id"
    )
    selected_works = _selected_work_lookup(snapshot_root)
    work_records = _work_record_lookup(snapshot_root)
    adjudications = {
        str(row.get("claim_id") or ""): row
        for row in _load_component_rows(snapshot_root, "claim_adjudications.jsonl", "claim_id")
        if str(row.get("claim_id") or "")
    }

    screen_candidates_path = out_dir / "screen_gold_candidates.jsonl"
    claim_candidates_path = out_dir / "claim_gold_candidates.jsonl"

    with open(screen_candidates_path, "w", encoding="utf-8") as screen_fh:
        for row in article_rows:
            work = selected_works.get(str(row.get("openalex_id") or ""), {})
            work_record = work_records.get(str(row.get("openalex_id") or ""), {})
            abstract = (
                reconstruct_abstract(work)
                or _normalized_text(work_record.get("abstract"))
                or row.get("citation_summary")
                or ""
            )
            screen_fh.write(
                json.dumps(
                    {
                        "paper_id": row.get("openalex_id"),
                        "title": row.get("title"),
                        "abstract": abstract,
                        "source_basis": row.get("source_basis"),
                        "suggested_bucket": "article_extract_output",
                        "paper_relevant_for_policy_causal_extraction": "",
                        "notes": "",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    with open(claim_candidates_path, "w", encoding="utf-8") as claim_fh:
        for row in article_rows:
            work = selected_works.get(str(row.get("openalex_id") or ""), {})
            work_record = work_records.get(str(row.get("openalex_id") or ""), {})
            abstract = (
                reconstruct_abstract(work)
                or _normalized_text(work_record.get("abstract"))
                or row.get("citation_summary")
                or ""
            )
            study_design = _normalized_text(
                row.get("methodology") or work_record.get("study_design")
            )
            for claim in row.get("causal_claims") or []:
                if not isinstance(claim, dict):
                    continue
                cause_text = _normalized_text(claim.get("cause_variable") or claim.get("cause"))
                effect_text = _normalized_text(claim.get("effect_variable") or claim.get("effect"))
                direction = _normalized_text(claim.get("direction"))
                claim_text = _claim_text_from_fields(
                    title=_normalized_text(row.get("title")),
                    abstract=abstract,
                    cause_text=cause_text,
                    effect_text=effect_text,
                    direction=direction,
                    effect_size=claim.get("effect_size"),
                    extracted_claim_text=claim.get("claim_text"),
                )
                supporting_spans = claim.get("supporting_spans") or _supporting_spans(
                    title=_normalized_text(row.get("title")),
                    abstract=abstract,
                    claim_text=claim_text,
                    cause_text=cause_text,
                    effect_text=effect_text,
                    direction=direction,
                )
                claim_id = str(claim.get("claim_id") or "")
                adjudication = adjudications.get(claim_id)
                design_family_hint = _normalized_text(
                    (adjudication or {}).get("design_family")
                    or claim.get("design_family_hint")
                    or _infer_design_family(
                        claim.get("evidence_strength"),
                        study_design,
                        row.get("title"),
                        abstract,
                    )
                )
                source_basis = (
                    _normalized_text(
                        (adjudication or {}).get("source_basis")
                        or claim.get("source_basis")
                        or row.get("source_basis")
                    )
                    or "abstract_only"
                )
                if not claim_id:
                    claim_id = _stable_claim_id(
                        paper_id=str(row.get("openalex_id") or ""),
                        cause=cause_text,
                        effect=effect_text,
                        direction=direction,
                        claim_text=claim_text,
                    )
                enriched_claim = {
                    "source_basis": source_basis,
                    "design_family_hint": design_family_hint,
                }
                claim_fh.write(
                    json.dumps(
                        {
                            "paper_id": row.get("openalex_id"),
                            "title": row.get("title"),
                            "paper_abstract": abstract,
                            "claim_id": claim_id,
                            "claim_text": claim_text,
                            "cause_text": cause_text,
                            "effect_text": effect_text,
                            "direction": direction,
                            "source_basis": source_basis,
                            "design_family_hint": design_family_hint,
                            "supporting_spans": supporting_spans,
                            "suggested_bucket": claim_bucket(
                                {**claim, **enriched_claim}, adjudication
                            ),
                            "paper_relevant_for_policy_causal_extraction": "",
                            "claim_present": "",
                            "claim_type": "",
                            "explicitness": "",
                            "design_family": "",
                            "causal_credibility": "",
                            "risk_of_bias": "",
                            "support_status": "",
                            "publish_to_graph": "",
                            "notes": "",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    return screen_candidates_path, claim_candidates_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build academic gold candidate pools from a snapshot"
    )
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    snapshot_root = Path(args.snapshot_root)
    component_dir = snapshot_root / "academic"
    out_dir = Path(args.out_dir) if args.out_dir else component_dir / "gold_candidates"
    screen_candidates_path, claim_candidates_path = build_candidate_pools(snapshot_root, out_dir)

    print(f"screen candidates: {screen_candidates_path}")
    print(f"claim candidates: {claim_candidates_path}")


if __name__ == "__main__":
    main()
