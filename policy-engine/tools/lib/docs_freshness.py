"""Shared admission rules for docs-freshness baselines and checker output."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VIOLATION_SUMMARY_RE = re.compile(r"- violations:\s+([0-9]+)")


@dataclass(frozen=True)
class DocsFreshnessBaseline:
    """Hold the validated fields used to admit a docs-freshness observation."""

    findings: tuple[str, ...]
    expected_violation_count: int | None
    baseline_sha256: str


def validate_docs_freshness_baseline(
    baseline: Mapping[str, object], *, today: dt.date | None = None
) -> DocsFreshnessBaseline:
    """Validate baseline fields without coercing malformed values into authority."""
    findings: list[str] = []
    if baseline.get("mode") != "fail_closed_baseline":
        findings.append("docs freshness mode is not fail_closed_baseline")
    for field in ("owner", "reason", "command", "issue"):
        value = baseline.get(field)
        if not isinstance(value, str) or not value.strip():
            findings.append(f"docs freshness baseline missing `{field}`")

    raw_expiry = baseline.get("expires")
    expires: dt.date | None = None
    if type(raw_expiry) is dt.date:
        expires = raw_expiry
    elif isinstance(raw_expiry, str) and raw_expiry.strip():
        with suppress(ValueError):
            expires = dt.date.fromisoformat(raw_expiry.strip())
    if expires is None:
        findings.append("docs freshness baseline has invalid `expires`")

    raw_count = baseline.get("expected_violation_count")
    expected_count = raw_count if type(raw_count) is int and raw_count >= 0 else None
    if expected_count is None:
        findings.append("expected_violation_count must be non-negative")

    current_date = today or dt.date.today()
    if expires is not None and expires < current_date and expected_count != 0:
        findings.append("docs freshness exception baseline expired")

    raw_digest = baseline.get("baseline_sha256")
    digest = raw_digest.strip() if isinstance(raw_digest, str) else ""
    if expected_count is not None and expected_count > 0 and (not digest or digest == "pending"):
        findings.append("docs freshness baseline hash is pending")
    elif raw_digest is not None and not SHA256_RE.fullmatch(digest):
        findings.append("docs freshness baseline hash is not sha256")

    return DocsFreshnessBaseline(tuple(findings), expected_count, digest)


def extract_docs_freshness_violation_count(output: str) -> int | None:
    """Read one exact violation summary; missing or ambiguous summaries are unknown."""
    summaries = [line for line in output.splitlines() if line.startswith("- violations:")]
    if len(summaries) != 1:
        return None
    match = _VIOLATION_SUMMARY_RE.fullmatch(summaries[0])
    if match is None:
        return None
    return int(match.group(1))


def evaluate_docs_freshness_observation(
    *,
    expected_count: int,
    expected_digest: str,
    returncode: int,
    output: str,
) -> tuple[str, ...]:
    """Apply the same zero-debt and positive-exception rules to both callers."""
    findings: list[str] = []
    observed_count = extract_docs_freshness_violation_count(output)
    digest = hashlib.sha256(output.encode("utf-8")).hexdigest()
    if observed_count is None:
        findings.append("docs accuracy output is missing or has a malformed violation count")

    if expected_count == 0:
        if returncode != 0:
            findings.append("docs accuracy failed with a zero-debt baseline")
        elif observed_count is not None and observed_count != 0:
            findings.append("docs accuracy reported violations despite a successful check")
        return tuple(findings)

    if returncode == 0:
        findings.append("docs accuracy is clean but baseline still expects violations")
        return tuple(findings)
    if observed_count is not None and observed_count != expected_count:
        findings.append(
            "docs freshness violation count changed: "
            f"expected {expected_count}, observed {observed_count}"
        )
    if digest != expected_digest:
        findings.append(
            f"docs freshness baseline hash changed: expected {expected_digest}, observed {digest}"
        )
    return tuple(findings)
