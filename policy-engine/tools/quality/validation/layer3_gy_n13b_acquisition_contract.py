"""Recomputing frozen contract for the GY-N13b acquisition executor.

This plan-named module is an audit composer only.  Runtime authority remains in
the canonical acquisition passport/overlay owners, the Fabric evidence journal,
the DatasetCatalogGraph read path, and the derived-observation CAS machinery.
The composer binds their narrow projections without becoming a parallel owner.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import (
    canonical_json_bytes,
    content_sha256,
    resolve_live_attempt_terminals,
    resolve_raw_response_body,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionGapType,
    AcquisitionPlannerReport,
    AcquisitionRequirementGap,
    AuthorityLevel,
    MandatoryGateState,
    RequirementGapFamily,
    plan_requirement_gap_acquisition,
)
from tools.quality.validation.layer3_gy_acquisition_executor import (
    D6RouteSelection,
    MetadataProbeExecutionEvidence,
    R1ForensicReceipt,
)
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CensusManifest,
    RecurringCarrierLivenessUpdate,
    semantic_content_hash,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    AcceptanceCaseReceipt,
    AcceptanceFallbackSelection,
    AcceptanceInputSelection,
    AcceptanceLiveExecutionReceipt,
    verify_persisted_acceptance_case,
)
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_DERIVATION_FAMILY_REGISTRY,
    DEFAULT_UNIVERSALITY_RECEIPT,
    DerivationUniversalityReceipt,
)
from tools.quality.validation.layer3_gy_n13b_reentry import N13bReentryTrace

SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
N13B_FAMILY_ID = "policy-design-case-layer3-gy-n13b-acquisition-executor"
DEFAULT_N13B_CONTRACT = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_executor_contract.json"
)
DEFAULT_N13B_LIFECYCLE_MANIFEST = Path(
    "architecture/policy_design_case/layer3_gy_n13b_lifecycle_manifest.json"
)
DEFAULT_GENERATED_ARTIFACTS = Path("architecture/generated_artifacts.toml")
DEFAULT_N13B_JOURNAL = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
)
DEFAULT_N13B_CAS = Path("architecture/policy_design_case/layer3_gy_acquisition_cas")
DEFAULT_N13B_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
DEFAULT_N13B_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_DERIVED_ACCEPTANCE = Path(
    "architecture/policy_design_case/layer3_gy_n13b_derived_acceptance_case.json"
)
DEFAULT_N13A_CENSUS = Path("architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json")
DEFAULT_CARRIER_LIVENESS = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
)
DEFAULT_R1_FORENSIC = Path(
    "architecture/policy_design_case/layer3_gy_n13b_r1_forensic_receipt.json"
)
DEFAULT_R2_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_metadata_evidence.json"
)
DEFAULT_D6_ROUTE = Path("architecture/policy_design_case/layer3_gy_n13b_d6_route_selection.json")
DEFAULT_R3_METADATA_EVIDENCE = Path(
    "architecture/policy_design_case/"
    "layer3_gy_n13b_worldbank_government_balance_percent_gdp_metadata_evidence.json"
)
DEFAULT_ACCEPTANCE_INPUTS = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_input_selection.json"
)
DEFAULT_ACCEPTANCE_EXECUTION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_cpi_live_execution_evidence.json"
)
DEFAULT_ACCEPTANCE_FALLBACK = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acceptance_fallback_selection.json"
)
DEFAULT_REENTRY_TRACE = Path("architecture/policy_design_case/layer3_gy_n13b_reentry_trace.json")
_SOURCE_OWNER_PATHS = (
    DEFAULT_DERIVATION_FAMILY_REGISTRY.as_posix(),
    "src/polisyos/data_forge/domains/catalog/knowledge/acquisition_authority.py",
    "src/polisyos/data_forge/domains/catalog/knowledge/derivation_catalog_selection.py",
    "src/polisyos/data_forge/domains/catalog/knowledge/overlay.py",
    "src/polisyos/fabric/data_plane/evidence_journal.py",
    "src/polisyos/ir/kernel/units.py",
    "src/polisyos/runtime/quality/acquisition_executor.py",
    "src/polisyos/runtime/quality/acquisition_planner.py",
    "src/polisyos/runtime/quality/data_state_substrate.py",
    "src/polisyos/runtime/quality/derived_observations.py",
    "tools/quality/validation/layer3_gy_n13b_derivation_universality.py",
)
_SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION = "policyos.layer3.gy.n13b.connector_request_lever_gap.v1"
_SOURCE_GROWTH_PLANNER_GENERATED_AT = datetime(2026, 7, 19, tzinfo=UTC)


class N13bContractError(RuntimeError):
    """Fail-closed N13b contract error with a stable code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


