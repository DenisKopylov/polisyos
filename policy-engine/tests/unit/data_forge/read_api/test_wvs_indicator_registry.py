from __future__ import annotations

from collections.abc import Mapping

import pytest

from polisyos.data_forge.read_api import catalog


def test_wvs_registry_read_api_is_a_discoverable_typed_facade(tmp_path) -> None:
    path = tmp_path / "wvs_indicator_registry.yaml"
    path.write_text(
        "version: 1\nindicators:\n  a165:\n    title: Social trust\n    waves: [7]\n    extension: retained\n",
        encoding="utf-8",
    )

    registry = catalog.read_wvs_indicator_registry(path)

    assert "read_wvs_indicator_registry" in catalog.__all__
    assert "WVSIndicatorRegistryReadError" in catalog.__all__
    assert isinstance(registry, Mapping)
    assert registry is not None
    assert registry["A165"]["title"] == "Social trust"
    assert registry["A165"]["extension"] == "retained"


def test_wvs_registry_read_api_distinguishes_missing_from_present_malformed(tmp_path) -> None:
    missing = tmp_path / "missing.yaml"
    assert catalog.read_wvs_indicator_registry(missing) is None

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("indicators: []\n", encoding="utf-8")
    with pytest.raises(catalog.WVSIndicatorRegistryReadError):
        catalog.read_wvs_indicator_registry(malformed)
