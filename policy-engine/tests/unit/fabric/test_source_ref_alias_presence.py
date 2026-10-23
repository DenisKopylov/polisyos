from __future__ import annotations

import pytest

from polisyos.fabric.catalog.source_selection_audit import (
    _SOURCE_REFERENCE_FACET_ALIASES,
    WAVE13_REQUIRED_SOURCE_FACETS,
    build_fabric_source_selection_trace,
    normalize_fabric_retrieval_trace,
)
from polisyos.runtime.quality.scorecard import normalize_quality_evidence


def _source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "source_id": "production-panel",
        "source_family": "production_panel",
        "source_kind": "production_data",
        "source_rights": "open-data",
        "dataset_ref": "dataset:production-panel",
        "dictionary_ref": "dictionary:production-panel:v1",
        "schema_ref": "schema:production-panel:v1",
        "field_refs": ["field:income"],
        "unit_refs": ["unit:currency"],
        "geography_refs": ["UA"],
        "time_coverage_refs": ["2024-2026"],
        "quality_refs": ["quality:production-panel:v1"],
        "missingness_refs": ["missingness:production-panel:v1"],
        "freshness_refs": ["freshness:production-panel:v1"],
        "lineage_refs": ["lineage:production-panel:v1"],
        "transformation_refs": ["transform:production-panel:v1"],
        "data_forge_snapshot_refs": ["sha256:" + "4" * 64],
        "freshness": {"status": "pass", "as_of": "2026-10-01"},
        "coverage": {"status": "pass", "geography": "UA", "time_window": "2024-2026"},
        "schema_compatibility": {"status": "pass", "required_fields": ["field:income"]},
        "quality": {"status": "pass", "ref": "quality:production-panel:v1"},
        "derived_features": [{"feature_ref": "feature:income"}],
        "relevance_score": 0.95,
        "relevance_rationale": "Matches the declared policy outcome.",
    }
    source.update(overrides)
    return source


def _trace(source: dict[str, object]) -> dict[str, object]:
    return build_fabric_source_selection_trace(
        query_intent={"policy_domain": "income_support"},
        candidate_sources=[source],
        selected_source_ids=["production-panel"],
        rejected_sources=[],
        expected_source_families=["production_panel"],
        canary_kind="production",
    )


def _set_path(source: dict[str, object], path: tuple[str, ...], value: object) -> None:
    current = source
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _remove_path(source: dict[str, object], path: tuple[str, ...]) -> None:
    current: object = source
    for key in path[:-1]:
        if not isinstance(current, dict) or key not in current:
            return
        current = current[key]
    if isinstance(current, dict):
        current.pop(path[-1], None)


def _source_without_aliases(facet: str) -> dict[str, object]:
    source = _source()
    for path in _SOURCE_REFERENCE_FACET_ALIASES[facet]:
        _remove_path(source, path)
    return source


_ISSUE_FOR_REFERENCE_FACET = {
    facet: issue
    for facet, issue, _, facet_kind in WAVE13_REQUIRED_SOURCE_FACETS
    if facet_kind == "reference"
}
_ALIAS_PATH_CASES = tuple(
    (facet, index, path)
    for facet, paths in _SOURCE_REFERENCE_FACET_ALIASES.items()
    for index, path in enumerate(paths)
)
_FACETS_WITH_ALIAS_PATHS = set(_SOURCE_REFERENCE_FACET_ALIASES)


def test_every_required_reference_facet_uses_the_shared_alias_inventory() -> None:
    additive_data_forge_facet = "data_forge_snapshot_refs"
    assert set(_ISSUE_FOR_REFERENCE_FACET) - {additive_data_forge_facet} <= _FACETS_WITH_ALIAS_PATHS


