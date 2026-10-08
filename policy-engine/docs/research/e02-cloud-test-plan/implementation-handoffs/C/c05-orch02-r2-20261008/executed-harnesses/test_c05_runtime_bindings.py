"""Independent actual owner-bound loader calls, without editing repository tests."""
from __future__ import annotations

import json
import os
from pathlib import Path

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders, transformers


def test_actual_loader_resolves_owner_global_and_request_context(monkeypatch):
    calls = []
    original_iso = transformers._to_iso3
    original_float = transformers._as_float
    observed = []

    def iso_spy(label):
        def call(value):
            calls.append([label, value])
            return original_iso(value)
        return call

    assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
    monkeypatch.setattr(transformers, "_to_iso3", iso_spy("canonical_owner"))
    assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
    assert calls == [["canonical_owner", "UA"]]
    monkeypatch.setattr(loaders, "_to_iso3", iso_spy("loader_override"))
    assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
    context = CoreSourcesCompatibilityContext({
        (transformers.__name__, "_to_iso3"): iso_spy("request_context"),
    })
    with bind_core_sources_compatibility_context(context):
        assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
    assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
    assert calls == [
        ["canonical_owner", "UA"], ["loader_override", "UA"],
        ["request_context", "UA"], ["loader_override", "UA"],
    ]

    def float_spy(value):
        result = original_float(value)
        observed.append({"raw": value, "actual_result": result})
        return result

    monkeypatch.setattr(transformers, "_as_float", float_spy)
    assert loaders._as_float("2.5") == 2.5
    assert loaders._as_float("not-a-number") is None
    assert observed == [{"raw": "2.5", "actual_result": 2.5},
                        {"raw": "not-a-number", "actual_result": None}]
    (Path(os.environ["ORCH02_OUTPUT_DIR"]) / "runtime-binding-events.json").write_text(
        json.dumps({"owner_country_results": "UKR", "actual_dispatch_calls": calls,
                    "actual_scalar_transformer_results": observed,
                    "oracle": "actual loader consumer output and delegated canonical transformer; context lifetime restored"}, indent=2) + "\n"
    )
