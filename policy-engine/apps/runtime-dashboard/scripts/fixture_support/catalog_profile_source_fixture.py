"""Opt-in source-bound fixture for a browser-served configured candidate run."""

from __future__ import annotations

import asyncio
import base64
import http.client
import importlib
import json
import os
import sqlite3
import sys
import threading
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest

_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL_ID = "cell-a"
_SOURCE_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
_CATALOG_PROFILE = "prod_full"
_CONFLICTING_CATALOG_PROFILE = "catalog_refresh"


class _MissingUsageGatewayProxy:
    """Pass a controlled local gateway response through without usage telemetry."""

    def __init__(self, upstream_url: str) -> None:
        parsed = urlsplit(upstream_url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
            raise ValueError("source_bound_gateway_must_use_local_http")
        self._upstream_host = f"{parsed.hostname}:{parsed.port}"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self._forward("GET")

            def do_POST(self) -> None:
                self._forward("POST")

            def _forward(self, method: str) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                headers = {
                    key: value
                    for key, value in self.headers.items()
                    if key.lower() not in {"connection", "content-length", "host"}
                }
                connection = http.client.HTTPConnection(owner._upstream_host, timeout=20)
                try:
                    connection.request(method, self.path, body=body or None, headers=headers)
                    response = connection.getresponse()
                    status = response.status
                    response_headers = response.getheaders()
                    response_body = response.read()
                finally:
                    connection.close()

                if method == "POST" and status == 200:
                    try:
                        payload = json.loads(response_body)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        payload = None
                    if isinstance(payload, dict):
                        payload.pop("usage", None)
                        response_body = json.dumps(
                            payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")

                self.send_response(status)
                for key, value in response_headers:
                    if key.lower() not in {
                        "connection",
                        "content-length",
                        "transfer-encoding",
                    }:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(response_body)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """Return this local proxy's OpenAI-compatible API root."""
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    def __enter__(self) -> _MissingUsageGatewayProxy:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _ensure_import_roots() -> Path:
    policy_engine_root = Path(__file__).resolve().parents[4]
    for root in (policy_engine_root / "src", policy_engine_root, policy_engine_root / "tests"):
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
    return policy_engine_root


def _restore_environment(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _seed_profile_qualified_inspector_views(env: dict[str, object]) -> dict[str, str]:
    """Persist two same-byte views with test-only dashboard display scope."""
    import hashlib

    from _helpers.runtime_http import (
        _put_fixture_authority_envelope,
        _record_fixture_owner,
        _runtime_fixture_authority_boundary,
    )

    from polisyos.core.artifacts import PutOptions, SchemaInfo
    from polisyos.core.artifacts.manifest import ArtifactAuthorityInfo, ProducerInfo
    from polisyos.core.canon import to_canonical_bytes
    from polisyos.core.security.tenant_context import tenant_scope

    app = env["app"]
    container = app.state.runtime_container
    runtime_context = container.runtime_api_context
    store = runtime_context.store
    payload = {
        "fixture": "source_bound_profile_inspector",
        "marker": "same-bytes-across-profile-views",
    }
    payload_bytes = to_canonical_bytes(payload)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    payload_ref = f"sha256:{payload_sha256}"
    producer = ProducerInfo(
        component="polisyos.tests.runtime_api_env",
        version="profile-qualified-inspector-v1",
    )
    refs = []
    envelope_refs = []
    for role in ("primary", "sibling"):
        kind = f"test.dashboard_profile_inspector.{role}"
        boundary = {
            **_runtime_fixture_authority_boundary(
                boundary_id=f"boundary-dashboard-profile-inspector-{role}"
            ),
            "authoritative_for": ["runtime_closeout_authority", "dashboard_display"],
            "may_not_use_for": ["claim_authority", "publication", "promotion"],
            "known_limits": ["controlled_test_fixture_only", "no_production_claim"],
            "subject_ref": payload_ref,
            "subject_kind": kind,
        }
        with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
            envelope_ref = _put_fixture_authority_envelope(
                store,
                boundary,
                producer_version="profile-qualified-inspector-v1",
            )
            ref = store.put_json(
                payload,
                PutOptions(
                    kind=kind,
                    media_type="application/json",
                    schema=SchemaInfo(
                        name=f"test.dashboard_profile_inspector.{role}",
                        version="1",
                    ),
                    producer=producer,
                    authority=ArtifactAuthorityInfo(
                        authority_envelope_ref=str(envelope_ref.artifact_id),
                        authority_envelope_manifest_profile_sha256=(
                            envelope_ref.manifest_profile_sha256
                        ),
                        diagnostic_event_ref=(f"event://tests/dashboard/profile-inspector/{role}"),
                        manifest_ref=f"cas-manifest://{payload_ref}",
                        payload_sha256=payload_sha256,
                    ),
                ),
                return_selected_profile=True,
            )
            refs.append(ref)
            envelope_refs.append(envelope_ref)

    primary, sibling = refs
    if (
        primary.artifact_id != sibling.artifact_id
        or primary.manifest_profile_sha256 is None
        or sibling.manifest_profile_sha256 is None
        or primary.manifest_profile_sha256 == sibling.manifest_profile_sha256
    ):
        raise RuntimeError("profile_inspector_fixture_views_are_not_distinct")
    _record_fixture_owner(
        store,
        *envelope_refs,
        *refs,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        runtime_api_env=env,
    )
    return {
        "source_bound_profile_inspector_artifact_id": str(primary.artifact_id),
        "source_bound_profile_inspector_primary_kind": primary.kind,
        "source_bound_profile_inspector_primary_media_type": primary.media_type,
        "source_bound_profile_inspector_primary_profile": str(primary.manifest_profile_sha256),
        "source_bound_profile_inspector_sibling_kind": sibling.kind,
        "source_bound_profile_inspector_sibling_media_type": sibling.media_type,
        "source_bound_profile_inspector_sibling_profile": str(sibling.manifest_profile_sha256),
        "source_bound_profile_inspector_authority_scope": (
            "controlled_fixture_runtime_inspector_and_dashboard_only_no_publication_claim"
        ),
    }


def _seed_profiled_workflow_data_view_request(
    env: dict[str, object],
    tmp_root: Path,
    stack: ExitStack,
) -> dict[str, str]:
    """Persist a typed request and local SQL source for the ordinary-POST browser path."""
    from _helpers.runtime_http import _record_fixture_owner

    from polisyos.core.artifacts import profile_bound_ref
    from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.contracts.fabric import DataViewRequestRef
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
    from polisyos.foundry._internal.quickstart import (
        build_trivial_trinity_bundle,
        put_trivial_trinity_bundle,
    )
    from polisyos.ir.model_layer.queries import DataViewRequest

    database = tmp_root / "workflow-profile-input.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE policy_inputs (metric TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO policy_inputs VALUES (?)",
            ("controlled-profile-selection",),
        )

    connector_registry = ConnectorRegistry()
    connector_registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{database}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )
    stack.callback(connector_registry.shutdown)
    fabric_api = importlib.import_module("polisyos.fabric.api")
    stack.enter_context(
        patch.object(
            fabric_api,
            "_default_connector_registry",
            lambda: connector_registry,
        )
    )

    runtime_context = env["app"].state.runtime_container.runtime_api_context
    store = runtime_context.store
    request = DataViewRequest(
        schema_version="1.0",
        request_id="dashboard-ordinary-post-profile-selection",
        view_type="table",
        metrics=["policy_inputs"],
    )
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        request_payload_ref = store.put_json(
            request,
            ArtifactWriteOptions(
                kind="ir.data_view_request",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.DataViewRequest",
                    version="1.0",
                ),
                producer=ProducerInfo(
                    component="polisyos.tests.runtime_dashboard.ordinary_post_profile_fixture",
                    version="1",
                ),
            ),
        )
        selected_request_ref = DataViewRequestRef.model_validate(
            profile_bound_ref(store, request_payload_ref).model_dump(mode="json")
        )
        registry_bundle_ref = build_default_registry_bundle(store).bundle_ref
        trinity_ref = put_trivial_trinity_bundle(
            store,
            build_trivial_trinity_bundle(str(registry_bundle_ref.artifact_id)),
        )
    _record_fixture_owner(
        store,
        selected_request_ref,
        trinity_ref,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        runtime_api_env=env,
    )
    profile = selected_request_ref.manifest_profile_sha256
    if profile is None:
        raise RuntimeError("workflow_profile_fixture_lacks_selected_manifest_profile")
    return {
        "source_bound_workflow_data_view_request_artifact_id": str(
            selected_request_ref.artifact_id
        ),
        "source_bound_workflow_data_view_request_profile": profile,
        "source_bound_workflow_trinity_bundle_ref": str(trinity_ref.artifact_id),
        "source_bound_workflow_profile_fixture_boundary": (
            "controlled local SQLite source and fixture CAS request; "
            "no production or currentness claim"
        ),
    }


