"""Independence maps for Policy Design Case evidence portfolios."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.runtime.quality.evidence_line import (
    EvidenceLineError,
    evidence_line_record_id,
    validate_evidence_line_records,
)

if TYPE_CHECKING:
    from datetime import datetime

INDEPENDENCE_MAP_SCHEMA_VERSION = "policyos.runtime.policy_design_case.independence_map.v1"
INDEPENDENCE_MAP_CONTRACT_ID = "policy_design_case.independence_map.v1"
INDEPENDENCE_COLLAPSE_DIMENSIONS = (
    "claim_ids",
    "evidence_strand",
    "method_cluster_id",
    "source_lineage_cluster_id",
    "corpus_ancestry_cluster_id",
    "author_institution_pool_id",
    "preprocessing_cluster_id",
    "assumption_cluster_id",
    "identification_strategy_id",
    "shared_failure_mode_cluster_id",
)
_PASSING_EQUIVALENCE_VERDICTS = frozenset(
    {"pass", "pass_strict", "pass_relaxed", "equivalent", "accepted"}
)


@dataclass(frozen=True)
class EvidenceIndependenceError(ValueError):
    """Fail-closed independence-map contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_evidence_independence_map(
    evidence_lines: Iterable[Mapping[str, Any]],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    method_consensus_reports: Iterable[object] = (),
    method_equivalence_reports: Iterable[object] = (),
    map_id: str,
    producer_execution_started_at: str | datetime | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Build an independence map by collapsing correlated evidence lines."""

    try:
        lines = validate_evidence_line_records(
            evidence_lines,
            portfolio_designs=tuple(portfolio_designs),
            producer_execution_started_at=producer_execution_started_at,
        )
    except EvidenceLineError as exc:
        raise EvidenceIndependenceError(exc.code, str(exc), exc.field) from exc

    map_id = _required_text(
        map_id,
        "map_id",
        "policy_design_independence_map_id_missing",
    )
    method_index = _MethodCollapseIndex.from_foundry_reports(
        lines,
        method_consensus_reports=method_consensus_reports,
        method_equivalence_reports=method_equivalence_reports,
    )
    clusters: dict[str, dict[str, Any]] = {}
    for line in lines:
        dimensions = _collapse_dimensions(line, method_index)
        signature = _signature(dimensions)
        cluster = clusters.setdefault(
            signature,
            {
                "cluster_id": f"independent-cluster-{len(clusters) + 1}",
                "line_ids": [],
                "raw_line_count": 0,
                "collapse_dimensions": dimensions,
                "representative_line_id": evidence_line_record_id(line),
            },
        )
        cluster["line_ids"].append(evidence_line_record_id(line))
        cluster["raw_line_count"] = int(cluster["raw_line_count"]) + 1

    collapse_clusters = sorted(
        (
            {
                **cluster,
                "line_ids": sorted(cluster["line_ids"]),
            }
            for cluster in clusters.values()
        ),
        key=lambda item: str(item["representative_line_id"]),
    )
    for index, cluster in enumerate(collapse_clusters, start=1):
        cluster["cluster_id"] = f"independent-cluster-{index}"

    payload: dict[str, Any] = {
        "schema_version": INDEPENDENCE_MAP_SCHEMA_VERSION,
        "contract_id": INDEPENDENCE_MAP_CONTRACT_ID,
        "map_id": map_id,
        "portfolio_ids": _sorted_unique(line["portfolio_id"] for line in lines),
        "claim_ids": _sorted_unique(
            claim_id for line in lines for claim_id in _text_values(line.get("claim_ids"))
        ),
        "raw_evidence_line_count": len(lines),
        "effective_independent_evidence_count": len(collapse_clusters),
        "collapse_dimensions_used": list(INDEPENDENCE_COLLAPSE_DIMENSIONS),
        "collapse_clusters": collapse_clusters,
    }
    if evidence_ref is not None:
        payload["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        payload["runtime_event_ref"] = str(runtime_event_ref)
    return payload


def validate_evidence_independence_map_record(
    record: Mapping[str, Any],
    *,
    evidence_lines: Iterable[Mapping[str, Any]] = (),
    portfolio_designs: Iterable[Mapping[str, Any]] = (),
    producer_execution_started_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Validate and normalize one independence-map record."""

    if not isinstance(record, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_map_invalid",
            "Evidence independence map must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_independence_schema_version_missing",
    )
    if schema_version != INDEPENDENCE_MAP_SCHEMA_VERSION:
        raise EvidenceIndependenceError(
            "policy_design_independence_schema_version_invalid",
            "Evidence independence map must use the runtime-quality independence schema.",
            "schema_version",
        )
    normalized["schema_version"] = INDEPENDENCE_MAP_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or INDEPENDENCE_MAP_CONTRACT_ID
    normalized["map_id"] = _required_text(
        record.get("map_id") or record.get("independence_map_id") or record.get("record_id"),
        "map_id",
        "policy_design_independence_map_id_missing",
    )

    raw_count = _required_nonnegative_int(
        _first_present(
            record,
            "raw_evidence_line_count",
            "raw_evidence_count",
            "raw_line_count",
        ),
        "raw_evidence_line_count",
        "policy_design_independence_raw_count_missing",
    )
    normalized["raw_evidence_line_count"] = raw_count
    effective_count = _required_nonnegative_int(
        _first_present(
            record,
            "effective_independent_evidence_count",
            "effective_independent_count",
            "effective_evidence_line_count",
        ),
        "effective_independent_evidence_count",
        "policy_design_independence_effective_count_missing",
    )
    normalized["effective_independent_evidence_count"] = effective_count
    if effective_count > raw_count:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_count_exceeds_raw",
            "Effective independent evidence count cannot exceed the raw evidence-line count.",
            "effective_independent_evidence_count",
        )

    clusters = record.get("collapse_clusters")
    if not isinstance(clusters, Sequence) or isinstance(clusters, str) or not clusters:
        if raw_count > 0:
            raise EvidenceIndependenceError(
                "policy_design_independence_clusters_missing",
                "Evidence independence map must include collapse clusters.",
                "collapse_clusters",
            )
        normalized["collapse_clusters"] = []
    else:
        normalized["collapse_clusters"] = [
            _validate_cluster(cluster, index=index) for index, cluster in enumerate(clusters)
        ]
        if len(normalized["collapse_clusters"]) != effective_count:
            raise EvidenceIndependenceError(
                "policy_design_independence_cluster_count_mismatch",
                "Effective independent evidence count must equal collapse cluster count.",
                "effective_independent_evidence_count",
            )
        raw_cluster_count = sum(
            int(cluster["raw_line_count"]) for cluster in normalized["collapse_clusters"]
        )
        if raw_cluster_count != raw_count:
            raise EvidenceIndependenceError(
                "policy_design_independence_raw_cluster_count_mismatch",
                "Collapse cluster raw-line counts must add up to raw evidence-line count.",
                "raw_evidence_line_count",
            )

    line_rows = tuple(evidence_lines)
    if line_rows:
        try:
            validated_lines = validate_evidence_line_records(
                line_rows,
                portfolio_designs=tuple(portfolio_designs),
                producer_execution_started_at=producer_execution_started_at,
            )
        except EvidenceLineError as exc:
            raise EvidenceIndependenceError(exc.code, str(exc), exc.field) from exc
        if len(validated_lines) != raw_count:
            raise EvidenceIndependenceError(
                "policy_design_independence_raw_count_mismatch",
                "Independence-map raw evidence-line count must match supplied evidence lines.",
                "raw_evidence_line_count",
            )
    return normalized


