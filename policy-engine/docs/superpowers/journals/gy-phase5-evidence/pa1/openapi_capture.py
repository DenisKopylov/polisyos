"""Capture actual fixture-only HTTP success bytes without changing the exercised path."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, S101, T201 - exact research observer
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

destination = Path(".tmp/gyphase5-pa1-openapi-example")
destination.mkdir(parents=True, exist_ok=True)
original_post = TestClient.post
captures = []


def observe_post(self, url, *args, **kwargs):
    response = original_post(self, url, *args, **kwargs)
    if str(url).endswith("/normative-evidence") and response.status_code == 200:
        raw = response.content
        path = destination / f"response-{len(captures) + 1}.json"
        path.write_bytes(raw)
        captures.append({
            "method": "POST",
            "path": str(url),
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type"),
            "body_file": str(path.resolve()),
            "body_sha256": hashlib.sha256(raw).hexdigest(),
            "body_bytes": len(raw),
            "scope": "fixture_only_transport_example",
            "authority_limitation": (
                "Emitted by the actual worker, later fixture-signed evidence intake and "
                "current-reader replay. Fixture principals, fixture trust and fixture "
                "source are not an institutional appointment, production candidate, "
                "canonical denominator, or a reusable admitted authority receipt."
            ),
        })
    return response


TestClient.post = observe_post
try:
    result = pytest.main([
        "tests/unit/runtime/http/test_normative_evidence_intake.py::"
        "test_post_source_signature_advances_both_current_job_readers",
        "-q",
    ])
finally:
    TestClient.post = original_post
assert len(captures) == 1, captures
metadata = {"pytest_returncode": int(result), "captures": captures}
(destination / "capture-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
print(json.dumps(metadata, indent=2), flush=True)
raise SystemExit(result)
