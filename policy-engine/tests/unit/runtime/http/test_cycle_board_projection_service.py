from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from polisyos.runtime.http.services.cycle_board_projection import (
    CycleBoardProjectionService,
    N13BGlobalMovementSignal,
    load_ds4_realized_disposition,
    load_historical_producer_availability,
    load_n13b_global_movement_signal,
)

from polisyos.core.contracts.runtime import RunSummary
from polisyos.core.trace.record import RunTerminality
from polisyos.runtime.http.services.governed_projections import (
    ArtifactMissingGovernedProjectionPacket,
    AudienceClass,
    AvailableGovernedProjectionPacket,
    DepthNAcquisitionRouteProjection,
    DepthNCycleBoardPayload,
    DepthNDomainRunProjection,
    InvalidGovernedProjectionPacket,
    LegacyProvingGroundPayload,
    N13AAcquisitionCensusPayload,
    N13ALiveProbeJournalPayload,
    ProjectionAvailability,
    ProjectionFreshness,
    ProjectionId,
    ProjectionSourceIdentity,
    ProjectionSourceValidation,
    ProvingGroundFixtureIdentity,
    ProvingGroundFixtureRecord,
    ProvingGroundRuntimeOutcomes,
    ReplayPinMismatchError,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
OBSERVED_AT = datetime(2026, 8, 20, 12, tzinfo=UTC)
N10_ORDER = ("first_vertical", "education", "unseen")
N10_SOURCE = json.loads(
    (
        REPO_ROOT
        / "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
    ).read_text(encoding="utf-8")
)


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _freshness(state: str = "observed") -> ProjectionFreshness:
    return ProjectionFreshness(
        state=state,
        basis="source_timestamp" if state != "artifact_missing" else "request_observation",
        observed_at=OBSERVED_AT,
        source_as_of=OBSERVED_AT if state != "artifact_missing" else None,
    )


def _source(projection_id: ProjectionId, *, passed: bool = True) -> ProjectionSourceIdentity:
    content_hash = _digest({"source": projection_id.value})
    return ProjectionSourceIdentity(
        relative_path=f"fixtures/{projection_id.value}.json",
        artifact_content_hash=content_hash,
        validation=ProjectionSourceValidation(
            validator_id="fixture.owner",
            validator_version="1",
            status="passed" if passed else "failed",
            bound_artifact_content_hash=content_hash,
            bound_dependency_aggregate_identity=_digest({"dependency": projection_id.value}),
            bound_dependency_count=1 if passed else 0,
            semantic_projection_hash=_digest({"semantic": projection_id.value}) if passed else None,
            semantic_projection_hash_rule_version="fixture.v1" if passed else None,
            issue_codes=() if passed else ("fixture_invalid",),
        ),
    )


def _available(
    projection_id: ProjectionId,
    payload: Any,
) -> AvailableGovernedProjectionPacket:
    projection_hash = _digest(payload.model_dump(mode="json"))
    source = _source(projection_id)
    return AvailableGovernedProjectionPacket(
        projection_id=projection_id,
        availability=ProjectionAvailability.AVAILABLE,
        intended_audience=AudienceClass.MACHINE,
        authoritative_for=("fixture_fact",),
        may_not_use_for=("mint_authority",),
        source=source,
        source_dependency_hash=_digest({"dependency": projection_hash}),
        projection_hash=projection_hash,
        replay_address=f"/projection/{projection_id.value}?projection_hash={projection_hash}",
        as_of=OBSERVED_AT,
        freshness=_freshness(),
        stable_address=f"/projection/{projection_id.value}",
        payload=payload,
    )


def _artifact_missing(projection_id: ProjectionId, *, reason: str = "fixture absent"):
    return ArtifactMissingGovernedProjectionPacket(
        projection_id=projection_id,
        availability=ProjectionAvailability.ARTIFACT_MISSING,
        intended_audience=AudienceClass.MACHINE,
        authoritative_for=(),
        may_not_use_for=("mint_authority",),
        as_of=OBSERVED_AT,
        freshness=_freshness("artifact_missing"),
        stable_address=f"/projection/{projection_id.value}",
        absence_reason=reason,
    )


def _invalid(projection_id: ProjectionId, *, reason: str = "fixture invalid"):
    return InvalidGovernedProjectionPacket(
        projection_id=projection_id,
        availability=ProjectionAvailability.INVALID_SOURCE,
        intended_audience=AudienceClass.MACHINE,
        authoritative_for=(),
        may_not_use_for=("mint_authority",),
        source=_source(projection_id, passed=False),
        as_of=OBSERVED_AT,
        freshness=_freshness("invalid_source"),
        stable_address=f"/projection/{projection_id.value}",
        absence_reason=reason,
    )


def _route(role: str, *, cost: float | None = None, voi: float | None = None):
    return DepthNAcquisitionRouteProjection(
        owner="polisyos.runtime.quality.acquisition_planner",
        route_kind="n7_requirement_gap",
        planner_report_content_hash=_digest({"planner": role}),
        planner_status="pass",
        requirement_gap_id=f"requirement-gap:{role}",
        missing_requirement_fields=(f"grounding_relation_or_owner_lever:{role}",),
        recommended_strategy="production_snapshot_build",
        expected_cost=cost,
        expected_voi=voi,
        voi_rank=1 if voi is not None else None,
        decision_owner_ref="polisyos.runtime.quality.acquisition_planner",
        producer_expected="data_forge.snapshot",
        next_action="build_production_snapshot",
    )


def _depth_payload() -> DepthNCycleBoardPayload:
    evidence = {
        "first_vertical": "owner_acquisition_route",
        "education": "estimand_binding_refusal",
        "unseen": "owner_acquisition_route",
    }
    return DepthNCycleBoardPayload(
        depth_evidence={"observed_max_depth": 3},
        domain_runs={
            role: DepthNDomainRunProjection(
                generation_cycle_run_id=f"cycle-{role}",
                design_problem_ref=N10_SOURCE["domain_runs"][role]["design_problem_ref"],
                design_problem=N10_SOURCE["domain_runs"][role]["design_problem"],
                domain_role=role,
                search_terminal_kind=f"search-terminal-{role}",
                terminal_distribution={
                    "count": 1,
                    "decision_grade": "blocked",
                    "evidence_kind": evidence[role],
                    "terminal_kind": f"search-terminal-{role}",
                },
                evidence_class=evidence[role],
                evidence_witness={"kind": evidence[role]},
                weakest_links=(f"weakest-{role}-1", f"weakest-{role}-2"),
                acquisition_route=_route(
                    role,
                    cost=12.5 if role == "first_vertical" else None,
                    voi=4.0 if role == "first_vertical" else None,
                ),
            )
            for role in N10_ORDER
        },
        terminal_distributions={},
    )


def _n13a_payload(*, adjacent_count: int = 10):
    kinds = {
        "first_vertical": "owner_acquisition_route",
        "education": "estimand_binding_refusal",
        "unseen": "owner_acquisition_route",
    }
    return N13AAcquisitionCensusPayload(
        catalog_identity={"table_row_counts": {"ds_observations": adjacent_count}},
        projection_bindings=(),
        family_scorecards=(),
        metric_resolutions=(),
        route_evidence=tuple(
            {
                "declared_supply": {"adjacent_observation_count": adjacent_count},
                "route_class": "not_a_data_gap",
                "row_addressable_supply": {"count": adjacent_count},
                "route": {
                    "domain_role": role,
                    "missing_link": (
                        "method_estimand_binding_mismatch"
                        if role == "education"
                        else f"grounding_relation_or_owner_lever:{role}"
                    ),
                    "planner_strategy_kind": "production_snapshot_build",
                    "requirement_gap_id": f"requirement-gap:{role}",
                    "witness_kind": kinds[role],
                },
            }
            for role in N10_ORDER
        ),
        growth_backlog=(),
        fetch_plan_generation={},
        reverse_demand_residuals=(),
    )


def _journal_payload() -> N13ALiveProbeJournalPayload:
    return N13ALiveProbeJournalPayload(selection_plan={}, family_receipts=(), records=())


def _legacy_payload_from_corpus() -> LegacyProvingGroundPayload:
    root = REPO_ROOT / "tests/fixtures/universal-corpus"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    identities = []
    records = []
    for entry in manifest["fixtures"]:
        identities.append(
            ProvingGroundFixtureIdentity.model_validate(
                {key: entry[key] for key in ProvingGroundFixtureIdentity.model_fields}
            )
        )
        raw = json.loads((root / entry["path"]).read_text(encoding="utf-8"))
        records.append(
            ProvingGroundFixtureRecord.model_validate(
                {key: raw[key] for key in ProvingGroundFixtureRecord.model_fields}
            )
        )
    return LegacyProvingGroundPayload(
        fixture_identities=tuple(identities),
        fixture_records=tuple(records),
        runtime_outcomes=ProvingGroundRuntimeOutcomes(
            reason="no persisted validator-confirmed 13-case runtime result is named"
        ),
    )


def _component_packets(
    *,
    depth: DepthNCycleBoardPayload | None = None,
    n13a: N13AAcquisitionCensusPayload | None = None,
    n13a_state: str = "available",
    readiness_reason: str = "Revision-3 readiness owner artifact is absent",
) -> dict[ProjectionId, Any]:
    n13a_packet = (
        _available(ProjectionId.N13A_ACQUISITION_CENSUS, n13a or _n13a_payload())
        if n13a_state == "available"
        else _invalid(ProjectionId.N13A_ACQUISITION_CENSUS)
    )
    return {
        ProjectionId.DEPTH_N_CYCLE_BOARD: _available(
            ProjectionId.DEPTH_N_CYCLE_BOARD, depth or _depth_payload()
        ),
        ProjectionId.N13A_ACQUISITION_CENSUS: n13a_packet,
        ProjectionId.N13A_LIVE_PROBE_JOURNAL: _available(
            ProjectionId.N13A_LIVE_PROBE_JOURNAL, _journal_payload()
        ),
        ProjectionId.LEGACY_PROVING_GROUND: _available(
            ProjectionId.LEGACY_PROVING_GROUND, _legacy_payload_from_corpus()
        ),
        ProjectionId.SURFACE_READINESS: _artifact_missing(
            ProjectionId.SURFACE_READINESS, reason=readiness_reason
        ),
    }


class _RawProjectionStub:
    def __init__(self, packets: dict[ProjectionId, Any]) -> None:
        self.packets = packets
        self.calls: list[tuple[ProjectionId, dict[str, Any]]] = []

    def get(self, projection_id: ProjectionId, **pins: Any):
        self.calls.append((projection_id, pins))
        packet = self.packets[projection_id]
        actual_by_pin = {
            "artifact_content_hash": (
                packet.source.artifact_content_hash if packet.source is not None else None
            ),
            "projection_hash": packet.projection_hash,
            "source_dependency_hash": packet.source_dependency_hash,
            "source_as_of": packet.as_of,
        }
        for field, expected in pins.items():
            if expected is not None and actual_by_pin[field] != expected:
                raise ReplayPinMismatchError(
                    field,
                    expected=str(expected),
                    actual=str(actual_by_pin[field]),
                )
        return packet


class _RunIndexStub:
    def __init__(self, summaries: dict[str, object] | None = None) -> None:
        self.summaries = summaries or {}
        self.requested: list[str] = []

    def get_run(self, run_id: str):
        self.requested.append(run_id)
        if run_id not in self.summaries:
            raise KeyError(run_id)
        return SimpleNamespace(summary=self.summaries[run_id])

    def list_runs(self, *_args: object, **_kwargs: object):
        raise AssertionError("the board may not enumerate /runs or /runs/nl shadow jobs")


def _summary(
    run_id: str,
    terminality: RunTerminality,
    *,
    status: str = "opaque-status",
    finished_at: datetime | None = None,
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        source_kind="core_run",
        status=status,
        run_terminality=terminality,
        finished_at=finished_at,
    )


def _service(
    packets: dict[ProjectionId, Any] | None = None,
    summaries: dict[str, object] | None = None,
    n13b_global_signal: N13BGlobalMovementSignal | None = None,
):
    raw = _RawProjectionStub(packets or _component_packets())
    index = _RunIndexStub(summaries)
    service = CycleBoardProjectionService(
        projection_service=raw,
        run_index=index,
        repository_root=REPO_ROOT,
        clock=lambda: OBSERVED_AT,
        n13b_global_signal=n13b_global_signal,
    )
    return service, raw, index


def _row(packet: Any, role: str):
    return next(row for row in packet.payload.rows if row.domain_role == role)


def _assert_composed_route_equals_owner(row: Any, owner_route: Any) -> None:
    composed = row.acquisition_route.value
    for field in (
        "owner",
        "route_kind",
        "planner_report_content_hash",
        "planner_status",
        "requirement_gap_id",
        "missing_requirement_fields",
        "recommended_strategy",
        "decision_owner_ref",
        "producer_expected",
        "next_action",
    ):
        assert getattr(composed, field) == getattr(owner_route, field)
    for field in ("expected_cost", "expected_voi", "voi_rank"):
        fact = getattr(composed, field)
        owner_value = getattr(owner_route, field)
        if owner_value is None:
            assert fact.availability == "not_established"
            assert "value" not in fact.model_dump()
        else:
            assert fact.availability == "available"
            assert fact.value == owner_value
    assert composed.execution_status.availability == "not_established"
    assert "value" not in composed.execution_status.model_dump()


def test_known_cohorts_are_owner_ordered_non_exhaustive_and_exclude_run_list_jobs() -> None:
    depth = _depth_payload()
    service, raw, index = _service(
        packets=_component_packets(depth=depth),
        summaries={
            "nl-shadow-terminal-job": _summary(
                "nl-shadow-terminal-job", RunTerminality.TERMINAL, status="finished"
            )
        }
    )

    packet = service.get()
    rows = packet.payload.rows
    legacy = _legacy_payload_from_corpus()
    legacy_ids = [item.case_id for item in legacy.fixture_identities]

    assert len(legacy.fixture_identities) == 13
    assert [row.domain_role for row in rows[:3]] == list(N10_ORDER)
    assert [row.row_id for row in rows[3:]] == legacy_ids
    assert len(rows) == len(N10_ORDER) + len(legacy.fixture_records)
    for role in N10_ORDER:
        row = _row(packet, role)
        owner_run = depth.domain_runs[role]
        assert row.design_problem.availability == "available"
        assert row.design_problem.value == owner_run.design_problem
        _assert_composed_route_equals_owner(row, owner_run.acquisition_route)
    coverage = packet.payload.coverage
    assert coverage.capability_state == "absent/unallocated"
    assert coverage.deficits == ("artifact_missing", "bridge_missing")
    assert coverage.owner_route == "GY-GAP5 -> runtime/quality GY-N12"
    assert coverage.execution_status == "not_established"
    assert coverage.known_scope == "N10 capstone + legacy fixture cohort"
    assert coverage.unknown_scope == "future production recursive-cycle DesignProblems"
    assert coverage.known_row_count == len(rows)
    assert coverage.exhaustive is False
    assert coverage.missing_link == "production_recursive_cycle_run_enumeration"
    assert set(index.requested) == {f"cycle-{role}" for role in N10_ORDER}
    assert Counter(call[0] for call in raw.calls) == Counter(
        {
            ProjectionId.DEPTH_N_CYCLE_BOARD: 1,
            ProjectionId.N13A_ACQUISITION_CENSUS: 1,
            ProjectionId.N13A_LIVE_PROBE_JOURNAL: 1,
            ProjectionId.LEGACY_PROVING_GROUND: 1,
            ProjectionId.SURFACE_READINESS: 1,
        }
    )
    movement = packet.payload.movement_gap
    assert movement.capability_state == "absent/unallocated"
    assert movement.deficits == ("artifact_missing", "bridge_missing")
    assert movement.producer_route == "GY-GAP6 -> GY-N13b"
    assert movement.chronology_route == "GY-N12"
    assert movement.execution_status == "not_established"
    assert movement.movement_records == ()
    assert all(row.movement_records == () for row in rows)
    assert all(row.cohort == "legacy_fixture" for row in rows[3:])
    for row in rows[:3]:
        assert row.stage_trace_href.availability == "not_established"
        assert "DS8" in row.stage_trace_href.owner_route
        assert "value" not in row.stage_trace_href.model_dump()
    for row in rows:
        assert row.surface_readiness.availability == "artifact_missing"
        assert "value" not in row.surface_readiness.model_dump()
    for row in rows[3:]:
        for field in (
            row.design_problem,
            row.search_terminal_kind,
            row.lifecycle_terminality,
            row.structural_evidence_class,
            row.weakest_links,
            row.missing_link,
            row.acquisition_route,
            row.stage_trace_href,
        ):
            assert field.availability == "artifact_missing"
            assert "value" not in field.model_dump()


def _structural_region(packet: Any) -> list[dict[str, Any]]:
    return [
        {
            "row_id": row.row_id,
            "evidence": row.structural_evidence_class.model_dump(mode="json"),
            "weakest": row.weakest_links.model_dump(mode="json"),
            "missing": row.missing_link.model_dump(mode="json"),
            "route": row.acquisition_route.model_dump(mode="json"),
            "movement": list(row.movement_records),
        }
        for row in packet.payload.rows[:3]
    ]


def _enumeration_region(packet: Any) -> dict[str, Any]:
    return {
        "ordered_row_ids": tuple(row.row_id for row in packet.payload.rows),
        "coverage": packet.payload.coverage.model_dump(mode="json"),
        "movement_gap": packet.payload.movement_gap.model_dump(mode="json"),
    }


def test_adjacent_counts_and_n13b_control_plane_signal_cannot_mint_structural_progress() -> None:
    n13b = load_n13b_global_movement_signal(REPO_ROOT)
    assert n13b.demonstration_status == "typed_deeper_terminal"
    mutated_n13b = N13BGlobalMovementSignal.model_validate(
        {
            **n13b.model_dump(mode="json"),
            "demonstration_status": "global_result_changed_without_row_binding",
            "source_content_hash": _digest(
                {
                    "source": n13b.source_ref,
                    "demonstration_status": "global_result_changed_without_row_binding",
                }
            ),
        }
    )
    baseline, _, _ = _service(n13b_global_signal=n13b)
    inflated, _, _ = _service(
        packets=_component_packets(n13a=_n13a_payload(adjacent_count=3_700_000)),
        n13b_global_signal=n13b,
    )
    changed_signal, _, _ = _service(
        n13b_global_signal=mutated_n13b,
    )

    baseline_packet = baseline.get()
    inflated_packet = inflated.get()
    changed_signal_packet = changed_signal.get()

    assert _structural_region(inflated_packet) == _structural_region(baseline_packet)
    assert _structural_region(changed_signal_packet) == _structural_region(baseline_packet)
    assert _enumeration_region(inflated_packet) == _enumeration_region(baseline_packet)
    assert _enumeration_region(changed_signal_packet) == _enumeration_region(baseline_packet)
    baseline_n13b_sources = [
        entry
        for entry in baseline_packet.composition_manifest
        if entry.source_id == "n13b-global-deeper-terminal"
    ]
    changed_n13b_sources = [
        entry
        for entry in changed_signal_packet.composition_manifest
        if entry.source_id == "n13b-global-deeper-terminal"
    ]
    assert len(baseline_n13b_sources) == len(changed_n13b_sources) == 1
    baseline_n13b_source = baseline_n13b_sources[0]
    changed_n13b_source = changed_n13b_sources[0]
    assert baseline_n13b_source.source_kind == "control_plane_evidence"
    assert baseline_n13b_source.availability == "available"
    assert baseline_n13b_source.artifact_content_hash == n13b.source_content_hash
    assert baseline_n13b_source.authoritative_for == ("global_demonstration_status",)
    assert baseline_n13b_source.may_not_use_for == (
        "per_row_movement",
        "row_enumeration",
        "exhaustiveness",
    )
    assert changed_n13b_source.artifact_content_hash == mutated_n13b.source_content_hash
    assert changed_signal_packet.composition_manifest_hash != (
        baseline_packet.composition_manifest_hash
    )
    assert changed_signal_packet.source_dependency_hash != baseline_packet.source_dependency_hash
    assert all(row.movement_records == () for row in changed_signal_packet.payload.rows)
    gap = inflated_packet.payload.movement_gap
    assert gap.capability_state == "absent/unallocated"
    assert gap.deficits == ("artifact_missing", "bridge_missing")
    assert gap.producer_route == "GY-GAP6 -> GY-N13b"
    assert gap.chronology_route == "GY-N12"
    assert gap.execution_status == "not_established"
    assert gap.movement_records == ()
    assert gap.missing_link == "acquisition_reentry_deeper_terminal_binding"
    first = _row(baseline_packet, "first_vertical")
    assert first.acquisition_route.value.expected_cost.value == 12.5
    assert first.acquisition_route.value.expected_voi.value == 4.0
    education = _row(baseline_packet, "education")
    assert education.acquisition_route.value.expected_cost.availability == "not_established"
    assert "value" not in education.acquisition_route.value.expected_cost.model_dump()
    assert education.acquisition_route.value.execution_status.availability == "not_established"


def test_component_absence_states_and_historical_environment_measurement_stay_separate() -> None:
    service, raw, index = _service(packets=_component_packets(n13a_state="invalid"))

    packet = service.get()
    manifest = tuple(packet.composition_manifest)
    manifest_by_id = {entry.source_id: entry for entry in manifest}
    expected_governed_ids = tuple(projection_id.value for projection_id in raw.packets)
    expected_lifecycle_ids = tuple(f"run-summary:cycle-{role}" for role in N10_ORDER)
    expected_source_ids = (
        *expected_governed_ids,
        "n13b-global-deeper-terminal",
        "ds4-realized-disposition",
        "historical-producer-availability",
        *expected_lifecycle_ids,
    )
    assert tuple(entry.source_id for entry in manifest) == expected_source_ids
    assert len(manifest_by_id) == len(manifest)
    governed_states = {
        entry.source_id: entry.availability
        for entry in manifest
        if entry.source_kind == "governed_projection"
    }
    history = load_historical_producer_availability(REPO_ROOT)
    ds4 = load_ds4_realized_disposition(REPO_ROOT)
    n13b = load_n13b_global_movement_signal(REPO_ROOT)
    owner_text = (
        REPO_ROOT / "docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"Producer availability denominator \| DS3 measured (\d+) available / "
        r"(\d+) `invalid_source` / (\d+) `artifact_missing` from a worktree WITHOUT "
        r"`production_data`",
        owner_text,
    )
    assert match is not None
    expected_history = {
        "available": int(match.group(1)),
        "invalid_source": int(match.group(2)),
        "artifact_missing": int(match.group(3)),
    }

    assert governed_states == {
        ProjectionId.DEPTH_N_CYCLE_BOARD.value: "available",
        ProjectionId.N13A_ACQUISITION_CENSUS.value: "invalid_source",
        ProjectionId.N13A_LIVE_PROBE_JOURNAL.value: "available",
        ProjectionId.LEGACY_PROVING_GROUND.value: "available",
        ProjectionId.SURFACE_READINESS.value: "artifact_missing",
    }
    for projection_id, raw_packet in raw.packets.items():
        entry = manifest_by_id[projection_id.value]
        assert entry.availability == raw_packet.availability.value
        assert entry.artifact_content_hash == (
            raw_packet.source.artifact_content_hash if raw_packet.source is not None else None
        )
        assert entry.source_dependency_hash == getattr(
            raw_packet, "source_dependency_hash", None
        )
        assert entry.as_of == raw_packet.as_of
        assert entry.freshness == raw_packet.freshness
    n13b_entry = manifest_by_id["n13b-global-deeper-terminal"]
    assert n13b_entry.artifact_content_hash == n13b.source_content_hash
    assert n13b_entry.as_of is None
    assert n13b_entry.freshness is None
    ds4_entry = manifest_by_id["ds4-realized-disposition"]
    assert ds4_entry.source_kind == "historical_owner_record"
    assert ds4_entry.artifact_content_hash == ds4.source_content_hash
    assert ds4_entry.as_of is None
    assert ds4_entry.freshness is None
    history_entry = manifest_by_id["historical-producer-availability"]
    assert history_entry.source_kind == "historical_owner_record"
    assert history_entry.artifact_content_hash == history.source_content_hash
    assert history_entry.as_of is None
    assert history_entry.freshness is None
    assert tuple(index.requested) == tuple(f"cycle-{role}" for role in N10_ORDER)
    for source_id in expected_lifecycle_ids:
        entry = manifest_by_id[source_id]
        assert entry.source_kind == "run_summary_lookup"
        assert entry.availability == "not_established"
        assert entry.artifact_content_hash is None
        assert entry.source_dependency_hash is None
        assert entry.as_of is None
        assert entry.freshness is None
        assert entry.authoritative_for == ("run_lifecycle_terminality",)
        assert entry.may_not_use_for == (
            "status_proxy",
            "time_proxy",
            "search_terminal_proxy",
        )
    assert dict(history.counts) == expected_history
    assert sum(history.counts.values()) == sum(expected_history.values())
    assert packet.payload.historical_producer_availability == history
    assert history.measurement_scope == "environment_relative"
    assert history.environment_absence == "production_data"
    assert "as_of" not in type(packet).model_fields
    assert "freshness" not in type(packet).model_fields
    assert packet.projection_observed_at == OBSERVED_AT

    invalid_readiness_packets = _component_packets()
    invalid_readiness_packets[ProjectionId.SURFACE_READINESS] = _invalid(
        ProjectionId.SURFACE_READINESS,
        reason="present readiness owner is semantically invalid",
    )
    invalid_readiness_service, _, _ = _service(packets=invalid_readiness_packets)
    for row in invalid_readiness_service.get().payload.rows:
        assert row.surface_readiness.availability == "invalid_source"
        assert "value" not in row.surface_readiness.model_dump()
