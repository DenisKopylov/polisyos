from __future__ import annotations

import pytest
from polisyos.ir.analytics.dependent_sensitivity import DependentSensitivityResult


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _indexed(result):
    return {row["input"]: row for row in result["result"]["indices"]}


def _base_params(rho: float = 0.0) -> dict:
    return {
        "input_names": ["x1", "x2"],
        "observed_copula": {
            "id": "observed",
            "family": "gaussian",
            "parameters": {"correlationMatrix": [[1.0, rho], [rho, 1.0]]},
        },
        "reference_copula": {
            "id": "product_ref",
            "family": "product",
            "supportPolicy": {
                "allowProductReferenceOutsideObservedSupport": False,
                "invalidPointPolicy": "error",
            },
        },
        "conditional_sampler": {
            "type": "analytic_gaussian",
            "exact": True,
            "supportsCoalitions": True,
        },
    }


class TestDependentCopulaSensitivity:
    def test_correlation_amplification_matches_linear_gaussian_closed_form(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        rho = 0.35
        result = method.pure_step(
            {
                "covariance_matrix": [[1.0, rho], [rho, 1.0]],
                "linear_coefficients": [1.0, 1.0],
            },
            {
                **_base_params(rho),
            },
        )

        payload = result["result"]
        rows = _indexed(result)

        assert payload["kind"] == "dependent_copula_sensitivity"
        assert payload["variance"]["full"] == pytest.approx(2.0 + 2.0 * rho)
        assert payload["variance"]["reference"]["product_ref"] == pytest.approx(2.0)
        assert rows["x1"]["full"]["shapley"]["value"] == pytest.approx(1.0 + rho)
        assert rows["x2"]["full"]["shapley"]["value"] == pytest.approx(1.0 + rho)
        assert rows["x1"]["marginalReference"]["shapley"]["value"] == pytest.approx(1.0)
        assert rows["x2"]["marginalReference"]["shapley"]["value"] == pytest.approx(1.0)
        assert rows["x1"]["structuralDelta"]["shapley"]["value"] == pytest.approx(rho)
        assert rows["x2"]["structuralDelta"]["shapley"]["value"] == pytest.approx(rho)
        DependentSensitivityResult.model_validate(payload)

    def test_proxy_variable_splits_predictive_from_marginal_reference(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        rho = 0.6
        result = method.pure_step(
            {
                "covariance_matrix": [[1.0, rho], [rho, 1.0]],
                "linear_coefficients": [1.0, 0.0],
            },
            {
                **_base_params(rho),
                "input_names": ["direct_driver", "proxy"],
                "observed_copula": {
                    "id": "observed",
                    "family": "gaussian",
                    "parameters": {"correlationMatrix": [[1.0, rho], [rho, 1.0]]},
                },
            },
        )

        proxy = _indexed(result)["proxy"]

        assert proxy["full"]["shapley"]["value"] > 0.0
        assert proxy["marginalReference"]["shapley"]["value"] == pytest.approx(0.0)
        assert proxy["structuralDelta"]["shapley"]["value"] == pytest.approx(
            proxy["full"]["shapley"]["value"]
        )
        assert proxy["structuralDelta"]["sign"] == "amplifying"

    def test_product_observed_and_product_reference_have_zero_structural_delta(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        result = method.pure_step(
            {
                "covariance_matrix": [[4.0, 0.0], [0.0, 9.0]],
                "linear_coefficients": [2.0, 3.0],
            },
            {
                **_base_params(0.0),
                "input_names": ["a", "b"],
                "observed_copula": {"id": "observed", "family": "product"},
            },
        )

        for row in result["result"]["indices"]:
            assert row["full"]["shapley"]["value"] == pytest.approx(
                row["marginalReference"]["shapley"]["value"]
            )
            assert row["structuralDelta"]["shapley"]["value"] == pytest.approx(0.0)
            assert row["structuralDelta"]["sign"] == "near_zero"

    def test_reference_copula_id_selects_declared_reference(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        rho = 0.4
        result = method.pure_step(
            {
                "covariance_matrix": [[1.0, rho], [rho, 1.0]],
                "linear_coefficients": [1.0, 1.0],
            },
            {
                **_base_params(rho),
                "reference_copulas": [
                    {
                        "id": "observed_like",
                        "family": "gaussian",
                        "parameters": {"correlationMatrix": [[1.0, rho], [rho, 1.0]]},
                    },
                    {"id": "product_ref", "family": "product"},
                ],
                "reference_copula_id": "product_ref",
            },
        )

        payload = result["result"]

        assert set(payload["variance"]["reference"]) == {"product_ref"}
        assert _indexed(result)["x1"]["structuralDelta"]["shapley"]["value"] == pytest.approx(rho)

    def test_registered_in_sensitivity_namespace(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        assert method.signature.name == "dependent_copula_sensitivity"

    def test_conditional_pair_payload_is_used_for_coalition_values(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        result = method.pure_step(
            {
                "covariance_matrix": [[1.0, 0.0], [0.0, 1.0]],
                "linear_coefficients": [1.0, 1.0],
                "conditional_pairs_full": {
                    "empty": {"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]},
                    "x1": {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0]},
                    "x2": {"a": [1.0, 3.0, 5.0], "b": [1.0, 3.0, 5.0]},
                    "all": {"a": [1.0, 4.0, 7.0], "b": [1.0, 4.0, 7.0]},
                },
                "conditional_pairs_reference": {
                    "empty": {"a": [1.0, 2.0, 3.0], "b": [3.0, 2.0, 1.0]},
                    "x1": {"a": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0]},
                    "x2": {"a": [1.0, 3.0, 5.0], "b": [1.0, 3.0, 5.0]},
                    "all": {"a": [1.0, 4.0, 7.0], "b": [1.0, 4.0, 7.0]},
                },
                "full_variance": 9.0,
                "reference_variance": 9.0,
            },
            _base_params(0.0),
        )

        payload = result["result"]
        rows = _indexed(result)

        assert payload["diagnostics"]["estimatorSemantics"] == "conditional_paired_sampling"
        assert rows["x1"]["full"]["shapley"]["value"] == pytest.approx(3.0)
        assert rows["x2"]["full"]["shapley"]["value"] == pytest.approx(6.0)

    def test_latent_screening_and_edge_shapley_are_reported(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )
        result = method.pure_step(
            {
                "covariance_matrix": [[1.0, 0.0], [0.0, 1.0]],
                "linear_coefficients": [1.0, 1.0],
                "latent_gradients": [[1.0, 2.0], [3.0, 4.0]],
                "latent_elementary_effects": [[1.0, -2.0], [3.0, -4.0]],
                "edge_names": ["x1--x2"],
                "edge_variance_values": {"empty": 2.0, "all": 3.0},
            },
            _base_params(0.0),
        )

        rows = _indexed(result)
        edge = result["result"]["edgeContributions"][0]

        assert rows["x1"]["latentInnovation"]["dgsm"]["value"] == pytest.approx(5.0)
        assert rows["x2"]["latentInnovation"]["morrisMuStar"]["value"] == pytest.approx(3.0)
        assert edge["edge"] == "x1--x2"
        assert edge["contribution"]["value"] == pytest.approx(1.0)
        assert result["result"]["identifiability"]["edgeStructuralIdentified"] is True

    def test_support_policy_blocks_product_reference_outside_support(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )

        with pytest.raises(ValueError, match="support violations"):
            method.pure_step(
                {
                    "covariance_matrix": [[1.0, 0.0], [0.0, 1.0]],
                    "linear_coefficients": [1.0, 1.0],
                    "support_violations": 1,
                },
                _base_params(0.0),
            )

    def test_declared_joint_distribution_is_required(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry,
            "sensitivity.global.dependent_copula_sensitivity@1.0.0",
        )

        with pytest.raises(ValueError, match="requires declared"):
            method.pure_step(
                {
                    "covariance_matrix": [[1.0, 0.0], [0.0, 1.0]],
                    "linear_coefficients": [1.0, 1.0],
                },
                {"input_names": ["x1", "x2"]},
            )
