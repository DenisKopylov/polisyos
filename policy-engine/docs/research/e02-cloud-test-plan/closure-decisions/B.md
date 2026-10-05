# B unit: карта закрытия runtime findings

**Исполнение:** читать вместе с [методами](method-decisions.md), [runtime-профилями](runtime-profiles.md), [семантикой](semantic-decisions.md), [контрактами](cross-unit-contracts.md) и [приёмкой](verification-and-closeout.md). Команды и новые test paths ниже — задачи следующей реализации; этот документ их не исполнял. Полный исходный критерий и маршрутизация: [coverage.json](coverage.json), immutable source G97.


## Решение

B-кандидат `a3daffbe867ddfe9eede5e5990687283b552952a` (`78f41aecb81d2e27ed89346328c90be1b4da6041`) содержит полезные ограниченные fixes, но не принят в G97. В G97 `97c85fae2d4505ec8248540d98b9556296244208` (`e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3`) из B присутствует только type-only изменение `common/async_tools.py` и его тест; остальные перечисленные механизмы остаются кандидатными.

Приёмочный cohort кандидата: 74 файла / 1 317 случаев; 1 315 PASS, 1 FAIL, 1 strict XFAIL, без errors/skips, 243.873 s. FAIL — `test_import_enforces_existing_tenant_ownership`: unbound import против существующего tenant claim не отказал. XFAIL B66: provider получил стоимость 0.02 после отмены инициатора, но settlement/trace/budget остались 0. Свежий C stream-consumer negative тоже FAIL при PASS healthy-disconnect; owner этого consumer — C. Architecture gate дал FAIL/154 нарушений; нельзя объявлять его унаследованным без replay того же gate от slice base по полному знаменателю. `closure_ids=[]` в final B acceptance.

## Основание и границы

Канонические таблицы `bundle-owners.tsv@97c85fae2d4505ec8248540d98b9556296244208` и `finding-owners.tsv@97c85fae2d4505ec8248540d98b9556296244208` проверены полным join: 127 bundles / 282 findings; B — 25 / 60, gaps/foreign/overlap/split owner нет. Точные finding criteria находятся в 25 canonical bundle files `@69780761ae091d8fcc6ab8778c7f5f7227eeef0b`; IDs, receipts, source refs, independent oracles, negative controls, test commands и статусы находятся в `coverage.json`.

Кандидат и source cut: base `c40d4acae1ce58b597267255026d9356565828fd`; candidate tree и whole-file receipt привязаны в `coverage.json`. Ранние CAS receipts рекламировали CAS-02, хотя canonical ownership относит CAS-01/CAS-03 к B; финальная acceptance объявила все 25 bundles, но не закрыла ID. Для CAS-01/03 не трактовать CAS-02 handoff как per-finding receipt.

В этом leaf выполнен статический разбор источника и полученных receipts; тесты и runtime gates не запускались. `coverage.json` — исполнимая карта следующей приёмки, а не PASS.

## Паттерны и атрибуция

- P40: B14/B40/B69/B155 — один end-to-end work/capacity класс на workflow и producer boundary; B66–B68 — producer identity/permission/settlement; B70–B76 — generation/frontier; B87/B89/B90 — physical connector ownership; CAS findings отдельно проверяют admission, inventory, blob, signature, batch consumer и iterator.
- P41 касается только происхождения gate-red: объявлять отказ унаследованным можно после точного replay того же gate от slice base с полным знаменателем и нулевым пересечением изменённых путей. Это не универсальное условие поведенческого закрытия; четыре исторических checkout не требуются для B151 или иных criteria.
- Семь detached исторических деревьев не имеют admission receipts; ретроспективный admission не заявлен. Candidate FAIL не переименовывать в inherited. G97 runtime и candidate branch различать по SHA.

## Задачи по bundle

Для каждого bundle ниже дан выбранный механизм и точечная карта finding IDs. Команда из `coverage.json` запускается только после точной интеграции соответствующего кандидата; `G` затем перечитывает branch SHA/tree и один раз запускает полный 74-file B cohort. Производственные данные не открывались.

<a id="bundle-cas-01"></a>

