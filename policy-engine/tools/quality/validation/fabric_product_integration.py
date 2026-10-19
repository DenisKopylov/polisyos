#!/usr/bin/env python3
"""Validate Fabric Phase 10 product/API integration closeout contracts."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from, resolve_polisyos_source_module_file

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.fabric._internal.compatibility import (  # noqa: E402
    FABRIC_COMPATIBILITY_BRIDGES,
    validate_fabric_compatibility_bridges,
)

REPORT_SCHEMA_VERSION = "fabric.product_integration_report.v1"

RUNTIME_ENDPOINTS: tuple[dict[str, str], ...] = (
    {
        "id": "fabric_source_scorecards",
        "operation_id": "get_fabric_source_scorecards",
        "path": "/api/v1/fabric/source-scorecards",
        "method": "get",
    },
    {
        "id": "fabric_quality_batch",
        "operation_id": "get_fabric_quality_batch",
        "path": "/api/v1/fabric/quality/batch",
        "method": "post",
    },
    {
        "id": "fabric_trust_batch",
        "operation_id": "get_fabric_trust_batch",
        "path": "/api/v1/fabric/trust/batch",
        "method": "post",
    },
    {
        "id": "fabric_replay",
        "operation_id": "get_fabric_run_replay",
        "path": "/api/v1/fabric/runs/{run_id}/replay",
        "method": "get",
    },
    {
        "id": "fabric_impact",
        "operation_id": "analyze_fabric_impact",
        "path": "/api/v1/fabric/impact",
        "method": "post",
    },
    {
        "id": "lineage_batch",
        "operation_id": "get_lineage_batch",
        "path": "/api/v1/lineage/batch",
        "method": "post",
    },
    {
        "id": "temporal_capabilities",
        "operation_id": "get_temporal_capabilities",
        "path": "/api/v1/temporal/capabilities",
        "method": "get",
    },
    {
        "id": "run_fabric_decision_data",
        "operation_id": "get_run_fabric_decision_data",
        "path": "/api/v1/runs/{run_id}/fabric-decision-data",
        "method": "get",
    },
)

FRONTEND_FIXTURES = (
    "run-quantities.json",
    "run-fabric-decision-data.json",
    "lineage.json",
    "lineage-batch.json",
    "temporal-capabilities.json",
    "compare-run.json",
    "counterfactual-metrics.json",
    "fabric-source-scorecards.json",
    "fabric-quality-batch.json",
    "fabric-trust-batch.json",
    "fabric-replay.json",
    "fabric-impact.json",
)

PRODUCT_ADAPTERS: tuple[dict[str, Any], ...] = (
    {
        "id": "fabric.product_evidence_path",
        "path": "src/polisyos/fabric/product_integration/__init__.py",
        "tokens": (
            "FabricProductEvidencePath",
            "evidence_path_from_fabric_decision_data",
        ),
    },
    {
        "id": "scholar.fabric_citation",
        "path": "src/polisyos/scholar/orchestrator/provenance.py",
        "tokens": (
            "ScholarFabricCitation",
            "scholar_citation_from_fabric_decision_data",
        ),
    },
    {
        "id": "lex.fabric_evidence",
        "module": "polisyos.lex.provenance",
        "implementation_module": "polisyos.lex.provenance.adapter",
        "symbols": {
            "LexFabricEvidencePath": "class",
            "lex_evidence_from_evidence_path": "function",
            "lex_evidence_from_fabric_decision_data": "function",
        },
        "test_path": "tests/unit/lex/provenance/test_adapter.py",
    },
    {
        "id": "foundry.calibration.fabric_quality",
        "path": "src/polisyos/foundry/calibration/fabric_quality.py",
        "tokens": (
            "FabricCalibrationContext",
            "fabric_calibration_context_from_decision_data",
        ),
    },
    {
        "id": "foundry.uncertainty.fabric_quality",
        "path": "src/polisyos/foundry/uncertainty/fabric_quality.py",
        "tokens": (
            "FabricUncertaintyContext",
            "fabric_uncertainty_context_from_decision_data",
        ),
    },
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Fail on Phase 10 gaps")
    return parser.parse_args(argv)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Build a static Phase 10 closeout report from committed artifacts."""
    openapi = _load_json(repo_root / "schemas" / "runtime_api_v1.openapi.json")
    openapi_operations = _openapi_operation_ids(openapi)
    runtime_route_text = "".join(
        _read(repo_root / path)
        for path in (
            "src/polisyos/runtime/http/routes/fabric.py",
            "src/polisyos/runtime/http/routes/lineage.py",
            "src/polisyos/runtime/http/routes/temporal.py",
            "src/polisyos/runtime/http/routes/runs.py",
        )
    )
    runtime_service_text = "".join(
        _read(repo_root / path)
        for path in (
            "src/polisyos/runtime/http/services/fabric.py",
            "src/polisyos/runtime/http/services/lineage.py",
            "src/polisyos/runtime/http/services/temporal.py",
        )
    )
    runtime_client_text = _read(
        repo_root / "packages" / "runtime-api-client" / "canonicalRuntimeApiClient.ts"
    )

    endpoint_rows = []
    for endpoint in RUNTIME_ENDPOINTS:
        endpoint_rows.append(
            {
                **endpoint,
                "route_present": endpoint["operation_id"] in runtime_route_text,
                "service_present": _service_present(endpoint["id"], runtime_service_text),
                "openapi_present": endpoint["operation_id"] in openapi_operations,
                "client_present": _client_present(endpoint["operation_id"], runtime_client_text),
            }
        )

    fixtures_dir = (
        repo_root / "apps" / "runtime-dashboard" / "src" / "test" / "contracts" / "fixtures"
    )
    fixture_registry_text = _read(
        repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "test"
        / "contracts"
        / "runtimeContractFixtures.ts"
    )
    validators_text = _read(
        repo_root / "apps" / "runtime-dashboard" / "src" / "api" / "validators.ts"
    )
    fixture_rows = [
        {
            "fixture": name,
            "file_present": (fixtures_dir / name).exists(),
            "registered": name in fixture_registry_text,
            "validator_present": _fixture_validator_present(name, validators_text),
        }
        for name in FRONTEND_FIXTURES
    ]
    frontend_rendering_rows = _frontend_rendering_rows(repo_root)

    scientist_rows = _scientist_rows(repo_root)
    adapter_rows = _adapter_rows(repo_root)
    compatibility_errors = validate_fabric_compatibility_bridges()
    root_facade_text = _read(repo_root / "src" / "polisyos" / "fabric" / "__init__.py")
    public_facade_stable = not any(
        token in root_facade_text
        for token in (
            "FabricProductEvidencePath",
            "FabricCompatibilityBridge",
            "scholar_citation_from_fabric_decision_data",
        )
    )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "summary": {
            "status": "implemented"
            if (
                all(_runtime_endpoint_ok(row) for row in endpoint_rows)
                and all(_fixture_ok(row) for row in fixture_rows)
                and all(row["status"] == "implemented" for row in frontend_rendering_rows)
                and all(row["status"] == "implemented" for row in scientist_rows)
                and all(row["status"] == "implemented" for row in adapter_rows)
                and not compatibility_errors
                and public_facade_stable
            )
            else "partial",
            "runtime_endpoint_count": len(endpoint_rows),
            "frontend_fixture_count": len(fixture_rows),
            "compatibility_bridge_count": len(FABRIC_COMPATIBILITY_BRIDGES),
            "public_facade_stable": public_facade_stable,
        },
        "runtime_endpoints": endpoint_rows,
        "frontend_contract_fixtures": fixture_rows,
        "frontend_rendering": frontend_rendering_rows,
        "scientist_governance": scientist_rows,
        "product_evidence_adapters": adapter_rows,
        "compatibility_bridges": [
            bridge.model_dump(mode="json") for bridge in FABRIC_COMPATIBILITY_BRIDGES
        ],
        "compatibility_errors": compatibility_errors,
    }


