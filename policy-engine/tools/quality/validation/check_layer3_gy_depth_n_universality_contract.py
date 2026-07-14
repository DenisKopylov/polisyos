"""Aggregate GY-N10 proof evidence from canonical PolicyOS owners.

This validator extends the existing N4, N8, N10a, composition, and recursive-cycle
validators.  It does not implement a second generation-cycle controller.  Task 12
intentionally emits only an in-memory ``proof_runs_pending`` payload; Task 13 will
attach the three owner-produced plain-language runs and register the frozen artifact.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import functools
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from tools.quality.validation.universality_preflight import assert_universality_preflight

REPO_ROOT = Path(__file__).resolve().parents[3]

# This is intentionally before argparse, artifact reads, caches, and PolicyOS owner imports.
try:
    assert_universality_preflight(REPO_ROOT)
except Exception as exc:  # pragma: no cover - exercised by a fresh child process
    error = str(exc)
    code = error.partition(":")[0] or type(exc).__name__
    sys.stderr.write(
        json.dumps(
            {"issues": [{"code": code, "error": error}], "status": "fail"},
            sort_keys=True,
        )
        + "\n"
    )
    raise SystemExit(1) from exc

import argparse  # noqa: E402

SCHEMA_VERSION = "policyos.policy_design_case.gy_n10.depth_n_universality.v1"
RULE_VERSION = "policyos.layer3.gy.n10.depth_n_universality.v1"
PRODUCER = (
    "tools.quality.validation.check_layer3_gy_depth_n_universality_contract"
)
OUTPUT_PATH = (
    "architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json"
)

N4_PATH = "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
FORK_B_PATH = (
    "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json"
)
N8_PATH = "architecture/policy_design_case/layer3_gy_value_gate_contract.json"
N10A_CENSUS_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_census.json"
)
N10A_PACK_PATH = "architecture/policy_design_case/layer3_gy_second_domain_pack.json"
N10A_SMOKE_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_smoke_design_problem.json"
)
N10A_TRACE_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_cycle_entry_trace.json"
)
N10A_GAPS_PATH = (
    "architecture/policy_design_case/layer3_gy_second_domain_free_grow_gaps.json"
)
COMPOSITION_PATH = (
    "architecture/policy_design_case/layer3_gy_composition_certificates.json"
)

PROOF_MODEL_ID = "moonshotai/Kimi-K2.6"
PLAIN_LANGUAGE_PROOF_REQUESTS = {
    "first_vertical": (
        "Design a policy to improve average household income and MSME survival in "
        "Ukraine under wartime fiscal constraints, considering a state-backed credit "
        "guarantee, and identify every evidence gap before recommendation."
    ),
    "education": (
        "Increase years of schooling and tertiary enrollment using evidence-backed "
        "teaching or learning interventions; do not assume that an education ministry "
        "can write to any simulation lever."
    ),
    "unseen": (
        "Reduce residential peak electricity demand and particulate emissions during "
        "heat waves without shifting costs onto low-income renters."
    ),
}
_PROOF_CAPTURE_JOURNAL_DIR = Path(".tmp/gy-n10-stage4-proof")
_N4_CAPTURE_ENV = {
    "POLISYOS_LLM_GATEWAY_TIMEOUT_S": "300",
    "POLISYOS_LLM_GATEWAY_MAX_RETRIES": "3",
    "POLISYOS_DRAFTER_PASS_TIMEOUT_S": "300",
    "POLISYOS_DRAFTER_PASS_RETRY_COUNT": "3",
    "POLISYOS_FORMALIZER_LLM_TIMEOUT_S": "300",
    "POLISYOS_FORMALIZER_LLM_RETRIES": "5",
    "POLISYOS_CRITIC_LLM_TIMEOUT_S": "300",
    "POLISYOS_CRITIC_LLM_RETRIES": "5",
    "POLISYOS_N4_TERMINAL_SALVAGE_RETRIES": "2",
    "POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S": "10",
    "POLISYOS_N4_PREWARM_CG1_INDEX": "1",
    "POLISYOS_LLM_CACHE_TTL_S": "300",
    "POLISYOS_LLM_CACHE_MAXSIZE": "128",
    "POLISYOS_FORMALIZER_SCHEMA_HEALING_MODE": "audit",
}

_UPSTREAM_PATHS = (
    N4_PATH,
    FORK_B_PATH,
    N8_PATH,
    "architecture/policy_design_case/layer3_gx_pinned_request.json",
    "architecture/policy_design_case/layer3_gy_data_state_substrate_contract.json",
    N10A_CENSUS_PATH,
    N10A_PACK_PATH,
    N10A_SMOKE_PATH,
    N10A_TRACE_PATH,
    N10A_GAPS_PATH,
    COMPOSITION_PATH,
    "architecture/generated_artifacts.toml",
)
_CONTENT_HASH_EXCLUDED_TOP_LEVEL = {"contract_content_hash", "runtime_metrics"}


class UniversalityContractError(RuntimeError):
    """Raised when a capstone payload cannot be derived honestly."""


class _RecordingGateway:
    """Capture one real compiler response denominator for deterministic replay."""

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.calls: list[dict[str, Any]] = []
        self.model_ids: list[str] = []

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        method = getattr(self._inner, "list_model_ids", None)
        if not callable(method):
            raise UniversalityContractError("compiler_gateway_models_endpoint_missing")
        values = await method(timeout=timeout)
        self.model_ids = [str(item) for item in values]
        return list(self.model_ids)

    async def generate(self, **kwargs: Any) -> object:
        method = getattr(self._inner, "generate", None)
        if not callable(method):
            raise UniversalityContractError("compiler_gateway_generate_missing")
        response = await method(**kwargs)
        response_payload = _normalized_gateway_response(response)
        request_content_hash = _semantic_hash(kwargs)
        row = {
            "call_index": len(self.calls),
            "request_content_hash": request_content_hash,
            "response": response_payload,
            "response_content_hash": _semantic_hash(response_payload),
        }
        self.calls.append(row)
        return response


class _ReplayGateway:
    """Replay a content-bound real compiler response through the compiler owner."""

    def __init__(self, recording: Mapping[str, Any]) -> None:
        self._recording = dict(recording)
        self._calls = _mappings(recording.get("calls"))
        self._cursor = 0

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        del timeout
        return _strings(self._recording.get("model_ids"))

    async def generate(self, **kwargs: Any) -> object:
        if self._cursor >= len(self._calls):
            raise UniversalityContractError("compiler_recording_response_exhausted")
        recorded = self._calls[self._cursor]
        observed_request_hash = _semantic_hash(kwargs)
        if observed_request_hash != recorded.get("request_content_hash"):
            raise UniversalityContractError("compiler_recording_request_drift")
        response_payload = _mapping(recorded.get("response"))
        if recorded.get("response_content_hash") != _semantic_hash(response_payload):
            raise UniversalityContractError("compiler_recording_response_tampered")
        self._cursor += 1
        return _gateway_response_from_payload(response_payload)

    def assert_exhausted(self) -> None:
        """Reject recordings whose denominator was not consumed by the owner."""

        if self._cursor != len(self._calls):
            raise UniversalityContractError("compiler_recording_denominator_not_consumed")


def _normalized_gateway_response(response: object) -> dict[str, Any]:
    """Project provider output bytes without operational clocks or transport ids."""

    usage = getattr(response, "usage", None)
    tool_calls: list[dict[str, Any]] = []
    for call in getattr(response, "tool_calls", None) or ():
        arguments = getattr(call, "arguments", None)
        error_envelope = getattr(call, "error_envelope", None)
        if not isinstance(arguments, Mapping):
            raise UniversalityContractError("compiler_gateway_tool_arguments_invalid")
        tool_calls.append(
            {
                "name": str(getattr(call, "name", "") or ""),
                "arguments": dict(arguments),
                "error_envelope": (
                    dict(error_envelope)
                    if isinstance(error_envelope, Mapping)
                    else None
                ),
            }
        )
    return {
        "content": str(getattr(response, "content", "") or ""),
        "model": str(getattr(response, "model", "") or ""),
        "provider": str(getattr(response, "provider", "") or "") or None,
        "usage": {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        },
        "tool_calls": tool_calls,
    }


def _gateway_response_from_payload(payload: Mapping[str, Any]) -> object:
    """Reconstruct the gateway carrier expected by the canonical compiler."""

    from polisyos.scientist.orchestration.llm.gateway_client import (
        GatewayLLMResponse,
        GatewayToolCall,
        GatewayUsage,
    )

    usage = _mapping(payload.get("usage"))
    return GatewayLLMResponse(
        content=str(payload.get("content") or ""),
        usage=GatewayUsage(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
        ),
        model=str(payload.get("model") or ""),
        provider=str(payload.get("provider") or "") or None,
        tool_calls=[
            GatewayToolCall(
                id=f"replay-call-{index}",
                name=str(row.get("name") or ""),
                arguments=_mapping(row.get("arguments")),
                error_envelope=(
                    _mapping(row.get("error_envelope")) or None
                ),
            )
            for index, row in enumerate(_mappings(payload.get("tool_calls")))
        ],
    )


@contextlib.contextmanager
def _temporary_environment(values: Mapping[str, str]) -> Any:
    """Apply one serial capture envelope and restore the process exactly."""

    missing = object()
    previous: dict[str, object] = {
        str(key): os.environ.get(str(key), missing) for key in values
    }
    try:
        os.environ.update({str(key): str(value) for key, value in values.items()})
        yield
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


def _proof_compiler_context(role: str) -> dict[str, object]:
    """Return stable caller authority/time context for one exact raw request."""

    jurisdictions = {
        "first_vertical": "UA",
        "education": "education_target_context",
        "unseen": "energy_heatwave_target_context",
    }
    return {
        "run_id": f"gy-n10-stage4-{role}",
        "job_id": f"gy-n10-stage4-{role}-plain-language",
        "tenant_id": "policyos_quality",
        "cell_id": f"depth-n-universality-{role}",
        "requested_authority_level": "research",
        "mandate": (
            "Produce candidate-only policy designs and enumerate unresolved evidence; "
            "do not assert legal, data, grounding, value, or promotion authority."
        ),
        "jurisdiction": jurisdictions[role],
        "as_of": "2026-07-14T00:00:00+00:00",
        "policy_time": "2026-07-14",
        "data_time": "2026-07-14",
    }


async def _capture_compiler_recording(
    *,
    role: str,
    raw_request: str,
    gateway: _RecordingGateway,
) -> tuple[object, dict[str, Any]]:
    """Capture and immediately validate one real plain-language compiler response."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.control.nl_pipeline import (
        build_design_problem_from_nl_request,
    )

    start = len(gateway.calls)
    context = _proof_compiler_context(role)
    problem = await build_design_problem_from_nl_request(
        nl_request=raw_request,
        context=context,
        model_name=PROOF_MODEL_ID,
        gateway_client=gateway,
        span_support_client=gateway,
    )
    calls = copy.deepcopy(gateway.calls[start:])
    if not calls:
        raise UniversalityContractError("compiler_recording_denominator_empty")
    recording: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.compiler_recording.v1",
        "recording_source": "live_gateway_canonical_design_problem_compiler",
        "role": role,
        "model_id": PROOF_MODEL_ID,
        "model_ids": list(gateway.model_ids),
        "raw_request": raw_request,
        "raw_request_content_hash": gy_content_hash({"raw_request": raw_request}),
        "context": context,
        "design_problem_ref": gy_content_hash(problem.model_dump(mode="json")),
        "calls": calls,
    }
    recording["recording_content_hash"] = _semantic_hash(recording)
    replayed = await _replay_compiler_recording(recording)
    if replayed != problem:
        raise UniversalityContractError("compiler_recording_replay_drift")
    return problem, recording


