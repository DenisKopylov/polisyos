# Установка

> Варианты source-установки, extras и troubleshooting для текущего дерева.

!!! info "Проверенная поверхность установки"
    Канонический contributor path для текущего дерева:
    `python3 -m tools.cli workspace bootstrap` ->
    `python3 -m tools.cli workspace doctor` ->
    `python3 -m tools.cli workspace verify`.
    По состоянию на 2026-04-03 этот путь был проверен на macOS с Python 3.14
    и Node 22.

## Canonical Contributor Path

Из корня `policy-engine/`:

```bash
python3 -m tools.cli workspace bootstrap
python3 -m tools.cli workspace doctor
python3 -m tools.cli workspace verify
python3 -m tools.cli workspace ci-parity --skip-browser
```

Что делает этот путь:

- фиксирует Python baseline на `3.14.x`;
- фиксирует Node baseline на `22.x`;
- использует `uv 0.9.21` как канонический Python environment manager;
- проверяет Playwright, lockfiles и generated contract artifacts;
- подготавливает backend и frontend contributor toolchains.

## Contributor Tiers

| Tier | Команда | Когда выбирать |
|---|---|---|
| Minimal contributor | `python3 -m tools.cli workspace bootstrap --profile minimal --skip-frontend` | Core Python, lint, unit/property tests |
| Docs contributor | `python3 -m tools.cli workspace bootstrap --profile docs --skip-frontend` | MkDocs, docstring quality, docs accuracy |
| Runtime contributor | `python3 -m tools.cli workspace bootstrap --profile runtime --skip-frontend` | Runtime API, contracts, backend workflows |
| Full research / causal contributor | `python3 -m tools.cli workspace bootstrap --profile research --skip-frontend` | Causal / Foundry / Scientist heavy workflows |
| Frontend contributor | `python3 -m tools.cli workspace bootstrap --profile runtime` | Runtime contributor Python surface плюс `npm ci --ignore-scripts` для dashboard |

## Версия Python

В текущем `pyproject.toml` Python 3.14 зафиксирован как единственный поддерживаемый
minor baseline:

```bash
python3.14 --version
```

Ожидаемый вывод:

```text
Python 3.14.x
```

## Editable Package Install

Для самого маленького source-install можно использовать любую из этих эквивалентных команд:

```bash
pip install -e "."
```

```bash
pip install -e ".[core]"
```

Что это даёт:

- пакет из `src/polisyos`
- IR types и core contracts
- базовый runtime, connector и CLI код из основного набора зависимостей

## Полная capability-установка

Для широкого capability-окружения используйте curated umbrella extra:

```bash
pip install -e ".[all]"
```

Текущий `all` включает такие проверенные семейства:

- `research`
- `hotreload`
- `rag`
- `runtime`
- `security`
- `shapesafe`

Почему `all` — именно curated umbrella, а не буквально “всё подряд”:

- часть optional-путей всё ещё тяжёлая или platform-specific
- часть extras требует внешних prerequisites, а не только `pip`-резолвера
- curated `all` избавляет новых разработчиков от долгого resolver backtracking
- contributor tooling (`lint`, `docs`, `test`, notebooks, mutation) вынесен отдельно и не смешивается с product-capability umbrella

## Конкретные extras

Авторитетный список находится в `[project.optional-dependencies]` в `pyproject.toml`.

| Extra | Что добавляет | Для чего использовать |
|-------|---------------|-----------------------|
| `core` | Пустой compatibility extra для минимального source-install | Базовый smoke и core contracts |
| `lint` | `mypy`, `pre-commit`, `ruff`, `types-requests` | Contributor lint/type surface |
| `docs` | `mkdocs`, `mkdocs-material`, `mkdocstrings[python]` | Docs site и docs quality |
| `notebooks` | `jupyterlab`, `matplotlib`, `seaborn` | Notebook/research authoring |
| `mutation` | `mutmut` | Mutation testing |
| `runtime` | `runtime-http` + observability + structured logging | Backend contributor umbrella |
| `research` | Method stacks + causal discovery/full + academic helpers | Full research / causal umbrella |
| `analytics` | `scipy`, `statsmodels`, `linearmodels`, `pandas`, `ruptures`, `arch` | Econometrics и structural analytics |
| `ml` | `scikit-learn`, `lifelines`, `mapie` | ML-методы |
| `deep-learning` | Compatibility alias | JAX already lives in base install |
| `apple-metal` | `jax-metal` на macOS | Opt-in Apple Metal acceleration |
| `bayesian` | `numpyro`, `arviz` | Bayesian workflows |
| `sensitivity` | `SALib`, `scipy` | Sensitivity analysis |
| `causal` | `causal-core` плюс `causal-dowhy` | Удобный high-level causal shortcut |
| `causal-core` | `econml` только на Python `<3.14` | EconML-based causal estimation |
| `causal-dowhy` | `dowhy`, `cvxpy<1.5` только на Python `<3.13` | Совместимость с DoWhy |
| `causal-bcf` | `stochtree` | Bayesian Causal Forest и BCF-like workflows |
| `causal-discovery` | `tigramite`, `causal-learn` | PC, FCI и другие discovery-алгоритмы |
| `causal-discovery-scale` | `dagma` | DAGMA-based discovery |
| `causal-symbolic` | `y0` | Symbolic identification |
| `causal-symbolic-r` | `rpy2` | R-backed symbolic workflows |
| `causal-full` | `econml`, `dowhy`, `lightgbm`, `zepid`, `y0` с version gates | Широкий causal stack |
| `optimization-advanced` | `cvxpy>=1.8.1` | Advanced optimization |
| `solvers` | `ortools`, `pulp` | Planning и optimization backends |
| `runtime-http` | `fastapi`, `uvicorn[standard]`, `httpx`, `PyJWT` | Runtime API и dashboard |
| `observability` | `prometheus-client` поверх base OTel stack | Tracing и metrics |
| `multi-tenant` | `runtime-http` + PostgreSQL drivers | Tenant-aware runtime paths |
| `security` | `boto3`, `sigstore`, `presidio-*`, `spacy` | Auth, privacy и security workflows |
| `rag` | `faiss-cpu` | Local retrieval index |
| `rag-local` | `sentence-transformers`, `onnxruntime` | Local embeddings и search |
| `table-extraction` | `marker-pdf` | Heavyweight extraction / PDF research flows |
| `agent-sim` | `plotly`, `streamlit` | Optional visualization/dashboard helpers |
| `sandbox` | `RestrictedPython` | Эксперименты с sandbox execution |
| `shapesafe` | `beartype` | Runtime type и shape guards |
| `hotreload` | `watchfiles` | Локальный auto-reload |
| `structured-logging` | `structlog` | Structured runtime logging |
| `dev` | `lint` + `docs` + notebooks + mutation + structured logging | Broad local authoring tooling |
| `test` | pytest stack плюс `runtime-http` | Тестовые зависимости |
| `all` | Curated product-capability umbrella | Широкая feature-поверхность без local-only tooling |

