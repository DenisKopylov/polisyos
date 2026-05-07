---
title: Tools Audit Remediation Plan
status: active
owner: team-devx
created: 2026-04-12
last_verified: 2026-05-05
stability: draft
---

# Tools Audit Remediation Plan

> Консолидированный план улучшения и исправления `policy-engine/tools` по
> итогам трех аудитов:
> `Глубокая SOTA-оценка policy-engine/tools`,
> `Код-уровневый аудит policy-engine/tools`,
> `Дополнительный аудит policy-engine/tools — новые находки`.
> Created: 2026-04-12

> Repository-topology supersession: product-root `cloud_deploy/`, `scripts/`,
> root `benchmarks/`, and duplicate top-level `tools/*` namespace workstreams
> were completed by the accepted Repository SOTA closeout. Mentions of those
> paths below are historical audit inputs, not current placement rules. Current
> placement is governed by `docs/reference/repository-topology.md` and
> `docs/plans/accepted/REPOSITORY_SOTA_PHASE_5_CLOSEOUT.md`.

---

## Цель

Довести `tools/` до состояния, в котором он является не набором разрозненных
скриптов, а безопасной, тестируемой и расширяемой инженерной платформой:

- без известных security/data-integrity дефектов;
- без silent skip, partial write и partial merge сценариев;
- с единым CLI, общими правилами запуска и machine-readable output;
- с высокой тестовой дисциплиной для всех production-gating инструментов;
- с понятной структурой владения, зависимостей и депрекейта.

## Область действия

План покрывает не только `policy-engine/tools/**`, но и все смежные зоны,
которые определяют его фактическое качество:

- `tests/repo_quality/tools/**`;
- `scripts/**`, если это тонкие обертки или data-prep утилиты вокруг `tools/`;
- `cloud_deploy/**`, если там лежат env/shard/deploy артефакты, которые должны
  быть частью `tools/ops_runners/cloud`;

- root-level `benchmarks/**`, если они описывают обязательный benchmark-story;
- `pyproject.toml`, entry points, extras, packaging и dependency metadata;
- docs и runbooks для эксплуатации, ротации секретов, rollback и recovery.

## Ключевой вывод

`tools/` уже силен по breadth: есть архитектурные гейты, ABI-контракты,
workspace bootstrap, runtime-контракты, cloud-операции, миграции, release и
domain tooling. Основной дефицит не в количестве возможностей, а в платформенной
дисциплине:

1. security и correctness-инварианты местами нарушены;
2. критические инструменты почти не покрыты тестами;
3. cloud/scripts/benchmarks фрагментированы;
4. нет единой модели запуска, вывода, кэша, preflight и telemetry;
5. legacy и broken tooling не изолированы явно.

Следствие: **Phase 0 и Phase 1 обязательны до любого расширения tooling surface
или новых SOTA-claims для `tools/`.**

---

## Принципы исполнения

1. **Security before convenience.** Секреты, инъекции, plaintext transport и
   destructive-операции закрываются раньше CLI-рефакторинга и DX-улучшений.
2. **No silent degradation.** Пропущенная проверка должна давать явный статус
   `skipped`/`degraded`, а не ложный "0 violations".
3. **Every fix gets a regression test.** Особенно для merge/idempotency,
   concurrent writes, SQL/shell hardening и parser/linter logic.
4. **Atomic by default.** Любая запись состояния, артефакта, базы или отчета -
   через temp file + `os.replace()`, transaction boundary или аналогичный
   атомарный протокол.
5. **One command surface.** Новый стандарт запуска - единый `polisyos-tools`
   entry point с общими флагами, preflight и structured output.
6. **Deprecate loudly.** Broken/legacy tooling либо чинится, либо уходит в
   `tools/archive/` с warning и ссылкой на replacement.
7. **Consolidate after containment.** Сначала убираем риски и silent failures,
   затем переносим каталоги и строим новый CLI поверх стабилизированной базы.

---

## Целевое состояние

```text
tools/
├── __init__.py
├── cli.py
├── _lib/
│   ├── runner.py
│   ├── output.py
│   ├── cache.py
│   ├── preflight.py
│   ├── timing.py
│   └── fs.py
├── architecture/
├── lint/
│   ├── __init__.py
│   ├── _common.py
│   └── rules/
├── diagnostics/
├── workspace/
├── runtime/
├── connectors/
├── migrations/
├── testing/
├── benchmarks/
│   ├── causal/
│   ├── foundry/
│   ├── ops/
│   ├── jax/
│   └── _reports/
├── release/
├── cloud/
│   ├── deploy/
│   ├── pipeline/
│   ├── shards/
│   └── preflight/
├── data/
├── validation/
├── calibration/
├── ukraine_data/
├── demos/
└── _deprecated/
```

