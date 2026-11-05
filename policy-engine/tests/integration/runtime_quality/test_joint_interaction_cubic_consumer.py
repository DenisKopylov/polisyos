from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

PHYSICAL_POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
_CANDIDATE_ONLY_SOURCE_CLAUSE = (
    "all proposals remain candidate-only and must assert target slot, sign, outcome slots, "
    "effect path, and estimand when known."
)
_CANDIDATE_ONLY_SOURCE_QUOTE = "all proposals remain candidate-only"
_SUPPORTED_CANDIDATE_ONLY_CLAIMS = frozenset(
    {
        "All proposals remain candidate-only.",
        "Keep the scenario candidate-only.",
    }
)
_CUBIC_AUTHORED_COMPOSITION_REQUEST = (
    "Using the selected scenario and outcome, assess tax_relief_rate, "
    "procurement_shock_intensity, and budget_allocation_multiplier together as one "
    "hypothetical joint candidate package for simulation. This request does not establish "
    "policy authority, adoption, verified coupling, an effect, or child-to-parent refinement. "
    + _CANDIDATE_ONLY_SOURCE_CLAUSE
)


class _ExactCandidateOnlySpanSupportClient:
    """Support only fixed candidate-only paraphrases from the exact source quote."""

    def __init__(self) -> None:
        self.observations: list[tuple[str, str, str]] = []

    async def generate(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        temperature: float | None = None,
        seed: int | None = None,
    ) -> Any:
        user_content = next(
            (
                message.get("content")
                for message in messages
                if isinstance(message, dict) and message.get("role") == "user"
            ),
            None,
        )
        try:
            payload = json.loads(user_content) if isinstance(user_content, str) else {}
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        claim_text = str(payload.get("claim_text") or "")
        span_text = str(payload.get("span_text") or "")
        exact_source_bound_claim = (
            claim_text in _SUPPORTED_CANDIDATE_ONLY_CLAIMS
            and span_text == _CANDIDATE_ONLY_SOURCE_QUOTE
        )
        decision = "entails" if exact_source_bound_claim else "abstain"
        confidence = 0.93 if exact_source_bound_claim else 0.0
        self.observations.append((claim_text, span_text, decision))

        from tests._helpers.runtime_http import _DeterministicSpanSupportClient

        fixture = _DeterministicSpanSupportClient(
            decision=decision,
            confidence=confidence,
        )
        return await fixture.generate(
            messages=messages,
            tools=tools,
            temperature=temperature,
            seed=seed,
        )


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Route the served compiler and N4 calls through the local recording gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


@pytest.fixture
async def prepared_cubic_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> tuple[Any, Any]:
    """Prepare the source-bound three-child parent without serving or running N5."""
    helper_name = "tests._helpers.generic_n4_served_replay"
    helper_path = (
        Path(__file__).resolve().parents[3] / "tests" / "_helpers" / "generic_n4_served_replay.py"
    )
    helper_spec = importlib.util.spec_from_file_location(helper_name, helper_path)
    assert helper_spec is not None and helper_spec.loader is not None
    generic_n4_served_replay = importlib.util.module_from_spec(helper_spec)
    sys.modules[helper_name] = generic_n4_served_replay
    helper_spec.loader.exec_module(generic_n4_served_replay)
    generic_n4_served_replay.REPO_ROOT = PHYSICAL_POLICY_ENGINE_ROOT

    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "n4-candidate-source-root",
        include_owner_slot_manifest=True,
        owner_knob_dictionary=generic_n4_served_replay._declared_generic_component_knobs(
            "controlled_overlay"
        ),
    )
    prepared = await generic_n4_served_replay.prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
        child_count=3,
        source_root=source_inputs.root,
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
        condition_synthetic_provider_on_child_sources=True,
        raw_request_override=_CUBIC_AUTHORED_COMPOSITION_REQUEST,
    )
    _assert_cubic_root_joint_profile(prepared)
    assert prepared.source_root == source_inputs.root
    assert prepared.app_kwargs["repo_root"] == source_inputs.root
    assert prepared.source_root_witness["n4_repo_root"] == str(source_inputs.root)
    assert prepared.recorded_problem.problem_statement == _CUBIC_AUTHORED_COMPOSITION_REQUEST
    assert prepared.recorded_problem.nl_provenance.raw_request == (
        _CUBIC_AUTHORED_COMPOSITION_REQUEST
    )
    raw_request = str(prepared.request_json["request"]).casefold()
    assert _CANDIDATE_ONLY_SOURCE_CLAUSE in raw_request
    candidate_only_constraint = next(
        constraint
        for constraint in prepared.recorded_problem.constraints
        if constraint.constraint_id == "no_authority_without_a"
    )
    assert candidate_only_constraint.source_text == _CANDIDATE_ONLY_SOURCE_QUOTE
    assert candidate_only_constraint.source_text in raw_request
    assert candidate_only_constraint.description in _SUPPORTED_CANDIDATE_ONLY_CLAIMS
    return generic_n4_served_replay, prepared


