# OPT-03 — Рабочий warm corpus и атомарное GP-продолжение

> Предложение review-v2: только спецификация; product implementation и все TEST остаются NOT_RUN. Основание: PS-F02.

**LANE-02 · B114, B115 · ТЗ исполнителю; все TEST — NOT_RUN.**
База `20d9009be21097bfbdc38a546a15cc60213b8ace`; [неизменённый аудит](../05_Основания/Аудит/02_Пакеты/OPT-03.md), [исходная карточка](../05_Основания/Аудит/05_Источники/OPT-03_исходные_строки.txt), строки 2505–2599.
**Практический результат:** Совместимые оплаченные наблюдения действительно достигают GP; append сохраняет learned basis, а отклонённый snapshot не уничтожает действующий поиск.
Типы работы разделены ниже. Уже существующий механизм не переписывать только ради diff; qualify означает реальный запуск/потребление, capability — построение недостающего положительного пути.

## 1. Сохраняемые свойства

- Общий corpus до threshold/subset.
- Origin/replica дедупликация, rejection history и настоящий source-admission bridge.
- Conditioning вместо необученного нового GP.
- X/Y prefix checks, bounded fallback/refit, saved full-refit boundary и numerical witnesses.
- Защищённые различения: релевантные candidate/authority, input/result, historical/current различия из отчёта. S08: новую совместимую конфигурацию проверять на том же механизме, а не ветке по ID кейса.

## 2. Полнота исходных обязательств и остатков

| Основание | REQ | Disposition / решение |
|---|---|---|
| audit-residual:C20_остатки:0 | REQ-OPT-03-01 | fix: [-0:] устранён без смены полезной subset policy. |
| audit-residual:C20_остатки:1 | REQ-OPT-03-02 | fix: Staged restore. |
| audit-residual:C20_остатки:2 | REQ-OPT-03-03, REQ-OPT-03-04 | qualify: Actual numerical/source witness, не spy. |
| audit-residual:C20_остатки:3 | REQ-OPT-03-04 | fix: Согласовать test с attempts/history contract. |
| audit-residual:C20_остатки:4 | REQ-OPT-03-04 | capability: Реальный conditioned-source positive path. |
| B114 | REQ-OPT-03-01, REQ-OPT-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| B115 | REQ-OPT-03-02, REQ-OPT-03-03, REQ-OPT-03-04 | fix: Исходный критерий покрыт указанными конкретными REQ; старое описание не объявляется текущим дефектом там, где механизм уже существует. |
| remaining:0185 | REQ-OPT-03-01 | fix: Cap крайние значения. |
| remaining:0186 | REQ-OPT-03-03, REQ-OPT-03-04 | qualify: Native corpus, iteration expectation и conditioned verification. |
| remaining:0187 | REQ-OPT-03-02 | fix: Атомарный snapshot. |
| remaining:0188 | REQ-OPT-03-03, REQ-OPT-03-04 | qualify: Learned posterior и actual composition. |

## 3. Нормативные REQ и конкретное решение

### REQ-OPT-03-01 — fix
max_train_size имеет явный положительный целочисленный диапазон; cap=1 действительно выбирает не более одной строки.

**Решение на существующих владельцах.** В BayesianConfig validation отвергнуть bool, zero, negative и нецелые cap, если отдельный unlimited contract не объявлен. В _select_training_subset обрабатывать recent_n=0 без [-0:]: recent=[] и older=filtered, затем ограниченная sampled часть. Не менять default diversity policy и source-admission corpus.
**Приёмка:** TEST-OPT-03-01.

### REQ-OPT-03-02 — fix
GP set_state валидирует и строит весь candidate state до единственной атомарной замены live state.

**Решение на существующих владельцах.** В BayesianOptimizer.set_state использовать staged base/RNG state из CTL-02 плюс временные tensors/model/transform/rejection ledger. Проверить version, objective/space, shapes/finite, full-refit boundary и model_state compatibility; загрузить модель в staging owner, не очищая live _model. Только после успешной материализации присвоить согласованный набор. Не обещать откат внешних backend side effects; они не должны менять live owner до commit.
**Приёмка:** TEST-OPT-03-02.

### REQ-OPT-03-03 — qualify
Квалифицировать настоящий learned-state conditioning и numerical posterior; fixture theta не приёмка.

**Решение на существующих владельцах.** Использовать найденные test_bayesian_no_refit_preserves_learned_gp_state_with_new_observation, test_restored_append_preserves_actual_full_refit_boundary_and_learned_basis и test_gp_resume_witness.py. Tiny actual SingleTaskGP 8→9→12 строк, fixed seed/dtype и explicit RBFKernel/ConstantMean profile; независимый NumPy Cholesky oracle с теми же noise/transforms сравнивает mean/covariance/UCB по численной bound существующего теста. Записать fit/condition cost отдельно от correctness.
**Приёмка:** TEST-OPT-03-03.

### REQ-OPT-03-04 — capability
Warm reuse результата genuinely conditioned GP согласуется с fresh source verifier и действительным source admission.

