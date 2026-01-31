"""Data transformation pipeline module for Policy OS."""
from polisyos.fabric.connectors.transform.aggregator import (
    AggregationMethod,
    AggregationTransform,
    TemporalType,
    validate_temporal_aggregation,
)
from polisyos.fabric.connectors.transform.filter import FilterTransform
from polisyos.fabric.connectors.transform.harmonizer import (
    CodeHarmonizationTransform,
    load_mapping_table,
)
from polisyos.fabric.connectors.transform.imputer import (
    ImputationStrategy,
    ImputationTransform,
    detect_missing_pattern,
    recommend_imputation_strategy,
    validate_imputation_quality,
)
from polisyos.fabric.connectors.transform.normalizer import NormalizationTransform
from polisyos.fabric.connectors.transform.pipeline import (
    CompiledPipeline,
    CopyPolicy,
    DataTransform,
    TransformContext,
    TransformError,
    TransformLineage,
    TransformPipeline,
    TransformResult,
    TransformStage,
)
from polisyos.fabric.connectors.transform.validator import (
    CompletenessRule,
    RangeRule,
    ValidationRule,
    ValidationTransform,
)

__all__ = [
    "TransformPipeline",
    "CompiledPipeline",
    "TransformContext",
    "TransformResult",
    "TransformLineage",
    "TransformStage",
    "DataTransform",
    "TransformError",
    "CopyPolicy",
    "NormalizationTransform",
    "CodeHarmonizationTransform",
    "AggregationTransform",
    "ImputationTransform",
    "FilterTransform",
    "ValidationTransform",
    "ValidationRule",
    "CompletenessRule",
    "RangeRule",
    "AggregationMethod",
    "TemporalType",
    "ImputationStrategy",
    "load_mapping_table",
    "validate_temporal_aggregation",
    "detect_missing_pattern",
    "recommend_imputation_strategy",
    "validate_imputation_quality",
]

__version__ = "1.0.0"
__phase__ = "Phase 2.5: Data Transformation Pipeline"
