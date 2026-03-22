"""Shared metadata helpers for capability-wins benchmark entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from benchmarks.reporting import WORKFLOW_LEVELS, dataclasses_to_dict


@dataclass(frozen=True)
class CapabilityProofSpec:
    """Canonical proof metadata attached to capability benchmark reports."""

    proof_class: str
    literature_anchor: Mapping[str, Any] | str
    claim_profile_targets: Sequence[str]
    competitor_gap: Sequence[Mapping[str, Any]]
    workflow_levels: Mapping[str, Any]
    evidence_bundle_complete: bool | None = None
    public_claim_eligible: bool | None = None


def make_gap_row(
    competitor: str,
    gap: str,
    *,
    status: str,
    note: str,
    level: str | None = None,
    citation: str | None = None,
) -> dict[str, Any]:
    """Build one machine-readable competitor-gap row."""

    row: dict[str, Any] = {
        "competitor": competitor,
        "gap": gap,
        "status": str(status).upper(),
        "note": note,
    }
    if level is not None:
        row["level"] = level
    if citation is not None:
        row["citation"] = citation
    return row


def _normalize_workflow_verdict(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "BLOCKED"
    verdict = str(value).strip().upper()
    return verdict or "UNKNOWN"


def _result_has_evidence(payload: Any) -> bool:
    data = dataclasses_to_dict(payload)
    if isinstance(data, dict):
        interesting_keys = (
            "proof_steps",
            "report",
            "envelope",
            "estimand_ast",
            "partial_bounds",
            "constructive_message",
            "effects",
            "result",
            "trace",
            "negative_certificate",
        )
        return any(bool(data.get(key)) for key in interesting_keys)
    if isinstance(data, list):
        return any(_result_has_evidence(item) for item in data)
    return bool(data)


def build_capability_report_extra(
    report: Any,
    spec: CapabilityProofSpec,
) -> dict[str, Any]:
    """Assemble the canonical capability metadata payload."""

    evidence_bundle_complete = (
        spec.evidence_bundle_complete
        if spec.evidence_bundle_complete is not None
        else bool(report.cases) and report.n_total() == report.n_passed()
    )
    public_claim_eligible = (
        spec.public_claim_eligible
        if spec.public_claim_eligible is not None
        else report.n_total() > 0 and report.n_total() == report.n_passed() and evidence_bundle_complete
    )

    workflow_verdicts = {level: "PASS" for level in WORKFLOW_LEVELS}
    for level, verdict in spec.workflow_levels.items():
        normalized_level = str(level).strip()
        if normalized_level in WORKFLOW_LEVELS:
            workflow_verdicts[normalized_level] = _normalize_workflow_verdict(verdict)

    competitor_matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for row in spec.competitor_gap:
        rendered = dataclasses_to_dict(row)
        competitor = str(rendered.get("competitor") or "unknown")
        level = str(rendered.get("level") or "identifiable")
        if level not in WORKFLOW_LEVELS:
            level = "identifiable"
        status = str(rendered.get("status") or "UNKNOWN").strip().lower()
        normalized_status = {
            "gap": "fail",
            "blocked": "fail",
            "unsupported": "fail",
            "partial": "partial",
            "pass": "pass",
            "ok": "pass",
        }.get(status, "partial")
        competitor_matrix.setdefault(
            competitor,
            {workflow: {"status": "pass", "reason": "No blocking evidence recorded."} for workflow in WORKFLOW_LEVELS},
        )
        competitor_matrix[competitor][level] = {
            "status": normalized_status,
            "reason": rendered.get("note") or rendered.get("gap") or "Capability gap observed.",
            **({"citation": rendered["citation"]} if rendered.get("citation") else {}),
        }

    return {
        "proof_class": "capability_gap",
        "literature_anchor": dataclasses_to_dict(spec.literature_anchor),
        "claim_profile_targets": [
            "frontier_frontier_claim",
            "full_stack_publication_claim",
        ],
        "competitor_gap": competitor_matrix,
        "workflow_levels": list(WORKFLOW_LEVELS),
        "workflow_verdicts": workflow_verdicts,
        "evidence_bundle_complete": evidence_bundle_complete,
        "public_claim_eligible": public_claim_eligible,
    }
