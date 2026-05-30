"""Can-I-Closeout compatibility matrix for deployed evidence bundles."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from polisyos.runtime.quality.scorecard import (
    QUALITY_REPORT_FILES,
    QUALITY_REPORT_GATE_METADATA,
)

if TYPE_CHECKING:
    from pathlib import Path

SCHEMA_VERSION = "policyos.runtime.can_i_closeout_compatibility.v1"
COMPATIBILITY_FILENAME = "can_i_closeout_compatibility.json"
COMPATIBILITY_BUNDLE_PATH = f"quality_evidence/{COMPATIBILITY_FILENAME}"
SERIOUS_PROFILES = frozenset({"research", "governed", "production"})
COMPATIBLE_SCHEMA_DECISIONS = frozenset(
    {"accepted", "backward_compatible", "compatible", "exact", "pass"}
)


def build_closeout_compatibility_record(
    *,
    bundle_payload: Mapping[str, Any] | None,
    scorecard_payload: Mapping[str, Any] | None,
    quality_reports: Mapping[str, Any] | None,
    authority_profile_version: str | None = None,
    validation_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deployed producer/reader/authority compatibility record."""

    bundle = dict(bundle_payload or {})
    scorecard = dict(scorecard_payload or {})
    reports = {
        str(key): value
        for key, value in (quality_reports or {}).items()
        if isinstance(value, Mapping)
    }
    command = _command_payload(bundle)
    git_sha = _text(bundle.get("git_sha"))
    code_revision = _code_revision(bundle)
    scenario = _scenario_contract(bundle, reports)
    profile = _profile_from_bundle(bundle)
    provider = _provider_from_command(command)
    serious_live_or_cloud = _serious_live_or_cloud_bundle(
        bundle=bundle,
        profile=profile,
        provider=provider,
    )
    matrix = _producer_reader_matrix(
        scorecard_payload=scorecard,
        quality_reports=reports,
        validation_refs=validation_refs or {},
    )
    issues: list[dict[str, Any]] = []
    if serious_live_or_cloud and not git_sha:
        issues.append(
            _issue(
                "closeout_git_sha_missing",
                "Serious cloud/live closeout requires the deployed git_sha.",
                next_action=(
                    "Rebuild the bundle from a checked-out revision and persist git_sha "
                    "before closeout."
                ),
            )
        )
    if serious_live_or_cloud and not code_revision:
        issues.append(
            _issue(
                "closeout_code_revision_missing",
                "Serious cloud/live closeout requires the deployed code revision.",
                next_action=(
                    "Persist code_revision alongside git_sha in the evidence bundle "
                    "before closeout."
                ),
            )
        )
    for row in matrix:
        if row["status"] == "pass":
            continue
        issues.append(
            _issue(
                "closeout_reader_schema_pair_unverified",
                (
                    "Producer report schema has not been verified against the active "
                    f"reader gate {row['reader_gate']}."
                ),
                next_action=(
                    "Run schema compatibility for the producer report and persist "
                    "schema_compatibility.decision, reader_gate_version, and validation_ref."
                ),
                report_key=row["report_key"],
                reader_gate=row["reader_gate"],
                producer_schema_version=row["producer_schema_version"],
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "summary": {
            "producer_reader_pair_count": len(matrix),
            "verified_pair_count": sum(1 for row in matrix if row["status"] == "pass"),
            "issue_count": len(issues),
        },
        "deployment_context": {
            "canary_kind": _text(bundle.get("canary_kind")),
            "profile": profile,
            "provider": provider,
            "serious_live_or_cloud_bundle": serious_live_or_cloud,
            "git_sha": git_sha,
            "code_revision": code_revision,
            "command": command,
        },
        "scenario_contract": scenario,
        "authority_profile": {
            "version": authority_profile_version
            or _text(bundle.get("authority_profile_version"))
            or _text(bundle.get("canary_kind"))
            or "unknown",
        },
        "producer_reader_matrix": matrix,
        "issues": issues,
    }


def build_closeout_compatibility_record_from_bundle_dir(
    bundle_dir: Path,
    *,
    authority_profile_version: str | None = None,
) -> dict[str, Any]:
    """Load a bundle directory and rebuild the compatibility record from files."""

    root = bundle_dir.resolve()
    quality_dir = root / "quality_evidence"
    quality_reports: dict[str, Any] = {}
    for report_key, filename in QUALITY_REPORT_FILES.items():
        payload = _load_json_or_none(quality_dir / filename)
        if isinstance(payload, Mapping):
            quality_reports[report_key] = dict(payload)
    for path in sorted(quality_dir.glob("*.json")) if quality_dir.exists() else []:
        if path.name in {"quality_scorecard.json", COMPATIBILITY_FILENAME}:
            continue
        key = path.stem
        quality_reports.setdefault(key, _load_json_or_none(path) or {})
    return build_closeout_compatibility_record(
        bundle_payload=_load_json_or_none(root / "bundle.json") or {},
        scorecard_payload=_load_json_or_none(quality_dir / "quality_scorecard.json") or {},
        quality_reports=quality_reports,
        authority_profile_version=authority_profile_version,
    )


def compatibility_failures_for_readiness(
    record: Mapping[str, Any],
    *,
    bundle_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Convert compatibility issues into readiness closeout blocker rows."""

    failures: list[dict[str, Any]] = []
    for issue in record.get("issues") or []:
        if not isinstance(issue, Mapping):
            continue
        code = _text(issue.get("code")) or "closeout_compatibility_failed"
        failures.append(
            {
                "source": "can_i_closeout_compatibility",
                "status": "fail",
                "code": code,
                "minimum_closeout_gate": "can_i_closeout_compatibility",
                "bundle_root": str(bundle_root) if bundle_root is not None else None,
                "message": _text(issue.get("message"))
                or "Can-I-Closeout compatibility matrix failed.",
                "evidence": dict(issue),
                "next_action": _text(issue.get("next_action"))
                or "Rebuild closeout compatibility evidence for the selected bundle.",
                "expected_verification_command": (
                    "uv run python tools/quality/validation/check_can_i_closeout.py "
                    "--repo-root . --bundle-dir <bundle-dir> "
                    "--json-output _build/.tmp/production-quality/can_i_closeout.json"
                ),
            }
        )
    return failures


def _producer_reader_matrix(
    *,
    scorecard_payload: Mapping[str, Any],
    quality_reports: Mapping[str, Any],
    validation_refs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gates = _scorecard_gates_by_name(scorecard_payload)
    rows: list[dict[str, Any]] = []
    for report_key, report in sorted(quality_reports.items()):
        if report_key not in QUALITY_REPORT_GATE_METADATA:
            continue
        gate_name = QUALITY_REPORT_GATE_METADATA[report_key][0]
        gate = gates.get(gate_name)
        if gate is None:
            continue
        report_map = dict(report)
        schema_version = _text(report_map.get("schema_version"))
        if not schema_version:
            continue
        compatibility = (
            report_map.get("schema_compatibility")
            if isinstance(report_map.get("schema_compatibility"), Mapping)
            else {}
        )
        decision = _text(
            compatibility.get("decision") if isinstance(compatibility, Mapping) else None
        ) or _text(compatibility.get("status") if isinstance(compatibility, Mapping) else None)
        validation_ref = (
            _text(compatibility.get("validation_ref"))
            or _text(compatibility.get("schema_compatibility_ref"))
            or _text(validation_refs.get(report_key))
        )
        reader_gate_version = (
            _text(gate.get("reader_gate_version"))
            or _text(gate.get("schema_version"))
            or _text(compatibility.get("reader_gate_version"))
            or f"runtime.scorecard.{gate_name}.v1"
        )
        compatibility_reader_version = _text(compatibility.get("reader_gate_version"))
        verified = (
            decision in COMPATIBLE_SCHEMA_DECISIONS
            and bool(validation_ref)
            and (
                not compatibility_reader_version
                or compatibility_reader_version == reader_gate_version
            )
        )
        rows.append(
            {
                "report_key": report_key,
                "producer_schema_version": schema_version,
                "reader_gate": gate_name,
                "reader_gate_version": reader_gate_version,
                "reader_gate_status": _text(gate.get("status")) or "unknown",
                "schema_compatibility_decision": decision or "missing",
                "validation_ref": validation_ref,
                "status": "pass" if verified else "fail",
            }
        )
    return rows


def _scorecard_gates_by_name(scorecard_payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    gates = scorecard_payload.get("quality_gates")
    if not isinstance(gates, list):
        return {}
    rows: dict[str, Mapping[str, Any]] = {}
    for gate in gates:
        if not isinstance(gate, Mapping):
            continue
        name = _text(gate.get("name") or gate.get("gate"))
        if name:
            rows[name] = gate
    return rows


def _scenario_contract(bundle: Mapping[str, Any], reports: Mapping[str, Any]) -> dict[str, Any]:
    for payload in (
        bundle.get("scenario_evidence_contract"),
        bundle.get("scenario_contract"),
        reports.get("golden_scenario_contract"),
    ):
        if not isinstance(payload, Mapping):
            continue
        contract_id = _text(
            payload.get("contract_id")
            or payload.get("scenario_evidence_contract_id")
            or payload.get("scenario_id")
        )
        version = _text(payload.get("version") or payload.get("contract_version"))
        return {"id": contract_id, "version": version}
    command = _command_payload(bundle)
    return {
        "id": _text(command.get("scenario_contract_id") or command.get("scenario")),
        "version": _text(command.get("scenario_contract_version")),
    }


def _command_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    command = bundle.get("command")
    return dict(command) if isinstance(command, Mapping) else {}


def _code_revision(bundle: Mapping[str, Any]) -> str | None:
    raw = bundle.get("code_revision")
    if isinstance(raw, str):
        return _text(raw)
    if isinstance(raw, Mapping):
        return _text(
            raw.get("git_sha")
            or raw.get("commit")
            or raw.get("revision")
            or raw.get("code_revision")
        )
    return _text(bundle.get("code_revision_sha") or bundle.get("commit"))


def _profile_from_bundle(bundle: Mapping[str, Any]) -> str:
    canary_kind = _text(bundle.get("canary_kind"))
    if canary_kind:
        return canary_kind
    lane_id = _matrix_lane_id(_command_payload(bundle)) or ""
    for part in lane_id.split("__"):
        key, _, value = part.partition("-")
        if key == "profile":
            return value
    return ""


def _provider_from_command(command: Mapping[str, Any]) -> str:
    explicit = _text(command.get("provider") or command.get("provider_mode"))
    if explicit:
        return explicit
    lane_id = _matrix_lane_id(command) or ""
    for part in lane_id.split("__"):
        key, _, value = part.partition("-")
        if key == "provider":
            return value
    argv = command.get("argv")
    if isinstance(argv, list) and any(str(item) == "--mode=real" for item in argv):
        return "live"
    return ""


def _matrix_lane_id(command: Mapping[str, Any]) -> str:
    return _text(command.get("matrix_lane_id") or command.get("lane_id"))


def _serious_live_or_cloud_bundle(
    *,
    bundle: Mapping[str, Any],
    profile: str,
    provider: str,
) -> bool:
    execution_target = (
        _text(
            bundle.get("execution_environment")
            or bundle.get("deployment_target")
            or bundle.get("runtime_environment")
        )
        or ""
    ).casefold()
    provider_normalized = provider.casefold()
    return profile in SERIOUS_PROFILES and (
        "live" in provider_normalized
        or "cloud" in execution_target
        or execution_target in {"gcp", "google_cloud", "production_cloud"}
    )


def _load_json_or_none(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _issue(
    code: str,
    message: str,
    *,
    next_action: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "message": message,
        "next_action": next_action,
        **{key: value for key, value in extra.items() if value not in (None, "", [])},
    }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "COMPATIBILITY_BUNDLE_PATH",
    "COMPATIBILITY_FILENAME",
    "SCHEMA_VERSION",
    "build_closeout_compatibility_record",
    "build_closeout_compatibility_record_from_bundle_dir",
    "compatibility_failures_for_readiness",
]
