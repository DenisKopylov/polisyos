# B / PR #55: независимый аудит остановленного closeout

Дата проверки: 2026-10-07. Это приёмка входящего B-пакета для G; она не меняет source, refs или integration branch и не запускает тесты.

## Точный вход и полный footprint

`origin` подтверждает PR #55 head `d030d82baed3b1c9d83c63a0ea26011a8247f47e`, tree `dc4ebd99afba72d13c60a46e77cd8fc99a002e60`. Последний commit — handoff/footprint carrier с родителем `af03a9d9693ed73b5dd1fd5b8fe8ad06dcb19cc8`, tree `bd77335cf86ea2f1c65714cd54d3b5e9540d2a83`; implementation handoff указывает base `f7967b420a0f80f32c35b2c7e4b5a90a017ff5a1`, tree `a07dc5b12a14ce004746cb43f7fbe609e8e0ff50`. Base является предком implementation. Handoff: `implementation-handoffs/B/continuation-final-full-B-20261007.json`; полный companion: `continuation-final-20261007-evidence/full-footprint.json`. В receipt `closure_ids=[]`, `formal_closure=false`.

G сейчас на `codex/e02-integration` SHA `76746fececd1a183a516c48f07ce2835baa8a2d1`, tree `51929dd44a3650c7842bf77aedcdeba6ecd1a755`, чистый checkout. G не является предком кандидата; их общий предок `9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`. Это не продолжение текущего G checkpoint, поэтому PR нельзя принимать как обычный append-only пакет без source-scope reconciliation.

Footprint receipt перечисляет 948 путей и 48,756,801 байт candidate-side: 936 research/docs, 2 release fragments, 4 `src` (два `.py`, два README), 6 тестов. Типы файлов: JSON 533, TXT 224, JSONL 63, BIN 62, XML 29, MD 12, PY 11, BLOB 10, TOML 2, ARGS 1, LOCK 1. Полная implementation-af03 projection от `198076863e143dea9f89f02734b13d50dae3eed5` — отдельный, более широкий знаменатель: 5,242 entries (5,125 добавленных и 117 изменённых), 168,694,626 candidate bytes; в том числе 73 product paths under `policy-engine/src/**` (all file types), 88 `tests`-путей и 5,032 research-документа. Не смешивать эту полную историю ветки с 948 путями текущего slice. Финальный d030 carrier сам добавляет только handoff и 2.66-MB полный footprint index.

Прямой source/test delta от slice base содержит:

- production: `src/polisyos/foundry/methods/artifacts/_implementation_identity.py`, `src/polisyos/scientist/orchestration/llm/gateway_client.py` и два README;
- tests: `test_imported_module_checkpoint_identity.py`, `test_module_source_identity.py`, `test_b_llm_cost_projection_consumer_e02.py`, `test_budget_llm_process_recovery.py`, `test_gateway_exact_money_consumer.py`, `test_gateway_numeric_decode.py`;
- release fragments: `2026-10-07-foundry-imported-module-identity.toml` и `2026-10-07-e02-b-gateway-exact-numeric-decode.toml`.

## Решение по коду и deciding evidence

**Ограниченный GO для source review, не code acceptance и не closure.** Gateway HTTP path читает `response.text()` и декодирует `json.loads(raw_text, parse_float=Decimal)` до имеющейся monetary/usage admission. Это устраняет превращение ненулевого `±1e-1000` в float-zero и сохраняет существующий результат `cost_status=invalid`, `cost_usd=None`; источник пока не меняет публичную float-модель денег. Для точного candidate-кода blob `gateway_client.py` `0dc65ee8cbe6477c50deb965d4d7cc12b3f6c5a2` совпадает с проверенным e7c source.

