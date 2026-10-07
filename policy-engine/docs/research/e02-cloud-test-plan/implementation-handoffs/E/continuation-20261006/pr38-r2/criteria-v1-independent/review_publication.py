#!/usr/bin/env python3
"Independent Git-publication and unchanged-output controls; no source edits."

import argparse
import copy
import hashlib
import json
import pathlib
import platform
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(repo: object, *args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(repo), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def digest(payload: object) -> dict[str, object]:
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--snapshot", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    revision = "b5ba9b2e3af3b6702235f3320bf705b8141fda24"
    correction_sha = git(args.repo, "rev-parse", "6994b1f4a").decode().strip()
    prior_sha = git(args.repo, "rev-parse", "6994b1f4a^").decode().strip()
    main_sha = git(args.repo, "rev-parse", "origin/main").decode().strip()
    base = (
        "policy-engine/docs/research/e02-cloud-test-plan/implementati"
        "on-handoffs/E/continuation-20261006/pr38-r2/"
    )
    validator = args.snapshot / "validate_review_copies.py"
    records_path = args.snapshot / "independent-reviews/copy-index.json"
    validator_data = validator.read_bytes()
    require(
        validator_data
        == git(args.repo, "show", revision + ":" + base + "validate_review_copies.py"),
        "validator snapshot differs from admitted Git source",
    )
    records_data = records_path.read_bytes()
    require(
        records_data
        == git(
            args.repo,
            "show",
            revision + ":" + base + "independent-reviews/copy-index.json",
        ),
        "copy index snapshot differs from admitted Git source",
    )
    records = json.loads(records_data)["records"]
    current = runpy.run_path(str(validator))
    current["validate"](args.repo, records, revision)
    controls = []
    for field, value in [("sha256", "0" * 64), ("bytes", records[0]["bytes"] + 1)]:
        corrupted = copy.deepcopy(records)
        corrupted[0][field] = value
        try:
            current["validate"](args.repo, corrupted, revision)
        except ValueError as exc:
            controls.append(
                {
                    "control": "actual_154_copy_" + field,
                    "state": "REJECTED",
                    "reason": str(exc),
                }
            )
        else:
            raise AssertionError("negative accepted:" + field)
    try:
        current["validate"](args.repo, records, main_sha)
    except ValueError as exc:
        controls.append(
            {
                "control": "actual_origin_main_unpublished",
                "state": "REJECTED",
                "source_sha": main_sha,
                "reason": str(exc),
                "local_files_unchanged": True,
            }
        )
    else:
        raise AssertionError("Main-unpublished negative accepted")

    correction_data = git(
        args.repo, "show", revision + ":" + base + "output-publication-correction.json"
    )
    correction = json.loads(correction_data)
    require(len(correction["current_copies"]) == 15, "corrective output denominator drift")
    old_index = json.loads(
        git(
            args.repo,
            "show",
            prior_sha + ":" + base + "independent-reviews/copy-index.json",
        )
    )["records"]
    old_by_path = {record["copied_path"]: record for record in old_index}
    current_by_path = {record["copied_path"]: record for record in records}
    details = []
    old_subset = []
    for record in correction["current_copies"]:
        published = git(args.repo, "show", correction_sha + ":" + record["published_path"])
        old_local = (args.repo / record["old_path"]).read_bytes()
        require(
            published == old_local,
            "published bytes differ from preserved historical ignored stdout",
        )
        require(
            digest(published) == {"bytes": record["bytes"], "sha256": record["sha256"]},
            "published corrective bytes/hash differ",
        )
        require(
            digest(published)
            == {
                "bytes": old_by_path[record["old_path"]]["bytes"],
                "sha256": old_by_path[record["old_path"]]["sha256"],
            },
            "historical old index does not bind published bytes",
        )
        current_row = current_by_path[record["published_path"]]
        require(
            current_row["historical_ignored_copy_path"] == record["old_path"],
            "historical ignored path identity lost",
        )
        require(
            digest(published) == {"bytes": current_row["bytes"], "sha256": current_row["sha256"]},
            "current copy index differs from corrective publication",
        )
        old_object = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(args.repo),
                "cat-file",
                "-e",
                prior_sha + ":" + record["old_path"],
            ],
            capture_output=True,
            check=False,
        )
        require(
            old_object.returncode != 0,
            "historical ignored output was unexpectedly published",
        )
        old_subset.append(old_by_path[record["old_path"]])
        details.append(
            {
                **record,
                "old_local_full_stdout_preserved": True,
                "same_bytes_in_corrective_Git_commit": True,
                "old_Git_object_unavailable": True,
            }
        )

    old_validator_data = git(
        args.repo, "show", revision + "^:" + base + "validate_review_copies.py"
    )
    old_namespace = {"__name__": "old_exact_validator_read_only"}
    exec(  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
        compile(old_validator_data, "exact_b5_parent_validate_review_copies.py", "exec"),
        old_namespace,
    )
    old_namespace["validate"](args.repo, old_subset)
    try:
        current["validate"](args.repo, old_subset, prior_sha)
    except ValueError as exc:
        controls.append(
            {
                "control": "Git_availability_property_removed_old_exact_validator",
                "state": "DETECTED",
                "same_bytes_metadata_and_15_local_files": True,
                "old_validator_source": git(args.repo, "rev-parse", revision + "^")
                .decode()
                .strip(),
                "old_validator_outcome": "PASS_local_only_despite_15_unpublished_Git_paths",
                "current_validator_outcome": "REJECTED_unpublished",
                "reason": str(exc),
            }
        )
    else:
        raise AssertionError("Git property removal not detected")
    output = {
        "schema": "policyos.e02.independent-review-publication.v1",
        "reviewer": "root/ddm_r2",
        "scope": (
            "Exact b5 copy validator and699 stdout publication correction"
            "; no product/numerical changes or new wave inferred"
        ),
        "source_revision": revision,
        "source_tree": git(args.repo, "rev-parse", revision + "^{tree}").decode().strip(),
        "validator_snapshot": {"path": str(validator), **digest(validator_data)},
        "copy_index_snapshot": {"path": str(records_path), **digest(records_data)},
        "actual_Git_bound_copy_count": len(records),
        "actual_origin_main_source": main_sha,
        "output_correction_sha": correction_sha,
        "output_correction_ref": {
            "path": base + "output-publication-correction.json",
            **digest(correction_data),
        },
        "actual_corrected_stdout_count": len(details),
        "actual_corrected_stdout_bytes": sum(record["bytes"] for record in details),
        "corrected_stdout_details": details,
        "negative_controls": controls,
        "bounded_verdict": "GO_Git_object_availability_and_same_bytes_publication",
        "scientific_result_change": False,
        "source_runtime_tests": "UNRUN_by_design; documentation/verification mechanism only",
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "executable": sys.executable,
            "no_process_thread_CPU_caps_added": True,
        },
        "cleanup": (
            "All original ignored stdout files preserved; no source edits"
            ", no deletion, no new environment."
        ),
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    _write_stdout(
        json.dumps(
            {
                "copies": len(records),
                "corrected_stdout": len(details),
                "corrected_bytes": sum(record["bytes"] for record in details),
                "negative_controls": controls,
                "verdict": output["bounded_verdict"],
            }
        )
    )


if __name__ == "__main__":
    main()
