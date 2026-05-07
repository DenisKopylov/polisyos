# Testing Tools

`tools/quality/testing` содержит Phase 4 tooling для локального smoke path и экономики тестов.

## Команды

Рабочая директория: `policy-engine/`.

### Local integration stack

```bash
uv run python tools/quality/testing/local_integration_stack.py up
uv run python tools/quality/testing/local_integration_stack.py smoke
```

Что делает:

- поднимает fixture-backed Runtime API на `127.0.0.1:8000`;
- поднимает dashboard dev server на `127.0.0.1:5173`;
- проверяет `/health`, корневую страницу dashboard и proxy health на `/api/v1/health`;
- в режиме `smoke` запускает `corepack pnpm run test:e2e:smoke` и затем корректно останавливает стек.

### Test economics report

```bash
uv run python tools/quality/testing/report_test_economics.py \
  --report quality=_build/.tmp/test-reports/quality-and-unit.xml \
  --report runtime-http=_build/.tmp/test-reports/runtime-http.xml \
  --report integration=_build/.tmp/test-reports/integration.xml \
  --allow-missing \
  --output _build/.tmp/test-reports/test-economics-summary.md
```

Что рендерит:

- totals по suite lanes;
- top slowest tests;
- active/expired quarantines из `tests/quarantine.toml`.

### Playwright quarantine guardrail

```bash
uv run python tools/quality/testing/check_playwright_quarantines.py
```

Что валидирует:

- каждый `@flaky` / `@quarantine` Playwright test имеет запись в `tests/quarantine.toml`;
- selector для `runner = "playwright"` совпадает с полным tagged title теста;
- в registry нет устаревших Playwright selectors, которые больше ни на что не указывают.

### Mutation testing

```bash
uv run python tools/quality/testing/mutation.py --suite foundry --target backends
uv run python tools/quality/testing/mutation.py --suite scientist --target governance
uv run python tools/quality/testing/mutation.py --suite scientist --target all
uv run python tools/quality/testing/mutation.py --suite foundry --target results
```

Что делает:

- предоставляет canonical mutation-testing surface через `polisyos-tools`;
- запускает `mutmut` по reviewed Foundry/Scientist target maps;
- считает kill rate и валидирует threshold в одном месте.

## Sharding guidance

Инструменты раннеров уже поддерживают нативное шардирование:

- `pytest`: шардировать по top-level directories и historical durations;
- `vitest`: `vitest --shard=<index>/<count>`;
- `playwright`: `playwright test --shard=<index>/<count>`.

Политика и рекомендуемые границы описаны в [`tests/TESTING_POLICY.md`](/Users/deniskopylov/polisyos/policy-engine/tests/TESTING_POLICY.md).
