from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from typing import Any, get_args

import pytest

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.contracts.capability_discovery import CapabilityDiscoveryResponse
from polisyos.core.contracts.control import EpochValidityBatchResponse
from polisyos.core.contracts.runtime import EpochStalenessProjectionResponse
from polisyos.pdc import DecisionGrade, RunBoundDesignRecordBinding
from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteProjection,
)
from polisyos.runtime.http.services.cycle_board_contracts import (
    CYCLE_BOARD_PROJECTION_RULE_VERSION,
    CYCLE_BOARD_STABLE_ADDRESS,
    CycleBoardProjectionPacket,
)
from polisyos.runtime.http.services.cycle_board_projection import (
    _GOVERNED_COMPONENT_ORDER,
    _manifest_hash_material,
)
from polisyos.runtime.http.services.cycle_board_sources import N13B_DENIED_ROW_USES
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.governed_projections import GovernedProjectionService
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionCreateResponse,
    HumanDecisionGateResponse,
    HumanDecisionReviewEffectivenessResponse,
)
from polisyos.runtime.http.services.run_paper_contracts import (
    RunPaperDesignRecordBinding,
    RunPaperPacket,
    build_run_paper_semantic_projection,
)
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import HumanDecisionRecord
from tools.ops_runners.runtime import generate_runtime_client

OPENAPI_TYPESCRIPT_VERSION = "7.13.0"


def test_openapi_contract_includes_examples_and_problem_payloads() -> None:
    schema = export_runtime_openapi_schema()
    violations = validate_runtime_openapi_contract(schema)
    assert violations == []


def test_runtime_api_problem_keeps_nested_diagnostics_separate_from_envelope() -> None:
    """The runtime model, OpenAPI schema, and emitter agree on nested JSON keys."""

    from jsonschema import Draft202012Validator
    from pydantic import ValidationError
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    from polisyos.core.contracts.runtime import RuntimeApiProblem
    from polisyos.runtime.http.errors import problem_response

    base = {
        "title": "Conflict",
        "detail": "Selected data conflicts",
        "code": "outer-code",
        "status": 409,
        "status_code": 409,
    }
    extensions = {
        "code": "diagnostic-code",
        "status": "diagnostic-status",
        "status_code": [409, 422],
        "error": None,
        "context": {"run_id": "diagnostic-only"},
        "extensions": {"code": "deeper-diagnostic"},
    }
    nested = RuntimeApiProblem.model_validate(
        {**base, "context": {"run_id": "R1"}, "extensions": extensions},
        strict=True,
    )
    assert nested.context is not None and nested.context.run_id == "R1"
    assert nested.extensions == extensions
    assert nested.code == "outer-code"
    assert nested.status == nested.status_code == 409

    snapshot = export_runtime_openapi_schema()
    openapi_uri = "https://policyos.example/runtime-api/openapi.json"
    registry = Registry().with_resource(
        openapi_uri,
        Resource.from_contents(snapshot, default_specification=DRAFT202012),
    )
    schema_validator = Draft202012Validator(
        {"$ref": f"{openapi_uri}#/components/schemas/RuntimeApiProblem"},
        registry=registry,
    )
    schema_validator.validate(nested.model_dump(mode="json"))
    assert not schema_validator.is_valid({**nested.model_dump(mode="json"), "unmodeled": "refuse"})
    with pytest.raises(ValidationError):
        RuntimeApiProblem.model_validate({**base, "unmodeled": "refuse"}, strict=True)
    with pytest.raises(ValidationError):
        RuntimeApiProblem.model_validate(
            {**base, "extensions": {"diagnostic": float("nan")}},
            strict=True,
        )

    response = problem_response(
        status_code=409,
        code="outer-code",
        detail="Selected data conflicts",
        request_id="req_nested_extensions",
        extensions=extensions,
    )
    emitted = RuntimeApiProblem.model_validate_json(response.body, strict=True)
    schema_validator.validate(json.loads(response.body))
    assert emitted.code == "outer-code"
    assert emitted.status == emitted.status_code == response.status_code == 409
    assert emitted.extensions == extensions


