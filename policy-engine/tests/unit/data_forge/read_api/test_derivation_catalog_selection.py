"""Behavioral tests for the canonical derivation catalog selector owner."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.data_forge import read_api as data_forge_read_api


def _policy(*, family_id: str, purposes: list[str]) -> dict[str, object]:
    return {
        "policy_id": f"{family_id}.{purposes[0]}",
        "family_id": family_id,
        "method_version": "1.0.0",
        "purposes": purposes,
        "country_code": "UA",
        "output_variable_id_template": "{amount_canonical_variable}_real",
        "roles": [
            {
                "role": "amount",
                "catalog_unit": "usd",
                "semantic_anchor": "gross domestic product current usd",
                "owner_metric_id": "gdp",
                "owner_canonical_variable": "gdp",
                "minimum_alignment_confidence": 0.8,
                "allow_proxy": False,
                "require_executable_binding": True,
                "executable_connectors": [],
                "required_themes": [],
                "forbidden_theme_fragments": [],
                "required_text_fragments": ["current"],
                "forbidden_text_fragments": ["per capita"],
            }
        ],
    }


def test_owner_loads_strict_policies_and_resolves_exact_purpose() -> None:
    payload = {
        "catalog_selection_policies": [
            _policy(
                family_id="price_index_exact_year_rebase",
                purposes=["derived_acceptance", "universality_proof"],
            ),
            _policy(family_id="unrelated_family", purposes=["universality_proof"]),
        ],
        "families": [{"family_id": "price_index_exact_year_rebase"}],
    }

    owner = data_forge_read_api.catalog.load_derivation_catalog_selection(payload)
    selected = data_forge_read_api.catalog.resolve_catalog_selection_policy(
        owner,
        purpose="derived_acceptance",
    )

    assert selected.family_id == "price_index_exact_year_rebase"
    assert tuple(
        item.family_id
        for item in data_forge_read_api.catalog.catalog_selection_policies_for_purpose(
            owner,
            purpose="universality_proof",
        )
    ) == ("price_index_exact_year_rebase", "unrelated_family")


def test_in_memory_owner_hash_binds_policy_content() -> None:
    first = _policy(family_id="family_a", purposes=["universality_proof"])
    second = _policy(family_id="family_a", purposes=["universality_proof"])
    second["country_code"] = "GB"

    first_owner = data_forge_read_api.catalog.load_derivation_catalog_selection(
        {"catalog_selection_policies": [first], "families": [{"family_id": "family_a"}]}
    )
    second_owner = data_forge_read_api.catalog.load_derivation_catalog_selection(
        {"catalog_selection_policies": [second], "families": [{"family_id": "family_a"}]}
    )

    assert first_owner.source_sha256 != second_owner.source_sha256


def test_owner_rejects_unsorted_purposes_and_unknown_policy_fields() -> None:
    unsorted = _policy(
        family_id="price_index_exact_year_rebase",
        purposes=["universality_proof", "derived_acceptance"],
    )
    with pytest.raises(ValidationError, match="purposes must be unique and sorted"):
        data_forge_read_api.catalog.CatalogSelectionPolicyConfig.model_validate(unsorted)

    unknown = _policy(family_id="price_index_exact_year_rebase", purposes=["proof"])
    unknown["economic_instance"] = "cpi"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        data_forge_read_api.catalog.CatalogSelectionPolicyConfig.model_validate(unknown)


def test_owner_allows_distinct_same_family_policies_and_rejects_duplicate_identity() -> None:
    proof = _policy(family_id="shared_family", purposes=["universality_proof"])
    route = _policy(family_id="shared_family", purposes=["d6_route"])
    owner = data_forge_read_api.catalog.load_derivation_catalog_selection(
        {
            "catalog_selection_policies": [proof, route],
            "families": [{"family_id": "shared_family"}],
        }
    )
    assert (
        data_forge_read_api.catalog.resolve_catalog_selection_policy(
            owner,
            purpose="d6_route",
            owner_metric_id="gdp",
        ).policy_id
        == "shared_family.d6_route"
    )

    duplicate = dict(route)
    duplicate["policy_id"] = proof["policy_id"]
    with pytest.raises(
        data_forge_read_api.catalog.CatalogSelectionError,
        match="policy identities must be unique",
    ):
        data_forge_read_api.catalog.load_derivation_catalog_selection(
            {
                "catalog_selection_policies": [proof, duplicate],
                "families": [{"family_id": "shared_family"}],
            }
        )


def test_owner_refuses_ambiguous_purpose_metric_resolution() -> None:
    first = _policy(family_id="family_a", purposes=["d6_route"])
    second = _policy(family_id="family_b", purposes=["d6_route"])
    with pytest.raises(
        data_forge_read_api.catalog.CatalogSelectionError,
        match=r"purpose=d6_route/metric=gdp/count=2",
    ):
        data_forge_read_api.catalog.resolve_catalog_selection_policy(
            data_forge_read_api.catalog.load_derivation_catalog_selection(
                {
                    "catalog_selection_policies": [first, second],
                    "families": [{"family_id": "family_a"}, {"family_id": "family_b"}],
                }
            ),
            purpose="d6_route",
            owner_metric_id="gdp",
        )


def test_owner_resolves_exact_family_version_and_refuses_missing_or_ambiguous() -> None:
    first = _policy(family_id="shared_family", purposes=["universality_proof"])
    second = _policy(family_id="shared_family", purposes=["universality_proof"])
    second["policy_id"] = "shared_family.proof.v2"
    second["method_version"] = "2.0.0"
    owner = data_forge_read_api.catalog.load_derivation_catalog_selection(
        {
            "catalog_selection_policies": [first, second],
            "families": [{"family_id": "shared_family"}],
        }
    )

    assert (
        data_forge_read_api.catalog.resolve_catalog_selection_policy(
            owner,
            purpose="universality_proof",
            family_id="shared_family",
            method_version="2.0.0",
        ).policy_id
        == "shared_family.proof.v2"
    )
    with pytest.raises(
        data_forge_read_api.catalog.CatalogSelectionError,
        match=r"family=shared_family/version=3.0.0/count=0",
    ):
        data_forge_read_api.catalog.resolve_catalog_selection_policy(
            owner,
            purpose="universality_proof",
            family_id="shared_family",
            method_version="3.0.0",
        )

    duplicate_version = dict(second)
    duplicate_version["policy_id"] = "shared_family.proof.v2.alternate"
    ambiguous = data_forge_read_api.catalog.load_derivation_catalog_selection(
        {
            "catalog_selection_policies": [first, second, duplicate_version],
            "families": [{"family_id": "shared_family"}],
        }
    )
    with pytest.raises(
        data_forge_read_api.catalog.CatalogSelectionError,
        match=r"family=shared_family/version=2.0.0/count=2",
    ):
        data_forge_read_api.catalog.resolve_catalog_selection_policy(
            ambiguous,
            purpose="universality_proof",
            family_id="shared_family",
            method_version="2.0.0",
        )


def test_candidate_evaluation_rejects_tempting_text_on_wrong_owner_edge() -> None:
    policy = data_forge_read_api.catalog.CatalogSelectionPolicyConfig.model_validate(
        _policy(
            family_id="price_index_exact_year_rebase",
            purposes=["universality_proof"],
        )
    ).role_policy("amount")
    evidence = data_forge_read_api.catalog.CatalogSelectionCandidateEvidence(
        candidate_kind="local_series",
        catalog_unit="usd",
        metric_id="household_income",
        canonical_variable="income",
        title="Gross domestic product current USD",
        description="Exact current monetary flow with very tempting semantic text.",
        access_license="CC-BY-4.0",
        alignment_method="exact",
        alignment_confidence=0.99,
        alignment_is_proxy=False,
        alignment_proxy_penalty=0.0,
        exact_binding_count=1,
        maximum_binding_confidence=0.99,
        maximum_distribution_quality=0.99,
        point_count=3,
        distinct_year_count=3,
        duplicate_year_count=0,
        source_watermark_count=3,
        dataset_version_count=3,
        acquisition_method_count=3,
    )

    result = data_forge_read_api.catalog.evaluate_catalog_selection_candidate(
        policy,
        evidence,
    )

    assert result.eligible is False
    assert result.rejection_codes == (
        data_forge_read_api.catalog.CatalogSelectionRejectionCode.OWNER_CANONICAL_VARIABLE_MISMATCH,
        data_forge_read_api.catalog.CatalogSelectionRejectionCode.OWNER_METRIC_MISMATCH,
    )


def test_shared_owner_toml_is_purpose_addressable() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    owner = data_forge_read_api.catalog.load_derivation_catalog_selection(
        repo_root / "architecture/production_quality/derivation_family_registry.toml"
    )

    selected = data_forge_read_api.catalog.resolve_catalog_selection_policy(
        owner,
        purpose="derived_acceptance",
    )

    assert selected.purposes == ("derived_acceptance", "universality_proof")
