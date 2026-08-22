from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.routing import APIRoute
from polisyos_tests_runtime_http_conftest import (
    build_runtime_api_env,
    close_runtime_api_env,
)
from pydantic import TypeAdapter, ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.case_inspection_contracts import CaseInspectionResponse
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.run_paper_contracts import (
    RunPaperBlocker,
    RunPaperCaseRecord,
    RunPaperPacket,
    RunPaperRun,
    RunPaperSourceBinding,
    RunPaperStageTrace,
    UnavailableRunPaperCase,
    build_run_paper_semantic_projection,
)
from polisyos.runtime.http.services.run_paper_projection import RunPaperProjectionService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
)


def _run_paper_secure_client(runtime_api_env, *, role: PolicyOSRole, suffix: str):
    bearer = _fixture_bearer(suffix)
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti=f"jwt-{suffix}",
            roles=frozenset({role}),
        ),
    )
    return client, {
        "Authorization": f"Bearer {bearer}",
        "X-Tenant-ID": runtime_api_env["tenant_a"],
    }


def _available_case_payload(packet: dict[str, object]) -> dict[str, object]:
    run = packet["run"]
    assert isinstance(run, dict)
    design_digest = "sha256:" + "c" * 64
    producer = {"component": "polisyos.fixture.run-paper", "version": "1.0.0"}
    design_record = {
        "schema_version": "policyos.policy_design_case.layer2_readiness.v1",
        "record_id": "case.design.fixture",
        "candidate_ref": "candidate://fixture",
        "candidate_source": "deterministic_producer",
        "projection_status": "governed",
        "authority_boundary": {
            "authoritative_for": ["governed_case_projection"],
            "may_not_use_for": ["production_authority"],
            "source_authority": "deterministic_producer",
            "posture": "governed",
            "rule_version_refs": ["policyos.fixture.case.v1"],
        },
        "axis_positions": [],
        "firewall_status": [],
        "envelope": {
            "envelope_id": "case.envelope.fixture",
            "domains": ["fixture"],
            "posture_scopes": ["governed"],
            "epistemic_regime_scopes": ["uncertainty"],
            "actor_scopes": ["actor.fixture"],
            "method_scopes": ["deterministic_fixture"],
            "certified_for": ["governed_case_projection"],
            "not_certified_for": ["production_authority"],
            "cluster_authority_dimension_refs": [],
            "rule_version_ref": "policyos.fixture.case.v1",
        },
        "ledger_refs": [],
        "projection_audiences": ["REVIEWER", "MACHINE"],
    }

    def source_binding(
        role: str,
        digest_character: str,
        validator_id: str,
    ) -> dict[str, object]:
        source_digest = "sha256:" + digest_character * 64
        return {
            "authority_purpose": role,
            "source_ref": {
                "artifact_id": source_digest,
                "kind": f"runtime.case_{role}",
                "media_type": "application/json",
            },
            "source_digest": source_digest,
            "source_schema_name": f"polisyos.runtime.case_{role}",
            "source_schema_version": "1.0.0",
            "producer": producer,
            "verification": {
                "status": "passed",
                "validator_id": validator_id,
                "validator_version": "1.0.0",
                "bound_artifact_content_hash": source_digest,
                "bound_case_id": "case.fixture",
                "bound_run_id": run["run_id"],
                "bound_tenant_id": run["tenant_id"],
                "bound_design_record_record_id": "case.design.fixture",
            },
            "as_of": None,
        }

    def issue(kind: str, digest_character: str) -> dict[str, object]:
        return {
            "issue_id": f"{kind}.fixture",
            "code": f"fixture.{kind}",
            "kind": kind,
            "status_vocabulary_ref": "polisyos.pdc.ObligationRecord.status",
            "status": "accepted_as_limit" if kind == "limitation" else "open",
            "statement": f"{kind} fixture statement",
            "owner_route": f"team-{kind}",
            "source_bindings": [source_binding(kind, digest_character, f"fixture.{kind}")],
        }

    return {
        "availability": "available",
        "case_id": "case.fixture",
        "design_record_binding": {
            "case_id": "case.fixture",
            "run_id": run["run_id"],
            "tenant_id": run["tenant_id"],
            "design_record_ref": {
                "artifact_id": design_digest,
                "kind": "policyos.layer2_s2.design_record_v0",
                "media_type": "application/json",
            },
            "design_record_record_id": "case.design.fixture",
            "schema_name": "policyos.layer2_s2.design_record_v0",
            "schema_version": "policyos.policy_design_case.layer2_readiness.v1",
            "content_digest": design_digest,
            "producer": producer,
        },
        "design_record": design_record,
        "grounding_state": {
            "source_binding": source_binding("grounding_state", "b", "fixture.grounding"),
            "state": "current_valid",
        },
        "admission_state": {
            "source_binding": source_binding("admission_state", "d", "fixture.admission"),
            "state": "admitted_to_claim",
        },
        "promotion_state": {
            "source_binding": source_binding("promotion_state", "e", "fixture.promotion"),
            "state": "governed_promoted",
        },
        "blockers": [issue("blocker", "f")],
        "limitations": [issue("limitation", "0")],
        "objections": [issue("objection", "1")],
        "abstentions": [issue("abstention", "2")],
    }


