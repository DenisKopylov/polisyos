#!/usr/bin/env python3
"""Recompute and freeze the GY-N11 honest confidence ledger contract."""

from __future__ import annotations

import argparse
import copy
import faulthandler
import hashlib
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass
from decimal import ROUND_FLOOR, Decimal, localcontext
from fractions import Fraction
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictBytes,
    StrictFloat,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
)

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import PromotionObligationClass, gy_content_hash
from polisyos.runtime.quality.confidence_ledger import (
    CONDITIONAL_VALIDITY_CLAUSE,
    CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION,
    CONFIDENCE_LEDGER_SCHEMA_VERSION,
    GOOD_EVENT_CLAUSE,
    CertificateClassRoute,
    ConfidenceLedgerCheck,
    ConfidenceLedgerError,
    ConfidenceLedgerPolicy,
    ConfidenceLedgerReceipt,
    ConfidenceLedgerRegistry,
    ConfidenceLedgerSession,
    ConfidenceRiskBudgetScope,
    InstrumentDefinition,
    InstrumentProofProfile,
    N9PromotionCertificateProjection,
    N12EpochReferenceProjection,
    ObligationBudgetPool,
    OwnerCertificateEvidence,
    OwnerCertificateVerification,
    PredictableClaimSpec,
    PredictableScheduleProfile,
    RationalSpec,
    load_confidence_ledger_registry,
    project_confidence_ledger_semantic_receipt,
    project_n9_promotion_certificate,
    project_n12_epoch_reference,
    recompute_confidence_owner_evidence_hash,
    recompute_confidence_schedule_projection_hash,
    recompute_confidence_scope_anchor_ref,
    validate_confidence_ledger_receipt,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerSemanticCheck as FrozenLedgerCheckProjection,
)
from polisyos.runtime.quality.confidence_ledger import (
    ConfidenceLedgerSemanticReceiptProjection as FrozenLedgerReceiptProjection,
)
from tools.quality.validation.layer3_gy_confidence_ledger_contract import (
    N10OwnerProjection,
    N13bOwnerProjection,
    clear_owner_bundle_cache,
    load_owner_bundle,
    owner_bundle_cache_stats,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = Path("architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json")
REGISTRY_PATH = Path("architecture/production_quality/confidence_ledger.toml")
DEFAULT_CATALOG_PATH = Path(
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
DEFAULT_L5_PATH = Path(
    "production_data/canonical/local_data_20260501/ukraine_server_support_20260410/"
    "runtime_calibration_internals/calibration/d2/measurement_registry.json"
)
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1"
CONFIDENCE_LEDGER_SOURCE_PATH = Path("src/polisyos/runtime/quality/confidence_ledger.py")
PROMOTION_SOURCE_PATH = Path("src/polisyos/runtime/quality/promotion_sequence.py")
GENERATION_SOURCE_PATH = Path("src/polisyos/runtime/quality/generation_cycle.py")
OWNER_ADAPTER_SOURCE_PATH = Path("tools/quality/validation/layer3_gy_confidence_ledger_contract.py")
CONFIDENCE_LEDGER_TEST_PATH = Path("tests/unit/runtime/quality/test_confidence_ledger.py")
PROMOTION_TEST_PATH = Path("tests/unit/runtime/quality/test_promotion_sequence.py")
CHECKER_TEST_PATH = Path("tests/repo_quality/tools/test_layer3_gy_confidence_ledger_contract.py")
SOURCE_FLIP_MUTATION_IDS: tuple[str, ...] = (
    "source_flip_over_spend_admission",
    "source_flip_schedule_slot_validation_removed",
    "source_flip_unknown_instrument_bypass",
    "source_flip_bayesian_ci_relabelled_anytime_valid",
    "source_flip_n9_ledger_draw_bypass",
    "source_flip_forged_spend_row_trusted",
    "source_flip_rehashed_forged_registry_trusted",
    "source_flip_conditionality_clause_deleted",
    "source_flip_deterministic_proof_nonzero_spend",
    "source_flip_unexecuted_check_spend_admitted",
    "source_flip_owner_certificate_recomputation_removed",
    "source_flip_registry_content_binding_removed",
    "source_flip_generation_cycle_ledger_revalidation_removed",
    "source_flip_obligation_split_denominator_truncated",
    "source_flip_duplicate_schedule_slot_accepted",
    "source_flip_non_anytime_instrument_promoted",
    "source_flip_projection_drops_conditionality_or_binds_whole_contract",
)
CORRUPT_FIELD_MUTATION_IDS: tuple[str, ...] = (
    "conditionality_clause",
    "registry_hash",
    "registry_conditionality_clause",
    "unseen_instrument_probe_projection_hash",
    "maintained_assumptions",
    "schedule_coefficient_numerator",
    "schedule_coefficient_denominator",
    "schedule_coefficient_display",
    "obligation_membership",
    "proof_kernel_theorem_id",
    "ledger_parent_head",
    "ledger_current_head",
    "semantic_root_hash",
    "executed_check_id",
    "executed_check_ordinal",
    "filtration_binding",
    "semantic_request_fingerprint",
    "claim_binding",
    "claim_polarity",
    "prepared_event_status",
    "started_event_status",
    "completed_event_status",
    "semantic_check_hash",
    "semantic_event_hash",
    "semantic_claim_execution_hash",
    "semantic_owner_invocation_claim",
    "semantic_owner_binding_hash",
    "semantic_good_event_identity",
    "semantic_ledger_projection_hash",
    "real_run_spend",
    "accounted_owner_hash",
    "conformance_spend",
    "per_check_spend",
    "promotion_projection_hash",
    "promotion_head_ref",
    "promotion_scope_anchor",
    "n12_scope_anchor",
    "projection_authority",
    "projection_deployment",
    "real_projection_scope",
    "conformance_projection_scope",
    "real_projection_conditionality_clause",
    "conformance_projection_conditionality_clause",
    "n9_projection_conditionality_clause",
    "n12_conditionality_clause",
    "epoch_projection_field",
    "accounted_run_projection_hash",
    "projection_edge_hash",
    "projection_edge_deleted",
    "projection_edge_cycle",
)
_BASEL_PI_UPPER = Fraction(355, 113)
_BASEL_COEFFICIENT_LOWER = Fraction(6 * 113 * 113, 355 * 355)
_SCHEDULE_DECIMAL_QUANTUM = Decimal("1e-48")
_HISTORICAL_STAGE_SECONDS: dict[str, float] = {
    "worker_startup": 60.0,
    "cold_owner_derivation": 25.0 * 60.0,
    "warmup_owner_derivation": 25.0 * 60.0,
    "warm_owner_derivation": 5.0 * 60.0,
    "cache_hit_derivation": 5.0 * 60.0,
}
_HEARTBEAT_INTERVAL_SECONDS = 30.0
_PROFILE_SIGNAL_GRACE_SECONDS = 0.1
_COLD_OWNER_PROGRESS_MILESTONES: tuple[str, ...] = (
    "n10_owner_recomputation_started",
    "n10_owner_recomputation_complete",
    "n13b_owner_recomputation_started",
    "n13b_owner_recomputation_complete",
    "n10_owner_projection_complete",
    "n13b_owner_projection_complete",
)
_BUILD_PROGRESS_PREFIX: tuple[str, ...] = (
    "confidence_registry_loaded",
    "owner_pre_derivation_fence_started",
    "owner_pre_derivation_fence_complete",
)
_BUILD_PROGRESS_SUFFIX: tuple[str, ...] = (
    "owner_post_derivation_fence_started",
    "owner_post_derivation_fence_complete",
    "owner_bundle_fence_validated",
    "owner_bundle_loaded",
    "n10_evidence_accounting_started",
    "n10_evidence_accounting_complete",
    "n13b_passport_accounting_started",
    "n13b_passport_accounting_complete",
    "real_ledger_receipt_validated",
    "n9_live_projection_validated",
    "n12_live_projection_validated",
    "conformance_ledger_started",
    "conformance_check_executed",
    "conformance_ledger_receipt_validated",
    "confidence_ledger_receipts_validated",
    "real_semantic_projection_complete",
    "conformance_semantic_projection_complete",
    "frozen_consumer_projections_complete",
    "frozen_contract_derived",
)


@dataclass(frozen=True)
class _SourceFlipReplacement:
    """One exact source replacement used by a restoring behavioral mutation."""

    source_path: Path
    old: str
    new: str


@dataclass(frozen=True)
class _SourceFlipCase:
    """One source mutation and its fresh-process semantic witness."""

    mutation_id: str
    replacements: tuple[_SourceFlipReplacement, ...]
    probe_nodeid: str
    expected_red_signal: str


@dataclass(frozen=True)
class _CodeOwnedOwnerCertificateContract:
    """Independent provenance and obligation contract for one real owner class."""

    certificate_class: str
    verifier_kernel_id: str
    obligation_class: PromotionObligationClass
    certificate_role: str
    claim_polarity: str
    owner_ref: str
    verifier_ref: str

    def route_matches(self, route: CertificateClassRoute) -> bool:
        """Return whether registry data preserves every code-owned semantic field."""

        return bool(
            route.verifier_kernel_id == self.verifier_kernel_id
            and route.obligation_class == self.obligation_class
            and route.certificate_role == self.certificate_role
            and route.claim_polarity == self.claim_polarity
            and route.owner_ref == self.owner_ref
            and route.verifier_ref == self.verifier_ref
        )


def _code_owned_owner_certificate_contracts() -> tuple[
    _CodeOwnedOwnerCertificateContract,
    ...,
]:
    """Return N10/N13b owner contracts; instrument choice stays registry-owned."""

    n10_owner = (
        "tools.quality.validation.layer3_gy_n13a_acquisition_census."
        "extract_route_projection"
    )
    n10_verifier = (
        "tools.quality.validation."
        "check_layer3_gy_depth_n_universality_contract.validate_payload"
    )
    return (
        _CodeOwnedOwnerCertificateContract(
            certificate_class="owner_acquisition_route",
            verifier_kernel_id="n10_route_projection_recompute_v1",
            obligation_class=PromotionObligationClass.DATA,
            certificate_role="acquisition",
            claim_polarity="confident_wrong_refusal",
            owner_ref=n10_owner,
            verifier_ref=n10_verifier,
        ),
        _CodeOwnedOwnerCertificateContract(
            certificate_class="estimand_binding_refusal",
            verifier_kernel_id="n10_route_projection_recompute_v1",
            obligation_class=PromotionObligationClass.IDENTIFICATION,
            certificate_role="refusal",
            claim_polarity="confident_wrong_refusal",
            owner_ref=n10_owner,
            verifier_ref=n10_verifier,
        ),
        _CodeOwnedOwnerCertificateContract(
            certificate_class="owner_data_gap",
            verifier_kernel_id="n10_route_projection_recompute_v1",
            obligation_class=PromotionObligationClass.DATA,
            certificate_role="refusal",
            claim_polarity="confident_wrong_refusal",
            owner_ref=n10_owner,
            verifier_ref=n10_verifier,
        ),
        _CodeOwnedOwnerCertificateContract(
            certificate_class="admission_passport",
            verifier_kernel_id="n13b_passport_revalidate_v1",
            obligation_class=PromotionObligationClass.DATA,
            certificate_role="admission",
            claim_polarity="confident_wrong_admission",
            owner_ref=(
                "polisyos.runtime.quality.acquisition_executor."
                "build_admission_passport"
            ),
            verifier_ref=(
                "polisyos.runtime.quality.acquisition_executor."
                "revalidate_admission_passport"
            ),
        ),
    )


def _bind_code_owned_owner_certificate_routes(
    registry: ConfidenceLedgerRegistry,
) -> dict[
    str,
    tuple[_CodeOwnedOwnerCertificateContract, CertificateClassRoute],
]:
    """Resolve every real owner route before any ledger event or risk spend."""

    contracts = _code_owned_owner_certificate_contracts()
    contract_classes = {item.certificate_class for item in contracts}
    contract_kernels = {item.verifier_kernel_id for item in contracts}
    for route in registry.certificate_class_routes:
        if (
            route.verifier_kernel_id in contract_kernels
            and route.certificate_class not in contract_classes
        ):
            raise ValueError(
                "owner_certificate_route_contract_unowned:"
                f"{route.certificate_class}"
            )
    bound: dict[
        str,
        tuple[_CodeOwnedOwnerCertificateContract, CertificateClassRoute],
    ] = {}
    for contract in contracts:
        try:
            route = registry.resolve_certificate_route(contract.certificate_class)
        except ConfidenceLedgerError as exc:
            raise ValueError(
                "owner_certificate_route_contract_missing:"
                f"{contract.certificate_class}"
            ) from exc
        if not contract.route_matches(route):
            raise ValueError(
                "owner_certificate_route_contract_mismatch:"
                f"{contract.certificate_class}"
            )
        bound[contract.certificate_class] = (contract, route)
    return bound


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH.as_posix()]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _StrictWireModel(BaseModel):
    """Exact local IPC shape; no bool/string/container coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class _WorkerCacheStats(_StrictWireModel):
    hits: StrictInt = Field(ge=0)
    misses: StrictInt = Field(ge=0)
    maxsize: StrictInt = Field(ge=0)
    currsize: StrictInt = Field(ge=0)


class _WorkerBootstrapMessage(_StrictWireModel):
    kind: Literal["worker_bootstrap"]
    pid: StrictInt = Field(gt=0)
    pgid: StrictInt = Field(gt=0)
    profiling_ready: StrictBool


class _WorkerReadyMessage(_StrictWireModel):
    kind: Literal["worker_ready"]
    pid: StrictInt = Field(gt=0)


class _ObjectiveProgressMessage(_StrictWireModel):
    kind: Literal["objective_progress"]
    stage: StrictStr = Field(min_length=1)
    ordinal: StrictInt = Field(gt=0)
    milestone: StrictStr = Field(min_length=1)


class _StageResultMessage(_StrictWireModel):
    kind: Literal["stage_result"]
    stage: StrictStr = Field(min_length=1)
    result_role: Literal["warmup", "first", "second"]
    worker_pid: StrictInt = Field(gt=0)
    wall_time_seconds: StrictFloat = Field(ge=0, allow_inf_nan=False)
    contract_bytes: StrictBytes
    cache_before: _WorkerCacheStats
    cache_after_warmup: _WorkerCacheStats | None
    cache_after_first: _WorkerCacheStats | None
    cache_after: _WorkerCacheStats


class _WorkerCompleteMessage(_StrictWireModel):
    kind: Literal["worker_complete"]
    pid: StrictInt = Field(gt=0)


class _WorkerErrorMessage(_StrictWireModel):
    kind: Literal["worker_error"]
    error_type: StrictStr = Field(min_length=1)
    detail: StrictStr
    traceback: StrictStr


_WorkerMessage = Annotated[
    _WorkerBootstrapMessage
    | _WorkerReadyMessage
    | _ObjectiveProgressMessage
    | _StageResultMessage
    | _WorkerCompleteMessage
    | _WorkerErrorMessage,
    Field(discriminator="kind"),
]
_WORKER_MESSAGE_ADAPTER = TypeAdapter(_WorkerMessage)


class _BootstrapAcceptedCommand(_StrictWireModel):
    command: Literal["bootstrap_accepted"]


class _RunSecondPassCommand(_StrictWireModel):
    command: Literal["run_second_pass"]


class RegistrySectionHashes(_StrictModel):
    """Content identities for every load-bearing registry section."""

    policy: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_profiles: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    obligation_pools: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    proof_profiles: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    instruments: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    certificate_class_routes: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ObligationClassWeight(_StrictModel):
    """Exact expanded schedule weight for one N9 obligation class."""

    obligation_class: PromotionObligationClass
    weight: RationalSpec


class ScheduleProofProjection(_StrictModel):
    """Exact checker-recomputed Basel schedule theorem projection."""

    schedule_profile_id: str = Field(min_length=1)
    proof_kernel_id: Literal["basel_square_v1"]
    declared_ideal_weight_formula: Literal["6/(pi^2*(t+1)^2)"]
    pi_upper_bound: RationalSpec
    certified_rational_coefficient: RationalSpec
    certified_rational_coefficient_decimal: str
    declared_mass: RationalSpec
    total_mass_relation: Literal["sum_t executable_weight_t <= declared_mass <= 1"]
    obligation_weights: tuple[ObligationClassWeight, ...]
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RegistryProjection(_StrictModel):
    """Typed content-bound N11 registry/config projection."""

    source_ref: str = Field(min_length=1)
    registry_schema_version: Literal[CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION]
    runtime_schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    artifact_schema_version: Literal[SCHEMA_VERSION]
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    section_hashes: RegistrySectionHashes
    policy: ConfidenceLedgerPolicy
    schedule_profiles: tuple[PredictableScheduleProfile, ...]
    obligation_pools: tuple[ObligationBudgetPool, ...]
    proof_profiles: tuple[InstrumentProofProfile, ...]
    instruments: tuple[InstrumentDefinition, ...]
    certificate_class_routes: tuple[CertificateClassRoute, ...]
    selected_schedule_proof: ScheduleProofProjection
    rule_ref: Literal[SCHEMA_VERSION]
    schema_ref: Literal[SCHEMA_VERSION]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class OwnerBundleProjection(_StrictModel):
    """Typed narrow N10/N13b owner projection carried by the artifact."""

    projection_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    n10: N10OwnerProjection
    n13b: N13bOwnerProjection


class ProjectionEdge(_StrictModel):
    """One declared directed projection dependency."""

    producer_scope: str = Field(min_length=1)
    producer_projection_ref: str = Field(min_length=1)
    producer_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    consumer_scope: str = Field(min_length=1)
    consumer_projection_ref: str = Field(min_length=1)
    consumer_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class UnseenInstrumentProbeEvidence(_StrictModel):
    """Content-bound runtime witness that U2 refuses before execution or spend."""

    request_key: Literal["universality://unseen-instrument/frozen"]
    instrument_id: Literal["__n11_unregistered_instrument_probe__"]
    instrument_family: Literal["unknown_instrument"]
    proof_profile_id: Literal["unknown_profile"]
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    refusal_code: Literal["unknown_instrument"]
    execution_status: Literal["refused"]
    outcome: Literal["preflight_refusal"]
    event_count: Literal[1]
    check_count: Literal[1]
    execution_ordinal: None
    schedule_query_index: None
    execution_id: None
    deterministic_proof: Literal[False]
    anytime_valid: Literal[False]
    instrument_definition_hash: None
    proof_profile_hash: None
    spend_numerator: Literal[0]
    spend_denominator: Literal[1]
    total_spend_numerator: Literal[0]
    total_spend_denominator: Literal[1]
    total_spend_decimal: Literal["0"]
    supports_obligation: Literal[False]
    eligible_for_promotion: Literal[False]
    within_budget: Literal[True]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class UniversalityEvidence(_StrictModel):
    """Runtime-derived U2/U3 facts without authorial pass booleans."""

    registered_instrument_count: int = Field(gt=0)
    structurally_distinct_instrument_family_count: int = Field(gt=0)
    registered_proof_kernel_ids: tuple[str, ...]
    registered_certificate_route_count: int = Field(ge=0)
    real_accounted_instrument_ids: tuple[str, ...]
    unseen_instrument_probe: UnseenInstrumentProbeEvidence


class FrozenN9PromotionLedgerRow(_StrictModel):
    """Stable N9 draw row derived from the semantic ledger projection."""

    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    instrument_family: str = Field(min_length=1)
    certificate_ref: str = Field(min_length=1)
    certificate_role: Literal["promotion"]
    claim_polarity: Literal["false_accept"]
    check_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_status: Literal["prepared", "started", "executed", "refused", "unexecuted"]
    outcome: Literal[
        "prepared",
        "started",
        "supported",
        "not_supported",
        "preflight_refusal",
        "cancelled",
        "owner_refused",
        "owner_error",
        "recovered_crash",
        "refused",
    ]
    execution_ordinal: int | None = Field(default=None, ge=0)
    execution_id: str | None = Field(
        default=None,
        pattern=r"^confidence-execution:sha256:[0-9a-f]{64}$",
    )
    spend: RationalSpec
    spend_decimal: str
    anytime_valid: bool
    supports_obligation: bool
    eligible_for_promotion: bool
    claim_execution_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class FrozenN9PromotionCertificateProjection(_StrictModel):
    """Frozen narrow N9 consumer projection without operational CAS identities."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal["n9_promotion_certificate"]
    authority_provenance: Literal["canonical_repo", "verification"]
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schedule_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    promotion_rows: tuple[FrozenN9PromotionLedgerRow, ...]
    total_spend: RationalSpec
    total_spend_decimal: str
    budget_delta: RationalSpec
    budget_delta_decimal: str
    within_budget: bool
    good_event_clause: Literal[GOOD_EVENT_CLAUSE]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class FrozenN12EpochReferenceProjection(_StrictModel):
    """Frozen future-N12 locator bound directly to the ledger projection."""

    schema_version: Literal[CONFIDENCE_LEDGER_SCHEMA_VERSION]
    projection_scope: Literal["n12_epoch_reference"]
    authority_provenance: Literal["canonical_repo", "verification"]
    deployment_identity: str = Field(pattern=r"^policy-engine-deployment:sha256:[0-9a-f]{64}$")
    risk_scope: ConfidenceRiskBudgetScope
    scope_id: str = Field(pattern=r"^confidence-risk-scope:sha256:[0-9a-f]{64}$")
    scope_anchor_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ledger_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    epoch_ref: str | None
    model_ref: str | None
    rule_ref: str | None
    schema_ref: str | None
    validity: Literal["epoch_not_implemented"]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class AccountedEvidenceRow(_StrictModel):
    """One real owner-derived row accounted by the ledger."""

    certificate_class: str = Field(min_length=1)
    certificate_ref: str = Field(min_length=1)
    obligation_class: PromotionObligationClass
    instrument_id: str = Field(min_length=1)
    certificate_role: Literal["refusal", "acquisition", "admission"]
    claim_polarity: Literal[
        "confident_wrong_refusal",
        "confident_wrong_admission",
    ]
    owner_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    check_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim_execution_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_ordinal: int = Field(ge=0)
    execution_status: Literal["executed"]
    deterministic_proof: bool
    supports_obligation: bool
    eligible_for_promotion: bool
    spend_numerator: int = Field(ge=0)
    spend_denominator: int = Field(gt=0)


class RealAccountedRun(_StrictModel):
    """Measured N10/N13b denominator and its genuine spend record."""

    n10_route_count: int = Field(ge=0)
    owner_acquisition_route_count: int = Field(ge=0)
    estimand_binding_refusal_count: int = Field(ge=0)
    owner_data_gap_count: int = Field(ge=0)
    n13b_attempt_count: int = Field(ge=0)
    n13b_raw_response_count: int = Field(ge=0)
    n13b_admission_count: int = Field(ge=0)
    n13b_passport_count: int = Field(ge=0)
    evidence_rows: tuple[AccountedEvidenceRow, ...]
    total_spend_numerator: int = Field(ge=0)
    total_spend_denominator: int = Field(gt=0)
    total_spend_decimal: str
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ConformanceAccountedRun(_StrictModel):
    """Separate positive-spend proof that the probabilistic machinery executes."""

    instrument_id: Literal["constant_unit_e_process"]
    certificate_role: Literal["promotion_conformance"]
    claim_polarity: Literal["conformance_only"]
    check_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    claim_execution_projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    execution_ordinal: int = Field(ge=0)
    anytime_valid: Literal[True]
    supports_obligation: Literal[False]
    eligible_for_promotion: Literal[False]
    total_spend_numerator: int = Field(gt=0)
    total_spend_denominator: int = Field(gt=0)
    total_spend_decimal: str


class FrozenConfidenceLedgerContract(_StrictModel):
    """Projection-scoped frozen N11 contract."""

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    contract_id: Literal["layer3-gy-n11-honest-confidence-ledger"]
    owner: Literal["polisyos.runtime.quality.confidence_ledger.ConfidenceLedgerSession"]
    registry_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    registry_projection: RegistryProjection
    owner_bundle_projection: OwnerBundleProjection
    accounted_run: RealAccountedRun
    conformance_run: ConformanceAccountedRun
    real_ledger_projection: FrozenLedgerReceiptProjection
    conformance_ledger_projection: FrozenLedgerReceiptProjection
    n9_promotion_projection: FrozenN9PromotionCertificateProjection
    n12_epoch_reference_projection: FrozenN12EpochReferenceProjection
    projection_edges: tuple[ProjectionEdge, ...]
    conditionality_clause: Literal[CONDITIONAL_VALIDITY_CLAUSE]
    maintained_assumptions: tuple[Literal["obligation_completeness", "validator_soundness"], ...]
    universality: UniversalityEvidence
    artifact_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _rational(value: Fraction) -> RationalSpec:
    return RationalSpec(numerator=value.numerator, denominator=value.denominator)


def _display_down(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 96
        rendered = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            _SCHEDULE_DECIMAL_QUANTUM, rounding=ROUND_FLOOR
        )
    return format(rendered, "f").rstrip("0").rstrip(".") or "0"


def _registry_section_hashes(registry: ConfidenceLedgerRegistry) -> RegistrySectionHashes:
    return RegistrySectionHashes(
        policy=_ledger_content_hash(registry.policy),
        schedule_profiles=_ledger_content_hash(registry.schedule_profiles),
        obligation_pools=_ledger_content_hash(registry.obligation_pools),
        proof_profiles=_ledger_content_hash(registry.proof_profiles),
        instruments=_ledger_content_hash(registry.instruments),
        certificate_class_routes=_ledger_content_hash(registry.certificate_class_routes),
    )


def _build_registry_projection(registry: ConfidenceLedgerRegistry) -> RegistryProjection:
    schedule = registry.resolve_schedule()
    obligation_weights = tuple(
        ObligationClassWeight(
            obligation_class=obligation_class,
            weight=_rational(weight),
        )
        for obligation_class, weight in sorted(
            registry.obligation_weights.items(), key=lambda item: item[0].value
        )
    )
    proof = ScheduleProofProjection(
        schedule_profile_id=schedule.profile_id,
        proof_kernel_id="basel_square_v1",
        declared_ideal_weight_formula="6/(pi^2*(t+1)^2)",
        pi_upper_bound=_rational(_BASEL_PI_UPPER),
        certified_rational_coefficient=_rational(_BASEL_COEFFICIENT_LOWER),
        certified_rational_coefficient_decimal=_display_down(_BASEL_COEFFICIENT_LOWER),
        declared_mass=schedule.mass,
        total_mass_relation="sum_t executable_weight_t <= declared_mass <= 1",
        obligation_weights=obligation_weights,
        schedule_projection_hash=recompute_confidence_schedule_projection_hash(
            registry,
            schedule_profile_id=schedule.profile_id,
        ),
    )
    values: dict[str, Any] = {
        "source_ref": REGISTRY_PATH.as_posix(),
        "registry_schema_version": registry.schema_version,
        "runtime_schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "artifact_schema_version": SCHEMA_VERSION,
        "registry_content_hash": registry.content_hash,
        "section_hashes": _registry_section_hashes(registry),
        "policy": registry.policy,
        "schedule_profiles": registry.schedule_profiles,
        "obligation_pools": registry.obligation_pools,
        "proof_profiles": registry.proof_profiles,
        "instruments": registry.instruments,
        "certificate_class_routes": registry.certificate_class_routes,
        "selected_schedule_proof": proof,
        "rule_ref": SCHEMA_VERSION,
        "schema_ref": SCHEMA_VERSION,
        "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
    }
    values["projection_hash"] = _ledger_content_hash(values)
    return RegistryProjection.model_validate(values)


def _real_risk_scope(owner_bundle: Any) -> ConfidenceRiskBudgetScope:
    """Derive the frozen real-accounting scope from narrow owner projections."""

    return ConfidenceRiskBudgetScope(
        scope_owner_ref=(
            "tools.quality.validation.check_layer3_gy_confidence_ledger.build_live_contract"
        ),
        authority_purpose="n11_real_n10_n13b_accounting",
        owner_scope_key="frozen-owner-bundle:n10+n13b",
        owner_projection_hash=owner_bundle.projection_sha256,
        epoch_ref=None,
        model_ref=owner_bundle.n13b.baseline_sha256,
        rule_ref=SCHEMA_VERSION,
        schema_ref=SCHEMA_VERSION,
    )


def _conformance_risk_scope(registry: ConfidenceLedgerRegistry) -> ConfidenceRiskBudgetScope:
    """Derive the frozen positive-spend conformance scope."""

    return ConfidenceRiskBudgetScope(
        scope_owner_ref=(
            "polisyos.runtime.quality.confidence_ledger.closed_constant_unit_e_process_v1"
        ),
        authority_purpose="n11_probabilistic_conformance",
        owner_scope_key="constant-unit-e-process:frozen-conformance",
        owner_projection_hash=registry.content_hash,
        epoch_ref=None,
        model_ref=None,
        rule_ref=SCHEMA_VERSION,
        schema_ref=SCHEMA_VERSION,
    )


def _unseen_instrument_probe_risk_scope(
    registry: ConfidenceLedgerRegistry,
) -> ConfidenceRiskBudgetScope:
    """Derive the isolated U2 fail-closed conformance scope."""

    return ConfidenceRiskBudgetScope(
        scope_owner_ref=(
            "tools.quality.validation.check_layer3_gy_confidence_ledger."
            "_build_unseen_instrument_probe"
        ),
        authority_purpose="n11_unseen_instrument_conformance",
        owner_scope_key="unseen-instrument:frozen-conformance",
        owner_projection_hash=registry.content_hash,
        epoch_ref=None,
        model_ref=None,
        rule_ref=SCHEMA_VERSION,
        schema_ref=SCHEMA_VERSION,
    )


def _ledger_fraction_display(value: Fraction) -> str:
    """Render a ledger rational with the runtime's exact 48-place floor rule."""

    if value == 0:
        return "0"
    scale = 10**48
    scaled = value.numerator * scale // value.denominator
    whole, remainder = divmod(scaled, scale)
    if remainder == 0:
        return str(whole)
    decimals = f"{remainder:048d}".rstrip("0")
    return f"{whole}.{decimals}"


def _frozen_ledger_root_values(
    *,
    receipt: ConfidenceLedgerReceipt | FrozenLedgerReceiptProjection,
    risk_scope: ConfidenceRiskBudgetScope,
    projection_scope: str,
) -> dict[str, Any]:
    """Return the stable semantic root payload shared by writer and checker."""

    return {
        "schema_version": receipt.schema_version,
        "projection_scope": projection_scope,
        "authority_provenance": receipt.authority_provenance,
        "deployment_identity": receipt.deployment_identity,
        "risk_scope": risk_scope,
        "scope_id": receipt.scope_id,
        "scope_anchor_ref": receipt.scope_anchor_ref,
        "registry_content_hash": receipt.registry_content_hash,
        "schedule_profile_id": receipt.schedule_profile_id,
        "schedule_profile_hash": receipt.schedule_profile_hash,
        "schedule_projection_hash": receipt.schedule_projection_hash,
        "budget_delta": receipt.budget_delta,
        "budget_delta_decimal": receipt.budget_delta_decimal,
        "conditionality_clause": receipt.conditionality_clause,
        "maintained_assumptions": receipt.maintained_assumptions,
    }


def _project_frozen_n9(
    runtime_projection: N9PromotionCertificateProjection,
    *,
    ledger: FrozenLedgerReceiptProjection,
) -> FrozenN9PromotionCertificateProjection:
    """Project the live N9 draw surface onto stable ledger identities."""

    rows = tuple(
        FrozenN9PromotionLedgerRow(
            obligation_class=check.obligation_class,
            instrument_id=check.instrument_id,
            instrument_family=check.instrument_family,
            certificate_ref=check.certificate_ref,
            certificate_role="promotion",
            claim_polarity="false_accept",
            check_projection_hash=check.check_projection_hash,
            execution_status=check.execution_status,
            outcome=check.outcome,
            execution_ordinal=check.execution_ordinal,
            execution_id=check.execution_id,
            spend=check.spend,
            spend_decimal=check.spend_decimal,
            anytime_valid=check.anytime_valid,
            supports_obligation=check.supports_obligation,
            eligible_for_promotion=check.eligible_for_promotion,
            claim_execution_projection_hash=(check.claim_execution_projection_hash),
        )
        for check in ledger.checks
        if check.certificate_role == "promotion" and check.claim_polarity == "false_accept"
    )
    if len(rows) != len(runtime_projection.promotion_rows):
        raise ValueError("frozen_n9_promotion_denominator_drift")
    values: dict[str, Any] = {
        "schema_version": runtime_projection.schema_version,
        "projection_scope": runtime_projection.projection_scope,
        "authority_provenance": runtime_projection.authority_provenance,
        "deployment_identity": runtime_projection.deployment_identity,
        "risk_scope": runtime_projection.risk_scope,
        "scope_id": runtime_projection.scope_id,
        "scope_anchor_ref": runtime_projection.scope_anchor_ref,
        "ledger_projection_hash": ledger.projection_hash,
        "registry_content_hash": runtime_projection.registry_content_hash,
        "schedule_projection_hash": runtime_projection.schedule_projection_hash,
        "promotion_rows": rows,
        "total_spend": runtime_projection.total_spend,
        "total_spend_decimal": runtime_projection.total_spend_decimal,
        "budget_delta": runtime_projection.budget_delta,
        "budget_delta_decimal": runtime_projection.budget_delta_decimal,
        "within_budget": runtime_projection.within_budget,
        "good_event_clause": runtime_projection.good_event_clause,
        "conditionality_clause": runtime_projection.conditionality_clause,
        "maintained_assumptions": runtime_projection.maintained_assumptions,
    }
    values["projection_hash"] = _ledger_content_hash(values)
    return FrozenN9PromotionCertificateProjection.model_validate(values)


def _project_frozen_n12(
    runtime_projection: N12EpochReferenceProjection,
    *,
    ledger: FrozenLedgerReceiptProjection,
) -> FrozenN12EpochReferenceProjection:
    """Project N12 locators without retaining live CAS receipt identities."""

    values: dict[str, Any] = {
        "schema_version": runtime_projection.schema_version,
        "projection_scope": runtime_projection.projection_scope,
        "authority_provenance": runtime_projection.authority_provenance,
        "deployment_identity": runtime_projection.deployment_identity,
        "risk_scope": runtime_projection.risk_scope,
        "scope_id": runtime_projection.scope_id,
        "scope_anchor_ref": runtime_projection.scope_anchor_ref,
        "ledger_projection_hash": ledger.projection_hash,
        "epoch_ref": runtime_projection.epoch_ref,
        "model_ref": runtime_projection.model_ref,
        "rule_ref": runtime_projection.rule_ref,
        "schema_ref": runtime_projection.schema_ref,
        "validity": runtime_projection.validity,
        "conditionality_clause": runtime_projection.conditionality_clause,
        "maintained_assumptions": runtime_projection.maintained_assumptions,
    }
    values["projection_hash"] = _ledger_content_hash(values)
    return FrozenN12EpochReferenceProjection.model_validate(values)


def _accounted_run_projection(values: dict[str, Any]) -> RealAccountedRun:
    """Bind the measured N10/N13b accounting rows as one narrow projection."""

    payload = dict(values)
    payload["projection_hash"] = _ledger_content_hash(payload)
    return RealAccountedRun.model_validate(payload)


def _projection_edges(
    *,
    owner_bundle: OwnerBundleProjection,
    accounted_run: RealAccountedRun,
    real_ledger: FrozenLedgerReceiptProjection,
    n9: FrozenN9PromotionCertificateProjection,
    n12: FrozenN12EpochReferenceProjection,
) -> tuple[ProjectionEdge, ...]:
    """Declare content-bound, acyclic producer-to-consumer projections."""

    if n9.ledger_projection_hash != n12.ledger_projection_hash:
        raise ValueError("projection_ledger_ref_drift")
    return (
        ProjectionEdge(
            producer_scope=owner_bundle.n10.source_projection_scope,
            producer_projection_ref=owner_bundle.n10.source_ref,
            producer_projection_hash=owner_bundle.n10.source_projection_sha256,
            consumer_scope=real_ledger.projection_scope,
            consumer_projection_ref="n11://append-lineage/real-accounting",
            consumer_projection_hash=real_ledger.projection_hash,
        ),
        ProjectionEdge(
            producer_scope=owner_bundle.n13b.source_accounting_projection_scope,
            producer_projection_ref=owner_bundle.n13b.source_ref,
            producer_projection_hash=(owner_bundle.n13b.source_accounting_projection_sha256),
            consumer_scope=real_ledger.projection_scope,
            consumer_projection_ref="n11://append-lineage/real-accounting",
            consumer_projection_hash=real_ledger.projection_hash,
        ),
        ProjectionEdge(
            producer_scope=real_ledger.projection_scope,
            producer_projection_ref="n11://append-lineage/real-accounting",
            producer_projection_hash=real_ledger.projection_hash,
            consumer_scope="n11_accounted_run",
            consumer_projection_ref="n11://accounted-run",
            consumer_projection_hash=accounted_run.projection_hash,
        ),
        ProjectionEdge(
            producer_scope=real_ledger.projection_scope,
            producer_projection_ref="n11://append-lineage/real-accounting",
            producer_projection_hash=real_ledger.projection_hash,
            consumer_scope="n9_promotion_certificate",
            consumer_projection_ref="n11://projection/n9-promotion-certificate",
            consumer_projection_hash=n9.projection_hash,
        ),
        ProjectionEdge(
            producer_scope=real_ledger.projection_scope,
            producer_projection_ref="n11://append-lineage/real-accounting",
            producer_projection_hash=real_ledger.projection_hash,
            consumer_scope="n12_epoch_reference",
            consumer_projection_ref="n11://projection/n12-epoch-reference",
            consumer_projection_hash=n12.projection_hash,
        ),
    )


def _build_unseen_instrument_probe(
    session: ConfidenceLedgerSession,
) -> UnseenInstrumentProbeEvidence:
    """Execute U2 through the ledger and freeze its validated refusal receipt."""

    try:
        session.prepare_check(
            history_token=session.observe_history(),
            request_key="universality://unseen-instrument/frozen",
            obligation_class=PromotionObligationClass.EVAL_SAFETY,
            instrument_id="__n11_unregistered_instrument_probe__",
            certificate_ref="universality://unseen-instrument/certificate",
            claim=PredictableClaimSpec(
                claim_ref="universality://claim/unseen-instrument-is-valid",
                null_ref="universality://null/unseen-instrument-is-invalid",
                claim_scope_ref="universality://scope/unseen-instrument",
                data_window_ref="universality://data-window/no-observations",
                certificate_role="promotion",
                claim_polarity="false_accept",
            ),
        )
    except ConfidenceLedgerError as exc:
        if exc.code != "unknown_instrument":
            raise
    else:  # pragma: no cover - the reserved probe ID must never resolve.
        raise ValueError("unseen_instrument_probe_unexpectedly_prepared")
    receipt = validate_confidence_ledger_receipt(session.receipt(), session=session)
    if len(receipt.events) != 1 or len(receipt.checks) != 1:
        raise ValueError("unseen_instrument_probe_denominator_drift")
    check = receipt.checks[0]
    values: dict[str, Any] = {
        "request_key": check.request_key,
        "instrument_id": check.instrument_id,
        "instrument_family": check.instrument_family,
        "proof_profile_id": check.proof_profile_id,
        "registry_content_hash": check.registry_content_hash,
        "scope_id": receipt.scope_id,
        "scope_anchor_ref": receipt.scope_anchor_ref,
        "request_fingerprint": check.request_fingerprint,
        "refusal_code": check.refusal_code,
        "execution_status": check.execution_status,
        "outcome": check.outcome,
        "event_count": len(receipt.events),
        "check_count": len(receipt.checks),
        "execution_ordinal": check.execution_ordinal,
        "schedule_query_index": check.schedule_query_index,
        "execution_id": check.execution_id,
        "deterministic_proof": check.deterministic_proof,
        "anytime_valid": check.anytime_valid,
        "instrument_definition_hash": check.instrument_definition_hash,
        "proof_profile_hash": check.proof_profile_hash,
        "spend_numerator": check.spend.numerator,
        "spend_denominator": check.spend.denominator,
        "total_spend_numerator": receipt.total_spend.numerator,
        "total_spend_denominator": receipt.total_spend.denominator,
        "total_spend_decimal": receipt.total_spend_decimal,
        "supports_obligation": check.supports_obligation,
        "eligible_for_promotion": check.eligible_for_promotion,
        "within_budget": receipt.within_budget,
    }
    values["projection_hash"] = _ledger_content_hash(values)
    return UnseenInstrumentProbeEvidence.model_validate(values)


def _universality_evidence(
    registry: ConfidenceLedgerRegistry,
    evidence_rows: tuple[AccountedEvidenceRow, ...],
    *,
    unseen_instrument_probe: UnseenInstrumentProbeEvidence,
) -> UniversalityEvidence:
    return UniversalityEvidence(
        registered_instrument_count=len(registry.instruments),
        structurally_distinct_instrument_family_count=len(
            {item.instrument_family for item in registry.instruments}
        ),
        registered_proof_kernel_ids=tuple(
            sorted({item.proof_kernel_id for item in registry.proof_profiles})
        ),
        registered_certificate_route_count=len(registry.certificate_class_routes),
        real_accounted_instrument_ids=tuple(sorted({row.instrument_id for row in evidence_rows})),
        unseen_instrument_probe=unseen_instrument_probe,
    )


def build_live_contract(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
    objective_progress: Callable[[str], None] | None = None,
) -> FrozenConfidenceLedgerContract:
    """Recompute N10/N13b owners and account their narrow projections."""

    def report(milestone: str) -> None:
        if objective_progress is not None:
            objective_progress(milestone)

    root = Path(repo_root).resolve()
    registry = load_confidence_ledger_registry(root / REGISTRY_PATH)
    report("confidence_registry_loaded")
    owner_bundle = load_owner_bundle(
        root,
        catalog_path=Path(catalog_path),
        l5_path=Path(l5_path),
        objective_progress=report,
    )
    report("owner_bundle_loaded")
    owner_routes = _bind_code_owned_owner_certificate_routes(registry)
    for route in owner_bundle.n10.routes:
        if route.witness_kind not in owner_routes:
            raise ValueError(
                f"owner_certificate_contract_missing:{route.witness_kind}"
            )
    evidence_by_ref: dict[str, dict[str, Any]] = {}

    def resolve(check: ConfidenceLedgerCheck) -> OwnerCertificateEvidence:
        certificate_ref = check.certificate_ref
        try:
            payload = evidence_by_ref[certificate_ref]
        except KeyError as exc:
            raise ValueError(f"owner_certificate_missing:{certificate_ref}") from exc
        return OwnerCertificateEvidence(
            **payload,
            claim_execution_binding_hash=check.claim_execution_binding_hash,
        )

    def verify(evidence: OwnerCertificateEvidence) -> OwnerCertificateVerification:
        expected = evidence_by_ref.get(evidence.certificate_ref)
        expected_evidence = (
            OwnerCertificateEvidence(
                **expected,
                claim_execution_binding_hash=evidence.claim_execution_binding_hash,
            )
            if expected is not None
            else None
        )
        if expected_evidence != evidence:
            raise ValueError(f"owner_certificate_drift:{evidence.certificate_ref}")
        if evidence.certificate_class is None:
            raise ValueError("certificate_class_route_missing")
        owner_contract, _certificate_route = owner_routes[evidence.certificate_class]
        if owner_contract.verifier_kernel_id == "n13b_passport_revalidate_v1":
            rows = {
                f"n13b-passport://{row.passport_id}": asdict(row)
                for row in owner_bundle.n13b.passports
            }
        elif owner_contract.verifier_kernel_id == "n10_route_projection_recompute_v1":
            rows = {f"n10-route://{row.route_id}": asdict(row) for row in owner_bundle.n10.routes}
        else:  # pragma: no cover - registry validation owns the finite kernel set.
            raise ValueError("unknown_owner_verifier_kernel")
        if rows.get(evidence.certificate_ref) != evidence.owner_projection:
            raise ValueError(f"owner_projection_recompute_failed:{evidence.certificate_ref}")
        return OwnerCertificateVerification(
            verifier_ref=owner_contract.verifier_ref,
            verifier_projection={
                "owner_bundle_projection_sha256": owner_bundle.projection_sha256,
                "certificate_ref": evidence.certificate_ref,
                "certificate_class": evidence.certificate_class,
                "owner_projection_hash": _ledger_content_hash(evidence.owner_projection),
                "claim_execution_binding_hash": (evidence.claim_execution_binding_hash),
            },
            certificate_evidence_hash=recompute_confidence_owner_evidence_hash(evidence),
            claim_execution_binding_hash=evidence.claim_execution_binding_hash,
            supports_obligation=True,
        )

    evidence_records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="gy-n11-accounted-") as temporary:
        scratch = Path(temporary)
        store = FileSystemCAS(scratch / "cas")
        real_scope = _real_risk_scope(owner_bundle)
        real_session = ConfidenceLedgerSession._for_verification(
            root,
            risk_scope=real_scope,
            artifact_store=store,
            state_root=scratch / "real-state",
            certificate_resolver=resolve,
            certificate_verifier=verify,
        )
        report("n10_evidence_accounting_started")
        for route in owner_bundle.n10.routes:
            certificate_class = route.witness_kind
            owner_contract, certificate_route = owner_routes[certificate_class]
            instrument_id = certificate_route.instrument_id
            obligation_class = owner_contract.obligation_class
            role = owner_contract.certificate_role
            polarity = owner_contract.claim_polarity
            certificate_ref = f"n10-route://{route.route_id}"
            evidence_by_ref[certificate_ref] = {
                "certificate_ref": certificate_ref,
                "instrument_id": instrument_id,
                "obligation_class": obligation_class,
                "certificate_role": role,
                "claim_polarity": polarity,
                "owner_ref": owner_contract.owner_ref,
                "owner_projection": asdict(route),
                "certificate_class": certificate_class,
            }
            prepared = real_session.prepare_check(
                history_token=real_session.observe_history(),
                request_key=f"account://{certificate_ref}",
                obligation_class=obligation_class,
                instrument_id=instrument_id,
                certificate_ref=certificate_ref,
                certificate_class=certificate_class,
                claim=PredictableClaimSpec(
                    claim_ref=f"n10://claim/{route.route_id}/certificate-is-correct",
                    null_ref=f"n10://null/{route.route_id}/certificate-is-wrong",
                    claim_scope_ref=f"n10://route/{route.projection_sha256}",
                    data_window_ref=owner_bundle.n10.source_projection_sha256,
                    certificate_role=role,
                    claim_polarity=polarity,
                ),
            )
            check = real_session.execute_check(prepared)
            if check.owner_binding is None:
                raise ValueError(f"deterministic_owner_binding_missing:{certificate_ref}")
            evidence_records.append(
                {
                    "request_key": check.request_key,
                    "certificate_class": certificate_class,
                    "certificate_ref": certificate_ref,
                    "obligation_class": obligation_class,
                    "instrument_id": instrument_id,
                    "certificate_role": role,
                    "claim_polarity": polarity,
                    "owner_projection_hash": check.owner_binding.owner_projection_hash,
                    "execution_status": "executed",
                    "deterministic_proof": True,
                    "supports_obligation": check.supports_obligation,
                    "eligible_for_promotion": False,
                    "spend_numerator": check.spend.numerator,
                    "spend_denominator": check.spend.denominator,
                }
            )
        report("n10_evidence_accounting_complete")
        report("n13b_passport_accounting_started")
        for passport in owner_bundle.n13b.passports:
            certificate_ref = f"n13b-passport://{passport.passport_id}"
            owner_contract, certificate_route = owner_routes["admission_passport"]
            instrument_id = certificate_route.instrument_id
            evidence_by_ref[certificate_ref] = {
                "certificate_ref": certificate_ref,
                "instrument_id": instrument_id,
                "obligation_class": owner_contract.obligation_class,
                "certificate_role": owner_contract.certificate_role,
                "claim_polarity": owner_contract.claim_polarity,
                "owner_ref": owner_contract.owner_ref,
                "owner_projection": asdict(passport),
                "certificate_class": "admission_passport",
            }
            prepared = real_session.prepare_check(
                history_token=real_session.observe_history(),
                request_key=f"account://{certificate_ref}",
                obligation_class=owner_contract.obligation_class,
                instrument_id=instrument_id,
                certificate_ref=certificate_ref,
                certificate_class="admission_passport",
                claim=PredictableClaimSpec(
                    claim_ref=f"n13b://claim/{passport.passport_id}/admission-is-correct",
                    null_ref=f"n13b://null/{passport.passport_id}/admission-is-wrong",
                    claim_scope_ref=f"n13b://passport/{passport.projection_sha256}",
                    data_window_ref=owner_bundle.n13b.journal_projection_sha256,
                    certificate_role=owner_contract.certificate_role,
                    claim_polarity=owner_contract.claim_polarity,
                ),
            )
            check = real_session.execute_check(prepared)
            if check.owner_binding is None:
                raise ValueError(f"passport_owner_binding_missing:{certificate_ref}")
            evidence_records.append(
                {
                    "request_key": check.request_key,
                    "certificate_class": "admission_passport",
                    "certificate_ref": certificate_ref,
                    "obligation_class": owner_contract.obligation_class,
                    "instrument_id": instrument_id,
                    "certificate_role": owner_contract.certificate_role,
                    "claim_polarity": owner_contract.claim_polarity,
                    "owner_projection_hash": check.owner_binding.owner_projection_hash,
                    "execution_status": "executed",
                    "deterministic_proof": True,
                    "supports_obligation": check.supports_obligation,
                    "eligible_for_promotion": False,
                    "spend_numerator": check.spend.numerator,
                    "spend_denominator": check.spend.denominator,
                }
            )
        report("n13b_passport_accounting_complete")
        real_receipt = validate_confidence_ledger_receipt(
            real_session.receipt(), session=real_session
        )
        report("real_ledger_receipt_validated")
        n9_projection = project_n9_promotion_certificate(real_receipt, session=real_session)
        report("n9_live_projection_validated")
        n12_projection = project_n12_epoch_reference(real_receipt, session=real_session)
        report("n12_live_projection_validated")
        conformance_scope = _conformance_risk_scope(registry)
        report("conformance_ledger_started")
        conformance_session = ConfidenceLedgerSession._for_verification(
            root,
            risk_scope=conformance_scope,
            artifact_store=store,
            state_root=scratch / "conformance-state",
        )
        prepared = conformance_session.prepare_check(
            history_token=conformance_session.observe_history(),
            request_key="conformance://constant-unit-e-process/frozen",
            obligation_class=PromotionObligationClass.EVAL_SAFETY,
            instrument_id="constant_unit_e_process",
            certificate_ref="construction://constant-unit-e-process/n11-frozen",
            claim=PredictableClaimSpec(
                claim_ref="n11://claim/constant-unit-e-process-crosses",
                null_ref="n11://null/constant-unit-e-process",
                claim_scope_ref="n11://conformance/closed-construction",
                data_window_ref="n11://data-window/no-observations",
                certificate_role="promotion_conformance",
                claim_polarity="conformance_only",
            ),
        )
        conformance_check = conformance_session.execute_check(prepared)
        report("conformance_check_executed")
        conformance_receipt = validate_confidence_ledger_receipt(
            conformance_session.receipt(), session=conformance_session
        )
        report("conformance_ledger_receipt_validated")
        unseen_instrument_session = ConfidenceLedgerSession._for_verification(
            root,
            risk_scope=_unseen_instrument_probe_risk_scope(registry),
            artifact_store=store,
            state_root=scratch / "unseen-instrument-state",
            registry_source=registry.source_payload(),
        )
        unseen_instrument_probe = _build_unseen_instrument_probe(unseen_instrument_session)
        report("confidence_ledger_receipts_validated")
        real_ledger_projection = project_confidence_ledger_semantic_receipt(
            real_receipt,
            session=real_session,
            projection_scope="n11_real_accounting_append_lineage",
        )
        report("real_semantic_projection_complete")
        conformance_ledger_projection = project_confidence_ledger_semantic_receipt(
            conformance_receipt,
            session=conformance_session,
            projection_scope="n11_conformance_append_lineage",
        )
        report("conformance_semantic_projection_complete")
    frozen_n9_projection = _project_frozen_n9(
        n9_projection,
        ledger=real_ledger_projection,
    )
    frozen_n12_projection = _project_frozen_n12(
        n12_projection,
        ledger=real_ledger_projection,
    )
    report("frozen_consumer_projections_complete")
    real_checks_by_key = {check.request_key: check for check in real_ledger_projection.checks}
    accounted_rows_list: list[AccountedEvidenceRow] = []
    for record in evidence_records:
        record_values = dict(record)
        request_key = str(record_values.pop("request_key"))
        try:
            projected_check = real_checks_by_key[request_key]
        except KeyError as exc:
            raise ValueError("accounted_check_projection_missing") from exc
        if projected_check.execution_ordinal is None:
            raise ValueError("accounted_check_execution_ordinal_missing")
        accounted_rows_list.append(
            AccountedEvidenceRow(
                **record_values,
                check_projection_hash=projected_check.check_projection_hash,
                claim_execution_projection_hash=(projected_check.claim_execution_projection_hash),
                execution_ordinal=projected_check.execution_ordinal,
            )
        )
    accounted_rows = tuple(accounted_rows_list)
    try:
        conformance_projected_check = next(
            check
            for check in conformance_ledger_projection.checks
            if check.request_key == "conformance://constant-unit-e-process/frozen"
        )
    except StopIteration as exc:
        raise ValueError("conformance_check_projection_missing") from exc
    if conformance_projected_check.execution_ordinal is None:
        raise ValueError("conformance_check_execution_ordinal_missing")
    owner_projection = OwnerBundleProjection(
        projection_sha256=owner_bundle.projection_sha256,
        n10=owner_bundle.n10,
        n13b=owner_bundle.n13b,
    )
    accounted_run = _accounted_run_projection(
        {
            "n10_route_count": owner_bundle.n10.route_count,
            "owner_acquisition_route_count": (owner_bundle.n10.owner_acquisition_route_count),
            "estimand_binding_refusal_count": (owner_bundle.n10.estimand_binding_refusal_count),
            "owner_data_gap_count": owner_bundle.n10.owner_data_gap_count,
            "n13b_attempt_count": owner_bundle.n13b.live_attempt_count,
            "n13b_raw_response_count": owner_bundle.n13b.raw_response_count,
            "n13b_admission_count": owner_bundle.n13b.response_admitted_count,
            "n13b_passport_count": owner_bundle.n13b.passport_count,
            "evidence_rows": accounted_rows,
            "total_spend_numerator": real_receipt.total_spend.numerator,
            "total_spend_denominator": real_receipt.total_spend.denominator,
            "total_spend_decimal": real_receipt.total_spend_decimal,
        }
    )
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "layer3-gy-n11-honest-confidence-ledger",
        "owner": ("polisyos.runtime.quality.confidence_ledger.ConfidenceLedgerSession"),
        "registry_content_hash": registry.content_hash,
        "registry_projection": _build_registry_projection(registry),
        "owner_bundle_projection": owner_projection,
        "accounted_run": accounted_run,
        "conformance_run": ConformanceAccountedRun(
            instrument_id=conformance_check.instrument_id,
            certificate_role="promotion_conformance",
            claim_polarity="conformance_only",
            check_projection_hash=conformance_projected_check.check_projection_hash,
            claim_execution_projection_hash=(
                conformance_projected_check.claim_execution_projection_hash
            ),
            execution_ordinal=conformance_projected_check.execution_ordinal,
            anytime_valid=True,
            supports_obligation=False,
            eligible_for_promotion=False,
            total_spend_numerator=conformance_receipt.total_spend.numerator,
            total_spend_denominator=conformance_receipt.total_spend.denominator,
            total_spend_decimal=conformance_receipt.total_spend_decimal,
        ),
        "real_ledger_projection": real_ledger_projection,
        "conformance_ledger_projection": conformance_ledger_projection,
        "n9_promotion_projection": frozen_n9_projection,
        "n12_epoch_reference_projection": frozen_n12_projection,
        "projection_edges": _projection_edges(
            owner_bundle=owner_projection,
            accounted_run=accounted_run,
            real_ledger=real_ledger_projection,
            n9=frozen_n9_projection,
            n12=frozen_n12_projection,
        ),
        "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,
        "maintained_assumptions": (
            "obligation_completeness",
            "validator_soundness",
        ),
        "universality": _universality_evidence(
            registry,
            accounted_rows,
            unseen_instrument_probe=unseen_instrument_probe,
        ),
    }
    contract = FrozenConfidenceLedgerContract(
        **payload,
        artifact_content_hash="sha256:" + "0" * 64,
    )
    artifact_hash = gy_content_hash(
        contract.model_dump(mode="json", exclude={"artifact_content_hash"})
    )
    report("frozen_contract_derived")
    return contract.model_copy(update={"artifact_content_hash": artifact_hash})