def test_artifact_resolver_and_batch_problem_openapi_matches_runtime_serializer(
    runtime_api_env, monkeypatch
) -> None:
    """Resolver and batch problem responses match the runtime serializer and model."""
    import ast
    import inspect
    from copy import deepcopy

    from polisyos.core.contracts.runtime import RuntimeApiProblem
    from polisyos.runtime.http._openapi_contract_helpers import (
        iter_openapi_operations,
        runtime_problem_example,
    )
    from polisyos.runtime.http.errors import problem_response
    from polisyos.runtime.http.routes import artifacts as artifact_routes

    media = "application/problem+json"
    ref = "#/components/schemas/RuntimeApiProblem"
    module_tree = ast.parse(inspect.getsource(artifact_routes))
    module_functions = {
        node.name: node
        for node in ast.walk(module_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    class _FunctionCalls(ast.NodeVisitor):
        def __init__(self, root: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self.root = root
            self.names: set[str] = set()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is self.root:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is self.root:
                self.generic_visit(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name):
                self.names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                self.names.add(node.func.attr)
            self.generic_visit(node)

    def reaches_resolver(function_name: str, visited: set[str]) -> bool:
        if function_name in visited:
            return False
        visited.add(function_name)
        function = module_functions.get(function_name)
        if function is None:
            return False
        calls = _FunctionCalls(function)
        calls.visit(function)
        return (
            "_resolve_artifact_manifest" in calls.names
            or "_resolve_selected_artifact_manifest" in calls.names
            or any(
                callee in module_functions and reaches_resolver(callee, visited)
                for callee in calls.names
            )
        )

    resolver_ids: set[str] = set()
    for route in artifact_routes.router.routes:
        endpoint = getattr(route, "endpoint", None)
        operation_id = getattr(route, "operation_id", None)
        endpoint_name = getattr(endpoint, "__name__", None)
        if isinstance(endpoint_name, str) and reaches_resolver(endpoint_name, set()):
            assert isinstance(operation_id, str)
            resolver_ids.add(operation_id)
    assert resolver_ids, "the router must expose at least one artifact resolver consumer"
    schema = export_runtime_openapi_schema(app=runtime_api_env["app"])
    live = {
        op.get("operationId"): op
        for _, _, op in iter_openapi_operations(schema)
        if isinstance(op.get("operationId"), str)
    }

    def assert_problem_response(operation_id: str, operation: dict[str, Any]) -> set[str]:
        responses = operation.get("responses")
        assert isinstance(responses, dict), f"{operation_id}: resolver responses are missing"
        response = responses.get("409")
        assert isinstance(response, dict), f"{operation_id}: missing or invalid 409 response"
        content = response.get("content")
        assert isinstance(content, dict), f"{operation_id}: 409 response content is missing"
        assert content.keys() == {media}, f"{operation_id}: 409 response media mismatch"
        payload = content.get(media)
        assert isinstance(payload, dict), f"{operation_id}: problem response payload is invalid"
        assert payload.get("schema") == {"$ref": ref}, (
            f"{operation_id}: 409 response schema mismatch"
        )
        values = [payload["example"]] if "example" in payload else []
        values.extend(
            item["value"]
            for item in payload.get("examples", {}).values()
            if isinstance(item, dict) and "value" in item
        )
        assert values, f"{operation_id}: problem response example is missing"
        codes: set[str] = set()
        for value in values:
            problem = RuntimeApiProblem.model_validate(value, strict=True)
            assert problem.status == problem.status_code == 409
            codes.add(problem.code)
        return codes

    def assert_routes(candidate: dict[str, Any]) -> set[str]:
        operations = {
            op.get("operationId"): op
            for _, _, op in iter_openapi_operations(candidate)
            if isinstance(op.get("operationId"), str)
        }
        assert resolver_ids <= operations.keys(), "resolver operation is missing"
        for operation_id in resolver_ids:
            operation = operations.get(operation_id)
            assert isinstance(operation, dict), f"{operation_id}: resolver operation is invalid"
            assert_problem_response(operation_id, operation)
        batch = operations.get("get_artifact_batch")
        assert isinstance(batch, dict), "batch operation is missing"
        batch_codes = assert_problem_response("get_artifact_batch", batch)
        assert {
            "artifact_batch_manifest_read_budget_exceeded",
            "artifact_batch_manifest_read_usage_unavailable",
            "authority_surface_admission_blocked",
        } <= batch_codes, "get_artifact_batch: missing representative 409 problem examples"
        return batch_codes

    batch_codes = assert_routes(schema)

    original_budget_factory = artifact_routes._new_artifact_batch_manifest_read_budget

    def one_byte_budget(requested_id_count: int):
        budget = original_budget_factory(requested_id_count)
        budget.limit_source_bytes = 1
        return budget

    monkeypatch.setattr(
        artifact_routes,
        "_new_artifact_batch_manifest_read_budget",
        one_byte_budget,
    )
    batch_response = runtime_api_env["client"].post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [str(runtime_api_env["decision_packet_artifact_id"])]},
    )
    assert batch_response.status_code == 409, batch_response.text
    assert batch_response.headers["content-type"].startswith(media)
    actual_batch_problem = RuntimeApiProblem.model_validate(batch_response.json(), strict=True)
    assert actual_batch_problem.code in {
        "artifact_batch_manifest_read_budget_exceeded",
        "artifact_batch_manifest_read_usage_unavailable",
    }
    assert actual_batch_problem.code in batch_codes

    model_schema = RuntimeApiProblem.model_json_schema(ref_template="#/components/schemas/{model}")
    model_defs = model_schema.pop("$defs", {})
    components = schema["components"]["schemas"]
    assert components["RuntimeApiProblem"] == model_schema
    for name, definition in model_defs.items():
        assert components[name] == definition
    response = problem_response(
        status_code=409,
        code="artifact_integrity_failed",
        detail="The selected artifact failed CAS integrity verification.",
        request_id="req_r193_problem_contract",
        instance="/api/v1/artifacts/sha256:abc",
    )
    assert response.status_code == 409
    assert response.media_type == media
    actual = RuntimeApiProblem.model_validate_json(response.body, strict=True)
    assert actual.status == actual.status_code == 409
    assert actual.code == "artifact_integrity_failed"

    future = deepcopy(schema)
    operation_id = next(iter(sorted(resolver_ids)))
    original_op = live[operation_id]
    path = next(path for path, _, op in iter_openapi_operations(schema) if op is original_op)
    op = next(
        op
        for candidate_path, _, op in iter_openapi_operations(future)
        if candidate_path == path and op.get("operationId") == operation_id
    )
    op["responses"]["418"] = {
        "description": "A future typed problem response.",
        "content": {
            media: {
                "schema": {"$ref": ref},
                "examples": {
                    "future": {
                        "value": runtime_problem_example(
                            status_code=418,
                            code="future_route_problem",
                            path=path,
                            request_id="req_future_problem",
                        )
                    }
                },
            }
        },
    }
    assert validate_runtime_openapi_contract(future) == []

    bad_media = deepcopy(schema)
    response = next(
        op["responses"]["409"]
        for _, _, op in iter_openapi_operations(bad_media)
        if op.get("operationId") in resolver_ids
    )
    payload = response["content"].pop(media)
    response["content"]["application/json"] = payload
    assert validate_runtime_openapi_contract(bad_media)
    with pytest.raises(AssertionError, match="409 response media mismatch"):
        assert_routes(bad_media)

    bad_ref = deepcopy(schema)
    response = next(
        op["responses"]["409"]
        for _, _, op in iter_openapi_operations(bad_ref)
        if op.get("operationId") in resolver_ids
    )
    response["content"][media]["schema"]["$ref"] = "#/components/schemas/ArtifactManifestResponse"
    assert validate_runtime_openapi_contract(bad_ref)
    with pytest.raises(AssertionError, match="409 response schema mismatch"):
        assert_routes(bad_ref)

    missing = deepcopy(schema)
    op = next(
        op for _, _, op in iter_openapi_operations(missing) if op.get("operationId") in resolver_ids
    )
    del op["responses"]["409"]
    with pytest.raises(AssertionError, match="missing or invalid 409 response"):
        assert_routes(missing)

    malformed = deepcopy(schema)
    op = next(
        op
        for _, _, op in iter_openapi_operations(malformed)
        if op.get("operationId") in resolver_ids
    )
    op["responses"]["409"] = None
    with pytest.raises(AssertionError, match="missing or invalid 409 response"):
        assert_routes(malformed)

    batch_without_problem = deepcopy(schema)
    batch_op = next(
        op
        for _, _, op in iter_openapi_operations(batch_without_problem)
        if op.get("operationId") == "get_artifact_batch"
    )
    del batch_op["responses"]["409"]
    with pytest.raises(AssertionError, match="get_artifact_batch: missing or invalid 409 response"):
        assert_routes(batch_without_problem)

    batch_with_wrong_example_code = deepcopy(schema)
    batch_op = next(
        op
        for _, _, op in iter_openapi_operations(batch_with_wrong_example_code)
        if op.get("operationId") == "get_artifact_batch"
    )
    batch_op["responses"]["409"]["content"][media]["examples"]["manifest_read_budget_exceeded"][
        "value"
    ]["code"] = "not_an_emitted_artifact_batch_code"
    with pytest.raises(
        AssertionError,
        match="get_artifact_batch: missing representative 409 problem examples",
    ):
        assert_routes(batch_with_wrong_example_code)


def test_artifact_batch_problem_examples_match_actual_conflict(
    runtime_api_env, monkeypatch
) -> None:
    """The route emits a typed 409 represented by its declared OpenAPI examples."""
    from copy import deepcopy

    from fastapi import FastAPI

    from polisyos.core.contracts.runtime import RuntimeApiProblem
    from polisyos.runtime.http.routes import artifacts as artifact_routes

    media = "application/problem+json"
    ref = "#/components/schemas/RuntimeApiProblem"
    required_codes = {
        "artifact_batch_manifest_read_budget_exceeded",
        "artifact_batch_manifest_read_usage_unavailable",
        "authority_surface_admission_blocked",
    }
    app = FastAPI()
    app.include_router(artifact_routes.router)
    schema = app.openapi()

    def assert_batch_response(candidate: dict[str, Any]) -> set[str]:
        operation = candidate["paths"]["/api/v1/artifacts/batch"]["post"]
        responses = operation.get("responses")
        assert isinstance(responses, dict), "get_artifact_batch: responses are missing"
        response = responses.get("409")
        assert isinstance(response, dict), "get_artifact_batch: missing or invalid 409 response"
        content = response.get("content")
        assert isinstance(content, dict), "get_artifact_batch: 409 response content is missing"
        assert content.keys() == {media}, "get_artifact_batch: 409 response media mismatch"
        payload = content.get(media)
        assert isinstance(payload, dict), "get_artifact_batch: problem payload is invalid"
        assert payload.get("schema") == {"$ref": ref}, (
            "get_artifact_batch: 409 response schema mismatch"
        )
        examples = payload.get("examples")
        assert isinstance(examples, dict), "get_artifact_batch: 409 response examples are missing"
        codes: set[str] = set()
        for example in examples.values():
            assert isinstance(example, dict) and "value" in example
            problem = RuntimeApiProblem.model_validate(example["value"], strict=True)
            assert problem.status == problem.status_code == 409
            codes.add(problem.code)
        assert required_codes <= codes, (
            "get_artifact_batch: missing representative 409 problem examples"
        )
        return codes

    declared_codes = assert_batch_response(schema)

    removed = deepcopy(schema)
    del removed["paths"]["/api/v1/artifacts/batch"]["post"]["responses"]["409"]
    with pytest.raises(AssertionError, match="get_artifact_batch: missing or invalid 409 response"):
        assert_batch_response(removed)

    wrong_example = deepcopy(schema)
    wrong_example["paths"]["/api/v1/artifacts/batch"]["post"]["responses"]["409"]["content"][media][
        "examples"
    ]["manifest_read_budget_exceeded"]["value"]["code"] = "not_an_emitted_artifact_batch_code"
    with pytest.raises(
        AssertionError,
        match="get_artifact_batch: missing representative 409 problem examples",
    ):
        assert_batch_response(wrong_example)

    original_budget_factory = artifact_routes._new_artifact_batch_manifest_read_budget

    def one_byte_budget(requested_id_count: int):
        budget = original_budget_factory(requested_id_count)
        budget.limit_source_bytes = 1
        return budget

    monkeypatch.setattr(
        artifact_routes,
        "_new_artifact_batch_manifest_read_budget",
        one_byte_budget,
    )
    response = runtime_api_env["client"].post(
        "/api/v1/artifacts/batch",
        json={"artifact_ids": [str(runtime_api_env["decision_packet_artifact_id"])]},
    )
    assert response.status_code == 409, response.text
    assert response.headers["content-type"].startswith(media)
    problem = RuntimeApiProblem.model_validate(response.json(), strict=True)
    assert problem.code in {
        "artifact_batch_manifest_read_budget_exceeded",
        "artifact_batch_manifest_read_usage_unavailable",
    }
    assert problem.code in declared_codes


def test_model_dispatched_success_examples_match_schema_and_reject_field_drift(
    runtime_openapi_app,
) -> None:
    """Registered examples agree with the actual schema and strict response DTOs."""
    from copy import deepcopy
    from typing import Annotated, get_args, get_origin

    from pydantic import BaseModel, ValidationError

    from polisyos.runtime.http import openapi_contract
    from polisyos.runtime.http._openapi_contract_helpers import iter_openapi_operations
    from polisyos.runtime.http.routes import lineage as lineage_routes
    from polisyos.runtime.http.routes import runs as runs_routes

    schema = export_runtime_openapi_schema(app=runtime_openapi_app)
    assert validate_runtime_openapi_contract(schema) == []
    response_models = openapi_contract._success_example_response_models()
    adapters = openapi_contract._success_example_response_adapters()
    assert response_models.keys() == adapters.keys()
    registered_example_operations = set(openapi_contract._SUCCESS_EXAMPLE_SETS_BY_OPERATION) | set(
        openapi_contract._SUCCESS_EXAMPLES_BY_OPERATION
    )
    assert set(response_models) <= registered_example_operations
    lineage_route_models = {
        route.operation_id: route.response_model
        for route in lineage_routes.router.routes
        if isinstance(getattr(route, "operation_id", None), str)
        and getattr(route, "response_model", None) is not None
    }
    assert lineage_route_models
    assert {
        operation_id: response_models[operation_id] for operation_id in lineage_route_models
    } == lineage_route_models
    assert set(lineage_route_models) <= registered_example_operations

    run_route_models = {
        route.operation_id: route.response_model
        for route in runs_routes.router.routes
        if isinstance(getattr(route, "operation_id", None), str)
        and getattr(route, "response_model", None) is not None
    }
    assert response_models["get_run_method_metrics"] is run_route_models["get_run_method_metrics"]
    assert "get_run_method_metrics" in registered_example_operations
    method_metric_examples = openapi_contract._SUCCESS_EXAMPLE_SETS_BY_OPERATION[
        "get_run_method_metrics"
    ]()
    owner_unavailable = method_metric_examples["owner_unavailable"]["value"]
    assert owner_unavailable["status"] == "verification_missing"
    assert owner_unavailable["vector_ref"] is None
    assert owner_unavailable["observations"] == []
    assert owner_unavailable["limitations"] == ["current_method_metric_owner_unavailable"]
    candidate_operation_id = "get_run_candidate_hte_packet"
    assert response_models[candidate_operation_id] is run_route_models[candidate_operation_id]
    assert candidate_operation_id in registered_example_operations
    candidate_hte_examples = openapi_contract._SUCCESS_EXAMPLE_SETS_BY_OPERATION[
        candidate_operation_id
    ]()
    assert set(candidate_hte_examples) == {"controlled_absence_fixture"}
    candidate_absence = candidate_hte_examples["controlled_absence_fixture"]["value"]
    assert candidate_absence["candidate_only"] is True
    assert candidate_absence["candidate_status"] == "absent"
    assert candidate_absence["source"] is None
    assert candidate_absence["limitations"] == ["completed_hte_source_not_established"]
    assert candidate_absence["publication_authorization"] == "not_established"
    assert candidate_absence["live_source_currentness"] == "not_established"
    operations = {
        operation.get("operationId"): operation
        for _, _, operation in iter_openapi_operations(schema)
        if isinstance(operation.get("operationId"), str)
    }
    operation_locations = {
        operation.get("operationId"): (path, method)
        for path, method, operation in iter_openapi_operations(schema)
        if isinstance(operation.get("operationId"), str)
    }

    candidate_operation = operations[candidate_operation_id]
    assert operation_locations[candidate_operation_id] == (
        "/api/v1/runs/{run_id}/decision-packets/{packet_id}/candidate-hte",
        "get",
    )
    candidate_success_pair = openapi_contract._first_success_response(
        candidate_operation["responses"]
    )
    assert candidate_success_pair is not None and candidate_success_pair[0] == "200"
    candidate_content = candidate_success_pair[1]["content"]["application/json"]
    assert candidate_content["examples"] == candidate_hte_examples

    def model_variants(response_model: Any) -> tuple[type[BaseModel], ...]:
        if get_origin(response_model) is Annotated:
            response_model = get_args(response_model)[0]
        arguments = get_args(response_model)
        candidates = arguments if arguments else (response_model,)
        return tuple(
            candidate
            for candidate in candidates
            if isinstance(candidate, type) and issubclass(candidate, BaseModel)
        )

    for operation_id, response_model in response_models.items():
        operation = operations[operation_id]
        path, method = operation_locations[operation_id]
        success_pair = openapi_contract._first_success_response(operation["responses"])
        assert success_pair is not None
        status_code, response = success_pair
        content = response.get("content")
        assert isinstance(content, dict)
        json_payload = content.get("application/json")
        assert isinstance(json_payload, dict)
        examples = json_payload.get("examples")
        assert isinstance(examples, dict) and examples
        variants = model_variants(response_model)
        assert variants

        actual_projection = openapi_contract._success_json_schema_projection(
            json_payload.get("schema"), document=schema
        )
        expected_schema = adapters[operation_id].json_schema(mode="serialization")
        expected_projection = openapi_contract._success_json_schema_projection(
            expected_schema, document=expected_schema
        )
        assert actual_projection == expected_projection

        required_sets = [
            set(variant.model_json_schema(mode="serialization").get("required", []))
            for variant in variants
        ]
        shared_required = set.intersection(*required_sets)
        assert shared_required
        drift_field = sorted(shared_required)[0]
        example_items = [
            (str(name), item["value"])
            for name, item in examples.items()
            if isinstance(item, dict) and "value" in item
        ]
        assert example_items
        for _name, value in example_items:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
            accepted = adapters[operation_id].validate_json(encoded, strict=True)
            assert accepted.model_dump(mode="json", exclude_unset=True) == value, (
                operation_id,
                _name,
            )

        example_name, example_value = example_items[0]
        assert isinstance(example_value, dict)
        corrupted_value = deepcopy(example_value)
        corrupted_value.pop(drift_field)
        with pytest.raises(ValidationError):
            adapters[operation_id].validate_json(
                json.dumps(corrupted_value, ensure_ascii=False, allow_nan=False), strict=True
            )
        corrupted_example_schema = deepcopy(schema)
        corrupted_operation = next(
            candidate
            for _, _, candidate in iter_openapi_operations(corrupted_example_schema)
            if candidate.get("operationId") == operation_id
        )
        corrupted_pair = openapi_contract._first_success_response(corrupted_operation["responses"])
        assert corrupted_pair is not None
        corrupted_payload = corrupted_pair[1]["content"]["application/json"]
        corrupted_payload["examples"][example_name]["value"] = corrupted_value
        example_violations = validate_runtime_openapi_contract(corrupted_example_schema)
        assert (
            f"{method.upper()} {path}: {status_code} success example {example_name} "
            "does not match registered response model"
        ) in example_violations

    predictive_schema_drift = deepcopy(schema)
    predictive_component = predictive_schema_drift["components"]["schemas"][
        "PredictiveCoverageDiagnosticPreview"
    ]
    predictive_version_schema = predictive_component["properties"]["source_schema_version"]
    assert predictive_version_schema["const"] == "1.0"
    predictive_version_schema["const"] = "2.0"
    drift_violations = validate_runtime_openapi_contract(predictive_schema_drift)

    assert (
        "GET /api/v1/artifacts/{artifact_id}/predictive-coverage-diagnostic: "
        "success response schema differs from registered response model"
    ) in drift_violations

    def predictive_scenario_component(snapshot: dict[str, Any]) -> dict[str, Any]:
        components = snapshot["components"]["schemas"]
        matches: list[dict[str, Any]] = []
        visited: set[int] = set()

        def visit(value: object) -> None:
            if isinstance(value, dict):
                if id(value) in visited:
                    return
                visited.add(id(value))
                properties = value.get("properties")
                if isinstance(properties, dict) and {
                    "interval_type",
                    "nominal_confidence_level",
                    "observed_hit_rate",
                }.issubset(properties):
                    matches.append(value)
                    return
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(components)
        assert len(matches) == 1
        return matches[0]

    non_null_default_drift = deepcopy(schema)
    non_null_default_component = predictive_scenario_component(non_null_default_drift)
    non_null_default_component["properties"]["nominal_confidence_level"]["default"] = 0.5
    non_null_default_violations = validate_runtime_openapi_contract(non_null_default_drift)
    assert (
        "GET /api/v1/artifacts/{artifact_id}/predictive-coverage-diagnostic: "
        "success response schema differs from registered response model"
    ) in non_null_default_violations

    requiredness_drift = deepcopy(schema)
    requiredness_component = predictive_scenario_component(requiredness_drift)
    requiredness = list(requiredness_component.get("required", []))
    assert "interval_type" not in requiredness
    requiredness.append("interval_type")
    requiredness_component["required"] = requiredness
    requiredness_violations = validate_runtime_openapi_contract(requiredness_drift)
    assert (
        "GET /api/v1/artifacts/{artifact_id}/predictive-coverage-diagnostic: "
        "success response schema differs from registered response model"
    ) in requiredness_violations

    def lex_discriminator_mapping(snapshot: dict[str, Any]) -> dict[str, Any]:
        lex_operation = next(
            candidate
            for _, _, candidate in iter_openapi_operations(snapshot)
            if candidate.get("operationId") == "get_lex_search_profile"
        )
        pair = openapi_contract._first_success_response(lex_operation["responses"])
        assert pair is not None
        response_schema = pair[1]["content"]["application/json"]["schema"]
        seen: set[str] = set()

        def find(value: object) -> dict[str, Any] | None:
            if isinstance(value, list):
                for item in value:
                    found = find(item)
                    if found is not None:
                        return found
            elif isinstance(value, dict):
                discriminator = value.get("discriminator")
                if isinstance(discriminator, dict) and isinstance(
                    discriminator.get("mapping"), dict
                ):
                    return discriminator["mapping"]
                ref = value.get("$ref")
                if isinstance(ref, str) and ref not in seen:
                    seen.add(ref)
                    target = openapi_contract._resolve_json_schema_pointer(snapshot, ref)
                    if target is not None:
                        found = find(target)
                        if found is not None:
                            return found
                for child in value.values():
                    found = find(child)
                    if found is not None:
                        return found
            return None

        mapping = find(response_schema)
        assert mapping and all(isinstance(target, str) for target in mapping.values())
        return mapping

    wrong_target_schema = deepcopy(schema)
    wrong_mapping = lex_discriminator_mapping(wrong_target_schema)
    tag, original_target = next(iter(wrong_mapping.items()))
    final_component = original_target.rsplit("/", 1)[-1]
    wrong_target_schema["components"]["schemas"]["R193WrongDiscriminatorTarget"] = {
        "properties": {final_component: {"type": "string", "const": "wrong-target"}}
    }
    wrong_mapping[tag] = (
        "#/components/schemas/R193WrongDiscriminatorTarget/properties/" + final_component
    )
    wrong_target_violations = validate_runtime_openapi_contract(wrong_target_schema)
    assert (
        "GET /api/v1/control/lex/search-profile: "
        "success response schema differs from registered response model"
    ) in wrong_target_violations

    for bad_ref in (
        "#/components/schemas/LexSearchProfileRefusedResponse~2Bad",
        "#/components/schemas/R193MissingResponse",
    ):
        bad_schema = deepcopy(schema)
        bad_op = next(
            candidate
            for _, _, candidate in iter_openapi_operations(bad_schema)
            if candidate.get("operationId") == "get_lex_search_profile"
        )
        bad_pair = openapi_contract._first_success_response(bad_op["responses"])
        assert bad_pair is not None
        bad_pair[1]["content"]["application/json"]["schema"] = {"$ref": bad_ref}
        bad_violations = validate_runtime_openapi_contract(bad_schema)
        assert (
            "GET /api/v1/control/lex/search-profile: "
            "success response schema differs from registered response model"
        ) in bad_violations

    raw_fragment_cases = (
        (
            "#/components/schemas/R193ReferenceTargets/properties/Response target",
            "Response target",
            True,
        ),
        (
            "#/components/schemas/R193ReferenceTargets/properties/Response%20target",
            "Response target",
            False,
        ),
        (
            "#/components/schemas/R193ReferenceTargets/properties/Response#target",
            "Response#target",
            True,
        ),
        (
            "#/components/schemas/R193ReferenceTargets/properties/Response%23target",
            "Response#target",
            False,
        ),
    )
    for response_reference, property_name, should_fail in raw_fragment_cases:
        fragment_schema = deepcopy(schema)
        fragment_operation = next(
            candidate
            for _, _, candidate in iter_openapi_operations(fragment_schema)
            if candidate.get("operationId") == "get_lex_search_profile"
        )
        fragment_pair = openapi_contract._first_success_response(fragment_operation["responses"])
        assert fragment_pair is not None
        fragment_payload = fragment_pair[1]["content"]["application/json"]
        target_schema = deepcopy(fragment_payload["schema"])
        fragment_schema["components"]["schemas"]["R193ReferenceTargets"] = {
            "properties": {property_name: target_schema}
        }
        fragment_payload["schema"] = {"$ref": response_reference}
        fragment_violations = validate_runtime_openapi_contract(fragment_schema)
        mismatch = (
            "GET /api/v1/control/lex/search-profile: "
            "success response schema differs from registered response model"
        ) in fragment_violations
        assert mismatch is should_fail

    predictive_example = openapi_contract._predictive_coverage_diagnostic_success_examples()[
        "limited_not_measured_candidate"
    ]["value"]
    assert predictive_example["measurement_status"] == "not_measured"
    assert predictive_example["reason_code"] == "no_evaluated_intervals"
    assert len(predictive_example["scenarios"]) == 1
    assert predictive_example["scenarios"][0]["interval_requested_count"] == 1
    assert predictive_example["scenarios"][0]["interval_evaluated_count"] == 0


def test_lineage_batch_openapi_schema_drift_is_rejected_against_route_dto() -> None:
    """Keep the batch DTO, route response schema, and resolution example joined."""
    from copy import deepcopy

    from polisyos.core.contracts.runtime import LineageBatchResponse
    from polisyos.runtime.http import openapi_contract

    response_models = openapi_contract._success_example_response_models()
    assert response_models["get_lineage_batch"] is LineageBatchResponse

    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/lineage/batch"]["post"]
    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
    assert any("lineage_resolutions" in item["value"] for item in examples.values())

    corrupted = deepcopy(schema)
    properties = corrupted["components"]["schemas"]["LineageBatchResponse"]["properties"]
    assert "lineage_resolutions" in properties
    del properties["lineage_resolutions"]

    expected = (
        "POST /api/v1/lineage/batch: success response schema differs from registered response model"
    )
    assert validate_runtime_openapi_contract(corrupted).count(expected) == 1


def test_success_schema_projection_resolves_complete_local_reference_graph() -> None:
    """Full target content binds refs; malformed and unsupported refs fail closed."""
    from polisyos.runtime.http.openapi_contract import (
        _is_valid_uri_fragment,
        _resolve_json_schema_pointer,
        _success_json_schema_projection,
    )

    pointer_doc = {"$defs": {"A/B": {"type": "string", "const": "bound"}}}
    assert _resolve_json_schema_pointer(pointer_doc, "#/%24defs/A~1B") == {
        "type": "string",
        "const": "bound",
    }
    assert _resolve_json_schema_pointer(pointer_doc, "#/$defs/A~2B") is None
    assert _resolve_json_schema_pointer(pointer_doc, "#/$defs/A%ZZB") is None
    raw_fragment_literals = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=:@/?"
    )
    for codepoint in range(0x80):
        character = chr(codepoint)
        assert _is_valid_uri_fragment(character) is (character in raw_fragment_literals)
    encoded_targets = {
        "Response target": {"type": "object", "const": "same"},
        "Response#target": {"type": "object", "const": "same"},
        "Response café": {"type": "object", "const": "same"},
    }
    encoded_document = {"components": {"schemas": encoded_targets}}
    assert (
        _resolve_json_schema_pointer(encoded_document, "#/components/schemas/Response%20target")
        == encoded_targets["Response target"]
    )
    assert (
        _resolve_json_schema_pointer(encoded_document, "#/components/schemas/Response%23target")
        == encoded_targets["Response#target"]
    )
    assert (
        _resolve_json_schema_pointer(encoded_document, "#/components/schemas/Response%20caf%C3%A9")
        == encoded_targets["Response café"]
    )
    expected_doc = {
        "$defs": {
            "LexSearchProfileRefusedResponse": {
                "type": "object",
                "properties": {"status": {"const": "refused"}},
            }
        }
    }
    actual_doc = {
        "components": {
            "schemas": {
                "LexSearchProfileRefusedResponse": expected_doc["$defs"][
                    "LexSearchProfileRefusedResponse"
                ],
                "R193Other": {
                    "properties": {
                        "LexSearchProfileRefusedResponse": {
                            "type": "string",
                            "const": "wrong-target",
                        }
                    }
                },
            }
        }
    }
    expected = {
        "oneOf": [{"$ref": "#/$defs/LexSearchProfileRefusedResponse"}],
        "discriminator": {
            "propertyName": "status",
            "mapping": {"refused": "#/$defs/LexSearchProfileRefusedResponse"},
        },
    }
    actual = {
        "oneOf": [{"$ref": "#/components/schemas/LexSearchProfileRefusedResponse"}],
        "discriminator": {
            "propertyName": "status",
            "mapping": {
                "refused": "#/components/schemas/R193Other/properties/LexSearchProfileRefusedResponse"
            },
        },
    }
    assert _success_json_schema_projection(
        expected, document=expected_doc
    ) != _success_json_schema_projection(actual, document=actual_doc)
    bad1 = _success_json_schema_projection(
        {"$ref": "#/components/schemas/X~2Y"}, document=actual_doc
    )
    bad2 = _success_json_schema_projection(
        {"$ref": "#/components/schemas/X~2Y"}, document=actual_doc
    )
    assert bad1 != bad2
    dag_doc = {"$defs": {"Shared": {"type": "string", "const": "same"}}}
    dag = _success_json_schema_projection(
        {"anyOf": [{"$ref": "#/$defs/Shared"}, {"$ref": "#/$defs/Shared"}]}, document=dag_doc
    )
    assert dag["anyOf"][0] == dag["anyOf"][1]
    cycle_doc = {
        "$defs": {"Node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/Node"}}}}
    }
    cycle = _success_json_schema_projection({"$ref": "#/$defs/Node"}, document=cycle_doc)
    assert cycle == _success_json_schema_projection({"$ref": "#/$defs/Node"}, document=cycle_doc)
    assert cycle["properties"]["next"] == {"$recursive_ref": True}


