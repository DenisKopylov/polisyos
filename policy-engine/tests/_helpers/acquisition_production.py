"""Persist a real WDI-resolvable case for served acquisition integration witnesses.

The candidate and missing-data observation are explicitly fixture inputs. The
recursive controller, planner, cost owner, durable control store and route reader
are their production implementations; no service or port object is fabricated.
"""

import hashlib
import json
import socket
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit

import aiohttp
import duckdb
import pandas as pd
import pytest

from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataSnapshot, DataSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
    AcquisitionAuthorityEntry,
    AuthoritySchemaColumn,
    CanonicalAcquisitionAuthority,
    build_acquisition_authority_provision,
    build_authority_entry,
    build_authority_registry,
)
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.fabric.connectors import (
    ResultSerializer,
    SourceProfileRegistry,
    resolve_connection_config,
)
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
from polisyos.fabric.data_plane import content_sha256
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteMutationRequest,
    AcquisitionRouteReplayPins,
)
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality import acquisition_executor as acquisition_executor_module
from polisyos.runtime.quality.acquisition_executor import (
    LiveCatalogExecutionConstraints,
    execute_live_catalog_acquisition,
)
from polisyos.runtime.quality.acquisition_planner import l1_variable_availability_requirement_gap
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.design_axes.coupling_composition import derive_recursive_design_graph
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    PendingN8ValuePort,
    ValuePortObservation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from tests._helpers import controlled_candidate_profile as fixtures

_ATTEMPT_ID = "n13b-worldbank-government-balance-001"
_TENANT_WDI = "00000000-0000-0000-0000-00000000000a"
_TENANT_FOREIGN = "00000000-0000-0000-0000-00000000000b"
_CONNECTOR_ID = "worldbank.wdi"
_PROFILE_ID = "worldbank_wdi"
_INDICATOR_ID = "GC.BAL.CASH.GD.ZS"
_COUNTRY_CODE = "UKR"
_START_YEAR = 2023
_END_YEAR = 2024
_PAGE_SIZE = 1000
_URL = "https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"
_PARAMS = {
    "date": "2023:2024",
    "format": "json",
    "page": "1",
    "per_page": "1000",
}