@pytest.mark.parametrize(
    ("facet", "alias_index", "path", "present_value"),
    [
        pytest.param(facet, index, path, value, id=f"{facet}-alias-{index}-{kind}")
        for facet, index, path in _ALIAS_PATH_CASES
        for value, kind in (([], "empty"), (17, "malformed"))
    ],
)
def test_present_alias_does_not_fall_through_to_later_alias_or_default(
    facet: str,
    alias_index: int,
    path: tuple[str, ...],
    present_value: object,
) -> None:
    source = _source_without_aliases(facet)
    _set_path(source, path, present_value)
    paths = _SOURCE_REFERENCE_FACET_ALIASES[facet]
    if alias_index + 1 < len(paths):
        fallback_path = paths[alias_index + 1]
        fallback_value = (
            f"fallback:{facet}"
            if facet in {"dataset_ref", "dictionary_ref", "schema_ref"}
            else [f"fallback:{facet}"]
        )
        _set_path(source, fallback_path, fallback_value)

    trace = _trace(source)
    selected = trace["selected_sources"][0]
    resolved = selected["source_facets"].get(facet)
    assert not (resolved if isinstance(resolved, list) else [resolved] if resolved else [])
    issue = _ISSUE_FOR_REFERENCE_FACET.get(facet)
    if issue is not None:
        assert trace["status"] == "fail"
        assert issue in {item["code"] for item in trace["issues"]}


@pytest.mark.parametrize(
    ("facet", "alias_index", "path"),
    [(facet, index, path) for facet, index, path in _ALIAS_PATH_CASES],
)
def test_each_legacy_alias_remains_a_valid_reference_source(
    facet: str,
    alias_index: int,
    path: tuple[str, ...],
) -> None:
    source = _source_without_aliases(facet)
    ref = f"recognized:{facet}"
    value: object = ref if facet in {"dataset_ref", "dictionary_ref", "schema_ref"} else [ref]
    _set_path(source, path, value)

    trace = _trace(source)
    selected = trace["selected_sources"][0]
    resolved = selected["source_facets"][facet]
    expected: object = ref if facet in {"dataset_ref", "dictionary_ref", "schema_ref"} else [ref]
    assert resolved == expected
    issue = _ISSUE_FOR_REFERENCE_FACET.get(facet)
    if issue is not None:
        assert trace["status"] == "pass"
        assert issue not in {item["code"] for item in trace["issues"]}


@pytest.mark.parametrize(
    ("facet", "path"),
    [
        pytest.param(facet, paths[0], id=f"{facet}-malformed-input")
        for facet, paths in _SOURCE_REFERENCE_FACET_ALIASES.items()
        if facet != "dataset_ref"
    ],
)
def test_malformed_alias_cannot_be_masked_by_a_preprojected_facet(
    facet: str,
    path: tuple[str, ...],
) -> None:
    source = _source_without_aliases(facet)
    _set_path(source, path, 17)
    source["source_facets"] = {facet: f"preprojected:{facet}"}

    trace = _trace(source)
    selected = trace["selected_sources"][0]

    assert not selected["source_facets"].get(facet)
    issue = _ISSUE_FOR_REFERENCE_FACET.get(facet)
    if issue is not None:
        assert trace["status"] == "fail"
        assert issue in {item["code"] for item in trace["issues"]}


@pytest.mark.parametrize(
    ("facet", "path", "present_value", "kind"),
    [
        pytest.param(facet, paths[0], value, kind, id=f"{facet}-present-empty-preprojection-{kind}")
        for facet, paths in _SOURCE_REFERENCE_FACET_ALIASES.items()
        for value, kind in ((None, "null"), ([], "list"), ("", "string"))
    ],
)
def test_present_empty_alias_cannot_be_masked_by_a_preprojected_facet(
    facet: str,
    path: tuple[str, ...],
    present_value: object,
    kind: str,
) -> None:
    source = _source_without_aliases(facet)
    _set_path(source, path, present_value)
    preprojected: object = (
        f"preprojected:{facet}"
        if facet in {"dataset_ref", "dictionary_ref", "schema_ref"}
        else [f"preprojected:{facet}"]
    )
    source["source_facets"] = {facet: preprojected}

    trace = _trace(source)
    selected = trace["selected_sources"][0]

    assert not selected["source_facets"].get(facet)
    issue = _ISSUE_FOR_REFERENCE_FACET.get(facet)
    if issue is not None:
        assert trace["status"] == "fail"
        assert issue in {item["code"] for item in trace["issues"]}


def test_absent_alias_preserves_a_valid_preprojected_facet() -> None:
    source = _source_without_aliases("field_refs")
    source["source_facets"] = {"field_refs": ["field:preprojected"]}

    trace = _trace(source)

    assert trace["status"] == "pass"
    assert trace["selected_sources"][0]["source_facets"]["field_refs"] == ["field:preprojected"]


