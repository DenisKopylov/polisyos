"""Opt-in source-bound fixture for a browser-served configured candidate run."""

from __future__ import annotations

import asyncio
import base64
import http.client
import importlib
import json
import os
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
_V6_RUN_ID = "R_dashboard_source_bound_v6_partial_001"
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


def _capture_v6_partial(*, tmp_root: Path, cas_root: Path) -> tuple[object, object]:
    """Run the existing V6 producer test and retain its real partial result."""
    _ensure_import_roots()
    source_test = importlib.import_module(
        "tests.unit.runtime.quality.test_recursive_generation_cycle"
    )
    generation_test = importlib.import_module("tests.unit.runtime.quality.test_generation_cycle")
    horizon_test = importlib.import_module(
        "tests.unit.runtime.quality.test_joint_simulation_horizon"
    )
    recursive_module = importlib.import_module(
        "polisyos.runtime.quality.recursive_generation_cycle"
    )
    tenant_module = importlib.import_module("polisyos.core.security.tenant_context")
    original_tenant_scope = tenant_module.tenant_scope
    original_run = recursive_module.RecursiveGenerationCycleController.run
    captured: list[tuple[object, object]] = []

    def shared_owner_tenant_scope(*args: object, **kwargs: object) -> object:
        if kwargs.get("tenant_id") == "tenant-n5-owner":
            kwargs = {**kwargs, "tenant_id": _TENANT_ID, "cell_id": _CELL_ID}
        return original_tenant_scope(*args, **kwargs)

    def build_shared_ncm_store(
        _ignored_tmp_path: Path,
        *,
        schema_version: str = "1.0",
    ) -> tuple[object, object, str]:
        from polisyos.core.artifacts import ensure_ir_artifact_store
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.ir.analytics.ncm import persist_ncm_spec
        from polisyos.runtime.http.resilience import guard_runtime_cas

        store = guard_runtime_cas(FileSystemCAS(cas_root).with_ambient_ownership_enforcement())
        expected = horizon_test._ncm_with_cross_term()
        with original_tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
            ref = persist_ncm_spec(
                ensure_ir_artifact_store(store),
                expected,
                schema_version=schema_version,
            )
        return store, expected, str(ref.artifact_id)

    async def capture_run(self: object, *args: object, **kwargs: object) -> object:
        partial = await original_run(self, *args, **kwargs)
        captured.append((partial, kwargs.get("problems_by_node")))
        return partial

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(tenant_module, "tenant_scope", shared_owner_tenant_scope)
        monkeypatch.setattr(source_test, "tenant_scope", shared_owner_tenant_scope)
        monkeypatch.setattr(
            generation_test,
            "_runtime_ncm_fixture_store",
            build_shared_ncm_store,
        )
        monkeypatch.setattr(
            recursive_module.RecursiveGenerationCycleController,
            "run",
            capture_run,
        )
        asyncio.run(
            source_test.test_real_leaf_result_survives_later_independent_sibling_failure(
                tmp_root / "v6-producer-source",
                monkeypatch,
            )
        )

    if len(captured) != 1:
        raise RuntimeError("source_bound_v6_partial_capture_invalid")
    partial, problems_by_node = captured[0]
    if not isinstance(problems_by_node, dict):
        raise RuntimeError("source_bound_v6_problem_map_missing")
    root_problem = problems_by_node.get("design://root")
    if root_problem is None:
        raise RuntimeError("source_bound_v6_root_problem_missing")
    return partial, root_problem