### CAS-01 — First-writer ref, blob integrity и lock bound

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/core/artifacts/test_cas_integrity_report.py tests/unit/core/artifacts/test_import_tenant_context.py tests/unit/core/artifacts/test_multi_tenant_shared_cas.py tests/unit/core/artifacts/test_artifact_id_serialization_contract.py
```

- **B150** — Сохранять отдельную manifest-view identity в refs при дедупликации общих bytes.
- **B151** — Не менять механизм без необходимости: добавить/выделить прямую регрессию через FileSystemCAS.put_bytes. Для существующего испорченного blob и отдельно изменённого manifest.byte_size допустим точный ArtifactIntegrityError до downstream; успешный retry обязан сразу пройти get_bytes(ref) и verify(ref). Сохранить положительный контроль: при отсутствующей sidecar тот же правильный digest восстанавливается и читается. После включения точечного теста выполнить свежий cohort/readback на точном интегрированном кандидате.
- **B153** — Сохранять striped locks и доказывать, что одна активная задача по ключу не исполняется конкурентно.

B151 статически покрыт в `store.py`: существующий blob сверяется с digest; существующий выбранный manifest проходит read-integrity проверку на исходных bytes, включая `byte_size` (`_integrity_ops.py:90`). Но общий cohort receipt не показывает прямой corrupted-put retry, неправильный `byte_size` retry и missing-sidecar positive control. Ближайший `test_cas_integrity_report.py:18` повреждает blob для `verify()`, затем восстанавливает его и проверяет duplicate write; это не retry-to-consumer доказательство. Четыре historical replay не нужны.

<a id="bundle-cas-02"></a>

### CAS-02 — Проверенный import и точная export inventory

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/core/artifacts/test_import_tenant_context.py tests/unit/core/artifacts/test_transfer_output_paths.py tests/unit/core/artifacts/test_transfer_publication.py tests/unit/remediation/test_cas_02.py
```

- **B148** — Рекомендуемое правило: под artifact lease и до staging/intent разрешать повторный импорт уже заявленного артефакта только как true no-op для того же bound tenant+cell, уже принадлежащего ему exact view, с идентичными manifest/profile/signature/bytes; не менять owner/view claims или generation. Любой unbound/foreign import в заявленный CAS отклонять. Для незаявленного CAS создавать tenant claim лишь когда manifest.tenant_context точно совпадает с явным owner; unscoped non-authority cache оставить отдельным unscoped путём. Публичный cross-tenant смысл — предложение, не ратифицированная политика.
- **B149** — Перенести exact-inventory staging и атомарную generation switch; после admission сохранить A→B same-destination probe, import независимым consumer, смену include_manifests и отказ второго publish с сохранением прежнего полного поколения.

Для B148 текущий конфликт прямой: `test_unbound_import_can_admit_an_independent_view_of_foreign_owned_bytes` разрешает случай, который `test_import_enforces_existing_tenant_ownership` запрещает. Добавить отказ до stage/intent/claim и снимки bytes/manifest/signature/claims/generation; same-owner exact-view повтор должен быть истинным no-op. Mutation-control, отключающий lease-level preflight при сохранённых marker-именах, должен провалить assertion. Существующие `ArtifactOwnershipIndex` primitives находятся в `ownership.py`: `artifact_lease(s)`, `has_any_tenant_claim`, `is_view_owned_by`, `is_blob_readable_by`; объединить preflight для `import_subgraph` и `import_exact_view`.

<a id="bundle-cas-03"></a>

### CAS-03 — Один integrity snapshot, batch result и bounded iteration

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/core/artifacts/test_signed_evidence.py tests/unit/core/artifacts/test_cas_integrity_report.py
```

- **B152** — Получать byte_size/hash/signature/report из одного snapshot тех же bytes.
- **B154** — Возвращать typed per-item result; собирать результаты всех admitted элементов до публикации и fail closed при пропуске или ошибке.
- **B155** — Ограничивать producer iteration, pending-future window и deadline вместе; если filesystem census нельзя остановить, объявить именно эту границу.

B154 остаётся `consumer_missing`, пока реальный all-confirmations publisher не использует полный typed batch report. B152 требует независимый wrong-`byte_size` selected-view control.

<a id="bundle-cmp-01"></a>

### CMP-01 — Импорт, effective DAG и payload исполнителей

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/foundry/methods/test_compiler.py tests/unit/foundry/methods/test_composer.py tests/unit/foundry/methods/test_semantic_validator.py
```

- **B42** — Сохранить тесты обоих process import orders и запуск реальной двухузловой registry chain.
- **B43** — Сохранить required edge в compiled graph и проверить его потребление executor.
- **B44** — Использовать один canonical payload builder/materializer для sequential, async и checkpoint resume.

<a id="bundle-cmp-02"></a>

### CMP-02 — Однозначные slots и occurrence order

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/foundry/methods/test_semantic_validator.py tests/unit/foundry/methods/test_composer.py
```

- **B45** — Сохранить явную merge authority и заявленное поведение WARN/STRICT; не придумывать normative choice.
- **B46** — Использовать реальный occurrence identity/index в validator и diagnostics.

<a id="bundle-cmp-03"></a>

### CMP-03 — Единая семантическая проверка links

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/foundry/methods/test_linker.py tests/unit/foundry/methods/test_composer.py
```

