#!/usr/bin/env python3
"""Build a single expert-ready JSON bundle for screen and claim gold review."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from build_academic_gold_candidates import build_candidate_pools, load_jsonl


INTRO_LINES = [
    "Вы размечаете не истинность экономических законов, а статус и качество причинных утверждений в академических работах для policy-oriented causal knowledge graph.",
    "",
    "В наборе два типа заданий.",
    "",
    "1. screening review:",
    "Нужно решить, должна ли статья вообще попадать в causal extraction pipeline. Это уровень paper relevance, а не оценка конкретных claims.",
    "",
    "2. claim review:",
    "Нужно оценить конкретное утверждение внутри статьи. Главная задача: отделить mere association от действительно publishable causal assertion.",
    "",
    "Система работает в режиме precision-first. При сомнении надо быть консервативными. Если в тексте нет явного design support, если claim основан только на abstract, если evidence span слабый или не подтверждает именно выделенную cause-effect связь, такой claim не должен автоматически считаться strong causal edge.",
    "",
    "Особенно важно различать:",
    "- paper uses causal language",
    "- paper has causally credible evidence",
    "- claim should be published to the graph",
    "",
    "Это три разные вещи.",
    "",
    "Для claim review опирайтесь только на текст в пакете:",
    "- title",
    "- claim_text",
    "- supporting_spans / supporting_text",
    "- source_basis",
    "- design_family_hint",
    "",
    "Не используйте внешние знания о paper, авторах или журнале. Если evidence недостаточно, снижайте credibility или ставьте insufficient / unclear.",
    "",
    "Подробная rubric находится в guidelines_path.",
]


def _matches_source_basis(row: dict, source_basis_filter: str | None) -> bool:
    if not source_basis_filter:
        return True
    return str(row.get("source_basis") or "").strip() == source_basis_filter


def _intro_text(source_basis_filter: str | None) -> str:
    lines = list(INTRO_LINES)
    if source_basis_filter == "fulltext":
        lines.extend(
            [
                "",
                "Этот пакет содержит только fulltext-grounded claims.",
                "При конфликте между силой claim-а и качеством evidence приоритет имеет реальный supporting span из полного текста.",
            ]
        )
    elif source_basis_filter == "abstract_only":
        lines.extend(
            [
                "",
                "Этот пакет содержит только abstract-only claims.",
                "Для этого пакета требуется особенно консервативная разметка: отсутствие full text само по себе ограничивает publishability claim-а.",
            ]
        )
    return "\n".join(lines)


def _screen_items(screen_rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    for i, row in enumerate(screen_rows, start=1):
        items.append(
            {
                "candidate_id": row.get("paper_id") or f"screen_{i:05d}",
                "paper_id": row.get("paper_id"),
                "title": row.get("title", ""),
                "abstract": row.get("abstract", ""),
                "source_basis": row.get("source_basis", ""),
                "suggested_bucket": row.get("suggested_bucket", ""),
                "annotation": {
                    "paper_relevant_for_policy_causal_extraction": row.get(
                        "paper_relevant_for_policy_causal_extraction", ""
                    ),
                    "notes": row.get("notes", ""),
                },
            }
        )
    return items


def _claim_items(claim_rows: list[dict]) -> list[dict]:
    items: list[dict] = []
    for i, row in enumerate(claim_rows, start=1):
        spans = row.get("supporting_spans") or []
        span_texts: list[str] = []
        for span in spans:
            if isinstance(span, dict):
                text = str(span.get("text") or "").strip()
                if text:
                    span_texts.append(text)
            elif isinstance(span, str):
                text = span.strip()
                if text:
                    span_texts.append(text)

        items.append(
            {
                "candidate_id": row.get("claim_id") or f"claim_{i:05d}",
                "paper_id": row.get("paper_id"),
                "title": row.get("title", ""),
                "paper_abstract": row.get("paper_abstract", ""),
                "claim_text": row.get("claim_text", ""),
                "cause_text": row.get("cause_text", ""),
                "effect_text": row.get("effect_text", ""),
                "direction": row.get("direction", ""),
                "source_basis": row.get("source_basis", ""),
                "design_family_hint": row.get("design_family_hint", ""),
                "suggested_bucket": row.get("suggested_bucket", ""),
                "supporting_spans": spans,
                "supporting_text": "\n".join(span_texts),
                "annotation": {
                    "paper_relevant_for_policy_causal_extraction": row.get(
                        "paper_relevant_for_policy_causal_extraction", ""
                    ),
                    "claim_present": row.get("claim_present", ""),
                    "claim_type": row.get("claim_type", ""),
                    "explicitness": row.get("explicitness", ""),
                    "design_family": row.get("design_family", ""),
                    "causal_credibility": row.get("causal_credibility", ""),
                    "risk_of_bias": row.get("risk_of_bias", ""),
                    "support_status": row.get("support_status", ""),
                    "publish_to_graph": row.get("publish_to_graph", ""),
                    "notes": row.get("notes", ""),
                },
            }
        )
    return items


def _validation_summary(screen_rows: list[dict], claim_rows: list[dict]) -> dict[str, object]:
    total_screen = len(screen_rows)
    total_claims = len(claim_rows)
    screen_without_abstract = sum(1 for row in screen_rows if not str(row.get("abstract") or "").strip())
    claims_without_text = sum(1 for row in claim_rows if not str(row.get("claim_text") or "").strip())
    claims_without_supporting_spans = sum(1 for row in claim_rows if not (row.get("supporting_spans") or []))
    claims_without_source_basis = sum(1 for row in claim_rows if not str(row.get("source_basis") or "").strip())
    claims_without_design_family_hint = sum(
        1 for row in claim_rows if not str(row.get("design_family_hint") or "").strip()
    )
    abstract_only_claims = sum(1 for row in claim_rows if str(row.get("source_basis") or "") == "abstract_only")

    claim_text_coverage_pct = round(
        ((total_claims - claims_without_text) / total_claims) * 100.0, 3
    ) if total_claims else 100.0
    supporting_span_coverage_pct = round(
        ((total_claims - claims_without_supporting_spans) / total_claims) * 100.0, 3
    ) if total_claims else 100.0
    source_basis_coverage_pct = round(
        ((total_claims - claims_without_source_basis) / total_claims) * 100.0, 3
    ) if total_claims else 100.0
    design_family_hint_coverage_pct = round(
        ((total_claims - claims_without_design_family_hint) / total_claims) * 100.0, 3
    ) if total_claims else 100.0
    abstract_only_share_pct = round(
        (abstract_only_claims / total_claims) * 100.0, 3
    ) if total_claims else 0.0

    return {
        "screen_items_total": total_screen,
        "claim_items_total": total_claims,
        "screen_items_without_abstract": screen_without_abstract,
        "claims_without_claim_text": claims_without_text,
        "claims_without_supporting_spans": claims_without_supporting_spans,
        "claims_without_source_basis": claims_without_source_basis,
        "claims_without_design_family_hint": claims_without_design_family_hint,
        "abstract_only_claims": abstract_only_claims,
        "claim_text_coverage_pct": claim_text_coverage_pct,
        "supporting_span_coverage_pct": supporting_span_coverage_pct,
        "source_basis_coverage_pct": source_basis_coverage_pct,
        "design_family_hint_coverage_pct": design_family_hint_coverage_pct,
        "abstract_only_share_pct": abstract_only_share_pct,
    }


def _validate_thresholds(
    summary: dict[str, object],
    *,
    min_claim_text_coverage_pct: float,
    min_supporting_span_coverage_pct: float,
    min_source_basis_coverage_pct: float,
    min_design_family_hint_coverage_pct: float,
    max_abstract_only_share_pct: float | None,
) -> list[str]:
    errors: list[str] = []
    if float(summary["claim_text_coverage_pct"]) < float(min_claim_text_coverage_pct):
        errors.append(
            f"claim_text_coverage_pct={summary['claim_text_coverage_pct']} < {min_claim_text_coverage_pct}"
        )
    if float(summary["supporting_span_coverage_pct"]) < float(min_supporting_span_coverage_pct):
        errors.append(
            "supporting_span_coverage_pct="
            f"{summary['supporting_span_coverage_pct']} < {min_supporting_span_coverage_pct}"
        )
    if float(summary["source_basis_coverage_pct"]) < float(min_source_basis_coverage_pct):
        errors.append(
            f"source_basis_coverage_pct={summary['source_basis_coverage_pct']} < {min_source_basis_coverage_pct}"
        )
    if float(summary["design_family_hint_coverage_pct"]) < float(min_design_family_hint_coverage_pct):
        errors.append(
            "design_family_hint_coverage_pct="
            f"{summary['design_family_hint_coverage_pct']} < {min_design_family_hint_coverage_pct}"
        )
    if max_abstract_only_share_pct is not None and float(summary["abstract_only_share_pct"]) > float(max_abstract_only_share_pct):
        errors.append(
            f"abstract_only_share_pct={summary['abstract_only_share_pct']} > {max_abstract_only_share_pct}"
        )
    return errors


def build_bundle(
    snapshot_root: Path,
    out_dir: Path,
    bundle_path: Path,
    guidelines_path: Path,
    validation_path: Path,
    *,
    source_basis_filter: str | None,
    min_claim_text_coverage_pct: float,
    min_supporting_span_coverage_pct: float,
    min_source_basis_coverage_pct: float,
    min_design_family_hint_coverage_pct: float,
    max_abstract_only_share_pct: float | None,
    fail_on_validation: bool,
) -> None:
    screen_candidates_path, claim_candidates_path = build_candidate_pools(snapshot_root, out_dir)
    screen_rows = [
        row for row in load_jsonl(screen_candidates_path)
        if _matches_source_basis(row, source_basis_filter)
    ]
    claim_rows = [
        row for row in load_jsonl(claim_candidates_path)
        if _matches_source_basis(row, source_basis_filter)
    ]
    validation = _validation_summary(screen_rows, claim_rows)
    validation_errors = _validate_thresholds(
        validation,
        min_claim_text_coverage_pct=min_claim_text_coverage_pct,
        min_supporting_span_coverage_pct=min_supporting_span_coverage_pct,
        min_source_basis_coverage_pct=min_source_basis_coverage_pct,
        min_design_family_hint_coverage_pct=min_design_family_hint_coverage_pct,
        max_abstract_only_share_pct=max_abstract_only_share_pct,
    )
    validation["ready_for_expert_review"] = not validation_errors
    validation["validation_errors"] = validation_errors

    bundle = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "snapshot_root": str(snapshot_root),
        "guidelines_path": str(guidelines_path),
        "source_basis_filter": source_basis_filter or "all",
        "source_files": {
            "screen_gold_candidates": str(screen_candidates_path),
            "claim_gold_candidates": str(claim_candidates_path),
        },
        "intro_for_experts": _intro_text(source_basis_filter),
        "validation_summary": validation,
        "tasks": {
            "screen_gold": {
                "description": "Paper-level relevance screening for policy-causal extraction",
                "count": len(screen_rows),
                "items": _screen_items(screen_rows),
            },
            "claim_gold": {
                "description": "Claim-level extraction and causal adjudication review",
                "count": len(claim_rows),
                "items": _claim_items(claim_rows),
            },
        },
    }

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bundle_path, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, ensure_ascii=False, indent=2)
    with open(validation_path, "w", encoding="utf-8") as fh:
        json.dump(validation, fh, ensure_ascii=False, indent=2)

    print(f"Bundle ready: {bundle_path}")
    print(f"Validation report: {validation_path}")
    print(f"screen_gold items: {len(screen_rows)}")
    print(f"claim_gold items: {len(claim_rows)}")
    print(
        "validation:"
        f" claim_text_coverage_pct={validation['claim_text_coverage_pct']}"
        f" supporting_span_coverage_pct={validation['supporting_span_coverage_pct']}"
        f" source_basis_coverage_pct={validation['source_basis_coverage_pct']}"
        f" design_family_hint_coverage_pct={validation['design_family_hint_coverage_pct']}"
        f" abstract_only_share_pct={validation['abstract_only_share_pct']}"
    )
    if validation_errors:
        for err in validation_errors:
            print(f"validation_error: {err}")
        if fail_on_validation:
            raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a single expert review JSON bundle from an academic snapshot"
    )
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--bundle-path", default="")
    parser.add_argument("--validation-path", default="")
    parser.add_argument(
        "--source-basis-filter",
        choices=["fulltext", "abstract_only"],
        default="",
        help="Restrict bundle to one source_basis stratum",
    )
    parser.add_argument(
        "--guidelines-path",
        default="/Users/deniskopylov/polisyos/policy-engine/data/academic_gold/guidelines.md",
    )
    parser.add_argument("--min-claim-text-coverage-pct", type=float, default=100.0)
    parser.add_argument("--min-supporting-span-coverage-pct", type=float, default=85.0)
    parser.add_argument("--min-source-basis-coverage-pct", type=float, default=100.0)
    parser.add_argument("--min-design-family-hint-coverage-pct", type=float, default=100.0)
    parser.add_argument("--max-abstract-only-share-pct", type=float, default=-1.0)
    parser.add_argument(
        "--fail-on-validation",
        action="store_true",
        help="Exit with code 2 when validation thresholds are violated",
    )
    args = parser.parse_args()

    snapshot_root = Path(args.snapshot_root)
    component_dir = snapshot_root / "academic"
    out_dir = Path(args.out_dir) if args.out_dir else component_dir / "gold_candidates"
    bundle_path = (
        Path(args.bundle_path)
        if args.bundle_path
        else out_dir / "expert_review_bundle.json"
    )
    validation_path = (
        Path(args.validation_path)
        if args.validation_path
        else out_dir / "expert_review_bundle_validation.json"
    )
    max_abstract_only_share_pct = (
        None if args.max_abstract_only_share_pct < 0 else args.max_abstract_only_share_pct
    )
    build_bundle(
        snapshot_root,
        out_dir,
        bundle_path,
        Path(args.guidelines_path),
        validation_path,
        source_basis_filter=args.source_basis_filter or None,
        min_claim_text_coverage_pct=args.min_claim_text_coverage_pct,
        min_supporting_span_coverage_pct=args.min_supporting_span_coverage_pct,
        min_source_basis_coverage_pct=args.min_source_basis_coverage_pct,
        min_design_family_hint_coverage_pct=args.min_design_family_hint_coverage_pct,
        max_abstract_only_share_pct=max_abstract_only_share_pct,
        fail_on_validation=args.fail_on_validation,
    )


if __name__ == "__main__":
    main()
