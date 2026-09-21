# GRF-02 — Неизменяемый граф, mixed-edge export и версии кэша

**E02 · окно CP5 · локальная проверка L · начальный статус planned.**

**B:** B219, B220. **LA:** Нет; технический пакет B.

**Предшественники:** [GRF-01](../bundles/GRF-01.md). **Совместная очередь:** LANE-05.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Сохранить directed/bidirected/lag отношения в поддержанном представлении. Публиковать глубоко immutable topology; новая версия не наследует старые derived-properties. Кэши строятся один раз для реальной версии и сохраняют правильный cleanup.

**Различающие тесты и сохраняемое поведение.** X→Y и X↔Y не перезаписывают друг друга при перестановке edges. После прогрева export/adjacency новое пустое ребро-представление совпадает с dump и cold-query. Nested mutation отвергается или остаётся только в builder до публикации. Weakref-cleanup сохраняется.

**Не считать исправлением.** Не хэшировать весь граф при каждом BFS и не отключать все кэши. MultiDiGraph сам по себе не делает directed-path algorithm причинно корректным.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/admg_ops.py
policy-engine/src/polisyos/ir/analytics/causal_graph.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/methods/catalog/causal/_graph_projection.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_grf_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** GRF-01, GRF-03. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Условия общего использования:**

**A07.** Active-query pruning сохраняет правильную surgery, immutable topology, factual ancestors и shared-noise/replica semantics. Частичный temporal/PAG профиль не присваивается статическому успеху.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B219

Источник B_r19, строки 5375–5388; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B219 -->
## B219. Простое DiGraph-представление перезаписывает параллельные причинные отношения

**Происхождение и приоритет:** C21-04. Условно высокий на границе, обещающей полный каузальный граф. Основание: `CausalGraphModel.to_networkx`. [C21.R01]

**Проблема.** Адаптер создаёт `networkx.DiGraph`, где одна упорядоченная пара вершин имеет одну запись атрибутов. Но исходный IR может хранить одновременно направленное воздействие X→Y и bidirected-связь X↔Y, а также несколько лагов. Последний `add_edge` заменяет атрибуты предыдущего отношения.

**EDGE01–EDGE02.** Два исходных отношения X→Y и X↔Y дают одно ребро. Перестановка записей меняет surviving `mark_src` между tail и arrow. Два лаговых ребра также сокращаются до одного. Контрольный `MultiDiGraph` с полной идентичностью рёбер сохраняет оба. Поддержка parallel edges является явным свойством этого контейнера. [C21.E04]

**Исправление.** Выбрать представление по назначению: отдельные directed/bidirected adjacency либо типизированный mixed-edge graph; для транспорта допустим MultiDiGraph с ключом, включающим тип концов и lag. Полные сведения о свидетельствах остаются прикреплёнными к правильному ребру. Простой DiGraph может сохраняться как явно ограниченная проекция для задач, которым она действительно достаточна.

Важно: MultiDiGraph ремонтирует хранение, но сам по себе не делает обычный directed-path алгоритм каузальным. Потребитель должен интерпретировать метки и временную структуру. Нельзя заменять bidirected-связь двумя произвольными причинными стрелками.

**Положительная граница.** Нативный `CachedAdjacency` уже хранит directed- и bidirected-множества раздельно. Не заявляется, что весь ID-engine проходит через NetworkX или теряет эту пару. Rustworkx/Kuzu не исполнялись. Приёмка — round-trip и неизменность результата при перестановке edges, отдельно для каждого реально используемого backend и класса графа.

<!-- SOURCE_END B:B219 -->

## Исходное основание B220

Источник B_r19, строки 5389–5402; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B220 -->
## B220. Frozen-модель не обеспечивает неизменность topology; кэш и копия расходятся с текущим графом

**Происхождение и приоритет:** C21-05. Высокий для переиспользования изменяемых графов; средняя связующая правка. Основания: nested lists/frozen DTO, ID-based adjacency cache и cached export properties. [C21.R01–R02]

**Проблема.** Pydantic `frozen=True` защищает присваивание полю, но `nodes`, `edges` и вложенные metadata остаются изменяемыми. Кэш adjacency адресуется `id(graph)`, а подготовленные Kuzu-строки — `cached_property`. Кроме того, обычный `model_copy(update=...)` переносит уже вычисленные cached properties в новый объект. В результате даже новый object-id не всегда устраняет устаревшую экспортную проекцию. Поверхностная immutable-семантика Pydantic документирована. [C21.E05]

**CACHE01–CACHE04.** Для A→B после первого чтения `edges.clear()` разрешён, хотя прямое присваивание `edges=[]` запрещено. Сериализация видит ноль рёбер, тёплый `ancestors(B)` — A и B, холодная реконструкция — только B, экспорт продолжает содержать одно ребро. Отдельно `model_copy(update={'edges':[]})` даёт корректную новую adjacency, но наследует старую экспортную строку. Свежая валидированная версия согласует оба представления. Положительный контроль: weakref-cleanup после удаления объекта действительно очищает adjacency-cache.

**Исправление.** Сделать семантически существенную topology глубоко неизменяемой и обновлять её через новый снимок. Конструктор новой версии обязан сбрасывать зависимые derived-properties; кэш связывается с реальной версией topology и правильной областью параметров. Подготовленные возвращаемые строки тоже не должны быть общим доступным для изменения источником истины.

Не нужно пересчитывать hash большого графа при каждом BFS либо отключать все кэши. Предварительная проверка неизменяемой версии и одноразовая adjacency сохраняют выигрыш. Если mutable-builder нужен, он остаётся отдельной подготовительной формой и публикует immutable-view только после завершения.

**Приёмка.** Проверить mutation-отказ, copy/update после прогрева cached property, согласованность dump/ancestors/export и правильное освобождение старого cache-entry. Здесь установлен механизм локального расхождения, а не порча настоящей Kuzu-базы. Прежнюю работающую weakref-инвалидацию нельзя ошибочно объявлять утечкой и заменять небезопасным LRU.

<!-- SOURCE_END B:B220 -->

