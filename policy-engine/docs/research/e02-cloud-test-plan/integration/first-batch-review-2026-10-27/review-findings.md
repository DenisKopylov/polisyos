# Решения G и продолжение первой партии

Проверяемый пакет: `8c5efa250faa2e983b1ce7a2021b9ea135846a69`. Все source указания ниже относятся к Git objects, не к движущемуся checkout исполнителя. При следующем изменении зависимости соответствующий receipt нужно повторно привязать либо переисполнить. Этот документ не разрешает массовый merge и не требует повторять неизменные проверки.

## G27-01 — V6: неполное совпадение node/state ArtifactRef

**Приоритет: блокирует source acceptance V6.** Статический дефект подтверждён на `8a24cc8ff895e61a51de2f91191251a9a8b23d84` и сохранённом кандидате; отдельный runtime exploit в этом review не запускался.

В `policy-engine/src/polisyos/runtime/http/services/debug.py:398–430` выбираются node refs с тем же artifact ID и отвергаются конфликты kind/media. `_artifact_ref_matches_any` около строки 2683 также сравнивает только ID/kind/media. При этом canonical `ArtifactRef`/`artifact_ref_identity_key` в `core/artifacts/manifest.py` включает `manifest_profile_sha256`. Проверка state и workflow-report артефактов не проверяет равенство вложенных node/state профилей.

Минимальный расходящийся случай: state содержит `(X, kind, media, profile A)`, а проверенный workflow report приписывает узлу `(X, kind, media, profile B)`, `A != B`. Node gate пропускает связку, затем CAS правильно проверяет и читает **A**. Это не делает **B** основанием этого узла. Вторая ссылка может выбирать другой существующий profile или лишь синтаксически допустимый digest — node profile здесь не разрешается. Наличие корректных state/report manifests не устраняет конфликт их содержимого.

**Решение владельцу Runtime debug/RES-03:** reuse canonical complete-ref identity; для всех одноимённых ID в выбранном node binding исключить конфликт полных identities, а затем читать именно согласованный ref. Не добавлять четвёртый локальный comparator рядом с уже существующим owner helper. Legacy отсутствие profile не превращать в wildcard или догадку о current profile; сохранить только явно поддержанный owner контракт. Если такого общего правила для конкретного legacy ref нет, отказать в exact binding с сохранённой диагностикой.

Минимальная проверка: положительный A/A, node-only A/B, A/absent в declared profile-sensitive пути, смесь A+B в одном node, неверный/недоступный B, оба способа запроса (explicit artifact ID и default from state). Fresh GET должен отказать на конфликте до выдачи результата; подмена gate при сохранённых status/ref markers должна сделать negative красным. Приёмка этой правки не закрывает следующий пункт B13 автоматически.

## G27-02 — B13: независимый сбой доказан, общее основание — ещё нет

V6 реально производит SimulationResult, сохраняет CAS/state/report, затем получает `res03.later_failure`; независимый sibling заканчивает работу, зависимый от сбоя узел пропускается, fresh parsed GET сохраняет результат и точный error. Это принято как исторический bounded witness на `8a24cc8`.

Но `dependent_after_failure -> later_failure` доказывает skip невыполненного узла. Исходный B13 также требует отзыва зависимых выводов при нарушении **общего основания**. Нужен persisted positive → изменение/инвалидация общего basis → fresh consumer не выдаёт зависимый вывод как действительный, сохраняя независимую часть и историю. Отдельно удалить retained result reference, оставив успешные markers: served reader должен отказать. Wrong/corrupt ref — полезные, но иные negatives.

Владельцы — существующие R1/V1/V6 boundaries; не создавать новый invalidation engine. Контролируемого источника достаточно для generic property. Нельзя требовать production corpus или браузер только потому, что старый план перечислял возможный dataset или писал `GET/browser`: исходный V6 exit требует served reader, и настоящий parsed HTTP GET его удовлетворяет.

## G27-03 — I1 / LA-041: исполнить исходную checkpoint матрицу

