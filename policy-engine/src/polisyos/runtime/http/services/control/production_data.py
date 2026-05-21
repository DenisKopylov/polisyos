"""Production data root discovery and logical bundle path resolution."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

from polisyos.fabric.catalog.source_selection_audit import (
    build_fabric_source_selection_trace,
)
from polisyos.runtime.quality.data_quality import (
    build_production_data_quality_report,
)
from polisyos.runtime.quality.production_data_contract_index import (
    ProductionDataContractIndex,
)

PRODUCTION_DATA_ROOT_ENV = "POLISYOS_PRODUCTION_DATA_ROOT"
PRODUCTION_DATA_MANIFEST_NAME = "manifest.json"


def resolve_production_data_root(
    params: Mapping[str, Any] | None = None,
    *,
    allow_default: bool,
) -> Path | None:
    configured = None
    if params is not None:
        configured = params.get("production_data_root")
    configured = configured or os.getenv(PRODUCTION_DATA_ROOT_ENV)
    if configured:
        path = Path(str(configured)).expanduser()
        if path.exists():
            return path

    if not allow_default:
        return None

    candidates = (Path("production_data"), Path("policy-engine/production_data"))
    for candidate in candidates:
        if (candidate / PRODUCTION_DATA_MANIFEST_NAME).exists():
            return candidate
    return _first_existing_path(*candidates)


def load_production_data_manifest(root: Path) -> Mapping[str, Any]:
    manifest_path = root / PRODUCTION_DATA_MANIFEST_NAME
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, Mapping):
        return {}
    return payload


def production_data_bundle_path(
    role: str,
    *,
    key: str = "path",
    params: Mapping[str, Any] | None = None,
    allow_default: bool,
) -> Path | None:
    root = resolve_production_data_root(params, allow_default=allow_default)
    if root is None:
        return None
    bundle = _manifest_bundle(load_production_data_manifest(root), role)
    return _manifest_path(root, bundle, key)


def production_data_evidence_context(
    params: Mapping[str, Any] | None = None,
    *,
    allow_default: bool,
) -> dict[str, Any] | None:
    root = resolve_production_data_root(params, allow_default=allow_default)
    if root is None:
        return None

    manifest_path = root / PRODUCTION_DATA_MANIFEST_NAME
    manifest = load_production_data_manifest(root)
    raw_bundles = manifest.get("bundles")
    bundles: dict[str, dict[str, Any]] = {}
    if isinstance(raw_bundles, Mapping):
        for role, raw_bundle in sorted(raw_bundles.items()):
            if not isinstance(raw_bundle, Mapping):
                continue
            selected: dict[str, Any] = {}
            for key in (
                "version_id",
                "role",
                "source_family",
                "data_source_family",
                "readiness",
                "path",
                "component_path",
                "dataset_path",
                "data_path",
                "records_path",
                "csv_path",
                "jsonl_path",
                "json_path",
                "parquet_path",
                "manifest_path",
                "catalog_db_path",
                "legal_kg_db_path",
                "academic_db_path",
                "benchmark_suite_path",
                "benchmark_report_path",
                "qc_report_path",
                "data_dictionary_path",
                "schema_path",
                "updated_at",
                "generated_at",
            ):
                value = raw_bundle.get(key)
                if isinstance(value, str) and value.strip():
                    selected[key] = value
            for key in (
                "required_files",
                "artifact_checksums",
                "expected_schema",
                "required_columns",
                "quality_contract",
            ):
                value = raw_bundle.get(key)
                if isinstance(value, Mapping):
                    selected[key] = dict(value)
                elif isinstance(value, list):
                    selected[key] = list(value)
            if selected:
                bundles[str(role)] = selected

    return {
        "root": str(root),
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "manifest_sha256": _file_sha256(manifest_path),
        "generated_at": (
            manifest.get("generated_at") if isinstance(manifest.get("generated_at"), str) else None
        ),
        "bundles": bundles,
    }


def production_data_quality_report(
    *,
    evidence_context: Mapping[str, Any],
    materialization_refs: Mapping[str, Any],
    data_needs: list[Mapping[str, Any]],
    claims: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build runtime production data quality diagnostics from manifest-backed data."""
    root = Path(str(evidence_context.get("root") or "")).expanduser()
    production_root = root if str(root) != "." or evidence_context.get("root") else None
    return build_production_data_quality_report(
        production_data_root=production_root,
        evidence_context=evidence_context,
        materialization_refs=materialization_refs,
        data_needs=data_needs,
        claims=claims,
    )


