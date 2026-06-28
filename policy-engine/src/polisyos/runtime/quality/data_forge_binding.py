"""Runtime Data Forge snapshot/read-API binding evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from polisyos.core import artifacts, canon, scan_secret_and_pii
from polisyos.data_forge import read_api
from polisyos.data_forge.read_api import OfficialSnapshotAnswer
from polisyos.data_forge.read_api.surfaces import available_surfaces, surface_module
from polisyos.data_requirement import DataQualityMinimums, DataRequirementScope, DataRequirementSpec
from polisyos.pdc import ArtifactEnvelope, ArtifactRef, gy_content_hash
from polisyos.runtime.quality.adapter_contracts import (
    ConnectorAdmissionGate,
    DataRequirementAdmissionGate,
    WORKSPACE_SOURCE_CONTRACT_FACETS,
)

DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION = (
    "policyos.runtime.data_forge_snapshot_binding.v1"
)
DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_FILE = "data_forge_snapshot_binding.json"
DATA_FORGE_SNAPSHOT_BINDING_GATE = "data_forge_snapshot_binding_valid"
DATA_FORGE_SNAPSHOT_BINDING_LAYER = "data_forge_snapshot_binding"
DATA_FORGE_SNAPSHOT_BINDING_PHASE = "data_forge_snapshot_binding"
DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS = 60 * 60 * 24 * 90
WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy_loop.v1"
WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION = (
    "policyos.gy.phase2.recorded_panel_measurement_root.v1"
)
REQUIRED_DATA_FORGE_SNAPSHOT_ROLES = ("legal", "catalog", "academic", "domain")
DATA_FORGE_SNAPSHOT_ROLE_SURFACES = {
    "legal": "legal",
    "catalog": "catalog",
    "academic": "academic",
    "domain": "ukraine",
}
_PASS_STATUSES = {"pass", "passed", "ok", "success"}
_LOCAL_PATH_PREFIXES = ("/", "./", "../", "~", "file://")
_BROAD_REQUIREMENT_KINDS = {
    "broad_bundle",
    "broad_context",
    "broad_dataset_label",
    "context_inventory",
    "dataset_bundle",
    "generic_dataset",
}
_TIME_ROLES = {
    "detection_time",
    "freshness_time",
    "ingestion_time",
    "observation_time",
    "publication_time",
    "release_time",
    "replay_time",
    "snapshot_time",
    "transaction_time",
    "valid_time",
}
_RECORDED_WORLD_BANK_MEASUREMENT_ROWS: dict[str, tuple[dict[str, Any], ...]] = {
    "FX.OWN.TOTL.ZS": (
        {
            "row_id": "worldbank-findex-ukr-fx-own-totl-zs-2024",
            "evidence_kind": "measurement",
            "indicator_id": "FX.OWN.TOTL.ZS",
            "indicator_name": (
                "Account ownership at a financial institution or with a mobile-money-service "
                "provider (% of population ages 15+)"
            ),
            "country_code": "UA",
            "country_iso3": "UKR",
            "country_name": "Ukraine",
            "year": 2024,
            "value": 87.581225854266,
            "unit": "percent_of_population_ages_15_plus",
            "source_ref": (
                "https://api.worldbank.org/v2/country/UKR/indicator/"
                "FX.OWN.TOTL.ZS?format=json"
            ),
            "source_observed_at": "2026-06-16T00:00:00Z",
            "cassette_ref": "recorded-worldbank-api:UKR:FX.OWN.TOTL.ZS:2024",
        },
        {
            "row_id": "worldbank-findex-ukr-fx-own-totl-zs-2021",
            "evidence_kind": "measurement",
            "indicator_id": "FX.OWN.TOTL.ZS",
            "indicator_name": (
                "Account ownership at a financial institution or with a mobile-money-service "
                "provider (% of population ages 15+)"
            ),
            "country_code": "UA",
            "country_iso3": "UKR",
            "country_name": "Ukraine",
            "year": 2021,
            "value": 83.5648133398349,
            "unit": "percent_of_population_ages_15_plus",
            "source_ref": (
                "https://api.worldbank.org/v2/country/UKR/indicator/"
                "FX.OWN.TOTL.ZS?format=json"
            ),
            "source_observed_at": "2026-06-16T00:00:00Z",
            "cassette_ref": "recorded-worldbank-api:UKR:FX.OWN.TOTL.ZS:2021",
        },
        {
            "row_id": "worldbank-findex-ukr-fx-own-totl-zs-2017",
            "evidence_kind": "measurement",
            "indicator_id": "FX.OWN.TOTL.ZS",
            "indicator_name": (
                "Account ownership at a financial institution or with a mobile-money-service "
                "provider (% of population ages 15+)"
            ),
            "country_code": "UA",
            "country_iso3": "UKR",
            "country_name": "Ukraine",
            "year": 2017,
            "value": 62.9023288438411,
            "unit": "percent_of_population_ages_15_plus",
            "source_ref": (
                "https://api.worldbank.org/v2/country/UKR/indicator/"
                "FX.OWN.TOTL.ZS?format=json"
            ),
            "source_observed_at": "2026-06-16T00:00:00Z",
            "cassette_ref": "recorded-worldbank-api:UKR:FX.OWN.TOTL.ZS:2017",
        },
    ),
}


class _CatalogRecordProtocol(Protocol):
    id: str
    source: str
    execution_tier: str
    connector_type: str

    def model_dump(self, *, mode: str) -> dict[str, object]:
        """Return a JSON payload for the catalog record."""

        ...


class CatalogGraphProtocol(Protocol):
    """Minimal DatasetCatalogGraph surface consumed by the workspace measurement producer."""

    def search_datasets(
        self,
        query: str,
        *,
        top_k: int,
        explain: bool,
    ) -> list[_CatalogRecordProtocol]:
        """Return ranked dataset matches for a construct/scope query."""

        ...

    def get_distributions(self, dataset_id: str) -> list[object]:
        """Return distribution metadata for one dataset id."""

        ...

    def resolve_fetch_target(self, dataset_id: str) -> object | None:
        """Return the fetch target for one dataset id, if available."""

        ...


class _WorkspaceFixtureManifestProtocol(Protocol):
    fixture_id: str
    construct_scope_query: str
    jurisdiction: str
    population: str
    time_horizon: str
    expected_catalog_binding_refs: list[str]
    expected_connector_profile: str
    expected_producer_root_kind: str


class MeasurementRootBindingError(RuntimeError):
    """Raised when a workspace measurement-root catalog binding cannot be produced."""


class MeasurementRootProducer:
    """Produce CAS-backed BaseDataset artifacts from DatasetCatalogGraph bindings."""

    def __init__(self, *, artifact_store: artifacts.FileSystemCAS | None = None) -> None:
        self._artifact_store = artifact_store

    def produce_from_catalog(
        self,
        manifest: _WorkspaceFixtureManifestProtocol,
        catalog_graph: CatalogGraphProtocol,
    ) -> ArtifactEnvelope:
        """Resolve a pinned construct through DatasetCatalogGraph and persist its root."""

        hits = catalog_graph.search_datasets(
            manifest.construct_scope_query,
            top_k=20,
            explain=True,
        )
        expected_refs = set(manifest.expected_catalog_binding_refs)
        expected_hits = [hit for hit in hits if hit.id in expected_refs]
        selected = next(
            (
                hit
                for hit in expected_hits
                if measurement_rows_for_catalog_payload(hit.model_dump(mode="json"))
            ),
            None,
        )
        if selected is None:
            selected = next(iter(expected_hits), None)
        if selected is None:
            selected = next(
                (
                    hit
                    for hit in hits
                    if hit.source == manifest.expected_connector_profile
                    and hit.execution_tier == "transport_ready"
                ),
                None,
            )
        if selected is None:
            raise MeasurementRootBindingError(
                f"catalog binding not found for fixture {manifest.fixture_id}"
            )
        distributions = [
            distribution.model_dump(mode="json")
            for distribution in catalog_graph.get_distributions(selected.id)
        ]
        connector_type = selected.connector_type or (
            str(distributions[0].get("connector_type")) if distributions else ""
        )
        connector_gate = ConnectorAdmissionGate().evaluate(connector_type)
        if connector_gate.status != "applicable":
            raise MeasurementRootBindingError(
                f"connector admission failed for {connector_type}: {connector_gate.status}"
            )
        (
            data_requirement_spec,
            source_contract_requirement,
        ) = source_requirement_for_catalog_binding(
            manifest=manifest,
            selected=selected,
            distributions=distributions,
            connector_type=connector_type,
        )
        source_contract_gate = DataRequirementAdmissionGate().evaluate(data_requirement_spec)
        if source_contract_gate.status != "applicable":
            raise MeasurementRootBindingError(
                "source-contract admission failed before measurement-root fetch"
            )
        selected_payload = canonical_catalog_result_for_workspace_loop(
            selected.model_dump(mode="json")
        )
        measurement_rows = measurement_rows_for_catalog_payload(selected_payload)
        if manifest.expected_producer_root_kind == "measurement" and not measurement_rows:
            raise MeasurementRootBindingError(
                "measurement-root admission failed: no recorded source measurement rows"
            )
        payload = {
            "fixture_id": manifest.fixture_id,
            "catalog_binding_refs": [selected.id],
            "catalog_result": selected_payload,
            "connector_profile": manifest.expected_connector_profile,
            "producer_root_kind": manifest.expected_producer_root_kind,
            "measurement_rows": measurement_rows,
            "distributions": distributions,
            "fetch_target": _model_dump_or_none(catalog_graph.resolve_fetch_target(selected.id)),
            "applicability_result": connector_gate.model_dump(mode="json"),
            "source_contract_admission": source_contract_gate.model_dump(mode="json"),
            "data_requirement_spec": data_requirement_spec.model_dump(mode="json"),
            "source_contract_requirement": source_contract_requirement,
        }
        payload_ref = self._persist_payload(payload)
        artifact_slug = _gy_slug(manifest.fixture_id)
        producer_root = ArtifactRef.from_payload(
            artifact_id=f"measurement-root-{artifact_slug}",
            artifact_type="MeasurementRoot",
            payload={
                "dataset_id": selected.id,
                "connector_type": connector_type,
                "producer_root_kind": manifest.expected_producer_root_kind,
                "measurement_row_count": len(measurement_rows),
                "measurement_row_refs": [row["row_id"] for row in measurement_rows],
            },
            schema_ref=WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION,
            uri=f"gy://slice0/{manifest.fixture_id}/measurement-root",
            version="v1",
        )
        ref = ArtifactRef.from_payload(
            artifact_id=f"base-{artifact_slug}",
            artifact_type="BaseDataset",
            payload=payload,
            schema_ref=WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION,
            uri=f"gy://slice0/{manifest.fixture_id}/base-dataset",
            version="v1",
        )
        return ArtifactEnvelope(
            ref=ref,
            payload_ref=payload_ref,
            payload_schema_ref=WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION,
            lifecycle_state="shadow",
            created_by={
                "kind": "producer",
                "component": "polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer",
            },
            producer_operation={
                "invocation_id": "invoke-bind",
                "operation_id": "slice0.bind.catalog",
                "operation_version": "v1",
            },
            input_artifacts=[],
            producer_roots=[producer_root],
            obligations=[],
            verification={"latest_applicability_result": source_contract_gate.result_id},
        )

    def _persist_payload(self, payload: dict[str, Any]) -> str:
        if self._artifact_store is None:
            return gy_content_hash(payload)
        scan = scan_secret_and_pii(
            payload,
            scope="DAG bundles",
            artifact_ref_or_route="gy-measurement-root://payload",
            redact=False,
            block_on_findings=True,
        )
        if scan.has_findings:
            raise MeasurementRootBindingError(
                "Measurement-root payload blocked by secret/PII scan: "
                + ",".join(scan.finding_kinds)
            )
        from polisyos.runtime.http.services.control.artifacts import write_authority_artifact

        generated_at = _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")
        fixture_id = str(payload.get("fixture_id") or "measurement-root")
        result = write_authority_artifact(
            self._artifact_store,
            payload,
            artifacts.PutOptions(
                kind="policyos.gy.measurement_root_payload",
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION,
                    version="v1",
                ),
                producer=artifacts.ProducerInfo(
                    component=(
                        "polisyos.runtime.quality.data_forge_binding."
                        "MeasurementRootProducer"
                    ),
                    version="1.0.0",
                ),
            ),
            evidence_id=f"gy-measurement-root-{gy_content_hash(payload).split(':')[-1][:16]}",
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION,
            reader_contract_version="v1",
            tenant_id="policyos-system",
            cell_id=None,
            run_id=f"run-gy-measurement-root-{_gy_slug(fixture_id)}",
            job_id=f"job-gy-measurement-root-{_gy_slug(fixture_id)}",
            trace_id="trace-gy-measurement-root",
            span_id="span-gy-measurement-root",
            parent_span_id=None,
            requested_execution_profile="gy_slice0",
            effective_execution_profile="gy_slice0",
            phase="GY-F2",
            generated_at=generated_at,
            as_of_time=generated_at,
            same_input_closure={
                "closure_id": f"gy-measurement-root-{_gy_slug(fixture_id)}",
                "status": "closed",
                "run_id": f"run-gy-measurement-root-{_gy_slug(fixture_id)}",
                "job_id": f"job-gy-measurement-root-{_gy_slug(fixture_id)}",
                "tenant_id": "policyos-system",
                "cell_id": None,
                "evidence_input_refs": (),
            },
            input_refs=[],
            effective_mode_ref="gy-slice0-runtime",
            validation_status="pass",
            blocking_status="non_blocking",
            governance={
                "classification": "internal",
                "authority_boundary": "measurement_root",
                "pii": "secret_pii_scanned",
                "retention_policy": "policy_design_case_generated_artifact",
                "review_status": "runtime_generated",
                "override_policy": "no_override",
                "approval_policy": "not_publication_authority",
            },
            redaction_policy_ref="polisyos.core.llm.sanitization.v1",
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        return str(result.cas_ref.artifact_id)


def produce_phase2_recorded_panel_measurement_root(
    *,
    store: artifacts.FileSystemCAS,
) -> artifacts.ArtifactRef:
    """Persist a deterministic Foundry panel from recorded production rows.

    This bridge stays with the Data Forge binding owner. It samples a fixed
    three-entity, ten-period panel from the recorded Ukraine calibration
    observation cassette and persists it as ``ir.observational_data`` so the
    existing Foundry causal node can consume a real measurement root.
    """

    extracted = _phase2_recorded_panel_payload()
    panel_payload = {
        "outcome": extracted["outcome"],
        "treatment": [1, 0, 0],
        "time_treatment": 5,
        "unit_ids": extracted["unit_ids"],
        "time_index": extracted["time_index"],
        "metadata": {
            "input_provenance": "measurement_rooted",
            "source": "recorded_rows",
            "source_path": extracted["source_path"],
            "source_manifest": extracted["source_manifest"],
            "row_count": extracted["row_count"],
            "metric_id": extracted["metric_id"],
            "family": extracted["family"],
            "aggregation": extracted["aggregation"],
            "producer": (
                "polisyos.runtime.quality.data_forge_binding."
                "produce_phase2_recorded_panel_measurement_root"
            ),
        },
    }
    return store.put_json(
        panel_payload,
        artifacts.PutOptions(
            kind="ir.observational_data",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION,
                version="1.0",
            ),
            producer=artifacts.ProducerInfo(
                component=(
                    "polisyos.runtime.quality.data_forge_binding."
                    "produce_phase2_recorded_panel_measurement_root"
                ),
                version="phase2.v1",
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


@lru_cache(maxsize=1)
def _phase2_recorded_panel_payload() -> dict[str, Any]:
    try:
        import duckdb
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency is expected locally
        raise MeasurementRootBindingError("duckdb is required for recorded-row binding") from exc

    root = Path(__file__).resolve().parents[4]
    bundle_dir = (
        root
        / "production_data"
        / "ukraine_agent_simulation_baseline_20260410"
        / "production_bundle"
        / "bundles"
        / "calibration_bundle_v1"
    )
    parquet_path = bundle_dir / "observation_panel_monthly.parquet"
    manifest_path = bundle_dir / "calibration_bundle_manifest.json"
    if not parquet_path.exists():
        raise MeasurementRootBindingError(f"recorded-row panel not found: {parquet_path}")
    entity_order = ["42032422", "41865032", "41433726"]
    query = """
        WITH filtered AS (
            SELECT
                CAST(entity_id AS VARCHAR) AS entity_id,
                CAST(period_start AS DATE) AS period_start,
                SUM(CAST(observed_value AS DOUBLE)) AS observed_value
            FROM read_parquet(?)
            WHERE family = 'budget_flows'
              AND metric_id = 'amount'
              AND observed_value IS NOT NULL
              AND CAST(entity_id AS VARCHAR) IN ('42032422', '41865032', '41433726')
              AND CAST(period_start AS DATE) >= DATE '2018-05-01'
              AND CAST(period_start AS DATE) <= DATE '2019-02-01'
            GROUP BY 1, 2
        ),
        complete_periods AS (
            SELECT period_start
            FROM filtered
            GROUP BY period_start
            HAVING COUNT(*) = 3
            ORDER BY period_start
            LIMIT 10
        )
        SELECT entity_id, CAST(period_start AS VARCHAR) AS period_start, observed_value
        FROM filtered
        JOIN complete_periods USING (period_start)
        ORDER BY period_start, entity_id
    """
    rows = duckdb.connect(database=":memory:").execute(query, [str(parquet_path)]).fetchall()
    if len(rows) != 30:
        raise MeasurementRootBindingError(
            f"recorded-row panel expected 30 entity-period rows, got {len(rows)}"
        )
    period_order = sorted({str(row[1]) for row in rows})
    values = {
        (str(entity), str(period)): round(float(value), 6)
        for entity, period, value in rows
    }
    return {
        "outcome": [
            [values[(entity_id, period)] for period in period_order]
            for entity_id in entity_order
        ],
        "unit_ids": entity_order,
        "time_index": period_order,
        "row_count": len(rows),
        "source_path": str(parquet_path.relative_to(root)),
        "source_manifest": str(manifest_path.relative_to(root)),
        "metric_id": "amount",
        "family": "budget_flows",
        "aggregation": "sum observed_value by entity_id and month",
    }


def build_default_workspace_catalog_graph() -> CatalogGraphProtocol:
    """Build the canonical workspace fixture DatasetCatalogGraph."""

    return read_api.catalog.build_slice0_fixture_catalog_graph()


def source_requirement_for_catalog_binding(
    *,
    manifest: _WorkspaceFixtureManifestProtocol,
    selected: _CatalogRecordProtocol,
    distributions: list[dict[str, Any]],
    connector_type: str,
) -> tuple[DataRequirementSpec, dict[str, Any]]:
    """Build the DataRequirementSpec/source-contract payload for a catalog root."""

    selected_payload = selected.model_dump(mode="json")
    source_registry_entry = _catalog_source_registry_entry(selected)
    source_registry_payload = (
        source_registry_entry.model_dump(mode="json")
        if source_registry_entry is not None
        else {}
    )
    facet_values = _source_contract_facet_values(
        manifest=manifest,
        selected_payload=selected_payload,
        distributions=distributions,
        connector_type=connector_type,
        source_registry_payload=source_registry_payload,
    )
    source_contract_requirement = {
        "requirement_id": f"req-{_gy_slug(manifest.fixture_id)}",
        "claim_id": f"claim-{_gy_slug(manifest.fixture_id)}",
        "dataset_id": selected.id,
        "connector_type": connector_type,
        "mandatory_facets": sorted(WORKSPACE_SOURCE_CONTRACT_FACETS),
        "facet_refs": {},
        "facet_values": facet_values,
        "source_registry_entry": source_registry_payload,
        "rule_version": "policyos.gy.source_contract_16_facets.v1",
    }
    spec = DataRequirementSpec(
        requirement_id=source_contract_requirement["requirement_id"],
        claim_id=source_contract_requirement["claim_id"],
        claim_family="measurement_root",
        claim_type="source_quality",
        claim_use="estimate_port",
        required_data_families=(str(selected_payload.get("source") or connector_type),),
        scope=DataRequirementScope(
            population=manifest.population,
            geography=manifest.jurisdiction,
            jurisdiction=manifest.jurisdiction,
            time=manifest.time_horizon,
            time_role="observation_time",
        ),
        recency_horizon=str(facet_values["freshness"]),
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(
            min_quality_score=0.7,
            min_completeness=0.9,
            required_quality_refs=("source_contract.quality_floor",),
        ),
        missingness_tolerance=0.05,
        transformation_tolerance="traceable",
        admissibility_predicates=(
            "connector_execution_ready",
            "source_contract_16_facets_present",
            "measurement_root_fetchable",
        ),
        mandatory_facets=tuple(sorted(WORKSPACE_SOURCE_CONTRACT_FACETS)),
        facet_refs=(),
        concept_spine_refs=(f"concept://gy/{_gy_slug(manifest.construct_scope_query)}",),
        authority_profile_refs=("authority_profile://gy/measurement_root_descriptive",),
        rule_version_ref="policyos.gy.data_requirement_admission.v1",
        producer="polisyos.runtime.quality.data_forge_binding.MeasurementRootProducer",
        source_requirement_refs=(f"catalog:{selected.id}",),
        metadata={"gy_source_contract": source_contract_requirement},
    )
    return spec, source_contract_requirement


def measurement_rows_for_catalog_payload(
    selected_payload: Mapping[str, object],
) -> list[dict[str, Any]]:
    """Return recorded source rows for a catalog payload when the workspace has a cassette."""

    source_dataset_id = str(selected_payload.get("source_dataset_id") or "").strip()
    dataset_id = str(selected_payload.get("dataset_id") or "").strip()
    rows = _RECORDED_WORLD_BANK_MEASUREMENT_ROWS.get(source_dataset_id) or (
        _RECORDED_WORLD_BANK_MEASUREMENT_ROWS.get(dataset_id) or ()
    )
    return [dict(row) for row in rows]


def canonical_catalog_result_for_workspace_loop(
    selected_payload: Mapping[str, object],
) -> dict[str, object]:
    """Return the stable catalog evidence fields used by workspace proof payloads."""

    payload = dict(selected_payload)
    payload.pop("similarity", None)
    payload.pop("search_explanation", None)
    return payload


def _catalog_source_registry_entry(selected: _CatalogRecordProtocol) -> object | None:
    try:
        registry = read_api.catalog.load_catalog_source_registry()
    except (AttributeError, ImportError):
        return None
    source_id = str(getattr(selected, "source", "") or "").strip()
    if source_id:
        entry = registry.source_by_id(source_id)
        if entry is not None:
            return entry
    connector_type = str(getattr(selected, "connector_type", "") or "").strip()
    for entry in registry.sources:
        if entry.connector_id == connector_type:
            return entry
    return None


def _source_contract_facet_values(
    *,
    manifest: _WorkspaceFixtureManifestProtocol,
    selected_payload: dict[str, object],
    distributions: list[dict[str, Any]],
    connector_type: str,
    source_registry_payload: dict[str, Any],
) -> dict[str, Any]:
    distribution = distributions[0] if distributions else {}
    access = (
        selected_payload.get("access")
        if isinstance(selected_payload.get("access"), dict)
        else {}
    )
    coverage = (
        selected_payload.get("coverage")
        if isinstance(selected_payload.get("coverage"), dict)
        else {}
    )
    quality = (
        selected_payload.get("quality")
        if isinstance(selected_payload.get("quality"), dict)
        else {}
    )
    source_registry_ref = source_registry_payload.get("source_id")
    validation_status = (
        "source_registry_verified"
        if selected_payload.get("id")
        and selected_payload.get("source_dataset_id")
        and selected_payload.get("variables")
        and connector_type
        and source_registry_ref
        and distribution.get("quality_score") is not None
        else "incomplete"
    )
    return {
        "authority_profile": "authority_profile://gy/measurement_root_descriptive",
        "connector": connector_type,
        "construct": manifest.construct_scope_query,
        "coverage": {
            "jurisdiction": manifest.jurisdiction,
            "population": manifest.population,
            "catalog_coverage": coverage,
        },
        "freshness": selected_payload.get("update_frequency")
        or source_registry_payload.get("update_frequency"),
        "granularity": coverage.get("granularity"),
        "jurisdiction": manifest.jurisdiction,
        "license": access.get("license")
        or selected_payload.get("license"),
        "lineage": {
            "catalog_dataset_id": selected_payload.get("id"),
            "source_dataset_id": selected_payload.get("source_dataset_id"),
            "source_registry_ref": source_registry_ref,
        },
        "population": manifest.population,
        "quality_floor": {
            "min_quality_score": 0.7,
            "catalog_quality": quality,
            "distribution_quality_score": distribution.get("quality_score"),
        },
        "rule_version": "policyos.gy.source_contract_16_facets.v1",
        "scope": {
            "query": manifest.construct_scope_query,
            "time_horizon": manifest.time_horizon,
        },
        "source_class": selected_payload.get("source") or source_registry_payload.get("family"),
        "source_contract": {
            "candidate_ref": f"source-contract://gy/{manifest.fixture_id}",
            "validation_status": validation_status,
            "validated_from": (
                "catalog_source_registry+dataset_catalog_graph+distribution_quality"
            ),
        },
        "time_horizon": manifest.time_horizon,
        "variables": list(selected_payload.get("variables") or []),
    }


def _model_dump_or_none(value: object) -> object | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _gy_slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


@dataclass(frozen=True)
class DataForgeSnapshotBindingIssue:
    """One deterministic Data Forge snapshot-binding validation issue."""

    code: str
    role: str
    field: str
    message: str
    value: object | None = None
    next_action: str = (
        "Emit Data Forge snapshot binding evidence with snapshot id, CAS manifest "
        "identity, artifact ids, quality-gate refs, freshness, and read_api surface."
    )

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": "fail",
            "status": "fail",
            "role": self.role,
            "field": self.field,
            "message": self.message,
            "next_action": self.next_action,
            "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


def normalize_data_forge_snapshot_binding_report(
    report: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize and validate runtime-owned Data Forge snapshot bindings."""

    observed_at = _utc(now)
    if not isinstance(report, Mapping):
        issue = DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_binding_missing",
            role="report",
            field=DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY,
            message=(
                "Serious runtime evidence is missing Data Forge snapshot/read-API "
                "binding evidence."
            ),
        )
        return _report_payload(
            source={},
            bindings=[],
            issues=[issue],
            now=observed_at,
        )

    source = {str(key): _json_value(value) for key, value in report.items()}
    issues: list[DataForgeSnapshotBindingIssue] = []
    if source.get("schema_version") != DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_binding_schema_version_invalid",
                role="report",
                field="schema_version",
                message="Data Forge snapshot binding report schema version is invalid.",
                value=source.get("schema_version"),
            )
        )

    blockers, blocker_issues = _runtime_blockers(source)
    issues.extend(blocker_issues)
    source_status = _clean_text(source.get("status") or source.get("quality_status"))
    if source_status is not None and source_status.casefold() == "blocked":
        if not blockers and not blocker_issues:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_missing",
                    role="report",
                    field="blockers",
                    message=(
                        "Blocked Data Forge snapshot binding report must preserve a "
                        "typed runtime blocker."
                    ),
                )
            )
        return _report_payload(
            source=source,
            bindings=[],
            issues=issues,
            now=observed_at,
            blockers=blockers,
            status_override="blocked",
        )

    raw_bindings = _binding_rows(source)
    bindings: list[dict[str, Any]] = []
    roles_seen: set[str] = set()
    for index, raw_binding in enumerate(raw_bindings, start=1):
        binding = {str(key): _json_value(value) for key, value in raw_binding.items()}
        role = _clean_text(binding.get("role")) or f"bindings[{index}]"
        if role in roles_seen:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_role_duplicate",
                    role=role,
                    field="role",
                    message=f"Data Forge snapshot role {role!r} appears more than once.",
                    value=role,
                )
            )
        roles_seen.add(role)
        _normalize_binding_surface(binding)
        _normalize_binding_report_defaults(binding, source)
        bindings.append(binding)
        issues.extend(_binding_issues(binding=binding, role=role, now=observed_at))

    for role in REQUIRED_DATA_FORGE_SNAPSHOT_ROLES:
        if role not in roles_seen:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_role_missing",
                    role=role,
                    field="bindings",
                    message=f"Data Forge snapshot binding for role {role!r} is missing.",
                )
            )

    return _report_payload(
        source=source,
        bindings=bindings,
        issues=issues,
        now=observed_at,
    )


