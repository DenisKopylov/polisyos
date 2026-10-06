"""Derive complete B cohort inputs from immutable Git bytes, never run tests."""

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


def native_pytest_positionals(
    argv: list[str], profile: dict[str, object]
) -> tuple[list[str], list[str]]:
    """Separate selectors using pinned observed option arities, without importing pytest."""
    marker = next(
        (i for i, x in enumerate(argv) if x in {"pytest", "pytest.main"} or x.endswith("/pytest")),
        None,
    )
    if marker is None:
        return [], ["native pytest marker absent"]
    tokens = argv[marker + 1 :]
    if any(token.startswith("@") for token in tokens):
        return [], ["argument-file expansion unresolved; no guessed positional selectors"]
    grammar = argparse.ArgumentParser(add_help=False, allow_abbrev=False, exit_on_error=False)
    seen: set[str] = set()
    for action in profile["actions"]:
        options = action["options"]
        if seen.intersection(options):
            raise ValueError("Pinned option grammar contains duplicate option names")
        seen.update(options)
        nargs = action["nargs"]
        if nargs == 0:
            grammar.add_argument(*options, action="store_true")
        elif nargs is None or nargs in {"?", "+", "*"} or isinstance(nargs, int):
            grammar.add_argument(*options, nargs=nargs)
        else:
            raise ValueError(f"Unsupported pinned option arity: {nargs!r}")
    grammar.add_argument("native_selectors", nargs="*")
    try:
        parsed, unknown = grammar.parse_known_intermixed_args(tokens)
    except (argparse.ArgumentError, ValueError) as exc:
        return [], [f"option/value grammar unresolved: {exc}"]
    if unknown:
        return [], [f"unknown option grammar: {unknown!r}; no guessed selectors"]
    return parsed.native_selectors, []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--equivalents", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--raw-output")
    args = parser.parse_args()
    repo = Path(args.repo)
    sha = args.sha
    mapping_path = Path(args.equivalents)

    git_executable = shutil.which("git")
    if git_executable is None or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("An existing Git executable and immutable SHA are required")

    def git(*xs: str) -> bytes:
        return subprocess.check_output([git_executable, ("-C"), str(repo), *xs])  # noqa: S603 - argv-only immutable Git reads

    tree = git("rev-parse", sha + "^{tree}").decode().strip()
    tracked = set(git("ls-tree", "-r", "--name-only", sha).decode().splitlines())
    try:
        mapping_source_path = mapping_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("The reviewed equivalence map must belong to the pinned Git tree") from exc
    if mapping_source_path not in tracked:
        raise ValueError("The reviewed equivalence map must be tracked at the pinned SHA")
    mapping_bytes = git("show", f"{sha}:{mapping_source_path}")
    mapping = json.loads(mapping_bytes)
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
    manifest_path = (
        "policy-engine/docs/plans/active/agent-packages/"
        "PolicyOS_E02_Combined_Agent_Package/bundle_manifest.json"
    )
    org = prefix + "execution-organization/"
    res = prefix + "results/"
    handoff = prefix + "implementation-handoffs/B/"
    option_profile_path = handoff + "final-root-evidence/pytest-cli-option-profile.json"
    option_profile = json.loads(text(option_profile_path))
    if option_profile["schema"] != "policyos.e02.pytest_cli_option_profile.v1":
        raise ValueError("An observed immutable pytest option profile is required")
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
        if not (Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py")):
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

    manifest = json.loads(text(manifest_path))
    manifest_bundles = [row for row in manifest["bundles"] if row["id"] in bundles]
    if {row["id"] for row in manifest_bundles} != set(bundles):
        raise ValueError("Canonical manifest must resolve every owned bundle")
    manifest_ids = {
        finding
        for row in manifest_bundles
        for finding in (*row["findings"], *row.get("legacy_cards", []))
    }
    if manifest_ids != ids:
        raise ValueError("Manifest findings plus legacy cards must reconcile full ownership")
    for row in manifest_bundles:
        for selector in row.get("test_paths", []):
            planned.setdefault(normalize(selector), set()).add(row["id"])
            add(selector, "canonical_manifest_plan", manifest_path + "#" + row["id"], row["id"])

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
        command_record = {
            "locator": locator,
            "role": role,
            "argv": argv,
            "bundle_ids": list(bundle_ids),
            "native_pytest_argv": is_pytest,
            "grade": "complete recorded check-command lineage, no execution claim",
        }
        all_commands.append(command_record)
        if not is_pytest:
            return
        selectors = []
        directory_members = []
        positional_tokens, unresolved = native_pytest_positionals(argv, option_profile)
        command_record["positional_selector_tokens"] = positional_tokens
        command_record["unresolved_option_grammar"] = unresolved
        for token in positional_tokens:
            # Match a complete positional token, never a substring of an option value.
            if pattern.fullmatch(token):
                selectors.append(token)
            # Native pytest directory inputs select whole tracked test files too.
            # Expand immutable Git members, never a local filesystem or ignored output.
            directory = token.removeprefix("policy-engine/").rstrip("/")
            if directory.startswith("tests/") and ".py" not in directory:
                members = sorted(
                    p.removeprefix("policy-engine/")
                    for p in tracked
                    if p.startswith("policy-engine/" + directory + "/")
                    and p.endswith(".py")
                    and (Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py"))
                )
                selectors.extend(members)
                if members:
                    directory_members.append(
                        {
                            "native_directory_token": token,
                            "members": members,
                            "selection_basis": "pinned tracked test_*.py or *_test.py descendants",
                            "grade": "whole-file input selection, not collection or runtime proof",
                        }
                    )
        if not selectors:
            return
        commands.append(
            {
                "locator": locator,
                "role": role,
                "argv": argv,
                "selectors": selectors,
                "bundle_ids": list(bundle_ids),
                "native_directory_inputs": directory_members,
                "positional_selector_tokens": positional_tokens,
                "unresolved_option_grammar": unresolved,
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
                    if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v)
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
            if Path(path).name.startswith("test_") or Path(path).name.endswith("_test.py"):
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
    if not {x["named_selector"] for x in missing}.issubset(mapping):
        raise ValueError("Every absent selector needs a reviewed map or explicit UNRUN")
    resolved_proposals = [
        {"named_selector": p, "identity": identity("policy-engine/" + p)}
        for p in sorted(mapping)
        if "policy-engine/" + p in tracked
    ]
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
        "state": "COMPLETE_STATIC_COHORT_INPUTS_NO_EXECUTION_OR_CASE_COUNT",
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
                manifest_path,
                option_profile_path,
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
        "previously_absent_proposals_now_present": resolved_proposals,
        "bundle_selector_map": {
            b: sorted(
                p for p, r in sources.items() if any(x.get("bundle") == b for x in r.values())
            )
            for b in sorted(bundles)
        },
        "non_execution_limits": [
            (
                "Native positional parsing uses Git-pinned observed pytest9 option arities. "
                "Repository-added/unknown options and argument files remain explicitly unresolved. "
                "Default test filename expansion does not establish custom collection hooks."
            ),
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
        "cwd": str(Path.cwd()),
        "driver_path": str(Path(__file__)),
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "equivalence_map_path": str(mapping_path),
        "equivalence_map_git_path": mapping_source_path,
        "equivalence_map_source_sha": sha,
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
    if args.raw_output:
        result["derivation"]["argv"].extend(["--raw-output", args.raw_output])
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
    raw_pin = None
    if args.raw_output:
        raw_path = Path(args.raw_output)
        if "_build" not in raw_path.parts and ".polisyos" not in raw_path.parts:
            raise ValueError("Large full metadata belongs only in ignored raw storage")
        raw_bytes = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
        raw_path.write_bytes(raw_bytes)
        raw_pin = {
            "path": str(raw_path.resolve()),
            "source_git_sha": sha,
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "bytes": len(raw_bytes),
            "grade": "ignored full lineage; compact census/source Git refs are authoritative",
        }

    def command_id(value: object) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    native_refs = {}
    descriptor_paths = set()
    for command in commands:
        key = command_id({"locator": command["locator"], "argv": command["argv"]})
        if key not in native_refs:
            native_refs[key] = {
                "command_id": key,
                "locator": command["locator"],
                "argv_sha256": command_id(command["argv"]),
                "selector_paths": sorted({normalize(x) for x in command["selectors"]}),
                "bundle_ids": [],
            }
        row = native_refs[key]
        row["bundle_ids"] = sorted(set(row["bundle_ids"]) | set(command["bundle_ids"]))
        if ".json" in command["locator"]:
            descriptor_paths.add(command["locator"].split(".json", 1)[0] + ".json")
    cells_by_finding = {
        finding: sorted({r["cell_id"] for r in route_records if r["finding_id"] == finding})
        for finding in sorted(ids)
    }
    card_names = {
        bundle: sorted(p for p, advertised in planned.items() if bundle in advertised)
        for bundle in sorted(bundles)
    }
    descriptor_inputs = [identity(p) for p in sorted(descriptor_paths) if p in tracked]
    descriptor_indexes = {row["path"]: i for i, row in enumerate(descriptor_inputs)}
    compact_native_refs = []
    for row in native_refs.values():
        path, pointer = row["locator"].split(".json", 1)
        compact_native_refs.append(
            {
                "command_id": row["command_id"],
                "input_index": descriptor_indexes[path + ".json"],
                "descriptor_pointer": pointer,
                "bundle_ids": row["bundle_ids"],
                "grade": "recorded native argv input; not executed case count or PASS",
            }
        )
    compact = {
        "schema": "policyos.e02.cohort_selector_audit.v3",
        "state": result["state"],
        "root_snapshot_sha": sha,
        "root_snapshot_tree": tree,
        "root_snapshot_custody": result["root_snapshot_custody"],
        "canonical_denominator": result["canonical_denominator"],
        "historical_snapshot_only": result["historical_snapshot_only"],
        "input_identities": result["input_identities"],
        "canonical_cards": result["canonical_cards"],
        "finding_criterion_refs": [
            {k: f[k] for k in ("id", "primary_bundle", "criterion_refs")}
            for f in result["finding_criteria"]
        ],
        "cells_by_finding_navigation_only": cells_by_finding,
        "candidate_whole_file_count": len(existing),
        "test_paths": result["test_paths"],
        "candidate_whole_file_identities": [x["identity"] for x in existing],
        "absent_named_selectors": missing,
        "previously_absent_proposals_now_present": resolved_proposals,
        "manifest_findings_reconciliation": {
            "ids": sorted(manifest_ids),
            "legacy_cards_included": sorted(
                {x for row in manifest_bundles for x in row.get("legacy_cards", [])}
            ),
            "grade": "manifest selector inputs only; closure decisions retain authority",
        },
        "bundle_planned_names": card_names,
        "owner_receipt_identities": receipt_manifest,
        "native_command_descriptor_refs": compact_native_refs,
        "descriptor_pointer_dialect": (
            "Dict/list traversal; /decoded parses a serialized JSON string. "
            "The complete deterministic walk is in this committed derivation driver."
        ),
        "command_descriptor_input_identities": descriptor_inputs,
        "script_native_child_descriptors": driver_records,
        "changed_defining_source_inputs": changed_defining,
        "changed_test_and_helper_inputs": changed_tests,
        "descriptor_counts_only": {
            "top_receipts": len(receipt_manifest),
            "native_argv_lineage_rows": len(commands),
            "deduplicated_native_descriptor_refs": len(native_refs),
            "static_script_rows": len(driver_records),
            "all_recorded_historical_command_lineage_rows": len(all_commands),
            "unresolved_native_option_grammar_rows": sum(
                bool(row.get("unresolved_option_grammar")) for row in all_commands
            ),
            "grade": "input lineage counts only; none is a case count or PASS",
        },
        "unresolved_native_option_grammar": [
            {
                "locator": row["locator"],
                "argv_sha256": command_id(row["argv"]),
                "reasons": row["unresolved_option_grammar"],
                "grade": "UNRESOLVED input lineage; no guessed positional inputs or absence claim",
            }
            for row in all_commands
            if row.get("unresolved_option_grammar")
        ],
        "ignored_full_lineage": raw_pin,
        "historical_oversized_packet": {
            "commit": "327b90023110f91b42a94e039863e7a8fe1425ec",
            "path": handoff + "current-adapters-evidence/cohort-selector-audit.json",
            "sha256": "7d9c8a9c1507753635d553f98c90e533524024d8b30c05094efdc1b155ccb922",
            "bytes": 6125292,
            "grade": "historical publishing mistake; superseded, not current input proof",
        },
        "derivation": result["derivation"],
        "known_pending_candidate_case_count": result["known_pending_candidate_case_count"],
        "non_execution_limits": result["non_execution_limits"],
    }
    Path(args.output).write_text(json.dumps(compact, indent=2, ensure_ascii=False) + "\n")
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
