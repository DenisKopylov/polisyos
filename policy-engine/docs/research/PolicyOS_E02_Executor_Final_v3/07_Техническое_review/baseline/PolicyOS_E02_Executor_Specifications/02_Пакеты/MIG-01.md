# MIG-01 — Один migration CLI: делегирование и явная Trinity validation

## 1. Паспорт и результат

**LANE-06 · CP2 · основание 20d9009be21097bfbdc38a546a15cc60213b8ace · статус: ТЗ, не выполнено.** Технический исполнитель и reviewer назначаются проектом. Исходные ID: LA-010, LA-049. Тип: atomic temp cleanup + validation/CLI qualification.

Исправить низкий остаток утечки temporary output в одном существующем writer и квалифицировать единый registered CLI с настоящим Trinity validator; не восстанавливать retired root duplicate.

Основания: [аудит](../05_Основания/Аудит/02_Пакеты/MIG-01.md), [все остатки](../05_Основания/Аудит/01_Реестры/C79_остатки.json), [неизменная исходная карточка](../05_Основания/Аудит/05_Источники/MIG-01_исходные_строки.txt), исходный объединённый план §MIG-01 (исторические строки 9129–9302).

## 2. Уже работает — сохранить

- Один tools.ops_runners.migrations.migrate runner; JSON/YAML, default/explicit target и actual operational binding.
- Current-version migrate_policy_ir вызывает настоящий TrinityBundle.model_validate и возвращает исходный mapping; self-edge отсутствует.
- Готовая model identity, split/model-dump/tuple/auto_migrate и actual error ABI различены; shape loader не exact-version authority.
- Atomic replace и scoped SecureOutputRoot сохраняются; old output/input не меняются при prepublication error.

## 3. Полнота обязательств и disposition

| Основание | Решение | Требования |
|---|---|---|
| C79-R01 | fix: Сохранить temp pathname сразу после успешного создания, до write/flush/fsync; cleanup всех failure paths у tools.lib.fs owner. | REQ-MIG-01-01 |
| C79-G01 | qualify: Реальный registered/installed CLI, preflight и active secure output, а не unchanged extracted main. | REQ-MIG-01-01, REQ-MIG-01-02 |
| C79-G02 | lifecycle: Current retirement и helper ABI сохраняются до explicit support decision; exact parser error types не нормализовать молча. | REQ-MIG-01-03 |
| C79-G03 | qualify: Native model validation только structural; future true transition требует versioned converter/corpus, не fake no-op report. | REQ-MIG-01-02, REQ-MIG-01-03 |

### Исходные обязанности, не только новые R

- LA-010/AM01: исходный root parser уже retired; историческое поручение сначала делегировать superseded текущим отсутствием duplicate. Не возвращать POLICY_IR_CURRENT_VERSION в Common.
- LA-049/LK26: validation находится на public current boundary; no-op не version conversion, tuple report None честен; не заставлять generic engine выполнять self-loops.
- LK27: operational binding/containment необходимы, но не release/admission evidence.

## 4. Нормативный контракт

### REQ-MIG-01-01
atomic_write_text фиксирует Path(handle.name) немедленно после входа в NamedTemporaryFile context, до рискованных write/flush/fsync. Любой exception после создания и до replace очищает только свой temp при сохранении исходного input и old output, передаёт исходную ошибку/явный cleanup failure без false success. Active SecureOutputRoot продолжает получать вызов; common text fix не обходит scoped owner. Парный atomic_write_bytes исследовать на тот же порядок и исправить в этом owner только при воспроизведённом таком же дефекте.

Источник: LA-010; аудит: C79-R01, C79-G01; проверки: TEST-MIG-01-01.

### REQ-MIG-01-02
Registered CLI→canonical main→IR same-version boundary вызывает настоящий nested Trinity validator, сохраняет mapping identity no-op и не пишет output при incomplete/invalid/current legacy markers/unsupported major/non-object input. Full JSON/YAML valid input проходит и публикуется атомарно. Missing operational contract отказывает до output. Generic self-edge не вводится; result означает validated unchanged, не converted/semantically admitted.

Источник: LA-010, LA-049; аудит: C79-G01, C79-G03; проверки: TEST-MIG-01-02.

### REQ-MIG-01-03
Поддержать current helper contract matrix: готовая model identity, migrate_policy_ir mapping identity, identity helper normalized dump/defaults, loader tuple(model,None), auto_migrate error text и actual JSONDecodeError/YAML ParserError/PolicyLoadError distinctions. Старый root path не восстанавливать; внешние command consumers и helper lifecycle квалифицировать с finite census/support window. Никакой historical output не становится validated задним числом.

Источник: LA-010, LA-049; аудит: C79-G02, C79-G03; проверки: TEST-MIG-01-03.

## 5. Техническое решение и producer → consumer

Точечная правка tools.lib.fs.atomic_write_text: переместить присваивание tmp_path перед handle.write. Cleanup сохраняет operation-owned path и atomic replace; не вводить новый writer в CLI. Secure output branch тестировать у настоящего owner, не предполагать что общий finally его покрывает. migrate_policy_ir current guard уже правильный — не рефакторить его ради задачи; native registered command test связывает actual validation, operational binding и output. Shared C79-R01 устраняется один раз и потребляется MIG-02/MIG-04.

### Проверенные owners на срезе
- policy-engine/tools/lib/fs.py: atomic_write_text, atomic_write_bytes, active_secure_output_root
- policy-engine/tools/ops_runners/migrations/migrate.py: main, _load, _dump
- policy-engine/src/polisyos/ir/migrations/__init__.py: migrate_policy_ir
- policy-engine/src/polisyos/ir/migrations/policy_ir.py: migrate_policy_ir_identity
- policy-engine/src/polisyos/ir/loading/loaders.py: load_trinity_bundle, load_policy
- policy-engine/ops/migrations/migration-contracts.toml

