# Установка

Freshness: 2026-10-14
Owner: `@platform-owners`
Source of truth: `CONTRIBUTING.md`, `docs/reference/environment-matrix.md`, `pyproject.toml`,
`.python-version`, `.nvmrc`, `package.json`, `tools/devx/workspace/_common.py`,
`tools/devx/workspace/bootstrap.py`, `tools/devx/workspace/doctor.py`, `tools/registry.py`,
`.pre-commit-config.yaml`.

!!! info "Historical command-surface receipt (2026-04-17)"
На локальном macOS workstation были проверены
`uv run polisyos-tools workspace bootstrap --help`,
`uv run polisyos-tools workspace doctor --help`,
`uv run polisyos-tools workspace verify --help`,
`uv run polisyos-tools workspace ci-parity --help`,
а также `uv run polisyos-tools workspace doctor --list-surfaces`. Это историческое
наблюдение доступности команд в конкретной среде, а не результат запуска текущего
bootstrap или проверки на свежем checkout. Команды установки ниже меняют локальное
окружение.

Команды ниже перечислены по текущим source entrypoints в `pyproject.toml` и
`tools/registry.py`; эта доступность не является receipt успешного запуска. Успешное
выполнение на машине утверждает только датированная историческая запись выше.

## Inputs

- checkout `policy-engine/`;
- Python `3.14.x`;
- `uv 0.9.21`;
- Node `22.x` для `docs-style` и frontend workflows;
- для frontend workflow и стандартных `doctor` lockfile/contract checks — Corepack и pnpm
  `10.33.2` (версию pnpm задает `package.json`);
- решение, нужен ли вам frontend и Playwright на этой машине.

Профили bootstrap задают только Python extras: `minimal` = `lint + test`, `docs` =
`lint + docs`, `runtime` = `lint + test + runtime`, `research` = `lint + test + runtime +
research`. Bootstrap по умолчанию также устанавливает pre-commit hooks, frontend workspace
и Playwright browsers, затем запускает `doctor`; флаги ниже позволяют пропустить эти шаги.

## Outputs

- локальное Python-окружение, соответствующее выбранному профилю;
- при необходимости установленный dashboard toolchain;
- понятный путь к `doctor`, `verify` и `ci-parity`.

## Commands

Полный runtime-путь устанавливает зависимости и запускает `doctor` в конце bootstrap;
`verify --skip-doctor` запускает fast contributor gate без повторного workstation preflight.

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --skip-doctor
```

## Канонический выбор профиля

| Профиль    | Когда брать                                    | Команда                                                                                      |
| ---------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `minimal`  | core Python, lint, быстрые unit/property tests | `uv run polisyos-tools workspace bootstrap --profile minimal --skip-frontend --skip-doctor`  |
| `docs`     | MkDocs и authored-document checks              | `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-doctor`     |
| `runtime`  | backend/runtime/API work, default path         | `uv run polisyos-tools workspace bootstrap --profile runtime`                                |
| `research` | causal, Foundry, Scientist heavy workflows     | `uv run polisyos-tools workspace bootstrap --profile research --skip-frontend --skip-doctor` |

Если вы не уверены, начинайте с `runtime`.

У `--skip-frontend` есть два эффекта: bootstrap пропускает проверку Node и установку pnpm
workspace. Без `--skip-doctor` последующий `doctor` все равно проверяет Python, Node, `uv`,
Playwright, lockfiles и generated contracts. Флаг bootstrap `--skip-playwright` пропускает
установку браузеров, но не передается автоматически в `doctor`; для browserless bootstrap
используйте `--skip-doctor`, затем запускайте нужные проверки отдельно.

## Рекомендуемый install path

Из корня `policy-engine/`:

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --skip-doctor
```

Что делает этот путь:

- фиксирует поддерживаемый baseline из
  [Environment Matrix](../reference/environment-matrix.md);

- использует `uv` как canonical Python environment manager;
- синхронизирует extras выбранного профиля и по умолчанию устанавливает pre-commit hooks;
- подготавливает frontend и Playwright browsers, если их не отключить;
- запускает `doctor`, если не указан `--skip-doctor`; этот шаг проверяет Node `22.x`, `uv`
  `0.9.21`, Playwright smoke, lockfiles и generated contracts, если проверки не отключены.

## Быстрые варианты

### Backend-only onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-doctor
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

Backend-only профиль не устанавливает Node workspace. Если нужен только базовый workstation
preflight без browser, pnpm lockfile и generated-contract checks, запускайте `doctor` отдельно:

```bash
uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks
```

