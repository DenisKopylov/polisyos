"""
Static type checker for method slots (runs BEFORE JAX compilation).

This module implements Law F: all slot compatibility checks happen in Python,
operating on SlotSpec metadata only. No JAX arrays or compilation involved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Sequence

from polisyos.foundry.methods.base import DimVar, SlotSpec, SlotType, Unit

# -----------------------------------------------------------------------------
# Result Types
# -----------------------------------------------------------------------------


class IncompatibilityReason(Enum):
    """Categorizes why slots are incompatible."""

    CONTRACT_MISMATCH = auto()
    UNIT_DIMENSION_MISMATCH = auto()
    SLOT_TYPE_INCOMPATIBLE = auto()
    SHAPE_MISMATCH = auto()


class UnitAdapterKind(Enum):
    """Unit adapter requirements."""

    NONE = auto()
    LINEAR_SCALE = auto()
    FX_RATE = auto()


@dataclass(frozen=True, slots=True)
class UnitAdapter:
    """Plan for unit conversion between slots."""

    kind: UnitAdapterKind
    factor: float | None = None
    source_symbol: str | None = None
    target_symbol: str | None = None

    @classmethod
    def none(cls) -> UnitAdapter:
        return cls(kind=UnitAdapterKind.NONE, factor=1.0)

    @classmethod
    def linear_scale(cls, factor: float, source: Unit, target: Unit) -> UnitAdapter:
        return cls(
            kind=UnitAdapterKind.LINEAR_SCALE,
            factor=factor,
            source_symbol=source.symbol,
            target_symbol=target.symbol,
        )

    @classmethod
    def fx_rate(cls, source: Unit, target: Unit) -> UnitAdapter:
        return cls(
            kind=UnitAdapterKind.FX_RATE,
            factor=None,
            source_symbol=source.symbol,
            target_symbol=target.symbol,
        )

    @property
    def is_identity(self) -> bool:
        return self.kind == UnitAdapterKind.NONE

    @property
    def requires_conversion(self) -> bool:
        return self.kind != UnitAdapterKind.NONE

    @property
    def requires_fx_rate(self) -> bool:
        return self.kind == UnitAdapterKind.FX_RATE


class ShapeAdapterKind(Enum):
    """Shape adapter requirements."""

    IDENTITY = auto()
    BROADCAST_TO = auto()
    EXPAND_DIMS = auto()
    UNSAFE_RESHAPE = auto()


@dataclass(frozen=True, slots=True)
class ShapeAdapter:
    """Plan for adapting shapes between slots."""

    kind: ShapeAdapterKind
    target_shape: tuple[int | str, ...] | None = None
    axis: int | None = None
    reason: str = ""

    @classmethod
    def identity(cls) -> ShapeAdapter:
        return cls(kind=ShapeAdapterKind.IDENTITY)

    @classmethod
    def broadcast_to(cls, target_shape: tuple[int | str, ...]) -> ShapeAdapter:
        return cls(kind=ShapeAdapterKind.BROADCAST_TO, target_shape=target_shape)

    @classmethod
    def expand_dims(cls, axis: int, target_shape: tuple[int | str, ...]) -> ShapeAdapter:
        return cls(kind=ShapeAdapterKind.EXPAND_DIMS, axis=axis, target_shape=target_shape)

    @classmethod
    def unsafe_reshape(cls, target_shape: tuple[int | str, ...], reason: str) -> ShapeAdapter:
        return cls(kind=ShapeAdapterKind.UNSAFE_RESHAPE, target_shape=target_shape, reason=reason)

    @property
    def is_identity(self) -> bool:
        return self.kind == ShapeAdapterKind.IDENTITY


class TypeAdapterKind(Enum):
    """SlotType adapter requirements."""

    NONE = auto()
    VECTOR_TO_MATRIX = auto()


@dataclass(frozen=True, slots=True)
class TypeAdapter:
    """Plan for adapting slot types."""

    kind: TypeAdapterKind
    orientation: str | None = None

    @classmethod
    def none(cls) -> TypeAdapter:
        return cls(kind=TypeAdapterKind.NONE)

    @classmethod
    def vector_to_matrix(cls, orientation: str | None) -> TypeAdapter:
        return cls(kind=TypeAdapterKind.VECTOR_TO_MATRIX, orientation=orientation)

    @property
    def is_identity(self) -> bool:
        return self.kind == TypeAdapterKind.NONE


@dataclass(frozen=True, slots=True)
class AdapterPlan:
    """Structured plan describing required adapters."""

    unit: UnitAdapter = field(default_factory=UnitAdapter.none)
    shape: ShapeAdapter = field(default_factory=ShapeAdapter.identity)
    slot_type: TypeAdapter = field(default_factory=TypeAdapter.none)

    def as_tuple(self) -> tuple[UnitAdapter | ShapeAdapter | TypeAdapter, ...]:
        adapters: list[UnitAdapter | ShapeAdapter | TypeAdapter] = []
        if not self.unit.is_identity:
            adapters.append(self.unit)
        if not self.shape.is_identity:
            adapters.append(self.shape)
        if not self.slot_type.is_identity:
            adapters.append(self.slot_type)
        return tuple(adapters)


@dataclass(frozen=True, slots=True)
class SlotCompatibility:
    """
    Result of a slot compatibility check.

    Attributes:
        compatible: True if slots can be connected
        source_slot: The source (output) slot specification
        target_slot: The target (input) slot specification
        adapter_plan: Structured plan of adapters required at runtime
        warnings: Tuple of warning messages for potential issues
        reason: If incompatible, the categorized reason
    """

    compatible: bool
    source_slot: SlotSpec
    target_slot: SlotSpec
    adapter_plan: AdapterPlan = field(default_factory=AdapterPlan)
    warnings: tuple[str, ...] = ()
    reason: IncompatibilityReason | None = None

    def __post_init__(self) -> None:
        if not self.compatible and self.reason is None:
            raise ValueError("Incompatible results must specify a reason")
        if self.compatible and self.reason is not None:
            raise ValueError("Compatible results must not have a reason")

    @property
    def adapters(self) -> tuple[UnitAdapter | ShapeAdapter | TypeAdapter, ...]:
        """Return non-identity adapters as a flat tuple."""
        return self.adapter_plan.as_tuple()

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings were generated."""
        return len(self.warnings) > 0

    @property
    def requires_conversion(self) -> bool:
        """Check if unit conversion is required."""
        return self.adapter_plan.unit.requires_conversion

    @property
    def conversion_factor(self) -> float | None:
        """Return linear conversion factor (None if FX or incompatible)."""
        unit_adapter = self.adapter_plan.unit
        if unit_adapter.kind == UnitAdapterKind.LINEAR_SCALE:
            return unit_adapter.factor
        if unit_adapter.kind == UnitAdapterKind.NONE:
            return 1.0
        return None

    @property
    def requires_fx_rate(self) -> bool:
        """Check if FX rate is required for currency conversion."""
        return self.adapter_plan.unit.requires_fx_rate


