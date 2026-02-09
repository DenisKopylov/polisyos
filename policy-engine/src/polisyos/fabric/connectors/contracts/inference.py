"""
Automatic schema inference from data samples.

Used when connectors don't provide explicit schemas,
or to validate provided schemas against actual data.

Inference Pipeline:
1. Sample data (if large)
2. Infer data types per column
3. Detect units from naming patterns
4. Identify semantic types
5. Detect time/geo dimensions
6. Generate schema with confidence scores

This facade re-exports all public names from the decomposed sub-modules:
- _inference_config: InferenceConfig, SchemaHints
- _inference_result: InferenceResult
- _inference_engine: SchemaInference, UNIT_PATTERNS, SEMANTIC_PATTERNS, GEO_CODE_PATTERNS
- _inference_validation: CoercionResult, infer_schema, validate_dataframe_against_schema,
                         coerce_dataframe_to_schema
"""

from polisyos.fabric.connectors.contracts._inference_config import (
    InferenceConfig,
    SchemaHints,
)
from polisyos.fabric.connectors.contracts._inference_engine import (
    GEO_CODE_PATTERNS,
    SEMANTIC_PATTERNS,
    UNIT_PATTERNS,
    SchemaInference,
)
from polisyos.fabric.connectors.contracts._inference_result import (
    InferenceResult,
)
from polisyos.fabric.connectors.contracts._inference_validation import (
    CoercionResult,
    coerce_dataframe_to_schema,
    infer_schema,
    validate_dataframe_against_schema,
)

__all__ = [
    # Configuration
    "InferenceConfig",
    "SchemaHints",
    # Result
    "InferenceResult",
    # Engine & patterns
    "SchemaInference",
    "UNIT_PATTERNS",
    "SEMANTIC_PATTERNS",
    "GEO_CODE_PATTERNS",
    # Validation & convenience
    "CoercionResult",
    "infer_schema",
    "validate_dataframe_against_schema",
    "coerce_dataframe_to_schema",
]
