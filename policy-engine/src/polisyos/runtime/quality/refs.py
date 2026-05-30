"""Runtime quality-ref discovery across canary and control payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

REQUIRED_QUALITY_REF_KEYS = (
    "production_data_quality_report_ref",
    "normative_applicability_report_ref",
    "fabric_retrieval_trace_ref",
    "foundry_method_report_ref",
    "policy_grounding_matrix_ref",
    "conflict_check_ref",
)
LIFECYCLE_QUALITY_REF_KEYS = (
    "continuous_governance_stale_report_ref",
    "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw_report_ref",
)
KNOWN_QUALITY_REF_KEYS = (*REQUIRED_QUALITY_REF_KEYS, *LIFECYCLE_QUALITY_REF_KEYS)

_KNOWN_QUALITY_REF_KEY_SET = set(KNOWN_QUALITY_REF_KEYS)
_GENERIC_REF_VALUE_KEYS = (
    "artifact_id",
    "artifact_ref",
    "ref",
    "value",
    "uri",
)
_GENERIC_REF_HINT_KEYS = (
    "name",
    "key",
    "role",
    "type",
    "kind",
    "label",
)
_SECRET_MARKERS = (
    "access_token",
    "api_key",
    "bearer ",
    "credential",
    "password",
    "refresh_token",
    "secret",
    "token",
)
_QUALITY_REF_HINTS = {
    "production_data_quality": "production_data_quality_report_ref",
    "production.data_quality": "production_data_quality_report_ref",
    "data_quality_report": "production_data_quality_report_ref",
    "normative_applicability": "normative_applicability_report_ref",
    "normative.applicability": "normative_applicability_report_ref",
    "applicability_report": "normative_applicability_report_ref",
    "fabric_retrieval_trace": "fabric_retrieval_trace_ref",
    "fabric.retrieval_trace": "fabric_retrieval_trace_ref",
    "retrieval_trace": "fabric_retrieval_trace_ref",
    "foundry_method_report": "foundry_method_report_ref",
    "foundry.method_report": "foundry_method_report_ref",
    "method_quality_report": "foundry_method_report_ref",
    "policy_grounding_matrix": "policy_grounding_matrix_ref",
    "policy.grounding_matrix": "policy_grounding_matrix_ref",
    "grounding_matrix": "policy_grounding_matrix_ref",
    "conflict_check": "conflict_check_ref",
    "policy_conflict_check": "conflict_check_ref",
    "continuous_governance_stale": "continuous_governance_stale_report_ref",
    "governance_lifecycle_stale": "continuous_governance_stale_report_ref",
    "continuous_governance_reissue": "continuous_governance_reissue_report_ref",
    "governance_lifecycle_reissue": "continuous_governance_reissue_report_ref",
    "continuous_governance_supersede": "continuous_governance_supersede_report_ref",
    "governance_lifecycle_supersede": "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw": "continuous_governance_withdraw_report_ref",
    "governance_lifecycle_withdraw": "continuous_governance_withdraw_report_ref",
}


@dataclass(frozen=True)
class QualityRefMatch:
    """One accepted quality-ref discovery candidate."""

    key: str
    value: str
    source: str
    path: str

    def to_evidence(self) -> dict[str, str]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "path": self.path,
        }


@dataclass(frozen=True)
class QualityRefResolution:
    """Resolved runtime quality refs plus stable missing-evidence diagnostics."""

    refs: dict[str, str]
    matches: tuple[QualityRefMatch, ...]
    missing: tuple[str, ...]
    missing_evidence: tuple[dict[str, str], ...]

    def to_evidence(self) -> dict[str, Any]:
        return {
            "status": "complete" if not self.missing else "missing",
            "required": list(REQUIRED_QUALITY_REF_KEYS),
            "refs": dict(self.refs),
            "matches": [match.to_evidence() for match in self.matches],
            "missing": list(self.missing),
            "missing_evidence": [dict(item) for item in self.missing_evidence],
        }


@dataclass(frozen=True)
class RuntimeQualityAuthorityRefs:
    """Typed authority refs read from runtime-owned surfaces only.

    This intentionally avoids recursive payload discovery. Compatibility
    projections may still carry direct `*_ref` keys, but authority readers only
    trust explicitly typed runtime surfaces.
    """

    refs: dict[str, str]
    sources: dict[str, str]

    @classmethod
    def from_runtime_payloads(
        cls,
        *,
        job_payload: Mapping[str, Any] | None = None,
        run_payload: Mapping[str, Any] | None = None,
        quality_evidence: Mapping[str, Any] | None = None,
    ) -> RuntimeQualityAuthorityRefs:
        refs: dict[str, str] = {}
        sources: dict[str, str] = {}

        def add_mapping(mapping: Any, *, source: str) -> None:
            if not isinstance(mapping, Mapping):
                return
            for raw_key, raw_value in mapping.items():
                key = str(raw_key)
                if not key.endswith("_ref"):
                    continue
                value = _coerce_ref_value(raw_value)
                if value is None:
                    continue
                refs.setdefault(key, value)
                sources.setdefault(key, source)

        for label, payload in (
            ("job", job_payload),
            ("run", run_payload),
        ):
            if not isinstance(payload, Mapping):
                continue
            add_mapping(payload.get("runtime_quality_refs"), source=f"{label}.runtime_quality_refs")
            progress = payload.get("progress")
            if isinstance(progress, Mapping):
                add_mapping(
                    progress.get("runtime_quality_refs"),
                    source=f"{label}.progress.runtime_quality_refs",
                )
                details = progress.get("details")
                if isinstance(details, Mapping):
                    add_mapping(
                        details.get("runtime_quality_refs"),
                        source=f"{label}.progress.details.runtime_quality_refs",
                    )
            details = payload.get("details")
            if isinstance(details, Mapping):
                add_mapping(
                    details.get("runtime_quality_refs"),
                    source=f"{label}.details.runtime_quality_refs",
                )

        if isinstance(quality_evidence, Mapping):
            add_mapping(
                quality_evidence.get("runtime_quality_refs"),
                source="quality_evidence.runtime_quality_refs",
            )
            for report_key, report in quality_evidence.items():
                if not isinstance(report, Mapping):
                    continue
                ref_key = _quality_ref_key_from_mapping(report) or _quality_ref_key_from_text(
                    report_key
                )
                ref_value = _coerce_ref_value(
                    report.get("ref")
                    or report.get("cas_ref")
                    or report.get("artifact_ref")
                    or (report.get(ref_key) if ref_key is not None else None)
                )
                if ref_key is not None and ref_value is not None:
                    refs.setdefault(ref_key, ref_value)
                    sources.setdefault(ref_key, f"quality_evidence.{report_key}")
                add_mapping(report, source=f"quality_evidence.{report_key}")
                envelope = report.get("authority_envelope")
                if isinstance(envelope, Mapping):
                    envelope_ref_key = ref_key or _quality_ref_key_from_text(report_key)
                    envelope_ref = _coerce_ref_value(
                        envelope.get("cas_ref") or envelope.get("artifact_ref")
                    )
                    if envelope_ref_key is not None and envelope_ref is not None:
                        refs.setdefault(envelope_ref_key, envelope_ref)
                        sources.setdefault(
                            envelope_ref_key,
                            f"quality_evidence.{report_key}.authority_envelope",
                        )

        return cls(refs=refs, sources=sources)

    def get(self, key: str) -> str | None:
        return self.refs.get(key)

    def missing_required(self) -> tuple[str, ...]:
        return tuple(key for key in REQUIRED_QUALITY_REF_KEYS if key not in self.refs)

    def to_evidence(self) -> dict[str, Any]:
        return {
            "refs": dict(self.refs),
            "sources": dict(self.sources),
            "missing": list(self.missing_required()),
        }


def resolve_quality_refs(
    *,
    run_params: Any | None = None,
    artifacts: Any | None = None,
    timeline: Any | None = None,
    lineage: Any | None = None,
    control_progress: Any | None = None,
) -> QualityRefResolution:
    """Discover required runtime quality refs from known run evidence surfaces."""

    sources = (
        ("control_progress", control_progress),
        ("run_params", run_params),
        ("artifacts", artifacts),
        ("timeline", timeline),
        ("lineage", lineage),
    )
    found: dict[str, QualityRefMatch] = {}
    for source_name, payload in sources:
        for match in _iter_quality_ref_matches(payload, source=source_name, path="$"):
            found.setdefault(match.key, match)

    refs = {key: found[key].value for key in KNOWN_QUALITY_REF_KEYS if key in found}
    matches = tuple(found[key] for key in KNOWN_QUALITY_REF_KEYS if key in found)
    missing = tuple(key for key in REQUIRED_QUALITY_REF_KEYS if key not in refs)
    missing_evidence = tuple(_missing_evidence(key) for key in missing)
    return QualityRefResolution(
        refs=refs,
        matches=matches,
        missing=missing,
        missing_evidence=missing_evidence,
    )


def _iter_quality_ref_matches(
    payload: Any,
    *,
    source: str,
    path: str,
) -> Iterable[QualityRefMatch]:
    if isinstance(payload, Mapping):
        hinted_key = _quality_ref_key_from_mapping(payload)
        if hinted_key is not None:
            value = _coerce_ref_value_from_mapping(payload)
            if value is not None:
                yield QualityRefMatch(
                    key=hinted_key,
                    value=value,
                    source=source,
                    path=path,
                )

        for raw_key, value in payload.items():
            key = str(raw_key)
            if key == "optional_runtime_quality_refs":
                continue
            next_path = f"{path}.{key}"
            if key in _KNOWN_QUALITY_REF_KEY_SET:
                ref_value = _coerce_ref_value(value)
                if ref_value is not None:
                    yield QualityRefMatch(
                        key=key,
                        value=ref_value,
                        source=source,
                        path=next_path,
                    )
                    continue
            yield from _iter_quality_ref_matches(value, source=source, path=next_path)
        return

    if isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            yield from _iter_quality_ref_matches(
                value,
                source=source,
                path=f"{path}[{index}]",
            )


def _quality_ref_key_from_mapping(payload: Mapping[Any, Any]) -> str | None:
    for hint_key in _GENERIC_REF_HINT_KEYS:
        hinted_value = payload.get(hint_key)
        ref_key = _quality_ref_key_from_text(hinted_value)
        if ref_key is not None:
            return ref_key
    return None


def _quality_ref_key_from_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("-", "_").casefold()
    for ref_key in KNOWN_QUALITY_REF_KEYS:
        if normalized == ref_key or ref_key in normalized:
            return ref_key
    for hint, ref_key in _QUALITY_REF_HINTS.items():
        if hint in normalized:
            return ref_key
    return None


def _coerce_ref_value_from_mapping(payload: Mapping[Any, Any]) -> str | None:
    for value_key in _GENERIC_REF_VALUE_KEYS:
        value = _coerce_ref_value(payload.get(value_key))
        if value is not None:
            return value
    return None


def _coerce_ref_value(value: Any) -> str | None:
    if isinstance(value, Mapping):
        return _coerce_ref_value_from_mapping(value)
    if isinstance(value, str):
        return _sanitize_ref(value)
    return None


def _sanitize_ref(value: str) -> str | None:
    text = value.strip()
    if not text or len(text) > 256 or any(char in text for char in "\r\n\t"):
        return None
    lowered = text.casefold()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return None
    return text


def _missing_evidence(ref_key: str) -> dict[str, str]:
    return {
        "code": f"{ref_key}_missing",
        "missing_evidence_type": ref_key,
        "message": f"Runtime quality ref {ref_key} was not found.",
        "next_action": (
            f"Persist {ref_key} from the owning runtime layer before production approval."
        ),
    }


__all__ = [
    "KNOWN_QUALITY_REF_KEYS",
    "LIFECYCLE_QUALITY_REF_KEYS",
    "REQUIRED_QUALITY_REF_KEYS",
    "QualityRefMatch",
    "QualityRefResolution",
    "RuntimeQualityAuthorityRefs",
    "resolve_quality_refs",
]
