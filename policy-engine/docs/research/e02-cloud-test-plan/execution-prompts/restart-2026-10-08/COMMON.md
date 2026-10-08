# Общий контекст продолжения пяти остановленных roots

Этот документ сопровождает ORCH02, ORCH03, ORCH04, L01 и L02. Это commissioning/continuation plan, не приёмка кода и не formal closure. Срез G при анализе: `f1f99ba5d040e138e3b3b0849d53c9df17d1f437`, tree `9184f5871c76062718ff3785a32feeec9d241664`. В дальнейшем считай актуальным fetched G и его применимые решения; исторические pins ниже нужны для восстановления свидетельств.

PolicyOS — causal operating system и custodian policy justification. Candidate, numeric diagnostic, typed artifact и защищённая authority — разные уровни. Реальная capability требует input → producer → persisted artifact → bridge → consumer → verification → surface/declared scope. Не подменяй runtime property формой, markers, source GO, импортом backend или receipt соседнего source.

## Доступ к инструкции на новой машине

Репозиторий: `https://github.com/DenisKopylov/polisyos.git`. Fetch `codex/e02-integration`; инструкции этого этапа могут отсутствовать в main. До source authoring полностью прочти из fetched G:
- корневой `AGENTS.md`, `policy-engine/CONTRIBUTING.md`;
- `policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/HANDOFF.md`;
- `execution-prompts/parallel-2026-10-08/{COMMON.md,dispatch.json}` и свои role prompts;
- относящиеся решения `integration/connected-closeout-plan-2026-10-08/`, исходные criterion pointers и точные G review/lease supplements.

Пути после первых двух пунктов относительны `policy-engine/docs/research/e02-cloud-test-plan/`. Нельзя принимать весь initial source carrier из dispatch как G-selected composition. Results pack используется только после `import_results.py --check` и чтения `verification.json`; transferred text/navigation не становится новым runtime PASS.

## Новая облачная машина и custody

Пользователь разрешил перенос остановленных cloud roles на новые машины. Старые `/tmp` и `/dev/shm` пути — исторические адреса, не адреса нового host. Сначала проверь actual host/repository/remote, writable storage, memory/cgroup, runtime profile и transport. В managed cloud прочти доступные environment-runtime инструкции для proxy/CA/credentials. Секреты в outputs не выводи.

До создания новой пары branch/path выполни read-only admission с обоими точными selectors по `tools/devx/workspace/README.md#worktree-admission`; create для новой пары, resume только для существующей совпадающей lane. Receipt — snapshot, не reservation. Пользовательский перенос сохраняет canonical role/path ownership; не запускай одновременно прежнего и нового writer одной роли. Root ведёт компактную actual lease board. Не угадывай directories и не пытайся исправить unexpected HEAD/status reset/rebase/switch.

Published ref, fetchable commit, unattached Git blob и локальный unpublished commit различаются:
1. Ref/commit: fetch exact SHA и read back tree/parents/source/test/companion closure.
2. Unattached blob: получить штатным GitHub read API, проверить Git object identity и SHA256 bytes из packet; это patch/review, не applied candidate. Применить в своей admitted lane после проверки exact preimage/owner/dependencies, затем создать новые implementation commits и receipts.
3. Unpublished local commits: восстановить исходные объекты обычным export/bundle/patch transport с исходного host, если он доступен. Bundle должен включать отдельные leaf refs, а также уникальные неприменённые patches и deciding outputs вне commits. Один coordination commit не обязательно содержит leaf ancestry.
4. Если байты недоступны, явно unavailable. Допустимо заново реализовать свой механизм от проверенных canonical inputs с новой lineage и свежими reviews/checks. Нельзя объявлять новые байты старым SHA или переносить утраченный PASS.

Нативные hooks/CI не обходить. Разрешение новой машины не является разрешением отключить hooks. Прерывание hook с 137 или runner с −9 — ERROR/incomplete с неизвестной причиной, пока причина не измерена. Проверить ресурсы и exact command/profile, затем обычный повтор на рабочем host; наличие RAM/headroom и правильного toolchain не само по себе PASS.

