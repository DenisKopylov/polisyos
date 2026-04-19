"""Tests for the new EstimandAST node types: NuisanceNode, ExpectationNode, IntegralNode."""
import pytest
from pydantic import ValidationError

from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionLawNode,
    DistributionLawQuery,
    DistributionRef,
    EstimandAST,
    ExpectationNode,
    IntegralNode,
    make_distribution_law_estimand,
    NuisanceNode,
    ProductNode,
    SumNode,
)


# ---------------------------------------------------------------------------
# NuisanceNode
# ---------------------------------------------------------------------------


class TestNuisanceNode:
    def test_propensity_creation(self):
        node = NuisanceNode(nuisance_type="propensity", target_variable="T")
        assert node.node_type == "nuisance"
        assert node.nuisance_type == "propensity"
        assert node.target_variable == "T"
        assert node.conditioning == ()
        assert node.domain == DistributionDomain.SOURCE
        assert node.dataset_ref is None

    def test_outcome_creation(self):
        node = NuisanceNode(
            nuisance_type="outcome",
            target_variable="Y",
            conditioning=("T", "X"),
            domain=DistributionDomain.TARGET,
            dataset_ref="target_ds",
        )
        assert node.nuisance_type == "outcome"
        assert node.conditioning == ("T", "X")
        assert node.dataset_ref == "target_ds"

    def test_density_ratio_creation(self):
        node = NuisanceNode(nuisance_type="density_ratio", target_variable="X")
        assert node.nuisance_type == "density_ratio"

    def test_mediator_density_creation(self):
        node = NuisanceNode(nuisance_type="mediator_density", target_variable="M", conditioning=("T",))
        assert node.nuisance_type == "mediator_density"

    def test_invalid_nuisance_type_raises(self):
        with pytest.raises((ValidationError, Exception)):
            NuisanceNode(nuisance_type="unknown_type", target_variable="X")

    def test_frozen_rejects_mutation(self):
        node = NuisanceNode(nuisance_type="propensity", target_variable="T")
        with pytest.raises((TypeError, Exception)):
            node.target_variable = "changed"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            NuisanceNode(nuisance_type="propensity", target_variable="T", surprise_field="oops")

    def test_round_trip_json(self):
        node = NuisanceNode(
            nuisance_type="outcome",
            target_variable="Y",
            conditioning=("T", "X"),
            domain=DistributionDomain.SOURCE,
            dataset_ref="ds1",
        )
        data = node.model_dump(mode="json")
        restored = NuisanceNode.model_validate(data)
        assert restored.nuisance_type == "outcome"
        assert restored.conditioning == ("T", "X")
        assert restored.dataset_ref == "ds1"

    def test_as_estimand_ast_root(self):
        node = NuisanceNode(nuisance_type="propensity", target_variable="T", conditioning=("X",))
        ast = EstimandAST(
            query_str="propensity(T|X)",
            root=node,
            treatment="T",
            outcome="T",
            all_variables=("T", "X"),
        )
        assert ast.root.node_type == "nuisance"  # type: ignore[union-attr]

    def test_collect_domains_from_nuisance_node(self):
        node = NuisanceNode(
            nuisance_type="density_ratio",
            target_variable="X",
            domain=DistributionDomain.TARGET,
        )
        ast = EstimandAST(
            query_str="density_ratio(X)",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("X",),
        )
        assert DistributionDomain.TARGET in ast.required_domains()

    def test_collect_dataset_refs_from_nuisance_node(self):
        node = NuisanceNode(
            nuisance_type="outcome",
            target_variable="Y",
            dataset_ref="my_ds",
        )
        ast = EstimandAST(
            query_str="E[Y|T,X]",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "T"),
        )
        assert "my_ds" in ast.required_datasets()

    def test_collect_dist_refs_from_nuisance_node_returns_empty(self):
        node = NuisanceNode(nuisance_type="propensity", target_variable="T")
        ast = EstimandAST(
            query_str="propensity(T)",
            root=node,
            treatment="T",
            outcome="T",
            all_variables=("T",),
        )
        assert ast.collect_distribution_refs() == []


# ---------------------------------------------------------------------------
# ExpectationNode
# ---------------------------------------------------------------------------