`pyproject.toml` должен содержать единый entry point:

```toml
[project.scripts]
polisyos-tools = "tools.cli:main"
```

## Definition of Done для любого production-grade tool

Инструмент считается приведенным к целевому стандарту только если:

- имеет subcommand в unified CLI или явный documented bridge к нему;
- умеет `--help` и поддерживает общий `--output-format`;
- объявляет свои extras/dependencies и проходит preflight;
- не использует hardcoded secrets, prod paths или `shell=True` без review;
- не пишет финальные артефакты неатомарно;
- имеет тесты, пропорциональные риску;
- экспортирует timing/result metadata;
- документирован на уровне README/docstring/reference;
- имеет явный lifecycle-статус: active, experimental или deprecated.

---

## Фазовый roadmap

| Phase | Цель                                           | Горизонт         | Выходной критерий                                                                     |
| ----- | ---------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------- |
| 0     | Закрыть security и correctness blockers        | 3-5 рабочих дней | Нет открытых P0-дефектов; секреты ротированы; критичные shell/SQL/HTTP риски закрыты  |
| 1     | Восстановить надежность и целостность данных   | 1 спринт         | Merge/write/pipeline path атомарны и идемпотентны; destructive ops защищены           |
| 2     | Построить единую tooling platform              | 1-2 спринта      | Работает `polisyos-tools`; есть preflight, общие output/timing правила                |
| 3     | Поднять testability и observability            | 1 спринт         | Критичные модули покрыты тестами и structured CI output                               |
| 4     | Консолидировать каталоги и убрать фрагментацию | 1-2 спринта      | `cloud_deploy/`, `scripts/`, `benchmarks/` либо absorbed, либо явно депрекейтнуты     |
| 5     | Дожать DX, extensibility и maintainability     | после Phase 4    | Есть cache, `--changed-only`, `--fix`, rule registry и устранены hot-path bottlenecks |

---

## Phase 0 - Containment and security blockers

### WS-0B. SQL, shell and command injection hardening

**Цель:** убрать прямые инъекционные поверхности.

**Основные поверхности:**

- `tools/ops_runners/cloud/merge_shards.py`
- `tools/ops_runners/migrations/migrate_duckdb_to_pg.py`
- `tools/quality/diagnostics/scan_fabric.py`
- `tools/quality/diagnostics/verify_scm_v3.py`
- `tools/quality/diagnostics/verify_scm_v3_fullspec.py`

**Задачи:**

1. Ввести allowlist-валидацию для table/schema/alias identifiers:
   regex вида `^[a-z_][a-z0-9_]*$`.
2. Нормализовать и валидировать filesystem paths до использования в SQL/DuckDB
   attach statements.
3. Убрать `shell=True` из `subprocess.run()`; там, где это невозможно, ввести
   жесткий whitelist command specs и раздельную валидацию аргументов.
4. Добавить regression tests на malicious alias/path/command inputs.
5. Вынести общие helpers для безопасного shell/SQL запуска в `tools/lib/`.

**Критерии приемки:**

- инъекционные payloads не доходят до execution layer;
- тесты покрывают shell и SQL hardening кейсы;
- в `tools/` нет новых `shell=True` без explicit review exception.

### WS-0C. Shell safety and broken-ops containment

**Цель:** прекратить запуск скриптов, которые молча ломаются или работают в
непредсказуемом состоянии.

**Основные поверхности:**

- `tools/ops_runners/cloud/run_datasets_validation.sh`
- `tools/ops_runners/cloud/check_progress.sh`
- `tools/ops_runners/cloud/prepare_shards.sh`
- `tools/ci/install_actionlint.sh`
- `tools/ci/install_supply_chain_tools.sh`

**Задачи:**

1. Исправить неверный путь `/opt/policyos` -> `/opt/polisyos`.
2. Проставить `set -euo pipefail` и убрать brittle проверки exit code.
3. Добавить `trap` cleanup для temp files.
4. Проверить bash-specific конструкции и явно фиксировать shell (`#!/usr/bin/env bash`).
5. На время Phase 0 отключить или маркировать broken scripts как deprecated,
   если они не могут быть быстро доведены до безопасного состояния.

