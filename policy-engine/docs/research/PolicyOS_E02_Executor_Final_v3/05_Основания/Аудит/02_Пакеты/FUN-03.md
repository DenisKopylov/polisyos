# FUN-03 — текущее знание, calibration routing и pre-commit ограничение
## C24 · 31 октября 2026 года

**Исходные IDs:** B161, B163, B164. **Порядок:** 24/127, LANE-02. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Только аудит; далее — TRN-01.

## Решение

**Частичная оценка с существенными полезными изменениями.** Исторический max uncertainty больше не выдаётся автоматически за текущее научное знание: есть отдельные typed task admission, exact same-basis refinement и fresh current read. Пустой tracker согласованно сообщает no_promotion/not_established и не порождает measured drift. L6 не вызывает effectful runner при запрете — более того, без typed writer bridge он fail-closed и в normal, не доверяя boolean callback.

При этом **полезная цепочка не везде замкнута**. Policy-blueprint producer прямо возвращает incomplete uncertainty owner context; current same-basis assessment требуется довести через реальные уже существующие method/source owners. L6 честно сообщает `bridge_missing`; normal технический успех ещё не даёт effectful promotion. Snapshot restoration существует, но штатный calibration report builder не сохраняет snapshot, которого ждёт node.

Подтверждены два более узких остатка: **C24-R01** — 1–2 пары или constant ranks выдаются за observed zero-correlation drift; **C24-R02** — пустой calibration report показывает false-negative criterion PASS=0 без наблюдений. Оба не означают снятие promotion cap: no_promotion сохраняется.

Итог **26 MATCH, 0 ERROR**, exit0. Настоящие selected AST tracker/report/L6/orchestrator/edge predicate и Pydantic DTO исполнены; стадии, refs/source admission и внешние owners — явные фикстуры. Native product/CAS/HTE/HTTP/pytest **UNRUN**.

## 1. Исходные требования и две независимые оси

[Оригинальный FUN-03](../05_Источники/FUN-03_исходные_строки.txt) требует не «снизить все риски», а разрешённо изменить **то же** знание, согласовать calibration routing и не исполнять запись до актуального допуска. LLM остаётся semantic proposer; stage number, lower scalar или похожий context не дают scientific или институциональной authority.

| ID | Ремонт — сохранить | Реальный остаток |
|---|---|---|
| B161 | Historical max отдельно от typed current read; numeric-free unknown; same-basis, generation, predecessor и completion identity; конфликты не усредняются | Native blueprint context заведомо not_established; замкнуть actual selected method/source/task basis и проверить owner assessment→consumer. Не заменять max глобально на min/last |
| B163 | Empty metrics/routing согласованы, no drift alerts; actual snapshot can restore corpus; missing snapshot не создаёт новый пустой tracker | C24-R01/R02: недостающая статистика не measured zero/PASS. Producer report→snapshot→node handoff не подключён штатным builder; scope compatibility отдельно |
| B164 | Нет callback до preflight; bool/self-attestation не разрешает effect; retained payload читается без producer; missing bridge явно ограничен | Нормальный effectful route требует настоящего назначенного writer, текущей проверки и revoke-serialized commit. Не разрешать callback ради зелёного теста |

## 2. B161: historical max сохранён, а current требует отдельной предметной основы

`get_outcome` по-прежнему вычисляет historical envelope через merge_max. Это намеренный консервативный обзор всей истории, теперь явно помещённый в feedback `uncertainty_historical_max`. `uncertainty_current` не подменяется последней стадией; legacy lower diagnostic остаётся диагностикой. Отдельно возвращается `search_uncertainty_current_read` — typed owner projection, не одно число. [S01:880–1129]

**P19:** ранняя unknown1, поздняя statistical0.1 и независимый model-risk0.8. Historical statistical остаётся1; последняя стадия сохраняет0.1 и0.8; current envelope=None, current_status=not_established, reason pre-dispatch owner/store missing. Это правильное отсутствие необоснованного refinement, **не доказательство уже работающего source-bound update**.

### Существующий содержательный путь

1. Policy runtime строит фактический stage configuration и owner context после выбора stages. Orchestrator `_admit_search_uncertainty_task` сохраняет owner context, ticket generation, task admission и binding **до dispatch**. [S01:342–413; S05:244–400,620–785]
2. `produce_search_task_admission` при complete basis сам выводит transitive role-qualified inventory: subject, quantity, contrast, population, outcome, plan/config/graph/rule/profile/procedure/selection, method ABI/params/seed/input, tenant/cell и epoch. Неполные данные дают `not_established`, а не придуманный scalar. [S06:4236–4370]
3. `record_first_assessment` загружает persisted predecessor/successor/refinement/profile, проверяет actual Runtime completion association и admitted binding. First assessment снимает **только свою** unknown obligation; независимые obligations остаются. Второй соперник того же поколения становится contested; позднее completion старого поколения сохраняется в history, не переписывает current. [S06:5261–5550]
4. `read_current_snapshot` под lock читает current pointer/generation и разрешает выбранные children из CAS. Missing/stale/mismatched children дают явный not_established. Возвращается `available_as_of_task_epoch`, а не необоснованное «сейчас истинно навсегда». [S06:5551–5795]

