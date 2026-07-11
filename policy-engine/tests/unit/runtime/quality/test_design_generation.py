from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
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
from polisyos.scientist.agent.drafter_clients import LLMDrafterAgent, MockDrafterAgent
from polisyos.scientist.agent.formalizer import (
    FormalizerSchemaValidationError,
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


def _valid_prompt_size_estimate() -> dict[str, int]:
    return {
        "frame_without_slice_chars": 1000,
        "frame_with_slice_chars": 1200,
        "slice_added_chars": 200,
        "frame_without_slice_estimated_tokens": 250,
        "frame_with_slice_estimated_tokens": 300,
        "slice_added_estimated_tokens": 50,
    }


def _lane0_prompt_slice() -> dg.LeverSpacePromptSlice:
    return dg.LeverSpacePromptSlice(
        status="derived",
        content_hash="sha256:" + "a" * 64,
        entries=(
            dg.LeverSpaceSliceEntry(
                operator_kind="lane0_test_lever",
                aliases=("lane0 test lever",),
                target_world_slots=("lane0_target_slot",),
                source_refs=("lane0.prompt_size.actual_frame_probe",),
            ),
        ),
        owner_refs=("lane0.prompt_size.actual_frame_probe",),
    )


def _alternate_honest_frozen_receipt_payload() -> dict[str, Any]:
    chain = {
        "cg1_certificate_id": "cg1_cert_" + "1" * 16,
        "cg1_content_hash": "sha256:" + "1" * 64,
        "cg2_certificate_id": "cg2_cert_" + "2" * 16,
        "cg2_content_hash": "sha256:" + "2" * 64,
        "cg3_certificate_id": "cg3_cert_" + "3" * 16,
        "cg3_content_hash": "sha256:" + "3" * 64,
    }
    dispositions = [
        {
            "proposal_id": "proposal_shadow",
            "candidate_id": "candidate_shadow",
            "disposition": "shadow_bound",
            "selected_relation": "exact",
            "identified_atom_id": "atom_shadow",
            "legacy_exact_match": "would_reject",
            "certificate_chain": copy.deepcopy(chain),
        },
        {
            "proposal_id": "proposal_existing",
            "candidate_id": "candidate_existing",
            "disposition": "shadow_bound",
            "selected_relation": "exact",
            "identified_atom_id": "atom_existing",
            "legacy_exact_match": "would_bind",
            "certificate_chain": copy.deepcopy(chain),
        },
        {
            "proposal_id": "proposal_unknown_b",
            "candidate_id": None,
            "disposition": "unknown_blocked",
            "selected_relation": "unknown",
            "identified_atom_id": None,
            "legacy_exact_match": "would_reject",
            "certificate_chain": copy.deepcopy(chain),
        },
    ]
    payload: dict[str, Any] = {
        "schema_version": contract.DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION,
        "behavioral_mutations": [],
        "recording_fixture_hash": "sha256:" + "4" * 64,
        "diagnostic_projection": dict(contract._FROZEN_DIAGNOSTIC_PROJECTION),
        "generation_results": [
            {
                "status": "generated",
                "effective_runtime_config": {},
                "diversity_report": {"candidate_count": 3},
                "grounding_disposition_summary": {
                    "total_candidates": 3,
                    "shadow_bound": 2,
                    "novel_cg3": 0,
                    "veto_false_analog": 0,
                    "abstain_or_blocked": 1,
                    "legacy_exact_match_would_bind": 1,
                    "legacy_exact_match_would_reject": 2,
                },
                "candidates": [
                    {
                        "candidate_id": "candidate_shadow",
                        "diversity_key": ["tax_relief", "all", "income", "rate"],
                    },
                    {
                        "candidate_id": "candidate_existing",
                        "diversity_key": ["income_tax", "all", "income", "rate"],
                    },
                ],
                "grounding_dispositions": dispositions,
            }
        ],
        "recording_set_coverage": {
            "recording_count": 1,
            "all_recordings_generated": True,
            "candidate_count": 3,
            "grounding_disposition_count": 3,
            "unique_diversity_key_count": 3,
            "has_legacy_rejected_shadow_binding": True,
            "has_novel_cg3_route": False,
            "coverage_status": "covered",
            "grounding_summary": {
                "total_candidates": 3,
                "shadow_bound": 2,
                "novel_cg3": 0,
                "veto_false_analog": 0,
                "abstain_or_blocked": 1,
                "legacy_exact_match_would_bind": 1,
                "legacy_exact_match_would_reject": 2,
            },
        },
        "grounding_payoff": {
            "recording_count": 1,
            "recorded_candidate_count": 3,
            "before_legacy_exact_match": {"would_bind": 1, "would_reject": 2},
            "after_cgf": {
                "shadow_bound": 2,
                "novel_cg3": 0,
                "veto_false_analog": 0,
                "abstain_or_blocked": 1,
            },
            "payoff_shadow_bindings_legacy_rejected": [
                {
                    "proposal_id": "proposal_shadow",
                    "candidate_id": "candidate_shadow",
                    "selected_relation": "exact",
                    "identified_atom_id": "atom_shadow",
                    "cg1_certificate_id": chain["cg1_certificate_id"],
                    "cg1_content_hash": chain["cg1_content_hash"],
                    "legacy_exact_match": "would_reject",
                }
            ],
            "novel_routes": [],
            "recorded_vetoes": [],
            "synthetic_cg3_handoff": {},
        },
        "positive_gate": {
            "candidate_count": 3,
            "grounding_disposition_count": 3,
            "grounding_summary": {
                "total_candidates": 3,
                "shadow_bound": 2,
                "novel_cg3": 0,
                "veto_false_analog": 0,
                "abstain_or_blocked": 1,
                "legacy_exact_match_would_bind": 1,
                "legacy_exact_match_would_reject": 2,
            },
            "unique_diversity_key_count": 3,
        },
        "recording_set_gate": {},
        "problem_variation_probe": {},
        "synthetic_cg3_handoff_probe": {},
    }
    live_for_gate = copy.deepcopy(payload["generation_results"])
    live_for_gate[0]["effective_runtime_config"][
        "prompt_size_estimate"
    ] = _valid_prompt_size_estimate()
    payload["prompt_size_gate"] = contract._prompt_size_gate(live_for_gate)
    payload["frozen_payoff_receipt"] = contract._build_frozen_payoff_receipt(payload)
    return payload


def _live_payload_for_frozen(payload: dict[str, Any]) -> dict[str, Any]:
    live = copy.deepcopy(payload)
    live.pop("frozen_payoff_receipt", None)
    for result in live["generation_results"]:
        result.setdefault("effective_runtime_config", {})[
            "prompt_size_estimate"
        ] = _valid_prompt_size_estimate()
    live["prompt_size_gate"] = contract._prompt_size_gate(live["generation_results"])
    return live


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
async def test_drafter_shared_parser_accepts_recorded_think_prefixed_json() -> None:
    payload = {
        "draft_id": "draft_think_prefixed_real",
        "problem_frame_ref": "gy_n4_test_problem",
        "narrative": "A real model-authored candidate draft.",
        "interventions": [
            {
                "name": "Candidate tax relief",
                "mechanism_type": "tax_relief_rate",
                "parameters": {"rate": 0.08},
            }
        ],
        "rationale": "Exercise the canonical embedded-JSON parser.",
        "alternatives_considered": ["No intervention"],
        "confidence": 0.72,
    }
    raw_response = "<think>provider-visible reasoning</think>" + json.dumps(payload)

    draft = await LLMDrafterAgent(StaticLLMClient(raw_response)).draft_policy(
        _test_design_problem().to_scientist_problem_frame()
    )

    assert draft.draft_id == "draft_think_prefixed_real"
    assert draft.interventions == payload["interventions"]
    assert draft.raw_llm_response == raw_response


@pytest.mark.asyncio
async def test_drafter_semantically_invalid_object_does_not_use_parse_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "draft_id": "draft_semantically_invalid",
        "problem_frame_ref": "gy_n4_test_problem",
        "narrative": "The extractor can parse this object.",
        "interventions": [],
        "rationale": "Confidence is deliberately invalid.",
        "confidence": "not-a-float",
    }

    async def _unexpected_fallback(*args: object, **kwargs: object) -> DraftResult:
        del args, kwargs
        raise AssertionError("semantic validation was laundered into mock fallback")

    monkeypatch.setattr(
        "polisyos.scientist.agent.drafter_clients.MockDrafterAgent.draft_policy",
        _unexpected_fallback,
    )

    with pytest.raises(ValueError, match="could not convert string to float"):
        await LLMDrafterAgent(StaticLLMClient(json.dumps(payload))).draft_policy(
            _test_design_problem().to_scientist_problem_frame()
        )


