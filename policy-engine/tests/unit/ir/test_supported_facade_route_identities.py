from __future__ import annotations

from importlib import import_module

from polisyos.core.contracts import MetricValidationReportRef as CoreMetricValidationReportRef
from polisyos.ir import analytics, governance, kernel, loading, model_layer, registry, trinity
from polisyos.ir.api import (
    LOADING_FACADE_EXPORTS,
    MODEL_LAYER_FACADE_EXPORTS,
    REGISTRY_FACADE_EXPORTS,
)
from polisyos.ir.registry.refs import MetricValidationReportRef as IRMetricValidationReportRef


def test_loading_facade_exports_owner_objects() -> None:
    from polisyos.ir.loading.citations import CitationRef
    from polisyos.ir.loading.fact_log import Fact, FactSegmentManifest

    assert loading.CitationRef is CitationRef
    assert loading.Fact is Fact
    assert loading.FactSegmentManifest is FactSegmentManifest
    assert set(loading.__all__) == set(LOADING_FACADE_EXPORTS)


def test_registry_facade_preserves_full_typed_reference_family() -> None:
    for name, (module_name, owner_name) in REGISTRY_FACADE_EXPORTS.items():
        assert getattr(registry, name) is getattr(import_module(module_name), owner_name)
    assert registry.MetricValidationReportRef is IRMetricValidationReportRef
    assert IRMetricValidationReportRef is not CoreMetricValidationReportRef


def test_model_and_existing_ir_facades_preserve_owner_identity() -> None:
    from polisyos.ir.analytics.partial_identification import BoundSoundnessLevel
    from polisyos.ir.governance.policy_spec import PolicySearchLevel
    from polisyos.ir.kernel.values import ParamValue
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity.loaders import load_trinity_bundle_artifact

    assert analytics.BoundSoundnessLevel is BoundSoundnessLevel
    assert governance.PolicySearchLevel is PolicySearchLevel
    assert kernel.ParamValue is ParamValue
    assert model_layer.SelectorOperator is SelectorOperator
    assert trinity.load_trinity_bundle_artifact is load_trinity_bundle_artifact
    assert set(model_layer.__all__) == set(MODEL_LAYER_FACADE_EXPORTS)
