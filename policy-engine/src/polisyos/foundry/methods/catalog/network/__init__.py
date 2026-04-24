"""Expose graph analytics, diffusion, contagion, and multiplex-network methods."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_network_methods
from .analysis import (
    CommunityDetectionEstimator,
    ContagionModelEstimator,
    InputOutputNetworkEstimator,
    MultiplexNetworkEstimator,
    NetworkDiffusionEstimator,
    NetworkMissingnessAssessmentEstimator,
    PeerEffectDecompositionEstimator,
)
from .embedding_fidelity import (
    compute_embedding_fidelity_certificate,
    maybe_compute_embedding_fidelity_certificate,
)
from .ergm import DiffusionNullTestEstimator, ERGMNullModelEstimator, fit_ergm_null_model
from .generative_protocols import (
    DiffusionNullResult,
    EdgeListNetworkData,
    ERGMResult,
    SBMStratificationResult,
)
from .missingness import (
    NetworkMissingnessMode,
    NetworkMissingnessRequest,
    NetworkMissingnessType,
    build_network_missingness_assessment,
    maybe_build_missingness_assessment,
)
from .protocols import (
    BoundEstimate,
    EmbeddingFidelityAction,
    EmbeddingFidelityStatus,
    EstimandAssessment,
    FormationEvent,
    IdentificationDiagnostics,
    IntervalEstimate,
    MissingnessAssessment,
    MissingnessAssessmentScope,
    MultiplexNetworkData,
    NetworkData,
    NetworkEmbeddingFidelityCertificate,
    NetworkEstimandTarget,
    NetworkFormationCounterfactualSummary,
    NetworkFormationDiagnostic,
    NetworkFormationIdentifiedSet,
    NetworkFormationPredictiveCheck,
    NetworkFormationScenarioMoments,
    NetworkFormationUncertaintySummary,
    NetworkFormationValidationSummary,
    NetworkIdentificationStatus,
    NetworkMissingnessRisk,
    NetworkResult,
    PeerEffectDecomposition,
    StrategicNetworkFormationData,
)
from .sbm import SBMStratificationEstimator
from .strategic import StrategicNetworkFormationEstimator


def ensure_network_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register built-in network methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_network_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "BoundEstimate",
    "CommunityDetectionEstimator",
    "ContagionModelEstimator",
    "DiffusionNullResult",
    "DiffusionNullTestEstimator",
    "ERGMNullModelEstimator",
    "ERGMResult",
    "EdgeListNetworkData",
    "EmbeddingFidelityAction",
    "EmbeddingFidelityStatus",
    "EstimandAssessment",
    "FormationEvent",
    "IdentificationDiagnostics",
    "InputOutputNetworkEstimator",
    "IntervalEstimate",
    "MissingnessAssessment",
    "MissingnessAssessmentScope",
    "MultiplexNetworkData",
    "MultiplexNetworkEstimator",
    "NetworkData",
    "NetworkDiffusionEstimator",
    "NetworkEmbeddingFidelityCertificate",
    "NetworkEstimandTarget",
    "NetworkFormationCounterfactualSummary",
    "NetworkFormationDiagnostic",
    "NetworkFormationIdentifiedSet",
    "NetworkFormationPredictiveCheck",
    "NetworkFormationScenarioMoments",
    "NetworkFormationUncertaintySummary",
    "NetworkFormationValidationSummary",
    "NetworkIdentificationStatus",
    "NetworkMissingnessAssessmentEstimator",
    "NetworkMissingnessMode",
    "NetworkMissingnessRequest",
    "NetworkMissingnessRisk",
    "NetworkMissingnessType",
    "NetworkResult",
    "PeerEffectDecomposition",
    "PeerEffectDecompositionEstimator",
    "SBMStratificationEstimator",
    "SBMStratificationResult",
    "StrategicNetworkFormationData",
    "StrategicNetworkFormationEstimator",
    "build_network_missingness_assessment",
    "compute_embedding_fidelity_certificate",
    "ensure_network_methods_registered",
    "fit_ergm_null_model",
    "maybe_build_missingness_assessment",
    "maybe_compute_embedding_fidelity_certificate",
    "register_network_methods",
]
