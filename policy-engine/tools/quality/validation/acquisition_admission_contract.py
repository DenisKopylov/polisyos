"""N13b contract admission composition over canonical owner projections."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, Field, model_validator

from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.data_plane import EvidenceJournalError, canonical_json_bytes, content_sha256
from tools.quality.validation.layer3_gy_acquisition_executor import (
    DEFAULT_D6_PRIMARY_METADATA_OWNER,
    DEFAULT_METADATA_PROBE_OWNER,
    D6MetadataProbeOwner,
    D6RouteSelection,
    MetadataProbeExecutionEvidence,
    MetadataProbeOwner,
    R1ForensicReceipt,
)
from tools.quality.validation.layer3_gy_n13a_acquisition_census import (
    CensusManifest,
    semantic_content_hash,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    AcceptanceCaseReceipt,
    AcceptanceFallbackSelection,
    AcceptanceInputSelection,
    AcceptanceLiveExecutionReceipt,
)
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_DERIVATION_FAMILY_REGISTRY,
    DEFAULT_UNIVERSALITY_RECEIPT,
    DerivationUniversalityReceipt,
)
from tools.quality.validation.layer3_gy_n13b_reentry import N13bReentryTrace

from .acquisition_contract_support import (
    _SOURCE_OWNER_PATHS,
    DEFAULT_ACCEPTANCE_EXECUTION,
    DEFAULT_ACCEPTANCE_FALLBACK,
    DEFAULT_ACCEPTANCE_INPUTS,
    DEFAULT_CARRIER_LIVENESS,
    DEFAULT_D6_ROUTE,
    DEFAULT_DERIVED_ACCEPTANCE,
    DEFAULT_GENERATED_ARTIFACTS,
    DEFAULT_N13A_CENSUS,
    DEFAULT_N13B_CAS,
    DEFAULT_N13B_JOURNAL,
    DEFAULT_N13B_PROVISION,
    DEFAULT_N13B_REGISTRY,
    DEFAULT_R1_FORENSIC,
    DEFAULT_R2_METADATA_EVIDENCE,
    DEFAULT_R3_METADATA_EVIDENCE,
    DEFAULT_REENTRY_TRACE,
    SHA256_PATTERN,
    AdmissionDependencies,
    N13bContractError,
    _bytes_sha256,
    _file_sha256,
    _json_value,
    _read_epoch_model,
    _read_model,
    _StrictModel,
)

if TYPE_CHECKING:
    from .artifact_lifecycle_manifest import N13bLifecycleManifest, N13bLifecycleManifestV2
from .demand_gap_projections import (
    D2SourceGrowthBacklog,
    LocalLiftRefusal,
    _read_recurring_carrier_receipts,
    derive_d2_source_growth_backlog,
    derive_local_lift_refusal,
)
from .derivation_route_projections import (
    CapstoneRoutePreservation,
    DerivationProjection,
    DerivationUniversalityProjection,
    derive_capstone_route_preservation,
    derive_derivation_projection,
    derive_derivation_universality_projection,
)
from .evidence_journal_custody import (
    JournalEvidenceProjection,
    derive_journal_evidence_projection,
    derive_n13b_generated_registry_update,
)


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


class N13bAcquisitionExecutorContractV4(_StrictModel):
    """Historical acquisition contract retaining its original lifecycle epoch."""

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
    lifecycle: N13bLifecycleManifestV2
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


class N13bAcquisitionExecutorContract(N13bAcquisitionExecutorContractV4):
    """Current acquisition contract with the complete split lifecycle custody."""

    schema_version: Literal["policyos.layer3.gy.n13b.acquisition_executor_contract.v5"] = (
        "policyos.layer3.gy.n13b.acquisition_executor_contract.v5"
    )
    lifecycle: N13bLifecycleManifest


def read_n13b_acquisition_executor_contract(
    path: Path,
) -> N13bAcquisitionExecutorContractV4 | N13bAcquisitionExecutorContract:
    """Read a recorded contract epoch; current admission still requires v5."""

    receipt = _read_epoch_model(
        path,
        {
            "policyos.layer3.gy.n13b.acquisition_executor_contract.v4": (
                N13bAcquisitionExecutorContractV4
            ),
            "policyos.layer3.gy.n13b.acquisition_executor_contract.v5": (
                N13bAcquisitionExecutorContract
            ),
        },
    )
    assert isinstance(receipt, N13bAcquisitionExecutorContractV4)
    return receipt


def _require_current_metadata_journal_refs(
    evidence: MetadataProbeExecutionEvidence,
    *,
    journal_path: Path,
) -> None:
    """Reject persisted evidence refs that point outside the current journal."""

    refs = (
        evidence.request_ref,
        evidence.terminal.request_ref,
        evidence.raw_evidence_ref,
        evidence.terminal.raw_evidence_ref,
        *(
            (
                evidence.transport_trace.request_ref,
                evidence.transport_trace.transport_attempt_ref,
                *evidence.transport_trace.heartbeat_refs,
                evidence.transport_trace.raw_evidence_ref,
            )
            if evidence.transport_trace is not None
            else ()
        ),
    )
    expected = Path(journal_path).as_posix()
    for ref in refs:
        if ref is not None and ref.journal_path != expected:
            raise EvidenceJournalError("journal_event_ref_unresolved", ref.event_sha256)


def _require_exact_artifact_payload(
    path: Path,
    payload: BaseModel,
    *,
    label: str,
) -> None:
    """Require exact canonical bytes for one freshly reopened owner payload."""

    try:
        stored = Path(path).read_bytes()
    except OSError as exc:
        raise N13bContractError(f"{label}_artifact_missing", Path(path).as_posix()) from exc
    expected = canonical_json_bytes(payload.model_dump(mode="json"))
    if stored != expected:
        raise N13bContractError(f"{label}_artifact_drift", Path(path).as_posix())


def _reopen_current_metadata_receipts(
    *,
    root: Path,
    baseline_path: Path,
    r1: R1ForensicReceipt,
    d6: D6RouteSelection,
    dependencies: AdmissionDependencies,
) -> tuple[MetadataProbeExecutionEvidence, MetadataProbeExecutionEvidence]:
    """Recompute both receipt variants and bind each to its stored payload."""

    stored_r2 = _read_model(
        root / DEFAULT_R2_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    _require_current_metadata_journal_refs(
        stored_r2,
        journal_path=root / DEFAULT_N13B_JOURNAL,
    )
    r2_owner = _read_model(root / DEFAULT_METADATA_PROBE_OWNER, MetadataProbeOwner)
    r2, carrier_update = dependencies.derive_metadata_probe_execution_evidence(
        owner=r2_owner,
        r1_receipt=r1,
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
        baseline_path=baseline_path,
    )
    _require_exact_artifact_payload(
        root / DEFAULT_R2_METADATA_EVIDENCE,
        r2,
        label="metadata_evidence",
    )
    _require_exact_artifact_payload(
        root / DEFAULT_CARRIER_LIVENESS,
        carrier_update,
        label="metadata_evidence",
    )

    stored_r3 = _read_model(
        root / DEFAULT_R3_METADATA_EVIDENCE,
        MetadataProbeExecutionEvidence,
    )
    _require_current_metadata_journal_refs(
        stored_r3,
        journal_path=root / DEFAULT_N13B_JOURNAL,
    )
    d6_owner = _read_model(root / DEFAULT_D6_PRIMARY_METADATA_OWNER, D6MetadataProbeOwner)
    r3 = dependencies.derive_d6_metadata_probe_execution_evidence(
        owner=d6_owner,
        selection=d6,
        journal_path=root / DEFAULT_N13B_JOURNAL,
        cas_root=root / DEFAULT_N13B_CAS,
        baseline_path=baseline_path,
    )
    _require_exact_artifact_payload(
        root / DEFAULT_R3_METADATA_EVIDENCE,
        r3,
        label="d6_metadata_evidence",
    )
    return r2, r3


def derive_n13b_acquisition_executor_contract(
    *,
    repo_root: Path,
    baseline_sha256: str,
    l5_sha256: str,
    universality_receipt: DerivationUniversalityReceipt | None = None,
    generated_artifacts_bytes: bytes | None = None,
    baseline_path: Path | None = None,
    _dependencies: AdmissionDependencies,
) -> N13bAcquisitionExecutorContract:
    """Recompute the frozen N13b contract from explicitly supplied current inputs."""

    if baseline_path is None:
        raise N13bContractError("n13b_current_baseline_required")
    root = Path(repo_root)
    baseline_path = Path(baseline_path)
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
    d6 = _read_model(root / DEFAULT_D6_ROUTE, D6RouteSelection)
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
    try:
        current_baseline_sha256 = _file_sha256(baseline_path)
    except OSError as exc:
        raise N13bContractError(
            "n13b_current_baseline_unreadable", baseline_path.as_posix()
        ) from exc
    if current_baseline_sha256 != baseline_sha256:
        raise N13bContractError("n13b_current_baseline_content_drift", baseline_path.as_posix())
    if (
        baseline_sha256 != provision.baseline_content_sha256
        or baseline_sha256 != registry.baseline_content_sha256
        or baseline_sha256 != reentry.baseline_sha256
        or l5_sha256 != registry.l5_measurement_registry_sha256
        or l5_sha256 != provision.l5_measurement_registry_content_sha256
    ):
        raise N13bContractError("n13b_baseline_or_l5_owner_drift")
    r2, r3 = _reopen_current_metadata_receipts(
        root=root,
        baseline_path=baseline_path,
        r1=r1,
        d6=d6,
        dependencies=_dependencies,
    )
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
    lifecycle = _dependencies.derive_lifecycle_manifest(
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
        "schema_version": "policyos.layer3.gy.n13b.acquisition_executor_contract.v5",
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
