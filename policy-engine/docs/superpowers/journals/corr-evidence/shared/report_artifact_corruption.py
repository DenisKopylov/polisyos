"""Mutate one persisted report leaf, run its owner, and restore exact bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"ambiguous_duplicate_json_key:{key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> NoReturn:
    raise ValueError(f"non_json_constant:{value}")


_DECODER = json.JSONDecoder(object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def _pointer_parts(pointer: str) -> tuple[str, ...]:
    if not pointer.startswith("/"):
        raise ValueError("nonempty_rfc6901_pointer_required")
    parts = pointer[1:].split("/")
    if any(re.search(r"~(?![01])", part) for part in parts):
        raise ValueError("invalid_json_pointer_escape")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in parts)


def _leaf_span(text: str, pointer: str) -> tuple[int, int, Any]:
    """Locate the exact selected token without rewriting the surrounding JSON."""
    target = _pointer_parts(pointer)
    # Validate the complete artifact, including duplicate keys outside the path.
    _DECODER.decode(text)
    matches: list[tuple[int, int, Any]] = []

    def whitespace(offset: int) -> int:
        while offset < len(text) and text[offset] in " \t\r\n":
            offset += 1
        return offset

    def visit(offset: int, path: tuple[str, ...]) -> int:
        offset = whitespace(offset)
        start = offset
        if text[offset] == "{":
            offset = whitespace(offset + 1)
            while text[offset] != "}":
                key, offset = _DECODER.raw_decode(text, offset)
                offset = whitespace(offset)
                if text[offset] != ":":
                    raise ValueError("json_object_colon_missing")
                offset = whitespace(visit(offset + 1, (*path, key)))
                if text[offset] == "}":
                    break
                offset = whitespace(offset + 1)
            offset += 1
        elif text[offset] == "[":
            offset = whitespace(offset + 1)
            index = 0
            while text[offset] != "]":
                offset = whitespace(visit(offset, (*path, str(index))))
                index += 1
                if text[offset] == "]":
                    break
                offset = whitespace(offset + 1)
            offset += 1
        else:
            _, offset = _DECODER.raw_decode(text, offset)
        if path == target:
            value, end = _DECODER.raw_decode(text, start)
            if end != offset:
                raise ValueError("json_span_reconciliation_failed")
            matches.append((start, offset, value))
        return offset

    visit(0, ())
    if len(matches) != 1:
        raise ValueError("mutation_identity_absent_or_ambiguous")
    return matches[0]


def run_probe(
    *, artifact: Path, checker_module: str, pointer: str, replacement: object,
    checker_args: list[str], timeout_seconds: float, root: Path | None = None,
) -> dict[str, Any]:
    """Run one bounded real checker against only a surgically changed leaf."""
    root = (root or Path.cwd()).resolve()
    if artifact.is_absolute():
        raise ValueError("artifact_must_be_relative_to_repo_root")
    path = (root / artifact).resolve()
    if not path.is_relative_to(root):
        raise ValueError("artifact_escapes_repo_root")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", checker_module):
        raise ValueError("checker_must_be_a_python_module")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_must_be_positive_and_finite")
    original = path.read_bytes()
    text = original.decode("utf-8")
    start, end, previous = _leaf_span(text, pointer)
    if type(previous) not in (bool, int, float) or type(replacement) not in (bool, int, float):
        raise ValueError("decisive_leaf_must_be_boolean_or_numeric")
    if (type(previous) is bool) != (type(replacement) is bool):
        raise ValueError("boolean_numeric_type_substitution_forbidden")
    replacement_token = json.dumps(replacement, allow_nan=False)
    if previous == replacement:
        raise ValueError("replacement_does_not_change_the_decisive_value")
    corrupted_text = text[:start] + replacement_token + text[end:]
    _DECODER.decode(corrupted_text)
    corrupted = corrupted_text.encode("utf-8")
    command = [sys.executable, "-m", checker_module, *checker_args]
    started = time.monotonic()
    timed_out = False
    returncode: int | None = None
    stdout = stderr = ""
    launch_error: str | None = None
    try:
        path.write_bytes(corrupted)
        try:
            child = subprocess.Popen(  # noqa: S603 - explicit local checker module/argv.
                command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True,
            )
            try:
                stdout, stderr = child.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Only this probe's process group is stopped; drain complete
                # output before restoring bytes and returning the nonreceipt.
                os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate()
            returncode = child.returncode
        except OSError as exc:
            launch_error = repr(exc)
    finally:
        path.write_bytes(original)
    restored = path.read_bytes()
    return {
        "artifact": str(artifact), "mutation_path": pointer,
        "original_value": previous, "mutated_value": replacement,
        "only_selected_token_changed": (
            corrupted_text[:start] == text[:start]
            and corrupted_text[start + len(replacement_token):] == text[end:]
        ),
        "argv": command, "cwd": str(root), "returncode": returncode,
        "timeout_seconds": timeout_seconds, "timed_out": timed_out,
        "launch_error": launch_error,
        "disposition": "harness_nonreceipt" if timed_out or launch_error else "completed",
        "elapsed_seconds": time.monotonic() - started,
        "stdout": stdout, "stderr": stderr,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "corrupted_sha256": hashlib.sha256(corrupted).hexdigest(),
        "restored_sha256": hashlib.sha256(restored).hexdigest(),
        "byte_identical_restoration": original == restored,
    }


def main() -> None:
    """Emit complete deciding output; a timeout never counts as a refused gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("checker_module")
    parser.add_argument("pointer")
    parser.add_argument("replacement_json")
    parser.add_argument("--checker-arg", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--expected-returncode", type=int, default=1)
    parser.add_argument("--expect-issue-code", action="append", default=[])
    args = parser.parse_args()
    evidence = run_probe(
        artifact=args.artifact, checker_module=args.checker_module, pointer=args.pointer,
        replacement=_DECODER.decode(args.replacement_json), checker_args=args.checker_arg,
        timeout_seconds=args.timeout_seconds,
    )
    issue_codes: set[str] | None = None
    if args.expect_issue_code and evidence["disposition"] == "completed":
        try:
            output = evidence["stdout"]
            report = json.loads(output[output.rfind("\n{") + 1:])
            issue_codes = {item["code"] for item in report["issues"]}
        except (ValueError, KeyError, TypeError):
            evidence["issue_output_not_established"] = True
    evidence["observed_issue_codes"] = sorted(issue_codes) if issue_codes is not None else None
    evidence["expected_returncode"] = args.expected_returncode
    evidence["expected_issue_codes"] = sorted(set(args.expect_issue_code))
    passed = (
        evidence["disposition"] == "completed"
        and evidence["returncode"] == args.expected_returncode
        and evidence["byte_identical_restoration"]
        and evidence["only_selected_token_changed"]
        and (not args.expect_issue_code or issue_codes == set(args.expect_issue_code))
    )
    evidence["probe_passed"] = passed
    sys.stdout.write(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
