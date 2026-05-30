"""Capability white-space report and failure-mode query layer.

Phase 6 makes missing evidence operational: failure-mode nodes are read from
the primary capability-index DuckDB, checked against owned acquisition
strategies, and projected into grouped reports for operators and validation
tools.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

from polisyos.runtime.quality.capability_index import (
    AcquisitionStrategy,
    FailureModeNode,
)

CAPABILITY_WHITE_SPACE_REPORT_SCHEMA_VERSION = (
    "policyos.capability_white_space_report.v1"
)
DEFAULT_REVIEW_TTL = "P30D"
DEFAULT_REVIEW_CADENCE = "P14D"

CONSTRUCT_DOMAINS: dict[str, tuple[str, ...]] = {
    "firm_survival": ("msme_credit", "employment_outcome"),
    "credit_program_enrollment": ("msme_credit", "fiscal_program_delivery"),
    "regional_displacement_pressure": ("displacement", "service_delivery"),
}
STATUS_TO_GAP_TYPE: dict[str, str] = {
    "blocked_construct_not_observed": "construct_gap",
    "blocked_acquisition_required": "acquisition_gap",
    "blocked_construct_validity_below_floor": "construct_validity_gap",
    "blocked_sample_size_below_floor": "sample_size_gap",
    "blocked_freshness": "freshness_gap",
    "blocked_rights_boundary": "rights_gap",
    "blocked_authority_boundary": "legal_authority_gap",
}


class WhiteSpaceValidationError(ValueError):
    """Raised when capability white-space nodes or strategies are incomplete."""


def build_capability_white_space_report_from_duckdb(
    path: str | Path,
) -> dict[str, Any]:
    """Build a white-space report from the primary capability-index DuckDB.

    Args:
        path: Path to ``capability_index_v1.duckdb``.

    Returns:
        A stable JSON-serializable report grouped by construct, domain,
        authority posture, and producer owner.

    Raises:
        WhiteSpaceValidationError: If failure nodes reference missing
            strategies or required ownership lifecycle fields are absent.
    """

    failure_modes, acquisition_strategies = load_white_space_records_from_duckdb(path)
    return build_capability_white_space_report(
        failure_modes=failure_modes,
        acquisition_strategies=acquisition_strategies,
    )


def load_white_space_records_from_duckdb(
    path: str | Path,
) -> tuple[tuple[FailureModeNode, ...], tuple[AcquisitionStrategy, ...]]:
    """Load failure-mode nodes and acquisition strategies from DuckDB."""

    import duckdb

    db_path = Path(path)
    with duckdb.connect(str(db_path), read_only=True) as con:
        failure_rows = con.execute(
            "SELECT failure_json FROM failure_modes ORDER BY failure_id"
        ).fetchall()
        strategy_rows = con.execute(
            "SELECT strategy_json FROM acquisition_strategies ORDER BY strategy_id"
        ).fetchall()
    return (
        tuple(FailureModeNode.model_validate_json(row[0]) for row in failure_rows),
        tuple(AcquisitionStrategy.model_validate_json(row[0]) for row in strategy_rows),
    )


def build_capability_white_space_report(
    *,
    failure_modes: Sequence[FailureModeNode | Mapping[str, Any]],
    acquisition_strategies: Sequence[AcquisitionStrategy | Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate a grouped capability white-space report."""

    nodes = tuple(_enriched_failure_node(_failure_node(item)) for item in failure_modes)
    strategies = tuple(_strategy(item) for item in acquisition_strategies)
    errors = white_space_validation_errors(nodes, strategies)
    if errors:
        raise WhiteSpaceValidationError("; ".join(errors))
    strategy_rows = tuple(strategy.model_dump(mode="json") for strategy in strategies)
    node_rows = tuple(node.model_dump(mode="json") for node in nodes)
    groups = _group_rows(nodes)
    return {
        "schema_version": CAPABILITY_WHITE_SPACE_REPORT_SCHEMA_VERSION,
        "failure_modes": list(node_rows),
        "white_space": list(node_rows),
        "acquisition_strategies": list(strategy_rows),
        "groups": groups,
        "groupings": {
            "by_construct": _grouping(node_rows, "construct"),
            "by_domain": _domain_grouping(nodes),
            "by_authority_posture": _grouping(node_rows, "authority_posture"),
            "by_producer_owner": _grouping(node_rows, "producer_owner"),
        },
        "summary": {
            "failure_mode_count": len(nodes),
            "acquisition_strategy_count": len(strategies),
            "group_count": len(groups),
            "status_counts": dict(sorted(Counter(node.status for node in nodes).items())),
            "gap_type_counts": dict(sorted(Counter(node.gap_type for node in nodes).items())),
            "construct_count": len({node.construct_id for node in nodes}),
        },
        "validation": {"status": "pass", "errors": []},
    }


def white_space_validation_errors(
    failure_modes: Sequence[FailureModeNode],
    acquisition_strategies: Sequence[AcquisitionStrategy],
) -> list[str]:
    """Return validation errors for Phase 6 hard gates."""

    strategy_by_id = {strategy.strategy_id: strategy for strategy in acquisition_strategies}
    errors: list[str] = []
    for node in failure_modes:
        missing_dimensions = [
            name
            for name, value in (
                ("construct", node.construct_id),
                ("domain", node.domain),
                ("authority_posture", node.authority_posture),
                ("producer_owner", node.producer_owner),
            )
            if not value
        ]
        if missing_dimensions:
            errors.append(
                f"failure node {node.failure_id} missing group dimensions: "
                f"{','.join(missing_dimensions)}"
            )
        if not node.acquisition_strategy_refs:
            errors.append(f"failure node {node.failure_id} has no acquisition_strategy_refs")
        for ref in node.acquisition_strategy_refs:
            strategy = strategy_by_id.get(ref)
            if strategy is None:
                errors.append(
                    f"failure node {node.failure_id} has orphan acquisition_strategy_ref {ref}"
                )
                continue
            errors.extend(_strategy_lifecycle_errors(strategy, node=node))
    for strategy in acquisition_strategies:
        errors.extend(_strategy_lifecycle_errors(strategy, node=None))
    return sorted(set(errors))