def production_data_contract_binding_report(
    params: Mapping[str, Any] | None = None,
    *,
    scenario_evidence_contract: Mapping[str, Any],
    allow_default: bool,
) -> dict[str, Any] | None:
    """Bind scenario data obligations against manifest-backed production data."""

    root = resolve_production_data_root(params, allow_default=allow_default)
    if root is None:
        return None
    return ProductionDataContractIndex.load(root).build_scenario_binding_report(
        scenario_evidence_contract
    )


def apply_production_data_defaults(
    params: MutableMapping[str, Any],
    *,
    allow_default: bool,
) -> None:
    root = resolve_production_data_root(params, allow_default=allow_default)
    if root is None:
        return

    params.setdefault("production_data_root", str(root))
    manifest = load_production_data_manifest(root)
    params.setdefault(
        "production_data_evidence_context",
        production_data_evidence_context(params, allow_default=allow_default),
    )

    datasets = _manifest_bundle(manifest, "datasets")
    datasets_dir = _manifest_path(
        root,
        datasets,
        "path",
        fallback=root / "datasets_full_phase3full_20260327_183054",
    )
    datasets_db = _manifest_path(
        root,
        datasets,
        "catalog_db_path",
        fallback=datasets_dir / "dataset_catalog.duckdb" if datasets_dir else None,
    )
    _set_default_existing_path(params, "datasets_snapshot_dir", datasets_dir)
    _set_default_existing_path(params, "datasets_db_path", datasets_db)
    _set_default_existing_path(params, "dataset_registry_db_path", datasets_db)

    lex = _manifest_bundle(manifest, "lex")
    lex_bundle = _existing_param_path(params, "lex_bundle_dir")
    if lex_bundle is None:
        lex_bundle = _manifest_path(root, lex, "path")
    if lex_bundle is None:
        lex_bundle = _first_child_with(root / "lex", "finalize/lex_knowledge_graph.duckdb")
    legal_db = _manifest_path(
        root,
        lex,
        "legal_kg_db_path",
        fallback=lex_bundle / "finalize" / "lex_knowledge_graph.duckdb" if lex_bundle else None,
    )
    _set_default_existing_path(params, "lex_bundle_dir", lex_bundle)
    _set_default_existing_path(params, "legal_db_path", legal_db)
    _set_default_existing_path(params, "legal_kg_db_path", legal_db)

    academic = _manifest_bundle(manifest, "academic")
    academic_dir = _manifest_path(
        root,
        academic,
        "path",
        fallback=root / "policyos_academic_runtime_slim_20260411T112032Z",
    )
    academic_component_dir = _manifest_path(
        root,
        academic,
        "component_path",
        fallback=academic_dir / "academic" if academic_dir else None,
    )
    academic_db = _manifest_path(
        root,
        academic,
        "academic_db_path",
        fallback=academic_component_dir / "graph" / "scholar_knowledge.duckdb"
        if academic_component_dir
        else None,
    )
    _set_default_existing_path(params, "academic_snapshot_dir", academic_dir)
    _set_default_existing_path(params, "academic_db_path", academic_db)
    _set_default_existing_path(params, "academic_index_dir", academic_component_dir)
    _set_default_existing_path(params, "skg_db_path", academic_db)
    _set_default_existing_path(params, "skg_index_dir", academic_component_dir)
    _set_default_existing_path(
        params,
        "benchmark_suite_path",
        _manifest_path(
            root,
            academic,
            "benchmark_suite_path",
            fallback=academic_component_dir / "benchmark_suite.json"
            if academic_component_dir
            else None,
        ),
    )
    _set_default_existing_path(
        params,
        "benchmark_report_path",
        _manifest_path(
            root,
            academic,
            "benchmark_report_path",
            fallback=academic_component_dir / "benchmark_report.json"
            if academic_component_dir
            else None,
        ),
    )
    _set_default_existing_path(
        params,
        "academic_demand_backlog_path",
        _manifest_path(
            root,
            academic,
            "demand_backlog_path",
            fallback=academic_component_dir / "runtime_demand_backlog.jsonl"
            if academic_component_dir
            else None,
        ),
    )

    ukraine = _manifest_bundle(manifest, "ukraine_simulation")
    ukraine_root = _manifest_path(
        root,
        ukraine,
        "path",
        fallback=root / "ukraine_agent_simulation_baseline_20260410",
    )
    ukraine_bundles = ukraine_root / "production_bundle" / "bundles" if ukraine_root else None
    _set_default_existing_path(params, "ukraine_agent_simulation_root", ukraine_root)
    _set_default_existing_path(
        params,
        "ukraine_runtime_bundle_dir",
        _manifest_path(
            root,
            ukraine,
            "runtime_bundle_dir",
            fallback=ukraine_bundles / "runtime_bundle_v1" if ukraine_bundles else None,
        ),
    )
    _set_default_existing_path(
        params,
        "ukraine_intervention_bundle_dir",
        _manifest_path(
            root,
            ukraine,
            "intervention_bundle_dir",
            fallback=ukraine_bundles / "intervention_bundle_v1" if ukraine_bundles else None,
        ),
    )
    _set_default_existing_path(
        params,
        "ukraine_calibration_bundle_dir",
        _manifest_path(
            root,
            ukraine,
            "calibration_bundle_dir",
            fallback=ukraine_bundles / "calibration_bundle_v1" if ukraine_bundles else None,
        ),
    )
    _set_default_existing_path(
        params,
        "ukraine_method_contract_bundle_dir",
        _manifest_path(
            root,
            ukraine,
            "method_contract_bundle_dir",
            fallback=ukraine_bundles / "method_contract_bundle_v1" if ukraine_bundles else None,
        ),
    )