Решающий HTTP oracle — `continuation-gateway-numeric-evidence`: на e7c исходный 30-case тест даёт 30 PASS; удаление только `parse_float=Decimal` даёт 20 FAIL/10 PASS; baseline даёт 20 FAIL/10 PASS. Он проверяет алиасы стоимости, top-level/components, tiny ±, нули и обычные значения, booleans/NaN/Infinity, fractional token и отдельную обработку tool-arguments. Независимый 15-case `test_gateway_exact_money_consumer.py` прогнал фактический loopback HTTP → B enforcer/FileBudgetLedger → fresh D reader; candidate дал 15 PASS, baseline 13 PASS/2 FAIL, removal tiny cases 2 FAIL. Тестовый blob `f15c776f355799a372157d9c39954ff11af0bcde` совпадает с af03. Я также сравнил семь прямых B runtime modules этого теста (`response`, `traced_client`, `budget`, `budget_ledger`, `budget_middleware`, `budget_enforcer`, `gateway_client`): у всех source blobs e7c и af03 совпадают; receipt сохраняет per-case module origins. D reader привязан к трём модулям SHA `8f58d7349edefebbac7e7f21e6859f8daa075c1d`. Вывод ограничен этим exact B transport/ledger path и этим D reader.

**Ограниченный GO для finite JIT source identity, B74 остаётся LIMITED.** `final-source-readback.json` связывает `_implementation_identity.py` blob `7f0d0323474ee2f8f1fe4adea316c5260159262e` с source 7c; тот же blob находится в PR candidate. Source реализует конечный профиль обычных функций/immutable captures, static module-member selection и ограниченное получение публичных полей обычной функцией; dynamic/reflection/unsupported cases отказывают. Находка B74 не исчезла: реальный `test_returned_frame_namespace_refuses_before_replacement_effect` в terminal-native source `7c05686dbd8427fa2e8bf217827046acef097058` провалился. С checkpoint исходное значение 7, после замены namespace member resume реально вернул 107; effects содержат `original, original, replacement`, refusal отсутствует. Это физический эффект, не только mismatch-маркер.

Текущий 5-file affected-consumer replay: 128 собрано, 127 PASS/1 FAIL (именно B74), canonical JIT 9 PASS, независимый настоящий JAX consumer 3 PASS, removal finite getter property 1 FAIL, Ruff/format/mypy-normal-imports PASS. Я сопоставил все 5 выбранных test-input SHA256 и все 168 `polisyos` file origins из `terminal-native` с Git blobs af03: 5/5 и 168/168 совпали. Значит эти bounded outcomes применимы к текущим source/test bytes этой части candidate, несмотря на то что сам запуск привязан к 7c. Остаток — именно frame/global namespace класса. По P40 не продолжать лестницу частных `ArtifactRef.kind`/имени/descriptor исключений: либо владелец расширяет общий механизм и falsifier для целого класса, либо оставляет B74 ограниченным.

Отдельная незакрытая приёмка: текущий candidate включает четырёх-case `test_imported_module_checkpoint_identity.py`, но он отсутствует в финальном 5-file/128-case selector. Этот файл присутствует в старом полном 6fa запуске, однако все 4 случая там завершились setup ERROR (`tmp_path` не смог создать numbered dirs), а helper тогда был другим blob `9e8d63ab…`, не нынешним `7f0d0323…`. Поэтому старое наблюдение не доказывает текущий consumer path. После reconciliation ограниченная следующая проверка — только этот файл на точном G-compatible candidate; не повторять весь JIT cohort без изменения его входов.

## Source-scope HOLD: ветвление и ArtifactRef

В PR candidate `src/polisyos/scientist/orchestration/engine/state_branching.py` — blob `6f5bd398af2b70ca72754a782e224b990638541`; текущий G — `08760b26aae2a489b54441b20b3a90fcd040888d`. Это реальная разница 437 строк (371 добавление/66 удалений). Тест `tests/unit/scientist/orchestration/engine/test_state_branching.py` в этих деревьях совпадает blob-к-blob (`e0d4c98e6f3d33eddc70a4affe7c1a0f89908357`), то есть тестовый delta не сопровождает source delta. Эта зона управляет producer branch write scope, nested branching, завершением producer grant и mutation journal; совпадение типизированного `ArtifactRef`/kind само по себе не доказывает её безопасность. Root уже зафиксировал residual: при интеграции сохранить сильные G producer/write-scope инварианты; не чинить только `ArtifactRef.kind` и не переносить B ancestry как есть.

