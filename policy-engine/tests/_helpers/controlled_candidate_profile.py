"""Shared controlled candidate-scenario inputs for served N4→N5 tests.

The fixture remains candidate-only: the replay changes one integer parameter and
records its exact target/outcome path; the configured model is a declared synthetic
SCM and does not establish empirical grounding, source time, S8, or N9 authority.
"""

from __future__ import annotations

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.ir.artifacts import ArtifactStore
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class ControlledCandidateGateway:
    """Small OpenAI-compatible local gateway for the real traced-client factory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._recording: dict[str, object] | None = None
        self._problem: dict[str, object] | None = None
        self._n4_cursor = 0

        class Handler(BaseHTTPRequestHandler):
            owner: ControlledCandidateGateway

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/v1/models":
                    self._send_json(404, {"error": "not_found"})
                    return
                with self.owner._lock:
                    recording = self.owner._recording
                if recording is None:
                    self._send_json(503, {"error": "fixture_not_selected"})
                    return
                with self.owner._lock:
                    self.owner._n4_cursor = 0
                self._send_json(
                    200,
                    {"data": [{"id": recording["model_id"], "object": "model"}]},
                )

            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/v1/chat/completions":
                    self._send_json(404, {"error": "not_found"})
                    return
                try:
                    request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self._send_json(400, {"error": "malformed_request"})
                    return
                if not isinstance(request, dict):
                    self._send_json(400, {"error": "malformed_request"})
                    return
                compiler_name = self._compiler_tool_name(request)
                if compiler_name is not None:
                    with self.owner._lock:
                        problem = self.owner._problem
                        self.owner._n4_cursor = 0
                    if problem is None:
                        self._send_json(503, {"error": "fixture_not_selected"})
                        return
                    completion = {
                        "id": "synthetic-design-problem-completion",
                        "object": "chat.completion",
                        "model": request.get("model"),
                        "provider": "controlled_local_gateway",
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [
                                        {
                                            "id": "synthetic-design-problem-tool-call",
                                            "type": "function",
                                            "function": {
                                                "name": compiler_name,
                                                "arguments": json.dumps(
                                                    problem,
                                                    sort_keys=True,
                                                    separators=(",", ":"),
                                                ),
                                            },
                                        }
                                    ],
                                },
                                "finish_reason": "tool_calls",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }
                    self._send_json(200, completion)
                    return

                with self.owner._lock:
                    recording = self.owner._recording
                    if recording is None:
                        response = None
                    else:
                        responses = recording.get("responses")
                        if not isinstance(responses, list) or self.owner._n4_cursor >= len(
                            responses
                        ):
                            response = None
                        else:
                            response = responses[self.owner._n4_cursor]
                            self.owner._n4_cursor += 1
                if not isinstance(response, dict):
                    self._send_json(502, {"error": "synthetic_response_exhausted"})
                    return
                if response.get("status") == "error":
                    error = response.get("error")
                    error_payload = error if isinstance(error, dict) else {}
                    self._send_json(
                        502,
                        {
                            "error": {
                                "type": error_payload.get("type") or "synthetic_gateway_error",
                                "code": error_payload.get("code"),
                                "message": error_payload.get("message")
                                or "controlled fixture provider error",
                            }
                        },
                    )
                    return
                content = response.get("raw_response")
                if not isinstance(content, str):
                    self._send_json(502, {"error": "synthetic_response_malformed"})
                    return
                usage = response.get("usage")
                usage_payload = usage if isinstance(usage, dict) else {}
                self._send_json(
                    200,
                    {
                        "id": "synthetic-candidate-completion",
                        "object": "chat.completion",
                        "model": request.get("model"),
                        "provider": "controlled_recorded_response",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": content},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": usage_payload.get("prompt_tokens") or 0,
                            "completion_tokens": usage_payload.get("completion_tokens") or 0,
                            "total_tokens": usage_payload.get("total_tokens") or 0,
                        },
                    },
                )

            @staticmethod
            def _compiler_tool_name(request: dict[str, object]) -> str | None:
                tools = request.get("tools")
                if not isinstance(tools, list):
                    return None
                for tool in tools:
                    if not isinstance(tool, dict):
                        continue
                    function = tool.get("function")
                    if not isinstance(function, dict):
                        continue
                    name = function.get("name")
                    if name == "emit_design_problem":
                        return name
                return None

            def _send_json(self, status: int, payload: object) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *args: object) -> None:
                del args

        Handler.owner = self
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        """Return this test server's ephemeral OpenAI-compatible API root."""
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"

    def __enter__(self) -> ControlledCandidateGateway:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def set_fixture(
        self,
        recording: dict[str, object],
        *,
        problem: object,
    ) -> None:
        """Select one immutable synthetic overlay and its compiler product."""
        self._validate_recording(recording)
        model_dump = getattr(problem, "model_dump", None)
        if not callable(model_dump):
            raise TypeError("controlled_gateway_problem_untyped")
        problem_payload = model_dump(mode="json")
        if not isinstance(problem_payload, dict):
            raise TypeError("controlled_gateway_problem_untyped")
        with self._lock:
            self._recording = copy.deepcopy(recording)
            self._problem = copy.deepcopy(problem_payload)
            self._n4_cursor = 0

    @staticmethod
    def _validate_recording(recording: dict[str, object]) -> None:
        n4_contract._validate_recording_fixture(recording)  # type: ignore[arg-type]


