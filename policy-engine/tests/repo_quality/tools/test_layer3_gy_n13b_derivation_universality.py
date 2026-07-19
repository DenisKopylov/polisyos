"""Behavioral tests for the data-only N13b derivation universality proof."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest
from pydantic import ValidationError

from tools.quality.validation import layer3_gy_n13b_derivation_universality as universality
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_DERIVATION_FAMILY_REGISTRY,
    DerivationUniversalityReceipt,
    build_derivation_universality_receipt,
    parse_derivation_universality_receipt,
    write_derivation_universality_receipt,
)

_PRICE_FAMILY = """
[[catalog_selection_policies]]
policy_id = "synthetic_index_rebase.proof"
family_id = "synthetic_index_rebase"
method_version = "7.0.0"
purposes = ["universality_proof"]
country_code = "UA"
output_variable_id_template = "{amount_canonical_variable}_real"

[[catalog_selection_policies.roles]]
role = "amount"
catalog_unit = "usd"
semantic_anchor = "cash flow current usd"
owner_metric_id = "savings"
owner_canonical_variable = "savings"
minimum_alignment_confidence = 0.8
allow_proxy = false
require_executable_binding = true
executable_connectors = []
required_themes = []
forbidden_theme_fragments = []
required_text_fragments = []
forbidden_text_fragments = []

[[catalog_selection_policies.roles]]
role = "index"
catalog_unit = "index"
semantic_anchor = "consumer price index level"
owner_metric_id = "price_level"
owner_canonical_variable = "price_level"
minimum_alignment_confidence = 0.8
allow_proxy = false
require_executable_binding = true
executable_connectors = []
required_themes = []
forbidden_theme_fragments = []
required_text_fragments = ["consumer price index"]
forbidden_text_fragments = []

[[families]]
family_id = "synthetic_index_rebase"
method_id = "arithmetic.synthetic.index_rebase"
method_version = "7.0.0"
year_domain_role = "amount"
input_specs = [
  { role = "amount", basis = { quantity_kind = "cash_flow", unit = "usd", attributes = [{ name = "price_basis", value = "current" }] }, value_constraints = [] },
  { role = "index", basis = { quantity_kind = "level_index", unit = "index", attributes = [] }, value_constraints = ["positive"] },
]
output_basis = { quantity_kind = "cash_flow", unit = "usd", attributes = [{ name = "price_basis", value = "constant" }, { name = "reference_year", value = "${reference_year}" }] }
parameter_rules = [
  { name = "reference_year", operator = "lower_median_common_year", input_roles = ["amount", "index"] },
]
output_parameter_bindings = [
  { parameter_name = "reference_year", output_attribute = "reference_year" },
]
expression = { operator = "divide", operands = [{ operator = "multiply", operands = [{ operator = "current_value", role = "amount" }, { operator = "value_at_parameter", role = "index", parameter_name = "reference_year" }] }, { operator = "current_value", role = "index" }] }
assumption_rules = [
  { name = "formula", literal_value = "amount_t * index_reference_year / index_t" },
  { name = "reference_year", parameter_name = "reference_year" },
]
"""

_NOVEL_FAMILY = """
[[catalog_selection_policies]]
policy_id = "novel_share_scale_77.proof"
family_id = "novel_share_scale_77"
method_version = "3.2.1"
purposes = ["universality_proof"]
country_code = "UA"
output_variable_id_template = "{share_canonical_variable}_amount"

[[catalog_selection_policies.roles]]
role = "share"
catalog_unit = "percent_gdp"
semantic_anchor = "share of aggregate"
owner_metric_id = "balance_share"
owner_canonical_variable = "balance_share"
minimum_alignment_confidence = 0.8
allow_proxy = false
require_executable_binding = true
executable_connectors = []
required_themes = []
forbidden_theme_fragments = []
required_text_fragments = []
forbidden_text_fragments = []

[[catalog_selection_policies.roles]]
role = "total"
catalog_unit = "usd"
semantic_anchor = "aggregate current usd"
owner_metric_id = "gdp"
owner_canonical_variable = "gdp"
minimum_alignment_confidence = 0.8
allow_proxy = false
require_executable_binding = true
executable_connectors = []
required_themes = []
forbidden_theme_fragments = []
required_text_fragments = []
forbidden_text_fragments = []

