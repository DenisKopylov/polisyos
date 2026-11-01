# MIG-01 — единый migration runner и настоящая Trinity validation

## 1. Решение

**Ограниченно оценён, не закрыт. Главный validation repair выполнен.** Same-version `migrate_policy_ir` теперь явно вызывает настоящий `TrinityBundle.model_validate`, а затем возвращает исходный mapping. Недостижимая self-edge удалена; generic engine не заставляют исполнять self-loops. Старый root `migrate.py` уже отсутствует, действующий operator runner находится в `tools.ops_runners.migrations.migrate`; исторический дубль и ошибочный Common import не восстановлены.

**Подтверждён один низкий остаток C79-R01:** при раннем fsync failure atomic text writer сохраняет старый output, но оставляет созданный temp файл. False success и потери старого output не установлено.

Свежие проверки: **6 bounded MATCH, 14 неизменённых bodies / 19 cases PASS**. Модель Trinity и registry настоящие, не минимальные fixtures. Native отдельный current/incomplete control также PASS; whole registered tools CLI остаётся blocked/unrun. Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/MIG-01_исходные_строки.txt) · [Pinned sources](../05_Источники/C79_источники.json).

## 2. Матрица исходных требований

| ID | Фактический результат | Остаток |
|---|---|---|
| LA-010 + AM01 | Root duplicate retired; canonical runner имеет один parser/load/dump, IR-owned migration, actual helper binding и atomic writer. Common не экспортирует старую Policy IR constant | R01 cleanup; G01 registered/installed execution; G02 external retirement |
| LA-049 | Current no-op вызывает реальный validator; incomplete/nested invalid отвергаются до output; self-edge отсутствует; tuple/auto_migrate/split semantics сохранены | Native full CLI и дальнейшие lifecycle/converted-artifact qualification G01–G03 |
| LK26 | Loading guard действительно вызывает настоящую модель; готовый model сохраняет identity | Не выдавать shape validation за exact-version/artifact authority |
| LK27 | Actual helper binding отказывает missing contract directory до записи | Operational binding не release review, validation или path identity proof; run_manifest scope у MIG-02 |

Удаление root path не трактуется как отсутствие всей migration capability. Source plan содержит историческое состояние; current Git и source dispatch проверены отдельно. Новая копия parser или возвращение константы в Common не нужны.

## 3. Producer → validation/conversion → output

Canonical `main` сначала проверяет operational binding, читает JSON/YAML object, затем выбирает реального владельца: IR migration для policy_ir, Fabric/Common format conversion для dataset_manifest, отдельный runtime path migrator для run_manifest. `_dump` сохраняет формат и использует общий atomic writer (`S01`).

`migrate_policy_ir` проверяет version syntax, legacy markers и explicit major consent. При равных версиях теперь выполняется **реальная Trinity model validation**, но возврат остаётся исходным mapping, не нормализованным dump. Это полезное различие: helper `migrate_policy_ir_identity` возвращает model_dump с defaults, `split_to_bundle` возвращает model, `load_trinity_bundle` — `(model, None)` (`S02–S06`). Ни один из этих результатов не означает выполненную version conversion.

Generic engine по-прежнему возвращает caller-owned no-op profile до поиска ребра (`S10`); validation находится на публичной IR boundary, а не спрятана в self-loop. Common dataset conversion отдельно переименовывает поддержанные поля 0.9→1.0 и не объявляет себя полной Fabric DTO validation (`S11`, `S12`). Новый report для no-op не придуман.

Registered tool source discovery выбирает `ops_runners` и actual module/main (`S20`). Внешний `tools.cli` импорт блокирован текущим runtime; факт source delegation не выдаётся за исполнение preflight, installed entry или exit translation.

## 4. Свежие проверки

1. **P01 — MIG regression:** 8 unchanged bodies / 13 cases PASS. Полный структурный Trinity JSON/YAML, default/explicit target; spy вызывает настоящий model validator; incomplete current mapping и malformed nested model отказаны, старый output сохранён; legacy/major и non-object input отказаны; dataset format conversion действительно выполняется и сохраняет input.
2. **P02 — старый helper contract:** все 6 bodies/cases PASS с настоящим TrinityBundle: split mapping, migrated-valid/invalid probe, model loaders и non-mapping error. Старые тесты не удалялись вместе с названиями helpers.
3. **P03 — разные результаты:** current no-op сохраняет `result is input`; готовый model сохраняется loader/split по identity; tuple report равен None. Identity helper возвращает новый normalized dump с настоящими ModelSpec defaults. Это не скрытый converted result.
4. **P04 — operational binding:** actual validator читает checkout TOML. В собственном fixture удалена required contract directory; actual main получает FileNotFoundError до output, input/output неизменны. Guard сохранён, а не stubbed PASS.
5. **P05 — R01/контроль:** actual atomic text function и canonical main при injected os.replace failure сохраняют old output и удаляют temp. При injected os.fsync failure old output/input также сохранены, но один `.output.*.tmp` остаётся с новым payload. Ошибка честно доставлена caller.
6. **P06 — parse/shape boundaries:** JSON/YAML strings и UTF-8 bytes валидируются настоящей моделью. Invalid UTF-8/invalid nested mapping дают PolicyLoadError; malformed explicit JSON даёт JSONDecodeError, YAML — ParserError. CLI malformed JSON не меняет output. Shape-only loading принимает структурно корректный schema_version 2.0, тогда как migration явно отвергает legacy 2.*; это уже описанное различие API, не доказанный bypass exact-version owner (`S24`).

