# UDF-04 — Typed unavailable без ослабления server admission

**LANE-07 · CP2 · LA-029 · fix + native/deployment qualification.**

**Практическая цель:** Installed console честно сообщает отсутствие repository workload, а допустимый server route сохраняет явные roots и доказуемый C7 lifecycle.

Статус: исполнительское ТЗ; продукт не изменён. Все TEST — **NOT_RUN**.

## 1. Основание и пределы
[Аудит](../05_Основания/Аудит/02_Пакеты/UDF-04.md) · [остатки C87](../05_Основания/Аудит/01_Реестры/C87_остатки.json) · [полная исходная карточка](../05_Основания/Аудит/05_Источники/UDF-04_исходные_строки.txt). Commit `20d9009be21097bfbdc38a546a15cc60213b8ace`. Full probes находятся в отдельно доставленном phase1 ZIP. R01 — low diagnostic ordering, не execution-policy bypass. Native installed wheel и C7 в audit не исполнены.

## 2. Сохранить работающий смысл
- Explicit workspace/root separation
- Ops callbacks и domain orchestration
- Server-only guard
- Structured source-bound complete lifecycle receipts
- Skip/failure reasons и private scratch

Защищённые различения: исходные positive/negative boundaries выше. Не считать qualification-only поручением искусственно переписать исправленный продукт. Изменение кода в такой части требуется только при воспроизведённом несоответствии.

## 3. Полная disposition

- **C87-R01: fix** → REQ-UDF-04-01. Неисполняющая availability диагностика предшествует server action admission; actual action guard сохраняется.
- **C87-G01: qualify** → REQ-UDF-04-02, REQ-UDF-04-03. Installed/native child receipt lifecycle в разрешённой среде.
- **C87-G02: qualify** → REQ-UDF-04-04. Deployment отдельно; render/capabilities не право и не исполнение.

Original remaining и preservation inventory IDs полностью сопоставлены в companion JSON. Shared/historical obligations не исчезают из-за отсутствия нового R.

## 4. Атомарные требования и различающие проверки

### REQ-UDF-04-01
Actual public validate-part-a route при отсутствующем usable checkout должен возвращать документированный typed unavailable без repository subprocess/provisioning, включая default server-required config без marker. Для существующего checkout server guard остаётся обязательным до любого исполнения.

**TEST-UDF-04-01 — native unit / integration; NOT_RUN.**
- Setup: Default config; installed-layout root/no marker, admitted server/no checkout, valid checkout/blocked server.
- Действие: Console→Ops factory→domain orchestrator.validate_part_a; recording subprocess.
- Точный oracle: Первые два case дают unavailable receipt/exit1 и 0 subprocess; valid checkout+blocked server даёт policy denial и 0 subprocess. Old public route ошибочно бросает block раньше unavailable.
- Doubles/границы: Только собственный tempfile installed-layout fixture; marker не institutional permission, no real C7/provisioning.

### REQ-UDF-04-02
Workspace root должен идти из CLI/composition отдельно от artifact build root; repo_root compatibility alias сохраняется с конфликтным отказом. Ops владеет callbacks/commands, domain не импортирует tools и не вычисляет checkout по parents[N].

**TEST-UDF-04-02 — native unit / integration; NOT_RUN.**
- Setup: Два разных roots, path с пробелами, cwd fallback, conflicting aliases.
- Действие: Actual console target и factory, render bootstrap, inspect command/cwd/env and domains imports.
- Точный oracle: Explicit workspace используется для repository action, outputs в build root; conflict отказ; quoting корректен; renderer не исполняет apt/uv.
- Doubles/границы: Recording subprocess разрешён; не подменять CLI/factory/orchestrator.

### REQ-UDF-04-03
Native installed console/package должен включать actual Ops/receipt plugin и выдавать source-bound C7 lifecycle receipt только для complete same-child collection/setup/call/teardown. Stdout passed/exit0 не достаточны; skip/fail и narrowed collection остаются различимыми.

**TEST-UDF-04-03 — native unit / integration; NOT_RUN.**
- Setup: Supported заранее подготовленное installed environment и разрешённый server checkout; реальные pytest/pluggy hooks, synthetic local test cases pass/skip/fail.
- Действие: Installed console route и child C7 qualification на разрешённом target; tamper own receipt attempt/hash/phase controls.
- Точный oracle: Valid complete receipt accepted; missing teardown/wrong attempt/narrowed collection/source hash mismatch rejected. Command/cwd/env/source/config hashes совпадают; private attempt вне checkout.
- Doubles/границы: Native server execution только с отдельным разрешением/подходящим profile; local parser fixture не C7 PASS.

### REQ-UDF-04-04
Deployment qualification должна сохранять distinction rendered plan/capabilities/environment admission/institutional authority. Без фактического target execution результат ограничивается render/readonly capability checks, а не утверждением provisioning.