def _assert_cubic_parent_owner_grounding(generic_n4_served_replay: Any, prepared: Any) -> None:
    """Require three source-bound owner relations before any runtime consumer call."""
    assert len(prepared.children) == 3
    actual_kref_roots = prepared.source_root_witness["actual_kref_build_repo_roots"]
    assert actual_kref_roots
    assert set(actual_kref_roots) == {str(prepared.source_root)}
    expected_groups = {
        (("budget_allocation_multiplier", "government.balance"),),
        (("procurement_shock_intensity", "cells.distress_score"),),
        (("tax_relief_rate", "global.tax_rate"),),
    }
    actual_groups = {
        generic_n4_served_replay._original_second_capture_child_group(child)
        for child in prepared.children
    }
    assert actual_groups == expected_groups
    assert len(prepared.generic_child_profiles) == 3
    expected_parameters = {
        "budget_allocation_multiplier": ("multiplier", 0.0, 2.0),
        "procurement_shock_intensity": ("intensity", -1.0, 1.0),
        "tax_relief_rate": ("rate", 0.1, 0.3),
    }
    for child, profile in zip(prepared.children, prepared.generic_child_profiles, strict=True):
        expected_group = generic_n4_served_replay._original_second_capture_child_group(child)
        rules = tuple(profile.n5.component_rules)
        assert len(rules) == 1
        (rule,) = rules
        assert (rule.operator_kind, rule.target_world_slot) == expected_group[0]
        assert (rule.parameter_id, float(rule.minimum), float(rule.maximum)) == (
            expected_parameters[rule.operator_kind]
        )
        assert rule.minimum.is_finite() and rule.maximum.is_finite()
        assert rule.target_world_slot in profile.n5.baseline_state

    generation_result = prepared.organ_run.result
    dispositions = generic_n4_served_replay._grounding_disposition_diagnostic(generation_result)
    accepted_relations = {"exact", "certified-specialization"}
    assert len(dispositions) == 3, dispositions
    assert all(
        disposition == "shadow_bound" and relation in accepted_relations
        for _proposal_id, disposition, relation, _cg2_reason, _cg3_reason, _cause in dispositions
    ), dispositions


def _assert_cubic_root_joint_profile(prepared: Any) -> None:
    """Require the prepared root profile to materialize all three owner components."""
    profile = prepared.root_profile
    expected_components = {
        ("budget_allocation_multiplier", "government.balance"),
        ("procurement_shock_intensity", "cells.distress_score"),
        ("tax_relief_rate", "global.tax_rate"),
    }
    rules = tuple(profile.n5.component_rules)
    actual_components = {(rule.operator_kind, rule.target_world_slot) for rule in rules}
    assert len(rules) == 3
    assert actual_components == expected_components
    assert len(profile.n5.ncm_plan_refs) == 1
    assert profile.n5.ncm_plan_refs == (profile.selected_ncm_ref,)
    assert {target for _operator, target in expected_components} <= set(profile.n5.baseline_state)


@pytest.mark.asyncio
async def test_candidate_only_span_support_requires_the_exact_declared_quote() -> None:
    """The test verifier supports one literal limitation and abstains on mutations."""
    client = _ExactCandidateOnlySpanSupportClient()
    tool = {
        "type": "function",
        "function": {"name": "layer3_gy_record_span_support_judgment"},
    }

    async def decide(claim_text: str, span_text: str) -> str:
        response = await client.generate(
            messages=[
                {"role": "system", "content": "test-only source-span judge"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "claim_text": claim_text,
                            "span_text": span_text,
                        },
                        sort_keys=True,
                    ),
                },
            ],
            tools=[tool],
        )
        return str(response.tool_calls[0].arguments["decision"])

    assert await decide("All proposals remain candidate-only.", _CANDIDATE_ONLY_SOURCE_QUOTE) == (
        "entails"
    )
    assert await decide("Keep the scenario candidate-only.", _CANDIDATE_ONLY_SOURCE_QUOTE) == (
        "entails"
    )
    assert await decide("Publication is authorized.", _CANDIDATE_ONLY_SOURCE_QUOTE) == "abstain"
    assert (
        await decide(
            "All proposals remain candidate-only.",
            _CANDIDATE_ONLY_SOURCE_QUOTE + " unless approved.",
        )
        == "abstain"
    )
    assert await decide("All proposals remain candidate-only.", "") == "abstain"
    assert client.observations == [
        ("All proposals remain candidate-only.", _CANDIDATE_ONLY_SOURCE_QUOTE, "entails"),
        ("Keep the scenario candidate-only.", _CANDIDATE_ONLY_SOURCE_QUOTE, "entails"),
        ("Publication is authorized.", _CANDIDATE_ONLY_SOURCE_QUOTE, "abstain"),
        (
            "All proposals remain candidate-only.",
            _CANDIDATE_ONLY_SOURCE_QUOTE + " unless approved.",
            "abstain",
        ),
        ("All proposals remain candidate-only.", "", "abstain"),
    ]


@pytest.mark.asyncio
async def test_cubic_parent_has_three_tracked_owner_relations(
    prepared_cubic_parent: tuple[Any, Any],
) -> None:
    """N4 binds each distinct child to an actual tracked owner mechanism."""
    generic_n4_served_replay, prepared = prepared_cubic_parent
    _assert_cubic_parent_owner_grounding(generic_n4_served_replay, prepared)


