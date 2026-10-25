"""Fabric source-selection quality audit reports for canary evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import TypeAdapter

SCHEMA_VERSION = "policyos.fabric.source_selection_trace.v1"
SERIOUS_CANARY_KINDS = {"production", "governed", "research"}
FIXTURE_MARKERS = ("fixture", "mock", "stub", "demo")
PLAUSIBLE_RELEVANCE_THRESHOLD = 0.5
_FLOAT_ADAPTER = TypeAdapter(float)

WAVE13_REQUIRED_SOURCE_FACETS: tuple[tuple[str, str, str, Literal["text", "reference"]], ...] = (
    (
        "source_rights",
        "selected_source_missing_source_rights",
        "Record source rights/license evidence for every selected Fabric source.",
        "text",
    ),
    (
        "dictionary_ref",
        "selected_source_missing_dictionary_ref",
        "Record the data dictionary ref for every selected Fabric source.",
        "reference",
    ),
    (
        "schema_ref",
        "selected_source_missing_schema_ref",
        "Record the schema ref for every selected Fabric source.",
        "reference",
    ),
    (
        "field_refs",
        "selected_source_missing_field_refs",
        "Record field-level refs for every selected Fabric source.",
        "reference",
    ),
    (
        "unit_refs",
        "selected_source_missing_unit_refs",
        "Record unit refs for every selected Fabric source.",
        "reference",
    ),
    (
        "geography_refs",
        "selected_source_missing_geography_refs",
        "Record geography coverage refs for every selected Fabric source.",
        "reference",
    ),
    (
        "time_coverage_refs",
        "selected_source_missing_time_coverage_refs",
        "Record time coverage refs for every selected Fabric source.",
        "reference",
    ),
    (
        "quality_refs",
        "selected_source_missing_quality_refs",
        "Record quality evidence refs for every selected Fabric source.",
        "reference",
    ),
    (
        "missingness_refs",
        "selected_source_missing_missingness_refs",
        "Record missingness evidence refs for every selected Fabric source.",
        "reference",
    ),
    (
        "freshness_refs",
        "selected_source_missing_freshness_refs",
        "Record freshness evidence refs for every selected Fabric source.",
        "reference",
    ),
    (
        "lineage_refs",
        "selected_source_missing_lineage_refs",
        "Record field/source lineage refs for every selected Fabric source.",
        "reference",
    ),
    (
        "transformation_refs",
        "selected_source_missing_transformation_refs",
        "Record transformation refs for every selected Fabric source.",
        "reference",
    ),
    (
        "data_forge_snapshot_refs",
        "selected_source_missing_data_forge_snapshot_refs",
        "Bind every selected Fabric source to Wave 12 Data Forge snapshot refs.",
        "reference",
    ),
)


def _checked_mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"fabric_source_selection_{field}_must_be_mapping")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"fabric_source_selection_{field}_key_must_be_text")
        result[key] = item
    return result


def _checked_record_list(value: object, *, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"fabric_source_selection_{field}_must_be_list")
    return [_checked_mapping(item, field=f"{field}[{index}]") for index, item in enumerate(value)]


_SOURCE_ROW_MAPPING_FIELDS = (
    "diagnostics",
    "freshness",
    "coverage",
    "schema_compatibility",
    "quality",
    "source_facets",
)
_SOURCE_ROW_LIST_FIELDS = ("derived_features", "derived_feature_bindings")


# These ordered paths are the complete set of source-reference aliases consumed
# by this builder. Presence, rather than truthiness, chooses a legacy alias:
# explicit empty values remain empty evidence and cannot promote a lower alias.
_SOURCE_REFERENCE_FACET_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    "dataset_ref": (("dataset_ref",), ("dataset_id",)),
    "dictionary_ref": (("dictionary_ref",), ("data_dictionary_ref",)),
    "schema_ref": (("schema_ref",), ("schema_id",)),
    "field_refs": (
        ("field_refs",),
        ("fields",),
        ("available_columns",),
        ("columns",),
        ("schema_compatibility", "required_fields"),
    ),
    "unit_refs": (("unit_refs",), ("units",)),
    "geography_refs": (("geography_refs",), ("geography",), ("coverage", "geography")),
    "time_coverage_refs": (
        ("time_coverage_refs",),
        ("time_coverage",),
        ("time_window",),
        ("coverage", "time_window"),
    ),
    "quality_refs": (("quality_refs",), ("quality", "ref")),
    "missingness_refs": (("missingness_refs",), ("missingness",)),
    "freshness_refs": (("freshness_refs",), ("freshness", "ref")),
    "lineage_refs": (("lineage_refs",), ("lineage",)),
    "transformation_refs": (("transformation_refs",), ("transformations",)),
}
_REFERENCE_VALUE_KEYS = (
    "ref",
    "id",
    "artifact_ref",
    "artifact_id",
    "snapshot_ref",
    "manifest_ref",
    "field_ref",
    "source_ref",
    "source_id",
)
_SINGULAR_SOURCE_REFERENCE_FACETS = frozenset({"dataset_ref", "dictionary_ref", "schema_ref"})


def _checked_optional_record_rows(value: object, *, field: str) -> None:
    """Validate the record rows consumed by source and snapshot projections."""
    if value is None:
        return
    if isinstance(value, Mapping):
        _checked_mapping(value, field=f"{field}[0]")
        return
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"fabric_source_selection_{field}_must_be_record_rows")
    for index, row in enumerate(value):
        _checked_mapping(row, field=f"{field}[{index}]")


def _checked_source_row(source: Mapping[str, Any]) -> dict[str, Any]:
    """Check every map/row collection consumed from one source record."""
    checked = _checked_mapping(source, field="source")
    for field in _SOURCE_ROW_MAPPING_FIELDS:
        if field in checked and checked[field] is not None:
            _checked_mapping(checked[field], field=f"source.{field}")
    for field in _SOURCE_ROW_LIST_FIELDS:
        if field in checked:
            _checked_optional_record_rows(checked[field], field=f"source.{field}")
    return checked


def _optional_report_mapping(report: Mapping[str, Any], field: str) -> dict[str, Any] | None:
    if field not in report or report[field] is None:
        return None
    return _checked_mapping(report[field], field=field)


def _report_record_list(report: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    if field not in report:
        return []
    return _checked_record_list(report[field], field=field)


def _report_text_list(report: Mapping[str, Any], field: str) -> list[str] | None:
    if field not in report or report[field] is None:
        return None
    value = report[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"fabric_source_selection_{field}_must_be_text_list")
    return value


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_expected_family_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"fabric_source_selection_{field}_must_be_text_list")
    return [normalized for item in value if (normalized := _text(item))]


def _source_id(source: dict[str, Any]) -> str:
    return _text(source.get("source_id") or source.get("id") or source.get("binding_id"))


def _source_family(source: dict[str, Any]) -> str:
    return _text(
        source.get("source_family") or source.get("family") or source.get("data_source_family")
    )


def _source_kind(source: dict[str, Any]) -> str:
    return _text(source.get("source_kind") or source.get("kind") or source.get("evidence_kind"))


def _status_pass(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    status = _text(value.get("status") or value.get("quality_status")).casefold()
    return status in {"pass", "passed", "ok", "success"}


def _status_value(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    return _text(value.get("status") or value.get("quality_status")).casefold()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _reference_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _issue(
    *,
    code: str,
    message: str,
    source_id: str | None = None,
    severity: str = "fail",
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "fabric_retrieval",
        "phase": "source_selection_audit",
        "source_id": source_id,
        "message": message,
        "next_action": next_action,
    }


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _source_is_fixture_like(source: dict[str, Any]) -> bool:
    if source.get("fixture_or_mock") is True:
        return True
    haystack = " ".join(
        [
            _source_id(source),
            _source_family(source),
            _source_kind(source),
            _text(source.get("source_path")),
        ]
    ).casefold()
    return any(marker in haystack for marker in FIXTURE_MARKERS)


def _source_relevance_score(source: dict[str, Any]) -> float | None:
    raw_score = source.get("relevance_score")
    if raw_score is None:
        raw_score = source.get("score")
    if isinstance(raw_score, bool):
        return None
    try:
        return _FLOAT_ADAPTER.validate_python(raw_score)
    except (TypeError, ValueError):
        return None


def _diagnostics(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diagnostics: dict[str, dict[str, Any]] = {}
    for field in ("freshness", "coverage", "schema_compatibility"):
        value = source.get(field)
        diagnostics[field] = dict(value) if isinstance(value, dict) else {}
    return diagnostics


def _normalize_source(
    source: dict[str, Any],
    *,
    data_forge_snapshot_refs: Sequence[str] = (),
) -> dict[str, Any]:
    source = _checked_source_row(source)
    normalized = dict(source)
    source_id = _source_id(source)
    source_family = _source_family(source)
    source_kind = _source_kind(source)
    if source_id:
        normalized["source_id"] = source_id
    if source_family:
        normalized["source_family"] = source_family
    if source_kind:
        normalized["source_kind"] = source_kind
    normalized["fixture_or_mock"] = _source_is_fixture_like(normalized)
    normalized["diagnostics"] = _diagnostics(normalized)
    source_facets = _source_facets(
        normalized,
        data_forge_snapshot_refs=data_forge_snapshot_refs,
    )
    normalized["source_facets"] = source_facets
    normalized["derived_features"] = _derived_feature_bindings(
        normalized,
        source_facets=source_facets,
    )
    return normalized


def _candidate_index(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = _source_id(source)
        if source_id:
            index[source_id] = source
    return index


def _selected_sources_from_ids(
    *,
    candidate_sources: list[dict[str, Any]],
    selected_source_ids: list[str],
    data_forge_snapshot_refs: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index = _candidate_index(candidate_sources)
    selected: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for source_id in selected_source_ids:
        source = index.get(source_id)
        if source is None:
            issues.append(
                _issue(
                    code="selected_source_missing_candidate",
                    source_id=source_id,
                    message=f"Selected source {source_id} is absent from candidate_sources.",
                    next_action="Record every selected source in the candidate source set.",
                )
            )
            selected.append(
                _normalize_source(
                    {"source_id": source_id},
                    data_forge_snapshot_refs=data_forge_snapshot_refs,
                )
            )
        else:
            selected.append(
                _normalize_source(
                    source,
                    data_forge_snapshot_refs=data_forge_snapshot_refs,
                )
            )
    return selected, issues


def _explicit_rejected_ids(rejected_sources: list[dict[str, Any]]) -> set[str]:
    return {_source_id(source) for source in rejected_sources if _source_id(source)}


def _is_plausible_unselected_candidate(
    source: dict[str, Any],
    *,
    selected_source_ids: set[str],
    explicit_rejected_ids: set[str],
    expected_source_families: set[str],
) -> bool:
    source_id = _source_id(source)
    if not source_id or source_id in selected_source_ids or source_id in explicit_rejected_ids:
        return False
    if source.get("plausible") is False:
        return False
    source_family = _source_family(source).casefold()
    if expected_source_families and source_family in expected_source_families:
        return True
    score = _source_relevance_score(source)
    return score is not None and score >= PLAUSIBLE_RELEVANCE_THRESHOLD


def _merge_rejected_sources(
    *,
    candidate_sources: list[dict[str, Any]],
    selected_source_ids: set[str],
    rejected_sources: list[dict[str, Any]],
    expected_source_families: set[str],
    data_forge_snapshot_refs: Sequence[str],
) -> list[dict[str, Any]]:
    explicit_ids = _explicit_rejected_ids(rejected_sources)
    merged = [
        _normalize_source(source, data_forge_snapshot_refs=data_forge_snapshot_refs)
        for source in rejected_sources
    ]
    for source in candidate_sources:
        if not _is_plausible_unselected_candidate(
            source,
            selected_source_ids=selected_source_ids,
            explicit_rejected_ids=explicit_ids,
            expected_source_families=expected_source_families,
        ):
            continue
        inferred = _normalize_source(
            source,
            data_forge_snapshot_refs=data_forge_snapshot_refs,
        )
        inferred["selection_status"] = "rejected"
        inferred["missing_rejection_reason"] = True
        merged.append(inferred)
    return merged


def _validate_query_intent(query_intent: dict[str, Any]) -> list[dict[str, Any]]:
    if query_intent:
        return []
    return [
        _issue(
            code="missing_query_intent",
            message="Fabric retrieval trace is missing query_intent.",
            next_action="Record outcome, treatment, policy domain, and scenario query intent.",
        )
    ]


def _validate_selected_source(
    source: dict[str, Any],
    *,
    expected_source_families: set[str],
    canary_kind: str,
) -> list[dict[str, Any]]:
    source_id = _source_id(source)
    family = _source_family(source)
    issues: list[dict[str, Any]] = []

    if expected_source_families and family.casefold() not in expected_source_families:
        issues.append(
            _issue(
                code="selected_source_family_not_admissible",
                source_id=source_id,
                message=(
                    f"Selected source family {family or '<missing>'} is not admissible "
                    "for the golden scenario."
                ),
                next_action=(
                    "Select an admissible production source family or update the scenario contract."
                ),
            )
        )

    if canary_kind.casefold() in SERIOUS_CANARY_KINDS and _source_is_fixture_like(source):
        issues.append(
            _issue(
                code="fixture_or_mock_source_selected",
                source_id=source_id,
                message=f"Selected source {source_id} appears to be fixture/mock evidence.",
                next_action=(
                    "Use production data sources for research/governed/production canaries."
                ),
            )
        )

    diagnostic_specs = {
        "freshness": (
            "selected_source_missing_freshness",
            "Record source freshness or last-updated diagnostics.",
        ),
        "coverage": (
            "selected_source_missing_coverage",
            "Record geographic/population/time coverage diagnostics.",
        ),
        "schema_compatibility": (
            "selected_source_missing_schema_compatibility",
            "Record schema compatibility with requested outcome/treatment variables.",
        ),
    }
    for field, (code, next_action) in diagnostic_specs.items():
        diagnostic = source.get(field)
        if _status_pass(diagnostic):
            continue
        if isinstance(diagnostic, dict):
            status = _status_value(diagnostic)
            diagnostic_code = _text(diagnostic.get("code") or diagnostic.get("reason_code"))
            issues.append(
                _issue(
                    code=diagnostic_code or code,
                    source_id=source_id,
                    severity=("warn" if status in {"warn", "warning", "degraded"} else "fail"),
                    message=(
                        _text(diagnostic.get("message"))
                        or (f"Selected source {source_id} has failing {field} diagnostics.")
                    ),
                    next_action=_text(diagnostic.get("next_action")) or next_action,
                )
            )
            continue
        issues.append(
            _issue(
                code=code,
                source_id=source_id,
                message=f"Selected source {source_id} is missing passing {field} diagnostics.",
                next_action=next_action,
            )
        )

    if _text(source.get("relevance_rationale")) == "":
        issues.append(
            _issue(
                code="selected_source_missing_relevance_rationale",
                source_id=source_id,
                message=f"Selected source {source_id} is missing relevance rationale.",
                next_action="Explain why the source matches the scenario outcome and treatment.",
            )
        )
    facets = source.get("source_facets")
    if not isinstance(facets, dict):
        facets = {}
    for field, code, next_action, facet_kind in WAVE13_REQUIRED_SOURCE_FACETS:
        value = facets.get(field)
        if _facet_present(value, facet_kind=facet_kind):
            continue
        issues.append(
            _issue(
                code=code,
                source_id=source_id,
                message=f"Selected source {source_id} is missing {field}.",
                next_action=next_action,
            )
        )
    if not source.get("derived_features"):
        issues.append(
            _issue(
                code="selected_source_missing_derived_feature_bindings",
                source_id=source_id,
                message=(
                    f"Selected source {source_id} is missing derived-feature "
                    "bindings to source facets and claim-support features."
                ),
                next_action=(
                    "Bind derived Fabric features to source_facet_refs and "
                    "claim_support_feature_refs."
                ),
            )
        )
    return issues


def _validate_rejected_source(source: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = _source_id(source)
    reason_code = _text(source.get("reason_code"))
    if reason_code:
        return []
    code = (
        "plausible_rejected_source_missing_reason_code"
        if source.get("missing_rejection_reason") is True
        else "rejected_source_missing_reason_code"
    )
    return [
        _issue(
            code=code,
            source_id=source_id,
            message=f"Rejected source {source_id or '<missing>'} is missing reason_code.",
            next_action="Record why every plausible-but-rejected source was not selected.",
        )
    ]


def _scenario_data_requirements(
    scenario_evidence_contract: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(scenario_evidence_contract, Mapping):
        return []
    if "requirements" not in scenario_evidence_contract:
        return []
    requirements = _checked_record_list(
        scenario_evidence_contract["requirements"], field="scenario_requirements"
    )
    return [
        requirement
        for requirement in requirements
        if _text(requirement.get("domain")).casefold() == "data"
        and _text(requirement.get("expected_family"))
    ]


def _scenario_expected_source_families(
    scenario_evidence_contract: Mapping[str, Any] | None,
) -> list[str]:
    return [
        _text(requirement.get("expected_family"))
        for requirement in _scenario_data_requirements(scenario_evidence_contract)
        if _text(requirement.get("expected_family"))
    ]


def _contract_binding_findings(
    production_data_contract_binding_report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(production_data_contract_binding_report, Mapping):
        return []
    if "scenario_binding_findings" not in production_data_contract_binding_report:
        return []
    return _checked_record_list(
        production_data_contract_binding_report["scenario_binding_findings"],
        field="scenario_binding_findings",
    )


def _scenario_contract_id_from_inputs(
    *,
    scenario_evidence_contract: Mapping[str, Any] | None,
    production_data_contract_binding_report: Mapping[str, Any] | None,
) -> str | None:
    if isinstance(scenario_evidence_contract, Mapping):
        contract_id = _optional_text(scenario_evidence_contract.get("contract_id"))
        if contract_id:
            return contract_id
    if isinstance(production_data_contract_binding_report, Mapping):
        for key in (
            "scenario_contract_id",
            "contract_id",
            "scenario_evidence_contract_id",
        ):
            contract_id = _optional_text(production_data_contract_binding_report.get(key))
            if contract_id:
                return contract_id
    return None


def _contract_finding_family(finding: Mapping[str, Any]) -> str:
    return _text(finding.get("expected_family") or finding.get("source_family"))


def _contract_binding_status(finding: Mapping[str, Any]) -> str:
    binding_status = _text(finding.get("binding_status")).casefold()
    if binding_status in {"selected", "satisfied"}:
        return "satisfied"
    if binding_status in {"blocked", "missing"}:
        return "blocked"
    if binding_status in {"rejected", "failed"}:
        return "failed"
    status = _text(finding.get("status")).casefold()
    if status in {"satisfied", "pass", "passed", "ok"}:
        return "satisfied"
    if status in {"blocked", "missing"}:
        return "blocked"
    return "failed"


def _contract_binding_projection(
    finding: Mapping[str, Any],
    *,
    selection_status: str,
    selected_source_ids: Sequence[str] = (),
    reason_code: str | None = None,
) -> dict[str, Any]:
    payload = {
        "requirement_id": finding.get("requirement_id"),
        "data_requirement_id": finding.get("data_requirement_id"),
        "expected_family": _contract_finding_family(finding),
        "candidate_ref": finding.get("candidate_ref"),
        "status": _contract_binding_status(finding),
        "binding_status": finding.get("binding_status"),
        "selection_status": selection_status,
        "selected_source_ids": list(selected_source_ids),
        "missing_facets": list(finding.get("missing_facets") or ()),
        "present_facets": list(finding.get("present_facets") or ()),
        "claim_bindability_status": finding.get("claim_bindability_status"),
        "claim_bound_limitations": list(finding.get("claim_bound_limitations") or ()),
    }
    if reason_code:
        payload["reason_code"] = reason_code
    for key in ("contract_id", "source_binding_id", "bundle_role", "source_family"):
        if finding.get(key):
            payload[key] = finding.get(key)
    return payload


def _source_family_contract_projection(
    *,
    selected_sources: Sequence[dict[str, Any]],
    expected_families: set[str],
    contract_findings: Sequence[dict[str, Any]],
    contract_required: bool,
) -> dict[str, Any]:
    selected_families: dict[str, list[str]] = {}
    selected_source_ids = {_source_id(source) for source in selected_sources if _source_id(source)}
    for source in selected_sources:
        family = _source_family(source).casefold()
        if not family:
            continue
        selected_families.setdefault(family, []).append(_source_id(source))

    findings_by_family = {
        _contract_finding_family(finding).casefold(): finding
        for finding in contract_findings
        if _contract_finding_family(finding)
    }
    selected_bindings: list[dict[str, Any]] = []
    rejected_bindings: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for expected_family in sorted(expected_families):
        source_ids = selected_families.get(expected_family, [])
        finding = findings_by_family.get(expected_family)
        candidate_ref = _text(finding.get("candidate_ref")) if finding else ""
        candidate_selected = bool(candidate_ref and candidate_ref in selected_source_ids)
        if finding is not None and candidate_selected:
            projection = _contract_binding_projection(
                finding,
                selection_status="selected",
                selected_source_ids=[candidate_ref],
            )
            selected_bindings.append(projection)
            if projection["status"] != "satisfied":
                message = "Selected source family has an incomplete contract binding."
                blocker = {
                    "code": "source_contract_binding_unsatisfied",
                    "status": "failed",
                    "expected_family": expected_family,
                    "candidate_ref": finding.get("candidate_ref"),
                    "missing_facets": list(finding.get("missing_facets") or ()),
                    "selected_source_ids": source_ids,
                    "message": message,
                }
                blockers.append(blocker)
                issues.append(
                    _issue(
                        code="source_contract_binding_unsatisfied",
                        source_id=_text(finding.get("candidate_ref")) or None,
                        message=message,
                        next_action=(
                            "Complete the missing dictionary, schema, field, quality, "
                            "lineage, or claim-bindability facets before selection."
                        ),
                    )
                )
            continue

        if source_ids:
            if finding is not None:
                rejected_bindings.append(
                    _contract_binding_projection(
                        finding,
                        selection_status="rejected",
                        reason_code="contract_candidate_not_selected",
                    )
                )
            if contract_required or contract_findings:
                blocker_code = (
                    "source_contract_binding_candidate_not_selected"
                    if candidate_ref
                    else "source_contract_binding_missing"
                )
                message = (
                    "Selected source family has no selected admissible "
                    "production-data contract binding."
                )
                blocker = {
                    "code": blocker_code,
                    "status": "failed",
                    "expected_family": expected_family,
                    "candidate_ref": candidate_ref or None,
                    "requirement_id": finding.get("requirement_id") if finding else None,
                    "selected_source_ids": source_ids,
                    "message": message,
                }
                blockers.append(blocker)
                issues.append(
                    _issue(
                        code=blocker_code,
                        source_id=candidate_ref or None,
                        message=message,
                        next_action=(
                            "Select the exact production-data contract-index candidate "
                            "or emit a typed source-family blocker."
                        ),
                    )
                )
            continue

        if finding is not None:
            rejected_bindings.append(
                _contract_binding_projection(
                    finding,
                    selection_status="rejected",
                    reason_code="required_source_family_not_selected",
                )
            )
        message = "No selected Fabric source matched the scenario source family."
        blocker = {
            "code": "source_family_mismatch",
            "status": "failed",
            "expected_family": expected_family,
            "selected_source_families": sorted(selected_families),
            "candidate_ref": finding.get("candidate_ref") if finding else None,
            "requirement_id": finding.get("requirement_id") if finding else None,
            "message": message,
        }
        blockers.append(blocker)
        issues.append(
            _issue(
                code="source_family_mismatch",
                source_id=_text(finding.get("candidate_ref")) if finding else None,
                message=message,
                next_action=(
                    "Select a Fabric source whose source_family matches the scenario "
                    "contract, or emit a typed absent-source blocker."
                ),
            )
        )

    for finding in contract_findings:
        family = _contract_finding_family(finding).casefold()
        if family in expected_families:
            continue
        rejected_bindings.append(
            _contract_binding_projection(
                finding,
                selection_status="rejected",
                reason_code="outside_scenario_contract",
            )
        )
    return {
        "selected_contract_bindings": selected_bindings,
        "selected_contract_binding": selected_bindings[0] if selected_bindings else None,
        "rejected_contract_bindings": rejected_bindings,
        "source_family_blockers": blockers,
        "issues": issues,
    }


def _classify_selected_sources(
    selected_sources: Sequence[dict[str, Any]],
    *,
    contract_projection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    selected_contract_source_ids = {
        source_id
        for binding in contract_projection.get("selected_contract_bindings") or []
        if isinstance(binding, Mapping) and _contract_binding_status(binding) == "satisfied"
        for source_id in binding.get("selected_source_ids") or []
        if _text(source_id)
    }
    classified: list[dict[str, Any]] = []
    for source in selected_sources:
        payload = dict(source)
        source_id = _source_id(payload)
        if source_id in selected_contract_source_ids:
            payload["selection_status"] = "claim_admissible_contract_selected"
            payload["authority_surface"] = "claim_admissible_contract"
        else:
            payload["selection_status"] = "non_admissible_context_only"
            payload["authority_surface"] = "context_inventory"
        classified.append(payload)
    return classified


def _fabric_spine_bindings(
    *,
    scenario_contract_id: str | None,
    scenario_evidence_contract: Mapping[str, Any] | None,
    contract_findings: Sequence[dict[str, Any]],
    contract_projection: Mapping[str, Any],
    selected_sources: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    scenario_requirements = _scenario_data_requirements(scenario_evidence_contract)
    requirement_ids = [
        _text(finding.get("requirement_id"))
        for finding in contract_findings
        if _text(finding.get("requirement_id"))
    ]
    requirement_ids.extend(
        _text(requirement.get("requirement_id"))
        for requirement in scenario_requirements
        if _text(requirement.get("requirement_id"))
    )
    selected_bindings = [
        binding
        for binding in contract_projection.get("selected_contract_bindings") or []
        if isinstance(binding, Mapping)
    ]
    rejected_bindings = [
        binding
        for binding in contract_projection.get("rejected_contract_bindings") or []
        if isinstance(binding, Mapping)
    ]
    blockers = [
        blocker
        for blocker in contract_projection.get("source_family_blockers") or []
        if isinstance(blocker, Mapping)
    ]
    return {
        "schema_version": "policyos.fabric.source_selection_spine_bindings.v1",
        "scenario_evidence_contract_id": scenario_contract_id,
        "consumed_requirement_ids": list(dict.fromkeys(requirement_ids)),
        "context_source_refs": [_source_id(source) for source in selected_sources],
        "selected_contract_binding_refs": [
            _text(binding.get("candidate_ref"))
            for binding in selected_bindings
            if _text(binding.get("candidate_ref"))
        ],
        "rejected_contract_binding_refs": [
            _text(binding.get("candidate_ref") or binding.get("requirement_id"))
            for binding in rejected_bindings
            if _text(binding.get("candidate_ref") or binding.get("requirement_id"))
        ],
        "blocked_requirement_ids": [
            _text(blocker.get("requirement_id") or blocker.get("expected_family"))
            for blocker in blockers
            if _text(blocker.get("requirement_id") or blocker.get("expected_family"))
        ],
        "emitted_binding_statuses": [
            {
                "requirement_id": binding.get("requirement_id"),
                "candidate_ref": binding.get("candidate_ref"),
                "status": binding.get("status"),
                "selection_status": binding.get("selection_status"),
                "reason_code": binding.get("reason_code"),
            }
            for binding in (*selected_bindings, *rejected_bindings)
        ],
    }


def build_fabric_source_selection_trace(
    *,
    query_intent: dict[str, Any],
    candidate_sources: list[dict[str, Any]],
    selected_source_ids: list[str],
    rejected_sources: list[dict[str, Any]],
    expected_source_families: list[str] | None = None,
    canary_kind: str = "production",
    materialization_refs: dict[str, Any] | None = None,
    production_data_evidence_context: dict[str, Any] | None = None,
    fabric_retrieval_trace_ref: str | None = None,
    spine_context: Mapping[str, Any] | None = None,
    data_forge_snapshot_binding: Mapping[str, Any] | None = None,
    scenario_evidence_contract: Mapping[str, Any] | None = None,
    production_data_contract_binding_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a strict source-selection audit trace from Fabric candidates."""
    query_intent = _checked_mapping(query_intent, field="query_intent")
    candidate_sources = _checked_record_list(candidate_sources, field="candidate_sources")
    rejected_sources = _checked_record_list(rejected_sources, field="rejected_sources")
    if scenario_evidence_contract is not None:
        scenario_evidence_contract = _checked_mapping(
            scenario_evidence_contract, field="scenario_evidence_contract"
        )
    if production_data_contract_binding_report is not None:
        production_data_contract_binding_report = _checked_mapping(
            production_data_contract_binding_report,
            field="production_data_contract_binding_report",
        )
    if data_forge_snapshot_binding is not None:
        data_forge_snapshot_binding = _checked_mapping(
            data_forge_snapshot_binding, field="data_forge_snapshot_binding"
        )
    if materialization_refs is not None:
        materialization_refs = _checked_mapping(materialization_refs, field="materialization_refs")
    if production_data_evidence_context is not None:
        production_data_evidence_context = _checked_mapping(
            production_data_evidence_context, field="production_data_evidence_context"
        )
    scenario_expected_families = _scenario_expected_source_families(scenario_evidence_contract)
    expected_families = {
        source_family.casefold()
        for source_family in (expected_source_families or scenario_expected_families or [])
        if _text(source_family)
    }
    contract_findings = _contract_binding_findings(production_data_contract_binding_report)
    scenario_contract_id = _scenario_contract_id_from_inputs(
        scenario_evidence_contract=scenario_evidence_contract,
        production_data_contract_binding_report=production_data_contract_binding_report,
    )
    contract_required = bool(
        scenario_evidence_contract
        or scenario_contract_id
        or production_data_contract_binding_report
    )
    materialization = dict(materialization_refs or {})
    data_forge_snapshot_refs = _data_forge_snapshot_refs(
        data_forge_snapshot_binding,
        fallback_refs=_refs_from_value(materialization.get("data_snapshot_ref")),
    )
    normalized_candidate_sources = [
        _normalize_source(
            source,
            data_forge_snapshot_refs=data_forge_snapshot_refs,
        )
        for source in candidate_sources
    ]
    normalized_selected_ids = {
        _text(source_id) for source_id in selected_source_ids if _text(source_id)
    }
    selected_sources, selected_id_issues = _selected_sources_from_ids(
        candidate_sources=normalized_candidate_sources,
        selected_source_ids=sorted(normalized_selected_ids),
        data_forge_snapshot_refs=data_forge_snapshot_refs,
    )
    effective_rejected_sources = _merge_rejected_sources(
        candidate_sources=normalized_candidate_sources,
        selected_source_ids=normalized_selected_ids,
        rejected_sources=rejected_sources,
        expected_source_families=expected_families,
        data_forge_snapshot_refs=data_forge_snapshot_refs,
    )

    issues = _validate_query_intent(query_intent)
    issues.extend(selected_id_issues)
    if not selected_sources:
        issues.append(
            _issue(
                code="no_selected_sources",
                message="Fabric retrieval trace has no selected sources.",
                next_action="Record at least one selected production data source.",
            )
        )

    for source in selected_sources:
        issues.extend(
            _validate_selected_source(
                source,
                expected_source_families=expected_families,
                canary_kind=canary_kind,
            )
        )
    for source in effective_rejected_sources:
        issues.extend(_validate_rejected_source(source))

    contract_projection = _source_family_contract_projection(
        selected_sources=selected_sources,
        expected_families=expected_families,
        contract_findings=contract_findings,
        contract_required=contract_required,
    )
    selected_sources = _classify_selected_sources(
        selected_sources,
        contract_projection=contract_projection,
    )
    issues.extend(contract_projection["issues"])

    status = _status_from_issues(issues)
    trace = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "query_intent": dict(query_intent),
        "expected_source_families": sorted(expected_families),
        "scenario_evidence_contract_id": scenario_contract_id,
        "candidate_sources": normalized_candidate_sources,
        "selected_sources": selected_sources,
        "rejected_sources": effective_rejected_sources,
        "selected_contract_binding": contract_projection["selected_contract_binding"],
        "selected_contract_bindings": contract_projection["selected_contract_bindings"],
        "rejected_contract_bindings": contract_projection["rejected_contract_bindings"],
        "source_family_blockers": contract_projection["source_family_blockers"],
        "scenario_binding_findings": contract_findings,
        "fabric_spine_bindings": _fabric_spine_bindings(
            scenario_contract_id=scenario_contract_id,
            scenario_evidence_contract=scenario_evidence_contract,
            contract_findings=contract_findings,
            contract_projection=contract_projection,
            selected_sources=selected_sources,
        ),
        "materialization_refs": materialization,
        "data_forge_snapshot_refs": list(data_forge_snapshot_refs),
        "production_data_evidence_context": dict(production_data_evidence_context or {}),
        "issues": issues,
        "blocking_issue_count": sum(1 for issue in issues if issue.get("severity") == "fail"),
        "summary": {
            "candidate_source_count": len(candidate_sources),
            "selected_source_count": len(selected_sources),
            "rejected_source_count": len(effective_rejected_sources),
        },
    }
    if spine_context is not None:
        from polisyos.core import contracts as core_contracts

        trace.update(
            core_contracts.build_producer_spine_binding_fields(
                component="fabric",
                spine_context=spine_context,
                candidate_refs=[_source_id(source) for source in normalized_candidate_sources],
                blocker_refs=[issue.get("code") for issue in issues],
            )
        )
    if _text(fabric_retrieval_trace_ref):
        trace["fabric_retrieval_trace_ref"] = _text(fabric_retrieval_trace_ref)
    return trace


