from __future__ import annotations

import ast
import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality import design_generation as dg
from polisyos.runtime.quality.credal_reference import build_credal_reference
from polisyos.runtime.quality.design_generation import (
    SUPPORTED_GENERATION_MODEL_IDS,
    DesignGenerationError,
    SurrogateRanking,
    firewall_issues_for_result,
    generate_design_candidates_under_a,
    validate_design_generation_strangle_receipts,
)
from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent
from polisyos.scientist.agent.formalizer import (
    LLMFormalizerAgent,
    trinity_bundle_formalizer_generator_path,
)
from polisyos.scientist.agent.protocols import DraftResult
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayUsage,
)
from tools.quality.validation import check_layer3_gy_design_generation_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[4]
DESIGN_GENERATION_PATH = REPO_ROOT / "src/polisyos/runtime/quality/design_generation.py"
_WORLD_MODEL_RECORD_REF = "world_model_record_a258fda4b7ceffd0"


def _recordings() -> list[dict[str, Any]]:
    return contract._load_recordings(REPO_ROOT)


def _test_design_problem() -> dg.DesignProblem:
    return contract._design_problem(
        {
            "design_problem_id": "gy_n4_test_problem",
            "domain": "ua_msme_cgf_decisive_capture",
        }
    )


def _candidate_set(result: dg.GenerationUnderAResult) -> list[tuple[str, str, str, str]]:
    return [candidate.diversity_key for candidate in result.candidates]


def _selector() -> SelectorPredicate:
    return SelectorPredicate(
        field="id",
        operator=SelectorOperator.EQUALS,
        value="all",
    )


def _bundle(interventions: list[InterventionSpec]) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_gy_n4_cgf", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_gy_n4_cgf",
            problem_frame_ref="sha256:" + "a" * 64,
            interventions=interventions,
        ),
        model_spec=ModelSpec(model_id="model_gy_n4_cgf", data_snapshot_ref="sha256:" + "b" * 64),
    )


def _intervention(intervention_id: str) -> InterventionSpec:
    return InterventionSpec(
        intervention_id=intervention_id,
        kind="tax_relief_rate",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.08")},
    )


def _formalizer_call(*, parsed_json: object) -> dg.LLMGenerationCall:
    return dg.LLMGenerationCall(
        call_index=0,
        role_hint="formalizer",
        status="success",
        model_id=SUPPORTED_GENERATION_MODEL_IDS[1],
        prompt_hash="sha256:" + "c" * 64,
        raw_llm_response=json.dumps(parsed_json, sort_keys=True, default=str),
        parsed_json=parsed_json,
    )


def _imports_name_from(module: ast.Module, owner: str, symbol: str) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == owner
        and any(alias.name == symbol for alias in node.names)
        for node in module.body
    )


def _assigns_module_name(module: ast.Module, symbol: str) -> bool:
    for node in module.body:
        targets: tuple[ast.expr, ...]
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
            return True
    return False


def _llm_call() -> dg.LLMGenerationCall:
    return dg.LLMGenerationCall(
        call_index=0,
        model_id=SUPPORTED_GENERATION_MODEL_IDS[1],
        prompt_hash="sha256:" + "c" * 64,
        raw_llm_response="{}",
    )


def _recording_with_successful_first_response() -> dict[str, Any]:
    recording = next(
        item
        for item in _recordings()
        if isinstance(item.get("responses"), list)
        and item["responses"]
        and item["responses"][0].get("status") != "error"
    )
    return copy.deepcopy(recording)


class GatewayUnavailableClient:
    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        raise RuntimeError("gateway down")


class RecordedClientWithCatalog(contract.RecordedGenerationReplayClient):
    def __init__(self, recording: dict[str, Any], *, model_ids: list[str]) -> None:
        super().__init__(recording)
        self._model_ids = list(model_ids)

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        return list(self._model_ids)


class BadOrganReplayClient(contract.RecordedGenerationReplayClient):
    def __init__(self, recording: dict[str, Any], *, bad_role: str) -> None:
        super().__init__(recording)
        self._bad_role = bad_role

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        user = str(kwargs.get("user") or "")
        role = ""
        if "Generate a draft JSON object" in user:
            role = "draft"
        elif "Generate a valid TrinityBundle" in user:
            role = "formalizer"
        elif "Provide your critique as a JSON object" in user:
            role = "critic"
        if role == self._bad_role:
            return GatewayLLMResponse(
                content="{bad json",
                usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                model=SUPPORTED_GENERATION_MODEL_IDS[0],
                provider="recorded_gateway_replay",
            )
        return await super().generate(**kwargs)


