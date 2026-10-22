# Остаточные долги: классы ремонта и межпоточные обязательства

Полный routing всех 86 nonclosed ID находится в [debt inventory](../inventory/debt-inventory.json), конкретные DEB-01–14 — в [task manifest](../tasks.json). Номер DEB обозначает класс работ, а не закрытие всех связанных debts одним commit. Исходные closure predicates не заменяются общим названием.

## Инструменты и воспроизводимость — DEB-01–04

**DEB-01** исправляет доказательство отсутствия. Для каждого инструмента устанавливаются полный input denominator (roots, file types, generated/excluded scope), predicate и handling unreadable. Census должен включать фактические executable callers, а не только заранее выбранные tooling folders. Сначала проверить, что E02 уже исправил trust-posture literal census; повторно не применять старое total. Генерический scanner проверяется реальным вне прежнего root инструментом и изменением predicate при сохранённых маркерах. Inventory/source IDs и компаньоны обновляет тот же writer.

**DEB-02** связывает semantic config budget и source/lock-bound OpenAPI. Перенос большого конфигурационного блока в соседний файл не является уменьшением механизма. Изменение окружения без изменения admitted source не должно менять contract identity; изменение действительной семантики должно. Native generator и consumer snapshots обновляются вместе. Не делать blanket snapshot refresh, скрывающий nondeterminism.

**DEB-03** закрывает только остаточную public/private boundary после E02. Определить полный набор actual callers, публичный owner и release inventory. Canonical public extension предпочтительнее шима; удаление private import без функционального successor не решение. Финальный сигнал — прежний consumer работает через public contract, а sibling bypass обнаруживается. API break оформляется как break с миграцией, а не нейтральный lint fix.

**DEB-04** разделяет isolated test defect и production defect. В частности, sys.modules replacement не может заражать соседний consumer; отсутствие catalog в checkout не равно допустимой runtime absence; unresolved discriminant bytes не заменяются удобной fixture. Контроль должен пережить порядок тестов и реальное удаление входа. P41 проверяется от slice base с полным input denominator; без replay происхождение red остаётся not_established.

## Native semantics — DEB-05–08 и DEB-12

**DEB-05:** retained schema и calibration version проверяются на выходе настоящего producer и fresh downstream reader. Различать malformed/unreadable/empty; не обходить строгость broad extra fields. Default обязан принадлежать собственной domain grammar либо перестать быть default через явную миграцию. Owner каждого schema остаётся прежним.

**DEB-06:** поздние merged generations, reissue и current-decision lineage потребляют общий LIF-02. Некоторые adapters/producers уже существуют; сначала выделить остающийся exact composition и appointments. Не переводить programmer error, чужую lineage и допустимый unavailable в один отказ. Проверка должна отличать unrelated branch merge, stale head и новый действительный decision.

**DEB-07:** unresolved vocabulary — содержательная работа. Прочитать ratified INT-R2 и actual consumer, определить unit/estimand/ceiling comparability и соответствующее направление ограничения. Нельзя превратить неизвестное сравнение в scalar ranking или enum. Для каждого CORR destination установить owner, producer и bridge; закрытая VC1 не переоткрывается. Если решение меняет ratified смысл, подготовить узкий G choice с альтернативами, не молчаливый code rewrite.

**DEB-08:** GY-GAP2/3/5/6 и DS15 evidence используют один полный production population и его typed denominator. Fixture не попадает в числитель. Повторные просмотры и управляемые выборы не превращаются в независимые evidence. INT-R9 остаётся отдельным протоколом первой promotion; численный sequence-level risk claim без его предпосылок запрещён. Свежий controlled transcript должен доходить до consumer movement, а не только содержать правильные слова.

**DEB-12:** flat-manifest residual сначала ограниченно трассируется через всех reachable consumers. После этого выбрать один requirements owner, перенести reader и закрыть legacy только после proving no live bypass. Не удалять путь по отсутствию в sampled search. Если реальный fallback нужен, versioned compatibility остаётся явной.

## Подлинные authority inputs — DEB-09