def data_forge_snapshot_binding_scorecard_gates(
    report: Mapping[str, Any] | None,
    *,
    canary_kind: str,
    serious: bool,
) -> list[dict[str, Any]]:
    """Build scorecard gates for Data Forge snapshot/read-API binding evidence."""

    if not serious and not isinstance(report, Mapping):
        return []
    normalized = normalize_data_forge_snapshot_binding_report(report)
    if normalized.get("status") == "blocked":
        blockers = [
            dict(blocker)
            for blocker in normalized.get("blockers", [])
            if isinstance(blocker, Mapping)
        ]
        if blockers:
            status = "fail" if serious else "warn"
            return [
                {
                    "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                    "stage": "materialization",
                    "code": str(
                        blocker.get("code") or "data_forge_snapshot_binding_blocked"
                    ),
                    "status": status,
                    "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
                    "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
                    "message": str(
                        blocker.get("message")
                        or "Data Forge snapshot binding emitted a runtime blocker."
                    ),
                    "evidence_ref": str(
                        blocker.get("evidence_ref")
                        or f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                    ),
                    "next_action": str(
                        blocker.get("next_action")
                        or (
                            "Resolve the Data Forge runtime blocker or explicitly "
                            "degrade the serious policy closeout."
                        )
                    ),
                    "blocking": serious,
                }
                for blocker in blockers
            ]
    issues = [
        dict(issue)
        for issue in normalized.get("issues", [])
        if isinstance(issue, Mapping)
    ]
    if not issues:
        return [
            {
                "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                "stage": "materialization",
                "code": DATA_FORGE_SNAPSHOT_BINDING_GATE,
                "status": "pass",
                "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
                "phase": DATA_FORGE_SNAPSHOT_BINDING_PHASE,
                "message": (
                    "Data Forge legal, catalog, academic, and domain snapshots are "
                    "bound to manifests, artifact ids, quality gates, and read APIs."
                ),
                "evidence_ref": (
                    f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                    if isinstance(report, Mapping)
                    else None
                ),
                "next_action": None,
                "blocking": False,
            }
        ]
    status = "fail" if serious else "warn"
    return [
        {
            "name": DATA_FORGE_SNAPSHOT_BINDING_GATE,
            "stage": "materialization",
            "code": str(issue.get("code") or DATA_FORGE_SNAPSHOT_BINDING_GATE),
            "status": status,
            "layer": DATA_FORGE_SNAPSHOT_BINDING_LAYER,
            "phase": str(issue.get("phase") or DATA_FORGE_SNAPSHOT_BINDING_PHASE),
            "message": str(issue.get("message") or "Data Forge snapshot binding failed."),
            "evidence_ref": (
                f"quality_evidence/{DATA_FORGE_SNAPSHOT_BINDING_FILE}"
                if isinstance(report, Mapping)
                else None
            ),
            "next_action": str(issue.get("next_action") or ""),
            "blocking": serious,
            "missing_input": str(issue.get("field") or "") or None,
        }
        for issue in issues
    ]


