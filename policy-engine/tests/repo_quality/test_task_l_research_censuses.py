"""Behavioral closure evidence for the five Task L register rows."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from polisyos.runtime.http.permissions import RuntimePermission
from tests.unit.runtime.quality import test_agent_action_authority as authority_fixtures

REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_ROOT = (
    REPO_ROOT / "docs" / "research" / "policy-operations" / "register-closure" / "task-l"
)
AUTHORITY_CENSUS = RESEARCH_ROOT / "authority_census.py"
LIFECYCLE_CENSUS = RESEARCH_ROOT / "lifecycle_census.py"
LOCALE_CENSUS_PYTHON = RESEARCH_ROOT / "locale_census.py"
LOCALE_CENSUS_NODE = RESEARCH_ROOT / "locale_census.mjs"
LOCALES = REPO_ROOT / "apps" / "runtime-dashboard" / "src" / "shared" / "i18n" / "locales"


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load research census: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _run_json(*command: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object] | None]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout) if completed.returncode == 0 else None
    return completed, payload


def test_int_r5_chain_falsifier_detects_one_corrupt_member() -> None:
    census = _load_module(AUTHORITY_CENSUS, "task_l_authority_census_falsifier")
    records = census.complete_chain_fixture()

    established = census.validate_authority_chain(records)

    assert established["status"] == "established"
    corrupt = copy.deepcopy(records)
    corrupt["conjunction-evaluator"]["consumes"].remove("pao_r4.crossing_receipt")
    with pytest.raises(census.AuthorityChainIncompleteError) as exc_info:
        census.validate_authority_chain(corrupt)
    assert exc_info.value.code == "conjunction_evaluator_input_missing"


def test_current_authority_denominators_agree_and_chain_is_not_established() -> None:
    census = _load_module(AUTHORITY_CENSUS, "task_l_authority_census_current")

    report = census.census_repository(REPO_ROOT)

    assert report["denominator"]["derivations_agree"] is True
    assert report["denominator"]["filesystem_count"] == report["denominator"]["git_count"]
    assert report["target_census"]["int_r5_files"] == 0
    assert report["target_census"]["pao_r4_files"] == 0
    assert report["target_census"]["conjunction_evaluator_files"] == 0
    assert report["target_census"]["target_call_sites"] == 0
    assert report["target_census"]["target_call_derivations_agree"] is True
    assert report["target_census"]["target_event_or_artifact_sites"] == 0
    assert report["target_census"]["target_event_derivations_agree"] is True
    provider = report["acquisition_authority_provider_census"]
    assert provider["derivations_agree"] is True
    assert provider["python_parse_ambiguous_count"] == 0
    assert provider["concrete_provider_count"] == 0
    assert report["authority_chain"]["status"] == "not_established"


def test_acquisition_authority_e2e_emits_one_decision_and_bound_companions(
    tmp_path: Path,
) -> None:
    census = _load_module(AUTHORITY_CENSUS, "task_l_authority_census_e2e")
    harness = authority_fixtures._harness(tmp_path)
    authority = authority_fixtures._authority_module()
    action_kind = authority.ACQUISITION_ACTION_KIND
    operation = authority_fixtures._operation(action_kind)
    invocation = authority_fixtures._invocation(operation)
    intent = authority_fixtures._intent(action_kind)
    permission = authority_fixtures._proof(RuntimePermission.EVIDENCE_ACQUIRE)
    effects: list[str] = []
    binding = authority_fixtures._binding(operation, effects, action_kind=action_kind)
    gateway, _, _ = authority_fixtures._prepare_gateway(
        harness,
        contract=authority_fixtures._contract(
            authority_fixtures._envelope(
                action_kind=action_kind,
                operation_id=operation.operation_id,
                permission=RuntimePermission.EVIDENCE_ACQUIRE,
            )
        ),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
        bound_permission=permission,
    )
    try:
        before = census.authority_artifacts(harness.root)
        before_store = {str(artifact_id) for artifact_id in harness.store.iter_artifact_ids()}
        with authority.agent_action_authority_scope(gateway):
            decision = authority.produce_agent_action_authority_decision(
                bound_permission=permission,
                operation=operation,
                invocation=invocation,
                intent=intent,
            )
            persisted = gateway.persist_decision(decision)
        after = census.authority_artifacts(harness.root)
        after_store = {str(artifact_id) for artifact_id in harness.store.iter_artifact_ids()}

        delta = census.assert_single_authority_delta(
            before,
            after,
            expected_ref=str(persisted.write_result.cas_ref.artifact_id),
            expected_kind=authority.AGENT_ACTION_DECISION_ARTIFACT_KIND,
        )
        assert decision.outcome == "refused"
        assert decision.refusal_reasons
        assert effects == []
        assert set(after) - set(before) == after_store - before_store
        assert delta["new_artifact_count"] == 1
        assert delta["custody_companion_count"] == 3
        assert delta["duplicate_competence_certificate_count"] == 0
    finally:
        harness.control_store.close()


def test_duplicate_competence_certificate_delta_fails_under_a_neutral_kind() -> None:
    census = _load_module(AUTHORITY_CENSUS, "task_l_authority_census_duplicate")
    before: dict[str, dict[str, object]] = {}
    after = {
        "sha256:" + "a" * 64: {"kind": "runtime.agent_action_authority_decision"},
        "sha256:" + "b" * 64: {
            "kind": "runtime.generic_receipt",
            "payload": {
                "authoritative_for": ["decision_maker_competence"],
                "certifies": "delegation_validity",
            },
        },
    }

    with pytest.raises(census.AuthorityArtifactDeltaError) as exc_info:
        census.assert_single_authority_delta(
            before,
            after,
            expected_ref="sha256:" + "a" * 64,
            expected_kind="runtime.agent_action_authority_decision",
        )
    assert exc_info.value.code == "unexpected_authority_artifact_delta"


def test_rule_change_table_has_two_agreeing_derivations() -> None:
    census = _load_module(LIFECYCLE_CENSUS, "task_l_lifecycle_census")

    report = census.build_report(REPO_ROOT)

    assert report["derivations_agree"] is True
    assert report["change_class_count"] == 9
    assert report["lifecycle_action_counts"] == {
        "none": 2,
        "partial_reissue": 5,
        "review_required": 2,
    }
    assert report["unmapped_requested_actions"] == [
        "downgrade",
        "full_reissue",
        "termination",
    ]


def test_independent_locale_parsers_agree_on_every_current_leaf() -> None:
    python_run, python_report = _run_json(
        sys.executable,
        str(LOCALE_CENSUS_PYTHON),
        str(LOCALES),
    )
    node = shutil.which("node")
    assert node is not None
    node_run, node_report = _run_json(node, str(LOCALE_CENSUS_NODE), str(LOCALES))

    assert python_run.returncode == 0, python_run.stderr
    assert node_run.returncode == 0, node_run.stderr
    assert python_report is not None
    assert node_report is not None
    reconciler = _load_module(LOCALE_CENSUS_PYTHON, "task_l_locale_reconciler")
    reconciled = reconciler.reconcile_reports(python_report, node_report)
    assert reconciled["status"] == "independently_reconciled"
    assert reconciled["directory_file_count"] == 3


def test_locale_corrupt_field_proves_decoder_and_result_independence(tmp_path: Path) -> None:
    copied = tmp_path / "locales"
    shutil.copytree(LOCALES, copied)
    english = copied / "en.json"
    original = english.read_text(encoding="utf-8")
    needle = '"loading": "Loading...",'
    assert original.count(needle) == 1
    english.write_text(
        original.replace(needle, needle + '\n    "loading": "duplicate corruption",'),
        encoding="utf-8",
    )

    python_run, _ = _run_json(sys.executable, str(LOCALE_CENSUS_PYTHON), str(copied))
    node = shutil.which("node")
    assert node is not None
    node_run, _ = _run_json(node, str(LOCALE_CENSUS_NODE), str(copied))

    assert python_run.returncode == 2
    assert node_run.returncode == 2
    assert "python_json_duplicate_key" in python_run.stderr
    assert "node_recursive_duplicate_key" in node_run.stderr
    assert python_run.stderr != node_run.stderr
    node_source = LOCALE_CENSUS_NODE.read_text(encoding="utf-8")
    python_source = LOCALE_CENSUS_PYTHON.read_text(encoding="utf-8")
    assert "JSON.parse" not in node_source
    assert LOCALE_CENSUS_PYTHON.name not in node_source
    assert LOCALE_CENSUS_NODE.name not in python_source


def test_locale_reconciliation_rejects_one_corrupt_report_field() -> None:
    python_run, python_report = _run_json(
        sys.executable,
        str(LOCALE_CENSUS_PYTHON),
        str(LOCALES),
    )
    node = shutil.which("node")
    assert node is not None
    node_run, node_report = _run_json(node, str(LOCALE_CENSUS_NODE), str(LOCALES))
    assert python_run.returncode == node_run.returncode == 0
    assert python_report is not None and node_report is not None
    corrupted = copy.deepcopy(python_report)
    corrupted["locales"]["en"]["leaf_count"] += 1
    reconciler = _load_module(LOCALE_CENSUS_PYTHON, "task_l_locale_reconciler_corrupt")

    with pytest.raises(reconciler.LocaleCensusMismatchError) as exc_info:
        reconciler.reconcile_reports(corrupted, node_report)
    assert exc_info.value.code == "parser_reports_disagree"
