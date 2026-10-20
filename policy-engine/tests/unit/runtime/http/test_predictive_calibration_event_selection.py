"""Real fresh-reader selection tests for predictive-calibration publications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.predictive_calibration import (
    PredictiveCalibrationError,
    load_run_predictive_calibration,
)


def _artifact_id(name: str) -> str:
    return "sha256:" + hashlib.sha256(name.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Event:
    event_type: str
    event_source: str
    producer_component: str
    phase: str
    run_id: str
    job_id: str
    tenant_id: str
    cell_id: str
    event_subject: str
    event_id: str
    event_time: str
    artifact_refs: tuple[str, ...]
    input_refs: tuple[str, ...]


@dataclass(frozen=True)
class _Record:
    event: _Event


class _EventLog:
    def __init__(self, events: list[_Event]) -> None:
        self.events = events

    def list_events(self, *, run_id: str, job_id: str, limit: int) -> list[_Record]:
        assert run_id == "run-1"
        assert job_id == "job-1"
        assert limit == 1000
        return [_Record(event) for event in self.events]


def _association_event(
    *,
    event_id: str,
    tenant_id: str = "tenant-1",
    cell_id: str = "cell-1",
    event_type: str = "polisyos.runtime.diagnostic.ref_publication.v1",
    event_source: str = "polisyos.runtime",
    producer_component: str = "polisyos.runtime.http.predictive_calibration",
    phase: str = "predictive_calibration_publication",
    subject_suffix: str = _artifact_id("association"),
    association_ref: str = _artifact_id("association"),
) -> _Event:
    refs = (
        _artifact_id("run-manifest"),
        _artifact_id("candidate"),
        _artifact_id("observed"),
        _artifact_id("model"),
        _artifact_id("policy"),
        _artifact_id("rule"),
        _artifact_id("report"),
        _artifact_id("evidence"),
        _artifact_id("uncertainty"),
    )
    return _Event(
        event_type=event_type,
        event_source=event_source,
        producer_component=producer_component,
        phase=phase,
        run_id="run-1",
        job_id="job-1",
        tenant_id=tenant_id,
        cell_id=cell_id,
        event_subject=(f"run/run-1/job/job-1/predictive-calibration/{subject_suffix}"),
        event_id=event_id,
        event_time=f"2026-10-20T00:00:{event_id[-2:]}Z",
        artifact_refs=(association_ref,),
        input_refs=refs,
    )


def _read(monkeypatch: pytest.MonkeyPatch, events: list[_Event]) -> tuple[Any, Any]:
    import polisyos.runtime.http.services.predictive_calibration as service

    run_ref = ArtifactRef(
        artifact_id=_artifact_id("run-manifest"),
        kind="runtime.run_manifest",
        media_type="application/json",
    )
    association_ref = ArtifactRef(
        artifact_id=_artifact_id("association"),
        kind="runtime.predictive_calibration_association",
        media_type="application/json",
    )
    association = SimpleNamespace(
        schema_version=service._ASSOCIATION_SCHEMA,
        event_id="evt-01",
        event_time="2026-10-20T00:00:01Z",
        created_at="2026-10-20T00:00:01Z",
        run_id="run-1",
        job_id="job-1",
        tenant_id="tenant-1",
        cell_id="cell-1",
        intent_id="intent-1",
        request_sha256="a" * 64,
        run_manifest_ref=run_ref,
        candidate_source_ref=SimpleNamespace(artifact_id=_artifact_id("candidate")),
        observed_source_ref=SimpleNamespace(artifact_id=_artifact_id("observed")),
        model_spec_ref=SimpleNamespace(artifact_id=_artifact_id("model")),
        policy_spec_ref=SimpleNamespace(artifact_id=_artifact_id("policy")),
        calibration_rule_ref=SimpleNamespace(artifact_id=_artifact_id("rule")),
        backtest_report_ref=SimpleNamespace(artifact_id=_artifact_id("report")),
        empirical_evidence_ref=SimpleNamespace(artifact_id=_artifact_id("evidence")),
        uncertainty_bundle_ref=SimpleNamespace(artifact_id=_artifact_id("uncertainty")),
        value_data_profile_ref=None,
        forecast_profile_member_ref=None,
    )
    event_log = _EventLog(events)
    monkeypatch.setattr(service, "_require_event_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_selected_run_manifest", lambda _details: run_ref)
    monkeypatch.setattr(service, "_require_event_log_owner", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        service,
        "_read_event_payload",
        lambda _store, record: {
            "schema_version": service._ASSOCIATION_VERSION,
            "association_ref": association_ref.model_dump(mode="json"),
            "intent_id": "intent-1",
            "request_sha256": "a" * 64,
        }
        if record.event.event_id == "evt-01"
        else pytest.fail("the unrelated event was selected"),
    )
    monkeypatch.setattr(service, "_load_association", lambda _store, _ref: association)
    monkeypatch.setattr(
        service, "_association_event_version", lambda _schema: service._ASSOCIATION_VERSION
    )
    monkeypatch.setattr(service, "_validate_current_run_binding", lambda *args, **kwargs: None)
    run = SimpleNamespace(
        details=SimpleNamespace(
            run_id="run-1",
            control_job_id="job-1",
            tenant_id="tenant-1",
            cell_id="cell-1",
        )
    )
    result = load_run_predictive_calibration(
        store=object(),
        run=run,
        event_log=event_log,
        event_scope={},
    )
    return result, association_ref


def test_fresh_reader_ignores_later_same_producer_publication_for_other_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _association_event(event_id="evt-01")
    unrelated = _association_event(
        event_id="evt-99",
        subject_suffix=_artifact_id("unrelated"),
        association_ref=_artifact_id("unrelated"),
    )

    result, association_ref = _read(monkeypatch, [original, unrelated])

    assert result[0] == association_ref
    assert result[1].event_id == original.event_id


def test_fresh_reader_selects_same_identity_from_wrong_scope_then_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _association_event(event_id="evt-02", tenant_id="tenant-other")
    run = SimpleNamespace(
        details=SimpleNamespace(
            run_id="run-1",
            control_job_id="job-1",
            tenant_id="tenant-1",
            cell_id="cell-1",
        )
    )
    import polisyos.runtime.http.services.predictive_calibration as service

    event_log = _EventLog([event])
    run_ref = ArtifactRef(
        artifact_id=_artifact_id("run-manifest"),
        kind="runtime.run_manifest",
        media_type="application/json",
    )
    monkeypatch.setattr(service, "_require_event_scope", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_selected_run_manifest", lambda _details: run_ref)
    monkeypatch.setattr(service, "_require_event_log_owner", lambda *args, **kwargs: None)

    with pytest.raises(PredictiveCalibrationError) as refusal:
        load_run_predictive_calibration(
            store=object(), run=run, event_log=event_log, event_scope={}
        )

    assert refusal.value.code == "predictive_calibration_event_scope_mismatch"