Appointment, mandate, policy signer, history holder и независимая competence — разные slots. Уже реализованные intake и verifier не строятся заново. Исполнитель обязан проверить доступные owner records и разрешённые каналы, подготовить точный минимальный запрос и рабочие typed refusals; он не может сам назначить внешнюю институцию, сделать self-sign или объявить существующее письмо достаточным вне его scope/time. Несколько связанных slots могут готовиться параллельно, но независимость источника и reviewer сохраняется. Технический owner получает admission/consumer delta; настоящий факт остаётся у его компетентного issuer.

## Human/operational surfaces — DEB-10–11

**DEB-10:** C13 print capture и часть migration уже выполнены. Остаток определяется поздним versioned DS18 reconciliation и independent countersign, а не повторной генерацией старого PDF. Freeze content/source/browser/render profile, получить требуемое независимое свидетельство и довести его до surface. Старый receipt не подтверждает новый текст; отсутствие внешнего countersign не делает внутреннюю accessibility engineering невозможной.

**DEB-11:** foreign connector cleanup и worktree tooling сохраняют исходные acceptance signals. Aiohttp/session lifecycle проверить через настоящий cancellation/error/normal path; fresh worktree должен использовать intended source, а не другой editable install. DS20-B CAS, PG linearizability, scorecard и Helm mirror имеют отдельные UI/OPS writers; их нельзя закрыть вместе с этими двумя foreign items.

## Сведение, миграции, ограничения

Новый task manifest управляет назначениями; canonical DEBT-REGISTER остаётся владельцем статусов. Сначала accepted mechanism и его consumers, затем отдельное source-qualified disposition каждого исходного ID. Не переписывать исторические closures и не добавлять массовый новый registry. Mandatory report/test/generated companions входят в deliverable, но не в искусственный лимит mechanism paths. General rollback: compatible source/config может быть восстановлен append-only, действительное решение revoke/currentness не откатывается вместе с бинарником.

Pattern pass: P06/P07/P10, P27/P29/P31–P41. Acceptance — закрывается текущая смысловая граница; remove-the-property-keep-the-markers отрицательная проверка отличает новый механизм от красивой записи в реестре. Все будущие runtime signals сейчас UNRUN.

## Newly separated semantic assignments — DEB-13/14 and UI-20

**DEB-13 — numeric VOI granularity.** The original DS15 metric debt is not acquisition-cost admission or INT-R2 vocabulary. Resolve its owner decision/ranking reference, measure/population/horizon/estimand, expected-value and expected-cost inputs. Research alternative laws and submit a precise G choice if authority/meaning changes; implement only the chosen native mechanism and real consumer. Unsupported inputs retain the existing refusal. UI-17 projects the result and does not own its mathematics.

**DEB-14 — scope-adjudication chain.** Extend the existing candidate artifact into the owed purpose-scoped ruling producer, resolver, persistence, claim-lifecycle admission/replay and governed surface under the ratified one-plane four-way rule. Candidate authority_effect=none is correct but not terminal. DEB-14 owns the producer adapter; LIF-02 owns common head/lifecycle mutation, UI-19 the permitted projection. This internal mechanism must not be blocked as a missing external appointment.

**UI-20** owns the exact remaining DS5 promotion-union/private-issuer property through its canonical generator/consumer; other successors retain their allocation. Two DS8 rows are instead scope/signal reconciliation at P0, not publication-build closure. Trust Center/Docs IA remains an Atlas-versus-marketing allocation decision before affected implementation.

**DEB-01 runner boundary:** retain the original intake-only attestation. Re-run the transitive executable mutation falsifier after runner changes with the complete current denominator. Missing out-of-band runner identity is a bounded residual; a local self-hash is not an independent replacement, and this plan does not silently commission external attestation infrastructure. Stronger claims require a concrete separate decision; the original row is not closed by truthful disclosure.

`source_extracted_capability_gap_labels` in the inventory are explicitly historical full-row phrases. The current remaining_property and accepted-source rebind govern dispatch; those labels cannot reopen an already built producer.