class _MethodCollapseIndex:
    def __init__(self, method_ids: Iterable[str]) -> None:
        self._parent: dict[str, str] = {}
        for method_id in method_ids:
            self._parent[str(method_id)] = str(method_id)

    @classmethod
    def from_foundry_reports(
        cls,
        lines: Iterable[Mapping[str, Any]],
        *,
        method_consensus_reports: Iterable[object],
        method_equivalence_reports: Iterable[object],
    ) -> _MethodCollapseIndex:
        index = cls(_clean_text(line.get("method_id")) for line in lines)
        for report in method_consensus_reports:
            group = _method_ids_from_consensus_report(report)
            index._union_group(group)
        for report in method_equivalence_reports:
            group = _method_ids_from_equivalence_report(report)
            index._union_group(group)
        return index

    def canonical(self, method_id: str) -> str:
        method_id = str(method_id)
        if method_id not in self._parent:
            self._parent[method_id] = method_id
        return self._find(method_id)

    def _union_group(self, method_ids: Sequence[str]) -> None:
        clean = [method_id for method_id in method_ids if method_id]
        if len(clean) < 2:
            return
        canonical = clean[0]
        for method_id in clean:
            self._parent.setdefault(method_id, method_id)
        for method_id in clean[1:]:
            self._union(canonical, method_id)

    def _union(self, preferred: str, other: str) -> None:
        preferred_root = self._find(preferred)
        other_root = self._find(other)
        if preferred_root != other_root:
            self._parent[other_root] = preferred_root

    def _find(self, method_id: str) -> str:
        self._parent.setdefault(method_id, method_id)
        parent = self._parent[method_id]
        if parent != method_id:
            parent = self._find(parent)
            self._parent[method_id] = parent
        return parent


