from __future__ import annotations

from polisyos.foundry.methods.catalog.survey import ensure_survey_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_survey_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_survey_methods_registered()
    registry = MethodRegistry.get_instance()

    weighting_names = {sig.name for sig in registry.query(namespace="survey.weighting")}
    assert weighting_names.issuperset({"horvitz_thompson", "raking", "propensity"})

    adaptive_names = {sig.name for sig in registry.query(namespace="survey.adaptive")}
    assert adaptive_names == {"adaptive_augmented", "adaptive_calibrated_ipw"}

    design_names = {sig.name for sig in registry.query(namespace="survey.design")}
    assert design_names == {"complex_survey"}

    estimation_names = {sig.name for sig in registry.query(namespace="survey.estimation")}
    assert estimation_names.issuperset(
        {
            "fay_herriot",
            "fay_herriot_dependence_aware",
            "causal_frontier_fay_herriot",
            "calibration_greg",
        }
    )

    imputation_names = {sig.name for sig in registry.query(namespace="survey.imputation")}
    assert imputation_names.issuperset({"mice", "nonresponse_adjustment"})

    semiparametric_names = {sig.name for sig in registry.query(namespace="survey.semiparametric")}
    assert semiparametric_names == {"ate", "att", "subgroup_mean"}