**Критерии приемки:**

- shell-скрипты либо безопасно падают, либо безопасно завершаются;
- не остается "тихо успешных" запусков при фактической ошибке.

### WS-0D. Destructive operations guardrails

**Цель:** запретить опасные массовые изменения без preview и rollback-path.

**Основные поверхности:**

- `tools/ops_runners/cloud/canonical_auto_approve.py`
- `tools/ops_runners/cloud/merge_shards.py`
- `tools/ops_runners/cloud/run_pipeline.sh`

**Задачи:**

1. Добавить `--dry-run`, `--yes` и preview affected rows/items.
2. Для destructive DB workflows внедрить temp output + atomic replace.
3. Для pipeline run-id перейти на collision-safe формат:
   UUID/ULID или timestamp + entropy.
4. Ввести resume/idempotency semantics вместо безусловного создания нового
   snapshot/run при каждом rerun.

**Критерии приемки:**

- опасные операции невозможно случайно запустить вслепую;
- pipeline rerun не приводит к коллизии идентификаторов или неявному дублю.

---

## Phase 1 - Reliability and data integrity baseline

### WS-1A. Atomicity, rollback and concurrency correctness

**Цель:** закрыть race condition, partial merge и corrupted-state пути.

**Основные поверхности:**

- `tools/ops_runners/cloud/merge_shards.py`
- `tools/ops_runners/ukraine_data/harvest_spending_contracts_by_disposer.py`
- `tools/ops_runners/ukraine_data/harvest_spending_daily.py`

**Задачи:**

1. Обернуть shard merge в transaction boundary или temp DB + rename protocol.
2. Гарантировать cleanup/rollback при падении на любом shard.
3. Для completion markers использовать `O_CREAT|O_EXCL`.
4. Все state-файлы писать атомарно через temp file + `os.replace()`.
5. Gzip/Zstd outputs сначала писать во временный путь, потом atomically publish.
6. Добавить concurrency tests на двойной старт, interrupted write и resume.

**Критерии приемки:**

- partial merge не оставляет поврежденный output;
- concurrent harvest не пишет двойные маркеры и не корраптит state JSON;
- crash mid-write не оставляет финальный битый gzip/json.

### WS-1B. Resource, I/O and validation hygiene

**Цель:** убрать утечки ресурсов и хрупкие точки чтения/парсинга.

**Основные поверхности:**

- `tools/ops_runners/cloud/run_lex_from_manifest.py`
- `tools/ops_runners/ukraine_data/pre_shard_lex_corpus.py`
- `tools/quality/diagnostics/check_udf_perf.py`
- `tools/quality/diagnostics/check_perf_regression.py`
- `tools/ops_runners/ukraine_data/*`
- `tools/ops_runners/calibration/compare_shards.py`

**Задачи:**

1. Перевести файловые и DB ресурсы на context managers.
2. Закрыть fd leaks при ошибках и добавить tests на exception path cleanup.
3. Проставить `encoding="utf-8"` в текстовых `open()`.
4. Ограничить размер HTTP response reads и внедрить streaming/size caps.
5. Добавить defensive parsing:
   `int()` с понятным error path, JSON schema/shape checks, empty-result guards.
6. Унифицировать JSON stdout c trailing newline.
7. Заменить `assert`-валидацию на explicit exceptions.

**Критерии приемки:**

- нет resource leaks на error paths;
- invalid input дает явную typed error вместо `KeyError`/`ValueError` без контекста;
- текстовый output и input одинаково стабильны на разных окружениях.

**Статус исполнения (2026-04-13):** выполнено для заявленных горячих
поверхностей: `check_udf_perf.py`, `check_perf_regression.py`,
`compare_shards.py`, `run_lex_from_manifest.py`,
`pre_shard_lex_corpus.py`, `check_action_freshness.py` и shared
`tools/lib/http.py`. Добавлены bounded HTTP reads, atomic writes, explicit
shape checks, `argv`-совместимый `main(...)`, resource cleanup и regression
tests.

### WS-1C. Failure semantics and explicit degraded mode

**Цель:** убрать ложные "успешные" проверки и маскировку ошибок.

**Основные поверхности:**

- `tools/quality/lint/lint_foundry_data_plane.py`
- `tools/ops_runners/migrations/migrate.py`
- `tools/ci/check_action_freshness.py`
- `tools/quality/diagnostics/gen_schema.py`
- все места с `except Exception`