def _report_payload(
    *,
    source: Mapping[str, Any],
    bindings: Sequence[Mapping[str, Any]],
    issues: Sequence[DataForgeSnapshotBindingIssue],
    now: datetime,
    blockers: Sequence[Mapping[str, Any]] = (),
    status_override: str | None = None,
) -> dict[str, Any]:
    payload = dict(source)
    payload["schema_version"] = DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION
    payload["status"] = "fail" if issues else status_override or "pass"
    payload["capability_reality_status"] = "implemented"
    payload["runtime_authority_envelope"] = _authority_envelope()
    payload["observed_at"] = now.isoformat()
    payload["bindings"] = [dict(binding) for binding in bindings]
    if blockers:
        payload["blockers"] = [dict(blocker) for blocker in blockers]
    payload["summary"] = {
        "required_role_count": len(REQUIRED_DATA_FORGE_SNAPSHOT_ROLES),
        "bound_role_count": len(
            {
                str(binding.get("role"))
                for binding in bindings
                if _clean_text(binding.get("role"))
            }
        ),
        "claim_requirement_binding_count": sum(
            len(_claim_requirement_rows(binding)) for binding in bindings
        ),
        "issue_count": len(issues),
    }
    payload["issues"] = [issue.as_dict() for issue in issues]
    return payload


