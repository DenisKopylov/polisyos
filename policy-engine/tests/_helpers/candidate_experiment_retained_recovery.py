"""Recompose real fixture owners around one retained candidate acquisition job.

The deployment and demo IdP are new. Institutional keys, signed approvals,
selected artifacts, creation scope, SQLite history and physical ledger are
retained. Opening this context neither leases nor dispatches a job.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest


@contextmanager
def retained_candidate_runtime(
    *,
    fixture_root: Path,
    job_id: str,
    output_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_owner_root: Path | None = None,
    issuer_fixture_root: Path | None = None,
) -> Iterator[dict[str, object]]:
    """Open the actual Runtime using retained selected inputs and new demo identity.

    Args:
        fixture_root: Existing fixture owning the CAS, SQLite and eight key pairs.
        job_id: Exact retained acquisition job to inspect or ordinarily recover.
        output_root: Fresh directory for this deployment's public reconstruction inputs.
        monkeypatch: Fixture environment owner, restored when the context exits.
        source_owner_root: Explicit retained Catalog owner; defaults to the original fixture layout.
        issuer_fixture_root: Explicit retained issuer; defaults to the original fixture layout.
    """
    from fastapi.testclient import TestClient

    from polisyos.core import artifacts
    from polisyos.core.artifacts.canonical_profile import (
        read_core_json_artifact,
        require_declared_profile,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
        DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
        DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
        DEFAULT_L5_MEASUREMENT_REGISTRY,
    )
    from polisyos.runtime.http import deployment_security as security
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.services.acquisition_action_service import (
        CandidateExperimentRouteMutationRequest,
    )
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )
    from polisyos.runtime.quality import agent_action_authority as authority
    from polisyos.runtime.quality import substrate_registry
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedAcquisitionPolicy,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.candidate_cycle_source_profile import (
        install_candidate_cycle_l6_source_root_reader,
    )
    from tests._helpers.control_worker import stop_embedded_control_worker
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        _candidate_experiment_policy_owner,
    )

    fixture = fixture_root.resolve(strict=True)
    output_root.mkdir(parents=True, exist_ok=False)
    database = fixture / ".polisyos/control_plane.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute("SELECT * FROM control_jobs WHERE job_id=?", (job_id,)).fetchone()
        if row is None or row["job_kind"] != "acquisition":
            raise ValueError("retained_candidate_acquisition_job_missing")
        payload_ref = row["payload_ref"]
        created = connection.execute(
            "SELECT payload_json FROM control_job_events WHERE job_id=? AND event_type=?",
            (job_id, "job_created"),
        ).fetchall()
        if len(created) != 1:
            raise ValueError("retained_candidate_creation_scope_ambiguous")
        creation_scope = json.loads(created[0]["payload_json"])["execution_scope"]
    # The shared fresh-fixture owner has a create-on-miss path. Recovery must
    # refuse before entering it when any retained issuer input is absent.
    issuer_fixture = (
        issuer_fixture_root if issuer_fixture_root is not None else fixture / "candidate-issuer"
    ).resolve()
    issuer_root = issuer_fixture / "repo"
    if not all(
        (issuer_root / path).is_file()
        for path in (
            DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
            DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
            DEFAULT_L5_MEASUREMENT_REGISTRY,
            Path("catalog/catalog.duckdb"),
        )
    ):
        raise ValueError("retained_candidate_issuer_inputs_missing")
    source_root = (
        source_owner_root
        if source_owner_root is not None
        else fixture / "labor-source/policy-engine"
    ).resolve()
    if source_owner_root is not None and not source_root.is_dir():
        raise ValueError("retained_candidate_source_root_missing")
    read_store = artifacts.FileSystemCAS.open_existing_read_only(fixture / "cas")

    def read(selector: object) -> object:
        return require_declared_profile(read_core_json_artifact(read_store, selector))

    # The job payload selects the old scope. These are inputs, not a new scope grant.
    tenant_id, cell_id = (creation_scope[name] for name in ("tenant_id", "cell_id"))
    run_id = row["run_id"]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        payload = read(payload_ref)
        if tuple(payload[name] for name in ("tenant_id", "cell_id", "run_id")) != (
            tenant_id,
            cell_id,
            run_id,
        ):
            raise ValueError("retained_candidate_creation_payload_scope_changed")
        request = CandidateExperimentRouteMutationRequest.model_validate(payload["request"])
        decision_ref = payload["decision_ref"]
        decision = authority.AgentActionAuthorityDecision.model_validate(read(decision_ref))
        policy = CandidateUnpricedAcquisitionPolicy.model_validate(
            read(request.replay_pins.policy_ref)
        )
        source = read(request.replay_pins.configured_port_source_ref)
        n5_input = read(artifacts.ArtifactRef.model_validate(source["n5_input_ref"]))
        profile = CandidateSimulationScenarioProfile.model_validate(n5_input["profile"])
        declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
            read(artifacts.ArtifactRef.model_validate(n5_input["model_declaration_ref"]))
        )
        current_refs = []
        for ref in decision.replay_input_refs:
            if not ref.startswith("sha256:"):
                continue
            try:
                manifest = read_store.get_manifest(ref)
            except FileNotFoundError:
                continue  # Content hashes in the decision are not all artifact selectors.
            if manifest.kind == authority.CURRENT_MANDATE_OWNER_ARTIFACT_KIND:
                current_refs.append(ref)
        if len(current_refs) != 1 or decision.contract_ref is None:
            raise ValueError("retained_candidate_mandate_selection_ambiguous")
        current = authority.CurrentMandateOwnerEvidence.model_validate(read(current_refs[0]))

    trust = served._ExternalTrust(output_root)
    try:
        signers, identities = served._existing_key_config(fixture, trust)
        trust.raw["acquisition_authority"]["mandates"] = [
            {
                "tenant_id": tenant_id,
                "cell_id": cell_id,
                "run_id": run_id,
                "route_id": payload["route_id"],
                "resource_digest": decision.bound_resource_digest,
                "delegation_contract_ref": decision.contract_ref,
                "mandate_owner_ref": current.mandate_owner_ref,
                "delegation_public_key_path": str(fixture / "owner.pub"),
                "current_mandate_evidence_ref": current_refs[0],
                "current_mandate_signer_identity": current.evidence_signer_identity,
                "current_mandate_public_key_path": str(fixture / "current.pub"),
                "verifier_provenance_ref": "fixture://candidate-experiment/independent-appointment",
            }
        ]
        (output_root / "public-reconstruction.json").write_text(
            json.dumps(
                {
                    "identity_context": "new_explicit_demo_IdP_not_original_deployment_recovery",
                    "job_id": job_id,
                    "payload_ref": payload_ref,
                    "decision_ref": decision_ref,
                    "original_authority_valid_until": current.effective_until.isoformat(),
                    "source_owner_root": str(source_root),
                    "issuer_fixture_root": str(issuer_fixture),
                    "deployment_config": trust.raw,
                },
                indent=2,
            )
            + "\n"
        )
        selection = substrate_registry.CatalogServingSourceSelection(
            snapshot_root=source_root / "complete-cov-published-catalog/snapshot",
            source_owner_root=source_root,
            catalog_run_profile="prod_full",
        )
        with monkeypatch.context() as environment:
            environment.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
            environment.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
            environment.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
            environment.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(database))
            environment.setenv("POLISYOS_CACHE_HOME", str(output_root / "runtime-cache"))
            install_candidate_cycle_l6_source_root_reader(
                environment, code_root=served.REPO_ROOT, source_owner_root=source_root
            )
            providers = resolve_control_registry_providers(
                capability_resolver=RequirementToCapabilityResolver.governed_fixture(
                    served.REPO_ROOT
                ),
                catalog_source_selection=selection,
                catalog_run_profile=selection.catalog_run_profile,
            )
            app = create_runtime_api_app(
                cas_root=fixture / "cas",
                core_runs_root=fixture / "cas/runs",
                deployment_security=security.build_deployment_security(
                    security.DeploymentSecurityConfig.from_mapping(trust.raw)
                ),
                enable_security_middlewares=True,
                enable_csrf_protection=False,
                container_overrides=RuntimeContainerOverrides(control_registry_providers=providers),
                candidate_simulation_profiles=(profile,),
                candidate_simulation_model_declarations=(declaration,),
                repo_root=source_root,
                catalog_source_selection=selection,
                catalog_run_profile=selection.catalog_run_profile,
            )
            with TestClient(app) as client:
                control = client.app.state._control_service
                stop_embedded_control_worker(control)
                owner = _candidate_experiment_policy_owner(
                    control=control,
                    fixture_root=issuer_fixture,
                    run_id=run_id,
                    subsequent_attempt_ids=tuple(policy.configured_template.subsequent_attempt_ids),
                )
                if owner.template != policy.configured_template:
                    raise ValueError("retained_candidate_current_template_changed")
                control._registry_providers = replace(
                    control._registry_providers,
                    source_profiles=owner.source_profiles,
                    candidate_unpriced_policy_bindings=(),
                    candidate_unpriced_policy_templates=(owner.template,),
                )
                action_service = client.app.state.runtime_container.acquisition_action_service
                yield {
                    "control": control,
                    "client": client,
                    "trust": trust,
                    "signers": signers,
                    "identities": identities,
                    "key_root": fixture,
                    "run_id": run_id,
                    "job_id": job_id,
                    "action_service": action_service,
                    "policy_owner": owner,
                    "policy": policy,
                    "policy_ref": request.replay_pins.policy_ref,
                    "request": request,
                    "decision_ref": decision_ref,
                    "source_owner_root": source_root,
                    "authority_valid_until": current.effective_until,
                }
    finally:
        trust.close()
