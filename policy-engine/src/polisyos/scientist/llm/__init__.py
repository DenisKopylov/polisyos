"""LLM utilities for Scientist agents."""

from .traced_client import LLMClientProtocol, TracedLLMClient

__all__ = [
    "LLMClientProtocol",
    "TracedLLMClient",
]
