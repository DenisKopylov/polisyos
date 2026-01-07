# Architecture (as-is → target) for `polisyos/policy-engine`

Этот документ фиксирует **текущую карту** проекта (as‑is) и **целевую архитектуру** (to‑be), а также **операционный план аудита** как серии маленьких PR.  
Код не менялся: это снимок/анализ текущего состояния репозитория на момент написания.

---

## 0) Непереговорные законы системы (инварианты)

### Закон A. Граф зависимостей только внутрь

**Целевая зависимость по слоям (пакетам):**

- `scientist` → {`ir`, `fabric`, `foundry`}
- `fabric` → {`ir`}
- `foundry` → {`ir` **(только типы/контракты)**; ничего про БД/LLM}
- `ir` → никого

Определение “зависимости”: **runtime‑import** (включая `from ... import ...`).  
`TYPE_CHECKING`‑импорты считаем “подозрительными”: они не ломают runtime, но часто закрепляют неправильные границы.

### Закон B. Ты строишь компилятор

Целевая труба:

`NL` → `LLM` → `IR (AST)` → `Compilation` → `Runtime (UDF + Foundry)` → `Artifacts / DecisionPacket`

- Runtime **не знает про LLM**.
- `IR` **не знает** про JAX/DuckDB/Kùzu/LangGraph.
- Это “frontend / IR / backend”, а не “папка со скриптами”.

### Закон C. Контракты — единственный источник истины

Если поле/сущность не описаны в **канонической Pydantic‑схеме** соответствующего артефакта — значит их “не существует”.

Следствия:

- Любой артефакт (IR, manifests, run passport, decision packet) имеет `schema_version`.
- Есть миграции `vX -> vY` (детерминированные преобразования).
- Есть экспорт JSON Schema как build‑артефакт.

### Закон D. Любой прогон — воспроизводим и аудируем

Фиксируются: `run_id`, `seed`, `repro_mode`, backend, версии библиотек, флаги, промпты, диффы self‑healing, артефакты и статус финализации.

---

## 1) As‑is: текущая структура репозитория

### 1.1. Физическая структура

В корне репозитория сейчас один проект: `policy-engine/`.

Ключевые элементы в `policy-engine/`:

- Много “ручных гейтов”/скриптов: `tools/diagnostics/*`, `tools/demos/*`, `tools/benchmarks/*`, `run_experiment.py`, `migrate.py`, `jax_bootstrap.py`, `dashboard.py`.
- Данные и локальные артефакты: `data/`, `*.duckdb`, `*.kuzu`, `logs/`, `policy_ir_schema.json`.
- Исходники: `policy-engine/src/` (важно: **пакет называется `src`**, и импорты вида `from src....`).  
  Отдельно: `policy-engine/src/__init__.py` при импорте вызывает `apply_jax_env_defaults()` (side‑effect на env для JAX); похожая логика есть в `policy-engine/jax_bootstrap.py`.
- Тесты: `policy-engine/tests/` (сейчас в основном foundry/JIT‑стабильность).

### 1.2. Логическая структура модулей (роль → где живёт)

Ниже — “карта ответственности” по пакетам внутри `policy-engine/src/` (as‑is):

#### `src/policy_ir/` (контракты IR)

- `policy-engine/src/policy_ir/contract.py`: **`PolicyRequestIR`**, `TargetSelector` (AST), лимиты размеров/глубины, валидация графа сущностей.
- `policy-engine/src/policy_ir/mechanism_spec.py`: `MechanismSpec` + глобальный `MECHANISM_SPECS` (whitelist и ranges/units для параметров).
- `policy-engine/src/policy_ir/units.py`: `UNIT_REGISTRY`.
- Плюс `types.py`, `base.py`.

Замечания:

- `policy-engine/src/policy_ir/types.py` уже поддерживает алиасы `En/Ua/Ru → en/ua/ru` через `validation_alias=AliasChoices(...)` и включает `populate_by_name=True` (канонические ключи в сериализации — lowercase).
- `policy-engine/src/policy_ir/base.py` выглядит как legacy/черновик (Pydantic v1‑style `class Config`, `__main__` demo) и не очевидно участвует в основной трубе.
- IR сейчас **сам** делает mechanism‑specific валидацию через `get_mechanism_spec(...)`, что связывает IR с “каталогом механизмов” (см. red list).

#### `src/foundry/` (JAX ядро механизмов)

- `policy-engine/src/foundry/base.py`: абстракция `Mechanism(eqx.Module)`; `fidelity`, `debug_mode`, `invariants()`.
- `policy-engine/src/foundry/fiscal.py`: `TaxSubsidy`, `IncomeTax` (и др. механизмы).
- `policy-engine/src/foundry/queue.py`: механизм очереди + fidelity gap.
- `policy-engine/src/foundry/loss.py`, `utils.py`, `basic_simulation.py`, `types.py`.

Замечание: foundry импортирует состояние из `src/domain/state.py` (см. ниже), т.е. “домен” сейчас физически вынесен в отдельный пакет.

#### `src/domain/` + `src/engine/` (runtime‑физика/экономика)