def _packet_with_recomputed_case(
    packet: dict[str, object],
    case_record: dict[str, object],
) -> dict[str, object]:
    rebound = deepcopy(packet)
    rebound["case_record"] = case_record
    run = RunPaperRun.model_validate(rebound["run"])
    typed_case = TypeAdapter(RunPaperCaseRecord).validate_python(case_record)
    stage_trace = TypeAdapter(RunPaperStageTrace).validate_python(rebound["stage_trace"])
    artifact_links = tuple(
        TypeAdapter(RunPaperPacket.model_fields["artifact_links"].annotation).validate_python(
            rebound["artifact_links"]
        )
    )
    source = RunPaperSourceBinding.model_validate(rebound["source"])
    projection_hash = hash_export_projection(
        build_run_paper_semantic_projection(
            run=run,
            case_record=typed_case,
            stage_trace=stage_trace,
            artifact_links=artifact_links,
            source=source,
        )
    )
    pins = dict(rebound["replay_pins"])
    pins["paper_projection_hash"] = projection_hash
    rebound["replay_pins"] = pins
    rebound["projection_hash"] = projection_hash
    stable_address = str(rebound["stable_address"])
    rebound["replay_address"] = build_export_replay_address(stable_address, pins)
    rebound["report_href"] = (
        build_export_replay_address(f"/runs/{run.run_id}/report", pins) + "#stage-trace"
    )
    return rebound


def test_case_inspection_resolves_bound_case_graph_and_design_record(
    runtime_api_env,
) -> None:
    """Structural witness only; production cannot construct the available arm."""

    packet = (
        runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper").json()
    )
    available = _available_case_payload(packet)

    witness = CaseInspectionResponse.model_validate(_packet_with_recomputed_case(packet, available))

    case = witness.case_record
    assert case.availability == "available"
    assert case.design_record_binding.content_digest == str(
        case.design_record_binding.design_record_ref.artifact_id
    )
    assert case.design_record_binding.design_record_ref.kind == (
        "policyos.layer2_s2.design_record_v0"
    )
    assert case.design_record_binding.design_record_ref.media_type == "application/json"
    assert case.design_record_binding.schema_name == "policyos.layer2_s2.design_record_v0"
    assert (
        case.design_record_binding.schema_version
        == "policyos.policy_design_case.layer2_readiness.v1"
        == case.design_record.schema_version
    )
    assert (
        case.case_id,
        case.design_record.record_id,
        case.design_record_binding.run_id,
        case.design_record_binding.tenant_id,
    ) == (
        case.design_record_binding.case_id,
        case.design_record_binding.design_record_record_id,
        witness.run.run_id,
        witness.run.tenant_id,
    )
    assert (
        case.grounding_state.state,
        case.admission_state.state,
        case.promotion_state.state,
    ) == ("current_valid", "admitted_to_claim", "governed_promoted")
    assert case.grounding_state.vocabulary_ref == (
        "polisyos.runtime.quality.generation_cycle.GroundingStatus"
    )
    assert case.admission_state.vocabulary_ref == (
        "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState"
    )
    assert case.promotion_state.vocabulary_ref == (
        "polisyos.runtime.quality.proving_ground.governed_promotion_gate."
        "Layer3G4PromotionRecord.promotion_state"
    )
    assert [issue.kind for issue in case.blockers] == ["blocker"]
    assert [issue.kind for issue in case.limitations] == ["limitation"]
    assert [issue.kind for issue in case.objections] == ["objection"]
    assert [issue.kind for issue in case.abstentions] == ["abstention"]

    candidate_with_governed_promotion = deepcopy(available)
    candidate_with_governed_promotion["admission_state"]["state"] = "candidate_unverified"
    with pytest.raises(
        ValidationError,
        match="governed promotion requires an admitted authority state",
    ):
        CaseInspectionResponse.model_validate(
            _packet_with_recomputed_case(packet, candidate_with_governed_promotion)
        )


