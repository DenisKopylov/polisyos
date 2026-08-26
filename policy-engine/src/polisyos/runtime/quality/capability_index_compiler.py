"""Compile production-data layers into a Policy Evidence Capability Index."""

# ruff: noqa: E501, S608, ANN401

from __future__ import annotations

import hashlib
import json
import shutil
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from polisyos.runtime.quality.capability_index import (
    CAPABILITY_INDEX_SCHEMA_VERSION,
    AcquisitionStrategy,
    AuthorityEnvelope,
    CapabilityConflictRecord,
    CapabilityIndex,
    CapabilityIndexDiscoveryRow,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FailureModeNode,
    FreshnessEnvelope,
    LegalNormOwnerTruth,
    QualityScore,
    RightsEnvelope,
    capability_is_production_admissible,
)
from polisyos.runtime.quality.capability_white_space import (
    build_capability_white_space_report as build_grouped_capability_white_space_report,
)

CAPABILITY_INDEX_COMPILER_VERSION = "policyos.capability_index_compiler.v1"
CAPABILITY_INDEX_RELEASE_REF = "policyos-capability-index-v1"
CAPABILITY_INDEX_DUCKDB = "capability_index_v1.duckdb"
CAPABILITY_INDEX_MANIFEST = "capability_index_v1.manifest.json"
CAPABILITY_INDEX_SHA256 = "capability_index_v1.sha256"
CAPABILITY_INDEX_SUMMARY = "capability_index_v1.summary.json"
CAPABILITY_INDEX_DCAT = "capability_index_v1.dcat.jsonld"
CAPABILITY_INDEX_PROV = "capability_index_v1.prov.ttl"
CAPABILITY_WHITE_SPACE_REPORT = "capability_white_space_report_v1.json"
CAPABILITY_CONFLICT_REPORT = "capability_conflict_report_v1.json"

PHASE1_ARTIFACT_PROFILE_SCHEMA_VERSION = "policyos.capability_index.phase1_artifact_profile.v1"
CAPABILITY_INDEX_OUTPUT_FILENAMES = (
    CAPABILITY_INDEX_DUCKDB,
    CAPABILITY_INDEX_MANIFEST,
    CAPABILITY_INDEX_SHA256,
    CAPABILITY_INDEX_SUMMARY,
    CAPABILITY_INDEX_DCAT,
    CAPABILITY_INDEX_PROV,
    CAPABILITY_WHITE_SPACE_REPORT,
    CAPABILITY_CONFLICT_REPORT,
)
CAPABILITY_INDEX_SIGNED_SIZE_FILENAMES = (
    CAPABILITY_CONFLICT_REPORT,
    CAPABILITY_INDEX_DCAT,
    CAPABILITY_INDEX_DUCKDB,
    CAPABILITY_INDEX_PROV,
    CAPABILITY_INDEX_SHA256,
    CAPABILITY_WHITE_SPACE_REPORT,
)
FULL_MODE_CAPABILITY_FLOORS: dict[str, int] = {
    "fabric_data": 1,
    "lex_norm": 1,
    "scholar_claim": 1,
    "foundry_method_contract": 1,
    "compatibility_only": 1,
}
PERFORMANCE_BUDGET_SECONDS: dict[str, int] = {
    "fixture": 30,
    "full": 600,
    "incremental": 120,
}
INPUT_GROUP_TO_SOURCE_LAYER: dict[str, str] = {
    "l1_dataset_catalog": "L1",
    "l2_scholar_kg": "L2",
    "l3_lex_kg": "L3",
    "l4_ukraine_panels": "L4",
    "l5_calibration_registries": "L5",
    "l6_foundry_method_contracts": "L6",
    "l7_curated_contracts": "L7",
}
SOURCE_LAYER_TO_INPUT_GROUP = {value: key for key, value in INPUT_GROUP_TO_SOURCE_LAYER.items()}
INPUT_GROUPS = tuple(INPUT_GROUP_TO_SOURCE_LAYER)
INTERDEPENDENT_PANEL_GROUPS = frozenset(
    {
        "l4_ukraine_panels",
        "l5_calibration_registries",
        "l6_foundry_method_contracts",
    }
)
L5_DERIVED_PARQUET_NAMES = frozenset(
    {
        "corrected_firm_panels.parquet",
        "survival_hazard_estimates.parquet",
    }
)


@dataclass(frozen=True)
class CapabilityIndexCompilerConfig:
    """Compiler configuration for fixture, full, and incremental builds."""

    production_data_root: Path
    output_dir: Path
    mode: Literal["fixture", "full", "incremental"] = "full"
    previous_manifest_path: Path | None = None
    generated_at: str | None = None
    max_l1_capabilities: int = 1_000
    max_scholar_capabilities: int = 1_000
    max_lex_capabilities: int = 1_000
    enforce_performance_budget: bool = True
    inject_same_construct_conflict: bool = False


@dataclass(frozen=True)
class CapabilityIndexBuildResult:
    """Paths and summary metadata emitted by the compiler."""

    output_dir: Path
    primary_duckdb_path: Path
    manifest_path: Path
    sha256_path: Path
    summary_path: Path
    dcat_path: Path
    prov_path: Path
    white_space_report_path: Path
    conflict_report_path: Path
    summary: Mapping[str, Any]
    manifest: Mapping[str, Any]
    capability_index: CapabilityIndex | None = None


@dataclass(frozen=True)
class ParquetProfile:
    """Metadata-only Parquet profile used to avoid full panel scans."""

    family: str
    path: Path
    relative_path: str
    source_layer: str
    row_count: int
    row_group_count: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class CalibrationContext:
    """Normalized calibration registry values by source family."""

    source_assets: tuple[CapabilitySourceAsset, ...]
    coverage_rules: Mapping[str, float]
    proxy_mappings: Mapping[str, Any]
    identification_modes: Mapping[str, str]
    schema_regime: str | None
    governance_passes: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class FoundryRouteContext:
    """Foundry route lookup derived from observation_to_contract_manifest."""

    source_assets: tuple[CapabilitySourceAsset, ...]
    targets_by_family: Mapping[str, tuple[str, ...]]


def compile_capability_index(
    config: CapabilityIndexCompilerConfig,
) -> CapabilityIndexBuildResult:
    """Compile a release-time capability index and write all Phase 1 outputs.

    Args:
        config: Compiler configuration including production-data root and mode.

    Returns:
        Build result with paths and emitted summary payloads.
    """

    started = time.perf_counter()
    production_data_root = config.production_data_root.resolve()
    output_dir = config.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = config.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    release_snapshot_at = _release_snapshot_at(generated_at)
    input_fingerprints = discover_input_fingerprints(production_data_root)
    previous_manifest = (
        _load_json(config.previous_manifest_path) if config.previous_manifest_path else None
    )
    incremental = _incremental_state(previous_manifest, input_fingerprints)

    if (
        config.mode == "incremental"
        and previous_manifest
        and not incremental["changed_input_labels"]
    ):
        return _copy_previous_incremental_outputs(
            config=config,
            output_dir=output_dir,
            generated_at=generated_at,
            input_fingerprints=input_fingerprints,
            previous_manifest=previous_manifest,
            started=started,
        )

    rebuilt_labels = tuple(INPUT_GROUPS)
    if config.mode == "incremental" and previous_manifest:
        rebuilt_labels = _incremental_rebuild_labels(incremental["changed_input_labels"])
        previous_capabilities = _load_previous_capabilities(config.previous_manifest_path)
        rebuilt_capabilities = _compile_capabilities_for_input_labels(
            config,
            production_data_root,
            rebuilt_labels,
            release_snapshot_at=release_snapshot_at,
        )
        capabilities = _merge_incremental_capabilities(
            previous_capabilities=previous_capabilities,
            rebuilt_capabilities=rebuilt_capabilities,
            rebuilt_input_labels=rebuilt_labels,
        )
    else:
        capabilities = list(
            _compile_capabilities_for_input_labels(
                config,
                production_data_root,
                INPUT_GROUPS,
                release_snapshot_at=release_snapshot_at,
            )
        )

    incremental = {
        **incremental,
        "rebuilt_input_labels": list(rebuilt_labels),
        "rebuild_strategy": "changed_input_dependency_closure"
        if config.mode == "incremental"
        else "full_input_scan",
    }

    if config.inject_same_construct_conflict:
        capabilities.append(
            _build_fixture_conflicting_capability(
                next(
                    (
                        capability
                        for capability in capabilities
                        if not capability.compatibility_only
                    ),
                    None,
                )
            )
        )

    capabilities = _dedupe_capabilities(capabilities)
    for capability in capabilities:
        validate_capability_authority(capability)

    conflicts = detect_same_construct_conflicts(capabilities)
    white_space = build_white_space_nodes(capabilities)
    acquisition_strategies = build_acquisition_strategies(white_space)
    capability_index = CapabilityIndex(
        compiler_version=CAPABILITY_INDEX_COMPILER_VERSION,
        release_ref=CAPABILITY_INDEX_RELEASE_REF,
        mode=config.mode,
        capabilities=tuple(sorted(capabilities, key=lambda capability: capability.capability_id)),
        failure_modes=tuple(white_space),
        acquisition_strategies=tuple(acquisition_strategies),
        conflicts=tuple(conflicts),
        white_space=tuple(white_space),
        generated_at=generated_at,
        metadata={
            "adr_ref": "ADR-0174",
            "pattern_refs": ["P01", "P02", "P03", "P05", "P10", "P15"],
            "incremental": incremental,
        },
    )

    primary_duckdb_path = output_dir / CAPABILITY_INDEX_DUCKDB
    table_row_counts = write_capability_index_duckdb(capability_index, primary_duckdb_path)
    logical_digest = compute_logical_duckdb_digest(primary_duckdb_path)
    sha256_path = output_dir / CAPABILITY_INDEX_SHA256
    sha256_path.write_text(
        f"{logical_digest}  {CAPABILITY_INDEX_DUCKDB}.logical\n",
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - started
    performance_budget = _performance_budget(config.mode, elapsed)
    if config.enforce_performance_budget and performance_budget["status"] != "pass":
        raise RuntimeError(
            "capability index build exceeded "
            f"{performance_budget['budget_seconds']}s budget for {config.mode}"
        )

    conflict_report = build_conflict_report(conflicts)
    white_space_report = build_white_space_report(white_space, acquisition_strategies)
    dcat_projection = build_dcat_projection(capability_index)
    prov_projection = build_prov_projection(capability_index)
    _write_json(output_dir / CAPABILITY_CONFLICT_REPORT, conflict_report)
    _write_json(output_dir / CAPABILITY_WHITE_SPACE_REPORT, white_space_report)
    _write_json(output_dir / CAPABILITY_INDEX_DCAT, dcat_projection)
    (output_dir / CAPABILITY_INDEX_PROV).write_text(prov_projection, encoding="utf-8")

    artifact_size_profile = _artifact_size_profile(
        output_dir,
        filenames=CAPABILITY_INDEX_SIGNED_SIZE_FILENAMES,
    )
    capability_floors = _capability_floor_report(capability_index.capabilities)
    summary = build_summary(
        capability_index=capability_index,
        table_row_counts=table_row_counts,
        artifact_size_profile=artifact_size_profile,
        performance_budget=performance_budget,
        capability_floors=capability_floors,
        incremental=incremental,
    )
    manifest = build_manifest(
        config=config,
        generated_at=generated_at,
        input_fingerprints=input_fingerprints,
        logical_digest=logical_digest,
        table_row_counts=table_row_counts,
        artifact_size_profile=artifact_size_profile,
        incremental=incremental,
    )

    _write_json(output_dir / CAPABILITY_INDEX_SUMMARY, summary)
    _write_json(output_dir / CAPABILITY_INDEX_MANIFEST, manifest)

    return CapabilityIndexBuildResult(
        output_dir=output_dir,
        primary_duckdb_path=primary_duckdb_path,
        manifest_path=output_dir / CAPABILITY_INDEX_MANIFEST,
        sha256_path=sha256_path,
        summary_path=output_dir / CAPABILITY_INDEX_SUMMARY,
        dcat_path=output_dir / CAPABILITY_INDEX_DCAT,
        prov_path=output_dir / CAPABILITY_INDEX_PROV,
        white_space_report_path=output_dir / CAPABILITY_WHITE_SPACE_REPORT,
        conflict_report_path=output_dir / CAPABILITY_CONFLICT_REPORT,
        summary=summary,
        manifest=manifest,
        capability_index=capability_index,
    )


def build_capability_discovery_snapshot(
    capability_index: CapabilityIndex,
) -> tuple[CapabilityIndexDiscoveryRow, ...]:
    """Project release-index rows for the kinds the index genuinely owns.

    L4 world-model rows are intentionally excluded. Scientist agent/tool
    capability discovery has a different owner and must enter through its
    registry provider.
    """

    observed_at = _release_snapshot_at(capability_index.generated_at)
    rows: list[CapabilityIndexDiscoveryRow] = []
    for capability in capability_index.capabilities:
        resource_kind = _discovery_resource_kind(capability)
        if resource_kind is None:
            continue
        owner_truth = (
            _legal_norm_owner_truth(capability, release_snapshot_at=observed_at)
            if resource_kind == "legal_norm"
            else None
        )
        if resource_kind == "legal_norm" and owner_truth is None:
            continue
        payload = capability.model_dump(mode="json", by_alias=True)
        digest = "sha256:" + _sha256_json(payload)
        source_refs = tuple(asset.ref for asset in capability.source_assets)
        freshness_ref = (
            capability.freshness_envelope.source_release_ref or capability_index.release_ref
        )
        rows.append(
            CapabilityIndexDiscoveryRow(
                capability_ref=capability.capability_id,
                content_digest=digest,
                resource_kind=resource_kind,
                construct_refs=tuple(
                    dict.fromkeys(
                        (
                            f"construct:{capability.construct_id.removeprefix('construct:')}",
                            *capability.concept_spine_refs,
                        )
                    )
                ),
                label=capability.construct_id.replace("_", " "),
                description=(
                    f"{capability.evidence_mode} capability from "
                    f"{', '.join(asset.source_layer for asset in capability.source_assets)}"
                ),
                producer_ref=capability_index.release_ref,
                snapshot_ref=(
                    f"{capability_index.release_ref}@{capability_index.compiler_version}"
                ),
                freshness_ref=freshness_ref,
                provenance_refs=(
                    source_refs or capability.lineage_refs or (capability_index.release_ref,)
                ),
                owner_truth=owner_truth,
                may_not_use_for=tuple(
                    dict.fromkeys(
                        (
                            *capability.may_not_use_for,
                            *capability.authority_envelope.may_not_use_for,
                            "execution_authority",
                            "publication_authority",
                        )
                    )
                ),
                time={
                    "observed_at": observed_at,
                    "valid_from": observed_at,
                    "valid_until": None,
                    "freshness": _discovery_freshness(capability),
                },
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.resource_kind, row.capability_ref)))


