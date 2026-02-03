"""
OpenTelemetry Configuration Module.

Provides centralized configuration for traces, metrics, and logs exporters.
Supports environment-based configuration for different deployment targets.

Environment Variables:
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (e.g., http://localhost:4317)
    OTEL_EXPORTER_OTLP_PROTOCOL: Protocol (grpc or http/protobuf)
    OTEL_SERVICE_NAME: Override service name
    POLISYOS_OTEL_ENABLED: Enable/disable OTel (default: true)
    POLISYOS_HPC_OBSERVABILITY_ENABLED: Enable/disable Phase 3 HPC observability (default: true)
    POLISYOS_OTEL_CONSOLE_EXPORT: Enable console span export for debugging
    POLISYOS_METRICS_PORT: Prometheus metrics port (default: 9464)
    POLISYOS_TRACE_SAMPLING_RATIO: Trace sampling ratio (default: 1.0)
    POLISYOS_ALWAYS_SAMPLE_ERRORS: Force sampling for spans created as errors (default: true)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ExporterType(str, Enum):
    """Supported exporter types."""

    OTLP_GRPC = "otlp_grpc"
    OTLP_HTTP = "otlp_http"
    JAEGER = "jaeger"
    CONSOLE = "console"
    NONE = "none"


class MetricsExporterType(str, Enum):
    """Supported metrics exporter types."""

    PROMETHEUS = "prometheus"
    OTLP = "otlp"
    CONSOLE = "console"
    NONE = "none"


class OTelConfig(BaseModel):
    """
    OpenTelemetry configuration with sensible defaults.

    Designed for lazy initialization to avoid slowing CLI startup.
    """

    model_config = ConfigDict(frozen=True)

    # Global toggle
    enabled: bool = Field(
        default_factory=lambda: os.getenv("POLISYOS_OTEL_ENABLED", "true").lower() == "true"
    )

    # Phase 3 HPC observability toggle
    hpc_observability_enabled: bool = Field(
        default_factory=lambda: os.getenv(
            "POLISYOS_HPC_OBSERVABILITY_ENABLED", "true"
        ).lower()
        == "true"
    )

    # Service identification
    service_name: str = Field(default_factory=lambda: os.getenv("OTEL_SERVICE_NAME", "polisyos"))
    service_version: str = Field(default="0.1.0")
    environment: str = Field(default_factory=lambda: os.getenv("POLISYOS_ENV", "development"))

    # Trace exporter configuration
    trace_exporter: ExporterType = Field(
        default_factory=lambda: (
            ExporterType.OTLP_GRPC
            if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            else ExporterType.NONE
        )
    )
    otlp_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    otlp_protocol: str = Field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    )
    otlp_headers: dict[str, str] = Field(default_factory=dict)

    # Batch processor settings (for production)
    batch_max_queue_size: int = Field(default=2048)
    batch_max_export_batch_size: int = Field(default=512)
    batch_schedule_delay_millis: int = Field(default=5000)  # 5 seconds
    batch_export_timeout_millis: int = Field(default=30000)  # 30 seconds

    # Metrics configuration
    metrics_exporter: MetricsExporterType = Field(default=MetricsExporterType.PROMETHEUS)
    metrics_port: int = Field(default_factory=lambda: int(os.getenv("POLISYOS_METRICS_PORT", "9464")))

    # Debug options
    console_export: bool = Field(
        default_factory=lambda: os.getenv("POLISYOS_OTEL_CONSOLE_EXPORT", "false").lower()
        == "true"
    )

    # Sampling configuration (Phase 4)
    sampling_ratio: float = Field(
        default_factory=lambda: float(os.getenv("POLISYOS_TRACE_SAMPLING_RATIO", "1.0")),
        ge=0.0,
        le=1.0,
        description="Trace sampling ratio. 1.0=all, 0.01=1% (recommended for prod)",
    )
    always_sample_errors: bool = Field(
        default_factory=lambda: os.getenv("POLISYOS_ALWAYS_SAMPLE_ERRORS", "true").lower()
        == "true",
        description="Force sample spans created with error attributes (best-effort)",
    )


@dataclass
class ResourceConfig:
    """
    Resource attributes for service identification.

    Populated from environment and runtime introspection.
    """

    service_name: str
    service_version: str
    service_namespace: str = "policy-engine"
    deployment_environment: str = "development"
    host_name: str = field(default_factory=lambda: __import__("socket").gethostname())
    determinism_tier: str = "UNKNOWN"

    def to_attributes(self) -> dict[str, str]:
        """Convert to OTel resource attributes."""

        return {
            "service.name": self.service_name,
            "service.version": self.service_version,
            "service.namespace": self.service_namespace,
            "deployment.environment": self.deployment_environment,
            "host.name": self.host_name,
            "polisyos.determinism.tier": self.determinism_tier,
        }


def get_default_config() -> OTelConfig:
    """
    Get default OTel configuration from environment.

    This is the primary entry point for configuration.
    """

    return OTelConfig()


def is_hpc_observability_enabled() -> bool:
    """Fast check for Phase 3 HPC observability toggle."""
    return os.getenv("POLISYOS_HPC_OBSERVABILITY_ENABLED", "true").lower() == "true"


def get_resource_config(config: OTelConfig) -> ResourceConfig:
    """
    Build resource configuration from OTel config.

    Attempts to load determinism tier from runtime fingerprint if available.
    """

    from polisyos.core.observability.determinism import get_determinism_tier

    tier = get_determinism_tier()
    determinism_tier = tier.value if tier else "UNKNOWN"

    return ResourceConfig(
        service_name=config.service_name,
        service_version=config.service_version,
        deployment_environment=config.environment,
        determinism_tier=determinism_tier,
    )
