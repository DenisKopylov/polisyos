# UDF-04 — Ukraine ops: явный workspace root и перенос server gate

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** Нет; пакет миграции LA. **LA:** LA-029 (R).

**Предшественники:** Нет. **Совместная очередь:** LANE-07.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Передать product/workspace root из CLI/composition вместо parents[3]. Вынести provision и запуск repository C7 в существующий tools/ops_runners/ukraine_data owner, домен получает callback/result и необходимые ограничения. Сохранить server-only policy и правильный unavailable для installed wheel без checkout.

**Различающие тесты и сохраняемое поведение.** Command/cwd/env/exit/skipped сравниваются recording subprocess, explicit root и installed layout. На Mac не выполнять apt-get, CPX62 provisioning или server-only C7. Native маленький CLI test проверяет маршрут без запуска сервера; тяжёлый deployment остаётся unrun.

**Не считать исправлением.** Не заменить 3 новой магической глубиной и не ослабить server-only marker ради локального зелёного результата. Src не импортирует tools.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Границы участия в LA

**LA-029:** Полная область карточки с конечной проверкой применимости/совместимости; исходный текст и ограничения обязательны. Accountable closure: **UDF-04**; необходимые пакеты: UDF-04.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/data_forge/domains/ukraine/cli.py
policy-engine/src/polisyos/data_forge/domains/ukraine/orchestrator.py
policy-engine/src/polisyos/data_forge/domains/ukraine/server.py
policy-engine/tools/ops_runners/ukraine_data/server_bootstrap.py
policy-engine/tools/ops_runners/ukraine_data/validate_part_a.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_udf_04.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-07, MOVE-19. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное решение LA-029

Источник LA_r09, строки 1518–1567; полный текст, не только выполняемая здесь фаза.

<!-- SOURCE_BEGIN LA:LA-029 -->
## LA-029. Ukraine server: эксплуатация и repository gate внутри предметного builder

**Перемещение по смысловой роли**

**Точная область:**

`src/polisyos/data_forge/domains/ukraine/server.py`

`src/polisyos/data_forge/domains/ukraine/orchestrator.py`

`src/polisyos/data_forge/domains/ukraine/cli.py`



**Статус.** Несоответствие ответственности и след старой глубины пути подтверждены; рабочие ограничения сохраняются.



**Что установлено и почему это legacy-кандидат.** server.py строит apt-get/uv bootstrap для CPX62, проверяет binaries/environment, запускает конкретный tests/integration/test_c7_synthetic_full_pipeline.py и интерпретирует pytest-output. Это эксплуатация среды и запуск repository-проверки, а не преобразование украинских наблюдений. После физического переноса constructor orchestrator всё ещё использует Path(__file__).resolve().parents[3]: в нынешнем расположении это src/polisyos, а не policy-engine. CLI не передаёт override. Успешный перенос import-пути поэтому не гарантировал сохранения контекста исполнения.



**Что сохранить.** Фактические требования к среде, защиту от непреднамеренного тяжёлого локального запуска, данные capabilities, результат gate и причины skipped/failed, stage manifests и воспроизводимость команд. Не убирать C7-проверку ради зелёного запуска и не превращать env-marker в институциональное разрешение.



**Куда перенести / с чем объединить.** Существующий tools/ops_runners/ukraine_data/ — подходящий владелец команды; предлагаемые server_bootstrap.py и validate_part_a.py, либо согласованная специализация deploy/. Это новые имена, готовый эквивалентный runner здесь не установлен. Доменные config/result contracts и необходимое исполнителю ограничение остаются в Data Forge; tooling зависит от домена, но домен не импортирует tools обратно.



**Порядок миграции.** Сначала передавать проверенный product/workspace root явно из CLI/composition layer. Затем вынести provision и запуск теста, сохраняя callback/результат у orchestration. Обновить ukraine-data команды, shell scripts и CI consumers. Для установленного wheel без checkout точно сообщать о недоступной repository-проверке, а не искать соседний тест произвольным parents[N]. Не менять server-only policy в том же relocation-коммите без отдельного решения.



**Фактическая проверка и приёмка.** P08 исполняет выбранное исходное тело constructor с фикстурами сервисов и получает /checkout/policy-engine/src/polisyos; P09 с явным корнем получает /checkout/policy-engine. Реальные apt-get, subprocess, C7 и CLI не запускались. В интеграции сравнить command, cwd, env, exit/skipped semantics, override и работу на установленном пакете.



**Приоритет.** Высокая ясность роли и умеренная цена. Исправление привязки root можно сделать до большого переноса.



**Граница вывода.** Потребитель с правильным repo_root уже избегает локального дефекта. Содержательно domain orchestrator остаётся нужным; вывод не означает удалить server-проверки или всю Ukraine pipeline.



**Основания:** E80, E81, E82, E94. Локальные проверки: P08, P09.


<!-- PAGEBREAK -->
<!-- SOURCE_END LA:LA-029 -->