def _discovery_resource_kind(capability: EvidenceCapability) -> str | None:
    modalities = set(capability.modality)
    layers = {asset.source_layer for asset in capability.source_assets}
    if "foundry_method_contract" in modalities:
        return "method"
    if "fabric_data" in modalities and "L1" in layers:
        return "dataset"
    if "lex_norm" in modalities and "L3" in layers:
        return "legal_norm"
    return None


def _discovery_freshness(capability: EvidenceCapability) -> str:
    freshness = capability.freshness_envelope.freshness_class.casefold()
    if "stale" in freshness or capability.capability_lifecycle.state in {
        "deprecated",
        "withdrawn",
    }:
        return "stale"
    if freshness:
        return "current"
    return "unknown"


def _legal_norm_owner_truth(
    capability: EvidenceCapability,
    *,
    release_snapshot_at: datetime,
) -> LegalNormOwnerTruth | None:
    payload = capability.metadata.get("legal_norm_owner_truth")
    if not isinstance(payload, Mapping):
        return None
    effective_from = _iso_date(payload.get("effective_from"))
    effective_to_raw = payload.get("effective_to")
    effective_to = _iso_date(effective_to_raw) if effective_to_raw else None
    if effective_from is None or (effective_to_raw and effective_to is None):
        return None
    try:
        truth = LegalNormOwnerTruth.model_validate(
            {
                **payload,
                "effective_from": effective_from,
                "effective_to": effective_to,
                "temporal_snapshot_at": release_snapshot_at,
                "provenance_refs": tuple(payload.get("provenance_refs") or ()),
            }
        )
        return truth
    except ValueError:
        return None


def validate_capability_authority(capability: EvidenceCapability) -> None:
    """Validate authority boundaries that must never be laundered."""

    if (
        capability.evidence_mode in {"simulation_only", "candidate_unverified"}
        or set(capability.modality) & {"simulation_state", "llm_candidate", "llm_critic_consensus"}
    ) and capability_is_production_admissible(capability):
        raise ValueError(
            f"{capability.evidence_mode} capability {capability.capability_id} "
            "cannot claim production authority"
        )
    if capability.compatibility_only and capability_is_production_admissible(capability):
        raise ValueError(
            f"compatibility_only capability {capability.capability_id} cannot claim "
            "production authority"
        )


def _compile_capabilities_for_input_labels(
    config: CapabilityIndexCompilerConfig,
    production_data_root: Path,
    input_labels: Sequence[str],
    *,
    release_snapshot_at: datetime,
) -> tuple[EvidenceCapability, ...]:
    labels = set(input_labels)
    capabilities: list[EvidenceCapability] = []
    needs_panel_context = bool(labels & INTERDEPENDENT_PANEL_GROUPS)
    calibration_context = (
        load_calibration_registries(production_data_root)
        if needs_panel_context
        else _empty_calibration_context()
    )
    foundry_context = (
        load_foundry_method_contracts(production_data_root)
        if needs_panel_context
        else FoundryRouteContext(source_assets=(), targets_by_family={})
    )
    if "l1_dataset_catalog" in labels:
        capabilities.extend(
            load_dataset_catalog_capabilities(
                production_data_root,
                max_capabilities=config.max_l1_capabilities,
            )
        )
    if "l2_scholar_kg" in labels:
        capabilities.extend(
            load_scholar_capabilities(
                production_data_root,
                max_capabilities=config.max_scholar_capabilities,
            )
        )
    if "l3_lex_kg" in labels:
        capabilities.extend(
            load_lex_capabilities(
                production_data_root,
                max_capabilities=config.max_lex_capabilities,
                release_snapshot_at=release_snapshot_at,
            )
        )
    if "l4_ukraine_panels" in labels:
        capabilities.extend(
            load_ukraine_panel_capabilities(
                production_data_root,
                calibration_context=calibration_context,
                foundry_context=foundry_context,
            )
        )
    if "l5_calibration_registries" in labels:
        capabilities.extend(
            load_calibration_capabilities(production_data_root, calibration_context)
        )
    if "l6_foundry_method_contracts" in labels:
        capabilities.extend(load_foundry_capabilities(production_data_root, foundry_context))
    if "l7_curated_contracts" in labels:
        capabilities.extend(load_l7_curated_contract_capabilities(production_data_root))
    return tuple(capabilities)


def _empty_calibration_context() -> CalibrationContext:
    return CalibrationContext(
        source_assets=(),
        coverage_rules={},
        proxy_mappings={},
        identification_modes={},
        schema_regime=None,
        governance_passes={},
    )


def _incremental_rebuild_labels(changed_input_labels: Sequence[str]) -> tuple[str, ...]:
    changed = set(changed_input_labels)
    rebuilt = set(changed)
    if changed & INTERDEPENDENT_PANEL_GROUPS:
        rebuilt.update(INTERDEPENDENT_PANEL_GROUPS)
    return tuple(sorted(rebuilt))


def _load_previous_capabilities(
    previous_manifest_path: Path | None,
) -> tuple[EvidenceCapability, ...]:
    if previous_manifest_path is None:
        return ()
    duckdb_path = previous_manifest_path.resolve().parent / CAPABILITY_INDEX_DUCKDB
    with duckdb.connect(str(duckdb_path), read_only=True) as con:
        rows = con.execute(
            "SELECT capability_json FROM capabilities ORDER BY capability_id"
        ).fetchall()
    return tuple(EvidenceCapability.model_validate_json(row[0]) for row in rows)


def _merge_incremental_capabilities(
    *,
    previous_capabilities: Sequence[EvidenceCapability],
    rebuilt_capabilities: Sequence[EvidenceCapability],
    rebuilt_input_labels: Sequence[str],
) -> list[EvidenceCapability]:
    rebuilt = set(rebuilt_input_labels)
    retained = [
        capability
        for capability in previous_capabilities
        if not (_capability_input_groups(capability) & rebuilt)
    ]
    return _dedupe_capabilities((*retained, *rebuilt_capabilities))


def _capability_input_groups(capability: EvidenceCapability) -> set[str]:
    groups = capability.metadata.get("input_groups") or ()
    if isinstance(groups, str):
        return {groups}
    if isinstance(groups, Sequence):
        return {str(group) for group in groups}
    return {
        SOURCE_LAYER_TO_INPUT_GROUP[asset.source_layer]
        for asset in capability.source_assets
        if asset.source_layer in SOURCE_LAYER_TO_INPUT_GROUP
    }


def discover_input_fingerprints(production_data_root: Path) -> dict[str, Any]:
    """Return deterministic per-layer fingerprints for incremental rebuilds."""

    root = production_data_root.resolve()
    grouped_paths: dict[str, list[Path]] = {
        "l1_dataset_catalog": list(root.glob("**/dataset_catalog.duckdb")),
        "l2_scholar_kg": list(root.glob("**/scholar_knowledge.duckdb")),
        "l3_lex_kg": list(root.glob("**/lex_knowledge_graph.duckdb")),
        "l4_ukraine_panels": _l4_ukraine_panel_paths(root),
        "l5_calibration_registries": [
            path
            for name in (
                "measurement_registry.json",
                "identification_mode_registry.json",
                "schema_regime_registry.json",
                "governance_pass_mapping_v1.json",
            )
            for path in root.glob(f"**/{name}")
        ]
        + _l5_derived_parquet_paths(root),
        "l6_foundry_method_contracts": list(root.glob("**/observation_to_contract_manifest.json")),
        "l7_curated_contracts": [
            path
            for name in ("data_contracts.json", "source_bindings.json")
            for path in root.glob(f"**/{name}")
        ],
    }
    fingerprints: dict[str, Any] = {}
    for label, paths in sorted(grouped_paths.items()):
        entries = [_fingerprint_path(path, root) for path in sorted(set(paths))]
        fingerprints[label] = {
            "source_layer": INPUT_GROUP_TO_SOURCE_LAYER[label],
            "asset_count": len(entries),
            "assets": entries,
            "group_digest": _sha256_json(entries),
        }
    return fingerprints


def load_dataset_catalog_capabilities(
    production_data_root: Path,
    *,
    max_capabilities: int,
) -> tuple[EvidenceCapability, ...]:
    """Load L1 dataset catalog capabilities from DCAT-shaped DuckDB tables."""

    path = _find_first(production_data_root, "**/dataset_catalog.duckdb")
    if path is None:
        return ()
    rows: list[Mapping[str, Any]] = []
    with duckdb.connect(str(path), read_only=True) as con:
        required_tables = {
            "ds_datasets",
            "ds_distributions",
            "ds_metric_bindings",
            "ds_schema_profiles",
            "ds_variable_alignments",
        }
        if not required_tables <= set(_show_tables(con)):
            return ()
        sql = """
            WITH metric AS (
                SELECT
                    dataset_id,
                    max(metric_id) AS metric_id,
                    max(confidence) AS metric_confidence
                FROM ds_metric_bindings
                GROUP BY dataset_id
            ),
            schema_profile AS (
                SELECT dataset_id, count(*) AS schema_profile_count
                FROM ds_schema_profiles
                GROUP BY dataset_id
            ),
            variable_alignment AS (
                SELECT
                    dataset_id,
                    avg(confidence) AS variable_alignment_confidence,
                    max(CASE WHEN is_proxy THEN 1 ELSE 0 END) AS has_proxy_alignment
                FROM ds_variable_alignments
                GROUP BY dataset_id
            )
            SELECT
                d.id,
                d.dataset_id,
                d.title,
                d.source,
                d.publisher,
                d.license,
                d.coverage_countries,
                d.coverage_time_start,
                d.coverage_time_end,
                d.coverage_granularity,
                d.quality_machine_readable_score,
                d.quality_parser_support_score,
                d.quality_freshness_score,
                d.quality_execution_readiness_score,
                d.preferred_distribution_id,
                dist.format AS distribution_format,
                dist.machine_readable AS distribution_machine_readable,
                dist.parser_supported AS distribution_parser_supported,
                metric.metric_id,
                metric.metric_confidence,
                coalesce(schema_profile.schema_profile_count, 0) AS schema_profile_count,
                variable_alignment.variable_alignment_confidence,
                coalesce(variable_alignment.has_proxy_alignment, 0) AS has_proxy_alignment
            FROM ds_datasets d
            LEFT JOIN ds_distributions dist
              ON dist.id = d.preferred_distribution_id
            LEFT JOIN metric
              ON metric.dataset_id = d.dataset_id OR metric.dataset_id = d.id
            LEFT JOIN schema_profile
              ON schema_profile.dataset_id = d.dataset_id OR schema_profile.dataset_id = d.id
            LEFT JOIN variable_alignment
              ON variable_alignment.dataset_id = d.dataset_id OR variable_alignment.dataset_id = d.id
            ORDER BY
              CASE WHEN metric.metric_id IS NULL THEN 1 ELSE 0 END,
              d.quality_execution_readiness_score DESC NULLS LAST,
              d.id
            LIMIT ?
        """
        rows = [
            dict(zip([col[0] for col in con.description], row, strict=True))
            for row in con.execute(sql, [max_capabilities]).fetchall()
        ]

    capabilities = []
    for row in rows:
        dataset_ref = _safe_text(row.get("dataset_id") or row.get("id") or "dataset")
        metric_id = _safe_text(row.get("metric_id"))
        title = _safe_text(row.get("title"))
        construct = _construct_from_text(" ".join(part for part in (metric_id, title) if part))
        breakdown = {
            "machine_readable": _score(row.get("quality_machine_readable_score"), default=0.5),
            "parser_readiness": _score(row.get("quality_parser_support_score"), default=0.5),
            "freshness": _score(row.get("quality_freshness_score"), default=0.5),
            "execution_readiness": _score(
                row.get("quality_execution_readiness_score"), default=0.5
            ),
            "schema_profile_present": 1.0 if int(row.get("schema_profile_count") or 0) > 0 else 0.0,
            "variable_alignment_confidence": _score(
                row.get("variable_alignment_confidence"), default=0.25
            ),
        }
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "fabric_data",
                    "catalog",
                    dataset_ref,
                    metric_id or title or "dataset",
                ),
                construct=construct,
                modality=("fabric_data",),
                evidence_mode="observed"
                if row.get("has_proxy_alignment") != 1
                else "proxy_observational",
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography=_coverage_geography(row.get("coverage_countries")),
                    time_start=_optional_str(row.get("coverage_time_start")),
                    time_end=_optional_str(row.get("coverage_time_end")),
                    entity_scope="dataset",
                    temporal_granularity=_optional_str(row.get("coverage_granularity")),
                ),
                identification_mode="catalog_bound",
                trust_tier="catalog_metadata",
                quality_score=QualityScore(
                    composite=_mean_score(breakdown.values()),
                    breakdown=breakdown,
                ),
                source_assets=(
                    CapabilitySourceAsset(
                        ref=f"duckdb:{path.name}:ds_datasets:{dataset_ref}",
                        source_layer="L1",
                        asset_type="duckdb_table_row",
                        role="dataset_metadata",
                        path=_relative_path(path, production_data_root),
                        table="ds_datasets",
                    ),
                    CapabilitySourceAsset(
                        ref=f"duckdb:{path.name}:ds_metric_bindings:{metric_id or dataset_ref}",
                        source_layer="L1",
                        asset_type="duckdb_table_row",
                        role="metric_binding",
                        path=_relative_path(path, production_data_root),
                        table="ds_metric_bindings",
                    ),
                    CapabilitySourceAsset(
                        ref=(
                            f"duckdb:{path.name}:ds_distributions:"
                            f"{row.get('preferred_distribution_id') or dataset_ref}"
                        ),
                        source_layer="L1",
                        asset_type="duckdb_table_row",
                        role="distribution_metadata",
                        path=_relative_path(path, production_data_root),
                        table="ds_distributions",
                        metadata={
                            "format": _optional_str(row.get("distribution_format")),
                            "machine_readable": bool(row.get("distribution_machine_readable")),
                            "parser_supported": bool(row.get("distribution_parser_supported")),
                        },
                    ),
                    CapabilitySourceAsset(
                        ref=f"duckdb:{path.name}:ds_schema_profiles:{dataset_ref}",
                        source_layer="L1",
                        asset_type="duckdb_table",
                        role="schema_profile",
                        path=_relative_path(path, production_data_root),
                        table="ds_schema_profiles",
                    ),
                    CapabilitySourceAsset(
                        ref=f"duckdb:{path.name}:ds_variable_alignments:{dataset_ref}",
                        source_layer="L1",
                        asset_type="duckdb_table",
                        role="variable_alignment",
                        path=_relative_path(path, production_data_root),
                        table="ds_variable_alignments",
                    ),
                ),
                limitations=(
                    "Catalog metadata is a capability discovery input, not raw observation evidence.",
                ),
                authority_envelope=AuthorityEnvelope(
                    research="admissible",
                    governed_pilot="admissible_with_catalog_validation",
                    production="blocked_until_source_specific_contract",
                    authoritative_for=("capability_discovery",),
                    may_not_use_for=("production_closeout_without_source_contract",),
                    authority_basis=("L1 dataset_catalog.duckdb",),
                ),
                lineage_refs=(f"dataset_catalog:{path.name}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="catalog_release_metadata",
                    last_updated=_optional_str(row.get("coverage_time_end")),
                    source_release_ref=_release_ref_from_path(path),
                ),
                rights_envelope=RightsEnvelope(
                    access_class="catalog_license",
                    license=_optional_str(row.get("license")),
                ),
                metadata={"input_groups": ("l1_dataset_catalog",)},
            )
        )
    return tuple(capabilities)


