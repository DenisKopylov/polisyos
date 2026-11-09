"""Fabric quality, safety, fitness, and processing-guarantee contracts."""

# These explicit re-exports preserve the complete historical runtime namespace.
from .fitness_report import DataFitnessReport, MetricFitness
from .processing_guarantees import (  # noqa: F401
    AtomicityProof,
    BackpressurePolicy,
    BackpressureStrategy,
    CDCSchemaChangePolicy,
    CDCSchemaCompatibility,
    IdempotencyDedupePolicy,
    OutOfOrderHandling,
    OutOfOrderPolicy,
    ProcessingGuarantee,
    ProcessingGuaranteeContract,
    batch_processing_contract,
    classify_cdc_schema_change,
    default_processing_contract_for_connector,
    processing_contract_snapshot,
    stream_processing_contract,
)
from .quality import (  # noqa: F401
    TYPE_CHECKING,
    Any,
    Enum,
    Protocol,
    QualityIndicators,
    QualityLevel,
    QualityThresholds,
    annotations,
    cast,
    compute_quality_from_duckdb,
    compute_quality_indicators,
    dataclass,
    ensure_non_negative_finite,
    ensure_probability,
    field,
    get_cached_quality_indicators,
    get_logger,
    get_metrics,
    is_finite_number,
    logger,
    parse_datetime_utc,
    pd,
    replace,
    total_ordering,
    utc_age,
    utc_now,
)
from .quality import _default_metrics as _default_metrics
from .safety import (  # noqa: F401
    FabricSafetyError,
    UnsafeDataPathError,
    UnsafeFilterExpressionError,
    UnsafeIdentifierError,
    UnsafeLiteralError,
    UnsafePathSegmentError,
    escape_odsql_literal,
    escape_soql_literal,
    escape_sparql_literal,
    extract_bounded_data_path,
    quote_sql_identifier,
    safe_path_segment,
    validate_data_path,
    validate_sparql_iri_token,
    validate_sparql_variable_name,
    validate_sql_identifier,
)

__all__ = [
    "DataFitnessReport",
    "MetricFitness",
]
