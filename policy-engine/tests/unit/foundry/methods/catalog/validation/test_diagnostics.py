from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods import MethodComposer, execute_heterogeneous_chain
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)


def _method_or_skip(registry, fqn):
    return registry.get(fqn)


def _register_fold_scores_source(registry) -> str:
    """Register a typed producer for the cross-validation input slot."""
    output_slot = SlotSpec(
        "fold_scores", SlotType.VECTOR, Unit("score", "value"), shape=("n_folds",)
    )
    input_slot = SlotSpec(
        "seed_scores", SlotType.VECTOR, Unit("score", "value"), shape=("n_folds",)
    )

    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        return {"fold_scores": state["seed_scores"]}

    producer = type(
        "FoldScoresSource",
        (),
        {
            "signature": MethodSignature(
                name="fold_scores_source",
                namespace="tests.validation.diagnostics",
                version="1.0.0",
                input_slots=frozenset({input_slot}),
                output_slots=frozenset({output_slot}),
                parameters=(),
                fidelity=FidelityLevel.MEDIUM,
                complexity=ComplexityClass.O_N,
                backend=ComputeBackend.NUMPY,
                supports_jit=False,
                supports_vmap=False,
                supports_grad=False,
            ),
            "metadata": MethodMetadata(
                description="Test producer for declared cross-validation fold scores.",
                tags=frozenset({"test", "validation", "cross-validation"}),
            ),
            "pure_step": staticmethod(pure_step),
        },
    )
    return registry.register(producer)


def _cross_validation_chain(registry):
    source_fqn = _register_fold_scores_source(registry)
    composer = MethodComposer(registry=registry)
    source = composer.add(source_fqn)
    estimator = composer.add("validation.model.cross_validation@1.0.0")
    composer.connect(source, estimator)
    return composer.build(validate_semantics=False)


class TestCrossValidation:
    def test_named_input_chain_preserves_fold_scores(self, isolated_registry) -> None:
        scores = np.array([0.7, 0.8, 0.9], dtype=float)
        execution = execute_heterogeneous_chain(
            _cross_validation_chain(isolated_registry),
            state={"seed_scores": scores},
            registry=isolated_registry,
            seed=13,
        )

        assert len(execution.node_results) == 2
        result = execution.final_state["result"]
        assert result["n_folds"] == 3
        assert result["mean_score"] == pytest.approx(0.8)
        assert result["min_score"] == pytest.approx(0.7)
        assert result["max_score"] == pytest.approx(0.9)

    def test_chain_without_owner_materializer_exposes_scalarization(
        self, isolated_registry, monkeypatch
    ) -> None:
        method = _method_or_skip(
            isolated_registry, "validation.model.cross_validation@1.0.0"
        )
        assert method.signature.input_slot_names == {"fold_scores"}
        assert "cross-validation" in method.metadata.tags

        monkeypatch.delattr(method, "materialize_input")
        assert method.signature.input_slot_names == {"fold_scores"}
        assert "cross-validation" in method.metadata.tags

        with pytest.raises(IndexError):
            execute_heterogeneous_chain(
                _cross_validation_chain(isolated_registry),
                state={"seed_scores": np.array([0.7, 0.8, 0.9], dtype=float)},
                registry=isolated_registry,
                seed=13,
            )

    def test_materializer_rejects_missing_or_malformed_fold_scores(
        self, isolated_registry
    ) -> None:
        method = _method_or_skip(
            isolated_registry, "validation.model.cross_validation@1.0.0"
        )
        scores = np.array([0.7, 0.8, 0.9], dtype=float)
        malformed_cases = (
            ({}, {}),
            ({}, {"fold_scores_alias": scores}),
            ({"fold_scores_alias": scores}, {}),
            ({"fold_scores": scores, "unexpected": scores}, {}),
        )

        for bound_inputs, fallback_state in malformed_cases:
            with pytest.raises(ValueError, match="fold_scores"):
                method.materialize_input(bound_inputs, fallback_state)

    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"fold_scores": np.array([0.8, 0.85, 0.82, 0.79, 0.83])}
        result = method.pure_step(state, {})
        assert isinstance(result, dict)

    def test_output_finite(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.cross_validation@1.0.0")
        state = {"fold_scores": np.array([0.9, 0.88, 0.91, 0.87])}
        result = method.pure_step(state, {})
        for v in result.values():
            arr = np.asarray(v)
            if arr.dtype.kind == "f":
                assert np.all(np.isfinite(arr))


class TestWalkForward:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "validation.model.walk_forward@1.0.0")
        state = {
            "actuals": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            "forecasts": np.array([1.1, 2.2, 2.8, 4.1, 5.3]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)


class TestCalibrationDiagnostic:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(
            isolated_registry, "validation.calibration.calibration_diagnostic@1.0.0"
        )
        state = {
            "predicted_probs": np.array([0.1, 0.4, 0.6, 0.8, 0.9]),
            "observed_outcomes": np.array([0.0, 0.0, 1.0, 1.0, 1.0]),
        }
        result = method.pure_step(state, {})
        assert isinstance(result, dict)
        report = result["result"]
        assert report.metrics.n_obs == 5
        assert report.truthfulness_receipt is not None
        assert report.truthfulness_receipt.truthfulness_scope == "predictive_calibration"