**Задачи:**

1. Разобрать все 27 broad catches на категории:
   expected degradation, retryable error, fatal bug.
2. Для skipped checks ввести явный статус/violation типа `skipped`.
3. Добавить exception chaining (`raise ... from exc`) там, где теряется traceback.
4. Унифицировать `raise SystemExit(main())` и exit-коды.
5. Запретить silent ImportError fallback для production-gating lint checks.

**Критерии приемки:**

- CI больше не показывает "чисто", когда проверка фактически не исполнилась;
- traceback сохраняет первичную причину ошибки;
- broad catch не скрывает баги в critical path.

**Статус исполнения (2026-04-13):** выполнено для Phase 1 target surface:
production lint fallback в `lint_foundry_data_plane.py` теперь возвращает
явную degraded violation, `migrate.py` исправлен на реальные migration exports
и атомарную запись, `check_action_freshness.py` различает degraded network
lookup, а unified CLI блокирует failed/degraded preflight с machine-readable
статусом.

### WS-1D. Legacy quarantine

**Цель:** изолировать сломанные и устаревшие инструменты.

**Основные поверхности:**

- `tools/ops_runners/migrations/migrate.py`
- broken UDF demos/diagnostics
- legacy foundry imports в `tools/research/demos/*`

**Задачи:**

1. Составить inventory broken tools со статусом:
   fix now / move to `_deprecated` / remove.
2. Перенести явно нерабочие утилиты в `tools/archive/`.
3. Добавить warning banner и replacement path.
4. Убрать сломанные примеры из default docs/README surfaces.

**Критерии приемки:**

- active tooling surface содержит только поддерживаемые команды;
- broken legacy code не создает ложное впечатление поддержки.

**Статус исполнения (2026-04-13):** выполнено через `tools/archive/`,
registry lifecycle metadata и README-политику: UDF diagnostics/demos
quarantined, legacy Foundry demos deprecated, replacements задокументированы,
default docs больше не представляют broken tooling как active surface.

---

## Phase 2 - Unified tooling platform

### WS-2A. Unified CLI entry point

**Цель:** заменить коллекцию standalone entry points единым интерфейсом.

**Основные поверхности:**

- `tools/cli.py`
- `pyproject.toml`
- все подкатегории `tools/*`

**Задачи:**

1. Ввести `polisyos-tools <category> <command>` на базе Typer или Click.
2. Реализовать lazy loading subcommands.
3. Добавить shell autocomplete для zsh/bash/fish.
4. Нормализовать `main(argv: Sequence[str] | None = None) -> int`.
5. Сохранить совместимость: старые script paths сначала становятся thin wrappers
   или documented aliases, потом удаляются.

**Критерии приемки:**

- contributor может discover all commands через `polisyos-tools --help`;
- все новые команды регистрируются через единый механизм.

### WS-2B. Shared tooling runtime

**Цель:** убрать копипаст и разношерстные правила запуска.

**Основные поверхности:**

- `tools/lib/runner.py`
- `tools/lib/output.py`
- `tools/lib/preflight.py`
- `tools/lib/cache.py`
- `tools/lib/timing.py`

**Задачи:**

1. Ввести `CommandSpec`/`ToolSpec`:
   имя, категория, required extras, output formats, deprecated flag.
2. Реализовать общий preflight checker для extras и внешних зависимостей.
3. Добавить единые formatter-ы для `text`, `json`, `sarif`, `junit`.
4. Вынести helpers для atomic writes, safe subprocess, bounded HTTP, safe SQL ids.
5. Стандартизировать structured timing/log record на каждый запуск.

**Критерии приемки:**

- инструменты не дублируют базовую обвязку запуска;
- user получает одинаковое поведение help/errors/output во всех подкомандах.

### WS-2C. Packaging and import normalization

**Цель:** сделать `tools` нормальным Python package, пригодным для discovery и
тестирования как модуля.

**Основные поверхности:**

- 14 поддиректорий без `__init__.py`
- `tools/devx/workspace/*`
- `tools/quality/lint/*`

**Задачи:**

1. Добавить `__init__.py` в все package-worthy директории.
2. Перевести bare imports и ad hoc fallback imports на единый стиль.
3. Вынести общую логику, например `is_type_checking_test()`, в shared module.
4. Нормализовать `pathlib` usage и убрать mixed `os.path`/`Path` внутри одного файла.

**Критерии приемки:**