def _openapi_operation_ids(openapi: Mapping[str, Any]) -> set[str]:
    operations: set[str] = set()
    paths = openapi.get("paths", {})
    if not isinstance(paths, Mapping):
        return operations
    for path_item in paths.values():
        if not isinstance(path_item, Mapping):
            continue
        for operation in path_item.values():
            if isinstance(operation, Mapping) and operation.get("operationId"):
                operations.add(str(operation["operationId"]))
    return operations


def _service_present(endpoint_id: str, text: str) -> bool:
    tokens_by_endpoint = {
        "fabric_source_scorecards": ("build_source_scorecards_response",),
        "fabric_quality_batch": ("build_quality_batch_response",),
        "fabric_trust_batch": ("build_trust_batch_response",),
        "fabric_replay": ("build_replay_response",),
        "fabric_impact": ("build_impact_response",),
        "lineage_batch": ("build_runtime_lineage_batch",),
        "temporal_capabilities": ("build_capabilities",),
        "run_fabric_decision_data": ("build_fabric_decision_data_for_run",),
    }
    return all(token in text for token in tokens_by_endpoint.get(endpoint_id, ()))


def _client_present(operation_id: str, text: str) -> bool:
    if not text:
        return False
    camel = "".join(
        part if index == 0 else part[:1].upper() + part[1:]
        for index, part in enumerate(operation_id.split("_"))
    )
    return operation_id in text or camel in text