**P20–P24** исполняют actual `_verify_first_assessment_edge`: same-basis transition принимается в declared reference fixture; другой basis, obligation, generation и отсутствующая selected profile отвергаются. Это только relation predicate, **не CAS authentication и не выполненное scientific assessment**.

Найденные current-binding tests проверяют exact request/tenant/profile, same-generation historical handoff и generation revocation; весь 200-строчный test-файл прочитан. Configured-observation tests содержат cold-read persisted unassessed payload и отказ после удаления selected child. Большой native HTTP/HTE outbox test содержит actual completion→assessed и второй completion→contested, distinct rows/order digests, source-unit/mapping removal controls. В C24 прочитаны конкретные source-join/result/assertion участки, но не весь его огромный fixture и не выполнен сам test. Эти тесты **не посчитаны нашим empirical PASS**. [S11–S13]

### C24-G01 — native blueprint пока не производит complete task basis

В `_build_search_uncertainty_owner_context` current policy-blueprint owner намеренно добавляет missing slices для semantic scope, rule/profile/procedure, method ABI, request projection, seed и selected method input. Возвращаются `semantic_scope=None`, соответствующие selected refs=None и `status='not_established'` независимо от наличия только candidate/config/source graph. [S05:330–399]

Это явная безопасная граница и реальная оставшаяся способность: в этом producer-пути нельзя получить admissible current assessment только по похожим dictionaries. Требуется связать уже имеющиеся выбранные method/source owners и их actual content с task epoch; не построить ещё один универсальный truth registry. В другом Runtime HTE пути существенная реализация уже есть, её нельзя объявить отсутствующей из-за неполного blueprint producer. `current_uncertainty_envelope=None` тоже не означает, что весь v2 current-read отсутствует: структурированный current read сохранён отдельно.

## 3. B163: empty устранён, но insufficient и undefined ещё названы measured drift