def _method_ids_from_consensus_report(report: object) -> tuple[str, ...]:
    payload = _mapping(report)
    status = _clean_text(payload.get("status"))
    if status and status not in {"pass", "warn"}:
        return ()
    for key in ("consensus_set", "method_consensus_set", "equivalent_method_ids"):
        values = _text_values(payload.get(key))
        if len(values) >= 2:
            return values
    nested = _mapping(payload.get("cross_method_consensus") or payload.get("consensus"))
    for key in ("consensus_set", "method_consensus_set"):
        values = _text_values(nested.get(key))
        if len(values) >= 2:
            return values
    return ()


def _method_ids_from_equivalence_report(report: object) -> tuple[str, ...]:
    payload = _mapping(report)
    verdict = _clean_text(payload.get("verdict") or payload.get("status"))
    if verdict and verdict not in _PASSING_EQUIVALENCE_VERDICTS:
        return ()
    group = _text_values(
        payload.get("method_ids")
        or payload.get("equivalent_method_ids")
        or payload.get("methods")
    )
    if len(group) >= 2:
        return group
    source = _clean_text(
        payload.get("source_method_id")
        or payload.get("source_method")
        or payload.get("method_fqn")
        or payload.get("method_id")
    )
    target = _clean_text(
        payload.get("target_method_id")
        or payload.get("target_method")
        or payload.get("equivalent_method_id")
    )
    return tuple(item for item in (source, target) if item)


def _collapse_dimensions(
    line: Mapping[str, Any],
    method_index: _MethodCollapseIndex,
) -> dict[str, Any]:
    method_id = _required_text(
        line.get("method_id"),
        "method_id",
        "policy_design_independence_method_id_missing",
    )
    return {
        "claim_ids": _text_values(line.get("claim_ids") or line.get("claim_id")),
        "evidence_strand": _required_text(
            line.get("evidence_strand"),
            "evidence_strand",
            "policy_design_independence_strand_missing",
        ),
        "method_cluster_id": method_index.canonical(method_id),
        "source_lineage_cluster_id": _lineage_cluster_id(line),
        "corpus_ancestry_cluster_id": _required_surface_key(
            _values_from_line(
                line,
                "corpus_ancestry",
                "corpus_ancestry_refs",
                ("source_lineage", "corpus_id"),
                ("source_lineage", "corpus_ref"),
                ("source_lineage", "corpus_ancestry"),
                ("source_lineage", "upstream_corpus_refs"),
            ),
            "corpus_ancestry",
            "policy_design_independence_corpus_ancestry_missing",
        ),
        "author_institution_pool_id": _required_surface_key(
            _values_from_line(
                line,
                "author_pool",
                "author_ids",
                "institution_pool",
                "institution_ids",
                ("source_lineage", "author_pool"),
                ("source_lineage", "institution_pool"),
            ),
            "author_institution_pool",
            "policy_design_independence_author_institution_pool_missing",
        ),
        "preprocessing_cluster_id": _required_surface_key(
            _values_from_line(
                line,
                "preprocessing",
                "preprocessing_ref",
                "preprocessing_pipeline_id",
                "preprocessing_pipeline_ref",
                ("source_lineage", "preprocessing"),
                ("source_lineage", "preprocessing_ref"),
            ),
            "preprocessing",
            "policy_design_independence_preprocessing_missing",
        ),
        "assumption_cluster_id": _required_surface_key(
            _values_from_line(
                line,
                "method_assumptions",
                "assumptions",
                "assumption_refs",
            ),
            "method_assumptions",
            "policy_design_independence_assumptions_missing",
        ),
        "identification_strategy_id": _required_surface_key(
            _values_from_line(
                line,
                "identification_strategy_id",
                "identification_strategy",
                "identification_ref",
                ("method", "identification_strategy"),
                ("method", "identification_strategy_id"),
            ),
            "identification_strategy",
            "policy_design_independence_identification_strategy_missing",
        ),
        "shared_failure_mode_cluster_id": _required_surface_key(
            _values_from_line(
                line,
                "shared_failure_modes",
                "failure_mode_refs",
                "known_failure_modes",
                ("source_lineage", "shared_failure_modes"),
                ("method", "shared_failure_modes"),
            ),
            "shared_failure_modes",
            "policy_design_independence_shared_failure_modes_missing",
        ),
    }


