"""Runtime-safe read API for catalog Data Forge artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
        confidence_layer_vintage_for_snapshot_digest as confidence_layer_vintage_for_snapshot_digest,  # noqa: E501
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_ASSET_GROUP as CATALOG_ASSET_GROUP,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_BASE_SCHEMA_CONTRACTS as CATALOG_BASE_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_BASE_SCHEMA_IDS as CATALOG_BASE_SCHEMA_IDS,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_INDEX_KEY as CATALOG_INDEX_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_NORMALIZED_DATASETS_KEY as CATALOG_NORMALIZED_DATASETS_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_OBSERVATIONS_KEY as CATALOG_OBSERVATIONS_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_RAW_SOURCES_KEY as CATALOG_RAW_SOURCES_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_READINESS_KEY as CATALOG_READINESS_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_SCHEMA_CONTRACTS as CATALOG_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_SOURCE_MODULES_KEY as CATALOG_SOURCE_MODULES_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_SOURCE_PREFLIGHT_KEY as CATALOG_SOURCE_PREFLIGHT_KEY,
    )
    from polisyos.data_forge.domains.catalog import (
        CATALOG_SOURCE_SCHEMA_CONTRACTS as CATALOG_SOURCE_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.catalog import (
        CORE_CATALOG_SOURCE_MODULES as CORE_CATALOG_SOURCE_MODULES,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogBenchmarkReport as CatalogBenchmarkReport,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogExecutionTier as CatalogExecutionTier,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogHistoryPolicy as CatalogHistoryPolicy,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogQCReport as CatalogQCReport,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogReadinessPackage as CatalogReadinessPackage,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogReadinessSummary as CatalogReadinessSummary,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogRunLane as CatalogRunLane,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogRunProfile as CatalogRunProfile,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogShadowArtifact as CatalogShadowArtifact,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogShadowBundle as CatalogShadowBundle,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogShadowDiff as CatalogShadowDiff,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceAssetKeys as CatalogSourceAssetKeys,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceModulePlan as CatalogSourceModulePlan,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceModuleSpec as CatalogSourceModuleSpec,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceRegistryEntry as CatalogSourceRegistryEntry,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceRegistrySpec as CatalogSourceRegistrySpec,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceStage as CatalogSourceStage,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceStageContract as CatalogSourceStageContract,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogSourceSummary as CatalogSourceSummary,
    )
    from polisyos.data_forge.domains.catalog import (
        CatalogStageManifest as CatalogStageManifest,
    )
    from polisyos.data_forge.domains.catalog import (
        build_catalog_schema_registry as build_catalog_schema_registry,
    )
    from polisyos.data_forge.domains.catalog import (
        build_catalog_source_asset_group as build_catalog_source_asset_group,
    )
    from polisyos.data_forge.domains.catalog import (
        catalog_source_modules_from_registry as catalog_source_modules_from_registry,
    )
    from polisyos.data_forge.domains.catalog import (
        compare_catalog_shadow_bundles as compare_catalog_shadow_bundles,
    )
    from polisyos.data_forge.domains.catalog import (
        default_catalog_source_registry_path as default_catalog_source_registry_path,
    )
    from polisyos.data_forge.domains.catalog import (
        load_catalog_benchmark_report as load_catalog_benchmark_report,
    )
    from polisyos.data_forge.domains.catalog import (
        load_catalog_qc_report as load_catalog_qc_report,
    )
    from polisyos.data_forge.domains.catalog import (
        load_catalog_readiness_package as load_catalog_readiness_package,
    )
    from polisyos.data_forge.domains.catalog import (
        load_catalog_shadow_bundle as load_catalog_shadow_bundle,
    )
    from polisyos.data_forge.domains.catalog import (
        load_catalog_source_registry as load_catalog_source_registry,
    )
    from polisyos.data_forge.domains.catalog import (
        plan_catalog_source_modules as plan_catalog_source_modules,
    )
    from polisyos.data_forge.domains.catalog import (
        plan_catalog_source_stage_contracts as plan_catalog_source_stage_contracts,
    )
    from polisyos.data_forge.domains.catalog import (
        select_catalog_source_modules as select_catalog_source_modules,
    )
    from polisyos.data_forge.domains.catalog._resources import (
        catalog_default_resource_path as catalog_default_resource_path,
    )
    from polisyos.data_forge.domains.catalog.batch.config import (
        parse_profile_input_coverage as parse_profile_input_coverage,
    )
    from polisyos.data_forge.domains.catalog.batch.config import (
        profile_input_coverage_currentness as profile_input_coverage_currentness,
    )
    from polisyos.data_forge.domains.catalog.batch.material_inputs import (
        WVSIndicatorRegistryError as WVSIndicatorRegistryError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_ACQUISITION_AUTHORITY_PROVISION as DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY as DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AcquisitionAuthorityEntry as AcquisitionAuthorityEntry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AcquisitionAuthorityError as AcquisitionAuthorityError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AcquisitionAuthorityProvision as AcquisitionAuthorityProvision,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AcquisitionAuthorityRegistry as AcquisitionAuthorityRegistry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        AuthoritySchemaColumn as AuthoritySchemaColumn,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        CanonicalAcquisitionAuthority as CanonicalAcquisitionAuthority,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LiveHarnessReceiptProvisionEntry as LiveHarnessReceiptProvisionEntry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LiveSourceExecutionEvidence as LiveSourceExecutionEvidence,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LocalRightsTrustedAuthority as LocalRightsTrustedAuthority,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LocalRightsTrustRegistry as LocalRightsTrustRegistry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LocalSourceRightsDeclaration as LocalSourceRightsDeclaration,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        LocalSourceRightsReceipt as LocalSourceRightsReceipt,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        ResolvedAcquisitionAuthority as ResolvedAcquisitionAuthority,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        ResolvedL5Trust as ResolvedL5Trust,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        ResolvedLiveHarnessReceipt as ResolvedLiveHarnessReceipt,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_acquisition_authority_provision as build_acquisition_authority_provision,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_authority_entry as build_authority_entry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_authority_registry as build_authority_registry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_live_source_execution_evidence as build_live_source_execution_evidence,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_local_rights_trust_registry as build_local_rights_trust_registry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        build_local_source_rights_declaration as build_local_source_rights_declaration,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        derive_catalog_unit_from_text as derive_catalog_unit_from_text,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        derive_license_disposition as derive_license_disposition,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        normalize_acquisition_unit as normalize_acquisition_unit,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        normalized_acquisition_source_body as normalized_acquisition_source_body,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        resolve_live_temporal_bounds as resolve_live_temporal_bounds,
    )
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        verify_local_source_rights as verify_local_source_rights,
    )
    from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
        iso2_to_iso3 as iso2_to_iso3,
    )
    from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
        normalize_country_code as normalize_country_code,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogReadSourceError as CatalogReadSourceError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionCandidateEvaluation as CatalogSelectionCandidateEvaluation,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionCandidateEvidence as CatalogSelectionCandidateEvidence,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionError as CatalogSelectionError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionPolicyConfig as CatalogSelectionPolicyConfig,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionRejectionCode as CatalogSelectionRejectionCode,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionRoleConfig as CatalogSelectionRoleConfig,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        DerivationCatalogSelectionOwner as DerivationCatalogSelectionOwner,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        catalog_selection_candidate_rank as catalog_selection_candidate_rank,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        catalog_selection_policies_for_purpose as catalog_selection_policies_for_purpose,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        evaluate_catalog_selection_candidate as evaluate_catalog_selection_candidate,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        load_derivation_catalog_selection as load_derivation_catalog_selection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        resolve_catalog_selection_policy as resolve_catalog_selection_policy,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        DEFAULT_ACQUISITION_OVERLAY_PATH as DEFAULT_ACQUISITION_OVERLAY_PATH,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION as LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        AcquisitionDatasetRegistration as AcquisitionDatasetRegistration,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ActivatedAcquisitionObservationProjection as ActivatedAcquisitionObservationProjection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        BaselineIdentity as BaselineIdentity,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        BaselineMutationError as BaselineMutationError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CanonicalAcquisitionObservation as CanonicalAcquisitionObservation,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionEpochProjection as CatalogAcquisitionEpochProjection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionEventProjection as CatalogAcquisitionEventProjection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionOverlay as CatalogAcquisitionOverlay,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionPassportProjection as CatalogAcquisitionPassportProjection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        CatalogAcquisitionStateProjection as CatalogAcquisitionStateProjection,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        LegacyAdmissionPassport as LegacyAdmissionPassport,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        MetricFieldBinding as MetricFieldBinding,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        ObservationProvenanceClass as ObservationProvenanceClass,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        OverlayAdmissionError as OverlayAdmissionError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        OverlayAdmissionReceipt as OverlayAdmissionReceipt,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        acquisition_overlay_admission_fence as acquisition_overlay_admission_fence,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        acquisition_overlay_admission_lock_path as acquisition_overlay_admission_lock_path,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        build_metric_field_binding as build_metric_field_binding,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        default_acquisition_overlay_path as default_acquisition_overlay_path,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        derive_canonical_observations as derive_canonical_observations,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        open_catalog_read_session as open_catalog_read_session,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        project_catalog_acquisition_state as project_catalog_acquisition_state,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        validate_overlay_admission_receipt as validate_overlay_admission_receipt,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        ProxyCandidate as ProxyCandidate,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        ProxyChain as ProxyChain,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        compose_confidence_chain as compose_confidence_chain,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        compose_confidence_harmonic as compose_confidence_harmonic,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        resolve_proxy as resolve_proxy,
    )
    from polisyos.data_forge.domains.catalog.knowledge.proxy_resolver import (
        validate_proxy as validate_proxy,
    )
    from polisyos.data_forge.domains.catalog.knowledge.registry import (
        DatasetRegistry as DatasetRegistry,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import (
        DatasetCatalogGraph as DatasetCatalogGraph,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import (
        SearchFilters as SearchFilters,
    )
    from polisyos.data_forge.domains.catalog.knowledge.store import (
        DatasetCatalogStore as DatasetCatalogStore,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogContentIdentity as CatalogContentIdentity,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogEmbeddingProfile as CatalogEmbeddingProfile,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogFetchBinding as CatalogFetchBinding,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogFetchRequest as CatalogFetchRequest,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogFetchResolution as CatalogFetchResolution,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        CatalogQueryGenerationContext as CatalogQueryGenerationContext,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetSearchResponse as DatasetSearchResponse,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetSearchResult as DatasetSearchResult,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        MetricBindingMatch as MetricBindingMatch,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        PStarZResult as PStarZResult,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        ResolvedFetchTarget as ResolvedFetchTarget,
    )
    from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
        VariableAlignment as VariableAlignment,
    )
    from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
        default_seed_alignments_path as default_seed_alignments_path,
    )
    from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
        load_seed_alignments as load_seed_alignments,
    )
    from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
        score_variable_pair as score_variable_pair,
    )
    from polisyos.data_forge.domains.catalog.selection import (
        validate_catalog_run_profile as validate_catalog_run_profile,
    )
    from polisyos.data_forge.kernel.embeddings import (
        GENERATION_SELECTOR_FILENAME as GENERATION_SELECTOR_FILENAME,
    )
    from polisyos.data_forge.kernel.embeddings import (
        EmbeddingGenerationRef as EmbeddingGenerationRef,
    )
    from polisyos.data_forge.kernel.embeddings import (
        embedding_generation_manifest as embedding_generation_manifest,
    )
    from polisyos.data_forge.kernel.embeddings import (
        embedding_generation_matches_encoder as embedding_generation_matches_encoder,
    )
    from polisyos.data_forge.kernel.embeddings import (
        resolve_embedding_generation as resolve_embedding_generation,
    )
    from polisyos.data_forge.kernel.io.generation_basis import (
        generation_basis_matches_members as generation_basis_matches_members,
    )

_CATALOG_DOMAIN = "polisyos.data_forge.domains.catalog"
_EXPORTS = {
    "normalize_country_code": ("polisyos.data_forge.domains.catalog.knowledge.country_codes"),
    "iso2_to_iso3": "polisyos.data_forge.domains.catalog.knowledge.country_codes",
    "validate_catalog_run_profile": "polisyos.data_forge.domains.catalog.selection",
    "parse_profile_input_coverage": "polisyos.data_forge.domains.catalog.batch.config",
    "profile_input_coverage_currentness": "polisyos.data_forge.domains.catalog.batch.config",
    "confidence_layer_vintage_for_snapshot_digest": (
        "polisyos.data_forge.domains.academic.knowledge.skg_versioning"
    ),
    "GENERATION_SELECTOR_FILENAME": "polisyos.data_forge.kernel.embeddings",
    "embedding_generation_manifest": "polisyos.data_forge.kernel.embeddings",
    "LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION": (
        "polisyos.data_forge.domains.catalog.knowledge.overlay"
    ),
    "LegacyAdmissionPassport": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "CATALOG_BASE_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_BASE_SCHEMA_IDS": _CATALOG_DOMAIN,
    "CATALOG_ASSET_GROUP": _CATALOG_DOMAIN,
    "CATALOG_INDEX_KEY": _CATALOG_DOMAIN,
    "CATALOG_NORMALIZED_DATASETS_KEY": _CATALOG_DOMAIN,
    "CATALOG_OBSERVATIONS_KEY": _CATALOG_DOMAIN,
    "CATALOG_RAW_SOURCES_KEY": _CATALOG_DOMAIN,
    "CATALOG_READINESS_KEY": _CATALOG_DOMAIN,
    "CATALOG_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_SCHEMA_CONTRACTS": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_MODULES_KEY": _CATALOG_DOMAIN,
    "CATALOG_SOURCE_PREFLIGHT_KEY": _CATALOG_DOMAIN,
    "CORE_CATALOG_SOURCE_MODULES": _CATALOG_DOMAIN,
    "CatalogBenchmarkReport": _CATALOG_DOMAIN,
    "CatalogExecutionTier": _CATALOG_DOMAIN,
    "CatalogHistoryPolicy": _CATALOG_DOMAIN,
    "CatalogQCReport": _CATALOG_DOMAIN,
    "CatalogReadinessSummary": _CATALOG_DOMAIN,
    "CatalogReadinessPackage": _CATALOG_DOMAIN,
    "CatalogRunLane": _CATALOG_DOMAIN,
    "CatalogRunProfile": _CATALOG_DOMAIN,
    "CatalogShadowArtifact": _CATALOG_DOMAIN,
    "CatalogShadowBundle": _CATALOG_DOMAIN,
    "CatalogShadowDiff": _CATALOG_DOMAIN,
    "CatalogSourceAssetKeys": _CATALOG_DOMAIN,
    "CatalogSourceModulePlan": _CATALOG_DOMAIN,
    "CatalogSourceModuleSpec": _CATALOG_DOMAIN,
    "CatalogSourceRegistryEntry": _CATALOG_DOMAIN,
    "CatalogSourceRegistrySpec": _CATALOG_DOMAIN,
    "CatalogSourceStage": _CATALOG_DOMAIN,
    "CatalogSourceStageContract": _CATALOG_DOMAIN,
    "CatalogSourceSummary": _CATALOG_DOMAIN,
    "CatalogSelectionCandidateEvaluation": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogSelectionCandidateEvidence": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogReadSourceError": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogSelectionError": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogSelectionPolicyConfig": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogSelectionRejectionCode": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogSelectionRoleConfig": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "CatalogStageManifest": _CATALOG_DOMAIN,
    "DatasetCatalogGraph": "polisyos.data_forge.domains.catalog.knowledge.search",
    "EmbeddingGenerationRef": "polisyos.data_forge.kernel.embeddings",
    "DerivationCatalogSelectionOwner": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "DatasetCatalogStore": "polisyos.data_forge.domains.catalog.knowledge.store",
    "DEFAULT_ACQUISITION_OVERLAY_PATH": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "DEFAULT_ACQUISITION_AUTHORITY_PROVISION": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "DatasetRegistry": "polisyos.data_forge.domains.catalog.knowledge.registry",
    "DatasetSearchResponse": "polisyos.data_forge.domains.catalog.knowledge.types",
    "DatasetSearchResult": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogEmbeddingProfile": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogQueryGenerationContext": "polisyos.data_forge.domains.catalog.knowledge.types",
    "MetricBindingMatch": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogContentIdentity": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogFetchBinding": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogFetchRequest": "polisyos.data_forge.domains.catalog.knowledge.types",
    "CatalogFetchResolution": "polisyos.data_forge.domains.catalog.knowledge.types",
    "AcquisitionDatasetRegistration": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "BaselineIdentity": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "BaselineMutationError": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "derive_canonical_observations": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "normalized_acquisition_source_body": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "CanonicalAcquisitionObservation": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "CatalogAcquisitionOverlay": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "acquisition_overlay_admission_fence": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "acquisition_overlay_admission_lock_path": (
        "polisyos.data_forge.domains.catalog.knowledge.overlay"
    ),
    "CatalogAcquisitionEpochProjection": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "CatalogAcquisitionEventProjection": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "ActivatedAcquisitionObservationProjection": (
        "polisyos.data_forge.domains.catalog.knowledge.overlay"
    ),
    "CatalogAcquisitionPassportProjection": (
        "polisyos.data_forge.domains.catalog.knowledge.overlay"
    ),
    "CatalogAcquisitionStateProjection": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "AcquisitionAuthorityEntry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "AcquisitionAuthorityProvision": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "AcquisitionAuthorityError": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "AcquisitionAuthorityRegistry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "AuthoritySchemaColumn": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "CanonicalAcquisitionAuthority": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LiveSourceExecutionEvidence": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LiveHarnessReceiptProvisionEntry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LocalSourceRightsDeclaration": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LocalSourceRightsReceipt": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LocalRightsTrustedAuthority": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "LocalRightsTrustRegistry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "ResolvedAcquisitionAuthority": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "ResolvedL5Trust": ("polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"),
    "ResolvedLiveHarnessReceipt": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "MetricFieldBinding": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "ObservationProvenanceClass": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "OverlayAdmissionError": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "OverlayAdmissionReceipt": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "PStarZResult": "polisyos.data_forge.domains.catalog.knowledge.types",
    "ProxyCandidate": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "ProxyChain": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "ResolvedFetchTarget": "polisyos.data_forge.domains.catalog.knowledge.types",
    "SearchFilters": "polisyos.data_forge.domains.catalog.knowledge.search",
    "VariableAlignment": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "build_catalog_source_asset_group": _CATALOG_DOMAIN,
    "build_authority_entry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_acquisition_authority_provision": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_authority_registry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_live_source_execution_evidence": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_local_source_rights_declaration": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_local_rights_trust_registry": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_metric_field_binding": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "default_acquisition_overlay_path": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "derive_catalog_unit_from_text": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "derive_license_disposition": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "build_catalog_schema_registry": _CATALOG_DOMAIN,
    "catalog_source_modules_from_registry": _CATALOG_DOMAIN,
    "catalog_selection_candidate_rank": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "catalog_selection_policies_for_purpose": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "compose_confidence_chain": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "compose_confidence_harmonic": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "compare_catalog_shadow_bundles": _CATALOG_DOMAIN,
    "default_catalog_source_registry_path": _CATALOG_DOMAIN,
    "catalog_default_resource_path": "polisyos.data_forge.domains.catalog._resources",
    "WVSIndicatorRegistryError": ("polisyos.data_forge.domains.catalog.batch.material_inputs"),
    "default_seed_alignments_path": (
        "polisyos.data_forge.domains.catalog.knowledge.variable_alignment"
    ),
    "embedding_generation_matches_encoder": "polisyos.data_forge.kernel.embeddings",
    "generation_basis_matches_members": "polisyos.data_forge.kernel.io.generation_basis",
    "load_catalog_benchmark_report": _CATALOG_DOMAIN,
    "load_catalog_qc_report": _CATALOG_DOMAIN,
    "load_catalog_readiness_package": _CATALOG_DOMAIN,
    "load_catalog_shadow_bundle": _CATALOG_DOMAIN,
    "load_catalog_source_registry": _CATALOG_DOMAIN,
    "load_derivation_catalog_selection": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "load_seed_alignments": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "normalize_acquisition_unit": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "open_catalog_read_session": "polisyos.data_forge.domains.catalog.knowledge.overlay",
    "project_catalog_acquisition_state": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "validate_overlay_admission_receipt": ("polisyos.data_forge.domains.catalog.knowledge.overlay"),
    "plan_catalog_source_stage_contracts": _CATALOG_DOMAIN,
    "plan_catalog_source_modules": _CATALOG_DOMAIN,
    "resolve_proxy": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "resolve_embedding_generation": "polisyos.data_forge.kernel.embeddings",
    "resolve_live_temporal_bounds": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
    "resolve_catalog_selection_policy": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "score_variable_pair": "polisyos.data_forge.domains.catalog.knowledge.variable_alignment",
    "evaluate_catalog_selection_candidate": (
        "polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection"
    ),
    "select_catalog_source_modules": _CATALOG_DOMAIN,
    "validate_proxy": "polisyos.data_forge.domains.catalog.knowledge.proxy_resolver",
    "verify_local_source_rights": (
        "polisyos.data_forge.domains.catalog.knowledge.acquisition_authority"
    ),
}


def __getattr__(name: str) -> object:
    """Lazily resolve catalog exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public catalog read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


