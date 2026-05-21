"""Evidence portfolio design contracts for Policy Design Case major claims."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.evidence_portfolio_design.v1"
)
EVIDENCE_PORTFOLIO_DESIGN_CONTRACT_ID = "policy_design_case.evidence_portfolio_design.v1"


@dataclass(frozen=True)
class EvidencePortfolioDesignError(ValueError):
    """Fail-closed portfolio design contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def validate_evidence_portfolio_design_record(
    record: Mapping[str, Any],
    *,
    major_claim_ids: Iterable[str] = (),
    producer_execution_started_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Validate and normalize a predeclared evidence portfolio design record."""

    if not isinstance(record, Mapping):
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_design_invalid",
            "Evidence portfolio design must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_portfolio_design_schema_version_missing",
    )
    if schema_version != EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION:
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_design_schema_version_invalid",
            "Evidence portfolio design must use the runtime-quality schema version.",
            "schema_version",
        )
    normalized["schema_version"] = EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or EVIDENCE_PORTFOLIO_DESIGN_CONTRACT_ID
    )
    normalized["portfolio_id"] = portfolio_design_record_id(record)
    normalized["claim_ids"] = list(_claim_ids(record))

    if record.get("predeclared") is not True:
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_design_not_predeclared",
            "Evidence portfolio design must be explicitly predeclared.",
            "predeclared",
        )
    declared_at = _parse_datetime_field(
        _required_text(
            record.get("declared_at") or record.get("created_at"),
            "declared_at",
            "policy_design_portfolio_design_declared_at_missing",
        ),
        "declared_at",
        "policy_design_portfolio_design_declared_at_invalid",
    )
    producer_started = _parse_datetime_field(
        producer_execution_started_at,
        "producer_execution_started_at",
        "policy_design_portfolio_producer_execution_time_invalid",
        required=False,
    )
    if (
        producer_started is not None
        and declared_at > producer_started
        and not _has_accepted_exception(record)
    ):
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_design_post_hoc",
            (
                "Evidence portfolio design was declared after producer execution "
                "without an accepted exception."
            ),
            "declared_at",
        )

    _required_text(
        record.get("authority_level"),
        "authority_level",
        "policy_design_portfolio_authority_level_missing",
    )
    for field, code in _PORTFOLIO_TOP_LEVEL_REQUIRED_FIELDS.items():
        _require_surface(record.get(field), field, code)

    strands = record.get("strands")
    if not isinstance(strands, list) or not strands:
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_design_strands_missing",
            "Evidence portfolio design must include one or more claim strands.",
            "strands",
        )

    normalized_strands: list[dict[str, Any]] = []
    for index, strand in enumerate(strands):
        normalized_strands.append(_validate_strand(strand, index=index))
    normalized["strands"] = normalized_strands

    required_claims = tuple(_clean_claim_ids(major_claim_ids))
    if required_claims:
        design_claims = set(normalized["claim_ids"])
        missing_design_claims = [
            claim_id for claim_id in required_claims if claim_id not in design_claims
        ]
        if missing_design_claims:
            raise EvidencePortfolioDesignError(
                "policy_design_portfolio_claim_ref_missing",
                "Evidence portfolio design does not bind all major claims.",
                "claim_ids",
            )
        strand_claims = {
            claim_id
            for strand in normalized_strands
            for claim_id in _claim_ids(strand)
        }
        missing_strand_claims = [
            claim_id for claim_id in required_claims if claim_id not in strand_claims
        ]
        if missing_strand_claims:
            raise EvidencePortfolioDesignError(
                "policy_design_portfolio_strand_claim_ref_missing",
                "Every major claim in the design must have at least one strand.",
                "strands",
            )

    return normalized


def portfolio_design_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for a portfolio design record."""

    return _required_text(
        record.get("portfolio_id")
        or record.get("portfolio_design_id")
        or record.get("design_id")
        or record.get("record_id"),
        "portfolio_id",
        "policy_design_portfolio_id_missing",
    )


def portfolio_design_claim_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Return normalized claim ids for matching scorecard major claims."""

    return _claim_ids(record)


def portfolio_design_refs_by_claim(
    portfolio_designs: Iterable[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Project portfolio design records onto the claim evidence-graph ref axis."""

    refs_by_claim: dict[str, list[str]] = {}
    for record in portfolio_designs:
        if not isinstance(record, Mapping):
            continue
        try:
            portfolio_id = portfolio_design_record_id(record)
        except EvidencePortfolioDesignError:
            continue
        for claim_id in portfolio_design_claim_ids(record):
            refs = refs_by_claim.setdefault(claim_id, [])
            if portfolio_id not in refs:
                refs.append(portfolio_id)
    return refs_by_claim


def validate_portfolio_predeclaration_before_evidence_acceptance(
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    major_claim_ids: Iterable[str],
    producer_execution_started_at: str | datetime | None = None,
    authority_profile_blockers: Iterable[Mapping[str, Any]] = (),
    effective_authority_profile: str | None = None,
) -> dict[str, Any]:
    """Producer-facing guard before evidence lines or execution results are accepted."""

    claim_ids = _clean_claim_ids(major_claim_ids)
    design_rows: list[Mapping[str, Any]] = []
    for index, design in enumerate(portfolio_designs):
        if not isinstance(design, Mapping):
            raise EvidencePortfolioDesignError(
                "policy_design_portfolio_design_invalid",
                "Evidence portfolio design rows must be mappings.",
                f"portfolio_designs[{index}]",
            )
        design_rows.append(design)
    blocker_rows = tuple(authority_profile_blockers)
    accepted_claim_ids: list[str] = []
    blocked_claim_ids: list[str] = []
    portfolio_design_ids: list[str] = []

    for claim_id in claim_ids:
        if _authority_profile_blocks_portfolio_design(
            blocker_rows,
            claim_id=claim_id,
            effective_authority_profile=effective_authority_profile,
        ):
            blocked_claim_ids.append(claim_id)
            continue

        matched_designs = tuple(
            design for design in design_rows if claim_id in set(_claim_ids(design))
        )
        if not matched_designs:
            raise EvidencePortfolioDesignError(
                "policy_design_major_claim_portfolio_missing",
                (
                    f"Major claim {claim_id!r} must have a predeclared evidence "
                    "portfolio design before evidence lines or producer execution "
                    "results can be accepted."
                ),
                "portfolio_designs",
            )

        for design in matched_designs:
            validated = validate_evidence_portfolio_design_record(
                design,
                major_claim_ids=[claim_id],
                producer_execution_started_at=producer_execution_started_at,
            )
            portfolio_design_ids.append(str(validated["portfolio_id"]))
        accepted_claim_ids.append(claim_id)

    return {
        "status": "blocked" if blocked_claim_ids else "pass",
        "accepted_claim_ids": accepted_claim_ids,
        "blocked_claim_ids": blocked_claim_ids,
        "portfolio_design_ids": list(dict.fromkeys(portfolio_design_ids)),
        "producer_execution_started_at": _datetime_input_to_text(
            producer_execution_started_at
        ),
        "contract_id": EVIDENCE_PORTFOLIO_DESIGN_CONTRACT_ID,
    }


_PORTFOLIO_TOP_LEVEL_REQUIRED_FIELDS = {
    "candidate_data_source_families": "policy_design_portfolio_candidate_data_missing",
    "candidate_method_families": "policy_design_portfolio_candidate_methods_missing",
    "inclusion_rules": "policy_design_portfolio_inclusion_rules_missing",
    "exclusion_rules": "policy_design_portfolio_exclusion_rules_missing",
    "disconfirming_lines": "policy_design_portfolio_disconfirming_lines_missing",
    "synthesis_rules": "policy_design_portfolio_synthesis_rules_missing",
    "stopping_rules": "policy_design_portfolio_stopping_rules_missing",
    "cost_proportionality": "policy_design_portfolio_cost_proportionality_missing",
}

_STRAND_REQUIRED_FIELDS = {
    "strand_id": "policy_design_portfolio_strand_id_missing",
    "authority_level": "policy_design_portfolio_strand_authority_level_missing",
    "candidate_data_source_families": "policy_design_portfolio_candidate_data_missing",
    "candidate_method_families": "policy_design_portfolio_candidate_methods_missing",
    "defensible_specification_space": (
        "policy_design_portfolio_specification_space_missing"
    ),
    "inclusion_rules": "policy_design_portfolio_inclusion_rules_missing",
    "exclusion_rules": "policy_design_portfolio_exclusion_rules_missing",
    "disconfirming_lines": "policy_design_portfolio_disconfirming_lines_missing",
    "synthesis_rules": "policy_design_portfolio_synthesis_rules_missing",
    "stopping_rules": "policy_design_portfolio_stopping_rules_missing",
    "cost_proportionality": "policy_design_portfolio_cost_proportionality_missing",
}


def _validate_strand(strand: object, *, index: int) -> dict[str, Any]:
    if not isinstance(strand, Mapping):
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_strand_invalid",
            "Evidence portfolio design strands must be mappings.",
            f"strands[{index}]",
        )
    normalized = dict(strand)
    if not _claim_ids(strand):
        raise EvidencePortfolioDesignError(
            "policy_design_portfolio_strand_claim_ref_missing",
            "Evidence portfolio strands must name their major claim.",
            f"strands[{index}].claim_id",
        )
    for field, code in _STRAND_REQUIRED_FIELDS.items():
        _require_surface(strand.get(field), f"strands[{index}].{field}", code)
    normalized["claim_ids"] = list(_claim_ids(strand))
    return normalized