- `python -m tools.<...>` и package imports работают предсказуемо;
- CLI auto-discovery и pytest imports не зависят от cwd-хаков.

### WS-2D. Tool dependency graph and docs metadata

**Цель:** сделать зависимости между инструментами явными.

**Задачи:**

1. Задекларировать tool DAG:
   например, `gen_schema` до `abi_diff`, preflight до deploy.
2. Добавить `polisyos-tools graph` с Mermaid/DOT output.
3. Генерировать reference/help docs из docstrings и command metadata.
4. Дописать README для отсутствующих каталогов:
   `ci/`, `cloud/`, `ukraine_data/`, `validation/`, `calibration/`, `release/`.

**Критерии приемки:**

- порядок исполнения больше не хранится "в голове";
- missing README gap закрыт полностью.

**Статус исполнения (2026-04-13):** выполнено: добавлен `polisyos-tools`,
`tools.registry`, lazy command dispatch, Click autocomplete snippets,
shared runtime modules (`runner`, `output`, `preflight`, `cache`, `timing`,
`http`), package `__init__.py`, generated
`docs/reference/tools.md`, Mermaid/DOT/JSON graph output и README для
`ci/`, `cloud/`, `ukraine_data/`, `validation/`, `calibration/`, `release/`.

---

## Phase 3 - Testing and observability

### WS-3A. Test program for critical tools

**Цель:** поднять доверие к tooling, который гейтит production code.

**Приоритетные модули:**

- `tools/quality/lint/lint_imports.py`
- `tools/devx/architecture/guardrails.py`
- `tools/devx/architecture/scaffold.py`
- `tools/quality/diagnostics/gen_schema.py`
- `tools/quality/diagnostics/abi_diff.py`
- `tools/devx/workspace/bootstrap.py`
- `tools/devx/workspace/doctor.py`
- `tools/devx/workspace/verify.py`
- `tools/ops_runners/cloud/*`
- `tools/ops_runners/ukraine_data/*`
- `tools/ops_runners/migrations/*`
- `tools/quality/diagnostics/check_perf_regression.py`
- `tools/quality/diagnostics/visualize_provenance.py`

**Требуемые виды тестов:**

1. Unit tests для validation, parser и branching logic.
2. Property-based tests для AST/import analysis и ABI diff matching.
3. Snapshot/golden tests для scaffold/gen_schema/generate_runtime_client.
4. Subprocess tests для CLI/shell wrappers.
5. Fault-injection tests для partial merge, interrupted writes, missing extras.

**Цели покрытия:**

- `lint_imports`, `gen_schema`, `abi_diff`, `workspace/*`: не ниже 80%;
- cloud/data destructive tooling: coverage по risk-based surface, а не только
  формальный процент;

- shell scripts: smoke coverage через subprocess/Bats-like checks.

### WS-3B. CI signal quality and structured output

**Цель:** сделать результаты tooling пригодными для автоматической обработки.

**Задачи:**

1. `lint` -> SARIF.
2. `perf` и regression gates -> JUnit XML или GitHub annotations.
3. ABI diff -> structured JSON verdict + details.
4. Пропущенные проверки -> explicit `skipped` outcome.
5. CI summary page -> что упало, что деградировало, сколько заняло.

**Критерии приемки:**

- GitHub/GitLab CI видит не только текст в stdout, но и структурированный итог;
- skipped/degraded состояния не теряются.

### WS-3C. Tool timing and operational telemetry

**Цель:** ответить на вопрос "что тормозит CI и локальный workflow?" без догадок.

**Задачи:**

1. Писать duration/status/tool/category/output-format в structured log.
2. Сохранять последние N запусков локально и в CI artifact.
3. Добавить `polisyos-tools report-timing`.
4. Ввести baseline budget для самых дорогих команд.

**Критерии приемки:**

- можно увидеть, какие инструменты замедляют pipeline;
- performance regression в tooling становится наблюдаемой.

**Статус исполнения (2026-04-13):** выполнено для unified tooling surface и
критичных Phase 3 modules. Добавлены новые tests в `tests/repo_quality/tools/` для
`lint_imports`, `guardrails`, `scaffold`, `gen_schema`, `abi_diff`,
`check_perf_regression`, `visualize_provenance`, `workspace/bootstrap`,
`workspace/doctor`, `workspace/verify` и unified CLI; покрыты unit,
property-based, subprocess, golden/snapshot и fault-path сценарии. Unified CLI
и critical tools теперь экспортируют machine-readable `json`/`sarif`/`junit`
results, `check_perf_regression` различает `skipped`, `lint_imports`
поддерживает SARIF/JUnit, а `tools/lib/timing.py` пишет bounded structured
timing log с `tool/category/output-format/status/preflight_status`, retention,
baseline budgets и `polisyos-tools report-timing` c Markdown summary для CI
artifacts. Полный `tests/repo_quality/tools` по-прежнему имеет 2 pre-existing unrelated
acceptance-audit blocker-а по `workflow-identity`; новая Phase 3 поверхность
проходит без регрессий.