- **B47** — Использовать complete matching по реальному typed compatibility graph.
- **B48** — Провести ручной и автоматический пути через одну semantic acceptance function.

<a id="bundle-dur-01"></a>

### DUR-01 — Полнота и integrity budget ledger

Точечная приёмка после admission:

Текущие регрессионные файлы (не заменяют process witness):

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/test_budget_middleware.py tests/unit/scientist/mirror_contracts/test_budget_ledger.py
```

В G97 отсутствует `tests/unit/scientist/orchestration/engine/test_budget_ledger_process.py`. Добавить туда process-level witness; после появления файла запустить:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/test_budget_ledger_process.py tests/unit/scientist/orchestration/engine/test_budget_middleware.py tests/unit/scientist/mirror_contracts/test_budget_ledger.py
```

- **B37** — Различать отсутствующий, но ещё не bootstrap-нутый ledger от malformed existing и от намеренно unlimited state. Прямой публичный cold `FileBudgetLedger.record_spend` не должен молча сохранять default `BudgetState()` без лимитов: требовать явную валидную bootstrap-конфигурацию и отказать до мутации, если её нет. Тот же completeness invariant охватывает parseable sparse existing JSON: `{}`, `{"state": {}}` и persisted записи с удалённым обязательным snapshot/state полем. Разделить явный constructor/bootstrap и strict persisted decode: required wire fields текущего writer/schema проверяются до любых default factories или `_normalize_snapshot`, включая вложенный state; nullable/optional поля, которые writer законно опускает через `exclude_none`, не объявлять обязательными. Каждый load/mutate/reopen проходит тот же decoder. Sparse existing record отклоняется без перезаписи; отсутствие файла не делает implicit unlimited bootstrap. Положительный контроль: `load_or_bootstrap(BudgetState())` — это явное валидное no-limit решение, которое остаётся unlimited после записи и reopen.

Текущие semantic controls в `test_budget_middleware.py`: `test_ledger_persists_state_across_middleware_instances`, `test_ledger_reader_never_observes_blank_snapshot_during_writer_pause`, `test_ledger_failed_atomic_replace_preserves_last_valid_snapshot`, `test_ledger_corrupt_existing_snapshot_never_becomes_unlimited`; они не являются process-level cold-mutation witness. Будущий файл должен включить `test_cold_record_spend_requires_bootstrap_across_processes`, `test_explicit_unlimited_bootstrap_remains_valid_across_processes` , `test_malformed_existing_ledger_is_not_rebootstrapped` и `test_parseable_sparse_existing_snapshot_is_not_unlimited_or_rewritten`. Первый запускает public cold `FileBudgetLedger.record_spend` на отсутствующем пути; затем отдельные процессы упражняют настроенный `BudgetMiddleware` через `record_spend_safe` и `pre_check`. После исправления cold writer не подменяет configured ledger состоянием unlimited, а middleware сохраняет заданный лимит и блокирует исчерпанный бюджет. Явный unlimited bootstrap остаётся разрешён; malformed existing отвергается без перезаписи.

<a id="bundle-dur-02"></a>

### DUR-02 — Lease, owner и неопределённый внешний outcome

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/runtime/http/test_control_plane_store.py tests/unit/remediation/test_dur_02.py
```

- **B38** — Сохранить действующий механизм; на G97 проверить точные stale-owner и lease-expiry сценарии.
- **B78** — Сохранять typed PrimaryExecutionOutcomeUnknownError; reconciliation разрешать только через реальный external idempotency/status contract.

<a id="bundle-exe-01"></a>

### EXE-01 — Execution cache и admission

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/integration/scientist/test_async_cache_recovery.py tests/integration/scientist/test_execution_state_replay.py
```

- **B51** — Разделить admission на чтение cache и новую computation.
- **B52** — Ограничить worker и private cache до принятия результата текущей попыткой и deadline.
- **B55** — Проверять cancellation под slot/release guard.

<a id="bundle-exe-02"></a>

### EXE-02 — Ready frontier и parallel execution

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/integration/scientist/test_execution_state_replay.py tests/integration/scientist/test_checkpoint_resume.py
```

- **B77** — Запускать готовые по зависимостям nodes через indegrees/readiness frontier, соблюдая max parallelism.

<a id="bundle-jit-01"></a>

### JIT-01 — JIT cache, single-flight и preparation

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/foundry/methods/test_compiler_e02.py
```

