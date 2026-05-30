"""Factory and compatibility node for drafter implementations."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.scientist.agent.code_verifier import CodeVerificationSandbox, SandboxConfig
from polisyos.scientist.agent.protocols import DrafterAgent
from polisyos.scientist.agent.rag import (
    CASRAGIndex,
    RAGConfig,
    build_default_embedder,
    build_or_load_rag_index,
)

from .drafter_clients import LLMDrafterAgent, MockDrafterAgent
from .drafter_models import MultiPassConfig
from .drafter_multipass import MultiPassLLMDrafter

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.loading.norm_pack import NormPack
    from polisyos.scientist.agent.constitution import ConstitutionGenerator
    from polisyos.scientist.agent.knowledge_base import CriticKnowledgeBase
    from polisyos.scientist.agent.memory import ShortTermMemory

logger = get_logger(__name__)

_DRAFTER_RAG_INIT_ERRORS = (
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _build_rag_filesystem_store(root: Path) -> FileSystemCAS:
    store = build_artifact_store(
        ArtifactStoreConfig(backend="filesystem", root=str(root)),
    )
    return cast("FileSystemCAS", store)


def create_drafter_agent(
    llm_client: Any,
    *,
    model_name: str | None = None,
    memory: ShortTermMemory | None = None,
    config: MultiPassConfig | None = None,
    constitution_generator: ConstitutionGenerator | None = None,
    knowledge_base: CriticKnowledgeBase | None = None,
    constitution_norm_pack: NormPack | None = None,
    constitution_model_spec: ModelSpec | None = None,
    rag_store_factory: Callable[[Path], FileSystemCAS] | None = None,
) -> DrafterAgent:
    """
    Build drafter according to feature flag `POLISYOS_DRAFTER_MULTIPASS_MODE`.

    Modes:
    - off (default): LLMDrafterAgent
    - active: MultiPassLLMDrafter
    - shadow: MultiPassLLMDrafter with shadow_mode=True
    """
    mode = os.getenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "off").strip().lower()
    inner = LLMDrafterAgent(llm_client, model_name=model_name)
    if mode not in {"active", "shadow"}:
        return inner

    effective_config = config or MultiPassConfig.from_env()
    if mode == "shadow" and not effective_config.shadow_mode:
        effective_config = effective_config.model_copy(update={"shadow_mode": True})

    rag_config: RAGConfig | None = None
    rag_index: CASRAGIndex | None = None
    if effective_config.rag_enabled:
        rag_config = RAGConfig.from_env().model_copy(
            update={
                "enabled": True,
                "top_k": effective_config.rag_top_k,
                "similarity_threshold": effective_config.rag_similarity_threshold,
                "domain_filter": effective_config.rag_domain_filter,
                "max_few_shot_chars": effective_config.rag_max_few_shot_chars,
                "freeze_snapshot_per_run": effective_config.rag_freeze_snapshot_per_run,
            }
        )
        try:
            cas = (rag_store_factory or _build_rag_filesystem_store)(Path(rag_config.cas_root))
            embedder = build_default_embedder(rag_config)
            rag_index = build_or_load_rag_index(
                cas,
                config=rag_config,
                embedder=embedder,
            )
        except _DRAFTER_RAG_INIT_ERRORS as exc:
            logger.warning("RAG initialization failed, continuing without RAG: %s", exc)
            rag_index = None

    verifier: CodeVerificationSandbox | None = None
    if effective_config.code_verification_enabled:
        verifier = CodeVerificationSandbox(
            SandboxConfig(timeout_seconds=effective_config.code_verification_timeout_s)
        )

    return MultiPassLLMDrafter(
        inner,
        config=effective_config,
        memory=memory,
        rag_index=rag_index,
        rag_config=rag_config,
        code_verifier=verifier,
        constitution_generator=constitution_generator,
        knowledge_base=knowledge_base,
        constitution_norm_pack=constitution_norm_pack,
        constitution_model_spec=constitution_model_spec,
    )


def drafter_node(state: Any) -> Any:
    """
    Backward-compatible no-op node.

    Legacy LangGraph node flow was removed; canonical Scientist path uses engine DAG.
    """
    return state


def _verify_protocol() -> None:
    agent = MockDrafterAgent()
    if not isinstance(agent, DrafterAgent):
        raise TypeError("MockDrafterAgent does not implement DrafterAgent protocol")


_verify_protocol()

__all__ = ["create_drafter_agent", "drafter_node"]
