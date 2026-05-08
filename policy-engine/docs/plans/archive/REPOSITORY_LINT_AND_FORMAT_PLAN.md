---
title: Repository Lint and Format Plan
status: archived
owner: team-polisyos
created: 2026-04-23
last_verified: 2026-04-24
stability: archived
archived: 2026-04-24
---

> **Archived:** implementation completed and canonical repository hygiene gates
> are documented in `docs/reference/repository-hygiene.md`.

# Repository Lint and Format Plan

## 0. Цель

Этот план задает репозиторный контракт для поэтапного наведения порядка в
`policy-engine/` по четырем направлениям одновременно:

1. единое и предсказуемое форматирование;
2. реальные quality gates, а не только style gates;
3. максимальная независимость потоков работы по директориям;
4. постепенное ужесточение правил без "big bang" PR на тысячи файлов.

Целевое состояние: кодовая база должна быть чище, безопаснее, проще для review,
дешевле в сопровождении и расширении, при этом без разрушительного массового
шума в diff.

## 1. Снимок репозитория на 2026-04-23

Ниже не полный inventory, а только те зоны, которые влияют на план lint/format:

| Область        | Примерный объем | Основные типы                                |
| -------------- | --------------: | -------------------------------------------- |
| `src/polisyos` | 1996 файлов     | 1880 `.py`, 84 `.md`                         |
| `tests`        | 1362 файла      | 1301 `.py`, 22 `.md`, 18 `.json`             |
| `tools`        | 440 файлов      | 318 `.py`, 45 `.sh`, 50 `.md`                |
| `frontend`     | 1100 файлов     | 404 `.tsx`, 271 `.ts`, 68 `.js`, 211 `.html` |
| `docs`         | 705 файлов      | 409 `.md`, 264 `.log`                        |
| `schemas`      | 118 файлов      | 104 `.json`, 12 `.md`                        |
| `ops`          | 98 файлов       | 42 YAML, 21 `.rego`, 5 `.sql`, 13 `.md`      |
| `benchmarks`   | 268 файлов      | 145 `.py`, 92 `.json`, 22 `.log`             |
| `architecture` | 14 файлов       | 8 `.toml`, 3 `.json`, 3 `.md`                |
| `scripts`      | 19 файлов       | 10 `.py`, 7 без расширения, 2 `.sh`          |

Вывод из этого снимка:

- репозиторий уже не "просто Python-проект";
- один глобальный formatter на все подряд здесь вреден;
- план должен быть file-type aware и dependency aware;
- главные serial зоны диктуются архитектурой Python-пакетов, а не только размером.

## 2. Репозиторные принципы

1. Один основной formatter на один язык.
2. Линтинг и форматирование разделяются концептуально:
   formatter отвечает за форму, linter за correctness и hygiene.
3. Directory-by-directory ratchet лучше, чем one-shot cleanup по всему дереву.
4. Каждая рабочая волна должна быть мерджабельна сама по себе.
5. Generated, cached, runtime-state и bulk data директории не должны участвовать
   в массовом автоформатировании.
6. Для Python-поверхностей источник истины для стиля - `ruff format`; для
   TypeScript/JS - `prettier`; для shell - `shfmt`; для TOML - `taplo fmt`;
   для Rego - `opa fmt`.
7. Если директория имеет собственный архитектурный gate, он считается частью
   lint-surface, а не "отдельной бюрократией".
8. Source + owning tests чинятся в одном потоке; tests не должны жить отдельной
   backlog-колонкой раньше своей source-директории.
9. Новый ignore допускается только как временный, локальный и объясненный.
10. CI должен разделять fast changed-scope gate и full scheduled gate.

## 3. Рекомендуемый стек best practices

План опирается на текущий стек репозитория и на официальные рекомендации
инструментов, а не на смену tooling ради моды.

### 3.1 Python

- `ruff check` как основной lint/hygiene gate.
- `ruff format` как основной formatter.
- `mypy --strict` как главный статический типовой gate.
- `dmypy` для локального ускоренного цикла на больших поверхностях.
- `basedpyright` как второй type checker для safety-oriented signal и постепенного
  расширения покрытия через baseline.

