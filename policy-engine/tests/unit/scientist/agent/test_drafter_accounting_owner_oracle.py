"""Ordinary critique normalization must preserve a pending accounting owner.

The synthetic provider performs real filesystem work. This proves local
constructor/callback custody, not invoice or protected audit-chain authority.
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
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.agent import _drafter_llm, _drafter_orchestrator
from polisyos.scientist.agent._drafter_orchestrator import MultiPassLLMDrafter
from polisyos.scientist.agent.drafter_models import MultiPassConfig
from polisyos.scientist.orchestration.llm import gateway_client


def _source_custody() -> list[dict[str, Any]]:
    root_text = os.environ.get("E02_DRAFTER_ORACLE_SOURCE_ROOT")
    source_sha = os.environ.get("E02_DRAFTER_ORACLE_SOURCE_SHA")
    if root_text is None or source_sha is None:
        return []
    root = Path(root_text).resolve()
    rows = []
    for module in (
        response,
        settlement,
        traced_client,
        _drafter_llm,
        _drafter_orchestrator,
        gateway_client,
    ):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root / "policy-engine/src"), path
        actual = path.read_bytes()
        expected = subprocess.check_output(
            ["git", "-C", str(root), "show", f"{source_sha}:{path.relative_to(root)}"]
        )
        assert actual == expected, path
        rows.append(
            {
                "module": module.__name__,
                "path": str(path),
                "sha256": hashlib.sha256(actual).hexdigest(),
            }
        )
    return rows


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
    def __init__(self, path: Path) -> None:
        self.path = path
        self.responses: list[Any] = []

    async def generate(self, **kwargs: Any) -> Any:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(kwargs, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        result = SimpleNamespace(
            content='{"value":7}',
            model="gpt-4o",
            provider="physical-constructor-oracle",
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3, cost_usd=0.02),
        )
        self.responses.append(result)
        return result


def _normalize(original: TracedLLMClient, model: str) -> TracedLLMClient:
    # Exercise the real constructor and its ordinary critique-client resolution.
    inner = SimpleNamespace(_llm=original)
    drafter = MultiPassLLMDrafter(
        inner,
        llm_client=original,
        config=MultiPassConfig(critique_model=model, constitution_enabled=False),
    )
    return drafter._llm


@pytest.mark.parametrize("critique_model", ["gpt-4o", "different-critique-model"])
def test_normalization_cannot_escape_original_pending_accounting(
    tmp_path: Path, critique_model: str
) -> None:
    origins = _source_custody()
    provider = _PhysicalProvider(tmp_path / "physical-provider.jsonl")
    callback_events: list[dict[str, Any]] = []
    cause = OSError("mandatory local accounting effect remains unresolved")

    def required_accounting(event: dict[str, Any]) -> None:
        callback_events.append(event)
        raise cause

    original = TracedLLMClient(
        provider,
        model_name="gpt-4o",
        required_accounting=required_accounting,
        tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
    )

    async def exercise() -> None:
        with pytest.raises(LLMAccountingError) as first:
            await original.generate(user="first actual request")
        assert first.value.response is provider.responses[0]
        assert first.value.cause is cause
        with pytest.raises(LLMAccountingError) as ordinary_guard:
            await original.generate(user="blocked original request")
        assert ordinary_guard.value is first.value
        received_error = None
        try:
            normalized = _normalize(original, critique_model)
            await normalized.generate(user="request after ordinary critique normalization")
        except LLMAccountingError as exc:
            received_error = exc
        work = [json.loads(line) for line in provider.path.read_text().splitlines()]
        print(
            "DRAFTER_ACCOUNTING_ACTUAL "
            + json.dumps(
                {
                    "critique_model": critique_model,
                    "source_origins": origins,
                    "physical_provider_requests": work,
                    "required_callback_calls": len(callback_events),
                    "same_original_error": received_error is first.value,
                    "original_response_content": first.value.response.content,
                },
                sort_keys=True,
            )
        )
        assert len(work) == len(provider.responses) == 1, (
            "ordinary normalization lost the original mandatory completion fence"
        )
        assert len(callback_events) == 1
        assert received_error is first.value

    asyncio.run(exercise())
    _source_custody()


def test_unmanaged_critique_retarget_preserves_real_provider_result(tmp_path: Path) -> None:
    origins = _source_custody()
    provider = _PhysicalProvider(tmp_path / "unmanaged-provider.jsonl")
    original = TracedLLMClient(
        provider,
        model_name="gpt-4o",
        tracer=SimpleNamespace(start_as_current_span=lambda *_a, **_k: _Span()),
        metrics=SimpleNamespace(record_llm_call=lambda **_k: None),
    )
    normalized = _normalize(original, "different-critique-model")
    result = asyncio.run(normalized.generate(user="legitimate unmanaged request"))
    work = [json.loads(line) for line in provider.path.read_text().splitlines()]
    print(
        "DRAFTER_UNMANAGED_ACTUAL "
        + json.dumps({"source_origins": origins, "physical_provider_requests": work})
    )
    assert len(work) == len(provider.responses) == 1
    assert result is provider.responses[0]
    assert json.loads(result.content)["value"] == 7
    _source_custody()
