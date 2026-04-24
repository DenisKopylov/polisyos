from __future__ import annotations

from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)


def _normal_env(point: float, std: float, level: float = 0.95) -> UncertaintyEnvelope:
    z = 1.96
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - z * std, point + z * std),
        confidence_level=level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def _linear_sim(**params: float) -> dict[str, float]:
    return {"y": 2.0 * params.get("x", 0.0)}


class TestDispatcherEdgeCases:
    def test_dispatcher_empty_envelopes_returns_empty(self) -> None:
        dispatcher = PropagationDispatcher()
        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            {},
            ["y"],
        )
        assert results == []

    def test_dispatcher_empty_metric_ids_returns_empty(self) -> None:
        dispatcher = PropagationDispatcher()
        envelopes = {"x": _normal_env(1.0, 0.5)}
        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            [],
        )
        assert results == []

    def test_dispatcher_explicit_mc_mode(self) -> None:
        config = PropagationConfig(preferred_method="monte_carlo", mc_n_samples=200, mc_seed=42)
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.MONTE_CARLO
        assert results[0].envelope.composition_provenance is not None
        assert (
            results[0].envelope.composition_provenance.composed_flavour
            == ComposedFlavour.MONTE_CARLO
        )
        assert (
            results[0].envelope.composition_provenance.certificate_kind
            == CertificateKind.KOLMOGOROV
        )

    def test_dispatcher_explicit_delta_mode(self) -> None:
        config = PropagationConfig(preferred_method="delta")
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            ["y"],
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.DELTA_METHOD
        assert results[0].envelope.composition_provenance is not None
        assert results[0].envelope.composition_provenance.composed_flavour == ComposedFlavour.DELTA
        assert (
            results[0].envelope.composition_provenance.certificate_kind
            == CertificateKind.TAYLOR_REMAINDER
        )

    def test_dispatcher_non_differentiable_fallback(self) -> None:
        config = PropagationConfig(preferred_method="auto", mc_n_samples=200, mc_seed=42)
        dispatcher = PropagationDispatcher(config)
        envelopes = {"x": _normal_env(1.0, 0.5)}

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            ["y"],
            is_jax_differentiable=False,
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.MONTE_CARLO

    def test_dispatcher_analytical_linear_combination_records_exact_provenance(self) -> None:
        dispatcher = PropagationDispatcher(PropagationConfig(preferred_method="analytical"))
        envelopes = {"x": _normal_env(1.0, 0.5), "z": _normal_env(2.0, 0.25)}

        results = dispatcher.propagate(
            lambda **params: {"y": params["x"] + params["z"]},
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
            weights={"x": 1.0, "z": 1.0},
        )

        assert len(results) == 1
        assert results[0].method_used == PropagationMethod.ANALYTICAL
        assert results[0].envelope.composition_provenance is not None
        assert (
            results[0].envelope.composition_provenance.composed_flavour
            == ComposedFlavour.ANALYTICAL
        )
        assert results[0].envelope.composition_provenance.certificate_kind == CertificateKind.EXACT
        assert results[0].envelope.distribution_payload is not None

    def test_dispatcher_analytical_preserves_delta_ancestry(self) -> None:
        dispatcher = PropagationDispatcher(PropagationConfig(preferred_method="analytical"))
        envelopes = {
            "x": UncertaintyEnvelope(
                point_estimate=1.0,
                confidence_interval=(0.02, 1.98),
                confidence_level=0.95,
                distribution_family=DistributionFamily.NORMAL,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.DELTA_METHOD,
                interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                gate_eligible=True,
            )
        }

        results = dispatcher.propagate(
            _linear_sim,
            {"x": 1.0},
            envelopes,
            ["y"],
            weights={"x": 2.0},
        )

        assert len(results) == 1
        assert results[0].envelope.composition_provenance is not None
        assert results[0].envelope.composition_provenance.composed_flavour == ComposedFlavour.DELTA
        assert results[0].envelope.composition_provenance.exactness == ExactnessKind.APPROXIMATION
        assert (
            results[0].envelope.composition_provenance.certificate_kind
            == CertificateKind.TAYLOR_REMAINDER
        )

    def test_dispatcher_analytical_marks_mixed_ancestry(self) -> None:
        dispatcher = PropagationDispatcher(PropagationConfig(preferred_method="analytical"))
        envelopes = {
            "x": UncertaintyEnvelope(
                point_estimate=1.0,
                confidence_interval=(0.02, 1.98),
                confidence_level=0.95,
                distribution_family=DistributionFamily.NORMAL,
                source=UncertaintySource.CALIBRATION,
                propagation_method=PropagationMethod.DELTA_METHOD,
                interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                gate_eligible=True,
            ),
            "z": UncertaintyEnvelope(
                point_estimate=2.0,
                confidence_interval=(1.51, 2.49),
                confidence_level=0.95,
                distribution_family=DistributionFamily.NORMAL,
                source=UncertaintySource.BOOTSTRAP,
                propagation_method=PropagationMethod.MONTE_CARLO,
                interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
                gate_eligible=True,
                sample_size=200,
                metadata={"mc_sampling_method": "random"},
            ),
        }

        results = dispatcher.propagate(
            lambda **params: {"y": params["x"] + params["z"]},
            {"x": 1.0, "z": 2.0},
            envelopes,
            ["y"],
            weights={"x": 1.0, "z": 1.0},
        )

        assert len(results) == 1
        assert results[0].envelope.composition_provenance is not None
        assert results[0].envelope.composition_provenance.composed_flavour == ComposedFlavour.MIXED
        assert (
            results[0].envelope.composition_provenance.certificate_kind
            == CertificateKind.WASSERSTEIN_1
        )
