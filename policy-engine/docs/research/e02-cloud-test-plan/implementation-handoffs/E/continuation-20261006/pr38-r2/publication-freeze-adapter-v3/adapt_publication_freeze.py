"""Preserve all freeze reviews while distinguishing Git and external carriers."""

from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

REPO = Path("/workspace/e02-E-continuation-20261006")
ORIGINAL = Path("/workspace/e02-E-pr38-r2-receipts/source-freeze-a9f78817c.json")
PUBLICATION = Path("/workspace/e02-E-pr38-r2-receipts/publication-freeze-a9f78817c-v3.json")
CURRENT_SHA = "a9f78817c873be5b35a08155f2593b229d9fdbb6"
CURRENT_TREE = "c02e043c3e1c8222c28aa71187fa8db4e2fdeea7"
ORIGINAL_BYTES = 6358
ORIGINAL_SHA256 = "f90129331279070984ccd9cd93da217633c9f734086c3a6213e6b4d7ca9311c4"
COLLECTOR = REPO / (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/"
    "continuation-20261006/pr38-r2/wave-controls/collect_wave.py"
)
COLLECTOR_SHA256 = "faecae68f9eecc741e12ae1469fcd57faad11a9facb747f2430762da1758f9fc"
PIN_KEYS = {
    "/workspace/e02-E-pr38-r2-receipts/g-checkpoint11-assembly-a9f78817/"
    "independent-G11-assembly-review-a9f78817.json": ("candidate", "tree"),
    "/workspace/e02-E-pr38-r2-receipts/independent-g-checkpoint11-a9/review.json": (
        "candidate_sha",
        "candidate_tree",
    ),
}


class CarrierAdmissionError(ValueError):
    """Reject review loss, ambiguous roles, changed source or broken content."""


def public_path(path: Path) -> Path:
    value = COLLECTOR.read_bytes()
    if hashlib.sha256(value).hexdigest() != COLLECTOR_SHA256:
        raise CarrierAdmissionError("canonical public-path admission source changed")
    helpers = runpy.run_path(str(COLLECTOR), run_name="publication_metadata_admission")
    return helpers["public_evidence"](path.parent.resolve(), path)


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


def git_bytes(*arguments: str) -> bytes:
    _admit_git_object_arguments(arguments)
    executable = shutil.which("git")
    if executable is None:
        raise FileNotFoundError("Git unavailable")
    command = [str(Path(executable).resolve()), "-C", str(REPO), *arguments]
    # Fixed metadata verbs, exact frozen SHA and admitted tracked review paths.
    return subprocess.check_output(command)  # noqa: S603


def original_binding() -> dict:
    return {"path": str(ORIGINAL), "bytes": ORIGINAL_BYTES, "sha256": ORIGINAL_SHA256}


def load_original() -> dict:
    value = public_path(ORIGINAL).read_bytes()
    if len(value) != ORIGINAL_BYTES or hashlib.sha256(value).hexdigest() != ORIGINAL_SHA256:
        raise CarrierAdmissionError("original frozen receipt changed")
    return json.loads(value)


def admit_source_pin(sha: str, tree: str) -> None:
    if sha != CURRENT_SHA or tree != CURRENT_TREE:
        raise CarrierAdmissionError("external review current source pin mismatch")


def admit_origin_binding(binding: dict) -> None:
    if binding != original_binding():
        raise CarrierAdmissionError("external carrier original freeze binding mismatch")


def build_carrier() -> dict:
    original = load_original()
    carrier = deepcopy(original)
    carrier["reviews"] = [r for r in original["reviews"] if not Path(r["path"]).is_absolute()]
    carrier["external_content_bound_reviews"] = [
        {
            "role": "external_content_bound_independent_review",
            "source_sha": CURRENT_SHA,
            "source_tree": CURRENT_TREE,
            "original_freeze_binding": original_binding(),
            "record": deepcopy(record),
        }
        for record in original["reviews"]
        if Path(record["path"]).is_absolute()
    ]
    carrier["publication_representation"] = {
        "schema": "e02.E.publication-freeze-carrier.v3",
        "kind": "review_input_role_correction_only",
        "original_freeze_binding": original_binding(),
        "original_review_count": 8,
        "candidate_git_review_count": 6,
        "external_content_bound_review_count": 2,
        "new_source_freeze": False,
        "canonical_collector_external_validation": False,
        "external_validator": "adapt_publication_freeze.py:validate_carrier",
    }
    return carrier


def validate_carrier(carrier: dict) -> None:
    original = load_original()
    if len(original["reviews"]) != 8:
        raise CarrierAdmissionError("original complete review denominator changed")
    expected_git = [r for r in original["reviews"] if not Path(r["path"]).is_absolute()]
    expected_external = [r for r in original["reviews"] if Path(r["path"]).is_absolute()]
    if carrier["reviews"] != expected_git or len(expected_git) != 6:
        raise CarrierAdmissionError("six candidate Git review records were changed or omitted")
    external = carrier["external_content_bound_reviews"]
    if len(external) != 2 or [r["record"] for r in external] != expected_external:
        raise CarrierAdmissionError("two external review records were changed or omitted")
    restored = deepcopy(carrier)
    restored.pop("external_content_bound_reviews")
    representation = restored.pop("publication_representation")
    restored["reviews"] = deepcopy(original["reviews"])
    if restored != original:
        raise CarrierAdmissionError("source/env/wave/closure/timestamp fields changed")
    if representation != build_carrier()["publication_representation"]:
        raise CarrierAdmissionError("typed representation role/count binding changed")
    admit_source_pin(carrier["frozen_sha"], carrier["tree"])
    if git_bytes("rev-parse", CURRENT_SHA + "^{tree}").decode().strip() != CURRENT_TREE:
        raise CarrierAdmissionError("candidate Git tree differs from source pin")
    for record in expected_git:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise CarrierAdmissionError("invalid candidate Git review path")
        public_path(REPO / relative)
        lookup = CURRENT_SHA + ":" + record["path"]
        value = git_bytes("show", lookup)
        blob = git_bytes("rev-parse", lookup).decode().strip()
        if (
            len(value) != record["bytes"]
            or hashlib.sha256(value).hexdigest() != record["sha256"]
            or blob != record["git_blob"]
        ):
            raise CarrierAdmissionError("candidate Git review integrity mismatch")
    for item in external:
        if set(item) != {"role", "source_sha", "source_tree", "original_freeze_binding", "record"}:
            raise CarrierAdmissionError("external carrier role fields changed")
        if item["role"] != "external_content_bound_independent_review":
            raise CarrierAdmissionError("external review role mismatch")
        admit_source_pin(item["source_sha"], item["source_tree"])
        admit_origin_binding(item["original_freeze_binding"])
        record = item["record"]
        path = public_path(Path(record["path"]))
        value = path.read_bytes()
        if len(value) != record["bytes"] or hashlib.sha256(value).hexdigest() != record["sha256"]:
            raise CarrierAdmissionError("external complete review content mismatch")
        data = json.loads(value)
        sha_key, tree_key = PIN_KEYS[str(path)]
        admit_source_pin(data[sha_key], data[tree_key])


def main() -> int:
    carrier = build_carrier()
    validate_carrier(carrier)
    public_path(PUBLICATION)
    if PUBLICATION.exists() or PUBLICATION.is_symlink():
        raise FileExistsError("preserve previous carrier output")
    with PUBLICATION.open("x") as stream:
        stream.write(json.dumps(carrier, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
