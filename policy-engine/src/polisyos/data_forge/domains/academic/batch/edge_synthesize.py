"""Synthesize family-level evidence layers from exact SKG edges."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.data_forge.domains.academic.batch._graph_staging import (
    DiskValues,
    GraphCapacityLimits,
    RowSpool,
    StagingStore,
    execute_rows,
    observe_stored_source_provenance,
    publish_owned_output,
    query_rows,
)
from polisyos.data_forge.domains.academic.batch.graph_builder import (
    _bounded_resolver,
    _configure_graph_capacity,
)
from polisyos.data_forge.domains.academic.knowledge.canonical_resolver import (
    ResolutionResult,
)
from polisyos.data_forge.domains.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ArticleEvidence,
    aggregate_edge_confidence,
    ensure_skg_schema,
    hash_contested_edge_id,
    hash_edge_id,
    parent_canonical_name,
    strongest_strength,
    weighted_direction_summary,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_stage_manifest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Literal

    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


# This is the existing writers' codec contract, reconciled against every actual
# source SELECT (including resolver reads) and complete live table schemas in tests.
# Empty families have no own persisted ancestry; absence never establishes false.
_SOURCE_PROVENANCE_CODECS: dict[str, dict[str, Literal["boolean", "json"]]] = {
    "ac_causal_claims_raw": {"synthetic": "boolean", "source_provenance_json": "json"},
    "ac_skg_articles": {"extraction_json": "json", "context_json": "json"},
    "ac_skg_edges": {"quality_signals_json": "json"},
    "ac_works": {},
    "ac_parameter_estimates": {},
    "ac_claim_adjudications": {},
    "ac_skg_variables": {},
    "ac_skg_edge_evidence": {},
    "ac_skg_context_attributes": {},
    "ac_skg_moderation_edges": {},
    "ac_skg_versions": {},
    "ac_skg_canonization_cache": {},
    "ac_skg_variable_synonyms": {},
}


def _seed_canonical_names() -> set[str]:
    names: set[str] = set()
    for parent, children in CANONICAL_VARIABLES.items():
        names.add(parent)
        for child_key in children:
            if child_key == "_root":
                continue
            names.add(f"{parent}.{child_key}")
    return names


def _approved_canonical_names(con: duckdb.DuckDBPyConnection, staging: StagingStore) -> set[str]:
    approved = {
        str(row[0])
        for row in query_rows(
            con,
            "SELECT canonical_name FROM ac_skg_canonization_cache WHERE approved = TRUE",
            store=staging,
        )
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


def _mention_maps(
    con: duckdb.DuckDBPyConnection,
    staging: StagingStore,
) -> tuple[DiskValues, DiskValues, DiskValues]:
    variable_counts = staging.values("variable_counts")
    try:
        variable_rows = query_rows(
            con, "SELECT normalized_name, mention_count FROM ac_skg_variables", store=staging
        )
    except duckdb.Error:
        variable_rows = query_rows(
            con, "SELECT canonical_name, mention_count FROM ac_skg_variables", store=staging
        )
    for row in variable_rows:
        if row and row[0]:
            variable_counts[str(row[0])] = int(row[1] or 0)
    context_counts = staging.values("context_counts")
    for row in query_rows(
        con,
        "SELECT canonical_name, COUNT(*) FROM ac_skg_context_attributes GROUP BY canonical_name",
        store=staging,
    ):
        if row and row[0]:
            context_counts[str(row[0])] = int(row[1] or 0)
    moderator_counts = staging.values("moderator_counts")
    for row in query_rows(
        con,
        "SELECT moderator, COUNT(*) FROM ac_skg_moderation_edges GROUP BY moderator",
        store=staging,
    ):
        if row and row[0]:
            moderator_counts[str(row[0])] = int(row[1] or 0)
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


def _append_review_row(queue: RowSpool, row: dict[str, Any]) -> None:
    queue.append(
        row,
        sort_key=(
            -int(row["total_mentions"]),
            str(row["suggested_canonical_name"]),
            str(row["raw_name"]),
        ),
    )


def _canonical_review_queue(
    con: duckdb.DuckDBPyConnection,
    *,
    pending_results: RowSpool | None = None,
    staging: StagingStore,
) -> RowSpool:
    unresolved = query_rows(
        con,
        """
        SELECT raw_name, canonical_name
        FROM ac_skg_canonization_cache
        WHERE approved = FALSE
        ORDER BY canonical_name, raw_name
        """,
        store=staging,
    )
    variable_counts, context_counts, moderator_counts = _mention_maps(con, staging)
    queue = staging.rows("review_queue")
    seen = staging.values("review_seen")
    for raw_name, canonical_name in unresolved:
        canonical = str(canonical_name or "")
        seen.add((str(raw_name or ""), canonical))
        lookup_keys = _review_lookup_keys(str(raw_name or ""), canonical)
        _append_review_row(
            queue,
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
            },
        )
    for result in pending_results or []:
        key = (result.raw_name, str(result.canonical_name or ""))
        if key in seen:
            continue
        canonical = str(result.canonical_name or "")
        lookup_keys = _review_lookup_keys(result.raw_name, canonical)
        _append_review_row(
            queue,
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
            },
        )
    return queue


def _materialized_resolution_map(
    con: duckdb.DuckDBPyConnection, staging: StagingStore
) -> DiskValues:
    mapping = staging.values("materialized_resolutions")
    try:
        rows = query_rows(
            con,
            """
            SELECT canonical_name, approved_canonical_name, is_approved_canonical,
                   resolution_method, resolution_confidence
            FROM ac_skg_variables
            """,
            store=staging,
        )
    except duckdb.Error:
        return mapping
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


def _canonization_summary(
    con: duckdb.DuckDBPyConnection, staging: StagingStore
) -> dict[str, float | int]:
    try:
        rows = query_rows(
            con,
            """
            SELECT resolution_method, is_approved_canonical, approved_canonical_name
            FROM ac_skg_variables
            """,
            store=staging,
        )
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


def _article_meta(con: duckdb.DuckDBPyConnection, staging: StagingStore) -> DiskValues:
    try:
        rows = query_rows(
            con,
            """
            SELECT a.openalex_id, a.year, a.retracted, w.fwci
            FROM ac_skg_articles a
            LEFT JOIN ac_works w ON w.id = a.openalex_id
            """,
            store=staging,
        )
    except duckdb.Error:
        rows = query_rows(
            con,
            """
            SELECT openalex_id, year, retracted, NULL AS fwci
            FROM ac_skg_articles
            """,
            store=staging,
        )
    mapping = staging.values("article_meta")
    for openalex_id, year, retracted, fwci in rows:
        if openalex_id:
            mapping[str(openalex_id)] = {
                "year": int(year) if year is not None else None,
                "retracted": bool(retracted),
                "fwci": float(fwci) if fwci is not None else None,
            }
    return mapping


def _sample_sizes(con: duckdb.DuckDBPyConnection, staging: StagingStore) -> DiskValues:
    mapping = staging.values("sample_sizes")
    try:
        rows = query_rows(
            con,
            """
            SELECT work_id, MAX(sample_size)
            FROM ac_parameter_estimates
            WHERE sample_size IS NOT NULL AND sample_size > 0
            GROUP BY work_id
            """,
            store=staging,
        )
    except duckdb.Error:
        return mapping
    for work_id, sample_size in rows:
        if work_id and sample_size is not None:
            mapping[str(work_id)] = int(sample_size)
    return mapping


def _claim_source_basis(con: duckdb.DuckDBPyConnection, staging: StagingStore) -> DiskValues:
    mapping = staging.values("claim_source_basis")
    for table_name, claim_col in (
        ("ac_claim_adjudications", "claim_id"),
        ("ac_causal_claims_raw", "id"),
    ):
        try:
            rows = query_rows(
                con, f"SELECT {claim_col}, source_basis FROM {table_name}", store=staging
            )
        except duckdb.Error:
            continue
        for claim_id, source_basis in rows:
            clean_claim_id = str(claim_id or "").strip()
            if clean_claim_id and clean_claim_id not in mapping:
                mapping[clean_claim_id] = str(source_basis or "fulltext")
    return mapping


def _synthetic_projection(values: list[object]) -> dict[str, bool]:
    """Union known synthetic ancestry; missing provenance never means real."""
    if any(value is True for value in values):
        return {"synthetic": True}
    if values and all(value is False for value in values):
        return {"synthetic": False}
    return {}


def run_edge_synthesize(
    config: AcademicBatchConfig,
    *,
    source_provenance: dict[str, object] | None = None,
    capacity_limits: GraphCapacityLimits | None = None,
    staging_dir: Path | None = None,
) -> dict[str, int]:
    """Run edge synthesize."""
    started_at = datetime.now(UTC).isoformat()
    limits = capacity_limits or GraphCapacityLimits()
    stage_path = config.manifests_dir / "edge_synthesize.json"
    stage_root = staging_dir or config.db_path.with_suffix(config.db_path.suffix + ".staging")
    if not config.db_path.exists():
        publish_owned_output(
            stage_path,
            lambda private: write_stage_manifest(
                manifest_path=private,
                stage="edge_synthesize",
                status="ok",
                metrics={"family_edges": 0, "review_queue": 0, **(source_provenance or {})},
                artifacts=[],
                started_at=started_at,
            ),
            paths=(stage_path,),
            limits=limits,
            temporary_root=stage_root,
        )
        return {"family_edges": 0, "review_queue": 0}

    con = duckdb.connect(str(config.db_path))
    staging: StagingStore | None = None
    try:
        staging = StagingStore(
            stage_root / "edge-synthesize.sqlite",
            limits,
            source_provenance=source_provenance,
        )
        staging.reset()
        staging.track_outputs(
            config.canonical_review_queue_path, config.edge_synthesis_report_path, stage_path
        )
        staging.register_type(ArticleEvidence)
        staging.register_type(ResolutionResult)
        _configure_graph_capacity(con, staging, config.db_path)
        ensure_skg_schema(con)
        observe_stored_source_provenance(con, _SOURCE_PROVENANCE_CODECS, store=staging)
        input_provenance = staging.provenance()
        family_rows = staging.rows("family_rows")
        contested_rows = staging.rows("contested_rows")
        resolver = _bounded_resolver(con, staging)
        approved_names = _approved_canonical_names(con, staging)
        materialized_resolutions = _materialized_resolution_map(con, staging)
        article_meta = _article_meta(con, staging)
        sample_sizes = _sample_sizes(con, staging)
        claim_source_basis = _claim_source_basis(con, staging)
        exact_provenance = staging.values("exact_provenance")
        for edge_id, quality in query_rows(
            con, "SELECT edge_id,quality_signals_json FROM ac_skg_edges", store=staging
        ):
            exact_provenance[str(edge_id)] = json.loads(quality or "{}")

        version_row = con.execute(
            "SELECT COALESCE(MAX(version_id), 0) FROM ac_skg_versions"
        ).fetchone()
        skg_version = int(version_row[0] or 0) if version_row else 0

        evidence_rows = query_rows(
            con,
            """
            SELECT edge_id, claim_id, openalex_id, src, dst, direction,
                   evidence_strength, confidence, design_family, design_quality_tier
            FROM ac_skg_edge_evidence
            WHERE skg_version = ?
            """,
            [skg_version],
            store=staging,
        )

        grouped = staging.groups("directional_groups")
        resolution_cache = staging.values("resolution_cache")
        pending_results = staging.rows("pending_results")
        for (
            edge_id,
            claim_id,
            openalex_id,
            src,
            dst,
            direction,
            strength,
            confidence,
            design_family,
            design_tier,
        ) in evidence_rows:
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
            src_family = (
                _family_name(src_resolution.canonical_name, approved_names)
                if src_resolution.approved
                else None
            )
            dst_family = (
                _family_name(dst_resolution.canonical_name, approved_names)
                if dst_resolution.approved
                else None
            )
            if not src_family or not dst_family:
                continue
            key = (src_family, dst_family, str(direction))
            with grouped.edit(
                key,
                lambda: {
                    "article_refs": set(),
                    "claim_refs": set(),
                    "evidence_samples": [],
                    "direction_histogram": Counter(),
                    "design_tier_histogram": Counter(),
                    "design_family_histogram": Counter(),
                    "exact_edge_ids": set(),
                    "synthetic_sources": [],
                },
                contribution=(
                    edge_id,
                    claim_id,
                    openalex_id,
                    src,
                    dst,
                    direction,
                    strength,
                    confidence,
                    design_family,
                    design_tier,
                ),
            ) as payload:
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
                payload["synthetic_sources"].append(
                    True
                    if input_provenance["synthetic"] is True
                    else exact_provenance[str(edge_id)].get("synthetic")
                )

        pair_totals = staging.groups("family_pairs", pair=True)

        def pair_factory() -> dict[str, Any]:
            return {
                "direction_histogram": Counter(),
                "article_refs": set(),
                "claim_refs": set(),
                "evidence_samples": [],
                "strengths": [],
                "direction_evidence": defaultdict(list),
                "family_edge_ids": set(),
                "exact_edge_ids": set(),
                "synthetic_sources": [],
            }

        for (src_family, dst_family, direction), payload in grouped.items():
            with pair_totals.edit(
                (src_family, dst_family),
                pair_factory,
                contribution_delta=len(payload["evidence_samples"]),
                contribution=payload,
            ) as pair_payload:
                pair_payload["direction_histogram"][direction] = len(payload["article_refs"])
                pair_payload["article_refs"].update(payload["article_refs"])
                pair_payload["claim_refs"].update(payload["claim_refs"])
                pair_payload["evidence_samples"].extend(payload["evidence_samples"])
                pair_payload["strengths"].extend(
                    sample.strength for sample in payload["evidence_samples"]
                )
                pair_payload["direction_evidence"][direction].extend(payload["evidence_samples"])
                pair_payload["exact_edge_ids"].update(payload["exact_edge_ids"])
                pair_payload["synthetic_sources"].extend(payload["synthetic_sources"])

        for (src_family, dst_family, direction), payload in grouped.items():
            article_refs = sorted(payload["article_refs"])
            claim_refs = sorted(payload["claim_refs"])
            evidence_samples = list(payload["evidence_samples"])
            pair_payload = pair_totals.get((src_family, dst_family), {})
            direction_counts = pair_payload.get("direction_histogram", {})
            total_direction_articles = max(
                1, sum(int(value) for value in direction_counts.values())
            )
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
                            **_synthetic_projection(payload["synthetic_sources"]),
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
            family_id = hash_edge_id(src_family, dst_family, direction)
            with pair_totals.edit(
                (src_family, dst_family), dict, contribution_delta=0, contribution=family_id
            ) as pair_payload:
                pair_payload["family_edge_ids"].add(family_id)

        for (src_family, dst_family), payload in pair_totals.iter_items(order="key"):
            direction_histogram = {
                str(key): int(value)
                for key, value in payload["direction_histogram"].items()
                if int(value) > 0
            }
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
                            **_synthetic_projection(payload["synthetic_sources"]),
                            "conflict_flag": True,
                            "exact_edge_count": len(payload["exact_edge_ids"]),
                            "family_edge_count": len(payload["family_edge_ids"]),
                            "exact_edge_ids": sorted(payload["exact_edge_ids"]),
                            "family_edge_ids": sorted(payload["family_edge_ids"]),
                            "weighted_direction_agreement": round(
                                float(direction_summary.agreement_score), 6
                            ),
                        },
                        ensure_ascii=False,
                    ),
                )
            )

        con.execute("DELETE FROM ac_skg_family_edges")
        if family_rows:
            execute_rows(
                con,
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
            execute_rows(
                con,
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

        review_queue = _canonical_review_queue(
            con, pending_results=pending_results, staging=staging
        )
        canonization_summary = _canonization_summary(con, staging)
        output_provenance = {**(source_provenance or {}), **staging.provenance()}
        config.canonical_review_queue_path.parent.mkdir(parents=True, exist_ok=True)
        with staging.text_output(config.canonical_review_queue_path) as fh:
            for batch in review_queue.iter_batches(sorted_rows=True):
                for row in batch:
                    emitted = {
                        **row,
                        "synthetic": output_provenance["synthetic"],
                        "source_provenance": output_provenance,
                    }
                    staging.check(
                        "max_record_bytes", "canonical review row", staging.encoded_size(emitted)
                    )
                    fh.write(json.dumps(emitted, ensure_ascii=False) + "\n")
        with staging.text_output(config.edge_synthesis_report_path) as fh:
            json.dump(
                {
                    **output_provenance,
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
        staging.check_disk(config.db_path)
        family_count, contested_count, review_count = (
            len(family_rows),
            len(contested_rows),
            len(review_queue),
        )
    finally:
        if staging is not None:
            staging.close()
        con.close()

    metrics = {
        "family_edges": family_count,
        "contested_edges": contested_count,
        "review_queue": review_count,
        "canonical_resolution_rate_pct": float(canonization_summary["resolution_rate_pct"]),
        "canonical_auto_approved": int(canonization_summary["auto_approved"]),
        "canonical_pending_review": int(canonization_summary["pending_review"]),
        "canonical_unresolved": int(canonization_summary["unresolved"]),
    }
    staging.publish_output(
        stage_path,
        lambda private: write_stage_manifest(
            manifest_path=private,
            stage="edge_synthesize",
            status="ok",
            metrics={**metrics, **output_provenance},
            artifacts=[
                config.db_path,
                config.canonical_review_queue_path,
                config.edge_synthesis_report_path,
            ],
            started_at=started_at,
        ),
    )
    return metrics


__all__ = ["run_edge_synthesize"]
