# Final Linux and browser wave readiness

Captured 2026-10-10. This is a read-only readiness receipt for the existing isolated worker and the already-installed host browser toolchain. No source was copied or mounted, no server/browser/test was started, and no Git operation or cleanup was performed. The final source freeze is not yet identified here: root reported candidate prefix `4699fdf` with WIP, so this note does not assert a frozen SHA/tree or bind a run to that candidate.

## Runner snapshot

The explicit profile remains healthy: Colima `e02-local`, aarch64, 2 CPUs, configured 3 GiB RAM and 8 GiB Docker data disk; Docker context `colima-e02-local`; Ubuntu 24.04.4 / Linux aarch64; Docker server 29.5.2, cgroup v2. Use only `COLIMA_HOME=/Users/deniskopylov/.colima-e02-local`, `DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local`, and `docker --context colima-e02-local`. The pre-existing default Docker context is not the target. The legacy `/usr/local/bin/docker` link remains untouched.

The only running container is `e02-local-worker-provision` (`88c8824b3970ef929473daf73cda2e50083b2035f5b725071acf8a829fa5b0c6`), pinned to `ghcr.io/astral-sh/uv@sha256:dc53af52cf658aa04401244105cd63b25a7dfd42a6c5125683710b553d8d263f`. Its only mounts are the existing named uv cache, managed Python, and `/scratch` environment volumes; there is no host source or production mount. Do not clean Docker state: the dedicated daemon currently also lists pre-existing Prometheus containers and volumes, which were left alone.

At the captured check, the worker cgroup used 1,651,593,216 of 2,306,867,200 bytes, with all `memory.events` counters (`high`, `max`, `oom`, `oom_kill`) at zero. Guest `MemAvailable` was 2,562,400 kB, with no swap. The 7.8 GiB Docker data filesystem had 3.0 GiB available (61% used); the host root filesystem had 19 GiB available. Keep those separate budgets. Docker reports the worker container at 374.7 MiB, reflecting a different accounting view than cgroup file cache. This is enough for the prepared profiles, but the numerical/browser heavy slot remains root-controlled and must be rechecked immediately before use. No cleanup is indicated.

The existing root environment is `/scratch/root-venv/bin/python` (Python 3.14.0, Hatchling 1.27.0, pytest 9.0.2). The existing worker environment is `/scratch/dowhy-venv/bin/python` (Python 3.12.12, DoWhy 0.14, pytest 9.0.2). `uv` is 0.9.21. Read-only `uv pip check` passed: 161 root distributions and 52 worker distributions are compatible. Do not create another environment or change either lock/profile. The root and worker recipe identities observed in this checkout are:

```text
policy-engine/pyproject.toml:                  b205b652e2a16d342394988aa4a4dab0e2eb54acb0788ea8cc90c7b8cc10a267
policy-engine/uv.lock:                         e6125cd8f7fc22dfdd7460e7461937b96ee0644b0b451e5a30c2e0f56367f463
policy-engine/workers/dowhy-014/pyproject.toml: df7ceb44d49f3e1befdf470a26cdff8146c91343dac13fb2f41f9fff97f94447
policy-engine/workers/dowhy-014/uv.lock:        c33e8f99180bb587b49c9473d40258502532bfbd0d6e792d6d31e5d545f71f3a
```

These hashes are pre-freeze observations and must be checked against the eventual frozen checkout. The existing Linux recipe is already fully documented in [`README.md`](README.md): B212 and F use the two real DoWhy-to-CAS consumers in `tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py`, with the 3.12.12 worker selected explicitly and a fresh 3.14 reader; LA-029 uses the real `tools/ops_runners/ukraine_data/validate_part_a.py` entrypoint with its server-only guard enabled and a synthetic C7 integration; DFK uses a Linux-native `bad_\xff.json` Git filename in an isolated temporary repository. Keep those commands' Linux guards and child-stream capture intact. They consume synthetic/minimal fixtures only and no production data. The prior note's captured command blocks are plans, not test receipts.

## One frozen source checkout

Wait for root to supply the exact final attached source checkout, branch, full commit SHA, and full tree SHA. Do not use the currently reported WIP candidate. Then make one shallow bare transport from that ordinary checkout and one reusable attached checkout in the existing container. No bind mount and no interpreter-specific source copies:

```sh
set -euo pipefail
source_checkout=/absolute/path/root-supplies-at-freeze
freeze_branch=ROOT_SUPPLIED_ATTACHED_BRANCH
freeze_sha=ROOT_SUPPLIED_FULL_COMMIT_SHA
freeze_tree=ROOT_SUPPLIED_FULL_TREE_SHA
host_bare="${TMPDIR%/}/e02-${freeze_sha}.git"

git -C "$source_checkout" status --short --branch
git -C "$source_checkout" symbolic-ref --short HEAD
git -C "$source_checkout" rev-parse HEAD
git -C "$source_checkout" rev-parse 'HEAD^{tree}'
git clone --bare --depth=1 --single-branch --branch "$freeze_branch" \
  "file://$source_checkout" "$host_bare"
git --git-dir="$host_bare" rev-parse HEAD
git --git-dir="$host_bare" rev-parse 'HEAD^{tree}'
git --git-dir="$host_bare" rev-parse --is-shallow-repository
```

Proceed only when the checkout is attached/clean and all commit/tree outputs match root's full identities; the bare clone must report shallow. Copy that object store to the existing `/scratch` volume, then create the single attached source checkout:

```sh
docker_e02() {
  COLIMA_HOME=/Users/deniskopylov/.colima-e02-local \
  DOCKER_CONFIG=/Users/deniskopylov/.docker-e02-local \
  /opt/homebrew/bin/docker --context colima-e02-local "$@"
}
docker_e02 cp "$host_bare" \
  "e02-local-worker-provision:/scratch/e02-${freeze_sha}.git"
docker_e02 exec e02-local-worker-provision mkdir -p /workspace
docker_e02 exec e02-local-worker-provision \
  git clone --shared --single-branch --branch "$freeze_branch" \
  "/scratch/e02-${freeze_sha}.git" /workspace/polisyos
```

Before tests, read the worker checkout back: exact full `HEAD`, tree, branch, clean status, `.git/shallow`, and `.git/objects/info/alternates`. The shallow boundary must be the frozen commit and the alternates target the retained bare object store. Keep that bare store for the checkout lifetime; don't prune borrowed objects. A mismatch is a stop condition, not a reason to synthesize Git history. Both Python profiles then consume this one `/workspace/polisyos` tree, with the distinct locked interpreter paths above.

## Browser/API consumer plan

The host already has Node `v22.22.2`, Corepack `0.34.6`, workspace `pnpm@10.33.2`, `@playwright/test` `1.59.1`, and cached Chromium `chromium-1217` plus headless shell. The workspace's host `policy-engine/.venv` is Python 3.14.3 with Hatchling 1.27.0, pytest 9.0.2, Ruff 0.14.10, FastAPI 0.128.6, and httpx 0.28.1. Existing `policy-engine/node_modules` and `apps/runtime-dashboard/node_modules` are present. A read-only host `uv pip check` found one incompatibility in the pre-existing superset environment: `ruptures==1.1.10` metadata excludes Python 3.14. The app lock has it only in the optional `analytics` extra, and source contains lazy function-local imports; the source-bound fixture path was not run, so this remains an environment caveat rather than a proven runtime failure. Do not remove or replace it as part of this prep. The source-bound browser journey's fixed listeners, 8000 and 5173, were both free at this snapshot; check them again before the eventual run and stop if either belongs to another process. The Playwright config has one worker, CPU-backed controlled producers, a 180-second test timeout, and fixed API/Vite ports. Do not run alongside another heavy test or dashboard server.

After root freezes the exact source and releases the browser slot, run the existing real-consumer journey from the dashboard package. This opt-in sets the source-bound fixture for both the test and fixture API process; `UV_NO_SYNC`/`UV_FROZEN` pins the already-installed host app environment while Playwright's webServer launches the fixture API and Vite:

```sh
cd /absolute/frozen/policy-engine/apps/runtime-dashboard
POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE=1 \
UV_PROJECT_ENVIRONMENT=/absolute/frozen/policy-engine/.venv \
UV_NO_SYNC=1 UV_FROZEN=1 \
corepack pnpm exec playwright test \
  e2e/journeys/catalog-profile-source-bound.spec.ts --project=chromium
```