def normalize_fabric_retrieval_trace(
    report: object,
    *,
    expected_source_families: list[str] | None = None,
    canary_kind: str = "production",
    data_forge_snapshot_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute Fabric retrieval trace status from source-selection evidence."""
    report = _checked_mapping(report, field="report")
    raw_query_intent = report.get("query_intent")
    query_intent = (
        {} if raw_query_intent is None else _checked_mapping(raw_query_intent, field="query_intent")
    )
    selected_sources = _report_record_list(report, "selected_sources")
    candidate_sources = _report_record_list(report, "candidate_sources")
    if not candidate_sources:
        candidate_sources = list(selected_sources)
    selected_source_ids_value = report.get("selected_source_ids")
    if selected_source_ids_value is None:
        selected_source_ids = [_source_id(source) for source in selected_sources]
    else:
        selected_source_ids = _report_text_list(report, "selected_source_ids") or []
    rejected_sources = _report_record_list(report, "rejected_sources")
    report_expected_families = (
        _normalized_expected_family_list(
            report["expected_source_families"],
            field="expected_source_families",
        )
        if "expected_source_families" in report
        else []
    )
    supplied_expected_families = (
        _normalized_expected_family_list(
            expected_source_families,
            field="expected_source_families",
        )
        if expected_source_families is not None
        else []
    )
    expected = supplied_expected_families or report_expected_families
    scenario_contract_payload = _optional_report_mapping(report, "scenario_evidence_contract")
    contract_binding_report = _optional_report_mapping(
        report, "production_data_contract_binding_report"
    )
    materialization_refs = _optional_report_mapping(report, "materialization_refs")
    production_data_evidence_context = _optional_report_mapping(
        report, "production_data_evidence_context"
    )

    normalized = build_fabric_source_selection_trace(
        query_intent=query_intent,
        candidate_sources=candidate_sources,
        selected_source_ids=[_text(source_id) for source_id in selected_source_ids],
        rejected_sources=rejected_sources,
        expected_source_families=expected,
        canary_kind=canary_kind,
        materialization_refs=materialization_refs,
        production_data_evidence_context=production_data_evidence_context,
        fabric_retrieval_trace_ref=_text(report.get("fabric_retrieval_trace_ref")),
        data_forge_snapshot_binding=data_forge_snapshot_binding,
        scenario_evidence_contract=scenario_contract_payload,
        production_data_contract_binding_report=contract_binding_report,
    )
    consumed_contract_id = _scenario_contract_id_from_inputs(
        scenario_evidence_contract=scenario_contract_payload,
        production_data_contract_binding_report=contract_binding_report,
    )
    original_contract_id = report.get("scenario_evidence_contract_id")
    if original_contract_id is not None and not isinstance(original_contract_id, str):
        raise ValueError("fabric_source_selection_scenario_evidence_contract_id_must_be_text")
    if (
        "scenario_evidence_contract_id" in report
        and consumed_contract_id
        and not _optional_text(original_contract_id)
    ):
        issues = list(normalized.get("issues") or [])
        issues.append(
            _issue(
                code="scenario_evidence_contract_id_dropped",
                message=(
                    "Fabric consumed a scenario evidence contract but emitted a null "
                    "top-level scenario_evidence_contract_id."
                ),
                next_action=(
                    "Promote the consumed scenario contract id to the top-level Fabric "
                    "trace before downstream readers inspect source authority."
                ),
            )
        )
        normalized["issues"] = issues
        normalized["status"] = _status_from_issues(issues)
        normalized["blocking_issue_count"] = sum(
            1 for issue in issues if issue.get("severity") == "fail"
        )
    return {**report, **normalized}


def _source_facets(
    source: Mapping[str, Any],
    *,
    data_forge_snapshot_refs: Sequence[str],
) -> dict[str, Any]:
    existing = source.get("source_facets")
    facets = {} if existing is None else _checked_mapping(existing, field="source.source_facets")
    source_id = _source_id(dict(source))
    freshness_value = source.get("freshness")
    freshness = (
        _checked_mapping(freshness_value, field="source.freshness")
        if freshness_value is not None
        else {}
    )
    quality_value = source.get("quality")
    quality = (
        _checked_mapping(quality_value, field="source.quality") if quality_value is not None else {}
    )

    alias_presence: dict[str, bool] = {}
    for facet, paths in _SOURCE_REFERENCE_FACET_ALIASES.items():
        present, value = _first_present_reference_value(source, paths)
        alias_presence[facet] = present
        if not present:
            continue
        refs = _refs_from_value(value)
        if not _reference_value_is_supported(value) or not refs:
            # A present empty or malformed alias cannot be hidden by preprojected evidence.
            facets[facet] = None if facet in _SINGULAR_SOURCE_REFERENCE_FACETS else ()
            continue
        if facet in facets:
            continue
        if facet in _SINGULAR_SOURCE_REFERENCE_FACETS:
            facets[facet] = refs[0] if refs else None
        else:
            facets[facet] = refs

    facets.setdefault("source_ref", source_id)
    facets.setdefault("source_family", _source_family(dict(source)))
    facets.setdefault(
        "source_rights",
        _optional_text(
            source.get("source_rights") or source.get("rights") or source.get("license")
        ),
    )
    facets.setdefault("dataset_ref", source_id if not alias_presence["dataset_ref"] else None)
    facets.setdefault("dictionary_ref", None)
    facets.setdefault("schema_ref", None)
    for facet in _SOURCE_REFERENCE_FACET_ALIASES:
        if facet in _SINGULAR_SOURCE_REFERENCE_FACETS:
            continue
        if facet == "quality_refs" and not alias_presence[facet]:
            facets.setdefault(
                facet,
                (f"quality:{source_id}",) if source_id and _status_pass(quality) else (),
            )
        elif facet == "freshness_refs" and not alias_presence[facet]:
            facets.setdefault(
                facet,
                (f"freshness:{source_id}",) if source_id and _status_pass(freshness) else (),
            )
        else:
            facets.setdefault(facet, ())
    explicit_data_forge_refs = _refs_from_value(source.get("data_forge_snapshot_refs"))
    facets.setdefault(
        "data_forge_snapshot_refs",
        tuple(dict.fromkeys([*explicit_data_forge_refs, *data_forge_snapshot_refs])),
    )
    return {key: _json_like(value) for key, value in facets.items()}


def _derived_feature_bindings(
    source: Mapping[str, Any],
    *,
    source_facets: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source_ref = _text(source_facets.get("source_ref"))
    rows = source.get("derived_features") or source.get("derived_feature_bindings")
    features: list[dict[str, Any]] = []
    for row in _rows_from(rows):
        item = dict(row)
        item.setdefault("source_ref", source_ref)
        item.setdefault(
            "source_facet_refs",
            list(_refs_from_value(source_facets.get("field_refs"))),
        )
        item.setdefault(
            "claim_support_feature_refs",
            list(_refs_from_value(source.get("claim_support_feature_refs"))),
        )
        features.append({str(key): _json_like(value) for key, value in item.items()})
    return features


def _data_forge_snapshot_refs(
    data_forge_snapshot_binding: Mapping[str, Any] | None,
    *,
    fallback_refs: Sequence[str] = (),
) -> tuple[str, ...]:
    refs: list[str] = []
    if isinstance(data_forge_snapshot_binding, Mapping):
        _checked_optional_record_rows(
            data_forge_snapshot_binding.get("bindings"),
            field="data_forge_snapshot_binding.bindings",
        )
        for row in _rows_from(data_forge_snapshot_binding.get("bindings")):
            for key in ("snapshot_ref", "manifest_ref", "manifest_artifact_id"):
                refs.extend(_refs_from_value(row.get(key)))
        refs.extend(_refs_from_value(data_forge_snapshot_binding.get("data_forge_snapshot_refs")))
    refs.extend(fallback_refs)
    return tuple(dict.fromkeys(refs))


def _first_present_reference_value(
    payload: Mapping[str, Any],
    paths: Sequence[Sequence[str]],
) -> tuple[bool, object]:
    for path in paths:
        current: object = payload
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                break
            current = current[key]
        else:
            return True, current
    return False, None


def _reference_value_is_supported(value: object) -> bool:
    """Return whether a present reference alias uses the existing ref grammar."""
    if value is None or isinstance(value, str):
        return True
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            return False
        recognized_keys = [key for key in _REFERENCE_VALUE_KEYS if key in value]
        return bool(recognized_keys) and all(
            value[key] is None or isinstance(value[key], str) for key in recognized_keys
        )
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return all(_reference_value_is_supported(item) for item in value)
    return False


def _refs_from_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        ref = next(
            (
                reference_text
                for key in _REFERENCE_VALUE_KEYS
                if (reference_text := _reference_text(value.get(key))) is not None
            ),
            None,
        )
        return (ref,) if ref else ()
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    return ()


def _rows_from(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _facet_present(
    value: object,
    *,
    facet_kind: Literal["text", "reference"],
) -> bool:
    if facet_kind == "reference":
        return bool(_refs_from_value(value))
    return isinstance(value, str) and bool(value.strip())


def _json_like(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_like(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_like(item) for item in value]
    if isinstance(value, list):
        return [_json_like(item) for item in value]
    return value


__all__ = [
    "SCHEMA_VERSION",
    "build_fabric_source_selection_trace",
    "normalize_fabric_retrieval_trace",
]
