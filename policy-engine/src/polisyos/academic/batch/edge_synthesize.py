"""Synthesize family-level evidence layers from exact SKG edges."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.academic.knowledge.skg_store import (
    aggregate_edge_confidence,
    ensure_skg_schema,
    hash_edge_id,
    parent_canonical_name,
    strongest_strength,
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


def _approved_family(name: str, approved: set[str]) -> str | None:
    candidate = str(name or "").strip()
    if not candidate:
        return None
    best = candidate if candidate in approved else None
    parent = parent_canonical_name(candidate)
    while parent:
        if parent in approved:
            best = parent
        parent = parent_canonical_name(parent)
    return best


def _canonical_review_queue(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    unresolved = con.execute(
        """
        SELECT raw_name, canonical_name
        FROM ac_skg_canonization_cache
        WHERE approved = FALSE
        ORDER BY canonical_name, raw_name
        """
    ).fetchall()
    if not unresolved:
        return []
    variable_counts = {
        str(row[0]): int(row[1] or 0)
        for row in con.execute(
            "SELECT canonical_name, mention_count FROM ac_skg_variables"
        ).fetchall()
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
    queue: list[dict[str, Any]] = []
    for raw_name, canonical_name in unresolved:
        canonical = str(canonical_name or "")
        queue.append(
            {
                "raw_name": str(raw_name or ""),
                "suggested_canonical_name": canonical,
                "variable_mentions": int(variable_counts.get(canonical, 0)),
                "context_mentions": int(context_counts.get(canonical, 0)),
                "moderator_mentions": int(moderator_counts.get(canonical, 0)),
                "total_mentions": int(
                    variable_counts.get(canonical, 0)
                    + context_counts.get(canonical, 0)
                    + moderator_counts.get(canonical, 0)
                ),
            }
        )
    queue.sort(key=lambda row: (-int(row["total_mentions"]), row["suggested_canonical_name"], row["raw_name"]))
    return queue


def run_edge_synthesize(config: AcademicBatchConfig) -> dict[str, int]:
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
    review_queue: list[dict[str, Any]] = []
    try:
        ensure_skg_schema(con)
        approved = _approved_canonical_names(con)
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
        for edge_id, claim_id, openalex_id, src, dst, direction, strength, confidence, design_family, design_tier in evidence_rows:
            src_family = _approved_family(str(src), approved)
            dst_family = _approved_family(str(dst), approved)
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
            payload["article_refs"].add(str(openalex_id))
            payload["claim_refs"].add(str(claim_id))
            payload["evidence_samples"].append((str(strength), float(confidence or 0.0)))
            payload["direction_histogram"][str(direction)] += 1
            if design_tier is not None:
                payload["design_tier_histogram"][str(int(design_tier))] += 1
            if design_family:
                payload["design_family_histogram"][str(design_family)] += 1
            payload["exact_edge_ids"].add(str(edge_id))

        pair_totals: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        for (src_family, dst_family, direction), payload in grouped.items():
            pair_totals[(src_family, dst_family)][direction] = len(payload["article_refs"])

        for (src_family, dst_family, direction), payload in grouped.items():
            article_refs = sorted(payload["article_refs"])
            claim_refs = sorted(payload["claim_refs"])
            evidence_samples = list(payload["evidence_samples"])
            direction_counts = pair_totals.get((src_family, dst_family), {})
            total_direction_articles = max(1, sum(direction_counts.values()))
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
                    strongest_strength([str(sample[0]) for sample in evidence_samples]),
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

        review_queue = _canonical_review_queue(con)
        config.canonical_review_queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config.canonical_review_queue_path, "w", encoding="utf-8") as fh:
            for row in review_queue:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(config.edge_synthesis_report_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "family_edges": len(family_rows),
                    "review_queue": len(review_queue),
                    "approved_canonical_names": len(approved),
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
        "review_queue": len(review_queue),
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