- repo-specific guards через `tools/quality/lint/*`, `import_policy.toml`,
  `architecture/packages/boundaries.toml`.

Практический вывод:

- не добавлять Black/isort/flake8 поверх Ruff;
- не запускать `basedpyright` сразу fail-closed на весь Python-репозиторий;
- сначала зафиксировать baseline, потом постепенно сужать его за директориями.

### 3.2 TypeScript / React / frontend

- `eslint` flat config остается каноническим linter.
- `typescript-eslint` typed linting остается обязательным для
  `apps/runtime-dashboard`.

- `prettier` остается formatter для TS/TSX/JS/JSON/CSS/HTML в frontend.
- `dependency-cruiser` и custom architecture checks остаются частью gate.

Практический вывод:

- не заменять текущий frontend stack на Biome "одним махом";
- сначала довести до зеленого текущие workspace gates;
- только потом оценивать точечные улучшения вроде `projectService`.

### 3.3 Markdown

- `markdownlint-cli2` как основной Markdown linter.
- Без repo-wide auto-reflow authored prose.
- Для больших архивных и исследовательских документов - lint-only либо
  touched-file-only режим.

Практический вывод:

- `docs/archive/**` не надо массово переписывать formatter-ом;
- правила должны ловить структуру, headings, list/style hygiene и broken layout,
  но не создавать гигантский churn в длинной исследовательской прозе.

### 3.4 YAML / GitHub Actions / Helm

- `yamllint` для общего YAML hygiene.
- `actionlint` для GitHub Actions.
- `helm lint` для Helm charts.

Практический вывод:

- `.github/workflows/**` должны проходить и `yamllint`, и `actionlint`;
- Helm values/chart surface должна валидироваться отдельным chart-aware шагом.

### 3.5 Shell

- `shfmt` для форматирования shell.
- `shellcheck` для correctness и portability.

Практический вывод:

- shell-скрипты в `tools/**`, `scripts/**`, `ops/scripts/**` и wrapper-скрипты
  должны чиниться одной волной по общему shell contract.

- zsh-специфичные скрипты нужно явно маркировать; для POSIX/Bash не плодить
  ad hoc style.

### 3.6 TOML

- `taplo fmt` и `taplo fmt --check`.

Практический вывод:

- `architecture/*.toml`, `release/**/*.toml`, `release-fragments/**/*.toml`,
  `tests/quarantine.toml`,
  security/release config поверхности должны стать низкорисковой ранней волной,
  потому что их форматирование почти не зависит от кода.

### 3.7 Rego

- `opa fmt --write` для единообразного formatting.
- `opa check --strict` как обязательный quality gate.
- `opa test` для policy tests.

Практический вывод:

- `ops/policy/policies/**` - отдельная независимая полоса работ после foundation.

## 4. Что входит в scope, а что нет

### 4.1 Полный scope

Полный lint/format scope плана:

- `src/polisyos/**`
- `tests/**`
- `tools/**`
- `frontend/**`
- `docs/**`
- `schemas/**`
- `ops/**`
- `architecture/**`
- `scripts/**`
- `benchmarks/**`
- `release/**`
- `release-fragments/**`
- `.github/**`
- верхнеуровневые authored файлы вроде `README.md`, `CONTRIBUTING.md`,
  `pyproject.toml`, `mkdocs.yml`, `import_policy.toml`, `import_exceptions.toml`

### 4.2 Check-only или generator-owned scope

Эти поверхности можно валидировать, но нельзя массово "улучшать" руками:

- generated clients и generated API outputs;
- schema snapshots;
- committed machine-generated JSON;
- release evidence bundles;
- большие benchmark result manifests;
- chart/render outputs, если появятся.

### 4.3 Excluded from bulk formatting

Эти директории и паттерны должны быть явно исключены из repo-wide sweeps:

- `.venv*`, `.uv-cache`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`,
  `.hypothesis`, `__pycache__`

- `.polisyos/**`, `runs/**`, `logs/**`, `tmp/**`, `.tmp/**`
- `out/**`, `dist/**`, `site/**`, `storybook-static/**`, `coverage/**`
- `production_data/**`, `data/raw/**`
- `benchmark-results/**`
- binary/media artifacts
- `.DS_Store`
- `.log` bundles under `docs/**` and `benchmarks/**`

Отдельное правило: наличие tracked `.DS_Store` считается hygiene defect и должно
быть устранено ранней волной, но не через formatter.

## 5. Dependency model и где нужна последовательность

Главный Python dependency DAG уже отражен в `import_policy.toml` и
`architecture/packages/boundaries.toml`. Для lint/format это означает:

1. `common -> ir -> core` - serial foundation для Python product code.
2. После `core` можно параллелить несколько доменных полос:

   - `data_forge` + legacy data packages
   - `fabric`
   - `lex`
   - `scholar`
   - `foundry`
3. `scientist` желательно запускать после стабилизации этих доменных полос,
   потому что он зависит сразу от нескольких из них.
4. `runtime` должен идти после стабилизации public facades нижних пакетов.

Все остальные большие поверхности могут жить значительно более независимо:

- `frontend/**`
- `docs/**`
- `schemas/**`
- `architecture/**`
- `ops/**`
- `benchmarks/**`
- `tools/**` после собственной shared foundation

## 6. Модель максимального параллелизма

### 6.1 Serial foundation

Эти задачи выполняются один раз и до старта широкого распараллеливания:

1. Зафиксировать repo-wide include/exclude policy.
2. Ввести root `.editorconfig`.
3. Довести до канонического состояния конфиги:

   - `pyproject.toml`
   - `.pre-commit-config.yaml`
   - `.markdownlint-cli2.jsonc`
   - будущие `.yamllint` и `.taplo.toml`
4. Разделить authored, generated и runtime-state поверхности.
5. Добавить canonical wrapper-команды в `tools/devx/workspace` или `polisyos-tools`,
   чтобы люди не изобретали 20 разных локальных команд.

Без этого параллельные PR начнут конфликтовать в конфиге вместо того, чтобы
чистить директории.

### 6.2 После foundation можно запускать одновременно

| Параллельный поток | Scope                                                                   | Блокируется чем                              |
| ------------------ | ----------------------------------------------------------------------- | -------------------------------------------- |
| F1                 | `apps/runtime-dashboard`                                            | только frontend-specific config              |
| F2                 | `packages/runtime-api-client`, `runtime-reference-shell`                | generator contract / minimal frontend config |
| P1                 | `src/polisyos/common` + `tests/unit/common`                                  | foundation                                   |
| D1                 | `docs/**`, `README.md`, `CONTRIBUTING.md`                               | markdown policy                              |
| C1                 | `architecture/**`, `release/**`, `release-fragments/**`, top-level TOML | taplo policy                                 |
| O1                 | `ops/**`, `.github/**`                                                  | yamllint/actionlint/shell/rego policy        |
| T1                 | `tools/lib`, `tools/devx/workspace`, `scripts/**`                           | foundation                                   |
| B1                 | `benchmarks/**`                                                         | python + shell policy                        |

### 6.3 Потоки, которые запускаются после первых merge

| Параллельный поток | Scope                                                              | Блокируется чем |
| ------------------ | ------------------------------------------------------------------ | --------------- |
| P2                 | `src/polisyos/ir` + `tests/unit/ir`                                     | P1              |
| P3                 | `src/polisyos/core` + `tests/unit/core`                                 | P2              |
| T2                 | `tools/quality`, `tools/quality/validation`, `tools/ci`                    | T1              |
| T3                 | `tools/devx`, `tools/connectors`, `tools/ops/runtime`, `tools/ops/release` | T1              |

### 6.4 Доменные полосы после `core`

| Параллельный поток | Scope                                                                          | Блокируется чем                                               |
| ------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| P4                 | `data_forge`, `academic`, `datasets`, `ukraine_data`, `batch_*` + owning tests | P3                                                            |
| P5                 | `fabric` + `tests/unit/fabric`                                                      | P3                                                            |
| P6                 | `lex` + `tests/unit/lex`                                                            | P3                                                            |
| P7                 | `scholar` + `tests/unit/scholar`                                                    | P3                                                            |
| P8                 | `foundry` + `tests/unit/foundry`                                                    | P3, желательно после стабилизации `fabric/data_forge` фасадов |

### 6.5 Последние Python consumer полосы

| Параллельный поток | Scope                                    | Блокируется чем                             |
| ------------------ | ---------------------------------------- | ------------------------------------------- |
| P9                 | `scientist` + `tests/unit/scientist`          | P4-P8                                       |
| P10                | `runtime` + `tests/unit/runtime`              | P4-P9 public facades                        |
| P11                | `synthetic_world`, `calibration` + tests | P8-P9 в зависимости от фактических импортов |

## 7. Фазовый план

## Фаза 0. Foundation contracts

### Цель

Создать единый lint/format contract, после которого директории можно чистить
независимо друг от друга.

### Изменения

1. Завести root `.editorconfig`.
2. Расширить root `.markdownlint-cli2.jsonc` с четкими glob-политиками:
   authored docs, package README, plan docs, но не `docs/archive/**`.
3. Добавить root `.yamllint`.
4. Добавить root `.taplo.toml`.
5. Зафиксировать shell policy:

   - `shfmt` options
   - `shellcheck` scope
6. Зафиксировать Rego policy:

   - `opa fmt`
   - `opa check --strict`
   - `opa test`
7. Для Python решить policy по `basedpyright`:

   - либо curated include + расширение по директориям;
   - либо репозиторный baseline-файл и ratchet.
8. Обновить `pre-commit` так, чтобы hooks были быстрыми и типизированными по
   file type, а тяжелые полные проходы оставались в CI/nightly.
9. Определить canonical wrapper-команды:

   - `polisyos-tools workspace verify`
   - `polisyos-tools workspace lint-fast`
   - `polisyos-tools workspace lint-full`
   - `polisyos-tools workspace format-check`
   - `polisyos-tools workspace docs-style`

### Acceptance

- есть один документированный include/exclude contract;
- full authored scope не задевает runtime/caches/generated;
- все будущие директории знают, какой toolchain к ним применяется.

## Фаза 1. Low-risk config and prose surfaces

### Почему рано

Это почти не зависит от Python import DAG и быстро дает зеленые wins.

### Подволны

1. `architecture/**`, `release/**`, `release-fragments/**`
2. `.github/**`
3. `docs/**`, `README.md`, `CONTRIBUTING.md`
4. `schemas/**`

### Инструменты

- `taplo fmt` / `taplo fmt --check`
- `yamllint`
- `actionlint`
- `markdownlint-cli2`
- при необходимости generator-owned validation для schema artifacts

### Особые правила

- `docs/archive/**` - lint-only on touch, без массового reflow.
- `schemas/**/*.json` - только если это authored schema source, а не snapshot.
- `.github/workflows/**` - `yamllint + actionlint` обязательно в паре.

## Фаза 2. Frontend wave

### Scope

- `apps/runtime-dashboard`
- `packages/runtime-api-client`
- `apps/runtime-reference-shell`

### Причина раннего параллелизма

Frontend почти не зависит от Python import DAG; критическая зависимость только
одна - runtime contract / generated API client flow.

### Подход

1. Сначала `runtime-dashboard`, так как это основной workspace.
2. Затем generator flow для `runtime-api-client`.
3. Затем `runtime-reference-shell`, как легкая независимая поверхность.

### Exit gate

- `npm run lint`
- `npm run format:check`
- `npm run typecheck`
- `npm run check:architecture`
- contract drift checks
- focused tests для затронутых feature slices

## Фаза 3. Python base layers

### Serial order

1. `src/polisyos/common` + `tests/unit/common`
2. `src/polisyos/ir` + `tests/unit/ir`
3. `src/polisyos/core` + `tests/unit/core`

### Почему строго последовательно

Эти слои лежат в основании import DAG. Пока они не стабилизированы, downstream
потоки неизбежно будут ловить шум от общих типов, import hygiene и public API.

### Standard gate для каждой директории

```bash
uv run ruff format <dir> <tests-dir>
uv run ruff check --fix <dir> <tests-dir>
uv run ruff check <dir> <tests-dir>
uv run mypy <dir>
uv run basedpyright <dir>
uv run pytest <tests-dir>
```

Если `basedpyright` еще не fail-closed на всей зоне, применяется baseline-based
ratchet: новые ошибки блокируются, исторические постепенно вымываются.

## Фаза 4. Python domain waves

После `core` запускаются параллельные полосы.

### Волна 4A. Data and migration surface

Scope:

- `src/polisyos/data_forge`
- `src/polisyos/academic`
- `src/polisyos/datasets`
- `src/polisyos/ukraine_data`
- `src/polisyos/batch_common`
- `src/polisyos/batch_snapshot`
- owning tests

Особое правило:

- legacy packages не должны получать новые blanket ignores;

### Волна 4B. Fabric

Scope:

- `src/polisyos/fabric`
- `tests/unit/fabric`

Особое правило:

- вместе с style cleanup идти через custom guards:
  `lint-connectors`, `lint-connector-hardening`, import policies, data-plane
  invariants по мере применимости.

### Волна 4C. Lex and Scholar

Scope:

- `src/polisyos/lex`, `tests/unit/lex`
- `src/polisyos/scholar`, `tests/unit/scholar`

Почему в одной волне:

- оба слоя завязаны на документные и retrieval-oriented поверхности;
- можно разделить на два независимых PR-потока, но policy и commands у них близки.

Статус на 2026-04-24:

- выполнено для `src/polisyos/lex`, `tests/unit/lex`, `src/polisyos/scholar`, `tests/unit/scholar`;
- Ruff format/check, mypy, basedpyright и pytest проходят на scope волны;
- legacy debt зафиксирован локальными ratchet-исключениями и basedpyright baseline.

### Волна 4D. Foundry

Scope:

- `src/polisyos/foundry`
- `tests/unit/foundry`

Особое правило:

- не ослаблять mypy plugin contract;
- отдельно держать mutation / benchmark / slow suites вне обязательного fast gate;
- heavy numerics и method registries лучше чистить вертикальными slices,
  а не whole-tree rewrite.

## Фаза 5. Python consumer waves

### Волна 5A. Scientist

Scope:

- `src/polisyos/scientist`
- `tests/unit/scientist`

Почему поздно:

- это крупный consumer сразу нескольких нижних доменных слоев;
- иначе поток утонет в чужих типовых и import-ошибках.

### Волна 5B. Runtime

Scope:

- `src/polisyos/runtime`
- `tests/unit/runtime`

Особое правило:

- runtime surfaces должны проверяться не только Ruff/Mypy, но и на boundary
  contract: public facades only, HTTP/runtime policy checks, OpenAPI drift.

Статус реализации на 2026-04-24:

- введен canonical gate `uv run polisyos-tools workspace runtime-surface`;
- gate покрывает `ruff format --check`, `ruff check`, `mypy src/polisyos/runtime`,
  `basedpyright src/polisyos/runtime`, OpenAPI/client drift check и
  `pytest tests/unit/runtime`;

- runtime Ruff debt оформлен explicit per-module ratchet для динамических
  HTTP/CAS/framework boundary точек, без wildcard на весь runtime package.

### Волна 5C. Satellite modules

Scope:

- `src/polisyos/synthetic_world`
- `src/polisyos/calibration`
- смежные tests

Эти модули можно вести параллельно с late scientist/runtime cleanups, если
фактический import graph не создает жесткой связки.

## Фаза 6. Tools and scripts

### Serial foundation внутри tools

Сначала:

- `tools/lib`
- `tools/devx/workspace`
- `scripts/**`

Потом можно параллелить:

- `tools/quality`, `tools/quality/validation`, `tools/ci`
- `tools/devx`, `tools/connectors`, `tools/ops/runtime`, `tools/ops/release`
- `tools/ops/cloud`, `tools/ops`, `tools/research`, `tools/research/benchmarks`

### Почему так

`tools/lib` и `tools/devx/workspace` - это shared substrate. Пока они не в порядке,
остальные tool-пакеты будут расходиться по локальным конвенциям.

### File-type gates

- Python: Ruff + mypy/basedpyright там, где это уместно
- Shell wrappers: shfmt + ShellCheck
- Markdown READMEs: markdownlint-cli2
- TOML/JSON config: Taplo / generator-owned validation

## Фаза 7. Ops and policy-as-code

### Scope

- `ops/observability/grafana/**`
- `ops/cloud/helm/**`
- `ops/observability/**`
- `ops/policy/**`
- `ops/observability/prometheus/**`
- `ops/security/**`
- `ops/scripts/**`

### Tool matrix

| Подзона                 | Инструменты                                 |
| ----------------------- | ------------------------------------------- |
| Helm charts             | `yamllint`, `helm lint`                     |
| Prometheus/Grafana YAML | `yamllint`                                  |
| Rego                    | `opa fmt`, `opa check --strict`, `opa test` |
| shell scripts           | `shfmt`, `shellcheck`                       |
| TOML security config    | `taplo fmt --check`                         |

### Независимость

Эта волна почти независима от Python code cleanup и может идти параллельно с
frontend и Python domain waves после Phase 0.

## Фаза 8. Benchmarks and supporting research surfaces

### Scope

- `benchmarks/**`
- research support scripts under `tools/research/**`

### Особое правило

- lint и format применяются только к authored Python/shell/YAML;
- `*.json`, `*.log`, result bundles и release summaries не должны массово
  переформатироваться.

### Exit gate

- Ruff/Shell/YAML green для authored assets;
- benchmark runner wrappers не ломаются;
- большие result артефакты остаются вне auto-format churn.

## 8. Директории и рекомендуемые batch units

Ниже unit of work, который желательно держать в одном PR:

| Batch unit                                                                     | Почему это хороший размер                        |
| ------------------------------------------------------------------------------ | ------------------------------------------------ |
| `src/polisyos/common` + `tests/unit/common`                                         | низкая зависимость, хороший foundation slice     |
| `src/polisyos/ir` + `tests/unit/ir`                                                 | отдельный слой DAG                               |
| `src/polisyos/core` + `tests/unit/core`                                             | естественный package boundary                    |
| `src/polisyos/fabric` + `tests/unit/fabric`                                         | высокий внутренний cohesion                      |
| `src/polisyos/foundry/analysis` или `foundry/runtime` и owning tests           | лучше, чем весь `foundry` сразу                  |
| `src/polisyos/scientist/<subdomain>` и owning tests                            | иначе diff и type-signal станут слишком шумными  |
| `tools/lib` отдельно                                                          | shared substrate                                 |
| `tools/quality/*` отдельно от `tools/ops/cloud/*`                                  | разный риск и разный язык вспомогательных файлов |
| `ops/policy` отдельно                                                             | свой toolchain                                   |
| `ops/cloud/helm` отдельно                                                            | свой validation contract                         |
| `docs/reference`, `docs/how-to`, `docs/plans/active` как отдельные doc batches | не смешивать authored prose с archive            |

## 9. Канонические команды по типам поверхностей

## 9.1 Python

```bash
uv run ruff format <dirs>
uv run ruff check --fix <dirs>
uv run ruff check <dirs>
uv run mypy <dirs>
uv run basedpyright <dirs>
uv run pytest <tests-dirs>
```

Для локальной быстрой итерации на больших поверхностях:

```bash
uv run dmypy start -- --strict
uv run dmypy check <dirs>
```

## 9.2 Frontend

```bash
cd apps/runtime-dashboard
npm run format
npm run format:check
npm run lint
npm run typecheck
npm run check:architecture
```

## 9.3 Markdown

```bash
markdownlint-cli2
markdownlint-cli2 "docs/**/*.md" "README.md" "CONTRIBUTING.md"
```

## 9.4 YAML / GitHub Actions / Helm

```bash
yamllint .
actionlint
helm lint ops/cloud/helm/<chart>
```

## 9.5 Shell

```bash
shfmt -w <paths>
shellcheck <paths>
```

## 9.6 TOML

```bash
taplo fmt <paths>
taplo fmt --check <paths>
```

## 9.7 Rego

```bash
opa fmt --write <paths>
opa check --strict <paths>
opa test <paths>
```

## 10. CI и ratchet strategy

### 10.1 Pre-commit

В pre-commit должны жить только быстрые, file-scoped проверки:

- Ruff on changed Python files
- Ruff format check or formatter hook
- markdownlint on changed Markdown
- yamllint on changed YAML
- shfmt + ShellCheck on changed shell
- Taplo check on changed TOML

### 10.2 PR required gate

На PR должны жить:

- changed-directory formatting/lint/type gates;
- frontend workspace gates, если затронут `frontend/**`;
- `actionlint` при изменениях `.github/workflows/**`;
- `opa check --strict` и `opa test` при изменениях `ops/policy/**`;
- package-specific import/boundary checks на touched Python areas.

### 10.3 Scheduled full gate

Ночью или по отдельному workflow:

- full `ruff check`
- full `ruff format --check`
- full Markdown/YAML/TOML/shell sweep
- full `actionlint`
- repo-wide ratchet reports
- full basedpyright run по curated or baselined surface

## 11. Quality bar для директории

Директория считается "закрытой" только если одновременно выполнено:

1. formatter green;
2. linter green;
3. type checker green там, где он применим;
4. package-specific architecture/import gates green;
5. owning tests green;
6. нет новых blanket ignore / noqa / pyright-ignore / eslint-disable без причины;
7. generated artifacts либо не тронуты, либо регенерированы канонической командой.

## 12. Риски и как их не превратить в болото

| Риск                                                   | Что делать                                           |
| ------------------------------------------------------ | ---------------------------------------------------- |
| Один гигантский cleanup PR                             | Жестко резать работу на batch units из раздела 8     |
| Конфликты из-за общих конфигов                         | Сначала Phase 0, потом распараллеливание             |
| Ложный сигнал от type checkers на старом коде          | baseline/rachet, а не массовые ignore-комментарии    |
| Markdown churn на research docs                        | archive lint-only, без auto-reflow                   |
| Generated files снова ломают format-check              | generator commands обязаны форматировать output сами |
| `tools/**` и shell wrappers выпадают из общей политики | отдельный tools/scripts workstream с shell gates     |
| Cleanup случайно ломает package boundaries             | boundary/import checks являются acceptance criteria  |

## 13. Рекомендуемый фактический порядок запуска работ

### Шаг 1. Один serial PR

- Phase 0 foundation contracts

### Шаг 2. Сразу после него параллельно

1. `apps/runtime-dashboard`
2. `docs + top-level prose`
3. `architecture + release + release-fragments + schemas`
4. `.github + ops`
5. `tools/lib + tools/devx/workspace + scripts`
6. `src/polisyos/common + tests/unit/common`
7. `benchmarks`

### Шаг 3. После merge `common`

1. `ir`
2. продолжение tools sublanes

### Шаг 4. После merge `ir`

1. `core`

### Шаг 5. После merge `core`

Параллельно:

1. `data_forge + legacy data packages`
2. `fabric`
3. `lex`
4. `scholar`
5. `foundry`

### Шаг 6. После стабилизации доменных слоев

1. `scientist`
2. `runtime`
3. `synthetic_world`, `calibration`

## 14. Конкретные выходные артефакты плана

После реализации этого плана в репозитории должны существовать:

- root formatting/lint policy files для всех релевантных типов файлов;
- documented exclude registry;
- canonical `polisyos-tools` / `tools/devx/workspace` wrappers;
- basedpyright baseline strategy;
- directory status board: какие зоны уже "green and ratcheted";
- CI split на fast changed-scope и full scheduled sweeps.

### 14.1 Closeout status на 2026-04-24

Закрыто текущей closeout-волной:

- `workspace docs-style` доведен до зеленого authored Markdown scope без
  переписывания `docs/archive/**`.
- `workspace format-check --skip-frontend --skip-rego` доведен до зеленого
  Python/shell/TOML formatter scope.
- `workspace lint-fast --skip-frontend --skip-docs` доведен до зеленого
  backend fast gate.
- `lint-fast` отделяет Phase 8 benchmark/research Python от strict Ruff pass и
  направляет его в `workspace benchmark-surfaces`.
- `format-check`, `lint-fast` и `lint-full` знают все frontend workspaces:
  `runtime-dashboard`, `runtime-api-client`, `runtime-reference-shell`.
- `lint-full` включает frontend type/architecture checks, `runtime-surface`,
  `benchmark-surfaces`, Helm и Rego gates.
- Добавлен `.github/workflows/repository-hygiene.yml` с PR fast job и
  scheduled/workflow_dispatch full job.
- `docs/reference/repository-hygiene.md` синхронизирован с фактическим
  basedpyright include scope и получил directory status board.

Оставшаяся работа не блокирует canonical fast gate, но должна выжигаться
отдельными owner-волнами:

- снять Ruff ratchet entries с `tools/ops/**`, `tools/quality/**`,
  `tools/devx/**`, `tests/**`, `calibration` и `synthetic_world`;
- перевести Phase 8 benchmark/research surfaces с limited contract на более
  строгий directory-by-directory режим, когда исследовательские API стабилизируются;
- прогнать `repository-hygiene.yml` через `workflow_dispatch` в GitHub перед
  переводом плана из `active` в `archive`.

## 15. Внешние best-practice источники

Ниже официальные источники, на которые опирается этот план:

- Ruff configuration and formatter:
  [docs.astral.sh/ruff/configuration](https://docs.astral.sh/ruff/configuration/),
  [docs.astral.sh/ruff/formatter](https://docs.astral.sh/ruff/formatter/)

- mypy daemon:
  [mypy.readthedocs.io/en/stable/mypy_daemon.html](https://mypy.readthedocs.io/en/stable/mypy_daemon.html)

- basedpyright baseline:
  [docs.basedpyright.com/dev/benefits-over-pyright/baseline](https://docs.basedpyright.com/dev/benefits-over-pyright/baseline/)

- typescript-eslint typed linting:
  [typescript-eslint.io/getting-started/typed-linting](https://typescript-eslint.io/getting-started/typed-linting/)

- ESLint flat config:
  [eslint.org/docs/latest/use/configure/configuration-files](https://eslint.org/docs/latest/use/configure/configuration-files)

- Prettier CLI and ignore policy:
  [prettier.io/docs/next/cli](https://prettier.io/docs/next/cli/),
  [prettier.io/docs/next/ignore](https://prettier.io/docs/next/ignore/)

- markdownlint-cli2:
  [github.com/DavidAnson/markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)

- actionlint:
  [github.com/rhysd/actionlint](https://github.com/rhysd/actionlint)

- yamllint:
  [yamllint.readthedocs.io](https://yamllint.readthedocs.io/en/latest/)

- ShellCheck:
  [github.com/koalaman/shellcheck](https://github.com/koalaman/shellcheck)

- shfmt:
  [github.com/mvdan/sh](https://github.com/mvdan/sh)

- Taplo:
  [taplo.tamasfe.dev/cli/usage/formatting.html](https://taplo.tamasfe.dev/cli/usage/formatting.html)

- OPA style guide and policy testing:
  [openpolicyagent.org/docs/style-guide](https://www.openpolicyagent.org/docs/style-guide),
  [openpolicyagent.org/docs/latest/policy-testing](https://www.openpolicyagent.org/docs/latest/policy-testing/)

- Helm lint:
  [helm.sh/docs](https://docs.helm.sh/docs)

## 16. Итоговый тезис

Самая важная идея этого плана: репозиторий нужно чистить не "по инструментам",
а по независимым рабочим поверхностям.

Foundation делается один раз. После этого:

- frontend,
- docs/config surfaces,
- ops/policy-as-code,
- tools shared substrate,
- Python lower layers,
- Python domain layers,
- Python consumer layers

идут как отдельные параллельные треки с очень редкими и явно обозначенными
точками синхронизации.
