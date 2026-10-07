"""Invoke the exact nested selector parser with a controlled tracked set only.

This internal B research discriminator executes standard-library AST metadata
helpers. It does not invoke the selector main, pytest, collection, a gate, a
product import, or filesystem test discovery.
"""

from __future__ import annotations

import argparse
import ast
import configparser
import fnmatch
import hashlib
import json
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

type Row = dict[str, object]

SELECTOR = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    "final-cohort-selector.py"
)
CONTROLLED = {
    "policy-engine/tests/controlled/test_first.py",
    "policy-engine/tests/controlled/nested/test_second.py",
    "policy-engine/tests/outside/test_outside.py",
    "policy-engine/tests/controlled/helper.py",
}
EXPECTED = ["tests/controlled/nested/test_second.py", "tests/controlled/test_first.py"]


def ref(data: bytes) -> Row:
    """Bind a complete explicit input read by size and digest."""
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    """Read pinned source, execute only its parser helpers, and record all cases."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--pytest-source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.target) is None:
        raise ValueError("An exact immutable SHA is required")
    reads: list[Row] = []
    driver_path = Path(__file__).absolute()
    reads.append({"path": str(driver_path), **ref(driver_path.read_bytes())})

    def git(*words: str) -> bytes:
        argv = ["/usr/bin/git", "-C", str(args.repo), *words]
        # Fixed Git, read-only immutable objects; no arbitrary child command.
        data = subprocess.check_output(argv)  # noqa: S603
        reads.append({"command": argv, **ref(data)})
        return data

    source = git("show", args.target + ":" + SELECTOR)
    module = ast.parse(source, filename=SELECTOR)
    selector_main = next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    helper_nodes = [*module.body, *selector_main.body]
    helpers = {
        node.name: node
        for node in helper_nodes
        if isinstance(node, ast.FunctionDef) and node.name != "main"
    }
    names = {"parse_native", "add", "normalize"}
    pending = list(names)
    while pending:
        name = pending.pop()
        for call in ast.walk(helpers[name]):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                dependency = call.func.id
                if dependency in helpers and dependency not in names:
                    names.add(dependency)
                    pending.append(dependency)
    definitions = [
        node for node in helper_nodes if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    pattern = next(
        node
        for node in selector_main.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "pattern" for target in node.targets)
    )
    regex = ast.literal_eval(cast("ast.Call", pattern.value).args[0])
    namespace: Row = {
        "Path": Path,
        "shlex": shlex,
        "re": re,
        "argparse": argparse,
        "pattern": re.compile(regex),
        "tracked": CONTROLLED,
        "sources": {},
        "commands": [],
        "all_commands": [],
    }
    option_profile: Row | None = None
    if "native_pytest_positionals" in helpers:
        profile_path = (
            SELECTOR.rsplit("/", 1)[0] + "/final-root-evidence/pytest-cli-option-profile.json"
        )
        option_profile = json.loads(git("show", args.target + ":" + profile_path))
        namespace["option_profile"] = option_profile
    executable = ast.Module(body=definitions, type_ignores=[])
    # Only exact hash-bound nested metadata definitions execute; main/imports are excluded.
    exec(compile(executable, SELECTOR, "exec"), namespace)  # noqa: S102
    parse_native = namespace["parse_native"]
    cases = []
    variants = [
        ("positional_directory", ["python", "-m", "pytest", "tests/controlled"], EXPECTED),
        (
            "prefixed_trailing_slash",
            ["python", "-m", "pytest", "policy-engine/tests/controlled/"],
            EXPECTED,
        ),
        ("native_string_command", "python -m pytest tests/controlled", EXPECTED),
        ("non_pytest", ["python", "-m", "ruff", "check", "tests/controlled"], []),
        ("attached_option", ["python", "-m", "pytest", "--basetemp=tests/controlled"], []),
        ("separate_option_value", ["python", "-m", "pytest", "--basetemp", "tests/controlled"], []),
    ]
    if option_profile is not None:
        variants.extend(
            [
                ("flag_preserves_position", ["pytest", "-q", "tests/controlled"], EXPECTED),
                ("short_group", ["pytest", "-vv", "tests/controlled"], EXPECTED),
                (
                    "short_group_attached_value",
                    ["pytest", "-qkneedle", "tests/controlled"],
                    EXPECTED,
                ),
                ("sentinel", ["pytest", "--", "tests/controlled"], EXPECTED),
                (
                    "sentinel_after_variable_arity",
                    ["pytest", "--benchmark-compare-fail", "mean:5%", "--", "tests/controlled"],
                    EXPECTED,
                ),
                (
                    "variable_arity_then_flag",
                    [
                        "pytest",
                        "--benchmark-compare-fail",
                        "mean:5%",
                        "stddev:7%",
                        "-q",
                        "tests/controlled",
                    ],
                    EXPECTED,
                ),
                (
                    "optional_value_then_flag",
                    ["pytest", "--debug", "debug.log", "-q", "tests/controlled"],
                    EXPECTED,
                ),
                (
                    "filename_option_value",
                    ["pytest", "--basetemp", "tests/controlled/test_first.py"],
                    [],
                ),
                ("unknown_option", ["pytest", "--e02-unregistered", "tests/controlled"], []),
                ("argument_file", ["pytest", "@not_read.args", "tests/controlled"], []),
                ("missing_value", ["pytest", "--basetemp"], []),
            ]
        )
    unresolved_names = {"unknown_option", "argument_file", "missing_value"}
    for name, argv, expected in variants:
        namespace["sources"] = {}
        namespace["commands"] = []
        namespace["all_commands"] = []
        parse_native(argv, "controlled/" + name, ["CAS-02"])
        sources = cast("dict[str, dict[object, Row]]", namespace["sources"])
        observed = sorted(sources)
        lineage = cast("list[Row]", namespace["all_commands"])
        unresolved = [
            reason
            for row in lineage
            for reason in cast("list[str]", row.get("unresolved_option_grammar", []))
        ]
        reasons_valid = bool(unresolved) if name in unresolved_names else not unresolved
        cases.append(
            {
                "name": name,
                "input": argv,
                "expected_files": expected,
                "observed_files": observed,
                "outcome": "PASS" if observed == expected and reasons_valid else "FAIL",
                "unresolved_reasons": unresolved,
                "native_descriptors": namespace["commands"],
                "complete_command_lineage": namespace["all_commands"],
                "sources": {path: list(records.values()) for path, records in sources.items()},
            }
        )
    ini_bytes = git("show", args.target + ":policy-engine/pytest.ini")
    ini = configparser.ConfigParser()
    ini.read_string(ini_bytes.decode())
    pytest_source = args.pytest_source.read_bytes()
    reads.append({"path": str(args.pytest_source), **ref(pytest_source)})
    pytest_ast = ast.parse(pytest_source)
    defaults = []
    for node in ast.walk(pytest_ast):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "addini" and node.args and isinstance(node.args[0], ast.Constant):
            if node.args[0].value == "python_files":
                defaults = ast.literal_eval(
                    next(kw.value for kw in node.keywords if kw.arg == "default")
                )
    if not defaults or "python_files" in ini["pytest"]:
        raise ValueError("Filename basis changed; review the actual configured patterns")
    all_paths = git("ls-tree", "-r", "--name-only", args.target).decode().splitlines()
    tests = [p for p in all_paths if p.startswith("policy-engine/tests/") and p.endswith(".py")]
    secondary = [
        p
        for p in tests
        if any(fnmatch.fnmatchcase(Path(p).name, pattern) for pattern in defaults)
        and not Path(p).name.startswith("test_")
    ]
    phase0 = [p for p in tests if p.startswith("policy-engine/tests/unit/core/phase0/")]
    if option_profile is not None:
        namespace["tracked"] = set(all_paths)
        namespace["sources"] = {}
        namespace["commands"] = []
        namespace["all_commands"] = []
        argv = ["pytest", "tests/unit/core/phase0"]
        parse_native(argv, "actual/phase0", ["CAS-02"])
        observed = sorted(cast("dict[str, object]", namespace["sources"]))
        expected = sorted(
            p.removeprefix("policy-engine/")
            for p in phase0
            if any(fnmatch.fnmatchcase(Path(p).name, pat) for pat in defaults)
        )
        cases.append(
            {
                "name": "actual_pinned_phase0_directory",
                "input": argv,
                "expected_files": expected,
                "observed_files": observed,
                "native_descriptors": namespace["commands"],
                "complete_command_lineage": namespace["all_commands"],
                "outcome": "PASS" if observed == expected else "FAIL",
            }
        )
        namespace["tracked"] = {*CONTROLLED, "policy-engine/tests/controlled/secondary_test.py"}
        namespace["sources"] = {}
        namespace["commands"] = []
        namespace["all_commands"] = []
        parse_native(["pytest", "tests/controlled"], "controlled/secondary_filename", ["CAS-02"])
        observed = sorted(cast("dict[str, object]", namespace["sources"]))
        expected = sorted([*EXPECTED, "tests/controlled/secondary_test.py"])
        cases.append(
            {
                "name": "default_secondary_filename",
                "input": ["pytest", "tests/controlled"],
                "expected_files": expected,
                "observed_files": observed,
                "native_descriptors": namespace["commands"],
                "outcome": "PASS" if observed == expected else "FAIL",
            }
        )
    report = {
        "schema": "policyos.e02.selector_directory_independent_review.v1",
        "source_sha": args.target,
        "tree_sha": git("rev-parse", args.target + "^{tree}").decode().strip(),
        "source_path": SELECTOR,
        "source_identity": ref(source),
        "compiled_helpers": [node.name for node in definitions],
        "controlled_tracked_set": sorted(CONTROLLED),
        "cases": cases,
        "counts": dict(Counter(str(row["outcome"]) for row in cases)),
        "pinned_option_profile": None
        if option_profile is None
        else {
            "source_sha": args.target,
            "path": profile_path,
            "schema": option_profile["schema"],
            "pytest_version": option_profile["pytest_version"],
            "actions": len(option_profile["actions"]),
            "option_names": sum(len(action["options"]) for action in option_profile["actions"]),
            "source_observations": len(option_profile["option_registration_sources"]),
            "arity_distribution": dict(
                Counter(repr(action["nargs"]) for action in option_profile["actions"])
            ),
            "limits": option_profile["limits"],
        },
        "filename_basis": {
            "pytest_ini": {"source_sha": args.target, **ref(ini_bytes)},
            "installed_pytest_source": str(args.pytest_source),
            "defaults_from_complete_source_ast": defaults,
            "python_files_override": False,
            "complete_tracked_python_test_paths": len(tests),
            "default_supported_non_test_prefix_paths": secondary,
            "phase0_python_paths": len(phase0),
            "phase0_test_prefix_paths": [p for p in phase0 if Path(p).name.startswith("test_")],
        },
        "explicit_reads": reads,
        "environment": {"executable": sys.executable, "version": sys.version},
        "property": (
            "Only native pytest positional directories expand into exact pinned tracked "
            "test descendants; options and nonpytest commands do not become native selector inputs."
        ),
        "bucket": "P40 SAME input-selection/positional-token class, not a product/runtime finding.",
        "unresolved_by_construction": [
            "No pytest, collection, full selector main, gate, ignored fixture or product code ran.",
            "Tracked path/AST selection does not establish actual case counts, importability, "
            "conftest exclusions or runtime semantics.",
            "Installed pytest source was read, not imported; full installed binary/import "
            "closure is unmeasured.",
        ],
        "closure_ids": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    sys.stdout.write(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