def _fixture_validator_present(fixture: str, validators_text: str) -> bool:
    token_by_fixture = {
        "run-quantities.json": "runQuantitiesSchema",
        "run-fabric-decision-data.json": "runFabricDecisionDataSchema",
        "lineage.json": "lineageResponseSchema",
        "lineage-batch.json": "lineageBatchResponseSchema",
        "temporal-capabilities.json": "temporalCapabilitiesSchema",
        "compare-run.json": "compareRunsSchema",
        "counterfactual-metrics.json": "counterfactualMetricsSchema",
        "fabric-source-scorecards.json": "fabricSourceScorecardsSchema",
        "fabric-quality-batch.json": "fabricQualityBatchSchema",
        "fabric-trust-batch.json": "fabricTrustBatchSchema",
        "fabric-replay.json": "fabricReplaySchema",
        "fabric-impact.json": "fabricImpactAnalysisSchema",
    }
    return token_by_fixture[fixture] in validators_text


def _scientist_rows(repo_root: Path) -> list[dict[str, Any]]:
    pass_text = _read(
        repo_root
        / "src"
        / "polisyos"
        / "scientist"
        / "governance"
        / "passes"
        / "fabric_trust_gate_pass.py"
    )
    registry_text = _read(
        repo_root / "src" / "polisyos" / "scientist" / "governance" / "pass_registry.py"
    )
    readiness_text = _read(
        repo_root / "src" / "polisyos" / "scientist" / "methods" / "search" / "readiness.py"
    )
    governance_tests_text = _read(
        repo_root / "tests" / "unit" / "scientist" / "governance" / "test_fabric_trust_gate_pass.py"
    )
    readiness_tests_text = _read(
        repo_root / "tests" / "unit" / "scientist" / "search" / "test_phase_b_policy_runtime.py"
    )
    rows = [
        {
            "id": "scientist.fabric_trust_gate_pass",
            "status": "implemented"
            if "FabricTrustGatePass" in pass_text
            and "fabric_trust" in registry_text
            and "FabricTrustGatePass" in governance_tests_text
            else "missing",
        },
        {
            "id": "scientist.fabric_readiness_cap",
            "status": "implemented"
            if "fabric_readiness_cap" in readiness_text
            and "test_fabric_trust_metadata_caps_decision_readiness" in readiness_tests_text
            else "missing",
        },
    ]
    return rows


def _top_level_assignment(tree: ast.Module, name: str) -> ast.expr | None:
    values: list[ast.expr | None] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
            value = node.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            values.append(value)
    return values[0] if len(values) == 1 and values[0] is not None else None


def _literal_string_sequence(tree: ast.Module, name: str) -> tuple[str, ...] | None:
    value = _top_level_assignment(tree, name)
    if not isinstance(value, (ast.List, ast.Tuple)):
        return None
    if any(
        not isinstance(item, ast.Constant) or not isinstance(item.value, str) for item in value.elts
    ):
        return None
    return tuple(str(item.value) for item in value.elts)


def _literal_string_mapping(tree: ast.Module, name: str) -> dict[str, str] | None:
    value = _top_level_assignment(tree, name)
    if not isinstance(value, ast.Dict):
        return None
    result: dict[str, str] = {}
    for key, item in zip(value.keys, value.values, strict=True):
        if (
            not isinstance(key, ast.Constant)
            or not isinstance(key.value, str)
            or not isinstance(item, ast.Constant)
            or not isinstance(item.value, str)
            or key.value in result
        ):
            return None
        result[key.value] = item.value
    return result


def _source_tree(path: Path | None) -> ast.Module | None:
    if path is None:
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return None


def _defined_symbol_kind(tree: ast.Module | None, symbol: str) -> str | None:
    if tree is None:
        return None
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == symbol
    ]
    if len(matches) != 1:
        return None
    return "class" if isinstance(matches[0], ast.ClassDef) else "function"


