# CTL-02 — Содержательный subject и атомарный воспроизводимый checkpoint

**LANE-02 · B124, B125, B126 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/CTL-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/CTL-02_исходные_строки.txt), строки 2045–2160.
**Практический результат:** Сохранённое исследование продолжается тем же RNG/Sobol потоком; невалидный restore не портит живой state, а предметные даты не исчезают из идентичности.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Все JSON-native предметные поля, включая dates и underscore names.
- Явный typed strategy/service envelope; recomputed identity и payload reconciliation.
- Версионный Python codec и нормальный JSON/new-process replay.
- Отдельные metadata/model shapes и независимые потоки.
- Фиксированный seed, actual backend/version, space/cache/cursor and prefix validation.
- True fresh stream и явно маркированный fallback.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C16_остатки:0 | REQ-CTL-02-03 | fix: Export сохраняет unknownSobol. |
| audit-residual:C16_остатки:1 | REQ-CTL-02-02 | fix: Validate before commit. |
| audit-residual:C16_остатки:2 | REQ-CTL-02-01 | qualify: Tests догоняют typed subject contract. |
| audit-residual:C16_остатки:3 | REQ-CTL-02-04 | capability: Измеренно убрать quadratic prefix для релевантного профиля. |
| audit-residual:C16_остатки:4 | REQ-CTL-02-05 | qualify: Actual concrete producer/consumer. |
| B124 | REQ-CTL-02-01 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B125 | REQ-CTL-02-02, REQ-CTL-02-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B126 | REQ-CTL-02-03, REQ-CTL-02-04, REQ-CTL-02-05 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0206 | REQ-CTL-02-01 | qualify: Согласовать rawsubjecttests, не restorestripping. |
| remaining:0207 | REQ-CTL-02-01, REQ-CTL-02-05 | qualify: Actualtypedproducer/reader. |
| remaining:0208 | REQ-CTL-02-02 | fix: Full cursor/gauss validation и atomic commit. |
| remaining:0209 | REQ-CTL-02-02, REQ-CTL-02-05 | qualify: Concrete/checkpoint на supported runtime. |
| remaining:0210 | REQ-CTL-02-03 | fix: No compatibility laundering. |
| remaining:0211 | REQ-CTL-02-04 | capability: Relevant prefix performance, не claim global cost. |
| remaining:0212 | REQ-CTL-02-04, REQ-CTL-02-05 | qualify: Actual backend/consumer. |

## 3. Нормативные REQ и конкретное решение

### REQ-CTL-02-01 — qualify
Generic subject hash должен включать все JSON-native substantive поля; только типизированный service/strategy envelope исключает известную transport metadata.

**Решение на существующих владельцах.** Сохранить policy_candidate_hash/current frontier и CandidateStrategyContext. Обновить stale test_frontier raw trace/_debug/generated_at expectations: raw dict сам subject, нельзя восстановить suffix stripping. Actual PolicyCandidateSchema producer/evaluation/reader проверяет materialized payload identity; unsupported metadata адресно ошибочна, не молча сброшена.
**Приёмка:** TEST-CTL-02-01.

### REQ-CTL-02-02 — fix
Python RNG checkpoint restore должен полностью валидировать schema/version/state words/final cursor/finite gauss и применяться атомарно ко всему strategy state.

**Решение на существующих владельцах.** В _validate_python_random_state отдельно state words uint32 и final index в диапазоне конкретной поддержанной версии; gauss_next finite numeric или None, не bool. Decode/temporary Random.setstate и остальные model/Sobol shape checks выполняются до commit живого объекта. Только успех меняет _rng/iteration/cache/model; failure сохраняет весь pre-state. Не reseed, не gauss0, не lists→tuples в metadata.
**Приёмка:** TEST-CTL-02-02.

### REQ-CTL-02-03 — fix
Missing/incompatible Sobol state должен оставаться missing/incompatible после любого export/import; новый fresh stream отличим от неизвестной истории.

**Решение на существующих владельцах.** get_state/_sobol_state обязаны сохранять _sobol_checkpoint_compatible=False через existing versioned codec explicit availability/reason либо отсутствие Sobol block. Не выпускать пустой valid cache/cursor 0 за восстановленную историю. Python stream можно продолжать отдельно; explicit new stream operation имеет новую identity и не replay.
**Приёмка:** TEST-CTL-02-03.

### REQ-CTL-02-04 — capability
Sobol prefix должен совпадать при incremental/batch/restore и actual backend/version; устранение повторной подготовки допускается без смены эксперимента и измеряется на выбранном workload.

**Решение на существующих владельцах.** Сохранить fixed seed/full space/cache/cursor/backend/scramble contract. При relevant sequential growth использовать живой sampler continuation выбранного бэкенда, восстановить/verify prefix один раз, затем draw недостающий хвост; не recreate/fast-forward from zero каждый раз. Cache bounded memory profile явен; backend failure fallback маркируется, не silent replay. Измерить prepared points отдельно policy calls.
**Приёмка:** TEST-CTL-02-04.

### REQ-CTL-02-05 — qualify
Каждый заявленный concrete strategy/model state должен пройти persisted native new-process roundtrip и быть реально потреблён следующим предложением/оцениванием.

