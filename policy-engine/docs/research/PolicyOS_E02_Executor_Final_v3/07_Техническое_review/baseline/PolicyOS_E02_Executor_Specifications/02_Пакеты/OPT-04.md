# OPT-04 — Сопоставимый champion и атомарная публикация

**LANE-02 · B116, B117 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/OPT-04.md), [исходная карточка](../05_Основания/Аудит/05_Источники/OPT-04_исходные_строки.txt), строки 2600–2696.
**Практический результат:** Реальная оценка правильного кандидата улучшает champion на одной явной comparison basis; развитие цели разрешено через честный переход.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Полные candidate/evaluation/suite/split/loop проверки и source edges.
- Неподтверждённый baseline и MethodJob execution provenance не допускаются молча.
- Стабильный per-loop flock вокруг current read/comparison/publish.
- Atomic replace и claim pointer+basis envelope.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C21_остатки:0 | REQ-OPT-04-01 | fix: Comparison basis до числа. |
| audit-residual:C21_остатки:1 | REQ-OPT-04-02, REQ-OPT-04-04 | qualify: Реальные owners, не fixture CAS. |
| audit-residual:C21_остатки:2 | REQ-OPT-04-02 | capability: Положительное измерение baseline, guard сохранён. |
| audit-residual:C21_остатки:3 | REQ-OPT-04-04 | qualify: Native достижимость отдельно, не объявленный bypass. |
| audit-residual:C21_остатки:4 | REQ-OPT-04-03 | qualify: Фактическая deployment durability. |
| B116 | REQ-OPT-04-01, REQ-OPT-04-02, REQ-OPT-04-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B117 | REQ-OPT-04-03 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0189 | REQ-OPT-04-01 | fix: Полный profile и explicit transition. |
| remaining:0190 | REQ-OPT-04-02, REQ-OPT-04-04 | capability: Native chain и measured seeded baseline. |
| remaining:0191 | REQ-OPT-04-02, REQ-OPT-04-03 | qualify: Actual authority consumer и crash/durability. |
| remaining:0192 | REQ-OPT-04-03 | qualify: Deployment scope не выводить из local filesystem. |

## 3. Нормативные REQ и конкретное решение

### REQ-OPT-04-01 — fix
Incumbent и challenger сравниваются по полной metric/split/direction/unit basis; смена basis — явный переход.

**Решение на существующих владельцах.** В _consider_promotion_locked до current.metrics.get использовать сохранённый promoted_by_policy/compare_split и canonical effective profile. Несовпадение не missing metric→automatic promotion. Существующий evaluator переоценивает incumbent на новой suite/profile либо создаётся отдельная начальная точка сравнения с explicit transition и predecessor linkage. Не объявлять старое число измеренным в новой единице. OPT-01 определяет coordinate identity, registry её потребляет.
**Приёмка:** TEST-OPT-04-01.

### REQ-OPT-04-02 — capability
Обеспечить положительный loader-first путь seeded baseline→active suite evaluation→bound champion.

**Решение на существующих владельцах.** В существующем seed_loop_baseline/runner хранить unknown status честно; если suite basis не установлена, запланировать/выполнить существующим evaluator измерение baseline на активной suite и связать candidate/evaluation/profile refs. Только такой bound result участвует в сравнении. Не добавлять фиктивную suite metadata к старому score. Проверить MethodJob trusted execution issuer/consumer и specialised claim путь отдельно; техническое число не право исполнения.
**Приёмка:** TEST-OPT-04-02.

### REQ-OPT-04-03 — qualify
Квалифицировать существующий cross-process compare-and-publish и envelope crash consistency в заявленном deployment profile.

**Решение на существующих владельцах.** Сохранить стабильный per-loop flock вокруг current read/binding/compare/publish, дорогой evaluator снаружи. Actual pointer+basis claim envelope пишется единым atomic replace; legacy reader не переименовывать как новый. Проверить deployment filesystem semantics и durability требование; если требуется surviving power loss, обосновать fsync parent directory/эквивалентный existing storage primitive. Не строить distributed registry по локальному тесту.
**Приёмка:** TEST-OPT-04-03.

### REQ-OPT-04-04 — qualify
Finite/source admission прямого registry доказать на настоящем producer и canonical CAS, не permissive fixture.

