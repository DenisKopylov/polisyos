#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_GENERATED_POST_OPERATION_IDS = frozenset(
    {
        "get_artifact_batch",
        "get_runs_batch",
        "estimate_mobility",
        "compute_mobility_bounds",
    }
)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    required: bool
    schema: dict[str, Any]
    location: str


@dataclass(frozen=True)
class OperationSpec:
    name: str
    method: str
    path: str
    response_type: str
    path_params: tuple[ParamSpec, ...]
    query_params: tuple[ParamSpec, ...]
    body_schema: dict[str, Any] | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate runtime API typed client from OpenAPI schema."
    )
    parser.add_argument(
        "--openapi",
        type=Path,
        default=Path("schemas/runtime_api_v1.openapi.json"),
        help="Input OpenAPI JSON path.",
    )
    parser.add_argument(
        "--out-ts",
        type=Path,
        default=Path("frontend/runtime-api-client/runtimeApiClient.ts"),
        help="Output TypeScript client path.",
    )
    parser.add_argument(
        "--out-js",
        type=Path,
        default=Path("frontend/runtime-api-client/runtimeApiClient.js"),
        help="Output JavaScript client path.",
    )
    return parser.parse_args()


def _read_openapi(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"OpenAPI document must be a JSON object: {path}")
    return payload


def _schema_to_ts(
    schema: dict[str, Any] | None,
    *,
    components: dict[str, dict[str, Any]],
) -> str:
    if not isinstance(schema, dict):
        return "unknown"

    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        return _ts_type_name(ref.rsplit("/", 1)[-1])

    if schema.get("enum") and isinstance(schema["enum"], list):
        values = " | ".join(_literal(value) for value in schema["enum"])
        return values or "unknown"

    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        return _join_union(
            _schema_to_ts(item, components=components) for item in any_of if isinstance(item, dict)
        )

    one_of = schema.get("oneOf")
    if isinstance(one_of, list) and one_of:
        return _join_union(
            _schema_to_ts(item, components=components) for item in one_of if isinstance(item, dict)
        )

    all_of = schema.get("allOf")
    if isinstance(all_of, list) and all_of:
        rendered = [
            _schema_to_ts(item, components=components) for item in all_of if isinstance(item, dict)
        ]
        return " & ".join(rendered) if rendered else "unknown"

    schema_type = schema.get("type")
    if schema_type == "array":
        item_type = _schema_to_ts(schema.get("items"), components=components)
        return f"Array<{item_type}>"

    if schema_type == "object" or isinstance(schema.get("properties"), dict):
        properties = schema.get("properties")
        required = set(schema.get("required", []))
        lines: list[str] = ["{"]
        if isinstance(properties, dict):
            for key in sorted(properties):
                prop_schema = properties[key]
                prop_type = _schema_to_ts(prop_schema, components=components)
                prop_name = key if _is_identifier(key) else json.dumps(key)
                optional = "" if key in required else "?"
                lines.append(f"  {prop_name}{optional}: {prop_type};")
        additional = schema.get("additionalProperties")
        if additional is True:
            lines.append("  [key: string]: unknown;")
        elif isinstance(additional, dict):
            additional_type = _schema_to_ts(additional, components=components)
            lines.append(f"  [key: string]: {additional_type};")
        if len(lines) == 1:
            lines.append("  [key: string]: unknown;")
        lines.append("}")
        return "\n".join(lines)

    if schema_type == "integer":
        return "number"
    if isinstance(schema_type, str) and schema_type in {"number", "boolean", "string", "null"}:
        return schema_type

    if schema.get("format") == "date-time":
        return "string"

    return "unknown"


def _join_union(values: Iterable[str]) -> str:
    dedup: list[str] = []
    for value in values:
        if value not in dedup:
            dedup.append(value)
    return " | ".join(dedup) if dedup else "unknown"