async def _replay_compiler_recording(recording: Mapping[str, Any]) -> object:
    """Re-run the real compiler owner over one content-addressed response set."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.control.nl_pipeline import (
        build_design_problem_from_nl_request,
    )

    stable_recording = {
        key: value
        for key, value in recording.items()
        if key != "recording_content_hash"
    }
    if recording.get("recording_content_hash") != _semantic_hash(stable_recording):
        raise UniversalityContractError("compiler_recording_content_hash_mismatch")
    replay = _ReplayGateway(recording)
    problem = await build_design_problem_from_nl_request(
        nl_request=str(recording.get("raw_request") or ""),
        context=_mapping(recording.get("context")),
        model_name=str(recording.get("model_id") or ""),
        gateway_client=replay,
        span_support_client=replay,
    )
    replay.assert_exhausted()
    observed_ref = gy_content_hash(problem.model_dump(mode="json"))
    if observed_ref != recording.get("design_problem_ref"):
        raise UniversalityContractError("compiler_recording_problem_binding_drift")
    return problem


def _cycle_context_for_problem(
    repo_root: Path,
    *,
    role: str,
    problem: object,
) -> object | None:
    """Bind known domains to owner evidence and leave the unseen domain packless."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.design_problem import DesignProblem

    resolved_problem = DesignProblem.model_validate(problem)
    if role == "unseen":
        return None
    if role == "education":
        from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a

        bundle = n10a._load_frozen_bundle(repo_root)
        return n10a._build_frozen_cycle_substrate_context(
            repo_root,
            bundle=bundle,
            design_problem=resolved_problem,
        )
    if role != "first_vertical":
        raise UniversalityContractError(f"proof_domain_role_unknown:{role}")

    from polisyos.runtime.quality.intervention_substrate import (
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )

    registry = build_substrate_registry_from_existing_catalogs(repo_root)
    world = production_composed_world_model_record(repo_root)
    if registry.content_hash != world.substrate_registry_ref.content_hash:
        raise UniversalityContractError("first_vertical_registry_wmr_mismatch")
    selected_hashes = tuple(
        entry.entry_content_hash
        for entry in world.substrate_registry_ref.resolved_entries
    )
    problem_ref = gy_content_hash(resolved_problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {
            "schema_version": "policyos.layer3.gy.n10.first_vertical_context.v1",
            "design_problem_ref": problem_ref,
            "substrate_registry_content_hash": registry.content_hash,
            "world_model_record_content_hash": world.content_hash,
            "selected_registry_entry_hashes": list(selected_hashes),
        }
    )
    return build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=resolved_problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_hashes,
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=substrate_input_hash,
    )


def _n4_responses_from_journal(path: Path) -> list[dict[str, Any]]:
    """Project the local call journal into path-independent N4 replay evidence."""

    from polisyos.pdc import gy_content_hash

    rows: list[dict[str, Any]] = []
    if not path.is_file():
        raise UniversalityContractError("proof_n4_call_journal_missing")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise UniversalityContractError("proof_n4_call_journal_row_invalid")
        raw = str(payload.get("raw_llm_response") or "")
        row = {
            "call_index": int(payload.get("call_index") or 0),
            "role": str(payload.get("role_hint") or "") or "unknown",
            "role_hint": payload.get("role_hint"),
            "status": str(payload.get("status") or "success"),
            "model_id": str(payload.get("model_id") or PROOF_MODEL_ID),
            "provider": payload.get("provider"),
            "prompt_hash": str(payload.get("prompt_hash") or ""),
            "raw_response": raw,
            "raw_llm_response": raw,
            "raw_response_hash": gy_content_hash(raw),
            "response_format": payload.get("response_format"),
            "usage": {
                "prompt_tokens": int(payload.get("prompt_tokens") or 0),
                "completion_tokens": int(payload.get("completion_tokens") or 0),
                "total_tokens": int(payload.get("total_tokens") or 0),
            },
            "error": {
                "type": payload.get("error_type"),
                "message": payload.get("error_message"),
                "status": payload.get("error_status"),
                "code": payload.get("error_code"),
                "retry_after_s": payload.get("retry_after_s"),
            },
        }
        rows.append(row)
    if not rows:
        raise UniversalityContractError("proof_n4_call_journal_empty")
    return rows


async def _replay_n4_recording(
    repo_root: Path,
    *,
    problem: object,
    cycle_substrate_context: object | None,
    recording: Mapping[str, Any],
) -> object:
    """Replay real raw generation responses through the current N4 owner."""

    from polisyos.runtime.quality.design_generation import (
        generate_design_candidate_bundle_under_a,
    )
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        RecordedGenerationReplayClient,
    )

    stable_recording = {
        key: value
        for key, value in recording.items()
        if key != "recording_content_hash"
    }
    if recording.get("recording_content_hash") != _semantic_hash(stable_recording):
        raise UniversalityContractError("proof_n4_recording_content_hash_mismatch")
    with _temporary_environment(_mapping(recording.get("effective_environment"))):
        organ_run = await generate_design_candidate_bundle_under_a(
            problem,
            model_id=str(recording.get("model_id") or ""),
            llm_client=RecordedGenerationReplayClient(dict(recording)),
            repo_root=repo_root,
            min_diverse_candidates=3,
            cycle_substrate_context=cycle_substrate_context,
        )
    projection = _n4_owner_projection(organ_run)
    if projection != _mapping(recording.get("owner_result_projection")):
        raise UniversalityContractError("proof_n4_owner_projection_replay_drift")
    return organ_run


