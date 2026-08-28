from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.routing import APIRoute
from polisyos_tests_runtime_http_conftest import (
    build_runtime_api_env,
    close_runtime_api_env,
)
from pydantic import TypeAdapter, ValidationError

from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.security import tenant_scope
from polisyos.core.security.identity import PolicyOSRole
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    persist_s2_design_search_run,
    run_s2_shadow_design_loop,
)
from polisyos.runtime.http.authorization import (
    ResourceBindingSource,
    get_route_action_permission_dependency,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.adapters.core_run import derive_core_run_dir
from polisyos.runtime.http.services.case_inspection_contracts import CaseInspectionResponse
from polisyos.runtime.http.services.export_replay import (
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.run_paper_case_record import (
    RunBoundDesignRecordResolver,
)
from polisyos.runtime.http.services.run_paper_contracts import (
    AuthorityAbstainingRunPaperCase,
    RunPaperBlocker,
    RunPaperCaseRecord,
    RunPaperPacket,
    RunPaperRun,
    RunPaperSourceBinding,
    RunPaperSourceError,
    RunPaperStageTrace,
    UnavailableRunPaperCase,
    build_run_paper_semantic_projection,
)
from polisyos.runtime.http.services.run_paper_projection import RunPaperProjectionService
from polisyos.runtime.quality.workspace.s2_design_search_operation import (
    S2_DESIGN_SEARCH_OPERATION_ID,
    execute_s2_design_search_operation,
)
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


def _install_http_bound_case_run(runtime_api_env, *, suffix: str) -> str:
    context = runtime_api_env["client"].app.state.runtime_container.runtime_api_context
    run_id = f"R_bound_{suffix}"
    with tenant_scope(
        None,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    ):
        execute_s2_design_search_operation(
            operation_id=S2_DESIGN_SEARCH_OPERATION_ID,
            search_input=_s2_run_input(),
            store=context.store,
            core_runs_root=context.core_runs_root,
            run_id=run_id,
        )
    context.run_index.refresh(force=True)
    return run_id


def _available_case_payload(packet: dict[str, object]) -> dict[str, object]:
    run = packet["run"]
    assert isinstance(run, dict)
    abstaining_case = packet["case_record"]
    assert isinstance(abstaining_case, dict)
    binding = deepcopy(abstaining_case["design_record_binding"])
    assert isinstance(binding, dict)
    design_record = deepcopy(abstaining_case["design_record"])
    assert isinstance(design_record, dict)
    design_record["projection_status"] = "governed"
    case_id = str(binding["case_id"])
    record_id = str(binding["design_record_record_id"])
    producer = {"component": "polisyos.fixture.run-paper", "version": "1.0.0"}

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
                "bound_case_id": case_id,
                "bound_run_id": run["run_id"],
                "bound_tenant_id": run["tenant_id"],
                "bound_cell_id": run["cell_id"],
                "bound_design_record_record_id": record_id,
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
        "case_id": case_id,
        "design_record_binding": binding,
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


def _s2_run_input() -> Layer2S2DesignSearchInput:
    repository_root = Path(__file__).resolve().parents[4]
    proving_case = json.loads(
        (
            repository_root
            / "architecture/policy_design_case/layer2_first_proving_case.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (
            repository_root
            / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
        ).read_text(encoding="utf-8")
    )
    candidate_space = manifest["candidate_space"]
    return Layer2S2DesignSearchInput(
        case_id=str(proving_case["case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        instrument_families=tuple(candidate_space["instrument_families"]),
        parameter_space={
            str(dimension): tuple(values)
            for dimension, values in candidate_space["parameter_space"].items()
        },
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in proving_case["constructs"]),
        construct_refs=tuple(f"construct://{item}" for item in proving_case["constructs"]),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime(2026, 5, 30, tzinfo=UTC),
    )


def _build_bound_case_run(
    tmp_path: Path,
    *,
    run_id: str = "R_bound-case",
    tenant_id: str = "tenant-bound",
    cell_id: str | None = "cell-bound",
    include_binding_output: bool = True,
):
    store = FileSystemCAS(tmp_path / "cas")
    search_run = run_s2_shadow_design_loop(_s2_run_input())
    persisted = persist_s2_design_search_run(
        search_run,
        store=store,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    core_runs_root = tmp_path / "core-runs"
    context = RunContext.start(
        store,
        registry_bundle,
        producer=ProducerInfo(component="polisyos.runtime.s2_design_search", version="v1"),
        run_dir=core_runs_root / run_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    context.add_output(persisted.design_record_ref)
    context.add_output(persisted.search_ledger_ref)
    if include_binding_output:
        context.add_output(persisted.binding_ref)
    manifest_ref = context.finalize(status="completed")
    return store, core_runs_root, persisted, manifest_ref


def _put_binding_payload(store: FileSystemCAS, payload: object):
    return store.put_json(
        payload,
        PutOptions(
            kind="policyos.pdc.run_bound_design_record_binding",
            media_type="application/json",
            schema=SchemaInfo(
                name="policyos.pdc.run_bound_design_record_binding",
                version="policyos.pdc.run_bound_design_record_binding.v1",
            ),
            producer=ProducerInfo(
                component="polisyos.pdc.layer2_design_search",
                version="policyos.layer2.s2.design_search.v1",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


class _FaultingArtifactStore:
    def __init__(self, store: FileSystemCAS, *, target: str, fault: str) -> None:
        self._store = store
        self._target = target
        self._fault = fault

    def __getattr__(self, name: str):
        return getattr(self._store, name)

    def verify(self, artifact_id):
        if str(artifact_id) == self._target and self._fault == "verify":
            return SimpleNamespace(ok=False)
        return self._store.verify(artifact_id)

    def get_bytes(self, artifact_id):
        if str(artifact_id) == self._target and self._fault == "bytes":
            return b"{}"
        return self._store.get_bytes(artifact_id)

    def get_manifest(self, artifact_id):
        sidecar = self._store.get_manifest(artifact_id)
        if str(artifact_id) != self._target:
            return sidecar
        if self._fault == "kind":
            return sidecar.model_copy(update={"kind": "substituted.kind"})
        if self._fault == "media":
            return sidecar.model_copy(update={"media_type": "text/plain"})
        if self._fault == "schema":
            return sidecar.model_copy(
                update={"artifact_schema": SchemaInfo(name="substituted.schema", version="0")}
            )
        if self._fault == "producer":
            return sidecar.model_copy(
                update={
                    "producer": ProducerInfo(component="substituted.producer", version="0")
                }
            )
        return sidecar


class _SubstitutingArtifactBytesStore:
    def __init__(self, store: FileSystemCAS, *, target: str, replacement: bytes) -> None:
        self._store = store
        self._target = target
        self._replacement = replacement
        self.target_reads = 0

    def __getattr__(self, name: str):
        return getattr(self._store, name)

    def get_bytes(self, artifact_id):
        if str(artifact_id) == self._target:
            self.target_reads += 1
            return self._replacement
        return self._store.get_bytes(artifact_id)


@pytest.mark.parametrize(
    "run_id",
    ["", ".", "..", "../escape", "nested/run", "nested\\run", "/absolute"],
)
def test_terminal_core_run_source_rejects_non_child_run_ids(
    tmp_path: Path,
    run_id: str,
) -> None:
    with pytest.raises(ValueError, match="run_id"):
        derive_core_run_dir(tmp_path / "core-runs", run_id)


def test_s2_operation_requires_exact_id_and_emits_candidate_only_trace(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    core_runs_root = tmp_path / "core-runs"
    run_id = "R_s2-exact-owner"

    with tenant_scope(None, tenant_id="tenant-bound", cell_id="cell-bound"):
        with pytest.raises(ValueError, match="non-owner operation IDs"):
            execute_s2_design_search_operation(
                operation_id="slice0.refine.stub",
                search_input=_s2_run_input(),
                store=store,
                core_runs_root=core_runs_root,
                run_id=run_id,
            )
        result = execute_s2_design_search_operation(
            operation_id=S2_DESIGN_SEARCH_OPERATION_ID,
            search_input=_s2_run_input(),
            store=store,
            core_runs_root=core_runs_root,
            run_id=run_id,
        )

    records = [
        json.loads(line)
        for line in (core_runs_root / run_id / "trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    governed = [record for record in records if str(record["event"]).startswith("S2_")]
    assert [record["event"] for record in governed] == [
        "S2_APPLICABILITY_RECORDED",
        "S2_OPERATION_INVOCATION_RECORDED",
        "S2_SEARCH_LEDGER_RECORDED",
        "S2_ARTIFACT_ENVELOPE_RECORDED",
    ]
    assert all(
        record["metrics"] == {"authority_bearing": 0, "candidate_only": 1}
        for record in governed
    )
    assert records[-1]["event"] == "RUN_FINALIZED"
    assert records[-1]["refs"]["outputs"] == [result.manifest_ref.model_dump(mode="json")]


def test_case_inspection_resolves_bound_case_graph_and_design_record(
    runtime_api_env,
) -> None:
    """Structural witness only; production cannot construct the available arm."""

    run_id = _install_http_bound_case_run(runtime_api_env, suffix="available_witness")
    packet = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/paper").json()
    available = _available_case_payload(packet)

    witness = CaseInspectionResponse.model_validate(_packet_with_recomputed_case(packet, available))

    case = witness.case_record
    assert case.availability == "available"
    assert case.design_record_binding.design_record_content_digest == str(
        case.design_record_binding.design_record_ref.artifact_id
    )
    assert case.design_record_binding.design_record_ref.kind == (
        "policyos.layer2_s2.design_record_v0"
    )
    assert case.design_record_binding.design_record_ref.media_type == "application/json"
    assert case.design_record_binding.design_record_schema_name == (
        "policyos.layer2_s2.design_record_v0"
    )
    assert (
        case.design_record_binding.design_record_schema_version
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


def test_run_paper_rejects_terminal_run_without_exact_case_binding(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    response = client.get(f"/api/v1/runs/{runtime_api_env['core_run_id']}/paper")

    assert response.status_code == 409
    assert response.json()["code"] == "run_paper_source_invalid"
    assert "exactly one run-bound DesignRecord binding" in response.json()["detail"]


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
    run_id = _install_http_bound_case_run(runtime_api_env, suffix="replay_primary")
    stable = client.get(f"/api/v1/runs/{run_id}/paper")

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
        f"/api/v1/runs/{run_id}/paper",
        params=pins,
    )
    assert replay.status_code == 200
    assert replay.content == stable.content

    partial = client.get(
        f"/api/v1/runs/{run_id}/paper",
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
            f"/api/v1/runs/{run_id}/paper",
            params=mutated,
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["code"] == "run_paper_replay_conflict"

    other_run_id = _install_http_bound_case_run(runtime_api_env, suffix="replay_secondary")
    other_generation = client.get(f"/api/v1/runs/{other_run_id}/paper")
    assert other_generation.status_code == 200
    cross_generation = client.get(
        f"/api/v1/runs/{run_id}/paper",
        params=other_generation.json()["replay_pins"],
    )
    assert cross_generation.status_code == 409
    assert cross_generation.json()["code"] == "run_paper_replay_conflict"


def test_run_paper_replay_syntax_rejects_unknown_duplicate_and_malformed_items(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = _install_http_bound_case_run(runtime_api_env, suffix="replay_syntax")
    endpoint = f"/api/v1/runs/{run_id}/paper"
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
    run_id = _install_http_bound_case_run(runtime_api_env, suffix="available_negative")
    packet = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/paper").json()
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
            ("design_record_binding", "design_record_content_digest"),
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
    run_id = _install_http_bound_case_run(runtime_api_env, suffix="addresses")
    response = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/paper")

    assert response.status_code == 200
    packet = response.json()
    report_address = urlsplit(packet["report_href"])
    assert report_address.path == f"/runs/{run_id}/report"
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

    run_id = _install_http_bound_case_run(runtime_api_env, suffix="review_guard")
    admitted = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}/paper")
    assert admitted.status_code == 200, admitted.text

    projection_calls: list[str] = []

    def _projection_must_not_run(_service, run_id: str, **_kwargs):
        projection_calls.append(run_id)
        raise AssertionError("paper projection ran before review authorization")

    monkeypatch.setattr(RunPaperProjectionService, "get", _projection_must_not_run)
    denied = viewer.get(
        f"/api/v1/runs/{run_id}/paper",
        headers=viewer_headers,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "action_permission_denied"
    assert projection_calls == []


def test_opt_in_legacy_run_paper_fixtures_fail_closed_without_case_binding(
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

        for metadata_key in ("run_paper_empty_run_id", "run_paper_growth_run_id"):
            response_bytes = []
            for env in envs:
                run_id = env[metadata_key]
                response = env["client"].get(f"/api/v1/runs/{run_id}/paper")
                assert response.status_code == 409, response.text
                assert response.json()["code"] == "run_paper_source_invalid"
                assert "exactly one run-bound DesignRecord binding" in response.json()["detail"]
                response_bytes.append(response.content)
            assert [json.loads(value)["code"] for value in response_bytes] == [
                "run_paper_source_invalid",
                "run_paper_source_invalid",
            ]
    finally:
        for env in envs:
            close_runtime_api_env(env)


def test_corrupt_manifest_bytes_fail_paper_and_stage_trace_resolution_closed(
    runtime_api_env,
) -> None:
    client = runtime_api_env["client"]
    run_id = _install_http_bound_case_run(runtime_api_env, suffix="corrupt_manifest")
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
        core_runs_root=context.core_runs_root,
        tenant_id=runtime_api_env["tenant_a"],
    )
    assert resolver.resolve(run_id) is None


def test_run_bound_case_resolver_uses_only_the_unique_terminal_trace_binding(
    tmp_path: Path,
) -> None:
    store, core_runs_root, persisted, manifest_ref = _build_bound_case_run(tmp_path)

    resolved = RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")

    assert resolved.terminal_source.manifest_ref == manifest_ref
    assert resolved.binding_ref == persisted.binding_ref
    assert resolved.binding == persisted.binding
    assert resolved.design_record.record_id == persisted.binding.design_record_record_id
    assert resolved.search_ledger.ledger_id == persisted.binding.search_ledger_id
    assert resolved.search_ledger.case_id == persisted.binding.case_id


def test_run_bound_case_resolver_hashes_the_exact_manifest_bytes_it_parses(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, manifest_ref = _build_bound_case_run(tmp_path)
    original = store.get_bytes(manifest_ref.artifact_id)
    alternate_payload = from_canonical_bytes(original)
    assert isinstance(alternate_payload, dict)
    alternate_payload["status"] = "alternate-valid-manifest"
    alternate = to_canonical_bytes(alternate_payload)
    assert alternate != original
    substituting_store = _SubstitutingArtifactBytesStore(
        store,
        target=str(manifest_ref.artifact_id),
        replacement=alternate,
    )

    with pytest.raises(RunPaperSourceError, match="manifest"):
        RunBoundDesignRecordResolver(substituting_store, core_runs_root).resolve("R_bound-case")

    assert substituting_store.target_reads == 1


def test_run_bound_case_resolver_rejects_an_outside_trace_symlink(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    trace_path = core_runs_root / "R_bound-case" / "trace.jsonl"
    outside_trace = tmp_path / "outside-trace.jsonl"
    outside_trace.write_bytes(trace_path.read_bytes())
    trace_path.unlink()
    trace_path.symlink_to(outside_trace)

    with pytest.raises(RunPaperSourceError, match="trace"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")


def test_run_bound_case_resolver_rejects_a_swapped_outside_run_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    run_id = "R_bound-case"
    run_dir = core_runs_root / run_id
    held_run_dir = tmp_path / "held-run"
    outside_run_dir = tmp_path / "outside-run"
    outside_run_dir.mkdir()
    (outside_run_dir / "trace.jsonl").write_bytes((run_dir / "trace.jsonl").read_bytes())
    real_open = os.open
    swapped = False

    def _swap_before_run_directory_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        direct_run_open = dir_fd is None and Path(path) == run_dir
        descriptor_child_open = dir_fd is not None and path == run_id
        if not swapped and (direct_run_open or descriptor_child_open):
            run_dir.rename(held_run_dir)
            run_dir.symlink_to(outside_run_dir, target_is_directory=True)
            swapped = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", _swap_before_run_directory_open)

    with pytest.raises(RunPaperSourceError, match="trace"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve(run_id)

    assert swapped is True


def test_run_bound_case_resolver_rejects_every_intermediate_terminal_fact(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    trace_path = core_runs_root / "R_bound-case" / "trace.jsonl"
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    intermediate = deepcopy(records[0])
    intermediate["phase"] = "pdc.gy"
    intermediate["event"] = "INTERMEDIATE_TERMINAL_FACT"
    intermediate["run_terminality"] = "terminal"
    trace_path.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in [records[0], intermediate, *records[1:]]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RunPaperSourceError, match="terminal"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")


@pytest.mark.parametrize(
    ("field", "substituted"),
    [
        ("run_id", "R_other"),
        ("tenant_id", "tenant-other"),
        ("cell_id", "cell-other"),
    ],
)
def test_run_bound_case_resolver_rejects_owner_substitution_with_constant_record_hash(
    tmp_path: Path,
    field: str,
    substituted: str,
) -> None:
    run_id = "R_binding-owner"
    tenant_id = "tenant-bound"
    cell_id = "cell-bound"
    store = FileSystemCAS(tmp_path / "cas")
    search_run = run_s2_shadow_design_loop(_s2_run_input())
    persisted = persist_s2_design_search_run(
        search_run,
        store=store,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    substituted_binding = persisted.binding.model_copy(update={field: substituted})
    substituted_binding_ref = _put_binding_payload(
        store,
        substituted_binding.model_dump(mode="json"),
    )
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    core_runs_root = tmp_path / "core-runs"
    context = RunContext.start(
        store,
        registry_bundle,
        run_dir=core_runs_root / run_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    context.add_output(persisted.design_record_ref)
    context.add_output(persisted.search_ledger_ref)
    context.add_output(substituted_binding_ref)
    context.finalize()

    with pytest.raises(RunPaperSourceError, match="owner identity"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve(run_id)


@pytest.mark.parametrize(
    ("field", "substituted"),
    [("case_id", "case-other"), ("ledger_id", "ledger-other")],
)
def test_run_bound_case_resolver_rejects_verified_ledger_identity_substitution(
    tmp_path: Path,
    field: str,
    substituted: str,
) -> None:
    run_id = "R_binding-ledger"
    store = FileSystemCAS(tmp_path / "cas")
    search_run = run_s2_shadow_design_loop(_s2_run_input())
    persisted = persist_s2_design_search_run(
        search_run,
        store=store,
        run_id=run_id,
        tenant_id="tenant-bound",
        cell_id="cell-bound",
    )
    producer = persisted.binding.producer
    substituted_ledger = search_run.search_ledger.model_copy(update={field: substituted})
    substituted_ledger_ref = store.put_json(
        substituted_ledger.model_dump(mode="json"),
        PutOptions(
            kind="policyos.layer2_s2.search_ledger",
            media_type="application/json",
            schema=SchemaInfo(
                name="policyos.layer2_s2.search_ledger",
                version="policyos.policy_design_case.layer2_s2_design_search.v1",
            ),
            producer=producer,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    substituted_binding = persisted.binding.model_copy(
        update={
            "search_ledger_ref": substituted_ledger_ref,
            "search_ledger_content_digest": str(substituted_ledger_ref.artifact_id),
        }
    )
    substituted_binding_ref = _put_binding_payload(
        store,
        substituted_binding.model_dump(mode="json"),
    )
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    core_runs_root = tmp_path / "core-runs"
    context = RunContext.start(
        store,
        registry_bundle,
        run_dir=core_runs_root / run_id,
        run_id=run_id,
        tenant_id="tenant-bound",
        cell_id="cell-bound",
    )
    context.add_output(persisted.design_record_ref)
    context.add_output(substituted_ledger_ref)
    context.add_output(substituted_binding_ref)
    context.finalize()

    with pytest.raises(RunPaperSourceError, match="SearchLedger"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve(run_id)


def test_run_bound_case_resolver_rejects_a_cas_decoy_not_named_by_terminal_manifest(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(
        tmp_path,
        include_binding_output=False,
    )

    with pytest.raises(RunPaperSourceError, match="binding"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")


@pytest.mark.parametrize("role", ["manifest", "binding", "design_record", "search_ledger"])
@pytest.mark.parametrize("fault", ["verify", "bytes", "kind", "media", "schema", "producer"])
def test_run_bound_case_resolver_rejects_every_cas_role_falsifier(
    tmp_path: Path,
    role: str,
    fault: str,
) -> None:
    store, core_runs_root, persisted, manifest_ref = _build_bound_case_run(tmp_path)
    targets = {
        "manifest": str(manifest_ref.artifact_id),
        "binding": str(persisted.binding_ref.artifact_id),
        "design_record": str(persisted.design_record_ref.artifact_id),
        "search_ledger": str(persisted.search_ledger_ref.artifact_id),
    }
    faulting_store = _FaultingArtifactStore(store, target=targets[role], fault=fault)

    with pytest.raises(RunPaperSourceError):
        RunBoundDesignRecordResolver(faulting_store, core_runs_root).resolve("R_bound-case")


def test_run_bound_case_resolver_rejects_missing_and_duplicate_terminal_closure(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    trace_path = core_runs_root / "R_bound-case" / "trace.jsonl"
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    terminal = lines[-1]
    trace_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(RunPaperSourceError, match="terminal"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")

    trace_path.write_text("\n".join([*lines, terminal]) + "\n", encoding="utf-8")
    with pytest.raises(RunPaperSourceError, match="terminal"):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")


@pytest.mark.parametrize(
    "mutation",
    ["missing_start", "owner_mismatch", "event_before_start", "conflicting_terminal"],
)
def test_run_bound_case_resolver_rejects_trace_owner_and_conflict_set(
    tmp_path: Path,
    mutation: str,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    trace_path = core_runs_root / "R_bound-case" / "trace.jsonl"
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    if mutation == "missing_start":
        records = records[1:]
    elif mutation == "owner_mismatch":
        records[0]["tenant_id"] = "tenant-other"
    elif mutation == "event_before_start":
        records[0], records[1] = records[1], records[0]
    else:
        conflicting = deepcopy(records[-1])
        conflicting["refs"]["outputs"][0]["artifact_id"] = "sha256:" + "0" * 64
        records.append(conflicting)
    trace_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )

    with pytest.raises(RunPaperSourceError):
        RunBoundDesignRecordResolver(store, core_runs_root).resolve("R_bound-case")


def test_authority_abstaining_case_rejects_nonreceipt_in_the_wrong_role(
    tmp_path: Path,
) -> None:
    store, core_runs_root, _persisted, _manifest_ref = _build_bound_case_run(tmp_path)
    packet = RunPaperProjectionService(
        store=store,
        core_runs_root=core_runs_root,
        tenant_id="tenant-bound",
    ).get("R_bound-case")
    assert isinstance(packet.case_record, AuthorityAbstainingRunPaperCase)
    assert packet.case_record.authority_projection == "abstained"
    assert packet.case_record.grounding_nonreceipt.missing_authority == (
        "generation_cycle_grounding_authority"
    )
    assert packet.case_record.admission_nonreceipt.missing_authority == (
        "hypothesis_ledger_admission_authority"
    )
    assert packet.case_record.promotion_nonreceipt.missing_authority == (
        "layer3_g4_promotion_authority"
    )

    payload = packet.case_record.model_dump(mode="python")
    payload["grounding_nonreceipt"] = payload["admission_nonreceipt"]
    with pytest.raises(ValidationError, match="grounding"):
        AuthorityAbstainingRunPaperCase.model_validate(payload)


def test_openapi_exposes_strict_run_paper_union(runtime_api_env) -> None:
    schema = runtime_api_env["client"].get("/openapi.json").json()

    operation = schema["paths"]["/api/v1/runs/{run_id}/paper"]["get"]
    assert operation["operationId"] == "get_run_paper"
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    packet_name = response_schema["$ref"].rsplit("/", 1)[-1]
    case_schema = schema["components"]["schemas"][packet_name]["properties"]["case_record"]
    assert case_schema["discriminator"]["propertyName"] == "availability"
    assert len(case_schema["oneOf"]) == 3
    for arm in case_schema["oneOf"]:
        arm_name = arm["$ref"].rsplit("/", 1)[-1]
        assert schema["components"]["schemas"][arm_name]["additionalProperties"] is False
