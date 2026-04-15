from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.drafter_factory import create_drafter_agent
from polisyos.scientist.agent.drafter_models import MultiPassConfig
from polisyos.scientist.agent.drafter_multipass import MultiPassLLMDrafter


class _StubClient:
    async def generate(self, **kwargs: Any) -> object:
        del kwargs
        return object()


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
