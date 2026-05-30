"""Deterministic runtime abuse-resistance gates for canary evidence."""

from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlsplit

SECURITY_ASSURANCE_REPORT_REF_KEY = "security_assurance_report_ref"
SECURITY_REPORT_FILE = "security_assurance_report.json"
SECURITY_REPORT_REF = f"quality_evidence/{SECURITY_REPORT_FILE}"

SECURITY_SURFACES = (
    "llm",
    "tool",
    "data",
    "artifact",
    "runtime_api",
    "dashboard",
)

_SURFACE_STAGE = {
    "llm": "llm",
    "tool": "ops",
    "data": "fabric",
    "artifact": "policy_output",
    "runtime_api": "ops",
    "dashboard": "ops",
}

_SECRET_VALUE_RE = re.compile(
    r"\bsk-(?:live|test|proj)?[a-z0-9][a-z0-9_-]{6,}\b"
    r"|\b(?:ghp|github_pat|hf|xox[baprs])-?[a-z0-9_-]{12,}\b",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}")
_SECRET_ENV_RE = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)[A-Z0-9_]*\b"
)
_PROMPT_INJECTION_RE = re.compile(
    r"\b(ignore|disregard|override)\b.{0,80}\b("
    r"previous|above|system|developer|instructions?|schemas?|tool schemas?"
    r")\b"
    r"|\breveal\b.{0,40}\bsystem prompt\b"
    r"|\bforce\b.{0,60}\bscorecard\b",
    re.IGNORECASE,
)
_SOURCE_OVERRIDE_RE = re.compile(
    r"\b(override|replace|ignore)\b.{0,80}\b("
    r"system instructions?|tool schemas?|approval_status|conflict_status|scorecard"
    r")\b"
    r"|\bset\b.{0,40}\b(conflict_status|approval_status|scorecard)\b",
    re.IGNORECASE,
)
_TOOL_CALL_RE = re.compile(r"(?i)\b(tool_calls?|function_call|approve_release)\b")
_UNSAFE_RENDER_RE = re.compile(
    r"(?is)<\s*script\b|<\s*(iframe|object|embed)\b|<\s*svg\b[^>]*\bon\w+\s*="
    r"|\bon\w+\s*=|javascript\s*:|data\s*:\s*text/html"
)
_URL_RE = re.compile(r"(?i)\b(?:https?|file)://[^\s\"'<>]+")
_PATH_TRAVERSAL_RE = re.compile(
    r"(?i)(?:^|[/\\])\.\.(?:[/\\]|$)|%2e%2e|(?<![A-Za-z0-9_])file://|"
    r"(?:^|[\s:=])/(?:etc/(?:passwd|shadow)|proc/self/environ|var/run/docker\.sock)|"
    r"(?:^|[/\\])\.ssh(?:[/\\]|$)"
)
_EXFIL_ACTION_RE = re.compile(r"(?i)\b(print|show|copy|dump|exfiltrate|leak|reveal)\b")

_ISSUE_TEXT = {
    "prompt_injection_detected": (
        "Untrusted LLM-facing text attempted to override system or scoring instructions.",
        "Quarantine the prompt/source text, preserve it as evidence, and rerun with trusted instructions only.",
        "llm.prompt_injection",
    ),
    "tool_call_injection_detected": (
        "Untrusted content attempted to inject a tool/function call or approval action.",
        "Drop injected tool-call content and require tool invocations from validated schemas only.",
        "tool.tool_call_injection",
    ),
    "malicious_source_content_detected": (
        "Retrieved source content attempted to override system instructions or policy status.",
        "Treat the source as hostile, remove it from retrieval, and rerun source selection.",
        "data.malicious_source_content",
    ),
    "provider_response_poisoning_detected": (
        "Provider output attempted to impersonate privileged roles or mutate governance status.",
        "Discard the provider response, rotate to a clean deterministic fixture, and inspect provider logs.",
        "llm.provider_response_poisoning",
    ),
    "unsafe_artifact_rendering_detected": (
        "Artifact or dashboard content contained active markup that is unsafe to render.",
        "Block rendering, escape the content, and inspect the artifact producer before approval.",
        "artifact.unsafe_rendering",
    ),
    "ssrf_url_blocked": (
        "Runtime or tool payload referenced a local, private, metadata, or file URL.",
        "Block outbound fetches to this target and restrict URL fetches to approved source allowlists.",
        "runtime_api.ssrf",
    ),
    "path_traversal_blocked": (
        "Runtime or artifact payload attempted path traversal or sensitive local file access.",
        "Reject the path and resolve artifacts through CAS identifiers or approved workspace roots only.",
        "runtime_api.path_traversal",
    ),
    "secret_exfiltration_blocked": (
        "A payload attempted to expose a secret, bearer token, API key, credential, or environment value.",
        "Redact the value, rotate any exposed credential, and rerun after removing the exfiltration path.",
        "security.secret_exfiltration",
    ),
}