def _lazy_facade_dispatches_to(
    tree: ast.Module | None, module_name: str, implementation_module: str
) -> bool:
    if tree is None:
        return False
    importlib_names = {
        alias.asname or alias.name.split(".", 1)[0]
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "importlib"
    }
    handlers = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__"
    ]
    if len(handlers) != 1 or not importlib_names:
        return False
    handler = handlers[0]
    imported_names: set[str] = set()
    for node in ast.walk(handler):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if (
            not isinstance(value, ast.Call)
            or not isinstance(value.func, ast.Attribute)
            or not isinstance(value.func.value, ast.Name)
            or value.func.value.id not in importlib_names
            or value.func.attr != "import_module"
            or len(value.args) != 1
            or not isinstance(value.args[0], ast.JoinedStr)
        ):
            continue
        rendered: list[str] = []
        valid = True
        for part in value.args[0].values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                rendered.append(part.value)
            elif (
                isinstance(part, ast.FormattedValue)
                and isinstance(part.value, ast.Name)
                and part.value.id == "__name__"
            ):
                rendered.append(module_name)
            else:
                valid = False
                break
        if valid and "".join(rendered) == implementation_module:
            imported_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )

    loaded_values: set[str] = set()
    for node in ast.walk(handler):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        value = node.value
        if (
            isinstance(value.func, ast.Name)
            and value.func.id == "getattr"
            and len(value.args) == 2
            and isinstance(value.args[0], ast.Name)
            and value.args[0].id in imported_names
            and isinstance(value.args[1], ast.Subscript)
            and isinstance(value.args[1].value, ast.Name)
            and value.args[1].value.id == "_EXPORTS"
            and isinstance(value.args[1].slice, ast.Name)
            and value.args[1].slice.id == "name"
        ):
            loaded_values.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )

    caches_loaded_value = any(
        isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Name)
        and node.value.id in loaded_values
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Call)
            and isinstance(target.value.func, ast.Name)
            and target.value.func.id == "globals"
            and not target.value.args
            and isinstance(target.slice, ast.Name)
            and target.slice.id == "name"
            for target in node.targets
        )
        for node in ast.walk(handler)
    )
    returns_loaded_value = any(
        isinstance(node, ast.Return)
        and isinstance(node.value, ast.Name)
        and node.value.id in loaded_values
        for node in ast.walk(handler)
    )
    refuses_unknown_names = any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and (
            (isinstance(node.exc.func, ast.Name) and node.exc.func.id == "AttributeError")
            or (isinstance(node.exc.func, ast.Attribute) and node.exc.func.attr == "AttributeError")
        )
        for node in ast.walk(handler)
    )
    return bool(
        loaded_values and caches_loaded_value and returns_loaded_value and refuses_unknown_names
    )


def _module_adapter_row(repo_root: Path, adapter: Mapping[str, Any]) -> dict[str, Any]:
    module_name = str(adapter["module"])
    implementation_module = str(adapter["implementation_module"])
    symbols = adapter.get("symbols")
    symbols = dict(symbols) if isinstance(symbols, Mapping) else {}
    facade_path, facade_error = resolve_polisyos_source_module_file(repo_root, module_name)
    implementation_path, implementation_error = resolve_polisyos_source_module_file(
        repo_root, implementation_module
    )
    facade_tree = _source_tree(facade_path if facade_error is None else None)
    implementation_tree = _source_tree(
        implementation_path if implementation_error is None else None
    )
    exported_names = _literal_string_sequence(facade_tree, "__all__") if facade_tree else None
    export_bindings = _literal_string_mapping(facade_tree, "_EXPORTS") if facade_tree else None
    exports_resolved = bool(
        symbols
        and exported_names is not None
        and export_bindings is not None
        and all(
            kind in {"class", "function"}
            and symbol in exported_names
            and export_bindings.get(symbol) == symbol
            for symbol, kind in symbols.items()
        )
    )
    implementation_symbols_resolved = bool(
        symbols
        and all(
            _defined_symbol_kind(implementation_tree, symbol) == kind
            for symbol, kind in symbols.items()
        )
    )
    facade_dispatch_resolved = _lazy_facade_dispatches_to(
        facade_tree, module_name, implementation_module
    )
    test_path = str(adapter["test_path"])
    test_present = (repo_root / test_path).is_file()
    status = (
        "implemented"
        if facade_error is None
        and implementation_error is None
        and exports_resolved
        and implementation_symbols_resolved
        and facade_dispatch_resolved
        and test_present
        else "missing"
    )
    return {
        "id": adapter["id"],
        "path": (
            facade_path.relative_to(repo_root).as_posix()
            if facade_path is not None
            else module_name
        ),
        "implementation_path": (
            implementation_path.relative_to(repo_root).as_posix()
            if implementation_path is not None
            else implementation_module
        ),
        "status": status,
        "tokens": list(symbols),
        "test_path": test_path,
        "source_resolution": {
            "facade": facade_error or "resolved",
            "implementation": implementation_error or "resolved",
            "exports_resolved": exports_resolved,
            "implementation_symbols_resolved": implementation_symbols_resolved,
            "facade_dispatch_resolved": facade_dispatch_resolved,
            "test_present": test_present,
        },
    }


