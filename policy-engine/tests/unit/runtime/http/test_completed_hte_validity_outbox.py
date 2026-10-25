"""Prove completed HTE validity intents use the bounded control outbox."""

from __future__ import annotations

import pytest

from polisyos.runtime.http.services.control_plane_store import (
    _COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
    ControlPlaneStore,
)


def test_completed_hte_validity_page_is_topic_scoped_and_freezes_arrivals(tmp_path) -> None:
    """Unrelated rows cannot starve a frozen HTE source-update page."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    for index in range(130):
        store.enqueue_outbox_event(
            topic="control.search.hte_completed",
            event_key=f"search-before:{index}",
            job_id=f"search-before-{index}",
            run_id=f"search-before-run-{index}",
            payload={"completed_event_id": index},
        )
    original = [
        store.enqueue_outbox_event(
            topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
            event_key=f"job-{index}:job_completed:{index + 1}",
            job_id=f"job-{index}",
            run_id=f"run-{index}",
            payload={"completed_event_id": index + 1},
        )
        for index in range(30)
    ]
    for index in range(130):
        store.enqueue_outbox_event(
            topic="control.search.hte_completed",
            event_key=f"search-after:{index}",
            job_id=f"search-after-{index}",
            run_id=f"search-after-run-{index}",
            payload={"completed_event_id": 1_000 + index},
        )
    watermark = store.get_outbox_topic_delivery_watermark(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC
    )
    search_watermark = store.get_outbox_topic_delivery_watermark(
        topic="control.search.hte_completed"
    )
    assert 0 < watermark < search_watermark
    first_page = store.list_pending_outbox_topic_delivery_page(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        limit=25,
        through_sequence_id=watermark,
    )
    assert [row.event_id for _, row in first_page] == [row.event_id for row in original[:25]]

    arrival = store.enqueue_outbox_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key="arrival:job_completed:31",
        job_id="arrival",
        run_id="arrival-run",
        payload={"completed_event_id": 31},
    )
    last_sequence = first_page[-1][0]
    second_page = store.list_pending_outbox_topic_delivery_page(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        limit=25,
        after_sequence_id=last_sequence,
        through_sequence_id=watermark,
    )
    assert [row.event_id for _, row in second_page] == [row.event_id for row in original[25:]]
    assert arrival.event_id not in {row.event_id for _, row in (*first_page, *second_page)}


def test_completed_hte_validity_intent_dedupes_only_identical_binding(tmp_path) -> None:
    """An unchanged replay reuses its intent; a changed binding cannot alias it."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    first = store.enqueue_outbox_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key="job-a:job_completed:17",
        job_id="job-a",
        run_id="run-a",
        payload={"completed_event_id": 17, "attempt": 1},
    )
    replay = store.enqueue_outbox_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key="job-a:job_completed:17",
        job_id="job-a",
        run_id="run-a",
        payload={"completed_event_id": 17, "attempt": 1},
    )
    assert replay.event_id == first.event_id
    with pytest.raises(ValueError, match="completed_hte_validity_outbox_immutable_conflict"):
        store.enqueue_outbox_event(
            topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
            event_key="job-a:job_completed:17",
            job_id="job-a",
            run_id="run-a",
            payload={"completed_event_id": 17, "attempt": 2},
        )


def _completed_hte_validity_request():
    """Build one immutable HTE-source invalidation request for the wire boundary."""
    from datetime import UTC, datetime

    from polisyos.core.contracts.control import DecisionValidityEventRequest
    from polisyos.core.contracts.decision_validity import (
        DecisionTriggerType,
        DecisionValidityStatus,
    )

    return DecisionValidityEventRequest(
        trigger_type=DecisionTriggerType.METRIC_INVALIDATION,
        status=DecisionValidityStatus.STALE,
        reason="completed_hte_source_owner_selection_updated",
        dependency_keys=["hte_completed_source_run:run-17"],
        source_ref=f"control-job-event:job-17:17:sha256:{'a' * 64}",
        dedupe_key="completed-hte-validity:job-17:run-17:attempt-1",
        occurred_at=datetime(2026, 10, 23, 12, 34, 56, tzinfo=UTC),
        payload={
            "source_run_id": "run-17",
            "source_job_id": "job-17",
            "source_attempt": 1,
            "completed_event_id": 17,
            "completed_event_payload_sha256": f"sha256:{'a' * 64}",
        },
    )


