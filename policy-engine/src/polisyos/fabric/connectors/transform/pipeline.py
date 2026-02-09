"""
DAG-based data transformation pipeline with lineage tracking.

This module implements a composable, compiler-style transformation engine
inspired by fabric/udf/passes, but operating on DataFrames instead of queries.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Sequence

import pandas as pd

from polisyos.core.pipeline import (
    DagPipeline as CoreDagPipeline,
    PipelineCycleError,
    UnknownStageError,
)
from polisyos.fabric.connectors.contracts.schema import DataSchema

__all__ = [
    "TransformError",
    "CopyPolicy",
    "TransformContext",
    "TransformLineage",
    "TransformResult",
    "DataTransform",
    "TransformStage",
    "TransformPipeline",
    "CompiledPipeline",
]


# =============================================================================
# Exceptions
# =============================================================================


class TransformError(Exception):
    """Base exception for transformation errors."""


# =============================================================================
# Copy Policy
# =============================================================================


class CopyPolicy(str, Enum):
    """Controls how transforms handle DataFrame copying."""

    COPY = "copy"
    COW = "cow"  # Copy-on-write (if enabled in pandas)
    INPLACE_IF_SAFE = "inplace_if_safe"


def _normalize_copy_policy(value: CopyPolicy | str | None) -> CopyPolicy:
    if isinstance(value, CopyPolicy):
        return value
    if value is None:
        return CopyPolicy.COPY
    value_str = str(value).lower()
    for policy in CopyPolicy:
        if policy.value == value_str:
            return policy
    raise TransformError(f"Unknown copy policy: {value}")


# =============================================================================
# Core Data Structures
# =============================================================================


@dataclass(frozen=True)
class TransformContext:
    """
    Context passed through the transformation pipeline.

    Immutable container for schema information, provenance references,
    and arbitrary metadata that transformations may need.
    """

    source_schema: DataSchema | None = None
    target_schema: DataSchema | None = None
    evidence_refs: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    copy_policy: CopyPolicy = CopyPolicy.COPY

    def effective_copy_policy(self) -> CopyPolicy:
        """Resolve copy policy, allowing metadata override."""
        override = self.metadata.get("copy_policy")
        if override is not None:
            return _normalize_copy_policy(override)
        return _normalize_copy_policy(self.copy_policy)


@dataclass
class TransformLineage:
    """
    Lineage tracking for transformations (Law E compliance).

    Records the complete audit trail for a transformation stage.
    """

    stage_name: str
    started_at: datetime
    completed_at: datetime
    input_row_count: int
    output_row_count: int
    parameters: dict[str, Any]
    parent_lineages: list["TransformLineage"] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Duration of this stage in milliseconds."""
        return (self.completed_at - self.started_at).total_seconds() * 1000

    @property
    def rows_added(self) -> int:
        """Number of rows added (if positive) or removed (if negative)."""
        return self.output_row_count - self.input_row_count

    def to_dict(self) -> dict[str, Any]:
        """Serialize lineage to dictionary for persistence."""
        return {
            "stage_name": self.stage_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_ms": self.duration_ms,
            "input_row_count": self.input_row_count,
            "output_row_count": self.output_row_count,
            "rows_delta": self.rows_added,
            "parameters": self.parameters,
            "parent_lineages": [p.to_dict() for p in self.parent_lineages],
        }


@dataclass
class TransformResult:
    """
    Result of a transformation pipeline execution.

    Contains the transformed data, inferred schema, complete lineage tree,
    and any warnings generated during transformation.
    """

    data: pd.DataFrame
    schema: DataSchema | None
    lineage: TransformLineage
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# Base Transform
# =============================================================================