# -----------------------------------------------------------------------------
# Main Compatibility Function
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShapeCheckResult:
    """Result of shape compatibility analysis."""

    compatible: bool
    adapter: ShapeAdapter
    warnings: tuple[str, ...] = ()
    reason: str = ""
    type_adapter: TypeAdapter | None = None


@dataclass(frozen=True, slots=True)
class TypeCheckResult:
    """Result of SlotType compatibility analysis."""

    compatible: bool
    adapter: TypeAdapter
    reason: IncompatibilityReason | None = None


def check_slot_compatibility(
    source: SlotSpec,
    target: SlotSpec,
    *,
    strict_shape: bool = False,
    allow_unsafe_shapes: bool = False,
) -> SlotCompatibility:
    """
    Check if a source output slot can connect to a target input slot.

    Checks are performed in order of severity:

    1. Unit dimensions (hard fail)
    2. Unit conversion requirements (adapter plan)
    3. SlotType compatibility (hard fail)
    4. Shape compatibility (directional broadcasting)
    5. Bounds overlap (warnings)

    Args:
        source: Output slot from the upstream method
        target: Input slot of the downstream method
        strict_shape: Require exact shape match (no broadcasting/reshape)
        allow_unsafe_shapes: Allow non-broadcastable shapes with UNSAFE_RESHAPE adapter
    """
    warnings: list[str] = []

    # -------------------------------------------------------------------------
    # Step 0: Explicit contract compatibility
    # -------------------------------------------------------------------------
    if (
        source.contract_id is not None
        and target.contract_id is not None
        and source.contract_id != target.contract_id
    ):
        return SlotCompatibility(
            compatible=False,
            source_slot=source,
            target_slot=target,
            reason=IncompatibilityReason.CONTRACT_MISMATCH,
            warnings=(
                f"Contract mismatch: {source.contract_id!r} -> {target.contract_id!r}",
            ),
        )

    # -------------------------------------------------------------------------
    # Step 1: Unit Dimension Check (Hard Fail)
    # -------------------------------------------------------------------------
    if not source.unit.is_compatible(target.unit):
        return SlotCompatibility(
            compatible=False,
            source_slot=source,
            target_slot=target,
            reason=IncompatibilityReason.UNIT_DIMENSION_MISMATCH,
            warnings=(
                "Unit dimension mismatch: "
                f"{source.unit.dimension!r} ({source.unit.symbol}) "
                f"-> {target.unit.dimension!r} ({target.unit.symbol})",
            ),
        )

    # -------------------------------------------------------------------------
    # Step 2: Unit Conversion / FX Detection
    # -------------------------------------------------------------------------
    unit_adapter = UnitAdapter.none()
    if source.unit.dimension == "currency" and source.unit.symbol != target.unit.symbol:
        unit_adapter = UnitAdapter.fx_rate(source.unit, target.unit)
    else:
        if not _scales_equal(source.unit.scale, target.unit.scale):
            factor = source.unit.scale / target.unit.scale
            unit_adapter = UnitAdapter.linear_scale(factor, source.unit, target.unit)

    # -------------------------------------------------------------------------
    # Step 3: SlotType Compatibility Check (Hard Fail)
    # -------------------------------------------------------------------------
    type_check = _check_slot_type_compatibility(source.slot_type, target.slot_type)
    if not type_check.compatible:
        return SlotCompatibility(
            compatible=False,
            source_slot=source,
            target_slot=target,
            reason=IncompatibilityReason.SLOT_TYPE_INCOMPATIBLE,
            warnings=(
                f"SlotType incompatible: {source.slot_type.name} -> {target.slot_type.name}",
            ),
        )

    # -------------------------------------------------------------------------
    # Step 4: Shape Compatibility Check (Directional)
    # -------------------------------------------------------------------------
    shape_result = _check_shape_compatibility(
        source,
        target,
        strict_shape=strict_shape,
        allow_unsafe_shapes=allow_unsafe_shapes,
        type_adapter=type_check.adapter,
    )
    if not shape_result.compatible:
        return SlotCompatibility(
            compatible=False,
            source_slot=source,
            target_slot=target,
            adapter_plan=AdapterPlan(unit=unit_adapter, slot_type=type_check.adapter),
            reason=IncompatibilityReason.SHAPE_MISMATCH,
            warnings=(
                shape_result.reason
                if shape_result.reason
                else f"Shape mismatch: {source.shape} -> {target.shape}",
            ),
        )

    warnings.extend(shape_result.warnings)

    # -------------------------------------------------------------------------
    # Step 5: Bounds Overlap Check (Warning Only)
    # -------------------------------------------------------------------------
    bounds_result = _check_bounds_overlap(source.bounds, target.bounds)
    if not bounds_result.has_overlap or bounds_result.partial_overlap:
        warnings.append(bounds_result.message)

    # -------------------------------------------------------------------------
    # Success
    # -------------------------------------------------------------------------
    resolved_type_adapter = shape_result.type_adapter or type_check.adapter

    return SlotCompatibility(
        compatible=True,
        source_slot=source,
        target_slot=target,
        adapter_plan=AdapterPlan(
            unit=unit_adapter,
            shape=shape_result.adapter,
            slot_type=resolved_type_adapter,
        ),
        warnings=tuple(warnings),
    )


