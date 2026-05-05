# Установка

> Канонические contributor paths для текущего дерева после refactor: выберите
> профиль, выполните bootstrap, затем `doctor` и `verify`.

!!! info "Validated against current command surface"
2026-04-17 на локальном macOS workstation были проверены
`uv run polisyos-tools workspace bootstrap --help`,
`uv run polisyos-tools workspace doctor --help`,
`uv run polisyos-tools workspace verify --help`,
`uv run polisyos-tools workspace ci-parity --help`,
а также `uv run polisyos-tools workspace doctor --list-surfaces`.
Сами install-команды ниже mutating и остаются manual/conceptual steps.

## Inputs

- checkout `policy-engine/`;
- Python `3.14.x`;
- Node `22.x`;
- `uv`;
- решение, нужен ли вам frontend и Playwright на этой машине.

## Outputs

- локальное Python-окружение, соответствующее выбранному профилю;
- при необходимости установленный dashboard toolchain;
- понятный путь к `doctor`, `verify` и `ci-parity`.

## Commands

```bash
cd policy-engine
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace doctor
uv run polisyos-tools workspace verify
```

## Канонический выбор профиля

| Профиль    | Когда брать                                    | Команда                                                                                      |
| ---------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `minimal`  | core Python, lint, быстрые unit/property tests | `uv run polisyos-tools workspace bootstrap --profile minimal --skip-frontend`                |
| `docs`     | MkDocs, docs accuracy, docstring quality       | `uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-playwright` |
| `runtime`  | backend/runtime/API work, default path         | `uv run polisyos-tools workspace bootstrap --profile runtime`                                |
| `research` | causal, Foundry, Scientist heavy workflows     | `uv run polisyos-tools workspace bootstrap --profile research --skip-frontend`               |

Если вы не уверены, начинайте с `runtime`.

## Рекомендуемый install path

Из корня `policy-engine/`:

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace doctor
uv run polisyos-tools workspace verify
```

Что делает этот путь:

- фиксирует поддерживаемый baseline из
  [Environment Matrix](../reference/environment-matrix.md);

- использует `uv` как canonical Python environment manager;
- проверяет lockfiles, generated-contract surfaces и optional env surfaces;
- подготавливает backend и, если вы не отключили frontend, dashboard toolchain.

## Быстрые варианты

### Backend-only onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile runtime --skip-frontend --skip-playwright
uv run polisyos-tools workspace doctor --skip-playwright
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

### Docs-only onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile docs --skip-frontend --skip-playwright
uv run polisyos-tools workspace doctor --skip-playwright --skip-contract-checks
uv run polisyos-tools workspace ci-parity --skip-browser
```

### Frontend onboarding

```bash
uv run polisyos-tools workspace bootstrap --profile runtime
uv run polisyos-tools workspace verify --frontend-only --skip-doctor
cd frontend/runtime-dashboard
npm run generate:api
npm run contracts:verify
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

Для frontend после manual path все равно нужен npm install:

```bash
cd frontend/runtime-dashboard
npm ci --ignore-scripts
npm run playwright:install
```

## Проверка результата

Минимальные проверки:

```bash
uv run polisyos --version
uv run polisyos-tools workspace doctor --list-surfaces
uv run polisyos-tools workspace verify --backend-only --skip-doctor
```

Если вы меняете runtime contract surface:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
```

Если вы меняете docs surface:

```bash
uv run --extra docs python -m mkdocs build --strict
```

## Rollback / cleanup

Если профиль оказался слишком тяжелым или не тем:

1. удалите локальное окружение `.venv` или другой venv, который вы создали;
2. если bootstrap тянул frontend зря, удалите `frontend/runtime-dashboard/node_modules`;
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

На 2026-04-17 доступны:

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

Но перед PR вернитесь к полному `doctor` или `ci-parity`.