- `policy-engine/src/domain/state.py`: JAX/chex dataclasses: `GlobalState`, `AgentState`, `FirmState`, `MarketState`.
- `policy-engine/src/engine/kernel.py`: `SimulationKernel` (jit шаг экономического цикла).
- `policy-engine/src/engine/logic.py`: функции рынка/производства/потребления (экономическая динамика).

Это уже выглядит как “runtime backend” (foundry+engine), но границы не зафиксированы как слой.

#### `src/fabric/` + `src/io/` + `src/udf/` (данные и Unified Data Fabric)

Сейчас функциональность fabric разнесена на 3 пакета:

- `policy-engine/src/fabric/ingestion.py`: CSV → validate(Pydantic rows) → parquet → загрузка в DuckDB/Kùzu → manifest JSON.
- `policy-engine/src/io/db.py`: `SimulationDB` (DuckDB, таблицы, save_macro, save_run_record).
- `policy-engine/src/io/graph_store.py`: `GraphStore` (Kùzu, схема графа, query).
- `policy-engine/src/udf/schema.py`: `DataViewRequest`, `DataViewType`, `AccessTier`, `DataFilter`.
- `policy-engine/src/udf/compiler.py`: `ViewCompiler` (DataViewRequest → SQL, whitelist, PII tier).
- `policy-engine/src/udf/engine.py`: `UDFEngine` (DuckDB + Kùzu) и компиляция запросов.

Замечания:

- `policy-engine/src/udf/config.py` уже реализует “schema‑driven whitelist”: `ALLOWED_COLUMNS`, `FIELD_CLASSIFICATION`, `ALLOWED_RELATION_TYPES` грузятся из `data/curated/udf_schema.json` (или `UDF_SCHEMA_PATH`), т.е. PII tiers и допустимые поля уже существуют в виде прототипа.
- `DataViewRequest` **не часть IR**, а живёт в `udf/`. Инициализация состояния в `orchestrator/data_loader.py` сейчас **обходит** UDF через сырой SQL‑строкой.

#### `src/orchestrator/` + `src/agent/` (scientist: LLM + workflow)

Два “контрольных центра” параллельно:

1) **LangGraph‑workflow (draft → simulate → governor)**:

- `policy-engine/src/orchestrator/workflow.py`: `StateGraph(ExperimentState)` с узлами.
- `policy-engine/src/agent/drafter.py`: `drafter_node` (MockLLM → JSON → `PolicyRequestIR`).
- `policy-engine/src/orchestrator/nodes.py`: `simulator_node` (UDF + JAX + оптимизация + запись артефактов), `governor_node`.

2) **Ручной цикл эксперимента**:

- `policy-engine/run_experiment.py`: perception(UDF) → decision(MockAgent) → compilation(compile_policy) → apply policy + engine step → persistence(DuckDB).

Артефакты/аудит:

- `policy-engine/src/orchestrator/run_record.py`: `RunRecord` (seed, backend, версии, флаги).
- `policy-engine/src/orchestrator/decision_packet.py`: `DecisionPacket` (IR + результаты + audit + RunRecord).
- `policy-engine/src/orchestrator/audit.py`: append-only audit trail.

Замечания:

- В `policy-engine/src/agent/` есть два похожих генератора промптов: `prompt.py` (только schema) и `prompts.py` (schema + механизм‑лист), что повышает риск “расхождения фронтенда”.
- Артефакты сейчас пишутся напрямую в `policy-engine/logs/` (`logs/run_records`, `logs/decision_packets`) без единого `runtime` API.

### 1.3. Существующие гейты/проверки (as‑is)

Сейчас часть “архитектурных гейтов” уже есть, но в виде скриптов/pytest и без единой классификации:

- **IR / contracts:** `policy-engine/tools/diagnostics/generate_ir_schema.py` генерирует `policy_ir_schema.json`; контракты — `policy-engine/tests/contract/test_ir_contract.py`.
- **Compiler boundary:** `policy-engine/tests/scientist/test_compiler.py` собирает `PolicyRequestIR → compile_policy() → foundry mechanism` и проверяет сохранность параметров.
- **Foundry / gradients:** `policy-engine/tests/foundry/test_gradients.py` делает sanity‑check градиента (eqx + jax).
- **Integration (real DB):** `policy-engine/tests/integration/test_workflow_smoke.py` прогоняет workflow на baseline в DuckDB.
- **Фискальная физика/движок:** `policy-engine/tests/foundry/test_fiscal.py`, `policy-engine/tests/foundry/test_production_kernel.py`.
- **Pytest:** `policy-engine/tests/foundry/test_jit_stability.py`, `policy-engine/tests/foundry/test_health.py` (JIT‑стабильность PyTree, fidelity gap).
- **Migrations:** `policy-engine/src/migrations/*` + CLI `policy-engine/migrate.py` (пока миграции частично заглушки).

---

## 2) As‑is: текущая “компиляторная” труба (фактически)

### 2.1. Труба A: LangGraph workflow

`user_request` → `agent/drafter.py` → `PolicyRequestIR` → `orchestrator/nodes.py`:

- загрузка baseline состояния из БД,
- применение механизмов (и “оптимизация” параметров),
- запись `RunRecord` + `DecisionPacket`,
- governor verdict (`APPROVE | NEEDS_REVISION | REJECT`).

