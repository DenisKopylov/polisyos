# Полный исходный объём и правила сверки

Это карта исходных обязательств, а не оценка процента готовности. Знаменатели разного рода не складываются: finding, задача, поверхность, источник и adversarial scenario обозначают разные сущности.

| Источник | Полный знаменатель | Текущее документарное состояние | Следующее действие |
|---|---:|---|---|
| GY §8.5 | 77 задач | 55 executed, 15 not_started, 5 blocked, 2 not_executed; у 14 executed не измерена полная конъюнкция | 22 невыполненных + 14 точных residual predicates; выполненные механизмы сохранить |
| Atlas | 22 DS slices | DS12/13/14/21 planned; DS16 grammar и ряд частичных/перенесённых обязательств | Читать актуальный owning slice и поздние уточнения, а не только обзорную таблицу |
| Debt A–G | 277 уникальных ID | 191 closed, 44 open, 32 blocked, 4 folded, 6 foreign | Все 86 nonclosed имеют маршрут; 76 open/blocked требуют фактического результата/решения |
| R9 | 26 families / 103 grounds / 197 source records | Финальная исследовательская редакция; runtime UNRUN | Реализовать механизм и case-selected evidence, не объявлять каталог admissible corpus |

[Источники](sources.json) привязывают исходные blobs и отличие E02 candidate от G. [GY JSON](gy-inventory.json), [Atlas JSON](atlas-inventory.json), [Debt JSON](debt-inventory.json) сохраняют исходный статус и адресуют новые work IDs. Atlas JSON включает 68 записей разных типов; это не 68 DS slices. Сценарии R9 перечислены отдельно в [r9-obligations.json](r9-obligations.json).

**Смысл повторного исполнения.** Строка может иметь старый заголовок «producer missing», свежий receipt готового producer и всё ещё open из-за другого условия. Исполнять надо текущий неудовлетворённый predicate. Полная строка реестра важнее первых предложений. Closed_by и зачёркнутые ID сохраняют семантику canonical parser; это не новые open задачи. Folded указывает на successor и не создаёт повторного writer. Foreign указывает на другого владельца, но не означает done.

**После E02.** P0-REBIND делает diff исходных документов и затронутых code/test/consumer families с принятой версией. Если E02 уже устранил residual, сохранить source-qualified proof и запросить соответствующий owner disposition. Если изменились interface/semantics, обновить затронутые tasks, reviewers и scenarios; не пересчитывать закрытые независимые цепи. Непринятый candidate не становится baseline по времени последнего commit.

**First-use.** Каждое исходное незакрытое обязательство должно быть выполнено и принято либо явно закрыто компетентным владельцем. Назвать его «не относящимся к выбранному профилю» недостаточно. Ускоренный запуск с отложенной обязательной работой требует отдельного решения пользователя.

Независимый документарный пересчёт и проверки связности приведены в [validation receipt](../assurance/document-validation.json). Они не заменяют продуктовые проверки.

[Дополнительный Atlas crosswalk](atlas-auxiliary-obligations.json) отдельно перечисляет все 2 subunits, 60 supplemental findings и 23 seeded-negative lifecycle records. Они не входят в 261 основной entry и не означают 85 новых реализаций: repaired/deleted сохраняются, stale-open строки требуют сверки с поздним owning receipt, отрицательные сценарии требуют собственного исполнения. Исторические признаки debt представлены как `source_extracted_capability_gap_labels`; они извлечены из полной старой строки и не являются текущим dispatch predicate. Текущий остаток определяется `remaining_property` и accepted-source P0.
