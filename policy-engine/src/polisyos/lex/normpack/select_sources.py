from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.world.abi import EdgeKind
from polisyos.ir.world.predicates import WORLD_ARTIFACT_ID, WORLD_KIND, rel
from polisyos.lex.artifacts import load_doc_meta_artifact
from polisyos.lex.common import latest_object_by_subject, parse_iso_date
from polisyos.lex.corpus.versioning import resolve_active_version
from polisyos.lex.errors import LexNotReadyError, LexValidationError
from polisyos.lex.factlog import load_world_facts
from polisyos.lex.types import ActiveVersionStrategy, NormPackBuildRequest, SelectedDocVersion

logger = get_logger(__name__)

_FACT_COLUMNS = [
    "fact_id",
    "subject_id",
    "predicate_id",
    "object_value",
    "target_id",
    "tx_time",
]


def _load_world_facts(fact_log_root: Path) -> pd.DataFrame:
    return load_world_facts(fact_log_root, columns=_FACT_COLUMNS)


def _is_lex_corpus_doc(cas: FileSystemCAS, artifact_id: str) -> bool:
    try:
        meta = load_doc_meta_artifact(cas, artifact_id, payload_label="doc meta artifact")
    except Exception:
        logger.debug("Failed to load doc meta artifact %s", artifact_id)
        return False
    lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
    if not isinstance(lex_props, dict):
        return False
    return str(lex_props.get("corpus", "")).casefold() == "lex.corpus"


def normalize_as_of(as_of: str) -> str:
    parsed = parse_iso_date(as_of)
    if parsed is None:
        raise LexValidationError(f"invalid as_of ISO value: {as_of}")
    return parsed.isoformat()


def select_doc_sources(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: NormPackBuildRequest,
) -> list[str]:
    if request.doc_source_ids is not None:
        selected = sorted(set(request.doc_source_ids))
    else:
        facts = _load_world_facts(fact_log_root)
        kinds = facts[
            (facts["predicate_id"] == WORLD_KIND)
            & (facts["object_value"] == "doc.source")
            & (facts["subject_id"].notna())
        ]
        candidate_doc_sources = sorted({str(value) for value in kinds["subject_id"].tolist()})
        if not candidate_doc_sources:
            selected = []
        else:
            version_rows = facts[
                (facts["predicate_id"] == rel(EdgeKind.DOC_HAS_VERSION))
                & (facts["subject_id"].isin(candidate_doc_sources))
                & (facts["target_id"].notna())
            ]
            versions_by_source: dict[str, list[str]] = {}
            for _, row in version_rows.iterrows():
                source_id = str(row["subject_id"])
                versions_by_source.setdefault(source_id, []).append(str(row["target_id"]))

            all_versions = {
                version_id
                for values in versions_by_source.values()
                for version_id in values
            }
            latest_meta_by_version = latest_object_by_subject(
                facts,
                subject_ids=all_versions,
                predicate_id=WORLD_ARTIFACT_ID,
            )

            selected = []
            for doc_source_id in candidate_doc_sources:
                version_ids = sorted(set(versions_by_source.get(doc_source_id, [])))
                if not version_ids:
                    continue
                if any(
                    _is_lex_corpus_doc(cas, latest_meta_by_version[doc_version_id])
                    for doc_version_id in version_ids
                    if doc_version_id in latest_meta_by_version
                ):
                    selected.append(doc_source_id)

    max_docs = request.budgets.max_docs
    if max_docs is not None:
        return selected[:max_docs]
    return selected


