"""First-party prompt/result sanitization with stable reversible placeholders."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "SECRET_AND_PII_SCAN_SCOPES",
    "SECRET_PII_DETECTOR_VERSION",
    "PromptSanitizer",
    "SanitizationRule",
    "SecretAndPIIScanReport",
    "SecretPIIScanResult",
    "scan_secret_and_pii",
]


SECRET_PII_DETECTOR_VERSION = "polisyos.core.llm.sanitization.v1"  # noqa: S105
SECRET_AND_PII_SCAN_SCOPES: tuple[str, ...] = (
    "DAG bundles",
    "connector request/response payloads",
    "CAS manifests",
    "raw artifact content/download routes",
    "dashboard/public/export packets",
)


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
_SENSITIVE_KEY_NAMES = {
    "access_key",
    "access_token",
    "api_key",
    "apikey",
    "auth_credentials",
    "auth_token",
    "authorization",
    "bearer_token",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "passwd",
    "private_prompt",
    "private_reviewer",
    "provider_config",
    "provider_credential",
    "raw_records",
    "raw_sensitive",
    "raw_source",
    "raw_transcript",
    "restricted_source",
    "reviewer_private",
    "private_key",
    "refresh_token",
    "sealed_battery",
    "sealed_case_payload",
    "sealed_fixture",
    "sealed_fixture_contents",
    "sensitive_data",
    "source_material",
    "secret",
    "secret_key",
    "system_prompt",
    "tenant",
    "tenant_id",
    "token",
    "gold_label",
    "gold_labels",
    "weak_gold_answer",
    "expert_oracle_private_notes",
    "oracle_private_notes",
    "answer_key",
    "benchmark_answer",
    "hidden_answer",
    "hidden_benchmark",
    "hidden_benchmark_answer",
    "hidden_eval",
    "hidden_holdout",
    "hidden_case_payload",
    "restricted_source_material",
}
_SENSITIVE_KEY_SUFFIXES = (
    "_access_key",
    "_api_key",
    "_credentials",
    "_credential",
    "_password",
    "_private_key",
    "_secret",
    "_token",
)


class SecretAndPIIScanReport(BaseModel):
    """Proof-packet record for one secret/PII scan outcome."""

    model_config = ConfigDict(extra="forbid")

    scope: str
    artifact_ref_or_route: str
    detector_version: str = SECRET_PII_DETECTOR_VERSION
    finding_kind: str
    redaction_applied: bool
    authority_surface_blocked: bool
    negative_fixture_result: str


class SecretPIIScanResult(BaseModel):
    """Internal scan result carrying redacted payload plus proof records."""

    model_config = ConfigDict(extra="forbid")

    redacted_payload: Any = None
    reports: list[SecretAndPIIScanReport] = Field(default_factory=list)
    finding_kinds: list[str] = Field(default_factory=list)
    has_findings: bool = False


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

    def finding_kinds_in_text(self, text: str) -> list[str]:
        """Return detector labels found in a text payload."""
        if not text:
            return []
        kinds: list[str] = []
        for rule in self.rules:
            if rule.pattern.search(text):
                kinds.append(rule.label)
        return kinds

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
                key: self._sanitize_keyed_value(str(key), item) for key, item in value.items()
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
            return {key: self.restore_payload(item) for key, item in value.items()}
        return value

    def sanitize_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sanitize OpenAI-style chat messages while preserving structure."""
        sanitized = self.sanitize_payload(copy.deepcopy(messages))
        if not isinstance(sanitized, list):
            raise TypeError("sanitized messages must remain a list")
        result: list[dict[str, Any]] = []
        for item in sanitized:
            if not isinstance(item, dict) or not all(isinstance(key, str) for key in item):
                raise TypeError("sanitized messages must contain string-keyed dictionaries")
            result.append(dict(item))
        return result

    def restore_response(self, response: Any) -> Any:
        """Restore placeholders in normalized gateway responses or generic payloads."""
        if response is None:
            return None
        if hasattr(response, "content"):
            with suppress(AttributeError, TypeError, ValueError):
                response.content = self.restore_text(str(response.content or ""))
        if hasattr(response, "tool_calls") and response.tool_calls is not None:
            try:
                for tool_call in response.tool_calls:
                    if hasattr(tool_call, "arguments"):
                        tool_call.arguments = self.restore_payload(tool_call.arguments)
            except (AttributeError, TypeError, ValueError):
                pass
        if hasattr(response, "raw"):
            with suppress(AttributeError, TypeError, ValueError):
                response.raw = self.restore_payload(response.raw)
        if isinstance(response, str):
            return self.restore_text(response)
        if isinstance(response, (dict, list, tuple)):
            return self.restore_payload(response)
        return response

    def placeholder_map(self) -> dict[str, str]:
        """Return a copy of the placeholder -> original secret map."""
        return dict(self._placeholder_to_secret)

    def keyed_value_finding_kind(self, key: str, value: Any) -> str | None:
        """Return a structured-field finding when a sensitive key carries a value."""
        if not _is_sensitive_key(key):
            return None
        if value in (None, "", [], {}, ()):
            return None
        return "keyed_secret"

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

    def _sanitize_keyed_value(self, key: str, value: Any) -> Any:
        if self.keyed_value_finding_kind(key, value):
            secret = value if isinstance(value, str) else _stable_secret_text(value)
            return self._placeholder_for("keyed_secret", secret)
        return self.sanitize_payload(value)

    def _placeholder_for(self, label: str, secret: str) -> str:
        existing = self._secret_to_placeholder.get(secret)
        if existing:
            return existing
        digest = hashlib.sha256(f"{label}:{secret}".encode()).hexdigest()[:16]
        placeholder = f"[{self.placeholder_prefix}_{label.upper()}_{digest}]"
        self._secret_to_placeholder[secret] = placeholder
        self._placeholder_to_secret[placeholder] = secret
        return placeholder


