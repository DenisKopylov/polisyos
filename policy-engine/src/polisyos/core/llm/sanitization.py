"""First-party prompt/result sanitization with stable reversible placeholders."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "PromptSanitizer",
    "SanitizationRule",
]


@dataclass(frozen=True, slots=True)
class SanitizationRule:
    """One regex-based secret/PII redaction rule."""

    label: str
    pattern: re.Pattern[str]


_DEFAULT_RULES: tuple[SanitizationRule, ...] = (
    SanitizationRule(
        label="bearer_token",
        pattern=re.compile(r"\bBearer\s+([A-Za-z0-9._~+\-/=]{16,})"),
    ),
    SanitizationRule(
        label="openai_like_key",
        pattern=re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,})\b"),
    ),
    SanitizationRule(
        label="aws_access_key",
        pattern=re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    ),
    SanitizationRule(
        label="email",
        pattern=re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b"),
    ),
    SanitizationRule(
        label="db_url",
        pattern=re.compile(
            r"\b((?:postgres(?:ql)?|mysql|redis|mongodb)://[^\s'\"]+)",
            re.IGNORECASE,
        ),
    ),
    SanitizationRule(
        label="password_assignment",
        pattern=re.compile(
            r"\b((?:password|passwd|api_key|secret|token)\s*[:=]\s*)([^\s'\"]{8,})",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class PromptSanitizer:
    """Stateful sanitizer with stable placeholder mapping across turns."""

    placeholder_prefix: str = "POLISYOS_SECRET"
    rules: tuple[SanitizationRule, ...] = _DEFAULT_RULES
    _secret_to_placeholder: dict[str, str] = field(default_factory=dict, init=False)
    _placeholder_to_secret: dict[str, str] = field(default_factory=dict, init=False)

    def sanitize_text(self, text: str) -> str:
        """Replace sensitive values with stable placeholders."""
        if not text:
            return text
        sanitized = text
        for rule in self.rules:
            sanitized = self._apply_rule(sanitized, rule)
        return sanitized

    def restore_text(self, text: str) -> str:
        """Restore placeholders back to original values."""
        if not text:
            return text
        restored = text
        for placeholder, secret in self._placeholder_to_secret.items():
            restored = restored.replace(placeholder, secret)
        return restored

    def sanitize_payload(self, value: Any) -> Any:
        """Recursively sanitize strings in dict/list payloads."""
        if isinstance(value, str):
            return self.sanitize_text(value)
        if isinstance(value, list):
            return [self.sanitize_payload(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.sanitize_payload(item) for item in value)
        if isinstance(value, dict):
            return {
                key: self.sanitize_payload(item)
                for key, item in value.items()
            }
        return value

    def restore_payload(self, value: Any) -> Any:
        """Recursively restore placeholders in dict/list payloads."""
        if isinstance(value, str):
            return self.restore_text(value)
        if isinstance(value, list):
            return [self.restore_payload(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.restore_payload(item) for item in value)
        if isinstance(value, dict):
            return {
                key: self.restore_payload(item)
                for key, item in value.items()
            }
        return value

    def sanitize_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sanitize OpenAI-style chat messages while preserving structure."""
        return self.sanitize_payload(copy.deepcopy(messages))

    def restore_response(self, response: Any) -> Any:
        """Restore placeholders in normalized gateway responses or generic payloads."""
        if response is None:
            return None
        if hasattr(response, "content"):
            try:
                response.content = self.restore_text(str(response.content or ""))
            except (AttributeError, TypeError, ValueError):
                pass
        if hasattr(response, "tool_calls") and getattr(response, "tool_calls") is not None:
            try:
                for tool_call in response.tool_calls:
                    if hasattr(tool_call, "arguments"):
                        tool_call.arguments = self.restore_payload(tool_call.arguments)
            except (AttributeError, TypeError, ValueError):
                pass
        if hasattr(response, "raw"):
            try:
                response.raw = self.restore_payload(response.raw)
            except (AttributeError, TypeError, ValueError):
                pass
        if isinstance(response, str):
            return self.restore_text(response)
        if isinstance(response, (dict, list, tuple)):
            return self.restore_payload(response)
        return response

    def placeholder_map(self) -> dict[str, str]:
        """Return a copy of the placeholder -> original secret map."""
        return dict(self._placeholder_to_secret)

    def _apply_rule(self, text: str, rule: SanitizationRule) -> str:
        def _replace(match: re.Match[str]) -> str:
            secret = match.group(match.lastindex or 0)
            placeholder = self._placeholder_for(rule.label, secret)
            if rule.label == "bearer_token":
                return f"Bearer {placeholder}"
            if rule.label == "password_assignment" and (match.lastindex or 0) >= 2:
                return f"{match.group(1)}{placeholder}"
            return placeholder

        return rule.pattern.sub(_replace, text)

    def _placeholder_for(self, label: str, secret: str) -> str:
        existing = self._secret_to_placeholder.get(secret)
        if existing:
            return existing
        digest = hashlib.sha256(f"{label}:{secret}".encode("utf-8")).hexdigest()[:16]
        placeholder = f"[{self.placeholder_prefix}_{label.upper()}_{digest}]"
        self._secret_to_placeholder[secret] = placeholder
        self._placeholder_to_secret[placeholder] = secret
        return placeholder