def _strategy_lifecycle_errors(
    strategy: AcquisitionStrategy,
    *,
    node: FailureModeNode | None,
) -> list[str]:
    errors: list[str] = []
    prefix = (
        f"strategy {strategy.strategy_id}"
        if node is None
        else f"failure node {node.failure_id} strategy {strategy.strategy_id}"
    )
    required = {
        "owner_team": strategy.owner_team,
        "estimated_cost": strategy.estimated_cost,
        "estimated_time": strategy.estimated_time,
        "prerequisites": strategy.prerequisites,
        "contact_path": strategy.contact_path,
        "ttl": strategy.ttl,
        "review_cadence": strategy.review_cadence,
        "escalation_owner": strategy.escalation_owner,
    }
    for field_name, value in required.items():
        if not value:
            errors.append(f"{prefix} missing {field_name}")
    if _government_data_involved(strategy.authority_class) and not strategy.legal_counsel_owner:
        errors.append(f"{prefix} missing legal_counsel_owner")
    if (
        strategy.resulting_authority_envelope.get("production") == "admissible"
        and not strategy.requires_construct_validity_review
    ):
        errors.append(
            f"{prefix} claims production admissible without "
            "requires_construct_validity_review"
        )
    return errors


def _enriched_failure_node(node: FailureModeNode) -> FailureModeNode:
    domain = node.domain or CONSTRUCT_DOMAINS.get(node.construct_id, ("uncategorized",))
    authority_posture = node.authority_posture or _first_posture(node)
    producer_owner = node.producer_owner or node.owner
    status = node.status or _status_from_gap_type(node.gap_type)
    gap_type = node.gap_type or STATUS_TO_GAP_TYPE.get(status, "acquisition_gap")
    return node.model_copy(
        update={
            "status": status,
            "gap_type": gap_type,
            "domain": tuple(domain),
            "authority_posture": authority_posture,
            "producer_owner": producer_owner,
            "ttl": node.ttl or DEFAULT_REVIEW_TTL,
            "review_cadence": node.review_cadence or DEFAULT_REVIEW_CADENCE,
            "escalation_owner": node.escalation_owner or producer_owner,
        }
    )


def _group_rows(nodes: Sequence[FailureModeNode]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for node in nodes:
        for domain in node.domain:
            key = (
                node.construct_id,
                domain,
                node.authority_posture,
                node.producer_owner or node.owner,
            )
            row = buckets.setdefault(
                key,
                {
                    "construct": key[0],
                    "domain": key[1],
                    "authority_posture": key[2],
                    "producer_owner": key[3],
                    "failure_ids": [],
                    "statuses": [],
                    "gap_types": [],
                    "acquisition_strategy_refs": [],
                    "count": 0,
                },
            )
            row["failure_ids"].append(node.failure_id)
            row["statuses"].append(node.status)
            row["gap_types"].append(node.gap_type)
            row["acquisition_strategy_refs"].extend(node.acquisition_strategy_refs)
            row["count"] += 1
    return [_canonical_group_row(row) for row in buckets.values()]


def _canonical_group_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "failure_ids": sorted(set(row["failure_ids"])),
        "statuses": sorted(set(row["statuses"])),
        "gap_types": sorted(set(row["gap_types"])),
        "acquisition_strategy_refs": sorted(set(row["acquisition_strategy_refs"])),
    }


def _grouping(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "failure_ids": []})
    for row in rows:
        value = str(row.get(key) or "missing")
        grouped[value]["count"] += 1
        grouped[value]["failure_ids"].append(str(row["failure_id"]))
    return {
        key: {"count": value["count"], "failure_ids": sorted(set(value["failure_ids"]))}
        for key, value in sorted(grouped.items())
    }


def _domain_grouping(nodes: Sequence[FailureModeNode]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "failure_ids": []})
    for node in nodes:
        for domain in node.domain:
            grouped[domain]["count"] += 1
            grouped[domain]["failure_ids"].append(node.failure_id)
    return {
        key: {"count": value["count"], "failure_ids": sorted(set(value["failure_ids"]))}
        for key, value in sorted(grouped.items())
    }


def _failure_node(item: FailureModeNode | Mapping[str, Any]) -> FailureModeNode:
    return item if isinstance(item, FailureModeNode) else FailureModeNode.model_validate(item)


def _strategy(item: AcquisitionStrategy | Mapping[str, Any]) -> AcquisitionStrategy:
    return (
        item
        if isinstance(item, AcquisitionStrategy)
        else AcquisitionStrategy.model_validate(item)
    )


def _first_posture(node: FailureModeNode) -> str:
    if node.affected_authority_postures:
        return node.affected_authority_postures[0]
    return "production"


def _status_from_gap_type(gap_type: str) -> str:
    for status, candidate in STATUS_TO_GAP_TYPE.items():
        if candidate == gap_type:
            return status
    return "blocked_acquisition_required"


def _government_data_involved(authority_class: str) -> bool:
    normalized = authority_class.casefold()
    return any(
        marker in normalized
        for marker in ("government", "official", "registry", "administrative")
    )


def dump_capability_white_space_report(payload: Mapping[str, Any]) -> str:
    """Return canonical report JSON for CLI output."""

    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
