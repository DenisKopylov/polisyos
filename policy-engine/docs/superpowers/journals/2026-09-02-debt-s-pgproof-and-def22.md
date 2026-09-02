# Task S — PostgreSQL reservation proof and GY-DEF22 plan journal

Date: 2026-09-02
Branch: `codex/debt-s-pgproof-and-def22`
Entry base: `071cf3c5feab54e57f21f1f931984f4319852536`

This is the append-only execution record for the two strictly serialized Task S parts. Part A was
closed and committed before any Part B research began. `docs/plans/active/` is transcription-only
and was not edited. The read-only `production_data` link was neither consulted nor changed.

## Part A — `ds9-postgres-reservation-proof`

### Verification contract

The sole product question was whether the existing named real-PostgreSQL proof observes exactly
one winner under concurrent human-decision reservation. Repository implementation was explicitly
out of scope: the 2026-08-31 audit had already established that the harness is complete and that
the historical `DS9-PG-PROOF-NONRECEIPT` results were honest fail-closed provisioning failures.

The machine identity and invocation were read from `_REPRO_COMMAND` in
`tests/unit/runtime/http/test_runtime_postgres_linearizability.py`; the selected identity was:

```text
tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner
```

Pass required all of the following from one real PostgreSQL endpoint: selection count greater than
zero, zero skips, test exit `0`, and the test's independent invariant
`sorted(result.acquired for result in results) == [False, True]`. Any zero-winner or multi-winner
result was a stop-level product finding.

### Provisioning receipt

1. Initial `/usr/local/bin/docker info` reached the client and failed to reach the daemon, confirming
   the requested stopped starting state. Docker Desktop was started with `open -a Docker`; the first
   successful daemon receipt reported zero containers.
2. Dependencies were provisioned with the invocation's own extras:

   ```bash
   uv sync --frozen --extra test --extra runtime --extra multi-tenant
   ```

   Exit: `0`.
3. A disposable `postgres:16` container ran at the non-default host endpoint
   `127.0.0.1:55439`, database/user `polisyos_proof`. The pulled image digest was
   `sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94`.
   `pg_isready` reported `accepting connections`. A direct privilege probe created and dropped
   schema `debt_s_privilege_probe`; it printed `schema_create_drop=PASS`.

### Measured proof and frozen timeout

The cold proof was run with both strict environment variables, the exact three extras from
`_REPRO_COMMAND`, and only the registered selector:

```bash
POLISYOS_DS9_REQUIRE_PG=1 \
POLISYOS_TEST_PG_DSN='postgresql://polisyos_proof:<ephemeral-password>@127.0.0.1:55439/polisyos_proof' \
/usr/bin/time -p uv run --extra test --extra runtime --extra multi-tenant pytest -q -rs \
  tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner
```

Terminal receipt: exit `0`, one passing test marker, `real 77.82`, `user 36.59`, `sys 2.72`.
The required timeout therefore freezes at:

```text
max(60s, 2 × 77.82s) = 155.64s
```

The same child invocation was then run under a `subprocess.run(..., timeout=155.64)` ceiling with
verbose collection output. Its terminal receipt was:

```text
collecting ... collected 1 item
tests/unit/runtime/http/test_runtime_postgres_linearizability.py::test_human_decision_concurrent_reservation_has_one_postgres_winner PASSED [100%]
============================== 1 passed in 0.27s ===============================
frozen_timeout_seconds=155.64 child_exit=0
```

Thus `selected = 1 > 0`, `passed = 1`, and `skipped = 0`. Passing the test establishes exactly one
winner because the executed oracle requires the two acquired flags to be `[False, True]` after
sorting and requires the loser to carry `DS9-OVERLAPPING-REISSUE`.

### Teardown and pattern pass

The named container was stopped; because it was created with `--rm`, the subsequent
`docker ps -a --format ...` result was empty. `docker desktop stop` returned
`Stopping Docker Desktop`, and the final status probe reported that Docker Desktop was not running;
the backend/UI process census was empty. No container or Docker daemon was left running.

- `P29`: closure comes from the real concurrency path on real PostgreSQL, not from an authored
  packet or marker check.
- `P34`: no skip, failure, retry, or exclusion was relabelled green.
- `P41`: no red was inherited or excluded; both proof executions terminated green on the entry
  base with no source change.

No source, test, configuration, generated artifact, active plan, or production-data path changed in
Part A.

### Architect transcription prose — `ds9-postgres-reservation-proof`

> **TASK S 2026-09-02 — `blocked` -> `closed`; provisioning-only closure.** The repository harness was already complete. A disposable real `postgres:16` endpoint with create/drop-schema privilege was provisioned at non-default port `55439`, `POLISYOS_DS9_REQUIRE_PG=1` forced fail-closed behavior, and the row's own machine-checked identity selected exactly one test with zero skips. The concurrent reservation proof passed and its executed oracle observed exactly one winner (`[False, True]`) plus the typed losing result `DS9-OVERLAPPING-REISSUE`. Cold measured wall time was `77.82s`; the timeout is frozen at `max(60s, 2 × 77.82s) = 155.64s`, under which the replay again reported `collected 1 item`, `1 passed`, `0 skipped`, exit `0`. The six historical `DS9-PG-PROOF-NONRECEIPT` errors remain correctly classified as the strict harness refusing an absent DSN, never as a product defect. The disposable container was removed and Docker Desktop returned to stopped state.
