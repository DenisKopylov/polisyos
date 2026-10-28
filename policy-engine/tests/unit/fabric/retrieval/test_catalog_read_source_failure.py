"""The real resolver preserves the typed read-source family at every fallback seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.contracts.control import DataNeed, DataResolveRequest
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.fabric.retrieval.service import RetrievalService
from tests.unit.runtime.quality.test_acquisition_planner import (
    _install_recorded_file_catalog_supplier,
)
from tests.unit.runtime.quality.test_catalog_acquisition_source_binding import _actual_graphs


@pytest.mark.parametrize("site", ["identity", "bindings", "lookup", "target"])
@pytest.mark.parametrize("typed_source", [True, False])
def test_resolver_preserves_owner_failure_family_and_keeps_unrelated_provider_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site: str, typed_source: bool
) -> None:
    """Future source codes propagate by ancestry; a provider's code string is no authority."""
    _install_recorded_file_catalog_supplier(monkeypatch)
    with _actual_graphs(tmp_path) as (_owner, _foreign, source, graph, _other, _overlay):
        calls: list[str] = []
        if typed_source:
            # Deliberately not a known prefix: the source family, not a reason
            # spelling, is the generic contract exercised by the actual consumer.
            failure = catalog_api.CatalogReadSourceError(
                "future_owner_read_state", "controlled fault"
            )
        else:

            class UnrelatedProviderError(RuntimeError):
                code = "catalog_read_source_checkpoint_required"

            failure = UnrelatedProviderError("controlled optional provider failure")

        def fail_actual_method(*_args, **_kwargs):
            calls.append(site)
            raise failure

        if site in {"lookup", "target"}:
            monkeypatch.setattr(
                catalog_api.DatasetCatalogGraph,
                "resolve_metric_bindings",
                lambda *_args, **_kwargs: [],
            )
        method = {
            "identity": "source_content_identities",
            "bindings": "resolve_metric_bindings",
            "lookup": "find_by_polisyos_metric",
            "target": "resolve_fetch_target",
        }[site]
        monkeypatch.setattr(catalog_api.DatasetCatalogGraph, method, fail_actual_method)
        service = RetrievalService(
            curated_dir=source.repo_root / "production_data", dataset_catalog=graph
        )
        request = DataResolveRequest(
            data_needs=[
                DataNeed(metric="metric.test", purpose="selected source failure discriminator")
            ],
            mode="hybrid",
            allow_explore_fallback=False,
        )
        if typed_source:
            with pytest.raises(catalog_api.CatalogReadSourceError) as refused:
                service.resolve(request, run_profile=source.catalog_run_profile)
            assert refused.value is failure
        else:
            result = service.resolve(request, run_profile=source.catalog_run_profile)
            assert result.mode == "hybrid"
            assert not result.fetch_plans
        assert calls, "the selected fallback seam must actually be entered"
