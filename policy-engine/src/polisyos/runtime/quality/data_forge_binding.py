"""Runtime Data Forge snapshot/read-API binding evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from polisyos.data_forge.read_api.surfaces import available_surfaces, surface_module

DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION = (
    "policyos.runtime.data_forge_snapshot_binding.v1"
)
DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_FILE = "data_forge_snapshot_binding.json"
DATA_FORGE_SNAPSHOT_BINDING_GATE = "data_forge_snapshot_binding_valid"
DATA_FORGE_SNAPSHOT_BINDING_LAYER = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_PHASE = "data_forge_snapshot_binding"
DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS = 60 * 60 * 24 * 90
REQUIRED_DATA_FORGE_SNAPSHOT_ROLES = ("legal", "catalog", "academic", "domain")
DATA_FORGE_SNAPSHOT_ROLE_SURFACES = {
    "legal": "legal",
    "catalog": "catalog",
    "academic": "academic",
    "domain": "ukraine",
}
_PASS_STATUSES = {"pass", "passed", "ok", "success"}
_LOCAL_PATH_PREFIXES = ("/", "./", "../", "~", "file://")


@dataclass(frozen=True)
class DataForgeSnapshotBindingIssue:
    """One deterministic Data Forge snapshot-binding validation issue."""

    code: str
    role: str
    field: str
    message: str
    value: object | None = None
    next_action: str = (
        "Emit Data Forge snapshot binding evidence with snapshot id, CAS manifest "
        "identity, artifact ids, quality-gate refs, freshness, and read_api surface."
    )

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": "fail",
            "status": "fail",
            "role": self.role,
            "field": self.field,
            "message": self.message,
            "next_action": self.next_action,
            "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


def normalize_data_forge_snapshot_binding_report(
    report: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize and validate runtime-owned Data Forge snapshot bindings."""

    observed_at = _utc(now)
    if not isinstance(report, Mapping):
        issue = DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_binding_missing",
            role="report",
            field=DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
            message=(
                "Serious runtime evidence is missing Data Forge snapshot/read-API "
                "binding evidence."
            ),
        )
        return _report_payload(
            source={},
            bindings=[],
            issues=[issue],
            now=observed_at,
        )

    source = {str(key): _json_value(value) for key, value in report.items()}
    issues: list[DataForgeSnapshotBindingIssue] = []
    if source.get("schema_version") != DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_binding_schema_version_invalid",
                role="report",
                field="schema_version",
                message="Data Forge snapshot binding report schema version is invalid.",
                value=source.get("schema_version"),
            )
        )

    blockers, blocker_issues = _runtime_blockers(source)
    issues.extend(blocker_issues)
    source_status = _clean_text(source.get("status") or source.get("quality_status"))
    if source_status is not None and source_status.casefold() == "blocked":
        if not blockers and not blocker_issues:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_missing",
                    role="report",
                    field="blockers",
                    message=(
                        "Blocked Data Forge snapshot binding report must preserve a "
                        "typed runtime blocker."
                    ),
                )
            )
        return _report_payload(
            source=source,
            bindings=[],
            issues=issues,
            now=observed_at,
            blockers=blockers,
            status_override="blocked",
        )

    raw_bindings = _binding_rows(source)
    bindings: list[dict[str, Any]] = []
    roles_seen: set[str] = set()
    for index, raw_binding in enumerate(raw_bindings, start=1):
        binding = {str(key): _json_value(value) for key, value in raw_binding.items()}
        role = _clean_text(binding.get("role")) or f"bindings[{index}]"
        if role in roles_seen:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_role_duplicate",
                    role=role,
                    field="role",
                    message=f"Data Forge snapshot role {role!r} appears more than once.",
                    value=role,
                )
            )
        roles_seen.add(role)
        _normalize_binding_surface(binding)
        bindings.append(binding)
        issues.extend(_binding_issues(binding=binding, role=role, now=observed_at))

    for role in REQUIRED_DATA_FORGE_SNAPSHOT_ROLES:
        if role not in roles_seen:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_role_missing",
                    role=role,
                    field="bindings",
                    message=f"Data Forge snapshot binding for role {role!r} is missing.",
                )
            )

    return _report_payload(
        source=source,
        bindings=bindings,
        issues=issues,
        now=observed_at,
    )


