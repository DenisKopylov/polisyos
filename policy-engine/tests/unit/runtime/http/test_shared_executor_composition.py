from __future__ import annotations

from typing import Any, cast

import pytest

from polisyos.common import async_tools
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerConfig


def test_runtime_app_configures_the_one_shared_executor_from_typed_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)

    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        process_worker_capacity=2,
        process_worker_profile_revision="r4-app-profile-v1",
    )
    container = cast("Any", app).state.runtime_container
    executor = async_tools.get_shared_executor()
    try:
        assert container.config.process_worker_capacity == 2
        assert container.config.process_worker_profile_revision == "r4-app-profile-v1"
        assert executor._max_workers == 2
        assert async_tools.get_shared_executor_profile() == async_tools.SharedExecutorProfile(
            capacity=2,
            revision="r4-app-profile-v1",
        )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_runtime_config_without_profile_declares_only_legacy_candidate_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 8)
    config = RuntimeContainerConfig(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    monkeypatch.setattr(async_tools.os, "cpu_count", lambda: 16)

    profile = config.shared_executor_profile()

    assert profile.capacity == 8
    assert profile.revision == "legacy-host-derived-v1"
    assert profile.source == "legacy_host_fallback"
    assert profile.authority == "candidate"


def test_runtime_config_requires_capacity_and_revision_together(tmp_path) -> None:
    with pytest.raises(async_tools.SharedExecutorConfigurationError, match="requires_capacity"):
        RuntimeContainerConfig(
            cas_root=tmp_path / "cas",
            core_runs_root=tmp_path / "runs",
            process_worker_capacity=2,
        )
