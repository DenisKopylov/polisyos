# TRN-01 — Верный исторический Evaluation и допустимый численный перенос

> Предложение review-v2: только спецификация; product implementation и все TEST остаются NOT_RUN. Основание: PS-F02.

**LANE-02 · B128, B130, B131, B132 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/TRN-01.md), [исходная карточка](../05_Основания/Аудит/05_Источники/TRN-01_исходные_строки.txt), строки 3045–3182.
**Практический результат:** Сохранённые пригодные наблюдения доходят до target training либо честной переоценки, не меняя время, feasibility и происхождение.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Actual raw/direction/assessment constructor.
- Malformed records retain identity/reason.
- MIN/MAX normalized ordering.
- Source diversity and refill without limit excess.
- Exact source/target fingerprints, rules and units.
- Actual native GP source receipt boundary; candidate-only reevaluation route.
- Distinct typed IDs, raw metric, empty holdout, nonpromotable.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C25_остатки:0 | REQ-TRN-01-01 | fix: Event time не restore time. |
| audit-residual:C25_остатки:1 | REQ-TRN-01-01 | fix: Wire boolean validation. |
| audit-residual:C25_остатки:2 | REQ-TRN-01-04 | capability: Historical result либо actual resolved benchmark. |
| audit-residual:C25_остатки:3 | REQ-TRN-01-03 | qualify: Native chain и fixture contract. |
| audit-residual:C25_остатки:4 | REQ-TRN-01-02 | qualify: Explicit diagnostics/admitted quota. |
| B128 | REQ-TRN-01-01, REQ-TRN-01-03 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B130 | REQ-TRN-01-02 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B131 | REQ-TRN-01-03 | qualify: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B132 | REQ-TRN-01-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0215 | REQ-TRN-01-01 | fix: Исходное время восстановлено. |
| remaining:0216 | REQ-TRN-01-01 | fix: Strict boolean. |
| remaining:0217 | REQ-TRN-01-03 | qualify: Native owner qualification. |
| remaining:0220 | REQ-TRN-01-02 | qualify: Два вида quotas. |
| remaining:0221 | REQ-TRN-01-02, REQ-TRN-01-03 | qualify: Benefit отдельно от correctness. |
| remaining:0222 | REQ-TRN-01-01 | fix: History fidelity. |
| remaining:0223 | REQ-TRN-01-03 | qualify: Actual tenant/receipt/source consumer. |
| remaining:0224 | REQ-TRN-01-04 | capability: True source suite/split/profile. |
| remaining:0225 | REQ-TRN-01-04 | qualify: Caller census, не вымышленная activation. |

## 3. Нормативные REQ и конкретное решение

### REQ-TRN-01-01 — fix
History reconstruction сохраняет event timestamp и принимает stage_a_passed только как настоящий boolean.

**Решение на существующих владельцах.** В TransferLearningManager._deserialize_evaluation разбирать timestamp из schema5 и передавать в Evaluation; restore_time, если нужен, отдельное diagnostic поле. Проверить timezone по общему TRN-03 contract. stage_a_passed требует type(value) is bool; malformed string/число дают уже существующий rejected row с candidate ID/reason, не truthiness. Legacy отсутствующий timestamp не now: explicit historical_time_unknown и ограниченный reuse/migration contract.
**Приёмка:** TEST-TRN-01-01.

### REQ-TRN-01-02 — qualify
Квоты diagnostic delivery и допустимого training corpus имеют разные явные counts/лимиты; MIN/MAX ordering сохраняется.

**Решение на существующих владельцах.** Существующий round-robin diversity и normalized ordering оставить. Расширить result envelope либо documented caller policy: returned/admitted/rejected/unavailable counts, общий bounded diagnostics и отдельный admissible max. Если API обещает max_evals всего выдаваемых rows, не менять молча; отдельный request admitted_quota с bounded refill и retained rejection refs. Не удалять плохие valid examples, полезные learning corpus, ради best-only.
**Приёмка:** TEST-TRN-01-02.

### REQ-TRN-01-03 — qualify
Native source compatibility и candidate-only reevaluation остаются разными полезными маршрутами.

**Решение на существующих владельцах.** Пройти existing WarmStartBridge→BayesianCandidateGenerator.warm_start_for_context с target MethodJob profile, exact selected Core history/header, actual objective rule/source receipt verifier и authenticated tenant owner. Same fingerprint не заменяет source admission. Для несовместимых чисел разрешить existing candidate-only hint и новое target evaluation без копирования старого score. Проверить required exact lookup fixture method вместо ослабления reader. Более широкий measured_observation reuse обсуждается только отдельным DEC-OPT-03-02: actual measurement admission не обязан наследовать source proposer fit, но новый profile требует собственной source/compatibility qualification. Это optional extension; существующий fitted-native guard, candidate-only reevaluation и TEST-TRN-01-03 сохраняются без ослабления и не ожидают эту развилку.
**Приёмка:** TEST-TRN-01-03.