def _literal(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if value is None:
        return "null"
    return str(value).lower() if isinstance(value, bool) else str(value)


def _is_identifier(value: str) -> bool:
    return bool(_IDENT_RE.match(value))


def _ts_type_name(value: str) -> str:
    if _is_identifier(value):
        return value
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", value) if part]
    candidate = "".join(part[:1].upper() + part[1:] for part in parts)
    if not candidate:
        return "AnonymousSchema"
    if candidate[0].isdigit():
        candidate = f"Schema{candidate}"
    return candidate if _is_identifier(candidate) else "AnonymousSchema"


def _to_camel(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", name)
    parts = [part for part in parts if part]
    if not parts:
        return "operation"
    head = parts[0].lower()
    tail = [part[:1].upper() + part[1:] for part in parts[1:]]
    candidate = head + "".join(tail)
    return candidate if _is_identifier(candidate) else f"op{candidate}"


def _resolve_parameter(
    raw_param: dict[str, Any],
    *,
    components: dict[str, dict[str, Any]],
) -> ParamSpec | None:
    param = raw_param
    if "$ref" in param:
        ref = param.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/parameters/"):
            parameter_name = ref.rsplit("/", 1)[-1]
            resolved = components.get("parameters", {}).get(parameter_name, {})
            if isinstance(resolved, dict):
                param = resolved
    name = param.get("name")
    location = param.get("in")
    if (
        not isinstance(name, str)
        or not isinstance(location, str)
        or location not in {"path", "query"}
    ):
        return None
    schema = param.get("schema")
    return ParamSpec(
        name=name,
        required=bool(param.get("required", False) or location == "path"),
        schema=schema if isinstance(schema, dict) else {},
        location=location,
    )


def _resolve_request_body(
    raw_body: dict[str, Any],
    *,
    components: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    body = raw_body
    ref = body.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/requestBodies/"):
        body_name = ref.rsplit("/", 1)[-1]
        resolved = components.get("requestBodies", {}).get(body_name)
        if isinstance(resolved, dict):
            body = resolved
    content = body.get("content")
    if not isinstance(content, dict):
        return None
    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        return None
    schema = app_json.get("schema")
    return schema if isinstance(schema, dict) else None


def _extract_operations(spec: dict[str, Any]) -> list[OperationSpec]:
    paths = spec.get("paths", {})
    components_root = spec.get("components", {})
    components = {
        "schemas": components_root.get("schemas", {}),
        "parameters": components_root.get("parameters", {}),
        "requestBodies": components_root.get("requestBodies", {}),
    }
    if not isinstance(paths, dict):
        return []

    operations: list[OperationSpec] = []
    for path in sorted(paths):
        raw_methods = paths[path]
        if not isinstance(raw_methods, dict):
            continue
        for method in sorted(raw_methods):
            method_spec = raw_methods[method]
            normalized_method = method.lower()
            if normalized_method not in {"get", "post"} or not isinstance(method_spec, dict):
                continue
            op_id = method_spec.get("operationId")
            raw_name = op_id if isinstance(op_id, str) else f"{method}_{path}"
            name = _to_camel(raw_name)
            if normalized_method == "post" and raw_name not in _GENERATED_POST_OPERATION_IDS:
                continue

            params: list[ParamSpec] = []
            for raw_param in method_spec.get("parameters", []):
                if not isinstance(raw_param, dict):
                    continue
                parsed = _resolve_parameter(raw_param, components=components)
                if parsed is not None:
                    params.append(parsed)
            path_params = tuple(param for param in params if param.location == "path")
            query_params = tuple(param for param in params if param.location == "query")
            body_schema = None
            request_body = method_spec.get("requestBody")
            if normalized_method == "post" and isinstance(request_body, dict):
                body_schema = _resolve_request_body(request_body, components=components)

            responses = method_spec.get("responses", {})
            response_schema: dict[str, Any] | None = None
            if isinstance(responses, dict):
                for code in ("200", "201", "202", "203", "204"):
                    candidate = responses.get(code)
                    if not isinstance(candidate, dict):
                        continue
                    content = candidate.get("content")
                    if not isinstance(content, dict):
                        continue
                    app_json = content.get("application/json")
                    if not isinstance(app_json, dict):
                        continue
                    payload_schema = app_json.get("schema")
                    if isinstance(payload_schema, dict):
                        response_schema = payload_schema
                        break
            response_type = _schema_to_ts(
                response_schema,
                components=components["schemas"],
            )
            operations.append(
                OperationSpec(
                    name=name,
                    method=method.upper(),
                    path=path,
                    response_type=response_type,
                    path_params=path_params,
                    query_params=query_params,
                    body_schema=body_schema,
                )
            )
    return operations


def _render_ts(spec: dict[str, Any], operations: list[OperationSpec]) -> str:
    components = spec.get("components", {}).get("schemas", {})
    lines: list[str] = [
        "// GENERATED FILE. DO NOT EDIT.",
        "// Source: schemas/runtime_api_v1.openapi.json",
        "",
        "export type JsonValue =",
        "  | string",
        "  | number",
        "  | boolean",
        "  | null",
        "  | { [key: string]: JsonValue }",
        "  | JsonValue[];",
        "",
    ]

    if isinstance(components, dict):
        for name in sorted(components):
            schema = components[name]
            if not isinstance(schema, dict):
                continue
            lines.append(
                f"export type {_ts_type_name(name)} = {_schema_to_ts(schema, components=components)};"
            )
            lines.append("")

    lines.extend(
        [
            "export interface RuntimeApiClientOptions {",
            "  baseUrl: string;",
            "  headers?: HeadersInit;",
            "  fetchImpl?: typeof fetch;",
            "}",
            "",
            "export class RuntimeApiClient {",
            "  private readonly baseUrl: string;",
            "  private readonly headers: HeadersInit;",
            "  private readonly fetchImpl: typeof fetch;",
            "",
            "  constructor(options: RuntimeApiClientOptions) {",
            '    this.baseUrl = options.baseUrl.replace(/\\/$/, "");',
            "    this.headers = options.headers ?? {};",
            "    this.fetchImpl = options.fetchImpl ?? fetch;",
            "  }",
            "",
            "  private async request<T>(",
            "    method: string,",
            "    path: string,",
            "    query?: URLSearchParams,",
            "    body?: unknown,",
            "  ): Promise<T> {",
            "    const url = query && query.toString()",
            "      ? `${this.baseUrl}${path}?${query.toString()}`",
            "      : `${this.baseUrl}${path}`;",
            "    const headers = body === undefined",
            "      ? this.headers",
            '      : { "Content-Type": "application/json", ...this.headers };',
            "    const response = await this.fetchImpl(url, {",
            "      method,",
            "      headers,",
            "      body: body === undefined ? undefined : JSON.stringify(body),",
            "    });",
            "    if (!response.ok) {",
            "      const body = await response.text();",
            "      throw new Error(",
            "        `Runtime API request failed: ${response.status} "
            "${response.statusText} ${body}`",
            "      );",
            "    }",
            "    return (await response.json()) as T;",
            "  }",
            "",
            "  private buildQuery(params: Record<string, unknown>): URLSearchParams {",
            "    const query = new URLSearchParams();",
            "    for (const [key, value] of Object.entries(params)) {",
            "      if (value === undefined || value === null) {",
            "        continue;",
            "      }",
            "      if (Array.isArray(value)) {",
            "        for (const item of value) {",
            "          query.append(key, String(item));",
            "        }",
            "        continue;",
            "      }",
            "      if (value instanceof Date) {",
            "        query.append(key, value.toISOString());",
            "        continue;",
            "      }",
            "      query.append(key, String(value));",
            "    }",
            "    return query;",
            "  }",
            "",
        ]
    )

    for operation in operations:
        params_fields = []
        for param in operation.path_params + operation.query_params:
            ts_type = _schema_to_ts(param.schema, components=components) or "unknown"
            optional = "" if param.required else "?"
            field_name = param.name if _is_identifier(param.name) else json.dumps(param.name)
            params_fields.append(f"    {field_name}{optional}: {ts_type};")
        if operation.body_schema is not None:
            params_fields.append(
                "    body: " + _schema_to_ts(operation.body_schema, components=components) + ";"
            )
        has_params = bool(params_fields)

        if has_params:
            lines.append(f"  async {operation.name}(params: {{")
            lines.extend(params_fields)
            lines.append(f"  }}): Promise<{operation.response_type}> {{")
        else:
            lines.append(f"  async {operation.name}(): Promise<{operation.response_type}> {{")

        path_expr = operation.path
        for param in operation.path_params:
            token = "{" + param.name + "}"
            replacement = "${encodeURIComponent(String(params." + param.name + "))}"
            path_expr = path_expr.replace(token, replacement)
        lines.append(f"    const path = `{path_expr}`;")
        if operation.query_params:
            lines.append("    const query = this.buildQuery({")
            for param in operation.query_params:
                lines.append(f"      {param.name}: params.{param.name},")
            lines.append("    });")
        else:
            lines.append("    const query = undefined;")
        if operation.body_schema is not None:
            lines.append(
                f"    return this.request<{operation.response_type}>("
                f'"{operation.method}", path, query, params.body);'
            )
        else:
            lines.append(
                f"    return this.request<{operation.response_type}>("
                f'"{operation.method}", path, query);'
            )
        lines.append("  }")
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _render_js(operations: list[OperationSpec]) -> str:
    lines: list[str] = [
        "// GENERATED FILE. DO NOT EDIT.",
        "// Source: schemas/runtime_api_v1.openapi.json",
        "",
        "export class RuntimeApiClient {",
        "  constructor(options) {",
        "    this.baseUrl = String(options.baseUrl || '').replace(/\\/$/, '');",
        "    this.headers = options.headers || {};",
        "    this.fetchImpl = options.fetchImpl || fetch;",
        "  }",
        "",
        "  async request(method, path, query, body) {",
        "    const suffix = query && query.toString() ? `?${query.toString()}` : '';",
        "    const url = `${this.baseUrl}${path}${suffix}`;",
        "    const headers = body === undefined",
        "      ? this.headers",
        "      : { 'Content-Type': 'application/json', ...this.headers };",
        "    const response = await this.fetchImpl(url, {",
        "      method,",
        "      headers,",
        "      body: body === undefined ? undefined : JSON.stringify(body),",
        "    });",
        "    if (!response.ok) {",
        "      const body = await response.text();",
        "      throw new Error(",
        "        `Runtime API request failed: ${response.status} ${response.statusText} ${body}`",
        "      );",
        "    }",
        "    return await response.json();",
        "  }",
        "",
        "  buildQuery(params) {",
        "    const query = new URLSearchParams();",
        "    for (const [key, value] of Object.entries(params || {})) {",
        "      if (value === undefined || value === null) {",
        "        continue;",
        "      }",
        "      if (Array.isArray(value)) {",
        "        for (const item of value) {",
        "          query.append(key, String(item));",
        "        }",
        "        continue;",
        "      }",
        "      if (value instanceof Date) {",
        "        query.append(key, value.toISOString());",
        "        continue;",
        "      }",
        "      query.append(key, String(value));",
        "    }",
        "    return query;",
        "  }",
        "",
    ]

    for operation in operations:
        params_arg = (
            "params"
            if (
                operation.path_params or operation.query_params or operation.body_schema is not None
            )
            else ""
        )
        lines.append(f"  async {operation.name}({params_arg}) {{")
        path_expr = operation.path
        for param in operation.path_params:
            token = "{" + param.name + "}"
            replacement = "${encodeURIComponent(String(params." + param.name + "))}"
            path_expr = path_expr.replace(token, replacement)
        lines.append(f"    const path = `{path_expr}`;")
        if operation.query_params:
            lines.append("    const query = this.buildQuery({")
            for param in operation.query_params:
                lines.append(f"      {param.name}: params?.{param.name},")
            lines.append("    });")
        else:
            lines.append("    const query = undefined;")
        if operation.body_schema is not None:
            lines.append(
                f"    return this.request('{operation.method}', path, query, params?.body);"
            )
        else:
            lines.append(f"    return this.request('{operation.method}', path, query);")
        lines.append("  }")
        lines.append("")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    spec = _read_openapi(args.openapi)
    operations = _extract_operations(spec)

    ts_output = _render_ts(spec, operations)
    js_output = _render_js(operations)

    args.out_ts.parent.mkdir(parents=True, exist_ok=True)
    args.out_ts.write_text(ts_output, encoding="utf-8")
    args.out_js.parent.mkdir(parents=True, exist_ok=True)
    args.out_js.write_text(js_output, encoding="utf-8")
    print(args.out_ts.as_posix())
    print(args.out_js.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
