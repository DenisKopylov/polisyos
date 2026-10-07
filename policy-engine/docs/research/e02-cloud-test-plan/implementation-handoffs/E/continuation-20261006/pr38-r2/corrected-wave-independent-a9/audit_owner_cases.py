"""Independently attribute actual current JUnit to exact selected source files."""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from audit_inputs import FREEZE, OUT, WAVE, git


def _write_stdout(*values: object, flush: bool = False) -> None:
    """Emit the existing CLI text and optionally flush without logging side effects."""
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def main() -> None:
    if not ((WAVE / "execution-complete.json").exists()):
        raise AssertionError
    plan = json.loads((WAVE / "plan.json").read_text())
    quantities = json.loads((OUT / "junit-independent-a9f78817c.json").read_text())
    all_paths = [p for files in plan["groups"].values() for p in files]
    packets = {r["source"]: r for r in plan["owner_packet_extra_inputs"]}
    source_functions = defaultdict(list)
    modules = {}
    snapshots = []
    for path in [*all_paths, *packets]:
        payload = git("show", FREEZE + ":" + path)
        module = (
            path.removeprefix("policy-engine/").removesuffix(".py").replace("/", ".")
            if path not in packets
            else Path(packets[path]["destination"]).stem
        )
        tree = ast.parse(payload)
        functions = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
        }
        modules[path] = module
        for function in functions:
            source_functions[function].append(path)
        snapshots.append(
            {
                "source": path,
                "module": module,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "function_count": len(functions),
                "A_packet": path in packets,
            }
        )

    def identify(case: object) -> tuple[object, ...]:
        function = case["name"].split("[", 1)[0]
        classname = case.get("classname") or ""
        if not classname:
            matches = source_functions.get(function, [])
            if not (len(matches) == 1):
                raise AssertionError(("unbound_anonymous_case", case, matches))
            return matches[0], "unique exact function in complete124 selected-source denominator"
        candidates = [
            path
            for path, module in modules.items()
            if classname == module or classname.startswith(module + ".")
        ]
        if not (len(candidates) == 1):
            raise AssertionError(("unbound_module_case", case, candidates))
        if candidates[0] not in source_functions.get(function, []):
            raise AssertionError(
                (
                    "module_function_contradiction",
                    case,
                    candidates[0],
                )
            )
        return candidates[0], "exact module label plus exact function in that source"

    attributed = []
    by_owner = defaultdict(Counter)
    packet_counts = defaultdict(Counter)
    for group, detail in quantities.items():
        for case in detail["case_ids"]:
            path, basis = identify(case)
            owner = "A_owner_packet" if path in packets else "native_selected_source"
            by_owner[owner][case["outcome"]] += 1
            if path in packets:
                packet_counts[path][case["outcome"]] += 1
            attributed.append(
                {"group": group, **case, "source": path, "owner": owner, "basis": basis}
            )
    if not (sum(sum(x.values()) for x in by_owner.values()) == len(attributed)):
        raise AssertionError
    controls = []
    actual_packet = next(x for x in attributed if x["owner"] == "A_owner_packet")
    bad = dict(actual_packet, classname="tests.unit.remediation.test_frc_01")
    try:
        identify(bad)
    except AssertionError:
        controls.append(
            {"control": "real_A_function_with_false_native_module_label", "state": "REJECTED"}
        )
    else:
        raise AssertionError("contradictory owner attribution accepted")
    bad = dict(actual_packet, name="test_unpublished_case_identity", classname="")
    try:
        identify(bad)
    except AssertionError:
        controls.append({"control": "anonymous_unpublished_function", "state": "REJECTED"})
    else:
        raise AssertionError("unpublished case accepted")

    # Inspect completed tmp_path/CAS custody only; no production reader or evaluator invoked.
    scratch = []
    for job in plan["jobs"]:
        if job["kind"] != "numerical":
            continue
        argv = job["argv"]
        temp = Path(argv[argv.index("--basetemp") + 1])
        entries = [p for p in temp.rglob("*") if p.is_file() and not p.is_symlink()]
        paths = sorted(str(p.relative_to(temp)) for p in entries)
        frame = hashlib.sha256()
        for relative in paths:
            frame.update(relative.encode() + b"\0")
        json_files = [p for p in entries if p.suffix == ".json"]
        schema_candidates = []
        for p in json_files:
            if p.stat().st_size > 2_000_000:
                continue
            try:
                value = json.loads(p.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and isinstance(value.get("kind"), str):
                schema_candidates.append(
                    {
                        "path": str(p),
                        "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "kind": value["kind"],
                        "schema": value.get("schema"),
                    }
                )
        scratch.append(
            {
                "group": job["group"],
                "basetemp": str(temp),
                "parent_exists": temp.parent.is_dir(),
                "actual_basetemp_exists": temp.is_dir(),
                "actual_file_count": len(entries),
                "sorted_file_path_frame_sha256": frame.hexdigest(),
                "actual_JSON_artifact_kind_records": schema_candidates,
                "qualification": (
                    "Actual current completed filesystem outputs; negative-test a"
                    "rtifacts may deliberately be malformed. Presence is IO custo"
                    "dy, not independent artifact authority or property replay."
                ),
            }
        )
    output = {
        "schema": "e02.E.independent-current-case-owner-and-scratch.v1",
        "candidate": FREEZE,
        "source_denominator": snapshots,
        "actual_case_count": len(attributed),
        "actual_owner_counts": {k: dict(v) for k, v in by_owner.items()},
        "A_packet_counts": {k: dict(v) for k, v in packet_counts.items()},
        "all_cases": attributed,
        "source_attribution_controls": controls,
        "actual_completed_scratch": scratch,
        "no_tests_or_CAS_reader_or_numeric_callbacks_launched": True,
    }
    (OUT / "actual-owner-attribution-and-scratch-a9f78817c.json").write_text(
        json.dumps(output, indent=2) + "\n"
    )
    _write_stdout(
        json.dumps(
            {
                "candidate": FREEZE,
                "owner_counts": output["actual_owner_counts"],
                "packet_counts": output["A_packet_counts"],
                "attribution_controls": controls,
                "scratch_groups": len(scratch),
            }
        )
    )


if __name__ == "__main__":
    main()