### 2.2. Труба B: `run_experiment.py` loop

`UDF.query(DataViewRequest)` → `MockAgent.decide()` → `PolicyRequestIR` → `compile_policy()` → `foundry` + `engine` → сохранение макро‑метрик в DuckDB.

**Следствие:** сейчас существуют **две архитектуры orchestration**, которые расходятся по контрактам и по точкам записи артефактов.

---

## 3) As‑is: граф зависимостей (фактический снимок)

### 3.1. Сводка зависимостей по целевым слоям (грубое сопоставление)

Чтобы сравнить с Законом A, пакеты as‑is сопоставлены слоям:

- `scientist`: `src/orchestrator/`, `src/agent/`
- `ir`: `src/policy_ir/`
- `foundry`: `src/foundry/`, `src/domain/`, `src/engine/`
- `fabric`: `src/fabric/`, `src/udf/`, `src/io/`
- `common`: `src/utils/`, `src/migrations/`

Фактические групповые зависимости (imports):

- `scientist → foundry` (есть)
- `scientist → ir` (есть)
- `scientist → fabric` (есть)
- `fabric → common` (есть)
- **`fabric → scientist` (type‑only утечка через `TYPE_CHECKING` в `policy-engine/src/io/db.py`; runtime‑зависимость не создаёт, но фиксирует неверную границу)**  

### 3.2. Явные циклы импортов (as‑is)

Циклы, обнаруженные по runtime‑импортам `src.<pkg>.*`:

- **`agent ↔ orchestrator`**  
  Причина:  
  - `policy-engine/src/orchestrator/workflow.py` импортирует `agent/drafter.py`  
  - `policy-engine/src/agent/prompts.py` импортирует `orchestrator/registry.py`

Технически это “пока работает”, но это прямая причина будущей лапши: модульные границы неустойчивы.

### 3.3. “Файлы‑боги” (высокая связность)

Файлы с наибольшим количеством внутренних импортов (кандидаты на декомпозицию):

- `policy-engine/src/orchestrator/nodes.py`
- `policy-engine/src/orchestrator/optimizer.py`
- `policy-engine/src/udf/engine.py`
- `policy-engine/src/fabric/ingestion.py`
- `policy-engine/src/orchestrator/compiler.py`
- `policy-engine/src/orchestrator/data_loader.py`
- `policy-engine/src/orchestrator/registry.py`
- `policy-engine/src/agent/drafter.py`

---

## 4) As‑is: красный список смешения ролей (что ломает “компиляторность”)

Это не “советы”, а конкретные места, где роли смешаны и будут множить энтропию:

1) **Цикл `agent ↔ orchestrator`**  
   `policy-engine/src/agent/prompts.py` тянет `MECHANISM_REGISTRY` из `policy-engine/src/orchestrator/registry.py`, а `workflow.py` тянет `drafter_node`.  
   В целевой архитектуре реестр механизмов живёт в `foundry`, а scientist “подписывается” на него, не создавая циклов.

2) **Scientist пишет/читает данные “куда попало”**  
   `policy-engine/src/orchestrator/nodes.py`: напрямую создаёт `SimulationDB("integration.duckdb")`, пишет в `logs/` через `save_*`.  
   В целевой архитектуре это делается через `runtime` API (`start_run/log_artifact/finalize_run`).

3) **Обход контракта UDF/Fabric**  
   `policy-engine/src/orchestrator/data_loader.py`: формирует `DataViewRequest`, но затем делает сырой SQL строкой, игнорируя UDF план/валидацию.  
   Это ломает Закон C (контракты) и 2.1 границу IR→Fabric (см. to‑be).

4) **IR знает слишком много про foundry**  
   `policy-engine/src/policy_ir/contract.py` валидирует параметры механизмов через `get_mechanism_spec()` из `policy-engine/src/policy_ir/mechanism_spec.py`.  
   В целевой архитектуре: IR хранит `mechanism_type + parameters`, а **foundry registry** валидирует ranges/units/fidelity.

