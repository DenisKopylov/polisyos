from __future__ import annotations

from copy import deepcopy
from typing import Any

from polisyos.core.contracts.runtime import RuntimeApiProblem

_ARTIFACT_ID_SAMPLE = "sha256:" + "a" * 64
_RUN_ID_SAMPLE = "R_core_api_001"
_REQUEST_ID_SAMPLE = "req_0123456789abcdef"
_TS_SAMPLE = "2026-02-11T12:00:00Z"
_META_CORE_RUN = {
    "request_id": _REQUEST_ID_SAMPLE,
    "generated_at": _TS_SAMPLE,
    "source_kinds": ["core_run"],
}
_META_NO_SOURCE = {
    "request_id": _REQUEST_ID_SAMPLE,
    "generated_at": _TS_SAMPLE,
    "source_kinds": [],
}

_DEFAULT_PROBLEM_RESPONSES: dict[str, dict[str, str]] = {
    "400": {"code": "bad_request", "description": "Malformed request payload or parameters."},
    "401": {"code": "unauthorized", "description": "Authentication is required for this route."},
    "403": {
        "code": "forbidden",
        "description": "Authenticated principal cannot access this resource.",
    },
    "404": {"code": "not_found", "description": "Requested resource does not exist."},
    "422": {"code": "request_validation_failed", "description": "Request validation failed."},
    "500": {"code": "internal_error", "description": "Unexpected runtime API failure."},
}

