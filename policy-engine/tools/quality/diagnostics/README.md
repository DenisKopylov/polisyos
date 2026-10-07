# tools/quality/diagnostics

Диагностический слой для контрактов, качества и verification-отчетов. Папка объединяет как CI-gates, так и ручные инженерные проверки.

## Роль в системе

- Контроль ABI/Schema drift и SemVer дисциплины.
- Проверка архитектурных контрактов Scientist/Foundry/Runtime.
- Формирование verification evidence/matrix (включая SCM v3 full-spec отчеты).
- Локальная диагностика окружения, provenance и data contracts.

## Скрипты

| Скрипт                                 | Назначение                                                                                                   | Контур                              |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------- |
| `gen_schema.py`                        | Генерация/проверка ABI snapshots в `schemas/snapshots` и generated IR reference pages                        | `pre-commit`, `arch.yml`, `abi.yml` |
| `generate_ir_reference_catalog.py`     | Генерация/проверка `docs/reference/ir/schema-catalog.md` и `docs/reference/schemas.md` из reflection catalog | docs / ABI tooling                  |
| `abi_diff.py`                          | Семантический diff baseline/current snapshots (`PASS/WARN/FAIL`)                                             | `abi.yml`                           |
| `check_state_reads.py`                 | AST-проверка соответствия `state_reads` у Scientist builtin nodes                                            | `arch.yml`                          |
| `check_scientist_node_version_bump.py` | Требует SemVer bump для измененных builtin-нод (`--base-ref`)                                                | `arch.yml`                          |
| `check_perf_regression.py`             | Сравнение benchmark JSON по порогам latency/throughput                                                       | `perf.yml`                          |
| `verify_scm_v3.py`                     | Прогон quick/full набора SCM v3 checks, генерация evidence/matrix + logs                                     | manual verification                 |
| `verify_scm_v3_fullspec.py`            | Full-spec матрица DoD/Laws/SL на базе `verify_scm_v3.py`, синхронизация canonical отчетов                    | manual verification                 |
| `check_setup.py`                       | Локальный smoke-check JAX/DuckDB/Pydantic и env настроек                                                     | local                               |
| `capture_env.py`                       | `capture/compare/validate` для `EnvironmentManifest`                                                         | local                               |
| `scan_fabric.py`                       | Генерация draft data-contracts из DuckDB схем                                                                | local                               |
| `visualize_provenance.py`              | Валидация/визуализация provenance (core graph, PROV-JSON, CAS, audit package)                                | local                               |
| `check_udf_perf.py`                    | UDF perf gate по baseline JSON                                                                               | legacy                              |
| `generate_ir_schema.py`                | Deprecated shim: проксирует вызов в `gen_schema.py`                                                          | deprecated                          |

## Связи с репозиторием

- `src/polisyos/*`: runtime-контракты, builtin-ноды, артефактные модели.
- `schemas/snapshots/*`: committed ABI snapshot outputs.
- `src/polisyos/schemas/abi_models.py`: Python ABI registry imported through `polisyos.*`.
- `docs/reports/*`: основная точка вывода verification отчетов (SCM v3 evidence/matrix + logs).
- `data/curated/*`, `data/databases/*`: входы для fabric/UDF локальных проверок.
- `baseline/*.json` и benchmark artifacts: входы perf-regression сценариев.

## Типовой запуск

```bash
uv run --extra ml polisyos-tools diagnostics gen-schema --check
uv run --extra ml polisyos-tools diagnostics gen-schema --check --changed-only --cache-dir _cache/polisyos-tools/cache --baseline-label ci --skip-if-unchanged
PYTHONPATH=src:. uv run python tools/quality/diagnostics/abi_diff.py --baseline /tmp/baseline --current /tmp/current --format markdown
PYTHONPATH=src:. uv run python tools/quality/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/quality/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/quality/diagnostics/verify_scm_v3.py --profile quick --output-dir docs/reports
PYTHONPATH=src:. uv run python tools/quality/diagnostics/verify_scm_v3_fullspec.py --output-dir docs/reports
```

## State-read diagnostic output

`check_state_reads.py` accepts the existing `NodeSpec` and `OutputAwareNodeSpec`
constructors in one unambiguous direct module `_SPEC` assignment, including
annotated assignments. The admission inventories syntactic `_SPEC` writes before
reading the declaration. Multiple writes, nested/dead declarations, destructuring,
or other unsupported binding forms return `UNRUN`; their read sets are never
unioned. Function-local or unreachable declarations cannot supply a module read.
The profile is deliberately conservative: a harmless local shadow or a valid last
rebind also remains undecided, rather than claiming Python reachability analysis.
It checks direct `state` reads in synchronous or asynchronous `execute` functions.
No node declarations or runtime authority are changed by this AST check.

The command emits a `state_reads measurement: ` JSON record before the existing
human-readable result. Preserve this record with deciding output: it lists the
selected paths, actual successful or failed reads and content hashes, exclusions,
denominator and boundaries that static interpretation does not resolve.

Exit `0` means the original read-declaration predicate passed on the disclosed
inputs. Exit `1` means a measured required read is missing. Exit `2` means the
check is incomplete (`UNRUN`): an enumerated file could not be read or parsed, or
its spec constructor or read expression is unsupported. Do not treat `2` as an
empty set or success. Literal list/tuple reads and the existing static f-string
prefix interpretation are supported; dynamic constructors, unpacked arguments,
nonliteral read expressions, aliases and indirect runtime reads remain undecided.
Zero declarations retain an empty static declared set, so the original missing-read
failure still applies. No recognized execute reads makes no runtime absence claim.
This is a static source predicate: dynamic writes, spec-object/list mutation and
actual runtime reaching definitions are outside the diagnostic, even after a
single declaration is admitted.

Git runs enumerate tracked files under the two declared builtin roots, retaining
missing members as failed read attempts. Non-Git fixtures enumerate their complete
filesystem set. Files outside those roots and `__init__.py`, `errors.py` and
`state_keys.py` are excluded. Import, Git/subprocess and service reads are outside
the explicit file-read collector. This output is a bounded repository diagnostic,
not a runtime execution, scientific correctness or permission verdict.

## Известные ограничения

- В кодовой базе отсутствуют `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store`; поэтому `check_udf_perf.py` сейчас не соответствует текущей структуре `src/polisyos`.
- `generate_ir_schema.py` оставлен только как backward-compatible alias к `gen_schema.py`.
- `gen_schema.py` использует content-addressable schema cache; invalidation key включает source hash ABI model module, ABI metadata, generator version и версию `pydantic`.
- `gen_schema.py --changed-only` не урезает manifest correctness: unchanged модели читаются из cache, а run целиком skip-ается только если не изменились ABI sources или persisted successful baseline fingerprint совпадает.
