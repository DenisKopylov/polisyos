"""Read-only JSON lexical-loss oracle; no PolicyOS producer is executed."""

import json
import math
from decimal import Decimal

cases = []
for lexeme in ("1e-1000", "-1e-1000", "-0.01", "0.0", "0.01"):
    decoded = json.loads(lexeme)
    exact = Decimal(lexeme)
    cases.append({
        "lexeme": lexeme,
        "decoded_float": repr(decoded),
        "float_is_zero": decoded == 0,
        "float_sign": math.copysign(1, decoded),
        "exact_is_zero": exact == 0,
        "exact_is_negative": exact < 0,
    })
assert cases[0]["float_is_zero"] and not cases[0]["exact_is_zero"]
assert cases[1]["float_is_zero"] and cases[1]["exact_is_negative"]
assert cases[3]["float_is_zero"] and cases[3]["exact_is_zero"]
print(json.dumps({"scope": "stdlib decoder only; not a B gateway run", "cases": cases}))
