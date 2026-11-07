# OPT-02 — Параметры реального действия и честное происхождение предложения

> Предложение review-v2: только спецификация; product implementation и все TEST остаются NOT_RUN. Основание: PS-F03.

**LANE-02 · B112, B113, B127 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/OPT-02.md), [исходная карточка](../05_Основания/Аудит/05_Источники/OPT-02_исходные_строки.txt), строки 2386–2504.
**Практический результат:** Настоящий SearchSpace ведёт от proposal к выполненному MethodJob и source-admitted history; конечное пространство не тратит работу на скрытые дубли.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Настоящий native SearchSpace и делегирование normalize/denormalize/Sobol/bounds.
- Работающая альтернативная стратегия не равна GP-ready.
- Нормализация фактических параметров, полные IDs и согласование identity.
- Missing score не становится successful zero; selected CAS/source/split ограничения.
- Сравнение integer/category по исполнению.
- Distinct continuous и явно независимые seed/replicate.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C19_остатки:0 | REQ-OPT-02-01 | fix: Расширить уже имеющийся guard на callers. |
| audit-residual:C19_остатки:1 | REQ-OPT-02-02 | fix: Fallback не новый Bayesian результат. |
| audit-residual:C19_остатки:2 | REQ-OPT-02-03 | fix: Canonical input до training. |
| audit-residual:C19_остатки:3 | REQ-OPT-02-03 | fix: Source-bound regression, не доказанный GP bypass. |
| audit-residual:C19_остатки:4 | REQ-OPT-02-04 | qualify: Реальные provenance/replicas, не metadata ID alone. |
| B112 | REQ-OPT-02-02 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B113 | REQ-OPT-02-03, REQ-OPT-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B127 | REQ-OPT-02-01, REQ-OPT-02-03, REQ-OPT-02-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0181 | REQ-OPT-02-02 | fix: Typed внешняя причина и reuse. |
| remaining:0182 | REQ-OPT-02-02, REQ-OPT-02-04 | qualify: Actual first suggest и отдельно GP readiness. |
| remaining:0183 | REQ-OPT-02-03, REQ-OPT-02-04 | qualify: Producer→history→training. |
| remaining:0184 | REQ-OPT-02-03, REQ-OPT-02-04 | fix: Standalone params и origin/replica. |
| remaining:0213 | REQ-OPT-02-01 | fix: Все proposal branches и exhaustion. |
| remaining:0214 | REQ-OPT-02-03 | fix: Canonical direct Evaluation admission. |

## 3. Нормативные REQ и конкретное решение

### REQ-OPT-02-01 — fix
Все cold, batch и fallback ветви проверяют effective-action identity в declared pending/completed scope; proposal budget exhaustion, доказанное finite-domain exhaustion и назначенная реплика различимы.

**Решение на существующих владельцах.** В BayesianOptimizer.suggest/suggest_batch применять единый existing SearchSpace/effective-execution identity owner ко всем ветвям и declared pending+completed history на том же measurement basis; просто вызвать нынешний pending-only _is_duplicate недостаточно. Batch добавляет уже выданные actions в pending. После bounded proposal search не возвращать заведомый дубль как новый: typed outcome proposal_search_budget_exhausted означает лишь лимит поиска. finite_domain_exhausted допустим только при complete feasible-domain census/enumeration в заранее ограниченном small-finite profile; большие mixed/continuous spaces не требуют полного перебора. При таком профиле использовать existing bounded enumeration либо locked BoTorch optimize_acqf_discrete unique/X_avoid, не новый optimizer. Replica разрешена по explicit measurement/seed intent и actual new provenance, а не cosmetic action ID или автоматически изменённому optimizer seed. Continuous без принятого допуска не округлять. Довести reason/status до service и сохранить useful partial result.
**Приёмка:** TEST-OPT-02-01.

### REQ-OPT-02-02 — fix
Внешний fallback сохраняет причину и reuse semantics, а native first suggest работает на существующем SearchSpace.

**Решение на существующих владельцах.** BayesianCandidateGenerator._fallback_generate возвращает совместимый с caller typed generation result/metadata: reuse_current_best/history, backend_unavailable либо wiring_error с проверенным candidate contract. Не считать context словарь кандидатом. Сохранить реально работающий random_no_botorch и различить wrapper_created/native_gp_ready. Провести metadata через codec/service без помещения reserved fields в mutation payload.
**Приёмка:** TEST-OPT-02-02.

### REQ-OPT-02-03 — fix
Training coordinate соответствует actual typed params на всех входах Evaluation, а не relaxed proposal.

**Решение на существующих владельцах.** Сохранить proposal_vector отдельно; в history и прямом Evaluation admission проверить полный набор имён, типы/range и canonical normalize(params) на версии пространства. При несовпадении params_normalized либо вычислить canonical значение по подтверждённым params с явной diagnostic provenance, либо адресно отклонить: не молча обучать на чужой координате. Standalone benchmark converter получает ту же обязательность параметров до permissive normalize.
**Приёмка:** TEST-OPT-02-03.

### REQ-OPT-02-04 — qualify
Допуск source history и самостоятельность реплик доказать actual producer→CAS→training, не числом evaluation_id.

