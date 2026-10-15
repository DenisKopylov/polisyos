from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

import pytest

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.core.artifacts.protocol import (
    resolve_manifest_by_profile as canonical_resolve_manifest_by_profile,
)
from polisyos.core.canon.canon_json import (
    CanonSpec as CanonicalCanonSpec,
)
from polisyos.core.canon.canon_json import (
    from_canonical_bytes as canonical_from_canonical_bytes,
)
from polisyos.core.canon.hashing import content_hash as canonical_content_hash
from polisyos.core.contracts import CatalogRunProfile as CoreCatalogRunProfile
from polisyos.core.contracts.control import (
    CatalogRunProfile as CanonicalCoreCatalogRunProfile,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGCredalSourceRows as CanonicalPreparedSKGCredalSourceRows,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGRead as CanonicalPreparedSKGRead,
)
from polisyos.data_forge.domains.academic.knowledge.skg_query import (
    PreparedSKGReadReceipt as CanonicalPreparedSKGReadReceipt,
)
from polisyos.data_forge.domains.catalog import (
    CatalogRunProfile,
    CatalogSourceRegistryEntry,
    CatalogSourceRegistrySpec,
)
from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError as CanonicalCatalogSelectionError,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    ActivatedAcquisitionObservationProjection as CanonicalActivatedAcquisitionObservationProjection,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay as CanonicalCatalogAcquisitionOverlay,
)
from polisyos.data_forge.read_api import (
    academic,
    available_surfaces,
    catalog,
    get_surface,
    surface_module,
    ukraine,
)
from polisyos.ir import analytics as ir_analytics
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel as CanonicalCausalGraphModel,
)
from polisyos.ir.analytics.data_views import DataViewRequest as CanonicalDataViewRequest


def test_catalog_type_checking_exports_match_lazy_mapping() -> None:
    catalog_module = import_module("polisyos.data_forge.read_api.catalog")
    tree = ast.parse(Path(catalog_module.__file__).read_text(encoding="utf-8"))
    type_only_exports = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for statement in node.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module is not None
        and statement.module.startswith("polisyos.data_forge.")
        for alias in statement.names
    }
    assert type_only_exports == set(catalog_module._EXPORTS)


def test_existing_facade_exports_preserve_canonical_object_identity() -> None:
    assert core_artifacts.resolve_manifest_by_profile is canonical_resolve_manifest_by_profile
    assert core_canon.CanonSpec is CanonicalCanonSpec
    assert core_canon.from_canonical_bytes is canonical_from_canonical_bytes
    assert core_canon.content_hash is canonical_content_hash
    assert CoreCatalogRunProfile is CanonicalCoreCatalogRunProfile
    assert ir_analytics.CausalGraphModel is CanonicalCausalGraphModel
    assert ir_analytics.DataViewRequest is CanonicalDataViewRequest
    assert catalog.CatalogRunProfile is CatalogRunProfile
    assert catalog.CatalogSelectionError is CanonicalCatalogSelectionError
    assert (
        catalog.ActivatedAcquisitionObservationProjection
        is CanonicalActivatedAcquisitionObservationProjection
    )
    assert catalog.CatalogAcquisitionOverlay is CanonicalCatalogAcquisitionOverlay


def test_read_api_surface_registry_resolves_public_modules() -> None:
    assert set(available_surfaces()) >= {"academic", "catalog", "legal", "ukraine"}

    catalog = get_surface("catalog")

    assert catalog.module == "polisyos.data_forge.read_api.catalog"
    assert surface_module("ukraine") == "polisyos.data_forge.read_api.ukraine"


def test_read_api_surface_registry_rejects_unknown_surface() -> None:
    with pytest.raises(KeyError, match="unknown Data Forge read_api surface"):
        get_surface("runtime")


def test_runtime_contract_exports_keep_canonical_object_identity() -> None:
    assert academic.PreparedSKGRead is CanonicalPreparedSKGRead
    assert academic.PreparedSKGReadReceipt is CanonicalPreparedSKGReadReceipt
    assert academic.PreparedSKGCredalSourceRows is CanonicalPreparedSKGCredalSourceRows
    assert catalog.CatalogRunProfile is CatalogRunProfile
    assert catalog.CatalogSourceRegistryEntry is CatalogSourceRegistryEntry
    assert catalog.CatalogSourceRegistrySpec is CatalogSourceRegistrySpec


