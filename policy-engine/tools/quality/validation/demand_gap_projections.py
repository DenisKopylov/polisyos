"""Rights-bound local-lift and complete D2 demand-gap projections."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import canonical_json_bytes, content_sha256
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionGapType,
    AcquisitionPlannerReport,
    AcquisitionRequirementGap,
    AuthorityLevel,
    MandatoryGateState,
    RequirementGapFamily,
    plan_requirement_gap_acquisition,
)
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CensusManifest,
    RecurringCarrierLivenessUpdate,
)

from .acquisition_contract_support import (
    _SOURCE_GROWTH_PLANNER_GENERATED_AT,
    _SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION,
    SHA256_PATTERN,
    N13bContractError,
    _json_value,
    _StrictModel,
)


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
            capability_requirement_resolutions=None,
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
