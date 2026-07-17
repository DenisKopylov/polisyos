"""Lazy, content-addressed HTTP projections of governed repository artifacts."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

_PROJECTION_BASE_PATH = "/api/v1/exports/governed-projections"


class AudienceClass(StrEnum):
    """Declare the intended consumer class without enforcing it in DS3."""

    REVIEWER = "REVIEWER"
    EXPERT = "EXPERT"
    MACHINE = "MACHINE"


class ProjectionAvailability(StrEnum):
    """Describe whether a governed source can back a projection."""

    AVAILABLE = "available"
    ARTIFACT_MISSING = "artifact_missing"
    INVALID_SOURCE = "invalid_source"


class ProjectionId(StrEnum):
    """Stable addresses for the DS3 governed projection denominator."""

    DEPTH_N_CYCLE_BOARD = "depth-n-cycle-board"
    VALUE_GATE = "value-gate"
    GENERATION_CYCLE_DISPOSITION = "generation-cycle-disposition"
    ENGINE_CENSUS = "engine-census"
    FORK_B_RELATION_CENSUS = "fork-b-relation-census"
    ACQUISITION_ROUTING_CONTRACT = "acquisition-routing-contract"
    N13A_ACQUISITION_CENSUS = "n13a-acquisition-census"
    N13A_LIVE_PROBE_JOURNAL = "n13a-live-probe-journal"
    CAPABILITY_REALITY = "capability-reality"
    CLUSTER_OWNERSHIP = "cluster-ownership"
    LAYER3_HEALTH_METRICS = "layer3-health-metrics"
    LEGACY_PROVING_GROUND = "legacy-proving-ground"
    SURFACE_READINESS = "surface-readiness"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectionSourceIdentity(_StrictModel):
    """Bind a packet to the exact source bytes observed by the producer."""

    relative_path: str
    artifact_content_hash: str
    declared_content_hash: str | None = None


class ProjectionFreshness(_StrictModel):
    """Separate source time from the time the HTTP producer observed it."""

    state: Literal["observed", "artifact_missing", "invalid_source"]
    basis: Literal["source_timestamp", "filesystem_mtime", "request_observation"]
    observed_at: datetime
    source_as_of: datetime | None = None


class ProjectionCatalogEntry(_StrictModel):
    """Describe one stable projection without reading its source artifact."""

    projection_id: ProjectionId
    expected_source_path: str
    source_policy: Literal["required", "presence_gated", "fixture_identity_only"]
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    stable_address: str


class GovernedProjectionPacket(_StrictModel):
    """Typed, replayable export packet shared by later MACHINE twins."""

    packet_schema_version: Literal["policyos.runtime.governed_projection_packet.v1"] = (
        "policyos.runtime.governed_projection_packet.v1"
    )
    projection_id: ProjectionId
    availability: ProjectionAvailability
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]
    source: ProjectionSourceIdentity | None = None
    source_schema_version: str | None = None
    source_rule_version: str | None = None
    projection_hash: str | None = None
    as_of: datetime
    freshness: ProjectionFreshness
    stable_address: str
    replay_address: str | None = None
    payload: dict[str, Any] | None = None
    absence_reason: str | None = None


class ProjectionCatalogResponse(_StrictModel):
    """Return the complete DS3 producer denominator."""

    schema_version: Literal["policyos.runtime.governed_projection_catalog.v1"] = (
        "policyos.runtime.governed_projection_catalog.v1"
    )
    projections: tuple[ProjectionCatalogEntry, ...]


class ChannelRegistryEntry(_StrictModel):
    """Govern a non-OpenAPI realtime channel and its existing security contract."""

    registry_id: str
    path_template: str
    transport: Literal["sse", "websocket"]
    channels: tuple[str, ...] = ()
    message_contract: str
    auth_class: str
    consumers: tuple[str, ...] = Field(min_length=1)
    owner: str
    include_in_schema: Literal[False] = False
    status: Literal["active"] = "active"


class ChannelRegistryResponse(_StrictModel):
    """Return all active hidden runtime channels."""

    schema_version: Literal["policyos.runtime.channel_registry.v1"] = (
        "policyos.runtime.channel_registry.v1"
    )
    channels: tuple[ChannelRegistryEntry, ...]


CHANNEL_REGISTRY: tuple[ChannelRegistryEntry, ...] = (
    ChannelRegistryEntry(
        registry_id="runs-list-live",
        path_template="/api/v1/runs/live",
        transport="sse",
        message_contract="policyos.runtime.runs_list_snapshot.v1",
        auth_class="runtime_tenant_access+stream_rate_limit",
        consumers=("apps/runtime-dashboard:RunsLiveProvider",),
        owner="polisyos.runtime.http.routes.runs",
    ),
    ChannelRegistryEntry(
        registry_id="run-detail-live",
        path_template="/api/v1/runs/{run_id}/live",
        transport="sse",
        message_contract="policyos.runtime.run_detail_snapshot.v1",
        auth_class="runtime_run_tenant_access+stream_rate_limit",
        consumers=("apps/runtime-dashboard:useRunLiveUpdates",),
        owner="polisyos.runtime.http.routes.runs",
    ),
    ChannelRegistryEntry(
        registry_id="review-live",
        path_template="/api/v1/review/live",
        transport="websocket",
        channels=("review.cursor", "review.lock", "review.presence"),
        message_contract="policyos.runtime.review_collaboration_envelope.v1",
        auth_class="runtime_review_socket_auth+tenant_opa_action+stream_rate_limit",
        consumers=("apps/runtime-dashboard:useReviewCollaborationSurface",),
        owner="polisyos.runtime.http.routes.review",
    ),
)


class ReplayPinMismatchError(ValueError):
    """Report that a stable address no longer matches requested replay pins."""

    def __init__(self, field: str, *, expected: str, actual: str | None) -> None:
        self.field = field
        self.expected = expected
        self.actual = actual
        super().__init__(f"{field} replay pin {expected!r} does not match {actual!r}")


class InvalidProjectionSourceError(ValueError):
    """Report a missing owner-recorded field without deriving a replacement."""


@dataclass(frozen=True, slots=True)
class _ProjectionDefinition:
    projection_id: ProjectionId
    source_path: str
    source_format: Literal["json", "toml", "proving_ground"]
    source_policy: Literal["required", "presence_gated", "fixture_identity_only"]
    intended_audience: AudienceClass
    authoritative_for: tuple[str, ...]
    may_not_use_for: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FileObservation:
    relative_path: str
    signature: tuple[int, int]
    content_hash: str
    raw: bytes
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class _LoadedSource:
    relative_path: str
    content_hash: str
    parsed: dict[str, Any]
    modified_at: datetime
    declared_content_hash: str | None


_COMMON_NOT_PUBLIC = (
    "public_claim",
    "publication_authority",
    "audience_authorization",
)

_DEFINITIONS: tuple[_ProjectionDefinition, ...] = (
    _ProjectionDefinition(
        ProjectionId.DEPTH_N_CYCLE_BOARD,
        "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("cycle_board_domain_runs", "terminal_distributions", "recorded_evidence_classes"),
        (*_COMMON_NOT_PUBLIC, "recompute_generation_cycle_semantics"),
    ),
    _ProjectionDefinition(
        ProjectionId.VALUE_GATE,
        "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("value_denominators", "advisor_receipts", "value_outer_set_contract_proofs"),
        (*_COMMON_NOT_PUBLIC, "method_validity"),
    ),
    _ProjectionDefinition(
        ProjectionId.GENERATION_CYCLE_DISPOSITION,
        "architecture/policy_design_case/layer3_gy_generation_cycle_disposition_ledger.json",
        "json",
        "required",
        AudienceClass.EXPERT,
        ("generation_cycle_task_disposition", "known_residuals"),
        _COMMON_NOT_PUBLIC,
    ),
    _ProjectionDefinition(
        ProjectionId.ENGINE_CENSUS,
        "architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json",
        "json",
        "required",
        AudienceClass.EXPERT,
        ("engine_census_summary", "critical_findings"),
        (*_COMMON_NOT_PUBLIC, "row_level_engine_export"),
    ),
    _ProjectionDefinition(
        ProjectionId.FORK_B_RELATION_CENSUS,
        "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("fork_b_relation_counts", "coverage_manifest", "transport_floor"),
        (*_COMMON_NOT_PUBLIC, "relation_table_export"),
    ),
    _ProjectionDefinition(
        ProjectionId.ACQUISITION_ROUTING_CONTRACT,
        "architecture/policy_design_case/layer3_gy_acquisition_contract.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("acquisition_receipts", "fail_closed_acquisition_behavior"),
        (*_COMMON_NOT_PUBLIC, "source_family_satisfaction"),
    ),
    _ProjectionDefinition(
        ProjectionId.N13A_ACQUISITION_CENSUS,
        "architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json",
        "json",
        "presence_gated",
        AudienceClass.MACHINE,
        ("acquisition_family_scorecards", "metric_resolution", "route_evidence"),
        (*_COMMON_NOT_PUBLIC, "closeout_pass"),
    ),
    _ProjectionDefinition(
        ProjectionId.N13A_LIVE_PROBE_JOURNAL,
        "architecture/policy_design_case/layer3_gy_n13a_live_probe_journal.json",
        "json",
        "presence_gated",
        AudienceClass.EXPERT,
        ("live_probe_records", "family_receipts", "selection_plan"),
        (*_COMMON_NOT_PUBLIC, "source_success_inference"),
    ),
    _ProjectionDefinition(
        ProjectionId.CAPABILITY_REALITY,
        "architecture/policy_design_case/capability_reality_report.json",
        "json",
        "required",
        AudienceClass.MACHINE,
        ("reported_capability_readiness", "reported_blockers", "ratchet_integrity"),
        (*_COMMON_NOT_PUBLIC, "recompute_capability_readiness"),
    ),
    _ProjectionDefinition(
        ProjectionId.CLUSTER_OWNERSHIP,
        "architecture/policy_design_case/cluster_ownership_map.toml",
        "toml",
        "required",
        AudienceClass.EXPERT,
        ("cluster_cell_ownership", "ratchet_state", "authority_firewall"),
        (*_COMMON_NOT_PUBLIC, "ownership_reassignment"),
    ),
    _ProjectionDefinition(
        ProjectionId.LAYER3_HEALTH_METRICS,
        "architecture/policy_design_case/layer3_health_metric_ledgers.toml",
        "toml",
        "required",
        AudienceClass.MACHINE,
        ("recorded_health_metric_freezes", "metric_update_rules"),
        (*_COMMON_NOT_PUBLIC, "metric_recomputation"),
    ),
    _ProjectionDefinition(
        ProjectionId.LEGACY_PROVING_GROUND,
        "tests/fixtures/universal-corpus/manifest.json",
        "proving_ground",
        "fixture_identity_only",
        AudienceClass.EXPERT,
        ("legacy_case_identity", "fixture_semantic_expectation"),
        (
            *_COMMON_NOT_PUBLIC,
            "readiness",
            "runtime_outcome",
            "admissibility",
        ),
    ),
    _ProjectionDefinition(
        ProjectionId.SURFACE_READINESS,
        "architecture/atlas_surfaces/surface-readiness-ledger.json",
        "json",
        "presence_gated",
        AudienceClass.MACHINE,
        ("validated_surface_readiness_entries",),
        (*_COMMON_NOT_PUBLIC, "derive_readiness_from_route_presence"),
    ),
)

_DEFINITION_BY_ID = {definition.projection_id: definition for definition in _DEFINITIONS}


class GovernedProjectionService:
    """Project governed files lazily and cache their parsed content by SHA-256."""

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root
        self._path_cache: dict[Path, _FileObservation] = {}
        self._parsed_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._projection_cache: dict[
            tuple[ProjectionId, str], tuple[dict[str, Any], str]
        ] = {}

    def catalog(self) -> tuple[ProjectionCatalogEntry, ...]:
        """Return the full denominator without touching artifact bytes."""
        return tuple(
            ProjectionCatalogEntry(
                projection_id=definition.projection_id,
                expected_source_path=definition.source_path,
                source_policy=definition.source_policy,
                intended_audience=definition.intended_audience,
                authoritative_for=definition.authoritative_for,
                may_not_use_for=definition.may_not_use_for,
                stable_address=_stable_address(definition.projection_id),
            )
            for definition in _DEFINITIONS
        )

    def get(
        self,
        projection_id: ProjectionId | str,
        *,
        artifact_content_hash: str | None = None,
        projection_hash: str | None = None,
    ) -> GovernedProjectionPacket:
        """Return one packet and optionally enforce byte and projection replay pins."""
        resolved_id = ProjectionId(projection_id)
        definition = _DEFINITION_BY_ID[resolved_id]
        observed_at = datetime.now(UTC)
        try:
            loaded = self._load(definition)
        except FileNotFoundError:
            packet = self._absence_packet(
                definition,
                availability=ProjectionAvailability.ARTIFACT_MISSING,
                reason=f"governed source is absent: {definition.source_path}",
                observed_at=observed_at,
            )
        else:
            try:
                payload, resolved_projection_hash = self._project(definition, loaded)
            except (InvalidProjectionSourceError, KeyError, TypeError, ValueError) as exc:
                packet = self._invalid_packet(
                    definition,
                    loaded=loaded,
                    reason=str(exc),
                    observed_at=observed_at,
                )
            else:
                as_of, basis = _resolve_as_of(loaded.parsed, loaded.modified_at)
                source = ProjectionSourceIdentity(
                    relative_path=loaded.relative_path,
                    artifact_content_hash=loaded.content_hash,
                    declared_content_hash=loaded.declared_content_hash,
                )
                packet = GovernedProjectionPacket(
                    projection_id=resolved_id,
                    availability=ProjectionAvailability.AVAILABLE,
                    intended_audience=definition.intended_audience,
                    authoritative_for=definition.authoritative_for,
                    may_not_use_for=definition.may_not_use_for,
                    source=source,
                    source_schema_version=_optional_string(
                        loaded.parsed.get("schema_version")
                        or loaded.parsed.get("manifest", {}).get("schema_version")
                    ),
                    source_rule_version=_optional_string(loaded.parsed.get("rule_version")),
                    projection_hash=resolved_projection_hash,
                    as_of=as_of,
                    freshness=ProjectionFreshness(
                        state="observed",
                        basis=basis,
                        observed_at=observed_at,
                        source_as_of=as_of,
                    ),
                    stable_address=_stable_address(resolved_id),
                    replay_address=_replay_address(
                        resolved_id,
                        artifact_content_hash=source.artifact_content_hash,
                        projection_hash=resolved_projection_hash,
                    ),
                    payload=payload,
                )
        _enforce_replay_pins(
            packet,
            artifact_content_hash=artifact_content_hash,
            projection_hash=projection_hash,
        )
        return packet

    def _load(self, definition: _ProjectionDefinition) -> _LoadedSource:
        if definition.source_format == "proving_ground":
            return self._load_proving_ground(definition.source_path)
        observation = self._read_file(definition.source_path)
        parsed = self._parse(observation, definition.source_format)
        return _LoadedSource(
            relative_path=definition.source_path,
            content_hash=observation.content_hash,
            parsed=parsed,
            modified_at=observation.modified_at,
            declared_content_hash=_declared_content_hash(parsed),
        )

    def _read_file(self, relative_path: str) -> _FileObservation:
        path = self._repository_root / relative_path
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._path_cache.get(path)
        if cached is not None and cached.signature == signature:
            return cached
        raw = path.read_bytes()
        stable_stat = path.stat()
        stable_signature = (stable_stat.st_mtime_ns, stable_stat.st_size)
        if stable_signature != signature:
            raw = path.read_bytes()
            stable_stat = path.stat()
            stable_signature = (stable_stat.st_mtime_ns, stable_stat.st_size)
        observation = _FileObservation(
            relative_path=relative_path,
            signature=stable_signature,
            content_hash=_sha256(raw),
            raw=raw,
            modified_at=datetime.fromtimestamp(stable_stat.st_mtime, tz=UTC),
        )
        self._path_cache[path] = observation
        return observation

    def _parse(
        self,
        observation: _FileObservation,
        source_format: Literal["json", "toml", "proving_ground"],
    ) -> dict[str, Any]:
        cache_key = (observation.content_hash, source_format)
        cached = self._parsed_cache.get(cache_key)
        if cached is not None:
            return cached
        if source_format == "json":
            value = json.loads(observation.raw)
        elif source_format == "toml":
            value = tomllib.loads(observation.raw.decode("utf-8"))
        else:  # pragma: no cover - composite sources have a dedicated loader
            raise AssertionError("proving-ground sources use the composite loader")
        if not isinstance(value, dict):
            raise InvalidProjectionSourceError(
                f"{observation.relative_path} must contain a top-level object"
            )
        normalized = _mapping(_json_ready(value), observation.relative_path)
        self._parsed_cache[cache_key] = normalized
        return normalized

    def _load_proving_ground(self, manifest_path: str) -> _LoadedSource:
        manifest_observation = self._read_file(manifest_path)
        manifest = self._parse(manifest_observation, "json")
        fixtures = _required_list(manifest, "fixtures")
        manifest_parent = Path(manifest_path).parent
        cases: list[dict[str, Any]] = []
        identities: list[dict[str, Any]] = []
        content_bindings = {manifest_path: manifest_observation.content_hash}
        modified_at = manifest_observation.modified_at
        for fixture in fixtures:
            fixture_record = _mapping(fixture, "fixtures[]")
            relative_case_path = (
                manifest_parent / _required_string(fixture_record, "path")
            ).as_posix()
            case_observation = self._read_file(relative_case_path)
            case = self._parse(case_observation, "json")
            if case.get("case_id") != fixture_record.get("case_id"):
                raise InvalidProjectionSourceError(
                    f"case_id mismatch for {relative_case_path}"
                )
            identities.append(
                {
                    "case_id": fixture_record.get("case_id"),
                    "domain": fixture_record.get("domain"),
                    "split": fixture_record.get("split"),
                    "authority_levels": fixture_record.get("authority_levels", []),
                }
            )
            cases.append(case)
            content_bindings[relative_case_path] = case_observation.content_hash
            modified_at = max(modified_at, case_observation.modified_at)
        parsed = {
            "manifest": manifest,
            "fixture_identities": identities,
            "fixture_records": cases,
        }
        return _LoadedSource(
            relative_path=f"{manifest_path}+cases/*",
            content_hash=_canonical_hash(content_bindings),
            parsed=parsed,
            modified_at=modified_at,
            declared_content_hash=None,
        )

    def _project(
        self,
        definition: _ProjectionDefinition,
        loaded: _LoadedSource,
    ) -> tuple[dict[str, Any], str]:
        cache_key = (definition.projection_id, loaded.content_hash)
        cached = self._projection_cache.get(cache_key)
        if cached is not None:
            return cached
        projector = _PROJECTORS[definition.projection_id]
        payload = _mapping(_json_ready(projector(loaded.parsed)), "projection_payload")
        projection_hash = _canonical_hash(payload)
        result = (payload, projection_hash)
        self._projection_cache[cache_key] = result
        return result

    def _absence_packet(
        self,
        definition: _ProjectionDefinition,
        *,
        availability: ProjectionAvailability,
        reason: str,
        observed_at: datetime,
    ) -> GovernedProjectionPacket:
        return GovernedProjectionPacket(
            projection_id=definition.projection_id,
            availability=availability,
            intended_audience=definition.intended_audience,
            authoritative_for=definition.authoritative_for,
            may_not_use_for=definition.may_not_use_for,
            as_of=observed_at,
            freshness=ProjectionFreshness(
                state="artifact_missing",
                basis="request_observation",
                observed_at=observed_at,
            ),
            stable_address=_stable_address(definition.projection_id),
            absence_reason=reason,
        )

    def _invalid_packet(
        self,
        definition: _ProjectionDefinition,
        *,
        loaded: _LoadedSource,
        reason: str,
        observed_at: datetime,
    ) -> GovernedProjectionPacket:
        as_of, basis = _resolve_as_of(loaded.parsed, loaded.modified_at)
        return GovernedProjectionPacket(
            projection_id=definition.projection_id,
            availability=ProjectionAvailability.INVALID_SOURCE,
            intended_audience=definition.intended_audience,
            authoritative_for=definition.authoritative_for,
            may_not_use_for=definition.may_not_use_for,
            source=ProjectionSourceIdentity(
                relative_path=loaded.relative_path,
                artifact_content_hash=loaded.content_hash,
                declared_content_hash=loaded.declared_content_hash,
            ),
            source_schema_version=_optional_string(loaded.parsed.get("schema_version")),
            source_rule_version=_optional_string(loaded.parsed.get("rule_version")),
            as_of=as_of,
            freshness=ProjectionFreshness(
                state="invalid_source",
                basis=basis,
                observed_at=observed_at,
                source_as_of=as_of,
            ),
            stable_address=_stable_address(definition.projection_id),
            absence_reason=reason,
        )


def _project_depth_n(source: dict[str, Any]) -> dict[str, Any]:
    domain_runs = _required_mapping(source, "domain_runs")
    projected_runs: dict[str, Any] = {}
    for domain, raw_run in sorted(domain_runs.items()):
        run = _mapping(raw_run, f"domain_runs.{domain}")
        witness = _required_mapping(run, "evidence_witness")
        evidence_class = _required_string(witness, "kind")
        terminal = _required_mapping(run, "terminal")
        weakest_links = _required_list(terminal, "blocking_obligations")
        terminal_distribution = _required_mapping(run, "terminal_distribution")
        stage_trace = _required_mapping(run, "stage_trace")
        acquisition = stage_trace.get("acquisition")
        projected_runs[str(domain)] = {
            "generation_cycle_run_id": run.get("generation_cycle_run_id"),
            "design_problem_ref": run.get("design_problem_ref"),
            "domain_role": run.get("domain_role"),
            "run_content_hash": run.get("content_hash"),
            "terminal_distribution": terminal_distribution,
            "evidence_class": evidence_class,
            "evidence_witness": witness,
            "weakest_links": weakest_links,
            "acquisition_route": acquisition,
        }
    return {
        "depth_evidence": _required_mapping(source, "depth_evidence"),
        "domain_runs": projected_runs,
        "terminal_distributions": _required_mapping(source, "terminal_distributions"),
    }


def _project_value_gate(source: dict[str, Any]) -> dict[str, Any]:
    education = _required_mapping(source, "education_refusal")
    production = _required_mapping(source, "production_refusal")
    mutations = _required_list(source, "decisive_mutation_expectations")
    outer_set_contract = [
        item
        for item in mutations
        if "value_outer_set"
        in str(
            _mapping(item, "decisive_mutation_expectations[]").get("mutation_id", "")
        )
    ]
    if not outer_set_contract:
        raise InvalidProjectionSourceError("missing recorded ValueOuterSet contract proofs")
    return {
        "denominators": _required_mapping(source, "denominators"),
        "education_refusal": education,
        "production_refusal": production,
        "advisor_receipts": {
            "education": education.get("method_selection_receipt"),
            "production": production.get("method_selection_receipt"),
        },
        "value_outer_set_contract": outer_set_contract,
        "mode_gates": _required_mapping(source, "mode_gates"),
        "acquisition_routing": source.get("acquisition_routing"),
        "disposition": source.get("disposition"),
    }


def _select(source: dict[str, Any], *fields: str) -> dict[str, Any]:
    return {field: source[field] for field in fields if field in source}


def _project_disposition(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "tasks",
        "owners",
        "task_owner_mapping",
        "bridge_artifacts",
        "method_availability_gate",
        "known_residuals",
        "parallel_world_reconciliation",
    )


def _project_engine_census(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "row_count",
        "execution_status_vocabulary",
        "critical_findings",
        "subcensus_summary",
        "gap_taxonomy_extensions",
        "verb_gap_consistency",
        "evidence_reproducibility",
        "discipline",
        "scope",
    )


def _project_fork_b(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "relation_counts",
        "relation_denominator_formula",
        "authority",
        "coverage_manifest",
        "certificate_summaries",
        "transport_floor",
        "transport_floor_rule",
        "known_bridge_limits",
        "normalization",
    )


def _project_acquisition_contract(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "denominators",
        "positive_receipt",
        "no_result_receipt",
        "fail_closed_receipt",
        "fail_closed_probes",
        "grounding_acquisition_request",
        "recorded_rederive_inputs",
        "compute_economics",
        "known_residuals",
    )


def _project_n13a_census(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "catalog_identity",
        "projection_bindings",
        "family_scorecards",
        "metric_resolutions",
        "route_evidence",
        "growth_backlog",
        "fetch_plan_generation",
        "reverse_demand_residuals",
    )


def _project_n13a_journal(source: dict[str, Any]) -> dict[str, Any]:
    return _select(source, "selection_plan", "family_receipts", "records")


def _project_capability_reality(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "summary",
        "readiness",
        "capability_claims",
        "blockers",
        "issues",
        "chain_clusters",
        "ratchet_integrity_status",
        "debt_algebra",
    )


def _project_cluster_ownership(source: dict[str, Any]) -> dict[str, Any]:
    return {
        **_select(
            source,
            "status",
            "owner",
            "purpose",
            "ratchet_state_vocabulary",
            "required_clusters",
            "required_cell_fields",
            "capability_chain_steps",
            "stop_rule",
            "open_cell_closure",
            "handshake_graph",
            "architecture_core",
        ),
        "clusters": _required_mapping(source, "cell"),
    }


def _project_health_metrics(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "health_metric_ledgers": _required_list(source, "health_metric_ledgers"),
    }


def _project_proving_ground(source: dict[str, Any]) -> dict[str, Any]:
    identities = _required_list(source, "fixture_identities")
    records = _required_list(source, "fixture_records")
    if len(identities) != 13 or len(records) != 13:
        raise InvalidProjectionSourceError("legacy proving ground must contain 13 fixture records")
    return {
        "fixture_authority": "fixture_only",
        "fixture_identities": identities,
        "fixture_records": records,
        "runtime_outcomes": {
            "availability": "artifact_missing",
            "reason": "no persisted validator-confirmed 13-case runtime result is named",
        },
    }


def _project_surface_readiness(source: dict[str, Any]) -> dict[str, Any]:
    return _select(
        source,
        "ledger_id",
        "authority",
        "controlled_vocabulary_source",
        "entries",
    )


_PROJECTORS = {
    ProjectionId.DEPTH_N_CYCLE_BOARD: _project_depth_n,
    ProjectionId.VALUE_GATE: _project_value_gate,
    ProjectionId.GENERATION_CYCLE_DISPOSITION: _project_disposition,
    ProjectionId.ENGINE_CENSUS: _project_engine_census,
    ProjectionId.FORK_B_RELATION_CENSUS: _project_fork_b,
    ProjectionId.ACQUISITION_ROUTING_CONTRACT: _project_acquisition_contract,
    ProjectionId.N13A_ACQUISITION_CENSUS: _project_n13a_census,
    ProjectionId.N13A_LIVE_PROBE_JOURNAL: _project_n13a_journal,
    ProjectionId.CAPABILITY_REALITY: _project_capability_reality,
    ProjectionId.CLUSTER_OWNERSHIP: _project_cluster_ownership,
    ProjectionId.LAYER3_HEALTH_METRICS: _project_health_metrics,
    ProjectionId.LEGACY_PROVING_GROUND: _project_proving_ground,
    ProjectionId.SURFACE_READINESS: _project_surface_readiness,
}


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidProjectionSourceError(f"{field} must be an object")
    return value


def _required_mapping(source: dict[str, Any], field: str) -> dict[str, Any]:
    if field not in source:
        raise InvalidProjectionSourceError(f"missing owner-recorded field: {field}")
    return _mapping(source[field], field)


def _required_list(source: dict[str, Any], field: str) -> list[Any]:
    value = source.get(field)
    if not isinstance(value, list):
        raise InvalidProjectionSourceError(f"{field} must be an array")
    return value


def _required_string(source: dict[str, Any], field: str) -> str:
    value = source.get(field)
    if not isinstance(value, str) or not value:
        raise InvalidProjectionSourceError(f"{field} must be a non-empty string")
    return value


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _declared_content_hash(source: dict[str, Any]) -> str | None:
    for field in (
        "contract_content_hash",
        "content_hash",
        "census_digest",
        "journal_content_sha256",
    ):
        value = _optional_string(source.get(field))
        if value is not None:
            return value
    return None


def _resolve_as_of(
    source: dict[str, Any],
    modified_at: datetime,
) -> tuple[datetime, Literal["source_timestamp", "filesystem_mtime"]]:
    candidates = [source]
    manifest = source.get("manifest")
    if isinstance(manifest, dict):
        candidates.append(manifest)
    for candidate in candidates:
        for field in ("as_of", "observed_at", "generated_at", "generated", "timestamp"):
            parsed = _parse_datetime(candidate.get(field))
            if parsed is not None:
                return parsed, "source_timestamp"
    return modified_at, "filesystem_mtime"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_ready(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256(encoded)


def _sha256(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _stable_address(projection_id: ProjectionId) -> str:
    return f"{_PROJECTION_BASE_PATH}/{projection_id.value}"


def _replay_address(
    projection_id: ProjectionId,
    *,
    artifact_content_hash: str,
    projection_hash: str,
) -> str:
    query = urlencode(
        {
            "artifact_content_hash": artifact_content_hash,
            "projection_hash": projection_hash,
        }
    )
    return f"{_stable_address(projection_id)}?{query}"


def _enforce_replay_pins(
    packet: GovernedProjectionPacket,
    *,
    artifact_content_hash: str | None,
    projection_hash: str | None,
) -> None:
    actual_artifact_hash = (
        packet.source.artifact_content_hash if packet.source is not None else None
    )
    if artifact_content_hash is not None and artifact_content_hash != actual_artifact_hash:
        raise ReplayPinMismatchError(
            "artifact_content_hash",
            expected=artifact_content_hash,
            actual=actual_artifact_hash,
        )
    if projection_hash is not None and projection_hash != packet.projection_hash:
        raise ReplayPinMismatchError(
            "projection_hash",
            expected=projection_hash,
            actual=packet.projection_hash,
        )


__all__ = [
    "CHANNEL_REGISTRY",
    "AudienceClass",
    "ChannelRegistryEntry",
    "ChannelRegistryResponse",
    "GovernedProjectionPacket",
    "GovernedProjectionService",
    "ProjectionAvailability",
    "ProjectionCatalogEntry",
    "ProjectionCatalogResponse",
    "ProjectionId",
    "ReplayPinMismatchError",
]
