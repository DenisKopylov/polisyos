"""Shared real served-acquisition fixture producer and controlled consumers."""

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
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.http import deployment_security as security
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.quality import agent_action_authority as authority
from polisyos.runtime.quality import substrate_registry
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceipt
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_AUTHORITY_RULE_VERSION,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
    DelegatedActionEnvelope,
    DelegationContract,
    build_decision_rights_matrix,
    build_delegation_contract,
    build_governance_decision_class_registry,
)
from tests._helpers.acquisition_human_decision import _mandate_authority_evidence
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import LocalJWKSStub
from tests._helpers.runtime_http import (
    deployment_security_config_mapping as _config_mapping,
)

TENANT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CELL = "018f47a0-0000-7000-8000-000000000001"
REPO_ROOT = Path(__file__).resolve().parents[2]

NOW = datetime(2026, 8, 30, 12, tzinfo=UTC)
TENANT_ID = "tenant-acquisition"
MANDATE_OWNER_REF = "principal://mandate-owner/acquisition"
RESOURCE_DIGEST = "sha256:9474372986dd62a9d754a235da9be00dcc68c344ce7935bf6f8a6a05fb8e77c0"


def _boundary(*, authoritative_for: str, source: str) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[authoritative_for],
        may_not_use_for=[
            "claim_evidence",
            "publication_authority",
            "promotion_authority",
        ],
        source_authority=source,
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _contract() -> DelegationContract:
    registry = build_governance_decision_class_registry(
        "case-acquisition", AGENT_ACTION_AUTHORITY_RULE_VERSION
    )
    matrix = build_decision_rights_matrix(
        "case-acquisition", registry, AGENT_ACTION_AUTHORITY_RULE_VERSION
    )
    legacy = build_delegation_contract(
        case_id="case-acquisition",
        matrix=matrix,
        governance_decision_classes=registry,
        s6_mandate_record_ref="pdc://acquisition/mandate",
        s6_mandate_firewall_disposition="pass",
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
    ).model_dump(mode="json")
    envelope = DelegatedActionEnvelope(
        envelope_id="envelope-acquisition",
        envelope_ref="pdc://acquisition/envelope",
        case_id="case-acquisition",
        mandate_owner_ref=MANDATE_OWNER_REF,
        owner_role="mandate_owner",
        action_kind=ACQUISITION_ACTION_KIND,
        operation_id=ACQUISITION_ACTION_KIND,
        operation_version="v1",
        required_permission=RuntimePermission.EVIDENCE_ACQUIRE,
        authorized_subject="user:acquisition-operator",
        authorized_runtime_roles=(PolicyOSRole.ANALYST,),
        required_tenant_id=TENANT_ID,
        required_resource_digest=RESOURCE_DIGEST,
        valid_from=NOW - timedelta(minutes=5),
        valid_until=NOW + timedelta(hours=1),
        status="active",
        issuance_decision_ref="pdc://acquisition/issuance",
        provenance_refs=("pdc://acquisition/mandate-owner",),
        rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
        authority_boundary=_boundary(
            authoritative_for="agent_action_envelope", source="human_governance"
        ),
    )
    legacy.update(
        {
            "schema_version": LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
            "mandate_owner_ref": MANDATE_OWNER_REF,
            "action_envelopes": [envelope.model_dump(mode="json")],
        }
    )
    return DelegationContract.model_validate(legacy)


