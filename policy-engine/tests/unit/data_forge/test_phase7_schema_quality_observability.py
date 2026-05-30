from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml
from polisyos.data_forge.errors import DataForgeValidationError, SchemaCompatibilityError
from polisyos.data_forge.kernel.artifacts import (
    ArtifactRef,
    PIILevel,
    ProducerVersion,
    RetentionClass,
)
from polisyos.data_forge.kernel.observability import (
    TraceContext,
    artifact_trace_metadata,
    attach_artifact_trace_metadata,
    current_trace_context,
)
from polisyos.data_forge.kernel.pipeline.manifests import (
    write_publish_manifest,
    write_raw_manifest,
    write_stage_manifest,
)
from polisyos.data_forge.kernel.schemas import (
    CompatibilityMode,
    SchemaChangeKind,
    SchemaEvolutionRule,
    SchemaMigrationPlan,
    SchemaMigrationRegistry,
    SchemaVersion,
    assert_schema_evolution_compatible,
    evaluate_schema_evolution,
)
from polisyos.data_forge.kernel.testing import (
    DriftThreshold,
    compare_domain_drift_suite,
    compare_domain_metrics,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_ROOT = REPO_ROOT / "schemas"
ARCHITECTURE_ROOT = REPO_ROOT / "architecture"


def test_phase7_artifact_schemas_validate_artifact_refs_and_trace_metadata() -> None:
    artifact_schema = _load_json_schema("artifacts/data_forge_artifact_ref_v1.schema.json")
    trace_schema = _load_json_schema("artifacts/data_forge_artifact_trace_metadata_v1.schema.json")
    domain_artifact_schema = _load_json_schema(
        "artifacts/data_forge_domain_artifact_v1.schema.json"
    )

    _assert_json_schema_contract(artifact_schema)
    _assert_json_schema_contract(trace_schema)
    _assert_json_schema_contract(domain_artifact_schema)

    artifact = _artifact_ref()
    metadata = artifact_trace_metadata(
        TraceContext(
            trace_id="1" * 32,
            span_id="2" * 16,
            trace_flags="01",
            is_sampled=True,
            is_valid=True,
        )
    )

    _validate_object_payload(artifact_schema, artifact.model_dump(mode="json"))
    _validate_object_payload(trace_schema, metadata)
    assert set(domain_artifact_schema["properties"]["domain"]["enum"]) == {
        "academic",
        "catalog",
        "legal",
        "ukraine",
    }


def test_phase7_manifest_schemas_validate_kernel_stage_and_publish_manifests(
    tmp_path: Path,
) -> None:
    raw_schema = _load_json_schema("manifests/data_forge_raw_manifest_v1.schema.json")
    stage_schema = _load_json_schema("manifests/data_forge_stage_manifest_v1.schema.json")
    publish_schema = _load_json_schema("manifests/data_forge_publish_manifest_v1.schema.json")
    _assert_json_schema_contract(raw_schema)
    _assert_json_schema_contract(stage_schema)
    _assert_json_schema_contract(publish_schema)

    artifact_path = tmp_path / "artifact.jsonl"
    artifact_path.write_text('{"ok": true}\n', encoding="utf-8")
    trace_context = TraceContext(
        trace_id="3" * 32,
        span_id="4" * 16,
        trace_flags="01",
        is_sampled=True,
        is_valid=True,
    )
    raw_manifest = write_raw_manifest(
        manifest_path=tmp_path / "raw.json",
        source="fixture",
        endpoint="file://fixture",
        payload_path=artifact_path,
        count=1,
        fetched_at="2026-05-02T00:00:00+00:00",
        trace_context=trace_context,
    )
    stage_manifest = write_stage_manifest(
        manifest_path=tmp_path / "stage.json",
        stage="normalize",
        status="ok",
        metrics={"rows": 1},
        artifacts=(artifact_path,),
        started_at="2026-05-02T00:00:00+00:00",
        finished_at="2026-05-02T00:00:01+00:00",
        trace_context=trace_context,
    )
    publish_manifest = write_publish_manifest(
        manifest_path=tmp_path / "publish.json",
        pipeline="catalog",
        artifacts=(artifact_path,),
        qc_report_path=tmp_path / "qc.json",
        published_at="2026-05-02T00:00:02+00:00",
        trace_context=trace_context,
    )

    _validate_object_payload(raw_schema, _load_json(raw_manifest))
    _validate_object_payload(stage_schema, _load_json(stage_manifest))
    _validate_object_payload(publish_schema, _load_json(publish_manifest))
    assert _load_json(stage_manifest)["trace_id"] == "3" * 32


def test_phase7_schema_evolution_requires_rules_for_breaking_changes() -> None:
    previous = _schema_version(
        version="1.0.0",
        required=("id",),
        properties={"id": {"type": "string"}},
    )
    optional_addition = _schema_version(
        version="1.1.0",
        required=("id",),
        properties={"id": {"type": "string"}, "title": {"type": "string"}},
    )
    required_addition = _schema_version(
        version="2.0.0",
        required=("id", "title"),
        properties={"id": {"type": "string"}, "title": {"type": "string"}},
    )

    compatible = evaluate_schema_evolution(previous, optional_addition)
    assert compatible.compatible is True
    assert compatible.changes[0].change_kind is SchemaChangeKind.ADD_OPTIONAL_FIELD

    breaking = evaluate_schema_evolution(previous, required_addition)
    assert breaking.compatible is False
    assert breaking.violations[0].change_kind is SchemaChangeKind.ADD_REQUIRED_FIELD
    with pytest.raises(SchemaCompatibilityError):
        assert_schema_evolution_compatible(previous, required_addition)

    allowed = assert_schema_evolution_compatible(
        previous,
        required_addition,
        rules=(
            SchemaEvolutionRule(
                schema_id="phase7.artifact",
                from_version="1.0.0",
                to_version="2.0.0",
                change_kind=SchemaChangeKind.ADD_REQUIRED_FIELD,
                rationale="producer can backfill title for all existing artifacts",
            ),
        ),
    )
    assert allowed.compatible is True


def test_phase7_schema_migration_registry_plans_and_applies_paths() -> None:
    registry = SchemaMigrationRegistry()
    registry.register(
        SchemaMigrationPlan(
            schema_id="phase7.artifact",
            from_version="1.0.0",
            to_version="1.1.0",
            migration_id="phase7.add_title",
        ),
        lambda payload: {**payload, "title": payload.get("id", "untitled")},
    )
    registry.register(
        SchemaMigrationPlan(
            schema_id="phase7.artifact",
            from_version="1.1.0",
            to_version="2.0.0",
            migration_id="phase7.add_schema_version",
        ),
        lambda payload: {**payload, "schema_version": "2.0.0"},
    )

    path = registry.plan_path(
        schema_id="phase7.artifact",
        from_version="1.0.0",
        to_version="2.0.0",
    )
    migrated = registry.apply(
        {"id": "artifact-1"},
        schema_id="phase7.artifact",
        from_version="1.0.0",
        to_version="2.0.0",
    )

    assert tuple(plan.migration_id for plan in path) == (
        "phase7.add_title",
        "phase7.add_schema_version",
    )
    assert migrated == {
        "id": "artifact-1",
        "title": "artifact-1",
        "schema_version": "2.0.0",
    }
    with pytest.raises(DataForgeValidationError):
        registry.plan_path(
            schema_id="phase7.artifact",
            from_version="2.0.0",
            to_version="3.0.0",
        )


def test_phase7_differential_drift_harness_covers_each_domain() -> None:
    suites = {
        "academic": ({"rows": 100, "readiness": 1}, {"rows": 101, "readiness": 1}),
        "catalog": ({"sources": 35, "tables": 8}, {"sources": 35, "tables": 8}),
        "legal": ({"claims": 1200, "qc": 1}, {"claims": 1200, "qc": 1}),
        "ukraine": ({"targets": 24, "aging_inputs": 6}, {"targets": 24, "aging_inputs": 6}),
    }
    reports = compare_domain_drift_suite(
        suites,
        thresholds={
            "academic": {"rows": DriftThreshold(metric="rows", max_absolute_delta=2)},
            "catalog": {"sources": 0, "tables": 0},
            "legal": {"claims": 0, "qc": 0},
            "ukraine": {"targets": 0, "aging_inputs": 0},
        },
    )
    failing = compare_domain_metrics(
        domain="academic",
        baseline={"rows": 100},
        candidate={"rows": 110},
        thresholds={"rows": 2},
    )

    assert {report.domain for report in reports} == {"academic", "catalog", "legal", "ukraine"}
    assert all(report.passed for report in reports)
    assert failing.passed is False
    assert failing.metric_by_name("rows").absolute_delta == 10


def test_phase7_artifact_refs_can_be_bound_to_otel_trace_metadata() -> None:
    artifact = _artifact_ref()
    context = TraceContext(
        trace_id="a" * 32,
        span_id="b" * 16,
        trace_flags="01",
        is_sampled=True,
        is_valid=True,
    )

    updated = attach_artifact_trace_metadata(artifact, context=context)
    metadata = artifact_trace_metadata(context)

    assert updated.trace_id == "a" * 32
    assert updated.span_id == "b" * 16
    assert updated.labels["otel.trace_flags"] == "01"
    assert updated.labels["otel.trace_valid"] == "true"
    assert metadata["otel.trace_sampled"] == "true"


def test_phase7_current_trace_context_reads_active_otel_span() -> None:
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

    span_context = SpanContext(
        trace_id=int("d" * 32, 16),
        span_id=int("e" * 16, 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    with use_span(NonRecordingSpan(span_context), end_on_exit=False):
        context = current_trace_context()

    assert context.trace_id == "d" * 32
    assert context.span_id == "e" * 16
    assert context.is_valid is True
    assert context.is_sampled is True


def test_phase7_slo_definitions_validate_against_ops_schema() -> None:
    slo_schema = _load_json_schema("ops/slo.schema.json")
    _assert_json_schema_contract(slo_schema)
    slo_paths = sorted((REPO_ROOT / "ops" / "observability" / "slo").glob("*.yaml"))

    assert slo_paths
    for path in slo_paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        _assert_slo_payload(payload)

    data_forge = yaml.safe_load(
        (REPO_ROOT / "ops" / "observability" / "slo" / "data_forge.yaml").read_text(
            encoding="utf-8"
        )
    )
    objective_names = {objective["name"] for objective in data_forge["objectives"]}
    assert {"schema_evolution_violation_rate", "domain_drift_violation_rate"} <= objective_names


def test_phase7_fabric_and_runtime_consumer_contracts_are_read_api_only() -> None:
    import_contracts = tomllib.loads(
        (ARCHITECTURE_ROOT / "imports" / "contracts.toml").read_text(encoding="utf-8")
    )
    package_boundaries = tomllib.loads(
        (ARCHITECTURE_ROOT / "packages" / "boundaries.toml").read_text(encoding="utf-8")
    )

    contract = _contract_by_name(
        import_contracts,
        "Runtime and Fabric consumers use Data Forge only through read_api",
    )
    assert {"polisyos.runtime", "polisyos.fabric"} <= set(contract["source_modules"])
    assert {
        "polisyos.data_forge",
        "polisyos.data_forge.kernel",
        "polisyos.data_forge.domains",
    } <= set(contract["forbidden_modules"])

    packages = {item["module"]: item for item in package_boundaries["package"]}
    for module in ("polisyos.runtime", "polisyos.fabric"):
        assert "polisyos.data_forge.kernel" in packages[module]["forbidden_dependencies"]
        assert "polisyos.data_forge.domains" in packages[module]["forbidden_dependencies"]

    violations = _direct_import_violations(
        (REPO_ROOT / "src" / "polisyos" / "runtime", REPO_ROOT / "src" / "polisyos" / "fabric"),
        ("polisyos.data_forge.kernel", "polisyos.data_forge.domains"),
    )
    dynamic_violations = _dynamic_reference_violations(
        (REPO_ROOT / "src" / "polisyos" / "runtime", REPO_ROOT / "src" / "polisyos" / "fabric"),
        ("polisyos.data_forge.kernel", "polisyos.data_forge.domains"),
    )
    assert violations == []
    assert dynamic_violations == []


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        uri="polisyos://academic/skg@snap-1",
        sha256="a" * 64,
        producer="tests.unit.data_forge.phase7",
        producer_version=ProducerVersion(code_version="0.1.0", lockfile_hash="b" * 64),
        trace_id="1" * 32,
        span_id="2" * 16,
        config_hash="c" * 64,
        owner="team-data-forge",
        license="test-fixture",
        regeneration_command=(
            "uv run pytest tests/unit/data_forge/test_phase7_schema_quality_observability.py"
        ),
        pii_level=PIILevel.NONE,
        retention_class=RetentionClass.HOT,
        freshness_sla_seconds=3600,
        schema_id="phase7.artifact",
        schema_version="1.0.0",
    )


def _schema_version(
    *,
    version: str,
    required: tuple[str, ...],
    properties: dict[str, dict[str, str]],
) -> SchemaVersion:
    return SchemaVersion(
        schema_id="phase7.artifact",
        version=version,
        compat_mode=CompatibilityMode.BACKWARD,
        json_schema={
            "type": "object",
            "required": list(required),
            "properties": properties,
        },
    )


def _load_json_schema(relative_path: str) -> dict[str, object]:
    return _load_json(SCHEMAS_ROOT / relative_path)


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _assert_json_schema_contract(schema: dict[str, object]) -> None:
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert str(schema["$id"]).startswith("polisyos://schemas/")
    assert schema["type"] == "object"
    assert isinstance(schema.get("properties"), dict)


def _validate_object_payload(schema: dict[str, object], payload: dict[str, object]) -> None:
    required = {str(item) for item in schema.get("required", ())}
    properties = schema.get("properties", {})
    assert isinstance(properties, dict)
    assert required <= set(payload)
    if schema.get("additionalProperties") is False:
        assert set(payload) <= set(properties)

    for key, value in payload.items():
        field_schema = properties[key]
        assert isinstance(field_schema, dict)
        _validate_schema_value(schema, field_schema, value)


def _validate_schema_value(
    root_schema: dict[str, object],
    field_schema: dict[str, object],
    value: object,
) -> None:
    if "$ref" in field_schema:
        ref = str(field_schema["$ref"])
        assert ref.startswith("#/$defs/")
        defs = root_schema["$defs"]
        assert isinstance(defs, dict)
        nested_schema = defs[ref.removeprefix("#/$defs/")]
        assert isinstance(nested_schema, dict)
        assert isinstance(value, dict)
        _validate_object_payload(nested_schema, value)
        return

    if "const" in field_schema:
        assert value == field_schema["const"]
    if "enum" in field_schema:
        assert value in field_schema["enum"]
    if "pattern" in field_schema:
        if value is not None:
            assert isinstance(value, str)
            assert re.fullmatch(str(field_schema["pattern"]), value)

    raw_type = field_schema.get("type")
    allowed_types = tuple(raw_type) if isinstance(raw_type, list) else (raw_type,)
    if raw_type is not None:
        assert any(_matches_json_type(value, item) for item in allowed_types)

    if raw_type == "array":
        assert isinstance(value, list)
        items_schema = field_schema.get("items", {})
        assert isinstance(items_schema, dict)
        for item in value:
            _validate_schema_value(root_schema, items_schema, item)


def _matches_json_type(value: object, json_type: object) -> bool:
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "object":
        return isinstance(value, dict)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "null":
        return value is None
    return True


def _assert_slo_payload(payload: object) -> None:
    assert isinstance(payload, dict)
    assert {"service", "version", "objectives"} <= set(payload)
    assert isinstance(payload["service"], str) and payload["service"]
    assert isinstance(payload["version"], int)
    assert isinstance(payload["objectives"], list)
    for objective in payload["objectives"]:
        assert isinstance(objective, dict)
        assert {"name", "sli", "threshold", "window", "owner", "runbook"} <= set(objective)
        assert all(isinstance(objective[key], str) and objective[key] for key in objective)


def _contract_by_name(payload: dict[str, object], name: str) -> dict[str, object]:
    contracts = payload.get("importlinter", {}).get("contracts", [])  # type: ignore[union-attr]
    for contract in contracts:
        if isinstance(contract, dict) and contract.get("name") == name:
            return contract
    raise AssertionError(f"missing import contract: {name}")


def _direct_import_violations(
    roots: tuple[Path, ...],
    blocked_prefixes: tuple[str, ...],
) -> list[str]:
    violations: list[str] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                import_name = _import_name(node)
                if import_name and import_name.startswith(blocked_prefixes):
                    violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {import_name}")
    return violations


def _dynamic_reference_violations(
    roots: tuple[Path, ...],
    blocked_fragments: tuple[str, ...],
) -> list[str]:
    violations: list[str] = []
    for root in roots:
        for path in sorted(item for item in root.rglob("*.py") if "__pycache__" not in item.parts):
            text = path.read_text(encoding="utf-8")
            for fragment in blocked_fragments:
                if fragment in text:
                    violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {fragment}")
    return violations


def _import_name(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        return str(node.names[0].name)
    if isinstance(node, ast.ImportFrom):
        return str(node.module or "")
    return ""
