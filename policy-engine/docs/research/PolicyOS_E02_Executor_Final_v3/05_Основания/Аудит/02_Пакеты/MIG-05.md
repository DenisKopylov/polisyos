# MIG-05 — общий linear executor и разные migration profiles

## 1. Решение

**Ограниченно оценён, не закрыт.** Общая линейная механика уже консолидирована в Common, а observable Common/IR profiles сохранены. DataForge graph registry остаётся самостоятельным механизмом. Найден **C82-R01: IR fingerprint подавляет отказ от неподдержанного captured object, из-за чего конфликтующие callback registrations ошибочно считаются одинаковыми**.

Свежий результат: **5 bounded MATCH;30 unchanged bodies /30 cases PASS**. MATCH в P05 означает воспроизведение дефекта, не product PASS. Настоящие Common/IR/DataForge modules импортируются native без product shells. Отдельный native subprocess без pytest повторил R01.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/MIG-05_исходные_строки.txt) · [Pinned sources](../05_Источники/C82_источники.json).

## 2. Требования и наблюдаемые profiles

| ID / свойство | Фактический результат | Остаток |
|---|---|---|
| LA-047: один traversal owner | Common и IR действительно вызывают shared engine; export objects совпадают; order/missing-later-edge проверены | Полный historical/installed callback corpus G01 |
| Common copy/no-op/stamp/errors | Deepcopy до/вокруг шага, новая глубокая no-op копия, registered stamp, str version, TypeError для bad result | Сохранять, не подменять IR semantics |
| IR copy/no-op/stamp/errors | Live nested mutation, в том числе до исключения; no-op identity; str coercion; incompatible returned version и bad result — public typed errors | Не объявлять synthetic mutation доказательством порчи actual datasets |
| Duplicate / cycle | Common overwrite и runtime cycle guard; IR identical-repeat acceptance, conflicting/cycle registration refusal | Намеренное отличие от старой карточки; R01 нарушает именно текущую strict identity boundary |
| IR compatibility | Отдельные rules/negotiation/major guard сохранены; migration-required отличается от direct-read | Selected checks не аттестуют весь registry/admission, G02 |
| LK25 | DataForge branching shortest path, deterministic tie, instance state,3-component versions, shallow copy, no auto-stamp | Не удалять или заменять linear runner |

Исходная карточка описывала overwrite в обоих engines. Current IR намеренно строже, что отражено в настоящем regression. Возвращать permissive replacement или self-cycle ради буквального совпадения с историей было бы регрессией, не завершением MIG-05.

## 3. Producer → registry → executor → consumer

`LinearMigrationProfile` передаёт prepare/no-op/edge-target/apply-step; shared loop ведёт visited versions, различает missing edge/cycle и выполняет зарегистрированную цепочку (`S01`). Common owner задаёт deepcopy и stamp, IR owner задаёт live payload/typed version check, собственный edge registry и negotiation (`S02`, `S03`). Реальный wrapping spy подтверждает, что IR дошёл до того же shared executor, не до копии функции (`S16`).

Полезный manifest converter работает через Common; его actual callback/input isolation проверены. Current IR identity helper вызывает настоящую Trinity validation и не требует self-edge; current public policy facade separately validates same-version payload (`S05`–`S07`, source-qualified C79). Fresh import baseline содержит schema declarations, но не IR migration edges: это узкий факт данного import composition, не вывод обо всех устанавливаемых extensions.

DataForge registry строит BFS graph route с сортировкой outgoing versions, а не one-edge-per-version chain. Его shallow-copy/no-stamp contract реален и не совпадает с Common. Результат local conversion ещё не является persisted authoritative policy artifact: реальные migration CLI/persisted consumer boundaries рассмотрены отдельно C79–C81; здесь проверяются shared mechanism и его owners, не повторно весь release pipeline.

## 4. Свежие проверки