def _n4_owner_projection(organ_run: object) -> dict[str, Any]:
    """Reuse the established N10a projection over the canonical N4 organ."""

    from tools.quality.validation import check_layer3_gy_second_domain_pack as n10a

    return n10a._n4_owner_result_projection(organ_run)


async def _n4_recording_from_journal(
    repo_root: Path,
    *,
    role: str,
    problem: object,
    cycle_substrate_context: object | None,
    journal_path: Path,
) -> tuple[dict[str, Any], object]:
    """Replay one just-finished live call set before admitting its receipt."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.design_generation import (
        generate_design_candidate_bundle_under_a,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from tools.quality.validation.check_layer3_gy_design_generation_contract import (
        RecordedGenerationReplayClient,
    )

    resolved_problem = DesignProblem.model_validate(problem)
    responses = _n4_responses_from_journal(journal_path)
    seed_recording = {"model_id": PROOF_MODEL_ID, "responses": responses}
    with _temporary_environment(_N4_CAPTURE_ENV):
        organ_run = await generate_design_candidate_bundle_under_a(
            resolved_problem,
            model_id=PROOF_MODEL_ID,
            llm_client=RecordedGenerationReplayClient(seed_recording),
            repo_root=repo_root,
            min_diverse_candidates=3,
            cycle_substrate_context=cycle_substrate_context,
        )
    projection = _n4_owner_projection(organ_run)
    if projection.get("status") != "generated":
        raise UniversalityContractError(
            "proof_n4_owner_generation_not_generated:"
            + str(projection.get("status"))
        )
    recording: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.n4_recording.v1",
        "recording_source": "live_gateway_call_journal_replayed_through_n4_owner",
        "role": role,
        "model_id": PROOF_MODEL_ID,
        "design_problem_ref": gy_content_hash(
            resolved_problem.model_dump(mode="json")
        ),
        "cycle_substrate_context_content_hash": getattr(
            cycle_substrate_context, "content_hash", None
        ),
        "effective_environment": dict(_N4_CAPTURE_ENV),
        "responses": responses,
        "owner_result_projection": projection,
    }
    recording["recording_content_hash"] = _semantic_hash(recording)
    replayed = await _replay_n4_recording(
        repo_root,
        problem=resolved_problem,
        cycle_substrate_context=cycle_substrate_context,
        recording=recording,
    )
    return recording, replayed


def _append_capture_journal(repo_root: Path, payload: Mapping[str, Any]) -> None:
    """Persist operational intent/result before any authoritative artifact write."""

    path = repo_root / _PROOF_CAPTURE_JOURNAL_DIR / "capture.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(_canonical_json(payload) + "\n")


async def _capture_domain_run(
    repo_root: Path,
    *,
    role: str,
    compiler_recording: Mapping[str, Any],
    problem: object,
) -> dict[str, Any]:
    """Run one compiled problem through the production recursive/cycle owners."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.control.generation_cycle import (
        compile_and_run_recursive_generation_cycle,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleBudget
    from polisyos.scientist.orchestration.engine.budget import (
        BudgetLimit,
        BudgetState,
    )

    context = _cycle_context_for_problem(
        repo_root,
        role=role,
        problem=problem,
    )
    replay = _ReplayGateway(compiler_recording)
    journal_path = repo_root / _PROOF_CAPTURE_JOURNAL_DIR / f"{role}-n4.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.unlink(missing_ok=True)
    _append_capture_journal(
        repo_root,
        {
            "event": "domain_run_started",
            "role": role,
            "raw_request_content_hash": compiler_recording.get(
                "raw_request_content_hash"
            ),
            "cycle_substrate_context_content_hash": getattr(
                context, "content_hash", None
            ),
            "artifact_write": "not_started",
        },
    )
    with _temporary_environment(
        {**_N4_CAPTURE_ENV, "POLISYOS_N4_CALL_JOURNAL_PATH": str(journal_path)}
    ):
        compiled = await compile_and_run_recursive_generation_cycle(
            raw_request=str(compiler_recording.get("raw_request") or ""),
            context=_mapping(compiler_recording.get("context")),
            model_name=PROOF_MODEL_ID,
            compiler_gateway=replay,
            span_support_client=replay,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0,
                max_nodes=1,
                min_cycles_per_leaf=1,
                max_cycles_per_leaf=1,
            ),
            cycle_substrate_context=context,
            repo_root=repo_root,
        )
    replay.assert_exhausted()
    n4_recording, organ_run = await _n4_recording_from_journal(
        repo_root,
        role=role,
        problem=compiled.design_problem,
        cycle_substrate_context=context,
        journal_path=journal_path,
    )
    _assert_n4_cycle_binding(compiled, organ_run)
    recording: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.domain_run_recording.v1",
        "role": role,
        "compiler_recording": copy.deepcopy(dict(compiler_recording)),
        "n4_recording": n4_recording,
        "cycle_substrate_context_content_hash": getattr(context, "content_hash", None),
        "compiled_run": compiled.model_dump(mode="json"),
        "compiled_run_content_hash": compiled.content_hash,
        "design_problem_ref": gy_content_hash(
            compiled.design_problem.model_dump(mode="json")
        ),
    }
    recording["recording_content_hash"] = _semantic_hash(recording)
    _append_capture_journal(
        repo_root,
        {
            "event": "domain_run_completed",
            "role": role,
            "recording_content_hash": recording["recording_content_hash"],
            "compiled_run_content_hash": compiled.content_hash,
            "artifact_write": "not_started",
        },
    )
    return recording


def _assert_n4_cycle_binding(compiled: object, organ_run: object) -> None:
    """Require the production cycle denominator to equal the replayed live N4 result."""

    result = getattr(organ_run, "result", None)
    if result is None or getattr(result, "status", None) != "generated":
        raise UniversalityContractError("proof_n4_result_not_generated")
    expected_ids = {
        str(candidate.candidate_id)
        for candidate in getattr(result, "candidates", ()) or ()
    }
    for disposition in getattr(result, "grounding_dispositions", ()) or ():
        if str(getattr(disposition, "disposition", "")) == "shadow_bound":
            continue
        candidate_id = str(
            getattr(disposition, "candidate_id", None)
            or getattr(disposition, "proposal_id", "")
        )
        if candidate_id:
            expected_ids.add(candidate_id)
    recursive_run = getattr(compiled, "recursive_run", None)
    nodes = tuple(getattr(recursive_run, "nodes", ()) or ())
    if len(nodes) != 1 or getattr(nodes[0], "cycle_run", None) is None:
        raise UniversalityContractError("proof_recursive_leaf_denominator_invalid")
    cycles = tuple(nodes[0].cycle_run.cycles)
    if len(cycles) != 1 or set(cycles[0].candidate_ids) != expected_ids:
        raise UniversalityContractError("proof_cycle_n4_candidate_denominator_mismatch")


async def _capture_proof_recordings(repo_root: Path) -> dict[str, Any]:
    """Execute the single journal-first cold closeout and return replayable evidence."""

    from polisyos.scientist.orchestration.llm.factory import (
        create_traced_gateway_client,
    )

    _append_capture_journal(
        repo_root,
        {
            "event": "cold_closeout_started",
            "roles": list(PLAIN_LANGUAGE_PROOF_REQUESTS),
            "model_id": PROOF_MODEL_ID,
            "artifact_write": "not_started",
        },
    )
    inner = create_traced_gateway_client(
        model_name=PROOF_MODEL_ID,
        run_id="gy_n10_stage4_plain_language_compiler",
        model_variant_id="gy-n10-stage4",
    )
    if inner is None:
        raise UniversalityContractError("proof_compiler_gateway_unavailable")
    gateway = _RecordingGateway(inner)
    compiled: dict[str, tuple[object, dict[str, Any]]] = {}
    try:
        for role, raw_request in PLAIN_LANGUAGE_PROOF_REQUESTS.items():
            compiled[role] = await _capture_compiler_recording(
                role=role,
                raw_request=raw_request,
                gateway=gateway,
            )
    finally:
        close = getattr(inner, "aclose", None)
        if callable(close):
            await close()

    domain_recordings: dict[str, Any] = {}
    for role in PLAIN_LANGUAGE_PROOF_REQUESTS:
        problem, compiler_recording = compiled[role]
        domain_recordings[role] = await _capture_domain_run(
            repo_root,
            role=role,
            compiler_recording=compiler_recording,
            problem=problem,
        )
    return domain_recordings


