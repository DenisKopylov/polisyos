from __future__ import annotations

from polisyos.data_requirement import (
    CapabilityRequirementResolution,
    DataRequirementSpec,
)
from polisyos.fabric import project_data_requirement_to_catalog_needs
from polisyos.fabric.catalog.data_requirement_adapter import (
    build_source_contract_requirement_bindings,
)


def test_selected_source_contract_without_matching_requirement_is_rejected() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-msme",
                claim_id="claim-msme",
                families=("production_msme_panel",),
            )
        ],
        source_contract_candidates=[
            {
                "candidate_ref": "production_data:curated:datasets:generic",
                "source_family": "datasets",
                "present_facets": [
                    "source_contract_ref",
                    "dictionary_ref",
                    "schema_ref",
                    "field_refs",
                    "unit_refs",
                    "geography_refs",
                    "time_coverage_refs",
                    "freshness_ref",
                    "lineage_refs",
                    "transformation_refs",
                    "quality_assertion_refs",
                    "missingness_refs",
                    "claim_bindability_refs",
                ],
                "source_contract_validation": {"status": "pass"},
            }
        ],
        selected_candidate_refs=("production_data:curated:datasets:generic",),
    )

    rejected = [
        binding
        for binding in report["source_contract_bindings"]
        if binding["binding_status"] == "rejected"
    ]
    blocked = [
        binding
        for binding in report["source_contract_bindings"]
        if binding["binding_status"] == "blocked"
    ]

    assert report["schema_version"] == "policyos.fabric.data_requirement_bindings.v1"
    assert rejected[0]["candidate_ref"] == "production_data:curated:datasets:generic"
    assert rejected[0]["reason_code"] == "no_matching_data_requirement_spec"
    assert rejected[0]["authority_surface"] == "context_inventory"
    assert blocked[0]["requirement_id"] == "data-requirement:claim-msme"
    assert blocked[0]["reason_code"] == "required_source_family_absent"


def test_unselected_extra_source_contract_is_context_only_and_matching_contract_selected() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-credit",
                claim_id="claim-credit",
                families=("credit_program_registry",),
            )
        ],
        source_contract_candidates=[
            {
                "candidate_ref": "production_data:curated:credit:contract.credit",
                "source_family": "credit_program_registry",
                "present_facets": list(
                    _spec("r", "c", ("credit_program_registry",)).mandatory_facets
                ),
                "source_contract_validation": {"status": "pass"},
            },
            {
                "candidate_ref": "production_data:curated:datasets:generic",
                "source_family": "datasets",
                "present_facets": ["source_contract_ref"],
                "source_contract_validation": {"status": "pass"},
            },
        ],
    )

    statuses = {
        binding["candidate_ref"]: binding["binding_status"]
        for binding in report["source_contract_bindings"]
        if binding.get("candidate_ref")
    }
    assert statuses["production_data:curated:credit:contract.credit"] == "selected"
    assert statuses["production_data:curated:datasets:generic"] == "context_only"
    assert report["summary"] == {
        "requirements": 1,
        "selected": 1,
        "rejected": 0,
        "blocked": 0,
        "context_only": 1,
    }


