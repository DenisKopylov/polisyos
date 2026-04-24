"""Derive actionable change proposals from failed legal-evaluation findings."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.lex.errors import LexNotReadyError, LexValidationError

if TYPE_CHECKING:
    from pathlib import Path


def _decimal_to_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(value)
    except Exception:
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _epsilon_for_threshold(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    if exponent < 0:
        return Decimal(1).scaleb(exponent)
    return Decimal("1")


def _metric_type_from_expected(expected: dict[str, Any] | None) -> str:
    if not isinstance(expected, dict):
        return "text"
    threshold = expected.get("threshold")
    if isinstance(threshold, str):
        if _parse_decimal(threshold) is not None:
            return "numeric"
        normalized = threshold.strip().casefold()
        if normalized in {"true", "false"}:
            return "boolean"
    return "text"


def _patch_value_for_operator(*, operator: str, threshold: Decimal) -> str:
    if operator in {"<=", ">=", "="}:
        return _decimal_to_text(threshold)
    epsilon = _epsilon_for_threshold(threshold)
    if operator == "<":
        return _decimal_to_text(threshold - epsilon)
    if operator == ">":
        return _decimal_to_text(threshold + epsilon)
    return _decimal_to_text(threshold)


def _action_sort_key(action: dict[str, Any]) -> tuple[int, str, str]:
    action_kind = str(action.get("action_kind", ""))
    if action_kind == "policy_patch":
        bucket = 0
        tie = str((action.get("patch_json") or [{}])[0].get("path", ""))
    elif action_kind == "add_metric":
        bucket = 1
        tie = str(action.get("metric_id", ""))
    else:
        bucket = 2
        tie = ""
    links = action.get("links_to_findings")
    first_link = ""
    if isinstance(links, list) and links:
        first_link = str(links[0])
    return bucket, first_link, tie


def propose_changes_v1(
    *,
    report_payload: dict[str, Any],
    based_on_report_ref: LegalReportRef,
) -> dict[str, Any]:
    """Propose changes v 1 helper."""
    request = report_payload.get("request")
    findings = report_payload.get("findings")
    quality_issues = report_payload.get("quality_issues")
    if not isinstance(request, dict) or not isinstance(findings, list):
        raise LexValidationError("invalid legal report payload for change proposal generation")

    policy_spec_ref = request.get("policy_spec_ref")
    if not isinstance(policy_spec_ref, dict):
        policy_spec_ref = None

    actions: list[dict[str, Any]] = []

    findings_by_rule_id: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        rule_id = finding.get("rule_id")
        if isinstance(rule_id, str):
            findings_by_rule_id[rule_id] = finding

    for finding in sorted(
        (row for row in findings if isinstance(row, dict)),
        key=lambda row: str(row.get("rule_id", "")),
    ):
        if finding.get("status") != "FAIL":
            continue
        rule_id = str(finding.get("rule_id", ""))
        expected = finding.get("expected")
        if not isinstance(expected, dict):
            continue
        operator = expected.get("op")
        threshold_raw = expected.get("threshold")
        if not isinstance(operator, str) or not isinstance(threshold_raw, str):
            continue
        threshold_decimal = _parse_decimal(threshold_raw)
        if threshold_decimal is None:
            continue

        evidence_refs = finding.get("observed_evidence_refs")
        if not isinstance(evidence_refs, list):
            continue
        policy_pointer: str | None = None
        for evidence in evidence_refs:
            if not isinstance(evidence, dict):
                continue
            if evidence.get("kind") != "policy_param":
                continue
            pointer = evidence.get("policy_json_pointer")
            if isinstance(pointer, str) and pointer:
                policy_pointer = pointer
                break
        if policy_pointer is None or policy_spec_ref is None:
            continue

        patch_value = _patch_value_for_operator(
            operator=operator,
            threshold=threshold_decimal,
        )
        actions.append(
            {
                "action_kind": "policy_patch",
                "target_ref": policy_spec_ref,
                "patch_format": "json_patch_v1",
                "patch_json": [{"op": "replace", "path": policy_pointer, "value": patch_value}],
                "rationale": (
                    f"Bring {policy_pointer} to satisfy rule {rule_id} "
                    f"({operator} {threshold_raw})."
                ),
                "links_to_findings": [rule_id],
            }
        )

    if isinstance(quality_issues, list):
        for issue in sorted(
            (row for row in quality_issues if isinstance(row, dict)),
            key=lambda row: (str(row.get("rule_id", "")), str(row.get("code", ""))),
        ):
            if issue.get("code") != "missing_observed_value":
                continue
            rule_id = issue.get("rule_id")
            if not isinstance(rule_id, str):
                continue
            details = issue.get("details")
            if not isinstance(details, dict):
                continue
            predicate_id = details.get("predicate_id")
            if not isinstance(predicate_id, str) or not predicate_id:
                continue

            finding = findings_by_rule_id.get(rule_id)
            expected = finding.get("expected") if isinstance(finding, dict) else None
            metric_type = _metric_type_from_expected(
                expected if isinstance(expected, dict) else None
            )
            unit_id = None
            if isinstance(expected, dict):
                maybe_unit = expected.get("unit")
                if isinstance(maybe_unit, str):
                    unit_id = maybe_unit

            actions.append(
                {
                    "action_kind": "add_metric",
                    "target_ref": None,
                    "patch_format": None,
                    "patch_json": None,
                    "rationale": (
                        f"Add instrumentation for metric {predicate_id} required by rule {rule_id}."
                    ),
                    "links_to_findings": [rule_id],
                    "metric_id": predicate_id,
                    "metric_type": metric_type,
                    "unit_id": unit_id,
                }
            )

    actions.sort(key=_action_sort_key)
    return {
        "schema_version": "1.0",
        "based_on_report_ref": {
            "artifact_id": str(based_on_report_ref.artifact_id),
            "kind": based_on_report_ref.kind,
        },
        "actions": actions,
    }


def propose_changes_impl(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    based_on_report_ref: LegalReportRef,
    segment_name: str | None = None,
) -> list[ChangeProposalRef]:
    """Load a legal report artifact and persist any policy or instrumentation proposals it implies."""
    del fact_log_root
    del segment_name

    try:
        report_payload_raw = from_canonical_bytes(
            cas.get_bytes(ArtifactID.model_validate(str(based_on_report_ref.artifact_id)))
        )
    except FileNotFoundError as exc:
        raise LexNotReadyError(
            "missing legal_report artifact",
            details={"artifact_id": str(based_on_report_ref.artifact_id)},
        ) from exc
    except Exception as exc:
        raise LexValidationError(
            "failed to load legal_report artifact",
            details={"artifact_id": str(based_on_report_ref.artifact_id)},
        ) from exc

    if not isinstance(report_payload_raw, dict):
        raise LexValidationError("legal_report payload must be a JSON object")

    proposal_payload = propose_changes_v1(
        report_payload=report_payload_raw,
        based_on_report_ref=based_on_report_ref,
    )
    actions = proposal_payload.get("actions")
    if not isinstance(actions, list) or not actions:
        return []

    inputs: list[InputRef] = [
        InputRef(
            artifact_id=ArtifactID.model_validate(str(based_on_report_ref.artifact_id)),
            role="legal_report",
        )
    ]
    policy_targets = sorted(
        {
            str(action["target_ref"]["artifact_id"])
            for action in actions
            if isinstance(action, dict)
            and action.get("action_kind") == "policy_patch"
            and isinstance(action.get("target_ref"), dict)
            and isinstance(action["target_ref"].get("artifact_id"), str)
        }
    )
    for artifact_id in policy_targets:
        inputs.append(
            InputRef(
                artifact_id=ArtifactID.model_validate(artifact_id),
                role="policy_spec",
            )
        )

    ref = cas.put_json(
        proposal_payload,
        opts=PutOptions(
            kind="lex.change_proposal",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.lex.ChangeProposal", version="1.0"),
            inputs=inputs,
        ),
    )
    return [ChangeProposalRef(artifact_id=ref.artifact_id)]


__all__ = [
    "propose_changes_impl",
    "propose_changes_v1",
]