def _lineage_cluster_id(line: Mapping[str, Any]) -> str:
    return _required_surface_key(
        _values_from_line(
            line,
            "source_lineage_refs",
            ("source_lineage", "source_id"),
            ("source_lineage", "source_ref"),
            ("source_lineage", "lineage_refs"),
            ("source_lineage", "source_family"),
            ("source_lineage", "source_family_id"),
        ),
        "source_lineage",
        "policy_design_independence_source_lineage_missing",
    )


def _validate_cluster(cluster: object, *, index: int) -> dict[str, Any]:
    if not isinstance(cluster, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_cluster_invalid",
            "Independence-map collapse clusters must be mappings.",
            f"collapse_clusters[{index}]",
        )
    normalized = dict(cluster)
    normalized["cluster_id"] = _required_text(
        cluster.get("cluster_id"),
        f"collapse_clusters[{index}].cluster_id",
        "policy_design_independence_cluster_id_missing",
    )
    normalized["raw_line_count"] = _required_nonnegative_int(
        _first_present(cluster, "raw_line_count", "raw_evidence_line_count"),
        f"collapse_clusters[{index}].raw_line_count",
        "policy_design_independence_cluster_raw_count_missing",
    )
    line_ids = _text_values(cluster.get("line_ids") or cluster.get("evidence_line_ids"))
    if not line_ids:
        raise EvidenceIndependenceError(
            "policy_design_independence_cluster_line_ids_missing",
            "Independence-map collapse clusters must name their evidence lines.",
            f"collapse_clusters[{index}].line_ids",
        )
    normalized["line_ids"] = list(line_ids)
    if not isinstance(cluster.get("collapse_dimensions"), Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_cluster_dimensions_missing",
            "Independence-map collapse clusters must include collapse dimensions.",
            f"collapse_clusters[{index}].collapse_dimensions",
        )
    return normalized


def _values_from_line(line: Mapping[str, Any], *paths: str | tuple[str, str]) -> tuple[str, ...]:
    values: list[str] = []
    for path in paths:
        if isinstance(path, str):
            values.extend(_text_values(line.get(path)))
            continue
        current: object = line
        for key in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(key)
        values.extend(_text_values(current))
    return tuple(dict.fromkeys(values))


def _required_surface_key(values: Iterable[str], field: str, code: str) -> str:
    clean = _sorted_unique(values)
    if clean:
        return "|".join(clean)
    raise EvidenceIndependenceError(
        code,
        f"Evidence independence map requires {field} collapse surface.",
        field,
    )


def _mapping(value: object) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    elif hasattr(value, "as_dict"):
        value = value.as_dict()
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _signature(dimensions: Mapping[str, Any]) -> str:
    return json.dumps(
        {key: _jsonable(dimensions.get(key)) for key in INDEPENDENCE_COLLAPSE_DIMENSIONS},
        sort_keys=True,
        separators=(",", ":"),
    )


def _jsonable(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_jsonable(item) for item in value]
    return value


def _required_nonnegative_int(value: object, field: str, code: str) -> int:
    if isinstance(value, bool) or value is None:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map must include {field}.",
            field,
        )
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map must include integer {field}.",
            field,
        ) from exc
    if count < 0:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map {field} cannot be negative.",
            field,
        )
    return count


def _first_present(record: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _required_text(value: object, field: str, code: str) -> str:
    text = _clean_text(value)
    if not text:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map must include {field}.",
            field,
        )
    return text


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _text(value: object) -> str | None:
    text = _clean_text(value)
    return text or None


def _text_values(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, str):
        text = _text(value)
        if text is not None:
            values.append(text)
    elif isinstance(value, Mapping):
        for key in sorted(value):
            item = value[key]
            if isinstance(item, Mapping | list | tuple | set):
                values.extend(_text_values(item))
            else:
                text = _text(item) or _text(key)
                if text is not None:
                    values.append(text)
    elif isinstance(value, list | tuple | set):
        for item in value:
            values.extend(_text_values(item))
    return tuple(dict.fromkeys(values))


def _sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})