class StaticLLMClient:
    def __init__(self, content: str) -> None:
        self.content = content

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        return GatewayLLMResponse(
            content=self.content,
            usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            model=SUPPORTED_GENERATION_MODEL_IDS[1],
            provider="unit_static",
        )


class CaptureDrafterPromptClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=json.dumps(
                {
                    "draft_id": "draft_prompt_lane0",
                    "problem_frame_ref": "gy_n4_test_problem",
                    "narrative": "Use a candidate lever from the grounding slice.",
                    "interventions": [],
                    "rationale": "Lane-0 prompt assembly witness.",
                    "alternatives_considered": [],
                    "confidence": 0.5,
                }
            ),
            usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            model=SUPPORTED_GENERATION_MODEL_IDS[1],
            provider="unit_capture",
        )


class TerminalCriticTransientClient:
    def __init__(self, *, persistent_failure: bool = False) -> None:
        self.persistent_failure = persistent_failure
        self.critic_attempts = 0
        self.critic_prompt_hashes: list[str] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        return [SUPPORTED_GENERATION_MODEL_IDS[1]]

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        user = str(kwargs.get("user") or "")
        if "Generate a draft JSON object" in user:
            payload = {
                "draft_id": "draft_terminal_salvage",
                "problem_frame_ref": "gy_n4_test_problem",
                "narrative": "Payroll tax relief for affected MSMEs.",
                "interventions": [
                    {
                        "intervention_id": "tax_credit_alias_probe",
                        "kind": "tax_credit_rate",
                        "target": {
                            "field": "id",
                            "operator": "==",
                            "value": "all",
                        },
                        "schedule": {"start_step": 0, "duration_steps": 1},
                        "params": {
                            "rate": "0.08",
                            "target_world_slot": "global.tax_rate",
                            "sign": "decrease",
                            "outcome_slots": ["government.balance"],
                            "effect_path": [
                                "tax_relief_rate",
                                "global.tax_rate",
                                "government.balance",
                            ],
                            "estimand": "average_treatment_effect",
                        },
                    }
                ],
                "rationale": "Uses registered tax-relief mechanism vocabulary.",
                "confidence": 0.82,
            }
            return self._response(payload, role="draft")
        if "Review the draft and return strict JSON with findings" in user:
            return self._response({"findings": [], "confidence_adjustment": 0.0}, role="pass")
        if "Integrate findings and return strict JSON" in user:
            return self._response(
                {
                    "narrative": "Payroll tax relief for affected MSMEs.",
                    "interventions": [
                        {
                            "intervention_id": "tax_credit_alias_probe",
                            "kind": "tax_credit_rate",
                            "target": {
                                "field": "id",
                                "operator": "==",
                                "value": "all",
                            },
                            "schedule": {"start_step": 0, "duration_steps": 1},
                            "params": {
                                "rate": "0.08",
                                "target_world_slot": "global.tax_rate",
                                "sign": "decrease",
                                "outcome_slots": ["government.balance"],
                                "effect_path": [
                                    "tax_relief_rate",
                                    "global.tax_rate",
                                    "government.balance",
                                ],
                                "estimand": "average_treatment_effect",
                            },
                        }
                    ],
                    "rationale": "No revisions required.",
                    "confidence": 0.82,
                },
                role="consolidation",
            )
        if "Generate a valid TrinityBundle" in user:
            intervention = InterventionSpec(
                intervention_id="tax_credit_alias_probe",
                kind="tax_credit_rate",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={
                    "rate": Decimal("0.08"),
                    "target_world_slot": "global.tax_rate",
                    "sign": "decrease",
                    "outcome_slots": ["government.balance"],
                    "effect_path": [
                        "tax_relief_rate",
                        "global.tax_rate",
                        "government.balance",
                    ],
                    "estimand": "average_treatment_effect",
                },
            )
            return self._response(_bundle([intervention]).model_dump(mode="json"), role="formalizer")
        if "Provide your critique as a JSON object" in user:
            self.critic_attempts += 1
            self.critic_prompt_hashes.append(
                dg.gy_content_hash(
                    {
                        "system": kwargs.get("system"),
                        "user": kwargs.get("user"),
                        "messages": kwargs.get("messages"),
                        "response_format": kwargs.get("response_format"),
                        "tools": kwargs.get("tools"),
                        "tool_choice": kwargs.get("tool_choice"),
                        "temperature": kwargs.get("temperature"),
                        "max_tokens": kwargs.get("max_tokens"),
                        "metadata": kwargs.get("metadata"),
                    }
                )
            )
            if self.persistent_failure or self.critic_attempts == 1:
                raise RuntimeError("Gateway request failed (429): rate_limit_exceeded")
            return self._response(
                {
                    "report_id": "critique_terminal_salvage",
                    "verdict": "APPROVE",
                    "issues": [],
                    "alignment_score": 0.93,
                    "completeness_score": 0.91,
                    "overall_quality": 0.92,
                    "reflexion_hint": "",
                },
                role="critic",
            )
        raise AssertionError(f"unexpected prompt: {user[:120]}")

    def _response(self, payload: dict[str, Any], *, role: str) -> GatewayLLMResponse:
        return GatewayLLMResponse(
            content=json.dumps(payload),
            usage=GatewayUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
            model=SUPPORTED_GENERATION_MODEL_IDS[1],
            provider=f"unit_{role}",
        )