Принимается ограниченный I1 exit на `a92c977`/`76691bd`: композиция 18 paths, same-stat input invalidation, unchanged skip, warm/fresh consumers, WVS/session behavior. 20-node receipt — 17 I1 + 3 I4; 25-node receipt — другая I1 группа. **Импорт test module не означает исполнение всех его testcase.**

Полная LA-041 матрица пока не доказана. При source selection найти существующие selectors по точному имени, сохранить их actual path/node ID и исполнить на одном immutable candidate:

- `test_changed_output_bytes_do_not_reuse_merge_stage`;
- `test_embed_resume_does_not_skip_when_selected_member_is_missing`;
- `test_empty_normalize_output_directory_is_not_reusable`;
- `test_selected_empty_generation_is_reused_without_reencoding`;
- `test_explicit_empty_required_outputs_do_not_fallback_to_recorded_outputs`;
- `test_legacy_directory_state_without_output_inventory_is_cache_miss`;
- `test_embed_resume_rejects_config_rule_and_selected_output_changes`;
- `test_interrupted_embed_state_is_never_reusable`.

Эти тесты существуют в проверенном source, но не исполнены выбранными 20/25 receipts. Это `verification_missing`, не указание писать их заново. Дополнительно нужны прямые malformed checkpoint и checksum-free legacy manifest cases, а также interrupted-stage retry → успешный persisted recovery. Existing malformed publish-coverage test не заменяет malformed stage state.

Для каждого случая показать disposition: skip, rerun, historical-only или unavailable. Не вводить четыре новых product enum только ради отчёта: сначала использовать существующие owner return/event/error semantics и показать различие в реальном consumer. Если наружу они сейчас сливаются, исправить минимальный owner/consumer boundary. Отдельно объяснить старое `required_outputs=[]` fallback поведение и выбранную миграцию: новое explicit-empty правило не должно молча переинтерпретировать старый caller.

После этой матрицы G решает LA-041 по существу; авторское `closure_ids=[]` само по себе не является причиной отказать в закрытии.

## G27-04 — I4: принятый bridge не закрывает чужие исходные свойства

Catalog request→profile→fresh reader и отказ неверного профиля доказаны на `8a24cc8`. Legal real-encoder/direct HTTP/fresh-reader evidence остаётся на `567c38cc98f74a5cea7c814dc5099d250d38f072`; selected producer/reader/provider blocks совпадают с более новым source, но это не whole-process equality: Core/IR/container изменялись. На новой композиции назначать affected direct-path recheck по фактическим зависимостям, не повторять весь Legal набор только из-за изменения номера HEAD.

LA-040 имеет content/encoder/projection/membership implementation и значительную historical test matrix. Остаток — прямой **legacy flat NPZ/HNSW без selector**: при изменении текста того же ID old vector не должен стать current reuse; encode должен исполниться, новая generation должна связать текущие basis/membership. Сохранить legitimate append-only reuse, withdrawal, exact row→vector identity и историю. Дефицит этой проверки — `verification_missing`, а не `producer_missing`. Не скачивать модель заново, если для этого migration predicate достаточно уже допущенного детерминированного encoder fixture; real-encoder receipt остаётся отдельным свидетельством.

LA-028 (единый registry/seed selection), LA-032 (единый demographic layout/inventory), LA-033 (replay compatibility migration), обе occurrences LA-046 (явный versioned compiler context и полный query/role discriminator) не закрываются Catalog/Legal profile checks. Точные маршруты сохранены в `decisions.json`. Дополнительное требование N7→WMR относится к смежному acquisition flow и не подменяет одинаковый исходный текст двух LA-046 occurrences.

## G27-05 — R4 / B56: исправление знаменателя и честная граница lease

**G принимает исходный B56 на source-qualified configured witness.** Исходный criterion допускает общий outer permit и serial folds внутри каждого admitted job. Production workload и inner-fold parallel fanout не являются prerequisites.