def load_scholar_capabilities(
    production_data_root: Path,
    *,
    max_capabilities: int,
) -> tuple[EvidenceCapability, ...]:
    """Load L2 Scholar KG causal, transport, contested, parameter, and boundary assets."""

    path = _find_first(production_data_root, "**/scholar_knowledge.duckdb")
    if path is None:
        return ()
    with duckdb.connect(str(path), read_only=True) as con:
        if "ac_skg_edges" not in _show_tables(con):
            return ()
        rows = _fetch_dicts(
            con,
            """
            SELECT
                e.edge_id,
                e.src,
                e.dst,
                e.direction,
                e.evidence_strength,
                e.confidence,
                e.scope_conditions,
                e.meta_effect_size,
                t.transport_confidence,
                c.resolution_status,
                c.positive_weight,
                c.negative_weight,
                c.mixed_weight,
                c.strongest_dissent_strength,
                p.id AS parameter_id,
                p.variable_name AS parameter_variable,
                p.trust_score AS parameter_trust_score,
                b.boundary_id,
                b.variable AS boundary_variable,
                b.confidence AS boundary_confidence
            FROM ac_skg_edges e
            LEFT JOIN ac_skg_transport_scores t ON t.edge_id = e.edge_id
            LEFT JOIN ac_skg_contested_edges c
              ON c.src_family = e.src AND c.dst_family = e.dst
            LEFT JOIN ac_parameter_estimates p
              ON lower(p.variable_name) = lower(e.dst)
            LEFT JOIN ac_boundary_conditions b
              ON lower(b.variable) = lower(e.dst)
            ORDER BY e.confidence DESC NULLS LAST, e.edge_id
            LIMIT ?
            """,
            [max_capabilities],
        )

    capabilities: list[EvidenceCapability] = []
    for row in rows:
        dst = _safe_text(row.get("dst") or row.get("effect") or "scholar_effect")
        src = _safe_text(row.get("src") or "scholar_cause")
        construct = _construct_from_text(dst)
        confidence = _score(row.get("confidence"), default=0.5)
        transport = _score(row.get("transport_confidence"), default=confidence)
        parameter = _score(row.get("parameter_trust_score"), default=confidence)
        boundary = _score(row.get("boundary_confidence"), default=confidence)
        breakdown = {
            "causal_edge_confidence": confidence,
            "transport_confidence": transport,
            "parameter_trust": parameter,
            "boundary_condition_confidence": boundary,
            "contestability_penalty": 1.0
            - min(1.0, _score(row.get("strongest_dissent_strength"), default=0.0)),
        }
        edge_id = _safe_text(row.get("edge_id") or f"{src}->{dst}")
        source_assets = [
            CapabilitySourceAsset(
                ref=f"duckdb:{path.name}:ac_skg_edges:{edge_id}",
                source_layer="L2",
                asset_type="duckdb_table_row",
                role="causal_edge",
                path=_relative_path(path, production_data_root),
                table="ac_skg_edges",
                fields=(src, dst),
            ),
            CapabilitySourceAsset(
                ref=f"duckdb:{path.name}:ac_skg_transport_scores:{edge_id}",
                source_layer="L2",
                asset_type="duckdb_table_row",
                role="transport_score",
                path=_relative_path(path, production_data_root),
                table="ac_skg_transport_scores",
            ),
        ]
        if row.get("resolution_status") is not None:
            source_assets.append(
                CapabilitySourceAsset(
                    ref=f"duckdb:{path.name}:ac_skg_contested_edges:{edge_id}",
                    source_layer="L2",
                    asset_type="duckdb_table_row",
                    role="contested_edge",
                    path=_relative_path(path, production_data_root),
                    table="ac_skg_contested_edges",
                )
            )
        if row.get("parameter_id") is not None:
            source_assets.append(
                CapabilitySourceAsset(
                    ref=f"duckdb:{path.name}:ac_parameter_estimates:{row['parameter_id']}",
                    source_layer="L2",
                    asset_type="duckdb_table_row",
                    role="parameter_estimate",
                    path=_relative_path(path, production_data_root),
                    table="ac_parameter_estimates",
                )
            )
        if row.get("boundary_id") is not None:
            source_assets.append(
                CapabilitySourceAsset(
                    ref=f"duckdb:{path.name}:ac_boundary_conditions:{row['boundary_id']}",
                    source_layer="L2",
                    asset_type="duckdb_table_row",
                    role="boundary_condition",
                    path=_relative_path(path, production_data_root),
                    table="ac_boundary_conditions",
                )
            )
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "scholar_claim",
                    src,
                    dst,
                    edge_id,
                ),
                construct=construct,
                modality=("scholar_claim",),
                evidence_mode="scholarly_causal_support",
                concept_spine_refs=(f"concept:{construct}", f"concept:{_slug(src)}"),
                scope=CapabilityScope(geography="multi_context", entity_scope="construct_pair"),
                identification_mode="literature_supported",
                trust_tier="academic_synthesis",
                quality_score=QualityScore(
                    composite=_mean_score(breakdown.values()),
                    breakdown=breakdown,
                ),
                source_assets=tuple(source_assets),
                limitations=("Scholar support cannot satisfy direct runtime outcome observation.",),
                authority_envelope=AuthorityEnvelope(
                    research="admissible",
                    governed_pilot="admissible_as_scholarly_support",
                    production="blocked_for_direct_outcome_evidence",
                    authoritative_for=("scholarly_support", "method_support"),
                    may_not_use_for=("direct_data_observation", "legal_authority"),
                    authority_basis=("L2 scholar_knowledge.duckdb",),
                ),
                lineage_refs=(f"scholar_kg:{path.name}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="scholar_release_snapshot",
                    source_release_ref=_release_ref_from_path(path),
                ),
                rights_envelope=RightsEnvelope(access_class="academic_metadata"),
                metadata={
                    "input_groups": ("l2_scholar_kg",),
                    "cause": src,
                    "effect": dst,
                    "direction": _optional_str(row.get("direction")),
                    "resolution_status": _optional_str(row.get("resolution_status")),
                },
            )
        )
    return tuple(capabilities)


def load_lex_capabilities(
    production_data_root: Path,
    *,
    max_capabilities: int,
    release_snapshot_at: datetime,
) -> tuple[EvidenceCapability, ...]:
    """Load L3 Lex KG normative facts, thresholds, amendments, audit, refs, entities."""

    path = _find_first(production_data_root, "**/lex_knowledge_graph.duckdb")
    if path is None:
        return ()
    with duckdb.connect(str(path), read_only=True) as con:
        tables = set(_show_tables(con))
        if "lex_rule_thresholds" not in tables:
            return ()
        rows = _fetch_dicts(
            con,
            """
            SELECT
                th.threshold_id,
                th.fact_id,
                th.metric,
                th.operator,
                th.value_decimal,
                th.unit,
                th.applies_to,
                nf.norm_type,
                nf.action_canon,
                nf.jurisdiction,
                nf.subject_en,
                nf.object_en,
                nf.trust_tier,
                nf.fused_confidence,
                nf.grounding_status,
                nf.canonical_status,
                nf.reference_resolution_status,
                nf.hallucination_flags_json,
                nf.doc_id,
                nf.provision_citation,
                nf.effective_from,
                nf.effective_to,
                nf.temporal_state,
                nf.temporal_resolution_status,
                nf.extraction_source,
                ta.audit_id,
                ref.reference_id,
                ent.entity_id,
                am.amendment_id
            FROM lex_rule_thresholds th
            LEFT JOIN lex_normative_facts nf ON nf.fact_id = th.fact_id
            LEFT JOIN lex_temporal_audit ta ON ta.fact_id = th.fact_id
            LEFT JOIN lex_references ref ON ref.doc_id = nf.doc_id
            LEFT JOIN lex_entities ent ON ent.entity_id = nf.subject_id
            LEFT JOIN lex_amendments am ON am.amended_doc_id = nf.doc_id
            ORDER BY nf.fused_confidence DESC NULLS LAST, th.threshold_id
            LIMIT ?
            """,
            [max_capabilities],
        )

    capabilities = []
    for row in rows:
        metric = _safe_text(row.get("metric") or "legal_threshold")
        construct = _legal_construct(metric, row.get("applies_to"))
        confidence = _score(row.get("fused_confidence"), default=0.7)
        threshold_id = _safe_text(row.get("threshold_id"))
        capability_id = deterministic_capability_id(
            construct,
            "lex_norm",
            threshold_id,
            metric,
        )
        legal_truth = _build_legal_norm_owner_truth(
            row,
            capability_ref=capability_id,
            lex_path=path,
            release_snapshot_at=release_snapshot_at,
        )
        if legal_truth is None:
            continue
        source_assets = [
            CapabilitySourceAsset(
                ref=f"duckdb:{path.name}:lex_rule_thresholds:{threshold_id}",
                source_layer="L3",
                asset_type="duckdb_table_row",
                role="legal_threshold",
                path=_relative_path(path, production_data_root),
                table="lex_rule_thresholds",
                fields=(metric,),
            ),
            CapabilitySourceAsset(
                ref=f"duckdb:{path.name}:lex_normative_facts:{row.get('fact_id') or threshold_id}",
                source_layer="L3",
                asset_type="duckdb_table_row",
                role="normative_fact",
                path=_relative_path(path, production_data_root),
                table="lex_normative_facts",
            ),
        ]
        for table, row_key, role in (
            ("lex_temporal_audit", "audit_id", "temporal_audit"),
            ("lex_references", "reference_id", "legal_reference"),
            ("lex_entities", "entity_id", "legal_entity"),
            ("lex_amendments", "amendment_id", "amendment_lineage"),
        ):
            if row.get(row_key) is not None:
                source_assets.append(
                    CapabilitySourceAsset(
                        ref=f"duckdb:{path.name}:{table}:{row[row_key]}",
                        source_layer="L3",
                        asset_type="duckdb_table_row",
                        role=role,
                        path=_relative_path(path, production_data_root),
                        table=table,
                    )
                )
        capabilities.append(
            EvidenceCapability(
                capability_id=capability_id,
                construct=construct,
                modality=("lex_norm",),
                evidence_mode="legal_threshold",
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography=_optional_str(row.get("jurisdiction")) or "UA",
                    time_start=_optional_str(row.get("effective_from")),
                    time_end=_optional_str(row.get("effective_to")),
                    entity_scope="legal_subject",
                    jurisdiction=_optional_str(row.get("jurisdiction")) or "UA",
                ),
                identification_mode="legal_threshold",
                trust_tier=_optional_str(row.get("trust_tier")) or "legal_kg_candidate",
                quality_score=QualityScore(
                    composite=_mean_score((confidence, 1.0, 0.9)),
                    breakdown={
                        "normative_fact_confidence": confidence,
                        "threshold_present": 1.0,
                        "temporal_audit_present": 1.0 if row.get("audit_id") else 0.5,
                    },
                ),
                source_assets=tuple(source_assets),
                limitations=("Legal thresholds cannot satisfy empirical outcome evidence.",),
                authority_envelope=AuthorityEnvelope(
                    research="admissible",
                    governed_pilot="admissible_as_legal_authority",
                    production="admissible_as_legal_authority",
                    authoritative_for=("legal_authority", "eligibility_threshold"),
                    may_not_use_for=("empirical_outcome_observation",),
                    authority_basis=("L3 lex_knowledge_graph.duckdb",),
                ),
                lineage_refs=(f"lex_kg:{path.name}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="legal_release_temporal_snapshot",
                    source_release_ref=_release_ref_from_path(path),
                ),
                rights_envelope=RightsEnvelope(access_class="public_legal_metadata"),
                metadata={
                    "input_groups": ("l3_lex_kg",),
                    "metric": metric,
                    "operator": _optional_str(row.get("operator")),
                    "unit": _optional_str(row.get("unit")),
                    "legal_norm_owner_truth": legal_truth.model_dump(
                        mode="json",
                        exclude={"temporal_snapshot_at"},
                    ),
                },
            )
        )
    return tuple(capabilities)


def _build_legal_norm_owner_truth(
    row: Mapping[str, Any],
    *,
    capability_ref: str,
    lex_path: Path,
    release_snapshot_at: datetime,
) -> LegalNormOwnerTruth | None:
    """Admit only grounded, hallucination-clear, temporally resolved Lex rows."""

    fact_id = _optional_str(row.get("fact_id"))
    document_ref = _optional_str(row.get("doc_id"))
    citation = _optional_str(row.get("provision_citation"))
    jurisdiction = _optional_str(row.get("jurisdiction"))
    audit_id = _optional_str(row.get("audit_id"))
    reference_id = _optional_str(row.get("reference_id"))
    effective_from = _iso_date(row.get("effective_from"))
    effective_to_raw = _optional_str(row.get("effective_to"))
    effective_to = _iso_date(effective_to_raw) if effective_to_raw else None
    required = (
        fact_id,
        document_ref,
        citation,
        jurisdiction,
        audit_id,
        reference_id,
        effective_from,
    )
    if any(value is None for value in required):
        return None
    if _optional_str(row.get("grounding_status")) != "grounded":
        return None
    if _optional_str(row.get("canonical_status")) not in {"canonical", "canonicalized"}:
        return None
    if _optional_str(row.get("reference_resolution_status")) != "resolved":
        return None
    if _optional_str(row.get("temporal_state")) != "effective":
        return None
    if _optional_str(row.get("temporal_resolution_status")) != "resolved":
        return None
    if not _hallucination_flags_are_clear(row.get("hallucination_flags_json")):
        return None
    if effective_to_raw and effective_to is None:
        return None
    provenance_refs = (
        f"duckdb:{lex_path.name}:lex_normative_facts:{fact_id}",
        f"duckdb:{lex_path.name}:lex_temporal_audit:{audit_id}",
        f"duckdb:{lex_path.name}:lex_references:{reference_id}",
    )
    try:
        return LegalNormOwnerTruth(
            legal_norm_ref=capability_ref,
            normative_fact_ref=provenance_refs[0],
            source_document_ref=document_ref,
            provision_citation=citation,
            grounding_status="grounded",
            hallucination_status="verified_clear",
            jurisdiction=jurisdiction,
            effective_from=effective_from,
            effective_to=effective_to,
            temporal_state="effective",
            temporal_resolution_status="resolved",
            temporal_snapshot_at=release_snapshot_at,
            temporal_audit_ref=provenance_refs[1],
            provenance_refs=provenance_refs,
        )
    except ValueError:
        return None


