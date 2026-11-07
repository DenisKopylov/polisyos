# UDF-04 — explicit workspace root и Ops-owned server gate

## 1. Решение

**Ограниченно оценён, не закрыт.** Исходная ошибка `parents[3]` в domain orchestrator устранена: default workspace unset, explicit workspace/legacy repo_root передаются через composition, artifact root отделён от checkout. Provisioning renderer, capabilities и C7 subprocess принадлежат Ops; domain не импортирует tools.

Свежий результат: **5 bounded MATCH;17 unchanged bodies /19 cases PASS**. Найден **C87-R01, low**: installed-layout console route вне admitted server context раньше typed unavailable выбрасывает server-block exception. Это diagnostic/compatibility расхождение, не обход защиты и не ложный C7 PASS.

Actual whole CLI/Ops/server/orchestrator исполнены за явными import seams. Subprocess только recording, native C7/provisioning/installed-wheel qualification **UNRUN**.

Срез `20d9009be21097bfbdc38a546a15cc60213b8ace`. [Исходная карточка](../05_Источники/UDF-04_исходные_строки.txt) · [Pinned sources](../05_Источники/C87_источники.json).

## 2. Матрица исходного ID

| ID | Проверенный результат | Остаток |
|---|---|---|
| LA-029 | Explicit workspace/root distinction; Ops callbacks; actual console mapping; server policy; structured receipt/skip/failure semantics | C87-R01 unavailable ordering; G01 installed/native C7; G02 deployment qualification |

Useful domain orchestrator не удалён. `repo_root` остаётся compatibility alias с отказом при конфликте двух roots. Ops default — process cwd, не module depth. `parents[3]` внутри Ops receipt code определяет собственный code root для plugin identity, не подменяет явно выбранный workspace root.

## 3. Owner → command → receipt

Actual console target в pyproject — `tools.ops_runners.ukraine_data_cli:main`. Он передаёт Ops factory в domain CLI. CLI загружает config/build root и отдельно передаёт `--workspace-root`; factory разрешает explicit path либо cwd и создаёт domain orchestrator с gate/renderer/capability callbacks (`S02`–`S06`, `S15`).

Domain server adapter проверяет structural checkout и возвращает typed unavailable, если его нет. При доступном checkout сохраняет server-only guard и требует Ops runner. Guard проверяет Python, Linux/host и marker; marker не является institutional permission. Renderer создаёт текст bootstrap, а не исполняет apt/uv (`S01`, `S04`).

Ops C7 owner создаёт private temporary attempt вне checkout, фиксирует command/cwd/env, убирает ambient plugin/autoload/selection controls и читает structured workload+phase sidecars. Attempt identity, sidecar binding, test source/config/node-map hashes и plugin/conftest source identities сверяются. Typed lifecycle требует полный collected set и setup/call/teardown; setup skip имеет иной допустимый shape. stdout «passed» и exit0 сами по себе недостаточны (`S05`, `S07`, `S09`, `S10`).

Это намеренное усиление старого console-summary подхода, не нарушение relocation equivalence. Не восстанавливать доверие к stdout ради прежнего поведения. В выполненных unit witnesses sidecars synthetic; никакой реальный C7 verdict не получен.

## 4. Свежие проверки

