"""Runtime-safe read API for academic Data Forge artifacts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._lazy import lazy_dir, load_lazy_export

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_ASSET_GROUP as ACADEMIC_ASSET_GROUP,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_ASSET_SCHEMA_CONTRACTS as ACADEMIC_ASSET_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_BATCH_SCHEMA_CONTRACTS as ACADEMIC_BATCH_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_BATCH_STAGE_DEPENDENCIES as ACADEMIC_BATCH_STAGE_DEPENDENCIES,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_BATCH_STAGE_ID_PATTERN as ACADEMIC_BATCH_STAGE_ID_PATTERN,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_BATCH_STAGE_ORDER as ACADEMIC_BATCH_STAGE_ORDER,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_CLAIMS_KEY as ACADEMIC_CLAIMS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_EXTRACTED_CLAIMS_KEY as ACADEMIC_EXTRACTED_CLAIMS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_FULLTEXT_KEY as ACADEMIC_FULLTEXT_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_NORMALIZED_WORKS_KEY as ACADEMIC_NORMALIZED_WORKS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_PUBLISHED_CLAIMS_KEY as ACADEMIC_PUBLISHED_CLAIMS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_RAW_WORKS_KEY as ACADEMIC_RAW_WORKS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_READINESS_KEY as ACADEMIC_READINESS_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_SCHEMA_CONTRACTS as ACADEMIC_SCHEMA_CONTRACTS,
    )
    from polisyos.data_forge.domains.academic import (
        ACADEMIC_SKG_KEY as ACADEMIC_SKG_KEY,
    )
    from polisyos.data_forge.domains.academic import (
        CORE_ACADEMIC_BATCH_STAGES as CORE_ACADEMIC_BATCH_STAGES,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicBatchRunProfile as AcademicBatchRunProfile,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicBatchStagePlan as AcademicBatchStagePlan,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicBatchStageSpec as AcademicBatchStageSpec,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicBenchmarkReport as AcademicBenchmarkReport,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicQCReport as AcademicQCReport,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicReadinessPackage as AcademicReadinessPackage,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicReadinessSummary as AcademicReadinessSummary,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicShadowArtifact as AcademicShadowArtifact,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicShadowBundle as AcademicShadowBundle,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicShadowDiff as AcademicShadowDiff,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicSKGSummary as AcademicSKGSummary,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicSKGTableSummary as AcademicSKGTableSummary,
    )
    from polisyos.data_forge.domains.academic import (
        AcademicStageManifest as AcademicStageManifest,
    )
    from polisyos.data_forge.domains.academic import (
        build_academic_batch_asset_group as build_academic_batch_asset_group,
    )
    from polisyos.data_forge.domains.academic import (
        build_academic_schema_registry as build_academic_schema_registry,
    )
    from polisyos.data_forge.domains.academic import (
        compare_academic_shadow_bundles as compare_academic_shadow_bundles,
    )
    from polisyos.data_forge.domains.academic import (
        load_academic_benchmark_report as load_academic_benchmark_report,
    )
    from polisyos.data_forge.domains.academic import (
        load_academic_qc_report as load_academic_qc_report,
    )
    from polisyos.data_forge.domains.academic import (
        load_academic_readiness_package as load_academic_readiness_package,
    )
    from polisyos.data_forge.domains.academic import (
        load_academic_shadow_bundle as load_academic_shadow_bundle,
    )
    from polisyos.data_forge.domains.academic import (
        load_academic_skg_summary as load_academic_skg_summary,
    )
    from polisyos.data_forge.domains.academic import (
        plan_academic_batch_stages as plan_academic_batch_stages,
    )
    from polisyos.data_forge.domains.academic import (
        select_academic_batch_stages as select_academic_batch_stages,
    )
    from polisyos.data_forge.domains.academic.batch._resolve_extract_providers import (
        GonkaMultiKeyPool as GonkaMultiKeyPool,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        STRONG_DESIGN_FAMILIES as STRONG_DESIGN_FAMILIES,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        ClaimAdjudicationRules as ClaimAdjudicationRules,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        ClaimConsensusRule as ClaimConsensusRule,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        aggregate_claim_rows as aggregate_claim_rows,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        claim_guardrails as claim_guardrails,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        claim_metrics as claim_metrics,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        claim_policy_publishable as claim_policy_publishable,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        claim_promotion_policy as claim_promotion_policy,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_policy import (
        metric_is_improved as metric_is_improved,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        ClaimAdjudicationVerifier as ClaimAdjudicationVerifier,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        read_claim_promotion_predecessor as read_claim_promotion_predecessor,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        require_selected_artifact_ref as require_selected_artifact_ref,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        same_selected_artifact_ref as same_selected_artifact_ref,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        selected_artifact_ref_for_input as selected_artifact_ref_for_input,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        materialize_claim_adjudication_result as materialize_claim_adjudication_result,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        produce_claim_adjudication_input as produce_claim_adjudication_input,
    )
    from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
        validate_claim_adjudication_input_batch as validate_claim_adjudication_input_batch,
    )
    from polisyos.data_forge.domains.academic.batch.config import (
        AcademicBatchConfig as AcademicBatchConfig,
    )
    from polisyos.data_forge.domains.academic.batch.edge_synthesize import (
        run_edge_synthesize as run_edge_synthesize,
    )
    from polisyos.data_forge.domains.academic.knowledge.canonical_resolver import (
        CanonicalVariableResolver as CanonicalVariableResolver,
    )
    from polisyos.data_forge.domains.academic.knowledge.canonical_seed import (
        CANONICAL_VARIABLES as CANONICAL_VARIABLES,
    )
    from polisyos.data_forge.domains.academic.knowledge.parameter_selector import (
        ParameterSelector as ParameterSelector,
    )
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        RUNTIME_CANONICAL_REGISTRY as RUNTIME_CANONICAL_REGISTRY,
    )
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        RUNTIME_CANONICAL_REGISTRY_VERSION as RUNTIME_CANONICAL_REGISTRY_VERSION,
    )
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        runtime_approved_synonyms as runtime_approved_synonyms,
    )
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        runtime_canonical_entries as runtime_canonical_entries,
    )
    from polisyos.data_forge.domains.academic.knowledge.runtime_canonical_registry import (
        runtime_canonical_names as runtime_canonical_names,
    )
    from polisyos.data_forge.domains.academic.knowledge.search import (
        ScholarKnowledgeGraph as ScholarKnowledgeGraph,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_identity_bridge import (
        SourceIdentityBundle as SourceIdentityBundle,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_identity_bridge import (
        SourceIdentitySelection as SourceIdentitySelection,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_identity_bridge import (
        SourceSnapshot as SourceSnapshot,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_identity_bridge import (
        produce_source_identity_bundle as produce_source_identity_bundle,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_identity_bridge import (
        replay_source_identity_bundle as replay_source_identity_bundle,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        ParameterCandidate as ParameterCandidate,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        PreparedSKGCredalSourceRows as PreparedSKGCredalSourceRows,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        PreparedSKGRead as PreparedSKGRead,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        PreparedSKGReadReceipt as PreparedSKGReadReceipt,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        SKGQuery as SKGQuery,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshot as RetainedSKGSnapshot,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshotChunk as RetainedSKGSnapshotChunk,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshotError as RetainedSKGSnapshotError,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshotRecord as RetainedSKGSnapshotRecord,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshotV10 as RetainedSKGSnapshotV10,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSnapshotV11 as RetainedSKGSnapshotV11,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        RetainedSKGSourceBinding as RetainedSKGSourceBinding,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        load_retained_skg_snapshot as load_retained_skg_snapshot,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_snapshot import (
        retained_skg_source_binding as retained_skg_source_binding,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_source_population import (
        SourceReferencePopulation as SourceReferencePopulation,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_source_population import (
        read_source_reference_population as read_source_reference_population,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
        ConfidenceLayerVintage as ConfidenceLayerVintage,
    )
    from polisyos.data_forge.domains.academic.knowledge.skg_versioning import (
        confidence_layer_vintage_for_snapshot_digest as confidence_layer_vintage_for_snapshot_digest,  # noqa: E501
    )
    from polisyos.data_forge.domains.academic.knowledge.store import (
        audit_academic_claim_lineage as audit_academic_claim_lineage,
    )
    from polisyos.data_forge.domains.academic.knowledge.store import (
        iter_causal_claim_results_v2 as iter_causal_claim_results_v2,
    )
    from polisyos.data_forge.domains.academic.knowledge.store import (
        load_causal_claim_results_v2 as load_causal_claim_results_v2,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        CausalClaimResult as CausalClaimResult,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        CausalClaimResultV1 as CausalClaimResultV1,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        CausalClaimResultV2 as CausalClaimResultV2,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimLineageAuditPage as ClaimLineageAuditPage,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimLineageAuditRecord as ClaimLineageAuditRecord,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimLineageCursorError as ClaimLineageCursorError,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimTableSchemaError as ClaimTableSchemaError,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimVocabularyLimitation as ClaimVocabularyLimitation,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimVocabularyProjectionBinding as ClaimVocabularyProjectionBinding,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ClaimVocabularySourceRowBinding as ClaimVocabularySourceRowBinding,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate as EstimateCandidate,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        ParameterPrior as ParameterPrior,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        WorkRecord as WorkRecord,
    )
    from polisyos.data_forge.domains.academic.knowledge.types import (
        WorkSearchResult as WorkSearchResult,
    )
    from polisyos.data_forge.domains.academic.openalex.client import (
        OpenAlexClient as OpenAlexClient,
    )
    from polisyos.data_forge.domains.academic.openalex.client import (
        OpenAlexRequest as OpenAlexRequest,
    )

_ACADEMIC_DOMAIN = "polisyos.data_forge.domains.academic"
_ACADEMIC_KNOWLEDGE = f"{_ACADEMIC_DOMAIN}.knowledge"
_CLAIM_ADJUDICATOR = f"{_ACADEMIC_DOMAIN}.batch.claim_adjudicator"
_RUNTIME_CANONICAL_REGISTRY = f"{_ACADEMIC_KNOWLEDGE}.runtime_canonical_registry"
_EXPORTS = {
    "ACADEMIC_ASSET_GROUP": _ACADEMIC_DOMAIN,
    "ACADEMIC_ASSET_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_DEPENDENCIES": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_ID_PATTERN": _ACADEMIC_DOMAIN,
    "ACADEMIC_BATCH_STAGE_ORDER": _ACADEMIC_DOMAIN,
    "ACADEMIC_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_EXTRACTED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_FULLTEXT_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_NORMALIZED_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_PUBLISHED_CLAIMS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_RAW_WORKS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_READINESS_KEY": _ACADEMIC_DOMAIN,
    "ACADEMIC_SCHEMA_CONTRACTS": _ACADEMIC_DOMAIN,
    "ACADEMIC_SKG_KEY": _ACADEMIC_DOMAIN,
    "CORE_ACADEMIC_BATCH_STAGES": _ACADEMIC_DOMAIN,
    "AcademicBatchRunProfile": _ACADEMIC_DOMAIN,
    "AcademicBatchStagePlan": _ACADEMIC_DOMAIN,
    "AcademicBatchStageSpec": _ACADEMIC_DOMAIN,
    "AcademicBenchmarkReport": _ACADEMIC_DOMAIN,
    "AcademicQCReport": _ACADEMIC_DOMAIN,
    "AcademicReadinessSummary": _ACADEMIC_DOMAIN,
    "AcademicReadinessPackage": _ACADEMIC_DOMAIN,
    "AcademicSKGSummary": _ACADEMIC_DOMAIN,
    "AcademicSKGTableSummary": _ACADEMIC_DOMAIN,
    "AcademicShadowArtifact": _ACADEMIC_DOMAIN,
    "AcademicShadowBundle": _ACADEMIC_DOMAIN,
    "AcademicShadowDiff": _ACADEMIC_DOMAIN,
    "AcademicStageManifest": _ACADEMIC_DOMAIN,
    "AcademicBatchConfig": "polisyos.data_forge.domains.academic.batch.config",
    "CANONICAL_VARIABLES": f"{_ACADEMIC_KNOWLEDGE}.canonical_seed",
    "CanonicalVariableResolver": f"{_ACADEMIC_KNOWLEDGE}.canonical_resolver",
    "CausalClaimResult": f"{_ACADEMIC_KNOWLEDGE}.types",
    "CausalClaimResultV1": f"{_ACADEMIC_KNOWLEDGE}.types",
    "CausalClaimResultV2": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimLineageAuditPage": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimLineageAuditRecord": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimLineageCursorError": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimTableSchemaError": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimVocabularyLimitation": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimVocabularyProjectionBinding": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ClaimVocabularySourceRowBinding": f"{_ACADEMIC_KNOWLEDGE}.types",
    "EstimateCandidate": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ParameterCandidate": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "PreparedSKGRead": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "PreparedSKGReadReceipt": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "PreparedSKGCredalSourceRows": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "RetainedSKGSnapshot": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSnapshotChunk": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSnapshotError": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSnapshotRecord": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSnapshotV10": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSnapshotV11": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "RetainedSKGSourceBinding": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "load_retained_skg_snapshot": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "retained_skg_source_binding": f"{_ACADEMIC_KNOWLEDGE}.skg_snapshot",
    "ParameterPrior": f"{_ACADEMIC_KNOWLEDGE}.types",
    "ParameterSelector": f"{_ACADEMIC_KNOWLEDGE}.parameter_selector",
    "RUNTIME_CANONICAL_REGISTRY": _RUNTIME_CANONICAL_REGISTRY,
    "RUNTIME_CANONICAL_REGISTRY_VERSION": _RUNTIME_CANONICAL_REGISTRY,
    "SKGQuery": f"{_ACADEMIC_KNOWLEDGE}.skg_query",
    "ScholarKnowledgeGraph": f"{_ACADEMIC_KNOWLEDGE}.search",
    "WorkRecord": f"{_ACADEMIC_KNOWLEDGE}.types",
    "WorkSearchResult": f"{_ACADEMIC_KNOWLEDGE}.types",
    "GonkaMultiKeyPool": "polisyos.data_forge.domains.academic.batch._resolve_extract_providers",
    "OpenAlexClient": "polisyos.data_forge.domains.academic.openalex.client",
    "OpenAlexRequest": "polisyos.data_forge.domains.academic.openalex.client",
    "build_academic_batch_asset_group": _ACADEMIC_DOMAIN,
    "build_academic_schema_registry": _ACADEMIC_DOMAIN,
    "compare_academic_shadow_bundles": _ACADEMIC_DOMAIN,
    "load_academic_benchmark_report": _ACADEMIC_DOMAIN,
    "load_academic_qc_report": _ACADEMIC_DOMAIN,
    "load_academic_readiness_package": _ACADEMIC_DOMAIN,
    "load_academic_skg_summary": _ACADEMIC_DOMAIN,
    "load_causal_claim_results_v2": f"{_ACADEMIC_KNOWLEDGE}.store",
    "iter_causal_claim_results_v2": f"{_ACADEMIC_KNOWLEDGE}.store",
    "audit_academic_claim_lineage": f"{_ACADEMIC_KNOWLEDGE}.store",
    "load_academic_shadow_bundle": _ACADEMIC_DOMAIN,
    "plan_academic_batch_stages": _ACADEMIC_DOMAIN,
    "materialize_claim_adjudication_result": _CLAIM_ADJUDICATOR,
    "produce_claim_adjudication_input": _CLAIM_ADJUDICATOR,
    "validate_claim_adjudication_input_batch": _CLAIM_ADJUDICATOR,
    "require_selected_artifact_ref": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_verifier",
    "same_selected_artifact_ref": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_verifier",
    "selected_artifact_ref_for_input": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_verifier",
    "ConfidenceLayerVintage": f"{_ACADEMIC_KNOWLEDGE}.skg_versioning",
    "confidence_layer_vintage_for_snapshot_digest": f"{_ACADEMIC_KNOWLEDGE}.skg_versioning",
    "run_edge_synthesize": "polisyos.data_forge.domains.academic.batch.edge_synthesize",
    "runtime_approved_synonyms": _RUNTIME_CANONICAL_REGISTRY,
    "runtime_canonical_entries": _RUNTIME_CANONICAL_REGISTRY,
    "runtime_canonical_names": _RUNTIME_CANONICAL_REGISTRY,
    "select_academic_batch_stages": _ACADEMIC_DOMAIN,
    "ClaimAdjudicationRules": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "ClaimConsensusRule": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "STRONG_DESIGN_FAMILIES": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "aggregate_claim_rows": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "claim_metrics": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "claim_guardrails": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "claim_promotion_policy": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "metric_is_improved": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "claim_policy_publishable": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_policy",
    "ClaimAdjudicationVerifier": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_verifier",
    "read_claim_promotion_predecessor": f"{_ACADEMIC_DOMAIN}.batch.claim_adjudication_verifier",
    "SourceSnapshot": f"{_ACADEMIC_KNOWLEDGE}.skg_identity_bridge",
    "SourceIdentitySelection": f"{_ACADEMIC_KNOWLEDGE}.skg_identity_bridge",
    "SourceIdentityBundle": f"{_ACADEMIC_KNOWLEDGE}.skg_identity_bridge",
    "produce_source_identity_bundle": f"{_ACADEMIC_KNOWLEDGE}.skg_identity_bridge",
    "replay_source_identity_bundle": f"{_ACADEMIC_KNOWLEDGE}.skg_identity_bridge",
    "SourceReferencePopulation": f"{_ACADEMIC_KNOWLEDGE}.skg_source_population",
    "read_source_reference_population": f"{_ACADEMIC_KNOWLEDGE}.skg_source_population",
}


def __getattr__(name: str) -> object:
    """Lazily resolve academic exports without importing domain internals at module import."""
    return load_lazy_export(name, exports=_EXPORTS, module_name=__name__, namespace=globals())


def __dir__() -> list[str]:
    """Return public academic read_api names without resolving exports."""
    return lazy_dir(globals(), _EXPORTS)


__all__ = sorted(_EXPORTS)
