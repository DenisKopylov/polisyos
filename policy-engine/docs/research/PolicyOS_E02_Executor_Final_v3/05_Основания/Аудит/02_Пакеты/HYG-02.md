# HYG-02 — адресные retirement без удаления полезных owners

**C125 · LANE-12 · LA-008, LA-009, LA-018 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

`lex.factlog` удалён, actual NormPack caller обращается к Fabric owner. Retired Scientist evidence_sources/provenance/claims roots не восстановлены. Но `_shim.py` остаётся, а три governance aliases ещё существуют и используются public Scientist passes facade/tests. Их наличие не три независимых policy implementation и не повод удалять весь governance/evidence слой.

**6 MATCH; 8 unchanged bodies/8cases:4PASS4environmentFAIL. Новых подтверждённых R нет.** Сохраняются G01–G03: точное lifecycle решение, миграция actual alias consumers и native full reader/compatibility qualification.

## 2. Матрица исходных оснований

| ID | Original repair | Actual capability / состояние | Остаток |
|---|---|---|---|
| LA-008 | Конечный scan3helper names; убрать ненужный _shim без нового framework. | Helper по-прежнему только forwarding+metadata. Actual empty compatibility manifest, negative roots и lightweight public imports работают. В finite static scan живые imports helper не найдены. | G01: точное retirement/package/external решение; отсутствие caller в bounded scope не абсолютный ноль. |
| LA-009 | Мигрировать3aliases к Core, сохранить actual Scientist passes и identity. | Реализации у Core; aliases narrow warning reexports. Builtin registry factories уже Core. Но Scientist facade ещё relative-imports Legal/Safety aliases, identity test ещё3legacy imports. | G02: конкретные2facade/3test consumers и config/plugin/native qualification; не произвольный sunset. |
| LA-018 | Снять Lex alias только после миграции, сохранить Fabric read semantics. | Alias отсутствует, root Lex export map не содержит factlog, exact missing-module check PASS; actual select_sources импортирует Fabric reader. README фиксирует removal. | G03: native Fabric→Lex result/access/provenance и distribution/historical tests; bounded adapter не actual Parquet. |

## 3. Producer → consumer

[Evidence helper](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/evidence/_shim.py#L10-L63) устанавливает aliases и metadata, но не claim/provenance calculation. [Compatibility registry](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/evidence/compatibility.py#L24-L59) пуст; его дата не назначает sunset governance aliases.

[Scientist passes facade](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/passes/__init__.py#L86-L117) реально маршрутизирует Legal/Safety через старые filenames. [Builtin factories](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/governance/pass_entrypoints.py#L7-L10) уже импортируют Core напрямую; plugin registry отдельно проверяет ValidatorPass и duplicate pass_id. Миграция этих addresses не требует нового policy engine.

[Lex caller](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/lex/normpack/select_sources.py#L1-L47) → `fabric.world` → `store.segments.load_world_facts`. [Reader](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/fabric/world/store/segments.py#L389-L448) читает typed manifest index, выбирает requested columns, объединяет readable segments, возвращает empty shaped frame при отсутствии данных. Missing files пропускаются по текущей readable-segment семантике; нет основания приписать это alias migration. Malformed index не выдаётся за пустоту. Authorization/current provenance authority не следует из DataFrame.

## 4. Проверки

| Проверка | Результат и предел |
|---|---|
| P01 | Native lightweight Scientist/evidence/Lex roots импортируются;4retired FQNs дают ModuleNotFoundError с точным missing name. Heavy export resolution не заявлено. |
| P02 |6 unchanged bodies:2negative batch PASS;3shared-shim identity и1actual Fabric→Lex subprocess FAIL из-за supported-runtime syntax mismatch. |
| P03 | Actual native _shim на math fixture сохраняет identity explicit exports, dynamic getattr и metadata. Это не evidence capability и не ratified sunset. |
| P04 | Actual selected Fabric reader + native manifest DTO: shaped empty, requested provenance/data forwarded, missing segment skipped, requested error wrapper и malformed-index refusal. Явный DataFrame adapter вместо Parquet и no-op lock. |
| P05 |Tracked lexical census28,264paths/123matching lines;6,857active Python files,44unsupported;5static imports targets.2facade imports+3test imports разобраны, helper imports не найдены. |
| P06 |2additional unchanged taxonomy bodies PASS; empty shim manifest проверен также на2026-11-01, retired roots отсутствуют. |

[Probe](../04_Проверки/C125_HYG02/probe_hyg02.py) · [cases](../04_Проверки/C125_HYG02/run02/existing_cases.json) · [taxonomy](../04_Проверки/C125_HYG02/taxonomy02/observations.json) · [census](../04_Проверки/C125_HYG02/run02/census.json) · [команды](../04_Проверки/C125_HYG02/commands.json). Две первоначальные harness ошибки сохранены отдельно;4environmentFAIL не превращены в PASS после correction.

## 5. Остаток и сохраняемые роли

**C125-G01:** закончить решение для точного `_shim.py` и3names на основании bounded census и конкретных external/package obligations. Если нужного caller нет, удаление без переселения claim/evidence логики; если есть — минимальная временная связь с принадлежащим owner условием завершения. Не считать baseline/generated-doc reference исполняемым client без дополнительного основания.

**C125-G02:** перед retirement Legal/Safety aliases переключить existing passes facade на Core, затем выполнить config/plugin/monkeypatch/identity tests и заменить relevant legacy tests negative controls. Default factories уже canonical; широкое удаление Scientist passes лишит настоящих validators. Arbitrary individual sunset не выдумывается, существующий compatibility warning сохраняется до решения.

**C125-G03:** повторить actual native Fabric→Lex tests на supported3.14/declared deps, real Parquet, historical manifests и access/provenance context; проверить wheel/sdist отдельно. Missing historical mirror selector не причина восстановить удалённый Lex alias. Не доказывать источник права, актуальность фактов или разрешение доступа тем, что fixture DataFrame содержит поле provenance.

Сохранить [root evidence role](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/evidence/README.md#L1-L29): cross-producer conflict/effective-independence records, не duplicate Scientist evidence и не positive support сами по себе. [OPA facade](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/opa_input.py#L1-L18) явно public и не включается в удаление по слову shim. Полные implementations этих protected owners здесь не аттестованы.

[Карточка](../05_Источники/HYG-02_исходные_строки.txt) · [sources](../05_Источники/C125_источники.json) · [остатки](../01_Реестры/C125_остатки.json) · [границы](../04_Проверки/C125_HYG02/Чтение_и_границы.md).

**125/127. Следующий HYG-04; осталось2 пакета. Фаза заданий исполнителю не начата.**
