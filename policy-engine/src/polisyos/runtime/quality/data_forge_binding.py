"""Runtime Data Forge snapshot/read-API binding evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from polisyos.data_forge.read_api import OfficialSnapshotAnswer
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
_BROAD_REQUIREMENT_KINDS = {
    "broad_bundle",
    "broad_context",
    "broad_dataset_label",
    "context_inventory",
    "dataset_bundle",
    "generic_dataset",
}
_TIME_ROLES = {
    "detection_time",
    "freshness_time",
    "ingestion_time",
    "observation_time",
    "publication_time",
    "release_time",
    "replay_time",
    "snapshot_time",
    "transaction_time",
    "valid_time",
}


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
        _normalize_binding_report_defaults(binding, source)
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
    payload["capability_reality_status"] = "implemented"
    payload["runtime_authority_envelope"] = _authority_envelope()
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
        "claim_requirement_binding_count": sum(
            len(_claim_requirement_rows(binding)) for binding in bindings
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


def _json_mapping_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [
        {str(key): _json_value(item) for key, item in row.items()}
        for row in value
        if isinstance(row, Mapping)
    ]


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
    issues.extend(_official_identity_issues(binding=binding, role=role))

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
    issues.extend(_provenance_manifest_issues(binding=binding, role=role))
    issues.extend(_lineage_issues(binding=binding, role=role))
    issues.extend(_claim_requirement_issues(binding=binding, role=role))
    freshness_issue = _freshness_issue(binding=binding, role=role, now=now)
    if freshness_issue is not None:
        issues.append(freshness_issue)
    return issues


def _official_identity_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    release_id = _clean_text(binding.get("release_id"))
    release_manifest_ref = _clean_text(binding.get("release_manifest_ref"))
    merkle = _clean_text(binding.get("merkle_root") or binding.get("merkle_hash"))
    data_hash = _clean_text(binding.get("data_hash") or binding.get("content_hash"))
    read_api_identity = _clean_text(binding.get("read_api_identity"))
    surface = _clean_text(binding.get("read_api_surface"))
    runtime_event_ref = _clean_text(
        binding.get("runtime_event_ref") or binding.get("release_event_ref")
    )
    if not release_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_id_missing",
                role=role,
                field="release_id",
                message="Data Forge snapshot binding is missing official release_id.",
            )
        )
    if _looks_local_path(release_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_manifest_local_path_substitution",
                role=role,
                field="release_manifest_ref",
                message=(
                    "Data Forge release manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=release_manifest_ref,
            )
        )
    elif not _looks_artifact_ref(release_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_manifest_ref_missing",
                role=role,
                field="release_manifest_ref",
                message="Data Forge snapshot binding is missing release manifest identity.",
            )
        )
    if not _looks_sha256_hex(merkle):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_merkle_root_missing",
                role=role,
                field="merkle_root",
                message="Data Forge snapshot binding is missing a sha256 Merkle root.",
                value=merkle,
            )
        )
    if _looks_local_path(data_hash):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_data_hash_local_path_substitution",
                role=role,
                field="data_hash",
                message=(
                    "Data Forge snapshot data hash must be hash identity, not a local "
                    "filesystem path."
                ),
                value=data_hash,
            )
        )
    elif not _looks_hash_ref(data_hash):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_data_hash_missing",
                role=role,
                field="data_hash",
                message="Data Forge snapshot binding is missing data hash identity.",
                value=data_hash,
            )
        )
    if not read_api_identity:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_identity_missing",
                role=role,
                field="read_api_identity",
                message="Data Forge snapshot binding is missing read_api_identity.",
            )
        )
    elif surface and not read_api_identity.startswith(f"{surface}@"):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_identity_mismatch",
                role=role,
                field="read_api_identity",
                message="Data Forge read_api_identity must be scoped to read_api_surface.",
                value=read_api_identity,
            )
        )
    if not _looks_runtime_event_ref(runtime_event_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_runtime_event_ref_missing",
                role=role,
                field="runtime_event_ref",
                message="Data Forge snapshot binding is missing a persisted runtime event ref.",
                value=runtime_event_ref,
            )
        )
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


def _lineage_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    prov = binding.get("prov") or binding.get("prov_lineage")
    openlineage = binding.get("openlineage") or binding.get("openlineage_lineage")
    if not isinstance(prov, Mapping):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_prov_lineage_missing",
                role=role,
                field="prov",
                message="Data Forge snapshot binding is missing PROV lineage.",
            )
        )
    else:
        missing = [
            field
            for field in ("entity", "activity", "agent")
            if not _clean_text(prov.get(field))
        ]
        if missing:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_prov_lineage_incomplete",
                    role=role,
                    field="prov",
                    message="Data Forge PROV lineage is missing entity, activity, or agent.",
                    value=missing,
                )
            )
    if not isinstance(openlineage, Mapping):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_openlineage_missing",
                role=role,
                field="openlineage",
                message="Data Forge snapshot binding is missing OpenLineage lineage.",
            )
        )
    else:
        job = openlineage.get("job")
        run = openlineage.get("run")
        outputs = openlineage.get("outputs")
        if not _clean_text(openlineage.get("namespace")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_namespace_missing",
                    role=role,
                    field="openlineage.namespace",
                    message="Data Forge OpenLineage payload is missing namespace.",
                )
            )
        if not isinstance(job, Mapping) or not _clean_text(job.get("name")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_job_missing",
                    role=role,
                    field="openlineage.job",
                    message="Data Forge OpenLineage payload is missing job identity.",
                )
            )
        if not isinstance(run, Mapping) or not _clean_text(run.get("runId")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_run_missing",
                    role=role,
                    field="openlineage.run",
                    message="Data Forge OpenLineage payload is missing run identity.",
                )
            )
        if not isinstance(outputs, list) or not outputs:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_outputs_missing",
                    role=role,
                    field="openlineage.outputs",
                    message="Data Forge OpenLineage payload is missing output datasets.",
                )
            )
        elif not _openlineage_outputs_have_hash_facets(outputs):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_hash_facets_missing",
                    role=role,
                    field="openlineage.outputs[].facets",
                    message=(
                        "Data Forge OpenLineage outputs must preserve dataHash and "
                        "merkleRoot facets."
                    ),
                )
            )
    return issues


def _claim_requirement_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    rows = _claim_requirement_rows(binding)
    if not rows:
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_claim_requirement_binding_missing",
                role=role,
                field="claim_requirement_bindings",
                message=(
                    "Data Forge snapshot binding is missing claim requirement bindings; "
                    "file availability cannot satisfy closeout-grade data authority."
                ),
            )
        ]

    issues: list[DataForgeSnapshotBindingIssue] = []
    authority_refs = set(_binding_authority_refs(binding))
    for index, row in enumerate(rows, start=1):
        claim_id = _clean_text(row.get("claim_id"))
        requirement_id = _clean_text(row.get("requirement_id"))
        requirement_kind = _clean_text(row.get("requirement_kind"))
        authority_level = _clean_text(row.get("authority_level"))
        time_role = _clean_text(row.get("time_role"))
        supported_by = _ref_list(row.get("supported_by") or row.get("supported_by_refs"))
        lifecycle_refs = _ref_list(row.get("lifecycle_dependency_refs"))
        if not claim_id:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_claim_id_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].claim_id",
                    message="Data Forge claim requirement binding is missing claim_id.",
                )
            )
        if not requirement_id:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_id_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_id",
                    message="Data Forge claim requirement binding is missing requirement_id.",
                )
            )
        if not requirement_kind:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_kind_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_kind",
                    message=(
                        "Data Forge claim requirement binding is missing requirement_kind."
                    ),
                )
            )
        elif requirement_kind.casefold() in _BROAD_REQUIREMENT_KINDS:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_broad_label",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_kind",
                    message=(
                        "Broad dataset labels are context only and cannot satisfy "
                        "claim data requirements."
                    ),
                    value=requirement_kind,
                )
            )
        if not authority_level or authority_level.casefold() in {"context", "context_only"}:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_authority_level_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].authority_level",
                    message=(
                        "Data Forge claim requirement binding must declare a non-context "
                        "authority level."
                    ),
                    value=authority_level,
                )
            )
        if not time_role or time_role.casefold() not in _TIME_ROLES:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_time_role_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].time_role",
                    message=(
                        "Data Forge claim requirement binding must declare an explicit "
                        "time role."
                    ),
                    value=time_role,
                )
            )
        if not supported_by:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_support_ref_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].supported_by",
                    message=(
                        "Data Forge claim requirement binding must cite snapshot, "
                        "manifest, or artifact refs."
                    ),
                )
            )
        for ref in supported_by:
            if _looks_local_path(ref) or ref.casefold() in {"dataset", "datasets", "bundle"}:
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_broad_label",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].supported_by",
                        message=(
                            "Claim requirement support must cite official Data Forge "
                            "artifact identity, not a broad dataset label."
                        ),
                        value=ref,
                    )
                )
            elif not _looks_artifact_ref(ref) or ref not in authority_refs:
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_support_ref_invalid",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].supported_by",
                        message=(
                            "Claim requirement support ref must be one of the official "
                            "snapshot, manifest, release, or artifact refs in the binding."
                        ),
                        value=ref,
                    )
                )
        if not lifecycle_refs:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_lifecycle_ref_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].lifecycle_dependency_refs",
                    message=(
                        "Data Forge claim requirement binding must cite lifecycle "
                        "dependency refs for reissue checks."
                    ),
                )
            )
        for ref in lifecycle_refs:
            if not _looks_runtime_event_ref(ref):
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_lifecycle_ref_invalid",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].lifecycle_dependency_refs",
                        message="Lifecycle dependency refs must be event or artifact refs.",
                        value=ref,
                    )
                )
    return issues


def official_data_forge_snapshot_for_claim(
    report: Mapping[str, Any] | None,
    *,
    claim_id: str,
    requirement_id: str | None = None,
    now: datetime | None = None,
) -> OfficialSnapshotAnswer:
    """Return the official Data Forge snapshot satisfying a claim requirement."""

    normalized = normalize_data_forge_snapshot_binding_report(
        report,
        now=_official_snapshot_evaluation_time(report, now=now),
    )
    issues_by_role: dict[str, str] = {}
    for raw_issue in normalized.get("issues", []):
        if not isinstance(raw_issue, Mapping):
            continue
        role = _clean_text(raw_issue.get("role"))
        code = _clean_text(raw_issue.get("code"))
        if role and code:
            issues_by_role.setdefault(role, code)

    for binding in _binding_rows(normalized):
        role = _clean_text(binding.get("role"))
        answer = _official_snapshot_answer_from_binding(
            binding,
            claim_id=claim_id,
            requirement_id=requirement_id,
            blocked_reason=issues_by_role.get(role or ""),
        )
        if answer is not None:
            return answer
    return OfficialSnapshotAnswer(
        status="not_found",
        claim_id=claim_id,
        requirement_id=requirement_id,
        reason="claim_requirement_binding_missing",
    )


def _official_snapshot_evaluation_time(
    report: Mapping[str, Any] | None,
    *,
    now: datetime | None,
) -> datetime | None:
    if now is not None:
        return _utc(now)
    if not isinstance(report, Mapping):
        return None
    return _parse_datetime(report.get("observed_at"))


def _official_snapshot_answer_from_binding(
    binding: Mapping[str, Any],
    *,
    claim_id: str,
    requirement_id: str | None = None,
    blocked_reason: str | None = None,
) -> OfficialSnapshotAnswer | None:
    for row in _claim_requirement_rows(binding):
        row_claim_id = _clean_text(row.get("claim_id"))
        row_requirement_id = _clean_text(row.get("requirement_id"))
        if row_claim_id != claim_id:
            continue
        if requirement_id is not None and row_requirement_id != requirement_id:
            continue
        return OfficialSnapshotAnswer(
            status="blocked" if blocked_reason else "satisfied",
            claim_id=claim_id,
            requirement_id=requirement_id or row_requirement_id,
            role=_clean_text(binding.get("role")),
            corpus_id=_clean_text(binding.get("corpus_id")),
            snapshot_id=_clean_text(binding.get("snapshot_id")),
            snapshot_ref=_clean_text(binding.get("snapshot_ref")),
            data_hash=_clean_text(binding.get("data_hash")),
            creation_time=_clean_text(binding.get("creation_time")),
            lineage_refs=tuple(_ref_list(binding.get("lineage_refs"))),
            quality_gates=tuple(_json_mapping_rows(binding.get("quality_gates"))),
            builder_revision=_clean_text(binding.get("builder_revision")),
            transform_lineage=tuple(
                _json_mapping_rows(binding.get("transform_lineage"))
            ),
            supported_by=tuple(_ref_list(row.get("supported_by"))),
            lifecycle_dependency_refs=tuple(
                _ref_list(row.get("lifecycle_dependency_refs"))
            ),
            reason=blocked_reason,
        )
    return None


def _provenance_manifest_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    corpus_id = _clean_text(binding.get("corpus_id"))
    provenance_manifest_ref = _clean_text(binding.get("provenance_manifest_ref"))
    creation_time = binding.get("creation_time")
    lineage_refs = _ref_list(binding.get("lineage_refs"))
    builder_revision = _clean_text(binding.get("builder_revision"))
    transform_lineage = binding.get("transform_lineage")

    if not corpus_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_corpus_id_missing",
                role=role,
                field="corpus_id",
                message="Data Forge snapshot provenance manifest is missing corpus_id.",
            )
        )
    if _looks_local_path(provenance_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_provenance_manifest_local_path_substitution",
                role=role,
                field="provenance_manifest_ref",
                message=(
                    "Data Forge provenance manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=provenance_manifest_ref,
            )
        )
    elif not _looks_artifact_ref(provenance_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_provenance_manifest_ref_missing",
                role=role,
                field="provenance_manifest_ref",
                message=(
                    "Data Forge snapshot binding is missing durable provenance "
                    "manifest identity."
                ),
                value=provenance_manifest_ref,
            )
        )
    if _parse_datetime(creation_time) is None:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_creation_time_missing",
                role=role,
                field="creation_time",
                message=(
                    "Data Forge provenance manifest must preserve snapshot creation_time."
                ),
                value=creation_time,
            )
        )
    if not lineage_refs:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_lineage_refs_missing",
                role=role,
                field="lineage_refs",
                message=(
                    "Data Forge provenance manifest must preserve source lineage refs."
                ),
            )
        )
    for index, ref in enumerate(lineage_refs, start=1):
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_lineage_ref_local_path_substitution",
                    role=role,
                    field=f"lineage_refs[{index}]",
                    message=(
                        "Data Forge lineage refs must be artifact/event refs, not local "
                        "filesystem paths."
                    ),
                    value=ref,
                )
            )
        elif not _looks_lineage_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_lineage_ref_invalid",
                    role=role,
                    field=f"lineage_refs[{index}]",
                    message="Data Forge lineage ref is not a recognized durable ref.",
                    value=ref,
                )
            )
    if not builder_revision:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_builder_revision_missing",
                role=role,
                field="builder_revision",
                message=(
                    "Data Forge provenance manifest is missing builder_revision."
                ),
            )
        )
    if not isinstance(transform_lineage, list) or not transform_lineage:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_transform_lineage_missing",
                role=role,
                field="transform_lineage",
                message=(
                    "Data Forge provenance manifest is missing transform lineage."
                ),
            )
        )
        return issues
    for index, step in enumerate(transform_lineage, start=1):
        if not isinstance(step, Mapping):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_step_invalid",
                    role=role,
                    field=f"transform_lineage[{index}]",
                    message="Data Forge transform lineage step must be a mapping.",
                )
            )
            continue
        if not _clean_text(step.get("step_id")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_step_id_missing",
                    role=role,
                    field=f"transform_lineage[{index}].step_id",
                    message="Data Forge transform lineage step is missing step_id.",
                )
            )
        if not _clean_text(step.get("operation")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_operation_missing",
                    role=role,
                    field=f"transform_lineage[{index}].operation",
                    message="Data Forge transform lineage step is missing operation.",
                )
            )
        if not _ref_list(step.get("input_refs")) and not _ref_list(step.get("output_refs")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_refs_missing",
                    role=role,
                    field=f"transform_lineage[{index}]",
                    message=(
                        "Data Forge transform lineage step must cite input or output refs."
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


def _normalize_binding_report_defaults(
    binding: dict[str, Any],
    report: Mapping[str, Any],
) -> None:
    for field in ("release_id", "release_manifest_ref"):
        if not _clean_text(binding.get(field)) and _clean_text(report.get(field)):
            binding[field] = report[field]
    surface = _clean_text(binding.get("read_api_surface"))
    snapshot_id = _clean_text(binding.get("snapshot_id"))
    if surface and snapshot_id and not _clean_text(binding.get("read_api_identity")):
        binding["read_api_identity"] = f"{surface}@{snapshot_id}"


def _claim_requirement_rows(binding: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = binding.get("claim_requirement_bindings") or binding.get("claim_requirements")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _binding_authority_refs(binding: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for field in (
        "snapshot_ref",
        "manifest_ref",
        "manifest_artifact_id",
        "manifest_artifact_ref",
        "release_manifest_ref",
        "provenance_manifest_ref",
        "data_hash",
    ):
        refs.extend(_ref_list(binding.get(field)))
    refs.extend(_ref_list(binding.get("artifact_ids") or binding.get("artifact_refs")))
    refs.extend(_ref_list(binding.get("quality_gates") or binding.get("quality_gate_refs")))
    return tuple(dict.fromkeys(ref for ref in refs if _looks_artifact_ref(ref)))


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


def _openlineage_outputs_have_hash_facets(outputs: Sequence[object]) -> bool:
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        facets = output.get("facets")
        if not isinstance(facets, Mapping):
            continue
        if isinstance(facets.get("dataHash"), Mapping) and isinstance(
            facets.get("merkleRoot"), Mapping
        ):
            return True
    return False


def _looks_artifact_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if text.startswith("sha256:") and len(text) == 71:
        return all(char in "0123456789abcdef" for char in text.removeprefix("sha256:"))
    if text.startswith("cas://sha256/") and len(text) == 77:
        return all(char in "0123456789abcdef" for char in text.removeprefix("cas://sha256/"))
    return text.startswith("artifact://")


def _looks_hash_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _looks_artifact_ref(text) or _looks_sha256_hex(text)


def _looks_sha256_hex(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if text.startswith("sha256:"):
        text = text.removeprefix("sha256:")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _looks_runtime_event_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _looks_artifact_ref(text) or text.startswith("event://")


def _looks_lineage_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return (
        _looks_artifact_ref(text)
        or text.startswith("event://")
        or text.startswith("lineage:")
        or text.startswith("prov:")
        or text.startswith("openlineage:")
    )


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


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "official_snapshot_identity",
            "release_manifest_identity",
            "read_api_identity",
            "merkle_and_data_hashes",
            "quality_gate_results",
            "prov_openlineage_lineage",
            "claim_requirement_bindings",
        ),
        "may_not_use_for": (
            "claim_support",
            "legal_authority",
            "method_validity",
            "academic_support_strength",
            "participation_representativeness",
            "source_family_satisfaction_without_fabric_binding",
        ),
    }


__all__ = [
    "DATA_FORGE_SNAPSHOT_BINDING_FILE",
    "DATA_FORGE_SNAPSHOT_BINDING_GATE",
    "DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY",
    "DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION",
    "REQUIRED_DATA_FORGE_SNAPSHOT_ROLES",
    "data_forge_snapshot_binding_scorecard_gates",
    "normalize_data_forge_snapshot_binding_report",
    "official_data_forge_snapshot_for_claim",
]