**Решение на существующих владельцах.** Проверить существующий _recompute_search_gp_fit_basis после fit interval>1 и actual conditioning. Если verifier full-refit fingerprint отличается, расширить имеющийся fit-basis contract: сохранять проверяемую lineage initial fit + ordered appended source refs + transforms/noise/parameters и воспроизводить объявленный continuation; либо явно refit перед issuance source-admissible result с измеренной стоимостью. Не разрешать fingerprint mismatch и не верить self-description. Выбор ограничен DEC-OPT-03-01. Отдельная необязательная capability-развилка DEC-OPT-03-02 касается strategy-neutral reuse actual measured observations, а не ремонта fitted-GP continuation. Она не меняет текущий fitted-native source guard, preserved cold rows≠fitted sources, существующие REQ/TEST или local DoD; до отдельного выбора/квалификации продолжает действовать нынешний profile.
**Приёмка:** TEST-OPT-03-04.

## 4. Локальные различающие тесты

Все номера TEST ниже — проектируемые проверки, не вымышленные имена существующих pytest-функций. Существующие файлы использовать/расширить; старый mutation или контролируемое удаление проверяемого механизма должен давать отличающийся исход.

### TEST-OPT-03-01 · NOT_RUN
- **Setup:** 8 допустимых строк с фиксированным порядком, cap1/2/4/512 и cap0,-1,True.
- **Действие:** Вызвать существующий subset через warm/current splits и реальный suggest.
- **Oracle:** Размер ≤cap, cap1 ровно1 при непустом corpus; повтор origin не дублируется; invalid config отвергнут до expensive fit.
- **Positive / negative / boundary:** Default512 сохраняет семантику; rejected history доступна; неизвестное число не вводится ради заполнения cap.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-03-02 · NOT_RUN
- **Setup:** Live fitted model с iteration7, saved model/RNG/continuation digest; snapshots с missing fitted X/Y, bad shape, mismatched basis и load_state_dict failure.
- **Действие:** Попытаться восстановить каждый snapshot; затем запросить тот же posterior и следующий proposal; применить один корректный snapshot.
- **Oracle:** Каждый отказ сохраняет прежние model parameters, transforms, counters, RNG и posterior; успешный commit согласован и продолжает actual full-refit boundary.
- **Positive / negative / boundary:** Legacy incomplete snapshot даёт точный unsupported, не случайный перенос state_dict; fresh empty owner не единственный тест.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-03-03 · NOT_RUN
- **Setup:** Поддержанный locked Torch/BoTorch runtime, существующие numerical fixtures и source tests; append до refit_interval, altered old X/Y и scheduled boundary.
- **Действие:** Fit→condition→save→fresh load→append; сравнить learned params/transform buffers и posterior oracle, затем выполнить removal controls.
- **Oracle:** Новая строка действительно учтена; learned state не defaults; full-refit boundary не сдвинута conditioning; altered prefix вызывает refit; удаление load_state/transform восстановления ломает oracle.
- **Positive / negative / boundary:** Backend exception даёт bounded explicit refit; native job coordinated single slot; никакого заявления о внешней эмпирической истинности GP.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

### TEST-OPT-03-04 · NOT_RUN
- **Setup:** Actual Source Search→MethodJob→CAS→WarmStartBridge→target Search, compatible objective/unit/context; fit interval>1, хотя существующий e2e использовал1.
- **Действие:** Создать fitted source, добавить observation без refit, сохранить и принять target; изменить context year, one source ref/transform и duplicate origin.
- **Oracle:** Один и тот же совместимый corpus whole vs warm/current имеет одинаковый допуск; genuine conditioned observation проходит только воспроизводимый declared profile; tamper исключён с причиной.
- **Positive / negative / boundary:** Cold initial rows не становятся fitted sources; попытки/current/admitted counts различены. Batch iteration expectation соответствует history_count=3, не устаревшему0.
- **Doubles:** Допустим контролируемый внешний транспорт/LLM и временный разрешённый store; проверяемый алгоритм, identity, реальный numerical owner, сериализатор и consumer не заменяются success-shaped stubs.
- **Evidence:** Точный base/patch, команда и exit/skip, исходные inputs/refs, полный различающий assertion и сохранённый результат. Positive и negative выполняются на одном квалифицированном срезе.

## 5. Общее испытание, зависимости и ownership

Общие сценарии: **E02-I02-B, E02-I02-D**, [определение LANE-02](../03_Интеграция/LANE-02.md). Исполнять только затронутый маршрут; CP — координационная приёмка, не новый runtime registry и не обязательный запуск всего CI.
- CTL-02 — общий portable RNG и base state; OPT-03 владеет GP atomic staging, не второй restore framework.
- OPT-02 — canonical params/source corpus; TRN-01/02 — discovery и compatible history.
- Проверять source verifier совместно с его actual owner; не отключать private admission.

## 6. Порядок и совместимость