def data_forge_snapshot_binding_scorecard_gates(
    report: Mapping[str, Any] | None,
    *,
    canary_kind: str,
    serious: bool,
) -> list[dict[str, Any]]:
    """Build scorecard gates for Data Forge snapshot/read-API binding evidence."""

    if not serious and not isinstance(report, Mapping):
        return []
    normalized = normalize_data_forge_snapshot_binding_report(report)
    if normalized.get("status") == "blocked":
        blockers = [
            dict(blocker)
            for blocker in normalized.get("blockers", [])
            if isinstance(blocker, Mapping)
        ]
        if blockers:
            status = "fail" if serious else "warn"
            return [
                {
                    "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                    "stage": "materialization",
                    "code": str(
                        blocker.get("code") or "data_forge_snapshot_binding_blocked"
                    ),
                    "status": status,
                    "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
                    "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
                    "message": str(
                        blocker.get("message")
                        or "Data Forge snapshot binding emitted a runtime blocker."
                    ),
                    "evidence_ref": str(
                        blocker.get("evidence_ref")
                        or f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                    ),
                    "next_action": str(
                        blocker.get("next_action")
                        or (
                            "Resolve the Data Forge runtime blocker or explicitly "
                            "degrade the serious policy closeout."
                        )
                    ),
                    "blocking": serious,
                }
                for blocker in blockers
            ]
    issues = [
        dict(issue)
        for issue in normalized.get("issues", [])
        if isinstance(issue, Mapping)
    ]
    if not issues:
        return [
            {
                "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                "stage": "materialization",
                "code": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                "status": "pass",
                "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
                "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
                "message": (
                    "Data Forge legal, catalog, academic, and domain snapshots are "
                    "bound to manifests, artifact ids, quality gates, and read APIs."
                ),
                "evidence_ref": (
                    f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                    if isinstance(report, Mapping)
                    else None
                ),
                "next_action": None,
                "blocking": False,
            }
        ]
    status = "fail" if serious else "warn"
    return [
        {
            "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
            "stage": "materialization",
            "code": str(issue.get("code") or DATA_FORGE_SNAPSHOT_BINDING_GATE),
            "status": status,
            "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
            "phase": str(issue.get("phase") or DATA_FORGE_SNAPSHOT_BINDING_PHASE),
            "message": str(issue.get("message") or "Data Forge snapshot binding failed."),
            "evidence_ref": (
                f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                if isinstance(report, Mapping)
                else None
            ),
            "next_action": str(issue.get("next_action") or ""),
            "blocking": serious,
            "missing_input": str(issue.get("field") or "") or None,
        }
        for issue in issues
    ]


def _report_payload(
    *,
    source: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    issues: Sequence[DataForgeSnapshotBindingIssue],
    now: datetime,
    blockers: Sequence[Mapping[str, Any]] = (),
    status_override: str | None = None,
) -> dict[str, Any]:
    payload = dict(source)
    payload["schema_version"] = DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION
    payload["status"] = "fail" if issues else status_override or "pass"
    payload["observed_at"] = now.isoformat()
    payload["bindings"] = [dict(binding) for binding in bindings]
    if blockers:
        payload["blockers"] = [dict(blocker) for blocker in blockers]
    payload["summary"] = {
        "required_role_count": len(REQUIRED_DATA_FORGE_SNAPSHOT_ROLES),
        "bound_role_count": len(
            {
                str(binding.get("role"))
                for binding in bindings
                if _clean_text(binding.get("role"))
            }
        ),
        "issue_count": len(issues),
    }
    payload["issues"] = [issue.as_dict() for issue in issues]
    return payload


