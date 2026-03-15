"""Stage: compute edge-level transport scores using moderation data."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from statistics import median
from typing import Any

import duckdb

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.knowledge.skg_store import (
    ensure_skg_schema,
    hash_context_profile_id,
    hash_transport_score_id,
)
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


def _context_attr_filter_clause(
    con: duckdb.DuckDBPyConnection,
    *,
    skg_version: int,
) -> str:
    """Use evidence-backed context rows when available, but fall back for legacy snapshots."""
    try:
        row = con.execute(
            "SELECT COUNT(*) FROM ac_skg_context_attributes WHERE skg_version = ? AND evidence_span_count > 0",
            [skg_version],
        ).fetchone()
    except duckdb.CatalogException:
        return ""
    count = int(row[0] or 0) if row else 0
    return " AND evidence_span_count > 0 " if count > 0 else ""


def _significant_moderators(moderators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        moderator
        for moderator in moderators
        if moderator.get("interaction_pvalue") is not None and float(moderator["interaction_pvalue"]) < 0.10
    ]


def _has_significance_signal(moderator: dict[str, Any]) -> bool:
    """Check if moderator has any evidence of significance (even without p-value)."""
    if moderator.get("interaction_pvalue") is not None:
        return float(moderator["interaction_pvalue"]) < 0.10
    # Moderators with explicit direction (not null) and decent confidence
    # are evidence of context-sensitivity even without a p-value
    direction = str(moderator.get("direction") or moderator.get("direction_of_moderation") or "")
    confidence = float(moderator.get("confidence") or 0.0)
    return direction in {"amplifying", "dampening", "reversing", "threshold"} and confidence >= 0.5


def _moderation_penalty_amount(moderators: list[dict[str, Any]]) -> float:
    # Strong penalty for moderators with explicit p-value < 0.10
    significant = _significant_moderators(moderators)
    strong_penalty = min(0.20, 0.05 * len(significant))
    # Soft penalty for moderators with directional signal but no p-value
    soft_signal = [
        m for m in moderators
        if m not in significant and _has_significance_signal(m)
    ]
    soft_penalty = min(0.10, 0.02 * len(soft_signal))
    return min(0.30, strong_penalty + soft_penalty)


def _apply_moderation_penalty(base_confidence: float, moderators: list[dict[str, Any]]) -> float:
    """Compatibility helper used in tests."""
    return max(0.0, base_confidence - _moderation_penalty_amount(moderators))


def _build_context_profiles(
    con: duckdb.DuckDBPyConnection,
    skg_version: int,
) -> int:
    """Aggregate context attributes into context profiles by country+time_period."""
    evidence_filter = _context_attr_filter_clause(con, skg_version=skg_version)
    rows = con.execute(
        "SELECT country_code, time_period, canonical_name, attribute_value, "
        "value_qualitative, confidence, COUNT(*) as n_articles "
        "FROM ac_skg_context_attributes "
        f"WHERE skg_version = ? {evidence_filter} AND country_code IS NOT NULL AND country_code != '' "
        "GROUP BY country_code, time_period, canonical_name, attribute_value, value_qualitative, confidence"
    , [skg_version]).fetchall()

    if not rows:
        return 0

    profiles: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "attributes": {},
            "n_articles": 0,
        }
    )
    for country_code, time_period, canonical_name, value, value_qual, confidence, n in rows:
        key = (str(country_code), str(time_period or ""))
        profile = profiles[key]
        profile["attributes"][canonical_name] = {
            "value": float(value) if value is not None else None,
            "value_qualitative": str(value_qual) if value_qual else None,
            "confidence": float(confidence or 0.5),
        }
        profile["n_articles"] = max(profile["n_articles"], int(n))

    profile_batch: list[tuple[Any, ...]] = []
    for (country_code, time_period), data in profiles.items():
        profile_id = hash_context_profile_id(country_code, time_period)
        label = f"{country_code} ({time_period})" if time_period else country_code
        profile_json = json.dumps(
            {
                "context_id": country_code,
                "context_label": label,
                "countries": [country_code],
                "time_period": time_period,
                "attributes": data["attributes"],
            },
            ensure_ascii=False,
        )
        profile_batch.append(
            (
                profile_id,
                country_code,
                label,
                profile_json,
                data["n_articles"],
                0,
                skg_version,
            )
        )

    con.execute("DELETE FROM ac_skg_context_profiles WHERE skg_version = ?", [skg_version])
    if profile_batch:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_context_profiles(
                profile_id, context_id, context_label, profile_json,
                n_source_articles, n_external_sources, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            profile_batch,
        )
    return len(profile_batch)


def _tokenize(value: str) -> set[str]:
    tokens = [token for token in str(value or "").lower().replace(".", "_").split("_") if token]
    return set(tokens)


def _token_overlap(left: str, right: str) -> float:
    lt = _tokenize(left)
    rt = _tokenize(right)
    if not lt or not rt:
        return 0.0
    return len(lt & rt) / max(1, len(lt | rt))


def _match_moderators_for_edge(
    src: str,
    dst: str,
    mod_index: dict[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], str]:
    exact = mod_index.get((str(src), str(dst)), [])
    if exact:
        if any(str(item.get("base_claim_id") or "").strip() for item in exact):
            return exact, "claim_ref"
        if any(str(item.get("match_quality") or "") == "exact_claim_ref" for item in exact):
            return exact, "claim_ref"
        return exact, "exact"

    best_score = 0.0
    best_match: list[dict[str, Any]] = []
    for (mod_src, mod_dst), moderators in mod_index.items():
        src_score = _token_overlap(str(src), mod_src)
        dst_score = _token_overlap(str(dst), mod_dst)
        score = (src_score + dst_score) / 2.0
        if score > best_score:
            best_score = score
            best_match = moderators
    if best_score >= 0.60:
        return best_match, "fuzzy"
    return [], ""


def _attribute_keys_for_lookup(name: str) -> list[str]:
    text = str(name or "").strip()
    if not text:
        return []
    suffix = text.rsplit(".", 1)[-1]
    return [text, suffix]


def _find_profile_attribute(profile: dict[str, Any], moderator_name: str) -> dict[str, Any] | None:
    attributes = profile.get("attributes", {}) if isinstance(profile, dict) else {}
    if not isinstance(attributes, dict):
        return None
    for key in _attribute_keys_for_lookup(moderator_name):
        if key in attributes and isinstance(attributes[key], dict):
            return attributes[key]
    for attr_name, payload in attributes.items():
        if not isinstance(payload, dict):
            continue
        if any(
            attr_name == candidate or attr_name.endswith(f".{candidate}")
            for candidate in _attribute_keys_for_lookup(moderator_name)
        ):
            return payload
    return None


def _aggregate_context_rows(rows: list[tuple[Any, ...]], *, context_id: str, time_period: str) -> dict[str, Any]:
    grouped: dict[str, list[tuple[Any, Any, float]]] = defaultdict(list)
    for canonical_name, value, value_qualitative, confidence in rows:
        grouped[str(canonical_name)].append((value, value_qualitative, float(confidence or 0.5)))

    attributes: dict[str, dict[str, Any]] = {}
    for canonical_name, values in grouped.items():
        numeric_values = [float(value) for value, _, _ in values if value is not None]
        qualitative_values = [str(label) for _, label, _ in values if label]
        attributes[canonical_name] = {
            "value": float(median(numeric_values)) if numeric_values else None,
            "value_qualitative": Counter(qualitative_values).most_common(1)[0][0] if qualitative_values else None,
            "confidence": max((conf for _, _, conf in values), default=0.5),
        }
    return {
        "context_id": context_id,
        "context_label": f"{context_id} ({time_period})" if time_period else context_id,
        "countries": [context_id] if context_id else [],
        "time_period": time_period,
        "attributes": attributes,
    }


def _load_target_context_profile(
    con: duckdb.DuckDBPyConnection,
    config: AcademicBatchConfig,
    *,
    skg_version: int,
) -> tuple[str, dict[str, Any] | None]:
    target_context_id = str(config.transport_target_context_id or "").strip()
    if target_context_id:
        row = con.execute(
            "SELECT profile_json FROM ac_skg_context_profiles "
            "WHERE skg_version = ? AND (profile_id = ? OR context_id = ?) LIMIT 1",
            [skg_version, target_context_id, target_context_id],
        ).fetchone()
        if row and row[0]:
            return target_context_id, json.loads(str(row[0]))

    if not config.transport_target_country_codes:
        return "", None

    countries = list(config.transport_target_country_codes)
    time_period = str(config.transport_target_time_period or "")
    evidence_filter = _context_attr_filter_clause(con, skg_version=skg_version)
    rows = con.execute(
        """
        SELECT canonical_name, attribute_value, value_qualitative, confidence
        FROM ac_skg_context_attributes
        WHERE skg_version = ?
          {evidence_filter}
          AND country_code IN ({placeholders})
          AND (? = '' OR time_period = ?)
        """.format(
            evidence_filter=evidence_filter,
            placeholders=",".join("?" for _ in countries),
        ),
        [skg_version, *countries, time_period, time_period],
    ).fetchall()
    if not rows:
        return target_context_id, None
    context_id = target_context_id or "+".join(countries)
    return context_id, _aggregate_context_rows(rows, context_id=context_id, time_period=time_period)


def _load_source_context_for_edge(
    con: duckdb.DuckDBPyConnection,
    article_refs: list[str],
    *,
    skg_version: int,
) -> dict[str, Any] | None:
    if not article_refs:
        return None
    evidence_filter = _context_attr_filter_clause(con, skg_version=skg_version)
    rows = con.execute(
        """
        SELECT canonical_name, attribute_value, value_qualitative, confidence
        FROM ac_skg_context_attributes
        WHERE skg_version = ? {evidence_filter} AND openalex_id IN ({placeholders})
        """.format(
            evidence_filter=evidence_filter,
            placeholders=",".join("?" for _ in article_refs),
        ),
        [skg_version, *article_refs],
    ).fetchall()
    if not rows:
        return None
    return _aggregate_context_rows(rows, context_id="source", time_period="")


def _context_similarity(
    source_profile: dict[str, Any] | None,
    target_profile: dict[str, Any] | None,
    moderators: list[dict[str, Any]],
) -> float:
    if source_profile is None or target_profile is None:
        return 0.0

    scores: list[float] = []
    relevant = [m for m in moderators if _has_significance_signal(m)]
    for moderator in relevant:
        moderator_name = str(moderator.get("moderator") or "")
        if not moderator_name:
            continue
        source_attr = _find_profile_attribute(source_profile, moderator_name)
        target_attr = _find_profile_attribute(target_profile, moderator_name)
        if source_attr is None or target_attr is None:
            continue

        source_value = source_attr.get("value")
        target_value = target_attr.get("value")
        if source_value is not None and target_value is not None:
            denom = max(abs(float(source_value)), abs(float(target_value)), 1.0)
            distance = abs(float(source_value) - float(target_value)) / denom
            scores.append(1.0 - min(1.0, distance))
            continue

        source_label = str(source_attr.get("value_qualitative") or "").strip().lower()
        target_label = str(target_attr.get("value_qualitative") or "").strip().lower()
        if source_label and target_label:
            scores.append(1.0 if source_label == target_label else _token_overlap(source_label, target_label))

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _target_dimension_coverage(
    target_profile: dict[str, Any] | None,
    moderators: list[dict[str, Any]],
) -> float:
    """Fraction of relevant moderator dimensions present in the target context.

    When source context is unavailable (common: only ~2% of articles have
    context attributes), we still reward edges whose moderated dimensions
    are *measurable* in the target context.  This partial signal avoids the
    all-or-nothing cliff of requiring source-vs-target matching.
    """
    if target_profile is None:
        return 0.0
    relevant = [m for m in moderators if _has_significance_signal(m)]
    if not relevant:
        return 0.0
    covered = 0
    for moderator in relevant:
        moderator_name = str(moderator.get("moderator") or "")
        if moderator_name and _find_profile_attribute(target_profile, moderator_name) is not None:
            covered += 1
    return covered / len(relevant)


def run_transport_score(config: AcademicBatchConfig) -> dict[str, int]:
    """Score edges for transportability using moderation data."""
    started_at = datetime.now(UTC).isoformat()
    result: dict[str, int] = {
        "edges_scored": 0,
        "moderators_applied": 0,
        "profiles_built": 0,
        "transport_scores_written": 0,
    }

    if not config.db_path.exists():
        logger.warning("SKG database not found at %s, skipping transport_score", config.db_path)
        return result

    con = duckdb.connect(str(config.db_path))
    transport_rows: list[dict[str, Any]] = []
    try:
        ensure_skg_schema(con)

        version_row = con.execute("SELECT COALESCE(MAX(version_id), 0) FROM ac_skg_versions").fetchone()
        skg_version = int(version_row[0]) if version_row else 0
        if skg_version == 0:
            logger.info("No SKG version found, skipping transport_score")
            return result

        result["profiles_built"] = _build_context_profiles(con, skg_version)

        mod_rows = con.execute(
            "SELECT base_cause, base_effect, moderator, direction_of_mod, interaction_coeff, "
            "interaction_pvalue, confidence, match_quality, alignment_source, base_claim_id "
            "FROM ac_skg_moderation_edges WHERE skg_version = ?",
            [skg_version],
        ).fetchall()
        mod_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in mod_rows:
            key = (str(row[0]), str(row[1]))
            mod_index[key].append(
                {
                    "moderator": str(row[2]),
                    "direction": str(row[3] or ""),
                    "interaction_coeff": row[4],
                    "interaction_pvalue": row[5],
                    "confidence": float(row[6] or 0.5),
                    "match_quality": str(row[7] or ""),
                    "alignment_source": str(row[8] or ""),
                    "base_claim_id": str(row[9] or "") or None,
                }
            )

        target_context_id, target_context_profile = _load_target_context_profile(con, config, skg_version=skg_version)
        target_context_key = target_context_id or ""

        edges = con.execute(
            "SELECT edge_id, src, dst, confidence, article_refs FROM ac_skg_edges"
        ).fetchall()

        transport_batch: list[tuple[Any, ...]] = []
        con.execute("DELETE FROM ac_skg_transport_scores WHERE skg_version = ?", [skg_version])

        for edge_id, src, dst, confidence, article_refs_json in edges:
            moderators, match_mode = _match_moderators_for_edge(str(src), str(dst), mod_index)
            matched_count = len(moderators)
            if matched_count:
                result["moderators_applied"] += matched_count
            result["edges_scored"] += 1

            penalty = _moderation_penalty_amount(moderators)
            source_refs = json.loads(str(article_refs_json or "[]"))
            article_refs = [str(item) for item in source_refs if item]
            source_context_profile = _load_source_context_for_edge(con, article_refs, skg_version=skg_version)
            similarity = _context_similarity(source_context_profile, target_context_profile, moderators)
            has_relevant = any(_has_significance_signal(m) for m in moderators)
            if target_context_profile is not None and has_relevant:
                if source_context_profile is not None and similarity > 0.0:
                    # Full reward: both profiles available and matching
                    reward = similarity * 0.20
                else:
                    # Partial reward: source context unavailable but target
                    # has data on the moderated dimensions — edge is at least
                    # "measurable" in the target context.
                    coverage = _target_dimension_coverage(target_context_profile, moderators)
                    reward = coverage * 0.10
            else:
                reward = 0.0
            transport_confidence = max(0.0, min(1.0, float(confidence) - penalty + reward))

            matched_json = json.dumps(moderators, ensure_ascii=False)
            transport_id = hash_transport_score_id(str(edge_id), target_context_key)
            transport_batch.append(
                (
                    transport_id,
                    str(edge_id),
                    target_context_key,
                    float(confidence),
                    penalty,
                    reward,
                    transport_confidence,
                    match_mode,
                    matched_json,
                    skg_version,
                )
            )
            transport_rows.append(
                {
                    "transport_id": transport_id,
                    "edge_id": str(edge_id),
                    "target_context_id": target_context_key,
                    "base_confidence": float(confidence),
                    "generic_penalty": penalty,
                    "context_match_reward": reward,
                    "transport_confidence": transport_confidence,
                    "match_mode": match_mode,
                    "matched_moderators_json": moderators,
                    "skg_version": skg_version,
                }
            )

        if transport_batch:
            con.executemany(
                """
                INSERT OR REPLACE INTO ac_skg_transport_scores(
                    transport_id, edge_id, target_context_id, base_confidence,
                    generic_penalty, context_match_reward, transport_confidence,
                    match_mode, matched_moderators_json, skg_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                transport_batch,
            )
        result["transport_scores_written"] = len(transport_batch)

        if transport_rows:
            with open(config.transport_scores_path, "w", encoding="utf-8") as fh:
                for row in transport_rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

        con.execute("CHECKPOINT")
    finally:
        con.close()

    artifacts: list[Any] = [config.db_path]
    if transport_rows:
        artifacts.append(config.transport_scores_path)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "transport_score.json",
        stage="transport_score",
        status="ok",
        metrics=result,
        artifacts=artifacts,
        started_at=started_at,
    )

    return result


__all__ = [
    "_apply_moderation_penalty",
    "_build_context_profiles",
    "run_transport_score",
]