async def _domain_run_from_recording(
    repo_root: Path,
    *,
    role: str,
    recording: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive one semantic run trace from frozen owner-response evidence."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )

    stable = {
        key: value
        for key, value in recording.items()
        if key != "recording_content_hash"
    }
    if recording.get("recording_content_hash") != _semantic_hash(stable):
        raise UniversalityContractError("domain_run_recording_content_hash_mismatch")
    if recording.get("role") != role:
        raise UniversalityContractError("domain_run_recording_role_mismatch")
    compiler_recording = _mapping(recording.get("compiler_recording"))
    problem = await _replay_compiler_recording(compiler_recording)
    context = _cycle_context_for_problem(
        repo_root,
        role=role,
        problem=problem,
    )
    observed_context_hash = getattr(context, "content_hash", None)
    if observed_context_hash != recording.get(
        "cycle_substrate_context_content_hash"
    ):
        raise UniversalityContractError("domain_run_context_binding_drift")
    n4_recording = _mapping(recording.get("n4_recording"))
    organ_run = await _replay_n4_recording(
        repo_root,
        problem=problem,
        cycle_substrate_context=context,
        recording=n4_recording,
    )
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        recording.get("compiled_run")
    )
    if compiled.design_problem != problem:
        raise UniversalityContractError("domain_run_compiler_problem_drift")
    if compiled.cycle_substrate_context_ref != observed_context_hash:
        raise UniversalityContractError("domain_run_compiled_context_drift")
    if compiled.content_hash != recording.get("compiled_run_content_hash"):
        raise UniversalityContractError("domain_run_compiled_receipt_drift")
    if compiled.design_problem_ref != recording.get("design_problem_ref"):
        raise UniversalityContractError("domain_run_design_problem_ref_drift")
    _assert_n4_cycle_binding(compiled, organ_run)
    projection = _n4_owner_projection(organ_run)
    domain_run = _project_domain_run(
        repo_root,
        role=role,
        raw_request=str(compiler_recording.get("raw_request") or ""),
        compiler_recording=compiler_recording,
        compiled=compiled,
        n4_projection=projection,
        cycle_substrate_context=context,
        recording_content_hash=str(recording.get("recording_content_hash") or ""),
    )
    expected_ref = gy_content_hash(problem.model_dump(mode="json"))
    if domain_run["compiler_receipt"]["design_problem_ref"] != expected_ref:
        raise UniversalityContractError("domain_run_compiler_receipt_drift")
    return domain_run


def _project_domain_run(
    repo_root: Path,
    *,
    role: str,
    raw_request: str,
    compiler_recording: Mapping[str, Any],
    compiled: object,
    n4_projection: Mapping[str, Any],
    cycle_substrate_context: object | None,
    recording_content_hash: str,
) -> dict[str, Any]:
    """Project compiler/N4/N6-N9 evidence into one compact typed trace."""

    from polisyos.pdc import gy_content_hash

    recursive_run = compiled.recursive_run
    nodes = tuple(recursive_run.nodes)
    if len(nodes) != 1 or nodes[0].cycle_run is None:
        raise UniversalityContractError("domain_run_recursive_leaf_invalid")
    cycle_run = nodes[0].cycle_run
    if len(cycle_run.cycles) != 1:
        raise UniversalityContractError("domain_run_cycle_denominator_invalid")
    cycle = cycle_run.cycles[0]
    value = cycle.value_port
    selection_receipt = value.method_selection_receipt
    acquisition_report = cycle.acquisition_routing_report
    dispositions = _mappings(n4_projection.get("grounding_dispositions"))
    selected_disposition = next(
        (
            row
            for row in dispositions
            if str(row.get("candidate_id") or row.get("proposal_id") or "")
            == cycle.selected_candidate_ref
        ),
        None,
    )
    proposed = _mappings(n4_projection.get("proposed_interventions"))
    evidence_kind = _domain_evidence_kind(
        role=role,
        value_status=value.status,
        blockers=tuple(value.authority_blockers),
        terminal_kind=recursive_run.terminal.kind.value,
    )
    decision_grade = value.decision_grade or "blocked"
    stage_trace: dict[str, Any] = {
        "generation": {
            "attempted": True,
            "owner": (
                "polisyos.runtime.quality.design_generation."
                "generate_design_candidate_bundle_under_a"
            ),
            "status": n4_projection.get("status"),
            "generation_channel": "n4_owner",
            "prompt_slice_content_hash": n4_projection.get(
                "lever_space_prompt_slice_content_hash"
            ),
            "prompt_slice_operator_kinds": _strings(
                n4_projection.get("prompt_slice_operator_kinds")
            ),
            "proposed_lever_ids": [
                str(row.get("operator_kind") or "") for row in proposed
            ],
            "proposed_candidate_ids": [
                str(row.get("proposal_id") or "") for row in proposed
            ],
            "proposed_raw_candidate_hashes": [
                str(row.get("raw_candidate_hash") or "") for row in proposed
            ],
        },
        "grounding": {
            "attempted": True,
            "owner": "polisyos.runtime.quality.generation_cycle.PolicyGroundingPort",
            "status": cycle.grounding.status,
            "source": cycle.grounding.grounding_source,
            "selected_candidate_ref": cycle.selected_candidate_ref,
            "selected_disposition": (
                str(selected_disposition.get("disposition") or "")
                if selected_disposition is not None
                else cycle.grounding.grounding_disposition
            ),
            "dispositions": [
                {
                    "candidate_id": row.get("candidate_id"),
                    "proposal_id": row.get("proposal_id"),
                    "disposition": row.get("disposition"),
                    "raw_candidate_hash": row.get("raw_candidate_hash"),
                }
                for row in dispositions
            ],
            "issue_codes": list(cycle.grounding.issue_codes),
        },
        "simulation": {
            "attempted": True,
            "owner": "polisyos.runtime.quality.generation_cycle.JointSimulationPort",
            "status": cycle.simulation.status,
            "authority_blockers": list(cycle.simulation.authority_blockers),
            "world_model_record_content_hash": (
                cycle.simulation.world_model_record.content_hash
                if cycle.simulation.world_model_record is not None
                else None
            ),
            "k_world_ref_before": cycle.simulation.k_world_ref_before,
            "k_world_ref_after": cycle.simulation.k_world_ref_after,
        },
        "value": {
            "attempted": True,
            "owner": "polisyos.runtime.quality.generation_cycle.FoundryValuePort",
            "status": value.status,
            "authority_blockers": list(value.authority_blockers),
            "decision_grade": value.decision_grade,
            "selected_method_fqn": value.selected_method_fqn,
            "advisor_selection_receipt_content_hash": (
                selection_receipt.content_hash
                if selection_receipt is not None
                else None
            ),
            "acquisition_requirement_id": (
                value.acquisition_requirement.requirement_gap_id
                if value.acquisition_requirement is not None
                else None
            ),
        },
        "acquisition": {
            "attempted": acquisition_report is not None,
            "owner": "polisyos.runtime.quality.acquisition_planner",
            "route_kind": (
                "n7_requirement_gap" if acquisition_report is not None else None
            ),
            "planner_report_content_hash": (
                gy_content_hash(
                    acquisition_report.model_dump(
                        mode="json", exclude={"generated_at"}
                    )
                )
                if acquisition_report is not None
                else None
            ),
        },
        "promotion": {
            "attempted": True,
            "owner": "polisyos.runtime.quality.promotion_sequence.CanonicalN9PromotionPort",
            "status": cycle_run.promotion_port.status,
            "certified_candidate_ids": list(
                cycle_run.promotion_port.certified_candidate_ids
            ),
        },
    }
    compiler_receipt = {
        "owner": (
            "polisyos.runtime.http.services.control.nl_pipeline."
            "build_design_problem_from_nl_request"
        ),
        "tool_name": "emit_design_problem",
        "model_id": compiler_recording.get("model_id"),
        "raw_request_content_hash": compiler_recording.get(
            "raw_request_content_hash"
        ),
        "recording_content_hash": compiler_recording.get(
            "recording_content_hash"
        ),
        "design_problem_ref": compiled.design_problem_ref,
        "used_committed_fixture": False,
    }
    run: dict[str, Any] = {
        "schema_version": "policyos.layer3.gy.n10.domain_run.v1",
        "domain_role": role,
        "raw_request": raw_request,
        "compiler_receipt": compiler_receipt,
        "design_problem": compiled.design_problem.model_dump(mode="json"),
        "design_problem_ref": compiled.design_problem_ref,
        "cycle_substrate_context_ref": getattr(
            cycle_substrate_context, "content_hash", None
        ),
        "recursive_run_content_hash": recursive_run.content_hash,
        "generation_cycle_run_id": cycle_run.run_id,
        "stage_trace": stage_trace,
        "terminal": recursive_run.terminal.model_dump(mode="json"),
        "terminal_distribution": {
            "terminal_kind": recursive_run.terminal.kind.value,
            "evidence_kind": evidence_kind,
            "decision_grade": decision_grade,
            "count": 1,
        },
        "promotion_reached": bool(cycle_run.promotion_port.certified_candidate_ids),
        "recording_content_hash": recording_content_hash,
    }
    if role == "education":
        baseline = _read_json(repo_root / N10A_TRACE_PATH)
        baseline_diff = _mapping(baseline.get("baseline_diff"))
        baseline_terminal = str(
            baseline_diff.get("baseline_terminal_kind") or ""
        )
        run["baseline_diff"] = {
            "baseline_terminal": baseline_terminal,
            "current_terminal": recursive_run.terminal.kind.value,
            "moved_past_a_spec_gap": (
                baseline_terminal == "a_spec_gap"
                and recursive_run.terminal.kind.value != "a_spec_gap"
            ),
            "unlocked_stages": [
                name
                for name, stage in stage_trace.items()
                if isinstance(stage, Mapping) and stage.get("attempted") is True
            ],
        }
    run["content_hash"] = _semantic_hash(run)
    return run