@pytest.mark.asyncio
async def test_terminal_critic_transient_salvage_keeps_real_run_and_records_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S", "0")
    client = TerminalCriticTransientClient()
    recording_client = dg.RecordingLLMClient(client, model_id=SUPPORTED_GENERATION_MODEL_IDS[1])
    critic = dg.create_critic_agent(recording_client, model_name=SUPPORTED_GENERATION_MODEL_IDS[1])
    bundle = _bundle(
        [
            InterventionSpec(
                intervention_id="tax_credit_alias_probe",
                kind="tax_credit_rate",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.08")},
            )
        ]
    )
    frame = _test_design_problem().to_scientist_problem_frame()

    terminal_start = len(recording_client.calls)
    critique = await critic.critique(bundle, frame, depth="standard")
    assert critique.metadata["generator_path"] == "degraded_mock_fallback"
    critique, critic_path = await dg._salvage_critic_terminal(
        critic=critic,
        bundle=bundle,
        scientist_frame=frame,
        recording_client=recording_client,
        terminal_start=terminal_start,
        current_critique=critique,
        current_path=str(critique.metadata["generator_path"]),
    )

    assert critic_path == "model_generated"
    assert critique.metadata["generator_path"] == "model_generated"
    assert client.critic_prompt_hashes[0] == client.critic_prompt_hashes[1]
    critic_calls = [call for call in recording_client.calls if call.role_hint == "critic"]
    assert [call.status for call in critic_calls] == ["error", "success"]


@pytest.mark.asyncio
async def test_terminal_critic_persistent_failure_stays_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S", "0")
    client = TerminalCriticTransientClient(persistent_failure=True)
    recording_client = dg.RecordingLLMClient(client, model_id=SUPPORTED_GENERATION_MODEL_IDS[1])
    critic = dg.create_critic_agent(recording_client, model_name=SUPPORTED_GENERATION_MODEL_IDS[1])
    bundle = _bundle(
        [
            InterventionSpec(
                intervention_id="tax_credit_alias_probe",
                kind="tax_credit_rate",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.08")},
            )
        ]
    )
    frame = _test_design_problem().to_scientist_problem_frame()

    terminal_start = len(recording_client.calls)
    critique = await critic.critique(bundle, frame, depth="standard")
    critique, critic_path = await dg._salvage_critic_terminal(
        critic=critic,
        bundle=bundle,
        scientist_frame=frame,
        recording_client=recording_client,
        terminal_start=terminal_start,
        current_critique=critique,
        current_path=str(critique.metadata["generator_path"]),
    )

    assert critic_path == "degraded_mock_fallback"
    assert critique.metadata["generator_path"] == "degraded_mock_fallback"
    critic_calls = [call for call in recording_client.calls if call.role_hint == "critic"]
    assert len(critic_calls) >= 3
    assert all(call.status == "error" for call in critic_calls)


def test_cgf_binding_recovers_legacy_exact_match_rejection() -> None:
    problem = _test_design_problem()
    reference = build_credal_reference(REPO_ROOT)
    intervention = InterventionSpec(
        intervention_id="tax_credit_alias_probe",
        kind="tax_credit_rate",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={
            "rate": Decimal("0.08"),
            "target_world_slot": "global.tax_rate",
            "sign": "decrease",
            "outcome_slots": ["government.balance"],
            "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
        },
        notes=["Payroll tax credit alias for the same tax relief lever."],
    )

    candidates, dispositions = dg._content_bound_candidates(
        design_problem=problem,
        design_problem_ref="sha256:" + "d" * 64,
        bundle=_bundle([intervention]),
        model_id=SUPPORTED_GENERATION_MODEL_IDS[1],
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="unit_probe",
        calls=(_llm_call(),),
        repo_root=REPO_ROOT,
        world_model_record_ref=_WORLD_MODEL_RECORD_REF,
        reference=reference,
    )

    assert len(candidates) == 1
    [disposition] = dispositions
    assert disposition.disposition == "shadow_bound"
    assert disposition.selected_relation == "certified-specialization"
    assert disposition.legacy_exact_match == "would_reject"
    assert disposition.certificate_chain.cg1_certificate_id.startswith("cg1_cert_")
    assert disposition.certificate_chain.cg1_content_hash in candidates[0].atom.provenance_refs
    assert candidates[0].atom.status == "candidate_unverified"
    assert candidates[0].atom.operator_kind.trinity_kind == "tax_relief_rate"
    assert candidates[0].atom.direct_effect_bundle.params == intervention.model_dump(
        mode="json"
    )["params"]
    assert candidates[0].atom.normalized_from is not None
    assert candidates[0].atom.normalized_from.original_kind == "tax_credit_rate"
    assert (
        candidates[0].atom.normalized_from.grounding_relation_certificate_id
        == disposition.certificate_chain.cg1_certificate_id
    )


