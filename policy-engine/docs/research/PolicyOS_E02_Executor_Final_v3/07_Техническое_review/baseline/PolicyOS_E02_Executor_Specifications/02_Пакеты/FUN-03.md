# FUN-03 — Текущее same-basis знание и разрешённый commit

**LANE-02 · B161, B163, B164 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/FUN-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/FUN-03_исходные_строки.txt), строки 2933–3044.
**Практический результат:** Поздняя реальная оценка уточняет своё знание, калибровка не выдумывает измерения, а нормальный разрешённый promotion действительно проходит protected writer.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Numeric-free unknown; exact basis/generation/predecessor relation.
- Independent obligations/contested/history preserved by source-traced owner.
- Empty no_promotion/not_established без measured drift.
- Actual corpus JSONsnapshot restore and preserved report routing projection.
- No effects under caps; normal bool callback не authority.
- Ready payload read-only; score admission remains distinct.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C24_остатки:0 | REQ-FUN-03-02 | fix: Typed metric state. |
| audit-residual:C24_остатки:1 | REQ-FUN-03-03 | fix: Denominator-bound criterion. |
| audit-residual:C24_остатки:2 | REQ-FUN-03-01 | capability: Source-traced blueprint context, существующий v2 owner. |
| audit-residual:C24_остатки:3 | REQ-FUN-03-03 | capability: Existing snapshot producer wiring. |
| audit-residual:C24_остатки:4 | REQ-FUN-03-04 | capability: Positive protected writer без bool bypass. |
| audit-residual:C24_остатки:5 | REQ-FUN-03-01, REQ-FUN-03-03, REQ-FUN-03-04 | qualify: Actual native chain и stale tests reconciliation. |
| B161 | REQ-FUN-03-01 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B163 | REQ-FUN-03-02, REQ-FUN-03-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B164 | REQ-FUN-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0273 | REQ-FUN-03-01 | capability: Complete actual selected method basis. |
| remaining:0274 | REQ-FUN-03-01 | qualify: Native current consumer replay. |
| remaining:0277 | REQ-FUN-03-02 | fix: Insufficient/undefined ≠ measured zero. |
| remaining:0278 | REQ-FUN-03-03 | fix: Empty criterion GAP. |
| remaining:0279 | REQ-FUN-03-03 | capability: Snapshot handoff и compatible scope. |
| remaining:0280 | REQ-FUN-03-04 | capability: Actual permit/writer bridge. |
| remaining:0281 | REQ-FUN-03-04 | qualify: Normal plus revoke protected execution. |

## 3. Нормативные REQ и конкретное решение

### REQ-FUN-03-01 — capability
Замкнуть blueprint selected-method/source context на существующий task admission→first assessment→fresh current reader.

**Решение на существующих владельцах.** В _build_search_uncertainty_owner_context получить actual выбранные rule/profile/procedure/ABI/params/seed/input/semantic scope из existing selection/method owners и owned HTE request projection. Проверять refs/content/tenant/epoch до dispatch через existing produce_search_task_admission. По actual Runtime completion записать first assessment existing uncertainty owner, затем fresh read. Не заполнить missing_slices константами и не создать второй truth registry; RuntimeHTE v2 путь уже существует.
**Приёмка:** TEST-FUN-03-01.

### REQ-FUN-03-02 — fix
Calibration различает empty, insufficient samples, undefined rank variation и measured poor correlation.

**Решение на существующих владельцах.** У CorrelationTracker ввести единый typed metric availability/reason/eligible count, используемый compute_metrics/routing/drift/report. Для len≤2 сохранить no_promotion/insufficient_window, не observed correlation0. Constant ranks дают undefined_variation, не measured drift. Достаточные finite pairs используют существующий Spearman с average ties. Исследование и сбор калибровки разрешены без ложного promotion.
**Приёмка:** TEST-FUN-03-02.

### REQ-FUN-03-03 — fix
Acceptance criterion без eligible denominator — GAP, а snapshot producer связывает совместимый corpus для следующего накопления.

**Решение на существующих владельцах.** build_calibration_report берёт availability и denominator от tracker; false_negative_rate empty/rejected_count0 становится None/GAP с причиной, настоящий observed0 при ненулевом denominator может PASS. В metadata включить existing to_snapshot с version и actual tenant/model/objective/calibration scope. Node resolver восстанавливает только compatible snapshot, иначе сохраняет routing/history projection и адресную причину без нового пустого tracker.
**Приёмка:** TEST-FUN-03-03.

### REQ-FUN-03-04 — capability
Интегрировать положительный L6 route через typed owner-issued permit и revoke-serialized commit, сохранив caps/read-only.

