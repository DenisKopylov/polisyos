"""Recomputing owners for the GY-N13b acquisition execution evidence.

This module is intentionally data-plane only.  It derives an executable target
from the frozen N13a demand denominator, the immutable catalog, and the L6 slot
vocabulary.  It never executes a connector merely to select a target.
"""

from __future__ import annotations

from polisyos.fabric.data_plane import (
    content_sha256 as content_sha256,
)

from .acquisition_executor_support import (
    DEFAULT_TARGET_HARNESS_RECEIPT as DEFAULT_TARGET_HARNESS_RECEIPT,
)
from .acquisition_executor_support import (
    _json_object as _json_object,
)
from .acquisition_executor_support import (
    _read_mapping as _read_mapping,
)
from .acquisition_executor_support import (
    _string_values as _string_values,
)
from .acquisition_executor_support import (
    bytes_sha256 as bytes_sha256,
)
from .acquisition_response_receipts import (
    DEFAULT_R1_FORENSIC_RECEIPT as DEFAULT_R1_FORENSIC_RECEIPT,
)
from .acquisition_response_receipts import (
    AcquisitionSelectionError as AcquisitionSelectionError,
)
from .acquisition_response_receipts import (
    CarrierDataDisposition as CarrierDataDisposition,
)
from .acquisition_response_receipts import (
    IndicatorMetadataDisposition as IndicatorMetadataDisposition,
)
from .acquisition_response_receipts import (
    R1AttemptForensicProjection as R1AttemptForensicProjection,
)
from .acquisition_response_receipts import (
    R1ForensicReceipt as R1ForensicReceipt,
)
from .acquisition_response_receipts import (
    WorldBankDataResponseClassification as WorldBankDataResponseClassification,
)
from .acquisition_response_receipts import (
    WorldBankIndicatorMetadataClassification as WorldBankIndicatorMetadataClassification,
)
from .acquisition_response_receipts import (
    _canonical_journal_projection as _canonical_journal_projection,
)
from .acquisition_response_receipts import (
    _nonbool_int as _nonbool_int,
)
from .acquisition_response_receipts import (
    _optional_owner_string as _optional_owner_string,
)
from .acquisition_response_receipts import (
    _optional_string as _optional_string,
)
from .acquisition_response_receipts import (
    _stable_repo_ref as _stable_repo_ref,
)
from .acquisition_response_receipts import (
    _StrictModel as _StrictModel,
)
from .acquisition_response_receipts import (
    _worldbank_api_messages as _worldbank_api_messages,
)
from .acquisition_response_receipts import (
    classify_worldbank_data_response as classify_worldbank_data_response,
)
from .acquisition_response_receipts import (
    classify_worldbank_indicator_metadata as classify_worldbank_indicator_metadata,
)
from .acquisition_response_receipts import (
    derive_r1_forensic_receipt as derive_r1_forensic_receipt,
)
from .catalog_candidate_admission import (
    D6CatalogCarrier as D6CatalogCarrier,
)
from .catalog_candidate_admission import (
    D6RouteSelection as D6RouteSelection,
)
from .catalog_candidate_admission import (
    _d6_carrier_matches_role as _d6_carrier_matches_role,
)
from .catalog_candidate_admission import (
    _d6_failed_and_auxiliary_roles as _d6_failed_and_auxiliary_roles,
)
from .catalog_candidate_admission import (
    _d6_filter_map as _d6_filter_map,
)
from .catalog_candidate_admission import (
    _d6_requires_source_characterization as _d6_requires_source_characterization,
)
from .catalog_candidate_admission import (
    _d6_transform_formula as _d6_transform_formula,
)
from .catalog_candidate_admission import (
    _load_d6_selection_policy as _load_d6_selection_policy,
)
from .catalog_candidate_admission import (
    _load_d6_transform_registry as _load_d6_transform_registry,
)
from .catalog_candidate_admission import (
    _raise_d6_no_certified_transform as _raise_d6_no_certified_transform,
)
from .catalog_candidate_admission import (
    _read_d6_catalog_denominator as _read_d6_catalog_denominator,
)
from .catalog_candidate_admission import (
    _require_d6_policy_purpose as _require_d6_policy_purpose,
)
from .catalog_candidate_admission import (
    _resolve_d6_catalog_role_policy as _resolve_d6_catalog_role_policy,
)
from .catalog_candidate_admission import (
    _resolve_d6_transform_family as _resolve_d6_transform_family,
)
from .catalog_candidate_admission import (
    _select_d6_carrier as _select_d6_carrier,
)
from .d6_route_selection import (
    _ALIVE_LIVENESS_PREFIX as _ALIVE_LIVENESS_PREFIX,
)
from .d6_route_selection import (
    DEFAULT_CARRIER_LIVENESS_UPDATE as DEFAULT_CARRIER_LIVENESS_UPDATE,
)
from .d6_route_selection import (
    DEFAULT_D6_ROUTE_SELECTION as DEFAULT_D6_ROUTE_SELECTION,
)
from .d6_route_selection import (
    _growth_backlog as _growth_backlog,
)
from .d6_route_selection import (
    _live_family_denominator as _live_family_denominator,
)
from .d6_route_selection import (
    _slot_units as _slot_units,
)
from .d6_route_selection import (
    derive_d6_route_selection as derive_d6_route_selection,
)
from .live_target_authority import (
    DEFAULT_TARGET_AUTHORITY_PROVISION as DEFAULT_TARGET_AUTHORITY_PROVISION,
)
from .live_target_authority import (
    DEFAULT_TARGET_AUTHORITY_REGISTRY as DEFAULT_TARGET_AUTHORITY_REGISTRY,
)
from .live_target_authority import (
    TARGET_SELECTION_SCHEMA_VERSION as TARGET_SELECTION_SCHEMA_VERSION,
)
from .live_target_authority import (
    LiveTargetSelection as LiveTargetSelection,
)
from .live_target_authority import (
    TargetAuthorityOwners as TargetAuthorityOwners,
)
from .live_target_authority import (
    _derive_l5_family_id as _derive_l5_family_id,
)
from .live_target_authority import (
    _file_sha256 as _file_sha256,
)
from .live_target_authority import (
    _json_string_lists as _json_string_lists,
)
from .live_target_authority import (
    _read_catalog_candidates as _read_catalog_candidates,
)
from .live_target_authority import (
    _validate_target_family_receipt as _validate_target_family_receipt,
)
from .live_target_authority import (
    build_selected_live_authority_entry as build_selected_live_authority_entry,
)
from .live_target_authority import (
    derive_live_attempt_id as derive_live_attempt_id,
)
from .live_target_authority import (
    derive_live_target_selection as derive_live_target_selection,
)
from .live_target_authority import (
    derive_target_authority_owners as derive_target_authority_owners,
)
from .live_target_authority import (
    derive_target_family_receipt as derive_target_family_receipt,
)
from .live_target_authority import (
    target_harness_receipt_path as target_harness_receipt_path,
)
from .metadata_execution_evidence import (
    DEFAULT_D6_PRIMARY_METADATA_EVIDENCE as DEFAULT_D6_PRIMARY_METADATA_EVIDENCE,
)
from .metadata_execution_evidence import (
    DEFAULT_D6_PRIMARY_METADATA_OWNER as DEFAULT_D6_PRIMARY_METADATA_OWNER,
)
from .metadata_execution_evidence import (
    DEFAULT_METADATA_EXECUTION_EVIDENCE as DEFAULT_METADATA_EXECUTION_EVIDENCE,
)
from .metadata_execution_evidence import (
    DEFAULT_METADATA_PROBE_OWNER as DEFAULT_METADATA_PROBE_OWNER,
)
from .metadata_execution_evidence import (
    D6MetadataProbeOwner as D6MetadataProbeOwner,
)
from .metadata_execution_evidence import (
    MetadataProbeExecutionEvidence as MetadataProbeExecutionEvidence,
)
from .metadata_execution_evidence import (
    MetadataProbeOwner as MetadataProbeOwner,
)
from .metadata_execution_evidence import (
    _derive_worldbank_metadata_harness_receipt_async as _derive_worldbank_metadata_harness_receipt_async,
)
from .metadata_execution_evidence import (
    _mapping_keys as _mapping_keys,
)
from .metadata_execution_evidence import (
    _reopen_metadata_probe_execution_evidence as _reopen_metadata_probe_execution_evidence,
)
from .metadata_execution_evidence import (
    _ReopenedMetadataProbe as _ReopenedMetadataProbe,
)
from .metadata_execution_evidence import (
    derive_d6_metadata_probe_execution_evidence as derive_d6_metadata_probe_execution_evidence,
)
from .metadata_execution_evidence import (
    derive_d6_metadata_probe_owner as derive_d6_metadata_probe_owner,
)
from .metadata_execution_evidence import (
    derive_metadata_probe_execution_evidence as derive_metadata_probe_execution_evidence,
)
from .metadata_execution_evidence import (
    derive_metadata_probe_owner as derive_metadata_probe_owner,
)
from .metadata_execution_evidence import (
    derive_worldbank_metadata_harness_receipt as derive_worldbank_metadata_harness_receipt,
)