---

## Phase 4 - Repository consolidation

### WS-4A. Cloud consolidation

**Цель:** убрать раздробленность между `tools/ops_runners/cloud/`, `cloud_deploy/` и
`scripts/remote-acceptance`.

**Задачи:**

1. Перенести `cloud_deploy/` assets под `tools/ops_runners/cloud/`.
2. Разделить cloud surface на `deploy/`, `pipeline/`, `shards/`, `preflight/`.
3. Свести документацию и env contracts в одном месте.
4. Убрать дублирование shell/python entry points.

### WS-4B. Scripts consolidation

**Цель:** убрать необоснованную индирекцию через `scripts/`.

**Задачи:**

1. Bash wrappers -> CLI subcommands в `tools/devx/workspace`.
2. Data-prep scripts -> `tools/ops_runners/data/`.
3. Mutation scripts -> `tools/quality/testing/mutation.py`.
4. После миграции очистить `scripts/` или оставить только truly external helpers.

### WS-4C. Benchmarks consolidation

**Цель:** иметь один benchmark-story вместо двух несовместимых.

**Задачи:**

1. Перенести root `benchmarks/` под `tools/research/benchmarks/`.
2. Ввести `suite_registry.py`, `harness.py`, `metrics.py`, `_reports/`.
3. `tools/research/benchmarks/bench_domain.py` и `bench_simulation.py` перевести в
   `tools/research/benchmarks/jax/`.
4. Согласовать benchmark docs и run commands.

### WS-4D. Deprecated surface cleanup

**Цель:** сделать legacy-границу явной для contributor и CI.

**Задачи:**

1. Все нечинящиеся быстро legacy/demo/migration инструменты отметить явно.
2. Ввести централизованный warning и запрет на включение deprecated tools в CI.
3. Держать replacement-map в docs.

Статус: completed.

Примечания исполнения:

- canonical data-prep surface перенесен в `tools/ops_runners/data/*`; legacy `scripts/*.py`
  оставлены как thin wrappers;

- workspace `scripts/*` теперь проксируют в `python -m tools.cli workspace ...`;
- standalone `scripts/generate_stubs.py` и
  `scripts/update_signature_baseline.py` переведены в `tools/devx/foundry/*` и
  оставлены как thin wrappers;

- canonical benchmark entry point перенесен в `tools/research/benchmarks/run_all.py`,
  root `benchmarks/run_all_benchmarks.sh` переведен в compatibility wrapper к
  unified CLI;

- `tools/research/benchmarks/suite_registry.py`, `harness.py` и `metrics.py` теперь
  являются canonical tools-facing modules, root `benchmarks/*.py` оставлены
  как compatibility re-exports;

- live workflows/docs используют `polisyos-tools benchmarks run-all`, а не
  legacy benchmark shell surface;
  JAX smoke scripts — в `tools/research/benchmarks/jax/`, lex bench helpers — в
  `tools/research/benchmarks/lex/`;

- cloud surface разбит на `tools/ops_runners/cloud/deploy|pipeline|shards|preflight`,
  `cloud_deploy/` переведен в compatibility bridge;

- legacy remaining-stages flow больше не хранит hardcoded API keys и работает
  как compatibility bridge к reviewed resume workflow.

---

## Phase 5 - DX, extensibility and maintainability

### WS-5A. Incremental execution and cache

**Цель:** убрать needless full-tree rework.

**Задачи:**

1. Content-addressable cache для `lint_imports`, `gen_schema` и подобных команд.
2. `--changed-only` режим по `git diff`.
3. Persisted baseline hash для CI skip-if-unchanged.
4. Cache invalidation policy документировать и покрыть тестами.

**Статус исполнения (2026-04-13):** выполнено для `lint_imports.py` и
`gen_schema.py`. Добавлены content-addressable cache keys, `--changed-only`,
persisted baseline hash (`--baseline-label` + `--skip-if-unchanged`),
regression tests и documented invalidation policy в `tools/quality/lint/README.md` и
`tools/quality/diagnostics/README.md`.