**Решение на существующих владельцах.** FUN-03 владеет funnel adapter: pure prepare получает subject/attempt/predecessor/purpose binding, запрашивает permit у назначенного existing promotion authority и передаёт actual protected writer. Writer независимо в одной serialization domain с revoke проверяет current generation/expiry/authority и predecessor, затем commit и durable receipt. Если подходящего port нет, реализовать минимальный port в существующем writer, не bool callback и не параллельный registry. До wiring bridge_missing остаётся честным; normal candidate work не блокируется. Начальная точка адаптации: run_policy_blueprint_runtime._policy_promotion_runner → policy_runtime_support.run_promotion_with_evidence → его actual runtime writer. Проверить конкретно subject/attempt/predecessor binding и общий revoke/commit serialization predicate. OPT-04 champion pointer не автоматически тот же институциональный policy act; DUR-02 lease fence не заменяет promotion permit.
**Приёмка:** TEST-FUN-03-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-FUN-03-01 · NOT_RUN
- **Setup:** Actual selected tiny method с declared quantity/population/outcome/units и persisted source, initial unknown obligation, independent risk0.8, два competing completion и другое generation.
- **Действие:** Blueprint→admission→actual method→completion association→record_first_assessment→new-process current read; затем изменить одну basis или удалить child.
- **Oracle:** Своё unknown заменено связанным assessment0.1, independent risk0.8/history сохранены; second same-generation contested, late old generation history-only; missing/tamper not_established.
- **Positive / negative / boundary:** 0.1 здесь заранее заданное валидное assessment test source по declared procedure, не автоматически scientific probability; native method oracle и source profile зафиксировать по DEC-FUN-03-01.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-03-02 · NOT_RUN
- **Setup:** 0,1,2 aligned pairs; пять x=1..5 и y=x; y=6-x; пять constant pairs; ties с independent rank oracle.
- **Действие:** Actual tracker→metrics→routing→stage5/report.
- **Oracle:** Aligned5 rho=1, inverse5 rho=-1; constant/short rho unavailable с причиной, no measured PROMOTION_BAN alert; оба public interfaces согласованы.
- **Positive / negative / boundary:** No_promotion cap не снимается ради green; отрицательный measured корпус сохраняет actual drift alert.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-03-03 · NOT_RUN
- **Setup:** Empty report; five eligible rejected-A examples без false negatives; known snapshot scope и incompatible tenant/objective; genuine JSON/CAS fresh read.
- **Действие:** Builder→Markdown+JSON→node from_snapshot→добавить новую source-bound pair→new report.
- **Oracle:** Пустой criterion не PASS; measured zero корректен; compatible corpus count5→6; incompatible scope не сливается; missing snapshot не стирает существующий report routing.
- **Positive / negative / boundary:** Старые inf/obsolete feedback assertions примирить с None/structured v2; native pytest не объявлять уже падавшим.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-FUN-03-04 · NOT_RUN
- **Setup:** Authorized test principal и sandbox target, actual configured writer; normal permit, no_promotion/reduced_judge/auto_cap, revoked-after-preflight permit, stale predecessor, retained payload.
- **Действие:** L6 prepare→issuer→writer commit→fresh receipt reader; синхронизированная revoke между preflight и commit; retry того же attempt.
- **Oracle:** Normal разрешённый effect ровно1, retry idempotent; revoke-before-commit effect0; caps не вызывают producer; retained payload read-only без нового effect.
- **Positive / negative / boundary:** Technical APPROVE/score или подпись сами по себе не authority. Не создавать credentials/назначение тестовым кодом без authorised fixture; unavailable owner даёт precise BLOCKED, не снятие guard.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-C**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- FUN-01 — attempts/lineage; FUN-02 — diagnostic interval origin и aggregate.
- Существующий search uncertainty owner единственный хранит task/current generations; UQS shared integration согласует source semantics, не второй ledger.
- FUN-03 — L6 adapter, existing protected promotion writer — final effect authority; назначение issuer/port фиксируется DEC-FUN-03-02, не автоматически CYC-05 readiness issuer.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

- **DEC-FUN-03-01**: Какой уже реализованный selected method/source profile квалифицирует первый blueprint assessment? Owner: FUN-03 с existing uncertainty/method owner. Варианты: существующий RuntimeHTE completion profile с полным selected method basis; другой already-supported source-owned method с точным inference contract. Выбор по: Actual method ABI/input/profile refs, units/population/contrast, independent numerical oracle и complete task admission. Обязательный выход: Один bounded positive fixture с формулой/данными/expected assessment и negative basis mutation до execution; не выдумывать универсальную0.1.
- **DEC-FUN-03-02**: Какой назначенный protected promotion writer и issuer обслуживает L6? Owner: FUN-03 и existing promotion authority owner. Варианты: адаптация существующего typed issuer/commit port; минимальное расширение существующего writer если port отсутствует. Выбор по: Caller/owner census, назначение test principal, текущий revoke serialization и predecessor operation. Обязательный выход: Точный symbol/interface, единственный owner, permit schema и commit/revoke linearization test до реализации; отсутствие port означает capability work, не снятие normal gate.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/stages.py:682–714](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py#L682-L714) — `    def _metrics_for_records(`.
- [policy-engine/src/polisyos/scientist/methods/search/calibration_report.py:80–112](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/calibration_report.py#L80-L112) — `def build_calibration_report(`.
- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py:244–276](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_blueprint_runtime_engine.py#L244-L276) — `def _build_search_uncertainty_owner_context(`.
- [policy-engine/src/polisyos/scientist/methods/search/funnel/level6_promotion.py:64–96](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/level6_promotion.py#L64-L96) — `    def evaluate(`.

- [policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py:1530–1562](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/nodes/builtins/decide/policy_runtime_support.py#L1530-L1562) — existing promotion integration entry, не уже квалифицированный revoke/commit port.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0403 | REQ-FUN-03-01, TEST-FUN-03-01 | Numeric-free unknown; exact basis/generation/predecessor relation. |
| preserve:0404 | REQ-FUN-03-01, TEST-FUN-03-01 | Independent obligations/contested/history preserved by source-traced owner. |
| preserve:0407 | REQ-FUN-03-02, TEST-FUN-03-02 | Empty no_promotion/not_established без measured drift. |
| preserve:0408 | REQ-FUN-03-03, TEST-FUN-03-03 | Actual corpus JSONsnapshot restore and preserved report routing projection. |
| preserve:0409 | REQ-FUN-03-04, TEST-FUN-03-04 | No effects under caps; normal bool callback не authority. |
| preserve:0410 | REQ-FUN-03-01, REQ-FUN-03-04, TEST-FUN-03-01, TEST-FUN-03-04 | Ready payload read-only; score admission remains distinct. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/FUN-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