def _domain_evidence_kind(
    *,
    role: str,
    value_status: str,
    blockers: tuple[str, ...],
    terminal_kind: str,
) -> str:
    """Classify measured degradation without widening the underlying terminal."""

    if "acquire_data:value_panel_data_missing" in blockers:
        return "owner_data_gap"
    if "method_estimand_binding_mismatch" in blockers:
        return "estimand_binding_refusal"
    if role == "unseen":
        return "unseen_domain_typed_degradation"
    if value_status == "value_ready":
        return "owner_value_receipt"
    return f"typed_terminal:{terminal_kind}"


async def _complete_payload_from_recordings(
    repo_root: Path,
    *,
    recordings: Mapping[str, Any],
) -> dict[str, Any]:
    """Aggregate three cached owner runs over the stable Task-12 evidence graph."""

    if set(recordings) != set(PLAIN_LANGUAGE_PROOF_REQUESTS):
        raise UniversalityContractError("proof_recording_domain_denominator_missing")
    base = _build_pending_payload(repo_root, lane="cached")
    domain_runs: dict[str, Any] = {}
    for role in PLAIN_LANGUAGE_PROOF_REQUESTS:
        domain_runs[role] = await _domain_run_from_recording(
            repo_root,
            role=role,
            recording=_mapping(recordings.get(role)),
        )
    base.update(
        {
            "proof_status": "complete",
            "capability_reality": {
                "producer": "implemented",
                "artifact": "implemented",
                "semantic_test": "implemented",
            },
            "proof_recordings": copy.deepcopy(dict(recordings)),
            "domain_runs": domain_runs,
            "terminal_distributions": {
                role: copy.deepcopy(run["terminal_distribution"])
                for role, run in domain_runs.items()
            },
            "runtime_metrics": {"lane": "cached"},
        }
    )
    base["contract_content_hash"] = _contract_content_hash(base)
    return base


def declared_outputs() -> list[str]:
    """Return the canonical artifact path reserved for the Task-13 proof."""

    return [OUTPUT_PATH]


def check_provenance_stability(repo_root: Path) -> dict[str, Any]:
    """Validate and cross-bind every frozen owner on the Stage-4 entry graph.

    Args:
        repo_root: Policy Engine checkout root.

    Returns:
        A content-only stability report. ``status=stable`` means every owner
        validator passed and every cross-artifact identity resolved.
    """

    root = repo_root.resolve()
    dirty_paths = _dirty_upstream_paths(root)
    if dirty_paths:
        return {
            "status": "drifted",
            "issues": [
                {"code": "upstream_artifact_dirty", "paths": dirty_paths}
            ],
        }
    return copy.deepcopy(_cached_provenance_stability(root.as_posix()))


@functools.lru_cache(maxsize=2)
def _cached_provenance_stability(repo_root: str) -> dict[str, Any]:
    # Imported owners may emit informational registration diagnostics. The capstone
    # validator owns one machine-readable output document, so those non-contract
    # side effects are contained at the single owner-intake boundary.
    owner_stdout = io.StringIO()
    owner_stderr = io.StringIO()
    with contextlib.redirect_stdout(owner_stdout), contextlib.redirect_stderr(
        owner_stderr
    ):
        return _derive_provenance_stability(repo_root)