### WS-5B. Autofix and rule registry

**Цель:** улучшить DX и extensibility без разрастания core-файлов.

**Задачи:**

1. `lint_imports --fix` и `lint_foundry --fix` вводить только после хорошей
   snapshot/regression базы.
2. Ввести `tools/quality/lint/rules/` и registry pattern для правил.
3. Разрешить domain-specific rules регистрироваться без редактирования core.

**Статус исполнения (2026-04-13):** выполнено для lint surface. Добавлен
`tools/quality/lint/rules/` registry, `lint_foundry.py` переведен на rule registry,
`lint_foundry --fix` получил safe autofix для standalone `print()` debug calls,
а `lint_imports --fix` — canonical rewrite для `architecture/imports/exceptions.toml`.

### WS-5C. Hot-path and maintainability refactors

**Цель:** убрать накопленный structural debt.

**Задачи:**

1. Упростить god-функции и глубокую вложенность.
2. Убрать dead code и дублирование helpers.
3. Заменить tuple indexing на `NamedTuple`/`dataclass`.
4. Сократить функции с 9-11 параметрами через config objects.
5. Оптимизировать:

   - `abi_diff.py` rename matching;
   - `lint_imports.py` exception matching;
   - прочие `O(n^2)` и `O(n*m)` места из аудита.
6. Вынести magic numbers argparse/defaults в именованные константы.
7. Заменить signal-handler флаги на `threading.Event` там, где это уместно.

**Критерии приемки:**

- code review для `tools/` больше не упирается в giant functions;
- hot-path инструменты масштабируются лучше и измеримо быстрее.

**Статус исполнения (2026-04-13):** выполнено по основным hot paths. В
`lint_imports.py` введены config/context dataclasses, compiled exception index,
именованные constants и cache-aware parse pipeline; в `abi_diff.py` rename
matching переведен на alias/semantic-hash indexes и narrowed similarity
buckets вместо полного `O(n*m)` перебора; `lint_foundry.py` разбит на registry
surface и safe fix pipeline. Все изменения покрыты targeted tests.

---

## Рекомендуемый порядок первых PR

1. Секреты, HTTPS и hardcoded prod paths.
2. SQL/shell hardening.
3. Shell safety flags, broken path fix, temp cleanup traps.
4. `canonical_auto_approve` dry-run/confirm/atomic output.
5. `merge_shards` transaction/temp-db/rollback.
6. Atomic state writes и marker locking в `ukraine_data`.
7. Resource leaks, bounded reads, UTF-8, explicit validation.
8. Silent skip/broad catch cleanup.
9. Unified CLI skeleton + `pyproject` script.
10. Test harness и structured output foundation.

Такой порядок минимизирует риск: сначала прекращаем ущерб, потом стабилизируем
данные, затем строим платформу поверх уже безопасной базы.

---

## Матрица покрытия структурных SOTA-gap находок

| SOTA gap                                | План закрытия |
| --------------------------------------- | ------------- |
| 1. Нет единого CLI-фреймворка           | WS-2A, WS-2B  |
| 2. Нет тестов для самих инструментов    | WS-3A         |
| 3. Фрагментация cloud/deploy            | WS-4A         |
| 4. Нет structured output                | WS-2B, WS-3B  |
| 5. Нет кэширования и инкрементальности  | WS-5A         |
| 6. Нет dry-run / fix mode               | WS-0D, WS-5B  |
| 7. Нет plugin/extension system          | WS-5B         |
| 8. Нет telemetry / timing               | WS-2B, WS-3C  |
| 9. Дублирование и разделение benchmarks | WS-4C         |
| 10. `scripts/` как лишняя индирекция    | WS-4B         |
| 11. Нет pre-flight validation           | WS-2B         |
| 12. Неполная документация инструментов  | WS-2D         |
| 13. Нет dependency graph между tools    | WS-2D         |
| 14. Legacy/broken код не изолирован     | WS-1D, WS-4D  |

## Матрица покрытия code-audit находок

