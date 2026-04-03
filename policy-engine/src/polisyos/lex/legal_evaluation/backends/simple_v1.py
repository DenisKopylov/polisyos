"""Public backends simple v 1 module API."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from polisyos.ir.norm_pack import NormRule
from polisyos.lex.common import collapse_ws
from polisyos.lex.legal_evaluation.context_builder import RuleObservation

FindingStatus = Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
FindingSeverity = Literal["info", "warning", "blocker"]

_NUMERIC_OPERATORS = {"<", "<=", "=", ">=", ">"}
_BOOL_TEXT_OPERATORS = {"="}


def _normalize_text(text: str) -> str:
    return collapse_ws(text).casefold()


def _parse_decimal(raw: str) -> Decimal | None:
    try:
        parsed = Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    return parsed


def _decimal_to_text(value: Decimal) -> str:
    out = format(value, "f")
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out or "0"


def _status_for_unknown(strict: bool) -> FindingStatus:
    if strict:
        return "FAIL"
    return "UNKNOWN"


def _severity_for_status(status: FindingStatus, *, strict: bool) -> FindingSeverity:
    if status in {"PASS", "NOT_APPLICABLE"}:
        return "info"
    if status == "UNKNOWN":
        return "blocker" if strict else "warning"
    return "blocker"


def _sorted_norm_citations(rule: NormRule) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provision_ref in rule.provision_refs:
        citations_sorted = sorted(
            provision_ref.citations,
            key=lambda citation: (
                citation.doc.doc_id,
                citation.fragment_id or "",
            ),
        )
        rows.append(
            {
                "provision_id": provision_ref.provision_id,
                "citations": [citation.model_dump(mode="python") for citation in citations_sorted],
            }
        )
    rows.sort(key=lambda row: row["provision_id"])
    return rows


def _evidence_refs(observation: RuleObservation) -> list[dict[str, Any]]:
    observed = observation.observed
    if observed is None:
        return []
    if observed.source_kind == "metrics":
        return [
            {
                "kind": "metrics",
                "simulation_result_ref": observed.simulation_result_ref,
                "metrics_ref": observed.metrics_ref,
                "metric_key": observed.metric_key,
            }
        ]
    if observed.source_kind == "policy_param":
        return [
            {
                "kind": "policy_param",
                "policy_spec_ref": observed.policy_spec_ref,
                "policy_json_pointer": observed.policy_json_pointer,
            }
        ]
    return [{"kind": observed.source_kind}]


def _mapping_rationale(
    *,
    observation: RuleObservation,
    observed_source: str | None,
) -> dict[str, Any]:
    return {
        "source": observed_source,
        "notes": list(observation.mapping_notes),
    }


def _convert_unit(*, value: Decimal, from_unit: str, to_unit: str) -> Decimal | None:
    pair = (from_unit.casefold(), to_unit.casefold())
    if pair == ("percent", "ratio"):
        return value / Decimal("100")
    if pair == ("ratio", "percent"):
        return value * Decimal("100")
    if pair == ("km", "m"):
        return value * Decimal("1000")
    if pair == ("m", "km"):
        return value / Decimal("1000")
    return None


@dataclass(frozen=True)
class RuleFinding:
    """Rule finding public type."""
    rule_id: str
    status: FindingStatus
    severity: FindingSeverity
    norm_citations: list[dict[str, Any]]
    observed_evidence_refs: list[dict[str, Any]]
    observed_value: str | None
    expected: dict[str, Any] | None
    rationale: dict[str, Any]


def evaluate_rule_simple_v1(
    *,
    rule: NormRule,
    observation: RuleObservation,
    strict: bool,
) -> tuple[RuleFinding, list[dict[str, Any]]]:
    """Evaluate rule simple v 1 helper."""
    norm_citations = _sorted_norm_citations(rule)
    evidence_refs = _evidence_refs(observation)

    metadata = dict(rule.backend_metadata or {})
    predicate_id = metadata.get("predicate_id")
    operator = metadata.get("operator")
    expected_decimal_raw = metadata.get("value_decimal")
    expected_text_raw = metadata.get("value_text")
    expected_unit_id = metadata.get("unit_id")

    if not isinstance(predicate_id, str):
        predicate_id = observation.predicate_id
    if not isinstance(operator, str):
        operator = None
    if not isinstance(expected_decimal_raw, str):
        expected_decimal_raw = None
    if not isinstance(expected_text_raw, str):
        expected_text_raw = None
    if not isinstance(expected_unit_id, str):
        expected_unit_id = None

    expected_kind: str | None = None
    expected_decimal: Decimal | None = None
    expected_value_text: str | None = None

    if expected_decimal_raw is not None:
        expected_decimal = _parse_decimal(expected_decimal_raw)
        if expected_decimal is not None:
            expected_kind = "numeric"
            expected_value_text = _decimal_to_text(expected_decimal)
    if expected_kind is None:
        text_value = _normalize_text(expected_text_raw or "")
        if text_value in {"true", "false"}:
            expected_kind = "boolean"
            expected_value_text = text_value
        elif text_value:
            expected_kind = "text"
            expected_value_text = text_value

    expected = None
    if operator is not None:
        expected = {
            "op": operator,
            "threshold": expected_value_text,
            "unit": expected_unit_id,
        }

    if not observation.applies:
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status="NOT_APPLICABLE",
            severity=_severity_for_status("NOT_APPLICABLE", strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=None,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=None,
                ),
                "comparison": {"result": None, "reason": "not_applicable"},
            },
        )
        return finding, []

    issues: list[dict[str, Any]] = []
    observed = observation.observed
    if observed is None:
        status = _status_for_unknown(strict)
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=None,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=None,
                ),
                "comparison": {"result": None, "reason": "missing_observed_value"},
            },
        )
        return finding, issues

    if operator is None:
        issues.append(
            {
                "code": "missing_operator",
                "rule_id": rule.norm_id,
                "details": {"predicate_id": predicate_id},
            }
        )
        status = _status_for_unknown(strict)
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=observed.value_text,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=observed.source_kind,
                ),
                "comparison": {"result": None, "reason": "missing_operator"},
            },
        )
        return finding, issues

    if expected_kind is None or expected_value_text is None:
        issues.append(
            {
                "code": "missing_expected_value",
                "rule_id": rule.norm_id,
                "details": {"predicate_id": predicate_id, "operator": operator},
            }
        )
        status = _status_for_unknown(strict)
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=observed.value_text,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=observed.source_kind,
                ),
                "comparison": {"result": None, "reason": "missing_expected_value"},
            },
        )
        return finding, issues

    if expected_kind == "numeric":
        if operator not in _NUMERIC_OPERATORS:
            issues.append(
                {
                    "code": "unsupported_operator",
                    "rule_id": rule.norm_id,
                    "details": {"predicate_id": predicate_id, "operator": operator},
                }
            )
            status = _status_for_unknown(strict)
            finding = RuleFinding(
                rule_id=rule.norm_id,
                status=status,
                severity=_severity_for_status(status, strict=strict),
                norm_citations=norm_citations,
                observed_evidence_refs=evidence_refs,
                observed_value=observed.value_text,
                expected=expected,
                rationale={
                    "predicate_id": predicate_id,
                    "mapping": _mapping_rationale(
                        observation=observation,
                        observed_source=observed.source_kind,
                    ),
                    "comparison": {"result": None, "reason": "unsupported_operator"},
                },
            )
            return finding, issues

        if observed.value_decimal is None:
            issues.append(
                {
                    "code": "type_mismatch",
                    "rule_id": rule.norm_id,
                    "details": {"predicate_id": predicate_id, "expected_kind": "numeric"},
                }
            )
            status = _status_for_unknown(strict)
            finding = RuleFinding(
                rule_id=rule.norm_id,
                status=status,
                severity=_severity_for_status(status, strict=strict),
                norm_citations=norm_citations,
                observed_evidence_refs=evidence_refs,
                observed_value=observed.value_text,
                expected=expected,
                rationale={
                    "predicate_id": predicate_id,
                    "mapping": _mapping_rationale(
                        observation=observation,
                        observed_source=observed.source_kind,
                    ),
                    "comparison": {"result": None, "reason": "type_mismatch"},
                },
            )
            return finding, issues

        observed_decimal = _parse_decimal(observed.value_decimal)
        if observed_decimal is None:
            issues.append(
                {
                    "code": "type_mismatch",
                    "rule_id": rule.norm_id,
                    "details": {"predicate_id": predicate_id, "expected_kind": "numeric"},
                }
            )
            status = _status_for_unknown(strict)
            finding = RuleFinding(
                rule_id=rule.norm_id,
                status=status,
                severity=_severity_for_status(status, strict=strict),
                norm_citations=norm_citations,
                observed_evidence_refs=evidence_refs,
                observed_value=observed.value_text,
                expected=expected,
                rationale={
                    "predicate_id": predicate_id,
                    "mapping": _mapping_rationale(
                        observation=observation,
                        observed_source=observed.source_kind,
                    ),
                    "comparison": {"result": None, "reason": "type_mismatch"},
                },
            )
            return finding, issues

        left_value = observed_decimal
        observed_unit = observed.unit_id
        if not (expected_unit_id is None and observed_unit is None):
            if expected_unit_id is None or observed_unit is None:
                issues.append(
                    {
                        "code": "missing_unit",
                        "rule_id": rule.norm_id,
                        "details": {
                            "predicate_id": predicate_id,
                            "expected_unit_id": expected_unit_id,
                            "observed_unit_id": observed_unit,
                        },
                    }
                )
                status = _status_for_unknown(strict)
                finding = RuleFinding(
                    rule_id=rule.norm_id,
                    status=status,
                    severity=_severity_for_status(status, strict=strict),
                    norm_citations=norm_citations,
                    observed_evidence_refs=evidence_refs,
                    observed_value=_decimal_to_text(observed_decimal),
                    expected=expected,
                    rationale={
                        "predicate_id": predicate_id,
                        "mapping": {
                            "source": observed.source_kind,
                            "notes": list(observation.mapping_notes),
                        },
                        "comparison": {"result": None, "reason": "missing_unit"},
                    },
                )
                return finding, issues
            if expected_unit_id != observed_unit:
                converted = _convert_unit(
                    value=left_value,
                    from_unit=observed_unit,
                    to_unit=expected_unit_id,
                )
                if converted is None:
                    issues.append(
                        {
                            "code": "unit_mismatch",
                            "rule_id": rule.norm_id,
                            "details": {
                                "predicate_id": predicate_id,
                                "expected_unit_id": expected_unit_id,
                                "observed_unit_id": observed_unit,
                            },
                        }
                    )
                    status = _status_for_unknown(strict)
                    finding = RuleFinding(
                        rule_id=rule.norm_id,
                        status=status,
                        severity=_severity_for_status(status, strict=strict),
                        norm_citations=norm_citations,
                        observed_evidence_refs=evidence_refs,
                        observed_value=_decimal_to_text(observed_decimal),
                        expected=expected,
                        rationale={
                            "predicate_id": predicate_id,
                            "mapping": {
                                "source": observed.source_kind,
                                "notes": list(observation.mapping_notes),
                            },
                            "comparison": {"result": None, "reason": "unit_mismatch"},
                        },
                    )
                    return finding, issues
                left_value = converted

        right_value = expected_decimal
        assert right_value is not None

        if operator == "<":
            comparison_result = left_value < right_value
        elif operator == "<=":
            comparison_result = left_value <= right_value
        elif operator == "=":
            comparison_result = left_value == right_value
        elif operator == ">=":
            comparison_result = left_value >= right_value
        else:
            comparison_result = left_value > right_value

        status: FindingStatus = "PASS" if comparison_result else "FAIL"
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=_decimal_to_text(left_value),
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=observed.source_kind,
                ),
                "comparison": {
                    "left": _decimal_to_text(left_value),
                    "op": operator,
                    "right": _decimal_to_text(right_value),
                    "result": comparison_result,
                },
            },
        )
        return finding, issues

    observed_text = _normalize_text(observed.value_text)
    if operator not in _BOOL_TEXT_OPERATORS:
        issues.append(
            {
                "code": "unsupported_operator",
                "rule_id": rule.norm_id,
                "details": {"predicate_id": predicate_id, "operator": operator},
            }
        )
        status = _status_for_unknown(strict)
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=observed_text,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=observed.source_kind,
                ),
                "comparison": {"result": None, "reason": "unsupported_operator"},
            },
        )
        return finding, issues

    if expected_kind == "boolean" and observed_text not in {"true", "false"}:
        issues.append(
            {
                "code": "type_mismatch",
                "rule_id": rule.norm_id,
                "details": {"predicate_id": predicate_id, "expected_kind": "boolean"},
            }
        )
        status = _status_for_unknown(strict)
        finding = RuleFinding(
            rule_id=rule.norm_id,
            status=status,
            severity=_severity_for_status(status, strict=strict),
            norm_citations=norm_citations,
            observed_evidence_refs=evidence_refs,
            observed_value=observed_text,
            expected=expected,
            rationale={
                "predicate_id": predicate_id,
                "mapping": _mapping_rationale(
                    observation=observation,
                    observed_source=observed.source_kind,
                ),
                "comparison": {"result": None, "reason": "type_mismatch"},
            },
        )
        return finding, issues

    comparison_result = observed_text == expected_value_text
    status = "PASS" if comparison_result else "FAIL"
    finding = RuleFinding(
        rule_id=rule.norm_id,
        status=status,
        severity=_severity_for_status(status, strict=strict),
        norm_citations=norm_citations,
        observed_evidence_refs=evidence_refs,
        observed_value=observed_text,
        expected=expected,
        rationale={
            "predicate_id": predicate_id,
            "mapping": _mapping_rationale(
                observation=observation,
                observed_source=observed.source_kind,
            ),
            "comparison": {
                "left": observed_text,
                "op": operator,
                "right": expected_value_text,
                "result": comparison_result,
            },
        },
    )
    return finding, issues


__all__ = [
    "FindingSeverity",
    "FindingStatus",
    "RuleFinding",
    "evaluate_rule_simple_v1",
]