def test_grounding_adapter_maps_and_omits_unasserted_axes() -> None:
    problem = _test_design_problem()
    intervention = InterventionSpec(
        intervention_id="procurement_countercase",
        kind="procurement_shock_intensity",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={
            "intensity": Decimal("0.70"),
            "target_world_slot": "cells.distress_score",
        },
    )

    proposal = dg._grounding_proposal_for_intervention(
        intervention,
        design_problem=problem,
        bundle_ref="sha256:" + "e" * 64,
    )

    signature = proposal["signature"]
    assert signature["op"] == "procurement_shock_intensity"
    assert signature["target"] == ["cells.distress_score"]
    assert signature["params"] == {"intensity": Decimal("0.70")}
    for axis in ("sign", "outcome", "scope", "population", "estimand", "effect_path"):
        assert axis not in signature


def test_grounding_adapter_no_slot_prose_fallback_stays_under_specified() -> None:
    problem = _test_design_problem()
    intervention = InterventionSpec(
        intervention_id="bare_tax_credit_probe",
        kind="tax_credit_rate",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.08")},
        notes=["Payroll tax credit for affected firms."],
    )

    proposal = dg._grounding_proposal_for_intervention(
        intervention,
        design_problem=problem,
        bundle_ref="sha256:" + "e" * 64,
    )

    assert "signature" not in proposal
    assert "operator=tax_credit_rate" in proposal["raw_text"]