Не возвращать root migrate.py только чтобы исполнить историческую фазу плана; current replacement — единственный registered canonical runner. Не ставить broad try вокруг validation и не подменять все ошибки одним классом.

## 6. Локальная приёмка — все будущие проверки NOT_RUN

### TEST-MIG-01-01
- Уровень: unit + targeted native integration.
- Setup: Собственные input/old output; actual atomic_write_text, parameterized write/flush/fsync/replace faults; отдельный active SecureOutputRoot.
- Действие: Fault до каждого publication boundary, compare paths/bytes; success JSON/YAML; bytes sibling characterization при необходимости.
- Точный oracle: До replace old output/input byte-identical, собственных temp0 после controllable failures; original exception виден, no success. При запрете удаления temp честный cleanup diagnostic, не ложный guarantee. SecureOutputRoot не bypass, outside root denied. Successful replace new bytes exactly expected.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-01-02
- Уровень: registered native command + installed entry.
- Setup: Full Trinity fixture с real validators, JSON/YAML variants, incomplete schema_version-only, invalid nested, legacy2.*, semantic marker, major request; actual contracts tree.
- Действие: Вызвать найденный registered entry и canonical main, default/explicit current; удалить required contract directory в test-owned copy.
- Точный oracle: Valid output native loader принимает, UTF8/newline/format ожидаемы; validator вызван на no-op. Invalid/binding failure nonzero/no output replacement. Root duplicate absent; unchanged vs converted report не выдуман.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

### TEST-MIG-01-03
- Уровень: unit + targeted native integration.
- Setup: Existing test_trinity_migration helper corpus + supported caller/FQN/docs census.
- Действие: Mapping/model/JSON/YAML/UTF8 invalid input через каждый public helper; inspect identity/tuple/errors/defaults; fresh shape-valid2.0 loader отдельно от migration refusal.
- Точный oracle: Exact distinct return/exception contracts сохранены; shape-valid не назван migration admission. Census фиксирует неизвестные external callers, adapters не удалены без окна. Исторические данные неизменны.
- Ожидаемый класс: positive + negative + boundary.
- Свидетельство: NOT_RUN; предъявить actual command, runtime/backend/import binding, exit/log, exact observed values; отдельный контроль на прежнем дефекте или отключённом механизме.

Повторно использовать/расширить реальные места, а не создавать 127 harness: `policy-engine/tests/unit/remediation/test_mig_01.py`; `policy-engine/tests/contract/test_trinity_migration.py`. До выбора selector прочитать полный test/fixture. Это проверенные пути, не утверждение о наличии всех предложенных assertions.

Допустимые doubles: faulting write/fsync/replace и test-owned contracts tree; actual model, writer и native scope не подменены. Запрещено: минимальная Trinity модель, tools.lib initializer shell в final CLI acceptance, пользовательские manifests.

## 7. Общая интеграция и порядок

Один common CLI suite охватывает policy_ir/run_manifest/dataset_manifest и scoped output; MIG-02/04 ссылаются на REQ-MIG-01-01 вместо второго writer fix. MIG-05 registry profile tests предшествуют изменениям shared engine, если они понадобятся.

Точные общие сценарии: E02-I06-E из [контракта интеграции](../03_Интеграция/LANE-06.md); одно свидетельство переиспользуется по неизменным input/backend bindings. Зависимости: нет обязательного нового предшественника; исходный DAG — ориентир, работающий контракт может удовлетворять ребру без нового ремонта. Общие файлы из §5 интегрировать последовательно с затронутыми owners; lane не новый runtime-реестр и не требование полного CI после каждого пакета.

## 8. Совместимость, история, rollback

Root retirement уже текущий факт, не новый delete. Текстовой helper fix не меняет successful bytes/newline. No-op validation не выдаёт migration report. Rollback patch не удаляет прошлые outputs; temp cleanup только operation-owned. Power-loss durability не доказана этим OSError injection.

## 9. Free-grow и design direction

- Validation, conversion и authority разные boundaries; повторное использование current owner дешевле параллельного runner.
- Механика atomic publication общая, форматные правила остаются в IR/Runtime/Fabric.

Архитектурные источники: [policyos-identity-and-custody-boundary.md §1, §3–6](../05_Основания/Архитектура/policyos-identity-and-custody-boundary.md); [policy-design-custody-time-model.md §2–5](../05_Основания/Архитектура/policy-design-custody-time-model.md). Историческая подлинность и текущая пригодность раздельны; физический layout design-docs не догма.

Полные исторические probes/commands/logs остаются в отдельно доставленном phase1 ZIP; ссылки внутри копий аудита на `04_Проверки` относятся к нему, не к новым исполненным проверкам этого комплекта.

## 10. Нерешённые решения и передача

- Если cleanup сам запрещён OS, выбрать приоритет diagnostic/exception chaining без сокрытия исходного отказа; document residual path.
- Retirement error/tuple/auto_migrate только отдельным compatibility решением; в этом пакете default — сохранить.

Предъявить patch/base SHA (либо обоснованный no-code результат), актуальную карту callers, REQ→TEST→evidence, фактические команды/логи, различающий контроль и сохранённые инварианты. Поддержанный native профиль: P-CORE (Python >=3.14,<3.15 и project lock); для процессов P-PROCESS, для поставки P-PACKAGING. Не устанавливать зависимости без отдельного разрешения. Fixture/source-only, исторические PASS и отсутствие ошибки при импорте не закрывают свежий producer→persistence→fresh-reader. Успешная сериализация/конверсия/подпись не доказывает научной истины или полномочия policy result. Никакое требование/тест этой карточки ещё не исполнены.