_SUCCESS_EXAMPLES_BY_OPERATION: dict[str, dict[str, Any]] = {
    "health": {"status": "ok"},
    "ready": {"status": "ready"},
    "runtime_api_health": {
        "status": "ok",
        "service": "runtime_api_v1",
        "ts": _TS_SAMPLE,
    },
    "list_runs": {
        "meta": _META_CORE_RUN,
        "page": {"limit": 50, "cursor": None, "next_cursor": None, "count": 1, "total": 1},
        "runs": [
            {
                "run_id": _RUN_ID_SAMPLE,
                "source_kind": "core_run",
                "status": "completed",
                "started_at": _TS_SAMPLE,
                "finished_at": _TS_SAMPLE,
                "duration_ms": 4200,
                "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "cell_id": "cell-a",
                "has_trace": True,
                "root_artifact_count": 2,
                "has_workflow_report": True,
                "warnings": [],
            }
        ],
    },
    "get_run_details": {
        "meta": _META_CORE_RUN,
        "run": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "status": "completed",
            "started_at": _TS_SAMPLE,
            "finished_at": _TS_SAMPLE,
            "duration_ms": 4200,
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "cell_id": "cell-a",
            "has_trace": True,
            "manifest_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "trace_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "root_artifacts": [{"artifact_id": _ARTIFACT_ID_SAMPLE}],
            "has_workflow_report": True,
            "workflow_report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "warnings": [],
        },
    },
    "get_run_timeline": {
        "meta": _META_CORE_RUN,
        "timeline": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "summary": {
                "run_id": _RUN_ID_SAMPLE,
                "total_events": 2,
                "duration_ms": 4200,
                "node_status_counts": {"ok": 1, "fail": 1},
                "phase_counts": {"scientist": 2},
                "cache_hits": 1,
                "cache_stores": 0,
                "cache_bypasses": 1,
            },
            "events": [
                {
                    "index": 0,
                    "timestamp": _TS_SAMPLE,
                    "phase": "scientist",
                    "event": "NODE_OK",
                    "span_id": "span-a",
                    "parent_span_id": None,
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "metrics": {"duration_ms": 11},
                    "warning_count": 0,
                    "error_count": 0,
                }
            ],
            "notes": [],
        },
    },
    "get_run_nodes": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "source_kind": "core_run",
        "nodes": [
            {
                "alias": "run_governance",
                "node_id": "scientist.node_run_governance@1.1.0",
                "status": "fail",
                "duration_ms": 7,
                "error_code": "governance.blocked",
                "error_message": "Blocked by policy",
                "error_details": {"severity": "blocker"},
                "skip_reason": None,
                "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                "input_artifact_ids": [],
                "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            }
        ],
    },
    "get_run_lineage": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "lineage": {
            "root_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            "total_nodes": 1,
            "total_edges": 0,
            "total_size_bytes": 1024,
            "is_complete": True,
            "missing_artifact_ids": [],
            "corrupted_artifact_ids": [],
            "nodes": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "role": "root",
                    "kind": "scientist.workflow_report",
                    "status": "ok",
                    "byte_size": 1024,
                    "depth": 0,
                }
            ],
            "edges": [],
        },
    },
    "get_run_agents": {
        "meta": _META_CORE_RUN,
        "pipeline": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "total_attempts": 1,
            "latest_verdict": "NEEDS_REVISION",
            "attempts": [
                {
                    "attempt": 1,
                    "status": "failed",
                    "verdict": "abort_with_report",
                    "started_at": _TS_SAMPLE,
                    "finished_at": _TS_SAMPLE,
                    "duration_ms": 3,
                    "steps": [
                        {
                            "attempt": 1,
                            "agent": "pi_agent",
                            "action": "problem_frame_created",
                            "status": "ok",
                            "timestamp": _TS_SAMPLE,
                            "summary": "Problem framed",
                            "details": {},
                            "prompt": None,
                            "response": None,
                            "model": None,
                            "latency_ms": None,
                            "token_usage": {},
                        },
                        {
                            "attempt": 1,
                            "agent": "critic",
                            "action": "critique_complete",
                            "status": "warn",
                            "timestamp": _TS_SAMPLE,
                            "summary": "NEEDS_REVISION",
                            "details": {"verdict": "NEEDS_REVISION"},
                            "prompt": None,
                            "response": None,
                            "model": "gpt-4.1-mini",
                            "provider": "gateway",
                            "model_variant_id": "gpt_4_1_mini_1",
                            "latency_ms": 1480,
                            "cost_usd": 0.00145,
                            "token_usage": {"prompt_tokens": 411, "completion_tokens": 92, "total_tokens": 503},
                        },
                    ],
                    "notes": [],
                }
            ],
            "decision_packet_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "reflexion_terminal_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "source": "decision_packet.audit_trail",
            "notes": [],
        },
    },
    "get_run_workflow": {
        "meta": _META_CORE_RUN,
        "workflow": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "summary": {
                "workflow_id": "scientist_default",
                "error_policy": "fail_fast",
                "status": "fail",
                "node_count": 2,
                "edge_count": 1,
                "ok_count": 1,
                "skip_count": 0,
                "fail_count": 1,
                "max_depth": 1,
                "critical_path_duration_ms": 18,
            },
            "nodes": [
                {
                    "alias": "compile_foundry",
                    "node_id": "scientist.node_compile_foundry@1.0.0",
                    "depends_on": [],
                    "depth": 0,
                    "status": "ok",
                    "duration_ms": 11,
                    "error_code": None,
                    "error_message": None,
                    "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "heat": 0.611,
                },
                {
                    "alias": "run_governance",
                    "node_id": "scientist.node_run_governance@1.1.0",
                    "depends_on": ["compile_foundry"],
                    "depth": 1,
                    "status": "fail",
                    "duration_ms": 7,
                    "error_code": "governance.blocked",
                    "error_message": "Blocked by policy",
                    "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "input_artifact_ids": [],
                    "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
                    "heat": 0.389,
                },
            ],
            "edges": [
                {
                    "from_alias": "compile_foundry",
                    "to_alias": "run_governance",
                }
            ],
            "workflow_spec_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "workflow_report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "notes": [],
        },
    },
    "get_node_debug": {
        "meta": _META_CORE_RUN,
        "debug": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "alias": "run_governance",
            "record": {
                "alias": "run_governance",
                "node_id": "scientist.node_run_governance@1.1.0",
                "status": "fail",
                "duration_ms": 7,
                "error_code": "governance.blocked",
                "error_message": "Blocked by policy",
                "error_details": {"severity": "blocker"},
                "skip_reason": None,
                "artifact_ids": [_ARTIFACT_ID_SAMPLE],
                "input_artifact_ids": [],
                "output_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            },
            "timeline_events": [],
            "cache_hits": 0,
            "cache_stores": 0,
            "cache_bypasses": 1,
            "notes": [],
        },
    },
    "get_governance_debug": {
        "meta": _META_CORE_RUN,
        "debug": {
            "run_id": _RUN_ID_SAMPLE,
            "source_kind": "core_run",
            "verdict": "reject",
            "issues": [{"code": "GOV001", "message": "Policy blocker"}],
            "notes": ["manual review required"],
            "report_ref": {"artifact_id": _ARTIFACT_ID_SAMPLE},
            "validation_trace": {"total_blockers": 1},
            "fallback_from_decision_packet": False,
        },
    },
    "get_run_errors": {
        "meta": _META_CORE_RUN,
        "run_id": _RUN_ID_SAMPLE,
        "errors": [
            {
                "source": "workflow_report",
                "code": "governance.blocked",
                "message": "Blocked by policy",
                "node_alias": "run_governance",
                "timestamp": _TS_SAMPLE,
                "details": {"severity": "blocker"},
            }
        ],
    },
    "get_artifact_manifest": {
        "meta": _META_NO_SOURCE,
        "artifact": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "byte_size": 1024,
            "created_at": _TS_SAMPLE,
            "schema_name": "scientist.workflow_report",
            "schema_version": "1.0",
            "producer_component": "scientist.run_governance",
            "producer_version": "1.0.0",
            "inputs": [],
            "integrity_sha256": "a" * 64,
        },
    },
    "get_artifact_content": {
        "meta": _META_NO_SOURCE,
        "artifact": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "mode": "json",
            "size_bytes": 1024,
            "max_bytes": 4096,
            "truncated": False,
            "preview": {"status": "fail"},
        },
    },
    "get_artifact_lineage": {
        "meta": _META_NO_SOURCE,
        "lineage": {
            "root_artifact_ids": [_ARTIFACT_ID_SAMPLE],
            "total_nodes": 1,
            "total_edges": 0,
            "total_size_bytes": 1024,
            "is_complete": True,
            "missing_artifact_ids": [],
            "corrupted_artifact_ids": [],
            "nodes": [
                {
                    "artifact_id": _ARTIFACT_ID_SAMPLE,
                    "role": "root",
                    "kind": "scientist.workflow_report",
                    "status": "ok",
                    "byte_size": 1024,
                    "depth": 0,
                }
            ],
            "edges": [],
        },
    },
    "get_artifact_schema": {
        "meta": _META_NO_SOURCE,
        "schema": {
            "artifact_id": _ARTIFACT_ID_SAMPLE,
            "kind": "scientist.workflow_report",
            "media_type": "application/json",
            "schema_name": "scientist.workflow_report",
            "schema_version": "1.0",
            "top_level_keys": ["run_id", "status", "nodes"],
        },
    },
    # --- Control-plane operations ---
    "launch_run": {
        "meta": _META_NO_SOURCE,
        "status": "accepted",
        "run_id": "R_ctrl_abcdef01",
        "message": "Workflow run R_ctrl_abcdef01 accepted and executing in background.",
    },
    "launch_nl_run": {
        "meta": _META_NO_SOURCE,
        "status": "accepted",
        "run_id": "R_nl_abcdef02",
        "message": "Natural-language run R_nl_abcdef02 accepted. Agent circuit will execute with mock agents.",
    },
    "ingest_data": {
        "meta": _META_NO_SOURCE,
        "status": "completed",
        "evidence_bundle_ref": _ARTIFACT_ID_SAMPLE,
        "datasets_fetched": 2,
        "message": "Successfully ingested 2 dataset(s).",
    },
    "list_connectors": {
        "meta": _META_NO_SOURCE,
        "connectors": [
            {
                "connector_id": "worldbank.wdi",
                "namespace": "worldbank",
                "version": "1.0.0",
                "known_datasets": ["NY.GDP.MKTP.CD", "SP.POP.TOTL"],
                "loaded": True,
                "last_health_check": None,
            },
        ],
    },
    "list_source_profiles": {
        "meta": _META_NO_SOURCE,
        "profiles": [
            {
                "profile_id": "worldbank_wdi",
                "display_name": "World Bank WDI",
                "description": "World Development Indicators via World Bank API v2",
                "connector_family": "worldbank",
                "base_url": "https://api.worldbank.org/v2",
                "auth_policy": "none",
                "tags": ["international", "development", "gdp"],
                "source_organization": "The World Bank Group",
                "estimated_datasets": 1600,
                "connector_available": True,
            }
        ],
    },
    "list_llm_profiles": {
        "meta": _META_NO_SOURCE,
        "profiles": [
            {
                "profile_id": "gpt5_mini_gateway",
                "display_name": "GPT-5 mini (Gateway)",
                "description": "Balanced OpenAI frontier model via OpenAI-compatible gateway.",
                "provider": "openai",
                "model_id": "gpt-5-mini",
                "base_url": "https://api.gonkagate.com/v1",
                "tags": ["frontier", "balanced"],
                "capabilities": ["json", "tool_calling"],
                "input_cost_per_mtoken_usd": None,
                "output_cost_per_mtoken_usd": None,
                "enabled": True,
            }
        ],
    },
    "get_cache_status": {
        "meta": _META_NO_SOURCE,
        "total_entries": 0,
        "total_size_bytes": 0,
        "entries": [],
    },
}