def _hallucination_flags_are_clear(raw: object) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        flags = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(flags, (list, dict)) and not flags


def _iso_date(raw: object) -> date | None:
    value = _optional_str(raw)
    if value is None:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _release_snapshot_at(raw: str) -> datetime:
    try:
        snapshot = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("capability release snapshot must be an ISO-8601 datetime") from exc
    if snapshot.tzinfo is None:
        raise ValueError("capability release snapshot must be timezone-aware")
    return snapshot


def load_calibration_registries(production_data_root: Path) -> CalibrationContext:
    """Load L5 measurement, identification, schema-regime, and governance registries."""

    measurement_path = _find_first(production_data_root, "**/measurement_registry.json")
    identification_path = _find_first(production_data_root, "**/identification_mode_registry.json")
    schema_regime_path = _find_first(production_data_root, "**/schema_regime_registry.json")
    governance_path = _find_first(production_data_root, "**/governance_pass_mapping_v1.json")
    measurement = _load_json(measurement_path) if measurement_path else {}
    identification = _load_json(identification_path) if identification_path else {}
    schema_regime = _load_json(schema_regime_path) if schema_regime_path else {}
    governance = _load_json(governance_path) if governance_path else {}

    source_assets = []
    for path, role in (
        (measurement_path, "measurement_registry"),
        (identification_path, "identification_mode_registry"),
        (schema_regime_path, "schema_regime_registry"),
        (governance_path, "governance_pass_mapping"),
    ):
        if path:
            source_assets.append(
                CapabilitySourceAsset(
                    ref=f"json:{path.name}",
                    source_layer="L5",
                    asset_type="json_registry",
                    role=role,
                    path=_relative_path(path, production_data_root),
                )
            )
    coverage_rules = {
        str(key): float(value)
        for key, value in (measurement.get("coverage_rules") or {}).items()
        if isinstance(value, int | float)
    }
    selected_modes = {
        str(key): str(value.get("selected_mode") or value.get("primary_mode") or "unknown")
        for key, value in identification.items()
        if isinstance(value, Mapping)
    }
    governance_passes = {
        str(key): tuple(str(item) for item in value)
        for key, value in governance.items()
        if isinstance(value, list)
    }
    regimes = schema_regime.get("regimes") or {}
    current_regime = (
        "ukraine_schema_v2" if "ukraine_schema_v2" in regimes else next(iter(regimes), None)
    )
    return CalibrationContext(
        source_assets=tuple(source_assets),
        coverage_rules=coverage_rules,
        proxy_mappings=measurement.get("proxy_mappings") or {},
        identification_modes=selected_modes,
        schema_regime=current_regime,
        governance_passes=governance_passes,
    )


def load_ukraine_panel_capabilities(
    production_data_root: Path,
    *,
    calibration_context: CalibrationContext,
    foundry_context: FoundryRouteContext,
) -> tuple[EvidenceCapability, ...]:
    """Load L4 Ukraine normalized panels using Parquet metadata only."""

    profiles = _profile_ukraine_parquets(production_data_root)
    if not profiles:
        return ()
    by_family = {profile.family: profile for profile in profiles}
    capabilities: list[EvidenceCapability] = []
    if "dps_financials" in by_family:
        capabilities.append(
            _build_firm_fundamentals_capability(
                by_family,
                calibration_context=calibration_context,
                foundry_context=foundry_context,
                production_data_root=production_data_root,
            )
        )
    for profile in profiles:
        if profile.family in {"dps_financials", "distress_events", "dps_tax_risk"}:
            continue
        construct = _panel_construct(profile.family, profile.fields)
        source_family = _source_family_from_panel(profile.family)
        coverage = calibration_context.coverage_rules.get(source_family, 0.5)
        breakdown = {
            "parquet_schema_present": 1.0,
            "row_count_metadata_present": 1.0 if profile.row_count >= 0 else 0.0,
            "coverage": _score(coverage, default=0.5),
            "governance_pass_presence": 1.0
            if calibration_context.governance_passes.get(source_family)
            else 0.5,
        }
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "fabric_data",
                    profile.family,
                    profile.path.stem,
                ),
                construct=construct,
                modality=("fabric_data",),
                evidence_mode="observed"
                if coverage >= 0.75
                else ("proxy_observational" if coverage >= 0.5 else "context_only"),
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography="UA",
                    schema_regime=calibration_context.schema_regime,
                    population=source_family,
                    entity_scope=_entity_scope_from_fields(profile.fields),
                ),
                identification_mode=calibration_context.identification_modes.get(
                    source_family, "metadata_profiled"
                ),
                trust_tier=_trust_tier_for_coverage(coverage),
                quality_score=QualityScore(
                    composite=_mean_score(breakdown.values()),
                    breakdown=breakdown,
                ),
                source_assets=(
                    _source_asset_from_parquet(profile, role="normalized_panel"),
                    *calibration_context.source_assets,
                ),
                method_contract_targets=foundry_context.targets_by_family.get(source_family, ()),
                limitations=("Panel profile uses Parquet metadata row counts, not full CI scans.",),
                authority_envelope=_authority_for_panel(coverage, source_family),
                lineage_refs=(f"source_snapshot:{_release_ref_from_path(profile.path)}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="release_snapshot_metadata",
                    source_release_ref=_release_ref_from_path(profile.path),
                ),
                rights_envelope=RightsEnvelope(
                    access_class="government_administrative",
                    public_export_allowed="aggregate_only",
                    restrictions=("no_row_level_public_export",),
                ),
                metadata={
                    "input_groups": ("l4_ukraine_panels", "l5_calibration_registries"),
                    "row_group_count": profile.row_group_count,
                    "governance_passes": calibration_context.governance_passes.get(
                        source_family, ()
                    ),
                },
            )
        )
    return tuple(capabilities)


def load_calibration_capabilities(
    production_data_root: Path,
    calibration_context: CalibrationContext,
) -> tuple[EvidenceCapability, ...]:
    """Expose L5 calibration registries as governance context capabilities."""

    if not calibration_context.source_assets:
        return ()
    capabilities = []
    for family, coverage in sorted(calibration_context.coverage_rules.items()):
        construct = _panel_construct(family, ())
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "fabric_data",
                    "calibration",
                    family,
                ),
                construct=construct,
                modality=("fabric_data", "runtime_calibration"),
                evidence_mode="context_only",
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography="UA",
                    schema_regime=calibration_context.schema_regime,
                    population=family,
                    entity_scope="calibration_registry",
                ),
                identification_mode=calibration_context.identification_modes.get(
                    family, "registry_context"
                ),
                trust_tier=_trust_tier_for_coverage(coverage),
                quality_score=QualityScore(
                    composite=_mean_score(
                        (
                            _score(coverage, default=0.5),
                            1.0 if calibration_context.governance_passes.get(family) else 0.5,
                        )
                    ),
                    breakdown={
                        "coverage": _score(coverage, default=0.5),
                        "governance_pass_presence": 1.0
                        if calibration_context.governance_passes.get(family)
                        else 0.5,
                    },
                ),
                source_assets=calibration_context.source_assets,
                limitations=(
                    "Calibration registry context cannot satisfy outcome evidence alone.",
                ),
                authority_envelope=AuthorityEnvelope(
                    research="admissible_as_context",
                    governed_pilot="admissible_as_governance_context",
                    production="blocked_for_standalone_claim_evidence",
                    authoritative_for=("calibration_context",),
                    may_not_use_for=("standalone_data_observation",),
                    authority_basis=("L5 calibration registries",),
                ),
                lineage_refs=(f"calibration_registry:{production_data_root.name}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="release_registry_snapshot",
                    source_release_ref=production_data_root.name,
                ),
                rights_envelope=RightsEnvelope(access_class="internal_registry"),
                metadata={"input_groups": ("l5_calibration_registries",)},
            )
        )
    return tuple(capabilities)


def load_foundry_method_contracts(production_data_root: Path) -> FoundryRouteContext:
    """Load L6 Foundry observation-to-method contract routes."""

    path = _find_first(production_data_root, "**/observation_to_contract_manifest.json")
    if path is None:
        return FoundryRouteContext(source_assets=(), targets_by_family={})
    payload = _load_json(path)
    targets_by_family: dict[str, tuple[str, ...]] = {}
    for route in payload.get("routes") or ():
        if not isinstance(route, Mapping):
            continue
        family = _safe_text(route.get("family"))
        target = route.get("target_contract") or {}
        contract_id = _safe_text(target.get("contract_id") if isinstance(target, Mapping) else "")
        if family and contract_id:
            targets_by_family[family] = tuple(
                sorted({*targets_by_family.get(family, ()), contract_id})
            )
    return FoundryRouteContext(
        source_assets=(
            CapabilitySourceAsset(
                ref=f"json:{path.name}",
                source_layer="L6",
                asset_type="json_manifest",
                role="observation_to_contract_manifest",
                path=_relative_path(path, production_data_root),
            ),
        ),
        targets_by_family=targets_by_family,
    )


def load_foundry_capabilities(
    production_data_root: Path,
    foundry_context: FoundryRouteContext,
) -> tuple[EvidenceCapability, ...]:
    """Expose L6 method-contract routes as method adequacy capabilities."""

    if not foundry_context.source_assets:
        return ()
    capabilities = []
    for family, targets in sorted(foundry_context.targets_by_family.items()):
        construct = _construct_from_family(family)
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "foundry_method_contract",
                    family,
                    *targets,
                ),
                construct=construct,
                modality=("foundry_method_contract",),
                evidence_mode="method_contract_route",
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography="UA", population=family, entity_scope="method_input"
                ),
                identification_mode="method_contract_routed",
                trust_tier="compiled_method_manifest",
                quality_score=QualityScore(
                    composite=0.9,
                    breakdown={"manifest_route_present": 1.0, "target_contract_present": 1.0},
                ),
                source_assets=(
                    *foundry_context.source_assets,
                    CapabilitySourceAsset(
                        ref=f"parquet:{family}",
                        source_layer="L4",
                        asset_type="normalized_panel_family",
                        role="method_input_family",
                        fields=(family,),
                    ),
                ),
                method_contract_targets=targets,
                limitations=("Method contract routes do not satisfy empirical evidence alone.",),
                authority_envelope=AuthorityEnvelope(
                    research="admissible",
                    governed_pilot="admissible_as_method_route",
                    production="admissible_as_method_route",
                    authoritative_for=("method_adequacy", "execution_route"),
                    may_not_use_for=("direct_data_observation", "legal_authority"),
                    authority_basis=("L6 observation_to_contract_manifest.json",),
                ),
                lineage_refs=(f"foundry_route:{family}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="method_manifest_snapshot",
                    source_release_ref=production_data_root.name,
                ),
                rights_envelope=RightsEnvelope(access_class="internal_method_manifest"),
                metadata={"input_groups": ("l6_foundry_method_contracts",), "family": family},
            )
        )
    return tuple(capabilities)


def load_l7_curated_contract_capabilities(
    production_data_root: Path,
) -> tuple[EvidenceCapability, ...]:
    """Load L7 curated contracts as compatibility-only inputs."""

    path = _find_first(production_data_root, "**/data_contracts.json")
    if path is None:
        return ()
    payload = _load_json(path)
    capabilities = []
    for contract in payload.get("contracts") or ():
        if not isinstance(contract, Mapping):
            continue
        metric_id = _safe_text(contract.get("metric_id") or contract.get("display_name"))
        if not metric_id:
            continue
        construct = _construct_from_text(metric_id)
        capabilities.append(
            EvidenceCapability(
                capability_id=deterministic_capability_id(
                    construct,
                    "compatibility_only",
                    metric_id,
                ),
                construct=construct,
                modality=("fabric_data", "compatibility_only"),
                evidence_mode="compatibility_only",
                concept_spine_refs=(f"concept:{construct}",),
                scope=CapabilityScope(
                    geography=_optional_str(contract.get("jurisdiction")) or "compatibility",
                    entity_scope="legacy_metric_contract",
                ),
                identification_mode="legacy_contract",
                trust_tier="compatibility_fixture",
                quality_score=QualityScore(
                    composite=0.2,
                    breakdown={
                        "legacy_contract_present": 1.0,
                        "production_authority": 0.0,
                    },
                ),
                source_assets=(
                    CapabilitySourceAsset(
                        ref=f"json:{path.name}:contracts:{metric_id}",
                        source_layer="L7",
                        asset_type="json_contract",
                        role="legacy_compatibility_contract",
                        path=_relative_path(path, production_data_root),
                        fields=(metric_id,),
                        compatibility_only=True,
                    ),
                ),
                limitations=("L7 curated contracts are compatibility inputs only.",),
                authority_envelope=AuthorityEnvelope(
                    research="admissible_as_compatibility_smoke",
                    governed_pilot="blocked_compatibility_only",
                    production="blocked_compatibility_only",
                    authoritative_for=("legacy_compatibility",),
                    may_not_use_for=("production_data_authority", "sole_data_authority"),
                    authority_basis=("L7 curated data_contracts.json",),
                ),
                lineage_refs=(f"legacy_curated:{path.name}",),
                freshness_envelope=FreshnessEnvelope(
                    freshness_class="legacy_fixture",
                    source_release_ref=_release_ref_from_path(path),
                ),
                rights_envelope=RightsEnvelope(access_class="legacy_compatibility_fixture"),
                may_not_use_for=("production_data_authority", "sole_data_authority"),
                compatibility_only=True,
                metadata={"input_groups": ("l7_curated_contracts",)},
            )
        )
    return tuple(capabilities)


def detect_same_construct_conflicts(
    capabilities: Sequence[EvidenceCapability],
) -> tuple[CapabilityConflictRecord, ...]:
    """Detect same-construct conflicts and emit W8.E-compatible records."""

    grouped: dict[tuple[str, str], list[EvidenceCapability]] = defaultdict(list)
    for capability in capabilities:
        grouped[(capability.construct_id, capability.scope.geography)].append(capability)
    conflicts = []
    for (construct, geography), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        contested = any(
            "contested" in str(capability.metadata.get("resolution_status", ""))
            for capability in group
        )
        forced = any(bool(capability.metadata.get("force_conflict")) for capability in group)
        if forced:
            conflict_class = "authority"
        elif contested:
            conflict_class = "empirical"
        else:
            continue
        refs = tuple(sorted(capability.capability_id for capability in group))
        conflicts.append(
            CapabilityConflictRecord(
                conflict_id=deterministic_record_id("conflict", construct, geography, *refs),
                construct=construct,
                geography=geography,
                conflict_class=conflict_class,
                conflict_resolution_route="scope_split_or_review",
                capability_refs=refs,
                evidence_refs=tuple(
                    sorted(
                        asset.ref for capability in group for asset in capability.source_assets[:2]
                    )
                ),
            )
        )
    return tuple(conflicts)