def test_run_paper_returns_typed_case_unavailable_without_defaulting_case_facts(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper")

    assert response.status_code == 200
    packet = response.json()
    assert packet["packet_schema_version"] == "policyos.runtime.run_paper_packet.v1"
    assert packet["projection_rule_version"] == "policyos.runtime.run_paper.v1"
    assert packet["run"]["run_id"] == runtime_api_env["core_run_id"]
    assert packet["run"]["run_terminality"] == "terminal"
    assert packet["case_record"] == {
        "availability": "artifact_missing",
        "capability_state": "producer_missing",
        "closure_signal": "case-record-not-run-bound",
        "may_not_use_for": [
            "case_identity",
            "design_record",
            "grounding_state",
            "admission_state",
            "promotion_state",
            "blockers",
            "limitations",
            "objections",
            "abstentions",
        ],
        "owner_route": "team-runtime",
        "reason_code": "case-record-not-run-bound",
    }
    assert not {
        "case_id",
        "design_record",
        "grounding_state",
        "admission_state",
        "promotion_state",
        "blockers",
        "limitations",
        "objections",
        "abstentions",
    }.intersection(packet["case_record"])


@pytest.mark.parametrize(
    "denied_uses",
    [(), ("case_identity",), ("placeholder",)],
)
def test_run_paper_unavailable_case_requires_complete_canonical_denied_uses(
    denied_uses: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError, match="complete canonical denied-use tuple"):
        UnavailableRunPaperCase(may_not_use_for=denied_uses)


def test_run_paper_requires_complete_recomputed_replay_tuple_and_preserves_bytes(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    stable = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper")

    assert stable.status_code == 200
    packet = stable.json()
    pins = packet["replay_pins"]
    assert set(pins) == {
        "manifest_artifact_id",
        "manifest_schema_version",
        "paper_projection_hash",
        "paper_projection_rule_version",
    }

    replay = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
        params=pins,
    )
    assert replay.status_code == 200
    assert replay.content == stable.content

    partial = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
        params={"manifest_artifact_id": pins["manifest_artifact_id"]},
    )
    assert partial.status_code == 409
    assert partial.json()["code"] == "run_paper_replay_conflict"

    mutations = {
        "manifest_artifact_id": "sha256:" + "1" * 64,
        "manifest_schema_version": "9.9.9",
        "paper_projection_rule_version": "policyos.runtime.run_paper.future",
        "paper_projection_hash": "sha256:" + "0" * 64,
    }
    for field, value in mutations.items():
        mutated = {**pins, field: value}
        mismatch = client.get(
            f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
            params=mutated,
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["code"] == "run_paper_replay_conflict"

    other_generation = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id_secondary']}/paper")
    assert other_generation.status_code == 200
    cross_generation = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
        params=other_generation.json()["replay_pins"],
    )
    assert cross_generation.status_code == 409
    assert cross_generation.json()["code"] == "run_paper_replay_conflict"


