"""Validate declared method patch targets against the selected model registries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.types.checker import validate_registered_method_input
from polisyos.ir.kernel.merge_rules import MergeRuleKind
from polisyos.ir.kernel.slots import SlotKind, SlotScope, SlotValueType

if TYPE_CHECKING:
    from polisyos.core.registry.loader import RegistryBundleContent


def validate_method_patch_targets(
    signature: MethodSignature,
    *,
    params: Mapping[str, Any],
    declared_outputs: Sequence[str],
    registry: RegistryBundleContent,
    input_slot_sources: Mapping[str, str] | None = None,
) -> Mapping[str, str]:
    """Resolve the finite additive-flow patch contract before invoking a method.

    The caller must supply the canonical, selected registry bundle rather than
    a caller-asserted slot inventory. No target identity is inferred from a
    method name, slot spelling or unit identifier. The returned immutable map
    additionally constrains the emitted patch records to delta-only additions.

    Empty declarations preserve the legacy method path. Nonempty declarations
    require exact declared outputs and enforce the supported scalar monetary
    flow-to-stock profile. They establish structural compatibility, not the
    empirical validity of the selected model's accumulation law.

    Args:
        signature: Executable method's typed ABI.
        params: Actual invocation parameters, including static target names.
        declared_outputs: State slots the selected graph authorizes writing.
        registry: Materialized canonical registry bundle for the model.
        input_slot_sources: Complete local ABI input to registered source map.
            None preserves the legacy identity join. An explicit map never
            falls back to local names for missing or invalid entries.

    Returns:
        Immutable mapping from exact state target to required operation.

    Raises:
        ValueError: A source, target, unit, rule or declaration is incompatible.
    """
    if not signature.patch_targets:
        return MappingProxyType({})
    if input_slot_sources is not None and (
        set(input_slot_sources) != signature.input_slot_names
        or any(
            not isinstance(source_id, str) or not source_id or source_id.strip() != source_id
            for source_id in input_slot_sources.values()
        )
    ):
        raise ValueError("method_patch_input_slot_sources_mismatch")
    if len(declared_outputs) != len(set(declared_outputs)):
        raise ValueError("method_patch_declared_outputs_not_unique")
    operations: dict[str, str] = {}
    for contract in signature.patch_targets:
        target_id = params.get(contract.target_parameter)
        if not isinstance(target_id, str) or not target_id or target_id.strip() != target_id:
            raise ValueError("method_patch_target_parameter_unbound")
        if target_id in operations:
            raise ValueError("method_patch_targets_not_unique")
        target = registry.slot_registry.slots.get(target_id)
        if target is None:
            raise ValueError("method_patch_target_unregistered")
        source = validate_registered_method_input(
            signature,
            input_slot_id=contract.source_input,
            registered_slot_id=(
                contract.source_input
                if input_slot_sources is None
                else input_slot_sources[contract.source_input]
            ),
            registry=registry,
        )
        if (
            target.kind is not SlotKind.STOCK
            or target.scope is not SlotScope.GLOBAL
            or target.value_type is not SlotValueType.DECIMAL
            or not target.state_path
            or target.shape not in (None, [])
        ):
            raise ValueError("method_patch_target_profile_mismatch")
        if source.kind is not SlotKind.FLOW:
            raise ValueError("method_patch_source_profile_mismatch")
        rule = registry.merge_registry.rules.get(target.merge_rule.rule_id)
        if rule is None or rule.kind is not MergeRuleKind.SUM:
            raise ValueError("method_patch_target_merge_rule_mismatch")
        if source.unit is None or target.unit != source.unit:
            raise ValueError("method_patch_source_target_unit_mismatch")
        operations[target_id] = contract.operation
    if set(declared_outputs) != set(operations):
        raise ValueError("method_patch_declared_outputs_mismatch")
    return MappingProxyType(operations)
