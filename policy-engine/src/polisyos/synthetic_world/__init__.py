"""Compatibility facade for :mod:`polisyos.foundry.agent_sim.world`.

The implementation moved under the Foundry agent simulation owner during
Repository Structure Remediation Phase 4A. Keep this root import available
until the 2026-07-31 shim sunset; deep ``polisyos.synthetic_world.*`` imports
are internal and must migrate to ``polisyos.foundry.agent_sim.world.*``.
"""

from polisyos.foundry.agent_sim.world import (
    BenchmarkSuiteBinding,
    EvaluationRun,
    EvaluationSpec,
    InterventionSpec,
    InterventionStyle,
    MeasurementErrorKind,
    MeasurementErrorSpec,
    MissingnessMechanism,
    MissingnessSpec,
    SamplingDesignKind,
    SamplingDesignSpec,
    SyntheticWorld,
    SyntheticWorldDGP,
    SyntheticWorldSample,
    TruthComputationMode,
    TruthManifest,
    TruthQuery,
    TruthSpec,
    WorldArtifact,
    WorldFamily,
    WorldSpec,
    phase0_seed_benchmark_binding,
    phase0_seed_world_specs,
)

__all__ = [
    "BenchmarkSuiteBinding",
    "EvaluationRun",
    "EvaluationSpec",
    "InterventionSpec",
    "InterventionStyle",
    "MeasurementErrorKind",
    "MeasurementErrorSpec",
    "MissingnessMechanism",
    "MissingnessSpec",
    "SamplingDesignKind",
    "SamplingDesignSpec",
    "SyntheticWorld",
    "SyntheticWorldDGP",
    "SyntheticWorldSample",
    "TruthComputationMode",
    "TruthManifest",
    "TruthQuery",
    "TruthSpec",
    "WorldArtifact",
    "WorldFamily",
    "WorldSpec",
    "phase0_seed_benchmark_binding",
    "phase0_seed_world_specs",
]
