#!/usr/bin/env python3
"""Validate the Layer 3 GY-N4 design-generation firewall contract."""

from __future__ import annotations

from time import perf_counter as _timing_perf_counter

_TIMING_STARTED_AT = _timing_perf_counter()

import argparse
import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.design_generation import (
    DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION,
    DESIGN_GENERATION_SCHEMA_VERSION,
    NOT_CERTIFICATE_KINDS,
    SUPPORTED_GENERATION_MODEL_IDS,
    EffectiveGenerationRuntimeConfig,
    GenerationUnderAResult,
    GroundingDispositionRecord,
    _content_bound_candidates,
    _grounding_disposition_summary,
    _grounding_proposal_for_intervention,
    _json_for_prompt_size,
    _with_generation_cycle_revision_context,
    _with_lever_space_prompt_slice,
    firewall_issues_for_result,
    generate_design_candidates_under_a,
    validate_design_generation_strangle_receipts,
)
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMResponse,
    GatewayUsage,
)
from tools.lib.timing import run_timed_entrypoint

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
RECORDING_FIXTURE_PATH = (
    "architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json"
)
MODEL_ID = SUPPORTED_GENERATION_MODEL_IDS[0]
SOURCE_FLIP_MUTATION_ID = "source_flip_formalizer_recorded_path_derivation_removed"
POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID = (
    "source_flip_policy_verified_fixture_reconnected_to_production"
)
NL_SOURCE_FLIP_MUTATION_ID = "source_flip_nl_contract_agents_reconnected_to_production"
S2_SOURCE_FLIP_MUTATION_ID = "source_flip_s2_fixed_candidate_body_restored"
DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID = (
    "source_flip_drafter_naive_json_parser_restored"
)
RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID = (
    "source_flip_recorded_effective_runtime_config_ignored"
)
PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID = "source_flip_prompt_size_estimate_fixed_default"
CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID = (
    "source_flip_candidate_lever_provenance_removed"
)
CURRENT_WMR_REISSUE_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.current_wmr_reissue_receipt.v1"
)
_PROMPT_SLICE_LIMIT_CHARS = 5000
_FROZEN_DIAGNOSTIC_PROJECTION = {
    "schema_version": "policyos.gy.n4.diagnostic_projection.v1",
    "elapsed_measurements": "journal_only_not_committed",
    "prompt_size_measurement": (
        "prompt_local_created_at_excluded_full_measurement_verified_live_then_omitted"
    ),
    "prompt_slice_limit_chars": _PROMPT_SLICE_LIMIT_CHARS,
}
N4_SOURCE_FLIP_MUTATION_IDS: tuple[str, ...] = (
    SOURCE_FLIP_MUTATION_ID,
    DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
    RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
    PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
    CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID,
    POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
    NL_SOURCE_FLIP_MUTATION_ID,
    S2_SOURCE_FLIP_MUTATION_ID,
)


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


class RecordedGenerationReplayClient:
    """Test-only replay transport over recorded gateway raw responses."""

    def __init__(self, recording: dict[str, Any]) -> None:
        self._recording = recording
        self._responses = [
            dict(item)
            for item in recording.get("responses") or []
            if isinstance(item, dict)
        ]
        self._cursor = 0

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        return [str(self._recording["model_id"])]

    async def generate(self, **kwargs: object) -> GatewayLLMResponse:
        if self._cursor >= len(self._responses):
            raise RuntimeError("gy_n4_recorded_response_exhausted")
        recorded = self._responses[self._cursor]
        label = _recorded_response_label(recorded, self._cursor)
        # Replay integrity is the recorded model output bytes. Prompt hashes are
        # retained as capture provenance only; current prompt assembly is guarded
        # by Lane-0 prompt unit tests, while this contract replays real outputs
        # through the live CG1->CG2->CG3 firewall.
        if recorded.get("status") == "error":
            raw_error = recorded.get("raw_response")
            recorded_hash = recorded.get("raw_response_hash")
            if not isinstance(raw_error, str):
                raise RuntimeError(f"gy_n4_recorded_raw_response_missing:{label}")
            if not isinstance(recorded_hash, str) or not recorded_hash:
                raise RuntimeError(f"gy_n4_recorded_raw_response_hash_missing:{label}")
            actual_hash = gy_content_hash(raw_error)
            if actual_hash != recorded_hash:
                raise RuntimeError(
                    "gy_n4_recorded_raw_response_hash_mismatch:"
                    f"{label}:{actual_hash}!={recorded_hash}"
                )
            self._cursor += 1
            error = recorded.get("error")
            error_payload = error if isinstance(error, dict) else {}
            status = error_payload.get("status")
            code = error_payload.get("code")
            message = str(error_payload.get("message") or "recorded gateway error")
            raise RecordedGatewayError(
                message,
                status=status if isinstance(status, int) else None,
                error_code=code if isinstance(code, str) else None,
                retry_after_s=(
                    float(error_payload["retry_after_s"])
                    if isinstance(error_payload.get("retry_after_s"), int | float)
                    else None
                ),
            )
        raw = recorded.get("raw_response")
        if not isinstance(raw, str) or not raw:
            raise RuntimeError(f"gy_n4_recorded_raw_response_missing:{label}")
        recorded_hash = recorded.get("raw_response_hash")
        if not isinstance(recorded_hash, str) or not recorded_hash:
            raise RuntimeError(f"gy_n4_recorded_raw_response_hash_missing:{label}")
        actual_hash = gy_content_hash(raw)
        if actual_hash != recorded_hash:
            raise RuntimeError(
                "gy_n4_recorded_raw_response_hash_mismatch:"
                f"{label}:{actual_hash}!={recorded_hash}"
            )
        usage = recorded.get("usage")
        usage_payload = usage if isinstance(usage, dict) else {}
        self._cursor += 1
        return GatewayLLMResponse(
            content=raw,
            usage=GatewayUsage(
                prompt_tokens=int(usage_payload.get("prompt_tokens") or 0),
                completion_tokens=int(usage_payload.get("completion_tokens") or 0),
                total_tokens=int(usage_payload.get("total_tokens") or 0),
            ),
            model=str(self._recording["model_id"]),
            provider="recorded_gateway_replay",
        )


class RecordedGatewayError(RuntimeError):
    """Replay a recorded gateway failure without changing prompt-repair text."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_code: str | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.retry_after_s = retry_after_s


def _recorded_response_label(recorded: dict[str, Any], index: int) -> str:
    role = recorded.get("role")
    return f"{index}:{role if isinstance(role, str) and role else 'unknown'}"


_RECORDED_RUNTIME_INPUT_FIELDS = frozenset(
    {
        "drafter_pass_timeout_s",
        "drafter_pass_retry_count",
        "formalizer_timeout_s",
        "formalizer_retry_count",
        "critic_timeout_s",
        "terminal_salvage_retry_count",
        "terminal_salvage_backoff_base_s",
        "gateway_timeout_s",
        "gateway_max_retries",
        "prompt_cache_ttl_s",
        "prompt_cache_maxsize",
        "cg1_index_prewarm_enabled",
    }
)


def _verify_recording_content_hash(recording: Mapping[str, Any]) -> None:
    recorded = recording.get("recording_content_hash")
    if not isinstance(recorded, str) or not recorded:
        raise RuntimeError("gy_n4_recording_content_hash_missing")
    computed = gy_content_hash(
        {
            key: value
            for key, value in recording.items()
            if key != "recording_content_hash"
        }
    )
    if computed != recorded:
        raise RuntimeError(
            f"gy_n4_recording_content_hash_mismatch:{computed}!={recorded}"
        )


def _resolve_current_wmr_owner_projection(repo_root: Path) -> dict[str, str]:
    """Resolve and structurally verify the current composed-WMR owner."""

    from polisyos.runtime.quality.intervention_substrate import (
        production_composed_world_model_record,
    )
    from polisyos.runtime.quality.world_model_record import (
        WorldModelRecord,
        world_model_record_content_hash,
    )

    owner = production_composed_world_model_record(repo_root.resolve())
    validated = WorldModelRecord.model_validate(owner.model_dump(mode="json"))
    recomputed_hash = world_model_record_content_hash(validated)
    if validated.content_hash != recomputed_hash:
        raise RuntimeError("gy_n4_current_wmr_owner_content_hash_mismatch")
    projection = {
        "schema_version": validated.schema_version,
        "world_model_record_id": validated.world_model_record_id,
        "world_model_record_content_hash": recomputed_hash,
        "producer_ref": validated.producer_ref,
    }
    _validate_current_wmr_owner_projection(projection)
    return projection


def _validate_current_wmr_owner_projection(projection: Mapping[str, Any]) -> None:
    content_hash = projection.get("world_model_record_content_hash")
    record_id = projection.get("world_model_record_id")
    schema_version = projection.get("schema_version")
    producer_ref = projection.get("producer_ref")
    if (
        not isinstance(content_hash, str)
        or not content_hash.startswith("sha256:")
        or len(content_hash) != 71
        or any(character not in "0123456789abcdef" for character in content_hash[7:])
    ):
        raise RuntimeError("gy_n4_current_wmr_owner_content_hash_invalid")
    expected_record_id = f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}"
    if record_id != expected_record_id:
        raise RuntimeError("gy_n4_current_wmr_owner_id_content_mismatch")
    if not isinstance(schema_version, str) or not schema_version:
        raise RuntimeError("gy_n4_current_wmr_owner_schema_missing")
    if not isinstance(producer_ref, str) or not producer_ref:
        raise RuntimeError("gy_n4_current_wmr_owner_producer_missing")


def _recording_non_wmr_projection(recording: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in recording.items()
        if key not in {"recording_content_hash", "world_model_record_ref"}
    }


def _assert_wmr_only_recording_reissue(
    historical: Mapping[str, Any],
    reissued: Mapping[str, Any],
) -> None:
    """Refuse a replay overlay that changes any historical non-WMR byte."""

    historical_projection = _recording_non_wmr_projection(historical)
    reissued_projection = _recording_non_wmr_projection(reissued)
    if historical_projection != reissued_projection:
        raise RuntimeError("gy_n4_current_wmr_reissue_non_wmr_drift")


def _reissue_recordings_to_current_wmr(
    historical_recordings: list[dict[str, Any]],
    *,
    owner_projection: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Overlay verified historical responses onto the current composed WMR."""

    _validate_current_wmr_owner_projection(owner_projection)
    owner = dict(owner_projection)
    current_ref = str(owner["world_model_record_id"])
    reissued_recordings: list[dict[str, Any]] = []
    receipt_rows: list[dict[str, Any]] = []
    for historical in historical_recordings:
        _validate_recording_fixture(historical)
        reissued = copy.deepcopy(historical)
        reissued["world_model_record_ref"] = current_ref
        reissued["recording_content_hash"] = gy_content_hash(
            {
                key: value
                for key, value in reissued.items()
                if key != "recording_content_hash"
            }
        )
        _assert_wmr_only_recording_reissue(historical, reissued)
        _validate_recording_fixture(reissued)
        reissued_recordings.append(reissued)
        receipt_rows.append(
            {
                "historical_recording_content_hash": historical[
                    "recording_content_hash"
                ],
                "historical_world_model_record_ref": historical.get(
                    "world_model_record_ref"
                ),
                "preserved_non_wmr_projection_hash": gy_content_hash(
                    _recording_non_wmr_projection(historical)
                ),
                "recording_id": historical.get("recording_id"),
                "reissued_recording_content_hash": reissued[
                    "recording_content_hash"
                ],
                "reissued_world_model_record_ref": current_ref,
            }
        )
    receipt: dict[str, Any] = {
        "schema_version": CURRENT_WMR_REISSUE_SCHEMA_VERSION,
        "mode": "offline_verified_historical_response_current_wmr_overlay",
        "owner_projection": owner,
        "owner_projection_content_hash": gy_content_hash(owner),
        "recordings": receipt_rows,
    }
    receipt["content_hash"] = gy_content_hash(receipt)
    return reissued_recordings, receipt