def _seed_v6_partial_run(env: dict[str, object]) -> dict[str, str]:
    """Persist the V6 producer result under a fixture Core run for real GET projection."""
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo
    from polisyos.core.run.context import RunContext
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.adapters.core_run import (
        load_terminal_core_run_source,
    )
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleFailedNode,
    )

    app = env["app"]
    container = app.state.runtime_container
    runtime_context = container.runtime_api_context
    partial, root_problem = _capture_v6_partial(
        tmp_root=Path(env["cas_root"]).parent,
        cas_root=Path(env["cas_root"]),
    )
    partial_payload = partial.model_dump(mode="json", exclude={"leaf_nodes"})
    problem_payload = root_problem.model_dump(mode="json")
    compiled_payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_FAILED_PARTIAL_SCHEMA_VERSION,
        "design_problem_ref": gy_content_hash(problem_payload),
        "design_problem": problem_payload,
        "cycle_substrate_context_ref": None,
        "recursive_run": partial_payload,
    }
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        {
            **compiled_payload,
            "recursive_run": partial,
            "content_hash": gy_content_hash(compiled_payload),
        }
    )
    existing_core_run = runtime_context.run_index.get_run(str(env["core_run_id"]))
    if existing_core_run is None:
        raise RuntimeError("source_bound_v6_registry_source_run_missing")
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        core_run_source = load_terminal_core_run_source(
            store=runtime_context.store,
            core_runs_root=runtime_context.core_runs_root,
            run_id=str(env["core_run_id"]),
        )
    service = app.state._control_service
    compiled_ref = service._put_json_artifact_ref(
        compiled.model_dump(mode="json"),
        kind="runtime.compiled_recursive_generation_cycle",
        schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
        tenant_context=ArtifactTenantContextInfo(tenant_id=_TENANT_ID, cell_id=_CELL_ID),
    )
    with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
        fixture_run = RunContext.start(
            store=runtime_context.store,
            registry_bundle=core_run_source.manifest.registry_bundle,
            run_id=_V6_RUN_ID,
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
        fixture_run.add_output(compiled_ref)
        fixture_run.finalize(status="completed")
    runtime_context.run_index.refresh(force=True)

    failed_node = next(node for node in partial.nodes if isinstance(node, RecursiveCycleFailedNode))
    successful_result_ref = next(
        node.cycle_run.cycles[0].simulation.simulation_result_ref
        for node in partial.nodes
        if getattr(node, "cycle_run", None) is not None
        and node.cycle_run.cycles[0].simulation.simulation_result_ref is not None
    )
    return {
        "source_bound_v6_run_id": _V6_RUN_ID,
        "source_bound_v6_compiled_ref": str(compiled_ref.artifact_id),
        "source_bound_v6_partial_schema": str(partial.schema_version),
        "source_bound_v6_failure_code": str(failed_node.failure.error_code),
        "source_bound_v6_success_result_ref": str(successful_result_ref.artifact_id),
        "source_bound_v6_control_job_status": "not_established_fixture_run_wrapper",
        "source_bound_v6_source_test": (
            "tests/unit/runtime/quality/test_recursive_generation_cycle.py::"
            "test_real_leaf_result_survives_later_independent_sibling_failure"
        ),
        "source_bound_acquisition_history_status": "not_established",
        "source_bound_acquisition_history_reason": (
            "fixture V6 output has no production control-job or acquisition-action head"
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

        from polisyos.runtime.http.container import RuntimeContainerOverrides
        from polisyos.runtime.http.dependencies import build_runtime_api_context
        from polisyos.runtime.http.services.control import (
            generation_cycle as generation_cycle_service,
        )
        from tests._helpers.runtime_http import _DeterministicSpanSupportClient

        cas_root = tmp_root / ".polisyos"
        runtime_api_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
        )
        profile, declaration = _configured_procurement_profile(
            recorded_problem=recorded_problem,
            artifact_store=runtime_api_context.store,
            tenant_id=_TENANT_ID,
            cell_id=_CELL_ID,
        )
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
        env = build_runtime_api_env(
            tmp_root,
            include_test_client=False,
            app_kwargs={
                "catalog_run_profile": _CATALOG_PROFILE,
                "candidate_simulation_profiles": (profile,),
                "candidate_simulation_model_declarations": (declaration,),
                "container_overrides": RuntimeContainerOverrides(
                    runtime_api_context=runtime_api_context
                ),
            },
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
                "source_bound_fixture_boundaries": (
                    "controlled synthetic profile; development fixture identity; "
                    "no production claim"
                ),
            }
        )
        env.update(_seed_v6_partial_run(env))
        yield env
