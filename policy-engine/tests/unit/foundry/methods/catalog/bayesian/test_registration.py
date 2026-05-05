from __future__ import annotations

from polisyos.foundry.methods.bayesian import ensure_bayesian_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_bayesian_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_bayesian_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("bayesian.")]
    names = {sig.name for sig in signatures}

    assert names == {
        "linear_regression",
        "autoregression",
        "hierarchical",
        "hmc",
        "nuts",
        "gaussian_mixture",
        "dirichlet_process_mixture",
        "gp_regression",
        "sparse_gp_regression",
        "bbvi",
        "mean_field_vi",
        "expectation_propagation_gaussian",
        "svgd_regression",
        "affine_normalizing_flow",
        "factor_graph_belief_propagation",
        "npe",
        "nle",
        "nre",
        "bart_regression",
    }
