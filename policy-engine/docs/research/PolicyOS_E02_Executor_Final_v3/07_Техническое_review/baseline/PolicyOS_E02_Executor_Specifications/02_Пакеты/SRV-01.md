# SRV-01 — Атомарное принятие tell и явный split-service контракт

**LANE-02 · LA-014 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/SRV-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/SRV-01_исходные_строки.txt), строки 1850–1944.
**Практический результат:** Один ответ принимается ровно один раз, цель запроса не теряется, а lightweight contracts и законные исторические адреса продолжают работать.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- DTO/protocol owner and lazy compatibility aliases
- historical serialized record identities
- shared lifecycle/run_state; no duplicated history/best mutation
- detached proposals/results; unknown and sequential duplicate refusal
- malformed typed input cannot silently become scalar best
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C14_остатки:0 | REQ-SRV-01-01 | fix: Reservation/prepare/commit у общего owner. |
| audit-residual:C14_остатки:1 | REQ-SRV-01-02 | fix: Не терять explicit args. |
| audit-residual:C14_остатки:2 | REQ-SRV-01-03 | capability: Достижимый split admission/accounting. |
| audit-residual:C14_остатки:3 | REQ-SRV-01-04 | qualify: Actual cold/installed identity scope. |
| LA-014 | REQ-SRV-01-01, REQ-SRV-01-02, REQ-SRV-01-03, REQ-SRV-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0378 | REQ-SRV-01-01 | fix: Atomic acceptance вместе с CTL01runaffinity. |
| remaining:0379 | REQ-SRV-01-02 | fix: Явный goal/space contract. |
| remaining:0380 | REQ-SRV-01-03 | capability: Shared primitives/реальный external owner, not implied parity. |
| remaining:0381 | REQ-SRV-01-04 | qualify: Native installed/import/consumer census. |

## 3. Нормативные REQ и конкретное решение

### REQ-SRV-01-01 — fix
Pending→applying→completed и owner state commit должны быть единым run-affine exactly-once переходом; overlapping/reentrant tell не мутирует state дважды и не выдаёт KeyError после повторной записи.

**Решение на существующих владельцах.** SRV-01 owns общий atomic acceptance у lifecycle/service: под owner synchronization проверить CTL-01generation и зарезервировать pending token; callback/validation готовят immutable delta без history mutation; commit под тем же owner проверяет reservation+generation и применяет SearchRunState transition один раз, затемcompleted. Reentry того же token отказан до callback; different IDs допускаются согласно declared serialization policy. При failure доcommit release/retry policy явна, послеcommit возврат/повтор видит committed outcome. Не держать не-reentrant lock вокруг внешнего callback и не просто менять del наpop.
**Приёмка:** TEST-SRV-01-01.

### REQ-SRV-01-02 — fix
Explicit goal/search_space в ask не могут молча игнорироваться: поддержанный профиль передаёт их actual generator с правилом конфликтов; unsupported explicit input отвергается до работы.

**Решение на существующих владельцах.** Finite caller census по SearchService.ask определить supported typed goal/space shapes. Предпочесть existing config/context semantic owner: normalize и validate explicit arguments, сравнить с context/config; конфликт адресный, provenance сохраняется в service envelope. Compatibility None/None остаётся. Если конкретный adapter договором допускает толькоNone — явный narrow refusal, не скрытая потеря; положительный supported route задаёт meaningful цель без нового goalowner.
**Приёмка:** TEST-SRV-01-02.

### REQ-SRV-01-03 — capability
Manual ask/tell должен иметь объявленного владельца generation/work accounting и нового resource admission; приём уже выполненного допустимого ответа не запрещается только поздним exhaustion.

**Решение на существующих владельцах.** Не копировать full loop. В existing lifecycle expose shared prepare-generation/check/account/finalize primitives CTL01/03. Split profile либо uses them, либо требует explicit external orchestrator owner/contract, проверяемый фактическим caller. Ask до нового paid work проверяет cap/budget; tell принимает source-bound выполненную работу, сверяя run/token/eligibility и не authorizing новый расход.
**Приёмка:** TEST-SRV-01-03.

### REQ-SRV-01-04 — qualify
Contracts-only import, DTO identity/lazy aliases и historical serialization должны оставаться совместимыми в реальной поставке; adapter не становится вторым редактором history/best.