Примечания:

- Frontend contributor path всегда требует ещё и `cd frontend/runtime-dashboard && npm ci --ignore-scripts`.
- `causal-core` специально ограничен Python `<3.14`, потому что `econml` пока не даёт чистого 3.14-пути в проверенном docs-окружении.
- `causal-bcf` остаётся opt-in, потому что `stochtree` обычно требует OpenMP на хосте.
- `apple-metal` остаётся opt-in: CPU baseline считается support path даже на Apple Silicon.

## Manual Contributor Setup

Для полного contributor-окружения:

```bash
uv sync --frozen --extra lint --extra test --extra runtime
uv run pre-commit install
cd frontend/runtime-dashboard && npm ci --ignore-scripts && npm run playwright:install
```

Если хотите более узкий набор, используйте один из tiered profiles:

```bash
python3 -m tools.cli workspace bootstrap --profile minimal --skip-frontend
python3 -m tools.cli workspace bootstrap --profile docs --skip-frontend
python3 -m tools.cli workspace bootstrap --profile research --skip-frontend
```

## Devcontainer And Cache Strategy

Hermetic local path:

```bash
code policy-engine
# Dev Containers: Reopen in Container
```

Конфигурация живёт в `policy-engine/.devcontainer/devcontainer.json`.

Cache policy:

- `uv`: volume-backed cache at `/home/vscode/.cache/uv` in the devcontainer;
- npm: volume-backed cache at `/home/vscode/.npm`;
- Playwright browsers: volume-backed cache at `/home/vscode/.cache/ms-playwright`;
- benchmark artifacts: dedicated volume mounted to `.benchmarks/`.

Локальная CI-подобная проверка:

```bash
python3 -m tools.cli workspace ci-parity --skip-browser
```

Для browser-backed parity-поверхности:

```bash
python3 -m tools.cli workspace ci-parity --include-e2e-smoke --include-visual
```

## Troubleshooting

### JAX на CPU, GPU и Metal

- На macOS Metal backend теперь opt-in через `.[apple-metal]`.
- В upstream setup guides этот путь также может называться `jax[metal]`.
- Если workload падает с ошибкой Metal runtime, например `default_memory_space is not supported`, принудительно переключите JAX на CPU:

```bash
export JAX_PLATFORM_NAME=cpu
export JAX_PLATFORMS=cpu
```

- Для smoke-прогонов документации и onboarding CPU-режим на Apple Silicon сейчас самый надёжный.

### Особенности Apple Silicon

- Если нужен именно GPU backend от Apple, рассчитывайте на дополнительную Metal-specific настройку.
- Для `causal-bcf` может потребоваться предварительно поставить OpenMP:

```bash
brew install libomp
```

- Некоторые native packages, например `grpcio`, могут требовать актуальные Xcode command line tools.

### Отсутствующие системные зависимости

Держите packaging toolchain в актуальном состоянии:

```bash
python -m pip install --upgrade pip setuptools wheel
```

На macOS:

```bash
xcode-select --install
```

### Конфликты resolver’а

- Если не знаете, с чего начать, используйте `.[all]`.
- Тяжёлые extras вроде `security`, `rag-local`, `table-extraction`, `agent-quality` или `causal-bcf` ставьте явно по мере необходимости.
- Если causal stack конфликтует на Python 3.14, сначала проверьте, не тянет ли выбранный extra `econml` или старые compatibility pins для `dowhy`.

### Только source-установка

- Для этого репозитория сейчас не описан PyPI package path.
- Поддерживаемый contributor path начинается с
  `python3 -m tools.cli workspace bootstrap`; `pip install -e ...`
  остаётся допустимым только как ручной editable package install.
