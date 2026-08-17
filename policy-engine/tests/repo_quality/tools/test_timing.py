from __future__ import annotations

import ast
import copy
import dataclasses
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import textwrap
from decimal import Decimal
from pathlib import Path

import pytest

from tools.lib.timing import (
    DEFAULT_HEALTHY_TERMINAL_EXIT_CODES,
    DEFAULT_TIMING_RETENTION,
    MIN_SAMPLES_FOR_P95,
    SAMPLE_ADMISSION_PREDICATE_ID,
    SAMPLE_ADMISSION_PREDICATE_IDS,
    ToolRunRecord,
    _mode_and_output_format_from_argv,
    admit_duration_sample,
    append_timing_record,
    budget_basis_for,
    default_timing_log_path,
    derive_timing_budget_lanes,
    healthy_terminal_exit_codes_for,
    load_healthy_terminal_declarations,
    load_timing_budget_catalog,
    load_timing_budget_catalog_data,
    percentile_ms,
    read_timing_records,
    summarize_timing_budget_lanes,
    summarize_timing_records,
    timing_key_for,
    uncatalogued_timing_lanes,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_ROOT = REPO_ROOT / "tools" / "quality" / "validation"
TIMED_SUITE_RUNNER = REPO_ROOT / "tools" / "quality" / "testing" / "run_timed_suite.py"
TIMING_BUDGET_CATALOG = REPO_ROOT / "tools" / "quality" / "timing_budgets.json"
_TIMING_MARKER = "_TIMING_STARTED_AT"


def _run_direct_guard(path: Path, *args: str, timing_log: Path) -> subprocess.CompletedProcess[str]:
    """Run a direct guard with an isolated real timing log."""

    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    return subprocess.run(  # noqa: S603 - trusted repository-local validator subprocess.
        [sys.executable, str(path), *args],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _is_main_guard(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Eq)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value == "__main__"
    )


def _is_real_argv_slice(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
        and node.value.attr == "argv"
        and isinstance(node.slice, ast.Slice)
        and isinstance(node.slice.lower, ast.Constant)
        and node.slice.lower.value == 1
        and node.slice.upper is None
        and node.slice.step is None
    )


def _direct_timing_contract_violations(source: str) -> list[str]:
    """Return structural direct-entry timing contract violations for one guard module."""

    tree = ast.parse(source)
    violations: list[str] = []
    marker_import_indexes = [
        index
        for index, node in enumerate(tree.body)
        if isinstance(node, ast.ImportFrom)
        and node.module == "time"
        and any(
            imported.name == "perf_counter" and imported.asname == "_timing_perf_counter"
            for imported in node.names
        )
    ]
    marker_indexes = [
        index
        for index, node in enumerate(tree.body)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == _TIMING_MARKER
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_timing_perf_counter"
        and not node.value.args
        and not node.value.keywords
    ]
    if len(marker_import_indexes) != 1 or len(marker_indexes) != 1:
        violations.append("missing_exact_early_timing_marker")
    else:
        marker_import_index = marker_import_indexes[0]
        marker_index = marker_indexes[0]
        if marker_import_index >= marker_index:
            violations.append("timing_marker_precedes_clock_import")
        prior_runtime_nodes = [
            node
            for node in tree.body[:marker_import_index]
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
        ]
        if prior_runtime_nodes or marker_index != marker_import_index + 1:
            violations.append("timing_marker_is_not_before_module_startup")

    wrapper_bindings = {
        imported.asname or imported.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "tools.lib.timing"
        for imported in node.names
        if imported.name == "run_timed_entrypoint"
    }
    if wrapper_bindings != {"run_timed_entrypoint"}:
        violations.append("missing_canonical_wrapper_import")

    main_guards = [node for node in tree.body if _is_main_guard(node)]
    if len(main_guards) != 1:
        violations.append("main_guard_count")
        return violations

    wrapper_calls = [
        node
        for node in ast.walk(main_guards[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in wrapper_bindings
    ]
    if len(wrapper_calls) != 1:
        violations.append("wrapper_call_count")
        return violations
    wrapper_call = wrapper_calls[0]

    system_exit_raises = [
        node
        for node in ast.walk(main_guards[0])
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        and len(node.exc.args) == 1
        and node.exc.args[0] is wrapper_call
    ]
    if len(system_exit_raises) != 1:
        violations.append("wrapper_result_not_raised_through_system_exit")
    allowed_prefix = all(
        isinstance(node, ast.Import)
        and len(node.names) == 1
        and node.names[0].name == "sys"
        and node.names[0].asname is None
        for node in main_guards[0].body[:-1]
    )
    if not (
        allowed_prefix
        and main_guards[0].body
        and len(system_exit_raises) == 1
        and main_guards[0].body[-1] is system_exit_raises[0]
    ):
        violations.append("main_guard_not_exact_wrapper_exit")

    if not (
        len(wrapper_call.args) == 1
        and isinstance(wrapper_call.args[0], ast.Name)
        and wrapper_call.args[0].id == "main"
    ):
        violations.append("wrapper_does_not_receive_real_main")
    keywords = {keyword.arg: keyword.value for keyword in wrapper_call.keywords if keyword.arg}
    script_path = keywords.get("script_path")
    if not (isinstance(script_path, ast.Name) and script_path.id == "__file__"):
        violations.append("wrapper_does_not_receive_real_script_path")
    argv = keywords.get("argv")
    if argv is None or not _is_real_argv_slice(argv):
        violations.append("wrapper_does_not_receive_real_argv")
    started = keywords.get("started_perf_counter")
    if not (isinstance(started, ast.Name) and started.id == _TIMING_MARKER):
        violations.append("wrapper_does_not_receive_early_timing_marker")
    return violations


_SOURCE_REF_RE = re.compile(r"(?P<path>.+):(?P<start>[1-9]\d*)(?:-(?P<end>[1-9]\d*))?")
_DURATION_RE = re.compile(
    r"(?<![\w.])(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>milliseconds?|ms|seconds?|secs?|s)\b",
    re.IGNORECASE,
)
_SECONDS_FIELD_RE = re.compile(
    r"(?:wall_time_seconds|validator_wall_time_seconds)=(?P<value>\d+(?:\.\d+)?)"
)


def _lane_workload_identity_markers(lane: dict[str, object]) -> tuple[str, ...]:
    """Derive command/tool identity tokens independently of an action flag."""

    command = lane.get("command")
    tool = lane.get("tool")
    assert isinstance(command, str)
    assert isinstance(tool, str)
    tokens = shlex.split(command)
    markers: list[str] = []
    for index, argument in enumerate(tokens[:-1]):
        if argument == "run":
            markers.append(tokens[index + 1])
    script_indexes = [index for index, token in enumerate(tokens) if token.endswith(".py")]
    markers.extend(Path(tokens[index]).name for index in script_indexes)
    markers.append(tool.rsplit(".", 1)[-1])
    return tuple(dict.fromkeys(marker for marker in markers if marker))


def _normalized_workload_text(value: str) -> str:
    """Normalize punctuation without weakening token order or word identity."""

    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _source_derived_unittest_denominator(path: Path) -> int:
    """Count source-declared unittest and module test nodes without importing the suite."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    test_case_names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in classes:
            base_names = {
                (
                    f"{base.value.id}.{base.attr}"
                    if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                    else base.id
                    if isinstance(base, ast.Name)
                    else ""
                )
                for base in node.bases
            }
            if node.name not in test_case_names and (
                {"unittest.TestCase", "TestCase"} & base_names
                or test_case_names & base_names
            ):
                test_case_names.add(node.name)
                changed = True
    test_node_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    module_tests = sum(
        isinstance(node, test_node_types) and node.name.startswith("test_")
        for node in tree.body
    )
    class_tests = sum(
        isinstance(member, test_node_types) and member.name.startswith("test_")
        for node in classes
        if node.name in test_case_names
        for member in node.body
    )
    return module_tests + class_tests


def _catalog_evidence_violations(payload: dict[str, object]) -> list[str]:
    """Return samples not positionally bound to their cited workload receipt."""

    violations: list[str] = []
    lanes = payload.get("lanes")
    assert isinstance(lanes, list)
    for lane in lanes:
        assert isinstance(lane, dict)
        source_refs = lane.get("source_refs")
        assert isinstance(source_refs, list)
        samples_ms = lane.get("samples_ms")
        assert isinstance(samples_ms, list)
        timing_key = lane.get("timing_key")
        if not samples_ms:
            continue
        if samples_ms and len(source_refs) != len(samples_ms):
            violations.append(
                f"{timing_key}:sample_source_cardinality:{len(samples_ms)}:{len(source_refs)}"
            )
            continue
        for sample, source_ref in zip(samples_ms, source_refs, strict=True):
            assert isinstance(source_ref, str)
            match = _SOURCE_REF_RE.fullmatch(source_ref)
            if match is None:
                violations.append(f"{timing_key}:invalid_source_ref:{source_ref}")
                continue
            source_path = (REPO_ROOT / match.group("path")).resolve()
            try:
                source_path.relative_to(REPO_ROOT)
                lines = source_path.read_text(encoding="utf-8").splitlines()
            except (OSError, ValueError):
                violations.append(f"{timing_key}:unreadable_source_ref:{source_ref}")
                continue
            start = int(match.group("start"))
            end = int(match.group("end") or start)
            if start > end or end > len(lines):
                violations.append(f"{timing_key}:invalid_source_range:{source_ref}")
                continue
            excerpt = "\n".join(lines[start - 1 : end])
            mode = lane.get("mode")
            assert isinstance(mode, str)
            workload_markers = _lane_workload_identity_markers(lane)
            normalized_excerpt = f" {_normalized_workload_text(excerpt)} "
            if not any(
                f" {_normalized_workload_text(marker)} " in normalized_excerpt
                for marker in workload_markers
            ):
                violations.append(
                    f"{timing_key}:uncited_workload_identity:{'|'.join(workload_markers)}"
                )
            if mode != "default":
                workload_marker = f"--{mode}"
                if workload_marker not in excerpt:
                    violations.append(f"{timing_key}:uncited_workload:{workload_marker}")
            cited_milliseconds: set[Decimal] = set()
            for duration_match in _DURATION_RE.finditer(excerpt):
                duration = Decimal(duration_match.group("value"))
                if duration_match.group("unit").casefold().startswith(("s", "second")):
                    duration *= 1000
                cited_milliseconds.add(duration)
            cited_milliseconds.update(
                Decimal(duration_match.group("value")) * 1000
                for duration_match in _SECONDS_FIELD_RE.finditer(excerpt)
            )
            rendered_sample = Decimal(str(sample))
            if rendered_sample not in cited_milliseconds:
                violations.append(f"{timing_key}:uncited_sample:{sample}")
    return violations


def _direct_cli_options() -> dict[str, tuple[set[str], set[str]]]:
    """Return independently derived action/context option names for every GY validator."""

    value_actions = {"accept-stage1-n4-journal", "capture-live-journal"}
    surfaces: dict[str, tuple[set[str], set[str]]] = {}
    for path in sorted(VALIDATION_ROOT.glob("check_layer3_gy_*.py")):
        actions: set[str] = set()
        contexts: set[str] = set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.startswith("--")
            ):
                continue
            name = node.args[0].value[2:]
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            action = keywords.get("action")
            is_store_true = isinstance(action, ast.Constant) and action.value == "store_true"
            if (is_store_true and name != "json") or name in value_actions:
                actions.add(name)
            else:
                contexts.add(name)
        surfaces[path.name] = (actions, contexts)
    return surfaces


def test_direct_gy_guard_persists_default_mode_without_changing_success_output(tmp_path: Path) -> None:
    """Catch a direct-entry timing-wrapper bypass for a successful no-flag guard."""

    timing_log = tmp_path / "timing.jsonl"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    assert result.stdout == "PASS\n"
    assert result.stderr == ""
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["tool"] == "quality.validation.check_layer3_gy_p0_coverage_audit"
    assert records[0]["mode"] == "default"
    assert records[0]["status"] == "ok"
    assert records[0]["exit_code"] == 0


def test_direct_gy_guard_persists_json_output_without_inventing_action_mode(
    tmp_path: Path,
) -> None:
    """Catch a presentation-only JSON flag being recorded as an operational action."""

    timing_log = tmp_path / "timing.jsonl"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        "--json",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["mode"] == "default"
    assert records[0]["output_format"] == "json"
    assert records[0]["status"] == "ok"
    assert records[0]["exit_code"] == 0


def test_direct_gy_guard_persists_expected_nonzero_exception_result(tmp_path: Path) -> None:
    """Catch a wrapper that changes a direct guard's exception exit code or output."""

    timing_log = tmp_path / "timing.jsonl"
    missing_audit = tmp_path / "missing.json"
    result = _run_direct_guard(
        VALIDATION_ROOT / "check_layer3_gy_p0_coverage_audit.py",
        "--audit",
        str(missing_audit),
        timing_log=timing_log,
    )

    assert result.returncode == 1
    assert "FileNotFoundError" in result.stderr
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["mode"] == "default"
    assert records[0]["status"] == "failed"
    assert records[0]["exit_code"] == 1


def test_canonical_direct_run_records_action_lane_and_output_format(tmp_path: Path) -> None:
    """Catch option parsing that mistakes value-taking plumbing for the action lane."""

    script_path = tmp_path / "check_layer3_gy_fixture.py"
    script_path.write_text(
        textwrap.dedent(
            """\
            from tools.lib.timing import run_timed_entrypoint

            def main(argv: list[str]) -> int:
                return 0

            if __name__ == "__main__":
                import sys
                raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
            """
        ),
        encoding="utf-8",
    )
    timing_log = tmp_path / "timing.jsonl"
    result = _run_direct_guard(
        script_path,
        "--repo-root",
        ".",
        "--check",
        "--output-format",
        "json",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    records = read_timing_records(timing_log)
    assert len(records) == 1
    assert records[0].mode == "check"
    assert records[0].output_format == "json"
    catalog = load_timing_budget_catalog_data(
        {
            "lanes": [
                {
                    "timing_key": "check_layer3_gy_fixture:check",
                    "tool": "check_layer3_gy_fixture",
                    "mode": "check",
                    "command": "python check_layer3_gy_fixture.py --repo-root . --check --output-format json",
                    "samples_ms": [0.0],
                    "measured_p95_ms": 0.0,
                    "recommended_timeout_ms": 0.0,
                    "source_refs": ["docs/receipt.md:1"],
                    "sample_admission_predicate": "manual_journal_excerpt:v1",
                    "regime": "serialized",
                }
            ]
        }
    )
    assert summarize_timing_budget_lanes(records, catalog)[0].local_runs == 1


def test_direct_context_options_do_not_invent_an_action_mode(tmp_path: Path) -> None:
    """Catch an alternate input path being mislabeled as an operational action."""

    script_path = tmp_path / "check_layer3_gy_fixture.py"
    script_path.write_text(
        textwrap.dedent(
            """\
            from tools.lib.timing import run_timed_entrypoint

            def main(argv: list[str]) -> int:
                return 0

            if __name__ == "__main__":
                import sys
                raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
            """
        ),
        encoding="utf-8",
    )
    timing_log = tmp_path / "timing.jsonl"

    result = _run_direct_guard(
        script_path,
        "--audit",
        "receipt.json",
        "--repo-root",
        ".",
        "--output-format=json",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    records = read_timing_records(timing_log)
    assert len(records) == 1
    assert records[0].mode == "default"
    assert records[0].output_format == "json"


def test_direct_action_classification_ignores_json_presentation_flag(tmp_path: Path) -> None:
    """Catch ``--json`` outranking a later operational action flag."""

    script_path = tmp_path / "check_layer3_gy_fixture.py"
    script_path.write_text(
        textwrap.dedent(
            """\
            from tools.lib.timing import run_timed_entrypoint

            def main(argv: list[str]) -> int:
                return 0

            if __name__ == "__main__":
                import sys
                raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
            """
        ),
        encoding="utf-8",
    )
    timing_log = tmp_path / "timing.jsonl"

    result = _run_direct_guard(
        script_path,
        "--json",
        "--check",
        timing_log=timing_log,
    )

    assert result.returncode == 0
    records = read_timing_records(timing_log)
    assert len(records) == 1
    assert records[0].mode == "check"
    assert records[0].output_format == "json"


def test_value_taking_action_precedes_later_context_options() -> None:
    """Catch a value-taking mode being replaced by the last value option in argv."""

    assert _mode_and_output_format_from_argv(
        [
            "--capture-live-journal",
            "capture.json",
            "--event-log-path",
            "events.jsonl",
            "--catalog-path",
            "catalog.duckdb",
        ]
    ) == ("capture-live-journal", "text")


def test_mode_classifier_covers_every_current_gy_argparse_surface() -> None:
    """Catch any current GY action or context option escaping shared classification."""

    surfaces = _direct_cli_options()
    value_actions = {"accept-stage1-n4-journal", "capture-live-journal"}
    observed_value_actions: set[str] = set()
    assert len(surfaces) == 41

    for script, (actions, contexts) in surfaces.items():
        context_argv: list[str] = []
        for context in sorted(contexts):
            context_argv.append(f"--{context}")
            if context == "json":
                continue
            context_argv.append("json" if context == "output-format" else "fixture")
        expected_format = "json" if {"json", "output-format"} & contexts else "text"
        assert _mode_and_output_format_from_argv(context_argv) == (
            "default",
            expected_format,
        ), script

        for action in actions:
            action_argv = [f"--{action}"]
            if action in value_actions:
                observed_value_actions.add(action)
                action_argv.append("action-value")
            assert _mode_and_output_format_from_argv([*action_argv, *context_argv]) == (
                action,
                expected_format,
            ), f"{script}:{action}"

    assert observed_value_actions == value_actions


def test_direct_duration_includes_slow_module_initialization(tmp_path: Path) -> None:
    """Catch a direct-entry timer that starts only after the validator module has imported."""

    script_path = tmp_path / "slow_guard.py"
    script_path.write_text(
        textwrap.dedent(
            """\
            from __future__ import annotations
            from time import perf_counter as _timing_perf_counter
            _TIMING_STARTED_AT = _timing_perf_counter()

            import time
            time.sleep(0.2)
            from tools.lib.timing import run_timed_entrypoint

            def main() -> int:
                return 0

            if __name__ == "__main__":
                import sys
                raise SystemExit(
                    run_timed_entrypoint(
                        main,
                        script_path=__file__,
                        argv=sys.argv[1:],
                        started_perf_counter=_TIMING_STARTED_AT,
                    )
                )
            """
        ),
        encoding="utf-8",
    )
    timing_log = tmp_path / "timing.jsonl"

    result = _run_direct_guard(script_path, timing_log=timing_log)

    assert result.returncode == 0
    records = _records(timing_log)
    assert len(records) == 1
    assert float(records[0]["duration_ms"]) >= 190.0


def test_every_direct_gy_guard_satisfies_exact_timing_entry_contract() -> None:
    """Catch any sibling guard that weakens the shared direct-entry timing chokepoint."""

    guard_paths = sorted(VALIDATION_ROOT.glob("check_layer3_gy_*.py"))
    violations = {
        path.name: findings
        for path in guard_paths
        if (findings := _direct_timing_contract_violations(path.read_text(encoding="utf-8")))
    }

    assert guard_paths
    assert violations == {}


@pytest.mark.parametrize(
    ("mutation", "expected_violation"),
    [
        ("wrong_callable", "wrapper_does_not_receive_real_main"),
        ("wrong_argv", "wrapper_does_not_receive_real_argv"),
        ("wrong_script_path", "wrapper_does_not_receive_real_script_path"),
        ("discarded_result", "wrapper_result_not_raised_through_system_exit"),
        ("missing_marker_argument", "wrapper_does_not_receive_early_timing_marker"),
        ("marker_only", "wrapper_call_count"),
        ("dead_wrapper_bypass", "main_guard_not_exact_wrapper_exit"),
    ],
)
def test_direct_timing_contract_rejects_semantically_inert_mutations(
    mutation: str, expected_violation: str
) -> None:
    """Catch a form-only census that accepts a no-op or miswired wrapper call."""

    valid = textwrap.dedent(
        """\
        from __future__ import annotations
        from time import perf_counter as _timing_perf_counter
        _TIMING_STARTED_AT = _timing_perf_counter()

        import sys
        from tools.lib.timing import run_timed_entrypoint

        def main(argv: list[str]) -> int:
            return 0

        def other(argv: list[str]) -> int:
            return 0

        if __name__ == "__main__":
            raise SystemExit(
                run_timed_entrypoint(
                    main,
                    script_path=__file__,
                    argv=sys.argv[1:],
                    started_perf_counter=_TIMING_STARTED_AT,
                )
            )
        """
    )
    replacements = {
        "wrong_callable": ("            main,", "            other,"),
        "wrong_argv": ("argv=sys.argv[1:]", "argv=[]"),
        "wrong_script_path": ("script_path=__file__", "script_path='fake.py'"),
        "discarded_result": (
            "    raise SystemExit(\n        run_timed_entrypoint(\n            main,\n            script_path=__file__,\n            argv=sys.argv[1:],\n            started_perf_counter=_TIMING_STARTED_AT,\n        )\n    )",
            "    run_timed_entrypoint(\n        main,\n        script_path=__file__,\n        argv=sys.argv[1:],\n        started_perf_counter=_TIMING_STARTED_AT,\n    )",
        ),
        "missing_marker_argument": (
            "            started_perf_counter=_TIMING_STARTED_AT,\n",
            "",
        ),
        "marker_only": (
            "    raise SystemExit(\n        run_timed_entrypoint(\n            main,\n            script_path=__file__,\n            argv=sys.argv[1:],\n            started_perf_counter=_TIMING_STARTED_AT,\n        )\n    )",
            "    raise SystemExit(main(sys.argv[1:]))",
        ),
        "dead_wrapper_bypass": (
            "    raise SystemExit(\n        run_timed_entrypoint(\n            main,\n            script_path=__file__,\n            argv=sys.argv[1:],\n            started_perf_counter=_TIMING_STARTED_AT,\n        )\n    )",
            "    if False:\n        raise SystemExit(\n            run_timed_entrypoint(\n                main,\n                script_path=__file__,\n                argv=sys.argv[1:],\n                started_perf_counter=_TIMING_STARTED_AT,\n            )\n        )\n    raise SystemExit(main(sys.argv[1:]))",
        ),
    }
    old, new = replacements[mutation]
    mutated = valid.replace(old, new)
    assert mutated != valid

    assert _direct_timing_contract_violations(valid) == []
    assert expected_violation in _direct_timing_contract_violations(mutated)


def test_timing_summary_keeps_all_modes_in_one_tool_denominator() -> None:
    """Catch summaries that redefine a tool's counts and percentiles by splitting its modes."""

    summaries = summarize_timing_records(
        [
            ToolRunRecord(
                tool="quality.validation.example",
                category="quality",
                output_format="text",
                status="ok",
                preflight_status="ok",
                started_at="2026-08-02T10:00:00+00:00",
                duration_ms=100.0,
                exit_code=0,
                mode="check",
            ),
            ToolRunRecord(
                tool="quality.validation.example",
                category="quality",
                output_format="text",
                status="failed",
                preflight_status="ok",
                started_at="2026-08-02T10:01:00+00:00",
                duration_ms=300.0,
                exit_code=1,
                mode="write",
            ),
        ],
        budgets_ms={"quality.validation.example": 250.0},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.runs == 2
    assert summary.failures == 1
    assert summary.average_duration_ms == 200.0
    assert summary.p95_duration_ms == 300.0
    assert summary.over_budget_runs == 1
    assert summary.latest_mode == "write"


def test_percentile_uses_nearest_rank_for_twelve_samples() -> None:
    """Catch interpolated or rounded-index p95 selecting rank 11 instead of rank 12."""

    assert percentile_ms([float(value) for value in range(1, 13)], 0.95) == 12.0


def test_concurrent_timing_writers_retain_every_unique_record(tmp_path: Path) -> None:
    """Catch unlocked timing-log read/modify/replace cycles that lose sibling records."""

    timing_log = tmp_path / "timing.jsonl"
    start_gate = tmp_path / "start"
    worker_count = 32
    worker = textwrap.dedent(
        """\
        import os
        import sys
        import time
        from pathlib import Path
        from tools.lib.timing import ToolRunRecord, append_timing_record

        timing_log = Path(sys.argv[1])
        start_gate = Path(sys.argv[2])
        worker_id = sys.argv[3]
        while not start_gate.exists():
            time.sleep(0.001)
        append_timing_record(
            timing_log,
            ToolRunRecord(
                tool=f"tests.concurrent.{worker_id}",
                category="tests",
                output_format="text",
                status="ok",
                preflight_status="ok",
                started_at=f"2026-08-03T00:00:{int(worker_id):02d}+00:00",
                duration_ms=float(worker_id),
                exit_code=0,
            ),
        )
        """
    )
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_RETENTION"] = str(worker_count)
    processes = [
        subprocess.Popen(  # noqa: S603 - trusted local interpreter concurrency fixture.
            [sys.executable, "-c", worker, str(timing_log), str(start_gate), str(worker_id)],
            cwd=REPO_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for worker_id in range(worker_count)
    ]
    start_gate.touch()
    results = [process.communicate(timeout=30) for process in processes]

    assert [process.returncode for process in processes] == [0] * worker_count, results
    records = _records(timing_log)
    assert len(records) == worker_count
    assert {record["tool"] for record in records} == {
        f"tests.concurrent.{worker_id}" for worker_id in range(worker_count)
    }


def test_timing_retention_one_keeps_only_the_latest_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Catch the ``-0`` slice retaining the entire log at the minimum limit."""

    timing_log = tmp_path / "timing.jsonl"
    monkeypatch.setenv("POLISYOS_TOOLS_TIMING_RETENTION", "1")
    for index in range(3):
        append_timing_record(
            timing_log,
            ToolRunRecord(
                tool=f"tests.retention.{index}",
                category="tests",
                output_format="text",
                status="ok",
                preflight_status="ok",
                started_at=f"2026-08-03T00:00:0{index}+00:00",
                duration_ms=float(index),
                exit_code=0,
            ),
        )

    records = read_timing_records(timing_log)
    assert [record.tool for record in records] == ["tests.retention.2"]


def test_timing_budget_catalog_rejects_p95_drift_from_literal_samples(tmp_path: Path) -> None:
    """Catch a catalog that asserts a p95 rather than deriving it from its samples."""

    catalog_path = tmp_path / "timing_budgets.json"
    catalog_path.write_text(
        json.dumps(
            {
                "lanes": [
                    {
                        "timing_key": "tests.example:default",
                        "tool": "tests.example",
                        "mode": "default",
                        "command": "pytest tests/example.py",
                        "samples_ms": [100.0, 200.0],
                        "measured_p95_ms": 100.0,
                        "recommended_timeout_ms": 200.0,
                        "source_refs": ["docs/receipt.md:1"],
                        "sample_admission_predicate": "manual_journal_excerpt:v1",
                        "regime": "serialized",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="measured_p95_ms"):
        load_timing_budget_catalog(catalog_path)


def test_committed_timing_budget_samples_are_bound_to_cited_excerpts() -> None:
    """Catch a literal sample whose cited repository lines do not contain that duration."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))

    assert _catalog_evidence_violations(payload) == []


def test_timing_budget_evidence_rejects_a_line_shifted_receipt() -> None:
    """Catch an evidence gate that accepts a nearby line instead of the cited measurement."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    shifted = copy.deepcopy(payload)
    lanes = shifted["lanes"]
    assert isinstance(lanes, list)
    atlas = next(
        lane
        for lane in lanes
        if isinstance(lane, dict) and lane.get("timing_key") == "atlas.python-governance:default"
    )
    atlas["source_refs"] = [
        "docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md:47"
    ]

    assert "atlas.python-governance:default:uncited_sample:160233.242" in (
        _catalog_evidence_violations(shifted)
    )


def test_timing_budget_evidence_rejects_samples_swapped_between_workloads() -> None:
    """Catch pooled receipt ranges accepting another lane's duration."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    swapped = copy.deepcopy(payload)
    lanes = swapped["lanes"]
    assert isinstance(lanes, list)
    check = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == "quality.validation.check_layer3_gy_depth_n_universality_contract:check"
    )
    corrupt = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == (
            "quality.validation.check_layer3_gy_depth_n_universality_contract:"
            "corrupt-field-drift-check"
        )
    )
    check.update(
        samples_ms=[9090.0],
        measured_p95_ms=9090.0,
        recommended_timeout_ms=18180.0,
    )
    corrupt.update(
        samples_ms=[104410.0],
        measured_p95_ms=104410.0,
        recommended_timeout_ms=208820.0,
    )

    violations = _catalog_evidence_violations(swapped)
    assert any("depth_n_universality_contract:check" in item for item in violations)
    assert any("corrupt-field-drift-check" in item for item in violations)


def test_timing_budget_evidence_rejects_receipts_swapped_with_samples() -> None:
    """Catch lane swaps that preserve sample-to-citation cardinality and durations."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    swapped = copy.deepcopy(payload)
    lanes = swapped["lanes"]
    assert isinstance(lanes, list)
    check = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == "quality.validation.check_layer3_gy_depth_n_universality_contract:check"
    )
    corrupt = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == (
            "quality.validation.check_layer3_gy_depth_n_universality_contract:"
            "corrupt-field-drift-check"
        )
    )
    measurement_fields = (
        "samples_ms",
        "measured_p95_ms",
        "recommended_timeout_ms",
        "source_refs",
    )
    check_measurements = {field: check[field] for field in measurement_fields}
    corrupt_measurements = {field: corrupt[field] for field in measurement_fields}
    check.update(corrupt_measurements)
    corrupt.update(check_measurements)

    violations = _catalog_evidence_violations(swapped)
    assert any(item.endswith(":uncited_workload:--check") for item in violations)
    assert any(
        item.endswith(":uncited_workload:--corrupt-field-drift-check")
        for item in violations
    )


def test_timing_budget_evidence_rejects_same_mode_cross_tool_swaps() -> None:
    """Catch action-only binding that accepts another tool's same-mode receipts."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    swapped = copy.deepcopy(payload)
    lanes = swapped["lanes"]
    assert isinstance(lanes, list)
    depth_check = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == "quality.validation.check_layer3_gy_depth_n_universality_contract:check"
    )
    confidence_check = next(
        lane
        for lane in lanes
        if isinstance(lane, dict)
        and lane.get("timing_key")
        == "quality.validation.check_layer3_gy_confidence_ledger:check"
    )
    measurement_fields = (
        "samples_ms",
        "measured_p95_ms",
        "recommended_timeout_ms",
        "source_refs",
    )
    depth_measurements = {field: depth_check[field] for field in measurement_fields}
    confidence_measurements = {field: confidence_check[field] for field in measurement_fields}
    depth_check.update(confidence_measurements)
    confidence_check.update(depth_measurements)

    violations = _catalog_evidence_violations(swapped)
    assert any("depth_n_universality_contract:check" in item for item in violations)
    assert any("confidence_ledger:check" in item for item in violations)


def test_atlas_python_governance_lane_names_one_exact_runnable_workload() -> None:
    """Catch a timing lane that combines samples from different Atlas governance suites."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    lanes = payload["lanes"]
    assert isinstance(lanes, list)
    atlas = next(
        lane
        for lane in lanes
        if isinstance(lane, dict) and lane.get("timing_key") == "atlas.python-governance:default"
    )

    assert atlas["command"] == (
        "uv run --extra test --with 'jsonschema>=4.25' python -m pytest "
        "architecture/atlas_surfaces/test_frontend_disposition_register.py "
        "architecture/atlas_surfaces/test_status_retirement_inventory.py -q"
    )
    assert atlas["samples_ms"] == [160233.242]
    assert atlas["source_refs"] == [
        "docs/superpowers/journals/2026-08-02-gy-infra-2-verification-economics.md:48"
    ]
    source_line = (
        REPO_ROOT / atlas["source_refs"][0].rsplit(":", 1)[0]
    ).read_text(encoding="utf-8").splitlines()[47]
    command_test_paths = [
        REPO_ROOT / token
        for token in shlex.split(atlas["command"])
        if token.startswith("architecture/") and Path(token).name.startswith("test_")
    ]
    source_denominator = sum(
        _source_derived_unittest_denominator(path) for path in command_test_paths
    )
    receipt_count_match = re.search(r"`(?P<count>\d+)` tests passed", source_line)
    assert receipt_count_match is not None
    assert int(receipt_count_match.group("count")) == source_denominator
    assert all("<" not in lane["command"] for lane in lanes if isinstance(lane, dict))
    assert not any(
        isinstance(lane, dict) and lane.get("timing_key") == "atlas.status-governance:default"
        for lane in lanes
    )


def test_atlas_source_denominator_changes_when_a_test_method_is_removed(
    tmp_path: Path,
) -> None:
    """Catch a source census that stays green when a collected test disappears."""

    source_path = REPO_ROOT / "architecture/atlas_surfaces/test_frontend_disposition_register.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    removed = next(
        member
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for member in node.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and member.name.startswith("test_")
    )
    removed.name = f"removed_{removed.name}"
    mutated_path = tmp_path / source_path.name
    mutated_path.write_text(ast.unparse(tree), encoding="utf-8")

    assert _source_derived_unittest_denominator(mutated_path) == (
        _source_derived_unittest_denominator(source_path) - 1
    )


def test_n11_closeout_catalog_includes_every_supplied_expensive_lane() -> None:
    """Catch supplied corruption/warm/cold measurements disappearing from the catalog."""

    payload = json.loads(TIMING_BUDGET_CATALOG.read_text(encoding="utf-8"))
    lanes = {
        lane["timing_key"]: lane
        for lane in payload["lanes"]
        if isinstance(lane, dict) and isinstance(lane.get("timing_key"), str)
    }
    prefix = "quality.validation.check_layer3_gy_confidence_ledger:"
    assert lanes[f"{prefix}write"]["samples_ms"][-2:] == [1086000.0, 951000.0]
    assert lanes[f"{prefix}check"]["samples_ms"][-1:] == [951000.0]
    assert lanes[f"{prefix}corrupt-field-drift-check"]["samples_ms"] == [937000.0]
    assert lanes[f"{prefix}warm-closeout"]["samples_ms"] == [975000.0]
    assert lanes[f"{prefix}cold-rederive"]["samples_ms"] == [952000.0]


def test_timing_budget_lanes_keep_unmeasured_catalog_entries_before_local_runs(
    tmp_path: Path,
) -> None:
    """Catch a requested no-sample lane disappearing before a timing log exists."""

    catalog_path = tmp_path / "timing_budgets.json"
    catalog_path.write_text(
        json.dumps(
            {
                "lanes": [
                    {
                        "timing_key": "tests.requested:default",
                        "tool": "tests.requested",
                        "mode": "default",
                        "command": "pytest tests/requested.py",
                        "samples_ms": [],
                        "measured_p95_ms": None,
                        "recommended_timeout_ms": None,
                        "source_refs": ["docs/receipt.md:2"],
                        "sample_admission_predicate": "manual_journal_excerpt:v1",
                        "regime": "serialized",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    lanes = summarize_timing_budget_lanes([], load_timing_budget_catalog(catalog_path))

    assert len(lanes) == 1
    assert lanes[0].timing_key == "tests.requested:default"
    assert lanes[0].state == "unmeasured"
    assert lanes[0].local_runs == 0


def test_timing_budget_lane_reports_completed_duration_above_measured_p95() -> None:
    """Catch a completed local lane exceeding its measured p95 without a finding."""

    catalog = load_timing_budget_catalog_data(
        {
            "lanes": [
                {
                    "timing_key": "tests.example:check",
                    "tool": "tests.example",
                    "mode": "check",
                    "command": "pytest tests/example.py --check",
                    "samples_ms": [100.0, 200.0],
                    "measured_p95_ms": 200.0,
                    "recommended_timeout_ms": 400.0,
                    "source_refs": ["docs/receipt.md:3"],
                    "sample_admission_predicate": "manual_journal_excerpt:v1",
                    "regime": "serialized",
                }
            ]
        }
    )

    lanes = summarize_timing_budget_lanes(
        [
            ToolRunRecord(
                tool="tests.example",
                category="tests",
                output_format="text",
                status="ok",
                preflight_status="ok",
                started_at="2026-08-02T10:00:00+00:00",
                duration_ms=201.0,
                exit_code=0,
                mode="check",
            )
        ],
        catalog,
    )

    assert lanes[0].state == "over_budget"
    assert lanes[0].over_budget_runs == 1


def test_external_suite_runner_preserves_child_streams_and_nonzero_exit(tmp_path: Path) -> None:
    """Catch an external runner that changes child semantics or skips timing persistence."""

    timing_log = tmp_path / "timing.jsonl"
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    result = subprocess.run(  # noqa: S603 - trusted local runner and interpreter fixture.
        [
            sys.executable,
            str(TIMED_SUITE_RUNNER),
            "--lane",
            "tests.external.failure",
            "--",
            sys.executable,
            "-c",
            "import sys; print('child-out'); print('child-err', file=sys.stderr); raise SystemExit(7)",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert result.stdout == "child-out\n"
    assert result.stderr == "child-err\n"
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["tool"] == "tests.external.failure"
    assert records[0]["mode"] == "default"
    assert records[0]["status"] == "failed"
    assert records[0]["exit_code"] == 7


def test_timing_persistence_failure_does_not_change_child_result(tmp_path: Path) -> None:
    """Catch telemetry storage failure escaping across the command-semantics boundary."""

    unwritable_log = tmp_path / "is-a-directory"
    unwritable_log.mkdir()
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(unwritable_log)
    result = subprocess.run(  # noqa: S603 - trusted local runner and interpreter fixture.
        [
            sys.executable,
            str(TIMED_SUITE_RUNNER),
            "--lane",
            "tests.external.telemetry-failure",
            "--",
            sys.executable,
            "-c",
            "import sys; print('child-out'); raise SystemExit(7)",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert result.stdout == "child-out\n"
    assert "could not persist tool timing telemetry" in result.stderr


def test_external_suite_runner_splits_explicit_tool_and_mode_lane(tmp_path: Path) -> None:
    """Catch a colon lane being persisted as a tool name while its mode stays default."""

    timing_log = tmp_path / "timing.jsonl"
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    result = subprocess.run(  # noqa: S603 - trusted local runner and interpreter fixture.
        [
            sys.executable,
            str(TIMED_SUITE_RUNNER),
            "--lane",
            "tests.external:check",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(0)",
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["tool"] == "tests.external"
    assert records[0]["mode"] == "check"


@pytest.mark.parametrize("termination_signal", [signal.SIGTERM, signal.SIGKILL])
def test_external_suite_runner_preserves_signal_termination(
    tmp_path: Path,
    termination_signal: signal.Signals,
) -> None:
    """Catch any signal-killed child being converted into a normal process exit."""

    timing_log = tmp_path / "timing.jsonl"
    environment = os.environ.copy()
    environment["POLISYOS_TOOLS_TIMING_LOG"] = str(timing_log)
    result = subprocess.run(  # noqa: S603 - trusted local signal-preservation fixture.
        [
            sys.executable,
            str(TIMED_SUITE_RUNNER),
            "--lane",
            "tests.external.signal",
            "--",
            sys.executable,
            "-c",
            (
                "import os, signal; "
                f"os.kill(os.getpid(), signal.Signals({int(termination_signal)}))"
            ),
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == -termination_signal
    records = _records(timing_log)
    assert len(records) == 1
    assert records[0]["status"] == "failed"
    assert records[0]["exit_code"] == -termination_signal


SALVAGED_TIMING_RECORDS = (
    REPO_ROOT / "docs" / "superpowers" / "timing-evidence" / "2026-08-17-salvaged-timing-records.jsonl"
)

# Measured 2026-08-17 by reading every module that defines ``corrupt_field_drift_check`` and
# pairing the status it returns on DETECTION with the exit code ``main`` maps that status to.
# Seven of the fifteen report "fail" when the mutation was detected -- the correct outcome -- so
# their healthy terminal is exit 1. Six of those seven map their DEFECT to exit 0, which is why
# the default {0} does not merely drop good samples there: it admits exactly the failures.
INVERTED_CORRUPT_LANES = {
    "check_layer3_gy_acquisition_contract",
    "check_layer3_gy_depth_n_universality_contract",
    "check_layer3_gy_generation_cycle_contract",
    "check_layer3_gy_generation_cycle_disposition_ledger",
    "check_layer3_gy_joint_simulation_horizon_contract",
    "check_layer3_gy_promotion_contract",
    "check_layer3_gy_second_domain_pack",
}
NORMAL_CORRUPT_LANES = {
    "check_grounding_active_controller_contract",
    "check_grounding_admission_contract",
    "check_grounding_benchmark_contract",
    "check_grounding_bind_contract",
    "check_grounding_credal_reference_contract",
    "check_grounding_relation_contract",
    "check_layer3_gy_confidence_ledger",
    "check_layer3_gy_value_gate_contract",
}
CORRUPT_DRIFT_MODE = "corrupt-field-drift-check"


def _salvaged_records() -> list[ToolRunRecord]:
    lines = SALVAGED_TIMING_RECORDS.read_text(encoding="utf-8").splitlines()
    return [
        ToolRunRecord(**json.loads(json.loads(line)["raw"])) for line in lines if line.strip()
    ]


def test_salvaged_corrupt_lane_run_at_exit_one_is_admitted_as_a_sample() -> None:
    """The completed corrupt-drift run today's proxy drops must become an admissible sample."""

    declarations = load_healthy_terminal_declarations()
    fixtures = [
        record
        for record in _salvaged_records()
        if record.tool.endswith("check_layer3_gy_second_domain_pack")
        and record.mode == CORRUPT_DRIFT_MODE
    ]
    assert fixtures, "salvaged evidence must retain the exit-1 second_domain_pack fixture"

    for record in fixtures:
        assert record.exit_code == 1
        assert record.status == "failed"  # the harness proxy, contradicted by the lane contract
        admission = admit_duration_sample(
            record,
            healthy_terminal_exit_codes=healthy_terminal_exit_codes_for(
                record.tool, record.mode, declarations
            ),
        )
        assert admission.admitted, admission.reason
        assert admission.reason == "declared_healthy_terminal"


def test_killed_run_stays_inadmissible_even_when_its_exit_code_is_declared_healthy() -> None:
    """A killed run's duration measures the cap, not the lane, under every declaration."""

    killed = ToolRunRecord(
        tool="quality.validation.check_layer3_gy_second_domain_pack",
        category="quality",
        output_format="json",
        status="killed",
        preflight_status="ok",
        started_at="2026-08-13T09:52:04.088329+00:00",
        duration_ms=526_392.0,
        exit_code=1,
        mode=CORRUPT_DRIFT_MODE,
    )
    admission = admit_duration_sample(killed, healthy_terminal_exit_codes=(0, 1, 2))
    assert not admission.admitted
    assert admission.reason == "no_terminal_decision:killed"


@pytest.mark.parametrize(
    ("record_kwargs", "expected_reason"),
    [
        ({"status": "failed", "exit_code": -9, "duration_ms": 900.0}, "signal_death"),
        (
            {"status": "skipped", "exit_code": 78, "duration_ms": 0.0, "preflight_status": "quarantined"},
            "skipped",
        ),
        ({"status": "ok", "exit_code": 0, "duration_ms": 0.0}, "zero_duration"),
        ({"status": "running", "exit_code": 0, "duration_ms": 10.0}, "no_terminal_decision:running"),
        ({"status": "ok", "exit_code": 0, "duration_ms": 10.0, "tool": ""}, "malformed_record"),
    ],
)
def test_non_terminal_records_stay_inadmissible_under_a_maximally_wide_declaration(
    record_kwargs: dict[str, object], expected_reason: str
) -> None:
    """No declaration can widen admission to a run that never reached its own terminal."""

    base = {
        "tool": "quality.validation.check_layer3_gy_second_domain_pack",
        "category": "quality",
        "output_format": "json",
        "status": "ok",
        "preflight_status": "ok",
        "started_at": "2026-08-13T09:52:04.088329+00:00",
        "duration_ms": 1000.0,
        "exit_code": 0,
        "mode": CORRUPT_DRIFT_MODE,
    }
    record = ToolRunRecord(**{**base, **record_kwargs})
    admission = admit_duration_sample(
        record, healthy_terminal_exit_codes=(-9, 0, 1, 2, 78)
    )
    assert not admission.admitted
    assert admission.reason == expected_reason


def test_guardrail_failures_at_exit_one_are_not_admitted_by_the_default_declaration() -> None:
    """Widening exit 1 globally is forbidden: these are truncated failures measuring nothing."""

    declarations = load_healthy_terminal_declarations()
    guardrail_records = [
        record for record in _salvaged_records() if record.tool == "architecture.guardrails"
    ]
    assert guardrail_records, "salvaged evidence must retain the guardrail counter-example"

    for record in guardrail_records:
        assert record.exit_code == 1
        terminals = healthy_terminal_exit_codes_for(record.tool, record.mode, declarations)
        assert terminals == DEFAULT_HEALTHY_TERMINAL_EXIT_CODES
        admission = admit_duration_sample(record, healthy_terminal_exit_codes=terminals)
        assert not admission.admitted
        assert admission.reason == "terminal_not_declared_healthy"


def test_every_corrupt_drift_lane_is_classified_and_declares_its_own_healthy_terminal() -> None:
    """Lock the denominator: a new corrupt-drift lane must be classified, not silently defaulted."""

    defining = {
        path.stem
        for path in VALIDATION_ROOT.rglob("*.py")
        if "def corrupt_field_drift_check" in path.read_text(encoding="utf-8")
    }
    assert defining == INVERTED_CORRUPT_LANES | NORMAL_CORRUPT_LANES, (
        "a corrupt-drift lane was added or removed; classify its healthy terminal by reading the "
        "status it returns on detection and the exit code main maps that status to"
    )

    declarations = load_healthy_terminal_declarations()
    for stem in INVERTED_CORRUPT_LANES:
        terminals = healthy_terminal_exit_codes_for(
            f"quality.validation.{stem}", CORRUPT_DRIFT_MODE, declarations
        )
        assert terminals == (1,), f"{stem} reports success at exit 1 and must declare it"
    for stem in NORMAL_CORRUPT_LANES:
        terminals = healthy_terminal_exit_codes_for(
            f"quality.validation.{stem}", CORRUPT_DRIFT_MODE, declarations
        )
        assert terminals == DEFAULT_HEALTHY_TERMINAL_EXIT_CODES, (
            f"{stem} reports success at exit 0 and must not declare a widened terminal"
        )


def test_declaration_is_resolved_for_both_direct_entry_and_registry_tool_names() -> None:
    """The same module is recorded under two namespaces; both must find the declaration."""

    declarations = load_healthy_terminal_declarations()
    direct = healthy_terminal_exit_codes_for(
        "quality.validation.check_layer3_gy_second_domain_pack", CORRUPT_DRIFT_MODE, declarations
    )
    registry = healthy_terminal_exit_codes_for(
        "validation.check-layer3-gy-second-domain-pack", CORRUPT_DRIFT_MODE, declarations
    )
    assert direct == registry == (1,)


def test_declared_modes_do_not_leak_into_other_modes_of_the_same_tool() -> None:
    """Exit 1 is the completed terminal only in the mode whose contract declares it."""

    declarations = load_healthy_terminal_declarations()
    write_terminals = healthy_terminal_exit_codes_for(
        "quality.validation.check_layer3_gy_second_domain_pack", "write", declarations
    )
    assert write_terminals == DEFAULT_HEALTHY_TERMINAL_EXIT_CODES

    write_failure = ToolRunRecord(
        tool="quality.validation.check_layer3_gy_second_domain_pack",
        category="quality",
        output_format="json",
        status="failed",
        preflight_status="ok",
        started_at="2026-08-13T09:52:04.088329+00:00",
        duration_ms=815_662.044,
        exit_code=1,
        mode="write",
    )
    assert not admit_duration_sample(
        write_failure, healthy_terminal_exit_codes=write_terminals
    ).admitted


def test_lane_summary_counts_a_declared_nonzero_terminal_as_an_admitted_run() -> None:
    """End to end: the catalog projection must see the corrupt lane's completed run."""

    catalog = load_timing_budget_catalog_data(
        {
            "lanes": [
                {
                    "timing_key": timing_key_for(
                        "quality.validation.check_layer3_gy_second_domain_pack",
                        CORRUPT_DRIFT_MODE,
                    ),
                    "tool": "quality.validation.check_layer3_gy_second_domain_pack",
                    "mode": CORRUPT_DRIFT_MODE,
                    "command": "python tools/quality/validation/check_layer3_gy_second_domain_pack.py --corrupt-field-drift-check",
                    "samples_ms": [31661.172],
                    "measured_p95_ms": 31661.172,
                    "recommended_timeout_ms": 63322.344,
                    "source_refs": ["docs/superpowers/timing-evidence/README.md:1"],
                    "sample_admission_predicate": "manual_journal_excerpt:v1",
                    "regime": "serialized",
                }
            ]
        }
    )
    records = [
        record
        for record in _salvaged_records()
        if record.tool.endswith("check_layer3_gy_second_domain_pack")
        and record.mode == CORRUPT_DRIFT_MODE
    ]
    summaries = summarize_timing_budget_lanes(records, catalog)

    assert len(summaries) == 1
    assert summaries[0].admitted_runs == len(records)
    assert summaries[0].inadmissible_runs == 0
    assert summaries[0].local_failures == len(records)  # the retained proxy still says "failed"


def test_default_timing_log_is_durable_and_not_under_tmp() -> None:
    """GY-DI3: a reboot or tmp sweep must not erase the measurement substrate."""

    default_path = default_timing_log_path()

    assert not default_path.is_relative_to(Path(tempfile.gettempdir()))
    assert not str(default_path).startswith(("/tmp/", "/private/tmp/", "/var/tmp/"))
    assert default_path.is_relative_to(REPO_ROOT), "the log must live inside the repository"
    assert default_path.name.endswith(".jsonl")


def test_default_timing_log_location_is_ignored_but_its_evidence_path_is_committed() -> None:
    """Ignored is fine; ignored under /tmp was the defect. Promotion is what protects evidence."""

    default_path = default_timing_log_path()
    ignore_check = subprocess.run(  # noqa: S603 - trusted local git query.
        ["git", "check-ignore", "-q", str(default_path)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert ignore_check.returncode == 0, "the rolling log must not be committed"

    tracked = subprocess.run(  # noqa: S603 - trusted local git query.
        ["git", "ls-files", "--error-unmatch", str(SALVAGED_TIMING_RECORDS.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    assert tracked.returncode == 0, "promoted timing evidence must be committed"


def test_default_retention_holds_a_sample_for_every_currently_known_lane() -> None:
    """The retention number is a measurement of the lane count, not a constant."""

    catalogued = {lane.timing_key for lane in load_timing_budget_catalog()}
    observed = {
        timing_key_for(record.tool, record.mode) for record in _salvaged_records()
    }
    known_lanes = catalogued | observed

    assert len(known_lanes) <= DEFAULT_TIMING_RETENTION, (
        "retention below the lane count guarantees a lane loses its only sample"
    )
    assert DEFAULT_TIMING_RETENTION // len(known_lanes) >= 25, (
        f"{len(known_lanes)} known lanes need headroom for a p95 to survive a wave; "
        "re-derive the retention default if the lane count moved"
    )


def test_retention_still_caps_the_log_at_the_default_limit(tmp_path: Path) -> None:
    """Raising the default must not disable the cap that keeps the log bounded."""

    log = tmp_path / "timing.jsonl"
    record = ToolRunRecord(
        tool="quality.validation.check_layer3_gy_second_domain_pack",
        category="quality",
        output_format="json",
        status="ok",
        preflight_status="ok",
        started_at="2026-08-13T09:52:04.088329+00:00",
        duration_ms=815_662.044,
        exit_code=0,
        mode="write",
    )
    log.write_text(
        "".join(
            json.dumps(dataclasses.asdict(record), sort_keys=True) + "\n"
            for _ in range(DEFAULT_TIMING_RETENTION + 25)
        ),
        encoding="utf-8",
    )
    append_timing_record(log, record)

    assert len(read_timing_records(log)) == DEFAULT_TIMING_RETENTION


def _catalog_lane_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "timing_key": "quality.validation.check_layer3_gy_second_domain_pack:write",
        "tool": "quality.validation.check_layer3_gy_second_domain_pack",
        "mode": "write",
        "command": "python tools/quality/validation/check_layer3_gy_second_domain_pack.py --write",
        "samples_ms": [815662.044],
        "measured_p95_ms": 815662.044,
        "recommended_timeout_ms": 1631324.088,
        "source_refs": ["docs/superpowers/timing-evidence/README.md:1"],
        "sample_admission_predicate": "declared_healthy_terminal:v1",
        "regime": "contended",
    }
    payload.update(overrides)
    return payload


def test_derived_lane_timing_key_is_the_tool_and_mode_join_the_catalog_already_enforces() -> None:
    """State the join rather than invent one: records carry tool+mode, the catalog keys on both."""

    derived = derive_timing_budget_lanes(_salvaged_records())

    for lane in derived:
        assert lane.timing_key == f"{lane.tool}:{lane.mode}"
        assert lane.timing_key == timing_key_for(lane.tool, lane.mode)


def test_uncatalogued_lanes_name_the_write_lane_whose_absence_stopped_a_wave() -> None:
    """GY-DI2: a lane with real samples must never be silently absent at the point of use."""

    catalog = load_timing_budget_catalog()
    missing = uncatalogued_timing_lanes(_salvaged_records(), catalog)
    missing_keys = {lane.timing_key for lane in missing}

    assert "quality.validation.check_layer3_gy_second_domain_pack:write" in missing_keys
    assert missing_keys.isdisjoint({lane.timing_key for lane in catalog})

    observed = {
        timing_key_for(record.tool, record.mode) for record in _salvaged_records()
    }
    catalogued = {lane.timing_key for lane in catalog}
    assert missing_keys == observed - catalogued, "every observed-but-absent lane must be named"


def test_lane_without_an_admitted_sample_gets_no_derived_cap_and_is_marked_declared() -> None:
    """A lane with no successful sample of its own has no budget at all -- it must be declared."""

    derived = {lane.timing_key: lane for lane in derive_timing_budget_lanes(_salvaged_records())}

    # architecture.guardrails only ever recorded real failures; check-udf-perf only ever skipped.
    for key in ("architecture.guardrails:default", "diagnostics.check-udf-perf:default"):
        lane = derived[key]
        assert lane.samples_ms == ()
        assert lane.measured_p95_ms is None
        assert lane.recommended_timeout_ms is None
        assert lane.ceiling_is_declared is True


def test_a_lane_with_no_sample_never_inherits_a_sibling_lanes_number() -> None:
    """The forbidden closure: reconstructing a cap from another mode of the same tool."""

    records = [
        record
        for record in _salvaged_records()
        if record.tool.endswith("check_layer3_gy_second_domain_pack")
    ]
    derived = {lane.timing_key: lane for lane in derive_timing_budget_lanes(records)}
    rederive = derived["quality.validation.check_layer3_gy_second_domain_pack:rederive-audit"]
    write = derived["quality.validation.check_layer3_gy_second_domain_pack:write"]

    assert rederive.measured_p95_ms is not None
    assert write.measured_p95_ms is not None
    assert write.measured_p95_ms != rederive.measured_p95_ms
    assert write.samples_ms and rederive.samples_ms
    assert set(write.samples_ms).isdisjoint(rederive.samples_ms)


def test_derived_lanes_record_the_regime_their_samples_were_measured_in() -> None:
    """A sample carries its regime; an unrecorded regime stays 'unknown' rather than assumed."""

    derived = derive_timing_budget_lanes(_salvaged_records())

    assert derived
    for lane in derived:
        assert lane.regime in {"serialized", "contended", "unknown"}
        assert lane.sample_admission_predicate == SAMPLE_ADMISSION_PREDICATE_ID
    # The salvaged records predate the regime field, so none may claim to be serialized.
    assert {lane.regime for lane in derived} == {"unknown"}


def test_every_committed_catalog_row_records_which_predicate_admitted_its_samples() -> None:
    """A widened predicate must be visible rather than silent."""

    for lane in load_timing_budget_catalog():
        assert lane.sample_admission_predicate in SAMPLE_ADMISSION_PREDICATE_IDS
        assert lane.regime in {"serialized", "contended", "unknown"}


@pytest.mark.parametrize(
    "corruption",
    [
        {"sample_admission_predicate": "whatever_i_felt_like"},
        {"regime": "quiet_host"},
        {"regime": ""},
    ],
)
def test_catalog_rejects_an_unknown_predicate_or_regime(corruption: dict[str, object]) -> None:
    """Verify the verifier: a corrupted provenance field must fail the catalog loader."""

    with pytest.raises(ValueError):
        load_timing_budget_catalog_data({"lanes": [_catalog_lane_payload(**corruption)]})


def test_catalog_requires_the_provenance_fields_rather_than_defaulting_them() -> None:
    """An omitted predicate or regime must fail, not silently inherit a default."""

    for omitted in ("sample_admission_predicate", "regime"):
        payload = _catalog_lane_payload()
        del payload[omitted]
        with pytest.raises(ValueError):
            load_timing_budget_catalog_data({"lanes": [payload]})


def test_report_names_unbudgeted_lanes_at_the_point_of_use(tmp_path: Path) -> None:
    """An executor must learn its lane is unbudgeted before spending a run to find out."""

    from tools.cli import _render_timing_text, _summary_payload

    log = tmp_path / "timing.jsonl"
    log.write_text(
        "".join(
            json.dumps(json.loads(line)["raw"] and json.loads(json.loads(line)["raw"])) + "\n"
            for line in SALVAGED_TIMING_RECORDS.read_text(encoding="utf-8").splitlines()
        ),
        encoding="utf-8",
    )
    payload = _summary_payload(5, log)
    rendered = _render_timing_text(payload)

    assert isinstance(payload["uncatalogued_lanes"], list)
    assert payload["uncatalogued_lanes"], "the salvaged log contains uncatalogued lanes"
    assert "quality.validation.check_layer3_gy_second_domain_pack:write" in rendered
    assert "ABSENT from the budget catalog" in rendered
    assert "a ceiling must be DECLARED and recorded as supplied" in rendered


def test_nearest_rank_p95_is_the_maximum_below_the_published_threshold() -> None:
    """The threshold is arithmetic, not taste: below it the p95 IS the maximum."""

    for count in range(1, MIN_SAMPLES_FOR_P95):
        values = [float(value) for value in range(count)]
        assert percentile_ms(values, 0.95) == max(values), count

    boundary = [float(value) for value in range(MIN_SAMPLES_FOR_P95)]
    assert percentile_ms(boundary, 0.95) != max(boundary), (
        "MIN_SAMPLES_FOR_P95 must be the first count where a p95 carries tail information"
    )


@pytest.mark.parametrize(
    ("sample_count", "expected_basis"),
    [
        (0, "declared"),
        (1, "max_observed"),
        (MIN_SAMPLES_FOR_P95 - 1, "max_observed"),
        (MIN_SAMPLES_FOR_P95, "p95"),
        (MIN_SAMPLES_FOR_P95 + 5, "p95"),
    ],
)
def test_budget_basis_names_what_the_ceiling_actually_rests_on(
    sample_count: int, expected_basis: str
) -> None:
    assert budget_basis_for(sample_count) == expected_basis


def test_no_p95_is_published_for_a_lane_that_cannot_support_one() -> None:
    """Forbidden closure: publishing a percentile from a sample count that cannot support it."""

    derived = derive_timing_budget_lanes(_salvaged_records())

    assert derived
    for lane in derived:
        if len(lane.samples_ms) < MIN_SAMPLES_FOR_P95:
            assert lane.published_p95_ms is None, lane.timing_key
        if lane.samples_ms:
            assert lane.max_observed_ms == max(lane.samples_ms)
        else:
            assert lane.budget_basis == "declared"
            assert lane.max_observed_ms is None


def test_committed_catalog_publishes_no_p95_it_cannot_support() -> None:
    """Measured: every committed row currently stores a maximum, not a percentile."""

    catalog = load_timing_budget_catalog()

    for lane in catalog:
        assert lane.measured_p95_ms == max(lane.samples_ms), lane.timing_key
        if len(lane.samples_ms) < MIN_SAMPLES_FOR_P95:
            assert lane.published_p95_ms is None
            assert lane.budget_basis == "max_observed"


def test_report_labels_a_sub_threshold_ceiling_as_a_maximum_not_a_p95(tmp_path: Path) -> None:
    """A reader must be able to tell a percentile from a maximum at the point of use."""

    from tools.cli import _render_timing_text, _summary_payload

    log = tmp_path / "timing.jsonl"
    log.write_text(
        "".join(
            json.loads(line)["raw"] + "\n"
            for line in SALVAGED_TIMING_RECORDS.read_text(encoding="utf-8").splitlines()
        ),
        encoding="utf-8",
    )
    payload = _summary_payload(5, log, include_unmeasured=True)
    rendered = _render_timing_text(payload)

    assert payload["min_samples_for_p95"] == MIN_SAMPLES_FOR_P95
    assert payload["lanes_publishing_a_p95"] == 0, "no lane currently has enough samples"
    assert "too few for a p95" in rendered
    for lane in payload["lane_summaries"]:
        assert lane["budget_basis"] in {"p95", "max_observed", "declared"}
        if lane["budget_basis"] != "p95":
            assert lane["published_p95_ms"] is None


def test_every_gy_validator_persists_timing_at_its_own_entry_point() -> None:
    """The invocation contract: plans call these scripts directly and must keep doing so."""

    scripts = sorted(VALIDATION_ROOT.glob("check_layer3_gy_*.py"))
    assert scripts, "the GY validator surface must not be empty"

    for script in scripts:
        source = script.read_text(encoding="utf-8")
        assert "run_timed_entrypoint" in source, script.name

    # None of them are registered as tools.cli commands, so nothing may require that path.
    registry_source = (REPO_ROOT / "tools" / "cli.py").read_text(encoding="utf-8")
    assert "check_layer3_gy" not in registry_source