# -----------------------------------------------------------------------------
# SlotType Compatibility Rules
# -----------------------------------------------------------------------------


def _check_slot_type_compatibility(source: SlotType, target: SlotType) -> TypeCheckResult:
    """
    Check if source SlotType can be coerced to target SlotType.

    Coercion Rules:
    1. SCALAR -> Anything
    2. Same -> Same
    3. Anything -> TENSOR
    4. VECTOR -> MATRIX (via expand dims)
    """
    if source == SlotType.SCALAR:
        return TypeCheckResult(compatible=True, adapter=TypeAdapter.none())
    if source == target:
        return TypeCheckResult(compatible=True, adapter=TypeAdapter.none())
    if target == SlotType.TENSOR:
        return TypeCheckResult(compatible=True, adapter=TypeAdapter.none())
    if source == SlotType.VECTOR and target == SlotType.MATRIX:
        return TypeCheckResult(compatible=True, adapter=TypeAdapter.vector_to_matrix(None))
    return TypeCheckResult(
        compatible=False,
        adapter=TypeAdapter.none(),
        reason=IncompatibilityReason.SLOT_TYPE_INCOMPATIBLE,
    )


# -----------------------------------------------------------------------------
# Shape Compatibility
# -----------------------------------------------------------------------------


def _check_shape_compatibility(
    source: SlotSpec,
    target: SlotSpec,
    *,
    strict_shape: bool,
    allow_unsafe_shapes: bool,
    type_adapter: TypeAdapter,
) -> ShapeCheckResult:
    if strict_shape:
        if source.shape != target.shape:
            return ShapeCheckResult(
                compatible=False,
                adapter=ShapeAdapter.identity(),
                reason=f"Strict shape mismatch: {source.shape} -> {target.shape}",
            )
        return ShapeCheckResult(compatible=True, adapter=ShapeAdapter.identity())

    # Special-case vector -> matrix: requires expand dims, not broadcast
    if type_adapter.kind == TypeAdapterKind.VECTOR_TO_MATRIX:
        vector_result = _vector_to_matrix_shape(source.shape, target.shape)
        if not vector_result.compatible:
            return ShapeCheckResult(
                compatible=False,
                adapter=ShapeAdapter.identity(),
                reason=vector_result.reason or f"Shape mismatch: {source.shape} -> {target.shape}",
            )
        return ShapeCheckResult(
            compatible=True,
            adapter=vector_result.adapter,
            warnings=vector_result.warnings,
        )

    broadcast = _check_shapes_broadcast_to(source.shape, target.shape)
    if not broadcast.can_broadcast:
        if allow_unsafe_shapes:
            return ShapeCheckResult(
                compatible=True,
                adapter=ShapeAdapter.unsafe_reshape(target.shape, broadcast.reason),
                warnings=(broadcast.reason,),
            )
        return ShapeCheckResult(
            compatible=False,
            adapter=ShapeAdapter.identity(),
            reason=broadcast.reason or f"Shape mismatch: {source.shape} -> {target.shape}",
        )

    adapter = ShapeAdapter.identity()
    if broadcast.requires_broadcast:
        adapter = ShapeAdapter.broadcast_to(target.shape)

    return ShapeCheckResult(
        compatible=True,
        adapter=adapter,
        warnings=broadcast.warnings,
    )


