# CAU-04 — DoWhy: реальный estimand и point-only результат

**E02 · окно CP5 · локальная проверка L · начальный статус planned.**

**B:** B212, B213. **LA:** Нет; технический пакет B.

**Предшественники:** Нет. **Совместная очередь:** LANE-05.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Связать запрошенный estimand/contrast/population с поддержанным identify/estimate API и проверить фактический ответ. Сохранить point, даже если CI недоступен, через совместимый частичный report; при необходимости согласованно расширить contract и consumers.

**Различающие тесты и сохраняемое поведение.** Recorder point=7 без CI не создаёт 7±epsilon. Настоящий interval[5,9] сохраняется. NIE-request не выдаёт backend-defaultATE под новой подписью; unsupported profile — точный capability-result. Native DTO тест обязателен; один действительный DoWhy smoke на K5. Proceed_when_unidentifiable=False остаётся.

**Не считать исправлением.** Не подставлять нулевую дисперсию и не ослаблять общий SUCCESS-guard без versioned смысла. Spy не доказывает работу реального DoWhy API.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/_common.py
policy-engine/src/polisyos/foundry/methods/catalog/causal/dowhy_identify_estimate.py
policy-engine/src/polisyos/ir/analytics/causal.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py
policy-engine/src/polisyos/ir/analytics/uncertainty.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_cau_04.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CAU-01. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A10.** Исправленный point/label не означает статистическую аттестацию CI/RBC/bootstrap. Невыполненные процедуры и coverage checks остаются отдельными остатками.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B212

Источник B_r19, строки 5194–5205; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B212 -->
## B212. Point-only ответ DoWhy превращается в почти точный доверительный интервал

**Приоритет:** высокий, центральная граница частичной полезности. **Основание:** _run_dowhy и _extract_confidence_interval; DW01–DW04. [C20.R06–R07]

**Проблема.** Если backend не возвращает interval, адаптер создаёт point±max(|point|×10⁻⁹,10⁻⁹) и вызывает build_success_report. В общем CausalEffectReport для SUCCESS требуются одновременно point и interval. Это создаёт давление заполнить отсутствующую неопределённость, но не делает такое заполнение обоснованным.

**Воспроизведение.** Recorder-backend вернул конечную точку 7 без CI и SE. Исходный адаптер запросил успешный report с [6,999999993;7,000000007], уровнем 0,95 и SE=None. Интервал [5,9], когда backend действительно его предоставил, сохранён. Ошибка identify и нечисловая point корректно пошли по отказным ветвям.

**Рекомендуемое исправление.** Независимо сохранять определённый estimand, вычисленную point и состояние inferential-части. Недоступность CI не должна ни стирать полезную point, ни создавать очень узкую фикцию. Вызывать действительную поддержанную CI-процедуру либо использовать реальный SE только при подходящем распределении и предпосылках. Для point-only пути нужен существующий совместимый частичный результат или адресное расширение общего контракта с согласованными потребителями.

**Приёмка и граница.** Recorder не является DoWhy; реальная библиотека, IR-envelope, права и публикация здесь не запускались. В production-тесте backend без inference должен давать point-only; backend с настоящим interval — сохранить его; недоступный backend — прежнее явное ограничение. Нельзя подставлять нулевую дисперсию, бесконечно узкую полосу или общий SUCCESS-гейт только ради завершения pipeline.

<!-- SOURCE_END B:B212 -->

## Исходное основание B213

Источник B_r19, строки 5206–5217; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B213 -->
## B213. Запрошенный estimand_type остаётся только подписью отчёта DoWhy

**Приоритет:** высокий при нескольких видах причинного запроса; небольшой явный binding. **Основание:** _run_dowhy; DW05–DW06. [C20.R06, C20.E04]

**Проблема.** Параметр estimand_type объявлен в методе и читается, но не передаётся ни CausalModel, ни identify_effect. В estimate_effect передаётся только method_name. Итоговый report записывает именно запрошенную строку, хотя фактический backend мог использовать свой default.

**Воспроизведение.** Для requested nonparametric-nie recorder с определённым default ATE получил constructor(data,treatment,outcome,graph), identify(proceed_when_unidentifiable=False), estimate(method_name=...). В отчёте одновременно оказались estimand_type=nonparametric-nie и identified_estimand='ATE(x:0->1) [fixture default]'. Это различающий протокольный опыт, не численное оценивание реального NIE.

**Рекомендуемое исправление.** До исполнения связать запрос с поддержанным типом estimand, вмешательством/контрастом, target population и фактической формулой идентификации. Для поддержанного профиля передать параметры по API конкретной версии, проверить ответ; для неподдержанного — точный capability-result. Неизвестное имя нельзя просто переслать в библиотеку и надеяться, что она корректно его поймёт.

**Приёмка.** Наблюдать реальные аргументы identify/estimate на обычном dispatcher-маршруте, а не только совпадение labels. Default ATE должен остаться рабочим. Существующий proceed_when_unidentifiable=False передаётся правильно и сохраняется. Документация DoWhy показывает отдельную точку задания estimand_type; её чтение не доказывает установленную runtime-версию проекта. [C20.E04]

<!-- SOURCE_END B:B213 -->

