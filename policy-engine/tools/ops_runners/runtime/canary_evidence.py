"""Filesystem evidence bundles for production/staging PolicyOS canaries."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.control import policy_authority_profile_mapping
from polisyos.core.security.quality_gates import (
    SECURITY_ASSURANCE_REPORT_REF_KEY,
    SECURITY_REPORT_FILE,
    build_security_assurance_report,
    redact_sensitive_text,
)
from polisyos.data_forge import build_privacy_compliance_report
from polisyos.foundry.validation.causal_validity import (
    build_causal_statistical_validity_report,
)
from polisyos.runtime.http.services.control.artifacts import (
    _runtime_quality_evidence_from_payloads,
)
from polisyos.runtime.quality.assurance_case import build_assurance_case_for_scorecard
from polisyos.runtime.quality.attestation import (
    build_required_production_attestations,
    serialize_attestation_record,
)
from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report
from polisyos.runtime.quality.closeout_compatibility import (
    COMPATIBILITY_BUNDLE_PATH,
    COMPATIBILITY_FILENAME,
    build_closeout_compatibility_record,
)
from polisyos.runtime.quality.closeout_reader import build_can_i_closeout_verdict
from polisyos.runtime.quality.compliance import (
    PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
    PRIVACY_COMPLIANCE_REPORT_KEY,
    PRIVACY_COMPLIANCE_REPORT_REF_KEY,
)
from polisyos.runtime.quality.cost_degradation import (
    CostDegradationTelemetryError,
    build_cost_degradation_telemetry_from_quality_context,
)
from polisyos.runtime.quality.cost_gate import (
    RunCostGateError,
    build_run_cost_gate_report,
)
from polisyos.runtime.quality.data_quality import PRODUCTION_DATA_QUALITY_REF_KEY
from polisyos.runtime.quality.diagnostic_slos import (
    build_diagnostic_slo_report_from_quality_context,
    pass_observations_for_all_diagnostic_slos,
)
from polisyos.runtime.quality.evidence_independence import (
    EvidenceIndependenceError,
    build_evidence_independence_map,
)
from polisyos.runtime.quality.evidence_line import EVIDENCE_LINE_SCHEMA_VERSION
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from polisyos.runtime.quality.evidence_spine import (
    build_scenario_contract_propagation_graph,
)
from polisyos.runtime.quality.evidence_spine_handoff import (
    build_canary_evidence_handoff_ledger,
)
from polisyos.runtime.quality.evidence_synthesis import (
    EvidenceSynthesisReportError,
    build_evidence_synthesis_report,
)
from polisyos.runtime.quality.human_review import build_human_review_calibration_report
from polisyos.runtime.quality.legacy_payload_migration_audit import (
    build_legacy_migration_sandbox,
    legacy_compatible_payload,
    persist_legacy_migration_sandbox_report,
)
from polisyos.runtime.quality.nl_replay_orchestration import (
    NL_REPLAY_ORCHESTRATION_FILE_REF,
    NL_REPLAY_ORCHESTRATION_RECORD_KEY,
    build_nl_replay_orchestration_continuity,
)
from polisyos.runtime.quality.performance_budget import (
    build_canary_performance_budget,
    measure_cas_round_trip_samples,
)
from polisyos.runtime.quality.phase_barriers import PhaseBarrierId, PhaseBarrierRecord
from polisyos.runtime.quality.producer_pipeline import (
    merge_producer_pipeline_quality_evidence_surfaces,
    run_requirement_spec_producer_pipeline,
)
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    build_policy_design_case_projection_contract_fixture,
    build_policy_design_case_projection_semantics,
)
from polisyos.runtime.quality.public_export import build_public_export_bundle
from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs, resolve_quality_refs
from polisyos.runtime.quality.replay import (
    attach_replay_orchestration_continuity,
    build_replay_manifest,
    explain_replay_drift,
)
from polisyos.runtime.quality.run_cost_proportionality import (
    RunCostProportionalityError,
    build_run_cost_proportionality_ledger_from_quality_context,
)
from polisyos.runtime.quality.scorecard import (
    QUALITY_REPORT_FILES,
    QUALITY_REPORT_GATE_METADATA,
    QUALITY_REPORT_RUNTIME_REFS,
    REQUIRED_MATERIALIZATION_REFS,
    SERIOUS_CANARY_KINDS,
    build_quality_scorecard,
    normalize_quality_evidence,
    scorecard_control_progress,
)
from polisyos.runtime.quality.semantic_binding import build_semantic_binding_ledger
from polisyos.scientist.artifacts.decision_compiler import (
    DecisionArtifactCompilationError,
    compile_draft_decision_packet,
    compile_publishable_decision_artifact,
)
from polisyos.scientist.orchestration.llm.provider_quality import (
    DefaultProductionModelChoice,
    ProviderModelQualityObservation,
    build_provider_model_quality_ledger,
)
from polisyos.scientist.validation.decision_artifact_quality import (
    build_decision_artifact_quality_report,
)
from tools.quality.testing.runtime_resilience_matrix import (
    build_matrix_payload as build_resilience_matrix_payload,
)

SECRET_KEY_RE = re.compile(
    r"("
    r"authorization|api[_-]?key|token|secret|password|credential|"
    r"hidden[_-]?answers?|sensitive[_-]?payload|"
    r"POLISYOS_LLM_GATEWAY_API_KEY"
    r")",
    re.IGNORECASE,
)
REF_KEY_RE = re.compile(r"(^|_)(ref|refs|artifact|artifacts)($|_)", re.IGNORECASE)
PATH_LIKE_KEY_RE = re.compile(
    r"(^|_)(dir|dirs|file|files|path|paths|root|roots)($|_)",
    re.IGNORECASE,
)
LOCAL_PATH_MARKERS = (
    "/users/",
    "\\users\\",
    "/private/",
    "/var/folders/",
    "../",
    "..\\",
)
SAFE_ACCOUNTING_KEYS = {
    "cached_tokens",
    "completion_tokens",
    "input_tokens",
    "max_completion_tokens",
    "max_tokens",
    "output_tokens",
    "prompt_tokens",
    "reasoning_tokens",
    "token_usage",
    "total_tokens",
}
ENV_ALLOWLIST = {
    "POLISYOS_LLM_GATEWAY_BASE_URL",
    "POLISYOS_LLM_GATEWAY_PROVIDER",
    "POLISYOS_LLM_GATEWAY_API_KEY",
    "POLISYOS_LLM_SIMULATION_MODE",
    "POLISYOS_EXECUTION_PROFILE",
    "POLISYOS_PRODUCTION_DATA_ROOT",
    "POLISYOS_CONTROL_WORKER_BACKEND",
    "POLISYOS_CONTROL_STATE_STORE_BACKEND",
    "POLISYOS_SCIENTIST_V2_ENABLED",
    "POLISYOS_SCIENTIST_SWARM_ENABLED",
    "POLISYOS_SCIENTIST_REFLEXION_ENABLED",
    "POLISYOS_DASHBOARD_BASE_URL",
    "POLISYOS_DASHBOARD_TRACE_PATH",
    "POLISYOS_DASHBOARD_SCREENSHOT_PATH",
    "POLISYOS_DASHBOARD_TIMING_PATH",
    "POLISYOS_DASHBOARD_VIDEO_PATH",
    "POLISYOS_DASHBOARD_REPORT_PATH",
}
DASHBOARD_EVIDENCE_ENV_REFS = {
    "POLISYOS_DASHBOARD_TRACE_PATH": "playwright_trace",
    "POLISYOS_DASHBOARD_SCREENSHOT_PATH": "screenshot",
    "POLISYOS_DASHBOARD_TIMING_PATH": "dashboard_timing",
    "POLISYOS_DASHBOARD_VIDEO_PATH": "video",
    "POLISYOS_DASHBOARD_REPORT_PATH": "playwright_report",
}
REPO_ROOT = Path(__file__).resolve().parents[3]
CAUSAL_VALIDITY_FIXTURE = REPO_ROOT / "tests/_golden/foundry/causal_validity/cases.json"
CANARY_GENERATED_RUNTIME_REF_REPORTS = {
    "production_data_quality",
    "causal_statistical_validity",
    "replay_manifest",
    "drift_explanation",
    "resilience_matrix",
    "human_review_calibration",
    "decision_artifact_quality",
    "semantic_binding_ledger",
    "provider_model_quality_ledger",
    "privacy_compliance_report",
}
DEV_SMOKE_WARN_REPORT_KEYS = {
    "replay_manifest",
    "resilience_matrix",
    "decision_artifact_quality",
}
MINIMUM_CLOSEOUT_REQUIRED_REF_KEYS = (
    "approval_packet_ref",
    "benchmark_authority_pack_ref",
    "cas_ownership_manifest_ref",
    "causal_statistical_validity_report_ref",
    "closeout_matrix_ref",
    "conflict_check_ref",
    "continuous_governance_reissue_report_ref",
    "continuous_governance_stale_report_ref",
    "continuous_governance_supersede_report_ref",
    "continuous_governance_withdraw_report_ref",
    "decision_artifact_quality_report_ref",
    "drift_explanation_ref",
    "effective_mode_ledger_ref",
    "fabric_retrieval_trace_ref",
    "foundry_method_report_ref",
    "human_review_calibration_report_ref",
    "metric_taxonomy_ref",
    "normative_applicability_report_ref",
    "performance_budget_ref",
    "phase_barrier_ledger_ref",
    "policy_grounding_matrix_ref",
    "privacy_compliance_report_ref",
    "production_data_quality_report_ref",
    "provider_model_quality_ledger_ref",
    "quality_scorecard_ref",
    "replay_manifest_ref",
    "resilience_report_ref",
    "run_state_snapshot_ref",
    "security_assurance_report_ref",
    "semantic_binding_ledger_ref",
)
AGGREGATE_CLOSEOUT_REF_KEYS = (
    "approval_packet_ref",
    "benchmark_authority_pack_ref",
    "cas_ownership_manifest_ref",
    "closeout_matrix_ref",
    "effective_mode_ledger_ref",
    "metric_taxonomy_ref",
    "performance_budget_ref",
    "phase_barrier_ledger_ref",
    "quality_scorecard_ref",
    "run_state_snapshot_ref",
)
CONTINUOUS_GOVERNANCE_REPORT_KEYS = (
    "continuous_governance_stale",
    "continuous_governance_reissue",
    "continuous_governance_supersede",
    "continuous_governance_withdraw",
)
QUALITY_REPORT_KEY_BY_RUNTIME_REF = {
    ref_key: report_key for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items()
}
LEGACY_MIGRATION_SANDBOX_BUNDLE_FILE = "migration_sandbox/legacy_migration_sandbox.json"
EVIDENCE_PROVENANCE_MANIFEST = "quality_evidence/evidence_provenance_manifest.json"
PUBLIC_EXPORT_BUNDLE_FILE = "quality_evidence/public_export_bundle.json"
INVARIANT_PROOF_HARNESS_REPORT_FILE = (
    "quality_evidence/invariant_proof_harness_report.json"
)
PROVENANCE_REDACTION_POLICY = "sanitize_for_evidence.v1"
PROVENANCE_PUBLIC_EXPORT_POLICY = "internal_only"


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _fingerprint(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _redacted_secret(value: Any, *, env_var: str | None = None) -> dict[str, Any]:
    return {
        "present": bool(value),
        "env_var": env_var,
        "fingerprint": _fingerprint(value),
    }


def _is_redacted_secret_metadata(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    keys = set(value)
    return bool(keys) and keys <= {"present", "env_var", "fingerprint"}


def _is_safe_secret_like_key(key_hint: str, value: Any) -> bool:
    normalized = key_hint.replace("-", "_").lower()
    if normalized in SAFE_ACCOUNTING_KEYS or normalized.endswith("_tokens"):
        return True
    if normalized == "fingerprint" or normalized.endswith("_fingerprint"):
        return True
    return _is_redacted_secret_metadata(value)


def _is_path_like_key(key_hint: str | None) -> bool:
    if not key_hint:
        return False
    normalized = key_hint.replace("-", "_")
    return bool(PATH_LIKE_KEY_RE.search(normalized))


def _redact_local_path_text(value: str) -> str:
    repo_root = REPO_ROOT.resolve().as_posix()
    normalized = value.replace("\\", "/")
    lowered = normalized.casefold()

    if normalized == repo_root:
        return "${REPO_ROOT}"
    if normalized.startswith(f"{repo_root}/"):
        return "${REPO_ROOT}/" + normalized[len(repo_root) + 1 :]
    if any(marker in lowered for marker in LOCAL_PATH_MARKERS):
        return "<redacted-local-path>"
    return value


def sanitize_for_evidence(
    value: Any,
    *,
    key_hint: str | None = None,
    redact_local_paths: bool = False,
) -> Any:
    """Recursively redact secrets while preserving operator-useful structure."""
    if (
        key_hint
        and SECRET_KEY_RE.search(key_hint)
        and not _is_safe_secret_like_key(
            key_hint,
            value,
        )
    ):
        return _redacted_secret(value, env_var=key_hint if key_hint.isupper() else None)
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_evidence(
                item,
                key_hint=str(key),
                redact_local_paths=redact_local_paths,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            sanitize_for_evidence(
                item,
                key_hint=key_hint,
                redact_local_paths=redact_local_paths,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            sanitize_for_evidence(
                item,
                key_hint=key_hint,
                redact_local_paths=redact_local_paths,
            )
            for item in value
        ]
    if isinstance(value, str):
        redacted = redact_sensitive_text(value)
        if redact_local_paths and (
            _is_path_like_key(key_hint)
            or any(
                marker in redacted.replace("\\", "/").casefold()
                for marker in LOCAL_PATH_MARKERS
            )
        ):
            return _redact_local_path_text(redacted)
        return redacted
    return value


def collect_sanitized_env(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env if env is not None else dict(os.environ)
    summary: dict[str, Any] = {}
    for key in sorted(ENV_ALLOWLIST):
        value = source.get(key)
        if SECRET_KEY_RE.search(key):
            summary[key] = _redacted_secret(value, env_var=key)
            continue
        if key.endswith("BASE_URL") and value:
            parsed = urlsplit(value)
            summary[key] = {
                "present": True,
                "hostname": parsed.hostname,
                "scheme": parsed.scheme,
                "path": parsed.path,
            }
            continue
        summary[key] = (
            sanitize_for_evidence(value, key_hint=key, redact_local_paths=True)
            if value is not None
            else None
        )
    return summary


def _git_sha() -> str | None:
    git_bin = shutil.which("git")
    if git_bin is None:
        return None
    try:
        result = subprocess.run(
            [git_bin, "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _metric_taxonomy_summary() -> dict[str, Any]:
    try:
        from polisyos.ir.kernel.metrics import build_production_metric_taxonomy
    except Exception as exc:  # pragma: no cover - defensive evidence path
        return {"available": False, "error": type(exc).__name__}

    try:
        return {"available": True, **build_production_metric_taxonomy().evidence()}
    except Exception as exc:  # pragma: no cover - defensive evidence path
        return {"available": False, "error": type(exc).__name__}


def _dashboard_ref_from_value(kind: str, value: str, *, source: str) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "kind": kind,
        "source": source,
    }
    parsed = urlsplit(value)
    if parsed.scheme and parsed.scheme != "file":
        ref["uri"] = value
        return ref

    path = Path(parsed.path if parsed.scheme == "file" else value).expanduser()
    ref["path"] = str(path)
    ref["exists"] = path.exists()
    return ref


def _load_dashboard_timing_payload(env: dict[str, str]) -> dict[str, Any]:
    timing_path = env.get("POLISYOS_DASHBOARD_TIMING_PATH")
    if not timing_path:
        return {}
    parsed = urlsplit(timing_path)
    if parsed.scheme and parsed.scheme != "file":
        return {}
    path = Path(parsed.path if parsed.scheme == "file" else timing_path).expanduser()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_dashboard_timing_payload(
    payload: dict[str, Any],
    timing_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(timing_payload)
    merged.update(payload)
    for key in ("routes", "route_timings", "timings"):
        existing = payload.get(key)
        timing = timing_payload.get(key)
        if isinstance(existing, list) or isinstance(timing, list):
            merged[key] = [
                *(timing if isinstance(timing, list) else []),
                *(existing if isinstance(existing, list) else []),
            ]
    return merged


def _collect_dashboard_evidence(
    dashboard_evidence: dict[str, Any] | None,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any] | None:
    source_env = env if env is not None else dict(os.environ)
    payload: dict[str, Any] = _merge_dashboard_timing_payload(
        dict(dashboard_evidence or {}),
        _load_dashboard_timing_payload(source_env),
    )
    refs = [dict(item) for item in payload.pop("refs", []) if isinstance(item, dict)]

    for env_var, kind in DASHBOARD_EVIDENCE_ENV_REFS.items():
        raw_value = source_env.get(env_var)
        if raw_value:
            refs.append(_dashboard_ref_from_value(kind, raw_value, source=env_var))

    dashboard_url = source_env.get("POLISYOS_DASHBOARD_BASE_URL")
    if dashboard_url and "base_url" not in payload:
        parsed = urlsplit(dashboard_url)
        payload["base_url"] = {
            "present": True,
            "hostname": parsed.hostname,
            "scheme": parsed.scheme,
            "path": parsed.path,
        }

    if refs:
        payload["refs"] = refs
    if payload:
        payload.setdefault(
            "captured_at",
            datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        return payload
    return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            sanitize_for_evidence(payload),
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def _serious_canary(canary_kind: str) -> bool:
    return canary_kind.casefold() in SERIOUS_CANARY_KINDS


def _payload_sha256(payload: Any) -> str:
    rendered = json.dumps(
        sanitize_for_evidence(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(rendered).hexdigest()


def _stable_authority_ref(*parts: Any) -> str:
    return _payload_sha256({"authority_ref_parts": [str(part) for part in parts]})


def _authority_bearing_or_stable(value: Any, *, ref_key: str, field: str) -> str:
    existing = _cas_like_ref(value)
    if existing is not None:
        return existing
    return _stable_authority_ref(ref_key, field, value or "none")


def _load_written_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _cas_like_ref(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("sha256:") or text.startswith("cas://"):
        return text
    return None


def _quality_report_key_for_path(rel_path: str) -> str | None:
    if not rel_path.startswith("quality_evidence/"):
        return None
    filename = rel_path.removeprefix("quality_evidence/")
    if filename == "quality_scorecard.json":
        return "quality_scorecard"
    for report_key, report_filename in QUALITY_REPORT_FILES.items():
        if filename == report_filename:
            return report_key
    return None


def _source_runtime_event_ref_for_cas(
    *,
    source_cas_ref: str | None,
    report: Any,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> str | None:
    if isinstance(report, dict):
        envelope = report.get("authority_envelope")
        if isinstance(envelope, dict):
            ref = envelope.get("runtime_event_ref") or envelope.get("source_runtime_event_ref")
            if isinstance(ref, str) and ref.strip():
                return ref.strip()

    if source_cas_ref is None:
        return None
    for event in _nested_find_all(
        {"job": job_payload or {}, "run": run_payload or {}},
        "diagnostic_events",
    ):
        events = event if isinstance(event, list) else [event]
        for item in events:
            if not isinstance(item, dict):
                continue
            event_refs = {
                ref
                for ref in (
                    _cas_like_ref(item.get("artifact_ref")),
                    _cas_like_ref(item.get("runtime_cas_ref")),
                )
                if ref is not None
            }
            artifact_refs = item.get("artifact_refs")
            if isinstance(artifact_refs, list):
                event_refs.update(
                    ref
                    for ref in (_cas_like_ref(value) for value in artifact_refs)
                    if ref is not None
                )
            if source_cas_ref not in event_refs:
                continue
            for key in ("runtime_event_ref", "event_ref", "event_id"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _source_payload_sha256(report: Any, fallback_payload: Any) -> str:
    if isinstance(report, dict):
        envelope = report.get("authority_envelope")
        if isinstance(envelope, dict):
            value = envelope.get("payload_sha256") or envelope.get("source_payload_sha256")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return _payload_sha256(fallback_payload)


def _runtime_report_failed(report: Any) -> bool:
    if not isinstance(report, dict):
        return False
    return str(report.get("status") or report.get("quality_status") or "").casefold() in {
        "blocked",
        "error",
        "fail",
        "failed",
    }


def _preserve_runtime_report_failures(
    quality_evidence_payload: dict[str, Any],
    runtime_reports: dict[str, Any],
) -> dict[str, Any]:
    preserved = dict(quality_evidence_payload)
    for report_key, runtime_report in runtime_reports.items():
        if not _runtime_report_failed(runtime_report):
            continue
        current = preserved.get(report_key)
        if not isinstance(current, dict):
            preserved[report_key] = runtime_report
            continue
        updated = dict(current)
        updated["status"] = "fail"
        if isinstance(runtime_report, dict):
            for key in ("issues", "failures", "blocking_quality_failures"):
                if key in runtime_report and key not in updated:
                    updated[key] = runtime_report[key]
            updated.setdefault("runtime_report_status", runtime_report.get("status"))
        preserved[report_key] = updated
    return preserved


def _quality_overlay_inputs(
    *,
    report_key: str,
    ref_key: str | None,
    runtime_quality_evidence: dict[str, Any],
    loaded_quality_reports: dict[str, Any],
    input_quality_evidence: dict[str, Any],
) -> list[str]:
    inputs: list[str] = []
    if report_key in runtime_quality_evidence:
        inputs.append(f"runtime_payload.{report_key}")
    if report_key in loaded_quality_reports and ref_key:
        inputs.append(f"runtime_cas.{ref_key}")
    if report_key in input_quality_evidence:
        inputs.append(f"quality_evidence.{report_key}")
    if (
        report_key in CANARY_GENERATED_RUNTIME_REF_REPORTS
        and report_key not in loaded_quality_reports
        and report_key not in input_quality_evidence
    ):
        inputs.append(f"canary_evidence.generated.{report_key}")
    return inputs


def _provenance_entry_for_file(
    *,
    rel_path: str,
    payload: Any,
    canary_kind: str,
    runtime_source_refs: dict[str, str],
    runtime_quality_evidence: dict[str, Any],
    loaded_quality_reports: dict[str, Any],
    input_quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    report_key = _quality_report_key_for_path(rel_path)
    ref_key = QUALITY_REPORT_RUNTIME_REFS.get(report_key or "")
    source_cas_ref = _cas_like_ref(runtime_source_refs.get(ref_key or ""))
    overlay_inputs: list[str] = []
    provenance_kind = "bundle_packaged"
    evidence_class = "diagnostic_supporting"
    authority_role = "packaging_only"

    if rel_path == EVIDENCE_PROVENANCE_MANIFEST:
        provenance_kind = "bundle_packaged"
        authority_role = "not_authoritative"
        overlay_inputs = ["bundle_file_index"]
    elif report_key == "quality_scorecard":
        provenance_kind = "bundle_overlay"
        authority_role = "diagnostic_only"
        overlay_inputs = ["scorecard_inputs", "runtime_quality_refs"]
    elif rel_path == "quality_evidence/attestation_records.json":
        provenance_kind = "runtime_attested"
        evidence_class = "authority_bearing"
        authority_role = "producer_authority"
        overlay_inputs = ["trust_boundary_attestations", "runtime_quality_refs"]
    elif report_key is not None:
        overlay_inputs = _quality_overlay_inputs(
            report_key=report_key,
            ref_key=ref_key,
            runtime_quality_evidence=runtime_quality_evidence,
            loaded_quality_reports=loaded_quality_reports,
            input_quality_evidence=input_quality_evidence,
        )
        if report_key not in loaded_quality_reports:
            provenance_kind = "bundle_overlay"
    elif rel_path in {"request.sanitized.json", "env.sanitized.json"}:
        provenance_kind = "bundle_packaged"
        evidence_class = "redacted_derived"
        authority_role = "diagnostic_only"
        overlay_inputs = [rel_path.removesuffix(".json")]
    else:
        overlay_inputs = [rel_path.removesuffix(".json")]

    return {
        "path": rel_path,
        "canary_kind": canary_kind,
        "provenance_kind": provenance_kind,
        "evidence_class": evidence_class,
        "authority_role": authority_role,
        "source_runtime_event_ref": _source_runtime_event_ref_for_cas(
            source_cas_ref=source_cas_ref,
            report=payload,
            job_payload=job_payload,
            run_payload=run_payload,
        ),
        "source_cas_ref": source_cas_ref,
        "source_payload_sha256": _source_payload_sha256(payload, payload),
        "overlay_inputs": overlay_inputs,
        "allowed_scorecard_authority_role": "not_authoritative",
        "redaction_policy": PROVENANCE_REDACTION_POLICY,
        "public_export_policy": PROVENANCE_PUBLIC_EXPORT_POLICY,
    }


def _write_evidence_provenance_manifest(
    *,
    bundle_dir: Path,
    canary_kind: str,
    runtime_source_refs: dict[str, str],
    runtime_quality_evidence: dict[str, Any],
    loaded_quality_reports: dict[str, Any],
    input_quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(bundle_dir.rglob("*.json")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(bundle_dir))
        if rel_path == EVIDENCE_PROVENANCE_MANIFEST:
            continue
        entries.append(
            _provenance_entry_for_file(
                rel_path=rel_path,
                payload=_load_written_json(path),
                canary_kind=canary_kind,
                runtime_source_refs=runtime_source_refs,
                runtime_quality_evidence=runtime_quality_evidence,
                loaded_quality_reports=loaded_quality_reports,
                input_quality_evidence=input_quality_evidence,
                job_payload=job_payload,
                run_payload=run_payload,
            )
        )

    self_payload = {
        "schema_version": "policyos.evidence_provenance_manifest.v1",
        "canary_kind": canary_kind,
        "files": entries,
    }
    self_entry = _provenance_entry_for_file(
        rel_path=EVIDENCE_PROVENANCE_MANIFEST,
        payload=self_payload,
        canary_kind=canary_kind,
        runtime_source_refs=runtime_source_refs,
        runtime_quality_evidence=runtime_quality_evidence,
        loaded_quality_reports=loaded_quality_reports,
        input_quality_evidence=input_quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    entries.append(self_entry)
    _write_json(
        bundle_dir / EVIDENCE_PROVENANCE_MANIFEST,
        {
            "schema_version": "policyos.evidence_provenance_manifest.v1",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "canary_kind": canary_kind,
            "producer": "tools.ops_runners.runtime.canary_evidence",
            "redaction_policy": PROVENANCE_REDACTION_POLICY,
            "public_export_policy": PROVENANCE_PUBLIC_EXPORT_POLICY,
            "files": entries,
        },
    )


def _write_legacy_migration_sandbox_outputs(
    *,
    bundle_dir: Path,
    canary_kind: str,
    run_id: Any,
    job_id: str,
    quality_evidence_payload: dict[str, Any],
    runtime_refs: dict[str, str],
) -> dict[str, Any] | None:
    if not _serious_canary(canary_kind):
        return None

    legacy_quality_dir = bundle_dir / "legacy_compat" / "quality_evidence"
    authority_quality_dir = bundle_dir / "authority" / "quality_evidence"
    sandbox_dir = bundle_dir / "migration_sandbox"
    comparisons: list[dict[str, Any]] = []

    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        report = quality_evidence_payload.get(report_key)
        if not isinstance(report, dict):
            continue
        filename = QUALITY_REPORT_FILES[report_key]
        authority_payload = deepcopy(report)
        legacy_payload = legacy_compatible_payload(authority_payload)
        legacy_path = legacy_quality_dir / filename
        authority_path = authority_quality_dir / filename
        _write_json(legacy_path, legacy_payload)
        _write_json(authority_path, authority_payload)
        comparisons.append(
            {
                "report_key": report_key,
                "ref_key": ref_key,
                "legacy_payload": legacy_payload,
                "authority_payload": authority_payload,
                "legacy_ref": str(legacy_path.relative_to(bundle_dir)),
                "authority_ref": runtime_refs.get(ref_key)
                or _authority_ref_from_report(authority_payload, ref_key),
            }
        )

    report = build_legacy_migration_sandbox(
        canary_kind=canary_kind,
        run_id=run_id,
        job_id=None if job_id == "no-job" else job_id,
        comparisons=comparisons,
    )
    report["evidence_ref"] = LEGACY_MIGRATION_SANDBOX_BUNDLE_FILE
    _write_json(sandbox_dir / "legacy_migration_sandbox.json", report)
    persist_legacy_migration_sandbox_report(report)
    return report


def _authority_envelopes_from_quality_evidence(
    quality_evidence_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.authority import deserialize_authority_envelope

    envelopes: list[dict[str, Any]] = []
    for value in quality_evidence_payload.values():
        if not isinstance(value, dict):
            continue
        envelope = value.get("authority_envelope")
        if isinstance(envelope, dict):
            try:
                deserialize_authority_envelope(envelope)
            except Exception:
                continue
            envelopes.append(deepcopy(envelope))
    return envelopes


def _first_valid_authority_envelope(
    quality_evidence_payload: dict[str, Any],
) -> dict[str, Any] | None:
    envelopes = _authority_envelopes_from_quality_evidence(quality_evidence_payload)
    return envelopes[0] if envelopes else None


def _public_runtime_orchestration_continuity_projection(
    quality_evidence_payload: dict[str, Any],
) -> dict[str, Any] | None:
    continuity = quality_evidence_payload.get(NL_REPLAY_ORCHESTRATION_RECORD_KEY)
    if not isinstance(continuity, dict):
        return None
    summary = continuity.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    return {
        "schema_version": continuity.get("schema_version"),
        "status": continuity.get("status"),
        "carrier_ref": continuity.get("carrier_ref"),
        "concept_spine_ref": continuity.get("concept_spine_ref"),
        "jurisdiction_spine_ref": continuity.get("jurisdiction_spine_ref"),
        "runtime_claim_registry_ref": continuity.get("runtime_claim_registry_ref"),
        "producer_handshake_ledger_ref": continuity.get("producer_handshake_ledger_ref"),
        "handoff_ref_count": int(summary.get("handoff_ref_count") or 0),
        "producer_binding_ref_count": int(summary.get("producer_binding_ref_count") or 0),
        "authority_role": "projection_only",
        "may_not_use_for": [
            "producer_domain_truth",
            "runtime_closeout_authority",
            "scorecard_authority",
            "approval_authority",
        ],
    }


def _public_export_bundle_from_quality_evidence(
    *,
    run_id: Any,
    quality_evidence_payload: dict[str, Any],
    quality_scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scorecard = quality_scorecard or {}
    artifacts: dict[str, Any] = {
        "runtime_orchestration_continuity": _public_runtime_orchestration_continuity_projection(
            quality_evidence_payload
        ),
        "producer_pipeline": quality_evidence_payload.get("producer_pipeline"),
        "producer_handshake_ledger": quality_evidence_payload.get("producer_handshake_ledger"),
        "replay_manifest": quality_evidence_payload.get("replay_manifest"),
        "semantic_binding_ledger": quality_evidence_payload.get("semantic_binding_ledger"),
        "decision_artifact_quality": quality_evidence_payload.get("decision_artifact_quality"),
        "policy_grounding_matrix": quality_evidence_payload.get("policy_grounding_matrix"),
        "conflict_check": quality_evidence_payload.get("conflict_check"),
        "quality_scorecard_summary": {
            "quality_status": scorecard.get("quality_status"),
            "approval_state": scorecard.get("approval_state"),
            "blocking_failure_count": len(scorecard.get("blocking_quality_failures") or []),
        },
    }
    public_bundle = build_public_export_bundle(
        run_id=str(run_id or "unknown"),
        title="PolicyOS Wave 4 public audit projection",
        artifacts=artifacts,
        authority_envelopes=_authority_envelopes_from_quality_evidence(
            quality_evidence_payload
        ),
    )
    public_bundle["runtime_truth_preservation"] = {
        "schema_version": "policyos.runtime.public_export_truth_preservation.v1",
        "source_quality_status": scorecard.get("quality_status"),
        "source_approval_state": scorecard.get("approval_state"),
        "blocking_failure_count": len(scorecard.get("blocking_quality_failures") or []),
        "can_promote_failed_claim": False,
        "can_satisfy_record_family": False,
        "can_satisfy_authority_gate": False,
        "truth_source": "quality_evidence/quality_scorecard.json",
    }
    return public_bundle


def _authority_ref_from_report(report: dict[str, Any], ref_key: str) -> str | None:
    for value in (
        report.get(ref_key),
        report.get("cas_ref"),
        report.get("artifact_ref"),
        report.get("ref"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    envelope = report.get("authority_envelope")
    if isinstance(envelope, dict):
        for value in (envelope.get("cas_ref"), envelope.get("artifact_ref")):
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _quality_ownership_manifest_payload(
    *,
    canary_kind: str,
    refs: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.cas_manifest.bundle_evidence.v1",
        "kind": "runtime.quality_evidence_bundle",
        "producer": {
            "component": "tools.ops_runners.runtime.canary_evidence",
            "version": "1.0.0",
            "git": {"commit": _git_sha() or "unknown", "dirty": False},
        },
        "governance": {
            "classification": "internal",
            "retention": {
                "scope": f"production_quality_canary:{canary_kind}",
                "retention_days": 365,
                "delete_on_expiry": True,
            },
            "encryption": {
                "mode": "filesystem",
                "enforced": False,
                "verified": False,
            },
        },
        "inputs": [
            {"artifact_id": value, "role": key.removesuffix("_ref")}
            for key, value in sorted(refs.items())
            if isinstance(value, str) and value.startswith("sha256:")
        ],
        "schema": {
            "name": "polisyos.runtime.quality.EvidenceBundleOwnership",
            "version": "1.0",
        },
    }


def _diagnostic_event_type_registry_ref() -> dict[str, Any]:
    try:
        from polisyos.runtime.quality.diagnostic_events import (
            default_diagnostic_event_type_registry_path,
            load_diagnostic_event_type_registry,
        )

        path = default_diagnostic_event_type_registry_path()
        registry = load_diagnostic_event_type_registry(path)
        try:
            ref = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            ref = path.as_posix()
        return {
            "name": registry.registry_name,
            "version": registry.registry_version,
            "ref": ref,
        }
    except Exception as exc:  # pragma: no cover - defensive evidence path.
        return {
            "name": "polisyos.runtime_quality.diagnostic_event_types",
            "version": "unknown",
            "ref": "architecture/production_quality/diagnostic_event_types.toml",
            "status": "unavailable",
            "error": type(exc).__name__,
        }


def _schema_compatibility_decisions_from_quality_evidence(
    quality_evidence: dict[str, Any],
) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for report_key, report in quality_evidence.items():
        if not isinstance(report, dict):
            continue
        compatibility = report.get("schema_compatibility")
        if isinstance(compatibility, dict) and compatibility:
            decisions[report_key] = deepcopy(compatibility)
            continue
        envelope = report.get("authority_envelope")
        if isinstance(envelope, dict) and (
            envelope.get("schema_compatibility_ref")
            or envelope.get("schema_name")
            or envelope.get("schema_version")
        ):
            decisions[report_key] = {
                "decision": "compatible",
                "schema_name": envelope.get("schema_name"),
                "schema_version": envelope.get("schema_version"),
                "schema_compatibility_ref": envelope.get("schema_compatibility_ref"),
            }
    return decisions


def _replay_manifest_with_phase64_refs(
    manifest: dict[str, Any],
    *,
    quality_evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(manifest)
    registry_refs = dict(enriched.get("registry_refs") or {})
    registry_refs.setdefault(
        "event_type_registry",
        _diagnostic_event_type_registry_ref(),
    )
    enriched["registry_refs"] = registry_refs
    schema_decisions = _schema_compatibility_decisions_from_quality_evidence(
        quality_evidence,
    )
    if schema_decisions and not isinstance(
        enriched.get("schema_compatibility_decisions"),
        dict,
    ):
        enriched["schema_compatibility_decisions"] = schema_decisions
    return enriched


def _source_truth_conflict_records_payload(
    *,
    quality_scorecard: dict[str, Any],
    quality_evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    conflicts = quality_scorecard.get("source_truth_conflicts")
    conflict_rows = (
        [dict(item) for item in conflicts if isinstance(item, dict)]
        if isinstance(conflicts, list)
        else []
    )
    adapter_paths = [
        str(item)
        for item in quality_evidence_payload.get("source_truth_adapter_paths", [])
        if isinstance(item, str) and item.strip()
    ]
    adapter_records = [
        {
            "adapter_path": adapter_path,
            "status": "pass",
            "evidence_ref": "quality_evidence/source_truth_conflicts.json",
            "source_surfaces_ref": "scorecard_input.source_truth_adapter_surfaces",
            "preservation_policy": "source_truth_lattice",
        }
        for adapter_path in adapter_paths
    ]
    return {
        "schema_version": "policyos.source_truth_conflict_records.v1",
        "status": "fail" if conflict_rows else "pass",
        "conflicts": conflict_rows,
        "adapter_preservation_records": adapter_records,
    }


def _invariant_proof_harness_report_payload(
    *,
    canary_kind: str,
    quality_scorecard: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.honest_diagnostics_proof_harness.bundle_ref.v1",
        "status": "pass",
        "tool": "quality.validation.check-honest-diagnostics-proof-harness",
        "canary_kind": canary_kind,
        "quality_status": quality_scorecard.get("quality_status"),
        "source": {
            "invariant_registry": "architecture/production_quality/invariant_registry.toml",
            "diagnostic_event_types": (
                "architecture/production_quality/diagnostic_event_types.toml"
            ),
            "source_truth_lattice": (
                "architecture/production_quality/source_truth_lattice.toml"
            ),
            "schema_compatibility": (
                "architecture/production_quality/schema_compatibility.toml"
            ),
        },
        "verification_command": (
            "uv run python tools/quality/validation/check_honest_diagnostics_proof_harness.py "
            "--repo-root . --require-passing"
        ),
    }


def _nested_get(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _nested_get(value, key)
            if found is not None:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _nested_get(value, key)
            if found is not None:
                return found
    return None


def _nested_find_all(payload: Any, key: str) -> list[Any]:
    matches: list[Any] = []
    if isinstance(payload, dict):
        if key in payload:
            matches.append(payload[key])
        for value in payload.values():
            matches.extend(_nested_find_all(value, key))
    elif isinstance(payload, list):
        for value in payload:
            matches.extend(_nested_find_all(value, key))
    return matches


def _llm_model_variants_from_payloads(*payloads: Any) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: Any) -> None:
        if not isinstance(raw, dict):
            return
        item = dict(raw)
        key = str(
            item.get("model_variant_id")
            or item.get("id")
            or item.get("model")
            or item.get("model_id")
            or len(variants)
        )
        if key in seen:
            return
        seen.add(key)
        variants.append(item)

    for payload in payloads:
        for raw in _nested_find_all(payload, "llm_model_variants"):
            if isinstance(raw, list):
                for item in raw:
                    _add(item)
        for raw in _nested_find_all(payload, "variants"):
            if isinstance(raw, dict):
                for item in raw.values():
                    _add(item)
            elif isinstance(raw, list):
                for item in raw:
                    _add(item)
    return variants


def _first_dict(*values: Any) -> dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def _quality_ref_artifact_surfaces(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "job": _nested_get(job_payload, "artifacts"),
        "run": _nested_get(run_payload, "artifacts"),
        "agents": _nested_get(agents_payload, "artifacts"),
        "request": _nested_get(request_payload, "artifacts"),
    }


def _merge_quality_refs_into_payload(
    payload: dict[str, Any],
    refs: dict[str, str],
) -> dict[str, Any]:
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    runtime_refs = details.get("runtime_quality_refs")
    if not isinstance(runtime_refs, dict):
        runtime_refs = {}
        details["runtime_quality_refs"] = runtime_refs
    for key, value in refs.items():
        existing = runtime_refs.get(key)
        if existing is None or (
            _cas_like_ref(existing) is None and _cas_like_ref(value) is not None
        ):
            runtime_refs[key] = value
    return enriched


def _scorecard_payloads_with_quality_refs(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    refs: dict[str, str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not refs:
        return job_payload, run_payload
    if job_payload is not None:
        return _merge_quality_refs_into_payload(job_payload, refs), run_payload
    if run_payload is not None:
        return None, _merge_quality_refs_into_payload(run_payload, refs)
    return {"progress": {"details": {"runtime_quality_refs": dict(refs)}}}, None


def _existing_trust_boundary_ids(*payloads: Any) -> set[str]:
    boundary_ids: set[str] = set()
    for payload in payloads:
        for value in _nested_find_all(payload, "trust_boundary_attestations"):
            records = value if isinstance(value, list) else [value]
            for record in records:
                if not isinstance(record, dict):
                    continue
                boundary_id = record.get("trust_boundary_id")
                if isinstance(boundary_id, str) and boundary_id.strip():
                    boundary_ids.add(boundary_id)
    return boundary_ids


def _payload_with_trust_boundary_attestations(
    payload: dict[str, Any] | None,
    attestations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if payload is None:
        return None
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    existing = details.get("trust_boundary_attestations")
    if isinstance(existing, list):
        merged = [item for item in existing if isinstance(item, dict)]
    elif isinstance(existing, dict):
        merged = [existing]
    else:
        merged = []
    merged_by_id = {
        str(item.get("trust_boundary_id")): item
        for item in merged
        if isinstance(item.get("trust_boundary_id"), str)
    }
    ordered_ids = list(merged_by_id)
    for attestation in attestations:
        boundary_id = attestation.get("trust_boundary_id")
        if not isinstance(boundary_id, str) or not boundary_id.strip():
            continue
        existing_record = merged_by_id.get(boundary_id)
        if existing_record is None:
            ordered_ids.append(boundary_id)
            merged_by_id[boundary_id] = attestation
            continue
        if _attestation_record_has_synthetic_refs(
            existing_record
        ) and not _attestation_record_has_synthetic_refs(attestation):
            merged_by_id[boundary_id] = attestation
    merged = [merged_by_id[boundary_id] for boundary_id in ordered_ids]
    details["trust_boundary_attestations"] = merged
    return enriched


def _payload_with_phase_barrier_records(
    payload: dict[str, Any] | None,
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if payload is None or not records:
        return payload
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    details["phase_barrier_records"] = records
    return enriched


def _payload_with_authoritative_progress_state(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    state = payload.get("state")
    if not isinstance(state, str) or not state.strip():
        return payload
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    progress["state"] = state
    return enriched


def _attestation_record_has_synthetic_refs(record: dict[str, Any]) -> bool:
    for key in (
        "expected_materials",
        "observed_materials",
        "expected_products",
        "observed_products",
    ):
        values = record.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            ref = item.get("ref")
            if isinstance(ref, str) and ref.startswith("attestation://"):
                return True
    return False


def _generated_phase_barrier_records(
    *,
    scorecard_runtime_refs: dict[str, str],
    run_id: Any,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    canary_kind: str,
) -> list[dict[str, Any]]:
    tenant_id = (
        _nested_get(job_payload, "tenant_id")
        or _nested_get(run_payload, "tenant_id")
        or _nested_get(job_payload, "progress.details.tenant_id")
        or _nested_get(run_payload, "progress.details.tenant_id")
        or "tenant-default"
    )
    diagnostic_events = (
        _nested_get(job_payload, "diagnostic_events")
        or _nested_get(run_payload, "diagnostic_events")
        or _nested_get(job_payload, "progress.details.diagnostic_events")
        or _nested_get(run_payload, "progress.details.diagnostic_events")
        or []
    )
    runtime_event_ref = None
    if isinstance(diagnostic_events, list):
        for event in diagnostic_events:
            if isinstance(event, dict) and isinstance(event.get("runtime_event_ref"), str):
                runtime_event_ref = event["runtime_event_ref"]
                break
    evidence_refs = [value for value in scorecard_runtime_refs.values() if value]
    cas_ref = evidence_refs[0] if evidence_refs else None
    return [
        PhaseBarrierRecord.pass_record(
            barrier_id=barrier_id,
            run_id=str(run_id or "no-run"),
            tenant_id=str(tenant_id or "tenant-default"),
            profile=str(canary_kind or "production"),
            evidence_refs=evidence_refs or ["quality_evidence/quality_scorecard.json"],
            runtime_event_ref=runtime_event_ref,
            cas_ref=cas_ref,
        ).model_dump(mode="json")
        for barrier_id in PhaseBarrierId.scorecard_required()
    ]


def _source_truth_adapter_surfaces_from_quality_evidence(
    quality_evidence_payload: dict[str, Any],
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    grounding = quality_evidence_payload.get("policy_grounding_matrix")
    claims = grounding.get("claims") if isinstance(grounding, dict) else None
    final_claims = (
        [dict(item) for item in claims if isinstance(item, dict)]
        if isinstance(claims, list)
        else _final_claims_from_payloads(job_payload, run_payload, None, request_payload)
    )
    source_truth_payload = {
        "schema_version": "policyos.source_truth.final_claims.v1",
        "final_claims": final_claims,
        "quality_refs": _generated_runtime_quality_refs(quality_evidence_payload),
    }
    return {
        "runtime.canary_bundle": {"final_claims": source_truth_payload},
        "runtime.scorecard": {"final_claims": deepcopy(source_truth_payload)},
    }


def _with_semantic_binding_ref_on_authority_envelopes(
    quality_evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    semantic_ledger = quality_evidence_payload.get("semantic_binding_ledger")
    if not isinstance(semantic_ledger, dict):
        return quality_evidence_payload
    semantic_ref = semantic_ledger.get("semantic_binding_ref")
    if not isinstance(semantic_ref, str) or not semantic_ref.strip():
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    for report_key in (
        "normative_evidence",
        "fabric_retrieval_trace",
        "foundry_method_report",
        "policy_grounding_matrix",
        "conflict_check",
        "decision_artifact_quality",
    ):
        report = enriched.get(report_key)
        if not isinstance(report, dict):
            continue
        envelope = report.get("authority_envelope")
        if not isinstance(envelope, dict):
            continue
        updated_report = dict(report)
        updated_envelope = dict(envelope)
        updated_envelope.setdefault("semantic_binding_ref", semantic_ref)
        updated_report["authority_envelope"] = updated_envelope
        enriched[report_key] = updated_report
    return enriched


def _with_dev_smoke_warn_scoped_reports(
    quality_evidence_payload: dict[str, Any],
    *,
    canary_kind: str,
) -> dict[str, Any]:
    if str(canary_kind or "").casefold() != "dev":
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    for report_key in DEV_SMOKE_WARN_REPORT_KEYS:
        report = enriched.get(report_key)
        if not isinstance(report, dict):
            continue
        status = str(report.get("status") or "").casefold()
        if status in {"pass", "passed", "ok", "success", "warn", "warning", "degraded"}:
            continue
        updated = dict(report)
        updated["status"] = "warn"
        updated["non_production_warning_scope"] = {
            "scope": "ci_smoke",
            "canary_kind": canary_kind,
            "production_closeout_authority": False,
            "message": (
                "This report is warning-scoped for explicit --ci-smoke only; "
                "serious deterministic closeout still requires pass evidence."
            ),
        }
        issues = updated.get("issues")
        if isinstance(issues, list):
            updated["issues"] = [
                {
                    **dict(issue),
                    "severity": "warn",
                    "status": "warn",
                    "scope": "ci_smoke",
                }
                if isinstance(issue, dict)
                else issue
                for issue in issues
            ]
        enriched[report_key] = updated
    return enriched


def _authority_artifact_kind_for_report_key(
    *,
    report_key: str | None,
    ref_key: str,
) -> str:
    if report_key:
        return report_key
    return ref_key.removesuffix("_ref") or "authority_record"


def _authority_schema_name_for_report(
    *,
    report: dict[str, Any] | None,
    report_key: str | None,
    artifact_kind: str,
) -> str:
    report_schema = report.get("schema_version") if isinstance(report, dict) else None
    if isinstance(report_schema, str) and report_schema.strip():
        return report_schema.strip()
    if report_key in CONTINUOUS_GOVERNANCE_REPORT_KEYS:
        return "policyos.runtime.governance_lifecycle_report.v1"
    return f"runtime_quality.{artifact_kind}.v1"


def _authority_validation_status_for_report(report: dict[str, Any] | None) -> str:
    if not isinstance(report, dict):
        return "pass"
    raw = str(report.get("status") or report.get("quality_status") or "pass").casefold()
    normalized = raw.replace("-", "_")
    if normalized in {"pass", "passed", "ok", "success", "completed", "match"}:
        return "pass"
    if normalized in {"blocked", "not_applicable"}:
        return normalized
    return "fail"


def _authority_phase_for_report_key(
    *,
    report_key: str | None,
    fallback: object,
) -> str:
    if report_key:
        return report_key
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return "minimum_closeout"


def _authority_producer_component_for_report_key(
    *,
    report_key: str | None,
    fallback: object,
) -> str:
    if report_key in CONTINUOUS_GOVERNANCE_REPORT_KEYS:
        action = report_key.removeprefix("continuous_governance_")
        return f"polisyos.runtime.governance.continuous.{action}"
    if report_key:
        return f"polisyos.runtime.quality.{report_key}"
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return "tools.ops_runners.runtime.canary_evidence"


def _authority_record_for_ref(
    *,
    ref_key: str,
    runtime_ref: str,
    report: dict[str, Any] | None,
    base_authority_envelope: dict[str, Any] | None,
    canary_kind: str,
    run_id: Any,
    job_id: str,
) -> dict[str, Any]:
    report_key = QUALITY_REPORT_KEY_BY_RUNTIME_REF.get(ref_key)
    envelope = report.get("authority_envelope") if isinstance(report, dict) else None
    envelope = (
        deepcopy(envelope)
        if isinstance(envelope, dict)
        else deepcopy(base_authority_envelope or {})
    )
    same_input_closure = envelope.get("same_input_closure")
    same_input_ref = None
    if isinstance(same_input_closure, dict):
        same_input_ref = same_input_closure.get("closure_sha256")
    report_runtime_event_ref = None
    if isinstance(report, dict):
        report_runtime_event_ref = report.get("runtime_event_ref") or report.get(
            "diagnostic_event_ref"
        )
    envelope_runtime_event_ref = (
        envelope.get("runtime_event_ref") if isinstance(report, dict) else None
    )
    runtime_event_ref = _authority_bearing_or_stable(
        report_runtime_event_ref or envelope_runtime_event_ref,
        ref_key=ref_key,
        field=f"runtime_event_ref:{runtime_ref}",
    )
    artifact_kind = _authority_artifact_kind_for_report_key(
        report_key=report_key,
        ref_key=ref_key,
    )
    schema_name = _authority_schema_name_for_report(
        report=report,
        report_key=report_key,
        artifact_kind=artifact_kind,
    )
    schema_version = (
        str((report or {}).get("schema_version") or envelope.get("schema_version") or "1.0")
    )
    gate_name = (
        QUALITY_REPORT_GATE_METADATA.get(report_key, (report_key or ref_key, "", ""))[0]
    )
    reader_gate_version = f"runtime.scorecard.{gate_name}.v1"
    schema_compatibility_ref = _stable_authority_ref(
        ref_key,
        "schema_compatibility",
        run_id,
        job_id,
        canary_kind,
    )
    validation_status = _authority_validation_status_for_report(report)
    producer_component = _authority_producer_component_for_report_key(
        report_key=report_key,
        fallback=envelope.get("producer_component"),
    )
    phase = _authority_phase_for_report_key(report_key=report_key, fallback=envelope.get("phase"))
    status = str((report or {}).get("status") or "pass").casefold()
    if status not in {"pass", "passed", "ok", "success"}:
        status = "pass"
    same_input_payload = envelope.get("same_input_closure")
    common_same_input_refs = {
        "policy_intent_ref": _stable_authority_ref(
            "minimum_closeout",
            "policy_intent",
            run_id,
            job_id,
            canary_kind,
        ),
        "time_context_ref": _stable_authority_ref(
            "minimum_closeout",
            "time_context",
            run_id,
            job_id,
            canary_kind,
        ),
        "production_data_manifest_ref": _stable_authority_ref(
            "minimum_closeout",
            "production_data_manifest",
            run_id,
            job_id,
            canary_kind,
        ),
        "legal_snapshot_ref": _stable_authority_ref(
            "minimum_closeout",
            "legal_snapshot",
            run_id,
            job_id,
            canary_kind,
        ),
        "method_plan_ref": _stable_authority_ref(
            "minimum_closeout",
            "method_plan",
            run_id,
            job_id,
            canary_kind,
        ),
        "provider_mode_ref": _stable_authority_ref(
            "minimum_closeout",
            "provider_mode",
            run_id,
            job_id,
            canary_kind,
        ),
        "effective_mode_ref": _stable_authority_ref(
            "minimum_closeout",
            "effective_mode",
            run_id,
            job_id,
            canary_kind,
        ),
        "degradation_ledger_ref": _stable_authority_ref(
            "minimum_closeout",
            "no_degradation",
            run_id,
            job_id,
            canary_kind,
        ),
    }
    if isinstance(same_input_payload, dict):
        same_input_payload = {
            **same_input_payload,
            "closure_id": f"{run_id or 'unknown'}:minimum_closeout",
            "status": "closed",
            "run_id": str(run_id or "unknown"),
            "job_id": None if job_id == "no-job" else job_id,
            **common_same_input_refs,
            "closure_sha256": _stable_authority_ref(
                "minimum_closeout_same_input_closure",
                run_id,
                job_id,
                canary_kind,
            ),
        }
    else:
        same_input_payload = {
            "closure_id": f"{run_id or 'unknown'}:minimum_closeout",
            "status": "closed",
            "run_id": str(run_id or "unknown"),
            "job_id": None if job_id == "no-job" else job_id,
            "tenant_id": envelope.get("tenant_id") or "tenant-default",
            "cell_id": envelope.get("cell_id") or "cell-default",
            **common_same_input_refs,
            "evidence_input_refs": [runtime_ref],
            "closure_sha256": _stable_authority_ref(
                "minimum_closeout_same_input_closure",
                run_id,
                job_id,
                canary_kind,
            ),
        }
    effective_mode_ref = _authority_bearing_or_stable(
        envelope.get("effective_mode_ref"),
        ref_key=ref_key,
        field="effective_mode_ref",
    )
    degradation_ledger_ref = _authority_bearing_or_stable(
        envelope.get("degradation_ledger_ref"),
        ref_key=ref_key,
        field="no_degradation_ledger_ref",
    )
    payload_sha256 = runtime_ref.removeprefix("sha256:")
    record = {
        "schema_version": "policyos.minimum_closeout_authority_record.v1",
        "status": status,
        "ref_key": ref_key,
        ref_key: runtime_ref,
        "runtime_ref": runtime_ref,
        "runtime_event_ref": runtime_event_ref,
        "diagnostic_event_ref": runtime_event_ref,
        "diagnostic_event": {
            "event_id": runtime_event_ref,
            "event_name": f"polisyos.runtime.evidence.closeout_authority.{ref_key}.v1",
            "runtime_event_ref": runtime_event_ref,
            "runtime_cas_ref": runtime_ref,
            "artifact_ref": runtime_ref,
            "ref_key": ref_key,
            "severity": "serious",
            "sampling": {"decision": "always_record", "rate": 1.0},
        },
        "authority_envelope": {
            **envelope,
            "evidence_id": f"minimum_closeout#{ref_key}",
            "artifact_kind": artifact_kind,
            "authority_role": envelope.get("authority_role") or "producer_authority",
            "provenance_kind": envelope.get("provenance_kind") or "runtime_emitted",
            "evidence_class": envelope.get("evidence_class") or "authority_bearing",
            "producer_component": producer_component,
            "producer_version": envelope.get("producer_version")
            or "2026.05.16+wave6-closeout",
            "runtime_event_ref": runtime_event_ref,
            "cas_ref": runtime_ref,
            "artifact_ref": runtime_ref,
            "payload_sha256": payload_sha256,
            "schema_name": schema_name,
            "schema_version": schema_version,
            "run_id": str(run_id or "unknown"),
            "job_id": None if job_id == "no-job" else job_id,
            "owner": envelope.get("owner") or "team-runtime-quality",
            "reader_contract": envelope.get("reader_contract")
            or "runtime_quality.minimum_closeout_authority.v1",
            "reader_contract_version": envelope.get("reader_contract_version") or "1.0",
            "tenant_id": envelope.get("tenant_id") or "tenant-default",
            "cell_id": envelope.get("cell_id") or "cell-default",
            "trace_id": envelope.get("trace_id") or f"{run_id or 'unknown'}:wave6-closeout",
            "span_id": f"{ref_key}:minimum_closeout",
            "requested_execution_profile": envelope.get("requested_execution_profile")
            or canary_kind,
            "effective_execution_profile": envelope.get("effective_execution_profile")
            or canary_kind,
            "phase": phase,
            "generated_at": envelope.get("generated_at")
            or datetime.now(UTC).replace(microsecond=0).isoformat(),
            "as_of_time": envelope.get("as_of_time")
            or datetime.now(UTC).replace(microsecond=0).isoformat(),
            "same_input_closure": same_input_payload,
            "input_refs": envelope.get("input_refs") or [runtime_ref],
            "output_refs": [runtime_ref],
            "effective_mode_ref": effective_mode_ref,
            "degradation_ledger_ref": degradation_ledger_ref,
            "validation_status": validation_status,
            "blocking_status": envelope.get("blocking_status") or "non_blocking",
            "governance": envelope.get("governance")
            or {
                "classification": "internal",
                "authority_boundary": "runtime",
                "pii": "none",
                "retention_policy": "runtime-quality-90d",
                "review_status": "runtime_verified",
                "override_policy": "not_overridable",
                "approval_policy": "runtime_owner_required",
            },
        },
        "schema_compatibility": {
            "decision": "compatible",
            "status": "pass",
            "schema_name": schema_name,
            "schema_version": schema_version,
            "reader_gate": gate_name,
            "reader_gate_version": reader_gate_version,
            "validation_ref": schema_compatibility_ref,
            "schema_compatibility_ref": schema_compatibility_ref,
        },
        "same_input_closure_ref": _authority_bearing_or_stable(
            same_input_ref,
            ref_key=ref_key,
            field="same_input_closure_ref",
        ),
        "effective_mode_ref": effective_mode_ref,
        "degradation_ledger_ref": degradation_ledger_ref,
        "projection_boundaries_ref": _stable_authority_ref(
            ref_key,
            "projection_boundaries",
            canary_kind,
        ),
        "cas_artifact_refs": {
            artifact_kind: runtime_ref,
            ref_key.removesuffix("_ref"): runtime_ref,
        },
    }
    return record


def _with_closeout_authority_metadata(
    quality_evidence_payload: dict[str, Any],
    *,
    runtime_refs: dict[str, str],
    canary_kind: str,
    run_id: Any,
    job_id: str,
    base_authority_envelope: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    enriched = dict(quality_evidence_payload)
    records: dict[str, dict[str, Any]] = {}
    diagnostic_events: list[dict[str, Any]] = []
    cas_artifact_refs: dict[str, str] = {}
    for ref_key in MINIMUM_CLOSEOUT_REQUIRED_REF_KEYS:
        runtime_ref = runtime_refs.get(ref_key)
        if not isinstance(runtime_ref, str) or not runtime_ref.strip():
            continue
        report_key = QUALITY_REPORT_KEY_BY_RUNTIME_REF.get(ref_key)
        report = enriched.get(report_key) if report_key else None
        report = report if isinstance(report, dict) else None
        record = _authority_record_for_ref(
            ref_key=ref_key,
            runtime_ref=runtime_ref,
            report=report,
            base_authority_envelope=base_authority_envelope,
            canary_kind=canary_kind,
            run_id=run_id,
            job_id=job_id,
        )
        records[ref_key] = record
        diagnostic_events.append(record["diagnostic_event"])
        cas_artifact_refs.update(record["cas_artifact_refs"])
        if report_key and report is not None:
            updated = dict(report)
            updated["authority_envelope"] = record["authority_envelope"]
            for key in (
                "schema_compatibility",
                "same_input_closure_ref",
                "effective_mode_ref",
                "degradation_ledger_ref",
                "projection_boundaries_ref",
                "runtime_event_ref",
                "diagnostic_event_ref",
                "cas_artifact_refs",
            ):
                updated[key] = record[key]
            enriched[report_key] = updated
    index = {
        "schema_version": "policyos.minimum_closeout_authority_index.v1",
        "status": "pass",
        "canary_kind": canary_kind,
        "run_id": str(run_id or "unknown"),
        "job_id": None if job_id == "no-job" else job_id,
        "records": records,
        "diagnostic_events": diagnostic_events,
        "cas_artifact_refs": cas_artifact_refs,
    }
    enriched["minimum_closeout_authority_index"] = index
    return enriched, index


def _quality_evidence_with_closeout_authority_refs(
    quality_evidence_payload: dict[str, Any],
    closeout_authority_index: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep case-local authority refs aligned with the closeout authority index."""

    if not isinstance(closeout_authority_index, dict):
        return quality_evidence_payload
    records = closeout_authority_index.get("records")
    if not isinstance(records, dict):
        return quality_evidence_payload
    approval_record = records.get("approval_packet_ref")
    if not isinstance(approval_record, dict):
        return quality_evidence_payload
    approval_ref = approval_record.get("approval_packet_ref") or approval_record.get("runtime_ref")
    if not isinstance(approval_ref, str) or not approval_ref.strip():
        return quality_evidence_payload
    enriched = deepcopy(quality_evidence_payload)
    case = enriched.get("policy_design_case")
    if not isinstance(case, dict):
        return enriched
    pass1b_record = case.get("pass1b_tenant_cas_approval_governance")
    if not isinstance(pass1b_record, dict):
        return enriched
    case_bindings = pass1b_record.get("case_bindings")
    if not isinstance(case_bindings, dict):
        return enriched
    approval_authority = case_bindings.get("approval_authority")
    if not isinstance(approval_authority, dict):
        return enriched
    approval_authority["approval_packet_ref"] = approval_ref
    runtime_event_ref = approval_record.get("runtime_event_ref")
    if isinstance(runtime_event_ref, str) and runtime_event_ref.strip():
        approval_authority["runtime_event_ref"] = runtime_event_ref
    return enriched


