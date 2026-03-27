"""
Method selection A/B benchmark: verify that rank_method_catalog_entries
returns the correct top method for known problem types.

Uses realistic MethodCatalogEntry mocks matching real catalog FQNs.
"""
from __future__ import annotations

import pytest

from polisyos.core.contracts.execution_plan import MethodCatalogEntry
from polisyos.foundry.methods.selection import (
    MethodSelectionCriteria,
    rank_method_catalog_entries,
)


def _entry(fqn: str, family: str, **kw) -> MethodCatalogEntry:
    """Build a minimal MethodCatalogEntry."""
    ns, rest = fqn.rsplit(".", 1)
    name_ver = rest.split("@")
    name = name_ver[0]
    version = name_ver[1] if len(name_ver) > 1 else "1.0.0"
    defaults = dict(
        fqn=fqn,
        namespace=ns,
        name=name,
        version=version,
        backend="numpy",
        execution_backend="numpy",
        kind="estimator",
        family=family,
        variant="default",
        fidelity_tier="medium",
        determinism_tier="library_deterministic",
        data_modalities=["tabular"],
        runtime_stack=["numpy"],
        side_effect_profile="pure",
        runnable=True,
    )
    defaults.update(kw)
    return MethodCatalogEntry(**defaults)


# Pool of realistic entries across domains
CATALOG_ENTRIES = [
    _entry("distributional.inequality.lorenz_curve@1.0.0", "distributional.inequality"),
    _entry("distributional.inequality.atkinson@1.0.0", "distributional.inequality"),
    _entry("distributional.inequality.generalized_entropy@1.0.0", "distributional.inequality"),
    _entry("distributional.poverty.fgt@1.0.0", "distributional.poverty"),
    _entry("distributional.poverty.multidimensional@1.0.0", "distributional.poverty"),
    _entry("econometrics.panel.fixed_effects@1.0.0", "econometrics.panel", data_modalities=["panel"]),
    _entry("econometrics.panel.random_effects@1.0.0", "econometrics.panel", data_modalities=["panel"]),
    _entry("econometrics.timeseries.garch@1.0.0", "econometrics.timeseries", data_modalities=["time-series"]),
    _entry("forecasting.univariate.exponential_smoothing@1.0.0", "forecasting.univariate", data_modalities=["time-series"]),
    _entry("forecasting.univariate.theta@1.0.0", "forecasting.univariate", data_modalities=["time-series"]),
    _entry("sensitivity.global.sobol_first_order@1.0.0", "sensitivity.global"),
    _entry("sensitivity.global.morris@1.0.0", "sensitivity.global"),
    _entry("survey.estimation.fay_herriot@1.0.0", "survey.estimation"),
    _entry("survey.estimation.calibration_greg@1.0.0", "survey.estimation"),
    _entry("bayesian.regression.linear_regression@1.0.0", "bayesian.regression"),
    _entry("spatial.autocorrelation.moran_i@1.0.0", "spatial.autocorrelation", data_modalities=["spatial"]),
    _entry("ml.regression.elastic_net@1.0.0", "ml.regression"),
    _entry("ml.regression.random_forest@1.0.0", "ml.regression"),
    _entry("network.community.community_detection@1.0.0", "network.community", data_modalities=["network"]),
    _entry("validation.model.cross_validation@1.0.0", "validation.model"),
    _entry("validation.probabilistic.normal_scores@1.0.0", "validation.probabilistic"),
]


SELECTION_SCENARIOS = [
    {
        "name": "inequality",
        "criteria": MethodSelectionCriteria(preferred_family="distributional.inequality"),
        "expected_top_contains": "distributional.inequality",
    },
    {
        "name": "poverty",
        "criteria": MethodSelectionCriteria(preferred_family="distributional.poverty"),
        "expected_top_contains": "distributional.poverty",
    },
    {
        "name": "panel_econometrics",
        "criteria": MethodSelectionCriteria(preferred_family="econometrics.panel"),
        "expected_top_contains": "econometrics.panel",
    },
    {
        "name": "forecasting",
        "criteria": MethodSelectionCriteria(preferred_family="forecasting.univariate"),
        "expected_top_contains": "forecasting",
    },
    {
        "name": "sensitivity",
        "criteria": MethodSelectionCriteria(preferred_family="sensitivity.global"),
        "expected_top_contains": "sensitivity",
    },
    {
        "name": "survey",
        "criteria": MethodSelectionCriteria(preferred_family="survey.estimation"),
        "expected_top_contains": "survey",
    },
    {
        "name": "bayesian",
        "criteria": MethodSelectionCriteria(preferred_family="bayesian.regression"),
        "expected_top_contains": "bayesian",
    },
    {
        "name": "spatial",
        "criteria": MethodSelectionCriteria(preferred_family="spatial.autocorrelation"),
        "expected_top_contains": "spatial",
    },
    {
        "name": "ml",
        "criteria": MethodSelectionCriteria(preferred_family="ml.regression"),
        "expected_top_contains": "ml",
    },
    {
        "name": "network",
        "criteria": MethodSelectionCriteria(preferred_family="network.community"),
        "expected_top_contains": "network",
    },
]


@pytest.mark.benchmark
@pytest.mark.parametrize(
    "scenario",
    SELECTION_SCENARIOS,
    ids=[s["name"] for s in SELECTION_SCENARIOS],
)
def test_selection_quality(scenario):
    """For each problem type, verify the top-ranked method is from the correct domain."""
    ranked = rank_method_catalog_entries(
        CATALOG_ENTRIES,
        scenario["criteria"],
        limit=5,
    )
    assert len(ranked) > 0, f"No methods ranked for {scenario['name']}"
    top_fqn = ranked[0].fqn
    assert scenario["expected_top_contains"] in top_fqn, (
        f"Selection mismatch for {scenario['name']}: "
        f"expected '{scenario['expected_top_contains']}' in top FQN, "
        f"got '{top_fqn}'"
    )
