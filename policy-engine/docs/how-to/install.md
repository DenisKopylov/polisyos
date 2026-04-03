# Установка

> Варианты source-установки, extras и troubleshooting для текущего дерева.

!!! info "Проверенная поверхность установки"
    Сейчас этот репозиторий поддерживает установку только из исходников.
    По состоянию на 2026-04-03 обе команды `pip install -e ".[core]"`
    и `pip install -e ".[all]"` были реально проверены на macOS с Python 3.14
    в свежих окружениях.

## Версия Python

В текущем `pyproject.toml` Python 3.14 уже зафиксирован как минимально поддерживаемая версия:

```bash
python3.14 --version
```

Ожидаемый вывод:

```text
Python 3.14.x
```

## Минимальная установка

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

## Полная установка

Для полного окружения, на котором проверялись tutorial/how-to страницы, используйте curated umbrella extra:

```bash
pip install -e ".[all]"
```

Текущий `all` включает такие проверенные семейства:

- `analytics`
- `bayesian`
- `causal-discovery`
- `causal-discovery-scale`
- `causal-full`
- `hotreload`
- `ml`
- `observability`
- `optimization-advanced`
- `runtime-http`
- `sensitivity`
- `shapesafe`
- `solvers`
- `structured-logging`

Почему `all` — именно curated umbrella, а не буквально “всё подряд”:

- часть optional-путей всё ещё тяжёлая или platform-specific
- у некоторых upstream зависимостей пока нет чистого Python 3.14 пути
- curated `all` избавляет новых разработчиков от долгого resolver backtracking

## Конкретные extras

Авторитетный список находится в `[project.optional-dependencies]` в `pyproject.toml`.

| Extra | Что добавляет | Для чего использовать |
|-------|---------------|-----------------------|
| `core` | Пустой compatibility extra для минимального source-install | Базовый smoke и core contracts |
| `analytics` | `scipy`, `statsmodels`, `linearmodels`, `pandas`, `ruptures`, `arch` | Econometrics и structural analytics |
| `ml` | `scikit-learn`, `lifelines`, `mapie` | ML-методы |
| `deep-learning` | `jax`, `jaxlib` | JAX-based вычисления |
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
| `observability` | OpenTelemetry и Prometheus dependencies | Tracing и metrics |
| `security` | `boto3`, `sigstore`, `presidio-*`, `spacy` | Auth, privacy и security workflows |
| `rag` | `faiss-cpu` | Local retrieval index |
| `rag-local` | `sentence-transformers`, `onnxruntime` | Local embeddings и search |
| `sandbox` | `RestrictedPython` | Эксперименты с sandbox execution |
| `shapesafe` | `beartype` | Runtime type и shape guards |
| `hotreload` | `watchfiles` | Локальный auto-reload |
| `structured-logging` | `structlog` | Structured runtime logging |
| `dev` | lint, types, docs, notebooks, plotting, pre-commit | Development tools |
| `test` | pytest stack плюс `runtime-http` | Тестовые зависимости |
| `all` | Curated umbrella для docs/onboarding | Рекомендуемая полная установка |

Примечания:

- Extras `[deep]` в текущем файле нет. Правильное имя — `[deep-learning]`.
- `causal-core` специально ограничен Python `<3.14`, потому что `econml` пока не даёт чистого 3.14-пути в проверенном docs-окружении.
- `causal-bcf` остаётся opt-in, потому что `stochtree` обычно требует OpenMP на хосте.

## Установка для разработки

Для полного contributor-окружения:

```bash
pip install -e ".[dev,test,all]"
pre-commit install
```

Если хотите более узкий набор, начните с `.[dev,test]` и добавляйте только нужные extras.

## Troubleshooting

### JAX на CPU, GPU и Metal

- На macOS текущее дерево уже включает `jax-metal`.
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
- Поддерживаемый путь — клонировать репозиторий и ставить из исходников через `pip install -e ...`.
