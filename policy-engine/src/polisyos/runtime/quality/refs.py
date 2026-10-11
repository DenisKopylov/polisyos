"""Runtime quality-ref discovery across canary and control payloads."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from hashlib import sha256
from typing import Any, get_args

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality.report_registry import (
    KNOWN_QUALITY_REF_KEYS,
    LIFECYCLE_QUALITY_REF_KEYS,
    QUALITY_REPORT_BODY_KEYS,
    QUALITY_REPORT_BODY_REF_KEYS,
    QUALITY_REPORT_REF_KEYS,
    REQUIRED_QUALITY_REF_KEYS,
    quality_report_ref_intake_registry,
)
from polisyos.runtime.quality.report_registry import (
    QUALITY_REF_HINTS as _QUALITY_REF_HINTS,
)

_KNOWN_QUALITY_REF_KEY_SET = set(KNOWN_QUALITY_REF_KEYS)
_UNSCOPED_QUALITY_REF_REJECTION_KEYS = frozenset(
    {"runtime_quality_refs", "runtime_quality_artifact_refs"}
)
_REF_ALIAS_CONTEXTS = {
    "artifact_id": frozenset({"nested"}),
    "artifact_ref": frozenset({"nested", "report", "authority_envelope"}),
    "cas_ref": frozenset({"nested", "report", "authority_envelope"}),
    "ref": frozenset({"nested", "report", "authority_envelope"}),
    "value": frozenset({"nested"}),
    "uri": frozenset({"nested"}),
}
_GENERIC_REF_VALUE_KEYS = tuple(_REF_ALIAS_CONTEXTS)
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


@dataclass(frozen=True)
class QualityRefMatch:
    """One accepted quality-ref discovery candidate."""

    key: str
    value: str
    source: str
    path: str

    def to_evidence(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "path": self.path,
        }


@dataclass(frozen=True)
class QualityRefRejection:
    """Describe one malformed or contradictory supplied ref without copying its value."""

    key: str
    source: str
    path: str
    reason: str
    input_type: str
    value_sha256: str
    value_length: int | None

    def to_evidence(self) -> dict[str, str]:
        return {
            "key": self.key,
            "source": self.source,
            "path": self.path,
            "reason": self.reason,
            "input_type": self.input_type,
            "value_sha256": self.value_sha256,
            "value_length": self.value_length,
        }


@dataclass(frozen=True)
class QualityRefResolution:
    """Resolved refs, missing evidence, and rejected supplied ref values."""

    refs: dict[str, str]
    matches: tuple[QualityRefMatch, ...]
    missing: tuple[str, ...]
    missing_evidence: tuple[dict[str, str], ...]
    rejections: tuple[QualityRefRejection, ...] = ()

    def unrejected_refs(self) -> dict[str, str]:
        """Return refs with no supplied malformed or conflicting counterpart.

        The result remains candidate data; callers must still apply the ref's
        existing role-specific verification before using it as evidence.
        An invalid unscoped container prevents safe attribution to any role.
        """
        rejected_keys = {item.key for item in self.rejections}
        if rejected_keys & _UNSCOPED_QUALITY_REF_REJECTION_KEYS:
            return {}
        return {key: value for key, value in self.refs.items() if key not in rejected_keys}

    def to_evidence(self) -> dict[str, Any]:
        return {
            "status": (
                "invalid"
                if self.rejections
                else "complete"
                if not self.missing
                else "missing"
            ),
            "required": list(REQUIRED_QUALITY_REF_KEYS),
            "refs": dict(self.refs),
            "matches": [match.to_evidence() for match in self.matches],
            "missing": list(self.missing),
            "missing_evidence": [dict(item) for item in self.missing_evidence],
            "rejections": [item.to_evidence() for item in self.rejections],
        }


@dataclass(frozen=True)
class RuntimeQualityAuthorityRefs:
    """Expose job/run ref candidates while retaining quality-body refusals.

    The `refs` field contains only values found on the runtime job/run surfaces.
    `quality_evidence` report bodies can add rejection diagnostics but cannot seed
    those runtime-owned values. Callers still apply role-specific verification.
    Legacy strings remain ID-only; selected views are retained only when an
    explicit typed-ref map was persisted, and the reader never manufactures a
    profile.
    """

    refs: dict[str, str]
    sources: dict[str, str]
    selected_refs: dict[str, ArtifactRef] = field(default_factory=dict)
    rejections: tuple[QualityRefRejection, ...] = ()

    @classmethod
    def from_runtime_payloads(
        cls,
        *,
        job_payload: Mapping[str, Any] | None = None,
        run_payload: Mapping[str, Any] | None = None,
        quality_evidence: Mapping[str, Any] | None = None,
    ) -> RuntimeQualityAuthorityRefs:
        """Resolve job/run refs; retain quality-evidence failures as diagnostics."""
        scoped = cls._from_runtime_payloads_scoped(
            job_payload=job_payload,
            run_payload=run_payload,
            quality_evidence=quality_evidence,
        )
        quality_evidence_scan = cls.from_sources(
            source_payloads={"quality_evidence": quality_evidence},
        )
        registered_ref_keys = frozenset(QUALITY_REPORT_REF_KEYS)
        scoped_only_rejections = tuple(
            rejection
            for rejection in scoped.rejections
            if not rejection.source.startswith("quality_evidence")
            or rejection.key not in registered_ref_keys | _UNSCOPED_QUALITY_REF_REJECTION_KEYS
        )
        runtime_keys = {
            key
            for key, source in scoped.sources.items()
            if not source.startswith("quality_evidence")
        }
        return cls(
            refs={key: value for key, value in scoped.refs.items() if key in runtime_keys},
            sources={key: value for key, value in scoped.sources.items() if key in runtime_keys},
            selected_refs={
                key: value for key, value in scoped.selected_refs.items() if key in runtime_keys
            },
            rejections=tuple(
                dict.fromkeys((*quality_evidence_scan.rejections, *scoped_only_rejections))
            ),
        )

    @classmethod
    def _from_runtime_payloads_scoped(
        cls,
        *,
        job_payload: Mapping[str, Any] | None = None,
        run_payload: Mapping[str, Any] | None = None,
        quality_evidence: Mapping[str, Any] | None = None,
    ) -> RuntimeQualityAuthorityRefs:
        refs: dict[str, str] = {}
        sources: dict[str, str] = {}
        selected_refs: dict[str, ArtifactRef] = {}
        rejections: list[QualityRefRejection] = []

        def add_rejections(
            key: str,
            raw_value: Any,
            issues: list[tuple[str, Any, str]],
            *,
            source: str,
            path: str,
        ) -> None:
            for reason, issue_value, suffix in issues:
                rejections.append(
                    _quality_ref_rejection(
                        key=key,
                        source=source,
                        path=f"{path}{suffix}",
                        reason=reason,
                        value=issue_value if issue_value is not None else raw_value,
                    )
                )

        def add_mapping(mapping: Any, *, source: str, path: str) -> None:
            if not isinstance(mapping, Mapping):
                add_rejections(
                    "runtime_quality_refs",
                    mapping,
                    [("explicit_null" if mapping is None else "unsupported_type", mapping, "")],
                    source=source,
                    path=path,
                )
                return
            for raw_key, raw_value in mapping.items():
                if not isinstance(raw_key, str) or not raw_key.endswith("_ref"):
                    continue
                key = raw_key
                key_path = _safe_path_key(raw_key)
                if key_path != raw_key:
                    rejections.append(
                        _quality_ref_rejection(
                            key="runtime_quality_refs",
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="malformed_mapping",
                            value=raw_value,
                        )
                    )
                    continue
                if raw_value is None:
                    rejections.append(
                        _quality_ref_rejection(
                            key=key,
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="explicit_null",
                            value=raw_value,
                        )
                    )
                    continue
                value, issues = _coerce_ref_value_details(raw_value)
                add_rejections(key, raw_value, issues, source=source, path=f"{path}.{key_path}")
                if value is None:
                    continue
                prior = refs.get(key)
                if prior is not None and prior != value:
                    rejections.append(
                        _quality_ref_rejection(
                            key=key,
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="conflicting_values",
                            value=raw_value,
                        )
                    )
                refs.setdefault(key, value)
                sources.setdefault(key, source)

        def add_optional_mapping(
            owner: Mapping[Any, Any],
            key: str,
            *,
            source: str,
            path: str,
        ) -> None:
            if key in owner:
                add_mapping(owner[key], source=source, path=path)

        def add_selected_mapping(mapping: Any, *, source: str, path: str) -> None:
            if not isinstance(mapping, Mapping):
                rejections.append(
                    _quality_ref_rejection(
                        key="runtime_quality_artifact_refs",
                        source=source,
                        path=path,
                        reason=("explicit_null" if mapping is None else "unsupported_type"),
                        value=mapping,
                    )
                )
                return
            for raw_key, raw_value in mapping.items():
                if not isinstance(raw_key, str) or not raw_key.endswith("_ref"):
                    rejections.append(
                        _quality_ref_rejection(
                            key="runtime_quality_artifact_refs",
                            source=source,
                            path=f"{path}.{_safe_path_key(raw_key)}",
                            reason="malformed_mapping",
                            value=raw_value,
                        )
                    )
                    continue
                key_path = _safe_path_key(raw_key)
                if key_path != raw_key:
                    rejections.append(
                        _quality_ref_rejection(
                            key="runtime_quality_artifact_refs",
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="malformed_mapping",
                            value=raw_value,
                        )
                    )
                    continue
                try:
                    selected = (
                        raw_value
                        if isinstance(raw_value, ArtifactRef)
                        else ArtifactRef.model_validate(raw_value)
                    )
                except (TypeError, ValueError):
                    rejections.append(
                        _quality_ref_rejection(
                            key=raw_key,
                            source=source,
                            path=f"{path}.{key_path}",
                            reason=(
                                "explicit_null"
                                if raw_value is None
                                else "unsupported_type"
                                if not isinstance(raw_value, Mapping)
                                else "malformed_mapping"
                            ),
                            value=raw_value,
                        )
                    )
                    continue
                prior_id = refs.get(raw_key)
                if prior_id is not None and prior_id != str(selected.artifact_id):
                    rejections.append(
                        _quality_ref_rejection(
                            key=raw_key,
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="conflicting_values",
                            value=raw_value,
                        )
                    )
                prior = selected_refs.get(raw_key)
                if prior is not None and prior != selected:
                    rejections.append(
                        _quality_ref_rejection(
                            key=raw_key,
                            source=source,
                            path=f"{path}.{key_path}",
                            reason="conflicting_values",
                            value=raw_value,
                        )
                    )
                selected_refs.setdefault(raw_key, selected)
                refs.setdefault(raw_key, str(selected.artifact_id))
                sources.setdefault(raw_key, source)

        for label, payload in (("job", job_payload), ("run", run_payload)):
            if not isinstance(payload, Mapping):
                continue
            add_optional_mapping(
                payload,
                "runtime_quality_refs",
                source=f"{label}.runtime_quality_refs",
                path=f"$.{label}.runtime_quality_refs",
            )
            if "runtime_quality_artifact_refs" in payload:
                add_selected_mapping(
                    payload["runtime_quality_artifact_refs"],
                    source=f"{label}.runtime_quality_artifact_refs",
                    path=f"$.{label}.runtime_quality_artifact_refs",
                )
            progress = payload.get("progress")
            if isinstance(progress, Mapping):
                add_optional_mapping(
                    progress,
                    "runtime_quality_refs",
                    source=f"{label}.progress.runtime_quality_refs",
                    path=f"$.{label}.progress.runtime_quality_refs",
                )
                if "runtime_quality_artifact_refs" in progress:
                    add_selected_mapping(
                        progress["runtime_quality_artifact_refs"],
                        source=f"{label}.progress.runtime_quality_artifact_refs",
                        path=f"$.{label}.progress.runtime_quality_artifact_refs",
                    )
                details = progress.get("details")
                if isinstance(details, Mapping):
                    add_optional_mapping(
                        details,
                        "runtime_quality_refs",
                        source=f"{label}.progress.details.runtime_quality_refs",
                        path=f"$.{label}.progress.details.runtime_quality_refs",
                    )
                    if "runtime_quality_artifact_refs" in details:
                        add_selected_mapping(
                            details["runtime_quality_artifact_refs"],
                            source=f"{label}.progress.details.runtime_quality_artifact_refs",
                            path=f"$.{label}.progress.details.runtime_quality_artifact_refs",
                        )
            details = payload.get("details")
            if isinstance(details, Mapping):
                add_optional_mapping(
                    details,
                    "runtime_quality_refs",
                    source=f"{label}.details.runtime_quality_refs",
                    path=f"$.{label}.details.runtime_quality_refs",
                )
                if "runtime_quality_artifact_refs" in details:
                    add_selected_mapping(
                        details["runtime_quality_artifact_refs"],
                        source=f"{label}.details.runtime_quality_artifact_refs",
                        path=f"$.{label}.details.runtime_quality_artifact_refs",
                    )

        if isinstance(quality_evidence, Mapping):
            add_optional_mapping(
                quality_evidence,
                "runtime_quality_refs",
                source="quality_evidence.runtime_quality_refs",
                path="$.quality_evidence.runtime_quality_refs",
            )
            if "runtime_quality_artifact_refs" in quality_evidence:
                add_selected_mapping(
                    quality_evidence["runtime_quality_artifact_refs"],
                    source="quality_evidence.runtime_quality_artifact_refs",
                    path="$.quality_evidence.runtime_quality_artifact_refs",
                )
            for report_key, report in quality_evidence.items():
                if not isinstance(report, Mapping):
                    continue
                safe_report_key = _safe_path_key(report_key)
                report_path = f"$.quality_evidence.{safe_report_key}"
                report_ref_keys = (
                    _quality_ref_keys_from_mapping(report)
                    | _quality_ref_keys_from_text(report_key)
                )
                if len(report_ref_keys) > 1:
                    rejections.extend(
                        _quality_ref_rejection(
                            key=ambiguous_key,
                            source=f"quality_evidence.{safe_report_key}",
                            path=f"{report_path}.role_hints",
                            reason="ambiguous_role_hints",
                            value=report,
                        )
                        for ambiguous_key in sorted(report_ref_keys)
                    )
                ref_key = next(iter(report_ref_keys)) if len(report_ref_keys) == 1 else None
                if ref_key is not None:
                    for alias, alias_ref_key in _report_body_ref_aliases(ref_key):
                        if alias not in report:
                            continue
                        raw_value = report[alias]
                        value, issues = _coerce_ref_value_details(raw_value)
                        add_rejections(
                            alias_ref_key,
                            raw_value,
                            issues,
                            source=f"quality_evidence.{safe_report_key}",
                            path=f"{report_path}.{alias}",
                        )
                        if value is not None:
                            prior = refs.get(alias_ref_key)
                            if prior is not None and prior != value:
                                rejections.append(
                                    _quality_ref_rejection(
                                        key=alias_ref_key,
                                        source=f"quality_evidence.{safe_report_key}",
                                        path=f"{report_path}.{alias}",
                                        reason="conflicting_values",
                                        value=raw_value,
                                    )
                                )
                            refs.setdefault(alias_ref_key, value)
                            sources.setdefault(alias_ref_key, f"quality_evidence.{safe_report_key}")
                if "runtime_quality_artifact_refs" in report:
                    add_selected_mapping(
                        report["runtime_quality_artifact_refs"],
                        source=f"quality_evidence.{safe_report_key}.runtime_quality_artifact_refs",
                        path=f"{report_path}.runtime_quality_artifact_refs",
                    )
                add_optional_mapping(
                    report,
                    "runtime_quality_refs",
                    source=f"quality_evidence.{safe_report_key}.runtime_quality_refs",
                    path=f"{report_path}.runtime_quality_refs",
                )
                if "authority_envelope" in report:
                    envelope = report["authority_envelope"]
                    envelope_ref_keys = report_ref_keys
                    envelope_ref_key = (
                        next(iter(envelope_ref_keys)) if len(envelope_ref_keys) == 1 else None
                    )
                    rejection_key = envelope_ref_key or "runtime_quality_refs"
                    envelope_source = (
                        f"quality_evidence.{safe_report_key}.authority_envelope"
                    )
                    envelope_path = f"{report_path}.authority_envelope"
                    if len(envelope_ref_keys) > 1:
                        rejections.extend(
                            _quality_ref_rejection(
                                key=ambiguous_key,
                                source=envelope_source,
                                path=f"{envelope_path}.role_hints",
                                reason="ambiguous_role_hints",
                                value=envelope,
                            )
                            for ambiguous_key in sorted(envelope_ref_keys)
                        )
                    elif not isinstance(envelope, Mapping):
                        rejections.append(
                            _quality_ref_rejection(
                                key=rejection_key,
                                source=envelope_source,
                                path=envelope_path,
                                reason=(
                                    "explicit_null"
                                    if envelope is None
                                    else "unsupported_type"
                                ),
                                value=envelope,
                            )
                        )
                    else:
                        nullable_ref_fields = _validated_authority_envelope_nullable_ref_fields(
                            envelope
                        )
                        if nullable_ref_fields is None:
                            rejections.append(
                                _quality_ref_rejection(
                                    key=rejection_key,
                                    source=envelope_source,
                                    path=envelope_path,
                                    reason="malformed_authority_envelope",
                                    value=envelope,
                                )
                            )
                            nullable_ref_fields = frozenset()
                        for alias in _ref_aliases_for("authority_envelope"):
                            if alias not in envelope:
                                continue
                            raw_value = envelope[alias]
                            if raw_value is None and alias in nullable_ref_fields:
                                continue
                            value, issues = _coerce_ref_value_details(raw_value)
                            add_rejections(
                                rejection_key,
                                raw_value,
                                issues,
                                source=envelope_source,
                                path=f"{envelope_path}.{alias}",
                            )
                            if value is not None and envelope_ref_key is not None:
                                prior = refs.get(envelope_ref_key)
                                if prior is not None and prior != value:
                                    rejections.append(
                                        _quality_ref_rejection(
                                            key=envelope_ref_key,
                                            source=envelope_source,
                                            path=f"{envelope_path}.{alias}",
                                            reason="conflicting_values",
                                            value=raw_value,
                                        )
                                    )
                                refs.setdefault(envelope_ref_key, value)
                                sources.setdefault(envelope_ref_key, envelope_source)

        return cls(
            refs=refs,
            sources=sources,
            selected_refs=selected_refs,
            rejections=tuple(dict.fromkeys(rejections)),
        )

    @classmethod
    def from_sources(
        cls,
        *,
        source_payloads: Mapping[str, Any],
    ) -> RuntimeQualityAuthorityRefs:
        """Collect candidate ref diagnostics and rejections from labeled payloads.

        `refs` is a diagnostic projection only. This method does not select an
        authority ref or verify its content, profile, issuer, or currentness.
        Callers use its rejection rows to construct an admitted input view and
        continue to use their existing source-specific resolver for selection.
        """
        registered_ref_keys, registered_body_ref_keys = quality_report_ref_intake_registry()
        role_keys = frozenset(registered_ref_keys)
        body_roles = {
            body_key: ref_key
            for body_key, ref_key in registered_body_ref_keys.items()
            if ref_key in role_keys
        }
        refs: dict[str, str] = {}
        sources: dict[str, str] = {}
        rejections: list[QualityRefRejection] = []
        for raw_source, payload in source_payloads.items():
            source = _safe_label(str(raw_source))
            for match in _iter_quality_ref_matches(
                payload,
                source=source,
                path="$",
                rejections=rejections,
                known_ref_keys=role_keys,
                report_body_ref_keys=body_roles,
            ):
                prior = refs.get(match.key)
                if prior is not None and prior != match.value:
                    rejections.append(
                        _quality_ref_rejection(
                            key=match.key,
                            source=source,
                            path=match.path,
                            reason="conflicting_values",
                            value=match.value,
                        )
                    )
                refs.setdefault(match.key, match.value)
                sources.setdefault(match.key, source)
        return cls(
            refs=refs,
            sources=sources,
            rejections=tuple(dict.fromkeys(rejections)),
        )

    def get(self, key: str) -> str | None:
        """Return a ref only when its supplied role has no intake rejection."""
        value = self.unrejected_refs().get(key)
        if value is not None:
            return value
        selected = self.unrejected_selected_refs().get(key)
        return str(selected.artifact_id) if selected is not None else None

    def get_selected_ref(self, key: str) -> ArtifactRef | None:
        """Return an explicitly persisted typed ref only when its role is clean."""
        return self.unrejected_selected_refs().get(key)

    def unrejected_refs(self) -> dict[str, str]:
        """Return refs with no supplied malformed or conflicting counterpart.

        The result remains candidate data; callers must still apply the ref's
        existing role-specific verification before using it as evidence.
        An invalid unscoped container prevents safe attribution to any role.
        """
        rejected_keys = {item.key for item in self.rejections}
        if rejected_keys & _UNSCOPED_QUALITY_REF_REJECTION_KEYS:
            return {}
        return {key: value for key, value in self.refs.items() if key not in rejected_keys}

    def unrejected_selected_refs(self) -> dict[str, ArtifactRef]:
        """Return typed selected views with no supplied malformed counterpart."""
        rejected_keys = {item.key for item in self.rejections}
        if rejected_keys & _UNSCOPED_QUALITY_REF_REJECTION_KEYS:
            return {}
        return {
            key: value for key, value in self.selected_refs.items() if key not in rejected_keys
        }

    def missing_required(self) -> tuple[str, ...]:
        """Report required refs unavailable after malformed/conflicting input is rejected."""
        accepted_keys = set(self.unrejected_refs()) | set(self.unrejected_selected_refs())
        return tuple(key for key in REQUIRED_QUALITY_REF_KEYS if key not in accepted_keys)

    def to_evidence(self) -> dict[str, Any]:
        """Return diagnostics; raw refs here are never an admission projection."""
        return {
            "refs": dict(self.refs),
            "selected_refs": {
                key: value.model_dump(mode="json") for key, value in self.selected_refs.items()
            },
            "sources": dict(self.sources),
            "missing": list(self.missing_required()),
            "rejections": [item.to_evidence() for item in self.rejections],
        }

def resolve_quality_refs(
    *,
    run_params: Any | None = None,
    artifacts: Any | None = None,
    timeline: Any | None = None,
    lineage: Any | None = None,
    control_progress: Any | None = None,
) -> QualityRefResolution:
    """Discover quality refs while retaining every malformed supplied known role."""

    sources = (
        ("control_progress", control_progress),
        ("run_params", run_params),
        ("artifacts", artifacts),
        ("timeline", timeline),
        ("lineage", lineage),
    )
    found: dict[str, QualityRefMatch] = {}
    rejections: list[QualityRefRejection] = []
    for source_name, payload in sources:
        for match in _iter_quality_ref_matches(
            payload,
            source=source_name,
            path="$",
            rejections=rejections,
        ):
            prior = found.get(match.key)
            if prior is not None and prior.value != match.value:
                rejections.append(
                    _quality_ref_rejection(
                        key=match.key,
                        source=match.source,
                        path=match.path,
                        reason="conflicting_values",
                        value=match.value,
                    )
                )
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
        rejections=tuple(dict.fromkeys(rejections)),
    )


def strip_rejected_quality_ref_inputs(
    payload: Any,
    *,
    rejected_ref_keys: Iterable[str],
    report_body_ref_keys: Mapping[str, str],
) -> Any:
    """Remove rejected ref roles and their typed report/ref objects recursively.

    This is an admission projection only. It neither selects nor verifies any
    ref, and it leaves unrelated payload fields intact for existing consumers.
    """
    rejected = frozenset(key for key in rejected_ref_keys if isinstance(key, str))
    known_ref_keys = frozenset(
        (*KNOWN_QUALITY_REF_KEYS, *report_body_ref_keys.values())
    )
    removed = object()

    def strip(value: Any) -> Any:
        if isinstance(value, Mapping):
            if _is_safe_quality_ref_rejection_record(value):
                return dict(value)
            hinted_keys = _quality_ref_keys_from_mapping(
                value,
                known_ref_keys=known_ref_keys,
                report_body_ref_keys=report_body_ref_keys,
            )
            if len(hinted_keys) > 1 or hinted_keys & rejected:
                return removed
            admitted: dict[Any, Any] = {}
            for raw_key, item in value.items():
                key = raw_key if isinstance(raw_key, str) else str(raw_key)
                body_ref_key = report_body_ref_keys.get(key)
                if key in rejected or body_ref_key in rejected:
                    continue
                cleaned = strip(item)
                if cleaned is not removed:
                    admitted[raw_key] = cleaned
            return admitted
        if isinstance(value, list):
            return [cleaned for item in value if (cleaned := strip(item)) is not removed]
        if isinstance(value, tuple):
            return tuple(cleaned for item in value if (cleaned := strip(item)) is not removed)
        return value

    admitted = strip(payload)
    return {} if admitted is removed else admitted


def _iter_quality_ref_matches(
    payload: Any,
    *,
    source: str,
    path: str,
    rejections: list[QualityRefRejection],
    known_ref_keys: frozenset[str] = frozenset(QUALITY_REPORT_REF_KEYS),
    report_body_ref_keys: Mapping[str, str] | None = QUALITY_REPORT_BODY_REF_KEYS,
) -> Iterable[QualityRefMatch]:
    body_roles = report_body_ref_keys or {}
    if isinstance(payload, Mapping):
        hinted_keys = _quality_ref_keys_from_mapping(
            payload,
            known_ref_keys=known_ref_keys,
            report_body_ref_keys=body_roles,
        )
        if len(hinted_keys) > 1:
            rejections.extend(
                _quality_ref_rejection(
                    key=hinted_key,
                    source=source,
                    path=f"{path}.role_hints",
                    reason="ambiguous_role_hints",
                    value=payload,
                )
                for hinted_key in sorted(hinted_keys)
            )
            return
        elif hinted_keys:
            hinted_key = next(iter(hinted_keys))
            if _is_report_body_mapping(payload):
                yield from _iter_report_body_ref_matches(
                    payload,
                    ref_key=hinted_key,
                    source=source,
                    path=path,
                    rejections=rejections,
                )
                return
            value, issues = _coerce_ref_value_details(payload)
            rejections.extend(
                _quality_ref_rejection(
                    key=hinted_key,
                    source=source,
                    path=f"{path}{suffix}",
                    reason=reason,
                    value=issue_value if issue_value is not None else payload,
                )
                for reason, issue_value, suffix in issues
            )
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
            next_path = f"{path}.{_safe_path_key(raw_key)}"
            key_roles = _quality_ref_keys_from_text(
                raw_key,
                known_ref_keys=known_ref_keys,
                report_body_ref_keys=body_roles,
            )
            if len(key_roles) > 1:
                rejections.extend(
                    _quality_ref_rejection(
                        key=ambiguous_key,
                        source=source,
                        path=f"{next_path}.role_hints",
                        reason="ambiguous_role_hints",
                        value=raw_key,
                    )
                    for ambiguous_key in sorted(key_roles)
                )
                continue
            if key in _UNSCOPED_QUALITY_REF_REJECTION_KEYS and (
                value is None or not isinstance(value, Mapping)
            ):
                rejections.append(
                    _quality_ref_rejection(
                        key=key,
                        source=source,
                        path=next_path,
                        reason=("explicit_null" if value is None else "unsupported_type"),
                        value=value,
                    )
                )
                continue
            if key == "runtime_quality_artifact_refs":
                if not isinstance(value, Mapping):
                    continue
                for raw_ref_key, raw_selected in value.items():
                    if not isinstance(raw_ref_key, str) or not raw_ref_key.endswith("_ref"):
                        rejections.append(
                            _quality_ref_rejection(
                                key=key,
                                source=source,
                                path=f"{next_path}.{_safe_path_key(raw_ref_key)}",
                                reason="malformed_mapping",
                                value=raw_selected,
                            )
                        )
                        continue
                    if raw_ref_key not in known_ref_keys:
                        continue
                    selected_path = f"{next_path}.{_safe_path_key(raw_ref_key)}"
                    try:
                        selected = (
                            raw_selected
                            if isinstance(raw_selected, ArtifactRef)
                            else ArtifactRef.model_validate(raw_selected)
                        )
                    except (TypeError, ValueError):
                        rejections.append(
                            _quality_ref_rejection(
                                key=raw_ref_key,
                                source=source,
                                path=selected_path,
                                reason=(
                                    "explicit_null"
                                    if raw_selected is None
                                    else "unsupported_type"
                                    if not isinstance(raw_selected, Mapping)
                                    else "malformed_mapping"
                                ),
                                value=raw_selected,
                            )
                        )
                        continue
                    yield QualityRefMatch(
                        key=raw_ref_key,
                        value=str(selected.artifact_id),
                        source=source,
                        path=selected_path,
                    )
                continue
            report_ref_key = body_roles.get(key)
            if (
                key in QUALITY_REPORT_BODY_KEYS
                and report_ref_key is None
                and isinstance(value, Mapping)
            ):
                wrapper_aliases = set(_ref_aliases_for("nested"))
                if wrapper_aliases.intersection(value) and not _is_report_body_mapping(value):
                    rejections.append(
                        _quality_ref_rejection(
                            key=key,
                            source=source,
                            path=next_path,
                            reason="malformed_report_body_wrapper",
                            value=value,
                        )
                    )
                continue
            if report_ref_key is not None and isinstance(value, Mapping):
                nested_roles = _quality_ref_keys_from_mapping(
                    value,
                    known_ref_keys=known_ref_keys,
                    report_body_ref_keys=body_roles,
                )
                if nested_roles and nested_roles != frozenset({report_ref_key}):
                    for ambiguous_key in sorted(nested_roles | {report_ref_key}):
                        rejections.append(
                            _quality_ref_rejection(
                                key=ambiguous_key,
                                source=source,
                                path=f"{next_path}.role_hints",
                                reason="ambiguous_role_hints",
                                value=value,
                            )
                        )
                    continue
                if _is_report_body_mapping(value, registered_body=True):
                    yield from _iter_report_body_ref_matches(
                        value,
                        ref_key=report_ref_key,
                        source=source,
                        path=next_path,
                        rejections=rejections,
                    )
                    continue
                ref_value, issues = _coerce_ref_value_details(value)
                rejections.extend(
                    _quality_ref_rejection(
                        key=report_ref_key,
                        source=source,
                        path=f"{next_path}{suffix}",
                        reason=reason,
                        value=issue_value if issue_value is not None else value,
                    )
                    for reason, issue_value, suffix in issues
                )
                if ref_value is not None and not issues:
                    yield QualityRefMatch(
                        key=report_ref_key,
                        value=ref_value,
                        source=source,
                        path=next_path,
                    )
                continue
            if (
                key in known_ref_keys
                and isinstance(value, Mapping)
                and _is_report_body_mapping(
                    value,
                    registered_body=key.removesuffix("_ref") in QUALITY_REPORT_BODY_KEYS,
                )
            ):
                yield from _iter_report_body_ref_matches(
                    value,
                    ref_key=key,
                    source=source,
                    path=next_path,
                    rejections=rejections,
                )
                continue
            if key in known_ref_keys:
                if value is None:
                    rejections.append(
                        _quality_ref_rejection(
                            key=key,
                            source=source,
                            path=next_path,
                            reason="explicit_null",
                            value=value,
                        )
                    )
                    continue
                ref_value, issues = _coerce_ref_value_details(value)
                rejections.extend(
                    _quality_ref_rejection(
                        key=key,
                        source=source,
                        path=f"{next_path}{suffix}",
                        reason=reason,
                        value=issue_value if issue_value is not None else value,
                    )
                    for reason, issue_value, suffix in issues
                )
                if ref_value is not None:
                    yield QualityRefMatch(
                        key=key,
                        value=ref_value,
                        source=source,
                        path=next_path,
                    )
                    continue
                if value is not None:
                    continue
            yield from _iter_quality_ref_matches(
                value,
                source=source,
                path=next_path,
                rejections=rejections,
                known_ref_keys=known_ref_keys,
                report_body_ref_keys=body_roles,
            )
        return

    if isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            yield from _iter_quality_ref_matches(
                value,
                source=source,
                path=f"{path}[{index}]",
                rejections=rejections,
                known_ref_keys=known_ref_keys,
                report_body_ref_keys=body_roles,
            )

def _is_safe_quality_ref_rejection_record(value: Mapping[Any, Any]) -> bool:
    """Recognize redacted intake diagnostics so ref stripping preserves them."""
    fields = {
        "key",
        "source",
        "path",
        "reason",
        "input_type",
        "value_sha256",
        "value_length",
    }
    if set(value) != fields:
        return False
    if any(
        not isinstance(value[name], str) or not value[name]
        for name in fields - {"value_length"}
    ):
        return False
    digest = value["value_sha256"]
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        return False
    length = value["value_length"]
    return length is None or (type(length) is int and length >= 0)


def _quality_ref_keys_from_mapping(
    payload: Mapping[Any, Any],
    *,
    known_ref_keys: frozenset[str] = frozenset(QUALITY_REPORT_REF_KEYS),
    report_body_ref_keys: Mapping[str, str] | None = QUALITY_REPORT_BODY_REF_KEYS,
) -> frozenset[str]:
    """Return every registered role named by any recognized mapping hint."""
    matches: set[str] = set()
    for hint_key in _GENERIC_REF_HINT_KEYS:
        matches.update(
            _quality_ref_keys_from_text(
                payload.get(hint_key),
                known_ref_keys=known_ref_keys,
                report_body_ref_keys=report_body_ref_keys,
            )
        )
    return frozenset(matches)


def _quality_ref_keys_from_text(
    value: Any,
    *,
    known_ref_keys: frozenset[str] = frozenset(QUALITY_REPORT_REF_KEYS),
    report_body_ref_keys: Mapping[str, str] | None = QUALITY_REPORT_BODY_REF_KEYS,
) -> frozenset[str]:
    """Return every registered role with a complete identifier boundary."""
    if not isinstance(value, str):
        return frozenset()
    text = value.strip()
    if not text:
        return frozenset()
    normalized = text.replace("-", "_").casefold()
    exact_matches = {
        ref_key
        for ref_key in known_ref_keys
        if normalized == ref_key.replace("-", "_").casefold()
    }
    exact_matches.update(
        ref_key
        for hint, ref_key in _QUALITY_REF_HINTS.items()
        if ref_key in known_ref_keys
        and normalized == hint.replace("-", "_").casefold()
    )
    exact_matches.update(
        ref_key
        for hint, ref_key in (report_body_ref_keys or {}).items()
        if normalized == hint.replace("-", "_").casefold()
    )
    if exact_matches:
        return frozenset(exact_matches)

    matches: set[str] = set()
    aliases = {
        **{ref_key: ref_key for ref_key in known_ref_keys},
        **{
            hint: ref_key
            for hint, ref_key in _QUALITY_REF_HINTS.items()
            if ref_key in known_ref_keys
        },
        **dict(report_body_ref_keys or {}),
    }
    folded_text = text.casefold()
    for alias, ref_key in aliases.items():
        if (
            ref_key in known_ref_keys
            and _quality_ref_alias_pattern(alias).search(folded_text) is not None
        ):
            matches.add(ref_key)
    return frozenset(matches)


def _iter_report_body_ref_matches(
    report: Mapping[Any, Any],
    *,
    ref_key: str,
    source: str,
    path: str,
    rejections: list[QualityRefRejection],
) -> Iterable[QualityRefMatch]:
    """Read registered report ref aliases while preserving typed failures."""
    for alias, alias_ref_key in _report_body_ref_aliases(ref_key):
        if alias not in report:
            continue
        raw_value = report[alias]
        value, issues = _coerce_ref_value_details(raw_value)
        rejections.extend(
            _quality_ref_rejection(
                key=alias_ref_key,
                source=source,
                path=f"{path}.{_safe_path_key(alias)}{suffix}",
                reason=reason,
                value=issue_value if issue_value is not None else raw_value,
            )
            for reason, issue_value, suffix in issues
        )
        if value is not None:
            yield QualityRefMatch(
                key=alias_ref_key,
                value=value,
                source=source,
                path=f"{path}.{_safe_path_key(alias)}",
            )

    if "authority_envelope" not in report:
        return
    envelope = report["authority_envelope"]
    envelope_path = f"{path}.authority_envelope"
    if not isinstance(envelope, Mapping):
        rejections.append(
            _quality_ref_rejection(
                key=ref_key,
                source=source,
                path=envelope_path,
                reason=("explicit_null" if envelope is None else "unsupported_type"),
                value=envelope,
            )
        )
        return
    nullable_fields = _validated_authority_envelope_nullable_ref_fields(envelope)
    if nullable_fields is None:
        rejections.append(
            _quality_ref_rejection(
                key=ref_key,
                source=source,
                path=envelope_path,
                reason="malformed_authority_envelope",
                value=envelope,
            )
        )
        nullable_fields = frozenset()
    for alias in _ref_aliases_for("authority_envelope"):
        if alias not in envelope:
            continue
        raw_value = envelope[alias]
        if raw_value is None and alias in nullable_fields:
            continue
        value, issues = _coerce_ref_value_details(raw_value)
        rejections.extend(
            _quality_ref_rejection(
                key=ref_key,
                source=source,
                path=f"{envelope_path}.{_safe_path_key(alias)}{suffix}",
                reason=reason,
                value=issue_value if issue_value is not None else raw_value,
            )
            for reason, issue_value, suffix in issues
        )
        if value is not None:
            yield QualityRefMatch(
                key=ref_key,
                value=value,
                source=source,
                path=f"{envelope_path}.{_safe_path_key(alias)}",
            )


def _coerce_ref_value_from_mapping(payload: Mapping[Any, Any]) -> str | None:
    value, _issues = _coerce_ref_value_details(payload)
    return value


def _coerce_ref_value(value: Any) -> str | None:
    normalized, _issues = _coerce_ref_value_details(value)
    return normalized


def _coerce_ref_value_details(
    value: Any,
    *,
    suffix: str = "",
) -> tuple[str | None, list[tuple[str, Any, str]]]:
    """Normalize one explicitly supplied ref value and retain malformed parts.

    Callers guard absent mapping keys before calling this helper; `None` here
    means a supplied null and is rejected rather than treated as absence.
    """
    if value is None:
        return None, [("explicit_null", None, suffix)]
    if isinstance(value, ArtifactRef):
        return str(value.artifact_id), []
    if isinstance(value, Mapping):
        present = [key for key in _GENERIC_REF_VALUE_KEYS if key in value]
        if not present:
            return None, [("malformed_mapping", value, suffix)]
        candidates: list[str] = []
        issues: list[tuple[str, Any, str]] = []
        for key in present:
            raw_candidate = value[key]
            candidate, candidate_issues = _coerce_ref_value_details(
                raw_candidate,
                suffix=f"{suffix}.{key}",
            )
            issues.extend(candidate_issues)
            if candidate is not None:
                candidates.append(candidate)
        distinct_candidates = tuple(dict.fromkeys(candidates))
        if len(distinct_candidates) > 1:
            issues.append(("conflicting_values", value, suffix))
        if not distinct_candidates and not issues:
            issues.append(("malformed_mapping", value, suffix))
        return (distinct_candidates[0] if distinct_candidates else None), issues
    if not isinstance(value, str):
        return None, [("unsupported_type", value, suffix)]
    text = value.strip()
    if not text:
        return None, [("empty_value", value, suffix)]
    if len(text) > 256:
        return None, [("value_too_long", value, suffix)]
    if any(char in text for char in "\r\n\t"):
        return None, [("control_character", value, suffix)]
    lowered = text.casefold()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return None, [("secret_marker", value, suffix)]
    return text, []


def _validated_authority_envelope_nullable_ref_fields(
    envelope: Mapping[Any, Any],
) -> frozenset[str] | None:
    """Return schema-declared nullable ref fields only for a valid envelope.

    A null optional field is absence only when the complete typed envelope
    validates. Generic report mappings do not receive this exception.
    """
    from pydantic import ValidationError

    from polisyos.runtime.quality.authority import EvidenceAuthorityEnvelope

    try:
        EvidenceAuthorityEnvelope.model_validate(envelope)
    except ValidationError:
        return None

    return frozenset(
        name
        for name, field_info in EvidenceAuthorityEnvelope.model_fields.items()
        if name.endswith("_ref")
        and field_info.default is None
        and type(None) in get_args(field_info.annotation)
    )


def _ref_aliases_for(context: str) -> tuple[str, ...]:
    """Return the registered aliases accepted by one ref intake context."""
    return tuple(
        alias
        for alias, contexts in _REF_ALIAS_CONTEXTS.items()
        if context in contexts
    )


def _report_body_ref_aliases(ref_key: str) -> tuple[tuple[str, str], ...]:
    """Return each body ref alias paired with its registered role.

    Generic `ref`-style fields inherit the uniquely identified report role. An
    explicit canonical role key always keeps that role, including when it is a
    cross-report dependency embedded in another report body.
    """
    aliases = [(alias, ref_key) for alias in _ref_aliases_for("report")]
    aliases.extend((role_key, role_key) for role_key in QUALITY_REPORT_REF_KEYS)
    return tuple(dict.fromkeys(aliases))


def _is_report_body_mapping(
    value: Mapping[Any, Any],
    *,
    registered_body: bool = False,
) -> bool:
    """Recognize report bodies without requiring one closed set of status markers."""
    if registered_body:
        wrapper_fields = {*_GENERIC_REF_VALUE_KEYS, *ArtifactRef.model_fields}
        generic_fields = set(value).intersection(_GENERIC_REF_VALUE_KEYS)
        if generic_fields and set(value) <= wrapper_fields:
            return False
        for key in generic_fields:
            _normalized, issues = _coerce_ref_value_details(value[key])
            if issues:
                return False
        return True
    body_markers = {"status", "issues", "schema_version", "authority_envelope"}
    report_aliases = {alias for alias, _role in _report_body_ref_aliases("")}
    return bool(body_markers.intersection(value) or any(alias in value for alias in report_aliases))


@lru_cache(maxsize=512)
def _quality_ref_alias_pattern(alias: str) -> re.Pattern[str]:
    """Compile one registry alias with role-internal separators and strict outer bounds."""
    alias_parts = alias.casefold().split("_")
    alias_pattern = r"[-_]".join(re.escape(part) for part in alias_parts)
    return re.compile(rf"(?<![A-Za-z0-9_]){alias_pattern}(?![A-Za-z0-9_])")


def _safe_value_sha256(value: Any, *, seen: frozenset[int] = frozenset()) -> str:
    """Hash a deterministic structural fingerprint without emitting raw ref material."""
    digest = sha256()
    value_type = f"{type(value).__module__}.{type(value).__qualname__}"
    digest.update(value_type.encode("utf-8", errors="backslashreplace"))
    if isinstance(value, str):
        raw = value.encode("utf-8", errors="surrogatepass")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    elif isinstance(value, bytes):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    elif value is None or isinstance(value, bool | int | float):
        digest.update(str(value).encode("ascii", errors="backslashreplace"))
    elif id(value) in seen:
        digest.update(b"recursive-value")
    elif isinstance(value, Mapping):
        next_seen = seen | {id(value)}
        items = sorted(
            (
                _safe_value_sha256(key, seen=next_seen),
                _safe_value_sha256(item, seen=next_seen),
            )
            for key, item in value.items()
        )
        for key_digest, item_digest in items:
            digest.update(key_digest.encode("ascii"))
            digest.update(item_digest.encode("ascii"))
    elif isinstance(value, list | tuple):
        next_seen = seen | {id(value)}
        for item in value:
            digest.update(_safe_value_sha256(item, seen=next_seen).encode("ascii"))
    else:
        digest.update(b"unsupported-object")
    return digest.hexdigest()


def _safe_path_key(value: Any) -> str:
    """Keep evidence paths useful without copying hostile or secret-bearing keys."""
    if isinstance(value, str):
        lowered = value.casefold()
        if (
            len(value) <= 128
            and not any(char in value for char in "\r\n\t")
            and not any(marker in lowered for marker in _SECRET_MARKERS)
        ):
            return value
    return f"<key:{_safe_value_sha256(value)[:16]}>"


def _safe_label(value: str) -> str:
    lowered = value.casefold()
    if (
        len(value) <= 256
        and not any(char in value for char in "\r\n\t")
        and not any(marker in lowered for marker in _SECRET_MARKERS)
    ):
        return value
    return f"<label:{_safe_value_sha256(value)[:16]}>"


def _quality_ref_rejection(
    *,
    key: str,
    source: str,
    path: str,
    reason: str,
    value: Any,
) -> QualityRefRejection:
    return QualityRefRejection(
        key=_safe_label(key),
        source=_safe_label(source),
        path=_safe_label(path),
        reason=reason,
        input_type=_safe_label(f"{type(value).__module__}.{type(value).__qualname__}"),
        value_sha256=_safe_value_sha256(value),
        value_length=(
            len(value.encode("utf-8", errors="surrogatepass"))
            if isinstance(value, str)
            else len(value)
            if isinstance(value, bytes | Mapping | list | tuple)
            else None
        ),
    )


def _sanitize_ref(value: str) -> str | None:
    normalized, _issues = _coerce_ref_value_details(value)
    return normalized

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
    "QualityRefRejection",
    "QualityRefResolution",
    "RuntimeQualityAuthorityRefs",
    "resolve_quality_refs",
]