def build_white_space_nodes(
    capabilities: Sequence[EvidenceCapability],
) -> tuple[FailureModeNode, ...]:
    """Emit first-class failure-mode nodes for capability white space."""

    production_covered = {
        capability.construct_id
        for capability in capabilities
        if not capability.compatibility_only and capability_is_production_admissible(capability)
    }
    observed = {
        capability.construct_id
        for capability in capabilities
        if _capability_observes_construct(capability)
    }
    nodes: dict[str, FailureModeNode] = {}
    for construct in _white_space_construct_universe(capabilities):
        if construct not in observed:
            _add_failure_node(
                nodes,
                construct=construct,
                status="blocked_construct_not_observed",
                gap_type="construct_gap",
                cause_class="construct_not_observed",
                severity="blocking_production",
            )
            _add_failure_node(
                nodes,
                construct=construct,
                status="blocked_acquisition_required",
                gap_type="source_gap",
                cause_class="source_gap",
                severity="blocking_production",
            )
        if construct not in production_covered:
            _add_failure_node(
                nodes,
                construct=construct,
                status="blocked_acquisition_required",
                gap_type="acquisition_gap",
                cause_class="production_acquisition_required",
                severity="blocking_production",
            )

    for capability in capabilities:
        if capability.compatibility_only:
            continue
        if _construct_validity_below_production_floor(capability):
            _add_failure_node(
                nodes,
                construct=capability.construct_id,
                status="blocked_construct_validity_below_floor",
                gap_type="construct_validity_gap",
                cause_class="construct_validity_gap",
                severity="blocking_production",
            )
        if _sample_size_below_floor(capability):
            _add_failure_node(
                nodes,
                construct=capability.construct_id,
                status="blocked_sample_size_below_floor",
                gap_type="sample_size_gap",
                cause_class="sample_size_gap",
                severity="blocking_production",
            )
        if _freshness_gap(capability):
            _add_failure_node(
                nodes,
                construct=capability.construct_id,
                status="blocked_freshness",
                gap_type="freshness_gap",
                cause_class="freshness_gap",
                severity="blocking_production",
            )
        if _rights_gap(capability):
            _add_failure_node(
                nodes,
                construct=capability.construct_id,
                status="blocked_rights_boundary",
                gap_type="rights_gap",
                cause_class="rights_gap",
                severity="blocking_production",
            )
        if _legal_authority_gap(capability):
            _add_failure_node(
                nodes,
                construct=capability.construct_id,
                status="blocked_authority_boundary",
                gap_type="legal_authority_gap",
                cause_class="legal_authority_gap",
                severity="blocking_production",
            )
    return tuple(nodes[key] for key in sorted(nodes))


def _white_space_construct_universe(
    capabilities: Sequence[EvidenceCapability],
) -> tuple[str, ...]:
    constructs = {
        capability.construct_id
        for capability in capabilities
        if not capability.compatibility_only and capability.construct_id
    }
    return tuple(sorted(constructs))


def build_acquisition_strategies(
    white_space_nodes: Sequence[FailureModeNode],
) -> tuple[AcquisitionStrategy, ...]:
    """Build owned acquisition strategies for white-space nodes."""

    strategies: dict[str, AcquisitionStrategy] = {}
    for node in white_space_nodes:
        for strategy in _strategies_for_failure_node(node):
            strategies[strategy.strategy_id] = strategy
    return tuple(strategies[key] for key in sorted(strategies))


def _add_failure_node(
    nodes: dict[str, FailureModeNode],
    *,
    construct: str,
    status: str,
    gap_type: str,
    cause_class: str,
    severity: str,
    geography: str = "UA",
) -> None:
    failure_id = deterministic_record_id("failure", status, gap_type, construct, geography)
    nodes[failure_id] = FailureModeNode(
        failure_id=failure_id,
        construct=construct,
        geography=geography,
        cause_class=cause_class,
        severity=severity,
        owner="team-data-acquisition",
        acquisition_strategy_refs=_strategy_refs_for_construct(construct, geography),
        affected_authority_postures=("production",),
        detected_at="capability_index_release_time",
        status=status,
        gap_type=gap_type,
        domain=("uncategorized",),
        producer_owner="team-data-acquisition",
        authority_posture="production",
        ttl="P30D",
        review_cadence="P14D",
        escalation_owner="team-data-acquisition",
    )


def _strategy_refs_for_construct(construct: str, geography: str) -> tuple[str, ...]:
    return (deterministic_record_id("acquisition", "close_gap", construct, geography),)


def _strategies_for_failure_node(node: FailureModeNode) -> tuple[AcquisitionStrategy, ...]:
    strategy_id = deterministic_record_id(
        "acquisition", "close_gap", node.construct_id, node.geography
    )
    return (
        AcquisitionStrategy(
            strategy_id=strategy_id,
            target_construct=node.construct_id,
            owner=("team-data-acquisition", "team-legal-counsel"),
            owner_team="team-data-acquisition",
            legal_counsel_owner="team-legal-counsel",
            authority_class="government_official_request",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("legal_use_scope_review", "producer_handshake"),
            resulting_authority_envelope={
                "research": "admissible",
                "governed_pilot": "admissible_after_review",
                "production": "admissible_after_construct_validity_review",
            },
            contact_path=f"ops://team-data-acquisition#{_slug(node.construct_id)}",
            ttl="P30D",
            review_cadence="P14D",
            escalation_owner="team-data-acquisition",
            requires_construct_validity_review=True,
        ),
    )


def _capability_observes_construct(capability: EvidenceCapability) -> bool:
    if capability.compatibility_only:
        return False
    if "fabric_data" not in capability.modality:
        return False
    return capability.evidence_mode in {
        "observed",
        "derived",
        "derived_administrative_with_proxy_validation",
        "proxy_observational",
        "bounds_only",
    }


def _construct_validity_below_production_floor(capability: EvidenceCapability) -> bool:
    if capability.authority_envelope.production != "blocked_construct_validity_below_floor":
        return False
    value = capability.quality_score.breakdown.get(
        "construct_validity",
        capability.quality_score.composite,
    )
    return value < 0.70


def _sample_size_below_floor(capability: EvidenceCapability) -> bool:
    row_counts = [
        asset.row_count
        for asset in capability.source_assets
        if asset.row_count is not None and asset.row_count >= 0
    ]
    if not row_counts:
        return False
    if capability.construct_id == "regional_displacement_pressure":
        return min(row_counts) < 30
    return False


def _freshness_gap(capability: EvidenceCapability) -> bool:
    freshness = capability.freshness_envelope.freshness_class.casefold()
    production_state = capability.authority_envelope.production.casefold()
    return "stale" in freshness or "expired" in freshness or "freshness" in production_state


def _rights_gap(capability: EvidenceCapability) -> bool:
    restrictions = {item.casefold() for item in capability.rights_envelope.restrictions}
    return (
        not capability.rights_envelope.claim_evidence_use_allowed
        or "claim_evidence_forbidden" in restrictions
        or "no_claim_evidence_use" in restrictions
        or "rights" in capability.authority_envelope.production.casefold()
    )


def _legal_authority_gap(capability: EvidenceCapability) -> bool:
    production = capability.authority_envelope.production.casefold()
    if "blocked" not in production:
        return False
    if any(
        marker in production for marker in ("construct_validity", "freshness", "rights", "sample")
    ):
        return False
    return "lex_norm" not in capability.modality


def write_capability_index_duckdb(
    capability_index: CapabilityIndex,
    output_path: Path,
) -> dict[str, int]:
    """Persist the primary capability index store as DuckDB."""

    if output_path.exists():
        output_path.unlink()
    with duckdb.connect(str(output_path)) as con:
        con.execute(
            """
            CREATE TABLE capabilities (
                capability_id VARCHAR PRIMARY KEY,
                construct VARCHAR NOT NULL,
                modality_json VARCHAR NOT NULL,
                evidence_mode VARCHAR NOT NULL,
                geography VARCHAR NOT NULL,
                entity_scope VARCHAR NOT NULL,
                quality_composite DOUBLE NOT NULL,
                research_authority VARCHAR NOT NULL,
                governed_pilot_authority VARCHAR NOT NULL,
                production_authority VARCHAR NOT NULL,
                compatibility_only BOOLEAN NOT NULL,
                source_refs_json VARCHAR NOT NULL,
                method_contract_targets_json VARCHAR NOT NULL,
                capability_json VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE source_assets (
                asset_ref VARCHAR NOT NULL,
                capability_id VARCHAR NOT NULL,
                source_layer VARCHAR NOT NULL,
                asset_type VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                path VARCHAR,
                table_name VARCHAR,
                row_count BIGINT,
                fields_json VARCHAR NOT NULL,
                compatibility_only BOOLEAN NOT NULL,
                asset_json VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE capability_source_assets (
                capability_id VARCHAR NOT NULL,
                asset_ref VARCHAR NOT NULL,
                source_layer VARCHAR NOT NULL,
                role VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE conflicts (
                conflict_id VARCHAR PRIMARY KEY,
                construct VARCHAR NOT NULL,
                geography VARCHAR NOT NULL,
                conflict_class VARCHAR NOT NULL,
                conflict_json VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE failure_modes (
                failure_id VARCHAR PRIMARY KEY,
                construct VARCHAR NOT NULL,
                geography VARCHAR NOT NULL,
                cause_class VARCHAR NOT NULL,
                severity VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                gap_type VARCHAR NOT NULL,
                authority_posture VARCHAR NOT NULL,
                producer_owner VARCHAR NOT NULL,
                acquisition_strategy_refs_json VARCHAR NOT NULL,
                failure_json VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE acquisition_strategies (
                strategy_id VARCHAR PRIMARY KEY,
                target_construct VARCHAR NOT NULL,
                owner_team VARCHAR NOT NULL,
                legal_counsel_owner VARCHAR,
                authority_class VARCHAR NOT NULL,
                ttl VARCHAR NOT NULL,
                review_cadence VARCHAR NOT NULL,
                escalation_owner VARCHAR NOT NULL,
                strategy_json VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE index_metadata (
                key VARCHAR PRIMARY KEY,
                value_json VARCHAR NOT NULL
            )
            """
        )
        capability_rows = []
        asset_rows = []
        link_rows = []
        for capability in capability_index.capabilities:
            source_refs = tuple(sorted(asset.ref for asset in capability.source_assets))
            capability_rows.append(
                (
                    capability.capability_id,
                    capability.construct_id,
                    _json_dumps(capability.modality),
                    capability.evidence_mode,
                    capability.scope.geography,
                    capability.scope.entity_scope,
                    capability.quality_score.composite,
                    capability.authority_envelope.research,
                    capability.authority_envelope.governed_pilot,
                    capability.authority_envelope.production,
                    capability.compatibility_only,
                    _json_dumps(source_refs),
                    _json_dumps(capability.method_contract_targets),
                    _json_dumps(capability.model_dump(mode="json")),
                )
            )
            for asset in capability.source_assets:
                asset_rows.append(
                    (
                        asset.ref,
                        capability.capability_id,
                        asset.source_layer,
                        asset.asset_type,
                        asset.role,
                        asset.path,
                        asset.table,
                        asset.row_count,
                        _json_dumps(asset.fields),
                        asset.compatibility_only,
                        _json_dumps(asset.model_dump(mode="json")),
                    )
                )
                link_rows.append(
                    (
                        capability.capability_id,
                        asset.ref,
                        asset.source_layer,
                        asset.role,
                    )
                )
        con.executemany(
            "INSERT INTO capabilities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            capability_rows,
        )
        if asset_rows:
            con.executemany(
                "INSERT INTO source_assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                asset_rows,
            )
            con.executemany(
                "INSERT INTO capability_source_assets VALUES (?, ?, ?, ?)",
                link_rows,
            )
        conflict_rows = [
            (
                conflict.conflict_id,
                conflict.construct_id,
                conflict.geography,
                conflict.conflict_class,
                _json_dumps(conflict.model_dump(mode="json")),
            )
            for conflict in capability_index.conflicts
        ]
        if conflict_rows:
            con.executemany("INSERT INTO conflicts VALUES (?, ?, ?, ?, ?)", conflict_rows)
        failure_rows = [
            (
                node.failure_id,
                node.construct_id,
                node.geography,
                node.cause_class,
                node.severity,
                node.status,
                node.gap_type,
                node.authority_posture,
                node.producer_owner or node.owner,
                _json_dumps(node.acquisition_strategy_refs),
                _json_dumps(node.model_dump(mode="json")),
            )
            for node in capability_index.failure_modes
        ]
        if failure_rows:
            con.executemany(
                "INSERT INTO failure_modes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                failure_rows,
            )
        strategy_rows = [
            (
                strategy.strategy_id,
                strategy.target_construct,
                strategy.owner_team,
                strategy.legal_counsel_owner,
                strategy.authority_class,
                strategy.ttl,
                strategy.review_cadence,
                strategy.escalation_owner,
                _json_dumps(strategy.model_dump(mode="json")),
            )
            for strategy in capability_index.acquisition_strategies
        ]
        if strategy_rows:
            con.executemany(
                "INSERT INTO acquisition_strategies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                strategy_rows,
            )
        con.executemany(
            "INSERT INTO index_metadata VALUES (?, ?)",
            [
                ("schema_version", _json_dumps(capability_index.schema_version)),
                ("compiler_version", _json_dumps(capability_index.compiler_version)),
                ("release_ref", _json_dumps(capability_index.release_ref)),
                ("mode", _json_dumps(capability_index.mode)),
            ],
        )
        return _duckdb_table_counts(con)


def compute_logical_duckdb_digest(path: Path) -> str:
    """Return a deterministic digest over DuckDB table content, not file bytes."""

    with duckdb.connect(str(path), read_only=True) as con:
        payload: dict[str, Any] = {}
        for table in sorted(_show_tables(con)):
            rows = con.execute(f"SELECT * FROM {table} ORDER BY ALL").fetchall()
            columns = [description[0] for description in con.description]
            payload[table] = [dict(zip(columns, row, strict=True)) for row in rows]
    return _sha256_json(payload)