def build_production_data_fabric_trace(
    *,
    query_intent: Mapping[str, Any] | None,
    evidence_context: Mapping[str, Any],
    data_needs: list[Mapping[str, Any]],
    fetch_plans: list[Mapping[str, Any]],
    retrieval_telemetry: Mapping[str, Any],
    materialization_refs: Mapping[str, Any],
    expected_source_families: list[str] | None = None,
    canary_kind: str = "production",
    spine_context: Mapping[str, Any] | None = None,
    scenario_evidence_contract: Mapping[str, Any] | None = None,
    production_data_contract_binding_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Fabric source-selection evidence for the production-data lane."""
    bundles = evidence_context.get("bundles")
    bundle_rows = bundles if isinstance(bundles, Mapping) else {}
    candidate_sources = [
        _source_from_manifest_bundle(
            role=str(role),
            bundle=bundle,
            evidence_context=evidence_context,
            data_needs=data_needs,
            retrieval_telemetry=retrieval_telemetry,
        )
        for role, bundle in sorted(bundle_rows.items())
        if isinstance(bundle, Mapping)
    ]
    contract_candidate_sources = _sources_from_contract_binding_report(
        production_data_contract_binding_report
    )
    candidate_sources.extend(contract_candidate_sources)
    selected_source_ids = [
        str(source["source_id"])
        for source in candidate_sources
        if isinstance(source.get("source_id"), str) and source["source_id"]
    ]
    satisfied_contract_source_ids = [
        str(source["source_id"])
        for source in contract_candidate_sources
        if source.get("contract_binding_status") == "satisfied"
        and isinstance(source.get("source_id"), str)
    ]
    if satisfied_contract_source_ids:
        selected_source_ids = satisfied_contract_source_ids
    rejected_sources = _rejected_fetch_plan_sources(fetch_plans)
    resolved_query_intent = dict(query_intent or {})
    if data_needs and "query_outcome" not in resolved_query_intent:
        outcome = _as_text(data_needs[0].get("metric"))
        if outcome:
            resolved_query_intent["query_outcome"] = outcome

    trace_context = dict(evidence_context)
    trace_context["materialization_refs"] = {
        str(key): str(value) for key, value in materialization_refs.items() if _as_text(value)
    }
    expected = expected_source_families
    if expected is None:
        expected = _expected_source_families_from_scenario_contract(
            scenario_evidence_contract
        )
    if expected is None:
        expected = [
            str(source.get("source_family"))
            for source in candidate_sources
            if _as_text(source.get("source_family"))
        ]

    return build_fabric_source_selection_trace(
        query_intent=resolved_query_intent,
        candidate_sources=candidate_sources,
        selected_source_ids=selected_source_ids,
        rejected_sources=rejected_sources,
        expected_source_families=expected,
        canary_kind=canary_kind,
        materialization_refs=trace_context["materialization_refs"],
        production_data_evidence_context=trace_context,
        spine_context=spine_context,
        scenario_evidence_contract=scenario_evidence_contract,
        production_data_contract_binding_report=production_data_contract_binding_report,
    )


def _expected_source_families_from_scenario_contract(
    scenario_evidence_contract: Mapping[str, Any] | None,
) -> list[str] | None:
    if not isinstance(scenario_evidence_contract, Mapping):
        return None
    requirements = scenario_evidence_contract.get("requirements")
    if not isinstance(requirements, list):
        return None
    families = [
        _as_text(requirement.get("expected_family"))
        for requirement in requirements
        if isinstance(requirement, Mapping)
        and _as_text(requirement.get("domain")).casefold() == "data"
        and _as_text(requirement.get("expected_family"))
    ]
    return families or None


def _sources_from_contract_binding_report(
    production_data_contract_binding_report: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(production_data_contract_binding_report, Mapping):
        return []
    findings = production_data_contract_binding_report.get("scenario_binding_findings")
    if not isinstance(findings, list):
        return []
    sources = []
    for finding in findings:
        if not isinstance(finding, Mapping) or not _as_text(finding.get("candidate_ref")):
            continue
        source = _source_from_contract_binding_finding(finding)
        if source:
            sources.append(source)
    return sources


def _source_from_contract_binding_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    candidate_ref = _as_text(finding.get("candidate_ref"))
    source_family = _as_text(finding.get("expected_family") or finding.get("source_family"))
    facet_refs = finding.get("facet_refs") if isinstance(finding.get("facet_refs"), Mapping) else {}
    present_facets = {
        _as_text(item)
        for item in finding.get("present_facets") or ()
        if _as_text(item)
    }
    status = _as_text(finding.get("status")).casefold()
    derived_features = [
        {
            "feature_ref": ref,
            "source_facet_refs": _refs_list(facet_refs.get("field_refs")),
            "claim_support_feature_refs": [f"claim-feature:{source_family}:{ref}"],
        }
        for ref in _refs_list(facet_refs.get("derived_feature_bindings"))
    ]
    return {
        "source_id": candidate_ref,
        "source_family": source_family,
        "source_kind": "production_data_contract",
        "source_rights": _first_ref(facet_refs.get("source_rights")),
        "dictionary_ref": _first_ref(facet_refs.get("dictionary_ref")),
        "schema_ref": _first_ref(facet_refs.get("schema_ref")),
        "field_refs": _refs_list(facet_refs.get("field_refs")),
        "unit_refs": _refs_list(facet_refs.get("unit_refs")),
        "geography_refs": _refs_list(facet_refs.get("geography_refs")),
        "time_coverage_refs": _refs_list(facet_refs.get("time_coverage_refs")),
        "quality_refs": _refs_list(facet_refs.get("quality_refs")),
        "missingness_refs": _refs_list(facet_refs.get("missingness_refs")),
        "freshness_refs": _refs_list(
            facet_refs.get("freshness_ref") or facet_refs.get("recency_ref")
        ),
        "lineage_refs": _refs_list(facet_refs.get("lineage_refs")),
        "transformation_refs": _refs_list(facet_refs.get("transformation_refs")),
        "quality_assertion_refs": _refs_list(
            facet_refs.get("quality_assertion_refs")
        ),
        "claim_bindability_refs": _refs_list(facet_refs.get("claim_bindability_refs")),
        "derived_features": derived_features,
        "freshness": {
            "status": "pass" if "freshness_ref" in present_facets else "fail",
            "ref": _first_ref(facet_refs.get("freshness_ref")),
        },
        "coverage": {
            "status": (
                "pass"
                if {"geography_refs", "time_coverage_refs"} <= present_facets
                else "fail"
            )
        },
        "schema_compatibility": {
            "status": (
                "pass"
                if {"schema_ref", "field_refs", "unit_refs"} <= present_facets
                else "fail"
            ),
            "required_fields": _refs_list(facet_refs.get("field_refs")),
        },
        "quality": {
            "status": "pass" if "quality_assertion_refs" in present_facets else "fail",
            "ref": _first_ref(facet_refs.get("quality_assertion_refs")),
        },
        "relevance_score": 1.0 if status == "satisfied" else 0.0,
        "relevance_rationale": (
            f"Production data contract-index candidate for scenario family {source_family}."
        ),
        "contract_binding_status": status,
        "contract_binding": dict(finding),
    }


def _refs_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        for key in ("ref", "id", "artifact_ref", "artifact_id"):
            text = _as_text(value.get(key))
            if text:
                return [text]
        return [
            text
            for text in (_as_text(item) for item in value.values())
            if text
        ]
    if isinstance(value, list | tuple | set):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_list(item))
        return list(dict.fromkeys(refs))
    text = _as_text(value)
    return [text] if text else []


def _first_ref(value: Any) -> str | None:
    refs = _refs_list(value)
    return refs[0] if refs else None


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _source_from_manifest_bundle(
    *,
    role: str,
    bundle: Mapping[str, Any],
    evidence_context: Mapping[str, Any],
    data_needs: list[Mapping[str, Any]],
    retrieval_telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    source_id = (
        _as_text(bundle.get("source_id"))
        or _as_text(bundle.get("version_id"))
        or f"production_data:{role}"
    )
    source_family = (
        _as_text(bundle.get("source_family")) or _as_text(bundle.get("data_source_family")) or role
    )
    source_path = _as_text(bundle.get("path") or bundle.get("manifest_path"))
    manifest_sha = _as_text(evidence_context.get("manifest_sha256"))
    readiness = _as_text(bundle.get("readiness")) or "available"
    return {
        "source_id": source_id,
        "source_family": source_family,
        "source_kind": "production_data",
        "source_path": source_path,
        "freshness": {
            "status": "pass" if manifest_sha else "fail",
            "manifest_sha256": manifest_sha,
            "readiness": readiness,
        },
        "coverage": {
            "status": "pass",
            "bundle_role": role,
            "root": _as_text(evidence_context.get("root")),
            "version_id": _as_text(bundle.get("version_id")),
        },
        "schema_compatibility": {
            "status": "pass",
            "data_need_count": len(data_needs),
            "required_metrics": [
                _as_text(item.get("metric")) for item in data_needs if _as_text(item.get("metric"))
            ],
        },
        "relevance_score": 1.0,
        "relevance_rationale": (
            f"Production data manifest bundle {role} selected for "
            f"{len(data_needs)} declared data need(s)."
        ),
        "retrieval_diagnostics": {
            "metadata_docs_fetched": int(retrieval_telemetry.get("metadata_docs_fetched") or 0),
            "index_docs_total": int(retrieval_telemetry.get("local_index_docs_total") or 0),
        },
    }


def _rejected_fetch_plan_sources(fetch_plans: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for plan in fetch_plans:
        source_lane = _as_text(plan.get("source_lane"))
        if source_lane == "production_data_manifest":
            continue
        connector_id = _as_text(plan.get("connector_id")) or "unknown.connector"
        dataset_id = _as_text(plan.get("dataset_id")) or "unknown.dataset"
        rejected.append(
            {
                "source_id": f"{connector_id}:{dataset_id}",
                "source_family": _as_text(plan.get("profile_id")) or connector_id,
                "source_kind": "candidate_fetch_plan",
                "reason_code": "production_data_manifest_lane_selected",
                "relevance_score": _as_text(plan.get("quality_min")) or None,
                "relevance_rationale": (
                    "Production-data lane used manifest-pinned bundles instead of "
                    "PromotionLane fetch-plan materialization."
                ),
            }
        )
    return rejected


def _manifest_bundle(manifest: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    bundles = manifest.get("bundles")
    if not isinstance(bundles, Mapping):
        return {}
    bundle = bundles.get(role)
    return bundle if isinstance(bundle, Mapping) else {}


def _manifest_path(
    root: Path,
    bundle: Mapping[str, Any],
    key: str,
    *,
    fallback: Path | None = None,
) -> Path | None:
    raw = bundle.get(key)
    if isinstance(raw, str) and raw.strip():
        path = Path(raw).expanduser()
        return path if path.is_absolute() else root / path
    return fallback


def _existing_param_path(params: Mapping[str, Any], key: str) -> Path | None:
    raw = params.get(key)
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.exists() else None


def _set_default_existing_path(
    params: MutableMapping[str, Any],
    key: str,
    path: Path | None,
) -> None:
    if key in params or path is None or not path.exists():
        return
    params[key] = str(path)


def _first_existing_path(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _first_child_with(parent: Path, relative_file: str) -> Path | None:
    if not parent.exists():
        return None
    for child in sorted((item for item in parent.iterdir() if item.is_dir()), reverse=True):
        if (child / relative_file).exists():
            return child
    return None


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    return f"sha256:{digest}"


__all__ = [
    "PRODUCTION_DATA_MANIFEST_NAME",
    "PRODUCTION_DATA_ROOT_ENV",
    "apply_production_data_defaults",
    "build_production_data_fabric_trace",
    "load_production_data_manifest",
    "production_data_bundle_path",
    "production_data_contract_binding_report",
    "production_data_evidence_context",
    "production_data_quality_report",
    "resolve_production_data_root",
]