def test_explicit_empty_field_refs_block_schema_required_fields_fallback() -> None:
    source = _source(
        field_refs=[],
        schema_compatibility={"status": "pass", "required_fields": ["field:income"]},
    )

    trace = _trace(source)

    assert trace["status"] == "fail"
    assert "selected_source_missing_field_refs" in {item["code"] for item in trace["issues"]}
    assert trace["selected_sources"][0]["source_facets"]["field_refs"] == []


def test_malformed_raw_field_alias_cannot_be_masked_by_preprojected_facet() -> None:
    source = _source(
        field_refs=17,
        source_facets={"field_refs": ["field:preprojected"]},
        schema_compatibility={"status": "pass", "required_fields": ["field:income"]},
    )

    trace = _trace(source)

    assert trace["status"] == "fail"
    assert "selected_source_missing_field_refs" in {item["code"] for item in trace["issues"]}
    assert trace["selected_sources"][0]["source_facets"]["field_refs"] == []


@pytest.mark.parametrize(
    "supplied",
    [None, [], "", False, 17, {"field_ref": 17}, {"unrecognized": "field:income"}],
)
def test_present_field_refs_do_not_fall_back_to_schema_required_fields(supplied: object) -> None:
    source = _source(
        field_refs=supplied,
        schema_compatibility={"status": "pass", "required_fields": ["field:income"]},
    )

    trace = _trace(source)

    assert trace["status"] == "fail"
    assert "selected_source_missing_field_refs" in {item["code"] for item in trace["issues"]}


def test_scorecard_consumer_keeps_present_empty_reference_as_a_blocker() -> None:
    source = _source(
        field_refs=[],
        schema_compatibility={"status": "pass", "required_fields": ["field:income"]},
    )
    normalized = normalize_quality_evidence(
        {
            "fabric_retrieval_trace": {
                "status": "pass",
                "query_intent": {"policy_domain": "income_support"},
                "selected_sources": [source],
                "rejected_sources": [],
            }
        },
        canary_kind="production",
    )

    trace = normalized["fabric_retrieval_trace"]
    assert isinstance(trace, dict)
    assert trace["status"] == "fail"
    assert "selected_source_missing_field_refs" in {item["code"] for item in trace["issues"]}


@pytest.mark.parametrize(
    "family",
    [
        " production_panel ",
        "\tproduction_panel\n",
        " Production_Panel ",
    ],
)
@pytest.mark.parametrize("channel", ["normalizer_argument", "report_declared"])
def test_valid_expected_family_text_keeps_legacy_normalization(
    family: str,
    channel: str,
) -> None:
    report = _trace(_source())
    if channel == "report_declared":
        report["expected_source_families"] = [family]
        normalized_value = normalize_quality_evidence(
            {"fabric_retrieval_trace": report},
            canary_kind="production",
        )["fabric_retrieval_trace"]
        assert isinstance(normalized_value, dict)
        normalized = normalized_value
    else:
        normalized = normalize_fabric_retrieval_trace(
            report,
            expected_source_families=[family],
            canary_kind="production",
        )

    assert normalized["expected_source_families"] == ["production_panel"]
    assert normalized["status"] == "pass"
    assert "selected_source_family_not_admissible" not in {
        issue["code"] for issue in normalized["issues"]
    }


def test_malformed_report_expected_family_list_remains_refused() -> None:
    report = _trace(_source())
    report["expected_source_families"] = ["production_panel", 17]

    with pytest.raises(
        ValueError,
        match="fabric_source_selection_expected_source_families_must_be_text_list",
    ):
        normalize_fabric_retrieval_trace(report)


_FAMILY_EXPECTATION_ABSENT = object()
_REPORT_EXPECTATION_CASES = [
    ("absent", _FAMILY_EXPECTATION_ABSENT),
    ("empty", []),
    ("blank-token", [" "]),
    ("padded-match", [" production_panel "]),
    ("case-match", ["PRODUCTION_PANEL"]),
    ("mismatch", ["required-but-unmatched"]),
]
_SUPPLIED_EXPECTATION_CASES = [
    ("absent", None),
    ("empty", []),
    ("blank-token", [" "]),
    ("padded-match", [" production_panel "]),
    ("case-match", ["Production_Panel"]),
    ("mismatch", ["required-but-unmatched"]),
]


