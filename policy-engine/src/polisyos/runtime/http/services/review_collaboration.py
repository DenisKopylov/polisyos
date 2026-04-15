"""Public services review collaboration module API."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional runtime dependency
    WebSocket: Any
    from fastapi import WebSocket

except ModuleNotFoundError:  # pragma: no cover
    WebSocket = Any


ReviewChannel = Literal["review.cursor", "review.lock", "review.presence"]
_COLLABORATION_COLORS = (
    "#1d8f85",
    "#2557a7",
    "#c4682b",
    "#b13d66",
    "#7a59a1",
    "#2f7a4f",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _resolve_color(participant_id: str) -> str:
    if not participant_id:
        return _COLLABORATION_COLORS[0]
    checksum = sum(ord(char) for char in participant_id)
    return _COLLABORATION_COLORS[checksum % len(_COLLABORATION_COLORS)]


@dataclass(slots=True)
class ReviewCollaborationSession:
    """Review collaboration session public type."""
    channel: ReviewChannel
    display_name: str
    participant_id: str
    review_id: str
    run_id: str | None
    session_id: str
    accent_color: str
    last_seen_at: datetime


@dataclass(slots=True)
class ReviewCursorState:
    """Review cursor state data model."""
    accent_color: str
    display_name: str
    hidden: bool
    participant_id: str
    updated_at: datetime
    x: float
    y: float


@dataclass(slots=True)
class ReviewLockState:
    """Review lock state data model."""
    accent_color: str
    acquired_at: datetime
    display_name: str
    expires_at: datetime
    participant_id: str
    review_id: str
    session_id: str


@dataclass(slots=True)
class OutboundReviewMessage:
    """Outbound review message public type."""
    channel: ReviewChannel
    payload: dict[str, Any]
    recipients: list["OutboundReviewRecipient"]
    review_id: str


@dataclass(slots=True)
class OutboundReviewRecipient:
    """A specific websocket recipient plus its registered collaboration session ID."""
    session_id: str
    websocket: WebSocket


class ReviewCollaborationHub:
    """Review collaboration hub public type."""
    def __init__(self, *, lease_ttl_seconds: int = 25) -> None:
        self._lease_ttl_seconds = lease_ttl_seconds
        self._guard = asyncio.Lock()
        self._subscribers: dict[tuple[ReviewChannel, str], dict[str, WebSocket]] = defaultdict(dict)
        self._presence_sessions: dict[str, dict[str, ReviewCollaborationSession]] = defaultdict(dict)
        self._cursor_states: dict[str, dict[str, ReviewCursorState]] = defaultdict(dict)
        self._locks: dict[str, ReviewLockState] = {}

    async def register(
        self,
        websocket: WebSocket,
        session: ReviewCollaborationSession,
    ) -> list[OutboundReviewMessage]:
        async with self._guard:
            self._subscribers[(session.channel, session.review_id)][session.session_id] = websocket
            if session.channel == "review.presence":
                self._presence_sessions[session.review_id][session.session_id] = session
                return [
                    OutboundReviewMessage(
                        channel=session.channel,
                        payload=self._build_presence_snapshot_locked(session.review_id),
                        recipients=self._recipient_entries_locked(session.channel, session.review_id),
                        review_id=session.review_id,
                    )
                ]
            if session.channel == "review.cursor":
                self._cursor_states[session.review_id][session.session_id] = ReviewCursorState(
                    accent_color=session.accent_color,
                    display_name=session.display_name,
                    hidden=True,
                    participant_id=session.participant_id,
                    updated_at=session.last_seen_at,
                    x=0.0,
                    y=0.0,
                )
                return [
                    OutboundReviewMessage(
                        channel=session.channel,
                        payload=self._build_cursor_snapshot_locked(session.review_id),
                        recipients=[OutboundReviewRecipient(session_id=session.session_id, websocket=websocket)],
                        review_id=session.review_id,
                    )
                ]
            self._clear_expired_lock_locked(session.review_id)
            return [
                OutboundReviewMessage(
                    channel=session.channel,
                    payload=self._build_lock_snapshot_locked(session.review_id),
                    recipients=[OutboundReviewRecipient(session_id=session.session_id, websocket=websocket)],
                    review_id=session.review_id,
                )
            ]

    async def unregister(
        self,
        session: ReviewCollaborationSession,
    ) -> list[OutboundReviewMessage]:
        messages: list[OutboundReviewMessage] = []
        async with self._guard:
            subscribers = self._subscribers[(session.channel, session.review_id)]
            subscribers.pop(session.session_id, None)
            if not subscribers:
                self._subscribers.pop((session.channel, session.review_id), None)

            if session.channel == "review.presence":
                sessions = self._presence_sessions.get(session.review_id)
                if sessions is not None:
                    sessions.pop(session.session_id, None)
                    if not sessions:
                        self._presence_sessions.pop(session.review_id, None)
                recipients = self._recipient_entries_locked(session.channel, session.review_id)
                if recipients:
                    messages.append(
                        OutboundReviewMessage(
                            channel=session.channel,
                            payload=self._build_presence_snapshot_locked(session.review_id),
                            recipients=recipients,
                            review_id=session.review_id,
                        )
                    )

            elif session.channel == "review.cursor":
                cursors = self._cursor_states.get(session.review_id)
                if cursors is not None:
                    cursors.pop(session.session_id, None)
                    if not cursors:
                        self._cursor_states.pop(session.review_id, None)
                recipients = self._recipient_entries_locked(session.channel, session.review_id)
                if recipients:
                    messages.append(
                        OutboundReviewMessage(
                            channel=session.channel,
                            payload=self._build_cursor_snapshot_locked(session.review_id),
                            recipients=recipients,
                            review_id=session.review_id,
                        )
                    )

            elif self._release_lock_locked(session.review_id, session.session_id):
                recipients = self._recipient_entries_locked(session.channel, session.review_id)
                if recipients:
                    messages.append(
                        OutboundReviewMessage(
                            channel=session.channel,
                            payload=self._build_lock_snapshot_locked(session.review_id),
                            recipients=recipients,
                            review_id=session.review_id,
                        )
                    )

        return messages

    async def handle_message(
        self,
        session: ReviewCollaborationSession,
        payload: dict[str, Any],
        *,
        websocket: WebSocket,
    ) -> list[OutboundReviewMessage]:
        message_type = str(payload.get("type") or "").strip().lower()
        now = _utcnow()
        session.last_seen_at = now

        async with self._guard:
            if session.channel == "review.presence":
                presence = self._presence_sessions.get(session.review_id, {}).get(session.session_id)
                if presence is not None:
                    presence.last_seen_at = now
                return []

            if session.channel == "review.cursor":
                cursor = self._cursor_states.get(session.review_id, {}).get(session.session_id)
                if cursor is None:
                    return []
                if message_type == "cursor.leave":
                    cursor.hidden = True
                    cursor.updated_at = now
                elif message_type == "cursor.update":
                    cursor.hidden = False
                    cursor.updated_at = now
                    cursor.x = max(0.0, min(1.0, float(payload.get("x") or 0.0)))
                    cursor.y = max(0.0, min(1.0, float(payload.get("y") or 0.0)))
                else:
                    return []
                return [
                    OutboundReviewMessage(
                        channel=session.channel,
                        payload=self._build_cursor_snapshot_locked(session.review_id),
                        recipients=self._recipient_entries_locked(session.channel, session.review_id),
                        review_id=session.review_id,
                    )
                ]

            self._clear_expired_lock_locked(session.review_id)

            if message_type == "lock.release":
                changed = self._release_lock_locked(session.review_id, session.session_id)
                recipients = self._recipient_entries_locked(session.channel, session.review_id)
                if not recipients:
                    return []
                if changed:
                    return [
                        OutboundReviewMessage(
                            channel=session.channel,
                            payload=self._build_lock_snapshot_locked(session.review_id),
                            recipients=recipients,
                            review_id=session.review_id,
                        )
                    ]
                return [
                    OutboundReviewMessage(
                        channel=session.channel,
                        payload=self._build_lock_snapshot_locked(session.review_id),
                        recipients=[
                            OutboundReviewRecipient(
                                session_id=session.session_id,
                                websocket=websocket,
                            )
                        ],
                        review_id=session.review_id,
                    )
                ]

            if message_type not in {"lock.acquire", "lock.renew"}:
                return []

            current = self._locks.get(session.review_id)
            expires_at = now + timedelta(seconds=self._lease_ttl_seconds)
            if current is None or current.participant_id == session.participant_id:
                self._locks[session.review_id] = ReviewLockState(
                    accent_color=session.accent_color,
                    acquired_at=current.acquired_at if current is not None else now,
                    display_name=session.display_name,
                    expires_at=expires_at,
                    participant_id=session.participant_id,
                    review_id=session.review_id,
                    session_id=session.session_id,
                )
                return [
                    OutboundReviewMessage(
                        channel=session.channel,
                        payload=self._build_lock_snapshot_locked(session.review_id),
                        recipients=self._recipient_entries_locked(session.channel, session.review_id),
                        review_id=session.review_id,
                    )
                ]

            return [
                OutboundReviewMessage(
                    channel=session.channel,
                    payload=self._build_lock_snapshot_locked(session.review_id),
                    recipients=[
                        OutboundReviewRecipient(
                            session_id=session.session_id,
                            websocket=websocket,
                        )
                    ],
                    review_id=session.review_id,
                )
            ]

    async def dispatch(self, messages: list[OutboundReviewMessage]) -> None:
        pending = list(messages)
        while pending:
            message = pending.pop(0)
            if not message.recipients:
                continue
            failed_session_ids: list[str] = []
            for recipient in list(message.recipients):
                try:
                    await recipient.websocket.send_json(message.payload)
                except (AttributeError, RuntimeError, ValueError) as exc:
                    logger.debug("Failed to send review message: %s", exc)
                    failed_session_ids.append(recipient.session_id)
            if failed_session_ids:
                pending.extend(
                    await self._prune_failed_recipients(
                        channel=message.channel,
                        review_id=message.review_id,
                        failed_session_ids=failed_session_ids,
                    )
                )

    async def close(self) -> None:
        """Close active sockets and clear in-memory collaboration state."""
        async with self._guard:
            recipients = [
                websocket
                for subscribers in self._subscribers.values()
                for websocket in subscribers.values()
            ]
            self._subscribers.clear()
            self._presence_sessions.clear()
            self._cursor_states.clear()
            self._locks.clear()
        for websocket in recipients:
            try:
                await websocket.close(code=1012, reason="Runtime shutting down")
            except (AttributeError, RuntimeError, ValueError):
                continue

    @staticmethod
    def build_session(
        *,
        channel: ReviewChannel,
        display_name: str | None,
        participant_id: str | None,
        review_id: str,
        run_id: str | None,
        accent_color: str | None = None,
    ) -> ReviewCollaborationSession:
        normalized_participant_id = (participant_id or "").strip() or f"anon-{uuid4().hex[:10]}"
        normalized_display_name = (display_name or "").strip() or normalized_participant_id
        return ReviewCollaborationSession(
            channel=channel,
            display_name=normalized_display_name,
            participant_id=normalized_participant_id,
            review_id=review_id,
            run_id=run_id,
            session_id=uuid4().hex,
            accent_color=(accent_color or "").strip() or _resolve_color(normalized_participant_id),
            last_seen_at=_utcnow(),
        )

    def _clear_expired_lock_locked(self, review_id: str) -> None:
        current = self._locks.get(review_id)
        if current is None:
            return
        if current.expires_at <= _utcnow():
            self._locks.pop(review_id, None)

    def _release_lock_locked(self, review_id: str, session_id: str) -> bool:
        current = self._locks.get(review_id)
        if current is None or current.session_id != session_id:
            return False
        self._locks.pop(review_id, None)
        return True

    def _recipient_entries_locked(
        self,
        channel: ReviewChannel,
        review_id: str,
    ) -> list[OutboundReviewRecipient]:
        return [
            OutboundReviewRecipient(session_id=session_id, websocket=websocket)
            for session_id, websocket in self._subscribers.get((channel, review_id), {}).items()
        ]

    def _build_presence_snapshot_locked(self, review_id: str) -> dict[str, Any]:
        grouped: dict[str, dict[str, Any]] = {}
        for session in self._presence_sessions.get(review_id, {}).values():
            current = grouped.get(session.participant_id)
            last_seen_at = _isoformat(session.last_seen_at)
            if current is None:
                grouped[session.participant_id] = {
                    "participant_id": session.participant_id,
                    "display_name": session.display_name,
                    "accent_color": session.accent_color,
                    "last_seen_at": last_seen_at,
                    "session_count": 1,
                }
                continue

            current["session_count"] += 1
            if last_seen_at > current["last_seen_at"]:
                current["last_seen_at"] = last_seen_at

        participants = sorted(
            grouped.values(),
            key=lambda item: (item["display_name"].lower(), item["participant_id"]),
        )
        return {
            "channel": "review.presence",
            "participants": participants,
            "review_id": review_id,
            "type": "presence.snapshot",
        }

    def _build_cursor_snapshot_locked(self, review_id: str) -> dict[str, Any]:
        cursors = [
            {
                "participant_id": cursor.participant_id,
                "display_name": cursor.display_name,
                "accent_color": cursor.accent_color,
                "x": cursor.x,
                "y": cursor.y,
                "updated_at": _isoformat(cursor.updated_at),
            }
            for cursor in self._cursor_states.get(review_id, {}).values()
            if not cursor.hidden
        ]
        cursors.sort(key=lambda item: (item["display_name"].lower(), item["participant_id"]))
        return {
            "channel": "review.cursor",
            "cursors": cursors,
            "review_id": review_id,
            "type": "cursor.snapshot",
        }

    def _build_lock_snapshot_locked(self, review_id: str) -> dict[str, Any]:
        self._clear_expired_lock_locked(review_id)
        current = self._locks.get(review_id)
        lock_payload = None
        if current is not None:
            lock_payload = {
                "participant_id": current.participant_id,
                "display_name": current.display_name,
                "accent_color": current.accent_color,
                "acquired_at": _isoformat(current.acquired_at),
                "expires_at": _isoformat(current.expires_at),
            }
        return {
            "channel": "review.lock",
            "lock": lock_payload,
            "review_id": review_id,
            "type": "lock.snapshot",
        }

    async def _prune_failed_recipients(
        self,
        *,
        channel: ReviewChannel,
        review_id: str,
        failed_session_ids: list[str],
    ) -> list[OutboundReviewMessage]:
        failed = set(failed_session_ids)
        if not failed:
            return []

        async with self._guard:
            subscribers = self._subscribers.get((channel, review_id))
            if subscribers is not None:
                for session_id in failed:
                    subscribers.pop(session_id, None)
                if not subscribers:
                    self._subscribers.pop((channel, review_id), None)

            if channel == "review.presence":
                sessions = self._presence_sessions.get(review_id)
                if sessions is not None:
                    for session_id in failed:
                        sessions.pop(session_id, None)
                    if not sessions:
                        self._presence_sessions.pop(review_id, None)
                recipients = self._recipient_entries_locked(channel, review_id)
                if not recipients:
                    return []
                return [
                    OutboundReviewMessage(
                        channel=channel,
                        payload=self._build_presence_snapshot_locked(review_id),
                        recipients=recipients,
                        review_id=review_id,
                    )
                ]

            if channel == "review.cursor":
                cursors = self._cursor_states.get(review_id)
                if cursors is not None:
                    for session_id in failed:
                        cursors.pop(session_id, None)
                    if not cursors:
                        self._cursor_states.pop(review_id, None)
                recipients = self._recipient_entries_locked(channel, review_id)
                if not recipients:
                    return []
                return [
                    OutboundReviewMessage(
                        channel=channel,
                        payload=self._build_cursor_snapshot_locked(review_id),
                        recipients=recipients,
                        review_id=review_id,
                    )
                ]

            released = False
            for session_id in failed:
                released = self._release_lock_locked(review_id, session_id) or released
            recipients = self._recipient_entries_locked(channel, review_id)
            if not released or not recipients:
                return []
            return [
                OutboundReviewMessage(
                    channel=channel,
                    payload=self._build_lock_snapshot_locked(review_id),
                    recipients=recipients,
                    review_id=review_id,
                )
            ]
