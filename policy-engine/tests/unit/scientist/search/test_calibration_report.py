from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security import AccessScope, reset_current_access_scope, set_current_access_scope
from polisyos.scientist.methods.search.calibration_report import (
    build_calibration_report,
    load_funnel_calibration_report,
    persist_funnel_calibration_report,
    render_calibration_report,
)
from polisyos.scientist.methods.search.cold_start import BurnInRunReport
from polisyos.scientist.methods.search.lessons import (
    LessonCard,
    LessonKind,
    LessonQuery,
    LessonRegistry,
    LessonTrustLevel,
)
from polisyos.scientist.methods.search.sentinels import SentinelCandidate, SentinelKind, SentinelSet
from polisyos.scientist.methods.search.stages import CorrelationTracker, StageResult
from polisyos.scientist.methods.search.transfer_context import (
    TransferContext,
    TransferScopeRefusalReason,
    TransferScopeRefusedError,
)


def _stage_result(*, score: float, passed: bool, stage_name: str) -> StageResult:
    return StageResult(
        policy_candidate={},
        objective_value=score,
        is_promising=passed,
        stage_name=stage_name,
        predicted_score=score,
        actual_score=score,
    )


def test_calibration_report_builds_from_tracker_lessons_and_burn_in(tmp_path) -> None:
    tracker = CorrelationTracker(drift_window_size=5)
    for index, row in enumerate(
        [
            (0.1, True, 0.9, True),
            (0.2, True, 0.8, True),
            (0.3, True, 0.7, True),
            (0.4, True, 0.6, True),
            (0.5, True, 0.5, True),
        ]
    ):
        tracker.record(
            _stage_result(score=row[0], passed=row[1], stage_name="L2"),
            _stage_result(score=row[2], passed=row[3], stage_name="L4"),
            f"cand-{index}",
        )

    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
    registry.record(
        LessonCard(
            kind=LessonKind.FAILURE,
            summary="Transportability repeatedly breaks for this policy family.",
            failure_type="transport_failure",
            stage_name="funnel_L2_causal",
            fidelity_level=2,
            candidate_hash="cand-transport",
            source_run_id="run-1",
            tags=["transport"],
        )
    )

    sentinel_set = SentinelSet(
        set_id="s1",
        suite_id="bench",
        sentinels=[
            SentinelCandidate(
                sentinel_id="sentinel-a",
                kind=SentinelKind.CALIBRATION,
                candidate={"semantic": {"interventions": [], "objectives": []}},
            )
        ],
        injection_rate=20,
        pass_rate_floor=0.95,
    )
    burn_in_report = BurnInRunReport(
        run_id="burn-in-1",
        cohort_sizes={"calibration": 10, "lesson_seeding": 5},
        baseline_level4_candidates=15,
        actual_level4_candidates=6,
        level4_execution_rate=0.4,
        expensive_stage_load_reduction=0.6,
        false_negative_rate=0.01,
        spearman_correlation=0.7,
        sentinel_pass_rate=1.0,
        degradation_mode="normal",
    )

    report = build_calibration_report(
        correlation_tracker=tracker,
        lesson_registry=registry,
        sentinel_set=sentinel_set,
        burn_in_report=burn_in_report,
    )
    rendered_md = render_calibration_report(report, format="md")

    assert report.top_lessons
    assert "Top Lessons" in rendered_md
    assert report.expensive_stage_load_reduction == 0.6

    ref = persist_funnel_calibration_report(store, report)
    assert ref.manifest_profile_sha256 is not None
    from polisyos.core.artifacts.canonical_profile import read_core_manifest_profile

    manifest, _declaration = read_core_manifest_profile(
        store,
        ref,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )
    assert manifest.kind == "scientist.search.calibration_report"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.version == report.schema_version == "1.1"
    loaded = load_funnel_calibration_report(store, ref)
    assert loaded.current_mode == report.current_mode


def test_calibration_report_marks_gaps_when_inputs_missing() -> None:
    report = build_calibration_report()
    assert "missing_burn_in" in report.gaps
    assert "missing_sentinels" in report.gaps
    assert "insufficient_correlation_window" in report.gaps


