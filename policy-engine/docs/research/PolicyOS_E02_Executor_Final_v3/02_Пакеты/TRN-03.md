# TRN-03 — Предметный context и согласованные evidence clocks

**LANE-02 · B135, B136, B137 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/TRN-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/TRN-03_исходные_строки.txt), строки 3301–3412.
**Практический результат:** Полезный lesson переносится по явным фильтрам, не омолаживается чтением и одинаково объясняется в search и report после restart.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Typed/JSON subject fields preserved.
- Defaults distinct, malformed/conflicting declarations refused.
- Authenticated status requires live owner seam.
- Threshold/trust/source-run preserved across paths.
- Final quota after effective quality, no rejected materialization writes.
- Source identity and target namespace distinct.
- Cold/warm/fresh demotion stable for ordinary old card.
- Daily access sidecar, no full snapshot write on reads.
- Transfer keeps original evidence time and lower grade.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C27_остатки:0 | REQ-TRN-03-02 | fix: Current effective grade versus raw historical. |
| audit-residual:C27_остатки:1 | REQ-TRN-03-01 | fix: Naive refused before arithmetic. |
| audit-residual:C27_остатки:2 | REQ-TRN-03-03 | fix: Conservative initial projection or resolved new assessment. |
| audit-residual:C27_остатки:3 | REQ-TRN-03-03, REQ-TRN-03-04 | qualify: Actual source/access/revalidation, not confidence probability. |
| B135 | REQ-TRN-03-01 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B136 | REQ-TRN-03-04 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B137 | REQ-TRN-03-02, REQ-TRN-03-03, REQ-TRN-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0230 | REQ-TRN-03-01 | fix: Timezone boundary. |
| remaining:0231 | REQ-TRN-03-01, REQ-TRN-03-04 | qualify: Actual auth/source qualification. |
| remaining:0232 | REQ-TRN-03-04 | qualify: Native persisted consumer. |
| remaining:0233 | REQ-TRN-03-02 | fix: Historical/current labels. |
| remaining:0234 | REQ-TRN-03-03 | fix: Source anchor handoff. |
| remaining:0235 | REQ-TRN-03-01 | fix: All affected datetime boundaries. |
| remaining:0236 | REQ-TRN-03-03, REQ-TRN-03-04 | qualify: Real revalidation semantics. |

## 3. Нормативные REQ и конкретное решение

### REQ-TRN-03-01 — fix
Typed/JSON timestamp имеет timezone-aware contract до age arithmetic; explicit subject и live tenant ownership сохраняются.

**Решение на существующих владельцах.** В TransferContext/resolve_transfer_context и связанных LessonCard/IndexEntry boundary требовать timezone-aware timestamp, нормализовать offset в UTC с сохранением instant; naive new input адресно отказать. Legacy naive evidence не угадывать: explicit migration only при достоверном producer timezone, иначе unknown time/limited. Согласовать TRN-01 history event time. Current conflicting declarations остаются refusal, не silent override.
**Приёмка:** TEST-TRN-03-01.

### REQ-TRN-03-02 — fix
Query, top_patterns и calibration lesson projection явно различают historical и current effective grade.

**Решение на существующих владельцах.** В lessons.top_patterns и calibration_report._resolve_top_lessons использовать existing age-aware projection либо отдельные historical_confidence/trust и current_effective_* с as_of/evidence_anchor/status. Сохранить исходную0.9/local как historical, но не тем же unlabeled current полем. Snapshot projection проверяет scope/time contract, не просто raw entry copy. Actual lifecycle hints уже query_with_transfer — не переписывать исправленный consumer.
**Приёмка:** TEST-TRN-03-02.

### REQ-TRN-03-03 — fix
Initial transfer и target restart имеют одинаковую обоснованную evidence freshness.

**Решение на существующих владельцах.** Для selected older card при newer aggregate occurrence выбрать conservative selected-card anchor уже при materialize_transfer; это default минимальный ремонт. Если требуется использовать более свежее assessment, переносить и разрешать actual source-bound assessment ref/anchor через existing provenance, не last_seen=now. Повышение только по содержательному owner assessment, а не UUID/new timestamp. Сохранить caller-demoted grade.
**Приёмка:** TEST-TRN-03-03.

### REQ-TRN-03-04 — qualify
Квалифицировать native funnel→lesson→search и общие local/transfer predicates без лишней materialization.