def _has_accepted_exception(record: Mapping[str, Any]) -> bool:
    for field in ("accepted_exception_ref", "accepted_exception_refs"):
        if _text_values(record.get(field)):
            return True
    exception = record.get("accepted_exception")
    if isinstance(exception, Mapping) and _exception_accepted(exception):
        return True
    exceptions = record.get("accepted_exceptions")
    if isinstance(exceptions, list):
        return any(isinstance(item, Mapping) and _exception_accepted(item) for item in exceptions)
    return False


def _exception_accepted(exception: Mapping[str, Any]) -> bool:
    status = _text(exception.get("status") or exception.get("decision"))
    if status != "accepted":
        return False
    return bool(
        _text(exception.get("exception_ref"))
        or _text(exception.get("evidence_ref"))
        or _text(exception.get("cas_ref"))
    )


def _authority_profile_blocks_portfolio_design(
    blockers: Iterable[Mapping[str, Any]],
    *,
    claim_id: str,
    effective_authority_profile: str | None,
) -> bool:
    for blocker in blockers:
        if _text(blocker.get("status") or blocker.get("decision")) != "blocked":
            continue
        blocker_claims = set(_claim_ids(blocker))
        if blocker_claims and claim_id not in blocker_claims:
            continue
        blocker_profile = _text(
            blocker.get("authority_profile")
            or blocker.get("effective_execution_profile")
            or blocker.get("profile")
        )
        if (
            blocker_profile
            and effective_authority_profile
            and blocker_profile != effective_authority_profile
        ):
            continue
        if not _text(blocker.get("code")):
            continue
        if not _text(blocker.get("message") or blocker.get("downstream_impact")):
            continue
        if not _text(blocker.get("evidence_ref") or blocker.get("cas_ref")):
            continue
        if not _text(blocker.get("runtime_event_ref")):
            continue
        return True
    return False


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


def _clean_claim_ids(values: Iterable[str]) -> tuple[str, ...]:
    ids: list[str] = []
    for value in values:
        text = _text(value)
        if text is not None:
            ids.append(text)
    return tuple(dict.fromkeys(ids))


def _require_surface(value: object, field: str, code: str) -> None:
    if _surface_present(value):
        return
    raise EvidencePortfolioDesignError(
        code,
        f"Evidence portfolio design must include {field}.",
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
        raise EvidencePortfolioDesignError(
            code,
            f"Evidence portfolio design must include {field}.",
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


def _datetime_input_to_text(value: str | datetime | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return _text(value)


def _parse_datetime_field(
    value: object,
    field: str,
    code: str,
    *,
    required: bool = True,
) -> datetime | None:
    if value is None and not required:
        return None
    if isinstance(value, datetime):
        return value
    text = _text(value)
    if text is None:
        if not required:
            return None
        raise EvidencePortfolioDesignError(
            code,
            f"Evidence portfolio design must include a valid {field}.",
            field,
        )
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidencePortfolioDesignError(
            code,
            f"Evidence portfolio design has invalid {field}.",
            field,
        ) from exc