def contract_bytes(contract: FrozenConfidenceLedgerContract) -> bytes:
    """Return canonical, byte-stable writer output."""

    return (
        json.dumps(
            contract.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _ledger_content_hash(payload: object) -> str:
    def jsonable(value: object) -> object:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(key): jsonable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [jsonable(item) for item in value]
        return value

    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                jsonable(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )


def _validate_registry_projection(
    projection: RegistryProjection,
    *,
    artifact_registry_hash: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        registry = ConfidenceLedgerRegistry(
            schema_version=projection.registry_schema_version,
            policy=projection.policy,
            schedule_profiles=projection.schedule_profiles,
            obligation_pools=projection.obligation_pools,
            proof_profiles=projection.proof_profiles,
            instruments=projection.instruments,
            certificate_class_routes=projection.certificate_class_routes,
        )
        expected = _build_registry_projection(registry)
    except (ValidationError, ValueError) as exc:
        return [{"code": "registry_projection_invalid", "error": str(exc)}]
    if projection != expected:
        issues.append({"code": "registry_projection_recomputation_drift"})
    if registry.content_hash != artifact_registry_hash:
        issues.append({"code": "registry_projection_content_hash_drift"})
    return issues


def _projection_edges_are_acyclic(edges: tuple[ProjectionEdge, ...]) -> bool:
    adjacency: dict[str, set[str]] = {}
    nodes: set[str] = set()
    for edge in edges:
        adjacency.setdefault(edge.producer_scope, set()).add(edge.consumer_scope)
        nodes.update((edge.producer_scope, edge.consumer_scope))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for child in adjacency.get(node, set()):
            if not visit(child):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    return all(visit(node) for node in nodes)


def _validate_projection_edges(
    edges: tuple[ProjectionEdge, ...],
    *,
    owner_bundle: OwnerBundleProjection,
    accounted_run: RealAccountedRun,
    real_ledger: FrozenLedgerReceiptProjection,
    n9: FrozenN9PromotionCertificateProjection,
    n12: FrozenN12EpochReferenceProjection,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    actual = tuple((edge.producer_scope, edge.consumer_scope) for edge in edges)
    try:
        expected = _projection_edges(
            owner_bundle=owner_bundle,
            accounted_run=accounted_run,
            real_ledger=real_ledger,
            n9=n9,
            n12=n12,
        )
    except ValueError as exc:
        issues.append({"code": "projection_edge_owner_invalid", "error": str(exc)})
        expected = ()
    if edges != expected:
        issues.append({"code": "projection_edge_binding_drift"})
    if len(actual) != len(set(actual)):
        issues.append({"code": "duplicate_projection_edge"})
    if not _projection_edges_are_acyclic(edges):
        issues.append({"code": "projection_edge_cycle"})
    return issues


def _validate_owner_bundle_projection(
    projection: OwnerBundleProjection,
) -> list[dict[str, Any]]:
    from polisyos.fabric.data_plane import content_sha256

    issues: list[dict[str, Any]] = []
    n10 = projection.n10
    n13b = projection.n13b
    for route in n10.routes:
        values = asdict(route)
        recorded = values.pop("projection_sha256")
        if recorded != content_sha256(values):
            issues.append({"code": "n10_route_projection_hash_drift"})
    n10_values = asdict(n10)
    n10_hash = n10_values.pop("projection_sha256")
    if n10_hash != content_sha256(n10_values):
        issues.append({"code": "n10_owner_projection_hash_drift"})
    if n10.route_count != len(n10.routes):
        issues.append({"code": "n10_route_denominator_drift"})
    witness_counts: dict[str, int] = {}
    for route in n10.routes:
        witness_counts[route.witness_kind] = witness_counts.get(route.witness_kind, 0) + 1
    if n10.witness_kind_counts != tuple(sorted(witness_counts.items())):
        issues.append({"code": "n10_witness_kind_count_drift"})

    # Attempt hashes are N13b-owner hashes over its richer journal projection;
    # N11 carries them as opaque owner bindings.  The N13b aggregate below is
    # recomputed over every field N11 actually projects.
    for passport in n13b.passports:
        values = asdict(passport)
        recorded = values.pop("projection_sha256")
        if recorded != content_sha256(values):
            issues.append({"code": "n13b_passport_projection_hash_drift"})
    n13b_values = asdict(n13b)
    n13b_hash = n13b_values.pop("projection_sha256")
    if n13b_hash != content_sha256(n13b_values):
        issues.append({"code": "n13b_owner_projection_hash_drift"})
    if n13b.live_attempt_count != len(n13b.attempts):
        issues.append({"code": "n13b_attempt_denominator_drift"})
    if n13b.passport_count != len(n13b.passports):
        issues.append({"code": "n13b_passport_denominator_drift"})
    if n13b.response_admitted_count != n13b.passport_count:
        issues.append({"code": "n13b_admission_passport_drift"})
    bundle_values = {"n10": asdict(n10), "n13b": asdict(n13b)}
    if projection.projection_sha256 != content_sha256(bundle_values):
        issues.append({"code": "owner_bundle_projection_hash_drift"})
    return issues


def _validate_unseen_instrument_probe(
    probe: UnseenInstrumentProbeEvidence,
    *,
    registry: ConfidenceLedgerRegistry,
) -> list[dict[str, Any]]:
    """Recompute the U2 absence, predictable request, scope, and projection binding."""

    issues: list[dict[str, Any]] = []
    values = probe.model_dump(mode="json", exclude={"projection_hash"})
    if probe.projection_hash != _ledger_content_hash(values):
        issues.append({"code": "unseen_instrument_probe_projection_hash_drift"})
    try:
        registry.resolve_instrument(probe.instrument_id)
    except ConfidenceLedgerError as exc:
        if exc.code != "unknown_instrument":
            issues.append({"code": "unseen_instrument_probe_resolution_drift"})
    else:
        issues.append({"code": "unseen_instrument_probe_unexpectedly_registered"})
    risk_scope = _unseen_instrument_probe_risk_scope(registry)
    if (
        probe.registry_content_hash != registry.content_hash
        or probe.scope_id != risk_scope.scope_id
        or probe.scope_anchor_ref != recompute_confidence_scope_anchor_ref(risk_scope)
    ):
        issues.append({"code": "unseen_instrument_probe_scope_binding_drift"})
    expected_fingerprint = _ledger_content_hash(
        {
            "request_key": "universality://unseen-instrument/frozen",
            "obligation_class": PromotionObligationClass.EVAL_SAFETY,
            "instrument_id": "__n11_unregistered_instrument_probe__",
            "certificate_ref": "universality://unseen-instrument/certificate",
            "certificate_class": None,
            "claim": {
                "claim_ref": "universality://claim/unseen-instrument-is-valid",
                "null_ref": "universality://null/unseen-instrument-is-invalid",
                "claim_scope_ref": "universality://scope/unseen-instrument",
                "data_window_ref": "universality://data-window/no-observations",
                "certificate_role": "promotion",
                "claim_polarity": "false_accept",
            },
        }
    )
    if probe.request_fingerprint != expected_fingerprint:
        issues.append({"code": "unseen_instrument_probe_request_binding_drift"})
    return issues


def _validate_frozen_check_projection(
    check: FrozenLedgerCheckProjection,
    *,
    registry: ConfidenceLedgerRegistry,
) -> list[dict[str, Any]]:
    """Recompute stable request, draw, registry, and owner bindings."""

    issues: list[dict[str, Any]] = []
    values = check.model_dump(mode="json", exclude={"check_projection_hash"})
    if check.check_projection_hash != _ledger_content_hash(values):
        issues.append({"code": "semantic_check_projection_hash_drift"})
    claim_values = {
        "scope_id": check.scope_id,
        "request_fingerprint": check.request_fingerprint,
        "claim_ref": check.claim_ref,
        "null_ref": check.null_ref,
        "claim_scope_ref": check.claim_scope_ref,
        "data_window_ref": check.data_window_ref,
        "filtration_projection_hash": check.filtration_projection_hash,
        "certificate_role": check.certificate_role,
        "claim_polarity": check.claim_polarity,
        "execution_id": check.execution_id,
        "execution_ordinal": check.execution_ordinal,
        "schedule_query_index": check.schedule_query_index,
        "reserved_alpha": check.spend,
        "registry_content_hash": check.registry_content_hash,
        "instrument_definition_hash": check.instrument_definition_hash,
        "proof_profile_hash": check.proof_profile_hash,
    }
    if check.claim_execution_projection_hash != _ledger_content_hash(claim_values):
        issues.append({"code": "semantic_claim_execution_binding_drift"})
    request_fingerprint = _ledger_content_hash(
        {
            "request_key": check.request_key,
            "obligation_class": check.obligation_class,
            "instrument_id": check.instrument_id,
            "certificate_ref": check.certificate_ref,
            "certificate_class": check.certificate_class,
            "claim": {
                "claim_ref": check.claim_ref,
                "null_ref": check.null_ref,
                "claim_scope_ref": check.claim_scope_ref,
                "data_window_ref": check.data_window_ref,
                "certificate_role": check.certificate_role,
                "claim_polarity": check.claim_polarity,
            },
        }
    )
    if check.request_fingerprint != request_fingerprint:
        issues.append({"code": "semantic_request_fingerprint_drift"})
    try:
        instrument = registry.resolve_instrument(check.instrument_id)
        profile = registry.resolve_proof_profile(check.proof_profile_id)
    except ConfidenceLedgerError as exc:
        return [*issues, {"code": "semantic_registry_resolution_failed", "error": exc.code}]
    if (
        check.instrument_family != instrument.instrument_family
        or check.proof_profile_id != instrument.proof_profile_id
        or check.instrument_definition_hash != _ledger_content_hash(instrument)
        or check.proof_profile_hash != _ledger_content_hash(profile)
        or check.deterministic_proof is not profile.deterministic
        or check.anytime_valid is not profile.anytime_valid
    ):
        issues.append({"code": "semantic_instrument_binding_drift"})
    if check.certificate_class is None:
        if check.certificate_route_hash is not None or check.owner_binding is not None:
            issues.append({"code": "semantic_certificate_route_binding_drift"})
    else:
        try:
            route = registry.resolve_certificate_route(check.certificate_class)
        except ConfidenceLedgerError as exc:
            issues.append({"code": "semantic_certificate_route_missing", "error": exc.code})
        else:
            if (
                route.instrument_id != check.instrument_id
                or route.obligation_class != check.obligation_class
                or route.certificate_role != check.certificate_role
                or route.claim_polarity != check.claim_polarity
                or check.certificate_route_hash != _ledger_content_hash(route)
            ):
                issues.append({"code": "semantic_certificate_route_binding_drift"})
    binding = check.owner_binding
    if binding is not None:
        binding_values = binding.model_dump(
            mode="json",
            exclude={"binding_projection_hash"},
        )
        if binding.binding_projection_hash != _ledger_content_hash(binding_values):
            issues.append({"code": "semantic_owner_verification_hash_drift"})
        if (
            binding.certificate_ref != check.certificate_ref
            or binding.certificate_class != check.certificate_class
            or binding.certificate_route_hash != check.certificate_route_hash
        ):
            issues.append({"code": "semantic_owner_binding_drift"})
    expected_invocation_claim = (
        _ledger_content_hash(
            {
                "scope_id": check.scope_id,
                "request_fingerprint": check.request_fingerprint,
                "execution_id": check.execution_id,
                "execution_ordinal": check.execution_ordinal,
                "schedule_query_index": check.schedule_query_index,
                "owner_invocation_claimed": True,
            }
        )
        if check.owner_invocation_claim_projection_hash is not None
        else None
    )
    if check.owner_invocation_claim_projection_hash != expected_invocation_claim:
        issues.append({"code": "semantic_owner_invocation_claim_drift"})
    if (
        check.outcome in {"supported", "not_supported", "owner_refused", "owner_error", "refused"}
        and check.owner_invocation_claim_projection_hash is None
    ):
        issues.append({"code": "semantic_owner_invocation_claim_missing"})
    expected_good_event = None
    if (
        not check.deterministic_proof
        and check.execution_ordinal is not None
        and check.outcome
        not in {
            "prepared",
            "started",
        }
    ):
        expected_good_event = "confidence-good-event:" + _ledger_content_hash(
            {
                "execution_id": check.execution_id,
                "spend": check.spend,
                "protected_error": check.claim_polarity,
            }
        )
    if check.good_event_id != expected_good_event:
        issues.append({"code": "semantic_good_event_binding_drift"})
    if check.spend_decimal != _ledger_fraction_display(check.spend.fraction):
        issues.append({"code": "semantic_spend_decimal_drift"})
    if check.deterministic_proof and check.spend.fraction != 0:
        issues.append({"code": "semantic_deterministic_spend_nonzero"})
    if (check.execution_ordinal is None) != (check.schedule_query_index is None):
        issues.append({"code": "semantic_schedule_identity_incomplete"})
    if (check.execution_ordinal is None) != (check.execution_id is None):
        issues.append({"code": "semantic_execution_identity_incomplete"})
    if check.eligible_for_promotion and not (
        check.execution_status == "executed"
        and check.outcome == "supported"
        and check.anytime_valid
        and check.supports_obligation
        and check.certificate_role == "promotion"
        and check.claim_polarity == "false_accept"
    ):
        issues.append({"code": "semantic_ineligible_check_marked_promotable"})
    return issues


def _validate_frozen_ledger_projection(
    projection: FrozenLedgerReceiptProjection,
    *,
    registry: ConfidenceLedgerRegistry,
) -> list[dict[str, Any]]:
    """Recompute semantic lineage and the predictable spend law."""

    issues: list[dict[str, Any]] = []
    root_values = _frozen_ledger_root_values(
        receipt=projection,
        risk_scope=projection.risk_scope,
        projection_scope=projection.projection_scope,
    )
    expected_root = _ledger_content_hash(root_values)
    if projection.root_projection_hash != expected_root:
        issues.append({"code": "semantic_ledger_root_hash_drift"})
    head = expected_root
    filtrations: dict[str, str] = {}
    current: dict[str, FrozenLedgerCheckProjection] = {}
    previous_checks: dict[str, FrozenLedgerCheckProjection] = {}
    for expected_revision, event in enumerate(projection.events, start=1):
        if event.revision != expected_revision:
            issues.append({"code": "semantic_event_revision_drift"})
        if event.parent_event_projection_hash != head:
            issues.append({"code": "semantic_event_parent_drift"})
        request_key = event.check.request_key
        if event.check.scope_id != projection.scope_id:
            issues.append({"code": "semantic_check_scope_drift"})
        expected_event_type = (
            "prepared"
            if event.check.outcome == "prepared"
            else "started"
            if event.check.outcome == "started"
            else "completed"
        )
        if event.event_type != expected_event_type:
            issues.append({"code": "semantic_transition_type_drift"})
        if event.event_type == "prepared" or (
            request_key not in filtrations and event.check.outcome == "preflight_refusal"
        ):
            if request_key in filtrations:
                issues.append({"code": "semantic_duplicate_preparation"})
            filtrations[request_key] = head
        expected_filtration = filtrations.get(request_key)
        if expected_filtration is None:
            issues.append({"code": "semantic_preparation_missing"})
        elif event.check.filtration_projection_hash != expected_filtration:
            issues.append({"code": "semantic_filtration_binding_drift"})
        previous = previous_checks.get(request_key)
        if previous is None:
            if event.check.outcome not in {"prepared", "preflight_refusal"}:
                issues.append({"code": "semantic_started_without_preparation"})
        else:
            immutable_fields = (
                "scope_id",
                "request_key",
                "request_fingerprint",
                "obligation_class",
                "instrument_id",
                "instrument_family",
                "proof_profile_id",
                "certificate_ref",
                "certificate_class",
                "certificate_route_hash",
                "certificate_role",
                "claim_polarity",
                "claim_ref",
                "null_ref",
                "claim_scope_ref",
                "data_window_ref",
                "filtration_projection_hash",
                "registry_content_hash",
                "instrument_definition_hash",
                "proof_profile_hash",
                "deterministic_proof",
                "anytime_valid",
            )
            if any(
                getattr(previous, field) != getattr(event.check, field)
                for field in immutable_fields
            ):
                issues.append({"code": "semantic_prepared_binding_changed"})
            allowed = {
                ("prepared", "started"),
                ("prepared", "cancelled"),
                ("started", "started"),
                ("started", "supported"),
                ("started", "not_supported"),
                ("started", "owner_refused"),
                ("started", "owner_error"),
                ("started", "recovered_crash"),
                ("started", "refused"),
            }
            if (previous.outcome, event.check.outcome) not in allowed:
                issues.append({"code": "semantic_transition_invalid"})
            if previous.outcome == "started":
                started_fields = (
                    "execution_ordinal",
                    "schedule_query_index",
                    "execution_id",
                    "spend",
                    "spend_decimal",
                    "claim_execution_projection_hash",
                )
                if any(
                    getattr(previous, field) != getattr(event.check, field)
                    for field in started_fields
                ):
                    issues.append({"code": "semantic_started_binding_changed"})
                if event.check.outcome == "started" and (
                    previous.owner_invocation_claim_projection_hash is not None
                    or event.check.owner_invocation_claim_projection_hash is None
                ):
                    issues.append({"code": "semantic_invocation_claim_transition_invalid"})
                if (
                    event.check.outcome not in {"started", "recovered_crash"}
                    and previous.owner_invocation_claim_projection_hash is None
                ):
                    issues.append({"code": "semantic_invocation_claim_missing"})
        issues.extend(_validate_frozen_check_projection(event.check, registry=registry))
        event_values = event.model_dump(mode="json", exclude={"event_projection_hash"})
        if event.event_projection_hash != _ledger_content_hash(event_values):
            issues.append({"code": "semantic_event_projection_hash_drift"})
        head = event.event_projection_hash
        current[request_key] = event.check
        previous_checks[request_key] = event.check
    if projection.head_event_projection_hash != head:
        issues.append({"code": "semantic_ledger_head_drift"})
    expected_checks = tuple(current[key] for key in sorted(current))
    if projection.checks != expected_checks:
        issues.append({"code": "semantic_current_check_projection_drift"})
    for check in projection.checks:
        issues.extend(_validate_frozen_check_projection(check, registry=registry))
    ordinals = [
        check.execution_ordinal
        for check in projection.checks
        if check.execution_ordinal is not None
    ]
    if sorted(ordinals) != list(range(len(ordinals))):
        issues.append({"code": "semantic_schedule_slot_sequence_drift"})
    schedule = registry.resolve_schedule(projection.schedule_profile_id)
    if (
        projection.registry_content_hash != registry.content_hash
        or projection.schedule_profile_hash != _ledger_content_hash(schedule)
        or projection.schedule_projection_hash
        != recompute_confidence_schedule_projection_hash(
            registry,
            schedule_profile_id=schedule.profile_id,
        )
    ):
        issues.append({"code": "semantic_schedule_projection_binding_drift"})
    recomputed_total = Fraction()
    for check in projection.checks:
        if check.execution_ordinal is None:
            if check.spend.fraction != 0:
                issues.append({"code": "semantic_unexecuted_spend"})
            continue
        if check.schedule_query_index != check.execution_ordinal:
            issues.append({"code": "semantic_schedule_slot_missing"})
            continue
        profile = registry.resolve_proof_profile(check.proof_profile_id)
        expected_spend = Fraction()
        if not profile.deterministic:
            expected_spend = (
                registry.policy.delta.fraction
                * registry.obligation_weights[check.obligation_class]
                * schedule.mass.fraction
                * _BASEL_COEFFICIENT_LOWER
                / ((check.schedule_query_index + 1) ** 2)
            )
        if check.spend.fraction != expected_spend:
            issues.append({"code": "semantic_forged_spend_row"})
        recomputed_total += check.spend.fraction
    if projection.total_spend.fraction != recomputed_total:
        issues.append({"code": "semantic_total_spend_drift"})
    if projection.total_spend_decimal != _ledger_fraction_display(recomputed_total):
        issues.append({"code": "semantic_total_spend_decimal_drift"})
    if projection.budget_delta != registry.policy.delta:
        issues.append({"code": "semantic_budget_delta_drift"})
    if projection.within_budget is not (recomputed_total <= registry.policy.delta.fraction):
        issues.append({"code": "semantic_budget_status_drift"})
    projection_values = projection.model_dump(mode="json", exclude={"projection_hash"})
    if projection.projection_hash != _ledger_content_hash(projection_values):
        issues.append({"code": "semantic_ledger_projection_hash_drift"})
    return issues


def _expected_frozen_n9_rows(
    ledger: FrozenLedgerReceiptProjection,
) -> tuple[FrozenN9PromotionLedgerRow, ...]:
    """Recompute N9's promotion-role rows from the semantic ledger owner."""

    return tuple(
        FrozenN9PromotionLedgerRow(
            obligation_class=check.obligation_class,
            instrument_id=check.instrument_id,
            instrument_family=check.instrument_family,
            certificate_ref=check.certificate_ref,
            certificate_role="promotion",
            claim_polarity="false_accept",
            check_projection_hash=check.check_projection_hash,
            execution_status=check.execution_status,
            outcome=check.outcome,
            execution_ordinal=check.execution_ordinal,
            execution_id=check.execution_id,
            spend=check.spend,
            spend_decimal=check.spend_decimal,
            anytime_valid=check.anytime_valid,
            supports_obligation=check.supports_obligation,
            eligible_for_promotion=check.eligible_for_promotion,
            claim_execution_projection_hash=check.claim_execution_projection_hash,
        )
        for check in ledger.checks
        if check.certificate_role == "promotion" and check.claim_polarity == "false_accept"
    )


def _validate_projection_authority(
    contract: FrozenConfidenceLedgerContract,
) -> list[dict[str, Any]]:
    """Recompute scope anchors and bind each sibling projection to its root."""

    issues: list[dict[str, Any]] = []
    try:
        registry = ConfidenceLedgerRegistry(
            schema_version=contract.registry_projection.registry_schema_version,
            policy=contract.registry_projection.policy,
            schedule_profiles=contract.registry_projection.schedule_profiles,
            obligation_pools=contract.registry_projection.obligation_pools,
            proof_profiles=contract.registry_projection.proof_profiles,
            instruments=contract.registry_projection.instruments,
            certificate_class_routes=contract.registry_projection.certificate_class_routes,
        )
        real_scope = _real_risk_scope(contract.owner_bundle_projection)
        conformance_scope = _conformance_risk_scope(registry)
    except (ValidationError, ValueError) as exc:
        return [{"code": "projection_authority_recomputation_failed", "error": str(exc)}]
    real = contract.real_ledger_projection
    conformance = contract.conformance_ledger_projection
    n9 = contract.n9_promotion_projection
    n12 = contract.n12_epoch_reference_projection
    real_anchor = recompute_confidence_scope_anchor_ref(real_scope)
    conformance_anchor = recompute_confidence_scope_anchor_ref(conformance_scope)
    if (
        real.projection_scope != "n11_real_accounting_append_lineage"
        or real.risk_scope != real_scope
        or conformance.projection_scope != "n11_conformance_append_lineage"
        or conformance.risk_scope != conformance_scope
    ):
        issues.append({"code": "semantic_projection_scope_authority_drift"})
    if (
        real.scope_id != real_scope.scope_id
        or real.scope_anchor_ref != real_anchor
        or n9.risk_scope != real_scope
        or n9.scope_id != real_scope.scope_id
        or n9.scope_anchor_ref != real_anchor
        or n12.risk_scope != real_scope
        or n12.scope_id != real_scope.scope_id
        or n12.scope_anchor_ref != real_anchor
    ):
        issues.append({"code": "real_scope_anchor_binding_drift"})
    if (
        conformance.scope_id != conformance_scope.scope_id
        or conformance.scope_anchor_ref != conformance_anchor
    ):
        issues.append({"code": "conformance_scope_anchor_binding_drift"})
    if any(
        provenance != "verification"
        for provenance in (
            real.authority_provenance,
            conformance.authority_provenance,
            n9.authority_provenance,
            n12.authority_provenance,
        )
    ):
        issues.append({"code": "frozen_authority_provenance_drift"})
    if (
        len(
            {
                real.deployment_identity,
                conformance.deployment_identity,
                n9.deployment_identity,
                n12.deployment_identity,
            }
        )
        != 1
    ):
        issues.append({"code": "projection_deployment_identity_drift"})
    if (
        n12.epoch_ref != n12.risk_scope.epoch_ref
        or n12.model_ref != n12.risk_scope.model_ref
        or n12.rule_ref != n12.risk_scope.rule_ref
        or n12.schema_ref != n12.risk_scope.schema_ref
    ):
        issues.append({"code": "n12_risk_scope_locator_drift"})
    return issues


def validate_payload(
    payload: object,
    *,
    expected: FrozenConfidenceLedgerContract | None = None,
) -> dict[str, Any]:
    """Validate structure, self-hash, projections, and optional owner replay."""

    issues: list[dict[str, Any]] = []
    try:
        parsed = FrozenConfidenceLedgerContract.model_validate(payload)
    except ValidationError as exc:
        return {"status": "fail", "issues": [{"code": "schema_invalid", "error": str(exc)}]}
    source = parsed.model_dump(mode="json", exclude={"artifact_content_hash"})
    if parsed.artifact_content_hash != gy_content_hash(source):
        issues.append({"code": "artifact_content_hash_drift"})
    issues.extend(
        _validate_registry_projection(
            parsed.registry_projection,
            artifact_registry_hash=parsed.registry_content_hash,
        )
    )
    issues.extend(_validate_owner_bundle_projection(parsed.owner_bundle_projection))
    try:
        projected_registry = ConfidenceLedgerRegistry(
            schema_version=parsed.registry_projection.registry_schema_version,
            policy=parsed.registry_projection.policy,
            schedule_profiles=parsed.registry_projection.schedule_profiles,
            obligation_pools=parsed.registry_projection.obligation_pools,
            proof_profiles=parsed.registry_projection.proof_profiles,
            instruments=parsed.registry_projection.instruments,
            certificate_class_routes=parsed.registry_projection.certificate_class_routes,
        )
    except (ValidationError, ValueError) as exc:
        projected_registry = None
        issues.append({"code": "semantic_registry_invalid", "error": str(exc)})
    if projected_registry is not None:
        issues.extend(
            _validate_frozen_ledger_projection(
                parsed.real_ledger_projection,
                registry=projected_registry,
            )
        )
        issues.extend(
            _validate_frozen_ledger_projection(
                parsed.conformance_ledger_projection,
                registry=projected_registry,
            )
        )
        issues.extend(
            _validate_unseen_instrument_probe(
                parsed.universality.unseen_instrument_probe,
                registry=projected_registry,
            )
        )
    accounted_values = parsed.accounted_run.model_dump(
        mode="json",
        exclude={"projection_hash"},
    )
    if parsed.accounted_run.projection_hash != _ledger_content_hash(accounted_values):
        issues.append({"code": "accounted_run_projection_hash_drift"})
    issues.extend(
        _validate_projection_edges(
            parsed.projection_edges,
            owner_bundle=parsed.owner_bundle_projection,
            accounted_run=parsed.accounted_run,
            real_ledger=parsed.real_ledger_projection,
            n9=parsed.n9_promotion_projection,
            n12=parsed.n12_epoch_reference_projection,
        )
    )
    issues.extend(_validate_projection_authority(parsed))
    if parsed.conditionality_clause != CONDITIONAL_VALIDITY_CLAUSE:
        issues.append({"code": "conditionality_clause_missing"})
    clauses = (
        parsed.real_ledger_projection.conditionality_clause,
        parsed.conformance_ledger_projection.conditionality_clause,
        parsed.n9_promotion_projection.conditionality_clause,
        parsed.n12_epoch_reference_projection.conditionality_clause,
    )
    if any(clause != CONDITIONAL_VALIDITY_CLAUSE for clause in clauses):
        issues.append({"code": "projection_conditionality_drift"})
    assumptions = (
        parsed.maintained_assumptions,
        parsed.real_ledger_projection.maintained_assumptions,
        parsed.conformance_ledger_projection.maintained_assumptions,
        parsed.n9_promotion_projection.maintained_assumptions,
        parsed.n12_epoch_reference_projection.maintained_assumptions,
    )
    if any(item != ("obligation_completeness", "validator_soundness") for item in assumptions):
        issues.append({"code": "maintained_assumptions_drift"})
    if parsed.accounted_run.n10_route_count + parsed.accounted_run.n13b_passport_count != len(
        parsed.accounted_run.evidence_rows
    ):
        issues.append({"code": "real_accounted_denominator_drift"})
    if parsed.accounted_run.n13b_admission_count != parsed.accounted_run.n13b_passport_count:
        issues.append({"code": "admission_passport_denominator_drift"})
    real_total = parsed.real_ledger_projection.total_spend.fraction
    if (
        real_total != 0
        or parsed.accounted_run.total_spend_numerator != 0
        or parsed.accounted_run.total_spend_decimal != "0"
        or any(row.spend_numerator != 0 for row in parsed.accounted_run.evidence_rows)
    ):
        issues.append({"code": "deterministic_real_run_spend_nonzero"})
    if any(
        not row.deterministic_proof or not row.supports_obligation or row.eligible_for_promotion
        for row in parsed.accounted_run.evidence_rows
    ):
        issues.append({"code": "real_accounting_semantics_drift"})
    conformance_total = parsed.conformance_ledger_projection.total_spend.fraction
    if (
        conformance_total <= 0
        or parsed.conformance_run.total_spend_numerator
        * parsed.conformance_ledger_projection.total_spend.denominator
        != parsed.conformance_ledger_projection.total_spend.numerator
        * parsed.conformance_run.total_spend_denominator
    ):
        issues.append({"code": "conformance_spend_drift"})
    if parsed.n9_promotion_projection.promotion_rows:
        issues.append({"code": "day_one_positive_promotion_fabricated"})
    registry_hashes = {
        parsed.registry_content_hash,
        parsed.registry_projection.registry_content_hash,
        parsed.real_ledger_projection.registry_content_hash,
        parsed.conformance_ledger_projection.registry_content_hash,
        parsed.n9_promotion_projection.registry_content_hash,
        parsed.universality.unseen_instrument_probe.registry_content_hash,
    }
    if len(registry_hashes) != 1:
        issues.append({"code": "registry_projection_binding_drift"})
    real = parsed.real_ledger_projection
    n9 = parsed.n9_promotion_projection
    n12 = parsed.n12_epoch_reference_projection
    if (
        n9.scope_id != real.scope_id
        or n9.scope_anchor_ref != real.scope_anchor_ref
        or n9.ledger_projection_hash != real.projection_hash
        or n9.registry_content_hash != real.registry_content_hash
        or n9.schedule_projection_hash != real.schedule_projection_hash
        or n9.promotion_rows != _expected_frozen_n9_rows(real)
        or n9.total_spend != real.total_spend
        or n9.budget_delta != real.budget_delta
        or n9.within_budget is not real.within_budget
    ):
        issues.append({"code": "n9_projection_owner_binding_drift"})
    if (
        n12.scope_id != real.scope_id
        or n12.scope_anchor_ref != real.scope_anchor_ref
        or n12.ledger_projection_hash != real.projection_hash
        or n12.epoch_ref != n12.risk_scope.epoch_ref
        or n12.model_ref != n12.risk_scope.model_ref
        or n12.rule_ref != n12.risk_scope.rule_ref
        or n12.schema_ref != n12.risk_scope.schema_ref
    ):
        issues.append({"code": "n12_projection_owner_binding_drift"})
    for projection in (n9, n12):
        projection_payload = projection.model_dump(mode="json", exclude={"projection_hash"})
        if projection.projection_hash != _ledger_content_hash(projection_payload):
            issues.append({"code": "projection_hash_drift"})
    owner_n10 = {
        f"n10-route://{row.route_id}": asdict(row)
        for row in parsed.owner_bundle_projection.n10.routes
    }
    owner_n13b = {
        f"n13b-passport://{row.passport_id}": asdict(row)
        for row in parsed.owner_bundle_projection.n13b.passports
    }
    for row in parsed.accounted_run.evidence_rows:
        owner_projection = owner_n13b.get(row.certificate_ref) or owner_n10.get(row.certificate_ref)
        if owner_projection is None or row.owner_projection_hash != _ledger_content_hash(
            owner_projection
        ):
            issues.append({"code": "accounted_owner_projection_drift"})
    if projected_registry is not None:
        real_checks = {check.check_projection_hash: check for check in real.checks}
        for row in parsed.accounted_run.evidence_rows:
            try:
                route = projected_registry.resolve_certificate_route(row.certificate_class)
            except ConfidenceLedgerError:
                issues.append({"code": "accounted_certificate_route_drift"})
                continue
            check = real_checks.get(row.check_projection_hash)
            if (
                route.instrument_id != row.instrument_id
                or route.obligation_class != row.obligation_class
                or route.certificate_role != row.certificate_role
                or route.claim_polarity != row.claim_polarity
                or check is None
                or check.certificate_class != row.certificate_class
                or check.owner_binding is None
                or check.owner_binding.owner_projection_hash != row.owner_projection_hash
                or check.claim_execution_projection_hash != row.claim_execution_projection_hash
                or check.execution_ordinal != row.execution_ordinal
                or check.spend.numerator != row.spend_numerator
                or check.spend.denominator != row.spend_denominator
            ):
                issues.append({"code": "accounted_certificate_route_drift"})
        conformance_checks = {
            check.check_projection_hash: check
            for check in parsed.conformance_ledger_projection.checks
        }
        conformance_check = conformance_checks.get(parsed.conformance_run.check_projection_hash)
        if (
            conformance_check is None
            or conformance_check.claim_execution_projection_hash
            != parsed.conformance_run.claim_execution_projection_hash
            or conformance_check.execution_ordinal != parsed.conformance_run.execution_ordinal
            or conformance_check.instrument_id != parsed.conformance_run.instrument_id
            or conformance_check.certificate_role != parsed.conformance_run.certificate_role
            or conformance_check.claim_polarity != parsed.conformance_run.claim_polarity
            or conformance_check.anytime_valid is not True
            or conformance_check.supports_obligation is not False
            or conformance_check.eligible_for_promotion is not False
        ):
            issues.append({"code": "conformance_check_projection_drift"})
        expected_universality = _universality_evidence(
            projected_registry,
            parsed.accounted_run.evidence_rows,
            unseen_instrument_probe=parsed.universality.unseen_instrument_probe,
        )
        if parsed.universality != expected_universality:
            issues.append({"code": "universality_evidence_drift"})
    if expected is not None and parsed != expected:
        issues.append({"code": "owner_recomputed_contract_drift"})
    return {"status": "pass" if not issues else "fail", "issues": issues}


def corrupt_field_drift_check(contract: FrozenConfidenceLedgerContract) -> dict[str, Any]:
    """Mutate nested load-bearing fields; every corruption must turn RED."""

    cases: tuple[tuple[str, tuple[str | int, ...], object], ...] = (
        ("conditionality_clause", ("conditionality_clause",), _DELETE),
        ("registry_hash", ("registry_content_hash",), "sha256:" + "0" * 64),
        (
            "registry_conditionality_clause",
            ("registry_projection", "conditionality_clause"),
            "conditionality removed",
        ),
        (
            "unseen_instrument_probe_projection_hash",
            ("universality", "unseen_instrument_probe", "projection_hash"),
            "sha256:" + "0" * 64,
        ),
        (
            "maintained_assumptions",
            ("n9_promotion_projection", "maintained_assumptions"),
            ["obligation_completeness"],
        ),
        (
            "schedule_coefficient_numerator",
            (
                "registry_projection",
                "selected_schedule_proof",
                "certified_rational_coefficient",
                "numerator",
            ),
            1,
        ),
        (
            "schedule_coefficient_denominator",
            (
                "registry_projection",
                "selected_schedule_proof",
                "certified_rational_coefficient",
                "denominator",
            ),
            1,
        ),
        (
            "schedule_coefficient_display",
            (
                "registry_projection",
                "selected_schedule_proof",
                "certified_rational_coefficient_decimal",
            ),
            "1",
        ),
        (
            "obligation_membership",
            (
                "registry_projection",
                "obligation_pools",
                0,
                "obligation_classes",
                0,
            ),
            "calibration",
        ),
        (
            "proof_kernel_theorem_id",
            ("registry_projection", "proof_profiles", 0, "proof_kernel_id"),
            "forged_theorem_v1",
        ),
        (
            "ledger_parent_head",
            ("real_ledger_projection", "events", 0, "parent_event_projection_hash"),
            "sha256:" + "4" * 64,
        ),
        (
            "ledger_current_head",
            ("real_ledger_projection", "head_event_projection_hash"),
            "sha256:" + "5" * 64,
        ),
        (
            "semantic_root_hash",
            ("real_ledger_projection", "root_projection_hash"),
            "sha256:" + "5" * 64,
        ),
        (
            "executed_check_id",
            ("conformance_ledger_projection", "checks", 0, "execution_id"),
            "confidence-execution:sha256:" + "6" * 64,
        ),
        (
            "executed_check_ordinal",
            ("conformance_ledger_projection", "checks", 0, "execution_ordinal"),
            7,
        ),
        (
            "filtration_binding",
            (
                "conformance_ledger_projection",
                "checks",
                0,
                "filtration_projection_hash",
            ),
            "sha256:" + "7" * 64,
        ),
        (
            "semantic_request_fingerprint",
            (
                "conformance_ledger_projection",
                "checks",
                0,
                "request_fingerprint",
            ),
            "sha256:" + "7" * 64,
        ),
        (
            "claim_binding",
            ("conformance_ledger_projection", "checks", 0, "claim_ref"),
            "n11://claim/forged",
        ),
        (
            "claim_polarity",
            ("conformance_ledger_projection", "checks", 0, "claim_polarity"),
            "false_accept",
        ),
        (
            "prepared_event_status",
            ("conformance_ledger_projection", "events", 0, "event_type"),
            "started",
        ),
        (
            "started_event_status",
            ("conformance_ledger_projection", "events", 1, "check", "outcome"),
            "supported",
        ),
        (
            "completed_event_status",
            (
                "conformance_ledger_projection",
                "events",
                3,
                "check",
                "execution_status",
            ),
            "started",
        ),
        (
            "semantic_check_hash",
            (
                "conformance_ledger_projection",
                "checks",
                0,
                "check_projection_hash",
            ),
            "sha256:" + "8" * 64,
        ),
        (
            "semantic_event_hash",
            (
                "conformance_ledger_projection",
                "events",
                0,
                "event_projection_hash",
            ),
            "sha256:" + "8" * 64,
        ),
        (
            "semantic_claim_execution_hash",
            (
                "conformance_ledger_projection",
                "checks",
                0,
                "claim_execution_projection_hash",
            ),
            "sha256:" + "8" * 64,
        ),
        (
            "semantic_owner_invocation_claim",
            (
                "conformance_ledger_projection",
                "checks",
                0,
                "owner_invocation_claim_projection_hash",
            ),
            "sha256:" + "8" * 64,
        ),
        (
            "semantic_owner_binding_hash",
            (
                "real_ledger_projection",
                "checks",
                0,
                "owner_binding",
                "binding_projection_hash",
            ),
            "sha256:" + "8" * 64,
        ),
        (
            "semantic_good_event_identity",
            ("conformance_ledger_projection", "checks", 0, "good_event_id"),
            "confidence-good-event:sha256:" + "8" * 64,
        ),
        (
            "semantic_ledger_projection_hash",
            ("conformance_ledger_projection", "projection_hash"),
            "sha256:" + "8" * 64,
        ),
        (
            "real_run_spend",
            ("real_ledger_projection", "total_spend", "numerator"),
            1,
        ),
        (
            "accounted_owner_hash",
            ("accounted_run", "evidence_rows", 0, "owner_projection_hash"),
            "sha256:" + "2" * 64,
        ),
        (
            "conformance_spend",
            ("conformance_ledger_projection", "total_spend", "numerator"),
            0,
        ),
        (
            "per_check_spend",
            ("conformance_ledger_projection", "checks", 0, "spend", "numerator"),
            0,
        ),
        (
            "promotion_projection_hash",
            ("n9_promotion_projection", "projection_hash"),
            "sha256:" + "1" * 64,
        ),
        (
            "promotion_head_ref",
            ("n9_promotion_projection", "ledger_projection_hash"),
            "sha256:" + "3" * 64,
        ),
        (
            "promotion_scope_anchor",
            ("n9_promotion_projection", "scope_anchor_ref"),
            "sha256:" + "6" * 64,
        ),
        (
            "n12_scope_anchor",
            ("n12_epoch_reference_projection", "scope_anchor_ref"),
            "sha256:" + "6" * 64,
        ),
        (
            "projection_authority",
            ("n9_promotion_projection", "authority_provenance"),
            "canonical_repo",
        ),
        (
            "projection_deployment",
            ("n12_epoch_reference_projection", "deployment_identity"),
            "policy-engine-deployment:sha256:" + "6" * 64,
        ),
        (
            "real_projection_scope",
            ("real_ledger_projection", "projection_scope"),
            "n11_conformance_append_lineage",
        ),
        (
            "conformance_projection_scope",
            ("conformance_ledger_projection", "projection_scope"),
            "n11_real_accounting_append_lineage",
        ),
        (
            "real_projection_conditionality_clause",
            ("real_ledger_projection", "conditionality_clause"),
            _DELETE,
        ),
        (
            "conformance_projection_conditionality_clause",
            ("conformance_ledger_projection", "conditionality_clause"),
            _DELETE,
        ),
        (
            "n9_projection_conditionality_clause",
            ("n9_promotion_projection", "conditionality_clause"),
            _DELETE,
        ),
        (
            "n12_conditionality_clause",
            ("n12_epoch_reference_projection", "conditionality_clause"),
            "conditionality removed",
        ),
        (
            "epoch_projection_field",
            ("n12_epoch_reference_projection", "epoch_ref"),
            "epoch://forged",
        ),
        (
            "accounted_run_projection_hash",
            ("accounted_run", "projection_hash"),
            "sha256:" + "6" * 64,
        ),
        (
            "projection_edge_hash",
            ("projection_edges", 0, "producer_projection_hash"),
            "sha256:" + "6" * 64,
        ),
        (
            "projection_edge_deleted",
            ("projection_edges", 3),
            _DELETE,
        ),
        (
            "projection_edge_cycle",
            ("projection_edges", 0, "consumer_scope"),
            "capstone_acquisition_routes",
        ),
    )
    case_ids = tuple(case_id for case_id, _path, _value in cases)
    if case_ids != CORRUPT_FIELD_MUTATION_IDS:
        return {
            "status": "fail",
            "issues": [{"code": "corrupt_field_denominator_drift"}],
            "results": [],
        }
    baseline = contract.model_dump(mode="json")
    results: list[dict[str, Any]] = []
    for case_id, path, value in cases:
        corrupted = copy.deepcopy(baseline)
        _set_nested(corrupted, path, value)
        corrupted["artifact_content_hash"] = gy_content_hash(
            {key: item for key, item in corrupted.items() if key != "artifact_content_hash"}
        )
        report = validate_payload(corrupted)
        results.append(
            {
                "case_id": case_id,
                "result": "RED" if report["status"] == "fail" else "GREEN",
                "issues": report["issues"],
            }
        )
    passed = all(item["result"] == "RED" for item in results)
    return {
        "status": "pass" if passed else "fail",
        "issues": [] if passed else [{"code": "corrupt_field_survived"}],
        "results": results,
    }


_DELETE = object()


def _set_nested(payload: object, path: tuple[str | int, ...], value: object) -> None:
    current: Any = payload
    for key in path[:-1]:
        current = current[key]
    if value is _DELETE:
        del current[path[-1]]
    else:
        current[path[-1]] = value


def _source_flip_cases() -> tuple[_SourceFlipCase, ...]:
    ledger_test = f"{CONFIDENCE_LEDGER_TEST_PATH}::"
    promotion_test = f"{PROMOTION_TEST_PATH}::"
    checker_test = f"{CHECKER_TEST_PATH}::"
    return (
        _SourceFlipCase(
            mutation_id="source_flip_over_spend_admission",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "    if recorded_total > budget or not receipt.within_budget:\n"
                        '        raise ConfidenceLedgerError("over_spend")\n'
                    ),
                    new=('    if False:\n        raise ConfidenceLedgerError("over_spend")\n'),
                ),
            ),
            probe_nodeid=(
                ledger_test + "test_over_spend_is_rejected_even_when_receipt_is_rehashed"
            ),
            expected_red_signal=(
                ledger_test + "test_over_spend_is_rejected_even_when_receipt_is_rehashed"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_schedule_slot_validation_removed",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "        if check.schedule_query_index != expected_index:\n"
                        '            raise ConfidenceLedgerError("schedule_slot_missing")\n'
                    ),
                    new=(
                        "        if False and check.schedule_query_index != expected_index:\n"
                        '            raise ConfidenceLedgerError("schedule_slot_missing")\n'
                    ),
                ),
            ),
            probe_nodeid=(ledger_test + "test_executed_check_without_schedule_slot_fails_closed"),
            expected_red_signal=(
                ledger_test + "test_executed_check_without_schedule_slot_fails_closed"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_unknown_instrument_bypass",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "        if len(matches) != 1:\n"
                        '            raise ConfidenceLedgerError("unknown_instrument", instrument_id)\n'
                        "        return matches[0]\n"
                    ),
                    new=(
                        "        if len(matches) != 1:\n"
                        "            return self.instruments[0]\n"
                        "        return matches[0]\n"
                    ),
                ),
            ),
            probe_nodeid=(
                ledger_test
                + "test_unknown_instrument_preflight_fails_closed_without_start_or_spend"
            ),
            expected_red_signal=(
                ledger_test
                + "test_unknown_instrument_preflight_fails_closed_without_start_or_spend"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_bayesian_ci_relabelled_anytime_valid",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        '    if profile.proof_kernel_id == "ineligible_v1":\n'
                        '        return profile.refusal_code or "non_anytime_valid"\n'
                    ),
                    new=(
                        '    if profile.proof_kernel_id == "disabled_ineligible_v1":\n'
                        '        return profile.refusal_code or "non_anytime_valid"\n'
                    ),
                ),
            ),
            probe_nodeid=(
                ledger_test
                + "test_bayesian_credible_interval_without_coverage_argument_is_typed_refusal"
            ),
            expected_red_signal=(
                ledger_test
                + "test_bayesian_credible_interval_without_coverage_argument_is_typed_refusal"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_n9_ledger_draw_bypass",
            replacements=(
                _SourceFlipReplacement(
                    source_path=PROMOTION_SOURCE_PATH,
                    old=(
                        "        if (\n"
                        "            obligation.status == PromotionObligationStatus.SATISFIED\n"
                        "            and ledger_required\n"
                        "            and not any(\n"
                    ),
                    new=(
                        "        if (\n"
                        "            False\n"
                        "            and obligation.status == PromotionObligationStatus.SATISFIED\n"
                        "            and ledger_required\n"
                        "            and not any(\n"
                    ),
                ),
            ),
            probe_nodeid=(
                promotion_test
                + "test_non_calibration_probabilistic_certificate_bypass_is_rejected"
            ),
            expected_red_signal=(
                promotion_test
                + "test_non_calibration_probabilistic_certificate_bypass_is_rejected"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_forged_spend_row_trusted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "        if check.spend.fraction != expected_spend:\n"
                        '            raise ConfidenceLedgerError("forged_spend_row")\n'
                    ),
                    new=(
                        "        if False and check.spend.fraction != expected_spend:\n"
                        '            raise ConfidenceLedgerError("forged_spend_row")\n'
                    ),
                ),
            ),
            probe_nodeid=(ledger_test + "test_forged_spend_row_is_recomputed_from_schedule"),
            expected_red_signal=(ledger_test + "test_forged_spend_row_is_recomputed_from_schedule"),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_rehashed_forged_registry_trusted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "                if (\n"
                        "                    not self._artifact_store.has(expected_root_ref)\n"
                        "                    and self._scope_root_artifact_exists()\n"
                        "                ):\n"
                        '                    raise ConfidenceLedgerError("ledger_scope_binding_mismatch")\n'
                    ),
                    new=(
                        "                if (\n"
                        "                    not self._artifact_store.has(expected_root_ref)\n"
                        "                    and self._scope_root_artifact_exists()\n"
                        "                ):\n"
                        "                    return\n"
                    ),
                ),
            ),
            probe_nodeid=(
                ledger_test + "test_rehashed_forged_instrument_registry_fails_content_binding"
            ),
            expected_red_signal=(
                ledger_test + "test_rehashed_forged_instrument_registry_fails_content_binding"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_conditionality_clause_deleted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        '        "within_budget": validated.within_budget,\n'
                        '        "good_event_clause": GOOD_EVENT_CLAUSE,\n'
                        '        "conditionality_clause": CONDITIONAL_VALIDITY_CLAUSE,\n'
                    ),
                    new=(
                        '        "within_budget": validated.within_budget,\n'
                        '        "good_event_clause": GOOD_EVENT_CLAUSE,\n'
                    ),
                ),
            ),
            probe_nodeid=(
                ledger_test
                + "test_conditionality_clause_is_required_in_receipt_and_both_projections"
            ),
            expected_red_signal=(
                ledger_test
                + "test_conditionality_clause_is_required_in_receipt_and_both_projections"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_deterministic_proof_nonzero_spend",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "            spend = Fraction()\n"
                        "            if not profile.deterministic:\n"
                    ),
                    new=("            spend = Fraction()\n            if True:\n"),
                ),
            ),
            probe_nodeid=(
                ledger_test
                + "test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification"
            ),
            expected_red_signal=(
                ledger_test
                + "test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_unexecuted_check_spend_admitted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "        if check.started_event_id is None and check.spend.fraction:\n"
                        '            raise ConfidenceLedgerError("spend_for_unexecuted_check")\n'
                    ),
                    new=(
                        "        if False and check.started_event_id is None and check.spend.fraction:\n"
                        '            raise ConfidenceLedgerError("spend_for_unexecuted_check")\n'
                    ),
                ),
            ),
            probe_nodeid=ledger_test + "test_spend_recorded_for_unstarted_check_is_rejected",
            expected_red_signal=(
                ledger_test + "test_spend_recorded_for_unstarted_check_is_rejected"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_owner_certificate_recomputation_removed",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=("    for check in canonical.checks:\n"),
                    new=("    for check in ():\n"),
                ),
            ),
            probe_nodeid=(
                ledger_test
                + "test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification"
            ),
            expected_red_signal=(
                ledger_test
                + "test_deterministic_proof_executes_at_unique_ordinal_with_zero_spend_and_reverification"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_registry_content_binding_removed",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        '            "registry_content_hash": self._registry.content_hash,\n'
                        "            \"instrument_definition_hash\": (_content_hash(instrument) if instrument else None),\n"
                    ),
                    new=(
                        '            "registry_content_hash": history_token.precheck_history_hash,\n'
                        "            \"instrument_definition_hash\": (_content_hash(instrument) if instrument else None),\n"
                    ),
                ),
            ),
            probe_nodeid=(ledger_test + "test_registry_content_hash_is_recomputed_not_trusted"),
            expected_red_signal=(
                ledger_test + "test_registry_content_hash_is_recomputed_not_trusted"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_generation_cycle_ledger_revalidation_removed",
            replacements=(
                _SourceFlipReplacement(
                    source_path=GENERATION_SOURCE_PATH,
                    old=(
                        "        if validate_canonical_promotion_receipt(\n"
                        "            parsed,\n"
                        "            candidate_summary=summary,\n"
                        "            design_problem=problem,\n"
                        "            value_receipt=summary.value_receipt,\n"
                        "        ):\n"
                    ),
                    new=(
                        "        if False and validate_canonical_promotion_receipt(\n"
                        "            parsed,\n"
                        "            candidate_summary=summary,\n"
                        "            design_problem=problem,\n"
                        "            value_receipt=summary.value_receipt,\n"
                        "        ):\n"
                    ),
                ),
            ),
            probe_nodeid=(
                promotion_test + "test_failed_obligation_cannot_be_relabelled_into_decision_front"
            ),
            expected_red_signal=(
                promotion_test + "test_failed_obligation_cannot_be_relabelled_into_decision_front"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_obligation_split_denominator_truncated",
            replacements=(
                _SourceFlipReplacement(
                    source_path=REGISTRY_PATH,
                    old='obligation_classes = ["implementation", "eval_safety"]\n',
                    new='obligation_classes = ["implementation"]\n',
                ),
            ),
            probe_nodeid=(ledger_test + "test_obligation_budget_split_is_total_over_n9_taxonomy"),
            expected_red_signal=(
                ledger_test + "test_obligation_budget_split_is_total_over_n9_taxonomy"
            ),
        ),
        _SourceFlipCase(
            mutation_id="source_flip_duplicate_schedule_slot_accepted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "    if len(set(ordinals)) != len(ordinals):\n"
                        '        raise ConfidenceLedgerError("duplicate_schedule_slot")\n'
                    ),
                    new=(
                        "    if False and len(set(ordinals)) != len(ordinals):\n"
                        '        raise ConfidenceLedgerError("duplicate_schedule_slot")\n'
                    ),
                ),
            ),
            probe_nodeid=ledger_test + "test_duplicate_schedule_slot_is_rejected",
            expected_red_signal=ledger_test + "test_duplicate_schedule_slot_is_rejected",
        ),
        _SourceFlipCase(
            mutation_id="source_flip_non_anytime_instrument_promoted",
            replacements=(
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        '    if profile.proof_kernel_id == "ineligible_v1":\n'
                        '        return profile.refusal_code or "non_anytime_valid"\n'
                    ),
                    new=(
                        '    if profile.proof_kernel_id == "disabled_ineligible_v1":\n'
                        '        return profile.refusal_code or "non_anytime_valid"\n'
                    ),
                ),
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "    if not profile.deterministic and not profile.anytime_valid:\n"
                        '        return "non_anytime_valid"\n'
                    ),
                    new=(
                        "    if False and not profile.deterministic and not profile.anytime_valid:\n"
                        '        return "non_anytime_valid"\n'
                    ),
                ),
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "        return self._complete(\n"
                        "            claimed,\n"
                        '            outcome="refused",\n'
                        "            supports_obligation=False,\n"
                        "            eligible_for_promotion=False,\n"
                        '            refusal_code="unknown_proof_theorem",\n'
                    ),
                    new=(
                        "        return self._complete(\n"
                        "            claimed,\n"
                        '            outcome="supported",\n'
                        "            supports_obligation=True,\n"
                        "            eligible_for_promotion=True,\n"
                        "            refusal_code=None,\n"
                    ),
                ),
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "            and self.anytime_valid\n"
                        "            and self.supports_obligation\n"
                    ),
                    new=("            and True\n            and self.supports_obligation\n"),
                ),
                _SourceFlipReplacement(
                    source_path=CONFIDENCE_LEDGER_SOURCE_PATH,
                    old=(
                        "    if (\n"
                        "        check.supports_obligation or check.eligible_for_promotion\n"
                        "    ) and not profile.permits_obligation_satisfaction:\n"
                        '        raise ConfidenceLedgerError("instrument_registry_binding_invalid")\n'
                    ),
                    new=(
                        "    if False and (\n"
                        "        check.supports_obligation or check.eligible_for_promotion\n"
                        "    ) and not profile.permits_obligation_satisfaction:\n"
                        '        raise ConfidenceLedgerError("instrument_registry_binding_invalid")\n'
                    ),
                ),
            ),
            probe_nodeid=(
                ledger_test + "test_non_anytime_valid_instrument_cannot_support_promotion"
            ),
            expected_red_signal=(
                ledger_test + "test_non_anytime_valid_instrument_cannot_support_promotion"
            ),
        ),
        _SourceFlipCase(
            mutation_id=("source_flip_projection_drops_conditionality_or_binds_whole_contract"),
            replacements=(
                _SourceFlipReplacement(
                    source_path=OWNER_ADAPTER_SOURCE_PATH,
                    old=(
                        "    if stored_routes != recomputed_routes:\n"
                        "        raise OwnerProjectionError("
                        '"n10_capstone_route_projection_drift")\n'
                    ),
                    new=(
                        "    if stored != recomputed:\n"
                        "        raise OwnerProjectionError("
                        '"n10_capstone_route_projection_drift")\n'
                    ),
                ),
            ),
            probe_nodeid=(
                checker_test
                + "test_n10_recomputation_ignores_fields_outside_the_declared_route_projection"
            ),
            expected_red_signal=(
                checker_test
                + "test_n10_recomputation_ignores_fields_outside_the_declared_route_projection"
            ),
        ),
    )


