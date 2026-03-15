from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_doc_fragment_facts,
    emit_doc_meta_facts,
    persist_doc_fragment,
    persist_doc_meta,
    stable_world_provenance_v1,
    validate_doc_meta_ids,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.citations import AnchorKind, FragmentLocator
from polisyos.ir.world.doc import DocFragment
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import doc_fragment_id
from polisyos.lex.artifacts import load_doc_meta_artifact, load_json_artifact
from polisyos.lex.corpus.index import (
    ProvisionEntryV1,
    ProvisionIndexV1,
    persist_provision_index,
)
from polisyos.lex.errors import LexError, LexNotReadyError, LexStructureError, LexValidationError
from polisyos.lex.types import LexStructureOptions, LexStructureResult

_POINT_RE_LIST = [
    re.compile(r"^\s*(\d+)\)\s+\S"),
    re.compile(r"^\s*(\d+)\.\s+\S"),
]
_SUBPOINT_RE = re.compile(r"^\s*([a-zA-Zа-яА-Я])\)\s+\S")


@dataclass(frozen=True)
class _LineSpan:
    text: str
    line_no_nl: str
    start: int
    end: int


@dataclass(frozen=True)
class _Ruleset:
    jurisdiction: str
    article_re: re.Pattern[str]
    part_re: re.Pattern[str] | None


@dataclass(frozen=True)
class _ProvisionCandidate:
    anchor_path: str
    kind: Literal["article", "part", "point", "subpoint", "paragraph"]
    number: str | None
    parent_anchor_path: str | None
    offset_start: int
    offset_end: int
    props: dict[str, str | int | bool]


def _iter_lines_with_offsets(text: str) -> list[_LineSpan]:
    offset = 0
    rows: list[_LineSpan] = []
    for line in text.splitlines(keepends=True):
        start = offset
        end = offset + len(line)
        rows.append(_LineSpan(text=line, line_no_nl=line.rstrip("\n"), start=start, end=end))
        offset = end
    if not rows and text:
        rows.append(_LineSpan(text=text, line_no_nl=text, start=0, end=len(text)))
    return rows


def _resolve_jurisdiction(meta: DocMeta, options: LexStructureOptions) -> str:
    if options.jurisdiction:
        return options.jurisdiction.upper()
    if meta.jurisdiction:
        return meta.jurisdiction.upper()
    lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
    if isinstance(lex_props, dict):
        raw = lex_props.get("jurisdiction")
        if isinstance(raw, str) and raw:
            return raw.upper()
    raise LexValidationError("jurisdiction required")


def _ruleset_for(jurisdiction: str) -> _Ruleset:
    if jurisdiction == "UA":
        return _Ruleset(
            jurisdiction="UA",
            article_re=re.compile(r"^\s*Статт(?:я|і)\s+(\d+)\b"),
            part_re=re.compile(r"^\s*Частин(?:а|и)\s+(\d+)\b"),
        )
    if jurisdiction == "RU":
        return _Ruleset(
            jurisdiction="RU",
            article_re=re.compile(r"^\s*Стать(?:я|и)\s+(\d+)\b"),
            part_re=re.compile(r"^\s*Част(?:ь|и)\s+(\d+)\b"),
        )
    if jurisdiction == "EN":
        return _Ruleset(
            jurisdiction="EN",
            article_re=re.compile(r"^\s*Article\s+(\d+)\b"),
            part_re=re.compile(r"^\s*Part\s+(\d+)\b"),
        )
    raise LexValidationError(f"unsupported jurisdiction ruleset: {jurisdiction}")


