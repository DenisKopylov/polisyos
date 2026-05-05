# Test Taxonomy and Execution Policy

Phase 4 ownership document for `policy-engine/tests` and `frontend/runtime-dashboard`.

Актуально на **3 апреля 2026**.

## 1. Taxonomy

### Python taxonomy

| Class | Meaning | Canonical surface | Default selection |
|---|---|---|---|
| `unit` | isolated logic, no multi-service seam | everything not classified below | `pytest -m unit` |
| `contract` | compatibility, schema, ABI and boundary stability | `tests/contract/**` | `pytest -m contract` |
| `property` | Hypothesis/property-based invariants | explicit `@pytest.mark.property` or `test_*property*.py` / `test_*properties.py` | `pytest -m property` |
| `integration` | cross-subsystem, runtime-boundary or reference-source tests | `tests/integration/**`, `tests/unit/runtime/http/**`, `tests/unit/fabric/connectors/reference/**` | `pytest -m integration` |
| `performance` | benchmark and cost-regression tests | `tests/performance/**`, tests with `@pytest.mark.benchmark` | `pytest -m performance` |

### Frontend taxonomy

| Class | Meaning | Canonical surface | Default selection |
|---|---|---|---|
| `frontend component` | component, hook, route, and Storybook interaction tests | `src/**/*.test.ts(x)`, `src/**/*.a11y.test.ts(x)`, `npm run test:components` | `npm run test:components` |
| `frontend journey` | end-to-end operator flows across runtime API + dashboard | `e2e/journeys/*.spec.ts`, `npm run test:journeys` | `npm run test:journeys` |
| `visual` | screenshot/snapshot-regression coverage | `e2e/*.visual.spec.ts`, `npm run test:visual` | `npm run test:visual` |

## 2. Marker and Tag Policy

### Pytest markers

Registered markers live in [`pyproject.toml`](/Users/deniskopylov/polisyos/policy-engine/pyproject.toml).

- Primary class markers are auto-applied during collection: `unit`, `contract`, `property`, `integration`, `performance`.
- `benchmark` remains available as the plugin-specific marker used by `pytest-benchmark`; it also implies `performance`.
- `--strict-markers` is enabled. New markers must be registered before use.
- Quarantined pytest tests are declared in [`tests/quarantine.toml`](/Users/deniskopylov/polisyos/policy-engine/tests/quarantine.toml) and are skipped by default. Use `pytest --run-quarantine ...` to include them.

### Frontend tags

- Playwright journeys and visual tests use title tags, not pytest markers.
- CI validates Playwright `@flaky` and `@quarantine` tags against `tests/quarantine.toml`.
- Required semantics:
  - `@smoke`: smallest representative confidence slice, expected to finish in minutes.
  - `@slow`: intentionally expensive flow, excluded from the fastest default loops.
  - `@flaky`: test currently needs additional operator scrutiny; must also have an owner and expiry in `tests/quarantine.toml`.
  - `@quarantine`: temporarily de-gated flow; excluded by default through Playwright config.
- Playwright registry selectors use the full tagged test title so a quarantined journey remains directly re-runnable with `playwright test --grep "<full title>"`.
- Stable defaults:
  - `npm run test:journeys`
  - `npm run test:journeys:smoke`
  - `npm run test:visual`
- Explicit quarantine access:
  - `npm run test:journeys:quarantine`
  - `npm run test:visual:quarantine`

## 3. Smoke, Slow, Flaky, Quarantine Semantics

- `smoke` means “minimal but representative confidence,” not “tiny unit test.” A smoke path should prove that the critical workflow is alive end-to-end.
- `slow` means the test is intentionally outside the tight local loop. Do not apply it only because a test is occasionally noisy.
- `flaky` means the signal is not currently trustworthy. Every flaky test must have:
  - an owner;
  - an expiry date;
  - a short reason;
  - explicit re-entry criteria.
