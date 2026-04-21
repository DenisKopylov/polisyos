"""Core contracts and helpers for synthetic worlds."""

from .artifacts import EvaluationRun, SyntheticWorldSample, TruthManifest, WorldArtifact
from .specs import (
    BenchmarkSuiteBinding,
    EvaluationSpec,
    InterventionSpec,
    InterventionStyle,
    MeasurementErrorKind,
    MeasurementErrorSpec,
    MissingnessMechanism,
    MissingnessSpec,
    SamplingDesignKind,
    SamplingDesignSpec,
    SyntheticWorldDGP,
    TruthComputationMode,
    TruthQuery,
    TruthSpec,
    WorldFamily,
    WorldSpec,
)
from .truth_api import select_truth_targets

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
    "SyntheticWorldDGP",
    "SyntheticWorldSample",
    "TruthComputationMode",
    "TruthManifest",
    "TruthQuery",
    "TruthSpec",
    "WorldArtifact",
    "WorldFamily",
    "WorldSpec",
    "select_truth_targets",
]
