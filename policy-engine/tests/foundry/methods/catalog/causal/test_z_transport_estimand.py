"""Tests for Z-transport estimand construction and classifier integration."""
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
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    EstimandShape,
    classify_estimand,
)


class TestMakeZTransportEstimand:
    """Test make_z_transport_estimand() factory function."""

    def test_basic_construction(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
        )
        assert isinstance(ast, EstimandAST)
        assert ast.treatment == "X"
        assert ast.outcome == "Y"
        assert ast.identification_method == "z_transport"
        assert ast.query_str == "P*(Y|do(X))"

    def test_multi_z_vars(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z1", "Z2"),
        )
        assert "Z1" in ast.all_variables
        assert "Z2" in ast.all_variables
        assert isinstance(ast.root, SumNode)
        assert set(ast.root.summation_vars) == {"Z1", "Z2"}

    def test_empty_z_vars_raises(self):
        with pytest.raises(ValueError, match="at least one z_var"):
            make_z_transport_estimand(treatment="X", outcome="Y", z_vars=())

    def test_domains_contain_experimental_and_target(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
        )
        domains = ast.required_domains()
        assert DistributionDomain.EXPERIMENTAL in domains
        assert DistributionDomain.TARGET in domains

    def test_distribution_refs(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
            source_dataset_ref="study_1",
            target_dataset_ref="target_pop",
        )
        dist_refs = ast.collect_distribution_refs()
        assert len(dist_refs) == 2
        domains = {dr.domain for dr in dist_refs}
        assert domains == {DistributionDomain.EXPERIMENTAL, DistributionDomain.TARGET}
        # Check dataset refs
        refs = {dr.dataset_ref for dr in dist_refs}
        assert "study_1" in refs
        assert "target_pop" in refs

    def test_side_conditions_overlap(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
        )
        assert len(ast.side_conditions) == 1
        sc = ast.side_conditions[0]
        assert sc.kind == SideConditionKind.OVERLAP
        assert "Z" in sc.variables
        assert sc.required is True


class TestClassifyZTransportEstimand:
    """Test that the estimand compiler correctly classifies Z-transport estimands."""

    def test_classifies_as_transport_reweight(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z",),
        )
        shape = classify_estimand(ast)
        assert shape == EstimandShape.TRANSPORT_REWEIGHT, (
            f"Z-transport estimand should classify as TRANSPORT_REWEIGHT, got {shape}"
        )

    def test_multi_z_classifies_as_transport_reweight(self):
        ast = make_z_transport_estimand(
            treatment="X",
            outcome="Y",
            z_vars=("Z1", "Z2", "Z3"),
        )
        shape = classify_estimand(ast)
        assert shape == EstimandShape.TRANSPORT_REWEIGHT