def _persisted_completed_hte_delivery(
    tmp_path, request, *, payload=None, run_id=None, event_key=None
):
    """Persist and reopen one HTE validity outbox row through SQLite."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    job_id = "job-17"
    source_run_id = run_id or "run-17"
    selected_payload = payload if payload is not None else request.model_dump(mode="json")
    row = store.enqueue_outbox_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key=event_key or f"{job_id}:job_completed:17",
        job_id=job_id,
        run_id=source_run_id,
        payload=selected_payload,
    )
    delivery = store.get_outbox_topic_event(
        topic=_COMPLETED_HTE_VALIDITY_OUTBOX_TOPIC,
        event_key=row.event_key,
        job_id=job_id,
    )
    assert delivery is not None
    return store, delivery


def _deliver_with_owner_request(store, request, delivery):
    """Invoke the production outbox consumer with only its owned collaborators."""
    from types import SimpleNamespace

    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    published = []
    service = SimpleNamespace(
        _control_store=store,
        _completed_hte_source_validity_request=lambda *, job_id: request,
        _completed_hte_source_validity_event_id=(
            ControlPlaneService._completed_hte_source_validity_event_id
        ),
        publish_decision_validity_event=lambda event, *, event_id: published.append(
            (event, event_id)
        ),
    )
    delivered = ControlPlaneService._deliver_completed_hte_source_validity_outbox(
        service,
        delivery,
    )
    return delivered, published


def test_completed_hte_validity_reader_publishes_persisted_json_wire_request(
    tmp_path,
) -> None:
    """The durable JSON request is strictly decoded before the existing consumer publishes."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    request = _completed_hte_validity_request()
    store, delivery = _persisted_completed_hte_delivery(tmp_path, request)
    assert delivery.payload["trigger_type"] == "metric_invalidation"
    assert delivery.payload["status"] == "stale"
    assert isinstance(delivery.payload["occurred_at"], str)

    delivered, published = _deliver_with_owner_request(store, request, delivery)

    assert delivered, store.get_outbox_event(delivery.event_id)
    assert published == [
        (
            request,
            ControlPlaneService._completed_hte_source_validity_event_id(
                dedupe_key=request.dedupe_key or ""
            ),
        )
    ]
    persisted = store.get_outbox_event(delivery.event_id)
    assert persisted is not None
    assert persisted.state == "published"
    assert persisted.error_message is None


@pytest.mark.parametrize(
    ("variant", "expected_error"),
    [
        ("extra-field", "completed_hte_validity_outbox_payload_invalid"),
        ("invalid-enum", "completed_hte_validity_outbox_payload_invalid"),
        ("mixed-intake-arms", "completed_hte_validity_outbox_payload_invalid"),
        (
            "owner-payload-mismatch",
            "completed_hte_validity_outbox_payload_owner_mismatch",
        ),
        ("owner-run-mismatch", "completed_hte_validity_source_not_established"),
        ("event-key-mismatch", "completed_hte_validity_outbox_payload_owner_mismatch"),
    ],
)
def test_completed_hte_validity_reader_keeps_bad_or_unowned_rows_pending(
    tmp_path,
    variant,
    expected_error,
) -> None:
    """Malformed-present and mismatched owner rows cannot reach the publisher."""
    request = _completed_hte_validity_request()
    payload = request.model_dump(mode="json")
    run_id = "run-17"
    event_key = "job-17:job_completed:17"
    if variant == "extra-field":
        payload["unexpected"] = "field"
    elif variant == "invalid-enum":
        payload["status"] = "publishable"
    elif variant == "mixed-intake-arms":
        payload["monitor_event_ref"] = {
            "artifact_id": f"sha256:{'b' * 64}",
            "kind": "core.test_artifact",
            "media_type": "application/json",
        }
    elif variant == "owner-payload-mismatch":
        payload["payload"]["source_run_id"] = "run-other"
    elif variant == "owner-run-mismatch":
        run_id = "run-other"
    elif variant == "event-key-mismatch":
        event_key = "job-17:job_completed:18"
    store, delivery = _persisted_completed_hte_delivery(
        tmp_path,
        request,
        payload=payload,
        run_id=run_id,
        event_key=event_key,
    )

    delivered, published = _deliver_with_owner_request(store, request, delivery)

    assert delivered is False
    assert published == []
    persisted = store.get_outbox_event(delivery.event_id)
    assert persisted is not None
    assert persisted.state == "pending"
    assert persisted.attempt == 1
    assert persisted.error_message == expected_error
