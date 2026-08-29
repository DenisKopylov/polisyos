"""Compose the read-only DS15 acquisition-growth surface from owner records."""

from __future__ import annotations

from collections.abc import Mapping

from polisyos.runtime.http.services.acquisition_surface_contracts import (
    AcquisitionBacklogProjection,
    AcquisitionGrowthPayload,
    AcquisitionGrowthSummary,
    EpochQualificationDisclosure,
    GapClass,
    N13bHistoryProjection,
    StructuralRouteProjection,
)

_QUALIFICATION_EFFECT = (
    "authority to qualify native semantic production, append its history head "
    "and permit overlay activation"
)
_QUALIFICATION_NON_EFFECTS = (
    "gap shape",
    "passport validity",
    "positive delta",
    "re-entry",
)


def build_acquisition_growth_projection(
    *,
    census: Mapping[str, object],
    journal: Mapping[str, object],
    carrier_liveness: Mapping[str, object],
    executor_contract: Mapping[str, object],
    lifecycle_manifest: Mapping[str, object],
    reentry_trace: Mapping[str, object],
) -> AcquisitionGrowthPayload:
    """Derive strict acquisition facts from the complete historical owner family."""

    _require_schema(
        census,
        "policyos.policy_design_case.gy_n13a.acquisition_census.v1",
    )
    _require_schema(journal, "policyos.layer3.gy.n13a.live_probe_journal.v1")
    _require_schema(
        carrier_liveness,
        "policyos.layer3.gy.n13a.recurring_carrier_liveness.v1",
    )
    _require_schema(
        executor_contract,
        "policyos.layer3.gy.n13b.acquisition_executor_contract.v4",
    )
    _require_schema(lifecycle_manifest, "policyos.layer3.gy.n13b.lifecycle_manifest.v2")
    _require_schema(reentry_trace, "policyos.layer3.gy.n13b.reentry_trace.v1")
    scorecards = _records(census, "family_scorecards")
    metric_resolutions = _records(census, "metric_resolutions")
    backlog_rows = _records(census, "growth_backlog")
    route_rows = _records(census, "route_evidence")
    journal_records = _records(journal, "records")
    n13b_journal = _mapping(executor_contract, "journal")
    n13b_growth = _mapping(executor_contract, "world_growth")
    n13b_reentry = _mapping(executor_contract, "reentry")
    n13b_quarantine = _mapping(executor_contract, "quarantine")
    _require_lifecycle(lifecycle_manifest)

    backlog = tuple(
        AcquisitionBacklogProjection(
            variable_id=_text(row, "variable_id"),
            rank=_integer(row, "rank"),
            binding_confidence=_number(row, "binding_confidence"),
            ranking_score=_number(row, "ranking_score"),
            route_demand=_number(row, "route_demand"),
            ranking_method=_text(row, "ranking_method"),
            authority_boundary=_text(row, "authority_boundary"),
            voi_owner_fit=_text(row, "voi_owner_fit"),
            voi_owner_integration=_text(row, "voi_owner_integration"),
            voi_owner_ref=_text(row, "voi_owner_ref"),
            gap_class=(
                GapClass.DATA_GAP
                if _data_gap_is_independently_reconciled(
                    backlog_row=row,
                    executor_contract=executor_contract,
                    reentry_trace=reentry_trace,
                )
                else GapClass.NOT_ESTABLISHED
            ),
            classification_basis=(
                "independently_reconciled"
                if _data_gap_is_independently_reconciled(
                    backlog_row=row,
                    executor_contract=executor_contract,
                    reentry_trace=reentry_trace,
                )
                else "not_established"
            ),
        )
        for row in backlog_rows
    )
    structural_routes = tuple(_project_structural_route(row) for row in route_rows)
    attempt_count = _integer(n13b_journal, "request_count")
    terminal_count = _integer(n13b_journal, "terminal_count")
    admitted_count = _integer(n13b_journal, "response_admitted_count")
    epoch_count = _integer(n13b_growth, "overlay_epoch_count")
    return AcquisitionGrowthPayload(
        summary=AcquisitionGrowthSummary(
            family_scorecard_count=len(scorecards),
            actual_network_call_count=sum(
                isinstance(row.get("request"), Mapping)
                and isinstance(row.get("raw_response"), Mapping)
                for row in journal_records
            ),
            selected_record_count=len(journal_records),
            metric_resolution_count=len(metric_resolutions),
            backlog_count=len(backlog),
            structural_route_count=len(structural_routes),
        ),
        backlog=backlog,
        structural_routes=structural_routes,
        carrier_liveness=_safe_carrier_liveness(carrier_liveness),
        n13b_history=N13bHistoryProjection(
            attempt_count=attempt_count,
            raw_response_count=_integer(n13b_journal, "raw_response_count"),
            response_admitted_count=admitted_count,
            terminal_count=terminal_count,
            quarantine_count=_integer(n13b_journal, "quarantine_count"),
            overlay_epoch_count=epoch_count,
            execution_phase=(
                "terminal" if attempt_count > 0 and terminal_count == attempt_count else "executing"
            ),
            admission="not_reached" if admitted_count == 0 else "not_established",
            quarantine=(
                "raw_terminal"
                if _integer(n13b_quarantine, "live_attempt_count") > 0 and admitted_count == 0
                else "none"
            ),
            world_growth=(
                "no_growth" if n13b_growth.get("status") == "no_growth" else "not_established"
            ),
            reentry=(
                "deeper_terminal"
                if str(n13b_reentry.get("reentry_disposition") or "").startswith("deeper_terminal")
                else "not_established"
            ),
            epoch_qualification=EpochQualificationDisclosure(
                epoch_state="pending_epoch_activation",
                status="not_established",
                code="policy_admission_missing",
                authority_role="semantic epoch policy-admission qualifier",
                authority_owner_ref=None,
                appointment_state="unappointed",
                appointment_would_establish=_QUALIFICATION_EFFECT,
                appointment_would_not_establish=_QUALIFICATION_NON_EFFECTS,
            ),
        ),
    )