Авторское утверждение «12 fold/repeat units per study» неверно: `3 folds × 2 repeats = 6` на study, **12 суммарно для двух studies**. Во всех трёх profiles один полный roster; cap 1/2 сохраняют numerical outputs, result refs и consumer-semantic evidence. Raw evidence refs/bytes различаются из-за фактических cost/time; это корректно и не выдаётся за byte equality. Настоящий remove-bridge control при cap 1 достигает dispatch peak 2. Здесь G исправляет интерпретацию; неизменяемые исходные outputs не редактируются и новый numerical run ради арифметики не нужен.

Отдельный наблюдённый residual: cap-1 stdout содержит два `RuntimeDependencyUnavailableError` для `control_plane_store.renew_job_lease`; heartbeat прекращается при недоступности store. Записанные jobs завершились раньше 60-second lease, с полным roster и без потерь. Поэтому этот receipt не доказывает отсутствие starvation/expired-lease retry при более долгой насыщенной нагрузке. Это **не продуктовый B56 FAIL данного run** и не доказательство inherited red.

Следующий владелец — Runtime control worker / shared executor. Проверить длительный cap-1 compute вместе с обязательным lease/control I/O: renewal, cancellation, expiry/fencing и фактический terminal ownership. При дефекте выделить control-plane service capacity в существующем owner либо иной обоснованный механизм, не выдавая денежный ledger за compute permit и не создавая второй scheduler без необходимости. Candidate witness измеряет dispatch, а не весь интервал materialization→persistence; более широкую AD-E02-02 capability принимать отдельно.

## G27-06 — R2: provenance и граница переноса

B87/B89 удовлетворены на `65ac853e2735e827e27688a6175f1a385901e20e`: физическое закрытие/повторяемое cleanup ownership, exactly-once permit, stream recovery и свежий CAS/cursor consumer. G нашёл ноль R2-scoped source blockers и отдельно повторил две новые race-проверки.

Четыре entries `f29d85e…`, `e46cb5c…`, `07bbb61…`, `1eb32f0…` из `implementation.historical_commits` не являются ancestors candidate. Это **related history refs**, не выбранные зависимости; фактический current source проверен по пяти pinned path hashes. Исправить README-формулировку о «своих исходных commits», не выдавая эти четыре refs за candidate lineage. Это documentation/provenance caveat, не опровержение прошедшего defining property.

## G27-07 — Integration: выбрать реальный состав, не переносить флаг

Все семь receipt commits отсутствуют в G ancestry. В проверенных packet path sets против G: R2 — 12 отличаются / 4 отсутствуют / 1 одинаков; I1 — 15 / 0 / 3; R4 — 3 / 2 / 2; I4 — 6 / 4 / 1; V6 — 5 / 0 / 1. Это scoped path comparisons, не полный dependency closure.

Нельзя взять test-only `65ac853` отдельно и считать R2 интегрированным: он использует отсутствующие в G ownership механизмы. Нельзя считать docs-only receipt переносом реализации. Нельзя сливать всю ветку с ещё не принятыми задачами под видом этой партии.

Базовый путь — вести накопительную приёмку на единой авторской lineage: сохранять уже принятые source-qualified свойства, учитывать последующие affected deltas и выбирать для merge полностью рассмотренную композицию. Не поручать исполнителю второй порт каждого пакета на старый G и не дублировать реализацию. Минимальный следующий handoff: один выбранный source boundary с полным перечислением механизмов, imports/config/build/public companions и исходных provenance refs; отдельно список уже принятых свойств и ещё непроверенных изменений того же delta. Для каждого реально переносимого commit G проверяет весь его footprint и ещё не рассмотренную импортируемую ancestry, а не только 37 упомянутых пакетами refs. Естественно отделимый законченный commit может пройти раньше общего состава. Если mixed commits такого slice не образуют, выбрать composition boundary с G и canonical writer; не выполнять partial cherry-pick или декоративный merge, который скрывает неперенесённый код из ancestry. Не менять main, историю и чужую текущую работу.

После состава: перенести законченную группу append-only, затем повторить **affected defining-property/consumer** checks на новом G head. Полная дорогая E02 wave остаётся после общего freeze. BOOT0/T1 и исправления документации не зависят от этой вычислительной волны; незатронутые доказательства не обнуляются.
