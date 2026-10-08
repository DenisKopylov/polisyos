# G / DevX — конкретные препятствия native publication

Это очередь владельца G/DevX, а не дополнительное разрешение ORCH03 менять общие policies. ORCH03 выполняет собственные C07/C08/C09/B190 действия одновременно. Root G `0321633…` и metadata composition `e01d15…` имеют одинаковые product source/tests/config; успешные ordinary Lefthook commits документации не означают PASS отдельно вызываемой Python pre-commit chain.

## Подтверждённый Ruff root defect

Read-only settings probes на G, Ruff0.14.10, подтвердили: native repo-root caller с `--config=policy-engine/ruff.toml` разрешает generated `../../../tests/**` вне product tree; discovery из `policy-engine` разрешает те же ignores внутри product tests. Исторические488 findings/100fixes/388residual не являются свежим диагнозом каждого правила.

Canonical manifest `policy-engine/architecture/tooling/tool_config_split.toml`, generator `policy-engine/tools/devx/workspace/tool_configs.py`, девять fragments `architecture/tooling/ruff/per-file-ignores/`, caller `policy-engine/.pre-commit-config.yaml`. Один DevX writer выбирает согласованный project-root для caller/generator. Не hand-edit generated `ruff.toml`/generated.toml, не добавлять построчные ignores и не отключать hooks.

Acceptance: обычная generation через `workspace tool-configs`, затем `workspace tool-configs --check`; settings probes **из обоих cwd** на `tests/unit/scientist/search/funnel/test_level4_full.py`; применимые selected lint/format/type checks с реальными path sets. Исправление root convention не подавляет настоящие product violations. Перед native `--fix` сохранить staged preimage; после него проверить весь diff.

## SOTA contract / policy rows

Команда: из product root `uv run polisyos-tools workspace repository-sota-closeout --contract-only`. Original cloud log `/workspace/orch03-c07-packet-commit2.stderr`, SHA256 `44488b8861ccca0260fc30b11fcc6ad8cde66fcb3a4c1e50f29a35edbb52cdf0`; G получил blocker report, **не raw stderr**.86parsed lines — historical source report: docs freshness1, imports21, complexity9, shims12, phase6.5 metadata39, public polish4. Fresh counts только после полного прочтения нового deciding output.

Owner-bearing inputs: `architecture/exceptions/docs_freshness.toml`, `architecture/imports/exceptions.toml`, `architecture/exceptions/complexity.toml`, `architecture/shims.toml` и registries `_check_phase65_exception_cleanup()`. Для каждой строки: actual current debt/consumer, существующий issuer, remove/fix устаревшую exception либо оформить evidence-backed bounded решение по действующей policy. Новые сроки/waivers без основания не назначать. Public links: `docs/reference/frontend/atlas-live-application-audit.md:22` и `docs/brand/ATLAS_SOURCE_OF_TRUTH.md:43,69,84` требуют решения своих doc/policy owners о current public references. Не менять clock и не импортировать научную authority из технического GO.

## Две причины, которые ещё не локализованы

- Inventory: native `uv run python tools/quality/validation/repository_last_mile_inventory.py --check` сообщил missing tracked `tests/unit/scientist/search/funnel/test_level4_full.py`. На G файл tracked и present1247bytes. На exact recovered candidate проверить Git index/worktree/cwd/наличие и повторить этот command. Если отсутствует tracked bytes — восстановить их из **того же** source identity штатным способом, не создавать пустой тест или менять baseline. Если дефект в census — packet canonical DevX owner.
- Package imports: `uv run polisyos-tools validation check-package-import-gates --fail-closed` сообщил только `NameError InterventionIdentificationStatus`. Static checker не заявляет runtime-import coverage. Нужен полный CLI traceback и отдельный cold import на том же уже provisioned profile с module origins. C08 source lease подтверждён в causal namespace; истинный runtime binding defect там чинит C08. Checker/caller issue — DevX. Короткое сообщение не доказывает missing export/cycle; текущий G импортирует enum и seeds globals.

Полный native gate output, candidate/index/tree/cwd/profile и actual source-origin bindings нужны до repair. P41 `not_established`, пока нет exact slice-base replay и zero overlap с полным input denominator. Reproduction alone не делает overlapping gate inherited.

## Checkpoint и независимое исполнение

G публикует только законченные собственные DevX companions в integration обычными commits; ORCH03 включает **конкретный** checkpoint без потери pending index. Не нужен весь E02 source freeze для test-only C07 temporal fixtures, C09 precision oracle или C08 cold-import диагностики. Broad replay по-прежнему ждёт selected G composition. Если mandatory gate ещё красный, ORCH03 сохраняет complete affected work + ordinary recovery export и точный owner packet; он не повторяет одинаковый commit/retry и не спрашивает заново уже выданные path grants. Этот документ не заявляет, что DevX repairs выполнены.
