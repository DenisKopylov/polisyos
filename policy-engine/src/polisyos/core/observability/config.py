"""
OpenTelemetry Configuration Module.

Provides centralized configuration for traces, metrics, and logs exporters.
Supports environment-based configuration for different deployment targets.

Environment Variables:
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector endpoint (e.g., http://localhost:4317)
    OTEL_EXPORTER_OTLP_PROTOCOL: Protocol (grpc or http/protobuf)
    OTEL_SERVICE_NAME: Override service name
    POLISYOS_OTEL_ENABLED: Enable/disable OTel (default: true)
    POLISYOS_OTEL_CONSOLE_EXPORT: Enable console span export for debugging
    POLISYOS_METRICS_PORT: Prometheus metrics port (default: 9464)
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

    # Sampling configuration
    sampling_ratio: float = Field(default=1.0)  # 100% for dev, reduce in prod


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


def get_resource_config(config: OTelConfig) -> ResourceConfig:
    """
    Build resource configuration from OTel config.

    Attempts to load determinism tier from runtime fingerprint if available.
    """

    determinism_tier = "UNKNOWN"
    try:
        from polisyos.foundry.runtime.fingerprint import get_determinism_tier

        determinism_tier = get_determinism_tier().value
    except ImportError:
        pass
    except Exception:
        pass

    return ResourceConfig(
        service_name=config.service_name,
        service_version=config.service_version,
        deployment_environment=config.environment,
        determinism_tier=determinism_tier,
    )