def _vector_to_matrix_shape(
    source_shape: tuple[int | str, ...],
    target_shape: tuple[int | str, ...],
) -> ShapeCheckResult:
    if len(source_shape) != 1 or len(target_shape) != 2:
        return ShapeCheckResult(
            compatible=False,
            adapter=ShapeAdapter.identity(),
            reason=f"Vector-to-matrix requires shapes (N,) -> (N,1) or (1,N), got {source_shape} -> {target_shape}",
        )

    src_dim = source_shape[0]
    tgt_dim0, tgt_dim1 = target_shape

    # Column vector: (N,) -> (N, 1)
    col_warnings: list[str] = []
    if _dims_match(src_dim, tgt_dim0, col_warnings, axis=-2) and _is_one_dim(tgt_dim1):
        return ShapeCheckResult(
            compatible=True,
            adapter=ShapeAdapter.expand_dims(axis=1, target_shape=target_shape),
            warnings=tuple(col_warnings),
            type_adapter=TypeAdapter.vector_to_matrix("col"),
        )

    # Row vector: (N,) -> (1, N)
    row_warnings: list[str] = []
    if _is_one_dim(tgt_dim0) and _dims_match(src_dim, tgt_dim1, row_warnings, axis=-1):
        return ShapeCheckResult(
            compatible=True,
            adapter=ShapeAdapter.expand_dims(axis=0, target_shape=target_shape),
            warnings=tuple(row_warnings),
            type_adapter=TypeAdapter.vector_to_matrix("row"),
        )

    return ShapeCheckResult(
        compatible=False,
        adapter=ShapeAdapter.identity(),
        reason=f"Vector-to-matrix requires singleton dimension, got {source_shape} -> {target_shape}",
    )


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    """Result of directional broadcast check."""

    can_broadcast: bool
    requires_broadcast: bool = False
    warnings: tuple[str, ...] = ()
    reason: str = ""


