from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.ic_verification import ICVerificationRequest
from polisyos.ir.analytics.mechanism_design import MechanismFamily
from polisyos.ir.governance.game_design import (
    BayesianTypeSpec,
    MechanismConstraintType,
    MechanismDesignConstraint,
    MechanismDesignSpec,
    MechanismGameRepresentation,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
from polisyos.scientist.validation.verification.ic import (
    load_ic_certificate,
    load_ic_negative_certificate,
    load_ic_report,
    verify_incentive_compatibility,
)


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

    expected = {
        "bayes_tax_pl_v1": (
            "monotone_piecewise_linear_earnings",
            ("type_grid", "earnings_schedule", "u0", "revenue_floor"),
            (
                "single_dimensional_private_type",
                "quasi_linear_utility",
                "mirrlees_quadratic_effort",
            ),
        ),
        "bayes_tax_affine_v1": (
            "affine_earnings_schedule",
            ("type_grid", "gamma", "u0", "revenue_floor"),
            (
                "single_dimensional_private_type",
                "quasi_linear_utility",
                "mirrlees_quadratic_effort",
            ),
        ),
        "license_scoring_reserve_v1": (
            "single_parameter_scoring_with_reserve",
            ("bid_grid", "allocation_rule", "payments", "reserve_price"),
            (
                "single_parameter_environment",
                "independent_private_values",
                "regular_priors_or_grid_audit",
            ),
        ),
        "license_myerson_score_v1": (
            "virtual_value_plus_public_score",
            ("bid_grid", "allocation_rule", "payments", "reserve_price"),
            (
                "single_parameter_environment",
                "independent_private_values",
                "regular_virtual_values",
            ),
        ),
    }
    for mechanism_id, (parameterization, parameters, assumptions) in expected.items():
        spec = families.get_mechanism_family_spec(mechanism_id)
        assert spec.parameterization == parameterization
        assert spec.tunable_parameters == parameters
        assert spec.assumptions == assumptions

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


@pytest.mark.parametrize(
    ("schedule", "verdict"),
    [(["0.85", "1.20", "1.55"], "positive"), (["1.0", "0.8", "1.4"], "negative")],
)
def test_registered_family_requires_native_certificate_for_actual_policy(
    tmp_path, schedule: list[str], verdict: str
) -> None:
    """Identical catalog membership admits one schedule and rejects its adversarial variant."""
    families = _canonical_families_module()
    family_spec = families.get_mechanism_family_spec("bayes_tax_pl_v1")
    assert family_spec.mechanism_id in {
        item["mechanism_id"] for item in families.mechanism_family_catalog()
    }
    policy = PolicySpec(
        policy_id="family_contract",
        interventions=[
            InterventionSpec(
                intervention_id="income_tax",
                kind="income_tax_piecewise_linear",
                target={"kind": "predicate", "field": "income", "operator": ">=", "value": 0},
                schedule={"start_step": 0, "duration_steps": 1},
                params={
                    "type_grid": [Decimal("1.0"), Decimal("1.5"), Decimal("2.0")],
                    "earnings_schedule": [Decimal(value) for value in schedule],
                    "prior_weights": [Decimal("0.25"), Decimal("0.50"), Decimal("0.25")],
                    "u0": Decimal("0"),
                    "revenue_floor": Decimal("-1"),
                },
            )
        ],
        mechanism_bindings=[
            MechanismBinding(
                binding_id="tax_binding",
                mechanism_id=family_spec.mechanism_id,
                intervention_ids=["income_tax"],
            )
        ],
        mechanism_design=MechanismDesignSpec(
            design_id="tax_design",
            representation=MechanismGameRepresentation.BAYESIAN,
            players=("taxpayer",),
            mechanism_ids=(family_spec.mechanism_id,),
            action_spaces={"taxpayer": ("low", "middle", "high")},
            bayesian_types=[
                BayesianTypeSpec(
                    player_id="taxpayer",
                    type_space=("low", "middle", "high"),
                    prior_probabilities={"low": 0.25, "middle": 0.50, "high": 0.25},
                )
            ],
            constraints=[
                MechanismDesignConstraint(
                    constraint_id="taxpayer_bic",
                    constraint_type=MechanismConstraintType.BAYESIAN_IC,
                    applies_to_players=("taxpayer",),
                )
            ],
        ),
    )
    store = FileSystemCAS(tmp_path / "cas")
    policy_ref = store.put_json(
        policy,
        PutOptions(kind="ir.policy_spec", media_type="application/json"),
        # BayesianTypeSpec carries float priors; use the native IC fixture's declared canon profile.
        canon_spec=CanonSpec(forbid_floats=False),
    )
    result = verify_incentive_compatibility(
        store, ICVerificationRequest(property="bayesian_ic", input_ref=policy_ref)
    )
    reopened = FileSystemCAS(tmp_path / "cas")
    report = load_ic_report(reopened, result.report_ref)
    assert result.verdict == report.verdict == verdict, result.notes
    assert report.backend == "mechanism_family"
    assert report.input_digest == str(policy_ref.artifact_id)
    assert result.certificate_ref is not None
    if verdict == "positive":
        certificate = load_ic_certificate(reopened, result.certificate_ref)
        assert result.ok
        assert certificate.witness["family_assumptions"] == list(family_spec.assumptions)
        assert certificate.witness["mechanism_id"] == family_spec.mechanism_id
    else:
        certificate = load_ic_negative_certificate(reopened, result.certificate_ref)
        assert not result.ok
        assert certificate.witness["reason"] == "non_monotone_earnings_schedule"
    assert certificate.input_digest == str(policy_ref.artifact_id)
    assert certificate.proof_artifacts