def _within_fixture_owner(call, *args, **kwargs):
    """Emit external fixture inputs under their actual tenant/cell ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        return call(*args, **kwargs)


def _safe_validation_error_fields(exception):
    """Keep only Pydantic location names and error type identifiers."""
    exception_type = type(exception)
    if exception_type.__name__ != "ValidationError" or exception_type.__module__.split(
        ".", maxsplit=1
    )[0] not in {"pydantic", "pydantic_core"}:
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
        safe_rows.append({"loc": tuple(location), "type": error_type})
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
                if isinstance(exception_type, type) and issubclass(exception_type, ValueError):
                    value_error_event_rows.append(row)
                rows = by_exception.setdefault(id(exception), [])
                if not rows or rows[-1] != row:
                    rows.append(row)
                if is_finalizer:
                    captured.append(
                        {
                            "exception_type": exception_type.__name__,
                            "frames": tuple(rows),
                            "validation_error_fields": _safe_validation_error_fields(exception),
                        }
                    )
        elif event == "return" and is_finalizer:
            target_frames.discard(id(frame))
        return trace

    sys.settrace(trace)
    try:
        return (
            call(),
            captured,
            {
                "scope": "all_value_error_trace_events_inside_finalizer_call",
                "identity": "trace_events_not_unique_exception_objects",
                "events": tuple(value_error_event_rows),
            },
        )
    finally:
        sys.settrace(prior_trace)


def _read_owned_terminal(store, ref):
    """Read the actual terminal schema through scoped immutable CAS ownership."""
    with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
        assert store.get_manifest(ref).kind == "runtime_quality.acquisition_route_loop_receipt"
        return AcquisitionRouteLoopReceipt.model_validate(
            canon.from_canonical_bytes(store.get_bytes(ref))
        )


def _served_wdi_candidate_profile(
    *, tmp_path, store, problem, source_owner_root: Path | None = None
):
    """Build one typed synthetic N5 profile over a real owner-built base WMR."""
    tmp_path.mkdir(parents=True, exist_ok=True)

    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate,
        WorkRecord,
    )
    from polisyos.data_forge.read_api.academic import SKGQuery
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
    from polisyos.runtime.quality.data_state_substrate import (
        ACQUIRED_DATA_STATE_LIMITATION_CODES,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        SkgCausalPriorRef,
        WorldModelLimitations,
        build_world_model_record,
    )
    from tests._helpers import world_model_record as wmr_fixture
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    source_owner_root = (
        Path(source_owner_root).resolve(strict=True) if source_owner_root is not None else None
    )
    snapshot_id = "served-wdi-controlled-candidate-base"
    base_data_snapshot_ref = wmr_fixture._data_snapshot_ref(store, snapshot_id=snapshot_id)
    substrate_registry = wmr_fixture._substrate_registry()
    substrate_registry_ref = persist_substrate_registry(store, substrate_registry)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = wmr_fixture._model_spec(
        base_data_snapshot_ref,
        registry_bundle.bundle_ref,
    )
    wmr_fixture._write_fabric_world_snapshot(tmp_path, snapshot_id=snapshot_id)
    # Use the canonical batch producer, then validate the exact selected source
    # through the prepared reader consumed by the real credal-reference path.
    selected_skg_root = (source_owner_root or tmp_path) / "controlled-candidate-source"
    selected_skg_root.mkdir(parents=True, exist_ok=True)
    selected_skg_db_path = selected_skg_root / "academic-skg.duckdb"
    selected_skg_record = WorkRecord(
        id="served-controlled-candidate-skg",
        title="Synthetic candidate source fixture",
        abstract="Synthetic fixture data; no causal or production claim.",
        year=2026,
        estimates=[
            EstimateCandidate(
                value=0.0,
                pattern_name="controlled_candidate_fixture",
                variable_hint="government.balance",
            ),
            EstimateCandidate(
                value=0.0,
                pattern_name="controlled_candidate_fixture",
                variable_hint="global.tax_rate",
            ),
        ],
        metadata={"synthetic": True, "fixture_scope": "served_candidate_only"},
    )
    build_synthetic_academic_skg_source(
        records=(selected_skg_record,),
        db_path=selected_skg_db_path,
    )
    prepared_skg = SKGQuery.prepare_read(
        db_path=selected_skg_db_path,
        index_dir=selected_skg_root / "index",
    )
    try:
        selected_skg_rows = prepared_skg.read_credal_source_rows()
        selected_skg_version_id = int(selected_skg_rows.version_id)
        selected_skg_snapshot_ref = prepared_skg.source_snapshot_ref
        selected_variables = {row.canonical_name for row in selected_skg_rows.variables}
        if not {"government.balance", "global.tax_rate"}.issubset(selected_variables):
            raise AssertionError("served_controlled_skg_producer_variables_missing")
        if selected_skg_rows.causal_edges:
            raise AssertionError("served_controlled_candidate_fixture_claimed_causal_edges")
    finally:
        prepared_skg.close()
    skg_causal_prior_ref = SkgCausalPriorRef(
        skg_snapshot_ref=selected_skg_snapshot_ref,
        skg_version_id=str(selected_skg_version_id),
        source_data_snapshot_id=snapshot_id,
    )
    base_world = build_world_model_record(
        store,
        fabric_world_ref=wmr_fixture._fabric_ref(tmp_path, snapshot_id=snapshot_id),
        data_forge_snapshot_binding_path=wmr_fixture._write_data_forge_binding(
            tmp_path, snapshot_id=snapshot_id
        ),
        data_snapshot_ref=base_data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=skg_causal_prior_ref,
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
        limitations=WorldModelLimitations(
            admissibility_blockers=ACQUIRED_DATA_STATE_LIMITATION_CODES,
        ),
        candidate_only=True,
        substrate_registry_artifact_ref=substrate_registry_ref,
    )
    slot_units = {binding.slot_id: binding.unit for binding in base_world.record.policy_slot_map}
    target_baseline = float(base_world.bound_global_state.government_balance)
    outcome_baseline = float(base_world.bound_global_state.tax_rate)
    selected_hashes = tuple(entry.entry_content_hash for entry in substrate_registry.entries)
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
            REPO_ROOT,
            source_owner_root=source_owner_root,
        ),
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("served-wdi-controlled-candidate-source-pack"),
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
        "schema_version": ("policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"),
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
                (
                    "acquisition-operator",
                    ["evidence.acquire", "runs.launch", "runs.review", "runs.view"],
                ),
                (
                    "human-reviewer-1",
                    ["runs.human_decisions.create", "runs.review", "runs.view"],
                ),
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
        self,
        client,
        path,
        body,
        *,
        route,
        subject="acquisition-operator",
        extra_headers=None,
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
        "provenance": {
            "source": "fixture_external_institution",
            "reference": "served-acquisition",
        },
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
            for field, name in (
                ("admission_signer", "admission"),
                ("decision_signer", "source"),
            )
        },
    }
    return signers, identities


def _produce_served_acquisition_history(
    tmp_path,
    monkeypatch,
    served_recorded_candidate_gateway,
    *,
    fixture_cas_root: Path | None = None,
    stop_after_fresh_get: bool = False,
    include_b09_evidence: bool = False,
    source_owner_root: Path | None = None,
    include_default_only_compiled_probe: bool = False,
) -> dict[str, str] | None:
    import os

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.runtime.http.services import (
        acquisition_action_service,
        acquisition_surface_execution,
    )
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.http.services.control import (
        nl_pipeline as nl_pipeline_service,
    )
    from polisyos.runtime.quality.authority_reconciliation import (
        reconcile_authority_ref,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
    from polisyos.runtime.quality.generation_cycle import (
        AcquisitionOverlayReentryReceipt,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )
    from tests._helpers import acquisition_chain
    from tests._helpers.acquisition_human_decision import (
        persist_signed,
        prepare_human_decision,
    )
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        intercepted_wdi_transport,
        resolve_completed_wdi_route,
    )
    from tests._helpers.controlled_candidate_profile import _current_compiler_problem
    from tests._helpers.runtime_http import (
        _DeterministicSpanSupportClient,
        _valid_intake_for_mode,
    )

    selected_source_root = (
        Path(source_owner_root).resolve(strict=True) if source_owner_root is not None else None
    )
    if selected_source_root == REPO_ROOT.resolve():
        raise ValueError("served_acquisition_candidate_source_root_must_be_fixture_owned")

    served_n4_recording = acquisition_chain.load_served_wdi_generation_recording()
    served_n4_model_id = str(served_n4_recording["model_id"])
    fiscal_nl_request = acquisition_chain.SERVED_WDI_FISCAL_REQUEST
    fiscal_scope_source = acquisition_chain.SERVED_WDI_FISCAL_SCOPE_SOURCE
    candidate_only_source = acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    install_fixture_wdi_cost_basis(monkeypatch)
    # Use the fixture's typed Catalog selector for both the base profile and
    # every served K_ref reader. Preserve the legacy startup-only path for tests
    # that do not select an isolated source root.
    catalog_selection = None
    catalog_serving_source = None
    selected_catalog_readback = None
    l6_source_reads = []
    bind_expected_l6_source = None
    assert_l6_adapter_installed = None
    if selected_source_root is None:
        catalog_root = tmp_path / "retrieval-catalog"
        catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
        default_catalog_paths = substrate_registry.default_substrate_catalog_paths
        startup_root = Path.cwd().resolve()
        fixture_catalog_path = catalog_root / "catalog.duckdb"

        def selected_catalog_paths(root, *, source_owner_root=None):
            resolved_root = Path(root).resolve()
            paths = default_catalog_paths(root, source_owner_root=source_owner_root)
            if resolved_root == startup_root and source_owner_root is None:
                return replace(paths, l1_dcat_path=fixture_catalog_path)
            return paths

        monkeypatch.setattr(
            substrate_registry,
            "default_substrate_catalog_paths",
            selected_catalog_paths,
        )
    else:
        from tests._helpers.candidate_cycle_source_profile import (
            build_candidate_cycle_catalog_serving_source,
            candidate_cycle_catalog_source_readback,
            install_candidate_cycle_l6_source_root_reader,
        )

        catalog_selection, catalog_serving_source = build_candidate_cycle_catalog_serving_source(
            selected_source_root
        )
        selected_catalog_readback = candidate_cycle_catalog_source_readback(
            catalog_serving_source.database_path
        )
        (
            l6_source_reads,
            bind_expected_l6_source,
            assert_l6_adapter_installed,
        ) = install_candidate_cycle_l6_source_root_reader(
            monkeypatch,
            code_root=REPO_ROOT,
            source_owner_root=selected_source_root,
        )
    trust = _ExternalTrust(tmp_path)
    port_patch = pytest.MonkeyPatch()
    signers, identities = _key_config(tmp_path, trust)
    cas_root = fixture_cas_root or (tmp_path / "cas")
    candidate_profiles = []
    candidate_model_declarations = []
    # Seed the first and re-entry N4 actions from the same recorded candidate.
    candidate_generation_mode = [True]
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
            repo_root=selected_source_root,
            catalog_source_selection=catalog_selection,
            catalog_run_profile=(
                catalog_selection.catalog_run_profile if catalog_selection is not None else None
            ),
        )

    base_compiler_problem = _current_compiler_problem(served_n4_recording)
    legacy_industrial_request = base_compiler_problem.nl_provenance.raw_request
    assert fiscal_scope_source in fiscal_nl_request
    assert candidate_only_source in fiscal_nl_request
    assert legacy_industrial_request != fiscal_nl_request
    recorded_problem = acquisition_chain.controlled_served_wdi_problem(
        base_compiler_problem, raw_request=fiscal_nl_request
    )
    controlled_recording = acquisition_chain.controlled_served_wdi_generation_recording(
        served_n4_recording,
        outcome_variable=recorded_problem.outcome_of_interest.target_variable,
    )
    served_recorded_candidate_gateway.set_fixture(controlled_recording, problem=recorded_problem)
    if catalog_serving_source is None:
        profile, model_declaration = _within_fixture_owner(
            _served_wdi_candidate_profile,
            tmp_path=tmp_path / "served-candidate-profile",
            store=artifacts.FileSystemCAS(cas_root, ownership_enforced=True),
            problem=recorded_problem,
            source_owner_root=selected_source_root,
        )
    else:
        with substrate_registry.catalog_serving_source_scope(catalog_serving_source):
            profile, model_declaration = _within_fixture_owner(
                _served_wdi_candidate_profile,
                tmp_path=tmp_path / "served-candidate-profile",
                store=artifacts.FileSystemCAS(cas_root, ownership_enforced=True),
                problem=recorded_problem,
                source_owner_root=selected_source_root,
            )
    source_root_witness_json = None
    actual_kref_witnesses = []
    if selected_source_root is not None:
        import duckdb

        from polisyos.data_forge.read_api.academic import SKGQuery
        from polisyos.runtime.quality import credal_reference, design_generation
        from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths
        from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref
        from tests._helpers.candidate_cycle_source_profile import (
            bind_candidate_cycle_kref_builder_root,
            candidate_cycle_kref_source_witness,
        )

        wmr_source = profile.context_inputs.world_model_record.skg_causal_prior_ref
        parsed_skg = _parse_skg_snapshot_ref(wmr_source.skg_snapshot_ref)
        selected_l2_path = parsed_skg.db_path.resolve(strict=True)
        if not selected_l2_path.is_relative_to(selected_source_root):
            raise AssertionError("served_candidate_selected_l2_source_outside_fixture_root")
        selected_skg_reader = SKGQuery.prepare_read(
            db_path=selected_l2_path,
            index_dir=selected_l2_path.parent / "index",
        )
        try:
            selected_skg_rows = selected_skg_reader.read_credal_source_rows()
            if selected_skg_rows.version_id != parsed_skg.version_id:
                raise AssertionError("served_candidate_selected_l2_version_mismatch")
        finally:
            selected_skg_reader.close()

        if catalog_serving_source is None or selected_catalog_readback is None:
            raise AssertionError("served_candidate_typed_catalog_source_missing")
        l1_path = catalog_serving_source.database_path.resolve(strict=True)
        if not l1_path.is_relative_to(selected_source_root):
            raise AssertionError("served_candidate_selected_l1_source_outside_fixture_root")
        l3_path = (selected_source_root / substrate_registry.DEFAULT_L3_LEX_KG_PATH).resolve(
            strict=True
        )
        if not l3_path.is_relative_to(selected_source_root):
            raise AssertionError("served_candidate_selected_l3_source_outside_fixture_root")
        l3_connection = duckdb.connect(str(l3_path), read_only=True)
        try:
            l3_row_counts = {
                "lex_amendments": int(
                    l3_connection.execute("SELECT COUNT(*) FROM lex_amendments").fetchone()[0]
                ),
                "lex_normative_ready_facts": int(
                    l3_connection.execute(
                        "SELECT COUNT(*) FROM lex_normative_ready_facts"
                    ).fetchone()[0]
                ),
                "lex_reference_edges": int(
                    l3_connection.execute("SELECT COUNT(*) FROM lex_reference_edges").fetchone()[0]
                ),
                "lex_rule_thresholds": int(
                    l3_connection.execute("SELECT COUNT(*) FROM lex_rule_thresholds").fetchone()[0]
                ),
            }
        finally:
            l3_connection.close()
        l6_paths = default_l6_bundle_paths(REPO_ROOT, source_owner_root=selected_source_root)
        required_l6_names = (
            "intervention_knob_dictionary",
            "lex_intervention_map",
            "observation_to_contract_manifest",
        )
        for name in required_l6_names:
            if not l6_paths[name].is_file() or not l6_paths[name].resolve().is_relative_to(
                selected_source_root
            ):
                raise AssertionError("served_candidate_selected_l6_source_unbound:" + name)
        l6_bundle = profile.context_inputs.intervention_substrate
        if l6_bundle is None or bind_expected_l6_source is None:
            raise AssertionError("served_candidate_selected_l6_bundle_missing")
        selected_l6_witness = bind_expected_l6_source(l6_bundle)
        assert_l6_adapter_installed()
        l6_hashes = selected_l6_witness["file_sha256"]
        data_forge_catalog = l1_path
        selected_l2_sha256 = hashlib.sha256(selected_l2_path.read_bytes()).hexdigest()
        source_root_witness_payload = {
            "source_root": str(selected_source_root),
            "selected_l1_dcat_path": str(l1_path),
            "selected_l1_dcat_sha256": selected_catalog_readback["source_database_sha256"],
            "selected_catalog_readback": selected_catalog_readback,
            "catalog_selection": catalog_selection.model_dump(mode="json"),
            "catalog_source": {
                "repo_root": str(catalog_serving_source.repo_root),
                "snapshot_root": str(catalog_serving_source.snapshot_root),
                "database_path": str(catalog_serving_source.database_path),
                "catalog_run_profile": catalog_serving_source.catalog_run_profile,
                "selection_basis": catalog_serving_source.selection_basis,
            },
            "selected_l2_skg_path": str(selected_l2_path),
            "selected_l2_source_sha256": selected_l2_sha256,
            "selected_l2_version_id": parsed_skg.version_id,
            "selected_l3_lex_path": str(l3_path),
            "selected_l3_row_counts": l3_row_counts,
            "selected_l6_bundle_paths": selected_l6_witness["paths"],
            "selected_l6_path_sha256": l6_hashes,
            "selected_l6_bundle_content_hash": l6_bundle.content_hash,
            "selected_l6_source_witness": selected_l6_witness,
            "selected_data_forge_catalog_path": str(data_forge_catalog),
        }
        source_root_witness_json = json.dumps(
            source_root_witness_payload,
            sort_keys=True,
            separators=(",", ":"),
        )

        original_kref_builder = credal_reference.build_credal_reference
        selected_root_kref_builder = bind_candidate_cycle_kref_builder_root(
            original_kref_builder,
            expected_repo_root=selected_source_root,
            mismatch_code="served_candidate_actual_kref_repo_root_mismatch",
        )

        def observe_served_kref(repo_root, *args, **kwargs):
            read_start = len(l6_source_reads)
            reference = selected_root_kref_builder(repo_root, *args, **kwargs)
            assert_l6_adapter_installed()
            actual_witness = candidate_cycle_kref_source_witness(
                reference,
                source_root=selected_source_root,
                expected_skg_ref=wmr_source,
                catalog_source=catalog_serving_source,
                expected_catalog_readback=selected_catalog_readback,
                expected_l6_bundle=l6_bundle,
                expected_l6_witness=selected_l6_witness,
                actual_l6_reads=l6_source_reads[read_start:],
            )
            actual_witness["actual_build_repo_root"] = str(Path(repo_root).resolve(strict=True))
            actual_kref_witnesses.append(actual_witness)
            return reference

        monkeypatch.setattr(
            credal_reference,
            "build_credal_reference",
            observe_served_kref,
        )
        monkeypatch.setattr(
            design_generation,
            "build_credal_reference",
            observe_served_kref,
        )

    def source_root_witness_json_for_return():
        if selected_source_root is None:
            return None
        if not actual_kref_witnesses:
            raise AssertionError("served_candidate_actual_kref_readback_missing")
        payload = json.loads(source_root_witness_json)
        payload["actual_kref_reads"] = actual_kref_witnesses
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    candidate_profiles.append(profile)
    candidate_model_declarations.append(model_declaration)

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems = []

    async def run_real_compiler(**kwargs):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        problem = await original_compiler(**kwargs)
        compiled_problems.append(problem)
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        nl_pipeline_service, "build_design_problem_from_nl_request", run_real_compiler
    )

    from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError

    with pytest.raises(DesignProblemAuthorityError) as mismatched_request:
        asyncio.run(
            original_compiler(
                nl_request=legacy_industrial_request,
                context={"requested_authority_level": "research"},
                model_name=served_n4_model_id,
                span_support_client=_DeterministicSpanSupportClient(),
            )
        )
    assert mismatched_request.value.code == "design_problem_admissibility_unverified"
    assert "fiscal_request_scope:source_span_unbound:request_text" in str(mismatched_request.value)
    assert cycle_job_profile_selection_ref(recorded_problem) == profile.profile_selection_ref

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
            update={
                "mandate_owner_ref": identities["owner"],
                "action_envelopes": (envelope,),
            }
        )
        context = {
            "control": control,
            "tenant_id": TENANT,
            "cell_id": CELL,
            "run_id": run_id,
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
            "run_id": run_id,
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
            run_id=run_id,
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
            f"/api/v1/runs/{run_id}/human-decisions",
            body,
            route="/api/v1/runs/{run_id}/human-decisions",
            subject="human-reviewer-1",
            extra_headers={"X-PolicyOS-Human-Decision-Exposure": gate.exposure_session_ref},
        )
        assert response.status_code == 201, response.text
        return source, response.json()["record_ref"]

    b09_evidence: dict[str, object] | None = None
    path = None
    try:
        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            if selected_source_root is not None:
                assert control._repo_root == selected_source_root
            assert control._cycle_substrate_context_admission_owner is not None
            assert control._cycle_substrate_context_admission_owner.store is control._artifact_store
            launch_response = client.post(
                "/api/v1/control/runs/nl",
                json={
                    "request": fiscal_nl_request,
                    "llm_model": served_n4_model_id,
                    "context": {
                        "evaluation_safety_attempt": _valid_intake_for_mode(
                            "simulate_only"
                        ).model_dump(mode="json")
                    },
                    "execution_profile": "dev",
                },
                headers={
                    **(
                        {
                            "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                            "X-Tenant-ID": TENANT,
                            "Content-Type": "application/json",
                        }
                    ),
                    "Idempotency-Key": "test-r216-192b38ae25f6425ebe45b42d7f7539e1",
                },
            )
            assert launch_response.status_code == 200, launch_response.text
            launch = launch_response.json()
            assert launch["status"] == "accepted", launch
            run_id = str(launch["run_id"])
            seed_job_id = str(launch["job_id"])
            assert (
                dispatch_one_control_job(
                    store=control._control_store,
                    handler=control._process_control_job,
                    expected_job_id=seed_job_id,
                )
                == seed_job_id
            )
            job = control._control_store.get_job(seed_job_id)
            assert job is not None and job.state == "completed"
            assert compiled_problems
            for compiled in compiled_problems:
                assert compiled.nl_provenance.raw_request == fiscal_nl_request
                assert compiled.nl_provenance.source_surface == "runtime.control.nl_request"
                assert compiled.domain == "fiscal"
                assert compiled.jurisdiction_time.region == "UKR"
                assert compiled.jurisdiction_time.valid_time == "2024"
                assert compiled.jurisdiction_time.as_of == "2024-12-31"
                assert compiled.jurisdiction_time.policy_time == "2024"
                assert compiled.jurisdiction_time.data_time == "2024"
                assert compiled.objectives[0].metric_id == "tax_rate"
                assert compiled.outcome_of_interest.target_variable == "global.tax_rate"
                assert compiled.outcome_of_interest.metric_id == "tax_rate"
                assert compiled.candidate_lever_space.allowed_operator_kinds == [
                    "budget_allocation_multiplier"
                ]
                assert compiled.candidate_lever_space.candidate_levers[0].target_slot == (
                    "government.balance"
                )
                constraint_sources = {
                    constraint.constraint_id: constraint.source_text
                    for constraint in compiled.constraints
                }
                assert constraint_sources["fiscal_request_scope"] == fiscal_scope_source
                assert constraint_sources["no_authority_without_a"] == candidate_only_source
                assert cycle_job_profile_selection_ref(compiled) == profile.profile_selection_ref
            persisted_job_payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            assert persisted_job_payload["llm_models"] == [served_n4_model_id]
            closure, request = _within_fixture_owner(
                resolve_completed_wdi_route,
                control,
                run_id=run_id,
                tenant_id=TENANT,
                cell_id=CELL,
            )
            store = control._artifact_store
            seed_simulation = closure.source_cycle.simulation
            assert seed_simulation.status == "joint_simulated"
            assert seed_simulation.candidate_simulation_n4_source_ref is not None
            assert seed_simulation.candidate_simulation_context_job_ref is not None
            assert seed_simulation.candidate_simulation_n5_input_ref is not None
            assert seed_simulation.candidate_simulation_profile_selection_ref == (
                profile.profile_selection_ref
            )
            n5_input_ref = seed_simulation.candidate_simulation_n5_input_ref
            n5_input = CandidateSimulationN5InputV5.model_validate(
                canon.from_canonical_bytes(_within_fixture_owner(store.get_bytes, n5_input_ref))
            )
            seed_source = _within_fixture_owner(
                GenerationSourceRepository(store).load_candidate_scenario_source_for_n5,
                n5_input.n4_source_ref,
                expected_run_id=run_id,
                expected_job_id=seed_job_id,
                expected_tenant_id=TENANT,
                expected_cell_id=CELL,
            )
            assert type(seed_source) is N4CandidateScenarioSourceRecordV3
            assert seed_source.origin_source_ref is None
            assert seed_source.profile_selection_ref == profile.profile_selection_ref
            assert seed_source.stable_subject_ref == closure.design_problem_ref
            assert seed_source.candidate.candidate_id == n5_input.original_candidate_id
            assert n5_input.profile.profile_selection_ref == profile.profile_selection_ref
            seed_n5_input = n5_input
            assert n5_input.context_job_ref == seed_simulation.candidate_simulation_context_job_ref
            assert artifact_ref_identity_key(n5_input.n4_source_ref) == artifact_ref_identity_key(
                seed_simulation.candidate_simulation_n4_source_ref
            )
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
                    run_dir=cas_root / "runs" / run_id,
                    run_id=run_id,
                    tenant_id=TENANT,
                    cell_id=CELL,
                ).finalize()
            path = f"/api/v1/runs/{run_id}/acquisition-routes/{closure.route_id}"
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
                from polisyos.runtime.quality.generation_cycle import (
                    JointSimulationPort,
                )

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
            ) = _capture_semantic_epoch_finalizer_failure(
                lambda: dispatch_one_control_job(
                    store=control._control_store,  # noqa: SLF001
                    handler=control._process_control_job,  # noqa: SLF001
                    expected_job_id=job_id,
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
            route_read_headers = {
                "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                "X-Tenant-ID": TENANT,
            }
            route_collection_path = f"/api/v1/runs/{run_id}/acquisition-routes"
            listed_route = client.get(route_collection_path, headers=route_read_headers)
            assert listed_route.status_code == 200, listed_route.text
            listed_routes = listed_route.json()["routes"]
            assert len(listed_routes) == 1
            assert listed_routes[0]["route_id"] == closure.route_id
            assert listed_routes[0]["qualification_status"] == "activated"
            assert listed_routes[0]["world_growth"] == "admitted_delta"
            detail_route = client.get(path, headers=route_read_headers)
            assert detail_route.status_code == 200, detail_route.text
            assert detail_route.json()["admitted_observation_delta"] == 1

            # A supplied selected epoch ref whose CAS bytes disappear or fail
            # integrity verification must fail closed through both public GETs.
            missing_epoch_blob, _missing_epoch_manifest = control._artifact_store._paths(
                artifacts.ArtifactID.model_validate(
                    growth.activation.overlay_admission_receipt_ref.artifact_id
                )
            )
            missing_epoch_bytes = missing_epoch_blob.read_bytes()
            invalid_epoch_responses = []
            for corrupt_blob in (False, True):
                try:
                    if corrupt_blob:
                        missing_epoch_blob.write_bytes(missing_epoch_bytes + b"\x00")
                    else:
                        missing_epoch_blob.unlink()
                    invalid_epoch_responses.extend(
                        (
                            client.get(route_collection_path, headers=route_read_headers),
                            client.get(path, headers=route_read_headers),
                        )
                    )
                finally:
                    missing_epoch_blob.write_bytes(missing_epoch_bytes)
            assert tuple(response.status_code for response in invalid_epoch_responses) == (
                409,
                409,
                409,
                409,
            )
            assert (
                tuple(response.json()["code"] for response in invalid_epoch_responses)
                == ("acquisition_native_admission_unverified",) * 4
            )
            assert receipt.tenant_id == closure.tenant_id
            assert receipt.cell_id == closure.cell_id
            assert receipt.run_id == closure.run_id
            assert receipt.source_job_id == closure.source_job_id
            reentry_ref = receipt.reentry_receipt_ref
            assert reentry_ref is not None, receipt
            reentry_manifest = _within_fixture_owner(
                control._artifact_store.get_manifest,
                reentry_ref,
            )
            assert reentry_manifest.artifact_schema is not None
            assert reentry_manifest.artifact_schema.name == (
                "polisyos.runtime.AcquisitionOverlayReentryReceipt"
            )
            assert reentry_manifest.artifact_schema.version == "2.0"
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
            _within_fixture_owner(cases[-1].bridge._validate_reentry, closure, growth, reentry)
            assert reentry.schema_version == "policyos.runtime.acquisition_overlay_reentry.v3"
            from polisyos.runtime.quality.generation_cycle import (
                generation_cycle_run_content_hash,
                validate_acquisition_overlay_continuation,
            )

            continued_run = reentry.continued_generation_run
            assert continued_run is not None
            validate_acquisition_overlay_continuation(closure.generation_run, reentry)
            assert reentry.source_generation_run_content_hash == generation_cycle_run_content_hash(
                closure.generation_run
            )
            assert (
                reentry.continued_generation_run_content_hash
                == generation_cycle_run_content_hash(continued_run)
            )
            assert continued_run.cycles[:-1] == closure.generation_run.cycles
            assert continued_run.cycles[-1] == reentry.new_cycle
            assert continued_run.promotion_port.status == "not_promoted"
            assert continued_run.promotion_port.certified_candidate_ids == ()
            assert reentry.source_run_currentness == reentry.continuation_currentness
            assert reentry.source_run_currentness is not None
            assert reentry.source_run_currentness.status == "not_established"
            # Removing the appended cycle while retaining the new_cycle marker is refused.
            removed_occurrence_run = continued_run.model_copy(
                update={"cycles": continued_run.cycles[:-1]}
            )
            removed_occurrence_receipt = reentry.model_copy(
                update={"continued_generation_run": removed_occurrence_run}
            )
            with pytest.raises(
                ValueError, match="acquisition_reentry_continued_run_binding_mismatch"
            ):
                validate_acquisition_overlay_continuation(
                    closure.generation_run, removed_occurrence_receipt
                )
            source_n4_ref = closure.source_cycle.simulation.candidate_simulation_n4_source_ref
            source_n5_ref = closure.source_cycle.simulation.candidate_simulation_n5_input_ref
            assert source_n4_ref is not None and source_n5_ref is not None
            swapped_simulation = reentry.new_cycle.simulation.model_copy(
                update={
                    "candidate_simulation_n4_source_ref": source_n4_ref,
                    "candidate_simulation_n5_input_ref": source_n5_ref,
                }
            )
            swapped_cycle = reentry.new_cycle.model_copy(update={"simulation": swapped_simulation})
            swapped_receipt = reentry.model_copy(update={"new_cycle": swapped_cycle})
            assert swapped_receipt.source_candidate_ref == reentry.source_candidate_ref
            assert (
                swapped_receipt.new_cycle.selected_candidate_ref
                == reentry.new_cycle.selected_candidate_ref
            )
            assert (
                swapped_receipt.source_candidate_ref
                == swapped_receipt.new_cycle.selected_candidate_ref
            )
            with pytest.raises(
                ValueError, match="acquisition_reentry_continued_run_binding_mismatch"
            ):
                validate_acquisition_overlay_continuation(closure.generation_run, swapped_receipt)
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

            source_repository = GenerationSourceRepository(control._artifact_store)
            source_record = _within_fixture_owner(
                source_repository.load_candidate_scenario_source_for_n5,
                n5_input.n4_source_ref,
                expected_run_id=n5_input.run_id,
                expected_job_id=n5_input.job_id,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
            )
            assert type(source_record) is N4CandidateScenarioSourceRecordV3
            origin_source_ref = source_record.origin_source_ref
            assert origin_source_ref is not None
            old_source_record = _within_fixture_owner(
                source_repository.load_candidate_scenario_source_v3,
                origin_source_ref,
                expected_run_id=n5_input.run_id,
                expected_job_id=n5_input.job_id,
                expected_tenant_id=n5_input.tenant_id,
                expected_cell_id=n5_input.cell_id,
            )
            assert type(old_source_record) is N4CandidateScenarioSourceRecordV3
            assert old_source_record.origin_source_ref is None
            old_semantic_identity = candidate_scenario_semantic_identity_hash(
                stable_subject_ref=old_source_record.stable_subject_ref,
                proposal=old_source_record.proposal,
                candidate=old_source_record.candidate,
                profile=old_source_record.profile,
            )
            new_semantic_identity = candidate_scenario_semantic_identity_hash(
                stable_subject_ref=source_record.stable_subject_ref,
                proposal=source_record.proposal,
                candidate=source_record.candidate,
                profile=source_record.profile,
            )
            assert old_semantic_identity == old_source_record.semantic_identity_hash
            assert new_semantic_identity == source_record.semantic_identity_hash
            assert old_source_record.stable_subject_ref == source_record.stable_subject_ref
            assert old_source_record.semantic_identity_hash == source_record.semantic_identity_hash
            assert old_source_record.profile_selection_ref == source_record.profile_selection_ref
            assert old_source_record.candidate.candidate_id == reentry.source_candidate_ref
            assert source_record.candidate.candidate_id == cycle.selected_candidate_ref
            assert old_source_record.candidate.candidate_id == source_record.candidate.candidate_id
            assert (
                old_source_record.candidate_occurrence_hash
                != source_record.candidate_occurrence_hash
            )
            assert (
                old_source_record.world_model_record_hash != source_record.world_model_record_hash
            )

            # Altered subject/profile/model semantics must change the actual candidate identity.
            changed_profile = source_record.profile.model_copy(
                update={"profile_selection_ref": "sha256:" + "f" * 64}
            )
            changed_profile_identity = candidate_scenario_semantic_identity_hash(
                stable_subject_ref=source_record.stable_subject_ref,
                proposal=source_record.proposal,
                candidate=source_record.candidate,
                profile=changed_profile,
            )
            changed_subject_identity = candidate_scenario_semantic_identity_hash(
                stable_subject_ref="sha256:" + "e" * 64,
                proposal=source_record.proposal,
                candidate=source_record.candidate,
                profile=source_record.profile,
            )
            bundle = source_record.proposal.trinity_bundle
            changed_model_spec = bundle.model_spec.model_copy(
                update={"model_id": bundle.model_spec.model_id + "-changed"}
            )
            changed_model_bundle = bundle.model_copy(update={"model_spec": changed_model_spec})
            changed_model_proposal = source_record.proposal.model_copy(
                update={"trinity_bundle": changed_model_bundle}
            )
            changed_model_identity = candidate_scenario_semantic_identity_hash(
                stable_subject_ref=source_record.stable_subject_ref,
                proposal=changed_model_proposal,
                candidate=source_record.candidate,
                profile=source_record.profile,
            )

            def candidate_id_for_identity(value):
                return "candidate_" + value.removeprefix("sha256:")[:16]

            assert candidate_id_for_identity(changed_profile_identity) != (
                source_record.candidate.candidate_id
            )
            assert candidate_id_for_identity(changed_subject_identity) != (
                source_record.candidate.candidate_id
            )
            assert candidate_id_for_identity(changed_model_identity) != (
                source_record.candidate.candidate_id
            )

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
                "candidate_" + source_record.semantic_identity_hash.removeprefix("sha256:")[:16]
            )
            assert (
                candidate_scenario_semantic_identity_hash(
                    stable_subject_ref=source_record.stable_subject_ref,
                    proposal=source_record.proposal,
                    candidate=source_record.candidate,
                    profile=source_record.profile,
                )
                == source_record.semantic_identity_hash
            )
            source_job = control._control_store.get_job(closure.source_job_id)
            assert source_job is not None
            core_run_id = source_job.progress["core_run_id"]
            history_path = f"/api/v1/runs/{core_run_id}"
            unauthenticated_history = client.get(
                history_path,
                headers={"X-Tenant-ID": TENANT},
            )
            assert unauthenticated_history.status_code == 401
            assert unauthenticated_history.json()["code"] == "missing_bearer_token"
            history_headers = {
                "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                "X-Tenant-ID": TENANT,
            }
            history_response = client.get(history_path, headers=history_headers)
            assert history_response.status_code == 200, history_response.text
            candidate_projection = history_response.json()["run"]["candidate_simulation"]
            assert candidate_projection["acquisition_history_limitation_code"] is None
            if include_default_only_compiled_probe:
                # Start from this real served run and exact owner, but supply an
                # older profileless compiled ref through an adapter whose only
                # missing member is that compiled artifact's qualified view.
                from polisyos.runtime.http.routes.runs import _candidate_simulation_projection

                compiled_ref = ArtifactRef.model_validate(candidate_projection["source_ref"])
                profileless = compiled_ref.model_copy(update={"manifest_profile_sha256": None})
                served_rows = candidate_projection["n5_observations"]

                def served_key(row):
                    ref = row.get("simulation_result_ref")
                    return (
                        row["node_ref"],
                        row["design_problem_ref"],
                        row.get("cycle_index"),
                        row.get("candidate_id"),
                        ref["artifact_id"] if ref is not None else None,
                        ref.get("manifest_profile_sha256") if ref is not None else None,
                    )

                expected_rows = {served_key(row): row for row in served_rows}
                assert any(row.get("simulation_result_ref") is not None for row in served_rows), (
                    "served non-generic source must expose an N5 result candidate"
                )
                assert len(expected_rows) == len(served_rows)
                real_store = control._artifact_store

                class DefaultOnlyCompiledOwner:
                    def __init__(self) -> None:
                        self.rejected_selected: list[str] = []

                    def __getattr__(self, name: str):
                        return getattr(real_store, name)

                    def reject_selected(self, selector) -> None:
                        if (
                            getattr(selector, "artifact_id", None) == compiled_ref.artifact_id
                            and getattr(selector, "manifest_profile_sha256", None) is not None
                        ):
                            self.rejected_selected.append("compiled-selected")
                            raise FileNotFoundError("legacy default-only compiled view")

                    def get_raw_manifest_bytes(self, selector, *args, **kwargs):
                        self.reject_selected(selector)
                        return real_store.get_raw_manifest_bytes(selector, *args, **kwargs)

                    def get_bytes(self, selector, *args, **kwargs):
                        self.reject_selected(selector)
                        return real_store.get_bytes(selector, *args, **kwargs)

                legacy_owner = DefaultOnlyCompiledOwner()
                with tenant_scope(None, tenant_id=TENANT, cell_id=CELL):
                    manifest, _ = artifacts.read_core_manifest_profile(legacy_owner, profileless)
                    selected = artifacts.artifact_ref_for_manifest(manifest)
                    if compiled_ref.manifest_profile_sha256 is not None:
                        assert selected == compiled_ref
                    with pytest.raises(FileNotFoundError, match="legacy default-only compiled"):
                        legacy_owner.get_raw_manifest_bytes(selected)
                    legacy_owner.rejected_selected.clear()
                    legacy_projection = _candidate_simulation_projection(
                        run_id=core_run_id,
                        tenant_id=TENANT,
                        cell_id=CELL,
                        control_job_id=source_job.job_id,
                        root_artifacts=(profileless,),
                        store=legacy_owner,
                        control_service=None,
                    )
                assert legacy_projection is not None
                assert legacy_projection.artifact_status == "resolved"
                assert legacy_projection.publication_authority is False
                legacy_rows = legacy_projection.n5_observations
                actual_rows = {
                    (
                        row.node_ref,
                        row.design_problem_ref,
                        row.cycle_index,
                        row.candidate_id,
                        (
                            str(row.simulation_result_ref.artifact_id)
                            if row.simulation_result_ref is not None
                            else None
                        ),
                        (
                            row.simulation_result_ref.manifest_profile_sha256
                            if row.simulation_result_ref is not None
                            else None
                        ),
                    ): row
                    for row in legacy_rows
                }
                assert len(actual_rows) == len(legacy_rows)
                assert set(actual_rows) == set(expected_rows)
                limitation = "compiled_cycle_selected_view_not_established"
                for key, row in actual_rows.items():
                    original = expected_rows[key]
                    assert row.status == original["status"]
                    assert list(row.atom_ids) == original["atom_ids"]
                    assert list(row.selected_outcomes) == original["selected_outcomes"]
                    assert row.simulation_ref == original.get("simulation_ref")
                    evidence = (
                        row.n5_interaction_evidence.model_dump(mode="json")
                        if row.n5_interaction_evidence is not None
                        else None
                    )
                    assert evidence == original.get("n5_interaction_evidence")
                    assert set(row.authority_blockers) == (
                        set(original["authority_blockers"]) | {limitation}
                    )
                    old_n8_status = original.get("n8_status")
                    expected_n8_status = (
                        "value_pending_n8" if old_n8_status == "value_ready" else old_n8_status
                    )
                    assert row.n8_status == expected_n8_status
                    old_n8_blockers = set(original["n8_authority_blockers"])
                    assert set(row.n8_authority_blockers) == (
                        old_n8_blockers | ({limitation} if old_n8_status is not None else set())
                    )
                    assert row.n8_numeric_interaction == original.get("n8_numeric_interaction")
                    assert row.n8_numeric_interaction_basis == original.get(
                        "n8_numeric_interaction_basis"
                    )
                    assert row.n8_interaction_sampling_status == original.get(
                        "n8_interaction_sampling_status"
                    )
                assert not legacy_owner.rejected_selected

            acquisition_history = candidate_projection["acquisition_history"]
            assert len(acquisition_history) == 2
            history_by_generation = {
                entry["action_generation"]: entry for entry in acquisition_history
            }
            assert set(history_by_generation) == {1, 2}
            quarantined_history = history_by_generation[1]
            assert quarantined_history["terminal_outcome"] == "quarantined_no_growth"
            assert quarantined_history["route_receipt_ref"]["artifact_id"] == first_terminal_ref
            assert quarantined_history.get("reentry_receipt_ref") is None
            assert quarantined_history.get("old_candidate_id") is None
            assert quarantined_history.get("new_candidate_id") is None
            assert quarantined_history.get("origin_source_ref") is not None
            assert quarantined_history.get("expected_origin_source_ref") is None
            assert quarantined_history["schema_version"] == (
                "policyos.runtime.run_candidate_simulation_acquisition_history.v2"
            )
            assert quarantined_history["reentry_receipt_schema_version"] is None
            assert quarantined_history["continuation_join_status"] == "not_applicable"
            assert quarantined_history["origin_source_binding_status"] == "observed_only"
            assert quarantined_history.get("continuation") is None

            acquisition_history = history_by_generation[2]
            assert acquisition_history["terminal_outcome"] == "reentry_completed"
            assert (
                acquisition_history["route_receipt_ref"]["artifact_id"]
                == result["terminal_receipt_ref"]
            )
            assert acquisition_history["reentry_receipt_ref"]["artifact_id"] == reentry_ref
            assert acquisition_history["old_candidate_id"] == reentry.source_candidate_ref
            assert acquisition_history["new_candidate_id"] == cycle.selected_candidate_ref
            assert acquisition_history["schema_version"] == (
                "policyos.runtime.run_candidate_simulation_acquisition_history.v2"
            )
            assert acquisition_history["reentry_receipt_schema_version"] == (
                "policyos.runtime.acquisition_overlay_reentry.v3"
            )
            assert acquisition_history["continuation_join_status"] == ("v3_occurrence_joined")
            assert acquisition_history["origin_source_binding_status"] == (
                "verified_same_candidate_root"
            )
            history_source_ref = ArtifactRef.model_validate(
                acquisition_history["new_candidate_source_ref"]
            )
            history_origin_ref = ArtifactRef.model_validate(
                acquisition_history["origin_source_ref"]
            )
            history_expected_origin_ref = ArtifactRef.model_validate(
                acquisition_history["expected_origin_source_ref"]
            )
            assert artifact_ref_identity_key(history_source_ref) == artifact_ref_identity_key(
                n5_input.n4_source_ref
            )
            assert artifact_ref_identity_key(history_origin_ref) == artifact_ref_identity_key(
                origin_source_ref
            )
            assert artifact_ref_identity_key(history_expected_origin_ref) == (
                artifact_ref_identity_key(origin_source_ref)
            )
            assert (
                acquisition_history["old_candidate_id"] == acquisition_history["new_candidate_id"]
            )
            assert acquisition_history["currentness_status"] == "not_established"
            assert acquisition_history["authority_purpose"] == "candidate_observation_only"
            assert acquisition_history["publication_authority"] is False
            continuation = acquisition_history["continuation"]
            assert (
                continuation["source_generation_run_content_hash"]
                == reentry.source_generation_run_content_hash
            )
            assert (
                continuation["continued_generation_run_content_hash"]
                == reentry.continued_generation_run_content_hash
            )
            assert continuation["source_cycle_index"] == reentry.source_cycle_index
            assert continuation["continued_cycle_index"] == cycle.cycle_index
            continuation_selected_n4_ref = ArtifactRef.model_validate(
                continuation["selected_n4_source_ref"]
            )
            assert artifact_ref_identity_key(history_source_ref) == (
                artifact_ref_identity_key(continuation_selected_n4_ref)
            )
            assert continuation["selected_n5_input_ref"]["artifact_id"] == str(
                n5_input_ref.artifact_id
            )
            assert continuation["previous_n4_source_ref"]["artifact_id"] == str(
                closure.source_cycle.simulation.candidate_simulation_n4_source_ref.artifact_id
            )
            assert continuation["previous_n5_input_ref"]["artifact_id"] == str(
                closure.source_cycle.simulation.candidate_simulation_n5_input_ref.artifact_id
            )
            assert continuation["previous_profile_selection_ref"] == (
                seed_n5_input.profile.profile_selection_ref
            )
            assert (
                continuation["previous_profile_content_hash"] == seed_n5_input.profile.content_hash
            )
            assert continuation["selected_profile_selection_ref"] == (
                n5_input.profile.profile_selection_ref
            )
            assert continuation["selected_profile_content_hash"] == n5_input.profile.content_hash
            assert (
                continuation["previous_profile_selection_ref"]
                == (continuation["selected_profile_selection_ref"])
            )
            assert continuation["selected_target_world_slot"] == "government.balance"
            assert continuation["previous_selected_target_baseline_hash"] is not None
            assert continuation["selected_target_baseline_hash"] is not None
            assert (
                continuation["previous_selected_target_baseline_hash"]
                != (continuation["selected_target_baseline_hash"])
            )
            assert continuation["n9_status"] == continued_run.promotion_port.status
            assert continuation["n9_reason"] == continued_run.promotion_port.reason
            assert continuation["n9_certified_candidate_ids"] == []
            assert continuation["continuation_currentness_status"] == "not_established"
            assert continuation["currentness_status"] == "not_established"
            assert continuation["authority_purpose"] == "candidate_observation_only"
            assert continuation["publication_authority"] is False
            current_occurrence = next(
                row
                for row in continuation["current_candidate_occurrences"]
                if row["candidate_id"] == cycle.selected_candidate_ref
            )
            assert current_occurrence["cycle_index"] == cycle.cycle_index
            assert current_occurrence["content_hash"] == next(
                row.content_hash
                for row in continued_run.candidate_summaries
                if row.candidate_id == cycle.selected_candidate_ref
                and row.cycle_index == cycle.cycle_index
            )
            projected_fronts = continuation["current_fronts"]
            assert (
                cycle.selected_candidate_ref
                in projected_fronts[current_occurrence["front"] + "_candidate_ids"]
            )

            # Fresh route resolution consumes the persisted owner-verified v3
            # continuation. The route/cost identity stays anchored to the
            # immutable compiled route while the selected N4 source advances.
            action_service = client.app.state.runtime_container.acquisition_action_service
            assert action_service is not None
            fresh_closure = action_service._resolve(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=run_id,
            )
            assert reentry.continued_generation_run is not None
            assert fresh_closure.generation_run == reentry.continued_generation_run
            assert fresh_closure.source_cycle == cycle
            assert fresh_closure.route_source_cycle == closure.source_cycle
            assert fresh_closure.route_id == closure.route_id
            assert fresh_closure.source_cycle.cycle_index == cycle.cycle_index
            # Replaying the same growth receipt still resolves its existing
            # pointer; this is distinct from advancing to a new growth ref.
            replayed_reentry_ref = _within_fixture_owner(
                cases[-1].bridge.resume,
                closure,
                (growth_refs[0],),
            )
            assert replayed_reentry_ref == reentry_ref
            # This fixture has no independently admitted second observation.
            # The latest source is selected, but absence of a new growth owner
            # remains a typed refusal rather than replaying the prior receipt.
            with pytest.raises(ValueError, match="acquisition_live_evidence_not_admitted"):
                _within_fixture_owner(cases[-1].bridge.resume, fresh_closure, ())

            if stop_after_fresh_get:
                return {
                    "run_id": core_run_id,
                    "candidate_id": cycle.selected_candidate_ref,
                    **(
                        {"source_root_witness_json": source_root_witness_json_for_return()}
                        if source_root_witness_json is not None
                        else {}
                    ),
                }
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
            assert (
                input_ref_from_artifact_ref(
                    source_record.source_ref,
                    role="n4_source_v2",
                )
                in n4_manifest.inputs
            )
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
            assert type(context_job.problem.outcome_of_interest) is (_QualifiedOutcomeOfInterestV3)
            assert context_job.problem == source_record.problem
            assert context_job.design_problem_ref == source_record.cycle_problem_ref
            assert artifact_ref_identity_key(n5_input.context_job_ref) == (
                artifact_ref_identity_key(source_record.context_job_ref)
            )
            assert context_job_manifest.kind == ("runtime.quality.cycle_substrate_context_job")
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
                candidate_ncm_spec_from_declaration(source_v2.model_declaration).model_dump(
                    mode="json"
                )
            )
            assert artifact_ref_identity_key(source_record.ncm_ref) == selected_ncm_identity
            assert artifact_ref_identity_key(n5_input.materialization.ncm_ref) == (
                selected_ncm_identity
            )
            context_world = context_job.context.world_model_record
            assert source_record.world_model_record_hash == context_world.content_hash
            assert n5_input.materialization.world_model_record_hash == (context_world.content_hash)
            acquired_world = n5_input.profile.context_inputs.world_model_record
            assert acquired_world.authority_status == "limited"
            assert context_world.authority_status == acquired_world.authority_status
            assert context_world.limitations == acquired_world.limitations
            assert context_world.simulation_model_ref.calibrated is False
            assert context_world.simulation_model_ref.calibration_ref is None
            assert (
                context_world.simulation_model_ref.fidelity_level == "declared_candidate_scenario"
            )
            assert any(
                item.get("declaration_content_hash") == source_v2.model_declaration.content_hash
                and item.get("status") == "candidate_only_not_empirically_grounded"
                for item in context_world.simulation_model_ref.assumptions
            )

            registry_admission_owner = cases[-1].bridge.cycle_substrate_context_admission_owner
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
            expected_context_world_views = world_model_artifact_views(expected_context_world)
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
            context_data_snapshot_ref = world_model_artifact_views(context_world).data_snapshot_ref
            data_snapshot_ref = world_model_artifact_views(acquired_world).data_snapshot_ref
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
            data_snapshot_ref = world_model_artifact_views(acquired_world).data_snapshot_ref
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
            assert (
                input_ref_from_artifact_ref(
                    data_snapshot_ref,
                    role="input.data_snapshot_ref",
                )
                in bound_state_snapshot.lineage_inputs
            )
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
            assert (
                declaration.target_baseline
                == expected_profile_baseline[declaration.target_world_slot]
            )
            assert (
                declaration.outcome_baseline
                == expected_profile_baseline[declaration.outcome_variable]
            )

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
            joint_atom_ids = (n5_input.materialization.derived_n5_atom.intervention_id,)
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
            unselected_baseline = dict(seed_n5_input.profile.n5.baseline_state)
            target_slot = seed_n5_input.materialization.target_world_slot
            unselected_slot = target_slot + ".unselected-control"
            unselected_baseline[unselected_slot] = 1.0
            unselected_profile = seed_n5_input.profile.model_copy(
                update={
                    "n5": seed_n5_input.profile.n5.model_copy(
                        update={"baseline_state": unselected_baseline}
                    )
                }
            )
            unselected_only_input = seed_n5_input.model_copy(update={"profile": unselected_profile})
            from polisyos.runtime.http.routes.runs import (
                _selected_target_baseline_hashes,
            )

            assert _selected_target_baseline_hashes(seed_n5_input, unselected_only_input) is None
            id_time_only_input = seed_n5_input.model_copy(
                update={
                    "run_id": seed_n5_input.run_id + "-later",
                    "job_id": seed_n5_input.job_id + "-later",
                }
            )
            assert _selected_target_baseline_hashes(seed_n5_input, id_time_only_input) is None

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
                * (n5_input.materialization.value - source_v2.model_declaration.target_baseline)
            )
            unacquired_value_outcome = (
                model_declaration.outcome_baseline
                + model_declaration.outcome_per_target_unit
                * (n5_input.materialization.value - model_declaration.target_baseline)
            )
            assert computed_outcome == pytest.approx(acquired_value_outcome, abs=1e-9)
            assert computed_outcome != pytest.approx(unacquired_value_outcome, abs=1e-9)

            candidate_projection_before_noop = {
                key: value
                for key, value in candidate_projection.items()
                if key
                not in {
                    "acquisition_history",
                    "acquisition_history_limitation_code",
                }
            }
            prior_growth_ref = growth_refs[0]

        # A fresh action with only request identity/time changed must reuse the
        # already admitted owner evidence and record a measured zero-delta result.
        third_request = request.model_copy(
            update={"idempotency_key": "served-acquisition-same-candidate-no-op"}
        )
        with TestClient(app()) as client:
            control = client.app.state.runtime_container.control_service
            response, third_resource_digest = trust.post(
                client,
                path + "/decision-request",
                third_request.model_dump(mode="json"),
                route=route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            third_slot, third_job_id = appoint_mandate(
                control, third_request, third_resource_digest
            )
            assert third_job_id not in {first_job_id, job_id}
            trust.raw["acquisition_authority"]["mandates"].append(third_slot)
            slot = third_slot

        with TestClient(app()) as client:
            third_source, third_human_ref = approve_request(
                client, third_request, third_resource_digest
            )
            slot["human_decision_record_ref"] = third_human_ref

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            response, _ = trust.post(
                client,
                path + "/execute",
                third_request.model_dump(mode="json"),
                route=route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            action_job = control._control_store.get_job(third_job_id)
            assert action_job is not None
            action_payload = canon.from_canonical_bytes(
                _within_fixture_owner(control._artifact_store.get_bytes, action_job.payload_ref)
            )
            action_service = container.acquisition_action_service
            assert action_service is not None
            third_closure = action_service._resolve(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=run_id,
            )
            action_generation = action_service._action_generation(third_closure, third_job_id)
            requested_phase = action_service._phase_receipt(
                action_generation=action_generation,
                closure=third_closure,
                job_id=third_job_id,
                decision_ref=str(action_payload["decision_ref"]),
                receipt_phase="requested",
                predecessor_receipt_ref=None,
                owner_receipt_refs=(),
            )
            action_sink = control.acquisition_route_sink
            requested_head = action_sink.get_head(requested_phase)
            assert requested_head is not None
            assert requested_head.receipt_phase == "requested"
            executing_phase = action_service._phase_receipt(
                action_generation=action_generation,
                closure=third_closure,
                job_id=third_job_id,
                decision_ref=str(action_payload["decision_ref"]),
                receipt_phase="executing",
                predecessor_receipt_ref=requested_head.receipt_ref,
                owner_receipt_refs=(),
            )
            executing_head = action_sink.persist_phase(executing_phase)
            bridge = cases[-1].bridge
            with pytest.raises(ValueError, match="acquisition_action_phase_head_binding_mismatch"):
                bridge.begin_action(third_closure, requested_head.receipt_ref)
            selected_route = bridge.selection(third_closure)
            assert selected_route is not None
            selected_pointer = bridge._growth_pointer(selected_route, create=False)
            previous_kind, previous_ref = bridge._read_outcome_pointer(selected_pointer)
            assert previous_kind == "runtime_quality.acquisition_world_growth_receipt"
            assert previous_ref == prior_growth_ref
            with pytest.raises(ValueError, match="acquisition_owner_outcome_not_established"):
                bridge.recover_admission(third_closure, executing_head.receipt_ref)
            assert bridge._read_outcome_pointer(selected_pointer) == (
                "runtime_quality.acquisition_world_growth_receipt",
                prior_growth_ref,
            )
            bridge.begin_action(third_closure, executing_head.receipt_ref)

            # Crash after the immutable current-action no-growth CAS is prepared,
            # but before its route pointer replaces the previous positive receipt.
            original_write_pointer = bridge._write_pointer

            def crash_before_route_pointer(pointer, receipt_ref, *, receipt_kind=None):
                if receipt_kind == "runtime_quality.acquisition_world_growth_no_growth_receipt":
                    raise OSError("simulated_loss_before_route_pointer_replace")
                return original_write_pointer(pointer, receipt_ref, receipt_kind=receipt_kind)

            monkeypatch.setattr(bridge, "_write_pointer", crash_before_route_pointer)
            with pytest.raises(OSError, match="simulated_loss_before_route_pointer_replace"):
                bridge.record_measured_no_growth(
                    third_closure, action_phase_ref=executing_head.receipt_ref
                )
            monkeypatch.setattr(bridge, "_write_pointer", original_write_pointer)
            still_positive_kind, still_positive_ref = bridge._read_outcome_pointer(selected_pointer)
            assert (still_positive_kind, still_positive_ref) == (
                "runtime_quality.acquisition_world_growth_receipt",
                prior_growth_ref,
            )
            selector_path, prepared_selector = bridge._read_action_selector(
                third_closure, selected_route, executing_head.receipt_ref
            )
            assert selector_path.exists()
            assert prepared_selector.state == "prepared"
            assert prepared_selector.receipt_kind == (
                "runtime_quality.acquisition_world_growth_no_growth_receipt"
            )
            assert prepared_selector.receipt_ref is not None
            assert not cases[-1].transport_calls

            # The latest action is prepared, but the route pointer still names the old positive.
            # Both public readers must report an unresolved current outcome, not that old delta.
            route_read_headers = {
                "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
                "X-Tenant-ID": TENANT,
            }
            route_collection_path = f"/api/v1/runs/{run_id}/acquisition-routes"
            stale_pointer_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in stale_pointer_reads), [
                response.text for response in stale_pointer_reads
            ]
            assert stale_pointer_reads[0].json()["routes"][0]["world_growth"] == ("not_established")
            assert stale_pointer_reads[0].json()["routes"][0]["admitted_observation_delta"] is None
            assert stale_pointer_reads[1].json()["world_growth"] == "not_established"
            assert stale_pointer_reads[1].json()["admitted_observation_delta"] is None
            assert bridge._has_verified_admission_basis(third_closure)

            # Recovery can replace the route pointer before it marks the selector selected.
            # That mixed state is still not a current outcome for either public reader.
            original_select_action_outcome = bridge._select_action_outcome

            def crash_after_route_pointer(*args, **kwargs):
                raise OSError("simulated_loss_before_action_selector_select")

            monkeypatch.setattr(bridge, "_select_action_outcome", crash_after_route_pointer)
            with pytest.raises(OSError, match="simulated_loss_before_action_selector_select"):
                bridge.recover_admission(third_closure, executing_head.receipt_ref)
            monkeypatch.setattr(bridge, "_select_action_outcome", original_select_action_outcome)
            assert bridge._read_outcome_pointer(selected_pointer) == (
                "runtime_quality.acquisition_world_growth_no_growth_receipt",
                prepared_selector.receipt_ref,
            )
            _prepared_path, pointer_prepared_selector = bridge._read_action_selector(
                third_closure, selected_route, executing_head.receipt_ref
            )
            assert pointer_prepared_selector.state == "prepared"
            pointer_replaced_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in pointer_replaced_reads), [
                response.text for response in pointer_replaced_reads
            ]
            assert pointer_replaced_reads[0].json()["routes"][0]["world_growth"] == (
                "not_established"
            )
            assert pointer_replaced_reads[1].json()["world_growth"] == "not_established"

            # A state-only selector rewrite has the same route, executing phase,
            # and owner CAS but no durable producer transition.
            selector_bytes_before_forgery = selector_path.read_bytes()
            selector_before_forgery = json.loads(selector_bytes_before_forgery)
            assert selector_before_forgery["state"] == "prepared"
            state_only_forgery = dict(selector_before_forgery)
            state_only_forgery["state"] = "selected"
            assert {key: value for key, value in state_only_forgery.items() if key != "state"} == {
                key: value for key, value in selector_before_forgery.items() if key != "state"
            }
            try:
                selector_path.write_text(json.dumps(state_only_forgery, sort_keys=True) + "\n")
                state_only_forgery_reads = (
                    client.get(route_collection_path, headers=route_read_headers),
                    client.get(path, headers=route_read_headers),
                )
            finally:
                selector_path.write_bytes(selector_bytes_before_forgery)
            assert all(response.status_code == 200 for response in state_only_forgery_reads), [
                response.text for response in state_only_forgery_reads
            ]
            assert state_only_forgery_reads[0].json()["routes"][0]["world_growth"] == (
                "not_established"
            )
            assert state_only_forgery_reads[1].json()["world_growth"] == "not_established"
            assert (
                state_only_forgery_reads[0].json()["routes"][0]["admitted_observation_delta"]
                is None
            )
            assert state_only_forgery_reads[1].json()["admitted_observation_delta"] is None
            assert bridge._has_verified_admission_basis(third_closure)

            # Independent adapters and overlapping readers use the same durable head and owner lock.
            from concurrent.futures import ThreadPoolExecutor

            with TestClient(app()) as reopened_client:
                reopened_reads = (
                    reopened_client.get(route_collection_path, headers=route_read_headers),
                    reopened_client.get(path, headers=route_read_headers),
                )
                assert all(response.status_code == 200 for response in reopened_reads), [
                    response.text for response in reopened_reads
                ]
                assert reopened_reads[0].json()["routes"][0]["world_growth"] == ("not_established")
                assert reopened_reads[1].json()["world_growth"] == "not_established"

            with ThreadPoolExecutor(max_workers=2) as readers:
                concurrent_reads = tuple(
                    readers.map(
                        lambda route_path: client.get(route_path, headers=route_read_headers),
                        (route_collection_path, path),
                    )
                )
            assert all(response.status_code == 200 for response in concurrent_reads), [
                response.text for response in concurrent_reads
            ]
            assert concurrent_reads[0].json()["routes"][0]["world_growth"] == ("not_established")
            assert concurrent_reads[1].json()["world_growth"] == "not_established"

            # The producer commits selection through the existing ActionHead and event
            # chain. A durable event without its ActionHead transition remains unknown.
            recovered_current = bridge.recover_admission(third_closure, executing_head.receipt_ref)
            with monkeypatch.context() as selection_crash:

                def fail_action_head_advance(**_kwargs):
                    raise OSError("simulated_loss_after_selection_event")

                selection_crash.setattr(
                    action_sink._control_store,  # noqa: SLF001
                    "advance_acquisition_action_head",
                    fail_action_head_advance,
                )
                with pytest.raises(OSError, match="simulated_loss_after_selection_event"):
                    action_sink.persist_action_outcome_selection(
                        executing_head.receipt_ref, recovered_current.owner_receipt_refs
                    )
            orphan_selection_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in orphan_selection_reads), [
                response.text for response in orphan_selection_reads
            ]
            assert orphan_selection_reads[0].json()["routes"][0]["world_growth"] == (
                "not_established"
            )
            assert orphan_selection_reads[1].json()["world_growth"] == "not_established"
            assert (
                orphan_selection_reads[0].json()["routes"][0]["admitted_observation_delta"] is None
            )
            assert orphan_selection_reads[1].json()["admitted_observation_delta"] is None

            # Reopen the exact event-before-head gap from the existing owner event.
            selected_head = action_sink.persist_action_outcome_selection(
                executing_head.receipt_ref, recovered_current.owner_receipt_refs
            )
            assert selected_head.receipt_phase == "outcome_selected"
            assert selected_head.predecessor_receipt_ref == executing_head.receipt_ref
            selected_snapshot = action_sink.current_action_outcome(
                tenant_id=third_closure.tenant_id,
                cell_id=third_closure.cell_id,
                run_id=third_closure.run_id,
                source_job_id=third_closure.source_job_id,
                route_id=third_closure.route_id,
            )
            assert selected_snapshot is not None
            assert selected_snapshot.head == selected_head
            assert selected_snapshot.executing_phase_ref == executing_head.receipt_ref
            assert selected_snapshot.selection_phase_ref == selected_head.receipt_ref
            selection_phase = selected_snapshot.selection_phase
            assert selection_phase is not None
            assert selection_phase.schema_version == "AcquisitionRoutePhaseReceipt@1.1"
            assert selection_phase.receipt_phase == "outcome_selected"
            assert selection_phase.predecessor_receipt_ref == executing_head.receipt_ref
            assert selection_phase.owner_receipt_refs == (prepared_selector.receipt_ref,)
            selection_events = action_sink._event_log.list_events(  # noqa: SLF001
                event_id=selected_head.durable_event_id,
                run_id=third_closure.run_id,
                job_id=third_job_id,
                limit=100,
            )
            assert len(selection_events) == 1
            selection_event = selection_events[0].event
            assert selection_event.payload_ref == selected_head.receipt_ref
            assert selection_event.input_refs == tuple(
                sorted((executing_head.receipt_ref, prepared_selector.receipt_ref))
            )
            assert selection_event.state_before == "executing"
            assert selection_event.state_after == "outcome_selected"
            with TestClient(app()) as selected_reopen:
                selected_reopened_reads = (
                    selected_reopen.get(route_collection_path, headers=route_read_headers),
                    selected_reopen.get(path, headers=route_read_headers),
                )
                assert all(response.status_code == 200 for response in selected_reopened_reads), [
                    response.text for response in selected_reopened_reads
                ]
                assert selected_reopened_reads[0].json()["routes"][0]["world_growth"] == (
                    "no_growth"
                )
                assert selected_reopened_reads[1].json()["world_growth"] == "no_growth"

            # A current selected receipt is safe to project before its action head becomes terminal.
            selected_before_terminal_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(
                response.status_code == 200 for response in selected_before_terminal_reads
            ), [response.text for response in selected_before_terminal_reads]
            assert selected_before_terminal_reads[0].json()["routes"][0]["world_growth"] == (
                "no_growth"
            )
            assert (
                selected_before_terminal_reads[0].json()["routes"][0]["admitted_observation_delta"]
                == 0
            )
            assert selected_before_terminal_reads[1].json()["world_growth"] == "no_growth"
            assert selected_before_terminal_reads[1].json()["admitted_observation_delta"] == 0

            # Keep the selected route pointer and selector intact while the current-head
            # reader observes no ActionHead. Neither public projection may promote that
            # historical pointer into a current outcome.
            selected_pointer_value = bridge._read_outcome_pointer(selected_pointer)
            selected_selector_value = json.loads(selector_path.read_text())
            original_list_action_heads = control._control_store.list_acquisition_action_heads

            def hide_current_action_head(**scope):
                if (
                    scope.get("tenant_id") == third_closure.tenant_id
                    and scope.get("cell_id") == third_closure.cell_id
                    and scope.get("run_id") == third_closure.run_id
                    and scope.get("source_job_id") == third_closure.source_job_id
                    and scope.get("route_id") == selected_route.route_id
                ):
                    return ()
                return original_list_action_heads(**scope)

            with monkeypatch.context() as no_current_head:
                no_current_head.setattr(
                    control._control_store,
                    "list_acquisition_action_heads",
                    hide_current_action_head,
                )
                no_head_reads = (
                    client.get(route_collection_path, headers=route_read_headers),
                    client.get(path, headers=route_read_headers),
                )
            assert all(response.status_code == 200 for response in no_head_reads), [
                response.text for response in no_head_reads
            ]
            assert no_head_reads[0].json()["routes"][0]["world_growth"] == ("not_established")
            assert no_head_reads[0].json()["routes"][0]["admitted_observation_delta"] is None
            assert no_head_reads[1].json()["world_growth"] == "not_established"
            assert no_head_reads[1].json()["admitted_observation_delta"] is None
            assert bridge._read_outcome_pointer(selected_pointer) == selected_pointer_value
            assert json.loads(selector_path.read_text()) == selected_selector_value

            # A valid legacy receipt without ActionHead linkage remains historical evidence.
            _legacy_no_growth, legacy_growth, _legacy_admitted = bridge._verified_no_growth(
                third_closure, selected_pointer_value[1]
            )
            legacy_growth = legacy_growth.model_copy(update={"action_phase_ref": None})
            assert legacy_growth.action_phase_ref is None
            try:
                bridge.persist_growth(third_closure, legacy_growth)
                with monkeypatch.context() as no_legacy_current_head:
                    no_legacy_current_head.setattr(
                        control._control_store,
                        "list_acquisition_action_heads",
                        hide_current_action_head,
                    )
                    legacy_no_head_reads = (
                        client.get(route_collection_path, headers=route_read_headers),
                        client.get(path, headers=route_read_headers),
                    )
                    assert bridge.project_growth(third_closure) is None
            finally:
                bridge._write_pointer(
                    selected_pointer,
                    selected_pointer_value[1],
                    receipt_kind=selected_pointer_value[0],
                )
            assert all(response.status_code == 200 for response in legacy_no_head_reads), [
                response.text for response in legacy_no_head_reads
            ]
            assert legacy_no_head_reads[0].json()["routes"][0]["world_growth"] == (
                "not_established"
            )
            assert legacy_no_head_reads[0].json()["routes"][0]["admitted_observation_delta"] is None
            assert legacy_no_head_reads[1].json()["world_growth"] == "not_established"
            assert legacy_no_head_reads[1].json()["admitted_observation_delta"] is None
            assert bridge._read_outcome_pointer(selected_pointer) == selected_pointer_value

            selected_selector_bytes = selector_path.read_bytes()
            selector_path.unlink()
            removed_selector_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in removed_selector_reads), [
                response.text for response in removed_selector_reads
            ]
            assert removed_selector_reads[0].json()["routes"][0]["world_growth"] == "no_growth"
            assert removed_selector_reads[0].json()["routes"][0]["admitted_observation_delta"] == 0
            assert removed_selector_reads[1].json()["world_growth"] == "no_growth"
            assert removed_selector_reads[1].json()["admitted_observation_delta"] == 0
            selector_path.write_bytes(selected_selector_bytes)

            tampered_selector = json.loads(selected_selector_bytes)
            tampered_selector["receipt_ref"] = "sha256:" + "f" * 64
            selector_path.write_text(json.dumps(tampered_selector, sort_keys=True) + "\n")
            tampered_selector_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in tampered_selector_reads), [
                response.text for response in tampered_selector_reads
            ]
            assert tampered_selector_reads[0].json()["routes"][0]["world_growth"] == "no_growth"
            assert tampered_selector_reads[0].json()["routes"][0]["admitted_observation_delta"] == 0
            assert tampered_selector_reads[1].json()["world_growth"] == "no_growth"
            assert tampered_selector_reads[1].json()["admitted_observation_delta"] == 0
            selector_path.write_bytes(selected_selector_bytes)

            third_decision = authority.AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(
                    _within_fixture_owner(
                        control._artifact_store.get_bytes,
                        action_payload["decision_ref"],
                    )
                )
            )
            assert third_decision.outcome == "allowed"
            assert third_decision.human_decision_record_ref == third_human_ref
            assert third_decision.permission_snapshot == third_source.permission_snapshot
            assert not cases[-1].transport_calls

        with TestClient(app()) as client:
            container = client.app.state.runtime_container
            control = container.control_service
            dispatch_one_control_job(
                store=control._control_store,  # noqa: SLF001
                handler=control._process_control_job,  # noqa: SLF001
                expected_job_id=third_job_id,
            )
            completed_job = control._control_store.get_job(third_job_id)
            assert completed_job is not None and completed_job.state == "completed"
            third_progress = completed_job.progress
            assert third_progress["receipt_phase"] == "terminal"
            third_terminal_ref = third_progress["terminal_receipt_ref"]
            third_terminal = _read_owned_terminal(control._artifact_store, third_terminal_ref)
            assert third_terminal.action_generation == 3
            assert third_terminal.predecessor_receipt_ref == selected_head.receipt_ref
            assert third_terminal.terminal_outcome == "quarantined_no_growth"
            assert third_terminal.reentry_receipt_ref is None
            assert not cases[-1].transport_calls
            terminal_reads = (
                client.get(route_collection_path, headers=route_read_headers),
                client.get(path, headers=route_read_headers),
            )
            assert all(response.status_code == 200 for response in terminal_reads), [
                response.text for response in terminal_reads
            ]
            assert terminal_reads[0].json()["routes"][0]["world_growth"] == "no_growth"
            assert terminal_reads[0].json()["routes"][0]["admitted_observation_delta"] == 0
            assert terminal_reads[1].json()["world_growth"] == "no_growth"
            assert terminal_reads[1].json()["admitted_observation_delta"] == 0

            from polisyos.runtime.quality.acquisition_world_growth import (
                AcquisitionWorldGrowthAttempt,
                AcquisitionWorldGrowthNoGrowthReceipt,
                admitted_membership_delta,
            )

            no_growth_refs = tuple(
                ref
                for ref in third_terminal.owner_receipt_refs
                if _within_fixture_owner(control._artifact_store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_no_growth_receipt"
            )
            assert len(no_growth_refs) == 1, third_terminal.owner_receipt_refs
            no_growth_ref = no_growth_refs[0]
            no_growth_manifest = _within_fixture_owner(
                control._artifact_store.get_manifest, no_growth_ref
            )
            assert no_growth_manifest.artifact_schema is not None
            assert no_growth_manifest.artifact_schema.name == (
                "polisyos.runtime.AcquisitionWorldGrowthNoGrowthReceipt"
            )
            assert no_growth_manifest.artifact_schema.version == "1.1"
            no_growth = AcquisitionWorldGrowthNoGrowthReceipt.model_validate(
                _within_fixture_owner(
                    cases[-1].bridge._read,
                    no_growth_ref,
                    "runtime_quality.acquisition_world_growth_no_growth_receipt",
                )
            )
            assert no_growth.growth_receipt_ref == prior_growth_ref
            assert no_growth.action_phase_ref == executing_head.receipt_ref
            assert executing_head.receipt_ref in third_terminal.owner_receipt_refs
            assert no_growth_ref == prepared_selector.receipt_ref
            assert no_growth.admitted_observation_delta == 0
            assert no_growth.before == no_growth.after
            assert (
                admitted_membership_delta(
                    before=no_growth.before,
                    after=no_growth.after,
                    epoch_id=no_growth.selection.epoch_id,
                    passport_id=no_growth.passport_id,
                )
                == 0
            )
            attempt = AcquisitionWorldGrowthAttempt.model_validate(
                _within_fixture_owner(
                    cases[-1].bridge._read,
                    no_growth.attempt_ref,
                    "runtime_quality.acquisition_world_growth_attempt",
                )
            )
            assert attempt.binding_id == no_growth.binding_id
            assert attempt.owner_receipt_refs == no_growth.live_evidence_refs
            assert prior_growth_ref in third_terminal.owner_receipt_refs
            no_growth_scope = _within_fixture_owner(
                reconcile_authority_ref,
                artifact_store=control._artifact_store,
                event_log=cases[-1].bridge.event_log,
                cas_ref=no_growth_ref,
                expected_tenant_id=closure.tenant_id,
                expected_cell_id=closure.cell_id,
                expected_run_id=closure.run_id,
                expected_job_id=closure.source_job_id,
            )
            assert no_growth_scope.durable_event_id is not None

            route_growth_response = client.get(route_collection_path, headers=route_read_headers)
            assert route_growth_response.status_code == 200, route_growth_response.text
            selected_growth = route_growth_response.json()["routes"][0]
            assert selected_growth["world_growth"] == "no_growth"
            assert selected_growth["admitted_observation_delta"] == 0

            growth_pointer = cases[-1].bridge._growth_pointer(no_growth.selection, create=False)
            original_growth_pointer = growth_pointer.read_bytes()
            attempt_pointer = growth_pointer.with_suffix(".attempt.json")
            assert attempt_pointer.exists()
            try:
                growth_pointer.write_text(
                    json.dumps(
                        {
                            "receipt_kind": (
                                "runtime_quality.acquisition_world_growth_no_growth_receipt"
                            ),
                            "receipt_ref": prior_growth_ref,
                        }
                    )
                    + "\n"
                )
                forged_no_growth = client.get(route_collection_path, headers=route_read_headers)
                assert forged_no_growth.status_code == 200, forged_no_growth.text
                assert forged_no_growth.json()["routes"][0]["world_growth"] == "no_growth"
                assert forged_no_growth.json()["routes"][0]["admitted_observation_delta"] == 0
            finally:
                growth_pointer.write_bytes(original_growth_pointer)

            try:
                growth_pointer.unlink()
                assert attempt_pointer.exists()
                assert _within_fixture_owner(control._artifact_store.get_bytes, no_growth_ref)
                unknown_growth = client.get(route_collection_path, headers=route_read_headers)
                assert unknown_growth.status_code == 200, unknown_growth.text
                unknown_route = unknown_growth.json()["routes"][0]
                assert unknown_route["world_growth"] == "no_growth"
                assert unknown_route["admitted_observation_delta"] == 0
                assert prior_growth_ref in third_terminal.owner_receipt_refs
            finally:
                growth_pointer.write_bytes(original_growth_pointer)

            restored_growth = client.get(route_collection_path, headers=route_read_headers)
            assert restored_growth.status_code == 200, restored_growth.text
            assert restored_growth.json()["routes"][0]["world_growth"] == "no_growth"
            assert restored_growth.json()["routes"][0]["admitted_observation_delta"] == 0

            third_history_response = client.get(history_path, headers=history_headers)
            assert third_history_response.status_code == 200, third_history_response.text
            third_candidate_projection = third_history_response.json()["run"][
                "candidate_simulation"
            ]
            assert third_candidate_projection["acquisition_history_limitation_code"] is None
            assert {
                key: value
                for key, value in third_candidate_projection.items()
                if key
                not in {
                    "acquisition_history",
                    "acquisition_history_limitation_code",
                }
            } == candidate_projection_before_noop
            third_history = third_candidate_projection["acquisition_history"]
            assert len(third_history) == 3
            history_by_generation = {entry["action_generation"]: entry for entry in third_history}
            assert set(history_by_generation) == {1, 2, 3}
            third_history_row = history_by_generation[3]
            assert third_history_row["route_receipt_ref"]["artifact_id"] == third_terminal_ref
            assert third_history_row["terminal_outcome"] == "quarantined_no_growth"
            assert third_history_row.get("reentry_receipt_ref") is None
            assert third_history_row.get("old_candidate_id") is None
            assert third_history_row.get("new_candidate_id") is None
            assert third_history_row.get("new_candidate_source_ref") is None
            assert third_history_row.get("origin_source_ref") is not None
            assert third_history_row.get("expected_origin_source_ref") is None
            assert third_history_row["origin_source_binding_status"] == "observed_only"
            assert third_history_row["continuation_join_status"] == "not_applicable"
            assert sum(row.get("reentry_receipt_ref") is not None for row in third_history) == 1
            assert history_by_generation[2]["terminal_outcome"] == "reentry_completed"
            assert history_by_generation[2]["old_candidate_id"] == reentry.source_candidate_ref
            assert history_by_generation[2]["new_candidate_id"] == cycle.selected_candidate_ref

            # Fresh GET must refuse corrupted lineage owners and restore the probe bytes.
            from polisyos.core.artifacts.ids import ArtifactID

            origin_blob_path, _origin_manifest_path = control._artifact_store._paths(
                ArtifactID.model_validate(origin_source_ref.artifact_id)
            )
            original_origin_bytes = origin_blob_path.read_bytes()
            try:
                origin_blob_path.write_bytes(original_origin_bytes + b"corrupt")
                corrupted_origin_response = client.get(history_path, headers=history_headers)
            finally:
                origin_blob_path.write_bytes(original_origin_bytes)
            assert corrupted_origin_response.status_code == 200, corrupted_origin_response.text
            corrupted_origin_projection = corrupted_origin_response.json()["run"][
                "candidate_simulation"
            ]
            assert corrupted_origin_projection["acquisition_history"] == []
            assert corrupted_origin_projection["acquisition_history_limitation_code"] == (
                "acquisition_action_history_integrity_not_established"
            )

            reentry_blob_path, _reentry_manifest_path = control._artifact_store._paths(
                ArtifactID.model_validate(reentry_ref)
            )
            original_reentry_bytes = reentry_blob_path.read_bytes()
            try:
                reentry_blob_path.write_bytes(original_reentry_bytes + b"corrupt")
                corrupted_reentry_response = client.get(history_path, headers=history_headers)
            finally:
                reentry_blob_path.write_bytes(original_reentry_bytes)
            assert corrupted_reentry_response.status_code == 200, corrupted_reentry_response.text
            corrupted_reentry_projection = corrupted_reentry_response.json()["run"][
                "candidate_simulation"
            ]
            assert corrupted_reentry_projection["acquisition_history"] == []
            assert corrupted_reentry_projection["acquisition_history_limitation_code"] == (
                "acquisition_action_history_integrity_not_established"
            )

            if include_b09_evidence:
                refreshes = cases[-1].bridge.config.candidate_world_refreshes
                assert len(refreshes) == 1
                refresh = refreshes[0]
                source_history = snapshot_payload["_policyos_acquisition_history"]
                persisted_rows = [
                    row["observation"]
                    for row in source_history
                    if row["observation_id"] == selected.observation.observation_id
                ]
                assert len(persisted_rows) == 1
                persisted_row = persisted_rows[0]
                assert persisted_row == selected.observation.model_dump(mode="json")
                acquisition_metadata = snapshot_payload["_policyos_acquisition"]
                assert (
                    acquisition_metadata["selected_observation_id"]
                    == selected.observation.observation_id
                )
                assert acquisition_metadata["source_time_status"] == "not_established"
                assert acquisition_metadata["selected_row_content_sha256"] == (
                    selected.row_content_sha256
                )

                from polisyos.core.artifacts import ArtifactRef
                from polisyos.core.artifacts.canonical_profile import artifact_ref_for_manifest
                from polisyos.core.contracts.runtime import (
                    RunCandidateSimulationAcquisitionHistoryEntry,
                )

                second_history_row = history_by_generation[2]
                second_history_entry = RunCandidateSimulationAcquisitionHistoryEntry.model_validate(
                    second_history_row
                )
                third_history_entry = RunCandidateSimulationAcquisitionHistoryEntry.model_validate(
                    third_history_row
                )
                second_route_ref = second_history_entry.route_receipt_ref
                third_route_ref = third_history_entry.route_receipt_ref
                second_route_id = str(second_route_ref.artifact_id)
                third_route_id = str(third_route_ref.artifact_id)
                second_route_manifest = _within_fixture_owner(
                    control._artifact_store.get_manifest,
                    second_route_ref,
                )
                third_route_manifest = _within_fixture_owner(
                    control._artifact_store.get_manifest,
                    third_route_ref,
                )

                def _selected_manifest_view(
                    ref: ArtifactRef,
                ) -> tuple[object, bytes, dict[str, object]]:
                    assert ref.manifest_profile_sha256 is not None
                    manifest = _within_fixture_owner(control._artifact_store.get_manifest, ref)
                    manifest_ref = artifact_ref_for_manifest(manifest)
                    assert artifact_ref_identity_key(ref) == artifact_ref_identity_key(manifest_ref)
                    payload = _within_fixture_owner(control._artifact_store.get_bytes, ref)
                    assert "sha256:" + hashlib.sha256(payload).hexdigest() == str(ref.artifact_id)
                    schema = manifest.artifact_schema
                    assert schema is not None
                    return (
                        manifest,
                        payload,
                        {
                            "profile_bound_ref": ref.model_dump(mode="json"),
                            "identity": list(artifact_ref_identity_key(ref)),
                            "manifest_profile_sha256": ref.manifest_profile_sha256,
                            "manifest_artifact_id": str(manifest.artifact_id),
                            "manifest_kind": manifest.kind,
                            "manifest_media_type": manifest.media_type,
                            "manifest_created_at": manifest.created_at.isoformat(),
                            "schema_name": schema.name,
                            "schema_version": schema.version,
                            "payload_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                        },
                    )

                second_route_manifest, second_route_bytes, second_route_view = (
                    _selected_manifest_view(second_route_ref)
                )
                third_route_manifest, third_route_bytes, third_route_view = _selected_manifest_view(
                    third_route_ref
                )
                second_route_receipt = AcquisitionRouteLoopReceipt.model_validate(
                    canon.from_canonical_bytes(second_route_bytes)
                )
                third_route_receipt = AcquisitionRouteLoopReceipt.model_validate(
                    canon.from_canonical_bytes(third_route_bytes)
                )
                for entry, manifest, receipt, generation, view in (
                    (
                        second_history_entry,
                        second_route_manifest,
                        second_route_receipt,
                        2,
                        second_route_view,
                    ),
                    (
                        third_history_entry,
                        third_route_manifest,
                        third_route_receipt,
                        3,
                        third_route_view,
                    ),
                ):
                    assert entry.route_receipt_ref.kind == manifest.kind
                    assert entry.route_receipt_ref.media_type == manifest.media_type
                    assert receipt.action_generation == generation
                    assert receipt.action_generation == entry.action_generation
                    assert receipt.route_id == entry.route_id
                    assert receipt.terminal_outcome == entry.terminal_outcome
                    assert manifest.artifact_schema is not None
                    assert manifest.artifact_schema.name == (
                        f"polisyos.runtime.{AcquisitionRouteLoopReceipt.__name__}"
                    )
                    assert (
                        manifest.artifact_schema.version
                        == (receipt.schema_version.rsplit("@", 1)[1])
                    )
                    assert manifest.producer is not None
                    assert manifest.producer.component == (
                        "polisyos.runtime.acquisition_route_loop"
                    )
                    view["receipt_action_generation"] = receipt.action_generation
                    view["receipt_terminal_outcome"] = receipt.terminal_outcome
                    view["receipt_schema_version"] = receipt.schema_version

                assert second_history_entry.reentry_receipt_ref is not None
                second_reentry_ref = second_history_entry.reentry_receipt_ref
                second_reentry_manifest, second_reentry_bytes, second_reentry_view = (
                    _selected_manifest_view(second_reentry_ref)
                )
                reentry_receipt = AcquisitionOverlayReentryReceipt.model_validate(
                    canon.from_canonical_bytes(second_reentry_bytes)
                )
                assert second_reentry_manifest.artifact_schema is not None
                assert second_reentry_manifest.artifact_schema.name == (
                    f"polisyos.runtime.{AcquisitionOverlayReentryReceipt.__name__}"
                )
                second_reentry_view["receipt_schema_version"] = reentry_receipt.schema_version
                b09_evidence = {
                    "rule_projection": {
                        "status": "test_only_existing_owner_projection",
                        "source_registration": passport.registration.model_dump(mode="json"),
                        "source_field_binding": passport.field_binding.model_dump(mode="json"),
                        "source_profile_id": passport.measured_profile.source_profile_id,
                        "candidate_refresh_mapping": {
                            "profile_selection_ref": refresh.profile_selection_ref,
                            "canonical_variable_id": refresh.canonical_variable_id,
                            "target_slot_id": refresh.target_slot_id,
                            "mapping_semantics": refresh.mapping_semantics,
                        },
                        "candidate_profile_selection_ref": (n5_input.profile.profile_selection_ref),
                        "candidate_scenario_rule": n5_input.profile.rule.model_dump(mode="json"),
                    },
                    "rows": [persisted_row],
                    "history_entries": [
                        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(
                            row
                        ).model_dump(mode="json")
                        for row in third_history
                    ],
                    "row_content_sha256": selected.row_content_sha256,
                    "source_time_status": projection.source_time_status,
                    "data_transaction_time": acquisition_metadata[
                        "materialized_at_transaction_time"
                    ],
                    "occurrences": {
                        "generation_2_reentry": {
                            "action_generation": 2,
                            "route_receipt_ref": second_route_id,
                            "route_receipt_view": second_route_view,
                            "reentry_receipt_ref": str(second_reentry_ref.artifact_id),
                            "reentry_receipt_view": second_reentry_view,
                            "route_manifest_created_at": (
                                second_route_manifest.created_at.isoformat()
                            ),
                            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
                            "n5_input_ref": str(n5_input_ref.artifact_id),
                            "world_model_record_hash": acquired_world.content_hash,
                            "candidate_id": cycle.selected_candidate_ref,
                        },
                        "generation_3_no_growth": {
                            "action_generation": 3,
                            "route_receipt_ref": third_route_id,
                            "route_receipt_view": third_route_view,
                            "action_phase_ref": str(no_growth.action_phase_ref),
                            "no_growth_receipt_ref": str(no_growth_ref),
                            "route_manifest_created_at": (
                                third_route_manifest.created_at.isoformat()
                            ),
                            "prior_growth_receipt_ref": str(no_growth.growth_receipt_ref),
                            "transport_call_count": len(cases[-1].transport_calls),
                            "new_n5_input_ref": None,
                            "retained_n5_input_ref": str(n5_input_ref.artifact_id),
                        },
                    },
                    "limitations": [
                        "test_only_existing_profile_and_mapping_projection",
                        "generation_3_is_no_growth_without_a_second_source_fetch",
                        "source_time_not_established",
                        "route_profile_is_reader_materialized_selected_manifest_view_not_producer_attestation",
                        "no_production_issuer_or_currentness_claim",
                        "new_epoch_same_content_and_actual_changed_row_reissue_unrun",
                    ],
                }

    finally:
        port_patch.undo()
        trust.close()

    result = {"run_id": core_run_id, "candidate_id": cycle.selected_candidate_ref}
    if source_root_witness_json is not None:
        result["source_root_witness_json"] = source_root_witness_json_for_return()
    if include_b09_evidence:
        assert b09_evidence is not None
        result["b09_evidence_json"] = json.dumps(
            b09_evidence,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    return result


@pytest.fixture
def served_recorded_candidate_gateway(monkeypatch):
    """Serve the controlled captured N4 recording to the real traced gateway client."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


def build_same_candidate_history_fixture(
    *,
    fixture_root: Path,
    cas_root: Path,
    tenant_id: str,
    cell_id: str,
) -> dict[str, str]:
    """Build the existing source-owned producer chain and return its run identity.

    The integration producer creates and verifies signed test-only authority, runs the
    ordinary request/worker path, persists source lineage, and confirms a fresh GET. Its
    output is reused by the local browser fixture; no production issuer/currentness claim is
    inferred from the test signature.
    """
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    producer = sys.modules[__name__]

    fixture_root.mkdir(parents=True, exist_ok=True)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(producer, "TENANT", tenant_id)
    monkeypatch.setattr(producer, "CELL", cell_id)
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(fixture_root / "control.sqlite3"))
    try:
        with ControlledCandidateGateway() as gateway:
            monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
            result = producer._produce_served_acquisition_history(
                fixture_root,
                monkeypatch,
                gateway,
                fixture_cas_root=cas_root,
                stop_after_fresh_get=True,
            )
    finally:
        monkeypatch.undo()
    if not isinstance(result, dict) or not result.get("run_id") or not result.get("candidate_id"):
        raise RuntimeError("same_candidate_history_fixture_producer_unavailable")
    return result
