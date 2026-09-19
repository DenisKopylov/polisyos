from __future__ import annotations

import importlib

import pytest

from polisyos.ir.analytics.mechanism_design import MechanismFamily


def _canonical_families_module():
    try:
        return importlib.import_module("polisyos.foundry.methods.catalog.mechanism.families")
    except ModuleNotFoundError as exc:
        pytest.fail("canonical mechanism-family owner is missing: " + str(exc), pytrace=False)


def test_catalog_family_owner_preserves_ids_assumptions_and_unknown_id_behavior() -> None:
    """The catalog owner must expose the four existing family declarations unchanged."""
    families = _canonical_families_module()
    expected_ids = {
        "bayes_tax_affine_v1",
        "bayes_tax_pl_v1",
        "license_myerson_score_v1",
        "license_scoring_reserve_v1",
    }

    catalog = families.mechanism_family_catalog()
    assert {entry["mechanism_id"] for entry in catalog} == expected_ids

    tax_spec = families.get_mechanism_family_spec("bayes_tax_pl_v1")
    assert tax_spec.family is MechanismFamily.TAX_PIECEWISE_LINEAR
    assert tax_spec.assumptions == (
        "single_dimensional_private_type",
        "quasi_linear_utility",
        "mirrlees_quadratic_effort",
    )

    license_spec = families.get_mechanism_family_spec("license_myerson_score_v1")
    assert license_spec.family is MechanismFamily.LICENSE_MYERSON_SCORE
    assert license_spec.assumptions == (
        "single_parameter_environment",
        "independent_private_values",
        "regular_virtual_values",
    )

    with pytest.raises(ValueError, match="Unknown mechanism family"):
        families.get_mechanism_family_spec("missing_family")


def test_ic_service_binds_family_lookup_to_catalog_owner() -> None:
    """IC verification must consume the canonical catalog binding directly."""
    service = importlib.import_module("polisyos.scientist.validation.verification.ic.service")
    families = _canonical_families_module()
    design_facade = importlib.import_module("polisyos.foundry.mechanisms.design")
    original = design_facade.get_mechanism_family_spec
    sentinel = object()

    try:
        design_facade.get_mechanism_family_spec = sentinel
        reloaded = importlib.reload(service)
        assert reloaded.get_mechanism_family_spec is families.get_mechanism_family_spec
    finally:
        design_facade.get_mechanism_family_spec = original
        importlib.reload(service)