def _preview(text: str, limit: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned[:limit]


def _match_number(regex: re.Pattern[str] | None, line: str) -> str | None:
    if regex is None:
        return None
    m = regex.match(line)
    if m is None:
        return None
    return m.group(1)


def _match_point(line: str) -> str | None:
    for regex in _POINT_RE_LIST:
        m = regex.match(line)
        if m is not None:
            return m.group(1)
    return None


def _find_headers(
    lines: list[_LineSpan],
    *,
    range_start: int,
    range_end: int,
    matcher,
) -> list[tuple[str, int]]:
    headers: list[tuple[str, int]] = []
    for line in lines:
        if line.start < range_start or line.start >= range_end:
            continue
        number = matcher(line.line_no_nl)
        if number is None:
            continue
        headers.append((number, line.start))
    headers.sort(key=lambda item: item[1])
    return headers


def _to_ranges(headers: list[tuple[str, int]], *, end_limit: int) -> list[tuple[str, int, int]]:
    ranges: list[tuple[str, int, int]] = []
    for idx, (number, start) in enumerate(headers):
        end = headers[idx + 1][1] if idx + 1 < len(headers) else end_limit
        if start >= end:
            continue
        ranges.append((number, start, end))
    return ranges


def _anchor_kind(kind: str) -> AnchorKind:
    mapping = {
        "article": AnchorKind.ARTICLE,
        "part": AnchorKind.SECTION,
        "point": AnchorKind.CLAUSE,
        "subpoint": AnchorKind.CLAUSE,
        "paragraph": AnchorKind.PARAGRAPH,
    }
    return mapping[kind]


def _build_paragraphs(
    lines: list[_LineSpan],
    *,
    container: _ProvisionCandidate,
) -> list[_ProvisionCandidate]:
    rows = [
        line
        for line in lines
        if line.start >= container.offset_start and line.start < container.offset_end
    ]
    if not rows:
        return []

    blocks: list[tuple[int, int]] = []
    block_start: int | None = None
    block_end: int | None = None
    for line in rows:
        if line.line_no_nl.strip() == "":
            if block_start is not None and block_end is not None:
                blocks.append((block_start, block_end))
                block_start = None
                block_end = None
            continue
        if block_start is None:
            block_start = line.start
        block_end = line.end

    if block_start is not None and block_end is not None:
        blocks.append((block_start, block_end))

    paragraphs: list[_ProvisionCandidate] = []
    for idx, (start, end) in enumerate(blocks, start=1):
        paragraphs.append(
            _ProvisionCandidate(
                anchor_path=f"{container.anchor_path}/para:{idx}",
                kind="paragraph",
                number=str(idx),
                parent_anchor_path=container.anchor_path,
                offset_start=start,
                offset_end=end,
                props={"lex_kind": "paragraph", "number": idx},
            )
        )
    return paragraphs


def _parse_anchor_components(anchor_path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in anchor_path.split("/"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key] = value
    return out


def _citation_label(kind: str, anchor_path: str, jurisdiction: str) -> str:
    parts = _parse_anchor_components(anchor_path)
    article = parts.get("art")
    part = parts.get("part")
    point = parts.get("pt")
    subpoint = parts.get("sub")

    if jurisdiction == "UA":
        if kind == "article":
            return f"Стаття {article}"
        if kind == "part":
            return f"Стаття {article}, Частина {part}"
        if kind == "point":
            base = f"Стаття {article}"
            if part is not None:
                base += f", Частина {part}"
            return f"{base}, пункт {point}"
        if kind == "subpoint":
            base = f"Стаття {article}"
            if part is not None:
                base += f", Частина {part}"
            if point is not None:
                base += f", пункт {point}"
            return f"{base}, підпункт {subpoint}"
    elif jurisdiction == "RU":
        if kind == "article":
            return f"Статья {article}"
        if kind == "part":
            return f"Статья {article}, Часть {part}"
        if kind == "point":
            base = f"Статья {article}"
            if part is not None:
                base += f", Часть {part}"
            return f"{base}, пункт {point}"
        if kind == "subpoint":
            base = f"Статья {article}"
            if part is not None:
                base += f", Часть {part}"
            if point is not None:
                base += f", пункт {point}"
            return f"{base}, подпункт {subpoint}"
    else:  # EN
        if kind == "article":
            return f"Article {article}"
        if kind == "part":
            return f"Article {article}, Part {part}"
        if kind == "point":
            base = f"Article {article}"
            if part is not None:
                base += f", Part {part}"
            return f"{base}, Clause {point}"
        if kind == "subpoint":
            base = f"Article {article}"
            if part is not None:
                base += f", Part {part}"
            if point is not None:
                base += f", Clause {point}"
            return f"{base}, Subpoint {subpoint}"

    return anchor_path


def _build_candidates(
    *,
    text: str,
    lines: list[_LineSpan],
    ruleset: _Ruleset,
    options: LexStructureOptions,
) -> tuple[list[_ProvisionCandidate], list[str]]:
    quality_issues: list[str] = []
    candidates: list[_ProvisionCandidate] = []

    article_headers = _find_headers(
        lines,
        range_start=0,
        range_end=len(text),
        matcher=lambda line: _match_number(ruleset.article_re, line),
    )
    article_ranges = _to_ranges(article_headers, end_limit=len(text))

    if not article_ranges:
        quality_issues.append("no_articles_detected")
        if options.require_articles:
            raise LexValidationError("no articles detected")
        return [], quality_issues

    counts: dict[str, int] = {}
    article_numbers: list[int] = []
    for number, _start, _end in article_ranges:
        counts[number] = counts.get(number, 0) + 1
        article_numbers.append(int(number))

    for number in sorted(counts):
        if counts[number] > 1:
            quality_issues.append(f"duplicate_article_number:{number}")

    if any(
        article_numbers[idx] <= article_numbers[idx - 1]
        for idx in range(1, len(article_numbers))
    ):
        quality_issues.append("non_monotonic_articles")

    for article_number, article_start, article_end in article_ranges:
        article_anchor = f"art:{article_number}"
        candidates.append(
            _ProvisionCandidate(
                anchor_path=article_anchor,
                kind="article",
                number=article_number,
                parent_anchor_path=None,
                offset_start=article_start,
                offset_end=article_end,
                props={"lex_kind": "article", "number": int(article_number)},
            )
        )

        if not options.enable_tier_b:
            continue

        part_headers = _find_headers(
            lines,
            range_start=article_start,
            range_end=article_end,
            matcher=lambda line: _match_number(ruleset.part_re, line),
        )
        part_ranges = _to_ranges(part_headers, end_limit=article_end)

        containers: list[tuple[str, int, int, str | None]]
        if part_ranges:
            containers = []
            for part_number, part_start, part_end in part_ranges:
                part_anchor = f"{article_anchor}/part:{part_number}"
                candidates.append(
                    _ProvisionCandidate(
                        anchor_path=part_anchor,
                        kind="part",
                        number=part_number,
                        parent_anchor_path=article_anchor,
                        offset_start=part_start,
                        offset_end=part_end,
                        props={
                            "lex_kind": "part",
                            "number": int(part_number),
                            "article": int(article_number),
                        },
                    )
                )
                containers.append((part_anchor, part_start, part_end, part_number))
        else:
            containers = [(article_anchor, article_start, article_end, None)]

        for container_anchor, container_start, container_end, part_number in containers:
            point_headers = _find_headers(
                lines,
                range_start=container_start,
                range_end=container_end,
                matcher=_match_point,
            )
            point_ranges = _to_ranges(point_headers, end_limit=container_end)

            for point_number, point_start, point_end in point_ranges:
                point_anchor = f"{container_anchor}/pt:{point_number}"
                point_props: dict[str, str | int | bool] = {
                    "lex_kind": "point",
                    "number": int(point_number),
                    "article": int(article_number),
                }
                if part_number is not None:
                    point_props["part"] = int(part_number)
                candidates.append(
                    _ProvisionCandidate(
                        anchor_path=point_anchor,
                        kind="point",
                        number=point_number,
                        parent_anchor_path=container_anchor,
                        offset_start=point_start,
                        offset_end=point_end,
                        props=point_props,
                    )
                )

                sub_headers = _find_headers(
                    lines,
                    range_start=point_start,
                    range_end=point_end,
                    matcher=lambda line: (
                        (_SUBPOINT_RE.match(line).group(1).lower())
                        if _SUBPOINT_RE.match(line)
                        else None
                    ),
                )
                sub_ranges = _to_ranges(sub_headers, end_limit=point_end)
                for sub_letter, sub_start, sub_end in sub_ranges:
                    candidates.append(
                        _ProvisionCandidate(
                            anchor_path=f"{point_anchor}/sub:{sub_letter}",
                            kind="subpoint",
                            number=sub_letter,
                            parent_anchor_path=point_anchor,
                            offset_start=sub_start,
                            offset_end=sub_end,
                            props={
                                "lex_kind": "subpoint",
                                "number": sub_letter,
                                "article": int(article_number),
                                **(
                                    {"part": int(part_number)}
                                    if part_number is not None
                                    else {}
                                ),
                            },
                        )
                    )

    if options.enable_paragraphs:
        non_paragraph = [c for c in candidates if c.kind != "paragraph"]
        has_child: set[str] = {
            c.parent_anchor_path for c in non_paragraph if c.parent_anchor_path is not None
        }
        leaves = [c for c in non_paragraph if c.anchor_path not in has_child]
        for leaf in leaves:
            candidates.extend(_build_paragraphs(lines, container=leaf))

    candidates = sorted(
        candidates,
        key=lambda item: (item.offset_start, item.offset_end, item.anchor_path),
    )
    return candidates, sorted(set(quality_issues))


def build_legal_structure(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: LexStructureOptions | None = None,
    segment_name: str | None = None,
) -> LexStructureResult:
    opts = options or LexStructureOptions()

    try:
        meta_before = load_doc_meta_artifact(
            cas,
            doc_meta_artifact_id,
            validate_ids=True,
        )
        if meta_before.normalized_ref is None:
            raise LexNotReadyError(
                "DocMeta.normalized_ref is required",
                doc_source_id=meta_before.doc_source_id,
                doc_version_id=meta_before.doc_version_id,
            )

        normalized_payload = load_json_artifact(cas, meta_before.normalized_ref)
        text = normalized_payload.get("text")
        if not isinstance(text, str):
            raise LexValidationError("normalized artifact missing text")

        lines = _iter_lines_with_offsets(text)
        jurisdiction = _resolve_jurisdiction(meta_before, opts)
        ruleset = _ruleset_for(jurisdiction)
        algorithm_id = opts.structure_algorithm_id or f"lex.structure_v1.{jurisdiction.lower()}"

        candidates, quality_issues = _build_candidates(
            text=text,
            lines=lines,
            ruleset=ruleset,
            options=opts,
        )

        stable_prov = stable_world_provenance_v1()
        facts = []
        fragment_ids: list[str] = []
        provision_entries: list[ProvisionEntryV1] = []

        for candidate in candidates:
            locator = FragmentLocator(
                anchor_kind=_anchor_kind(candidate.kind),
                anchor_path=candidate.anchor_path,
                offset_start=candidate.offset_start,
                offset_end=candidate.offset_end,
            )
            fragment_id = doc_fragment_id(
                doc_version_id=meta_before.doc_version_id,
                locator=locator,
                text_artifact_id=meta_before.normalized_ref,
            )
            fragment = DocFragment(
                fragment_id=fragment_id,
                doc_version_id=meta_before.doc_version_id,
                locator=locator,
                text_hash=meta_before.normalized_ref,
                quote_preview=_preview(text[candidate.offset_start : candidate.offset_end]),
                props=candidate.props,
            )
            fragment_ref = persist_doc_fragment(cas, fragment)
            fragment_artifact_id = str(fragment_ref.artifact_id)
            fragment_ids.append(fragment_id)

            facts.extend(
                emit_doc_fragment_facts(
                    fragment,
                    fragment_artifact_id=fragment_artifact_id,
                    provenance=stable_prov,
                )
            )

            provision_key = f"{meta_before.doc_source_id}|{candidate.anchor_path}"
            parent_provision_key = (
                f"{meta_before.doc_source_id}|{candidate.parent_anchor_path}"
                if candidate.parent_anchor_path is not None
                else None
            )
            provision_entries.append(
                ProvisionEntryV1(
                    provision_key=provision_key,
                    fragment_id=fragment_id,
                    citation_label=_citation_label(
                        candidate.kind,
                        candidate.anchor_path,
                        jurisdiction,
                    ),
                    parent_provision_key=parent_provision_key,
                    anchor_path=candidate.anchor_path,
                    offset_start=candidate.offset_start,
                    offset_end=candidate.offset_end,
                    kind=candidate.kind,
                    number=candidate.number,
                    props=candidate.props,
                )
            )

        stats = {"total": len(provision_entries)}
        for kind in ("article", "part", "point", "subpoint", "paragraph"):
            stats[kind] = sum(1 for entry in provision_entries if entry.kind == kind)

        provision_index = ProvisionIndexV1(
            doc_source_id=meta_before.doc_source_id,
            doc_version_id=meta_before.doc_version_id,
            doc_meta_artifact_id=doc_meta_artifact_id,
            structure_algorithm_id=algorithm_id,
            range_semantics="python_slice",
            provisions=provision_entries,
            stats=stats,
            quality_issues=quality_issues,
            notes=[],
        )
        provision_index_artifact_id = persist_provision_index(cas, provision_index)

        props = dict(meta_before.props)
        lex_props = props.get("lex") if isinstance(props.get("lex"), dict) else {}
        lex_props = dict(lex_props)
        lex_props["schema_version"] = "1.0"
        lex_props["structure_algorithm_id"] = algorithm_id
        lex_props["provision_index_ref"] = provision_index_artifact_id
        lex_props["structure_pipeline"] = "lex.corpus.structure_v1"
        if opts.write_structure_built_at:
            lex_props["structure_built_at"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        props["lex"] = lex_props

        meta_after = meta_before.model_copy(update={"props": props})
        validate_doc_meta_ids(meta_after)
        meta_ref = persist_doc_meta(cas, meta_after)
        meta_artifact_id = str(meta_ref.artifact_id)

        facts.extend(
            emit_doc_meta_facts(
                meta_after,
                meta_artifact_id=meta_artifact_id,
                provenance=stable_prov,
            )
        )

        inputs = [
            WorldObjectRef(world_id=meta_before.doc_version_id),
            WorldObjectRef(artifact_id=meta_before.normalized_ref),
            WorldObjectRef(artifact_id=doc_meta_artifact_id),
        ]
        outputs = [
            WorldObjectRef(artifact_id=provision_index_artifact_id),
            WorldObjectRef(artifact_id=meta_artifact_id),
        ] + [WorldObjectRef(world_id=fragment_id) for fragment_id in fragment_ids]
        event = build_deterministic_world_event(
            event_kind=EventKind.STRUCTURE_DOC,
            agent_id=opts.lex_agent_id,
            agent_type=ProvAgentType.SYSTEM,
            agent_label="Lex Corpus",
            activity_id=opts.lex_activity_id,
            activity_type=ProvActivityType.STRUCTURE_DOC,
            activity_label="Build legal structure",
            activity_parameters={
                "pipeline": "lex.corpus.structure_v1",
                "structure_algorithm_id": algorithm_id,
                "tier_b": opts.enable_tier_b,
                "tier_c": opts.enable_paragraphs,
            },
            inputs=inputs,
            outputs=outputs,
            props={
                "pipeline": "lex.corpus.structure_v1",
                "structure_algorithm_id": algorithm_id,
            },
        )
        event_id = event.event_id
        event_artifact_id = persist_world_event_with_facts(cas=cas, event=event, facts=facts)

        segment_base = segment_name or "lex_structure"
        segment_suffix = event_id.split("sha256_", 1)[-1][:12]
        manifest = write_world_fact_segment(
            facts,
            fact_log_root=fact_log_root,
            segment_name=f"{segment_base}_{segment_suffix}",
        )
        append_world_segment_index(manifest, fact_log_root=fact_log_root)

        return LexStructureResult(
            doc_source_id=meta_after.doc_source_id,
            doc_version_id=meta_after.doc_version_id,
            doc_meta_artifact_id=meta_artifact_id,
            fragment_ids=fragment_ids,
            provision_index_artifact_id=provision_index_artifact_id,
            world_event_id=event_id,
            world_event_artifact_id=event_artifact_id,
            world_segment_manifest=manifest,
            quality_issues=quality_issues,
        )
    except LexError:
        raise
    except Exception as exc:
        raise LexStructureError(
            f"failed to build legal structure: {exc}",
        ) from exc


__all__ = ["build_legal_structure"]
