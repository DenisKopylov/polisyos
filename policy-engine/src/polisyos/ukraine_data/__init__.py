"""Server-first build stack for Ukraine open-data integration artifacts."""

from .models import (
    ArtifactRetentionPolicy,
    BuildRootConfig,
    PipelineConfig,
    ResourceBudget,
    ServerConfig,
    SourceConfig,
    StageConfig,
    StageId,
    build_default_pipeline_config,
)


def main(*args, **kwargs):
    """Lazily import the CLI entrypoint to avoid package import cycles."""
    from .cli import main as _main

    return _main(*args, **kwargs)

__all__ = [
    "ArtifactRetentionPolicy",
    "BuildRootConfig",
    "PipelineConfig",
    "ResourceBudget",
    "ServerConfig",
    "SourceConfig",
    "StageConfig",
    "StageId",
    "build_default_pipeline_config",
    "main",
]