def test_grounding_adapter_passes_candidate_asserted_axes_verbatim() -> None:
    problem = _test_design_problem()
    intervention = InterventionSpec(
        intervention_id="tax_credit_axis_probe",
        kind="tax_credit_rate",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={
            "rate": Decimal("0.08"),
            "target_world_slot": "global.tax_rate",
            "sign": "decrease",
            "outcome_slots": ["government.balance"],
            "effect_path": ["tax_relief_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
        },
    )

    proposal = dg._grounding_proposal_for_intervention(
        intervention,
        design_problem=problem,
        bundle_ref="sha256:" + "e" * 64,
    )

    signature = proposal["signature"]
    assert signature["sign"] == "decrease"
    assert signature["outcome"] == ["government.balance"]
    assert signature["effect_path"] == [
        "tax_relief_rate",
        "global.tax_rate",
        "government.balance",
    ]
    assert signature["estimand"] == "average_treatment_effect"
    assert signature["params"] == {"rate": Decimal("0.08")}


def test_lever_space_prompt_slice_payload_is_compact_and_hash_bound() -> None:
    slice_payload = dg.LeverSpacePromptSlice(
        status="derived",
        content_hash="sha256:" + "f" * 64,
        entries=(
            dg.LeverSpaceSliceEntry(
                operator_kind="tax_relief_rate",
                aliases=("tax credit",),
                target_world_slots=("global.tax_rate",),
                unit="ratio",
                parameter_key="rate",
                parameter_bounds={"min": 0, "max": 0.5},
                sign_semantics="decrease",
                expected_outcome_slots=("government.balance",),
                effect_path=("tax_relief_rate", "global.tax_rate", "government.balance"),
                source_refs=("repo://owner",),
            ),
        ),
        owner_refs=("repo://owner",),
    )
    frame = _test_design_problem().to_scientist_problem_frame()

    nudged = dg._with_lever_space_prompt_slice(
        frame,
        lever_space_prompt_slice=slice_payload,
    )

    payload = nudged.success_criteria["lever_space_prompt_slice"]
    assert payload["content_hash"] == slice_payload.content_hash
    assert payload["entries"][0]["parameter_bounds"] == {"min": 0, "max": 0.5}
    assert payload["entries"][0]["effect_path"] == [
        "tax_relief_rate",
        "global.tax_rate",
        "government.balance",
    ]
    assert "parameter_domain" not in payload["entries"][0]
    assert nudged.context["lever_space_prompt_slice_ref"] == {
        "content_hash": slice_payload.content_hash,
        "non_constraining": True,
    }


@pytest.mark.asyncio
async def test_drafter_prompt_assembly_carries_slice_and_axis_ontology_nudge() -> None:
    slice_payload = dg.LeverSpacePromptSlice(
        status="derived",
        content_hash="sha256:" + "f" * 64,
        entries=(
            dg.LeverSpaceSliceEntry(
                operator_kind="tax_relief_rate",
                aliases=("tax credit",),
                target_world_slots=("global.tax_rate",),
                unit="ratio",
                parameter_key="rate",
                parameter_bounds={"min": 0, "max": 0.5},
                sign_semantics="decrease",
                expected_outcome_slots=("government.balance",),
                effect_path=("tax_relief_rate", "global.tax_rate", "government.balance"),
                source_refs=("repo://owner",),
            ),
        ),
        owner_refs=("repo://owner",),
    )
    frame = dg._with_lever_space_prompt_slice(
        _test_design_problem().to_scientist_problem_frame(),
        lever_space_prompt_slice=slice_payload,
    )
    client = CaptureDrafterPromptClient()

    await LLMDrafterAgent(client).draft_policy(frame)

    [call] = client.calls
    assert "Grounding axes describe the LEVER MECHANISM" in call["system"]
    assert "lever_space_prompt_slice" in call["user"]
    assert slice_payload.content_hash in call["user"]
    assert "tax_relief_rate" in call["user"]
    assert "target_world_slots" in call["user"]


@pytest.mark.asyncio
async def test_formalizer_records_unknown_extra_field_healing() -> None:
    payload = _bundle(
        [
            InterventionSpec(
                intervention_id="tax_relief_probe",
                kind="tax_subsidy",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.08")},
            )
        ]
    ).model_dump(mode="json")
    payload["problem_frame"]["unknown_extra_for_probe"] = "strip-me"
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
    )
    draft = DraftResult(
        draft_id="draft_schema_healing_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    bundle = await formalizer.formalize(draft)

    assert bundle.problem_frame.problem_id == "problem_gy_n4_cgf"
    assert formalizer.schema_healing_events
    assert formalizer.schema_healing_events[0]["path"] == (
        "problem_frame.unknown_extra_for_probe"
    )
    assert formalizer.schema_healing_events[0]["normalized"] == (
        "stripped_unknown_extra_field"
    )


@pytest.mark.asyncio
async def test_formalizer_records_trinity_root_wrapper_healing() -> None:
    payload = {
        "schema_version": "1.0",
        "root": _bundle(
            [
                InterventionSpec(
                    intervention_id="tax_relief_probe",
                    kind="tax_subsidy",
                    target=_selector(),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.08")},
                )
            ]
        ).model_dump(mode="json"),
    }
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
    )
    draft = DraftResult(
        draft_id="draft_root_wrapper_healing_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    bundle = await formalizer.formalize(draft)

    assert bundle.policy_spec.interventions[0].intervention_id == "tax_relief_probe"
    assert any(
        item["path"] == "root" and item["normalized"] == "unwrapped_trinity_bundle_root"
        for item in formalizer.schema_healing_events
    )


@pytest.mark.asyncio
async def test_formalizer_preserves_candidate_grounding_axis_params() -> None:
    payload = _bundle(
        [
            InterventionSpec(
                intervention_id="axis_preservation_probe",
                kind="tax_credit",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={
                    "rate": Decimal("0.08"),
                    "target_world_slot": "global.tax_rate",
                    "sign": "decrease",
                    "outcome_slots": ["government.balance"],
                    "effect_path": ["tax_credit_rate", "global.tax_rate", "government.balance"],
                    "estimand": "average_treatment_effect",
                },
            )
        ]
    ).model_dump(mode="json")
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
    )
    draft = DraftResult(
        draft_id="draft_axis_preservation_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    bundle = await formalizer.formalize(draft)
    intervention = bundle.policy_spec.interventions[0]
    assert intervention.kind == "tax_credit"
    params = intervention.params

    assert params["target_world_slot"] == "global.tax_rate"
    assert params["sign"] == "decrease"
    assert params["outcome_slots"] == ["government.balance"]
    assert params["effect_path"] == [
        "tax_credit_rate",
        "global.tax_rate",
        "government.balance",
    ]
    assert params["estimand"] == "average_treatment_effect"


def test_novel_candidate_with_false_analog_evidence_routes_to_cg3() -> None:
    problem = _test_design_problem()
    reference = build_credal_reference(REPO_ROOT)
    intervention = InterventionSpec(
        intervention_id="household_transfer_tax_credit_like_probe",
        kind="household_transfer",
        target=_selector(),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.08")},
        notes=[
            "Household tax credit-like transfer near fiscal relief text.",
        ],
    )

    candidates, dispositions = dg._content_bound_candidates(
        design_problem=problem,
        design_problem_ref="sha256:" + "d" * 64,
        bundle=_bundle([intervention]),
        model_id=SUPPORTED_GENERATION_MODEL_IDS[1],
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="unit_probe",
        calls=(_llm_call(),),
        repo_root=REPO_ROOT,
        world_model_record_ref=_WORLD_MODEL_RECORD_REF,
        reference=reference,
    )

    assert candidates == ()
    [disposition] = dispositions
    assert disposition.selected_relation == "novel-candidate"
    assert disposition.disposition == "novel_cg3"
    assert disposition.cg3_decision is not None
    assert disposition.rejected_cause is not None
    assert disposition.rejected_cause["cg1_relation"] == "novel-candidate"
    assert "target" in disposition.rejected_cause["cg1_critical_contradictions"]


@pytest.mark.asyncio
async def test_recorded_llm_organs_emit_diverse_shadow_candidates() -> None:
    recording = _recordings()[0]
    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id=str(recording["model_id"]),
        llm_client=contract.RecordedGenerationReplayClient(recording),
        repo_root=REPO_ROOT,
    )

    assert result.status == "generated", [item.reason for item in result.degraded_artifacts]
    assert result.preflight.status == "supported"
    assert result.diversity_report.diverse_enough is True
    assert result.diversity_report.unique_diversity_key_count == 3
    assert len(result.candidates) == 3
    for candidate in result.candidates:
        assert candidate.generator_path == "model_generated"
        assert candidate.status == "candidate_unverified"
        assert candidate.atom.status == "candidate_unverified"
        assert candidate.atom.content_hash == candidate.provenance.content_hash
        assert candidate.provenance.draft_generator_path == "model_generated"
        assert candidate.provenance.formalizer_generator_path == "model_generated"
        assert candidate.provenance.critic_generator_path == "model_generated"
    assert result.surrogate_rankings
    assert all(not ranking.promotion_allowed for ranking in result.surrogate_rankings)
    assert firewall_issues_for_result(result) == ()


