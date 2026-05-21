"""Disconfirming evidence ledgers for Policy Design Case portfolios."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.disconfirming_evidence_ledger.v1"
)
DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID = (
    "policy_design_case.disconfirming_evidence_ledger.v1"
)

_DEFAULT_DEFICIT_PROFILES = frozenset({"exploratory", "research"})
_ACCEPTABLE_DEFICIT_KINDS = frozenset(
    {
        "disconfirming_evidence_deficit",
        "disconfirming_line_deficit",
        "severe_test_unavailable",
        "single_line_evidence_deficit",
    }
)
_DISCONFIRMING_TOKENS = (
    "adversarial",
    "counter",
    "disconfirm",
    "falsif",
    "negative_control",
    "placebo",
    "refut",
    "severe",
    "stress",
)
_FRIENDLY_ONLY_TOKENS = (
    "confirmatory",
    "friendly",
    "positive",
    "supporting",
)


@dataclass(frozen=True)
class DisconfirmingEvidenceLedgerError(ValueError):
    """Fail-closed disconfirming-evidence ledger contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_disconfirming_evidence_ledger(
    *,
    ledger_id: str,
    portfolio_id: str,
    claim_ids: Iterable[str],
    disconfirming_lines: Iterable[object],
    ir_falsification_reports: Iterable[object],
    adversarial_plans: Iterable[object],
    severe_test_records: Iterable[Mapping[str, Any]],
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    accepted_deficits: Iterable[Mapping[str, Any]] = (),
    previous_wave_refs: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Build a normalized ledger from IR, adversarial, and severe-test surfaces."""

    payload: dict[str, Any] = {
        "schema_version": DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION,
        "contract_id": DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID,
        "ledger_id": _required_text(
            ledger_id,
            "ledger_id",
            "policy_design_disconfirming_ledger_id_missing",
        ),
        "portfolio_id": _required_text(
            portfolio_id,
            "portfolio_id",
            "policy_design_disconfirming_portfolio_id_missing",
        ),
        "claim_ids": list(_clean_texts(claim_ids)),
        "disconfirming_lines": [
            _normalizable_mapping_or_value(line) for line in disconfirming_lines
        ],
        "ir_falsification_reports": [
            _normalizable_mapping_or_value(report) for report in ir_falsification_reports
        ],
        "adversarial_plans": [
            _normalizable_mapping_or_value(plan) for plan in adversarial_plans
        ],
        "severe_tests": [dict(record) for record in severe_test_records],
    }
    if evidence_ref is not None:
        payload["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        payload["runtime_event_ref"] = str(runtime_event_ref)
    if previous_wave_refs is not None:
        payload["previous_wave_refs"] = _validate_previous_wave_refs(previous_wave_refs)
    deficits = [dict(deficit) for deficit in accepted_deficits]
    if deficits:
        payload["accepted_deficits"] = deficits
    return payload


def validate_disconfirming_evidence_ledger_record(
    record: Mapping[str, Any],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]] = (),
    evidence_lines: Iterable[Mapping[str, Any]] = (),
    independence_maps: Iterable[Mapping[str, Any]] = (),
    accepted_deficits: Iterable[Mapping[str, Any]] = (),
    effective_authority_profile: str | None = None,
    major_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate and normalize one disconfirming-evidence ledger record."""

    if not isinstance(record, Mapping):
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_ledger_invalid",
            "Disconfirming evidence ledger must be a mapping.",
        )

    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_disconfirming_schema_version_missing",
    )
    if schema_version != DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION:
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_schema_version_invalid",
            "Disconfirming evidence ledger must use the runtime-quality schema version.",
            "schema_version",
        )
    normalized["schema_version"] = DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID
    )
    normalized["ledger_id"] = disconfirming_ledger_record_id(record)
    portfolio_id = disconfirming_ledger_portfolio_id(record)
    normalized["portfolio_id"] = portfolio_id
    claim_ids = _claim_ids(record)
    if not claim_ids:
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_claim_ref_missing",
            "Disconfirming evidence ledger must bind at least one major claim.",
            "claim_ids",
        )
    normalized["claim_ids"] = list(claim_ids)
    required_claim_ids = set(_clean_texts(major_claim_ids))
    if required_claim_ids and required_claim_ids.isdisjoint(claim_ids):
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_claim_ref_missing",
            "Disconfirming evidence ledger does not bind the required major claim.",
            "claim_ids",
        )
    normalized["previous_wave_refs"] = _validate_previous_wave_refs(
        record.get("previous_wave_refs"),
        portfolio_designs=tuple(portfolio_designs),
        evidence_lines=tuple(evidence_lines),
        independence_maps=tuple(independence_maps),
    )

    combined_deficits = [
        *[dict(deficit) for deficit in accepted_deficits if isinstance(deficit, Mapping)],
        *[
            dict(deficit)
            for deficit in _sequence_of_mappings(record.get("accepted_deficits"))
        ],
    ]
    accepted_deficit = disconfirming_deficit_accepted(
        combined_deficits,
        claim_ids=claim_ids,
        effective_authority_profile=effective_authority_profile,
    )

    normalized["disconfirming_lines"] = _validate_disconfirming_lines(
        record.get("disconfirming_lines"),
        accepted_deficit=accepted_deficit,
    )
    if not accepted_deficit:
        _validate_portfolio_disconfirming_lines(
            portfolio_designs,
            portfolio_id=portfolio_id,
            claim_ids=claim_ids,
        )

    normalized["ir_falsification_reports"] = _validate_nonempty_records(
        record.get("ir_falsification_reports")
        or record.get("falsification_reports")
        or record.get("ir_falsification_report_refs"),
        field="ir_falsification_reports",
        missing_code="policy_design_disconfirming_ir_falsification_missing",
        accepted_deficit=accepted_deficit,
    )
    _validate_ir_falsification_reports(normalized["ir_falsification_reports"])

    normalized["adversarial_plans"] = _validate_nonempty_records(
        record.get("adversarial_plans") or record.get("adversarial_plan_refs"),
        field="adversarial_plans",
        missing_code="policy_design_disconfirming_adversarial_plan_missing",
        accepted_deficit=accepted_deficit,
    )
    _validate_adversarial_plans(normalized["adversarial_plans"])

    normalized["severe_tests"] = _validate_nonempty_records(
        record.get("severe_tests")
        or record.get("severe_test_records")
        or record.get("severe_test_refs"),
        field="severe_tests",
        missing_code="policy_design_disconfirming_severe_tests_missing",
        accepted_deficit=accepted_deficit,
    )
    _validate_severe_tests(normalized["severe_tests"], claim_ids=claim_ids)

    evidence_ref = _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_disconfirming_evidence_ref_missing",
    )
    if not _runtime_artifact_ref(evidence_ref):
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_evidence_ref_invalid",
            "Disconfirming evidence ledger evidence_ref must be a runtime artifact ref.",
            "evidence_ref",
        )
    normalized["evidence_ref"] = evidence_ref
    runtime_event_ref = _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_disconfirming_runtime_event_ref_missing",
    )
    if not _runtime_event_ref(runtime_event_ref):
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_runtime_event_ref_invalid",
            "Disconfirming evidence ledger must cite a runtime event ref.",
            "runtime_event_ref",
        )
    normalized["runtime_event_ref"] = runtime_event_ref
    return normalized