@pytest.mark.asyncio
async def test_drafter_uses_mock_fallback_only_when_no_json_object_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback_calls = 0
    original_fallback = MockDrafterAgent.draft_policy

    async def _record_fallback(*args: object, **kwargs: object) -> DraftResult:
        nonlocal fallback_calls
        fallback_calls += 1
        return await original_fallback(*args, **kwargs)

    monkeypatch.setattr(MockDrafterAgent, "draft_policy", _record_fallback)

    draft = await LLMDrafterAgent(StaticLLMClient("no object is present")).draft_policy(
        _test_design_problem().to_scientist_problem_frame()
    )

    assert fallback_calls == 1
    assert draft.raw_llm_response is None
    assert draft.draft_id != "draft_semantically_invalid"


@pytest.mark.asyncio
async def test_n4_replay_applies_recorded_effective_config_and_restores_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = copy.deepcopy(_recordings()[0])
    expected = dg.EffectiveGenerationRuntimeConfig.model_validate(
        recording["capture_summary"]["effective_runtime_config"]
    )
    environment_fields = {
        "POLISYOS_DRAFTER_PASS_TIMEOUT_S": "17",
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": "17",
        "POLISYOS_FORMALIZER_LLM_TIMEOUT_S": "17",
        "POLISYOS_FORMALIZER_LLM_RETRIES": "17",
        "POLISYOS_CRITIC_LLM_TIMEOUT_S": "17",
        "POLISYOS_N4_TERMINAL_SALVAGE_RETRIES": "17",
        "POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S": "17",
        "POLISYOS_LLM_GATEWAY_TIMEOUT_S": "17",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "17",
        "POLISYOS_LLM_CACHE_TTL_S": "17",
        "POLISYOS_LLM_CACHE_MAXSIZE": "17",
        "POLISYOS_FORMALIZER_SCHEMA_HEALING_MODE": "strict",
    }
    for key, value in environment_fields.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("POLISYOS_N4_PREWARM_CG1_INDEX", raising=False)
    observed: dict[str, str | None] = {}

    async def _capture_runtime_config(*args: object, **kwargs: object) -> object:
        del args, kwargs
        keys = (*environment_fields, "POLISYOS_N4_PREWARM_CG1_INDEX")
        observed.update({key: os.environ.get(key) for key in keys})
        emitted = expected.model_copy(
            update={
                "drafter_pass_timeout_s": float(
                    os.environ["POLISYOS_DRAFTER_PASS_TIMEOUT_S"]
                ),
                "drafter_pass_retry_count": int(
                    os.environ["POLISYOS_DRAFTER_PASS_RETRY_COUNT"]
                ),
                "formalizer_timeout_s": float(
                    os.environ["POLISYOS_FORMALIZER_LLM_TIMEOUT_S"]
                ),
                "formalizer_retry_count": int(
                    os.environ["POLISYOS_FORMALIZER_LLM_RETRIES"]
                ),
                "critic_timeout_s": float(
                    os.environ["POLISYOS_CRITIC_LLM_TIMEOUT_S"]
                ),
                "terminal_salvage_retry_count": int(
                    os.environ["POLISYOS_N4_TERMINAL_SALVAGE_RETRIES"]
                ),
                "terminal_salvage_backoff_base_s": float(
                    os.environ["POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S"]
                ),
                "gateway_timeout_s": float(os.environ["POLISYOS_LLM_GATEWAY_TIMEOUT_S"]),
                "gateway_max_retries": int(
                    os.environ["POLISYOS_LLM_GATEWAY_MAX_RETRIES"]
                ),
                "prompt_cache_ttl_s": float(os.environ["POLISYOS_LLM_CACHE_TTL_S"]),
                "prompt_cache_maxsize": int(
                    os.environ["POLISYOS_LLM_CACHE_MAXSIZE"]
                ),
                "cg1_index_prewarm_enabled": (
                    os.environ.get("POLISYOS_N4_PREWARM_CG1_INDEX", "0") == "1"
                ),
            }
        )
        return SimpleNamespace(effective_runtime_config=emitted)

    monkeypatch.setattr(
        contract,
        "generate_design_candidates_under_a",
        _capture_runtime_config,
    )

    result = await contract._run_live_generation(REPO_ROOT, recording=recording)

    assert result.effective_runtime_config == expected
    assert observed == {
        "POLISYOS_DRAFTER_PASS_TIMEOUT_S": "300.0",
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": "3",
        "POLISYOS_FORMALIZER_LLM_TIMEOUT_S": "300.0",
        "POLISYOS_FORMALIZER_LLM_RETRIES": "5",
        "POLISYOS_CRITIC_LLM_TIMEOUT_S": "300.0",
        "POLISYOS_N4_TERMINAL_SALVAGE_RETRIES": "2",
        "POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S": "10.0",
        "POLISYOS_LLM_GATEWAY_TIMEOUT_S": "300.0",
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "3",
        "POLISYOS_LLM_CACHE_TTL_S": "300.0",
        "POLISYOS_LLM_CACHE_MAXSIZE": "128",
        "POLISYOS_FORMALIZER_SCHEMA_HEALING_MODE": "audit",
        "POLISYOS_N4_PREWARM_CG1_INDEX": "1",
    }
    assert {
        key: os.environ.get(key) for key in environment_fields
    } == environment_fields
    assert "POLISYOS_N4_PREWARM_CG1_INDEX" not in os.environ


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["missing", "invalid"])
async def test_n4_replay_refuses_missing_or_invalid_recorded_effective_config(
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    recording = copy.deepcopy(_recordings()[0])
    if corruption == "missing":
        recording["capture_summary"].pop("effective_runtime_config")
    else:
        recording["capture_summary"]["effective_runtime_config"][
            "formalizer_retry_count"
        ] = "not-an-integer"
    recording["recording_content_hash"] = contract.gy_content_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )
    called = False

    async def _must_not_run(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        return object()

    monkeypatch.setattr(contract, "generate_design_candidates_under_a", _must_not_run)

    with pytest.raises(RuntimeError, match="recorded_effective_runtime_config"):
        await contract._run_live_generation(REPO_ROOT, recording=recording)

    assert called is False


@pytest.mark.asyncio
async def test_n4_replay_refuses_tampered_recorded_config_before_owner_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = copy.deepcopy(_recordings()[0])
    recording["capture_summary"]["effective_runtime_config"][
        "formalizer_retry_count"
    ] -= 1
    called = False

    async def _must_not_run(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        return object()

    monkeypatch.setattr(contract, "generate_design_candidates_under_a", _must_not_run)

    with pytest.raises(RuntimeError, match="recording_content_hash_mismatch"):
        await contract._run_live_generation(REPO_ROOT, recording=recording)

    assert called is False


@pytest.mark.asyncio
async def test_n4_replay_refuses_omitted_recorded_runtime_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = copy.deepcopy(_recordings()[0])
    recording["capture_summary"]["effective_runtime_config"].pop(
        "cg1_index_prewarm_enabled"
    )
    recording["recording_content_hash"] = contract.gy_content_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )
    called = False

    async def _must_not_run(*args: object, **kwargs: object) -> object:
        nonlocal called
        del args, kwargs
        called = True
        return object()

    monkeypatch.setattr(contract, "generate_design_candidates_under_a", _must_not_run)

    with pytest.raises(RuntimeError, match="recorded_effective_runtime_config_input_missing"):
        await contract._run_live_generation(REPO_ROOT, recording=recording)

    assert called is False


@pytest.mark.asyncio
async def test_n4_replay_refuses_owner_emitted_effective_config_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = copy.deepcopy(_recordings()[0])
    expected = dg.EffectiveGenerationRuntimeConfig.model_validate(
        recording["capture_summary"]["effective_runtime_config"]
    )

    async def _emit_drift(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return SimpleNamespace(
            effective_runtime_config=expected.model_copy(
                update={"formalizer_retry_count": expected.formalizer_retry_count - 1}
            )
        )

    monkeypatch.setattr(contract, "generate_design_candidates_under_a", _emit_drift)

    with pytest.raises(RuntimeError, match="recorded_effective_runtime_config_drift"):
        await contract._run_live_generation(REPO_ROOT, recording=recording)


def test_drafter_parser_source_flip_runs_rederive_and_restores_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "src/polisyos/scientist/agent/drafter_clients.py"
    source_path.parent.mkdir(parents=True)
    original = (
        b"def probe(content):\n"
        b"    try:\n"
        b"        data = extract_llm_json_object(content)\n"
        b"    except json.JSONDecodeError:\n"
        b"        return None\n"
        b"    return data\n"
    )
    source_path.write_bytes(original)
    calls: list[tuple[str, ...]] = []
    timeouts: list[object] = []

    def _completed(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        timeouts.append(kwargs.get("timeout"))
        calls.append(args)
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout=json.dumps(
                {
                    "status": "fail",
                    "issues": [
                        {"code": "positive_generation_not_generated", "index": 0},
                        {"code": "positive_grounding_denominator_missing"},
                    ],
                    "generation_terminal_evidence": [
                        {
                            "index": 0,
                            "status": "generation_unavailable",
                            "degraded_reasons": ["drafter_degraded_mock_fallback"],
                        }
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(contract.subprocess, "run", _completed)

    result = contract._run_drafter_parser_source_flip(tmp_path)

    assert result["result"] == "RED"
    assert result["proof"]["issue_code_counts"] == {
        "positive_generation_not_generated": 1,
        "positive_grounding_denominator_missing": 1,
    }
    assert result["proof"]["terminal_reason_observed"] is True
    assert any("--rederive-audit" in args for args in calls)
    assert len(calls) == 1
    assert timeouts == [3600]
    assert source_path.read_bytes() == original


def test_n4_recording_leaf_hash_classifies_before_envelope_hash() -> None:
    recording = copy.deepcopy(_recordings()[0])
    recording["responses"][0]["raw_response"] += "\n"

    with pytest.raises(RuntimeError, match="gy_n4_recording_raw_response_hash_mismatch"):
        contract._validate_recording_fixture(recording)


def test_n4_recording_envelope_still_rejects_rehashed_leaf_tamper() -> None:
    recording = copy.deepcopy(_recordings()[0])
    response = recording["responses"][0]
    response["raw_response"] += "\n"
    response["raw_response_hash"] = contract.gy_content_hash(response["raw_response"])

    with pytest.raises(RuntimeError, match="gy_n4_recording_content_hash_mismatch"):
        contract._validate_recording_fixture(recording)


def test_n4_recorded_response_mutation_report_is_precisely_red() -> None:
    [report] = contract._recording_fixture_mutation_reports(_recordings())

    assert report == {
        "mutation_id": "recorded_raw_response_hash_mismatch",
        "status": "red",
        "issue_codes": ["gy_n4_recording_raw_response_hash_mismatch"],
    }


def test_n4_frozen_receipt_accepts_coherent_non_july_disposition_split() -> None:
    payload = _alternate_honest_frozen_receipt_payload()

    assert contract._frozen_payoff_receipt_issues(payload) == []


def test_n4_frozen_receipt_rejects_incoherent_full_denominator() -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload["recording_set_coverage"]["grounding_summary"]["total_candidates"] = 4
    payload["frozen_payoff_receipt"] = contract._build_frozen_payoff_receipt(payload)

    issue_codes = {
        item["code"] for item in contract._frozen_payoff_receipt_issues(payload)
    }

    assert "frozen_receipt_payoff_summary_drift" in issue_codes


def test_n4_frozen_receipt_static_claims_are_verified() -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload["frozen_payoff_receipt"]["mode"] = "decorative"

    assert "frozen_payoff_receipt_mode_drift" in {
        item["code"] for item in contract._frozen_payoff_receipt_issues(payload)
    }


def test_n4_frozen_receipt_rejects_same_id_payoff_tamper() -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload["grounding_payoff"]["payoff_shadow_bindings_legacy_rejected"][0][
        "cg1_content_hash"
    ] = "sha256:" + "f" * 64
    payload["frozen_payoff_receipt"] = contract._build_frozen_payoff_receipt(payload)

    assert "frozen_receipt_shadow_binding_payoff_drift" in {
        item["code"] for item in contract._frozen_payoff_receipt_issues(payload)
    }


def test_n4_frozen_receipt_rejects_extra_payoff_authority_field() -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload["grounding_payoff"]["promotion_allowed"] = True
    payload["frozen_payoff_receipt"] = contract._build_frozen_payoff_receipt(payload)

    assert "frozen_receipt_payoff_envelope_drift" in {
        item["code"] for item in contract._frozen_payoff_receipt_issues(payload)
    }


def test_n4_frozen_receipt_rejects_legacy_singular_result_sibling() -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload["generation_result"] = copy.deepcopy(payload["generation_results"][0])
    payload["frozen_payoff_receipt"] = contract._build_frozen_payoff_receipt(payload)

    assert "legacy_singular_generation_result_present" in {
        item["code"] for item in contract.validate_payload(payload)["issues"]
    }


def test_generation_result_rejects_independent_producer_denominator_drift() -> None:
    payload = json.loads((REPO_ROOT / contract.OUTPUT_PATH).read_text(encoding="utf-8"))[
        "generation_results"
    ][0]
    payload["diversity_report"]["candidate_count"] += 1

    with pytest.raises(ValueError, match="producer_candidate_denominator_drift"):
        dg.GenerationUnderAResult.model_validate(payload)


def test_n4_producer_denominator_mutation_is_causal_on_green_base() -> None:
    payload = json.loads((REPO_ROOT / contract.OUTPUT_PATH).read_text(encoding="utf-8"))
    payload.pop("generation_result", None)
    payload["source_flip_mutation_harness"] = {
        "mode": "--source-flip-mutations",
        "mutation_ids": list(contract.N4_SOURCE_FLIP_MUTATION_IDS),
        "property": "patch_source_then_causal_red_then_restore_exact_bytes",
    }
    if "prompt_size_gate" not in payload:
        payload["diagnostic_projection"] = contract._FROZEN_DIAGNOSTIC_PROJECTION
        payload["prompt_size_gate"] = contract._prompt_size_gate(
            payload["generation_results"]
        )
    assert contract.validate_payload(payload)["status"] == "pass"

    contract._mutate_producer_candidate_denominator(payload)
    mutated = contract.validate_payload(payload)

    assert mutated["status"] == "fail"
    assert any(
        item["code"] == "generation_result_invalid"
        and "producer_candidate_denominator_drift" in str(item.get("error"))
        for item in mutated["issues"]
    )


def test_n4_write_adds_receipt_and_excludes_wall_time_from_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = _alternate_honest_frozen_receipt_payload()
    payload.pop("frozen_payoff_receipt")
    payload["generation_results"][0]["llm_calls"] = [{"wall_seconds": 1.25}]
    payload["generation_results"][0]["effective_runtime_config"] = {
        "cg1_index_prewarm_wall_seconds": 2.5,
        "prompt_size_estimate": _valid_prompt_size_estimate(),
    }
    payload["generation_results"][0]["candidates"][0]["provenance"] = {
        "parsed_candidate": {
            "params": {
                "wall_seconds": 17.0,
                "prompt_size_estimate": "semantic-domain-parameter",
            }
        }
    }
    payload["wall_time_seconds"] = 3.75
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: copy.deepcopy(payload))

    contract.write(tmp_path)
    output_path = tmp_path / contract.OUTPUT_PATH
    first = output_path.read_bytes()
    written = json.loads(first)
    assert written["frozen_payoff_receipt"]["content_hash"] == contract._frozen_receipt_hash(
        written
    )
    assert "wall_seconds" not in written["generation_results"][0]["llm_calls"][0]
    assert "cg1_index_prewarm_wall_seconds" not in (
        written["generation_results"][0]["effective_runtime_config"]
    )
    assert "prompt_size_estimate" not in (
        written["generation_results"][0]["effective_runtime_config"]
    )
    assert "wall_time_seconds" not in written
    assert (
        written["generation_results"][0]["candidates"][0]["provenance"]
        ["parsed_candidate"]["params"]["wall_seconds"]
        == 17.0
    )
    assert (
        written["generation_results"][0]["candidates"][0]["provenance"]
        ["parsed_candidate"]["params"]["prompt_size_estimate"]
        == "semantic-domain-parameter"
    )

    payload["generation_results"][0]["llm_calls"][0]["wall_seconds"] = 99.75
    payload["generation_results"][0]["effective_runtime_config"][
        "cg1_index_prewarm_wall_seconds"
    ] = 88.5
    payload["wall_time_seconds"] = 77.25
    contract.write(tmp_path)

    assert output_path.read_bytes() == first

    first_receipt_hash = written["frozen_payoff_receipt"]["content_hash"]
    payload["generation_results"][0]["candidates"][0]["provenance"][
        "parsed_candidate"
    ]["params"]["wall_seconds"] = 18.0
    contract.write(tmp_path)
    semantic_change = json.loads(output_path.read_bytes())

    assert output_path.read_bytes() != first
    assert semantic_change["frozen_payoff_receipt"]["content_hash"] != first_receipt_hash


def test_n4_prompt_size_gate_accepts_live_and_frozen_diagnostic_shapes() -> None:
    results = [
        {
            "effective_runtime_config": {
                "prompt_size_estimate": {
                    "frame_without_slice_chars": 1000,
                    "frame_with_slice_chars": 1200,
                    "slice_added_chars": 200,
                    "frame_without_slice_estimated_tokens": 250,
                    "frame_with_slice_estimated_tokens": 300,
                    "slice_added_estimated_tokens": 50,
                }
            }
        }
    ]
    live = {
        "diagnostic_projection": contract._FROZEN_DIAGNOSTIC_PROJECTION,
        "generation_results": results,
        "prompt_size_gate": contract._prompt_size_gate(results),
    }

    assert contract._prompt_size_projection_issues(live, results) == []
    frozen = contract._artifact_stable_payload(live)
    assert contract._prompt_size_projection_issues(
        frozen,
        frozen["generation_results"],
    ) == []


def test_n4_prompt_size_gate_rejects_live_oversize_slice() -> None:
    results = [
        {
            "effective_runtime_config": {
                "prompt_size_estimate": {
                    "frame_without_slice_chars": 1000,
                    "frame_with_slice_chars": 6200,
                    "slice_added_chars": 5200,
                    "frame_without_slice_estimated_tokens": 250,
                    "frame_with_slice_estimated_tokens": 1550,
                    "slice_added_estimated_tokens": 1300,
                }
            }
        }
    ]
    payload = {
        "diagnostic_projection": contract._FROZEN_DIAGNOSTIC_PROJECTION,
        "generation_results": results,
        "prompt_size_gate": contract._prompt_size_gate(results),
    }

    assert "prompt_size_gate_not_pass" in {
        item["code"] for item in contract._prompt_size_projection_issues(payload, results)
    }


def test_n4_prompt_size_gate_rejects_inconsistent_self_attested_slice() -> None:
    results = [
        {
            "effective_runtime_config": {
                "prompt_size_estimate": {
                    "frame_without_slice_chars": 1000,
                    "frame_with_slice_chars": 6200,
                    "slice_added_chars": 200,
                    "frame_without_slice_estimated_tokens": 250,
                    "frame_with_slice_estimated_tokens": 1550,
                    "slice_added_estimated_tokens": 50,
                }
            }
        }
    ]
    payload = {
        "diagnostic_projection": contract._FROZEN_DIAGNOSTIC_PROJECTION,
        "generation_results": results,
        "prompt_size_gate": contract._prompt_size_gate(results),
    }

    assert "prompt_size_measurement_inconsistent" in {
        item["code"] for item in contract._prompt_size_projection_issues(payload, results)
    }


@pytest.mark.parametrize(
    ("target", "replacement"),
    [
        ("gate_limit", 5000.0),
        ("gate_boolean", 1),
        ("projection_limit", 5000.0),
    ],
)
def test_n4_prompt_size_frozen_projection_rejects_python_equality_aliases(
    target: str,
    replacement: object,
) -> None:
    live = _live_payload_for_frozen(_alternate_honest_frozen_receipt_payload())
    frozen = contract._artifact_stable_payload(live)
    if target == "gate_limit":
        frozen["prompt_size_gate"]["limit_slice_added_chars"] = replacement
    elif target == "gate_boolean":
        frozen["prompt_size_gate"]["within_limit_by_index"][0] = replacement
    else:
        frozen["diagnostic_projection"]["prompt_slice_limit_chars"] = replacement

    issues = contract._prompt_size_projection_issues(
        frozen,
        frozen["generation_results"],
    )

    assert issues


def test_n4_prompt_size_measurement_is_bound_to_actual_frames() -> None:
    problem = _test_design_problem()
    lever_slice = _lane0_prompt_slice()
    base_frame = dg._with_generation_cycle_revision_context(
        problem.to_scientist_problem_frame(),
        design_problem=problem,
    )
    sliced_frame = dg._with_lever_space_prompt_slice(
        base_frame,
        lever_space_prompt_slice=lever_slice,
    )
    real_measurement = dg._prompt_size_estimate(base_frame, sliced_frame)

    assert contract._prompt_size_actual_frame_issue(
        design_problem=problem,
        lever_space_prompt_slice=lever_slice,
        emitted=real_measurement,
    ) is None, "prompt_size_measurement_not_actual_frames"
    issue = contract._prompt_size_actual_frame_issue(
        design_problem=problem,
        lever_space_prompt_slice=lever_slice,
        emitted=dg.PromptSizeEstimate(),
    )
    assert issue is not None
    assert issue["code"] == "prompt_size_measurement_not_actual_frames"


def test_n4_prompt_size_actual_frame_binding_ignores_only_absolute_timestamp_width() -> None:
    problem = _test_design_problem()
    lever_slice = _lane0_prompt_slice()
    base_frame = dg._with_generation_cycle_revision_context(
        problem.to_scientist_problem_frame(),
        design_problem=problem,
    )
    sliced_frame = dg._with_lever_space_prompt_slice(
        base_frame,
        lever_space_prompt_slice=lever_slice,
    )
    measured = dg._prompt_size_estimate(base_frame, sliced_frame)
    shifted_without = measured.frame_without_slice_chars + 1
    shifted_with = measured.frame_with_slice_chars + 1
    timestamp_width_shift = measured.model_copy(
        update={
            "frame_without_slice_chars": shifted_without,
            "frame_with_slice_chars": shifted_with,
            "frame_without_slice_estimated_tokens": (shifted_without + 3) // 4,
            "frame_with_slice_estimated_tokens": (shifted_with + 3) // 4,
        }
    )

    assert contract._prompt_size_actual_frame_issue(
        design_problem=problem,
        lever_space_prompt_slice=lever_slice,
        emitted=timestamp_width_shift,
    ) is None
    slice_lie = timestamp_width_shift.model_copy(
        update={
            "slice_added_chars": timestamp_width_shift.slice_added_chars - 1,
        }
    )
    issue = contract._prompt_size_actual_frame_issue(
        design_problem=problem,
        lever_space_prompt_slice=lever_slice,
        emitted=slice_lie,
    )
    assert issue is not None
    assert issue["code"] == "prompt_size_measurement_not_actual_frames"


def test_n4_build_live_payload_binds_prompt_size_to_actual_frames(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    recording = {
        "design_problem_id": "gy_n4_prompt_size_emission_probe",
        "domain": "prompt_size_emission_probe",
    }
    monkeypatch.setattr(contract, "_load_recordings", lambda _repo_root: [recording])

    async def _measured_result(*args: object, **kwargs: object) -> object:
        del args, kwargs
        problem = contract._design_problem(recording)
        lever_slice = _lane0_prompt_slice()
        base_frame = dg._with_generation_cycle_revision_context(
            problem.to_scientist_problem_frame(),
            design_problem=problem,
        )
        sliced_frame = dg._with_lever_space_prompt_slice(
            base_frame,
            lever_space_prompt_slice=lever_slice,
        )
        return SimpleNamespace(
            lever_space_prompt_slice=lever_slice,
            effective_runtime_config=SimpleNamespace(
                prompt_size_estimate=dg._prompt_size_estimate(base_frame, sliced_frame),
            ),
        )

    monkeypatch.setattr(contract, "_run_live_generation", _measured_result)

    def _emission_path_reached(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise RuntimeError("prompt_size_emission_path_reached")

    monkeypatch.setattr(
        contract,
        "_synthetic_cg3_handoff_probe",
        _emission_path_reached,
    )

    with pytest.raises(RuntimeError, match="prompt_size_emission_path_reached"):
        contract.build_live_payload(tmp_path)


def test_n4_prompt_size_gate_mutation_is_causal() -> None:
    payload = json.loads((REPO_ROOT / contract.OUTPUT_PATH).read_text(encoding="utf-8"))
    payload.pop("generation_result", None)
    payload["source_flip_mutation_harness"] = {
        "mode": "--source-flip-mutations",
        "mutation_ids": list(contract.N4_SOURCE_FLIP_MUTATION_IDS),
        "property": "patch_source_then_causal_red_then_restore_exact_bytes",
    }
    if "prompt_size_gate" not in payload:
        payload["diagnostic_projection"] = contract._FROZEN_DIAGNOSTIC_PROJECTION
        payload["prompt_size_gate"] = contract._prompt_size_gate(
            payload["generation_results"]
        )
    assert contract.validate_payload(payload)["status"] == "pass"

    contract._mutate_prompt_size_gate(payload)
    mutated = contract.validate_payload(payload)

    assert mutated["status"] == "fail"
    assert "prompt_size_gate_drift" in {
        item["code"] for item in mutated["issues"]
    } or "prompt_size_gate_frozen_drift" in {
        item["code"] for item in mutated["issues"]
    }


def test_n4_frozen_builder_refuses_forged_pass_over_oversize_live_measurement() -> None:
    results = [
        {
            "effective_runtime_config": {
                "prompt_size_estimate": {
                    "frame_without_slice_chars": 1000,
                    "frame_with_slice_chars": 6200,
                    "slice_added_chars": 5200,
                    "frame_without_slice_estimated_tokens": 250,
                    "frame_with_slice_estimated_tokens": 1550,
                    "slice_added_estimated_tokens": 1300,
                }
            }
        }
    ]
    forged_gate = contract._prompt_size_gate(results)
    forged_gate["within_limit_by_index"] = [True]
    forged_gate["status"] = "pass"
    live = {
        "diagnostic_projection": contract._FROZEN_DIAGNOSTIC_PROJECTION,
        "generation_results": results,
        "prompt_size_gate": forged_gate,
    }

    with pytest.raises(RuntimeError, match="gy_n4_prompt_size_projection_invalid"):
        contract._build_frozen_artifact_payload(live)


def test_n4_frozen_builder_refuses_already_frozen_input_without_measurement() -> None:
    frozen = _alternate_honest_frozen_receipt_payload()

    with pytest.raises(RuntimeError, match="gy_n4_prompt_size_live_measurement_missing"):
        contract._build_frozen_artifact_payload(frozen)


def test_n4_frozen_builder_rejects_malformed_result_sibling() -> None:
    live = _live_payload_for_frozen(_alternate_honest_frozen_receipt_payload())
    live["generation_results"].append("malformed-sibling")

    with pytest.raises(RuntimeError, match="gy_n4_generation_result_denominator_invalid"):
        contract._build_frozen_artifact_payload(live)


def test_n4_rederive_rejects_live_semantic_receipt_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    committed = _alternate_honest_frozen_receipt_payload()
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    live = _live_payload_for_frozen(committed)
    live["generation_results"][0]["grounding_dispositions"][0][
        "selected_relation"
    ] = "certified-specialization"
    live["behavioral_mutations"] = []
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_payoff_live_receipt_drift" in {
        item["code"] for item in report["issues"]
    }


def test_n4_rederive_rejects_live_artifact_drift_outside_receipt_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    committed = _alternate_honest_frozen_receipt_payload()
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    live = _live_payload_for_frozen(committed)
    live["producer"] = "tampered_producer_outside_receipt_projection"
    live["behavioral_mutations"] = []
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_artifact_live_drift" in {
        item["code"] for item in report["issues"]
    }


def test_n4_rederive_rejects_python_equality_alias_outside_receipt_projection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    committed = _alternate_honest_frozen_receipt_payload()
    committed["exact_json_type_probe"] = True
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    live = _live_payload_for_frozen(_alternate_honest_frozen_receipt_payload())
    live["exact_json_type_probe"] = 1
    live["behavioral_mutations"] = []
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_artifact_live_drift" in {
        item["code"] for item in report["issues"]
    }


def test_n4_rederive_accepts_matching_semantic_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    committed = _alternate_honest_frozen_receipt_payload()
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    live = _live_payload_for_frozen(committed)
    live["behavioral_mutations"] = []
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_payoff_live_receipt_drift" not in {
        item["code"] for item in report["issues"]
    }


def test_n4_rederive_rejects_decorative_committed_receipt_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    committed = _alternate_honest_frozen_receipt_payload()
    committed["frozen_payoff_receipt"]["mode"] = "decorative"
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    live = _live_payload_for_frozen(_alternate_honest_frozen_receipt_payload())
    live["behavioral_mutations"] = []
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_payoff_receipt_mode_drift" in {
        item["code"] for item in report["issues"]
    }


def test_n4_rederive_does_not_trust_repointed_committed_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    frozen = _alternate_honest_frozen_receipt_payload()
    live = _live_payload_for_frozen(frozen)
    live["behavioral_mutations"] = []
    committed = copy.deepcopy(frozen)
    committed["generation_results"][0]["grounding_dispositions"][0][
        "selected_relation"
    ] = "certified-specialization"
    output_path = tmp_path / contract.OUTPUT_PATH
    output_path.parent.mkdir(parents=True)
    output_path.write_text(json.dumps(committed), encoding="utf-8")
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "pass", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(tmp_path)

    assert "frozen_payoff_receipt_hash_drift" in {
        item["code"] for item in report["issues"]
    }


def test_recorded_effective_config_source_flip_runs_behavior_and_restores_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = getattr(contract, "_run_recorded_config_source_flip", None)
    assert callable(runner), "recorded-config source-flip runner is missing"
    source_path = (
        tmp_path
        / "tools/quality/validation/check_layer3_gy_design_generation_contract.py"
    )
    source_path.parent.mkdir(parents=True)
    original = (
        b"def probe(expected):\n"
        b"    runtime_environment = _recorded_runtime_environment_values(expected)\n"
        b"    return runtime_environment\n"
    )
    source_path.write_bytes(original)

    def _completed(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="RuntimeError: recorded_effective_runtime_config_drift",
            stderr="",
        )

    monkeypatch.setattr(contract.subprocess, "run", _completed)

    result = runner(tmp_path)

    assert result["mutation_id"] == (
        "source_flip_recorded_effective_runtime_config_ignored"
    )
    assert result["result"] == "RED"
    assert result["proof"]["drift_reason_observed"] is True
    assert source_path.read_bytes() == original


def test_prompt_size_source_flip_runs_behavior_and_restores_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = getattr(contract, "_run_prompt_size_source_flip", None)
    assert callable(runner), "prompt-size source-flip runner is missing"
    source_path = tmp_path / "src/polisyos/runtime/quality/design_generation.py"
    source_path.parent.mkdir(parents=True)
    original = (
        b"def _prompt_size_estimate(base_frame: object, sliced_frame: object) -> PromptSizeEstimate:\n"
        b"    base_chars = len(_json_for_prompt_size(base_frame))\n"
        b"    sliced_chars = len(_json_for_prompt_size(sliced_frame))\n"
        b"    added = max(0, sliced_chars - base_chars)\n"
        b"    return PromptSizeEstimate(\n"
        b"        frame_without_slice_chars=base_chars,\n"
        b"        frame_with_slice_chars=sliced_chars,\n"
        b"        slice_added_chars=added,\n"
        b"        frame_without_slice_estimated_tokens=_estimated_tokens(base_chars),\n"
        b"        frame_with_slice_estimated_tokens=_estimated_tokens(sliced_chars),\n"
        b"        slice_added_estimated_tokens=_estimated_tokens(added),\n"
        b"    )\n"
    )
    source_path.write_bytes(original)

    def _completed(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout="AssertionError: prompt_size_measurement_not_actual_frames",
            stderr="",
        )

    monkeypatch.setattr(contract.subprocess, "run", _completed)

    result = runner(tmp_path)

    assert result["mutation_id"] == "source_flip_prompt_size_estimate_fixed_default"
    assert result["result"] == "RED"
    assert result["proof"]["drift_reason_observed"] is True
    assert source_path.read_bytes() == original


def test_n4_source_flip_denominator_includes_recorded_effective_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_config_id = "source_flip_recorded_effective_runtime_config_ignored"

    def red(mutation_id: str) -> dict[str, str]:
        return {"mutation_id": mutation_id, "result": "RED"}

    monkeypatch.setattr(
        contract,
        "_run_formalizer_source_flip",
        lambda _repo_root: (red(contract.SOURCE_FLIP_MUTATION_ID),),
    )
    monkeypatch.setattr(
        contract,
        "_run_drafter_parser_source_flip",
        lambda _repo_root: red(contract.DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_recorded_config_source_flip",
        lambda _repo_root: red(recorded_config_id),
        raising=False,
    )
    monkeypatch.setattr(
        contract,
        "_run_prompt_size_source_flip",
        lambda _repo_root: red(contract.PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID),
        raising=False,
    )
    monkeypatch.setattr(
        contract,
        "_run_policy_verified_source_flip",
        lambda _repo_root: red(contract.POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_nl_source_flip",
        lambda _repo_root: red(contract.NL_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_s2_source_flip",
        lambda _repo_root: red(contract.S2_SOURCE_FLIP_MUTATION_ID),
    )

    results = contract.run_source_flip_mutations(REPO_ROOT)

    assert tuple(item["mutation_id"] for item in results) == (
        contract.SOURCE_FLIP_MUTATION_ID,
        contract.DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
        recorded_config_id,
        contract.PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
        contract.POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
        contract.NL_SOURCE_FLIP_MUTATION_ID,
        contract.S2_SOURCE_FLIP_MUTATION_ID,
    )


def test_n4_rederive_exposes_typed_generation_terminal_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live = {
        "behavioral_mutations": [],
        "generation_results": [
            {
                "status": "generation_unavailable",
                "degraded_artifacts": [
                    {"reason": "drafter_degraded_mock_fallback"},
                ],
            }
        ],
    }
    monkeypatch.setattr(contract, "build_live_payload", lambda _repo_root: live)
    monkeypatch.setattr(
        contract,
        "validate_payload",
        lambda _payload: {"status": "fail", "issues": [], "outputs": []},
    )

    report = contract.validate_rederive_audit(REPO_ROOT)

    assert report["generation_terminal_evidence"] == [
        {
            "index": 0,
            "status": "generation_unavailable",
            "degraded_reasons": ["drafter_degraded_mock_fallback"],
        }
    ]


def test_n4_payload_rejects_source_flip_denominator_drift() -> None:
    payload: dict[str, Any] = {}

    missing = contract.validate_payload(payload)
    payload["source_flip_mutation_harness"] = {
        "mode": "--source-flip-mutations",
        "mutation_ids": list(contract.N4_SOURCE_FLIP_MUTATION_IDS),
        "property": "patch_source_then_causal_red_then_restore_exact_bytes",
    }
    present = contract.validate_payload(payload)

    assert "source_flip_mutation_denominator_drift" in {
        issue["code"] for issue in missing["issues"]
    }
    assert "source_flip_mutation_denominator_drift" not in {
        issue["code"] for issue in present["issues"]
    }


def test_n4_source_flip_denominator_rejects_missing_parser_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def red(mutation_id: str) -> dict[str, str]:
        return {"mutation_id": mutation_id, "result": "RED"}
    monkeypatch.setattr(
        contract,
        "_run_formalizer_source_flip",
        lambda _repo_root: (red(contract.SOURCE_FLIP_MUTATION_ID),),
    )
    monkeypatch.setattr(
        contract,
        "_run_drafter_parser_source_flip",
        lambda _repo_root: red("source_flip_wrong_parser_mutation"),
    )
    monkeypatch.setattr(
        contract,
        "_run_recorded_config_source_flip",
        lambda _repo_root: red(contract.RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_prompt_size_source_flip",
        lambda _repo_root: red(contract.PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_policy_verified_source_flip",
        lambda _repo_root: red(contract.POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_nl_source_flip",
        lambda _repo_root: red(contract.NL_SOURCE_FLIP_MUTATION_ID),
    )
    monkeypatch.setattr(
        contract,
        "_run_s2_source_flip",
        lambda _repo_root: red(contract.S2_SOURCE_FLIP_MUTATION_ID),
    )

    results = contract.run_source_flip_mutations(REPO_ROOT)

    assert results == (
        {
            "mutation_id": "source_flip_harness_denominator",
            "result": "HARNESS_ERROR",
            "proof": {
                "expected": list(contract.N4_SOURCE_FLIP_MUTATION_IDS),
                "observed": [
                    contract.SOURCE_FLIP_MUTATION_ID,
                    "source_flip_wrong_parser_mutation",
                    contract.RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
                    contract.PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
                    contract.POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
                    contract.NL_SOURCE_FLIP_MUTATION_ID,
                    contract.S2_SOURCE_FLIP_MUTATION_ID,
                ],
            },
        },
    )


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
async def test_formalizer_strict_mode_refuses_unknown_extra_field_healing() -> None:
    payload = _bundle(
        [
            InterventionSpec(
                intervention_id="strict_extra_probe",
                kind="tax_subsidy",
                target=_selector(),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.08")},
            )
        ]
    ).model_dump(mode="json")
    payload["problem_frame"]["unknown_extra_for_probe"] = "must-refuse"
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
        schema_healing_mode="strict",
    )
    draft = DraftResult(
        draft_id="draft_strict_extra_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    with pytest.raises(FormalizerSchemaValidationError) as exc_info:
        await formalizer.formalize(draft)

    error = exc_info.value
    assert error.failure["phase"] == "schema_healing"
    assert error.field_errors == [
        {
            "path": "problem_frame.unknown_extra_for_probe",
            "raw": "must-refuse",
            "normalized": "stripped_unknown_extra_field",
            "note": (
                "schema_healed:problem_frame.unknown_extra_for_probe:"
                "unknown_extra_stripped"
            ),
        }
    ]


@pytest.mark.asyncio
async def test_formalizer_strict_mode_refuses_unrecognized_bound_alias() -> None:
    payload = _bundle([_intervention("strict_bound_probe")]).model_dump(mode="json")
    payload["problem_frame"]["hard_constraints"] = [
        {
            "constraint_id": "strict_bound_constraint",
            "constraint_type": "hard",
            "value": "bounded",
            "bound": "not_a_bound",
        }
    ]
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
        schema_healing_mode="strict",
    )
    draft = DraftResult(
        draft_id="draft_strict_bound_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    with pytest.raises(FormalizerSchemaValidationError) as exc_info:
        await formalizer.formalize(draft)

    assert exc_info.value.failure["phase"] == "schema_healing"
    assert exc_info.value.field_errors[0]["path"] == (
        "problem_frame.hard_constraints.0.bound"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("nullable_alias", ["description", "threshold", "scope"])
async def test_formalizer_strict_mode_refuses_null_constraint_alias(
    nullable_alias: str,
) -> None:
    payload = _bundle([_intervention("strict_null_alias_probe")]).model_dump(mode="json")
    payload["problem_frame"]["hard_constraints"] = [
        {
            "constraint_id": "strict_null_alias_constraint",
            "constraint_type": "hard",
            "value": "bounded",
            nullable_alias: None,
        }
    ]
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(payload)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
        schema_healing_mode="strict",
    )
    draft = DraftResult(
        draft_id="draft_strict_null_alias_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    with pytest.raises(FormalizerSchemaValidationError) as exc_info:
        await formalizer.formalize(draft)

    assert exc_info.value.failure["phase"] == "schema_healing"
    assert exc_info.value.field_errors[0]["path"].endswith(nullable_alias)


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
async def test_formalizer_live_path_rejects_ambiguous_root_wrapper() -> None:
    inner = _bundle([_intervention("inner_candidate")])
    outer = _bundle([_intervention("outer_candidate")]).model_dump(mode="json")
    outer["root"] = inner.model_dump(mode="json")
    formalizer = LLMFormalizerAgent(
        StaticLLMClient(json.dumps(outer)),
        model_name=SUPPORTED_GENERATION_MODEL_IDS[1],
        enable_response_healing=True,
    )
    draft = DraftResult(
        draft_id="draft_ambiguous_root_probe",
        problem_frame_ref="problem_gy_n4_cgf",
        narrative="Probe",
        interventions=[],
        rationale="Probe",
    )

    result = await formalizer.formalize(draft)

    intervention_ids = {
        item.intervention_id for item in result.policy_spec.interventions
    }
    assert intervention_ids.isdisjoint({"inner_candidate", "outer_candidate"})
    assert formalizer.schema_healing_events == ()


def test_formalizer_path_rejects_ambiguous_root_wrapper() -> None:
    inner = _bundle([_intervention("inner_candidate")])
    outer = _bundle([_intervention("outer_candidate")]).model_dump(mode="json")
    outer["root"] = inner.model_dump(mode="json")

    assert (
        trinity_bundle_formalizer_generator_path(
            inner,
            recorded_calls=(_formalizer_call(parsed_json=outer),),
        )
        == "path_unrecorded"
    )


def test_formalizer_path_rejects_root_schema_version_disagreement() -> None:
    inner = _bundle([_intervention("inner_candidate")])
    payload = {
        "schema_version": "9.9",
        "root": inner.model_dump(mode="json"),
    }

    assert (
        trinity_bundle_formalizer_generator_path(
            inner,
            recorded_calls=(_formalizer_call(parsed_json=payload),),
        )
        == "path_unrecorded"
    )


def test_formalizer_path_rejects_unregistered_double_underscore_alias() -> None:
    expected_payload = _bundle([_intervention("parameter_alias_probe")]).model_dump(
        mode="json"
    )
    expected_payload["policy_spec"]["parameters"] = [
        {
            "param_id": "rate_parameter",
            "intervention_id": "parameter_alias_probe",
            "param_path": "rate",
            "default_value": "0.08",
        }
    ]
    expected = TrinityBundle.model_validate(expected_payload)
    recorded_payload = copy.deepcopy(expected_payload)
    parameter = recorded_payload["policy_spec"]["parameters"][0]
    parameter["param__id"] = parameter.pop("param_id")

    assert (
        trinity_bundle_formalizer_generator_path(
            expected,
            recorded_calls=(_formalizer_call(parsed_json=recorded_payload),),
        )
        == "path_unrecorded"
    )


def test_formalizer_path_accepts_registered_parameter_alias() -> None:
    expected_payload = _bundle([_intervention("registered_alias_probe")]).model_dump(
        mode="json"
    )
    expected_payload["policy_spec"]["parameters"] = [
        {
            "param_id": "rate_parameter",
            "intervention_id": "registered_alias_probe",
            "param_path": "rate",
            "default_value": "0.08",
        }
    ]
    expected = TrinityBundle.model_validate(expected_payload)
    recorded_payload = copy.deepcopy(expected_payload)
    parameter = recorded_payload["policy_spec"]["parameters"][0]
    parameter["intervention__id"] = parameter.pop("intervention_id")

    assert (
        trinity_bundle_formalizer_generator_path(
            expected,
            recorded_calls=(_formalizer_call(parsed_json=recorded_payload),),
        )
        == "model_generated"
    )


def test_formalizer_path_rejects_conflicting_registered_alias() -> None:
    expected_payload = _bundle([_intervention("parameter_conflict_probe")]).model_dump(
        mode="json"
    )
    expected_payload["policy_spec"]["parameters"] = [
        {
            "param_id": "rate_parameter",
            "intervention_id": "parameter_conflict_probe",
            "param_path": "rate",
            "default_value": "0.08",
        }
    ]
    expected = TrinityBundle.model_validate(expected_payload)
    recorded_payload = copy.deepcopy(expected_payload)
    recorded_payload["policy_spec"]["parameters"][0]["intervention__id"] = (
        "different_intervention"
    )

    assert (
        trinity_bundle_formalizer_generator_path(
            expected,
            recorded_calls=(_formalizer_call(parsed_json=recorded_payload),),
        )
        == "path_unrecorded"
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
            ("formalizer", "formalizer_path_unrecorded"),
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


def test_policy_verified_fixture_strangle_has_zero_live_callers() -> None:
    receipt = next(
        item
        for item in dg.design_generation_strangle_receipts(REPO_ROOT)
        if item["predecessor_ref"]
        == "scientist.validation.policy_verified.mock_formalizer_tax_subsidy"
    )

    assert receipt["status"] == "strangled", receipt["remaining_callers"]
    assert receipt["remaining_callers"] == []
    assert receipt["disposition"] == "supplied_real_or_typed_refusal"


def test_nl_mock_generator_strangle_has_zero_live_callers() -> None:
    receipt = next(
        item
        for item in dg.design_generation_strangle_receipts(REPO_ROOT)
        if item["predecessor_ref"] == "runtime.http.nl_pipeline.none_to_mock_generator_fork"
    )

    assert receipt["status"] == "strangled", receipt["remaining_callers"]
    assert receipt["remaining_callers"] == []
    assert receipt["disposition"] == "contract_testing_only"


def test_s2_fixed_candidate_strangle_is_behaviorally_data_derived() -> None:
    receipt = next(
        item
        for item in dg.design_generation_strangle_receipts(REPO_ROOT)
        if item["predecessor_ref"]
        == "pdc._impl.layer2_design_search.fixed_credit_guarantee_candidate"
    )

    assert receipt["status"] == "strangled", receipt["remaining_callers"]
    assert receipt["remaining_callers"] == []
    assert receipt["disposition"] == "input_derived_candidate_space"


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


def test_formalizer_path_replays_live_payload_normalization() -> None:
    bundle = _bundle([_intervention("normalized_replay")])
    rooted_payload = bundle.model_dump(mode="json")
    rooted_payload["problem_frame"]["unknown_extra_for_probe"] = "strip-me"
    recorded_payload = {
        "schema_version": "1.0",
        "root": rooted_payload,
    }

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