def _dim_name(d: object) -> str:
    """Return a display name for any DimExpr."""
    if d is None:
        return "*"
    if isinstance(d, DimVar):
        return f"${d.name}"
    return repr(d)


def _dims_are_same_symbolic(a: object, b: object) -> bool:
    """True if both are symbolic and refer to the same name."""
    if isinstance(a, DimVar) and isinstance(b, DimVar):
        return a.name == b.name
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, DimVar) and isinstance(b, str):
        return a.name == b
    if isinstance(a, str) and isinstance(b, DimVar):
        return a == b.name
    return False


def _is_symbolic(d: object) -> bool:
    """True if dimension is symbolic (DimVar, str, or None wildcard)."""
    return d is None or isinstance(d, (DimVar, str))


def _check_shapes_broadcast_to(
    source_shape: tuple,
    target_shape: tuple,
) -> BroadcastResult:
    """
    Check if source shape can broadcast to target shape (directional).

    Rules (NumPy broadcast_to style):
    - source.ndim must be <= target.ndim
    - Align from the right
    - Each dimension must be equal or source dimension == 1

    Handles int, str, DimVar, and None (wildcard) dimension types.
    DimVar rules:
    - DimVar × DimVar with same name → compatible
    - DimVar × DimVar with different names → warning (may mismatch at runtime)
    - DimVar × int → compatible (symbolic satisfied by concrete)
    - int × DimVar → warning unless int == 1
    - None (wildcard) × anything → compatible, no warning
    """
    warnings: list[str] = []

    if len(source_shape) > len(target_shape):
        return BroadcastResult(
            can_broadcast=False,
            reason="Source has more dimensions than target",
        )

    requires_broadcast = False
    max_dims = len(target_shape)

    for i in range(max_dims):
        tgt_dim = target_shape[-1 - i]
        src_missing = i >= len(source_shape)
        src_dim = 1 if src_missing else source_shape[-1 - i]

        if src_missing:
            requires_broadcast = True
            continue

        # Either side is None (wildcard) → always compatible
        if src_dim is None or tgt_dim is None:
            continue

        # Both concrete integers
        if isinstance(src_dim, int) and isinstance(tgt_dim, int):
            if src_dim == tgt_dim:
                continue
            if src_dim == 1:
                requires_broadcast = True
                continue
            return BroadcastResult(
                can_broadcast=False,
                reason=(
                    f"Dimension mismatch at axis -{i + 1}: {src_dim} -> {tgt_dim} "
                    "(source not 1)"
                ),
            )

        # Both symbolic (DimVar or str)
        if _is_symbolic(src_dim) and _is_symbolic(tgt_dim):
            if not _dims_are_same_symbolic(src_dim, tgt_dim):
                warnings.append(
                    f"Symbolic dimension mismatch at axis -{i + 1}: "
                    f"{_dim_name(src_dim)} vs {_dim_name(tgt_dim)}"
                )
            continue

        # Symbolic source vs concrete target
        if _is_symbolic(src_dim) and isinstance(tgt_dim, int):
            warnings.append(
                f"Symbolic source dimension vs fixed target at axis -{i + 1}: "
                f"{_dim_name(src_dim)} vs {tgt_dim}"
            )
            continue

        # Concrete source vs symbolic target
        if isinstance(src_dim, int) and _is_symbolic(tgt_dim):
            if src_dim != 1:
                warnings.append(
                    f"Fixed source dimension vs symbolic target at axis -{i + 1}: "
                    f"{src_dim} vs {_dim_name(tgt_dim)}"
                )
            else:
                requires_broadcast = True
            continue

    return BroadcastResult(
        can_broadcast=True,
        requires_broadcast=requires_broadcast,
        warnings=tuple(warnings),
    )