def run_source_flip_mutations(repo_root: Path) -> dict[str, object]:
    """Mutate decisive sources serially and restore their exact original bytes."""

    cases = _source_flip_cases()
    actual_ids = tuple(case.mutation_id for case in cases)
    if actual_ids != SOURCE_FLIP_MUTATION_IDS:
        return {
            "status": "fail",
            "issues": [
                {
                    "code": "source_flip_denominator_mismatch",
                    "expected": list(SOURCE_FLIP_MUTATION_IDS),
                    "actual": list(actual_ids),
                }
            ],
            "results": [],
        }
    results = [_run_source_flip(repo_root, case) for case in cases]
    all_red = all(row["result"] == "RED" for row in results)
    return {
        "status": "pass" if all_red else "fail",
        "issues": [] if all_red else [{"code": "source_flip_mutation_survived"}],
        "mutation_count": len(cases),
        "results": results,
    }


def _run_source_flip(repo_root: Path, case: _SourceFlipCase) -> dict[str, object]:
    root = Path(repo_root).resolve()
    originals: dict[Path, bytes] = {}
    mutated_sources: dict[Path, str] = {}
    for replacement in case.replacements:
        try:
            source_path = _resolve_source_flip_path(root, replacement.source_path)
            original = originals.setdefault(source_path, source_path.read_bytes())
            source = mutated_sources.setdefault(source_path, original.decode("utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return _source_flip_harness_error(
                case,
                "source_flip_source_unreadable",
                detail=str(exc),
            )
        target_count = source.count(replacement.old)
        if target_count != 1:
            return _source_flip_harness_error(
                case,
                "source_flip_guard_count_invalid",
                detail={
                    "path": replacement.source_path.as_posix(),
                    "target_count": target_count,
                },
            )
        mutated_sources[source_path] = source.replace(
            replacement.old,
            replacement.new,
            1,
        )

    baseline = _run_flip_probe(root, case.probe_nodeid)
    if baseline.returncode != 0:
        return _source_flip_harness_error(
            case,
            "source_flip_probe_not_green_before_mutation",
            detail=_probe_evidence(baseline),
        )

    completed: subprocess.CompletedProcess[str] | None = None
    mutation_error: str | None = None
    started = time.monotonic()
    try:
        for source_path, mutated in mutated_sources.items():
            source_path.write_bytes(mutated.encode("utf-8"))
        completed = _run_flip_probe(root, case.probe_nodeid)
    except Exception as exc:  # noqa: BLE001 - emitted as harness evidence.
        mutation_error = f"{type(exc).__name__}:{exc}"
    finally:
        for source_path, original in originals.items():
            source_path.write_bytes(original)

    restored_hashes: dict[str, str] = {}
    for source_path, original in originals.items():
        restored = source_path.read_bytes()
        before_hash = hashlib.sha256(original).hexdigest()
        after_hash = hashlib.sha256(restored).hexdigest()
        restored_hashes[source_path.relative_to(root).as_posix()] = after_hash
        if restored != original or after_hash != before_hash:
            return _source_flip_harness_error(
                case,
                "source_restore_hash_mismatch",
                detail={
                    "path": source_path.relative_to(root).as_posix(),
                    "before": before_hash,
                    "after": after_hash,
                },
            )

    restored_probe = _run_flip_probe(root, case.probe_nodeid)
    if restored_probe.returncode != 0:
        return _source_flip_harness_error(
            case,
            "source_flip_probe_not_green_after_restore",
            detail=_probe_evidence(restored_probe),
        )
    if mutation_error is not None or completed is None:
        return _source_flip_harness_error(
            case,
            "source_flip_probe_not_run",
            detail=mutation_error or "completed process missing",
        )

    output = f"{completed.stdout}\n{completed.stderr}"
    targeted_failure = f"FAILED {case.expected_red_signal}" in output
    red = completed.returncode != 0 and targeted_failure
    return {
        "mutation_id": case.mutation_id,
        "result": "RED" if red else "GREEN_MUTATION_SURVIVED",
        "proof": {
            "probe_nodeid": case.probe_nodeid,
            "expected_red_signal": case.expected_red_signal,
            "exit_code": completed.returncode,
            "baseline_exit_code": baseline.returncode,
            "restored_exit_code": restored_probe.returncode,
            "targeted_failure_observed": targeted_failure,
            "source_restored_sha256": restored_hashes,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": _output_tail(completed.stdout),
            "stderr_tail": _output_tail(completed.stderr),
        },
    }


def _resolve_source_flip_path(repo_root: Path, relative_path: Path) -> Path:
    if relative_path.is_absolute():
        raise ValueError(f"source flip path must be relative: {relative_path}")
    candidate = (repo_root / relative_path).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"source flip path escapes repository: {relative_path}") from exc
    return candidate