_EXECUTABLE_TIERS = frozenset({"fetchable", "transport_ready"})


__all__ = [
    "DEFAULT_CARRIER_LIVENESS_UPDATE",
    "DEFAULT_D6_PRIMARY_METADATA_EVIDENCE",
    "DEFAULT_D6_PRIMARY_METADATA_OWNER",
    "DEFAULT_D6_ROUTE_SELECTION",
    "DEFAULT_METADATA_EXECUTION_EVIDENCE",
    "DEFAULT_METADATA_PROBE_OWNER",
    "DEFAULT_R1_FORENSIC_RECEIPT",
    "DEFAULT_TARGET_AUTHORITY_PROVISION",
    "DEFAULT_TARGET_AUTHORITY_REGISTRY",
    "DEFAULT_TARGET_HARNESS_RECEIPT",
    "AcquisitionSelectionError",
    "CarrierDataDisposition",
    "D6CatalogCarrier",
    "D6MetadataProbeOwner",
    "D6RouteSelection",
    "IndicatorMetadataDisposition",
    "LiveTargetSelection",
    "MetadataProbeExecutionEvidence",
    "MetadataProbeOwner",
    "R1AttemptForensicProjection",
    "R1ForensicReceipt",
    "TargetAuthorityOwners",
    "build_selected_live_authority_entry",
    "bytes_sha256",
    "classify_worldbank_data_response",
    "classify_worldbank_indicator_metadata",
    "derive_d6_metadata_probe_execution_evidence",
    "derive_d6_metadata_probe_owner",
    "derive_d6_route_selection",
    "derive_live_attempt_id",
    "derive_live_target_selection",
    "derive_metadata_probe_execution_evidence",
    "derive_metadata_probe_owner",
    "derive_r1_forensic_receipt",
    "derive_target_authority_owners",
    "derive_target_family_receipt",
    "derive_worldbank_metadata_harness_receipt",
    "target_harness_receipt_path",
]