def _problem_example(*, status_code: int, code: str, path: str) -> dict[str, Any]:
    return {
        "type": "about:blank",
        "title": code.replace("_", " ").capitalize(),
        "status": status_code,
        "detail": f"{code} while processing request.",
        "code": code,
        "instance": path,
        "request_id": _REQUEST_ID_SAMPLE,
        "error": code,
        "status_code": status_code,
    }


def _iter_operations(schema: dict[str, Any]):
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post"}:
                continue
            if not isinstance(operation, dict):
                continue
            yield path, method.lower(), operation


def augment_runtime_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    mutated = deepcopy(schema)
    components = mutated.setdefault("components", {})
    component_schemas = components.setdefault("schemas", {})
    if "RuntimeApiProblem" not in component_schemas:
        component_schemas["RuntimeApiProblem"] = RuntimeApiProblem.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )

    for path, _, operation in _iter_operations(mutated):
        operation_id = operation.get("operationId")
        responses = operation.setdefault("responses", {})
        if not isinstance(responses, dict):
            continue

        for status_code, descriptor in _DEFAULT_PROBLEM_RESPONSES.items():
            response = responses.get(status_code)
            if not isinstance(response, dict):
                response = {"description": descriptor["description"]}
                responses[status_code] = response
            response.setdefault("description", descriptor["description"])
            content = response.setdefault("content", {})
            if not isinstance(content, dict):
                continue
            payload = content.setdefault("application/problem+json", {})
            if not isinstance(payload, dict):
                continue
            payload.setdefault("schema", {"$ref": "#/components/schemas/RuntimeApiProblem"})
            if "example" not in payload and not payload.get("examples"):
                payload["examples"] = {
                    "default": {
                        "summary": descriptor["description"],
                        "value": _problem_example(
                            status_code=int(status_code),
                            code=descriptor["code"],
                            path=path,
                        ),
                    }
                }

        success_response = responses.get("200")
        if not isinstance(success_response, dict):
            continue
        success_content = success_response.get("content")
        if not isinstance(success_content, dict):
            continue
        success_json = success_content.get("application/json")
        if not isinstance(success_json, dict):
            continue
        if "example" in success_json or success_json.get("examples"):
            continue
        if not isinstance(operation_id, str):
            continue
        example = _SUCCESS_EXAMPLES_BY_OPERATION.get(operation_id)
        if example is None:
            continue
        success_json["examples"] = {
            "default": {
                "summary": f"{operation_id} response example",
                "value": example,
            }
        }

    return mutated


