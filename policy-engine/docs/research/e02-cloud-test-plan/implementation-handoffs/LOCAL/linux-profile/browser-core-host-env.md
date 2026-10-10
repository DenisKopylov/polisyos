# Clean host browser-core environment

Provisioned one isolated macOS host environment for the browser/API core profile. This is a dependency environment only: it is not attached to a frozen source tree, and no application, browser, server, or test command has been run from it.

## Exact recipe and input binding

The target is the ignored local path `raw/browser-core-venv`. It was created with Homebrew `uv 0.10.6` and CPython 3.14.0, which satisfies the root project's `>=3.14,<3.15` range. The selected locked profile is the root base plus `runtime-http`, `test`, and `dev`; it does not select the `analytics` extra or `ruptures`.

```sh
UV_CACHE_DIR=/Users/deniskopylov/.cache/uv \
UV_PROJECT_ENVIRONMENT=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/browser-core-venv \
/opt/homebrew/bin/uv sync \
  --project /Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine \
  --python 3.14.0 --locked \
  --extra runtime-http --extra test --group dev --no-install-project
```

The exact `pyproject.toml` SHA-256 was `b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267`; `uv.lock` was `e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463`. Before/after hashes match. These bind only the dependency recipe used here; the source candidate is still mutable, so the frozen source archive must be checked against these lock inputs before a later browser run.

## Result

An offline locked dry run against an absent target resolved 418 lock entries and proposed 141 downloads / 148 installs. The offline install then stopped at the uncached `jaxlib==0.8.2` macOS ARM64 wheel and created only a small partial target. The same locked recipe, same target, and same lock completed after removing only `--offline`: 141 packages prepared and 148 installed, with no source-build phase reported.

`uv pip check` passes for all 148 packages. Metadata confirms Python 3.14.0 and the selected core packages (`fastapi 0.128.6`, `httpx 0.28.1`, `pytest 9.0.2`, `jax/jaxlib 0.8.2`, `uvicorn 0.40.0`, `pyjwt 2.11.0`, `libcst 1.8.6`); `ruptures` is absent. Target disk usage is 746 MiB. The human-readable `df -h /` rounded both install snapshots to 18 GiB, which does not establish an 18 GiB reserve. Exact `df -k /` snapshots were 18,471,188 KiB (17.615498 GiB) after provisioning and 18,450,456 KiB (17.595726 GiB) in the following root snapshot; the latest read-only follow-up snapshot was 18,458,236 KiB (17.603146 GiB). All are below 18 GiB; remeasure before another host artifact wave. The pre-existing broad `policy-engine/.venv` was not modified.

The full dry-run, offline failure, network retry, integrity check, installed package list, command arguments, stdout/stderr bytes, exit codes, and their checksums are in `raw/browser-core-install-receipt/`. This is an environment-integrity receipt, not a test receipt. No source clone/copy, source mount, server, browser, application test, or numerical test occurred.
