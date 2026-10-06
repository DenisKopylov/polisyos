"""Audit existing frozen gate outputs; run no gate, test, or product import.

The B root invokes this internal research reader after publishing terminal
receipts. Its selector is the supplied launcher's complete AST tag set. Git
reads bind immutable source; explicit file reads carry their own byte receipts.
Missing, malformed, or unfinished inputs remain named undecided boundaries.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

# The input is local root-produced JUnit, with no network XML dispatch.
from xml.etree import ElementTree  # noqa: S405

type Row = dict[str, object]

HANDOFF = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
LAUNCHER = HANDOFF + "final-root-evidence/run_frozen.py"
CAPTURE = HANDOFF + "final-root-evidence/capture_frozen.py"
CAPS = {
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
}


class Reader:
    """Record every explicit read; do not treat an unreadable member as empty."""

    def __init__(self, root: Path) -> None:
        """Bind the Git repository and initialize the explicit input ledger."""
        self.root = root
        self.reads: dict[str, Row] = {}
        self.unresolved: list[Row] = []

    def file(self, path: Path) -> bytes:
        """Read complete bytes and retain identity or the failed-read boundary."""
        try:
            data = path.read_bytes()
        except OSError as exc:
            self.unresolved.append(
                {"class": "unreadable_file", "path": str(path), "error": repr(exc)}
            )
            raise
        self.reads[str(path)] = {
            "path": str(path),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        return data

    def git(self, *words: str) -> bytes:
        """Read local Git objects only; retain the full returned byte identity."""
        argv = ["/usr/bin/git", "--no-optional-locks", "-C", str(self.root), *words]
        # Fixed system Git, literal read-only subcommands; no shell or gate dispatch.
        data = subprocess.check_output(argv)  # noqa: S603
        key = "git:" + json.dumps(words)
        self.reads[key] = {
            "command": argv,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        return data

    def row(self, path: Path) -> Row:
        """Read a JSON object, refusing a different top-level type."""
        value = json.loads(self.file(path))
        if not isinstance(value, dict):
            raise TypeError(f"Expected an object: {path}")
        return cast("Row", value)


def require(predicate: bool, message: str) -> None:
    """Refuse a custody predicate that this reader cannot reconcile."""
    if not predicate:
        raise ValueError(message)


def tags_from_source(source: bytes, prefix: str) -> list[str]:
    """Derive every supported tag from comparisons on the canonical tag variable."""
    tags: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare) or not isinstance(node.left, ast.Name):
            continue
        if node.left.id != "tag" or len(node.ops) != 1:
            continue
        right = node.comparators[0]
        if isinstance(node.ops[0], ast.Eq) and isinstance(right, ast.Constant):
            values = [right.value]
        elif isinstance(node.ops[0], ast.In) and isinstance(right, (ast.Set, ast.Tuple)):
            values = [value.value for value in right.elts if isinstance(value, ast.Constant)]
        else:
            raise ValueError("Unsupported canonical tag-dispatch syntax")
        tags.update(
            value for value in values if isinstance(value, str) and value.startswith(prefix)
        )
    require(bool(tags), "Launcher selected no supported tags")
    return sorted(tags)


def constituent_audit(text: str, wrapper: Row, target: str, tree: str) -> Row:
    """Reconcile the full printed factory plan with the actually entered prefix."""
    plan, position = json.JSONDecoder().raw_decode(text)
    require(plan["target_source_sha"] == target and plan["target_tree"] == tree, "Plan source")
    commands = plan["commands"]
    require(len(commands) == plan["expanded_commands"], "Expanded denominator")
    suffix = text[position:]
    labels = re.findall(r"^\[uncapped constituent\] (.*)$", suffix, re.MULTILINE)
    require(labels == [row["label"] for row in commands[: len(labels)]], "Entered prefix")
    require(len(labels) <= len(commands), "Extra entered constituent")
    terminal = re.findall(r"returned non-zero exit status (\d+)\.", suffix)
    states = []
    for index, row in enumerate(commands):
        require(row["index"] == index, "Constituent ordinal")
        require(not CAPS.intersection(row["uncapped_environment_overlay"]), "Numeric cap overlay")
        state = "UNRUN"
        if plan["execute"] and index < len(labels):
            if index < len(labels) - 1 or wrapper["exit_code"] == 0:
                state = "PASS"
            else:
                state = "FAIL" if terminal else "ERROR"
        states.append({"index": index, "label": row["label"], "outcome": state})
    if wrapper["exit_code"] == 0 and plan["execute"]:
        require(len(labels) == len(commands), "Successful execution omitted a constituent")
    doctor = re.findall(r"^\[(PASS|FAIL|SKIP|UNRUN)\] ([^:]+): (.*)$", suffix, re.MULTILINE)
    return {
        "plan": plan,
        "constituents": states,
        "counts": dict(Counter(str(row["outcome"]) for row in states)),
        "actual_entered_labels": labels,
        "doctor_checks": [
            {"outcome": state, "name": name, "detail": detail} for state, name, detail in doctor
        ],
        "doctor_counts": dict(Counter(state for state, _, _ in doctor)),
        "native_capped_cli": "UNRUN",
        "qualification": "Canonical uncapped projection; npm lifecycle metadata is not reproduced.",
    }


def style_audit(reader: Reader, tag: str, profile: Row, text: str, target: str) -> Row:
    """Recompute the literal changed-Python set, including docs, and parse all diagnostics."""
    inputs = cast("Row", profile["inputs"])
    base = str(inputs["literal_comparison_base"])
    all_paths = reader.git("ls-tree", "-r", "--name-only", target).decode().splitlines()
    changed = reader.git("diff", "--name-only", "--diff-filter=ACMR", base, target)
    paths = [
        p
        for p in changed.decode().splitlines()
        if p.startswith("policy-engine/") and p.endswith(".py") and p in all_paths
    ]
    require(paths == inputs["paths"] and len(paths) == inputs["count"], "Literal style set")
    argv = cast("list[str]", profile["argv"])
    offset = 5
    require(argv[offset:] == [p.removeprefix("policy-engine/") for p in paths], "Literal argv")
    result: Row = {
        "literal_base": base,
        "count": len(paths),
        "paths_ref": "profile.inputs.paths (complete set; includes docs)",
        "fresh_projection_is_not_literal_denominator": inputs[
            "fresh_published_base_projection_only"
        ],
    }
    if tag.endswith("ruff"):
        headers = re.findall(r"^([A-Z]+\d+) (.*)$", text, re.MULTILINE)
        locations = re.findall(r"^\s*--> (.*?):(\d+):(\d+)$", text, re.MULTILINE)
        reported = re.findall(r"^Found (\d+) errors?\.", text, re.MULTILINE)
        require(len(headers) == len(locations), "Ruff header/location quantity")
        if reported:
            require(len(headers) == int(reported[-1]), "Ruff reported error quantity")
        elif not headers:
            require("All checks passed!" in text, "Ruff completion not established")
        else:
            raise ValueError("Ruff missing terminal error quantity")
        result.update(
            diagnostic_count=len(headers),
            by_code=dict(Counter(code for code, _ in headers)),
            by_path=dict(Counter(path for path, _, _ in locations)),
            source_test_diagnostics=[
                {
                    "code": header[0],
                    "message": header[1],
                    "path": location[0],
                    "line": int(location[1]),
                    "column": int(location[2]),
                }
                for header, location in zip(headers, locations, strict=True)
                if location[0].startswith(("src/", "tests/", "tools/"))
            ],
        )
    else:
        reformatted = re.findall(r"^Would reformat: (.*)$", text, re.MULTILINE)
        summary = re.findall(
            r"(\d+) files? would be reformatted, (\d+) files? already formatted", text
        )
        if summary:
            bad, good = map(int, summary[-1])
        else:
            formatted = re.findall(r"(\d+) files? already formatted", text)
            require(bool(formatted), "Format completion not established")
            bad, good = 0, int(formatted[-1])
        require(bad == len(reformatted) and bad + good == len(paths), "Format full quantity")
        result.update(would_reformat=bad, already_formatted=good, paths=reformatted)
    return result


def gate_audit(reader: Reader, raw: Path, tag: str, target: str, tree: str) -> Row:
    """Audit one terminal receipt, leaving missing or incomplete attempts UNRUN."""
    result: Row = {"tag": tag, "outcome": "UNRUN"}
    profile_path = raw / (tag + "-profile.json")
    wrapper_path = raw / (tag + ".json")
    output_path = raw / (tag + ".txt")
    try:
        profile = reader.row(profile_path)
        result["profile"] = profile
        wrapper = reader.row(wrapper_path)
        result["wrapper"] = wrapper
        result["captured_exit_code"] = wrapper["exit_code"]
        data = reader.file(output_path)
        text = data.decode()
        require(profile["sha"] == wrapper["head"] == wrapper["head_after"] == target, "Gate source")
        require(profile["tree"] == wrapper["tree"] == tree, "Gate tree")
        result["target_bound"] = True
        require(
            profile["argv"] == wrapper["command"] and profile["cwd"] == wrapper["cwd"],
            "Gate argv/cwd",
        )
        require(wrapper["output_sha256"] == hashlib.sha256(data).hexdigest(), "Output bytes")
        require(
            set(cast("list[str]", profile["all_cap_names_absent_in_child"])) == CAPS,
            "Cap disclosure",
        )
        require(not CAPS.intersection(cast("Row", profile["environment"])), "Environment cap names")
        source = reader.git("show", target + ":" + LAUNCHER)
        require(hashlib.sha256(source).hexdigest() == profile["launcher_sha256"], "Launcher bytes")
        result["output"] = reader.reads[str(output_path)]
        if wrapper.get("harness_state") == "UNRUN" or wrapper.get("exec_setup_error"):
            result["qualification"] = "Executable setup failed; gate was not executed."
            return result
        code = int(cast("int", wrapper["exit_code"]))
        result["outcome"] = "PASS" if code == 0 else "ERROR" if code < 0 else "FAIL"
        require(bool(data), "Empty output cannot establish a semantic completion")
        if tag.endswith(("verify-uncapped", "parity-uncapped")):
            result["execution"] = constituent_audit(text, wrapper, target, tree)
            plan = cast("Row", cast("Row", result["execution"])["plan"])
            if not plan["execute"]:
                result["outcome"] = "UNRUN"
            config = str(plan["config_source_sha"])
            for locator in cast("list[str]", plan["factory_paths"]):
                path, source_sha = locator.rsplit("@", 1)
                require(source_sha == config, "Factory source locator")
                require(
                    reader.git("show", config + ":" + path)
                    == reader.git("show", target + ":" + path),
                    "Canonical factory bytes",
                )
            projection = plan.get("additional_argv_projection")
            if isinstance(projection, dict):
                path, source_sha = projection["source"].rsplit("@", 1)
                require(
                    reader.git("show", source_sha + ":" + path)
                    == reader.git("show", target + ":" + path),
                    "Canonical coverage projection bytes",
                )
        elif tag.endswith(("all-changed-ruff", "all-changed-format")):
            result["style"] = style_audit(reader, tag, profile, text, target)
        elif tag.endswith("runtime-api"):
            if "Runtime API contract check UNRUN:" in text:
                result["outcome"] = "UNRUN"
            else:
                require(
                    "Runtime API contract check passed (" in text
                    or "Runtime API contract check FAILED:" in text,
                    "Runtime API completion",
                )
            result["violations"] = re.findall(r"^- (.*)$", text, re.MULTILINE)
            result["not_measured"] = (
                "Endpoint/auth/client behavior, production deployment, hosted CI."
            )
            result["client_comparison_input"] = (
                "Committed OpenAPI, not regenerated drifted OpenAPI."
            )
        elif tag.endswith("production-invocation"):
            diagnostic = json.loads(text)
            result["diagnostic"] = diagnostic
            require(
                diagnostic["runtime_invocation_established"] is False, "Unexpected runtime grade"
            )
            receipt = Path(diagnostic["receipt"])
            reader.file(receipt)
            result["full_receipt"] = reader.reads[str(receipt)]
            result["qualification"] = "Static diagnosis only; full raw receipt remains ignored."
        elif tag.endswith("architecture"):
            require("Architecture guardrail check" in text, "Architecture completion")
            result["reported_failure_lines"] = re.findall(r"^- (.*)$", text, re.MULTILINE)
            result["explicit_unrun_lines"] = [
                line for line in text.splitlines() if "not run by" in line or "UNRUN" in line
            ]
        else:
            xml = raw / (tag + ".xml")
            # This reader accepts only local root-produced JUnit, not untrusted network XML.
            document = ElementTree.fromstring(reader.file(xml))  # noqa: S314
            cases = document.findall(".//testcase")
            counts: Counter[str] = Counter()
            for case in cases:
                skipped = case.find("skipped")
                state = (
                    "ERROR"
                    if case.find("error") is not None
                    else "FAIL"
                    if case.find("failure") is not None
                    else "PASS"
                )
                if skipped is not None:
                    state = "XFAIL" if skipped.get("type") == "pytest.xfail" else "SKIP"
                counts[state] += 1
            result["junit_counts"] = dict(counts)
            result["case_denominator"] = len(cases)
            result["qualification"] = (
                "JUnit case accounting; phase inventory and warnings need separate "
                "full observer review."
            )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        if not result.get("target_bound") or result["outcome"] == "PASS":
            result["outcome"] = "UNRUN"
        result["accounting_state"] = "UNRUN"
        result["audit_boundary"] = repr(exc)
        reader.unresolved.append(
            {"class": "gate_accounting_not_established", "tag": tag, "error": repr(exc)}
        )
    return result


def main() -> None:
    """Read the complete declared gate set and emit a bounded audit receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--target-sha", required=True)
    parser.add_argument("--prefix", default="repaired-final")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", args.target_sha)), "Supply an exact SHA")
    reader = Reader(args.root)
    reader.file(Path(__file__).absolute())
    tree = reader.git("rev-parse", args.target_sha + "^{tree}").decode().strip()
    source = reader.git("show", args.target_sha + ":" + LAUNCHER)
    reader.git("show", args.target_sha + ":" + CAPTURE)
    tags = tags_from_source(source, args.prefix)
    universe = reader.git("ls-tree", "-r", "--name-only", args.target_sha).decode().splitlines()
    gates = [gate_audit(reader, args.raw, tag, args.target_sha, tree) for tag in tags]
    report = {
        "schema": "policyos.e02.gate_execution_independent_audit.v2",
        "audit_utc": datetime.now(UTC).isoformat(),
        "target_source_sha": args.target_sha,
        "target_tree_sha": tree,
        "observed_head": reader.git("rev-parse", "HEAD").decode().strip(),
        "reader_environment": {"executable": sys.executable, "version": sys.version},
        "selector": {
            "source": LAUNCHER + "@" + args.target_sha,
            "prefix": args.prefix,
            "tags": tags,
            "denominator": len(tags),
        },
        "source_universe": {
            "command": ["git", "ls-tree", "-r", "--name-only", args.target_sha],
            "count": len(universe),
            "by_suffix": dict(Counter(Path(p).suffix or "<none>" for p in universe)),
            "not_dynamic_read_set": True,
        },
        "gates": gates,
        "gate_counts": dict(Counter(str(row["outcome"]) for row in gates)),
        "explicit_reads": list(reader.reads.values()),
        "unresolved_by_construction": reader.unresolved
        + [
            {
                "class": "dynamic_gate_read_set",
                "property": (
                    "Complete runtime imports, installed binary content, service and backend "
                    "reads were not reconstructed."
                ),
            },
            {
                "class": "inherited_failure_attribution",
                "property": (
                    "No slice-base same-command replay or zero input overlap proof; "
                    "P41 waiver not established."
                ),
            },
            {
                "class": "product_acceptance",
                "property": (
                    "Execution accounting does not independently accept the author's "
                    "production mechanism or served production."
                ),
            },
        ],
        "measurement": (
            "Explicit existing-file/Git reads only; no gate, pytest, product import, "
            "environment sync, or source edits."
        ),
        "rss_qualification": "wait4 child rusage, not an aggregate of concurrent gates.",
        "closure_ids": [],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    sys.stdout.write(
        json.dumps({"report": str(args.out), "gate_counts": report["gate_counts"]}) + "\n"
    )


if __name__ == "__main__":
    main()
