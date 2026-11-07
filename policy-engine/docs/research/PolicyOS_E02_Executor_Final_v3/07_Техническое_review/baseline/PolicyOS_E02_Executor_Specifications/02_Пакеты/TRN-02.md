# TRN-02 — Полезное bounded discovery и целое поколение памяти

**LANE-02 · B129, B133, B134 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/TRN-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/TRN-02_исходные_строки.txt), строки 3183–3300.
**Практический результат:** Найти доступный совместимый опыт, прочитать exact snapshot и пережить ошибку native индекса без смешения vectors/metadata.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Discovered selected profile preserved.
- No second ANN; corruption distinct from empty.
- Old/new snapshots and current alias distinct.
- Fresh decode, repeated source check,128 entries/32MiB.
- Lock across query/mutation/save capture.
- Partial mutation restore, failed rollback unavailable.
- Candidate load before publish; portable row and default native trust guard.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C26_остатки:0 | REQ-TRN-02-01 | fix: Bounded compatible discovery. |
| audit-residual:C26_остатки:1 | REQ-TRN-02-02, REQ-TRN-02-03, REQ-TRN-02-04 | capability: Native source/portable actual producer. |
| audit-residual:C26_остатки:2 | REQ-TRN-02-03, REQ-TRN-02-04 | qualify: Native measured lifecycle cost. |
| audit-residual:C26_остатки:3 | REQ-TRN-02-02 | fix: Coverage assertion по реальной fixture schema. |
| B129 | REQ-TRN-02-01, REQ-TRN-02-02 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B133 | REQ-TRN-02-02 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B134 | REQ-TRN-02-03, REQ-TRN-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0218 | REQ-TRN-02-01 | fix: Refill до final quota. |
| remaining:0219 | REQ-TRN-02-02, REQ-TRN-02-04 | qualify: Actual owner/source. |
| remaining:0226 | REQ-TRN-02-02, REQ-TRN-02-03, REQ-TRN-02-04 | qualify: Native custody/resources. |
| remaining:0227 | REQ-TRN-02-02 | fix: Stale fixture assertion reconcile. |
| remaining:0228 | REQ-TRN-02-03, REQ-TRN-02-04 | capability: HNSW/portable consumer chain. |
| remaining:0229 | REQ-TRN-02-03, REQ-TRN-02-04 | qualify: Snapshot/recovery cost. |

## 3. Нормативные REQ и конкретное решение

### REQ-TRN-02-01 — fix
Compatibility filtering выполняется до окончательной квоты discovery либо через bounded refill с явным exhaustion status.

**Решение на существующих владельцах.** find_similar_runs использовать existing index-owner filter, если он действительно поддерживает exact binding, либо повторный bounded расширяющий query с дедупом visited keys и лимитом scanned/results/work. Сохранять tenant/split/space predicates, не увеличивать fixed multiplier как доказательство полноты. Пустой bounded result маркируется budget_exhausted/no_compatible_in_scanned, не no_history_anywhere. Exact known ref не проходит ANN повторно.
**Приёмка:** TEST-TRN-02-01.

### REQ-TRN-02-02 — qualify
Квалифицировать exact Core snapshot/cache custody и ресурсные пределы на настоящем store.

**Решение на существующих владельцах.** Сохранить full ref+fingerprint cache key, immutable bytes, fresh decode/revalidation, LRU128/32MiB. Actual read_core_json_artifact на hit повторяет selected profile/owner checks. Обновление run alias выбирает новый ref, старый replay остаётся старым. Исправить stale test coverage key только по actual producer schema, не добавлением fabricated coverage.
**Приёмка:** TEST-TRN-02-02.

### REQ-TRN-02-03 — qualify
Поддержанное native поколение index/metadata публикуется целиком и сохраняется после failed mutation/load.

**Решение на существующих владельцах.** Исполнить existing RLock/_Generation snapshot→poison→native add→publish/restore. Tiny hnswlib0.8.0 с capacity/shape negatives, controlled backend partial mutation failure и actual rollback load; при failed rollback все операции unavailable. Load полностью строит candidate index до switch. Не заменить native failure только preflight fixture; fault wrapper должен делегировать реальной мутации до сбоя.
**Приёмка:** TEST-TRN-02-03.

### REQ-TRN-02-04 — capability
Замкнуть actual portable rows producer→selected artifact→runtime consumer и измерить native стоимость.

