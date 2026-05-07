from __future__ import annotations

from polisyos.data_forge.domains.academic.batch import resolve_extract as runtime
from polisyos.data_forge.domains.academic.batch._resolve_extract_contracts import (
    EligibilityDecision,
    EligibleItem,
    ProviderResponse,
    ResolveExtractStats,
    WorkItem,
)


def test_resolve_extract_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime.ResolveExtractStats is ResolveExtractStats
    assert runtime.WorkItem is WorkItem
    assert runtime.EligibleItem is EligibleItem
    assert runtime.EligibilityDecision is EligibilityDecision
    assert runtime.ProviderResponse is ProviderResponse


def test_resolve_extract_contract_defaults_are_independent() -> None:
    first = ResolveExtractStats()
    second = ResolveExtractStats()

    first.rejection_reason_counts["too_short"] += 1
    first.fetch_latency_ms.append(12.5)

    assert first.rejection_reason_counts == {"too_short": 1}
    assert second.rejection_reason_counts == {}
    assert first.fetch_latency_ms == [12.5]
    assert second.fetch_latency_ms == []
