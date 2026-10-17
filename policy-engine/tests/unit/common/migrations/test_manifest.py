from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.unit


def _legacy_manifest(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "0.9",
        "datasetName": "baseline",
        "rawHash": "sha256:abc",
    }
    payload.update(extra)
    return payload


def test_legacy_common_manifest_module_remains_a_compatibility_adapter() -> None:
    """The old import path remains a narrow adapter while callers transition."""
    from polisyos.common.migrations.manifest import (
        MANIFEST_CURRENT_VERSION,
        migrate_manifest_0_9_to_1_0,
    )

    assert MANIFEST_CURRENT_VERSION == "1.0"
    assert migrate_manifest_0_9_to_1_0(_legacy_manifest())["dataset_name"] == "baseline"