class TestExpectationNode:
    def test_observational_expectation(self):
        node = ExpectationNode(outcome="Y", conditioning=("X",))
        assert node.node_type == "expectation"
        assert node.outcome == "Y"
        assert node.conditioning == ("X",)
        assert node.intervention_set == ()
        assert node.counterfactual is False
        assert node.domain == DistributionDomain.SOURCE
        assert node.dataset_ref is None

    def test_counterfactual_expectation(self):
        node = ExpectationNode(
            outcome="Y",
            intervention_set=("T",),
            counterfactual=True,
            domain=DistributionDomain.TARGET,
        )
        assert node.counterfactual is True
        assert node.intervention_set == ("T",)

    def test_to_latex_with_conditioning(self):
        node = ExpectationNode(outcome="Y", conditioning=("X", "Z"))
        latex = node.to_latex()
        assert "\\mathbb{E}" in latex
        assert "Y" in latex
        assert "X" in latex

    def test_to_latex_counterfactual(self):
        node = ExpectationNode(outcome="Y", intervention_set=("T",), counterfactual=True)
        latex = node.to_latex()
        assert "do(" in latex
        assert "T" in latex

    def test_to_latex_unconditional(self):
        node = ExpectationNode(outcome="Y")
        latex = node.to_latex()
        assert "\\mathbb{E}[Y]" == latex

    def test_frozen_rejects_mutation(self):
        node = ExpectationNode(outcome="Y")
        with pytest.raises((TypeError, Exception)):
            node.outcome = "Z"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            ExpectationNode(outcome="Y", not_a_field="x")

    def test_round_trip_json(self):
        node = ExpectationNode(
            outcome="Y",
            conditioning=("T", "X"),
            intervention_set=("T",),
            counterfactual=True,
            domain=DistributionDomain.TARGET,
            dataset_ref="target_ds",
        )
        data = node.model_dump(mode="json")
        restored = ExpectationNode.model_validate(data)
        assert restored.outcome == "Y"
        assert restored.counterfactual is True
        assert restored.dataset_ref == "target_ds"

    def test_as_estimand_ast_root(self):
        node = ExpectationNode(outcome="Y", conditioning=("T",))
        ast = EstimandAST(
            query_str="E[Y|T]",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "T"),
        )
        assert ast.root.node_type == "expectation"  # type: ignore[union-attr]

    def test_collect_domains(self):
        node = ExpectationNode(outcome="Y", domain=DistributionDomain.EXPERIMENTAL)
        ast = EstimandAST(
            query_str="E[Y]",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y",),
        )
        assert DistributionDomain.EXPERIMENTAL in ast.required_domains()


class TestDistributionLawNode:
    def test_distribution_query_defaults_to_halfline_cdf(self):
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
        )
        assert query.generator_type == "halfline_cdf"
        assert query.resolved_parameter_domain == "Q"

    def test_distribution_query_rejects_invalid_representation(self):
        with pytest.raises(ValidationError):
            DistributionLawQuery(
                outcome_variables=("income",),
                intervention_set=("tax_policy",),
                support_space="real",
                representation="pmf",
            )

    def test_distribution_law_node_latex_mentions_do(self):
        node = DistributionLawNode(
            outcome=("income",),
            intervention_set=("tax_policy",),
            conditioning=("region",),
        )
        latex = node.to_latex()
        assert "\\in \\cdot" in latex
        assert "do(tax_policy)" in latex
        assert "region" in latex

    def test_make_distribution_law_estimand_wraps_query(self):
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
            conditioning=("region",),
        )
        ast = make_distribution_law_estimand(query=query, identification_method="dist_id_v1")
        assert ast.root.node_type == "distribution_law"  # type: ignore[union-attr]
        assert ast.identification_method == "dist_id_v1"
        assert ast.required_datasets() == []
        assert DistributionDomain.SOURCE in ast.required_domains()

    def test_collect_dataset_refs(self):
        node = ExpectationNode(outcome="Y", dataset_ref="exp_ds")
        ast = EstimandAST(
            query_str="E[Y]",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y",),
        )
        assert "exp_ds" in ast.required_datasets()

    def test_collect_dist_refs_returns_empty(self):
        node = ExpectationNode(outcome="Y")
        ast = EstimandAST(
            query_str="E[Y]",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y",),
        )
        assert ast.collect_distribution_refs() == []


# ---------------------------------------------------------------------------
# IntegralNode
# ---------------------------------------------------------------------------


