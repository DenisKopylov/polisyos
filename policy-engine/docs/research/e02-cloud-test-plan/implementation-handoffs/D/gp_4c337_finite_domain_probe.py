"""Read-only native domain probe; expected coordinates follow interval symmetry."""

import json
import math

from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import ParameterBounds

SOURCE = "4c337ca58a87d6b7d4458113af4ff5c07fb3b6b5"
space = SearchSpace([ParameterBounds("x", lower=-1e308, upper=1e308)])
expected = [-1e308, 0.0, 1e308]
actual = []
print(json.dumps({"source": SOURCE, "bounds": [-1e308, 1e308], "expected_endpoints_midpoint": expected}))
for normalized in (0.0, 0.5, 1.0):
    physical = space.denormalize((normalized,))["x"]
    actual.append(physical)
    print(json.dumps({"normalized": normalized, "physical": physical if math.isfinite(physical) else str(physical)}))
normalized_zero = space.normalize({"x": 0.0})
print(json.dumps({"normalized_physical_zero": normalized_zero, "expected": [0.5]}))
try:
    candidate = RandomSearchStrategy(space, seed=31).suggest([])
    print(json.dumps({"native_random_candidate": candidate.params}))
except ValueError as exc:
    print(json.dumps({"native_random_candidate_error": type(exc).__name__, "message": str(exc)}))
assert actual == expected and tuple(normalized_zero) == (0.5,), "Finite admitted symmetric interval has incorrect/nonfinite canonical coordinates"
