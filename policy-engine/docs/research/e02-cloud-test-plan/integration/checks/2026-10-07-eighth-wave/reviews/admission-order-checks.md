# B/D/F: порядок допуска и очередь проверок

Снимок: G `ff277db7798fc312654704fa51c52e00f53f10f4` (tree `618e17b5da96a623d5e57f30d265e245a2b277eb`). Pin-set `full-reviewed-head-delta.json` SHA-256 `23cdf6d8cbb1d209c4ad0db52d92fbe8b3a4045eda6c12855f959594296abdba`. Все 23 B/D/F `origin/codex/...` refs в локальном Git равны указанным heads; это снимок локальных refs, fetch не выполнялся. Ранее `import_results.py --check` завершился `ok:true`, `verification.json` прочитан; baseline query — контекст, не доказательство owner/приёмки.

В колонке `G-unique` — commits `rev-list HEAD ^ff277...`; `после pin` — commits после `previous_reviewed`; `Δ src/tests` — изменённые Python source/test paths после pin, а для heads без pin — от общего предка с G. Точные прежние pins и slice bases остаются в JSON и в коммитнутых handoffs.

| Локальный ref suffix | Точный HEAD | G-unique | после pin | Δ src/tests |
|---|---|---:|---:|---:|
| B-current-adapters | `c0f31b203c44bed9390913a53ceb5aa5dccacf8b` | 447 | 420 | 40/55 |
| B-current-cas-generation | `425744a521484c262ff55421ed6dd09793594b33` | 351 | 21 | 0/1 |
| B-current-composition | `21cf3f92a8bf3f09e6a02a9d22835bacc3983dbd` | 54 | 11 | 0/0 |
| B-current-coordination | `0d1f158c8aa86cf287b41b0e88121b8e0aa005e4` | 441 | 114 | 4/11 |
| B-current-durability | `9f2a31c8869525ecf55fa55d0f5b08027c09a988` | 443 | 371 | 30/44 |
| B-current-execution-state | `b3ab709441527919b5839fcdb5b0e02c1a6029ea` | 345 | 300 | 39/44 |
| B-current-runtime | `b0ab3419eb2f165a834dc2cccb17b7538d2071aa` | 58 | 26 | 0/1 |
| D-published-champion | `c8dba610c92730f1fb073b453148a948f7b2bb51` | 278 | 18 | 13/6 |
| D-published-funnel | `5ab28d7621a6e290d4d0482a5091a62d201de850` | 327 | 12 | 0/1 |
| D-published-oracle | `c879ce8de2701513347ab811b60f63aebb61b351` | 248 | 12 | 0/2 |
| D-published-root | `8c17a44c6f6ce8fe1b3dc334a689fb6cb05a6e47` | 501 | 128 | 16/22 |
| D-published-search | `fba341253528eb344c340b5e683ecc1f88ea631f` | 303 | 18 | 3/5 |
| D-published-transfer | `273616d37737b86665d1d12f0d90e22212afb2e1` | 254 | 7 | 1/2 |
| F-api-20261006 | `90c72b51155321684c788cd5a03fbb70fc001d53` | 189 | — | 58/62 |
| F-closeout-20261006 | `072d45a56d1119fe3e7665cec2cbbdca015d2934` | 199 | 62 | 9/12 |
| F-dowhy-20261006 | `c8c2319d6c48f23f90103322da8cd63bc959da6f` | 14 | — | 3/3 |
| F-economics-20261006 | `3912782bfd55cc87f76757310c32603ecbe58cc3` | 14 | 3 | 1/1 |
| F-fry-20261006 | `a2d55a1942e1f56f35cf2b9772ae56b0b46de95d` | 151 | 168 | 50/54 |
| F-graph-20261006 | `46bbfa53adc8da775a08b66b80d02109cc5b2db8` | 152 | 145 | 30/44 |
| F-graph-intake-20261006 | `2044260c39dc4988b37d5a1568b65a1cdb1e3d31` | 3 | — | 2/3 |
| F-installed-worker-20261006 | `3dde887e22592cdd7c1fe8865707afdfd72dc6fb` | 27 | — | 19/16 |
| F-lex-20261006 | `77166daa0ff8b9659e3978447f9016c691694266` | 3 | 1 | 0/0 |
| F-tmle-20261006 | `d13e83bba7ac9ae02f68ff23ddf7ed8a24ea424a` | 151 | 19 | 2/3 |

## Приоритет допуска

