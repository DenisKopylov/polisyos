"""Read back the retained E02 runtime-fixture evidence without running product tests."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SCRIPT = Path(__file__).resolve()
REPO = Path(
    subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=SCRIPT.parent, text=True
    ).strip()
)
A_HANDOFF = REPO / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/A"
REPORT_PATH = A_HANDOFF / "runtime-fixture-validation.json"
MANIFEST_PATH = A_HANDOFF / "runtime-fixture-validation/source-hashes.json"
SUMMARY = re.compile(
    r"(?:(?P<failed>\d+) failed,\s*)?(?P<passed>\d+) passed"
    r"(?:,\s*\d+ warnings?)?(?:,\s*(?P<errors>\d+) errors?)?"
)


def sha256(path: Path) -> tuple[int, str]:
    content = path.read_bytes()
    return len(content), hashlib.sha256(content).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=REPO)


def outcome_counts(path: Path) -> tuple[Counter[str], Counter[str]]:
    root = ET.parse(path).getroot()
    totals: Counter[str] = Counter()
    by_file: Counter[str] = Counter()
    for case in root.iter("testcase"):
        status = "passed"
        for tag, label in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            if case.find(tag) is not None:
                status = label
                break
        totals[status] += 1
        classname = case.get("classname", "")
        filepath = "policy-engine/" + classname.replace(".", "/") + ".py"
        by_file[filepath + "|" + status] += 1
    return totals, by_file


def main() -> int:
    report = json.loads(REPORT_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    failures: list[str] = []
    wave_outputs: list[str] = []

    fixture_paths: set[str] = set()
    for commit in manifest["fixture_implementation_commits"]:
        rows = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit["sha"])
        fixture_paths.update(line for line in rows.splitlines() if line)
    expected_fixture_paths = set(manifest["fixture_source_path_census"]["paths"])
    if fixture_paths != expected_fixture_paths:
        failures.append("fixture source path census differs from committed change set")

    source_tree_paths = set(
        git("diff-tree", "--no-commit-id", "--name-only", "-r", manifest["source_facade_dependency"]["sha"]).splitlines()
    )
    expected_dependency_paths = {row["path"] for row in manifest["source_facade_dependency"]["files"]}
    if source_tree_paths != expected_dependency_paths:
        failures.append("source facade dependency path census mismatch")

    for row in manifest["fixture_candidate_source_files"]:
        blob = git("rev-parse", f"{report['candidate_sha']}:{row['path']}")
        content = git_bytes("show", f"{report['candidate_sha']}:{row['path']}")
        if blob != row["git_blob_at_candidate"] or hashlib.sha256(content).hexdigest() != row["sha256_at_candidate"]:
            failures.append(f"candidate fixture source hash mismatch: {row['path']}")
    for row in manifest["source_facade_dependency"]["files"]:
        blob = git("rev-parse", f"{manifest['source_facade_dependency']['sha']}:{row['path']}")
        content = git_bytes("show", f"{manifest['source_facade_dependency']['sha']}:{row['path']}")
        if blob != row["git_blob_at_commit"] or hashlib.sha256(content).hexdigest() != row["sha256_at_commit"]:
            failures.append(f"source facade dependency hash mismatch: {row['path']}")

    for wave in report["historical_waves"]:
        artifacts = wave["artifacts"]
        for name, artifact in artifacts.items():
            copied = REPO / artifact["path"]
            original = REPO / artifact["source_build_path"]
            copied_size, copied_sha = sha256(copied)
            source_size, source_sha = sha256(original)
            expected = (artifact["bytes"], artifact["sha256"])
            if (copied_size, copied_sha) != expected or (source_size, source_sha) != expected:
                failures.append(f"artifact bytes/hash mismatch for {wave['candidate_sha']} {name}")
        junit_path = REPO / artifacts["junit.xml"]["path"]
        stdout_path = REPO / artifacts["stdout.txt"]["path"]
        junit_totals, junit_files = outcome_counts(junit_path)
        if dict(junit_totals) != wave["junit_outcome_counts"] or sum(junit_totals.values()) != wave["junit_case_count"]:
            failures.append(f"JUnit count mismatch for {wave['candidate_sha']}")
        expected_files = Counter()
        for row in wave["junit_file_denominator"]:
            for status, count in row["outcomes"].items():
                expected_files[row["path"] + "|" + status] = count
        if expected_files != junit_files:
            failures.append(f"JUnit per-file denominator mismatch for {wave['candidate_sha']}")
        stdout = stdout_path.read_text(errors="replace")
        summaries = list(SUMMARY.finditer(stdout))
        if not summaries:
            failures.append(f"pytest summary not found in stdout for {wave['candidate_sha']}")
            continue
        match = summaries[-1]
        stdout_totals = {
            "passed": int(match.group("passed")),
            "failed": int(match.group("failed") or 0),
            "error": int(match.group("errors") or 0),
        }
        expected_totals = {
            "passed": wave["junit_outcome_counts"].get("passed", 0),
            "failed": wave["junit_outcome_counts"].get("failed", 0),
            "error": wave["junit_outcome_counts"].get("error", 0),
        }
        if stdout_totals != expected_totals:
            failures.append(f"pytest stdout/JUnit outcome mismatch for {wave['candidate_sha']}")
        env = json.loads((REPO / artifacts["environment-and-inputs.json"]["path"]).read_text())
        if env["candidate_sha"] != wave["candidate_sha"] or env["candidate_tree_sha"] != wave["candidate_tree_sha"]:
            failures.append(f"environment candidate identity mismatch for {wave['candidate_sha']}")
        wave_outputs.append(
            f"{wave['candidate_sha'][:12]} stdout/JUnit {stdout_totals} over {sum(junit_totals.values())} cases"
        )

    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1
    print(
        "PASS git fixture path census: "
        f"{len(expected_fixture_paths)} paths / {manifest['fixture_source_path_census']['file_type_denominator']}"
    )
    print(
        "PASS source dependency path census: "
        f"{len(expected_dependency_paths)} paths / {manifest['source_facade_dependency']['file_type_denominator']}"
    )
    print("PASS Git blob/content hashes for fixture and dependency source inputs")
    for output in wave_outputs:
        print("PASS", output)
    print("PASS byte-for-byte source-to-companion copies for all retained environment/stdout/stderr/JUnit files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