Отдельный **native subprocess без tools seams** подтвердил current mapping identity и ValidationError для `{"schema_version":"1.0"}`. Это существенно сильнее старой модельной фикстуры из исходного аудита, но всё ещё небольшой структурный corpus, не production admission.

Root-entry census охватывает все **7021 tracked `.py/.toml/.sh`** в src/tools/tests/architecture плюс pyproject по сохранённым patterns. Единственный match — filename-pattern test (`S26`), не запуск root CLI. Root path не существует и не tracked. Census не охватывает downstream пользователей или динамически составленные команды; старые plan/docs mentions не считаются исполняющими consumers.

## 5. Что сохранить и что осталось

**Сохранить:** один canonical runner; настоящий validator в same-version boundary; source identity no-op, helper model/dump различия; отсутствие self-edge; JSON/YAML и separate converters; operational binding и containment; tuple/auto_migrate compatibility до отдельного lifecycle решения. Не возвращать retired root parser и не удалять IR loading/migrations целиком.

**C79-R01 — low, cleanup atomic text writer.** `tmp_path` присваивается только после `handle.write`, `flush` и `fsync` (`S13:88–104`). Если fsync выбрасывает exception, finally видит None и не удаляет созданный file. Контроль replace-failure показывает, что поздняя ошибка очищается. Минимальное направление: удерживать созданное имя до рискованных операций и проверять cleanup на write/flush/fsync/replace faults в существующем owner. Не менять atomic replace/secure output contract. Проверка ограничена unbound-output branch с собственными fixtures; power-loss durability и активный SecureOutputRoot не аттестованы.

**C79-G01 — native registered/installed path.** Исполнить existing public command test и реальный output-scope/preflight/exit путь на supported runtime, затем общий LANE-06/CP2 integration. Сейчас actual main и atomic function выполнены за явно описанным import/scope seam; full tools CLI body исключён, не назван PASS. Python3.12/Pydantic вне project baseline, pytest отсутствует.

**C79-G02 — lifecycle и ABI.** Root retirement source state подтверждён, внешние consumers ещё не аттестованы. Прежние split/tuple/auto_migrate адреса не механические aliases: сохранять input/model/error contracts до согласованного окна. Docstring обобщает parsing как PolicyLoadError, но фактические JSON/YAML exception types различаются; перед нормализацией ошибок нужен явный compatibility выбор, не тихая подмена. Shape loader не exact-version loader и не admission authority.

**C79-G03 — смысл validation/conversion.** Настоящая модель доказывает структурный контракт конкретного input; не semantic adequacy, научную валидность, evidence custody или исполнимость политики. Для нового реального policy transition нужен versioned converter и его corpus, не фиктивный migration report. Исторические outputs не повышаются до прошедших новый validator задним числом. Dataset rename — отдельная format conversion, не универсальное исправление всех artifacts.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C79_MIG01/commands.json) · [Cases/observations](../04_Проверки/C79_MIG01/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C79_MIG01/native_verification.json) · [Остатки](../01_Реестры/C79_остатки.json).

Run01 остановился на неполном внешнем tools.lib shell; run02 исправляет только harness и завершается exit0. Whole native tools.fs import блокирует Python3.14 `except` syntax. Selected atomic function80–104 исполнена unchanged; `active_secure_output_root=None` — явный unbound fixture, не квалификация SecureOutputRoot. Модель/registry/loader не заменены. Existing test bodies unchanged, pytest decorators/fixtures обслуживает минимальный внешний helper; registered tools_cli body UNRUN. Input/output byte snapshots и negative JSON fixtures сохранены losslessly с отдельной картой переименования. Checkout чист, dependencies/source/tests не менялись.

**79/127 рассмотрены ограниченно. Следующий — MIG-02. Фаза 2 не начата.**