- **B49** — Кешировать executable только по static/signature axes; на каждом вызове заново собирать текущий dynamic payload.
- **B50** — До освобождения followers публиковать value/error; после неудачной сборки разрешать настоящий retry.
- **B53** — Использовать declared schema либо явно ограниченный pure probe; не повторять работу.

<a id="bundle-llm-01"></a>

### LLM-01 — LLM adapter identity, metrics и settlement

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py tests/unit/scientist/orchestration/llm/test_prompt_cache.py
```

- **B64** — Назначать имя результата на adapter boundary одним owner.
- **B65** — Изолировать исключение optional metrics/tracing от доставки результата, но сохранять различие с отказом обязательного accounting.
- **B66** — Создать producer-owned settlement event и ack/idempotent ledger link, живущие дольше caller cancellation; при потере ack выдавать unknown.

<a id="bundle-llm-02"></a>

### LLM-02 — LLM cache permission и exact evidence

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py
```

- **B67** — Получить permission owner contract и до cache reuse связать actor/scope/epoch с точными evidence refs.
- **B68** — Только после B66/B67 делать single-flight по точным scoped request/ref/permission epoch и одному producer event.

<a id="bundle-net-01"></a>

### NET-01 — Pool resource ownership и stream cleanup

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/fabric/connectors/test_pool_e02.py tests/unit/fabric/data_plane/test_streaming_runtime.py
```

- **B87** — Перед очисткой состояния C должен передать владение handle/pending cleanup; B pool покрывает только producer половину цепочки.
- **B89** — Один physical owner должен освободить semaphore ровно один раз после завершения disconnect.
- **B90** — Интегрировать точный B pool slice; держать один deadline через wait/connect/health/register и атомарно передавать ownership.

<a id="bundle-net-02"></a>

### NET-02 — Circuit breaker state и provider mapping

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/fabric/connectors/test_resilience.py tests/unit/scientist/orchestration/engine/test_circuit_breaker.py
```

- **B91** — Сохранить fractional monotonic refill и отдельный wait deadline.
- **B92** — Связывать каждую попытку с generation lease; stale finalization должна быть no-op либо диагностироваться.
- **B93** — G и владелец ledger сверяют критерий canonical card, связывают его с реально защищённым state и повторяют committed probe.

<a id="bundle-res-01"></a>

### RES-01 — Idempotency и exact ArtifactRef

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/remediation/test_res_01.py tests/integration/scientist/test_checkpoint_resume.py
```

- **B63** — Дедуплицировать только точный ArtifactRef; связывать результат с content/view/tenant.
- **B70** — Сохранять неизменный origin fingerprint во всех resumed specs.
- **B71** — Проверять уникальные node/request refs относительно канонического completed frontier.

<a id="bundle-res-02"></a>

### RES-02 — Checkpoint journal и completion

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/integration/scientist/test_execution_state_replay.py tests/integration/scientist/test_checkpoint_resume.py
```

- **B72** — Использовать один canonical journal/completion operation при width 1 и N.
- **B73** — Публиковать state, completed frontier и cache refs как одно generation.

<a id="bundle-res-03"></a>

### RES-03 — Реальный simulation route и локальные данные

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/integration/scientist/test_res_03_real_simulation_route.py
```

- **B13** — Сначала выполнить A/G admission локального read-only каталога и реальный TestClient путь; сохранить владение A файлами generation_cycle.py и run_lifecycle.py.

<a id="bundle-res-04"></a>

### RES-04 — Checkpoint fingerprint, per-node history и generation

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/remediation/test_res_04.py tests/unit/foundry/methods/backends/test_checkpointing_execution.py
```

- **B74** — Вычислять digest compiled effective request, initial input и относящуюся к ним dependency/version identity.
- **B75** — Восстанавливать per-node result records/seed/order; при отсутствующей истории сообщать incomplete, не синтезировать результат.
- **B76** — Использовать immutable generation dir и manifest pointer; удалять sidecar под той же writer lock.

<a id="bundle-run-01"></a>

