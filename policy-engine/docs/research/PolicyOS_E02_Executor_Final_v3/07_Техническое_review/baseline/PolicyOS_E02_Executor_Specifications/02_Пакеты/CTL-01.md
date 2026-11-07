# CTL-01 — Принадлежность run и доступный результат прерывания

**LANE-02 · B118, B119, LA-015 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CTL-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CTL-01_исходные_строки.txt), строки 1589–1729.
**Практический результат:** Поздний ответ не попадает в другое исследование; уже полученная работа остаётся доступной после ошибки/отмены, а пустые предложения завершаются без выдуманного научного исчерпания.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- fresh allocated state instead of clear
- deep result snapshots
- full-run non-reentrant guard
- legitimate same-session continuation
- separate generation/evaluation counters
- finite empty streak
- post-generation/pre-evaluation budget check
- original error/cancel propagation
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C12_остатки:0 | REQ-CTL-01-01 | fix: Run generation binds all drivers; reset admission safe. |
| audit-residual:C12_остатки:1 | REQ-CTL-01-02 | capability: Намеренное расширение raise-path, не просто stale test fix. |
| audit-residual:C12_остатки:2 | REQ-CTL-01-03 | fix: Typed producer reason/deadline. |
| audit-residual:C12_остатки:3 | REQ-CTL-01-03 | shared: CTL-03 owns sentinel physical-work cap. |
| audit-residual:C12_остатки:4 | REQ-CTL-01-01, REQ-CTL-01-02 | shared: SRV-01 owns split API accounting/admission composition. |
| audit-residual:C12_остатки:5 | REQ-CTL-01-04 | fix: Evaluator fixture соответствует constructor. |
| B118 | REQ-CTL-01-01, REQ-CTL-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B119 | REQ-CTL-01-02, REQ-CTL-01-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| LA-015 | REQ-CTL-01-01, REQ-CTL-01-02, REQ-CTL-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0193 | REQ-CTL-01-01 | fix: Owner generation affinity. |
| remaining:0194 | REQ-CTL-01-01 | fix: Reset после admission. |
| remaining:0195 | REQ-CTL-01-04 | qualify: Actual caller/readback. |
| remaining:0196 | REQ-CTL-01-02 | capability: Доступный partial и attempt accounting. |
| remaining:0197 | REQ-CTL-01-03 | fix: Attempt stop не scientific exhaustion. |
| remaining:0198 | REQ-CTL-01-02, REQ-CTL-01-04 | qualify: Actual provider/ledger/caller. |

## 3. Нормативные REQ и конкретное решение

### REQ-CTL-01-01 — fix
Pending proposal и tell должны принадлежать точному run/generation owner; новый admitted run не принимает старый ответ, а отказ admission не сбрасывает pending.

**Решение на существующих владельцах.** Добавить/использовать monotonic generation token у _SearchLifecycleOwner/SearchRunState и bind его в service proposal envelope/pending, не subject payload. Reset driver state только после owner lock admission. Fresh run заменяет generation; same-session ask/tell сохраняет её; явный resume принимает конкретную прежнюю generation. Atomic pending claim/commit единый SRV-01; CTL-01 owns generation/replace contract, не второй lock в facade.
**Приёмка:** TEST-CTL-01-01.

### REQ-CTL-01-02 — capability
Каждая начатая generation/evaluation attempt и её failed/cancelled outcome должны оставаться учтены; interruption сохраняет detached partial run с причиной и актуальным owner budget, затем распространяет исходную ошибку/отмену.

**Решение на существующих владельцах.** В native driver/lifecycle разделить started/completed/failed/cancelled counters; existing generation_attempts может остаться completed-call с явной единицей. При исключении до нормального finish вызвать bounded failure finalization у existing owner: snapshot completed history/frontier/telemetry, reconcile durable budget, persist через existing caller artifact/event либо typed interruption attachment, terminal failed/cancelled. Сохранять исходный exception/cancellation; не catch-as-empty, не auto paid retry. SRV-03 owns фактическое сохранение/возобновление в runner.
**Приёмка:** TEST-CTL-01-02.

### REQ-CTL-01-03 — fix
Persistent empty должен ограниченно завершать попытки с причиной, отличной от подтверждённого exhaustion; transient empty может привести к настоящему кандидату без busy loop.

**Решение на существующих владельцах.** Сохранить separate generation_attempts/max_empty streak. Использовать существующий typed generation transition для proposal/exhausted/repair/transient, source reason если он дан. У bare[] после count cap писать attempt_limit/unknown-exhaustion, а не научную полноту. Repair требует meaningful input change; transient retry имеет deadline/backoff и actual budget admission.
**Приёмка:** TEST-CTL-01-03.

### REQ-CTL-01-04 — qualify
Fresh runs и возвращённые snapshots должны оставаться независимыми; реальные callers сохраняют новый state-owner и законные evaluator ports.