def find_raw_acquisition_sibling_consumers(
    sources: Mapping[str, str],
) -> tuple[str, ...]:
    """Find new raw N13a/N13b readers outside the admitted owner seams."""

    allowed_suffixes = (
        "services/acquisition_surface_projection.py",
        "services/governed_projections.py",
        "services/governed_projection_validation_worker.py",
        "services/cycle_board_sources.py",
    )
    raw_markers = (
        "layer3_gy_n13a_acquisition_census.json",
        "layer3_gy_n13a_live_probe_journal.json",
        "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json",
        "layer3_gy_n13b_acquisition_executor_contract.json",
        "layer3_gy_n13b_lifecycle_manifest.json",
        "layer3_gy_n13b_reentry_trace.json",
        "layer3_gy_acquisition_raw_journal.jsonl",
    )
    read_markers = (".read_text(", ".read_bytes(", "_load_json(", "json.load(", "open(")
    return tuple(
        sorted(
            path
            for path, source in sources.items()
            if not path.endswith(allowed_suffixes)
            and any(marker in source for marker in raw_markers)
            and any(marker in source for marker in read_markers)
        )
    )


def _data_gap_is_independently_reconciled(
    *,
    backlog_row: Mapping[str, object],
    executor_contract: Mapping[str, object],
    reentry_trace: Mapping[str, object],
) -> bool:
    variable_id = backlog_row.get("variable_id")
    if not isinstance(variable_id, str) or backlog_row.get("gap_kind") != "binding_gap":
        return False
    requirement = reentry_trace.get("requirement_gap")
    availability = None
    if isinstance(requirement, Mapping):
        metadata = requirement.get("metadata")
        if isinstance(metadata, Mapping):
            availability = metadata.get("availability")
    local_lift = executor_contract.get("local_lift")
    reentry = executor_contract.get("reentry")
    if not isinstance(requirement, Mapping) or not isinstance(availability, Mapping):
        return False
    if not isinstance(local_lift, Mapping) or not isinstance(reentry, Mapping):
        return False
    rows = local_lift.get("rows")
    matched_local = (
        isinstance(rows, list)
        and sum(
            isinstance(row, Mapping)
            and row.get("variable_id") == variable_id
            and row.get("gap_kind") == "binding_gap"
            for row in rows
        )
        == 1
    )
    missing_fields = requirement.get("missing_requirement_fields")
    return bool(
        matched_local
        and reentry_trace.get("target_variable") == variable_id
        and reentry.get("target_variable") == variable_id
        and reentry.get("trace_sha256") == reentry_trace.get("trace_sha256")
        and requirement.get("requirement_family") == "data_requirement"
        and requirement.get("gap_type") == "data_snapshot_release"
        and isinstance(missing_fields, list)
        and f"canonical_variable_observations:{variable_id}" in missing_fields
        and availability.get("variable_id") == variable_id
        and availability.get("status") == "unavailable"
        and availability.get("dataset_count") == 0
        and availability.get("metric_binding_count") == 0
        and availability.get("observation_count") == 0
    )


