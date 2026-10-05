# Общий протокол E02 для A–G

## Источники и первые действия

1. Прочитайте этот файл, `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, `policy-engine/docs/reference/policy-design-case-failure-patterns.md`, `policy-engine/docs/research/e02-cloud-test-plan/execution-organization/README.md` и свою строку/группу строк в `bundle-owners.tsv` и `finding-owners.tsv`.
2. Baseline находится в `policy-engine/docs/research/e02-cloud-test-plan/results/`: `README.md`, `sources.json`, `cells.tsv`, `properties.tsv`, `events.jsonl`, `routes.tsv`, `verification.json`, `received/F01.txt`…`F15.txt`, `query.py`, `import_results.py`. Начните с `python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit <A-F> --failures-only --limit 30`; затем запросите каждый решающий finding/cell/path отдельно, если лимит не покрывает полный относящийся набор. Не делайте выводов по выборке из 30 строк. Полные знаменатели и исходные event locators сверяйте с TSV/JSONL и receipt исходной машины.
3. Результат Fxx привязан к конкретным test cells, исходному commit/ref, среде и входам. Это наблюдение baseline, не PASS будущего кандидата и не автоматическое подтверждение/опровержение finding. Сопоставляйте его через `routes.tsv`/`query.py`, затем читайте канонический bundle и настоящий producer→artifact→bridge→consumer. Если raw bytes архива не переданы, source-reported receipt служит только ориентиром: начинайте независимую работу по коду и bounded fixtures; для решения, зависящего от отсутствующих байтов, назначьте точный rerun исходной ячейки и сохраните deciding output. Не требуйте полного production dataset для каждого теста.
4. Разделите каждый остаток на code/mechanism, verification/oracle, missing input, semantic-owner decision. Исследовать и писать независимый тест можно до upstream; не выдумывайте недостающее правило или authority, чтобы получить зелёный сценарий. Известные held/open решения сохраняйте таковыми до надлежащего решения.

Плановая ёмкость каждого root A–G — до 20 прямых исполнителей, без субагентов второго уровня. Это ёмкость leaf-агентов, не 20 авторов или одновременно работающих pytest-процессов. A–F начинают с двух авторов независимых механизмов и расширяют до четырёх только при доказанной непересекаемости; остальная ёмкость — исследование, оракулы, review и handoff. В G один издатель integration branch; помощники проверяют receipts, потребителей и reviews.

## Изменения и Git

- Один slice — законченное свойство у одного canonical owner со своим тестом и обязательными companions. Записывайте slice-base **до любых своих изменений**. Пакеты `bundle-owners.tsv` задают первичных владельцев; общие издатели фиксированы: A — `runtime/quality/generation_cycle.py` и HTTP `run_lifecycle.py`; C — `fabric/data_plane/streaming.py`. B/E передают им producer/contract и сценарии, не пишут параллельно в эти файлы.
- До работы проверьте clean/attached checkout и актуальный `origin/main` или опубликованный `codex/e02-integration` checkpoint; запишите точный SHA. Каждому root/slice — своя ветка `codex/e02-<unit>-<slug>`. Не делите один изменяемый checkout между roots. Для A/C/G создавайте отдельные worktrees от fetched `origin/main`/G checkpoint; текущая исследовательская ветка не является published base. A/C разрешены commits и push локальных topic branches; B/D/E/F — commits и push cloud topic branches, PR по возможности. G может публиковать свою integration branch/checkpoints. Публикуйте ветку на remote, чтобы G мог fetch её точный head. Git — единственный обязательный канал handoff; не рассчитывайте на сообщение в другой чат.
- Проверьте Git transport в начале работы и публикуйте первый законченный slice рано. После push прочитайте remote branch head и сверьте SHA; G независимо fetch-ит и читает его. Если CLI push недоступен, используйте штатную публикацию PR/ветки облачной среды. Если ни один канал не работает, сохраните commits, отдайте применимый patch и handoff со статусом `transport_blocked`; локальный VM commit не объявляйте доступным G. Исходные SHA и deciding outputs должны пережить перенос.
- G начинает одновременно с авторами, создаёт/ведёт одну append-only `codex/e02-integration`, последовательно проверяет и интегрирует принятые SHA, затем публикует checkpoint в Git для зависимых slices. Авторы периодически fetch-ат ветку G и фиксируют, на каком checkpoint основана зависимость. При конфликте возвращайте изменение canonical owner-у; G не решает научную семантику ради удобства merge.
- Разрешены обычные коммиты и push только в свою topic/integration ветку; PR приветствуется. Запрещены push в `main`, force-push, rebase, reset и переписывание истории. Текущая публикация исследовательского пакета не выдаёт будущим агентам разрешение пушить код в `main`.

## Проверка и обязательный receipt

Для каждого slice проверяйте изменяемое defining property на реальном runtime path, затронутых importer/consumer и хотя бы один отрицательный/adversarial control. Покажите один пример, где дешевый proxy расходится со свойством. Constructor-only, marker/field-name, exit-code-only, mock-only и collection-only проверки это свойство не доказывают. Выполняйте быструю релевантную проверку во время разработки; broad suite запускается на стабилизированном checkpoint, а не после каждого merge. После изменения upstream contract повторяйте затронутые consumer проверки. Отсутствующий/пропущенный backend не объявляйте успешным: DoWhy/EconML markers и отсутствующий Temporal в базовом профиле явно ограничивают возможный verdict.

Compute policy: проверенная стартовая конфигурация — один численный test process на VM; лёгкие чтение/review/code-analysis задачи можно вести параллельно. Увеличивайте test workers только после замера throughput/RSS и подтверждения отсутствия contention. Сериализуйте общий fixed port, DuckDB, governed artifact writer и другой явно contended ресурс; не разделяйте изменяемые DB/cache/scratch между slices.

Каждый slice сохраняет `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/<unit>/<slice>.json` в Git. Сначала зафиксируйте implementation commit(ы), затем handoff JSON отдельным коммитом: receipt указывает на implementation commit/tree, но никогда на собственный будущий commit SHA. Минимальные поля:

```json
{
  "schema": "policyos.e02.implementation_handoff.v1",
  "unit": "B",
  "slice": "dur-ledger",
  "closure_ids": ["B37"],
  "bundle_ids": ["DUR-01"],
  "slice_base_sha": "...",
  "implementation_commits": ["..."],
  "candidate_tree_sha": "...",
  "branch": "codex/e02-B-dur-ledger",
  "pull_request": null,
  "changed_paths": ["..."],
  "baseline_cells": [],
  "checks": [{"command": "...", "target_sha": "...", "environment": "...", "input_closure": "...", "outcome": "PASS|FAIL|ERROR|SKIP|UNRUN", "output": "complete concise output or committed log ref"}],
  "property": {"statement": "...", "runtime_path": ["producer", "artifact", "bridge", "consumer"], "proxy_divergence": "...", "negative_controls": ["..."]},
  "predicate_basis": "recomputed|independently_reconciled|consumer_asserted|institutionally_supplied|not_established",
  "capability_state_or_finding_state": "...",
  "limitations_and_next_owner": ["..."]
}
```

Добавляйте полные source/environment/input identity, producer/artifact/bridge/consumer/surface, authority purpose, provenance, rule/schema version и time roles там, где они определяют вывод. Короткий deciding output включайте в receipt; полный умеренный лог коммитьте рядом с ним. Огромные логи/raw остаются в локальном ignored `raw/` с `path@sha`; если независимый приёмщик не может получить deciding bytes, помечайте evidence как `not_established` и назначайте точный rerun, не выдавая summary за receipt. Если PR создан, прикрепите его к текущей задаче через `mcp__codex_app__attach_artifact`, если этот инструмент доступен; обязательные repository/PR checks не обходите и не ослабляйте.

Полный production dataset остаётся только локально, read-only. Нет blanket-требования прогонять каждую проверку на production: используйте достаточные fixtures для generic property. Когда критерий по существу зависит от реальной history/evaluator/source law/full data, cloud finding остаётся ограниченным до локальной проверки на точном candidate SHA. Никаких секретов или полного набора данных в branch/PR.

Inherited red по P41 принимается как унаследованный только после точного повторения команды на slice-base до всех своих изменений **и** доказательства нулевого пересечения изменённых путей с полным input denominator gate. Иначе помечайте источник как `not_established`; не выбирайте более близкий SHA для зелёного вывода.

Pattern pass для исполнения: P01/P02 требуют реальной producer→artifact→bridge→consumer цепочки; P05/P09/P15 удерживают authority, warnings и LLM output в правильных границах; P10 требует семантического discriminator; P27/P31 — канонического owner и закрытия класса дефектов; P32/P33 — content-bound admission и adversarial variants; P35 — полный знаменатель с указанием исполнителя; P37/P38 — классификацию gate predicate и проверку фактического свойства; P40 — не чинить один и тот же escape лестницей локальных патчей; P41 — атрибутировать красный только с slice-base.

## Приёмка G и closeout

G fetch-ит exact remote head/PR и отдельный handoff receipt, проверяет base/candidate ancestry, owner, diff footprint, deciding evidence, негативный сценарий и зависимости, затем делает code review и только после приёмки добавляет slice в `codex/e02-integration`. Коммит/PR и finding closure — разные решения. Записывайте каждый интеграционный SHA/checkpoint в Git; зависимая группа получает его через fetch. Финальный broad regression запускается один раз на зафиксированном кандидате, затем локальные data-dependent checks и итоговый residual report. `main` остаётся вне scope до отдельной явной авторизации публикации.
