from __future__ import annotations

import json
import os
import re
import subprocess
from importlib.util import find_spec
from pathlib import Path

import pytest

if find_spec("fastapi") is None:  # pragma: no cover - optional dependency guard
    pytest.skip("fastapi is not installed", allow_module_level=True)

from polisyos.core.contracts.capability_discovery import CapabilityDiscoveryResponse
from polisyos.core.contracts.control import EpochValidityBatchResponse
from polisyos.pdc import RunBoundDesignRecordBinding
from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.openapi_contract import validate_runtime_openapi_contract
from polisyos.runtime.http.permissions import RuntimePermission
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


def test_epoch_validity_batch_success_example_matches_its_wire_contract() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/control/decision-validity/epoch-batches"]["post"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"][
        "default"
    ]["value"]

    response = EpochValidityBatchResponse.model_validate(example)

    assert response.state == "completed"
    assert response.completion_receipt.batch_id == response.batch_id
    assert response.affected_packet_refs == response.completion_receipt.affected_packet_refs


def _assert_ds15_acquisition_openapi_contract(schema: dict[str, object]) -> None:
    paths = schema["paths"]
    operations = {
        "list": paths["/api/v1/runs/{run_id}/acquisition-routes"]["get"],
        "get": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}"]["get"],
        "decision": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request"][
            "post"
        ],
        "execute": paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"]["post"],
    }
    assert {
        key: operation["operationId"] for key, operation in operations.items()
    } == {
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
    assert projection["properties"]["schema_version"]["const"] == (
        "AcquisitionRouteProjection@1.0"
    )
    assert projection["properties"]["world_growth"]["const"] == "no_growth"
    assert projection["properties"]["qualification_status"]["const"] == ("pending_epoch_activation")
    for operation in operations.values():
        examples = operation["responses"]["200"]["content"]["application/json"]["examples"]
        assert examples


def test_openapi_exposes_strict_acquisition_route_boundary_without_growth_authority() -> None:
    _assert_ds15_acquisition_openapi_contract(export_runtime_openapi_schema())


@pytest.mark.parametrize(
    "mutation",
    ["facet", "schema_discriminator", "replay_pin", "operation_binding"],
)
def test_ds15_acquisition_openapi_mutations_fail_the_semantic_contract(mutation: str) -> None:
    schema = export_runtime_openapi_schema()
    projection = schema["components"]["schemas"]["AcquisitionRouteProjection"]
    body = schema["components"]["schemas"]["AcquisitionRouteMutationRequest"]
    if mutation == "facet":
        projection["properties"]["world_growth"]["const"] = "grew"
    elif mutation == "schema_discriminator":
        projection["properties"]["schema_version"]["const"] = (
            "AcquisitionRouteProjection@0.0"
        )
    elif mutation == "replay_pin":
        del body["properties"]["replay_pins"]
    else:
        schema["paths"][
            "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"
        ]["post"]["operationId"] = "get_run_acquisition_route"

    with pytest.raises(AssertionError):
        _assert_ds15_acquisition_openapi_contract(schema)


def test_openapi_preserves_run_paper_design_record_binding_as_an_exact_alias() -> None:
    schema = export_runtime_openapi_schema()

    assert RunPaperDesignRecordBinding is RunBoundDesignRecordBinding
    assert schema["components"]["schemas"]["RunPaperDesignRecordBinding"] == {
        "$ref": "#/components/schemas/RunBoundDesignRecordBinding"
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


def test_cycle_board_success_example_is_a_strict_composed_absence_packet() -> None:
    schema = export_runtime_openapi_schema()
    operation = schema["paths"]["/api/v1/exports/governed-projections/depth-n-cycle-board"]["get"]
    example = operation["responses"]["200"]["content"]["application/json"]["examples"]["default"][
        "value"
    ]

    packet = CycleBoardProjectionPacket.model_validate(example)

    assert packet.projection_rule_version == "policyos.runtime.depth_n_cycle_board.v2"
    assert tuple(source.source_id for source in packet.composition_manifest) == (
        *(projection_id.value for projection_id in _GOVERNED_COMPONENT_ORDER),
        "n13b-global-deeper-terminal",
        "ds4-realized-disposition",
        "historical-producer-availability",
    )
    repository_root = Path(__file__).resolve().parents[4]
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

    client_root = repo_root / "packages" / "runtime-api-client"
    committed_ts = (client_root / "runtimeApiClient.ts").read_text(encoding="utf-8")
    committed_js = (client_root / "runtimeApiClient.js").read_text(encoding="utf-8")

    assert committed_ts == expected_ts
    assert committed_js == expected_js

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
    assert (client_root / "canonicalRuntimeApiClient.ts").read_bytes() == (
        canonical_ts.read_bytes()
    )
    assert (client_root / "canonicalRuntimeApiClient.js").read_bytes() == (
        canonical_js.read_bytes()
    )


def _render_openapi_typescript(repo_root: Path, spec_path: Path, output_path: Path) -> None:
    result = subprocess.run(
        [
            "npx",
            "--yes",
            f"openapi-typescript@{OPENAPI_TYPESCRIPT_VERSION}",
            str(spec_path),
            "-o",
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
    manifest = json.loads((client_root / "package.json").read_text(encoding="utf-8"))
    generator = (client_root / "scripts/generate-runtime-api-client.sh").read_text(encoding="utf-8")
    readme = (client_root / "README.md").read_text(encoding="utf-8")
    expected_invocation = f"npx --yes openapi-typescript@{OPENAPI_TYPESCRIPT_VERSION}"

    generate_command = manifest["scripts"]["generate"]
    assert generate_command == "bash ./scripts/generate-runtime-api-client.sh"
    assert expected_invocation in generator
    assert "apps/runtime-dashboard" not in generator
    assert "--prefix" not in generator
    assert "--output-root" in generator
    assert expected_invocation in readme
    assert "npx --prefix apps/runtime-dashboard" not in readme


def test_client_package_entrypoints_generate_only_in_scratch(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    output_root = tmp_path / "generated"
    package_outputs = {
        "packages/runtime-api-client/types.ts",
        "packages/runtime-api-client/runtimeApiClient.ts",
        "packages/runtime-api-client/runtimeApiClient.js",
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


def test_openapi_typescript_output_matches_committed_shared_types(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    spec_path = repo_root / "schemas" / "runtime_api_v1.openapi.json"
    generated = tmp_path / "types.ts"

    _render_openapi_typescript(repo_root, spec_path, generated)

    committed = repo_root / "packages" / "runtime-api-client" / "types.ts"
    assert committed.read_bytes() == generated.read_bytes()


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
