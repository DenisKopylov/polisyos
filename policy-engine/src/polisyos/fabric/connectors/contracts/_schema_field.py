"""
Schema versioning and field specification.

Provides:
- SchemaVersion: semantic versioning for schemas with compatibility checks
- FieldSpec: Pydantic model for a single data field (column) specification
- FIELD_NAME_PATTERN: regex for valid snake_case field names
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.fabric.finite import ensure_probability, finite_or_none
from polisyos.ir.kernel.units import UnitRef

from ._schema_types import Additivity, SchemaType, SemanticType

__all__ = [
    "FIELD_NAME_PATTERN",
    "SCHEMA_ID_PATTERN",
    "FieldSpec",
    "SchemaVersion",
    "make_field_id",
    "make_schema_id",
    "normalize_schema_id_part",
    "normalize_unit_id",
]


# =============================================================================
# Version Management
# =============================================================================


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    """
    Semantic versioning for schemas.

    Version rules:
    - MAJOR: Breaking changes (field removal, type narrowing)
    - MINOR: Backward-compatible additions (new fields, type widening)
    - PATCH: Documentation, metadata changes
    """

    major: int
    minor: int
    patch: int = 0

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version components must be non-negative")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, version_str: str) -> SchemaVersion:
        """Parse version string like '1.2.3' or '1.2'."""
        match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?$", version_str)
        if not match:
            raise ValueError(f"Invalid version format: {version_str}")
        patch = int(match.group(3)) if match.group(3) is not None else 0
        return cls(int(match.group(1)), int(match.group(2)), patch)

    def is_compatible_with(self, other: SchemaVersion) -> bool:
        """
        Check backward compatibility (same major version).

        A schema at version 1.2.3 is compatible with 1.0.0 but not 2.0.0.
        """
        return self.major == other.major

    def bump_major(self) -> SchemaVersion:
        """Create new version with major bump."""
        return SchemaVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> SchemaVersion:
        """Create new version with minor bump."""
        return SchemaVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> SchemaVersion:
        """Create new version with patch bump."""
        return SchemaVersion(self.major, self.minor, self.patch + 1)


# =============================================================================
# Field Specification
# =============================================================================


# Pattern for valid field names (snake_case)
FIELD_NAME_PATTERN = r"^[a-z][a-z0-9_]*$"
SCHEMA_ID_PATTERN = (
    r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
    r"(?:\.[a-z][a-z0-9]*(?:_[a-z0-9]+)*)*$"
)


def _encode_identifier_char(char: str) -> str:
    return f"u{ord(char):04x}"


def _normalize_identifier_segment(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    if not value:
        return ""

    chars: list[str] = []
    for char in value:
        if char.isascii():
            if char.isalnum():
                chars.append(char)
            elif char in {"_", "-"} or char.isspace():
                chars.append("_")
            else:
                chars.append("_")
            continue
        if unicodedata.category(char)[:1] in {"L", "N"}:
            chars.append(_encode_identifier_char(char))
        else:
            chars.append("_")

    segment = re.sub(r"_+", "_", "".join(chars)).strip("_")
    if not segment:
        return ""
    if not segment[0].isalpha():
        segment = f"id_{segment}"
    return segment


def normalize_schema_id_part(value: object) -> str:
    """Normalize a source/provider token into one or more schema-id segments."""
    raw = unicodedata.normalize("NFKC", str(value)).strip()
    if not raw:
        return ""
    raw = re.sub(r"[\s/\\:]+", ".", raw)
    raw = re.sub(r"\.+", ".", raw)
    segments = [
        normalized
        for part in raw.split(".")
        if (normalized := _normalize_identifier_segment(part))
    ]
    return ".".join(segments)


def make_schema_id(*parts: object, fallback: str = "schema") -> str:
    """Build a stable Fabric schema id from connector/source tokens."""
    segments: list[str] = []
    for part in parts:
        normalized = normalize_schema_id_part(part)
        if normalized:
            segments.extend(normalized.split("."))
    candidate = ".".join(segments) or normalize_schema_id_part(fallback) or "schema"
    if re.fullmatch(SCHEMA_ID_PATTERN, candidate) is None:
        raise ValueError(f"Cannot build valid schema_id from parts: {parts!r}")
    return candidate


def make_field_id(schema_id: str, field_name: str) -> str:
    """Build a globally stable field id under a schema id."""
    return make_schema_id(schema_id, field_name)


def normalize_unit_id(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("/", "_per_")
    value = value.replace(" ", "_")
    value = re.sub(r"[^a-z0-9_.-]", "_", value)
    value = re.sub(r"_+", "_", value)
    return value


class FieldSpec(BaseModel):
    """
    Specification for a single data field (column).

    Captures both technical type information and semantic meaning,
    enabling:
    - Cross-platform type mapping
    - Validation rule generation
    - Unit-aware calculations
    - Documentation generation
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity
    name: str = Field(
        ...,
        pattern=FIELD_NAME_PATTERN,
        description="Field name in snake_case format",
    )
    field_id: str | None = Field(
        default=None,
        pattern=SCHEMA_ID_PATTERN,
        description=(
            "Stable semantic field identity. If omitted, the field name is the local identity."
        ),
    )

    # Type information
    data_type: SchemaType = Field(..., description="Canonical data type")
    element_type: SchemaType | None = Field(
        default=None,
        description="Element type for ARRAY fields",
    )

    # Units & semantics (integrates with ir/kernel/units.py)
    unit: UnitRef | None = Field(
        default=None,
        description="Unit reference (uses UnitRef identifiers)",
    )
    display_unit: str | None = Field(
        default=None,
        max_length=64,
        description="Optional display unit label (UI only)",
    )
    semantic_type: SemanticType | None = Field(
        default=None,
        description="Semantic meaning for validation and inference",
    )
    additivity: Additivity | None = Field(
        default=None,
        description="Additivity semantics for aggregation (additive/semi/non)",
    )

    # Constraints
    nullable: bool = Field(default=True, description="Whether NULL values are allowed")
    bounds: tuple[float | None, float | None] = Field(
        default=(None, None),
        description="Min/max bounds for numeric fields",
    )
    allowed_values: frozenset[str] | None = Field(
        default=None,
        description="Allowed values for CATEGORY fields",
    )
    pattern: str | None = Field(
        default=None,
        max_length=256,
        description="Regex pattern for STRING validation",
    )
    max_length: int | None = Field(
        default=None,
        ge=1,
        description="Maximum length for STRING/BINARY fields",
    )

    # Decimal precision (for DECIMAL type)
    precision: int | None = Field(default=None, ge=1, le=38)
    scale: int | None = Field(default=None, ge=0, le=38)

    # Documentation
    description: str = Field(default="", max_length=1024)
    source_name: str = Field(
        default="",
        max_length=256,
        description="Original name in source before normalization",
    )

    # Quality expectations
    expected_completeness: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Expected proportion of non-null values",
    )

    # Metadata
    tags: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("unit", mode="before")
    @classmethod
    def _coerce_unit(cls, v: UnitRef | str | None) -> UnitRef | None:
        if v is None or isinstance(v, UnitRef):
            return v
        if isinstance(v, Mapping):
            return UnitRef.model_validate(v)
        if isinstance(v, str):
            unit_id = normalize_unit_id(v)
            if not unit_id:
                return None
            return UnitRef(unit_id=unit_id)
        raise TypeError("unit must be UnitRef or str")

    @field_validator("field_id", mode="before")
    @classmethod
    def _coerce_field_id(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("bounds", mode="before")
    @classmethod
    def _coerce_bounds(cls, value: object) -> tuple[float | None, float | None]:
        if value is None:
            return (None, None)
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("bounds must contain exactly two values")
        min_val = finite_or_none(value[0], what="bounds min")
        max_val = finite_or_none(value[1], what="bounds max")
        return (min_val, max_val)

    @field_validator("expected_completeness", mode="after")
    @classmethod
    def _validate_expected_completeness(cls, value: float) -> float:
        return ensure_probability(value, what="expected_completeness")

    @model_validator(mode="after")
    def validate_element_type(self) -> FieldSpec:
        """Validate element_type is set for ARRAY fields."""
        if self.data_type == SchemaType.ARRAY and self.element_type is None:
            raise ValueError("element_type is required for ARRAY fields")
        if self.data_type != SchemaType.ARRAY and self.element_type is not None:
            raise ValueError("element_type should only be set for ARRAY fields")
        return self

    @model_validator(mode="after")
    def validate_decimal_precision(self) -> FieldSpec:
        """Validate decimal precision/scale."""
        if self.data_type != SchemaType.DECIMAL:
            return self

        precision = self.precision
        scale = self.scale

        if precision is None:
            precision = 18
            scale = 4 if scale is None else scale
        elif scale is None:
            scale = 0

        if scale is not None and precision is not None and scale > precision:
            raise ValueError("scale cannot exceed precision")

        if precision != self.precision:
            object.__setattr__(self, "precision", precision)
        if scale != self.scale:
            object.__setattr__(self, "scale", scale)

        return self

    @model_validator(mode="after")
    def validate_semantic_shape(self) -> FieldSpec:
        """Reject schema declarations whose technical type cannot carry the semantics."""
        if self.semantic_type is None:
            return self

        numeric_semantics = {
            SemanticType.CURRENCY,
            SemanticType.PERCENTAGE,
            SemanticType.RATIO,
            SemanticType.COUNT,
            SemanticType.RATE,
            SemanticType.INDEX,
            SemanticType.POPULATION,
            SemanticType.AREA,
            SemanticType.DISTANCE,
            SemanticType.WEIGHT,
            SemanticType.LATITUDE,
            SemanticType.LONGITUDE,
        }
        numeric_types = {
            SchemaType.INT8,
            SchemaType.INT16,
            SchemaType.INT32,
            SchemaType.INT64,
            SchemaType.UINT8,
            SchemaType.UINT16,
            SchemaType.UINT32,
            SchemaType.UINT64,
            SchemaType.FLOAT16,
            SchemaType.FLOAT32,
            SchemaType.FLOAT64,
            SchemaType.DECIMAL,
        }
        if self.semantic_type in numeric_semantics and self.data_type not in numeric_types:
            raise ValueError(
                f"semantic_type {self.semantic_type.value!r} requires a numeric data_type"
            )

        semantic_min, semantic_max = self.semantic_type.get_validation_bounds()
        field_min, field_max = self.bounds
        if semantic_min is not None and field_min is not None and field_min < semantic_min:
            raise ValueError(
                f"bounds min {field_min} is outside semantic bounds for "
                f"{self.semantic_type.value}: {semantic_min}"
            )
        if semantic_max is not None and field_max is not None and field_max > semantic_max:
            raise ValueError(
                f"bounds max {field_max} is outside semantic bounds for "
                f"{self.semantic_type.value}: {semantic_max}"
            )

        return self

    @field_validator("bounds", mode="after")
    @classmethod
    def validate_bounds(
        cls, v: tuple[float | None, float | None]
    ) -> tuple[float | None, float | None]:
        """Ensure min <= max."""
        min_val, max_val = v
        if min_val is not None and max_val is not None and min_val > max_val:
            raise ValueError(f"bounds min ({min_val}) must be <= max ({max_val})")
        return v

    def is_compatible_with(self, other: FieldSpec) -> bool:
        """
        Check if this field can be merged/compared with another.

        Compatibility rules:
        1. Semantic types must match (if both specified)
        2. Data types must be coercible
        3. Units must match if both specified
        """
        if self.semantic_type and other.semantic_type:
            if self.semantic_type != other.semantic_type:
                return False

        if self.additivity and other.additivity and self.additivity != other.additivity:
            return False

        if self.unit and other.unit and self.unit.unit_id != other.unit.unit_id:
            return False

        if not self.data_type.is_compatible_with(other.data_type):
            if not other.data_type.is_compatible_with(self.data_type):
                return False

        return True

    @property
    def stable_id(self) -> str:
        """Return the field identity used for evolution matching."""
        return self.field_id or self.name

    def widen_to(self, other: FieldSpec) -> FieldSpec:
        """
        Create a widened field spec that accommodates both fields.

        Used in schema evolution to create compatible merged schemas.
        """
        if self.unit and other.unit and self.unit.unit_id != other.unit.unit_id:
            raise ValueError(
                f"Cannot widen fields with conflicting units: {self.unit} vs {other.unit}"
            )

        if self.semantic_type and other.semantic_type:
            if self.semantic_type != other.semantic_type:
                raise ValueError(
                    "Cannot widen fields with conflicting semantic types: "
                    f"{self.semantic_type} vs {other.semantic_type}"
                )

        if self.additivity and other.additivity and self.additivity != other.additivity:
            raise ValueError(
                "Cannot widen fields with conflicting additivity: "
                f"{self.additivity} vs {other.additivity}"
            )

        if self.data_type.is_compatible_with(other.data_type):
            widened_type = other.data_type
        elif other.data_type.is_compatible_with(self.data_type):
            widened_type = self.data_type
        else:
            raise ValueError(f"Cannot widen {self.data_type} and {other.data_type}")

        min_bound = None
        max_bound = None
        if self.bounds[0] is not None or other.bounds[0] is not None:
            vals = [v for v in [self.bounds[0], other.bounds[0]] if v is not None]
            min_bound = min(vals) if vals else None
        if self.bounds[1] is not None or other.bounds[1] is not None:
            vals = [v for v in [self.bounds[1], other.bounds[1]] if v is not None]
            max_bound = max(vals) if vals else None

        merged_allowed = None
        if self.allowed_values is not None and other.allowed_values is not None:
            merged_allowed = self.allowed_values | other.allowed_values

        return FieldSpec(
            name=self.name,
            data_type=widened_type,
            element_type=self.element_type or other.element_type,
            unit=self.unit or other.unit,
            display_unit=self.display_unit or other.display_unit,
            semantic_type=self.semantic_type or other.semantic_type,
            additivity=self.additivity or other.additivity,
            nullable=self.nullable or other.nullable,
            bounds=(min_bound, max_bound),
            allowed_values=merged_allowed,
            pattern=self.pattern if self.pattern == other.pattern else None,
            max_length=self.max_length if self.max_length == other.max_length else None,
            precision=self.precision if self.precision == other.precision else None,
            scale=self.scale if self.scale == other.scale else None,
            description=self.description or other.description,
            source_name=self.source_name or other.source_name,
            expected_completeness=min(self.expected_completeness, other.expected_completeness),
            tags=self.tags | other.tags,
        )

    def to_duckdb_column_def(self) -> str:
        """Generate DuckDB column definition."""
        type_str = self.data_type.to_duckdb_type()

        if self.data_type == SchemaType.DECIMAL and self.precision:
            type_str = f"DECIMAL({self.precision},{self.scale or 0})"

        if self.data_type == SchemaType.ARRAY and self.element_type:
            type_str = f"{self.element_type.to_duckdb_type()}[]"

        null_str = "" if self.nullable else " NOT NULL"
        return f"{self.name} {type_str}{null_str}"