def _dims_match(
    src_dim: object,
    tgt_dim: object,
    warnings: list[str],
    *,
    axis: int,
) -> bool:
    # Wildcard (None) matches anything
    if src_dim is None or tgt_dim is None:
        return True
    # Both concrete ints
    if isinstance(src_dim, int) and isinstance(tgt_dim, int):
        return src_dim == tgt_dim
    # Both symbolic (DimVar or str)
    if _is_symbolic(src_dim) and _is_symbolic(tgt_dim):
        if not _dims_are_same_symbolic(src_dim, tgt_dim):
            warnings.append(
                f"Symbolic dimension mismatch at axis {axis}: "
                f"{_dim_name(src_dim)} vs {_dim_name(tgt_dim)}"
            )
        return True
    # Mixed symbolic / concrete
    warnings.append(
        f"Symbolic dimension vs fixed size at axis {axis}: "
        f"{_dim_name(src_dim)} vs {_dim_name(tgt_dim)}"
    )
    return True


def _is_one_dim(dim: object) -> bool:
    return isinstance(dim, int) and dim == 1


# -----------------------------------------------------------------------------
# Bounds Overlap
# -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BoundsResult:
    """Result of bounds overlap analysis."""

    has_overlap: bool
    partial_overlap: bool = False
    message: str = ""


def _check_bounds_overlap(
    source_bounds: tuple[float | int | None, float | int | None],
    target_bounds: tuple[float | int | None, float | int | None],
) -> BoundsResult:
    src_min, src_max = source_bounds
    tgt_min, tgt_max = target_bounds

    if src_min is not None and tgt_max is not None:
        if src_min > tgt_max:
            return BoundsResult(
                has_overlap=False,
                message=f"No bounds overlap: source min ({src_min}) > target max ({tgt_max})",
            )

    if src_max is not None and tgt_min is not None:
        if src_max < tgt_min:
            return BoundsResult(
                has_overlap=False,
                message=f"No bounds overlap: source max ({src_max}) < target min ({tgt_min})",
            )

    min_contained = (
        tgt_min is None
        or src_min is None
        or src_min >= tgt_min
    )
    max_contained = (
        tgt_max is None
        or src_max is None
        or src_max <= tgt_max
    )

    if min_contained and max_contained:
        return BoundsResult(has_overlap=True)

    return BoundsResult(
        has_overlap=True,
        partial_overlap=True,
        message=f"Partial bounds overlap: source {source_bounds} may exceed target {target_bounds}",
    )


def _bounds_overlap(a: tuple, b: tuple) -> bool:
    """Simplified bounds check returning bool only."""
    return _check_bounds_overlap(a, b).has_overlap


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def _scales_equal(a: float, b: float, rel_tol: float = 1e-9) -> bool:
    """Check if two scale factors are effectively equal."""
    if a == b:
        return True
    return abs(a - b) <= rel_tol * max(abs(a), abs(b))


# -----------------------------------------------------------------------------
# Batch Compatibility Checking
# -----------------------------------------------------------------------------


def check_multiple_compatibility(
    pairs: Sequence[tuple[SlotSpec, SlotSpec]],
    *,
    strict_shape: bool = False,
    allow_unsafe_shapes: bool = False,
) -> list[SlotCompatibility]:
    """Check compatibility for multiple slot pairs."""
    return [
        check_slot_compatibility(
            src,
            tgt,
            strict_shape=strict_shape,
            allow_unsafe_shapes=allow_unsafe_shapes,
        )
        for src, tgt in pairs
    ]


def find_compatible_slots(
    source_slots: Sequence[SlotSpec],
    target_slot: SlotSpec,
    *,
    strict_shape: bool = False,
    allow_unsafe_shapes: bool = False,
) -> list[tuple[SlotSpec, SlotCompatibility]]:
    """Find all source slots compatible with a target slot."""
    results = []
    for source in source_slots:
        compat = check_slot_compatibility(
            source,
            target_slot,
            strict_shape=strict_shape,
            allow_unsafe_shapes=allow_unsafe_shapes,
        )
        if compat.compatible:
            results.append((source, compat))
    return results