def test_fabric_consumes_capability_binding_result_with_source_assets_and_rejections() -> None:
    report = build_source_contract_requirement_bindings(
        data_requirement_specs=[
            _spec(
                requirement_id="data-requirement:claim-msme",
                claim_id="claim-msme",
                families=("production_msme_panel",),
            )
        ],
        source_contract_candidates=[],
        capability_bindings=[
            {
                "requirement_id": "data-requirement:claim-msme",
                "status": "selected_proxy_with_limitation",
                "selected_capability_ref": "capability:firm_survival_signal__ua__wartime_2022",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "source_assets": [
                    {
                        "ref": "parquet:dps_financials/firm_fundamentals_annual",
                        "fields": ["revenue", "assets", "employees"],
                    },
                    {
                        "ref": "parquet:distress_events/distress_events_panel_monthly",
                        "fields": ["event_flag", "event_count"],
                    },
                    {
                        "ref": "parquet:dps_tax_risk/compliance_distress_signals_monthly",
                        "fields": ["tax_debt", "risk_score"],
                    },
                ],
                "rights_envelope": {
                    "access_class": "government_administrative",
                    "public_export_allowed": "aggregate_only",
                },
                "quality_score": {"composite": 0.78},
                "limitations": ["Derived survival event; excludes informal firms."],
                "rejected_alternatives": [
                    {
                        "capability_ref": "capability:firm_survival_signal__ua__prewar",
                        "rejection_reason": "time_window_outside_claim",
                        "rejection_severity": "hard",
                    }
                ],
            }
        ],
    )

    selected = next(
        (row for row in report["source_contract_bindings"] if row["binding_status"] == "selected"),
        None,
    )
    rejected = next(
        (row for row in report["source_contract_bindings"] if row["binding_status"] == "rejected"),
        None,
    )
    assert selected is not None, "expected a selected source-contract binding"
    assert rejected is not None, "expected a rejected source-contract binding"

    assert selected["capability_ref"] == "capability:firm_survival_signal__ua__wartime_2022"
    assert selected["construct_ref"] == "construct:firm_survival"
    assert selected["capability_index_ref"] == "capability-index:phase5"
    assert selected["construct_registry_ref"] == "construct-registry:v1"
    assert selected["authority_composition_rule_ref"] == "capability-authority-v1.0"
    assert selected["source_asset_refs"] == [
        "parquet:dps_financials/firm_fundamentals_annual",
        "parquet:distress_events/distress_events_panel_monthly",
        "parquet:dps_tax_risk/compliance_distress_signals_monthly",
    ]
    assert selected["field_refs"] == [
        "assets",
        "employees",
        "event_count",
        "event_flag",
        "revenue",
        "risk_score",
        "tax_debt",
    ]
    assert selected["rights_envelope"]["public_export_allowed"] == "aggregate_only"
    assert selected["quality_score"]["composite"] == 0.78
    assert rejected["capability_ref"] == "capability:firm_survival_signal__ua__prewar"
    assert rejected["reason_code"] == "time_window_outside_claim"
    assert report["summary"]["capability_binding_count"] == 2


def test_catalog_projection_refusal_preserves_unprofiled_typed_scope() -> None:
    spec = _spec(
        requirement_id="data-requirement:ua-health",
        claim_id="claim:ua-health",
        families=("health_panel",),
    ).model_dump(mode="json")

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=spec)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["scope_profile_not_established"]
    assert report["source_scope"] == {
        **spec["scope"],
        "quality_minima": spec["quality_minima"],
        "required_data_families": spec["required_data_families"],
        "recency_horizon": spec["recency_horizon"],
    }


def test_catalog_projection_preserves_same_family_jurisdiction_and_interval() -> None:
    projected = []
    for profile_id, geography, start, end in (
        ("ua-2026", "UA", "2026-01-01", "2026-12-31"),
        ("pl-2027", "PL", "2027-01-01", "2027-12-31"),
    ):
        spec = _profiled_spec(
            profile_id=profile_id,
            geography=geography,
            start=start,
            end=end,
        )
        resolution = _not_established_resolution(
            profile_id=profile_id,
            geography=geography,
            start=start,
            end=end,
            source_family=spec.required_data_families[0],
        )
        payload = spec.model_dump(mode="json")
        payload["capability_requirement_resolutions"] = [resolution.model_dump(mode="json")]
        needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

        assert report["disposition"] == "candidate_only"
        assert report["authority_status"] == "not_established"
        assert report["capability_resolution_status"] == "not_established"
        assert report["budget_status"] == "not_established_at_catalog_boundary"
        assert report["availability_status"] == "not_established_at_catalog_boundary"
        assert needs[0].metric == "health_panel"
        assert needs[0].geography == geography
        assert needs[0].time_start == start
        assert needs[0].time_end == end
        assert needs[0].granularity == "annual"
        assert needs[0].quality_min == spec.quality_minima.min_quality_score
        assert "compiled_requirement_fields_not_enforced_by_catalog_query" in report["limitations"]
        projected.append(needs[0].model_dump(mode="json"))

    assert projected[0] != projected[1]
    assert projected[0]["metric"] == projected[1]["metric"]


def test_catalog_projection_refuses_unrepresentable_budget_and_availability() -> None:
    spec = _profiled_spec(
        profile_id="ua-budgeted",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    spec["catalog_request_context"] = {
        "budget_fields": {"cost_budget_usd": 0},
        "availability_fields": {},
    }
    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=spec)
    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["catalog_zero_budget_unrepresentable"]

    spec["catalog_request_context"] = {
        "budget_fields": {},
        "availability_fields": {"availability_filters": []},
    }
    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=spec)
    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["catalog_availability_filter_unrepresentable"]


