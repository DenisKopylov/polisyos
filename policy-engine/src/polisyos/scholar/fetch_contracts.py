"""Shared typed outcomes for Scholar raw-fetch adapters."""

from __future__ import annotations

from typing import Literal

type FetchFailureReason = Literal[
    "blocked_private_network",
    "blocked_domain",
    "blocked_content_type",
    "max_bytes_exceeded",
    "redirect_error",
    "timeout",
    "http_error",
    "transport_error",
    "paywall",
    "inaccessible_text",
]
