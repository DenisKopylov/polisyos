"""Async handoff ledger for evidence-spine carrier propagation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

EVIDENCE_SPINE_HANDOFF_SCHEMA_VERSION = "policyos.evidence_spine_handoff.v1"
EVIDENCE_SPINE_HANDOFF_LEDGER_SCHEMA_VERSION = "policyos.evidence_spine_handoff_ledger.v1"

REQUIRED_HANDOFF_KINDS = (
    "nl_request_creation",
    "control_plane_job_lease",
    "workflow_state_persistence",
    "cas_artifact_write",
    "canary_bundle_assembly",
    "readiness_result",
)

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "dsn",
        re.compile(
            r"\b(?:postgresql|postgres|mysql|mongodb|redis)://[^\s/]+:[^\s@]+@[^\s]+",
            re.IGNORECASE,
        ),
    ),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{10,}", re.IGNORECASE)),
    (
        "api_key",
        re.compile(
            r"\b(?:sk|pk|ghp|gho|github_pat|AIza|xox[baprs])[-_A-Za-z0-9]{12,}",
            re.IGNORECASE,
        ),
    ),
)
_RAW_TEXT_KEYS = frozenset(
    {
        "raw_prompt",
        "prompt_text",
        "raw_legal_corpus_excerpt",
        "legal_corpus_excerpt",
        "raw_corpus_excerpt",
        "raw_recommendation_body",
        "recommendation_body",
        "draft_recommendation_body",
        "raw_policy_text",
    }
)


class EvidenceSpineHandoffSafetyError(ValueError):
    """Raised when a carrier or handoff payload contains raw sensitive content."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.path = path


