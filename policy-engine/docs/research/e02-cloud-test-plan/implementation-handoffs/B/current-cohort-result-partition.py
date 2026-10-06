"""Partition one completed real pytest inventory without executing pytest.

Inputs must be the same completed root invocation: inventory, native JUnit, wait4
wrapper, stdout, profile and full selector manifest. Complete case/phase details
are written only to a fresh explicitly Git-ignored output. This observation never
admits a finding, an unavailable backend or an unmeasured resource read-set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

type Record = dict[str, Any]

_STATES = ("PASS", "FAIL", "ERROR", "XFAIL", "SKIP", "UNRUN")


def _object(value: object) -> Record:
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _objects(value: object) -> list[Record]:
    if not isinstance(value, list):
        raise ValueError("Expected a JSON object list")
    return [_object(row) for row in value]


def _input(path: Path) -> tuple[bytes, Record]:
    data = path.read_bytes()
    return data, {
        "path": str(path.resolve()),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _json_input(path: Path) -> tuple[Record, Record]:
    data, identity = _input(path)
    return _object(json.loads(data)), identity


def _phase(report: Record) -> str:
    outcome = report["outcome"]
    if outcome == "passed":
        return "PASS"
    if outcome == "failed":
        return "FAIL" if report["when"] == "call" else "ERROR"
    if outcome == "skipped":
        return "XFAIL" if report.get("classification") == "xfail" else "SKIP"
    return "UNRUN"


def _case(item: Record, indexes: list[int], reports: list[Record], duplicate: bool) -> Record:
    phases: dict[str, list[int]] = {phase: [] for phase in ("setup", "call", "teardown")}
    unknown = []
    for index in indexes:
        phase = reports[index]["when"]
        if phase in phases:
            phases[phase].append(index)
        else:
            unknown.append(index)
    ambiguous = duplicate or bool(unknown) or any(len(v) > 1 for v in phases.values())
    setup = reports[phases["setup"][0]] if len(phases["setup"]) == 1 else None
    complete = (
        not ambiguous
        and len(phases["setup"]) == len(phases["teardown"]) == 1
        and (
            len(phases["call"]) == 1
            if setup and setup["outcome"] == "passed"
            else not phases["call"]
        )
    )
    assigned = [reports[index] for index in indexes]
    if ambiguous:
        state, reason = "UNRUN", "physical attempt assignment ambiguous"
    elif any(r["outcome"] == "failed" and r["when"] in {"setup", "teardown"} for r in assigned):
        state, reason = "ERROR", "observed setup/teardown failure"
    elif any(r["outcome"] == "failed" and r["when"] == "call" for r in assigned):
        state, reason = "FAIL", "observed call failure including strict XPASS"
    elif not complete:
        state, reason = "UNRUN", "normal terminal attempt incomplete"
    elif any(_phase(r) == "SKIP" for r in assigned):
        state, reason = "SKIP", "ordinary phase skip"
    elif any(_phase(r) == "XFAIL" for r in assigned):
        state, reason = "XFAIL", "actual evaluated expected-failure phase"
    elif all(r["outcome"] == "passed" for r in assigned):
        state, reason = "PASS", "complete normal all-passed attempt"
    else:
        state, reason = "UNRUN", "unknown outcome profile"
    return {
        "nodeid": item["nodeid"],
        "path": item["path"],
        "location": item["location"],
        "state": state,
        "reason": reason,
        "complete": complete,
        "assignment_ambiguous": ambiguous,
        "phase_report_indexes": phases,
        "unknown_phase_report_indexes": unknown,
        "phase_states": {
            key: [_phase(reports[index]) for index in value] or ["UNRUN"]
            for key, value in phases.items()
        },
        "unexpected_success_nonstrict": any(r.get("classification") == "xpass" for r in assigned),
        "unexpected_success_strict": any(
            r.get("classification") == "strict_xpass" for r in assigned
        ),
    }


def _xml_name(value: str) -> str:
    # Exact inspected pytest9 bin_xml_escape character ranges, not reason parsing.
    pattern = "[^\u0009\u000a\u000d\u0020-\u007e\u0080-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
    return re.sub(
        pattern, lambda m: f"#x{ord(m[0]):02X}" if ord(m[0]) <= 255 else f"#x{ord(m[0]):04X}", value
    )


def _xml_key(nodeid: str, prefix: str | None) -> tuple[str, str]:
    path, bracket, params = nodeid.partition("[")
    names = path.split("::")
    names[0] = re.sub(r"\.py$", "", names[0].replace("/", "."))
    names[-1] += bracket + params
    classes = names[:-1]
    if prefix:
        classes.insert(0, prefix)
    return ".".join(classes), _xml_name(names[-1])


def _junit(
    data: bytes, cases: list[Record], collectors: list[Record], prefix: str | None
) -> Record:
    root = ET.fromstring(data)  # noqa: S314 - explicit native pytest artifact input
    case_map: dict[tuple[str, str], list[str]] = defaultdict(list)
    collector_map: dict[tuple[str, str], list[int]] = defaultdict(list)
    for case in cases:
        case_map[_xml_key(case["nodeid"], prefix)].append(case["nodeid"])
    for index, report in enumerate(collectors):
        if report["outcome"] != "passed":
            collector_map[_xml_key(report["nodeid"], prefix)].append(index)
    entries: list[Record] = []
    for index, element in enumerate(root.iter("testcase")):
        key = element.get("classname", ""), element.get("name", "")
        candidate_cases, candidate_collectors = case_map.get(key, []), collector_map.get(key, [])
        target: Record = {"state": "unmatched"}
        if len(candidate_cases) == 1 and not candidate_collectors:
            target = {"state": "case", "nodeid": candidate_cases[0]}
        elif not candidate_cases and len(candidate_collectors) == 1:
            target = {"state": "collector", "collection_report_index": candidate_collectors[0]}
        elif key == ("pytest", "internal") and not candidate_cases and not candidate_collectors:
            target = {"state": "synthetic_internal_error"}
        elif candidate_cases or candidate_collectors:
            target = {
                "state": "ambiguous",
                "case_nodeids": candidate_cases,
                "collection_report_indexes": candidate_collectors,
            }
        entries.append(
            {
                "index": index,
                "classname": key[0],
                "name": key[1],
                "target": target,
                "result_elements": [
                    {"tag": child.tag, "type": child.get("type")}
                    for child in element
                    if child.tag in {"failure", "error", "skipped"}
                ],
            }
        )
    return {
        "suite_attributes": [dict(node.attrib) for node in root.iter("testsuite")],
        "entries": entries,
        "representation_count": len(entries),
        "mapping_counts": dict(Counter(row["target"]["state"] for row in entries)),
    }


def _result_tag(report: Record) -> tuple[str, str | None] | None:
    if report["outcome"] == "failed":
        if report.get("has_wasxfail") and report["when"] == "call":
            return "skipped", None
        return ("failure", None) if report["when"] == "call" else ("error", None)
    if report["outcome"] == "skipped":
        return "skipped", "pytest.xfail" if report.get("has_wasxfail") else "pytest.skip"
    return None


def _xml_agreement(
    xml: Record, cases: list[Record], reports: list[Record], collectors: list[Record]
) -> Record:
    by_case: dict[str, list[Record]] = defaultdict(list)
    by_collector: dict[int, list[Record]] = defaultdict(list)
    for entry in xml["entries"]:
        target = entry["target"]
        if target["state"] == "case":
            by_case[target["nodeid"]].append(entry)
        elif target["state"] == "collector":
            by_collector[target["collection_report_index"]].append(entry)
    mismatches = []
    for case in cases:
        indexes = [i for values in case["phase_report_indexes"].values() for i in values]
        indexes += case["unknown_phase_report_indexes"]
        assigned = [reports[i] for i in indexes]
        expected = Counter(tag for r in assigned if (tag := _result_tag(r)) is not None)
        actual = Counter(
            (child["tag"], child["type"])
            for entry in by_case[case["nodeid"]]
            for child in entry["result_elements"]
        )
        double_failure = any(
            r["when"] == "call" and r["outcome"] == "failed" for r in assigned
        ) and any(r["when"] == "teardown" and r["outcome"] == "failed" for r in assigned)
        expected_rows = 2 if double_failure else int(bool(assigned))
        actual_rows = len(by_case[case["nodeid"]])
        if expected != actual or expected_rows != actual_rows:
            mismatches.append(
                {
                    "nodeid": case["nodeid"],
                    "expected_result_tags": repr(expected),
                    "actual_result_tags": repr(actual),
                    "expected_xml_rows": expected_rows,
                    "actual_xml_rows": actual_rows,
                }
            )
        case["junit_representation_indexes"] = [row["index"] for row in by_case[case["nodeid"]]]
    collector_mismatches = []
    for index, report in enumerate(collectors):
        if report["outcome"] == "passed":
            continue
        expected_tag = "error" if report["outcome"] == "failed" else "skipped"
        rows = by_collector[index]
        collector_actual = [
            (child["tag"], child["type"]) for row in rows for child in row["result_elements"]
        ]
        if len(rows) != 1 or collector_actual != [(expected_tag, None)]:
            collector_mismatches.append(
                {
                    "collection_report_index": index,
                    "expected_tag": expected_tag,
                    "actual_tags": collector_actual,
                    "actual_xml_rows": len(rows),
                }
            )
    return {
        "case_projection_mismatches": mismatches,
        "collector_projection_mismatches": collector_mismatches,
        "all_native_case_projections_match": not mismatches,
        "all_native_collector_projections_match": not collector_mismatches,
    }


def _origins(inventory: Record) -> Record:
    origins = _object(inventory.get("module_origin_snapshot"))
    modules, files = (
        _objects(origins["observed_modules"]),
        _objects(origins["observed_file_backends"]),
    )
    return {
        "module_entry_denominator": len(modules),
        "distinct_file_backend_denominator": len(files),
        "recorded_denominator_match": len(modules) == origins["module_entry_denominator"]
        and len(files) == origins["distinct_file_backend_denominator"],
        "module_states": dict(Counter(row["state"] for row in modules)),
        "file_scopes": dict(Counter(row["scope"] for row in files)),
        "file_backends": dict(Counter(row["backend"] for row in files)),
        "file_types": dict(Counter(Path(row["path"]).suffix or "extensionless" for row in files)),
        "read_states": dict(Counter(row["actual_read"]["state"] for row in files)),
        "git_byte_match": dict(Counter(str(row["source_git_byte_match"]) for row in files)),
        "nonmatching_or_unreadable_file_indexes": [
            i
            for i, row in enumerate(files)
            if row["source_git_byte_match"] is False or row["actual_read"]["state"] != "read"
        ],
        "loaded_instrument_source_git_byte_match": origins[
            "loaded_instrument_source_git_byte_match"
        ],
        "boundary": (
            "Hook-time declared origins/backing bytes only; no loader read-set, "
            "after-finalization, child, transient or resource/service census."
        ),
    }


def _prefix(command: list[str]) -> str | None:
    for index, arg in enumerate(command):
        if arg.startswith(("--junitprefix=", "--junit-prefix=")):
            return arg.split("=", 1)[1]
        if arg in {"--junitprefix", "--junit-prefix"}:
            return command[index + 1]
    return None


def _partition(args: argparse.Namespace) -> Record:
    inventory, inv_id = _json_input(args.inventory)
    if (
        inventory.get("schema") != "policyos.e02.pytest_inventory.v1"
        or inventory.get("state") != "session_finished"
    ):
        raise ValueError(
            "Complete sessionfinish artifact required; do not parse a running checkpoint"
        )
    wrapper, wrapper_id = _json_input(args.wrapper)
    profile, profile_id = _json_input(args.profile)
    selectors, selectors_id = _json_input(args.selectors)
    junit, junit_id = _input(args.junit)
    _, stdout_id = _input(args.stdout)
    items, reports, collectors = (
        _objects(inventory[key])
        for key in ("session_items_before_execution", "runtime_phase_reports", "collection_reports")
    )
    ids = Counter(item["nodeid"] for item in items)
    report_indexes: dict[str, list[int]] = defaultdict(list)
    for index, report in enumerate(reports):
        report_indexes[report["nodeid"]].append(index)
    seen = set()
    cases = []
    for item in items:
        nodeid = item["nodeid"]
        if nodeid in seen:
            continue
        seen.add(nodeid)
        cases.append(_case(item, report_indexes[nodeid], reports, ids[nodeid] != 1))
    case_counts = dict.fromkeys(_STATES, 0)
    case_counts.update(Counter(row["state"] for row in cases))
    by_collection_file: dict[str, Counter[str]] = defaultdict(Counter)
    by_definition_path: dict[str, Counter[str]] = defaultdict(Counter)
    file_relations: Counter[tuple[str, str]] = Counter()
    mismatching_case_indices = []
    rootpath = Path(inventory["rootpath"])
    for index, case in enumerate(cases):
        collection, definition = case["path"], case["location"][0]
        by_collection_file[collection][case["state"]] += 1
        by_definition_path[definition][case["state"]] += 1
        file_relations[collection, definition] += 1
        collection_path, definition_path = Path(collection), Path(definition)
        if not collection_path.is_absolute():
            collection_path = rootpath / collection_path
        if not definition_path.is_absolute():
            definition_path = rootpath / definition_path
        same_lexical_path = os.path.normpath(str(collection_path)) == os.path.normpath(
            str(definition_path)
        )
        case["collection_file"] = collection
        case["definition_path"] = definition
        case["same_lexical_collection_and_definition_path"] = same_lexical_path
        if not same_lexical_path:
            mismatching_case_indices.append(index)
    checks = {
        "pytest_source_profile": inventory["pytest_version"] == "9.0.2",
        "plain_single_process_observation": inventory["worker_id"] is None
        and not inventory["xdist_worker_collection_reports"],
        "phase_annotations_present": all(
            "classification" in row and "has_wasxfail" in row for row in reports
        ),
        "session_count_binding": inventory["session_testscollected"] == len(items),
        "wrapper_source": wrapper["head"] == wrapper["head_after"] == args.source_sha,
        "profile_source": profile["sha"] == selectors["root_snapshot_sha"] == args.source_sha,
        "same_source_tree": wrapper["tree"] == profile["tree"] == selectors["root_snapshot_tree"],
        "observer_start_source": inventory["git_at_start"]["head"] == args.source_sha,
        "observer_finish_source": inventory["git_at_finish"]["head"] == args.source_sha,
        "observer_source_tree": inventory["git_at_start"]["tree"]
        == inventory["git_at_finish"]["tree"]
        == wrapper["tree"],
        "same_command": wrapper["command"] == profile["argv"],
        "same_cwd": wrapper["cwd"] == profile["cwd"],
        "stdout_binding": wrapper["output_sha256"] == stdout_id["sha256"]
        and Path(wrapper["output_path"]).resolve() == args.stdout.resolve(),
        "selector_hash_binding": profile["inputs"]["selector_sha256"] == selectors_id["sha256"],
        "selector_list_binding": profile["inputs"]["test_paths"]
        == selectors["test_paths"]
        == inventory["selectors"],
        "selector_denominator": len(selectors["test_paths"])
        == len(set(selectors["test_paths"]))
        == selectors["candidate_whole_file_count"],
        "case_identity_unique": all(n == 1 for n in ids.values()),
        "case_partition_total": sum(case_counts.values()) == len(ids),
        "case_file_groupings_complete": sum(sum(v.values()) for v in by_collection_file.values())
        == sum(sum(v.values()) for v in by_definition_path.values())
        == sum(file_relations.values())
        == len(cases),
        "all_reports_have_admitted_nodeid": all(row["nodeid"] in ids for row in reports),
        "same_junit_path": Path(inventory["junit_path"]).resolve() == args.junit.resolve(),
    }
    origins = _origins(inventory)
    xml = _junit(junit, cases, collectors, _prefix(wrapper["command"]))
    xml_agreement = _xml_agreement(xml, cases, reports, collectors)
    checks.update(
        native_xml_case_projection=xml_agreement["all_native_case_projections_match"],
        native_xml_collector_projection=xml_agreement["all_native_collector_projections_match"],
        origins_recorded_denominators=origins["recorded_denominator_match"],
        instrument_byte_match=origins["loaded_instrument_source_git_byte_match"] is True,
        every_xml_representation_assigned=not any(
            row["target"]["state"] in {"unmatched", "ambiguous"} for row in xml["entries"]
        ),
    )
    return {
        "schema": "policyos.e02.case_partition.v1",
        "interpretation_guide": {
            "source_sha": "b766309e4cf887fbd2b4bcea13e59d4dc16831f8",
            "path": (
                "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
                "current-cohort-inventory-consumer-guide.json"
            ),
            "sha256": "a98693e2dfeedc16f4ca34624c0ace0411d6c86cc7ed4cdbf96a1ad6c3226f13",
        },
        "predicate_basis": "recomputed",
        "claim_grade": "complete observed-report interpretation, not property/finding admission",
        "source_sha": args.source_sha,
        "source_tree": wrapper["tree"],
        "input_identities": {
            "inventory": inv_id,
            "wrapper": wrapper_id,
            "profile": profile_id,
            "selectors": selectors_id,
            "junit": junit_id,
            "stdout": stdout_id,
        },
        "reconciliation_checks": checks,
        "parse_state": "COMPLETE" if all(checks.values()) else "UNRESOLVED_BINDINGS_OR_IDENTITIES",
        "session": {
            "observer_state": inventory["state"],
            "observed_sessionfinish_exitstatus_argument": inventory["session_exitstatus"],
            "actual_wait4_exit_code": wrapper["exit_code"],
            "hook_argument_matches_wait4": inventory["session_exitstatus"] == wrapper["exit_code"],
            "session_testsfailed_report_count": inventory["session_testsfailed"],
            "session_testscollected": inventory["session_testscollected"],
            "wall_seconds": wrapper["wall_s"],
            "process_rusage_maxrss_kib": wrapper["process_rusage_maxrss_kib"],
            "exit_boundary": (
                "Hook argument is not guaranteed final exit; "
                "actual wait4 code is independent deciding status."
            ),
        },
        "denominators": {
            "requested_whole_files": len(selectors["test_paths"]),
            "session_item_entries": len(items),
            "unique_nodeids": len(ids),
            "collection_file_types_item_entries": dict(
                Counter(Path(row["path"]).suffix or "extensionless" for row in items)
            ),
            "definition_path_file_types_item_entries": dict(
                Counter(Path(row["location"][0]).suffix or "extensionless" for row in items)
            ),
            "distinct_collection_files": len(by_collection_file),
            "distinct_definition_paths": len(by_definition_path),
            "distinct_collection_file_types": dict(
                Counter(Path(path).suffix or "extensionless" for path in by_collection_file)
            ),
            "distinct_definition_path_file_types": dict(
                Counter(Path(path).suffix or "extensionless" for path in by_definition_path)
            ),
            "phase_reports": len(reports),
            "collection_reports": len(collectors),
            "deselected_item_entries": len(inventory["deselected_items"]),
            "junit_representations": xml["representation_count"],
        },
        "case_counts": case_counts,
        "cases": cases,
        "case_counts_by_collection_file": {
            key: dict(value) for key, value in sorted(by_collection_file.items())
        },
        "case_counts_by_definition_path": {
            key: dict(value) for key, value in sorted(by_definition_path.items())
        },
        "collection_definition_relation": {
            "normalization": "Root-relative lexical normpath; not symlink/inode/read-set proof.",
            "same_lexical_path_cases": len(cases) - len(mismatching_case_indices),
            "different_declared_path_cases": len(mismatching_case_indices),
            "mismatching_case_indices": mismatching_case_indices,
            "pair_counts": [
                {"collection_file": collection, "definition_path": definition, "cases": count}
                for (collection, definition), count in sorted(file_relations.items())
            ],
        },
        "duplicate_session_nodeids": {key: value for key, value in ids.items() if value != 1},
        "orphan_runtime_report_indexes": [
            i for i, row in enumerate(reports) if row["nodeid"] not in ids
        ],
        "phase_event_counts": dict(
            Counter(
                "/".join(
                    (
                        row["when"],
                        row["outcome"],
                        str(row.get("classification", "annotation_absent")),
                    )
                )
                for row in reports
            )
        ),
        "collection_event_counts": dict(Counter(row["outcome"] for row in collectors)),
        "nonpassed_collection_report_indexes": [
            i for i, row in enumerate(collectors) if row["outcome"] != "passed"
        ],
        "deselected_nodeids": [row["nodeid"] for row in inventory["deselected_items"]],
        "absent_named_selectors": [
            {"named_selector": row["named_selector"], "state": "UNRUN_named_selector_absent"}
            for row in selectors["absent_named_selectors"]
        ],
        "junit": xml,
        "junit_projection_agreement": xml_agreement,
        "module_origin_summary": origins,
        "unresolved_by_construction": [
            (
                "No closures: criterion adequacy, semantic owner permission "
                "and production data remain separately owned."
            ),
            (
                "File/case presence is not property proof; "
                "uncollected files have unknown case cardinality."
            ),
            (
                "Collector ERROR/SKIP, deselection and synthetic XML cells "
                "are separate from admitted cases."
            ),
            (
                "Repeated identity/phase and custom/subtest/xdist profiles "
                "require physical-attempt evidence."
            ),
            (
                "Raw inventories/JUnit/stdout are separately hash-bound; "
                "only hook-time backing-file census is observed."
            ),
        ],
    }


def main() -> None:
    """Read completed artifacts and write one exclusive ignored partition artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inventory", "junit", "wrapper", "profile", "selectors", "stdout"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("output must be a fresh absolute ignored path")
    output, repo = args.output.resolve(), args.repo.resolve()
    executable = shutil.which("git")
    if executable is None:
        parser.error("read-only Git identity check requires git")
    ignored = subprocess.run(  # noqa: S603 - argv-only read-only Git check
        [executable, "-C", str(repo), "check-ignore", "--quiet", "--no-index", "--", str(output)],
        check=False,
    )
    if not output.is_relative_to(repo) or ignored.returncode != 0:
        parser.error("output must be inside actual Git-ignored repo storage")
    result = _partition(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    _, identity = _input(output)
    sys.stdout.write(
        json.dumps(
            {
                "output": identity,
                "parse_state": result["parse_state"],
                "case_counts": result["case_counts"],
                "denominators": result["denominators"],
                "reconciliation_checks": result["reconciliation_checks"],
                "session": result["session"],
            },
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