@pytest.mark.parametrize(
    ("report_label", "report_families"),
    _REPORT_EXPECTATION_CASES,
    ids=[label for label, _ in _REPORT_EXPECTATION_CASES],
)
@pytest.mark.parametrize(
    ("supplied_label", "supplied_families"),
    _SUPPLIED_EXPECTATION_CASES,
    ids=[label for label, _ in _SUPPLIED_EXPECTATION_CASES],
)
def test_expected_family_precedence_normalizes_both_sources_before_selection(
    report_label: str,
    report_families: object,
    supplied_label: str,
    supplied_families: list[str] | None,
) -> None:
    report = _trace(_source())
    if report_families is _FAMILY_EXPECTATION_ABSENT:
        report.pop("expected_source_families", None)
        normalized_report: list[str] = []
    else:
        report["expected_source_families"] = report_families
        assert isinstance(report_families, list)
        normalized_report = [
            token.strip() for token in report_families if isinstance(token, str) and token.strip()
        ]
    normalized_supplied = (
        []
        if supplied_families is None
        else [
            token.strip() for token in supplied_families if isinstance(token, str) and token.strip()
        ]
    )
    selected = normalized_supplied or normalized_report
    expected = sorted({token.casefold() for token in selected})

    normalized = normalize_fabric_retrieval_trace(
        report,
        expected_source_families=supplied_families,
    )

    assert normalized["expected_source_families"] == expected
    assert normalized["status"] == (
        "pass" if not expected or "production_panel" in expected else "fail"
    )


@pytest.mark.parametrize(
    "report_families",
    [None, 17, "production_panel", {"family": "production_panel"}, ["production_panel", 17]],
    ids=["null", "integer", "string", "mapping", "mixed-list"],
)
@pytest.mark.parametrize("supplied_families", [None, ["production_panel"]], ids=["absent", "valid"])
def test_malformed_report_family_value_is_refused_before_caller_precedence(
    report_families: object,
    supplied_families: list[str] | None,
) -> None:
    report = _trace(_source())
    report["expected_source_families"] = report_families

    with pytest.raises(
        ValueError,
        match="fabric_source_selection_expected_source_families_must_be_text_list",
    ):
        normalize_fabric_retrieval_trace(
            report,
            expected_source_families=supplied_families,
        )


@pytest.mark.parametrize(
    "supplied_families",
    [
        17,
        "production_panel",
        ("production_panel",),
        ["production_panel", 17],
        {"family": "production_panel"},
    ],
    ids=["integer", "string", "tuple", "mixed-list", "mapping"],
)
@pytest.mark.parametrize(
    ("report_label", "report_families"),
    [
        ("absent", _FAMILY_EXPECTATION_ABSENT),
        ("valid", ["production_panel"]),
    ],
    ids=["absent", "valid"],
)
def test_malformed_caller_family_value_is_refused_before_report_fallback(
    supplied_families: object,
    report_label: str,
    report_families: object,
) -> None:
    report = _trace(_source())
    if report_families is _FAMILY_EXPECTATION_ABSENT:
        report.pop("expected_source_families", None)
    else:
        report["expected_source_families"] = report_families

    with pytest.raises(
        ValueError,
        match="fabric_source_selection_expected_source_families_must_be_text_list",
    ):
        normalize_fabric_retrieval_trace(
            report,
            expected_source_families=supplied_families,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "report_families",
    [[], [" "], [" production_panel "], ["required-but-unmatched"]],
    ids=["empty", "blank-token", "padded-match", "mismatch"],
)
def test_scorecard_consumer_preserves_report_expectation_after_normalization(
    report_families: list[str],
) -> None:
    report = _trace(_source())
    report["expected_source_families"] = report_families

    result = normalize_quality_evidence(
        {"fabric_retrieval_trace": report},
        canary_kind="production",
    )
    trace = result["fabric_retrieval_trace"]
    assert isinstance(trace, dict)
    expected = sorted({token.strip().casefold() for token in report_families if token.strip()})
    assert trace["expected_source_families"] == expected
    assert trace["status"] == ("pass" if not expected or "production_panel" in expected else "fail")