def _derive_provenance_stability(repo_root: str) -> dict[str, Any]:
    root = Path(repo_root)
    issues: list[dict[str, Any]] = []

    # Owner imports happen only after the module-level universality preflight.
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.design_problem import DesignProblem
    from tools.quality.validation import (
        check_layer3_gy_composition_artifacts as composition_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_n10_cg1_l2_relation_census as census_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_second_domain_pack as n10a_validator,
    )
    from tools.quality.validation import (
        check_layer3_gy_value_gate_contract as n8_validator,
    )

    n4 = _read_json(root / N4_PATH)
    census = _read_json(root / FORK_B_PATH)
    n8 = _read_json(root / N8_PATH)
    composition = _read_json(root / COMPOSITION_PATH)
    n10a_bundle = n10a_validator._load_frozen_bundle(root)

    with contextlib.chdir(root):
        n4_report = n4_validator.validate(root)
    _extend_owner_issues(issues, "n4", n4_report.get("issues"))
    try:
        census_validator._validate(census)
    except (KeyError, TypeError, ValueError) as exc:
        issues.append({"code": "fork_b_census_invalid", "error": str(exc)})
    _extend_owner_issues(issues, "n8", n8_validator.validate_payload(n8))
    _extend_owner_issues(
        issues,
        "n10a",
        n10a_validator.validate_bundle_payloads(n10a_bundle, root),
    )
    composition_report = composition_validator.validate(root)
    _extend_owner_issues(
        issues,
        "composition",
        composition_report.get("issues"),
    )

    n4_file_sha = _file_sha256(root / N4_PATH)
    census_input = _mapping(census.get("input_refs"))
    census_n4_sha = str(census_input.get("design_generation_artifact_sha256") or "")
    production = _mapping(n8.get("production_refusal"))
    if census_n4_sha != n4_file_sha:
        issues.append({"code": "n4_to_fork_b_artifact_binding_drift"})
    if str(production.get("n4_artifact_sha256") or "") != n4_file_sha:
        issues.append({"code": "n4_to_n8_artifact_binding_drift"})

    census_ref = {
        "artifact_ref": FORK_B_PATH,
        "content_hash": census.get("content_hash"),
        "raw_full_table_content_hash": census.get("raw_full_table_content_hash"),
        "n4_artifact_sha256": census_n4_sha,
    }
    n8_fork_b_ref = _mapping(n8.get("fork_b_census_receipt"))
    if census_ref["content_hash"] != n8_fork_b_ref.get("content_hash"):
        issues.append({"code": "fork_b_to_n8_content_binding_drift"})
    if census_ref["raw_full_table_content_hash"] != n8_fork_b_ref.get(
        "raw_full_table_content_hash"
    ):
        issues.append({"code": "fork_b_to_n8_raw_binding_drift"})

    n4_problem_refs = sorted(
        {
            str(item.get("design_problem_ref"))
            for item in _mappings(n4.get("generation_results"))
            if item.get("design_problem_ref")
        }
    )
    n8_problem_ref = str(production.get("design_problem_ref") or "")
    if n8_problem_ref not in n4_problem_refs:
        issues.append({"code": "n8_design_problem_not_in_n4_denominator"})

    frozen_comparator = _mapping(
        _mapping(n10a_bundle.get("census")).get("first_vertical_comparator")
    )
    live_comparator = n10a_validator._first_vertical_comparator(root)
    if frozen_comparator != live_comparator:
        issues.append({"code": "n10a_first_vertical_comparator_drift"})
    semantic_projection_hash = str(
        _mapping(live_comparator.get("source_hashes")).get(N8_PATH) or ""
    )
    n10a_comparator_hash = str(
        _mapping(frozen_comparator.get("source_hashes")).get(N8_PATH) or ""
    )
    if semantic_projection_hash != n10a_comparator_hash:
        issues.append({"code": "n8_to_n10a_semantic_projection_drift"})

    smoke = _mapping(n10a_bundle.get("smoke_problem"))
    problem = DesignProblem.model_validate(smoke.get("design_problem"))
    canonical_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    trace = _mapping(n10a_bundle.get("cycle_trace"))
    capture = _mapping(trace.get("n4_owner_capture"))
    capture_input = _mapping(capture.get("input_binding"))
    projection = _mapping(capture.get("owner_result_projection"))
    cycle_run = _mapping(trace.get("generation_cycle_run"))
    design_problem_refs = {
        "canonical": canonical_problem_ref,
        "capture_input": str(capture_input.get("design_problem_ref") or ""),
        "owner_projection": str(projection.get("design_problem_ref") or ""),
        "generation_cycle_run": str(cycle_run.get("design_problem_ref") or ""),
    }
    for index, cycle in enumerate(_mappings(cycle_run.get("cycles"))):
        design_problem_refs[f"cycle_{index}"] = str(
            cycle.get("design_problem_ref") or ""
        )
    if len(set(design_problem_refs.values())) != 1:
        issues.append({"code": "education_design_problem_binding_drift"})

    prompt_hashes = {
        "owner_projection": _strings(projection.get("exact_call_prompt_hashes")),
        "responses": [
            str(item.get("prompt_hash") or "")
            for item in _mappings(capture.get("responses"))
        ],
        "journal": [
            str(item.get("prompt_hash") or "")
            for item in _mappings(
                _mapping(capture.get("journal_receipt")).get("call_evidence_rows")
            )
        ],
    }
    if (
        not prompt_hashes["owner_projection"]
        or prompt_hashes["owner_projection"] != prompt_hashes["responses"]
        or prompt_hashes["owner_projection"] != prompt_hashes["journal"]
    ):
        issues.append({"code": "education_prompt_hash_binding_drift"})

    n10a_census_hash = str(
        _mapping(n10a_bundle.get("census")).get("census_content_hash") or ""
    )
    observed_composition_census_hashes = sorted(
        set(_values_for_key(composition, "census_content_hash"))
    )
    composition_status = (
        "bound"
        if composition_report.get("status") == "pass"
        and observed_composition_census_hashes == [n10a_census_hash]
        else "drifted"
    )
    if composition_status != "bound":
        issues.append({"code": "composition_to_n10a_census_binding_drift"})

    return {
        "status": "stable" if not issues else "drifted",
        "issues": issues,
        "source_refs": {
            "n4_artifact": N4_PATH,
            "n4_artifact_sha256": n4_file_sha,
            "fork_b_census": FORK_B_PATH,
            "n8_contract": N8_PATH,
            "n10a_census": N10A_CENSUS_PATH,
            "n10a_smoke_problem": N10A_SMOKE_PATH,
            "n10a_cycle_trace": N10A_TRACE_PATH,
            "composition_contract": COMPOSITION_PATH,
        },
        "census_ref": census_ref,
        "n8_fork_b_ref": {
            "content_hash": n8_fork_b_ref.get("content_hash"),
            "raw_full_table_content_hash": n8_fork_b_ref.get(
                "raw_full_table_content_hash"
            ),
            "usable_certified_relations": n8_fork_b_ref.get(
                "usable_certified_relations"
            ),
        },
        "first_vertical_refs": {
            "n8_design_problem_ref": n8_problem_ref,
            "n4_generation_design_problem_refs": n4_problem_refs,
            "semantic_projection_hash": semantic_projection_hash,
            "n10a_comparator_hash": n10a_comparator_hash,
        },
        "design_problem_refs": design_problem_refs,
        "prompt_hashes": prompt_hashes,
        "composition_ref": {
            "status": composition_status,
            "n10a_census_content_hash": n10a_census_hash,
            "observed_census_content_hashes": observed_composition_census_hashes,
        },
    }


def build_live_payload(repo_root: Path, *, lane: str = "lane0") -> dict[str, Any]:
    """Build either the cheap pending view or the cached completed proof.

    Args:
        repo_root: Policy Engine checkout root.
        lane: ``lane0`` returns the pre-proof owner graph; ``cached`` replays the
            committed live response recordings through the canonical owners.

    Returns:
        A content-bound pending or completed payload.

    Raises:
        UniversalityContractError: If the entry graph or recordings drift.
    """

    root = repo_root.resolve()
    if lane == "lane0":
        return _build_pending_payload(root, lane=lane)
    if lane != "cached":
        raise UniversalityContractError(f"proof_lane_unknown:{lane}")
    path = root / OUTPUT_PATH
    if not path.is_file():
        raise UniversalityContractError("proof_recordings_missing")
    committed = _read_json(path)
    recordings = _mapping(committed.get("proof_recordings"))
    return asyncio.run(
        _complete_payload_from_recordings(root, recordings=recordings)
    )


def _build_pending_payload(repo_root: Path, *, lane: str) -> dict[str, Any]:
    """Aggregate the stable pre-proof owner graph without claiming domain runs."""

    root = repo_root.resolve()
    stability = check_provenance_stability(root)
    if stability.get("status") != "stable":
        raise UniversalityContractError("provenance_stability_failed")

    n8 = _read_json(root / N8_PATH)
    census = _read_json(root / FORK_B_PATH)
    composition = _read_json(root / COMPOSITION_PATH)
    denominators = _mapping(n8.get("denominators"))
    families = _strings(denominators.get("native_contract_families"))
    education = _mapping(n8.get("education_refusal"))
    production = _mapping(n8.get("production_refusal"))
    recursive_run = _mappings(composition.get("recursive_runs"))[0]
    joint_receipts = _joint_simulation_receipts(recursive_run)

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "producer": PRODUCER,
        "proof_status": "proof_runs_pending",
        "capability_reality": {
            "producer": "producer_missing",
            "artifact": "artifact_missing",
            "semantic_test": "semantic_test_missing",
        },
        "content_hash_excluded_fields": ["runtime_metrics"],
        "source_refs": stability["source_refs"],
        "provenance_stability": stability,
        "domain_runs": {},
        "non_panel_evidence": {
            "fork": str(census.get("fork") or ""),
            "status": "acquisition_required",
            "native_contract_families": families,
            "supported_native_families": len(families),
            "fork_a_candidate_count": len(
                census.get("fork_a_evidence_candidate_refs") or []
            ),
            "census_content_hash": census.get("content_hash"),
            "raw_census_content_hash": census.get(
                "raw_full_table_content_hash"
            ),
            "first_vertical_terminal": {
                "status": production.get("status"),
                "authority_blockers": list(
                    production.get("authority_blockers") or []
                ),
                "decision_grade": production.get("decision_grade"),
                "acquisition_requirement": production.get(
                    "acquisition_requirement"
                ),
                "receipt_content_hash": production.get("content_hash"),
            },
        },
        "education_refusal": {
            "status": education.get("status"),
            "authority_blockers": list(education.get("authority_blockers") or []),
            "decision_grade": education.get("decision_grade"),
            "selected_method_fqn": education.get("selected_method_fqn"),
            "selection_receipt_content_hash": _mapping(
                education.get("method_selection_receipt")
            ).get("content_hash"),
            "receipt_content_hash": education.get("content_hash"),
        },
        "depth_evidence": {
            "authority_scope": recursive_run.get("authority_scope"),
            "controller_ref": recursive_run.get("controller_ref"),
            "observed_max_depth": recursive_run.get("observed_max_depth"),
            "recursive_run_content_hash": recursive_run.get("content_hash"),
            "recursive_graph_ref": recursive_run.get("recursive_graph_ref"),
            "recursive_graph_content_hash": recursive_run.get(
                "recursive_graph_content_hash"
            ),
            "joint_simulation_receipts": joint_receipts,
            "composition_receipts": [
                {
                    "receipt_id": item.get("receipt_id"),
                    "receipt_ref": item.get("receipt_ref"),
                }
                for item in _mappings(composition.get("composition_receipts"))
            ],
        },
        "gy_g_strangle_receipt": copy.deepcopy(
            _mapping(composition.get("depth_n_strangle_receipt"))
        ),
        "pattern_pass": {
            "P27": "canonical_owners_aggregated_no_parallel_cycle",
            "P29": "proof_runs_pending_not_self_attested",
            "P31": "single_validator_intake_for_capstone_evidence",
            "P32": "resolve_content_bind_and_validate_before_projection",
        },
        "runtime_metrics": {"lane": lane},
    }
    payload["contract_content_hash"] = _contract_content_hash(payload)
    return payload


