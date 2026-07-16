from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
from polisyos.scientist.agent.drafter_factory import create_drafter_agent
from polisyos.scientist.agent.drafter_models import MultiPassConfig
from polisyos.scientist.agent.drafter_multipass import MultiPassLLMDrafter


class _StubClient:
    async def generate(self, **kwargs: Any) -> object:
        del kwargs
        return object()


def test_explicit_multipass_mode_overrides_environment(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "off")

    active = create_drafter_agent(
        _StubClient(),
        config=MultiPassConfig(max_passes=1),
        multipass_mode="active",
    )

    assert isinstance(active, MultiPassLLMDrafter)

    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "active")
    off = create_drafter_agent(_StubClient(), multipass_mode="off")

    assert isinstance(off, LLMDrafterAgent)


def test_explicit_unknown_multipass_mode_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported_drafter_multipass_mode"):
        create_drafter_agent(_StubClient(), multipass_mode="invented")  # type: ignore[arg-type]


def test_create_drafter_agent_uses_injected_rag_store_factory(
    monkeypatch,
    tmp_path,
) -> None:
    seen_roots: list[str] = []

    def _store_factory(root):
        seen_roots.append(str(root))
        return FileSystemCAS(tmp_path / "rag-store")

    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "active")
    agent = create_drafter_agent(
        _StubClient(),
        config=MultiPassConfig(max_passes=1, rag_enabled=True),
        rag_store_factory=_store_factory,
    )

    assert isinstance(agent, MultiPassLLMDrafter)
    assert len(seen_roots) == 1


def test_create_drafter_agent_rag_assertion_is_not_swallowed(
    monkeypatch,
    tmp_path,
) -> None:
    def _store_factory(root):
        del root
        return FileSystemCAS(tmp_path / "rag-store")

    def _boom(cas, *, config, embedder):
        del cas, config, embedder
        raise AssertionError("rag bootstrap invariant failed")

    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "active")
    monkeypatch.setattr(
        "polisyos.scientist.agent.drafter_factory.build_or_load_rag_index",
        _boom,
    )

    with pytest.raises(AssertionError, match="rag bootstrap invariant failed"):
        create_drafter_agent(
            _StubClient(),
            config=MultiPassConfig(max_passes=1, rag_enabled=True),
            rag_store_factory=_store_factory,
        )