Решение: HOLD этой части до одного из двух конкретных исходов: (1) canonical B владелец reconcile-ит своё topic с актуальным G, сохраняет G-инварианты и даёт source-bound positive/negative consumer test на branch producer path; или (2) canonical B публикует новый узкий G-based delivery candidate, сохраняя старые refs/историю и перепривязывая source/test/receipts без held широкого ancestry. G сохраняет оригинальную историю принятых новых commits; cherry-pick старых upstream commits не запрошен. Не переписывать upstream историю, не делать instance-patch. B59 `closed` — лишь bounded technical proposal по branch isolation, не приёмка текущего кода и не разрешение заменять source на G.

## Cross-owner границы и 60 строк

Индекс `continuation-all60-decisions-20261007.json` явно имеет 25 bundles, `closure_ids=[]`, `formal_closure=false`; 48 `closed` — bounded technical recommendations, не закрытые findings. Статусы по всем 60 строкам пересчитаны из полного `decisions_by_id`:

- `closed` (48): B37–B40, B42–B53, B55, B57–B60, B62–B65, B69–B73, B75–B78, B90–B96, B149–B153, B155, LA-057;
- `limited` (7): B13, B14, B24, B66, B74, B89, B154;
- `held` (4): B61, B67, B68, B148;
- `open` (1): B87.

Cumulative union содержит 18 continuation delta-строк: 15 в `continuation-disposition-delta-20261007.json` плюс B49/B50/B53 из более раннего JIT continuation. Полный union: B13/B14/B24, B37, B49/B50/B53, B61, B65/B66/B67/B68, B74/B78, B87/B89, B148/B154. Остальные 42 дословно сохраняют предыдущие immutable bounded decisions и exact refs без нового исполнения. Не запускать и не оформлять повторное review этих 42 только из-за смены carrier.

Особые owner boundaries:

- B66 — независимый B→A consumer packet на source f796: 3 PASS/1 FAIL. При неизвестной стоимости `None` реальный A `_sum_call_events` выдаёт `0.0`; отдельный served downstream admission остаётся UNRUN. Это A/G задача, не дефект нового Decimal decoder.
- B120 находится вне этих 60 строк и относится к D `CTL-03`. В текущем `closure-decisions/D.md` B120 остаток — evaluator retry/cache-ledger admission и независимый фактический spend provider для D controller; метка `bridge_missing`. HTTP→ledger→fresh-reader тест выше полезен для B transport, но не исполняет реальный D controller/evaluator и не закрывает B120.
- B13/B154 остаются A/G served producer/publisher и локальными read-only inputs; B14/B24 — native Mac receipts; B87 — B/NET-01 finding; C — canonical production retry-owner writer (старый physical pool теряет retry owner при `permitfree=1`); B89 — отдельный cap3 checkpoint → cap1 restart budget failure, не cleanup.
- B61/B67/B68/B148 остаются held из-за отсутствующей внешней версии/permission/tenant ownership law. Не получать authority из readable/hash-identical bytes и не придумывать policy для зелёного теста.

## Общие gates и P41

Полный frozen native wave привязан к старому source `6fa9b7142ba590c3173f1cd3be097286db5acc4d`/tree `f53c67ae…`: 3,986 случаев, 1,326 PASS, 10 FAIL, 2,650 ERROR, SKIP 0; это не поздний JIT candidate. В том же frozen 6fa9 пакете wheel PASS; Ruff/format FAIL; mypy/runtime API/production invocation ERROR; verify/parity FAIL; architecture UNRUN; у verify 14 составляющих и у parity 34 составляющих UNRUN. Отсутствовали distributions `numba`, `dask`, `distributed`, `dowhy`, `econml`, `temporalio`; cloud production data недоступны. Не приписывать этот frozen profile нынешнему af03 JIT-коду, но и не выдавать его за окончательную зелёную сборку.

Receipt сам пишет `quality_admission=not_established` и `P41=not_established`: унаследованного красного нет без replay на соответствующем slice-base и нулевого пересечения полного входного знаменателя. Дешёвые прокси здесь расходятся: float превращает ненулевую стоимость в zero; версия модуля не замечает изменённый member; `PASS`/коллекция не означает исполненное тело; eventual refusal не отменяет физический replacement effect.

Для G: новая source admission — после проверки exact source/test/receipt, не по статусу all60. Ближайший полезный шаг — reconcile branch source и один exact consumer test, затем принимать только конкретные commits последовательно; broad replay и closure остаются отдельными решениями G.
