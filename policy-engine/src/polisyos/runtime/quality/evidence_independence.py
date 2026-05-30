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
GRADED_INDEPENDENCE_FEATURE_FLAG = "policy_design_case.graded_independence_weights"
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
_VALID_GOVERNED_CONFIG_STATUSES = frozenset({"provisional", "validated", "deprecated", "withdrawn"})
_VALID_SCARCITY_STATUSES = frozenset(
    {"not_rare_domain", "scarcity_structural", "scarcity_remediable"}
)
_VALID_BALANCE_STATUSES = frozenset(
    {"support_dominant", "mixed", "counter_dominant", "insufficient"}
)
_VALID_INDEPENDENCE_STATUSES = frozenset(
    {"sufficient", "weak", "singular", "inflated_raw_count", "insufficient"}
)
_COUNTEREVIDENCE_TOKENS = frozenset(
    {
        "conflict",
        "counter",
        "counterevidence",
        "counter_evidence",
        "contradict",
        "contradictory",
        "disconfirm",
        "disconfirming",
        "negative_control",
        "opposes",
        "rebuttal",
        "refute",
        "refuting",
    }
)
_CONTEXT_TOKENS = frozenset({"context", "context_only", "neutral", "background"})


@dataclass(frozen=True)
class EvidenceIndependenceError(ValueError):
    """Fail-closed independence-map contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class CapabilityIndependenceFactor:
    """W8.F effective-independence factor for one candidate capability."""

    value: float
    collapse_ratio: float
    candidate_lineage_refs: tuple[str, ...]
    shared_lineage_refs: tuple[str, ...]
    source: str


def effective_independence_factor_for_capability(
    capability: object,
    *,
    selected_capabilities: Sequence[object] = (),
    independence_map: Mapping[str, Any] | None = None,
) -> CapabilityIndependenceFactor:
    """Return the effective-independence factor for a candidate capability.

    The helper reads a precomputed W8.F map when available, otherwise it applies
    the same P14 principle to capability lineage refs: already-selected claim
    evidence that shares source/calibration lineage collapses support mass
    instead of adding independent authority.
    """

    payload = _mapping(capability)
    capability_id = _text(payload.get("capability_id")) or _text(payload.get("id"))
    precomputed = _precomputed_capability_independence(
        capability_id=capability_id,
        independence_map=independence_map,
    )
    if precomputed is not None:
        return precomputed

    candidate_refs = _capability_lineage_refs(payload)
    selected_refs = tuple(
        dict.fromkeys(
            ref
            for selected in selected_capabilities
            for ref in _capability_lineage_refs(_mapping(selected))
        )
    )
    shared_refs = tuple(sorted(set(candidate_refs) & set(selected_refs)))
    if not candidate_refs or not selected_refs:
        collapse_ratio = 0.0
    else:
        collapse_ratio = len(shared_refs) / len(candidate_refs)
    value = max(0.0, min(1.0, 1.0 - collapse_ratio))
    return CapabilityIndependenceFactor(
        value=value,
        collapse_ratio=collapse_ratio,
        candidate_lineage_refs=candidate_refs,
        shared_lineage_refs=shared_refs,
        source="w8f.lineage_overlap_fallback",
    )


def build_evidence_independence_map(
    evidence_lines: Iterable[Mapping[str, Any]],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    method_consensus_reports: Iterable[object] = (),
    method_equivalence_reports: Iterable[object] = (),
    feature_flags: Mapping[str, bool] | None = None,
    graded_independence_config: Mapping[str, Any] | None = None,
    rare_domain_context: Mapping[str, Any] | None = None,
    map_id: str,
    producer_execution_started_at: str | datetime | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Build an independence map by collapsing correlated evidence lines."""

    portfolio_design_rows = tuple(portfolio_designs)
    try:
        lines = validate_evidence_line_records(
            evidence_lines,
            portfolio_designs=portfolio_design_rows,
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
        cluster["effective_line_count"] = 1
        cluster["collapse_reasons"] = _collapse_reasons_for_cluster(cluster)

    effective_mass_report = _build_effective_mass_report(
        lines=lines,
        collapse_clusters=collapse_clusters,
    )
    rare_domain_scarcity = _build_rare_domain_scarcity_report(
        rare_domain_context,
        effective_support_mass=float(effective_mass_report["effective_support_mass"]),
    )
    if rare_domain_scarcity["status"] != "not_rare_domain":
        deficits = list(effective_mass_report["limiting_deficits"])
        if str(rare_domain_scarcity["status"]) not in deficits:
            deficits.append(str(rare_domain_scarcity["status"]))
        effective_mass_report["limiting_deficits"] = deficits

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
        "effective_mass_report": effective_mass_report,
        "graded_independence": _build_graded_independence_report(
            feature_flags=feature_flags,
            governed_config=graded_independence_config,
            raw_count=len(lines),
            hard_effective_count=len(collapse_clusters),
            lines=lines,
            portfolio_designs=portfolio_design_rows,
            map_id=map_id,
            producer_execution_started_at=producer_execution_started_at,
            rare_domain_context=rare_domain_context,
        ),
        "rare_domain_scarcity": rare_domain_scarcity,
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

    normalized["effective_mass_report"] = _validate_effective_mass_report(
        record.get("effective_mass_report"),
        raw_count=raw_count,
        effective_count=effective_count,
        collapse_clusters=tuple(normalized["collapse_clusters"]),
    )
    normalized["graded_independence"] = _validate_graded_independence_report(
        record.get("graded_independence"),
        raw_count=raw_count,
    )
    normalized["rare_domain_scarcity"] = _validate_rare_domain_scarcity_report(
        record.get("rare_domain_scarcity"),
        effective_support_mass=float(normalized["effective_mass_report"]["effective_support_mass"]),
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


def _precomputed_capability_independence(
    *,
    capability_id: str | None,
    independence_map: Mapping[str, Any] | None,
) -> CapabilityIndependenceFactor | None:
    if not capability_id or not isinstance(independence_map, Mapping):
        return None
    for key in (
        "capability_independence_factors",
        "effective_independence_factors",
        "capability_factors",
    ):
        rows = independence_map.get(key)
        if not isinstance(rows, Sequence) or isinstance(rows, str):
            continue
        for raw_row in rows:
            row = _mapping(raw_row)
            row_capability_id = (
                _text(row.get("capability_id"))
                or _text(row.get("capability_ref"))
                or _text(row.get("selected_capability_ref"))
            )
            if row_capability_id != capability_id:
                continue
            value = _required_nonnegative_float(
                _first_present(
                    row,
                    "effective_independence_factor",
                    "factor",
                    "value",
                ),
                "effective_independence_factor",
                "policy_design_independence_capability_factor_missing",
            )
            collapse_ratio = float(
                row.get("collapse_ratio")
                if row.get("collapse_ratio") is not None
                else max(0.0, 1.0 - value)
            )
            return CapabilityIndependenceFactor(
                value=max(0.0, min(1.0, value)),
                collapse_ratio=max(0.0, min(1.0, collapse_ratio)),
                candidate_lineage_refs=_text_values(row.get("candidate_lineage_refs")),
                shared_lineage_refs=_text_values(row.get("shared_lineage_refs")),
                source="w8f.effective_independence_map",
            )
    return None


def _capability_lineage_refs(capability: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(_text_values(capability.get("lineage_refs")))
    refs.extend(_text_values(_mapping(capability.get("metadata")).get("lineage_refs")))
    if refs:
        return tuple(dict.fromkeys(refs))
    for asset in _mapping_rows(capability.get("source_assets")):
        refs.extend(
            _text_values(
                (
                    asset.get("ref"),
                    asset.get("path"),
                    asset.get("table"),
                    asset.get("source_snapshot_id"),
                )
            )
        )
    return tuple(dict.fromkeys(refs))


def _mapping_rows(value: object) -> tuple[dict[str, Any], ...]:
    if isinstance(value, Mapping):
        return (_mapping(value),)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_mapping(item) for item in value if _mapping(item))
    return ()


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
        payload.get("method_ids") or payload.get("equivalent_method_ids") or payload.get("methods")
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
    normalized["collapse_dimensions"] = dict(cluster["collapse_dimensions"])
    normalized["effective_line_count"] = _required_nonnegative_int(
        _first_present(cluster, "effective_line_count", "effective_count"),
        f"collapse_clusters[{index}].effective_line_count",
        "policy_design_independence_cluster_effective_count_missing",
    )
    if normalized["effective_line_count"] > normalized["raw_line_count"]:
        raise EvidenceIndependenceError(
            "policy_design_independence_cluster_effective_count_exceeds_raw",
            "Cluster effective line count cannot exceed raw line count.",
            f"collapse_clusters[{index}].effective_line_count",
        )
    normalized["collapse_reasons"] = _validate_collapse_reasons(
        cluster.get("collapse_reasons") or cluster.get("collapse_reason_records"),
        index=index,
        raw_line_count=int(normalized["raw_line_count"]),
        line_ids=line_ids,
    )
    return normalized


def _collapse_reasons_for_cluster(cluster: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_line_count = int(cluster.get("raw_line_count") or 0)
    if raw_line_count <= 1:
        return []
    line_ids = _text_values(cluster.get("line_ids"))
    dimensions = _mapping(cluster.get("collapse_dimensions"))
    cluster_id = str(cluster.get("cluster_id") or "independent-cluster")
    reasons: list[dict[str, Any]] = []
    for dimension in INDEPENDENCE_COLLAPSE_DIMENSIONS:
        if dimension in {"claim_ids", "evidence_strand"}:
            continue
        value = dimensions.get(dimension)
        if not _surface_present(value):
            continue
        reasons.append(
            {
                "reason_id": f"{cluster_id}:{dimension}",
                "dimension": dimension,
                "reason_code": f"shared_{dimension}",
                "value": _reason_value(value),
                "line_ids": list(line_ids),
                "collapse_policy": "strict_hard_collapse",
                "explanation": f"Evidence lines share {dimension}.",
            }
        )
    return reasons


def _validate_collapse_reasons(
    value: object,
    *,
    index: int,
    raw_line_count: int,
    line_ids: Sequence[str],
) -> list[dict[str, Any]]:
    if raw_line_count <= 1 and value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str) or not value:
        if raw_line_count > 1:
            raise EvidenceIndependenceError(
                "policy_design_independence_collapse_reasons_missing",
                "Collapsed evidence clusters must explain their collapse reasons.",
                f"collapse_clusters[{index}].collapse_reasons",
            )
        return []
    rows: list[dict[str, Any]] = []
    for reason_index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceIndependenceError(
                "policy_design_independence_collapse_reason_invalid",
                "Collapse reason records must be mappings.",
                f"collapse_clusters[{index}].collapse_reasons[{reason_index}]",
            )
        row = dict(item)
        row["reason_id"] = _required_text(
            row.get("reason_id") or row.get("id"),
            "reason_id",
            "policy_design_independence_collapse_reason_id_missing",
        )
        row["dimension"] = _required_text(
            row.get("dimension") or row.get("collapse_dimension"),
            "dimension",
            "policy_design_independence_collapse_reason_dimension_missing",
        )
        row["reason_code"] = _required_text(
            row.get("reason_code") or row.get("code"),
            "reason_code",
            "policy_design_independence_collapse_reason_code_missing",
        )
        reason_line_ids = _text_values(row.get("line_ids") or row.get("evidence_line_ids"))
        if not reason_line_ids:
            reason_line_ids = tuple(line_ids)
        row["line_ids"] = list(reason_line_ids)
        rows.append(row)
    return rows


def _build_effective_mass_report(
    *,
    lines: Sequence[Mapping[str, Any]],
    collapse_clusters: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    line_by_id = {evidence_line_record_id(line): line for line in lines}
    support_line_ids: list[str] = []
    counter_line_ids: list[str] = []
    context_line_ids: list[str] = []
    effective_support_mass = 0.0
    effective_counter_mass = 0.0
    effective_context_mass = 0.0
    reason_counts: dict[str, int] = {}
    largest_hard_collapse_cluster = 0

    for cluster in collapse_clusters:
        cluster_line_ids = _text_values(cluster.get("line_ids"))
        polarities = {
            _line_polarity(line_by_id[line_id])
            for line_id in cluster_line_ids
            if line_id in line_by_id
        }
        if "support" in polarities:
            effective_support_mass += 1.0
        if "counterevidence" in polarities:
            effective_counter_mass += 1.0
        if "context" in polarities:
            effective_context_mass += 1.0

        for line_id in cluster_line_ids:
            line = line_by_id.get(line_id)
            if line is None:
                continue
            polarity = _line_polarity(line)
            if polarity == "support":
                support_line_ids.append(line_id)
            elif polarity == "counterevidence":
                counter_line_ids.append(line_id)
            else:
                context_line_ids.append(line_id)

        raw_line_count = int(cluster.get("raw_line_count") or 0)
        if raw_line_count > 1:
            largest_hard_collapse_cluster = max(largest_hard_collapse_cluster, raw_line_count)
            for reason in _validate_collapse_reasons(
                cluster.get("collapse_reasons"),
                index=0,
                raw_line_count=raw_line_count,
                line_ids=cluster_line_ids,
            ):
                reason_code = str(reason["reason_code"])
                reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1

    raw_count = len(lines)
    effective_count = len(collapse_clusters)
    deficits: list[str] = []
    if raw_count > effective_count:
        deficits.append("dependent_evidence_collapsed")
    if effective_count == 0:
        deficits.append("no_independent_evidence")

    return {
        "raw_evidence_line_count": raw_count,
        "effective_independent_evidence_count": effective_count,
        "raw_support_line_count": len(support_line_ids),
        "raw_counterevidence_line_count": len(counter_line_ids),
        "raw_context_line_count": len(context_line_ids),
        "effective_support_mass": effective_support_mass,
        "effective_counterevidence_mass": effective_counter_mass,
        "effective_context_mass": effective_context_mass,
        "balance_status": _balance_status(
            support_mass=effective_support_mass,
            counter_mass=effective_counter_mass,
        ),
        "independence_status": _independence_status(
            raw_count=raw_count,
            effective_count=effective_count,
        ),
        "largest_hard_collapse_cluster": largest_hard_collapse_cluster,
        "dominant_collapse_reasons": _dominant_reasons(reason_counts),
        "support_line_ids": sorted(support_line_ids),
        "counterevidence_line_ids": sorted(counter_line_ids),
        "context_line_ids": sorted(context_line_ids),
        "limiting_deficits": deficits,
        "raw_count_display_policy": {
            "raw_count_authority": "diagnostic_only",
            "must_display_with": [
                "effective_independent_evidence_count",
                "effective_support_mass",
                "collapse_reasons",
            ],
        },
    }


def _validate_effective_mass_report(
    value: object,
    *,
    raw_count: int,
    effective_count: int,
    collapse_clusters: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_report_missing",
            "Evidence independence map must include an effective mass report.",
            "effective_mass_report",
        )
    row = dict(value)
    row["raw_evidence_line_count"] = _required_nonnegative_int(
        _first_present(row, "raw_evidence_line_count", "raw_line_count"),
        "effective_mass_report.raw_evidence_line_count",
        "policy_design_independence_effective_mass_raw_count_missing",
    )
    if row["raw_evidence_line_count"] != raw_count:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_raw_count_mismatch",
            "Effective mass raw evidence-line count must match independence-map raw count.",
            "effective_mass_report.raw_evidence_line_count",
        )
    row["effective_independent_evidence_count"] = _required_nonnegative_int(
        _first_present(
            row,
            "effective_independent_evidence_count",
            "effective_independent_count",
        ),
        "effective_mass_report.effective_independent_evidence_count",
        "policy_design_independence_effective_mass_effective_count_missing",
    )
    if row["effective_independent_evidence_count"] != effective_count:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_effective_count_mismatch",
            (
                "Effective mass independent evidence count must match "
                "independence-map effective count."
            ),
            "effective_mass_report.effective_independent_evidence_count",
        )
    for key in (
        "raw_support_line_count",
        "raw_counterevidence_line_count",
        "raw_context_line_count",
    ):
        row[key] = _required_nonnegative_int(
            row.get(key),
            f"effective_mass_report.{key}",
            f"policy_design_independence_effective_mass_{key}_missing",
        )
    for key in (
        "effective_support_mass",
        "effective_counterevidence_mass",
        "effective_context_mass",
    ):
        row[key] = _required_nonnegative_float(
            row.get(key),
            f"effective_mass_report.{key}",
            f"policy_design_independence_effective_mass_{key}_missing",
        )
    if row["effective_support_mass"] > row["raw_support_line_count"]:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_support_exceeds_raw",
            "Effective support mass cannot exceed raw support line count.",
            "effective_mass_report.effective_support_mass",
        )
    if row["effective_counterevidence_mass"] > row["raw_counterevidence_line_count"]:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_counter_exceeds_raw",
            "Effective counterevidence mass cannot exceed raw counterevidence line count.",
            "effective_mass_report.effective_counterevidence_mass",
        )
    balance_status = _required_text(
        row.get("balance_status"),
        "balance_status",
        "policy_design_independence_effective_mass_balance_status_missing",
    )
    if balance_status not in _VALID_BALANCE_STATUSES:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_balance_status_invalid",
            "Evidence mass balance status is not recognized.",
            "effective_mass_report.balance_status",
        )
    row["balance_status"] = balance_status
    independence_status = _required_text(
        row.get("independence_status"),
        "independence_status",
        "policy_design_independence_effective_mass_independence_status_missing",
    )
    if independence_status not in _VALID_INDEPENDENCE_STATUSES:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_independence_status_invalid",
            "Evidence mass independence status is not recognized.",
            "effective_mass_report.independence_status",
        )
    row["independence_status"] = independence_status
    largest = _required_nonnegative_int(
        row.get("largest_hard_collapse_cluster"),
        "effective_mass_report.largest_hard_collapse_cluster",
        "policy_design_independence_effective_mass_largest_cluster_missing",
    )
    row["largest_hard_collapse_cluster"] = largest
    dominant_reasons = _validate_dominant_reasons(row.get("dominant_collapse_reasons"))
    if raw_count > effective_count and not dominant_reasons:
        raise EvidenceIndependenceError(
            "policy_design_independence_effective_mass_collapse_reasons_missing",
            (
                "Raw counts that collapse to lower effective support must report "
                "dominant collapse reasons."
            ),
            "effective_mass_report.dominant_collapse_reasons",
        )
    row["dominant_collapse_reasons"] = dominant_reasons
    row["support_line_ids"] = list(_text_values(row.get("support_line_ids")))
    row["counterevidence_line_ids"] = list(_text_values(row.get("counterevidence_line_ids")))
    row["context_line_ids"] = list(_text_values(row.get("context_line_ids")))
    row["limiting_deficits"] = list(_text_values(row.get("limiting_deficits")))
    display_policy = row.get("raw_count_display_policy")
    if not isinstance(display_policy, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_raw_count_display_policy_missing",
            (
                "Raw evidence-line count must declare that it is diagnostic-only and "
                "displayed beside effective support and collapse reasons."
            ),
            "effective_mass_report.raw_count_display_policy",
        )
    row["raw_count_display_policy"] = dict(display_policy)
    _validate_mass_clusters_have_reasons(collapse_clusters)
    return row