Сначала воспроизвести на pinned baseline адресный контракт/дефект; затем один writer меняет общий owner, сохраняя callers и исторические readers. Поведенческий delta и перенос/cleanup описать раздельно. Не переписывать immutable старые artifacts: новая интерпретация получает явную version/basis. Rollback не переименовывает новые результаты как старые; reader обязан либо сохранить корректное чтение, либо дать точное unsupported/version ограничение. Команды и selectors проверить в checkout перед запуском, dependency install согласовать с общим исполнителем среды.

## 7. Design alignment и полезная способность

[System Vision, §6 Capability Reality Bar и §5 Rule12](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md): полный producer→persisted artifact→bridge→consumer; новый совместимый ресурс проходит общий механизм. Это не запрет нового общего кода для новой семантики. [D0 B-on-A](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md), раздел «D0 — Decision: B-on-A, Shadow-First»: полезная кандидатная работа допускается без автоматического полномочия. [Stage0 §4.3 K06](../05_Основания/Архитектура/stage0-custody-kernel-ratification.md): неизвестность ограничивает затронутое действие, не всё исследование.



## 8. Ограниченные решения

- **DEC-OPT-03-01**: Как source verifier воспроизводит genuinely conditioned fit basis? Owner: OPT-03 и existing fit-basis verifier. Варианты: версионированная проверяемая continuation lineage с replay исходного fit и append; явный bounded full-refit перед выдачей reusable source result. Выбор по: Native posterior/fingerprint replay, поддержанный backend serialization, измеренные время/память и совместимость readers. Обязательный выход: Один выбранный profile, DTO/version migration и positive/negative e2e; до выбора conditioned reuse остаётся NOT_RUN/unsupported, а candidate exploration допустима.

- **DEC-OPT-03-02**: Нужен ли отдельный bounded measured_observation reuse profile независимо от того, успел ли source proposer обучить GP? Owner: OPT-03 с OPT-02 actual observation admission и TRN-01 WarmStartBridge. Варианты: Сохранить только нынешний fitted-native-GP historical profile и честно ограничить reusable-search claim; Отдельно квалифицировать strategy-neutral verified measurement reuse; source predictions/model continuation сохраняют более сильный fitted-basis contract. Выбор по: Actual MethodJob source outcome/selected receipt, objective/units/direction/data/split/tenant/space/replica guards; whole-current vs persist/fresh-warm eligibility; measured evaluation/fit costs. Proposer strategy сама по себе не measurement validity, но syntactic ID/self-asserted score также не evidence. Обязательный выход: Либо явный bounded scope без нового profile, либо отдельная согласованная capability specification/profile version и discriminating positive/negative tests: cold Sobol/random actual measurement before/after restart, same measured corpus once, wrong units/split/tenant/data rejected, prediction-only value не observation, target GP fit собственный. Никакого mandatory ослабления existing fitted-native guard или превращения cold source в fitted; новые tests/profile принимаются отдельно, текущий local repair не блокируются.

**Scope capability-extension:** Отдельная необязательная capability-развилка DEC-OPT-03-02 касается strategy-neutral reuse actual measured observations, а не ремонта fitted-GP continuation. Она не меняет текущий fitted-native source guard, preserved cold rows≠fitted sources, существующие REQ/TEST или local DoD; до отдельного выбора/квалификации продолжает действовать нынешний profile.

## 9. Проверенные текущие пути

- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1085–1117](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1085-L1117) — `    def set_state(`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1197–1229](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1197-L1229) — `    def _select_training_subset(`.
- [policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py:1373–1405](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/strategies/bayesian.py#L1373-L1405) — `    def _fit_gp(`.

## 10. Точная preservation-трассировка

| Inventory ID | REQ / TEST | Смысл |
|---|---|---|
| preserve:0299 | REQ-OPT-03-01, REQ-OPT-03-04, TEST-OPT-03-01, TEST-OPT-03-04 | Общий corpus до threshold/subset. |
| preserve:0300 | REQ-OPT-03-04, TEST-OPT-03-04 | Origin/replica дедупликация, rejection history и настоящий source-admission bridge. |
| preserve:0301 | REQ-OPT-03-03, TEST-OPT-03-03 | Conditioning вместо необученного нового GP. |
| preserve:0302 | REQ-OPT-03-02, REQ-OPT-03-03, TEST-OPT-03-02, TEST-OPT-03-03 | X/Y prefix checks, bounded fallback/refit, saved full-refit boundary и numerical witnesses. |

## 11. Что предъявить и что не считать PASS

Предъявить конкретные до/после assertions и actual affected consumer, сохранённые outputs/refs, failure controls, source identity и поддержанный runtime. Наличие кода, формы receipt, этого ТЗ либо старого зелёного теста не является выполнением. Local/source-excerpt observation не native acceptance; skipped/blocked остаётся видимым. Число или candidate output не повышается автоматически в empirical/decision authority. Согласовать полезный positive, не ограничиваться запретами. Полные исходные probes находятся в отдельно доставленном phase1 ZIP; текущая подготовка не создаёт нового product execution.

[Машинная трассировка](../04_Трассировка/OPT-03.json). Аудит охватил127/127; это не означает выполненных127 ремонтов.
