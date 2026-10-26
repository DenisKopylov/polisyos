from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator
from typing import Any

import pytest

from polisyos.fabric.connectors.testing.harness import ConnectorTestHarness


class _DisconnectError(RuntimeError):
    """Identify the failure emitted by fixture teardown."""


class _MainCallError(RuntimeError):
    """Identify a failure from the test body."""


class _FixtureConnector:
    def __init__(self) -> None:
        self.fetch_completed = False
        self.disconnect_attempts = 0

    async def fetch(self, _handle: object) -> None:
        self.fetch_completed = True

    async def disconnect(self, _handle: object) -> None:
        self.disconnect_attempts += 1
        if not self.fetch_completed:
            raise AssertionError("disconnect was attempted before fetch")
        raise _DisconnectError("disconnect failed after fetch")


def _connected_fixture(
    connector: _FixtureConnector,
) -> tuple[AsyncGenerator[Any], object]:
    fixture_function = inspect.unwrap(ConnectorTestHarness.__dict__["connected"])
    handle = object()
    harness = object.__new__(ConnectorTestHarness)
    return fixture_function(harness, connector, handle), handle


async def _failing_test_body(connector: _FixtureConnector, handle: object) -> None:
    await connector.fetch(handle)
    raise _MainCallError("test body failed")


async def test_connected_surfaces_disconnect_failure_after_fetch() -> None:
    connector = _FixtureConnector()
    generator, handle = _connected_fixture(connector)

    assert await anext(generator) == (connector, handle)
    await connector.fetch(handle)

    with pytest.raises(_DisconnectError, match="disconnect failed after fetch") as teardown:
        await anext(generator)

    assert type(teardown.value) is _DisconnectError
    assert connector.disconnect_attempts == 1


async def test_connected_runs_teardown_after_body_failure() -> None:
    connector = _FixtureConnector()
    generator, handle = _connected_fixture(connector)

    assert await anext(generator) == (connector, handle)

    with pytest.raises(_MainCallError, match="test body failed") as call:
        await _failing_test_body(connector, handle)

    with pytest.raises(_DisconnectError, match="disconnect failed after fetch") as teardown:
        await anext(generator)

    assert type(call.value) is _MainCallError
    assert type(teardown.value) is _DisconnectError
    assert connector.disconnect_attempts == 1