[Actual tracker, S02:421–547](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stages.py#L421-L547) для пустого корпуса возвращает drift_alerts=[], promotion_ban_active=False, calibration_state=not_established, routing_mode=no_promotion. `compute_metrics` вызывает тот же routing owner. **P01** подтвердил согласованность; cap означает отсутствие калибровки, не наблюдённое падение корреляции.

**P02/P03:** пять aligned pairs дают observed/normal; пять inverse pairs дают observed/no_promotion/PROMOTION_BAN. P07 сохраняет corpus и routing после настоящего Pydantic snapshot→JSON→from_snapshot; P08 исполняет actual node resolver с этим snapshot. P09 подтверждает, что missing/invalid snapshot возвращает None, а не новый пустой mutable tracker. P10 исправляет persisted sample_count0/current_mode normal на not_established/no_promotion; P11 сохраняет существующую nonempty projection. [S03:84–146]

### C24-R01 — 1–2 пары и constant ranks ошибочно имеют measured zero

**Важность:** средняя для объяснения состояния и выбора исследования; консервативный запрет не снимается.

`_metrics_for_records` при len≤2 устанавливает correlation=0. `_spearman` при нулевой дисперсии рангов тоже возвращает0. Однако всякий непустой tracker объявляется calibration_state=observed; `drift_alerts` сравнивает этот0 с threshold и выпускает PROMOTION_BAN с текстом о падении корреляции. [S02:682–750]

* **P04/P05:** одна и две **идеально согласованные** пары → observed, correlation0, promotion_ban_active=True.
* **P06:** пять constant pairs, для которых rank-correlation не определена, → тот же measured-drift вывод.

Остаток не требует разрешить promotion при недостаточных данных. Нужно сохранить no_promotion либо явный ограниченный research route, но различить insufficient sample, undefined variation и действительно плохую измеренную связь. Existing report уже содержит gap `insufficient_correlation_window`; нельзя одновременно называть это падением измеренной корреляции без уточнения. Полная statistical calibration/power/domain qualification этой узкой механикой не исчерпывается.

### C24-R02 — report возвращает зелёный false-negative criterion для пустого корпуса

Actual `build_calibration_report()` переносит legacy numeric defaults и делает `passed=float(false_negative_rate)<0.02`. **P26:** sample_count0, no_promotion, gaps missing_burn_in/missing_sentinels/insufficient_window, но acceptance criterion `false_negative_rate` имеет actual0, passed=True; Markdown печатает **PASS**. [S04:86–240]

Наличие no_promotion и gaps — важная защита, поэтому это не ложное право публикации и не полностью «зелёный report». Но конкретная метрика воспринимается как проверенная без единого eligible наблюдения. Минимальное направление — criterion GAP/None с причиной отсутствия denominator, сохранив текущий cap и реальные измеренные нули. Не заменять все нулевые доли ошибкой.

### C24-G02 — snapshot reader есть, штатный producer snapshot не передаёт

`_resolve_runtime_correlation_tracker` ждёт `report.metadata['correlation_tracker_snapshot']`. Full source search нашёл этот ключ в runtime reader, но штатный `build_calibration_report` пишет только burn_in_present/lesson_pattern_count. **P25:** actual builder с 5 pairs → JSON round trip → actual node resolver: metrics5/normal сохранились, tracker=None. Это **не потеря routing projection**, но mutable corpus не восстановлен для дальнейшего накопления через данный producer. [S03:127–146; S04:159–182]

Существующие `to_snapshot/from_snapshot` пригодны; нужно выбрать actual report/snapshot producer и compatible scope, а не создавать новый state key наугад. Source/tenant/model/objective/calibration scope compatibility не доказывается только Pydantic-valid snapshot. Native persistence/reload и реальное накопление пар в C24 не выполнялись. Orchestrator уже записывает корреляцию лишь при AVAILABLE scores L2/L4; это полезный guard. [S01:2096–2135]

## 4. B164: callback не может успеть выполнить запрещённый эффект

[Actual L6, S07:64–136](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/funnel/level6_promotion.py#L64-L136) сначала читает ready payload и degradation mode. В no_promotion/reduced_judge/auto_cap effectful runner не вызывается. Более сильная нынешняя граница: при normal и runner без payload возвращается `bridge_missing`, поскольку callback/bool не являются owner-issued permit и revoke-serialized commit.

* **P12–P14:** запрещённые режимы, runner специально бросил бы exception; calls=[] и defer_to_human.
* **P15:** normal плюс recheck, возвращающий True, — calls=[] и bridge_missing. Ни recheck, ни runner не вызваны.
* **P16:** ready payload остаётся доступен read-only под no_promotion; новый producer не запускается, итог defer_to_human.
* **P17:** normal ready complete payload без admitted prior score не даёт APPROVE: score=None, итог defer, callbacks=[].
* **P18:** `_owner_recheck_allows_write` отвергает bool, mapping и произвольный объект. Не возвращать старое self-attestation поведение.

### C24-G03 — effectful capability всё ещё требует интегрированного writer boundary

Runtime действительно подключает runner/recheck lambdas, но L6 их сейчас намеренно не вызывает. `_policy_promotion_runner` содержит source/evaluation/provenance/evidence checks и непосредственный owner recheck перед `run_promotion_with_evidence`; `_policy_promotion_owner_recheck` проверяет explicit True, mode, candidate/evidence/run compatibility. Это исходный код, **не доказательство revoke-serialized final commit**, и именно поэтому bool callback не считается достаточным допуском. [S08:561–643,750–780; S05:653–674]

Нужен существующий назначенный protected writer с актуальной authority, binding к subject/attempt/predecessor и сериализацией revoke/commit; preflight не заменяет финальную проверку. Наш audit не назначает такой authority и не предлагает снять gate ради normal-path success. Retained result можно читать по своей политике без нового эффекта. На source snapshot стадия безопасно ограничена, но E02 capability «разрешённое нормальное продвижение» этим ещё не закрыта.

## 5. Native tests, реальные ограничения и аккуратность следов

Remediation `test_fun_03.py` прочитан целиком (841 строк). В нём есть positive/negative local gates, сохранение payload и controlled actual-node harness с заменёнными backend/non-funnel boundaries. Эти tests не объявлены полноценным deployment экспериментом даже по дизайну. В старых assertions ещё встречается `_empty_result.objective_value==inf` и obsolete feedback key `uncertainty_refinement_status`; current source даёт None и structured v2 read. **C24-G04:** согласовать test contracts и выполнить native профиль; это source-read contradiction, не фактический pytest failure.

Native pytest отсутствует; Python3.14 не запущен. Audit harness разбирает неизменённые полные selected definitions uncertainty из exact ranges, а не переписывает Python3.14 product source. Relation refs — tuple fixtures, не authenticated CAS. No HTTP/LLM/services, no writes/push/commit в продукте. Initial run24 MATCH/0 ERROR и final после P25/P26 — **26 MATCH/0 ERROR**; оба logs сохранены.

При metadata-сверке исправлены четыре end-of-file диапазона **наших C22/C23 source indexes**, с исходными копиями и erratum в истории. Packet reports, execution logs и все original18 artifacts не менялись; выводы не переаттестованы этой коррекцией. [Erratum](../06_История/Поправки_диапазонов_C24.md)

[Диагностика](../04_Проверки/C24_FUN03/bounded_diagnostics.json) · [команды](../04_Проверки/C24_FUN03/commands.json) · [границы](../04_Проверки/C24_FUN03/Чтение_и_границы.md) · [источники](../05_Источники/C24_источники.json) · [остатки](../01_Реестры/C24_остатки.json).

**24/127 пакетов рассмотрены ограниченно; 63 уникальных B/LA частично оценены; полного закрытия нет.** Следующий — **TRN-01 / B128, B130, B131, B132**.
