from __future__ import annotations

from polisyos.foundry.uncertainty.protocol import (
    UncertaintyDecomposition,
    gaussian_uncertainty_envelope,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintySource,
)


def test_gaussian_uncertainty_envelope_builds_statistical_interval() -> None:
    envelope = gaussian_uncertainty_envelope(
        point_estimate=1.5,
        std=0.2,
        confidence_level=0.9,
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.NORMAL,
        propagation_method=PropagationMethod.MONTE_CARLO,
        metadata={"metric": "policy_loss"},
    )

    assert envelope.point_estimate == 1.5
    assert envelope.interval_semantics == IntervalSemantics.CREDIBLE_INTERVAL
    assert envelope.metadata["metric"] == "policy_loss"
    assert envelope.ci_lower < envelope.point_estimate < envelope.ci_upper


def test_uncertainty_decomposition_combines_epistemic_and_aleatoric_components() -> None:
    decomposition = UncertaintyDecomposition.from_gaussian_components(
        metric_id="policy_loss",
        point_estimate=2.0,
        confidence_level=0.95,
        epistemic_std=0.3,
        aleatoric_std=0.4,
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.BAYESIAN,
        propagation_method=PropagationMethod.MONTE_CARLO,
        metadata={"method": "posterior_predictive"},
    )

    assert decomposition.metric_id == "policy_loss"
    assert decomposition.epistemic is not None
    assert decomposition.aleatoric is not None
    assert decomposition.total.ci_width >= decomposition.epistemic.ci_width
    assert decomposition.total.metadata["component"] == "total"
    assert decomposition.as_dict()["diagnostics"]["total_std"] > 0.0