def test_run_paper_replay_syntax_rejects_unknown_duplicate_and_malformed_items(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    endpoint = f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper"
    stable = client.get(endpoint)
    pins = stable.json()["replay_pins"]
    pin_items = list(pins.items())
    stale = "sha256:" + "1" * 64

    attempts = (
        [*pin_items, ("unexpected_replay_pin", "stale")],
        [("manifest_artifact_id", stale), *pin_items],
        [*pin_items, ("manifest_artifact_id", stale)],
    )
    for params in attempts:
        response = client.get(endpoint, params=params)
        assert response.status_code == 422
        assert response.json()["code"] == "run_paper_replay_syntax_invalid"

    malformed = client.get(
        endpoint,
        params={**pins, "paper_projection_hash": "sha256:not-a-digest"},
    )
    assert malformed.status_code == 422


def test_run_paper_available_case_rejects_cross_bound_or_candidate_authority(
    runtime_api_env,
) -> None:
    packet = (
        runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper").json()
    )
    available = _available_case_payload(packet)
    with pytest.raises(ValidationError, match="complete paper semantics"):
        RunPaperPacket.model_validate({**packet, "case_record": available})
    RunPaperPacket.model_validate(_packet_with_recomputed_case(packet, available))

    mutations: tuple[tuple[str, tuple[str, ...], str], ...] = (
        (
            "authority digest",
            ("grounding_state", "source_binding", "source_digest"),
            "sha256:" + "d" * 64,
        ),
        (
            "DesignRecord digest",
            ("design_record_binding", "content_digest"),
            "sha256:" + "d" * 64,
        ),
        ("case identity", ("design_record_binding", "case_id"), "case.other"),
        (
            "record identity",
            ("design_record_binding", "design_record_record_id"),
            "case.design.other",
        ),
        ("run identity", ("design_record_binding", "run_id"), "R_other"),
        ("tenant identity", ("design_record_binding", "tenant_id"), "tenant-other"),
        ("candidate promotion", ("admission_state", "state"), "candidate_unverified"),
        (
            "verifier case identity",
            (
                "grounding_state",
                "source_binding",
                "verification",
                "bound_case_id",
            ),
            "case.other",
        ),
    )
    for _label, field_path, value in mutations:
        mutated = deepcopy(available)
        owner = mutated
        for key in field_path[:-1]:
            nested = owner[key]
            assert isinstance(nested, dict)
            owner = nested
        owner[field_path[-1]] = value
        with pytest.raises(ValidationError):
            RunPaperPacket.model_validate(_packet_with_recomputed_case(packet, mutated))

    novel_grounding = deepcopy(available)
    grounding = novel_grounding["grounding_state"]
    assert isinstance(grounding, dict)
    grounding["state"] = "looks_grounded"
    with pytest.raises(ValidationError):
        RunPaperPacket.model_validate(_packet_with_recomputed_case(packet, novel_grounding))

    one_generic_source = deepcopy(available)
    grounding_source = one_generic_source["grounding_state"]
    admission_source = one_generic_source["admission_state"]
    promotion_source = one_generic_source["promotion_state"]
    assert isinstance(grounding_source, dict)
    assert isinstance(admission_source, dict)
    assert isinstance(promotion_source, dict)
    common = grounding_source["source_binding"]
    assert isinstance(common, dict)
    for role, authority_state, validator_id in (
        ("admission_state", admission_source, "fixture.admission"),
        ("promotion_state", promotion_source, "fixture.promotion"),
    ):
        reused = deepcopy(common)
        reused["authority_purpose"] = role
        verification = reused["verification"]
        assert isinstance(verification, dict)
        verification["validator_id"] = validator_id
        authority_state["source_binding"] = reused
    with pytest.raises(ValidationError, match="distinct owner sources"):
        RunPaperPacket.model_validate(_packet_with_recomputed_case(packet, one_generic_source))

    grounding_state = available["grounding_state"]
    assert isinstance(grounding_state, dict)
    source = deepcopy(grounding_state["source_binding"])
    assert isinstance(source, dict)
    source["authority_purpose"] = "blocker"
    with pytest.raises(ValidationError):
        RunPaperBlocker.model_validate(
            {
                "issue_id": "blocker.fixture",
                "code": "fixture_blocker",
                "status": "done-ish",
                "statement": "Fixture blocker.",
                "owner_route": "team-runtime",
                "source_bindings": [source],
            }
        )

    bad_link = deepcopy(packet)
    links = bad_link["artifact_links"]
    assert isinstance(links, list)
    assert links
    first_link = links[0]
    assert isinstance(first_link, dict)
    first_link["href"] = "/api/v1/artifacts/sha256:not-the-ref"
    with pytest.raises(ValidationError, match="derive from artifact_ref"):
        RunPaperPacket.model_validate(bad_link)


def test_run_paper_addresses_serialize_every_pin_before_the_stage_trace_fragment(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper")

    assert response.status_code == 200
    packet = response.json()
    report_address = urlsplit(packet["report_href"])
    assert report_address.path == f"/runs/{runtime_api_env['core_run_id']}/report"
    assert report_address.fragment == "stage-trace"
    assert parse_qs(report_address.query) == {
        key: [value] for key, value in packet["replay_pins"].items()
    }
    assert packet["replay_address"].startswith(packet["stable_address"] + "?")


def test_run_paper_denies_cross_tenant_before_projecting(runtime_api_env) -> None:
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['cross_tenant_run_id']}/paper"
    )

    assert response.status_code == 403
    assert response.json()["code"] == "run_tenant_mismatch"


