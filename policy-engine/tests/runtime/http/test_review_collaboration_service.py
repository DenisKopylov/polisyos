from __future__ import annotations

import asyncio
from datetime import datetime

from polisyos.runtime.http.services.review_collaboration import ReviewCollaborationHub


class _FakeWebSocket:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.fail_on_send = fail_on_send
        self.sent: list[dict[str, object]] = []
        self.closed = False

    async def send_json(self, payload: dict[str, object]) -> None:
        if self.fail_on_send:
            raise RuntimeError("closed")
        self.sent.append(payload)

    async def close(self, code: int, reason: str) -> None:
        del code, reason
        self.closed = True


def test_dispatch_prunes_failed_presence_recipients_and_rebroadcasts() -> None:
    async def _run() -> None:
        hub = ReviewCollaborationHub()
        review_id = "run:R_core_api_001:governance"
        alice_ws = _FakeWebSocket()
        bob_ws = _FakeWebSocket(fail_on_send=True)
        alice = hub.build_session(
            channel="review.presence",
            display_name="Alice",
            participant_id="alice",
            review_id=review_id,
            run_id="R_core_api_001",
        )
        bob = hub.build_session(
            channel="review.presence",
            display_name="Bob",
            participant_id="bob",
            review_id=review_id,
            run_id="R_core_api_001",
        )

        await hub.dispatch(await hub.register(alice_ws, alice))
        await hub.dispatch(await hub.register(bob_ws, bob))

        subscribers = hub._subscribers[("review.presence", review_id)]
        participants = alice_ws.sent[-1]["participants"]
        assert bob.session_id not in subscribers
        assert [participant["participant_id"] for participant in participants] == ["alice"]

    asyncio.run(_run())


def test_cursor_leave_hides_cursor_for_all_subscribers() -> None:
    async def _run() -> None:
        hub = ReviewCollaborationHub()
        review_id = "run:R_core_api_001:governance"
        alice_ws = _FakeWebSocket()
        bob_ws = _FakeWebSocket()
        alice = hub.build_session(
            channel="review.cursor",
            display_name="Alice",
            participant_id="alice",
            review_id=review_id,
            run_id="R_core_api_001",
        )
        bob = hub.build_session(
            channel="review.cursor",
            display_name="Bob",
            participant_id="bob",
            review_id=review_id,
            run_id="R_core_api_001",
        )

        await hub.dispatch(await hub.register(alice_ws, alice))
        await hub.dispatch(await hub.register(bob_ws, bob))
        await hub.dispatch(
            await hub.handle_message(
                alice,
                {"type": "cursor.update", "x": 0.2, "y": 0.4},
                websocket=alice_ws,
            )
        )
        await hub.dispatch(
            await hub.handle_message(
                alice,
                {"type": "cursor.leave"},
                websocket=alice_ws,
            )
        )

        assert alice_ws.sent[-1]["type"] == "cursor.snapshot"
        assert bob_ws.sent[-1]["cursors"] == []

    asyncio.run(_run())


def test_lock_renew_extends_existing_lease_snapshot() -> None:
    async def _run() -> None:
        hub = ReviewCollaborationHub(lease_ttl_seconds=60)
        review_id = "run:R_core_api_001:governance"
        alice_ws = _FakeWebSocket()
        alice = hub.build_session(
            channel="review.lock",
            display_name="Alice",
            participant_id="alice",
            review_id=review_id,
            run_id="R_core_api_001",
        )

        await hub.dispatch(await hub.register(alice_ws, alice))
        await hub.dispatch(
            await hub.handle_message(
                alice,
                {"type": "lock.acquire"},
                websocket=alice_ws,
            )
        )
        first_expires_at = datetime.fromisoformat(
            str(alice_ws.sent[-1]["lock"]["expires_at"]).replace("Z", "+00:00")
        )

        await hub.dispatch(
            await hub.handle_message(
                alice,
                {"type": "lock.renew"},
                websocket=alice_ws,
            )
        )
        renewed_expires_at = datetime.fromisoformat(
            str(alice_ws.sent[-1]["lock"]["expires_at"]).replace("Z", "+00:00")
        )

        assert renewed_expires_at >= first_expires_at

    asyncio.run(_run())
