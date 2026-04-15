# Запуск benchmark-наборов

> Используйте benchmark suite registry, интерпретируйте JSON-отчёты и понимайте, чем основной benchmark workflow отличается от отдельного GitHub performance-regression workflow.

## 1. Обзор

Публичная compatibility-точка входа для benchmark-раннера:

```text
tools/benchmarks/run_all.py
```

Каноническая implementation-точка входа:

```text
tools/research/benchmarks/run_all.py
```

CLI-эквивалент:

```text
polisyos-tools benchmarks run-all
```

Авторитетный benchmark-domain registry:

```text
benchmarks/suite_registry.py
```

Совместимый tools-facing shim:

```text
tools/benchmarks/suite_registry.py
```

Важный текущий нюанс:

- имена каталогов в `benchmarks/` не являются главным источником истины
- главным источником истины является registry
- многие suites оформлены как circuit-style scripts, а не как обычные `pytest` директории

Сейчас в репозитории есть benchmark-области вроде:

- `abstraction`
- `advanced`
- `adversarial`
- `capability_wins`
- `comparators`
- `composition`
- `discovery`
- `distributional`
- `estimation`
- `foundry`
- `governance`
- `hte`
- `interaction`
- `interference`
- `missing`
- `natural_experiments`
- `ops`
- `proof_closure`
- `strategic`
- `symbolic`
- `temporal`
- `transport`

При этом сам registry сейчас определяет suites вроде:

- `symbolic`
- `estimation_acic`
- `estimation_lbidd`
- `estimation_realcause`
- `hte_interpretable`
- `discovery_sachs`
- `transport_core`
- `policy_natural_experiments`
- `temporal_gold`
- capability demos

## 2. Быстрый запуск

Из корня репозитория:

```bash
uv run polisyos-tools benchmarks run-all
```

Поведение по умолчанию из текущего shell script:

- `BENCH_MODE=smoke`
- JSON-отчёты по умолчанию пишутся в `tools/research/benchmarks/_reports/`
  при запуске через canonical tools surface
- `PYTHONPATH` включает `src` и корень репозитория

Репрезентативный формат вывода в консоль:

```text
========================================================================
  Circuit: Circuit 1: Symbolic Identification (ID algorithm gold suite)
========================================================================
  Suite  : symbolic
  Script : benchmarks/symbolic/run_symbolic_benchmark.py
  Report : benchmarks/_reports/symbolic.json
  Mode   : smoke
  Tier   : smoke
  Run ID : bench-20260403T...
```

Полезные переменные окружения, которые поддерживает раннер:

- `BENCH_MODE`
- `BENCH_TIER`
- `BENCH_PROFILE`
- `BENCH_VALIDATION_CONTOUR`
- `BENCH_VISIBILITY`
- `BENCH_CIRCUIT`
- `BENCH_RUN_ID`
- `BENCH_ESTIMATOR_PROFILE`

## 3. Выборочный запуск

Registry-driven selective run:

```bash
uv run polisyos-tools benchmarks run-all --circuit symbolic
uv run polisyos-tools benchmarks run-all --circuit temporal_gold --mode smoke
```

Прямой запуск через `pytest` тоже полезен для части локальных сценариев:

```bash
pytest benchmarks/comparators/ -v
pytest benchmarks/strategic/ -v
```

!!! note
    Не каждая benchmark family представлена обычной `pytest` директорией.
    Если вам нужна полная canonical suite surface, предпочитайте registry-backed shell runner.

## 4. Как устроен suite registry

`benchmarks/suite_registry.py` определяет dataclass `SuiteSpec` с полями вроде:

- `suite_id`
- `label`
- `script_relpath`
- `aliases`
- `profiles`
- `claim_profiles`
- `proof_class`
- `default_timeout_s`
- `headline`
- `stress_only`
- `validation_contours`
- `visibility`
- `family`
- `gate_class`
- `required_comparators`
- `primary_metrics`
- `supports_shadow`

Полезные helper API:

- `all_suite_specs()`
- `canonical_suite_id(...)`
- `spec_by_suite_id(...)`
- `suites_for_profile(...)`
- `suites_for_claim_profile(...)`
- `emit_registry_tsv(...)`

## 5. Как читать результаты

Canonical runner пишет per-suite JSON-файлы в `benchmarks/_reports/`.

`benchmarks/reporting.py` строит более богатые report payloads, включая:

- `pass_rate`
- `aggregate_metrics`
- `standardized_metrics`
- `governance_metrics`
- `leaderboard_tables`
- `release_gate_results`
- `comparator_matrix`
- `comparator_runs`
- `ablation_matrix`

`polisyos-tools benchmarks build-release-summary`
(`tools/research/benchmarks/build_release_summary.py`, root wrapper
`benchmarks/build_release_summary.py`) агрегирует их в release-level summary с
полями вроде:

- `contour_matrix`
- `comparator_completeness`
- `ablation_status`
- `leaderboard_tables`
- `release_gate_results`
- `comparator_execution_summary`
- `shadow_evidence_status`

## 6. Как добавить новый benchmark suite

Типовой workflow:

1. добавьте новый benchmark script в подходящий каталог `benchmarks/<family>/`
2. зарегистрируйте его в `benchmarks/suite_registry.py`
3. задайте стабильные `suite_id`, label, script path, aliases и metric focus
4. убедитесь, что скрипт пишет JSON shape, который понимает reporting layer

Минимальный паттерн `SuiteSpec`:

```python
SuiteSpec(
    suite_id="my_suite",
    label="Circuit X: My benchmark",
    script_relpath="my_family/run_my_benchmark.py",
    aliases=("my_family",),
    profiles=("air-m2", "extended"),
    validation_contours=("legacy",),
    visibility="public",
    family="my_family",
    gate_class="legacy_floor",
    primary_metrics=("score", "latency_ms"),
)
```

## 7. Интеграция с CI

Здесь важно не смешивать локальный benchmark registry и текущий CI reality.

### Benchmark registry workflow

Registry и `tools/research/benchmarks/run_all.py` — это canonical suite system
для benchmark circuits и release summaries. `tools/benchmarks/run_all.py`
остается public compatibility shim.

### Что есть в CI сейчас

В текущем дереве нет отдельного legacy performance-regression workflow.
Это означает:

- benchmark registry остаётся главным способом локально прогонять suites и читать JSON reports;
- performance regression policy, если она нужна для конкретного change set, должна оформляться
  отдельным PR/workflow решением, а не предполагаться как уже существующий repo-wide gate.

То есть:

- benchmark registry и CI quality gates сейчас не являются одной и той же системой;
- `polisyos-tools benchmarks run-all` остается canonical command boundary для benchmark circuits.
- `tools/research/benchmarks/run_all.py` остается canonical implementation entrypoint.
- `tools/benchmarks/run_all.py` и `benchmarks/run_all_benchmarks.sh` остаются compatibility shims.

## Советы

- начинайте с `--mode smoke`, прежде чем запускать тяжёлые профили
- используйте `--circuit` или `BENCH_CIRCUIT`, чтобы сузить локальный прогон
- если важны canonical suite ids и report locations, предпочитайте registry-driven runner
- raw `pytest` используйте тогда, когда вам нужен именно low-level local debugging