| Группа находок                                                                  | Что закрывает       |
| ------------------------------------------------------------------------------- | ------------------- |
| Hardcoded keys, hardcoded prod paths, HTTP вместо HTTPS                         | WS-0A               |
| SQL injection через f-strings                                                   | WS-0B               |
| `shell=True` и отсутствие shell safety flags                                    | WS-0B, WS-0C        |
| Нерабочий `run_datasets_validation.sh`                                          | WS-0C               |
| Destructive ops без dry-run/confirm                                             | WS-0D               |
| Нет rollback, нет idempotency, run-id collisions                                | WS-0D, WS-1A        |
| TOCTOU race conditions и неатомарные записи state/files                         | WS-1A               |
| Утечки fd, missing finally, `duckdb.connect()` без context manager              | WS-1B               |
| Unbounded HTTP reads, missing encoding, trailing newline drift                  | WS-1B               |
| `assert`-валидация, хрупкий `int()`, JSON без shape checks, unsafe indexing     | WS-1B               |
| Silent lint skip и broad `except Exception`                                     | WS-1C               |
| Missing exception chaining, inconsistent `sys.exit`                             | WS-1C               |
| Dead code, duplicate helpers, import inconsistency, missing `__init__.py`       | WS-2C, WS-5C        |
| Нет README/doc metadata/dependency graph                                        | WS-2D               |
| Coverage gap для критичных tools                                                | WS-3A               |
| Нет SARIF/JUnit/JSON результатов                                                | WS-3B               |
| Нет timing telemetry                                                            | WS-3C               |
| `cloud_deploy/`, `scripts/`, root `benchmarks/` раздроблены                     | WS-4A, WS-4B, WS-4C |
| Legacy demos и broken migrations                                                | WS-1D, WS-4D        |
| Нет cache/changed-only                                                          | WS-5A               |
| Нет `--fix` и rule registry                                                     | WS-5B               |
| O(n^2), god-functions, deep nesting, magic numbers, tuple indexing, many params | WS-5C               |

---

## D1 Docs Impact Table

| D1 doc cluster                      | Exact files                                                                                                                                                                                                                                                                 | Source of truth                                                                      | Validation command or evidence                                | Backlog / priority |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------ |
| Generated tools reference           | `docs/reference/tools.md`                                                                                                                                                                                                                                                   | `tools.registry` command metadata, dependency graph edges, lifecycle status metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` | none               |
| Tooling READMEs                     | `tools/README.md`, `tools/quality/validation/README.md`, `tools/devx/workspace/README.md`, `tools/devx/architecture/README.md`                                                                                                                                                      | canonical CLI behavior, workspace gates, validation helpers, architecture guardrails | `uv run polisyos-tools workspace ci-parity --skip-browser`    | none               |
| Shared D1-L5 how-to/reference pages | `docs/how-to/operate-ci-cd-platform.md`, `docs/how-to/manage-generated-artifacts.md`, `docs/how-to/release-policy.md`, `docs/reference/quality-gates.md`, `docs/reference/dependency-platform.md`, `docs/reference/merge-governance.md`, `docs/reference/ratchet-policy.md` | repo workflows, generated-artifact guardrails, release tooling, ratchet policy docs  | `uv run polisyos-tools architecture guardrails check`         | none               |

D1 closure note: all required D1-L5 pages are present. Additional per-category
README expansion outside this required set is a D2/P3 improvement, not a D1
blocker.

## Риски исполнения

1. **Соблазн начать с CLI вместо security-fix.**
   Это создаст красивую оболочку вокруг небезопасного содержимого.
2. **Слишком ранний перенос каталогов.**
   Если сначала двигать `cloud_deploy/` и `benchmarks/`, можно размазать баги по
   новой структуре и усложнить regression triage.
3. **Автофикс без snapshot-базы.**
   `--fix` для lint-правил нельзя включать раньше, чем появятся надежные golden
   tests на преобразования.
4. **Подмена надежности формальным coverage %.**
   Для destructive/cloud/data tools важнее сценарии partial failure и resume,
   чем большой процент покрытия сам по себе.

## Явные non-goals

- Не переписывать весь `tools/` в runtime-сервис.
- Не объединять каталоги в одну giant migration без промежуточных совместимых
  entry points.

- Не включать experimental autofix или plugin registry до завершения Phase 1-3.

## Итог

Правильная последовательность для `tools/` выглядит так:

1. остановить security и integrity протечки;
2. сделать destructive/data paths атомарными и идемпотентными;
3. вытащить общую платформу запуска в unified CLI;
4. поднять тесты, structured output и telemetry;
5. только после этого консолидировать каталоги и вкладываться в DX.

Если этот порядок выдержать, `tools/` перестанет быть "сложным набором полезных
скриптов" и станет полноценным engineering control plane для репозитория.
