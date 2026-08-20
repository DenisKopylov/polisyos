"""Server-owned composition for the promoted Depth-N Cycle Board surface."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from polisyos.runtime.http.services.adapters import RunTerminality
from polisyos.runtime.http.services.cycle_board_contracts import (
    CYCLE_BOARD_PROJECTION_RULE_VERSION,
    CYCLE_BOARD_STABLE_ADDRESS,
    AbsentFact,
    AvailableFact,
    CycleBoardAcquisitionRoute,
    CycleBoardCompositionSource,
    CycleBoardCoverageGap,
    CycleBoardExportResponse,
    CycleBoardMovementGap,
    CycleBoardProjectionPacket,
    CycleBoardReplayConflictError,
    CycleBoardRow,
    DepthNCycleBoardPayloadV2,
    LifecycleFact,
    ReadinessFact,
    StringFact,
)
from polisyos.runtime.http.services.cycle_board_sources import (
    N13B_DENIED_ROW_USES,
    HistoricalDispositionError,
    N13BGlobalMovementSignal,
    load_ds4_realized_disposition,
    load_historical_producer_availability,
    load_n13b_global_movement_signal,
    parse_ds4_realized_disposition,
)
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.governed_projections import (
    AvailableGovernedProjectionPacket,
    DepthNAcquisitionRouteProjection,
    DepthNDomainRunProjection,
    GovernedProjectionPacket,
    LegacyProvingGroundPayload,
    ProjectionAvailability,
    ProjectionId,
    ReplayPinMismatchError,
    SurfaceReadinessPayload,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_N10_ORDER = ("first_vertical", "education", "unseen")
_GOVERNED_COMPONENT_ORDER = (
    ProjectionId.DEPTH_N_CYCLE_BOARD,
    ProjectionId.N13A_ACQUISITION_CENSUS,
    ProjectionId.N13A_LIVE_PROBE_JOURNAL,
    ProjectionId.LEGACY_PROVING_GROUND,
    ProjectionId.SURFACE_READINESS,
)


class _ProjectionService(Protocol):
    def get(self, projection_id: ProjectionId, **pins: object) -> GovernedProjectionPacket: ...


class _IndexedRunRecord(Protocol):
    summary: object


class _RunIndex(Protocol):
    def get_run(self, run_id: str) -> _IndexedRunRecord: ...


def _absent(
    availability: Literal["not_established", "artifact_missing", "invalid_source"],
    *,
    reason: str,
    owner_route: str,
) -> AbsentFact:
    return AbsentFact(
        availability=availability,
        reason=reason,
        owner_route=owner_route,
    )


def _available[T](
    value: T,
    *,
    source_ref: str,
    source_as_of: datetime | None,
) -> AvailableFact[T]:
    return AvailableFact(value=value, source_ref=source_ref, source_as_of=source_as_of)


def _packet_source_ref(packet: GovernedProjectionPacket) -> str:
    source = getattr(packet, "source", None)
    if source is not None:
        return source.relative_path
    return packet.stable_address


def _packet_availability(packet: GovernedProjectionPacket) -> str:
    availability = packet.availability
    return availability.value if isinstance(availability, ProjectionAvailability) else availability


def _absence_from_packet(
    packet: GovernedProjectionPacket,
    *,
    owner_route: str,
    fallback_reason: str,
) -> AbsentFact:
    availability = _packet_availability(packet)
    if availability not in {"artifact_missing", "invalid_source"}:
        availability = "not_established"
    return _absent(
        availability,
        reason=getattr(packet, "absence_reason", None) or fallback_reason,
        owner_route=owner_route,
    )


def _fact_from_optional_number(
    value: float | int | None,
    *,
    source_ref: str,
    source_as_of: datetime | None,
    field_name: str,
) -> AvailableFact[float] | AvailableFact[int] | AbsentFact:
    if value is None:
        return _absent(
            "not_established",
            reason=f"N7 planner did not record {field_name}",
            owner_route="polisyos.runtime.quality.acquisition_planner",
        )
    return _available(value, source_ref=source_ref, source_as_of=source_as_of)


def _compose_acquisition_route(
    route: DepthNAcquisitionRouteProjection,
    *,
    source_ref: str,
    source_as_of: datetime | None,
) -> CycleBoardAcquisitionRoute:
    return CycleBoardAcquisitionRoute(
        owner=route.owner,
        route_kind=route.route_kind,
        planner_report_content_hash=route.planner_report_content_hash,
        planner_status=route.planner_status,
        requirement_gap_id=route.requirement_gap_id,
        missing_requirement_fields=route.missing_requirement_fields,
        recommended_strategy=route.recommended_strategy,
        expected_cost=_fact_from_optional_number(
            route.expected_cost,
            source_ref=source_ref,
            source_as_of=source_as_of,
            field_name="expected cost",
        ),
        expected_voi=_fact_from_optional_number(
            route.expected_voi,
            source_ref=source_ref,
            source_as_of=source_as_of,
            field_name="expected VOI",
        ),
        voi_rank=_fact_from_optional_number(
            route.voi_rank,
            source_ref=source_ref,
            source_as_of=source_as_of,
            field_name="VOI rank",
        ),
        decision_owner_ref=route.decision_owner_ref,
        producer_expected=route.producer_expected,
        next_action=route.next_action,
        execution_status=_absent(
            "not_established",
            reason="no admitted acquisition execution receipt is bound to this row",
            owner_route=route.producer_expected,
        ),
    )


def _governed_source_entry(packet: GovernedProjectionPacket) -> CycleBoardCompositionSource:
    source = getattr(packet, "source", None)
    return CycleBoardCompositionSource(
        source_id=packet.projection_id.value,
        source_kind="governed_projection",
        source_ref=source.relative_path if source is not None else packet.stable_address,
        availability=_packet_availability(packet),
        artifact_content_hash=(source.artifact_content_hash if source is not None else None),
        source_dependency_hash=getattr(packet, "source_dependency_hash", None),
        as_of=packet.as_of,
        freshness=packet.freshness,
        authoritative_for=packet.authoritative_for,
        may_not_use_for=packet.may_not_use_for,
        absence_reason=getattr(packet, "absence_reason", None),
    )


def _n13b_source_entry(signal: N13BGlobalMovementSignal) -> CycleBoardCompositionSource:
    return CycleBoardCompositionSource(
        source_id="n13b-global-deeper-terminal",
        source_kind="control_plane_evidence",
        source_ref=signal.source_ref,
        availability=signal.availability,
        artifact_content_hash=signal.source_content_hash,
        authoritative_for=(
            ("global_demonstration_status",) if signal.availability == "available" else ()
        ),
        may_not_use_for=N13B_DENIED_ROW_USES,
        absence_reason=signal.reason,
    )


def _historical_source_entry(
    *,
    source_id: str,
    source_ref: str,
    source_content_hash: str,
    authoritative_for: tuple[str, ...],
) -> CycleBoardCompositionSource:
    return CycleBoardCompositionSource(
        source_id=source_id,
        source_kind="historical_owner_record",
        source_ref=source_ref,
        availability="available",
        artifact_content_hash=source_content_hash,
        authoritative_for=authoritative_for,
        may_not_use_for=("current_readiness", "current_producer_availability"),
    )


def _readiness_fact(packet: GovernedProjectionPacket) -> ReadinessFact:
    if isinstance(packet, AvailableGovernedProjectionPacket):
        payload = packet.payload
        if not isinstance(payload, SurfaceReadinessPayload):
            raise TypeError("surface readiness packet carried the wrong payload")
        return _available(
            payload,
            source_ref=packet.source.relative_path,
            source_as_of=packet.as_of,
        )
    return _absence_from_packet(
        packet,
        owner_route="Revision-3 surface readiness owner and validator",
        fallback_reason="surface readiness is not established",
    )


def _n13a_missing_links(packet: GovernedProjectionPacket) -> dict[str, str]:
    if not isinstance(packet, AvailableGovernedProjectionPacket):
        return {}
    route_evidence = getattr(packet.payload, "route_evidence", ())
    links: dict[str, str] = {}
    for item in route_evidence:
        route = item.get("route") if isinstance(item, dict) else None
        if not isinstance(route, dict):
            continue
        role = route.get("domain_role")
        missing_link = route.get("missing_link")
        if isinstance(role, str) and isinstance(missing_link, str):
            links[role] = missing_link
    return links


def _lifecycle_binding(
    run_index: _RunIndex,
    run_id: str,
) -> tuple[LifecycleFact, CycleBoardCompositionSource]:
    source_id = f"run-summary:{run_id}"
    summary: object | None = None
    try:
        record = run_index.get_run(run_id)
    except KeyError:
        record = None
    if record is not None:
        summary = record.summary
    signed_value = getattr(summary, "run_terminality", None)
    summary_run_id = getattr(summary, "run_id", None)
    if summary_run_id == run_id and isinstance(signed_value, RunTerminality):
        content_hash = hash_export_projection(
            {"run_id": summary_run_id, "run_terminality": signed_value.value}
        )
        fact: LifecycleFact = _available(
            signed_value,
            source_ref=source_id,
            source_as_of=None,
        )
        availability = "available"
        reason = None
    else:
        content_hash = None
        fact = _absent(
            "not_established",
            reason="no exact producer-signed RunSummary terminality binding exists",
            owner_route="core RunSummary.run_terminality",
        )
        availability = "not_established"
        reason = "exact signed lifecycle binding is absent"
    entry = CycleBoardCompositionSource(
        source_id=source_id,
        source_kind="run_summary_lookup",
        source_ref=source_id,
        availability=availability,
        artifact_content_hash=content_hash,
        source_dependency_hash=content_hash,
        authoritative_for=("run_lifecycle_terminality",),
        may_not_use_for=("status_proxy", "time_proxy", "search_terminal_proxy"),
        absence_reason=reason,
    )
    return fact, entry


def _capstone_rows(
    depth_packet: GovernedProjectionPacket,
    n13a_packet: GovernedProjectionPacket,
    readiness: ReadinessFact,
    run_index: _RunIndex,
) -> tuple[tuple[CycleBoardRow, ...], tuple[CycleBoardCompositionSource, ...]]:
    if not isinstance(depth_packet, AvailableGovernedProjectionPacket):
        return (), ()
    domain_runs = getattr(depth_packet.payload, "domain_runs", None)
    if not isinstance(domain_runs, dict):
        raise TypeError("depth-N packet omitted its typed domain runs")
    source_ref = depth_packet.source.relative_path
    source_as_of = depth_packet.as_of
    n13a_links = _n13a_missing_links(n13a_packet)
    n13a_source_ref = _packet_source_ref(n13a_packet)
    rows: list[CycleBoardRow] = []
    lifecycle_entries: list[CycleBoardCompositionSource] = []
    for role in _N10_ORDER:
        raw_run = domain_runs.get(role)
        if not isinstance(raw_run, DepthNDomainRunProjection):
            raise ValueError(f"depth-N owner packet omitted the {role} domain run")
        lifecycle, lifecycle_entry = _lifecycle_binding(
            run_index,
            raw_run.generation_cycle_run_id,
        )
        lifecycle_entries.append(lifecycle_entry)
        missing_link_value = n13a_links.get(role)
        if missing_link_value is not None:
            missing_link: StringFact = _available(
                missing_link_value,
                source_ref=n13a_source_ref,
                source_as_of=n13a_packet.as_of,
            )
        elif _packet_availability(n13a_packet) in {"artifact_missing", "invalid_source"}:
            missing_link = _absence_from_packet(
                n13a_packet,
                owner_route="GY-N13a acquisition route owner",
                fallback_reason="typed structural missing link is unavailable",
            )
        else:
            missing_link = _absent(
                "not_established",
                reason="N13a did not bind a structural missing link for this row",
                owner_route="GY-N13a acquisition route owner",
            )
        design_problem_id = raw_run.design_problem.design_problem_id
        rows.append(
            CycleBoardRow(
                row_id=design_problem_id,
                cohort="n10_capstone",
                domain_role=role,
                generation_cycle_run_id=_available(
                    raw_run.generation_cycle_run_id,
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                design_problem=_available(
                    raw_run.design_problem,
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                search_terminal_kind=_available(
                    raw_run.search_terminal_kind,
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                lifecycle_terminality=lifecycle,
                structural_evidence_class=_available(
                    raw_run.evidence_class,
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                weakest_links=_available(
                    raw_run.weakest_links,
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                missing_link=missing_link,
                acquisition_route=_available(
                    _compose_acquisition_route(
                        raw_run.acquisition_route,
                        source_ref=source_ref,
                        source_as_of=source_as_of,
                    ),
                    source_ref=source_ref,
                    source_as_of=source_as_of,
                ),
                responsible_slices=("GY-N10", "GY-N13a", "DS7"),
                stage_trace_href=_absent(
                    "not_established",
                    reason="DS8 has not bound a stage-trace route for this row",
                    owner_route="DS8 stage-trace drill-down",
                ),
                surface_readiness=readiness,
                explanation_code="cycle_board.refusal_with_path",
                explanation_inputs={
                    "design_problem_id": design_problem_id,
                    "domain_role": role,
                },
            )
        )
    return tuple(rows), tuple(lifecycle_entries)


def _legacy_rows(
    packet: GovernedProjectionPacket,
    readiness: ReadinessFact,
) -> tuple[CycleBoardRow, ...]:
    if not isinstance(packet, AvailableGovernedProjectionPacket):
        return ()
    payload = packet.payload
    if not isinstance(payload, LegacyProvingGroundPayload):
        raise TypeError("legacy proving-ground packet carried the wrong payload")

    def runtime_absence(field: str) -> AbsentFact:
        return _absent(
            "artifact_missing",
            reason=f"legacy fixture owner carries no validator-confirmed runtime {field}",
            owner_route="legacy proving-ground runtime outcome producer",
        )

    return tuple(
        CycleBoardRow(
            row_id=identity.case_id,
            cohort="legacy_fixture",
            domain_role=identity.case_id,
            generation_cycle_run_id=runtime_absence("cycle binding"),
            design_problem=runtime_absence("DesignProblem"),
            search_terminal_kind=runtime_absence("search terminal"),
            lifecycle_terminality=runtime_absence("lifecycle terminality"),
            structural_evidence_class=runtime_absence("evidence class"),
            weakest_links=runtime_absence("weakest links"),
            missing_link=runtime_absence("missing link"),
            acquisition_route=runtime_absence("acquisition route"),
            responsible_slices=("legacy-proving-ground", "DS7"),
            stage_trace_href=runtime_absence("DS8 stage trace"),
            surface_readiness=readiness,
            explanation_code="cycle_board.fixture_only_runtime_absent",
            explanation_inputs={"case_id": identity.case_id, "domain": identity.domain},
        )
        for identity in payload.fixture_identities
    )


def _manifest_hash_material(
    manifest: tuple[CycleBoardCompositionSource, ...],
) -> tuple[dict[str, Any], ...]:
    """Bind source truth while excluding request-observation timestamps."""

    material: list[dict[str, Any]] = []
    for entry in manifest:
        dumped = entry.model_dump(mode="json")
        freshness = dumped.get("freshness")
        if isinstance(freshness, dict):
            freshness = dict(freshness)
            freshness.pop("observed_at", None)
            dumped["freshness"] = freshness
        material.append(dumped)
    return tuple(material)


class CycleBoardProjectionService:
    """Compose producer-owned Cycle Board facts without minting their authority."""

    def __init__(
        self,
        *,
        projection_service: _ProjectionService,
        run_index: _RunIndex,
        repository_root: Path,
        clock: Callable[[], datetime] | None = None,
        n13b_global_signal: N13BGlobalMovementSignal | None = None,
    ) -> None:
        self._projection_service = projection_service
        self._run_index = run_index
        self._repository_root = repository_root
        self._clock = clock or (lambda: datetime.now(UTC))
        self._n13b_global_signal = n13b_global_signal

    def get(
        self,
        *,
        replay_target: Literal["raw_v1", "composed_v2"] | None = None,
        artifact_content_hash: str | None = None,
        projection_hash: str | None = None,
        source_dependency_hash: str | None = None,
        source_as_of: datetime | None = None,
        projection_rule_version: str | None = None,
        composition_manifest_hash: str | None = None,
    ) -> CycleBoardExportResponse:
        """Return unpinned v2 or one complete, unmixed replay generation."""

        raw_complete = all(
            value is not None
            for value in (
                artifact_content_hash,
                projection_hash,
                source_dependency_hash,
                source_as_of,
            )
        )
        v2_complete = all(
            value is not None
            for value in (
                projection_rule_version,
                composition_manifest_hash,
                projection_hash,
                source_dependency_hash,
            )
        )
        any_pin = any(
            value is not None
            for value in (
                artifact_content_hash,
                projection_hash,
                source_dependency_hash,
                source_as_of,
                projection_rule_version,
                composition_manifest_hash,
            )
        )
        if replay_target == "raw_v1":
            if (
                not raw_complete
                or projection_rule_version is not None
                or composition_manifest_hash is not None
            ):
                raise CycleBoardReplayConflictError(
                    "raw_v1 replay requires exactly the complete legacy four-pin tuple"
                )
            try:
                return self._projection_service.get(
                    ProjectionId.DEPTH_N_CYCLE_BOARD,
                    artifact_content_hash=artifact_content_hash,
                    projection_hash=projection_hash,
                    source_dependency_hash=source_dependency_hash,
                    source_as_of=source_as_of,
                )
            except ReplayPinMismatchError as exc:
                raise CycleBoardReplayConflictError(str(exc)) from exc
        if replay_target == "composed_v2":
            if not v2_complete or artifact_content_hash is not None or source_as_of is not None:
                raise CycleBoardReplayConflictError(
                    "composed_v2 replay requires exactly the complete v2 four-pin tuple"
                )
            packet = self._compose()
            expected = {
                "projection_rule_version": projection_rule_version,
                "composition_manifest_hash": composition_manifest_hash,
                "projection_hash": projection_hash,
                "source_dependency_hash": source_dependency_hash,
            }
            actual = {field: getattr(packet, field) for field in expected}
            if actual != expected:
                raise CycleBoardReplayConflictError(
                    "composed_v2 replay pins do not match the current composition"
                )
            return packet
        if replay_target is not None or any_pin:
            raise CycleBoardReplayConflictError(
                "Cycle Board replay pins require an explicit, unmixed replay target"
            )
        return self._compose()

    def _compose(self) -> CycleBoardProjectionPacket:
        packets = {
            projection_id: self._projection_service.get(projection_id)
            for projection_id in _GOVERNED_COMPONENT_ORDER
        }
        n13b = self._n13b_global_signal or load_n13b_global_movement_signal(self._repository_root)
        ds4 = load_ds4_realized_disposition(self._repository_root)
        history = load_historical_producer_availability(self._repository_root)
        readiness = _readiness_fact(packets[ProjectionId.SURFACE_READINESS])
        capstones, lifecycle_entries = _capstone_rows(
            packets[ProjectionId.DEPTH_N_CYCLE_BOARD],
            packets[ProjectionId.N13A_ACQUISITION_CENSUS],
            readiness,
            self._run_index,
        )
        legacy = _legacy_rows(packets[ProjectionId.LEGACY_PROVING_GROUND], readiness)
        rows = (*capstones, *legacy)
        manifest = (
            *(_governed_source_entry(packets[item]) for item in _GOVERNED_COMPONENT_ORDER),
            _n13b_source_entry(n13b),
            _historical_source_entry(
                source_id="ds4-realized-disposition",
                source_ref=ds4.source_ref,
                source_content_hash=ds4.source_content_hash,
                authoritative_for=("historical_ds4_component_disposition",),
            ),
            _historical_source_entry(
                source_id="historical-producer-availability",
                source_ref=history.source_ref,
                source_content_hash=history.source_content_hash,
                authoritative_for=("historical_environment_relative_measurement",),
            ),
            *lifecycle_entries,
        )
        payload = DepthNCycleBoardPayloadV2(
            rows=rows,
            coverage=CycleBoardCoverageGap(known_row_count=len(rows)),
            movement_gap=CycleBoardMovementGap(),
            realized_ds4_disposition=ds4,
            historical_producer_availability=history,
        )
        manifest_material = _manifest_hash_material(manifest)
        manifest_hash = hash_export_projection(manifest_material)
        dependency_hash = hash_export_projection(
            tuple(
                {
                    "source_id": item["source_id"],
                    "availability": item["availability"],
                    "artifact_content_hash": item["artifact_content_hash"],
                    "source_dependency_hash": item["source_dependency_hash"],
                    "absence_reason": item["absence_reason"],
                }
                for item in manifest_material
            )
        )
        resolved_projection_hash = hash_export_projection(
            {
                "projection_rule_version": CYCLE_BOARD_PROJECTION_RULE_VERSION,
                "composition_manifest": manifest_material,
                "payload": payload,
            }
        )
        replay_address = build_export_replay_address(
            CYCLE_BOARD_STABLE_ADDRESS,
            {
                "replay_target": "composed_v2",
                "projection_rule_version": CYCLE_BOARD_PROJECTION_RULE_VERSION,
                "composition_manifest_hash": manifest_hash,
                "projection_hash": resolved_projection_hash,
                "source_dependency_hash": dependency_hash,
            },
        )
        return CycleBoardProjectionPacket(
            composition_manifest=manifest,
            composition_manifest_hash=manifest_hash,
            source_dependency_hash=dependency_hash,
            projection_hash=resolved_projection_hash,
            projection_observed_at=self._clock(),
            replay_address=replay_address,
            payload=payload,
        )


__all__ = [
    "CycleBoardExportResponse",
    "CycleBoardProjectionPacket",
    "CycleBoardProjectionService",
    "CycleBoardReplayConflictError",
    "HistoricalDispositionError",
    "N13BGlobalMovementSignal",
    "load_ds4_realized_disposition",
    "load_historical_producer_availability",
    "load_n13b_global_movement_signal",
    "parse_ds4_realized_disposition",
]
