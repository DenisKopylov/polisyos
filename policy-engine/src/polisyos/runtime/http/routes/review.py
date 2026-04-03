"""Public routes review module API."""
from __future__ import annotations

import json
from typing import Any, cast

from polisyos.runtime.http.services.review_collaboration import (
    ReviewChannel,
    ReviewCollaborationHub,
)

try:  # pragma: no cover - optional runtime dependency
    from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
except ModuleNotFoundError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    WebSocket = Any  # type: ignore[assignment]
    WebSocketDisconnect = Exception  # type: ignore[assignment]


router = APIRouter(prefix="/api/v1/review", tags=["review-collaboration"]) if APIRouter else None
_VALID_CHANNELS = {"review.cursor", "review.lock", "review.presence"}


def _get_review_collaboration_hub(websocket: WebSocket) -> ReviewCollaborationHub:
    hub = getattr(websocket.app.state, "review_collaboration_hub", None)
    if isinstance(hub, ReviewCollaborationHub):
        return hub
    hub = ReviewCollaborationHub()
    websocket.app.state.review_collaboration_hub = hub
    return hub


if router is not None:

    @router.websocket("/live")
    async def review_live(
        websocket: WebSocket,
        channel: str = Query(...),
        review_id: str = Query(..., min_length=1),
        run_id: str | None = Query(default=None),
        participant_id: str | None = Query(default=None),
        display_name: str | None = Query(default=None),
        accent_color: str | None = Query(default=None),
    ) -> None:
        if channel not in _VALID_CHANNELS:
            await websocket.close(code=4400, reason="Unsupported collaboration channel")
            return

        await websocket.accept()
        hub = _get_review_collaboration_hub(websocket)
        session = hub.build_session(
            channel=cast(ReviewChannel, channel),
            display_name=display_name,
            participant_id=participant_id,
            review_id=review_id,
            run_id=run_id,
            accent_color=accent_color,
        )
        await hub.dispatch(await hub.register(websocket, session))

        try:
            while True:
                raw_payload = await websocket.receive_text()
                try:
                    payload = json.loads(raw_payload) if raw_payload else {}
                except json.JSONDecodeError:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                await hub.dispatch(
                    await hub.handle_message(session, payload, websocket=websocket)
                )
        except WebSocketDisconnect:
            pass
        finally:
            await hub.dispatch(await hub.unregister(session))
