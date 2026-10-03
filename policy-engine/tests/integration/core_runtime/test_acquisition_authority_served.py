"""Real deployment/HTTP/DS9/durable-worker acquisition authority bridge."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from polisyos.core import artifacts, canon
from polisyos.core.run.context import RunContext
from polisyos.core.security.identity import PolicyOSRole
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality import substrate_registry
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
from tests._helpers.acquisition_production import persist_wdi_route
from tests._helpers.control_worker import dispatch_one_control_job
from tests.integration.core_runtime.test_acquisition_admission_bundle import _contract
from tests.unit.runtime.http.deployment_security_test_support import LocalJWKSStub
from tests.unit.runtime.http.test_runtime_deployment_security import _config_mapping
from tests.unit.runtime.quality.test_agent_action_authority import _mandate_authority_evidence

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CELL = "018f47a0-0000-7000-8000-000000000001"
RUN = "run-acquisition"


def _within_fixture_owner(call, *args, **kwargs):
    """Emit external fixture inputs under their actual tenant/cell ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        return call(*args, **kwargs)




def _safe_validation_error_fields(exception):
    """Keep only Pydantic location names and error type identifiers."""
    exception_type = type(exception)
    if (
        exception_type.__name__ != "ValidationError"
        or exception_type.__module__.split(".", maxsplit=1)[0]
        not in {"pydantic", "pydantic_core"}
    ):
        return ()
    errors = getattr(exception, "errors", None)
    if not callable(errors):
        return ()
    try:
        rows = errors(include_input=False, include_context=False, include_url=False)
    except Exception:
        return ()
    if not isinstance(rows, list):
        return ()
    safe_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        location = row.get("loc")
        error_type = row.get("type")
        if (
            not isinstance(location, (tuple, list))
            or type(error_type) is not str
            or any(type(part) not in (str, int) for part in location)
        ):
            continue
        safe_rows.append(
            {"loc": tuple(location), "type": error_type}
        )
    return tuple(safe_rows)


def _capture_semantic_epoch_finalizer_failure(call):
    """Capture safe exception coordinates and Pydantic field/type metadata."""
    prior_trace = sys.gettrace()
    target_frames = set()
    by_exception = {}
    captured = []
    value_error_event_rows = []

    def trace(frame, event, argument):
        is_finalizer = (
            frame.f_globals.get("__name__") == "polisyos.runtime.quality.semantic_epoch"
            and frame.f_code.co_name == "finalize_admitted_epoch"
        )
        if event == "call" and is_finalizer:
            target_frames.add(id(frame))
        elif event == "exception":
            exception_type, exception, _traceback = argument
            ancestor = frame
            inside_finalizer = False
            while ancestor is not None:
                if id(ancestor) in target_frames:
                    inside_finalizer = True
                    break
                ancestor = ancestor.f_back
            if inside_finalizer:
                module_name = frame.f_globals.get("__name__", "")
                row = (
                    module_name,
                    frame.f_code.co_name,
                    frame.f_lineno,
                    exception_type.__name__,
                )
                if isinstance(exception_type, type) and issubclass(
                    exception_type, ValueError
                ):
                    value_error_event_rows.append(row)
                rows = by_exception.setdefault(id(exception), [])
                if not rows or rows[-1] != row:
                    rows.append(row)
                if is_finalizer:
                    captured.append(
                        {
                            "exception_type": exception_type.__name__,
                            "frames": tuple(rows),
                            "validation_error_fields": _safe_validation_error_fields(
                                exception
                            ),
                        }
                    )
        elif event == "return" and is_finalizer:
            target_frames.discard(id(frame))
        return trace

    sys.settrace(trace)
    try:
        return call(), captured, {
            "scope": "all_value_error_trace_events_inside_finalizer_call",
            "identity": "trace_events_not_unique_exception_objects",
            "events": tuple(value_error_event_rows),
        }
    finally:
        sys.settrace(prior_trace)