**Решение на существующих владельцах.** Конечный census используемых strategies; base Random/Sobol не proof GP model. OPT-03 owns model/conditioning checkpoint; CTL-02 общий RNG codec/atomic restore. Сохранить metadata/model shapes и независимые streams, provenance backend. Actual StrategyAdapter→MethodJob/spec binding через OPT-02, no fake point only.
**Приёмка:** TEST-CTL-02-05.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-CTL-02-01 · NOT_RUN
- **Setup:** Current test_candidate_identity_semantics/test_frontier; реальные starts_at и raw underscore/date fields, typed trace/service iteration controls.
- **Действие:** Изменить только дату действия, затем только typed transport ID; сохранить два несравнимых front points и перечитать.
- **Oracle:** Даты дают разные субъекты/два points; transport changes не subject; forged hash/payload mismatch refused; JSON key order инвариантен.
- **Positive / negative / boundary:** Научный seed сохраняется в своей basis; no arbitrary volatile name heuristic.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-02-02 · NOT_RUN
- **Setup:** Checkpoint после uniform и gauss с непустым cache, invalid cursor 625, NaN/inf gauss, foreign version/model state; actual native Python 3.14.
- **Действие:** set_state failure then getstate/next uniform/next gauss; valid JSON→новый процесс restore.
- **Oracle:** После отказа bytes state/следующие числа равны контролю, valid restore точно совпадает uniform+gauss+iteration/model metadata.
- **Positive / negative / boundary:** Unversioned legacy JSON не тихий replay; допустимый direct legacy tuple сохраняет явный профиль.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-02-03 · NOT_RUN
- **Setup:** Versioned Python-only checkpoint, direct legacy tuple, invalid Sobol и genuine fresh unused strategy.
- **Действие:** Restore→Sobol refusal→get_state→JSON→new strategy restore→Sobol; отдельно fresh positive.
- **Oracle:** Повторный round trip не launders compatibility; exact reason сохраняется; genuine fresh работает.
- **Positive / negative / boundary:** Не запрещать все legacy/Random states, не новый seed под старой меткой.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-02-04 · NOT_RUN
- **Setup:** Existing test_space_codec SciPy/PyTorch supported locked versions;32 sequential vs one batch, checkpoint after 3, backend drift и true Random fallback.
- **Действие:** Сравнить первые 32/next point, count generated points/calls, corrupt prefix/cursor/space.
- **Oracle:** Sequence identical, changed backend denied for replay; relevant improvement не O(n²) prefix preparation; policy calls неизменны.
- **Positive / negative / boundary:** Не обещать 2^m balance для неполного prefix, не запускать дополнительные policy jobs ради степени 2.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-CTL-02-05 · NOT_RUN
- **Setup:** Supported random и используемый Bayesian/model checkpoint, temporary artifact store, input space/source fingerprint.
- **Действие:** Произвести/checkpoint/exit/restore и сравнить следующие реальные proposals/consumed inputs с continuous run; corrupted foreign model negative.
- **Oracle:** Точная continuation в declared profile и meaningful consumer, not just JSON parse; несовместимость не переименовывается в fresh.
- **Positive / negative / boundary:** Isolated 3.13 sampler наблюдения унаследованы, но native 3.14 acceptance отдельна.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-B**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- OPT-02 исполняемый параметр/identity до checkpoint consumer; OPT03model state owner.
- CTL-02 owns общий codec/atomic restore, не independent RNG fixes в стратегиях; SRV-03 проверяет actual resume.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.

Детерминизм — свойство повторяемости, не независимость samples иликачествоисследования. Новый compatiblebackend требует честной version/profilequalification, а не запрет всех новых методов.

## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/strategies/base.py:117–200](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/base.py#L117-L200) — `def set_state`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/base.py:438–460](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/base.py#L438-L460) — `def _validate_python_random_state`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/base.py:256–288](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/base.py#L256-L288) — `def _sobol_state`.
- [policy-engine/src/polisyos/scientist/methods/search/frontier.py:175–207](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/frontier.py#L175-L207) — `def policy_candidate_hash`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0325 | REQ-CTL-02-01, TEST-CTL-02-01 | Все JSON-native предметные поля, включая dates и underscore names. |
| preserve:0326 | REQ-CTL-02-01, TEST-CTL-02-01 | Явный typed strategy/service envelope; recomputed identity и payload reconciliation. |
| preserve:0327 | REQ-CTL-02-02, REQ-CTL-02-05, TEST-CTL-02-02, TEST-CTL-02-05 | Версионный Python codec и нормальный JSON/new-process replay. |
| preserve:0328 | REQ-CTL-02-02, REQ-CTL-02-05, TEST-CTL-02-02, TEST-CTL-02-05 | Отдельные metadata/model shapes и независимые потоки. |
| preserve:0329 | REQ-CTL-02-03, REQ-CTL-02-04, TEST-CTL-02-03, TEST-CTL-02-04 | Фиксированный seed, actual backend/version, space/cache/cursor and prefix validation. |
| preserve:0330 | REQ-CTL-02-03, REQ-CTL-02-04, TEST-CTL-02-03, TEST-CTL-02-04 | True fresh stream и явно маркированный fallback. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/CTL-02.json). Аудит охватил 127/127; это не означает выполненных 127 ремонтов.