def _catalog_graph_cache_root() -> Path:
    """Resolve the root holding content-addressed catalog graphs."""

    override = os.environ.get("POLISYOS_CACHE_HOME")
    if override:
        base = Path(override).expanduser()
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg).expanduser() if xdg else Path.home() / ".cache" / "polisyos"
    return base / "catalog-graphs"


def _catalog_graph_cache_key(*, kind: str, records: Sequence[object]) -> str:
    """Derive the content key identifying a built catalog graph.

    The key covers both the records the graph is built from and the builder
    module that writes them, so a cache hit is indistinguishable from a rebuild.
    """

    from polisyos.data_forge.domains.catalog.batch import graph_builder

    digest = hashlib.sha256(kind.encode("utf-8"))
    builder_source = Path(graph_builder.__file__)
    digest.update(builder_source.read_bytes())
    for record in records:
        digest.update(record.model_dump_json().encode("utf-8"))  # type: ignore[attr-defined]
        digest.update(b"\x00")
    return digest.hexdigest()[:32]


def _cached_catalog_graph_root(*, cache_key: str, build: Callable[[Path], None]) -> Path:
    """Return the content-addressed root for ``cache_key``, building it once.

    The graph is built into a staging directory and published with an atomic
    rename, so a visible root is always a complete build and concurrent callers
    converge on a single copy instead of leaking one temporary tree per call.
    """

    root = _catalog_graph_cache_root() / cache_key
    if root.is_dir():
        return root
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".staging-{cache_key}-", dir=root.parent))
    try:
        build(staging)
        os.replace(staging, root)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if not root.is_dir():
            raise
    return root


