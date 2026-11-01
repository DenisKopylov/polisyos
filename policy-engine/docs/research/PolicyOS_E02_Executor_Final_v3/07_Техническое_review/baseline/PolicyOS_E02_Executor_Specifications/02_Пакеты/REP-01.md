# REP-01 — Runtime replay: прямой Scientist owner без лишнего compatibility hop

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-033. Тип: native activation/compatibility qualification.

Довести уже выполненную переадресацию к Scientist до доказанного persisted replay/resume и installed API без повторного перемещения алгоритма и преждевременного удаления compatibility.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/REP-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C77_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/REP-01_исходные_строки.txt), исходный объединённый план §REP-01 (исторические строки 8893–9007).

## 2. Уже работает — сохранить

- Root ровно10 lazy exports прямо Scientist; runtime.replay сохраняет20 точных objects, enum values и signatures.
- Core CLI импортирует deterministic/backend/checkpoint отложенно; dynamic inventory и benchmark direct owner остаются согласованными.
- RunManifest1.0 reader/writer и независимый runtime.quality.replay сохраняются (LK15).
- Complete/recoverable/incomplete, snapshot availability/actual execution, bit-exact/CI-bounded/skip не сливаются.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C77-G01 | qualify: Native full imports, persisted backend replay и remaining-node resume, shared package check вместо fixture factory. | REQ-REP-01-01, REQ-REP-01-02 |
| C77-G02 | lifecycle: Compatibility retirement получает явное окно и downstream census; сейчас supported shim сохраняется. | REQ-REP-01-03 |
| C77-G03 | qualify: Historical corpus и точный смысл verification требуют самостоятельных evidence, не API availability. | REQ-REP-01-02, REQ-REP-01-03 |

### Исходные обязанности, не только новые R

- LA-033: actual source/string/FQN/monkeypatch consumers, documentation и installed paths квалифицируются раздельно; literal census не production census.
- Удаление shim возможно только после реального окна поддержки; прекращение root API отдельное решение, не часть этого ремонта.
- LK15: похожий Core DTO не конвертер historical RunManifest schema; сохранить старые run directories и quality replay.

## 4. Нормативный контракт

### REQ-REP-01-01
На supported native и installed package root import не загружает Scientist/compatibility до обращения, __all__ содержит прежние10; каждый root binding и20 shim exports identity/signature/enum-compatible с Scientist. Unknown attribute отказан. Core direct delayed path, dynamic inventory и benchmark разрешаются к тому же canonical object без транзита через shim.

Источник: LA-033; аудит: C77-G01; проверки: TEST-REP-01-01.

### REQ-REP-01-02
Малый настоящий producer создаёт complete replayable packet в local CAS; fresh CLI --check-only оценивает graph, обычный replay действительно исполняет выбранный backend, а resume исполняет только оставшийся узел из свежего checkpoint head. Incomplete/tampered packet не исполняется. Verification SKIP явно skipped; bit-exact сравнение refs не scientific validation; CI-bounded получает собственный фактический oracle либо остаётся UNQUALIFIED.

Источник: LA-033; аудит: C77-G01, C77-G03; проверки: TEST-REP-01-02.

### REQ-REP-01-03
До согласованного retirement supported shim20 и root10 остаются; source-qualified исторический RunManifest1.0 читается прежним Runtime owner без изменения bytes и без подмены quality replay/Core DTO. Census фиксирует denominator, FQN/string/monkeypatch/docs/package callers и внешние неизвестные; отсутствие внешнего usage не выдумывается. Удаление shim — отдельный approved change.

Источник: LA-033; аудит: C77-G02, C77-G03; проверки: TEST-REP-01-03.

## 5. Техническое решение и producer → consumer

Wire-existing уже сделан: не переносить deterministic повторно. Добавить/расширить native tests вокруг _cmd_replay/_cmd_resume и replay_packet, используя реальные store factory и checkpoint owner; переиспользовать RES resume scenario. Проверить installed import graph вместе с общим packaging owner. Если native mismatch воспроизведён, исправлять конкретный consumer/binding, сохраняя delayed import. Отдельно подготовить compatibility matrix и решения по historical corpus, не делать migration всех run files.