**Решение на существующих владельцах.** Extraction уже есть: contracts.py DTO/protocols, adapters.py concrete, lifecycle/run_state mutation. Сохранить historical __module__ и resolved dataclass annotations. Finite import/string/public consumer census; fresh subprocess trap controller/funnel, supported installed imports и preserved pickle fixtures. Удаление aliases только после explicit retirement evidence, не по словуlegacy.
**Приёмка:** TEST-SRV-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-SRV-01-01 · NOT_RUN
- **Setup:** Actual owner/DTO, две threads с barrier и samecandidate, callbackreentry, twodifferentIDs, generationreplace; invalid payload beforecommit.
- **Действие:** Пройти оба overlap witnesses, затем законный последовательный duplicate/retry и reversed completion разныхIDs.
- **Oracle:** Ровно1history/count/transition для одного token, второй явный duplicate/inflight outcome доmutation; два разных subject сохраняются; pending восстановим при precommit invalid.
- **Positive / negative / boundary:** Не заявлять два физических расчёта или billing effects по count; admission reset/epoch sharedCTL01.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-01-02 · NOT_RUN
- **Setup:** Две разные цели/непересекающиеся space при samecontext; None; conflictingcontext; actual generator observing accepted normalized input.
- **Действие:** Вызвать native ask, materialize proposal и пройти selected consumer.
- **Oracle:** Supported goal/space меняет эффективный generator input и результат/constraints, конфликт не silent override; Nonecompat unchanged.
- **Positive / negative / boundary:** Одного context.update недостаточно; LLM proposal не доказательство source truth.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-01-03 · NOT_RUN
- **Setup:** Actual split caller, full-run comparison, persistentempty/sentinels, бюджет exhausted доask и послеactualevaluation передtell.
- **Действие:** Сравнить одинаковый admitted workload через APIs и позднее принятие завершённого результата.
- **Oracle:** Счётчики имеют одну declared unit, newwork запрещён когда нельзя, late validtell сохраняет knowledge без extra work; reason/pending/partial читаемы.
- **Positive / negative / boundary:** Manual3asks не автоматически бесконечныйloop, однако generationcost/attempts не0; no implied full-run parity без owner.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-SRV-01-04 · NOT_RUN
- **Setup:** Existing tests/unit/remediation/test_srv_01.py и tests/unit/scientist/search/test_contracts.py; supported wheel/environment, oldrecordfixtures.
- **Действие:** Coldimport contracts доaliasaccess; затем aliases/roundtrip/actualasktell и malformedtyped feedback.
- **Oracle:** Concrete runtime не eager по contract-only path; identity та же, old histories читаются, unknown/duplicate/invalidtyped не bypass best.
- **Positive / negative / boundary:** Rootpackage может иметь свои dependencies: проверять заявленную границу, не обещать любойimport лёгким; no newSearchService framework.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-A**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- SRV-01 owns atomic acceptance API; CTL-01 owns run-generation replacement. Реализовать одним согласованным shared-owner patch, не два locks.
- CTL-03 supplies work/cost/typed eligibility semantics; SRV-03 validates actual autotune split/full consumer and LA015 closure.
- LA014 closed only after ownactualcontracts/caller/evidence; protocol presence не acceptance.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Исправление расширяет надёжное продолжение содержательного поиска и не требует нового планировщика. Поздний полезный результат сохраняется без выдачи права на новый расход.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/service.py:111–143](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py#L111-L143) — `def tell`.
- [policy-engine/src/polisyos/scientist/methods/search/service.py:46–78](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py#L46-L78) — `def ask`.
- [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py:254–286](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py#L254-L286) — `def _accept_tell`.
- [policy-engine/src/polisyos/scientist/methods/search/contracts.py:609–631](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/contracts.py#L609-L631) — `def __getattr__`.
- [policy-engine/src/polisyos/scientist/methods/search/adapters.py:28–60](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/adapters.py#L28-L60) — `class LegacySearchServiceAdapter`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0613 | REQ-SRV-01-04, TEST-SRV-01-04 | DTO/protocol owner and lazy compatibility aliases |
| preserve:0614 | REQ-SRV-01-04, TEST-SRV-01-04 | historical serialized record identities |
| preserve:0615 | REQ-SRV-01-01, REQ-SRV-01-04, TEST-SRV-01-01, TEST-SRV-01-04 | shared lifecycle/run_state; no duplicated history/best mutation |
| preserve:0616 | REQ-SRV-01-01, TEST-SRV-01-01 | detached proposals/results; unknown and sequential duplicate refusal |
| preserve:0617 | REQ-SRV-01-01, REQ-SRV-01-04, TEST-SRV-01-01, TEST-SRV-01-04 | malformed typed input cannot silently become scalar best |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/SRV-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