def _binding_rows(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = (
        report.get("bindings")
        or report.get("snapshot_bindings")
        or report.get("snapshots")
    )
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _runtime_blockers(
    report: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[DataForgeSnapshotBindingIssue]]:
    raw_blockers = report.get("blockers") or report.get("runtime_blockers")
    if not isinstance(raw_blockers, list):
        return [], []
    blockers: list[dict[str, Any]] = []
    issues: list[DataForgeSnapshotBindingIssue] = []
    for index, raw_blocker in enumerate(raw_blockers, start=1):
        if not isinstance(raw_blocker, Mapping):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_invalid",
                    role="report",
                    field=f"blockers[{index}]",
                    message="Data Forge runtime blocker must be a mapping.",
                )
            )
            continue
        blocker = {str(key): _json_value(value) for key, value in raw_blocker.items()}
        blockers.append(blocker)
        if not _clean_text(blocker.get("code")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_code_missing",
                    role="report",
                    field=f"blockers[{index}].code",
                    message="Data Forge runtime blocker is missing a code.",
                )
            )
        if not _clean_text(blocker.get("message") or blocker.get("downstream_impact")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_message_missing",
                    role="report",
                    field=f"blockers[{index}].message",
                    message="Data Forge runtime blocker is missing a message.",
                )
            )
        if _clean_text(blocker.get("provenance_kind")) != "runtime_blocker":
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_provenance_invalid",
                    role="report",
                    field=f"blockers[{index}].provenance_kind",
                    message=(
                        "Data Forge blockers must be emitted with "
                        "provenance_kind=runtime_blocker."
                    ),
                    value=blocker.get("provenance_kind"),
                )
            )
        evidence_ref = _clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref"))
        if not _looks_artifact_ref(evidence_ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_evidence_ref_missing",
                    role="report",
                    field=f"blockers[{index}].evidence_ref",
                    message=(
                        "Data Forge runtime blocker must cite a CAS/artifact evidence ref."
                    ),
                    value=evidence_ref,
                )
            )
        runtime_event_ref = _clean_text(blocker.get("runtime_event_ref"))
        if not _looks_runtime_event_ref(runtime_event_ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_event_ref_missing",
                    role="report",
                    field=f"blockers[{index}].runtime_event_ref",
                    message="Data Forge runtime blocker must cite a runtime event ref.",
                    value=runtime_event_ref,
                )
            )
    return blockers, issues


def _binding_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
    now: datetime,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    expected_surface = DATA_FORGE_SNAPSHOT_ROLE_SURFACES.get(role)
    surface = _clean_text(binding.get("read_api_surface"))
    module = _clean_text(binding.get("read_api_module"))
    snapshot_id = _clean_text(binding.get("snapshot_id"))

    if role not in REQUIRED_DATA_FORGE_SNAPSHOT_ROLES:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_role_unknown",
                role=role,
                field="role",
                message=(
                    "Data Forge snapshot binding role must be one of legal, catalog, "
                    "academic, or domain."
                ),
                value=role,
            )
        )
    if not snapshot_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_id_missing",
                role=role,
                field="snapshot_id",
                message="Data Forge snapshot binding is missing snapshot_id.",
            )
        )

    if not surface:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_missing",
                role=role,
                field="read_api_surface",
                message="Data Forge snapshot binding is missing read_api_surface.",
            )
        )
    elif surface not in available_surfaces():
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_unknown",
                role=role,
                field="read_api_surface",
                message=f"Data Forge read_api surface {surface!r} is not registered.",
                value=surface,
            )
        )
    elif expected_surface is not None and surface != expected_surface:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_mismatch",
                role=role,
                field="read_api_surface",
                message=(
                    f"Data Forge role {role!r} must bind to read_api surface "
                    f"{expected_surface!r}."
                ),
                value=surface,
            )
        )
    elif module and module != surface_module(surface):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_module_mismatch",
                role=role,
                field="read_api_module",
                message=(
                    f"Data Forge read_api module for surface {surface!r} does not "
                    "match the registered surface module."
                ),
                value=module,
            )
        )

    issues.extend(_manifest_issues(binding=binding, role=role))
    issues.extend(_artifact_issues(binding=binding, role=role))
    issues.extend(_quality_gate_issues(binding=binding, role=role))
    freshness_issue = _freshness_issue(binding=binding, role=role, now=now)
    if freshness_issue is not None:
        issues.append(freshness_issue)
    return issues