### Проверенные owners на срезе
- policy-engine/src/polisyos/runtime/__init__.py: _LAZY_IMPORTS, __getattr__
- policy-engine/src/polisyos/runtime/replay.py: exact compatibility aliases
- policy-engine/src/polisyos/core/components/_cli_replay.py: _cmd_replay, _cmd_resume
- policy-engine/src/polisyos/scientist/replay/backend.py: replay_packet
- policy-engine/src/polisyos/scientist/replay/deterministic.py: completeness_check, verify_replay
- policy-engine/src/polisyos/runtime/manifest: RunManifest schema owner
- policy-engine/architecture/imports/dynamic.toml
- policy-engine/benchmarks/advanced/common.py

Eager import и расширение root до20 не упрощение, а ABI/side-effect изменение. Новый replay subsystem или универсальный semantic model не нужен.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-REP-01-01
- Уровень: unit + targeted native integration.
- Setup: Fresh P-CORE process и затем isolated installed wheel environment; existing compatibility tests.
- Действие: Import runtime, inspect sys.modules, получить все10 root и20 shim exports, unknown symbol; check delayed CLI and dynamic inventory targets.
- Точный oracle: До обращения нет heavy modules; exact identities/signatures/enums unchanged; root10 не20; canonical target Scientist, не shim. Installed и checkout imports совпадают, import trace приложен.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-REP-01-02
- Уровень: native producer → CAS → fresh CLI → backend/checkpoint.
- Setup: Исполнимый tiny Scientist/Foundry-supported workflow с known seed и2 узлами, первый persisted, второй callback счётчик; реальный CAS/profile admission.
- Действие: --check-only, replay, resume, повтор resume; missing/tampered binding; отдельно skip/bit-exact modes и --check-only --export conflict.
- Точный oracle: check-only не вызывает backend; actual replay даёт исполнимый persisted result, resume оставшийся узел ровно1, completed не повторён. Incomplete даёт nonzero без execution; conflicting flags exit2 без output. SKIP не passed verification; recovery/complete уровни не слиты.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-REP-01-03
- Уровень: unit + targeted native integration.
- Setup: Source-qualified finite historical RunManifest corpus с provenance/hash, current writer sample и separate quality schema; consumer census.
- Действие: Read/finalize/readback поддержанных1.0 samples; resolve old imports/FQN/monkeypatch fixtures; документировать support window.
- Точный oracle: Bytes существующих manifests не переписаны, refs/status прочитаны прежним owner; quality algorithm не заменён. Census сообщает границы, неизвестный downstream остаётся неизвестным. Без принятого окна shim не удалён.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_rep_01.py`; `policy-engine/tests/unit/scientist/replay/test_deterministic_compatibility.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: счётчик tiny scientific node и controlled missing/tamper inputs; без внешних services. Запрещено: fixture canonical objects/factory вместо final native path, complete synthetic role graph вместо исполнимого workflow.

## 7. Общая интеграция и порядок

RES-01/02/03 дают один настоящий checkpoint/fresh-reader/resume сценарий; REP проверяет CLI activation и direct owner. Packaging объединить с общим установленным baseline, не строить wheel на каждый пакет.

Точные общие сценарии: E02-I06-B из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

LA migration эквивалентна только по import owner. Historical bytes unchanged; source census C77 ограничен3009 tracked files и не обновляется автоматически как текущий факт. Retirement не blocker для native qualification, но остаётся отдельной обязанностью lifecycle.

## 9. Free-grow и design direction

- Direct canonical owner уменьшает compatibility hops без нового контракта.
- Артефактная полнота, replay execution и scientific confidence имеют разное доказательство.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Зафиксировать реально поддержанные historical manifest версии и окно old module support; нет evidence — сохранить compatibility, не удалять.
- CI-bounded scientific interpretation требует отдельного domain oracle, не переименования existing tolerance calculation.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

