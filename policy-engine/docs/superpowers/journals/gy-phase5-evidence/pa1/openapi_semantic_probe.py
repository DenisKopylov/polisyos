"""Exercise the complete OpenAPI example owner with its PA1 registration intact or removed."""
# ruff: noqa: S101, T201 - run-emitted research gate and complete denominator witness
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from polisyos.runtime.http import openapi_contract as owner
from polisyos.runtime.http._openapi_contract_helpers import iter_openapi_operations

mode = sys.argv[1]
root = Path.cwd()
capture_path = (
    root / "docs/superpowers/journals/gy-phase5-evidence/pa1/openapi-response-capture.json"
)
captured_bytes = capture_path.read_bytes()
captured = json.loads(captured_bytes)
assert captured == owner._NORMATIVE_EVIDENCE_FIXTURE_RESPONSE
schema = json.loads((root / "schemas/runtime_api_v1.openapi.json").read_bytes())
owner_identities = {
    (path, method, operation["operationId"])
    for path, method, operation in iter_openapi_operations(schema)
}
independent_identities = {
    (path, method, entry[method]["operationId"])
    for path, entry in schema["paths"].items()
    for method in ("get", "post") if method in entry
}
assert owner_identities == independent_identities
positive = (
    "tests/unit/runtime/http/test_runtime_api_contract_hardening.py::"
    "test_normative_evidence_openapi_example_preserves_actual_fixture_response"
)
nodes = [positive]
if mode == "remove_registration":
    del owner._SUCCESS_EXAMPLE_SETS_BY_OPERATION["submit_run_normative_evidence"]
elif mode == "green":
    nodes.append(
        "tests/unit/runtime/http/test_runtime_api_contract_hardening.py::"
        "test_normative_evidence_openapi_registration_removal_restores_exact_refusal"
    )
else:
    raise ValueError(mode)
print(json.dumps({
    "mode": mode,
    "denominator": "Every get/post operation in the complete tracked runtime OpenAPI JSON",
    "owner_operation_identities": sorted(owner_identities),
    "independent_operation_identities": sorted(independent_identities),
    "identity_sets_equal": owner_identities == independent_identities,
    "captured_body_sha256": hashlib.sha256(captured_bytes).hexdigest(),
    "entire_captured_payload_preserved": captured == owner._NORMATIVE_EVIDENCE_FIXTURE_RESPONSE,
    "payload_and_fixture_description_remain": callable(
        owner._normative_evidence_transport_examples
    ),
    "pytest_nodes": nodes,
}, indent=2), flush=True)
raise SystemExit(pytest.main([*nodes, "-q"]))
