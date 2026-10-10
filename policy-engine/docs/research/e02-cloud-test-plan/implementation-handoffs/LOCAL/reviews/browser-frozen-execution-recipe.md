# Frozen browser execution recipe

## Reconciled environment

Use the dedicated clean browser-core environment at
`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/browser-core-venv`, not the broad `policy-engine/.venv` and not the Linux worker/container. Its installation receipt records CPython 3.14.0, 148 installed packages, `fastapi==0.128.6`, `uvicorn==0.40.0`, and `pytest==9.0.2`; `uv pip check` exited 0. The locked selection is root base + `runtime-http` + `test` + `dev`; it excludes the `analytics` extra and `ruptures`. The profile was prepared from `pyproject.toml@b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267` and `uv.lock@e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463`. Recheck these inputs against the frozen checkout before using this environment; do not sync or modify the profile during the browser run.

The original [`browser-consumer-companion-readiness.md`](browser-consumer-companion-readiness.md) uses the broad host `.venv` in its future command. This recipe supersedes that environment choice: use the dedicated 148-package browser-core environment above. Root's separate 248-package profile is not needed for this API fixture. The install recipe and complete package-integrity evidence are in [`browser-core-host-env.md`](../linux-profile/browser-core-host-env.md) and [`raw/browser-core-install-receipt/SHA256SUMS`](../linux-profile/raw/browser-core-install-receipt/SHA256SUMS).

The Playwright webServer API command runs from the frozen checkout's `policy-engine` root and invokes `uv run --extra runtime-http --extra test`. Set `UV_PROJECT_ENVIRONMENT` to the browser-core venv and `UV_NO_SYNC=1 UV_FROZEN=1`, so the child uses the already installed compatible profile without reconciling packages. Set `POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE=1` in the parent command; Playwright passes the inherited environment to the fixture API child, and the journey itself uses the same opt-in. Do not set `PYTHONPATH`: `serve_fixture_runtime_api.py` resolves its own frozen source location and inserts that checkout's `src`, product root, `tests`, and fixture-support roots. A stale path to a prior candidate would undermine the source binding.

The supported journey has substantive but bounded synthetic work. API fixture startup seeds V6 by executing the existing recursive-controller test with controlled `N4GenerationPort` instances and persists the partial result to CAS. The V1 POST then exercises the configured candidate route against a controlled local gateway and synthetic profile. It sets `JAX_PLATFORMS=cpu` and `OMP_NUM_THREADS=1`; there is no GP/TMLE/native-fit suite or `analytics` extra in the browser command. The journey is still CPU-backed candidate simulation and CAS work, so keep it serialized with the root-owned browser slot and do not describe it as a trivial HTTP smoke test.

## Preflight and exact command

The frozen source must be the root-supplied attached checkout and full commit/tree identity. Root reports current candidate prefix `82b0954f9`; this note does not promote that abbreviated identity to a final freeze receipt. Leave the existing 19-command base plan and 11-command supplement inputs/manifest untouched. The prior independent review records their plan hashes as `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a` and `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2`; root owns the final post-freeze source manifest.

Before starting Playwright, run these separately from the host and inspect ownership:

```sh
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Both must show no listener. Stop if either port is occupied. The journey config uses fixed API/Vite ports 8000 and 5173. Set `CI=1` so its existing `reuseExistingServer: !process.env.CI` setting becomes `false`; Playwright then starts its own servers and refuses to adopt an unrelated listener. This does not change production code or the test selection.

After root releases the browser slot, fill in the frozen checkout and full commit SHA and run from its dashboard package:

```sh
set -euo pipefail
frozen_policy_engine=/absolute/root-supplied/frozen-checkout/policy-engine
freeze_sha=ROOT_SUPPLIED_FULL_COMMIT_SHA
browser_venv=/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/browser-core-venv
evidence_root="$frozen_policy_engine/_build/apps/runtime-dashboard/browser-source-bound-$freeze_sha"
mkdir -p "$evidence_root"
cd "$frozen_policy_engine/apps/runtime-dashboard"

CI=1 \
PATH="/opt/homebrew/bin:$PATH" \
POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE=1 \
UV_PROJECT_ENVIRONMENT="$browser_venv" \
UV_NO_SYNC=1 UV_FROZEN=1 \
PLAYWRIGHT_JSON_OUTPUT_FILE="$evidence_root/playwright.json" \
corepack pnpm exec playwright test \
  e2e/journeys/catalog-profile-source-bound.spec.ts \
  --project=chromium \
  --reporter=json \
  --trace=on \
  --output="$evidence_root/test-results"
```

`--reporter=json` and `PLAYWRIGHT_JSON_OUTPUT_FILE` are supported by the installed Playwright and used by existing repository evidence code. The unique report path, unique `--output` directory, and Playwright's configured Vite/API metadata path are under ignored `_build/` (`policy-engine/.gitignore` ignores `_build/`). The isolated test output directory avoids clearing prior shared `test-results`. `CI=1` changes the default reporter, so keep the explicit JSON reporter in the command. Preserve the command's full stdout/stderr, exit status, and measured wall duration beside the JSON report under `evidence_root`.

The config sets test timeout to 180 seconds, server startup timeout to 120 seconds, one worker, and routes the API fixture through port 8000 and Vite through 5173. The exact fixture metadata path remains `_build/apps/runtime-dashboard/.tmp/fixture-runtime.json`. The source-bound setting builds the controlled fixture; no extra run-paper flag is needed for that branch. Browser-core `uv` is `/opt/homebrew/bin/uv` (measured 0.10.6); `PATH` is prefixed so the Playwright webServer's `uv` resolves consistently while preserving Node/Corepack from the existing shell.

## Evidence and limits

Current source inputs reviewed read-only:

- `catalog-profile-source-bound.spec.ts@bca8cf651a363615085a53cdfe1615f4288a377773048e8a84aa8980e3a7f4ea`
- `playwright.config.ts@04e27f939d43268b2c678bc205c941c0cf1ef719e430bdb65ecf6d197d844927`
- `serve_fixture_runtime_api.py@87b39c9f8c0be64f38bf49334e7bae6bc8c26459691a1a3cc47133e822d5e00f`
- `fixture_support/catalog_profile_source_fixture.py@c40d9a0344e6ccf343f433c44c60af9ee2ac355dcaa553d6487e1d444cdd9985`

The current test source hash is not the frozen source identity; root must bind the executed source/test/config/input manifest to the actual freeze. No Playwright journey, server, browser, port check, or model fit was run for this reconciliation. The browser-core environment receipt is an install/profile receipt, not a test result.

On failure, the existing Playwright config writes screenshot, video, and trace artifacts under its configured test output directory; the command's `--trace=on` also retains a trace on a passing run, where the page snapshots and console can be reviewed. The configured screenshot mode is `only-on-failure`, so a successful run does not produce a standalone PNG with this frozen test source. Do not claim a passing screenshot exists: if a standalone success PNG is required, root must authorize and freeze a test-side screenshot companion or another controlled capture step before execution.

At readback, verify the fresh agents GET belongs to the `core_run_id` returned by the actual V1 POST; the `/runs/{id}/agents` URL and visible `run-tab-agents` / `Cost: Unknown` assertion are in the same test. Record URL, rendered text, API response status, page/console state from the retained trace, and the artifact path. This remains a source-bound synthetic candidate witness: unknown cost is disclosed as unknown, with no external fiscal fact or production-currentness authority.