def build_summary(
    *,
    capability_index: CapabilityIndex,
    table_row_counts: Mapping[str, int],
    artifact_size_profile: Mapping[str, int],
    performance_budget: Mapping[str, Any],
    capability_floors: Mapping[str, Any],
    incremental: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the human-readable summary/export payload."""

    modality_counts: Counter[str] = Counter()
    evidence_mode_counts: Counter[str] = Counter()
    source_layer_counts: Counter[str] = Counter()
    for capability in capability_index.capabilities:
        evidence_mode_counts[capability.evidence_mode] += 1
        for modality in capability.modality:
            modality_counts[modality] += 1
        if capability.compatibility_only:
            modality_counts["compatibility_only"] += 1
        for asset in capability.source_assets:
            source_layer_counts[asset.source_layer] += 1
    return {
        "schema_version": "policyos.capability_index.summary.v1",
        "primary_runtime_output": CAPABILITY_INDEX_DUCKDB,
        "exports_are_summary_only": True,
        "compiler_version": capability_index.compiler_version,
        "mode": capability_index.mode,
        "capability_count": len(capability_index.capabilities),
        "conflict_count": len(capability_index.conflicts),
        "white_space_count": len(capability_index.white_space),
        "modality_counts": dict(sorted(modality_counts.items())),
        "evidence_mode_counts": dict(sorted(evidence_mode_counts.items())),
        "source_layer_counts": dict(sorted(source_layer_counts.items())),
        "capability_floors": capability_floors,
        "duckdb_table_row_counts": dict(sorted(table_row_counts.items())),
        "artifact_size_profile": dict(sorted(artifact_size_profile.items())),
        "performance_budget": dict(performance_budget),
        "incremental": dict(incremental),
    }


def build_manifest(
    *,
    config: CapabilityIndexCompilerConfig,
    generated_at: str,
    input_fingerprints: Mapping[str, Any],
    logical_digest: str,
    table_row_counts: Mapping[str, int],
    artifact_size_profile: Mapping[str, int],
    incremental: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the signed manifest metadata."""

    return {
        "schema_version": "policyos.capability_index.manifest.v1",
        "compiler_version": CAPABILITY_INDEX_COMPILER_VERSION,
        "compiler_module": "polisyos.runtime.quality.capability_index_compiler",
        "mode": config.mode,
        "generated_at": generated_at,
        "release_refs": {
            "capability_index_ref": CAPABILITY_INDEX_RELEASE_REF,
            "adr_ref": "ADR-0174",
            "schema_version": CAPABILITY_INDEX_SCHEMA_VERSION,
        },
        "input_fingerprints": input_fingerprints,
        "outputs": {
            "primary_duckdb": CAPABILITY_INDEX_DUCKDB,
            "logical_duckdb_sha256": logical_digest,
            "summary": CAPABILITY_INDEX_SUMMARY,
            "manifest": CAPABILITY_INDEX_MANIFEST,
            "sha256": CAPABILITY_INDEX_SHA256,
            "dcat": CAPABILITY_INDEX_DCAT,
            "prov": CAPABILITY_INDEX_PROV,
            "white_space_report": CAPABILITY_WHITE_SPACE_REPORT,
            "conflict_report": CAPABILITY_CONFLICT_REPORT,
        },
        "duckdb_table_row_counts": dict(sorted(table_row_counts.items())),
        "artifact_size_profile": dict(sorted(artifact_size_profile.items())),
        "incremental": dict(incremental),
        "signature": {
            "algorithm": "sha256",
            "scope": "logical_duckdb_content",
            "digest": logical_digest,
        },
    }


def build_conflict_report(conflicts: Sequence[CapabilityConflictRecord]) -> dict[str, Any]:
    """Build the conflict report, including empty reports."""

    return {
        "schema_version": "policyos.capability_conflict_report.v1",
        "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
        "w8e_conflict_records": [conflict.model_dump(mode="json") for conflict in conflicts],
    }


def build_white_space_report(
    white_space: Sequence[FailureModeNode],
    acquisition_strategies: Sequence[AcquisitionStrategy],
) -> dict[str, Any]:
    """Build construct white-space and acquisition report."""

    return build_grouped_capability_white_space_report(
        failure_modes=white_space,
        acquisition_strategies=acquisition_strategies,
    )


def build_dcat_projection(capability_index: CapabilityIndex) -> dict[str, Any]:
    """Build a compact DCAT-compatible projection."""

    return {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
        },
        "@type": "dcat:Catalog",
        "dct:title": "PolicyOS Policy Evidence Capability Index",
        "dct:identifier": capability_index.release_ref,
        "dcat:dataset": [
            {
                "@id": capability.capability_id,
                "@type": "dcat:Dataset",
                "dct:title": capability.construct_id,
                "dct:type": list(capability.modality),
                "dct:spatial": capability.scope.geography,
                "dct:conformsTo": capability.schema_version,
            }
            for capability in capability_index.capabilities[:500]
        ],
    }


def build_prov_projection(capability_index: CapabilityIndex) -> str:
    """Build a compact PROV-O Turtle projection."""

    lines = [
        "@prefix prov: <http://www.w3.org/ns/prov#> .",
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "",
        f"<urn:policyos:{capability_index.release_ref}> a prov:Entity ;",
        f'  dct:identifier "{capability_index.release_ref}" .',
        "",
    ]
    for capability in capability_index.capabilities[:500]:
        lines.append(f"<urn:policyos:{capability.capability_id}> a prov:Entity ;")
        lines.append(f'  dct:title "{_ttl_escape(capability.construct_id)}" ;')
        lines.append(f"  prov:wasDerivedFrom <urn:policyos:{capability_index.release_ref}> .")
        lines.append("")
    return "\n".join(lines)