### RUN-01 — Retry, deadline, context и capacity

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/test_retry.py tests/unit/common/test_async_tools.py
```

- **B14** — Интегрировать B retry/worker slice и зафиксировать остановку: завершать собственное дерево процессов и queued work; не обещать остановку произвольного running thread/coroutine.
- **B40** — Провести один monotonic deadline от producer через очередь/retry/publication; поздний unknown effect типизировать, а не считать остановленным.
- **B69** — Заменить raw `Future` на `Future`-совместимый proxy, оставив bounded slot занятым до возврата всех синхронных done-callbacks. Admission/reentrant guard должен атомарно считать worker и callback capacity; callback в worker или callback context при полном пуле получает немедленный `SharedExecutorReentrancyError(RuntimeError)`, а не queued inner job. Proxy синхронизирует `running`/`result`/exception/cancel и сохраняет стандартный `add_done_callback` порядок/поток исполнения; обёртка callback помечает context и для late registration на уже завершённом Future. При shutdown сначала закрыть admission под lock, затем вызвать base shutdown уже без него. Барьерный тест должен показать refusal при N физически занятых workers, восстановление после снятия барьера, cancel-before-start, callback exception и позднюю регистрацию. Не обещать прерывание уже запущенного callable/callback; произвольный вечный внешний wait всё ещё может удерживать worker.
- **B95** — Захватывать и восстанавливать context для каждой отправленной задачи; не делить один mutable context между callers.
- **LA-057** — Сохранить type-only изменение; отдельно проверить G97 import/API и admission callers для opaque dynamic consumers и package distribution.

<a id="bundle-run-02"></a>

### RUN-02 — Parent drain и завершение процессов

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/test_retry.py
```

- **B24** — Интегрировать transport с одновременным parent drain; сохранить typed failure и descendant cleanup.

<a id="bundle-run-03"></a>

### RUN-03 — Единая retry-классификация и baseline

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/test_retry.py tests/unit/remediation/test_run_03.py
```

- **B39** — Использовать один classifier на всех adapter routes; после integration повторить точную матрицу.
- **B96** — Перед retry восстанавливать declared baseline; continuation сохранять только через явный checkpoint contract.

<a id="bundle-sta-01"></a>

### STA-01 — Typed state operations и restore

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/integration/scientist/test_execution_state_replay.py tests/unit/remediation/test_res_04.py
```

- **B57** — Сохранять typed операции изменённых полей и применять их к актуальному состоянию.
- **B58** — Сохранять remove/delete операцию в journal.
- **B59** — Сохранить вложенную изоляцию на границе state snapshot.

<a id="bundle-sta-02"></a>

### STA-02 — Cache identity и resolver inputs

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/methods/causal/test_resolve_parameters_node.py tests/integration/scientist/test_checkpoint_resume.py
```

- **B60** — Сохранить проверки source digest/context и invalidation до повторного cache reuse.
- **B61** — До реализации получить immutable/versioned SKG data_record contract с точным перечнем consumed query/run/custody полей; не выдумывать этот нормативный закон.
- **B62** — Сохранить явный presence bit/typed input state в cache key и API.

<a id="bundle-wire-01"></a>

### WIRE-01 — Versioned state wire format

Точечная приёмка после admission:

```sh
cd policy-engine && PYTHONPATH=src .venv/bin/python -m pytest -o addopts= -q tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py
```

- **B94** — Использовать versioned tagged Decimal wire encoding и строгий typed decode.

## Межсрезовые зависимости и порядок

1. Сначала admit exact candidate source; сохранить owners: A — `generation_cycle.py` / `run_lifecycle.py`, C — `streaming.py`. B-pool PASS не закрывает stream consumer; текущий свежий C negative показывает pending cleanup без pool ownership/retry.
2. Не придумывать чужие нормативные контракты: B61 требует immutable/versioned SKG `data_record` с точными consumed query/run/custody fields; B67 — permission owner contract и binding actor/scope/epoch к exact evidence refs; B66 — producer-owned idempotent settlement, живущий дольше caller cancellation; B93 — canonical protected regulator state из owner ledger. Для CAS-02 дана конкретная fail-closed admission recommendation; её публичное значение должно быть ратифицировано до объявления принятой межtenant политики.
3. После targeted tests собрать один свежий B cohort на immutable admitted G candidate с точной командой, input identity и resource capture из final acceptance. Проверку наследования красного исполнять отдельно только если заявлен inherited failure; без replay атрибуция `not_established`.
4. Не менять исходные ledger statuses на основании этой карты: 56 partial / 3 closed / 1 held; промежуточные closure proposals B37/B44/B74/B75/B76 не были formal acceptance.

Per-ID карта содержит criterion locators, выбранную задачу, oracle, negative control и P40/P41; source/receipt identity отдельно в input-identity.json: `coverage.json`.

**B37 completeness control:** из настоящего полного persisted snapshot по одному удалять каждое mandatory wire поле, включая поля nested state; проверять отказ public load/mutate и configured middleware/fresh-process read без изменения bytes. Сохранённые constructor defaults не должны делать этот negative зелёным. Это тот же `snapshot-completeness` класс, не новый permission subsystem; полный явно bootstrap-нутый unlimited snapshot остаётся положительным контролем.
