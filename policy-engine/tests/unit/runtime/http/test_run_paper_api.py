from __future__ import annotations

from urllib.parse import parse_qs, urlsplit


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
    assert partial.json()["error"]["code"] == "run_paper_replay_conflict"

    mutated = dict(pins)
    mutated["paper_projection_hash"] = "sha256:" + "0" * 64
    mismatch = client.get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper",
        params=mutated,
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "run_paper_replay_conflict"


def test_run_paper_addresses_serialize_every_pin_before_the_stage_trace_fragment(
    runtime_api_env,
) -> None:
    response = runtime_api_env["client"].get(
        f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper"
    )

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
    assert response.json()["error"]["code"] == "run_tenant_mismatch"


def test_openapi_exposes_strict_run_paper_union(runtime_api_env) -> None:
    schema = runtime_api_env["client"].get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/runs/{run_id}/paper"]["get"]
    assert operation["operationId"] == "get_run_paper"
    response_schema = operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    packet_name = response_schema["$ref"].rsplit("/", 1)[-1]
    case_schema = schema["components"]["schemas"][packet_name]["properties"][
        "case_record"
    ]
    assert case_schema["discriminator"]["propertyName"] == "availability"
    assert len(case_schema["oneOf"]) == 2
