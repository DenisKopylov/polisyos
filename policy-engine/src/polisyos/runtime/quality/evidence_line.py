"""Evidence line records for Policy Design Case evidence portfolios."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.runtime.quality.authority import ProducerIdentity
from polisyos.runtime.quality.evidence_portfolio import (
    EvidencePortfolioDesignError,
    portfolio_design_claim_ids,
    portfolio_design_record_id,
    validate_portfolio_predeclaration_before_evidence_acceptance,
)

if TYPE_CHECKING:
    from datetime import datetime

EVIDENCE_LINE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.evidence_line.v1"
EVIDENCE_LINE_CONTRACT_ID = "policy_design_case.evidence_line.v1"
SUPPORTED_EVIDENCE_LINE_STRANDS = (
    "legal",
    "data",
    "literature",
    "method",
    "simulation",
    "distributional",
    "feasibility",
    "monitoring",
)


@dataclass(frozen=True)
class EvidenceLineError(ValueError):
    """Fail-closed evidence-line contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def validate_evidence_line_record(
    record: Mapping[str, Any],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    producer_execution_started_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Validate and normalize one portfolio evidence-line record."""

    if not isinstance(record, Mapping):
        raise EvidenceLineError(
            "policy_design_evidence_line_invalid",
            "Evidence line record must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_evidence_line_schema_version_missing",
    )
    if schema_version != EVIDENCE_LINE_SCHEMA_VERSION:
        raise EvidenceLineError(
            "policy_design_evidence_line_schema_version_invalid",
            "Evidence line record must use the runtime-quality evidence-line schema.",
            "schema_version",
        )
    normalized["schema_version"] = EVIDENCE_LINE_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or EVIDENCE_LINE_CONTRACT_ID
    normalized["line_id"] = evidence_line_record_id(record)
    normalized["portfolio_id"] = _required_text(
        record.get("portfolio_id")
        or record.get("portfolio_design_id")
        or record.get("portfolio_ref"),
        "portfolio_id",
        "policy_design_evidence_line_portfolio_id_missing",
    )

    claim_ids = _claim_ids(record)
    if not claim_ids:
        raise EvidenceLineError(
            "policy_design_evidence_line_claim_ref_missing",
            "Evidence line record must bind at least one major claim.",
            "claim_id",
        )
    normalized["claim_ids"] = list(claim_ids)

    strand = _required_text(
        record.get("evidence_strand") or record.get("strand"),
        "evidence_strand",
        "policy_design_evidence_line_strand_missing",
    )
    if strand not in SUPPORTED_EVIDENCE_LINE_STRANDS:
        raise EvidenceLineError(
            "policy_design_evidence_line_strand_invalid",
            (
                "Evidence line strand must be one of "
                + ", ".join(SUPPORTED_EVIDENCE_LINE_STRANDS)
                + "."
            ),
            "evidence_strand",
        )
    normalized["evidence_strand"] = strand

    normalized["method_id"] = _required_text(
        record.get("method_id")
        or record.get("method_ref")
        or _mapping_text(record.get("method"), "method_id")
        or _mapping_text(record.get("method"), "id"),
        "method_id",
        "policy_design_evidence_line_method_id_missing",
    )
    _require_surface(
        record.get("source_lineage") or record.get("source_lineage_refs"),
        "source_lineage",
        "policy_design_evidence_line_source_lineage_missing",
    )
    _require_surface(
        record.get("method_assumptions")
        or record.get("assumptions")
        or record.get("assumption_refs"),
        "method_assumptions",
        "policy_design_evidence_line_method_assumptions_missing",
    )
    normalized["specification_id"] = _required_text(
        record.get("specification_id")
        or record.get("spec_id")
        or _mapping_text(record.get("specification"), "specification_id")
        or _mapping_text(record.get("specification"), "id"),
        "specification_id",
        "policy_design_evidence_line_specification_id_missing",
    )
    normalized["producer_identity"] = _producer_identity(record.get("producer_identity"))
    _require_surface(
        record.get("execution_context") or record.get("execution_context_ref"),
        "execution_context",
        "policy_design_evidence_line_execution_context_missing",
    )

    _validate_portfolio_binding(
        normalized,
        portfolio_designs=portfolio_designs,
        producer_execution_started_at=producer_execution_started_at,
    )
    return normalized


def validate_evidence_line_records(
    records: Iterable[Mapping[str, Any]],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    producer_execution_started_at: str | datetime | None = None,
) -> list[dict[str, Any]]:
    """Validate a batch of evidence lines against the same portfolio designs."""

    design_rows = tuple(portfolio_designs)
    normalized: list[dict[str, Any]] = []
    seen_line_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise EvidenceLineError(
                "policy_design_evidence_line_invalid",
                "Evidence line rows must be mappings.",
                f"evidence_lines[{index}]",
            )
        line = validate_evidence_line_record(
            record,
            portfolio_designs=design_rows,
            producer_execution_started_at=producer_execution_started_at,
        )
        line_id = str(line["line_id"])
        if line_id in seen_line_ids:
            raise EvidenceLineError(
                "policy_design_evidence_line_id_duplicate",
                "Evidence line ids must be unique within a portfolio evidence set.",
                f"evidence_lines[{index}].line_id",
            )
        seen_line_ids.add(line_id)
        normalized.append(line)
    return normalized


def evidence_line_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for an evidence-line record."""

    return _required_text(
        record.get("line_id")
        or record.get("evidence_line_id")
        or record.get("record_id")
        or record.get("id"),
        "line_id",
        "policy_design_evidence_line_id_missing",
    )


def _producer_identity(value: object) -> dict[str, str]:
    if not _surface_present(value):
        raise EvidenceLineError(
            "policy_design_evidence_line_producer_identity_missing",
            "Evidence line record must include producer_identity.",
            "producer_identity",
        )
    try:
        return ProducerIdentity.model_validate(value).model_dump()
    except ValidationError as exc:
        raise EvidenceLineError(
            "policy_design_evidence_line_producer_identity_invalid",
            "Evidence line producer_identity must include component, version, and owner.",
            "producer_identity",
        ) from exc


def _validate_portfolio_binding(
    line: Mapping[str, Any],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    producer_execution_started_at: str | datetime | None,
) -> None:
    design_rows = tuple(portfolio_designs)
    try:
        validate_portfolio_predeclaration_before_evidence_acceptance(
            portfolio_designs=design_rows,
            major_claim_ids=_claim_ids(line),
            producer_execution_started_at=producer_execution_started_at,
        )
    except EvidencePortfolioDesignError as exc:
        raise EvidenceLineError(exc.code, str(exc), exc.field) from exc

    portfolio_id = _required_text(
        line.get("portfolio_id"),
        "portfolio_id",
        "policy_design_evidence_line_portfolio_id_missing",
    )
    claim_ids = set(_claim_ids(line))
    bound_designs: list[Mapping[str, Any]] = []
    for design in design_rows:
        if not isinstance(design, Mapping):
            continue
        try:
            design_id = portfolio_design_record_id(design)
        except EvidencePortfolioDesignError:
            continue
        if design_id != portfolio_id:
            continue
        if claim_ids and claim_ids.isdisjoint(portfolio_design_claim_ids(design)):
            continue
        bound_designs.append(design)

    if not bound_designs:
        raise EvidenceLineError(
            "policy_design_evidence_line_portfolio_binding_missing",
            "Evidence line record must bind a predeclared portfolio design.",
            "portfolio_id",
        )

    portfolio_strand_id = _text(line.get("portfolio_strand_id") or line.get("strand_id"))
    if portfolio_strand_id is None:
        return
    for design in bound_designs:
        strands = design.get("strands")
        if not isinstance(strands, Sequence) or isinstance(strands, str):
            continue
        for strand in strands:
            if not isinstance(strand, Mapping):
                continue
            if _text(strand.get("strand_id")) != portfolio_strand_id:
                continue
            if claim_ids and claim_ids.isdisjoint(_claim_ids(strand)):
                continue
            return
    raise EvidenceLineError(
        "policy_design_evidence_line_portfolio_strand_binding_missing",
        "Evidence line record must bind an existing portfolio design strand.",
        "portfolio_strand_id",
    )


def _mapping_text(value: object, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    return _text(value.get(key))


def _claim_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    candidates = (
        record.get("claim_ids"),
        record.get("major_claim_ids"),
        record.get("claim_id"),
        record.get("major_claim_id"),
    )
    ids: list[str] = []
    for candidate in candidates:
        ids.extend(_text_values(candidate))
    return tuple(dict.fromkeys(ids))


def _require_surface(value: object, field: str, code: str) -> None:
    if _surface_present(value):
        return
    raise EvidenceLineError(
        code,
        f"Evidence line record must include {field}.",
        field,
    )


def _surface_present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping | list | tuple | set):
        return bool(value)
    return value is not None


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise EvidenceLineError(
            code,
            f"Evidence line record must include {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text is not None else ()
    if isinstance(value, list | tuple | set):
        values: list[str] = []
        for item in value:
            text = _text(item)
            if text is not None:
                values.append(text)
        return tuple(dict.fromkeys(values))
    return ()
