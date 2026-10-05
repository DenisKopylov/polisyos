# Общий протокол E02 для A–G

## Источники и первые действия

1. Прочитайте этот файл, `AGENTS.md`, `policy-engine/CONTRIBUTING.md`, `policy-engine/docs/reference/policy-design-case-failure-patterns.md`, `policy-engine/docs/research/e02-cloud-test-plan/execution-organization/README.md` и свою строку/группу строк в `bundle-owners.tsv` и `finding-owners.tsv`.
2. Baseline находится в `policy-engine/docs/research/e02-cloud-test-plan/results/`: `README.md`, `sources.json`, `cells.tsv`, `properties.tsv`, `events.jsonl`, `routes.tsv`, `verification.json`, `received/F01.txt`…`F15.txt`, `query.py`, `import_results.py`. Начните с `python3 policy-engine/docs/research/e02-cloud-test-plan/results/query.py --unit <A-F> --failures-only --limit 30`; затем запросите каждый решающий finding/cell/path отдельно, если лимит не покрывает полный относящийся набор. Не делайте выводов по выборке из 30 строк. Полные знаменатели и исходные event locators сверяйте с TSV/JSONL и receipt исходной машины.
3. Результат Fxx привязан к конкретным test cells, исходному commit/ref, среде и входам. Это наблюдение baseline, не PASS будущего кандидата и не автоматическое подтверждение/опровержение finding. Сопоставляйте его через `routes.tsv`/`query.py`, затем читайте канонический bundle и настоящий producer→artifact→bridge→consumer. Если raw bytes архива не переданы, source-reported receipt служит только ориентиром: начинайте независимую работу по коду и bounded fixtures; для решения, зависящего от отсутствующих байтов, назначьте точный rerun исходной ячейки и сохраните deciding output. Не требуйте полного production dataset для каждого теста.
4. Разделите каждый остаток на code/mechanism, verification/oracle, missing input, semantic-owner decision. Исследовать и писать независимый тест можно до upstream; не выдумывайте недостающее правило или authority, чтобы получить зелёный сценарий. Известные held/open решения сохраняйте таковыми до надлежащего решения.

## Максимальная полезная параллельность

По умолчанию делегируй каждую независимую полезную задачу. Если сомневаешься, нужен ли дополнительный субагент, и можешь назвать отдельный проверяемый результат, запускай его. Оркестратор организует критический путь и принимает решения; исследование, подготовка тестов, реализация независимых механизмов и проверка идут параллельно. Не выполняй их последовательно только потому, что можешь сделать сам.

Цель — заполнить доступную ёмкость до **20 активных прямых субагентов** содержательной работой; при достаточной очереди стартуй 16–20, не ждя завершения первой пары. Проверь фактический доступный лимит; если он ниже, используй все доступные слоты и очередь. Новые готовые задачи получают освободившиеся слоты сразу. Субагенты не создают своих субагентов. Нет фиксированного лимита «2 автора, максимум 4»: число авторов определяется готовыми непересекающимися механизмами и общей ёмкостью, а роли перераспределяются по очередям.

Для каждого задания укажи pinned base, конкретный вопрос/свойство, входные source/cell refs, разрешённые write paths или read-only режим и ожидаемый patch/test/вывод. Не раздавай связанные finding ID разным авторам одного owner. `initial_writer_family` — стартовая карта конфликтов; объединяй работу над общим инвариантом. Разделять семью можно после проверки реальных paths, тестов и обязательных companions. Один writer на изменяемый файл/механизм, общий schema/lockfile/generator/ledger; независимые авторы используют изолированные checkout/worktrees и малые законченные commits. Если sandbox-изоляция недоступна, независимые subagents готовят patches, а единственный writer применяет их последовательно.

Внутри каждой группы параллельно веди: поиск reuse/producer/consumer, проектирование независимого oracle, реализацию свободных owners, adversarial/negative probes, независимый review и подготовку evidence/handoff. Тестовый автор пишет в отдельно выделенный test path либо отдаёт patch владельцу; он не конкурирует за тот же тестовый файл. Автор механизма и его reviewer — разные исполнители. Пока один owner занят или локальная тяжёлая проверка ждёт свободного ресурса, другие проектируют будущие discriminators, исследуют соседних consumers и проверяют другой готовый slice. В облаке проверки свободных slices стартуют по готовности без очереди вычислительных слотов. Результат каждого задания должен менять решение или предоставлять проверяемый артефакт; одинаковое исследование без отдельной гипотезы/контроля не заполняет полезный слот.