class TestIntegralNode:
    def _leaf(self) -> DistributionRef:
        return DistributionRef(domain=DistributionDomain.SOURCE, variables=("Y",))

    def test_basic_creation(self):
        node = IntegralNode(integration_vars=("Z",), operand=self._leaf())
        assert node.node_type == "integral"
        assert node.integration_vars == ("Z",)
        assert node.measure == "lebesgue"

    def test_custom_measure(self):
        node = IntegralNode(integration_vars=("Z",), operand=self._leaf(), measure="gaussian")
        assert node.measure == "gaussian"

    def test_to_latex(self):
        operand = DistributionRef(domain=DistributionDomain.SOURCE, variables=("Y",), conditioning=("Z",))
        node = IntegralNode(integration_vars=("Z",), operand=operand)
        latex = node.to_latex()
        assert "\\int" in latex
        assert "dZ" in latex

    def test_nested_in_product(self):
        leaf1 = DistributionRef(domain=DistributionDomain.SOURCE, variables=("M",), conditioning=("T",))
        leaf2 = DistributionRef(domain=DistributionDomain.SOURCE, variables=("Y",), conditioning=("M",))
        product = ProductNode(factors=(leaf1, leaf2))
        integral = IntegralNode(integration_vars=("M",), operand=product)
        assert integral.integration_vars == ("M",)

    def test_frozen_rejects_mutation(self):
        node = IntegralNode(integration_vars=("Z",), operand=self._leaf())
        with pytest.raises((TypeError, Exception)):
            node.measure = "uniform"

    def test_extra_fields_forbidden(self):
        with pytest.raises((ValidationError, Exception)):
            IntegralNode(integration_vars=("Z",), operand=self._leaf(), bad_field=True)

    def test_round_trip_json(self):
        leaf = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
            conditioning=("Z",),
            dataset_ref="ds1",
        )
        node = IntegralNode(integration_vars=("Z",), operand=leaf, measure="lebesgue")
        data = node.model_dump(mode="json")
        restored = IntegralNode.model_validate(data)
        assert restored.integration_vars == ("Z",)
        assert restored.measure == "lebesgue"

    def test_as_estimand_ast_root(self):
        leaf = DistributionRef(domain=DistributionDomain.SOURCE, variables=("Y",), conditioning=("Z",))
        node = IntegralNode(integration_vars=("Z",), operand=leaf)
        ast = EstimandAST(
            query_str="int P(Y|Z) dZ",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "Z"),
        )
        assert ast.root.node_type == "integral"  # type: ignore[union-attr]

    def test_collect_domains_recurses_into_operand(self):
        leaf = DistributionRef(domain=DistributionDomain.TARGET, variables=("Y",))
        node = IntegralNode(integration_vars=("Z",), operand=leaf)
        ast = EstimandAST(
            query_str="int P*(Y) dZ",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "Z"),
        )
        assert DistributionDomain.TARGET in ast.required_domains()

    def test_collect_dataset_refs_recurses_into_operand(self):
        leaf = DistributionRef(
            domain=DistributionDomain.SOURCE,
            variables=("Y",),
            dataset_ref="source_ds",
        )
        node = IntegralNode(integration_vars=("Z",), operand=leaf)
        ast = EstimandAST(
            query_str="int P(Y) dZ",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "Z"),
        )
        assert "source_ds" in ast.required_datasets()

    def test_collect_dist_refs_recurses_into_operand(self):
        leaf = DistributionRef(domain=DistributionDomain.SOURCE, variables=("Y",))
        node = IntegralNode(integration_vars=("Z",), operand=leaf)
        ast = EstimandAST(
            query_str="int P(Y) dZ",
            root=node,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "Z"),
        )
        refs = ast.collect_distribution_refs()
        assert len(refs) == 1
        assert refs[0].variables == ("Y",)


# ---------------------------------------------------------------------------
# Mixed: new nodes inside composite trees
# ---------------------------------------------------------------------------


class TestMixedTrees:
    def test_sum_over_nuisance_node(self):
        nuisance = NuisanceNode(nuisance_type="outcome", target_variable="Y", conditioning=("T", "Z"))
        marginal = DistributionRef(domain=DistributionDomain.SOURCE, variables=("Z",))
        product = ProductNode(factors=(nuisance, marginal))
        root = SumNode(summation_vars=("Z",), operand=product)
        ast = EstimandAST(
            query_str="Σ_Z hat_f(Y|T,Z)·P(Z)",
            root=root,
            treatment="T",
            outcome="Y",
            all_variables=("T", "Y", "Z"),
        )
        domains = ast.required_domains()
        assert DistributionDomain.SOURCE in domains
        # NuisanceNode domain also SOURCE by default
        dist_refs = ast.collect_distribution_refs()
        # Only the DistributionRef leaf should appear
        assert len(dist_refs) == 1

    def test_integral_wrapping_expectation(self):
        exp = ExpectationNode(
            outcome="Y",
            conditioning=("T",),
            domain=DistributionDomain.SOURCE,
            dataset_ref="obs_ds",
        )
        integral = IntegralNode(integration_vars=("T",), operand=exp)
        ast = EstimandAST(
            query_str="∫ E[Y|T] dT",
            root=integral,
            treatment="T",
            outcome="Y",
            all_variables=("Y", "T"),
        )
        assert "obs_ds" in ast.required_datasets()
        assert ast.collect_distribution_refs() == []