def _project_structural_route(row: Mapping[str, object]) -> StructuralRouteProjection:
    route = row.get("route")
    route_mapping = route if isinstance(route, Mapping) else {}
    established = (
        row.get("route_class") == "not_a_data_gap"
        and isinstance(route_mapping.get("witness_kind"), str)
        and isinstance(route_mapping.get("missing_link"), str)
    )
    return StructuralRouteProjection(
        route_id=_text(route_mapping, "route_id"),
        route_class=_text(row, "route_class"),
        witness_kind=_text(route_mapping, "witness_kind"),
        missing_link=_text(route_mapping, "missing_link"),
        gap_class=GapClass.STRUCTURAL_GAP if established else GapClass.NOT_ESTABLISHED,
        action_eligibility="not_applicable" if established else "blocked",
    )


def _require_lifecycle(source: Mapping[str, object]) -> None:
    registrations = _records(source, "registrations")
    if len(registrations) != 43:
        raise ValueError("n13b_lifecycle_registration_count_mismatch")
    content_bound = sum(row.get("registration_status") == "content_bound" for row in registrations)
    writer_managed = sum(
        row.get("registration_status") == "writer_managed" for row in registrations
    )
    if content_bound != 41 or writer_managed != 2:
        raise ValueError("n13b_lifecycle_registration_partition_mismatch")


def _require_schema(source: Mapping[str, object], expected: str) -> None:
    if source.get("schema_version") != expected:
        raise ValueError("acquisition_growth_source_schema_mismatch")


def _safe_carrier_liveness(source: Mapping[str, object]) -> dict[str, object]:
    fields = (
        "schema_version",
        "rule_version",
        "request_dataset_id",
        "connector_id",
        "execution_tier",
        "data_disposition",
        "metadata_disposition",
        "carrier_disposition",
        "missing_request_levers",
        "source_receipt_sha256",
    )
    return {field: source[field] for field in fields if field in source}


def _mapping(source: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = source.get(field)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field}_must_be_mapping")
    return value


def _records(source: Mapping[str, object], field: str) -> list[Mapping[str, object]]:
    value = source.get(field)
    if not isinstance(value, list) or not all(isinstance(row, Mapping) for row in value):
        raise ValueError(f"{field}_must_be_record_array")
    return value


def _text(source: Mapping[str, object], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field}_must_be_text")
    return value


def _integer(source: Mapping[str, object], field: str) -> int:
    value = source.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field}_must_be_integer")
    return value


def _number(source: Mapping[str, object], field: str) -> float:
    value = source.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field}_must_be_number")
    return float(value)


__all__ = [
    "build_acquisition_growth_projection",
    "find_raw_acquisition_sibling_consumers",
]