def disconfirming_ledger_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for a disconfirming-evidence ledger."""

    return _required_text(
        record.get("ledger_id")
        or record.get("disconfirming_ledger_id")
        or record.get("record_id")
        or record.get("id"),
        "ledger_id",
        "policy_design_disconfirming_ledger_id_missing",
    )


def disconfirming_ledger_portfolio_id(record: Mapping[str, Any]) -> str:
    """Return the bound portfolio id for a disconfirming-evidence ledger."""

    return _required_text(
        record.get("portfolio_id")
        or record.get("portfolio_design_id")
        or record.get("portfolio_ref"),
        "portfolio_id",
        "policy_design_disconfirming_portfolio_id_missing",
    )


def disconfirming_deficit_accepted(
    deficits: Iterable[Mapping[str, Any]],
    *,
    claim_ids: Iterable[str],
    effective_authority_profile: str | None,
) -> bool:
    """Return whether a visible assurance deficit is accepted for this profile."""

    target_claims = set(_clean_texts(claim_ids))
    profile = _profile_text(effective_authority_profile)
    for deficit in deficits:
        if not isinstance(deficit, Mapping):
            continue
        if _text(deficit.get("status") or deficit.get("decision")) != "accepted":
            continue
        kind = _text(
            deficit.get("deficit_kind")
            or deficit.get("kind")
            or deficit.get("code")
            or deficit.get("deficit_code")
        )
        if kind is not None and kind not in _ACCEPTABLE_DEFICIT_KINDS:
            lowered = kind.casefold()
            if "disconfirm" not in lowered and "severe" not in lowered:
                continue
        deficit_claims = set(_claim_ids(deficit))
        if deficit_claims and target_claims and deficit_claims.isdisjoint(target_claims):
            continue
        if not _deficit_profile_allowed(deficit, profile):
            continue
        evidence_ref = _text(deficit.get("evidence_ref") or deficit.get("cas_ref"))
        if not _runtime_artifact_ref(evidence_ref):
            continue
        if not _runtime_event_ref(deficit.get("runtime_event_ref")):
            continue
        return True
    return False


def portfolio_design_has_disconfirming_lines(design: Mapping[str, Any]) -> bool:
    """Return whether a portfolio design predeclares at least one disconfirming line."""

    return any(_line_is_disconfirming(line) for line in _portfolio_disconfirming_lines(design))


def _validate_disconfirming_lines(
    value: object,
    *,
    accepted_deficit: bool,
) -> list[object]:
    lines = _sequence(value)
    disconfirming = [line for line in lines if _line_is_disconfirming(line)]
    if disconfirming or accepted_deficit:
        return [_normalizable_mapping_or_value(line) for line in lines]
    raise DisconfirmingEvidenceLedgerError(
        "policy_design_disconfirming_lines_missing",
        (
            "Disconfirming evidence ledger must include disconfirming lines or "
            "an accepted profile-specific deficit."
        ),
        "disconfirming_lines",
    )


def _validate_portfolio_disconfirming_lines(
    portfolio_designs: Iterable[Mapping[str, Any]],
    *,
    portfolio_id: str,
    claim_ids: tuple[str, ...],
) -> None:
    matched = [
        design
        for design in portfolio_designs
        if isinstance(design, Mapping)
        and _portfolio_design_matches(design, portfolio_id=portfolio_id, claim_ids=claim_ids)
    ]
    if not matched:
        return
    for design in matched:
        if any(_line_is_disconfirming(line) for line in _portfolio_disconfirming_lines(design)):
            return
    raise DisconfirmingEvidenceLedgerError(
        "policy_design_disconfirming_lines_missing",
        (
            "Portfolio design must predeclare disconfirming lines or cite an "
            "accepted profile-specific deficit."
        ),
        "disconfirming_lines",
    )


def _validate_nonempty_records(
    value: object,
    *,
    field: str,
    missing_code: str,
    accepted_deficit: bool,
) -> list[object]:
    records = [_normalizable_mapping_or_value(item) for item in _sequence(value)]
    if records or accepted_deficit:
        return records
    raise DisconfirmingEvidenceLedgerError(
        missing_code,
        f"Disconfirming evidence ledger must include {field}.",
        field,
    )


def _validate_ir_falsification_reports(reports: Sequence[object]) -> None:
    for index, report in enumerate(reports):
        if isinstance(report, str):
            continue
        if not isinstance(report, Mapping):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_disconfirming_ir_falsification_invalid",
                "IR falsification reports must be mappings or refs.",
                f"ir_falsification_reports[{index}]",
            )
        tests = _sequence(report.get("tests"))
        if not tests and not _text(report.get("report_ref") or report.get("ref")):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_disconfirming_ir_falsification_missing",
                "IR falsification report must include tests or a report ref.",
                f"ir_falsification_reports[{index}].tests",
            )


def _validate_adversarial_plans(plans: Sequence[object]) -> None:
    for index, plan in enumerate(plans):
        if isinstance(plan, str):
            continue
        if not isinstance(plan, Mapping):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_disconfirming_adversarial_plan_invalid",
                "Adversarial plans must be mappings or refs.",
                f"adversarial_plans[{index}]",
            )
        if not _text(plan.get("strategy")) and not _text(plan.get("plan_ref") or plan.get("ref")):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_disconfirming_adversarial_plan_missing",
                "Adversarial plan must include a strategy or plan ref.",
                f"adversarial_plans[{index}].strategy",
            )
        if "parameter_specs" in plan and not _sequence(plan.get("parameter_specs")):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_disconfirming_adversarial_plan_invalid",
                "Adversarial plan parameter_specs cannot be empty when present.",
                f"adversarial_plans[{index}].parameter_specs",
            )


def _validate_severe_tests(tests: Sequence[object], *, claim_ids: tuple[str, ...]) -> None:
    target_claims = set(claim_ids)
    for index, test in enumerate(tests):
        if isinstance(test, str):
            continue
        if not isinstance(test, Mapping):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_severe_test_invalid",
                "Severe-test records must be mappings or refs.",
                f"severe_tests[{index}]",
            )
        _required_text(
            test.get("test_id") or test.get("record_id") or test.get("id"),
            f"severe_tests[{index}].test_id",
            "policy_design_severe_test_id_missing",
        )
        _required_text(
            test.get("rationale") or test.get("severity_rationale"),
            f"severe_tests[{index}].rationale",
            "policy_design_severe_test_rationale_missing",
        )
        _required_text(
            test.get("test_kind") or test.get("kind"),
            f"severe_tests[{index}].test_kind",
            "policy_design_severe_test_kind_missing",
        )
        _required_text(
            test.get("severity"),
            f"severe_tests[{index}].severity",
            "policy_design_severe_test_severity_missing",
        )
        test_claims = set(_claim_ids(test))
        if test_claims and target_claims and test_claims.isdisjoint(target_claims):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_severe_test_claim_ref_missing",
                "Severe-test record must bind the ledger major claim.",
                f"severe_tests[{index}].claim_id",
            )
        evidence_ref = _text(test.get("evidence_ref") or test.get("cas_ref"))
        if evidence_ref is not None and not _runtime_artifact_ref(evidence_ref):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_severe_test_evidence_ref_invalid",
                "Severe-test evidence_ref must be a runtime artifact ref.",
                f"severe_tests[{index}].evidence_ref",
            )
        runtime_event_ref = _text(test.get("runtime_event_ref"))
        if runtime_event_ref is not None and not _runtime_event_ref(runtime_event_ref):
            raise DisconfirmingEvidenceLedgerError(
                "policy_design_severe_test_runtime_event_ref_invalid",
                "Severe-test runtime_event_ref must be a runtime event ref.",
                f"severe_tests[{index}].runtime_event_ref",
            )


def _portfolio_design_matches(
    design: Mapping[str, Any],
    *,
    portfolio_id: str,
    claim_ids: tuple[str, ...],
) -> bool:
    ids = _text_values(
        [
            design.get("portfolio_id"),
            design.get("portfolio_design_id"),
            design.get("design_id"),
            design.get("record_id"),
            design.get("cas_ref"),
            design.get("evidence_ref"),
        ]
    )
    if portfolio_id not in ids:
        return False
    design_claims = set(_claim_ids(design))
    return not design_claims or not set(claim_ids).isdisjoint(design_claims)


def _portfolio_disconfirming_lines(design: Mapping[str, Any]) -> list[object]:
    lines = list(_sequence(design.get("disconfirming_lines")))
    strands = design.get("strands")
    if isinstance(strands, Sequence) and not isinstance(strands, str):
        for strand in strands:
            if isinstance(strand, Mapping):
                lines.extend(_sequence(strand.get("disconfirming_lines")))
    return lines


def _line_is_disconfirming(line: object) -> bool:
    if isinstance(line, Mapping):
        text_parts = [
            _text(line.get("stance")),
            _text(line.get("evidence_family")),
            _text(line.get("line_kind")),
            _text(line.get("test_kind")),
            _text(line.get("line_id") or line.get("id")),
        ]
        joined = " ".join(part for part in text_parts if part).casefold()
    else:
        text = _text(line)
        joined = text.casefold() if text else ""
    if not joined:
        return False
    if any(token in joined for token in _FRIENDLY_ONLY_TOKENS) and not any(
        token in joined for token in _DISCONFIRMING_TOKENS
    ):
        return False
    return any(token in joined for token in _DISCONFIRMING_TOKENS)


def _deficit_profile_allowed(deficit: Mapping[str, Any], profile: str | None) -> bool:
    if profile is None:
        return True
    rejected = {
        normalized
        for raw_profile in _text_values(deficit.get("rejected_profiles"))
        if (normalized := _profile_text(raw_profile)) is not None
    }
    if profile in rejected:
        return False
    explicit = {
        normalized
        for raw_profile in _text_values(
            deficit.get("accepted_profiles")
            or deficit.get("permitted_profiles")
            or deficit.get("authority_profiles")
            or deficit.get("profiles")
        )
        if (normalized := _profile_text(raw_profile)) is not None
    }
    if explicit:
        return profile in explicit
    return profile in _DEFAULT_DEFICIT_PROFILES


def _validate_previous_wave_refs(
    value: object,
    *,
    portfolio_designs: Sequence[Mapping[str, Any]] = (),
    evidence_lines: Sequence[Mapping[str, Any]] = (),
    independence_maps: Sequence[Mapping[str, Any]] = (),
) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_previous_wave_refs_missing",
            (
                "Disconfirming evidence ledger must cite previous-wave portfolio, "
                "evidence-line, and independence-map refs."
            ),
            "previous_wave_refs",
        )
    normalized = {
        "portfolio_design_refs": _required_previous_refs(
            value,
            (
                "portfolio_design_refs",
                "portfolio_refs",
                "evidence_portfolio_refs",
            ),
            code="policy_design_disconfirming_previous_wave_portfolio_refs_missing",
            field="previous_wave_refs.portfolio_design_refs",
        ),
        "evidence_line_refs": _required_previous_refs(
            value,
            ("evidence_line_refs", "line_refs", "portfolio_evidence_line_refs"),
            code="policy_design_disconfirming_previous_wave_evidence_line_refs_missing",
            field="previous_wave_refs.evidence_line_refs",
        ),
        "independence_map_refs": _required_previous_refs(
            value,
            (
                "independence_map_refs",
                "evidence_independence_map_refs",
                "independence_refs",
            ),
            code="policy_design_disconfirming_previous_wave_independence_refs_missing",
            field="previous_wave_refs.independence_map_refs",
        ),
    }
    _reject_wave18_phase_refs(normalized)
    _validate_refs_resolve(
        normalized["portfolio_design_refs"],
        rows=portfolio_designs,
        keys=(
            "portfolio_id",
            "portfolio_design_id",
            "design_id",
            "record_id",
            "id",
            "cas_ref",
            "evidence_ref",
        ),
        field="previous_wave_refs.portfolio_design_refs",
    )
    _validate_refs_resolve(
        normalized["evidence_line_refs"],
        rows=evidence_lines,
        keys=("line_id", "evidence_line_id", "record_id", "id", "cas_ref", "evidence_ref"),
        field="previous_wave_refs.evidence_line_refs",
    )
    _validate_refs_resolve(
        normalized["independence_map_refs"],
        rows=independence_maps,
        keys=("map_id", "independence_map_id", "record_id", "id", "cas_ref", "evidence_ref"),
        field="previous_wave_refs.independence_map_refs",
    )
    return normalized


def _required_previous_refs(
    mapping: Mapping[str, object],
    keys: Sequence[str],
    *,
    code: str,
    field: str,
) -> list[str]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_text_values(mapping.get(key)))
    if not refs:
        raise DisconfirmingEvidenceLedgerError(
            code,
            f"Disconfirming evidence ledger must include {field}.",
            field,
        )
    return list(dict.fromkeys(refs))


def _reject_wave18_phase_refs(refs_by_field: Mapping[str, Sequence[str]]) -> None:
    wave18_tokens = ("multiverse", "specification_curve", "disconfirming")
    for field, refs in refs_by_field.items():
        for ref in refs:
            lowered = ref.casefold()
            if any(token in lowered for token in wave18_tokens):
                raise DisconfirmingEvidenceLedgerError(
                    "policy_design_disconfirming_wave18_phase_dependency",
                    "Wave 18 disconfirming ledgers cannot depend on Wave 18 phase refs.",
                    f"previous_wave_refs.{field}",
                )


def _validate_refs_resolve(
    refs: Sequence[str],
    *,
    rows: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
    field: str,
) -> None:
    if not rows:
        return
    index = {ref for row in rows for ref in _row_refs(row, keys)}
    unresolved = [ref for ref in refs if ref not in index]
    if unresolved:
        raise DisconfirmingEvidenceLedgerError(
            "policy_design_disconfirming_previous_wave_ref_unresolved",
            "Disconfirming previous-wave refs must resolve to supplied previous-wave rows.",
            field,
        )


def _row_refs(row: Mapping[str, Any], keys: Sequence[str]) -> set[str]:
    refs: set[str] = set()
    for key in keys:
        refs.update(_text_values(row.get(key)))
    return refs


def _normalizable_mapping_or_value(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        return dict(dumped) if isinstance(dumped, Mapping) else dumped
    return value


def _sequence(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, str):
        text = _text(value)
        return [text] if text is not None else []
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Sequence):
        return [item for item in value if item is not None]
    return []


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _claim_ids(record: Mapping[str, Any]) -> tuple[str, ...]:
    candidates = (
        record.get("claim_ids"),
        record.get("major_claim_ids"),
        record.get("claim_id"),
        record.get("major_claim_id"),
        record.get("claim_ref"),
    )
    ids: list[str] = []
    for candidate in candidates:
        ids.extend(_text_values(candidate))
    return tuple(dict.fromkeys(ids))


def _clean_texts(values: Iterable[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        text = _text(value)
        if text is not None:
            cleaned.append(text)
    return tuple(dict.fromkeys(cleaned))


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text is not None else ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("claim_id", "major_claim_id", "id", "ref", "value"):
            text = _text(value.get(key))
            if text is not None:
                values.append(text)
        return tuple(dict.fromkeys(values))
    if isinstance(value, Iterable):
        values = []
        for item in value:
            values.extend(_text_values(item))
        return tuple(dict.fromkeys(values))
    return ()


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise DisconfirmingEvidenceLedgerError(
            code,
            f"Disconfirming evidence ledger must include {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _profile_text(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text.casefold().replace("-", "_")


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    if text is None or text.startswith(("/", "./", "../", "~", "file://", "repo://")):
        return False
    if text.startswith("sha256:"):
        digest = text.removeprefix("sha256:")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    if text.startswith("cas://sha256/"):
        digest = text.removeprefix("cas://sha256/")
        return len(digest) == 64 and all(char in "0123456789abcdefABCDEF" for char in digest)
    return text.startswith("artifact://")


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    if text is None:
        return False
    return _runtime_artifact_ref(text) or text.startswith("event://")


__all__ = [
    "DISCONFIRMING_EVIDENCE_LEDGER_CONTRACT_ID",
    "DISCONFIRMING_EVIDENCE_LEDGER_SCHEMA_VERSION",
    "DisconfirmingEvidenceLedgerError",
    "build_disconfirming_evidence_ledger",
    "disconfirming_deficit_accepted",
    "disconfirming_ledger_portfolio_id",
    "disconfirming_ledger_record_id",
    "portfolio_design_has_disconfirming_lines",
    "validate_disconfirming_evidence_ledger_record",
]
