"""Render the captured JSON values as a Python literal without changing any value."""
# ruff: noqa: S101, T201 - append-only research transformation witness
from __future__ import annotations

import ast
import json
import pprint
from pathlib import Path

root = Path.cwd()
capture = root / "docs/superpowers/journals/gy-phase5-evidence/pa1/openapi-response-capture.json"
captured = json.loads(capture.read_bytes())
owner = root / "src/polisyos/runtime/http/openapi_contract.py"
source = owner.read_text()
start = source.index('_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON = r"""')
end = source.index('\n"""', start) + len('\n"""')
literal = pprint.pformat(captured, width=88, sort_dicts=False)
assert ast.literal_eval(literal) == captured
source = (
    source[:start]
    + "_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE: dict[str, Any] = " + literal
    + source[end:]
)
source = source.replace(
    "_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON, strict=True",
    "json.dumps(_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE), strict=True",
    1,
).replace(
    '"value": json.loads(_NORMATIVE_EVIDENCE_FIXTURE_RESPONSE_JSON),',
    '"value": _NORMATIVE_EVIDENCE_FIXTURE_RESPONSE,',
    1,
)
owner.write_text(source)
print(json.dumps({"captured_values_unchanged": ast.literal_eval(literal) == captured}))
