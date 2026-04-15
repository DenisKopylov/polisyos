from __future__ import annotations

from typing import Any, cast

from polisyos.fabric.catalog.resolver_fast_lane import FastLaneResolver
from polisyos.fabric.catalog.semantic import _resolve_profile_payloads
from polisyos.fabric.catalog.source_bindings import SourceBinding


def test_fast_lane_resolver_uses_injected_connector_registry(tmp_path) -> None:
    fake_registry = cast("Any", object())
    resolver = FastLaneResolver(
        curated_dir=tmp_path,
        connector_registry=fake_registry,
    )

    assert resolver._connector_registry is fake_registry


def test_semantic_profile_payloads_use_injected_registry() -> None:
    class _Profile:
        def model_dump(self, *, mode: str = "json") -> dict[str, object]:
            assert mode == "json"
            return {"profile_id": "profile.test"}

    class _Profiles:
        def get(self, profile_id: str) -> _Profile | None:
            assert profile_id == "profile.test"
            return _Profile()

    payloads = _resolve_profile_payloads(
        [
            SourceBinding(
                metric_id="test.metric",
                connector_id="test.connector",
                dataset_id="test.dataset",
                profile_id="profile.test",
            )
        ],
        source_profiles=_Profiles(),
    )

    assert payloads == {"profile.test": {"profile_id": "profile.test"}}
