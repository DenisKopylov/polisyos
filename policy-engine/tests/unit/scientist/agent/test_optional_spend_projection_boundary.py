"""Trace unknown physical spend through the actual optional runtime projection.

This is a helper boundary oracle, not a served-route or vendor billing test.
The unknown case currently distinguishes a producer contract from its consumer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.llm import response, settlement, traced_client
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.runtime.http.services.control import response_shapes


def _source_custody() -> list[dict[str, Any]]:
    root_text = os.environ.get("E02_OPTIONAL_SPEND_SOURCE_ROOT")
    source_sha = os.environ.get("E02_OPTIONAL_SPEND_SOURCE_SHA")
    if root_text is None or source_sha is None:
        return []
    root = Path(root_text).resolve()
    origins = []
    for module in (response, settlement, traced_client, response_shapes):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root / "policy-engine/src"), path
        actual = path.read_bytes()
        expected = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{source_sha}:{path.relative_to(root)}"]
        )
        assert actual == expected, path
        origins.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(actual).hexdigest(),
            }
        )
    return origins


class _Span:
    def __enter__(self) -> _Span:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def set_attribute(self, *_args: Any) -> None:
        return None

    def set_status(self, *_args: Any) -> None:
        return None

    def record_exception(self, *_args: Any) -> None:
        return None


class _PhysicalProvider:
    def __init__(self, path: Path, reported_cost: float | None) -> None:
        self.path = path
        self.reported_cost = reported_cost
        self.responses: list[Any] = []

    async def generate(self, **kwargs: Any) -> Any:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(kwargs, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        usage = (
            None
            if self.reported_cost is None
            else SimpleNamespace(prompt_tokens=7, completion_tokens=3, cost_usd=self.reported_cost)
        )
        result = SimpleNamespace(
            content='{"value":7}',
            model="gpt-4o",
            provider="physical-optional-spend-oracle",
            usage=usage,
        )
        self.responses.append(result)
        return result


@pytest.mark.parametrize(
    "reported_cost",
    [
        pytest.param(None, id="unknown"),
        pytest.param(0.02, id="reported-02"),
        pytest.param(0.0, id="reported-zero"),
    ],
)
def test_optional_projection_preserves_physical_spend_knowledge(
    tmp_path: Path, reported_cost: float | None
) -> None:
    origins = _source_custody()
    provider = _PhysicalProvider(tmp_path / "physical-provider.jsonl", reported_cost)
    events: list[dict[str, Any]] = []
    client = TracedLLMClient(
        provider,
        model_name="gpt-4o",
        run_id="optional-spend-boundary",
        call_observer=events.append,
        tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
    )
    result = asyncio.run(client.generate(user="one actual optional-spend request"))
    physical_requests = [json.loads(line) for line in provider.path.read_text().splitlines()]
    projection = response_shapes._sum_call_events(events)
    print(
        "OPTIONAL_SPEND_ACTUAL "
        + json.dumps(
            {
                "reported_cost": reported_cost,
                "source_origins": origins,
                "physical_provider_requests": physical_requests,
                "actual_observer_events": events,
                "actual_runtime_projection": projection,
            },
            sort_keys=True,
        )
    )
    assert len(physical_requests) == len(provider.responses) == len(events) == 1
    assert result is provider.responses[0]
    assert json.loads(result.content)["value"] == 7
    event = events[0]
    assert event["provider_call"] is True
    assert event["cache_hit"] is False
    assert event["cost_usd"] == reported_cost
    if reported_cost is None:
        assert event["cost_origin"] == "unknown"
        assert event["usage_status"] == event["cost_status"] == "missing"
    else:
        assert event["usage_status"] == event["cost_status"] == "known"
    _source_custody()
    assert projection["cost_usd"] == reported_cost, (
        "the spend projection must distinguish an unknown physical charge from a reported zero"
    )
