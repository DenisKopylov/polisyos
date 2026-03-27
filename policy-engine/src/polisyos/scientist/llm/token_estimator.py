"""Pre-request token estimation for LLM budget checks."""

from __future__ import annotations

from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in *text*.

    Uses ``tiktoken`` with the ``cl100k_base`` encoding when available,
    otherwise falls back to a character-based heuristic
    (``len(text) // 4``).
    """
    if not text:
        return 0
    try:
        return _tiktoken_count(text)
    except Exception:  # noqa: BLE001
        return max(len(text) // 4, 1)


def estimate_request_tokens(
    *,
    system: str | None = None,
    user: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> int:
    """Estimate total prompt tokens for a chat completion request.

    Accounts for message framing overhead (~4 tokens per message)
    and tool schema serialization.
    """
    total = 0
    if system:
        total += estimate_tokens(system) + 4  # message framing
    if user:
        total += estimate_tokens(user) + 4
    if tools:
        import json
        tools_text = json.dumps(tools)
        total += estimate_tokens(tools_text) + 4
    return max(total, 1)


def _tiktoken_count(text: str) -> int:
    """Count tokens using tiktoken (lazy-loaded)."""
    import tiktoken  # type: ignore[import-untyped]

    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


__all__ = [
    "estimate_tokens",
    "estimate_request_tokens",
]
