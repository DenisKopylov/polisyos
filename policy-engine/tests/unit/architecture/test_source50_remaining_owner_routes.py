"""Identity controls for the exact Source50 owner routes."""

from polisyos.berl import validate_persisted_explanation_bundle_payload
from polisyos.berl.contracts.validation_rules import (
    validate_persisted_explanation_bundle_payload as owner_berl_validator,
)
from polisyos.calibration import (
    REFERENCE_PROFILES,
    EmpiricalCalibrationContext,
    EmpiricalCalibrationEvidenceRef,
    EvidenceArtifactRef,
    load_empirical_calibration_evidence,
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.calibration.forecast_bridge import (
    REFERENCE_PROFILES as OWNER_REFERENCE_PROFILES,
)
from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationContext as OwnerEmpiricalCalibrationContext,
)
from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationEvidenceRef as OwnerEmpiricalCalibrationEvidenceRef,
)
from polisyos.calibration.forecast_bridge import (
    EvidenceArtifactRef as OwnerEvidenceArtifactRef,
)
from polisyos.calibration.forecast_bridge import (
    load_empirical_calibration_evidence as owner_load_evidence,
)
from polisyos.calibration.forecast_bridge import (
    persist_empirical_calibration_evidence as owner_persist_evidence,
)
from polisyos.calibration.forecast_bridge import (
    produce_empirical_calibration_evidence as owner_produce_evidence,
)
from polisyos.lex import (
    ConstraintSeverity,
    LegalConstraint,
    LegalToDAGMapping,
    LegalToDAGMappingType,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity as OwnerConstraintSeverity,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraint as OwnerLegalConstraint,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalToDAGMapping as OwnerLegalToDAGMapping,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalToDAGMappingType as OwnerLegalToDAGMappingType,
)
from polisyos.scholar import (
    SourceSnippet,
    WebEvidenceBundle,
    validate_source_snippet_spans,
    validate_web_evidence_source_binding,
)
from polisyos.scholar.search.models import (
    SourceSnippet as OwnerSourceSnippet,
)
from polisyos.scholar.search.models import (
    WebEvidenceBundle as OwnerWebEvidenceBundle,
)
from polisyos.scholar.search.source_binding import (
    validate_source_snippet_spans as owner_validate_snippet_spans,
)
from polisyos.scholar.search.source_binding import (
    validate_web_evidence_source_binding as owner_validate_web_binding,
)
from polisyos.scientist import CritiqueReport, DraftResult
from polisyos.scientist.agent.protocols import (
    CritiqueReport as OwnerCritiqueReport,
)
from polisyos.scientist.agent.protocols import (
    DraftResult as OwnerDraftResult,
)
from polisyos.scientist.methods.backtesting import (
    CALIBRATION_RULE_ID,
    CalibrationRuleBinding,
    ForecastMethodParams,
    ForecastOwner,
    ForecastOwnerRequest,
    ForecastOwnerResult,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
    run_forecast_owner,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CALIBRATION_RULE_ID as OWNER_CALIBRATION_RULE_ID,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CalibrationRuleBinding as OwnerCalibrationRuleBinding,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastMethodParams as OwnerForecastMethodParams,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwner as OwnerForecastOwner,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwnerRequest as OwnerForecastOwnerRequest,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwnerResult as OwnerForecastOwnerResult,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastTemporalRoles as OwnerForecastTemporalRoles,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    TrainHoldoutSplit as OwnerTrainHoldoutSplit,
)
from polisyos.scientist.methods.backtesting.forecast_owner import (
    run_forecast_owner as owner_run_forecast_owner,
)
from polisyos.scientist.orchestration.engine import (
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLimit,
    BudgetMiddleware,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget import (
    BudgetLimit as OwnerBudgetLimit,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRecord as OwnerBudgetLedgerProducerRecord,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding as OwnerBudgetLedgerProducerRunBinding,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    FileBudgetLedger as OwnerFileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import (
    BudgetMiddleware as OwnerBudgetMiddleware,
)


def test_budget_runtime_exports_preserve_owner_identity() -> None:
    assert BudgetLimit is OwnerBudgetLimit
    assert BudgetMiddleware is OwnerBudgetMiddleware
    assert BudgetLedgerProducerRecord is OwnerBudgetLedgerProducerRecord
    assert BudgetLedgerProducerRunBinding is OwnerBudgetLedgerProducerRunBinding
    assert FileBudgetLedger is OwnerFileBudgetLedger


def test_predictive_bridge_exports_preserve_owner_identity() -> None:
    assert EmpiricalCalibrationContext is OwnerEmpiricalCalibrationContext
    assert EmpiricalCalibrationEvidenceRef is OwnerEmpiricalCalibrationEvidenceRef
    assert EvidenceArtifactRef is OwnerEvidenceArtifactRef
    assert REFERENCE_PROFILES is OWNER_REFERENCE_PROFILES
    assert load_empirical_calibration_evidence is owner_load_evidence
    assert persist_empirical_calibration_evidence is owner_persist_evidence
    assert produce_empirical_calibration_evidence is owner_produce_evidence
    assert CALIBRATION_RULE_ID is OWNER_CALIBRATION_RULE_ID
    assert CalibrationRuleBinding is OwnerCalibrationRuleBinding
    assert ForecastMethodParams is OwnerForecastMethodParams
    assert ForecastOwner is OwnerForecastOwner
    assert ForecastOwnerRequest is OwnerForecastOwnerRequest
    assert ForecastOwnerResult is OwnerForecastOwnerResult
    assert ForecastTemporalRoles is OwnerForecastTemporalRoles
    assert TrainHoldoutSplit is OwnerTrainHoldoutSplit
    assert run_forecast_owner is owner_run_forecast_owner


def test_candidate_berl_scholar_and_lex_exports_are_same_objects() -> None:
    assert CritiqueReport is OwnerCritiqueReport
    assert DraftResult is OwnerDraftResult
    assert validate_persisted_explanation_bundle_payload is owner_berl_validator
    assert SourceSnippet is OwnerSourceSnippet
    assert WebEvidenceBundle is OwnerWebEvidenceBundle
    assert validate_source_snippet_spans is owner_validate_snippet_spans
    assert validate_web_evidence_source_binding is owner_validate_web_binding
    assert ConstraintSeverity is OwnerConstraintSeverity
    assert LegalConstraint is OwnerLegalConstraint
    assert LegalToDAGMapping is OwnerLegalToDAGMapping
    assert LegalToDAGMappingType is OwnerLegalToDAGMappingType
