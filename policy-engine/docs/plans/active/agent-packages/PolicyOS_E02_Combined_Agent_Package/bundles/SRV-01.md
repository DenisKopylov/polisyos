# SRV-01 — SearchService: чистые contracts и один ask/tell state transition

**E02 · окно CP3 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-014 (M).

**Предшественники:** [CTL-03](../bundles/CTL-03.md). **Совместная очередь:** LANE-02.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

В contracts оставить DTO/protocols; concrete adapters перенести в предлагаемый adapters.py. После CTL-03 подключить tell к единственной операции state-owner вместо _history/_best mutation. Сохранить старый export только по фактическому public договору, не через eager runtime import.

**Различающие тесты и сохраняемое поведение.** Contract-only import при controller trap; настоящие ask/tell и run_search, unknown/duplicate IDs, typed evaluation, frontier и resume. Tell не может обойти B123 или вернуть старый history-counter. Identity поддержанных DTO/aliases и lazy facade проверяется.

**Не считать исправлением.** Не объявлять protocol готовым native driver и не удалять controller. Не превращать чистый интерфейс в новый private-field editor.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-014:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **SRV-01**; необходимые пакеты: SRV-01.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/scientist/methods/search/adapters.py
policy-engine/src/polisyos/scientist/methods/search/contracts.py
policy-engine/src/polisyos/scientist/methods/search/controller.py
policy-engine/src/polisyos/scientist/methods/search/run_state.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/scientist/methods/autotune/runtime.py
policy-engine/src/polisyos/scientist/methods/search/funnel/orchestrator.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_srv_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CTL-01, CTL-03, SRV-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-05, MOVE-06. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A11.** Native search cutover не копирует private mutation и сохраняет все принятые B fresh/empty/cost/typed controls. LA-015 закрывается после проверки реального consumer, не появления protocol.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-014

Источник LA_r09, строки 455–481; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-014 -->
## LA-014. Search contracts импортируют и изменяют legacy runtime

**Слияние / разделение ответственности**

**Статус.** Смешение контрактов и реализации подтверждено.

**Точная область:**

`src/polisyos/scientist/methods/search/contracts.py`

**Что установлено и почему это legacy-кандидат.** Рядом с CandidateProposal, EvaluationBundle, SearchService и FunnelService находятся concrete adapters. Импорт contracts тянет SearchController и FunnelOrchestrator. LegacySearchServiceAdapter.tell вручную пишет _history, _best_objective и _best_candidate контроллера. Это отдельный путь обновления состояния, а не чистая декларация интерфейса.

**Что сохранить.** Стабильные DTO/protocols и переходный доступ к действующему controller. Сохранить семантику policy_evaluation/frontier/registry feedback, а не лишь scalar minimum.

**Куда перенести / с чем объединить.** В contracts.py оставить DTO/protocols; предлагаемый новый adapters.py в том же существующем methods/search/ принимает LegacySearchServiceAdapter и OrchestratorFunnelService. Конкретную операцию tell-state transition предоставляет владелец search state, не обход приватных полей.

**Порядок миграции.** Сначала разорвать import dependency, затем централизовать переход состояния; временно сохранить старый export только если подтверждён публичный контракт. Перемещение dataclass без устранения ручной мутации не завершает смысловую миграцию.

**Приёмочная проверка.** Импорт contract-only не загружает controller; прежний ask/tell, run_search, unknown/duplicate candidate IDs, typed policy evaluation, frontier и resumed state сохраняют согласованный смысл.

**Приоритет.** Высокая архитектурная отдача; средняя цена.

**Граница вывода.** Новый native SearchService не показан как готовая замена: в прочитанном contracts присутствуют protocol и adapter. Нельзя удалить controller потому, что интерфейс уже назван canonical.

**Основания:** E27, E28.

<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-014 -->

