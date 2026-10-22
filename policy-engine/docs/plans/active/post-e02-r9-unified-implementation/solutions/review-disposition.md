# R13: исследование, независимые атаки и самостоятельное review

**Статус:** документация для будущего исполнения. Product execution UNRUN, E02 acceptance не установлена этим пакетом. SDD, исходные GY/Atlas/debt статусы и runtime code не менялись.

## Полный охват

12 прямых исследовательских помощников подготовили непересекающиеся группы: CAP6, custody5, lineage4, GY core18, GY learning8, verification7, Atlas public8, Atlas data12, foundations9, operations12, debt14, execution6. Итого **109** task IDs. Шесть других прямых помощников атаковали эти решения: capture/custody11, lineage/operations16, GY26, Atlas20, foundations/debt23, verification/execution13. Итого снова **109**, без пропуска или двойного зачёта. Дочерних агентов не было; product tests, builds, installs и production-data reads не запускались.

В [источниках](sources.json) **185 source records**: 168 внешних ссылок с 156 уникальными URL и 17 ссылок на локальные canonical документы/код. Один URL может поддерживать несколько разных узких утверждений; это не 185 независимых исследований. Среди рассмотренных механизмов — HTTP/caching/change feeds, DCAT/PROV/ODRL, Iceberg/transactional heads, distributed consistency, durable effects, resource enforcement, TUF/SLSA, PostgreSQL, metrics cardinality, selective/online inference, causal transport, decision-theoretic VOI, accessibility и API compatibility. Каждая запись содержит поддерживаемое утверждение и предел переноса. Никакой внешний проект не объявлен доказательством корректности PolicyOS.

Root собрал рекомендации, разрешил противоречия, проверил source-bound anchors и выполнил заключительное [содержательное review каждой задачи](root-review.md). [Машинный review](root-review.json) связывает каждую из109 строк с точным хешем reviewed solution. Это самостоятельная проверка автора документации; будущий implementation author всё равно нуждается в независимом review своего кода.

## Что исправлено

42 первоначальных наблюдения ниже — число записей review, **не** число независимых классов дефектов или runtime findings. Повторяющиеся случаи internal-input-as-external, candidate-as-authority и недостаточного exact binding сведены к общим правилам. Дельта-review выполнялось только на изменённых distinctions; исходные результаты и границы каждой проверки сохранены.

| Review | Первоначальные записи | Исправление и окончательная граница |
|---|---:|---|
| [RCC-01–09](reviews/r13-red-capture-custody.md) | 9 | Raw storage только при разрешённом profile и до materialization; query-only result/receipt; private query binding; lawful-basis OR; no-hit после admitted search; authorized CDN; idempotent overlap; second-source slice; один LIF-05 seam; отсутствовавшие index/registries доставлены. [Delta](reviews/delta-red-capture-custody.md), [final](reviews/final-delta-capture.md). |
| [RLO-01–08](reviews/red-lineage-ops.md) | 8 | LIF-06 admission и OPS-08 host adapter; физический reserve; полный retained-reader denominator; один provider-budget owner; remote conformance без искусственного vertical-exhaustion барьера; scoped concurrency; source currentness; API-specific preconditions. [Delta](reviews/delta-red-lineage-ops.md). |
| [RGY-01–06](reviews/red-gy.md) | 6 | Не переоткрывать принятые ADR; internal work остаётся работой; AS2 comparator конкретизирован как proposal, original criterion не закрыт; WP-01/02 no mutation; optional O2→O1→O3 путь; multi-object recovery. [Delta](reviews/delta-red-gy.md). |
| [Atlas 1–8](reviews/red-atlas.md) | 8 | PR1a/PR1b разделены; real PG не обязан быть cloud; FAIL не environment block; UI не writer world; gross/net VOI; actual-page accessibility; interface-stage preparation; raw-byte parity и version-pinned citations. [Delta](reviews/delta-red-atlas.md), [final](reviews/final-delta-atlas.md). |
| [Foundations/debt N1–N5](reviews/red-foundations-debt.md) | 5 | 26-family grammar отдельно от case acquisition; runtime candidate formulation и hypothetical weights; известные connector/tooling criteria не запрашиваются заново; finite EVSI/gross-net split; jurisdiction/access-level. [Delta](reviews/delta-red-foundations-debt.md), [final](reviews/final-delta-foundations-debt.md). |
| [RXE-01–06](reviews/red-verification-execution.md) | 6 | Rule/schema/upstream identities в каждом shard; reviewer identity separation; internal/external distinction; P40 с проверкой отсутствия closing capability; exact post-N13b terminal/no epoch; source-derived expected artifact×validator relation. [Delta](reviews/delta-red-verification-execution.md), [final](reviews/final-delta-verification-execution.md). |

Все указанные противоречия документации разрешены. Это не означает, что источники уже доступны, нормативные вопросы приняты или будущий продукт прошёл проверку. **AS2 operational interpretation остаётся предложением; WP activation остаётся необходимым реальным решением.** Их точные варианты, рекомендация, rejected alternative, activation inputs и допустимая независимая работа изложены в [decision-clarifications](decision-clarifications.md). SDD не изменены.

## Собственная проверка root сверх red-team

Root дополнительно проверил последовательность этапов, сохранение всех исходных obligations и условий free-grow; исправил dependent references в tasks/workstreams/executive, а не только карточки. Подготовка по согласованному интерфейсу не требует полного producer completion. Composed acceptance требует реального producer. Один worker — начальная rehearsal настройка; metrics и permits не заменяют физические ограничения. Симуляция, exact joint witness и inference plurality сохраняют конкретные предпосылки и разные гарантии.

Выбран минимальный общий путь: расширять native owners, immutable permitted representations и conditional heads; использовать настоящую транзакцию там, где она охватывает effect, иначе durable intent/reconcile/quarantine; хранить только разрешённые bytes/results/receipts; проверять rights/currentness для каждого use; проецировать owner records в UI. Incremental cache/lineage, новый remote backend и более сложный numerical profile включаются по доказанной необходимости, а не ради технологической новизны.

Обоснованное инженерное отклонение допускается без повторного абстрактного согласования: exact observation, сохраняемый predicate, сравнённые варианты, ресурсы/миграция, consumers и distinguishing test. Изменение исходного нормативного смысла проходит компетентное согласование.

## Сохранение и пределы

[review-receipts.json](review-receipts.json) содержит hashes полных deciding review outputs. Исходные промежуточные предложения retained local ignored; их окончательная содержательная редакция находится в portable task cards и preferred-solutions.json. Исторические review line numbers относятся к версии, читавшейся reviewer; точные task ID/field anchors и цитируемые counterexamples сохраняют смысл после render.

[validation.json](validation.json) фиксирует только лёгкие проверки документации, полного покрытия, ссылок, source paths и неизменности исходных inventories/stage DAG. Продуктовые gates и тяжёлые hooks сознательно UNRUN по заданному ограничению ресурсов; отсутствие этих прогонов не называется PASS. Implementation acceptance, genuine external facts и измеренные performance claims остаются будущей работой после E02.