**Решение на существующих владельцах.** Исполнить actual persist helpers с NaN/Inf и обычным finite bootstrap; проверить кто уже отвергает invalid. Только при реально поддержанном public direct API без upstream guard добавить адресную finite validation перед pointer write. Не регистрировать C21-G03 как доказанный native дефект без достижимого replay. Fresh reader обязан читать каждый успешно опубликованный pointer.
**Приёмка:** TEST-OPT-04-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-OPT-04-01 · NOT_RUN
- **Setup:** Последовательные policies одной suite: holdout10→selection20, metric score→other=-999, maximize→minimize, USD→EUR; same-basis1→3→2.
- **Действие:** Вызвать actual registry и loader; для нового profile выполнить явную baseline reevaluation/transition.
- **Oracle:** Same-basis итог3; каждое mismatch даёт адресный transition-required и не меняет старый pointer. После реальной переоценки новая задача может работать.
- **Positive / negative / boundary:** Не запрещать изменение цели навсегда; не снимать canonical specialised claim policy checks.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-04-02 · NOT_RUN
- **Setup:** Actual authorized evaluator, temporary native CAS, seeded baseline без suite refs; normal candidate; MethodJob provenance missing и valid assigned test principal.
- **Действие:** Loader→baseline evaluation→registry promotion→fresh loader; затем source ref/profile mismatch и отсутствующий trusted execution provenance.
- **Oracle:** Полезный measured baseline и candidate путь работает; unknown seed сохраняет champion_suite_basis_unknown до измерения; чужие candidate/loop/suite/split/profile не меняют pointer.
- **Positive / negative / boundary:** Один generic benchmark не квалифицирует specialised claim authority; если authorized issuer unavailable — точный BLOCKED, не guard removal.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-04-03 · NOT_RUN
- **Setup:** Два управляемых процесса, current1, slow2 остановлен после predecessor read, fast3; actual native store/loader. Fault injection до replace и на declared crash boundaries.
- **Действие:** Исполнить race, fresh reader и sanctioned envelope consumer; отдельный no-lock removal control только test profile.
- **Oracle:** Итог3 и каждый writer сравнивает актуального predecessor; old-or-new согласованный pointer+basis после отказа; no-lock control воспроизводит2.
- **Positive / negative / boundary:** Local POSIX PASS не network FS/multihost PASS; если deployment не заявлен, scope local filesystem и limitation явны.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-04-04 · NOT_RUN
- **Setup:** Native CanonSpec default запрета NaN/Inf, bootstrap finite0 и invalid values; exact source manifest/profile.
- **Действие:** Persist evaluation→consider_promotion→fresh loader; отдельно documented direct entry если существует.
- **Oracle:** Finite0 допустим при valid source; invalid не создаёт unreadable null pointer; upstream denial зафиксирован как owner результата.
- **Positive / negative / boundary:** Не дублировать несовместимые error codes; candidate/evaluation/suite exact refs и lineage checks не ослаблены.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-B**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- OPT-01 — comparison coordinate contract; OPT-02/03 — source-admitted evaluations, не issuer полномочий.
- SRV-03/OPT-02 разделяют runtime.py: один writer.
- Existing claim verifier владеет appointment/signature/expiry; этот пакет интегрирует разрешённый test principal, не создаёт право из score.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/autotune/registry.py:724–756](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/registry.py#L724-L756) — `    def _consider_promotion_locked(`.
- [policy-engine/src/polisyos/scientist/methods/autotune/registry.py:943–975](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/registry.py#L943-L975) — `    def _promotion_lock(`.
- [policy-engine/src/polisyos/scientist/methods/autotune/runtime.py:152–184](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/runtime.py#L152-L184) — `def seed_loop_baseline(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0303 | REQ-OPT-04-01, REQ-OPT-04-02, REQ-OPT-04-04, TEST-OPT-04-01, TEST-OPT-04-02, TEST-OPT-04-04 | Полные candidate/evaluation/suite/split/loop проверки и source edges. |
| preserve:0304 | REQ-OPT-04-02, TEST-OPT-04-02 | Неподтверждённый baseline и MethodJob execution provenance не допускаются молча. |
| preserve:0305 | REQ-OPT-04-03, TEST-OPT-04-03 | Стабильный per-loop flock вокруг current read/comparison/publish. |
| preserve:0306 | REQ-OPT-04-03, TEST-OPT-04-03 | Atomic replace и claim pointer+basis envelope. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/OPT-04.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
