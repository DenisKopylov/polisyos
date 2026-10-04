# Как обновлять предложение

[Обзор](README.md) · [Источники](sources.md) · [Каталог](catalogue.json)

## Статус документа

Это изолированный исследовательский комплект. Он не заменяет GY, Atlas, DEBT-REGISTER, E02, ADR, действующие контракты или owner decisions. Аналитический ID с префиксом DEV программы, пакета или связи не является официальным task ID и не разрешает реализацию.

## Единицы обновления

Обновлять следует утверждение, source version, конкретный program increment и его затронутые связи. Не переписывать весь портфель после каждого нового PASS. Закрытие узкой E02-карточки меняет ровно потребляемый repair output; не обязательно scientific suitability, deployment, human usefulness или institutional authority.

1. Сохранить новый source path, hash, observation time и точный диапазон/selector. Stable HEAD недостаточен при dirty edits
2. Определить тип нового сведения: ruling, source observation, historical receipt, fresh execution, independent scientific evidence, actual consumer или permitted authority
3. Указать supersedes только для того утверждения, которое действительно заменено. Новое evidence не становится новым principal ruling
4. Обновить observed baseline отдельно от development scenario. Исторические сведения остаются в provenance
5. Удалить из будущей сметы работу, оказавшуюся уже выполненной; при исчезновении reuse premise приостановить либо пересчитать только затронутый диапазон
6. Проверить границы первого приращения, проверки переноса и зрелой способности, конкретный consumer и условия остановки. Новый метод не требует новой программы автоматически
7. Сверить все machine-readable ссылки и отдельные знаменатели, затем прочитать обзор как самостоятельный ответ

## Когда менять границу программы

Выделять ветвь, если у неё появились самостоятельный повторяемый outcome/consumer, отличающаяся scientific/behavioral acceptance, свой data cadence и upkeep, а общая программа скрывает важные решения. Например, forecasting с отдельными vintages и rolling horizon или market design с собственными actors/messages/equilibrium witnesses.

Объединять, если две траектории всё время меняют один и тот же объект, проходят одну совместную проверку и не дают автономного результата. Но общий serializer или repository package недостаточны. Scientific adequacy и human comprehension, либо custody и causal identification, нельзя объединить одним PASS ради удобства.

Вынести работу в общее условие можно, если она действительно нужна нескольким outcomes и имеет existing owner. Это не означает нулевую цену и не требует новой платформы. У shared cost должен остаться один unique work node и названные consumers.

## Состав машиночитаемого комплекта

- `catalogue.json`: выбранная иерархия, программы, условные и прикладные ветви, альтернативы и ссылки на карточки
- `decisions.json`: принятые направления, аналитические рекомендации, 25 E02 families, 13 P118 cards и отдельный LA055 scope
- `dependencies.json`: типизированные входы, общие активы, положительное повторное использование, комплементы, обратные связи и вредные связи
- `effort.json`: точные bounded scopes, D/A/B/I/V, условность и история приостановленных/снятых оценок; нет суммы всех опций
- `source_disposition.json`: отдельные исходные популяции и их аналитическая судьба с сохранённым source standing
- `sources.json`: канонические пути, versions/hashes, точные reading modes и ограничения evidence
- `validation.json`: проверка структуры **этого комплекта**, не результат тестов PolicyOS

Текстовые карточки являются авторским изложением. При изменении каталога и Markdown следует сверять одноимённые поля одновременно; validator не решает смысловой спор и не доказывает научное утверждение.

## Контроль полноты

Не складывать 54 GV, 77 GY, 22 Atlas, 277 debt rows, восемь data requirements, 366 planning Markdown, 182 Foundry research IDs и 169 phase pointers. Исторический повтор Refinement или Addition не становится новой независимой способностью. Source-qualified IDs предотвращают столкновение старого E2, текущего E02 и одинаковых номеров разных планов.

File inventory completeness не означает full reading. Full reading не означает scientific revalidation. Declared implementation не означает actual default consumer, а actual consumer не означает правильность исходных предпосылок. Эти ограничения не стираются после machine validation.

## Перед окончательной передачей

Первый утренний reported-local срез 03:46–03:52 UTC и заключительная ограниченная сверка 05:01:10–05:01:44 учтены. Последняя сообщает HEAD `8b40f8f5`, отдельно проверенное clean tree, все 282 ID/status без переходов и точные изменённые области. Bounded freshness gate завершён для этого среза. Он не означает проверки всего текущего корпуса или состояния после 05:01:44. Прежним source records не приписано новое observation time; совпадение пяти документов, трёх receipts и пяти code owners записано отдельным сравнением.

`validation.json` фиксирует проверку готового содержательного комплекта до размещения. Поэтому `repository_transfer_verified=false` описывает только границу этой проверки и не делает исследовательские выводы предварительными. Размещение в изолированном repository docs subtree проверяется отдельно по точным hashes этих файлов и внутренним ссылкам; результат сохраняется отдельной placement receipt без изменения уже проверенного комплекта. Официальные планы, статусы, контракты, код и процессы E02 этим комплектом не меняются.

## Что не превращать в постоянное обязательство

Не возобновлять retired migration/cleanup только по старому checkbox или архивной дате. Не запускать все conditional branches ради полноты каталога. Не делать внешний акт, runtime appointment или protected publication универсальным prerequisite candidate research. Не ослаблять явно выбранный protected mode под видом более дешёвой демонстрации.

## Значение схемы источников

В source_disposition.v3 E02-записи сохраняют materialized исторический ledger со своим статусом и unresolved premise; текущая reported-local overlay отделена от него. repair_output_baseline означает условное повторное использование принятого выхода существующего repair owner. premise_resolution_assumed=false запрещает читать этот сценарий как принятое principal/owner решение, назначение владельца или допуск данных. B122, LA-055 и B31 сохраняют свои отдельные decision references.

В sources.v3 исторический массив sources содержит514materialized представлений; отдельный reported_current_sources содержит22local-report records, из которых19 имеют reported hashes, а3 — только paths/selectors. Сохранены18прежних записей и добавлены четыре новые версии финального среза. Эти22не засчитываются как source bytes, rehashed здесь. Поле sha256 относится к явно указанному hash_scope. Полный retained manifest, numbered source excerpt и transcription Parquet footer имеют разные границы: hash выдержки не является hash всего исходного файла. Source aliases имеют namespace и точную версию; archive_data:DR означает DEBT-REGISTER, а DR в реестре решений означает DECISION_RECORDS. Старые locators не переназначаются автоматически на последнюю версию.

Current reported hash, materialized historical hash и hash самого readback report — разные свидетельства. Сообщённые31changed B197 selectors не дают права восстановить новые literal values полного ledger. Финальный B61 ledger уже supersedes старый v2 blocker; прежняя строка сохраняется только в исторической materialized копии. B152/B154/B155 имеют сообщённое уточнение owner scope без appointments. Утренний frozen producer census на28ea3bb не переименовывается в полный census на8b40f8f5. Неизменённый FINAL_REPORT хранит свой старый R9 cut; новая integration подтверждается отдельным source/receipt observation.
