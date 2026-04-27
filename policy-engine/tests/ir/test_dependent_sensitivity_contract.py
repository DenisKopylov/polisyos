from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.dependent_sensitivity import (
    ConditionalSamplerSpec,
    CopulaSpec,
    DependentEstimatorSpec,
    DependentSensitivityAnalysisBundle,
    DependentSensitivityResult,
    IdentifiabilityAssumptionSpec,
    InputMarginalSpec,
    InputVariableSpec,
    JointInputDistributionSpec,
    OutputSpec,
    ReferenceCopulaSpec,
    load_dependent_sensitivity_bundle,
    load_dependent_sensitivity_result,
    persist_dependent_sensitivity_bundle,
    persist_dependent_sensitivity_result,
)


def _bundle(reference_copula_id: str = "product_ref") -> DependentSensitivityAnalysisBundle:
    inputs = [
        InputVariableSpec(
            name="income",
            dtype="continuous",
            role="economic",
            marginal=InputMarginalSpec(family="normal", support=(-5.0, 5.0)),
        ),
        InputVariableSpec(
            name="education",
            dtype="continuous",
            role="demographic",
            marginal=InputMarginalSpec(family="normal", support=(-5.0, 5.0)),
        ),
    ]
    joint = JointInputDistributionSpec(
        observed_copula=CopulaSpec(
            id="observed",
            family="gaussian",
            parameters={"correlation_matrix": [[1.0, 0.4], [0.4, 1.0]]},
        ),
        reference_copulas=[
            ReferenceCopulaSpec(id="product_ref", family="product"),
        ],
        conditional_sampler=ConditionalSamplerSpec(
            type="analytic_gaussian",
            exact=True,
            supports_coalitions=True,
            supports_groups=False,
        ),
    )
    return DependentSensitivityAnalysisBundle(
        model={"model_id": "demo"},
        inputs=inputs,
        joint_distribution=joint,
        estimators=[
            DependentEstimatorSpec(
                id="dc_safe",
                family="dependent_shapley_copula",
                contribution_modes=["full", "marginal_reference", "structural_delta"],
                reference_copula_id=reference_copula_id,
            )
        ],
        outputs=[OutputSpec(name="welfare_loss")],
        assumptions=IdentifiabilityAssumptionSpec(structural_claim_level="distributional"),
    )


def test_dependent_sensitivity_bundle_declares_required_joint_distribution() -> None:
    bundle = _bundle()

    assert bundle.contract_version == "2.0"
    assert bundle.kind == "dependent_copula_sensitivity"
    assert bundle.joint_distribution.observed_copula.family == "gaussian"
    assert bundle.joint_distribution.reference_copulas[0].family == "product"
    assert bundle.joint_distribution.conditional_sampler.supports_coalitions is True
    assert bundle.estimators[0].contribution_modes == [
        "full",
        "marginal_reference",
        "structural_delta",
    ]


def test_dependent_sensitivity_bundle_rejects_unknown_reference_copula() -> None:
    with pytest.raises(ValueError, match="unknown reference_copula_id"):
        _bundle(reference_copula_id="missing_ref")


def test_dependent_sensitivity_bundle_accepts_camel_case_contract_payload() -> None:
    bundle = DependentSensitivityAnalysisBundle.model_validate(
        {
            "contractVersion": "2.0",
            "kind": "dependent_copula_sensitivity",
            "model": {"modelId": "demo"},
            "inputs": [
                {
                    "name": "income",
                    "dtype": "continuous",
                    "marginal": {"family": "normal", "support": [-5.0, 5.0]},
                }
            ],
            "jointDistribution": {
                "observedCopula": {"id": "observed", "family": "gaussian"},
                "referenceCopulas": [{"id": "product_ref", "family": "product"}],
                "conditionalSampler": {
                    "type": "analytic_gaussian",
                    "exact": True,
                    "supportsCoalitions": True,
                },
            },
            "estimators": [
                {
                    "id": "dc_safe",
                    "family": "dependent_shapley_copula",
                    "contributionModes": ["full", "marginal_reference", "structural_delta"],
                    "referenceCopulaId": "product_ref",
                }
            ],
            "outputs": [{"name": "welfare_loss"}],
        }
    )

    assert bundle.joint_distribution.conditional_sampler.supports_coalitions is True
    dumped = bundle.model_dump(mode="json", by_alias=True)
    assert "contractVersion" in dumped
    assert "jointDistribution" in dumped


def test_dependent_sensitivity_bundle_and_result_persist_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = _bundle()
    bundle_ref = persist_dependent_sensitivity_bundle(store, bundle)
    loaded_bundle = load_dependent_sensitivity_bundle(store, bundle_ref)

    result = DependentSensitivityResult.model_validate(
        {
            "bundleId": "bundle.demo",
            "outputName": "welfare_loss",
            "variance": {
                "full": 2.8,
                "reference": {"product_ref": 2.0},
                "structuralDelta": {"product_ref": 0.8},
            },
            "indices": [
                {
                    "input": "income",
                    "full": {"shapley": {"value": 1.4, "normalized": 0.5}},
                    "marginalReference": {
                        "referenceCopulaId": "product_ref",
                        "shapley": {"value": 1.0, "normalized": 0.357142857},
                    },
                    "structuralDelta": {
                        "referenceCopulaId": "product_ref",
                        "shapley": {"value": 0.4, "normalized": 0.142857143},
                        "sign": "amplifying",
                    },
                }
            ],
            "diagnostics": {"conditionalSamplerChecks": []},
            "identifiability": {"structuralClaimLevel": "distributional"},
            "reproducibility": {"seed": 42, "estimatorVersion": "dc-safe-test"},
        }
    )
    result_ref = persist_dependent_sensitivity_result(store, result)
    loaded_result = load_dependent_sensitivity_result(store, result_ref)

    assert bundle_ref.kind == "ir.dependent_sensitivity_bundle"
    assert result_ref.kind == "ir.dependent_sensitivity_result"
    assert loaded_bundle == bundle
    assert loaded_result == result
