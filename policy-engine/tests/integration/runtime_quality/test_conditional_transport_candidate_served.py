"""Served conditional-transport candidate projection from real engine artifacts."""

from __future__ import annotations

import dataclasses
import logging
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import ComponentId
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security.authz import AuthzDecision, AuthzResult
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
from polisyos.core.security.registry import CellRegistry
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    TransportabilityCandidateRequestV1,
    TransportabilityStatus,
    TransportMode,
    load_transportability_result,
)
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
    RunTransportabilityNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path

_TREATMENT = "consumption_response"
_OUTCOME = "gdp_growth"
_PROFILE_ID = "pag.no_selection.finite_member_sensitivity"
_PROFILE_REVISION = "1"
_SELECTION = "transport-candidate.standard.v1"
_TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_SHA_A = "sha256:" + "a" * 64


class _AllowOPA:
    async def check(self, authz_input: object) -> AuthzResult:
        del authz_input
        return AuthzResult(decision=AuthzDecision.ALLOW, policy="polisyos/authz/decision")


class _IdentityProvider:
    def __init__(self, claims: dict[str, UserIdentityClaims]) -> None:
        self._claims = claims

    def extract_user_claims(
        self,
        jwt_token: str,
        *,
        expected_cell_id: str | None = None,
    ) -> UserIdentityClaims:
        claim = self._claims[jwt_token]
        if expected_cell_id is not None and claim.cell_id != expected_cell_id:
            raise ValueError("cell binding mismatch")
        return claim


def _identity_claims(
    *,
    tenant_id: str,
    cell_id: str,
    role: PolicyOSRole,
    token_id: str,
) -> UserIdentityClaims:
    return UserIdentityClaims(
        sub=f"transport-{role.value}",
        email=f"transport-{role.value}@example.test",
        tenant_id=tenant_id,
        cell_id=cell_id,
        roles=frozenset({role}),
        mfa_verified=True,
        iss="https://identity.example.test/realms/polisyos",
        aud="polisyos-web",
        exp=4_102_444_800,
        iat=1,
        jti=token_id,
    )


def _source_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=[_TREATMENT, _OUTCOME],
        edges=[
            CausalEdge(
                src=_TREATMENT,
                dst=_OUTCOME,
                mark_src=EdgeMark.CIRCLE,
                mark_dst=EdgeMark.CIRCLE,
            )
        ],
        discovery_method="FCI",
    )


def _source_report() -> CausalEffectReport:
    """Provide a typed upstream input; this synthetic fixture is not proof."""
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
        method_params={"source_type": "external_literature"},
    )