**Решение на существующих владельцах.** Сохранить _begin_native_run новый SearchRunState/deep snapshots/reset scoped diversity/stopping; warm initial_evaluations копируются и source-qualified, не случайная старая history. Исправить test_search_controller_uses_facade_default_metrics_binding: дать StageA/B ports до assertion metrics, не ослаблять constructor. Историческую relocation parity проверять только на том commit, не требовать сегодняшнего AST equality.
**Приёмка:** TEST-CTL-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CTL-01-01 · NOT_RUN
- **Setup:** Один lifecycle owner, adaptersA/B; A ask(old), B fullrun(new), A late tell; отдельно занятый full-run lock и исходный pending.
- **Действие:** Пройти обе interleavings, then legal same-session out-of-order different IDs.
- **Oracle:** Old tell адресно stale-run до state change; rejected new run сохраняет pending, valid same-generation tell работает; previous detached result неизменен.
- **Positive / negative / boundary:** Новый ID не мигрирует старую историю; внешний generator/warm corpus не обнулять произвольно.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-01-02 · NOT_RUN
- **Setup:** Один good candidate, затем generation RuntimeError/CancelledError после settlement; evaluatorfailure и отказ до dispatch отдельно; actual ledger и result reader.
- **Действие:** Запустить full route, получить typed interruption/partial ref, открыть её новым reader, затем fresh run.
- **Oracle:** Partial история доступна под прежним run; attempts и committed spend точны; lock released, original error/cancel propagates, fresh run не стирает сохранённый результат.
- **Positive / negative / boundary:** Незавершённый run не RUNNING навечно и не converged; cancellation не swallowed; settledzero/cache согласно owner, не fake price.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-01-03 · NOT_RUN
- **Setup:** Existing empty tests; generator[]always, []then realcandidate, explicit exhausted, repair-needed и transient source.
- **Действие:** Пройти actual driver stopping до/после generation и перед evaluation.
- **Oracle:** Finite calls, useful transient candidate оценён, empty reason доступен reader; generation spend не потерян и scientific evaluation count не увеличен пустотой.
- **Positive / negative / boundary:** Никаких fabricated candidates, увеличения hard-limit или short busy-loop; sentinel-only общий cap у CTL-03.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-01-04 · NOT_RUN
- **Setup:** Actual tests/unit/scientist/search/test_search_loop.py fresh/concurrent tests и test_controller_api.py metrics test; два native runs, mutable nested payload.
- **Действие:** A/B same owner vs two fresh owners; mutate returned snapshots; attempt overlapping fullrun; actual autotune reader.
- **Oracle:** История/лучший/counters independent; rejected overlap не меняет state; typedfixture достигает metrics assertion; реальный consumer читает верный subject.
- **Positive / negative / boundary:** Не clear старый list; permitted warm restart явно задан; LA-015 accountable closure SRV-03, не здесь.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-A**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- OPT-01 objective/source identity before accepted scientific best; чтение поregistry не integration order.
- CTL-01 owner generation/failure-finalize; SRV-01 atomic pending/commit и split lifecycle; CTL-03 counters/budget; SRV-03 actual runner and LA-015 closure.
- service/lifecycle/run_state общий один writer на согласованный atomic patch, не independent facade locks.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Содержательный поиск выигрывает от сохранения частичного знания и явного продолжения; error не должен выглядеть успешным empty или стирать полезный результат.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/service.py:177–209](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py#L177-L209) — `def run_search`.
- [policy-engine/src/polisyos/scientist/methods/search/service.py:199–231](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py#L199-L231) — `def _run_locked`.
- [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py:234–266](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py#L234-L266) — `def _prepare_service_run`.
- [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py:437–469](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py#L437-L469) — `def _begin_native_run`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0307 | REQ-CTL-01-04, TEST-CTL-01-04 | fresh allocated state instead of clear |
| preserve:0308 | REQ-CTL-01-04, TEST-CTL-01-04 | deep result snapshots |
| preserve:0309 | REQ-CTL-01-01, REQ-CTL-01-04, TEST-CTL-01-01, TEST-CTL-01-04 | full-run non-reentrant guard |
| preserve:0310 | REQ-CTL-01-01, TEST-CTL-01-01 | legitimate same-session continuation |
| preserve:0311 | REQ-CTL-01-02, REQ-CTL-01-03, TEST-CTL-01-02, TEST-CTL-01-03 | separate generation/evaluation counters |
| preserve:0312 | REQ-CTL-01-03, TEST-CTL-01-03 | finite empty streak |
| preserve:0313 | REQ-CTL-01-02, REQ-CTL-01-03, TEST-CTL-01-02, TEST-CTL-01-03 | post-generation/pre-evaluation budget check |
| preserve:0314 | REQ-CTL-01-02, TEST-CTL-01-02 | original error/cancel propagation |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CTL-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