## Параллельность и границы

User-owned root делегирует только один уровень прямых helpers; helpers детей не создают. Автор и independent reviewer различаются. Root — coordinator, не второй production writer. Независимые mechanisms/oracles/reviews/installed checks готовятся параллельно; сериализуются общий файл, governed generator/lock, DB/CAS/fixture directory/fixed port.

Cloud готовые compute checks не получают искусственную общую CPU/process/thread квоту. Локально тяжёлые A/C/G/L проверки согласуются в одном contended compute slot; лёгкое чтение/authoring продолжается. Production payload остаётся локально read-only; облаку достаточно portable fixtures и nonsecret source-qualified facts. Не требуй полного dataset для generic criterion.

G один writer shared generated families/inventories, `pyproject.toml` и `uv.lock`. C07 владеет IR uncertainty/facade; C08 graph supplier; C09 scientific producers; C10 A served/S10/HTTP; C11 configured search/builtin registration; C05 material generation; C06 census/CAN; C12 Legal query. Точные source/test/README leases читай в dispatch и G supplements: test-start selector не выдаёт write lease. Передавай partner requirement/patch через Git, не правь чужой путь.

L01 добывает/связывает конкретные фактические inputs, L02 проверяет authentic consumers. Недостающий issuer/law/profile удерживает только соответствующий защищённый переход или критерий. Candidate путь может продолжаться с явно сохраняемым unknown. Не превращай S1, все L01 packets или все production inputs в общий all-of gate; инженерное решение не заменяет внешнюю authority.

## Исполнение и delivery

Полный source/test/companion footprint → source freeze → nonauthor review → одна affected defining-property/consumer wave с independent oracle, negative и matched removal. Её размер выбирается по новой delta и настоящим зависимостям: не повторять unchanged history ради slots, но и не ограничивать новую generic delta только двумя ранее упавшими assertions. Сохраняй source/tree, environment/profile, exact input closure, wall time и полный deciding output. Коллекция, import readiness, сборка wheel и numerical consumer PASS — отдельные наблюдения.

P40: второй escape той же completeness/identity class требует общего механизма или честной bounded limitation с falsifier; не чинить именованные типы лестницей. P41: inherited red только по exact slice-base replay и нулевому пересечению полного gate denominator; иначе `not_established`. Не приписывать красный коду по signal9 или чужой summary.

После implementation — отдельный committed handoff с исходным unit/finding/criterion, source/tree/base, footprint, tests, limitations, source acceptance и proposed closure раздельно. Обычный push своей topic + independent fetch/readback. G интегрирует исходную историю append-only. Main и integration cloud/local authors не публикуют. Конфликт возвращается canonical owner через tracked packet, сообщения в чужие пользовательские чаты не авторизованы.

Portable broad replay выполняет независимый C13 один раз после G selected source freeze и reviews; локальный production-dependent общий closeout — после него на том же composition. Scoped verification конкретного immutable candidate может идти раньше; не выдавать её за общий replay.

Порог внимания к диску Mac — 18 GiB; выше только лёгкая проверка. При необходимости cleanup сохраняй уникальный код/данные/docs и deciding receipts, проверяй отсутствие активных пользователей; воспроизводимые объекты только в штатную Trash, никогда не очищать её. В cloud без native Trash лишь перечислить кандидатов, никаких permanent deletes.

Pattern pass: P01/P02/P12 — supplier/bridge reality; P05/P32/P37 — purpose/content-bound protected admission; P29/P38 — behavior вместо markers/setup; P35 — полный свой denominator; P40 — общий class repair; P41 — provenance красного. Acceptance signal этого плана — восстановленные доступные source bytes, выполненные affected checks либо точный unavailable boundary, опубликованный source-qualified handoff. Новых product enums/authority правил план не вводит.
