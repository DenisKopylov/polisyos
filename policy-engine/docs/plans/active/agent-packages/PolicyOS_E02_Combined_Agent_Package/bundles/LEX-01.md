# LEX-01 — Lex: norm/compliance comparison отдельно от impact-topic эвристики

**E02 · окно CP3 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-017 (R).

**Предшественники:** Нет. **Совместная очередь:** LANE-11.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Сначала прочитать реальные diff/report consumers и зафиксировать report semantics; разделить norm diff, compliance transitions и candidate impact topics. Переносить связный модуль к предложенным Lex normpack/diff.py и legal_evaluation/impact_diff.py только по совместимому import contract. Старый simulator address — узкий alias по lifecycle; historical schema не меняется незаметно. Количественный эффект остаётся за существующими Scientist/Foundry путями.

**Различающие тесты и сохраняемое поведение.** Unchanged/added/removed/modified norms, issue keys и pass configuration, реальные report refs/bytes, persistence и downstream display. OBLIGATION→compliance_cost tag остаётся предположением темы, не измеренными затратами. Для relocation старое полезное поведение совпадает; изменение label/schema версии явно отделено.

**Не считать исправлением.** Не переносить всё в Foundry, не удалять реальный norm diff/compliance, не придумывать величины эффекта по тегам. Непрочитанные diff/report детали уточняются до перемещения, не объявляются уже готовой эквивалентной заменой.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-017:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **LEX-01**; необходимые пакеты: LEX-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py
policy-engine/src/polisyos/lex/normpack/diff.py
policy-engine/src/polisyos/lex/simulator/diff.py
policy-engine/src/polisyos/lex/simulator/engine.py
policy-engine/src/polisyos/lex/simulator/report.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/core/governance/passes/legal_pass.py
policy-engine/src/polisyos/core/governance/passes/safety_pass.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_lex_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-21. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-017

Источник LA_r09, строки 540–570; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-017 -->
## LA-017. Lex simulator: норм-различия, проверки и эвристика воздействия смешаны

**Перемещение по смысловой роли**

**Статус.** Фактическая функция установлена; преимущественно полезный код, не мёртвый симулятор.

**Точная область:**

`src/polisyos/lex/simulator/engine.py`

`src/polisyos/lex/simulator/diff.py`

`src/polisyos/lex/simulator/report.py`

**Что установлено и почему это legacy-кандидат.** NormImpactAnalyzer сравнивает NormPacks, запускает legal/safety passes и строит compliance transitions. Его _infer_affected_kpis лишь сопоставляет OBLIGATION с compliance_cost, PROHIBITION с operational_restrictions, прочее — с regulatory_flexibility. Ни эффекты поведения, ни величины издержек из этого соответствия не вычисляются. Название simulator/impact шире выполненной функции.

**Что сохранить.** Реальный norm diff, сравнение issues, provenance и persistence. Простая типизация потенциально затронутых тем полезна как подсказка, но не как экономическая или причинная симуляция.

**Куда перенести / с чем объединить.** Предлагаемые normpack/diff.py и legal_evaluation/impact_diff.py под существующими Lex-владельцами; report рядом с фактическим владельцем сравнения. Эвристические tags отделить и назвать как candidate impact topics; для количественного эффекта существующие Scientist/Foundry routes, не новый механизм в Lex.

**Порядок миграции.** Сначала уточнить report semantics, не переписывая historical schema незаметно. Затем перенести согласованный модуль с public alias. diff.py/report.py обозначены как необходимые dependencies переноса: их полный текст здесь не анализировался, поэтому собственное слияние этих файлов остаётся условным.

**Приёмочная проверка.** Unchanged/added/removed/modified norms, одинаковые issue keys, pass configuration, сохранённые report IDs/refs и отсутствие превращения candidate tags в измеренные KPI. Проверить реальных downstream-consumers.

**Приоритет.** Средняя цена; высокий эффект для смысловой навигации.

**Граница вывода.** Нельзя переносить весь package в Foundry: правовое сравнение остаётся задачей Lex. И нельзя утверждать измеренный вред только по эвристическому имени KPI.

**Основания:** E30.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-017 -->

