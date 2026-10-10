"""Focused mutation controls for occurrence admission evidence bindings."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

EMITTER_PATH = Path(__file__).resolve().parents[1] / "emit_proposals.py"
SPEC = importlib.util.spec_from_file_location("e02_emit_proposals", EMITTER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load the admission emitter")
EMITTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EMITTER)

CANDIDATE = {"commit": "1" * 40, "tree": "2" * 40}
OCCURRENCE_POINTER = "#/findings/0/criterion_refs/0"
OCCURRENCE_SHA = "d" * 64


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_failure(action: object, message_fragment: str | None = None) -> None:
    try:
        action()
    except ValueError as exc:
        if message_fragment is not None:
            check(message_fragment in str(exc), f"unexpected rejection: {exc}")
    else:
        raise AssertionError("expected validation failure")


def environment_fixture() -> tuple[dict[str, object], dict[str, object]]:
    footprint = [
        {
            "path": "policy-engine/backend.toml",
            "change": "M",
            "git_blob": "b" * 40,
            "sha256": "3" * 64,
        },
        {
            "path": "policy-engine/uv.lock",
            "change": "M",
            "git_blob": "c" * 40,
            "sha256": "4" * 64,
        },
    ]
    selected_inputs = [
        {"identity": "fixture:available", "status": "available", "sha256": "a" * 64},
        {"identity": "fixture:unavailable", "status": "unavailable", "sha256": None},
    ]
    commands = [
        {
            "argv": ["python", "-m", "pytest", "tests/unit/test_example.py"],
            "cwd": "policy-engine",
            "status": "PASS",
            "stdout_ref": raw_ref("stdout.txt", "5" * 64),
            "stderr_ref": raw_ref("stderr.txt", "6" * 64),
        },
        {
            "command": "python tools/optional_probe.py",
            "cwd": "policy-engine",
            "status": "UNRUN",
            "unrun_reason": "fixture not required for this slice",
        },
    ]
    normalized_inputs = EMITTER.normalized_environment_inputs(selected_inputs, label="fixture")
    manifest: dict[str, object] = {
        "schema": EMITTER.ENVIRONMENT_MANIFEST_SCHEMA,
        "candidate_source": CANDIDATE,
        "backend_id": "python-runtime",
        "profile_id": "local-candidate-py314",
        "source_refs": [
            {"path": "policy-engine/backend.toml", "role": "backend_recipe", "sha256": "3" * 64},
            {"path": "policy-engine/uv.lock", "role": "lockfile", "sha256": "4" * 64},
        ],
        "runtime": {
            "implementation": "CPython",
            "version": "3.14.0",
            "executable": "/candidate/.venv/bin/python",
        },
        "platform": {"system": "Darwin", "release": "26.0", "machine": "arm64"},
        "loaded_import_origins": [
            {
                "module": "polisyos.runtime",
                "origin": "policy-engine/src/polisyos/runtime/__init__.py",
                "package_version": "0.1.0",
            },
            {
                "module": "numpy",
                "origin": "/candidate/.venv/lib/python3.14/site-packages/numpy/__init__.py",
                "package_version": "2.3.0",
            },
        ],
        "environment_settings": {"OMP_NUM_THREADS": "1", "LC_ALL": "C.UTF-8"},
        "command_runs": [
            {
                "command_index": 0,
                "argv": commands[0]["argv"],
                "cwd": commands[0]["cwd"],
                "status": "PASS",
                "stdout_sha256": "5" * 64,
                "stderr_sha256": "6" * 64,
            },
            {
                "command_index": 1,
                "command": commands[1]["command"],
                "cwd": commands[1]["cwd"],
                "status": "UNRUN",
                "unrun_reason": commands[1]["unrun_reason"],
            },
        ],
        "selected_inputs": normalized_inputs,
        "selected_input_denominator_sha256": EMITTER.canonical_json_sha256(normalized_inputs),
    }
    handoff: dict[str, object] = {
        "candidate_source": CANDIDATE,
        "source_footprint": footprint,
        "selected_inputs": selected_inputs,
        "commands": commands,
        "backend_profile": {
            "backend_id": "python-runtime",
            "profile_id": "local-candidate-py314",
            "environment_sha256": "0" * 64,
            "environment_manifest_ref": {
                "storage": EMITTER.LOCAL_RAW_STORAGE,
                "path": (
                    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
                    "LOCAL/raw/test/environment.json"
                ),
                "sha256": "0" * 64,
                "candidate_source": CANDIDATE,
                "availability": "available_local_readback",
            },
        },
    }
    reseal(handoff, manifest)
    return handoff, manifest


def raw_ref(name: str, digest: str) -> dict[str, object]:
    return {
        "storage": EMITTER.LOCAL_RAW_STORAGE,
        "path": (
            "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
            f"LOCAL/raw/test/{name}"
        ),
        "sha256": digest,
        "candidate_source": CANDIDATE,
        "availability": "available_local_readback",
    }


def reseal(handoff: dict[str, object], manifest: dict[str, object]) -> bytes:
    data = canonical_bytes(manifest)
    profile = handoff["backend_profile"]
    if not isinstance(profile, dict):
        raise TypeError("fixture backend_profile must be an object")
    profile["environment_sha256"] = EMITTER.sha256(data)
    manifest_ref = profile["environment_manifest_ref"]
    if not isinstance(manifest_ref, dict):
        raise TypeError("fixture environment_manifest_ref must be an object")
    manifest_ref["sha256"] = EMITTER.sha256(data)
    return data


def test_verified_roles_are_required_without_any_proposal_disposition() -> None:
    base_evaluation = {
        "state": "VERIFIED",
        "result_summary": "current consumer exercised",
        "boundary": {"kind": "property", "details": "exact occurrence"},
        "next_check": "retain the final source-bound receipt",
        "candidate_source": CANDIDATE,
        "evidence_refs": [],
        "execution_context": {},
        "attempts": [],
        "review_escape": {"state": "none_observed"},
    }

    def validate(roles: list[str], disposition: str | None = None) -> None:
        evaluation = copy.deepcopy(base_evaluation)
        evaluation["evidence_refs"] = [{"role": role} for role in roles]
        if disposition is not None:
            evaluation["proposal_disposition"] = disposition
        with (
            patch.object(EMITTER, "validate_candidate_source", return_value=CANDIDATE),
            patch.object(
                EMITTER,
                "validate_evidence_refs",
                return_value=evaluation["evidence_refs"],
            ),
            patch.object(EMITTER, "validate_execution_context", return_value={}),
            patch.object(EMITTER, "validate_attempts", return_value=[]),
            patch.object(
                EMITTER,
                "validate_p40_escape",
                return_value={"state": "none_observed"},
            ),
        ):
            EMITTER.validate_explicit_evaluation(
                evaluation,
                Path("."),
                OCCURRENCE_POINTER,
                OCCURRENCE_SHA,
                finding_id="B001",
                source_footprint_sha256="e" * 64,
                complete_census={},
            )

    complete_roles = ["property_positive", "actual_consumer", "negative"]
    validate(complete_roles)
    for missing_role in complete_roles:
        remaining = [role for role in complete_roles if role != missing_role]
        expect_failure(
            lambda remaining=remaining: validate(remaining),
            "VERIFIED evaluation needs",
        )
    expect_failure(
        lambda: validate(["property_positive", "actual_consumer"], "held"),
        "VERIFIED evaluation needs",
    )


def test_canonical_environment_manifest_binds_all_receipt_denominators() -> None:
    handoff, manifest = environment_fixture()
    raw_bytes = reseal(handoff, manifest)
    with patch.object(EMITTER, "validate_local_raw_output", return_value=raw_bytes) as reader:
        validated = EMITTER.validate_backend_environment_manifest(
            Path("."), handoff, candidate_source=CANDIDATE, label="positive fixture"
        )
    check(validated == manifest, "valid environment manifest was not preserved")
    check(reader.call_args.kwargs["read_bytes"], "manifest raw read did not return bound bytes")


def test_complete_typed_receipt_accepts_exact_manifest_without_git_access() -> None:
    handoff, manifest = environment_fixture()
    raw_bytes = reseal(handoff, manifest)
    handoff.update(
        {
            "schema": EMITTER.SLICE_HANDOFF_SCHEMA,
            "slice_id": "test",
            "slice_base": CANDIDATE,
            "parents": ["9" * 40],
            "chain": {
                "producer": "source producer",
                "artifact": "typed artifact",
                "bridge": "orchestration bridge",
                "consumer": "actual consumer",
            },
            "controls": [],
            "consumer_surface": {
                "consumer_id": "consumer.test",
                "path": "policy-engine/src/polisyos/runtime/example.py",
                "selector": "consume_example",
            },
            "limitations": [],
            "proposal_ids": ["B001"],
            "proposal_occurrences": [
                {
                    "finding_id": "B001",
                    "occurrence_pointer": OCCURRENCE_POINTER,
                    "criterion_sha256": OCCURRENCE_SHA,
                }
            ],
            "decision_refs": [{"kind": "prototype"}],
            "formal_closure_ids": [],
        }
    )
    handoff["decision_refs"] = [
        {
            "kind": "prototype",
            "source_ref": {
                "covers": {
                    "occurrence_pointer": OCCURRENCE_POINTER,
                    "sha256": OCCURRENCE_SHA,
                }
            },
        }
    ]
    with patch.object(EMITTER, "decision_refs_by_occurrence"):
        EMITTER.validate_slice_handoff(
            handoff,
            path=f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
            slice_id="test",
            expected_candidate=CANDIDATE,
            label="complete shape",
        )

    missing_cwd = copy.deepcopy(handoff)
    missing_cwd["commands"][0].pop("cwd")
    with patch.object(EMITTER, "decision_refs_by_occurrence"):
        expect_failure(
            lambda: EMITTER.validate_slice_handoff(
                missing_cwd,
                path=f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
                slice_id="test",
                expected_candidate=CANDIDATE,
                label="missing cwd",
            ),
            "working directory",
        )

    source_bytes = canonical_bytes(handoff)

    def read_raw(
        _root: Path,
        _ref: dict[str, object],
        *,
        read_bytes: bool = False,
        **_kwargs: object,
    ) -> bytes | None:
        return raw_bytes if read_bytes else None

    with (
        patch.object(EMITTER, "git_bytes", return_value=source_bytes),
        patch.object(EMITTER, "validate_slice_handoff"),
        patch.object(EMITTER, "validate_slice_source_relationships"),
        patch.object(EMITTER, "validate_slice_footprint"),
        patch.object(EMITTER, "validate_local_raw_output", side_effect=read_raw),
        patch.object(EMITTER, "validate_decision_research_rows"),
    ):
        validated = EMITTER.validate_typed_slice_receipt(
            Path("."),
            {
                "role": "typed_slice_receipt",
                "path": f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
                "commit": "8" * 40,
            },
            candidate_source=CANDIDATE,
            occurrence_pointer=OCCURRENCE_POINTER,
            occurrence_sha256=OCCURRENCE_SHA,
            finding_id="B001",
            evaluation_state="VERIFIED",
            complete_census={},
            label="full positive",
        )
    check(validated == handoff, "valid typed receipt was not preserved")


def test_backend_profile_evidence_requires_exact_pointer() -> None:
    evidence_refs = [
        {"role": "configuration_scope"},
        {"role": "no_input_basis"},
        {
            "role": "backend_profile",
            "pointer": "#/backend_profile/identity",
            "path": f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
            "commit": "8" * 40,
        },
        {"role": "actual_consumer"},
        {
            "role": "typed_slice_receipt",
            "path": f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
            "commit": "8" * 40,
        },
        {
            "role": "prototype",
            "path": f"{EMITTER.LOCAL_REL.as_posix()}/test.json",
            "commit": "8" * 40,
            "pointer": "#/decision_refs/0",
        },
    ]
    context = {
        "source_footprint_sha256": "e" * 64,
        "configuration_and_lock_evidence_indexes": [],
        "configuration_scope_evidence_index": 0,
        "selected_input_state": "not_required",
        "selected_input_evidence_indexes": [],
        "input_scope_evidence_index": 1,
        "backend_profile_evidence_index": 2,
        "consumer_surface_evidence_indexes": [3],
        "typed_slice_receipt_evidence_indexes": [4],
        "decision_research_evidence_indexes": [5],
    }

    def validate(refs: list[dict[str, object]]) -> None:
        with (
            patch.object(
                EMITTER,
                "validate_typed_slice_receipt",
                return_value={"selected_inputs": []},
            ),
            patch.object(EMITTER, "validate_input_evidence_bindings"),
        ):
            EMITTER.validate_execution_context(
                Path("."),
                context,
                refs,
                candidate_source=CANDIDATE,
                occurrence_pointer=OCCURRENCE_POINTER,
                occurrence_sha256=OCCURRENCE_SHA,
                finding_id="B001",
                evaluation_state="VERIFIED",
                source_footprint_sha256="e" * 64,
                complete_census={},
            )

    good_refs = copy.deepcopy(evidence_refs)
    good_refs[2]["pointer"] = "#/backend_profile"
    validate(good_refs)
    expect_failure(lambda: validate(evidence_refs), "identify the backend_profile object")


def test_environment_mutations_fail_after_attacker_recomputes_outer_hashes() -> None:
    mutations = {
        "profile identity": lambda manifest: manifest.__setitem__("profile_id", "other-profile"),
        "input bytes": lambda manifest: manifest["selected_inputs"][0].__setitem__(
            "sha256", "b" * 64
        ),
        "command output": lambda manifest: manifest["command_runs"][0].__setitem__(
            "stdout_sha256", "f" * 64
        ),
        "candidate config": lambda manifest: manifest["source_refs"][1].__setitem__(
            "sha256", "f" * 64
        ),
        "runtime identity": lambda manifest: manifest["runtime"].__setitem__("version", ""),
    }
    for label, mutate in mutations.items():
        handoff, manifest = environment_fixture()
        mutate(manifest)
        if label == "input bytes":
            manifest["selected_input_denominator_sha256"] = EMITTER.canonical_json_sha256(
                manifest["selected_inputs"]
            )
        raw_bytes = reseal(handoff, manifest)

        def validate_mutation(
            raw_bytes: bytes = raw_bytes,
            handoff: dict[str, object] = handoff,
            label: str = label,
        ) -> None:
            EMITTER.validate_environment_manifest_bytes(
                raw_bytes,
                handoff,
                candidate_source=CANDIDATE,
                label=label,
            )

        expect_failure(validate_mutation)


def test_environment_fingerprint_must_equal_recomputed_bytes() -> None:
    handoff, manifest = environment_fixture()
    raw_bytes = canonical_bytes(manifest)
    profile = handoff["backend_profile"]
    if not isinstance(profile, dict):
        raise TypeError("fixture backend_profile must be an object")
    profile["environment_sha256"] = "f" * 64
    manifest_ref = profile["environment_manifest_ref"]
    if not isinstance(manifest_ref, dict):
        raise TypeError("fixture environment_manifest_ref must be an object")
    manifest_ref["sha256"] = "f" * 64
    expect_failure(
        lambda: EMITTER.validate_environment_manifest_bytes(
            raw_bytes,
            handoff,
            candidate_source=CANDIDATE,
            label="wrong digest",
        ),
        "SHA-256 does not match",
    )


def test_malformed_source_and_command_enums_refuse_cleanly() -> None:
    handoff, manifest = environment_fixture()
    manifest["source_refs"][0]["role"] = []
    raw_bytes = reseal(handoff, manifest)
    expect_failure(
        lambda: EMITTER.validate_environment_manifest_bytes(
            raw_bytes,
            handoff,
            candidate_source=CANDIDATE,
            label="malformed source role",
        ),
        "source role is invalid",
    )

    handoff, manifest = environment_fixture()
    handoff["commands"][0]["status"] = []
    raw_bytes = reseal(handoff, manifest)
    expect_failure(
        lambda: EMITTER.validate_environment_manifest_bytes(
            raw_bytes,
            handoff,
            candidate_source=CANDIDATE,
            label="malformed command status",
        ),
        "command status is invalid",
    )


if __name__ == "__main__":
    for test in (
        test_verified_roles_are_required_without_any_proposal_disposition,
        test_canonical_environment_manifest_binds_all_receipt_denominators,
        test_complete_typed_receipt_accepts_exact_manifest_without_git_access,
        test_backend_profile_evidence_requires_exact_pointer,
        test_environment_mutations_fail_after_attacker_recomputes_outer_hashes,
        test_environment_fingerprint_must_equal_recomputed_bytes,
        test_malformed_source_and_command_enums_refuse_cleanly,
    ):
        test()
    sys.stdout.write("7 admission proof-binding checks passed\n")
