"""Timeout helpers for Scientist agent LLM calls."""

from __future__ import annotations

import os


def resolve_agent_llm_timeout_s(env_name: str, *, default: float) -> float:
    """Resolve a bounded per-agent LLM timeout from environment variables."""

    raw = os.getenv(env_name)
    if raw is None:
        raw = os.getenv("POLISYOS_AGENT_LLM_TIMEOUT_S")
    if raw is None:
        return max(float(default), 1.0)
    try:
        return max(float(raw.strip()), 1.0)
    except ValueError:
        return max(float(default), 1.0)


__all__ = ["resolve_agent_llm_timeout_s"]