class DataTransform(ABC):
    """
    Base class for all data transformations.

    Each transform is a pure function:
        (DataFrame, Context) → (DataFrame, Lineage, Warnings)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this transform type."""
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> tuple[pd.DataFrame, TransformLineage, list[str]]:
        """
        Apply the transformation to the input data.

        Returns:
            Tuple of (transformed_data, lineage, warnings)

        Raises:
            TransformError: If transformation fails
        """
        raise NotImplementedError

    def validate_input(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        """Validate input data before transformation."""
        return []

    def validate_output(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> list[str]:
        """Validate output data after transformation."""
        return []


# =============================================================================
# Pipeline Stages
# =============================================================================


@dataclass
class TransformStage:
    """
    A stage in the transformation pipeline.

    Represents a node in the DAG with its transformation logic
    and dependency information.
    """

    name: str
    transform: DataTransform
    dependencies: list[str] = field(default_factory=list)
    order_index: int = 0


# =============================================================================
# Pipeline Builder
# =============================================================================


class TransformPipeline:
    """
    DAG-based data transformation pipeline.

    Default builder methods create a linear chain. Use branch/fork/join
    helpers to express explicit DAGs.
    """

    def __init__(self, *, auto_chain: bool = True) -> None:
        self._stages: list[TransformStage] = []
        self._graph = CoreDagPipeline[TransformStage](auto_chain=False)
        self._compiled: CompiledPipeline | None = None
        self._auto_chain = auto_chain
        self._tail: list[str] = []

    def add_stage(
        self,
        transform: DataTransform,
        *,
        name: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> "TransformPipeline":
        """
        Add a transformation stage (builder pattern).

        Args:
            transform: The transformation to add
            name: Optional custom name (auto-generated if not provided)
            depends_on: List of stage names this depends on

        Returns:
            Self for method chaining
        """
        stage_name = name or f"{transform.name}_{len(self._stages)}"

        if self._graph.has_node(stage_name):
            raise TransformError(f"Stage name '{stage_name}' already exists")

        if depends_on is None:
            if self._auto_chain and self._tail:
                resolved_deps = list(self._tail)
            else:
                resolved_deps = []
        else:
            resolved_deps = list(depends_on)

        for dep in resolved_deps:
            if not self._graph.has_node(dep):
                raise TransformError(
                    f"Dependency '{dep}' not found in pipeline. "
                    f"Available stages: {self._graph.nodes()}"
                )

        stage = TransformStage(
            name=stage_name,
            transform=transform,
            dependencies=resolved_deps,
            order_index=len(self._stages),
        )
        self._stages.append(stage)
        self._graph.add_stage(stage, name=stage_name, depends_on=stage.dependencies)

        self._compiled = None
        self._tail = [stage_name]
        return self

    # ------------------------------------------------------------------
    # DAG helpers
    # ------------------------------------------------------------------

    def branch(
        self,
        builder: Callable[["TransformPipeline"], Any],
        *,
        depends_on: Sequence[str] | None = None,
    ) -> list[str]:
        """
        Create a branch from the current pipeline tail.

        The builder is executed against this pipeline with the tail temporarily
        set to the branch starting point. The branch tail is returned and the
        original tail is restored.
        """
        start = list(depends_on) if depends_on is not None else list(self._tail)
        original_tail = list(self._tail)
        self._tail = start
        builder(self)
        branch_tail = list(self._tail)
        self._tail = original_tail
        return branch_tail

    def fork(
        self,
        builders: Sequence[Callable[["TransformPipeline"], Any]],
        *,
        depends_on: Sequence[str] | None = None,
    ) -> list[str]:
        """Create multiple branches from the same starting point."""
        tails: list[str] = []
        for builder in builders:
            tails.extend(self.branch(builder, depends_on=depends_on))
        return tails

    def join(
        self,
        transform: DataTransform,
        *,
        name: str | None = None,
        depends_on: Sequence[str] | None = None,
    ) -> "TransformPipeline":
        """Join branches into a new stage with explicit dependencies."""
        return self.add_stage(transform, name=name, depends_on=depends_on)

    # ------------------------------------------------------------------
    # Convenience methods for common transformations
    # ------------------------------------------------------------------

    def normalize(
        self,
        field_mappings: dict[str, str] | None = None,
        unit_conversions: dict[str, tuple[str, str]] | None = None,
        *,
        type_casts: dict[str, str] | None = None,
        drop_unmapped: bool = False,
        cast_to_schema: bool = True,
    ) -> "TransformPipeline":
        """Add normalization stage."""
        from polisyos.fabric.connectors.transform.normalizer import (
            NormalizationTransform,
        )

        return self.add_stage(
            NormalizationTransform(
                field_mappings=field_mappings or {},
                unit_conversions=unit_conversions or {},
                type_casts=type_casts or {},
                drop_unmapped=drop_unmapped,
                cast_to_schema=cast_to_schema,
            )
        )

    def harmonize_codes(
        self,
        dimension: str,
        target_codelist: str,
        mapping: dict[str, str] | None = None,
        *,
        drop_unmapped: bool = False,
        warn_unmapped: bool = True,
        strict: bool = False,
    ) -> "TransformPipeline":
        """Add code harmonization stage."""
        from polisyos.fabric.connectors.transform.harmonizer import (
            CodeHarmonizationTransform,
        )

        return self.add_stage(
            CodeHarmonizationTransform(
                dimension=dimension,
                target_codelist=target_codelist,
                mapping=mapping,
                drop_unmapped=drop_unmapped,
                warn_unmapped=warn_unmapped,
                strict=strict,
            )
        )

    def impute_missing(
        self,
        strategy: str = "linear",
        fields: list[str] | None = None,
        max_missing_pct: float = 0.3,
        *,
        strict: bool = False,
        fill_value: float | None = None,
    ) -> "TransformPipeline":
        """Add missing value imputation stage."""
        from polisyos.fabric.connectors.transform.imputer import (
            ImputationTransform,
        )

        return self.add_stage(
            ImputationTransform(
                strategy=strategy,
                target_fields=fields,
                max_missing_pct=max_missing_pct,
                strict=strict,
                fill_value=fill_value,
            )
        )

    def aggregate(
        self,
        by: Sequence[Any],
        aggregations: dict[str, str],
        temporal_context: dict[str, Any] | None = None,
        *,
        additivity_context: dict[str, Any] | None = None,
        strict: bool = False,
        auto_infer_temporal: bool = True,
    ) -> "TransformPipeline":
        """Add aggregation stage."""
        from polisyos.fabric.connectors.transform.aggregator import (
            AggregationTransform,
        )

        return self.add_stage(
            AggregationTransform(
                group_by=list(by),
                aggregations=aggregations,
                temporal_context=temporal_context or {},
                additivity_context=additivity_context or {},
                strict=strict,
                auto_infer_temporal=auto_infer_temporal,
            )
        )

    def filter(
        self,
        condition: str | Callable[[pd.DataFrame], pd.Series],
        *,
        keep: bool = True,
        max_drop_pct: float = 0.9,
    ) -> "TransformPipeline":
        """Add row filtering stage."""
        from polisyos.fabric.connectors.transform.filter import FilterTransform

        return self.add_stage(
            FilterTransform(
                condition=condition,
                keep=keep,
                max_drop_pct=max_drop_pct,
            )
        )

    def validate(
        self,
        rules: Sequence[Any],
        *,
        strict: bool = False,
    ) -> "TransformPipeline":
        """Add validation stage."""
        from polisyos.fabric.connectors.transform.validator import ValidationTransform

        return self.add_stage(ValidationTransform(rules=list(rules), strict=strict))

    # ------------------------------------------------------------------
    # Compilation and Execution
    # ------------------------------------------------------------------

    def compile(self) -> "CompiledPipeline":
        """Compile pipeline for efficient execution."""
        if self._compiled is not None:
            return self._compiled

        try:
            compiled = self._graph.compile()
        except (PipelineCycleError, UnknownStageError) as exc:
            raise TransformError(str(exc)) from exc

        ordered_stages = [stage.stage for stage in compiled.stages]
        execution_order = list(compiled.execution_order)

        self._compiled = CompiledPipeline(
            stages=ordered_stages,
            execution_order=execution_order,
        )

        return self._compiled

    def apply(
        self,
        data: pd.DataFrame,
        context: TransformContext | None = None,
    ) -> TransformResult:
        """Apply pipeline to data, returning result with lineage."""
        compiled = self.compile()
        return compiled.execute(data, context or TransformContext())


# =============================================================================
# Compiled Pipeline
# =============================================================================


@dataclass
class CompiledPipeline:
    """
    Compiled, optimized pipeline ready for execution.

    The compiled pipeline has a fixed execution order determined by
    topological sorting the DAG.
    """

    stages: list[TransformStage]
    execution_order: list[str]

    def execute(
        self,
        data: pd.DataFrame,
        context: TransformContext,
    ) -> TransformResult:
        """Execute the compiled pipeline."""
        current_data = data
        lineages: list[TransformLineage] = []
        all_warnings: list[str] = []

        row_growth_threshold = float(context.metadata.get("row_growth_threshold", 10.0))
        row_growth_strict = bool(context.metadata.get("row_growth_strict", False))

        for stage in self.stages:
            input_errors = stage.transform.validate_input(current_data, context)
            if input_errors:
                raise TransformError(
                    f"Input validation failed for stage '{stage.name}': {input_errors}"
                )

            input_count = len(current_data)
            current_data, lineage, warnings = stage.transform.apply(
                current_data,
                context,
            )
            lineages.append(lineage)

            # Guardrail: row explosion
            if input_count > 0 and row_growth_threshold > 0:
                growth = len(current_data) / input_count
                if growth > row_growth_threshold:
                    message = (
                        f"[{stage.name}] Row growth {growth:.2f}x exceeds "
                        f"threshold {row_growth_threshold:.2f}x"
                    )
                    if row_growth_strict:
                        raise TransformError(message)
                    all_warnings.append(message)

            if warnings:
                all_warnings.extend(f"[{stage.name}] {w}" for w in warnings)

            output_warnings = stage.transform.validate_output(current_data, context)
            if output_warnings:
                all_warnings.extend(f"[{stage.name}] {w}" for w in output_warnings)

        now = datetime.now(timezone.utc)
        combined_lineage = TransformLineage(
            stage_name="pipeline",
            started_at=lineages[0].started_at if lineages else now,
            completed_at=lineages[-1].completed_at if lineages else now,
            input_row_count=len(data),
            output_row_count=len(current_data),
            parameters={
                "stages": [s.name for s in self.stages],
                "stage_count": len(self.stages),
            },
            parent_lineages=lineages,
        )

        output_schema = context.target_schema

        return TransformResult(
            data=current_data,
            schema=output_schema,
            lineage=combined_lineage,
            warnings=all_warnings,
        )