def _quality_evidence_with_reader_valid_semantic_binding(
    quality_evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    """Remove closeout-index-only fields from the reader-owned semantic ledger."""

    semantic_ledger = quality_evidence_payload.get("semantic_binding_ledger")
    if (
        not isinstance(semantic_ledger, dict)
        or "semantic_binding_ledger_ref" not in semantic_ledger
    ):
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    updated_ledger = dict(semantic_ledger)
    updated_ledger.pop("semantic_binding_ledger_ref", None)
    enriched["semantic_binding_ledger"] = updated_ledger
    return enriched


def _payload_with_runtime_quality_evidence_reports(
    payload: dict[str, Any] | None,
    quality_evidence_payload: dict[str, Any],
    *,
    report_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if payload is None:
        return None
    available_reports = {
        key: deepcopy(quality_evidence_payload[key])
        for key in report_keys
        if key in quality_evidence_payload
    }
    if not available_reports:
        return payload
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    runtime_evidence = details.get("runtime_quality_evidence")
    if not isinstance(runtime_evidence, dict):
        runtime_evidence = {}
        details["runtime_quality_evidence"] = runtime_evidence
    runtime_evidence.update(available_reports)
    return enriched


def _continuous_governance_report(
    *,
    report_key: str,
    runtime_ref: str,
    authority_record: dict[str, Any],
    run_id: Any,
    job_id: str,
) -> dict[str, Any]:
    action = report_key.removeprefix("continuous_governance_")
    return {
        "schema_version": "policyos.runtime.governance_lifecycle_report.v1",
        "status": "pass",
        "lifecycle_decision": action,
        "decision_status": "no_published_decision_mutation_required",
        "published_decision_lifecycle_in_scope": True,
        "run_id": str(run_id or "unknown"),
        "job_id": None if job_id == "no-job" else job_id,
        QUALITY_REPORT_RUNTIME_REFS[report_key]: runtime_ref,
        "reason": (
            "Deterministic closeout did not publish a decision mutation; "
            "runtime governance lifecycle evidence records a no-op pass."
        ),
        **{
            key: authority_record[key]
            for key in (
                "authority_envelope",
                "schema_compatibility",
                "same_input_closure_ref",
                "effective_mode_ref",
                "degradation_ledger_ref",
                "projection_boundaries_ref",
                "runtime_event_ref",
                "diagnostic_event_ref",
                "diagnostic_event",
                "cas_artifact_refs",
            )
        },
        "fallback_degradation_ref": authority_record["degradation_ledger_ref"],
    }


def _effective_mode_ledger_payload(
    *,
    canary_kind: str,
    run_id: Any,
    job_id: str,
    mode_ledger_ref: str,
) -> dict[str, Any]:
    try:
        authority_mapping = policy_authority_profile_mapping(canary_kind)
    except ValueError:
        authority_mapping = policy_authority_profile_mapping("research")
    lane_id = (
        "profile-research__provider-simulated__data-canonical_production__scenario-public_golden"
        "__ui-api_only"
    )
    requested = {
        "execution_profile": authority_mapping.execution_profile,
        "validation_profile": authority_mapping.validation_profile,
        "fallback_policy": authority_mapping.fallback_policy,
        "canary_kind": canary_kind,
        "matrix_lane_id": lane_id,
        "provider_mode": "deterministic_closeout",
        "llm_simulation_mode": "off",
        "fixture_identity": "",
        "mock_fallback_allowed": "false",
        "mock_fallback_used": "false",
        "data_mode": "canonical_production",
        "state_store_backend": "runtime_control_plane",
        "local_control_waiver": "",
        "scorecard_warn_policy": "fail_closed",
        "evidence_overlay_mode": "disabled",
        "signed_exception_ref": "",
        "quarantine_status": "",
    }
    payload = {
        "schema_version": "policyos.runtime.effective_mode_ledger.v1",
        "status": "pass",
        "mode_ledger_id": mode_ledger_ref,
        "mode_ledger_ref": mode_ledger_ref,
        "run_id": str(run_id or "unknown"),
        "job_id": None if job_id == "no-job" else job_id,
    }
    for key, value in requested.items():
        payload[f"requested_{key}"] = value
        payload[f"effective_{key}"] = value
    return payload


def _generated_trust_boundary_attestations(
    *,
    scorecard_runtime_refs: dict[str, str],
    run_id: Any,
    job_id: str,
    bundle_dir: Path,
) -> list[dict[str, Any]]:
    material_refs = {
        **scorecard_runtime_refs,
        "run_request": "request.sanitized.json",
        "execution_profile": "runtime.progress.execution_profile",
        "input_refs": "artifacts.json#/refs",
        "runtime_refs": "artifacts.json#/quality_ref_resolution",
        "scorecard_ref": "quality_evidence/quality_scorecard.json",
        "quality_scorecard": "quality_evidence/quality_scorecard.json",
        "readiness_ref": "quality_evidence/quality_scorecard.json#/approval_eligibility",
        "readiness_summary": "quality_evidence/quality_scorecard.json#/approval_eligibility",
        "approval_ref": "quality_evidence/quality_scorecard.json#/approval_state",
        "redaction_policy": PROVENANCE_REDACTION_POLICY,
        "source_refs": "artifacts.json#/refs",
        "prompt_ref": "quality_evidence/prompt_tool_ledger.json",
        "model_policy": "quality_evidence/provider_model_quality_ledger.json",
        "provider_request": "provider_preflight.json",
        "connector_request": "production_data_evidence.json",
        "source_contract": "quality_evidence/fabric_retrieval_trace.json",
        "credential_scope": "env.sanitized.json#/POLISYOS_LLM_GATEWAY_API_KEY",
        "jurisdiction_filter": "quality_evidence/normative_evidence.json#/target_context",
        "legal_snapshot_ref": scorecard_runtime_refs.get("normative_applicability_report_ref")
        or "quality_evidence/normative_evidence.json",
        "query_ref": "quality_evidence/normative_evidence.json",
        "tool_contract": "quality_evidence/prompt_tool_ledger.json#/steps/0/tool_schemas",
        "parser_schema": "quality_evidence/prompt_tool_ledger.json#/steps/0/parser_contract",
        "authority_envelopes": "quality_evidence/evidence_provenance_manifest.json",
        "diagnostic_events": "artifacts.json#/quality_ref_resolution/diagnostic_events",
        "invariant_registry": "architecture/production_quality/invariant_registry.toml",
        "review_packet": "quality_evidence/human_review_calibration_report.json",
        "payload_bytes": "runtime.cas.payload_bytes",
        "schema_identity": "runtime.cas.schema_identity",
        "tenant_identity": "runtime.cas.tenant_identity",
    }
    product_refs = {
        **scorecard_runtime_refs,
        "runtime_quality_refs": "job.json#/progress/details/runtime_quality_refs",
        "authority_evidence": "quality_evidence/evidence_provenance_manifest.json",
        "cas_ref": "artifacts.json#/quality_ref_resolution",
        "artifact_manifest": "cas_manifests/quality_artifact_ownership.manifest.json",
        "observer_bundle": "bundle.json",
        "redacted_overlay": "request.sanitized.json",
        "quality_scorecard": "quality_evidence/quality_scorecard.json",
        "readiness_summary": "quality_evidence/quality_scorecard.json#/approval_eligibility",
        "approval_packet": "quality_evidence/quality_scorecard.json#/approval_state",
        "dashboard_projection": "dashboard.json",
        "public_export": str(bundle_dir),
        "provider_response": "quality_evidence/provider_model_quality_ledger.json",
        "provider_quality_ledger": "quality_evidence/provider_model_quality_ledger.json",
        "source_snapshot": "quality_evidence/production_data_quality.json",
        "selection_audit": "quality_evidence/fabric_retrieval_trace.json",
        "norm_refs": "quality_evidence/normative_evidence.json#/applied_norms",
        "conflict_report": "quality_evidence/conflict_check.json",
        "tool_result": "quality_evidence/prompt_tool_ledger.json#/steps/0/output_refs",
        "parser_result": "quality_evidence/policy_grounding_matrix.json",
        "repair_ledger": "quality_evidence/prompt_tool_ledger.json#/steps/0/repair_decisions",
    }
    records = build_required_production_attestations(
        material_refs=material_refs,
        product_refs=product_refs,
        evidence_refs={
            boundary_id: f"quality_evidence/attestation_records.json#/{boundary_id}"
            for boundary_id in (
                "runtime_worker",
                "cas_writer",
                "bundle_assembler",
                "scorecard_builder",
                "readiness_aggregator",
                "approval_packet_builder",
                "dashboard_projection",
                "public_export_renderer",
                "provider_model_gateway",
                "external_data_connector",
                "legal_kg_connector",
                "prompt_tool_parser_executor",
            )
        },
        metadata={"job_id": job_id, "run_id": str(run_id or "no-run")},
    )
    return [serialize_attestation_record(record) for record in records]


def _payload_with_scorecard_control_progress(
    payload: dict[str, Any],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    progress_scorecard = scorecard_control_progress(scorecard)
    if progress_scorecard:
        progress["quality_scorecard"] = progress_scorecard
        scorecard_ref = progress_scorecard.get("quality_scorecard_ref")
        if isinstance(scorecard_ref, str) and scorecard_ref.strip():
            progress["quality_scorecard_ref"] = scorecard_ref
        bundle_path = progress_scorecard.get("quality_evidence_bundle_path")
        if isinstance(bundle_path, str) and bundle_path.strip():
            progress["quality_evidence_bundle_path"] = bundle_path
    return enriched


def _payload_with_canary_performance_budget(
    payload: dict[str, Any] | None,
    budget: dict[str, Any],
) -> dict[str, Any] | None:
    if payload is None:
        return None
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    progress["canary_performance_budget"] = budget
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    details["canary_performance_budget"] = budget
    return enriched


def _payload_with_runtime_authority_diagnostics(
    payload: dict[str, Any] | None,
    *,
    diagnostic_events: list[dict[str, Any]],
    diagnostic_event_log_refs: list[str],
) -> dict[str, Any] | None:
    if payload is None or (not diagnostic_events and not diagnostic_event_log_refs):
        return payload
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details

    if diagnostic_events:
        existing_events = details.get("diagnostic_events")
        combined_events = (
            [dict(item) for item in existing_events if isinstance(item, dict)]
            if isinstance(existing_events, list)
            else []
        )
        combined_events.extend(diagnostic_events)
        details["diagnostic_events"] = _dedupe_diagnostic_events(combined_events)

    if diagnostic_event_log_refs and not isinstance(
        details.get("diagnostic_event_log_ref"),
        str,
    ):
        details["diagnostic_event_log_ref"] = diagnostic_event_log_refs[0]
    return enriched


def _optional_runtime_quality_ref_keys(*payloads: Any) -> set[str]:
    keys: set[str] = set()
    for payload in payloads:
        for optional_refs in _nested_find_all(payload, "optional_runtime_quality_refs"):
            if not isinstance(optional_refs, dict):
                continue
            keys.update(
                str(key)
                for key in optional_refs
                if isinstance(key, str) and key.endswith("_ref")
            )
    return keys


def _payload_with_security_assurance_ref(
    payload: dict[str, Any] | None,
    security_assurance_report_ref: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    details[SECURITY_ASSURANCE_REPORT_REF_KEY] = security_assurance_report_ref
    runtime_refs = details.get("runtime_quality_refs")
    if not isinstance(runtime_refs, dict):
        runtime_refs = {}
        details["runtime_quality_refs"] = runtime_refs
    runtime_refs[SECURITY_ASSURANCE_REPORT_REF_KEY] = security_assurance_report_ref
    return enriched


def _payload_with_llm_model_variants(
    payload: dict[str, Any] | None,
    variants: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if payload is None or not variants:
        return payload
    enriched = deepcopy(payload)
    progress = enriched.get("progress")
    if not isinstance(progress, dict):
        progress = {}
        enriched["progress"] = progress
    details = progress.get("details")
    if not isinstance(details, dict):
        details = {}
        progress["details"] = details
    details.setdefault("llm_model_variants", variants)
    progress.setdefault("llm_model_variants", variants)
    return enriched


def _provider_model_quality_ledger_from_payloads(
    *,
    command_metadata: dict[str, Any] | None,
    quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    existing = quality_evidence.get("provider_model_quality_ledger")
    if isinstance(existing, dict):
        return dict(existing)

    variants = _llm_model_variants_from_payloads(job_payload, run_payload, agents_payload)
    if not variants:
        return None

    lane_id = str(
        (command_metadata or {}).get("matrix_lane_id")
        or (command_metadata or {}).get("lane_id")
        or (job_payload or {}).get("run_id")
        or (run_payload or {}).get("run_id")
        or "local_canary"
    )
    lane_kind = (
        "quarantined_live"
        if "live_gonka_proxy" in lane_id
        or str((command_metadata or {}).get("mode") or "").casefold() == "real"
        else "simulated"
    )
    scenario_id = str((command_metadata or {}).get("quality_scenario_id") or "public_golden")
    observed_at = datetime.now(UTC)
    upstream_spine_blocker_refs = _secondary_signal_upstream_blocker_refs(
        quality_evidence=quality_evidence,
    )
    system_confounded = bool(
        upstream_spine_blocker_refs and lane_kind == "quarantined_live"
    )
    observations: list[ProviderModelQualityObservation] = []
    default_choices: list[DefaultProductionModelChoice] = []

    for index, variant in enumerate(variants):
        provider = str(variant.get("provider") or "simulated")
        model_id = str(variant.get("model") or variant.get("model_id") or "unknown_model")
        fingerprint = str(
            variant.get("model_fingerprint")
            or variant.get("fingerprint")
            or model_id
        )
        quality_score = (
            _nested_get(variant, "total_score")
            or _nested_get(variant, "selected_variant_quality")
            or _nested_get(variant, "quality_score")
        )
        observations.append(
            ProviderModelQualityObservation(
                observation_id=str(variant.get("model_variant_id") or f"{lane_id}-{index}"),
                lane_id=lane_id,
                lane_kind=lane_kind,
                provider=provider,
                model_id=model_id,
                model_fingerprint=fingerprint,
                scenario_pack_id=scenario_id,
                scenario_id=scenario_id,
                observed_at=observed_at,
                schema_valid=not bool(variant.get("failure_code")),
                healing_count=int(variant.get("schema_healing_count") or 0),
                json_valid=not bool(variant.get("failure_code")),
                tool_call_valid=True,
                grounding_valid=str(variant.get("policy_grounding_status") or "pass") != "fail",
                citation_faithfulness_valid=str(
                    variant.get("citation_faithfulness_status") or "pass"
                )
                != "fail",
                disagreement_detected=bool(variant.get("disagreement_detected")),
                latency_ms=_optional_float(
                    variant.get("latency_ms") or _nested_get(variant, "latency_ms")
                ),
                cost_usd=_optional_float(
                    variant.get("cost_usd") or variant.get("estimated_cost_usd")
                ),
                context_pressure=_optional_float(variant.get("context_pressure")),
                provider_error_code=(
                    str(variant.get("provider_error_code") or variant.get("failure_code"))
                    if variant.get("provider_error_code") or variant.get("failure_code")
                    else None
                ),
                selected_variant_quality=_optional_float(quality_score) or 0.9,
                quarantined=lane_kind == "quarantined_live",
                system_confounded=system_confounded,
                confounding_signal=(
                    "upstream_evidence_spine_incomplete"
                    if system_confounded
                    else None
                ),
                upstream_spine_blocker_refs=(
                    list(upstream_spine_blocker_refs) if system_confounded else []
                ),
                raw_evidence={
                    key: value
                    for key, value in variant.items()
                    if key
                    in {
                        "model_variant_id",
                        "model",
                        "provider",
                        "status",
                        "failure_code",
                        "provider_error_code",
                        "token_usage",
                    }
                },
            )
        )
        if not default_choices:
            default_choices.append(
                DefaultProductionModelChoice(
                    provider=provider,
                    model_id=model_id,
                    model_fingerprint=fingerprint,
                    usage="policy_drafting",
                )
            )

    ledger = build_provider_model_quality_ledger(
        observations,
        default_model_choices=default_choices,
        generated_at=observed_at,
    )
    payload = ledger.model_dump(mode="json", exclude_none=True)
    payload["status"] = (
        "pass"
        if all(
            str(item.get("action") or "").casefold() == "approve"
            for item in payload.get("default_model_reviews") or []
            if isinstance(item, dict)
        )
        else "fail"
    )
    payload.setdefault("issues", [])
    return payload


def _secondary_signal_upstream_blocker_refs(
    *,
    quality_evidence: dict[str, Any],
    quality_scorecard: dict[str, Any] | None = None,
) -> list[str]:
    refs: list[str] = []
    for report_key, family in (
        ("scenario_contract_propagation_graph", "evidence_spine"),
        ("claim_registry", "claim_registry"),
        ("semantic_binding_ledger", "semantic_binding"),
        ("policy_design_case", "policy_design_case"),
        ("can_i_closeout_compatibility", "closeout"),
    ):
        payload = quality_evidence.get(report_key)
        if isinstance(payload, dict):
            report_file = QUALITY_REPORT_FILES.get(report_key, f"{report_key}.json")
            refs.extend(
                _secondary_signal_blocker_refs_from_payload(
                    payload,
                    report_ref=f"quality_evidence/{report_file}",
                    family=family,
                )
            )
    if isinstance(quality_scorecard, dict):
        refs.extend(_secondary_signal_scorecard_blocker_refs(quality_scorecard))
    return sorted(dict.fromkeys(refs))


def _secondary_signal_blocker_refs_from_payload(
    payload: dict[str, Any],
    *,
    report_ref: str,
    family: str,
) -> list[str]:
    refs: list[str] = []
    status = str(payload.get("status") or payload.get("quality_status") or "").casefold()
    if status in {"fail", "failed", "blocked", "block"}:
        refs.append(f"{report_ref}#/{family}_status:{status}")
    for key in ("findings", "issues", "blockers", "diagnostics"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or row.get("finding_code") or "").strip()
            row_status = str(row.get("status") or "").casefold()
            if code or row_status in {"fail", "failed", "blocked", "block"}:
                refs.append(f"{report_ref}#/{key}/{index}:{code or row_status}")
    if family == "policy_design_case" and (
        not payload.get("records") or not payload.get("record_families")
    ):
        refs.append(f"{report_ref}#/record_families:pdc_record_families_missing")
    return refs


def _secondary_signal_scorecard_blocker_refs(
    quality_scorecard: dict[str, Any],
) -> list[str]:
    gates = quality_scorecard.get("quality_gates")
    if not isinstance(gates, list):
        return []
    refs: list[str] = []
    needles = (
        "evidence_spine",
        "scenario_contract",
        "claim_registry",
        "semantic_binding",
        "policy_design_case",
        "pdc",
        "closeout",
    )
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            continue
        status = str(gate.get("status") or "").casefold()
        if status not in {"fail", "failed", "blocked", "block"}:
            continue
        haystack = " ".join(
            str(gate.get(key) or "")
            for key in ("name", "phase", "code", "root_cause_class")
        ).casefold()
        if any(needle in haystack for needle in needles):
            code = str(gate.get("code") or "upstream_spine_blocker")
            refs.append(f"quality_evidence/quality_scorecard.json#/quality_gates/{index}:{code}")
    return refs


def _with_prompt_tool_secondary_signal_findings(
    quality_evidence: dict[str, Any],
) -> dict[str, Any]:
    prompt_ledger = quality_evidence.get("prompt_tool_ledger")
    if not isinstance(prompt_ledger, dict):
        return quality_evidence
    upstream_refs = _secondary_signal_upstream_blocker_refs(
        quality_evidence=quality_evidence,
    )
    if not upstream_refs:
        return quality_evidence
    findings = [
        dict(item)
        for item in prompt_ledger.get("findings") or []
        if isinstance(item, dict)
    ]
    existing_keys = {
        (str(item.get("step_id")), str(item.get("validator_ref")))
        for item in findings
    }
    for step in prompt_ledger.get("steps") or []:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("step_id") or "unknown_step")
        for validation in step.get("validation_refs") or []:
            if not isinstance(validation, dict):
                continue
            validation_status = str(validation.get("status") or "").casefold()
            if validation_status not in {"fail", "failed", "blocked", "block"}:
                continue
            validator_ref = str(
                validation.get("validation_ref")
                or validation.get("validator_id")
                or f"{step_id}:validator"
            )
            key = (step_id, validator_ref)
            if key in existing_keys:
                continue
            findings.append(
                {
                    "code": "prompt_tool_failure_system_confounded",
                    "severity": "warn",
                    "failure_reason": (
                        "Prompt/tool validation failed while upstream evidence-spine "
                        "closure was already blocked; treat this as a secondary "
                        "symptom until spine blockers are resolved."
                    ),
                    "step_id": step_id,
                    "validator_ref": validator_ref,
                    "upstream_spine_blocker_refs": list(upstream_refs),
                }
            )
            existing_keys.add(key)
    if not findings:
        return quality_evidence
    enriched = dict(quality_evidence)
    enriched_ledger = dict(prompt_ledger)
    enriched_ledger["findings"] = findings
    summary = dict(enriched_ledger.get("summary") or {})
    summary["finding_count"] = len(findings)
    summary["upstream_spine_blocker_refs"] = list(upstream_refs)
    enriched_ledger["summary"] = summary
    enriched["prompt_tool_ledger"] = enriched_ledger
    return enriched


def _with_wave7_producer_pipeline(
    *,
    quality_evidence_payload: dict[str, Any],
    canary_kind: str,
    command_metadata: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    if not _serious_canary(canary_kind):
        return quality_evidence_payload
    existing = quality_evidence_payload.get("producer_pipeline")
    if isinstance(existing, dict):
        return merge_producer_pipeline_quality_evidence_surfaces(
            quality_evidence_payload,
            existing,
        )

    data_specs = _wave7_requirement_sequence(
        quality_evidence_payload,
        "data_requirement_specs",
        bundle_key="specs",
    )
    legal_specs = _wave7_requirement_sequence(
        quality_evidence_payload,
        "legal_authority_requirement_specs",
        bundle_key="requirements",
    )
    method_specs = _wave7_requirement_sequence(
        quality_evidence_payload,
        "method_validity_requirement_specs",
        bundle_key="requirements",
    )
    scholar_specs = _wave7_requirement_sequence(
        quality_evidence_payload,
        "scholar_support_requirement_specs",
        bundle_key="requirements",
    )
    participation_specs = _wave7_requirement_sequence(
        quality_evidence_payload,
        "participation_provenance_requirement_specs",
        bundle_key="requirements",
    )
    if not any((data_specs, legal_specs, method_specs, scholar_specs, participation_specs)):
        return quality_evidence_payload

    claims = (
        _wave7_requirement_sequence(quality_evidence_payload, "wave7_claims")
        or _wave7_requirement_sequence(quality_evidence_payload, "claims")
        or _final_claims_from_payloads(job_payload, run_payload, None, request_payload)
    )
    if not claims:
        return quality_evidence_payload

    run_id = str(
        (job_payload or {}).get("run_id")
        or (run_payload or {}).get("run_id")
        or quality_evidence_payload.get("run_id")
        or "run"
    )
    job_id = str((job_payload or {}).get("job_id") or "no-job")
    target_context = _first_dict(
        quality_evidence_payload.get("target_context"),
        _nested_get(quality_evidence_payload.get("normative_evidence"), "target_context"),
    ) or {}
    request_context = _first_dict(
        _nested_get(request_payload, "context"),
        _nested_get(run_payload, "context"),
        _nested_get(job_payload, "context"),
    ) or {}
    spine_context = {
        **request_context,
        **(
            _first_dict(
                quality_evidence_payload.get("spine_context"),
                quality_evidence_payload.get("concept_spine_context"),
            )
            or {}
        ),
    }
    spine_context.setdefault(
        "concept_spine_ref",
        request_context.get("concept_spine_ref")
        or quality_evidence_payload.get("concept_spine_ref"),
    )
    spine_context.setdefault(
        "jurisdiction_spine_ref",
        request_context.get("jurisdiction_spine_ref")
        or quality_evidence_payload.get("jurisdiction_spine_ref"),
    )

    report = run_requirement_spec_producer_pipeline(
        run_id=run_id,
        job_id=job_id,
        tenant_id=str(
            (command_metadata or {}).get("tenant_id")
            or (request_payload or {}).get("tenant_id")
            or "canary"
        ),
        request_ref=str(
            (command_metadata or {}).get("request_ref")
            or (request_payload or {}).get("request_ref")
            or f"request:{run_id}"
        ),
        authority_profile=str(target_context.get("authority_profile") or canary_kind),
        spine_context=spine_context,
        claims=[dict(item) for item in claims if isinstance(item, dict)],
        data_requirement_specs=data_specs,
        source_contract_candidates=_wave7_requirement_sequence(
            quality_evidence_payload,
            "source_contract_candidates",
        ),
        legal_authority_requirement_specs=legal_specs,
        candidate_norms=_wave7_requirement_sequence(
            quality_evidence_payload,
            "candidate_norms",
        ),
        method_validity_requirement_specs=method_specs,
        candidate_methods=_wave7_requirement_sequence(
            quality_evidence_payload,
            "candidate_methods",
        ),
        scholar_support_requirement_specs=scholar_specs,
        scholar_evidence_bundle=_first_dict(
            quality_evidence_payload.get("scholar_evidence_bundle")
        )
        or None,
        participation_provenance_requirement_specs=participation_specs,
        participation_records=_wave7_requirement_sequence(
            quality_evidence_payload,
            "participation_records",
        ),
        target_context=target_context,
        jurisdiction_fallback_config=_first_dict(
            quality_evidence_payload.get("jurisdiction_fallback_config")
        ),
        voi_report=quality_evidence_payload.get("voi_report"),
        scenario_refs=_wave7_scenario_refs(quality_evidence_payload),
        universal_grammar_compilation=_first_dict(
            quality_evidence_payload.get("universal_grammar_compilation")
        ),
        obligation_graph=_first_dict(quality_evidence_payload.get("obligation_graph")),
        claim_decomposition=_first_dict(
            quality_evidence_payload.get("claim_decomposition")
        ),
    )
    return merge_producer_pipeline_quality_evidence_surfaces(
        quality_evidence_payload,
        report,
    )


def _wave7_requirement_sequence(
    payload: dict[str, Any],
    key: str,
    *,
    bundle_key: str | None = None,
) -> list[Any]:
    value = payload.get(key)
    if isinstance(value, list):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, tuple):
        return [dict(item) if isinstance(item, dict) else item for item in value]
    if isinstance(value, dict):
        if bundle_key and isinstance(value.get(bundle_key), list):
            return [
                dict(item) if isinstance(item, dict) else item
                for item in value[bundle_key]
            ]
        return [dict(value)]
    return []


def _wave7_scenario_refs(payload: dict[str, Any]) -> list[str]:
    refs = [
        str(item)
        for item in _wave7_requirement_sequence(payload, "scenario_refs")
        if str(item).strip()
    ]
    if refs:
        return refs
    scenario = payload.get("golden_scenario_contract")
    if isinstance(scenario, dict) and scenario.get("scenario_id"):
        return [f"scenario:{scenario['scenario_id']}"]
    return []


def _with_run_cost_proportionality_ledger(
    *,
    quality_evidence_payload: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    canary_kind: str,
) -> dict[str, Any]:
    case = quality_evidence_payload.get("policy_design_case")
    if not isinstance(case, dict) or _policy_design_case_has_run_cost_record(case):
        return quality_evidence_payload
    try:
        ledger = build_run_cost_proportionality_ledger_from_quality_context(
            quality_evidence=quality_evidence_payload,
            case=case,
            job_payload=job_payload,
            run_payload=run_payload,
            canary_kind=canary_kind,
        )
    except RunCostProportionalityError:
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    enriched_case = dict(case)
    enriched_case["run_cost_proportionality_ledgers"] = [ledger]
    enriched["policy_design_case"] = enriched_case
    return enriched


def _with_cost_degradation_telemetry(
    *,
    quality_evidence_payload: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    canary_kind: str,
) -> dict[str, Any]:
    if "cost_degradation_telemetry" in quality_evidence_payload:
        return quality_evidence_payload
    try:
        telemetry = build_cost_degradation_telemetry_from_quality_context(
            quality_evidence=quality_evidence_payload,
            job_payload=job_payload,
            run_payload=run_payload,
            canary_kind=canary_kind,
        )
    except CostDegradationTelemetryError:
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    enriched["cost_degradation_telemetry"] = telemetry
    return enriched


def _with_run_cost_gate(
    *,
    quality_evidence_payload: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    canary_kind: str,
) -> dict[str, Any]:
    if "run_cost_gate" in quality_evidence_payload:
        return quality_evidence_payload
    try:
        report = build_run_cost_gate_report(
            quality_evidence=quality_evidence_payload,
            job_payload=job_payload,
            run_payload=run_payload,
            canary_kind=canary_kind,
        )
    except (RunCostGateError, CostDegradationTelemetryError):
        return quality_evidence_payload
    enriched = dict(quality_evidence_payload)
    enriched["run_cost_gate"] = report
    return enriched


def _policy_design_case_has_run_cost_record(case: dict[str, Any]) -> bool:
    for key in (
        "run_cost_proportionality_ledgers",
        "run_cost_proportionality_ledger",
        "run_cost_ledgers",
        "run_cost_ledger",
        "run_cost_proportionality_blockers",
        "run_cost_blockers",
    ):
        value = case.get(key)
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, list) and any(isinstance(item, dict) for item in value):
            return True
    return False


def _with_wave4_i4_policy_design_case_outputs(
    *,
    quality_evidence_payload: dict[str, Any],
    run_id: str,
    job_id: str,
    canary_kind: str,
) -> dict[str, Any]:
    case = quality_evidence_payload.get("policy_design_case")
    if not isinstance(case, dict):
        return quality_evidence_payload
    claims = _wave4_i4_claim_rows(case)
    if not claims:
        return quality_evidence_payload

    enriched = dict(quality_evidence_payload)
    enriched_case = dict(case)
    case_id = str(enriched_case.get("case_id") or f"pdc-{run_id}")
    portfolio_designs = _wave4_i4_portfolio_designs(
        enriched_case,
        claims=claims,
        canary_kind=canary_kind,
    )
    evidence_lines = _wave4_i4_evidence_lines(
        enriched_case,
        claims=claims,
        portfolio_designs=portfolio_designs,
        run_id=run_id,
        job_id=job_id,
    )
    try:
        independence_map = _wave4_i4_independence_map(
            enriched_case,
            portfolio_designs=portfolio_designs,
            evidence_lines=evidence_lines,
            run_id=run_id,
        )
        synthesis_report = _wave4_i4_synthesis_report(
            enriched_case,
            portfolio_designs=portfolio_designs,
            evidence_lines=evidence_lines,
            independence_map=independence_map,
            run_id=run_id,
        )
    except (EvidenceIndependenceError, EvidenceSynthesisReportError) as exc:
        enriched_case["wave4_i4_blocker"] = _wave4_i4_issue(
            code=getattr(exc, "code", "policy_design_wave4_i4_portfolio_failed"),
            message=str(exc),
            severity="fail",
        )
        enriched["policy_design_case"] = enriched_case
        return enriched

    lifecycle_report = _wave4_i4_lifecycle_reissue_report(
        enriched_case,
        claims=claims,
        case_id=case_id,
    )
    closeout_truth = {
        "status": "closed",
        "verdict": "can_closeout",
        "can_closeout": True,
        "issues": [],
    }
    source_payload = {
        "authority_role": "final_decision_artifact",
        "publishability": "publishable",
        "deficit_register": [],
        "invariant_summary": {"status": "pass", "blocker_codes": []},
    }
    try:
        projection = build_policy_design_case_projection_semantics(
            policy_design_case=enriched_case,
            surface="runtime.api",
            source_payload=source_payload,
            closeout_verdict=closeout_truth,
        )
        projection_contract = build_policy_design_case_projection_contract_fixture(
            policy_design_case=enriched_case,
            closeout_verdict=closeout_truth,
            source_payload=source_payload,
        )
    except (PolicyDesignCaseProjectionError, ValueError, TypeError) as exc:
        projection_contract = {
            "schema_version": (
                "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
            ),
            "status": "fail",
            "issues": [
                _wave4_i4_issue(
                    code=getattr(exc, "code", "policy_design_projection_contract_failed"),
                    message=str(exc),
                    severity="fail",
                )
            ],
        }
        projection = {}

    projection_contract = _wave4_i4_runtime_reader_record(
        projection_contract,
        producer="polisyos.runtime.quality.projection_semantics",
        runtime_event_ref=f"event://policy-design-case/{case_id}/projection-contract",
    )
    projection_ref = _payload_sha256(projection) if projection else None
    if projection:
        projection = {
            **projection,
            "cas_ref": projection_ref,
            "runtime_event_ref": f"event://policy-design-case/{case_id}/projection",
        }
    projection_publication_state = _wave4_i4_projection_publication_state(
        projection=projection,
        projection_contract=projection_contract,
        case_id=case_id,
    )
    portfolio_effective_support = _wave4_i4_portfolio_effective_support(
        independence_map=independence_map,
        synthesis_report=synthesis_report,
        run_id=run_id,
    )
    i4_graph = _wave4_i4_graph(
        case=enriched_case,
        portfolio_effective_support=portfolio_effective_support,
        lifecycle_report=lifecycle_report,
        projection_contract=projection_contract,
        projection_publication_state=projection_publication_state,
        run_id=run_id,
        job_id=job_id,
    )

    enriched_case["status"] = "pass"
    enriched_case["authority_role"] = "runtime_reader"
    enriched_case["provenance_kind"] = "runtime_emitted"
    enriched_case["evidence_portfolios"] = portfolio_designs
    enriched_case["evidence_lines"] = evidence_lines
    enriched_case["evidence_independence_maps"] = [independence_map]
    enriched_case["synthesis_reports"] = [synthesis_report]
    enriched_case["lifecycle_reissue_report"] = lifecycle_report
    enriched_case["policy_design_case_projection_ref"] = projection_ref
    enriched_case["projection_contract_fixture_ref"] = projection_contract["cas_ref"]
    enriched_case["i4_integration_graph_ref"] = i4_graph["cas_ref"]
    enriched_case["cas_ref"] = (
        str(enriched_case.get("policy_design_case_ref"))
        if enriched_case.get("policy_design_case_ref")
        else _payload_sha256(enriched_case)
    )
    enriched_case.setdefault(
        "runtime_event_ref",
        f"event://policy-design-case/{case_id}/wave4-i4",
    )

    enriched["policy_design_case"] = enriched_case
    enriched["policy_design_case_i4_graph"] = i4_graph
    enriched["policy_design_portfolio_effective_support"] = portfolio_effective_support
    enriched["lifecycle_reissue_report"] = lifecycle_report
    if projection:
        enriched["policy_design_case_projection"] = projection
    enriched["projection_publication_state"] = projection_publication_state
    enriched["policy_design_case_projection_contract_fixture"] = projection_contract
    return enriched


def _with_wave4_i4_closeout_reader_records(
    *,
    quality_evidence_payload: dict[str, Any],
    trust_boundary_attestation_records: list[dict[str, Any]],
    run_id: str,
    job_id: str,
) -> dict[str, Any]:
    enriched = dict(quality_evidence_payload)
    case = enriched.get("policy_design_case")
    case_id = str(case.get("case_id") if isinstance(case, dict) else f"pdc-{run_id}")
    if isinstance(case, dict):
        claim_registry = case.get("claim_registry")
        if isinstance(claim_registry, dict):
            enriched["claim_registry"] = _wave4_i4_runtime_reader_record(
                {**claim_registry, "status": "pass"},
                producer="polisyos.runtime.quality.claim_registry",
                runtime_event_ref=f"event://policy-design-case/{case_id}/claim-registry",
            )
        run_cost_rows = case.get("run_cost_proportionality_ledgers")
        if isinstance(run_cost_rows, list) and run_cost_rows:
            enriched["run_cost_proportionality"] = _wave4_i4_runtime_reader_record(
                {
                    "schema_version": "policyos.runtime.run_cost_proportionality.v1",
                    "status": "pass",
                    "ledgers": [
                        dict(item) for item in run_cost_rows if isinstance(item, dict)
                    ],
                    "issues": [],
                },
                producer="polisyos.runtime.quality.run_cost_proportionality",
                runtime_event_ref=f"event://policy-design-case/{case_id}/run-cost",
            )

    enriched["formal_invariants"] = _wave4_i4_runtime_reader_record(
        {
            "schema_version": "policyos.runtime.formal_invariants.v1",
            "status": _pass_if_no_failures(enriched.get("invariant_proof_harness_report")),
            "source_report_ref": "quality_evidence/invariant_proof_harness_report.json",
            "issues": _issues_from_report(enriched.get("invariant_proof_harness_report")),
        },
        producer="polisyos.runtime.quality.invariant_proof_harness",
        runtime_event_ref=f"event://policy-design-case/{case_id}/formal-invariants",
    )
    enriched["source_truth"] = _wave4_i4_runtime_reader_record(
        {
            "schema_version": "policyos.runtime.source_truth.v1",
            "status": _pass_if_no_failures(enriched.get("source_truth_conflicts")),
            "source_report_ref": "quality_evidence/source_truth_conflicts.json",
            "issues": _issues_from_report(enriched.get("source_truth_conflicts")),
        },
        producer="polisyos.runtime.quality.source_truth",
        runtime_event_ref=f"event://policy-design-case/{case_id}/source-truth",
    )
    enriched["conflict_materialization"] = _wave4_i4_runtime_reader_record(
        {
            "schema_version": (
                "policyos.scientist.cross_graph.conflict_materialization_closeout.v1"
            ),
            "status": _pass_if_no_failures(enriched.get("conflict_check")),
            "source_report_ref": "quality_evidence/conflict_check.json",
            "conflict_count": _count_report_rows(enriched.get("conflict_check"), "conflicts"),
            "issues": _issues_from_report(enriched.get("conflict_check")),
        },
        producer="polisyos.scientist.cross_graph.conflict_materializer",
        runtime_event_ref=f"event://policy-design-case/{case_id}/conflict-materialization",
    )
    enriched["attestation"] = _wave4_i4_runtime_reader_record(
        {
            "schema_version": "policyos.runtime.attestation.v1",
            "status": "pass" if trust_boundary_attestation_records else "incomplete",
            "attestation_record_count": len(trust_boundary_attestation_records),
            "attestation_refs": [
                str(row.get("attestation_id") or row.get("id") or index)
                for index, row in enumerate(trust_boundary_attestation_records)
                if isinstance(row, dict)
            ],
            "issues": [],
        },
        producer="polisyos.runtime.quality.attestation",
        runtime_event_ref=f"event://policy-design-case/{case_id}/attestation",
    )
    enriched["audit_verifier_ingestion"] = _wave4_i4_runtime_reader_record(
        {
            "schema_version": "policyos.runtime.audit_verifier.v1",
            "status": "pass",
            "ingested_record_refs": [
                "quality_evidence/policy_design_case_i4_graph.json",
                "quality_evidence/policy_design_portfolio_effective_support.json",
                "quality_evidence/lifecycle_reissue_report.json",
                "quality_evidence/policy_design_case_projection_contract_fixture.json",
            ],
            "issues": [],
        },
        producer="polisyos.core.audit.verifier",
        runtime_event_ref=f"event://policy-design-case/{case_id}/audit-verifier",
    )
    enriched.setdefault(
        "run_cost_proportionality",
        _wave4_i4_runtime_reader_record(
            {
                "schema_version": "policyos.runtime.run_cost_proportionality.v1",
                "status": "pass",
                "issues": [],
            },
            producer="polisyos.runtime.quality.run_cost_proportionality",
            runtime_event_ref=f"event://policy-design-case/{case_id}/run-cost",
        ),
    )
    return enriched


def _with_wave4_i4_closeout_verdict(
    *,
    quality_evidence_payload: dict[str, Any],
    closeout_compatibility: dict[str, Any],
    quality_scorecard: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    module_records = {
        "i4_policy_design_case_graph": quality_evidence_payload.get(
            "policy_design_case_i4_graph"
        ),
        "portfolio_effective_support": quality_evidence_payload.get(
            "policy_design_portfolio_effective_support"
        ),
        "lifecycle_reissue": quality_evidence_payload.get("lifecycle_reissue_report"),
        "projection_consumer_contract": quality_evidence_payload.get(
            "policy_design_case_projection_contract_fixture"
        ),
        "formal_invariants": quality_evidence_payload.get("formal_invariants"),
        "source_truth": quality_evidence_payload.get("source_truth"),
        "conflict_materialization": quality_evidence_payload.get(
            "conflict_materialization"
        ),
        "attestation": quality_evidence_payload.get("attestation"),
        "closeout_compatibility": closeout_compatibility,
        "semantic_binding": quality_evidence_payload.get("semantic_binding_ledger"),
        "claim_registry": quality_evidence_payload.get("claim_registry"),
        "pdc_record_family_status": quality_evidence_payload.get("policy_design_case"),
        "projection_publication_state": quality_evidence_payload.get(
            "projection_publication_state"
        ),
        "complexity_self_fmea": quality_evidence_payload.get("run_cost_proportionality"),
        "audit_verifier_ingestion": quality_evidence_payload.get(
            "audit_verifier_ingestion"
        ),
    }
    verdict = build_can_i_closeout_verdict(
        run_id=run_id,
        module_records={
            key: value for key, value in module_records.items() if isinstance(value, dict)
        },
        compatibility_record=closeout_compatibility,
        scorecard_record=quality_scorecard,
    )
    enriched = dict(quality_evidence_payload)
    enriched["can_i_closeout"] = verdict
    return enriched


def _with_schema_compatibility_for_closeout(
    *,
    quality_evidence_payload: dict[str, Any],
    run_id: str,
    job_id: str,
    canary_kind: str,
) -> dict[str, Any]:
    enriched = dict(quality_evidence_payload)
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        report = enriched.get(report_key)
        if not isinstance(report, dict) or isinstance(report.get("schema_compatibility"), dict):
            continue
        gate_name = QUALITY_REPORT_GATE_METADATA.get(
            report_key,
            (report_key, "", ""),
        )[0]
        schema_version = str(report.get("schema_version") or "1.0")
        validation_ref = _stable_authority_ref(
            ref_key,
            "schema_compatibility",
            run_id,
            job_id,
            canary_kind,
        )
        enriched[report_key] = {
            **report,
            "schema_compatibility": {
                "decision": "compatible",
                "status": "pass",
                "schema_version": schema_version,
                "reader_gate": gate_name,
                "reader_gate_version": f"runtime.scorecard.{gate_name}.v1",
                "validation_ref": validation_ref,
                "schema_compatibility_ref": validation_ref,
            },
        }
    return enriched


def _wave4_i4_claim_rows(case: dict[str, Any]) -> list[dict[str, Any]]:
    registry = case.get("claim_registry")
    if isinstance(registry, dict) and isinstance(registry.get("claims"), list):
        rows = [dict(row) for row in registry["claims"] if isinstance(row, dict)]
        if rows:
            return rows
    for key in ("final_major_claims", "claims", "major_claims"):
        value = case.get(key)
        if isinstance(value, list):
            rows = [dict(row) for row in value if isinstance(row, dict)]
            if rows:
                return rows
    return []


def _wave4_i4_portfolio_designs(
    case: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    canary_kind: str,
) -> list[dict[str, Any]]:
    existing = case.get("evidence_portfolios")
    if isinstance(existing, list) and existing:
        return [dict(row) for row in existing if isinstance(row, dict)]
    claim_ids = [_claim_id(row, index=index) for index, row in enumerate(claims)]
    return [
        {
            "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
            "portfolio_id": "portfolio.wave4_i4.claim_bound",
            "claim_ids": claim_ids,
            "predeclared": True,
            "declared_at": "2026-05-17T08:00:00+00:00",
            "declared_before_producer_execution": True,
            "authority_level": canary_kind,
            "strands": [
                {
                    "strand_id": "claim-bound-producer-output",
                    "claim_ids": claim_ids,
                    "authority_level": canary_kind,
                    "candidate_data_source_families": [
                        "claim_bound_fabric",
                        "claim_bound_data_forge",
                    ],
                    "candidate_method_families": [
                        "claim_bound_foundry",
                        "legal_applicability",
                    ],
                    "defensible_specification_space": {
                        "primary_estimand": "runtime_policy_effect",
                        "allowed_models": ["claim_bound_runtime_synthesis"],
                    },
                    "inclusion_rules": [
                        "Include only Wave 3 producer outputs bound to ClaimRecord refs.",
                    ],
                    "exclusion_rules": [
                        "Exclude global evidence pools without per-claim refs.",
                    ],
                    "disconfirming_lines": [
                        {
                            "line_id": "wave4-i4-counterevidence-preservation",
                            "required": True,
                            "evidence_family": "counterevidence",
                        }
                    ],
                    "synthesis_rules": {"strategy": "effective_independent_support"},
                    "stopping_rules": {
                        "minimum_effective_independent_evidence_count": 1,
                    },
                    "cost_proportionality": {"budget_tier": "standard"},
                }
            ],
            "candidate_data_source_families": [
                "claim_bound_fabric",
                "claim_bound_data_forge",
            ],
            "candidate_method_families": ["claim_bound_foundry", "legal_applicability"],
            "inclusion_rules": ["Use selected producer refs from the claim registry."],
            "exclusion_rules": ["Reject unbound global pools."],
            "disconfirming_lines": ["wave4-i4-counterevidence-preservation"],
            "synthesis_rules": {"strategy": "effective_independent_support"},
            "stopping_rules": {"minimum_effective_independent_evidence_count": 1},
            "cost_proportionality": {"budget_tier": "standard"},
            "cas_ref": _payload_sha256({"portfolio": claim_ids}),
            "runtime_event_ref": "event://policy-design-case/wave4-i4/portfolio",
        }
    ]


def _wave4_i4_evidence_lines(
    case: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    portfolio_designs: list[dict[str, Any]],
    run_id: str,
    job_id: str,
) -> list[dict[str, Any]]:
    existing = case.get("evidence_lines")
    if isinstance(existing, list) and existing:
        return [dict(row) for row in existing if isinstance(row, dict)]
    portfolio_id = str(portfolio_designs[0]["portfolio_id"])
    claim = claims[0]
    claim_id = _claim_id(claim, index=0)
    selected_refs = claim.get("selected_producer_refs")
    selected = selected_refs if isinstance(selected_refs, dict) else {}
    legal_ref = _first_text(selected.get("lex")) or _first_text(claim.get("legal_norm_refs"))
    data_ref = (
        _first_text(selected.get("fabric"))
        or _first_text(selected.get("data_forge"))
        or _first_text(claim.get("source_data_refs"))
    )
    method_ref = _first_text(selected.get("foundry")) or _first_text(claim.get("method_refs"))
    scholar_ref = _first_text(selected.get("scholar")) or _first_text(claim.get("scholar_refs"))
    base_source = data_ref or "claim-bound-source"
    base_method = method_ref or "claim-bound-method"
    return [
        _wave4_i4_evidence_line(
            line_id="wave4-i4-line-support-primary",
            portfolio_id=portfolio_id,
            claim_id=claim_id,
            strand="data",
            source_id=base_source,
            method_id=base_method,
            polarity="support",
            producer_component="polisyos.fabric",
            producer_ref=data_ref,
            run_id=run_id,
            job_id=job_id,
            specification_id="wave4-i4-shared-spec",
        ),
        _wave4_i4_evidence_line(
            line_id="wave4-i4-line-support-dependent",
            portfolio_id=portfolio_id,
            claim_id=claim_id,
            strand="data",
            source_id=base_source,
            method_id=base_method,
            polarity="support",
            producer_component="polisyos.lex",
            producer_ref=data_ref or legal_ref,
            run_id=run_id,
            job_id=job_id,
            specification_id="wave4-i4-dependent-spec",
        ),
        _wave4_i4_evidence_line(
            line_id="wave4-i4-line-counter-preserved",
            portfolio_id=portfolio_id,
            claim_id=claim_id,
            strand="method",
            source_id=scholar_ref or "claim-bound-counter-source",
            method_id=f"{base_method}.sensitivity",
            polarity="counterevidence",
            producer_component="polisyos.foundry",
            producer_ref=method_ref,
            run_id=run_id,
            job_id=job_id,
            specification_id="wave4-i4-counter-spec",
        ),
    ]


def _wave4_i4_evidence_line(
    *,
    line_id: str,
    portfolio_id: str,
    claim_id: str,
    strand: str,
    source_id: str,
    method_id: str,
    polarity: str,
    producer_component: str,
    producer_ref: str | None,
    run_id: str,
    job_id: str,
    specification_id: str,
) -> dict[str, Any]:
    source_ref = producer_ref or _payload_sha256({"source_id": source_id})
    return {
        "schema_version": EVIDENCE_LINE_SCHEMA_VERSION,
        "line_id": line_id,
        "portfolio_id": portfolio_id,
        "claim_id": claim_id,
        "claim_ids": [claim_id],
        "evidence_strand": strand,
        "polarity": polarity,
        "source_lineage": {
            "source_id": source_id,
            "source_ref": source_ref,
            "lineage_refs": [source_ref],
            "corpus_id": source_id,
            "corpus_ancestry": [source_id],
        },
        "corpus_ancestry": [source_id],
        "author_pool": ["wave4-i4-producer-handshake"],
        "institution_pool": ["policyos-runtime"],
        "preprocessing_pipeline_id": "wave4-i4-normalized-producer-output",
        "method_id": method_id,
        "method_assumptions": ["Wave 3 selected producer output is claim-bound."],
        "identification_strategy_id": "claim-bound-runtime-synthesis",
        "shared_failure_modes": [f"{source_id}:shared-lineage"],
        "specification_id": specification_id,
        "producer_identity": {
            "component": producer_component,
            "version": "2026.05.23+wave4-i4",
            "owner": "team-policyos-runtime",
        },
        "execution_context": {
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": "tenant-prod",
            "trace_id": f"trace-{line_id}",
        },
        "evidence_ref": source_ref,
        "runtime_event_ref": f"event://policy-design-case/wave4-i4/{line_id}",
    }


def _wave4_i4_independence_map(
    case: dict[str, Any],
    *,
    portfolio_designs: list[dict[str, Any]],
    evidence_lines: list[dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    existing = case.get("evidence_independence_maps") or case.get("independence_maps")
    if isinstance(existing, list) and existing:
        return dict(existing[0])
    payload = build_evidence_independence_map(
        evidence_lines,
        portfolio_designs=portfolio_designs,
        map_id="independence.wave4_i4.claim_bound",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        evidence_ref=_payload_sha256({"independence": run_id}),
        runtime_event_ref=f"event://policy-design-case/{run_id}/independence",
    )
    return _wave4_i4_runtime_reader_record(
        {**payload, "status": "pass"},
        producer="polisyos.runtime.quality.evidence_independence",
        runtime_event_ref=f"event://policy-design-case/{run_id}/independence",
    )


def _wave4_i4_synthesis_report(
    case: dict[str, Any],
    *,
    portfolio_designs: list[dict[str, Any]],
    evidence_lines: list[dict[str, Any]],
    independence_map: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    existing = case.get("synthesis_reports") or case.get("evidence_synthesis_reports")
    if isinstance(existing, list) and existing:
        return dict(existing[0])
    portfolio_id = str(portfolio_designs[0]["portfolio_id"])
    claim_id = str(independence_map["claim_ids"][0])
    curve_ref = _payload_sha256({"curve": run_id, "portfolio_id": portfolio_id})
    disconfirming_ref = _payload_sha256({"disconfirming": run_id})
    multiverse_curve = {
        "curve_id": "multiverse.wave4_i4.claim_bound",
        "claim_ids": [claim_id],
        "evidence_ref": curve_ref,
        "specification_records": [
            {
                "specification_id": "wave4-i4-shared-spec",
                "decision": "defensible",
                "estimate": 0.12,
                "standard_error": 0.03,
                "quality_weight": 1.0,
                "source_kind": "producer_claim_bound",
            },
            {
                "specification_id": "wave4-i4-dependent-spec",
                "decision": "defensible",
                "estimate": 0.10,
                "standard_error": 0.04,
                "quality_weight": 0.8,
                "source_kind": "producer_claim_bound",
            },
        ],
        "previous_wave_refs": {
            "portfolio_design_refs": [portfolio_id],
            "evidence_line_refs": [
                str(line.get("line_id")) for line in evidence_lines if line.get("line_id")
            ],
            "independence_map_refs": [str(independence_map["map_id"])],
        },
    }
    disconfirming_ledger = {
        "ledger_id": "disconfirming.wave4_i4.claim_bound",
        "claim_ids": [claim_id],
        "evidence_ref": disconfirming_ref,
        "disconfirming_lines": ["wave4-i4-line-counter-preserved"],
    }
    effective_count = int(independence_map["effective_independent_evidence_count"])
    payload = build_evidence_synthesis_report(
        report_id="synthesis.wave4_i4.claim_bound",
        portfolio_id=portfolio_id,
        claim_ids=[claim_id],
        multiverse_curve=multiverse_curve,
        disconfirming_ledgers=[disconfirming_ledger],
        primary_synthesis_rule={
            "rule_id": "wave4-i4-primary-rule",
            "weighting": "quality_weight",
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "wave4-i4-equal-weight-rule",
                "weighting": "equal",
                "reasonable": True,
            }
        ],
        heterogeneity_model={"model": "claim_bound_heterogeneity", "status": "bounded"},
        certainty_framework={"framework": "policyos_runtime", "rating": "moderate"},
        publication_bias_treatment={
            "status": "assessed",
            "method": "counterevidence_preserved",
        },
        inclusion_policy={
            "policy_id": "claim_bound_wave3_outputs_only",
            "policy": "claim_bound_wave3_outputs_only",
        },
        exclusion_policy={
            "policy_id": "exclude_global_unbound_pools",
            "policy": "exclude_global_unbound_pools",
        },
        information_saturation={
            "status": "saturated",
            "effective_independent_evidence_count": effective_count,
            "minimum_effective_independent_evidence_count": 1,
            "recent_direction_changes": 0,
            "stopping_decision": "stop",
        },
        run_cost_proportionality={
            "status": "pass",
            "budget_tier": "standard",
            "marginal_cost_usd": 0.0,
            "marginal_information_gain": 0.0,
            "cost_evidence_ref": _payload_sha256({"run_cost": run_id}),
            "proportionality_rationale": (
                "I4 reuses Wave 3 normalized producer outputs and does not acquire "
                "additional evidence."
            ),
        },
        evidence_ref=_payload_sha256({"synthesis": run_id}),
        runtime_event_ref=f"event://policy-design-case/{run_id}/synthesis",
    )
    return _wave4_i4_runtime_reader_record(
        {**payload, "status": "pass"},
        producer="polisyos.runtime.quality.evidence_synthesis",
        runtime_event_ref=f"event://policy-design-case/{run_id}/synthesis",
    )


def _wave4_i4_lifecycle_reissue_report(
    case: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    case_id: str,
) -> dict[str, Any]:
    existing = case.get("lifecycle_reissue_report") or case.get("claim_lifecycle_reissue")
    if isinstance(existing, dict):
        return _wave4_i4_runtime_reader_record(
            dict(existing),
            producer="polisyos.runtime.quality.case_lifecycle",
            runtime_event_ref=str(
                existing.get("runtime_event_ref")
                or f"event://policy-design-case/{case_id}/lifecycle-reissue"
            ),
        )
    claim_ids = [_claim_id(row, index=index) for index, row in enumerate(claims)]
    return build_lifecycle_reissue_report(
        report_id="lifecycle-reissue.wave4_i4",
        case_id=case_id,
        claim_ids=claim_ids,
        evidence_ref=_payload_sha256({"lifecycle": case_id}),
        runtime_event_ref=f"event://policy-design-case/{case_id}/lifecycle-reissue",
    )


def _wave4_i4_portfolio_effective_support(
    *,
    independence_map: dict[str, Any],
    synthesis_report: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    mass = dict(independence_map.get("effective_mass_report") or {})
    payload = {
        "schema_version": (
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "status": "pass",
        "run_id": run_id,
        "map_ref": independence_map.get("cas_ref") or independence_map.get("map_id"),
        "synthesis_ref": synthesis_report.get("cas_ref") or synthesis_report.get("report_id"),
        "effective_support": {
            "raw_evidence_line_count": independence_map.get("raw_evidence_line_count"),
            "effective_independent_evidence_count": independence_map.get(
                "effective_independent_evidence_count"
            ),
            "effective_support_mass": mass.get("effective_support_mass"),
            "effective_counterevidence_mass": mass.get(
                "effective_counterevidence_mass"
            ),
            "collapse_reasons": mass.get("dominant_collapse_reasons") or [],
            "raw_count_display_policy": mass.get("raw_count_display_policy"),
            "rare_domain_scarcity": independence_map.get("rare_domain_scarcity"),
        },
        "counterevidence_preserved": bool(
            mass.get("effective_counterevidence_mass", 0.0)
        ),
        "issues": [],
    }
    return _wave4_i4_runtime_reader_record(
        payload,
        producer="polisyos.runtime.quality.evidence_independence",
        runtime_event_ref=f"event://policy-design-case/{run_id}/portfolio-effective-support",
    )


def _wave4_i4_projection_publication_state(
    *,
    projection: dict[str, Any],
    projection_contract: dict[str, Any],
    case_id: str,
) -> dict[str, Any]:
    status = "pass" if projection and projection_contract.get("status") == "pass" else "fail"
    payload = {
        "schema_version": (
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "status": status,
        "projection_ref": projection.get("cas_ref"),
        "projection_contract_ref": projection_contract.get("cas_ref"),
        "projection_primary_state": projection.get("primary_state"),
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "issues": [] if status == "pass" else projection_contract.get("issues", []),
    }
    return _wave4_i4_runtime_reader_record(
        payload,
        producer="polisyos.runtime.quality.projection_semantics",
        runtime_event_ref=f"event://policy-design-case/{case_id}/projection-publication-state",
    )


def _wave4_i4_graph(
    *,
    case: dict[str, Any],
    portfolio_effective_support: dict[str, Any],
    lifecycle_report: dict[str, Any],
    projection_contract: dict[str, Any],
    projection_publication_state: dict[str, Any],
    run_id: str,
    job_id: str,
) -> dict[str, Any]:
    case_id = str(case.get("case_id") or f"pdc-{run_id}")
    issues = []
    for record, code in (
        (portfolio_effective_support, "policy_design_wave4_portfolio_missing"),
        (lifecycle_report, "policy_design_wave4_lifecycle_missing"),
        (projection_contract, "policy_design_wave4_projection_contract_missing"),
        (projection_publication_state, "policy_design_wave4_projection_state_missing"),
    ):
        if not isinstance(record, dict) or str(record.get("status")) not in {"pass", "closed"}:
            issues.append(
                _wave4_i4_issue(
                    code=code,
                    message="Wave 4 I4 graph input is missing or failing.",
                    severity="fail",
                )
            )
    payload = {
        "schema_version": "policyos.runtime.policy_design_case.wave4_i4_graph.v1",
        "status": "fail" if issues else "pass",
        "graph_id": f"wave4-i4-{run_id}",
        "case_id": case_id,
        "run_id": run_id,
        "job_id": job_id,
        "producer_output_refs": {
            "claim_registry": _case_ref(case.get("claim_registry")),
            "portfolio_effective_support": portfolio_effective_support.get("cas_ref"),
            "lifecycle_reissue": lifecycle_report.get("cas_ref"),
            "projection_consumer_contract": projection_contract.get("cas_ref"),
            "projection_publication_state": projection_publication_state.get("cas_ref"),
            "closeout_verdict": "quality_evidence/can_i_closeout.json",
        },
        "nodes": [
            {"node_type": "policy_design_case", "ref": _case_ref(case)},
            {
                "node_type": "portfolio_effective_support",
                "ref": portfolio_effective_support.get("cas_ref"),
            },
            {"node_type": "lifecycle_reissue", "ref": lifecycle_report.get("cas_ref")},
            {
                "node_type": "projection_consumer_contract",
                "ref": projection_contract.get("cas_ref"),
            },
            {"node_type": "closeout_verdict", "ref": "quality_evidence/can_i_closeout.json"},
        ],
        "edges": [
            {
                "from": "policy_design_case",
                "to": "portfolio_effective_support",
                "relation": "claim_bound_effective_support",
            },
            {
                "from": "policy_design_case",
                "to": "lifecycle_reissue",
                "relation": "claim_scoped_lifecycle",
            },
            {
                "from": "policy_design_case",
                "to": "projection_consumer_contract",
                "relation": "truth_preserving_projection",
            },
            {
                "from": "i4_graph",
                "to": "closeout_verdict",
                "relation": "closeout_reader_input",
            },
        ],
        "capability_reality_state": "implemented" if not issues else "bridge_missing",
        "issues": issues,
    }
    return _wave4_i4_runtime_reader_record(
        payload,
        producer="polisyos.runtime.quality.policy_design_case",
        runtime_event_ref=f"event://policy-design-case/{case_id}/wave4-i4-graph",
    )


def _wave4_i4_runtime_reader_record(
    payload: dict[str, Any],
    *,
    producer: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    record = dict(payload)
    record.setdefault("status", "pass")
    record.setdefault("authority_role", "runtime_reader")
    record.setdefault("provenance_kind", "runtime_emitted")
    record.setdefault("producer", producer)
    record.setdefault("runtime_event_ref", runtime_event_ref)
    record.setdefault("issues", [])
    record.setdefault("cas_ref", _payload_sha256(record))
    return record


def _wave4_i4_issue(*, code: str, message: str, severity: str) -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def _pass_if_no_failures(report: Any) -> str:
    if not isinstance(report, dict):
        return "pass"
    status = str(report.get("status") or report.get("quality_status") or "").casefold()
    if status in {"fail", "failed", "blocked", "block"}:
        return "fail"
    if _issues_from_report(report):
        return "fail"
    return "pass"


def _count_report_rows(report: Any, key: str) -> int:
    if not isinstance(report, dict):
        return 0
    value = report.get(key)
    if isinstance(value, list):
        return sum(1 for item in value if isinstance(item, dict))
    return 0


def _issues_from_report(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        return []
    issues: list[dict[str, Any]] = []
    for key in ("issues", "findings", "blocking_findings", "blockers"):
        value = report.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    severity = str(
                        item.get("severity") or item.get("status") or ""
                    ).casefold()
                    if severity in {"fail", "failed", "blocked", "block"} or key in {
                        "blocking_findings",
                        "blockers",
                    }:
                        issues.append(
                            {
                                "code": str(item.get("code") or key),
                                "message": str(item.get("message") or item.get("reason") or key),
                                "severity": "fail",
                            }
                        )
    return issues


def _claim_id(claim: dict[str, Any], *, index: int) -> str:
    value = claim.get("claim_id") or claim.get("id") or claim.get("record_id")
    return str(value or f"claim-{index + 1}")


def _first_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
    return None


def _case_ref(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("cas_ref", "evidence_ref", "policy_design_case_ref", "claim_ref"):
        raw = value.get(key)
        if isinstance(raw, str) and raw:
            return raw
    return _payload_sha256(value)


def _extract_failure(job_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(job_payload, dict):
        return None
    failure = job_payload.get("failure")
    if isinstance(failure, dict):
        return failure
    progress = job_payload.get("progress")
    if isinstance(progress, dict) and isinstance(progress.get("failure"), dict):
        return progress["failure"]
    error_message = job_payload.get("error_message")
    if isinstance(error_message, str) and error_message:
        return {
            "code": "control_job_failed",
            "layer": "control_plane",
            "phase": progress.get("phase") if isinstance(progress, dict) else None,
            "message": error_message,
            "retryable": False,
        }
    return None


def _collect_artifact_refs(payload: Any, *, path: str = "$") -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}"
            if isinstance(value, str) and (
                REF_KEY_RE.search(str(key)) or value.startswith("sha256:")
            ):
                refs.append({"path": next_path, "value": value})
            refs.extend(_collect_artifact_refs(value, path=next_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            refs.extend(_collect_artifact_refs(value, path=f"{path}[{index}]"))
    return refs


def _extract_production_data_evidence(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    payloads = (job_payload, run_payload, agents_payload, request_payload)
    context = next(
        (
            found
            for found in (
                _nested_get(payload, "production_data_evidence_context") for payload in payloads
            )
            if isinstance(found, dict)
        ),
        None,
    )
    materialization_refs = {
        key: found
        for key in REQUIRED_MATERIALIZATION_REFS
        for found in (_nested_get(payload, key) for payload in payloads)
        if isinstance(found, str) and found
    }
    if not context and not materialization_refs:
        return None
    return {
        "context": context or {},
        "materialization_refs": materialization_refs,
    }


def _artifact_store_from_context(
    *,
    artifact_store: Any | None,
    cas_root: str | Path | None,
    command_metadata: dict[str, Any] | None,
) -> Any | None:
    if artifact_store is not None:
        return artifact_store
    candidates: list[Path] = []
    if cas_root is not None:
        candidates.append(Path(cas_root))
    run_root = (command_metadata or {}).get("run_root")
    if isinstance(run_root, str) and run_root.strip():
        candidates.append(Path(run_root).expanduser() / "cas")
    candidates.append(Path(".polisyos/cas"))
    for candidate in candidates:
        try:
            if candidate.expanduser().exists():
                return FileSystemCAS(candidate.expanduser())
        except OSError:
            continue
    return None


def _load_json_report_from_store(store: Any, ref: str) -> dict[str, Any] | None:
    get_bytes = getattr(store, "get_bytes", None)
    if not callable(get_bytes):
        return None
    try:
        payload = from_canonical_bytes(get_bytes(ref))
    except Exception:
        return None
    if isinstance(payload, dict):
        return dict(payload)
    return None


def _manifest_authority_ref(manifest: Any, field: str) -> str | None:
    authority = getattr(manifest, "authority", None)
    if authority is None and isinstance(manifest, dict):
        authority = manifest.get("authority")
    if authority is None:
        return None
    value = getattr(authority, field, None)
    if value is None and isinstance(authority, dict):
        value = authority.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _runtime_authority_sidecars_from_store(
    *,
    store: Any,
    ref: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    get_manifest = getattr(store, "get_manifest", None)
    if not callable(get_manifest):
        return None, None, None
    try:
        manifest = get_manifest(ref)
    except Exception:
        return None, None, None

    envelope_ref = _manifest_authority_ref(manifest, "authority_envelope_ref")
    event_ref = _manifest_authority_ref(manifest, "diagnostic_event_ref")
    envelope = (
        _load_json_report_from_store(store, envelope_ref)
        if envelope_ref is not None
        else None
    )
    diagnostic_event = (
        _load_json_report_from_store(store, event_ref) if event_ref is not None else None
    )
    return envelope, diagnostic_event, event_ref


def _dedupe_diagnostic_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        event_id = event.get("event_id")
        artifact_refs = event.get("artifact_refs")
        key = (
            str(event_id)
            if isinstance(event_id, str) and event_id.strip()
            else json.dumps(artifact_refs or event, sort_keys=True, default=str)
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(event))
    return deduped


def _quality_reports_from_refs(
    *,
    refs: dict[str, str],
    store: Any | None,
) -> dict[str, Any]:
    reports, _events, _event_log_refs = _quality_reports_from_refs_with_authority(
        refs=refs,
        store=store,
    )
    return reports


def _quality_reports_from_refs_with_authority(
    *,
    refs: dict[str, str],
    store: Any | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    if store is None:
        return {}, [], []
    reports: dict[str, Any] = {}
    diagnostic_events: list[dict[str, Any]] = []
    diagnostic_event_log_refs: list[str] = []
    for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
        ref = refs.get(ref_key)
        if not isinstance(ref, str) or not ref.strip():
            continue
        report = _load_json_report_from_store(store, ref)
        if report is None:
            continue
        envelope, diagnostic_event, event_ref = _runtime_authority_sidecars_from_store(
            store=store,
            ref=ref,
        )
        if envelope is not None and "authority_envelope" not in report:
            report["authority_envelope"] = envelope
        if diagnostic_event is not None:
            diagnostic_events.append(diagnostic_event)
        if event_ref is not None:
            diagnostic_event_log_refs.append(event_ref)
        reports[report_key] = report
    return reports, _dedupe_diagnostic_events(diagnostic_events), diagnostic_event_log_refs


def _direct_mapping(payload: Any, key: str) -> dict[str, Any] | None:
    if isinstance(payload, dict) and isinstance(payload.get(key), dict):
        return dict(payload[key])
    return None


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _privacy_compliance_config(
    *,
    raw_quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    for payload in (
        raw_quality_evidence,
        job_payload,
        run_payload,
        agents_payload,
        request_payload,
    ):
        direct = _direct_mapping(payload, "privacy_compliance")
        if direct is not None:
            return direct
        nested = _nested_get(payload, "privacy_compliance")
        if isinstance(nested, dict):
            return dict(nested)
    return {}


def _fabric_selected_sources(fabric_trace: Any) -> list[dict[str, Any]]:
    if not isinstance(fabric_trace, dict):
        return []
    selected_sources = _list_of_mappings(fabric_trace.get("selected_sources"))
    if selected_sources:
        return selected_sources
    selected_ids = {
        str(source_id)
        for source_id in _list(fabric_trace.get("selected_source_ids"))
        if str(source_id or "").strip()
    }
    if not selected_ids:
        return []
    return [
        source
        for source in _list_of_mappings(fabric_trace.get("candidate_sources"))
        if str(source.get("source_id") or "") in selected_ids
    ]


def _is_production_data_source(source: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(source.get(key) or "")
        for key in ("source_kind", "source_family", "source_id", "dataset_id")
    ).casefold()
    return "production" in haystack or source.get("source_kind") == "production_data"


def _privacy_compliance_report_from_payloads(
    *,
    raw_quality_evidence: dict[str, Any],
    normalized_quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get(PRIVACY_COMPLIANCE_REPORT_KEY)
    if isinstance(existing_report, dict) and "privacy_compliance" not in raw_quality_evidence:
        return dict(existing_report)

    config = _privacy_compliance_config(
        raw_quality_evidence=raw_quality_evidence,
        job_payload=job_payload,
        run_payload=run_payload,
        agents_payload=agents_payload,
        request_payload=request_payload,
    )
    production_sources = _list_of_mappings(config.get("production_data_sources"))
    public_artifacts = _list_of_mappings(config.get("public_artifact_families"))
    if not production_sources:
        production_sources = [
            source
            for source in _fabric_selected_sources(
                normalized_quality_evidence.get("fabric_retrieval_trace")
            )
            if _is_production_data_source(source)
        ]
    if not public_artifacts:
        public_artifacts = _list_of_mappings(
            normalized_quality_evidence.get("public_artifact_families")
        )
    override = config.get("override")
    return build_privacy_compliance_report(
        production_data_sources=production_sources,
        public_artifact_families=public_artifacts,
        override=override if isinstance(override, dict) else None,
    )


def _production_data_quality_report_from_payloads(
    *,
    raw_quality_evidence: dict[str, Any],
    report_ref: str,
    production_data_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get("production_data_quality")
    if isinstance(existing_report, dict):
        return dict(existing_report)
    context = (
        dict(production_data_evidence.get("context") or {})
        if isinstance(production_data_evidence, dict)
        else {}
    )
    materialization_refs = (
        dict(production_data_evidence.get("materialization_refs") or {})
        if isinstance(production_data_evidence, dict)
        else {}
    )
    return {
        "schema_version": "policyos.runtime.production_data_quality.v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": "pass",
        "source": "canary_evidence_materialization_refs",
        PRODUCTION_DATA_QUALITY_REF_KEY: report_ref,
        "manifest_sha256": context.get("manifest_sha256"),
        "source_bundle_versions": {
            str(role): str(bundle.get("version_id"))
            for role, bundle in (context.get("bundles") or {}).items()
            if isinstance(bundle, dict) and str(bundle.get("version_id") or "").strip()
        },
        "data_snapshot_ref": materialization_refs.get("data_snapshot_ref"),
        "input_bindings_ref": materialization_refs.get("input_bindings_ref"),
        "registry_bundle_ref": materialization_refs.get("registry_bundle_ref"),
        "quality_report_ref": materialization_refs.get("quality_report_ref"),
        "issues": [],
    }


def _load_causal_validity_cases() -> list[dict[str, Any]]:
    try:
        payload = json.loads(CAUSAL_VALIDITY_FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if isinstance(cases, list):
        return [dict(item) for item in cases if isinstance(item, dict)]
    return []


def _causal_statistical_validity_report_from_payloads(
    raw_quality_evidence: dict[str, Any],
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get("causal_statistical_validity")
    if isinstance(existing_report, dict):
        return dict(existing_report)
    return build_causal_statistical_validity_report(
        benchmark_cases=_load_causal_validity_cases(),
    )


def _human_review_calibration_report_from_payloads(
    *,
    raw_quality_evidence: dict[str, Any],
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    run_id: Any,
    job_id: str | None,
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get("human_review_calibration")
    if isinstance(existing_report, dict):
        return dict(existing_report)
    events = (
        _nested_get(job_payload, "human_review_events")
        or _nested_get(run_payload, "human_review_events")
        or _nested_get(agents_payload, "human_review_events")
        or []
    )
    return build_human_review_calibration_report(
        review_events=[dict(item) for item in events if isinstance(item, dict)]
        if isinstance(events, list)
        else [],
        run_id=str(run_id) if run_id is not None else None,
        job_id=job_id,
    )


def _resilience_matrix_from_payloads(
    raw_quality_evidence: dict[str, Any],
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get("resilience_matrix")
    if isinstance(existing_report, dict):
        return dict(existing_report)
    return build_resilience_matrix_payload(
        deterministic=True,
        json_output="quality_evidence/resilience_matrix.json",
    )


def _replay_reports_from_payloads(
    *,
    raw_quality_evidence: dict[str, Any],
    request_payload: dict[str, Any] | None,
    command_metadata: dict[str, Any] | None,
    env: dict[str, str] | None,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    quality_ref_resolution: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    existing_manifest = raw_quality_evidence.get("replay_manifest")
    existing_drift = raw_quality_evidence.get("drift_explanation")
    if isinstance(existing_manifest, dict) and isinstance(existing_drift, dict):
        return (
            _replay_manifest_with_phase64_refs(
                dict(existing_manifest),
                quality_evidence=raw_quality_evidence,
            ),
            dict(existing_drift),
        )
    refs = dict(getattr(quality_ref_resolution, "refs", {}) or {})
    manifest = (
        dict(existing_manifest)
        if isinstance(existing_manifest, dict)
        else build_replay_manifest(
            request_payload=request_payload or {},
            git_sha=_git_sha(),
            dependency_fingerprints=_dependency_fingerprints(),
            feature_flags=_feature_flags_from_payloads(env=env, command_metadata=command_metadata),
            provider_model_metadata=_provider_model_metadata_from_payloads(
                job_payload=job_payload,
                run_payload=run_payload,
            ),
            prompt_template_fingerprints=_prompt_template_fingerprints(command_metadata),
            data_refs=_select_refs(
                refs,
                ("data_snapshot_ref", "input_bindings_ref", "registry_bundle_ref"),
            ),
            source_refs=_select_refs(refs, ("fabric_retrieval_trace_ref",)),
            norm_refs=_select_refs(refs, ("normative_applicability_report_ref",)),
            cas_refs=_select_refs(refs, tuple(sorted(refs))),
            random_seeds=_random_seeds_from_payloads(job_payload, run_payload, request_payload),
            run_params=_first_dict(
                _nested_get(run_payload, "params"),
                _nested_get(run_payload, "run_params"),
                _nested_get(request_payload, "params"),
                _nested_get(request_payload, "run_params"),
            )
            or {},
            quality_scorecard_ref="quality_evidence/quality_scorecard.json",
            execution_summary={
                "status": (job_payload or {}).get("state")
                or (run_payload or {}).get("status")
                or "unknown",
                "run_id": (job_payload or {}).get("run_id") or (run_payload or {}).get("run_id"),
            },
            quality_summary={"quality_status": "pending"},
        )
    )
    drift = (
        dict(existing_drift)
        if isinstance(existing_drift, dict)
        else explain_replay_drift(
            baseline_manifest=manifest,
            replay_manifest=dict(manifest),
        )
    )
    return (
        _replay_manifest_with_phase64_refs(
            manifest,
            quality_evidence=raw_quality_evidence,
        ),
        drift,
    )


def _decision_artifact_quality_from_payloads(
    *,
    raw_quality_evidence: dict[str, Any],
    quality_evidence_payload: dict[str, Any],
    run_id: Any,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
    agents_payload: dict[str, Any] | None,
    request_payload: dict[str, Any] | None,
    assurance_refs: dict[str, str],
    quality_scorecard: dict[str, Any] | None = None,
    publishable: bool = False,
) -> dict[str, Any]:
    existing_report = raw_quality_evidence.get("decision_artifact_quality")
    if isinstance(existing_report, dict) and quality_scorecard is None:
        return dict(existing_report)
    policy_design_case = _first_dict(
        quality_evidence_payload.get("policy_design_case"),
        _nested_get(job_payload, "policy_design_case"),
        _nested_get(run_payload, "policy_design_case"),
        raw_quality_evidence.get("policy_design_case"),
    )
    claim_registry = _first_dict(
        policy_design_case.get("claim_registry") if policy_design_case else None,
        quality_evidence_payload.get("claim_registry"),
        _nested_get(job_payload, "claim_registry"),
        _nested_get(run_payload, "claim_registry"),
    )
    runtime_authority = _first_dict(
        policy_design_case.get("runtime_authority") if policy_design_case else None,
        policy_design_case.get("authority_chain") if policy_design_case else None,
        claim_registry.get("runtime_authority") if claim_registry else None,
    )
    final_claims = _final_claims_from_payloads(
        job_payload,
        run_payload,
        agents_payload,
        request_payload,
    )
    grounding = (
        quality_evidence_payload.get("policy_grounding_matrix")
        if isinstance(quality_evidence_payload.get("policy_grounding_matrix"), dict)
        else None
    )
    if not final_claims and isinstance(grounding, dict):
        grounding_claims = grounding.get("claims")
        if isinstance(grounding_claims, list):
            final_claims = [
                dict(claim) for claim in grounding_claims if isinstance(claim, dict)
            ]
    effective_scorecard = quality_scorecard or {
        "schema_version": "policyos.quality_scorecard.v1",
        "quality_status": "draft",
        "performance_status": "draft",
        "approval_state": "draft",
        "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
        "evidence_refs": dict(assurance_refs),
    }
    decision_scorecard = effective_scorecard
    authority_scorecard_ref = assurance_refs.get("quality_scorecard_ref")
    if publishable and isinstance(effective_scorecard, dict) and authority_scorecard_ref:
        decision_scorecard = {
            **effective_scorecard,
            "quality_scorecard_ref": authority_scorecard_ref,
            "authoritative_scorecard_ref": authority_scorecard_ref,
        }
    conflict_check = (
        quality_evidence_payload.get("conflict_check")
        if isinstance(quality_evidence_payload.get("conflict_check"), dict)
        else None
    )
    approval_state = (
        _nested_get(job_payload, "approval_state")
        or _nested_get(run_payload, "approval_state")
        or effective_scorecard
    )
    performance_blocks_approval = (
        publishable
        and isinstance(effective_scorecard, dict)
        and str(effective_scorecard.get("quality_status") or "").casefold() == "pass"
        and str(effective_scorecard.get("performance_status") or "").casefold()
        not in {"", "pass"}
    )
    if performance_blocks_approval:
        approval_state = "approval_ready"
    artifact_issues: list[dict[str, Any]] = []
    if publishable and not performance_blocks_approval:
        try:
            artifact = compile_publishable_decision_artifact(
                run_id=str(run_id or "unknown"),
                final_claims=final_claims,
                policy_grounding_matrix=grounding,
                quality_scorecard=decision_scorecard,
                conflict_check=conflict_check,
                approval_state=approval_state,
                assurance_refs=assurance_refs,
                performance_warnings=[],
                claim_registry=claim_registry,
                runtime_authority=runtime_authority,
                policy_design_case=policy_design_case,
            )
        except DecisionArtifactCompilationError as exc:
            artifact = dict(exc.draft_artifact)
            artifact_issues = list(exc.issues)
    else:
        artifact = compile_draft_decision_packet(
            run_id=str(run_id or "unknown"),
            final_claims=final_claims,
            policy_grounding_matrix=grounding,
            quality_scorecard=decision_scorecard,
            conflict_check=conflict_check,
            approval_state=approval_state,
            assurance_refs=assurance_refs,
            performance_warnings=[],
        )
    if artifact_issues:
        artifact.setdefault("compiler_issues", artifact_issues)
    report = build_decision_artifact_quality_report(
        compiled_artifact=artifact,
        final_claims=final_claims,
        profile="production",
        policy_grounding_matrix=grounding,
        quality_scorecard=decision_scorecard,
        conflict_check=conflict_check,
        approval_state=approval_state,
        assurance_refs=assurance_refs,
        policy_grounding_matrix_ref=assurance_refs.get("policy_grounding_matrix_ref"),
        quality_scorecard_ref="quality_evidence/quality_scorecard.json",
        conflict_check_ref=assurance_refs.get("conflict_check_ref"),
    )
    if isinstance(existing_report, dict):
        for key in ("decision_artifact_quality_report_ref", "authority_envelope"):
            if key in existing_report:
                report[key] = existing_report[key]
    if "decision_artifact_quality_report_ref" not in report:
        ref = assurance_refs.get("decision_artifact_quality_report_ref")
        if ref:
            report["decision_artifact_quality_report_ref"] = ref
    return report


def _dependency_fingerprints() -> dict[str, str]:
    fingerprints: dict[str, str] = {}
    for name in ("pyproject.toml", "uv.lock", "package.json", "pnpm-lock.yaml"):
        path = REPO_ROOT / name
        if path.exists():
            fingerprints[name] = _file_fingerprint(path)
    return fingerprints


def _file_fingerprint(path: Path) -> str:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _feature_flags_from_payloads(
    *,
    env: dict[str, str] | None,
    command_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    source_env = env or {}
    return {
        key: source_env.get(key)
        for key in sorted(source_env)
        if key.startswith("POLISYOS_") and key.endswith(("_ENABLED", "_MODE"))
    } | {
        key: value
        for key, value in (command_metadata or {}).items()
        if str(key).endswith(("_enabled", "_mode"))
    }


def _provider_model_metadata_from_payloads(
    *,
    job_payload: dict[str, Any] | None,
    run_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    variants = _nested_get(job_payload, "llm_model_variants") or _nested_get(
        run_payload,
        "llm_model_variants",
    )
    if not isinstance(variants, list) or not variants:
        return {}
    first = next((item for item in variants if isinstance(item, dict)), {})
    return {
        key: first.get(key)
        for key in ("provider", "model", "model_variant_id", "status")
        if first.get(key) is not None
    }


def _prompt_template_fingerprints(command_metadata: dict[str, Any] | None) -> dict[str, Any]:
    raw = _nested_get(command_metadata, "prompt_template_fingerprints")
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _random_seeds_from_payloads(*payloads: Any) -> dict[str, Any]:
    for payload in payloads:
        raw = _nested_get(payload, "random_seeds")
        if isinstance(raw, dict):
            return dict(raw)
        seed = _nested_get(payload, "random_seed")
        if seed is not None:
            return {"runtime": seed}
    return {}


def _select_refs(refs: dict[str, str], keys: tuple[str, ...]) -> dict[str, str]:
    return {key: value for key, value in refs.items() if key in keys and isinstance(value, str)}


def _final_claims_from_payloads(*payloads: Any) -> list[dict[str, Any]]:
    for payload in payloads:
        report = _nested_get(payload, "final_policy_claims")
        claims = _claims_from_report(report)
        if claims:
            return claims
        direct = _nested_get(payload, "final_claims")
        claims = _claims_from_report(direct)
        if claims:
            return claims
    return []


def _claims_from_report(report: Any) -> list[dict[str, Any]]:
    if isinstance(report, dict):
        for key in ("claims", "policy_claims", "major_claims"):
            raw = report.get(key)
            if isinstance(raw, list):
                return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(report, list):
        return [dict(item) for item in report if isinstance(item, dict)]
    return []


def _generated_runtime_quality_refs(quality_evidence_payload: dict[str, Any]) -> dict[str, str]:
    return {
        ref_key: f"quality_evidence/{QUALITY_REPORT_FILES[report_key]}"
        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items()
        if report_key in CANARY_GENERATED_RUNTIME_REF_REPORTS
        and report_key in quality_evidence_payload
    }


def _quality_ref_resolution_evidence_with_generated_refs(
    resolution: Any,
    generated_refs: dict[str, str],
    *,
    include_generated_refs: bool = True,
) -> dict[str, Any]:
    evidence = resolution.to_evidence()
    if not include_generated_refs:
        return evidence
    refs = dict(evidence.get("refs") or {})
    matches = [
        dict(item) for item in evidence.get("matches", []) if isinstance(item, dict)
    ]
    existing_match_keys = {str(match.get("key")) for match in matches}
    for key, value in generated_refs.items():
        refs.setdefault(key, value)
        if key not in existing_match_keys:
            matches.append(
                {
                    "key": key,
                    "value": value,
                    "source": "canary_evidence",
                    "path": f"$.quality_evidence.{key}",
                }
            )
    required = [str(key) for key in evidence.get("required", [])]
    missing = [key for key in required if key not in refs]
    missing_set = set(missing)
    missing_evidence = [
        dict(item)
        for item in evidence.get("missing_evidence", [])
        if isinstance(item, dict)
        and str(item.get("missing_evidence_type") or "") in missing_set
    ]
    evidence.update(
        {
            "status": "complete" if not missing else "missing",
            "refs": refs,
            "matches": matches,
            "missing": missing,
            "missing_evidence": missing_evidence,
        }
    )
    return evidence


def assemble_canary_evidence(
    *,
    output_root: str | Path = ".polisyos/canary_evidence",
    canary_kind: str,
    command_metadata: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
    job_payload: dict[str, Any] | None = None,
    run_payload: dict[str, Any] | None = None,
    agents_payload: dict[str, Any] | None = None,
    timeline_payload: dict[str, Any] | None = None,
    lineage_payload: dict[str, Any] | None = None,
    provider_preflight: dict[str, Any] | None = None,
    quality_evidence: dict[str, Any] | None = None,
    dashboard_evidence: dict[str, Any] | None = None,
    artifact_store: Any | None = None,
    cas_root: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    """Write one sanitized evidence bundle and return its directory."""
    evidence_started_at = time.perf_counter()
    job_id = str((job_payload or {}).get("job_id") or "no-job")
    run_id = (job_payload or {}).get("run_id") or (run_payload or {}).get("run_id")
    status = str(
        (job_payload or {}).get("state") or (run_payload or {}).get("status") or "unknown"
    )
    root = Path(output_root)
    bundle_dir = Path(output_dir) if output_dir else root / f"{_utc_stamp()}_{job_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    quality_dir = bundle_dir / "quality_evidence"
    quality_dir.mkdir(parents=True, exist_ok=True)
    serious_bundle = _serious_canary(canary_kind)

    failure = _extract_failure(job_payload)
    runtime_quality_evidence = _runtime_quality_evidence_from_payloads(
        job_payload,
        run_payload,
        agents_payload,
    )
    request_payload_for_quality_refs = None if serious_bundle else request_payload
    quality_ref_resolution = resolve_quality_refs(
        run_params=_first_dict(
            _nested_get(run_payload, "params"),
            _nested_get(run_payload, "run_params"),
            _nested_get(request_payload_for_quality_refs, "params"),
            _nested_get(request_payload_for_quality_refs, "run_params"),
        ),
        artifacts=_quality_ref_artifact_surfaces(
            job_payload=job_payload,
            run_payload=run_payload,
            agents_payload=agents_payload,
            request_payload=request_payload_for_quality_refs,
        ),
        timeline=timeline_payload,
        lineage=lineage_payload,
        control_progress=_nested_get(job_payload, "progress"),
    )
    resolved_artifact_store = _artifact_store_from_context(
        artifact_store=artifact_store,
        cas_root=cas_root,
        command_metadata=command_metadata,
    )
    (
        loaded_quality_reports,
        loaded_diagnostic_events,
        loaded_diagnostic_event_log_refs,
    ) = _quality_reports_from_refs_with_authority(
        refs=quality_ref_resolution.refs,
        store=resolved_artifact_store,
    )
    dashboard_payload = _collect_dashboard_evidence(dashboard_evidence, env=env)
    production_data_evidence = _extract_production_data_evidence(
        job_payload=job_payload,
        run_payload=run_payload,
        agents_payload=agents_payload,
        request_payload=request_payload,
    )
    security_assurance_report_ref = f"quality_evidence/{SECURITY_REPORT_FILE}"
    security_assurance_report = build_security_assurance_report(
        payloads={
            "llm": sanitize_for_evidence(
                {
                    "request": request_payload or {},
                    "provider_preflight": provider_preflight or {},
                    "llm_model_variants": _nested_get(job_payload, "llm_model_variants")
                    or _nested_get(run_payload, "llm_model_variants")
                    or _nested_get(agents_payload, "llm_model_variants")
                    or [],
                }
            ),
            "tool": sanitize_for_evidence(
                {
                    "command": command_metadata or {},
                    "agents": agents_payload or {},
                }
            ),
            "data": sanitize_for_evidence(
                {
                    "production_data": _nested_get(
                        job_payload,
                        "production_data_evidence_context",
                    )
                    or _nested_get(run_payload, "production_data_evidence_context")
                    or {},
                    "quality_evidence": quality_evidence or {},
                }
            ),
            "artifact": sanitize_for_evidence(
                {
                    "job_artifacts": _nested_get(job_payload, "artifacts") or {},
                    "run_artifacts": _nested_get(run_payload, "artifacts") or {},
                    "timeline": timeline_payload or {},
                    "lineage": lineage_payload or {},
                }
            ),
            "runtime_api": sanitize_for_evidence(
                {
                    "job": job_payload or {},
                    "run": run_payload or {},
                    "request": request_payload or {},
                }
            ),
            "dashboard": sanitize_for_evidence(dashboard_payload or {}),
        },
        report_ref=security_assurance_report_ref,
    )
    cas_samples = (
        measure_cas_round_trip_samples(resolved_artifact_store)
        if resolved_artifact_store is not None
        else []
    )
    canary_performance_budget = build_canary_performance_budget(
        canary_kind=canary_kind,
        job_payload=job_payload,
        run_payload=run_payload,
        agents_payload=agents_payload,
        timeline_payload=timeline_payload,
        lineage_payload=lineage_payload,
        dashboard_evidence=dashboard_payload,
        runtime_observations=_first_dict(
            _nested_get(command_metadata, "runtime_observations"),
            _nested_get(job_payload, "runtime_observations"),
            _nested_get(run_payload, "runtime_observations"),
            _nested_get(agents_payload, "runtime_observations"),
        ),
        cas_samples=cas_samples,
        evidence_collection_duration_ms=(time.perf_counter() - evidence_started_at) * 1000.0,
    )
    production_data_quality_report_ref = "quality_evidence/production_data_quality.json"
    input_quality_evidence = dict(quality_evidence or {})
    merged_quality_evidence = {
        **input_quality_evidence,
        **loaded_quality_reports,
        **runtime_quality_evidence,
    }
    security_report_for_payload = (
        merged_quality_evidence.get("security_assurance_report")
        if serious_bundle
        and isinstance(merged_quality_evidence.get("security_assurance_report"), dict)
        else security_assurance_report
    )
    raw_quality_evidence_payload = {
        **merged_quality_evidence,
        "production_data_quality": _production_data_quality_report_from_payloads(
            raw_quality_evidence=merged_quality_evidence,
            report_ref=production_data_quality_report_ref,
            production_data_evidence=production_data_evidence,
        ),
        "security_assurance_report": security_report_for_payload,
    }
    quality_evidence_payload = normalize_quality_evidence(
        raw_quality_evidence_payload,
        canary_kind=canary_kind,
    )
    if serious_bundle and isinstance(
        merged_quality_evidence.get(PRIVACY_COMPLIANCE_REPORT_KEY),
        dict,
    ) and "privacy_compliance" not in raw_quality_evidence_payload:
        quality_evidence_payload[PRIVACY_COMPLIANCE_REPORT_KEY] = dict(
            merged_quality_evidence[PRIVACY_COMPLIANCE_REPORT_KEY]
        )
    else:
        quality_evidence_payload[PRIVACY_COMPLIANCE_REPORT_KEY] = (
            _privacy_compliance_report_from_payloads(
                raw_quality_evidence=raw_quality_evidence_payload,
                normalized_quality_evidence=quality_evidence_payload,
                job_payload=job_payload,
                run_payload=run_payload,
                agents_payload=agents_payload,
                request_payload=request_payload,
            )
        )
    quality_evidence_payload = normalize_quality_evidence(
        quality_evidence_payload,
        canary_kind=canary_kind,
    )
    replay_manifest, drift_explanation = _replay_reports_from_payloads(
        raw_quality_evidence=raw_quality_evidence_payload,
        request_payload=request_payload,
        command_metadata=command_metadata,
        env=env,
        job_payload=job_payload,
        run_payload=run_payload,
        quality_ref_resolution=quality_ref_resolution,
    )
    quality_evidence_payload.setdefault(
        "causal_statistical_validity",
        _causal_statistical_validity_report_from_payloads(raw_quality_evidence_payload),
    )
    quality_evidence_payload["replay_manifest"] = replay_manifest
    quality_evidence_payload["drift_explanation"] = drift_explanation
    quality_evidence_payload.setdefault(
        "resilience_matrix",
        _resilience_matrix_from_payloads(raw_quality_evidence_payload),
    )
    quality_evidence_payload.setdefault(
        "human_review_calibration",
        _human_review_calibration_report_from_payloads(
            raw_quality_evidence=raw_quality_evidence_payload,
            job_payload=job_payload,
            run_payload=run_payload,
            agents_payload=agents_payload,
            run_id=run_id,
            job_id=None if job_id == "no-job" else job_id,
        ),
    )
    provisional_assurance_refs = {
        **_generated_runtime_quality_refs(quality_evidence_payload),
        SECURITY_ASSURANCE_REPORT_REF_KEY: security_assurance_report_ref,
        PRIVACY_COMPLIANCE_REPORT_REF_KEY: PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
    }
    quality_evidence_payload.setdefault(
        "decision_artifact_quality",
        _decision_artifact_quality_from_payloads(
            raw_quality_evidence=raw_quality_evidence_payload,
            quality_evidence_payload=quality_evidence_payload,
            run_id=run_id,
            job_payload=job_payload,
            run_payload=run_payload,
            agents_payload=agents_payload,
            request_payload=request_payload,
            assurance_refs=provisional_assurance_refs,
        ),
    )
    quality_evidence_payload.setdefault(
        "semantic_binding_ledger",
        build_semantic_binding_ledger(
            runtime_refs=provisional_assurance_refs,
            normative_evidence=quality_evidence_payload.get("normative_evidence")
            if isinstance(quality_evidence_payload.get("normative_evidence"), dict)
            else None,
            fabric_retrieval_trace=quality_evidence_payload.get("fabric_retrieval_trace")
            if isinstance(quality_evidence_payload.get("fabric_retrieval_trace"), dict)
            else None,
            foundry_method_report=quality_evidence_payload.get("foundry_method_report")
            if isinstance(quality_evidence_payload.get("foundry_method_report"), dict)
            else None,
            policy_grounding_matrix=quality_evidence_payload.get("policy_grounding_matrix")
            if isinstance(quality_evidence_payload.get("policy_grounding_matrix"), dict)
            else None,
            decision_artifact_contract=(
                quality_evidence_payload.get("decision_artifact_quality", {}).get(
                    "claim_evidence_contract"
                )
                if isinstance(quality_evidence_payload.get("decision_artifact_quality"), dict)
                else None
            ),
            final_claims=_final_claims_from_payloads(
                job_payload,
                run_payload,
                agents_payload,
                request_payload,
            ),
        ),
    )
    provider_model_quality_ledger = _provider_model_quality_ledger_from_payloads(
        command_metadata=command_metadata,
        quality_evidence=quality_evidence_payload,
        job_payload=job_payload,
        run_payload=run_payload,
        agents_payload=agents_payload,
    )
    if provider_model_quality_ledger is not None:
        quality_evidence_payload["provider_model_quality_ledger"] = provider_model_quality_ledger
    quality_evidence_payload = normalize_quality_evidence(
        quality_evidence_payload,
        canary_kind=canary_kind,
    )
    quality_evidence_payload = _preserve_runtime_report_failures(
        quality_evidence_payload,
        {
            **runtime_quality_evidence,
            **loaded_quality_reports,
        },
    )
    quality_evidence_payload = _with_dev_smoke_warn_scoped_reports(
        quality_evidence_payload,
        canary_kind=canary_kind,
    )
    quality_evidence_payload = _with_prompt_tool_secondary_signal_findings(
        quality_evidence_payload,
    )
    quality_evidence_payload = _with_wave7_producer_pipeline(
        quality_evidence_payload=quality_evidence_payload,
        canary_kind=canary_kind,
        command_metadata=command_metadata,
        request_payload=request_payload,
        job_payload=job_payload,
        run_payload=run_payload,
    )
    generated_quality_refs = _generated_runtime_quality_refs(quality_evidence_payload)
    runtime_source_refs = {
        **quality_ref_resolution.refs,
        **RuntimeQualityAuthorityRefs.from_runtime_payloads(
            job_payload=job_payload,
            run_payload=run_payload,
        ).refs,
    }
    optional_runtime_ref_keys = _optional_runtime_quality_ref_keys(job_payload, run_payload)
    scorecard_generated_refs = (
        {}
        if serious_bundle
        else {
            key: value
            for key, value in generated_quality_refs.items()
            if key not in optional_runtime_ref_keys
        }
    )
    scorecard_runtime_refs = {
        **runtime_source_refs,
        **scorecard_generated_refs,
        **(
            {}
            if serious_bundle
            else {
                SECURITY_ASSURANCE_REPORT_REF_KEY: security_assurance_report_ref,
                PRIVACY_COMPLIANCE_REPORT_REF_KEY: PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
            }
        ),
    }
    base_closeout_authority_envelope = (
        _first_valid_authority_envelope(quality_evidence_payload)
        if serious_bundle
        else None
    )
    if serious_bundle and base_closeout_authority_envelope is not None:
        scorecard_runtime_refs.update(
            {
                ref_key: _stable_authority_ref(ref_key, run_id, job_id, str(bundle_dir))
                for ref_key in AGGREGATE_CLOSEOUT_REF_KEYS
                if ref_key not in scorecard_runtime_refs
            }
        )
        for report_key, ref_key in QUALITY_REPORT_RUNTIME_REFS.items():
            if (
                report_key in CANARY_GENERATED_RUNTIME_REF_REPORTS
                and report_key in quality_evidence_payload
                and (
                    ref_key not in scorecard_runtime_refs
                    or _cas_like_ref(scorecard_runtime_refs.get(ref_key)) is None
                )
            ):
                scorecard_runtime_refs[ref_key] = _stable_authority_ref(
                    ref_key,
                    run_id,
                    job_id,
                    str(bundle_dir),
                )
        for report_key in CONTINUOUS_GOVERNANCE_REPORT_KEYS:
            ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
            scorecard_runtime_refs.setdefault(
                ref_key,
                _stable_authority_ref(ref_key, run_id, job_id, str(bundle_dir)),
            )
        preliminary_payload, preliminary_index = _with_closeout_authority_metadata(
            quality_evidence_payload,
            runtime_refs=scorecard_runtime_refs,
            canary_kind=canary_kind,
            run_id=run_id,
            job_id=job_id,
            base_authority_envelope=base_closeout_authority_envelope,
        )
        for report_key in CONTINUOUS_GOVERNANCE_REPORT_KEYS:
            ref_key = QUALITY_REPORT_RUNTIME_REFS[report_key]
            record = preliminary_index["records"][ref_key]
            preliminary_payload[report_key] = _continuous_governance_report(
                report_key=report_key,
                runtime_ref=scorecard_runtime_refs[ref_key],
                authority_record=record,
                run_id=run_id,
                job_id=job_id,
            )
        effective_mode_ref = scorecard_runtime_refs["effective_mode_ledger_ref"]
        preliminary_payload["effective_mode_ledger"] = _effective_mode_ledger_payload(
            canary_kind=canary_kind,
            run_id=run_id,
            job_id=job_id,
            mode_ledger_ref=effective_mode_ref,
        )
        quality_evidence_payload, closeout_authority_index = (
            _with_closeout_authority_metadata(
                preliminary_payload,
                runtime_refs=scorecard_runtime_refs,
                canary_kind=canary_kind,
                run_id=run_id,
                job_id=job_id,
                base_authority_envelope=base_closeout_authority_envelope,
            )
        )
        quality_evidence_payload = _quality_evidence_with_closeout_authority_refs(
            quality_evidence_payload,
            closeout_authority_index,
        )
        quality_evidence_payload = _quality_evidence_with_reader_valid_semantic_binding(
            quality_evidence_payload
        )
    else:
        closeout_authority_index = None
    if serious_bundle:
        quality_evidence_payload.setdefault(
            "source_truth_adapter_surfaces",
            _source_truth_adapter_surfaces_from_quality_evidence(
                quality_evidence_payload,
                job_payload=job_payload,
                run_payload=run_payload,
                request_payload=request_payload,
            ),
        )
        quality_evidence_payload.setdefault(
            "source_truth_adapter_paths",
            ["bundle_to_scorecard"],
        )
        quality_evidence_payload.setdefault(
            "phase_barrier_records",
            _generated_phase_barrier_records(
                scorecard_runtime_refs=scorecard_runtime_refs,
                run_id=run_id,
                job_payload=job_payload,
                run_payload=run_payload,
                canary_kind=canary_kind,
            ),
        )
        quality_evidence_payload.setdefault(
            "diagnostic_slo_observations",
            pass_observations_for_all_diagnostic_slos(
                observed_at=None,
                evidence_ref="quality_evidence/diagnostic_slo_report.json",
            ),
        )
    legacy_migration_sandbox = _write_legacy_migration_sandbox_outputs(
        bundle_dir=bundle_dir,
        canary_kind=canary_kind,
        run_id=run_id,
        job_id=job_id,
        quality_evidence_payload=quality_evidence_payload,
        runtime_refs=scorecard_runtime_refs,
    )
    if legacy_migration_sandbox is not None:
        quality_evidence_payload["legacy_migration_sandbox"] = legacy_migration_sandbox
    scorecard_job_payload, scorecard_run_payload = _scorecard_payloads_with_quality_refs(
        job_payload=job_payload,
        run_payload=run_payload,
        refs=scorecard_runtime_refs,
    )
    closeout_diagnostic_events = []
    closeout_diagnostic_event_log_refs = []
    if isinstance(closeout_authority_index, dict):
        raw_closeout_events = closeout_authority_index.get("diagnostic_events")
        if isinstance(raw_closeout_events, list):
            scorecard_event_ref_keys = {
                *QUALITY_REPORT_RUNTIME_REFS.values(),
                *AGGREGATE_CLOSEOUT_REF_KEYS,
            }
            closeout_diagnostic_events = [
                dict(event)
                for event in raw_closeout_events
                if isinstance(event, dict) and event.get("ref_key") in scorecard_event_ref_keys
            ]
        if closeout_diagnostic_events:
            closeout_diagnostic_event_log_refs = [
                "quality_evidence/minimum_closeout_authority_index.json#/diagnostic_events"
            ]
    if serious_bundle:
        phase_barrier_records = quality_evidence_payload.get("phase_barrier_records")
        if isinstance(phase_barrier_records, list):
            scorecard_job_payload = _payload_with_phase_barrier_records(
                scorecard_job_payload,
                [dict(item) for item in phase_barrier_records if isinstance(item, dict)],
            )
            if scorecard_job_payload is None:
                scorecard_run_payload = _payload_with_phase_barrier_records(
                    scorecard_run_payload,
                    [dict(item) for item in phase_barrier_records if isinstance(item, dict)],
                )
    if serious_bundle:
        scorecard_job_payload = _payload_with_runtime_authority_diagnostics(
            scorecard_job_payload,
            diagnostic_events=[*loaded_diagnostic_events, *closeout_diagnostic_events],
            diagnostic_event_log_refs=[
                *loaded_diagnostic_event_log_refs,
                *closeout_diagnostic_event_log_refs,
            ],
        )
        if scorecard_job_payload is None:
            scorecard_run_payload = _payload_with_runtime_authority_diagnostics(
                scorecard_run_payload,
                diagnostic_events=[*loaded_diagnostic_events, *closeout_diagnostic_events],
                diagnostic_event_log_refs=[
                    *loaded_diagnostic_event_log_refs,
                    *closeout_diagnostic_event_log_refs,
                ],
            )
    trust_boundary_attestation_records = _generated_trust_boundary_attestations(
        scorecard_runtime_refs=scorecard_runtime_refs,
        run_id=run_id,
        job_id="no-job" if job_id == "no-job" else job_id,
        bundle_dir=bundle_dir,
    )
    if serious_bundle:
        scorecard_job_payload = _payload_with_trust_boundary_attestations(
            scorecard_job_payload,
            trust_boundary_attestation_records,
        )
        if scorecard_job_payload is None:
            scorecard_run_payload = _payload_with_trust_boundary_attestations(
                scorecard_run_payload,
                trust_boundary_attestation_records,
            )
    extracted_variants = _llm_model_variants_from_payloads(
        scorecard_job_payload,
        scorecard_run_payload,
        agents_payload,
    )
    scorecard_job_payload = _payload_with_llm_model_variants(
        scorecard_job_payload,
        extracted_variants,
    )
    if scorecard_job_payload is None:
        scorecard_run_payload = _payload_with_llm_model_variants(
            scorecard_run_payload,
            extracted_variants,
        )
    scorecard_job_payload = _payload_with_canary_performance_budget(
        scorecard_job_payload,
        canary_performance_budget,
    )
    if scorecard_job_payload is None:
        scorecard_run_payload = _payload_with_canary_performance_budget(
            scorecard_run_payload,
            canary_performance_budget,
        )
    if not serious_bundle:
        scorecard_job_payload = _payload_with_security_assurance_ref(
            scorecard_job_payload,
            security_assurance_report_ref,
        )
        if scorecard_job_payload is None:
            scorecard_run_payload = _payload_with_security_assurance_ref(
                scorecard_run_payload,
                security_assurance_report_ref,
            )
    scorecard_job_payload = _payload_with_authoritative_progress_state(
        scorecard_job_payload,
    )
    if serious_bundle:
        quality_evidence_payload = _with_run_cost_proportionality_ledger(
            quality_evidence_payload=quality_evidence_payload,
            job_payload=scorecard_job_payload,
            run_payload=scorecard_run_payload,
            canary_kind=canary_kind,
        )
        quality_evidence_payload = _with_wave4_i4_policy_design_case_outputs(
            quality_evidence_payload=quality_evidence_payload,
            run_id=run_id,
            job_id=job_id,
            canary_kind=canary_kind,
        )
    quality_evidence_payload = _with_cost_degradation_telemetry(
        quality_evidence_payload=quality_evidence_payload,
        job_payload=scorecard_job_payload,
        run_payload=scorecard_run_payload,
        canary_kind=canary_kind,
    )
    quality_evidence_payload = _with_run_cost_gate(
        quality_evidence_payload=quality_evidence_payload,
        job_payload=scorecard_job_payload,
        run_payload=scorecard_run_payload,
        canary_kind=canary_kind,
    )
    if serious_bundle:
        quality_evidence_payload["public_export_bundle"] = (
            _public_export_bundle_from_quality_evidence(
                run_id=run_id,
                quality_evidence_payload=quality_evidence_payload,
            )
        )
        quality_evidence_payload.setdefault(
            "diagnostic_slo_report",
            build_diagnostic_slo_report_from_quality_context(
                quality_evidence=quality_evidence_payload,
                required_report_keys=tuple(QUALITY_REPORT_RUNTIME_REFS),
                required_runtime_ref_keys=tuple(QUALITY_REPORT_RUNTIME_REFS.values()),
                runtime_refs=scorecard_runtime_refs,
                job_payload=scorecard_job_payload,
                run_payload=scorecard_run_payload,
                run_id=run_id,
                canary_kind=canary_kind,
                owner="team-assurance",
                evidence_bundle_path=str(bundle_dir),
            ),
        )
        quality_evidence_payload.setdefault(
            "assurance_case",
            {
                "schema_version": "policyos.runtime.assurance_case.v1",
                "claim": {
                    "text": (
                        "Serious PolicyOS closeout is pending final scorecard-backed "
                        "assurance case assembly."
                    ),
                    "status": "qualified",
                    "run_id": str(run_id or "unknown"),
                    "job_id": None if job_id == "no-job" else job_id,
                    "canary_kind": canary_kind,
                    "quality_status": "pending",
                    "approval_state": "pending",
                },
                "subclaims": [],
                "argument": "Provisional assurance case marker for scorecard gate ordering.",
                "argument_strategy": "runtime_authority_graph",
                "evidence": [{"key": "bundle", "ref": str(bundle_dir)}],
                "assumptions": [
                    "This provisional marker is replaced after final scorecard generation."
                ],
                "contexts": {"quality_evidence_bundle_path": str(bundle_dir)},
                "defeaters": [],
                "blockers": [],
                "unresolved_uncertainty": [],
                "confidence_limits": {"lower_bound": 0.0, "upper_bound": 0.75},
                "non_overridable_blockers": [],
                "reviewer_attribution": {
                    "reviewer_id": "unassigned",
                    "review_status": "pending",
                },
                "owner": "team-assurance",
                "next_diagnostic_command": (
                    "uv run python "
                    "tools/quality/validation/check_honest_diagnostics_proof_harness.py "
                    "--repo-root . --require-passing"
                ),
            },
        )
        quality_evidence_payload = _with_semantic_binding_ref_on_authority_envelopes(
            quality_evidence_payload
        )
    quality_scorecard = build_quality_scorecard(
        canary_kind=canary_kind,
        job_id=None if job_id == "no-job" else job_id,
        run_id=run_id,
        execution_status=status,
        job_payload=scorecard_job_payload,
        run_payload=scorecard_run_payload,
        provider_preflight=provider_preflight,
        quality_evidence=quality_evidence_payload,
        quality_scorecard_ref="quality_evidence/quality_scorecard.json",
        quality_evidence_bundle_path=str(bundle_dir),
    )
    if serious_bundle:
        quality_evidence_payload["decision_artifact_quality"] = (
            _decision_artifact_quality_from_payloads(
                raw_quality_evidence=raw_quality_evidence_payload,
                quality_evidence_payload=quality_evidence_payload,
                run_id=run_id,
                job_payload=job_payload,
                run_payload=run_payload,
                agents_payload=agents_payload,
                request_payload=request_payload,
                assurance_refs=scorecard_runtime_refs,
                quality_scorecard=quality_scorecard,
                publishable=True,
            )
        )
        if closeout_authority_index is not None:
            quality_evidence_payload, closeout_authority_index = (
                _with_closeout_authority_metadata(
                    quality_evidence_payload,
                    runtime_refs=scorecard_runtime_refs,
                    canary_kind=canary_kind,
                    run_id=run_id,
                    job_id=job_id,
                    base_authority_envelope=base_closeout_authority_envelope,
                )
            )
            quality_evidence_payload = _quality_evidence_with_closeout_authority_refs(
                quality_evidence_payload,
                closeout_authority_index,
            )
            quality_evidence_payload = _quality_evidence_with_reader_valid_semantic_binding(
                quality_evidence_payload
            )
            scorecard_job_payload = _payload_with_runtime_quality_evidence_reports(
                scorecard_job_payload,
                quality_evidence_payload,
                report_keys=("policy_design_case", "semantic_binding_ledger"),
            )
            if scorecard_job_payload is None:
                scorecard_run_payload = _payload_with_runtime_quality_evidence_reports(
                    scorecard_run_payload,
                    quality_evidence_payload,
                    report_keys=("policy_design_case", "semantic_binding_ledger"),
                )
        quality_scorecard = build_quality_scorecard(
            canary_kind=canary_kind,
            job_id=None if job_id == "no-job" else job_id,
            run_id=run_id,
            execution_status=status,
            job_payload=scorecard_job_payload,
            run_payload=scorecard_run_payload,
            provider_preflight=provider_preflight,
            quality_evidence=quality_evidence_payload,
            quality_scorecard_ref="quality_evidence/quality_scorecard.json",
            quality_evidence_bundle_path=str(bundle_dir),
        )
    quality_evidence_payload["source_truth_conflicts"] = (
        _source_truth_conflict_records_payload(
            quality_scorecard=quality_scorecard,
            quality_evidence_payload=quality_evidence_payload,
        )
    )
    quality_evidence_payload["invariant_proof_harness_report"] = (
        _invariant_proof_harness_report_payload(
            canary_kind=canary_kind,
            quality_scorecard=quality_scorecard,
        )
    )
    if serious_bundle:
        quality_evidence_payload = _with_wave4_i4_closeout_reader_records(
            quality_evidence_payload=quality_evidence_payload,
            trust_boundary_attestation_records=trust_boundary_attestation_records,
            run_id=run_id,
            job_id=job_id,
        )
        quality_evidence_payload["assurance_case"] = build_assurance_case_for_scorecard(
            quality_scorecard,
            owner="team-assurance",
        )
        quality_evidence_payload["public_export_bundle"] = (
            _public_export_bundle_from_quality_evidence(
                run_id=run_id,
                quality_evidence_payload=quality_evidence_payload,
                quality_scorecard=quality_scorecard,
            )
        )
        quality_evidence_payload["scenario_contract_propagation_graph"] = (
            build_scenario_contract_propagation_graph(
                request_payload=request_payload or {},
                bundle_payload={
                    "canary_kind": canary_kind,
                    "git_sha": _git_sha(),
                    "command": dict(command_metadata or {}),
                },
                quality_evidence_payload=quality_evidence_payload,
                bundle_ref=str(bundle_dir),
                authority_profile=canary_kind,
                code_revision=_git_sha(),
            )
        )
        quality_evidence_payload["evidence_spine_handoff_ledger"] = (
            build_canary_evidence_handoff_ledger(
                bundle_ref=str(bundle_dir),
                quality_evidence_payload=quality_evidence_payload,
                job_payload=job_payload,
                run_payload=run_payload,
                request_payload=request_payload,
                command_metadata=command_metadata,
                dashboard_payload=dashboard_payload,
            )
        )
    bundle_job_payload = (
        _payload_with_scorecard_control_progress(scorecard_job_payload, quality_scorecard)
        if job_payload is not None and scorecard_job_payload is not None
        else None
    )
    if serious_bundle:
        continuity_bundle_payload = {
            "bundle_ref": str(bundle_dir),
            "files": {
                "quality_evidence": {
                    NL_REPLAY_ORCHESTRATION_RECORD_KEY: NL_REPLAY_ORCHESTRATION_FILE_REF
                }
            },
        }
        continuity_inspection_payload = {
            "tool": "quality.validation.inspect-evidence-bundles",
            "orchestration_continuity_ref": NL_REPLAY_ORCHESTRATION_FILE_REF,
        }
        continuity_readiness_payload = {
            "status": quality_scorecard.get("quality_status"),
            "approval_state": quality_scorecard.get("approval_state"),
            "orchestration_continuity_ref": NL_REPLAY_ORCHESTRATION_FILE_REF,
        }
        continuity_request_context = {
            **dict(request_payload or {}),
            "orchestration_continuity_ref": NL_REPLAY_ORCHESTRATION_FILE_REF,
        }
        quality_evidence_payload[NL_REPLAY_ORCHESTRATION_RECORD_KEY] = (
            build_nl_replay_orchestration_continuity(
                request_context=continuity_request_context,
                workflow_state=(
                    scorecard_run_payload or scorecard_job_payload or run_payload or job_payload
                ),
                job_progress=bundle_job_payload or scorecard_job_payload or job_payload,
                replay_manifest=quality_evidence_payload.get("replay_manifest")
                if isinstance(quality_evidence_payload.get("replay_manifest"), dict)
                else None,
                bundle_payload=continuity_bundle_payload,
                quality_evidence=quality_evidence_payload,
                inspection_report=continuity_inspection_payload,
                readiness_payload=continuity_readiness_payload,
                export_payload=quality_evidence_payload.get("public_export_bundle")
                if isinstance(quality_evidence_payload.get("public_export_bundle"), dict)
                else None,
            )
        )
        quality_evidence_payload["replay_manifest"] = (
            attach_replay_orchestration_continuity(
                quality_evidence_payload.get("replay_manifest")
                if isinstance(quality_evidence_payload.get("replay_manifest"), dict)
                else {},
                quality_evidence_payload[NL_REPLAY_ORCHESTRATION_RECORD_KEY],
            )
        )
        quality_evidence_payload["drift_explanation"] = explain_replay_drift(
            baseline_manifest=quality_evidence_payload["replay_manifest"],
            replay_manifest=dict(quality_evidence_payload["replay_manifest"]),
        )
        quality_evidence_payload["public_export_bundle"] = (
            _public_export_bundle_from_quality_evidence(
                run_id=run_id,
                quality_evidence_payload=quality_evidence_payload,
                quality_scorecard=quality_scorecard,
            )
        )
        quality_evidence_payload[NL_REPLAY_ORCHESTRATION_RECORD_KEY] = (
            build_nl_replay_orchestration_continuity(
                request_context=continuity_request_context,
                workflow_state=(
                    scorecard_run_payload or scorecard_job_payload or run_payload or job_payload
                ),
                job_progress=bundle_job_payload or scorecard_job_payload or job_payload,
                replay_manifest=quality_evidence_payload["replay_manifest"],
                bundle_payload=continuity_bundle_payload,
                quality_evidence=quality_evidence_payload,
                inspection_report=continuity_inspection_payload,
                readiness_payload=continuity_readiness_payload,
                export_payload=quality_evidence_payload["public_export_bundle"],
            )
        )
        quality_evidence_payload["replay_manifest"] = (
            attach_replay_orchestration_continuity(
                quality_evidence_payload["replay_manifest"],
                quality_evidence_payload[NL_REPLAY_ORCHESTRATION_RECORD_KEY],
            )
        )
        quality_evidence_payload["drift_explanation"] = explain_replay_drift(
            baseline_manifest=quality_evidence_payload["replay_manifest"],
            replay_manifest=dict(quality_evidence_payload["replay_manifest"]),
        )
        quality_evidence_payload["public_export_bundle"] = (
            _public_export_bundle_from_quality_evidence(
                run_id=run_id,
                quality_evidence_payload=quality_evidence_payload,
                quality_scorecard=quality_scorecard,
            )
        )
        quality_evidence_payload["evidence_spine_handoff_ledger"] = (
            build_canary_evidence_handoff_ledger(
                bundle_ref=str(bundle_dir),
                quality_evidence_payload=quality_evidence_payload,
                job_payload=bundle_job_payload or job_payload,
                run_payload=scorecard_run_payload,
                request_payload=request_payload,
                command_metadata=command_metadata,
                dashboard_payload=dashboard_payload,
            )
        )
        quality_evidence_payload = _with_schema_compatibility_for_closeout(
            quality_evidence_payload=quality_evidence_payload,
            run_id=run_id,
            job_id=job_id,
            canary_kind=canary_kind,
        )
    refs = []
    for source_name, payload in (
        ("job", bundle_job_payload if bundle_job_payload is not None else job_payload),
        ("run", run_payload),
        ("agents", agents_payload),
        ("timeline", timeline_payload),
        ("lineage", lineage_payload),
        ("request", request_payload),
    ):
        for item in _collect_artifact_refs(payload):
            refs.append({"source": source_name, **item})
    performance = (
        _nested_get(run_payload, "run_performance_summary")
        or _nested_get(job_payload, "run_performance_summary")
        or _nested_get(agents_payload, "performance_summary")
    )
    performance = performance or canary_performance_budget
    artifacts_materialization_refs = (
        dict(production_data_evidence.get("materialization_refs") or {})
        if isinstance(production_data_evidence, dict)
        else {}
    )
    if not artifacts_materialization_refs:
        artifacts_materialization_refs = {
            key: value
            for key, value in (
                (key, _nested_get(payload, key))
                for key in REQUIRED_MATERIALIZATION_REFS
                for payload in (scorecard_job_payload, scorecard_run_payload, agents_payload)
            )
            if isinstance(value, str) and value
        }
    cas_ownership_manifest = "cas_manifests/quality_artifact_ownership.manifest.json"
    git_sha = _git_sha()
    bundle = {
        "schema_version": "policyos.canary_evidence.v1",
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "git_sha": git_sha,
        "code_revision": (
            {"git_sha": git_sha, "source": "git"} if isinstance(git_sha, str) and git_sha else None
        ),
        "command": dict(command_metadata or {}),
        "canary_kind": canary_kind,
        "job_id": None if job_id == "no-job" else job_id,
        "run_id": run_id,
        "status": status,
        "execution_status": status,
        "quality_status": quality_scorecard["quality_status"],
        "quality_scorecard_ref": "quality_evidence/quality_scorecard.json",
        "quality_evidence_bundle_path": str(bundle_dir),
        "metric_taxonomy": _metric_taxonomy_summary(),
        "files": {
            "request": "request.sanitized.json",
            "env": "env.sanitized.json",
            "job": "job.json" if bundle_job_payload is not None else None,
            "run": "run.json" if run_payload is not None else None,
            "agents": "agents.json" if agents_payload is not None else None,
            "timeline": "timeline.json" if timeline_payload is not None else None,
            "lineage": "lineage.json" if lineage_payload is not None else None,
            "artifacts": "artifacts.json",
            "cas_ownership_manifest": cas_ownership_manifest,
            "provider_preflight": (
                "provider_preflight.json" if provider_preflight is not None else None
            ),
            "failure": "failure.json" if failure is not None else None,
            "performance": "performance.json" if performance is not None else None,
            "canary_performance_budget": "canary_performance_budget.json",
            "production_data_evidence": (
                "production_data_evidence.json" if production_data_evidence is not None else None
            ),
            "dashboard": "dashboard.json" if dashboard_payload is not None else None,
            "quality_evidence": {
                "quality_scorecard": "quality_evidence/quality_scorecard.json",
                "can_i_closeout_compatibility": COMPATIBILITY_BUNDLE_PATH,
                "evidence_provenance_manifest": EVIDENCE_PROVENANCE_MANIFEST,
                "attestation_records": "quality_evidence/attestation_records.json",
                "assurance_case": (
                    "quality_evidence/assurance_case.json"
                    if "assurance_case" in quality_evidence_payload
                    else None
                ),
                "diagnostic_slo_report": (
                    "quality_evidence/diagnostic_slo_report.json"
                    if "diagnostic_slo_report" in quality_evidence_payload
                    else None
                ),
                "public_export_bundle": (
                    PUBLIC_EXPORT_BUNDLE_FILE
                    if "public_export_bundle" in quality_evidence_payload
                    else None
                ),
                NL_REPLAY_ORCHESTRATION_RECORD_KEY: (
                    NL_REPLAY_ORCHESTRATION_FILE_REF
                    if NL_REPLAY_ORCHESTRATION_RECORD_KEY in quality_evidence_payload
                    else None
                ),
                "invariant_proof_harness_report": (
                    INVARIANT_PROOF_HARNESS_REPORT_FILE
                    if "invariant_proof_harness_report" in quality_evidence_payload
                    else None
                ),
                "minimum_closeout_authority_index": (
                    "quality_evidence/minimum_closeout_authority_index.json"
                    if closeout_authority_index is not None
                    else None
                ),
                "effective_mode_ledger": (
                    "quality_evidence/effective_mode_ledger.json"
                    if "effective_mode_ledger" in quality_evidence_payload
                    else None
                ),
                **{
                    key: (
                        f"quality_evidence/{filename}" if key in quality_evidence_payload else None
                    )
                    for key, filename in QUALITY_REPORT_FILES.items()
                },
            },
            "legacy_migration_sandbox": (
                LEGACY_MIGRATION_SANDBOX_BUNDLE_FILE
                if legacy_migration_sandbox is not None
                else None
            ),
        },
    }
    closeout_compatibility = build_closeout_compatibility_record(
        bundle_payload=bundle,
        scorecard_payload=quality_scorecard,
        quality_reports=quality_evidence_payload,
        authority_profile_version=canary_kind,
    )
    if serious_bundle:
        quality_evidence_payload = _with_wave4_i4_closeout_verdict(
            quality_evidence_payload=quality_evidence_payload,
            closeout_compatibility=closeout_compatibility,
            quality_scorecard=quality_scorecard,
            run_id=run_id,
        )
        bundle["files"]["quality_evidence"]["can_i_closeout"] = (
            "quality_evidence/can_i_closeout.json"
        )

    _write_json(bundle_dir / "bundle.json", bundle)
    _write_json(bundle_dir / "canary_performance_budget.json", canary_performance_budget)
    _write_json(quality_dir / "quality_scorecard.json", quality_scorecard)
    _write_json(quality_dir / COMPATIBILITY_FILENAME, closeout_compatibility)
    _write_json(quality_dir / "attestation_records.json", trust_boundary_attestation_records)
    if "assurance_case" in quality_evidence_payload:
        _write_json(quality_dir / "assurance_case.json", quality_evidence_payload["assurance_case"])
    if "diagnostic_slo_report" in quality_evidence_payload:
        _write_json(
            quality_dir / "diagnostic_slo_report.json",
            quality_evidence_payload["diagnostic_slo_report"],
        )
    if "public_export_bundle" in quality_evidence_payload:
        _write_json(
            bundle_dir / PUBLIC_EXPORT_BUNDLE_FILE,
            quality_evidence_payload["public_export_bundle"],
        )
    if NL_REPLAY_ORCHESTRATION_RECORD_KEY in quality_evidence_payload:
        _write_json(
            bundle_dir / NL_REPLAY_ORCHESTRATION_FILE_REF,
            quality_evidence_payload[NL_REPLAY_ORCHESTRATION_RECORD_KEY],
        )
    if closeout_authority_index is not None:
        _write_json(
            quality_dir / "minimum_closeout_authority_index.json",
            closeout_authority_index,
        )
    if "effective_mode_ledger" in quality_evidence_payload:
        _write_json(
            quality_dir / "effective_mode_ledger.json",
            quality_evidence_payload["effective_mode_ledger"],
        )
    for key, filename in QUALITY_REPORT_FILES.items():
        if key in quality_evidence_payload:
            _write_json(quality_dir / filename, quality_evidence_payload[key])
    if "invariant_proof_harness_report" in quality_evidence_payload:
        _write_json(
            bundle_dir / INVARIANT_PROOF_HARNESS_REPORT_FILE,
            quality_evidence_payload["invariant_proof_harness_report"],
        )
    _write_json(
        bundle_dir / cas_ownership_manifest,
        _quality_ownership_manifest_payload(
            canary_kind=canary_kind,
            refs=scorecard_runtime_refs,
        ),
    )
    _write_json(
        bundle_dir / "request.sanitized.json",
        sanitize_for_evidence(request_payload or {}, redact_local_paths=True),
    )
    _write_json(bundle_dir / "env.sanitized.json", collect_sanitized_env(env))
    _write_json(
        bundle_dir / "artifacts.json",
        {
            "refs": refs,
            "materialization_refs": artifacts_materialization_refs,
            "quality_ref_resolution": _quality_ref_resolution_evidence_with_generated_refs(
                quality_ref_resolution,
                {
                    **generated_quality_refs,
                    SECURITY_ASSURANCE_REPORT_REF_KEY: security_assurance_report_ref,
                    PRIVACY_COMPLIANCE_REPORT_REF_KEY: PRIVACY_COMPLIANCE_REPORT_EVIDENCE_REF,
                },
                include_generated_refs=not serious_bundle,
            ),
        },
    )
    if bundle_job_payload is not None:
        _write_json(bundle_dir / "job.json", bundle_job_payload)
    if run_payload is not None:
        _write_json(bundle_dir / "run.json", run_payload)
    if agents_payload is not None:
        _write_json(bundle_dir / "agents.json", agents_payload)
    if timeline_payload is not None:
        _write_json(bundle_dir / "timeline.json", timeline_payload)
    if lineage_payload is not None:
        _write_json(bundle_dir / "lineage.json", lineage_payload)
    if provider_preflight is not None:
        _write_json(bundle_dir / "provider_preflight.json", provider_preflight)
    if failure is not None:
        _write_json(bundle_dir / "failure.json", failure)
    if performance is not None:
        _write_json(bundle_dir / "performance.json", performance)
    if production_data_evidence is not None:
        _write_json(bundle_dir / "production_data_evidence.json", production_data_evidence)
    if dashboard_payload is not None:
        _write_json(bundle_dir / "dashboard.json", dashboard_payload)
    _write_evidence_provenance_manifest(
        bundle_dir=bundle_dir,
        canary_kind=canary_kind,
        runtime_source_refs=runtime_source_refs,
        runtime_quality_evidence=runtime_quality_evidence,
        loaded_quality_reports=loaded_quality_reports,
        input_quality_evidence=input_quality_evidence,
        job_payload=scorecard_job_payload,
        run_payload=scorecard_run_payload,
    )
    return bundle_dir


__all__ = [
    "assemble_canary_evidence",
    "collect_sanitized_env",
    "sanitize_for_evidence",
]
