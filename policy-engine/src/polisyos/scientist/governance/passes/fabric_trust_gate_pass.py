"""Cap Scientist readiness from Fabric quality, trust, lineage, and freshness metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)


class FabricTrustGatePass(ValidatorPass):
    """Validate Fabric trust envelopes before Scientist outputs become decision-ready."""

    def __init__(self, *, force_run: bool = False) -> None:
        self._force_run = force_run

    @property
    def pass_id(self) -> str:
        return "fabric_trust"

    @property
    def estimated_cost_ms(self) -> int:
        return 50

    @property
    def requires_data(self) -> bool:
        return False

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        if not self._force_run and self.pass_id not in ctx.profile.pass_ids:
            return []

        rows = _fabric_trust_rows(ctx.state)
        scorecards = _source_scorecards(ctx.state)
        if not rows and not scorecards:
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "fabric_decision_data"],
                    message="Fabric trust metadata is missing from Scientist governance state",
                    severity=IssueSeverity.WARNING,
                    code="FABRIC_TRUST_METADATA_MISSING",
                    suggestion="Attach FabricDecisionData or Fabric trust batch refs before promotion.",
                )
            ]

        issues: list[ComplianceIssue] = []
        for row in rows:
            subject = str(row.get("id") or row.get("subject_id") or "fabric_decision_data")
            quality = _mapping(row.get("quality"))
            lineage = _mapping(row.get("lineage"))
            access = _mapping(row.get("access"))
            freshness = _lineage_freshness(row)

            quality_status = str(quality.get("status") or "").strip().lower()
            if quality_status in {"failed", "unknown_quality"}:
                issues.append(
                    _issue(
                        subject,
                        code=(
                            "FABRIC_QUALITY_FAILED"
                            if quality_status == "failed"
                            else "FABRIC_QUALITY_UNKNOWN"
                        ),
                        message=f"Fabric quality status is {quality_status}.",
                        path=["fabric", subject, "quality"],
                        strict=ctx.profile.level.value == "strict",
                    )
                )

            lineage_status = str(lineage.get("status") or "").strip().lower()
            if lineage_status in {"", "untraced", "disputed"}:
                issues.append(
                    _issue(
                        subject,
                        code="FABRIC_LINEAGE_MISSING",
                        message=f"Fabric lineage status is {lineage_status or 'missing'}.",
                        path=["fabric", subject, "lineage"],
                        strict=True,
                    )
                )

            if freshness == "stale":
                issues.append(
                    _issue(
                        subject,
                        code="FABRIC_EVIDENCE_STALE",
                        message="Fabric evidence freshness is stale.",
                        path=["fabric", subject, "lineage", "freshness"],
                        strict=ctx.profile.level.value == "strict",
                    )
                )

            if str(access.get("classification") or "").strip().lower() == "restricted":
                issues.append(
                    _issue(
                        subject,
                        code="FABRIC_ACCESS_RESTRICTED",
                        message="Fabric access classification is restricted.",
                        path=["fabric", subject, "access"],
                        strict=True,
                    )
                )

        for contract_id, scorecard in scorecards.items():
            grade = str(scorecard.get("grade") or "").strip().upper()
            status = str(scorecard.get("status") or "").strip().lower()
            trust_tier = _source_trust_tier(scorecard)
            if grade in {"D", "F"} or status == "breached" or trust_tier in {"low", "unknown"}:
                issues.append(
                    _issue(
                        contract_id,
                        code="FABRIC_SOURCE_TRUST_LOW",
                        message="Fabric source trust or scorecard grade is below decision threshold.",
                        path=["fabric", contract_id, "source_trust"],
                        strict=True,
                    )
                )

        cap = _readiness_cap_from_issues(issues)
        if cap is not None:
            ctx.state["fabric_readiness_cap"] = cap
            existing = list(ctx.state.get("fabric_trust_issues") or [])
            existing.extend(issue.code for issue in issues)
            ctx.state["fabric_trust_issues"] = sorted(set(existing))
        return issues


def _fabric_trust_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    decision_data = state.get("fabric_decision_data")
    if isinstance(decision_data, list):
        rows.extend(_as_mapping(row) for row in decision_data)
    trust_refs = state.get("fabric_trust_refs")
    if isinstance(trust_refs, Mapping):
        rows.extend(_as_mapping(row) | {"id": str(key)} for key, row in trust_refs.items())
    trust_batch = _mapping(state.get("fabric_trust_batch"))
    batch_refs = trust_batch.get("trust_refs")
    if isinstance(batch_refs, Mapping):
        rows.extend(_as_mapping(row) | {"id": str(key)} for key, row in batch_refs.items())
    return [row for row in rows if row]


def _source_scorecards(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    payload = state.get("fabric_source_scorecards")
    if isinstance(payload, Mapping):
        nested = payload.get("scorecards")
        if isinstance(nested, Mapping):
            payload = nested
        return {
            str(contract_id): _as_mapping(scorecard)
            for contract_id, scorecard in payload.items()
            if _as_mapping(scorecard)
        }
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return _as_mapping(value)


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
        return dict(payload) if isinstance(payload, Mapping) else {}
    return {}


def _lineage_freshness(row: Mapping[str, Any]) -> str:
    lineage = _mapping(row.get("lineage"))
    direct = str(lineage.get("freshness") or "").strip().lower()
    if direct:
        return direct
    trust_metadata = _mapping(lineage.get("trust_metadata"))
    return str(trust_metadata.get("freshness") or "").strip().lower()


def _source_trust_tier(scorecard: Mapping[str, Any]) -> str:
    metrics = scorecard.get("metrics")
    if not isinstance(metrics, list):
        return ""
    for metric in metrics:
        row = _mapping(metric)
        if row.get("name") == "source_trust":
            reason = str(row.get("reason") or "").strip().lower()
            if "source_trust=" in reason:
                return reason.split("source_trust=", 1)[1].split()[0]
            score = row.get("score")
            if isinstance(score, int | float) and float(score) < 0.5:
                return "low"
    return ""


def _issue(
    subject: str,
    *,
    code: str,
    message: str,
    path: list[str],
    strict: bool,
) -> ComplianceIssue:
    return ComplianceIssue(
        pass_id="fabric_trust",
        path=path,
        message=f"{message} Subject: {subject}.",
        severity=IssueSeverity.BLOCKER if strict else IssueSeverity.WARNING,
        code=code,
        suggestion="Refresh Fabric trust metadata or record an accepted-risk waiver.",
    )


def _readiness_cap_from_issues(issues: list[ComplianceIssue]) -> dict[str, str] | None:
    if not issues:
        return None
    blocker = next((issue for issue in issues if issue.severity is IssueSeverity.BLOCKER), None)
    selected = blocker or issues[0]
    return {
        "level": "research_artifact" if blocker is not None else "analyst_advisory",
        "reason": str(selected.code or "fabric_trust_gate"),
    }


__all__ = ["FabricTrustGatePass"]
