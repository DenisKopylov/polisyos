# F35: независимый разбор и решение G о следующей работе

Проверен весь пакет F: **17 bundles / 35 IDs / 36 исходных criterion bindings**. Независимые разборы поддерживают 33 рекомендации по ограниченным исходным свойствам; B214 и B56 остаются limited. Это оценка свидетельств: **новых formal closures G — 0, новых принятых runtime commits — 0**. Найден отдельный исправимый F-owned escape в той же группе B214: допустимый MGraph проходит реальный producer → Node → CAS, теряя graph type и ломая missingness consumer.

Immutable head PR65 — `25cdea9064ddea2c3a812fd68670076bd4b088cb`, tree `ed4a4fd6864e8b60cb45124fb8e6fa9b7c503b66`. Измеренный product source — `519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82`, tree `750d28da94f372848fe6b2db5f88db95b94cb57d`. После прежнего root cdf изменены 1228 documentation paths, product delta — 0. Source 519 не является предком integration checkpoint c75. Original criteria привязаны к published main `198076863e143dea9f89f02734b13d50dae3eed5`.

[Все 35 решений](all-35.md) и [машинные pins/карточки/остатки](decisions.json) сохраняют полный denominator. Подробные независимые reviews: [11 estimator criteria](estimators.md), [11 GCM/graph criteria](GCM.md), [11 migrations](migrations.md), [B214](B214.md), [B56](B56.md). Полные авторские deciding refs остаются в `implementation-handoffs/F/continuation-transfer-20261007/per-ID/<ID>.json@25cdea9064ddea2c3a812fd68670076bd4b088cb`; код и tracked outputs повторно не копируются.

## Два крупных остатка: отложить общую реализацию, сохранить конкретный trigger

**B214 — совместное решение A/C/F о partial-graph semantics.** Сначала переиспользовать существующие CPDAG/PAG/ID consumers. Контракт должен различать результат, одинаковый для допустимого семейства графов, условный candidate, typed limitation/refusal и authority-grade identification. Одна произвольная DAG completion не получает authority. До решения частичный граф сохраняется; DAG-only consumer честно отказывает неподдержанному профилю. Общий новый identification engine сейчас F не назначается. Trigger: tracked решение canonical identification owner с допустимым graph family/query profile и правилами проекции в A, затем discriminator, где эффект различается между допустимыми completions. Не требовать отказа для всех partial graphs навсегда.

**B56 — общий Runtime/Scientist admission и измеренный workload.** F уже исполняет все folds/repeats последовательно внутри admitted job; тест показывает реальную очередь одного созданного pool, но не canonical Runtime admission нескольких studies. Сначала связать существующий worker-slot cap с фактическим `RunLifecycle → run_experiment → sync_run_causal_full`; денежный ledger не становится CPU permit. Если общий pool реально охватывает конкурирующие jobs, переиспользовать его. Межпроцессный permit нужен только при доказанном разрыве этого scope. Trigger: source-bound пакет Runtime/Scientist owner с admission unit/cap, полным roster jobs/folds/repeats/seeds, runnable profile и input refs; G измеряет active peak, wait, wall/RSS, сохранность всех folds и CAS provenance. Синтетический достаточный input допустим для общего свойства; production read-only refs нужны только для конкретного data-dependent критерия. Данные в cloud не переносятся.

## Узкая работа F сейчас

[Continuation prompt](../../../execution-prompts/continuation-2026-10-07/F-resume-after-25c-focused.md) задаёт один runtime repair и небольшие evidence/companion задачи. [Native MGraph witness](native-MGraph/README.md) подтверждает type erasure; DAG/ADMG controls проходят. Это P40 static-profile admission class на уровне типа графа. Нужен canonical profile guard или полное сохранение MGraph semantics, а не новый finding ID или серия исправлений каждого имени.

Также остаются: B204 benchmark с двумя pre-periods не должен требовать успешный pre-trend test; changed DoWhy worker test требует точечного exact-source запуска; B218 needs explicit status supersession; LA-037 — finite docs/shim alignment. Два layout paths сами по себе не означают два алгоритма: primary facade и same-object alias обходят прежнюю двухступенчатую зависимость. Не назначать LA-035 новое normative/optimizer approval для неизменённой исторической функции.

## Исправление прежнего G installed вывода

Current source 519 имеет **91 PASS wheel и 91 PASS rebuilt-sdist**: в каждом 79 maintained graph cases и 12 installed catalog cases, включая шесть actual consumers. Origin checks и resource bytes bound. Отдельный fresh-child witness — wheel-only. Прежний twelfth-wave вывод о полном отсутствии current installed graph/catalog evidence был слишком широк; operative reviews исправлены. Не повторять эти 91 неизменившихся checks ради новой упаковки receipts. Они не проверяют ещё не собранный G source и не дают policy authority.

Scanner остаётся ERROR/-9 в двух попытках, Ruff FAIL103, public-surface FAIL38; P41 — not_established. Это сохраняется как отдельный quality/input residual, без заявления inherited и без замены исходного конечного критерия условием «весь продукт зелёный». Общий G replay выполняется один раз после accepted source freeze и independent reviews. Main не публикуется.

## Pattern и custody pass

P14/P29: математический oracle, runtime witness, installed checks и formal closure различаются. P35: все 35/36 bindings проверены, summaries не задают ownership. P37/P38: тестовый pool cap не является actual study admission; edge marks не устанавливают graph-type semantics. P27/P31/P40: repair у canonical producer, общий supported-profile invariant, shared-helper/global refactor не назначается. P41: происхождение красных gates без полного base/input proof остаётся неизвестным. Actual importer `--check` PASS и полный verification.json прочитан до использования results; hash указан в decisions.json.

[Storage receipt](storage/README.md): три завершённых source-copy leaves перенесены в native Trash после сохранения receipts; 185757696 allocated bytes nominally. Корзина не очищалась. Это перенос, не утверждение о восстановленном физическом месте.
