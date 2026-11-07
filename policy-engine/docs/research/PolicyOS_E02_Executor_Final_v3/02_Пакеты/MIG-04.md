# MIG-04 — DatasetManifest: converter у schema owner, явная registration

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-050. Тип: format-only migration + compatibility/native qualification.

Сохранить Fabric-owned rename и neutral engine, квалифицировать historical mapping/target disposition без fabricated provenance; общий CLI/writer проверяется один раз с MIG-01/02.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/MIG-04.md), [все остатки](../05_Основания/Аудит/01_Реестры/C81_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/MIG-04_исходные_строки.txt), исходный объединённый план §MIG-04 (исторические строки 9429–9543).

## 2. Уже работает — сохранить

- Fabric canonical converter и explicit registration у ops/composition; generic Common не импортирует Fabric.
- Bounded deprecated Common adapter сохраняет explicit-import registration side effect и version export до support window.
- Callback меняет свой input/не stamp-ит, public engine deep-copies/stamp-ит; caller isolation сохраняется.
- Equal/conflicting aliases, unknown/missing fields наблюдаемы; conversion-only не target admission, absent raw_hash/created_at не выдумываются.

Изменение продукта требуется только при воспроизведённом несоответствии ниже; отсутствие native проверки само по себе не дефект. Не создавать искусственный рефакторинг для отчёта.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C81-G01 | qualify: Source-qualified historical profiles и explicit conversion-only/target-admission matrix; использовать existing DTO/registry, не parallel validator. | REQ-MIG-04-02 |
| C81-G02 | lifecycle: Adapter поддерживает внешние callers/import order до actual retirement window; нейтральность Common сохранить. | REQ-MIG-04-03 |
| C81-G03 | qualify: Native registered CLI/secure writer общий с MIG-01, затем actual registry consumer; rename не source authority. | REQ-MIG-04-01, REQ-MIG-04-02 |

### Исходные обязанности, не только новые R

- LA-050/LK28: полезный rename не placeholder; owner move уже выполнен. Не удалять generic API/readers и не переносить формат в DataForge StageManifest по похожему имени.
- Historical format mapping и optional target validation — отдельное решение. Current format-only контракт честен: version1.0 не обещает пригодную DTO.
- Raw content/source/license/completeness/reconciliation/reuse проверяются existing evidence owners, не converter.

## 4. Нормативный контракт

### REQ-MIG-04-01
Native registered/installed dataset_manifest CLI явно register_manifest_migration у Fabric, использует neutral Common engine и atomic _dump. Default и explicit1.0 сохраняют одинаковый результат; unsupported target сохраняет input/old output. Engine deep-copy защищает nested caller data, raw callback mutates/returns same object и не stamp-ит; no-op public engine также isolated. Shared C79-R01 закрывается только MIG-01 REQ-MIG-01-01.

Источник: LA-050; аудит: C81-G03; проверки: TEST-MIG-04-01.

### REQ-MIG-04-02
Составить явную finite historical mapping matrix: legacy-only/current/equal aliases/conflicts/unknown/missing fields. Для принятого format-only profile rename не выбирает молча противоречащее значение и не создаёт raw_hash/created_at. Persisted converted output отдельно проходит существующий DatasetManifest/ManifestRegistry admission; если shape отказан, conversion может оставаться успешной, но пригодность обозначается false/not assessed. Optional validation mode, если необходим реальному consumer, вызывает этот owner и не меняет default без согласованного delta.

Источник: LA-050; аудит: C81-G01, C81-G03; проверки: TEST-MIG-04-02.

### REQ-MIG-04-03
Generic Common import не регистрирует предметный converter автоматически и не грузит Fabric. Явный legacy adapter import сохраняет прежнюю registration/version ABI без обратного Common→Fabric dependency; bounded equivalence old/new callback table и import order проверяются. Retirement только после supported external caller census и принятого окна, не по факту source move.

Источник: LA-050; аудит: C81-G02; проверки: TEST-MIG-04-03.

## 5. Техническое решение и producer → consumer