def _current_wmr_reissue_receipt_issues(
    payload: Mapping[str, Any],
    historical_recordings: list[dict[str, Any]],
    *,
    owner_projection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Recompute the reissue receipt from the current owner and historical rows."""

    issues: list[dict[str, Any]] = []
    recorded = payload.get("current_wmr_reissue_receipt")
    if not isinstance(recorded, Mapping):
        return [{"code": "current_wmr_reissue_receipt_missing"}]
    try:
        _validate_current_wmr_owner_projection(owner_projection)
    except RuntimeError as exc:
        return [
            {
                "code": "current_wmr_reissue_owner_projection_invalid",
                "error": str(exc),
            }
        ]
    if recorded.get("owner_projection") != dict(owner_projection):
        return [{"code": "current_wmr_reissue_receipt_owner_projection_drift"}]
    _reissued, expected = _reissue_recordings_to_current_wmr(
        historical_recordings,
        owner_projection=owner_projection,
    )
    if recorded.get("owner_projection_content_hash") != expected.get(
        "owner_projection_content_hash"
    ):
        issues.append(
            {"code": "current_wmr_reissue_receipt_owner_projection_hash_drift"}
        )
    if recorded.get("recordings") != expected.get("recordings"):
        issues.append({"code": "current_wmr_reissue_receipt_recording_binding_drift"})
    if recorded.get("content_hash") != gy_content_hash(
        {key: value for key, value in recorded.items() if key != "content_hash"}
    ):
        issues.append({"code": "current_wmr_reissue_receipt_content_hash_drift"})
    if dict(recorded) != expected and not issues:
        issues.append({"code": "current_wmr_reissue_receipt_contract_drift"})
    generation_results = payload.get("generation_results")
    if isinstance(generation_results, list) and generation_results:
        observed_refs = set(_nested_values_for_key(generation_results, "world_model_record_ref"))
        expected_ref = str(owner_projection["world_model_record_id"])
        if not observed_refs:
            issues.append({"code": "current_wmr_reissue_generation_binding_missing"})
        elif observed_refs != {expected_ref}:
            issues.append(
                {
                    "code": "current_wmr_reissue_generation_binding_drift",
                    "expected": expected_ref,
                    "observed": sorted(observed_refs),
                }
            )
    return issues


def _nested_values_for_key(value: Any, key: str) -> list[str]:
    values: list[str] = []
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            if nested_key == key and isinstance(nested_value, str) and nested_value:
                values.append(nested_value)
            else:
                values.extend(_nested_values_for_key(nested_value, key))
    elif isinstance(value, list | tuple):
        for item in value:
            values.extend(_nested_values_for_key(item, key))
    return values


def _recorded_effective_runtime_config(
    recording: Mapping[str, Any],
) -> EffectiveGenerationRuntimeConfig:
    _verify_recording_content_hash(recording)
    capture_summary = recording.get("capture_summary")
    if not isinstance(capture_summary, Mapping):
        raise RuntimeError("recorded_effective_runtime_config_missing:capture_summary")
    payload = capture_summary.get("effective_runtime_config")
    if not isinstance(payload, Mapping):
        raise RuntimeError("recorded_effective_runtime_config_missing")
    missing_inputs = sorted(_RECORDED_RUNTIME_INPUT_FIELDS.difference(payload))
    if missing_inputs:
        raise RuntimeError(
            "recorded_effective_runtime_config_input_missing:"
            + ",".join(missing_inputs)
        )
    try:
        config = EffectiveGenerationRuntimeConfig.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("recorded_effective_runtime_config_invalid") from exc
    if not config.formalizer_schema_healing_events:
        raise RuntimeError("recorded_effective_runtime_config_healing_mode_unrecorded")
    return config


def _recorded_runtime_input_projection(
    config: EffectiveGenerationRuntimeConfig,
) -> dict[str, float | int | bool]:
    optional_inputs = {
        "gateway_timeout_s": config.gateway_timeout_s,
        "gateway_max_retries": config.gateway_max_retries,
        "prompt_cache_ttl_s": config.prompt_cache_ttl_s,
        "prompt_cache_maxsize": config.prompt_cache_maxsize,
    }
    missing = sorted(key for key, value in optional_inputs.items() if value is None)
    if missing:
        raise RuntimeError(
            "recorded_effective_runtime_config_input_missing:" + ",".join(missing)
        )
    return {
        "drafter_pass_timeout_s": config.drafter_pass_timeout_s,
        "drafter_pass_retry_count": config.drafter_pass_retry_count,
        "formalizer_timeout_s": config.formalizer_timeout_s,
        "formalizer_retry_count": config.formalizer_retry_count,
        "critic_timeout_s": config.critic_timeout_s,
        "terminal_salvage_retry_count": config.terminal_salvage_retry_count,
        "terminal_salvage_backoff_base_s": config.terminal_salvage_backoff_base_s,
        "gateway_timeout_s": float(config.gateway_timeout_s),
        "gateway_max_retries": int(config.gateway_max_retries),
        "prompt_cache_ttl_s": float(config.prompt_cache_ttl_s),
        "prompt_cache_maxsize": int(config.prompt_cache_maxsize),
        "cg1_index_prewarm_enabled": config.cg1_index_prewarm_enabled,
    }


def _recorded_runtime_environment_values(
    config: EffectiveGenerationRuntimeConfig,
) -> dict[str, str]:
    inputs = _recorded_runtime_input_projection(config)
    return {
        "POLISYOS_DRAFTER_PASS_TIMEOUT_S": str(inputs["drafter_pass_timeout_s"]),
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": str(inputs["drafter_pass_retry_count"]),
        "POLISYOS_FORMALIZER_LLM_TIMEOUT_S": str(inputs["formalizer_timeout_s"]),
        "POLISYOS_FORMALIZER_LLM_RETRIES": str(inputs["formalizer_retry_count"]),
        "POLISYOS_CRITIC_LLM_TIMEOUT_S": str(inputs["critic_timeout_s"]),
        "POLISYOS_N4_TERMINAL_SALVAGE_RETRIES": str(
            inputs["terminal_salvage_retry_count"]
        ),
        "POLISYOS_N4_TERMINAL_SALVAGE_BACKOFF_BASE_S": str(
            inputs["terminal_salvage_backoff_base_s"]
        ),
        "POLISYOS_LLM_GATEWAY_TIMEOUT_S": str(inputs["gateway_timeout_s"]),
        "POLISYOS_LLM_GATEWAY_MAX_RETRIES": str(inputs["gateway_max_retries"]),
        "POLISYOS_LLM_CACHE_TTL_S": str(inputs["prompt_cache_ttl_s"]),
        "POLISYOS_LLM_CACHE_MAXSIZE": str(inputs["prompt_cache_maxsize"]),
        "POLISYOS_N4_PREWARM_CG1_INDEX": (
            "1" if inputs["cg1_index_prewarm_enabled"] else "0"
        ),
        # Historical v1 receipts did not persist the mode field itself. Their
        # non-empty healing-event denominator proves audit mode: strict mode
        # would have refused before emitting the captured result.
        "POLISYOS_FORMALIZER_SCHEMA_HEALING_MODE": "audit",
    }


@contextmanager
def _recorded_runtime_environment(
    recording: Mapping[str, Any],
) -> Iterator[EffectiveGenerationRuntimeConfig]:
    expected = _recorded_effective_runtime_config(recording)
    runtime_environment = _recorded_runtime_environment_values(expected)
    missing = object()
    previous: dict[str, object] = {
        key: os.environ.get(key, missing) for key in runtime_environment
    }
    try:
        os.environ.update(runtime_environment)
        yield expected
    finally:
        for key, value in previous.items():
            if value is missing:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)


async def _run_live_generation(
    repo_root: Path,
    *,
    recording: dict[str, Any],
) -> GenerationUnderAResult:
    client = RecordedGenerationReplayClient(recording)
    world_model_record_ref = recording.get("world_model_record_ref")
    with _recorded_runtime_environment(recording) as expected_config:
        result = await generate_design_candidates_under_a(
            _design_problem(recording),
            model_id=str(recording["model_id"]),
            llm_client=client,
            repo_root=repo_root,
            world_model_record_ref=(
                str(world_model_record_ref) if world_model_record_ref else None
            ),
        )
        emitted_config = getattr(result, "effective_runtime_config", None)
        try:
            emitted = EffectiveGenerationRuntimeConfig.model_validate(emitted_config)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("recorded_effective_runtime_config_emission_missing") from exc
        expected_inputs = _recorded_runtime_input_projection(expected_config)
        emitted_inputs = _recorded_runtime_input_projection(emitted)
        if emitted_inputs != expected_inputs:
            raise RuntimeError(
                "recorded_effective_runtime_config_drift:"
                + json.dumps(
                    {"expected": expected_inputs, "emitted": emitted_inputs},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
    # Historical fixtures can include retry/repair tail calls that current live
    # assembly no longer reaches. The fixture loader still validates every
    # recorded raw_response_hash; replay only gates the outputs actually served
    # to the live CG pipeline.
    return result


def build_live_payload(repo_root: Path) -> dict[str, Any]:
    """Recompute the GY-N4 contract from live code and deterministic replay provenance."""

    historical_recordings = _load_recordings(repo_root)
    if not historical_recordings:
        raise RuntimeError("gy_n4_replay_recording_denominator_missing")
    owner_projection = _resolve_current_wmr_owner_projection(repo_root)
    recordings, current_wmr_reissue_receipt = _reissue_recordings_to_current_wmr(
        historical_recordings,
        owner_projection=owner_projection,
    )
    results = [
        asyncio.run(_run_live_generation(repo_root.resolve(), recording=recording))
        for recording in recordings
    ]
    prompt_size_frame_issues = [
        issue
        for recording, replay_result in zip(recordings, results, strict=True)
        if (
            issue := _prompt_size_actual_frame_issue(
                design_problem=_design_problem(recording),
                lever_space_prompt_slice=replay_result.lever_space_prompt_slice,
                emitted=replay_result.effective_runtime_config.prompt_size_estimate,
            )
        )
        is not None
    ]
    if prompt_size_frame_issues:
        raise RuntimeError(
            "gy_n4_prompt_size_measurement_not_actual_frames:"
            + json.dumps(
                prompt_size_frame_issues,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    result = results[0]
    if len(recordings) >= 2:
        variation = results[1]
        variation_report = _problem_variation_report(result, variation, recordings=recordings[:2])
    else:
        variation_report = {
            "status": "not_run",
            "reason": "second_recording_not_required_for_rev13_cgf_hook",
            "cases": [],
        }
    cg3_handoff_probe = _synthetic_cg3_handoff_probe(repo_root.resolve(), recordings[0])
    grounding_payoff = _grounding_payoff_report(
        results,
        cg3_handoff_probe=cg3_handoff_probe,
    )
    result_payload = result.model_dump(mode="json")
    result_payloads = [item.model_dump(mode="json") for item in results]
    set_coverage = _recording_set_coverage(results)
    base: dict[str, Any] = {
        "schema_version": DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION,
        "gy_lifecycle_marker": DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION,
        "contract_id": "policyos.runtime.design_generation_under_a",
        "runtime_schema_version": DESIGN_GENERATION_SCHEMA_VERSION,
        "producer": "tools.quality.validation.check_layer3_gy_design_generation_contract",
        "source_modules": [
            "src/polisyos/runtime/quality/design_generation.py",
            "src/polisyos/runtime/quality/intervention_substrate.py",
            "src/polisyos/runtime/quality/intervention_atom_binding.py",
            "src/polisyos/runtime/quality/world_model_record.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_admission.py",
            "src/polisyos/runtime/quality/grounding_phrasing_defense.py",
            "src/polisyos/runtime/quality/grounding_active_controller.py",
            "src/polisyos/scientist/agent/drafter_clients.py",
            "src/polisyos/scientist/agent/_drafter_orchestrator.py",
            "src/polisyos/scientist/agent/formalizer.py",
            "src/polisyos/scientist/agent/critic.py",
            "src/polisyos/scientist/agent/prompts.py",
            RECORDING_FIXTURE_PATH,
        ],
        "canonical_path": [
            "LLMDrafterAgent.draft_policy",
            "MultiPassLLMDrafter",
            "LLMFormalizerAgent.formalize",
            "LLMCriticAgent.critique",
            "GroundingRelationEngine.certificate_for",
            "GroundingBindGate.certificate_for",
            "GroundingAdmissionEngine.decide",
            "InterventionAtomBinding(candidate_unverified, certificate-bound)",
        ],
        "supported_model_ids": list(SUPPORTED_GENERATION_MODEL_IDS),
        "recording_fixture_ref": RECORDING_FIXTURE_PATH,
        "recording_fixture_hash": _fixture_hash(repo_root),
        "recording_fixture_integrity": _recording_fixture_integrity_report(
            historical_recordings
        ),
        "current_wmr_reissue_receipt": current_wmr_reissue_receipt,
        "diagnostic_projection": dict(_FROZEN_DIAGNOSTIC_PROJECTION),
        "prompt_size_gate": _prompt_size_gate(result_payloads),
        "replay_fixture_versioning": {
            "follow_up": "GY_N4_REPLAY_FIXTURE_VERSIONING_AND_CG_CONTRACT_DECOUPLING",
            "status": "closed",
            "prompt_hash_role": "recorded_provenance_only",
            "replay_gate": "raw_response_hash",
            "lane0_prompt_assembly_guard": (
                "unit assertions cover hash-bound lever-space prompt slice, "
                "axis-ontology drafter instruction, and adapter map-and-omit behavior"
            ),
        },
        "not_certificate_denominator": list(NOT_CERTIFICATE_KINDS),
        "source_flip_mutation_harness": {
            "mode": "--source-flip-mutations",
            "mutation_ids": list(N4_SOURCE_FLIP_MUTATION_IDS),
            "property": "patch_source_then_causal_red_then_restore_exact_bytes",
        },
        "generation_results": result_payloads,
        "recording_set_coverage": set_coverage,
        "grounding_payoff": grounding_payoff,
        "synthetic_cg3_handoff_probe": cg3_handoff_probe,
        "recording_set_gate": {
            "required_live_classes": [
                "at_least_3_diverse_real_candidates",
                "at_least_1_legacy_rejected_shadow_bound_recovery",
            ],
            "novel_cg3_live_requirement": "desirable_recorded_not_required_after_mapping_second_guess_fix",
            "deterministic_cg3_handoff_probe": "required",
            "reason": (
                "N4 previously second-guessed CG1 by converting proposal-level "
                "novel-candidate certificates with critical contradictions into vetoes; "
                "after the fix, live novel_cg3 is recorded when present but the closure "
                "gate requires deterministic CG3 handoff plus live legacy-rejected recovery."
            ),
        },
        "adapter_honesty_probe": _adapter_honesty_probe(recordings[0]),
        "known_cg6_finding": {
            "finding_id": "CG6_REAL_FIREWALL_GAP",
            "status": "referenced_not_repaired_in_gy_n4",
            "note": (
                "CG1 certified-specialization has four recorded generalization gaps; "
                "CG2 abstained on all, so shadow-only N4 wiring remains acceptable."
            ),
        },
        "honesty_notes": {
            "normalization_warrant_dropped_mutation": {
                "exercise": "synthetic_contract_corruption",
                "real_recording_spelling_swap_present": False,
                "note": (
                    "The committed replay set exercises certified shadow bindings but "
                    "does not currently include a real normalized_from spelling/slot "
                    "swap. The normalization_warrant_dropped mutation therefore "
                    "corrupts a shadow-bound candidate into an unmarked normalization "
                    "case and must be revisited when a real swap recording lands."
                ),
            },
            "drift_canonicalization_scope": {
                "normalized_measured_diagnostics": [
                    "llm_calls[].wall_seconds",
                    "effective_runtime_config.cg1_index_prewarm_wall_seconds",
                    "effective_runtime_config.prompt_size_estimate",
                ],
                "content_binding_preserved": [
                    "lever_space_prompt_slice.content_hash",
                    "candidate/atom content_hashes",
                    "grounding certificate hashes",
                    "raw_response_hashes",
                ],
                "prompt_hashes": "recorded_provenance_only_not_replay_gate",
                "note": (
                    "Artifact drift canonicalization ignores only replay-local measured "
                    "diagnostics; recorded outputs, slice, candidate, atom, and "
                    "certificate content remain hash-bound. Prompt hashes are retained "
                    "only as capture provenance because prompt assembly is guarded in "
                    "Lane-0 unit tests."
                ),
            },
        },
        "problem_variation_probe": variation_report,
        "positive_gate": {
            "min_diverse_model_generated_candidates": 3,
            "status": "generated" if all(item.status == "generated" for item in results) else "fail",
            "recording_count": len(results),
            "candidate_count": set_coverage["candidate_count"],
            "grounding_disposition_count": set_coverage["grounding_disposition_count"],
            "grounding_summary": set_coverage["grounding_summary"],
            "lever_space_prompt_slice_hashes": [
                item.lever_space_prompt_slice.content_hash for item in results
            ],
            "unique_diversity_key_count": set_coverage["unique_diversity_key_count"],
            "candidate_statuses": [
                candidate.status for item in results for candidate in item.candidates
            ],
            "generator_paths": [
                candidate.generator_path for item in results for candidate in item.candidates
            ],
            "content_hashes": [
                candidate.atom.content_hash for item in results for candidate in item.candidates
            ],
        },
        "strangle_receipts": result_payload.get("strangle_receipts", []),
    }
    base["behavioral_mutations"] = [
        *_mutation_reports(base),
        *_recording_fixture_mutation_reports(recordings),
    ]
    return base


def _grounding_payoff_report(
    results: list[GenerationUnderAResult],
    *,
    cg3_handoff_probe: dict[str, Any],
) -> dict[str, Any]:
    disposition_payloads = [
        disposition.model_dump(mode="json")
        for result in results
        for disposition in result.grounding_dispositions
    ]
    return {
        "recording_count": len(results),
        "recorded_candidate_count": len(disposition_payloads),
        **_grounding_payoff_projection(disposition_payloads),
        "synthetic_cg3_handoff": cg3_handoff_probe,
    }


def _grounding_payoff_projection(
    dispositions: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Project full payoff evidence from canonical disposition rows."""

    counts = Counter(str(item.get("disposition") or "") for item in dispositions)
    legacy = Counter(str(item.get("legacy_exact_match") or "") for item in dispositions)
    payoff_bindings: list[dict[str, Any]] = []
    novel_routes: list[dict[str, Any]] = []
    vetoes: list[dict[str, Any]] = []
    for item in dispositions:
        chain = item.get("certificate_chain")
        chain_payload = dict(chain) if isinstance(chain, Mapping) else {}
        if (
            item.get("disposition") == "shadow_bound"
            and item.get("legacy_exact_match") == "would_reject"
        ):
            payoff_bindings.append(
                {
                    "proposal_id": item.get("proposal_id"),
                    "candidate_id": item.get("candidate_id"),
                    "selected_relation": item.get("selected_relation"),
                    "identified_atom_id": item.get("identified_atom_id"),
                    "cg1_certificate_id": chain_payload.get("cg1_certificate_id"),
                    "cg1_content_hash": chain_payload.get("cg1_content_hash"),
                    "legacy_exact_match": item.get("legacy_exact_match"),
                }
            )
        if item.get("disposition") == "novel_cg3":
            novel_routes.append(
                {
                    "proposal_id": item.get("proposal_id"),
                    "selected_relation": item.get("selected_relation"),
                    "cg2_decision": item.get("cg2_decision"),
                    "cg3_decision": item.get("cg3_decision"),
                    "cg3_reason": item.get("cg3_reason"),
                    "certificate_chain": chain_payload,
                    "bridge_missing_records": list(
                        item.get("bridge_missing_records") or []
                    ),
                }
            )
        if item.get("disposition") == "veto_false_analog":
            rejected_cause = item.get("rejected_cause")
            vetoes.append(
                {
                    "proposal_id": item.get("proposal_id"),
                    "selected_relation": item.get("selected_relation"),
                    "identified_atom_id": item.get("identified_atom_id"),
                    "rejected_cause": (
                        dict(rejected_cause)
                        if isinstance(rejected_cause, Mapping)
                        else rejected_cause
                    ),
                    "certificate_chain": chain_payload,
                }
            )
    return {
        "before_legacy_exact_match": {
            "would_bind": legacy["would_bind"],
            "would_reject": legacy["would_reject"],
        },
        "after_cgf": {
            "shadow_bound": counts["shadow_bound"],
            "novel_cg3": counts["novel_cg3"],
            "veto_false_analog": counts["veto_false_analog"],
            "abstain_or_blocked": counts["non_binding_abstain"] + counts["unknown_blocked"],
        },
        "payoff_shadow_bindings_legacy_rejected": payoff_bindings,
        "novel_routes": novel_routes,
        "recorded_vetoes": vetoes,
    }


def _recording_set_coverage(results: list[GenerationUnderAResult]) -> dict[str, Any]:
    """Project typed live results through the canonical coverage owner."""

    return _recording_set_coverage_from_payloads(
        [item.model_dump(mode="json") for item in results]
    )


def _recording_set_coverage_from_payloads(
    results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compute one full-denominator coverage projection from result payloads."""

    dispositions = tuple(
        disposition
        for result in results
        for disposition in result.get("grounding_dispositions") or []
        if isinstance(disposition, Mapping)
    )
    candidates = tuple(
        candidate
        for result in results
        for candidate in result.get("candidates") or []
        if isinstance(candidate, Mapping)
    )
    counts = Counter(str(item.get("disposition") or "") for item in dispositions)
    legacy = Counter(str(item.get("legacy_exact_match") or "") for item in dispositions)
    diversity_keys: set[tuple[str, ...]] = {
        tuple(str(part) for part in candidate.get("diversity_key") or ())
        for candidate in candidates
        if isinstance(candidate.get("diversity_key"), list | tuple)
    }


    diversity_keys.update(
        (
            str(disposition.get("proposal_id") or ""),
            str(disposition.get("disposition") or ""),
            str(disposition.get("selected_relation") or ""),
            str(
                disposition.get("identified_atom_id")
                or disposition.get("cg3_decision")
                or disposition.get("cg2_decision")
                or disposition.get("raw_candidate_hash")
                or ""
            ),
        )
        for disposition in dispositions
        if disposition.get("candidate_id") is None
    )
    has_recovered = any(
        item.get("disposition") == "shadow_bound"
        and item.get("legacy_exact_match") == "would_reject"
        for item in dispositions
    )
    has_novel = any(item.get("disposition") == "novel_cg3" for item in dispositions)
    candidate_count = len(dispositions)
    return {
        "recording_count": len(results),
        "all_recordings_generated": all(item.get("status") == "generated" for item in results),
        "candidate_count": candidate_count,
        "grounding_disposition_count": len(dispositions),
        "unique_diversity_key_count": len(diversity_keys),
        "has_legacy_rejected_shadow_binding": has_recovered,
        "has_novel_cg3_route": has_novel,
        "coverage_status": (
            "covered"
            if candidate_count >= 3 and len(diversity_keys) >= 3 and has_recovered
            else "missing_class"
        ),
        "grounding_summary": {
            "total_candidates": len(dispositions),
            "shadow_bound": counts["shadow_bound"],
            "novel_cg3": counts["novel_cg3"],
            "veto_false_analog": counts["veto_false_analog"],
            "abstain_or_blocked": counts["non_binding_abstain"] + counts["unknown_blocked"],
            "legacy_exact_match_would_bind": legacy["would_bind"],
            "legacy_exact_match_would_reject": legacy["would_reject"],
        },
    }


def _prompt_size_gate(results: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Derive a stable verdict from live prompt-size diagnostics."""

    within_limit: list[bool] = []
    measurement_consistent: list[bool] = []
    for result in results:
        config = result.get("effective_runtime_config")
        estimate = config.get("prompt_size_estimate") if isinstance(config, Mapping) else None
        consistent, derived_slice = _prompt_size_measurement(estimate)
        measurement_consistent.append(consistent)
        within_limit.append(
            derived_slice is not None and derived_slice <= _PROMPT_SLICE_LIMIT_CHARS
        )
    return {
        "schema_version": "policyos.gy.n4.prompt_size_gate.v1",
        "source_field": (
            "generation_results[].effective_runtime_config."
            "prompt_size_estimate.slice_added_chars"
        ),
        "limit_slice_added_chars": _PROMPT_SLICE_LIMIT_CHARS,
        "result_count": len(results),
        "within_limit_by_index": within_limit,
        "measurement_consistent_by_index": measurement_consistent,
        "status": (
            "pass"
            if within_limit
            and all(within_limit)
            and all(measurement_consistent)
            else "fail"
        ),
    }


def _canonical_json_bytes(value: object) -> bytes | None:
    """Return exact canonical JSON bytes, preserving JSON scalar types."""

    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None
    return payload.encode("utf-8")


def _json_exact_equal(left: object, right: object) -> bool:
    """Compare JSON values without Python's bool/int or int/float aliases."""

    left_bytes = _canonical_json_bytes(left)
    right_bytes = _canonical_json_bytes(right)
    return left_bytes is not None and right_bytes is not None and left_bytes == right_bytes


def _prompt_size_actual_frame_issue(
    *,
    design_problem: DesignProblem,
    lever_space_prompt_slice: object,
    emitted: object,
) -> dict[str, Any] | None:
    """Bind the full measurement after the owner excludes prompt-local clocks."""

    base_frame = _with_generation_cycle_revision_context(
        design_problem.to_scientist_problem_frame(),
        design_problem=design_problem,
    )
    sliced_frame = _with_lever_space_prompt_slice(
        base_frame,
        lever_space_prompt_slice=lever_space_prompt_slice,
    )

    def _frame_chars(frame: object) -> int:
        return len(_json_for_prompt_size(frame))

    without_chars = _frame_chars(base_frame)
    with_chars = _frame_chars(sliced_frame)
    slice_chars = max(0, with_chars - without_chars)
    expected = {
        "frame_without_slice_chars": without_chars,
        "frame_with_slice_chars": with_chars,
        "slice_added_chars": slice_chars,
        "frame_without_slice_estimated_tokens": (without_chars + 3) // 4,
        "frame_with_slice_estimated_tokens": (with_chars + 3) // 4,
        "slice_added_estimated_tokens": (slice_chars + 3) // 4,
    }
    if isinstance(emitted, Mapping):
        observed: object = dict(emitted)
    elif hasattr(emitted, "model_dump"):
        observed = emitted.model_dump(mode="json")
    else:
        observed = emitted
    if _json_exact_equal(observed, expected):
        return None
    return {
        "code": "prompt_size_measurement_not_actual_frames",
        "observed": observed,
        "expected": expected,
        "excluded_prompt_local_fields": ["created_at"],
    }


def _prompt_size_measurement(value: object) -> tuple[bool, int | None]:
    """Verify prompt-size arithmetic and return the derived slice length."""

    if not isinstance(value, Mapping):
        return False, None
    fields = (
        "frame_without_slice_chars",
        "frame_with_slice_chars",
        "slice_added_chars",
        "frame_without_slice_estimated_tokens",
        "frame_with_slice_estimated_tokens",
        "slice_added_estimated_tokens",
    )
    if any(
        not isinstance(value.get(field), int)
        or isinstance(value.get(field), bool)
        or int(value[field]) < 0
        for field in fields
    ):
        return False, None
    without_chars = int(value["frame_without_slice_chars"])
    with_chars = int(value["frame_with_slice_chars"])
    derived_slice = max(0, with_chars - without_chars)
    consistent = (
        int(value["slice_added_chars"]) == derived_slice
        and int(value["frame_without_slice_estimated_tokens"])
        == (without_chars + 3) // 4
        and int(value["frame_with_slice_estimated_tokens"])
        == (with_chars + 3) // 4
        and int(value["slice_added_estimated_tokens"])
        == (derived_slice + 3) // 4
    )
    return consistent, derived_slice


def _prompt_size_projection_issues(
    payload: Mapping[str, Any],
    results: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Verify live measurements or their byte-stable frozen verdict."""

    issues: list[dict[str, Any]] = []
    if not _json_exact_equal(
        payload.get("diagnostic_projection"),
        _FROZEN_DIAGNOSTIC_PROJECTION,
    ):
        issues.append({"code": "frozen_diagnostic_projection_drift"})
    gate = payload.get("prompt_size_gate")
    if not isinstance(gate, Mapping):
        return [*issues, {"code": "prompt_size_gate_missing"}]
    presence: list[bool] = []
    for result in results:
        config = result.get("effective_runtime_config")
        presence.append(
            isinstance(config, Mapping) and "prompt_size_estimate" in config
        )
    if presence and all(presence):
        expected = _prompt_size_gate(results)
        if not _json_exact_equal(dict(gate), expected):
            issues.append(
                {
                    "code": "prompt_size_gate_drift",
                    "recorded": dict(gate),
                    "expected": expected,
                }
            )
    elif presence and not any(presence):
        expected_frozen = {
            "schema_version": "policyos.gy.n4.prompt_size_gate.v1",
            "source_field": (
                "generation_results[].effective_runtime_config."
                "prompt_size_estimate.slice_added_chars"
            ),
            "limit_slice_added_chars": _PROMPT_SLICE_LIMIT_CHARS,
            "result_count": len(results),
            "within_limit_by_index": [True] * len(results),
            "measurement_consistent_by_index": [True] * len(results),
            "status": "pass",
        }
        if not _json_exact_equal(dict(gate), expected_frozen):
            issues.append(
                {
                    "code": "prompt_size_gate_frozen_drift",
                    "recorded": dict(gate),
                    "expected": expected_frozen,
                }
            )
    else:
        issues.append({"code": "prompt_size_measurement_partial_denominator"})
    consistency = gate.get("measurement_consistent_by_index")
    if not isinstance(consistency, list) or not consistency or not all(consistency):
        issues.append({"code": "prompt_size_measurement_inconsistent"})
    if gate.get("status") != "pass":
        issues.append({"code": "prompt_size_gate_not_pass"})
    return issues


def _synthetic_cg3_handoff_probe(repo_root: Path, recording: dict[str, Any]) -> dict[str, Any]:
    """Run a labeled near-miss addition through the N4 CGF handoff path."""

    problem = _design_problem(recording)
    intervention = InterventionSpec(
        intervention_id="synthetic_false_analog_household_transfer_tax_credit",
        kind="household_transfer",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={
            "rate": Decimal("0.08"),
        },
        notes=[
            (
                "Synthetic false-analog probe: household tax credit-like transfer near "
                "fiscal relief text; not a recorded model output."
            )
        ],
    )
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_synthetic_false_analog",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="policy_synthetic_false_analog",
            problem_frame_ref="sha256:" + "a" * 64,
            interventions=[intervention],
        ),
        model_spec=ModelSpec(
            model_id="model_synthetic_false_analog",
            data_snapshot_ref="sha256:" + "b" * 64,
        ),
    )
    candidates, dispositions = _content_bound_candidates(
        design_problem=problem,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        bundle=bundle,
        model_id=str(recording["model_id"]),
        draft_path="model_generated",
        formalizer_path="model_generated",
        critic_path="model_generated",
        critique_verdict="synthetic_probe",
        calls=(),
        repo_root=repo_root,
        world_model_record_ref=None,
        reference=None,
    )
    summary = _grounding_disposition_summary(dispositions)
    return {
        "recording_source": "synthetic_addition_not_model_recording",
        "expected_mapping": "proposal_level_novel_candidate_with_false_analog_evidence_routes_to_cg3",
        "candidate_count": len(candidates),
        "summary": summary.model_dump(mode="json"),
        "dispositions": [item.model_dump(mode="json") for item in dispositions],
    }


def _synthetic_cg3_handoff_probe_passed(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("recording_source") != "synthetic_addition_not_model_recording":
        return False
    if (
        value.get("expected_mapping")
        != "proposal_level_novel_candidate_with_false_analog_evidence_routes_to_cg3"
    ):
        return False
    summary = value.get("summary")
    if not isinstance(summary, dict) or int(summary.get("novel_cg3") or 0) < 1:
        return False
    dispositions = value.get("dispositions")
    if not isinstance(dispositions, list):
        return False
    return any(
        isinstance(item, dict)
        and item.get("disposition") == "novel_cg3"
        and item.get("selected_relation") == "novel-candidate"
        and isinstance(item.get("rejected_cause"), dict)
        and item["rejected_cause"].get("cg3_decision")
        for item in dispositions
    )


_ADAPTER_FORBIDDEN_AUTHORED_AXES = frozenset(
    {
        "sign",
        "outcome",
        "scope",
        "population",
        "estimand",
        "unit",
        "time",
        "wm_version",
        "effect_path",
        "modal_claims",
    }
)


def _adapter_honesty_probe(recording: dict[str, Any]) -> dict[str, Any]:
    """Construct the audit counter-case and observe the real N4 adapter output."""

    problem = _design_problem(recording)
    intervention = InterventionSpec(
        intervention_id="adapter_honesty_procurement_counter_case",
        kind="procurement_shock_intensity",
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={
            "intensity": Decimal("0.35"),
            "target_world_slot": "government.procurement_queue",
        },
        notes=[
            "Audit counter-case: candidate asserts only operator, slot, and direct param."
        ],
    )
    proposal = _grounding_proposal_for_intervention(
        intervention,
        design_problem=problem,
        bundle_ref="sha256:" + "0" * 64,
    )
    signature = _json_safe_dict(proposal.get("signature") or {})
    forbidden_present = sorted(
        key for key in _ADAPTER_FORBIDDEN_AUTHORED_AXES if key in signature
    )
    return {
        "probe_id": "adapter_map_and_omit_procurement_counter_case",
        "adapter_authority": "map_and_omit",
        "candidate_asserted_fields": ["kind", "target_world_slot", "intensity"],
        "emitted_signature": signature,
        "forbidden_axis_fields_present": forbidden_present,
        "expected_forbidden_axis_fields_present": [],
    }


def _adapter_honesty_payload_issues(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    probe = payload.get("adapter_honesty_probe")
    if not isinstance(probe, Mapping):
        return [{"code": "adapter_honesty_probe_missing"}]
    issues: list[dict[str, Any]] = []
    signature = probe.get("emitted_signature")
    if not isinstance(signature, Mapping):
        issues.append({"code": "adapter_honesty_signature_missing"})
        signature = {}
    authored_axes = sorted(
        key for key in _ADAPTER_FORBIDDEN_AUTHORED_AXES if key in signature
    )
    recorded_present = probe.get("forbidden_axis_fields_present")
    if authored_axes or recorded_present not in ([], ()):
        issues.append(
            {
                "code": "adapter_authored_semantic_axis",
                "axes": authored_axes or recorded_present,
            }
        )
    if signature.get("op") != "procurement_shock_intensity":
        issues.append({"code": "adapter_honesty_operator_not_pass_through"})
    if signature.get("target") != ["government.procurement_queue"]:
        issues.append({"code": "adapter_honesty_target_not_candidate_owned"})
    direct = signature.get("x_do")
    if not isinstance(direct, Mapping) or sorted(direct.keys()) != ["intensity"]:
        issues.append({"code": "adapter_honesty_direct_params_not_map_and_omit"})
    return issues


def _disposition_certificate_verdict_issues(
    disposition: GroundingDispositionRecord,
) -> list[dict[str, Any]]:
    selected_relation = disposition.selected_relation
    actual = disposition.disposition
    expected: str
    if selected_relation in {"exact", "certified-specialization"}:
        if actual == "unknown_blocked":
            cause = disposition.rejected_cause
            if isinstance(cause, Mapping) and cause.get("code") == "shadow_atom_binding_failed":
                return []
        expected = "shadow_bound"
    elif selected_relation == "false-analog":
        expected = "veto_false_analog"
    elif selected_relation == "novel-candidate":
        expected = "novel_cg3"
    elif selected_relation in {"unknown", "blocked"}:
        expected = "unknown_blocked"
    else:
        expected = "non_binding_abstain"
    if actual == expected:
        return []
    return [
        {
            "code": "grounding_disposition_diverges_from_cg1_verdict",
            "proposal_id": disposition.proposal_id,
            "selected_relation": selected_relation,
            "expected_disposition": expected,
            "actual_disposition": actual,
        }
    ]


def _recording_set_gate_matches_mapping_fix(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required = value.get("required_live_classes")
    if required != [
        "at_least_3_diverse_real_candidates",
        "at_least_1_legacy_rejected_shadow_bound_recovery",
    ]:
        return False
    if (
        value.get("novel_cg3_live_requirement")
        != "desirable_recorded_not_required_after_mapping_second_guess_fix"
    ):
        return False
    return value.get("deterministic_cg3_handoff_probe") == "required"


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate one contract payload, including behavioral firewall properties."""

    issues: list[dict[str, Any]] = []
    if "generation_result" in payload:
        issues.append({"code": "legacy_singular_generation_result_present"})
    if payload.get("schema_version") != DESIGN_GENERATION_CONTRACT_SCHEMA_VERSION:
        issues.append({"code": "design_generation_contract_schema_mismatch"})
    result_payloads = payload.get("generation_results")
    if not isinstance(result_payloads, list):
        result_payload = payload.get("generation_result")
        result_payloads = [result_payload] if isinstance(result_payload, dict) else []
    if not result_payloads:
        issues.append({"code": "design_generation_result_missing"})
    raw_result_payloads = [
        item for item in result_payloads if isinstance(item, Mapping)
    ]
    issues.extend(_prompt_size_projection_issues(payload, raw_result_payloads))
    results: list[GenerationUnderAResult] = []
    for index, result_payload in enumerate(result_payloads):
        if not isinstance(result_payload, dict):
            issues.append({"code": "generation_result_invalid", "index": index})
            continue
        issues.extend(_raw_generation_payload_issues(result_payload))
        try:
            result = GenerationUnderAResult.model_validate(result_payload)
        except ValueError as exc:
            issues.append(
                {"code": "generation_result_invalid", "index": index, "error": str(exc)}
            )
            continue
        results.append(result)
        issues.extend(firewall_issues_for_result(result))
        issues.extend(validate_design_generation_strangle_receipts(Path.cwd()))
        if result.status != "generated":
            issues.append({"code": "positive_generation_not_generated", "index": index})
        if result.lever_space_prompt_slice.status != "derived":
            issues.append({"code": "lever_space_prompt_slice_not_derived", "index": index})
        if not result.lever_space_prompt_slice.content_hash:
            issues.append({"code": "lever_space_prompt_slice_hash_missing", "index": index})
        if not result.lever_space_prompt_slice.non_constraining:
            issues.append(
                {"code": "lever_space_prompt_slice_not_non_constraining", "index": index}
            )
        for disposition in result.grounding_dispositions:
            issues.extend(_disposition_certificate_verdict_issues(disposition))
            chain = disposition.certificate_chain
            if not chain.cg1_certificate_id or not chain.cg1_content_hash:
                issues.append(
                    {
                        "code": "grounding_relation_certificate_chain_missing",
                        "proposal_id": disposition.proposal_id,
                    }
                )
            if disposition.disposition == "shadow_bound" and (
                not disposition.candidate_id
                or disposition.selected_relation not in {"exact", "certified-specialization"}
            ):
                issues.append(
                    {
                        "code": "shadow_binding_without_identifying_certificate",
                        "proposal_id": disposition.proposal_id,
                    }
                )
    if results:
        coverage = _recording_set_coverage(results)
        if coverage["candidate_count"] < 3:
            issues.append({"code": "positive_grounding_denominator_missing"})
        if coverage["unique_diversity_key_count"] < 3:
            issues.append({"code": "positive_generation_diversity_missing"})
        if not coverage["has_legacy_rejected_shadow_binding"]:
            issues.append({"code": "legacy_rejected_candidate_not_recovered_by_cgf"})
        recorded_coverage = payload.get("recording_set_coverage")
        if isinstance(recorded_coverage, dict) and recorded_coverage != coverage:
            issues.append({"code": "recording_set_coverage_drift"})
        elif not isinstance(recorded_coverage, dict):
            issues.append({"code": "recording_set_coverage_missing"})
    issues.extend(_adapter_honesty_payload_issues(payload))
    denominator = payload.get("not_certificate_denominator")
    if denominator != list(NOT_CERTIFICATE_KINDS):
        issues.append({"code": "not_certificate_denominator_drift"})
    if payload.get("source_flip_mutation_harness") != {
        "mode": "--source-flip-mutations",
        "mutation_ids": list(N4_SOURCE_FLIP_MUTATION_IDS),
        "property": "patch_source_then_causal_red_then_restore_exact_bytes",
    }:
        issues.append({"code": "source_flip_mutation_denominator_drift"})
    payoff = payload.get("grounding_payoff")
    if not isinstance(payoff, dict):
        issues.append({"code": "grounding_payoff_missing"})
    else:
        if not payoff.get("payoff_shadow_bindings_legacy_rejected"):
            issues.append({"code": "grounding_payoff_shadow_binding_missing"})
        synthetic = payoff.get("synthetic_cg3_handoff")
        if not _synthetic_cg3_handoff_probe_passed(synthetic):
            issues.append({"code": "synthetic_cg3_handoff_missing"})
    gate = payload.get("recording_set_gate")
    if not _recording_set_gate_matches_mapping_fix(gate):
        issues.append({"code": "recording_set_gate_not_aligned_with_mapping_fix"})
    integrity = payload.get("recording_fixture_integrity")
    if not isinstance(integrity, dict):
        issues.append({"code": "recording_fixture_integrity_missing"})
    else:
        if integrity.get("status") != "pass":
            issues.append({"code": "recording_fixture_integrity_not_pass"})
        if integrity.get("raw_response_hash_gate") != "required_recomputed_before_replay":
            issues.append({"code": "recording_fixture_raw_response_hash_gate_missing"})
        if integrity.get("prompt_hash_role") != "recorded_provenance_only":
            issues.append({"code": "recording_fixture_prompt_hash_not_provenance_only"})
    replay = payload.get("replay_fixture_versioning")
    if not isinstance(replay, dict):
        issues.append({"code": "replay_fixture_versioning_note_missing"})
    else:
        if (
            replay.get("follow_up")
            != "GY_N4_REPLAY_FIXTURE_VERSIONING_AND_CG_CONTRACT_DECOUPLING"
            or replay.get("status") != "closed"
        ):
            issues.append({"code": "replay_fixture_versioning_followup_not_closed"})
        if replay.get("replay_gate") != "raw_response_hash":
            issues.append({"code": "replay_fixture_versioning_gate_not_raw_response_hash"})
        if replay.get("prompt_hash_role") != "recorded_provenance_only":
            issues.append({"code": "replay_fixture_versioning_prompt_hash_not_provenance"})
    variation = payload.get("problem_variation_probe")
    if not isinstance(variation, dict):
        issues.append({"code": "problem_variation_probe_missing"})
    elif variation.get("status") != "not_run":
        if variation.get("status") != "pass":
            issues.append({"code": "problem_variation_invariant_candidates"})
        if variation.get("authored_fixed_set_detected"):
            issues.append({"code": "authored_fixed_replay_detected"})
        for case in variation.get("cases") or []:
            if not isinstance(case, dict):
                continue
            if case.get("status") != "generated":
                issues.append({"code": "problem_variation_generation_failed"})
            disposition_count = case.get("grounding_disposition_count")
            if not isinstance(disposition_count, int) or disposition_count < 3:
                issues.append({"code": "problem_variation_disposition_denominator_missing"})
            prompt_hashes = case.get("prompt_hashes")
            if not isinstance(prompt_hashes, list) or not prompt_hashes:
                issues.append({"code": "problem_variation_prompt_hashes_missing"})
            generator_paths = case.get("generator_paths")
            if (
                not isinstance(generator_paths, list)
                or any(item != "model_generated" for item in generator_paths)
            ):
                issues.append({"code": "problem_variation_generator_path_not_real"})
    positive = payload.get("positive_gate")
    if not isinstance(positive, dict):
        issues.append({"code": "positive_gate_missing"})
    else:
        grounding_summary = positive.get("grounding_summary")
        if not isinstance(grounding_summary, dict):
            issues.append({"code": "positive_grounding_summary_missing"})
        elif int(grounding_summary.get("total_candidates") or 0) < 3:
            issues.append({"code": "positive_grounding_summary_denominator_missing"})
        slice_hashes = positive.get("lever_space_prompt_slice_hashes")
        if (
            not isinstance(slice_hashes, list)
            or not slice_hashes
            or any(not item for item in slice_hashes)
        ):
            issues.append({"code": "positive_gate_slice_hash_missing"})
        positive_paths = positive.get("generator_paths")
        if (
            not isinstance(positive_paths, list)
            or len(positive_paths) < 1
            or any(item != "model_generated" for item in positive_paths)
        ):
            issues.append({"code": "positive_generator_paths_not_real"})
        positive_statuses = positive.get("candidate_statuses")
        if (
            not isinstance(positive_statuses, list)
            or len(positive_statuses) < 1
            or any(item != "candidate_unverified" for item in positive_statuses)
        ):
            issues.append({"code": "positive_candidates_not_shadow"})
    receipt_issues = payload.get("strangle_receipts")
    if not isinstance(receipt_issues, list) or any(
        not isinstance(item, dict) or item.get("status") != "strangled"
        for item in receipt_issues
    ):
        issues.append({"code": "strangle_receipts_not_recomputed_strangled"})
    mutation_statuses = {
        item.get("mutation_id"): item.get("status")
        for item in payload.get("behavioral_mutations", [])
        if isinstance(item, dict)
    }
    if mutation_statuses.get("recorded_raw_response_hash_mismatch") != "red":
        issues.append({"code": "recorded_raw_response_hash_mutation_not_red"})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def validate(repo_root: Path) -> dict[str, Any]:
    """Validate the frozen real-output payoff receipt without live re-derivation."""

    path = repo_root / OUTPUT_PATH
    issues: list[dict[str, Any]] = []
    recordings: list[dict[str, Any]] = []
    try:
        recordings = _load_recordings(repo_root)
    except RuntimeError as exc:
        issues.append({"code": "recording_fixture_integrity_failed", "error": str(exc)})
        issues.append(
            {
                "code": "current_wmr_reissue_receipt_verification_blocked",
                "reason": "recording_fixture_denominator_invalid",
            }
        )
    if not path.is_file():
        issues.append({"code": "design_generation_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "design_generation_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None:
        committed_report = validate_payload(committed)
        issues.extend(committed_report["issues"])
        issues.extend(_frozen_payoff_receipt_issues(committed))
        if recordings:
            issues.extend(_recording_fixture_artifact_issues(committed, recordings, repo_root))
            mutation_reports = [
                *_mutation_reports(committed),
                *_recording_fixture_mutation_reports(recordings),
            ]
        else:
            mutation_reports = _mutation_reports(committed)
        mutation_failures = [
            item
            for item in mutation_reports
            if not isinstance(item, dict) or item.get("status") != "red"
        ]
        if mutation_failures:
            issues.append(
                {
                    "code": "behavioral_mutation_not_red",
                    "mutations": mutation_failures,
                }
            )
        stored_mutation_statuses = {
            item.get("mutation_id"): item.get("status")
            for item in committed.get("behavioral_mutations", [])
            if isinstance(item, dict)
        }
        for mutation in (
            "recorded_raw_response_hash_mismatch",
            "exact_match_restored_rejects_cgf_payoff",
            "adapter_authored_axis_injected",
            "normalization_warrant_dropped",
            "disposition_diverges_from_certificate_verdict",
        ):
            if stored_mutation_statuses.get(mutation) != "red":
                issues.append(
                    {"code": "stored_behavioral_mutation_not_red", "mutation_id": mutation}
                )
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
    }


def validate_rederive_audit(repo_root: Path) -> dict[str, Any]:
    """Run the optional live replay audit; routine --check does not call this."""

    live = build_live_payload(repo_root)
    report = validate_payload(live)
    mutation_failures = [
        item
        for item in live.get("behavioral_mutations", [])
        if not isinstance(item, dict) or item.get("status") != "red"
    ]
    issues = list(report["issues"])
    path = repo_root / OUTPUT_PATH
    if not path.is_file():
        issues.append({"code": "design_generation_contract_missing", "path": OUTPUT_PATH})
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                {
                    "code": "design_generation_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
        else:
            committed_report = validate_payload(dict(committed))
            issues.extend(committed_report["issues"])
            issues.extend(_frozen_payoff_receipt_issues(dict(committed)))
            issues.extend(_frozen_payoff_live_receipt_issues(committed, live))
            if report["status"] == "pass":
                expected_artifact = _build_frozen_artifact_payload(live)
                if not _json_exact_equal(committed, expected_artifact):
                    differing_keys = sorted(
                        key
                        for key in set(committed).union(expected_artifact)
                        if committed.get(key) != expected_artifact.get(key)
                    )
                    issues.append(
                        {
                            "code": "frozen_artifact_live_drift",
                            "differing_top_level_keys": differing_keys,
                        }
                    )
    if mutation_failures:
        issues.append(
            {
                "code": "behavioral_mutation_not_red",
                "mutations": mutation_failures,
            }
        )
    generation_terminal_evidence = [
        {
            "index": index,
            "status": result.get("status"),
            "degraded_reasons": [
                item.get("reason")
                for item in result.get("degraded_artifacts", [])
                if isinstance(item, Mapping) and item.get("reason")
            ],
        }
        for index, result in enumerate(live.get("generation_results", []))
        if isinstance(result, Mapping)
    ]
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "generation_terminal_evidence": generation_terminal_evidence,
    }


def _recording_fixture_artifact_issues(
    payload: dict[str, Any],
    recordings: list[dict[str, Any]],
    repo_root: Path,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_fixture_hash = _fixture_hash(repo_root)
    if payload.get("recording_fixture_hash") != expected_fixture_hash:
        issues.append(
            {
                "code": "recording_fixture_hash_drift",
                "recorded": payload.get("recording_fixture_hash"),
                "computed": expected_fixture_hash,
            }
        )
    expected_integrity = _recording_fixture_integrity_report(recordings)
    recorded_integrity = payload.get("recording_fixture_integrity")
    if not isinstance(recorded_integrity, dict):
        issues.append({"code": "recording_fixture_integrity_missing"})
    elif recorded_integrity != expected_integrity:
        issues.append(
            {
                "code": "recording_fixture_integrity_drift",
                "recorded": recorded_integrity,
                "computed": expected_integrity,
            }
        )
    try:
        owner_projection = _resolve_current_wmr_owner_projection(repo_root)
    except (OSError, RuntimeError, ValueError) as exc:
        issues.append(
            {
                "code": "current_wmr_reissue_owner_resolution_failed",
                "error": str(exc),
            }
        )
    else:
        issues.extend(
            _current_wmr_reissue_receipt_issues(
                payload,
                recordings,
                owner_projection=owner_projection,
            )
        )
    return issues


def _frozen_payoff_receipt_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    receipt = payload.get("frozen_payoff_receipt")
    if not isinstance(receipt, dict):
        issues.append({"code": "frozen_payoff_receipt_missing"})
    else:
        if receipt.get("mode") != "frozen_real_output_payoff_receipt":
            issues.append({"code": "frozen_payoff_receipt_mode_drift"})
        if (
            receipt.get("follow_up")
            != "GY_N4_REPLAY_FIXTURE_VERSIONING_AND_CG_CONTRACT_DECOUPLING"
            or receipt.get("status") != "closed"
        ):
            issues.append({"code": "frozen_payoff_followup_not_closed"})
        if receipt.get("routine_check_mode") != "verify_frozen_receipt_without_live_rederive":
            issues.append({"code": "frozen_payoff_receipt_check_mode_drift"})
        if receipt.get("live_grounding_guarantee") != (
            "test_cgf_binding_recovers_legacy_exact_match_rejection plus "
            "recomputing CG0-CG6 contracts"
        ):
            issues.append({"code": "frozen_payoff_receipt_live_guarantee_drift"})
        expected_hash = _frozen_receipt_hash(payload)
        if receipt.get("content_hash") != expected_hash:
            issues.append(
                {
                    "code": "frozen_payoff_receipt_hash_drift",
                    "recorded": receipt.get("content_hash"),
                    "computed": expected_hash,
                }
            )

    coverage = payload.get("recording_set_coverage")
    if not isinstance(coverage, dict):
        issues.append({"code": "recording_set_coverage_missing"})
        coverage = {}
    expected_coverage = _recomputed_frozen_coverage(payload)
    summary = coverage.get("grounding_summary")
    expected_summary = expected_coverage["grounding_summary"]
    if coverage.get("coverage_status") != "covered":
        issues.append({"code": "frozen_receipt_coverage_not_covered"})
    if int(coverage.get("candidate_count") or 0) < 3:
        issues.append({"code": "frozen_receipt_candidate_denominator_missing"})
    if int(coverage.get("unique_diversity_key_count") or 0) < 3:
        issues.append({"code": "frozen_receipt_diversity_missing"})
    if coverage.get("has_legacy_rejected_shadow_binding") is not True:
        issues.append({"code": "frozen_receipt_shadow_recovery_missing"})
    if summary != expected_summary:
        issues.append(
            {
                "code": "frozen_receipt_payoff_summary_drift",
                "recorded": summary,
                "expected": expected_summary,
            }
        )
    coverage_projection = {key: value for key, value in coverage.items() if key != "grounding_summary"}
    expected_coverage_projection = {
        key: value for key, value in expected_coverage.items() if key != "grounding_summary"
    }
    if coverage_projection != expected_coverage_projection:
        issues.append(
            {
                "code": "frozen_receipt_coverage_drift",
                "recorded": coverage_projection,
                "expected": expected_coverage_projection,
            }
        )
    for index, result in enumerate(_mutable_generation_results(payload)):
        dispositions = [
            item
            for item in result.get("grounding_dispositions") or []
            if isinstance(item, dict)
        ]
        diversity = result.get("diversity_report")
        grounding_summary = result.get("grounding_disposition_summary")
        if not isinstance(diversity, dict) or not isinstance(grounding_summary, dict):
            issues.append(
                {
                    "code": "frozen_receipt_producer_denominator_missing",
                    "index": index,
                }
            )
            continue
        owner_count = diversity.get("candidate_count")
        summary_count = grounding_summary.get("total_candidates")
        if owner_count != len(dispositions) or summary_count != len(dispositions):
            issues.append(
                {
                    "code": "producer_candidate_denominator_drift",
                    "index": index,
                    "owner_candidate_count": owner_count,
                    "grounding_summary_count": summary_count,
                    "disposition_count": len(dispositions),
                }
            )
    positive = payload.get("positive_gate")
    if not isinstance(positive, dict):
        issues.append({"code": "frozen_receipt_positive_gate_missing"})
    elif (
        positive.get("candidate_count") != expected_coverage["candidate_count"]
        or positive.get("grounding_disposition_count")
        != expected_coverage["grounding_disposition_count"]
        or positive.get("grounding_summary") != expected_summary
        or positive.get("unique_diversity_key_count")
        != expected_coverage["unique_diversity_key_count"]
    ):
        issues.append({"code": "frozen_receipt_positive_denominator_drift"})

    disposition_rows = _frozen_disposition_rows(payload)
    expected_payoff = _grounding_payoff_projection(disposition_rows)
    payoff = payload.get("grounding_payoff")
    if not isinstance(payoff, dict):
        issues.append({"code": "grounding_payoff_missing"})
        payoff = {}
    expected_payoff_keys = {
        "recording_count",
        "recorded_candidate_count",
        "synthetic_cg3_handoff",
        *expected_payoff,
    }
    if set(payoff) != expected_payoff_keys:
        issues.append(
            {
                "code": "frozen_receipt_payoff_envelope_drift",
                "recorded": sorted(payoff),
                "expected": sorted(expected_payoff_keys),
            }
        )
    if payoff.get("recording_count") != expected_coverage["recording_count"]:
        issues.append({"code": "frozen_receipt_payoff_recording_denominator_drift"})
    if payoff.get("recorded_candidate_count") != expected_coverage["candidate_count"]:
        issues.append({"code": "frozen_receipt_payoff_candidate_denominator_drift"})
    expected_before = expected_payoff["before_legacy_exact_match"]
    if payoff.get("before_legacy_exact_match") != expected_before:
        issues.append({"code": "frozen_receipt_before_table_drift"})
    expected_after = expected_payoff["after_cgf"]
    if payoff.get("after_cgf") != expected_after:
        issues.append({"code": "frozen_receipt_after_table_drift"})
    shadow_payoff = payoff.get("payoff_shadow_bindings_legacy_rejected")
    if shadow_payoff != expected_payoff["payoff_shadow_bindings_legacy_rejected"]:
        issues.append({"code": "frozen_receipt_shadow_binding_payoff_drift"})
    novel_routes = payoff.get("novel_routes")
    if novel_routes != expected_payoff["novel_routes"]:
        issues.append({"code": "frozen_receipt_novel_route_payoff_drift"})
    vetoes = payoff.get("recorded_vetoes")
    if vetoes != expected_payoff["recorded_vetoes"]:
        issues.append({"code": "frozen_receipt_veto_payoff_drift"})
    if payoff.get("synthetic_cg3_handoff") != payload.get("synthetic_cg3_handoff_probe"):
        issues.append({"code": "frozen_receipt_synthetic_cg3_projection_drift"})

    if len(disposition_rows) != expected_coverage["candidate_count"]:
        issues.append({"code": "frozen_receipt_disposition_denominator_drift"})
    novel_dispositions = [
        item for item in disposition_rows if item.get("selected_relation") == "novel-candidate"
    ]
    if len(novel_dispositions) != expected_summary["novel_cg3"] or any(
        item.get("disposition") != "novel_cg3" for item in novel_dispositions
    ):
        issues.append({"code": "frozen_receipt_novel_disposition_drift"})
    for disposition in disposition_rows:
        chain = disposition.get("certificate_chain")
        if not isinstance(chain, dict):
            issues.append(
                {
                    "code": "frozen_receipt_certificate_chain_missing",
                    "proposal_id": disposition.get("proposal_id"),
                }
            )
            continue
        for key in (
            "cg1_certificate_id",
            "cg1_content_hash",
            "cg2_certificate_id",
            "cg2_content_hash",
            "cg3_certificate_id",
            "cg3_content_hash",
        ):
            if not chain.get(key):
                issues.append(
                    {
                        "code": "frozen_receipt_certificate_ref_missing",
                        "proposal_id": disposition.get("proposal_id"),
                        "field": key,
                    }
                )
        if disposition.get("disposition") == "shadow_bound" and (
            not disposition.get("candidate_id")
            or disposition.get("selected_relation") not in {"exact", "certified-specialization"}
        ):
            issues.append(
                {
                    "code": "frozen_receipt_shadow_binding_identity_missing",
                    "proposal_id": disposition.get("proposal_id"),
                }
            )
    return issues


def _recomputed_frozen_coverage(payload: dict[str, Any]) -> dict[str, Any]:
    """Recompute the frozen receipt's complete disposition denominator."""

    return _recording_set_coverage_from_payloads(_mutable_generation_results(payload))


def _frozen_disposition_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in _mutable_generation_results(payload):
        rows.extend(
            item for item in result.get("grounding_dispositions") or [] if isinstance(item, dict)
        )
    return rows


def _frozen_receipt_projection(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "recording_fixture_hash": payload.get("recording_fixture_hash"),
        "current_wmr_reissue_receipt": payload.get("current_wmr_reissue_receipt"),
        "generation_results": payload.get("generation_results"),
        "diagnostic_projection": payload.get("diagnostic_projection"),
        "prompt_size_gate": payload.get("prompt_size_gate"),
        "recording_set_coverage": payload.get("recording_set_coverage"),
        "grounding_payoff": payload.get("grounding_payoff"),
        "positive_gate": payload.get("positive_gate"),
        "recording_set_gate": payload.get("recording_set_gate"),
        "problem_variation_probe": payload.get("problem_variation_probe"),
        "synthetic_cg3_handoff_probe": payload.get("synthetic_cg3_handoff_probe"),
    }


def _frozen_receipt_hash(payload: dict[str, Any]) -> str:
    return _stable_json_hash(_drift_stable_payload(_frozen_receipt_projection(payload)))


def _build_frozen_payoff_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the content-bound routine-verification receipt for one live payload."""

    return {
        "content_hash": _frozen_receipt_hash(payload),
        "follow_up": "GY_N4_REPLAY_FIXTURE_VERSIONING_AND_CG_CONTRACT_DECOUPLING",
        "live_grounding_guarantee": (
            "test_cgf_binding_recovers_legacy_exact_match_rejection plus "
            "recomputing CG0-CG6 contracts"
        ),
        "mode": "frozen_real_output_payoff_receipt",
        "routine_check_mode": "verify_frozen_receipt_without_live_rederive",
        "status": "closed",
    }


def _frozen_payoff_live_receipt_issues(
    committed: Mapping[str, Any],
    live: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compare current live semantics with the committed frozen receipt."""

    receipt = committed.get("frozen_payoff_receipt")
    if not isinstance(receipt, Mapping):
        return [{"code": "frozen_payoff_receipt_missing"}]
    recorded = receipt.get("content_hash")
    committed_computed = _frozen_receipt_hash(dict(committed))
    live_computed = _frozen_receipt_hash(dict(live))
    issues: list[dict[str, Any]] = []
    if "generation_result" in committed:
        issues.append({"code": "legacy_singular_generation_result_present"})
    if recorded != committed_computed:
        issues.append(
            {
                "code": "frozen_payoff_receipt_hash_drift",
                "recorded": recorded,
                "computed": committed_computed,
            }
        )
    if recorded != live_computed:
        issues.append(
            {
                "code": "frozen_payoff_live_receipt_drift",
                "recorded": recorded,
                "computed": live_computed,
            }
        )
    return issues


def write(repo_root: Path) -> None:
    """Write the live GY-N4 design-generation contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_frozen_artifact_payload(build_live_payload(repo_root))
    if not isinstance(payload, dict):  # pragma: no cover - build_live_payload is typed.
        raise RuntimeError("gy_n4_artifact_payload_invalid")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_frozen_artifact_payload(live: Mapping[str, Any]) -> dict[str, Any]:
    """Project one live run into the exact byte-stable committed payload."""

    raw_results = live.get("generation_results")
    if (
        not isinstance(raw_results, list)
        or not raw_results
        or any(not isinstance(item, Mapping) for item in raw_results)
    ):
        raise RuntimeError("gy_n4_generation_result_denominator_invalid")
    live_results = list(raw_results)
    if not live_results or any(
        not isinstance(result.get("effective_runtime_config"), Mapping)
        or "prompt_size_estimate" not in result["effective_runtime_config"]
        for result in live_results
    ):
        raise RuntimeError("gy_n4_prompt_size_live_measurement_missing")
    prompt_issues = _prompt_size_projection_issues(live, live_results)
    if prompt_issues:
        codes = ",".join(str(item.get("code")) for item in prompt_issues)
        raise RuntimeError(f"gy_n4_prompt_size_projection_invalid:{codes}")
    payload = _artifact_stable_payload(dict(live))
    if not isinstance(payload, dict):  # pragma: no cover - input is a mapping.
        raise RuntimeError("gy_n4_artifact_payload_invalid")
    payload.pop("frozen_payoff_receipt", None)
    payload["frozen_payoff_receipt"] = _build_frozen_payoff_receipt(payload)
    return payload


def _artifact_stable_payload(value: Any) -> Any:
    """Remove replay-local elapsed measurements from committed artifact bytes."""

    normalized = copy.deepcopy(value)
    if not isinstance(normalized, dict):
        return normalized
    normalized.pop("wall_time_seconds", None)
    for result in normalized.get("generation_results") or []:
        if not isinstance(result, dict):
            continue
        config = result.get("effective_runtime_config")
        if isinstance(config, dict):
            config.pop("cg1_index_prewarm_wall_seconds", None)
            config.pop("prompt_size_estimate", None)
        for call in result.get("llm_calls") or []:
            if isinstance(call, dict):
                call.pop("wall_seconds", None)
    return normalized


def _drift_stable_payload(value: Any) -> Any:
    """Normalize replay-local timing measurements before artifact drift comparison."""

    return _artifact_stable_payload(value)


def _mutation_reports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    mutations = {
        "degraded_mock_fallback_candidate_counted_real": _mutate_degraded_candidate,
        "not_certificate_reaches_authority": _mutate_not_certificate_authority,
        "surrogate_below_certified_mints_promotion": _mutate_surrogate_promotion,
        "unsupported_model_not_rejected": _mutate_unsupported_model,
        "candidate_without_content_bound_n2_atom": _mutate_atom_content_hash,
        "pending_world_model_record_ref_admitted": _mutate_pending_wmr_ref,
        "exact_match_restored_rejects_cgf_payoff": _mutate_restore_exact_match_authority,
        "binding_without_grounding_relation_certificate": _mutate_binding_without_certificate,
        "surrogate_score_mints_grounding_binding": _mutate_surrogate_grounding_binding,
        "lever_space_slice_hash_dropped": _mutate_drop_slice_hash,
        "adapter_authored_axis_injected": _mutate_adapter_authored_axis,
        "normalization_warrant_dropped": _mutate_normalization_warrant_dropped,
        "effective_runtime_config_regressed": _mutate_effective_runtime_config,
        "disposition_diverges_from_certificate_verdict": (
            _mutate_disposition_diverges_from_certificate_verdict
        ),
        "grounding_disposition_count_drift": _mutate_grounding_disposition_count,
        "producer_candidate_denominator_drift": _mutate_producer_candidate_denominator,
        "prompt_size_gate_drift": _mutate_prompt_size_gate,
        "grounding_certificate_chain_drift": _mutate_grounding_certificate_chain,
        "domain_mechanism_hardcode": _mutate_domain_hardcode,
        "recorded_replay_collapses_to_authored_fixed_set": _mutate_authored_replay_collapse,
        "problem_variation_candidates_invariant": _mutate_problem_variation_invariant,
    }
    reports: list[dict[str, Any]] = []
    for mutation_id, mutator in mutations.items():
        mutated = copy.deepcopy(payload)
        try:
            mutator(mutated)
            report = validate_payload(mutated)
        except RuntimeError as exc:
            reports.append(
                {
                    "mutation_id": mutation_id,
                    "status": "red",
                    "issue_codes": [str(exc).split(":", 1)[0]],
                    "mutation_harness_error": str(exc),
                }
            )
            continue
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red" if report["status"] == "fail" else "green",
                "issue_codes": [str(issue.get("code")) for issue in report["issues"]],
            }
        )
    return reports


def _recording_fixture_mutation_reports(recordings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mutated = _mutated_first_successful_recording(recordings)
    if mutated is None:
        return [
            {
                "mutation_id": "recorded_raw_response_hash_mismatch",
                "status": "green",
                "issue_codes": ["gy_n4_recording_success_response_missing"],
            }
        ]
    try:
        _validate_recording_fixture(mutated)
    except RuntimeError as exc:
        error = str(exc)
        return [
            {
                "mutation_id": "recorded_raw_response_hash_mismatch",
                "status": "red"
                if "gy_n4_recording_raw_response_hash_mismatch" in error
                else "green",
                "issue_codes": [error.split(":", 1)[0]],
            }
        ]
    return [
        {
            "mutation_id": "recorded_raw_response_hash_mismatch",
            "status": "green",
            "issue_codes": [],
        }
    ]


def _mutated_first_successful_recording(
    recordings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for recording in recordings:
        mutated = copy.deepcopy(recording)
        for item in mutated.get("responses") or []:
            if not isinstance(item, dict) or item.get("status") == "error":
                continue
            raw = item.get("raw_response")
            if isinstance(raw, str) and raw:
                item["raw_response"] = raw + "\n"
                return mutated
    return None


def _raw_generation_payload_issues(result_payload: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    preflight = result_payload.get("preflight")
    if isinstance(preflight, dict):
        if preflight.get("status") != "supported" and result_payload.get("status") == "generated":
            issues.append({"code": "unsupported_model_not_rejected"})
        live = preflight.get("live_model_ids")
        if (
            result_payload.get("status") == "generated"
            and isinstance(live, list)
            and result_payload.get("model_id") not in live
        ):
            issues.append({"code": "generated_model_not_in_live_catalog"})
    candidates = result_payload.get("candidates")
    if isinstance(candidates, list):
        candidates_by_id = {
            str(candidate.get("candidate_id")): candidate
            for candidate in candidates
            if isinstance(candidate, dict) and candidate.get("candidate_id")
        }
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("generator_path") != "model_generated":
                issues.append({"code": "degraded_candidate_counted_real"})
            if candidate.get("status") != "candidate_unverified":
                issues.append({"code": "candidate_reached_authority_without_A"})
            atom = candidate.get("atom")
            if isinstance(atom, dict):
                world_ref = str(atom.get("world_model_record_ref") or "")
                if world_ref.startswith("world_model_record_pending:"):
                    issues.append({"code": "pending_world_model_record_ref_admitted"})
                elif not world_ref.startswith("world_model_record_"):
                    issues.append({"code": "world_model_record_ref_not_composed"})
    else:
        candidates_by_id = {}
    slice_payload = result_payload.get("lever_space_prompt_slice")
    if isinstance(slice_payload, dict):
        if result_payload.get("status") == "generated":
            if slice_payload.get("status") != "derived":
                issues.append({"code": "lever_space_prompt_slice_not_derived"})
            if not slice_payload.get("content_hash"):
                issues.append({"code": "lever_space_prompt_slice_hash_missing"})
            if slice_payload.get("non_constraining") is not True:
                issues.append({"code": "lever_space_prompt_slice_not_non_constraining"})
    elif result_payload.get("status") == "generated":
        issues.append({"code": "lever_space_prompt_slice_missing"})
    if result_payload.get("status") == "generated":
        issues.extend(_effective_runtime_config_issues(result_payload))
    dispositions = result_payload.get("grounding_dispositions")
    if isinstance(dispositions, list):
        for disposition in dispositions:
            if not isinstance(disposition, dict):
                continue
            chain = disposition.get("certificate_chain")
            if not isinstance(chain, dict) or not chain.get("cg1_content_hash"):
                issues.append({"code": "grounding_relation_certificate_chain_missing"})
                continue
            if disposition.get("disposition") != "shadow_bound":
                continue
            candidate = candidates_by_id.get(str(disposition.get("candidate_id") or ""))
            if not isinstance(candidate, dict):
                issues.append({"code": "shadow_binding_candidate_missing"})
                continue
            provenance = candidate.get("provenance")
            parsed = provenance.get("parsed_candidate") if isinstance(provenance, dict) else {}
            if not isinstance(parsed, dict):
                issues.append({"code": "shadow_binding_parsed_candidate_missing"})
                continue
            if parsed.get("grounding_relation_content_hash") != chain.get("cg1_content_hash"):
                issues.append({"code": "candidate_grounding_relation_hash_mismatch"})
            if parsed.get("grounding_decision_content_hash") != chain.get("cg2_content_hash"):
                issues.append({"code": "candidate_grounding_decision_hash_mismatch"})
            issues.extend(
                _shadow_binding_normalization_issues(
                    candidate=candidate,
                    disposition=disposition,
                    chain=chain,
                )
            )
    elif result_payload.get("status") == "generated":
        issues.append({"code": "grounding_dispositions_missing"})
    rankings = result_payload.get("surrogate_rankings")
    if isinstance(rankings, list):
        for ranking in rankings:
            if not isinstance(ranking, dict):
                continue
            if ranking.get("trust_level") != "certified" and ranking.get("promotion_allowed"):
                issues.append({"code": "surrogate_below_certified_promoted"})
            owner_refs = ranking.get("owner_refs")
            if isinstance(owner_refs, list):
                try:
                    from polisyos.runtime.quality.design_generation import _resolve_owner_symbol

                    for owner_ref in owner_refs:
                        _resolve_owner_symbol(str(owner_ref))
                except ValueError as exc:
                    issues.append({"code": "surrogate_owner_ref_unresolved", "error": str(exc)})
    evidence = result_payload.get("firewall_evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if item.get("evidence_kind") not in NOT_CERTIFICATE_KINDS:
                continue
            reached = (
                item.get("authority_state") != "candidate_unverified"
                or item.get("blocked_from_authority") is not True
            )
            if reached:
                issues.append({"code": "not_certificate_reached_authority"})
    diversity = result_payload.get("diversity_report")
    if isinstance(diversity, dict) and diversity.get("domain_mechanism_hardcode_detected"):
        issues.append({"code": "domain_mechanism_hardcode_detected"})
    return issues


def _mutable_generation_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("generation_results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return []


def first_shadow_bound_recorded_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the first candidate from a recording that is shadow-bound."""

    results = _mutable_generation_results(payload)
    assert any(_shadow_bound_candidate_ids(result) for result in results), (
        "gy_n4_shadow_bound_recorded_candidate_missing"
    )
    for result in results:
        shadow_bound_ids = _shadow_bound_candidate_ids(result)
        for candidate in result.get("candidates") or []:
            if isinstance(candidate, dict) and candidate.get("candidate_id") in shadow_bound_ids:
                return dict(candidate)
    raise RuntimeError("gy_n4_shadow_bound_recorded_candidate_missing")


def _shadow_bound_candidate_ids(result: dict[str, Any]) -> set[str]:
    return {
        str(disposition.get("candidate_id"))
        for disposition in result.get("grounding_dispositions") or []
        if isinstance(disposition, dict)
        and disposition.get("disposition") == "shadow_bound"
        and disposition.get("candidate_id")
    }


def _first_mutable_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    for result in _mutable_generation_results(payload):
        for candidate in result.get("candidates") or []:
            if isinstance(candidate, dict):
                return candidate
    raise RuntimeError("gy_n4_mutation_candidate_missing")


def _first_mutable_surrogate_ranking(payload: dict[str, Any]) -> dict[str, Any]:
    for result in _mutable_generation_results(payload):
        for ranking in result.get("surrogate_rankings") or []:
            if isinstance(ranking, dict):
                return ranking
    raise RuntimeError("gy_n4_mutation_surrogate_ranking_missing")


def _effective_runtime_config_issues(result_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    config = result_payload.get("effective_runtime_config")
    if not isinstance(config, Mapping):
        return [{"code": "effective_runtime_config_missing"}]
    issues: list[dict[str, Any]] = []
    if float(config.get("drafter_pass_timeout_s") or 0.0) < 120.0:
        issues.append({"code": "drafter_pass_timeout_too_small"})
    if int(config.get("drafter_pass_retry_count") or 0) < 2:
        issues.append({"code": "drafter_pass_retry_count_too_small"})
    if float(config.get("formalizer_timeout_s") or 0.0) < 120.0:
        issues.append({"code": "formalizer_timeout_too_small"})
    if int(config.get("formalizer_retry_count") or 0) < 5:
        issues.append({"code": "formalizer_retry_count_too_small"})
    if float(config.get("critic_timeout_s") or 0.0) < 120.0:
        issues.append({"code": "critic_timeout_too_small"})
    if int(config.get("terminal_salvage_retry_count") or 0) < 2:
        issues.append({"code": "terminal_salvage_retry_count_too_small"})
    if int(config.get("gateway_max_retries") or 0) < 3:
        issues.append({"code": "gateway_retry_count_too_small"})
    if float(config.get("prompt_cache_ttl_s") or 0.0) <= 0.0:
        issues.append({"code": "prompt_cache_disabled"})
    prompt_size = config.get("prompt_size_estimate")
    if prompt_size is not None and not isinstance(prompt_size, Mapping):
        issues.append({"code": "prompt_size_estimate_invalid"})
    elif isinstance(prompt_size, Mapping) and int(
        prompt_size.get("slice_added_chars") or 0
    ) > _PROMPT_SLICE_LIMIT_CHARS:
        issues.append(
            {
                "code": "lever_space_prompt_slice_not_compact",
                "slice_added_chars": prompt_size.get("slice_added_chars"),
            }
        )
    return issues


def _shadow_binding_normalization_issues(
    *,
    candidate: Mapping[str, Any],
    disposition: Mapping[str, Any],
    chain: Mapping[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    atom = candidate.get("atom")
    provenance = candidate.get("provenance")
    parsed = provenance.get("parsed_candidate") if isinstance(provenance, Mapping) else {}
    if not isinstance(atom, Mapping) or not isinstance(parsed, Mapping):
        return issues
    atom_params = _mapping_value(atom.get("direct_effect_bundle")).get("params")
    parsed_params = parsed.get("params")
    if _json_safe(parsed_params or {}) != _json_safe(atom_params or {}):
        issues.append(
            {
                "code": "shadow_binding_candidate_params_not_preserved",
                "candidate_id": candidate.get("candidate_id"),
            }
        )
    candidate_kind = str(parsed.get("kind") or "")
    atom_kind = str(_mapping_value(atom.get("operator_kind")).get("trinity_kind") or "")
    original_slots = _parsed_candidate_target_slots(parsed)
    atom_slots = tuple(str(item) for item in atom.get("target_world_slots") or () if str(item))
    normalized_from = atom.get("normalized_from")
    needs_normalization = bool(
        (candidate_kind and atom_kind and candidate_kind != atom_kind)
        or (original_slots and tuple(sorted(original_slots)) != tuple(sorted(atom_slots)))
    )
    if needs_normalization and not isinstance(normalized_from, Mapping):
        issues.append(
            {
                "code": "shadow_normalization_warrant_missing",
                "candidate_id": candidate.get("candidate_id"),
            }
        )
        return issues
    if not isinstance(normalized_from, Mapping):
        return issues
    if normalized_from.get("grounding_relation") not in {"exact", "certified-specialization"}:
        issues.append({"code": "shadow_normalization_relation_not_identifying"})
    if normalized_from.get("grounding_relation_certificate_id") != chain.get("cg1_certificate_id"):
        issues.append({"code": "shadow_normalization_certificate_id_mismatch"})
    if normalized_from.get("grounding_relation_content_hash") != chain.get("cg1_content_hash"):
        issues.append({"code": "shadow_normalization_certificate_hash_mismatch"})
    if candidate_kind and normalized_from.get("original_kind") != candidate_kind:
        issues.append({"code": "shadow_normalization_original_kind_mismatch"})
    if atom_kind and normalized_from.get("normalized_kind") != atom_kind:
        issues.append({"code": "shadow_normalization_normalized_kind_mismatch"})
    if disposition.get("selected_relation") not in {"exact", "certified-specialization"}:
        issues.append({"code": "shadow_normalization_without_identifying_disposition"})
    return issues


def _mutate_degraded_candidate(payload: dict[str, Any]) -> None:
    _first_mutable_candidate(payload)["generator_path"] = "degraded_mock_fallback"


def _mutate_not_certificate_authority(payload: dict[str, Any]) -> None:
    item = _mutable_generation_results(payload)[0]["firewall_evidence"][0]
    item["authority_state"] = "promoted"
    item["blocked_from_authority"] = False


def _mutate_surrogate_promotion(payload: dict[str, Any]) -> None:
    ranking = _first_mutable_surrogate_ranking(payload)
    ranking["trust_level"] = "search_guiding"
    ranking["promotion_allowed"] = True


def _mutate_unsupported_model(payload: dict[str, Any]) -> None:
    result = _mutable_generation_results(payload)[0]
    result["model_id"] = "gpt-5-mini"
    result["preflight"]["model_id"] = "gpt-5-mini"
    result["preflight"]["status"] = "supported"


def _mutate_atom_content_hash(payload: dict[str, Any]) -> None:
    _first_mutable_candidate(payload)["atom"]["content_hash"] = "sha256:" + "f" * 64


def _mutate_pending_wmr_ref(payload: dict[str, Any]) -> None:
    _first_mutable_candidate(payload)["atom"][
        "world_model_record_ref"
    ] = "world_model_record_pending:mutated"


def _mutate_restore_exact_match_authority(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for disposition in result.get("grounding_dispositions") or []:
            if (
                isinstance(disposition, dict)
                and disposition.get("disposition") == "shadow_bound"
                and disposition.get("legacy_exact_match") == "would_reject"
            ):
                disposition["disposition"] = "unknown_blocked"
                disposition["candidate_id"] = None
                disposition["shadow_atom_content_hash"] = None
                disposition["rejected_cause"] = {"code": "legacy_exact_match_restored"}
                result["candidates"] = [
                    candidate
                    for candidate in result.get("candidates") or []
                    if any(
                        item.get("candidate_id") == candidate.get("candidate_id")
                        for item in result.get("grounding_dispositions") or []
                        if isinstance(item, dict)
                        and item.get("disposition") == "shadow_bound"
                    )
                ]
                break
    payload["grounding_payoff"]["payoff_shadow_bindings_legacy_rejected"] = []
    if isinstance(payload.get("recording_set_coverage"), dict):
        payload["recording_set_coverage"]["has_legacy_rejected_shadow_binding"] = False
        payload["recording_set_coverage"]["coverage_status"] = "missing_class"


def _mutate_binding_without_certificate(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for disposition in result.get("grounding_dispositions") or []:
            if isinstance(disposition, dict) and disposition.get("disposition") == "shadow_bound":
                disposition["certificate_chain"]["cg1_certificate_id"] = ""
                return


def _mutate_surrogate_grounding_binding(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for disposition in result.get("grounding_dispositions") or []:
            if isinstance(disposition, dict) and disposition.get("disposition") == "shadow_bound":
                disposition["selected_relation"] = "surrogate_score"
                return


def _mutate_drop_slice_hash(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        result["lever_space_prompt_slice"]["content_hash"] = None
    payload["positive_gate"]["lever_space_prompt_slice_hashes"] = []


def _mutate_adapter_authored_axis(payload: dict[str, Any]) -> None:
    probe = payload["adapter_honesty_probe"]
    signature = probe["emitted_signature"]
    signature["sign"] = "increase"
    probe["forbidden_axis_fields_present"] = ["sign"]


def _mutate_normalization_warrant_dropped(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for candidate in result.get("candidates") or []:
            atom = candidate.get("atom") if isinstance(candidate, dict) else None
            if isinstance(atom, dict) and isinstance(atom.get("normalized_from"), dict):
                atom.pop("normalized_from")
                return
    candidate = _first_mutable_candidate(payload)
    provenance = candidate.get("provenance")
    parsed = provenance.get("parsed_candidate") if isinstance(provenance, dict) else None
    atom = candidate.get("atom")
    if isinstance(parsed, dict) and isinstance(atom, dict):
        parsed["kind"] = "unwarranted_alias_for_normalized_atom"
        atom.pop("normalized_from", None)


def _mutate_effective_runtime_config(payload: dict[str, Any]) -> None:
    config = _mutable_generation_results(payload)[0]["effective_runtime_config"]
    config["drafter_pass_timeout_s"] = 30.0
    config["drafter_pass_retry_count"] = 0
    config["gateway_max_retries"] = 0
    config["terminal_salvage_retry_count"] = 0
    config["prompt_cache_ttl_s"] = 0.0


def _mutate_disposition_diverges_from_certificate_verdict(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for disposition in result.get("grounding_dispositions") or []:
            if (
                isinstance(disposition, dict)
                and disposition.get("selected_relation") == "novel-candidate"
            ):
                disposition["disposition"] = "veto_false_analog"
                disposition["rejected_cause"] = {
                    "reason": "mutated_old_n4_critical_contradiction_veto"
                }
                return
    probe = payload.get("synthetic_cg3_handoff_probe")
    if isinstance(probe, dict):
        for disposition in probe.get("dispositions") or []:
            if isinstance(disposition, dict):
                disposition["disposition"] = "veto_false_analog"
                disposition["rejected_cause"] = {
                    "reason": "mutated_old_n4_critical_contradiction_veto"
                }
                return


def _mutate_grounding_disposition_count(payload: dict[str, Any]) -> None:
    summary = _mutable_generation_results(payload)[0]["grounding_disposition_summary"]
    summary["shadow_bound"] = int(summary.get("shadow_bound") or 0) + 1


def _mutate_producer_candidate_denominator(payload: dict[str, Any]) -> None:
    diversity = _mutable_generation_results(payload)[0]["diversity_report"]
    diversity["candidate_count"] = int(diversity.get("candidate_count") or 0) + 1


def _mutate_prompt_size_gate(payload: dict[str, Any]) -> None:
    gate = payload["prompt_size_gate"]
    gate["within_limit_by_index"][0] = False


def _mutate_grounding_certificate_chain(payload: dict[str, Any]) -> None:
    for result in _mutable_generation_results(payload):
        for disposition in result.get("grounding_dispositions") or []:
            if isinstance(disposition, dict) and disposition.get("disposition") == "shadow_bound":
                disposition["certificate_chain"]["cg1_content_hash"] = "sha256:" + "f" * 64
                return


def _mutate_domain_hardcode(payload: dict[str, Any]) -> None:
    _mutable_generation_results(payload)[0]["diversity_report"][
        "domain_mechanism_hardcode_detected"
    ] = True
    payload["problem_variation_probe"]["authored_fixed_set_detected"] = True


def _mutate_authored_replay_collapse(payload: dict[str, Any]) -> None:
    payload["problem_variation_probe"]["authored_fixed_set_detected"] = True


def _mutate_problem_variation_invariant(payload: dict[str, Any]) -> None:
    variation = payload["problem_variation_probe"]
    variation["status"] = "fail"
    variation["candidate_sets_differ"] = False


def _load_recordings(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / RECORDING_FIXTURE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    recordings = payload.get("recordings")
    if not isinstance(recordings, list):
        raise RuntimeError("gy_n4_recordings_missing")
    if not recordings:
        raise RuntimeError("gy_n4_replay_recording_denominator_missing")
    loaded: list[dict[str, Any]] = []
    for index, item in enumerate(recordings):
        if not isinstance(item, Mapping):
            raise RuntimeError(f"gy_n4_recording_member_invalid:{index}")
        loaded.append(dict(item))
    for recording in loaded:
        _validate_recording_fixture(recording)
    return loaded


def _recording_fixture_integrity_report(recordings: list[dict[str, Any]]) -> dict[str, Any]:
    success_response_count = 0
    error_response_count = 0
    raw_response_hashes: list[str] = []
    prompt_hashes: list[str] = []
    for recording in recordings:
        for index, item in enumerate(recording.get("responses") or []):
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("prompt_hash"), str):
                prompt_hashes.append(str(item["prompt_hash"]))
            if item.get("status") == "error":
                error_response_count += 1
                continue
            raw = item.get("raw_response")
            recorded_hash = item.get("raw_response_hash")
            if isinstance(raw, str) and isinstance(recorded_hash, str):
                success_response_count += 1
                raw_response_hashes.append(recorded_hash)
            else:
                raise RuntimeError(
                    "gy_n4_recording_integrity_report_hash_missing:"
                    + _recorded_response_label(item, index)
                )
    return {
        "status": "pass",
        "success_response_count": success_response_count,
        "error_response_count": error_response_count,
        "raw_response_hash_gate": "required_recomputed_before_replay",
        "prompt_hash_role": "recorded_provenance_only",
        "unique_raw_response_hash_count": len(set(raw_response_hashes)),
        "unique_prompt_hash_count": len(set(prompt_hashes)),
    }


def _validate_recording_fixture(recording: dict[str, Any]) -> None:
    if not recording.get("recorded_at"):
        raise RuntimeError("gy_n4_recording_timestamp_missing")
    response = recording.get("response")
    if not isinstance(response, dict) or not response.get("prompt_hash"):
        raise RuntimeError("gy_n4_recording_primary_prompt_hash_missing")
    responses = recording.get("responses")
    if not isinstance(responses, list) or not responses:
        raise RuntimeError("gy_n4_recording_responses_missing")
    for index, item in enumerate(responses):
        if not isinstance(item, dict):
            raise RuntimeError(f"gy_n4_recording_response_invalid:{index}")
        if not item.get("prompt_hash"):
            raise RuntimeError(f"gy_n4_recording_prompt_hash_missing:{index}")
        if item.get("status") == "error":
            raw_error = item.get("raw_response")
            recorded_hash = item.get("raw_response_hash")
            if not isinstance(raw_error, str):
                raise RuntimeError(f"gy_n4_recording_raw_response_missing:{index}")
            if not isinstance(recorded_hash, str) or not recorded_hash:
                raise RuntimeError(f"gy_n4_recording_raw_response_hash_missing:{index}")
            actual_hash = gy_content_hash(raw_error)
            if actual_hash != recorded_hash:
                raise RuntimeError(
                    "gy_n4_recording_raw_response_hash_mismatch:"
                    f"{_recorded_response_label(item, index)}:{actual_hash}!={recorded_hash}"
                )
            error = item.get("error")
            if not isinstance(error, dict) or not (
                error.get("type") or error.get("status") or error.get("message")
            ):
                raise RuntimeError(f"gy_n4_recording_error_payload_missing:{index}")
            continue
        raw = item.get("raw_response")
        if not isinstance(raw, str) or not raw.strip():
            raise RuntimeError(f"gy_n4_recording_raw_response_missing:{index}")
        recorded_hash = item.get("raw_response_hash")
        if not isinstance(recorded_hash, str) or not recorded_hash:
            raise RuntimeError(f"gy_n4_recording_raw_response_hash_missing:{index}")
        actual_hash = gy_content_hash(raw)
        if actual_hash != recorded_hash:
            raise RuntimeError(
                "gy_n4_recording_raw_response_hash_mismatch:"
                f"{_recorded_response_label(item, index)}:{actual_hash}!={recorded_hash}"
            )
        if "__draft_" in raw or "__placeholder__" in raw:
            raise RuntimeError(f"gy_n4_recording_placeholder_detected:{index}")
    _verify_recording_content_hash(recording)


def _fixture_hash(repo_root: Path) -> str:
    payload = json.loads((repo_root / RECORDING_FIXTURE_PATH).read_text(encoding="utf-8"))
    return _stable_json_hash(payload)


def _recording_payload(recording: dict[str, Any], role: str) -> dict[str, Any]:
    for item in recording.get("responses") or []:
        if isinstance(item, dict) and item.get("role") == role:
            payload = item.get("raw_llm_response")
            if isinstance(payload, dict):
                return payload
    raise RuntimeError(f"gy_n4_recording_role_missing:{role}")


def _replace_recording_placeholders(payload: dict[str, Any], interventions: list[dict[str, Any]]) -> None:
    for key, value in list(payload.items()):
        if value == "__draft_interventions__":
            payload[key] = copy.deepcopy(interventions)
        elif value == "__draft_parameters__":
            payload[key] = _parameters_for_interventions(interventions)
        elif isinstance(value, dict):
            _replace_recording_placeholders(value, interventions)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _replace_recording_placeholders(item, interventions)


def _parameters_for_interventions(interventions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for intervention in interventions:
        intervention_id = str(intervention["intervention_id"])
        params = intervention.get("params") or {}
        if not isinstance(params, dict):
            continue
        for param_path, default_value in sorted(params.items()):
            rows.append(
                {
                    "param_id": f"{intervention_id}_{param_path}",
                    "intervention_id": intervention_id,
                    "param_path": str(param_path),
                    "default_value": str(default_value),
                }
            )
    return rows


def _problem_variation_report(
    first: GenerationUnderAResult,
    second: GenerationUnderAResult,
    *,
    recordings: list[dict[str, Any]],
) -> dict[str, Any]:
    first_set = _candidate_set(first)
    second_set = _candidate_set(second)
    differ = first_set != second_set
    return {
        "status": "pass" if differ else "fail",
        "candidate_sets_differ": differ,
        "authored_fixed_set_detected": not differ,
        "cases": [
            _variation_case_payload(recordings[0], first, first_set),
            _variation_case_payload(recordings[1], second, second_set),
        ],
    }


def _variation_case_payload(
    recording: dict[str, Any],
    result: GenerationUnderAResult,
    candidate_set: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "design_problem_id": recording.get("design_problem_id"),
        "domain": recording.get("domain"),
        "status": result.status,
        "candidate_set": candidate_set,
        "grounding_disposition_count": (
            result.grounding_disposition_summary.total_candidates
        ),
        "diversity_report": result.diversity_report.model_dump(mode="json"),
        "generator_paths": [candidate.generator_path for candidate in result.candidates],
        "llm_success_count": sum(1 for call in result.llm_calls if call.status == "success"),
        "llm_error_count": sum(1 for call in result.llm_calls if call.status == "error"),
        "prompt_hashes": [call.prompt_hash for call in result.llm_calls],
        "raw_response_hashes": [_stable_json_hash(call.raw_llm_response) for call in result.llm_calls],
    }


def _candidate_set(result: GenerationUnderAResult) -> list[dict[str, str]]:
    return [
        {
            "operator": candidate.diversity_key[0],
            "target_selector": candidate.diversity_key[1],
            "mechanism": candidate.diversity_key[2],
            "parameterization": candidate.diversity_key[3],
        }
        for candidate in result.candidates
    ]


def _design_problem(recording: dict[str, Any]) -> DesignProblem:
    problem_id = str(recording["design_problem_id"])
    domain = str(recording["domain"])
    if domain == "public_health_heat_risk":
        statement = "Reduce heat illness during urban heat waves with health-sector interventions."
        objective = DesignObjective(
            objective_id="heat_illness_reduction",
            description="Reduce heat illness during extreme urban heat events",
            metric_id="welfare",
        )
        target_variable = "heat_illness"
        stakeholder = DesignStakeholder(
            stakeholder_id="heat_vulnerable_residents",
            name="Heat-vulnerable residents",
            role="target_population",
        )
    elif domain == "ua_msme_cgf_decisive_capture":
        statement = (
            "Maintain Ukrainian MSME industrial production capacity while limiting fiscal "
            "exposure. Include candidate options using tax-credit wording for a temporary "
            "tax-relief lever and consider a genuinely novel financing or guarantee lever "
            "when existing fiscal levers are insufficient; all proposals remain "
            "candidate-only and must assert target slot, sign, outcome slots, effect path, "
            "and estimand when known."
        )
        objective = DesignObjective(
            objective_id="industrial_retention_decisive_capture",
            description="Retain industrial employment with bounded fiscal exposure",
            metric_id="employment_retention",
        )
        target_variable = "employment_retention"
        stakeholder = DesignStakeholder(
            stakeholder_id="industrial_workers",
            name="Industrial MSME workers",
            role="target_population",
        )
    elif domain == "ua_msme_cgf_novel_capture":
        statement = (
            "Maintain Ukrainian MSME industrial production capacity while limiting fiscal "
            "exposure. Include candidate options using tax-credit wording for a temporary "
            "tax-relief lever, and separately consider an off-slice credit-guarantee or "
            "working-capital mechanism only if it has its own mechanism, target slot, sign, "
            "mechanistic outcome slots, and effect path. Do not describe an off-slice "
            "guarantee as writing tax, procurement, or budget-multiplier slots unless that "
            "is actually the mechanism."
        )
        objective = DesignObjective(
            objective_id="industrial_retention_novel_capture",
            description="Retain industrial employment with bounded fiscal exposure",
            metric_id="employment_retention",
        )
        target_variable = "employment_retention"
        stakeholder = DesignStakeholder(
            stakeholder_id="industrial_workers",
            name="Industrial MSME workers",
            role="target_population",
        )
    else:
        statement = "Maintain industrial production capacity while limiting fiscal exposure."
        objective = DesignObjective(
            objective_id="industrial_retention",
            description="Retain industrial employment and production capacity",
            metric_id="employment_retention",
        )
        target_variable = "employment_retention"
        stakeholder = DesignStakeholder(
            stakeholder_id="industrial_workers",
            name="Industrial workers",
            role="target_population",
        )
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement=statement,
        domain=domain,
        nl_provenance=NLProvenance(
            raw_request=statement,
            source_surface="contract.recorded_gateway_replay",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="contract recorded replay",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[objective],
        constraints=[
            DesignConstraint(
                constraint_id="no_authority_without_a",
                description="N4 cannot promote or certify generated policy candidates",
                admissibility_basis="request_text",
                source_text="LLM output is candidate_unverified until A-side grounding.",
            )
        ],
        stakeholders=[stakeholder],
        outcome_of_interest=OutcomeOfInterest(
            target_variable=target_variable,
            metric_id=objective.metric_id,
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=[
                "budget_allocation_multiplier",
                "income_tax",
                "labor_market",
                "procurement_shock_intensity",
                "tax_relief_rate",
            ],
            candidate_levers=[
                CandidateLever(
                    lever_id="fiscal_budget_multiplier",
                    operator_kind="budget_allocation_multiplier",
                    instrument="Budget allocation multiplier",
                    target_slot="government_balance",
                ),
                CandidateLever(
                    lever_id="reported_income_tax",
                    operator_kind="income_tax",
                    instrument="Income tax adjustment",
                    target_slot="agents_income",
                ),
                CandidateLever(
                    lever_id="labor_market_assignment",
                    operator_kind="labor_market",
                    instrument="Labor market retention or surge staffing",
                    target_slot="agents_is_employed",
                ),
                CandidateLever(
                    lever_id="procurement_distress_shock",
                    operator_kind="procurement_shock_intensity",
                    instrument="Procurement shock intensity",
                    target_slot="cells_distress_score",
                ),
                CandidateLever(
                    lever_id="global_tax_relief",
                    operator_kind="tax_relief_rate",
                    instrument="Temporary tax relief",
                    target_slot="global_tax_rate",
                ),
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="effect_grounding",
                    question="What is the grounded effect?",
                    required_for="A-side promotion",
                )
            ]
        ),
    )


def _stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    import hashlib

    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mapping_value(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _json_safe(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _json_safe_dict(value: object) -> dict[str, Any]:
    safe = _json_safe(value)
    return safe if isinstance(safe, dict) else {}


def _parsed_candidate_target_slots(parsed: Mapping[str, Any]) -> tuple[str, ...]:
    params = _mapping_value(parsed.get("params"))
    for key in (
        "target_world_slot",
        "world_slot",
        "slot",
        "target_slot",
        "state_variable",
    ):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return (value.strip(),)
        if isinstance(value, list | tuple):
            return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _corrupt_field_drift_report(repo_root: Path) -> dict[str, Any]:
    path = repo_root / OUTPUT_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    _mutate_grounding_disposition_count(payload)
    _mutate_grounding_certificate_chain(payload)
    report = validate_payload(payload)
    corruption_red = report["status"] == "fail"
    return {
        "status": "pass" if corruption_red else "fail",
        "corruption_status": "red" if corruption_red else "green",
        "corruption_report": report,
        "issues": []
        if corruption_red
        else [{"code": "corrupt_field_drift_not_detected"}],
        "outputs": declared_outputs(),
    }


def _run_formalizer_source_flip(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Remove the formalizer evidence derivation and require the live path to go RED."""

    relative_path = Path("src/polisyos/scientist/agent/formalizer.py")
    source_path = repo_root / relative_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    old = (
        '        if candidate.model_dump(mode="json") == expected:\n'
        '            return "model_generated"\n'
    )
    new = (
        '        if candidate.model_dump(mode="json") == expected:\n'
        '            return "path_unrecorded"\n'
    )
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return (
            {
                "mutation_id": SOURCE_FLIP_MUTATION_ID,
                "result": "HARNESS_ERROR",
                "proof": f"source guard count was {text.count(old)}, expected 1",
            },
        )

    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/runtime/quality/test_design_generation.py::"
                    "test_unrecorded_formalizer_path_salvages_only_from_matching_retry"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return (
            {
                "mutation_id": SOURCE_FLIP_MUTATION_ID,
                "result": "HARNESS_ERROR",
                "proof": {
                    "error": "source_restore_hash_mismatch",
                    "before": original_hash,
                    "after": restored_hash,
                },
            },
        )
    if harness_error is not None or completed is None:
        return (
            {
                "mutation_id": SOURCE_FLIP_MUTATION_ID,
                "result": "HARNESS_ERROR",
                "proof": harness_error or "source_flip_probe_not_run",
            },
        )

    output = f"{completed.stdout}\n{completed.stderr}"
    mutation_red = completed.returncode != 0 and "formalizer_path_unrecorded" in output
    return (
        {
            "mutation_id": SOURCE_FLIP_MUTATION_ID,
            "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
            "guard": "formalizer provenance derives from matching recorded response evidence",
            "proof": {
                "command": [str(item) for item in completed.args],
                "exit_code": completed.returncode,
                "expected_terminal_reason": "formalizer_path_unrecorded",
                "terminal_reason_observed": "formalizer_path_unrecorded" in output,
                "source_restored_sha256": restored_hash,
                "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
            },
        },
    )


def _run_drafter_parser_source_flip(repo_root: Path) -> dict[str, Any]:
    """Restore naive drafter parsing and require the real N4 replay to go RED."""

    relative_path = Path("src/polisyos/scientist/agent/drafter_clients.py")
    source_path = repo_root / relative_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    old = "data = extract_llm_json_object(content)"
    new = "data = json.loads(content)"
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return {
            "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": f"source guard count was {text.count(old)}, expected 1",
        }

    rederive: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        env = {
            **os.environ,
            "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            "JAX_PLATFORMS": "cpu",
            "JAX_PLATFORM_NAME": "cpu",
        }
        rederive = subprocess.run(
            (
                sys.executable,
                str(
                    repo_root
                    / "tools/quality/validation/"
                    "check_layer3_gy_design_generation_contract.py"
                ),
                "--repo-root",
                str(repo_root),
                "--rederive-audit",
                "--output-format",
                "json",
            ),
            cwd=repo_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=3600,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or rederive is None:
        return {
            "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }

    try:
        rederive_report = json.loads(rederive.stdout)
    except json.JSONDecodeError as exc:
        return {
            "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "rederive_output_not_json",
                "detail": str(exc),
                "exit_code": rederive.returncode,
                "source_restored_sha256": restored_hash,
                "stdout_tail": "\n".join(rederive.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(rederive.stderr.splitlines()[-20:]),
            },
        }
    if rederive.returncode not in {0, 1} or not isinstance(rederive_report, Mapping):
        return {
            "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "rederive_probe_invalid_exit_or_shape",
                "exit_code": rederive.returncode,
                "source_restored_sha256": restored_hash,
                "stdout_tail": "\n".join(rederive.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(rederive.stderr.splitlines()[-20:]),
            },
        }
    issues = rederive_report.get("issues")
    issue_rows = issues if isinstance(issues, list) else []
    issue_fingerprint = Counter(
        (
            str(item.get("code")),
            item.get("index") if isinstance(item.get("index"), int) else None,
        )
        for item in issue_rows
        if isinstance(item, Mapping) and item.get("code")
    )
    issue_code_counts = dict(
        sorted(
            Counter(
                str(item.get("code"))
                for item in issue_rows
                if isinstance(item, Mapping) and item.get("code")
            ).items()
        )
    )
    positive_index_zero = any(
        isinstance(item, Mapping)
        and item.get("code") == "positive_generation_not_generated"
        and item.get("index") == 0
        for item in issue_rows
    )
    terminal_evidence = rederive_report.get("generation_terminal_evidence")
    terminal_rows = terminal_evidence if isinstance(terminal_evidence, list) else []
    terminal_reason_observed = any(
        isinstance(item, Mapping)
        and item.get("index") == 0
        and "drafter_degraded_mock_fallback" in (item.get("degraded_reasons") or [])
        for item in terminal_rows
    )
    mutation_red = (
        rederive.returncode == 1
        and rederive_report.get("status") == "fail"
        and positive_index_zero
        and terminal_reason_observed
    )
    return {
        "mutation_id": DRAFTER_PARSER_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "guard": (
            "drafter semantic model output uses the shared embedded-object parser, "
            "with degraded fallback only when no object exists"
        ),
        "proof": {
            "rederive_command": [str(item) for item in rederive.args],
            "rederive_exit_code": rederive.returncode,
            "positive_generation_index_zero_observed": positive_index_zero,
            "terminal_reason": "drafter_degraded_mock_fallback",
            "terminal_reason_observed": terminal_reason_observed,
            "issue_code_counts": issue_code_counts,
            "issue_fingerprint": [
                {"code": code, "index": index, "count": count}
                for (code, index), count in sorted(
                    issue_fingerprint.items(),
                    key=lambda item: (item[0][0], -1 if item[0][1] is None else item[0][1]),
                )
            ],
            "generation_terminal_evidence": terminal_rows,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "rederive_stdout_tail": "\n".join(rederive.stdout.splitlines()[-20:]),
            "rederive_stderr_tail": "\n".join(rederive.stderr.splitlines()[-20:]),
        },
    }


def _run_recorded_config_source_flip(repo_root: Path) -> dict[str, Any]:
    """Ignore recorded replay config and require the behavioral lane to go RED."""

    relative_path = Path(
        "tools/quality/validation/check_layer3_gy_design_generation_contract.py"
    )
    source_path = repo_root / relative_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    old = "    runtime_environment = _recorded_runtime_environment_values(expected)\n"
    new = "    runtime_environment: dict[str, str] = {}\n"
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return {
            "mutation_id": RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": f"source guard count was {text.count(old)}, expected 1",
        }

    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/runtime/quality/test_design_generation.py::"
                    "test_n4_replay_applies_recorded_effective_config_and_restores_host"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }

    output = f"{completed.stdout}\n{completed.stderr}"
    drift_reason_observed = "recorded_effective_runtime_config_drift" in output
    mutation_red = completed.returncode != 0 and drift_reason_observed
    return {
        "mutation_id": RECORDED_CONFIG_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "guard": (
            "N4 deterministic replay applies each recording's content-bound effective "
            "runtime config and verifies the owner-emitted input projection"
        ),
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "drift_reason": "recorded_effective_runtime_config_drift",
            "drift_reason_observed": drift_reason_observed,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def _run_prompt_size_source_flip(repo_root: Path) -> dict[str, Any]:
    """Hardwire prompt-size defaults and require actual-frame binding to go RED."""

    relative_path = Path("src/polisyos/runtime/quality/design_generation.py")
    source_path = repo_root / relative_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    old = (
        "def _prompt_size_estimate(base_frame: object, sliced_frame: object) -> PromptSizeEstimate:\n"
        "    base_chars = len(_json_for_prompt_size(base_frame))\n"
        "    sliced_chars = len(_json_for_prompt_size(sliced_frame))\n"
        "    added = max(0, sliced_chars - base_chars)\n"
        "    return PromptSizeEstimate(\n"
        "        frame_without_slice_chars=base_chars,\n"
        "        frame_with_slice_chars=sliced_chars,\n"
        "        slice_added_chars=added,\n"
        "        frame_without_slice_estimated_tokens=_estimated_tokens(base_chars),\n"
        "        frame_with_slice_estimated_tokens=_estimated_tokens(sliced_chars),\n"
        "        slice_added_estimated_tokens=_estimated_tokens(added),\n"
        "    )\n"
    )
    new = (
        "def _prompt_size_estimate(base_frame: object, sliced_frame: object) -> PromptSizeEstimate:\n"
        "    del base_frame, sliced_frame\n"
        "    return PromptSizeEstimate()\n"
    )
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return {
            "mutation_id": PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": f"source guard count was {text.count(old)}, expected 1",
        }

    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/runtime/quality/test_design_generation.py::"
                    "test_n4_build_live_payload_binds_prompt_size_to_actual_frames"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }

    output = f"{completed.stdout}\n{completed.stderr}"
    drift_reason = "prompt_size_measurement_not_actual_frames"
    drift_reason_observed = drift_reason in output
    mutation_red = completed.returncode != 0 and drift_reason_observed
    return {
        "mutation_id": PROMPT_SIZE_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "guard": (
            "N4 prompt-size evidence is independently recomputed from the actual "
            "base and lever-sliced prompt frames"
        ),
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "drift_reason": drift_reason,
            "drift_reason_observed": drift_reason_observed,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def _run_candidate_lever_source_flip(repo_root: Path) -> dict[str, Any]:
    """Remove candidate-lever provenance and require its owner probe to go RED."""

    relative_path = Path("src/polisyos/scientist/agent/formalizer.py")
    source_path = repo_root / relative_path
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    old = "            if key in executable_keys or key in _CANDIDATE_ONLY_PARAM_KEYS\n"
    new = "            if key in executable_keys\n"
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return {
            "mutation_id": CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": f"source guard count was {text.count(old)}, expected 1",
        }

    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    started = time.monotonic()
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/runtime/quality/test_design_generation.py::"
                    "test_formalizer_preserves_a_translated_draft_lever_as_candidate_only"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={
                **os.environ,
                "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}",
            },
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)

    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "error": "source_restore_hash_mismatch",
                "before": original_hash,
                "after": restored_hash,
            },
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }

    output = f"{completed.stdout}\n{completed.stderr}"
    candidate_lever_loss_observed = "candidate_lever_id" in output
    mutation_red = completed.returncode != 0 and candidate_lever_loss_observed
    return {
        "mutation_id": CANDIDATE_LEVER_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if mutation_red else "GREEN_MUTATION_SURVIVED",
        "guard": (
            "formalizer normalization retains the exact data-derived candidate lever "
            "as non-authoritative provenance when executable Trinity kinds differ"
        ),
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "candidate_lever_loss_observed": candidate_lever_loss_observed,
            "source_restored_sha256": restored_hash,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def _run_policy_verified_source_flip(repo_root: Path) -> dict[str, Any]:
    source_path = repo_root / "src/polisyos/scientist/validation/policy_verified/service.py"
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    replacements = (
        (
            "    del ctx, frame, option_set\n",
            (
                "    from polisyos.scientist.validation.policy_verified.testing import (\n"
                "        formalize_policy_option_set_for_contract_testing,\n"
                "    )\n"
            ),
        ),
        (
            "    if existing_ref is None:\n        return None\n",
            (
                "    if existing_ref is None:\n"
                "        fixture = formalize_policy_option_set_for_contract_testing(\n"
                "            ctx, frame, option_set\n"
                "        )\n"
                "        return TrinityBundleRef.model_validate(\n"
                "            fixture.artifact_ref.model_dump()\n"
                "        )\n"
            ),
        ),
    )
    for old, _new in replacements:
        if text.count(old) != 1:
            return {
                "mutation_id": POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
                "result": "HARNESS_ERROR",
                "proof": f"source guard count was {text.count(old)}, expected 1",
            }
    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    try:
        mutated = text
        for old, new in replacements:
            mutated = mutated.replace(old, new, 1)
        source_path.write_text(mutated, encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/scientist/nodes/builtins/compile/"
                    "test_formalize_verified_policy.py::"
                    "test_production_formalizer_only_resolves_supplied_trinity"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}"},
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": "source_restore_hash_mismatch",
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }
    return {
        "mutation_id": POLICY_VERIFIED_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if completed.returncode != 0 else "GREEN_MUTATION_SURVIVED",
        "guard": "policy-verified production accepts supplied real Trinity only",
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "source_restored_sha256": restored_hash,
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def _run_nl_source_flip(repo_root: Path) -> dict[str, Any]:
    source_path = repo_root / "src/polisyos/runtime/http/services/control/nl_pipeline.py"
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    old = "            contract_testing_agent_factory=None,\n"
    new = (
        "            contract_testing_agent_factory=(\n"
        "                __import__(\n"
        "                    'polisyos.runtime.http.services.control.nl_pipeline_testing',\n"
        "                    fromlist=['build_nl_contract_testing_agents'],\n"
        "                ).build_nl_contract_testing_agents\n"
        "            ),\n"
    )
    if text.count(old) != 1:
        return {
            "mutation_id": NL_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": f"source guard count was {text.count(old)}, expected 1",
        }
    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    try:
        source_path.write_text(text.replace(old, new, 1), encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/runtime/http/test_nl_pipeline_materialization.py::"
                    "test_production_nl_pipeline_never_injects_contract_agents"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}"},
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": NL_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": "source_restore_hash_mismatch",
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": NL_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }
    return {
        "mutation_id": NL_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if completed.returncode != 0 else "GREEN_MUTATION_SURVIVED",
        "guard": "production NL router cannot inject contract-testing agents",
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "source_restored_sha256": restored_hash,
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def _run_s2_source_flip(repo_root: Path) -> dict[str, Any]:
    source_path = repo_root / "src/polisyos/pdc/_impl/layer2_design_search.py"
    original = source_path.read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    text = original.decode("utf-8")
    family_old = "    instrument_family = expansion.instrument_families[0]\n"
    family_new = '    instrument_family = "credit_guarantee"\n'
    parameters_old = (
        "        parameterization={\n"
        "            dimension: values[0] for dimension, values in expansion.parameter_space.items()\n"
        "        },\n"
    )
    parameters_new = (
        "        parameterization={\n"
        '            "coverage": "partial_portfolio",\n'
        '            "risk_share": "first_loss",\n'
        '            "delivery_channel": "bank_intermediated",\n'
        "        },\n"
    )
    if text.count(family_old) != 1 or text.count(parameters_old) != 1:
        return {
            "mutation_id": S2_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": {
                "family_guard_count": text.count(family_old),
                "parameter_guard_count": text.count(parameters_old),
                "expected": 1,
            },
        }
    completed: subprocess.CompletedProcess[str] | None = None
    harness_error: str | None = None
    try:
        mutated = text.replace(family_old, family_new, 1).replace(
            parameters_old,
            parameters_new,
            1,
        )
        source_path.write_text(mutated, encoding="utf-8")
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                (
                    "tests/unit/pdc/test_layer2_s2_design_search.py::"
                    "test_s2_candidate_space_is_data_derived_for_unseen_families"
                ),
                "-q",
            ),
            cwd=repo_root,
            env={**os.environ, "PYTHONPATH": f"{repo_root / 'src'}:{repo_root}"},
            text=True,
            capture_output=True,
            timeout=240,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - returned as harness evidence.
        harness_error = str(exc)
    finally:
        source_path.write_bytes(original)
    restored = source_path.read_bytes()
    restored_hash = hashlib.sha256(restored).hexdigest()
    if restored != original or restored_hash != original_hash:
        return {
            "mutation_id": S2_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": "source_restore_hash_mismatch",
        }
    if harness_error is not None or completed is None:
        return {
            "mutation_id": S2_SOURCE_FLIP_MUTATION_ID,
            "result": "HARNESS_ERROR",
            "proof": harness_error or "source_flip_probe_not_run",
        }
    return {
        "mutation_id": S2_SOURCE_FLIP_MUTATION_ID,
        "result": "RED" if completed.returncode != 0 else "GREEN_MUTATION_SURVIVED",
        "guard": (
            "S2 candidate family and parameterization derive from the input-carried "
            "candidate space"
        ),
        "proof": {
            "command": [str(item) for item in completed.args],
            "exit_code": completed.returncode,
            "source_restored_sha256": restored_hash,
            "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
        },
    }


def run_source_flip_mutations(repo_root: Path) -> tuple[dict[str, Any], ...]:
    """Run every restoring N4 source mutation sequentially."""

    results = (
        *_run_formalizer_source_flip(repo_root),
        _run_drafter_parser_source_flip(repo_root),
        _run_recorded_config_source_flip(repo_root),
        _run_prompt_size_source_flip(repo_root),
        _run_candidate_lever_source_flip(repo_root),
        _run_policy_verified_source_flip(repo_root),
        _run_nl_source_flip(repo_root),
        _run_s2_source_flip(repo_root),
    )
    observed_ids = tuple(str(item.get("mutation_id")) for item in results)
    if observed_ids != N4_SOURCE_FLIP_MUTATION_IDS:
        return (
            {
                "mutation_id": "source_flip_harness_denominator",
                "result": "HARNESS_ERROR",
                "proof": {
                    "expected": list(N4_SOURCE_FLIP_MUTATION_IDS),
                    "observed": list(observed_ids),
                },
            },
        )
    return results


def main(argv: list[str] | None = None) -> int:
    """Run the GY-N4 contract validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--rederive-audit", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--source-flip-mutations", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)
    if args.source_flip_mutations:
        results = run_source_flip_mutations(repo_root)
        print(json.dumps({"results": list(results)}, indent=2, sort_keys=True))
        return 0 if all(item.get("result") == "RED" for item in results) else 1
    if args.write:
        write(repo_root)
    if args.corrupt_field_drift_check:
        report = _corrupt_field_drift_report(repo_root)
    elif args.rederive_audit:
        report = validate_rederive_audit(repo_root)
    else:
        report = validate(repo_root)
    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(
        run_timed_entrypoint(
            main,
            script_path=__file__,
            argv=sys.argv[1:],
            started_perf_counter=_TIMING_STARTED_AT,
        )
    )