def _run_flip_probe(
    repo_root: Path,
    nodeid: str,
) -> subprocess.CompletedProcess[str]:
    """Run one semantic witness in a fresh process with isolated bytecode state."""

    with tempfile.TemporaryDirectory(prefix="polisyos-n11-flip-pycache-") as cache_root:
        return subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "pytest",
                nodeid,
                "-q",
                "-p",
                "no:cacheprovider",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "JAX_PLATFORMS": "cpu",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPYCACHEPREFIX": cache_root,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )


def _source_flip_harness_error(
    case: _SourceFlipCase,
    code: str,
    *,
    detail: object,
) -> dict[str, object]:
    return {
        "mutation_id": case.mutation_id,
        "result": "HARNESS_ERROR",
        "proof": {"error": code, "detail": detail},
    }


def _probe_evidence(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return {
        "exit_code": completed.returncode,
        "stdout_tail": _output_tail(completed.stdout),
        "stderr_tail": _output_tail(completed.stderr),
    }


def _output_tail(output: str, *, max_lines: int = 16) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _read_contract(path: Path) -> FrozenConfidenceLedgerContract:
    try:
        return FrozenConfidenceLedgerContract.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise RuntimeError(f"confidence_ledger_contract_unreadable:{path}") from exc


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _check_exact(path: Path, expected: bytes, code: str) -> None:
    """Require a frozen artifact to equal canonical writer bytes exactly."""

    try:
        actual = Path(path).read_bytes()
    except OSError as exc:
        raise RuntimeError(f"{code}:unreadable:{path}") from exc
    if actual != expected:
        raise RuntimeError(code)


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _effective_closeout_config(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
    output: Path,
    cold: bool,
) -> dict[str, Any]:
    registry_path = repo_root / REGISTRY_PATH
    return {
        "repo_root": repo_root.as_posix(),
        "registry_path": registry_path.as_posix(),
        "registry_file_sha256": _file_digest(registry_path),
        "registry_content_hash": load_confidence_ledger_registry(registry_path).content_hash,
        "catalog_path": catalog_path.as_posix(),
        "catalog_sha256": _file_digest(catalog_path),
        "l5_path": l5_path.as_posix(),
        "l5_sha256": _file_digest(l5_path),
        "output_path": output.as_posix(),
        "cache_mode": ("cold_clear_then_hit" if cold else "worker_warmup_then_two_cache_hits"),
        "jax_platforms": os.environ.get("JAX_PLATFORMS", "unset"),
        "runtime_schema_version": CONFIDENCE_LEDGER_SCHEMA_VERSION,
        "registry_schema_version": CONFIDENCE_LEDGER_REGISTRY_SCHEMA_VERSION,
        "artifact_schema_version": SCHEMA_VERSION,
        "rule_ref": SCHEMA_VERSION,
        "varied_input": {
            "name": "owner_cache_mode",
            "value": "cold" if cold else "warm",
        },
    }


def _stage_heartbeat(
    heartbeats: list[dict[str, Any]],
    *,
    stage: str,
    event: Literal[
        "objective_progress",
        "cpu_heartbeat",
        "complete",
        "terminated",
    ],
    elapsed_seconds: float,
    progress: str,
    process_cpu_seconds: float | None,
    objective_progress_ordinal: int | None,
    profiling_stop_required: bool = False,
) -> None:
    row = {
        "stage": stage,
        "event": event,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "process_cpu_seconds": (
            round(process_cpu_seconds, 6) if process_cpu_seconds is not None else None
        ),
        "objective_progress_ordinal": objective_progress_ordinal,
        "profiling_stop_required": profiling_stop_required,
        "progress": progress,
    }
    heartbeats.append(row)
    print(
        "N11_HEARTBEAT " + json.dumps(row, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def _closeout_stage_plan(*, cold: bool) -> tuple[str, ...]:
    """Return the in-worker stage plan for one closeout invocation."""

    if cold:
        return ("cold_owner_derivation", "cache_hit_derivation")
    return (
        "warmup_owner_derivation",
        "warm_owner_derivation",
        "cache_hit_derivation",
    )


def _expected_objective_milestones(stage: str) -> tuple[str, ...]:
    """Return the exact objective state machine for one derivation stage."""

    if stage in {"cold_owner_derivation", "warmup_owner_derivation"}:
        owner_milestones = _COLD_OWNER_PROGRESS_MILESTONES
    elif stage in {"warm_owner_derivation", "cache_hit_derivation"}:
        owner_milestones = ()
    else:
        raise ValueError(f"unknown_closeout_stage:{stage}")
    return (
        "stage_started",
        *_BUILD_PROGRESS_PREFIX,
        *owner_milestones,
        *_BUILD_PROGRESS_SUFFIX,
        "stage_complete",
    )


def _validated_worker_message(payload: object) -> dict[str, Any]:
    """Return one exact discriminated IPC message or raise validation error."""

    message = _WORKER_MESSAGE_ADAPTER.validate_python(payload, strict=True)
    return message.model_dump(mode="python")


def _send_worker_message(connection: Connection, payload: object) -> None:
    """Validate an outgoing worker message before crossing the pipe."""

    connection.send(_validated_worker_message(payload))


def _closeout_worker_bootstrap(
    connection: Connection,
    *,
    worker_target: Callable[..., None],
    worker_kwargs: dict[str, object],
) -> None:
    """Establish the sole profiled process group before invoking worker payload code."""

    profile_handle: Any | None = None
    profile_signal = getattr(signal, "SIGUSR1", None)
    registered = False
    try:
        if not hasattr(os, "setsid"):
            raise RuntimeError("closeout_worker_setsid_unavailable")
        os.setsid()
        pid = os.getpid()
        pgid = os.getpgid(pid)
        profile_path = Path(str(worker_kwargs["profile_path"]))
        profile_handle = profile_path.open("w", encoding="utf-8")
        if profile_signal is not None:
            faulthandler.register(profile_signal, file=profile_handle, all_threads=True)
            registered = True
        _send_worker_message(
            connection,
            {
                "kind": "worker_bootstrap",
                "pid": pid,
                "pgid": pgid,
                "profiling_ready": registered,
            },
        )
        command = connection.recv()
        _BootstrapAcceptedCommand.model_validate(command, strict=True)
        worker_target(connection=connection, **worker_kwargs)
    except BaseException as exc:  # noqa: BLE001 - serialized across the process boundary.
        with suppress(BrokenPipeError, EOFError, OSError, ValidationError):
            _send_worker_message(
                connection,
                {
                    "kind": "worker_error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
    finally:
        if registered and profile_signal is not None:
            with suppress(RuntimeError):
                faulthandler.unregister(profile_signal)
        if profile_handle is not None:
            profile_handle.close()
        connection.close()


def _closeout_worker_main(
    connection: Connection,
    *,
    repo_root: str,
    catalog_path: str,
    l5_path: str,
    cold: bool,
    profile_path: str,
) -> None:
    """Run both contract builds in one killable process with one shared cache."""

    del profile_path
    ordinal = 0

    def send(message: dict[str, Any]) -> None:
        _send_worker_message(connection, message)

    def objective_progress(stage: str, milestone: str) -> None:
        nonlocal ordinal
        ordinal += 1
        send(
            {
                "kind": "objective_progress",
                "stage": stage,
                "ordinal": ordinal,
                "milestone": milestone,
            }
        )

    try:
        send({"kind": "worker_ready", "pid": os.getpid()})
        clear_owner_bundle_cache()
        cache_before = owner_bundle_cache_stats()
        stages = _closeout_stage_plan(cold=cold)
        cache_after_warmup: dict[str, int] | None = None
        cache_after_first: dict[str, int] | None = None
        for stage in stages:
            result_role = (
                "warmup"
                if stage == "warmup_owner_derivation"
                else "second"
                if stage == "cache_hit_derivation"
                else "first"
            )
            stage_started = time.monotonic()
            objective_progress(stage, "stage_started")
            contract = build_live_contract(
                Path(repo_root),
                catalog_path=Path(catalog_path),
                l5_path=Path(l5_path),
                objective_progress=lambda milestone, stage=stage: objective_progress(
                    stage,
                    milestone,
                ),
            )
            objective_progress(stage, "stage_complete")
            cache_after = owner_bundle_cache_stats()
            if result_role == "warmup":
                cache_after_warmup = cache_after
            elif result_role == "first":
                cache_after_first = cache_after
            send(
                {
                    "kind": "stage_result",
                    "stage": stage,
                    "result_role": result_role,
                    "worker_pid": os.getpid(),
                    "wall_time_seconds": time.monotonic() - stage_started,
                    "contract_bytes": contract_bytes(contract),
                    "cache_before": cache_before,
                    "cache_after_warmup": cache_after_warmup,
                    "cache_after_first": cache_after_first,
                    "cache_after": cache_after,
                }
            )
            if result_role == "first":
                command = connection.recv()
                _RunSecondPassCommand.model_validate(command, strict=True)
        send({"kind": "worker_complete", "pid": os.getpid()})
    except BaseException as exc:  # noqa: BLE001 - serialized across process boundary.
        with suppress(BrokenPipeError, EOFError, OSError):
            send(
                {
                    "kind": "worker_error",
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )


def _read_process_cpu_seconds(pid: int) -> float | None:
    """Read one worker CPU sample without treating it as semantic progress."""

    try:
        completed = subprocess.run(
            ("ps", "-o", "time=", "-p", str(pid)),
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value:
        return None
    try:
        day_parts = value.split("-", maxsplit=1)
        days = int(day_parts[0]) if len(day_parts) == 2 else 0
        clock = day_parts[-1].split(":")
        if len(clock) == 3:
            hours, minutes, seconds = clock
        elif len(clock) == 2:
            hours = "0"
            minutes, seconds = clock
        else:
            return None
        return days * 86400.0 + int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)
    except ValueError:
        return None


def _terminate_and_profile_worker(
    process: multiprocessing.Process,
    *,
    profile_path: Path,
    verified_pgid: int | None,
    profiling_ready: bool,
) -> dict[str, Any]:
    """Capture a worker stack and terminate the stalled process."""

    profile_signal = getattr(signal, "SIGUSR1", None)
    signal_sent = False
    status = "profile_handler_not_ready"
    if profiling_ready and profile_signal is None:
        status = "profile_signal_unavailable"
    elif profiling_ready and not process.is_alive():
        status = "profile_target_exited"
    elif profiling_ready and process.pid is not None:
        try:
            os.kill(process.pid, profile_signal)
            signal_sent = True
            status = "profile_signal_sent"
            time.sleep(_PROFILE_SIGNAL_GRACE_SECONDS)
        except OSError:
            signal_sent = False
            status = "profile_signal_failed"
    process_group_clean = _stop_worker(process, verified_pgid=verified_pgid)
    try:
        stack_trace = profile_path.read_text(encoding="utf-8")
    except OSError:
        stack_trace = ""
    if stack_trace.strip():
        status = "profile_captured"
    elif signal_sent:
        status = "profile_empty"
    return {
        "status": status,
        "signal_sent": signal_sent,
        "captured": bool(stack_trace.strip()),
        "stack_trace": stack_trace,
        "process_group_clean": process_group_clean,
    }


def _process_group_exists(pgid: int) -> bool:
    """Return whether a verified POSIX process group still has members."""

    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_process_group_exit(pgid: int, *, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while _process_group_exists(pgid) and time.monotonic() < deadline:
        time.sleep(0.01)
    return not _process_group_exists(pgid)


def _stop_worker(
    process: multiprocessing.Process,
    *,
    verified_pgid: int | None,
) -> bool:
    """Terminate the verified group, or only the leader before bootstrap."""

    pid = process.pid
    group_verified = verified_pgid is not None and pid is not None and verified_pgid == pid
    if group_verified:
        if not process.is_alive():
            process.join(timeout=0.5)
            if not _process_group_exists(verified_pgid):
                return True
        if _process_group_exists(verified_pgid):
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(verified_pgid, signal.SIGTERM)
        process.join(timeout=0.5)
        if not _wait_for_process_group_exit(verified_pgid, timeout=0.5):
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(verified_pgid, signal.SIGKILL)
            process.join(timeout=1.0)
            _wait_for_process_group_exit(verified_pgid, timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
        return not process.is_alive() and not _process_group_exists(verified_pgid)
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=1.0)
    return not process.is_alive()


def _run_closeout_worker(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
    cold: bool,
    process_start_method: str,
    worker_target: Callable[..., None] = _closeout_worker_main,
    _bootstrap_target: Callable[..., None] = _closeout_worker_bootstrap,
) -> dict[str, Any]:
    """Monitor one two-pass worker using objective progress as the only wait signal."""

    context = multiprocessing.get_context(process_start_method)
    parent_connection, child_connection = context.Pipe(duplex=True)
    heartbeats: list[dict[str, Any]] = []
    closeout_started = time.monotonic()
    stage_plan = _closeout_stage_plan(cold=cold)
    stage_plan_index = 0
    current_stage = "worker_startup"
    expected_milestones: tuple[str, ...] = ()
    milestone_index = 0
    stage_started = closeout_started
    last_objective_at = closeout_started
    last_ordinal = 0
    worker_pid = 0
    verified_pgid: int | None = None
    bootstrap_verified = False
    worker_ready = False
    profiling_ready = False
    worker_terminated = False
    profiling_stop = False
    worker_profile: dict[str, Any] = {
        "status": "profile_handler_not_ready",
        "signal_sent": False,
        "captured": False,
        "stack_trace": "",
        "process_group_clean": False,
    }
    first_bytes: bytes | None = None
    second_bytes: bytes | None = None
    first_wall = 0.0
    second_wall = 0.0
    cache_before: dict[str, int] = {}
    cache_after_warmup: dict[str, int] = {}
    cache_after_first: dict[str, int] = {}
    cache_after_second: dict[str, int] = {}
    stage_wall_times: dict[str, float] = {}
    second_pass_started = False
    stop_stage: str | None = None
    worker_error: dict[str, Any] | None = None
    process_group_clean = False
    with tempfile.TemporaryDirectory(prefix="gy-n11-worker-profile-") as temporary:
        profile_path = Path(temporary) / "worker-stack.txt"
        worker_kwargs: dict[str, object] = {
            "repo_root": repo_root.as_posix(),
            "catalog_path": catalog_path.as_posix(),
            "l5_path": l5_path.as_posix(),
            "cold": cold,
            "profile_path": profile_path.as_posix(),
        }
        process = context.Process(
            target=_bootstrap_target,
            kwargs={
                "connection": child_connection,
                "worker_target": worker_target,
                "worker_kwargs": worker_kwargs,
            },
            name="n11-confidence-ledger-closeout",
        )
        process.start()
        if type(process.pid) is not int or process.pid <= 0:
            raise RuntimeError("closeout_worker_pid_unavailable")
        worker_pid = process.pid
        child_connection.close()
        completed = False
        try:
            while not completed:
                message: dict[str, Any] | None = None
                pipe_eof = False
                if parent_connection.poll(_HEARTBEAT_INTERVAL_SECONDS):
                    try:
                        received = parent_connection.recv()
                    except EOFError:
                        pipe_eof = True
                        received = None
                    if not pipe_eof:
                        try:
                            message = _validated_worker_message(received)
                        except ValidationError as exc:
                            worker_error = {
                                "code": "closeout_worker_wire_invalid",
                                "error": str(exc),
                            }
                            stop_stage = current_stage
                now = time.monotonic()
                if pipe_eof:
                    worker_error = worker_error or {
                        "code": "closeout_worker_exited_early",
                        "exit_code": process.exitcode,
                    }
                    stop_stage = current_stage
                    break
                if stop_stage is not None:
                    break
                if message is None:
                    cpu_seconds = _read_process_cpu_seconds(worker_pid) if worker_pid else None
                    _stage_heartbeat(
                        heartbeats,
                        stage=current_stage,
                        event="cpu_heartbeat",
                        elapsed_seconds=now - closeout_started,
                        progress="worker_cpu_sample",
                        process_cpu_seconds=cpu_seconds,
                        objective_progress_ordinal=None,
                    )
                else:
                    kind = message["kind"]
                    if kind == "worker_error":
                        worker_error = {
                            "code": "closeout_worker_error",
                            "error_type": message["error_type"],
                            "detail": message["detail"],
                            "traceback": message["traceback"],
                        }
                        stop_stage = current_stage
                    elif not bootstrap_verified:
                        if kind != "worker_bootstrap":
                            worker_error = {
                                "code": "closeout_worker_bootstrap_order_invalid",
                                "observed_kind": kind,
                            }
                            stop_stage = current_stage
                        else:
                            try:
                                observed_pgid = os.getpgid(worker_pid)
                            except OSError:
                                observed_pgid = None
                            if (
                                message["pid"] != worker_pid
                                or message["pgid"] != worker_pid
                                or observed_pgid != message["pgid"]
                                or message["profiling_ready"] is not True
                            ):
                                worker_error = {
                                    "code": "closeout_worker_bootstrap_invalid",
                                    "expected_pid_pgid": worker_pid,
                                    "observed_pid": message["pid"],
                                    "declared_pgid": message["pgid"],
                                    "observed_pgid": observed_pgid,
                                    "profiling_ready": message["profiling_ready"],
                                }
                                stop_stage = current_stage
                                break
                            verified_pgid = message["pgid"]
                            profiling_ready = True
                            bootstrap_verified = True
                            _stage_heartbeat(
                                heartbeats,
                                stage="worker_startup",
                                event="cpu_heartbeat",
                                elapsed_seconds=now - closeout_started,
                                progress="worker_bootstrap_verified",
                                process_cpu_seconds=_read_process_cpu_seconds(worker_pid),
                                objective_progress_ordinal=None,
                            )
                            try:
                                parent_connection.send(
                                    _BootstrapAcceptedCommand(
                                        command="bootstrap_accepted"
                                    ).model_dump(mode="python")
                                )
                            except (BrokenPipeError, EOFError, OSError) as exc:
                                worker_error = {
                                    "code": "closeout_worker_command_channel_closed",
                                    "error_type": type(exc).__name__,
                                }
                                stop_stage = current_stage
                                break
                    elif kind == "worker_bootstrap":
                        worker_error = {"code": "closeout_worker_duplicate_bootstrap"}
                        stop_stage = current_stage
                    elif kind == "worker_ready":
                        if (
                            worker_ready
                            or current_stage != "worker_startup"
                            or message["pid"] != worker_pid
                        ):
                            worker_error = {
                                "code": "closeout_worker_readiness_protocol_error",
                                "expected_pid": worker_pid,
                                "observed_pid": message["pid"],
                                "duplicate": worker_ready,
                            }
                            stop_stage = current_stage
                        else:
                            worker_ready = True
                            stage_wall_times["worker_startup"] = now - closeout_started
                            _stage_heartbeat(
                                heartbeats,
                                stage="worker_startup",
                                event="complete",
                                elapsed_seconds=now - closeout_started,
                                progress="worker_ready",
                                process_cpu_seconds=None,
                                objective_progress_ordinal=None,
                            )
                            current_stage = stage_plan[stage_plan_index]
                            expected_milestones = _expected_objective_milestones(current_stage)
                            stage_started = now
                            last_objective_at = now
                    elif not worker_ready:
                        worker_error = {
                            "code": "closeout_worker_readiness_order_invalid",
                            "observed_kind": kind,
                        }
                        stop_stage = current_stage
                    elif kind == "objective_progress":
                        ordinal = message["ordinal"]
                        milestone = message["milestone"]
                        observed_stage = message["stage"]
                        expected_milestone = (
                            expected_milestones[milestone_index]
                            if milestone_index < len(expected_milestones)
                            else None
                        )
                        if (
                            ordinal != last_ordinal + 1
                            or observed_stage != current_stage
                            or milestone != expected_milestone
                        ):
                            worker_error = {
                                "code": "objective_progress_protocol_error",
                                "observed_ordinal": ordinal,
                                "expected_ordinal": last_ordinal + 1,
                                "observed_stage": observed_stage,
                                "expected_stage": current_stage,
                                "observed_milestone": milestone,
                                "expected_milestone": expected_milestone,
                            }
                            stop_stage = current_stage
                        else:
                            last_ordinal = ordinal
                            last_objective_at = now
                            milestone_index += 1
                            if milestone == "stage_started":
                                stage_started = now
                                if current_stage == "cache_hit_derivation":
                                    second_pass_started = True
                            _stage_heartbeat(
                                heartbeats,
                                stage=current_stage,
                                event="objective_progress",
                                elapsed_seconds=now - closeout_started,
                                progress=milestone,
                                process_cpu_seconds=None,
                                objective_progress_ordinal=ordinal,
                            )
                    elif kind == "stage_result":
                        result_role = message["result_role"]
                        expected_role = (
                            "warmup"
                            if current_stage == "warmup_owner_derivation"
                            else "second"
                            if current_stage == "cache_hit_derivation"
                            else "first"
                        )
                        if (
                            message["worker_pid"] != worker_pid
                            or message["stage"] != current_stage
                            or result_role != expected_role
                            or milestone_index != len(expected_milestones)
                        ):
                            worker_error = {
                                "code": "closeout_worker_stage_result_protocol_error",
                                "observed_stage": message.get("stage"),
                                "expected_stage": current_stage,
                                "observed_role": result_role,
                                "expected_role": expected_role,
                                "observed_milestone_count": milestone_index,
                                "expected_milestone_count": len(expected_milestones),
                            }
                            stop_stage = current_stage
                        else:
                            stage_wall = message["wall_time_seconds"]
                            stage_wall_times[current_stage] = stage_wall
                            cache_before = message["cache_before"].copy()
                            if result_role == "warmup":
                                cache_after_warmup = message["cache_after"].copy()
                            elif result_role == "first":
                                first_bytes = message["contract_bytes"]
                                first_wall = stage_wall
                                cache_after_first = message["cache_after"].copy()
                                try:
                                    parent_connection.send({"command": "run_second_pass"})
                                except (BrokenPipeError, EOFError, OSError) as exc:
                                    worker_error = {
                                        "code": "closeout_worker_command_channel_closed",
                                        "error_type": type(exc).__name__,
                                    }
                                    stop_stage = current_stage
                            else:
                                second_bytes = message["contract_bytes"]
                                second_wall = stage_wall
                                cache_after_second = message["cache_after"].copy()
                                _stage_heartbeat(
                                    heartbeats,
                                    stage=current_stage,
                                    event="complete",
                                    elapsed_seconds=now - closeout_started,
                                    progress="two_pass_worker_complete",
                                    process_cpu_seconds=_read_process_cpu_seconds(worker_pid),
                                    objective_progress_ordinal=None,
                                )
                            if stop_stage is None:
                                stage_plan_index += 1
                                if stage_plan_index < len(stage_plan):
                                    current_stage = stage_plan[stage_plan_index]
                                    expected_milestones = _expected_objective_milestones(
                                        current_stage
                                    )
                                    milestone_index = 0
                    elif kind == "worker_complete":
                        if (
                            message["pid"] != worker_pid
                            or stage_plan_index != len(stage_plan)
                            or first_bytes is None
                            or second_bytes is None
                        ):
                            worker_error = {"code": "closeout_worker_completion_protocol_error"}
                            stop_stage = current_stage
                        else:
                            completed = True

                if stop_stage is not None:
                    break
                stale_seconds = time.monotonic() - last_objective_at
                stale_limit = _HISTORICAL_STAGE_SECONDS[current_stage] * 2.0
                if stale_seconds > stale_limit:
                    stop_stage = current_stage
                    worker_terminated = True
                    profiling_stop = True
                    worker_profile = _terminate_and_profile_worker(
                        process,
                        profile_path=profile_path,
                        verified_pgid=verified_pgid,
                        profiling_ready=profiling_ready,
                    )
                    _stage_heartbeat(
                        heartbeats,
                        stage=stop_stage,
                        event="terminated",
                        elapsed_seconds=time.monotonic() - closeout_started,
                        progress="profiled_and_terminated_after_objective_stall",
                        process_cpu_seconds=(
                            _read_process_cpu_seconds(worker_pid) if worker_pid else None
                        ),
                        objective_progress_ordinal=None,
                        profiling_stop_required=True,
                    )
                    break
                if not process.is_alive() and not completed:
                    if parent_connection.poll(0.0):
                        continue
                    worker_error = worker_error or {
                        "code": "closeout_worker_exited_early",
                        "exit_code": process.exitcode,
                    }
                    stop_stage = current_stage
                    break
        finally:
            process_group_clean = _stop_worker(process, verified_pgid=verified_pgid)
            parent_connection.close()
        if current_stage == "worker_startup" and "worker_startup" not in stage_wall_times:
            stage_wall_times["worker_startup"] = max(
                0.0,
                time.monotonic() - closeout_started,
            )
        if not process_group_clean:
            worker_error = worker_error or {"code": "closeout_worker_process_group_leak"}
            stop_stage = stop_stage or current_stage
        if not worker_terminated:
            try:
                stack_trace = profile_path.read_text(encoding="utf-8")
            except OSError:
                stack_trace = ""
            worker_profile = {
                "status": "not_requested" if profiling_ready else "profile_handler_not_ready",
                "signal_sent": False,
                "captured": False,
                "stack_trace": stack_trace,
                "process_group_clean": process_group_clean,
            }
        else:
            worker_profile["process_group_clean"] = process_group_clean
    return {
        "worker_pid": worker_pid,
        "verified_pgid": verified_pgid,
        "bootstrap_verified": bootstrap_verified,
        "profiling_ready": profiling_ready,
        "process_group_clean": process_group_clean,
        "worker_terminated": worker_terminated,
        "profiling_stop": profiling_stop,
        "worker_profile": worker_profile,
        "worker_error": worker_error,
        "stop_stage": stop_stage,
        "stage_heartbeats": heartbeats,
        "first_bytes": first_bytes,
        "second_bytes": second_bytes,
        "first_wall": first_wall or (time.monotonic() - stage_started),
        "second_wall": second_wall,
        "stage_wall_times": stage_wall_times,
        "cache_before": cache_before,
        "cache_after_warmup": cache_after_warmup,
        "cache_after_first": cache_after_first,
        "cache_after_second": cache_after_second,
        "second_pass_started": second_pass_started,
    }


def _historical_stage_comparison(
    *,
    stage: str,
    wall_time_seconds: float,
) -> dict[str, Any]:
    historical = _HISTORICAL_STAGE_SECONDS[stage]
    return {
        "stage": stage,
        "historical_wall_time_seconds": historical,
        "observed_wall_time_seconds": round(wall_time_seconds, 6),
        "observed_to_historical_ratio": round(wall_time_seconds / historical, 6),
        "two_x_stop_threshold_seconds": historical * 2.0,
        "within_two_x_historical": wall_time_seconds <= historical * 2.0,
    }


def _derive_byte_stable_contract(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
) -> tuple[FrozenConfidenceLedgerContract, bytes]:
    """Derive twice in a killable worker and return byte-identical output."""

    worker = _run_closeout_worker(
        repo_root,
        catalog_path=catalog_path,
        l5_path=l5_path,
        cold=True,
        process_start_method="spawn",
    )
    if worker["profiling_stop"]:
        raise RuntimeError("historical_stage_two_x_profiling_stop")
    if worker["worker_error"] is not None:
        raise RuntimeError(str(worker["worker_error"]["code"]))
    first_bytes = worker["first_bytes"]
    second_bytes = worker["second_bytes"]
    if first_bytes is None or second_bytes is None:
        raise RuntimeError("monitored_derivation_incomplete")
    if first_bytes != second_bytes:
        raise RuntimeError("writer_not_byte_stable")
    first = FrozenConfidenceLedgerContract.model_validate_json(first_bytes)
    return first, first_bytes


def _run_one_process_closeout(
    repo_root: Path,
    *,
    catalog_path: Path,
    l5_path: Path,
    output: Path,
    cold: bool,
    write_output: bool = False,
    _process_start_method: str = "spawn",
) -> dict[str, Any]:
    """Run one cold-or-warm owner build plus a cache-hit equivalence pass."""

    effective_config = _effective_closeout_config(
        repo_root,
        catalog_path=catalog_path,
        l5_path=l5_path,
        output=output,
        cold=cold,
    )
    first_stage = "cold_owner_derivation" if cold else "warm_owner_derivation"
    worker = _run_closeout_worker(
        repo_root,
        catalog_path=catalog_path,
        l5_path=l5_path,
        cold=cold,
        process_start_method=_process_start_method,
    )
    first_bytes = worker["first_bytes"]
    second_bytes = worker["second_bytes"]
    first_wall = float(worker["first_wall"])
    second_wall = float(worker["second_wall"])
    second_ran = second_bytes is not None
    issues: list[dict[str, Any]] = []
    if worker["worker_error"] is not None:
        issues.append(worker["worker_error"])
    if worker["profiling_stop"]:
        issues.append(
            {
                "code": "historical_stage_two_x_profiling_stop",
                "stage": worker["stop_stage"],
            }
        )
    if first_bytes is None:
        return {
            "status": "fail",
            "issues": issues or [{"code": "first_derivation_missing"}],
            "lane": "cold_closeout" if cold else "warm_closeout",
            "byte_stable_passes": 0,
            "cold_warm_byte_identical": False,
            "corrupt_field_case_count": 0,
            "cache_before": worker["cache_before"],
            "cache_after_warmup": worker["cache_after_warmup"],
            "cache_after_first": worker["cache_after_first"],
            "cache_after_second": worker["cache_after_second"],
            "effective_config": effective_config,
            "stage_heartbeats": worker["stage_heartbeats"],
            "historical_stage_comparison": (),
            "first_derivation_wall_time_seconds": round(first_wall, 6),
            "cache_hit_derivation_wall_time_seconds": 0.0,
            "worker_pid": worker["worker_pid"],
            "verified_pgid": worker["verified_pgid"],
            "bootstrap_verified": worker["bootstrap_verified"],
            "profiling_ready": worker["profiling_ready"],
            "process_group_clean": worker["process_group_clean"],
            "worker_terminated": worker["worker_terminated"],
            "worker_profile": worker["worker_profile"],
            "second_pass_started": worker["second_pass_started"],
            "cold_closeout_budget_seconds": (
                _HISTORICAL_STAGE_SECONDS["cold_owner_derivation"] if cold else None
            ),
            "cold_closeout_budget_exceeded": False,
            "cold_closeout_budget_disposition": (
                "incomplete" if cold else "not_applicable"
            ),
        }
    first = FrozenConfidenceLedgerContract.model_validate_json(first_bytes)
    second = (
        FrozenConfidenceLedgerContract.model_validate_json(second_bytes)
        if second_bytes is not None
        else None
    )
    if write_output:
        if second is None or first_bytes != second_bytes:
            issues.append({"code": "writer_not_byte_stable"})
        else:
            _write_atomic(output, first_bytes)
    comparisons = []
    startup_wall = worker["stage_wall_times"].get("worker_startup")
    if startup_wall is not None:
        comparisons.append(
            _historical_stage_comparison(
                stage="worker_startup",
                wall_time_seconds=startup_wall,
            )
        )
    warmup_wall = worker["stage_wall_times"].get("warmup_owner_derivation")
    if warmup_wall is not None:
        comparisons.append(
            _historical_stage_comparison(
                stage="warmup_owner_derivation",
                wall_time_seconds=warmup_wall,
            )
        )
    comparisons.append(
        _historical_stage_comparison(stage=first_stage, wall_time_seconds=first_wall)
    )
    if second_ran:
        comparisons.append(
            _historical_stage_comparison(
                stage="cache_hit_derivation", wall_time_seconds=second_wall
            )
        )
    cold_budget_seconds = _HISTORICAL_STAGE_SECONDS["cold_owner_derivation"]
    cold_budget_exceeded = cold and first_wall > cold_budget_seconds
    cold_budget_disposition = "not_applicable"
    if cold:
        cold_budget_disposition = "within_budget"
        if cold_budget_exceeded:
            completed_with_objective_progress = any(
                row["stage"] == "cold_owner_derivation"
                and row["event"] == "objective_progress"
                and row["progress"] == "stage_complete"
                for row in worker["stage_heartbeats"]
            )
            if completed_with_objective_progress and not worker["profiling_stop"]:
                cold_budget_disposition = "completed_with_objective_progress"
            else:
                cold_budget_disposition = "profiling_required"
                issues.append(
                    {
                        "code": "cold_closeout_wall_time_overrun",
                        "wall_time_seconds": round(first_wall, 6),
                    }
                )
    if effective_config["jax_platforms"] != "cpu":
        issues.append({"code": "jax_platform_not_cpu"})
    if second is None or first_bytes != second_bytes:
        issues.append({"code": "cold_warm_contract_bytes_differ"})
    try:
        _check_exact(output, first_bytes, "confidence_ledger_contract_drift")
    except RuntimeError as exc:
        issues.append({"code": str(exc)})
    stored_report = validate_payload(_read_contract(output), expected=first)
    issues.extend(stored_report["issues"])
    corrupt_report = corrupt_field_drift_check(first)
    issues.extend(corrupt_report["issues"])
    cache_after_first = worker["cache_after_first"]
    cache_after_second = worker["cache_after_second"]
    if not cold and cache_after_first["hits"] <= worker["cache_after_warmup"]["hits"]:
        issues.append({"code": "warm_owner_bundle_cache_hit_missing"})
    if second_ran and cache_after_second["hits"] <= cache_after_first["hits"]:
        issues.append({"code": "owner_bundle_cache_hit_missing"})
    if second_wall > 5 * 60:
        issues.append(
            {
                "code": "warm_closeout_wall_time_overrun",
                "wall_time_seconds": round(second_wall, 6),
            }
        )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "lane": "cold_closeout" if cold else "warm_closeout",
        "byte_stable_passes": 2 if second_ran else 1,
        "cold_warm_byte_identical": second is not None and first_bytes == second_bytes,
        "corrupt_field_case_count": len(corrupt_report.get("results", ())),
        "cache_before": worker["cache_before"],
        "cache_after_warmup": worker["cache_after_warmup"],
        "cache_after_first": cache_after_first,
        "cache_after_second": cache_after_second,
        "effective_config": effective_config,
        "stage_heartbeats": worker["stage_heartbeats"],
        "historical_stage_comparison": tuple(comparisons),
        "first_derivation_wall_time_seconds": round(first_wall, 6),
        "cache_hit_derivation_wall_time_seconds": round(second_wall, 6),
        "cold_closeout_budget_seconds": cold_budget_seconds if cold else None,
        "cold_closeout_budget_exceeded": cold_budget_exceeded,
        "cold_closeout_budget_disposition": cold_budget_disposition,
        "warmup_derivation_wall_time_seconds": round(warmup_wall or 0.0, 6),
        "worker_startup_wall_time_seconds": round(startup_wall or 0.0, 6),
        "worker_pid": worker["worker_pid"],
        "verified_pgid": worker["verified_pgid"],
        "bootstrap_verified": worker["bootstrap_verified"],
        "profiling_ready": worker["profiling_ready"],
        "process_group_clean": worker["process_group_clean"],
        "worker_terminated": worker["worker_terminated"],
        "worker_profile": worker["worker_profile"],
        "second_pass_started": worker["second_pass_started"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    modes.add_argument("--warm-closeout", action="store_true")
    modes.add_argument("--cold-rederive", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=POLICY_ENGINE_ROOT)
    parser.add_argument("--catalog-path", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--l5-path", type=Path, default=DEFAULT_L5_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    started = time.monotonic()
    if args.source_flip_mutations:
        report = run_source_flip_mutations(root)
    elif args.warm_closeout:
        try:
            report = _run_one_process_closeout(
                root,
                catalog_path=args.catalog_path,
                l5_path=args.l5_path,
                output=output,
                cold=False,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            report = {"status": "fail", "issues": [{"code": str(exc)}]}
    elif args.cold_rederive:
        try:
            report = _run_one_process_closeout(
                root,
                catalog_path=args.catalog_path,
                l5_path=args.l5_path,
                output=output,
                cold=True,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            report = {"status": "fail", "issues": [{"code": str(exc)}]}
    elif args.write:
        try:
            report = _run_one_process_closeout(
                root,
                catalog_path=args.catalog_path,
                l5_path=args.l5_path,
                output=output,
                cold=True,
                write_output=True,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            report = {"status": "fail", "issues": [{"code": str(exc)}]}
    else:
        try:
            live, live_bytes = _derive_byte_stable_contract(
                root,
                catalog_path=args.catalog_path,
                l5_path=args.l5_path,
            )
            if args.rederive_audit:
                report = validate_payload(live, expected=live)
            elif args.corrupt_field_drift_check:
                _check_exact(output, live_bytes, "confidence_ledger_contract_drift")
                report = corrupt_field_drift_check(live)
            else:
                _check_exact(output, live_bytes, "confidence_ledger_contract_drift")
                stored = _read_contract(output)
                report = validate_payload(stored, expected=live)
            report["byte_stable_passes"] = 2
        except RuntimeError as exc:
            report = {
                "status": "fail",
                "issues": [{"code": str(exc)}],
            }
    report["wall_time_seconds"] = round(time.monotonic() - started, 6)
    if args.output_format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    elif report["status"] == "pass":
        print("layer3 GY N11 confidence ledger: pass")
    else:
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
