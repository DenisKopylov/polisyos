"""Run six existing J falsifiers once, with isolated call/teardown mutations.

Native failures remain failures (normally exit 1). No production file is edited.
--describe-only performs stdlib source reads, without importing pytest or owners.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import copy
import hashlib
import inspect
import json
from pathlib import Path
import re

from _build.gy_gaps import j_l_regression_wave as source_owner

ROOT = source_owner.ROOT
ADMISSION = "tests/unit/runtime/quality/workspace/test_production_case_admission.py"
PROOF = "tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py"
SELECTED = {
    ADMISSION + "::test_production_attempts_original_requirements_through_s1_before_terminal": "s1-execution",
    ADMISSION + "::test_original_source_markers_do_not_admit_changed_demand": "original-source",
    ADMISSION + "::test_actual_production_workspace_custody_survives_annotated_reader": "workspace-union",
    PROOF + "::test_full_recorded_gx_is_replayed_and_failed_marker_cannot_disappear": "gx-result-consumption",
    PROOF + "::test_recorded_refusal_capsule_requires_complete_actual_recomputation": "recorded-recomputation",
    PROOF + "::test_production_p28_refuses_detached_named_witness_dependency": "witness-dependency",
}
PREDECESSORS = (
    "_build/gy-gaps/j/removal_probes.py",
    "_build/gy-gaps/j/merge-planning/recorded_recomputation_removal.py",
    "_build/gy-gaps/j/merge-planning/witness_dependency_removal.py",
)
EXTRA_SOURCES = (
    "_build/gy_gaps/j_removal_wave.py", "_build/gy_gaps/j_l_regression_wave.py", *PREDECESSORS,
)
ABSENT = object()


def emit(kind: str, value: object) -> None:
    print("GY_J_REMOVAL_" + kind + " " + json.dumps(value, sort_keys=True), flush=True)


def digest(value: object) -> str:
    return source_owner.canonical_hash(value)


def population() -> set[str]:
    result = set()
    for path in (ADMISSION, PROOF):
        source = (ROOT / path).read_text()
        parsed = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)]
        functions = {node.name: node for node in parsed}
        require = source_owner.require
        require(len(functions) == len(parsed), "duplicate_native_definition:" + path)
        independently = re.findall(r"^def (test_[A-Za-z0-9_]+)\(", source, re.M)
        wanted = {node.split("::", 1)[1] for node in SELECTED if node.startswith(path + "::")}
        require(wanted <= functions.keys() and wanted <= set(independently),
                "existing_falsifier_definition_absent:" + path)
        for name in wanted:
            decorators = functions[name].decorator_list
            base = path + "::" + name
            if not decorators:
                result.add(base)
                continue
            require(len(decorators) == 1, "unclassified_stacked_parameter_population:" + base)
            decorator = decorators[0]
            require(isinstance(decorator, ast.Call)
                    and ast.unparse(decorator.func) == "pytest.mark.parametrize"
                    and len(decorator.args) == 2 and not decorator.keywords,
                    "unclassified_parameter_declaration:" + base)
            values = ast.literal_eval(decorator.args[1])
            require(type(values) is list and all(type(value) is str for value in values)
                    and len(values) == len(set(values)), "unclassified_parameter_ids:" + base)
            result.update(base + "[" + value + "]" for value in values)
    source_owner.require({node.split("[", 1)[0] for node in result} == set(SELECTED),
                         "expanded_definition_population_mismatch")
    return result


def source_fence() -> dict:
    values = source_owner.source_snapshot()
    for path in EXTRA_SOURCES:
        values[path] = {"state": "present", "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
    return values


def family_fingerprint(item, owner) -> dict:
    """Read only actual module fixture objects; never synthesize a family."""
    result = {}
    if "actual_j_family_pair" in item.funcargs:
        old, new, observation = item.funcargs["actual_j_family_pair"]
        for label, family in (("old", old), ("fresh", new)):
            raw = family._frozen_final_output()
            packet = family._j_checked_gx_packet()
            result[label] = {
                "full_family_sha256": hashlib.sha256(owner.serialize_loop_artifact(raw)).hexdigest(),
                "full_private_gx_packet_sha256": hashlib.sha256(owner.serialize_loop_artifact(packet)).hexdigest(),
                "gx_status": packet["verification"]["status"],
                "complete_family_members": sorted(raw),
                "request_ref": raw[owner.OUTCOME_RUN_PATH]["recorded_production_evidence"]["request_ref"],
                "admission_ref": raw[owner.OUTCOME_RUN_PATH]["recorded_production_evidence"]["admission_ref"],
            }
        request, snapshot = observation._checked_snapshot()
        custody = observation._checked_custody()
        result["fresh_observation"] = {
            "request": request.model_dump(mode="json"), "snapshot_sha256": digest(snapshot),
            "custody_sha256": digest(custody),
        }
    if "actual_j_witness_semantic_pairs" in item.funcargs:
        result["witness_semantic_pairs"] = [
            {"raw_sha256": digest(raw), "semantic_sha256": digest(semantics),
             "references_sha256": digest(refs),
             "complete_verified_values_sha256": digest(
                 sorted((key.hex(), value) for key, value in values.items()))}
            for _, raw, semantics, refs, values in item.funcargs["actual_j_witness_semantic_pairs"]
        ]
    return result


def actual_production_setup(item, loop) -> tuple[object, dict]:
    source, payload, ref = item.funcargs["production_input"]
    result = item.module._actual_entry(source, ref)
    members = [entry for entry in result.artifact_envelopes
               if entry.payload_schema_ref == loop.PRODUCTION_CASE_ADMISSION_SCHEMA]
    source_owner.require(len(members) == 1, "actual_positive_setup_admission_not_unique")
    admission = loop.resolve_production_case_admission(
        store=source.store, receipt_ref=members[0].payload_ref, request_ref=ref, catalog=source.graph,
    )
    expected = [row["construct_ref"] for row in payload["pinned_request"]["requested_constructs"]]
    actual = [decision.claim_id for decision in admission.graded_decisions]
    source_owner.require(actual == expected and len(set(actual)) == len(actual),
                         "actual_positive_setup_claim_population_mismatch")
    return admission, {
        "source_request_ref": ref, "source_admission_ref": members[0].payload_ref,
        "actual_terminal": result.terminal_state.model_dump(mode="json"),
        "actual_result_sha256": digest(result.model_dump(mode="json")),
        "actual_admission_sha256": digest(admission.model_dump(mode="json")),
        "whole_original_claim_identities": actual,
        "positive_admission_state": admission.positive_admission_state,
        "authority_boundary": result.authority_boundary,
        "scope": "actual engineering refusal setup; no positive scientific admission",
    }


def replace_call(patch, module, name: str, before: str, after: str) -> dict:
    original = getattr(module, name)
    source = inspect.getsource(original)
    source_owner.require(source.count(before) == 1, "removal_seam_not_unique:" + name)
    changed = source.replace(before, after, 1)
    namespace = {}
    # Resolve all unmodified globals in the real owner, so native monkeypatch
    # observers still reach the executed function. Do not capture a stale copy.
    exec(compile("from __future__ import annotations\n" + changed,
                 inspect.getsourcefile(original), "exec"), module.__dict__, namespace)
    patch.setattr(module, name, namespace[name])
    return {"owner": module.__name__, "function": name, "removed": before, "replacement": after,
            "original_function_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "in_memory_function_sha256": hashlib.sha256(changed.encode()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe-only", action="store_true")
    args = parser.parse_args()
    source_owner.require(Path.cwd().resolve() == ROOT, "run_from_product_root")
    before, expected = source_fence(), population()
    emit("POPULATION", {
        "definition_modes": SELECTED, "definition_denominator": len(SELECTED),
        "independent_expanded_denominator": len(expected),
        "complete_expected_identity_sha256": digest(sorted(expected)),
        "source_before": source_owner.source_summary(before),
        "removal_source_refs": {path: before[path] for path in EXTRA_SOURCES},
        "describe_only": args.describe_only,
        "fixture_policy": "actual module fixtures shared by one pytest session; mutations only after setup",
    })
    if args.describe_only:
        source_owner.require(source_fence() == before, "source_changed_during_description")
        return 0

    import pytest

    collected, outcomes, prepared, restored, problems = [], [], {}, {}, []
    active = {}

    class ScopedRemovals:
        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_call(self, item):
            from polisyos.runtime.quality.workspace import loop
            from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

            mode = SELECTED[item.nodeid.split("[", 1)[0]]
            shared = family_fingerprint(item, owner)
            setup = {"actual_module_fixture": shared}
            admission = None
            if "production_input" in item.funcargs:
                admission, setup = actual_production_setup(item, loop)
            retained = None
            if mode == "recorded-recomputation":
                old, _, _ = item.funcargs["actual_j_family_pair"]
                payload = old._frozen_final_output()
                packet, store, _ = owner._restore_j_recorded_evidence(
                    outcome=payload[owner.OUTCOME_RUN_PATH],
                    replay_artifact=payload[owner.OUTCOME_REPLAY_PATH], repo_root=ROOT,
                )
                retained = loop.resolve_production_case_admission(
                    store=store, receipt_ref=packet["admission_ref"], request_ref=packet["request_ref"],
                    catalog=item.funcargs["actual_j_catalog"], repo_root=ROOT,
                )
                setup["actual_replayed_admission"] = {
                    "request_ref": packet["request_ref"], "admission_ref": packet["admission_ref"],
                    "full_payload_sha256": digest(retained.model_dump(mode="json")),
                    "whole_claim_identities": [row.claim_id for row in retained.graded_decisions],
                }
            context = pytest.MonkeyPatch.context()
            patch = context.__enter__()
            touched = []

            def set_attribute(module, name, value):
                original = getattr(module, name)
                touched.append((module, name, original))
                patch.setattr(module, name, value)

            try:
                detail = {"removed_property": mode, "disk_source_and_markers_retained": True}
                if mode == "s1-execution":
                    snapshots = {decision.claim_id: decision.model_dump(mode="json")
                                 for decision in admission.graded_decisions}
                    touched.append((loop, "_gy_j_probe_retained_s1",
                                    getattr(loop, "_gy_j_probe_retained_s1", ABSENT)))
                    patch.setitem(loop.__dict__, "_gy_j_probe_retained_s1", lambda evidence:
                                  loop.GradedOutcomeDecision.model_validate(copy.deepcopy(snapshots[evidence.claim_id])))
                    touched.append((loop, "_compose_production_case_admission", loop._compose_production_case_admission))
                    detail["call_delta"] = replace_call(
                        patch, loop, "_compose_production_case_admission",
                        "decision = compose_graded_outcome(evidence)",
                        "decision = _gy_j_probe_retained_s1(evidence)",
                    )
                elif mode == "original-source":
                    set_attribute(loop, "_verify_production_case_intake", lambda *_args, **_kwargs: None)
                elif mode == "workspace-union":
                    from pydantic import create_model
                    unguarded = create_model(
                        "WorkspaceSearchExitContractWithoutRefusalUnion", __base__=loop.WorkspaceSearchExitContract,
                        workspace_contract=(loop.WorkspaceContract, ...),
                    )
                    set_attribute(loop, "WorkspaceSearchExitContract", unguarded)
                elif mode == "gx-result-consumption":
                    touched.append((owner, "_compare_j_current_outputs", owner._compare_j_current_outputs))
                    detail["call_delta"] = replace_call(
                        patch, owner, "_compare_j_current_outputs", 'expected = old_packet["verification"]',
                        'expected = committed[OUTCOME_RUN_PATH]["gx_validation"]',
                    )
                elif mode == "recorded-recomputation":
                    set_attribute(loop, "resolve_production_case_admission", lambda **_kwargs: retained)
                else:
                    set_attribute(owner, "_j_require_production_witness_dependency", lambda **_kwargs: None)
                active[item.nodeid] = (context, touched, shared, owner)
                prepared[item.nodeid] = mode
                emit("PREPARED", {"nodeid": item.nodeid, "positive_custodied_setup": setup, **detail})
            except BaseException:
                context.__exit__(None, None, None)
                raise
            yield
            # Do not undo here. The native monkeypatch fixture can have observed
            # the mutant; its undo must finish before our outer undo runs.

        @pytest.hookimpl(hookwrapper=True, tryfirst=True)
        def pytest_runtest_teardown(self, item, nextitem):
            try:
                yield
            finally:
                state = active.pop(item.nodeid, None)
                if state is not None:
                    context, touched, shared, owner = state
                    context.__exit__(None, None, None)
                    changed = [module.__name__ + "." + name for module, name, original in touched
                               if getattr(module, name, ABSENT) is not original]
                    unchanged = family_fingerprint(item, owner) == shared
                    restored[item.nodeid] = not changed and unchanged
                    emit("RESTORED", {"nodeid": item.nodeid, "exact_owner_objects_restored": not changed,
                                      "changed_owner_objects": changed, "shared_actual_fixture_unchanged": unchanged})
                    source_owner.require(not changed and unchanged, "removal_restore_or_shared_fixture_drift")

        def pytest_collection_finish(self, session):
            collected.extend(item.nodeid for item in session.items)
            source_owner.require(set(collected) == expected and len(collected) == len(expected),
                                 "actual_collected_falsifier_identity_population_changed")

        def pytest_runtest_logreport(self, report):
            outcomes.append({"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome,
                             "wasxfail": str(getattr(report, "wasxfail", ""))})

        def pytest_sessionfinish(self, session):
            reporter = session.config.pluginmanager.get_plugin("terminalreporter")
            self.terminal = [
                {"nodeid": row.nodeid, "when": row.when, "outcome": row.outcome,
                 "wasxfail": str(getattr(row, "wasxfail", ""))}
                for category, reports in reporter.stats.items()
                if category in {"passed", "failed", "error", "skipped", "xfailed", "xpassed"}
                for row in reports if hasattr(row, "when")
            ]

    plugin = ScopedRemovals()
    result = int(pytest.main(["-q", "-s", "-rA", "--show-capture=no", "--tb=short", *SELECTED], plugins=[plugin]))
    # Teardown should cover every active hook, even when a native call fails.
    if active:
        for context, _, _, _ in active.values():
            context.__exit__(None, None, None)
        problems.append({"teardown_missing_for": sorted(active)})
    after = source_fence()
    visible = [row for row in outcomes if row["when"] == "call" or row["outcome"] != "passed"]
    if Counter(digest(row) for row in visible) != Counter(digest(row) for row in getattr(plugin, "terminal", [])):
        problems.append({"complete_terminal_progress_identity_mismatch": True})
    emitted = {row["nodeid"] for row in outcomes}
    if set(collected) != expected or emitted != expected or set(prepared) != expected or set(restored) != expected:
        problems.append({"complete_execution_population_mismatch": {
            "uncollected": sorted(expected - set(collected)), "unreported": sorted(expected - emitted),
            "unprepared": sorted(expected - prepared.keys()), "unrestored": sorted(expected - restored.keys()),
        }})
    if not all(restored.values()):
        problems.append({"restoration_failed": sorted(node for node, state in restored.items() if not state)})
    if before != after:
        problems.append({"source_changed_during_removals": {
            path: {"before": before[path] if path in before else {"state": "absent_identity"},
                   "after": after[path] if path in after else {"state": "absent_identity"}}
            for path in sorted(before.keys() | after.keys())
            if path not in before or path not in after or before[path] != after[path]
        }})
    calls = {row["nodeid"]: row["outcome"] for row in outcomes if row["when"] == "call"}
    noncalls = [row for row in outcomes if (row["when"] != "call" and row["outcome"] != "passed") or row["wasxfail"]]
    state = "not_established" if problems or noncalls or set(calls) != expected else (
        "all_native_controls_failed_at_call" if all(value == "failed" for value in calls.values())
        else "some_native_controls_did_not_fail")
    final = result if state != "not_established" else 2
    emit("READBACK", {
        "collected": collected, "outcomes": outcomes, "prepared": prepared, "restored": restored,
        "expanded_denominator": len(collected), "complete_call_states": calls,
        "falsifier_status": state, "reconciliation_issues": problems,
        "source_after": source_owner.source_summary(after), "source_frozen": before == after,
        "pytest_returncode": result, "returncode": final,
        "interpretation": "inspect full native failures for the removed property; exit 1 alone is not semantic proof",
    })
    return final


if __name__ == "__main__":
    raise SystemExit(main())
