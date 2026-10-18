"""Recomputing frozen contract for the GY-N13b acquisition executor.

This plan-named module is an audit composer only.  Runtime authority remains in
the canonical acquisition passport/overlay owners, the Fabric evidence journal,
the DatasetCatalogGraph read path, and the derived-observation CAS machinery.
The composer binds their narrow projections without becoming a parallel owner.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.fabric.data_plane import (
    content_sha256 as content_sha256,
)
from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
    DEFAULT_UNIVERSALITY_RECEIPT as DEFAULT_UNIVERSALITY_RECEIPT,
)

if TYPE_CHECKING:
    from tools.quality.validation.layer3_gy_n13b_derivation_universality import (
        DerivationUniversalityReceipt,
    )

from .acquisition_admission_contract import (
    AuthorityOwnerProjection as AuthorityOwnerProjection,
)
from .acquisition_admission_contract import (
    CarrierLivenessProjection as CarrierLivenessProjection,
)
from .acquisition_admission_contract import (
    EvidenceBinding as EvidenceBinding,
)
from .acquisition_admission_contract import (
    N13bAcquisitionExecutorContract as N13bAcquisitionExecutorContract,
)
from .acquisition_admission_contract import (
    N13bAcquisitionExecutorContractV4 as N13bAcquisitionExecutorContractV4,
)
from .acquisition_admission_contract import (
    QuarantineProjection as QuarantineProjection,
)
from .acquisition_admission_contract import (
    ReentryProjection as ReentryProjection,
)
from .acquisition_admission_contract import (
    ResidualClosureProjection as ResidualClosureProjection,
)
from .acquisition_admission_contract import (
    ResumptionBudgetProjection as ResumptionBudgetProjection,
)
from .acquisition_admission_contract import (
    SourceOwnerBinding as SourceOwnerBinding,
)
from .acquisition_admission_contract import (
    WorldGrowthProjection as WorldGrowthProjection,
)
from .acquisition_admission_contract import (
    _evidence_binding as _evidence_binding,
)
from .acquisition_admission_contract import (
    derive_n13b_acquisition_executor_contract as _derive_n13b_acquisition_executor_contract_impl,
)
from .acquisition_admission_contract import (
    read_n13b_acquisition_executor_contract as read_n13b_acquisition_executor_contract,
)
from .acquisition_contract_support import (
    _SOURCE_GROWTH_PLANNER_GENERATED_AT as _SOURCE_GROWTH_PLANNER_GENERATED_AT,
)
from .acquisition_contract_support import (
    _SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION as _SOURCE_GROWTH_REQUIREMENT_SCHEMA_VERSION,
)
from .acquisition_contract_support import (
    _SOURCE_OWNER_PATHS as _SOURCE_OWNER_PATHS,
)
from .acquisition_contract_support import (
    DEFAULT_ACCEPTANCE_EXECUTION as DEFAULT_ACCEPTANCE_EXECUTION,
)
from .acquisition_contract_support import (
    DEFAULT_ACCEPTANCE_FALLBACK as DEFAULT_ACCEPTANCE_FALLBACK,
)
from .acquisition_contract_support import (
    DEFAULT_ACCEPTANCE_INPUTS as DEFAULT_ACCEPTANCE_INPUTS,
)
from .acquisition_contract_support import (
    DEFAULT_CARRIER_LIVENESS as DEFAULT_CARRIER_LIVENESS,
)
from .acquisition_contract_support import (
    DEFAULT_D6_ROUTE as DEFAULT_D6_ROUTE,
)
from .acquisition_contract_support import (
    DEFAULT_DERIVED_ACCEPTANCE as DEFAULT_DERIVED_ACCEPTANCE,
)
from .acquisition_contract_support import (
    DEFAULT_GENERATED_ARTIFACTS as DEFAULT_GENERATED_ARTIFACTS,
)
from .acquisition_contract_support import (
    DEFAULT_N13A_CENSUS as DEFAULT_N13A_CENSUS,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_CAS as DEFAULT_N13B_CAS,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_CONTRACT as DEFAULT_N13B_CONTRACT,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_JOURNAL as DEFAULT_N13B_JOURNAL,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_LIFECYCLE_MANIFEST as DEFAULT_N13B_LIFECYCLE_MANIFEST,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_PROVISION as DEFAULT_N13B_PROVISION,
)
from .acquisition_contract_support import (
    DEFAULT_N13B_REGISTRY as DEFAULT_N13B_REGISTRY,
)
from .acquisition_contract_support import (
    DEFAULT_R1_FORENSIC as DEFAULT_R1_FORENSIC,
)
from .acquisition_contract_support import (
    DEFAULT_R2_METADATA_EVIDENCE as DEFAULT_R2_METADATA_EVIDENCE,
)
from .acquisition_contract_support import (
    DEFAULT_R3_METADATA_EVIDENCE as DEFAULT_R3_METADATA_EVIDENCE,
)
from .acquisition_contract_support import (
    DEFAULT_REENTRY_TRACE as DEFAULT_REENTRY_TRACE,
)
from .acquisition_contract_support import (
    N13B_FAMILY_ID as N13B_FAMILY_ID,
)
from .acquisition_contract_support import (
    N13B_SOURCE_FAMILY_ID as N13B_SOURCE_FAMILY_ID,
)
from .acquisition_contract_support import (
    SHA256_PATTERN as SHA256_PATTERN,
)
from .acquisition_contract_support import AdmissionDependencies
from .acquisition_contract_support import (
    N13bContractError as N13bContractError,
)
from .acquisition_contract_support import (
    _bytes_sha256 as _bytes_sha256,
)
from .acquisition_contract_support import (
    _file_sha256 as _file_sha256,
)
from .acquisition_contract_support import (
    _json_value as _json_value,
)
from .acquisition_contract_support import (
    _read_epoch_model as _read_epoch_model,
)
from .acquisition_contract_support import (
    _read_model as _read_model,
)
from .acquisition_contract_support import (
    _StrictModel as _StrictModel,
)
from .artifact_lifecycle_manifest import (
    LifecycleRegistration as LifecycleRegistration,
)
from .artifact_lifecycle_manifest import (
    N13bLifecycleManifest as N13bLifecycleManifest,
)
from .artifact_lifecycle_manifest import (
    N13bLifecycleManifestV2 as N13bLifecycleManifestV2,
)
from .artifact_lifecycle_manifest import (
    _lifecycle_role as _lifecycle_role,
)
from .artifact_lifecycle_manifest import (
    derive_lifecycle_manifest as derive_lifecycle_manifest,
)
from .artifact_lifecycle_manifest import (
    read_n13b_lifecycle_manifest as read_n13b_lifecycle_manifest,
)
from .demand_gap_projections import (
    D2CarrierReceiptProjection as D2CarrierReceiptProjection,
)
from .demand_gap_projections import (
    D2ConnectorGapRow as D2ConnectorGapRow,
)
from .demand_gap_projections import (
    D2PlannerRouteProjection as D2PlannerRouteProjection,
)
from .demand_gap_projections import (
    D2SourceGrowthBacklog as D2SourceGrowthBacklog,
)
from .demand_gap_projections import (
    LocalLiftRefusal as LocalLiftRefusal,
)
from .demand_gap_projections import (
    LocalLiftRefusalRow as LocalLiftRefusalRow,
)
from .demand_gap_projections import (
    _d2_planner_route_projection as _d2_planner_route_projection,
)
from .demand_gap_projections import (
    _read_recurring_carrier_receipts as _read_recurring_carrier_receipts,
)
from .demand_gap_projections import (
    _source_growth_gap_identity as _source_growth_gap_identity,
)
from .demand_gap_projections import (
    derive_d2_source_growth_backlog as derive_d2_source_growth_backlog,
)
from .demand_gap_projections import (
    derive_local_lift_refusal as derive_local_lift_refusal,
)
from .derivation_route_projections import (
    CapstoneRoutePreservation as CapstoneRoutePreservation,
)
from .derivation_route_projections import (
    CapstoneRouteRow as CapstoneRouteRow,
)
from .derivation_route_projections import (
    DerivationProjection as DerivationProjection,
)
from .derivation_route_projections import (
    DerivationUniversalityProjection as DerivationUniversalityProjection,
)
from .derivation_route_projections import (
    UniversalityFamilyProjection as UniversalityFamilyProjection,
)
from .derivation_route_projections import (
    derive_capstone_route_preservation as derive_capstone_route_preservation,
)
from .derivation_route_projections import (
    derive_derivation_projection as derive_derivation_projection,
)
from .derivation_route_projections import (
    derive_derivation_universality_projection as derive_derivation_universality_projection,
)
from .evidence_journal_custody import (
    JournalEvidenceProjection as JournalEvidenceProjection,
)
from .evidence_journal_custody import (
    LiveAttemptProjection as LiveAttemptProjection,
)
from .evidence_journal_custody import (
    N13bGeneratedRegistryUpdate as N13bGeneratedRegistryUpdate,
)
from .evidence_journal_custody import (
    _cas_blob_path as _cas_blob_path,
)
from .evidence_journal_custody import (
    _cas_blob_relative as _cas_blob_relative,
)
from .evidence_journal_custody import (
    _cas_manifest_path as _cas_manifest_path,
)
from .evidence_journal_custody import (
    _cas_manifest_relative as _cas_manifest_relative,
)
from .evidence_journal_custody import (
    _n13b_generated_family as _n13b_generated_family,
)
from .evidence_journal_custody import (
    _n13b_lifecycle_families as _n13b_lifecycle_families,
)
from .evidence_journal_custody import (
    _read_canonical_jsonl as _read_canonical_jsonl,
)
from .evidence_journal_custody import (
    _replace_n13b_generated_outputs as _replace_n13b_generated_outputs,
)
from .evidence_journal_custody import (
    _require_artifact_id as _require_artifact_id,
)
from .evidence_journal_custody import (
    _verify_n13b_source_integrity as _verify_n13b_source_integrity,
)
from .evidence_journal_custody import (
    derive_cas_artifact_closure as derive_cas_artifact_closure,
)
from .evidence_journal_custody import (
    derive_journal_evidence_projection as derive_journal_evidence_projection,
)
from .evidence_journal_custody import (
    derive_n13b_generated_registry_update as derive_n13b_generated_registry_update,
)
from .layer3_gy_acquisition_executor import (
    derive_d6_metadata_probe_execution_evidence as derive_d6_metadata_probe_execution_evidence,
)
from .layer3_gy_acquisition_executor import (
    derive_metadata_probe_execution_evidence as derive_metadata_probe_execution_evidence,
)


def derive_n13b_acquisition_executor_contract(
    *,
    repo_root: Path,
    baseline_sha256: str,
    l5_sha256: str,
    universality_receipt: DerivationUniversalityReceipt | None = None,
    generated_artifacts_bytes: bytes | None = None,
    baseline_path: Path | None = None,
) -> N13bAcquisitionExecutorContract:
    return _derive_n13b_acquisition_executor_contract_impl(
        repo_root=repo_root,
        baseline_sha256=baseline_sha256,
        l5_sha256=l5_sha256,
        universality_receipt=universality_receipt,
        generated_artifacts_bytes=generated_artifacts_bytes,
        baseline_path=baseline_path,
        _dependencies=AdmissionDependencies(
            derive_lifecycle_manifest=derive_lifecycle_manifest,
            derive_metadata_probe_execution_evidence=derive_metadata_probe_execution_evidence,
            derive_d6_metadata_probe_execution_evidence=derive_d6_metadata_probe_execution_evidence,
        ),
    )


__all__ = [
    "DEFAULT_N13B_CONTRACT",
    "DEFAULT_N13B_LIFECYCLE_MANIFEST",
    "N13B_FAMILY_ID",
    "N13B_SOURCE_FAMILY_ID",
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
    "N13bAcquisitionExecutorContractV4",
    "N13bContractError",
    "N13bGeneratedRegistryUpdate",
    "N13bLifecycleManifest",
    "N13bLifecycleManifestV2",
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
    "read_n13b_acquisition_executor_contract",
    "read_n13b_lifecycle_manifest",
]