def _current_compiler_problem(recording: dict[str, object]):
    """Build honest current-schema compiler arguments without rewriting replay bytes."""

    historical = n4_contract._design_problem(recording)
    source_text = "all proposals remain candidate-only"
    assert source_text in historical.nl_provenance.raw_request
    constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": source_text,
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in historical.constraints
    ]
    return historical.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": constraints,
        }
    )


def _controlled_procurement_recording(
    recording: dict[str, object], *, outcome_variable: str, intensity: int = 1
) -> dict[str, object]:
    """Return a new synthetic fixture identity for a controlled N4 replay overlay."""

    from polisyos.pdc import gy_content_hash

    controlled = copy.deepcopy(recording)
    base_recording_id = str(controlled.get("recording_id") or "recording")
    base_content_hash = str(controlled.get("recording_content_hash") or "")
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        procurement = next(
            item for item in interventions if item.get("kind") == "procurement_shock_intensity"
        )
        procurement["params"] = {"intensity": intensity}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=cells.distress_score,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    # Edited provider bytes are a synthetic test fixture, not the historical
    # provider capture. Give the overlay an identity derived from its changed
    # bytes and retain an explicit lineage pointer to the immutable source.
    identity_seed = gy_content_hash(
        {
            "base_recording_id": base_recording_id,
            "base_content_hash": base_content_hash,
            "response_hashes": [
                item.get("raw_response_hash") for item in responses if isinstance(item, dict)
            ],
            "outcome_variable": outcome_variable,
            "intensity": intensity,
        }
    ).removeprefix("sha256:")[:20]
    fixture_id = f"synthetic_controlled_n4_{identity_seed}"
    controlled["fixture_id"] = fixture_id
    controlled["recording_id"] = fixture_id
    controlled["recording_source"] = "synthetic_controlled_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = base_recording_id
    controlled["derived_from_content_hash"] = base_content_hash

    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)
    return controlled


def _configured_procurement_profile(
    *,
    recorded_problem: object,
    artifact_store: ArtifactStore,
    tenant_id: str,
    cell_id: str,
):
    """Return a configured candidate profile and its explicit synthetic SCM."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        ExogenousSpec,
        NCMSpec,
        StructuralEquation,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash, world_model_record_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from tests.unit.runtime.quality.test_generation_cycle import (
        _cyc01_owner_bound_n5_case,
        _record_with_selected_ncm_ref,
    )

    base_problem, base_context, _candidate = _cyc01_owner_bound_n5_case(
        problem_seed=recorded_problem
    )
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    ncm = NCMSpec(
        endogenous_vars=["cells.distress_score", outcome_variable],
        exogenous_specs=[
            ExogenousSpec(
                variable="u_distress",
                associated_endogenous="cells.distress_score",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
            ExogenousSpec(
                variable="u_output",
                associated_endogenous=outcome_variable,
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
        ],
        structural_equations=[
            StructuralEquation(
                variable="cells.distress_score",
                parents=[],
                exogenous="u_distress",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable=outcome_variable,
                parents=["cells.distress_score"],
                exogenous="u_output",
                equation_type="linear",
                equation_params={
                    "intercept": 0.0,
                    "coefficients": {"cells.distress_score": 0.5},
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="synthetic_candidate_profile_fixture",
    )
    with tenant_scope(
        None,
        tenant_id=tenant_id,
        cell_id=cell_id,
    ):
        ncm_ref = persist_ncm_spec(_ensure_ir_artifact_store(artifact_store), ncm)

    candidate_slots = tuple(
        dict.fromkeys(
            [lever.target_slot for lever in recorded_problem.candidate_lever_space.candidate_levers]
            + ["global.tax_rate", "cells.distress_score", outcome_variable]
        )
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome=outcome_variable,
        policy_slot_ids=candidate_slots,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
    )
    bindings = tuple(
        item.model_copy(update={"unit": "synthetic_score"}) for item in world.policy_slot_map
    )
    foundry = world.foundry_binding_ref.model_copy(
        update={
            "state_slot_digest": gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [item.model_dump(mode="json") for item in bindings],
                }
            )
        }
    )
    draft = world.model_copy(update={"policy_slot_map": bindings, "foundry_binding_ref": foundry})
    world = draft.model_copy(
        update={
            "content_hash": world_model_record_content_hash(draft),
            "world_model_record_id": (
                "world_model_record_"
                + world_model_record_content_hash(draft).removeprefix("sha256:")[:16]
            ),
        }
    )
    world = _record_with_selected_ncm_ref(world, str(ncm_ref.artifact_id))
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=load_l6_intervention_substrate(REPO_ROOT),
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="procurement_shock_intensity",
        parameter_id="intensity",
        target_world_slot="cells.distress_score",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://r1/controlled-candidate-n5",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"cells.distress_score": 0.0, outcome_variable: 0.0},
        seed=11,
        replications=2,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft_profile = CandidateSimulationScenarioProfile.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    declaration_fields = {
        "schema_version": ("policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": rule.unit_id,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    return profile, declaration