@pytest.mark.asyncio
async def test_cubic_joint_residual_survives_persisted_fresh_get_to_n8(
    monkeypatch: pytest.MonkeyPatch,
    prepared_cubic_parent: tuple[Any, Any],
) -> None:
    """A controlled synthetic NCM kernel preserves source-bound cubic samples to N8."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as compiler_owner
    from polisyos.runtime.quality import recursive_generation_cycle as recursive_cycle
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        generic_n4_child_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from tests._helpers.control_worker import dispatch_one_control_job

    generic_n4_served_replay, prepared = prepared_cubic_parent
    _assert_cubic_parent_owner_grounding(generic_n4_served_replay, prepared)

    def controlled_ncm_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        query = state["ncm_query_data"]
        intervention = query.interventions[0]
        del params
        value = 0.0
        if len(intervention) == 3:
            value = 1.0
        return {
            "counterfactual_result": {"world_summaries": [{query.query_vars[0]: {"mean": value}}]}
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(controlled_ncm_step))
    authored_materializations: list[tuple[tuple[Any, ...], tuple[Any, ...]]] = []
    original_persist_authored = recursive_cycle.persist_authored_joint_components

    def observe_authored_materializations(**kwargs: Any) -> Any:
        materializations = tuple(kwargs["component_materializations"])
        members = tuple(kwargs["members"])
        result = original_persist_authored(**kwargs)
        authored_materializations.append((materializations, members))
        return result

    monkeypatch.setattr(
        recursive_cycle,
        "persist_authored_joint_components",
        observe_authored_materializations,
    )
    candidate_only_constraint = next(
        constraint
        for constraint in prepared.recorded_problem.constraints
        if constraint.constraint_id == "no_authority_without_a"
    )
    span_support_client = _ExactCandidateOnlySpanSupportClient()
    original_compiler = compiler_owner.build_design_problem_from_nl_request

    async def compile_with_source_bound_span_support(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = span_support_client
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        compiler_owner,
        "build_design_problem_from_nl_request",
        compile_with_source_bound_span_support,
    )
    request_payload = {
        **prepared.request_json,
        "joint_interaction_candidate_intent": "authored_joint_components.v1",
    }
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        request_json = json.dumps(
            request_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        idempotency_key = "test-r218-" + hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            content=request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        assert len(authored_materializations) == 1
        materializations, source_members = authored_materializations[0]
        assert len(materializations) == len(source_members) == 3
        assert {item.original_atom_hash for item in materializations} == {
            member.source_atom_content_hash for member in source_members
        }
        expected_materialized = {
            "tax_relief_rate": ("global.tax_rate", 0.25),
            "procurement_shock_intensity": ("cells.distress_score", 1.0),
            "budget_allocation_multiplier": ("government.balance", 0.5),
        }
        assert {item.operator_kind for item in materializations} == set(expected_materialized)
        for item in materializations:
            expected_target, expected_value = expected_materialized[item.operator_kind]
            assert item.target_world_slot == expected_target
            assert float(item.value) == expected_value
            assert item.native_input_value == expected_value
            assert item.derived_n5_atom.target_world_slots == (expected_target,)
            assert item.derived_n5_atom.causal_do_expr.write_variables == (expected_target,)
            assignments = item.derived_n5_atom.causal_do_expr.assignments
            assert len(assignments) == 1
            assert assignments[0].value_expr is None
            assert float(assignments[0].value) == expected_value
        assert len(span_support_client.observations) == 1
        observed_claim, observed_span, observed_decision = span_support_client.observations[0]
        assert observed_claim in _SUPPORTED_CANDIDATE_ONLY_CLAIMS
        assert observed_span == _CANDIDATE_ONLY_SOURCE_QUOTE
        assert observed_decision == "entails"
        run_id = str(job.progress["core_run_id"])
        fresh_response = client.get(f"/api/v1/runs/{run_id}")
        assert fresh_response.status_code == 200, fresh_response.text
        fresh_run = fresh_response.json()["run"]
        projection = fresh_run["generic_cycle_simulation"]

        # Bind every served node to the compiled artifact and N4 source that
        # this request actually persisted. The prepared objects are independent
        # semantic controls, not identities for the later served run.
        served_compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        assert served_compiled_ref == ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert (
            str(served_compiled_ref.artifact_id)
            == job.progress["compiled_recursive_generation_cycle_ref"]
        )
        assert served_compiled_ref.manifest_profile_sha256 is not None
        store = service._artifact_store
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            assert store.verify(served_compiled_ref).ok
            compiled = compiler_owner.CompiledRecursiveGenerationCycleRun.model_validate(
                read_core_json_artifact(store, served_compiled_ref).value
            )
        assert compiled.generic_cycle_simulation_handoff is not None
        assert compiled.n4_child_profile_set_ref is not None
        assert compiled.n4_recursive_source_ref is not None
        parent_handoff = compiled.generic_cycle_simulation_handoff
        served_source_run_id = compiled.n4_recursive_source_run_id
        assert served_source_run_id is not None
        assert served_source_run_id == parent_handoff.run_id
        assert compiled.n4_recursive_source_job_id == job.job_id
        assert compiled.n4_recursive_source_tenant_id == prepared.tenant_id
        assert compiled.n4_recursive_source_cell_id == prepared.cell_id
        assert compiled.n4_recursive_source_context_job_ref == parent_handoff.context_job_ref
        assert parent_handoff.n4_child_profile_family_ref is not None
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            served_source = GenerationSourceRepository(store).load(
                compiled.n4_recursive_source_ref,
                run_id=served_source_run_id,
                expected_run_id=parent_handoff.run_id,
                expected_job_id=job.job_id,
                expected_tenant_id=prepared.tenant_id,
                expected_cell_id=prepared.cell_id,
                context_job_ref=compiled.n4_recursive_source_context_job_ref,
                profile_ref=parent_handoff.profile_ref,
                n4_child_profile_family_ref=parent_handoff.n4_child_profile_family_ref,
            )
        assert served_source.problem == compiled.design_problem
        assert (
            compiled.design_problem.problem_statement == prepared.recorded_problem.problem_statement
        )
        assert (
            compiled.design_problem.nl_provenance.raw_request
            == prepared.recorded_problem.nl_provenance.raw_request
            == _CUBIC_AUTHORED_COMPOSITION_REQUEST
        )
        assert (
            compiled.design_problem.outcome_of_interest.target_variable
            == prepared.recorded_problem.outcome_of_interest.target_variable
        )
        served_root_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            compiled.design_problem
        ).removeprefix("sha256:")
        assert compiled.recursive_run.root_node_ref == served_root_node_ref

        served_children = tuple(
            derive_n4_candidate_child_problems(
                served_source.problem,
                served_source.generation_result,
                model_id=served_source.generation_result.model_id,
            )
        )
        assert len(served_children) == 3
        served_source_result_ref = gy_content_hash(
            served_source.generation_result.model_dump(mode="json")
        )
        served_source_atom_refs = {
            str(candidate.atom.content_hash)
            for candidate in served_source.generation_result.candidates
        }
        assert len(served_source_atom_refs) == 3
        served_children_by_selection_ref: dict[str, Any] = {}
        for child in served_children:
            child_atom_refs = tuple(sorted(str(ref) for ref in child.source_atom_refs))
            assert child.source_result_ref == served_source_result_ref
            assert set(child_atom_refs) <= served_source_atom_refs
            assert len(child_atom_refs) == 1
            selection_ref = generic_n4_child_profile_selection_ref(
                child.problem,
                parent_problem_ref=cycle_job_design_problem_ref(served_source.problem),
                source_result_ref=child.source_result_ref,
                source_atom_refs=child_atom_refs,
                semantic_ref=child.semantic_ref,
            )
            assert selection_ref not in served_children_by_selection_ref
            served_children_by_selection_ref[selection_ref] = child
        assert {
            str(ref) for child in served_children for ref in child.source_atom_refs
        } == served_source_atom_refs
        assert len({child.semantic_ref for child in served_children}) == 3

        candidate_before = projection["n5_observations"]
        served_child_bindings = projection["child_profile_bindings"]
        assert len(served_child_bindings) == 3
        bindings_by_selection_ref = {
            binding["profile_selection_ref"]: binding for binding in served_child_bindings
        }
        prepared_profiles_by_selection_ref = {
            profile.profile_selection_ref: profile for profile in prepared.generic_child_profiles
        }
        prepared_groups_by_selection_ref = {
            profile.profile_selection_ref: generic_n4_served_replay._original_second_capture_child_group(
                child
            )
            for child, profile in zip(
                prepared.children, prepared.generic_child_profiles, strict=True
            )
        }
        assert len(bindings_by_selection_ref) == 3
        assert set(bindings_by_selection_ref) == set(prepared.child_keys)
        assert set(bindings_by_selection_ref) == set(prepared_profiles_by_selection_ref)
        assert set(bindings_by_selection_ref) == set(served_children_by_selection_ref)
        for selection_ref, child in served_children_by_selection_ref.items():
            binding = bindings_by_selection_ref[selection_ref]
            child_problem_ref = cycle_job_design_problem_ref(child.problem)
            child_node_ref = "design-problem://" + child_problem_ref.removeprefix("sha256:")
            assert binding["node_ref"] == child_node_ref
            assert binding["design_problem_ref"] == child_problem_ref
            assert binding["source_result_ref"] == child.source_result_ref
            assert binding["source_atom_refs"] == sorted(str(ref) for ref in child.source_atom_refs)
            assert binding["semantic_ref"] == child.semantic_ref
            assert (
                binding["profile_id"]
                == prepared_profiles_by_selection_ref[selection_ref].profile_id
            )
            assert (
                generic_n4_served_replay._original_second_capture_child_group(child)
                == prepared_groups_by_selection_ref[selection_ref]
            )
        child_node_refs = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:")
            for child in served_children_by_selection_ref.values()
        }
        assert len(child_node_refs) == 3
        child_rows_before = [row for row in candidate_before if row["node_ref"] in child_node_refs]
        assert len(child_rows_before) == 3
        assert {row["node_ref"] for row in child_rows_before} == child_node_refs
        assert {row["profile_selection_ref"] for row in child_rows_before} == set(
            prepared.child_keys
        )
        assert all(row["n5_owner_join_status"] == "resolved" for row in child_rows_before)
        source_leaf = next(
            row
            for row in projection["n5_observations"]
            if row["n5_execution_ref"] is not None and row["n8_status"] == "value_conditional"
        )
        assert source_leaf["n5_owner_join_status"] == "resolved"
        owner_artifact_id = str(source_leaf["n5_execution_ref"]["artifact_id"])
        store = service._artifact_store
        original_raw_manifest = store.get_raw_manifest_bytes
        from polisyos.runtime.http.routes import runs as runs_route
        from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result

        selected_result_ref = ArtifactRef.model_validate(source_leaf["simulation_result_ref"])
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            selected_result = load_joint_simulation_result(
                selected_result_ref,
                store=store,
                expected_world_model_record_content_hash=source_leaf[
                    "world_model_record_content_hash"
                ],
                expected_atom_ids=tuple(source_leaf["atom_ids"]),
                expected_selected_outcomes=tuple(source_leaf["selected_outcomes"]),
            )
        selected_result_payload = selected_result.model_dump(mode="json")
        original_n8_qualification = runs_route._n8_interaction_qualification_fields
        fallback_result_observations: list[dict[str, Any]] = []

        def observe_actual_fallback(
            value_port: Any, *, include_status: bool = True, n5_result: Any = None
        ) -> dict[str, Any]:
            # This observes the actual fresh missing-owner branch, then forwards
            # unchanged to its real consumer. It does not manufacture an old v4
            # result: the independent v4-format control qualifies that mapping.
            if not include_status:
                assert n5_result is not None, "actual fallback dropped its selected N5 result"
                if n5_result.receipt.payload_hash == selected_result.receipt.payload_hash:
                    observed = n5_result.model_dump(mode="json")
                    assert observed == selected_result_payload
                    assert n5_result.schema_version == selected_result.schema_version
                    fallback_result_observations.append(observed)
            return original_n8_qualification(
                value_port, include_status=include_status, n5_result=n5_result
            )

        missing_owner_calls: list[str] = []

        def missing_one_owner(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if str(getattr(ref, "artifact_id", "")) == owner_artifact_id:
                missing_owner_calls.append(owner_artifact_id)
                raise FileNotFoundError("synthetic missing selected owner manifest")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as missing_owner:
            missing_owner.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            missing_owner.setattr(
                runs_route, "_n8_interaction_qualification_fields", observe_actual_fallback
            )
            missing_response = client.get(f"/api/v1/runs/{run_id}")
        assert missing_response.status_code == 200, missing_response.text
        assert missing_owner_calls
        assert fallback_result_observations == [selected_result_payload]

        def drop_fallback_result(
            value_port: Any, *, include_status: bool = True, n5_result: Any = None
        ) -> dict[str, Any]:
            return observe_actual_fallback(
                value_port,
                include_status=include_status,
                n5_result=n5_result if include_status else None,
            )

        with monkeypatch.context() as removed_result:
            removed_result.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            removed_result.setattr(
                runs_route, "_n8_interaction_qualification_fields", drop_fallback_result
            )
            with pytest.raises(
                AssertionError, match="actual fallback dropped its selected N5 result"
            ):
                client.get(f"/api/v1/runs/{run_id}")
        restored_response = client.get(f"/api/v1/runs/{run_id}")
        assert restored_response.status_code == 200, restored_response.text
        assert any(
            row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
            and row["n5_owner_join_status"] == "resolved"
            for row in restored_response.json()["run"]["generic_cycle_simulation"][
                "n5_observations"
            ]
        )
        candidates_after = missing_response.json()["run"]["generic_cycle_simulation"][
            "n5_observations"
        ]
        before_keys = {(row["node_ref"], row["candidate_id"]) for row in candidate_before}
        after_keys = {(row["node_ref"], row["candidate_id"]) for row in candidates_after}
        assert len(before_keys) == 3
        assert after_keys == before_keys
        limited_leaf = next(
            row
            for row in candidates_after
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert limited_leaf["status"] == "joint_simulated"
        assert limited_leaf["n5_owner_join_status"] == "unavailable"
        assert limited_leaf["simulation_result_ref"] is not None
        assert (
            sum(
                row["node_ref"] != source_leaf["node_ref"]
                and row["n5_owner_join_status"] == "resolved"
                for row in candidates_after
            )
            == 2
        )
        assert (
            "n5_execution_request_provenance_not_established" in limited_leaf["authority_blockers"]
        )

        # Exercise the same served run through parent profile faults. These are
        # targeted reader failures after the real worker persisted the parent and
        # independently readable children; no parent evidence is invented.
        parent_ref = ArtifactRef.model_validate(
            projection["joint_parent_observations"][0]["simulation_result_ref"]
        )
        from polisyos.core.artifacts import ArtifactOwnershipError
        from polisyos.core.artifacts.ownership import ArtifactReadOnlyUnavailableError

        def is_parent(ref: Any) -> bool:
            return (
                getattr(ref, "artifact_id", None) == parent_ref.artifact_id
                and getattr(ref, "manifest_profile_sha256", None)
                == parent_ref.manifest_profile_sha256
            )

        def checked_parent_limitation(response: Any, code: str) -> None:
            assert response.status_code == 200, response.text
            result = response.json()["run"]["generic_cycle_simulation"]
            assert result["joint_parent_status"] == "not_established"
            assert result["joint_parent_limitation_code"] == code
            assert not result.get("joint_parent_observations", [])
            assert {
                (row["node_ref"], row["candidate_id"]) for row in result["n5_observations"]
            } == before_keys
            assert any(
                row["n5_owner_join_status"] == "resolved" for row in result["n5_observations"]
            )

        def missing_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise FileNotFoundError("synthetic selected parent missing")
            return original_raw_manifest(ref, *args, **kwargs)

        def invalid_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                return b"{"
            return original_raw_manifest(ref, *args, **kwargs)

        def unavailable_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise ArtifactReadOnlyUnavailableError("synthetic backend unavailable")
            return original_raw_manifest(ref, *args, **kwargs)

        for failure, expected_code in (
            (missing_parent, "generic_joint_parent_result_unavailable"),
            (invalid_parent, "generic_joint_parent_result_invalid"),
            (unavailable_parent, "generic_joint_parent_result_unavailable"),
        ):
            with monkeypatch.context() as fault:
                fault.setattr(store, "get_raw_manifest_bytes", failure)
                checked_parent_limitation(client.get(f"/api/v1/runs/{run_id}"), expected_code)

        def denied_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise ArtifactOwnershipError("synthetic selected owner denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_parent)
            denied_response = client.get(f"/api/v1/runs/{run_id}")
        assert denied_response.status_code == 403, denied_response.text
        assert "n5_observations" not in json.dumps(denied_response.json())

        def inaccessible_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise PermissionError("synthetic filesystem permission failure")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", inaccessible_parent)
            unavailable_response = client.get(f"/api/v1/runs/{run_id}")
        assert unavailable_response.status_code == 503, unavailable_response.text
        assert "n5_observations" not in json.dumps(unavailable_response.json())

        # A denial on the first compiled-root read must not be swallowed by
        # the earlier non-generic projection before the generic sibling read.
        compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        for cause, expected_status in (
            (ArtifactOwnershipError("one-shot compiled owner denial"), 403),
            (PermissionError("one-shot compiled filesystem denial"), 503),
        ):
            compiled_denials: list[str] = []

            def deny_first_compiled(
                ref: Any,
                *args: Any,
                _calls: list[str] = compiled_denials,
                _cause: Exception = cause,
                **kwargs: Any,
            ) -> bytes:
                if (
                    not _calls
                    and getattr(ref, "artifact_id", None) == compiled_ref.artifact_id
                    and getattr(ref, "manifest_profile_sha256", None)
                    == compiled_ref.manifest_profile_sha256
                ):
                    _calls.append("denied")
                    raise _cause
                return original_raw_manifest(ref, *args, **kwargs)

            with monkeypatch.context() as fault:
                fault.setattr(store, "get_raw_manifest_bytes", deny_first_compiled)
                compiled_denial = client.get(f"/api/v1/runs/{run_id}")
            assert compiled_denials == ["denied"]
            assert compiled_denial.status_code == expected_status, compiled_denial.text
            assert "n5_observations" not in json.dumps(compiled_denial.json())

        # Reader-scope comparison after a valid selected manifest was opened:
        # the injected different tenant is a simulated fault, not evidence of a
        # real foreign owner grant. The actual selector and request are unchanged.
        original_profile_reader = runs_route.read_core_manifest_profile
        scope_checks: list[str] = []

        def foreign_scope(reader: Any, ref: Any, *args: Any, **kwargs: Any) -> Any:
            manifest, declaration = original_profile_reader(reader, ref, *args, **kwargs)
            if is_parent(ref):
                assert manifest.tenant_context is not None
                scope_checks.append("parent")
                foreign = manifest.tenant_context.model_copy(update={"cell_id": "foreign-cell"})
                manifest = manifest.model_copy(update={"tenant_context": foreign})
            return manifest, declaration

        with monkeypatch.context() as fault:
            fault.setattr(runs_route, "read_core_manifest_profile", foreign_scope)
            foreign_response = client.get(f"/api/v1/runs/{run_id}")
        assert scope_checks
        assert foreign_response.status_code == 403, foreign_response.text
        assert "n5_observations" not in json.dumps(foreign_response.json())

        # A dependency wrapper must not turn an explicitly caused owner denial
        # into candidate unavailability. A typed unavailable cause remains
        # unavailable, and an ordinary filesystem permission cause remains 503.
        from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError

        execution_ref = ArtifactRef.model_validate(source_leaf["n5_execution_ref"])
        wrapped_calls: list[str] = []

        def wrapped_raw(target: ArtifactRef, cause: Exception):
            def read(ref: Any, *args: Any, **kwargs: Any) -> bytes:
                if (
                    getattr(ref, "artifact_id", None) == target.artifact_id
                    and getattr(ref, "manifest_profile_sha256", None)
                    == target.manifest_profile_sha256
                ):
                    wrapped_calls.append(str(target.artifact_id))
                    raise RuntimeDependencyUnavailableError("synthetic-cas") from cause
                return original_raw_manifest(ref, *args, **kwargs)

            return read

        def unavailable_from(cause: Exception) -> ArtifactReadOnlyUnavailableError:
            unavailable = ArtifactReadOnlyUnavailableError("selected read unavailable")
            unavailable.__cause__ = cause
            return unavailable

        for target in (parent_ref, execution_ref):
            for cause, expected_status in (
                (ArtifactOwnershipError("nested owner denial"), 403),
                (PermissionError("nested filesystem permission"), 503),
            ):
                wrapped_calls.clear()
                with monkeypatch.context() as fault:
                    fault.setattr(
                        store,
                        "get_raw_manifest_bytes",
                        wrapped_raw(target, unavailable_from(cause)),
                    )
                    nested_response = client.get(f"/api/v1/runs/{run_id}")
                assert wrapped_calls
                assert nested_response.status_code == expected_status, nested_response.text
                assert "n5_observations" not in json.dumps(nested_response.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, ArtifactOwnershipError("owner denies selected view")),
                )
                wrapped_denial = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            assert wrapped_denial.status_code == 403, wrapped_denial.text
            assert "n5_observations" not in json.dumps(wrapped_denial.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, PermissionError("filesystem refuses selected read")),
                )
                wrapped_permission = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            assert wrapped_permission.status_code == 503, wrapped_permission.text
            assert "n5_observations" not in json.dumps(wrapped_permission.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, ArtifactReadOnlyUnavailableError("reader unavailable")),
                )
                wrapped_unavailable = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            if target == parent_ref:
                checked_parent_limitation(
                    wrapped_unavailable, "generic_joint_parent_result_unavailable"
                )
            else:
                assert wrapped_unavailable.status_code == 200, wrapped_unavailable.text
                wrapped_rows = wrapped_unavailable.json()["run"]["generic_cycle_simulation"][
                    "n5_observations"
                ]
                assert {
                    (row["node_ref"], row["candidate_id"]) for row in wrapped_rows
                } == before_keys
                wrapped_leaf = next(
                    row
                    for row in wrapped_rows
                    if row["node_ref"] == source_leaf["node_ref"]
                    and row["candidate_id"] == source_leaf["candidate_id"]
                )
                assert wrapped_leaf["n5_owner_join_status"] == "unavailable"
                assert (
                    "n5_execution_request_provenance_not_established"
                    in wrapped_leaf["authority_blockers"]
                )
                assert any(
                    row["node_ref"] != source_leaf["node_ref"]
                    and row["n5_owner_join_status"] == "resolved"
                    for row in wrapped_rows
                )

        # The second selected parent read denies access after the first succeeded.
        parent_reads: list[int] = []

        def denied_after_parent_read(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                parent_reads.append(1)
                if len(parent_reads) == 2:
                    raise ArtifactOwnershipError("synthetic post-read owner denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_after_parent_read)
            race_response = client.get(f"/api/v1/runs/{run_id}")
        assert len(parent_reads) == 2
        assert race_response.status_code == 403, race_response.text
        assert "n5_observations" not in json.dumps(race_response.json())

        # Deny a distinct child-source view after another sibling could have
        # been replayed. Permission refusal must suppress the whole response.
        last_leaf = max(candidate_before, key=lambda row: row["node_ref"])
        child_ref = ArtifactRef.model_validate(last_leaf["n4_source_ref"])
        child_denials: list[str] = []

        def denied_child_source(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if (
                getattr(ref, "artifact_id", None) == child_ref.artifact_id
                and getattr(ref, "manifest_profile_sha256", None)
                == child_ref.manifest_profile_sha256
            ):
                child_denials.append("denied")
                raise ArtifactOwnershipError("synthetic child source denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_child_source)
            child_denied_response = client.get(f"/api/v1/runs/{run_id}")
        assert child_denials
        assert child_denied_response.status_code == 403, child_denied_response.text
        assert "n5_observations" not in json.dumps(child_denied_response.json())

        # Present a foreign candidate expectation while the selected execution
        # view is unavailable. The real owner must compare the independently
        # readable input before returning an unknown execution limitation.
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner,
        )

        resolve_owner = GenericCycleSimulationAdmissionOwner.resolve_n5_execution_join
        mismatches: list[str] = []

        def mismatched_owner(owner: Any, ref: Any, *, expected: Any) -> Any:
            if str(ref.artifact_id) == owner_artifact_id:
                mismatches.append(owner_artifact_id)
                expected = expected.model_copy(update={"candidate_id": "foreign-candidate"})
            return resolve_owner(owner, ref, expected=expected)

        missing_owner_calls.clear()
        with monkeypatch.context() as mismatch:
            mismatch.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            mismatch.setattr(
                GenericCycleSimulationAdmissionOwner, "resolve_n5_execution_join", mismatched_owner
            )
            mismatch_response = client.get(f"/api/v1/runs/{run_id}")
        assert mismatch_response.status_code == 200, mismatch_response.text
        assert mismatches
        conflict_projection = mismatch_response.json()["run"]["generic_cycle_simulation"]
        conflict_rows = conflict_projection["n5_observations"]
        assert {(row["node_ref"], row["candidate_id"]) for row in conflict_rows} == before_keys
        assert conflict_projection["publication_authority"] is False
        conflicting_leaf = next(
            row
            for row in conflict_rows
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert conflicting_leaf["status"] == "simulation_blocked"
        assert conflicting_leaf["n8_status"] == "value_blocked"
        assert conflicting_leaf["n5_owner_join_status"] == "mismatch"
        assert (
            conflicting_leaf["n5_owner_join_limitation_code"]
            == "generic_n5_input_cycle_join_mismatch"
        )
        assert not missing_owner_calls
        assert "n5_execution_request_provenance_conflict" in conflicting_leaf["authority_blockers"]

        # The input has a self-hashed complete profile. A different selected
        # seed in the independently supplied expected profile must be a known
        # conflict even when the later execution view is unavailable.
        from polisyos.pdc import gy_content_hash

        profile_mismatches: list[str] = []

        def different_profile(owner: Any, ref: Any, *, expected: Any) -> Any:
            if str(ref.artifact_id) == owner_artifact_id:
                assert expected.profile is not None
                profile_mismatches.append(owner_artifact_id)
                payload = expected.profile.model_dump(mode="json", exclude={"content_hash"})
                payload["n5"]["seed"] += 1
                foreign_profile = type(expected.profile).model_validate(
                    {**payload, "content_hash": gy_content_hash(payload)}
                )
                expected = expected.model_copy(update={"profile": foreign_profile})
            return resolve_owner(owner, ref, expected=expected)

        missing_owner_calls.clear()
        with monkeypatch.context() as mismatch:
            mismatch.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            mismatch.setattr(
                GenericCycleSimulationAdmissionOwner, "resolve_n5_execution_join", different_profile
            )
            profile_response = client.get(f"/api/v1/runs/{run_id}")
        assert profile_response.status_code == 200, profile_response.text
        assert profile_mismatches
        profile_rows = profile_response.json()["run"]["generic_cycle_simulation"]["n5_observations"]
        assert {(row["node_ref"], row["candidate_id"]) for row in profile_rows} == before_keys
        profile_leaf = next(
            row
            for row in profile_rows
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert profile_leaf["status"] == "simulation_blocked"
        assert profile_leaf["n5_owner_join_status"] == "mismatch"
        assert profile_leaf["n5_owner_join_limitation_code"] == (
            "generic_n5_input_cycle_join_mismatch"
        )
        assert any(
            row["node_ref"] != source_leaf["node_ref"] and row["n5_owner_join_status"] == "resolved"
            for row in profile_rows
        )
        assert not missing_owner_calls

    assert projection["joint_parent_status"] == "resolved"
    parent_rows = projection["joint_parent_observations"]
    assert len(parent_rows) == 1
    parent = parent_rows[0]
    assert parent["node_ref"] == served_root_node_ref
    root_nodes = tuple(
        node for node in compiled.recursive_run.nodes if node.node_ref == served_root_node_ref
    )
    assert len(root_nodes) == 1
    (served_root_node,) = root_nodes
    assert served_root_node.joint_candidate_selection is not None
    assert set(served_root_node.joint_candidate_selection.child_node_refs) == child_node_refs
    evidence = parent["n5_interaction_evidence"]
    assert len(parent["atom_ids"]) == 3
    assert len(evidence["interaction_terms"]) == 3
    assert evidence["checked_interaction_orders"] == [1, 2, 3]
    assert parent["n8_candidate_joint_selection_status"] == "resolved"
    assert parent["n8_candidate_joint_selection_content_hash"].startswith("sha256:")
    assert len(parent["n8_candidate_parent_atom_ids"]) == 3
    assert len(parent["n8_candidate_parent_atom_content_hashes"]) == 3
    assert parent["n8_candidate_parent_intervention_ids"] == parent["atom_ids"]
    assert len(parent["n8_candidate_parent_child_refs"]) == 3
    assert parent["n8_candidate_member_basis"] == "authored_materialized_n4_source_members"
    assert parent["n8_source_candidate_relationship"] == "alternatives"
    assert parent["n8_selected_member_relationship"] == "joint_components"
    assert parent["n8_policy_composition_status"] == "authored_candidate"
    assert parent["n8_policy_composition_limitation_code"] == (
        "authored_candidate_coupling_not_established"
    )
    assert parent["n8_child_to_parent_refinement_status"] == "not_established"
    assert parent["n8_child_to_parent_refinement_limitation_code"] == (
        "child_to_parent_refinement_rule_not_established"
    )
    assert parent["n8_joint_scope_status"] == "not_established"
    assert parent["n8_joint_scope_limitation_code"] == (
        "parent_joint_coupling_evidence_not_established"
    )
    assert parent["n8_status"] == "value_conditional"
    assert parent["n8_candidate_decision_grade"] == "low"
    assert parent["n8_candidate_value_ref"] == parent["simulation_result_ref"]["artifact_id"]
    assert parent["n8_numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
    assert "authored_candidate_coupling_not_established" in parent["n8_authority_blockers"]
    assert (
        "n4_source_candidates_are_alternatives_not_authored_compound_design"
        not in parent["n8_authority_blockers"]
    )
    assert "n5_execution_request_provenance_not_established" in parent["n8_authority_blockers"]
    assert evidence["higher_order_residual_sampling_status"] == "estimated"
    assert evidence["numeric_interaction"] == "non_additive"
    assert evidence["numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"

    expected_seeds = [prepared.root_profile.n5.seed, prepared.root_profile.n5.seed + 1]
    outcome = compiled.design_problem.outcome_of_interest.target_variable
    baseline = float(prepared.root_profile.n5.baseline_state[outcome])
    assert parent["replication_seeds"] == expected_seeds
    assert evidence["interaction_sampling_status"] == "estimated"
    expected_pair_keys = {
        frozenset((left, right))
        for index, left in enumerate(parent["atom_ids"])
        for right in parent["atom_ids"][index + 1 :]
    }
    served_pair_rows = evidence["interaction_terms"]
    assert len(served_pair_rows) == len(expected_pair_keys)
    assert {frozenset(term["atom_ids"]) for term in served_pair_rows} == expected_pair_keys
    for term in served_pair_rows:
        summary = term["replication_sampling_by_step"]["0"]
        assert summary["status"] == "estimated"
        assert summary["seeds"] == expected_seeds
        assert summary["samples"] == [
            {"seed": expected_seeds[0], "value": baseline},
            {"seed": expected_seeds[1], "value": baseline},
        ]
        assert summary["mean"] == baseline
        assert summary["standard_error"] == 0.0

    served_residual = evidence["higher_order_residual_sampling"][outcome]["0"]
    assert served_residual["status"] == "estimated"
    assert served_residual["seeds"] == expected_seeds
    assert served_residual["samples"] == [
        {"seed": expected_seeds[0], "value": 1.0 - baseline},
        {"seed": expected_seeds[1], "value": 1.0 - baseline},
    ]
    assert served_residual["mean"] == 1.0 - baseline
    assert served_residual["standard_error"] == pytest.approx(0.0)

    result_ref = ArtifactRef.model_validate(parent["simulation_result_ref"])
    assert result_ref.manifest_profile_sha256 is not None
    result_manifest = service._artifact_store.get_manifest(result_ref)
    assert result_manifest.tenant_context is not None
    assert result_manifest.tenant_context.tenant_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert result_manifest.tenant_context.cell_id == "cell-b26-joint-candidate"
    result = service._artifact_store.get_json(result_ref)
    residual = result["higher_order_residual_sampling"][outcome][0]
    assert residual["samples"] == [
        {"seed": expected_seeds[0], "value": 1.0 - baseline},
        {"seed": expected_seeds[1], "value": 1.0 - baseline},
    ]
    assert residual["mean"] == 1.0 - baseline
    assert residual["standard_error"] == pytest.approx(0.0)