def test_schema_projection_omits_only_nullable_null_default_annotations() -> None:
    """Only a null default on an explicitly nullable schema is annotation-equivalent."""
    from polisyos.runtime.http.openapi_contract import _success_json_schema_projection

    nullable_any_of = {
        "anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}],
        "default": None,
    }
    nullable_any_of_without_default = {
        "anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}]
    }
    assert _success_json_schema_projection(
        nullable_any_of, document=nullable_any_of
    ) == _success_json_schema_projection(
        nullable_any_of_without_default, document=nullable_any_of_without_default
    )

    nullable_type_array = {"type": ["string", "null"], "default": None}
    nullable_type_array_without_default = {"type": ["string", "null"]}
    assert _success_json_schema_projection(
        nullable_type_array, document=nullable_type_array
    ) == _success_json_schema_projection(
        nullable_type_array_without_default, document=nullable_type_array_without_default
    )

    nullable_one_of = {
        "oneOf": [{"type": "string"}, {"type": "null"}],
        "default": None,
    }
    nullable_one_of_without_default = {"oneOf": [{"type": "string"}, {"type": "null"}]}
    assert _success_json_schema_projection(
        nullable_one_of, document=nullable_one_of
    ) == _success_json_schema_projection(
        nullable_one_of_without_default, document=nullable_one_of_without_default
    )

    type_union_but_any_of_excludes_null = {
        "type": ["number", "null"],
        "anyOf": [{"type": "number"}],
        "default": None,
    }
    type_union_but_any_of_without_default = {
        "type": ["number", "null"],
        "anyOf": [{"type": "number"}],
    }
    assert _success_json_schema_projection(
        type_union_but_any_of_excludes_null,
        document=type_union_but_any_of_excludes_null,
    ) != _success_json_schema_projection(
        type_union_but_any_of_without_default,
        document=type_union_but_any_of_without_default,
    )

    overlapping_one_of = {
        "oneOf": [{"type": "null"}, {}],
        "default": None,
    }
    overlapping_one_of_without_default = {"oneOf": [{"type": "null"}, {}]}
    assert _success_json_schema_projection(
        overlapping_one_of, document=overlapping_one_of
    ) != _success_json_schema_projection(
        overlapping_one_of_without_default, document=overlapping_one_of_without_default
    )

    unknown_one_of = {
        "oneOf": [{"type": "null", "x-unreviewed": True}, {"type": "string"}],
        "default": None,
    }
    unknown_one_of_without_default = {
        "oneOf": [{"type": "null", "x-unreviewed": True}, {"type": "string"}]
    }
    assert _success_json_schema_projection(
        unknown_one_of, document=unknown_one_of
    ) != _success_json_schema_projection(
        unknown_one_of_without_default, document=unknown_one_of_without_default
    )

    nullable_any_of_without_null = {"anyOf": [{"type": "number", "minimum": 0}]}
    assert _success_json_schema_projection(
        nullable_any_of_without_default, document=nullable_any_of_without_default
    ) != _success_json_schema_projection(
        nullable_any_of_without_null, document=nullable_any_of_without_null
    )

    non_null_default = {**nullable_any_of_without_default, "default": 0.5}
    assert _success_json_schema_projection(
        nullable_any_of_without_default, document=nullable_any_of_without_default
    ) != _success_json_schema_projection(non_null_default, document=non_null_default)

    non_nullable_null_default = {"type": "string", "default": None}
    non_nullable_without_default = {"type": "string"}
    assert _success_json_schema_projection(
        non_nullable_null_default, document=non_nullable_null_default
    ) != _success_json_schema_projection(
        non_nullable_without_default, document=non_nullable_without_default
    )

    constrained_null_default = {
        **nullable_any_of_without_default,
        "not": {"type": "null"},
        "default": None,
    }
    constrained_without_default = {
        **nullable_any_of_without_default,
        "not": {"type": "null"},
    }
    assert _success_json_schema_projection(
        constrained_null_default, document=constrained_null_default
    ) != _success_json_schema_projection(
        constrained_without_default, document=constrained_without_default
    )

    const_null = {**nullable_any_of_without_default, "const": None, "default": None}
    const_non_null = {**nullable_any_of_without_default, "const": "item", "default": None}
    assert _success_json_schema_projection(const_null, document=const_null) != (
        _success_json_schema_projection(const_non_null, document=const_non_null)
    )

    enum_with_null = {
        **nullable_any_of_without_default,
        "enum": [None, "item"],
        "default": None,
    }
    enum_without_null = {
        **nullable_any_of_without_default,
        "enum": ["item"],
        "default": None,
    }
    assert _success_json_schema_projection(enum_with_null, document=enum_with_null) != (
        _success_json_schema_projection(enum_without_null, document=enum_without_null)
    )

    required_schema = {
        "type": "object",
        "properties": {"value": nullable_any_of},
        "required": [],
    }
    newly_required_schema = {
        "type": "object",
        "properties": {"value": nullable_any_of_without_default},
        "required": ["value"],
    }
    assert _success_json_schema_projection(
        required_schema, document=required_schema
    ) != _success_json_schema_projection(newly_required_schema, document=newly_required_schema)


