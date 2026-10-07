"""Bounded actual canonical-decoder/objective underflow intake diagnostic."""

from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

from polisyos.core.canon.canon_json import (
    CanonSpec,
    from_canonical_bytes,
    to_canonical_bytes,
)
from polisyos.scientist.methods.search.objective import BudgetDeficitObjective

ROOT = Path("/dev/shm/e02-D-oct07-continuation")
PRODUCT = ROOT / "policy-engine"
OUTPUT = Path(__file__).with_name("actual969_decoder_probe.json")
INPUT_PATHS = [
    "src/polisyos/scientist/methods/search/objective.py",
    "src/polisyos/core/canon/canon_json.py",
    "src/polisyos/common/canonical.py",
]


def hashes():
    result = {}
    for path in INPUT_PATHS:
        data = (PRODUCT / path).read_bytes()
        expected = subprocess.check_output(
            [
                "git",
                "-C",
                str(ROOT),
                "show",
                "96905636726483fdea3a98d9313871d825b54a9e:policy-engine/" + path,
            ]
        )
        assert data == expected, "source dependency differs from exact969"
        result[path] = hashlib.sha256(data).hexdigest()
    return result


before = hashes()
cases = [
    ("positive_tiny_balance", {"gov_balance": Decimal("1e-1000")}, "unavailable", None),
    (
        "negative_tiny_balance",
        {"gov_balance": Decimal("-1e-1000")},
        "unavailable",
        None,
    ),
    (
        "positive_tiny_deficit",
        {"budget_deficit": Decimal("1e-1000")},
        "unavailable",
        None,
    ),
    (
        "negative_tiny_deficit",
        {"budget_deficit": Decimal("-1e-1000")},
        "unavailable",
        None,
    ),
    (
        "tiny_balance_alias_conflict",
        {
            "gov_balance": Decimal("1e-1000"),
            "government_balance": Decimal(0),
            "budget_deficit": 12,
        },
        "unavailable",
        None,
    ),
    ("legacy_numeric_string_tiny", {"budget_deficit": "-1e-1000"}, "unavailable", None),
    ("genuine_decimal_zero", {"budget_deficit": Decimal("0E-1000")}, "available", 0.0),
    (
        "genuine_integer_zero",
        {"gov_balance": 0, "budget_deficit": 12},
        "available",
        0.0,
    ),
    ("ordinary_decimal_balance", {"gov_balance": Decimal(-5)}, "available", 5.0),
    (
        "representable_small_deficit",
        {"budget_deficit": Decimal("1e-300")},
        "available",
        1e-300,
    ),
    (
        "malformed_present_no_fallback",
        {"gov_balance": "bad", "budget_deficit": 0},
        "unavailable",
        None,
    ),
    ("boolean_false_not_zero", {"gov_balance": False}, "unavailable", None),
    (
        "null_balance_legacy_fallback",
        {"gov_balance": None, "budget_deficit": 12},
        "available",
        12.0,
    ),
]
rows = []
for name, source, expected, expected_value in cases:
    raw = to_canonical_bytes(source, CanonSpec(forbid_floats=False))
    decoded = from_canonical_bytes(raw)
    outcome = BudgetDeficitObjective(threshold=0).evaluate(decoded)
    observed = "available" if math.isfinite(outcome.raw_value) else "unavailable"
    rows.append(
        {
            "case": name,
            "raw_canonical_bytes_utf8": raw.decode(),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "actual_decoded_values": {
                key: {"type": type(value).__name__, "repr": str(value)}
                for key, value in decoded.items()
            },
            "expected_state": expected,
            "expected_value": expected_value,
            "actual_state": observed,
            "actual_value": outcome.raw_value
            if math.isfinite(outcome.raw_value)
            else {"nonfinite": str(outcome.raw_value)},
            "actual_satisfied": outcome.is_satisfied,
            "check": "PASS"
            if expected == observed
            and (expected_value is None or outcome.raw_value == expected_value)
            else "FAIL",
        }
    )
after = hashes()
record = {
    "schema": "e02.D.objective_alias_decimal_actual_diagnostic.v1",
    "source_sha": "96905636726483fdea3a98d9313871d825b54a9e",
    "source_tree": "8a48f3c03ce75c263f466cd4c2dfa0f87bc99e60",
    "runtime": {"executable": sys.executable, "python": sys.version},
    "inputs_before": before,
    "inputs_after": after,
    "source_unchanged": before == after,
    "cases": rows,
    "check_counts": {
        label: sum(row["check"] == label for row in rows) for label in ("PASS", "FAIL")
    },
    "limits": [
        "Actual canonical typed-tag decode and existing BudgetDeficitObjective; no synthetic numeric conversion helper or mocked result.",
        "Float64 intake representability only; no actual fiscal issuer/unit/sign/alias law appointed by this controlled diagnostic.",
        "Raw predecode original nonzero retained exactly; ordinary/genuinezero controls distinguish conversion loss.",
    ],
}
OUTPUT.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
print(
    json.dumps(
        {
            "output": str(OUTPUT),
            "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            "checks": record["check_counts"],
            "source_unchanged": record["source_unchanged"],
        }
    )
)  # noqa: T201
