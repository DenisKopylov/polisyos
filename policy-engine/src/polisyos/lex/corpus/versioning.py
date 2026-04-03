"""Public corpus versioning module API."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_world_node_facts,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.predicates import WORLD_ARTIFACT_ID, WORLD_PROPS_REF, rel
from polisyos.lex.artifacts import load_doc_meta_artifact
from polisyos.lex.common import latest_object_by_subject, parse_iso_date
from polisyos.lex.corpus.index import (
    DocSourcePropsV1,
    VersionEntryV1,
    VersionIndexV1,
    load_doc_source_props,
    load_version_index,
    persist_doc_source_props,
    persist_version_index,
)
from polisyos.lex.errors import (
    LexError,
    LexNotReadyError,
    LexValidationError,
    LexVersioningError,
)
from polisyos.lex.factlog import load_world_facts
from polisyos.lex.types import (
    ActiveVersionResult,
    ActiveVersionStrategy,
    LexVersionIndexOptions,
    LexVersionIndexResult,
)

_FACT_COLUMNS = ["fact_id", "subject_id", "predicate_id", "object_value", "target_id", "tx_time"]


def _parse_iso_date(
    value: str | None,
    *,
    field: str,
    issues: list[str],
    doc_version_id: str,
) -> date | None:
    parsed = parse_iso_date(value)
    if value is not None and value.strip() and parsed is None:
        issues.append(f"invalid_iso:{field}:{doc_version_id}")
    return parsed


def _load_world_facts(fact_log_root: Path) -> pd.DataFrame:
    return load_world_facts(
        fact_log_root,
        columns=_FACT_COLUMNS,
        read_error_cls=LexVersioningError,
    )


def _entry_sort_key(
    entry: VersionEntryV1,
    parsed_effective_from: dict[str, date | None],
    parsed_published_at: dict[str, date | None],
) -> tuple[str, str, str]:
    temporal = parsed_effective_from.get(entry.doc_version_id)
    if temporal is None:
        temporal = parsed_published_at.get(entry.doc_version_id)
    temporal_key = temporal.isoformat() if temporal is not None else "9999-12-31"
    return (temporal_key, entry.doc_version_id, entry.doc_meta_artifact_id)


def _has_overlaps(
    entries: list[VersionEntryV1],
    parsed_effective_from: dict[str, date | None],
    parsed_effective_to: dict[str, date | None],
) -> bool:
    ranged: list[tuple[date, date]] = []
    for entry in entries:
        start = parsed_effective_from.get(entry.doc_version_id)
        if start is None:
            continue
        end = parsed_effective_to.get(entry.doc_version_id) or date.max
        ranged.append((start, end))

    ranged.sort(key=lambda item: item[0])
    for idx in range(len(ranged)):
        start_i, end_i = ranged[idx]
        for jdx in range(idx + 1, len(ranged)):
            start_j, end_j = ranged[jdx]
            if start_j > end_i:
                break
            if start_i <= end_j and start_j <= end_i:
                return True
    return False


def build_version_index(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_source_id: str,
    options: LexVersionIndexOptions | None = None,
    segment_name: str | None = None,
) -> LexVersionIndexResult:
    """Build version index."""
    opts = options or LexVersionIndexOptions()

    try:
        facts = _load_world_facts(fact_log_root)

        has_version_rows = facts[
            (facts["predicate_id"] == rel(EdgeKind.DOC_HAS_VERSION))
            & (facts["subject_id"] == doc_source_id)
            & (facts["target_id"].notna())
        ]
        doc_version_ids = sorted({str(value) for value in has_version_rows["target_id"].tolist()})
        if not doc_version_ids:
            raise LexVersioningError(
                "no doc versions found for doc_source_id",
                doc_source_id=doc_source_id,
            )

        latest_meta = latest_object_by_subject(
            facts,
            subject_ids=set(doc_version_ids),
            predicate_id=WORLD_ARTIFACT_ID,
        )

        quality_issues: list[str] = []
        entries: list[VersionEntryV1] = []
        parsed_effective_from: dict[str, date | None] = {}
        parsed_effective_to: dict[str, date | None] = {}
        parsed_published_at: dict[str, date | None] = {}

        for doc_version_id in doc_version_ids:
            meta_artifact_id = latest_meta.get(doc_version_id)
            if meta_artifact_id is None:
                quality_issues.append(f"missing_meta_artifact:{doc_version_id}")
                continue

            meta = load_doc_meta_artifact(cas, meta_artifact_id)
            lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
            if not isinstance(lex_props, dict):
                lex_props = {}
            temporal_props = lex_props.get("temporal") if isinstance(lex_props.get("temporal"), dict) else {}

            published_at = temporal_props.get("published_at") or lex_props.get("published_at")
            effective_from = temporal_props.get("effective_from") or lex_props.get("effective_from")
            effective_to = temporal_props.get("effective_to") or lex_props.get("effective_to")
            temporal_resolution_status = str(temporal_props.get("temporal_resolution_status") or "").strip().lower()

            if published_at is not None and not isinstance(published_at, str):
                quality_issues.append(f"invalid_iso:published_at:{doc_version_id}")
                published_at = None
            if effective_from is not None and not isinstance(effective_from, str):
                quality_issues.append(f"invalid_iso:effective_from:{doc_version_id}")
                effective_from = None
            if effective_to is not None and not isinstance(effective_to, str):
                quality_issues.append(f"invalid_iso:effective_to:{doc_version_id}")
                effective_to = None

            entry_issues: list[str] = []
            parsed_pub = _parse_iso_date(
                published_at,
                field="published_at",
                issues=quality_issues,
                doc_version_id=doc_version_id,
            )
            parsed_from = _parse_iso_date(
                effective_from,
                field="effective_from",
                issues=quality_issues,
                doc_version_id=doc_version_id,
            )
            parsed_to = _parse_iso_date(
                effective_to,
                field="effective_to",
                issues=quality_issues,
                doc_version_id=doc_version_id,
            )

            parsed_published_at[doc_version_id] = parsed_pub
            parsed_effective_from[doc_version_id] = parsed_from
            parsed_effective_to[doc_version_id] = parsed_to

            if effective_from is None:
                issue = f"missing_effective_from:{doc_version_id}"
                quality_issues.append(issue)
                entry_issues.append(issue)
            if temporal_resolution_status and temporal_resolution_status != "resolved":
                issue = f"unresolved_temporal:{doc_version_id}"
                quality_issues.append(issue)
                entry_issues.append(issue)
            if published_at is None:
                issue = f"missing_published_at:{doc_version_id}"
                quality_issues.append(issue)
                entry_issues.append(issue)

            if parsed_from is not None and temporal_resolution_status in {"", "resolved"}:
                confidence = "1.0"
            else:
                confidence = "0.3"

            entries.append(
                VersionEntryV1(
                    doc_version_id=doc_version_id,
                    doc_meta_artifact_id=meta_artifact_id,
                    published_at=published_at,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    confidence=confidence,
                    quality_issues=sorted(set(entry_issues)),
                )
            )

        entries = sorted(
            entries,
            key=lambda entry: _entry_sort_key(entry, parsed_effective_from, parsed_published_at),
        )

        if _has_overlaps(entries, parsed_effective_from, parsed_effective_to):
            quality_issues.append("overlapping_effective_ranges")

        version_index = VersionIndexV1(
            doc_source_id=doc_source_id,
            selection_policy_id=opts.selection_policy_id,
            versions=entries,
            quality_issues=sorted(set(quality_issues)),
            notes=[],
        )
        version_index_artifact_id = persist_version_index(cas, version_index)

        doc_source_props = DocSourcePropsV1(
            doc_source_id=doc_source_id,
            version_index_ref=version_index_artifact_id,
            updated_at_iso=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            notes=[],
        )
        doc_source_props_artifact_id = persist_doc_source_props(cas, doc_source_props)

        stable_prov = stable_world_provenance_v1()
        facts_out = []
        if opts.write_doc_source_props_pointer:
            facts_out.extend(
                emit_world_node_facts(
                    node_id=doc_source_id,
                    kind=NodeKind.DOC_SOURCE,
                    label=None,
                    artifact_id=None,
                    props_ref=doc_source_props_artifact_id,
                    provenance=stable_prov,
                )
            )

        input_refs = [WorldObjectRef(world_id=doc_source_id)]
        input_refs.extend(
            WorldObjectRef(world_id=doc_version_id)
            for doc_version_id in doc_version_ids
        )
        input_refs.extend(
            WorldObjectRef(artifact_id=entry.doc_meta_artifact_id) for entry in entries
        )
        output_refs = [
            WorldObjectRef(artifact_id=version_index_artifact_id),
            WorldObjectRef(artifact_id=doc_source_props_artifact_id),
        ]
        event = build_deterministic_world_event(
            event_kind=EventKind.VALIDATE,
            agent_id=opts.lex_agent_id,
            agent_type=ProvAgentType.SYSTEM,
            agent_label="Lex Corpus",
            activity_id=opts.lex_activity_id,
            activity_type=ProvActivityType.VALIDATE,
            activity_label="Build legal version index",
            activity_parameters={
                "pipeline": "lex.corpus.versioning_v1",
                "selection_policy_id": opts.selection_policy_id,
                "versions_count": len(entries),
            },
            inputs=input_refs,
            outputs=output_refs,
            props={
                "pipeline": "lex.corpus.versioning_v1",
                "selection_policy_id": opts.selection_policy_id,
            },
        )
        event_id = event.event_id
        event_artifact_id = persist_world_event_with_facts(
            cas=cas,
            event=event,
            facts=facts_out,
        )

        segment_base = segment_name or "lex_version_index"
        segment_suffix = event_id.split("sha256_", 1)[-1][:12]
        manifest = write_world_fact_segment(
            facts_out,
            fact_log_root=fact_log_root,
            segment_name=f"{segment_base}_{segment_suffix}",
        )
        append_world_segment_index(manifest, fact_log_root=fact_log_root)

        return LexVersionIndexResult(
            doc_source_id=doc_source_id,
            version_index_artifact_id=version_index_artifact_id,
            doc_source_props_artifact_id=doc_source_props_artifact_id,
            world_event_id=event_id,
            world_event_artifact_id=event_artifact_id,
            world_segment_manifest=manifest,
            versions_count=len(entries),
            quality_issues=version_index.quality_issues,
        )
    except LexError:
        raise
    except Exception as exc:
        raise LexVersioningError(
            f"failed to build version index: {exc}",
            doc_source_id=doc_source_id,
        ) from exc


def _latest_props_ref(
    facts: pd.DataFrame,
    *,
    doc_source_id: str,
) -> str | None:
    subset = facts[
        (facts["subject_id"] == doc_source_id)
        & (facts["predicate_id"] == WORLD_PROPS_REF)
        & (facts["object_value"].notna())
    ].copy()
    if subset.empty:
        return None
    subset["tx_time"] = subset["tx_time"].fillna("").astype(str)
    subset["fact_id"] = subset["fact_id"].fillna("").astype(str)
    subset = subset.sort_values(by=["tx_time", "fact_id"], ascending=[False, False])
    return str(subset.iloc[0]["object_value"])


def _candidate_rank(
    candidate: dict[str, str | None],
    *,
    parsed_effective_from: dict[str, date | None],
    parsed_published_at: dict[str, date | None],
) -> tuple[date, date, str]:
    doc_version_id = str(candidate["doc_version_id"])
    return (
        parsed_effective_from.get(doc_version_id) or date.min,
        parsed_published_at.get(doc_version_id) or date.min,
        doc_version_id,
    )


def resolve_active_version(
    *,
    cas: FileSystemCAS,
    doc_source_id: str,
    as_of_iso: str,
    strategy: ActiveVersionStrategy | None = None,
) -> ActiveVersionResult:
    """Resolve active version."""
    strat = strategy or ActiveVersionStrategy()

    try:
        if strat.mode != "by_version_index_v1":
            raise LexValidationError(f"unsupported resolve mode: {strat.mode}")
        if strat.as_of_semantics != "date_inclusive":
            raise LexValidationError(
                f"unsupported as_of_semantics: {strat.as_of_semantics}"
            )
        if (
            strat.tie_breaker
            != "effective_from_then_published_then_doc_version_id"
        ):
            raise LexValidationError(
                f"unsupported tie_breaker: {strat.tie_breaker}"
            )

        explanation: list[str] = []
        as_of_date = _parse_iso_date(
            as_of_iso,
            field="as_of_iso",
            issues=[],
            doc_version_id="resolve",
        )
        if as_of_date is None:
            raise LexValidationError(f"invalid as_of_iso: {as_of_iso}")
        as_of_norm = as_of_date.isoformat()
        explanation.append(f"as_of_normalized={as_of_norm}")

        if strat.version_index_artifact_id is not None:
            version_index_artifact_id = strat.version_index_artifact_id
            explanation.append("using explicit strategy.version_index_artifact_id")
        else:
            fact_log_root = strat.fact_log_root or Path(cas.root).parent
            explanation.append(f"using fact_log_root={fact_log_root}")
            facts = _load_world_facts(fact_log_root)
            props_ref = _latest_props_ref(facts, doc_source_id=doc_source_id)
            if props_ref is None:
                raise LexNotReadyError(
                    (
                        "version index pointer not found; run build_version_index "
                        "or pass version_index_artifact_id"
                    ),
                    doc_source_id=doc_source_id,
                )
            doc_source_props = load_doc_source_props(cas, props_ref)
            version_index_artifact_id = doc_source_props.version_index_ref
            explanation.append(f"resolved props_ref={props_ref}")

        index = load_version_index(cas, version_index_artifact_id)
        if index.doc_source_id != doc_source_id:
            raise LexValidationError(
                "version index doc_source_id mismatch",
                doc_source_id=doc_source_id,
                details={"index_doc_source_id": index.doc_source_id},
            )

        candidates = [
            {
                "doc_version_id": entry.doc_version_id,
                "doc_meta_artifact_id": entry.doc_meta_artifact_id,
                "published_at": entry.published_at,
                "effective_from": entry.effective_from,
                "effective_to": entry.effective_to,
            }
            for entry in index.versions
        ]
        explanation.append(f"versions_total={len(candidates)}")

        parsed_effective_from: dict[str, date | None] = {}
        parsed_effective_to: dict[str, date | None] = {}
        parsed_published_at: dict[str, date | None] = {}

        for entry in index.versions:
            issues: list[str] = []
            parsed_effective_from[entry.doc_version_id] = _parse_iso_date(
                entry.effective_from,
                field="effective_from",
                issues=issues,
                doc_version_id=entry.doc_version_id,
            )
            parsed_effective_to[entry.doc_version_id] = _parse_iso_date(
                entry.effective_to,
                field="effective_to",
                issues=issues,
                doc_version_id=entry.doc_version_id,
            )
            parsed_published_at[entry.doc_version_id] = _parse_iso_date(
                entry.published_at,
                field="published_at",
                issues=issues,
                doc_version_id=entry.doc_version_id,
            )

        effective_candidates = [
            candidate
            for candidate in candidates
            if parsed_effective_from.get(str(candidate["doc_version_id"])) is not None
            and parsed_effective_from[str(candidate["doc_version_id"])] <= as_of_date
            and (
                parsed_effective_to.get(str(candidate["doc_version_id"])) is None
                or as_of_date <= parsed_effective_to[str(candidate["doc_version_id"])]
            )
        ]
        explanation.append(f"effective_candidates={len(effective_candidates)}")

        selected: dict[str, str | None] | None = None
        if effective_candidates:
            selected = max(
                effective_candidates,
                key=lambda candidate: _candidate_rank(
                    candidate,
                    parsed_effective_from=parsed_effective_from,
                    parsed_published_at=parsed_published_at,
                ),
            )
            explanation.append(
                "selected via effective range with tie-break: "
                "effective_from, published_at, doc_version_id"
            )
        else:
            explanation.append("no_resolved_temporal_candidate")

        return ActiveVersionResult(
            doc_source_id=doc_source_id,
            as_of_iso=as_of_norm,
            selected_doc_version_id=(
                None if selected is None else str(selected["doc_version_id"])
            ),
            selected_doc_meta_artifact_id=(
                None if selected is None else str(selected["doc_meta_artifact_id"])
            ),
            selection_policy_id=index.selection_policy_id,
            used_version_index_artifact_id=version_index_artifact_id,
            explanation=explanation,
            candidates=candidates if strat.include_candidates else [],
        )
    except LexError:
        raise
    except Exception as exc:
        raise LexVersioningError(
            f"failed to resolve active version: {exc}",
            doc_source_id=doc_source_id,
        ) from exc


__all__ = ["build_version_index", "resolve_active_version"]
