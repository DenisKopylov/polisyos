"""Cache identity rules for BERL service requests."""

from __future__ import annotations

import struct
from dataclasses import fields
from enum import Enum
from typing import TYPE_CHECKING, TypeGuard

from polisyos.berl.adapters import (
    ALEAdapter,
    EBMComponentAdapter,
    FiniteDifferenceGradientAdapter,
    KernelSHAPAdapter,
    LIMEAdapter,
    PermutationImportanceAdapter,
    TreeSHAPAdapter,
)
from polisyos.berl.perturbations import FeatureConstraint

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.berl.adapters.protocol import (
        ExplanationAdapter,
        ExplanationContext,
        ScalarModel,
    )
    from polisyos.berl.service import ExplanationRequest

_CACHE_IDENTITY_UNSUPPORTED = object()
type _BuiltinAdapter = (
    ALEAdapter
    | EBMComponentAdapter
    | FiniteDifferenceGradientAdapter
    | KernelSHAPAdapter
    | LIMEAdapter
    | PermutationImportanceAdapter
    | TreeSHAPAdapter
)
_BUILTIN_EFFECTIVE_METHODS: dict[type[_BuiltinAdapter], str] = {
    ALEAdapter: "ale_local_bin",
    EBMComponentAdapter: "ebm_components",
    FiniteDifferenceGradientAdapter: "finite_difference_gradient",
    KernelSHAPAdapter: "kernel_shap",
    LIMEAdapter: "lime",
    PermutationImportanceAdapter: "permutation_importance",
    TreeSHAPAdapter: "kernel_shap",
}


def _effective_method_id(adapter: ExplanationAdapter) -> str:
    if _is_builtin_adapter(adapter):
        return _BUILTIN_EFFECTIVE_METHODS[type(adapter)]
    candidate = getattr(adapter, "effective_method_id", None)
    if isinstance(candidate, str) and candidate:
        return candidate
    return adapter.method_id


def _effective_request_key(
    *,
    model: ScalarModel,
    request: ExplanationRequest,
    context: ExplanationContext,
    adapter: ExplanationAdapter,
    effective_method_id: str,
) -> tuple[object, ...] | None:
    """Return a complete request key only for known built-ins and typed inputs.

    Custom adapters remain executable, but are not automatically reused because
    the protocol has no source-owned cache-identity contract for their state.
    """

    adapter_identity = _adapter_cache_identity(adapter, effective_method_id)
    if adapter_identity is None:
        return None
    request_values = (
        _freeze(request.x),
        _freeze(request.feature_names),
        _freeze(request.background_rows),
        _freeze(request.adapter_params),
        _freeze(request.constraints),
    )
    if any(value is _CACHE_IDENTITY_UNSUPPORTED for value in request_values):
        return None
    return (
        "berl-effective-request-v3",
        adapter_identity,
        id(model),
        request.model_id,
        request.model_hash,
        request.model_class,
        request.training_data_hash,
        request.calibration_ref,
        *request_values,
        context.output_scale,
        context.perturbation_distribution,
        context.feature_dependence_policy,
        context.confidence,
        context.random_seed,
        request.n_eval_perturbations,
        request.perturbation_radius,
        request.residual_cap,
        request.include_redundancy,
    )


def _adapter_cache_identity(
    adapter: ExplanationAdapter,
    effective_method_id: str,
) -> tuple[object, ...] | None:
    """Return identity for an exact, source-owned immutable built-in adapter.

    Custom adapters, dataclass or otherwise, execute every selected route until
    the adapter protocol supplies an admitted cache-configuration contract.
    """

    if not _is_builtin_adapter(adapter):
        return None
    builtin_profile = _BUILTIN_EFFECTIVE_METHODS[type(adapter)]
    if effective_method_id != builtin_profile:
        return None

    adapter_method_id = object.__getattribute__(adapter, "method_id")
    shared_kernel_profile = (
        isinstance(adapter, KernelSHAPAdapter)
        and type(adapter) is KernelSHAPAdapter
        and adapter_method_id in {"kernel_shap", "kernel_shap_marginal"}
        and builtin_profile == "kernel_shap"
    )
    shared_tree_fallback = (
        isinstance(adapter, TreeSHAPAdapter)
        and type(adapter) is TreeSHAPAdapter
        and adapter_method_id == "tree_shap"
        and builtin_profile == "kernel_shap"
    )
    identity_type = (
        KernelSHAPAdapter if shared_kernel_profile or shared_tree_fallback else type(adapter)
    )
    configuration: list[tuple[str, object]] = []
    for item in fields(adapter):
        if (shared_kernel_profile or shared_tree_fallback) and item.name == "method_id":
            continue
        frozen_value = _freeze_immutable_configuration(object.__getattribute__(adapter, item.name))
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return None
        configuration.append((item.name, frozen_value))
    return (
        identity_type.__module__,
        identity_type.__qualname__,
        builtin_profile,
        tuple(configuration),
    )


