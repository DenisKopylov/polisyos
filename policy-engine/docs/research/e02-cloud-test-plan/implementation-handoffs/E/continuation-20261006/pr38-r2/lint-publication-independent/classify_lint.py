#!/usr/bin/env python3
"Read-only exact-Git lint-output classifier; never launches Ruff/native checks."

import ast
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath


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


REPO = Path("/workspace/e02-E-continuation-20261006")
HERE = Path(__file__).resolve().parent
PUBLICATION = "eb035c0785a63c9c2a6d8991e2503a6a5117a1aa"
SOURCE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
BASE = "198076863e143dea9f89f02734b13d50dae3eed5"
PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
WAVE = PREFIX + "E/continuation-20261006/pr38-r2/failed-wave-5e/"
inputs = {}


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


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(REPO), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def blob(sha: str, path: object) -> object:
    value = git("show", sha + ":" + path)
    inputs[(sha, path)] = {
        "source_sha": sha,
        "path": path,
        "git_blob": git("rev-parse", sha + ":" + path).decode().strip(),
        "bytes": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }
    return value


def load(sha: str, path: object) -> object:
    return json.loads(blob(sha, path))


def emit(path: object, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parse_ruff(stdout: str) -> object:
    text = stdout.decode("utf-8")
    headers = list(re.finditer(r"^([A-Z]+\d+) (.+)$", text, re.M))
    rows = []
    for i, header in enumerate(headers):
        block = text[header.end() : headers[i + 1].start() if i + 1 < len(headers) else len(text)]
        location = re.findall(r"^\s*--> (.+):(\d+):(\d+)\s*$", block, re.M)
        if len(location) != 1:
            raise ValueError("Each actual diagnostic must have one exact location")
        path, line, column = location[0]
        rows.append(
            {
                "path": path,
                "line": int(line),
                "column": int(column),
                "code": header.group(1),
                "message": header.group(2),
            }
        )
    summary = re.findall(r"^Found (\d+) errors\.$", text, re.M)
    if len(summary) != 1 or int(summary[0]) != len(rows):
        raise ValueError("Full stdout summary disagrees with parsed diagnostic denominator")
    return rows


def parse_format(stdout: str) -> tuple[object, ...]:
    text = stdout.decode("utf-8")
    paths = re.findall(r"^Would reformat: (.+)$", text, re.M)
    summary = re.findall(
        r"^(\d+) files would be reformatted, (\d+) files already formatted$", text, re.M
    )
    if len(summary) != 1 or int(summary[0][0]) != len(paths) or len(set(paths)) != len(paths):
        raise ValueError("Full formatter stdout summary/path denominator disagrees")
    return paths, int(summary[0][1])


def norm_copied(index_path: object, item_path: object) -> object:
    path = PurePosixPath(item_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    if item_path.startswith("policy-engine/"):
        return item_path
    if item_path.startswith("docs/"):
        return "policy-engine/" + item_path
    return str(PurePosixPath(index_path).parent / path)


def index_records(value: object) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("sha256"), str) and isinstance(value.get("bytes"), int):
            for field in ["copied_path", "path", "destination_path", "relative_path"]:
                if isinstance(value.get(field), str):
                    yield value, value[field]
                    break
        for child in value.values():
            yield from index_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from index_records(child)


def usage_axis(path: object) -> str:
    name = PurePosixPath(path).name
    if "/harness-author-v2/" in path:
        return "operational_wave_harness"
    if re.search(r"(probe|falsifier|control|tests|removal|readback|replay)", name, re.I):
        return "runnable_witness_or_adversarial_control"
    return "runnable_receipt_review_or_assembly_utility"


def history_axis(path: object) -> str:
    if re.search(r"/(historical[^/]*|git-inputs-[^/]+)/", path) or re.search(
        r"(\.initial\.|\.attempt\d+\.|old58|old5d|old-c0f)", path
    ):
        return "explicit_historical_copy"
    return "published_source_bound_control_or_utility"


def validate(report: object, actual: object) -> str:
    if report["source_sha"] != SOURCE or report["publication_sha"] != PUBLICATION:
        raise ValueError("Source/publication identity changed")
    if report["denominator"] != actual["denominator"]:
        raise ValueError("Full changed Python denominator changed")
    if report["ruff"] != actual["ruff"] or report["format"] != actual["format"]:
        raise ValueError("Diagnostic or format counts/classes differ from full stdout")
    if report["paths"] != actual["paths"]:
        raise ValueError("Exact path/code/custody/usage rows changed or omitted")
    for row in report["paths"]:
        if row["path"] not in report["denominator"]["paths"]:
            raise ValueError("Reported diagnostic path escapes admitted denominator")
    return "ACCEPTED_exact_read_only_metadata"


def main() -> None:
    plan = load(PUBLICATION, WAVE + "plan.json")
    check = load(PUBLICATION, WAVE + "checks/ruff/ruff.json")
    formatter = load(PUBLICATION, WAVE + "checks/ruff-format/ruff-format.json")
    stdout = blob(PUBLICATION, WAVE + "checks/ruff/ruff.stdout.txt")
    format_stdout = blob(PUBLICATION, WAVE + "checks/ruff-format/ruff-format.stdout.txt")
    for receipt, value in [(check, stdout), (formatter, format_stdout)]:
        if (
            receipt["candidate_sha"] != SOURCE
            or receipt["stdout_bytes"] != len(value)
            or receipt["stdout_sha256"] != hashlib.sha256(value).hexdigest()
        ):
            raise ValueError("Actual stdout hash/size/source disagrees with receipt")
    denominator = plan["changed_python_lint_paths"]
    if (
        len(denominator) != 231
        or len(set(denominator)) != 231
        or any(
            not p.endswith(".py")
            or PurePosixPath(p).is_absolute()
            or ".." in PurePosixPath(p).parts
            for p in denominator
        )
    ):
        raise ValueError("Canonical full231 Python denominator admission failed")
    if check["command"][4:] != denominator or formatter["command"][5:] != denominator:
        raise ValueError("Actual Ruff/format argv differs from exact full plan denominator")
    delta = (
        git("diff", "--name-only", "--diff-filter=ACMR", BASE, SOURCE, "--", "policy-engine/")
        .decode()
        .splitlines()
    )
    changed = sorted(p.removeprefix("policy-engine/") for p in delta if p.endswith(".py"))
    if changed != sorted(denominator):
        raise ValueError("Recomputed exact base->candidate changed Python paths differ from plan")
    diagnostics = parse_ruff(stdout)
    format_paths, already_formatted = parse_format(format_stdout)
    if any(r["path"] not in denominator for r in diagnostics) or any(
        p not in denominator for p in format_paths
    ):
        raise ValueError("Actual output path escapes full command denominator")
    affected = sorted({r["path"] for r in diagnostics} | set(format_paths))
    tree_paths = git("ls-tree", "-r", "--name-only", SOURCE, PREFIX).decode().splitlines()
    index_paths = [
        p
        for p in tree_paths
        if p.endswith("/portable-copy-index.json") or p.endswith("/copy-index.json")
    ]
    indexed = {}
    for path in index_paths:
        value = load(SOURCE, path)
        for record, name in index_records(value):
            candidate = norm_copied(path, name)
            if candidate:
                indexed.setdefault(candidate, []).append(
                    {
                        "index_ref": path + "@" + SOURCE,
                        "bytes": record["bytes"],
                        "sha256": record["sha256"],
                        "stage": record.get("stage"),
                        "copy_mode": record.get("copy_mode"),
                    }
                )
    per_path = []
    semantic_context = []
    for path in affected:
        full = "policy-engine/" + path
        data = blob(SOURCE, full)
        identity = inputs[(SOURCE, full)]
        matches = [
            r
            for r in indexed.get(full, [])
            if r["bytes"] == identity["bytes"] and r["sha256"] == identity["sha256"]
        ]
        entries = [r for r in diagnostics if r["path"] == path]
        parsed = ast.parse(data.decode("utf-8"), filename=path)
        swaps = [
            n.lineno
            for n in ast.walk(parsed)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Attribute) and t.attr == "__code__" for t in n.targets)
        ]
        per_path.append(
            {
                "path": path,
                "identity": identity,
                "diagnostic_count": len(entries),
                "codes": dict(sorted(Counter(r["code"] for r in entries).items())),
                "would_reformat": path in format_paths,
                "location_class": "docs_implementation_handoff",
                "usage_axis": usage_axis(path),
                "history_axis": history_axis(path),
                "matching_copy_index_records": matches,
                "copy_index_custody": "exact_hash_size_matched"
                if matches
                else "direct_exact_Git_blob_only_no_matched_copy_index",
                "code_object_replacement_lines": sorted(swaps),
            }
        )
        if any(r["code"] == "F821" for r in entries):
            semantic_context.append(
                {
                    "path": path,
                    "diagnostics": [r for r in entries if r["code"] == "F821"],
                    "code_object_replacement_lines": sorted(swaps),
                    "scope": (
                        "Static undefined names are in recorded c"
                        "ode-removal function bodies assigned via"
                        " __code__; canonical target globals are "
                        "resolved separately below. No fresh runt"
                        "ime PASS is inferred."
                    ),
                }
            )
    owner_sources = [
        "policy-engine/src/polisyos/foundry/calibration/report.py",
        "policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py",
    ]
    owner_globals = []
    for path in owner_sources:
        data = blob(SOURCE, path)
        module = ast.parse(data.decode("utf-8"))
        names = set()
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Import):
                names.update(a.asname or a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.asname or a.name for a in node.names)
        owner_globals.append(
            {
                "path": path,
                "identity": inputs[(SOURCE, path)],
                "CalibrationReport_defined": "CalibrationReport" in names,
                "numbers_imported": "numbers" in names,
                "basis": (
                    "Exact source module top-level AST only; runtime/function glo"
                    "bal rebinding not executed by this audit"
                ),
            }
        )
    report = {
        "schema": "policyos.e02.actual5e.lint-publication-debt.independent.v1",
        "source_sha": SOURCE,
        "source_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(),
        "publication_sha": PUBLICATION,
        "base_sha": BASE,
        "disposition": (
            "Confirmed current failed5e lint/publication debt; no gate waiver or finding closure"
        ),
        "denominator": {
            "count": 231,
            "paths": denominator,
            "recomputed_exact_base_delta": True,
            "plan_ref": WAVE + "plan.json@" + PUBLICATION,
            "commands_exact_full_scope": True,
            "scope": (
                "AllACMRchanged.py underpolicy-engine bas"
                "e198->candidate5e, includingpublishedcop"
                "iedcontrols andproduct/tests; no narrowi"
                "ng"
            ),
        },
        "ruff": {
            "outcome": "FAIL",
            "exit_code": 1,
            "diagnostics": len(diagnostics),
            "unique_paths": len({r["path"] for r in diagnostics}),
            "code_classes": len({r["code"] for r in diagnostics}),
            "codes": dict(sorted(Counter(r["code"] for r in diagnostics).items())),
            "stdout_identity": inputs[(PUBLICATION, WAVE + "checks/ruff/ruff.stdout.txt")],
        },
        "format": {
            "outcome": "FAIL",
            "exit_code": 1,
            "would_reformat": len(format_paths),
            "already_formatted": already_formatted,
            "paths": format_paths,
            "stdout_identity": inputs[
                (PUBLICATION, WAVE + "checks/ruff-format/ruff-format.stdout.txt")
            ],
        },
        "paths": per_path,
        "scope_classification": {
            "docs_handoff_affected_paths": len(per_path),
            "outside_docs_affected_paths": sum(not p["path"].startswith("docs/") for p in per_path),
            "product_src_affected_paths": sum(p["path"].startswith("src/") for p in per_path),
            "repository_test_affected_paths": sum(p["path"].startswith("tests/") for p in per_path),
            "repository_tool_affected_paths": sum(p["path"].startswith("tools/") for p in per_path),
            "usage_counts": dict(Counter(p["usage_axis"] for p in per_path)),
            "history_counts": dict(Counter(p["history_axis"] for p in per_path)),
            "copy_index_hash_matched_paths": sum(
                bool(p["matching_copy_index_records"]) for p in per_path
            ),
            "direct_Git_only_paths": sum(not p["matching_copy_index_records"] for p in per_path),
            "axes_rule": (
                "Custody/history and runnable-purpose are"
                " distinct. Docs location doesnotestablis"
                "hinertness; exactcopyhash doesnotexempto"
                "perationalPythonfromchecks."
            ),
        },
        "current_wave_harness_scope": [
            {
                "path": p,
                "diagnostics": sum(r["path"] == p for r in diagnostics),
                "would_reformat": p in format_paths,
                "planned": p in denominator,
            }
            for p in denominator
            if "/harness-author-v2/" in p
        ],
        "F821_code_object_context": semantic_context,
        "canonical_owner_global_source": owner_globals,
        "claim_limits": [
            ("FullRuff output classified, no new Ruff/format/native/gate command launched"),
            (
                "No source/style/renaming/deletion/exception/baseline change;"
                " exacthistoricalstdout/history preserved"
            ),
            (
                "S/B/F/PT annotations fromlint are static"
                "proxies; theyneedcontextualreview, notbl"
                "anketcosmetic orrealruntimebugclassifica"
                "tion"
            ),
            (
                "ExactbaseASTdiff verifies231paths; exactbase Ruff/format rep"
                "laynotrun, P41 inheritedred/notnew remainsnot_established"
            ),
            (
                "Current failed5e facts applyonly5e; no correctedfreeze numer"
                "icPASS orfindingstatusreclassification"
            ),
        ],
        "next_owner": (
            "E root/canonical evidence publication writer; independentrev"
            "iewer distinctfrom formatted operational author; G integrati"
            "on reviewer fornext candidate gate receipt"
        ),
        "next_protocol": [
            (
                "Preserve original5e stdout, scripts, source/hash indexes and"
                " historicalreview receipts byteforbyte"
            ),
            (
                "Classify currentoperational reusablecont"
                "rols vs preservedhistorical copies using"
                "exact consumer/caller, then append a mai"
                "ntained formatted/typed operationalversi"
                "on with sourceparent/candidate refs; do "
                "notrenamesuffix or exclude231denominator"
                " tohidefailedgate"
            ),
            (
                "Use semantic review for __code__ globalc"
                "ontext andnonstyle S/B/F/PT classes; do "
                "notblind unsafe-fix historicalcontrol lo"
                "gic"
            ),
            (
                "If operationalPython changes, run affect"
                "edactual control/oracle/removal and reco"
                "mpute canonical lint/format withcomplete"
                " changed.py denominator atnewcandidate; "
                "updatecopy/hash/size refs innew correcti"
                "veversion"
            ),
            (
                "Cosmetic postfreeze publication debt may"
                " be handedoff explicitly as userallowed;"
                " requiredgate remainsFAIL untilactualful"
                "lscopecheckpasses. No root waiver/findin"
                "g closure bylintsummary"
            ),
        ],
        "cleanup": (
            "No cleanup/deletion; repeatablemetadata scratchcandidate may"
            " only move to nativeTrash after receipts/noactiveusers; clou"
            "dwithoutTrash preserves andlists"
        ),
    }
    expected = copy.deepcopy(report)
    positive = validate(report, expected)
    negatives = []
    mutations = [
        ("fake_denominator_104", lambda r: r["denominator"].__setitem__("count", 104)),
        ("omit_actual_path", lambda r: r["paths"].pop()),
        (
            "forge_product_path",
            lambda r: r["paths"][0].__setitem__("path", "src/polisyos/calibration/__init__.py"),
        ),
        (
            "rename_hiding.py.txt",
            lambda r: r["paths"][0].__setitem__("path", r["paths"][0]["path"] + ".txt"),
        ),
        ("forge_ruff_count", lambda r: r["ruff"].__setitem__("diagnostics", 5315)),
        ("forge_format_already128", lambda r: r["format"].__setitem__("already_formatted", 129)),
        (
            "forge_copy_source_digest",
            lambda r: r["paths"][0]["identity"].__setitem__("sha256", "0" * 64),
        ),
    ]
    for name, mutate in mutations:
        forged = copy.deepcopy(report)
        mutate(forged)
        try:
            validate(forged, expected)
        except ValueError as error:
            negatives.append(
                {
                    "control": name,
                    "outcome": "REFUSED",
                    "reason": str(error),
                    "native_or_gate_calls": 0,
                }
            )
        else:
            raise ValueError("Present-but-fake lint metadata admitted:" + name)
    report["metadata_verification"] = {
        "positive": positive,
        "negative_count": len(negatives),
        "negative_controls_ref": "corrupt-controls.json",
        "independence": (
            "Lint-output classification author is not originalgate produc"
            "er/control author; no closure or code author selfapproval"
        ),
    }
    emit(HERE / "classification.json", report)
    emit(HERE / "corrupt-controls.json", negatives)
    emit(
        HERE / "input-index.json",
        {
            "inputs": list(inputs.values()),
            "source_rule": (
                "Only exact tracked5e original source and"
                " publishedeb originalfullstdout/plan/rec"
                "eipts; ignoredraw/privates are neverread"
            ),
        },
    )
    _write_stdout(
        json.dumps(
            {
                "source": SOURCE,
                "publication": PUBLICATION,
                "ruff": {
                    "diagnostics": len(diagnostics),
                    "unique_paths": len({r["path"] for r in diagnostics}),
                    "codes": len({r["code"] for r in diagnostics}),
                },
                "format": {"would": len(format_paths), "already": already_formatted},
                "scope": report["scope_classification"],
                "corrupt_controls": len(negatives),
                "inputs": len(inputs),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