def _build_graded_independence_report(
    *,
    feature_flags: Mapping[str, bool] | None,
    governed_config: Mapping[str, Any] | None,
    raw_count: int,
    hard_effective_count: int,
    lines: Sequence[Mapping[str, Any]],
    portfolio_designs: Sequence[Mapping[str, Any]],
    map_id: str,
    producer_execution_started_at: str | datetime | None,
    rare_domain_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    flags = dict(feature_flags or {})
    enabled = bool(flags.get(GRADED_INDEPENDENCE_FEATURE_FLAG, False))
    report: dict[str, Any] = {
        "enabled": enabled,
        "feature_flag": GRADED_INDEPENDENCE_FEATURE_FLAG,
        "feature_flag_enabled": enabled,
        "authority_posture": "advisory_only" if enabled else "strict_hard_collapse_only",
        "hard_effective_independent_evidence_count": hard_effective_count,
        "raw_evidence_line_count": raw_count,
        "may_not_use_for": ["closeout_authority", "publication_strength_inflation"],
    }
    if governed_config is not None:
        report["governed_config"] = dict(governed_config)
    else:
        report["governed_config"] = {"status": "not_configured"}
    if enabled:
        report["graded_effective_independent_evidence_count"] = float(hard_effective_count)
        from polisyos.evidence import (
            PAIRWISE_MODEL_FORMULA,
            build_effective_independence_graph,
        )

        graph = build_effective_independence_graph(
            lines,
            portfolio_designs=portfolio_designs,
            graph_id=f"effective-independence-graph:{map_id}",
            producer_execution_started_at=producer_execution_started_at,
            feature_flags=feature_flags,
            graded_independence_config=governed_config,
            rare_domain_context=rare_domain_context,
            independence_map_ref=map_id,
        )
        report["effective_independence_graph_ref"] = graph["graph_id"]
        report["effective_independence_graph"] = graph
        report["pairwise_model"] = PAIRWISE_MODEL_FORMULA
        report["pairwise_dependency_count"] = len(graph["graded_calculus"]["pairwise_dependencies"])
        report["graded_effective_support_mass"] = graph["mass_report"][
            "graded_effective_support_mass"
        ]
        report["graded_effective_counterevidence_mass"] = graph["mass_report"][
            "graded_effective_counterevidence_mass"
        ]
        report["graded_effective_independent_evidence_count"] = (
            graph["mass_report"]["graded_effective_support_mass"]
            + graph["mass_report"]["graded_effective_counterevidence_mass"]
            + graph["mass_report"]["graded_effective_context_mass"]
        )
    return report


def _validate_graded_independence_report(
    value: object,
    *,
    raw_count: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_graded_report_missing",
            "Evidence independence map must include graded-independence posture.",
            "graded_independence",
        )
    row = dict(value)
    row["enabled"] = bool(row.get("enabled", False))
    row["feature_flag"] = _required_text(
        row.get("feature_flag"),
        "feature_flag",
        "policy_design_independence_graded_feature_flag_missing",
    )
    row["feature_flag_enabled"] = bool(row.get("feature_flag_enabled", False))
    row["authority_posture"] = _required_text(
        row.get("authority_posture"),
        "authority_posture",
        "policy_design_independence_graded_authority_posture_missing",
    )
    if row["enabled"] and not row["feature_flag_enabled"]:
        raise EvidenceIndependenceError(
            "policy_design_independence_graded_feature_flag_disabled",
            "Graded independence weights cannot run unless their feature flag is enabled.",
            "graded_independence.feature_flag_enabled",
        )
    if row["enabled"]:
        config = row.get("governed_config")
        if not isinstance(config, Mapping):
            raise EvidenceIndependenceError(
                "policy_design_independence_graded_config_missing",
                "Enabled graded independence requires governed config.",
                "graded_independence.governed_config",
            )
        normalized_config = dict(config)
        for key in ("owner", "version", "status"):
            normalized_config[key] = _required_text(
                normalized_config.get(key),
                key,
                f"policy_design_independence_graded_config_{key}_missing",
            )
        if normalized_config["status"] not in _VALID_GOVERNED_CONFIG_STATUSES:
            raise EvidenceIndependenceError(
                "policy_design_independence_graded_config_status_invalid",
                "Governed config status is not recognized.",
                "graded_independence.governed_config.status",
            )
        row["governed_config"] = normalized_config
    if "graded_effective_independent_evidence_count" in row:
        graded_count = _required_nonnegative_float(
            row.get("graded_effective_independent_evidence_count"),
            "graded_independence.graded_effective_independent_evidence_count",
            "policy_design_independence_graded_effective_count_invalid",
        )
        if graded_count > raw_count:
            raise EvidenceIndependenceError(
                "policy_design_independence_graded_effective_count_exceeds_raw",
                "Graded effective evidence count cannot exceed raw evidence count.",
                "graded_independence.graded_effective_independent_evidence_count",
            )
        row["graded_effective_independent_evidence_count"] = graded_count
    for key in (
        "graded_effective_support_mass",
        "graded_effective_counterevidence_mass",
    ):
        if key not in row:
            continue
        mass = _required_nonnegative_float(
            row.get(key),
            f"graded_independence.{key}",
            f"policy_design_independence_{key}_invalid",
        )
        if mass > raw_count:
            raise EvidenceIndependenceError(
                "policy_design_independence_graded_mass_exceeds_raw",
                "Graded effective mass cannot exceed raw evidence count.",
                f"graded_independence.{key}",
            )
        row[key] = mass
    if row["enabled"] and "effective_independence_graph_ref" in row:
        row["effective_independence_graph_ref"] = _required_text(
            row.get("effective_independence_graph_ref"),
            "effective_independence_graph_ref",
            "policy_design_independence_effective_graph_ref_missing",
        )
    return row


def _build_rare_domain_scarcity_report(
    context: Mapping[str, Any] | None,
    *,
    effective_support_mass: float,
) -> dict[str, Any]:
    if context is None:
        return {
            "status": "not_rare_domain",
            "support_inflation_allowed": False,
            "effective_support_mass_after_scarcity": effective_support_mass,
            "authority_effect": "none",
        }
    status = (
        _text(context.get("scarcity_kind"))
        or _text(context.get("status"))
        or (
            "scarcity_structural"
            if bool(context.get("is_rare_domain", False))
            else "not_rare_domain"
        )
    )
    report = {
        "status": status,
        "support_inflation_allowed": False,
        "effective_support_mass_after_scarcity": effective_support_mass,
        "authority_effect": _scarcity_authority_effect(status),
    }
    for key in (
        "limitation_ref",
        "accepted_deficit_ref",
        "monitoring_plan_ref",
        "next_acquisition_action_ref",
        "minimum_effective_independent_evidence_count",
    ):
        if key in context:
            report[key] = context[key]
    return report


def _validate_rare_domain_scarcity_report(
    value: object,
    *,
    effective_support_mass: float,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceIndependenceError(
            "policy_design_independence_scarcity_report_missing",
            "Evidence independence map must classify rare-domain scarcity.",
            "rare_domain_scarcity",
        )
    row = dict(value)
    status = _required_text(
        row.get("status"),
        "status",
        "policy_design_independence_scarcity_status_missing",
    )
    if status not in _VALID_SCARCITY_STATUSES:
        raise EvidenceIndependenceError(
            "policy_design_independence_scarcity_status_invalid",
            "Rare-domain scarcity status is not recognized.",
            "rare_domain_scarcity.status",
        )
    row["status"] = status
    if bool(row.get("support_inflation_allowed", True)):
        raise EvidenceIndependenceError(
            "policy_design_independence_scarcity_support_inflation",
            "Rare-domain scarcity cannot inflate independent evidence support.",
            "rare_domain_scarcity.support_inflation_allowed",
        )
    row["support_inflation_allowed"] = False
    after_scarcity = _required_nonnegative_float(
        row.get("effective_support_mass_after_scarcity"),
        "rare_domain_scarcity.effective_support_mass_after_scarcity",
        "policy_design_independence_scarcity_effective_mass_missing",
    )
    if after_scarcity > effective_support_mass:
        raise EvidenceIndependenceError(
            "policy_design_independence_scarcity_support_inflation",
            "Rare-domain scarcity cannot increase effective support mass.",
            "rare_domain_scarcity.effective_support_mass_after_scarcity",
        )
    row["effective_support_mass_after_scarcity"] = after_scarcity
    if status == "scarcity_structural" and not any(
        _text(row.get(key))
        for key in ("limitation_ref", "accepted_deficit_ref", "monitoring_plan_ref")
    ):
        raise EvidenceIndependenceError(
            "policy_design_independence_structural_scarcity_surface_missing",
            (
                "Structural scarcity must produce a limitation, accepted deficit, "
                "or monitored-design surface."
            ),
            "rare_domain_scarcity",
        )
    if status == "scarcity_remediable" and not _text(row.get("next_acquisition_action_ref")):
        raise EvidenceIndependenceError(
            "policy_design_independence_remediable_scarcity_action_missing",
            "Remediable scarcity must point to an acquisition action.",
            "rare_domain_scarcity.next_acquisition_action_ref",
        )
    row["authority_effect"] = _text(row.get("authority_effect")) or _scarcity_authority_effect(
        status
    )
    return row


def _validate_mass_clusters_have_reasons(
    collapse_clusters: Sequence[Mapping[str, Any]],
) -> None:
    for index, cluster in enumerate(collapse_clusters):
        raw_line_count = int(cluster.get("raw_line_count") or 0)
        if raw_line_count <= 1:
            continue
        if not cluster.get("collapse_reasons"):
            raise EvidenceIndependenceError(
                "policy_design_independence_collapse_reasons_missing",
                "Collapsed evidence clusters must explain their collapse reasons.",
                f"collapse_clusters[{index}].collapse_reasons",
            )


def _line_polarity(line: Mapping[str, Any]) -> str:
    value = _clean_text(
        line.get("polarity")
        or line.get("evidence_polarity")
        or line.get("stance")
        or line.get("support_polarity")
        or line.get("direction")
    ).lower()
    normalized = value.replace("-", "_").replace(" ", "_")
    if normalized in _COUNTEREVIDENCE_TOKENS or any(
        token in normalized for token in _COUNTEREVIDENCE_TOKENS
    ):
        return "counterevidence"
    if normalized in _CONTEXT_TOKENS:
        return "context"
    return "support"


def _balance_status(*, support_mass: float, counter_mass: float) -> str:
    if support_mass <= 0.0 and counter_mass <= 0.0:
        return "insufficient"
    if counter_mass > support_mass:
        return "counter_dominant"
    if counter_mass > 0.0 and support_mass > 0.0:
        return "mixed"
    return "support_dominant"


def _independence_status(*, raw_count: int, effective_count: int) -> str:
    if effective_count <= 0:
        return "insufficient"
    if raw_count > effective_count:
        return "inflated_raw_count"
    if effective_count == 1:
        return "singular"
    return "sufficient"


def _dominant_reasons(reason_counts: Mapping[str, int]) -> list[dict[str, Any]]:
    return [
        {"reason_code": reason_code, "cluster_count": count}
        for reason_code, count in sorted(
            reason_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _validate_dominant_reasons(value: object) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise EvidenceIndependenceError(
            "policy_design_independence_dominant_reasons_invalid",
            "Dominant collapse reasons must be a sequence.",
            "effective_mass_report.dominant_collapse_reasons",
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvidenceIndependenceError(
                "policy_design_independence_dominant_reason_invalid",
                "Dominant collapse reason rows must be mappings.",
                f"effective_mass_report.dominant_collapse_reasons[{index}]",
            )
        row = dict(item)
        row["reason_code"] = _required_text(
            row.get("reason_code") or row.get("code"),
            "reason_code",
            "policy_design_independence_dominant_reason_code_missing",
        )
        row["cluster_count"] = _required_nonnegative_int(
            row.get("cluster_count"),
            "cluster_count",
            "policy_design_independence_dominant_reason_count_missing",
        )
        rows.append(row)
    return rows


def _scarcity_authority_effect(status: str) -> str:
    if status == "scarcity_structural":
        return "limitation_or_monitored_design"
    if status == "scarcity_remediable":
        return "acquisition_required"
    return "none"


def _reason_value(value: object) -> object:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list | str | int | float | bool) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _reason_value(item) for key, item in value.items()}
    return str(value)


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


def _required_nonnegative_float(value: object, field: str, code: str) -> float:
    if isinstance(value, bool) or value is None:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map must include {field}.",
            field,
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map must include numeric {field}.",
            field,
        ) from exc
    if number < 0.0:
        raise EvidenceIndependenceError(
            code,
            f"Evidence independence map {field} cannot be negative.",
            field,
        )
    return number


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


def _surface_present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping | list | tuple | set):
        return bool(value)
    return value is not None


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