def test_success_example_gate_requires_inline_example_or_typed_binary_body() -> None:
    """Non-JSON presence alone is not an example; constrained binary is explicit."""
    from polisyos.runtime.http.openapi_contract import _success_response_has_example

    assert _success_response_has_example(
        "200",
        {"content": {"application/json": {"examples": {"candidate": {"value": {}}}}}},
    )
    assert _success_response_has_example(
        "200",
        {
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            }
        },
    )
    assert _success_response_has_example("204", {})
    assert not _success_response_has_example("200", {"content": {}})
    assert not _success_response_has_example(
        "200", {"content": {"text/csv": {"schema": {"type": "string"}}}}
    )
    assert not _success_response_has_example(
        "200",
        {
            "content": {
                "application/json": {"examples": {"external": {"externalValue": "sample.json"}}}
            }
        },
    )


def test_checked_in_openapi_design_problem_schema_preserves_v1_v2_and_admits_v3() -> None:
    """The published snapshot accepts qualified outcomes only under DesignProblem v3."""

    from copy import deepcopy

    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    from polisyos.runtime.quality.design_problem import DesignProblem

    repository_root = Path(__file__).resolve().parents[4]
    openapi = json.loads(
        (repository_root / "schemas/runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    openapi_uri = "https://policyos.example/runtime-api/openapi.json"

    def _validator(snapshot: dict[str, Any]) -> Draft202012Validator:
        registry = Registry().with_resource(
            openapi_uri,
            Resource.from_contents(snapshot, default_specification=DRAFT202012),
        )
        return Draft202012Validator(
            {"$ref": f"{openapi_uri}#/components/schemas/DesignProblem"},
            registry=registry,
        )

    problem = DesignProblem.model_validate(
        {
            "design_problem_id": "dp_openapi_contract",
            "problem_statement": "Assess a policy intervention.",
            "domain": "social",
            "nl_provenance": {
                "raw_request": "Assess a policy intervention.",
                "source_surface": "runtime.control.nl_request",
                "source_context": {},
            },
            "authority_profile": {
                "requester_authority": "research",
                "requested_authority_level": "research",
                "mandate": "Research mandate.",
            },
            "jurisdiction_time": {
                "region": "UA",
                "valid_time": "2026-09-29",
                "as_of": "2026-09-29",
                "policy_time": "2026-09-29",
                "data_time": "2025-2026",
                "time_semantics": {
                    "frequency": "Q",
                    "start_date": "2025-01-01",
                    "step_count": 4,
                },
            },
            "objectives": [
                {
                    "objective_id": "survival",
                    "description": "Increase survival.",
                    "metric_id": "survival_rate",
                    "direction": "maximize",
                }
            ],
            "stakeholders": [
                {"stakeholder_id": "households", "name": "Households", "role": "beneficiary"}
            ],
            "outcome_of_interest": {
                "target_variable": "firm_survival",
                "metric_id": "survival_rate",
                "estimand": "P(firm_survival | do(credit_access))",
                "direction": "maximize",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["credit_guarantee"],
                "candidate_levers": [
                    {
                        "lever_id": "credit_access",
                        "operator_kind": "credit_guarantee",
                        "instrument": "credit guarantee",
                        "target_slot": "credit_access",
                    }
                ],
            },
            "evidence_acquisition_needs": {
                "needs": [
                    {
                        "need_id": "survival_panel",
                        "question": "Measure survival.",
                        "required_for": "outcome_of_interest",
                        "status": "required",
                        "source_hint": "measurement_root",
                    }
                ]
            },
        }
    ).model_dump(mode="json")
    validator = _validator(openapi)

    for schema_version in (
        "policyos.runtime.design_problem.v1",
        "policyos.runtime.design_problem.v2",
    ):
        legacy_payload = {
            **problem,
            "schema_version": schema_version,
        }
        assert validator.is_valid(legacy_payload), schema_version

        dotted_legacy_payload = {
            **legacy_payload,
            "outcome_of_interest": {
                **problem["outcome_of_interest"],
                "target_variable": "government.balance",
            },
        }
        assert not validator.is_valid(dotted_legacy_payload), schema_version

    v3_payload = {
        **problem,
        "schema_version": "policyos.runtime.design_problem.v3",
        "outcome_of_interest": {
            **problem["outcome_of_interest"],
            "target_variable": "government.balance",
        },
    }
    assert validator.is_valid(v3_payload)

    without_v3_outcome_arm = deepcopy(openapi)
    without_v3_outcome_arm["components"]["schemas"]["DesignProblem"]["properties"][
        "outcome_of_interest"
    ]["anyOf"] = [{"$ref": "#/components/schemas/OutcomeOfInterest"}]
    assert not _validator(without_v3_outcome_arm).is_valid(v3_payload)


def test_epoch_validity_batch_success_example_matches_its_wire_contract() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/control/decision-validity/epoch-batches"]["post"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]

    response = EpochValidityBatchResponse.model_validate(example)

    assert response.state == "completed"
    assert response.completion_receipt.batch_id == response.batch_id
    assert response.affected_packet_refs == response.completion_receipt.affected_packet_refs


def _normative_evidence_schema_without_example() -> dict[str, Any]:
    """Keep the complete schema while requiring this owner to supply its example."""
    repository_root = Path(__file__).resolve().parents[4]
    schema = json.loads(
        (repository_root / "schemas/runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    operation = schema["paths"]["/api/v1/control/runs/{run_id}/normative-evidence"]["post"]
    assert operation["operationId"] == "submit_run_normative_evidence"
    content = operation["responses"]["200"]["content"]["application/json"]
    content.pop("example", None)
    content.pop("examples", None)
    return schema


def test_normative_evidence_openapi_example_preserves_actual_fixture_response() -> None:
    from polisyos.runtime.http.openapi_contract import augment_runtime_openapi
    from polisyos.runtime.http.services.control.generation_cycle import (
        NormativeEvidenceSubmissionResponse,
    )

    schema = augment_runtime_openapi(_normative_evidence_schema_without_example())
    assert validate_runtime_openapi_contract(schema) == []
    operation = schema["paths"]["/api/v1/control/runs/{run_id}/normative-evidence"]["post"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"][
        "positive_fixture_only_transport"
    ]
    repository_root = Path(__file__).resolve().parents[4]
    captured = json.loads(
        (
            repository_root / "docs/superpowers/journals/gy-phase5-evidence/pa1/"
            "openapi-response-capture.json"
        ).read_text(encoding="utf-8")
    )
    assert example["value"] == captured
    response = NormativeEvidenceSubmissionResponse.model_validate_json(
        json.dumps(example["value"]), strict=True
    )
    assert response.model_dump(mode="json", exclude_unset=True) == captured
    assert response.status == "admitted"
    assert response.job.progress["normative_disposition"]["ranked_recommendations"]
    assert "fixture" in example["summary"].lower()
    assert "not production authority or a canonical denominator" in example["description"]


def test_current_control_job_producer_serializes_runtime_quality_artifact_refs() -> None:
    """Project current persisted artifact refs through the normal response serializer."""
    from datetime import UTC, datetime

    from polisyos.runtime.http.services.control_plane_store import ControlJobRecord

    artifact_ref = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": "runtime.quality_scorecard",
        "media_type": "application/json",
    }
    timestamp = datetime(2026, 10, 12, tzinfo=UTC)
    record = ControlJobRecord(
        job_id="job-r10-runtime-quality-ref",
        kind="natural_language_run",
        state="completed",
        run_id="R_r10_runtime_quality_ref",
        pipeline_id=None,
        requested_execution_profile="dev",
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="fixture",
        created_at=timestamp,
        started_at=timestamp,
        finished_at=timestamp,
        lease_owner=None,
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={"runtime_quality_artifact_refs": {"quality_scorecard": artifact_ref}},
    )

    response = record.to_response(request_id="r10-current-producer")
    body = response.model_dump(mode="json")
    assert body["runtime_quality_artifact_refs"] == {"quality_scorecard": artifact_ref}


def test_normative_evidence_openapi_registration_removal_restores_exact_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.http import openapi_contract

    monkeypatch.delitem(
        openapi_contract._SUCCESS_EXAMPLE_SETS_BY_OPERATION, "submit_run_normative_evidence"
    )
    schema = openapi_contract.augment_runtime_openapi(_normative_evidence_schema_without_example())
    assert validate_runtime_openapi_contract(schema) == [
        "POST /api/v1/control/runs/{run_id}/normative-evidence: "
        "missing 2xx success response example"
    ]


def _acquisition_route_projection_payload(
    *,
    world_growth: str,
    admitted_observation_delta: int | None,
    activated: bool = False,
) -> dict[str, object]:
    digest = "sha256:" + "a" * 64
    return {
        "tenant_id": "tenant",
        "cell_id": "cell",
        "run_id": "run",
        "route_id": digest,
        "route_projection_hash": digest,
        "planner_report_hash": digest,
        "planner_record_id": "planner-record",
        "recommended_strategy": "targeted_primary_data_collection",
        "cost_basis": {},
        "replay_pins": {
            "source_job_id": "source-job",
            "compiled_ref": digest,
            "compiled_content_hash": digest,
            "terminal_event_id": "terminal-event",
            "design_problem_ref": digest,
            "cost_basis_hash": digest,
        },
        "authority_capability": "ready",
        "execution_capability": "ready",
        "qualification_status": "activated" if activated else "pending_epoch_activation",
        "qualification_predicate": ("independently_reconciled" if activated else "not_established"),
        "qualification_reason": (
            "native_owner_readback" if activated else "policy_admission_missing"
        ),
        "authority_badge": (
            "native_owner_verified" if activated else "behavioral_fixture_not_production"
        ),
        "world_growth": world_growth,
        "admitted_observation_delta": admitted_observation_delta,
    }


def test_acquisition_route_growth_status_requires_matching_owner_delta() -> None:
    for status, delta, activated in (
        ("not_established", None, False),
        ("no_growth", 0, True),
        ("admitted_delta", 2, True),
    ):
        AcquisitionRouteProjection.model_validate(
            _acquisition_route_projection_payload(
                world_growth=status,
                admitted_observation_delta=delta,
                activated=activated,
            )
        )
    for status, delta, activated in (
        ("not_established", 0, False),
        ("no_growth", None, True),
        ("no_growth", 1, True),
        ("admitted_delta", 0, True),
        ("admitted_delta", None, True),
        ("no_growth", 0, False),
    ):
        with pytest.raises(ValueError):
            AcquisitionRouteProjection.model_validate(
                _acquisition_route_projection_payload(
                    world_growth=status,
                    admitted_observation_delta=delta,
                    activated=activated,
                )
            )


def _assert_ds15_acquisition_openapi_contract(schema: dict[str, object]) -> None:
    from copy import deepcopy

    paths = schema["paths"]
    operations = {
        "list": paths["/api/v1/runs/{run_id}/acquisition-routes"]["get"],
        "get": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}"]["get"],
        "decision": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"][
            "post"
        ],
        "execute": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"]["post"],
    }
    assert {key: operation["operationId"] for key, operation in operations.items()} == {
        "list": "list_run_acquisition_routes",
        "get": "get_run_acquisition_route",
        "decision": "request_run_acquisition_decision",
        "execute": "execute_run_acquisition_route",
    }
    assert operations["decision"]["x-polisyos-step-up-class"] == "acquisition_approval"
    assert operations["execute"]["x-polisyos-step-up-class"] == "acquisition_approval"
    body = schema["components"]["schemas"]["AcquisitionRouteMutationRequest"]
    assert body["additionalProperties"] is False
    assert set(body["properties"]) == {
        "route_projection_hash",
        "planner_report_hash",
        "replay_pins",
        "idempotency_key",
        "human_decision_record_ref",
    }
    forbidden_authority_fields = {
        "gap_class",
        "cost",
        "voi",
        "action_eligibility",
        "decision_status",
        "passport",
        "rejection",
        "epoch",
        "growth",
        "reentry",
    }
    assert forbidden_authority_fields.isdisjoint(body["properties"])
    projection = schema["components"]["schemas"]["AcquisitionRouteProjection"]
    assert projection["properties"]["schema_version"]["const"] == ("AcquisitionRouteProjection@1.1")
    model_schema = AcquisitionRouteProjection.model_json_schema(mode="serialization")
    model_properties = model_schema["properties"]
    assert (
        projection["properties"]["world_growth"]["enum"] == model_properties["world_growth"]["enum"]
    )
    assert (
        projection["properties"]["qualification_status"]["enum"]
        == model_properties["qualification_status"]["enum"]
    )
    delta_key = "admitted_observation_delta"
    actual_delta = deepcopy(projection["properties"][delta_key])
    model_delta = deepcopy(model_properties[delta_key])
    for property_schema in (actual_delta, model_delta):
        nullable_branches = property_schema.get("anyOf")
        assert isinstance(nullable_branches, list)
        assert any(
            isinstance(branch, dict) and branch.get("type") == "null"
            for branch in nullable_branches
        )
        if property_schema.get("default", object()) is None:
            property_schema.pop("default")
    assert actual_delta == model_delta
    assert (delta_key in projection.get("required", [])) == (
        delta_key in model_schema.get("required", [])
    )
    for operation in operations.values():
        examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
        assert examples


def test_openapi_exposes_strict_acquisition_route_boundary_without_growth_authority() -> None:
    _assert_ds15_acquisition_openapi_contract(export_runtime_openapi_schema())


@pytest.mark.parametrize(
    "mutation",
    ["facet", "growth_delta", "schema_discriminator", "replay_pin", "operation_binding"],
)
def test_ds15_acquisition_openapi_mutations_fail_the_semantic_contract(mutation: str) -> None:
    schema = export_runtime_openapi_schema()
    projection = schema["components"]["schemas"]["AcquisitionRouteProjection"]
    body = schema["components"]["schemas"]["AcquisitionRouteMutationRequest"]
    if mutation == "facet":
        projection["properties"]["world_growth"]["enum"].remove("not_established")
    elif mutation == "growth_delta":
        projection["properties"]["admitted_observation_delta"]["default"] = 0
    elif mutation == "schema_discriminator":
        projection["properties"]["schema_version"]["const"] = "AcquisitionRouteProjection@0.0"
    elif mutation == "replay_pin":
        del body["properties"]["replay_pins"]
    else:
        schema["paths"]["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"]["post"][
            "operationId"
        ] = "get_run_acquisition_route"

    with pytest.raises(AssertionError):
        _assert_ds15_acquisition_openapi_contract(schema)


def test_openapi_preserves_run_paper_design_record_binding_as_an_exact_alias() -> None:
    schema = export_runtime_openapi_schema()

    assert RunPaperDesignRecordBinding is RunBoundDesignRecordBinding
    assert schema["components"]["schemas"]["RunPaperDesignRecordBinding"] == {
        "$ref": "#/components/schemas/RunBoundDesignRecordBinding"
    }


def test_openapi_preserves_artifact_id_as_an_exact_compatibility_alias() -> None:
    schema = export_runtime_openapi_schema()

    assert schema["components"]["schemas"]["ArtifactID"] == {
        "$ref": "#/components/schemas/ArtifactID-Input"
    }


def test_capability_discovery_examples_cover_truthful_postures_without_authority() -> None:
    schema = export_runtime_openapi_schema()
    for method, path in (
        ("post", "/api/v1/control/capabilities/search"),
        ("get", "/api/v1/control/data/catalog/search"),
    ):
        examples = schema["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "examples"
        ]
        assert set(examples) == {
            "discoverable_executable_authority_not_established",
            "candidate_only",
            "no_hit_incomplete",
            "case_producer_missing",
        }
        packets = [
            CapabilityDiscoveryResponse.model_validate(example["value"])
            for example in examples.values()
        ]
        assert all(
            item.authority_result.state != "admitted_authority"
            for packet in packets
            for item in packet.results
        )
        assert packets[0].results[0].discovery_result.state == "discoverable"
        assert packets[0].results[0].execution_result.state == "executable"
        assert packets[0].results[0].authority_result.state == "not_established"
        assert packets[1].results[0].execution_result.state == "not_established"
        assert packets[1].results[0].authority_result.state == "candidate_only"
        assert packets[2].frontier.completeness_status == "recall_unmeasured"
        assert packets[3].frontier.incompleteness_reasons == ("case:producer_missing",)


def test_epoch_staleness_examples_separate_positive_and_declared_absence() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/temporal/runs/{run_id}/epoch-staleness"]["get"]
    examples = operation["responses"]["200"]["content"]["application/json"]["examples"]

    assert set(examples) == {"positive_fixture_only", "declared_production_absence"}
    positive = EpochStalenessProjectionResponse.model_validate(
        examples["positive_fixture_only"]["value"]
    ).projection
    absence = EpochStalenessProjectionResponse.model_validate(
        examples["declared_production_absence"]["value"]
    ).projection

    assert positive.fixture_only is True
    assert positive.status == "current"
    assert absence.fixture_only is False
    assert absence.status == "not_established"
    assert {row.title for row in absence.institutional_absences} == {"Authority not appointed"}
    assert [row.title for row in absence.engineering_absences] == [
        "Engineering capability not wired"
    ]
    assert all(
        row.appointment_is_closure_precondition is False for row in absence.institutional_absences
    )
    assert absence.engineering_absences[0].candidate_owner_module == (
        "polisyos.runtime.quality.derived_observations"
    )


def test_epoch_batch_success_example_is_owner_derived_and_strict() -> None:
    from polisyos.runtime.http import openapi_contract

    print(
        "Measured: canonical typed epoch transport example registration and wire/status "
        "agreement. Not measured: persisted epoch admission, runtime status composition, "
        "clock/expiry behavior, or hosted CI."
    )
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/control/decision-validity/epoch-batches"]["post"]
    content = operation["responses"]["200"]["content"]["application/json"]
    assert "examples" in content, "canonical epoch batch transport example is not registered"
    example = content["examples"]["default"]["value"]
    assert example == openapi_contract._epoch_validity_batch_example()

    packet = EpochValidityBatchResponse.model_validate(example)

    assert packet.state == "completed"
    assert packet.affected_packet_refs == packet.completion_receipt.affected_packet_refs
    assert packet.transition == packet.completion_receipt.transition_artifact_ref
    assert packet.completion_receipt.targets[0].status.value == "review_required"


def test_openapi_exposes_strict_human_decision_unions() -> None:
    schema = export_runtime_openapi_schema()
    gate = schema["paths"]["/api/v1/runs/{run_id}/human-decision-gate"]["get"]
    create = schema["paths"]["/api/v1/runs/{run_id}/human-decisions"]["post"]
    evidence = schema["paths"][
        "/api/v1/runs/{run_id}/human-decision-evidence/{artifact_id}/content"
    ]["get"]

    gate_schema = schema["components"]["schemas"]["HumanDecisionGateResponse"]
    assert "submission" in gate_schema["properties"]
    assert "continuation" in gate_schema["properties"]
    replay = schema["components"]["schemas"]["HumanDecisionSubmissionSurface"]["properties"][
        "selector"
    ]
    assert replay["discriminator"]["propertyName"] == "source_kind"
    assert len(replay["oneOf"]) == 2
    pa2 = schema["components"]["schemas"]["HumanDecisionPA2ReplaySelector"]
    production = schema["components"]["schemas"]["HumanDecisionProductionReplaySelector"]
    assert "action_kind" in pa2["required"]
    assert "action_kind" not in production["properties"]
    assert "production_packet_ref" not in production["properties"]

    for operation in (create, evidence):
        header = next(
            parameter
            for parameter in operation["parameters"]
            if parameter["in"] == "header"
            and parameter["name"] == "X-PolicyOS-Human-Decision-Exposure"
        )
        assert header["required"] is True
        assert header["schema"]["pattern"] == r"^sha256:[0-9a-f]{64}$"

    body = schema["components"]["schemas"]["HumanDecisionMutationRequest"]
    assert body["additionalProperties"] is False
    assert "exposure_session_ref" not in body["properties"]
    record_schema = schema["components"]["schemas"]["HumanDecisionRecord"]
    assert record_schema["additionalProperties"] is False
    assert {
        "schema_version",
        "record_id",
        "human_decision_request_ref",
        "actor_ref",
        "decision_action_exercised",
        "responsibility_integrity",
        "authority_boundary",
        "tenant_id",
        "run_id",
        "binding_sha256",
        "predicate_receipts",
        "custody_signer_identity",
        "custody_boundary",
    } <= set(record_schema["properties"])
    assert {
        "schema_version",
        "record_id",
        "human_decision_request_ref",
        "actor_ref",
        "decision_action_exercised",
        "responsibility_integrity",
        "authority_boundary",
    } <= set(record_schema["required"])
    assert record_schema["properties"]["schema_version"]["enum"] == [
        "policyos.policy_design_case.layer2_s7_delegation.v1",
        "policyos.runtime.human_decision_record.v2",
    ]
    assert gate["operationId"] == "get_run_human_decision_gate"
    assert create["operationId"] == "create_run_human_decision"
    assert evidence["operationId"] == "get_run_human_decision_evidence_content"
    evidence_content = evidence["responses"]["200"]["content"]
    assert evidence_content["*/*"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    response_headers = evidence["responses"]["200"]["headers"]
    assert set(response_headers) == {
        "Cache-Control",
        "Content-Encoding",
        "ETag",
        "X-Content-Type-Options",
        "X-PolicyOS-Exposure-Session",
    }
    assert response_headers["Cache-Control"]["schema"]["enum"] == ["no-store"]
    assert response_headers["Content-Encoding"]["schema"]["enum"] == ["identity"]
    assert response_headers["X-Content-Type-Options"]["schema"]["enum"] == ["nosniff"]
    assert response_headers["X-PolicyOS-Exposure-Session"]["schema"]["pattern"] == (
        r"^sha256:[0-9a-f]{64}$"
    )

    examples = {
        "gate": gate,
        "create": create,
        "record": schema["paths"]["/api/v1/runs/{run_id}/human-decisions"]["get"],
        "review": schema["paths"]["/api/v1/runs/{run_id}/human-decisions/review-effectiveness"][
            "get"
        ],
    }
    values = {
        name: operation["responses"][next(iter(operation["responses"]))]["content"][
            "application/json"
        ]["examples"]["default"]["value"]
        for name, operation in examples.items()
    }
    HumanDecisionGateResponse.model_validate(values["gate"])
    HumanDecisionCreateResponse.model_validate(values["create"])
    HumanDecisionRecord.model_validate(values["record"])
    HumanDecisionReviewEffectivenessResponse.model_validate(values["review"])


def test_run_paper_success_example_recomputes_its_declared_projection_hash() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/runs/{run_id}/paper"]["get"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]
    packet = RunPaperPacket.model_validate(example)

    semantic_projection = build_run_paper_semantic_projection(
        run=packet.run,
        case_record=packet.case_record,
        stage_trace=packet.stage_trace,
        artifact_links=packet.artifact_links,
        source=packet.source,
    )

    assert hash_export_projection(semantic_projection) == packet.projection_hash


def _assert_cycle_board_example_source_and_replay_bindings(
    packet: CycleBoardProjectionPacket,
) -> None:
    history = packet.payload.historical_producer_availability
    receipt = history.read_receipt
    assert receipt.source_ref == history.source_ref
    assert receipt.source_content_hash == history.source_content_hash
    assert receipt.read_status == "read"
    assert receipt.status == "COMPLETE"
    assert receipt.coverage == "complete_selected_input"
    assert "current_availability_not_measured" in receipt.unresolved_by_construction
    historical_source = next(
        source
        for source in packet.composition_manifest
        if source.source_id == "historical-producer-availability"
    )
    assert historical_source.source_ref == history.source_ref
    assert historical_source.artifact_content_hash == history.source_content_hash

    manifest_material = _manifest_hash_material(packet.composition_manifest)
    manifest_hash = hash_export_projection(manifest_material)
    dependency_hash = hash_export_projection(
        tuple(
            {
                "source_id": source["source_id"],
                "availability": source["availability"],
                "artifact_content_hash": source["artifact_content_hash"],
                "source_dependency_hash": source["source_dependency_hash"],
                "absence_reason": source["absence_reason"],
            }
            for source in manifest_material
        )
    )
    projection_hash = hash_export_projection(
        {
            "projection_rule_version": CYCLE_BOARD_PROJECTION_RULE_VERSION,
            "composition_manifest": manifest_material,
            "payload": packet.payload,
        }
    )
    assert packet.composition_manifest_hash == manifest_hash
    assert packet.source_dependency_hash == dependency_hash
    assert packet.projection_hash == projection_hash
    assert packet.replay_address == build_export_replay_address(
        CYCLE_BOARD_STABLE_ADDRESS,
        {
            "replay_target": "composed_v2",
            "projection_rule_version": CYCLE_BOARD_PROJECTION_RULE_VERSION,
            "composition_manifest_hash": manifest_hash,
            "projection_hash": projection_hash,
            "source_dependency_hash": dependency_hash,
        },
    )


def test_cycle_board_success_example_is_a_strict_composed_absence_packet() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/exports/governed-projections/depth-n-cycle-board"]["get"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]

    packet = CycleBoardProjectionPacket.model_validate(example)
    _assert_cycle_board_example_source_and_replay_bindings(packet)

    assert packet.projection_rule_version == "policyos.runtime.depth_n_cycle_board.v2"
    assert tuple(source.source_id for source in packet.composition_manifest) == (
        *(projection_id.value for projection_id in _GOVERNED_COMPONENT_ORDER),
        "n13b-global-deeper-terminal",
        "ds4-realized-disposition",
        "historical-producer-availability",
    )
    repository_root = Path(__file__).resolve().parents[4]
    from polisyos.runtime.http.services.cycle_board_sources import (
        load_historical_producer_availability,
    )

    assert packet.payload.historical_producer_availability == (
        load_historical_producer_availability(repository_root)
    )
    catalog = {
        item.projection_id.value: item
        for item in GovernedProjectionService(repository_root).catalog()
    }
    for source in packet.composition_manifest[: len(_GOVERNED_COMPONENT_ORDER)]:
        owner = catalog[source.source_id]
        assert source.source_ref == owner.expected_source_path
        assert source.authoritative_for == owner.authoritative_for
        assert source.may_not_use_for == owner.may_not_use_for
    n13b_source = packet.composition_manifest[len(_GOVERNED_COMPONENT_ORDER)]
    assert n13b_source.authoritative_for == ()
    assert n13b_source.may_not_use_for == N13B_DENIED_ROW_USES
    assert packet.payload.rows == ()
    assert packet.payload.coverage.capability_state == "absent/unallocated"
    assert packet.payload.coverage.execution_status == "not_established"
    assert packet.payload.coverage.exhaustive is False
    assert packet.payload.movement_gap.capability_state == "absent/unallocated"
    assert packet.payload.movement_gap.execution_status == "not_established"
    assert packet.payload.movement_gap.movement_records == ()


def test_cycle_board_success_example_rejects_missing_read_receipt() -> None:
    from copy import deepcopy

    from pydantic import ValidationError

    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/exports/governed-projections/depth-n-cycle-board"]["get"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]
    malformed = deepcopy(example)
    del malformed["payload"]["historical_producer_availability"]["read_receipt"]
    with pytest.raises(ValidationError, match="read_receipt"):
        CycleBoardProjectionPacket.model_validate(malformed)


def test_cycle_board_success_example_rejects_manifest_source_hash_drift() -> None:
    from copy import deepcopy

    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/exports/governed-projections/depth-n-cycle-board"]["get"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]
    mutated = deepcopy(example)
    source = next(
        item
        for item in mutated["composition_manifest"]
        if item["source_id"] == "historical-producer-availability"
    )
    source["artifact_content_hash"] = "sha256:" + "0" * 64
    packet = CycleBoardProjectionPacket.model_validate(mutated)
    with pytest.raises(AssertionError):
        _assert_cycle_board_example_source_and_replay_bindings(packet)


def test_openapi_contract_includes_client_navigation_links() -> None:
    schema = export_runtime_openapi_schema()
    run_links = schema["paths"]["/api/v1/runs/{run_id}"]["get"]["responses"]["200"]["links"]
    artifact_links = schema["paths"]["/api/v1/artifacts/{artifact_id}"]["get"]["responses"]["200"][
        "links"
    ]
    mobility_links = schema["paths"]["/api/v1/mobility/reports/{artifact_id}"]["get"]["responses"][
        "200"
    ]["links"]

    assert sorted(run_links) == [
        "runAgents",
        "runEvidenceContext",
        "runFabricDecisionData",
        "runLineage",
        "runNodes",
        "runQuantities",
        "runTimeline",
        "runWorkflow",
    ]
    assert sorted(artifact_links) == [
        "artifactDownload",
        "artifactLineage",
        "artifactPreview",
        "artifactSchema",
    ]
    assert sorted(mobility_links) == [
        "mobilityBounds",
        "mobilityDiagnostics",
    ]


def test_openapi_contract_includes_batch_read_operations() -> None:
    schema = export_runtime_openapi_schema()

    runs_batch = schema["paths"]["/api/v1/runs/batch"]["post"]
    artifacts_batch = schema["paths"]["/api/v1/artifacts/batch"]["post"]

    assert runs_batch["operationId"] == "get_runs_batch"
    assert artifacts_batch["operationId"] == "get_artifact_batch"
    lineage_batch = schema["paths"]["/api/v1/lineage/batch"]["post"]
    assert lineage_batch["operationId"] == "get_lineage_batch"


def test_openapi_run_summary_requires_three_state_producer_terminality() -> None:
    schema = export_runtime_openapi_schema()
    components = schema["components"]["schemas"]
    summary = components["RunSummary"]

    assert components["RunTerminality"]["enum"] == [
        "terminal",
        "non_terminal",
        "not_established",
    ]
    assert "run_terminality" in summary["required"]
    assert summary["properties"]["run_terminality"] == {
        "$ref": "#/components/schemas/RunTerminality"
    }
    assert "run_terminality" not in components["RunDetails"]["properties"]


def test_openapi_contract_exposes_typed_policy_design_case_projection() -> None:
    schema = export_runtime_openapi_schema()
    components = schema["components"]["schemas"]

    projection_schema = components["PolicyDesignCaseProjection"]
    assert {
        "closeout_truth",
        "projection_gaps",
        "contested_records",
        "recourse_pointer",
        "deficit_register",
        "invariant_summary",
        "may_not_be_used_for",
    } <= set(projection_schema["properties"])

    control_projection = components["ControlJobResponse"]["properties"][
        "policy_design_case_projection"
    ]
    run_projection = components["RunDetails"]["properties"]["policy_design_case_projection"]

    assert "#/components/schemas/PolicyDesignCaseProjection" in json.dumps(control_projection)
    assert "#/components/schemas/PolicyDesignCaseProjection" in json.dumps(run_projection)


def test_generated_runtime_client_includes_batch_read_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    names = {operation.name for operation in operations}

    assert "getRunsBatch" in names
    assert "getArtifactBatch" in names
    assert "getRunFabricDecisionData" in names


def test_generated_runtime_client_includes_mobility_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    names = {operation.name for operation in operations}

    assert "estimateMobility" in names
    assert "computeMobilityBounds" in names
    assert "getMobilityReport" in names
    assert "getMobilityReportBounds" in names
    assert "getMobilityReportDiagnostics" in names


def test_generated_runtime_client_includes_governed_projection_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    names = {operation.name for operation in operations}

    assert "listGovernedProjections" in names
    assert "getGovernedProjection" in names
    assert "getRuntimeChannelRegistry" in names


def test_generated_runtime_client_includes_capability_search_wrapper(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)

    assert "searchCapabilities" in {operation.name for operation in operations}

    runtime_ts = tmp_path / "runtimeApiClient.ts"
    runtime_js = tmp_path / "runtimeApiClient.js"
    canonical_ts = tmp_path / "canonicalRuntimeApiClient.ts"
    canonical_js = tmp_path / "canonicalRuntimeApiClient.js"
    runtime_ts.write_text(
        generate_runtime_client._render_ts(spec, operations),
        encoding="utf-8",
    )
    runtime_js.write_text(
        generate_runtime_client._render_js(operations),
        encoding="utf-8",
    )
    _canonicalize_runtime_client(
        repo_root,
        spec_path,
        runtime_ts,
        runtime_js,
        canonical_ts,
        canonical_js,
    )

    for client_path in (runtime_ts, runtime_js, canonical_ts, canonical_js):
        source = client_path.read_text(encoding="utf-8")
        assert "async searchCapabilities(" in source
        assert "`/api/v1/control/capabilities/search`" in source


def _invoke_generated_operation(
    tmp_path: Path,
    *,
    spec: dict[str, object],
    method_name: str,
    params: dict[str, object],
) -> dict[str, object]:
    operations = generate_runtime_client._extract_operations(spec)
    client_path = tmp_path / "runtimeApiClient.mjs"
    client_path.write_text(
        generate_runtime_client._render_js(operations),
        encoding="utf-8",
    )
    probe_path = tmp_path / "invoke-generated-operation.mjs"
    probe_path.write_text(
        "\n".join(
            (
                f"import {{ RuntimeApiClient }} from {json.dumps(client_path.as_uri())};",
                "const calls = [];",
                "const client = new RuntimeApiClient({",
                '  baseUrl: "https://runtime.example",',
                "  fetchImpl: async (url, init) => {",
                "    calls.push({ url, method: init.method, body: init.body ?? null });",
                "    return {",
                "      ok: true,",
                "      status: 200,",
                '      statusText: "OK",',
                "      json: async () => ({ admitted: true }),",
                "    };",
                "  },",
                "});",
                f"await client[{json.dumps(method_name)}]({json.dumps(params)});",
                "process.stdout.write(JSON.stringify(calls[0]));",
            )
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(probe_path)],
        cwd=Path(__file__).resolve().parents[4],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_generated_epoch_batch_post_is_executable_not_just_typed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec = json.loads(
        (repo_root / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    operation = spec["paths"]["/api/v1/control/decision-validity/epoch-batches"]["post"]
    assert operation["operationId"] == "admit_epoch_validity_batch"

    call = _invoke_generated_operation(
        tmp_path,
        spec=spec,
        method_name="admitEpochValidityBatch",
        params={"body": {"probe": "content-bound"}},
    )

    assert call == {
        "url": "https://runtime.example/api/v1/control/decision-validity/epoch-batches",
        "method": "POST",
        "body": '{"probe":"content-bound"}',
    }


def test_generated_epoch_staleness_get_invokes_frozen_operation(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec = json.loads(
        (repo_root / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    operation = spec["paths"]["/api/v1/temporal/runs/{run_id}/epoch-staleness"]["get"]
    assert operation["operationId"] == "get_run_epoch_staleness"

    call = _invoke_generated_operation(
        tmp_path,
        spec=spec,
        method_name="getRunEpochStaleness",
        params={"run_id": "run-ds18-probe", "branch": "review-branch"},
    )

    assert call == {
        "url": (
            "https://runtime.example/api/v1/temporal/runs/run-ds18-probe/"
            "epoch-staleness?branch=review-branch"
        ),
        "method": "GET",
        "body": None,
    }


def test_runtime_contract_gate_rejects_nested_epoch_semantic_corruption(
    tmp_path: Path,
) -> None:
    schema = export_runtime_openapi_schema()
    title_schema = schema["components"]["schemas"]["InstitutionalAuthorityAbsenceView"][
        "properties"
    ]["title"]
    assert title_schema["const"] == "Authority not appointed"
    title_schema["const"] = "Generic error"
    corrupted = tmp_path / "runtime_api_v1.corrupted.openapi.json"
    corrupted.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    repo_root = Path(__file__).resolve().parents[4]

    result = subprocess.run(
        [
            sys.executable,
            "tools/ops_runners/runtime/check_runtime_api_contract.py",
            "--openapi",
            str(corrupted),
            "--skip-client-drift",
        ],
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "OpenAPI drift detected" in result.stdout


def test_generated_runtime_client_includes_all_acquisition_route_wrappers() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)

    assert {
        "listRunAcquisitionRoutes",
        "getRunAcquisitionRoute",
        "requestRunAcquisitionDecision",
        "executeRunAcquisitionRoute",
    } <= {operation.name for operation in operations}


def test_generated_runtime_js_client_accepts_params_for_body_operations() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    rendered_js = generate_runtime_client._render_js(operations)

    body_operations = [
        operation.name for operation in operations if operation.body_schema is not None
    ]

    for operation_name in body_operations:
        assert f"async {operation_name}(params) {{" in rendered_js


def _canonicalize_runtime_client(
    repo_root: Path,
    spec_path: Path,
    client_path: Path,
    runtime_js_path: Path,
    output_ts_path: Path,
    output_js_path: Path,
) -> None:
    result = subprocess.run(
        [
            "node",
            "packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs",
            "--openapi",
            str(spec_path),
            "--client",
            str(client_path),
            "--out-ts",
            str(output_ts_path),
            "--runtime-js",
            str(runtime_js_path),
            "--out-js",
            str(output_js_path),
        ],
        cwd=repo_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_committed_runtime_client_matches_package_generation_pipeline(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    operations = generate_runtime_client._extract_operations(spec)
    expected_ts = generate_runtime_client._render_ts(spec, operations)
    expected_js = generate_runtime_client._render_js(operations)

    generated_ts = tmp_path / "runtimeApiClient.ts"
    generated_js = tmp_path / "runtimeApiClient.js"
    canonical_ts = tmp_path / "canonicalRuntimeApiClient.ts"
    canonical_js = tmp_path / "canonicalRuntimeApiClient.js"
    generated_ts.write_text(expected_ts, encoding="utf-8")
    generated_js.write_text(expected_js, encoding="utf-8")
    _canonicalize_runtime_client(
        repo_root,
        spec_path,
        generated_ts,
        generated_js,
        canonical_ts,
        canonical_js,
    )
    client_root = repo_root / "packages" / "runtime-api-client"
    assert (client_root / "canonicalRuntimeApiClient.ts").read_bytes() == (
        canonical_ts.read_bytes()
    )
    assert (client_root / "canonicalRuntimeApiClient.js").read_bytes() == (
        canonical_js.read_bytes()
    )


def _render_openapi_typescript(repo_root: Path, spec_path: Path, output_path: Path) -> None:
    result = subprocess.run(
        [
            "node",
            str(repo_root / "packages/runtime-api-client/scripts/generate-openapi-types.mjs"),
            "--openapi",
            str(spec_path),
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_shared_client_generation_is_package_owned_and_version_pinned() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    client_root = repo_root / "packages" / "runtime-api-client"
    dashboard_root = repo_root / "apps" / "runtime-dashboard"
    manifest = json.loads((client_root / "package.json").read_text(encoding="utf-8"))
    dashboard_manifest = json.loads((dashboard_root / "package.json").read_text(encoding="utf-8"))
    lockfile = (repo_root / "pnpm-lock.yaml").read_text(encoding="utf-8")
    generator = (client_root / "scripts/generate-runtime-api-client.sh").read_text(encoding="utf-8")
    dashboard_generator = (dashboard_root / "scripts/generate-api-client.sh").read_text(
        encoding="utf-8"
    )
    readme = (client_root / "README.md").read_text(encoding="utf-8")
    package_importer = re.search(
        r"(?ms)^  packages/runtime-api-client:\n(?P<body>.*?)(?=^  [^ \n].*:\n|\Z)",
        lockfile,
    )

    generate_command = manifest["scripts"]["generate"]
    assert generate_command == "bash ./scripts/generate-runtime-api-client.sh"
    assert manifest["devDependencies"]["openapi-typescript"] == OPENAPI_TYPESCRIPT_VERSION
    assert package_importer is not None
    assert f"specifier: {OPENAPI_TYPESCRIPT_VERSION}" in package_importer.group("body")
    assert f"version: {OPENAPI_TYPESCRIPT_VERSION}(typescript@" in package_importer.group("body")
    dashboard_importer = re.search(
        r"(?ms)^  apps/runtime-dashboard:\n(?P<body>.*?)(?=^  [^ \n].*:\n|\Z)",
        lockfile,
    )
    assert dashboard_importer is not None
    assert "openapi-typescript" not in dashboard_manifest["devDependencies"]
    assert "openapi-typescript" not in dashboard_importer.group("body")
    assert "generate-openapi-types.mjs" in generator
    assert "generate-openapi-types.mjs" in dashboard_generator
    assert "--openapi" in generator
    assert '--openapi "${OPENAPI_FILE}"' in generator
    assert "apps/runtime-dashboard" not in generator
    assert "--prefix" not in generator
    assert "--output-root" in generator
    assert "generate-openapi-types.mjs" in readme
    assert "--openapi schemas/runtime_api_v1.openapi.json" in readme
    assert "npx --prefix apps/runtime-dashboard" not in readme


def test_client_package_entrypoints_generate_only_in_scratch(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    output_root = tmp_path / "generated"
    spec_path = tmp_path / "runtime_api_v1.openapi.json"
    source_spec = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    spec_path.write_bytes(source_spec.read_bytes())
    package_outputs = {
        "packages/runtime-api-client/types.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    }
    dashboard_output = "apps/runtime-dashboard/src/api/types.ts"
    tracked_outputs = {
        relative: (repo_root / relative).read_bytes()
        for relative in package_outputs | {dashboard_output}
    }

    for package, script in (
        ("@polisyos/runtime-api-client", "generate"),
        ("@polisyos/runtime-dashboard", "generate:api"),
    ):
        result = subprocess.run(
            [
                "corepack",
                "pnpm",
                "--filter",
                package,
                "run",
                script,
                "--",
                "--openapi",
                str(spec_path),
                "--output-root",
                str(output_root),
            ],
            cwd=repo_root,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr or result.stdout

    observed = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file()
    }
    assert observed == package_outputs | {dashboard_output}
    assert {
        relative: (repo_root / relative).read_bytes() for relative in tracked_outputs
    } == tracked_outputs


def test_openapi_typescript_output_matches_canonical_types_and_rejects_field_drift(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    generated = tmp_path / "types.ts"

    _render_openapi_typescript(repo_root, spec_path, generated)

    committed = repo_root / "packages" / "runtime-api-client" / "types.ts"
    assert committed.read_bytes() == generated.read_bytes()

    mutated_spec = json.loads(spec_path.read_text(encoding="utf-8"))
    lex_response = mutated_spec["components"]["schemas"]["LexSearchResponse"]
    removed_property = lex_response["properties"].pop("legal_relation_refusal")
    assert removed_property
    mutated_spec_path = tmp_path / "runtime_api_v1.missing_legal_refusal.json"
    mutated_spec_path.write_text(json.dumps(mutated_spec), encoding="utf-8")
    mutated_types = tmp_path / "types.missing_legal_refusal.ts"
    _render_openapi_typescript(repo_root, mutated_spec_path, mutated_types)
    assert mutated_types.read_bytes() != generated.read_bytes()

    from tools.ops_runners.runtime.check_runtime_api_contract import _check_openapi_drift

    violations = _check_openapi_drift(
        repo_root=repo_root,
        openapi_path=mutated_spec_path,
        max_diff_lines=120,
    )
    assert any("OpenAPI drift detected" in violation for violation in violations), violations


def test_generated_client_permission_union_matches_server_openapi_enum() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    schema = json.loads(
        (repo_root / "schemas" / "runtime_api_v1.openapi.json").read_text(encoding="utf-8")
    )
    server_permissions = [permission.value for permission in RuntimePermission]
    openapi_permissions = schema["components"]["schemas"]["RuntimePermission"]["enum"]
    generated_types = (repo_root / "packages" / "runtime-api-client" / "types.ts").read_text(
        encoding="utf-8"
    )
    match = re.search(r"^\s*RuntimePermission:\s*([^;]+);$", generated_types, re.MULTILINE)

    assert match is not None
    generated_permissions = re.findall(r'"([^"]+)"', match.group(1))
    assert openapi_permissions == server_permissions
    assert generated_permissions == server_permissions


def test_openapi_names_the_owner_decision_grade_at_its_only_property() -> None:
    schema = export_runtime_openapi_schema()
    components = schema["components"]["schemas"]
    owner_alias = getattr(DecisionGrade, "__value__", DecisionGrade)
    owner_values = list(get_args(owner_alias))
    decision_grade_ref = "#/components/schemas/DecisionGrade"
    reference_paths: list[tuple[str | int, ...]] = []

    def collect_reference_paths(value: object, path: tuple[str | int, ...] = ()) -> None:
        if isinstance(value, dict):
            if value.get("$ref") == decision_grade_ref:
                reference_paths.append((*path, "$ref"))
            for key, child in value.items():
                collect_reference_paths(child, (*path, key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect_reference_paths(child, (*path, index))

    collect_reference_paths(schema)

    assert components["DecisionGrade"]["enum"] == owner_values
    assert reference_paths == [
        (
            "components",
            "schemas",
            "AuthorityBoundary",
            "properties",
            "decision_grade",
            "anyOf",
            0,
            "$ref",
        )
    ]


def test_schema_and_clients_regenerate_byte_identically_twice(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    first_spec = export_runtime_openapi_schema()
    second_spec = export_runtime_openapi_schema()
    first_spec_bytes = (json.dumps(first_spec, indent=2, sort_keys=True) + "\n").encode()
    second_spec_bytes = (json.dumps(second_spec, indent=2, sort_keys=True) + "\n").encode()
    assert first_spec_bytes == second_spec_bytes

    first_path = tmp_path / "first.openapi.json"
    second_path = tmp_path / "second.openapi.json"
    first_path.write_bytes(first_spec_bytes)
    second_path.write_bytes(second_spec_bytes)
    first_types = tmp_path / "first.types.ts"
    second_types = tmp_path / "second.types.ts"
    _render_openapi_typescript(repo_root, first_path, first_types)
    _render_openapi_typescript(repo_root, second_path, second_types)
    assert first_types.read_bytes() == second_types.read_bytes()

    first_operations = generate_runtime_client._extract_operations(first_spec)
    second_operations = generate_runtime_client._extract_operations(second_spec)
    first_client = tmp_path / "first.runtimeApiClient.ts"
    second_client = tmp_path / "second.runtimeApiClient.ts"
    first_client_js = tmp_path / "first.runtimeApiClient.js"
    second_client_js = tmp_path / "second.runtimeApiClient.js"
    first_client.write_text(
        generate_runtime_client._render_ts(first_spec, first_operations),
        encoding="utf-8",
    )
    second_client.write_text(
        generate_runtime_client._render_ts(second_spec, second_operations),
        encoding="utf-8",
    )
    assert first_client.read_bytes() == second_client.read_bytes()
    first_client_js.write_text(
        generate_runtime_client._render_js(first_operations),
        encoding="utf-8",
    )
    second_client_js.write_text(
        generate_runtime_client._render_js(second_operations),
        encoding="utf-8",
    )
    assert first_client_js.read_bytes() == second_client_js.read_bytes()
    first_canonical_ts = tmp_path / "first.canonicalRuntimeApiClient.ts"
    second_canonical_ts = tmp_path / "second.canonicalRuntimeApiClient.ts"
    first_canonical_js = tmp_path / "first.canonicalRuntimeApiClient.js"
    second_canonical_js = tmp_path / "second.canonicalRuntimeApiClient.js"
    _canonicalize_runtime_client(
        repo_root,
        first_path,
        first_client,
        first_client_js,
        first_canonical_ts,
        first_canonical_js,
    )
    _canonicalize_runtime_client(
        repo_root,
        second_path,
        second_client,
        second_client_js,
        second_canonical_ts,
        second_canonical_js,
    )
    assert first_canonical_ts.read_bytes() == second_canonical_ts.read_bytes()
    assert first_canonical_js.read_bytes() == second_canonical_js.read_bytes()


def test_bad_request_uses_problem_json_payload(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    response = client.get("/api/v1/artifacts/not-a-valid-artifact-id")
    assert response.status_code == 400
    assert response.headers.get("content-type", "").startswith("application/problem+json")

    payload = response.json()
    assert payload["status"] == 400
    assert payload["status_code"] == 400
    assert payload["code"] == "invalid_artifact_id"
    assert payload["error"] == "bad_request"