1. **P01:**19 MIG-05 +2 Common base +2 shared engine +2 purity bodies,25/25 PASS. Два шага, missing edge после actual первого шага, cycle, duplicate, bad result, conflicting stamp, mutation+failure, source type, no-op identity, actual manifest callback и Trinity helper. Runtime type hints разрешаются на Python3.12.
2. **P02:**4 selected unchanged IR compatibility bodies и1 complete DataForge migration body,5/5 PASS. Полные остальные suites не исполнялись. Старые canonical fixture bytes не стали эмпирической authority.
3. **P03:** два равных DataForge пути выбирают `low → vialow` при прямом и обратном registration order. Exact duplicate, missing route и двухкомпонентная plan version отвергаются; instance isolation, shallow nested identity и отсутствие stamp сохранены.
4. **P04:** existing explicit NONE schema policy не перезаписывается edge registration; available route даёт `migration_required=True`, а не притворный direct-read. Identical callback repeat принимается, cycle отказывает до execution, policy facade отвергает3-component version.
5. **P05:** unsupported captured object напрямую вызывает MigrationCompatibilityError, но тот же объект внутри closure ошибочно кодируется как empty cell. Две closures с разными значениями имеют одинаковый fingerprint; вторая регистрация принимается и возвращает second callable, однако actual runner возвращает значение first. Scalar-capture control правильно отвергает конфликт. Fresh native отдельный процесс подтвердил тот же результат без test helpers.

## 5. Подтверждённый остаток

### C82-R01 — false idempotence при неподдержанном captured object

**Средняя серьёзность, высокая уверенность в bounded воспроизведении.** `MigrationCompatibilityError` наследует ValueError (`S03:24–33`). В fingerprint `try` охватывает не только `cell.cell_contents`, но и `_stable_migration_value(...)`; `except ValueError` превращает ошибку unsupported identity в `{"type":"empty_cell"}` (`S03:575–583`). Поэтому разные конфигурации, которые должны были явно отказать, получают одинаковое описание. Duplicate-registration guard сравнивает этот fingerprint и сохраняет первоначальное edge, молча принимая вторую регистрацию (`S03:611–626`).

Наблюдаемый эффект: вызывающий получает успешную регистрацию callback `second`, но migration исполняет `first`. Это **не криптографическая коллизия SHA256**, а потеря различающего входа до hashing. Не установлено, что реальные product callbacks используют такие captures или уже изменили пользовательские snapshots.

Минимальное направление: сузить existing empty-cell handler до чтения cell; ошибки stable encoder должны оставаться refusal. Сохранить текущие strict IR conflict/cycle semantics и добавить отличающие empty/unsupported/supported/idempotent/conflicting cases. Новый migration framework не нужен.

## 6. Что сохранить и что не закрыто

**Сохранить:** shared traversal, отдельные copy/stamp/error/no-op profiles, actual callbacks/helper, public exception identities, нейтральность Common, IR schema rules/negotiation, stricter IR registration и DataForge graph semantics.

**C82-G01:** historical inputs, реальные supported registrations/import order и installed external plugins. Synthetic nested mutation — характеристика явно сохранённого IR API, не автоматический product defect. Усиление isolation требует отдельного behavioural решения, не скрытого refactor.

**C82-G02:** native pytest, supported Python3.14/Pydantic, installed/release и связанный LANE-06/CP2 corpus. Четыре compatibility tests не доказывают все declared DTO readers. Version conversion, одинаковые bytes и shape validation не заменяют source/provenance/semantic validity и authority. Использовать действующих owners, не добавлять бумажный параллельный контур.

## 7. Воспроизводимость и пределы

[Commands/exit/logs](../04_Проверки/C82_MIG05/commands.json) · [Cases/observations](../04_Проверки/C82_MIG05/bounded_diagnostics.json) · [Native qualification](../04_Проверки/C82_MIG05/native_verification.json) · [Остатки](../01_Реестры/C82_остатки.json).

Final run02 exit0,30/30 cases. Run01:29 PASS и1 external harness NameError; добавлены только недостающие pytest/error-class bindings, результаты сохранены. Product modules native;5 existing bodies selected целиком через AST, остальные4 test modules исполнены полностью с внешним pytest helper. Native pytest не установлен. R01 standalone native control exit0. Supported runtime/installed/release UNRUN, зависимости не устанавливались.

Checkout чист; source/tests/config не менялись. Это аудит bounded contracts и synthetic diagnostic callbacks, не миграция production данных и не доказательство научной истинности policy outputs.

**82/127 рассмотрены ограниченно. Следующий — UDF-01. Фаза 2 не начата.**