def validate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate Task-12 honesty and content integrity.

    Args:
        payload: Universality contract payload.

    Returns:
        Structured validation status and issues.
    """

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "schema_version_mismatch"})
    if payload.get("rule_version") != RULE_VERSION:
        issues.append({"code": "rule_version_mismatch"})
    if payload.get("contract_content_hash") != _contract_content_hash(payload):
        issues.append({"code": "contract_content_hash_mismatch"})

    proof_status = payload.get("proof_status")
    domain_runs = payload.get("domain_runs")
    if proof_status == "proof_runs_pending":
        if domain_runs != {}:
            issues.append({"code": "pending_proof_contains_domain_runs"})
        expected_reality = {
            "producer": "producer_missing",
            "artifact": "artifact_missing",
            "semantic_test": "semantic_test_missing",
        }
        if payload.get("capability_reality") != expected_reality:
            issues.append({"code": "pending_capability_reality_drift"})
    elif proof_status == "complete":
        if set(domain_runs or {}) != {"first_vertical", "education", "unseen"}:
            issues.append({"code": "complete_proof_domain_denominator_missing"})
        else:
            issues.extend(_completed_domain_run_issues(payload))
    else:
        issues.append({"code": "proof_status_invalid"})

    stability = _mapping(payload.get("provenance_stability"))
    if stability.get("status") != "stable" or stability.get("issues") != []:
        issues.append({"code": "provenance_stability_not_green"})
    non_panel = _mapping(payload.get("non_panel_evidence"))
    families = _strings(non_panel.get("native_contract_families"))
    if (
        non_panel.get("fork") != "B"
        or non_panel.get("status") != "acquisition_required"
        or int(non_panel.get("fork_a_candidate_count") or 0) != 0
        or non_panel.get("supported_native_families") != len(families)
        or not families
    ):
        issues.append({"code": "fork_b_evidence_invalid"})
    education = _mapping(payload.get("education_refusal"))
    if (
        education.get("status") != "value_blocked"
        or education.get("authority_blockers")
        != ["method_estimand_binding_mismatch"]
    ):
        issues.append({"code": "education_refusal_invalid"})
    depth = _mapping(payload.get("depth_evidence"))
    if int(depth.get("observed_max_depth") or 0) <= 2:
        issues.append({"code": "depth_n_evidence_missing"})
    strangle = _mapping(payload.get("gy_g_strangle_receipt"))
    if (
        strangle.get("status") != "strangled"
        or strangle.get("production_fixture_callers") != []
    ):
        issues.append({"code": "gy_g_strangle_receipt_invalid"})
    volatile_paths = _volatile_content_paths(payload)
    if volatile_paths:
        mutated_clocks = copy.deepcopy(dict(payload))
        _mutate_volatile_values(mutated_clocks)
        if _contract_content_hash(mutated_clocks) != _contract_content_hash(payload):
            issues.append(
                {
                    "code": "volatile_content_field",
                    "paths": volatile_paths,
                }
            )

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def _completed_domain_run_issues(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate exact raw requests, real compiler bindings, and honest terminals."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.design_problem import DesignProblem

    issues: list[dict[str, Any]] = []
    domain_runs = _mapping(payload.get("domain_runs"))
    recordings = _mapping(payload.get("proof_recordings"))
    if set(recordings) != set(PLAIN_LANGUAGE_PROOF_REQUESTS):
        issues.append({"code": "proof_recording_domain_denominator_missing"})
    smoke_problem = _mapping(
        _read_json(REPO_ROOT / N10A_SMOKE_PATH).get("design_problem")
    )
    for role, expected_request in PLAIN_LANGUAGE_PROOF_REQUESTS.items():
        run = _mapping(domain_runs.get(role))
        if not run:
            continue
        stable_run = {
            key: value for key, value in run.items() if key != "content_hash"
        }
        if run.get("content_hash") != _semantic_hash(stable_run):
            issues.append({"code": "domain_run_content_hash_mismatch", "role": role})
        try:
            problem = DesignProblem.model_validate(run.get("design_problem"))
        except ValueError as exc:
            issues.append(
                {"code": "domain_run_design_problem_invalid", "role": role, "error": str(exc)}
            )
            continue
        receipt = _mapping(run.get("compiler_receipt"))
        expected_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        pinned_fixture = (
            run.get("raw_request") != expected_request
            or problem.nl_provenance.raw_request != expected_request
            or problem.model_dump(mode="json") == smoke_problem
            or receipt.get("design_problem_ref") != expected_problem_ref
            or receipt.get("owner")
            != (
                "polisyos.runtime.http.services.control.nl_pipeline."
                "build_design_problem_from_nl_request"
            )
            or receipt.get("tool_name") != "emit_design_problem"
            or receipt.get("used_committed_fixture") is not False
        )
        if pinned_fixture:
            issues.append({"code": "cycle_driven_by_pinned_fixture", "role": role})
        if receipt.get("raw_request_content_hash") != gy_content_hash(
            {"raw_request": expected_request}
        ):
            issues.append({"code": "plain_language_request_binding_mismatch", "role": role})
        terminal = _mapping(run.get("terminal"))
        distribution = _mapping(run.get("terminal_distribution"))
        if (
            not terminal.get("kind")
            or distribution.get("terminal_kind") != terminal.get("kind")
            or distribution.get("count") != 1
        ):
            issues.append({"code": "domain_terminal_distribution_invalid", "role": role})

    first = _mapping(domain_runs.get("first_vertical"))
    first_stages = _mapping(first.get("stage_trace"))
    first_value = _mapping(first_stages.get("value"))
    first_acquisition = _mapping(first_stages.get("acquisition"))
    if (
        first_value.get("status") != "value_blocked"
        or "acquire_data:value_panel_data_missing"
        not in _strings(first_value.get("authority_blockers"))
        or first_acquisition.get("attempted") is not True
        or first_acquisition.get("route_kind") != "n7_requirement_gap"
    ):
        issues.append({"code": "first_vertical_honest_degradation_missing"})

    education = _mapping(domain_runs.get("education"))
    education_stages = _mapping(education.get("stage_trace"))
    education_generation = _mapping(education_stages.get("generation"))
    education_value = _mapping(education_stages.get("value"))
    pack = _read_json(REPO_ROOT / N10A_PACK_PATH)
    expected_education_levers = sorted(
        str(row.get("lever_id") or "")
        for row in _mappings(
            _mapping(_mapping(pack.get("components")).get("lever_vocabulary")).get(
                "entries"
            )
        )
    )
    if sorted(_strings(education_generation.get("proposed_lever_ids"))) != (
        expected_education_levers
    ):
        issues.append({"code": "education_pack_lever_denominator_missing"})
    if (
        education_value.get("status") != "value_blocked"
        or _strings(education_value.get("authority_blockers"))
        != ["method_estimand_binding_mismatch"]
        or not education_value.get("advisor_selection_receipt_content_hash")
        or education.get("promotion_reached") is not False
    ):
        issues.append({"code": "education_honest_refusal_missing"})
    baseline = _mapping(education.get("baseline_diff"))
    if (
        baseline.get("baseline_terminal") != "a_spec_gap"
        or baseline.get("moved_past_a_spec_gap") is not True
    ):
        issues.append({"code": "education_baseline_movement_missing"})

    unseen = _mapping(domain_runs.get("unseen"))
    unseen_text = _canonical_json(unseen).casefold()
    if unseen.get("cycle_substrate_context_ref") is not None:
        issues.append({"code": "unseen_domain_pack_substitution"})
    forbidden = (
        "education_spending",
        "school_quality",
        "teaching_method",
        "tax_relief_rate",
        "ua_msme_cgf_decisive_capture",
    )
    contaminants = [item for item in forbidden if item in unseen_text]
    if contaminants:
        issues.append(
            {
                "code": "unseen_domain_vertical_contamination",
                "tokens": contaminants,
            }
        )
    return issues


def write_payload(repo_root: Path, output_path: Path) -> bytes:
    """Write a byte-stable pending test payload or completed canonical proof.

    Args:
        repo_root: Policy Engine checkout root.
        output_path: Explicit destination. Canonical writes require previously
            captured owner recordings; noncanonical writes remain Lane 0.

    Returns:
        Exact bytes written.

    Raises:
        UniversalityContractError: If cached recordings are absent or invalid.
    """

    root = repo_root.resolve()
    canonical = output_path.resolve() == (root / OUTPUT_PATH).resolve()
    payload = build_live_payload(root, lane="cached" if canonical else "lane0")
    report = validate_payload(payload)
    if canonical and report["status"] != "pass":
        raise UniversalityContractError(
            "universality_contract_write_invalid:"
            + ",".join(str(item.get("code")) for item in report["issues"])
        )
    data = (_canonical_json(payload) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return data


def capture_and_write_payload(repo_root: Path) -> bytes:
    """Run the single cold closeout and write only after semantic validation."""

    root = repo_root.resolve()
    output_path = root / OUTPUT_PATH
    if output_path.exists():
        raise UniversalityContractError("proof_capture_already_exists")
    stability = check_provenance_stability(root)
    if stability.get("status") != "stable":
        raise UniversalityContractError("provenance_stability_failed")
    recordings = asyncio.run(_capture_proof_recordings(root))
    payload = asyncio.run(
        _complete_payload_from_recordings(root, recordings=recordings)
    )
    report = validate_payload(payload)
    if report["status"] != "pass":
        _append_capture_journal(
            root,
            {
                "event": "cold_closeout_refused_before_artifact_write",
                "issues": report["issues"],
            },
        )
        raise UniversalityContractError(
            "captured_proof_semantically_invalid:"
            + ",".join(str(item.get("code")) for item in report["issues"])
        )
    data = (_canonical_json(payload) + "\n").encode("utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    _append_capture_journal(
        root,
        {
            "event": "cold_closeout_artifact_written",
            "contract_content_hash": payload["contract_content_hash"],
        },
    )
    return data


def corrupt_field_drift_check(repo_root: Path) -> dict[str, Any]:
    """Corrupt one semantic field and require the hash verifier to reject it."""

    lane = "cached" if (repo_root / OUTPUT_PATH).is_file() else "lane0"
    payload = build_live_payload(repo_root, lane=lane)
    payload["proof_status"] = (
        "proof_runs_pending" if lane == "cached" else "complete"
    )
    report = validate_payload(payload)
    detected = any(
        issue.get("code") == "contract_content_hash_mismatch"
        for issue in report["issues"]
    )
    return {
        "status": "fail" if detected else "pass",
        "issues": report["issues"] if detected else [
            {"code": "corrupt_field_drift_not_detected"}
        ],
        "expected_exit": 1,
    }


def _check_canonical(repo_root: Path) -> dict[str, Any]:
    stability = check_provenance_stability(repo_root)
    if stability.get("status") != "stable":
        return {"status": "fail", "issues": stability.get("issues", [])}
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "universality_contract_artifact_missing"}],
        }
    payload = _read_json(path)
    report = validate_payload(payload)
    if payload.get("proof_status") != "complete":
        report["issues"].append({"code": "proof_runs_pending"})
        report["status"] = "fail"
    return report


def _rederive_audit(repo_root: Path) -> dict[str, Any]:
    stability = check_provenance_stability(repo_root)
    if stability.get("status") != "stable":
        return {"status": "fail", "issues": stability.get("issues", [])}
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        return {
            "status": "fail",
            "issues": [{"code": "universality_contract_artifact_missing"}],
        }
    live = build_live_payload(repo_root, lane="cached")
    committed = _read_json(path)
    issues = list(validate_payload(committed)["issues"])
    if committed != live:
        issues.append({"code": "universality_contract_rederive_drift"})
    return {"status": "pass" if not issues else "fail", "issues": issues}


def _main_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(REPO_ROOT)
        return report, 1 if report["status"] == "fail" else 0
    if args.source_flip_mutations:
        return {
            "status": "fail",
            "issues": [{"code": "source_flip_mutations_pending"}],
        }, 1
    if args.rederive_audit:
        report = _rederive_audit(REPO_ROOT)
        return report, 0 if report["status"] == "pass" else 1
    if args.capture_proof_runs:
        try:
            data = capture_and_write_payload(REPO_ROOT)
        except (UniversalityContractError, ValueError) as exc:
            return {
                "status": "fail",
                "issues": [
                    {"code": str(exc).partition(":")[0], "error": str(exc)}
                ],
            }, 1
        payload = json.loads(data)
        return {
            "status": "pass",
            "issues": [],
            "contract_content_hash": payload["contract_content_hash"],
            "domain_terminals": {
                role: run["terminal_distribution"]
                for role, run in payload["domain_runs"].items()
            },
        }, 0
    if args.write:
        stability = check_provenance_stability(REPO_ROOT)
        if stability.get("status") != "stable":
            return {"status": "fail", "issues": stability.get("issues", [])}, 1
        try:
            data = write_payload(REPO_ROOT, REPO_ROOT / OUTPUT_PATH)
        except (UniversalityContractError, ValueError) as exc:
            return {
                "status": "fail",
                "issues": [
                    {"code": str(exc).partition(":")[0], "error": str(exc)}
                ],
            }, 1
        payload = json.loads(data)
        return {
            "status": "pass",
            "issues": [],
            "contract_content_hash": payload["contract_content_hash"],
        }, 0
    report = _check_canonical(REPO_ROOT)
    return report, 0 if report["status"] == "pass" else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run one universality validator mode after the mandatory preflight."""

    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--corrupt-field-drift-check", action="store_true")
    modes.add_argument("--rederive-audit", action="store_true")
    modes.add_argument("--source-flip-mutations", action="store_true")
    modes.add_argument("--capture-proof-runs", action="store_true")
    modes.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    report, exit_code = _main_report(args)
    report["wall_time_seconds"] = round(max(0.0, time.monotonic() - started), 6)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, sort_keys=True))
    return exit_code