def redact_sensitive_text(value: str) -> str:
    """Redact secret-like substrings while preserving surrounding operator context."""

    redacted = _BEARER_RE.sub("Bearer [REDACTED_SECRET]", value)
    return _SECRET_VALUE_RE.sub("[REDACTED_SECRET]", redacted)


def build_security_assurance_report(
    *,
    payloads: Mapping[str, Any],
    now: datetime | None = None,
    report_ref: str = SECURITY_REPORT_REF,
) -> dict[str, Any]:
    """Build a deterministic abuse-resistance report from sanitized runtime surfaces."""

    generated_at = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    issues: list[dict[str, Any]] = []
    assured_paths: list[dict[str, Any]] = []

    for surface in SECURITY_SURFACES:
        payload = payloads.get(surface)
        surface_issue_start = len(issues)
        if payload is not None:
            for candidate in _walk_payload(payload):
                _append_candidate_issues(
                    issues,
                    surface=surface,
                    path=candidate.path,
                    key=candidate.key,
                    value=candidate.value,
                )
        surface_issues = issues[surface_issue_start:]
        assured_paths.append(
            {
                "path": surface,
                "status": "fail" if surface_issues else "pass",
                "evidence_ref": f"{report_ref}#/assured_paths/{len(assured_paths)}",
                "issue_count": len(surface_issues),
            }
        )

    for index, issue in enumerate(issues):
        issue["evidence_ref"] = f"{report_ref}#/issues/{index}"

    return {
        "schema_version": "policyos.security_assurance_report.v1",
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        SECURITY_ASSURANCE_REPORT_REF_KEY: report_ref,
        "status": "fail" if issues else "pass",
        "assured_paths": assured_paths,
        "issues": issues,
        "blockers": [dict(issue) for issue in issues],
    }


def security_gates_from_report(report: Any) -> list[dict[str, Any]]:
    """Project one security assurance report into scorecard gate dictionaries."""

    if not isinstance(report, Mapping):
        return []
    report_ref = _clean_ref(report.get(SECURITY_ASSURANCE_REPORT_REF_KEY)) or SECURITY_REPORT_REF
    issues = [dict(issue) for issue in report.get("issues", []) if isinstance(issue, Mapping)]
    if not issues:
        return [
            _gate(
                name="security_assurance_report_passed",
                stage="ops",
                code="security_assurance_passed",
                status="pass",
                phase="security.assurance",
                message="Security assurance gates passed for runtime abuse surfaces.",
                evidence_ref=report_ref,
                next_action=None,
                blocking=False,
            )
        ]

    gates: list[dict[str, Any]] = []
    for issue in issues:
        code = _clean_code(issue.get("code")) or "security_assurance_failed"
        surface = _clean_code(issue.get("surface")) or _surface_from_phase(issue.get("phase"))
        gates.append(
            _gate(
                name=f"security_{surface}_abuse_gate",
                stage=_SURFACE_STAGE.get(surface, "ops"),
                code=code,
                status="fail",
                phase=_clean_text(issue.get("phase")) or "security.assurance",
                message=_clean_text(issue.get("message"))
                or "Security assurance gate failed.",
                evidence_ref=_clean_ref(issue.get("evidence_ref")) or report_ref,
                next_action=_clean_text(issue.get("next_action"))
                or "Inspect security assurance evidence before approval.",
                blocking=True,
            )
        )
    return gates


class _Candidate(tuple):
    __slots__ = ()

    @property
    def path(self) -> str:
        return self[0]

    @property
    def key(self) -> str | None:
        return self[1]

    @property
    def value(self) -> Any:
        return self[2]


def _candidate(path: str, key: str | None, value: Any) -> _Candidate:
    return _Candidate((path, key, value))