@dataclass(frozen=True)
class EvidenceSpineHandoff:
    """One async/batch boundary crossed by an evidence spine carrier."""

    handoff_kind: str
    producer_ref: str
    consumer_ref: str
    parent_spine_ref: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    carrier_ref: str
    handoff_id: str | None = None
    batch_id: str | None = None
    message_count: int | None = None
    carrier_redaction_status: str = "pass"
    integrity_status: str = "pass"
    schema_version: str = EVIDENCE_SPINE_HANDOFF_SCHEMA_VERSION

    def __post_init__(self) -> None:
        payload = {
            "handoff_kind": self.handoff_kind,
            "producer_ref": self.producer_ref,
            "consumer_ref": self.consumer_ref,
            "parent_spine_ref": self.parent_spine_ref,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "carrier_ref": self.carrier_ref,
            "batch_id": self.batch_id,
        }
        assert_carrier_payload_safe(payload)
        handoff_kind = _clean_text(self.handoff_kind)
        if handoff_kind is None:
            raise EvidenceSpineHandoffSafetyError(
                "evidence_spine_handoff_kind_missing",
                "handoff_kind is required.",
            )
        producer_ref = _clean_text(self.producer_ref)
        consumer_ref = _clean_text(self.consumer_ref)
        parent_spine_ref = _clean_text(self.parent_spine_ref)
        carrier_ref = _clean_text(self.carrier_ref)
        input_refs = _text_tuple(self.input_refs)
        output_refs = _text_tuple(self.output_refs)
        message_count = self.message_count
        if message_count is None:
            message_count = max(len(input_refs), len(output_refs), 1)

        object.__setattr__(self, "handoff_kind", handoff_kind)
        object.__setattr__(self, "producer_ref", producer_ref or "")
        object.__setattr__(self, "consumer_ref", consumer_ref or "")
        object.__setattr__(self, "parent_spine_ref", parent_spine_ref or "")
        object.__setattr__(self, "input_refs", input_refs)
        object.__setattr__(self, "output_refs", output_refs)
        object.__setattr__(self, "carrier_ref", carrier_ref or "")
        object.__setattr__(self, "batch_id", _clean_text(self.batch_id))
        object.__setattr__(self, "message_count", max(int(message_count), 0))
        object.__setattr__(
            self,
            "carrier_redaction_status",
            _clean_text(self.carrier_redaction_status) or "pass",
        )
        object.__setattr__(
            self,
            "integrity_status",
            _clean_text(self.integrity_status) or "pass",
        )
        object.__setattr__(self, "handoff_id", _clean_text(self.handoff_id) or _stable_id(payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "handoff_id": self.handoff_id,
            "handoff_kind": self.handoff_kind,
            "producer_ref": self.producer_ref,
            "consumer_ref": self.consumer_ref,
            "parent_spine_ref": self.parent_spine_ref,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "batch_id": self.batch_id,
            "message_count": self.message_count,
            "carrier_ref": self.carrier_ref,
            "carrier_redaction_status": self.carrier_redaction_status,
            "integrity_status": self.integrity_status,
        }


def assert_carrier_payload_safe(payload: Any, *, path: str = "$") -> None:
    """Reject secret-like values and raw text surfaces from handoff carrier payloads."""

    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if key_text.casefold() in _RAW_TEXT_KEYS:
                raise EvidenceSpineHandoffSafetyError(
                    "evidence_spine_carrier_raw_text_forbidden",
                    f"Raw text field {key_text!r} cannot travel in evidence spine handoffs.",
                    path=child_path,
                )
            assert_carrier_payload_safe(value, path=child_path)
        return
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for index, item in enumerate(payload):
            assert_carrier_payload_safe(item, path=f"{path}[{index}]")
        return
    if isinstance(payload, str):
        for code, pattern in _SECRET_PATTERNS:
            if pattern.search(payload):
                raise EvidenceSpineHandoffSafetyError(
                    f"evidence_spine_carrier_{code}_forbidden",
                    f"Secret-like value cannot travel in evidence spine handoffs at {path}.",
                    path=path,
                )


def append_evidence_spine_handoff(
    progress: Mapping[str, Any] | None,
    handoff: EvidenceSpineHandoff | Mapping[str, Any],
) -> dict[str, Any]:
    """Return progress with one idempotently appended handoff record."""

    normalized = dict(progress or {})
    records = [
        dict(item)
        for item in normalized.get("evidence_spine_handoffs", [])
        if isinstance(item, Mapping)
    ]
    record = handoff.to_dict() if isinstance(handoff, EvidenceSpineHandoff) else dict(handoff)
    if not any(item.get("handoff_id") == record.get("handoff_id") for item in records):
        records.append(record)
    normalized["evidence_spine_handoffs"] = records
    normalized["evidence_spine_handoff_count"] = len(records)
    return normalized


def control_plane_handoff(
    *,
    handoff_kind: str,
    job_id: str,
    producer_ref: str,
    consumer_ref: str,
    input_refs: Sequence[Any],
    output_refs: Sequence[Any],
    carrier_ref: str | None = None,
    parent_spine_ref: str | None = None,
    batch_id: str | None = None,
) -> EvidenceSpineHandoff:
    """Build a sanitized control-plane handoff record for job progress."""

    safe_carrier_ref = carrier_ref or f"control-job:{job_id}:carrier"
    return EvidenceSpineHandoff(
        handoff_kind=handoff_kind,
        producer_ref=producer_ref,
        consumer_ref=consumer_ref,
        parent_spine_ref=parent_spine_ref or safe_carrier_ref,
        input_refs=_text_tuple(input_refs) or (f"control-job:{job_id}",),
        output_refs=_text_tuple(output_refs) or (f"control-job:{job_id}:progress",),
        carrier_ref=safe_carrier_ref,
        batch_id=batch_id,
    )


def build_runtime_async_handoff_ledger(
    *,
    job_progress: Mapping[str, Any],
    bundle_ref: str | None,
    carrier_ref: str,
) -> dict[str, Any]:
    """Build a ledger from job progress plus bundle/readiness/CAS refs."""

    parent_spine_ref = (
        _clean_text(job_progress.get("evidence_spine_parent_ref"))
        or _clean_text(carrier_ref)
        or "evidence-spine:unknown"
    )
    handoffs: list[Mapping[str, Any] | EvidenceSpineHandoff] = []
    for item in job_progress.get("evidence_spine_handoffs", []):
        if not isinstance(item, Mapping):
            continue
        record = dict(item)
        record["carrier_ref"] = carrier_ref
        record["parent_spine_ref"] = parent_spine_ref
        handoffs.append(record)
    bundle_output = _clean_text(bundle_ref) or _clean_text(
        job_progress.get("quality_evidence_bundle_path")
    )
    if bundle_output is not None:
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="workflow_state_persistence",
                producer_ref="runtime.nl_pipeline",
                consumer_ref="tools.ops_runners.runtime.canary_evidence",
                parent_spine_ref=parent_spine_ref,
                input_refs=("job.json",),
                output_refs=(bundle_output,),
                carrier_ref=carrier_ref,
            )
        )
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="canary_bundle_assembly",
                producer_ref="tools.ops_runners.runtime.canary_evidence",
                consumer_ref="quality.validation.inspect_evidence_bundles",
                parent_spine_ref=parent_spine_ref,
                input_refs=("job.json",),
                output_refs=(bundle_output,),
                carrier_ref=carrier_ref,
            )
        )
    artifacts = job_progress.get("artifacts")
    cas_ref = None
    if isinstance(artifacts, Mapping):
        cas_ref = _clean_text(artifacts.get("cas_ownership_manifest"))
    if cas_ref is not None:
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="cas_artifact_write",
                producer_ref="runtime.cas_store",
                consumer_ref="runtime.evidence_provenance_manifest",
                parent_spine_ref=parent_spine_ref,
                input_refs=("artifacts.json",),
                output_refs=(cas_ref,),
                carrier_ref=carrier_ref,
            )
        )
    readiness_ref = _readiness_ref(job_progress)
    if readiness_ref is not None:
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="readiness_result",
                producer_ref="quality.validation.inspect_evidence_bundles",
                consumer_ref="ci.production_quality_readiness",
                parent_spine_ref=parent_spine_ref,
                input_refs=(bundle_output or "bundle.json",),
                output_refs=(readiness_ref,),
                carrier_ref=carrier_ref,
            )
        )
    return build_evidence_spine_handoff_ledger(handoffs)