def _run_transportability_node(
    *,
    store: FileSystemCAS,
    registry_bundle_ref: ArtifactRef,
    source_report_ref: ArtifactRef,
    graph_ref: ArtifactRef,
    tenant_id: str,
    cell_id: str,
    tamper_resource_policy: bool = False,
    request_params: dict[str, Any] | None = None,
    run_id: str | None = None,
    control_job_id: str | None = None,
) -> tuple[str, ArtifactRef | None, Any | None, Any, list[ArtifactRef]]:
    """Run the real node and persist its selected refs into a terminal Core run."""
    from polisyos.ir.analytics.causal import CausalEffectReportRef
    from polisyos.ir.analytics.transportability import (
        TransportabilityCandidateRequestV1,
        TransportabilityResultRef,
    )
    from polisyos.scientist.orchestration.workflows.causal_full import (
        CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM,
        causal_full_workflow_spec,
    )

    ir_store = ensure_ir_artifact_store(store)
    run_id = run_id or f"R_transport_served_{uuid.uuid4().hex}"
    candidate_request = TransportabilityCandidateRequestV1(
        schema_version="1.0",
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        selection_identity=_SELECTION,
    )
    params: dict[str, Any] = {
        "conditional_transport_request": candidate_request.model_dump(mode="json"),
        "query_treatment": _TREATMENT,
        "query_outcome": _OUTCOME,
        "transport_solver_mode": "simplified",
        "source_context": ContextProfile(
            context_id="source",
            income_level=IncomeLevel.HIGH,
        ).model_dump(mode="json"),
        "target_context": ContextProfile(
            context_id="target",
            income_level=IncomeLevel.LOW,
        ).model_dump(mode="json"),
    }
    if request_params is not None:
        params = dict(request_params)
    request = WorkflowRunRequest.model_validate(
        {
            "data_source": {"data_snapshot_ref": _SHA_A},
            "params": params,
        }
    )
    assert request.params == params

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle_ref,
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
        if control_job_id is not None:
            run.update_manifest(control_job_id=control_job_id)
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger(f"conditional_transport_served.{run_id}"),
        )
        registry = NodeRegistry()
        registry.register(RunTransportabilityNode())
        canonical_workflow = causal_full_workflow_spec()
        canonical_transport_node = next(
            invocation
            for invocation in canonical_workflow.nodes
            if invocation.alias == "run_transportability"
        )
        transport_node_params = dict(canonical_transport_node.params)
        if tamper_resource_policy:
            frozen_policy = dict(transport_node_params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM])
            frozen_limits = dict(frozen_policy["limits"])
            frozen_limits["max_members"] = int(frozen_limits["max_members"]) - 1
            frozen_policy["limits"] = frozen_limits
            transport_node_params[CAUSAL_FULL_TRANSPORT_RESOURCE_POLICY_PARAM] = frozen_policy
        if canonical_transport_node.timeout_s is None:
            raise AssertionError("the canonical transport node must carry its supervised timeout")
        workflow = WorkflowSpec(
            workflow_id="conditional_transport_candidate_served",
            required_binds=["run_id"],
            nodes=[
                NodeInvocation(
                    alias="run_transportability",
                    node_id=ComponentId.parse("scientist.node_run_transportability@1.0.0"),
                    params=transport_node_params,
                    timeout_s=canonical_transport_node.timeout_s,
                )
            ],
        )
        state = ExperimentState(
            run_id=run_id,
            control_job_id=control_job_id,
            execution_profile="research",
            artifacts_index={
                ARTIFACT_CAUSAL_REPORT_REF: CausalEffectReportRef.model_validate(
                    source_report_ref.model_dump(mode="python")
                ),
                ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: graph_ref,
            },
            params=dict(request.params),
        )
        execution = WorkflowExecutor(ctx, registry).execute(workflow, state)
        run_output_refs = list(run.run_manifest.outputs)

        if ARTIFACT_TRANSPORTABILITY_RESULT_REF not in execution.state.artifacts_index:
            return run_id, None, None, execution, run_output_refs
        result_ref = TransportabilityResultRef.model_validate(
            execution.state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF].model_dump(
                mode="json"
            )
        )
        report_ref = CausalEffectReportRef.model_validate(
            execution.state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF].model_dump(mode="json")
        )
        output_identities = {
            (str(ref.artifact_id), ref.manifest_profile_sha256) for ref in run_output_refs
        }
        expected_output_refs = {
            (str(result_ref.artifact_id), result_ref.manifest_profile_sha256),
            (str(report_ref.artifact_id), report_ref.manifest_profile_sha256),
        }
        if not expected_output_refs.issubset(output_identities):
            raise AssertionError(
                "candidate selected refs are absent from the terminal Core run manifest"
            )
        result = load_transportability_result(ir_store, result_ref)
    return run_id, result_ref, result, execution, run_output_refs