def _binding_rows(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = (
        report.get("bindings")
        or report.get("snapshot_bindings")
        or report.get("snapshots")
    )
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _json_mapping_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [
        {str(key): _json_value(item) for key, item in row.items()}
        for row in value
        if isinstance(row, Mapping)
    ]


def _runtime_blockers(
    report: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[DataForgeSnapshotBindingIssue]]:
    raw_blockers = report.get("blockers") or report.get("runtime_blockers")
    if not isinstance(raw_blockers, list):
        return [], []
    blockers: list[dict[str, Any]] = []
    issues: list[DataForgeSnapshotBindingIssue] = []
    for index, raw_blocker in enumerate(raw_blockers, start=1):
        if not isinstance(raw_blocker, Mapping):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_invalid",
                    role="report",
                    field=f"blockers[{index}]",
                    message="Data Forge runtime blocker must be a mapping.",
                )
            )
            continue
        blocker = {str(key): _json_value(value) for key, value in raw_blocker.items()}
        blockers.append(blocker)
        if not _clean_text(blocker.get("code")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_code_missing",
                    role="report",
                    field=f"blockers[{index}].code",
                    message="Data Forge runtime blocker is missing a code.",
                )
            )
        if not _clean_text(blocker.get("message") or blocker.get("downstream_impact")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_message_missing",
                    role="report",
                    field=f"blockers[{index}].message",
                    message="Data Forge runtime blocker is missing a message.",
                )
            )
        if _clean_text(blocker.get("provenance_kind")) != "runtime_blocker":
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_provenance_invalid",
                    role="report",
                    field=f"blockers[{index}].provenance_kind",
                    message=(
                        "Data Forge blockers must be emitted with "
                        "provenance_kind=runtime_blocker."
                    ),
                    value=blocker.get("provenance_kind"),
                )
            )
        evidence_ref = _clean_text(blocker.get("evidence_ref") or blocker.get("cas_ref"))
        if not _looks_artifact_ref(evidence_ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_evidence_ref_missing",
                    role="report",
                    field=f"blockers[{index}].evidence_ref",
                    message=(
                        "Data Forge runtime blocker must cite a CAS/artifact evidence ref."
                    ),
                    value=evidence_ref,
                )
            )
        runtime_event_ref = _clean_text(blocker.get("runtime_event_ref"))
        if not _looks_runtime_event_ref(runtime_event_ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_runtime_blocker_event_ref_missing",
                    role="report",
                    field=f"blockers[{index}].runtime_event_ref",
                    message="Data Forge runtime blocker must cite a runtime event ref.",
                    value=runtime_event_ref,
                )
            )
    return blockers, issues


