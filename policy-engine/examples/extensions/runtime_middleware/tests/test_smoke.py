from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from polisyos_runtime_middleware_example import response_header_middleware_component

from polisyos.core.components import ComponentKind

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


async def _empty_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _app(scope: dict[str, Any], receive: Receive, send: Send) -> None:
    del scope, receive
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def test_response_header_middleware_component_wraps_asgi_app() -> None:
    component = response_header_middleware_component

    if component.metadata.kind is not ComponentKind.RUNTIME_MIDDLEWARE:
        raise AssertionError(component.metadata.kind)
    if component.metadata.abi_targets["runtime_middleware_api"] != ">=1.0.0,<2.0.0":
        raise AssertionError(component.metadata.abi_targets)

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    middleware_class = component.create()
    asyncio.run(middleware_class(_app)({"type": "http", "path": "/"}, _empty_receive, send))

    expected_headers = [(b"x-polisyos-example", b"runtime-middleware")]
    if messages[0]["headers"] != expected_headers:
        raise AssertionError(messages[0]["headers"])