def _read_owned_terminal(store, ref):
    """Read the actual terminal schema through scoped immutable CAS ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert store.get_manifest(ref).kind == "runtime_quality.acquisition_route_loop_receipt"
        return AcquisitionRouteLoopReceipt.model_validate(
            canon.from_canonical_bytes(store.get_bytes(ref))
        )


def _served_wdi_candidate_profile(*, tmp_path, store, problem):
    """Build one typed synthetic N5 profile over a real owner-built base WMR."""
    tmp_path.mkdir(parents=True, exist_ok=True)

    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        build_world_model_record,
    )
    from tests.unit.runtime.quality import test_world_model_record as wmr_fixture

    snapshot_id = "served-wdi-controlled-candidate-base"
    base_data_snapshot_ref = wmr_fixture._data_snapshot_ref(
        store, snapshot_id=snapshot_id
    )
    substrate_registry = wmr_fixture._substrate_registry()
    substrate_registry_ref = persist_substrate_registry(store, substrate_registry)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = wmr_fixture._model_spec(
        base_data_snapshot_ref,
        registry_bundle.bundle_ref,
    )
    wmr_fixture._write_fabric_world_snapshot(tmp_path, snapshot_id=snapshot_id)
    base_world = build_world_model_record(
        store,
        fabric_world_ref=wmr_fixture._fabric_ref(tmp_path, snapshot_id=snapshot_id),
        data_forge_snapshot_binding_path=wmr_fixture._write_data_forge_binding(
            tmp_path, snapshot_id=snapshot_id
        ),
        data_snapshot_ref=base_data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=wmr_fixture._skg_ref(tmp_path, snapshot_id=snapshot_id),
        substrate_registry=substrate_registry,
        region_or_jurisdiction=problem.jurisdiction_time.region,
        population_scope="served_controlled_candidate_fixture",
        policy_domain=problem.domain,
        valid_time_scope="controlled_fixture_baseline_only",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="country_year",
        branch_mode=BranchMode.OBSERVED,
        policy_slot_ids=("government.balance", "global.tax_rate"),
        producer_ref="test.served_wdi_candidate_profile",
        required_substrate_families=("firm_fundamentals",),
        substrate_registry_artifact_ref=substrate_registry_ref,
    )
    slot_units = {
        binding.slot_id: binding.unit for binding in base_world.record.policy_slot_map
    }
    target_baseline = float(base_world.bound_global_state.government_balance)
    outcome_baseline = float(base_world.bound_global_state.tax_rate)
    selected_hashes = tuple(
        entry.entry_content_hash for entry in substrate_registry.entries
    )
    substrate_input_hash = gy_content_hash(
        {
            "purpose": "served-controlled-candidate-profile",
            "substrate_registry_content_hash": substrate_registry.content_hash,
        }
    )
    context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(problem),
        domain=problem.domain,
        substrate_registry=substrate_registry,
        selected_registry_entry_hashes=selected_hashes,
        world_model_record=base_world.record,
        intervention_substrate=load_l6_intervention_substrate(
            Path(__file__).resolve().parents[3]
        ),
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash(
            "served-wdi-controlled-candidate-source-pack"
        ),
        substrate_input_content_hash=substrate_input_hash,
    )
    inputs = CandidateSimulationContextInputs(
        substrate_registry=context.substrate_registry,
        selected_registry_entry_hashes=context.selected_registry_entry_hashes,
        world_model_record=base_world.record,
        intervention_substrate=context.intervention_substrate,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=context.source_pack_content_hash,
        substrate_input_content_hash=context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="budget_allocation_multiplier",
        parameter_id="multiplier",
        target_world_slot="government.balance",
        unit_id=slot_units["government.balance"],
        minimum=1,
        maximum=2,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://e02r2/b09-controlled-acquisition-candidate",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={
            "government.balance": target_baseline,
            problem.outcome_of_interest.target_variable: outcome_baseline,
        },
        seed=17,
        replications=2,
    )
    profile_fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "e02r2.b09.served.wdi.controlled",
        "profile_selection_ref": cycle_job_profile_selection_ref(problem),
        "context_inputs": inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    profile_draft = CandidateSimulationScenarioProfile.model_construct(
        **profile_fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **profile_fields,
            "content_hash": gy_content_hash(
                profile_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    outcome_variable = problem.outcome_of_interest.target_variable
    declaration_fields = {
        "schema_version": (
            "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
        ),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": slot_units[rule.target_world_slot],
        "outcome_unit_id": slot_units[outcome_variable],
        "target_baseline": target_baseline,
        "outcome_baseline": outcome_baseline,
        "outcome_per_target_unit": 0.001,
        "outcome_noise_stddev": 0.0,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    return profile, declaration


class _ExternalTrust:
    """Fixture institutional JWT/JWKS/OPA endpoints; runtime verifiers remain real."""

    def __init__(self, tmp_path):
        self.inputs = []
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwks = LocalJWKSStub(self.key)
        uri = self.jwks.start()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                outer.inputs.append(
                    json.loads(self.rfile.read(int(self.headers["content-length"])))["input"]
                )
                body = b'{"result":{"allow":true}}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.opa = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.opa.serve_forever, daemon=True)
        self.thread.start()
        self.raw = _config_mapping(tmp_path)
        self.raw["identity_verifier"]["jwks_uri"] = uri
        self.raw["step_up_verifier"]["jwks_uri"] = uri
        self.raw["step_up_verifier"]["allowed_key_ids"] = ["identity-2026-07"]
        self.raw["opa"]["url"] = f"http://127.0.0.1:{self.opa.server_port}"
        self.raw["service_principals"] = [
            {
                "issuer": "https://idp.example",
                "audience": "polisyos-runtime",
                "subject": subject,
                "tenant_id": TENANT,
                "cell_id": CELL,
                "permissions": permissions,
            }
            for subject, permissions in (
                ("acquisition-operator", ["evidence.acquire", "runs.review", "runs.view"]),
                ("human-reviewer-1", ["runs.human_decisions.create", "runs.review", "runs.view"]),
            )
        ]
        now = int(time.time())
        self.tokens = {
            subject: self.encode(
                {
                    "iss": "https://idp.example",
                    "aud": "polisyos-runtime",
                    "sub": subject,
                    "tenant_id": TENANT,
                    "cell_id": CELL,
                    "realm_access": {"roles": ["polisyos_analyst"]},
                    "amr": ["pwd", "mfa"],
                    "iat": now,
                    "exp": now + 3600,
                    "jti": f"jwt-{subject}",
                }
            )
            for subject in ("acquisition-operator", "human-reviewer-1")
        }

    def encode(self, payload):
        return jwt.encode(payload, self.key, algorithm="RS256", headers={"kid": "identity-2026-07"})

    def close(self):
        self.opa.shutdown()
        self.opa.server_close()
        self.thread.join(timeout=5)
        self.jwks.close()

    def post(
        self, client, path, body, *, route, subject="acquisition-operator", extra_headers=None
    ):
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        headers = {
            "Authorization": f"Bearer {self.tokens[subject]}",
            "X-Tenant-ID": TENANT,
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        # First request reaches real authorization and intentionally lacks step-up.
        refused = client.post(path, content=payload, headers=headers)
        assert refused.status_code == 403 and refused.json()["code"] == "step_up_required", (
            refused.text
        )
        observed = self.inputs[-1]
        resource = observed["resource"]
        resource_id = resource["artifact_id"]
        digest = "sha256:" + resource_id.rsplit("sha256:", 1)[1]
        now = int(time.time())
        headers["X-PolicyOS-Step-Up"] = self.encode(
            {
                "iss": "https://step-up.example",
                "aud": "polisyos-runtime-step-up",
                "sub": subject,
                "tenant_id": TENANT,
                "jti": str(uuid.uuid4()),
                "iat": now,
                "exp": now + 240,
                "mfa_verified": True,
                "assurance": "fixture-real-signature",
                "method": "POST",
                "route": route,
                "permission": observed["action"]["permission"],
                "resource_id": resource_id,
                "resource_digest": digest,
                "resource_kind": resource["kind"],
                "binding_authority": resource["binding_authority"],
                "body_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "step_up_class": "human_decision"
                if subject == "human-reviewer-1"
                else "acquisition_approval",
            }
        )
        return client.post(path, content=payload, headers=headers), digest


def _key_config(tmp_path, trust):
    families = (
        "owner",
        "current",
        "admission",
        "source",
        "principal",
        "separation",
        "presentation",
        "custody",
    )
    pairs = {name: artifacts.KeyPair.generate() for name in families}
    signers = {name: artifacts.Ed25519Signer(pair.private_key) for name, pair in pairs.items()}
    identities = {name: f"institution://acquisition-fixture/{name}" for name in families}
    for name, pair in pairs.items():
        (tmp_path / f"{name}.pem").write_bytes(pair.private_pem())
        (tmp_path / f"{name}.pub").write_bytes(pair.public_pem())
    from polisyos.runtime.http.services import human_decision_contracts as hdc

    rows = [
        (
            "source",
            authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
            "AgentActionAuthorityDecision",
            authority.AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        ),
        (
            "owner",
            authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            "DelegationContract",
            authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
        ),
        (
            "admission",
            authority.AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
            "AgentActionAdmissionBundle",
            authority.AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
        ),
        (
            "principal",
            hdc.HUMAN_DECISION_PRINCIPAL_BINDING_ARTIFACT_KIND,
            "HumanDecisionPrincipalBinding",
            hdc.HUMAN_DECISION_PRINCIPAL_BINDING_MANIFEST_VERSION,
        ),
        (
            "separation",
            hdc.REVIEWER_SEPARATION_CREDENTIAL_ARTIFACT_KIND,
            "ReviewerSeparationCredential",
            hdc.REVIEWER_SEPARATION_CREDENTIAL_MANIFEST_VERSION,
        ),
        (
            "presentation",
            hdc.HUMAN_DECISION_PRESENTATION_CONTRACT_ARTIFACT_KIND,
            "HumanDecisionPresentationContract",
            hdc.HUMAN_DECISION_PRESENTATION_CONTRACT_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_EXPOSURE_SESSION_ARTIFACT_KIND,
            "HumanDecisionExposureSession",
            hdc.HUMAN_DECISION_EXPOSURE_SESSION_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_EXPOSURE_EVENT_ARTIFACT_KIND,
            "HumanDecisionExposureAuditEvent",
            hdc.HUMAN_DECISION_EXPOSURE_EVENT_MANIFEST_VERSION,
        ),
        (
            "custody",
            hdc.HUMAN_DECISION_RECORD_ARTIFACT_KIND,
            "HumanDecisionRecord",
            hdc.HUMAN_DECISION_RECORD_MANIFEST_VERSION,
        ),
    ]
    trust.raw["human_decision_custody"] = {
        "signer_identity": identities["custody"],
        "private_key_path": str(tmp_path / "custody.pem"),
        "public_key_path": str(tmp_path / "custody.pub"),
        "verifier_epoch": "acquisition-served-epoch",
        "provenance": {"source": "fixture_external_institution", "reference": "served-acquisition"},
        "revoked_key_ids": [],
        "trusted_producers": [
            {
                "artifact_kind": kind,
                "schema_name": f"polisyos.runtime.{schema}",
                "schema_version": version,
                "signer_identity": identities[name],
                "public_key_path": str(tmp_path / f"{name}.pub"),
            }
            for name, kind, schema, version in rows
        ],
    }
    trust.raw["acquisition_authority"] = {
        "mandates": [],
        **{
            field: {
                "signer_identity": identities[name],
                "private_key_path": str(tmp_path / f"{name}.pem"),
                "public_key_path": str(tmp_path / f"{name}.pub"),
                "verifier_provenance_ref": "fixture://appointments",
            }
            for field, name in (("admission_signer", "admission"), ("decision_signer", "source"))
        },
    }
    return signers, identities


def test_served_acquisition_selects_committed_human_authority_and_reopens_worker(
    tmp_path, monkeypatch
):
    import os

    from polisyos.runtime.http.services import (
        acquisition_action_service,
        acquisition_surface_execution,
    )
    from polisyos.runtime.quality.authority_reconciliation import (
        reconcile_authority_ref,
    )
    from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
    from tests._helpers import acquisition_chain
    from tests._helpers.acquisition_human_decision import persist_signed, prepare_human_decision
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        intercepted_wdi_transport,
    )
    from tests.unit.runtime.quality import test_generation_cycle as cycle_fixtures

    served_n4_recording = acquisition_chain.load_served_wdi_generation_recording()
    served_n4_model_id = str(served_n4_recording["model_id"])

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    install_fixture_wdi_cost_basis(monkeypatch)
    # The isolated checkout has no production catalog. Supply actual persisted
    # catalog input; every container still opens and hashes it through its owner.
    catalog_root = tmp_path / "retrieval-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    default_catalog_paths = substrate_registry.default_substrate_catalog_paths
    startup_root = Path.cwd().resolve()
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(default_catalog_paths(root), l1_dcat_path=catalog_root / "catalog.duckdb")
            if Path(root).resolve() == startup_root
            else default_catalog_paths(root)
        ),
    )
    trust = _ExternalTrust(tmp_path)
    port_patch = pytest.MonkeyPatch()
    signers, identities = _key_config(tmp_path, trust)
    cas_root = tmp_path / "cas"
    candidate_profiles = []
    candidate_model_declarations = []
    candidate_generation_mode = [False]
    remove_acquired_n5_baseline = (
        os.environ.get("POLISYOS_R1_REMOVE_ACQUIRED_N5_INPUT_CONSUMPTION") == "1"
    )
    removal_probe_n5_baselines: list[dict[str, float]] = []

    def app():
        return create_runtime_api_app(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
            deployment_security=security.build_deployment_security(
                security.DeploymentSecurityConfig.from_mapping(trust.raw)
            ),
            enable_security_middlewares=True,
            enable_csrf_protection=False,
            candidate_simulation_profiles=tuple(candidate_profiles),
            candidate_simulation_model_declarations=tuple(candidate_model_declarations),
        )

    original_problem = cycle_fixtures._problem

    def controlled_fiscal_problem(problem_id="served_wdi_acquisition"):
        from polisyos.runtime.quality.design_problem import (
            _QualifiedOutcomeOfInterestV3,
        )

        problem = original_problem(problem_id)
        payload = problem.model_dump(mode="json")
        payload["schema_version"] = "policyos.runtime.design_problem.v3"
        payload["problem_statement"] = (
            "Explore the tax-rate outcome from a bounded government-balance "
            "candidate while carrying acquisition limitations."
        )
        payload["domain"] = "fiscal"
        payload["objectives"][0].update(
            {
                "objective_id": "tax_rate",
                "description": "Explore the tax rate under a candidate-only scenario.",
                "metric_id": "tax_rate",
            }
        )
        payload["outcome_of_interest"].update(
            {
                "target_variable": "global.tax_rate",
                "metric_id": "tax_rate",
                "estimand": "synthetic candidate change in tax rate",
            }
        )
        lever_space = payload["candidate_lever_space"]
        lever_space["allowed_operator_kinds"] = ["budget_allocation_multiplier"]
        for lever in lever_space["candidate_levers"]:
            lever.update(
                {
                    "operator_kind": "budget_allocation_multiplier",
                    "instrument": "candidate budget allocation multiplier",
                    "target_slot": "government.balance",
                }
            )
        # Re-parse the complete V3 payload so qualified variable identities use
        # the versioned DesignProblem owner instead of bypassing its validator.
        problem = type(problem).model_validate(payload)
        assert type(problem.outcome_of_interest) is _QualifiedOutcomeOfInterestV3
        return problem

    monkeypatch.setattr(cycle_fixtures, "_problem", controlled_fiscal_problem)

    def appoint_mandate(control, request, resource_digest):
        store = control._artifact_store
        now = datetime.now(UTC)
        job_id = acquisition_action_service.AcquisitionActionService._job_id(closure, request)
        contract = _contract()
        envelope = contract.action_envelopes[0].model_copy(
            update={
                "mandate_owner_ref": identities["owner"],
                "authorized_subject": "acquisition-operator",
                "authorized_runtime_roles": (PolicyOSRole.ANALYST,),
                "required_tenant_id": TENANT,
                "required_resource_digest": resource_digest,
                "valid_from": now - timedelta(minutes=1),
                "valid_until": now + timedelta(hours=1),
            }
        )
        contract = contract.model_copy(
            update={"mandate_owner_ref": identities["owner"], "action_envelopes": (envelope,)}
        )
        context = {
            "control": control,
            "tenant_id": TENANT,
            "cell_id": CELL,
            "run_id": RUN,
            "job_id": job_id,
            "now": now,
        }
        contract_ref = _within_fixture_owner(
            persist_signed,
            payload=contract,
            kind=authority.DELEGATION_CONTRACT_ARTIFACT_KIND,
            schema_name="polisyos.runtime.DelegationContract",
            schema_version=authority.LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            signer=signers["owner"],
            signer_identity=identities["owner"],
            **context,
        )
        evidence = _mandate_authority_evidence(
            owner_ref=identities["owner"],
            signer_identity=identities["current"],
            rule_version_ref=contract.rule_version_ref,
            effective_from=now - timedelta(minutes=1),
            effective_until=now + timedelta(hours=1),
        )
        evidence_ref = _within_fixture_owner(
            persist_signed,
            payload=evidence,
            kind=authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND,
            schema_name="polisyos.runtime.CurrentMandateOwnerEvidence",
            schema_version=authority.CURRENT_MANDATE_OWNER_SCHEMA_VERSION,
            signer=signers["current"],
            signer_identity=identities["current"],
            **context,
        )
        info = _within_fixture_owner(
            store.put_json,
            {"risk": "Fiscal measurement excludes unreported balances; review required."},
            artifacts.ArtifactWriteOptions(
                kind="test.acquisition.disconfirming", media_type="application/json"
            ),
        )
        slot = {
            "tenant_id": TENANT,
            "cell_id": CELL,
            "run_id": RUN,
            "route_id": closure.route_id,
            "resource_digest": resource_digest,
            "delegation_contract_ref": contract_ref,
            "mandate_owner_ref": identities["owner"],
            "delegation_public_key_path": str(tmp_path / "owner.pub"),
            "current_mandate_evidence_ref": evidence_ref,
            "current_mandate_signer_identity": identities["current"],
            "current_mandate_public_key_path": str(tmp_path / "current.pub"),
            "verifier_provenance_ref": "fixture://appointment-registry",
            "decision_information_refs": [info.model_dump(mode="json")],
            "decision_disconfirming_refs": [info.model_dump(mode="json")],
        }
        return slot, job_id

    def approve_request(client, request, resource_digest):
        container = client.app.state.runtime_container
        response, digest = trust.post(
            client,
            path + "/decision-request",
            request.model_dump(mode="json"),
            route=route_prefix + "/decision-request",
        )
        assert response.status_code == 200 and digest == resource_digest, response.text
        source_ref = response.json()["authority_decision_ref"]
        source = authority.AgentActionAuthorityDecision.model_validate(
            canon.from_canonical_bytes(
                _within_fixture_owner(
                    container.control_service._artifact_store.get_bytes, source_ref
                )
            )
        )
        assert source.refusal_reasons == ("human_decision_missing",), source.refusal_reasons
        gate = _within_fixture_owner(
            prepare_human_decision,
            container.control_service,
            container.human_decision_service,
            source_ref,
            tenant_id=TENANT,
            cell_id=CELL,
            run_id=RUN,
            signers=signers,
            identities=identities,
            now=datetime.now(UTC),
            audit_path=cas_root / "runtime" / "audit" / "access.jsonl",
        )
        body = {
            name: value
            for name, value in gate.model_dump(mode="json").items()
            if name not in {"tenant_id", "run_id", "exposure_session_ref"}
        }
        body.update(
            action="approve",
            decision_mode="ordinary",
            accountability_statement="I accept this bounded acquisition.",
            dissent_statement="The measurement limitations remain material and were reviewed.",
        )
        response, _ = trust.post(
            client,
            f"/api/v1/runs/{RUN}/human-decisions",
            body,
            route="/api/v1/runs/{run_id}/human-decisions",
            subject="human-reviewer-1",
            extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
        )
        assert response.status_code == 201, response.text
        return source, response.json()["record_ref"]

    path = None
    try:
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            closure, request = _within_fixture_owner(
                asyncio.run,
                persist_wdi_route(
                    control,
                    tenant_id=TENANT,
                    cell_id=CELL,
                    llm_model_id=served_n4_model_id,
                ),
            )
            job = control._control_store.get_job("job-natural-language")
            assert job is not None
            persisted_job_payload = canon.from_canonical_bytes(
                _within_fixture_owner(
                    control._artifact_store.get_bytes, job.payload_ref
                )
            )
            assert persisted_job_payload["llm_models"] == [
                str(served_n4_recording["model_id"])
            ]
            store = control._artifact_store
            profile, model_declaration = _within_fixture_owner(
                _served_wdi_candidate_profile,
                tmp_path=tmp_path / "served-candidate-profile",
                store=store,
                problem=closure.design_problem,
            )
            candidate_profiles.append(profile)
            candidate_model_declarations.append(model_declaration)
            with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
                registry = store.put_json(
                    {"fixture": "registry"},
                    artifacts.ArtifactWriteOptions(
                        kind="test.registry", media_type="application/json"
                    ),
                )
                RunContext.start(
                    store=store,
                    registry_bundle=registry,
                    run_dir=cas_root / "runs" / RUN,
                    run_id=RUN,
                    tenant_id=TENANT,
                    cell_id=CELL,
                ).finalize()
            path = f"/api/v1/runs/{RUN}/acquisition-routes/{closure.route_id}"
            route_prefix = "/api/v1/runs/{run_id}/acquisition-routes/{route_id}"
            response, resource_digest = trust.post(
                client,
                path + "/decision-request",
                request.model_dump(mode="json"),
                route=route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            empty = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(
                        store.get_bytes, response.json()["authority_decision_ref"]
                    )
                )
            )
            assert empty.outcome == "refused"
            assert "delegation_contract_not_persisted" in empty.refusal_reasons
            slot, job_id = appoint_mandate(control, request, resource_digest)
            trust.raw["acquisition_authority"]["mandates"] = [slot]

        with TestClient(app()) as client:
            source, human_ref = approve_request(client, request, resource_digest)
            slot["human_decision_record_ref"] = human_ref

        # Controlled development composition selects a genuine production WDI
        # port with explicit external owner fixtures. All route/gateway/DS9/job
        # owners run unchanged; production PostgreSQL bootstrap is separate.
        cases = []
        monkeypatch.setattr(
            acquisition_chain,
            "intercepted_wdi_transport",
            lambda patch: intercepted_wdi_transport(patch, allow_loopback=True),
        )

        def select_fixture_port(*, control_service, **kwargs):
            # Each restart discards the prior transport/candidate fixture hooks
            # and reopens the same external inputs with a fresh owner bridge.
            port_patch.undo()
            refreshes = ()
            if candidate_generation_mode[0]:
                from polisyos.runtime.quality.acquisition_world_growth import (
                    AcquisitionCandidateWorldRefresh,
                )

                refreshes = (
                    AcquisitionCandidateWorldRefresh(
                        tenant_id=closure.tenant_id,
                        cell_id=closure.cell_id,
                        run_id=closure.run_id,
                        route_id=closure.route_id,
                        profile_selection_ref=profile.profile_selection_ref,
                        canonical_variable_id="government.balance",
                        target_slot_id="government.balance",
                    ),
                )
            case = _within_fixture_owner(
                acquisition_chain.make_wdi_port_case,
                tmp_path / "wdi",
                port_patch,
                control=control_service,
                closure=closure,
                previous_case=cases[-1] if cases else None,
                candidate_world_refreshes=refreshes,
                candidate_scenario_generation=candidate_generation_mode[0],
                candidate_generation_recording=(
                    served_n4_recording if candidate_generation_mode[0] else None
                ),
                # The initial route carries one N6-stage cap through restarts.
                # A compute cap establishes neither authority nor causal coupling.
                reentry_budget_usd=Decimal("0.50"),
            )
            cases.append(case)
            if candidate_generation_mode[0] and remove_acquired_n5_baseline:
                from polisyos.runtime.quality.generation_cycle import JointSimulationPort

                original_build_candidate_request = (
                    JointSimulationPort._build_candidate_simulation_request
                )

                def remove_acquired_baseline_from_n5_request(
                    simulation_port,
                    *,
                    candidate,
                    problem,
                    input_record,
                ):
                    request = original_build_candidate_request(
                        simulation_port,
                        candidate=candidate,
                        problem=problem,
                        input_record=input_record,
                    )
                    baseline_state = dict(request.baseline_state)
                    baseline_state[model_declaration.target_world_slot] = (
                        model_declaration.target_baseline
                    )
                    baseline_state[model_declaration.outcome_variable] = (
                        model_declaration.outcome_baseline
                    )
                    removal_probe_n5_baselines.append(baseline_state)
                    return request.model_copy(update={"baseline_state": baseline_state})

                port_patch.setattr(
                    JointSimulationPort,
                    "_build_candidate_simulation_request",
                    remove_acquired_baseline_from_n5_request,
                )
            return case.port

        monkeypatch.setattr(
            acquisition_surface_execution,
            "build_production_world_bank_wdi_execution_port",
            select_fixture_port,
        )
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            response, _ = trust.post(
                client,
                path + "/execute",
                request.model_dump(mode="json"),
                route=route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None
            admitted_scope = control._control_store.get_job_created_event_payload(job_id)[
                "execution_scope"
            ]
            assert admitted_scope["status"] == "established"
            assert admitted_scope["tenant_id"] == TENANT
            assert admitted_scope["cell_id"] == CELL
            assert admitted_scope["actor_subject"] == job.submitted_by
            assert admitted_scope["actor_authenticated"] is True
            assert admitted_scope["actor_roles"] == sorted(set(admitted_scope["actor_roles"]))
            persisted_payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            decision_ref = persisted_payload["decision_ref"]
            allowed = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, decision_ref)
                )
            )
            assert allowed.outcome == "allowed"
            assert allowed.human_decision_record_ref == slot["human_decision_record_ref"]
            assert allowed.permission_snapshot == source.permission_snapshot
            assert not cases[-1].transport_calls

        # Fresh container/provider: actual durable job replay has no live DS20 proof.
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            job = control._control_store.get_job(job_id)
            dispatch_one_control_job(
                store=control._control_store,  # noqa: SLF001
                handler=control._process_control_job,  # noqa: SLF001
                expected_job_id=job_id,
            )
            completed_job = control._control_store.get_job(job_id)
            assert completed_job.state == "completed", completed_job
            result = completed_job.progress
            assert result["state"] == "completed", result
            assert result["receipt_phase"] == "terminal", result
            assert cases[-1].transport_calls
            receipt = _read_owned_terminal(control._artifact_store, result["terminal_receipt_ref"])
            assert receipt.receipt_phase == "terminal"
            assert receipt.action_generation == 1
            assert receipt.terminal_outcome == "quarantined_no_growth"
            first_terminal_ref = result["terminal_receipt_ref"]
            first_job_id = job_id
            first_progress = dict(completed_job.progress)
            retained_refs = (first_terminal_ref, *receipt.owner_receipt_refs)
            retained_bytes = {
                ref: _within_fixture_owner(control._artifact_store.get_bytes, ref)
                for ref in retained_refs
            }
            assert not any(
                _within_fixture_owner(control._artifact_store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_receipt"
                for ref in receipt.owner_receipt_refs
            )
            assert _within_fixture_owner(cases[-1].bridge.has_deferred_admission, closure)
            before = tuple(cases[-1].transport_calls)
            _within_fixture_owner(cases[-1].appoint_native_policy)
            assert tuple(cases[-1].transport_calls) == before

            # A new action changes the exact request/resource and needs its own
            # mandate, currentness evidence, human decision and durable allow.
            request = request.model_copy(
                update={"idempotency_key": "served-acquisition-admission-after-appointment"}
            )
            response, resource_digest = trust.post(
                client,
                path + "/decision-request",
                request.model_dump(mode="json"),
                route=route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            new_slot, job_id = appoint_mandate(control, request, resource_digest)
            assert job_id != first_job_id
            assert new_slot["resource_digest"] != slot["resource_digest"]
            assert new_slot["delegation_contract_ref"] != slot["delegation_contract_ref"]
            trust.raw["acquisition_authority"]["mandates"].append(new_slot)
            slot = new_slot
            candidate_generation_mode[0] = True

        with TestClient(app()) as client:
            source, human_ref = approve_request(client, request, resource_digest)
            slot["human_decision_record_ref"] = human_ref

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            response, _ = trust.post(
                client,
                path + "/execute",
                request.model_dump(mode="json"),
                route=route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None
            payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            second_decision_ref = payload["decision_ref"]
            assert second_decision_ref != decision_ref
            allowed = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, second_decision_ref)
                )
            )
            assert allowed.outcome == "allowed"
            assert allowed.human_decision_record_ref == human_ref
            assert allowed.permission_snapshot == source.permission_snapshot
            assert not cases[-1].transport_calls

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            job = control._control_store.get_job(job_id)
            assert job is not None
            admitted_scope = control._control_store.get_job_created_event_payload(job_id)[
                "execution_scope"
            ]
            assert admitted_scope["status"] == "established"
            assert admitted_scope["tenant_id"] == TENANT
            assert admitted_scope["cell_id"] == CELL
            assert admitted_scope["actor_subject"] == job.submitted_by
            assert admitted_scope["actor_authenticated"] is True
            assert admitted_scope["actor_roles"] == sorted(set(admitted_scope["actor_roles"]))
            (
                _dispatched_job_id,
                semantic_epoch_finalizer_exceptions,
                semantic_epoch_value_error_event_census,
            ) = (
                _capture_semantic_epoch_finalizer_failure(
                    lambda: dispatch_one_control_job(
                        store=control._control_store,  # noqa: SLF001
                        handler=control._process_control_job,  # noqa: SLF001
                        expected_job_id=job_id,
                    )
                )
            )
            completed_job = control._control_store.get_job(job_id)
            assert completed_job.state == "completed", completed_job
            result = completed_job.progress
            assert result["receipt_phase"] == "terminal", result
            receipt = _read_owned_terminal(control._artifact_store, result["terminal_receipt_ref"])
            assert receipt.action_generation == 2
            terminal_diagnostic = json.dumps(
                {
                    "terminal_outcome": receipt.terminal_outcome,
                    "semantic_epoch_finalizer_exceptions": semantic_epoch_finalizer_exceptions,
                    "semantic_epoch_value_error_event_census": (
                        semantic_epoch_value_error_event_census
                    ),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            assert receipt.terminal_outcome == "reentry_completed", terminal_diagnostic
            assert not cases[-1].transport_calls
            assert control._control_store.get_job(first_job_id).progress == first_progress
            assert all(
                _within_fixture_owner(control._artifact_store.get_bytes, ref) == blob
                for ref, blob in retained_bytes.items()
            )
            growth_refs = [
                ref
                for ref in receipt.owner_receipt_refs
                if _within_fixture_owner(control._artifact_store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_receipt"
            ]
            assert growth_refs, receipt
            growth = _within_fixture_owner(cases[-1].port.project_world_growth, closure)
            assert growth.admitted_observation_delta == 1
            assert receipt.tenant_id == closure.tenant_id
            assert receipt.cell_id == closure.cell_id
            assert receipt.run_id == closure.run_id
            assert receipt.source_job_id == closure.source_job_id
            reentry_ref = receipt.reentry_receipt_ref
            assert reentry_ref is not None, receipt
            reentry_scope = _within_fixture_owner(
                reconcile_authority_ref,
                artifact_store=control._artifact_store,
                event_log=cases[-1].bridge.event_log,
                cas_ref=reentry_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            assert reentry_scope.durable_event_id is not None
            reentry = AcquisitionOverlayReentryReceipt.model_validate(
                _within_fixture_owner(
                    cases[-1].bridge._read,
                    reentry_ref,
                    "runtime_quality.acquisition_overlay_reentry_receipt",
                )
            )
            _within_fixture_owner(
                cases[-1].bridge._validate_reentry, closure, growth, reentry
            )
            cycle = reentry.new_cycle
            assert cycle.simulation.status == "joint_simulated", cycle.simulation
            assert cycle.simulation.candidate_id == cycle.selected_candidate_ref
            assert cycle.simulation.simulation_result_ref is not None
            diagnostics = cycle.simulation.diagnostics
            assert diagnostics["candidate_simulation_purpose"] == "candidate_scenario_n5_only"

            import numpy as np

            from polisyos.core.artifacts import ArtifactRef
            from polisyos.core.artifacts.manifest import (
                artifact_ref_identity_key,
                input_ref_from_artifact_ref,
            )
            from polisyos.core.contracts import epoch as epoch_contract
            from polisyos.core.contracts.fabric import DataSnapshot
            from polisyos.core.contracts.foundry import StateSnapshot
            from polisyos.data_forge.domains.catalog.knowledge.overlay import (
                CatalogAcquisitionOverlay,
            )
            from polisyos.foundry.execute.executor import (
                get_state_path,
                load_state_snapshot,
            )
            from polisyos.ir.analytics.ncm import (
                candidate_ncm_spec_from_declaration,
                load_ncm_spec_selected_view,
            )
            from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationExecutionV5,
                CandidateSimulationN5InputV5,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA,
                CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA,
                ConfiguredCandidateSimulationContextAdmissionOwner,
                CycleSubstrateContextArtifactOwner,
                CycleSubstrateContextJobArtifactV2,
                CycleSubstrateContextJobArtifactV3,
            )
            from polisyos.runtime.quality.design_problem import (
                _QualifiedOutcomeOfInterestV3,
            )
            from polisyos.runtime.quality.generation_cycle import (
                load_joint_simulation_result,
            )
            from polisyos.runtime.quality.generation_source import (
                GenerationSourceRepository,
                N4CandidateScenarioSourceRecordV3,
                candidate_scenario_semantic_identity_hash,
            )
            from polisyos.runtime.quality.world_model_record import (
                derive_candidate_scenario_world_model_record,
                world_model_artifact_views,
            )

            n5_input_ref = ArtifactRef.model_validate(
                diagnostics["candidate_simulation_n5_input_selected_ref"]
            )
            n5_input = CandidateSimulationN5InputV5.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, n5_input_ref)
                )
            )
            assert n5_input.original_candidate_id == cycle.selected_candidate_ref
            assert n5_input.outcome_variable == "global.tax_rate"
            assert n5_input.profile.rule.target_world_slot == "government.balance"
            assert n5_input.profile.context_inputs.world_model_record.authority_status == "limited"
            assert {
                "source_time_not_established",
                "source_to_target_measurement_contract_not_established",
                "causal_coupling_not_established",
            }.issubset(
                n5_input.profile.context_inputs.world_model_record.limitations.admissibility_blockers
            )

            source_repository = GenerationSourceRepository(
                control._artifact_store
            )
            source_record = _within_fixture_owner(
                source_repository.load_candidate_scenario_source_for_n5,
                n5_input.n4_source_ref,
                expected_run_id=n5_input.run_id,
                expected_job_id=n5_input.job_id,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
            )
            assert type(source_record) is N4CandidateScenarioSourceRecordV3
            assert source_record.origin_source_ref is None
            context_job = _within_fixture_owner(
                CycleSubstrateContextArtifactOwner(
                    store=control._artifact_store
                ).resolve_historical_job_artifact,
                n5_input.context_job_ref,
                problem=source_record.problem,
                expected_job_id=n5_input.job_id,
                expected_run_id=n5_input.run_id,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
            )
            context_job_manifest = _within_fixture_owner(
                control._artifact_store.get_manifest,
                n5_input.context_job_ref,
            )
            assert source_record.profile_selection_ref == n5_input.profile.profile_selection_ref
            assert source_record.stable_subject_ref == closure.design_problem_ref
            assert source_record.candidate_occurrence_hash == (
                source_record.candidate.atom.content_hash
            )
            assert n5_input.original_candidate_id == source_record.candidate.candidate_id
            assert n5_input.original_candidate_hash == source_record.candidate_occurrence_hash
            assert source_record.candidate.candidate_id == (
                "candidate_"
                + source_record.semantic_identity_hash.removeprefix("sha256:")[:16]
            )
            assert candidate_scenario_semantic_identity_hash(
                stable_subject_ref=source_record.stable_subject_ref,
                proposal=source_record.proposal,
                candidate=source_record.candidate,
                profile=source_record.profile,
            ) == source_record.semantic_identity_hash
            n4_selected_ref = ArtifactRef.model_validate(
                diagnostics["candidate_simulation_n4_source_selected_ref"]
            )
            assert artifact_ref_identity_key(n4_selected_ref) == artifact_ref_identity_key(
                n5_input.n4_source_ref
            )
            n4_manifest = _within_fixture_owner(
                control._artifact_store.get_manifest,
                n5_input.n4_source_ref,
            )
            assert input_ref_from_artifact_ref(
                source_record.source_ref,
                role="n4_source_v2",
            ) in n4_manifest.inputs
            source_v2 = source_record.source_record
            assert (
                source_v2.model_declaration.profile_selection_ref
                == model_declaration.profile_selection_ref
            )
            assert source_record.s8_status == "blocked"
            assert source_record.n9_status == "not_admitted"
            if (
                context_job.context.world_model_record.schema_version
                == "policyos.runtime.world_model_record.v2"
            ):
                assert type(context_job) is CycleSubstrateContextJobArtifactV3
                assert context_job.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA
            else:
                assert type(context_job) is CycleSubstrateContextJobArtifactV2
                assert context_job.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V2_SCHEMA
            assert type(context_job.problem.outcome_of_interest) is (
                _QualifiedOutcomeOfInterestV3
            )
            assert context_job.problem == source_record.problem
            assert context_job.design_problem_ref == source_record.cycle_problem_ref
            assert artifact_ref_identity_key(n5_input.context_job_ref) == (
                artifact_ref_identity_key(source_record.context_job_ref)
            )
            assert context_job_manifest.kind == (
                "runtime.quality.cycle_substrate_context_job"
            )
            assert context_job_manifest.artifact_schema is not None
            assert context_job_manifest.artifact_schema.name == context_job.schema_version
            assert context_job_manifest.artifact_schema.version == (
                "3.0"
                if context_job.schema_version == CYCLE_SUBSTRATE_CONTEXT_JOB_V3_SCHEMA
                else "2.0"
            )
            assert context_job_manifest.tenant_context is not None
            assert context_job_manifest.tenant_context.tenant_id == n5_input.tenant_id
            assert context_job_manifest.tenant_context.cell_id == n5_input.cell_id
            assert context_job_manifest.same_input_closure is not None
            assert context_job_manifest.same_input_closure.status == "candidate_only"
            assert context_job_manifest.same_input_closure.run_id == n5_input.run_id
            assert context_job_manifest.same_input_closure.job_id == n5_input.job_id
            assert context_job_manifest.same_input_closure.tenant_id == n5_input.tenant_id
            assert context_job_manifest.same_input_closure.cell_id == n5_input.cell_id
            assert context_job.profile_admission_status == "not_established"
            assert context_job.s8_status == "blocked"
            assert context_job.authority_purpose == "cycle_input_candidate_only"
            # Compare the complete persisted source/context/WMR selector chain,
            # including CAS manifest profiles rather than only artifact IDs.
            # None selects the owner default; the NCM loader still validates it.
            selected_ncm_ref = n5_input.ncm_ref
            selected_ncm_identity = artifact_ref_identity_key(selected_ncm_ref)
            selected_ncm_spec = _within_fixture_owner(
                load_ncm_spec_selected_view,
                control._artifact_store,
                selected_ncm_ref,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
                expected_declaration_ref=source_v2.model_declaration_ref,
            )
            assert selected_ncm_spec.model_dump(mode="json") == (
                candidate_ncm_spec_from_declaration(
                    source_v2.model_declaration
                ).model_dump(mode="json")
            )
            assert artifact_ref_identity_key(source_record.ncm_ref) == selected_ncm_identity
            assert artifact_ref_identity_key(n5_input.materialization.ncm_ref) == (
                selected_ncm_identity
            )
            context_world = context_job.context.world_model_record
            assert source_record.world_model_record_hash == context_world.content_hash
            assert n5_input.materialization.world_model_record_hash == (
                context_world.content_hash
            )
            acquired_world = n5_input.profile.context_inputs.world_model_record
            assert acquired_world.authority_status == "limited"
            assert context_world.authority_status == acquired_world.authority_status
            assert context_world.limitations == acquired_world.limitations
            assert context_world.simulation_model_ref.calibrated is False
            assert context_world.simulation_model_ref.calibration_ref is None
            assert (
                context_world.simulation_model_ref.fidelity_level
                == "declared_candidate_scenario"
            )
            assert any(
                item.get("declaration_content_hash")
                == source_v2.model_declaration.content_hash
                and item.get("status") == "candidate_only_not_empirically_grounded"
                for item in context_world.simulation_model_ref.assumptions
            )

            registry_admission_owner = (
                cases[-1].bridge.cycle_substrate_context_admission_owner
            )
            assert type(registry_admission_owner) is (
                ConfiguredCandidateSimulationContextAdmissionOwner
            )
            configured_profile_for_registry = _within_fixture_owner(
                registry_admission_owner.configured_profile_for_selection_ref,
                n5_input.profile.profile_selection_ref,
            )
            assert configured_profile_for_registry.profile_selection_ref == (
                n5_input.profile.profile_selection_ref
            )
            acquired_world_views = world_model_artifact_views(acquired_world)
            acquired_registry_view_ref = acquired_world_views.substrate_registry_ref
            assert acquired_registry_view_ref is not None
            resolved_registry_view_ref = _within_fixture_owner(
                registry_admission_owner._candidate_world_model_substrate_registry_view,
                world_model_record=acquired_world,
                substrate_registry=(
                    configured_profile_for_registry.context_inputs.substrate_registry
                ),
            )
            assert artifact_ref_identity_key(acquired_registry_view_ref) == (
                artifact_ref_identity_key(resolved_registry_view_ref)
            )

            expected_context_world = derive_candidate_scenario_world_model_record(
                acquired_world,
                ncm_artifact_ref=selected_ncm_ref,
                declaration_content_hash=source_v2.model_declaration.content_hash,
                substrate_registry_view_ref=resolved_registry_view_ref,
            )
            assert context_world.model_dump(mode="json") == (
                expected_context_world.model_dump(mode="json")
            )
            context_world_views = world_model_artifact_views(context_world)
            expected_context_world_views = world_model_artifact_views(
                expected_context_world
            )
            assert context_world_views.model_dump(mode="json") == (
                expected_context_world_views.model_dump(mode="json")
            )
            assert context_world_views.substrate_registry_ref is not None
            assert artifact_ref_identity_key(
                context_world_views.substrate_registry_ref
            ) == artifact_ref_identity_key(resolved_registry_view_ref)
            acquired_views_payload = acquired_world_views.model_dump(mode="json")
            context_views_payload = context_world_views.model_dump(mode="json")
            for view_field, acquired_view in acquired_views_payload.items():
                if view_field in {"ncm_refs", "substrate_registry_ref"}:
                    continue
                assert context_views_payload[view_field] == acquired_view

            expected_context_ncm_refs = []
            seen_context_ncm_ref_identities = set()
            for ref in (*acquired_world_views.ncm_refs, selected_ncm_ref):
                identity = artifact_ref_identity_key(ref)
                if identity in seen_context_ncm_ref_identities:
                    continue
                expected_context_ncm_refs.append(ref)
                seen_context_ncm_ref_identities.add(identity)
            assert context_world_views.ncm_refs == tuple(expected_context_ncm_refs)
            context_ncm_views = world_model_artifact_views(context_world).ncm_refs
            selected_context_ncm_views = tuple(
                ref
                for ref in context_ncm_views
                if artifact_ref_identity_key(ref) == selected_ncm_identity
            )
            assert len(selected_context_ncm_views) == 1
            assert selected_context_ncm_views[0] == selected_ncm_ref
            acquired_world = n5_input.profile.context_inputs.world_model_record
            context_data_snapshot_ref = world_model_artifact_views(
                context_world
            ).data_snapshot_ref
            data_snapshot_ref = world_model_artifact_views(
                acquired_world
            ).data_snapshot_ref
            assert artifact_ref_identity_key(data_snapshot_ref) == (
                artifact_ref_identity_key(context_data_snapshot_ref)
            )
            assert source_record.context_hash == context_job.context.content_hash

            growth = _within_fixture_owner(cases[-1].port.project_world_growth, closure)
            assert growth is not None
            overlay_path, _ = cases[-1].bridge._paths(growth.selection, create=False)
            overlay = CatalogAcquisitionOverlay(
                cases[-1].authority.baseline_path,
                overlay_path=overlay_path,
            )
            passport = AdmissionPassport.model_validate(
                _within_fixture_owner(
                    epoch_contract.load_verified_epoch_statement,
                    store=control._artifact_store,
                    ref=growth.activation.passport_ref,
                    expected_kind="epoch.acquisition_passport_snapshot",
                )
            )
            projection = _within_fixture_owner(
                overlay.read_activated_semantic_epoch_observations,
                receipt_ref=growth.activation.overlay_admission_receipt_ref,
                artifact_store=control._artifact_store,
                passport=passport,
                authority=cases[-1].authority,
            )
            selected_rows = tuple(
                item
                for item in projection.observations
                if item.observation.canonical_var == "government.balance"
            )
            assert len(selected_rows) == 1
            selected = selected_rows[0]
            acquired_world = n5_input.profile.context_inputs.world_model_record
            data_snapshot_ref = world_model_artifact_views(
                acquired_world
            ).data_snapshot_ref
            assert str(data_snapshot_ref.artifact_id) == (
                acquired_world.simulation_model_ref.data_snapshot_ref
            )
            data_snapshot = DataSnapshot.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(control._artifact_store.get_bytes, data_snapshot_ref)
                )
            )
            snapshot_payload = canon.from_canonical_bytes(
                _within_fixture_owner(
                    control._artifact_store.get_bytes,
                    data_snapshot.data_ref,
                )
            )
            acquired_value = snapshot_payload["acquisition"]["selected"]
            assert acquired_value["observation_id"] == selected.observation.observation_id
            assert acquired_value["value"] == selected.observation.value
            assert acquired_value["source_time_status"] == "not_established"
            acquired_world_views = world_model_artifact_views(acquired_world)
            bound_state_ref = acquired_world_views.bound_state_snapshot_ref
            assert bound_state_ref is not None
            bound_state_verification = _within_fixture_owner(
                control._artifact_store.verify,
                bound_state_ref,
            )
            assert bound_state_verification.ok, bound_state_verification.error
            bound_state_manifest = _within_fixture_owner(
                control._artifact_store.get_manifest,
                bound_state_ref,
            )
            bound_state_snapshot = StateSnapshot.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(
                        control._artifact_store.get_bytes,
                        bound_state_ref,
                    )
                )
            )
            assert bound_state_manifest.inputs == bound_state_snapshot.lineage_inputs
            assert input_ref_from_artifact_ref(
                data_snapshot_ref,
                role="input.data_snapshot_ref",
            ) in bound_state_snapshot.lineage_inputs
            bound_state = _within_fixture_owner(
                load_state_snapshot,
                control._artifact_store,
                snapshot_ref=bound_state_ref,
            )

            typed_state_by_slot = {}
            expected_profile_baseline = {}
            for slot_id in sorted(n5_input.profile.n5.baseline_state):
                binding = acquired_world.slot_binding(slot_id)
                assert binding is not None, slot_id
                assert binding.state_path
                typed_value = np.asarray(
                    _within_fixture_owner(
                        get_state_path,
                        bound_state,
                        binding.state_path,
                    )
                )
                assert typed_value.size == 1, slot_id
                typed_state_by_slot[slot_id] = typed_value
                expected_profile_baseline[slot_id] = float(typed_value.item())
            assert n5_input.profile.n5.baseline_state == expected_profile_baseline

            target_slot = n5_input.profile.rule.target_world_slot
            typed_target_value = typed_state_by_slot[target_slot]
            selected_value_in_bound_dtype = np.asarray(
                selected.observation.value,
                dtype=typed_target_value.dtype,
            ).item()
            assert selected_value_in_bound_dtype == typed_target_value.item()
            declaration = source_v2.model_declaration
            assert declaration.target_baseline == expected_profile_baseline[
                declaration.target_world_slot
            ]
            assert declaration.outcome_baseline == expected_profile_baseline[
                declaration.outcome_variable
            ]

            n5_result_ref = cycle.simulation.simulation_result_ref
            n5_result = _within_fixture_owner(
                load_joint_simulation_result,
                n5_result_ref,
                store=control._artifact_store,
            )
            selected_result_decisions = tuple(
                decision
                for decision in n5_result.engine_decisions
                if decision.decision == "selected"
            )
            assert len(selected_result_decisions) == 1
            selected_result_decision = selected_result_decisions[0]
            assert n5_input.n5.engine_kind == "ncm_parallel_worlds"
            assert selected_result_decision.engine_kind == n5_input.n5.engine_kind
            assert n5_result.receipt.engine_kind == selected_result_decision.engine_kind
            joint_atom_ids = (
                n5_input.materialization.derived_n5_atom.intervention_id,
            )
            joint_trajectories = tuple(
                item
                for item in n5_result.trajectories
                if item.run_level == "joint" and item.atom_ids == joint_atom_ids
            )
            assert len(joint_trajectories) == 1
            trajectory = joint_trajectories[0]
            assert trajectory.engine_kind == selected_result_decision.engine_kind
            assert trajectory.method_fqn == selected_result_decision.method_fqn
            assert "global.tax_rate" in n5_result.selected_outcomes
            assert n5_result.world_model_record_content_hash == (
                n5_input.materialization.world_model_record_hash
            )
            assert n5_input.materialization.value == 2

            execution_ref = ArtifactRef.model_validate(
                diagnostics["candidate_simulation_execution_selected_ref"]
            )
            execution = _within_fixture_owner(
                source_repository.resolve_candidate_simulation_v5,
                ref=execution_ref,
                expected_run_id=n5_input.run_id,
                expected_job_id=n5_input.job_id,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
            )
            assert type(execution) is CandidateSimulationExecutionV5
            assert execution.authority_purpose == "candidate_scenario_n5_only"
            assert execution.run_id == n5_input.run_id
            assert execution.job_id == n5_input.job_id
            assert execution.tenant_id == n5_input.tenant_id
            assert execution.cell_id == n5_input.cell_id
            assert artifact_ref_identity_key(execution.n5_input_ref) == (
                artifact_ref_identity_key(n5_input_ref)
            )
            assert artifact_ref_identity_key(execution.n4_source_ref) == (
                artifact_ref_identity_key(n5_input.n4_source_ref)
            )
            assert artifact_ref_identity_key(execution.context_job_ref) == (
                artifact_ref_identity_key(n5_input.context_job_ref)
            )
            assert artifact_ref_identity_key(execution.model_declaration_ref) == (
                artifact_ref_identity_key(source_v2.model_declaration_ref)
            )
            assert artifact_ref_identity_key(execution.ncm_ref) == (
                artifact_ref_identity_key(selected_ncm_ref)
            )
            assert artifact_ref_identity_key(execution.n5_result_ref) == (
                artifact_ref_identity_key(n5_result_ref)
            )
            assert execution.world_model_record_hash == (
                n5_input.materialization.world_model_record_hash
            )
            assert execution.n5_result_content_hash == n5_result.receipt.payload_hash
            assert source_v2.model_declaration.target_baseline != pytest.approx(
                model_declaration.target_baseline
            )
            computed_outcome = trajectory.points[-1].outcomes["global.tax_rate"]
            if remove_acquired_n5_baseline:
                assert removal_probe_n5_baselines, (
                    "removal probe did not reach the owner N5 request builder"
                )
                assert all(
                    baseline[model_declaration.target_world_slot]
                    == model_declaration.target_baseline
                    and baseline[model_declaration.outcome_variable]
                    == model_declaration.outcome_baseline
                    for baseline in removal_probe_n5_baselines
                )
            else:
                assert not removal_probe_n5_baselines
            acquired_value_outcome = (
                source_v2.model_declaration.outcome_baseline
                + source_v2.model_declaration.outcome_per_target_unit
                * (
                    n5_input.materialization.value
                    - source_v2.model_declaration.target_baseline
                )
            )
            unacquired_value_outcome = (
                model_declaration.outcome_baseline
                + model_declaration.outcome_per_target_unit
                * (
                    n5_input.materialization.value
                    - model_declaration.target_baseline
                )
            )
            assert computed_outcome == pytest.approx(acquired_value_outcome, abs=1e-9)
            assert computed_outcome != pytest.approx(unacquired_value_outcome, abs=1e-9)

    finally:
        port_patch.undo()
        trust.close()