def _binding_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
    now: datetime,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    expected_surface = DATA_FORGE_SNAPSHOT_ROLE_SURFACES.get(role)
    surface = _clean_text(binding.get("read_api_surface"))
    module = _clean_text(binding.get("read_api_module"))
    snapshot_id = _clean_text(binding.get("snapshot_id"))

    if role not in REQUIRED_DATA_FORGE_SNAPSHOT_ROLES:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_role_unknown",
                role=role,
                field="role",
                message=(
                    "Data Forge snapshot binding role must be one of legal, catalog, "
                    "academic, or domain."
                ),
                value=role,
            )
        )
    if not snapshot_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_id_missing",
                role=role,
                field="snapshot_id",
                message="Data Forge snapshot binding is missing snapshot_id.",
            )
        )
    issues.extend(_official_identity_issues(binding=binding, role=role))

    if not surface:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_missing",
                role=role,
                field="read_api_surface",
                message="Data Forge snapshot binding is missing read_api_surface.",
            )
        )
    elif surface not in available_surfaces():
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_unknown",
                role=role,
                field="read_api_surface",
                message=f"Data Forge read_api surface {surface!r} is not registered.",
                value=surface,
            )
        )
    elif expected_surface is not None and surface != expected_surface:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_surface_mismatch",
                role=role,
                field="read_api_surface",
                message=(
                    f"Data Forge role {role!r} must bind to read_api surface "
                    f"{expected_surface!r}."
                ),
                value=surface,
            )
        )
    elif module and module != surface_module(surface):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_module_mismatch",
                role=role,
                field="read_api_module",
                message=(
                    f"Data Forge read_api module for surface {surface!r} does not "
                    "match the registered surface module."
                ),
                value=module,
            )
        )

    issues.extend(_manifest_issues(binding=binding, role=role))
    issues.extend(_artifact_issues(binding=binding, role=role))
    issues.extend(_quality_gate_issues(binding=binding, role=role))
    issues.extend(_provenance_manifest_issues(binding=binding, role=role))
    issues.extend(_lineage_issues(binding=binding, role=role))
    issues.extend(_claim_requirement_issues(binding=binding, role=role))
    freshness_issue = _freshness_issue(binding=binding, role=role, now=now)
    if freshness_issue is not None:
        issues.append(freshness_issue)
    return issues


def _official_identity_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    release_id = _clean_text(binding.get("release_id"))
    release_manifest_ref = _clean_text(binding.get("release_manifest_ref"))
    merkle = _clean_text(binding.get("merkle_root") or binding.get("merkle_hash"))
    data_hash = _clean_text(binding.get("data_hash") or binding.get("content_hash"))
    read_api_identity = _clean_text(binding.get("read_api_identity"))
    surface = _clean_text(binding.get("read_api_surface"))
    runtime_event_ref = _clean_text(
        binding.get("runtime_event_ref") or binding.get("release_event_ref")
    )
    if not release_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_id_missing",
                role=role,
                field="release_id",
                message="Data Forge snapshot binding is missing official release_id.",
            )
        )
    if _looks_local_path(release_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_manifest_local_path_substitution",
                role=role,
                field="release_manifest_ref",
                message=(
                    "Data Forge release manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=release_manifest_ref,
            )
        )
    elif not _looks_artifact_ref(release_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_release_manifest_ref_missing",
                role=role,
                field="release_manifest_ref",
                message="Data Forge snapshot binding is missing release manifest identity.",
            )
        )
    if not _looks_sha256_hex(merkle):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_merkle_root_missing",
                role=role,
                field="merkle_root",
                message="Data Forge snapshot binding is missing a sha256 Merkle root.",
                value=merkle,
            )
        )
    if _looks_local_path(data_hash):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_data_hash_local_path_substitution",
                role=role,
                field="data_hash",
                message=(
                    "Data Forge snapshot data hash must be hash identity, not a local "
                    "filesystem path."
                ),
                value=data_hash,
            )
        )
    elif not _looks_hash_ref(data_hash):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_data_hash_missing",
                role=role,
                field="data_hash",
                message="Data Forge snapshot binding is missing data hash identity.",
                value=data_hash,
            )
        )
    if not read_api_identity:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_identity_missing",
                role=role,
                field="read_api_identity",
                message="Data Forge snapshot binding is missing read_api_identity.",
            )
        )
    elif surface and not read_api_identity.startswith(f"{surface}@"):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_read_api_identity_mismatch",
                role=role,
                field="read_api_identity",
                message="Data Forge read_api_identity must be scoped to read_api_surface.",
                value=read_api_identity,
            )
        )
    if not _looks_runtime_event_ref(runtime_event_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_runtime_event_ref_missing",
                role=role,
                field="runtime_event_ref",
                message="Data Forge snapshot binding is missing a persisted runtime event ref.",
                value=runtime_event_ref,
            )
        )
    return issues


