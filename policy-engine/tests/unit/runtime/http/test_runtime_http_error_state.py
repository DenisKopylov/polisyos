"""HTTP problem exceptions retain their status through normal exception protocols."""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager

import pytest

from polisyos.runtime.http.errors import (
    RuntimeHTTPError,
    bad_request,
    conflict,
    forbidden,
    service_unavailable,
    unprocessable_entity,
)


@contextmanager
def _forward_error():
    yield


@asynccontextmanager
async def _forward_async_error():
    yield


@pytest.mark.parametrize(
    "factory",
    [
        bad_request,
        forbidden,
        conflict,
        unprocessable_entity,
        service_unavailable,
    ],
)
def test_runtime_http_error_survives_context_manager_traceback_reassignment(factory) -> None:
    error = factory("Preserve this typed problem.", code="fixture_problem")
    before = error.to_model(request_id="fixture").model_dump(mode="json")
    with pytest.raises(RuntimeHTTPError) as raised, _forward_error():
        raise error
    assert raised.value is error
    assert error.__traceback__ is not None
    assert error.to_model(request_id="fixture").model_dump(mode="json") == before


@pytest.mark.asyncio
async def test_runtime_http_error_survives_async_context_manager_and_preserves_problem() -> None:
    error = conflict(
        "Selected source remains contested.",
        code="fixture_contested",
        extensions={"authority_surface_decision": {"status": "blocked"}},
    )
    before = error.to_model(request_id="fixture").model_dump(mode="json")
    with pytest.raises(RuntimeHTTPError) as raised:
        async with _forward_async_error():
            raise error
    assert raised.value is error
    assert error.to_model(request_id="fixture").model_dump(mode="json") == before


def test_runtime_http_error_allows_standard_traceback_chaining_and_notes() -> None:
    error = bad_request("Input is not JSON.", code="fixture_json_invalid")
    cause = ValueError("non-JSON value")
    before = error.to_model(request_id="fixture").model_dump(mode="json")
    error.add_note("fixture note")

    def propagate_with_cause() -> None:
        try:
            raise cause
        except ValueError as caught:
            with _forward_error():
                raise error from caught

    with pytest.raises(RuntimeHTTPError) as raised:
        propagate_with_cause()
    assert raised.value is error and error.__cause__ is cause
    assert error.with_traceback(error.__traceback__) is error
    assert error.__notes__ == ["fixture note"]
    assert error.to_model(request_id="fixture").model_dump(mode="json") == before
