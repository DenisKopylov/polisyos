# Exception-observer attempt assessment

This attempt is a **harness error**, not a test result. Pytest stopped before collection with `ERROR: file or directory not found: pytest` (JUnit: 0 tests). The wrapper passed `['-m', 'pytest', ...]` to `runpy.run_module("pytest", run_name="__main__", alter_sys=True)`; `runpy` replaced `argv[0]` with `pytest/__main__.py`, leaving the literal `pytest` as a positional path.

The observer recorded zero `WorkerUnavailableError` events. The exact candidate's tracked source integrity passed before and after, its candidate-only origin audit had no errors, and prior receipts remained unchanged. No inference can be made about the original exception branch or its cause. No retry was attempted, as instructed.

Complete raw stdout/stderr, JUnit, zero-event trace, scripts, and hashes are preserved in this directory; see `observer-harness-error-assessment.json`.