def test_catalog_projection_refuses_unrepresentable_time_role() -> None:
    payload = _profiled_spec(
        profile_id="ua-valid-time",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["scope"]["time_role"] = "valid_time"
    payload["metadata"]["scope_profile"]["time_role"] = "valid_time"

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["catalog_time_role_unrepresentable"]


def test_catalog_projection_refuses_interval_without_an_explicit_time_role() -> None:
    payload = _profiled_spec(
        profile_id="ua-unknown-time-role",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["metadata"]["scope_profile"].pop("time_role")

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["catalog_time_role_not_established"]


def test_catalog_projection_keeps_unbounded_time_role_unknown_as_candidate() -> None:
    payload = _profiled_spec(
        profile_id="ua-unbounded-time",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["metadata"]["scope_profile"].pop("time_role")
    payload["metadata"]["scope_profile"]["time_window"] = {
        "start": None,
        "end": None,
    }

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert report["disposition"] == "candidate_only"
    assert report["authority_status"] == "not_established"
    assert report["source_scope"]["time_role"] is None
    assert needs[0].time_start is None
    assert needs[0].time_end is None
    assert "time_role_not_established" in report["limitations"]


def test_catalog_projection_refuses_resolution_geography_and_interval_mismatch() -> None:
    base = _profiled_spec(
        profile_id="ua-2026",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    for geography, start, expected_code in (
        ("PL", "2026-01-01", "capability_resolution_geography_mismatch"),
        ("UA", "2027-01-01", "capability_resolution_time_window_mismatch"),
    ):
        payload = dict(base)
        payload["capability_requirement_resolutions"] = [
            _not_established_resolution(
                profile_id="ua-2026",
                geography=geography,
                start=start,
                end="2026-12-31",
                source_family="health_panel",
            ).model_dump(mode="json")
        ]

        needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

        assert needs == ()
        assert report["disposition"] == "refused"
        assert report["reason_codes"] == [expected_code]


def test_catalog_projection_refuses_resolution_for_an_unrequested_construct() -> None:
    payload = _profiled_spec(
        profile_id="ua-2026",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["metadata"]["scope_profile"]["required_constructs"] = ["correct_construct"]
    payload["capability_requirement_resolutions"] = [
        _not_established_resolution(
            profile_id="ua-2026",
            geography="UA",
            start="2026-01-01",
            end="2026-12-31",
            source_family="health_panel",
        ).model_dump(mode="json")
    ]

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["capability_resolution_construct_mismatch"]


def test_catalog_projection_does_not_let_resolution_supply_missing_geography() -> None:
    payload = _profiled_spec(
        profile_id="profile:unlocated",
        geography="state_or_region",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["scope"]["jurisdiction"] = None
    payload["metadata"]["scope_profile"]["jurisdiction"] = None
    payload["metadata"]["scope_profile"]["time_window"] = {
        "start": None,
        "end": None,
    }
    payload["capability_requirement_resolutions"] = [
        CapabilityRequirementResolution.model_validate(
            {
                "scope_profile_id": "profile:unlocated",
                "query": {
                    "requirement_id": "data-requirement:profile:unlocated:firm_survival",
                    "construct": "firm_survival",
                    "entity_scope": "firm",
                    "population_filter": {"type": "msmes"},
                    "geography": "UA",
                    "time_window": {"start": None, "end": None},
                    "claim_use": "claim_evidence_closeout",
                    "source_family_alias": "health_panel",
                },
                "state": "not_established",
                "binding": None,
                "reason_codes": ["capability_resolver_not_established"],
            }
        ).model_dump(mode="json")
    ]

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["capability_resolution_geography_not_bound_to_requirement"]


def test_catalog_projection_carries_unestablished_geography_without_defaulting() -> None:
    payload = _profiled_spec(
        profile_id="profile:unlocated",
        geography="state_or_region",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["scope"]["jurisdiction"] = None
    payload["metadata"]["scope_profile"]["jurisdiction"] = None
    payload["metadata"]["scope_profile"]["time_window"] = {"start": None, "end": None}

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert report["disposition"] == "candidate_only"
    assert report["source_scope"]["geography"] == "state_or_region"
    assert report["source_scope"]["catalog_geography"] is None
    assert needs[0].geography is None
    assert "geography_not_established" in report["limitations"]


def test_catalog_projection_derives_time_role_domain_from_requirement_schema() -> None:
    payload = _profiled_spec(
        profile_id="ua-unknown-time-role",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    payload["metadata"]["scope_profile"]["time_role"] = "unrecognized_time"

    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=payload)

    assert needs == ()
    assert report["disposition"] == "refused"
    assert report["reason_codes"] == ["scope_profile_time_role_invalid"]


def test_catalog_projection_refuses_missing_granularity_and_profile_mismatch() -> None:
    base = _profiled_spec(
        profile_id="ua-2026",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    base["metadata"]["scope_profile"].pop("granularity")
    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=base)
    assert needs == ()
    assert report["reason_codes"] == ["catalog_granularity_not_established"]

    base = _profiled_spec(
        profile_id="ua-2026",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    base["metadata"]["scope_profile"]["unrepresented_fields"] = ["scope.availability"]
    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=base)
    assert needs == ()
    assert report["reason_codes"] == ["scope_profile_fields_unrepresented"]

    base = _profiled_spec(
        profile_id="ua-2026",
        geography="UA",
        start="2026-01-01",
        end="2026-12-31",
    ).model_dump(mode="json")
    base["capability_requirement_resolutions"] = [
        _not_established_resolution(
            profile_id="pl-2027",
            geography="PL",
            start="2027-01-01",
            end="2027-12-31",
            source_family="health_panel",
        ).model_dump(mode="json")
    ]
    needs, report = project_data_requirement_to_catalog_needs(compiled_requirement_spec=base)
    assert needs == ()
    assert report["reason_codes"] == ["capability_resolution_profile_mismatch"]


def _profiled_spec(
    *,
    profile_id: str,
    geography: str,
    start: str,
    end: str,
) -> DataRequirementSpec:
    payload = _spec(
        requirement_id=f"data-requirement:{profile_id}",
        claim_id=f"claim:{profile_id}",
        families=("health_panel",),
    ).model_dump(mode="json")
    payload["scope"].update({"geography": geography, "jurisdiction": geography})
    payload["metadata"] = {
        "scope_profile": {
            "profile_id": profile_id,
            "jurisdiction": geography,
            "time_window": {"start": start, "end": end},
            "time_role": "observation_time",
            "granularity": "annual",
            "required_constructs": ["firm_survival"],
            "candidate_construct_proposals": [],
        }
    }
    return DataRequirementSpec.model_validate(payload)


def _not_established_resolution(
    *,
    profile_id: str,
    geography: str,
    start: str,
    end: str,
    source_family: str,
) -> CapabilityRequirementResolution:
    return CapabilityRequirementResolution.model_validate(
        {
            "scope_profile_id": profile_id,
            "query": {
                "requirement_id": f"data-requirement:{profile_id}:firm_survival",
                "construct": "firm_survival",
                "entity_scope": "firm",
                "population_filter": {"type": "msmes"},
                "geography": geography,
                "time_window": {"start": start, "end": end},
                "claim_use": "claim_evidence_closeout",
                "source_family_alias": source_family,
            },
            "state": "not_established",
            "binding": None,
            "reason_codes": ["capability_resolver_not_established"],
        }
    )


def _spec(
    requirement_id: str,
    claim_id: str,
    families: tuple[str, ...],
) -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id=requirement_id,
        claim_id=claim_id,
        claim_family="causal",
        claim_type="causal",
        claim_use="decision_support",
        required_data_families=families,
        scope={
            "population": "msmes",
            "geography": "state_or_region",
            "time": "annual",
            "time_role": "observation_time",
        },
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima={"min_quality_score": 0.8, "min_completeness": 0.95},
        missingness_tolerance=0.05,
        transformation_tolerance="traceable",
        admissibility_predicates=(
            "source_family_matches_compiled_requirement",
            "source_contract_active",
        ),
        mandatory_facets=(
            "source_contract_ref",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "freshness_ref",
            "lineage_refs",
            "transformation_refs",
            "quality_assertion_refs",
            "missingness_refs",
            "claim_bindability_refs",
        ),
        facet_refs=("facet:instrument",),
        obligation_refs=("obl:data",),
        concept_spine_refs=("concept:msme",),
        authority_profile_refs=("authority:production",),
    )
