"""Protected candidate-action harness over a real native N7 source-job fixture.

The source job uses the recursive controller's contract-testing candidate input,
not an NL provider. The HTTP mutation, human authorization, worker lease, WDI
connector, compiler report, action sink and CAS are their real owners. The
transport bytes and institutional signatures are explicitly test-owned inputs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import socket
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar, Literal
from urllib.parse import urlsplit

import aiohttp
import pytest
from fastapi.testclient import TestClient

from polisyos.core import artifacts
from polisyos.core.run.context import RunContext
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.services import acquisition_surface_execution
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.quality import acquisition_planner, substrate_registry
from polisyos.runtime.quality.acquisition_planner import l1_variable_availability_requirement_gap
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidateSourceRoute,
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
)
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import ValuePortObservation
from tests._helpers import acquisition_served_history as served
from tests._helpers.acquisition_human_decision import persist_signed, prepare_human_decision
from tests._helpers.acquisition_production import bind_fixture_l1_catalog_source, persist_wdi_route
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.lane01_candidate_problem import (
    labor_candidate_problem as labor_candidate_problem,
)
from tests._helpers.lane01_wdi_profiles import (
    UNEMPLOYMENT_PROFILE,
    build_fixture_wdi_authority,
    fixture_wdi_response,
)

RUN_ID = "run-lane01-served-candidate-source"
SOURCE_JOB_ID = "job-lane01-native-n7-source"

if TYPE_CHECKING:
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
    )


def labor_candidate_profile(
    *, tmp_path: Path, store: artifacts.ArtifactStore, problem: DesignProblem
) -> tuple[CandidateSimulationScenarioProfile, CandidateSimulationSyntheticModelDeclarationV1]:
    """Build an owner-issued annual labor profile with declared candidate SCM limits."""
    return served._served_wdi_candidate_profile(
        tmp_path=tmp_path,
        store=store,
        problem=problem,
        country_code="USA",
        data_year=2024,
        population_scope="total_labor_force",
    )


def build_candidate_port_owners(tmp_path: Path) -> SimpleNamespace:
    """Compose real authority, bridge, CAS and control owners without an N7 job."""
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", UNEMPLOYMENT_PROFILE)
    same_source_authority = catalog.CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
    )
    registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(
        authority.registry_path.read_bytes()
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    control_store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    event_log = RuntimeDiagnosticEventLog(store=control_store, artifact_store=store)
    runtime_root = tmp_path / "runtime"
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(),
        repo_root=authority.repo_root,
        runtime_root=runtime_root,
        authority=authority,
        artifact_store=store,
        event_log=event_log,
        epoch_deployment=None,
        control_store=control_store,
    )
    return SimpleNamespace(
        authority=authority,
        same_source_authority=same_source_authority,
        entry=entry,
        registry=registry,
        store=store,
        control_store=control_store,
        event_log=event_log,
        runtime_root=runtime_root,
        bridge=bridge,
    )


class _LaborGap:
    def __call__(self, *, candidate: Any, problem: DesignProblem, **kwargs: Any):
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            candidate_id=candidate.candidate_id,
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="The controlled modeled unemployment input is absent before acquisition.",
            decision_grade="blocked",
            acquisition_requirement=l1_variable_availability_requirement_gap(
                candidate_id=candidate.candidate_id,
                candidate_content_hash=candidate.atom.content_hash,
                design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
                availability=L1VariableAvailability(
                    variable_id="global.unemployment_rate",
                    status="unavailable",
                    dataset_count=0,
                    metric_binding_count=0,
                    observation_count=0,
                    coverage_ref="fixture://lane01/usa-2024/unemployment-missing",
                ),
                authority_level=problem.authority_profile.requested_authority_level,
            ),
        )


def candidate_route_for_closure(control: Any, closure: Any) -> AcquisitionCandidateSourceRoute:
    """Select the actual persisted compiler discovery joined to the current N7 record."""
    basis = closure.planner_report.requirement_basis_binding
    if basis is None:
        raise AssertionError("native N7 fixture did not persist its compiler basis")
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(control._artifact_store, basis.compiler_report_ref)
    )
    specs = [
        s
        for s in report.specs
        if s.requirement_id == closure.planner_record.compiled_requirement_ref
    ]
    if len(specs) != 1:
        raise AssertionError("native N7 record does not join one compiler spec")
    binding = specs[0].metadata["capability_binding"]
    matches = [
        r
        for r in (report.capability_requirement_resolutions or ())
        if r.query.requirement_id == binding["requirement_id"]
        and r.query.construct == UNEMPLOYMENT_PROFILE.construct
    ]
    if len(matches) != 1 or matches[0].candidate_discovery is None:
        raise AssertionError("native N7 compiler has no unique labor candidate discovery")
    candidates = matches[0].candidate_discovery.candidates
    if len(candidates) != 1:
        raise AssertionError("native N7 compiler has no unique selected labor candidate")
    return AcquisitionCandidateSourceRoute(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        route_id=closure.route_id,
        design_problem_ref=closure.design_problem_ref,
        compiled_requirement_ref=specs[0].requirement_id,
        requirement_id=matches[0].query.requirement_id,
        candidate_digest=candidates[0].content_digest,
        profile_selection_ref=cycle_job_profile_selection_ref(closure.design_problem_basis),
        canonical_variable_id="global.unemployment_rate",
        target_slot_id="global.unemployment_rate",
        country_code="USA",
        year=2024,
        population="total_labor_force",
        reentry_budget_usd=Decimal("0.50"),
    )


def _transport(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, dict[str, str]]]:
    original_request = aiohttp.ClientSession._request
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    calls: list[tuple[str, str, dict[str, str]]] = []
    loopback = {"127.0.0.1", "::1", "localhost"}

    class Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "application/json"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def read(self) -> bytes:
            return fixture_wdi_response(UNEMPLOYMENT_PROFILE)

        def release(self) -> None:
            pass

        async def wait_for_close(self) -> None:
            pass

        def close(self) -> None:
            pass

    async def request(session: Any, method: str, url: object, **kwargs: Any):
        if urlsplit(str(url)).hostname in loopback:
            return await original_request(session, method, url, **kwargs)
        assert method == "GET"
        assert str(url).endswith("/country/USA/indicator/SL.UEM.TOTL.ZS")
        params = kwargs["params"]
        assert isinstance(params, Mapping)
        calls.append((method, str(url), {str(k): str(v) for k, v in params.items()}))
        return Response()

    def connect(sock: Any, address: Any):
        if isinstance(address, tuple) and address[0] in loopback:
            return original_connect(sock, address)
        pytest.fail("candidate fixture escaped to external network")

    def connect_ex(sock: Any, address: Any):
        if isinstance(address, tuple) and address[0] in loopback:
            return original_connect_ex(sock, address)
        pytest.fail("candidate fixture escaped to external network")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", request)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    return calls


def run_lane01_candidate_action_served(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observer: Callable[[SimpleNamespace], None],
    *,
    candidate_profile_builder: Callable[
        ...,
        tuple[CandidateSimulationScenarioProfile, CandidateSimulationSyntheticModelDeclarationV1],
    ]
    | None = None,
    candidate_owner_mode: Literal[
        "configured", "no_bridge", "bridge_without_candidate"
    ] = "configured",
) -> None:
    """Run protected HTTP acquisition and expose the actual resulting action state."""
    for key, value in {
        "POLISYOS_EXECUTION_PROFILE": "dev",
        "POLISYOS_CONTROL_WORKER_BACKEND": "external",
        "POLISYOS_CONTROL_STATE_STORE_BACKEND": "sqlite",
        "POLISYOS_METRICS_PORT": "0",
        "POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS": "10",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "global.unemployment_rate",
        {
            "basis_ref": "fixture-only:lane01-hypothetical-cost:v1",
            "collection_mode": "Fixture-only modeled unemployment input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )
    catalog_root = tmp_path / "retrieval-catalog"
    catalog.build_slice0_fixture_catalog_graph(catalog_root).close()
    bind_fixture_l1_catalog_source(
        catalog_root,
        catalog_root / "catalog.duckdb",
        include_n7_dataset_bundle=True,
    )
    from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

    catalog_path = catalog_root / "catalog.duckdb"
    catalog_sha256 = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    _write_substrate_catalog_fixture(catalog_root, include_graphs=False)
    if hashlib.sha256(catalog_path.read_bytes()).hexdigest() != catalog_sha256:
        raise AssertionError("served_candidate_catalog_metadata_replaced_owner_l1")
    paths = substrate_registry.default_substrate_catalog_paths(catalog_root)
    if paths.l1_dcat_path.resolve(strict=True) != catalog_path.resolve(strict=True):
        raise AssertionError("served_candidate_catalog_source_binding_mismatch")
    # Reopen all source metadata through the real owner before launching N7.
    substrate_registry.build_substrate_registry_from_existing_catalogs(catalog_root)
    capability_resolver = RequirementToCapabilityResolver.governed_fixture(served.REPO_ROOT)
    trust = served._ExternalTrust(tmp_path)
    signers, identities = served._key_config(tmp_path, trust)
    cas_root = tmp_path / "cas"
    try:
        problem = labor_candidate_problem()
        candidate_profiles = ()
        model_declarations = ()
        if candidate_profile_builder is not None:
            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationScenarioProfile,
                CandidateSimulationSyntheticModelDeclarationV1,
                candidate_simulation_profile_ref,
            )

            profile, declaration = served._within_fixture_owner(
                candidate_profile_builder,
                tmp_path=tmp_path / "candidate-profile",
                store=artifacts.FileSystemCAS(cas_root, ownership_enforced=True),
                problem=problem,
            )
            if (
                type(profile) is not CandidateSimulationScenarioProfile
                or type(declaration) is not CandidateSimulationSyntheticModelDeclarationV1
                or profile.profile_selection_ref != cycle_job_profile_selection_ref(problem)
                or declaration.profile_selection_ref != profile.profile_selection_ref
                or declaration.profile_config_ref != candidate_simulation_profile_ref(profile)
                or declaration.profile_content_hash != profile.content_hash
            ):
                raise ValueError("served_candidate_profile_factory_binding_mismatch")
            candidate_profiles = (profile,)
            model_declarations = (declaration,)

    except BaseException:
        trust.close()
        raise

    def app():
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
            candidate_simulation_profiles=candidate_profiles,
            candidate_simulation_model_declarations=model_declarations,
            repo_root=catalog_root,
        )

    try:
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            closure, mutation = served._within_fixture_owner(
                asyncio.run,
                persist_wdi_route(
                    control,
                    tenant_id=served.TENANT,
                    cell_id=served.CELL,
                    run_id=RUN_ID,
                    job_id=SOURCE_JOB_ID,
                    generation_cycle_repo_root=catalog_root,
                    fixture_problem=problem,
                    fixture_value_port=_LaborGap(),
                    fixture_capability_resolver=capability_resolver,
                ),
            )
            selected = served._within_fixture_owner(candidate_route_for_closure, control, closure)
            # Retain only the selected source/report and its original request;
            # this native fixture supplies no prior candidate N4/N5 witness.
            (tmp_path / "native-selected-source.json").write_text(
                json.dumps(
                    {
                        "cas_root": str(cas_root),
                        "source_kind": "native_recursive_controller_without_prior_n5",
                        "run_id": closure.run_id,
                        "source_job_id": closure.source_job_id,
                        "source_payload_ref": closure.source_payload_ref,
                        "compiled_ref": closure.compiled_ref,
                        "terminal_event_id": closure.terminal_event_id,
                        "route_id": closure.route_id,
                        "source_problem": closure.design_problem_basis.model_dump(mode="json"),
                        "source_cycle": closure.source_cycle.model_dump(mode="json"),
                        "selected_planner_report": closure.planner_report.model_dump(mode="json"),
                        "selected_planner_record": closure.planner_record.model_dump(mode="json"),
                        "request": mutation.model_dump(mode="json"),
                        "candidate_selection": selected.model_dump(mode="json"),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            with tenant_scope(None, tenant_id=served.TENANT, cell_id=served.CELL):
                registry = control._artifact_store.put_json(
                    {"fixture": "native candidate acquisition source job"},
                    artifacts.ArtifactWriteOptions(
                        kind="test.registry", media_type="application/json"
                    ),
                )
                RunContext.start(
                    store=control._artifact_store,
                    registry_bundle=registry,
                    run_dir=cas_root / "runs" / RUN_ID,
                    run_id=RUN_ID,
                    tenant_id=served.TENANT,
                    cell_id=served.CELL,
                ).finalize()
            path = f"/api/v1/runs/{RUN_ID}/acquisition-routes/{closure.route_id}"
            template = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
            preflight, digest = trust.post(
                client,
                path + "/decision-request",
                mutation.model_dump(mode="json"),
                route=template + "/decision-request",
            )
            assert preflight.status_code == 200, preflight.text
            job_id = AcquisitionActionService._job_id(closure, mutation)
            now = datetime.now(UTC)
            contract = served._contract()
            envelope = contract.action_envelopes[0].model_copy(
                update={
                    "mandate_owner_ref": identities["owner"],
                    "authorized_subject": "acquisition-operator",
                    "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
                    "required_tenant_id": served.TENANT,
                    "required_resource_digest": digest,
                    "valid_from": now - timedelta(minutes=1),
                    "valid_until": now + timedelta(hours=1),
                }
            )
            contract = contract.model_copy(
                update={
                    "mandate_owner_ref": identities["owner"],
                    "action_envelopes": (envelope,),
                }
            )
            context = {
                "control": control,
                "tenant_id": served.TENANT,
                "cell_id": served.CELL,
                "run_id": RUN_ID,
                "job_id": job_id,
                "now": now,
            }
            contract_ref = served._within_fixture_owner(
                persist_signed,
                payload=contract,
                kind=served.authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
                schema_name="polisyos.runtime.DelegationContract",
                schema_version=served.authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
                signer=signers["owner"],
                signer_identity=identities["owner"],
                **context,
            )
            current = served._mandate_authority_evidence(
                owner_ref=identities["owner"],
                signer_identity=identities["current"],
                rule_version_ref=contract.rule_version_ref,
                effective_from=now - timedelta(minutes=1),
                effective_until=now + timedelta(hours=1),
            )
            current_ref = served._within_fixture_owner(
                persist_signed,
                payload=current,
                kind=served.authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
                schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
                schema_version=served.authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
                signer=signers["current"],
                signer_identity=identities["current"],
                **context,
            )
            info = served._within_fixture_owner(
                control._artifact_store.put_json,
                {"limitation": "modeled fixture; no measurement, causal, or publication authority"},
                artifacts.ArtifactWriteOptions(
                    kind="test.acquisition.disconfirming", media_type="application/json"
                ),
            )
            slot = {
                "tenant_id": served.TENANT,
                "cell_id": served.CELL,
                "run_id": RUN_ID,
                "route_id": closure.route_id,
                "resource_digest": digest,
                "delegation_contract_ref": contract_ref,
                "mandate_owner_ref": identities["owner"],
                "delegation_public_key_path": str(tmp_path / "owner.pub"),
                "current_mandate_evidence_ref": current_ref,
                "current_mandate_signer_identity": identities["current"],
                "current_mandate_public_key_path": str(tmp_path / "current.pub"),
                "verifier_provenance_ref": "fixture://appointment-registry",
                "decision_information_refs": [info.model_dump(mode="json")],
                "decision_disconfirming_refs": [info.model_dump(mode="json")],
            }
            trust.raw["acquisition_authority"]["mandates"] = [slot]

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            response, _ = trust.post(
                client,
                path + "/decision-request",
                mutation.model_dump(mode="json"),
                route=template + "/decision-request",
            )
            assert response.status_code == 200, response.text
            source_ref = response.json()["authority_decision_ref"]
            gate = served._within_fixture_owner(
                prepare_human_decision,
                container.control_service,
                container.human_decision_service,
                source_ref,
                tenant_id=served.TENANT,
                cell_id=served.CELL,
                run_id=RUN_ID,
                signers=signers,
                identities=identities,
                now=datetime.now(UTC),
                audit_path=cas_root / "runtime" / "audit" / "access.jsonl",
            )
            body = {
                k: v
                for k, v in gate.model_dump(mode="json").items()
                if k not in {"tenant_id", "run_id", "exposure_session_ref"}
            }
            body.update(
                action="approve",
                decision_mode="ordinary",
                accountability_statement="I accept this bounded candidate-only input acquisition.",
                dissent_statement="Its model and measurement limitations remain unresolved.",
            )
            human, _ = trust.post(
                client,
                f"/api/v1/runs/{RUN_ID}/human-decisions",
                body,
                route="/api/v1/runs/{run_id}/human-decisions",
                subject="human-reviewer-1",
                extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
            )
            assert human.status_code == 201, human.text
            slot["human_decision_record_ref"] = human.json()["record_ref"]

        authority, _entry = build_fixture_wdi_authority(tmp_path / "wdi-repo", UNEMPLOYMENT_PROFILE)
        transport_calls = _transport(monkeypatch)
        cases = []

        def port(*, control_service: Any, **kwargs: Any):
            del kwargs
            bridge = AcquisitionWorldGrowthBridge(
                config=AcquisitionWorldGrowthConfig(
                    candidate_source_routes=(selected,)
                    if candidate_owner_mode == "configured"
                    else (),
                ),
                repo_root=authority.repo_root,
                runtime_root=cas_root,
                authority=authority,
                epoch_deployment=None,
                artifact_store=control_service._artifact_store,
                event_log=control_service._diagnostic_event_log,
                control_store=control_service._control_store,
                action_head_sink=control_service.acquisition_route_sink,
                source_control_service=control_service,
                promotion_runtime=control_service._promotion_runtime,
                cycle_substrate_context_admission_owner=control_service._cycle_substrate_context_admission_owner,
            )
            registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(
                authority.registry_path.read_bytes()
            )
            result = acquisition_surface_execution.WorldBankWDIAcquisitionExecutionPort(
                authority=authority,
                registry=registry,
                provision=authority.provision,
                provision_content_sha256=authority.provision_content_sha256,
                runtime_state_root=cas_root,
                artifact_store=control_service._artifact_store,
                world_growth_bridge=None if candidate_owner_mode == "no_bridge" else bridge,
            )
            cases.append(
                SimpleNamespace(
                    port=result,
                    bridge=None if candidate_owner_mode == "no_bridge" else bridge,
                )
            )
            return result

        monkeypatch.setattr(
            acquisition_surface_execution, "build_production_world_bank_wdi_execution_port", port
        )
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            response, _ = trust.post(
                client,
                path + "/execute",
                mutation.model_dump(mode="json"),
                route=template + "/execute",
            )
            assert not transport_calls
            if response.status_code not in {200, 202}:
                served._within_fixture_owner(
                    observer,
                    SimpleNamespace(
                        client=client,
                        control=control,
                        closure=closure,
                        selected=selected,
                        request=mutation,
                        response=response,
                        job_id=job_id,
                        job=control._control_store.get_job(job_id),
                        cases=cases,
                        transport_calls=transport_calls,
                        trust=trust,
                        path=path,
                        template=template,
                    ),
                )
                return
            dispatched = dispatch_one_control_job(
                store=control._control_store,
                handler=control._process_control_job,
                expected_job_id=job_id,
            )
            assert dispatched == job_id
            served._within_fixture_owner(
                observer,
                SimpleNamespace(
                    client=client,
                    control=control,
                    closure=closure,
                    selected=selected,
                    request=mutation,
                    response=response,
                    job_id=job_id,
                    job=control._control_store.get_job(job_id),
                    cases=cases,
                    transport_calls=transport_calls,
                    trust=trust,
                    path=path,
                    template=template,
                ),
            )
    finally:
        trust.close()