Fabric.identity.migrations уже canonical owner; не повторять перемещение и не импортировать Fabric из Common ради устранения небольшой intentional compatibility copy. Основное deliverable — executable contract matrix и native persisted consumer witness. Existing ManifestRegistry вызывает DatasetManifest validation до регистрации и отдельный require проверяет reconciliation, поэтому optional target admission при потребности делегируется туда. В CLI _dump оставить общим; dataset branch только подтверждает consumption MIG-01 atomic fix.

### Проверенные owners на срезе
- policy-engine/src/polisyos/fabric/identity/migrations.py: migrate_manifest_0_9_to_1_0, register_manifest_migration
- policy-engine/src/polisyos/fabric/identity/manifest.py: DatasetManifest
- policy-engine/src/polisyos/fabric/_internal/registry.py: ManifestRegistry
- policy-engine/src/polisyos/common/migrations/manifest.py: deprecated adapter
- policy-engine/src/polisyos/common/migrations/base.py: public migrate_artifact
- policy-engine/tools/ops_runners/migrations/migrate.py: dataset_manifest branch

Удаление adapter по слову deprecated без downstream census нарушает ABI. Parallel DTO validator или manufacture defaults ради green parse создаёт ложную provenance; current format-only результат достаточен, если consumer не требует admission.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-MIG-04-01
- Уровень: native registered CLI + shared output scope.
- Setup: JSON/YAML complete legacy fixture с provided created_at/raw_hash, nested caller dict; registered canonical tool и actual Common/Fabric.
- Действие: Default1.0/explicit1.0/unsupported2.0; raw callback/public engine/no-op identity; reuse common writer faults MIG-01.
- Точный oracle: Default/explicit outputs equal, input deep-unchanged; raw callback same object version0.9, public result version1.0; unknown target no replacement. Native CLI preflight/scope не bypass; shared temp cleanup evidence приложено один раз.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-04-02
- Уровень: unit + targeted native integration.
- Setup: Source-qualified historical corpus и synthetic boundary matrix; own persisted *_manifest.json output, actual ManifestRegistry.
- Действие: Convert then registry load/require; equal/conflicting aliases, unknown, missing raw_hash/created_at; complete positive.
- Точный oracle: Complete supported payload принят реальной DTO с provided fields; equal/conflicting/unknown/missing outcomes не скрыты. Invalid output не зарегистрирован как valid DTO; raw_hash/created_at не изготовлены converter. DTO clock default не объявлен source provenance; reconciliation require отдельно.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-04-03
- Уровень: unit + targeted native integration.
- Setup: Fresh child processes: generic Common, explicit legacy adapter, explicit Fabric registration; bounded alias corpus.
- Действие: Inspect modules/registry before/after imports, compare callback outputs/errors and registration order; supported FQN consumers.
- Точный oracle: Generic Common не Fabric/no implicit dataset registration; legacy import retains side effect без Fabric; explicit canonical registration работает. Old/new bounded semantics совпадают, unresolved external use не равно0; adapter не удалён без window.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_mig_04.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: synthetic alias/error fixtures и controlled output failures; historical label только для actual source-qualified sample. Запрещено: fake Fabric DTO/clock для native consumer, rename version1.0 как доказательство raw data/license integrity.

## 7. Общая интеграция и порядок

MIG-01/02/04 один registered CLI и scoped writer integration. Этот пакет добавляет Fabric registry fresh-reader branch; общий engine profile reuse MIG-05 не смешивает IR/Common политики. [MIG-01](MIG-01.md) owns C79-R01.

Точные общие сценарии: E02-I06-E из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: MIG-01; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Relocation equivalence уже достигнута; conflict/default/target-admission изменения только отдельным intended delta. Historical profiles не переименовывать в нынешнюю DTO без mapping. Adapter можно сохранять без product patch; source files не мигрировать автоматически.

## 9. Free-grow и design direction

- Format conversion, structural admission и evidence/reuse eligibility раздельны; optional candidate output остаётся полезен без ложного authority.
- Schema-adjacent converter + нейтральный engine допускают новые profiles без тяжёлого Common coupling.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Получить supported historical profiles; если нет, bounded matrix не заявлять полным historical PASS.
- Решить, требуется ли optional target validation реальному consumer; по умолчанию сохранить честный format-only контракт, без forced stricter default.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

