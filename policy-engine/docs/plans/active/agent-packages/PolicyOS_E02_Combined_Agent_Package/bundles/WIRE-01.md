# WIRE-01 — Версионированный transport допустимых типов state

**E02 · окно CP2 · локальная проверка L · начальный статус planned.**

**B:** B94. **LA:** Нет; технический пакет B.

**Предшественники:** Нет. **Совместная очередь:** LANE-06.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Согласовать typed wire-codec для state/outcome и safe-digest. Сохранить Decimal в типизированных и union-полях, идентичность bytes и non-finite policy через оба заявленных JSON backend.

**Различающие тесты и сохраняемое поведение.** Decimal в budget и params после round-trip имеет прежний тип/значение. Nested non-finite/unsupported даёт точный отказ, не строку/ноль. Настоящие ArtifactRef и OutputAwareNodeOutcome проходят native codec. Запуск Ray/Temporal для codec-теста не нужен.

**Не считать исправлением.** Не использовать default=str или float(Decimal). JSON-mode сам по себе не доказывает сохранение union-типа. Не повторять вычисление из-за детерминированной serialization ошибки.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/scientist/orchestration/engine/runner/serialization.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/core/llm/response.py
policy-engine/src/polisyos/scientist/orchestration/engine/state.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_wire_01.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** Нет по статической карте. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-11. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B94

Источник B_r19, строки 2477–2492; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B94 -->
## B94. Wire-сериализация не принимает Decimal, разрешённый собственным состоянием

**Происхождение:** C08-06. **Основание:** runner serialization → типы ExperimentState → callers Ray/Temporal; J1–J7. **Приоритет:** для реального перехода через этот codec; не обязательное условие локального in-process запуска. [C08.R05, C08.R06, C08.R10, C08.R11]

**Проблема.** `serialize_state`, `serialize_outcome` и `serialize_state_safe` передают `model_dump()` в orjson либо стандартный json без type-aware default. `ExperimentState.budgets` явно содержит Decimal; Decimal также допускается в params и causal_method_params. Python-mode dump сохраняет такие объекты. Поэтому обычный непустой бюджет останавливает сериализацию до отправки. Версия с digest использует тот же encoder и не устраняет проблему добавлением хэша.

**Проверки.** На реальном Pydantic/stdlib/orjson с уменьшенной DTO той же формы Decimal-бюджет вызывает TypeError в обоих JSON backend; аналогично outcome и safe-state. JSON-mode позволяет точно вернуть Decimal в типизированное поле budgets. Но Decimal внутри union-поля params превращается в строку и после model_validate остаётся строкой. Следовательно, одного глобального `mode='json'` недостаточно для полного сохранения типов.

J7 дополнительно показывает зависимость поведения от необязательной библиотеки: вложенный NaN в list[Any] стандартный encoder сохраняет нестандартным NaN, orjson преобразует в null. Это не отдельный доказанный ошибочный научный результат, но обязательный негативный тест нового codec: unsupported/non-finite нельзя молча превращать в другое значение. [C08.E03, C08.E04]

**Рекомендуемое исправление.** Использовать единый версионированный wire-контракт с точным кодированием допустимых типов и согласованной политикой непригодных значений. Переиспользовать существующую canonical/typed инфраструктуру, предварительно проверив round-trip требований state/outcome; не вводить параллельный формат без необходимости. Типизированные поля могут читать точные decimal-строки по схеме; неоднозначные Any/union-поля требуют явного tag либо нормализованного предметного представления.

Не переводить Decimal в float ради скорости; не применять `default=str` ко всем неизвестным объектам; не лечить transport TypeError повторным дорогостоящим вычислением. Число байтов, hash и версия должны связываться с действительно переданным представлением. Access/tenant-проверки не заменяются digest: он устанавливает целостность bytes, не полномочия.

**Приёмка.** Непустые бюджеты, Decimal в union, вложенные типы, настоящие ArtifactRef, OutputAwareNodeOutcome; оба поддерживаемых JSON backend; cold/warm; unsupported/non-finite; повреждённый digest. Проверять значение и тип после round-trip. Существующие тесты пустого состояния и простых params прочитаны; они не объявлены отсутствующими и не выданы за покрытие Decimal. Реальные Ray/Temporal не запускались.

<!-- SOURCE_END B:B94 -->