5) **Print‑логирование в “продакшн” src/**  
   Например `policy-engine/src/orchestrator/optimizer.py`, `policy-engine/src/orchestrator/nodes.py`, `policy-engine/src/agent/drafter.py`.  
   Это конфликтует с заявленным правилом Ruff `T20` (и в целом усложняет runtime tracing).

6) **Side‑effects при импорте `src`**  
   `policy-engine/src/__init__.py` мутирует env (JAX backend defaults). Это полезно как workaround, но архитектурно это “скрытый runtime слой” и источник сюрпризов: импорт типа/контракта может внезапно менять окружение исполнения.

7) **Дублирование фронтенда промптов**  
   `policy-engine/src/agent/prompt.py` и `policy-engine/src/agent/prompts.py` оба генерируют “schema prompt”, но с разными источниками истины (в одном месте только schema, в другом ещё `MECHANISM_REGISTRY` из orchestrator). Это повышает риск рассинхрона “что LLM думает, что можно”.

8) **Смешение “контракты vs примеры/legacy” в `policy_ir`**  
   Наличие `policy-engine/src/policy_ir/base.py` (demo/legacy) рядом с каноном IR затрудняет восприятие “где истина”. В целевой архитектуре IR‑пакет должен быть максимально аскетичным и однозначным.

---

## 5) To‑be: целевая структура репозитория (чтобы не тонуть)

Ниже — канонический “скелет компилятора”, который выдерживает рост.

### 5.1. Топ‑уровень (минимальный шум)

```
/src/
  /polisyos/
    /ir/
    /fabric/
    /foundry/
    /scientist/
    /runtime/        # запуск/артефакты/трейсинг (тонкий слой)
    /common/         # общие утилиты без тяжёлых зависимостей
/tests/
  /unit/
  /contract/
  /integration/
  /e2e/
/docs/
  architecture.md
  /adr/
  /schemas/          # экспортированные JSON Schema (build artifacts)
/tools/
  migrate.py
  gen_schema.py
  lint_imports.py
/pyproject.toml
/Makefile
```

### 5.2. Жёсткое разделение ответственности

#### `polisyos.ir` — контракты и правила (канон)

Содержит:

- Pydantic модели: `PolicyRequestIR`, `Entity`, `Intervention`, `Objective`, `Scenarios`,
  **`DataViewRequest` (IR‑версия)**, `TargetSelector` AST.
- Универсальные валидаторы: лимиты графа, циклы/глубина, размеры, units/форматы.
- Ошибки в едином формате: `ValidationIssue`.
- Миграции: `polisyos/ir/migrations/v1_to_v2.py` и т.п., CLI `tools/migrate.py`.

Запрещено:

- JAX/Equinox/Diffrax/Optax
- DuckDB/Kùzu/Parquet/Polars
- LangGraph/LLM
- файловый I/O кроме (де)сериализации IR

Целевые требования (детально):

- **Стабильность “отдельного мира”:** `polisyos.ir` должен жить и тестироваться как отдельная библиотека (всё остальное может “падать”, IR остаётся стабильным).
- **Канонизация схемы:** `schema_version`, `generated_at`, `generator` обязательны; `extra="forbid"` на всех моделях; жёсткие лимиты (`max_entities/interventions/objectives/shocks`, `max_len` строк, `max_depth/max_children`).
- **Языковые алиасы:** принимать `En/Ua/Ru → en/ua/ru`, но сериализовать всегда канонически (`en/ua/ru`, lowercase); запрет “плавающих ключей” в артефактах.
- **Units как часть контракта:** `currency`, `price_base_year`, `time_unit` должны быть в корневом IR и проходить валидацию (без “догадок” на стороне runtime).
- **TargetSelector AST:**  
  `predicate={field, op, value}` + композиция `all_of/any_of/not`; опциональное `selector_text` допускается только как “для человека”, **никогда не исполняется**.
- **Граф сущностей:** плоский adjacency‑list (`entities[] + parent_id`), валидаторы: DAG (без циклов), `max_depth`, `max_children`, достижимость от корней.
- **Протокол self‑healing ошибок (канон):** `ValidationIssue{issue_id,severity,component,loc,message,recommended_fix,blocking}`; при любом `ValidationError` формируются `error_summary`, `repair_attempt`, `diff_before_after` (даже если diff пустой).
- **Миграции:** `ir/migrations/*` + CLI migrate; правила: `MAJOR` = rename/remove/semantic change, `MINOR` = add optional. Миграции детерминированы и покрыты тестами.
- **Contract tests (обязательно):**
  - roundtrip: `yaml → model → yaml` (канон сохраняется),
  - alias acceptance: принимает `En/Ua/Ru`, сохраняет `en/ua/ru`,
  - limits: огромный JSON не “валит пайплайн”, а превращается в структурированный `REJECT_IR`,
  - entity DAG: цикл ловится,
  - selector AST: запрещённые `op` ловятся; “field existence” валидируется на границах (см. IR→Fabric/IR→Foundry), а не через сырой eval.

As‑is уже частично совпадает с целями:

- `schema_version/generated_at/generator`, units, лимиты и DAG‑валидаторы уже есть в `policy-engine/src/policy_ir/contract.py`.
- `TargetSelector` уже структурный (AST) + `SelectorOperator` enum (`policy-engine/src/policy_ir/types.py`).
- Языковые алиасы `En/Ua/Ru` уже поддержаны в `policy-engine/src/policy_ir/types.py`.
- Есть зачатки миграций: `policy-engine/src/migrations/*` + `policy-engine/migrate.py`.

Главные “дыры” as‑is относительно цели:

- Нет канонического `ValidationIssue` и единого “self‑healing report” как артефакта.
- Семантика механизмов (specs/ranges) сейчас зашита в `policy_ir/mechanism_spec.py`, т.е. IR знает про foundry‑семантику (см. Закон A).
- Есть базовый contract‑test набор для IR (`policy-engine/tests/contract/`), но генерация JSON Schema остаётся отдельным tool (`policy-engine/tools/diagnostics/generate_ir_schema.py`).

#### `polisyos.fabric` — Unified Data Fabric

Содержит:

- Слои данных `raw/staging/curated` + manifests.
- ER/Reconciliation/PII tiers.
- Компилятор view: `DataViewRequest(IR)` → (SQL/Cypher) → DataFrame/edges → (опц.) тензоры.
- Репозитории: `FirmRepo`, `EventRepo`, `GraphRepo`.

Запрещено:

- LangGraph/LLM (scientist‑уровень)

Разрешено:

- DuckDB/Kùzu, Parquet, Pandas/Polars/Arrow

Целевые требования (детально):

- **Слои данных + manifests:** `raw/` неизменяемо → `staging/` нормализация → `curated/` parquet + загрузка в DuckDB/Kùzu; `DatasetManifest` обязателен (`source/license/hash/schema_version/quality/pii_flags/coverage`).
- **EntityResolution как стадия:** `raw_id → canonical_id`, `match_confidence`, `match_method`; curated без `canonical_id` запрещён.
- **Reconciliation:** баланс “источник↔приёмник” в tolerance, иначе dataset непригоден (ingestion падает или помечает fail).
- **PII tiers:** классификация полей `public/internal/sensitive`; `DataViewRequest` включает `access_tier`; compiler обязан **вырезать** запрещённое.
- **DataViewCompiler:** принимает только декларативный `DataViewRequest` (из IR), возвращает типизированные результаты:
  - `PanelView` (df + schema),
  - `NetworkView` (edges + schema),
  - `EventLog` (traces + schema),
  плюс `DataViewPlan` (план компиляции: источники/партиции/индексы/фильтры/PII‑редакции).
- **Performance budget:** фиксируются 2–3 эталонных запроса и SLA на ноутбуке как тест‑гейт (например: “< baseline * 1.2”).
- **Integration tests (обязательно):**
  - поднять demo UDF “на пустой машине”: ingest → curated → 1 panel + 1 network,
  - запрет сырого SQL от LLM: compiler не принимает строковые запросы,
  - `access_tier`: PII не выдаётся ни при каких условиях,
  - manifest mismatch: если feature отсутствует — `REJECT` до выполнения SQL.

As‑is уже частично совпадает с целями:

- Ingestion уже пишет manifests + hash/quality/pii_flags + reconciliation: `policy-engine/src/fabric/manifest.py`, `policy-engine/src/fabric/ingestion.py`.
- Entity resolution уже существует: `entity_resolution.parquet` + mapping raw→canonical в `policy-engine/src/fabric/ingestion.py`.
- PII tiers и whitelist прототип уже есть в UDF: `policy-engine/src/udf/config.py`, `policy-engine/src/udf/compiler.py`, `policy-engine/src/udf/schema.py`.
- Есть графовый слой (Kùzu) и табличный (DuckDB): `policy-engine/src/io/graph_store.py`, `policy-engine/src/io/db.py`.

Главные “дыры” as‑is относительно цели:

- `DataViewRequest` живёт в `udf/`, а не в IR, и его можно обойти (см. `policy-engine/src/orchestrator/data_loader.py` с raw SQL).
- Нет `DataViewPlan` и типизированных view‑результатов (всё возвращается как `pd.DataFrame`).
- Нет “manifest mismatch gate” на уровне единого fabric API: сейчас часть проверки есть (allowed columns), но manifest‑контракт не является центром принятия решений.

#### `polisyos.foundry` — functional core (JAX)

Содержит:

- Механизмы как `eqx.Module` с `init_state/step/invariants`.
- **Реестр механизмов** (owner механик и их `MechanismSpec`), без импортов scientist/fabric.
- Fidelity levels/relaxation roadmap.
- Debug mode (`disable_jit`, checks).

Запрещено:

- БД, LLM, файловые I/O, `print` (кроме `jax.debug.print`)

Целевые требования (детально):

- **Единый API механизмов:**  
  `init_state(key, params) -> State`  
  `step(state, inputs, params, key?) -> (state, outputs, key?)`  
  `invariants(state) -> bool | metrics`  
  PRNGKey передаётся явно (и возвращается, если расходуется).
- **JIT‑Safety:** запрет Python side effects; контроль потока только через `jax.lax.*`; структуры — только PyTree стабильной формы.
- **Fidelity levels:** `SURROGATE_FLUID → RELAXED_DISCRETE → HARD_DISCRETE` + параметры `temperature/beta`, политика annealing; `fidelity gap tests` между уровнями.
- **Gradient Health Protocol:** логировать NaN/Inf долю, нормы градиентов, vanishing/exploding; опции `clipping`, reparam (softplus), checkpointing.
- **Debug mode:** `jax.disable_jit()`, `jax.debug.print`, расширенные `invariants` проверки.
- **Реестр механизмов:** `MECHANISM_REGISTRY` + `MECHANISM_SPECS` живут в foundry и не импортируют scientist/fabric; scientist получает только read‑only каталог.
- **Unit tests (обязательно):**
  - `jit(step)` компилируется, 2 шага подряд, структура PyTree стабильна,
  - grad check на игрушке (finite diff vs `jax.grad` в допуске),
  - invariants дают понятный сигнал (неотрицательность/балансы).

As‑is уже частично совпадает с целями:

- База механизма с `debug_mode` и `jax.disable_jit()` уже есть: `policy-engine/src/foundry/base.py`.
- `FidelityLevel` уже есть: `policy-engine/src/foundry/types.py`, и есть `fidelity_gap_report`/тест: `policy-engine/src/foundry/queue.py`, `policy-engine/tests/test_queue_fidelity.py`.
- JIT‑стабильность PyTree для механизмов уже тестируется: `policy-engine/tests/test_foundry_jit.py`.
- Есть зачаток gradient health: `policy-engine/src/foundry/utils.py` (`gradient_health`).

Главные “дыры” as‑is относительно цели:

- API механизмов пока “монолитный”: `Mechanism.step(state, key) -> state` без явных `inputs/outputs` и без возврата key.
- Реестр механизмов сейчас живёт в `policy-engine/src/orchestrator/registry.py`, что создаёт цикл и привязку scientist↔foundry.

#### `polisyos.scientist` — imperative shell (оркестрация)

Содержит:

- Workflow (LangGraph): `Draft → Validate → Repair → DataCompile → Sim → Analyze → Governor → Pack`.
- Self‑healing цикл (`max_repair_attempts`) и budgets (`max_llm_calls`, `max_sim_runs`, `max_wall_time`).
- Governor rules + пороги human approval.
- Формирование DecisionPacket (через runtime API).

Целевые требования (детально):

- **LangGraph как диаграмма процесса:** узлы `DraftIR → ValidateIR → RepairIR → CompileDataViews → CompileModel → RunSim → Analyze → Governor → PackDecision`.
- **Budget‑протокол:** `max_llm_calls`, `max_sim_runs`, `max_wall_time`; pruning с причиной (`timeout/constraint/metric`) как артефакт.
- **Governor:** `APPROVE/NEEDS_REVISION/REJECT`, замечания структурированы как `ValidationIssue`; policy safety check до симуляции (запрещённые меры/селекторы/немеряемые метрики).
- **Run management:** запрет повторного `run_id` или явный `parent_run_id`; каждый шаг пишет JSON/YAML + метаданные; полный audit trail (включая промпты и diff self‑healing).
- **E2E tests (обязательно):**
  - “золотой путь” на синтетике (1–2 интервенции, 1 цель, 1 view),
  - governor path: `NEEDS_REVISION` возвращается на правильный узел,
  - budget path: pruning работает и логируется.

As‑is уже частично совпадает с целями:

- Уже есть минимальный LangGraph workflow `drafter → simulator → governor`: `policy-engine/src/orchestrator/workflow.py`.
- Уже есть `RunRecord` и `DecisionPacket` как артефакты воспроизводимости: `policy-engine/src/orchestrator/run_record.py`, `policy-engine/src/orchestrator/decision_packet.py`.
- Уже есть audit trail: `policy-engine/src/orchestrator/audit.py`.

Главные “дыры” as‑is относительно цели:

- Scientist напрямую управляет путями/файлами/БД и пишет артефакты без runtime API (`logs/`, `integration.duckdb`).
- Есть две параллельные “трубы” orchestration (workflow vs `run_experiment.py`), нет единого процесса/артефактов.
- Нет явного бюджета/протокола pruning и нет канонического `ValidationIssue` (issues сейчас `GovernorIssue`).

#### `polisyos.runtime` — сквозная инфраструктура запуска

Содержит:

- run registry, артефакты, audit trail, кэш, логирование, сериализация результатов.
- Только инфраструктура: без бизнес‑логики.

Целевые требования (детально):

- Единая точка входа для прогона: `start_run()` создаёт `run_id` и `RunManifest`.
- `log_artifact(step, payload, media_type, schema_version, provenance)` пишет артефакты структурно (не “куда попало”).
- `finalize_run(status)` фиксирует причины завершения (approve/reject/pruned/error) и ссылочную целостность артефактов.
- Директория артефактов “как у компилятора”: `runs/<run_id>/...` (см. раздел “Золотые артефакты”).

---

## 6) Контракты на границах (самое важное)

### 6.1. Граница IR → Fabric: `DataViewSpec`

IR содержит только **декларативные** запросы (`TargetSelector` AST, `DataViewRequest`).

Fabric обязан:

- валидировать, что запрошенные фичи/колонки существуют (manifest/registry) **до** исполнения,
- применять `access_tier` (вырезать/запрещать PII) как часть компиляции,
- компилировать запрос **безопасно** (никакого “сырого SQL/Cypher от LLM”),
- возвращать **план** и **типизированный результат** (а не “просто DataFrame без контекста”).

Артефакты:

- `DataViewPlan` (внутренний план компиляции: таблицы/партиции/индексы/ограничения/PII‑редакции).
- Результат одного из видов: `PanelView` | `NetworkView` | `EventLog` (payload + schema/meta).

### 6.2. Граница IR → Foundry: `MechanismSpec`

IR хранит `mechanism_type + parameters`.

Foundry/Registry знает список механизмов и их `MechanismSpec`:

- required params
- ranges
- units
- fidelity support

До запуска JAX: `validate_mechanism_params(ir)` **обязателен**.

Артефакты:

- `CompiledModelSpec` (последовательность механизмов + нормализованные параметры + выбранные fidelity/режимы).
- (опционально) `MechanismCatalog` snapshot (read‑only список доступных механизмов + их specs) — вход для scientist prompt.

### 6.3. Граница Scientist → Runtime

Scientist не “пишет куда попало”: только через runtime API:

- `runtime.start_run()`
- `runtime.log_artifact(step, payload)`
- `runtime.finalize_run(status)`

Артефакты:

- `RunManifest` (паспорт прогона: версии/seed/backend/budgets/prompts + ссылки на все артефакты).
- Структура хранения: `runs/<run_id>/...` (см. “золотые артефакты”).

---

## 7) Операционный план аудита (серии маленьких PR)

Цель: понижать структурную энтропию, фиксируя контракты и границы.  
Каждый PR должен либо:

- **уменьшать связность**, либо
- **добавлять гейт**, который не даст связности снова вырасти, либо
- **фиксировать контракт/миграцию**, чтобы изменения были безопасными.

### Фаза 0. “Забор”: архитектурные гейты (сначала)

Цель: прежде чем двигать файлы, поставить автоматические запреты, чтобы не откатиться назад.

Мини‑PR’ы:

- Импорт‑гейт (варианты: `import-linter` или свой `tools/lint_imports.py`): Закон A как проверка (и отчёт: циклы/запрещённые ребра/топ “бог‑файлов”).
- Ban‑list гейт для foundry (статически): запрет `print/open/random/pandas/duckdb/kuzu` и т.п. в `polisyos.foundry`/`src/foundry`.
- Schema snapshot гейт: `gen_schema` + сравнение с committed JSON Schema (изменения контрактов должны быть осознанны).

DoD:

- Невозможно случайно добавить `foundry → fabric` или `fabric → scientist` (CI падает).
- Невозможно внести “побочные эффекты”/тяжёлые зависимости в foundry.

### Фаза 1. Жёстко закрепить `polisyos.ir` как отдельный мир

Цель: всё остальное может меняться/падать, но IR остаётся стабильным, мигрируемым и тестируемым.

Мини‑PR’ы (по одному “контрактному блоку”):

- Канонизация: обязательные поля (`schema_version/generated_at/generator`), lower‑case сериализация, `extra="forbid"`, лимиты, units.
- TargetSelector AST: фиксируем как единственный исполняемый формат; `selector_text` допускается только как “human string”.
- `ValidationIssue` + протокол self‑healing: единый формат ошибок с `loc`, `error_summary`, `repair_attempt`, `diff_before_after`.
- Миграции: структура `ir/migrations/*`, правила `MAJOR/MINOR`, миграционный CLI, тесты миграций.

DoD:

- IR можно генерировать/валидировать/мигрировать независимо (как библиотеку) без JAX/DB/LLM.

### Фаза 2. Fabric/UDF: сделать “умный склад” детерминированным сервисом

Цель: данные становятся библиотекой‑сервисом со строгим контрактом, которую можно вызывать без scientist/foundry.

Мини‑PR’ы:

- Утверждение слоёв `raw/staging/curated` + обязательность `DatasetManifest` как входа в curated.
- Отдельная стадия entity resolution (canonical ids) и запрет curated без неё.
- Reconciliation как gate (tolerance) — либо fail ingestion, либо явный “dataset unusable”.
- PII tiers как обязательная часть DataView компиляции (request → plan → execution).
- `DataViewRequest` переносится в IR (декларативный контракт), а fabric принимает только его; запрет “сырого SQL” в scientist.
- Performance budget: эталонные запросы + regression gate (relative к baseline).

DoD:

- Любая view строится только через декларативный compiler; несоответствие manifest/PII режется **до** исполнения SQL/Cypher.

### Фаза 3. Foundry: превратить JAX‑часть в герметичный “станок”

Цель: чистая математика + предсказуемые градиенты, независимая от данных/LLM.

Мини‑PR’ы:

- Единый API механизмов + явный PRNGKey‑протокол (передаётся/возвращается).
- JIT‑safety правила и тесты стабильности PyTree/форм.
- Fidelity levels + gap tests (fluid vs relaxed vs hard).
- Gradient health как артефакт (NaN/Inf, norms, clipping policies).
- Реестр механизмов и specs owned by foundry (scientist читает каталог, но не владеет им).

DoD:

- Foundry можно прогонять на синтетике без Fabric/Scientist и получать стабильные jit/grad sanity‑signals.

### Фаза 4. Scientist: собрать “чистый” workflow и run‑артефакты через runtime

Цель: orchestration становится читаемым графом с бюджетами/гейтами и понятными артефактами.

Мини‑PR’ы:

- LangGraph узлы: `DraftIR → ValidateIR → RepairIR → CompileDataViews → CompileModel → RunSim → Analyze → Governor → PackDecision`.
- Budget‑протокол и причины pruning.
- Governor: структурированные issues (`ValidationIssue`) + policy safety checks до симуляции.
- Run management: `run_id/parent_run_id`, `RunManifest`, audit trail, prompts, diffs — всё через runtime API.

DoD:

- Одна команда прогоняет pipeline и всегда оставляет полный паспорт (`RunManifest`) + артефакты + причины reject/pruning.

### Фаза 5. Репо‑реструктуризация (физическая)

Цель: сделать физическую структуру как в разделе 5.1 (`src/polisyos/...`) без “скрытых import side effects”.

Мини‑PR’ы:

- Перенос модулей по слоям + обновление импортов (маленькими порциями, слой за слоем).
- Удаление/вынос legacy/demo из канонических пакетов (пример: `policy_ir/base.py`).
- Доработка tooling (`tools/gen_schema.py`, `tools/migrate.py`, `tools/lint_imports.py`) и привязка к CI.

DoD:

- `polisyos.*` — единственный публичный namespace; старые `src.*` либо удалены, либо временно проксируются как миграционный слой (если нужно).

### Практичный порядок (сводка)

1) Import‑гейты (забор) → 2) `polisyos.ir` (скелет) → 3) minimal Fabric demo (кровь) → 4) Foundry API+registry+jit/grad tests (мышцы) → 5) Scientist workflow + runtime артефакты (нервная система) → 6) миграции + schema snapshotting (память).

---

## 8) Прямое сопоставление as‑is → to‑be (чтобы видеть миграции)

| As‑is пакет/файл | Роль сейчас | To‑be слой |
|---|---|---|
| `policy-engine/src/policy_ir/*` | IR контракты | `polisyos.ir` |
| `policy-engine/src/foundry/*` | механизмы JAX | `polisyos.foundry` |
| `policy-engine/src/domain/*` | JAX state (мир) | `polisyos.foundry` (или `polisyos.ir` только типы‑контракты, но без JAX) |
| `policy-engine/src/engine/*` | экономический kernel | `polisyos.foundry` |
| `policy-engine/src/udf/*` | data view request + compiler + engine | `polisyos.fabric` (request в `polisyos.ir`) |
| `policy-engine/src/io/*` | DB/graph adapters | `polisyos.fabric` |
| `policy-engine/src/fabric/*` | ingestion + manifests | `polisyos.fabric` |
| `policy-engine/src/orchestrator/*` | workflow + артефакты | `polisyos.scientist` + `polisyos.runtime` |
| `policy-engine/src/agent/*` | LLM drafting | `polisyos.scientist` |
| `policy-engine/src/utils/*` | logger/env | `polisyos.common` или `polisyos.runtime` (в зависимости от веса) |

---

## 9) Архитектурные гейты в CI (чтобы не откатиться назад)

### 9.1. Статические гейты

- `ruff` (включая запрет `print` в прод‑коде), `mypy --strict`.
- Import‑rules (Закон A): `import-linter` или `tools/lint_imports.py` как “забор”.
- Ban‑list для foundry: запрет тяжёлых импортов и side‑effects (`duckdb/kuzu/pandas/open/print/random` и т.п.).

### 9.2. Контрактные гейты

- `tools/gen_schema.py` → экспорт JSON Schema в `docs/schemas/` + diff с committed версией.
- Migration tests: `v(N-1)` IR/manifest/run‑artifacts мигрируются в `vN` и валидируются.
- Contract tests для IR/Fabric интерфейсов (roundtrip, alias acceptance, limits, PII enforcement).

### 9.3. Выполнимые гейты

- **Unit:** foundry механизмы `jit + grad + invariants` sanity.
- **Integration:** fabric demo `ingest → curated → 1 panel + 1 network` (без scientist/foundry).
- **E2E:** pipeline run → `DecisionPacket`/`RunManifest` создан + причины pruning/reject логируются.
- **Performance regression:** эталонные запросы/view‑операции не деградируют относительно baseline (relative gate).

Примечание: это уже перепаковано в `policy-engine/tests/*` (по слоям) и `policy-engine/tools/*` (ручные прогоны/диагностика).

## 10) Definition of Done (архитектура без самообмана)

Система архитектурно “здоровая”, когда одновременно истинно:

- Невозможно импортировать `fabric` из `foundry` (CI падает).
- IR‑пакеты можно установить отдельно и использовать как библиотеку (без тяжёлых зависимостей и без side‑effects).
- Любой IR имеет версию/единицы/лимиты и валидируется так, что LLM не может “раздуть мир”.
- Любой DataView создаётся только через декларативный compiler (не через текст SQL/Cypher).
- Любой механизм foundry проходит `jit + grad` sanity tests.
- Любой run оставляет `RunManifest` + артефакты + причины всех pruning/reject, воспроизводимость проверяема.

## 11) Минимальный набор “золотых” артефактов (чтобы дебажить как инженер)

Целевая структура артефактов: `runs/<run_id>/` (одно место, один паспорт, ссылка на всё).

```
runs/<run_id>/
  00_run_manifest.json
  A_policy_ir.yaml
  A_validation_report.json
  A_repair_diffs/
  B_data_view_request.json
  B_data_view_plan.json
  C_compiled_model_spec.json
  D_simulation_metrics.json
  D_gradient_health.json
  E_governor_decision.json
  F_decision_packet/
    decision_packet.json
    decision_packet.md   # или pdf/docx/md по необходимости
```

As‑is: часть артефактов уже есть, но разнесена по `policy-engine/logs/run_records/` и `policy-engine/logs/decision_packets/` без единого `RunManifest` и без стабильной структуры по шагам.
