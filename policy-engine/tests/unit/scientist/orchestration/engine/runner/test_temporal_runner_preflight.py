"""Importable preflight tests for the optional Temporal integration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.scientist.orchestration.engine.runner.temporal_runner import (
    TemporalParentRunReceiptUnavailable,
    TemporalWorkflowRunner,
    _require_temporal_parent_receipt_route,
)


def test_context_without_parent_run_has_no_writer_ownership_conflict() -> None:
    """The preflight only guards contexts that own a live parent run."""
    _require_temporal_parent_receipt_route(SimpleNamespace(run=None))


@pytest.mark.asyncio
async def test_parent_run_refusal_precedes_temporal_client_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unimplemented receipt bridge must fail before any remote dispatch."""
    runner = TemporalWorkflowRunner.__new__(TemporalWorkflowRunner)
    client_lookups = 0

    async def _unexpected_client_lookup():
        nonlocal client_lookups
        client_lookups += 1
        raise AssertionError("Temporal client lookup must not occur")

    monkeypatch.setattr(runner, "_get_client", _unexpected_client_lookup, raising=False)

    with pytest.raises(TemporalParentRunReceiptUnavailable) as exc_info:
        await runner.execute_workflow(
            workflow=None,
            state=None,
            ctx=SimpleNamespace(run=object()),
            registry=None,
        )

    assert exc_info.value.code == "temporal_parent_run_receipt_route_unavailable"
    assert client_lookups == 0
