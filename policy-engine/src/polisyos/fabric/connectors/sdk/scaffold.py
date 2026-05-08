"""Scaffold helpers for SourceContract v2 authoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    SourceContract,
    SourceContractDocs,
    SourceContractLineage,
    SourceContractQuality,
    SourceContractReplay,
    SourceContractRetention,
    SourceContractSchema,
    SourceContractSecurity,
    SourceContractSemantics,
    SourceContractSLA,
    SourceContractSource,
    SourceContractTerms,
    SourceContractTrust,
    default_source_field_access_policies,
)
from polisyos.fabric.connectors.profiles.models import SourceProfile
from polisyos.fabric.quality.processing_guarantees import default_processing_contract_for_connector
from polisyos.ir.connectors import ConnectorMetadataSpec

PROFILE_ID_BY_CONNECTOR_ID: dict[str, str] = {
    "worldbank.wdi": "worldbank_wdi",
    "wvs.wave7": "wvs_wave7",
    "eurostat.data": "eurostat_public",
    "ukons.datasets": "ukons_public",
    "sdmx.source": "ecb_sdmx",
    "ckan.catalog": "data_gov_us",
    "ckan.resource": "data_gov_us",
    "socrata.soda": "nyc_opendata",
    "opendatasoft.ods": "opendatasoft_public",
    "sparql.endpoint": "wikidata_sparql",
    "rest.json": "open_meteo",
    "who.indicators": "who_gho",
    "unpd.data": "unpd_dataportal",
    "unesco_uis.data": "unesco_uis_public",
    "files.tabular": "files_demo_tabular",
    "object_storage.blob": "object_storage_demo",
    "sql.query": "sqlite_demo",
    "graphql.api": "graphql_demo",
    "geojson.features": "geojson_demo",
    "stream.jsonl": "stream_jsonl_demo",
}

_SOURCE_TRUST_BY_NAMESPACE = {
    "worldbank": "institutional",
    "eurostat": "government",
    "ukons": "government",
    "who": "institutional",
    "unpd": "institutional",
    "unesco_uis": "institutional",
}


class SourceScaffoldSpec(BaseModel):
    """Inputs needed to scaffold a production source contract and docs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_id: str = Field(..., min_length=1)
    dataset_pattern: str = "*"
    profile_id: str | None = None
    contract_id: str | None = None
    version: str = "1.1.0"
    owner: str = "@fabric-owners"
    reviewer: str = "@fabric-reviewers"
    domain: str = "general_policy_data"
    quality_contract_id: str | None = None
    replay_fixture_ref: str | None = None
    non_replayable_reason: str = (
        "Replay fixture has not been recorded for this migrated source yet."
    )


@dataclass(frozen=True, slots=True)
class SourceScaffoldArtifacts:
    """Generated authoring artifacts for a source connector."""

    contract: SourceContract
    quality_contract: dict[str, Any]
    replay_fixture_id: str
    documentation_stub: str


def make_source_contract_id(connector_id: str, dataset_pattern: str = "*") -> str:
    """Build a stable SourceContract id."""

    dataset = (
        "generic"
        if dataset_pattern in {"", "*"}
        else dataset_pattern.strip().lower().replace("*", "generic")
    )
    normalized = (
        dataset.replace("-", "_").replace("/", ".").replace(" ", "_").replace("..", ".").strip(".")
    )
    if not normalized:
        normalized = "generic"
    if connector_id.endswith(f".{normalized}"):
        return connector_id
    return f"{connector_id}.{normalized}"


def make_source_profile_id(connector_id: str) -> str:
    """Resolve the canonical profile id for a connector id."""

    if connector_id in PROFILE_ID_BY_CONNECTOR_ID:
        return PROFILE_ID_BY_CONNECTOR_ID[connector_id]
    return connector_id.replace(".", "_")


def make_quality_contract_id(contract_id: str) -> str:
    """Build a default quality contract id for a SourceContract."""

    return f"fabric.quality.{contract_id}.v1"


def make_replay_fixture_id(contract_id: str) -> str:
    """Build a stable replay fixture path for source authoring."""

    return f"tests/_data/fabric/shared/source_contracts/{contract_id}.replay.json"


def make_source_doc_stub(contract: SourceContract) -> str:
    """Render a compact reference stub suitable for source-platform docs."""

    replay = contract.replay.fixture_ref or contract.replay.non_replayable_reason or ""
    return "\n".join(
        [
            f"### `{contract.id}`",
            "",
            f"- Source: {contract.source.source_name or contract.source.connector_id}",
            f"- Organization: {contract.source.source_organization or 'unknown'}",
            f"- Connector: `{contract.source.connector_id}`",
            f"- Profile: `{contract.source.profile_id}`",
            f"- Owner/reviewer: `{contract.owner}` / `{contract.reviewer}`",
            f"- Classification: `{contract.security.classification}`",
            f"- Quality contract: `{contract.quality.contract_ref}`",
            f"- Replay: `{replay}`",
            f"- Processing guarantee: `{contract.processing.guarantee_value}`, "
            f"dedupe window `{contract.processing.idempotency.dedupe_window_seconds}s`, "
            f"replay retention `{contract.processing.idempotency.replay_retention_days}d`",
            f"- SLO: availability `{contract.sla.availability_target:.3f}`, "
            f"freshness `{contract.sla.freshness_slo_seconds}s`, "
            f"p95 latency `{contract.sla.p95_latency_ms:.0f}ms`",
        ]
    )


