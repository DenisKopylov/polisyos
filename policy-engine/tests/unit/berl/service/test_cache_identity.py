from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import ClassVar

import pytest

import polisyos.berl.service as berl_service
from polisyos.berl.adapters.ale import ALEAdapter
from polisyos.berl.adapters.lime import LIMEAdapter
from polisyos.berl.adapters.protocol import (
    ExplanationAdapter,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UnavailableAdapter,
)
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest
from polisyos.berl.service.cache_identity import _adapter_cache_identity


class _PreResultFailureAdapter(UnavailableAdapter):
    """Adapter that fails before producing an explanation for the failure counterfactual."""

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        del model, x, context
        raise RuntimeError(self.diagnostic)


class _MislabeledKernelAdapter(KernelSHAPAdapter):
    """Return a real result whose payload tries to self-assign another identity."""

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        raw = super().explain(model, x, context)
        return replace(
            raw,
            method_id="payload_claimed_method",
            effective_method_id="payload_claimed_effective",
            params={**raw.params, "effective_method_id": "payload_claimed_effective"},
        )


# These exercise cache_identity through the real ExplanationOrchestrator route; they are
# integration witnesses for reuse and method identity, not pure helper-only checks.


def test_builtin_adapter_profiles_are_not_collapsed() -> None:
    ale_identity = _adapter_cache_identity(ALEAdapter(), "ale_local_bin")
    lime_identity = _adapter_cache_identity(LIMEAdapter(), "lime")

    assert ale_identity is not None
    assert lime_identity is not None
    assert ale_identity != lime_identity


class _CustomKernelSubclass(KernelSHAPAdapter):
    """A subclass remains executable but has no source-owned cache identity."""

    calls: ClassVar[list[str]] = []

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        type(self).calls.append(self.method_id)
        return super().explain(model, x, context)


def test_custom_adapter_subclass_is_executed_for_each_duplicate_route() -> None:
    _CustomKernelSubclass.calls = []
    adapter = _CustomKernelSubclass(method_id="custom_kernel")
    request = _request_for_kernel_aliases(("custom_kernel", "custom_kernel"), feature_count=1)

    bundle = ExplanationOrchestrator(adapters={"custom_kernel": adapter}).explain(
        lambda features: features["x0"],
        request,
    )

    assert _adapter_cache_identity(adapter, "kernel_shap") is None
    assert _CustomKernelSubclass.calls == ["custom_kernel", "custom_kernel"]
    assert [method.requested_method_id for method in bundle.methods] == [
        "custom_kernel",
        "custom_kernel",
    ]
    assert all(method.effective_method_id == "kernel_shap" for method in bundle.methods)


@pytest.mark.parametrize(
    ("method_id", "feature_dependence_policy", "adapters", "expected_diagnostic"),
    [
        pytest.param(
            "kernel_shap",
            "conditional_observational",
            None,
            "no verified conditional law",
            id="default-kernel-unsupported-conditional",
        ),
        pytest.param(
            "kernel_shap_conditional",
            "conditional_observational",
            None,
            "no verified conditional law",
            id="explicit-conditional-unavailable",
        ),
        pytest.param(
            "missing_adapter",
            "marginal_interventional",
            None,
            "adapter_not_registered",
            id="unregistered-method",
        ),
        pytest.param(
            "unavailable_adapter",
            "marginal_interventional",
            {
                "unavailable_adapter": UnavailableAdapter(
                    method_id="unavailable_adapter",
                    diagnostic="conditional backend unavailable",
                )
            },
            "conditional backend unavailable",
            id="selected-unavailable-adapter",
        ),
        pytest.param(
            "pre_result_error",
            "marginal_interventional",
            {
                "pre_result_error": _PreResultFailureAdapter(
                    method_id="pre_result_error",
                    diagnostic="adapter failed before returning a result",
                )
            },
            "adapter failed before returning a result",
            id="selected-adapter-pre-result-error",
        ),
    ],
)
def test_unexecuted_diagnostics_leave_effective_method_identity_unset(
    method_id: str,
    feature_dependence_policy: str,
    adapters: Mapping[str, ExplanationAdapter] | None,
    expected_diagnostic: str,
) -> None:
    request = ExplanationRequest(
        prediction_id=f"prediction-{method_id}",
        row_id="row-1",
        x={"x1": 1.0},
        feature_names=("x1",),
        methods=(method_id,),
        feature_dependence_policy=feature_dependence_policy,
        background_rows=({"x1": 0.0}, {"x1": 1.0}),
        n_eval_perturbations=2,
        random_seed=7,
        include_disagreement=False,
        include_redundancy=False,
    )

    bundle = ExplanationOrchestrator(adapters=adapters).explain(
        lambda features: features["x1"],
        request,
    )

    method = bundle.methods[0]
    assert bundle.faithfulness_claim == "unbounded"
    assert bundle.display_policy == "diagnostic_only"
    assert method.method_id == method_id
    assert method.requested_method_id == method_id
    assert method.effective_method_id is None
    assert method.params["requested_method_id"] == method_id
    assert method.params["effective_method_id"] is None
    assert expected_diagnostic in str(method.params["diagnostic"])
    assert method.scope == "diagnostic"
    assert method.attributions == []
    assert method.fallback is False
    assert method.fallback_reason is None