Даже с этими флагами `doctor` проверяет Python `3.14.x`, Node `22.x` и `uv 0.9.21`.

### Docs-only onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-doctor
uv run polisyos-tools workspace docs-style docs/
uv run --extra docs python -m mkdocs build --strict
uv run polisyos-tools validation check-docs-accuracy --repo-root .
```

Этот профиль ставит только Python extras `lint + docs`; Node/Corepack/pnpm и browser stack
не устанавливаются автоматически. Для `docs-style` нужен Node `22.x`, так как authored
Markdown проверяет Node-based `markdownlint-cli2` hook; Corepack/pnpm и browser stack для
этого targeted docs path не нужны. Если отдельно запускаете полный `doctor`, он снова проверит
Node, lockfiles и generated contracts; browser smoke можно отключить флагом `--skip-playwright`,
а остальные поверхности — соответствующими `--skip-*` флагами.

### Frontend onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --frontend-only --skip-doctor
cd apps/runtime-dashboard
corepack pnpm run generate:api
corepack pnpm run contracts:verify
```

## Manual editable install

Если вам нужен ручной path вместо workspace bootstrap:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e "."
```

Частые варианты extras:

| Extra                            | Когда нужен                                              |
| -------------------------------- | -------------------------------------------------------- |
| `.[core]`                        | самый узкий source-install                               |
| `.[docs]`                        | MkDocs и docs quality                                    |
| `.[runtime]` / `.[runtime-http]` | Runtime API и dashboard contract surface                 |
| `.[test]`                        | pytest stack                                             |
| `.[research]`                    | causal / Scientist / Foundry heavy workflows             |
| `.[all]`                         | curated umbrella для широкого локального feature surface |

Для frontend после manual path нужен Node `22.x` и Corepack с pnpm `10.33.2`:

```bash
corepack pnpm install --frozen-lockfile
cd apps/runtime-dashboard
corepack pnpm run playwright:install
```

В свежем checkout выполните `corepack pnpm install --frozen-lockfile` перед TypeScript
scanner: отсутствие workspace links может дать ложные findings. Bootstrap использует
`--ignore-scripts` при своей установке; эта команда выполняет предписанную fresh-checkout
установку для scanner workflows.

## Проверка результата

Минимальные проверки:

```bash
uv run polisyos --version
uv run polisyos-tools workspace doctor --list-surfaces
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

Если вы меняете runtime contract surface:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
```

Если вы меняете docs surface:

```bash
uv run --extra docs python -m mkdocs build --strict
```

## Rollback / cleanup

Если профиль оказался слишком тяжелым или не тем:

1. удалите локальное окружение `.venv` или другой venv, который вы создали;
2. если bootstrap тянул frontend зря, удалите `apps/runtime-dashboard/node_modules`;
3. повторите bootstrap с более узким профилем и нужными `--skip-*` флагами.

Если вы сознательно не хотите держать browser stack локально, используйте
`--skip-playwright` и оставьте Playwright suites на CI или отдельную машину.

## Troubleshooting

### Python или Node вне поддерживаемой матрицы

- сверяйтесь с [Environment Matrix](../reference/environment-matrix.md);
- неподдерживаемые minor versions сначала считаются unsupported, пока не
  воспроизведут баг на Python `3.14.x` и Node `22.x`.

### Нужен список optional surfaces для `doctor`

```bash
uv run polisyos-tools workspace doctor --list-surfaces
```

Historical list, captured on 2026-04-17:

- `datasets-unpd`
- `frontend-sentry-build`
- `frontend-sentry-runtime`
- `llm-anthropic`
- `llm-openai`
- `runtime-oidc`
- `runtime-research-postgres`
- `runtime-signing`

### Apple Silicon и JAX

- CPU-first path считается поддерживаемым baseline;
- Metal остается opt-in через `apple-metal` extra;
- для первых smoke/tutorial runs используйте CPU, если нет явной причины
  отлаживать Metal.

### Конфликтующие или тяжелые зависимости

- если не уверены, начните с профиля `runtime`, а не со случайной смеси extras;
- causal/research extras добавляйте только когда задача их действительно требует;
- если нужна просто docs или backend surface, не тяните frontend/browser stack без нужды.

### Lockfile, contract или generated-artifact checks мешают локальному triage

Для первого preflight можно временно сузить `doctor`:

```bash
uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks
```

Это оставляет проверки Python, Node и `uv`; перед PR запускайте подходящий scope-specific gate.
`ci-parity --skip-browser` — широкая CI-parity проверка, а не короткая проверка для docs-only
изменений.
