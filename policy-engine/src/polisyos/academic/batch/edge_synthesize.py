"""Synthesize family-level evidence layers from exact SKG edges."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.canonical_resolver import (
    CanonicalVariableResolver,
    ResolutionResult,
)
from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.academic.knowledge.skg_store import (
    ArticleEvidence,
    aggregate_edge_confidence,
    ensure_skg_schema,
    hash_contested_edge_id,
    hash_edge_id,
    parent_canonical_name,
    strongest_strength,
    weighted_direction_summary,
)
from polisyos.batch_common.manifest import write_stage_manifest


def _seed_canonical_names() -> set[str]:
    names: set[str] = set()
    for parent, children in CANONICAL_VARIABLES.items():
        names.add(parent)
        for child_key in children:
            if child_key == "_root":
                continue
            names.add(f"{parent}.{child_key}")
    return names


def _approved_canonical_names(con: duckdb.DuckDBPyConnection) -> set[str]:
    approved = {
        str(row[0])
        for row in con.execute(
            "SELECT canonical_name FROM ac_skg_canonization_cache WHERE approved = TRUE"
        ).fetchall()
        if row and row[0]
    }
    return approved | _seed_canonical_names()


def _family_name(canonical_name: str | None, approved_names: set[str]) -> str | None:
    clean = str(canonical_name or "").strip()
    if not clean:
        return None
    parent = parent_canonical_name(clean)
    if parent and parent in approved_names:
        return parent
    return clean if clean in approved_names else None


def _mention_maps(con: duckdb.DuckDBPyConnection) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    try:
        variable_rows = con.execute(
            "SELECT normalized_name, mention_count FROM ac_skg_variables"
        ).fetchall()
    except duckdb.Error:
        variable_rows = con.execute(
            "SELECT canonical_name, mention_count FROM ac_skg_variables"
        ).fetchall()
    variable_counts = {
        str(row[0]): int(row[1] or 0)
        for row in variable_rows
        if row and row[0]
    }
    context_counts = {
        str(row[0]): int(row[1] or 0)
        for row in con.execute(
            "SELECT canonical_name, COUNT(*) FROM ac_skg_context_attributes GROUP BY canonical_name"
        ).fetchall()
        if row and row[0]
    }
    moderator_counts = {
        str(row[0]): int(row[1] or 0)
        for row in con.execute(
            "SELECT moderator, COUNT(*) FROM ac_skg_moderation_edges GROUP BY moderator"
        ).fetchall()
        if row and row[0]
    }
    return variable_counts, context_counts, moderator_counts


def _review_lookup_keys(raw_name: str, suggested_canonical_name: str) -> set[str]:
    keys = {
        str(raw_name or "").strip(),
        str(raw_name or "").strip().lower(),
        str(suggested_canonical_name or "").strip(),
    }
    raw_slug = re.sub(r"[^a-z0-9._]+", "_", str(raw_name or "").strip().lower())
    raw_slug = re.sub(r"_+", "_", raw_slug).strip("_")
    if raw_slug:
        keys.add(raw_slug)
    return {key for key in keys if key}


def _canonical_review_queue(
    con: duckdb.DuckDBPyConnection,
    *,
    pending_results: list[ResolutionResult] | None = None,
) -> list[dict[str, Any]]:
    unresolved = con.execute(
        """
        SELECT raw_name, canonical_name
        FROM ac_skg_canonization_cache
        WHERE approved = FALSE
        ORDER BY canonical_name, raw_name
        """
    ).fetchall()
    variable_counts, context_counts, moderator_counts = _mention_maps(con)
    queue: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_name, canonical_name in unresolved:
        canonical = str(canonical_name or "")
        seen.add((str(raw_name or ""), canonical))
        lookup_keys = _review_lookup_keys(str(raw_name or ""), canonical)
        queue.append(
            {
                "raw_name": str(raw_name or ""),
                "suggested_canonical_name": canonical,
                "confidence": 0.0,
                "source_method": "cache",
                "variable_mentions": int(sum(variable_counts.get(key, 0) for key in lookup_keys)),
                "context_mentions": int(sum(context_counts.get(key, 0) for key in lookup_keys)),
                "moderator_mentions": int(sum(moderator_counts.get(key, 0) for key in lookup_keys)),
                "total_mentions": int(
                    sum(variable_counts.get(key, 0) for key in lookup_keys)
                    + sum(context_counts.get(key, 0) for key in lookup_keys)
                    + sum(moderator_counts.get(key, 0) for key in lookup_keys)
                ),
            }
        )
    for result in pending_results or []:
        key = (result.raw_name, str(result.canonical_name or ""))
        if key in seen:
            continue
        canonical = str(result.canonical_name or "")
        lookup_keys = _review_lookup_keys(result.raw_name, canonical)
        queue.append(
            {
                "raw_name": result.raw_name,
                "suggested_canonical_name": canonical,
                "confidence": round(float(result.confidence), 6),
                "source_method": result.method,
                "variable_mentions": int(sum(variable_counts.get(key, 0) for key in lookup_keys)),
                "context_mentions": int(sum(context_counts.get(key, 0) for key in lookup_keys)),
                "moderator_mentions": int(sum(moderator_counts.get(key, 0) for key in lookup_keys)),
                "total_mentions": int(
                    sum(variable_counts.get(key, 0) for key in lookup_keys)
                    + sum(context_counts.get(key, 0) for key in lookup_keys)
                    + sum(moderator_counts.get(key, 0) for key in lookup_keys)
                ),
            }
        )
    queue.sort(key=lambda row: (-int(row["total_mentions"]), row["suggested_canonical_name"], row["raw_name"]))
    return queue


def _materialized_resolution_map(con: duckdb.DuckDBPyConnection) -> dict[str, ResolutionResult]:
    try:
        rows = con.execute(
            """
            SELECT canonical_name, approved_canonical_name, is_approved_canonical,
                   resolution_method, resolution_confidence
            FROM ac_skg_variables
            """
        ).fetchall()
    except duckdb.Error:
        return {}
    mapping: dict[str, ResolutionResult] = {}
    for normalized_name, approved_name, is_approved, method, confidence in rows:
        clean_name = str(normalized_name or "").strip()
        if not clean_name:
            continue
        canonical_name = str(approved_name or "").strip() or None
        approved = bool(is_approved and canonical_name)
        review_required = not approved
        mapping[clean_name] = ResolutionResult(
            raw_name=clean_name,
            canonical_name=canonical_name,
            method=str(method or "materialized"),
            confidence=float(confidence or 0.0),
            approved=approved,
            review_required=review_required,
        )
    return mapping


def _canonization_summary(con: duckdb.DuckDBPyConnection) -> dict[str, float | int]:
    try:
        rows = con.execute(
            """
            SELECT resolution_method, is_approved_canonical, approved_canonical_name
            FROM ac_skg_variables
            """
        ).fetchall()
    except duckdb.Error:
        return {
            "exact_matches": 0,
            "synonym_matches": 0,
            "hierarchy_matches": 0,
            "embedding_matches": 0,
            "auto_approved": 0,
            "pending_review": 0,
            "unresolved": 0,
            "total": 0,
            "resolution_rate_pct": 0.0,
        }
    exact_matches = 0
    synonym_matches = 0
    hierarchy_matches = 0
    embedding_matches = 0
    auto_approved = 0
    pending_review = 0
    unresolved = 0
    total = 0
    for method, is_approved, approved_name in rows:
        total += 1
        clean_method = str(method or "").strip().lower()
        approved = bool(is_approved)
        has_candidate = bool(str(approved_name or "").strip())
        if clean_method in {"exact", "exact_alias"}:
            exact_matches += 1
        elif clean_method == "synonym":
            synonym_matches += 1
        elif clean_method == "hierarchy":
            hierarchy_matches += 1
        elif clean_method == "embedding":
            embedding_matches += 1
        if approved:
            auto_approved += 1
        elif has_candidate:
            pending_review += 1
        else:
            unresolved += 1
    return {
        "exact_matches": exact_matches,
        "synonym_matches": synonym_matches,
        "hierarchy_matches": hierarchy_matches,
        "embedding_matches": embedding_matches,
        "auto_approved": auto_approved,
        "pending_review": pending_review,
        "unresolved": unresolved,
        "total": total,
        "resolution_rate_pct": round((auto_approved / max(1, total)) * 100.0, 3),
    }


def _article_meta(con: duckdb.DuckDBPyConnection) -> dict[str, dict[str, Any]]:
    try:
        rows = con.execute(
            """
            SELECT a.openalex_id, a.year, a.retracted, w.fwci
            FROM ac_skg_articles a
            LEFT JOIN ac_works w ON w.id = a.openalex_id
            """
        ).fetchall()
    except duckdb.Error:
        rows = con.execute(
            """
            SELECT openalex_id, year, retracted, NULL AS fwci
            FROM ac_skg_articles
            """
        ).fetchall()
    return {
        str(openalex_id): {
            "year": int(year) if year is not None else None,
            "retracted": bool(retracted),
            "fwci": float(fwci) if fwci is not None else None,
        }
        for openalex_id, year, retracted, fwci in rows
        if openalex_id
    }


def _sample_sizes(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    try:
        rows = con.execute(
            """
            SELECT work_id, MAX(sample_size)
            FROM ac_parameter_estimates
            WHERE sample_size IS NOT NULL AND sample_size > 0
            GROUP BY work_id
            """
        ).fetchall()
    except duckdb.Error:
        return {}
    return {
        str(work_id): int(sample_size)
        for work_id, sample_size in rows
        if work_id and sample_size is not None
    }


def _claim_source_basis(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for table_name, claim_col in (("ac_claim_adjudications", "claim_id"), ("ac_causal_claims_raw", "id")):
        try:
            rows = con.execute(f"SELECT {claim_col}, source_basis FROM {table_name}").fetchall()
        except duckdb.Error:
            continue
        for claim_id, source_basis in rows:
            clean_claim_id = str(claim_id or "").strip()
            if clean_claim_id and clean_claim_id not in mapping:
                mapping[clean_claim_id] = str(source_basis or "fulltext")
    return mapping


def run_edge_synthesize(config: AcademicBatchConfig) -> dict[str, int]:
    """Run edge synthesize."""
    started_at = datetime.now(UTC).isoformat()
    if not config.db_path.exists():
        write_stage_manifest(
            manifest_path=config.manifests_dir / "edge_synthesize.json",
            stage="edge_synthesize",
            status="ok",
            metrics={"family_edges": 0, "review_queue": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"family_edges": 0, "review_queue": 0}

    con = duckdb.connect(str(config.db_path))
    family_rows: list[tuple[Any, ...]] = []
    contested_rows: list[tuple[Any, ...]] = []
    review_queue: list[dict[str, Any]] = []
    try:
        ensure_skg_schema(con)
        approved_names = _approved_canonical_names(con)
        resolver = CanonicalVariableResolver.from_connection(con)
        materialized_resolutions = _materialized_resolution_map(con)
        article_meta = _article_meta(con)
        sample_sizes = _sample_sizes(con)
        claim_source_basis = _claim_source_basis(con)
        version_row = con.execute("SELECT COALESCE(MAX(version_id), 0) FROM ac_skg_versions").fetchone()
        skg_version = int(version_row[0] or 0) if version_row else 0

        evidence_rows = con.execute(
            """
            SELECT edge_id, claim_id, openalex_id, src, dst, direction,
                   evidence_strength, confidence, design_family, design_quality_tier
            FROM ac_skg_edge_evidence
            WHERE skg_version = ?
            """,
            [skg_version],
        ).fetchall()

        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        resolution_cache: dict[str, ResolutionResult] = {}
        pending_results: list[ResolutionResult] = []
        for edge_id, claim_id, openalex_id, src, dst, direction, strength, confidence, design_family, design_tier in evidence_rows:
            src_key = str(src or "")
            dst_key = str(dst or "")
            src_resolution = resolution_cache.get(src_key)
            if src_resolution is None:
                src_resolution = materialized_resolutions.get(src_key) or resolver.resolve(src_key)
                resolution_cache[src_key] = src_resolution
                if src_key not in materialized_resolutions:
                    resolver.persist_resolution(con, src_resolution)
            dst_resolution = resolution_cache.get(dst_key)
            if dst_resolution is None:
                dst_resolution = materialized_resolutions.get(dst_key) or resolver.resolve(dst_key)
                resolution_cache[dst_key] = dst_resolution
                if dst_key not in materialized_resolutions:
                    resolver.persist_resolution(con, dst_resolution)
            if src_resolution.review_required:
                pending_results.append(src_resolution)
            if dst_resolution.review_required:
                pending_results.append(dst_resolution)
            src_family = _family_name(src_resolution.canonical_name, approved_names) if src_resolution.approved else None
            dst_family = _family_name(dst_resolution.canonical_name, approved_names) if dst_resolution.approved else None
            if not src_family or not dst_family:
                continue
            key = (src_family, dst_family, str(direction))
            payload = grouped.setdefault(
                key,
                {
                    "article_refs": set(),
                    "claim_refs": set(),
                    "evidence_samples": [],
                    "direction_histogram": Counter(),
                    "design_tier_histogram": Counter(),
                    "design_family_histogram": Counter(),
                    "exact_edge_ids": set(),
                },
            )
            meta = article_meta.get(str(openalex_id), {})
            payload["article_refs"].add(str(openalex_id))
            payload["claim_refs"].add(str(claim_id))
            payload["evidence_samples"].append(
                ArticleEvidence(
                    strength=str(strength),
                    extraction_confidence=float(confidence or 0.0),
                    publication_year=meta.get("year"),
                    sample_size=sample_sizes.get(str(openalex_id)),
                    source_basis=claim_source_basis.get(str(claim_id), "fulltext"),
                    retracted=bool(meta.get("retracted")),
                    fwci=meta.get("fwci"),
                )
            )
            payload["direction_histogram"][str(direction)] += 1
            if design_tier is not None:
                payload["design_tier_histogram"][str(int(design_tier))] += 1
            if design_family:
                payload["design_family_histogram"][str(design_family)] += 1
            payload["exact_edge_ids"].add(str(edge_id))

        pair_totals: dict[tuple[str, str], dict[str, Any]] = defaultdict(
            lambda: {
                "direction_histogram": Counter(),
                "article_refs": set(),
                "claim_refs": set(),
                "evidence_samples": [],
                "strengths": [],
                "direction_evidence": defaultdict(list),
                "family_edge_ids": set(),
                "exact_edge_ids": set(),
            }
        )
        for (src_family, dst_family, direction), payload in grouped.items():
            pair_payload = pair_totals[(src_family, dst_family)]
            pair_payload["direction_histogram"][direction] = len(payload["article_refs"])
            pair_payload["article_refs"].update(payload["article_refs"])
            pair_payload["claim_refs"].update(payload["claim_refs"])
            pair_payload["evidence_samples"].extend(payload["evidence_samples"])
            pair_payload["strengths"].extend(sample.strength for sample in payload["evidence_samples"])
            pair_payload["direction_evidence"][direction].extend(payload["evidence_samples"])
            pair_payload["exact_edge_ids"].update(payload["exact_edge_ids"])

        for (src_family, dst_family, direction), payload in grouped.items():
            article_refs = sorted(payload["article_refs"])
            claim_refs = sorted(payload["claim_refs"])
            evidence_samples = list(payload["evidence_samples"])
            pair_payload = pair_totals.get((src_family, dst_family), {})
            direction_counts = pair_payload.get("direction_histogram", {})
            total_direction_articles = max(1, sum(int(value) for value in direction_counts.values()))
            direction_agreement = len(article_refs) / total_direction_articles
            conflict_flag = len([count for count in direction_counts.values() if count > 0]) > 1
            family_rows.append(
                (
                    hash_edge_id(src_family, dst_family, direction),
                    src_family,
                    dst_family,
                    direction,
                    len(article_refs),
                    len(claim_refs),
                    json.dumps(article_refs, ensure_ascii=False),
                    json.dumps(claim_refs, ensure_ascii=False),
                    strongest_strength([sample.strength for sample in evidence_samples]),
                    aggregate_edge_confidence(evidence_samples),
                    json.dumps(dict(payload["direction_histogram"]), ensure_ascii=False),
                    json.dumps(dict(payload["design_tier_histogram"]), ensure_ascii=False),
                    json.dumps(dict(payload["design_family_histogram"]), ensure_ascii=False),
                    "family",
                    json.dumps(
                        {
                            "exact_edge_count": len(payload["exact_edge_ids"]),
                            "exact_edge_ids": sorted(payload["exact_edge_ids"]),
                            "n_unique_works": len(article_refs),
                            "n_unique_claims": len(claim_refs),
                            "direction_agreement": round(direction_agreement, 4),
                            "conflict_flag": conflict_flag,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
            pair_totals[(src_family, dst_family)]["family_edge_ids"].add(hash_edge_id(src_family, dst_family, direction))

        for (src_family, dst_family), payload in sorted(pair_totals.items()):
            direction_histogram = {str(key): int(value) for key, value in payload["direction_histogram"].items() if int(value) > 0}
            direction_summary = weighted_direction_summary(payload["direction_evidence"])
            positive_weight = float(direction_summary.direction_weights.get("positive", 0.0))
            negative_weight = float(direction_summary.direction_weights.get("negative", 0.0))
            mixed_weight = sum(
                float(direction_summary.direction_weights.get(direction, 0.0))
                for direction in ("mixed", "ambiguous", "non_linear")
            )
            if direction_summary.is_contested and positive_weight > 0.0 and negative_weight > 0.0:
                resolution_status = "contested"
                dominant_direction = str(direction_summary.dominant_direction or "mixed")
            elif mixed_weight > 0.0:
                resolution_status = "mixed"
                dominant_direction = "mixed"
            else:
                continue
            article_refs = sorted(payload["article_refs"])
            claim_refs = sorted(payload["claim_refs"])
            evidence_samples = list(payload["evidence_samples"])
            base_confidence = aggregate_edge_confidence(evidence_samples)
            minority_weight = max(0.0, 1.0 - float(direction_summary.agreement_score))
            confidence = max(0.15, base_confidence - (minority_weight * 0.5))
            contested_rows.append(
                (
                    hash_contested_edge_id(src_family, dst_family),
                    src_family,
                    dst_family,
                    len(article_refs),
                    len(claim_refs),
                    json.dumps(article_refs, ensure_ascii=False),
                    json.dumps(claim_refs, ensure_ascii=False),
                    dominant_direction,
                    resolution_status,
                    "MIXED",
                    strongest_strength(payload["strengths"]),
                    confidence,
                    positive_weight,
                    negative_weight,
                    mixed_weight,
                    float(direction_summary.agreement_score),
                    str(direction_summary.strongest_dissent_strength or ""),
                    int(direction_summary.strongest_dissent_year)
                    if direction_summary.strongest_dissent_year is not None
                    else None,
                    json.dumps(direction_histogram, ensure_ascii=False),
                    json.dumps(
                        {
                            "conflict_flag": True,
                            "exact_edge_count": len(payload["exact_edge_ids"]),
                            "family_edge_count": len(payload["family_edge_ids"]),
                            "exact_edge_ids": sorted(payload["exact_edge_ids"]),
                            "family_edge_ids": sorted(payload["family_edge_ids"]),
                            "weighted_direction_agreement": round(float(direction_summary.agreement_score), 6),
                        },
                        ensure_ascii=False,
                    ),
                )
            )

        con.execute("DELETE FROM ac_skg_family_edges")
        if family_rows:
            con.executemany(
                """
                INSERT OR REPLACE INTO ac_skg_family_edges(
                    family_edge_id, src_family, dst_family, direction,
                    n_articles, n_claims, article_refs, claim_refs,
                    evidence_strength, confidence, direction_histogram_json,
                    design_tier_histogram_json, design_family_histogram_json,
                    candidate_layer, quality_signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                family_rows,
            )
        con.execute("DELETE FROM ac_skg_contested_edges")
        if contested_rows:
            con.executemany(
                """
                INSERT OR REPLACE INTO ac_skg_contested_edges(
                    contested_edge_id, src_family, dst_family, n_articles, n_claims,
                    article_refs, claim_refs, dominant_direction, resolution_status,
                    runtime_support, evidence_strength, confidence,
                    positive_weight, negative_weight, mixed_weight,
                    dominant_direction_agreement, strongest_dissent_strength, strongest_dissent_year,
                    direction_histogram_json, quality_signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                contested_rows,
            )

        review_queue = _canonical_review_queue(con, pending_results=pending_results)
        canonization_summary = _canonization_summary(con)
        config.canonical_review_queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config.canonical_review_queue_path, "w", encoding="utf-8") as fh:
            for row in review_queue:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(config.edge_synthesis_report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "family_edges": len(family_rows),
                    "contested_edges": len(contested_rows),
                    "review_queue": len(review_queue),
                    "approved_canonical_names": len(resolver._approved_set),
                    "canonization": canonization_summary,
                },
                fh,
                ensure_ascii=False,
                indent=2,
            )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    metrics = {
        "family_edges": len(family_rows),
        "contested_edges": len(contested_rows),
        "review_queue": len(review_queue),
        "canonical_resolution_rate_pct": float(canonization_summary["resolution_rate_pct"]),
        "canonical_auto_approved": int(canonization_summary["auto_approved"]),
        "canonical_pending_review": int(canonization_summary["pending_review"]),
        "canonical_unresolved": int(canonization_summary["unresolved"]),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "edge_synthesize.json",
        stage="edge_synthesize",
        status="ok",
        metrics=metrics,
        artifacts=[config.db_path, config.canonical_review_queue_path, config.edge_synthesis_report_path],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_edge_synthesize"]
