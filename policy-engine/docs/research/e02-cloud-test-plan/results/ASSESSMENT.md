# Оценка тестовой кампании E02

Кампания дала качественный исходный материал для архитектурного исследования и начала исправлений: переданы компактные строки всех назначенных ячеек, результаты привязаны к cut/cell/path, можно исследовать общие механизмы и готовить точечные discriminators. Финальная готовность E02 ещё не установлена: raw archives не переданы, backend/input/semantic gaps сохраняются, а критерии 282 findings требуют отдельного доказательства.

## Полный census, а не оценка по заголовкам

Источник расчёта — **все 2 074 строки `cells.tsv`**, Python test file×source-cut denominator, без retries и property/gate записей. В них 560 разных test paths; исторические cuts повторяют 482 из этих путей. Поэтому 2 074 наблюдения не являются 2 074 независимыми тестовыми файлами.

| Область | Cells | PASS | FAILED | ERROR | COLLECTION_SKIP | COLLECTION_ERROR | Доля PASS файлов |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Текущий cut · F01–F04 | 560 | 477 | 74 | 8 | 1 | 0 | 85.18% |
| Четыре исторических cut · F05–F15 | 1514 | 1196 | 233 | 80 | 4 | 1 | 79.00% |
| Все назначенные file×cut cells | 2074 | 1673 | 307 | 88 | 5 | 1 | 80.67% |

Текущий код исследован на `69780761ae091d8fcc6ab8778c7f5f7227eeef0b`. 477/560 PASS (85,18%) — хороший объём доступной регрессионной опоры для начала работы. 74 FAILED, 8 ERROR и 1 COLLECTION_SKIP указывают, где требуется triage. Это **не процент готовности E02**: один файл может содержать множество разных assertions, несколько failures могут иметь общий blocker, а PASS может не различать существенное нарушение свойства. Нельзя получить число дефектов или закрытых findings делением этих чисел.

История полезна для поиска изменений и проверки гипотез. Сравнение процентов между cuts не устанавливает улучшение качества: наборы файлов, profiles/inputs и полнота observer/receipt сведений различаются; P41 требует точного воспроизведения на правильной slice-base и полного input-denominator доказательства.

## Самые полезные сигналы

- **Чувствительность discriminator.** `F03-R1-removal`: expected target `failed`, observed target `passed`; normal/restored target тоже `passed` ([source line 275](received/F03.txt#L275), normalized `properties.tsv` + `extra_json`). В removal-клетке действительно упал **другой** тест (`test_cycle_substrate_context_job_v3_binds_wmr_v2_selected_views`, 1 failed call из 41, [normalized counts](properties.tsv#L3), [source line 417](received/F03.txt#L417)); обозначенный target остался зелёным. Это свидетельство иной проверки в файле, которое нельзя подставить за заявленный target discriminator. Сначала сверить mutation, реальный owner path и корректность target/criterion binding. У R6/R7 source сообщает ожидаемые target pass/fail/pass — полезные ограниченные controls, без автоматической product closure.
- **Producer/DTO seam.** F01-P012 сообщает `KeyError: 'const'` и отсутствие обязательного `historical_producer_availability.read_receipt` в projection packet. Это конкретный повод сверить producer, strict DTO, consumer и тестовый input, сохраняя custody rule; из сообщения нельзя выбрать виновником код или ожидание ([KeyError](received/F01.txt#L341), [read_receipt](received/F01.txt#L342)).
- **Status/refusal semantics.** F04-P012 сравнивает ожидаемый `promotion_reissue_historical_receipt_incomplete` с фактическим `promotion_history_payload_not_lossless`. Проверить, какой смысл должен применять gate, и смешанные исходы; простая смена ожидаемой строки без критерия недостаточна ([source line 415](received/F04.txt#L415)).
- **Generated/owner drift.** G04/G13/G14 сообщают OpenAPI, architecture/generated и owner/snapshot расхождения. Нужны targeted recomputation, canonical generator и семантическая проверка consumer; часть сообщений G14 повторяет G13, поэтому counts не складываются как независимые дефекты ([G04](received/F01.txt#L368), [G13](received/F04.txt#L130), [G14](received/F04.txt#L140)).
- **Общие blockers — гипотеза для группировки.** G10/G11 сообщают `owner_production_input_admission_not_established`; это не устанавливает недоступность самих inputs. В источнике также есть DuckDB FTS download failure. Часть красных результатов может группироваться вокруг этих ограничений; это вывод для triage, а не установленная причинная атрибуция. Проверка admission или исправление среды/fixtures может разблокировать несколько проверок, что нужно показать повторным запуском ([G10](received/F04.txt#L91), [G11](received/F04.txt#L104), [FTS](received/F04.txt#L398)).

## Что делать исполнителям

Параллельно: разбирать имеющиеся failures по owner/mechanism, искать реальный producer→artifact→consumer путь, проектировать независимые oracle и недостающие negative tests. Отдельные read-only leaf проверяют полный census/source binding, property target outcomes, gates и происхождение красного по P41; каждый возвращает полный относящийся знаменатель и `received/Fxx.txt:line` ссылки. Первым делом повторять **решающую клетку**, где старый вывод выбирает архитектурное решение, с полным deciding output на нужном SHA. Затем исправлять общий класс, проверять sibling consumers и передавать малые законченные slices G.

Четырнадцать gates по `gates.json`: 8 PASS, 3 FAILED, 2 UNRUN/environment_unavailable, 1 PARTIAL. G10/G11 требуют локальных owner inputs; G12 ещё не установил нужную полноту/currentness. Полная cloud-campaign coverage не делает эти gates зелёными. Production-dependent проверки выполняются локально только там, где они входят в criterion; generic mechanism проверяется достаточными bounded fixtures.

Новый полный baseline всех 15 машин сейчас не нужен. Во время исправлений нужны targeted reruns на candidate, новые discriminators и affected-consumer checks; общая дорогая волна — после freeze/reviews. Verdict о причине красного, independent raw receipt и closure finding остаются `not_established`, пока не получено соответствующее доказательство. P14/P29/P35/P37/P38/P41 определяют границы этой оценки.
