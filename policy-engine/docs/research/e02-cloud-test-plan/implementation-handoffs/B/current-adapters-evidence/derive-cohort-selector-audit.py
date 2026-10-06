"""Derive a draft whole-file B denominator from immutable Git bytes, never run tests."""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import hashlib
import io
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--equivalents", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(args.repo)
    sha = args.sha
    mapping_path = Path(args.equivalents)
    mapping_bytes = mapping_path.read_bytes()
    mapping = json.loads(mapping_bytes)

    git_executable = shutil.which("git")
    if git_executable is None or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("An existing Git executable and immutable SHA are required")

    def git(*xs: str) -> bytes:
        return subprocess.check_output([git_executable, ("-C"), str(repo), *xs])  # noqa: S603 - argv-only immutable Git reads

    tree = git("rev-parse", sha + "^{tree}").decode().strip()
    tracked = set(git("ls-tree", "-r", "--name-only", sha).decode().splitlines())
    cache = {}

    def data(path: str) -> bytes:
        if path not in cache:
            cache[path] = git("show", f"{sha}:{path}")
        return cache[path]

    def text(path: str) -> str:
        return data(path).decode()

    def identity(path: str) -> dict[str, str | int]:
        return {
            "path": path,
            "git_blob": git("rev-parse", f"{sha}:{path}").decode().strip(),
            "sha256": hashlib.sha256(data(path)).hexdigest(),
            "bytes": len(data(path)),
        }

    def rows(path: str) -> list[dict[str, str]]:
        return list(csv.DictReader(io.StringIO(text(path)), delimiter="\t"))

    prefix = "policy-engine/docs/research/e02-cloud-test-plan/"
    org = prefix + "execution-organization/"
    res = prefix + "results/"
    handoff = prefix + "implementation-handoffs/B/"
    owners = [x for x in rows(org + "finding-owners.tsv") if x["unit"] == "B"]
    ids = {x["finding_id"] for x in owners}
    bundles = [x["bundle_id"] for x in rows(org + "bundle-owners.tsv") if x["unit"] == "B"]
    coverage = json.loads(text(prefix + "closure-decisions/coverage.json"))
    cards = {x["id"]: x for x in coverage["bundles"] if x["unit"] == "B"}
    if len(ids) != 60 or len(bundles) != 25 or set(cards) != set(bundles):
        raise ValueError("Canonical B denominator must be all60 findings and25 bundles")
    pattern = re.compile(
        r"(?:policy-engine/)?tests/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_:.\[\]-]+)?"
    )

    def normalize(selector: str) -> str:
        p = selector.split("::")[0]
        return p.removeprefix("policy-engine/")

    sources = {}
    planned = {}
    commands = []
    all_commands = []
    driver_records = []
    receipt_manifest = []
    owner_dispositions = []

    def add(
        selector: str,
        kind: str,
        locator: str,
        bundle: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        p = normalize(selector)
        if not Path(p).name.startswith("test_"):
            return
        key = (kind, locator, selector, bundle)
        rows = sources.setdefault(p, {})
        if key not in rows:
            rows[key] = {
                "kind": kind,
                "locator": locator,
                "selector": selector,
                "bundle": bundle,
                **(details or {}),
            }

    def parse_native(
        value: object,
        locator: str,
        bundle_ids: list[str] | tuple[str, ...] = (),
        role: str = ("owner_recorded_command"),
    ) -> None:
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            argv = value
        elif isinstance(value, str):
            try:
                argv = shlex.split(value)
            except ValueError:
                return
        else:
            return
        is_pytest = any(x == "pytest" or x.endswith("/pytest") or x == "pytest.main" for x in argv)
        all_commands.append(
            {
                "locator": locator,
                "role": role,
                "argv": argv,
                "bundle_ids": list(bundle_ids),
                "native_pytest_argv": is_pytest,
                "grade": "complete recorded check-command lineage, no execution claim",
            }
        )
        if not is_pytest:
            return
        selectors = []
        for token in argv:
            # Options containing cache/output paths are not pytest selectors.
            if token.startswith("-"):
                continue
            selectors += pattern.findall(token)
        if not selectors:
            return
        commands.append(
            {
                "locator": locator,
                "role": role,
                "argv": argv,
                "selectors": selectors,
                "bundle_ids": list(bundle_ids),
            }
        )
        for selector in selectors:
            for bundle in bundle_ids or [None]:
                add(selector, role, locator, bundle)

    def walk(value: object, locator: str, bundle_ids: list[str] | tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if k in {
                    "command",
                    "argv",
                    "command_argv",
                    "native_command",
                    "native_argv",
                    "pytest_command",
                    "pytest_argv",
                    "replay_argv",
                }:
                    parse_native(v, locator + "/" + k, bundle_ids)
                if k in {"tool_run_record", "native_child"} and isinstance(v, str):
                    with contextlib.suppress(ValueError):
                        walk(json.loads(v), locator + "/" + k + "/decoded", bundle_ids)
                walk(v, locator + "/" + k, bundle_ids)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(v, locator + f"/{i}", bundle_ids)

    def json_references(value: object) -> list[str]:
        refs = []
        if isinstance(value, dict):
            p = value.get("path")
            if isinstance(p, str) and p in tracked and p.endswith((".json", ".py")):
                refs.append(p)
            for v in value.values():
                refs += json_references(v)
        elif isinstance(value, list):
            for v in value:
                refs += json_references(v)
        elif isinstance(value, str):
            for p in re.findall(
                (
                    "(?:/workspace/[^\\s\\\"\\']+/)?(policy-engine/docs/research/e02-cloud"
                    "-test-plan/implementation-handoffs/B/[A-Za-z0-9_./-]+\\.(?:json|py"
                    "))"
                ),
                value,
            ):
                if p in tracked:
                    refs.append(p)
        return refs

    # Read every complete canonical card; proposed paths are plans, never found-file evidence.
    for bundle in bundles:
        card = cards[bundle]["criterion_card"]
        body = text(card)
        for selector in pattern.findall(body):
            planned.setdefault(normalize(selector), set()).add(bundle)
            add(selector, "canonical_card_plan", card, bundle)
    # Full B.md sections retain per-bundle command lineage, not just the last section.
    bdoc = prefix + "closure-decisions/B.md"
    sections = re.split(r"(?=^### [A-Z]+-\d\d\b)", text(bdoc), flags=re.M)
    for section in sections:
        match = re.match(r"### ([A-Z]+-\d\d)\b", section)
        bundle = match.group(1) if match else None
        for selector in pattern.findall(section):
            if bundle in bundles:
                planned.setdefault(normalize(selector), set()).add(bundle)
            add(selector, "closure_decision_plan", bdoc + (f"#{bundle}" if bundle else ""), bundle)
    # Route the entire current B census through exact canonical cells, not summary or filenames.
    cellmap = {x["id"]: x for x in rows(res + "cells.tsv")}
    route_rows = [
        r for r in rows(res + "routes.tsv") if r["unit"] == "B" and r["finding_id"] in ids
    ]
    route_records = []
    for r in route_rows:
        c = cellmap.get(r["cell_id"])
        if c is None:
            raise ValueError(f"Missing exact canonical cell for {r}")
        route_records.append(
            {
                "finding_id": r["finding_id"],
                "cell_id": c["id"],
                "source_sha": c["source_sha"],
                "source_ref": r["source_ref"],
                "path": c["path"],
                "source_file": c["source_file"],
                "source_line": c["source_line"],
                "grade": r["route_grade"],
                "semantic_adequacy": r["semantic_adequacy"],
            }
        )
        bundle = next(
            x["source_closure_owner"] for x in owners if x["finding_id"] == r["finding_id"]
        )
        for selector in pattern.findall(c["path"]):
            add(
                selector,
                "historical_route_navigation",
                res + "routes.tsv#" + r["finding_id"] + "/" + r["cell_id"],
                bundle,
            )
    # Current owner/independent receipts and qualified type-only historical input.
    roots = []
    for path in sorted(tracked):
        if (
            not path.startswith(handoff)
            or "/" in path[len(handoff) :]
            or not path.endswith(".json")
        ):
            continue
        if not Path(path).name.startswith(
            (
                "current-",
                "cas-current-",
                "cas-verification-",
                "cas-profile-",
                "cas-independent-",
                "independent-net02-",
                "run-typevar",
            )
        ):
            continue
        d = json.loads(text(path))
        roots.append((path, d))
    for rootpath, d in roots:
        advertised = [x for x in d.get("bundle_ids", []) if x in bundles]
        if "finding_dispositions" in d:
            owner_dispositions.append(
                {
                    "receipt": rootpath,
                    "receipt_identity": identity(rootpath),
                    "dispositions": d["finding_dispositions"],
                    "grade": "recorded owner input only; no automatic latest-overlay adjudication",
                }
            )
        receipt_manifest.append(
            {
                "identity": identity(rootpath),
                "bundle_ids": advertised,
                "source_points": {
                    k: v
                    for k, v in d.items()
                    if ("sha" in k or "commit" in k) and isinstance(v, str)
                },
                "generation": "historical_type_only_input"
                if Path(rootpath).name == "run-typevar.json"
                else "current_owner_or_independent_receipt",
            }
        )
        queue = [rootpath]
        seen = set()
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            if path.endswith(".json"):
                try:
                    obj = json.loads(text(path))
                except ValueError:
                    continue
                walk(obj, path, advertised)
                queue += json_references(obj)
            else:
                # Source/test modules can mention unrelated pytest paths in documentation.
                # Only handoff driver inputs are eligible static native-child descriptors.
                if not path.startswith(handoff):
                    continue
                body = text(path)
                # Static driver discovery is candidate input lineage; it is not an executed PASS.
                if "pytest" not in body:
                    continue
                selectors = sorted(set(pattern.findall(body)))
                if selectors:
                    driver_records.append(
                        {
                            "identity": identity(path),
                            "root_receipt": rootpath,
                            "bundle_ids": advertised,
                            "selectors": selectors,
                            ("grade"): (
                                "static native-child descriptor, no execution or selector conforma"
                                "nce claim"
                            ),
                        }
                    )
                    for selector in selectors:
                        for bundle in advertised or [None]:
                            add(selector, "script_native_child_static", path, bundle)
    # Include every genuinely changed/new test definition; helpers are separately listed inputs.
    changed = (
        git("diff", "--name-only", "198076863e143dea9f89f02734b13d50dae3eed5", sha)
        .decode()
        .splitlines()
    )
    changed_tests = []
    changed_defining = []
    for path in changed:
        if path not in tracked:
            continue
        if path.startswith("policy-engine/tests/") and path.endswith(".py"):
            changed_tests.append(identity(path))
            if Path(path).name.startswith("test_"):
                add(path, "actual_changed_test_input", path)
        if path.startswith("policy-engine/src/") and path.endswith(".py"):
            changed_defining.append(identity(path))
    existing = []
    missing = []
    test_defs = {}
    for p, records in sorted(sources.items()):
        path = "policy-engine/" + p
        if path in tracked:
            module = ast.parse(text(path), filename=path)
            defs = []

            def definition(
                n: ast.AST,
                qualifier: str = "",
                output: list[dict[str, object]] = defs,
                test_path: str = p,
                module_path: str = path,
            ) -> None:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith(
                    "test_"
                ):
                    output.append(
                        {
                            "name": n.name,
                            "selector": test_path + "::" + qualifier + n.name,
                            "line": n.lineno,
                            "end_line": n.end_lineno,
                            "source_sha256": hashlib.sha256(
                                ast.get_source_segment(text(module_path), n).encode()
                            ).hexdigest(),
                        }
                    )

            for n in module.body:
                definition(n)
                if isinstance(n, ast.ClassDef) and n.name.startswith("Test"):
                    for member in n.body:
                        definition(member, n.name + "::")
            test_defs[p] = defs
            existing.append(
                {
                    "test_path": p,
                    "identity": identity(path),
                    "source_refs": list(records.values()),
                    "test_definitions": defs,
                    ("grade"): (
                        "candidate input denominator only; path/AST existence does not pro"
                        "ve property or successful collection"
                    ),
                }
            )
        else:
            missing.append(
                {
                    "named_selector": p,
                    "bundle_ids": sorted(planned.get(p, [])),
                    "source_refs": list(records.values()),
                    "state": "UNRUN_named_selector_absent",
                    "equivalent_candidate_selectors": [],
                }
            )
    if {x["named_selector"] for x in missing} != set(mapping):
        raise ValueError("Every absent selector needs a reviewed map or explicit UNRUN")
    for item in missing:
        entry = mapping[item["named_selector"]]
        for candidate in entry["candidates"]:
            selected = candidate["selector"]
            p = normalize(selected)
            matches = [x for x in test_defs.get(p, []) if x["selector"] == selected]
            if len(matches) != 1:
                raise ValueError(f"Selected exact test body not found once: {selected}")
            candidate = {
                **candidate,
                "definition": matches[0],
                "module_identity": identity("policy-engine/" + p),
                ("execution_state"): (
                    "UNRUN_at_this_draft_snapshot; body review only, not collection or PASS"
                ),
            }
            item["equivalent_candidate_selectors"].append(candidate)
        item["residuals"] = entry["residuals"]
        item["equivalence_grade"] = (
            "source-reviewed bounded discriminators; absent planned name is not silently satisfied"
        )
    result = {
        "schema": "policyos.e02.cohort_selector_audit.v1",
        "state": "DRAFT_current_snapshot_not_final_union",
        "root_snapshot_sha": sha,
        "root_snapshot_tree": tree,
        ("root_snapshot_custody"): (
            "Every tracked input read via git show@exactSHA; no live root sour"
            "ce read, edit, checkout, test or collection run"
        ),
        "canonical_denominator": {
            "bundles": 25,
            "findings": 60,
            "bundle_ids": sorted(bundles),
            "finding_ids": sorted(ids),
            "route_rows": len(route_records),
            "deduplicated_route_cells": len({r["cell_id"] for r in route_records}),
        },
        "historical_snapshot_only": {
            "files": 74,
            "cases": 1317,
            "grade": "historical G97 candidate snapshot, never current collected denominator",
        },
        "input_identities": [
            identity(x)
            for x in [
                org + "bundle-owners.tsv",
                org + "finding-owners.tsv",
                res + "routes.tsv",
                res + "cells.tsv",
                prefix + "closure-decisions/coverage.json",
                bdoc,
            ]
        ],
        "canonical_cards": [
            {
                "bundle_id": b,
                "finding_ids": cards[b]["finding_ids"],
                "identity": identity(cards[b]["criterion_card"]),
            }
            for b in sorted(bundles)
        ],
        "owner_receipts": receipt_manifest,
        "owner_disposition_descriptors": owner_dispositions,
        "actual_command_descriptors": commands,
        "all_recorded_check_command_descriptors": all_commands,
        "script_native_child_descriptors": driver_records,
        "changed_defining_source_inputs": changed_defining,
        "changed_test_and_helper_inputs": changed_tests,
        "route_records": route_records,
        "test_paths": [x["test_path"] for x in existing],
        "candidate_whole_file_count": len(existing),
        "candidate_test_inputs": existing,
        "absent_named_selectors": missing,
        "bundle_selector_map": {
            b: sorted(
                p for p, r in sources.items() if any(x.get("bundle") == b for x in r.values())
            )
            for b in sorted(bundles)
        },
        "non_execution_limits": [
            (
                "No pytest execution or collection; parameterized cases/conftest/i"
                "mport closure are not established by AST/path inspection."
            ),
            (
                "Native-child descriptors are parsed recursively from full committ"
                "ed owner receipts/execution JSON and driver bytes. Base/negative/"
                "in-memory-overlay commands contribute input lineage, never a gree"
                "n execution claim."
            ),
            (
                "Absent planned names need independent criterion-to-actual-selecto"
                "r source review or remain explicit UNRUN; future-root freeze must"
                " rederive after all writers ready."
            ),
            (
                "B13 A-owned generation route and B61 source-owner/versioned SKG b"
                "oundary remain explicit; cardinality is input selection, not find"
                "ing closure."
            ),
        ],
    }
    result["derivation"] = {
        "driver_path": str(Path(__file__)),
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "equivalence_map_path": str(mapping_path),
        "equivalence_map_sha256": hashlib.sha256(mapping_bytes).hexdigest(),
        "argv": [
            "python3",
            str(Path(__file__)),
            "--repo",
            str(repo),
            "--sha",
            sha,
            "--equivalents",
            str(mapping_path),
            "--output",
            args.output,
        ],
        ("input_grade"): (
            "fresh reviewed static map and immutable Git inputs; no ignored runtime output input"
        ),
    }
    result["finding_criteria"] = [f for f in coverage["findings"] if f.get("unit") == "B"]
    result["bundle_absent_selector_map"] = {
        b: [
            {
                "named_selector": m["named_selector"],
                "equivalent_candidate_selectors": m["equivalent_candidate_selectors"],
                "residuals": m["residuals"],
            }
            for m in missing
            if b in m["bundle_ids"]
        ]
        for b in sorted(bundles)
    }
    result["known_pending_candidate_case_count"] = (
        "UNRUN: parameterized case count and successful native collection "
        "must be measured on final root freeze"
    )
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                "sha": sha,
                "tree": tree,
                "files": len(existing),
                "missing": len(missing),
                "commands": len(commands),
                "scripts": len(driver_records),
                "receipts": len(receipt_manifest),
                "route_rows": len(route_records),
                "cells": result["canonical_denominator"]["deduplicated_route_cells"],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
