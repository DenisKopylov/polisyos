"""
Slot Linker - Resolves and validates connections between Foundry methods.

All validation happens at link time (Python layer) before any JAX compilation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterator, Mapping, Sequence
from uuid import UUID

from polisyos.foundry.methods.base import MethodSignature, SlotSpec
from polisyos.foundry.methods.exceptions import (
    ShapeMismatchError,
    SlotConnectionError,
    UnitMismatchError,
)
from polisyos.foundry.methods.slot_schema import (
    SemanticCompatibilityError,
    is_semantically_compatible,
)
from polisyos.foundry.methods.types.checker import (
    IncompatibilityReason,
    ShapeAdapterKind,
    SlotCompatibility,
    TypeAdapterKind,
    UnitAdapterKind,
    check_slot_compatibility,
    find_compatible_slots,
)

# -----------------------------------------------------------------------------
# Result Types
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SlotBinding:
    """A validated binding from a source output slot to a target input slot."""

    source_method: str
    source_slot: str
    target_method: str
    target_slot: str
    compatibility: SlotCompatibility
    source_node_id: UUID | None = None
    target_node_id: UUID | None = None

    @property
    def requires_conversion(self) -> bool:
        return self.compatibility.requires_conversion

    @property
    def conversion_factor(self) -> float | None:
        return self.compatibility.conversion_factor

    @property
    def requires_fx_rate(self) -> bool:
        return self.compatibility.requires_fx_rate

    def __repr__(self) -> str:
        conv = ""
        if self.requires_fx_rate:
            conv = " [FX]"
        elif self.requires_conversion:
            factor = self.conversion_factor
            if factor is not None:
                conv = f" [x{factor:.4g}]"
        return (
            f"SlotBinding({self.source_method}:{self.source_slot} -> "
            f"{self.target_method}:{self.target_slot}{conv})"
        )

    def with_node_ids(self, source_id: UUID, target_id: UUID) -> SlotBinding:
        return replace(self, source_node_id=source_id, target_node_id=target_id)


@dataclass(frozen=True, slots=True)
class LinkResult:
    """Result of linking two methods together."""

    source_fqn: str
    target_fqn: str
    bindings: tuple[SlotBinding, ...]
    warnings: tuple[str, ...] = ()
    unconnected_inputs: tuple[str, ...] = ()
    source_id: UUID | None = None
    target_id: UUID | None = None

    @property
    def requires_conversions(self) -> bool:
        return any(b.requires_conversion for b in self.bindings)

    @property
    def conversion_count(self) -> int:
        return sum(1 for b in self.bindings if b.requires_conversion)

    @property
    def binding_count(self) -> int:
        return len(self.bindings)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def has_unconnected(self) -> bool:
        return len(self.unconnected_inputs) > 0

    def get_binding(self, target_slot: str) -> SlotBinding | None:
        for binding in self.bindings:
            if binding.target_slot == target_slot:
                return binding
        return None

    def iter_bindings(self) -> Iterator[SlotBinding]:
        return iter(self.bindings)

    def with_node_ids(self, source_id: UUID, target_id: UUID) -> LinkResult:
        if not self.bindings:
            return replace(self, source_id=source_id, target_id=target_id)
        updated = tuple(b.with_node_ids(source_id, target_id) for b in self.bindings)
        return replace(self, bindings=updated, source_id=source_id, target_id=target_id)

    def __repr__(self) -> str:
        return (
            f"LinkResult({self.source_fqn} -> {self.target_fqn}, "
            f"bindings={self.binding_count}, warnings={len(self.warnings)})"
        )


# -----------------------------------------------------------------------------
# Linker Configuration
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LinkerConfig:
    """Configuration options for the SlotLinker."""

    strict_shape: bool = False
    allow_partial_links: bool = True
    prefer_exact_names: bool = True
    warn_on_conversion: bool = True
    allow_unsafe_shapes: bool = False
    check_semantic_compatibility: bool = True
    """
    When True (default), the linker checks that source and target slots are
    semantically compatible according to ``SLOT_SCHEMA_REGISTRY``.  Slots
    not present in the registry are considered unconstrained (always allowed).
    Set to False to disable semantic checks (e.g. for legacy chains or when
    connecting slots with non-standard names).
    """

    @classmethod
    def strict(cls) -> LinkerConfig:
        return cls(strict_shape=True, allow_partial_links=False, check_semantic_compatibility=True)

    @classmethod
    def permissive(cls) -> LinkerConfig:
        return cls(strict_shape=False, allow_partial_links=True, check_semantic_compatibility=False)

    @classmethod
    def semantic_strict(cls) -> LinkerConfig:
        """Full semantic + shape strictness — use in production pipelines."""
        return cls(
            strict_shape=True,
            allow_partial_links=False,
            check_semantic_compatibility=True,
        )


# -----------------------------------------------------------------------------
# Main Linker Class
# -----------------------------------------------------------------------------


class SlotLinker:
    """Links slots between methods, validating compatibility before JAX."""

    def __init__(self, config: LinkerConfig | None = None):
        self._config = config or LinkerConfig()

    @property
    def config(self) -> LinkerConfig:
        return self._config

    def _check_semantic(self, src_name: str, tgt_name: str) -> None:
        """Raise SemanticCompatibilityError if slots are semantically incompatible."""
        if not self._config.check_semantic_compatibility:
            return
        if not is_semantically_compatible(src_name, tgt_name):
            raise SemanticCompatibilityError(src_name, tgt_name)

    def link(
        self,
        source_sig: MethodSignature,
        target_sig: MethodSignature,
        explicit_mapping: Mapping[str, str] | None = None,
    ) -> LinkResult:
        if explicit_mapping is not None:
            return self._link_explicit(source_sig, target_sig, explicit_mapping)
        return self._link_auto(source_sig, target_sig)

    def _link_explicit(
        self,
        source_sig: MethodSignature,
        target_sig: MethodSignature,
        mapping: Mapping[str, str],
    ) -> LinkResult:
        source_outputs = _slots_by_name(source_sig.output_slots)
        target_inputs = _slots_by_name(target_sig.input_slots)

        bindings: list[SlotBinding] = []
        warnings: list[str] = []
        connected_inputs: set[str] = set()

        for src_name, tgt_name in mapping.items():
            if src_name not in source_outputs:
                raise SlotConnectionError(
                    f"Source output slot '{src_name}' not found in "
                    f"{source_sig.fqn}. Available: {list(source_outputs.keys())}"
                )
            if tgt_name not in target_inputs:
                raise SlotConnectionError(
                    f"Target input slot '{tgt_name}' not found in "
                    f"{target_sig.fqn}. Available: {list(target_inputs.keys())}"
                )

            src_slot = source_outputs[src_name]
            tgt_slot = target_inputs[tgt_name]

            compat = check_slot_compatibility(
                src_slot,
                tgt_slot,
                strict_shape=self._config.strict_shape,
                allow_unsafe_shapes=self._config.allow_unsafe_shapes,
            )

            if not compat.compatible:
                if compat.reason == IncompatibilityReason.UNIT_DIMENSION_MISMATCH:
                    raise UnitMismatchError(
                        src_name,
                        tgt_name,
                        src_slot.unit.symbol,
                        tgt_slot.unit.symbol,
                    )
                if compat.reason == IncompatibilityReason.SHAPE_MISMATCH:
                    raise ShapeMismatchError(
                        src_name,
                        tgt_name,
                        src_slot.shape,
                        tgt_slot.shape,
                    )
                raise SlotConnectionError(
                    f"Cannot connect {src_name} -> {tgt_name}: "
                    f"{compat.warnings[0] if compat.warnings else 'incompatible'}"
                )

            # Semantic compatibility check (respects config.check_semantic_compatibility)
            self._check_semantic(src_name, tgt_name)

            binding = SlotBinding(
                source_method=source_sig.fqn,
                source_slot=src_name,
                target_method=target_sig.fqn,
                target_slot=tgt_name,
                compatibility=compat,
            )
            bindings.append(binding)
            connected_inputs.add(tgt_name)

            warnings.extend(_conversion_warnings(binding, src_slot, tgt_slot, self._config))
            warnings.extend(compat.warnings)

        unconnected = tuple(
            name for name in target_inputs.keys()
            if name not in connected_inputs
        )

        return LinkResult(
            source_fqn=source_sig.fqn,
            target_fqn=target_sig.fqn,
            bindings=tuple(bindings),
            warnings=tuple(warnings),
            unconnected_inputs=unconnected,
        )

    def _link_auto(
        self,
        source_sig: MethodSignature,
        target_sig: MethodSignature,
    ) -> LinkResult:
        source_outputs = _slots_by_name(source_sig.output_slots)
        target_inputs = _slots_by_name(target_sig.input_slots)

        bindings: list[SlotBinding] = []
        warnings: list[str] = []
        used_sources: set[str] = set()
        connected_inputs: set[str] = set()

        # Pass 1: exact name matching (if configured)
        if self._config.prefer_exact_names:
            for name, tgt_slot in target_inputs.items():
                if name not in source_outputs:
                    continue
                src_slot = source_outputs[name]
                compat = check_slot_compatibility(
                    src_slot,
                    tgt_slot,
                    strict_shape=self._config.strict_shape,
                    allow_unsafe_shapes=self._config.allow_unsafe_shapes,
                )
                if compat.compatible:
                    # Skip semantically incompatible same-named slots gracefully
                    if not is_semantically_compatible(name, name):
                        warnings.append(
                            f"Slot '{name}' skipped: semantic incompatibility "
                            f"(source and target have same name but different semantics)"
                        )
                        continue
                    binding = SlotBinding(
                        source_method=source_sig.fqn,
                        source_slot=name,
                        target_method=target_sig.fqn,
                        target_slot=name,
                        compatibility=compat,
                    )
                    bindings.append(binding)
                    used_sources.add(name)
                    connected_inputs.add(name)
                    warnings.extend(_conversion_warnings(binding, src_slot, tgt_slot, self._config))
                    warnings.extend(compat.warnings)
                else:
                    warnings.append(
                        f"Slot '{name}' exists in both but incompatible: "
                        f"{compat.warnings[0] if compat.warnings else 'type mismatch'}"
                    )

        # Pass 2: type-based matching for remaining inputs
        for tgt_name, tgt_slot in target_inputs.items():
            if tgt_name in connected_inputs:
                continue

            available_sources = [
                source_outputs[name] for name in source_outputs
                if name not in used_sources
            ]

            compatible = find_compatible_slots(
                available_sources,
                tgt_slot,
                strict_shape=self._config.strict_shape,
                allow_unsafe_shapes=self._config.allow_unsafe_shapes,
            )

            if not compatible:
                continue

            best, _best_score, best_candidates = _select_best_candidate(
                compatible,
                tgt_slot,
                prefer_exact_names=self._config.prefer_exact_names,
            )
            src_slot, compat = best

            binding = SlotBinding(
                source_method=source_sig.fqn,
                source_slot=src_slot.name,
                target_method=target_sig.fqn,
                target_slot=tgt_name,
                compatibility=compat,
            )
            bindings.append(binding)
            used_sources.add(src_slot.name)
            connected_inputs.add(tgt_name)

            warnings.append(f"Auto-linked: {src_slot.name} -> {tgt_name}")
            warnings.extend(_conversion_warnings(binding, src_slot, tgt_slot, self._config))
            warnings.extend(compat.warnings)

            if len(compatible) > 1:
                others = sorted(
                    [slot.name for slot, _ in compatible if slot.name != src_slot.name]
                )
                if others:
                    warnings.append(
                        f"Multiple compatible sources for '{tgt_name}': used '{src_slot.name}', "
                        f"also available: {others}"
                    )

        unconnected = tuple(
            name for name in target_inputs.keys()
            if name not in connected_inputs
        )

        if unconnected and not self._config.allow_partial_links:
            raise SlotConnectionError(
                f"Unconnected required inputs in {target_sig.fqn}: {list(unconnected)}. "
                f"Available outputs from {source_sig.fqn}: {list(source_outputs.keys())}"
            )

        for name in unconnected:
            warnings.append(f"Input slot '{name}' remains unconnected")

        return LinkResult(
            source_fqn=source_sig.fqn,
            target_fqn=target_sig.fqn,
            bindings=tuple(bindings),
            warnings=tuple(warnings),
            unconnected_inputs=unconnected,
        )

    def validate_chain(
        self,
        signatures: Sequence[MethodSignature],
        links: Sequence[LinkResult],
    ) -> list[str]:
        issues: list[str] = []
        all_connected: set[tuple[UUID | str, str]] = set()

        for link in links:
            for binding in link.bindings:
                key = (
                    binding.target_node_id if binding.target_node_id is not None else binding.target_method,
                    binding.target_slot,
                )
                if key in all_connected:
                    issues.append(
                        f"Slot {binding.target_slot} in {binding.target_method} "
                        "connected multiple times"
                    )
                all_connected.add(key)

        return issues


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def link_methods(
    source: MethodSignature,
    target: MethodSignature,
    mapping: Mapping[str, str] | None = None,
    *,
    strict_shape: bool = False,
    allow_unsafe_shapes: bool = False,
) -> LinkResult:
    config = LinkerConfig(
        strict_shape=strict_shape,
        allow_unsafe_shapes=allow_unsafe_shapes,
    )
    linker = SlotLinker(config)
    return linker.link(source, target, explicit_mapping=mapping)


def check_linkable(
    source: MethodSignature,
    target: MethodSignature,
) -> bool:
    try:
        result = link_methods(source, target)
        return result.binding_count > 0
    except SlotConnectionError:
        return False


# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------


def _slots_by_name(slots: Sequence[SlotSpec]) -> dict[str, SlotSpec]:
    return {slot.name: slot for slot in sorted(slots, key=lambda s: s.name)}


def _conversion_warnings(
    binding: SlotBinding,
    src_slot: SlotSpec,
    tgt_slot: SlotSpec,
    config: LinkerConfig,
) -> list[str]:
    if not config.warn_on_conversion or not binding.requires_conversion:
        return []
    if binding.requires_fx_rate:
        return [
            f"FX rate required: {src_slot.name}({src_slot.unit.symbol}) -> "
            f"{tgt_slot.name}({tgt_slot.unit.symbol})"
        ]
    factor = binding.conversion_factor
    if factor is None:
        return []
    return [
        f"Unit conversion: {src_slot.name}({src_slot.unit.symbol}) -> "
        f"{tgt_slot.name}({tgt_slot.unit.symbol}) factor={factor:.6g}"
    ]


def _select_best_candidate(
    candidates: list[tuple[SlotSpec, SlotCompatibility]],
    target_slot: SlotSpec,
    *,
    prefer_exact_names: bool,
) -> tuple[tuple[SlotSpec, SlotCompatibility], tuple[int, int, int, int, int], list[tuple[SlotSpec, SlotCompatibility]]]:
    best_score: tuple[int, int, int, int, int] | None = None
    best_candidates: list[tuple[SlotSpec, SlotCompatibility]] = []

    for src_slot, compat in candidates:
        score = _score_candidate(src_slot, target_slot, compat, prefer_exact_names=prefer_exact_names)
        if best_score is None or score > best_score:
            best_score = score
            best_candidates = [(src_slot, compat)]
        elif score == best_score:
            best_candidates.append((src_slot, compat))

    if best_score is None:
        return candidates[0], (0, 0, 0, 0, 0), candidates

    chosen = min(best_candidates, key=lambda item: item[0].name)
    return chosen, best_score, best_candidates


def _score_candidate(
    source_slot: SlotSpec,
    target_slot: SlotSpec,
    compat: SlotCompatibility,
    *,
    prefer_exact_names: bool,
) -> tuple[int, int, int, int, int]:
    name_score = 1 if prefer_exact_names and source_slot.name == target_slot.name else 0

    unit_kind = compat.adapter_plan.unit.kind
    if unit_kind == UnitAdapterKind.NONE:
        unit_score = 3 if source_slot.unit.symbol == target_slot.unit.symbol else 2
    elif unit_kind == UnitAdapterKind.LINEAR_SCALE:
        unit_score = 1
    else:
        unit_score = 0

    if source_slot.slot_type == target_slot.slot_type:
        type_score = 2
    elif compat.adapter_plan.slot_type.kind == TypeAdapterKind.VECTOR_TO_MATRIX:
        type_score = 0
    else:
        type_score = 1

    shape_kind = compat.adapter_plan.shape.kind
    if shape_kind == ShapeAdapterKind.IDENTITY:
        shape_score = 2
    elif shape_kind == ShapeAdapterKind.BROADCAST_TO:
        shape_score = 1
    elif shape_kind == ShapeAdapterKind.EXPAND_DIMS:
        shape_score = 0
    else:
        shape_score = -1

    warning_score = -len(compat.warnings)

    return (name_score, unit_score, type_score, shape_score, warning_score)