def build_slice0_fixture_catalog_graph(graph_root: str | Path | None = None) -> object:
    """Build the committed GY Slice-0 fixture catalog graph for runtime bindings."""

    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetAccess,
        DatasetCoverage,
        DatasetQuality,
        DatasetRecord,
        DistributionRecord,
    )

    dataset_catalog_graph_cls = load_lazy_export(
        "DatasetCatalogGraph",
        exports=_EXPORTS,
        module_name=__name__,
        namespace=globals(),
    )
    records = [
        DatasetRecord(
            id="catalog://worldbank/enterprise-surveys/ukraine/msme-credit-access",
            title="Ukraine MSME credit access World Bank firm measurement",
            description="Enterprise Survey measurement for firm credit access in Ukraine.",
            publisher="World Bank",
            themes=["economy", "finance", "business"],
            keywords=["ukraine", "msme", "firm", "credit", "enterprise survey"],
            source="worldbank",
            source_portal="worldbank",
            dataset_id="IC.FRM.ACCS.ZS",
            source_dataset_id="IC.FRM.ACCS.ZS",
            execution_tier="transport_ready",
            update_frequency="annual",
            license="World Bank Open Data Terms",
            polisyos_metrics=["msme_credit_access"],
            variables=["country_code", "year", "firm_size", "credit_access"],
            spatial="UA",
            coverage=DatasetCoverage(
                countries=["UA"],
                time_start="2020",
                time_end="2024",
                granularity="firm-year",
            ),
            access=DatasetAccess(license="World Bank Open Data Terms"),
            quality=DatasetQuality(
                description_score=0.95,
                machine_readable_score=1.0,
                parser_support_score=1.0,
                freshness_score=0.9,
                execution_readiness_score=0.92,
            ),
            preferred_distribution_id="dist-worldbank-ua-msme-credit",
            distributions=[
                DistributionRecord(
                    id="dist-worldbank-ua-msme-credit",
                    connector_type="worldbank.wdi",
                    source_locator="IC.FRM.ACCS.ZS",
                    profile_id="worldbank",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.92,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://worldbank/global-findex/ukraine-account-credit",
            title="Ukraine Global Findex borrowing account and credit access measurement",
            description=(
                "World Bank Global Findex indicators on account ownership, borrowing, "
                "formal credit and financial inclusion in Ukraine."
            ),
            publisher="World Bank",
            themes=["finance", "inclusion"],
            keywords=["ukraine", "credit", "borrowing", "financial inclusion"],
            source="worldbank",
            source_portal="worldbank",
            dataset_id="FX.OWN.TOTL.ZS",
            source_dataset_id="FX.OWN.TOTL.ZS",
            execution_tier="transport_ready",
            update_frequency="triennial",
            license="World Bank Open Data Terms",
            polisyos_metrics=["msme_credit_access", "financial_inclusion"],
            variables=["country_code", "year", "formal_borrowing", "account_ownership"],
            spatial="UA",
            coverage=DatasetCoverage(
                countries=["UA"],
                time_start="2017",
                time_end="2024",
                granularity="country-year",
            ),
            access=DatasetAccess(license="World Bank Open Data Terms"),
            quality=DatasetQuality(
                description_score=0.9,
                machine_readable_score=1.0,
                parser_support_score=1.0,
                freshness_score=0.85,
                execution_readiness_score=0.88,
            ),
            preferred_distribution_id="dist-worldbank-ua-findex-credit",
            distributions=[
                DistributionRecord(
                    id="dist-worldbank-ua-findex-credit",
                    connector_type="worldbank.wdi",
                    source_locator="FX.OWN.TOTL.ZS",
                    profile_id="worldbank",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.88,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://ilo/sme-finance/ukraine-credit-constraints",
            title="Ukraine SME finance credit constraints labour market enterprise measurement",
            description=(
                "ILO-aligned enterprise finance indicators for credit constraints, "
                "working capital and firm employment in Ukraine."
            ),
            publisher="International Labour Organization",
            themes=["labour", "enterprise", "finance"],
            keywords=["ukraine", "sme", "credit", "firm", "employment"],
            source="ilo",
            source_portal="ilo",
            dataset_id="ILO_SME_CREDIT_UA",
            source_dataset_id="ILO_SME_CREDIT_UA",
            execution_tier="fetchable",
            update_frequency="annual",
            license="ILO open data terms",
            polisyos_metrics=["msme_credit_access", "firm_employment"],
            variables=["country_code", "year", "credit_constraint", "employment"],
            spatial="UA",
            coverage=DatasetCoverage(
                countries=["UA"],
                time_start="2019",
                time_end="2024",
                granularity="firm-year",
            ),
            access=DatasetAccess(license="ILO open data terms"),
            quality=DatasetQuality(
                description_score=0.86,
                machine_readable_score=0.9,
                parser_support_score=0.8,
                freshness_score=0.8,
                execution_readiness_score=0.78,
            ),
            preferred_distribution_id="dist-ilo-ua-sme-credit",
            distributions=[
                DistributionRecord(
                    id="dist-ilo-ua-sme-credit",
                    connector_type="sdmx.source",
                    source_locator="ILO_SME_CREDIT_UA",
                    profile_id="ilo",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.78,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://data-gov-ua/business-credit-registrations",
            title="Ukraine business registration credit program participation measurement",
            description=(
                "Ukrainian open-data business registry proxy for SME credit program "
                "participation and firm registration status."
            ),
            publisher="data.gov.ua",
            themes=["business", "finance", "administrative"],
            keywords=["ukraine", "msme", "credit", "business registry", "program"],
            source="data_gov_ua_exec",
            source_portal="data.gov.ua",
            dataset_id="ua-business-credit-programs",
            source_dataset_id="ua-business-credit-programs",
            execution_tier="fetchable",
            update_frequency="monthly",
            license="Open Data Commons",
            polisyos_metrics=["msme_credit_access", "program_participation"],
            variables=["edrpou", "program_id", "credit_status", "registration_status"],
            spatial="UA",
            coverage=DatasetCoverage(
                countries=["UA"],
                time_start="2020",
                time_end="2024",
                granularity="firm-month",
            ),
            access=DatasetAccess(license="Open Data Commons"),
            quality=DatasetQuality(
                description_score=0.82,
                machine_readable_score=0.9,
                parser_support_score=0.75,
                freshness_score=0.9,
                execution_readiness_score=0.74,
            ),
            preferred_distribution_id="dist-data-gov-ua-business-credit",
            distributions=[
                DistributionRecord(
                    id="dist-data-gov-ua-business-credit",
                    connector_type="ckan.resource",
                    source_locator="ua-business-credit-programs",
                    profile_id="data_gov_ua",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.74,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://oecd/enterprise-finance/ukraine-sme-credit",
            title="OECD SME enterprise finance credit access Ukraine comparison",
            description=(
                "OECD enterprise finance and SME credit access comparative measurement "
                "used as corroborating source for Ukrainian firm credit constraints."
            ),
            publisher="OECD",
            themes=["enterprise", "finance"],
            keywords=["ukraine", "sme", "credit", "finance", "oecd"],
            source="oecd",
            source_portal="oecd",
            dataset_id="OECD_SME_FINANCE_UA",
            source_dataset_id="OECD_SME_FINANCE_UA",
            execution_tier="catalog",
            update_frequency="annual",
            license="OECD terms",
            polisyos_metrics=["msme_credit_access", "enterprise_finance"],
            variables=["country_code", "year", "sme_lending", "credit_conditions"],
            spatial="UA",
            coverage=DatasetCoverage(
                countries=["UA"],
                time_start="2018",
                time_end="2023",
                granularity="country-year",
            ),
            access=DatasetAccess(license="OECD terms"),
            quality=DatasetQuality(
                description_score=0.82,
                machine_readable_score=0.7,
                parser_support_score=0.55,
                freshness_score=0.7,
                execution_readiness_score=0.58,
            ),
            preferred_distribution_id="dist-oecd-ua-sme-credit",
            distributions=[
                DistributionRecord(
                    id="dist-oecd-ua-sme-credit",
                    connector_type="sdmx.source",
                    source_locator="OECD_SME_FINANCE_UA",
                    profile_id="oecd",
                    parser_supported=False,
                    machine_readable=True,
                    quality_score=0.58,
                )
            ],
        ),
        DatasetRecord(
            id="tourism_attraction_reviews",
            title="Tourism attraction review snippets and local development traffic",
            description=(
                "Unverified local tourism review text and attraction traffic snippets; "
                "negative control for MSME credit access despite mentioning Ukraine."
            ),
            publisher="Example Reviews",
            themes=["tourism", "local-development"],
            keywords=["ukraine", "tourism", "attraction", "traffic", "reviews"],
            source="web_reviews",
            source_portal="reviews",
            dataset_id="tourism_reviews",
            source_dataset_id="tourism_reviews",
            execution_tier="discovery_only",
            update_frequency="unknown",
            polisyos_metrics=["tourism_visits"],
            variables=["place", "review_text"],
            spatial="UA",
            coverage=DatasetCoverage(countries=["UA"], granularity="review"),
            preferred_distribution_id="dist-tourism-reviews",
            distributions=[
                DistributionRecord(
                    id="dist-tourism-reviews",
                    connector_type="rest.json",
                    source_locator="https://example.test/tourism",
                    profile_id="rest_json",
                    parser_supported=False,
                    machine_readable=False,
                    quality_score=0.2,
                )
            ],
        ),
        DatasetRecord(
            id="synthetic_llm_only_credit_claim",
            title="Synthetic LLM-only Ukraine MSME credit claim",
            description=(
                "A generated narrative about MSME credit access with no source contract, "
                "producer root, distribution or measurement lineage."
            ),
            publisher="LLM candidate",
            themes=["finance"],
            keywords=["ukraine", "msme", "credit", "synthetic"],
            source="llm_candidate",
            source_portal="none",
            dataset_id="synthetic_llm_only_credit_claim",
            source_dataset_id="synthetic_llm_only_credit_claim",
            execution_tier="discovery_only",
            update_frequency="none",
            polisyos_metrics=["msme_credit_access"],
            variables=["claim_text"],
            spatial="UA",
            coverage=DatasetCoverage(countries=["UA"], granularity="narrative"),
            preferred_distribution_id="dist-synthetic-llm-credit-claim",
            distributions=[
                DistributionRecord(
                    id="dist-synthetic-llm-credit-claim",
                    connector_type="rest.json",
                    source_locator="https://example.test/synthetic-credit-claim",
                    profile_id="llm_candidate",
                    parser_supported=False,
                    machine_readable=False,
                    quality_score=0.0,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://who/ukraine-health-facility-capacity",
            title="Ukraine health facility capacity measurement",
            description="WHO health facility and hospital capacity indicators for Ukraine.",
            publisher="WHO",
            themes=["health"],
            keywords=["ukraine", "health", "hospital", "capacity"],
            source="who",
            source_portal="who",
            dataset_id="WHO_HEALTH_CAPACITY_UA",
            source_dataset_id="WHO_HEALTH_CAPACITY_UA",
            execution_tier="fetchable",
            update_frequency="annual",
            polisyos_metrics=["health_capacity"],
            variables=["hospital_beds", "facility_count"],
            spatial="UA",
            coverage=DatasetCoverage(countries=["UA"], time_end="2024"),
            preferred_distribution_id="dist-who-ua-health-capacity",
            distributions=[
                DistributionRecord(
                    id="dist-who-ua-health-capacity",
                    connector_type="sdmx.source",
                    source_locator="WHO_HEALTH_CAPACITY_UA",
                    profile_id="who",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.8,
                )
            ],
        ),
        DatasetRecord(
            id="catalog://unesco/ukraine-school-enrollment",
            title="Ukraine school enrollment education measurement",
            description="UNESCO education enrollment indicators for Ukraine.",
            publisher="UNESCO UIS",
            themes=["education"],
            keywords=["ukraine", "education", "school", "enrollment"],
            source="unesco_uis",
            source_portal="unesco",
            dataset_id="UNESCO_ENROLLMENT_UA",
            source_dataset_id="UNESCO_ENROLLMENT_UA",
            execution_tier="fetchable",
            update_frequency="annual",
            polisyos_metrics=["school_enrollment"],
            variables=["enrollment_rate", "grade"],
            spatial="UA",
            coverage=DatasetCoverage(countries=["UA"], time_end="2024"),
            preferred_distribution_id="dist-unesco-ua-enrollment",
            distributions=[
                DistributionRecord(
                    id="dist-unesco-ua-enrollment",
                    connector_type="sdmx.source",
                    source_locator="UNESCO_ENROLLMENT_UA",
                    profile_id="unesco_uis",
                    parser_supported=True,
                    machine_readable=True,
                    quality_score=0.8,
                )
            ],
        ),
    ]

    def build(target: Path) -> None:
        build_graph(records=iter(records), db_path=target / "catalog.duckdb")

    if graph_root is not None:
        root = Path(graph_root)
        root.mkdir(parents=True, exist_ok=True)
        build(root)
    else:
        root = _cached_catalog_graph_root(
            cache_key=_catalog_graph_cache_key(kind="gy-slice0-fixture", records=records),
            build=build,
        )
    return dataset_catalog_graph_cls(db_path=root / "catalog.duckdb", index_dir=root)


def build_production_data_contract_catalog_graph(
    *,
    production_root: str | Path | None = None,
    graph_root: str | Path | None = None,
) -> object:
    """Build a DatasetCatalogGraph from committed production-data contracts."""

    from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph

    dataset_catalog_graph_cls = load_lazy_export(
        "DatasetCatalogGraph",
        exports=_EXPORTS,
        module_name=__name__,
        namespace=globals(),
    )
    source_root = (
        Path(production_root).expanduser()
        if production_root is not None
        else _default_production_data_root()
    )
    curated_root = source_root / "curated" if (source_root / "curated").exists() else source_root
    contracts_payload = _read_catalog_json(curated_root / "data_contracts.json")
    bindings_payload = _read_catalog_json(curated_root / "source_bindings.json")
    generated_at = str(
        contracts_payload.get("generated_at") or bindings_payload.get("generated_at") or ""
    )
    contracts = {
        str(item.get("metric_id")): item
        for item in contracts_payload.get("contracts") or []
        if isinstance(item, dict) and item.get("metric_id")
    }
    records = [
        _production_contract_dataset_record(
            contract=contracts[str(binding["metric_id"])],
            binding=binding,
            generated_at=generated_at,
        )
        for binding in bindings_payload.get("bindings") or []
        if isinstance(binding, dict)
        and binding.get("metric_id")
        and str(binding["metric_id"]) in contracts
    ]
    if not records:
        raise FileNotFoundError(
            f"no production data contracts/source bindings found under {curated_root}"
        )

    def build(target: Path) -> None:
        build_graph(records=iter(records), db_path=target / "catalog.duckdb")

    if graph_root is not None:
        root = Path(graph_root)
        root.mkdir(parents=True, exist_ok=True)
        build(root)
    else:
        root = _cached_catalog_graph_root(
            cache_key=_catalog_graph_cache_key(kind="production-data-contracts", records=records),
            build=build,
        )
    return dataset_catalog_graph_cls(db_path=root / "catalog.duckdb", index_dir=root)


def _production_contract_dataset_record(
    *,
    contract: dict[str, object],
    binding: dict[str, object],
    generated_at: str,
) -> object:
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetAccess,
        DatasetCoverage,
        DatasetQuality,
        DatasetRecord,
        DistributionRecord,
    )

    metric_id = str(contract.get("metric_id") or binding.get("metric_id") or "")
    connector_id = str(binding.get("connector_id") or "")
    profile_id = str(binding.get("profile_id") or connector_id)
    dataset_id = str(binding.get("dataset_id") or metric_id)
    trust = _bounded_float(binding.get("trust"), default=0.5)
    jurisdiction = str(contract.get("jurisdiction") or "").strip()
    dimensions = [str(item) for item in contract.get("dimensions") or []]
    aliases = [str(item) for item in contract.get("aliases") or []]
    source_column = str(contract.get("source_column") or "").strip()
    variables = [item for item in dict.fromkeys([source_column, *dimensions, *aliases]) if item]
    connector_slug = _catalog_slug(connector_id or "production")
    dataset_slug = _catalog_slug(dataset_id or metric_id)
    distribution_id = f"dist-production-{connector_slug}-{dataset_slug}"
    parser_ready = connector_id in {"worldbank.wdi", "static_csv"}
    return DatasetRecord(
        id=f"catalog://production-data/{connector_slug}/{dataset_slug}",
        title=str(contract.get("display_name") or metric_id),
        description=str(contract.get("description") or ""),
        publisher=connector_id or "production_data",
        themes=[str(item) for item in contract.get("tags") or []],
        keywords=[
            metric_id,
            *aliases,
            *[str(item) for item in contract.get("tags") or []],
        ],
        source=connector_id.split(".", maxsplit=1)[0] if connector_id else "production_data",
        source_portal=connector_id or "production_data",
        dataset_id=dataset_id,
        source_dataset_id=dataset_id,
        execution_tier="transport_ready" if connector_id == "worldbank.wdi" else "fetchable",
        update_frequency=str(contract.get("granularity") or ""),
        last_updated=generated_at or None,
        license="production-data curated contract",
        polisyos_metrics=[metric_id],
        variables=variables,
        spatial=jurisdiction,
        coverage=DatasetCoverage(
            countries=[jurisdiction] if jurisdiction else [],
            granularity=str(contract.get("granularity") or ""),
        ),
        access=DatasetAccess(license="production-data curated contract"),
        quality=DatasetQuality(
            description_score=0.85 if contract.get("description") else 0.5,
            machine_readable_score=1.0,
            parser_support_score=1.0 if parser_ready else 0.5,
            freshness_score=0.75 if generated_at else 0.5,
            execution_readiness_score=trust,
        ),
        preferred_distribution_id=distribution_id,
        distributions=[
            DistributionRecord(
                id=distribution_id,
                connector_type=connector_id,
                source_locator=dataset_id,
                profile_id=profile_id,
                parser_supported=parser_ready,
                machine_readable=True,
                default_filters={
                    str(key): [str(value_item) for value_item in value]
                    for key, value in (binding.get("filters_template") or {}).items()
                    if isinstance(value, list)
                },
                quality_score=trust,
            )
        ],
    )


def _default_production_data_root() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "production_data"
        / "canonical"
        / "local_data_20260501"
        / "policy_engine_data"
    )


def _read_catalog_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _bounded_float(value: object, *, default: float) -> float:
    try:
        number = float(value)
    except TypeError, ValueError:
        return default
    return max(0.0, min(1.0, number))


def _catalog_slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in normalized.split("-") if part) or "dataset"


class WVSIndicatorRegistryReadError(ValueError):
    """A present WVS registry does not satisfy the read API's schema contract."""


def read_wvs_indicator_registry(
    path: str | Path,
) -> Mapping[str, Mapping[str, object]] | None:
    """Read a present WVS indicator registry through the shared content snapshot.

    Missing input returns ``None``. Present malformed input raises the typed
    ``WVSIndicatorRegistryReadError`` exported by this facade. Batch readers and
    Fabric therefore share one parser and a cache keyed by current file bytes.
    """
    from polisyos.data_forge.domains.catalog.batch.material_inputs import (
        WVSIndicatorRegistryError as _WVSIndicatorRegistryError,
    )
    from polisyos.data_forge.domains.catalog.batch.material_inputs import (
        _material_file_snapshot,
        _wvs_indicator_registry_from_snapshot,
    )

    snapshot = _material_file_snapshot(Path(path))
    try:
        return _wvs_indicator_registry_from_snapshot(snapshot)
    except _WVSIndicatorRegistryError as exc:
        raise WVSIndicatorRegistryReadError(str(exc)) from exc


__all__ = sorted(
    [
        *_EXPORTS,
        "build_production_data_contract_catalog_graph",
        "build_slice0_fixture_catalog_graph",
        "read_wvs_indicator_registry",
        "WVSIndicatorRegistryReadError",
    ]
)


def _current_catalog_publish_receipt(
    database_path: Path, *, run_profile: str | None = None
) -> dict[str, object]:
    """Return local publish currentness without widening the public API."""
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_catalog_publish_receipt,
    )

    return current_catalog_publish_receipt(database_path, run_profile=run_profile)
