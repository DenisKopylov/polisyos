from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.human_review.packets import build_review_packet, persist_review_packet
from polisyos.scientist.governance.human_review.queue import (
    HumanReviewQueueState,
    assign_review,
    enqueue_review_packet,
    load_review_queue,
    persist_review_queue,
)


def test_review_queue_assigns_and_persists_packet(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    packet = build_review_packet(run_id="run_queue")
    packet_ref = persist_review_packet(store, packet)
    queue = enqueue_review_packet(
        HumanReviewQueueState(),
        packet=packet,
        packet_ref=packet_ref,
    )

    queue, assignment = assign_review(
        queue,
        packet_id=packet.packet_id,
        reviewer_id="reviewer_a",
    )
    queue_ref = persist_review_queue(store, queue)
    loaded = load_review_queue(store, queue_ref)

    assert assignment.packet_id == packet.packet_id
    assert loaded.pending()[0].assignments[0].reviewer_id == "reviewer_a"