def _manifest_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    manifest_ref = _clean_text(binding.get("manifest_ref"))
    manifest_artifact_id = _clean_text(
        binding.get("manifest_artifact_id") or binding.get("manifest_artifact_ref")
    )
    manifest_path = _clean_text(binding.get("manifest_path"))
    if _looks_local_path(manifest_ref) or (
        not manifest_ref and _looks_local_path(manifest_path)
    ):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_manifest_local_path_substitution",
                role=role,
                field="manifest_ref",
                message=(
                    "Data Forge snapshot manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=manifest_ref or manifest_path,
            )
        )
    if not _looks_artifact_ref(manifest_ref) and not _looks_artifact_ref(manifest_artifact_id):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_manifest_ref_missing",
                role=role,
                field="manifest_ref",
                message="Data Forge snapshot binding is missing manifest CAS/artifact identity.",
            )
        )
    return issues


def _artifact_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    refs = _ref_list(binding.get("artifact_ids") or binding.get("artifact_refs"))
    snapshot_ref = _clean_text(binding.get("snapshot_ref"))
    if _looks_local_path(snapshot_ref):
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_ref_local_path_substitution",
                role=role,
                field="snapshot_ref",
                message=(
                    "Data Forge snapshot identity must be a CAS/artifact reference, "
                    "not a local filesystem path."
                ),
                value=snapshot_ref,
            )
        ]
    issues: list[DataForgeSnapshotBindingIssue] = []
    if not _looks_artifact_ref(snapshot_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_ref_missing",
                role=role,
                field="snapshot_ref",
                message="Data Forge snapshot binding is missing snapshot_ref.",
            )
        )
    if not refs:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_artifact_ids_missing",
                role=role,
                field="artifact_ids",
                message="Data Forge snapshot binding is missing published artifact ids.",
            )
        )
        return issues
    for ref in refs:
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_artifact_local_path_substitution",
                    role=role,
                    field="artifact_ids",
                    message=(
                        "Data Forge snapshot artifact identities must be CAS/artifact "
                        "references, not local filesystem paths."
                    ),
                    value=ref,
                )
            )
        elif not _looks_artifact_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_artifact_id_invalid",
                    role=role,
                    field="artifact_ids",
                    message="Data Forge snapshot artifact id is not a recognized artifact ref.",
                    value=ref,
                )
            )
    return issues


def _quality_gate_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    raw_gates = binding.get("quality_gates") or binding.get("quality_gate_refs")
    if not isinstance(raw_gates, list) or not raw_gates:
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_quality_gate_missing",
                role=role,
                field="quality_gates",
                message="Data Forge snapshot binding is missing quality gate evidence.",
            )
        ]
    issues: list[DataForgeSnapshotBindingIssue] = []
    for index, raw_gate in enumerate(raw_gates, start=1):
        if isinstance(raw_gate, Mapping):
            gate = raw_gate
            status = str(gate.get("status") or gate.get("result") or "").casefold()
            ref = _clean_text(
                gate.get("artifact_id")
                or gate.get("artifact_ref")
                or gate.get("quality_gate_ref")
            )
            name = _clean_text(gate.get("name")) or f"quality_gates[{index}]"
        else:
            status = "pass"
            ref = _clean_text(raw_gate)
            name = f"quality_gates[{index}]"
        if status not in _PASS_STATUSES:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_failed",
                    role=role,
                    field=f"quality_gates[{index}].status",
                    message=f"Data Forge snapshot quality gate {name!r} is not passing.",
                    value=status,
                )
            )
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_local_path_substitution",
                    role=role,
                    field=f"quality_gates[{index}].artifact_id",
                    message=(
                        "Data Forge quality gate identity must be a CAS/artifact "
                        "reference, not a local filesystem path."
                    ),
                    value=ref,
                )
            )
        elif not _looks_artifact_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_quality_gate_artifact_missing",
                    role=role,
                    field=f"quality_gates[{index}].artifact_id",
                    message=(
                        f"Data Forge snapshot quality gate {name!r} is missing an "
                        "artifact identity."
                    ),
                )
            )
    return issues


def _lineage_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    prov = binding.get("prov") or binding.get("prov_lineage")
    openlineage = binding.get("openlineage") or binding.get("openlineage_lineage")
    if not isinstance(prov, Mapping):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_prov_lineage_missing",
                role=role,
                field="prov",
                message="Data Forge snapshot binding is missing PROV lineage.",
            )
        )
    else:
        missing = [
            field
            for field in ("entity", "activity", "agent")
            if not _clean_text(prov.get(field))
        ]
        if missing:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_prov_lineage_incomplete",
                    role=role,
                    field="prov",
                    message="Data Forge PROV lineage is missing entity, activity, or agent.",
                    value=missing,
                )
            )
    if not isinstance(openlineage, Mapping):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_openlineage_missing",
                role=role,
                field="openlineage",
                message="Data Forge snapshot binding is missing OpenLineage lineage.",
            )
        )
    else:
        job = openlineage.get("job")
        run = openlineage.get("run")
        outputs = openlineage.get("outputs")
        if not _clean_text(openlineage.get("namespace")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_namespace_missing",
                    role=role,
                    field="openlineage.namespace",
                    message="Data Forge OpenLineage payload is missing namespace.",
                )
            )
        if not isinstance(job, Mapping) or not _clean_text(job.get("name")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_job_missing",
                    role=role,
                    field="openlineage.job",
                    message="Data Forge OpenLineage payload is missing job identity.",
                )
            )
        if not isinstance(run, Mapping) or not _clean_text(run.get("runId")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_run_missing",
                    role=role,
                    field="openlineage.run",
                    message="Data Forge OpenLineage payload is missing run identity.",
                )
            )
        if not isinstance(outputs, list) or not outputs:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_outputs_missing",
                    role=role,
                    field="openlineage.outputs",
                    message="Data Forge OpenLineage payload is missing output datasets.",
                )
            )
        elif not _openlineage_outputs_have_hash_facets(outputs):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_openlineage_hash_facets_missing",
                    role=role,
                    field="openlineage.outputs[].facets",
                    message=(
                        "Data Forge OpenLineage outputs must preserve dataHash and "
                        "merkleRoot facets."
                    ),
                )
            )
    return issues


