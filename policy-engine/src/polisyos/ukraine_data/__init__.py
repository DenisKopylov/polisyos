"""Server-first build stack for Ukraine open-data integration artifacts."""

from .demography import (
    UkraineDemographyArtifacts,
    build_static_aging_state,
    load_demography_artifacts,
    load_donor_pool,
    load_reconciled_targets,
    load_transition_priors,
)
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
    "UkraineDemographyArtifacts",
    "build_default_pipeline_config",
    "build_static_aging_state",
    "load_demography_artifacts",
    "load_donor_pool",
    "load_reconciled_targets",
    "load_transition_priors",
    "main",
]