def test_calibration_report_keeps_live_and_historical_lesson_grades_distinct(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    root = tmp_path / "registry" / "lessons"
    registry = LessonRegistry(root=root, store=store)
    as_of = datetime.now(UTC)
    source = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Old evidence has limited current applicability.",
        failure_type="transport_failure",
        stage_name="funnel_L2_causal",
        fidelity_level=2,
        candidate_hash="old-candidate",
        source_run_id="historic-run",
        created_at=as_of - timedelta(days=100),
        confidence=0.9,
    )
    card_ref = registry.record(source)
    original_card = store.get_bytes(card_ref)
    snapshot_ref = registry.snapshot_ref()
    assert snapshot_ref is not None
    original_snapshot = store.get_bytes(snapshot_ref)
    strict = LessonQuery(as_of=as_of, min_confidence=0.8, trust_levels=[LessonTrustLevel.LOCAL])
    assert registry.query(strict) == []
    assert registry.query(LessonQuery(as_of=as_of))[0].confidence == 0.5

    report = build_calibration_report(lesson_registry=registry)
    assert report.top_lessons[0].trust_level is LessonTrustLevel.LOW_CONFIDENCE
    report = build_calibration_report(lesson_registry=registry, as_of=as_of)
    pattern = report.top_lessons[0]
    assert pattern.artifact_ref == card_ref
    assert pattern.confidence == 0.5
    assert pattern.historical_confidence == 0.9
    assert pattern.historical_trust_level is LessonTrustLevel.LOCAL
    assert pattern.effective_as_of == as_of
    assert pattern.evidence_anchor == source.created_at
    assert pattern.grade_basis == "current_effective"
    report_json = json.loads(render_calibration_report(report))
    assert report_json["top_lessons"][0]["grade_basis"] == "current_effective"
    assert report_json["top_lessons"][0]["historical_confidence"] == 0.9
    markdown = render_calibration_report(report, format="md")
    assert "effective grade 0.5 / low_confidence" in markdown
    assert "historical grade 0.9 / local" in markdown
    assert source.created_at.isoformat() in markdown

    fresh_store = FileSystemCAS(tmp_path / ".polisyos")
    fresh = LessonRegistry(root=root, store=fresh_store)
    assert fresh.top_patterns(as_of=as_of)[0] == pattern
    report_ref = persist_funnel_calibration_report(store, report)
    reopened_report = load_funnel_calibration_report(fresh_store, report_ref)
    assert reopened_report.top_lessons == [pattern]
    assert json.loads(render_calibration_report(reopened_report)) == report_json
    assert render_calibration_report(reopened_report, format="md") == markdown
    retained = LessonRegistry.load_snapshot(fresh_store, snapshot_ref)
    historical_report = build_calibration_report(lesson_registry=retained, as_of=as_of)
    historical = historical_report.top_lessons[0]
    assert historical.artifact_ref == card_ref
    assert historical.grade_basis == "historical"
    assert historical.confidence == historical.historical_confidence == 0.9
    assert historical.trust_level is historical.historical_trust_level is LessonTrustLevel.LOCAL
    assert historical.effective_as_of is None
    assert "effective grade unavailable" in render_calibration_report(
        historical_report, format="md"
    )
    assert fresh_store.get_bytes(card_ref) == original_card
    assert fresh_store.get_bytes(snapshot_ref) == original_snapshot

    unknown_entry = retained.entries[0].model_copy(
        update={"last_seen": retained.entries[0].last_seen.replace(tzinfo=None)}
    )
    unknown_time = retained.model_copy(update={"entries": [unknown_entry]})
    unavailable = build_calibration_report(lesson_registry=unknown_time, as_of=as_of)
    assert unavailable.top_lessons[0].grade_basis == "historical"
    assert unavailable.top_lessons[0].effective_as_of is None
    assert unavailable.top_lessons[0].evidence_anchor is None
    assert (
        build_calibration_report(
            lesson_registry=retained, as_of=source.created_at - timedelta(seconds=1)
        ).top_lessons
        == []
    )