def build_canary_evidence_handoff_ledger(
    *,
    bundle_ref: str,
    quality_evidence_payload: Mapping[str, Any],
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
    request_payload: Mapping[str, Any] | None,
    command_metadata: Mapping[str, Any] | None,
    dashboard_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the bundle-level handoff ledger emitted beside serious evidence."""

    carrier_ref = _carrier_ref_from_quality_evidence(quality_evidence_payload, command_metadata)
    parent_spine_ref = carrier_ref
    handoffs: list[EvidenceSpineHandoff] = []
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="nl_request_creation",
            producer_ref="runtime.api.nl_request",
            consumer_ref="runtime.control_plane.create_job",
            parent_spine_ref=parent_spine_ref,
            input_refs=("request.sanitized.json",),
            output_refs=("job.json",),
            carrier_ref=carrier_ref,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="control_plane_job_lease",
            producer_ref="runtime.control_plane_store",
            consumer_ref="runtime.control_worker",
            parent_spine_ref=parent_spine_ref,
            input_refs=("job.json",),
            output_refs=("job.json#/lease_owner",),
            carrier_ref=carrier_ref,
        )
    )
    quality_outputs = _quality_output_refs(quality_evidence_payload)
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="workflow_state_persistence",
            producer_ref="runtime.nl_pipeline",
            consumer_ref="tools.ops_runners.runtime.canary_evidence",
            parent_spine_ref=parent_spine_ref,
            input_refs=tuple(ref for ref in ("job.json", "run.json") if _surface_present(ref, job_payload, run_payload)),
            output_refs=quality_outputs or ("quality_evidence/quality_scorecard.json",),
            carrier_ref=carrier_ref,
            message_count=len(quality_outputs) or 1,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="cas_artifact_write",
            producer_ref="runtime.cas_store",
            consumer_ref="runtime.evidence_provenance_manifest",
            parent_spine_ref=parent_spine_ref,
            input_refs=("artifacts.json",),
            output_refs=("cas_manifests/quality_artifact_ownership.manifest.json",),
            carrier_ref=carrier_ref,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="canary_bundle_assembly",
            producer_ref="tools.ops_runners.runtime.canary_evidence",
            consumer_ref="quality.validation.inspect_evidence_bundles",
            parent_spine_ref=parent_spine_ref,
            input_refs=("request.sanitized.json", "job.json"),
            output_refs=("bundle.json", str(bundle_ref)),
            carrier_ref=carrier_ref,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="replay_result",
            producer_ref="tools.ops_runners.runtime.replay_canary_bundle",
            consumer_ref="quality.validation.inspect_evidence_bundles",
            parent_spine_ref=parent_spine_ref,
            input_refs=("bundle.json",),
            output_refs=("quality_evidence/replay_manifest.json",),
            carrier_ref=carrier_ref,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="inspection_result",
            producer_ref="quality.validation.inspect_evidence_bundles",
            consumer_ref="ci.production_quality_readiness",
            parent_spine_ref=parent_spine_ref,
            input_refs=("bundle.json",),
            output_refs=("_build/.tmp/production-quality/final_evidence_bundle_inspection.json",),
            carrier_ref=carrier_ref,
        )
    )
    handoffs.append(
        EvidenceSpineHandoff(
            handoff_kind="readiness_result",
            producer_ref="ci.production_quality_readiness",
            consumer_ref="runtime.operator_closeout",
            parent_spine_ref=parent_spine_ref,
            input_refs=("bundle.json",),
            output_refs=("_build/.tmp/production-quality/final_readiness.json",),
            carrier_ref=carrier_ref,
        )
    )
    if "public_export_bundle" in quality_evidence_payload:
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="public_export_projection",
                producer_ref="runtime.public_export",
                consumer_ref="public.policy_artifact",
                parent_spine_ref=parent_spine_ref,
                input_refs=("quality_evidence/public_export_bundle.json",),
                output_refs=("quality_evidence/public_export_bundle.json",),
                carrier_ref=carrier_ref,
            )
        )
    if dashboard_payload is not None:
        handoffs.append(
            EvidenceSpineHandoff(
                handoff_kind="dashboard_api_export",
                producer_ref="runtime.dashboard_api",
                consumer_ref="apps.runtime_dashboard",
                parent_spine_ref=parent_spine_ref,
                input_refs=("bundle.json",),
                output_refs=("dashboard.json",),
                carrier_ref=carrier_ref,
            )
        )
    return build_evidence_spine_handoff_ledger(handoffs)


def build_evidence_spine_handoff_ledger(
    handoffs: Sequence[EvidenceSpineHandoff | Mapping[str, Any]],
    *,
    required_handoff_kinds: Sequence[str] = REQUIRED_HANDOFF_KINDS,
) -> dict[str, Any]:
    """Validate a handoff ledger and return typed findings."""

    records = [_normalize_handoff(item) for item in handoffs]
    findings: list[dict[str, Any]] = []
    for record in records:
        findings.extend(_handoff_findings(record))
    present_kinds = {record.get("handoff_kind") for record in records}
    for kind in required_handoff_kinds:
        if kind not in present_kinds:
            findings.append(
                _finding(
                    code="evidence_spine_handoff_kind_missing",
                    message=f"Required evidence spine handoff kind is missing: {kind}.",
                    handoff={"handoff_kind": kind},
                    field="handoff_kind",
                )
            )
    status = "fail" if findings else "pass"
    return {
        "schema_version": EVIDENCE_SPINE_HANDOFF_LEDGER_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": status,
        "summary": {
            "handoff_count": len(records),
            "finding_count": len(findings),
            "required_handoff_count": len(tuple(required_handoff_kinds)),
        },
        "handoffs": records,
        "findings": findings,
    }


def _normalize_handoff(item: EvidenceSpineHandoff | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(item, EvidenceSpineHandoff):
        return item.to_dict()
    record = dict(item)
    record.setdefault("schema_version", EVIDENCE_SPINE_HANDOFF_SCHEMA_VERSION)
    record.setdefault("input_refs", [])
    record.setdefault("output_refs", [])
    record.setdefault("message_count", max(len(record.get("input_refs") or []), 1))
    return record


def _handoff_findings(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    checks = (
        ("parent_spine_ref", "evidence_spine_handoff_parent_ref_missing"),
        ("carrier_ref", "evidence_spine_handoff_carrier_ref_missing"),
    )
    for field, code in checks:
        if _clean_text(record.get(field)) is None:
            findings.append(
                _finding(
                    code=code,
                    message=f"Evidence spine handoff is missing {field}.",
                    handoff=record,
                    field=field,
                )
            )
    if not _text_tuple(record.get("input_refs")):
        findings.append(
            _finding(
                code="evidence_spine_handoff_input_refs_missing",
                message="Evidence spine handoff has no input refs.",
                handoff=record,
                field="input_refs",
            )
        )
    if not _text_tuple(record.get("output_refs")):
        findings.append(
            _finding(
                code="evidence_spine_handoff_output_refs_missing",
                message="Evidence spine handoff has no output refs.",
                handoff=record,
                field="output_refs",
            )
        )
    if str(record.get("carrier_redaction_status") or "").casefold() != "pass":
        findings.append(
            _finding(
                code="evidence_spine_handoff_redaction_failed",
                message="Evidence spine handoff carrier redaction did not pass.",
                handoff=record,
                field="carrier_redaction_status",
            )
        )
    if str(record.get("integrity_status") or "").casefold() != "pass":
        findings.append(
            _finding(
                code="evidence_spine_handoff_integrity_failed",
                message="Evidence spine handoff integrity did not pass.",
                handoff=record,
                field="integrity_status",
            )
        )
    producer_ref = _clean_text(record.get("producer_ref"))
    consumer_ref = _clean_text(record.get("consumer_ref"))
    if producer_ref is None or consumer_ref is None or producer_ref == consumer_ref:
        findings.append(
            _finding(
                code="evidence_spine_handoff_producer_consumer_mismatch",
                message="Evidence spine handoff producer and consumer ids are missing or equal.",
                handoff=record,
                field="producer_ref",
            )
        )
    try:
        assert_carrier_payload_safe(record)
    except EvidenceSpineHandoffSafetyError as exc:
        findings.append(
            _finding(
                code=exc.code,
                message=str(exc),
                handoff=record,
                field=exc.path or "payload",
            )
        )
    return findings


def _finding(
    *,
    code: str,
    message: str,
    handoff: Mapping[str, Any],
    field: str,
) -> dict[str, Any]:
    return {
        "status": "fail",
        "severity": "error",
        "code": code,
        "message": message,
        "handoff_id": handoff.get("handoff_id"),
        "handoff_kind": handoff.get("handoff_kind"),
        "producer_ref": handoff.get("producer_ref"),
        "consumer_ref": handoff.get("consumer_ref"),
        "field": field,
        "root_cause_class": "evidence_spine_async_handoff",
        "next_action": (
            "Persist a redacted handoff record with parent/input/output/carrier refs "
            "at the async boundary before using downstream readiness or export results."
        ),
    }


def _carrier_ref_from_quality_evidence(
    quality_evidence_payload: Mapping[str, Any],
    command_metadata: Mapping[str, Any] | None,
) -> str:
    graph = quality_evidence_payload.get("scenario_contract_propagation_graph")
    if isinstance(graph, Mapping):
        nodes = graph.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                carrier = node.get("carrier")
                if isinstance(carrier, Mapping):
                    spine_id = _clean_text(carrier.get("spine_id"))
                    if spine_id is not None:
                        return spine_id
    command_contract_id = None
    if isinstance(command_metadata, Mapping):
        command_contract_id = _clean_text(command_metadata.get("scenario_evidence_contract_id"))
    return command_contract_id or "evidence-spine:bundle-carrier-unavailable"


def _quality_output_refs(quality_evidence_payload: Mapping[str, Any]) -> tuple[str, ...]:
    filenames = {
        "golden_scenario_contract": "quality_evidence/golden_scenario_contract.json",
        "production_data_quality": "quality_evidence/production_data_quality.json",
        "normative_evidence": "quality_evidence/normative_evidence.json",
        "fabric_retrieval_trace": "quality_evidence/fabric_retrieval_trace.json",
        "foundry_method_report": "quality_evidence/foundry_method_report.json",
        "policy_grounding_matrix": "quality_evidence/policy_grounding_matrix.json",
        "semantic_binding_ledger": "quality_evidence/semantic_binding_ledger.json",
        "policy_design_case": "quality_evidence/policy_design_case.json",
        "scenario_contract_propagation_graph": (
            "quality_evidence/scenario_contract_propagation_graph.json"
        ),
    }
    return tuple(
        filename for key, filename in filenames.items() if key in quality_evidence_payload
    )


def _surface_present(
    ref: str,
    job_payload: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
) -> bool:
    if ref == "job.json":
        return job_payload is not None
    if ref == "run.json":
        return run_payload is not None
    return True


def _readiness_ref(progress: Mapping[str, Any]) -> str | None:
    evidence_refs = progress.get("evidence_refs")
    if isinstance(evidence_refs, Mapping):
        for key in ("readiness", "final_readiness", "production_readiness"):
            value = _clean_text(evidence_refs.get(key))
            if value is not None:
                return value
    return _clean_text(progress.get("readiness_ref"))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        return ()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text is not None and text not in result:
            result.append(text)
    return tuple(result)


def _stable_id(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "handoff:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:24]