1. **P01:**9 UDF-04 bodies/11 cases и8 existing server/CLI bodies — всего17/19 PASS. Проверены default unset root, distinct CLI roots, exact recorded command/cwd/env/check, unavailable modes, callbacks, console route, rendered script и local readonly capability probe. Whole modules actual, builders stage map — empty import fixture; stage activation не заявлена.
2. **P02:** macOS даже с marker, Linux без marker и Linux с marker0 блокируются до callback. Linux+marker1 достигает только recording callback. Conflicting roots отвергнуты; repo_root alias и Ops cwd resolution сохранены. Ни одной реальной серверной команды.
3. **P03 / C87-R01:** с default `require_server_for_build=True`, installed-layout root и отсутствующим marker direct domain adapter возвращает unavailable. Но actual console→orchestrator сначала вызывает server guard и выбрасывает LocalExecutionBlockedError: typed unavailable не emitted и gate receipt не создан. Linux+marker control возвращает unavailable/exit1 без subprocess. README обещает typed unavailable при отсутствии usable checkout (`S14:25–32`).
4. **P04:** actual receipt parser принимает только synthetic complete-pass/control и complete setup-skip/control. Missing teardown, wrong attempt, exit mismatch, altered source digest, narrowed collection и stdout-only получают failed. Ambient `-k`, collect-only и malformed addopts отказываются до subprocess. Private attempts удалены. Эти controls проверяют parser semantics, а не реальное исполнение C7.
5. **P05:** bootstrap renderer сохраняет quoting путей с пробелами; legacy Ops alias возвращает тот же текст. AST census domain CLI/server/orchestrator не содержит imports из tools. Script сохранён как `bootstrap_NOT_EXECUTED.txt`, provisioning не выполнялся.

## 5. Сохранить и доработать

**Сохранить:** explicit root contracts, correct Ops→domain dependency direction, domain orchestration, server-only admission, source-bound structured receipts, exact skip/failure reasons, private attempts вне checkout и distinction capabilities/authority. Не менять depth3 на новую magic depth и не ослаблять server policy ради зелёного local теста.

**C87-R01 — low diagnostic ordering.** Согласовать actual public route с existing unavailable contract для случая, когда repository execution в принципе недоступно. До любого реального subprocess/provisioning server guard остаётся обязательным. Различающий corpus: default config+installed root+missing marker; admitted server+installed root; valid checkout+blocked server. Если публичный server-workflow намеренно должен отдавать только policy denial до availability diagnosis, это нужно явно согласовать в контракте/README; наблюдаемое расхождение не исчезает от direct-adapter test.

Ограничение R: не утверждается bypass, false positive gate, runtime malfunction на admitted server или проверенный установленный wheel. Это узкое несоответствие diagnostic маршрутов, воспроизведённое с actual CLI/Ops/orchestrator code и platform/env controls.

**C87-G01 — native installed/server activation.** Проверить supported installed console/package contents, real receipt plugin hooks, selected checkout/cwd modes и server C7 lifecycle. Текущие17/19 unit cases используют explicit initialization/timing seams и recording subprocess. Весь shell/CI caller corpus и actual installed wheel не аттестованы. Shared C83-R01 import issue не дублируется.

**C87-G02 — deployment.** Rendered bootstrap и локальные capabilities — только подготовка/описание среды. Remote provisioning, requirements на target, historical script byte equivalence и институциональный допуск не установлены. Эта проверка не разрешает apt/uv/C7 в текущем audit environment.

## 6. Воспроизводимость и ограничения

[Commands/exit/logs](../04_Проверки/C87_UDF04/commands.json) · [Diagnostics](../04_Проверки/C87_UDF04/bounded_diagnostics.json) · [Native/seams](../04_Проверки/C87_UDF04/native_verification.json) · [Fixture authority limits](../04_Проверки/C87_UDF04/fixture_authority_limits.json) · [Остатки](../01_Реестры/C87_остатки.json).

Run02 exit0:5 MATCH,19 cases PASS. Run01 setup blocked на unrelated Python3.14 syntax в full timing.py; сохранён. Вместо source editing selected complete identity functions прочитаны/скомпилированы unchanged по ranges. Core/builders/tools.lib initializers — shells; actual whole CLI/Ops/server/orchestrator и lower DTOs исполнены. Producer plugin hooks, native pytest/pluggy/C7/installed wheel UNRUN. Synthetic versions/receipts не скрыты.

Checkout чист; source/tests/config/dependencies не менялись. All subprocess boundaries recorder/sentinel, remote server и production paths не использованы. Scientific/governance authority не следует из unit receipt.

**87/127 рассмотрены ограниченно. Следующий — UDF-05. Фаза 2 не начата.**