def _manifest_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    manifest_ref = _clean_text(binding.get("manifest_ref"))
    manifest_artifact_id = _clean_text(
        binding.get("manifest_artifact_id") or binding.get("manifest_artifact_ref")
    )
    manifest_path = _clean_text(binding.get("manifest_path"))
    if _looks_local_path(manifest_ref) or (
        not manifest_ref and _looks_local_path(manifest_path)
    ):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_manifest_local_path_substitution",
                role=role,
                field="manifest_ref",
                message=(
                    "Data Forge snapshot manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=manifest_ref or manifest_path,
            )
        )
    if not _looks_artifact_ref(manifest_ref) and not _looks_artifact_ref(manifest_artifact_id):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_manifest_ref_missing",
                role=role,
                field="manifest_ref",
                message="Data Forge snapshot binding is missing manifest CAS/artifact identity.",
            )
        )
    return issues


def _artifact_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    refs = _ref_list(binding.get("artifact_ids") or binding.get("artifact_refs"))
    snapshot_ref = _clean_text(binding.get("snapshot_ref"))
    if _looks_local_path(snapshot_ref):
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_ref_local_path_substitution",
                role=role,
                field="snapshot_ref",
                message=(
                    "Data Forge snapshot identity must be a CAS/artifact reference, "
                    "not a local filesystem path."
                ),
                value=snapshot_ref,
            )
        ]
    issues: list[DataForgeSnapshotBindingIssue] = []
    if not _looks_artifact_ref(snapshot_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_ref_missing",
                role=role,
                field="snapshot_ref",
                message="Data Forge snapshot binding is missing snapshot_ref.",
            )
        )
    if not refs:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_artifact_ids_missing",
                role=role,
                field="artifact_ids",
                message="Data Forge snapshot binding is missing published artifact ids.",
            )
        )
        return issues
    for ref in refs:
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_artifact_local_path_substitution",
                    role=role,
                    field="artifact_ids",
                    message=(
                        "Data Forge snapshot artifact identities must be CAS/artifact "
                        "references, not local filesystem paths."
                    ),
                    value=ref,
                )
            )
        elif not _looks_artifact_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_artifact_id_invalid",
                    role=role,
                    field="artifact_ids",
                    message="Data Forge snapshot artifact id is not a recognized artifact ref.",
                    value=ref,
                )
            )
    return issues


def _quality_gate_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    raw_gates = binding.get("quality_gates") or binding.get("quality_gate_refs")
    if not isinstance(raw_gates, list) or not raw_gates:
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_quality_gate_missing",
                role=role,
                field="quality_gates",
                message="Data Forge snapshot binding is missing quality gate evidence.",
            )
        ]
    issues: list[DataForgeSnapshotBindingIssue] = []
    for index, raw_gate in enumerate(raw_gates, start=1):
        if isinstance(raw_gate, Mapping):
            gate = raw_gate
            status = str(gate.get("status") or gate.get("result") or "").casefold()
            ref = _clean_text(
                gate.get("artifact_id")
                or gate.get("artifact_ref")
                or gate.get("quality_gate_ref")
            )
            name = _clean_text(gate.get("name")) or f"quality_gates[{index}]"
        else:
            status = "pass"
            ref = _clean_text(raw_gate)
            name = f"quality_gates[{index}]"
        if status not in _PASS_STATUSES:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_failed",
                    role=role,
                    field=f"quality_gates[{index}].status",
                    message=f"Data Forge snapshot quality gate {name!r} is not passing.",
                    value=status,
                )
            )
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_local_path_substitution",
                    role=role,
                    field=f"quality_gates[{index}].artifact_id",
                    message=(
                        "Data Forge quality gate identity must be a CAS/artifact "
                        "reference, not a local filesystem path."
                    ),
                    value=ref,
                )
            )
        elif not _looks_artifact_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_artifact_missing",
                    role=role,
                    field=f"quality_gates[{index}].artifact_id",
                    message=(
                        f"Data Forge snapshot quality gate {name!r} is missing an "
                        "artifact identity."
                    ),
                )
            )
    return issues


