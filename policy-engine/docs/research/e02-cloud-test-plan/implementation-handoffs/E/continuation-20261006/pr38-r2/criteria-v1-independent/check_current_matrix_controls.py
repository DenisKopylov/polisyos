#!/usr/bin/env python3
"""Repeat the three bounded matrix controls without mutating ready files."""

import argparse
import copy
import hashlib
import json
import pathlib
import runpy
import sys


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--packet-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    paths = [
        args.packet_dir / name
        for name in [
            "all-54-update.json",
            "input-index.json",
            "validate.py",
            "current-local-G-recipes.json",
        ]
    ]
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    packet = json.loads(paths[0].read_text())
    inputs = json.loads(paths[1].read_text())
    recipes = json.loads(paths[3].read_text())
    check = runpy.run_path(str(paths[2]))["check"]
    recipe_gate = runpy.run_path(
        str(pathlib.Path(__file__).with_name("validate_independently_f445.py"))
    )["current_recipe_gate"]
    check(packet, inputs, args.repo)
    recipe_gate(packet, recipes)
    controls = []
    for name in [
        "hide_available_Welfare_code",
        "closed_B198_relabel_proposal",
        "stale58_recipe_under_current_marker",
    ]:
        modified = copy.deepcopy(packet)
        modified_recipes = copy.deepcopy(recipes)
        if name == "hide_available_Welfare_code":
            next(r for r in modified["rows"] if r["id"] == "B194")[
                "implementation_residual_or_external_boundary"
            ] = "Only external source authority hold; no code work"
        elif name == "closed_B198_relabel_proposal":
            next(r for r in modified["rows"] if r["id"] == "B198")["next_verifiable_result"] = (
                "Submit new closure proposal for owner acceptance"
            )
        else:
            modified_recipes["implementation_sha"] = "58e2d97965c0826c44843a78dcb2f8698d9950a3"
        try:
            check(modified, inputs, args.repo)
            recipe_gate(modified, modified_recipes)
        except ValueError as exc:
            controls.append({"control": name, "state": "REJECTED", "reason": str(exc)})
        else:
            raise AssertionError("Corrupt matrix control accepted: " + name)
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if not (before == after):
        raise AssertionError("Ready files changed during read-only review")
    result = {
        "schema": "policyos.e02.independent-current-matrix-controls.v1",
        "source_sha": packet["assembled_source_sha"],
        "packet_publication": "b5ba9b2e3af3b6702235f3320bf705b8141fda24",
        "negative_controls": controls,
        "ready_bytes_preserved": before == after,
        "classification": "Matrix/provenance controls only; no runtime wave evidence",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    _write_stdout(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