def install_fixture_wdi_cost_basis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply hypothetical owner input; this is not a repository cost allocation.

    The default schedule has no WDI row. Downstream witnesses replace only that
    owner's input data, while its real producer, hash and route revalidation run.
    The one expert hour is a synthetic test quantity, not an estimated WDI cost.
    """
    from polisyos.runtime.quality import acquisition_planner

    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "government.balance",
        {
            "basis_ref": "fixture-only:hypothetical-wdi-cost-input:v1",
            "collection_mode": "Fixture-only WDI acquisition costing input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )


class _WDIGap:
    def __call__(self, *, candidate, problem, **kwargs):
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Fixture WDI observations are absent before acquisition.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id="government.balance",
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref="repo://production_data/dataset_catalog.duckdb#variable/government.balance",
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


class _RevisedCycleWdiValuePort:
    def __call__(self, **kwargs):
        if kwargs.get("cycle_index") == 1:
            return _WDIGap()(**kwargs)
        return PendingN8ValuePort()(**kwargs)


class _RevisedCycleWdiGrounding:
    """Drive revision on cycle 0, then allow the cycle-1 value gap to request N7."""

    def __call__(
        self,
        *,
        candidate,
        problem,
        cycle_index,
        generation_result=None,
    ):
        grounding_port = (
            fixtures._AlwaysLowGrounding()
            if cycle_index == 0
            else fixtures._StableShadowGrounding()
        )
        return grounding_port(
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
            generation_result=generation_result,
        )


def resolve_completed_wdi_route(control, *, run_id: str, tenant_id: str, cell_id: str):
    """Resolve one completed NL producer through the canonical acquisition route owner."""
    closure = AcquisitionRouteLoop(
        control_store=control._control_store,
        artifact_store=control._artifact_store,
        event_log=control._diagnostic_event_log,
        core_source_resolver=control.resolve_completed_control_job_core_run_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
    ).resolve_current_route(run_id=run_id)
    request = AcquisitionRouteMutationRequest(
        route_projection_hash=closure.route_id,
        planner_report_hash=agent_action_content_hash(closure.planner_report),
        replay_pins=AcquisitionRouteReplayPins(
            source_job_id=closure.source_job_id,
            compiled_ref=closure.compiled_ref,
            compiled_content_hash=closure.compiled_content_hash,
            terminal_event_id=closure.terminal_event_id,
            design_problem_ref=closure.design_problem_ref,
            cost_basis_hash=closure.cost_basis_hash,
        ),
        idempotency_key="served-acquisition-fixture",
    )
    return closure, request


async def persist_wdi_route(
    control,
    *,
    tenant_id: str = "tenant-a",
    cell_id: str = "cell-a",
    run_id: str = "run-acquisition",
    job_id: str = "job-natural-language",
    generation_cycle_repo_root: Path | None = None,
    revised_source: bool = False,
    llm_model_id: str = "fixture-model",
):
    """Install a real compiled fixture case into the supplied app's canonical owners."""
    problem = fixtures._problem("served_wdi_acquisition")
    problem = problem.model_copy(
        update={
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2024"}
            )
        }
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = "design-problem://" + problem_ref.removeprefix("sha256:")
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    if revised_source:

        def cycle_controller_factory(_node_ref: str, _problem: object) -> GenerationCycleController:
            return GenerationCycleController(
                generation_port=fixtures._SameCandidateNewBasisGenerator(),
                grounding_port=_RevisedCycleWdiGrounding(),
                value_port=_RevisedCycleWdiValuePort(),
                repo_root=generation_cycle_repo_root,
            )

        cycle_budget = RecursiveCycleBudget(
            max_depth=0, max_nodes=1, min_cycles_per_leaf=2, max_cycles_per_leaf=2
        )
    else:

        def cycle_controller_factory(_node_ref: str, _problem: object) -> GenerationCycleController:
            return GenerationCycleController(
                generation_port=fixtures._CgfGenerationPort(
                    target_world_slots=("government.balance",)
                ),
                value_port=_WDIGap(),
                repo_root=generation_cycle_repo_root,
            )

        cycle_budget = RecursiveCycleBudget(
            max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
        )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=cycle_controller_factory,
        repo_root=generation_cycle_repo_root,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        manifest_ref = control._put_json_artifact(
            {"capability": "acquisition_fixture"},
            kind="runtime.capability_manifest",
            schema_name="CapabilityManifest",
        )
        source_payload_ref = control._put_json_artifact(
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "llm_models": [llm_model_id],
            },
            kind="runtime.control_job_payload.natural_language_run",
            schema_name="polisyos.runtime.ControlJobPayload",
        )
    store = control._control_store
    actor = "explicit-fixture"
    execution_scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "actor_subject": actor,
        "actor_authenticated": True,
        "actor_roles": ["analyst"],
    }
    store.create_job(
        job_id=job_id,
        kind="natural_language_run",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=source_payload_ref,
        submitted_by=actor,
        creation_event_payload={
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": "natural_language_run",
            "pipeline_id": None,
            "payload_ref": source_payload_ref,
            "submitted_by": actor,
            "requested_execution_profile": "dev",
            "effective_execution_profile": "dev",
            "policy_flags": {},
            "capability_manifest_ref": manifest_ref,
            "execution_scope": execution_scope,
        },
    )
    leased = store.lease_next_job(worker_id="acquisition-fixture-worker")
    if leased is None or leased.job_id != job_id:
        raise AssertionError("acquisition fixture did not lease its source job")
    with store.job_execution_fence(
        job_id=leased.job_id,
        worker_id=str(leased.lease_owner),
        attempt=leased.attempt,
    ):
        admission = store.current_execution_job_admission()
        with control._install_execution_scope(admission.scope):
            core_run_id, core_context = control._start_generation_run_context(
                job=admission.job,
                execution_scope=admission.scope,
            )
            run = await controller.run(
                graph,
                problems_by_node={root_ref: problem},
                budget_state=fixtures._budget(),
                recursive_budget=cycle_budget,
            )
            payload = {
                "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
                "design_problem_ref": problem_ref,
                "design_problem": problem.model_dump(mode="json"),
                "cycle_substrate_context_ref": None,
                "recursive_run": run.model_dump(mode="json", exclude={"leaf_nodes"}),
            }
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                {**payload, "content_hash": gy_content_hash(payload)}
            )
            compiled_artifact_ref = control._put_json_artifact_ref(
                compiled.model_dump(mode="json"),
                kind="runtime.compiled_recursive_generation_cycle",
                schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                tenant_context=(
                    ArtifactTenantContextInfo(
                        tenant_id=admission.scope.tenant_id,
                        cell_id=admission.scope.cell_id,
                    )
                    if admission.scope.status == "established"
                    and admission.scope.tenant_id is not None
                    else None
                ),
            )
            core_manifest_ref = control._finish_generation_run_context(
                job=admission.job,
                execution_scope=admission.scope,
                core_run_id=core_run_id,
                context=core_context,
                outputs=[compiled_artifact_ref],
                status="ok",
            )
            compiled_ref = str(compiled_artifact_ref.artifact_id)
            progress = {
                "state": "completed",
                "phase": "natural_language_run",
                "run_id": run_id,
                "compiled_recursive_generation_cycle_ref": compiled_ref,
                "compiled_recursive_generation_cycle_artifact_ref": (
                    compiled_artifact_ref.model_dump(mode="json")
                ),
                **control._core_run_progress_fields(
                    job=admission.job,
                    core_run_id=core_run_id,
                    manifest_ref=core_manifest_ref,
                ),
            }
            store.complete_job(
                job_id=leased.job_id,
                run_id=run_id,
                capability_manifest_ref=manifest_ref,
                progress=progress,
                expected_lease_owner=leased.lease_owner,
                expected_attempt=leased.attempt,
            )
    with control._install_execution_scope(admission.scope):
        control._diagnostic_event_log.append(
            DiagnosticEvent(
                event_id=f"evt-{run_id}-nl-terminal",
                event_source="polisyos.runtime.control",
                event_type="polisyos.runtime.diagnostic.phase_transition.v1",
                event_time=datetime.now(UTC),
                event_subject=f"run/{run_id}/job/{job_id}/phase/job_execution",
                schema_name="polisyos.runtime.quality.diagnostic_event",
                schema_version="1.0",
                trace_id=f"trace-{run_id}",
                span_id=f"span-{run_id}",
                parent_span_id=None,
                run_id=run_id,
                job_id=job_id,
                tenant_id=tenant_id,
                cell_id=cell_id,
                producer_component="polisyos.runtime.control",
                producer_version="test",
                execution_profile="governed",
                phase="job_execution",
                state_before="running",
                state_after="completed",
                payload_ref=None,
                artifact_refs=(manifest_ref, compiled_ref),
                input_refs=(),
                blocking_status=None,
                redaction_policy_ref=None,
                duplicate_of=None,
                dedupe_key=None,
            ),
            payload={
                "job_kind": "natural_language_run",
                "capability_manifest_ref": manifest_ref,
                "compiled_recursive_generation_cycle_ref": compiled_ref,
            },
        )
        return resolve_completed_wdi_route(
            control,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )


def intercepted_wdi_transport(
    monkeypatch: pytest.MonkeyPatch,
    *,
    allow_loopback: bool = False,
) -> list[tuple[str, str, dict[str, str]]]:
    """Intercept external HTTP bytes while executing the real WDI/Fabric owners."""
    original_request = aiohttp.ClientSession._request
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    loopback_hosts = {"127.0.0.1", "::1", "localhost"}
    transport_calls: list[tuple[str, str, dict[str, str]]] = []

    class _InterceptedResponse:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        def __init__(self, body: bytes):
            self.body = body

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return self.body

        def release(self) -> None:
            return None

        async def wait_for_close(self) -> None:
            return None

        def close(self) -> None:
            return None

    async def _intercept_request(_session: object, method: str, url: object, **kwargs: object):
        if allow_loopback and urlsplit(str(url)).hostname in loopback_hosts:
            return await original_request(_session, method, url, **kwargs)
        params = kwargs.get("params")
        assert isinstance(params, Mapping)
        normalized = {str(key): str(value) for key, value in params.items()}
        transport_calls.append((method, str(url), normalized))
        bounds = normalized["date"].split(":")
        start_year, end_year = int(bounds[0]), int(bounds[-1])
        rows = [row for row in _normalized_rows() if start_year <= row["year"] <= end_year]
        return _InterceptedResponse(_raw_body(rows))

    def _connect(sock, address):
        if allow_loopback and isinstance(address, tuple) and address[0] in loopback_hosts:
            return original_connect(sock, address)
        pytest.fail("intercepted integration escaped to a real network socket")

    def _connect_ex(sock, address):
        if allow_loopback and isinstance(address, tuple) and address[0] in loopback_hosts:
            return original_connect_ex(sock, address)
        pytest.fail("intercepted integration escaped to a real network socket")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _intercept_request)
    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex)
    return transport_calls


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_l5(repo_root: Path) -> Path:
    path = repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "coverage_rules": {"macro_state": 0.95},
                "proxy_mappings": {},
                "trust_tiers": {
                    "authoritative_high_coverage": {
                        "tier": "authoritative_high_coverage",
                        "min_coverage": 0.85,
                        "max_coverage": 1.0,
                        "trust_cap": 1.0,
                        "trust_multiplier": 1.0,
                    },
                    "administrative_noisy": {
                        "tier": "administrative_noisy",
                        "min_coverage": 0.0,
                        "max_coverage": 1.0,
                        "trust_cap": 0.7,
                        "trust_multiplier": 0.85,
                    },
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _write_provision(
    repo_root: Path,
    *,
    baseline: Path,
    l5_path: Path,
    baseline_owner_ref: str,
    live_harness_receipts: tuple[dict[str, str], ...] = (),
) -> Path:
    provision = build_acquisition_authority_provision(
        baseline_owner_ref=baseline_owner_ref,
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_owner_ref=("repo://" + DEFAULT_L5_MEASUREMENT_REGISTRY.as_posix()),
        l5_measurement_registry_content_sha256=_sha(l5_path),
        live_harness_receipts=live_harness_receipts,
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            provision.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _baseline(repo_root: Path, *, license_id: str = "CC-BY-4.0") -> Path:
    root = repo_root / "catalog"
    graph = build_slice0_fixture_catalog_graph(root)
    graph.close()
    path = root / "catalog.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            INSERT INTO ds_datasets (
                id, source, agency, title, description, access_license,
                execution_tier, polisyos_metrics, preferred_distribution_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "worldbank",
                "World Bank",
                "Cash surplus/deficit (% of GDP)",
                "Government cash balance as a share of GDP.",
                license_id,
                "transport_ready",
                ["gov_balance"],
                "source-worldbank-balance-json",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_distributions (
                id, dataset_id, connector_type, profile_id, source_locator,
                parser_supported, machine_readable, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance-json",
                "source-worldbank-balance",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                True,
                True,
                0.9,
            ],
        )
        con.execute(
            """
            INSERT INTO ds_metric_bindings (
                metric_id, dataset_id, distribution_id, connector_id, profile_id,
                request_dataset_id, confidence, metric_inference_confidence,
                default_filters, execution_tier, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gov_balance",
                "source-worldbank-balance",
                "source-worldbank-balance-json",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                0.87,
                0.95,
                "{}",
                "transport_ready",
                "worldbank",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "GC.BAL.CASH.GD.ZS",
                "gov_balance",
                "exact",
                0.85,
                "Cash surplus/deficit % GDP;source=worldbank",
                False,
                0.0,
            ],
        )
    finally:
        con.close()
    return path


def _entry():
    return build_authority_entry(
        source_lane="live_fetch",
        target_variable="government.balance",
        landing_dataset_id="acquisition.worldbank.government_balance",
        landing_distribution_id="acquisition.worldbank.government_balance.json",
        source_catalog_dataset_id="source-worldbank-balance",
        source_catalog_distribution_id="source-worldbank-balance-json",
        upstream_metric_id="gov_balance",
        catalog_raw_variable="GC.BAL.CASH.GD.ZS",
        raw_field="value",
        raw_unit="percent_gdp",
        canonical_unit="percent_gdp",
        unit_transform="identity",
        unit_transform_ref="fabric://units/percent-gdp-identity/v1",
        alignment_method="meta_analytic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=-100.0,
        valid_max=100.0,
        evidence_refs=("duckdb://production_data/dataset_catalog.duckdb#/gov_balance",),
        schema_contract_ref="fabric://worldbank.wdi.generic@2.0.0",
        schema_columns=(
            AuthoritySchemaColumn(name="country_code", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="country_name", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="decimal", logical_types=("integer",), nullable=False),
            AuthoritySchemaColumn(name="indicator_id", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="indicator_name", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="unit", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="value", logical_types=("null", "number"), nullable=True),
            AuthoritySchemaColumn(name="year", logical_types=("integer",), nullable=False),
        ),
        l5_family_id="macro_state",
        title="Acquired government balance",
        description="Owner-validated World Bank government balance observations.",
        country_codes=("UKR",),
        temporal_start="2020",
        temporal_end="2024",
    )


def _authority_family_receipt(attempt_id: str) -> dict[str, object]:
    outcome = "replay_fixture_missing_after_interception"
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    return {
        "connector_id": "worldbank.wdi",
        "component_id": "worldbank.wdi@1.0.0",
        "connector_class": ("polisyos.fabric.connectors.sources.world_bank.WorldBankConnector"),
        "protocol_violations": [],
        "protocol_conformant": True,
        "harness_checks_passed": [
            "capability_gated_methods_present",
            "connect_returns_unique_sessions",
            "core_methods_are_async",
            "disconnect_idempotent",
            "protocol_compliance",
            "required_class_attributes",
        ],
        "harness_check_failures": [],
        "carrier_denominator": 1,
        "carrier_attempt_count": 1,
        "dry_run_attempts": [
            {
                "attempt_id": attempt_id,
                "profile_id": "worldbank_wdi",
                "source_profile_family": "worldbank",
                "request_dataset_id": "GC.BAL.CASH.GD.ZS",
                "fetch_request_key": FetchRequest(dataset_id="GC.BAL.CASH.GD.ZS").request_key,
                "connection_config_content_sha256": content_sha256(
                    resolve_connection_config(profile).to_dict(redact=True)
                ),
                "connector_fetch_invoked": True,
                "fetch_completed": False,
                "outcome": outcome,
                "finding_code": outcome,
                "failure_type": (
                    "polisyos.fabric.connectors.testing.simulator.MissingFixtureError"
                ),
                "simulator_mode": "replay",
                "simulator_call_count": 1,
                "transport_intercepted": True,
                "network_escape_attempt_count": 0,
                "actual_network_call_count": 0,
            }
        ],
        "outcome_counts": {outcome: 1},
        "safe_dry_run_passed": True,
        "simulator_mode": "replay",
        "simulator_intercepted": True,
        "simulator_call_count": 1,
        "network_escape_attempt_count": 0,
        "simulator_network_calls": 0,
    }


def _write_family_receipt(
    repo_root: Path,
    *,
    entry_id: str,
    attempt_id: str,
    receipt: dict[str, object],
    receipt_path: str = "evidence/worldbank-wdi-live-harness.json",
) -> dict[str, str]:
    path = repo_root / receipt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return {
        "entry_id": entry_id,
        "attempt_id": attempt_id,
        "receipt_owner_ref": f"repo://{receipt_path}",
        "receipt_content_sha256": _sha(path),
    }


def _resolver(
    repo_root: Path,
    *,
    license_id: str = "CC-BY-4.0",
    authority_entry: AcquisitionAuthorityEntry | None = None,
    live_harness_receipts: tuple[dict[str, str], ...] = (),
):
    baseline = _baseline(repo_root, license_id=license_id)
    l5 = _write_l5(repo_root)
    entry = authority_entry or _entry()
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(entry,),
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
        live_harness_receipts=live_harness_receipts,
    )
    return (
        CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=baseline,
        ),
        entry,
    )


def _family_receipt(*, scenario: str = "success") -> dict[str, object]:
    receipt = _authority_family_receipt(_ATTEMPT_ID)
    carrier = dict(receipt["dry_run_attempts"][0])
    profile = SourceProfileRegistry.get_instance().get(_PROFILE_ID)
    assert profile is not None
    carrier.update(
        {
            "source_profile_family": "worldbank",
            "connection_config_content_sha256": content_sha256(
                resolve_connection_config(profile).to_dict(redact=True)
            ),
            "fetch_request_key": FetchRequest(dataset_id=_INDICATOR_ID).request_key,
        }
    )
    if scenario == "receipt_config_drift":
        carrier["connection_config_content_sha256"] = "sha256:" + "0" * 64
    elif scenario == "receipt_request_drift":
        carrier["fetch_request_key"] = "sha256:" + "0" * 64
    elif scenario == "receipt_profile_family_drift":
        carrier["source_profile_family"] = "forged"
    receipt["dry_run_attempts"] = [carrier]
    return receipt


def _constraints() -> LiveCatalogExecutionConstraints:
    return LiveCatalogExecutionConstraints(
        country_code=_COUNTRY_CODE,
        start_year=_START_YEAR,
        end_year=_END_YEAR,
        page_size=_PAGE_SIZE,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
        timeout_cap_seconds=15.0,
        heartbeat_cap_seconds=5.0,
    )


def _normalized_rows(*, adjacent: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "country_code": _COUNTRY_CODE,
            "country_name": "Ukraine",
            "indicator_id": _INDICATOR_ID,
            "indicator_name": "Cash surplus/deficit (% of GDP)",
            "year": 2023,
            "value": -18.2,
            "unit": "% of GDP",
            "decimal": 1,
        },
        {
            "country_code": _COUNTRY_CODE,
            "country_name": "Ukraine",
            "indicator_id": _INDICATOR_ID,
            "indicator_name": "Cash surplus/deficit (% of GDP)",
            "year": 2024,
            "value": -17.1,
            "unit": "% of GDP",
            "decimal": 1,
        },
    ]
    if adjacent == "indicator":
        rows.append(
            {
                **rows[-1],
                "indicator_id": "FP.CPI.TOTL",
                "indicator_name": "Consumer price index",
                "value": 128.4,
            }
        )
    elif adjacent == "country":
        rows.append({**rows[-1], "country_code": "POL", "country_name": "Poland"})
    elif adjacent == "year":
        rows.append({**rows[-1], "year": 2022})
    return rows


def _raw_body(
    rows: list[dict[str, object]],
    *,
    per_page: int = _PAGE_SIZE,
    total: int | None = None,
) -> bytes:
    records = [
        {
            "countryiso3code": row["country_code"],
            "country": {"id": "UA", "value": row["country_name"]},
            "indicator": {
                "id": row["indicator_id"],
                "value": row["indicator_name"],
            },
            "date": str(row["year"]),
            "value": row["value"],
            "unit": row["unit"],
            "decimal": row["decimal"],
        }
        for row in rows
    ]
    return json.dumps(
        [
            {
                "page": 1,
                "pages": 1,
                "per_page": per_page,
                "total": len(records) if total is None else total,
            },
            records,
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _fetch_result(
    rows: list[dict[str, object]],
    *,
    body: bytes,
) -> FetchResult[pd.DataFrame]:
    fetched_at = datetime.now(UTC)
    body_sha256 = "sha256:" + hashlib.sha256(body).hexdigest()
    frame = pd.DataFrame(rows)
    return FetchResult(
        data=frame,
        row_count=len(frame),
        schema_id="worldbank.wdi.generic",
        schema_version="2.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=body_sha256,
            timestamp=fetched_at,
            content_hash=body_sha256,
        ),
        fetched_at=fetched_at,
        completeness=1.0,
        quality_tier=QualityTier.GOLD,
        has_more=False,
        next_page_token=None,
    )


def _manifest_dataset(manifest: object) -> object:
    datasets = getattr(manifest, "datasets", None)
    if datasets is None and isinstance(manifest, Mapping):
        datasets = manifest.get("datasets")
    assert isinstance(datasets, list)
    assert len(datasets) == 1
    return datasets[0]


def _dataset_value(dataset: object, key: str) -> object:
    if isinstance(dataset, Mapping):
        return dataset[key]
    return getattr(dataset, key)


def _fetch_request_from_manifest(manifest: object) -> FetchRequest:
    dataset = _manifest_dataset(manifest)
    filters = _dataset_value(dataset, "filters")
    assert isinstance(filters, Mapping)
    normalized_filters = tuple(
        (str(key), tuple(str(value) for value in values)) for key, values in sorted(filters.items())
    )
    return FetchRequest(
        dataset_id=str(_dataset_value(dataset, "dataset_id")),
        date_start=datetime.fromisoformat(str(_dataset_value(dataset, "date_start"))).replace(
            tzinfo=UTC
        ),
        date_end=datetime.fromisoformat(str(_dataset_value(dataset, "date_end"))).replace(
            tzinfo=UTC
        ),
        filters=normalized_filters,
        page_size=int(_dataset_value(dataset, "page_size")),
        retryable=bool(_dataset_value(dataset, "retryable")),
    )


class _OrchestratedWorldBankStub:
    """Emulate only Fabric's observer/sink contract; never open a network socket."""

    def __init__(
        self,
        *,
        scenario: str,
        baseline_path: Path,
        journal_path: Path,
    ) -> None:
        self.scenario = scenario
        self.baseline_path = baseline_path
        self.journal_path = journal_path
        self.calls: list[dict[str, object]] = []
        self.raw_visible_before_sink = False
        self.cas_root: Path | None = None

    def __call__(self, **kwargs: object) -> IngestionResult:
        self.calls.append(dict(kwargs))
        self.cas_root = Path(str(kwargs["cas_root"]))
        manifest = kwargs["connector_manifest"]
        observer = kwargs.get("raw_http_response_observer")
        sink = kwargs.get("raw_result_sink")
        rows = _normalized_rows(
            adjacent=(
                self.scenario.removeprefix("adjacent_")
                if self.scenario.startswith("adjacent_")
                else None
            )
        )
        result_rows = [dict(row) for row in rows]
        if self.scenario == "result_value_drift":
            result_rows[0]["value"] = -999.0
        elif self.scenario == "result_unit_drift":
            result_rows[0]["unit"] = "percentage points"
        elif self.scenario == "result_decimal_drift":
            result_rows[0]["decimal"] = 7
        elif self.scenario == "result_name_drift":
            result_rows[0]["indicator_name"] = "Fabricated government balance"
        body = _raw_body(
            rows,
            per_page=(999 if self.scenario == "metadata_per_page_drift" else _PAGE_SIZE),
            total=(999 if self.scenario == "metadata_total_drift" else None),
        )
        result = _fetch_result(result_rows, body=body)
        if self.scenario == "fabricated_result_version":
            forged_hash = "sha256:" + "0" * 64
            result = result.model_copy(
                update={
                    "version": result.version.model_copy(
                        update={"value": forged_hash, "content_hash": forged_hash}
                    )
                }
            )
        fetch_request = _fetch_request_from_manifest(manifest)

        if self.scenario != "omit_observer":
            assert observer is not None
            url, params = self._transport_projection()
            observer.before_request(_CONNECTOR_ID, url, params)  # type: ignore[attr-defined]
            on_headers = getattr(observer, "on_response_headers", None)
            if callable(on_headers):
                on_headers(
                    _CONNECTOR_ID,
                    url,
                    params,
                    200,
                    {"content-type": "application/json"},
                )
            on_progress = getattr(observer, "on_body_progress", None)
            if callable(on_progress):
                on_progress(_CONNECTOR_ID, url, params, len(body))

            if self.scenario == "sink_before_raw":
                assert callable(sink)
                sink(_CONNECTOR_ID, _INDICATOR_ID, fetch_request, result)

            observer.on_raw_response(  # type: ignore[attr-defined]
                _CONNECTOR_ID,
                url,
                params,
                200,
                {"content-type": "application/json"},
                body,
            )

            if self.scenario in {"retry_second_call", "renamed_second_call"}:
                retry_url = (
                    url
                    if self.scenario == "retry_second_call"
                    else url.replace(_INDICATOR_ID, "FP.CPI.TOTL")
                )
                observer.before_request(  # type: ignore[attr-defined]
                    _CONNECTOR_ID,
                    retry_url,
                    params,
                )

        if self.scenario != "omit_sink":
            assert callable(sink)
            if self.journal_path.is_file():
                events = _journal_events(self.journal_path)
                self.raw_visible_before_sink = any(
                    event.get("event_kind") == "raw_response" for event in events
                )
            sink(_CONNECTOR_ID, _INDICATOR_ID, fetch_request, result)

        if self.scenario == "baseline_mutation":
            with self.baseline_path.open("ab") as handle:
                handle.write(b"n13b-baseline-mutation-probe")
        if self.scenario == "baseline_mutation_then_error":
            with self.baseline_path.open("ab") as handle:
                handle.write(b"n13b-baseline-mutation-probe")
            raise RuntimeError("simulated transport failure after baseline mutation")

        store = FileSystemCAS(self.cas_root)
        serialized, media_type = ResultSerializer.serialize(result)
        data_ref = store.put_bytes(
            serialized,
            ArtifactWriteOptions(
                kind="fabric.connector_cache.payload",
                media_type=media_type,
            ),
        )
        evidence_ref = persist_evidence_bundle(
            store,
            build_evidence_bundle(
                sources=[data_ref],
                notes=["network-free orchestrated WDI test"],
            ),
        )
        snapshot = DataSnapshot(
            data_ref=data_ref,
            evidence_ref=evidence_ref,
            stats={"datasets_fetched": 1, "source": "orchestrated_ingestion:test"},
            notes=["fabric.data_plane.orchestrator", "datasets=1"],
        )
        snapshot_artifact = store.put_json(
            snapshot,
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.core.DataSnapshot",
                    version="0.2.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return IngestionResult(
            evidence_bundle_ref=evidence_ref,
            data_snapshot_ref=DataSnapshotRef(artifact_id=snapshot_artifact.artifact_id),
            datasets_fetched=1,
        )

    def _transport_projection(self) -> tuple[str, dict[str, str]]:
        url = _URL
        params = dict(_PARAMS)
        if self.scenario == "wrong_host":
            url = url.replace("api.worldbank.org", "attacker.invalid")
        elif self.scenario == "wrong_path":
            url = url.replace("/v2/country/", "/v1/series/")
        elif self.scenario == "wrong_indicator":
            url = url.replace(_INDICATOR_ID, "FP.CPI.TOTL")
        elif self.scenario == "wrong_country":
            url = url.replace("/UKR/", "/POL/")
        elif self.scenario == "wrong_year":
            params["date"] = "2022:2024"
        return url, params


def _journal_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    scenario: str = "success",
    constraints: LiveCatalogExecutionConstraints | None = None,
    authority_entry: object | None = None,
    execution_dependencies: dict[str, object] | None = None,
    cache_namespace: str | None = None,
) -> tuple[object, object, _OrchestratedWorldBankStub, Path]:
    repo_root = tmp_path / "repo"
    entry = authority_entry or _entry()
    receipt = _family_receipt(scenario=scenario)
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        receipt=receipt,
    )
    authority, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    journal_path = tmp_path / "journal.jsonl"
    stub = _OrchestratedWorldBankStub(
        scenario=scenario,
        baseline_path=authority.baseline_path,
        journal_path=journal_path,
    )

    async def _forbid_direct_fetch(*args: object, **kwargs: object) -> object:
        del args, kwargs
        pytest.fail("live acquisition bypassed run_orchestrated_ingestion")

    monkeypatch.setattr(WorldBankConnector, "fetch", _forbid_direct_fetch)
    monkeypatch.setattr(
        acquisition_executor_module,
        "run_orchestrated_ingestion",
        stub,
    )

    cas_root = tmp_path / "cas"
    dependencies = dict(execution_dependencies or {})
    if "artifact_store" not in dependencies:
        dependencies["artifact_store"] = FileSystemCAS(cas_root)
    result = execute_live_catalog_acquisition(
        authority=authority,
        entry_id=entry.entry_id,
        attempt_id=_ATTEMPT_ID,
        constraints=constraints or _constraints(),
        journal_path=journal_path,
        cas_root=cas_root,
        cache_namespace=cache_namespace,
        **dependencies,
    )
    return authority, result, stub, journal_path
