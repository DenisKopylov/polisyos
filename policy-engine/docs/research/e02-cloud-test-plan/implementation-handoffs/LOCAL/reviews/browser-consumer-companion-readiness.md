# Browser consumer companion readiness

## Scope and finding

The frontend companion is limited to
[`catalog-profile-source-bound.spec.ts`](../../../../../../apps/runtime-dashboard/e2e/journeys/catalog-profile-source-bound.spec.ts), plus this readiness record and ignored local receipts. The source-bound journey now follows the real V1 control-job response to its `core_run_id`, keeps the existing fresh `no-store` agents DTO assertions (`cost_origin="unknown"`, amount absent), then visits that same run's `/agents` route and checks the `run-tab-agents` surface and visible `Cost: Unknown` summary. It returns to the existing overview flow afterward. Existing auth, selected profile, metadata, and V6 assertions remain in place.

This is the same unknown-cost disclosure property at the rendered-consumer depth (P40: same class, one level deeper), not a new monetary class. Before this check, the journey proved the DTO but did not visit the real agents consumer; an otherwise valid unknown DTO could therefore be rendered as a dash or a number. The paired DTO and visible assertions distinguish that divergent case (P37/P38). Dropping the unknown event or supplying an amount should fail the existing DTO assertion; hiding or changing the unknown summary should fail the rendered assertion. These are source-level test controls only until the post-freeze browser run executes.

The fixture remains a controlled traced producer and candidate-only run. It establishes no external fiscal fact, production-currentness claim, or reported/estimated/reuse settlement authority. The rendered-consumer verification is still `verification_missing` pending the live browser witness.

## Source identity and static receipts

The assigned source basis was commit `6a4bdc1be190d00fd0f25d38709184ab9cb4c0df`, tree `998523d31d9844692bce4e2e668f3b94e9f01c12`. The journey source hash before this companion was `ac4b45a89801b9fea0f5a316199ef4e1154953471d147e12d776b0386719bfc6`; current source hash is `bca8cf651a363615085a53cdfe1615f4288a377773048e8a84aa8980e3a7f4ea`.

Static validation passed:

- `corepack pnpm --dir apps/runtime-dashboard run typecheck` — exit 0, 15.436838 s.
- `corepack pnpm --dir apps/runtime-dashboard exec playwright test e2e/journeys/catalog-profile-source-bound.spec.ts --project=chromium --list` — exit 0, 0.947139 s; collected one Chromium journey. `--list` did not start the API server, Vite, or a browser.

Complete command, stdout, stderr, exit, and duration receipts are under [`raw/browser-consumer-companion/`](../raw/browser-consumer-companion/). The manifest `static-output-hashes.json` hashes each receipt. The current source hash above is the only code input hash for this companion; relevant existing consumer identities are `playwright.config.ts@04e27f939d43268b2c678bc205c941c0cf1ef719e430bdb65ecf6d197d844927` and `serve_fixture_runtime_api.py@87b39c9f8c0be64f38bf49334e7bae6bc8c26459691a1a3cc47133e822d5e00f`.

The two existing Lex source-profile unit tests are useful mocked controls, not a browser witness. Their current source hashes are `useLexSearchProfile.test.tsx@9f5b158fb18673af3eec36e297c54db9de07c7ed1aa8e55be39a1e0b857fd417` and `LexKnowledgeGraphPage.test.tsx@0780244a53a874a8ef901f78cb03dd821e0c91005228fd9a970209f5d97ebf9e`. The additional focused unit command is prepared but unrun:

```sh
cd /absolute/frozen/policy-engine/apps/runtime-dashboard
corepack pnpm exec vitest run \
  src/api/hooks/useLexSearchProfile.test.tsx \
  src/features/lex/routes/LexKnowledgeGraphPage.test.tsx
```

## Post-freeze browser witness

Browser plugin not available; repository Playwright is the fallback. The live run is intentionally deferred until source freeze and the root-owned browser slot release. At that point, first confirm ports 8000 and 5173 are free; stop if another process owns either port. Do not adopt an unrelated listener. Then run the existing source-bound journey with the pinned host environment:

```sh
cd /absolute/frozen/policy-engine/apps/runtime-dashboard
POLISYOS_DASHBOARD_SOURCE_BOUND_PROFILE_FIXTURE=1 \
UV_PROJECT_ENVIRONMENT=/absolute/frozen/policy-engine/.venv \
UV_NO_SYNC=1 UV_FROZEN=1 \
corepack pnpm exec playwright test \
  e2e/journeys/catalog-profile-source-bound.spec.ts --project=chromium
```

Retain complete stdout/stderr, exit code, duration, JUnit or equivalent test result, screenshot, and browser trace if the journey fails. Record the frozen source/tree identity, target page URL, nonblank `run-tab-agents` DOM, visible unknown-cost summary, console health, and screenshot path. Confirm the fresh agents GET is for the same `core_run_id` created by the real V1 POST; preserve the JSON origin/amount assertions as well as the rendered label. No server, port, browser, or full journey was started during this preparation.
