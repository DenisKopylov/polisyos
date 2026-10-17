"""Exercise the real basedpyright scope selector without running the checker."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.devx.workspace import core_runtime_basedpyright

_EXPECTED_CURATED_SCOPE = (
    "src/polisyos/scholar/orchestrator/freshness.py",
    "src/polisyos/scholar/orchestrator/bundle.py",
    "src/polisyos/scholar/api.py",
    "src/polisyos/scientist/api.py",
    "src/polisyos/scientist/adapters/fabric_bridge.py",
    "src/polisyos/scientist/agent/drafter_factory.py",
    "src/polisyos/scientist/agent/knowledge_base.py",
    "src/polisyos/scientist/methods/autotune/models.py",
    "src/polisyos/scientist/compute/runner.py",
    "src/polisyos/scientist/validation/decision_validity.py",
    "src/polisyos/scientist/orchestration/engine/checkpoint.py",
    "src/polisyos/scientist/orchestration/engine/metrics_otel.py",
    "src/polisyos/scientist/orchestration/engine/operational_monitoring.py",
    "src/polisyos/scientist/orchestration/engine/runner/_activity_worker.py",
    "src/polisyos/scientist/orchestration/engine/error_semantics.py",
    "src/polisyos/scientist/governance/pipeline.py",
    "src/polisyos/scientist/governance/preflight.py",
    "src/polisyos/scientist/orchestration/llm/budget_enforcer.py",
    "src/polisyos/scientist/orchestration/llm/factory.py",
    "src/polisyos/scientist/orchestration/llm/profiles/registry.py",
    "src/polisyos/scientist/orchestration/llm/cycle.py",
    "src/polisyos/scientist/replay/backend.py",
    "src/polisyos/scientist/orchestration/workflows/builder.py",
    "src/polisyos/fabric/api.py",
    "src/polisyos/fabric/catalog/providers.py",
    "src/polisyos/fabric/catalog/resolver_fast_lane.py",
    "src/polisyos/fabric/connectors/bindings/registry.py",
    "src/polisyos/fabric/connectors/bindings/resolver.py",
    "src/polisyos/fabric/connectors/cache/_store_core.py",
    "src/polisyos/fabric/connectors/cache/prefetch.py",
    "src/polisyos/fabric/connectors/cache/proxy.py",
    "src/polisyos/fabric/connectors/profiles/registry.py",
    "src/polisyos/fabric/connectors/resilience/circuit_breaker.py",
    "src/polisyos/fabric/connectors/resilience/fallback.py",
    "src/polisyos/fabric/connectors/resilience/rate_limiter.py",
    "src/polisyos/fabric/data_plane/cli.py",
    "src/polisyos/fabric/data_plane/cursor_store.py",
    "src/polisyos/fabric/data_plane/modes.py",
    "src/polisyos/fabric/data_plane/orchestrator.py",
    "src/polisyos/fabric/data_plane/quarantine.py",
    "src/polisyos/fabric/data_plane/streaming.py",
    "src/polisyos/fabric/ingestion/__init__.py",
    "src/polisyos/fabric/ingestion/ingestion.py",
    "src/polisyos/fabric/ingestion/ingestion_providers.py",
    "src/polisyos/fabric/retrieval/executor.py",
    "src/polisyos/fabric/retrieval/explore_lane.py",
    "src/polisyos/fabric/retrieval/providers.py",
    "src/polisyos/fabric/retrieval/service.py",
    "src/polisyos/fabric/storage/tenant_cas.py",
    "src/polisyos/fabric/world/events.py",
    "src/polisyos/fabric/world/providers.py",
    "src/polisyos/fabric/world/store/persist.py",
    "src/polisyos/fabric/world/store/segments.py",
)


def _capture_commands(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    calls: list[tuple[list[str], Path]] = []

    def run(
        command: list[str],
        *,
        cwd: Path,
        text: bool,
        capture_output: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert text is True
        assert capture_output is True
        calls.append((command, Path(cwd)))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(core_runtime_basedpyright.subprocess, "run", run)
    return calls


def test_default_command_dispatches_every_current_curated_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_commands(monkeypatch)

    assert core_runtime_basedpyright.main([]) == 0

    common_prefix = [
        "basedpyright",
        "--baselinemode=discard",
        "--project",
        "basedpyright.toml",
    ]
    assert [command for command, _ in calls] == [
        [*common_prefix, *core_runtime_basedpyright.DEFAULT_SCOPE],
        [*common_prefix, *_EXPECTED_CURATED_SCOPE],
    ]
    assert all(cwd == core_runtime_basedpyright.PRODUCT_ROOT for _, cwd in calls)
    assert all(
        (core_runtime_basedpyright.PRODUCT_ROOT / path).is_file()
        for path in _EXPECTED_CURATED_SCOPE
    )
    assert "src/polisyos/fabric/api.py" in _EXPECTED_CURATED_SCOPE
    assert "src/polisyos/fabric/ingestion/__init__.py" in _EXPECTED_CURATED_SCOPE
    assert "src/polisyos/fabric/ingestion/ingestion.py" in _EXPECTED_CURATED_SCOPE
    assert "src/polisyos/fabric/ingestion/ingestion_providers.py" in _EXPECTED_CURATED_SCOPE


def test_missing_curated_owner_fails_before_any_checker_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_commands(monkeypatch)
    missing = "src/polisyos/fabric/missing_owner.py"
    monkeypatch.setattr(
        core_runtime_basedpyright,
        "CURATED_EXTRA_SCOPE",
        (*_EXPECTED_CURATED_SCOPE, missing),
    )

    with pytest.raises(FileNotFoundError, match=missing):
        core_runtime_basedpyright.main([])

    assert calls == []


def test_curated_directory_fails_before_any_checker_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_commands(monkeypatch)
    directory = "src/polisyos/fabric"
    assert (core_runtime_basedpyright.PRODUCT_ROOT / directory).is_dir()
    monkeypatch.setattr(
        core_runtime_basedpyright,
        "CURATED_EXTRA_SCOPE",
        (*_EXPECTED_CURATED_SCOPE, directory),
    )

    with pytest.raises(ValueError, match=directory):
        core_runtime_basedpyright.main([])

    assert calls == []


def test_skip_curated_extras_does_not_resolve_the_skipped_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_commands(monkeypatch)
    monkeypatch.setattr(
        core_runtime_basedpyright,
        "CURATED_EXTRA_SCOPE",
        ("src/polisyos/fabric/missing_owner.py",),
    )

    assert core_runtime_basedpyright.main(["--skip-curated-extras"]) == 0

    assert [command for command, _ in calls] == [
        [
            "basedpyright",
            "--baselinemode=discard",
            "--project",
            "basedpyright.toml",
            *core_runtime_basedpyright.DEFAULT_SCOPE,
        ]
    ]


def test_explicit_paths_dispatch_only_the_requested_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _capture_commands(monkeypatch)

    assert core_runtime_basedpyright.main(["src/polisyos/common"]) == 0

    assert [command for command, _ in calls] == [
        [
            "basedpyright",
            "--baselinemode=discard",
            "--project",
            "basedpyright.toml",
            "src/polisyos/common",
        ]
    ]
