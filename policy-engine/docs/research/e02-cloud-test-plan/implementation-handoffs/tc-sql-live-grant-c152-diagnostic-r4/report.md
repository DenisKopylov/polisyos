# C152 R4 one-node served-job diagnostic report

## Verdict

- **Environment/setup:** `ENVIRONMENT_ERROR`. Initial source admission passed for commit `0e852befd1fdde966c661dc1895d6f704dc5c184`, tree `b4456a308f2b4c2c7edb1cbe105715ea19e08d9a`, and all 56 materialized pins.
- **Exact served selector:** `UNRUN`. No pytest collection, dispatch, terminal job, stage event, JUnit, selected-process origin census, or diagnostic JSON exists.
- **Product cause:** `not_established`. No statement about C148's cause or reproduction is warranted.
- **G acceptance/closure:** `false`.

## Environment outcome

The pre-bootstrap resource measurement reported `safe_to_start=true`. The checkout had an existing CPython 3.14 project environment, but the required frozen lock sync is the admission predicate. Installed `uv 0.7.22` was noncanonical. Its one frozen/offline sync failed because `psutil==7.2.1` was absent from the configured cache; that sync recreated `.venv`, so prior package observations no longer admitted the environment. The pinned `uv==0.9.21` offline `uvx` probe established that the pinned tool was not cached. The one bounded online pinned-manager attempt failed at the package tunnel while fetching the uv index. Therefore the required post-sync interpreter/profile, backend probe, resource recheck, and exact pytest run were not permitted.

A repeated post-sync admission command encountered its already-created scratch `initial-pycache`; this is a harness receipt after environment failure and is not a product failure. No retry with fresh scratch was needed or permitted because dependency admission had already failed.

## Exact intended selector

`tests/integration/runtime/http/test_registered_sql_live_grant.py::test_real_sql_workflows_recheck_current_use_on_every_debug_get`

The intended runner timeout was 1200 seconds. The runner was never invoked.

## Evidence and limits

The command directory retains complete stdout, stderr, and exit receipts for source/pin admission, environment observations, resource measurement, installed-manager parser/version, offline sync, pinned-tool cache probe, and the single online attempt. Static source and pins qualify only the admitted checkout. Because the selected pytest PID does not exist, dynamic process source qualification is unavailable. C148 remains `not_established`; publication, transport, setup, source qualification, test verdict, and future G acceptance remain separate predicates.

Pattern pass: P29 is not claimed because the runtime path was unrun; P37/P38 keep package observations and parser acceptance from substituting for a successful frozen sync; P41 classifies the current outcome as environment admission failure rather than product red.