def _claim_requirement_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    rows = _claim_requirement_rows(binding)
    if not rows:
        return [
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_claim_requirement_binding_missing",
                role=role,
                field="claim_requirement_bindings",
                message=(
                    "Data Forge snapshot binding is missing claim requirement bindings; "
                    "file availability cannot satisfy closeout-grade data authority."
                ),
            )
        ]

    issues: list[DataForgeSnapshotBindingIssue] = []
    authority_refs = set(_binding_authority_refs(binding))
    for index, row in enumerate(rows, start=1):
        claim_id = _clean_text(row.get("claim_id"))
        requirement_id = _clean_text(row.get("requirement_id"))
        requirement_kind = _clean_text(row.get("requirement_kind"))
        authority_level = _clean_text(row.get("authority_level"))
        time_role = _clean_text(row.get("time_role"))
        supported_by = _ref_list(row.get("supported_by") or row.get("supported_by_refs"))
        lifecycle_refs = _ref_list(row.get("lifecycle_dependency_refs"))
        if not claim_id:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_claim_id_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].claim_id",
                    message="Data Forge claim requirement binding is missing claim_id.",
                )
            )
        if not requirement_id:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_id_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_id",
                    message="Data Forge claim requirement binding is missing requirement_id.",
                )
            )
        if not requirement_kind:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_kind_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_kind",
                    message=(
                        "Data Forge claim requirement binding is missing requirement_kind."
                    ),
                )
            )
        elif requirement_kind.casefold() in _BROAD_REQUIREMENT_KINDS:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_broad_label",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].requirement_kind",
                    message=(
                        "Broad dataset labels are context only and cannot satisfy "
                        "claim data requirements."
                    ),
                    value=requirement_kind,
                )
            )
        if not authority_level or authority_level.casefold() in {"context", "context_only"}:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_authority_level_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].authority_level",
                    message=(
                        "Data Forge claim requirement binding must declare a non-context "
                        "authority level."
                    ),
                    value=authority_level,
                )
            )
        if not time_role or time_role.casefold() not in _TIME_ROLES:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_time_role_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].time_role",
                    message=(
                        "Data Forge claim requirement binding must declare an explicit "
                        "time role."
                    ),
                    value=time_role,
                )
            )
        if not supported_by:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_support_ref_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].supported_by",
                    message=(
                        "Data Forge claim requirement binding must cite snapshot, "
                        "manifest, or artifact refs."
                    ),
                )
            )
        for ref in supported_by:
            if _looks_local_path(ref) or ref.casefold() in {"dataset", "datasets", "bundle"}:
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_broad_label",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].supported_by",
                        message=(
                            "Claim requirement support must cite official Data Forge "
                            "artifact identity, not a broad dataset label."
                        ),
                        value=ref,
                    )
                )
            elif not _looks_artifact_ref(ref) or ref not in authority_refs:
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_support_ref_invalid",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].supported_by",
                        message=(
                            "Claim requirement support ref must be one of the official "
                            "snapshot, manifest, release, or artifact refs in the binding."
                        ),
                        value=ref,
                    )
                )
        if not lifecycle_refs:
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_claim_requirement_lifecycle_ref_missing",
                    role=role,
                    field=f"claim_requirement_bindings[{index}].lifecycle_dependency_refs",
                    message=(
                        "Data Forge claim requirement binding must cite lifecycle "
                        "dependency refs for reissue checks."
                    ),
                )
            )
        for ref in lifecycle_refs:
            if not _looks_runtime_event_ref(ref):
                issues.append(
                    DataForgeSnapshotBindingIssue(
                        code="data_forge_snapshot_claim_requirement_lifecycle_ref_invalid",
                        role=role,
                        field=f"claim_requirement_bindings[{index}].lifecycle_dependency_refs",
                        message="Lifecycle dependency refs must be event or artifact refs.",
                        value=ref,
                    )
                )
    return issues


def official_data_forge_snapshot_for_claim(
    report: Mapping[str, Any] | None,
    *,
    claim_id: str,
    requirement_id: str | None = None,
    now: datetime | None = None,
) -> OfficialSnapshotAnswer:
    """Return the official Data Forge snapshot satisfying a claim requirement."""

    normalized = normalize_data_forge_snapshot_binding_report(
        report,
        now=_official_snapshot_evaluation_time(report, now=now),
    )
    issues_by_role: dict[str, str] = {}
    for raw_issue in normalized.get("issues", []):
        if not isinstance(raw_issue, Mapping):
            continue
        role = _clean_text(raw_issue.get("role"))
        code = _clean_text(raw_issue.get("code"))
        if role and code:
            issues_by_role.setdefault(role, code)

    for binding in _binding_rows(normalized):
        role = _clean_text(binding.get("role"))
        answer = _official_snapshot_answer_from_binding(
            binding,
            claim_id=claim_id,
            requirement_id=requirement_id,
            blocked_reason=issues_by_role.get(role or ""),
        )
        if answer is not None:
            return answer
    return OfficialSnapshotAnswer(
        status="not_found",
        claim_id=claim_id,
        requirement_id=requirement_id,
        reason="claim_requirement_binding_missing",
    )


def _official_snapshot_evaluation_time(
    report: Mapping[str, Any] | None,
    *,
    now: datetime | None,
) -> datetime | None:
    if now is not None:
        return _utc(now)
    if not isinstance(report, Mapping):
        return None
    return _parse_datetime(report.get("observed_at"))


def _official_snapshot_answer_from_binding(
    binding: Mapping[str, Any],
    *,
    claim_id: str,
    requirement_id: str | None = None,
    blocked_reason: str | None = None,
) -> OfficialSnapshotAnswer | None:
    for row in _claim_requirement_rows(binding):
        row_claim_id = _clean_text(row.get("claim_id"))
        row_requirement_id = _clean_text(row.get("requirement_id"))
        if row_claim_id != claim_id:
            continue
        if requirement_id is not None and row_requirement_id != requirement_id:
            continue
        return OfficialSnapshotAnswer(
            status="blocked" if blocked_reason else "satisfied",
            claim_id=claim_id,
            requirement_id=requirement_id or row_requirement_id,
            role=_clean_text(binding.get("role")),
            corpus_id=_clean_text(binding.get("corpus_id")),
            snapshot_id=_clean_text(binding.get("snapshot_id")),
            snapshot_ref=_clean_text(binding.get("snapshot_ref")),
            data_hash=_clean_text(binding.get("data_hash")),
            creation_time=_clean_text(binding.get("creation_time")),
            lineage_refs=tuple(_ref_list(binding.get("lineage_refs"))),
            quality_gates=tuple(_json_mapping_rows(binding.get("quality_gates"))),
            builder_revision=_clean_text(binding.get("builder_revision")),
            transform_lineage=tuple(
                _json_mapping_rows(binding.get("transform_lineage"))
            ),
            supported_by=tuple(_ref_list(row.get("supported_by"))),
            lifecycle_dependency_refs=tuple(
                _ref_list(row.get("lifecycle_dependency_refs"))
            ),
            reason=blocked_reason,
        )
    return None


def _provenance_manifest_issues(
    *,
    binding: Mapping[str, Any],
    role: str,
) -> list[DataForgeSnapshotBindingIssue]:
    issues: list[DataForgeSnapshotBindingIssue] = []
    corpus_id = _clean_text(binding.get("corpus_id"))
    provenance_manifest_ref = _clean_text(binding.get("provenance_manifest_ref"))
    creation_time = binding.get("creation_time")
    lineage_refs = _ref_list(binding.get("lineage_refs"))
    builder_revision = _clean_text(binding.get("builder_revision"))
    transform_lineage = binding.get("transform_lineage")

    if not corpus_id:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_corpus_id_missing",
                role=role,
                field="corpus_id",
                message="Data Forge snapshot provenance manifest is missing corpus_id.",
            )
        )
    if _looks_local_path(provenance_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_provenance_manifest_local_path_substitution",
                role=role,
                field="provenance_manifest_ref",
                message=(
                    "Data Forge provenance manifest authority must be a CAS/artifact "
                    "reference, not a local filesystem path."
                ),
                value=provenance_manifest_ref,
            )
        )
    elif not _looks_artifact_ref(provenance_manifest_ref):
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_provenance_manifest_ref_missing",
                role=role,
                field="provenance_manifest_ref",
                message=(
                    "Data Forge snapshot binding is missing durable provenance "
                    "manifest identity."
                ),
                value=provenance_manifest_ref,
            )
        )
    if _parse_datetime(creation_time) is None:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_creation_time_missing",
                role=role,
                field="creation_time",
                message=(
                    "Data Forge provenance manifest must preserve snapshot creation_time."
                ),
                value=creation_time,
            )
        )
    if not lineage_refs:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_lineage_refs_missing",
                role=role,
                field="lineage_refs",
                message=(
                    "Data Forge provenance manifest must preserve source lineage refs."
                ),
            )
        )
    for index, ref in enumerate(lineage_refs, start=1):
        if _looks_local_path(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_lineage_ref_local_path_substitution",
                    role=role,
                    field=f"lineage_refs[{index}]",
                    message=(
                        "Data Forge lineage refs must be artifact/event refs, not local "
                        "filesystem paths."
                    ),
                    value=ref,
                )
            )
        elif not _looks_lineage_ref(ref):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_lineage_ref_invalid",
                    role=role,
                    field=f"lineage_refs[{index}]",
                    message="Data Forge lineage ref is not a recognized durable ref.",
                    value=ref,
                )
            )
    if not builder_revision:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_builder_revision_missing",
                role=role,
                field="builder_revision",
                message=(
                    "Data Forge provenance manifest is missing builder_revision."
                ),
            )
        )
    if not isinstance(transform_lineage, list) or not transform_lineage:
        issues.append(
            DataForgeSnapshotBindingIssue(
                code="data_forge_snapshot_transform_lineage_missing",
                role=role,
                field="transform_lineage",
                message=(
                    "Data Forge provenance manifest is missing transform lineage."
                ),
            )
        )
        return issues
    for index, step in enumerate(transform_lineage, start=1):
        if not isinstance(step, Mapping):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_step_invalid",
                    role=role,
                    field=f"transform_lineage[{index}]",
                    message="Data Forge transform lineage step must be a mapping.",
                )
            )
            continue
        if not _clean_text(step.get("step_id")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_step_id_missing",
                    role=role,
                    field=f"transform_lineage[{index}].step_id",
                    message="Data Forge transform lineage step is missing step_id.",
                )
            )
        if not _clean_text(step.get("operation")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_operation_missing",
                    role=role,
                    field=f"transform_lineage[{index}].operation",
                    message="Data Forge transform lineage step is missing operation.",
                )
            )
        if not _ref_list(step.get("input_refs")) and not _ref_list(step.get("output_refs")):
            issues.append(
                DataForgeSnapshotBindingIssue(
                    code="data_forge_snapshot_transform_lineage_refs_missing",
                    role=role,
                    field=f"transform_lineage[{index}]",
                    message=(
                        "Data Forge transform lineage step must cite input or output refs."
                    ),
                )
            )
    return issues


