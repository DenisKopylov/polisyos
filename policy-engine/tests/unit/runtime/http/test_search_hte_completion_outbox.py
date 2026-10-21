"""Prove the Runtime Search HTE delivery outbox is filtered and retry-safe."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC

from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore


def test_search_hte_pending_page_is_topic_scoped_and_replay_cursor_is_stable(tmp_path) -> None:
    """Unrelated pending rows cannot starve Search deliveries past the page limit."""
    db_path = tmp_path / "control-plane.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    for index in range(120):
        store.enqueue_outbox_event(
            topic="control.unrelated.pending",
            event_key=f"unrelated:{index}",
            payload={"index": index},
        )

    first = store.enqueue_outbox_event(
        topic="control.search.hte_completed",
        event_key="job-a:job_completed:11",
        job_id="job-a",
        run_id="run-a",
        payload={"completed_event_id": 11},
    )
    second = store.enqueue_outbox_event(
        topic="control.search.hte_completed",
        event_key="job-b:job_completed:19",
        job_id="job-b",
        run_id="run-b",
        payload={"completed_event_id": 19},
    )

    expected_order = sorted(
        (first, second),
        key=lambda row: (row.created_at.astimezone(UTC).isoformat(), row.event_id),
    )
    page_one = store.list_pending_search_hte_completion_events(limit=1)
    assert [row.event_id for row in page_one] == [expected_order[0].event_id]
    cursor_time = page_one[0].created_at.astimezone(UTC).isoformat()
    page_two = store.list_pending_search_hte_completion_events(
        limit=1,
        after_created_at=cursor_time,
        after_event_id=page_one[0].event_id,
    )
    assert [row.event_id for row in page_two] == [expected_order[1].event_id]


def test_search_hte_delivery_failure_stays_pending_and_ack_is_idempotent(tmp_path) -> None:
    """A failed receiver is retryable; duplicate acknowledged delivery is harmless."""
    db_path = tmp_path / "control-plane.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    record = store.enqueue_outbox_event(
        topic="control.search.hte_completed",
        event_key="job-c:job_completed:23",
        job_id="job-c",
        run_id="run-c",
        payload={"completed_event_id": 23},
    )

    store.record_outbox_delivery_failure(
        event_id=record.event_id,
        reason_code="search_hte_receiver_not_established",
    )
    pending = store.get_outbox_event(record.event_id)
    assert pending is not None
    assert pending.state == "pending"
    assert pending.error_message == "search_hte_receiver_not_established"
    assert pending.attempt == 1
    assert [row.event_id for row in store.list_pending_search_hte_completion_events()] == [
        record.event_id
    ]

    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    reopened.mark_outbox_published(event_id=record.event_id)
    published_once = reopened.get_outbox_event(record.event_id)
    assert published_once is not None
    assert published_once.state == "published"
    assert published_once.attempt == 2

    reopened.mark_outbox_published(event_id=record.event_id)
    published_twice = reopened.get_outbox_event(record.event_id)
    assert published_twice is not None
    assert published_twice.state == "published"
    assert published_twice.attempt == 2


def test_concurrent_search_hte_acknowledgements_compare_and_set_pending_state(tmp_path) -> None:
    """Two Runtime workers cannot count one successful delivery twice."""
    db_path = tmp_path / "control-plane.sqlite3"
    first_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    second_store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    record = first_store.enqueue_outbox_event(
        topic="control.search.hte_completed",
        event_key="job-d:job_completed:29",
        job_id="job-d",
        run_id="run-d",
        payload={"completed_event_id": 29},
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(store.mark_outbox_published, event_id=record.event_id)
            for store in (first_store, second_store)
        ]
        for future in futures:
            future.result()

    acknowledged = first_store.get_outbox_event(record.event_id)
    assert acknowledged is not None
    assert acknowledged.state == "published"
    assert acknowledged.attempt == 1


def test_worker_retries_failed_search_rows_across_continuous_arrivals_and_restart(
    tmp_path,
) -> None:
    """A frozen sequence watermark lets a full cycle finish despite new arrivals."""
    db_path = tmp_path / "control-plane.sqlite3"
    store = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    initial = [
        store.enqueue_outbox_event(
            topic="control.search.hte_completed",
            event_key=f"initial:{index}",
            job_id=f"initial-{index}",
            run_id="run-initial",
            payload={"completed_event_id": index + 1},
        )
        for index in range(60)
    ]
    initial_ids = [event.event_id for event in initial]
    first_cycle_visits: list[str] = []
    service = object.__new__(ControlPlaneService)
    service._control_store = store
    service._search_hte_outbox_cursor = None
    service._search_hte_outbox_watermark = None

    def fail_once(delivery) -> bool:
        first_cycle_visits.append(delivery.event_id)
        store.record_outbox_delivery_failure(
            event_id=delivery.event_id,
            reason_code="search_hte_receiver_not_established",
        )
        return False

    service._deliver_search_hte_completion_outbox = fail_once
    for page_index in range(3):
        assert service.reconcile_pending_search_hte_completion_events() == 0
        for offset in range(25):
            arrival = page_index * 25 + offset
            store.enqueue_outbox_event(
                topic="control.search.hte_completed",
                event_key=f"arrival:{arrival}",
                job_id=f"arrival-{arrival}",
                run_id="run-arrivals",
                payload={"completed_event_id": arrival + 1000},
            )

    assert first_cycle_visits == initial_ids
    assert service._search_hte_outbox_cursor is None
    assert service._search_hte_outbox_watermark is None

    reopened = ControlPlaneStore(backend="sqlite", sqlite_path=db_path)
    restarted_service = object.__new__(ControlPlaneService)
    restarted_service._control_store = reopened
    restarted_service._search_hte_outbox_cursor = None
    restarted_service._search_hte_outbox_watermark = None
    second_cycle_visits: list[str] = []

    def acknowledge(delivery) -> bool:
        second_cycle_visits.append(delivery.event_id)
        reopened.mark_outbox_published(event_id=delivery.event_id)
        return True

    restarted_service._deliver_search_hte_completion_outbox = acknowledge
    assert restarted_service.reconcile_pending_search_hte_completion_events() == 25
    assert second_cycle_visits == initial_ids[:25]
    for event_id in initial_ids[:25]:
        delivery = reopened.get_outbox_event(event_id)
        assert delivery is not None
        assert delivery.state == "published"
        assert delivery.attempt == 2
