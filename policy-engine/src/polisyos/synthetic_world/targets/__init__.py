"""Truth-target builders for synthetic worlds."""

from .bayesian import (
    exact_linear_regression_posterior,
    reference_posterior_summary,
    register_latent_state_targets,
    register_prior_targets,
    register_reference_posterior_targets,
)
from .causal import register_cross_sectional_causal_targets, register_dynamic_causal_targets, register_spatial_causal_targets
from .distributional import register_distributional_targets
from .econometrics import register_cross_sectional_econometrics_targets, register_panel_econometrics_targets, register_survey_econometrics_targets
from .forecasting import register_forecasting_targets
from .ml import register_binary_classification_targets, register_regression_targets
from .survey import register_survey_targets

__all__ = [
    "exact_linear_regression_posterior",
    "reference_posterior_summary",
    "register_latent_state_targets",
    "register_binary_classification_targets",
    "register_cross_sectional_causal_targets",
    "register_cross_sectional_econometrics_targets",
    "register_distributional_targets",
    "register_dynamic_causal_targets",
    "register_forecasting_targets",
    "register_panel_econometrics_targets",
    "register_prior_targets",
    "register_regression_targets",
    "register_reference_posterior_targets",
    "register_spatial_causal_targets",
    "register_survey_econometrics_targets",
    "register_survey_targets",
]
