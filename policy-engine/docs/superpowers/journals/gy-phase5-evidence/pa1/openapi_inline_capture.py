"""Install the observed transport response without authoring or normalizing its values."""
# ruff: noqa: S101, T201 - append-only research transformation witness
from __future__ import annotations

import hashlib
import json
from pathlib import Path

root = Path.cwd()
evidence = root / "docs/superpowers/journals/gy-phase5-evidence/pa1"
raw = (evidence / "openapi-response-capture.json").read_bytes()
assert hashlib.sha256(raw).hexdigest() == (
    "becbcde583102a388069266d50e0dbee946b7c642223a958f8234652b8e4ed65"
)
captured = json.loads(raw)
rendered = json.dumps(captured, indent=4, ensure_ascii=False)
assert '\"\"\"' not in rendered
owner = root / "src/polisyos/runtime/http/openapi_contract.py"
source = owner.read_text()
assert source.count("_SUCCESS_EXAMPLE_SETS_BY_OPERATION = {") == 1
source = source.replace("import os\n", "import json\nimport os\n", 1)
addition = '''# Captured from the actual worker -> later-signed HTTP fixture, without changing
# response values. See the PA1 openapi-response-capture command and provenance.
# This documentation sample is never read by runtime evidence admission.
_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON = r"""
''' + rendered + '''
"""


def _normative_evidence_transport_examples() -> dict[str, Any]:
    """Validate the captured fixture transport without granting production authority."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        NormativeEvidenceSubmissionResponse,
    )

    NormativeEvidenceSubmissionResponse.model_validate_json(
        _NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON, strict=True
    )
    return {
        "positive_fixture_only_transport": {
            "summary": "Actual post-source fixture admission",
            "description": (
                "Documentation transport captured from the actual worker and later-signed "
                "HTTP intake using declared fixture sources, signers and trust; "
                "not production authority or a canonical denominator. "
                "Captured references and times describe that fixture run and must not "
                "be submitted as reusable authority evidence."
            ),
            "value": json.loads(_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON),
        }
    }


_SUCCESS_EXAMPLE_SETS_BY_OPERATION: dict[
    str,
    dict[str, Any] | Callable[[], dict[str, Any]],
] = {
    "submit_run_normative_evidence": _normative_evidence_transport_examples,
'''
source = source.replace("_SUCCESS_EXAMPLE_SETS_BY_OPERATION = {\n", addition, 1)
old = '''            if examples is not None:
                success_json["examples"] = deepcopy(examples)
'''
new = '''            if examples is not None:
                examples_value = examples() if callable(examples) else examples
                success_json["examples"] = deepcopy(examples_value)
'''
assert source.count(old) == 1
source = source.replace(old, new, 1)
owner.write_text(source)
print(json.dumps({
    "owner": str(owner),
    "captured_response_sha256": hashlib.sha256(raw).hexdigest(),
    "operation_id": "submit_run_normative_evidence",
    "scope": "fixture_only_transport_example",
    "capture_values_preserved": json.loads(rendered) == captured,
}, indent=2))
