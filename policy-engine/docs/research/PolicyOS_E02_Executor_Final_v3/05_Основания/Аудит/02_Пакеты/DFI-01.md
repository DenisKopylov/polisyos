# DFI-01 — самостоятельные writer / validator / loader dependencies

## 1. Решение

**Ограниченно оценён, не закрыт.** Исходный broadcast не просто переименован: у трёх leaves есть конечные owner bindings, ленивые адресные proxies и request-scoped compatibility context. Canonical выбранные вызовы работают **до импорта старого фасада**; facade больше не раздаёт произвольные globals соседям. **Новых подтверждённых локальных дефектов R в проверенной области не найдено.** Полной эквивалентности ingestion по database/network traces пока нет.

Свежий результат: **5 MATCH; 15 unchanged existing test bodies / 15 cases PASS** в явно ограниченной оснастке. MATCH не означает product PASS. Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.

[Полная карточка](../05_Источники/DFI-01_исходные_строки.txt) · [Pinned источники](../05_Источники/C93_источники.json).

## 2. Матрица исходных IDs

| ID | Подтверждено | Остаток |
|---|---|---|
| LA-038 / M, этап 1 из 2 | Finite owner declarations для writers/validators/loaders; нет wildcard и global broadcast; canonical consumers, immutable scoped overrides, actual request/SQL capture | C93-G01 native trace parity; C93-G02 финальный namespace и pipeline в DFI-02 |
| LK19 | Существующие Fabric DTO/connectors/profile boundaries не объявлены лишними | Полная equivalence сетевых helpers не установлена; удаление acquisition owners не предлагается |

LA-038 встречается в двух пакетах, но остаётся **одним** исходным ID. Accountable closure — DFI-02. Наличие уже переключённого pipeline не закрывает остатки автоматически.

## 3. Actual owner и передача данных

Каждый из трёх leaves объявляет точные `(owner, symbol) → (module, symbol)` связи. Resolver сначала проверяет конечный manifest, затем request-scoped override, затем явную local developer substitution и только после этого импортирует фактического владельца. Противоречие между compatibility и owner tables отвергается. `fallback` служит type witness, а не запасным алгоритмом. Локальная установка объявленных proxy names через `globals().setdefault` остаётся, но **не является старым обходом и обратной записью общего namespace во все модули** (`S01–S03`).

DTO и context остаются в существующем contracts-файле. Context копирует mapping, замораживает его, хранится в ContextVar и сбрасывается в finally. Это developer seam, не authority predicate: значения substitutions не валидируются как доказательства, и этим API нельзя обосновывать научную достоверность (`S04:294–355`).

Конкретная цепочка writer: ObservationPlan + rows → actual transformer normalization/country mapping → condition-aware observation ID → existing-ID lookup → actual chunker → SQL executemany payload → attempted/inserted/replaced stats. В опыте только DB boundary и lookup заменены capture/empty fixture; payload, provenance и счётчики формирует реальный код. Validator формирует настоящий immutable FetchRequest с временным окном, а loader разрешает country dependency у transformer без facade bootstrap (`S01:1361–1453`, `S02:1810–1866`, `S03:1438–1449`, `S06`, `S13`).

Facade использует конечный перечень names и scope snapshot; `_sync_implementation_globals` — no-op. Текущий pipeline уже импортирует canonical API и переносит seven ingest counters в metrics, но эта ветка **не исполнялась** в C93 (`S05`, `S15`). Полная проверка остальных leaves и этого маршрута — следующая DFI-02, не результат трёх selected consumers.

## 4. Свежие различающие проверки

