"""Example middleware exposed through `polisyos.runtime_middlewares`."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]
AsgiApp = Callable[[dict[str, Any], Receive, Send], Awaitable[None]]


class ExampleHeaderMiddleware:
    """ASGI middleware that appends a deterministic response header."""

    header_name = b"x-polisyos-example"
    header_value = b"runtime-middleware"

    def __init__(self, app: AsgiApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        async def send_with_example_header(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((self.header_name, self.header_value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_example_header)


@dataclass(frozen=True)
class RuntimeMiddlewareExampleComponent:
    """Component provider for the example Runtime middleware."""

    metadata: ComponentMetadata

    def create(self) -> type[ExampleHeaderMiddleware]:
        return ExampleHeaderMiddleware


response_header_middleware_component = RuntimeMiddlewareExampleComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("example.runtime_middleware.response_header@1.0.0"),
        kind=ComponentKind.RUNTIME_MIDDLEWARE,
        abi_targets={"runtime_middleware_api": ">=1.0.0,<2.0.0"},
        domains=["example"],
        jurisdictions=[],
        tags=["external-example", "runtime"],
        capabilities=Capability.RUNTIME_MIDDLEWARE,
        deps=[],
        display_name="Example Response Header Middleware",
        description="Offline ASGI middleware example for extension authors.",
        provides=["x-polisyos-example"],
    )
)

__all__ = [
    "ExampleHeaderMiddleware",
    "RuntimeMiddlewareExampleComponent",
    "response_header_middleware_component",
]
