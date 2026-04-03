"""Aggregate analytics IR modules covering causal, uncertainty, and trust reports.

This subpackage re-exports analytics schemas for convenience, but the stable
top-level compatibility boundary remains :mod:`polisyos.ir` and the explicit
references pages under ``docs/reference/ir``.
"""

from polisyos.ir.analytics.abm_bridge import *  # noqa: F401,F403
from polisyos.ir.analytics.alignment_certification import *  # noqa: F401,F403
from polisyos.ir.analytics.applicability import *  # noqa: F401,F403
from polisyos.ir.analytics.abstraction import *  # noqa: F401,F403
from polisyos.ir.analytics.backtest import *  # noqa: F401,F403
from polisyos.ir.analytics.calibration import *  # noqa: F401,F403
from polisyos.ir.analytics.causal import *  # noqa: F401,F403
from polisyos.ir.analytics.causal_discovery import *  # noqa: F401,F403
from polisyos.ir.analytics.causal_ensemble import *  # noqa: F401,F403
from polisyos.ir.analytics.causal_graph import *  # noqa: F401,F403
from polisyos.ir.analytics.causal_queries import *  # noqa: F401,F403
from polisyos.ir.analytics.context import *  # noqa: F401,F403
from polisyos.ir.analytics.cross_graph import *  # noqa: F401,F403
from polisyos.ir.analytics.data_views import *  # noqa: F401,F403
from polisyos.ir.analytics.distributional import *  # noqa: F401,F403
from polisyos.ir.analytics.dynamic_regime import *  # noqa: F401,F403
from polisyos.ir.analytics.hte import *  # noqa: F401,F403
from polisyos.ir.analytics.literature import *  # noqa: F401,F403
from polisyos.ir.analytics.normative_arbitration import *  # noqa: F401,F403
from polisyos.ir.analytics.parameters import *  # noqa: F401,F403
from polisyos.ir.analytics.partial_identification import *  # noqa: F401,F403
from polisyos.ir.analytics.sensitivity import *  # noqa: F401,F403
from polisyos.ir.analytics.strategic import *  # noqa: F401,F403
from polisyos.ir.analytics.structural_causal_model import *  # noqa: F401,F403
from polisyos.ir.analytics.transportability import *  # noqa: F401,F403
from polisyos.ir.analytics.estimand import *  # noqa: F401,F403
from polisyos.ir.analytics.knowledge_base import *  # noqa: F401,F403
from polisyos.ir.analytics.uncertainty import *  # noqa: F401,F403
from polisyos.ir.analytics.evidence_bundle import DataProvenance, EvidenceBundle
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    EpistemicTier,
    FallbackResult,
    NegativeCertificate,
    ParametricRescueResult,
    SuggestedExperiment,
)
from polisyos.ir.analytics.query_validation_report import (
    ValidationSeverity,
    ValidationIssue,
    ValidationError,
    ValidationWarning,
    QueryValidationReport,
)
from polisyos.ir.analytics.sensitivity_report import SensitivityReport
from polisyos.ir.analytics.covariate_balance import CovariateBalanceReport, compute_smd
from polisyos.ir.analytics.falsification_report import *  # noqa: F401,F403
from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData
from polisyos.ir.analytics.causal_run_snapshot import CausalRunSnapshot, persist_snapshot, lookup_snapshot
from polisyos.ir.analytics.quality_report import CausalQualityReport, QualityDimension
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InteractionComplex,
    InterferenceEffectDecomposition,
    InterferenceCertificate,
    InterferenceMethod,
    NetworkInterferenceReport,
    load_interaction_complex,
    load_interference_certificate,
    persist_interaction_complex,
    persist_interference_certificate,
)
from polisyos.ir.analytics.data_fusion import (
    FusionDataset,
    FusionResult,
    DataCombinationPlan,
    ValidityReport,
)
from polisyos.ir.analytics.experiment_plan import (
    OptimalAdjustmentResult,
    ExperimentPlan,
    OptimalIVResult,
)
