"""Metadata-only review-carrier corruption and effective-removal controls."""

from __future__ import annotations

import ast
import hashlib
import json
import runpy
import sys
from copy import deepcopy
from pathlib import Path

OUT = Path(__file__).parent
SOURCE = OUT / "adapt_publication_freeze.py"


def remove_predicate(function_name: str, destination: Path) -> dict:
    text = SOURCE.read_text()
    tree = ast.parse(text)
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name
    )
    if len(function.body) != 1 or not isinstance(function.body[0], ast.If):
        raise AssertionError("exact one-function predicate shape changed")
    conditional = function.body[0]
    lines = text.splitlines(keepends=True)
    repaired = [
        *lines[: conditional.lineno - 1],
        "    return None\n",
        *lines[conditional.end_lineno :],
    ]
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("preserve previous predicate-removal source")
    destination.write_text("".join(repaired))
    return runpy.run_path(str(destination), run_name="author_effective_metadata_removal")


def main() -> int:
    module = runpy.run_path(str(SOURCE), run_name="author_review_carrier_controls")
    original_digest = hashlib.sha256(module["ORIGINAL"].read_bytes()).hexdigest()
    carrier = json.loads(module["PUBLICATION"].read_text())
    module["validate_carrier"](carrier)
    rows = [
        {"control": "original8 equals exact6Git plus2external complete reviews", "outcome": "BOUND"}
    ]
    mutations = [
        (
            "external review content digest corrupted",
            lambda c: c["external_content_bound_reviews"][0]["record"].update(sha256="0" * 64),
        ),
        (
            "external review content byte count corrupted",
            lambda c: c["external_content_bound_reviews"][0]["record"].update(bytes=1),
        ),
        (
            "external declared source pin replaced by valid historical5e",
            lambda c: c["external_content_bound_reviews"][0].update(
                source_sha="5e3e3727685132f270a3a07b9f63dd962a88cd96"
            ),
        ),
        (
            "external original freeze digest corrupted",
            lambda c: c["external_content_bound_reviews"][0]["original_freeze_binding"].update(
                sha256="0" * 64
            ),
        ),
        ("external review omitted", lambda c: c["external_content_bound_reviews"].pop()),
        ("candidate Git review omitted", lambda c: c["reviews"].pop()),
        (
            "external role disguised as candidate Git",
            lambda c: c["external_content_bound_reviews"][0].update(role="candidate_git_review"),
        ),
        (
            "external path aliases raw/private payload",
            lambda c: c["external_content_bound_reviews"][0]["record"].update(
                path=str(OUT / "raw" / "sentinel.json")
            ),
        ),
        (
            "source frozen timestamp changed",
            lambda c: c.update(frozen_at_utc="2026-10-07T00:00:00Z"),
        ),
        ("closure upgraded by representation", lambda c: c.update(closure_ratified=True)),
        (
            "external count metadata forged",
            lambda c: c["publication_representation"].update(external_content_bound_review_count=0),
        ),
    ]
    for label, mutate in mutations:
        changed = deepcopy(carrier)
        mutate(changed)
        try:
            module["validate_carrier"](changed)
        except module["CarrierAdmissionError"] as error:
            rows.append({"control": label, "outcome": "TYPED_REFUSAL", "reason": str(error)})
        else:
            raise AssertionError(label)
    for name, index in [("admit_source_pin", 2), ("admit_origin_binding", 3)]:
        removed = remove_predicate(name, OUT / (name + "_predicate_removed.py.txt"))
        changed = deepcopy(carrier)
        label, mutate = mutations[index]
        mutate(changed)
        removed["validate_carrier"](changed)
        rows.append(
            {"control": label + " with only shared predicate removed", "outcome": "REACCEPTED"}
        )
    path_root = OUT / "synthetic-path-controls"
    path_root.mkdir(exist_ok=False)
    ordinary = path_root / "public" / "sentinel.json"
    ordinary.parent.mkdir()
    ordinary.write_text('{"synthetic_metadata":true}\n')
    for component in ("raw", "PRIVATE", "git-config-private"):
        path = path_root / component / "sentinel.json"
        path.parent.mkdir()
        path.write_text('{"synthetic_metadata":true}\n')
        try:
            module["public_path"](path)
        except RuntimeError as error:
            rows.append(
                {
                    "control": "full public role " + component,
                    "outcome": "TYPED_REFUSAL",
                    "reason": str(error),
                }
            )
        else:
            raise AssertionError(component)
    alias = path_root / "leaf-alias.json"
    alias.symlink_to(ordinary)
    try:
        module["public_path"](alias)
    except RuntimeError as error:
        rows.append(
            {
                "control": "external public leaf symlink",
                "outcome": "TYPED_REFUSAL",
                "reason": str(error),
            }
        )
    else:
        raise AssertionError("external symlink")
    if hashlib.sha256(module["ORIGINAL"].read_bytes()).hexdigest() != original_digest:
        raise AssertionError("original freeze changed")
    result = {
        "scope": (
            "Author metadata-only adapter controls; no product/native/numeric/gate commands "
            "or private payload reads/copies"
        ),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "original_freeze_unchanged": True,
        "checks": rows,
    }
    encoded = json.dumps(result, indent=2) + "\n"
    destination = OUT / "adapter-controls.json"
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("preserve prior results")
    destination.write_text(encoded)
    sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