1. **F graph intake** — самый короткий законченный source chain: branch `2044260…` (tree `56a3f7…`), implementation `6321dc33476b0fad24d97ebb140c373608d30019` (tree `f01888…`), handoff `F/graph-intake-native-20261006.json`. Head и candidate отличаются в receipts, но source/tests совпадают. Независимый bounded GO уже приложен. Допускать только ограниченный synthetic intake; B214 остаётся limited, EMP-01 от A и canonical production/CAS custody от C не установлены. Не объявлять protected consumer или production closure.
2. **F DoWhy** — полный source-chain из 14 commits (3 source + 3 tests), candidate `423165322e508a293ffd23918c039c99fb37e7a7` (tree `191a4c…`), handoff `F/dowhy-worker-20261006.json`; source/tests от candidate до `c8c2319…` неизменны. Использовать текущий bounded independent GO и 25 реальных worker cases на неизменившемся профиле; не повторять эти cases. B212/B213 limited; Python 3.14 markers/EconML и production-positive admission остаются UNRUN. Отдельный installed/API consumer нужен для packaging closure.
3. **F economics** — взять текущую ветку целиком, не только два последних commits: 14 G-unique, но delta после pin — 3 commits, один `fiscal.py` и один тест. Handoff source `1324d2fcd7b75e448ad0fa1cce128a79101df1aa` (tree `dc4b6a…`); текущий head source/tests byte-identical. Есть bounded независимый GO; исходный результат `124PASS/1FAIL` сохраняет отдельный ABM-owner failure, это не общий PASS и не closure. В F-API эта ветка уже ancestor, и `fiscal.py`/тест там byte-identical.
4. **D lesson partial consumer** — малый delta после старого pin, но ещё НЕ допущен: handoff `D/continuation/lesson-partial-consumer.json@d61e97d1dbab91f0174ba5af8b01a488dc04ee61`; implementation `6ca3b5f167c140370a44653f25a3483bad4a9659`, final source/test `409dce868a8a4f0c80fc02881b089ba93a26914d` (tree `cf0fe4946f41e904880ac1c6ec1b0ef7a57663a7`). 40 PASS и removal controls есть, но receipt прямо говорит «independent original-criterion review pending». Сначала этот отдельный review; B136 remains not closed. После него допустимы exact source/test paths `lessons.py`, `test_lesson_query_persistence.py`, `test_lesson_partial_consumer.py` без повтора byte-identical 40-case run.
5. **Только test/receipt deltas:** B runtime — один тестовый actor-binding assertion; B CAS generation — один completion-admission consumer test; D funnel — один controller integration test; D oracle — два независимых regression tests; F Lex — документационная поправка, код уже в G (`00a6eda…` ancestor, ноль source/test delta). Их можно не трактовать как новые product capabilities. Присоединять лишь после принятия предшествующей reviewed ancestry; запускать только новые exact selectors, если их deciding output отсутствует.

## Git-порядок, конфликты и проверки

Все объявленные старые `previous_reviewed` pins пока не являются ancestors G; поэтому `git merge HEAD` импортирует всю уникальную ancestry, не только видимую последнюю правку. Проверьте для каждого принятого topic: `git merge-base --is-ancestor <previous-reviewed> <HEAD>`; `git rev-list --reverse --topo-order <HEAD> ^ff277db7798fc312654704fa51c52e00f53f10f4`; `git diff --name-only <previous-reviewed> <HEAD> -- policy-engine/src policy-engine/tests`; затем сопоставьте полный closure commit-by-commit с immutable handoff. Обычный `git merge --no-ff <exact-HEAD>` допустим только когда весь импортируемый closure принят. Не cherry-pick и не переписывать topic. Если нужен изолированный малый slice с непрошедшими ancestry, попросить canonical owner опубликовать новый forward-only descendant, исходную историю оставить нетронутой.

Есть полезная ancestry-очередь: D-root содержит D-champion, D-oracle, D-search и D-transfer; после принятия всех четырёх в нём останется 130 новых commits против G. D-funnel не ancestor D-root, но его один изменённый integration-test blob совпадает с D-root — не интегрировать второй раз, если root receipt покрывает тот же consumer. F-economics и F-TMLE — ancestors F-API; после этих двух heads у F-API остаётся 35 новых commits, а у F-closeout после F-API — 10. F-API всё ещё требует review своих 58 source/62 test paths. F DoWhy и installed-worker siblings не имеют общей ancestry. Пять общих worker/API blobs из DoWhy handoff byte-identical, но текущий installed-worker head `3dde887…` на 9 commits после reviewed candidate `ab56a0…`: появились `gcm_fit.py`, `gcm_query.py`, `ir/analytics/causal_graph.py` и `test_causal_graph_cache_rows.py`. Три из четырёх blobs совпадают с F-API; `causal_graph.py` расходится (`342d416…` против `f263566…`). Этот файл требует решения его канонического F/IR owner; старый wheel GO не покрывает текущий head. Сначала разрешить текущий source delta и точный source receipt, затем DoWhy producer → installed packaging consumer и один installed wheel/CAS fresh-reader check на замороженном consumer. B current ветки не образуют ancestry chain и их deltas реально пересекаются (adapters↔durability: 65 путей; durability↔execution-state: 55; coordination↔durability: 15); B canonical owner должен выбрать согласованный current branch, не чередовать tips.

После допуска проверять только изменённый runtime путь и точные consumers: F graph — три selectors из handoff (`test_reconcile_causal_graph_node.py`, `test_reconcile_graph_intake_contract.py`, `test_reconcile_causal_graph.py`); D lesson — пять selectors из handoff, включая дубликат evidence/partial quota; B runtime/CAS — соответственно `test_retained_protected_act_wrong_binding_refuses_before_filesystem_effect` и `test_completion_admission_consumer_oracle.py`. `cd policy-engine && uv run pytest -o addopts= -q <точные selectors>` — только на frozen integration SHA, одна локальная тяжёлая задача/один численный поток. D transfer→receiving optimizer и D funnel→настоящий downstream workflow проверяются только если их конкретный consumer contract изменён; mocks не заменяют этот путь. Не повторять source-identical checks и не требовать production dataset без исходного criterion. Один общий дорогой replay — после общего source freeze; finding outcome остаётся отдельным от PASS/FAIL/UNRUN check status.


Publication scope: this is a pinned review observation/recommendation. A bounded GO here is not an integrated commit or formal finding closure. The root decisions in the eighth-wave README and newer per-unit audit take precedence for later heads.