Оркестратор выдаёт компактный контекст с путями и SHA, не копирует весь набор результатов каждому leaf. Сначала читается решающий source block; исследование разрешается расширять по новым зависимостям. Рабочую доску задач/leases веди в доступной памяти или ignored scratch, без отдельного сервиса и двадцати новых планов. Полученные summaries — навигация: код и deciding evidence читаются и проверяются на конкретном SHA. В G параллелятся reviews/receipts/consumer checks; интеграционную ветку публикует один исполнитель.

## Изменения и Git

- Один slice — законченное свойство у одного canonical owner со своим тестом и обязательными companions. Записывайте slice-base **до любых своих изменений**. Пакеты `bundle-owners.tsv` задают первичных владельцев; общие издатели фиксированы: A — `runtime/quality/generation_cycle.py` и HTTP `run_lifecycle.py`; C — `fabric/data_plane/streaming.py`. B/E передают им producer/contract и сценарии, не пишут параллельно в эти файлы.
- До работы проверьте clean/attached checkout и актуальный `origin/main` или опубликованный `codex/e02-integration` checkpoint; запишите точный SHA. Каждому root/slice — своя ветка `codex/e02-<unit>-<slug>`. Не делите один изменяемый checkout между roots. Для A/C/G создавайте отдельные worktrees от fetched `origin/main`/G checkpoint; текущая исследовательская ветка не является published base. A/C разрешены commits и push локальных topic branches; B/D/E/F — commits и push cloud topic branches, PR по возможности. G может публиковать свою integration branch/checkpoints. Публикуйте ветку на remote, чтобы G мог fetch её точный head. Git — единственный обязательный канал handoff; не рассчитывайте на сообщение в другой чат.
- Проверьте Git transport в начале работы и публикуйте первый законченный slice рано. После push прочитайте remote branch head и сверьте SHA; G независимо fetch-ит и читает его. Если CLI push недоступен, используйте штатную публикацию PR/ветки облачной среды. Если ни один канал не работает, сохраните commits, отдайте применимый patch и handoff со статусом `transport_blocked`; локальный VM commit не объявляйте доступным G. Исходные SHA и deciding outputs должны пережить перенос.
- G начинает одновременно с авторами, создаёт/ведёт одну append-only `codex/e02-integration`, последовательно проверяет и интегрирует принятые SHA, затем публикует checkpoint в Git для зависимых slices. Авторы периодически fetch-ат ветку G и фиксируют, на каком checkpoint основана зависимость. При конфликте возвращайте изменение canonical owner-у; G не решает научную семантику ради удобства merge.
- Разрешены обычные коммиты и push только в свою topic/integration ветку; PR приветствуется. Запрещены push в `main`, force-push, rebase, reset и переписывание истории. Текущая публикация исследовательского пакета не выдаёт будущим агентам разрешение пушить код в `main`.

## Проверка и обязательный receipt

Для каждого slice проверяйте изменяемое defining property на реальном runtime path, затронутых importer/consumer и хотя бы один отрицательный/adversarial control. Покажите один пример, где дешевый proxy расходится со свойством. Constructor-only, marker/field-name, exit-code-only, mock-only и collection-only проверки это свойство не доказывают. Выполняйте быструю релевантную проверку во время разработки; broad suite запускается на стабилизированном checkpoint, а не после каждого merge. После изменения upstream contract повторяйте затронутые consumer проверки. Отсутствующий/пропущенный backend не объявляйте успешным: DoWhy/EconML markers и отсутствующий Temporal в базовом профиле явно ограничивают возможный verdict.

**В облаке B/D/E/F:** запускайте готовые проверки параллельно, включая тяжёлые, без искусственного лимита процессов, test workers, численных потоков или CPU-квоты в оркестраторе. Вычислительная способность VM определяет фактический throughput. Не ждите измерений для допуска следующего готового теста; wall time/RSS/env фиксируйте для интерпретации результатов. Сериализуются только конфликтующие fixtures/shared state: один fixed port, изменяемая DB/cache/scratch, общий generator/артефакт. Сам тест может намеренно создавать конкурентных workers для проверки свойства. Недоступный backend, авария runner или нехватка ресурса фиксируются как фактическое ограничение исполнения, не как доказанный product defect.

**Локально A/C/G:** защищайте суммарную нагрузку MacBook, а не выдавайте каждому root независимую тяжёлую квоту. G координирует общую очередь; начните с одного тяжёлого численного/полного data прогона на ноутбуке и одного численного потока, повышайте только при свободной RAM/CPU и отсутствии интерактивного замедления. Лёгкие тесты, чтение, авторство и review продолжаются параллельно. Production data read-only; DB/ports/governed writers изолированы. Проверку immutable candidate N можно вести одновременно с авторством N+1; receipt остаётся привязан к N. Это местное ограничение не переносится на облачные VM.

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