def _freshness_issue(
    *,
    binding: Mapping[str, Any],
    role: str,
    now: datetime,
) -> DataForgeSnapshotBindingIssue | None:
    published_at = _parse_datetime(
        binding.get("published_at")
        or binding.get("snapshot_created_at")
        or binding.get("as_of")
    )
    if published_at is None:
        return DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_freshness_missing",
            role=role,
            field="published_at",
            message="Data Forge snapshot binding is missing freshness timestamp.",
        )
    ttl_seconds = _positive_int(
        binding.get("freshness_ttl_seconds")
        or binding.get("max_age_seconds")
        or DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS
    )
    if ttl_seconds is None:
        ttl_seconds = DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS
    if published_at + timedelta(seconds=ttl_seconds) < now:
        return DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_stale",
            role=role,
            field="published_at",
            message="Data Forge snapshot binding is stale for its freshness TTL.",
            value=published_at.isoformat(),
        )
    return None


def _normalize_binding_surface(binding: dict[str, Any]) -> None:
    role = _clean_text(binding.get("role"))
    surface = _clean_text(binding.get("read_api_surface"))
    if (
        surface
        and not _clean_text(binding.get("read_api_module"))
        and surface in available_surfaces()
    ):
        binding["read_api_module"] = surface_module(surface)
    elif not surface and role in DATA_FORGE_SNAPSHOT_ROLE_SURFACES:
        expected = DATA_FORGE_SNAPSHOT_ROLE_SURFACES[role]
        binding["read_api_surface"] = expected
        binding["read_api_module"] = surface_module(expected)


def _ref_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [_clean_text(value) or ""]
    if not isinstance(value, list | tuple):
        return []
    refs: list[str] = []
    for item in value:
        if isinstance(item, str):
            ref = _clean_text(item)
        elif isinstance(item, Mapping):
            ref = _clean_text(
                item.get("artifact_id")
                or item.get("artifact_ref")
                or item.get("ref")
                or item.get("uri")
            )
        else:
            ref = None
        if ref:
            refs.append(ref)
    return refs


def _looks_artifact_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if text.startswith("sha256:") and len(text) == 71:
        return all(char in "0123456789abcdef" for char in text.removeprefix("sha256:"))
    if text.startswith("cas://sha256/") and len(text) == 77:
        return all(char in "0123456789abcdef" for char in text.removeprefix("cas://sha256/"))
    return text.startswith("artifact://")


def _looks_runtime_event_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _looks_artifact_ref(text) or text.startswith("event://")


def _looks_local_path(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    lowered = text.casefold()
    return lowered.startswith(_LOCAL_PATH_PREFIXES) or lowered.startswith(
        ("tests/", "tmp/", "var/folders/")
    )


def _parse_datetime(value: object) -> datetime | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    return text


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "DATA_FORGE_SNAPSHOT_BINDING_FILE",
    "DATA_FORGE_SNAPSHOT_BINDING_GATE",
    "DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY",
    "DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION",
    "REQUIRED_DATA_FORGE_SNAPSHOT_ROLES",
    "data_forge_snapshot_binding_scorecard_gates",
    "normalize_data_forge_snapshot_binding_report",
]