[[families]]
family_id = "novel_share_scale_77"
method_id = "arithmetic.synthetic.share_times_total"
method_version = "3.2.1"
year_domain_role = "share"
input_specs = [
  { role = "share", basis = { quantity_kind = "share_of_aggregate", unit = "percent", attributes = [{ name = "denominator", value = "output_scale" }] }, value_constraints = [] },
  { role = "total", basis = { quantity_kind = "aggregate_flow", unit = "usd", attributes = [] }, value_constraints = ["nonnegative"] },
]
output_basis = { quantity_kind = "absolute_flow", unit = "usd", attributes = [] }
parameter_rules = []
output_parameter_bindings = []
expression = { operator = "divide", operands = [{ operator = "multiply", operands = [{ operator = "current_value", role = "share" }, { operator = "current_value", role = "total" }] }, { operator = "constant", constant_value = "100" }] }
assumption_rules = [
  { name = "formula", literal_value = "share_t * total_t / 100" },
  { name = "year_join", literal_value = "exact; no interpolation" },
]
"""


def _create_catalog(path: Path) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE ds_datasets (
              id VARCHAR PRIMARY KEY, source VARCHAR, agency VARCHAR,
              title VARCHAR, description VARCHAR, license VARCHAR,
              access_license VARCHAR
            );
            CREATE TABLE ds_distributions (
              id VARCHAR PRIMARY KEY, dataset_id VARCHAR, quality_score FLOAT
            );
            CREATE TABLE ds_metric_bindings (
              metric_id VARCHAR, dataset_id VARCHAR, distribution_id VARCHAR,
              request_dataset_id VARCHAR, confidence FLOAT
            );
            CREATE TABLE ds_variable_alignments (
              dataset_id VARCHAR, raw_variable VARCHAR, canonical_var VARCHAR,
              method VARCHAR, confidence FLOAT, is_proxy BOOLEAN,
              proxy_penalty FLOAT
            );
            CREATE TABLE ds_observations (
              observation_id VARCHAR PRIMARY KEY, dataset_id VARCHAR,
              raw_variable VARCHAR, canonical_var VARCHAR, country_code VARCHAR,
              year INTEGER, value DOUBLE, acquisition_method VARCHAR,
              source_watermark VARCHAR, dataset_version VARCHAR
            );
            """
        )
        datasets = (
            (
                "amount-ds",
                "owner-a",
                "A",
                "Gross savings (current US$)",
                "Owner current monetary flow.",
                "CC-BY-4.0",
                "CC-BY-4.0",
                "SAVINGS.CD",
                "savings",
                ("100", "120", "150"),
            ),
            (
                "index-ds",
                "owner-b",
                "B",
                "Consumer price index (2010 = 100)",
                "Owner price index level.",
                "CC-BY-4.0",
                "CC-BY-4.0",
                "INDEX.LEVEL",
                "price_level",
                ("80", "100", "125"),
            ),
            (
                "aaa-tempting-index-ds",
                "owner-wrong",
                "WRONG",
                "Consumer price index level index (2010 = 100)",
                "Exact level index index evidence with tempting semantic text.",
                "CC-BY-4.0",
                "CC-BY-4.0",
                "TEMPTING.INDEX",
                "wrong_price_owner",
                ("81", "101", "126"),
            ),
            (
                "share-ds",
                "owner-c",
                "C",
                "Current account balance (% of GDP)",
                "Owner-declared share of GDP.",
                "CC-BY-4.0",
                "CC-BY-4.0",
                "BALANCE.SHARE",
                "balance_share",
                ("-2", "3", "5"),
            ),
            (
                "total-ds",
                "owner-d",
                "D",
                "GDP (current US$)",
                "Owner aggregate in current United States dollars.",
                "CC-BY-4.0",
                "CC-BY-4.0",
                "GDP.CD",
                "gdp",
                ("1000", "1200", "1400"),
            ),
            (
                "closed-ds",
                "owner-e",
                "E",
                "Restricted index (2010 = 100)",
                "Non-admissible control row.",
                "proprietary",
                "proprietary",
                "CLOSED.INDEX",
                "closed_index",
                ("1", "2", "3"),
            ),
        )
        for (
            dataset_id,
            source,
            agency,
            title,
            description,
            license_id,
            access_license,
            raw_variable,
            canonical_variable,
            values,
        ) in datasets:
            distribution_id = f"{dataset_id}-distribution"
            connection.execute(
                "INSERT INTO ds_datasets VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    dataset_id,
                    source,
                    agency,
                    title,
                    description,
                    license_id,
                    access_license,
                ],
            )
            connection.execute(
                "INSERT INTO ds_distributions VALUES (?, ?, 0.91)",
                [distribution_id, dataset_id],
            )
            connection.execute(
                "INSERT INTO ds_metric_bindings VALUES (?, ?, ?, ?, 0.89)",
                [canonical_variable, dataset_id, distribution_id, raw_variable],
            )
            connection.execute(
                "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, 'exact', 0.93, false, 0.0)",
                [dataset_id, raw_variable, canonical_variable],
            )
            for year, value in zip((2019, 2020, 2021), values, strict=True):
                connection.execute(
                    "INSERT INTO ds_observations VALUES (?, ?, ?, ?, 'UA', ?, ?, ?, ?, ?)",
                    [
                        f"{dataset_id}-{year}",
                        dataset_id,
                        raw_variable,
                        canonical_variable,
                        year,
                        value,
                        "owner_import",
                        f"owner:{dataset_id}:{year}",
                        "v1",
                    ],
                )