@pytest.mark.asyncio
async def test_problem_variation_recordings_produce_different_candidate_sets() -> None:
    recordings = _recordings()
    first = await generate_design_candidates_under_a(
        contract._design_problem(recordings[0]),
        model_id=str(recordings[0]["model_id"]),
        llm_client=contract.RecordedGenerationReplayClient(recordings[0]),
        repo_root=REPO_ROOT,
    )
    second = await generate_design_candidates_under_a(
        contract._design_problem(recordings[1]),
        model_id=str(recordings[1]["model_id"]),
        llm_client=contract.RecordedGenerationReplayClient(recordings[1]),
        repo_root=REPO_ROOT,
    )

    assert first.status == "generated"
    assert second.status == "generated"
    assert _candidate_set(first) != _candidate_set(second)


@pytest.mark.asyncio
async def test_recorded_replay_serves_output_when_prompt_hash_drifts() -> None:
    recording = _recording_with_successful_first_response()
    recorded = recording["responses"][0]
    expected = recorded["raw_response"]
    recorded["prompt_hash"] = "sha256:" + "0" * 64
    if isinstance(recording.get("response"), dict):
        recording["response"]["prompt_hash"] = "sha256:" + "0" * 64

    result = await contract.RecordedGenerationReplayClient(recording).generate(
        system="current prompt text may drift",
        user="recorded output remains the replay contract",
        response_format={"type": "json_object"},
    )

    assert result.content == expected


@pytest.mark.asyncio
async def test_recorded_replay_rejects_raw_response_tamper() -> None:
    recording = _recording_with_successful_first_response()
    recording["responses"][0]["raw_response"] += "\n"
    client = contract.RecordedGenerationReplayClient(recording)

    with pytest.raises(RuntimeError, match="gy_n4_recorded_raw_response_hash_mismatch"):
        await client.generate(system="anything", user="anything")