def _dirty_upstream_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *_UPSTREAM_PATHS],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise UniversalityContractError(
            "upstream_dirty_census_failed:" + result.stderr.strip()
        )
    return sorted(
        line[3:].strip()
        for line in result.stdout.splitlines()
        if line.strip()
    )


def _extend_owner_issues(
    target: list[dict[str, Any]],
    owner: str,
    owner_issues: object,
) -> None:
    for issue in owner_issues or ():
        if isinstance(issue, Mapping):
            target.append(
                {
                    "code": f"{owner}_owner_validation_failed",
                    "owner_issue": dict(issue),
                }
            )
        else:
            target.append(
                {"code": f"{owner}_owner_validation_failed", "owner_issue": issue}
            )


def _joint_simulation_receipts(recursive_run: Mapping[str, Any]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for node in _mappings(recursive_run.get("nodes")):
        simulation = _mapping(node.get("joint_simulation"))
        receipt = _mapping(simulation.get("receipt"))
        if not receipt:
            continue
        receipts.append(
            {
                "node_ref": node.get("node_ref"),
                "receipt_id": receipt.get("receipt_id"),
                "payload_hash": receipt.get("payload_hash"),
                "uncertainty_kind": receipt.get("uncertainty_kind"),
                "interaction_term_count": len(
                    simulation.get("interaction_terms") or []
                ),
            }
        )
    return receipts


def _contract_content_hash(payload: Mapping[str, Any]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in _CONTENT_HASH_EXCLUDED_TOP_LEVEL
    }
    return _semantic_hash(stable)


def _volatile_content_paths(value: object, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if path == "$" and key == "runtime_metrics":
                continue
            lowered = str(key).lower()
            if any(
                token in lowered
                for token in ("timestamp", "wall_time", "elapsed", "generated_at")
            ):
                paths.append(child_path)
            paths.extend(_volatile_content_paths(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_volatile_content_paths(item, f"{path}[{index}]"))
    return paths


def _mutate_volatile_values(value: object, path: str = "$") -> None:
    """Perturb operational clocks so the hash gate proves they are excluded."""

    if isinstance(value, dict):
        for key, item in value.items():
            if path == "$" and key == "runtime_metrics":
                continue
            lowered = str(key).lower()
            if any(
                token in lowered
                for token in ("timestamp", "wall_time", "elapsed", "generated_at")
            ):
                value[key] = "gy-n10-operational-clock-mutation"
            else:
                _mutate_volatile_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _mutate_volatile_values(item, f"{path}[{index}]")


def _values_for_key(value: object, target_key: str) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == target_key and isinstance(item, str):
                values.append(item)
            values.extend(_values_for_key(item, target_key))
    elif isinstance(value, list):
        for item in value:
            values.extend(_values_for_key(item, target_key))
    return values


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise UniversalityContractError(f"json_object_required:{path.name}")
    return payload


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _semantic_hash(value: object) -> str:
    """Hash semantic content through the canonical clock-excluding owner."""

    from polisyos.pdc import gy_content_hash

    return gy_content_hash(value)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


if __name__ == "__main__":
    raise SystemExit(main())