def _write_registry(path: Path, *, include_price_family: bool) -> None:
    blocks = [_NOVEL_FAMILY]
    if include_price_family:
        blocks.append(_PRICE_FAMILY)
    path.write_text("\n".join(blocks), encoding="utf-8")


def test_owner_registry_keeps_instance_metadata_outside_runtime_payload() -> None:
    payload = DEFAULT_DERIVATION_FAMILY_REGISTRY.read_text(encoding="utf-8")
    assert "[[catalog_selection_policies]]" in payload
    assert "[[families]]" in payload
    assert 'family_id = "price_index_exact_year_rebase"' in payload
    assert "[acceptance_case]" not in payload


def test_receipt_repo_refs_ignore_canonical_vs_worktree_path_shape() -> None:
    relative = Path("architecture/production_quality/derivation_family_registry.toml")
    canonical = Path("/checkout/policy-engine") / relative
    worktree = Path("/checkout/.worktrees/feature/policy-engine") / relative

    assert universality._stable_repo_ref(canonical) == universality._stable_repo_ref(worktree)
    assert universality._stable_repo_ref(canonical) == f"repo://{relative.as_posix()}"


def test_novel_family_runs_without_python_branch_and_unregistered_pair_refuses(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.duckdb"
    registry_path = tmp_path / "families.toml"
    _create_catalog(catalog_path)
    _write_registry(registry_path, include_price_family=False)

    receipt = build_derivation_universality_receipt(
        catalog_path=catalog_path,
        registry_path=registry_path,
    )

    assert receipt.family_count == 1
    assert receipt.full_series_denominator_count == 6
    assert receipt.unregistered_basis_refusal_code == "basis_mismatch"
    assert receipt.unregistered_basis_refusal_reason == "no_certified_transform"
    proof = receipt.family_proofs[0]
    assert proof.family_id == "novel_share_scale_77"
    assert {item.denominator_count for item in proof.selections} == {6}
    selected = {item.role: item.selected for item in proof.selections}
    expected = tuple(
        share.value * total.value / 100
        for share, total in zip(
            selected["share"].points,
            selected["total"].points,
            strict=True,
        )
    )
    assert tuple(proof.consumers[0].series) == expected
    assert proof.first_materialization_cache_hit is False
    assert proof.second_materialization_cache_hit is True
    assert proof.fresh_cas_rebuild_equal is True


def test_universality_rejects_tempting_wrong_owner_edge_and_selects_exact_owner(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.duckdb"
    registry_path = tmp_path / "families.toml"
    _create_catalog(catalog_path)
    registry_path.write_text(_PRICE_FAMILY, encoding="utf-8")

    receipt = build_derivation_universality_receipt(
        catalog_path=catalog_path,
        registry_path=registry_path,
    )

    price = next(
        proof for proof in receipt.family_proofs if proof.family_id == "synthetic_index_rebase"
    )
    index = next(selection for selection in price.selections if selection.role == "index")
    assert index.selected.dataset_id == "index-ds"
    assert index.selected.canonical_variable == "price_level"
    counts = {item.code: item.count for item in index.rejection_counts}
    assert counts["owner_metric_mismatch"] >= 1
    assert counts["owner_canonical_variable_mismatch"] >= 1


def test_generic_invariants_are_parameterized_over_every_registered_family(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.duckdb"
    registry_path = tmp_path / "families.toml"
    output_path = tmp_path / "receipt.json"
    _create_catalog(catalog_path)
    _write_registry(registry_path, include_price_family=True)

    first = build_derivation_universality_receipt(
        catalog_path=catalog_path,
        registry_path=registry_path,
    )
    second = build_derivation_universality_receipt(
        catalog_path=catalog_path,
        registry_path=registry_path,
    )
    assert first == second
    assert {item.family_id for item in first.family_proofs} == {
        "novel_share_scale_77",
        "synthetic_index_rebase",
    }
    for proof in first.family_proofs:
        assert proof.monotone_authority_proven
        assert proof.derived_authority == proof.weakest_input_authority
        assert proof.certificate.observation_class == "derived"
        assert len({item.consumer_method_id for item in proof.consumers}) == 2

    write_derivation_universality_receipt(first, output_path=output_path)
    bytes_once = output_path.read_bytes()
    assert bytes_once.endswith(b"\n")
    assert not bytes_once.endswith(b"\n\n")
    write_derivation_universality_receipt(second, output_path=output_path)
    assert output_path.read_bytes() == bytes_once
    assert parse_derivation_universality_receipt(output_path) == first

    frozen = json.loads(bytes_once)
    for index, proof in enumerate(frozen["family_proofs"]):
        recipe_tamper = json.loads(bytes_once)
        recipe_tamper["family_proofs"][index]["recipe"]["method_version"] += ".tampered"
        with pytest.raises(ValidationError):
            DerivationUniversalityReceipt.model_validate(recipe_tamper)

        masquerading = json.loads(bytes_once)
        masquerading["family_proofs"][index]["certificate"]["observation_class"] = "observed"
        with pytest.raises(ValidationError):
            DerivationUniversalityReceipt.model_validate(masquerading)

        inflated = json.loads(bytes_once)
        inflated["family_proofs"][index]["derived_authority"] = "1"
        with pytest.raises(ValidationError):
            DerivationUniversalityReceipt.model_validate(inflated)

        if proof["recipe"]["parameters"]:
            parameter_tamper = json.loads(bytes_once)
            parameter_tamper["family_proofs"][index]["recipe"]["parameters"][0]["value"] = "2019"
            with pytest.raises(ValidationError):
                DerivationUniversalityReceipt.model_validate(parameter_tamper)


def test_same_family_versions_use_exact_policy_and_recipe_identity(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.duckdb"
    registry_path = tmp_path / "families.toml"
    _create_catalog(catalog_path)
    second_version = _PRICE_FAMILY.replace(
        'policy_id = "synthetic_index_rebase.proof"',
        'policy_id = "synthetic_index_rebase.proof.v8"',
    ).replace('method_version = "7.0.0"', 'method_version = "8.0.0"')
    registry_path.write_text(
        "\n".join((_PRICE_FAMILY, second_version)),
        encoding="utf-8",
    )

    receipt = build_derivation_universality_receipt(
        catalog_path=catalog_path,
        registry_path=registry_path,
    )

    identities = tuple((proof.family_id, proof.method_version) for proof in receipt.family_proofs)
    assert identities == (
        ("synthetic_index_rebase", "7.0.0"),
        ("synthetic_index_rebase", "8.0.0"),
    )
    assert len({proof.recipe.recipe_id for proof in receipt.family_proofs}) == 2

    from tools.quality.validation.layer3_gy_n13b_acquisition_contract import (
        derive_derivation_universality_projection,
    )

    projection = derive_derivation_universality_projection(receipt)
    assert (
        tuple((family.family_id, family.method_version) for family in projection.families)
        == identities
    )