def _fallback_select_active_version(
    *,
    cas: FileSystemCAS,
    facts: pd.DataFrame,
    doc_source_id: str,
    as_of_norm: str,
) -> tuple[dict[str, str] | None, list[str]]:
    explanations: list[str] = ["selected_via=fallback"]
    as_of_date = date.fromisoformat(as_of_norm)

    version_rows = facts[
        (facts["predicate_id"] == rel(EdgeKind.DOC_HAS_VERSION))
        & (facts["subject_id"] == doc_source_id)
        & (facts["target_id"].notna())
    ]
    doc_version_ids = sorted({str(value) for value in version_rows["target_id"].tolist()})
    explanations.append(f"fallback_versions_total={len(doc_version_ids)}")
    if not doc_version_ids:
        return None, explanations

    latest_meta_by_version = latest_object_by_subject(
        facts,
        subject_ids=set(doc_version_ids),
        predicate_id=WORLD_ARTIFACT_ID,
    )

    candidates: list[dict[str, Any]] = []
    for doc_version_id in doc_version_ids:
        artifact_id = latest_meta_by_version.get(doc_version_id)
        if artifact_id is None:
            continue
        try:
            meta = load_doc_meta_artifact(cas, artifact_id, payload_label="doc meta artifact")
        except Exception:
            logger.debug("Failed to load doc meta artifact %s in fallback version selection", artifact_id)
            continue
        lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
        if not isinstance(lex_props, dict):
            lex_props = {}
        effective_from_raw = lex_props.get("effective_from")
        effective_to_raw = lex_props.get("effective_to")
        published_at_raw = lex_props.get("published_at")

        effective_from = parse_iso_date(
            effective_from_raw if isinstance(effective_from_raw, str) else None
        )
        effective_to = parse_iso_date(
            effective_to_raw if isinstance(effective_to_raw, str) else None
        )
        published_at = parse_iso_date(
            published_at_raw if isinstance(published_at_raw, str) else None
        )

        candidates.append(
            {
                "doc_version_id": doc_version_id,
                "doc_meta_artifact_id": artifact_id,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "published_at": published_at,
            }
        )

    def _date_ord(value: date | None) -> int:
        return value.toordinal() if value is not None else date.min.toordinal()

    effective_candidates = [
        row
        for row in candidates
        if row["effective_from"] is not None
        and row["effective_from"] <= as_of_date
        and (row["effective_to"] is None or as_of_date <= row["effective_to"])
    ]
    explanations.append(f"fallback_effective_candidates={len(effective_candidates)}")
    if effective_candidates:
        selected = sorted(
            effective_candidates,
            key=lambda row: (
                -_date_ord(row["effective_from"]),
                -_date_ord(row["published_at"]),
                str(row["doc_version_id"]),
            ),
        )[0]
        explanations.append(
            "selected via effective range with tie-break: effective_from desc, "
            "published_at desc, doc_version_id asc"
        )
        return {
            "doc_version_id": str(selected["doc_version_id"]),
            "doc_meta_artifact_id": str(selected["doc_meta_artifact_id"]),
        }, explanations

    published_candidates = [
        row
        for row in candidates
        if row["published_at"] is not None and row["published_at"] <= as_of_date
    ]
    explanations.append(f"fallback_published_candidates={len(published_candidates)}")
    if published_candidates:
        selected = sorted(
            published_candidates,
            key=lambda row: (
                -_date_ord(row["published_at"]),
                str(row["doc_version_id"]),
            ),
        )[0]
        explanations.append("selected via published_at fallback")
        return {
            "doc_version_id": str(selected["doc_version_id"]),
            "doc_meta_artifact_id": str(selected["doc_meta_artifact_id"]),
        }, explanations

    if candidates:
        selected = max(
            candidates,
            key=lambda row: (
                str(row["doc_meta_artifact_id"]),
                str(row["doc_version_id"]),
            ),
        )
        explanations.append("selected via deterministic id fallback")
        return {
            "doc_version_id": str(selected["doc_version_id"]),
            "doc_meta_artifact_id": str(selected["doc_meta_artifact_id"]),
        }, explanations

    explanations.append("no fallback candidates")
    return None, explanations