That existing journey performs an ordinary browser `POST /api/v1/control/runs/nl`, polls the actual control job, then does a `cache: "no-store"` fresh `GET /api/v1/runs/{id}` and `GET /api/v1/runs/{id}/agents`. Its V1 assertions bind a resolved candidate N5 projection, `candidate_observation_only`, `publication_authority=false`, and `joint_simulated`; its real controlled gateway → `TracedLLMClient` → `BudgetMiddleware` fixture emits an unknown-cost event and the GET assertion requires `cost_origin="unknown"` with no amount. The fixture metadata names its boundary as synthetic/development-only and makes no production-currentness claim.

The cost DTO is strict in `src/api/validators.ts`; the production React route is `/runs/{id}/agents`, whose real query path is `AgentsTab` → `useSuspenseRunAgents` → `AgentPipelinePanel`. The existing browser spec checks the fresh JSON cost event but does not visit that route. After the freeze, extend the consumer assertion in the same spec if source changes are in scope: await the fresh agents GET while navigating to `/runs/{v1RunId}/agents`, require `data-testid="run-tab-agents"`, and require the visible unknown-cost summary (`Unknown` in the default English test locale). Keep the JSON origin/amount assertion too; the visible label alone cannot distinguish `unknown` from another missing-value fallback. This closes the browser/API-to-rendered-consumer gap without inventing a monetary event. It remains a bounded unknown-cost case; it does not prove reported/estimated/reuse settlement classes or retry/cancel/reopen behavior.

The same journey fresh-GETs the pre-seeded V6 run, checks typed `recursive_cycle_checkpoint.v2` partial status, `publication_authority=false`, the controlled independent-sibling failure, empty acquisition history plus `acquisition_n4_source_not_established`, then checks the rendered Overview selectors `overview-candidate-simulation` and `overview-acquisition-history-limitation`. The fixture's V6 seed calls the actual existing `test_real_leaf_result_survives_later_independent_sibling_failure`, which runs controlled N4 ports, produces an earlier N5 simulation, resolves it from CAS, and rejects a corrupted CAS ref. The seeded HTTP run is explicitly a fixture wrapper: metadata says `source_bound_v6_control_job_status=not_established_fixture_run_wrapper` and `source_bound_acquisition_history_status=not_established`; the browser spec does not assert the successful CAS ref from metadata. Therefore this is a genuine partial/CAS producer plus GET/UI witness, not an actual V6 control-job POST or an N4 acquisition-history proof. Preserve that typed limitation; don't promote it to a source-bound N4 capability claim.

The Playwright config starts `serve_fixture_runtime_api.py --port 8000 --metadata-file _build/apps/runtime-dashboard/.tmp/fixture-runtime.json` and `corepack pnpm exec vite --host 127.0.0.1` on port 5173. Both servers run on the host; the Linux container remains for Linux-profile witnesses only. At execution time, preflight both ports with separate `lsof -nP -iTCP:8000 -sTCP:LISTEN` and `lsof -nP -iTCP:5173 -sTCP:LISTEN` commands; do not set `reuseExistingServer` to adopt an unrelated listener. Use the existing Chromium cache and `corepack pnpm` (never bare `pnpm`). No browser installation is currently needed based on the cache-path check.

## Receipt and disposition

Complete command/stdout/stderr/exit captures for the lightweight profile, cgroup, storage, package, host, port, and input-hash checks are under [`raw/final-wave-readiness/`](raw/final-wave-readiness/); `SHA256SUMS` covers the bounded receipt files. Tracked input-file hashes observed during the read are in `input-hashes.tsv`; root and worker lock hashes above are included there. `free(1)` is not installed in the Debian-slim worker image, so guest memory was measured from `/proc/meminfo` and the container's cgroup files instead.

Disposition: existing Linux environments pass package consistency; source transport and frozen identity are pending root's actual freeze; heavy numerical/B212/F, LA-029, DFK and browser runs remain unexecuted pending root's one-slot release. No production payload, credentials, source mount, or currentness assertion is part of this profile.
