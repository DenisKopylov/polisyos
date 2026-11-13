# Core Runtime Integration Tests

These scenarios exercise acquisition and candidate simulation through the actual
Runtime lifecycle, persisted Core artifacts, control-store events and API readers.
Start with the test matching the changed boundary: authority admission, data
preparation, world transition, generation continuation, or terminal recovery.

Shared fixtures live in [`tests/_helpers`](../../_helpers). Preserve each
scenario's selected artifact profiles, tenant and source identities, physical
quota and declared authority ceiling. A synthetic appointment exercises the
mechanism; it does not establish a production issuer or publication permission.

Run selected tests from `policy-engine/` with the existing environment, for
example `.venv/bin/python -B -m pytest -q
tests/integration/core_runtime/test_acquisition_route_execution_binding.py`.
Numerical and crash/restart cases need isolated scratch stores and the resource
profile recorded in [the current E02 plan](../../../../E02-WORK-PLAN.md). A
retained incomplete run is diagnostic input, not a completed integration pass.