def test_full35_routes_preserve_owner_identity_and_fail_closed_results() -> None:
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        require_selected_artifact_ref as owner_require_selected_artifact_ref,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        same_selected_artifact_ref as owner_same_selected_artifact_ref,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        selected_artifact_ref_for_input as owner_selected_artifact_ref_for_input,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        validate_claim_adjudication_input_batch as owner_validate_input_batch,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
        ConfidenceLayerVintage as OwnerConfidenceLayerVintage,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
        confidence_layer_vintage_for_snapshot_digest as owner_vintage_for_digest,
    )
    from polisyos.data_forge.domains.catalog.batch.config import (
        parse_profile_input_coverage as owner_parse_coverage,
    )
    from polisyos.data_forge.domains.catalog.batch.config import (
        profile_input_coverage_currentness as owner_coverage_currentness,
    )
    from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
        iso2_to_iso3 as owner_iso2_to_iso3,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION as OWNER_LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION,
    )
    from polisyos.data_forge.domains.catalog.knowledge.overlay import (
        LegacyAdmissionPassport as OwnerLegacyAdmissionPassport,
    )
    from polisyos.data_forge.domains.catalog.selection import (
        validate_catalog_run_profile as owner_validate_catalog_run_profile,
    )
    from polisyos.data_forge.domains.ukraine.builders.demography import (
        build_household_diagnostic_panel as owner_build_household_diagnostic_panel,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        ArtifactRecord as OwnerArtifactRecord,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        D5ReleaseHandoffRequest as OwnerD5ReleaseHandoffRequest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        HouseholdDiagnosticPanelBasis as OwnerHouseholdDiagnosticPanelBasis,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        NormalizedArtifactManifest as OwnerNormalizedArtifactManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        SourceSnapshotManifest as OwnerSourceSnapshotManifest,
    )
    from polisyos.data_forge.domains.ukraine.manifests import (
        directory_tree_entries as owner_directory_tree_entries,
    )
    from polisyos.data_forge.kernel.embeddings import (
        GENERATION_SELECTOR_FILENAME as OWNER_GENERATION_SELECTOR_FILENAME,
    )
    from polisyos.data_forge.kernel.embeddings import (
        embedding_generation_manifest as owner_embedding_generation_manifest,
    )
    from polisyos.fabric import (
        IngestionStoreBindingError as OwnerIngestionStoreBindingError,
    )
    from polisyos.fabric import (
        TenantSidecarScope as OwnerTenantSidecarScope,
    )
    from polisyos.fabric import (
        project_data_requirement_to_catalog_needs as owner_requirement_projection,
    )
    from polisyos.fabric.catalog.data_requirement_adapter import (
        project_data_requirement_to_catalog_needs as canonical_requirement_projection,
    )
    from polisyos.fabric.connectors import (
        FileTabularConnector as OwnerFileTabularConnector,
    )
    from polisyos.fabric.connectors import (
        resolve_execution_policy as canonical_resolve_execution_policy,
    )
    from polisyos.fabric.connectors.profiles.resolver import (
        resolve_execution_policy as owner_resolve_execution_policy,
    )
    from polisyos.fabric.connectors.sources.file_tabular import (
        FileTabularConnector as CanonicalFileTabularConnector,
    )
    from polisyos.fabric.ingestion.ingestion_providers import (
        IngestionStoreBindingError as CanonicalIngestionStoreBindingError,
    )
    from polisyos.fabric.storage.tenant_cas import (
        TenantSidecarScope as CanonicalTenantSidecarScope,
    )

    assert catalog.validate_catalog_run_profile is owner_validate_catalog_run_profile
    assert catalog.iso2_to_iso3 is owner_iso2_to_iso3
    assert OWNER_GENERATION_SELECTOR_FILENAME == catalog.GENERATION_SELECTOR_FILENAME
    assert catalog.embedding_generation_manifest is owner_embedding_generation_manifest
    assert catalog.parse_profile_input_coverage is owner_parse_coverage
    assert catalog.profile_input_coverage_currentness is owner_coverage_currentness
    assert (
        OWNER_LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION
        == catalog.LEGACY_ADMISSION_PASSPORT_SCHEMA_VERSION
    )
    assert catalog.LegacyAdmissionPassport is OwnerLegacyAdmissionPassport

    assert academic.ConfidenceLayerVintage is OwnerConfidenceLayerVintage
    assert academic.confidence_layer_vintage_for_snapshot_digest is owner_vintage_for_digest
    assert academic.require_selected_artifact_ref is owner_require_selected_artifact_ref
    assert academic.same_selected_artifact_ref is owner_same_selected_artifact_ref
    assert academic.selected_artifact_ref_for_input is owner_selected_artifact_ref_for_input
    assert academic.validate_claim_adjudication_input_batch is owner_validate_input_batch

    assert ukraine.ArtifactRecord is OwnerArtifactRecord
    assert ukraine.D5ReleaseHandoffRequest is OwnerD5ReleaseHandoffRequest
    assert ukraine.HouseholdDiagnosticPanelBasis is OwnerHouseholdDiagnosticPanelBasis
    assert ukraine.NormalizedArtifactManifest is OwnerNormalizedArtifactManifest
    assert ukraine.SourceSnapshotManifest is OwnerSourceSnapshotManifest
    assert ukraine.directory_tree_entries is owner_directory_tree_entries
    assert ukraine.build_household_diagnostic_panel is owner_build_household_diagnostic_panel

    assert owner_requirement_projection is canonical_requirement_projection
    assert OwnerIngestionStoreBindingError is CanonicalIngestionStoreBindingError
    assert OwnerTenantSidecarScope is CanonicalTenantSidecarScope
    assert OwnerFileTabularConnector is CanonicalFileTabularConnector
    assert canonical_resolve_execution_policy is owner_resolve_execution_policy

    assert catalog.parse_profile_input_coverage(None, missing=True) == (
        "legacy_unknown",
        None,
    )
    assert catalog.profile_input_coverage_currentness(
        {
            "schema_version": "policyos.catalog.profile_input_coverage.v1",
            "profiles": {"fixture_profile": "excluded_present"},
        }
    ) == ("not_established", {"fixture_profile": "excluded_present"})
    assert catalog.confidence_layer_vintage_for_snapshot_digest("0" * 64) is None
    with pytest.raises(ValueError, match="malformed source digest"):
        catalog.confidence_layer_vintage_for_snapshot_digest("not-a-digest")
    assert not hasattr(catalog, "_LegacyAdmissionPassport")
    assert not hasattr(catalog, "_LEGACY_PASSPORT_SCHEMA_VERSION")
