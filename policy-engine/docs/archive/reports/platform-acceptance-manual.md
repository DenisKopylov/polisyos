# Platform Acceptance Manual Evidence

Date: 2026-04-04
Operator: Codex

## Recorded Outcomes

### Clean-machine bootstrap rehearsal

Status: passed

- Rebuilt a clean detached checkout from committed snapshot `ccde518` under
  `/root/polisyos-clean-next` on `root@204.168.164.187` using
  `polisyos-tools workspace remote-acceptance --clean-tree /root/polisyos-clean-next clean-checkout --ref HEAD`.
- Ran `polisyos-tools workspace bootstrap --profile runtime --skip-hooks` from
  `/root/polisyos-clean-next/policy-engine`.
- Bootstrap completed with Python `3.14.0`, Node `v22.22.2`, uv `0.9.21`,
  Playwright Chromium launchability, fresh `uv.lock` / `package-lock.json`,
  fresh schema/runtime OpenAPI/frontend contract artifacts, and
  `doctor passed.`

### Backend contributor walkthrough

Status: passed

- Ran `polisyos-tools workspace verify --skip-doctor --pytest-workers 16` from
  `/root/polisyos-clean-next/policy-engine` after clean bootstrap.
- Backend checks passed end-to-end:
  import gate, Foundry purity lint, state-read contracts, Scholar imports,
  connector contracts, ABI schema freshness, runtime API contract freshness,
  the parallel non-benchmark pytest slice, and the serial benchmark slice.
- Non-benchmark pytest summary: `7586 passed, 142 skipped, 751 warnings in
  603.33s`.
- Benchmark pytest summary: `6 passed, 7 skipped, 7818 deselected, 5 warnings
  in 10.53s`.
- The previously failing compositional-causality benchmark, twin-network
  counterfactual pipeline, and merge-determinism Hypothesis test now pass on
  the committed clean checkout under 16-way xdist.

### Frontend contributor walkthrough

Status: passed

- The same clean `polisyos-tools workspace verify --skip-doctor --pytest-workers 16` run
  completed `npm run typecheck`, `npm run lint`, `npm run format:check`,
  `npm run check:architecture`, `npm run contracts:verify`, and
  `npm run test`.
- Frontend component-test summary: `99 passed` test files and `258 passed`
  tests in `9.50s`.
- Existing jsdom/react warnings are still visible in a few UI tests
  (`JsonPreview` act warning, `canvas` / `getComputedStyle` not implemented),
  but they are non-fatal and the frontend fast gate exits successfully.

### Platform contributor walkthrough

Status: passed

- Confirmed the clean contributor path by running
  `polisyos-tools workspace bootstrap --profile runtime --skip-hooks` followed by
  `polisyos-tools workspace verify --skip-doctor --pytest-workers 16`.
- Exercised the observability entrypoint from
  `/root/polisyos-clean-next/policy-engine/ops` with
  `COMPOSE_PROJECT_NAME=polisyos-clean-obs docker compose -f ops/docker/observability.compose.yml up -d`.
- Verified live readiness:
  `curl -fsS http://127.0.0.1:9090/-/ready` returned
  `Prometheus Server is Ready.`, and
  `curl -fsS http://127.0.0.1:3000/api/health` returned
  `{"database":"ok","version":"10.4.3"}`.
- Confirmed the stack was running via `docker compose ... ps`, then tore it
  down with `docker compose -f ops/docker/observability.compose.yml down --remove-orphans`.

### Release rehearsal or dry run

Status: passed

- `python3 policy-engine/tools/ops/release/check_release_version.py --tag v0.1.0`
  passed from `/root/polisyos-clean-next`.
- `python3 tools/ops/release/build_release_notes.py --version 0.1.0 --fragments-dir release-fragments/releases/0.1.0 --output docs/archive/reports/platform-release-dry-run-notes.md --metadata-output docs/archive/reports/platform-release-dry-run-notes.json --require-curated-sections compatibility migration api limitations`
  passed from `/root/polisyos-clean-next/policy-engine` with `/tmp/polisyos-release-notes.md`
  and `/tmp/polisyos-release-notes.json` as the dry-run outputs.
- `uv run --extra runtime --extra ml python tools/ops/release/run_release_canary.py --summary docs/archive/reports/platform-release-canary.md --json-output docs/archive/reports/platform-release-canary.json`
  passed from `/root/polisyos-clean-next/policy-engine` with `/tmp/polisyos-release-canary.md`
  and `/tmp/polisyos-release-canary.json` as the dry-run outputs.

### Incident / runbook tabletop

Status: passed

- Reviewed the runtime alert path from
  `docs/reference/operations/observability-topology.md` into
  `docs/runbooks/runtime-api-outage.md`.
- Confirmed the runbook has explicit timeline capture, rollback / mitigation,
  escalation owners, and postmortem action-item sections.
- Validated that the observability local stack definition is syntactically sound
  with `docker compose -f ops/docker/observability.compose.yml config`.

## True Misses From This Pass

- No acceptance-blocking misses remain in the repo-side closeout pass recorded
  on `2026-04-04`.
- Non-blocking follow-up backlog still exists for diagnostic noise and
  ecosystem freshness:
  Pydantic `schema` field shadowing warnings in connector contracts, jsdom/react
  test-environment warnings in a few UI tests, Docker Compose's obsolete
  `version` warning in the observability compose file, and the already tracked
  GitHub Actions freshness backlog surfaced by the nightly audit.