@pytest.mark.asyncio
async def test_generation_cycle_revision_changes_lane0_prompt_hash_without_replay_gate() -> None:
    recording = _recordings()[1]
    base_problem = contract._design_problem(recording)
    revised_problem = base_problem.model_copy(
        update={
            "runtime_hints": {
                **base_problem.runtime_hints,
                "generation_cycle_grammar": (
                    "seed",
                    "repair:grounding_gap:major_claim_portfolio_refs_missing",
                ),
                "generation_cycle_revision": {
                    "source_counterexample_ref": (
                        "pdc://gy/n6/industrial_resilience_retooling/counterexample/001"
                    ),
                    "previous_candidate_ref": "candidate_09eb3877267a24e8",
                    "new_grammar_elements": (
                        "repair:grounding_gap:major_claim_portfolio_refs_missing",
                    ),
                },
            },
        }
    )

    base_client = CaptureDrafterPromptClient()
    revised_client = CaptureDrafterPromptClient()
    await LLMDrafterAgent(base_client).draft_policy(
        dg._with_generation_cycle_revision_context(
            base_problem.to_scientist_problem_frame(),
            design_problem=base_problem,
        )
    )
    await LLMDrafterAgent(revised_client).draft_policy(
        dg._with_generation_cycle_revision_context(
            revised_problem.to_scientist_problem_frame(),
            design_problem=revised_problem,
        )
    )

    base_call = base_client.calls[0]
    revised_call = revised_client.calls[0]
    base_hash = contract.gy_content_hash(
        {
            "system": base_call.get("system"),
            "user": base_call.get("user"),
            "response_format": base_call.get("response_format"),
        }
    )
    revised_hash = contract.gy_content_hash(
        {
            "system": revised_call.get("system"),
            "user": revised_call.get("user"),
            "response_format": revised_call.get("response_format"),
        }
    )

    assert base_hash != revised_hash
    assert "generation_cycle_revision" in revised_call["user"]
    assert "counterexample/001" in revised_call["user"]


@pytest.mark.asyncio
async def test_gateway_unavailable_returns_terminal_not_mock_candidate() -> None:
    recording = _recordings()[0]
    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id=str(recording["model_id"]),
        llm_client=GatewayUnavailableClient(),
        repo_root=REPO_ROOT,
    )

    assert result.status == "generation_unavailable"
    assert result.candidates == ()
    assert result.degraded_artifacts[0].generator_path == "degraded_mock_fallback"
    assert "models_endpoint_unavailable" in result.degraded_artifacts[0].reason


@pytest.mark.asyncio
async def test_unsupported_model_profile_rejects_before_generation() -> None:
    recording = _recordings()[0]
    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id="gpt-5-mini",
        llm_client=RecordedClientWithCatalog(
            recording,
            model_ids=list(SUPPORTED_GENERATION_MODEL_IDS),
        ),
        repo_root=REPO_ROOT,
    )

    assert result.status == "preflight_rejected"
    assert result.preflight.status == "unsupported"
    assert result.candidates == ()


@pytest.mark.asyncio
async def test_gateway_only_model_is_accepted_from_live_catalog() -> None:
    recording = _recordings()[0]
    gateway_only = "Future/Only-Gateway"
    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id=gateway_only,
        llm_client=RecordedClientWithCatalog(recording, model_ids=[gateway_only]),
        repo_root=REPO_ROOT,
    )

    assert result.status == "generated"
    assert result.preflight.status == "supported"
    assert result.model_id == gateway_only


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bad_role", "reason"),
    [
        ("draft", "drafter_degraded_mock_fallback"),
        ("formalizer", "formalizer_degraded_mock_fallback"),
        ("critic", "critic_degraded_mock_fallback"),
    ],
)
async def test_degraded_organs_are_labeled_and_excluded(bad_role: str, reason: str) -> None:
    recording = _recordings()[0]
    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id=str(recording["model_id"]),
        llm_client=BadOrganReplayClient(recording, bad_role=bad_role),
        repo_root=REPO_ROOT,
    )

    assert result.status == "generation_unavailable"
    assert result.candidates == ()
    assert result.degraded_artifacts[0].generator_path == "degraded_mock_fallback"
    assert result.degraded_artifacts[0].reason == reason


@pytest.mark.asyncio
async def test_fake_surrogate_owner_ref_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    recording = _recordings()[0]
    monkeypatch.setattr(
        dg,
        "_SEARCH_SURROGATE_OWNERS",
        ("polisyos.fake.DoesNotExist",),
    )

    result = await generate_design_candidates_under_a(
        contract._design_problem(recording),
        model_id=str(recording["model_id"]),
        llm_client=contract.RecordedGenerationReplayClient(recording),
        repo_root=REPO_ROOT,
    )

    assert result.status == "generation_unavailable"
    assert result.candidates == ()
    assert result.degraded_artifacts[0].organ == "surrogate"
    assert "surrogate_owner_ref_unresolved" in result.degraded_artifacts[0].reason


def test_surrogate_score_below_certified_cannot_promote() -> None:
    with pytest.raises(ValueError, match="surrogate_below_certified_promoted"):
        SurrogateRanking(
            candidate_id="candidate_probe",
            trust_level="search_guiding",
            score=0.9,
            voi_estimate=0.9,
            promotion_allowed=True,
        )