**Решение на существующих владельцах.** Existing save portable v3 создаёт bounded JSON+NPZ selected members/lineage из approved source rows; передать этот ref существующему candidate-only runtime loader, а не caller fabricated label. from_portable_artifact проверяет dtype/finite/count/dimension/work limits и rebuild. Default external native graph trust refusal сохранить; explicit native opt-in требует отдельного origin qualification. Измерить snapshot-per-add/recovery/rebuild на tiny native profile без выдуманного throughput SLA.
**Приёмка:** TEST-TRN-02-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-TRN-02-01 · NOT_RUN
- **Setup:** Ordered index: два incompatible ближайших, третий compatible; requested top_k1; малый и достаточный scan budgets; exact history ref.
- **Действие:** Actual discovery→binding filter→history read, проверить количество index calls и budget status.
- **Oracle:** При достаточном bounded budget compatible третий возвращён; при меньшем честная неполнота, не ложное отсутствие; selected ref читается без второго ANN.
- **Positive / negative / boundary:** Нельзя снять tenant фильтр; не обещать exhaustive recall ANN; новая совместимая source запись работает без case-ID branch.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-02-02 · NOT_RUN
- **Setup:** Old/new history same run с scores1/9, selected profile drift, cache corruption,129 small entries и oversized payload; actual authorised CAS.
- **Действие:** Warm/cold/fresh reads, caller mutation, eviction и access revocation; измерить payload reads отдельно от owner checks.
- **Oracle:** Последовательность old/new/old/alias/fresh =1/9/1/9/9; cache hit не обходит current custody; oversized читается без caching; eviction не удаляет provenance.
- **Positive / negative / boundary:** 32MiB — retained payload budget, не RSS ceiling; corruption ≠ empty; missing key не nearest fallback.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-02-03 · NOT_RUN
- **Setup:** Десятки deterministic finite vectors, owned metadata, current generation digest; add/update/query/save concurrent barriers; candidate corrupt bundle.
- **Действие:** Actual add/load/query и fresh process read; failure injection после actual add, затем rollback failure variant.
- **Oracle:** Old или new согласованный key/vector/meta набор; ни один reader не видит mixed generation; rollback восстанавливает прежние bytes/binding; failed rollback не выдаёт данные.
- **Positive / negative / boundary:** Capacity не снимается; metadata callbacks/cycles/reserved keys отвергнуты до mutation; обычный query не snapshot/rebuild.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-02-04 · NOT_RUN
- **Setup:** Actual source history→portable rows artifact; fresh process без предварительно allocated index; malformed NPZ/profile/lineage и превышение лимитов.
- **Действие:** Producer persist→runtime selected ref load→candidate discovery→TRN-01 target consumer, записать time/peak memory/calls.
- **Oracle:** Совместимый ресурс даёт полезный hit/readback; tamper не публикует candidate generation; normal reads не rebuild; actual стоимость/ограничения видимы.
- **Positive / negative / boundary:** Bytes cap не total memory; native graph admission не включать по умолчанию ради теста; fixture interface PASS не native stress.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-D, E02-X03**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- TRN-01 — численный admission и target reevaluation, не ANN similarity.
- Existing Core/CAS owner сохраняет доступ/profile на cached read; не второй authority cache.
- Тяжёлый tiny native job один coordinated slot, без одновременного GP job.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py:184–216](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py#L184-L216) — `    def find_similar_runs(`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py:465–497](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py#L465-L497) — `    def _history_cache_key(`.
- [policy-engine/src/polisyos/scientist/agent/vector_memory.py:362–394](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/agent/vector_memory.py#L362-L394) — `    def add(`.
- [policy-engine/src/polisyos/scientist/agent/vector_memory.py:317–349](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/agent/vector_memory.py#L317-L349) — `    def from_portable_artifact(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0335 | REQ-TRN-02-01, REQ-TRN-02-02, TEST-TRN-02-01, TEST-TRN-02-02 | Discovered selected profile preserved. |
| preserve:0336 | REQ-TRN-02-01, REQ-TRN-02-02, TEST-TRN-02-01, TEST-TRN-02-02 | No second ANN; corruption distinct from empty. |
| preserve:0342 | REQ-TRN-02-02, TEST-TRN-02-02 | Old/new snapshots and current alias distinct. |
| preserve:0343 | REQ-TRN-02-02, TEST-TRN-02-02 | Fresh decode, repeated source check,128 entries/32MiB. |
| preserve:0344 | REQ-TRN-02-03, TEST-TRN-02-03 | Lock across query/mutation/save capture. |
| preserve:0345 | REQ-TRN-02-03, TEST-TRN-02-03 | Partial mutation restore, failed rollback unavailable. |
| preserve:0346 | REQ-TRN-02-03, REQ-TRN-02-04, TEST-TRN-02-03, TEST-TRN-02-04 | Candidate load before publish; portable row and default native trust guard. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/TRN-02.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