@pytest.mark.integration
def test_real_transport_candidate_is_freshly_served_only_for_verified_review_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real solver lineage reaches GET as a candidate-only, access-gated summary."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    tenant_id = _TENANT_ID
    cell = CellSpec(tier=CellTier.SHARED, region="us-gov-west-1", max_tenants=50)
    cells = CellRegistry()
    cells.register_cell(cell)
    cells.register_tenant(
        TenantSpec(tenant_id=tenant_id, name="transport-served-test", region=cell.region),
        cell.cell_id,
    )
    store = FileSystemCAS(tmp_path / "cas").for_tenant(tenant_id, cell.cell_id)
    ir_store = ensure_ir_artifact_store(store)

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
        registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
        source_report_ref = persist_causal_effect_report(
            ir_store,
            _source_report(),
            return_selected_profile=True,
        )
        graph_ref = persist_causal_graph_model(
            ir_store,
            _source_graph(),
            return_selected_profile=True,
        )

    analyst_token = uuid.uuid4().hex
    viewer_token = uuid.uuid4().hex
    identity_provider = _IdentityProvider(
        {
            analyst_token: _identity_claims(
                tenant_id=tenant_id,
                cell_id=cell.cell_id,
                role=PolicyOSRole.ANALYST,
                token_id=uuid.uuid4().hex,
            ),
            viewer_token: _identity_claims(
                tenant_id=tenant_id,
                cell_id=cell.cell_id,
                role=PolicyOSRole.VIEWER,
                token_id=uuid.uuid4().hex,
            ),
        }
    )
    analyst_headers = {
        "Authorization": f"Bearer {analyst_token}",
        "X-Tenant-ID": tenant_id,
    }
    viewer_headers = {
        "Authorization": f"Bearer {viewer_token}",
        "X-Tenant-ID": tenant_id,
    }
    candidate_request = TransportabilityCandidateRequestV1(
        schema_version="1.0",
        profile_id=_PROFILE_ID,
        profile_revision=_PROFILE_REVISION,
        selection_identity=_SELECTION,
    )
    candidate_params: dict[str, Any] = {
        "conditional_transport_request": candidate_request.model_dump(mode="json"),
        "query_treatment": _TREATMENT,
        "query_outcome": _OUTCOME,
        "transport_solver_mode": "simplified",
        "source_context": ContextProfile(
            context_id="source",
            income_level=IncomeLevel.HIGH,
        ).model_dump(mode="json"),
        "target_context": ContextProfile(
            context_id="target",
            income_level=IncomeLevel.LOW,
        ).model_dump(mode="json"),
    }
    launch_request = WorkflowRunRequest.model_validate(
        {
            "data_source": {"data_snapshot_ref": _SHA_A},
            "params": candidate_params,
        }
    )
    post_app = create_runtime_api_app(
        cas_root=store.root,
        core_runs_root=store.root / "runs",
        enable_security_middlewares=True,
        identity_provider=identity_provider,
        cell_registry=cells,
        opa_client=_AllowOPA(),
    )
    from tests._helpers.control_worker import stop_embedded_control_worker

    with TestClient(post_app) as post_client:
        post_service = post_app.state._control_service
        stop_embedded_control_worker(post_service)
        launch_response = post_client.post(
            "/api/v1/control/runs",
            json=launch_request.model_dump(mode="json", exclude_none=True),
            headers=analyst_headers,
        )
        assert launch_response.status_code == 200, launch_response.text
        launch = launch_response.json()
        run_id = launch["run_id"]
        control_job_id = launch["job_id"]
        admitted_job = post_service._control_store.get_job(control_job_id)
        assert admitted_job is not None
        assert admitted_job.run_id == run_id
        assert admitted_job.kind == "workflow_run"
        assert admitted_job.payload_ref is not None
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
            admitted_payload = post_service._load_payload_ref(
                admitted_job.payload_ref,
                kind="runtime.control_job_payload.workflow_run",
            )
        admitted_params = admitted_payload["state_payload"]["params"]
        assert admitted_params == launch_request.params
        assert admitted_params["conditional_transport_request"] == candidate_request.model_dump(
            mode="json"
        )
        created_event = post_service._control_store.get_job_created_outbox_event(control_job_id)
        assert created_event.topic == "control.job.created"
        assert created_event.run_id == run_id

    (
        run_id,
        selected_result_ref,
        selected_result,
        selected_execution,
        selected_run_outputs,
    ) = _run_transportability_node(
        store=store,
        registry_bundle_ref=registry_bundle.bundle_ref,
        source_report_ref=source_report_ref,
        graph_ref=graph_ref,
        tenant_id=tenant_id,
        cell_id=cell.cell_id,
        request_params=admitted_params,
        run_id=run_id,
        control_job_id=control_job_id,
    )
    (
        tampered_policy_run_id,
        tampered_policy_ref,
        tampered_policy_result,
        tampered_policy_execution,
        tampered_policy_outputs,
    ) = _run_transportability_node(
        store=store,
        registry_bundle_ref=registry_bundle.bundle_ref,
        source_report_ref=source_report_ref,
        graph_ref=graph_ref,
        tenant_id=tenant_id,
        cell_id=cell.cell_id,
        tamper_resource_policy=True,
        request_params=admitted_params,
    )
    assert selected_result_ref is not None
    assert selected_result is not None
    assert selected_execution.report.status == "ok"
    assert selected_run_outputs
    assert tampered_policy_ref is None
    assert tampered_policy_result is None
    assert tampered_policy_execution.report.status == "fail"
    node_record = tampered_policy_execution.report.nodes[0]
    assert node_record.error is not None
    assert "conditional_transport_resource_policy_snapshot_mismatch" in node_record.error.message
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF not in (
        tampered_policy_execution.state.artifacts_index
    )
    assert not any(
        ref.kind in {"ir.transportability_result", "ir.causal_effect_report"}
        for ref in tampered_policy_outputs
    )

    app = create_runtime_api_app(
        cas_root=store.root,
        core_runs_root=store.root / "runs",
        enable_security_middlewares=True,
        identity_provider=identity_provider,
        cell_registry=cells,
        opa_client=_AllowOPA(),
    )
    with TestClient(app) as client:
        selected_response = client.get(
            f"/api/v1/runs/{run_id}",
            headers=analyst_headers,
        )
        assert selected_response.status_code == 200, selected_response.text
        receipt_root_value = os.environ.get("POLISYOS_R4_RECEIPT_ROOT")
        if receipt_root_value:
            import hashlib
            import json
            from pathlib import Path

            receipt_root = Path(receipt_root_value)
            receipt_root.mkdir(parents=True, exist_ok=True)
            response_bytes = selected_response.content
            response_path = receipt_root / "conditional-transport-selected-get.body"
            response_path.write_bytes(response_bytes)
            receipt_metadata = {
                "byte_count": len(response_bytes),
                "run_id": run_id,
                "sha256": hashlib.sha256(response_bytes).hexdigest(),
                "status_code": selected_response.status_code,
                "x_temporal_scope": selected_response.headers.get("X-Temporal-Scope"),
            }
            (receipt_root / "conditional-transport-selected-get.metadata.json").write_text(
                json.dumps(receipt_metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        selected_body = selected_response.json()
        projection = selected_body["run"]["conditional_transport_candidate"]
        assert projection["candidate_scope"] == "candidate_only"
        assert projection["candidate_disposition"] == "completed"
        assert projection["requested_profile_id"] == _PROFILE_ID
        assert projection["requested_profile_revision"] == _PROFILE_REVISION
        assert projection["selection_identity"] == _SELECTION
        assert projection["member_evaluation_count"] == 3
        assert projection["completed_valid_member_count"] == 3
        assert projection["identified_member_fraction"] == 1.0
        assert projection["identified_member_fraction_basis"] == (
            "selected_completed_valid_members"
        )
        assert projection["source_currentness"] == "unknown"
        assert projection["interpretation_limit"] == (
            "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility"
        )
        assert {
            "artifact_id",
            "report_ref",
            "result_ref",
            "manifest_profile_sha256",
            "authority",
            "publishable",
        }.isdisjoint(projection)

        assert selected_result.status is TransportabilityStatus.UNSUPPORTED
        assert selected_result.transport_mode is TransportMode.NONE
        assert selected_result.feasible is False
        assert selected_result.unsupported_reason == (
            "legal_source_relation_verification_not_established"
        )
        assert selected_result.candidate_diagnostics is not None
        assert selected_result.candidate_diagnostics.identified_member_fraction == 1.0

        from inspect import getsource, getsourcefile
        from textwrap import dedent

        from polisyos.core.artifacts import read_core_manifest_profile
        from polisyos.core.artifacts.manifest import (
            ArtifactManifest,
            InputRef,
            ProducerInfo,
            SchemaInfo,
        )
        from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
        from polisyos.ir.analytics.causal import (
            CausalEffectReportRef,
            load_causal_effect_report,
        )
        from polisyos.runtime.http.routes import runs as runs_routes

        selected_report_refs = [
            ref for ref in selected_run_outputs if ref.kind == "ir.causal_effect_report"
        ]
        assert len(selected_report_refs) == 1
        selected_report_ref = selected_report_refs[0]
        source_core_ref = ArtifactRef.model_validate(source_report_ref.model_dump(mode="json"))
        selected_report_core_ref = ArtifactRef.model_validate(
            selected_report_ref.model_dump(mode="json")
        )
        selected_result_core_ref = ArtifactRef.model_validate(
            selected_result_ref.model_dump(mode="json")
        )
        report_manifest, _report_declaration = read_core_manifest_profile(
            store, selected_report_core_ref
        )
        result_manifest, _result_declaration = read_core_manifest_profile(
            store, selected_result_core_ref
        )
        predecessor_edges = [
            edge for edge in report_manifest.inputs if edge.role == "causal_report_prev"
        ]
        report_result_edges = [
            edge for edge in report_manifest.inputs if edge.role == "transportability_result"
        ]
        result_source_edges = [
            edge for edge in result_manifest.inputs if edge.role == "causal_effect_report"
        ]
        assert len(predecessor_edges) == 1
        assert len(report_result_edges) == 1
        assert len(result_source_edges) == 1
        predecessor_edge = predecessor_edges[0]
        report_result_edge = report_result_edges[0]
        result_source_edge = result_source_edges[0]
        assert str(predecessor_edge.artifact_id) == str(source_report_ref.artifact_id)
        assert predecessor_edge.manifest_profile_sha256 == source_report_ref.manifest_profile_sha256
        assert str(result_source_edge.artifact_id) == str(predecessor_edge.artifact_id)
        assert (
            result_source_edge.manifest_profile_sha256 == predecessor_edge.manifest_profile_sha256
        )
        assert str(report_result_edge.artifact_id) == str(selected_result_ref.artifact_id)
        assert (
            report_result_edge.manifest_profile_sha256
            == selected_result_ref.manifest_profile_sha256
        )

        source_manifest, _source_declaration = read_core_manifest_profile(store, source_core_ref)
        assert source_manifest.artifact_schema is not None
        assert source_manifest.canon is not None
        typed_report_ref = CausalEffectReportRef.model_validate(
            selected_report_ref.model_dump(mode="json")
        )
        selected_report = load_causal_effect_report(ir_store, typed_report_ref)
        profile_variant_producer = ProducerInfo(
            component="test_conditional_transport_profile_variant",
            version="r2",
        )

        def _write_manifest_view(
            source_ref: ArtifactRef,
            source_manifest: ArtifactManifest,
            *,
            kind: str | None = None,
            schema: SchemaInfo | None = None,
            producer: ProducerInfo | None = None,
        ) -> ArtifactRef:
            options = ArtifactWriteOptions(
                kind=source_manifest.kind if kind is None else kind,
                media_type=source_manifest.media_type,
                schema=source_manifest.artifact_schema if schema is None else schema,
                producer=source_manifest.producer if producer is None else producer,
                env=source_manifest.env,
                inputs=list(source_manifest.inputs),
                canon=source_manifest.canon,
                governance=source_manifest.governance,
                tenant_context=source_manifest.tenant_context,
                same_input_closure=source_manifest.same_input_closure,
                authority=source_manifest.authority,
                warnings=list(source_manifest.warnings),
            )
            source_bytes = store.get_bytes(source_ref)
            variant_ref = store.put_bytes(
                source_bytes,
                options,
                return_selected_profile=True,
            )
            assert str(variant_ref.artifact_id) == str(source_ref.artifact_id)
            assert store.get_bytes(variant_ref) == source_bytes
            assert variant_ref.manifest_profile_sha256 is not None
            assert variant_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
            return variant_ref

        alternate_source_profile_ref = _write_manifest_view(
            source_core_ref,
            source_manifest,
            producer=profile_variant_producer,
        )

        alternate_source_report = _source_report().model_copy(
            update={"method_params": {"source_type": "lineage-control-alternate"}}
        )
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
            wrong_source_id_ref = persist_causal_effect_report(
                ir_store,
                alternate_source_report,
                return_selected_profile=True,
            )
        assert str(wrong_source_id_ref.artifact_id) != str(source_report_ref.artifact_id)

        alternate_source_schema_ref = _write_manifest_view(
            source_core_ref,
            source_manifest,
            schema=SchemaInfo(
                name="ir.lineage_control_foreign_causal_effect_report",
                version="9.9",
            ),
        )
        alternate_source_kind_ref = _write_manifest_view(
            source_core_ref,
            source_manifest,
            kind="ir.lineage_control_foreign_causal_effect_report",
        )

        alternate_result_profile_ref = _write_manifest_view(
            selected_result_core_ref,
            result_manifest,
            producer=profile_variant_producer,
        )

        def _selected_input(ref: ArtifactRef, *, role: str) -> InputRef:
            selected_core_ref = ArtifactRef.model_validate(ref.model_dump(mode="json"))
            assert selected_core_ref.manifest_profile_sha256 is not None
            return InputRef(
                artifact_id=selected_core_ref.artifact_id,
                role=role,
                manifest_profile_sha256=selected_core_ref.manifest_profile_sha256,
            )

        def _report_variant(
            *,
            predecessor: InputRef | None,
            result_input: InputRef | None = None,
            duplicate_predecessor: bool = False,
        ) -> ArtifactRef:
            variant_inputs: list[InputRef] = []
            for edge in report_manifest.inputs:
                if edge.role == "causal_report_prev":
                    if predecessor is not None:
                        variant_inputs.append(predecessor)
                        if duplicate_predecessor:
                            variant_inputs.append(predecessor)
                elif edge.role == "transportability_result":
                    variant_inputs.append(result_input or edge)
                else:
                    variant_inputs.append(edge)
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell.cell_id):
                return persist_causal_effect_report(
                    ir_store,
                    selected_report,
                    inputs=variant_inputs,
                    schema_version="1.1",
                    return_selected_profile=True,
                )

        lineage_controls = {
            "missing_predecessor": _report_variant(predecessor=None),
            "duplicate_predecessor": _report_variant(
                predecessor=predecessor_edge,
                duplicate_predecessor=True,
            ),
            "wrong_source_id": _report_variant(
                predecessor=_selected_input(wrong_source_id_ref, role="causal_report_prev")
            ),
            "wrong_source_profile": _report_variant(
                predecessor=_selected_input(alternate_source_profile_ref, role="causal_report_prev")
            ),
            "wrong_source_kind": _report_variant(
                predecessor=_selected_input(alternate_source_kind_ref, role="causal_report_prev")
            ),
            "wrong_source_schema": _report_variant(
                predecessor=_selected_input(alternate_source_schema_ref, role="causal_report_prev")
            ),
            "selected_result_report_edge_mismatch": _report_variant(
                predecessor=predecessor_edge,
                result_input=_selected_input(
                    alternate_result_profile_ref,
                    role="transportability_result",
                ),
            ),
        }

        run_index = app.state.runtime_api_ctx.run_index
        original_get_run = run_index.get_run
        original_index_record = original_get_run(run_id)
        assert original_index_record.run_id == run_id
        assert original_index_record.details.run_id == run_id
        assert original_index_record.details.tenant_id == tenant_id
        assert original_index_record.details.cell_id == cell.cell_id
        assert (
            sum(
                ref.kind == "ir.causal_effect_report"
                for ref in original_index_record.details.root_artifacts
            )
            == 1
        )
        assert (
            sum(
                ref.kind == "ir.transportability_result"
                for ref in original_index_record.details.root_artifacts
            )
            == 1
        )

        def _record_with_selected_report(report_ref: Any) -> Any:
            selected_core_ref = ArtifactRef.model_validate(report_ref.model_dump(mode="json"))
            root_artifacts = [
                selected_core_ref if ref.kind == "ir.causal_effect_report" else ref
                for ref in original_index_record.details.root_artifacts
            ]
            assert sum(ref.kind == "ir.causal_effect_report" for ref in root_artifacts) == 1
            assert sum(ref.kind == "ir.transportability_result" for ref in root_artifacts) == 1
            details = original_index_record.details.model_copy(
                update={"root_artifacts": root_artifacts}
            )
            record = dataclasses.replace(original_index_record, details=details)
            assert record.run_id == run_id and record.details.run_id == run_id
            assert (
                record.details.tenant_id,
                record.details.cell_id,
                record.details.status,
                record.details.started_at,
                record.details.finished_at,
            ) == (
                original_index_record.details.tenant_id,
                original_index_record.details.cell_id,
                original_index_record.details.status,
                original_index_record.details.started_at,
                original_index_record.details.finished_at,
            )
            assert [
                ref
                for ref in record.details.root_artifacts
                if ref.kind == "ir.transportability_result"
            ] == [
                ref
                for ref in original_index_record.details.root_artifacts
                if ref.kind == "ir.transportability_result"
            ]
            return record

        def _get_with_indexed_record(
            indexed_record: Any,
            *,
            projector: Any | None = None,
        ) -> Any:
            with monkeypatch.context() as control_patch:
                control_patch.setattr(
                    run_index,
                    "get_run",
                    lambda requested_run_id: (
                        indexed_record
                        if requested_run_id == run_id
                        else original_get_run(requested_run_id)
                    ),
                )
                if projector is not None:
                    control_patch.setattr(
                        runs_routes,
                        "_conditional_transport_candidate_for_indexed_run",
                        projector,
                    )
                response = client.get(
                    f"/api/v1/runs/{run_id}",
                    headers=analyst_headers,
                )
            assert response.status_code == 200, response.text
            return response

        same_run_positive = _get_with_indexed_record(original_index_record)
        assert (
            same_run_positive.json()["run"]["conditional_transport_candidate"]["candidate_scope"]
            == "candidate_only"
        )
        for label, report_ref in lineage_controls.items():
            control_record = _record_with_selected_report(report_ref)
            refused_response = _get_with_indexed_record(control_record)
            assert "conditional_transport_candidate" not in refused_response.json()["run"], label

        selected_projector = runs_routes._conditional_transport_candidate_for_indexed_run
        projector_source = dedent(getsource(selected_projector))
        source_join_guard = "if not root_matches_edge(source_report_ref, actual_edge):"
        assert projector_source.count(source_join_guard) == 1
        no_source_join_source = projector_source.replace(
            source_join_guard,
            "if False and not root_matches_edge(source_report_ref, actual_edge):",
            1,
        )
        projector_source_path = getsourcefile(selected_projector)
        assert projector_source_path is not None
        from types import CodeType, FunctionType

        mutant_module_code = compile(
            "from __future__ import annotations\n" + no_source_join_source,
            projector_source_path,
            "exec",
        )
        mutant_function_code = next(
            code
            for code in mutant_module_code.co_consts
            if isinstance(code, CodeType)
            and code.co_name == "_conditional_transport_candidate_for_indexed_run"
        )
        assert mutant_function_code.co_freevars == selected_projector.__code__.co_freevars
        no_source_join_projector = FunctionType(
            mutant_function_code,
            selected_projector.__globals__,
            selected_projector.__name__,
            selected_projector.__defaults__,
            selected_projector.__closure__,
        )
        no_source_join_projector.__kwdefaults__ = selected_projector.__kwdefaults__
        profile_control_record = _record_with_selected_report(
            lineage_controls["wrong_source_profile"]
        )
        mutant_response = _get_with_indexed_record(
            profile_control_record,
            projector=no_source_join_projector,
        )
        assert mutant_response.status_code == 200, mutant_response.text
        mutant_projection = mutant_response.json()["run"].get("conditional_transport_candidate")
        assert mutant_projection is not None
        assert mutant_projection["candidate_scope"] == "candidate_only"

        result_join_guard = "if not root_matches_edge(result_ref, result_edge):"
        assert projector_source.count(result_join_guard) == 1
        no_result_join_source = projector_source.replace(
            result_join_guard,
            "if False and not root_matches_edge(result_ref, result_edge):",
            1,
        )
        result_mutant_module_code = compile(
            "from __future__ import annotations\n" + no_result_join_source,
            projector_source_path,
            "exec",
        )
        result_mutant_function_code = next(
            code
            for code in result_mutant_module_code.co_consts
            if isinstance(code, CodeType)
            and code.co_name == "_conditional_transport_candidate_for_indexed_run"
        )
        assert result_mutant_function_code.co_freevars == selected_projector.__code__.co_freevars
        no_result_join_projector = FunctionType(
            result_mutant_function_code,
            selected_projector.__globals__,
            selected_projector.__name__,
            selected_projector.__defaults__,
            selected_projector.__closure__,
        )
        no_result_join_projector.__kwdefaults__ = selected_projector.__kwdefaults__
        result_edge_control_record = _record_with_selected_report(
            lineage_controls["selected_result_report_edge_mismatch"]
        )
        result_mutant_response = _get_with_indexed_record(
            result_edge_control_record,
            projector=no_result_join_projector,
        )
        assert result_mutant_response.status_code == 200, result_mutant_response.text
        result_mutant_projection = result_mutant_response.json()["run"].get(
            "conditional_transport_candidate"
        )
        assert result_mutant_projection is not None
        assert result_mutant_projection["candidate_scope"] == "candidate_only"

        access_audit = app.state.runtime_access_audit
        before_historical_audit = access_audit.scan_read_only().entries
        started_at = datetime.fromisoformat(
            selected_body["run"]["started_at"].replace("Z", "+00:00")
        )
        finished_at = datetime.fromisoformat(
            selected_body["run"]["finished_at"].replace("Z", "+00:00")
        )
        historical_cutoff = started_at + (finished_at - started_at) / 2
        assert started_at <= historical_cutoff < finished_at
        historical_response = client.get(
            f"/api/v1/runs/{run_id}",
            params={"valid_at": historical_cutoff.isoformat()},
            headers=analyst_headers,
        )
        assert historical_response.status_code == 200, historical_response.text
        historical_body = historical_response.json()
        assert historical_response.headers["X-Temporal-Scope"] != "current"
        assert historical_body["run"]["status"] == "running"
        assert historical_body["run"]["finished_at"] is None
        assert "conditional_transport_candidate" not in historical_body["run"]
        assert _PROFILE_ID not in historical_response.text
        after_historical_audit = access_audit.scan_read_only().entries
        projected_event_count = sum(
            1
            for entry in after_historical_audit
            if entry.get("resource_id") == run_id
            and entry.get("resource_kind") == "runtime.run.conditional_transport_candidate"
            and entry.get("outcome") == "conditional_transport_candidate_projected"
        )
        previous_projected_event_count = sum(
            1
            for entry in before_historical_audit
            if entry.get("resource_id") == run_id
            and entry.get("resource_kind") == "runtime.run.conditional_transport_candidate"
            and entry.get("outcome") == "conditional_transport_candidate_projected"
        )
        assert projected_event_count == previous_projected_event_count

        before_finish_cutoff_audit = access_audit.scan_read_only().entries
        finished_cutoff_response = client.get(
            f"/api/v1/runs/{run_id}",
            params={"valid_at": finished_at.isoformat()},
            headers=analyst_headers,
        )
        assert finished_cutoff_response.status_code == 200, finished_cutoff_response.text
        finished_cutoff_body = finished_cutoff_response.json()
        assert finished_cutoff_response.headers["X-Temporal-Scope"] != "current"
        assert "conditional_transport_candidate" not in finished_cutoff_body["run"]
        assert _PROFILE_ID not in finished_cutoff_response.text
        after_finish_cutoff_audit = access_audit.scan_read_only().entries
        finished_cutoff_event_count = sum(
            1
            for entry in after_finish_cutoff_audit
            if entry.get("resource_id") == run_id
            and entry.get("resource_kind") == "runtime.run.conditional_transport_candidate"
            and entry.get("outcome") == "conditional_transport_candidate_projected"
        )
        before_finish_cutoff_event_count = sum(
            1
            for entry in before_finish_cutoff_audit
            if entry.get("resource_id") == run_id
            and entry.get("resource_kind") == "runtime.run.conditional_transport_candidate"
            and entry.get("outcome") == "conditional_transport_candidate_projected"
        )
        assert finished_cutoff_event_count == before_finish_cutoff_event_count

        viewer_response = client.get(
            f"/api/v1/runs/{run_id}",
            headers=viewer_headers,
        )
        assert viewer_response.status_code == 200, viewer_response.text
        viewer_body = viewer_response.json()
        assert "conditional_transport_candidate" not in viewer_body["run"]
        assert _PROFILE_ID not in viewer_response.text

        result_blob, _manifest_path = store._paths(selected_result_ref.artifact_id)
        original_result_bytes = result_blob.read_bytes()
        try:
            result_blob.write_bytes(original_result_bytes + b"tampered")
            tampered_response = client.get(
                f"/api/v1/runs/{run_id}",
                headers=analyst_headers,
            )
            assert tampered_response.status_code == 200, tampered_response.text
            assert "conditional_transport_candidate" not in tampered_response.json()["run"]
            assert _PROFILE_ID not in tampered_response.text
        finally:
            result_blob.write_bytes(original_result_bytes)

        tampered_policy_response = client.get(
            f"/api/v1/runs/{tampered_policy_run_id}",
            headers=analyst_headers,
        )
        assert tampered_policy_response.status_code == 200, tampered_policy_response.text
        tampered_projection = tampered_policy_response.json()["run"].get(
            "conditional_transport_candidate"
        )
        if tampered_projection is not None:
            assert tampered_projection["candidate_disposition"] == "unsupported"
            assert tampered_projection["completed_valid_member_count"] == 0
            assert tampered_projection["member_evaluation_count"] == 0
            assert tampered_projection["identified_member_fraction"] is None
            assert tampered_projection["identified_member_fraction_basis"] == (
                "selected_completed_valid_members"
            )