def test_marginal_alias_reuse_preserves_confidence_count_and_single_calculation() -> None:
    one_alias_calls: list[dict[str, float]] = []
    two_alias_calls: list[dict[str, float]] = []

    def one_alias_model(features: Mapping[str, float]) -> float:
        one_alias_calls.append(dict(features))
        return float(features["x1"])

    def two_alias_model(features: Mapping[str, float]) -> float:
        two_alias_calls.append(dict(features))
        return float(features["x1"])

    def request(methods: tuple[str, ...]) -> ExplanationRequest:
        return ExplanationRequest(
            prediction_id=f"prediction-{len(methods)}",
            row_id="row-1",
            x={"x1": 1.0},
            feature_names=("x1",),
            methods=methods,
            feature_dependence_policy="marginal_interventional",
            background_rows=({"x1": 0.0}, {"x1": 1.0}),
            n_eval_perturbations=2,
            random_seed=7,
            include_disagreement=True,
            include_redundancy=False,
        )

    one_alias_bundle = ExplanationOrchestrator().explain(one_alias_model, request(("kernel_shap",)))
    two_alias_bundle = ExplanationOrchestrator().explain(
        two_alias_model, request(("kernel_shap", "kernel_shap_marginal"))
    )

    assert len(two_alias_calls) == len(one_alias_calls)
    assert two_alias_bundle.disagreement is None
    assert [method.requested_method_id for method in two_alias_bundle.methods] == [
        "kernel_shap",
        "kernel_shap_marginal",
    ]
    assert all(method.effective_method_id == "kernel_shap" for method in two_alias_bundle.methods)
    assert all(
        method.infidelity is not None and method.infidelity.confidence == pytest.approx(0.975)
        for method in two_alias_bundle.methods
    )
    assert one_alias_bundle.methods[0].infidelity is not None
    assert one_alias_bundle.methods[0].infidelity.confidence == pytest.approx(0.95)


def _request_for_kernel_aliases(methods: tuple[str, ...], feature_count: int) -> ExplanationRequest:
    feature_names = tuple(f"x{index}" for index in range(feature_count))
    return ExplanationRequest(
        prediction_id="kernel-alias-failure",
        row_id="row-1",
        x=dict.fromkeys(feature_names, 1.0),
        feature_names=feature_names,
        methods=methods,
        feature_dependence_policy="marginal_interventional",
        background_rows=(
            dict.fromkeys(feature_names, 0.0),
            dict.fromkeys(feature_names, 1.0),
        ),
        n_eval_perturbations=2,
        random_seed=7,
        include_disagreement=False,
        include_redundancy=False,
    )


@pytest.mark.parametrize(
    "methods",
    [
        pytest.param(
            ("kernel_shap", "kernel_shap_marginal"),
            id="canonical-then-alias",
        ),
        pytest.param(
            ("kernel_shap_marginal", "kernel_shap"),
            id="alias-then-canonical",
        ),
        pytest.param(("kernel_shap", "kernel_shap"), id="repeated-same-alias"),
    ],
)
def test_cached_builtin_failure_does_not_reidentify_diagnostic(
    methods: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_calls: list[str] = []
    original_explain = KernelSHAPAdapter.explain

    def record_explain(
        adapter: KernelSHAPAdapter,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        adapter_calls.append(adapter.method_id)
        return original_explain(adapter, model, x, context)

    monkeypatch.setattr(KernelSHAPAdapter, "explain", record_explain)
    names = tuple(f"x{index}" for index in range(11))
    bundle = ExplanationOrchestrator().explain(
        lambda features: sum(features.values()),
        _request_for_kernel_aliases(methods, len(names)),
    )

    assert adapter_calls == [methods[0]]
    assert [method.requested_method_id for method in bundle.methods] == list(methods)
    for method, requested_method_id in zip(bundle.methods, methods, strict=True):
        assert method.method_id == requested_method_id
        assert method.effective_method_id is None
        assert method.params["requested_method_id"] == requested_method_id
        assert method.params["effective_method_id"] is None
        assert "reduce features" in str(method.params["diagnostic"])
        assert method.scope == "diagnostic"
        assert method.attributions == []


def test_cached_post_result_rejection_keeps_effective_identity_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter_calls: list[str] = []
    original_explain = KernelSHAPAdapter.explain

    def record_explain(
        adapter: KernelSHAPAdapter,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        adapter_calls.append(adapter.method_id)
        return original_explain(adapter, model, x, context)

    def reject_after_raw_result(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ValueError("held-out validation rejected the result")

    monkeypatch.setattr(KernelSHAPAdapter, "explain", record_explain)
    monkeypatch.setattr(berl_service, "build_heldout_records", reject_after_raw_result)
    methods = ("kernel_shap", "kernel_shap_marginal")
    bundle = ExplanationOrchestrator().explain(
        lambda features: features["x0"],
        _request_for_kernel_aliases(methods, feature_count=1),
    )

    assert adapter_calls == ["kernel_shap"]
    assert [method.requested_method_id for method in bundle.methods] == list(methods)
    for method, requested_method_id in zip(bundle.methods, methods, strict=True):
        assert method.method_id == requested_method_id
        assert method.effective_method_id is None
        assert method.params["requested_method_id"] == requested_method_id
        assert method.params["effective_method_id"] is None
        assert method.params["diagnostic"] == "held-out validation rejected the result"
        assert method.scope == "diagnostic"
        assert method.attributions == []


def test_selected_execution_identity_overrides_mislabeled_raw_result() -> None:
    bundle = ExplanationOrchestrator(
        adapters={"selected_kernel": _MislabeledKernelAdapter(method_id="selected_kernel")}
    ).explain(
        lambda features: features["x0"],
        _request_for_kernel_aliases(("selected_kernel",), feature_count=1),
    )

    method = bundle.methods[0]
    assert method.method_id == "selected_kernel"
    assert method.requested_method_id == "selected_kernel"
    assert method.effective_method_id == "kernel_shap"
    assert method.params["effective_method_id"] == "kernel_shap"
    assert "payload_claimed_effective" not in method.model_dump_json()
