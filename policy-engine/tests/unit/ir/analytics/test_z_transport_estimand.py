"""Tests for make_z_transport_estimand() — Z-transport estimand constructor."""

import pytest
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    SideConditionKind,
    SumNode,
    make_z_transport_estimand,
)


class TestMakeZTransportEstimand:
    def _simple(self) -> EstimandAST:
        return make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
        )

    # --- Structure ---

    def test_returns_estimand_ast(self):
        est = self._simple()
        assert isinstance(est, EstimandAST)

    def test_query_str(self):
        est = self._simple()
        assert est.query_str == "P*(Y|do(X))"

    def test_treatment_and_outcome(self):
        est = self._simple()
        assert est.treatment == "X"
        assert est.outcome == "Y"

    def test_identification_method(self):
        est = self._simple()
        assert est.identification_method == "z_transport"

    def test_all_variables_contains_z(self):
        est = self._simple()
        assert "X" in est.all_variables
        assert "Y" in est.all_variables
        assert "Z" in est.all_variables

    def test_root_is_sum_node(self):
        est = self._simple()
        assert isinstance(est.root, SumNode)
        assert "Z" in est.root.summation_vars

    def test_sum_node_operand_is_product(self):
        est = self._simple()
        assert isinstance(est.root.operand, ProductNode)

    def test_product_has_two_factors(self):
        est = self._simple()
        factors = est.root.operand.factors
        assert len(factors) == 2

    def test_pz_factor_is_experimental(self):
        est = self._simple()
        factors = est.root.operand.factors
        # pz_factor is the first factor: EXPERIMENTAL domain
        pz = next(
            (
                f
                for f in factors
                if isinstance(f, DistributionRef) and f.domain is DistributionDomain.EXPERIMENTAL
            ),
            None,
        )
        assert pz is not None, "No EXPERIMENTAL factor found"

    def test_pstar_z_factor_is_target(self):
        est = self._simple()
        factors = est.root.operand.factors
        ptarget = next(
            (
                f
                for f in factors
                if isinstance(f, DistributionRef) and f.domain is DistributionDomain.TARGET
            ),
            None,
        )
        assert ptarget is not None, "No TARGET factor found"

    def test_pz_factor_variables(self):
        est = self._simple()
        factors = est.root.operand.factors
        pz = next(
            f
            for f in factors
            if isinstance(f, DistributionRef) and f.domain is DistributionDomain.EXPERIMENTAL
        )
        assert "Y" in pz.variables

    def test_pz_factor_conditioning_contains_treatment_and_z(self):
        est = self._simple()
        factors = est.root.operand.factors
        pz = next(
            f
            for f in factors
            if isinstance(f, DistributionRef) and f.domain is DistributionDomain.EXPERIMENTAL
        )
        assert "X" in pz.conditioning
        assert "Z" in pz.conditioning

    def test_pz_factor_intervention_set(self):
        est = self._simple()
        factors = est.root.operand.factors
        pz = next(
            f
            for f in factors
            if isinstance(f, DistributionRef) and f.domain is DistributionDomain.EXPERIMENTAL
        )
        assert "X" in pz.intervention_set

    def test_pstar_z_variables_are_z_vars(self):
        est = self._simple()
        factors = est.root.operand.factors
        pstar = next(
            f
            for f in factors
            if isinstance(f, DistributionRef) and f.domain is DistributionDomain.TARGET
        )
        assert "Z" in pstar.variables

    # --- Required domains ---

    def test_required_domains_includes_experimental_and_target(self):
        est = self._simple()
        domains = est.required_domains()
        assert DistributionDomain.EXPERIMENTAL in domains
        assert DistributionDomain.TARGET in domains

    def test_required_domains_not_source(self):
        est = self._simple()
        domains = est.required_domains()
        # Z-transport uses EXPERIMENTAL (not SOURCE) for the interventional factor
        assert DistributionDomain.SOURCE not in domains

    # --- Side conditions ---

    def test_overlap_side_condition_present(self):
        est = self._simple()
        overlap = [sc for sc in est.side_conditions if sc.kind is SideConditionKind.OVERLAP]
        assert len(overlap) >= 1

    def test_overlap_side_condition_covers_z_vars(self):
        est = self._simple()
        overlap = next(sc for sc in est.side_conditions if sc.kind is SideConditionKind.OVERLAP)
        assert "Z" in overlap.variables

    # --- Dataset refs ---

    def test_default_dataset_refs(self):
        est = self._simple()
        refs = est.required_datasets()
        assert "source" in refs
        assert "target" in refs

    def test_custom_dataset_refs(self):
        est = make_z_transport_estimand(
            treatment="T",
            outcome="Y",
            z_vars=("Z",),
            source_dataset_ref="rct_us_2020",
            target_dataset_ref="target_pop",
        )
        refs = est.required_datasets()
        assert "rct_us_2020" in refs
        assert "target_pop" in refs

    # --- Multiple Z vars ---

    def test_multiple_z_vars(self):
        est = make_z_transport_estimand(
            treatment="T",
            outcome="Y",
            z_vars=("Z1", "Z2"),
        )
        assert "Z1" in est.all_variables
        assert "Z2" in est.all_variables
        assert "Z1" in est.root.summation_vars
        assert "Z2" in est.root.summation_vars

    def test_multiple_z_in_pz_conditioning(self):
        est = make_z_transport_estimand(
            treatment="T",
            outcome="Y",
            z_vars=("Z1", "Z2"),
        )
        factors = est.root.operand.factors
        pz = next(
            f
            for f in factors
            if isinstance(f, DistributionRef) and f.domain is DistributionDomain.EXPERIMENTAL
        )
        assert "Z1" in pz.conditioning
        assert "Z2" in pz.conditioning

    # --- Validation ---

    def test_empty_z_vars_raises_value_error(self):
        with pytest.raises(ValueError, match="z_var"):
            make_z_transport_estimand(treatment="T", outcome="Y", z_vars=())

    # --- Serialisation ---

    def test_round_trip_json(self):
        est = self._simple()
        data = est.model_dump(mode="json")
        restored = EstimandAST.model_validate(data)
        assert restored.identification_method == "z_transport"
        assert restored.treatment == "X"
        assert restored.outcome == "Y"

    # --- LaTeX ---

    def test_to_latex_non_empty(self):
        est = self._simple()
        latex = est.to_latex()
        assert len(latex) > 0

    def test_to_latex_contains_sum_symbol(self):
        est = self._simple()
        latex = est.to_latex()
        assert "sum" in latex.lower() or "\\sum" in latex

    # --- Distinct from reweight estimand ---

    def test_different_from_transport_reweight(self):
        from polisyos.ir.analytics.estimand import make_transport_reweight_estimand

        z_est = make_z_transport_estimand(treatment="X", outcome="Y", z_vars=("Z",))
        rw_est = make_transport_reweight_estimand(
            treatment="X", outcome="Y", reweighting_vars=("Z",)
        )
        assert z_est.identification_method == "z_transport"
        assert rw_est.identification_method == "transport_reweight"
        # Z-transport uses EXPERIMENTAL; reweight uses SOURCE
        assert DistributionDomain.EXPERIMENTAL in z_est.required_domains()
        assert DistributionDomain.EXPERIMENTAL not in rw_est.required_domains()