1. **P01:** восемь unchanged existing leaf bodies проходят до первого facade import. Включены direct transformer resolution, request-scoped sketch ID, capability country lookup, year-window override и actual FetchRequest dates. Это не три пустых smoke imports.
2. **P02:** четыре unchanged contract bodies подтверждают stats/write payload, copy-and-freeze mapping, nested reset, async tasks / два threads и cancellation без порчи живого sibling. Они исполняют whole actual contracts owner.
3. **P03:** полный AST трёх leaves: writers — 13 owner proxies / 11 literal resolver calls; loaders — 12 / 19; validators — 18 / 7. Все объявленные proxy targets существуют в AST шести owners; wildcard imports отсутствуют. Этот полный структурный census **не** подтверждает semantic correctness всех функций.
4. **P04:** пять synthetic строк с разными conditions проходят actual writer→normalizer→ID→chunker; получены пять разных IDs, chunks **2/2/1**, stats **5/5/0**, неизменные acquisition method / watermark / dataset version. SQL и все 13 полей каждой строки сохранены. DB commit, dedup against real existing rows и raw-source bytes этим не доказаны.
5. **P05:** whole actual facade с двумя явно synthetic соседями не переносит неизвестный атрибут ни в один из selected modules. Поддержанный override даёт `SCOPED`, после scope direct canonical вызов снова даёт `UKR`, transformer global не изменён. Ещё три unchanged facade/contract tests проходят. Это не тест полного API ingestion и не доказательство независимости всех шести leaves.

## 5. Что сохранить и что осталось

**Сохранить:** existing DTO owners и finite maps; lazy import без facade bootstrap; current owner resolution; explicit scoped substitutions; immutable ContextVar/reset; actual request semantics; condition-aware IDs и provenance; writer chunking/counts; реальные Fabric contracts. Не возвращать broadcast ради старых monkeypatch patterns и не заменять его wildcard import или новым service container. Не переписывать source-specific algorithms под видом equivalent move.

**C93-G01 — native эквивалентность группы.** В supported environment исполнить existing leaf tests и небольшой общий LANE-08 ingest witness с actual database boundary. Сопоставить source profiles, request filters/dates, bytes, empty/error paths, budget accounting, rows и counts. Existing source code и SQL capture дают полезную частичную уверенность, но не доказывают полный producer→persisted artifact→consumer. Отсутствующая среда — не product defect.

**C93-G02 — остаточная миграция.** В DFI-02 независимо оценить registry/transformers/api, finite facade lifecycle, sync/async signatures и конкурентные overrides, затем canonical pipeline consumer. Не считать closure по отсутствию слова broadcast или по synthetic-only import. Старый source-plan тезис «pipeline ещё зовёт facade» уже не описывает текущий call site; полезное переключение сохранить, а его работоспособность доказать.

Положительный synthetic trace не делает данные эмпирически надёжными и не доказывает causal identification. Для этой миграции не требуется универсальный детерминистический генератор моделей: задача — честно соединить уже существующих owners без потери семантики.

## 6. Воспроизводимость и пределы

[Команды / exit / logs](../04_Проверки/C93_DFI01/commands.json) · [Diagnostics](../04_Проверки/C93_DFI01/bounded_diagnostics.json) · [Полный AST census](../04_Проверки/C93_DFI01/run01/full_group_dependency_inventory.json) · [SQL capture](../04_Проверки/C93_DFI01/run01/writer_capture.json) · [Native status](../04_Проверки/C93_DFI01/native_verification.json) · [Оснастка](../04_Проверки/C93_DFI01/Чтение_и_границы.md) · [Остатки](../01_Реестры/C93_остатки.json).

Run01 exit 0: 5 MATCH, 15/15 existing cases PASS. Bodies unchanged; decorators/import setup представлены isolated runner. Parent shells, actual capability AST class и synthetic api/registry neighbors описаны явно. Native writer import BLOCKED на транзитивном Core store.py:2118 (Python3.14 syntax при Python3.12); pytest/DuckDB отсутствуют. PEP695 functions реально исполнялись, Python3.12 их поддерживает. Native ingest, real SQL/network и scientific validation — UNRUN. Репозиторий и зависимости не менялись.

**93/127 рассмотрены ограниченно. Следующий — DFI-02; фаза 2 не начата.**
