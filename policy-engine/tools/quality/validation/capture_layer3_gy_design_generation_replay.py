#!/usr/bin/env python3
"""Capture candidate-only GY-N4 replay inputs in an admitted owned directory."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import stat
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.runtime.quality.design_generation import GenerationUnderAResult

DEFAULT_MODELS = (
    "moonshotai/Kimi-K2.6",
    "moonshotai/Kimi-K2.6",
    "MiniMaxAI/MiniMax-M2.7",
)
DEFAULT_DOMAIN = "ua_msme_cgf_decisive_capture"
DEFAULT_ENV = {
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
}

gy_content_hash: Any
generate_design_candidate_bundle_under_a: Any
contract: Any


@dataclass(frozen=True)
class _OwnedCaptureDestination:
    """An admitted fresh leaf held relative to its caller-owned directory."""

    owner_root: str
    filename: str
    directory_fd: int

    @property
    def display_path(self) -> str:
        """Return the admitted lexical destination for diagnostics only."""
        return os.path.join(self.owner_root, self.filename)

    def write_text_exclusive(self, content: str) -> None:
        """Create the admitted leaf once; never follow or replace an existing entry."""
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        flags |= getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(
            self.filename,
            flags,
            0o600,
            dir_fd=self.directory_fd,
        )
        stream = None
        try:
            stream = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
            descriptor = -1
            with stream:
                stream.write(content)
                stream.flush()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def close(self) -> None:
        """Release the directory capability after capture completes."""
        if self.directory_fd >= 0:
            os.close(self.directory_fd)
            object.__setattr__(self, "directory_fd", -1)


def _admit_owned_capture_destination(
    owner_root: str | os.PathLike[str], output_name: str | os.PathLike[str]
) -> _OwnedCaptureDestination:
    """Admit one fresh basename beneath an explicit, physical owner directory.

    Every owner-root component is opened from `/` with no-follow directory
    semantics. The output is a single relative basename held under the resulting
    directory descriptor, so traversal, parent symlinks, and existing file or
    dangling-link aliases cannot redirect the write outside that owner.
    """
    if (
        os.name != "posix"
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or os.open not in os.supports_dir_fd
        or os.stat not in os.supports_dir_fd
    ):
        raise RuntimeError("versioned_capture_nofollow_dirfd_unsupported")

    owner_text = os.fspath(owner_root)
    if (
        not isinstance(owner_text, str)
        or not owner_text
        or not os.path.isabs(owner_text)
        or owner_text.startswith("//")
        or os.path.normpath(owner_text) != owner_text
    ):
        raise ValueError("versioned_capture_owner_root_must_be_absolute_canonical_path")

    output_text = os.fspath(output_name)
    if (
        not isinstance(output_text, str)
        or not output_text
        or output_text in {".", ".."}
        or os.path.isabs(output_text)
        or os.sep in output_text
        or (os.altsep is not None and os.altsep in output_text)
        or "\\" in output_text
        or "\x00" in output_text
    ):
        raise ValueError("versioned_capture_output_must_be_single_relative_filename")

    owner_components = [] if owner_text == os.sep else owner_text[len(os.sep) :].split(os.sep)
    if any(component in {"", ".", ".."} for component in owner_components):
        raise ValueError("versioned_capture_owner_root_must_be_absolute_canonical_path")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_flags |= getattr(os, "O_CLOEXEC", 0)
    directory_fd = os.open(os.sep, directory_flags)
    try:
        for component in owner_components:
            parent_stat = os.fstat(directory_fd)
            if parent_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH) and not (
                parent_stat.st_mode & stat.S_ISVTX
            ):
                raise ValueError("versioned_capture_owner_parent_must_be_sticky_or_private")
            try:
                next_fd = os.open(component, directory_flags, dir_fd=directory_fd)
            except OSError as error:
                raise ValueError(
                    "versioned_capture_owner_path_must_be_real_directory_chain"
                ) from error
            os.close(directory_fd)
            directory_fd = next_fd

        owner_stat = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(owner_stat.st_mode)
            or not hasattr(os, "geteuid")
            or owner_stat.st_uid != os.geteuid()
            or owner_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise ValueError(
                "versioned_capture_owner_directory_not_user_owned_or_group_world_writable"
            )

        try:
            os.stat(output_text, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        except OSError as error:
            raise ValueError("versioned_capture_destination_admission_failed") from error
        else:
            raise ValueError("versioned_capture_destination_must_be_fresh")

        admitted = _OwnedCaptureDestination(
            owner_root=owner_text,
            filename=output_text,
            directory_fd=directory_fd,
        )
        directory_fd = -1
        return admitted
    finally:
        if directory_fd >= 0:
            os.close(directory_fd)


def _load_runtime_symbols() -> None:
    global contract, generate_design_candidate_bundle_under_a, gy_content_hash
    if "contract" in globals():
        return
    gy_content_hash = importlib.import_module("polisyos.pdc").gy_content_hash
    design_generation = importlib.import_module("polisyos.runtime.quality.design_generation")
    generate_design_candidate_bundle_under_a = (
        design_generation.generate_design_candidate_bundle_under_a
    )
    contract = importlib.import_module(
        "tools.quality.validation.check_layer3_gy_design_generation_contract"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.capture_v3_output is not None:
        if int(args.attempts) != 1:
            raise ValueError("versioned_capture_requires_one_isolated_attempt")
        destination = _admit_owned_capture_destination(
            args.capture_v3_owner_root,
            args.capture_v3_output,
        )
        try:
            for key, value in DEFAULT_ENV.items():
                os.environ.setdefault(key, value)
            _load_runtime_symbols()
            return asyncio.run(_run_v3(args, destination))
        finally:
            destination.close()
    for key, value in DEFAULT_ENV.items():
        os.environ.setdefault(key, value)
    _load_runtime_symbols()
    return asyncio.run(_run(args))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--pace-s", type=float, default=120.0)
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--problem-id-prefix", default="gy_n4_cgf_decisive_capture")
    parser.add_argument(
        "--world-model-record-ref",
        default=None,
        help="Optional assertion of the current owner-resolved WMR ref.",
    )
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    parser.add_argument(
        "--capture-v3-output",
        type=str,
        default=None,
        help=(
            "Opt-in one-attempt candidate capture filename. Must be a fresh basename "
            "inside --capture-v3-owner-root. The CLI does not provision a producer "
            "settlement store; replay usage can remain missing, and a successful write "
            "is not runtime PASS or historical-spend evidence."
        ),
    )
    parser.add_argument(
        "--capture-v3-owner-root",
        type=str,
        default=None,
        help=(
            "Existing absolute, canonical, user-owned directory with no symlink "
            "components and no group/world-writable parent without sticky mode; "
            "capture-v3 output is confined to one fresh filename there."
        ),
    )
    args = parser.parse_args(argv)
    if (args.capture_v3_output is None) != (args.capture_v3_owner_root is None):
        parser.error("--capture-v3-output and --capture-v3-owner-root must be supplied together")
    return args


async def _run_v3(args: argparse.Namespace, destination: _OwnedCaptureDestination) -> int:
    """Write one candidate-only capture through an admitted owned destination."""
    if int(args.attempts) != 1:
        raise ValueError("versioned_capture_requires_one_isolated_attempt")
    from polisyos.runtime.quality._n4_usage_capture import capture_call_usage
    from tools.quality.validation.generation_replay_input import build_replay_capture

    repo_root = args.repo_root.resolve()
    projection = contract._resolve_current_wmr_owner_projection(repo_root)
    world_ref = _resolve_capture_world_model_record_ref(
        projection, requested=args.world_model_record_ref
    )
    model_id = str(_model_plan(args.models, 1)[0])
    problem_id = f"{args.problem_id_prefix}_v3_{_timestamp_id()}"
    problem = contract._design_problem(
        {"design_problem_id": problem_id, "domain": str(args.domain)}
    )
    failure = None
    organ = None
    with capture_call_usage() as capture:
        try:
            organ = await generate_design_candidate_bundle_under_a(
                problem,
                model_id=model_id,
                repo_root=repo_root,
                min_diverse_candidates=3,
                world_model_record_ref=world_ref,
            )
        except Exception as error:
            import traceback

            failure = {"type": type(error).__name__, "traceback": traceback.format_exc()}
    actual_calls = (
        [call.model_dump(mode="json") for call in organ.result.llm_calls]
        if organ is not None
        else capture.calls
    )
    if actual_calls != capture.calls:
        raise ValueError("versioned_capture_complete_call_denominator_mismatch")
    if not actual_calls:
        attempt = {
            "schema_version": "policyos.testing.design_generation_capture_attempt.v1",
            "disposition": "no_replay_input_no_provider_call_bytes",
            "model_id": model_id,
            "design_problem_id": problem_id,
            "failure": failure,
            "actual_result": organ.result.model_dump(mode="json") if organ is not None else None,
            "authority_scope": "diagnostic_only_not_runtime_acceptance",
            "usage_qualification": "candidate_quantity_only_committed_settlement_required",
            "runtime_acceptance": "not_asserted",
        }
        destination.write_text_exclusive(json.dumps(attempt, indent=2) + "\n")
        print(
            "CAPTURE_V3_NO_CALLS "
            + json.dumps(
                {
                    "path": destination.display_path,
                    "disposition": attempt["disposition"],
                    "authority": "candidate_input_only",
                    "usage_qualification": attempt["usage_qualification"],
                    "runtime_acceptance": "not_asserted",
                }
            ),
            flush=True,
        )
        return 1
    metadata = {
        "recorded_at": _now_iso(),
        "design_problem_id": problem_id,
        "domain": str(args.domain),
        "model_id": model_id,
        "world_model_record_ref": world_ref,
        "problem_content_ref": gy_content_hash(problem.model_dump(mode="json")),
        "capture_status": organ.result.status if organ is not None else "capture_exception",
        "failure": failure,
        "source_qualification": "separate_runtime_readset_and_receipt_required_for_historical_claims",
        "usage_qualification": "candidate_quantity_only_committed_settlement_required",
        "runtime_acceptance": "not_asserted",
    }
    try:
        envelope = build_replay_capture(
            metadata=metadata, calls=actual_calls, evidence=capture.evidence
        )
    except Exception:
        import traceback

        diagnostic = {
            "schema_version": "policyos.testing.design_generation_capture_attempt.v1",
            "disposition": "capture_input_reconciliation_failed_not_replay_input",
            "metadata": metadata,
            "source_calls": actual_calls,
            "call_usage": [row.model_dump(mode="json") for row in capture.evidence],
            "capture_failures": capture.failures,
            "traceback": traceback.format_exc(),
            "authority_scope": "diagnostic_only_not_runtime_acceptance",
            "usage_qualification": "candidate_quantity_only_committed_settlement_required",
            "runtime_acceptance": "not_asserted",
        }
        destination.write_text_exclusive(json.dumps(diagnostic, indent=2) + "\n")
        print(
            "CAPTURE_V3_RECONCILIATION_ERROR "
            + json.dumps(
                {
                    "path": destination.display_path,
                    "authority": "candidate_input_only",
                    "usage_qualification": diagnostic["usage_qualification"],
                    "runtime_acceptance": "not_asserted",
                }
            ),
            flush=True,
        )
        return 1
    destination.write_text_exclusive(envelope.model_dump_json(indent=2) + "\n")
    print(
        "CAPTURE_V3_WRITE_CANDIDATE_INPUT "
        + json.dumps(
            {
                "path": destination.display_path,
                "content_hash": envelope.content_hash,
                "calls": len(actual_calls),
                "authority": "candidate_input_only",
                "usage_qualification": "candidate_quantity_only_committed_settlement_required",
                "runtime_acceptance": "not_asserted",
            }
        ),
        flush=True,
    )
    return 0 if organ is not None and _recordable(organ.result) else 1


async def _run(args: argparse.Namespace) -> int:
    repo_root = args.repo_root.resolve()
    owner_projection = contract._resolve_current_wmr_owner_projection(repo_root)
    world_model_record_ref = _resolve_capture_world_model_record_ref(
        owner_projection,
        requested=args.world_model_record_ref,
    )
    fixture_path = repo_root / contract.RECORDING_FIXTURE_PATH
    fixture = _load_fixture(fixture_path)
    recordings = _recordings(fixture)
    results = await _replay_existing(
        repo_root,
        recordings,
        owner_projection=owner_projection,
    )
    _print_coverage("INITIAL_COVERAGE", results)

    attempts = max(0, int(args.attempts))
    model_plan = _model_plan(args.models, attempts)
    for index, model_id in enumerate(model_plan, start=1):
        problem_id = f"{args.problem_id_prefix}_{index}_{_timestamp_id()}"
        print(f"ATTEMPT_START {index}/{attempts} model={model_id} problem={problem_id}", flush=True)
        journal_path = repo_root / ".tmp" / "gy-n4-capture-journals" / f"{problem_id}.jsonl"
        previous_journal = os.environ.get("POLISYOS_N4_CALL_JOURNAL_PATH")
        os.environ["POLISYOS_N4_CALL_JOURNAL_PATH"] = str(journal_path)
        try:
            run = await generate_design_candidate_bundle_under_a(
                contract._design_problem(
                    {
                        "design_problem_id": problem_id,
                        "domain": str(args.domain),
                    }
                ),
                model_id=str(model_id),
                repo_root=repo_root,
                min_diverse_candidates=3,
                world_model_record_ref=world_model_record_ref,
            )
        except Exception as exc:
            fixture = _load_fixture(fixture_path)
            diagnostic = _diagnostic_from_exception(
                exc,
                design_problem_id=problem_id,
                domain=str(args.domain),
                model_id=str(model_id),
                world_model_record_ref=world_model_record_ref,
                journal_path=journal_path,
            )
            fixture.setdefault("diagnostic_archive", []).insert(0, diagnostic)
            _write_fixture(fixture_path, fixture)
            print(
                "ATTEMPT_WRITE diagnostic_archive "
                f"reason={diagnostic['archive_reason']} exception={type(exc).__name__}",
                flush=True,
            )
            coverage = _print_coverage("ACCUMULATED_COVERAGE", results)
            if coverage and coverage.get("coverage_status") == "covered":
                print("CAPTURE_SET_COVERED", json.dumps(coverage, sort_keys=True), flush=True)
                return 0
            if index < attempts and float(args.pace_s) > 0:
                print(f"PACE_SLEEP seconds={float(args.pace_s):.1f}", flush=True)
                await asyncio.sleep(float(args.pace_s))
            continue
        finally:
            if previous_journal is None:
                os.environ.pop("POLISYOS_N4_CALL_JOURNAL_PATH", None)
            else:
                os.environ["POLISYOS_N4_CALL_JOURNAL_PATH"] = previous_journal
        result = run.result
        _print_result(result)
        fixture = _load_fixture(fixture_path)
        if _recordable(result):
            recording = _recording_from_result(
                result,
                design_problem_id=problem_id,
                domain=str(args.domain),
                model_id=str(model_id),
                world_model_record_ref=world_model_record_ref,
            )
            _recordings(fixture).append(recording)
            results.append(result)
            _write_fixture(fixture_path, fixture)
            print(
                "ATTEMPT_WRITE recordings[] "
                f"id={recording['recording_id']} hash={recording['recording_content_hash']}",
                flush=True,
            )
        else:
            diagnostic = _diagnostic_from_result(
                result,
                design_problem_id=problem_id,
                domain=str(args.domain),
                model_id=str(model_id),
                world_model_record_ref=world_model_record_ref,
            )
            fixture.setdefault("diagnostic_archive", []).insert(0, diagnostic)
            _write_fixture(fixture_path, fixture)
            print(
                "ATTEMPT_WRITE diagnostic_archive "
                f"reason={diagnostic['archive_reason']} status={result.status}",
                flush=True,
            )
        coverage = _print_coverage("ACCUMULATED_COVERAGE", results)
        if coverage and coverage.get("coverage_status") == "covered":
            print("CAPTURE_SET_COVERED", json.dumps(coverage, sort_keys=True), flush=True)
            return 0
        if index < attempts and float(args.pace_s) > 0:
            print(f"PACE_SLEEP seconds={float(args.pace_s):.1f}", flush=True)
            await asyncio.sleep(float(args.pace_s))
    print("CAPTURE_SET_INCOMPLETE", flush=True)
    return 1


def _resolve_capture_world_model_record_ref(
    owner_projection: Mapping[str, Any],
    *,
    requested: object,
) -> str:
    """Resolve the current owner WMR and refuse stale capture assertions."""

    _load_runtime_symbols()
    contract._validate_current_wmr_owner_projection(owner_projection)
    resolved = str(owner_projection["world_model_record_id"])
    if requested is not None and str(requested) != resolved:
        raise RuntimeError(
            f"gy_n4_capture_world_model_record_ref_not_current:{requested}!={resolved}"
        )
    return resolved


async def _replay_existing(
    repo_root: Path,
    recordings: list[dict[str, Any]],
    *,
    owner_projection: Mapping[str, Any],
) -> list[GenerationUnderAResult]:
    reissued, _receipt = contract._reissue_recordings_to_current_wmr(
        recordings,
        owner_projection=owner_projection,
    )
    results: list[GenerationUnderAResult] = []
    for recording in reissued:
        results.append(await contract._run_live_generation(repo_root, recording=recording))
    return results


def _recordable(result: GenerationUnderAResult) -> bool:
    return (
        result.status == "generated"
        and not result.degraded_artifacts
        and bool(result.llm_calls)
        and result.lever_space_prompt_slice.status == "derived"
        and bool(result.lever_space_prompt_slice.content_hash)
    )


def _recording_from_result(
    result: GenerationUnderAResult,
    *,
    design_problem_id: str,
    domain: str,
    model_id: str,
    world_model_record_ref: str,
) -> dict[str, Any]:
    responses = _responses(result)
    first_response = responses[0]
    recording: dict[str, Any] = {
        "recording_id": f"gy_n4_replay_{_timestamp_id()}_{gy_content_hash(responses).removeprefix('sha256:')[:12]}",
        "recording_source": "live_gateway_real_capture_accumulating_harness",
        "recorded_at": _now_iso(),
        "design_problem_id": design_problem_id,
        "domain": domain,
        "model_id": model_id,
        "world_model_record_ref": world_model_record_ref,
        "prompt_state": "final_prompt_frozen_axis_ontology_and_cg1_verbatim_mapping",
        "response": first_response,
        "responses": responses,
        "capture_summary": {
            "candidate_count": len(result.candidates),
            "grounding_summary": result.grounding_disposition_summary.model_dump(mode="json"),
            "lever_space_prompt_slice_hash": result.lever_space_prompt_slice.content_hash,
            "effective_runtime_config": result.effective_runtime_config.model_dump(mode="json"),
            "diversity_report": result.diversity_report.model_dump(mode="json"),
        },
    }
    recording["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in recording.items() if key != "recording_content_hash"}
    )
    return recording


def _diagnostic_from_result(
    result: GenerationUnderAResult,
    *,
    design_problem_id: str,
    domain: str,
    model_id: str,
    world_model_record_ref: str,
) -> dict[str, Any]:
    return {
        "archive_reason": "generated_run_not_recordable"
        if result.status == "generated"
        else "generation_not_generated",
        "attempt_source": "live_gateway_accumulating_harness",
        "recorded_at": _now_iso(),
        "counts_toward_replay_coverage": False,
        "design_problem_id": design_problem_id,
        "domain": domain,
        "model_id": model_id,
        "world_model_record_ref": world_model_record_ref,
        "status": result.status,
        "preflight": result.preflight.model_dump(mode="json"),
        "grounding_summary": result.grounding_disposition_summary.model_dump(mode="json"),
        "diversity_report": result.diversity_report.model_dump(mode="json"),
        "degraded_artifacts": [item.model_dump(mode="json") for item in result.degraded_artifacts],
        "lever_space_prompt_slice_hash": result.lever_space_prompt_slice.content_hash,
        "effective_runtime_config": result.effective_runtime_config.model_dump(mode="json"),
        "responses": _responses(result),
    }


def _diagnostic_from_exception(
    exc: Exception,
    *,
    design_problem_id: str,
    domain: str,
    model_id: str,
    world_model_record_ref: str,
    journal_path: Path,
) -> dict[str, Any]:
    return {
        "archive_reason": "generation_exception_with_call_journal",
        "attempt_source": "live_gateway_accumulating_harness",
        "recorded_at": _now_iso(),
        "counts_toward_replay_coverage": False,
        "design_problem_id": design_problem_id,
        "domain": domain,
        "model_id": model_id,
        "world_model_record_ref": world_model_record_ref,
        "status": "generation_unavailable",
        "exception": {
            "type": type(exc).__name__,
            "message": str(exc)[:2000],
        },
        "journal_path": str(journal_path),
        "responses": _responses_from_journal(journal_path),
    }


def _responses(result: GenerationUnderAResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in result.llm_calls:
        rows.append(_response_from_call_payload(call.model_dump(mode="json")))
    return rows


def _responses_from_journal(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(_response_from_call_payload(payload))
    return rows


def _response_from_call_payload(call: dict[str, Any]) -> dict[str, Any]:
    from tools.quality.validation.generation_replay_input import response_from_call_payload

    row = response_from_call_payload(call)
    if not call.get("role_hint"):
        row["role"] = _role_for_index(int(call.get("call_index") or 0))
    return row


def _role_for_index(index: int) -> str:
    return {
        0: "draft",
        1: "drafter_multipass_1",
        2: "drafter_multipass_2",
        3: "formalize",
        4: "critic",
    }.get(index, f"llm_call_{index}")


def _print_result(result: GenerationUnderAResult) -> None:
    print(f"ATTEMPT_STATUS {result.status}", flush=True)
    print(
        "ATTEMPT_SUMMARY "
        + json.dumps(result.grounding_disposition_summary.model_dump(mode="json"), sort_keys=True),
        flush=True,
    )
    print(
        "ATTEMPT_DIVERSITY "
        + json.dumps(result.diversity_report.model_dump(mode="json"), sort_keys=True),
        flush=True,
    )
    for disposition in result.grounding_dispositions:
        print(
            "ATTEMPT_DISPOSITION "
            + json.dumps(
                {
                    "proposal_id": disposition.proposal_id,
                    "disposition": disposition.disposition,
                    "selected_relation": disposition.selected_relation,
                    "legacy_exact_match": disposition.legacy_exact_match,
                    "cg2_decision": disposition.cg2_decision,
                    "cg3_decision": disposition.cg3_decision,
                    "rejected_cause": disposition.rejected_cause,
                },
                sort_keys=True,
            ),
            flush=True,
        )


def _print_coverage(
    label: str,
    results: list[GenerationUnderAResult],
) -> dict[str, Any] | None:
    if not results:
        print(f"{label} none", flush=True)
        return None
    coverage = contract._recording_set_coverage(results)
    print(f"{label} " + json.dumps(coverage, sort_keys=True), flush=True)
    return coverage


def _model_plan(models: Sequence[str], attempts: int) -> list[str]:
    if not models:
        models = DEFAULT_MODELS
    plan: list[str] = []
    for index in range(attempts):
        plan.append(str(models[index]) if index < len(models) else str(models[-1]))
    return plan


def _load_fixture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema_version": "policyos.policy_design_case.layer3_gy.design_generation_replay_recordings.v1",
            "recording_fixture_id": "gy_n4_cgf_hook_accumulating_capture",
            "recordings": [],
            "diagnostic_archive": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("recordings"), list):
        payload["recordings"] = []
    if not isinstance(payload.get("diagnostic_archive"), list):
        payload["diagnostic_archive"] = []
    return payload


def _recordings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recordings = payload.setdefault("recordings", [])
    if not isinstance(recordings, list):
        raise RuntimeError("gy_n4_capture_recordings_not_list")
    return recordings


def _write_fixture(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
