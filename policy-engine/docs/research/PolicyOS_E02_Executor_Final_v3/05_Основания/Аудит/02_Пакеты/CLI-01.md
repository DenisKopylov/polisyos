# CLI-01 — package-owned генерация и публичный Runtime client

**C127 · LANE-12 · LA-043, LA-044 · срез `20d9009be21097bfbdc38a546a15cc60213b8ace`.**

## 1. Решение

Исходная миграция существенно выполнена: committed raw TS/JS удалены, public exports и обычные behavioral tests используют canonical client. Raw pair создаётся в private scratch и передаётся полезному canonicalizer. `openapi-typescript` принадлежит package, закреплён на 7.13.0; dashboard вызывает общий schema generator и сохраняет собственное форматирование. Checker принимает один `--openapi` и проверяет все три поддерживаемых output, различая drift, skip и UNRUN.

**Остались два воспроизведённых дефекта:** R01 — raw producer некорректно генерирует path/query access для не-identifier имён; R02 — зарегистрированный architecture check не согласован с текущими generator files/imports и принимает строки за imports. **7 MATCH; 18 начатых existing test cases: 17 PASS, 1 environment FAIL; ещё 2 test files BLOCKED до bodies.** Полная native regeneration/type/freshness квалификация не выполнена.

## 2. Матрица исходных оснований

| ID | Original repair | Фактическая способность | Остаток |
|---|---|---|---|
| LA-043 | Перевести raw retaining consumers, создать scratch handoff, сохранить public client и полный freshness family. | Raw pair отсутствует; canonical tests исполняются. Actual shell создаёт только3public outputs, private raw удаляется. Selected checker обнаруживает порчу/отсутствие каждого файла, extra output и UNRUN; custom input одинаков. | R01: входная граница producer. R02: architecture companion. G01/G02: native corpus/types/service/external compatibility. |
| LA-044 | Разрешать schema tool у package owner, сохранить pinned lock/provisioning и dashboard profile. | Package devDependency и lock importer7.13.0; native unchanged metadata test PASS. Dashboard больше не владеет schema dependency; общий helper вызывается из обоих shell. Registry runtime paths разделены по family. | G01: actual frozen environment/full generation. Перенос ownership не требует нового builder или нового UI. |

## 3. Producer → consumer

