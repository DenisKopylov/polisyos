"""Observe persisted threshold consumers and remove only float-scalar preservation.

The source parser and all actual DuckDB/evaluation behavior stay active. For the
matched removal a float is routed through the existing text scanner, as if the
new scalar-preservation branch were absent. Zero-text controls may still pass.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

TARGET = "test_reopened_threshold_consumer_retains_numeric_scalar"
EVENTS = []
REPORTS = []
RESTORE = []
CURRENT = None


def record(kind, **data):
    EVENTS.append({"nodeid": CURRENT, "kind": kind, **data})


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global CURRENT
    if item.originalname != TARGET:
        return
    CURRENT = item.nodeid
    from polisyos.lex.knowledge.store import LegalKnowledgeStore

    mode = os.environ.get("ORCH02_NUMERIC_SCALAR", "observe")
    if mode not in {"observe", "remove"}:
        raise ValueError("ORCH02_NUMERIC_SCALAR must be observe or remove")
    original_parse = LegalKnowledgeStore._parse_numeric_values
    original_evaluate = LegalKnowledgeStore.evaluate_rule_threshold
    record("fixture_setup", mode=mode,
           parser_source_sha256=hashlib.sha256(inspect.getsource(original_parse).encode()).hexdigest(),
           owned_test_source_sha256=hashlib.sha256(Path(item.path).read_bytes()).hexdigest())

    def parse(*values):
        supplied = tuple(str(value) if isinstance(value, float) else value for value in values) if mode == "remove" else values
        result = original_parse(*supplied)
        record("actual_parser_call", raw_values=list(values), supplied_values=list(supplied),
               parsed_values=list(result), float_branch_removed=mode == "remove")
        return result

    def evaluate(store, *args, **kwargs):
        result = original_evaluate(store, *args, **kwargs)
        record("actual_persisted_threshold_evaluation", request=kwargs,
               actual_result=result.model_dump(mode="json"))
        return result

    LegalKnowledgeStore._parse_numeric_values = staticmethod(parse)
    LegalKnowledgeStore.evaluate_rule_threshold = evaluate
    RESTORE.extend([
        (LegalKnowledgeStore, "_parse_numeric_values", staticmethod(original_parse)),
        (LegalKnowledgeStore, "evaluate_rule_threshold", original_evaluate),
    ])


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    global CURRENT
    yield
    if item.originalname == TARGET:
        for owner, name, original in reversed(RESTORE):
            setattr(owner, name, original)
        RESTORE.clear()
        CURRENT = None


def pytest_runtest_logreport(report):
    if TARGET in report.nodeid:
        REPORTS.append({"nodeid": report.nodeid, "when": report.when,
                        "outcome": report.outcome, "duration_seconds": report.duration})


def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ["ORCH02_OUTPUT_DIR"])
    payload = {
        "schema": "orch02r2.actual-numeric-scalar-probe.v1",
        "mode": os.environ.get("ORCH02_NUMERIC_SCALAR", "observe"),
        "raw_pytest_exitstatus": int(exitstatus),
        "removed_quantity": "ONLY float-scalar preservation; float routed through existing text scanner" if os.environ.get("ORCH02_NUMERIC_SCALAR") == "remove" else None,
        "retained_quantities": ["actual persisted DuckDB fact/threshold rows", "reopened LegalKnowledgeStore", "actual evaluate_rule_threshold and unit/scope/operator rules", "unchanged owned test assertions"],
        "oracle": "Raw actual consumer pytest assertions, no keyword/marker classifier; actual status/reason/normalized scalar events accompany failures",
        "reports": REPORTS,
        "events": EVENTS,
        "source_files_changed": False,
    }
    (out / "numeric-events.json").write_text(json.dumps(payload, indent=2) + "\n")