def scan_secret_and_pii(
    value: Any,
    *,
    scope: str,
    artifact_ref_or_route: str,
    sanitizer: PromptSanitizer | None = None,
    redact: bool = True,
    block_on_findings: bool = False,
) -> SecretPIIScanResult:
    """Scan a public/raw payload and return exact GY-F2 proof records.

    Args:
        value: Bytes, text, or JSON-like payload to scan.
        scope: One of the GY-F2 declared scan scopes.
        artifact_ref_or_route: Artifact reference or route identifier being scanned.
        sanitizer: Optional stateful sanitizer; defaults to `PromptSanitizer`.
        redact: Whether the returned payload should replace findings with placeholders.
        block_on_findings: Whether callers blocked the authority/public surface on findings.

    Returns:
        A scan result with strict `SecretAndPIIScanReport` records.
    """

    if scope not in SECRET_AND_PII_SCAN_SCOPES:
        raise ValueError(f"unknown secret/PII scan scope: {scope}")
    active = sanitizer or PromptSanitizer()
    finding_kinds = sorted(set(_collect_finding_kinds(value, active)))
    has_findings = bool(finding_kinds)
    redacted_payload = _redact_payload(value, active) if redact else value
    redaction_applied = bool(redact and has_findings and redacted_payload != value)
    negative_fixture_result = _negative_fixture_result(
        has_findings=has_findings,
        redaction_applied=redaction_applied,
        authority_surface_blocked=block_on_findings and has_findings,
    )
    reports = [
        SecretAndPIIScanReport(
            scope=scope,
            artifact_ref_or_route=artifact_ref_or_route,
            finding_kind=finding_kind,
            redaction_applied=redaction_applied,
            authority_surface_blocked=block_on_findings and has_findings,
            negative_fixture_result=negative_fixture_result,
        )
        for finding_kind in (finding_kinds or ["none"])
    ]
    return SecretPIIScanResult(
        redacted_payload=redacted_payload,
        reports=reports,
        finding_kinds=finding_kinds,
        has_findings=has_findings,
    )


def _collect_finding_kinds(value: Any, sanitizer: PromptSanitizer) -> list[str]:
    if isinstance(value, bytes):
        return sanitizer.finding_kinds_in_text(value.decode("utf-8", errors="ignore"))
    if isinstance(value, str):
        return sanitizer.finding_kinds_in_text(value)
    if isinstance(value, dict):
        kinds: list[str] = []
        for key, item in value.items():
            kinds.extend(_collect_finding_kinds(str(key), sanitizer))
            keyed_kind = sanitizer.keyed_value_finding_kind(str(key), item)
            if keyed_kind is not None:
                kinds.append(keyed_kind)
            kinds.extend(_collect_finding_kinds(item, sanitizer))
        return kinds
    if isinstance(value, (list, tuple, set, frozenset)):
        kinds = []
        for item in value:
            kinds.extend(_collect_finding_kinds(item, sanitizer))
        return kinds
    return []


def _redact_payload(value: Any, sanitizer: PromptSanitizer) -> Any:
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError:
            text = value.decode("utf-8", errors="ignore")
            return sanitizer.sanitize_text(text).encode("utf-8")
        return sanitizer.sanitize_text(text).encode("utf-8")
    return sanitizer.sanitize_payload(copy.deepcopy(value))


def _negative_fixture_result(
    *,
    has_findings: bool,
    redaction_applied: bool,
    authority_surface_blocked: bool,
) -> str:
    if not has_findings:
        return "clean"
    if authority_surface_blocked:
        return "blocked"
    if redaction_applied:
        return "redacted"
    return "finding_detected"


def _is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    compact = normalized.replace("_", "")
    if normalized in _SENSITIVE_KEY_NAMES or compact in _SENSITIVE_KEY_NAMES:
        return True
    return any(normalized.endswith(suffix) for suffix in _SENSITIVE_KEY_SUFFIXES)


def _stable_secret_text(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return repr(value)
