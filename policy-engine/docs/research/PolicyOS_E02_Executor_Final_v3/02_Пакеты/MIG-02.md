# MIG-02 — RunManifest: сохраняющее identity преобразование paths

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-048. Тип: path-only current contract + native/historical qualification.

Подтвердить настоящий Runtime writer→converter→reader на одном declared root без basename подмены, ложного relocation или дублирования shared atomic fix.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/MIG-02.md), [все остатки](../05_Основания/Аудит/01_Реестры/C80_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/MIG-02_исходные_строки.txt), исходный объединённый план §MIG-02 (исторические строки 9303–9428).

## 2. Уже работает — сохранить

- Runtime manifest_migrations — единственный path converter; все entries preflight проверяются до output.
- Значимые subdirectories, resolved source identity/containment, deepcopy и exact conflicting path отказ.
- Никакого external copy; --to явно отказан в path-only режиме; RunManifest1.0 reader/writer остаются.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C80-G01 | qualify: Registered native CLI/Runtime persisted roundtrip и shared writer failure свидетельство MIG-01. | REQ-MIG-02-01 |
| C80-G02 | qualify: Явно квалифицировать root/CWD, narrow path-only профиль и point-in-time limitation вместо обещания relocation. | REQ-MIG-02-02 |
| C80-G03 | qualify: Source-qualified historical layouts и actual readers; собственный новый run не весь old corpus. | REQ-MIG-02-03 |

### Исходные обязанности, не только новые R

- LA-048: историческая inline basename логика уже заменена actual Runtime owner; не выполнять move повторно.
- Исходное предложение rebase/relocation сужено до явного normalization profile: root сохраняется, unsupported external/--to честно отказаны. Новый relocation engine без реальной потребности не нужен.
- LK15/LK27: Runtime persisted schema и containment/binding сохраняются; совпадение адреса в момент проверки не immutable custody.

## 4. Нормативный контракт

### REQ-MIG-02-01
Actual Runtime writer создаёт RunManifest1.0 с artifacts, registered CLI преобразует копию JSON/YAML, fresh native Runtime DTO/resolver читает те же resolved paths и bytes для каждого entry. Весь список проходит preflight до _dump: mixed valid+missing/conflicting/escape entry сохраняет old output/input. Shared C79-R01 закрывается REQ-MIG-01-01; run_manifest ветка подтверждает использование того же исправленного writer без своего patch.

Источник: LA-048; аудит: C80-G01; проверки: TEST-MIG-02-01.

### REQ-MIG-02-02
Normalization использует declared run_root либо documented input.parent.parent default, сохраняет root spelling и nested source identity. Relative root остаётся привязанным к явно записанному CWD; перенос output manifest не меняет artifact root. External/missing/broken-link/conflicting identities и любой --to отказаны; внутренний symlink может нормализоваться к тому же внутреннему target. Никакой физический move/copy, arbitrary rebase или immutable snapshot не обещается.

Источник: LA-048; аудит: C80-G02; проверки: TEST-MIG-02-02.

### REQ-MIG-02-03
Для конечного перечня реально поддержанных исторических RunManifest layouts проверить existing reader до/после normalization без изменения исходных bytes. Нельзя заменить Runtime1.0 похожим Core DTO, объявить journal/pickle recovery проверенным или повысить point-in-time same-path до scientific/release authority. Неподдержанный layout получает явную диагностическую границу, не basename fallback.

Источник: LA-048; аудит: C80-G03; проверки: TEST-MIG-02-03.

## 5. Техническое решение и producer → consumer

migrate_run_manifest_paths уже deepcopy и source-root preflight owner. Основная работа — native activation и explicit documented profile: сохранять current refusal semantics, не расширять режимы только из исторического пожелания. Registered CLI связывает actual operational binding, converter и _dump. Для нового реального relocation запроса отдельное ограниченное решение у этого же owner: source/destination mapping, authorized copy и bytes verification; до такого решения он out of scope, не скрытая capability.

### Проверенные owners на срезе
- policy-engine/src/polisyos/runtime/manifest_migrations.py: migrate_run_manifest_paths, _source_root, _canonical_reference
- policy-engine/src/polisyos/runtime/api.py: resolve_artifact_path and persisted writer
- policy-engine/src/polisyos/runtime/manifest: RunManifest, ArtifactRef
- policy-engine/tools/ops_runners/migrations/migrate.py: run_manifest branch, _dump

Новая копия path normalizer в CLI и basename fallback запрещены. Автоматическое копирование внешних files опаснее честного unsupported отказа и не нужно для исправленного контракта.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-MIG-02-01
- Уровень: native Runtime producer → registered CLI → fresh reader.
- Setup: Temporary own Runtime start/log/finalize run с audit/payload; absolute declared root, JSON/YAML inputs, output в другом каталоге.
- Действие: Normalize, parse actual RunManifest, resolve all artifacts and compare bytes SHA; repeat; mixed second entry missing; reuse MIG-01 output faults.
- Точный oracle: Каждый resolved path/bytes до=после; повтор idempotent, source unchanged, schema1.0/status preserved. Invalid second entry не публикует partial first; общий writer faults temp0/old output preserved по MIG-01 evidence.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-02-02
- Уровень: unit + targeted native integration.
- Setup: sub/data.json='original', root/data.json='unrelated'; два внешних same-basename files; relative root under fixed CWD; valid/broken/escape symlinks.
- Действие: Normalize supported cases, переместить только output file, сменить CWD для characterization, вызвать --to9.9.
- Точный oracle: Ни один substitute basename не выбран; same root сохраняет original. External/--to/escape/missing точный RunManifestPathMigrationError. Relative root CWD-dependence явно отражена, не portable relocation promise; converter не копирует files.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-02-03
- Уровень: unit + targeted native integration.
- Setup: Source-qualified old-run layout corpus с version/provenance и checksums; existing native readers.
- Действие: Read original and normalized copy при объявленном root; unsupported layout controls; inspect independent quality/journal consumers.
- Точный oracle: Поддержанные layouts читаются без DTO substitution/byte rewriting; corpus границы названы. Journal/pickle не PASS без собственного теста; converter outcome не утверждает immutable custody или content validity.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_mig_02.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: controlled filesystem fixtures только в собственном root; checksum counters. Запрещено: двухполевая fake ArtifactRef вместо native DTO final check, import bridge вместо полного Runtime activation, пользовательские runs.

## 7. Общая интеграция и порядок

Общий registered/installed suite MIG-01 выполняется один раз; этот пакет добавляет реальный Runtime consumer и collision matrix. Shared C79-R01 owner [MIG-01](MIG-01.md), не новый residual.

Точные общие сценарии: E02-I06-E из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: MIG-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Old RunManifest1.0 address сохраняется как package. Relative root spelling сознательно не меняется; новая абсолютная нормализация была бы отдельным behavior delta. Original plan multi-mode proposal superseded current honest path-only contract; отсутствие arbitrary relocation не product defect. Rollback только отдельного output, source manifests не трогать.

## 9. Free-grow и design direction

- Same addressed object и custody/authority различены; conversion не создаёт доказательства содержания.
- Небольшой Runtime-owned normalization обслуживает новые совместимые layouts через явный profile, не через case-by-case basename heuristics.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Зафиксировать supported historical layouts и CWD/root binding; при недоступном corpus G03 остаётся qualified limitation.
- Shared cleanup evidence требует принятого MIG-01 patch; native happy path MIG-02 не закрывает его сам.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