def test_fake_surrogate_owner_ref_resolver_rejects() -> None:
    with pytest.raises(DesignGenerationError, match="surrogate_owner_ref_unresolved"):
        dg._resolve_owner_symbol("polisyos.fake.DoesNotExist")


def test_strangle_receipts_recompute_as_strangled() -> None:
    assert validate_design_generation_strangle_receipts(REPO_ROOT) == ()


def test_recording_fixture_is_problem_variant_not_authored_constant() -> None:
    recordings = _recordings()
    first = str(recordings[0]["response"]["raw_response"])
    second = str(recordings[1]["response"]["raw_response"])
    assert recordings[0]["response"]["prompt_hash"]
    assert recordings[1]["response"]["prompt_hash"]
    assert "__draft_interventions__" not in first
    assert "__draft_interventions__" not in second
    assert first != second


def test_default_n4_stack_imports_canonical_intervention_owners() -> None:
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.intervention_substrate import (
        intervention_generation_registry_bundle,
        production_composed_world_model_record,
    )

    assert callable(intervention_generation_registry_bundle)
    assert callable(production_composed_world_model_record)
    assert design_generation.intervention_generation_registry_bundle is (
        intervention_generation_registry_bundle
    )


def test_design_generation_reexports_canonical_grounding_disposition_kind() -> None:
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.grounding_disposition_vocab import (
        GroundingDispositionKind,
    )

    assert design_generation.GroundingDispositionKind is GroundingDispositionKind


def test_design_generation_has_one_grounding_disposition_owner() -> None:
    module = ast.parse(DESIGN_GENERATION_PATH.read_text(encoding="utf-8"))

    assert _imports_name_from(
        module,
        "polisyos.runtime.quality.grounding_disposition_vocab",
        "GroundingDispositionKind",
    )
    assert not _assigns_module_name(module, "GroundingDispositionKind")


def test_formalizer_path_requires_matching_recorded_response() -> None:
    bundle = _bundle([_intervention("recorded")])

    assert (
        trinity_bundle_formalizer_generator_path(
            bundle,
            recorded_calls=(_formalizer_call(parsed_json=bundle.model_dump(mode="json")),),
        )
        == "model_generated"
    )


def test_formalizer_path_without_record_is_typed_unrecorded() -> None:
    assert (
        trinity_bundle_formalizer_generator_path(
            _bundle([_intervention("unrecorded")]),
            recorded_calls=(),
        )
        == "path_unrecorded"
    )


def test_formalizer_path_with_unusable_record_is_typed_unrecorded() -> None:
    assert (
        trinity_bundle_formalizer_generator_path(
            _bundle([_intervention("unusable")]),
            recorded_calls=(_formalizer_call(parsed_json={"not": "trinity"}),),
        )
        == "path_unrecorded"
    )


def test_formalizer_path_mismatched_record_is_degraded() -> None:
    returned = _bundle([_intervention("returned")])
    recorded = _bundle([_intervention("different")])

    assert (
        trinity_bundle_formalizer_generator_path(
            returned,
            recorded_calls=(
                _formalizer_call(parsed_json=recorded.model_dump(mode="json")),
            ),
        )
        == "degraded_mock_fallback"
    )


def test_formalizer_path_replays_formalize_schema_version_override() -> None:
    bundle = _bundle([_intervention("schema_version")])
    recorded_payload = bundle.model_dump(mode="json")
    recorded_payload["schema_version"] = "1.1"

    assert (
        trinity_bundle_formalizer_generator_path(
            bundle,
            recorded_calls=(_formalizer_call(parsed_json=recorded_payload),),
        )
        == "model_generated"
    )


@pytest.mark.asyncio
async def test_unrecorded_formalizer_path_salvages_only_from_matching_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle([_intervention("salvaged")])
    recording_client = dg.RecordingLLMClient(
        object(),
        model_id=SUPPORTED_GENERATION_MODEL_IDS[1],
    )

    class MatchingRetryFormalizer:
        attempts = 0

        async def formalize(self, draft: object) -> TrinityBundle:
            self.attempts += 1
            recording_client.calls.append(
                _formalizer_call(parsed_json=bundle.model_dump(mode="json"))
            )
            return bundle

    formalizer = MatchingRetryFormalizer()
    monkeypatch.setenv("POLISYOS_N4_TERMINAL_SALVAGE_RETRIES", "1")
    monkeypatch.setenv("POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S", "0")

    returned, path = await dg._salvage_formalizer_terminal(
        formalizer=formalizer,
        draft=object(),
        recording_client=recording_client,
        terminal_start=0,
        current_bundle=bundle,
        current_path="path_unrecorded",
    )

    assert formalizer.attempts == 1
    assert returned == bundle
    assert path == "model_generated", f"formalizer_{path}"