def _matches_jurisdiction(
    *,
    doc_source_id: str,
    meta: DocMeta,
    jurisdiction_norm: str,
    warnings: list[str],
) -> bool:
    values: list[str] = []
    if meta.jurisdiction:
        values.append(meta.jurisdiction)

    lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
    if isinstance(lex_props, dict):
        lex_jurisdiction = lex_props.get("jurisdiction")
        if isinstance(lex_jurisdiction, str) and lex_jurisdiction.strip():
            values.append(lex_jurisdiction)

    if not values:
        warnings.append(f"warning:doc_jurisdiction_missing:{doc_source_id}")
        return True

    return any(value.strip().casefold() == jurisdiction_norm for value in values)


def select_active_doc_versions(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: NormPackBuildRequest,
    jurisdiction_norm: str,
    as_of_norm: str,
    doc_source_ids: list[str],
) -> tuple[list[SelectedDocVersion], list[str]]:
    selected: list[SelectedDocVersion] = []
    warnings: list[str] = []
    facts = _load_world_facts(fact_log_root)

    for doc_source_id in sorted(set(doc_source_ids)):
        chosen_doc_version_id: str | None = None
        chosen_doc_meta_artifact_id: str | None = None
        used_version_index_artifact_id: str | None = None
        explanation: list[str] = []

        try:
            resolved = resolve_active_version(
                cas=cas,
                doc_source_id=doc_source_id,
                as_of_iso=as_of_norm,
                strategy=ActiveVersionStrategy(fact_log_root=fact_log_root),
            )
            explanation.extend(resolved.explanation)
            if (
                resolved.selected_doc_version_id is not None
                and resolved.selected_doc_meta_artifact_id is not None
            ):
                chosen_doc_version_id = resolved.selected_doc_version_id
                chosen_doc_meta_artifact_id = resolved.selected_doc_meta_artifact_id
                used_version_index_artifact_id = resolved.used_version_index_artifact_id
                if resolved.selection_policy_id != request.selection_policy_id:
                    warnings.append(
                        "warning:selection_policy_mismatch:"
                        f"{doc_source_id}:{resolved.selection_policy_id}"
                    )
        except LexNotReadyError:
            explanation.append("primary_path_not_ready")
        except LexValidationError as exc:
            explanation.append(f"primary_path_error:{exc}")

        if chosen_doc_version_id is None or chosen_doc_meta_artifact_id is None:
            fallback_selected, fallback_explanation = _fallback_select_active_version(
                cas=cas,
                facts=facts,
                doc_source_id=doc_source_id,
                as_of_norm=as_of_norm,
            )
            explanation.extend(fallback_explanation)
            if fallback_selected is None:
                warnings.append(f"warning:no_active_version:{doc_source_id}")
                continue
            chosen_doc_version_id = fallback_selected["doc_version_id"]
            chosen_doc_meta_artifact_id = fallback_selected["doc_meta_artifact_id"]
            used_version_index_artifact_id = None

        try:
            meta = load_doc_meta_artifact(
                cas,
                chosen_doc_meta_artifact_id,
                payload_label="doc meta artifact",
            )
        except Exception:
            logger.debug("Failed to load doc meta for source %s", doc_source_id)
            warnings.append(f"warning:doc_meta_not_loadable:{doc_source_id}")
            continue

        if not _matches_jurisdiction(
            doc_source_id=doc_source_id,
            meta=meta,
            jurisdiction_norm=jurisdiction_norm,
            warnings=warnings,
        ):
            continue

        selected.append(
            SelectedDocVersion(
                doc_source_id=doc_source_id,
                doc_version_id=chosen_doc_version_id,
                doc_meta_artifact_id=chosen_doc_meta_artifact_id,
                selection_policy_id=request.selection_policy_id,
                used_version_index_artifact_id=used_version_index_artifact_id,
                explanation=explanation,
            )
        )

    selected.sort(key=lambda row: row.doc_source_id)
    return selected, sorted(set(warnings))


__all__ = [
    "normalize_as_of",
    "select_active_doc_versions",
    "select_doc_sources",
]