def test_run_paper_is_review_guarded_before_projection(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    viewer, viewer_headers = _run_paper_secure_client(
        runtime_api_env,
        role=PolicyOSRole.VIEWER,
        suffix="run-paper-viewer",
    )
    routes = [route for route in viewer.app.routes if isinstance(route, APIRoute)]
    paper_routes = [
        route
        for route in routes
        if route.path == "/api/v1/runs/{run_id}/paper" and "GET" in route.methods
    ]

    assert len(paper_routes) == 1
    dependency = get_route_action_permission_dependency(paper_routes[0])
    assert dependency.requirement.permission is RuntimePermission.RUNS_REVIEW
    assert dependency.requirement.resource_binding.source is ResourceBindingSource.TENANT_COLLECTION
    assert dependency.requirement.resource_binding.resource_kind == "runtime.run_paper"

    admitted = runtime_api_env["client"].get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper")
    assert admitted.status_code == 200, admitted.text

    projection_calls: list[str] = []

    def _projection_must_not_run(_service, run_id: str, **_kwargs):
        projection_calls.append(run_id)
        raise AssertionError("paper projection ran before review authorization")

    monkeypatch.setattr(RunPaperProjectionService, "get", _projection_must_not_run)
    denied = viewer.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
        headers=viewer_headers,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"
    assert projection_calls == []


def test_opt_in_run_paper_growth_fixtures_are_real_stable_terminal_packets(
    runtime_api_env,
    tmp_path: Path,
) -> None:
    assert "run_paper_empty_run_id" not in runtime_api_env
    assert "run_paper_growth_run_id" not in runtime_api_env

    envs = []
    try:
        for name in ("first", "second"):
            envs.append(
                build_runtime_api_env(
                    tmp_path / name,
                    include_run_paper_fixtures=True,
                    include_test_client=True,
                )
            )

        for metadata_key, expected_link_count in (
            ("run_paper_empty_run_id", 0),
            ("run_paper_growth_run_id", 64),
        ):
            response_bytes = []
            for env in envs:
                run_id = env[metadata_key]
                response = env["client"].get(f"/api/v1/runs/{run_id}/paper")
                assert response.status_code == 200, response.text
                packet = response.json()
                assert packet["run"] == {
                    "cell_id": env["cell_a"],
                    "duration_ms": 300_000,
                    "finished_at": "2026-01-01T00:05:00Z",
                    "run_id": run_id,
                    "run_terminality": "terminal",
                    "source_kind": "core_run",
                    "started_at": "2026-01-01T00:00:00Z",
                    "status": "completed",
                    "tenant_id": env["tenant_a"],
                }
                assert packet["case_record"]["reason_code"] == ("case-record-not-run-bound")
                links = packet["artifact_links"]
                assert len(links) == expected_link_count
                artifact_ids = [link["artifact_ref"]["artifact_id"] for link in links]
                assert len(artifact_ids) == len(set(artifact_ids))
                assert [link["relation"] for link in links] == ["run_output"] * expected_link_count
                assert [link["href"] for link in links] == [
                    f"/api/v1/artifacts/{artifact_id}" for artifact_id in artifact_ids
                ]
                store = FileSystemCAS(env["cas_root"])
                assert all(store.verify(artifact_id).ok for artifact_id in artifact_ids)
                response_bytes.append(response.content)
            assert response_bytes[0] == response_bytes[1]
    finally:
        for env in envs:
            close_runtime_api_env(env)


def test_corrupt_manifest_bytes_fail_paper_and_stage_trace_resolution_closed(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    initial = client.get(f"/api/v1/runs/{run_id}/paper")
    assert initial.status_code == 200
    manifest_id = initial.json()["replay_pins"]["manifest_artifact_id"]
    digest = manifest_id.removeprefix("sha256:")
    blob = (
        Path(runtime_api_env["cas_root"])
        / "artifacts"
        / "sha256"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.blob"
    )
    blob.write_bytes(blob.read_bytes() + b"\n")

    invalid = client.get(f"/api/v1/runs/{run_id}/paper")
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "run_paper_source_invalid"

    context = client.app.state.runtime_container.runtime_api_context
    resolver = RunPaperProjectionService(
        store=context.store,
        run_index=context.run_index,
        tenant_id=runtime_api_env["tenant_a"],
    )
    assert resolver.resolve(run_id) is None


def test_openapi_exposes_strict_run_paper_union(runtime_api_env) -> None:
    schema = runtime_api_env["client"].get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/runs/{run_id}/paper"]["get"]
    assert operation["operationId"] == "get_run_paper"
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    packet_name = response_schema["$ref"].rsplit("/", 1)[-1]
    case_schema = schema["components"]["schemas"][packet_name]["properties"]["case_record"]
    assert case_schema["discriminator"]["propertyName"] == "availability"
    assert len(case_schema["oneOf"]) == 2
    for arm in case_schema["oneOf"]:
        arm_name = arm["$ref"].rsplit("/", 1)[-1]
        assert schema["components"]["schemas"][arm_name]["additionalProperties"] is False
