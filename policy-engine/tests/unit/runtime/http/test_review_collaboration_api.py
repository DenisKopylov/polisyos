from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.parametrize(
    ("channel", "message_type"),
    [
        ("review.presence", "presence.snapshot"),
        ("review.cursor", "cursor.snapshot"),
        ("review.lock", "lock.snapshot"),
    ],
)
def test_review_websocket_snapshots_emit_versioned_contract_identity(
    runtime_api_env, channel: str, message_type: str
) -> None:
    review_id = "run:R_core_api_001:governance"
    with runtime_api_env["client"].websocket_connect(
        f"/api/v1/review/live?channel={channel}&review_id={review_id}"
        "&participant_id=alice&display_name=Alice"
    ) as websocket:
        snapshot = websocket.receive_json()

    assert snapshot["contract_id"] == "policyos.runtime.review_collaboration_envelope"
    assert snapshot["schema_version"] == "policyos.runtime.review_collaboration_envelope.v1"
    assert snapshot["type"] == message_type


class TestReviewCollaborationApi:
    def test_presence_snapshot_tracks_active_reviewers(self, runtime_api_env):
        client = runtime_api_env["client"]
        review_id = "run:R_core_api_001:governance"

        with client.websocket_connect(
            f"/api/v1/review/live?channel=review.presence&review_id={review_id}"
            "&participant_id=alice&display_name=Alice"
        ) as alice_ws:
            first_snapshot = alice_ws.receive_json()
            assert first_snapshot["type"] == "presence.snapshot"
            assert len(first_snapshot["participants"]) == 1
            assert first_snapshot["participants"][0]["participant_id"] == "alice"
            assert first_snapshot["participants"][0]["display_name"] == "Alice"
            assert first_snapshot["participants"][0]["session_count"] == 1
            assert first_snapshot["participants"][0]["accent_color"]

            with client.websocket_connect(
                f"/api/v1/review/live?channel=review.presence&review_id={review_id}"
                "&participant_id=bob&display_name=Bob"
            ) as bob_ws:
                updated_for_alice = alice_ws.receive_json()
                updated_for_bob = bob_ws.receive_json()

                assert len(updated_for_alice["participants"]) == 2
                assert [item["participant_id"] for item in updated_for_bob["participants"]] == [
                    "alice",
                    "bob",
                ]

    def test_cursor_and_lock_channels_broadcast_state(self, runtime_api_env):
        client = runtime_api_env["client"]
        review_id = "run:R_core_api_001:promotion:promotion_fixture_001"

        with (
            client.websocket_connect(
                f"/api/v1/review/live?channel=review.cursor&review_id={review_id}"
                "&participant_id=alice&display_name=Alice"
            ) as alice_cursor,
            client.websocket_connect(
                f"/api/v1/review/live?channel=review.cursor&review_id={review_id}"
                "&participant_id=bob&display_name=Bob"
            ) as bob_cursor,
        ):
            assert alice_cursor.receive_json()["cursors"] == []
            assert bob_cursor.receive_json()["cursors"] == []

            alice_cursor.send_json({"type": "cursor.update", "x": 0.25, "y": 0.5})
            alice_snapshot = alice_cursor.receive_json()
            bob_snapshot = bob_cursor.receive_json()

            assert alice_snapshot["type"] == "cursor.snapshot"
            assert bob_snapshot["cursors"][0]["participant_id"] == "alice"
            assert bob_snapshot["cursors"][0]["x"] == 0.25
            assert bob_snapshot["cursors"][0]["y"] == 0.5

            alice_cursor.send_json({"type": "cursor.leave"})
            left_for_alice = alice_cursor.receive_json()
            left_for_bob = bob_cursor.receive_json()
            assert left_for_alice["cursors"] == []
            assert left_for_bob["cursors"] == []

        with (
            client.websocket_connect(
                f"/api/v1/review/live?channel=review.lock&review_id={review_id}"
                "&participant_id=alice&display_name=Alice"
            ) as alice_lock,
            client.websocket_connect(
                f"/api/v1/review/live?channel=review.lock&review_id={review_id}"
                "&participant_id=bob&display_name=Bob"
            ) as bob_lock,
        ):
            assert alice_lock.receive_json()["lock"] is None
            assert bob_lock.receive_json()["lock"] is None

            alice_lock.send_json({"type": "lock.acquire"})
            owned_snapshot = alice_lock.receive_json()
            mirrored_snapshot = bob_lock.receive_json()
            assert owned_snapshot["lock"]["participant_id"] == "alice"
            assert mirrored_snapshot["lock"]["participant_id"] == "alice"
            initial_expires_at = datetime.fromisoformat(
                owned_snapshot["lock"]["expires_at"].replace("Z", "+00:00")
            )

            alice_lock.send_json({"type": "lock.renew"})
            renewed_for_alice = alice_lock.receive_json()
            renewed_for_bob = bob_lock.receive_json()
            renewed_expires_at = datetime.fromisoformat(
                renewed_for_alice["lock"]["expires_at"].replace("Z", "+00:00")
            )
            assert renewed_for_alice["lock"]["participant_id"] == "alice"
            assert renewed_for_bob["lock"]["participant_id"] == "alice"
            assert renewed_expires_at >= initial_expires_at

            bob_lock.send_json({"type": "lock.acquire"})
            denied_snapshot = bob_lock.receive_json()
            assert denied_snapshot["lock"]["participant_id"] == "alice"

            alice_lock.send_json({"type": "lock.release"})
            released_for_alice = alice_lock.receive_json()
            released_for_bob = bob_lock.receive_json()
            assert released_for_alice["lock"] is None
            assert released_for_bob["lock"] is None