def _freshness_issue(
    *,
    binding: Mapping[str, Any],
    role: str,
    now: datetime,
) -> DataForgeSnapshotBindingIssue | None:
    published_at = _parse_datetime(
        binding.get("published_at")
        or binding.get("snapshot_created_at")
        or binding.get("as_of")
    )
    if published_at is None:
        return DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_freshness_missing",
            role=role,
            field="published_at",
            message="Data Forge snapshot binding is missing freshness timestamp.",
        )
    ttl_seconds = _positive_int(
        binding.get("freshness_ttl_seconds")
        or binding.get("max_age_seconds")
        or DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS
    )
    if ttl_seconds is None:
        ttl_seconds = DEFAULT_DATA_FORGE_SNAPSHOT_TTL_SECONDS
    if published_at + timedelta(seconds=ttl_seconds) < now:
        return DataForgeSnapshotBindingIssue(
            code="data_forge_snapshot_stale",
            role=role,
            field="published_at",
            message="Data Forge snapshot binding is stale for its freshness TTL.",
            value=published_at.isoformat(),
        )
    return None


def _normalize_binding_surface(binding: dict[str, Any]) -> None:
    role = _clean_text(binding.get("role"))
    surface = _clean_text(binding.get("read_api_surface"))
    if (
        surface
        and not _clean_text(binding.get("read_api_module"))
        and surface in available_surfaces()
    ):
        binding["read_api_module"] = surface_module(surface)
    elif not surface and role in DATA_FORGE_SNAPSHOT_ROLE_SURFACES:
        expected = DATA_FORGE_SNAPSHOT_ROLE_SURFACES[role]
        binding["read_api_surface"] = expected
        binding["read_api_module"] = surface_module(expected)


def _normalize_binding_report_defaults(
    binding: dict[str, Any],
    report: Mapping[str, Any],
) -> None:
    for field in ("release_id", "release_manifest_ref"):
        if not _clean_text(binding.get(field)) and _clean_text(report.get(field)):
            binding[field] = report[field]
    surface = _clean_text(binding.get("read_api_surface"))
    snapshot_id = _clean_text(binding.get("snapshot_id"))
    if surface and snapshot_id and not _clean_text(binding.get("read_api_identity")):
        binding["read_api_identity"] = f"{surface}@{snapshot_id}"


def _claim_requirement_rows(binding: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = binding.get("claim_requirement_bindings") or binding.get("claim_requirements")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _binding_authority_refs(binding: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for field in (
        "snapshot_ref",
        "manifest_ref",
        "manifest_artifact_id",
        "manifest_artifact_ref",
        "release_manifest_ref",
        "provenance_manifest_ref",
        "data_hash",
    ):
        refs.extend(_ref_list(binding.get(field)))
    refs.extend(_ref_list(binding.get("artifact_ids") or binding.get("artifact_refs")))
    refs.extend(_ref_list(binding.get("quality_gates") or binding.get("quality_gate_refs")))
    return tuple(dict.fromkeys(ref for ref in refs if _looks_artifact_ref(ref)))


def _ref_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [_clean_text(value) or ""]
    if not isinstance(value, list | tuple):
        return []
    refs: list[str] = []
    for item in value:
        if isinstance(item, str):
            ref = _clean_text(item)
        elif isinstance(item, Mapping):
            ref = _clean_text(
                item.get("artifact_id")
                or item.get("artifact_ref")
                or item.get("ref")
                or item.get("uri")
            )
        else:
            ref = None
        if ref:
            refs.append(ref)
    return refs


def _openlineage_outputs_have_hash_facets(outputs: Sequence[object]) -> bool:
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        facets = output.get("facets")
        if not isinstance(facets, Mapping):
            continue
        if isinstance(facets.get("dataHash"), Mapping) and isinstance(
            facets.get("merkleRoot"), Mapping
        ):
            return True
    return False


def _looks_artifact_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if text.startswith("sha256:") and len(text) == 71:
        return all(char in "0123456789abcdef" for char in text.removeprefix("sha256:"))
    if text.startswith("cas://sha256/") and len(text) == 77:
        return all(char in "0123456789abcdef" for char in text.removeprefix("cas://sha256/"))
    return text.startswith("artifact://")


def _looks_hash_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _looks_artifact_ref(text) or _looks_sha256_hex(text)


def _looks_sha256_hex(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    if text.startswith("sha256:"):
        text = text.removeprefix("sha256:")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _looks_runtime_event_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return _looks_artifact_ref(text) or text.startswith("event://")


def _looks_lineage_ref(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    return (
        _looks_artifact_ref(text)
        or text.startswith("event://")
        or text.startswith("lineage:")
        or text.startswith("prov:")
        or text.startswith("openlineage:")
    )


def _looks_local_path(value: object) -> bool:
    text = _clean_text(value)
    if text is None:
        return False
    lowered = text.casefold()
    return lowered.startswith(_LOCAL_PATH_PREFIXES) or lowered.startswith(
        ("tests/", "tmp/", "var/folders/")
    )


def _parse_datetime(value: object) -> datetime | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return None
    return text


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    return value


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "official_snapshot_identity",
            "release_manifest_identity",
            "read_api_identity",
            "merkle_and_data_hashes",
            "quality_gate_results",
            "prov_openlineage_lineage",
            "claim_requirement_bindings",
        ),
        "may_not_use_for": (
            "claim_support",
            "legal_authority",
            "method_validity",
            "academic_support_strength",
            "participation_representativeness",
            "source_family_satisfaction_without_fabric_binding",
        ),
    }


__all__ = [
    "DATA_FORGE_SNAPSHOT_BINDING_FILE",
    "DATA_FORGE_SNAPSHOT_BINDING_GATE",
    "DATA_FORGE_SNAPSHOT_BINDING_REPORT_KEY",
    "DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION",
    "WORKSPACE_MEASUREMENT_ROOT_SCHEMA_VERSION",
    "WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION",
    "REQUIRED_DATA_FORGE_SNAPSHOT_ROLES",
    "CatalogGraphProtocol",
    "MeasurementRootBindingError",
    "MeasurementRootProducer",
    "build_default_workspace_catalog_graph",
    "data_forge_snapshot_binding_scorecard_gates",
    "normalize_data_forge_snapshot_binding_report",
    "official_data_forge_snapshot_for_claim",
    "produce_phase2_recorded_panel_measurement_root",
    "source_requirement_for_catalog_binding",
]