- `quarantine` means the test does not gate the main CI path until the re-entry criteria are met. Quarantine is temporary by policy.

## 4. Retry Policy

- Pytest: no blanket retries in CI. A failing Python test should fail the lane.
- Vitest: no blanket retries in CI. `--retry` is for local diagnosis only.
- Playwright: default retries are `0`. If a journey needs temporary retries for diagnosis or a non-blocking lane, pass `PLAYWRIGHT_RETRIES=<n>` explicitly and keep the test tagged `@flaky` plus listed in `tests/quarantine.toml`.
- “Retry to hide signal” is prohibited. Retries are allowed only to collect better artifacts around a known instability.

## 5. Local and CI Loops

### Fast local Python loop

```bash
cd policy-engine
pytest -m "not integration and not performance and not quarantine" --ignore=tests/unit/runtime/http
```

### Dedicated Python surfaces

```bash
cd policy-engine
pytest -m contract
pytest -m property
pytest -m integration --ignore=tests/unit/runtime/http
pytest -m performance
pytest tests/unit/runtime/http -m "not quarantine"
```

### Frontend surfaces

```bash
cd policy-engine/frontend/runtime-dashboard
npm run test:components
npm run test:journeys:smoke
npm run test:visual
```

### Local integration smoke stack

Use [`tools/quality/testing/local_integration_stack.py`](/Users/deniskopylov/polisyos/policy-engine/tools/quality/testing/local_integration_stack.py):

```bash
cd policy-engine
uv run python tools/quality/testing/local_integration_stack.py up
uv run python tools/quality/testing/local_integration_stack.py smoke
```

The smoke profile validates:

- backend health on `127.0.0.1:8000`;
- dashboard dev server on `127.0.0.1:5173`;
- control-plane to runtime interaction via `http://127.0.0.1:5173/api/v1/health`.

## 6. CI Sharding Strategy

When the suite outgrows a single lane, shard by test class first and by runner-native shard support second.

### Recommended order

1. Keep `contract`, `integration`, `performance`, `frontend journey`, and `visual` in separate lanes.
2. Split the large Python `unit + property` surface by historical duration, not by alphabetical file order.
3. Use `vitest --shard=<index>/<count>` for large frontend-component lanes.
4. Use `playwright test --shard=<index>/<count>` for large journey suites.
5. Keep visual tests in a dedicated lane unless screenshot volume becomes the bottleneck.
6. Never mix quarantined tests back into the main shards; run them in an explicit opt-in lane if needed.

### Practical shard boundaries

- Python shard A: `tests/unit/core`, `tests/unit/ir`, `tests/contract`
- Python shard B: `tests/unit/fabric`, `tests/unit/runtime` except `tests/unit/runtime/http`
- Python shard C: `tests/unit/foundry`, `tests/unit/scientist`
- Python shard D: `tests/unit/data_forge`, `tests/unit/lex`, `tests/e2e/demos`
- Frontend component shards: `vitest --shard=1/2`, `vitest --shard=2/2`
- Frontend journey shards: `playwright test --shard=1/2`, `playwright test --shard=2/2`

Historical duration data should come from the economics report tool instead of intuition.

## 7. Enforcement and Reporting

- Active PR CI emits JUnit XML for the Python `runtime-http`, `integration`, and `performance` lanes.
- [`tools/quality/testing/report_test_economics.py`](/Users/deniskopylov/polisyos/policy-engine/tools/quality/testing/report_test_economics.py) renders the top slowest suites/tests plus active quarantine inventory into the GitHub Actions step summary.
- [`tools/quality/testing/check_playwright_quarantines.py`](/Users/deniskopylov/polisyos/policy-engine/tools/quality/testing/check_playwright_quarantines.py) fails CI if a Playwright `@flaky` or `@quarantine` title has no matching registry entry, if selectors are duplicated, or if a registry entry points at a non-tagged test.