def _adapter_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for adapter in PRODUCT_ADAPTERS:
        if "module" in adapter:
            rows.append(_module_adapter_row(repo_root, adapter))
            continue
        path = repo_root / str(adapter["path"])
        text = _read(path)
        tokens = adapter["tokens"]
        assert isinstance(tokens, tuple)
        rows.append(
            {
                "id": adapter["id"],
                "path": adapter["path"],
                "status": "implemented"
                if path.exists() and all(token in text for token in tokens)
                else "missing",
                "tokens": list(tokens),
            }
        )
    return rows


def _runtime_endpoint_ok(row: Mapping[str, Any]) -> bool:
    return bool(
        row.get("route_present")
        and row.get("service_present")
        and row.get("openapi_present")
        and row.get("client_present")
    )


def _fixture_ok(row: Mapping[str, Any]) -> bool:
    return bool(row.get("file_present") and row.get("registered") and row.get("validator_present"))


def _frontend_rendering_rows(repo_root: Path) -> list[dict[str, Any]]:
    adapter_path = (
        repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "shared"
        / "ui"
        / "quantity"
        / "fabric-decision-data.ts"
    )
    adapter_test_path = adapter_path.with_suffix(".test.tsx")
    hook_path = (
        repo_root
        / "apps"
        / "runtime-dashboard"
        / "src"
        / "api"
        / "hooks"
        / "useRunFabricDecisionData.ts"
    )
    hook_test_path = hook_path.with_suffix(".test.tsx")
    adapter_text = _read(adapter_path)
    adapter_test_text = _read(adapter_test_path)
    hook_text = _read(hook_path)
    hook_test_text = _read(hook_test_path)
    return [
        {
            "id": "frontend.fabric_decision_data_to_quantity",
            "path": str(adapter_path.relative_to(repo_root)),
            "status": "implemented"
            if adapter_path.exists()
            and "fabricDecisionDataToQuantityValue" in adapter_text
            and "fabric_trust_envelope" in adapter_text
            and "TrustInspector" in adapter_test_text
            else "missing",
        },
        {
            "id": "frontend.use_run_fabric_decision_data",
            "path": str(hook_path.relative_to(repo_root)),
            "status": "implemented"
            if hook_path.exists()
            and "/api/v1/runs/{run_id}/fabric-decision-data" in hook_text
            and "fabricDecisionDataPayloadToQuantities" in hook_text
            and "quantities" in hook_test_text
            else "missing",
        },
    ]


def validate_report(report: Mapping[str, Any]) -> list[str]:
    """Return Phase 10 validation errors."""
    errors: list[str] = []
    for row in report.get("runtime_endpoints", []):
        if isinstance(row, Mapping) and not _runtime_endpoint_ok(row):
            errors.append(f"{row.get('id')}: runtime endpoint is not fully published")
    for row in report.get("frontend_contract_fixtures", []):
        if isinstance(row, Mapping) and not _fixture_ok(row):
            errors.append(f"{row.get('fixture')}: frontend fixture is incomplete")
    for section in ("frontend_rendering", "scientist_governance", "product_evidence_adapters"):
        for row in report.get(section, []):
            if isinstance(row, Mapping) and row.get("status") != "implemented":
                errors.append(f"{row.get('id')}: {section} is incomplete")
    if report.get("compatibility_errors"):
        errors.extend(str(error) for error in report["compatibility_errors"])
    if not report.get("summary", {}).get("public_facade_stable"):
        errors.append("polisyos.fabric.__all__ changed without public surface governance")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report()
    errors = validate_report(report)
    if args.report or not args.check:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.check and errors:
        print("Fabric product integration validation FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if args.check:
        print("Fabric product integration validation PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