**TEST-UDF-04-04 — native unit / integration; NOT_RUN.**
- Setup: Actual requested deployment profile или только доступная локальная readonly среда; existing server policy.
- Действие: Проверить target prerequisites и rendered commands; исполнение лишь в отдельно разрешённой deployment операции.
- Точный oracle: Точный scope RUN/BLOCKED/NOT_AUTHORIZED; Mac/marker0 не запускают server action; quoted plan и capability facts полезны без выдуманного deployment PASS.
- Doubles/границы: Не apt/uv/install/remote mutation в текущей подготовке ТЗ.

### REQ-UDF-04-05
Domain stages должны потреблять shared lazy facade fix UDF-01 без снятия server guards и без новой import implementation.

**TEST-UDF-04-05 — native unit / integration; NOT_RUN.**
- Setup: Common native E02-I07-A import/CLI fixture.
- Действие: Проверить installed/domain import и deferred stage activation.
- Точный oracle: Unrelated activation устранена shared owner, valid explicit route доступен; server policy unchanged.
- Doubles/границы: Не считать native lazy root import всей pipeline.

## 5. Конкретное решение / producer→consumer
Все пути ниже от `policy-engine/`; не выполнять повторный move по историческому имени.

`src/polisyos/data_forge/domains/ukraine/orchestrator.py::validate_part_a` сейчас вызывает assert_server_execution_allowed до `src/polisyos/data_forge/domains/ukraine/server.py::run_part_a_gate`, хотя latter сначала проверяет is_repository_checkout и отдаёт typed unavailable. Предпочтительное исправление — shared nonexecuting availability preflight: для no-checkout вернуть существующий unavailable через тот же manifest/report owner; для usable checkout затем выполнить server guard, подготовку layout/tracker и Ops callback. Не делать доступность способом вызвать runner без guard. В preflight не запускать subprocess и не разыскивать соседние repository по magic depth.

`tools.ops_runners.ukraine_data_cli:main` — actual pyproject console target; `tools/ops_runners/ukraine_data/` владеет server_bootstrap/validate_part_a и source-bound receipt integration. Domain остаётся callback/result adapter. Existing stronger receipt contract сохраняется: не возвращаться к stdout parser ради literal relocation equivalence.

Если принято противоположное намеренное правило «policy denial всегда скрывает availability», требуется явное конечное owner решение и синхронный контракт/README/test delta вместо заявления, что R01 исчез. По умолчанию здесь выбрана documented typed-unavailable semantics; альтернативу не использовать как бессодержательное исследование. Native installed/package/C7 квалификация не выполняется автоматически на авторской машине.

## 6. Общая интеграция и порядок
**E02-I07-A**, [канонический LANE-07](../03_Интеграция/LANE-07.md). Один общий evidence set, не одинаковая тяжёлая suite на каждый пакет.

- UDF-01 shared import owner; no required original predecessor
- Ops sole writer receipt plugin/commands; server qualification отдельным разрешённым job

Owners/callers: `src/polisyos/data_forge/domains/ukraine/orchestrator.py::validate_part_a`; `src/polisyos/data_forge/domains/ukraine/server.py::run_part_a_gate`; `src/polisyos/data_forge/domains/ukraine/cli.py`; `tools/ops_runners/ukraine_data_cli.py`; `tools/ops_runners/ukraine_data/validate_part_a.py`. Shared files — один writer с последовательными commits и review потребителей; CP не отдельный runtime registry.

## 7. Совместимость / история / rollback
Repo_root alias и serialized receipt schema/history сохранены; no-checkout diagnostics intentional ordering delta. Нельзя изменить server-only policy в том же «equivalent move». Rollback не разрешает локальный C7; affected installed diagnosis может оставаться explicitly limited до исправления.

## 8. Free-grow и разумные отступления
[Vision §3, §6–§7, §11](../05_Основания/Архитектура/universal-policy-design-system-vision-and-organizing-rules.md) — существующий owner, реально подключённый consumer, совместимые новые ресурсы через общий контракт; не бесконечный реестр вместо работы. [Target Architecture D2.5](../05_Основания/Архитектура/universal-policy-design-target-architecture-and-gap.md) — candidate/conditional вычисление не равно эмпирической или институциональной authority.

[Execution topology](../05_Основания/Архитектура/policy-design-execution-topology.md) поддерживает раздельные deployment и domain roles. Не превращать marker в authority, но полезный rendered plan/unavailable diagnostic не блокировать требованием несуществующей институциональной подписи.

## 9. Приёмка и запреты PASS
Показать base/patch/write map, requirements/test matrix, failing-before/fixed-after либо controlled-removal witness, actual commands/runtime/exit/logs, selected hashes/refs и declared doubles. Реальные test owners: `tests/unit/remediation/test_udf_04.py`, `tests/unit/data_forge/domains/ukraine/test_server.py`, `tests/unit/data_forge/domains/ukraine/test_cli.py`. Адаптируемый шаблон `<supported-python> -m pytest <verified paths>` из `policy-engine/`; будущие TEST IDs не названы существующими pytest functions.

Нельзя выдавать source inspection/fixture/AST/import-only за native цепочку; marker/hash/exit0 — за current admission или scientific truth; отказ всех inputs — за положительную способность; написанное ТЗ — за выполненную реализацию. Сохранять полезные независимые результаты и явные ограничения неподтверждённых claims. Install/deployment/external mutation не разрешаются документом автоматически.