def _is_builtin_adapter(adapter: ExplanationAdapter) -> TypeGuard[_BuiltinAdapter]:
    """Narrow to exact registered built-ins eligible for dataclass identity."""

    if not isinstance(
        adapter,
        (
            ALEAdapter,
            EBMComponentAdapter,
            FiniteDifferenceGradientAdapter,
            KernelSHAPAdapter,
            LIMEAdapter,
            PermutationImportanceAdapter,
            TreeSHAPAdapter,
        ),
    ):
        return False
    return type(adapter) in _BUILTIN_EFFECTIVE_METHODS


def _freeze_scalar(value: object) -> object:
    """Encode supported scalar values with their exact primitive type."""

    if value is None:
        return ("none",)
    if type(value) is bool:
        return ("bool", value)
    if type(value) is int:
        return ("int", value)
    if type(value) is float:
        return ("float64", struct.pack(">d", value).hex())
    if type(value) is str:
        return ("str", value)
    return _CACHE_IDENTITY_UNSUPPORTED


def _freeze_immutable_configuration(value: object) -> object:
    """Freeze typed immutable values for source-owned built-in configuration."""

    if isinstance(value, Enum):
        frozen_value = _freeze_immutable_configuration(value.value)
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("enum", type(value).__module__, type(value).__qualname__, frozen_value)
    scalar = _freeze_scalar(value)
    if scalar is not _CACHE_IDENTITY_UNSUPPORTED:
        return scalar
    if type(value) is dict:
        items = []
        for key, item in value.items():
            frozen_key = _freeze_immutable_configuration(key)
            frozen_item = _freeze_immutable_configuration(item)
            if (
                frozen_key is _CACHE_IDENTITY_UNSUPPORTED
                or frozen_item is _CACHE_IDENTITY_UNSUPPORTED
            ):
                return _CACHE_IDENTITY_UNSUPPORTED
            items.append((frozen_key, frozen_item))
        return ("dict", tuple(sorted(items, key=lambda pair: repr(pair[0]))))
    if type(value) is tuple or type(value) is frozenset:
        frozen_items = tuple(_freeze_immutable_configuration(item) for item in value)
        if any(item is _CACHE_IDENTITY_UNSUPPORTED for item in frozen_items):
            return _CACHE_IDENTITY_UNSUPPORTED
        if type(value) is frozenset:
            frozen_items = tuple(sorted(frozen_items, key=repr))
        return (type(value).__name__, frozen_items)
    if type(value) is FeatureConstraint:
        lower = _freeze_immutable_configuration(object.__getattribute__(value, "lower"))
        upper = _freeze_immutable_configuration(object.__getattribute__(value, "upper"))
        if lower is _CACHE_IDENTITY_UNSUPPORTED or upper is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("feature_constraint", lower, upper)
    return _CACHE_IDENTITY_UNSUPPORTED


def _freeze(value: object) -> object:
    """Freeze canonical request values; opaque values disable cross-route reuse."""

    if isinstance(value, Enum):
        frozen_value = _freeze(value.value)
        if frozen_value is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("enum", type(value).__module__, type(value).__qualname__, frozen_value)
    scalar = _freeze_scalar(value)
    if scalar is not _CACHE_IDENTITY_UNSUPPORTED:
        return scalar
    if type(value) is dict:
        items = []
        for key, item in value.items():
            frozen_key = _freeze(key)
            frozen_item = _freeze(item)
            if (
                frozen_key is _CACHE_IDENTITY_UNSUPPORTED
                or frozen_item is _CACHE_IDENTITY_UNSUPPORTED
            ):
                return _CACHE_IDENTITY_UNSUPPORTED
            items.append((frozen_key, frozen_item))
        return ("dict", tuple(sorted(items, key=lambda pair: repr(pair[0]))))
    if isinstance(value, (tuple, list, set, frozenset)):
        if type(value) not in {tuple, list, set, frozenset}:
            return _CACHE_IDENTITY_UNSUPPORTED
        frozen_items = tuple(_freeze(item) for item in value)
        if any(item is _CACHE_IDENTITY_UNSUPPORTED for item in frozen_items):
            return _CACHE_IDENTITY_UNSUPPORTED
        if type(value) in {set, frozenset}:
            frozen_items = tuple(sorted(frozen_items, key=repr))
        return (type(value).__name__, frozen_items)
    if type(value) is FeatureConstraint:
        lower = _freeze(object.__getattribute__(value, "lower"))
        upper = _freeze(object.__getattribute__(value, "upper"))
        if lower is _CACHE_IDENTITY_UNSUPPORTED or upper is _CACHE_IDENTITY_UNSUPPORTED:
            return _CACHE_IDENTITY_UNSUPPORTED
        return ("feature_constraint", lower, upper)
    return _CACHE_IDENTITY_UNSUPPORTED


def _string_param(params: Mapping[str, object], name: str) -> str | None:
    value = params.get(name)
    return value if isinstance(value, str) else None
