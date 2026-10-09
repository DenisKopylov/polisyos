"""Observe actual query consumers; optionally remove only request-profile pairing.

No source/test file is edited. Actual encoder identity, matrix/membership/index
loading and native HNSW query remain active. Raw pytest assertions decide.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

TARGET = "test_reopened_consumer_uses_saved_request_intent_before_encode_and_index"
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
    import hnswlib
    from polisyos.lex.knowledge.store import LegalKnowledgeStore

    mode = os.environ.get("ORCH02_PROFILE_GUARD", "observe")
    if mode not in {"observe", "remove"}:
        raise ValueError("ORCH02_PROFILE_GUARD must be observe or remove")
    original_guard = LegalKnowledgeStore._require_query_profile
    original_encode = item.module._DirectionalLegalEncoder.encode
    original_knn = hnswlib.Index.knn_query
    record("fixture_setup", mode=mode,
           guard_source_sha256=hashlib.sha256(inspect.getsource(original_guard).encode()).hexdigest(),
           owned_test_source_sha256=hashlib.sha256(Path(item.path).read_bytes()).hexdigest(),
           native_module_origin=hnswlib.__file__)

    def guard(query, generation, *, table_name):
        profiles = getattr(query, "profile", None)
        data = {
            "table_name": table_name,
            "query_text": getattr(query, "text", None),
            "encoder_object_id": id(getattr(query, "encoder", None)),
            "selected_generation_id": getattr(generation, "generation_id", None),
            "requested": None if profiles is None else [
                {"basis_kind": p.basis_kind, "generation_id": p.generation_id,
                 "inventory_sha256": hashlib.sha256(p.inventory_bytes).hexdigest()}
                for p in profiles
            ],
        }
        if mode == "remove":
            record("request_guard_removed", **data)
            return None
        try:
            original_guard(query, generation, table_name=table_name)
        except BaseException as exc:
            record("request_guard_refusal", **data,
                   error_type=type(exc).__name__, error_code=getattr(exc, "code", None))
            raise
        record("request_guard_accept", **data)

    def encode(encoder, texts, **kwargs):
        result = original_encode(encoder, texts, **kwargs)
        record("actual_encoder_call", encoder_object_id=id(encoder), texts=list(texts),
               output_shape=list(result.shape), kwargs=kwargs)
        return result

    def knn(index, *args, **kwargs):
        result = original_knn(index, *args, **kwargs)
        record("actual_native_knn", labels=result[0].tolist(), distances=result[1].tolist())
        return result

    LegalKnowledgeStore._require_query_profile = staticmethod(guard)
    item.module._DirectionalLegalEncoder.encode = encode
    hnswlib.Index.knn_query = knn
    RESTORE.extend([
        (LegalKnowledgeStore, "_require_query_profile", staticmethod(original_guard)),
        (item.module._DirectionalLegalEncoder, "encode", original_encode),
        (hnswlib.Index, "knn_query", original_knn),
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
        "schema": "orch02r2.actual-query-profile-probe.v1",
        "mode": os.environ.get("ORCH02_PROFILE_GUARD", "observe"),
        "raw_pytest_exitstatus": int(exitstatus),
        "removed_quantity": "ONLY LegalKnowledgeStore._require_query_profile pairing" if os.environ.get("ORCH02_PROFILE_GUARD") == "remove" else None,
        "retained_quantities": ["actual encoder identity and encode", "persisted matrix/membership/index validation", "native HNSW knn", "unchanged owned test assertions"],
        "oracle": "Raw actual consumer pytest assertions, no keyword/marker classifier; events are observations and do not replace assertions",
        "boundary": "Only queried table pairing; refuse before encode/native knn, not before selected index loading",
        "reports": REPORTS,
        "events": EVENTS,
        "source_files_changed": False,
    }
    (out / "profile-events.json").write_text(json.dumps(payload, indent=2) + "\n")