@contextmanager
def source_bound_catalog_profile_fixture(tmp_root: Path) -> Iterator[dict[str, object]]:
    """Serve a real configured candidate producer under an explicit test identity."""
    _ensure_import_roots()
    from tests._helpers.controlled_candidate_profile import (
        ControlledCandidateGateway,
        _configured_procurement_profile,
        _controlled_procurement_recording,
        _current_compiler_problem,
    )
    from tools.quality.validation import check_layer3_gy_design_generation_contract as n4_contract

    policy_engine_root = Path(__file__).resolve().parents[4]
    environment = {
        "JAX_PLATFORMS": "cpu",
        "OMP_NUM_THREADS": "1",
        "POLISYOS_CACHE_HOME": str(tmp_root / "runtime-cache"),
        "POLISYOS_CONTROL_SQLITE_PATH": str(tmp_root / "control.sqlite3"),
        "POLISYOS_CONTROL_STATE_STORE_BACKEND": "sqlite",
        "POLISYOS_CONTROL_WORKER_BACKEND": "embedded",
        "POLISYOS_EXECUTION_PROFILE": "dev",
        "POLISYOS_LLM_CACHE_MAXSIZE": "0",
        "POLISYOS_LLM_CACHE_TTL_S": "0",
        "POLISYOS_LLM_GATEWAY_API_KEY": "sk-source-bound-local-fixture-key",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "0",
        "POLISYOS_LLM_PROMPT_SANITIZER": "false",
        "POLISYOS_LLM_SIMULATION_MODE": "0",
    }

    with ExitStack() as stack:
        gateway = stack.enter_context(ControlledCandidateGateway())
        gateway_proxy = stack.enter_context(_MissingUsageGatewayProxy(gateway.base_url))
        environment["POLISYOS_LLM_GATEWAY_BASE_URL"] = gateway_proxy.base_url
        previous_environment = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        stack.callback(_restore_environment, previous_environment)

        recording = next(
            item
            for item in n4_contract._load_recordings(policy_engine_root)
            if item.get("design_problem_id") == _SOURCE_RECORDING_ID
        )
        original_problem = _current_compiler_problem(recording)
        controlled_recording = _controlled_procurement_recording(
            recording,
            outcome_variable=original_problem.outcome_of_interest.target_variable,
        )
        recorded_problem = _current_compiler_problem(controlled_recording)
        gateway.set_fixture(controlled_recording, problem=recorded_problem)

        from fastapi.testclient import TestClient

        from polisyos.runtime.http.app import create_runtime_api_app
        from polisyos.runtime.http.container import RuntimeContainerOverrides
        from polisyos.runtime.http.dependencies import build_runtime_api_context
        from polisyos.runtime.http.services.control import (
            generation_cycle as generation_cycle_service,
        )
        from tests._helpers.generic_n4_served_replay import (
            prepare_generic_n4_served_replay,
            run_n4_budget_stop_worker_and_get,
            run_n4_control_worker_and_get,
        )
        from tests._helpers.runtime_http import _DeterministicSpanSupportClient

        cas_root = tmp_root / ".polisyos"
        runtime_api_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
        )
        from polisyos.runtime.quality.substrate_registry import resolve_catalog_serving_source

        selected_catalog_serving_source = resolve_catalog_serving_source(
            policy_engine_root,
            selection=None,
            requested_profile=_CATALOG_PROFILE,
        )
        v6_monkeypatch = pytest.MonkeyPatch()
        try:
            prepared_v6 = asyncio.run(
                prepare_generic_n4_served_replay(
                    tmp_path=tmp_root / "v6-served-replay",
                    controlled_candidate_gateway=gateway,
                    monkeypatch=v6_monkeypatch,
                    tenant_id=_TENANT_ID,
                    cell_id=_CELL_ID,
                    recording_id=_SOURCE_RECORDING_ID,
                    runtime_api_context=runtime_api_context,
                    catalog_serving_source=selected_catalog_serving_source,
                )
            )
            if prepared_v6.runtime_api_context is not runtime_api_context:
                raise RuntimeError("source_bound_v6_runtime_context_was_replaced")
            if (
                prepared_v6.app_kwargs["container_overrides"].runtime_api_context
                is not runtime_api_context
            ):
                raise RuntimeError("source_bound_v6_app_context_does_not_match")

            selected_source_profile = prepared_v6.selected_source_profile
            selected_skg_source = prepared_v6.selected_skg_source
            selected_skg_snapshot_ref = selected_skg_source.snapshot_ref
            selected_skg_snapshot_sha256 = selected_skg_source.sha256
            source_profile_content_hash = selected_source_profile.content_hash
            if (
                selected_source_profile.skg_causal_prior_ref != prepared_v6.selected_source_ref
                or selected_source_profile.source_snapshot_ref != selected_skg_snapshot_ref
                or prepared_v6.selected_source_ref.skg_snapshot_ref != selected_skg_snapshot_ref
                or selected_source_profile.source_snapshot_sha256 != selected_skg_snapshot_sha256
                or not source_profile_content_hash
            ):
                raise RuntimeError("source_bound_v6_selected_source_identity_mismatch")

            v6_app = create_runtime_api_app(**prepared_v6.app_kwargs)
            with TestClient(v6_app) as v6_client:
                v6_receipt = asyncio.run(
                    run_n4_control_worker_and_get(
                        client=v6_client,
                        app=v6_app,
                        prepared=prepared_v6,
                        monkeypatch=v6_monkeypatch,
                        expected_failure_code="v6_controlled_second_n4_child_failure",
                        exercise_projection_controls=True,
                    )
                )
                v7_receipt = asyncio.run(
                    run_n4_budget_stop_worker_and_get(
                        client=v6_client,
                        app=v6_app,
                        prepared=prepared_v6,
                    )
                )
        finally:
            v6_monkeypatch.undo()

        # TestClient shutdown closes the guarded store owned by the producer app.
        # Reopen the same CAS root for fixture profile writes and browser readback.
        serving_runtime_api_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
        )
        serving_runtime_api_context.run_index.refresh(force=True)
        if serving_runtime_api_context.run_index.get_run(v7_receipt.run_id) is None:
            raise RuntimeError("source_bound_v7_reopened_run_index_missing")
        from tests._helpers.same_candidate_history_fixture import (
            build_same_candidate_history_fixture,
        )

        same_candidate_history = build_same_candidate_history_fixture(
            fixture_root=tmp_root / "same-candidate-history",
            cas_root=cas_root,
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
        serving_runtime_api_context.run_index.refresh(force=True)
        if serving_runtime_api_context.run_index.get_run(same_candidate_history["run_id"]) is None:
            raise RuntimeError("source_bound_same_candidate_reopened_run_index_missing")
        gateway.set_fixture(controlled_recording, problem=recorded_problem)
        profile, declaration = _configured_procurement_profile(
            recorded_problem=recorded_problem,
            artifact_store=serving_runtime_api_context.store,
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
        v6_projection = v6_receipt.projection
        if (
            v6_receipt.job_state != "completed"
            or v6_receipt.failure_code != "v6_controlled_second_n4_child_failure"
            or not v6_receipt.failure_message
            or v6_projection.get("artifact_status") != "resolved"
            or v6_projection.get("publication_authority") is not False
            or v6_projection.get("currentness_status") != "not_established"
            or v6_projection.get("child_profile_status") != "resolved"
        ):
            raise RuntimeError("source_bound_v6_served_projection_incomplete")
        v6_observations = v6_projection.get("n5_observations")
        successful_v6_observation = (
            next(
                (
                    row
                    for row in v6_observations
                    if isinstance(row, dict) and row.get("status") == "joint_simulated"
                ),
                None,
            )
            if isinstance(v6_observations, list)
            else None
        )
        if not isinstance(successful_v6_observation, dict):
            raise RuntimeError("source_bound_v6_n5_observation_missing")
        successful_v6_ref = successful_v6_observation.get("simulation_result_ref")
        if not isinstance(successful_v6_ref, dict) or successful_v6_ref.get("artifact_id") != str(
            v6_receipt.n5_result_ref.artifact_id
        ):
            raise RuntimeError("source_bound_v6_n5_reference_mismatch")
        if (
            v6_receipt.checkpoint.get("status") != "partial"
            or v6_receipt.checkpoint.get("publication_authority") is not False
            or not any(
                isinstance(row, dict)
                and row.get("error_code") == v6_receipt.failure_code
                and row.get("error_message") == v6_receipt.failure_message
                for row in v6_receipt.checkpoint.get("failed_branches", [])
            )
        ):
            raise RuntimeError("source_bound_v6_sibling_failure_not_reconciled")
        v7_projection = v7_receipt.projection
        v7_checkpoint = v7_receipt.checkpoint
        v7_budget_stop_ref = v7_checkpoint.get("budget_stop_node_ref")
        v7_pending_frontier = v7_checkpoint.get("pending_frontier")
        v7_completed_refs = v7_checkpoint.get("completed_design_refs")
        v7_leaf_terminals = v7_checkpoint.get("leaf_terminal_kinds")
        if (
            v7_receipt.job_state != "completed"
            or v7_projection.get("child_profile_status") != "resolved"
            or v7_projection.get("publication_authority") is not False
            or v7_projection.get("currentness_status") != "not_established"
            or len(v7_receipt.child_node_refs) != 2
            or v7_checkpoint.get("schema_version")
            != "policyos.runtime.recursive_cycle_checkpoint.v1"
            or v7_checkpoint.get("status") != "partial"
            or v7_checkpoint.get("publication_authority") is not False
            or v7_checkpoint.get("root_n9_status") != "not_run"
            or v7_checkpoint.get("failed_branches") != []
            or not isinstance(v7_budget_stop_ref, str)
            or v7_budget_stop_ref not in v7_receipt.child_node_refs
            or set(v7_pending_frontier or ())
            != set(v7_receipt.child_node_refs) - {v7_budget_stop_ref}
            or v7_budget_stop_ref not in set(v7_completed_refs or ())
            or not isinstance(v7_leaf_terminals, dict)
            or v7_leaf_terminals.get(v7_budget_stop_ref) != "budget_exhausted"
        ):
            raise RuntimeError("source_bound_v7_budget_frontier_not_reconciled")
        original_compiler = generation_cycle_service.build_design_problem_from_nl_request

        async def compile_with_controlled_span_support(**kwargs: object) -> object:
            kwargs["span_support_client"] = _DeterministicSpanSupportClient()
            return await original_compiler(**kwargs)

        stack.enter_context(
            patch.object(
                generation_cycle_service,
                "build_design_problem_from_nl_request",
                compile_with_controlled_span_support,
            )
        )

        from _helpers.runtime_http import build_runtime_api_env

        from tests._helpers.runtime_http import _valid_intake_for_mode

        request_body = {
            "request": recorded_problem.nl_provenance.raw_request,
            "llm_model": str(recording["model_id"]),
            "context": {
                "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                    mode="json"
                )
            },
        }
        serving_app_kwargs = {
            key: value
            for key, value in prepared_v6.app_kwargs.items()
            if key not in {"cas_root", "core_runs_root"}
        }
        serving_app_kwargs.update(
            {
                "catalog_run_profile": _CATALOG_PROFILE,
                "candidate_simulation_profiles": (profile,),
                "candidate_simulation_model_declarations": (declaration,),
                "container_overrides": RuntimeContainerOverrides(
                    runtime_api_context=serving_runtime_api_context
                ),
            }
        )
        env = build_runtime_api_env(
            tmp_root,
            include_test_client=False,
            app_kwargs=serving_app_kwargs,
        )
        env.update(
            {
                "source_bound_fixture": "1",
                "source_bound_fixture_identity": (
                    f"DevelopmentFixtureIdentityMiddleware:fixture-analyst:{_TENANT_ID}:{_CELL_ID}"
                ),
                "source_bound_catalog_configured_profile": _CATALOG_PROFILE,
                "source_bound_catalog_conflict_profile": _CONFLICTING_CATALOG_PROFILE,
                "source_bound_v1_model_id": str(recording["model_id"]),
                "source_bound_v1_recording_id": str(controlled_recording["recording_id"]),
                "source_bound_v1_source_test": (
                    "tests/integration/runtime_quality/"
                    "test_configured_candidate_simulation_served.py::"
                    "test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift"
                ),
                "source_bound_v1_request_json_base64": base64.b64encode(
                    json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).decode("ascii"),
                "source_bound_cost_source": (
                    "controlled local gateway response without usage -> TracedLLMClient -> "
                    "durable BudgetMiddleware settlement ledger"
                ),
                "source_bound_cost_scope": "real_traced_producer_unknown_cost_not_manual_event",
                "source_bound_v6_run_id": v6_receipt.run_id,
                "source_bound_v6_control_job_id": v6_receipt.job_id,
                "source_bound_v6_control_job_status": v6_receipt.job_state,
                "source_bound_v6_failure_code": v6_receipt.failure_code,
                "source_bound_v6_failure_message": v6_receipt.failure_message,
                "source_bound_v6_success_result_ref": str(v6_receipt.n5_result_ref.artifact_id),
                "source_bound_v6_source_profile_content_hash": source_profile_content_hash,
                "source_bound_v6_selected_skg_snapshot_ref": selected_skg_snapshot_ref,
                "source_bound_v6_selected_skg_snapshot_sha256": selected_skg_snapshot_sha256,
                "source_bound_v6_child_count": str(len(prepared_v6.child_keys)),
                "source_bound_v6_missing_result_ref_error_code": (
                    v6_receipt.missing_result_ref_error_code
                ),
                "source_bound_v6_source_test": (
                    "tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py::"
                    "test_served_real_n4_children_keep_first_n5_after_later_sibling_failure"
                ),
                "source_bound_v6_fixture_boundary": (
                    "controlled local ordinary POST, worker, CAS and fresh GET; "
                    "candidate-only with no production currentness or authority claim"
                ),
                "source_bound_same_candidate_run_id": same_candidate_history["run_id"],
                "source_bound_same_candidate_candidate_id": same_candidate_history["candidate_id"],
                "source_bound_same_candidate_source_test": (
                    "tests/integration/core_runtime/test_acquisition_authority_served.py::"
                    "test_served_acquisition_selects_committed_human_authority_and_reopens_worker"
                ),
                "source_bound_same_candidate_fixture_boundary": (
                    "controlled local ordinary request and worker; existing local test issuer "
                    "signs the test receipt and the test verifier reconciles it; same admitted "
                    "source and root profile persist in the shared CAS and are read by fresh GET; "
                    "test-only, with no external issuer, production authority, currentness, "
                    "or publication claim"
                ),
                "source_bound_v7_run_id": v7_receipt.run_id,
                "source_bound_v7_control_job_id": v7_receipt.job_id,
                "source_bound_v7_control_job_status": v7_receipt.job_state,
                "source_bound_v7_budget_stop_node_ref": str(v7_budget_stop_ref),
                "source_bound_v7_child_count": str(len(v7_receipt.child_node_refs)),
                "source_bound_v7_source_test": (
                    "tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py::"
                    "test_served_real_n4_children_keep_first_n5_after_later_sibling_failure"
                ),
                "source_bound_v7_fixture_boundary": (
                    "controlled ordinary POST with run_budget_usd=0, real N6 owner, worker, "
                    "persisted checkpoint and reopened CAS; candidate-only, no production "
                    "currentness or authority claim"
                ),
                "source_bound_fixture_boundaries": (
                    "controlled synthetic profile; development fixture identity; "
                    "no production claim"
                ),
            }
        )
        env.update(_seed_profile_qualified_inspector_views(env))
        env.update(_seed_profiled_workflow_data_view_request(env, tmp_root, stack))
        yield env