**Решение на существующих владельцах.** Actual orchestrator lesson producer требует terminal/AVAILABLE score по существующему контракту; record_local сохраняет source/traces. _SearchLifecycleOwner._build_lesson_hints получает query_with_transfer с current trust/provenance. Проверить source_run/domain/stage/tags/threshold до/после projection и quota после eligibility; authorized cross-domain route сохраняется. Usage daily sidecar не evidence clock и не полный CAS snapshot.
**Приёмка:** TEST-TRN-03-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-TRN-03-01 · NOT_RUN
- **Setup:** Typed и JSON education/discovery/r, aware UTC и +03:00 того же instant; naive2020-01-01; real test tenant owner и forged authenticated label.
- **Действие:** Resolve→compute_provenance_weight→lesson query/transfer; same-scope важно для достижения age branch.
- **Oracle:** Aware варианты дают одинаковый age; naive отказ до TypeError; defaults не затирают explicit fields; live owner определяет tenant.
- **Positive / negative / boundary:** Неизвестная область isolated fallback; новый subject требует согласованного context, не arbitrary override права.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-03-02 · NOT_RUN
- **Setup:** 100-day .9/local lesson при TTL90, now fixed; cold/warm/fresh registry и persisted snapshot report.
- **Действие:** Query→top_patterns→build_calibration_report→JSON/Markdown→fresh reader.
- **Oracle:** Тот же ref имеет current .5/low_confidence всюду либо явно historical .9 отдельно; strict .8/local query пуст; clocks объяснены.
- **Positive / negative / boundary:** Чтения не empirical revalidation; отсутствие возраста не превращается в current .9; старую полезную идею не удалять.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-03-03 · NOT_RUN
- **Setup:** Новая и затем100-day карточка одной signature, selected old ref; immediate transfer→new target process; отдельное verified new assessment с source ref и invalidation.
- **Действие:** Materialize→persist target→fresh query; source anchor missing/revoked и allowed assessment update.
- **Oracle:** Conservative path сразу и после restart .5/low_confidence; actual new assessment может создать новую связанную версию, не переписать old evidence; invalid source не materializes.
- **Positive / negative / boundary:** Existing conservative restart test сохраняется; .9 не восстановить простым переносом агрегатного last_seen.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-03-04 · NOT_RUN
- **Setup:** Actual authorised source/store/profile, разрешённый .9 source fiscal→labor с weight.65; old source.5→weight.325; invalid trust/threshold/source_run; matching lower-ranked candidate.
- **Действие:** Funnel→persisted lesson→fresh registry→actual hint consumer; повторные reads и source invalidation.
- **Oracle:** Полезный разрешённый hint доходит с source_run/origin_domain/target namespace; rejected results не создают writes; limit1 заполняется подходящим after-filter; repeated reads0 CAS writes и ≤1 daily sidecar update.
- **Positive / negative / boundary:** Confidence/TTL/provenance weight — внутренние правила, не probability истинности. Empirical revalidation требует конкретного source procedure, не marker/ref alone.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-D, E02-X03**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- TRN-01 использует общий aware-time contract для history; timestamp policy один, не duplicated defaults.
- FUN-03 calibration report использует тот же effective lesson projection; report snapshot не новая authority.
- Actual tenant/CAS owner подтверждает доступ; lesson similarity — proposal, не научное или институциональное полномочие.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/transfer_context.py:352–384](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/transfer_context.py#L352-L384) — `def resolve_transfer_context(`.
- [policy-engine/src/polisyos/scientist/methods/search/transfer_context.py:308–340](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/transfer_context.py#L308-L340) — `def compute_provenance_weight(`.
- [policy-engine/src/polisyos/scientist/methods/search/lessons.py:872–904](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lessons.py#L872-L904) — `    def top_patterns(`.
- [policy-engine/src/polisyos/scientist/methods/search/lessons.py:784–816](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lessons.py#L784-L816) — `    def materialize_transfer(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0347 | REQ-TRN-03-01, TEST-TRN-03-01 | Typed/JSON subject fields preserved. |
| preserve:0348 | REQ-TRN-03-01, TEST-TRN-03-01 | Defaults distinct, malformed/conflicting declarations refused. |
| preserve:0349 | REQ-TRN-03-01, REQ-TRN-03-04, TEST-TRN-03-01, TEST-TRN-03-04 | Authenticated status requires live owner seam. |
| preserve:0350 | REQ-TRN-03-04, TEST-TRN-03-04 | Threshold/trust/source-run preserved across paths. |
| preserve:0351 | REQ-TRN-03-04, TEST-TRN-03-04 | Final quota after effective quality, no rejected materialization writes. |
| preserve:0352 | REQ-TRN-03-03, REQ-TRN-03-04, TEST-TRN-03-03, TEST-TRN-03-04 | Source identity and target namespace distinct. |
| preserve:0353 | REQ-TRN-03-02, REQ-TRN-03-03, TEST-TRN-03-02, TEST-TRN-03-03 | Cold/warm/fresh demotion stable for ordinary old card. |
| preserve:0354 | REQ-TRN-03-04, TEST-TRN-03-04 | Daily access sidecar, no full snapshot write on reads. |
| preserve:0355 | REQ-TRN-03-03, TEST-TRN-03-03 | Transfer keeps original evidence time and lower grade. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/TRN-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