def install_runtime_openapi_contract(app: Any) -> None:
    original_openapi = app.openapi
    cached: dict[str, Any] | None = None

    def _custom_openapi() -> dict[str, Any]:
        nonlocal cached
        if cached is None:
            cached = augment_runtime_openapi(original_openapi())
        return cached

    app.openapi = _custom_openapi


def validate_runtime_openapi_contract(schema: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for path, method, operation in _iter_operations(schema):
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            violations.append(f"{method.upper()} {path}: missing responses object")
            continue

        success = responses.get("200")
        success_example_found = False
        if isinstance(success, dict):
            content = success.get("content")
            if isinstance(content, dict):
                json_content = content.get("application/json")
                if isinstance(json_content, dict):
                    success_example_found = bool(
                        ("example" in json_content) or json_content.get("examples")
                    )
        if not success_example_found:
            violations.append(f"{method.upper()} {path}: missing success response example")

        for status_code in ("400", "401", "403", "404", "422", "500"):
            response = responses.get(status_code)
            if not isinstance(response, dict):
                violations.append(f"{method.upper()} {path}: missing {status_code} response")
                continue
            content = response.get("content")
            if not isinstance(content, dict):
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing content"
                )
                continue
            problem_payload = content.get("application/problem+json")
            if not isinstance(problem_payload, dict):
                violations.append(
                    (
                        f"{method.upper()} {path}: {status_code} response "
                        "missing application/problem+json"
                    )
                )
                continue
            if "schema" not in problem_payload:
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing problem schema"
                )
            if "example" not in problem_payload and not problem_payload.get("examples"):
                violations.append(
                    f"{method.upper()} {path}: {status_code} response missing problem example"
                )

    return violations


__all__ = [
    "augment_runtime_openapi",
    "install_runtime_openapi_contract",
    "validate_runtime_openapi_contract",
]
