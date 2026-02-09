"""Compatibility bridge to the consolidated core LLM layer."""

from polisyos.core.llm.traced_client import LLMClientProtocol, TracedLLMClient

__all__ = [
    "LLMClientProtocol",
    "TracedLLMClient",
]

