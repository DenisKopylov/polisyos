"""Runtime-owned institutional provenance producers for Policy Design Case ledgers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

IMPLEMENTATION_FEASIBILITY_RUNTIME_PROVENANCE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.implementation_feasibility_runtime_provenance.v1"
)
CONTESTABILITY_APPEALS_RUNTIME_PROVENANCE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.contestability_appeals_runtime_provenance.v1"
)
PRODUCER_ID = "polisyos.runtime.quality.institutional_provenance"
PRODUCER_VERSION = "2026.05.19+wave35h"
EVIDENCE_AUTHORITY = "runtime_emitted"
SERIOUS_EXECUTION_PROFILES = frozenset({"governed", "production", "research", "serious"})


@dataclass(frozen=True)
class InstitutionalProvenanceError(ValueError):
    """Fail-closed institutional provenance emission violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def emit_implementation_feasibility_runtime_provenance(
    *,
    recommendation_rows: Sequence[Mapping[str, Any]],
    run_context: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Emit one runtime-owned feasibility provenance record per recommendation."""

    if not recommendation_rows:
        raise InstitutionalProvenanceError(
            "recommendation_rows_missing",
            "Implementation feasibility runtime provenance requires recommendation rows.",
            "recommendation_rows",
        )
    context = _serious_run_context(run_context)
    timestamp = generated_at or _now()
    records = [
        _implementation_record(row=row, context=context, generated_at=timestamp)
        for row in recommendation_rows
    ]
    for record in records:
        validate_runtime_owned_provenance(record, surface="implementation_feasibility")
    return {
        "schema_version": IMPLEMENTATION_FEASIBILITY_RUNTIME_PROVENANCE_SCHEMA_VERSION,
        "producer": PRODUCER_ID,
        "producer_version": PRODUCER_VERSION,
        "generated_at": timestamp,
        "status": "complete",
        "evidence_authority": EVIDENCE_AUTHORITY,
        "emitted_during_serious_run": True,
        "run_identity": _run_identity(context),
        "record_count": len(records),
        "records": records,
    }


def emit_contestability_appeals_runtime_provenance(
    *,
    appeal_rows: Sequence[Mapping[str, Any]],
    run_context: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Emit one runtime-owned lifecycle outcome provenance record per appeal."""

    if not appeal_rows:
        raise InstitutionalProvenanceError(
            "appeal_rows_missing",
            "Contestability runtime provenance requires appeal rows.",
            "appeal_rows",
        )
    context = _serious_run_context(run_context)
    timestamp = generated_at or _now()
    records = [
        _appeal_record(row=row, context=context, generated_at=timestamp)
        for row in appeal_rows
    ]
    for record in records:
        validate_runtime_owned_provenance(record, surface="contestability_appeals")
    return {
        "schema_version": CONTESTABILITY_APPEALS_RUNTIME_PROVENANCE_SCHEMA_VERSION,
        "producer": PRODUCER_ID,
        "producer_version": PRODUCER_VERSION,
        "generated_at": timestamp,
        "status": "complete",
        "evidence_authority": EVIDENCE_AUTHORITY,
        "emitted_during_serious_run": True,
        "run_identity": _run_identity(context),
        "record_count": len(records),
        "records": records,
    }


def validate_runtime_owned_provenance(
    record: Mapping[str, Any],
    *,
    surface: str,
) -> None:
    """Validate the field set Wave 35H requires before a record can be authority."""

    if not isinstance(record, Mapping):
        raise InstitutionalProvenanceError(
            "runtime_provenance_missing",
            "Runtime-owned provenance record must be a mapping.",
        )
    for field in (
        "producer",
        "event_refs",
        "artifact_refs",
        "trace_refs",
        "run_identity",
        "evidence_authority",
    ):
        _require_surface(record.get(field), field, f"{field}_missing")
    if record.get("producer") != PRODUCER_ID:
        raise InstitutionalProvenanceError(
            "producer_invalid",
            "Runtime-owned institutional provenance must be emitted by the runtime producer.",
            "producer",
        )
    if record.get("evidence_authority") != EVIDENCE_AUTHORITY:
        raise InstitutionalProvenanceError(
            "evidence_authority_invalid",
            "Institutional runtime provenance must carry runtime_emitted authority.",
            "evidence_authority",
        )
    if record.get("emitted_during_serious_run") is not True:
        raise InstitutionalProvenanceError(
            "serious_run_required",
            "Institutional provenance must be emitted during a serious run.",
            "emitted_during_serious_run",
        )
    identity = _mapping(record.get("run_identity"))
    profile = str(identity.get("execution_profile") or "").casefold()
    if profile not in SERIOUS_EXECUTION_PROFILES:
        raise InstitutionalProvenanceError(
            "serious_run_required",
            "Institutional provenance must carry a serious execution profile.",
            "run_identity.execution_profile",
        )
    if surface == "implementation_feasibility":
        _validate_implementation_record(record)
    elif surface == "contestability_appeals":
        _validate_appeal_record(record)
    else:
        raise InstitutionalProvenanceError(
            "surface_invalid",
            f"Unsupported institutional provenance surface: {surface}",
            "surface",
        )


def _implementation_record(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    recommendation_id = _required_text(
        row.get("recommendation_id"),
        "recommendation_id",
        "recommendation_id_missing",
    )
    claim_binding = _required_mapping(
        row.get("claim_binding"),
        "claim_binding",
        "claim_binding_missing",
    )
    if not _text(claim_binding.get("claim_id")):
        raise InstitutionalProvenanceError(
            "claim_binding_missing",
            "Implementation feasibility provenance requires a claim binding claim_id.",
            "claim_binding.claim_id",
        )
    if claim_binding.get("generic_final_text_sufficient") is True:
        raise InstitutionalProvenanceError(
            "generic_final_text_not_runtime_provenance",
            "Generic final text cannot stand in for runtime feasibility provenance.",
            "claim_binding.generic_final_text_sufficient",
        )
    actor = _required_mapping(
        row.get("implementation_actor"),
        "actor",
        "actor_missing",
    )
    risk = _required_mapping(row.get("risk_evidence"), "risk", "risk_missing")
    monitoring = _required_mapping(
        row.get("monitoring_evidence"),
        "monitoring_evidence",
        "monitoring_outcome_refs_missing",
    )
    monitoring_outcome_refs = _string_refs(monitoring.get("monitor_refs"))
    if not monitoring_outcome_refs:
        raise InstitutionalProvenanceError(
            "monitoring_outcome_refs_missing",
            "Implementation feasibility provenance requires monitoring outcome refs.",
            "monitoring_evidence.monitor_refs",
        )
    artifact_refs = _unique(
        [
            *_context_refs(context, "artifact_refs"),
            *_string_refs(row.get("source_refs")),
            *_string_refs(row.get("method_refs")),
            *_string_refs(row.get("norm_refs")),
            *_collect_ref_strings(row.get("feasibility_evidence")),
            *_collect_ref_strings(row.get("risk_evidence")),
            *_collect_ref_strings(row.get("monitoring_evidence")),
            *_collect_ref_strings(row.get("authority_refs")),
            *_collect_ref_strings(claim_binding),
        ]
    )
    return {
        "record_id": "institutional-feasibility-" + _digest(recommendation_id),
        "producer": PRODUCER_ID,
        "producer_version": PRODUCER_VERSION,
        "evidence_authority": EVIDENCE_AUTHORITY,
        "provenance_kind": "runtime_emitted",
        "emitted_during_serious_run": True,
        "generated_at": generated_at,
        "run_identity": _run_identity(context),
        "recommendation_id": recommendation_id,
        "event_refs": _unique(
            [
                *_context_refs(context, "event_refs"),
                _runtime_event_ref(context, f"implementation-feasibility/{recommendation_id}"),
            ]
        ),
        "artifact_refs": artifact_refs,
        "trace_refs": _trace_refs(context, f"implementation-feasibility/{recommendation_id}"),
        "claim_binding": dict(claim_binding),
        "actor": dict(actor),
        "risk": dict(risk),
        "monitoring_outcome_refs": monitoring_outcome_refs,
        "source_refs": _unique(
            [
                *_string_refs(row.get("source_refs")),
                *_string_refs(row.get("method_refs")),
                *_string_refs(row.get("norm_refs")),
            ]
        ),
        "runtime_surface": "publication_readiness_and_continuous_governance",
        "build_time_overlay": False,
    }


def _appeal_record(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    appeal_id = _required_text(row.get("appeal_id"), "appeal_id", "appeal_id_missing")
    disposition = _required_text(
        row.get("disposition"),
        "appeal_disposition",
        "appeal_disposition_missing",
    )
    transition = _required_text(
        row.get("lifecycle_transition"),
        "lifecycle_transition",
        "lifecycle_transition_missing",
    )
    publication_state_effect = _required_text(
        row.get("publication_state_effect"),
        "publication_state_effect",
        "publication_state_effect_missing",
    )
    outcome_refs = _string_refs(row.get("outcome_refs"))
    if not outcome_refs:
        raise InstitutionalProvenanceError(
            "artifact_refs_missing",
            "Appeal lifecycle provenance requires runtime outcome artifact refs.",
            "outcome_refs",
        )
    artifact_refs = _unique(
        [
            *_context_refs(context, "artifact_refs"),
            *_string_refs(row.get("submitted_evidence")),
            *outcome_refs,
            *_collect_ref_strings(row.get("reissue_stale_withdrawal_impact")),
        ]
    )
    return {
        "record_id": "institutional-appeal-" + _digest(appeal_id),
        "producer": PRODUCER_ID,
        "producer_version": PRODUCER_VERSION,
        "evidence_authority": EVIDENCE_AUTHORITY,
        "provenance_kind": "runtime_emitted",
        "emitted_during_serious_run": True,
        "generated_at": generated_at,
        "run_identity": _run_identity(context),
        "appeal_id": appeal_id,
        "claim_id": _text(row.get("claim_id")),
        "standing": _text(row.get("standing")),
        "grounds": _text(row.get("grounds")),
        "event_refs": _unique(
            [
                *_context_refs(context, "event_refs"),
                _runtime_event_ref(context, f"appeals/{appeal_id}/{transition}"),
            ]
        ),
        "artifact_refs": artifact_refs,
        "trace_refs": _trace_refs(context, f"appeals/{appeal_id}/{transition}"),
        "appeal_disposition": disposition,
        "lifecycle_transition": transition,
        "publication_state_effect": publication_state_effect,
        "monitoring_changes": _string_refs(row.get("monitoring_changes")),
        "source_refs": _unique(
            [
                *_string_refs(row.get("submitted_evidence")),
                *outcome_refs,
            ]
        ),
        "runtime_surface": "contestability_appeals_lifecycle",
        "build_time_overlay": False,
    }


def _validate_implementation_record(record: Mapping[str, Any]) -> None:
    for field in ("claim_binding", "actor", "risk", "monitoring_outcome_refs"):
        _require_surface(record.get(field), field, f"{field}_missing")
    claim_binding = _mapping(record.get("claim_binding"))
    if not _text(claim_binding.get("claim_id")):
        raise InstitutionalProvenanceError(
            "claim_binding_missing",
            "Implementation feasibility provenance requires claim_binding.claim_id.",
            "claim_binding.claim_id",
        )


def _validate_appeal_record(record: Mapping[str, Any]) -> None:
    for field in (
        "appeal_disposition",
        "lifecycle_transition",
        "publication_state_effect",
    ):
        _require_surface(record.get(field), field, f"{field}_missing")


def _serious_run_context(context: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(context, Mapping):
        raise InstitutionalProvenanceError(
            "run_context_missing",
            "Runtime provenance requires run context.",
            "run_context",
        )
    profile = str(context.get("execution_profile") or "").casefold()
    if profile not in SERIOUS_EXECUTION_PROFILES:
        raise InstitutionalProvenanceError(
            "serious_run_required",
            "Institutional provenance must be emitted during a serious run.",
            "execution_profile",
        )
    for field in ("run_id", "job_id", "case_id", "trace_id"):
        _required_text(context.get(field), field, f"{field}_missing")
    if not _context_refs(context, "event_refs"):
        raise InstitutionalProvenanceError(
            "event_refs_missing",
            "Runtime provenance requires event refs from the emitting run.",
            "event_refs",
        )
    if not _context_refs(context, "trace_refs"):
        raise InstitutionalProvenanceError(
            "trace_refs_missing",
            "Runtime provenance requires trace refs from the emitting run.",
            "trace_refs",
        )
    return context


def _run_identity(context: Mapping[str, Any]) -> dict[str, str | None]:
    return {
        "run_id": _text(context.get("run_id")),
        "job_id": _text(context.get("job_id")),
        "case_id": _text(context.get("case_id")),
        "tenant_id": _text(context.get("tenant_id")),
        "cell_id": _text(context.get("cell_id")),
        "trace_id": _text(context.get("trace_id")),
        "execution_profile": _text(context.get("execution_profile")),
    }


def _runtime_event_ref(context: Mapping[str, Any], suffix: str) -> str:
    run_id = _text(context.get("run_id")) or "unknown-run"
    return f"runtime-event://policy-design-case/{run_id}/institutional-provenance/{suffix}"


def _trace_refs(context: Mapping[str, Any], suffix: str) -> list[str]:
    return _unique(
        [
            *_context_refs(context, "trace_refs"),
            f"trace://{_text(context.get('trace_id')) or 'unknown-trace'}/{suffix}",
        ]
    )


def _context_refs(context: Mapping[str, Any], key: str) -> list[str]:
    return _string_refs(context.get(key))


def _required_mapping(value: object, field: str, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise InstitutionalProvenanceError(
            code,
            f"Runtime provenance requires {field}.",
            field,
        )
    return value


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if not text:
        raise InstitutionalProvenanceError(
            code,
            f"Runtime provenance requires {field}.",
            field,
        )
    return text


def _require_surface(value: object, field: str, code: str) -> None:
    if isinstance(value, Mapping) and value:
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) and value:
        return
    if _text(value):
        return
    raise InstitutionalProvenanceError(
        code,
        f"Runtime provenance requires {field}.",
        field,
    )


def _collect_ref_strings(value: object) -> list[str]:
    refs: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, str):
            if _looks_like_ref(item):
                refs.add(item)
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                visit(child)

    visit(value)
    return sorted(refs)


def _looks_like_ref(value: str) -> bool:
    return any(
        marker in value
        for marker in (
            "/",
            ".json",
            ".py",
            ".ts",
            ".tsx",
            "sha256:",
            "cas://",
            "ledger://",
            "appeal-ledger://",
            "scenario-contract://",
            "#",
        )
    )


def _string_refs(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if item]
    return []


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _unique(values: Iterable[str]) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


__all__ = [
    "CONTESTABILITY_APPEALS_RUNTIME_PROVENANCE_SCHEMA_VERSION",
    "EVIDENCE_AUTHORITY",
    "IMPLEMENTATION_FEASIBILITY_RUNTIME_PROVENANCE_SCHEMA_VERSION",
    "PRODUCER_ID",
    "InstitutionalProvenanceError",
    "emit_contestability_appeals_runtime_provenance",
    "emit_implementation_feasibility_runtime_provenance",
    "validate_runtime_owned_provenance",
]
