# DX0 Fabric and Foundry behavioral mirrors

Status: three test-only additions are ready for the parent’s combined test run. The three production modules were read and remain unchanged. No pytest command was run in this slice, as requested.

The source/test byte hashes and complete Ruff/compile command records are in [`raw/dx0-native/fabric-foundry-mirrors/`](../raw/dx0-native/fabric-foundry-mirrors/). That directory is under the repository’s ignored research `raw/` path.

| Owner path | Behavioral property exercised |
|---|---|
| `tests/unit/fabric/connectors/contracts/test_validation_middleware.py` | Warms strict and warn proxies against a permissive contract, advances the real registry revision with a stricter version, and fetches again. The strict error is bound to the new expected/actual schema version and records both new quality-policy violations; warn returns with both counters incremented; disabled returns with no validation counters. |
| `tests/unit/foundry/feedback/test_jacobian.py` | Compares the finite-difference Jacobian of a known affine map with its independent matrix, using a nonzero offset and both computed and supplied baselines. Exercises the inclusive fold singular-value boundary and an outside point, plus the flip eigenvalue boundary and an outside point. |
| `tests/unit/foundry/feedback/test_basin.py` | Calls the real basin estimator with one failed start, one converged-but-unassigned start, and two assigned starts. Confirms all four remain in the denominator (share `2/4`, not `2/2`). Confirms an empty start set makes no solver calls and `wilson_interval(0, 0)` is `[0, 1]`; the estimator’s separate zero-draw `ci_95=None` remains explicit. |

The routed owner properties are the ones listed in Section 4 of `ratchet-repair-routing-current.md`. Existing tests cover broader contract validation and a multi-start fixed-point example; these new tests cover the specific missing behaviors, using actual `fetch`, `finite_difference_jacobian`/`summarize_jacobian`, and `estimate_basin_shares`/`wilson_interval` paths rather than import or constructor checks.

Pattern pass: P29/P38 are addressed by behavior-level calls and assertions whose outcomes change with the property. No production defect or missing source behavior was established in this read, so no source lease was requested. P40 does not currently show a repeated same-class escape in these three owners; this is not a closure claim beyond the routed properties.

Validation receipts:

- `.venv/bin/python -m ruff check` on the three new test paths: exit 0.
- `.venv/bin/python -m ruff format --check` on the three new test paths: exit 0.
- `.venv/bin/python -m compileall -q` on the three new test paths: exit 0.
- Pytest: `UNRUN` in this slice; the parent owns the combined run.

Full stdout/stderr, argv, working directory, and exit status for each allowed check are preserved under `raw/dx0-native/fabric-foundry-mirrors/`. The hash manifest binds each new test to its corresponding read-only source module.