def write_phase1_architecture_profile(
    summary_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Write the committed Phase 1 artifact profile under architecture/."""

    summary = _load_json(summary_path)
    payload = {
        "schema_version": PHASE1_ARTIFACT_PROFILE_SCHEMA_VERSION,
        "source_summary_ref": f"repo://{_repo_relative_ref(summary_path)}",
        "full_mode_capability_floors": FULL_MODE_CAPABILITY_FLOORS,
        "duckdb_table_row_counts": summary["duckdb_table_row_counts"],
        "artifact_size_profile": summary["artifact_size_profile"],
        "performance_budget": {
            mode: {"budget_seconds": seconds}
            for mode, seconds in sorted(PERFORMANCE_BUDGET_SECONDS.items())
        },
        "observed_modality_counts": summary["modality_counts"],
    }
    _write_json(output_path, payload)
    return payload


def create_capability_index_fixture_inputs(production_data_root: Path) -> Path:
    """Create tiny L1-L7 test assets matching production-data shapes."""

    root = production_data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    _create_fixture_dataset_catalog(root)
    _create_fixture_scholar_kg(root)
    _create_fixture_lex_kg(root)
    _create_fixture_ukraine_panels(root)
    _create_fixture_calibration_registries(root)
    _create_fixture_foundry_manifest(root)
    _create_fixture_l7_contracts(root)
    return root


def deterministic_capability_id(*parts: str) -> str:
    """Return a deterministic capability ID from semantic parts."""

    semantic = "__".join(_slug(part) for part in parts if part)
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"capability:{semantic}__{digest}"


def deterministic_record_id(prefix: str, *parts: str) -> str:
    """Return a deterministic graph record ID."""

    semantic = ":".join(_slug(part) for part in parts if part)
    digest = hashlib.sha256("|".join((prefix, *parts)).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}:{semantic}:{digest}"


def _copy_previous_incremental_outputs(
    *,
    config: CapabilityIndexCompilerConfig,
    output_dir: Path,
    generated_at: str,
    input_fingerprints: Mapping[str, Any],
    previous_manifest: Mapping[str, Any],
    started: float,
) -> CapabilityIndexBuildResult:
    previous_dir = Path(config.previous_manifest_path).resolve().parent  # type: ignore[arg-type]
    for filename in CAPABILITY_INDEX_OUTPUT_FILENAMES:
        source = previous_dir / filename
        target = output_dir / filename
        if filename in {CAPABILITY_INDEX_MANIFEST, CAPABILITY_INDEX_SUMMARY}:
            continue
        if source.exists():
            shutil.copy2(source, target)
    elapsed = time.perf_counter() - started
    performance_budget = _performance_budget("incremental", elapsed)
    previous_summary = _load_json(previous_dir / CAPABILITY_INDEX_SUMMARY)
    table_row_counts = previous_summary["duckdb_table_row_counts"]
    artifact_size_profile = _artifact_size_profile(
        output_dir,
        filenames=CAPABILITY_INDEX_SIGNED_SIZE_FILENAMES,
    )
    incremental = {
        "previous_manifest_ref": _relative_path(
            Path(config.previous_manifest_path), Path(config.previous_manifest_path).parent
        )
        if config.previous_manifest_path
        else None,
        "changed_input_labels": [],
        "changed_input_count": 0,
        "rebuilt_input_labels": [],
        "rebuild_strategy": "reuse_previous_outputs",
        "reused_previous_index": True,
    }
    summary = dict(previous_summary)
    summary["mode"] = "incremental"
    summary["performance_budget"] = performance_budget
    summary["incremental"] = incremental
    summary["artifact_size_profile"] = artifact_size_profile
    logical_digest = str(previous_manifest["outputs"]["logical_duckdb_sha256"])
    manifest = build_manifest(
        config=config,
        generated_at=generated_at,
        input_fingerprints=input_fingerprints,
        logical_digest=logical_digest,
        table_row_counts=table_row_counts,
        artifact_size_profile=artifact_size_profile,
        incremental=incremental,
    )
    _write_json(output_dir / CAPABILITY_INDEX_SUMMARY, summary)
    _write_json(output_dir / CAPABILITY_INDEX_MANIFEST, manifest)
    return CapabilityIndexBuildResult(
        output_dir=output_dir,
        primary_duckdb_path=output_dir / CAPABILITY_INDEX_DUCKDB,
        manifest_path=output_dir / CAPABILITY_INDEX_MANIFEST,
        sha256_path=output_dir / CAPABILITY_INDEX_SHA256,
        summary_path=output_dir / CAPABILITY_INDEX_SUMMARY,
        dcat_path=output_dir / CAPABILITY_INDEX_DCAT,
        prov_path=output_dir / CAPABILITY_INDEX_PROV,
        white_space_report_path=output_dir / CAPABILITY_WHITE_SPACE_REPORT,
        conflict_report_path=output_dir / CAPABILITY_CONFLICT_REPORT,
        summary=summary,
        manifest=manifest,
    )


def _incremental_state(
    previous_manifest: Mapping[str, Any] | None,
    input_fingerprints: Mapping[str, Any],
) -> dict[str, Any]:
    if not previous_manifest:
        return {
            "previous_manifest_ref": None,
            "changed_input_labels": sorted(input_fingerprints),
            "changed_input_count": len(input_fingerprints),
            "rebuilt_input_labels": sorted(input_fingerprints),
            "rebuild_strategy": "full_input_scan",
            "reused_previous_index": False,
        }
    previous = previous_manifest.get("input_fingerprints") or {}
    changed = [
        label
        for label, fingerprint in sorted(input_fingerprints.items())
        if previous.get(label, {}).get("group_digest") != fingerprint.get("group_digest")
    ]
    return {
        "previous_manifest_ref": previous_manifest.get("outputs", {}).get("manifest"),
        "changed_input_labels": changed,
        "changed_input_count": len(changed),
        "rebuilt_input_labels": _incremental_rebuild_labels(changed),
        "rebuild_strategy": "changed_input_dependency_closure",
        "reused_previous_index": False,
    }


def _build_firm_fundamentals_capability(
    by_family: Mapping[str, ParquetProfile],
    *,
    calibration_context: CalibrationContext,
    foundry_context: FoundryRouteContext,
    production_data_root: Path,
) -> EvidenceCapability:
    firm = by_family["dps_financials"]
    source_family = "firm_fundamentals"
    construct = _construct_from_family(source_family)
    coverage = calibration_context.coverage_rules.get(source_family, 0.8)
    source_assets = [_source_asset_from_parquet(firm, role="firm_fundamentals")]
    for family, role in (
        ("distress_events", "derived_outcome_signal"),
        ("dps_tax_risk", "distress_proxy"),
        ("survival_hazard_estimates", "proxy_validation"),
        ("corrected_firm_panels", "bias_correction"),
    ):
        if family in by_family:
            source_assets.append(_source_asset_from_parquet(by_family[family], role=role))
    source_assets.extend(calibration_context.source_assets)
    method_targets = foundry_context.targets_by_family.get("firm_fundamentals", ())
    breakdown = {
        "coverage": _score(coverage, default=0.8),
        "schema_profile_present": 1.0,
        "variable_alignment_confidence": 0.85,
        "freshness": 0.8,
        "construct_validity": 0.65 if "survival_hazard_estimates" in by_family else 0.45,
        "parser_readiness": 1.0,
    }
    return EvidenceCapability(
        capability_id=deterministic_capability_id(
            construct,
            "fabric_data",
            "ua",
            "firm_fundamentals",
            "survival_hazard_estimates",
        ),
        construct=construct,
        modality=("fabric_data", "derived"),
        evidence_mode="derived_administrative_with_proxy_validation",
        concept_spine_refs=(f"concept:{construct}", "concept:registered_firm"),
        scope=CapabilityScope(
            geography="UA",
            time_start="2022-02-01",
            schema_regime=calibration_context.schema_regime,
            population="registered_firms",
            entity_scope="firm",
        ),
        identification_mode=calibration_context.identification_modes.get(
            source_family, "point_identified"
        ),
        trust_tier=_trust_tier_for_coverage(coverage),
        quality_score=QualityScore(
            composite=_mean_score(breakdown.values()),
            breakdown=breakdown,
        ),
        source_assets=tuple(source_assets),
        method_contract_targets=method_targets,
        proxy_validation={
            "construct_validity_status": "proxy_validated"
            if "survival_hazard_estimates" in by_family
            else "proxy_unvalidated",
            "validated_by": [
                asset.ref
                for asset in source_assets
                if asset.role in {"proxy_validation", "bias_correction"}
            ],
        },
        limitations=(
            "Excludes informal-sector firms not represented in the EDR registry.",
            "Survival event is derived from distress signals, not direct firm-closure registry.",
        ),
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible_with_proxy_limitation",
            production="blocked_construct_validity_below_floor",
            authoritative_for=("firm_outcome_signal", "governed_pilot_data_evidence"),
            may_not_use_for=("production_closeout_without_construct_validity_review",),
            authority_basis=("L4 Ukraine panels", "L5 calibration registries", "L6 Foundry route"),
        ),
        lineage_refs=(
            f"source_snapshot:{_release_ref_from_path(firm.path)}",
            "calibration_run:d2",
            "calibration_run:d3",
        ),
        freshness_envelope=FreshnessEnvelope(
            freshness_class="fresh_for_governed_pilot",
            source_release_ref=_release_ref_from_path(firm.path),
        ),
        rights_envelope=RightsEnvelope(
            access_class="government_administrative",
            public_export_allowed="aggregate_only",
            restrictions=("no_row_level_public_export",),
        ),
        may_not_use_for=("public_row_level_export",),
        metadata={
            "input_groups": (
                "l4_ukraine_panels",
                "l5_calibration_registries",
                "l6_foundry_method_contracts",
            ),
            "row_count": firm.row_count,
            "production_data_root": production_data_root.name,
        },
    )


def _build_fixture_conflicting_capability(
    reference: EvidenceCapability | None = None,
) -> EvidenceCapability:
    construct = (
        reference.construct_id
        if reference is not None
        else _construct_from_text("fixture conflict")
    )
    scope = (
        reference.scope
        if reference is not None
        else CapabilityScope(geography="UA", entity_scope="firm")
    )
    return EvidenceCapability(
        capability_id=deterministic_capability_id(
            construct,
            "fabric_data",
            "fixture_conflict",
        ),
        construct=construct,
        modality=("fabric_data",),
        evidence_mode="context_only",
        concept_spine_refs=(f"concept:{construct}",),
        scope=scope,
        identification_mode="context_only",
        trust_tier="weak_anchor",
        quality_score=QualityScore(composite=0.25, breakdown={"context": 0.25}),
        source_assets=(
            CapabilitySourceAsset(
                ref=f"fixture:conflicting_{construct}_context",
                source_layer="L4",
                asset_type="synthetic_test_fixture",
                role="conflict_fixture",
            ),
        ),
        authority_envelope=AuthorityEnvelope(
            research="admissible_as_context",
            governed_pilot="blocked_context_only",
            production="blocked_context_only",
            authoritative_for=("conflict_fixture",),
            may_not_use_for=("production_claim_evidence",),
        ),
        freshness_envelope=FreshnessEnvelope(freshness_class="fixture"),
        rights_envelope=RightsEnvelope(access_class="fixture"),
        metadata={"input_groups": ("l4_ukraine_panels",), "force_conflict": True},
    )


def _profile_ukraine_parquets(production_data_root: Path) -> tuple[ParquetProfile, ...]:
    profiles = []
    for path in (
        *_l4_ukraine_panel_paths(production_data_root),
        *_l5_derived_parquet_paths(production_data_root),
    ):
        family = path.parent.name
        source_layer = "L4"
        if path.stem == "survival_hazard_estimates":
            family = "survival_hazard_estimates"
            source_layer = "L5"
        elif path.stem == "corrected_firm_panels":
            family = "corrected_firm_panels"
            source_layer = "L5"
        try:
            parquet = pq.ParquetFile(path)
        except (OSError, pa.ArrowInvalid):
            continue
        profiles.append(
            ParquetProfile(
                family=family,
                path=path,
                relative_path=_relative_path(path, production_data_root),
                source_layer=source_layer,
                row_count=int(parquet.metadata.num_rows),
                row_group_count=int(parquet.metadata.num_row_groups),
                fields=tuple(parquet.schema.names),
            )
        )
    return tuple(profiles)


def _source_asset_from_parquet(profile: ParquetProfile, *, role: str) -> CapabilitySourceAsset:
    return CapabilitySourceAsset(
        ref=f"parquet:{profile.family}/{profile.path.stem}",
        source_layer=profile.source_layer,
        asset_type="parquet_metadata_profile",
        role=role,
        path=profile.relative_path,
        row_count=profile.row_count,
        fields=profile.fields,
        metadata={"row_groups": profile.row_group_count},
    )


def _fingerprint_path(path: Path, root: Path) -> dict[str, Any]:
    relative = _relative_path(path, root)
    stat = path.stat()
    if path.suffix == ".duckdb":
        digest = _duckdb_schema_count_digest(path)
        hash_status = "logical_schema_count_hash"
    elif path.suffix == ".parquet":
        digest = _parquet_metadata_digest(path)
        hash_status = "parquet_metadata_hash"
    elif path.suffix == ".json":
        digest = _sha256_json(_load_json(path))
        hash_status = "canonical_json_hash"
    else:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hash_status = "sha256"
    return {
        "path": relative,
        "size_bytes": stat.st_size,
        "fingerprint": digest,
        "hash_status": hash_status,
    }


def _duckdb_schema_count_digest(path: Path) -> str:
    with duckdb.connect(str(path), read_only=True) as con:
        payload = {}
        for table in sorted(_show_tables(con)):
            columns = [row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()]
            count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            payload[table] = {"columns": columns, "row_count": int(count)}
    return _sha256_json(payload)


def _parquet_metadata_digest(path: Path) -> str:
    parquet = pq.ParquetFile(path)
    payload = {
        "row_count": parquet.metadata.num_rows,
        "row_group_count": parquet.metadata.num_row_groups,
        "fields": parquet.schema.names,
    }
    return _sha256_json(payload)


def _create_fixture_dataset_catalog(root: Path) -> None:
    path = root / "datasets_full_phase3full_20260327_183054" / "dataset_catalog.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with duckdb.connect(str(path)) as con:
        con.execute(
            """
            CREATE TABLE ds_datasets (
                id VARCHAR,
                source VARCHAR,
                agency VARCHAR,
                dataset_id VARCHAR,
                source_dataset_id VARCHAR,
                dedup_key VARCHAR,
                title VARCHAR,
                description VARCHAR,
                publisher VARCHAR,
                spatial VARCHAR,
                temporal_start VARCHAR,
                temporal_end VARCHAR,
                license VARCHAR,
                source_portal VARCHAR,
                execution_tier VARCHAR,
                update_frequency VARCHAR,
                last_updated VARCHAR,
                polisyos_metrics VARCHAR,
                keywords VARCHAR,
                themes VARCHAR,
                variables VARCHAR,
                formats VARCHAR,
                coverage_countries VARCHAR,
                coverage_regions VARCHAR,
                coverage_time_start VARCHAR,
                coverage_time_end VARCHAR,
                coverage_granularity VARCHAR,
                access_api_endpoint VARCHAR,
                access_bulk_download_url VARCHAR,
                access_license VARCHAR,
                access_auth_required BOOLEAN,
                quality_description_score DOUBLE,
                quality_machine_readable_score DOUBLE,
                quality_parser_support_score DOUBLE,
                quality_freshness_score DOUBLE,
                quality_execution_readiness_score DOUBLE,
                preferred_distribution_id VARCHAR,
                updated_at VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ds_datasets VALUES
            (
                'dataset:ua-firm-fundamentals', 'data_gov_ua_exec', 'DPS',
                'ua_firm_fundamentals', 'ua_firm_fundamentals', 'ua_firm_fundamentals',
                'Ukraine firm fundamentals annual panel',
                'Firm revenue assets liabilities employees',
                'State Tax Service of Ukraine', 'UA', '2022-02-01', NULL,
                'restricted_government', 'fixture', 'ready', 'annual', '2026-05-01',
                'fixture_survival', 'firm,msme', 'economy', 'revenue,assets,employees',
                'parquet', 'UA', NULL, '2022-02-01', NULL, 'annual', NULL, NULL,
                'restricted_government', false, 0.9, 1.0, 1.0, 0.8, 0.9,
                'distribution:ua-firm-fundamentals', '2026-05-25'
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ds_distributions (
                id VARCHAR,
                dataset_id VARCHAR,
                url VARCHAR,
                format VARCHAR,
                name VARCHAR,
                connector_type VARCHAR,
                connector_params VARCHAR,
                source_locator VARCHAR,
                profile_id VARCHAR,
                media_type VARCHAR,
                machine_readable BOOLEAN,
                parser_supported BOOLEAN,
                size_estimate_bytes BIGINT,
                checksum VARCHAR,
                default_filters VARCHAR,
                quality_score DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO ds_distributions VALUES
            (
                'distribution:ua-firm-fundamentals', 'ua_firm_fundamentals',
                'fixture://firm_fundamentals_annual.parquet', 'parquet',
                'firm_fundamentals_annual.parquet', 'parquet', '{}',
                'dps_financials/firm_fundamentals_annual.parquet', 'schema:firm',
                'application/vnd.apache.parquet', true, true, 1000, NULL, '{}', 0.95
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ds_metric_bindings (
                metric_id VARCHAR,
                dataset_id VARCHAR,
                distribution_id VARCHAR,
                connector_id VARCHAR,
                profile_id VARCHAR,
                request_dataset_id VARCHAR,
                confidence DOUBLE,
                metric_inference_confidence DOUBLE,
                default_filters VARCHAR,
                execution_tier VARCHAR,
                source VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ds_metric_bindings VALUES
            (
                'fixture_survival', 'ua_firm_fundamentals',
                'distribution:ua-firm-fundamentals', 'parquet', 'schema:firm',
                'ua_firm_fundamentals', 0.86, 0.84, '{}', 'ready', 'fixture'
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ds_schema_profiles (
                distribution_id VARCHAR,
                dataset_id VARCHAR,
                columns_json VARCHAR,
                inferred_time_column VARCHAR,
                inferred_geography_column VARCHAR,
                inferred_value_columns VARCHAR,
                sample_row_count INTEGER,
                preview_sample_hash VARCHAR,
                inference_mode VARCHAR,
                parser_mode VARCHAR,
                format_notes_json VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ds_schema_profiles VALUES
            (
                'distribution:ua-firm-fundamentals', 'ua_firm_fundamentals',
                '["agent_id","period_id","revenue","employees"]',
                'period_id', 'region_code', '["revenue","employees"]',
                3, 'fixture-hash', 'fixture', 'parquet', '{}'
            )
            """
        )
        con.execute(
            """
            CREATE TABLE ds_variable_alignments (
                dataset_id VARCHAR,
                raw_variable VARCHAR,
                canonical_var VARCHAR,
                method VARCHAR,
                confidence DOUBLE,
                evidence VARCHAR,
                is_proxy BOOLEAN,
                proxy_penalty DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO ds_variable_alignments VALUES
            ('ua_firm_fundamentals', 'employees', 'firm_size', 'fixture', 0.9, 'fixture', false, 0.0)
            """
        )


def _create_fixture_scholar_kg(root: Path) -> None:
    path = (
        root
        / "policyos_academic_runtime_slim_20260411T112032Z"
        / "academic/graph/scholar_knowledge.duckdb"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with duckdb.connect(str(path)) as con:
        con.execute(
            """
            CREATE TABLE ac_skg_edges (
                edge_id VARCHAR, src VARCHAR, dst VARCHAR, direction VARCHAR,
                n_articles INTEGER, article_refs VARCHAR, evidence_strength DOUBLE,
                confidence DOUBLE, scope_conditions VARCHAR, meta_effect_size DOUBLE,
                candidate_layer VARCHAR, quality_signals_json VARCHAR, updated_ts VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_edges VALUES
            ('edge:fixture_cause:fixture_effect', 'fixture_cause', 'fixture_effect',
             'positive', 2, '["work:1"]', 0.8, 0.82, 'wartime firms', 0.2,
             'runtime', '{}', '2026-05-25')
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_transport_scores (
                transport_id VARCHAR, edge_id VARCHAR, target_context_id VARCHAR,
                base_confidence DOUBLE, generic_penalty DOUBLE, context_match_reward DOUBLE,
                transport_confidence DOUBLE, match_mode VARCHAR, matched_moderators_json VARCHAR,
                skg_version VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_transport_scores VALUES
            ('transport:1', 'edge:fixture_cause:fixture_effect', 'UA-wartime',
             0.82, 0.1, 0.12, 0.84, 'context_match', '{}', 'fixture')
            """
        )
        con.execute(
            """
            CREATE TABLE ac_skg_contested_edges (
                contested_edge_id VARCHAR, src_family VARCHAR, dst_family VARCHAR,
                n_articles INTEGER, n_claims INTEGER, article_refs VARCHAR, claim_refs VARCHAR,
                dominant_direction VARCHAR, resolution_status VARCHAR, runtime_support VARCHAR,
                evidence_strength DOUBLE, confidence DOUBLE, positive_weight DOUBLE,
                negative_weight DOUBLE, mixed_weight DOUBLE, dominant_direction_agreement DOUBLE,
                strongest_dissent_strength DOUBLE, strongest_dissent_year INTEGER,
                direction_histogram_json VARCHAR, quality_signals_json VARCHAR, updated_ts VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_skg_contested_edges VALUES
            ('contested:1', 'fixture_cause', 'fixture_effect', 2, 2, '[]', '[]',
             'positive', 'resolved', 'supportive', 0.8, 0.82, 0.8, 0.1, 0.1,
             0.8, 0.1, 2024, '{}', '{}', '2026-05-25')
            """
        )
        con.execute(
            """
            CREATE TABLE ac_parameter_estimates (
                id VARCHAR, work_id VARCHAR, variable_name VARCHAR, estimate DOUBLE,
                ci_low DOUBLE, ci_high DOUBLE, std_error DOUBLE, unit VARCHAR, domain VARCHAR,
                study_design VARCHAR, sample_size INTEGER, country VARCHAR, period_start VARCHAR,
                period_end VARCHAR, trust_score DOUBLE, raw_context VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_parameter_estimates VALUES
            ('parameter:1', 'work:1', 'fixture_effect', 0.2, 0.1, 0.3, 0.01,
             'effect_ratio', 'fixture_domain', 'quasi_experimental', 1000, 'UA',
             '2022', '2024', 0.78, '{}')
            """
        )
        con.execute(
            """
            CREATE TABLE ac_boundary_conditions (
                boundary_id VARCHAR, work_id VARCHAR, variable VARCHAR, operator VARCHAR,
                threshold_value DOUBLE, scope_text VARCHAR, confidence DOUBLE
            )
            """
        )
        con.execute(
            """
            INSERT INTO ac_boundary_conditions VALUES
            ('boundary:1', 'work:1', 'fixture_effect', '>=', 0.0, 'registered firms', 0.75)
            """
        )


def _create_fixture_lex_kg(root: Path) -> None:
    path = root / "lex/lex-amendment-only-optimized-20260501-v3/finalize/lex_knowledge_graph.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    with duckdb.connect(str(path)) as con:
        con.execute(
            """
            CREATE TABLE lex_rule_thresholds (
                threshold_id VARCHAR, fact_id VARCHAR, metric VARCHAR, operator VARCHAR,
                value_decimal DOUBLE, value_text VARCHAR, unit VARCHAR, applies_to VARCHAR,
                metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_rule_thresholds VALUES
            ('threshold:msme:employees', 'fact:msme-eligibility', 'employee_count',
             '<=', 250, '250', 'persons', 'msme_eligibility', '{}', '2026-05-25')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_normative_facts (
                fact_id VARCHAR, statement_id VARCHAR, subject_id VARCHAR, predicate VARCHAR,
                object_id VARCHAR, fact_text VARCHAR, confidence DOUBLE, norm_type VARCHAR,
                action_canon VARCHAR, norm_type_canon VARCHAR, subject_en VARCHAR, subject_uk VARCHAR,
                object_en VARCHAR, object_uk VARCHAR, condition_text_uk VARCHAR,
                exception_text_uk VARCHAR, procedure_text_uk VARCHAR, temporal_text_uk VARCHAR,
                sanction_text_uk VARCHAR, source_quote_uk VARCHAR, source_quote_start INTEGER,
                source_quote_end INTEGER, thresholds_json VARCHAR, trust_tier VARCHAR,
                grounding_status VARCHAR, canonical_status VARCHAR, reference_resolution_status VARCHAR,
                structure_quality DOUBLE, constraint_type_canon VARCHAR, legal_unit_subtype VARCHAR,
                route_class VARCHAR, empty_spo_retry_eligible BOOLEAN, audit_miss_prone BOOLEAN,
                reference_bearing BOOLEAN, threshold_bearing BOOLEAN, fused_confidence DOUBLE,
                confidence_breakdown_json VARCHAR, consistency_score DOUBLE,
                hallucination_flags_json VARCHAR, quality_band VARCHAR, doc_id VARCHAR,
                doc_reestr_code VARCHAR, doc_name VARCHAR, doc_type VARCHAR, doc_date_acc VARCHAR,
                doc_status VARCHAR, jurisdiction VARCHAR, top_domain VARCHAR, doc_family_id VARCHAR,
                version_id VARCHAR, provision_anchor VARCHAR, provision_citation VARCHAR,
                effective_from VARCHAR, effective_to VARCHAR, temporal_state VARCHAR,
                temporal_resolution_status VARCHAR, temporal_source_scope VARCHAR,
                temporal_source_kind VARCHAR, temporal_confidence DOUBLE,
                temporal_provenance_json VARCHAR, extraction_source VARCHAR, gate_score DOUBLE,
                gate_reason_codes VARCHAR, metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            """
            INSERT INTO lex_normative_facts VALUES
            ('fact:msme-eligibility', 'statement:1', 'entity:ministry', 'defines',
             'entity:msme', 'MSME eligibility threshold', 0.9, 'eligibility',
             'define', 'eligibility', 'Ministry', 'Міністерство', 'MSME', 'МСП',
             NULL, NULL, NULL, NULL, NULL, 'quote', 0, 5, '{}',
             'high_confidence_norm', 'grounded', 'canonical', 'resolved', 0.9,
             'threshold', 'article', 'legal_authority', false, false, true, true,
             0.9, '{}', 0.9, '{}', 'high', 'doc:1', '123', 'MSME Law',
             'law', '2022-01-01', 'active', 'UA', 'economy', 'docfam:1',
             'version:1', '1', 'Art. 1', '2022-02-01', NULL, 'effective',
             'resolved', 'document', 'explicit', 0.9, '{}', 'fixture', 0.9,
             '[]', '{}', '2026-05-25')
            """
        )
        con.execute(
            """
            CREATE TABLE lex_temporal_audit (
                audit_id VARCHAR, scope VARCHAR, doc_id VARCHAR, fact_id VARCHAR,
                temporal_state VARCHAR, temporal_resolution_status VARCHAR,
                issue_type VARCHAR, evidence_text_uk VARCHAR, metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_temporal_audit VALUES ('audit:1','fact','doc:1','fact:msme-eligibility','effective','resolved',NULL,'evidence','{}','2026-05-25')"
        )
        con.execute(
            """
            CREATE TABLE lex_references (
                reference_id VARCHAR, doc_id VARCHAR, provision_anchor VARCHAR,
                source_span_start INTEGER, source_span_end INTEGER, target_raw VARCHAR,
                ref_type VARCHAR, confidence DOUBLE, metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_references VALUES ('ref:1','doc:1','1',0,10,'target','law',0.8,'{}','2026-05-25')"
        )
        con.execute(
            """
            CREATE TABLE lex_entities (
                entity_id VARCHAR, name_en VARCHAR, name_uk VARCHAR, entity_type VARCHAR,
                entity_subtype VARCHAR, mention_count INTEGER, aliases_en VARCHAR, aliases_uk VARCHAR,
                wikidata_id VARCHAR, metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_entities VALUES ('entity:ministry','Ministry','Міністерство','agency','state',1,'[]','[]',NULL,'{}','2026-05-25')"
        )
        con.execute(
            """
            CREATE TABLE lex_amendments (
                amendment_id VARCHAR, amending_doc_id VARCHAR, amended_doc_id VARCHAR,
                target_resolution_expected BOOLEAN, amendment_type VARCHAR, target_anchor VARCHAR,
                old_text_uk VARCHAR, new_text_uk VARCHAR, effective_from VARCHAR,
                detected_by VARCHAR, confidence DOUBLE, metadata VARCHAR, created_at VARCHAR
            )
            """
        )
        con.execute(
            "INSERT INTO lex_amendments VALUES ('amendment:1','doc:2','doc:1',true,'update','1','old','new','2022-02-01','fixture',0.8,'{}','2026-05-25')"
        )


def _create_fixture_ukraine_panels(root: Path) -> None:
    base = (
        root
        / "canonical/local_data_20260501/ukraine_server_support_20260410"
        / "normalized_corpus/normalized"
    )
    _write_parquet(
        base / "dps_financials/firm_fundamentals_annual.parquet",
        {
            "agent_id": [1, 2],
            "registration_code": ["a", "b"],
            "period_id": ["2022", "2023"],
            "revenue": [100.0, 120.0],
            "assets": [80.0, 90.0],
            "liabilities": [20.0, 30.0],
            "employees": [10, 12],
            "source_snapshot_id": ["fixture", "fixture"],
            "schema_version": ["v1", "v1"],
            "record_hash": ["h1", "h2"],
        },
    )
    _write_parquet(
        base / "distress_events/distress_events_panel_monthly.parquet",
        {
            "agent_id": [1],
            "period_id": ["2022-03"],
            "event_count": [1],
            "event_flag": [True],
            "region_code": ["UA-30"],
        },
    )
    _write_parquet(
        base / "dps_tax_risk/compliance_distress_signals_monthly.parquet",
        {
            "agent_id": [1],
            "period_id": ["2022-03"],
            "tax_debt": [10.0],
            "risk_score": [0.7],
        },
    )
    d3 = (
        root
        / "canonical/local_data_20260501/ukraine_server_support_20260410"
        / "runtime_calibration_internals/calibration/d3"
    )
    _write_parquet(
        d3 / "survival_hazard_estimates.parquet",
        {"duration": [1.0], "event": [1], "risk_signal": [0.8], "wage_arrears": [0.0]},
    )
    _write_parquet(
        d3 / "corrected_firm_panels.parquet",
        {
            "registration_code": ["a"],
            "period_id": ["2022"],
            "arrears_amount": [0.0],
            "debt_amount": [0.0],
            "region_code": ["UA-30"],
            "agent_id": [1],
            "source_snapshot_id": ["fixture"],
            "schema_version": ["v1"],
            "record_hash": ["h1"],
            "selection_term": [0.1],
            "corrected_exit_bias": [0.2],
        },
    )
    _write_parquet(
        base / "logistics_mobility_displacement/transport_pressure_monthly.parquet",
        {
            "cell_id": ["c1"],
            "region_code": ["UA-30"],
            "mobility_pressure": [0.4],
            "period_id": ["2022-03"],
        },
    )


def _create_fixture_calibration_registries(root: Path) -> None:
    base = (
        root
        / "canonical/local_data_20260501/ukraine_server_support_20260410"
        / "runtime_calibration_internals/calibration/d2"
    )
    base.mkdir(parents=True, exist_ok=True)
    _write_json(
        base / "measurement_registry.json",
        {
            "schema_version": "1.0",
            "coverage_rules": {
                "firm_fundamentals": 0.8,
                "logistics_friction": 0.7,
            },
            "proxy_mappings": {"logistics_friction": ["regional_displacement_pressure"]},
            "trust_tiers": {"authoritative_partial_coverage": "fixture"},
        },
    )
    _write_json(
        base / "identification_mode_registry.json",
        {
            "firm_fundamentals": {"selected_mode": "point_identified"},
            "logistics_friction": {"selected_mode": "proxy_identified"},
        },
    )
    _write_json(
        base / "schema_regime_registry.json",
        {
            "schema_version": "1.0",
            "regimes": {"ukraine_schema_v2": {"effective_from": "2022-02-01"}},
            "changepoints": [],
        },
    )
    _write_json(
        base / "governance_pass_mapping_v1.json",
        {"firm_fundamentals": ["refutation", "freshness"], "logistics_friction": ["freshness"]},
    )


def _create_fixture_foundry_manifest(root: Path) -> None:
    path = (
        root
        / "ukraine_agent_simulation_baseline_20260410/production_bundle/bundles"
        / "method_contract_bundle_v1/observation_to_contract_manifest.json"
    )
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "artifact_name": "observation_to_contract_manifest.json",
            "artifacts": [],
            "routes": [
                {
                    "family": "firm_fundamentals",
                    "identification_mode": "point_identified",
                    "notes": [],
                    "target_contract": {
                        "contract_fqn": (
                            "polisyos.foundry.methods.catalog.ml.protocols.SurvivalData"
                        ),
                        "contract_id": "foundry.ml.survival_data.v1",
                    },
                }
            ],
        },
    )


def _create_fixture_l7_contracts(root: Path) -> None:
    path = root / "canonical/local_data_20260501/policy_engine_data/curated/data_contracts.json"
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "generated_at": "2026-01-15T10:00:00Z",
            "generated_by": "manual",
            "contracts": [
                {
                    "metric_id": "us.macro.gdp_nominal",
                    "display_name": "Nominal GDP",
                    "jurisdiction": "US",
                    "source_system": "simulation.duckdb",
                    "source_table": "macro_history",
                    "source_column": "gdp",
                }
            ],
        },
    )
    _write_json(
        path.parent / "source_bindings.json",
        {"schema_version": "1.0", "bindings": []},
    )


def _write_parquet(path: Path, payload: Mapping[str, Sequence[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(payload), path)


def _l4_ukraine_panel_paths(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.glob("**/*.parquet"))
        if _is_ukraine_normalized_panel_path(path, root)
    ]


def _l5_derived_parquet_paths(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.glob("**/*.parquet"))
        if _is_l5_derived_support_path(path, root)
    ]


def _is_ukraine_normalized_panel_path(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return (
        any(part.startswith("ukraine_server_support_") for part in parts)
        and "normalized_corpus" in parts
        and "normalized" in parts
    )


def _is_l5_derived_support_path(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return (
        path.name in L5_DERIVED_PARQUET_NAMES
        and "runtime_calibration_internals" in parts
        and "calibration" in parts
        and "d3" in parts
    )


def _find_first(root: Path, pattern: str) -> Path | None:
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def _show_tables(con: duckdb.DuckDBPyConnection) -> tuple[str, ...]:
    return tuple(row[0] for row in con.execute("SHOW TABLES").fetchall())


def _fetch_dicts(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    result = con.execute(sql, params or [])
    columns = [description[0] for description in result.description]
    return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]


def _duckdb_table_counts(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {
        table: int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in sorted(_show_tables(con))
    }


def _capability_floor_report(
    capabilities: Sequence[EvidenceCapability],
) -> dict[str, dict[str, int | str]]:
    modality_counts: Counter[str] = Counter()
    for capability in capabilities:
        for modality in capability.modality:
            modality_counts[modality] += 1
        if capability.compatibility_only:
            modality_counts["compatibility_only"] += 1
    report = {}
    for modality, minimum in FULL_MODE_CAPABILITY_FLOORS.items():
        observed = modality_counts[modality]
        report[modality] = {
            "minimum": minimum,
            "observed": observed,
            "status": "pass" if observed >= minimum else "fail",
        }
    return report


def _performance_budget(mode: str, elapsed: float) -> dict[str, Any]:
    budget = PERFORMANCE_BUDGET_SECONDS[mode]
    return {
        "mode": mode,
        "elapsed_seconds": round(elapsed, 6),
        "budget_seconds": budget,
        "status": "pass" if elapsed <= budget else "fail",
    }


def _artifact_size_profile(
    output_dir: Path,
    *,
    filenames: Sequence[str] = CAPABILITY_INDEX_OUTPUT_FILENAMES,
) -> dict[str, int]:
    return {
        filename: (output_dir / filename).stat().st_size
        for filename in filenames
        if (output_dir / filename).exists()
    }


def _dedupe_capabilities(
    capabilities: Iterable[EvidenceCapability],
) -> list[EvidenceCapability]:
    by_id: dict[str, EvidenceCapability] = {}
    for capability in capabilities:
        by_id[capability.capability_id] = capability
    return [by_id[key] for key in sorted(by_id)]


def _authority_for_panel(coverage: float, source_family: str) -> AuthorityEnvelope:
    production = "admissible" if coverage >= 0.9 else "blocked_construct_validity_below_floor"
    return AuthorityEnvelope(
        research="admissible",
        governed_pilot="admissible_with_limitation" if coverage >= 0.5 else "blocked_low_coverage",
        production=production,
        authoritative_for=("data_evidence",),
        may_not_use_for=("production_closeout_without_review",)
        if production.startswith("blocked")
        else (),
        authority_basis=(f"L4 panel family {source_family}", "L5 calibration registry"),
    )


def _construct_from_family(family: str) -> str:
    return _construct_from_text(family)


def _construct_from_text(text: str) -> str:
    return _slug(text) or "catalog_dataset"


def _legal_construct(metric: str, applies_to: object) -> str:
    text = f"{metric} {_optional_str(applies_to) or ''}"
    if "employee" in text or "msme" in text:
        return "msme_eligibility"
    return _construct_from_text(text)


def _panel_construct(family: str, fields: Sequence[str]) -> str:
    joined = " ".join((family, *fields))
    return _construct_from_text(joined)


def _source_family_from_panel(family: str) -> str:
    mapping = {
        "dps_financials": "firm_fundamentals",
        "logistics_mobility_displacement": "logistics_friction",
        "distress_events": "distress_enforcement",
        "dps_tax_risk": "distress_enforcement",
    }
    return mapping.get(family, family)


def _entity_scope_from_fields(fields: Sequence[str]) -> str:
    if "agent_id" in fields or "registration_code" in fields:
        return "firm"
    if "household_id" in fields:
        return "household"
    if "cell_id" in fields:
        return "cell_or_region"
    if "region_code" in fields:
        return "region"
    return "panel_entity"


def _trust_tier_for_coverage(coverage: float) -> str:
    if coverage >= 0.85:
        return "authoritative_high_coverage"
    if coverage >= 0.75:
        return "authoritative_partial_coverage"
    if coverage >= 0.55:
        return "administrative_noisy"
    if coverage >= 0.35:
        return "derived_proxy"
    return "weak_anchor"


def _coverage_geography(value: object) -> str:
    text = _optional_str(value)
    if not text:
        return "unspecified"
    if "UA" in text or "Ukraine" in text:
        return "UA"
    if "US" in text:
        return "US"
    return text.split(",")[0].strip("[]'\" ") or "unspecified"


def _score(value: object, *, default: float) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric < 0:
        return 0.0
    if numeric > 1:
        return 1.0
    return numeric


def _mean_score(values: Iterable[float]) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), 6)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_text(value: object) -> str:
    return _optional_str(value) or ""


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value.strip())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _release_ref_from_path(path: Path) -> str:
    parts = path.parts
    for part in parts:
        if part.startswith(
            ("local_data_", "ukraine_server_support_", "datasets_full_", "policyos_", "lex-")
        ):
            return part
    return path.parent.name


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _repo_relative_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ttl_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