def _walk_payload(payload: Any, *, path: str = "$", key: str | None = None) -> Iterable[_Candidate]:
    yield _candidate(path, key, payload)
    if isinstance(payload, Mapping):
        for raw_key, value in payload.items():
            next_key = str(raw_key)
            yield from _walk_payload(value, path=f"{path}.{next_key}", key=next_key)
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from _walk_payload(value, path=f"{path}[{index}]", key=key)


def _append_candidate_issues(
    issues: list[dict[str, Any]],
    *,
    surface: str,
    path: str,
    key: str | None,
    value: Any,
) -> None:
    text = _candidate_text(value)
    normalized_key = (key or "").casefold()
    if text is None:
        return

    lowered = text.casefold()
    if _SECRET_VALUE_RE.search(text) or _BEARER_RE.search(text) or (
        _SECRET_ENV_RE.search(text) and _EXFIL_ACTION_RE.search(text)
    ):
        _append_issue(issues, "secret_exfiltration_blocked", surface, path)

    if _URL_RE.search(text) and any(_unsafe_url(match.group(0)) for match in _URL_RE.finditer(text)):
        _append_issue(issues, "ssrf_url_blocked", surface, path)

    if _PATH_TRAVERSAL_RE.search(unquote(text)):
        _append_issue(issues, "path_traversal_blocked", surface, path)

    if _UNSAFE_RENDER_RE.search(text):
        _append_issue(issues, "unsafe_artifact_rendering_detected", surface, path)

    if surface == "tool" and (_TOOL_CALL_RE.search(text) or _TOOL_CALL_RE.search(normalized_key)):
        _append_issue(issues, "tool_call_injection_detected", surface, path)

    if surface == "data" and _SOURCE_OVERRIDE_RE.search(text):
        _append_issue(issues, "malicious_source_content_detected", surface, path)

    if surface == "llm" and _PROMPT_INJECTION_RE.search(text):
        _append_issue(issues, "prompt_injection_detected", surface, path)

    if surface == "llm" and (
        ("provider_response" in path and _SOURCE_OVERRIDE_RE.search(text))
        or (normalized_key == "role" and lowered in {"system", "developer"})
    ):
        _append_issue(issues, "provider_response_poisoning_detected", surface, path)

    if surface in {"dashboard", "artifact"} and _PROMPT_INJECTION_RE.search(text):
        _append_issue(issues, "prompt_injection_detected", surface, path)


def _candidate_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return None
    return None


def _append_issue(
    issues: list[dict[str, Any]],
    code: str,
    surface: str,
    path: str,
) -> None:
    if any(issue["code"] == code and issue["surface"] == surface for issue in issues):
        return
    message, next_action, phase = _ISSUE_TEXT[code]
    issues.append(
        {
            "code": code,
            "surface": surface,
            "path": path,
            "layer": "security",
            "phase": phase,
            "severity": "high",
            "message": message,
            "retryable": False,
            "retryability": "not_retryable",
            "evidence_ref": None,
            "next_action": next_action,
        }
    )


def _unsafe_url(raw_url: str) -> bool:
    parsed = urlsplit(raw_url)
    if parsed.scheme == "file":
        return True
    hostname = (parsed.hostname or "").strip().casefold()
    if not hostname:
        return False
    if hostname in {"localhost", "metadata", "metadata.google.internal"}:
        return True
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return hostname.endswith(".localhost") or hostname.endswith(".internal")
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def _gate(
    *,
    name: str,
    stage: str,
    code: str,
    status: str,
    phase: str,
    message: str,
    evidence_ref: str | None,
    next_action: str | None,
    blocking: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "stage": stage,
        "code": code,
        "status": status,
        "layer": "security",
        "phase": phase,
        "message": message,
        "evidence_ref": evidence_ref,
        "next_action": next_action,
        "blocking": blocking,
        "retryable": False,
        "retryability": "not_retryable",
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = redact_sensitive_text(str(value)).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    return text


def _clean_ref(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None or len(text) > 256:
        return None
    return text


def _clean_code(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    normalized = text.replace("-", "_").casefold()
    if not re.fullmatch(r"[a-z0-9_]+", normalized):
        return None
    return normalized


def _surface_from_phase(value: Any) -> str:
    phase = _clean_text(value) or ""
    return phase.split(".", 1)[0] if "." in phase else "runtime_api"


__all__ = [
    "SECURITY_ASSURANCE_REPORT_REF_KEY",
    "SECURITY_REPORT_FILE",
    "SECURITY_REPORT_REF",
    "build_security_assurance_report",
    "redact_sensitive_text",
    "security_gates_from_report",
]