### REQ-TRN-01-04 — capability
Обратный benchmark bridge не создаёт измерение target suite из исторического Evaluation.

**Решение на существующих владельцах.** Сначала подтвердить caller census: production runtime сейчас передаёт Evaluation напрямую. Сохранить этот основной путь. Если evaluations_to_benchmarks нужен explicit caller, требовать source resolver настоящего candidate/suite/split/selected profile и raw objective, не синтаксический ref; иначе возвращать historical Evaluation/typed unsupported, а target evaluator создаёт новый benchmark. Не активировать неиспользуемый converter ради coverage.
**Приёмка:** TEST-TRN-01-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-TRN-01-01 · NOT_RUN
- **Setup:** JSON round-trip timestamp2001-01-01T00:00:00+00:00, boolean false/true, string false,0,1,null,missing; typed source assessment.
- **Действие:** Actual register_run→CAS→history read→deserialize→bridge; malformed rows среди пригодных.
- **Oracle:** Время2001 сохраняется; false infeasible; true при действительном source проходит; malformed видим как rejected и не valid training; остальные rows не пропадают.
- **Positive / negative / boundary:** Не восстановить старый value= constructor или swallow-all. Raw objective/direction/provenance/metadata сохраняются.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-01-02 · NOT_RUN
- **Setup:** MIN1/2/9, MAX1/2/9; histories1+3 при limit4; rejected row в первом source и ещё valid во втором.
- **Действие:** Actual transfer selection→consumer corpus, сравнить declared quota semantics и порядок.
- **Oracle:** MIN first1/MAX first9; общий предел не превышен, доступная квота распределена; diagnostics не считаются numerical observations; admitted request заполняется до доступного bound.
- **Positive / negative / boundary:** Source diversity сохраняется; ties не меняют identity; performance/GP benefit измерять отдельно, не обещать по количеству rows.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-01-03 · NOT_RUN
- **Setup:** Compatible saved native fitted observation и target; по одному drift bounds/split/unit/origin/tenant/direction/rule; отдельная похожая, но numerical-incompatible идея.
- **Действие:** Actual store→bridge→source verifier→GP corpus; отдельно idea→target reevaluation→новый evaluation ref.
- **Oracle:** Только совместимое source-admitted наблюдение входит один раз; drift исключается до неправильного reuse; новая полезная идея может быть измерена на target и получить новый результат.
- **Positive / negative / boundary:** Closed holdout не становится training; candidate_only не configured_native_gp; source-only fixture contradiction не назван native test failure.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-TRN-01-04 · NOT_RUN
- **Setup:** Два actual distinct candidate refs, source hidden/selection split и suite, raw MAX0.8/normalized-0.8, отсутствующий selected profile и zero-digest syntactic-only ref.
- **Действие:** Разрешить source и round-trip через фактический выбранный caller; отдельно target reevaluation.
- **Oracle:** Source identity/split/profile не переименованы в selection/warm_start; raw0.8 не normalized-0.8; params вне metrics, holdout отсутствует если не измерен.
- **Positive / negative / boundary:** Nonpromotable сохраняется; syntactic-only candidate не объявлен существующим; отсутствие production caller явно зафиксировано, не новый blocker основного warm-start.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-D, E02-I02-B, E02-X03**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- TRN-02 владеет exact ref/cache/discovery; общий transfer.py один writer.
- OPT-02 — canonical training params; OPT-03 — learned GP/source-fit qualification.
- TRN-03 определяет aware timestamp boundary; historical unknown не автоматически UTC-now.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py:537–569](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py#L537-L569) — `    def _deserialize_evaluation(`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py:222–254](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/transfer.py#L222-L254) — `    def get_warm_start_evaluations(`.
- [policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py:78–110](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/warm_start.py#L78-L110) — `    def evaluations_to_benchmarks(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0333 | REQ-TRN-01-01, TEST-TRN-01-01 | Actual raw/direction/assessment constructor. |
| preserve:0334 | REQ-TRN-01-01, TEST-TRN-01-01 | Malformed records retain identity/reason. |
| preserve:0337 | REQ-TRN-01-02, TEST-TRN-01-02 | MIN/MAX normalized ordering. |
| preserve:0338 | REQ-TRN-01-02, TEST-TRN-01-02 | Source diversity and refill without limit excess. |
| preserve:0339 | REQ-TRN-01-03, TEST-TRN-01-03 | Exact source/target fingerprints, rules and units. |
| preserve:0340 | REQ-TRN-01-03, TEST-TRN-01-03 | Actual native GP source receipt boundary; candidate-only reevaluation route. |
| preserve:0341 | REQ-TRN-01-04, TEST-TRN-01-04 | Distinct typed IDs, raw metric, empty holdout, nonpromotable. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/TRN-01.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