@dataclass(frozen=True)
class N13bGeneratedRegistryUpdate:
    """Canonical generated-artifact registry update for the live CAS closure."""

    registry_bytes: bytes
    required_cas_artifact_ids: tuple[str, ...]
    required_cas_output_paths: tuple[str, ...]
    obsolete_cas_output_paths: tuple[str, ...]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalLiftRefusalRow(_StrictModel):
    """One census residual evaluated against the canonical local-rights owner."""

    rank: int = Field(ge=1)
    variable_id: str = Field(min_length=1)
    gap_kind: Literal["binding_gap"]
    demand_sources: tuple[str, ...] = Field(min_length=1)
    admissible: bool
    rejection_codes: tuple[str, ...]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _row_is_content_bound(self) -> Self:
        if self.demand_sources != tuple(sorted(set(self.demand_sources))):
            raise ValueError("local-lift demand sources must be unique and sorted")
        if self.rejection_codes != tuple(sorted(set(self.rejection_codes))):
            raise ValueError("local-lift rejection codes must be unique and sorted")
        if self.admissible != (not self.rejection_codes):
            raise ValueError("local-lift admission must derive from owner rejection codes")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local-lift row identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class LocalLiftRefusal(_StrictModel):
    """Full 15-row local-lift denominator and its honest terminal."""

    census_growth_backlog_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    provision_id: str = Field(pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$")
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    rows: tuple[LocalLiftRefusalRow, ...] = Field(min_length=1)
    residual_denominator_count: int = Field(ge=1)
    admissible_count: int = Field(ge=0)
    disposition: Literal["no_admissible_local_binding", "local_lift_admissible"]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        ranks = tuple(row.rank for row in self.rows)
        if ranks != tuple(range(1, len(self.rows) + 1)):
            raise ValueError("local-lift rows must preserve the complete ranked denominator")
        if self.residual_denominator_count != len(self.rows):
            raise ValueError("local-lift denominator count drift")
        admissible = sum(row.admissible for row in self.rows)
        if self.admissible_count != admissible:
            raise ValueError("local-lift admissible count must be recomputed")
        expected = "local_lift_admissible" if admissible else "no_admissible_local_binding"
        if self.disposition != expected:
            raise ValueError("local-lift disposition must be recomputed")
        if self.local_rights_trust_anchor_sha256 is None and any(
            row.rejection_codes != ("local_rights_authority_unavailable",) for row in self.rows
        ):
            raise ValueError("absent local rights owner must fail every residual closed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("local-lift refusal identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_local_lift_refusal(
    *,
    census: CensusManifest,
    provision: catalog_read_api.AcquisitionAuthorityProvision,
) -> LocalLiftRefusal:
    """Evaluate every D2 residual against the independently owned rights root."""

    frozen_census = CensusManifest.model_validate(census.model_dump(mode="python"))
    frozen_provision = catalog_read_api.AcquisitionAuthorityProvision.model_validate(
        provision.model_dump(mode="python")
    )
    rows: list[LocalLiftRefusalRow] = []
    for backlog in frozen_census.growth_backlog:
        rejection_codes = (
            ("local_rights_authority_unavailable",)
            if frozen_provision.local_rights_trust_anchor_sha256 is None
            else ()
        )
        values = {
            "rank": backlog.rank,
            "variable_id": backlog.variable_id,
            "gap_kind": backlog.gap_kind.value,
            "demand_sources": backlog.demand_sources,
            "admissible": not rejection_codes,
            "rejection_codes": rejection_codes,
        }
        rows.append(
            LocalLiftRefusalRow(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    backlog_projection = [row.model_dump(mode="json") for row in frozen_census.growth_backlog]
    values = {
        "census_growth_backlog_projection_sha256": content_sha256(backlog_projection),
        "provision_id": frozen_provision.provision_id,
        "local_rights_trust_anchor_sha256": frozen_provision.local_rights_trust_anchor_sha256,
        "rows": tuple(rows),
        "residual_denominator_count": len(rows),
        "admissible_count": sum(row.admissible for row in rows),
        "disposition": (
            "local_lift_admissible"
            if any(row.admissible for row in rows)
            else "no_admissible_local_binding"
        ),
    }
    return LocalLiftRefusal(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class D2CarrierReceiptProjection(_StrictModel):
    """Narrow D3 receipt projection supplying the D2 connector-gap denominator."""

    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    execution_tier: str = Field(min_length=1)
    missing_request_levers: tuple[str, ...]
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.missing_request_levers != tuple(sorted(set(self.missing_request_levers))):
            raise ValueError("carrier request-lever denominator must be unique and sorted")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("carrier request-lever projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class D2PlannerRouteProjection(_StrictModel):
    """Timestamp-free narrow projection of one canonical N7 planner run."""

    planner_schema_version: Literal["policyos.runtime.acquisition_planner.v1"]
    run_id: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    requirement_gap_ref: str = Field(min_length=1)
    requirement_family: Literal["data_requirement"]
    compiled_requirement_ref: str = Field(min_length=1)
    requirement_schema_version: Literal["policyos.layer3.gy.n13b.connector_request_lever_gap.v1"]
    gap_type: Literal["scenario_source_family"]
    missing_requirement_fields: tuple[str, ...] = Field(min_length=1)
    report_status: Literal["pass", "warn", "blocked"]
    record_status: Literal["ready", "limited", "blocked"]
    recommended_strategy: str = Field(min_length=1)
    terminal_disposition: str = Field(min_length=1)
    eligible_strategies: tuple[str, ...] = Field(min_length=1)
    ineligible_strategies: tuple[str, ...] = Field(min_length=1)
    producer_expected: str | None = None
    producer_output_ref: str = Field(min_length=1)
    voi_ranking_ref: None = None
    voi_numeric_support: Literal[False]
    source_report_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.eligible_strategies != tuple(sorted(set(self.eligible_strategies))):
            raise ValueError("eligible strategy projection must be unique and sorted")
        if self.ineligible_strategies != tuple(sorted(set(self.ineligible_strategies))):
            raise ValueError("ineligible strategy projection must be unique and sorted")
        if set(self.eligible_strategies) & set(self.ineligible_strategies):
            raise ValueError("planner strategies cannot be both eligible and ineligible")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("N7 connector-gap planner projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class D2ConnectorGapRow(_StrictModel):
    """One family-first request-contract growth demand routed through N7."""

    rank: int = Field(ge=1)
    gap_kind: Literal["connector_gap"]
    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    missing_request_lever: str = Field(min_length=1)
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    growth_scope: Literal["connector_family_request_contract"]
    growth_mechanism: Literal["family_first_config_not_code"]
    requirement_gap: AcquisitionRequirementGap
    planner_route: D2PlannerRouteProjection
    voi_owner_integration: Literal["planner_routed_no_owner_voi_numeric_support"]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _row_is_recomputed_from_owner_outputs(self) -> Self:
        identity = _source_growth_gap_identity(
            connector_id=self.connector_id,
            request_dataset_id=self.request_dataset_id,
            missing_request_lever=self.missing_request_lever,
            source_receipt_sha256=self.source_receipt_sha256,
        )
        receipt_ref = f"carrier-liveness:{self.source_receipt_sha256}"
        expected_metadata = {
            "source": "n13a_recurring_carrier_liveness",
            "connector_id": self.connector_id,
            "request_dataset_id": self.request_dataset_id,
            "missing_request_lever": self.missing_request_lever,
            "source_receipt_sha256": self.source_receipt_sha256,
            "growth_scope": self.growth_scope,
            "growth_mechanism": self.growth_mechanism,
        }
        gap = self.requirement_gap
        if (
            gap.requirement_gap_id
            != f"requirement-gap:data_requirement:connector-request-lever:{identity}"
            or gap.requirement_family is not RequirementGapFamily.DATA
            or gap.compiled_requirement_ref
            != f"runtime-requirement:connector-request-lever:{identity}:v1"
            or gap.requirement_schema_version != _SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION
            or gap.gap_type is not AcquisitionGapType.SCENARIO_SOURCE_FAMILY
            or gap.claim_ref != f"connector-request-contract-claim:{identity}"
            or gap.scenario_requirement_refs != (receipt_ref,)
            or gap.missing_requirement_fields
            != (f"connector_request_lever:{self.missing_request_lever}",)
            or gap.authority_level is not AuthorityLevel.RESEARCH
            or gap.mandatory_gate_state is not MandatoryGateState.NONE
            or gap.mandatory_gate_refs
            or gap.limitation_permitted
            or gap.decision_owner_ref != "polisyos.runtime.quality.acquisition_planner"
            or gap.producer_output_ref != receipt_ref
            or gap.calibration_feedback_ref is not None
            or gap.metadata != expected_metadata
        ):
            raise ValueError("connector gap must recompute from its carrier request lever")
        route = self.planner_route
        if (
            route.run_id != f"gy-n13b-source-growth-{identity}"
            or route.gap_id != gap.requirement_gap_id
            or route.requirement_gap_ref != gap.requirement_gap_id
            or route.requirement_family != gap.requirement_family.value
            or route.compiled_requirement_ref != gap.compiled_requirement_ref
            or route.requirement_schema_version != gap.requirement_schema_version
            or route.gap_type != gap.gap_type.value
            or route.missing_requirement_fields != gap.missing_requirement_fields
            or route.producer_output_ref != gap.producer_output_ref
        ):
            raise ValueError("connector gap planner record must preserve the typed requirement")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("connector-gap row identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class D2SourceGrowthBacklog(_StrictModel):
    """Full recurring-receipt denominator and its N7-routed connector gaps."""

    carrier_receipts: tuple[D2CarrierReceiptProjection, ...]
    carrier_receipt_denominator_count: int = Field(ge=0)
    missing_request_lever_denominator_count: int = Field(ge=0)
    connector_gap_count: int = Field(ge=0)
    rows: tuple[D2ConnectorGapRow, ...]
    ranking_basis: Literal["family_first_config_growth_then_carrier_identity"]
    voi_owner_integration: Literal["planner_routed_no_owner_voi_numeric_support"]
    source_receipt_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _full_denominator_and_ranking_are_recomputed(self) -> Self:
        receipt_keys = tuple(
            (row.connector_id, row.request_dataset_id, row.source_receipt_sha256)
            for row in self.carrier_receipts
        )
        if receipt_keys != tuple(sorted(set(receipt_keys))):
            raise ValueError("recurring carrier receipt denominator must be unique and sorted")
        if self.carrier_receipt_denominator_count != len(self.carrier_receipts):
            raise ValueError("recurring carrier receipt denominator count drift")
        expected_gap_keys = tuple(
            sorted(
                (
                    receipt.connector_id,
                    receipt.request_dataset_id,
                    lever,
                    receipt.source_receipt_sha256,
                )
                for receipt in self.carrier_receipts
                for lever in receipt.missing_request_levers
            )
        )
        row_keys = tuple(
            (
                row.connector_id,
                row.request_dataset_id,
                row.missing_request_lever,
                row.source_receipt_sha256,
            )
            for row in self.rows
        )
        if row_keys != expected_gap_keys:
            raise ValueError("connector-gap rows must cover every recurring missing request lever")
        if tuple(row.rank for row in self.rows) != tuple(range(1, len(self.rows) + 1)):
            raise ValueError("connector-gap rows must preserve their derived rank")
        if self.missing_request_lever_denominator_count != len(
            expected_gap_keys
        ) or self.connector_gap_count != len(self.rows):
            raise ValueError("connector-gap denominator count drift")
        receipt_projection = [row.model_dump(mode="json") for row in self.carrier_receipts]
        if self.source_receipt_projection_sha256 != content_sha256(receipt_projection):
            raise ValueError("recurring carrier receipt projection identity drift")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("D2 source-growth backlog identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_d2_source_growth_backlog(
    carrier_receipts: Sequence[RecurringCarrierLivenessUpdate],
) -> D2SourceGrowthBacklog:
    """Route every recurring missing request lever through the canonical N7 owner."""

    frozen_receipts = tuple(
        RecurringCarrierLivenessUpdate.model_validate(receipt.model_dump(mode="python"))
        for receipt in carrier_receipts
    )
    receipt_shas = tuple(receipt.receipt_sha256 for receipt in frozen_receipts)
    if len(receipt_shas) != len(set(receipt_shas)):
        raise N13bContractError("duplicate_recurring_carrier_receipt")
    carrier_projections: list[D2CarrierReceiptProjection] = []
    for receipt in sorted(
        frozen_receipts,
        key=lambda value: (
            value.connector_id,
            value.request_dataset_id,
            value.receipt_sha256,
        ),
    ):
        receipt_values = {
            "connector_id": receipt.connector_id,
            "request_dataset_id": receipt.request_dataset_id,
            "execution_tier": receipt.execution_tier,
            "missing_request_levers": tuple(sorted(receipt.missing_request_levers)),
            "source_receipt_sha256": receipt.receipt_sha256,
        }
        carrier_projections.append(
            D2CarrierReceiptProjection(
                **receipt_values,
                projection_sha256=content_sha256(receipt_values),
            )
        )
    gap_sources = sorted(
        (
            receipt.connector_id,
            receipt.request_dataset_id,
            lever,
            receipt.receipt_sha256,
        )
        for receipt in frozen_receipts
        for lever in receipt.missing_request_levers
    )
    rows: list[D2ConnectorGapRow] = []
    for rank, (
        connector_id,
        request_dataset_id,
        missing_request_lever,
        source_receipt_sha256,
    ) in enumerate(gap_sources, start=1):
        identity = _source_growth_gap_identity(
            connector_id=connector_id,
            request_dataset_id=request_dataset_id,
            missing_request_lever=missing_request_lever,
            source_receipt_sha256=source_receipt_sha256,
        )
        receipt_ref = f"carrier-liveness:{source_receipt_sha256}"
        requirement_gap = AcquisitionRequirementGap(
            requirement_gap_id=(
                f"requirement-gap:data_requirement:connector-request-lever:{identity}"
            ),
            requirement_family=RequirementGapFamily.DATA,
            compiled_requirement_ref=(f"runtime-requirement:connector-request-lever:{identity}:v1"),
            requirement_schema_version=_SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION,
            gap_type=AcquisitionGapType.SCENARIO_SOURCE_FAMILY,
            claim_ref=f"connector-request-contract-claim:{identity}",
            scenario_requirement_refs=(receipt_ref,),
            missing_requirement_fields=(f"connector_request_lever:{missing_request_lever}",),
            authority_level=AuthorityLevel.RESEARCH,
            mandatory_gate_state=MandatoryGateState.NONE,
            limitation_permitted=False,
            decision_owner_ref="polisyos.runtime.quality.acquisition_planner",
            producer_output_ref=receipt_ref,
            metadata={
                "source": "n13a_recurring_carrier_liveness",
                "connector_id": connector_id,
                "request_dataset_id": request_dataset_id,
                "missing_request_lever": missing_request_lever,
                "source_receipt_sha256": source_receipt_sha256,
                "growth_scope": "connector_family_request_contract",
                "growth_mechanism": "family_first_config_not_code",
            },
        )
        planner_report = plan_requirement_gap_acquisition(
            run_id=f"gy-n13b-source-growth-{identity}",
            requirement_gaps=(requirement_gap,),
            generated_at=_SOURCE_GROWTH_PLANNER_GENERATED_AT,
        )
        planner_route = _d2_planner_route_projection(planner_report)
        row_values = {
            "rank": rank,
            "gap_kind": "connector_gap",
            "connector_id": connector_id,
            "request_dataset_id": request_dataset_id,
            "missing_request_lever": missing_request_lever,
            "source_receipt_sha256": source_receipt_sha256,
            "growth_scope": "connector_family_request_contract",
            "growth_mechanism": "family_first_config_not_code",
            "requirement_gap": requirement_gap,
            "planner_route": planner_route,
            "voi_owner_integration": "planner_routed_no_owner_voi_numeric_support",
        }
        rows.append(
            D2ConnectorGapRow(
                **row_values,
                projection_sha256=content_sha256(_json_value(row_values)),
            )
        )
    receipt_projection = [row.model_dump(mode="json") for row in carrier_projections]
    values = {
        "carrier_receipts": tuple(carrier_projections),
        "carrier_receipt_denominator_count": len(carrier_projections),
        "missing_request_lever_denominator_count": len(gap_sources),
        "connector_gap_count": len(rows),
        "rows": tuple(rows),
        "ranking_basis": "family_first_config_growth_then_carrier_identity",
        "voi_owner_integration": "planner_routed_no_owner_voi_numeric_support",
        "source_receipt_projection_sha256": content_sha256(receipt_projection),
    }
    return D2SourceGrowthBacklog(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class LiveAttemptProjection(_StrictModel):
    """Path-stable journal/CAS projection for one paid live attempt."""

    attempt_id: str = Field(min_length=1)
    request_sequence: int = Field(ge=1)
    call_class: Literal["data_fetch", "indicator_metadata"]
    request_variables: tuple[str, ...] = Field(min_length=1, max_length=1)
    request_event_sha256: str = Field(pattern=SHA256_PATTERN)
    failure_code: str = Field(min_length=1)
    outcome_code: str = Field(min_length=1)
    terminal_sha256: str = Field(pattern=SHA256_PATTERN)
    raw_evidence_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_body_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    raw_byte_count: int | None = Field(default=None, ge=0)
    raw_cas_persisted: bool
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    quarantine: Literal[True]
    response_admitted: Literal[False]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _attempt_is_content_bound(self) -> Self:
        raw = (
            self.raw_evidence_event_sha256,
            self.raw_body_sha256,
            self.raw_byte_count,
        )
        if any(value is None for value in raw) != all(value is None for value in raw):
            raise ValueError("attempt raw evidence projection must be complete or absent")
        if self.raw_body_sha256 is None and self.raw_cas_persisted:
            raise ValueError("an absent raw response cannot claim CAS persistence")
        if self.raw_body_sha256 is not None and not self.raw_cas_persisted:
            raise ValueError("journaled raw response bytes must persist in quarantine CAS")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("live-attempt projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class JournalEvidenceProjection(_StrictModel):
    """Full journal denominator proving request/terminal/raw evidence persistence."""

    journal_ref: Literal[
        "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
    ]
    journal_byte_sha256: str = Field(pattern=SHA256_PATTERN)
    event_count: int = Field(ge=1)
    request_count: int = Field(ge=1)
    terminal_count: int = Field(ge=1)
    raw_response_count: int = Field(ge=0)
    persisted_raw_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    quarantine_count: int = Field(ge=0)
    attempts: tuple[LiveAttemptProjection, ...] = Field(min_length=1)
    journal_raw_evidence_persistence_missing_closed: bool
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _denominator_is_recomputed(self) -> Self:
        attempts = self.attempts
        if tuple(row.request_sequence for row in attempts) != tuple(
            sorted(row.request_sequence for row in attempts)
        ):
            raise ValueError("live attempts must preserve journal request order")
        if len({row.attempt_id for row in attempts}) != len(attempts):
            raise ValueError("live attempt denominator contains duplicates")
        expected_raw = sum(row.raw_body_sha256 is not None for row in attempts)
        expected_persisted = sum(row.raw_cas_persisted for row in attempts)
        expected_admitted = sum(row.response_admitted for row in attempts)
        expected_quarantine = sum(row.quarantine for row in attempts)
        if (
            self.request_count != len(attempts)
            or self.terminal_count != len(attempts)
            or self.raw_response_count != expected_raw
            or self.persisted_raw_response_count != expected_persisted
            or self.response_admitted_count != expected_admitted
            or self.quarantine_count != expected_quarantine
        ):
            raise ValueError("journal evidence counts must cover the complete attempt denominator")
        expected_closed = (
            self.request_count == self.terminal_count
            and self.raw_response_count == self.persisted_raw_response_count
            and self.response_admitted_count == 0
        )
        if self.journal_raw_evidence_persistence_missing_closed != expected_closed:
            raise ValueError("journal persistence residual must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("journal projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_journal_evidence_projection(
    *,
    journal_path: Path,
    cas_root: Path,
) -> JournalEvidenceProjection:
    """Reopen every exact request/terminal and bind raw bytes into quarantine CAS."""

    journal = Path(journal_path)
    events = _read_canonical_jsonl(journal)
    terminals = resolve_live_attempt_terminals(journal)
    requests = {
        int(event["sequence"]): event for event in events if event.get("event_kind") == "request"
    }
    if len(requests) != len(terminals):
        raise N13bContractError("journal_attempt_denominator_incomplete")
    rows: list[LiveAttemptProjection] = []
    for terminal in terminals:
        request_event = requests.get(terminal.request_ref.sequence)
        if request_event is None or request_event.get("attempt_id") != terminal.attempt_id:
            raise N13bContractError("journal_terminal_request_unresolved", terminal.attempt_id)
        request = request_event.get("request")
        if not isinstance(request, dict):
            raise N13bContractError("journal_request_payload_invalid", terminal.attempt_id)
        request_variables = request.get("request_variables")
        if not isinstance(request_variables, list) or len(request_variables) != 1:
            raise N13bContractError("journal_request_variable_budget_drift", terminal.attempt_id)
        call_class = (
            "indicator_metadata"
            if request.get("call_class") == "indicator_metadata"
            else "data_fetch"
        )
        raw_body: bytes | None = None
        raw_body_sha: str | None = None
        raw_byte_count: int | None = None
        raw_event_sha: str | None = None
        raw_persisted = False
        if terminal.raw_evidence_ref is not None:
            raw_body = resolve_raw_response_body(terminal.raw_evidence_ref)
            raw_body_sha = _bytes_sha256(raw_body)
            raw_byte_count = len(raw_body)
            raw_event_sha = terminal.raw_evidence_ref.event_sha256
            blob = _cas_blob_path(Path(cas_root), raw_body_sha)
            raw_persisted = blob.is_file() and _file_sha256(blob) == raw_body_sha
        values = {
            "attempt_id": terminal.attempt_id,
            "request_sequence": terminal.request_ref.sequence,
            "call_class": call_class,
            "request_variables": tuple(str(value) for value in request_variables),
            "request_event_sha256": terminal.request_ref.event_sha256,
            "failure_code": terminal.failure_code,
            "outcome_code": terminal.outcome_code,
            "terminal_sha256": terminal.terminal_sha256,
            "raw_evidence_event_sha256": raw_event_sha,
            "raw_body_sha256": raw_body_sha,
            "raw_byte_count": raw_byte_count,
            "raw_cas_persisted": raw_persisted,
            "http_status_code": terminal.http_status_code,
            "quarantine": terminal.quarantine,
            "response_admitted": terminal.response_admitted,
        }
        rows.append(
            LiveAttemptProjection(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    values = {
        "journal_ref": (
            "repo://architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        "journal_byte_sha256": _file_sha256(journal),
        "event_count": len(events),
        "request_count": len(requests),
        "terminal_count": len(terminals),
        "raw_response_count": sum(row.raw_body_sha256 is not None for row in rows),
        "persisted_raw_response_count": sum(row.raw_cas_persisted for row in rows),
        "response_admitted_count": sum(row.response_admitted for row in rows),
        "quarantine_count": sum(row.quarantine for row in rows),
        "attempts": tuple(rows),
        "journal_raw_evidence_persistence_missing_closed": (
            len(requests) == len(terminals)
            and all(row.raw_body_sha256 is None or row.raw_cas_persisted for row in rows)
            and not any(row.response_admitted for row in rows)
        ),
    }
    return JournalEvidenceProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


def derive_cas_artifact_closure(
    cas_root: Path,
    root_artifact_ids: Sequence[str],
) -> tuple[str, ...]:
    """Resolve and content-validate the complete CAS input graph from exact roots."""

    roots = tuple(sorted({str(value) for value in root_artifact_ids}))
    if not roots:
        raise N13bContractError("n13b_cas_root_denominator_empty")
    pending = list(reversed(roots))
    visited: set[str] = set()
    while pending:
        artifact_id = pending.pop()
        if artifact_id in visited:
            continue
        _require_artifact_id(artifact_id)
        blob = _cas_blob_path(Path(cas_root), artifact_id)
        manifest_path = _cas_manifest_path(Path(cas_root), artifact_id)
        if not blob.is_file() or not manifest_path.is_file():
            raise N13bContractError("n13b_cas_artifact_missing", artifact_id)
        if _file_sha256(blob) != artifact_id:
            raise N13bContractError("n13b_cas_blob_content_drift", artifact_id)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise N13bContractError("n13b_cas_manifest_invalid", artifact_id) from exc
        if not isinstance(manifest, dict) or manifest.get("artifact_id") != artifact_id:
            raise N13bContractError("n13b_cas_manifest_identity_drift", artifact_id)
        digest = artifact_id.removeprefix("sha256:")
        integrity = manifest.get("integrity")
        if (
            not isinstance(integrity, dict)
            or integrity.get("sha256") not in {digest, artifact_id}
            or manifest.get("byte_size") != blob.stat().st_size
        ):
            raise N13bContractError("n13b_cas_manifest_integrity_drift", artifact_id)
        inputs = manifest.get("inputs")
        if not isinstance(inputs, list):
            raise N13bContractError("n13b_cas_manifest_inputs_invalid", artifact_id)
        input_ids: list[str] = []
        for row in inputs:
            if not isinstance(row, dict) or not isinstance(row.get("artifact_id"), str):
                raise N13bContractError("n13b_cas_manifest_input_invalid", artifact_id)
            input_id = str(row["artifact_id"])
            _require_artifact_id(input_id)
            input_ids.append(input_id)
        visited.add(artifact_id)
        pending.extend(
            reversed(
                tuple(sorted(input_id for input_id in set(input_ids) if input_id not in visited))
            )
        )
    return tuple(sorted(visited))


def derive_n13b_generated_registry_update(repo_root: Path) -> N13bGeneratedRegistryUpdate:
    """Derive the exact N13b CAS closure and its registry-only textual update."""

    root = Path(repo_root)
    acceptance = _read_model(root / DEFAULT_DERIVED_ACCEPTANCE, AcceptanceCaseReceipt)
    journal = derive_journal_evidence_projection(
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    raw_artifact_ids = tuple(
        str(row.raw_body_sha256) for row in journal.attempts if row.raw_body_sha256 is not None
    )
    artifact_ids = derive_cas_artifact_closure(
        root / DEFAULT_N13B_CAS,
        (*raw_artifact_ids, acceptance.certificate_artifact_id),
    )
    required_paths = tuple(
        sorted(
            path
            for artifact_id in artifact_ids
            for path in (
                _cas_blob_relative(artifact_id),
                _cas_manifest_relative(artifact_id),
            )
        )
    )
    registry_path = root / DEFAULT_GENERATED_ARTIFACTS
    try:
        original = registry_path.read_bytes()
        parsed = tomllib.loads(original.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    family, other_output_paths = _n13b_generated_family(parsed)
    output_values = family.get("outputs")
    if not isinstance(output_values, list) or not output_values:
        raise N13bContractError("n13b_generated_outputs_missing")
    current_outputs = tuple(str(value) for value in output_values)
    cas_prefix = (DEFAULT_N13B_CAS / "artifacts/sha256").as_posix() + "/"
    non_cas_outputs = tuple(path for path in current_outputs if not path.startswith(cas_prefix))
    next_outputs = tuple(sorted((*non_cas_outputs, *required_paths)))
    registry_bytes = _replace_n13b_generated_outputs(original, next_outputs)
    stale = set(current_outputs) - set(next_outputs)
    removable_stale = tuple(
        sorted(
            path for path in stale if path.startswith(cas_prefix) and path not in other_output_paths
        )
    )
    return N13bGeneratedRegistryUpdate(
        registry_bytes=registry_bytes,
        required_cas_artifact_ids=artifact_ids,
        required_cas_output_paths=required_paths,
        obsolete_cas_output_paths=removable_stale,
    )


def _n13b_generated_family(
    parsed: Mapping[str, Any],
) -> tuple[Mapping[str, Any], frozenset[str]]:
    families = parsed.get("family")
    if not isinstance(families, list):
        raise N13bContractError("n13b_generated_family_unresolved")
    matches = [row for row in families if isinstance(row, dict) and row.get("id") == N13B_FAMILY_ID]
    if len(matches) != 1:
        raise N13bContractError("n13b_generated_family_unresolved")
    other_outputs = frozenset(
        str(output)
        for row in families
        if isinstance(row, dict) and row.get("id") != N13B_FAMILY_ID
        for output in (row.get("outputs") or ())
    )
    return matches[0], other_outputs


def _replace_n13b_generated_outputs(
    registry_bytes: bytes,
    outputs: Sequence[str],
) -> bytes:
    """Replace only the N13b family output list while preserving all other bytes."""

    try:
        text = registry_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "[[family]]"]
    starts.append(len(lines))
    matching_blocks: list[tuple[int, int]] = []
    id_pattern = re.compile(r'id\s*=\s*"' + re.escape(N13B_FAMILY_ID) + r'"\s*')
    for start, end in pairwise(starts):
        if any(id_pattern.fullmatch(line.strip()) for line in lines[start:end]):
            matching_blocks.append((start, end))
    if len(matching_blocks) != 1:
        raise N13bContractError("n13b_generated_family_unresolved")
    start, end = matching_blocks[0]
    output_starts = [
        index
        for index in range(start, end)
        if re.fullmatch(r"outputs\s*=\s*\[\s*", lines[index].strip())
    ]
    if len(output_starts) != 1:
        raise N13bContractError("n13b_generated_outputs_missing")
    output_start = output_starts[0]
    output_ends = [index for index in range(output_start + 1, end) if lines[index].strip() == "]"]
    if not output_ends:
        raise N13bContractError("n13b_generated_outputs_missing")
    output_end = output_ends[0]
    newline = "\r\n" if lines[output_start].endswith("\r\n") else "\n"
    replacement = [lines[output_start]]
    replacement.extend(f"  {json.dumps(path)}," + newline for path in outputs)
    replacement.append(lines[output_end])
    rewritten = "".join((*lines[:output_start], *replacement, *lines[output_end + 1 :])).encode()
    try:
        before = tomllib.loads(text)
        after = tomllib.loads(rewritten.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    before_family, _before_other = _n13b_generated_family(before)
    after_family, _after_other = _n13b_generated_family(after)
    before_without_outputs = {
        key: value for key, value in before_family.items() if key != "outputs"
    }
    after_without_outputs = {key: value for key, value in after_family.items() if key != "outputs"}
    if before_without_outputs != after_without_outputs or after_family.get("outputs") != list(
        outputs
    ):
        raise N13bContractError("n13b_generated_registry_update_scope_drift")
    before_others = [row for row in before["family"] if row.get("id") != N13B_FAMILY_ID]
    after_others = [row for row in after["family"] if row.get("id") != N13B_FAMILY_ID]
    if before_others != after_others:
        raise N13bContractError("n13b_generated_registry_update_scope_drift")
    return rewritten


def _require_artifact_id(artifact_id: str) -> None:
    if re.fullmatch(SHA256_PATTERN, artifact_id) is None:
        raise N13bContractError("n13b_cas_artifact_id_invalid", artifact_id)


class DerivationProjection(_StrictModel):
    """Narrow D4–D6 acceptance projection over one verified CAS recipe."""

    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    recipe_projection: dict[str, Any]
    recipe_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    nominal_artifact_id: str = Field(pattern=SHA256_PATTERN)
    deflator_artifact_id: str = Field(pattern=SHA256_PATTERN)
    derived_artifact_id: str = Field(pattern=SHA256_PATTERN)
    certificate_artifact_id: str = Field(pattern=SHA256_PATTERN)
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    consumer_method_ids: tuple[str, str]
    consumer_count: Literal[2]
    distinct_consumer_count: Literal[2]
    observation_class: Literal["derived"]
    effective_authority: str = Field(min_length=1)
    basis_mismatch_refusal_code: Literal["basis_mismatch"]
    model_output_observation_rejection_codes: tuple[
        Literal["model_output_not_observation"],
        ...,
    ]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _acceptance_is_content_bound(self) -> Self:
        if self.recipe_projection.get("recipe_id") != self.recipe_id:
            raise ValueError("derivation projection recipe identity drift")
        if self.recipe_projection_sha256 != content_sha256(self.recipe_projection):
            raise ValueError("derivation recipe projection hash drift")
        if self.consumer_method_ids != tuple(sorted(set(self.consumer_method_ids))):
            raise ValueError("derivation consumers must be distinct and sorted")
        if self.consumer_count != len(self.consumer_method_ids) or (
            self.distinct_consumer_count != len(set(self.consumer_method_ids))
        ):
            raise ValueError("derivation consumer denominator drift")
        if self.model_output_observation_rejection_codes != ("model_output_not_observation",):
            raise ValueError("class-(iv) output must fail observation admission closed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("derivation projection identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_derivation_projection(
    *,
    acceptance: AcceptanceCaseReceipt,
    cas_root: Path,
) -> DerivationProjection:
    """Reopen the CAS graph and bind the exact recipe/consumer acceptance case."""

    frozen = AcceptanceCaseReceipt.model_validate(acceptance.model_dump(mode="python"))
    store = artifacts.FileSystemCAS(Path(cas_root))
    verify_persisted_acceptance_case(store, frozen)
    recipe = frozen.recipe.model_dump(mode="json")
    consumers = tuple(sorted(row.consumer_method_id for row in frozen.consumers))
    values = {
        "recipe_id": frozen.recipe.recipe_id,
        "recipe_projection": recipe,
        "recipe_projection_sha256": content_sha256(recipe),
        "nominal_artifact_id": frozen.nominal_series_artifact_id,
        "deflator_artifact_id": frozen.deflator_series_artifact_id,
        "derived_artifact_id": frozen.derived_artifact_id,
        "certificate_artifact_id": frozen.certificate_artifact_id,
        "first_materialization_cache_hit": frozen.first_materialization_cache_hit,
        "second_materialization_cache_hit": frozen.second_materialization_cache_hit,
        "consumer_method_ids": consumers,
        "consumer_count": len(frozen.consumers),
        "distinct_consumer_count": len(set(consumers)),
        "observation_class": frozen.certificate.observation_class,
        "effective_authority": str(frozen.certificate.effective_authority),
        "basis_mismatch_refusal_code": frozen.basis_mismatch_refusal_code,
        "model_output_observation_rejection_codes": (
            frozen.model_output_observation_rejection_codes
        ),
    }
    return DerivationProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class UniversalityFamilyProjection(_StrictModel):
    """Narrow proof that one data-registered family used the generic owner."""

    family_id: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    family_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    recipe_id: str = Field(pattern=r"^derivation-recipe:sha256:[0-9a-f]{64}$")
    recipe_sha256: str = Field(pattern=SHA256_PATTERN)
    certificate_artifact_id: str = Field(pattern=SHA256_PATTERN)
    derived_artifact_id: str = Field(pattern=SHA256_PATTERN)
    selected_role_projection_sha256s: tuple[str, ...] = Field(min_length=1)
    parameter_rule_operators: tuple[str, ...]
    assumption_names: tuple[str, ...] = Field(min_length=1)
    first_materialization_cache_hit: Literal[False]
    second_materialization_cache_hit: Literal[True]
    fresh_cas_rebuild_equal: Literal[True]
    monotone_authority_proven: Literal[True]
    observation_class: Literal["derived"]
    family_proof_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _family_projection_is_canonical(self) -> Self:
        if self.selected_role_projection_sha256s != tuple(
            sorted(set(self.selected_role_projection_sha256s))
        ):
            raise ValueError("universality role projections must be unique and sorted")
        if self.assumption_names != tuple(sorted(set(self.assumption_names))):
            raise ValueError("universality assumption names must be unique and sorted")
        return self


class DerivationUniversalityProjection(_StrictModel):
    """Projection-scoped A1–A5 proof over the full transform-family registry."""

    registry_ref: str = Field(min_length=1)
    registry_sha256: str = Field(pattern=SHA256_PATTERN)
    source_epoch: Literal[0]
    full_series_denominator_count: int = Field(ge=1)
    family_count: int = Field(ge=1)
    families: tuple[UniversalityFamilyProjection, ...] = Field(min_length=1)
    unregistered_basis_refusal_code: Literal["basis_mismatch"]
    unregistered_basis_refusal_reason: Literal["no_certified_transform"]
    network_call_count: Literal[0]
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_denominator_is_recomputed(self) -> Self:
        family_identities = tuple((row.family_id, row.method_version) for row in self.families)
        if family_identities != tuple(sorted(set(family_identities))):
            raise ValueError("universality family denominator must be unique and sorted")
        if self.family_count != len(self.families):
            raise ValueError("universality family count must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("derivation universality projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_derivation_universality_projection(
    receipt: DerivationUniversalityReceipt,
) -> DerivationUniversalityProjection:
    """Bind only decisive genericity fields from the recomputing receipt."""

    frozen = DerivationUniversalityReceipt.model_validate(receipt.model_dump(mode="python"))
    rows = tuple(
        UniversalityFamilyProjection(
            family_id=proof.family_id,
            method_version=proof.method_version,
            family_projection_sha256=proof.family_projection_sha256,
            recipe_id=proof.recipe.recipe_id,
            recipe_sha256=proof.recipe_sha256,
            certificate_artifact_id=proof.certificate_artifact_id,
            derived_artifact_id=proof.derived_artifact_id,
            selected_role_projection_sha256s=tuple(
                sorted(selection.selected.projection_sha256 for selection in proof.selections)
            ),
            parameter_rule_operators=tuple(
                parameter.rule.operator for parameter in proof.recipe.parameters
            ),
            assumption_names=tuple(
                sorted(assumption.name for assumption in proof.recipe.assumptions)
            ),
            first_materialization_cache_hit=proof.first_materialization_cache_hit,
            second_materialization_cache_hit=proof.second_materialization_cache_hit,
            fresh_cas_rebuild_equal=proof.fresh_cas_rebuild_equal,
            monotone_authority_proven=proof.monotone_authority_proven,
            observation_class=proof.certificate.observation_class,
            family_proof_sha256=proof.proof_sha256,
        )
        for proof in frozen.family_proofs
    )
    values = {
        "registry_ref": frozen.registry_ref,
        "registry_sha256": frozen.registry_sha256,
        "source_epoch": frozen.source_epoch,
        "full_series_denominator_count": frozen.full_series_denominator_count,
        "family_count": frozen.family_count,
        "families": rows,
        "unregistered_basis_refusal_code": frozen.unregistered_basis_refusal_code,
        "unregistered_basis_refusal_reason": frozen.unregistered_basis_refusal_reason,
        "network_call_count": frozen.network_call_count,
        "source_receipt_sha256": frozen.receipt_sha256,
    }
    return DerivationUniversalityProjection(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class CapstoneRouteRow(_StrictModel):
    """Decisive N13a route fields sufficient to recompute its class."""

    route_id: str = Field(min_length=1)
    witness_kind: str = Field(min_length=1)
    row_addressable_variable: str | None
    row_addressable_local_observation_count: int | None = Field(default=None, ge=0)
    row_addressable_executable_binding_count: int | None = Field(default=None, ge=0)
    missing_link: str = Field(min_length=1)
    route_class: Literal[
        "local_lift",
        "live_fetchable",
        "not_a_data_gap",
        "unresolved",
    ]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _route_class_is_recomputed(self) -> Self:
        if self.witness_kind != "owner_data_gap":
            expected = "not_a_data_gap"
        elif self.row_addressable_variable is None:
            raise ValueError("owner data gap requires a row-addressable variable")
        elif (self.row_addressable_local_observation_count or 0) > 0:
            expected = "local_lift"
        elif (self.row_addressable_executable_binding_count or 0) > 0:
            expected = "live_fetchable"
        else:
            expected = "unresolved"
        if self.route_class != expected:
            raise ValueError("capstone route class must be recomputed from decisive evidence")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("capstone route projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class CapstoneRoutePreservation(_StrictModel):
    """Three-route N13a fence proving no data-support laundering."""

    source_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    routes: tuple[CapstoneRouteRow, ...] = Field(min_length=3, max_length=3)
    route_count: Literal[3]
    laundered_route_count: int = Field(ge=0)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _denominator_and_fence_are_recomputed(self) -> Self:
        route_ids = tuple(row.route_id for row in self.routes)
        if route_ids != tuple(sorted(set(route_ids))):
            raise ValueError("capstone route denominator must be unique and sorted")
        if self.route_count != len(self.routes):
            raise ValueError("capstone route count drift")
        laundered = sum(row.route_class != "not_a_data_gap" for row in self.routes)
        if self.laundered_route_count != laundered:
            raise ValueError("capstone route laundering count must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("capstone preservation identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


def derive_capstone_route_preservation(census: CensusManifest) -> CapstoneRoutePreservation:
    """Project only decisive route-class inputs from the validated N13a census."""

    frozen = CensusManifest.model_validate(census.model_dump(mode="python"))
    rows: list[CapstoneRouteRow] = []
    for evidence in frozen.route_evidence:
        supply = evidence.row_addressable_supply
        values = {
            "route_id": evidence.route.route_id,
            "witness_kind": evidence.route.witness_kind,
            "row_addressable_variable": evidence.route.row_addressable_variable,
            "row_addressable_local_observation_count": (
                supply.local_observation_count if supply is not None else None
            ),
            "row_addressable_executable_binding_count": (
                supply.executable_binding_count if supply is not None else None
            ),
            "missing_link": evidence.route.missing_link,
            "route_class": evidence.route_class.value,
        }
        rows.append(
            CapstoneRouteRow(
                **values,
                projection_sha256=content_sha256(values),
            )
        )
    rows = sorted(rows, key=lambda row: row.route_id)
    values = {
        "source_projection_sha256": semantic_content_hash(frozen.route_evidence),
        "routes": tuple(rows),
        "route_count": len(rows),
        "laundered_route_count": sum(row.route_class != "not_a_data_gap" for row in rows),
    }
    return CapstoneRoutePreservation(
        **values,
        projection_sha256=content_sha256(_json_value(values)),
    )


class LifecycleRegistration(_StrictModel):
    """One exact output row from the generated-artifact family denominator."""

    path: str = Field(min_length=1)
    role: Literal[
        "writer_managed",
        "journal",
        "cas_blob",
        "cas_manifest",
        "provision",
        "registry",
        "receipt",
    ]
    registration_status: Literal["writer_managed", "content_bound"]
    byte_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    byte_size: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _registration_is_well_formed(self) -> Self:
        if self.registration_status == "writer_managed":
            if self.role != "writer_managed" or self.byte_sha256 is not None:
                raise ValueError("writer-managed outputs cannot self-bind content")
        elif self.role == "writer_managed" or self.byte_sha256 is None or self.byte_size is None:
            raise ValueError("content-bound lifecycle output is incomplete")
        return self


class N13bLifecycleManifest(_StrictModel):
    """Acyclic lifecycle registration for all materialized N13b outputs."""

    schema_version: Literal["policyos.layer3.gy.n13b.lifecycle_manifest.v2"] = (
        "policyos.layer3.gy.n13b.lifecycle_manifest.v2"
    )
    generated_family_id: Literal["policy-design-case-layer3-gy-n13b-acquisition-executor"]
    generated_family_projection_sha256: str = Field(pattern=SHA256_PATTERN)
    registrations: tuple[LifecycleRegistration, ...] = Field(min_length=1)
    registered_output_count: int = Field(ge=1)
    content_bound_output_count: int = Field(ge=1)
    phantom_output_count: int = Field(ge=0)
    materialized_acquired_snapshot_count: int = Field(ge=0)
    registered_acquired_snapshot_count: int = Field(ge=0)
    canonical_provision_registered: bool
    derived_artifact_registered: bool
    derivation_certificate_registered: bool
    universality_receipt_registered: bool
    owner_registration_derivation_missing_closed: bool
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _closure_is_recomputed(self) -> Self:
        paths = tuple(row.path for row in self.registrations)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("lifecycle output denominator must be unique and sorted")
        content_bound = sum(
            row.registration_status == "content_bound" for row in self.registrations
        )
        if (
            self.registered_output_count != len(self.registrations)
            or self.content_bound_output_count != content_bound
        ):
            raise ValueError("lifecycle registration counts must be recomputed")
        expected_closed = (
            self.phantom_output_count == 0
            and self.materialized_acquired_snapshot_count == self.registered_acquired_snapshot_count
            and self.canonical_provision_registered
            and self.derived_artifact_registered
            and self.derivation_certificate_registered
            and self.universality_receipt_registered
        )
        if self.owner_registration_derivation_missing_closed != expected_closed:
            raise ValueError("owner-registration residual must be recomputed")
        if self.manifest_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("lifecycle manifest identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        value = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "manifest_sha256"
        }
        value["registrations"] = [
            {
                "path": row.path,
                "role": row.role,
                "registration_status": row.registration_status,
            }
            for row in self.registrations
        ]
        return value


def derive_lifecycle_manifest(
    repo_root: Path,
    *,
    derived_artifact_id: str | None = None,
    certificate_artifact_id: str | None = None,
    prospective_outputs: Mapping[str, bytes] | None = None,
    generated_artifacts_bytes: bytes | None = None,
    required_cas_artifact_ids: Sequence[str] | None = None,
) -> N13bLifecycleManifest:
    """Derive lifecycle registrations from the real generated-artifact family."""

    root = Path(repo_root)
    if derived_artifact_id is None or certificate_artifact_id is None:
        acceptance = _read_model(
            root / DEFAULT_DERIVED_ACCEPTANCE,
            AcceptanceCaseReceipt,
        )
        derived_artifact_id = acceptance.derived_artifact_id
        certificate_artifact_id = acceptance.certificate_artifact_id
    generated_path = root / DEFAULT_GENERATED_ARTIFACTS
    try:
        registry_bytes = (
            generated_artifacts_bytes
            if generated_artifacts_bytes is not None
            else generated_path.read_bytes()
        )
        payload = tomllib.loads(registry_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise N13bContractError("generated_artifact_registry_unreadable") from exc
    families = [
        row
        for row in payload.get("family", [])
        if isinstance(row, dict) and row.get("id") == N13B_FAMILY_ID
    ]
    if len(families) != 1:
        raise N13bContractError("n13b_generated_family_unresolved")
    family = families[0]
    output_values = family.get("outputs")
    if not isinstance(output_values, list) or not output_values:
        raise N13bContractError("n13b_generated_outputs_missing")
    outputs = tuple(sorted(str(value) for value in output_values))
    if len(outputs) != len(set(outputs)):
        raise N13bContractError("n13b_generated_outputs_duplicate")
    if required_cas_artifact_ids is not None:
        expected_cas_outputs = {
            path
            for artifact_id in required_cas_artifact_ids
            for path in (
                _cas_blob_relative(str(artifact_id)),
                _cas_manifest_relative(str(artifact_id)),
            )
        }
        cas_prefix = (DEFAULT_N13B_CAS / "artifacts/sha256").as_posix() + "/"
        registered_cas_outputs = {path for path in outputs if path.startswith(cas_prefix)}
        if registered_cas_outputs != expected_cas_outputs:
            raise N13bContractError("n13b_generated_cas_output_denominator_drift")
    writer_paths = {
        DEFAULT_N13B_CONTRACT.as_posix(),
        DEFAULT_N13B_LIFECYCLE_MANIFEST.as_posix(),
    }
    prospective = dict(prospective_outputs or {})
    if set(prospective) - set(outputs):
        raise N13bContractError("n13b_prospective_output_not_registered")
    registrations: list[LifecycleRegistration] = []
    phantom = 0
    for relative in outputs:
        path = root / relative
        if relative in writer_paths:
            registrations.append(
                LifecycleRegistration(
                    path=relative,
                    role="writer_managed",
                    registration_status="writer_managed",
                    byte_sha256=None,
                    byte_size=None,
                )
            )
            continue
        if relative in prospective:
            payload = prospective[relative]
            registrations.append(
                LifecycleRegistration(
                    path=relative,
                    role=_lifecycle_role(relative),
                    registration_status="content_bound",
                    byte_sha256=_bytes_sha256(payload),
                    byte_size=len(payload),
                )
            )
            continue
        if not path.is_file():
            phantom += 1
            continue
        registrations.append(
            LifecycleRegistration(
                path=relative,
                role=_lifecycle_role(relative),
                registration_status="content_bound",
                byte_sha256=_file_sha256(path),
                byte_size=path.stat().st_size,
            )
        )
    registration_paths = {row.path for row in registrations}
    derived_path = _cas_blob_relative(derived_artifact_id)
    certificate_path = _cas_blob_relative(certificate_artifact_id)
    snapshots = tuple(
        path
        for path in outputs
        if "snapshot" in Path(path).name or "overlay.duckdb" in Path(path).name
    )
    materialized_snapshots = tuple(path for path in snapshots if (root / path).is_file())
    family_projection = {
        key: family.get(key)
        for key in (
            "id",
            "lifecycle",
            "gy_lifecycle_family",
            "generator",
            "verifier",
            "promotion_target",
            "stale_output_behavior",
            "source_of_truth",
            "outputs",
            "regenerate_commands",
            "workflow",
            "check_command",
        )
    }
    values = {
        "schema_version": "policyos.layer3.gy.n13b.lifecycle_manifest.v2",
        "generated_family_id": N13B_FAMILY_ID,
        "generated_family_projection_sha256": content_sha256(family_projection),
        "registrations": tuple(sorted(registrations, key=lambda row: row.path)),
        "registered_output_count": len(registrations),
        "content_bound_output_count": sum(
            row.registration_status == "content_bound" for row in registrations
        ),
        "phantom_output_count": phantom,
        "materialized_acquired_snapshot_count": len(materialized_snapshots),
        "registered_acquired_snapshot_count": sum(
            path in registration_paths for path in materialized_snapshots
        ),
        "canonical_provision_registered": DEFAULT_N13B_PROVISION.as_posix() in registration_paths,
        "derived_artifact_registered": derived_path in registration_paths,
        "derivation_certificate_registered": certificate_path in registration_paths,
        "universality_receipt_registered": (
            DEFAULT_UNIVERSALITY_RECEIPT.as_posix() in registration_paths
        ),
        "owner_registration_derivation_missing_closed": False,
    }
    values["owner_registration_derivation_missing_closed"] = (
        phantom == 0
        and len(materialized_snapshots)
        == sum(path in registration_paths for path in materialized_snapshots)
        and values["canonical_provision_registered"]
        and values["derived_artifact_registered"]
        and values["derivation_certificate_registered"]
        and values["universality_receipt_registered"]
    )
    identity = _json_value(values)
    identity["registrations"] = [
        {
            "path": row.path,
            "role": row.role,
            "registration_status": row.registration_status,
        }
        for row in values["registrations"]
    ]
    return N13bLifecycleManifest(**values, manifest_sha256=content_sha256(identity))


class EvidenceBinding(_StrictModel):
    """One validated source receipt with semantic and byte identities separated."""

    path: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    content_identity: str = Field(min_length=1)
    file_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)


class SourceOwnerBinding(_StrictModel):
    """Exact committed source owner participating in the executor chain."""

    path: str = Field(min_length=1)
    file_sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(ge=1)


class AuthorityOwnerProjection(_StrictModel):
    """Canonical acquisition provision/registry projection."""

    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_content_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_entry_count: int = Field(ge=1)
    provision_id: str = Field(pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$")
    live_harness_receipt_count: int = Field(ge=1)
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("acquisition authority projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class CarrierLivenessProjection(_StrictModel):
    """D3 carrier disposition and tier-decay projection from the recurring owner."""

    connector_id: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    execution_tier: str = Field(min_length=1)
    data_disposition: str = Field(min_length=1)
    metadata_disposition: str = Field(min_length=1)
    carrier_disposition: str = Field(min_length=1)
    data_attempt_count: int = Field(ge=1)
    metadata_attempt_count: int = Field(ge=0, le=1)
    tier_decay_findings: tuple[str, ...]
    source_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _projection_is_content_bound(self) -> Self:
        if self.tier_decay_findings != tuple(sorted(set(self.tier_decay_findings))):
            raise ValueError("tier-decay findings must be unique and sorted")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("carrier liveness projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ReentryProjection(_StrictModel):
    """Narrow real N7/catalog/runtime availability re-entry result."""

    target_variable: str = Field(min_length=1)
    trace_sha256: str = Field(pattern=SHA256_PATTERN)
    availability_count_before: int = Field(ge=0)
    availability_count_after: int = Field(ge=0)
    availability_count_delta: int
    overlay_epoch_count: int = Field(ge=0)
    overlay_admitted_observation_count: int = Field(ge=0)
    fetch_plan_count: int = Field(ge=0)
    fetch_plan_execution_count: Literal[0]
    reentry_disposition: str = Field(min_length=1)
    world_growth_status: Literal["grew", "no_growth"]
    world_growth_event_count: int = Field(ge=0, le=1)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _growth_is_recomputed(self) -> Self:
        if self.availability_count_delta != (
            self.availability_count_after - self.availability_count_before
        ):
            raise ValueError("re-entry availability delta drift")
        expected_count = int(
            self.availability_count_delta > 0
            and self.overlay_admitted_observation_count > 0
            and self.overlay_epoch_count > 0
        )
        if self.world_growth_event_count != expected_count or self.world_growth_status != (
            "grew" if expected_count else "no_growth"
        ):
            raise ValueError("re-entry world growth must derive from runtime availability")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("re-entry projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class QuarantineProjection(_StrictModel):
    """What arrived but did not enter the canonical observation overlay."""

    live_attempt_count: int = Field(ge=1)
    raw_response_count: int = Field(ge=0)
    terminal_without_response_count: int = Field(ge=0)
    response_admitted_count: int = Field(ge=0)
    overlay_admitted_observation_count: int = Field(ge=0)
    failure_code_counts: dict[str, int]
    disposition: Literal["all_live_evidence_quarantined_or_terminal", "admitted"]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _disposition_is_recomputed(self) -> Self:
        if any(value < 0 for value in self.failure_code_counts.values()):
            raise ValueError("quarantine failure counts must be nonnegative")
        if sum(self.failure_code_counts.values()) != self.live_attempt_count:
            raise ValueError("quarantine reasons must cover every attempt")
        if self.raw_response_count + self.terminal_without_response_count != (
            self.live_attempt_count
        ):
            raise ValueError("quarantine response denominator drift")
        admitted = self.response_admitted_count + self.overlay_admitted_observation_count
        expected = "admitted" if admitted else "all_live_evidence_quarantined_or_terminal"
        if self.disposition != expected:
            raise ValueError("quarantine disposition must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("quarantine projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class WorldGrowthProjection(_StrictModel):
    """True acquisition world-growth outcome, including honest zero."""

    target_variable: str = Field(min_length=1)
    availability_count_before: int = Field(ge=0)
    availability_count_after: int = Field(ge=0)
    availability_count_delta: int
    overlay_epoch_count: int = Field(ge=0)
    admitted_observation_count: int = Field(ge=0)
    event_count: int = Field(ge=0, le=1)
    status: Literal["grew", "no_growth"]
    terminal_disposition: str = Field(min_length=1)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _status_is_recomputed(self) -> Self:
        if self.availability_count_delta != (
            self.availability_count_after - self.availability_count_before
        ):
            raise ValueError("world-growth availability delta drift")
        expected = int(
            self.availability_count_delta > 0
            and self.overlay_epoch_count > 0
            and self.admitted_observation_count > 0
        )
        if self.event_count != expected or self.status != ("grew" if expected else "no_growth"):
            raise ValueError("world-growth status must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("world-growth projection identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ResumptionBudgetProjection(_StrictModel):
    """Hard six-call resumption budget derived from the three source receipts."""

    maximum_call_count: Literal[6]
    spent_attempt_ids: tuple[str, ...]
    spent_call_count: int = Field(ge=0, le=6)
    remaining_call_count: int = Field(ge=0, le=6)
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _budget_is_recomputed(self) -> Self:
        if self.spent_attempt_ids != tuple(sorted(set(self.spent_attempt_ids))):
            raise ValueError("resumption attempts must be unique and sorted")
        if self.spent_call_count != len(self.spent_attempt_ids) or self.remaining_call_count != (
            self.maximum_call_count - self.spent_call_count
        ):
            raise ValueError("resumption call budget must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("resumption budget identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class ResidualClosureProjection(_StrictModel):
    """The two N10 lifecycle/journal residuals closed by their real owners."""

    owner_registration_derivation_missing_closed: bool
    journal_raw_evidence_persistence_missing_closed: bool
    open_residuals: tuple[str, ...]
    projection_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _residuals_are_recomputed(self) -> Self:
        expected = tuple(
            name
            for name, closed in (
                (
                    "journal_raw_evidence_persistence_missing",
                    self.journal_raw_evidence_persistence_missing_closed,
                ),
                (
                    "owner_registration_derivation_missing",
                    self.owner_registration_derivation_missing_closed,
                ),
            )
            if not closed
        )
        if self.open_residuals != expected:
            raise ValueError("N10 residual closure must be recomputed")
        if self.projection_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("residual closure identity drift")
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "projection_sha256"
        }


class N13bAcquisitionExecutorContract(_StrictModel):
    """Frozen N13b contract recomputed from canonical data-plane owners."""

    schema_version: Literal["policyos.layer3.gy.n13b.acquisition_executor_contract.v4"] = (
        "policyos.layer3.gy.n13b.acquisition_executor_contract.v4"
    )
    rule_version: Literal["GY-plan-rev18+3.5.12-D1-D6"]
    producer: Literal[
        "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
        "derive_n13b_acquisition_executor_contract"
    ]
    baseline_ref: Literal[
        "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
    ]
    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    source_owners: tuple[SourceOwnerBinding, ...] = Field(min_length=1)
    evidence_bindings: tuple[EvidenceBinding, ...] = Field(min_length=1)
    authority_owner: AuthorityOwnerProjection
    local_lift: LocalLiftRefusal
    d2_source_growth: D2SourceGrowthBacklog
    journal: JournalEvidenceProjection
    carrier_liveness: CarrierLivenessProjection
    derivation: DerivationProjection
    derivation_universality: DerivationUniversalityProjection
    reentry: ReentryProjection
    capstone_routes: CapstoneRoutePreservation
    lifecycle: N13bLifecycleManifest
    quarantine: QuarantineProjection
    world_growth: WorldGrowthProjection
    resumption_budget: ResumptionBudgetProjection
    residual_closure: ResidualClosureProjection
    executor_capability_status: Literal["implemented"]
    demonstration_status: Literal["world_growth_observed", "typed_deeper_terminal"]
    surface_status: Literal["audit_surface"]
    pattern_pass: tuple[
        Literal["P05", "P10", "P27", "P29", "P31", "P32", "P33", "P34"],
        ...,
    ]
    contract_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _contract_is_recomputed(self) -> Self:
        source_paths = tuple(row.path for row in self.source_owners)
        if source_paths != tuple(sorted(set(source_paths))):
            raise ValueError("source-owner denominator must be unique and sorted")
        evidence_paths = tuple(row.path for row in self.evidence_bindings)
        if evidence_paths != tuple(sorted(set(evidence_paths))):
            raise ValueError("evidence-binding denominator must be unique and sorted")
        evidence_identities = {row.content_identity for row in self.evidence_bindings}
        recurring_receipt_identities = {
            row.source_receipt_sha256 for row in self.d2_source_growth.carrier_receipts
        }
        if not recurring_receipt_identities.issubset(evidence_identities):
            raise ValueError("D2 connector-gap sources must bind registered recurring receipts")
        if self.derivation_universality.source_receipt_sha256 not in evidence_identities:
            raise ValueError("universality projection must bind its frozen receipt")
        if (
            self.baseline_sha256 != self.authority_owner.baseline_sha256
            or self.l5_measurement_registry_sha256
            != self.authority_owner.l5_measurement_registry_sha256
        ):
            raise ValueError("contract baseline/L5 identity drift")
        if (
            self.world_growth.target_variable != self.reentry.target_variable
            or self.world_growth.availability_count_delta != self.reentry.availability_count_delta
            or self.world_growth.overlay_epoch_count != self.reentry.overlay_epoch_count
            or self.world_growth.admitted_observation_count
            != self.reentry.overlay_admitted_observation_count
            or self.world_growth.event_count != self.reentry.world_growth_event_count
            or self.world_growth.status != self.reentry.world_growth_status
            or self.world_growth.terminal_disposition != self.reentry.reentry_disposition
        ):
            raise ValueError("world-growth receipt must preserve the real re-entry trace")
        expected_demo = (
            "world_growth_observed" if self.world_growth.event_count else "typed_deeper_terminal"
        )
        if self.demonstration_status != expected_demo:
            raise ValueError("demonstration status must derive from true world growth")
        if self.capstone_routes.laundered_route_count != 0:
            raise ValueError("N13b cannot launder structural capstone routes")
        if (
            self.residual_closure.owner_registration_derivation_missing_closed
            != self.lifecycle.owner_registration_derivation_missing_closed
            or self.residual_closure.journal_raw_evidence_persistence_missing_closed
            != self.journal.journal_raw_evidence_persistence_missing_closed
        ):
            raise ValueError("residual closure must bind lifecycle and journal owners")
        if self.pattern_pass != tuple(sorted(set(self.pattern_pass))):
            raise ValueError("pattern pass must be unique and sorted")
        if self.contract_sha256 != content_sha256(self.identity_payload()):
            raise ValueError("N13b contract identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return timestamp-free semantic evidence without byte-only lifecycle fields."""

        value = self.model_dump(mode="json")
        value.pop("contract_sha256", None)
        value["source_owners"] = [
            {"path": row.path, "file_sha256": row.file_sha256} for row in self.source_owners
        ]
        value["evidence_bindings"] = [
            {
                "path": row.path,
                "schema_version": row.schema_version,
                "content_identity": row.content_identity,
            }
            for row in self.evidence_bindings
        ]
        value["lifecycle"] = self.lifecycle.identity_payload()
        return value


def derive_n13b_acquisition_executor_contract(
    *,
    repo_root: Path,
    baseline_sha256: str,
    l5_sha256: str,
    universality_receipt: DerivationUniversalityReceipt | None = None,
    generated_artifacts_bytes: bytes | None = None,
) -> N13bAcquisitionExecutorContract:
    """Recompute the frozen N13b contract without any network or engine execution."""

    root = Path(repo_root)
    census = _read_model(root / DEFAULT_N13A_CENSUS, CensusManifest)
    provision = _read_model(
        root / DEFAULT_N13B_PROVISION,
        catalog_read_api.AcquisitionAuthorityProvision,
    )
    registry = _read_model(
        root / DEFAULT_N13B_REGISTRY,
        catalog_read_api.AcquisitionAuthorityRegistry,
    )
    r1 = _read_model(root / DEFAULT_R1_FORENSIC, R1ForensicReceipt)
    recurring_carrier_receipts = _read_recurring_carrier_receipts(root)
    carrier = next(
        (
            receipt
            for path, receipt in recurring_carrier_receipts
            if path == DEFAULT_CARRIER_LIVENESS
        ),
        None,
    )
    if carrier is None:
        raise N13bContractError("required_carrier_liveness_receipt_missing")
    r2 = _read_model(
        root / DEFAULT_R2_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    d6 = _read_model(root / DEFAULT_D6_ROUTE, D6RouteSelection)
    r3 = _read_model(
        root / DEFAULT_R3_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    acceptance_inputs = _read_model(
        root / DEFAULT_ACCEPTANCE_INPUTS,
        AcceptanceInputSelection,
    )
    acceptance_live = _read_model(
        root / DEFAULT_ACCEPTANCE_EXECUTION,
        AcceptanceLiveExecutionReceipt,
    )
    acceptance_fallback = _read_model(
        root / DEFAULT_ACCEPTANCE_FALLBACK,
        AcceptanceFallbackSelection,
    )
    acceptance = _read_model(root / DEFAULT_DERIVED_ACCEPTANCE, AcceptanceCaseReceipt)
    if universality_receipt is None:
        universality_receipt = _read_model(
            root / DEFAULT_UNIVERSALITY_RECEIPT,
            DerivationUniversalityReceipt,
        )
    else:
        universality_receipt = DerivationUniversalityReceipt.model_validate(
            universality_receipt.model_dump(mode="python")
        )
    expected_registry_ref = f"repo://{DEFAULT_DERIVATION_FAMILY_REGISTRY.as_posix()}"
    expected_registry_sha256 = _file_sha256(root / DEFAULT_DERIVATION_FAMILY_REGISTRY)
    if (
        universality_receipt.registry_ref != expected_registry_ref
        or universality_receipt.registry_sha256 != expected_registry_sha256
    ):
        raise N13bContractError("n13b_derivation_registry_owner_drift")
    universality_receipt_bytes = canonical_json_bytes(universality_receipt.model_dump(mode="json"))
    reentry = _read_model(root / DEFAULT_REENTRY_TRACE, N13bReentryTrace)
    if (
        baseline_sha256 != provision.baseline_content_sha256
        or baseline_sha256 != registry.baseline_content_sha256
        or baseline_sha256 != reentry.baseline_sha256
        or l5_sha256 != registry.l5_measurement_registry_sha256
        or l5_sha256 != provision.l5_measurement_registry_content_sha256
    ):
        raise N13bContractError("n13b_baseline_or_l5_owner_drift")
    journal = derive_journal_evidence_projection(
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    registry_update = derive_n13b_generated_registry_update(root)
    expected_registry_bytes = registry_update.registry_bytes
    if generated_artifacts_bytes is None:
        try:
            actual_registry_bytes = (root / DEFAULT_GENERATED_ARTIFACTS).read_bytes()
        except OSError as exc:
            raise N13bContractError("generated_artifact_registry_unreadable") from exc
        if actual_registry_bytes != expected_registry_bytes:
            raise N13bContractError("n13b_generated_cas_registry_drift")
        generated_artifacts_bytes = actual_registry_bytes
    elif generated_artifacts_bytes != expected_registry_bytes:
        raise N13bContractError("n13b_generated_cas_registry_override_drift")
    lifecycle = derive_lifecycle_manifest(
        root,
        derived_artifact_id=acceptance.derived_artifact_id,
        certificate_artifact_id=acceptance.certificate_artifact_id,
        prospective_outputs={
            DEFAULT_UNIVERSALITY_RECEIPT.as_posix(): universality_receipt_bytes,
        },
        generated_artifacts_bytes=generated_artifacts_bytes,
        required_cas_artifact_ids=registry_update.required_cas_artifact_ids,
    )
    local_lift = derive_local_lift_refusal(census=census, provision=provision)
    d2_source_growth = derive_d2_source_growth_backlog(
        tuple(receipt for _, receipt in recurring_carrier_receipts)
    )
    derivation = derive_derivation_projection(
        acceptance=acceptance,
        cas_root=root / DEFAULT_N13B_CAS,
    )
    derivation_universality = derive_derivation_universality_projection(universality_receipt)
    capstone = derive_capstone_route_preservation(census)
    authority_values = {
        "baseline_sha256": provision.baseline_content_sha256,
        "l5_measurement_registry_sha256": (provision.l5_measurement_registry_content_sha256),
        "registry_content_sha256": registry.content_sha256,
        "registry_entry_count": len(registry.entries),
        "provision_id": provision.provision_id,
        "live_harness_receipt_count": len(provision.live_harness_receipts),
        "local_rights_trust_anchor_sha256": provision.local_rights_trust_anchor_sha256,
    }
    authority = AuthorityOwnerProjection(
        **authority_values,
        projection_sha256=content_sha256(authority_values),
    )
    carrier_values = {
        "connector_id": carrier.connector_id,
        "request_dataset_id": carrier.request_dataset_id,
        "execution_tier": carrier.execution_tier,
        "data_disposition": carrier.data_disposition.value,
        "metadata_disposition": carrier.metadata_disposition.value,
        "carrier_disposition": carrier.carrier_disposition.value,
        "data_attempt_count": len(carrier.data_attempts),
        "metadata_attempt_count": int(carrier.metadata_attempt is not None),
        "tier_decay_findings": carrier.tier_decay_findings,
        "source_receipt_sha256": carrier.receipt_sha256,
    }
    carrier_projection = CarrierLivenessProjection(
        **carrier_values,
        projection_sha256=content_sha256(carrier_values),
    )
    reentry_values = {
        "target_variable": reentry.target_variable,
        "trace_sha256": reentry.trace_sha256,
        "availability_count_before": reentry.availability_count_before,
        "availability_count_after": reentry.availability_count_after,
        "availability_count_delta": reentry.availability_count_delta,
        "overlay_epoch_count": reentry.overlay_state.epoch_count,
        "overlay_admitted_observation_count": (reentry.overlay_state.admitted_observation_count),
        "fetch_plan_count": reentry.catalog_resolution.fetch_plan_count,
        "fetch_plan_execution_count": (reentry.catalog_resolution.fetch_plan_execution_count),
        "reentry_disposition": reentry.reentry_disposition,
        "world_growth_status": reentry.world_growth_status,
        "world_growth_event_count": reentry.world_growth_event_count,
    }
    reentry_projection = ReentryProjection(
        **reentry_values,
        projection_sha256=content_sha256(reentry_values),
    )
    failure_counts: dict[str, int] = {}
    for attempt in journal.attempts:
        failure_counts[attempt.failure_code] = failure_counts.get(attempt.failure_code, 0) + 1
    quarantine_values = {
        "live_attempt_count": journal.terminal_count,
        "raw_response_count": journal.raw_response_count,
        "terminal_without_response_count": (journal.terminal_count - journal.raw_response_count),
        "response_admitted_count": journal.response_admitted_count,
        "overlay_admitted_observation_count": (reentry.overlay_state.admitted_observation_count),
        "failure_code_counts": dict(sorted(failure_counts.items())),
        "disposition": (
            "admitted"
            if journal.response_admitted_count or reentry.overlay_state.admitted_observation_count
            else "all_live_evidence_quarantined_or_terminal"
        ),
    }
    quarantine = QuarantineProjection(
        **quarantine_values,
        projection_sha256=content_sha256(quarantine_values),
    )
    world_values = {
        "target_variable": reentry.target_variable,
        "availability_count_before": reentry.availability_count_before,
        "availability_count_after": reentry.availability_count_after,
        "availability_count_delta": reentry.availability_count_delta,
        "overlay_epoch_count": reentry.overlay_state.epoch_count,
        "admitted_observation_count": reentry.overlay_state.admitted_observation_count,
        "event_count": reentry.world_growth_event_count,
        "status": reentry.world_growth_status,
        "terminal_disposition": reentry.reentry_disposition,
    }
    world_growth = WorldGrowthProjection(
        **world_values,
        projection_sha256=content_sha256(world_values),
    )
    resumption_ids = tuple(sorted({r2.attempt_id, r3.attempt_id, acceptance_live.attempt_id}))
    budget_values = {
        "maximum_call_count": 6,
        "spent_attempt_ids": resumption_ids,
        "spent_call_count": len(resumption_ids),
        "remaining_call_count": 6 - len(resumption_ids),
    }
    budget = ResumptionBudgetProjection(
        **budget_values,
        projection_sha256=content_sha256(budget_values),
    )
    closure_values = {
        "owner_registration_derivation_missing_closed": (
            lifecycle.owner_registration_derivation_missing_closed
        ),
        "journal_raw_evidence_persistence_missing_closed": (
            journal.journal_raw_evidence_persistence_missing_closed
        ),
    }
    closure_values["open_residuals"] = tuple(
        name
        for name, closed in (
            (
                "journal_raw_evidence_persistence_missing",
                closure_values["journal_raw_evidence_persistence_missing_closed"],
            ),
            (
                "owner_registration_derivation_missing",
                closure_values["owner_registration_derivation_missing_closed"],
            ),
        )
        if not closed
    )
    closure = ResidualClosureProjection(
        **closure_values,
        projection_sha256=content_sha256(closure_values),
    )
    models_and_identities: tuple[tuple[Path, BaseModel, str], ...] = (
        (DEFAULT_N13A_CENSUS, census, semantic_content_hash(census)),
        (DEFAULT_N13B_PROVISION, provision, provision.provision_id),
        (DEFAULT_N13B_REGISTRY, registry, registry.content_sha256),
        (DEFAULT_R1_FORENSIC, r1, r1.receipt_sha256),
        *((path, receipt, receipt.receipt_sha256) for path, receipt in recurring_carrier_receipts),
        (DEFAULT_R2_METADATA_EVIDENCE, r2, r2.evidence_sha256),
        (DEFAULT_D6_ROUTE, d6, d6.selection_sha256),
        (DEFAULT_R3_METADATA_EVIDENCE, r3, r3.evidence_sha256),
        (DEFAULT_ACCEPTANCE_INPUTS, acceptance_inputs, acceptance_inputs.selection_sha256),
        (DEFAULT_ACCEPTANCE_EXECUTION, acceptance_live, acceptance_live.receipt_sha256),
        (
            DEFAULT_ACCEPTANCE_FALLBACK,
            acceptance_fallback,
            acceptance_fallback.selection_sha256,
        ),
        (DEFAULT_DERIVED_ACCEPTANCE, acceptance, acceptance.receipt_sha256),
        (
            DEFAULT_UNIVERSALITY_RECEIPT,
            universality_receipt,
            universality_receipt.receipt_sha256,
        ),
        (DEFAULT_REENTRY_TRACE, reentry, reentry.trace_sha256),
    )
    evidence_bindings = tuple(
        sorted(
            (
                _evidence_binding(
                    root,
                    path,
                    model,
                    identity,
                    payload_override=(
                        universality_receipt_bytes if path == DEFAULT_UNIVERSALITY_RECEIPT else None
                    ),
                )
                for path, model, identity in models_and_identities
            ),
            key=lambda row: row.path,
        )
    )
    source_owners = tuple(
        SourceOwnerBinding(
            path=path,
            file_sha256=_file_sha256(root / path),
            byte_size=(root / path).stat().st_size,
        )
        for path in _SOURCE_OWNER_PATHS
    )
    values = {
        "schema_version": "policyos.layer3.gy.n13b.acquisition_executor_contract.v4",
        "rule_version": "GY-plan-rev18+3.5.12-D1-D6",
        "producer": (
            "tools.quality.validation.layer3_gy_n13b_acquisition_contract."
            "derive_n13b_acquisition_executor_contract"
        ),
        "baseline_ref": (
            "repo://production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
        ),
        "baseline_sha256": baseline_sha256,
        "l5_measurement_registry_sha256": l5_sha256,
        "source_owners": source_owners,
        "evidence_bindings": evidence_bindings,
        "authority_owner": authority,
        "local_lift": local_lift,
        "d2_source_growth": d2_source_growth,
        "journal": journal,
        "carrier_liveness": carrier_projection,
        "derivation": derivation,
        "derivation_universality": derivation_universality,
        "reentry": reentry_projection,
        "capstone_routes": capstone,
        "lifecycle": lifecycle,
        "quarantine": quarantine,
        "world_growth": world_growth,
        "resumption_budget": budget,
        "residual_closure": closure,
        "executor_capability_status": "implemented",
        "demonstration_status": (
            "world_growth_observed" if world_growth.event_count else "typed_deeper_terminal"
        ),
        "surface_status": "audit_surface",
        "pattern_pass": ("P05", "P10", "P27", "P29", "P31", "P32", "P33", "P34"),
    }
    identity = _json_value(values)
    identity["source_owners"] = [
        {"path": row.path, "file_sha256": row.file_sha256} for row in source_owners
    ]
    identity["evidence_bindings"] = [
        {
            "path": row.path,
            "schema_version": row.schema_version,
            "content_identity": row.content_identity,
        }
        for row in evidence_bindings
    ]
    identity["lifecycle"] = lifecycle.identity_payload()
    return N13bAcquisitionExecutorContract(
        **values,
        contract_sha256=content_sha256(identity),
    )


def _read_model(path: Path, model: type[BaseModel]) -> Any:
    try:
        return model.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise N13bContractError("n13b_source_artifact_invalid", path.as_posix()) from exc


def _d2_planner_route_projection(
    report: AcquisitionPlannerReport,
) -> D2PlannerRouteProjection:
    if len(report.acquisition_records) != 1:
        raise N13bContractError("connector_gap_planner_record_denominator_drift")
    record = report.acquisition_records[0]
    strategy_records = (*record.strategy_records, *record.ineligible_strategy_records)
    if record.voi_ranking_ref is not None or any(
        strategy.voi_decision_ref is not None
        or strategy.voi_rank is not None
        or strategy.voi_expected_value is not None
        or strategy.voi_expected_cost is not None
        for strategy in strategy_records
    ):
        raise N13bContractError("connector_gap_owner_voi_evidence_unexpected")
    if record.producer_output_ref is None:
        raise N13bContractError("connector_gap_planner_producer_output_ref_missing")
    source_projection = report.model_dump(mode="json")
    source_projection.pop("generated_at", None)
    values = {
        "planner_schema_version": report.schema_version,
        "run_id": report.run_id,
        "gap_id": record.gap_id,
        "requirement_gap_ref": record.requirement_gap_ref,
        "requirement_family": record.requirement_family,
        "compiled_requirement_ref": record.compiled_requirement_ref,
        "requirement_schema_version": record.requirement_schema_version,
        "gap_type": record.gap_type.value,
        "missing_requirement_fields": record.missing_requirement_fields,
        "report_status": report.status,
        "record_status": record.status,
        "recommended_strategy": record.recommended_strategy.value,
        "terminal_disposition": record.terminal_disposition.value,
        "eligible_strategies": tuple(
            sorted(strategy.value for strategy in record.eligible_strategies)
        ),
        "ineligible_strategies": tuple(sorted(record.ineligible_strategies)),
        "producer_expected": record.producer_expected,
        "producer_output_ref": record.producer_output_ref,
        "voi_ranking_ref": None,
        "voi_numeric_support": False,
        "source_report_projection_sha256": content_sha256(source_projection),
    }
    return D2PlannerRouteProjection(
        **values,
        projection_sha256=content_sha256(values),
    )


def _read_recurring_carrier_receipts(
    root: Path,
) -> tuple[tuple[Path, RecurringCarrierLivenessUpdate], ...]:
    """Discover the full typed recurring-receipt denominator without family lists."""

    artifact_root = Path(root) / "architecture/policy_design_case"
    receipts: list[tuple[Path, RecurringCarrierLivenessUpdate]] = []
    for path in sorted(artifact_root.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes())
        except (OSError, json.JSONDecodeError) as exc:
            raise N13bContractError("n13b_source_artifact_invalid", path.as_posix()) from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != (
            "policyos.layer3.gy.n13a.recurring_carrier_liveness.v1"
        ):
            continue
        try:
            receipt = RecurringCarrierLivenessUpdate.model_validate_json(
                canonical_json_bytes(payload)
            )
        except ValueError as exc:
            raise N13bContractError(
                "n13b_recurring_carrier_receipt_invalid",
                path.as_posix(),
            ) from exc
        receipts.append((path.relative_to(root), receipt))
    receipt_paths = tuple(path for path, _ in receipts)
    if receipt_paths != tuple(sorted(set(receipt_paths))):
        raise N13bContractError("n13b_recurring_carrier_receipt_denominator_invalid")
    return tuple(receipts)


def _source_growth_gap_identity(
    *,
    connector_id: str,
    request_dataset_id: str,
    missing_request_lever: str,
    source_receipt_sha256: str,
) -> str:
    return content_sha256(
        {
            "connector_id": connector_id,
            "request_dataset_id": request_dataset_id,
            "missing_request_lever": missing_request_lever,
            "source_receipt_sha256": source_receipt_sha256,
        }
    ).removeprefix("sha256:")[:20]


def _evidence_binding(
    root: Path,
    relative: Path,
    model: BaseModel,
    identity: str,
    *,
    payload_override: bytes | None = None,
) -> EvidenceBinding:
    path = root / relative
    schema_version = getattr(model, "schema_version", None)
    if not isinstance(schema_version, str):
        raise N13bContractError("n13b_source_schema_version_missing", relative.as_posix())
    return EvidenceBinding(
        path=relative.as_posix(),
        schema_version=schema_version,
        content_identity=identity,
        file_sha256=(
            _bytes_sha256(payload_override) if payload_override is not None else _file_sha256(path)
        ),
        byte_size=(len(payload_override) if payload_override is not None else path.stat().st_size),
    )


def _lifecycle_role(
    path: str,
) -> Literal[
    "journal",
    "cas_blob",
    "cas_manifest",
    "provision",
    "registry",
    "receipt",
]:
    if path.endswith(".jsonl"):
        return "journal"
    if path.endswith(".blob"):
        return "cas_blob"
    if path.endswith(".manifest.json"):
        return "cas_manifest"
    if path == DEFAULT_N13B_PROVISION.as_posix():
        return "provision"
    if path == DEFAULT_N13B_REGISTRY.as_posix():
        return "registry"
    return "receipt"


def _read_canonical_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    payload = path.read_bytes()
    if not payload.endswith(b"\n"):
        raise N13bContractError("journal_not_newline_terminated")
    events: list[dict[str, Any]] = []
    for expected_sequence, line in enumerate(payload.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise N13bContractError("journal_event_invalid") from exc
        if not isinstance(event, dict) or event.get("sequence") != expected_sequence:
            raise N13bContractError("journal_event_sequence_drift")
        if canonical_json_bytes(event).rstrip(b"\n") != line:
            raise N13bContractError("journal_event_not_canonical")
        events.append(event)
    return tuple(events)


def _cas_blob_path(cas_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.removeprefix("sha256:")
    return Path(cas_root) / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"


def _cas_manifest_path(cas_root: Path, artifact_id: str) -> Path:
    digest = artifact_id.removeprefix("sha256:")
    return (
        Path(cas_root) / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.manifest.json"
    )


def _cas_blob_relative(artifact_id: str) -> str:
    digest = artifact_id.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    ).as_posix()


def _cas_manifest_relative(artifact_id: str) -> str:
    digest = artifact_id.removeprefix("sha256:")
    return (
        DEFAULT_N13B_CAS / "artifacts/sha256" / digest[:2] / digest[2:4] / f"{digest}.manifest.json"
    ).as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _bytes_sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "DEFAULT_N13B_CONTRACT",
    "DEFAULT_N13B_LIFECYCLE_MANIFEST",
    "CapstoneRoutePreservation",
    "D2CarrierReceiptProjection",
    "D2ConnectorGapRow",
    "D2PlannerRouteProjection",
    "D2SourceGrowthBacklog",
    "DerivationProjection",
    "DerivationUniversalityProjection",
    "JournalEvidenceProjection",
    "LocalLiftRefusal",
    "N13bAcquisitionExecutorContract",
    "N13bContractError",
    "N13bGeneratedRegistryUpdate",
    "N13bLifecycleManifest",
    "derive_capstone_route_preservation",
    "derive_cas_artifact_closure",
    "derive_d2_source_growth_backlog",
    "derive_derivation_projection",
    "derive_derivation_universality_projection",
    "derive_journal_evidence_projection",
    "derive_lifecycle_manifest",
    "derive_local_lift_refusal",
    "derive_n13b_acquisition_executor_contract",
    "derive_n13b_generated_registry_update",
]