def test_snapshot_lesson_report_requires_its_effective_access_scope(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
    access = AccessScope.for_service(tenant_id="producer", cell_id=None, spiffe_id="spiffe://test")
    token = set_current_access_scope(access)
    try:
        registry.record(
            LessonCard(
                kind=LessonKind.FAILURE,
                summary="Evidence recorded in the producer tenant.",
                failure_type="transport_failure",
                stage_name="funnel_L2_causal",
                fidelity_level=2,
                candidate_hash="tenant-candidate",
                source_run_id="tenant-run",
            )
        )
        snapshot_ref = registry.snapshot_ref()
        assert snapshot_ref is not None
        snapshot = LessonRegistry.load_snapshot(store, snapshot_ref)
        assert build_calibration_report(lesson_registry=snapshot).top_lessons
    finally:
        reset_current_access_scope(token)

    with pytest.raises(TransferScopeRefusedError) as refusal:
        build_calibration_report(lesson_registry=snapshot)
    assert (
        refusal.value.refusals[0].reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
    )

    assert snapshot.source_scope is not None
    claimed = TransferContext(
        tenant_hash=snapshot.source_scope.tenant_hash,
        tenant_scope_status=snapshot.source_scope.tenant_scope_status,
    )
    with pytest.raises(TransferScopeRefusedError) as refusal:
        build_calibration_report(lesson_registry=snapshot, lesson_context=claimed)
    assert (
        refusal.value.refusals[0].reason is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
    )

    access = AccessScope.for_service(tenant_id="other", cell_id=None, spiffe_id="spiffe://test")
    token = set_current_access_scope(access)
    try:
        with pytest.raises(TransferScopeRefusedError) as refusal:
            build_calibration_report(lesson_registry=snapshot)
        assert (
            refusal.value.refusals[0].reason
            is TransferScopeRefusalReason.CROSS_TENANT_NOT_AUTHORIZED
        )
    finally:
        reset_current_access_scope(token)


def test_legacy_calibration_report_decodes_its_unlabelled_lesson_grade_as_historical(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=store)
    card = LessonCard(
        kind=LessonKind.FAILURE,
        summary="Original authored lesson.",
        failure_type="transport_failure",
        stage_name="funnel_L2_causal",
        fidelity_level=2,
        candidate_hash="legacy-candidate",
        source_run_id="legacy-run",
        confidence=0.9,
    )
    card_ref = registry.record(card)
    legacy_payload = {
        "schema_version": "1.0",
        "current_mode": "normal",
        "top_lessons": [
            {
                "lesson_id": card.lesson_id,
                "artifact_ref": card_ref.model_dump(mode="json"),
                "occurrence_count": 1,
                "kind": card.kind.value,
                "summary": card.summary,
                "failure_type": card.failure_type,
                "stage_name": card.stage_name,
                "fidelity_level": card.fidelity_level,
                "confidence": card.confidence,
                "trust_level": card.trust_level.value,
                "last_seen": card.created_at.isoformat(),
            }
        ],
    }
    legacy_ref = store.put_json(
        legacy_payload,
        PutOptions(
            kind="scientist.search.calibration_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.FunnelCalibrationReport", version="1.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    original_report = store.get_bytes(legacy_ref)

    fresh = FileSystemCAS(tmp_path / ".polisyos")
    report = load_funnel_calibration_report(fresh, legacy_ref)
    assert report.schema_version == "1.0"
    assert "historical grade 0.9 / local" in render_calibration_report(report, format="md")
    assert report.top_lessons[0].grade_basis == "historical"
    assert report.top_lessons[0].effective_as_of is None
    assert fresh.get_bytes(legacy_ref) == original_report

    mislabelled_ref = store.put_json(
        legacy_payload,
        PutOptions(
            kind="scientist.search.calibration_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.FunnelCalibrationReport", version="1.1"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert mislabelled_ref.artifact_id == legacy_ref.artifact_id
    assert mislabelled_ref.manifest_profile_sha256 != legacy_ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="^calibration_report_payload_schema_mismatch$"):
        load_funnel_calibration_report(fresh, mislabelled_ref)
    assert load_funnel_calibration_report(fresh, legacy_ref).schema_version == "1.0"