**Решение на существующих владельцах.** Использовать SearchLoopRunner._evaluate_candidate и source resolver: сравнить candidate/evaluation/full selected profile, MethodJob input/data/split/unit basis. Одна provenance+replica в двух списках даёт одну строку; действительная новая MethodJob evaluation/seed сохраняет отдельную observation. Не снимать unitless/closed-holdout ограничения ради GP; unitless ATE может давать четыре разных exploratory actions без GP admission.
**Приёмка:** TEST-OPT-02-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-OPT-02-01 · NOT_RUN
- **Setup:** Бинарный n∈{0,1}; cold pending содержит первый Sobol action; batch_size=3; тот же набор после completed tell. Отдельно finite100-point domain с99seen и controlled20 duplicate proposals при свободном последнем action; bounded exact tiny enumeration; categorical aliases, близкие continuous и explicit genuine replica.
- **Действие:** Вызвать actual suggest/batch через wrapper/service на cold/no-backend/random/hard-limit/acquisition branches, проверить effective params до evaluator admission. Для bounded-failure control управлять внешним proposal stream, не подменять identity/admission; точный small-finite oracle перечисляет feasible actions независимо.
- **Oracle:** Cold/batch не возвращает pending или completed same-scope action как новый. Бинарный complete census имеет максимум два новых actions, затем finite_domain_exhausted. При99seen/100 и20 неудачных draws result только proposal_search_budget_exhausted, если полный census не выполнен: вероятность такого промаха при uniform draws0.99^20≈81.79%, свободный action ещё существует. Exact tiny enumerator находит последний action и лишь затем доказывает exhaustion. Genuine independent replica distinct; new ID/optimizer RNG label без measurement intent не оправдывает повтор.
- **Positive / negative / boundary:** Все branches bounded; отсутствие нового proposal не scientific convergence и не выдуманный evaluation. Declared stochastic repeats сохраняются; continuous values не сливаются без tolerance, changed measurement basis не history-global forever-dedup.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-02-02 · NOT_RUN
- **Setup:** Смешанный x∈[0,10], n integer, category A/B, log scale∈[1,100]; current_best x=7; отсутствующий backend и отдельная wiring exception.
- **Действие:** Actual generator.generate→native first suggest; затем fallback→consumer, без monkeypatch владельца SearchSpace.
- **Oracle:** Например x5,n0,B,scale10 нормализуется в (0.5,0,0,1,0.5); reuse явно повтор старого, wiring не назван Bayesian success; working alternative возвращает новый допустимый action.
- **Positive / negative / boundary:** Optional backend absence не запрещает candidate exploration; context-only не исполняется как политика; GP readiness требует отдельного native qualification.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-02-03 · NOT_RUN
- **Setup:** Integer n∈{0,1}: params n0 и relaxed0.9; standalone missing {}, out-of-range, bool-as-integer; две корректные continuous x0/x10.
- **Действие:** Actual converter/source verifier→training corpus, затем inspect tensor coordinates и readback.
- **Oracle:** Недопустимый вход не становится x0/центр0.5; accepted n0 canonical0; корректные x0/x10 различны, metrics остаются отдельно.
- **Positive / negative / boundary:** Missing/invalid scalar не SUCCESS0; full artifact IDs и split/unit guards остаются; relaxed diagnostic не теряется.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-02-04 · NOT_RUN
- **Setup:** Authorized tiny MethodJob run с declared objective units, две разные params и две разрешённые реплики одного action; duplicate origin через warm/current; fresh CAS reader.
- **Действие:** Пройти настоящий runner→history→_history_to_evaluations→training; выполнить найденный native unitless exploration контроль отдельно.
- **Oracle:** Training содержит только source-admitted строки с canonical params и полными refs; independent repeat учитывается ровно раз; source tamper/closed split исключён с причиной.
- **Positive / negative / boundary:** Generic candidate_only не повышается до configured_native_gp. Полезная exploration сохраняется при недопуске в численный corpus.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-B**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CTL-02 владеет portable RNG/base snapshot; OPT-03 GP continuation. Общий bayesian.py — последовательный writer.
- SRV-01 владеет атомарным tell, SRV-03 typed role envelope; не второй pending registry.
- TRN-01/02 обеспечивают совместимый source history, но similarity не admission.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

Отдельного свободного исследования не требуется: контракт, owner и различающий oracle заданы выше. Выявленный недостающий общий interface расширять только с конкретным producer/consumer и тестом, не новым параллельным framework.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:896–928](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L896-L928) — `    def suggest(`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:962–994](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L962-L994) — `    def suggest_batch(`.
- [policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py:869–901](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py#L869-L901) — `    def _fallback_generate(`.
- [policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py:1290–1322](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/bayesian_generator.py#L1290-L1322) — `def benchmark_to_evaluation(`.

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1601–1649](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1601-L1649) — bounded proposals and pending-only duplicate owner.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0295 | REQ-OPT-02-02, TEST-OPT-02-02 | Настоящий native SearchSpace и делегирование normalize/denormalize/Sobol/bounds. |
| preserve:0296 | REQ-OPT-02-02, TEST-OPT-02-02 | Работающая альтернативная стратегия не равна GP-ready. |
| preserve:0297 | REQ-OPT-02-03, REQ-OPT-02-04, TEST-OPT-02-03, TEST-OPT-02-04 | Нормализация фактических параметров, полные IDs и согласование identity. |
| preserve:0298 | REQ-OPT-02-03, REQ-OPT-02-04, TEST-OPT-02-03, TEST-OPT-02-04 | Missing score не становится successful zero; selected CAS/source/split ограничения. |
| preserve:0331 | REQ-OPT-02-01, REQ-OPT-02-03, TEST-OPT-02-01, TEST-OPT-02-03 | Сравнение integer/category по исполнению. |
| preserve:0332 | REQ-OPT-02-01, REQ-OPT-02-04, TEST-OPT-02-01, TEST-OPT-02-04 | Distinct continuous и явно независимые seed/replicate. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/OPT-02.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