[Package shell](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/generate-runtime-api-client.sh#L44-L85): OpenAPI → package schema generator → private raw producer → canonicalizer → `types.ts` и canonical TS/JS. Cleanup trap не удаляет public family. [Dashboard shell](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/apps/runtime-dashboard/scripts/generate-api-client.sh#L44-L60) использует тот же schema source, но отдельный Prettier profile; byte identity двух profiles не предполагается.

[Canonicalizer](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs#L444-L669) проверяет полную ordered schema run, сохраняет established support aliases, связывает schema aliases с `types.ts`, отказывает при неоднозначности/collision. [Recursive normalizer](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs#L107-L206) выделяет guarded recursive components и отказывает при unguarded cycles. Они остаются полезными owners; source inspection не приравнен к выполненным TypeScript tests.

[Checker](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/ops_runners/runtime/check_runtime_api_contract.py#L95-L204) передаёт выбранный input в package generation, сравнивает exact output set и bytes; exception возвращает2/UNRUN, drift1, измеренное отсутствие drift0. Общий [family measurement](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/devx/architecture/guardrails.py#L8304-L8490) отдельно проверяет owners, фактически выпущенные files и escape. Его native provisioning здесь не запускался; существующий gate сохраняется, новый параллельный framework не нужен.

[Public client](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/canonicalRuntimeApiClient.js#L4-L69) передаёт supplied headers/body, кодирует query и различает JSON/arrayBuffer. Binary exposure test реально исполнен. Transport не устанавливает auth, currentness, verified ranking или допустимость policy decision.

## 4. Подтверждённые остатки

### C127-R01 — не-identifier wire names ломают raw generation

[TS access](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/ops_runners/runtime/generate_runtime_client.py#L483-L492) и [JS access](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tools/ops_runners/runtime/generate_runtime_client.py#L625-L634) вставляют wire name непосредственно после точки и в object key. Настоящий generator на custom GET с query `filter-mode` завершается0, но выдаёт JS, который Node отвергает с SyntaxError. Для path `{item-id}` JS синтаксически допустим, но выражение `params.item-id` приводит к ReferenceError до fetch. Контроли `filter_mode`, `item_id` и header `X-Trace-ID` проходят.

**Ограничение:** полный canonical pipeline недоступен; не заявлена генерация ошибочного committed client. Actual census нынешнего OpenAPI выделил 103 operations и не нашёл таких path/query names. Это bounded custom-input defect, не вывод о текущем production incidence и не доказательство, что дефект возник при миграции.

Минимальное направление: распространить уже существующий безопасный accessor на TS/JS path/query и корректно цитировать wire keys; проверить общий механизм, а не добавлять шаблон на каждый endpoint. Сохранить header/binary/body/error semantics и отказ при непредставимом входе.

### C127-R02 — package architecture check расходится с текущим owner

Команда `node scripts/check-architecture.mjs` из package, зарегистрированная как `check:architecture`, реально вернула1. [Allowlist/import checker](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/packages/runtime-api-client/scripts/check-architecture.mjs#L5-L137) отвергает два существующих `generate-openapi-types.*` файла. Две import-проверки тоже расходятся: добавились реальные `typescript`/`node:path`, а regex дополнительно извлекает import-like строки из generator templates и test fixtures (`${COMPONENTS_MODULE}`, `./remote.js`, `./types.js`, regex text).

Это ограниченный developer gate defect, не runtime transport defect и не доказанный hosted CI incident. Согласовать exact surface и реальную import семантику, сохранив meaningful отрицательные controls. Не выключать gate и не расширять его до allow-all.

## 5. Выполненные проверки

| Проверка | Результат и предел |
|---|---|
| P01 |15 native Node transport tests PASS; remediation retirement PASS, full generation FAIL missing openapi-typescript;1 unchanged Python package/lock body PASS. Node24.22.1, не supported22. |
| P02 |14 controls actual selected checker: clean, corruption/missing каждого из3outputs, extra, UNRUN, missing committed и4main routing/skip/exit cases. Generator subprocess настоящий, но пишет fixture bytes; OpenAPI rendering в main — recorder. |
| P03 | Exact Bash custom input/output-root/private scratch cleanup и3bad-argument refusals; dashboard shared input + formatter. Все tools — recorders, не фактическая генерация. |
| P04 | Actual standalone raw producer + Node parser/call на5fixtures: R01 и3контроля. Никакого HTTP request во внешнюю сеть. |
| P05 | Actual registered architecture gate exit1;4violations, R02. |
| P06 | Raw committed pair отсутствует; finite tracked text census и точный package inventory сохранены. General guardrails только прочитан по relevant complete functions. |
| P07 | Entire current JSON parsed actual owner:103 selected operations,0nonidentifier path/query names. Это metadata census, не 103 endpoint executions. |

[Native commands](../04_Проверки/C127_CLI01/native_commands.json) · [probe](../04_Проверки/C127_CLI01/probe_cli01.py) · [checker controls](../04_Проверки/C127_CLI01/run02/checker_results.json) · [shell](../04_Проверки/C127_CLI01/run02/shell_results.json) · [raw controls](../04_Проверки/C127_CLI01/run02/raw_results.json) · [actual subprocess outputs](../04_Проверки/C127_CLI01/run02/commands.json) · [operation census](../04_Проверки/C127_CLI01/selected_operations.json) · [общие команды](../04_Проверки/C127_CLI01/commands.json).

Run01 сохранён: external harness typo `else1`, до product execution. Run02 исправляет только whitespace. Два TypeScript-dependent test files блокируются до bodies; их tests не включены в число выполненных. Native full checker/pytest также не прошли environment admission.

## 6. Квалификация и сохраняемые обязанности

**C127-G01:** один согласованный CP6 native/frozen window для полной 3-output family, dashboard profile, compiler/normalizer/collision/idempotency и existing general freshness. Не обновлять версии по памяти, не считать fixture equality реальной freshness.

**C127-G02:** existing generated-client→Runtime service bridge, реальные resource/auth границы и конкретная external compatibility. 15 fetch-fixture tests доказывают транспорт, но не разрешение или исполнение институционального действия. POST allowlist — существующий selected-operation контракт, а не обещание универсального client для всех routes.

Сохранить canonicalizer, recursive normalizer, typed discriminated aliases, binary/exposure tests, currentness/limitation fields, точный UNRUN и protected Runtime Reference Shell/terminal styleguide. Эти UI/formatting роли не становятся авторами полномочий из-за migration cleanup.

[Исходная карточка](../05_Источники/CLI-01_исходные_строки.txt) · [pinned sources](../05_Источники/C127_источники.json) · [остатки](../01_Реестры/C127_остатки.json) · [границы](../04_Проверки/C127_CLI01/Чтение_и_границы.md).

**127/127 пакетов рассмотрены в текущем ограниченном формате; 282 уникальных B/LA охвачены. Это завершение последовательного охвата, не 127 реализованных пакетов и не полное закрытие E02. Итоговая независимая проверка досье и внешнее сохранение ожидаются. Фаза заданий исполнителю не начата.**