def build_source_contract_scaffold(
    *,
    metadata: ConnectorMetadataSpec,
    schema_contract: ConnectorSchemaContract | None = None,
    spec: SourceScaffoldSpec | None = None,
) -> SourceContract:
    """Build a SourceContract v2 scaffold from connector metadata."""

    connector_id = f"{metadata.namespace}.{metadata.connector_id}"
    resolved = spec or SourceScaffoldSpec(
        connector_id=connector_id,
        owner=metadata.owner,
        quality_contract_id=metadata.quality_contract_id,
    )
    profile_id = resolved.profile_id or make_source_profile_id(resolved.connector_id)
    contract_id = resolved.contract_id or make_source_contract_id(
        resolved.connector_id,
        resolved.dataset_pattern,
    )
    quality_ref = (
        resolved.quality_contract_id
        or metadata.quality_contract_id
        or make_quality_contract_id(contract_id)
    )

    if schema_contract is not None:
        return SourceContract.from_connector_schema_contract(
            schema_contract,
            metadata=metadata,
            profile_id=profile_id,
            owner=resolved.owner or metadata.owner,
            reviewer=resolved.reviewer,
            version=resolved.version,
            domain=resolved.domain,
            replay_fixture_ref=resolved.replay_fixture_ref,
            non_replayable_reason=resolved.non_replayable_reason,
        )

    replay_required = resolved.replay_fixture_ref is not None
    schema_ref = metadata.schema_registry_ref
    schema_id = metadata.schema_id
    return SourceContract(
        id=contract_id,
        version=resolved.version,
        owner=resolved.owner or metadata.owner,
        reviewer=resolved.reviewer,
        source=SourceContractSource(
            connector_id=resolved.connector_id,
            dataset_pattern=resolved.dataset_pattern,
            profile_id=profile_id,
            source_name=metadata.source_name,
            source_organization=metadata.source_organization,
            source_url=metadata.source_url,
        ),
        schema=SourceContractSchema(
            schema_id=schema_id,
            schema_version="1.0.0" if schema_id else None,
            schema_contract_ref=schema_ref,
            compatibility_status=(
                "template_only"
                if metadata.schema_id_template
                else "pending_profile_specific_schema"
            ),
        ),
        semantics=SourceContractSemantics(domain=resolved.domain),
        security=SourceContractSecurity(
            classification=metadata.data_classification,  # type: ignore[arg-type]
            field_policies=default_source_field_access_policies(
                (),
                classification=metadata.data_classification,  # type: ignore[arg-type]
            ),
        ),
        quality=SourceContractQuality(
            contract_ref=quality_ref,
            required_checks=(
                "schema_compliance",
                "finite_values",
                "freshness",
                "safe_filters",
                "bounded_reads",
            ),
        ),
        sla=SourceContractSLA.from_metadata(metadata),
        terms=SourceContractTerms(
            terms_url=metadata.source_url,
            attribution_required=bool(metadata.source_organization),
        ),
        replay=SourceContractReplay(
            required=replay_required,
            fixture_ref=resolved.replay_fixture_ref,
            non_replayable_reason=None if replay_required else resolved.non_replayable_reason,
            determinism_key=metadata.schema_id_template or metadata.schema_id,
        ),
        lineage=SourceContractLineage(seed_node_kind="source_dataset"),
        source_trust=SourceContractTrust(
            tier=_SOURCE_TRUST_BY_NAMESPACE.get(metadata.namespace, "institutional"),  # type: ignore[arg-type]
            calibration_status="heuristic",
            rationale="Scaffolded from connector metadata.",
        ),
        processing=default_processing_contract_for_connector(resolved.connector_id),
        retention=SourceContractRetention(policy="source_terms_bound"),
        docs=SourceContractDocs(generated_anchor=contract_id.replace(".", "-")),
    )


def scaffold_source_artifacts(
    *,
    metadata: ConnectorMetadataSpec,
    schema_contract: ConnectorSchemaContract | None = None,
    spec: SourceScaffoldSpec | None = None,
) -> SourceScaffoldArtifacts:
    """Generate contract, quality contract, replay id, and docs stub."""

    contract = build_source_contract_scaffold(
        metadata=metadata,
        schema_contract=schema_contract,
        spec=spec,
    )
    quality_contract = {
        "schema_version": "fabric.quality_contract.v1",
        "contract_id": contract.quality.contract_ref,
        "source_contract_id": contract.id,
        "required_checks": list(contract.quality.required_checks),
        "min_quality_score": contract.quality.min_quality_score,
    }
    return SourceScaffoldArtifacts(
        contract=contract,
        quality_contract=quality_contract,
        replay_fixture_id=contract.replay.fixture_ref or make_replay_fixture_id(contract.id),
        documentation_stub=make_source_doc_stub(contract),
    )


def build_source_profile_matrix(
    contracts: list[SourceContract] | tuple[SourceContract, ...],
    profiles: list[SourceProfile] | tuple[SourceProfile, ...],
) -> list[dict[str, Any]]:
    """Build a source profile compatibility matrix."""

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    rows: list[dict[str, Any]] = []
    for contract in sorted(contracts, key=lambda item: item.id):
        profile = profiles_by_id.get(contract.source.profile_id)
        rows.append(
            {
                "source_contract_id": contract.id,
                "connector_id": contract.source.connector_id,
                "profile_id": contract.source.profile_id,
                "profile_present": profile is not None,
                "connector_family": profile.connector_family if profile else "",
                "schema_preflight": bool(profile.schema_preflight) if profile else False,
                "supports_async_fetch": bool(profile.supports_async_fetch) if profile else False,
                "max_concurrency": profile.max_concurrency if profile else None,
            }
        )
    return rows
