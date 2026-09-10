"""Independent, confined TSV grader for the acquisition contract-testing corpus.

This program is separately authored from the subject adapter. It shares no
project imports, JSON decoder, fixture loader, or comparison implementation with
AQ1 or the assurance subject. Only the serialized observation protocol crosses
the process boundary. Its exact expectation digest is appointed by the calling
assurance instrument, never recomputed as a substitute for that trust input.
Institutional appointments and general policy assurance are outside its purpose.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import sys
from collections.abc import Callable
from pathlib import Path

FIELDS = (
    "case_id", "shape", "types", "state", "terminal", "ceiling", "authority",
    "signer", "reentry", "event", "reason",
)
RESEARCH_CASE_TOTAL = 63


class OracleRefusalError(ValueError):
    """The independent program cannot issue a conformance judgment."""


def _rows(text: str) -> dict[str, tuple[str, ...]]:
    """Decode the separate wire format and reject incomplete/duplicate records."""
    reader = csv.reader(io.StringIO(text), delimiter="\t", strict=True)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise OracleRefusalError("oracle_header_missing") from exc
    if tuple(header) != FIELDS:
        raise OracleRefusalError("oracle_protocol_header_mismatch")
    result: dict[str, tuple[str, ...]] = {}
    for line, row in enumerate(reader, start=2):
        if len(row) != len(FIELDS) or any(not value for value in row):
            raise OracleRefusalError(f"oracle_unreadable_record:{line}")
        if any("\n" in value or "\r" in value or "\t" in value for value in row):
            raise OracleRefusalError(f"oracle_nested_record:{line}")
        if row[0] in result:
            raise OracleRefusalError("oracle_duplicate_case:" + row[0])
        result[row[0]] = tuple(row)
    return result


def _confine(expected_path: Path) -> None:
    """Deny dependencies and reads outside the appointed oracle artifact.

    The interpreter is already isolated and all required stdlib code is loaded.
    Denying subsequent imports includes a shared stdlib JSON decoder, not merely
    names under a project prefix. No source path or callback enters the grader.
    """
    allowed = os.fspath(expected_path)

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event == "open":
            target, mode, flags = args
            if not isinstance(target, (str, bytes, os.PathLike)):
                raise PermissionError("oracle_boundary:descriptor_open")
            actual = os.path.realpath(os.fsdecode(target))
            writing = isinstance(mode, str) and any(char in mode for char in "wax+")
            writing = writing or bool(int(flags) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            if actual != allowed or writing:
                raise PermissionError("oracle_boundary:read_or_write")
        elif event == "import":
            raise PermissionError("oracle_boundary:shared_import")
        elif event in {"compile", "exec", "subprocess.Popen", "os.system", "os.fork"}:
            raise PermissionError("oracle_boundary:execution")
        elif event.startswith("socket.") or event.startswith("ctypes."):
            raise PermissionError("oracle_boundary:external_capability")

    sys.addaudithook(audit)


def _must_be_denied(action: Callable[[], object], property_name: str) -> None:
    """Exercise denied capability; an absent resource is not a passing probe."""
    try:
        action()
    except PermissionError as exc:
        if not str(exc).startswith("oracle_boundary:"):
            raise OracleRefusalError("oracle_unexpected_denial:" + property_name) from exc
        return
    except Exception as exc:
        raise OracleRefusalError("oracle_isolation_probe_unestablished:" + property_name) from exc
    raise OracleRefusalError("oracle_isolation_not_enforced:" + property_name)


def _compare(expected: dict[str, tuple[str, ...]], observed: dict[str, tuple[str, ...]]) -> int:
    """Compare every independently sealed semantic field and the complete ID set."""
    failures = 0
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(("case_id", "field", "expected", "observed"))
    for case in sorted(expected.keys() | observed.keys()):
        if case not in expected or case not in observed:
            writer.writerow((case, "membership", str(case in expected), str(case in observed)))
            failures += 1
            continue
        for index, field in enumerate(FIELDS[1:], start=1):
            left, right = expected[case][index], observed[case][index]
            if left != right:
                writer.writerow((case, field, left, right))
                failures += 1
    writer.writerow(("ORACLE_FAIL", failures) if failures else ("ORACLE_PASS", len(expected)))
    return 1 if failures else 0


def main() -> int:
    """Run isolated capability challenges, sealed parsing, and exact comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--challenge", choices=("decoder", "loader", "comparator", "unconfined"))
    args = parser.parse_args()
    try:
        if not sys.flags.isolated or not sys.flags.no_site:
            raise OracleRefusalError("oracle_isolated_interpreter_required")
        if "json" in sys.modules or any(name.startswith("polisyos") for name in sys.modules):
            raise OracleRefusalError("oracle_shared_decoder_already_loaded")
        expected_path = args.expectations.resolve()
        project = Path(__file__).resolve().parents[3]
        subject = project / "src/polisyos/fabric/evidence/non_data_acquisition.py"
        corpus = project / "docs/reference/gy-acquisition-assurance-corpus.json"
        if expected_path != project / "docs/reference/gy-acquisition-assurance-oracle.tsv":
            raise OracleRefusalError("oracle_expectation_owner_path_mismatch")
        if args.challenge != "unconfined":
            _confine(expected_path)
        # This is an existing readable subject, not a fabricated missing path.
        # Removing the boundary permits this read, and necessarily refuses a grade.
        _must_be_denied(subject.read_bytes, "subject_read")
        _must_be_denied(lambda: __import__("json"), "shared_decoder")
        if args.challenge:
            if args.challenge == "decoder":
                def action() -> object:
                    return __import__("json")
            elif args.challenge == "loader":
                action = corpus.read_bytes
            else:
                def action() -> object:
                    return __import__("polisyos.fabric.evidence.acquisition_assurance")
            _must_be_denied(action, args.challenge)
            raise OracleRefusalError("oracle_shared_dependency_refused:" + args.challenge)
        blob = expected_path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != args.expected_sha256:
            raise OracleRefusalError("oracle_expectation_seal_mismatch")
        expected = _rows(blob.decode("utf-8"))
        if len(expected) != RESEARCH_CASE_TOTAL:
            raise OracleRefusalError("oracle_research_denominator_mismatch")
        return _compare(expected, _rows(sys.stdin.read()))
    except (OracleRefusalError, PermissionError, UnicodeError, csv.Error) as exc:
        print("ORACLE_ERROR\t" + str(exc))  # noqa: T201
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
