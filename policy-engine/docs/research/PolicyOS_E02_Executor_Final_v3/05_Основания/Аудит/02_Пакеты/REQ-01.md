# REQ-01 · Явные требования к данным и смысловая сохранность запроса

**Исходные IDs:** LA-045 и compiler-часть LA-046. Закрытие всей LA-046 включает ACQ-01.  
**Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace` · переоценка 31 октября 2026.  
**Основание:** [первый отчёт](../04_Проверки/REQ01_предыдущий_проход/Исходный_отчёт.md), его сохранённые excerpts/пробы/логи и дополнительное чтение архитектурного направления в этом выпуске. Нового исполнения compiler здесь нет.

[Исходный пакет](../05_Источники/E02_исходный_план.md#bundle-req-01), строки 303–501. Первое свидетельство не переписано; ниже уточнены его инженерная интерпретация и следующий содержательный остаток.

## 1. Что сохранить из выполненного ремонта

**Действующий владелец требований.** В первом проходе полностью прочитан compiler и facade: семь private functions и одна constant из точной LA-045-группы удалены; DataRequirementCompiler, активное извлечение constructs, injected resolver, hashing и reports остаются. Не нужно возвращать старые определения или строить новый compiler. [Текущий файл](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py); [installed проверка](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_req_01_installed.py#L1-L330).

**Явный предмет требования.** Непрозрачный scenario ID больше не определяет обязательный construct. Лексическое обнаружение темы остаётся candidate proposal, а явные constructs передаются отдельно. При этом не заявлена полноценная интерпретация отрицаний или полнота всех constructs. Исправление конкретного ложного обязательства не тождественно готовому универсальному пониманию текста. [Construct extraction и proposals](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L1120-L1340).

**Scope без украинского пилота по умолчанию.** Generic geography/periodicity больше не превращаются автоматически в UA/2022. Явный профиль сохраняет jurisdiction и interval. Исторический пилот не требуется удалять: его предпосылки должны быть объявлены. [Scope helpers](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L1320-L1365); [profile parser](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L1890-L2240).

**Передачу настоящих полей.** Adapter принимает `text` и `request`, не дописывает `annual` и не использует ID как содержание. N7 caller теперь передаёт text/domain/profile и resolver. Историческое утверждение, что весь handoff по-прежнему теряет эти поля, нельзя переносить на новый срез целиком. [Scenario adapter](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L2235-L2335); [N7 caller](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L10000-L10200).

**Честное отсутствие основания.** Отсутствующий resolver, неизвестная basis и пустой результат не должны стать доказательством отсутствия потребности или разрешением source authority. Сохраняются guards и ограничения роли family projections. Запись `consumer_asserted` не превращается в независимо установленное основание. Первый аудит рассматривал эти границы в compiler; полная downstream приёмка остаётся отдельной.

## 2. Подтверждённый содержательный остаток: domain alias

В предыдущих source-пробах на этом же commit `education_policy` превратился в `fiscal`, тогда как `education` сохранился. Такой alias уже встречается в существующем N7 handoff test. Сам test подменяет compiler на `_RecordingCompiler`, поэтому видит сохранённую входную строку, но не дальнейшую нормализацию настоящим получателем. [Нормализатор](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L2280-L2320); [N7 test](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_acq_01.py#L310-L385).

| Переданный домен | Наблюдавшееся поведение excerpt-пробы | Смысл |
|---|---|---|
| `education` | `education` | Положительный canonical control |
| `education_policy` | `fiscal` | Явно переданная область заменена другой без адресного отказа |
| `domain_hint="Education Policy"` | `fiscal` | Та же потеря через предусмотренный alias поля |
| `fiscal_policy`, `social_policy`, `healthcare_policy` | Соответствующий домен | Асимметричная нормализация, а не универсальный запрет `_policy` |

Другие `_policy` примеры воспроизводят тот же механизм. **8 FAIL в сохранённом выводе — один класс дефекта**, не восемь новых задач.

### Почему это важно для универсальной политики

Domain здесь не доказывает причинную модель и сам по себе не определяет всё решение. Но он влияет на последующую маршрутизацию/компиляцию. Система, получившая образование, не должна незаметно получать fiscal defaults лишь из-за формы названия. Это потеря уже имеющегося входа, не потребность заново добывать знание.

### Что исправлять

Нужно согласовать поддержанные caller aliases с canonical vocabulary на существующем adapter. Для явно неподдержанного значения допустим адресный unknown/отказ либо предусмотренное расширение taxonomy; молчаливая подмена другой предметной областью неприемлема. Исходный текст и raw domain должны оставаться доступными для диагностики. Избирательный regex для одного `education_policy` не является общим контрактом.

Наличие enum регулируемых доменов не нарушает само по себе принцип универсальности: [Rule 12](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md#L210-L230) отдельно допускает governed vocabularies и запрещает capability-gating enumerations. Ошибка здесь — не сам словарь, а необъявленная замена смысла. В дальнейшем cross-domain запрос может требовать иной модели scope, но это не повод немедленно строить новый NLP framework ради этого локального дефекта.

### Различающая проверка

Пара `education` / `education_policy` с одинаковым содержанием проходит через настоящий scenario adapter; проверяется реальный аргумент grammar и последующий resolver query, а не только captured dict подмены. Рабочие fiscal/social/healthcare и корректный unknown control сохраняются. Native-reproducer в предыдущем комплекте оставлен как **UNRUN**, не как подтверждённый продуктовый прогон.

**Граница:** доказана нормализация конкретного source excerpt. Не установлено, что из неё уже возникли неверная production-рекомендация, причинная оценка или обход authority.

## 3. Переоценка пункта об удалённой family-эвристике

Исходный E02 запрещал удалять активный `_required_data_families_from_heuristic` в рамках точной private-чистки LA-045 и требовал сохранить opt-in поведение. Первый отчёт отметил, что нынешний test, напротив, намеренно требует отсутствия этой эвристики даже при старом включающем флаге. Это точное наблюдение о смене поведения. [Текущий test](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/data_requirement/test_compiler.py#L770-L850).

**Нынешнее решение аудита: не требовать восстановления эвристики и не считать её отсутствие самостоятельным дефектом.** В прочитанной архитектурной конституции Rule 12 прямо требует заменять hardcoded capability enumeration поиском по корпусу и удалять fallback; отдельно допускает schemas, vocabularies и rule versions. Frontmatter конституции имеет proposed/draft, поэтому этот документ не используется для выдуманного утверждения о формальном sign-off каждой детали. Но её содержательное направление вместе с нынешним заданием пользователя даёт ясное основание не возвращать прежнее поведение автоматически. [Rule 12](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md#L198-L230).

Правильная проверка replacement существенно сильнее формальной отметки retirement:

| Вопрос | Что доказывает достаточный результат |
|---|---|
| Остались ли полезные кандидатные предположения? | Discovery может предложить construct с объявленным статусом; предложение не становится authority |
| Сохраняется ли реальная потребность без совпадения со старой таблицей? | Явный construct/claim не теряется; unknown basis отличается от «данные не нужны» |
| Расширяется ли система через корпус? | Добавленный пригодный ресурс обнаруживается существующим путём без новой hardcoded ветки |
| Есть ли настоящий downstream consumer? | Resolver result сохраняется, потребляется и имеет тот же предмет; не только shape совместимого словаря |
| Что с прежними данными? | Поддержанные historical artifacts читаются в своём старом профиле, не получают новую доказательную силу задним числом |

Удаление fallback **не доказывает**, что discovery уже достаточно хорош. Если оно обнаруживает неполноту нужного пути, чинить следует эту неполноту, а не маскировать её возвратом опасной эвристики. И наоборот: отсутствие отдельной бумажной записи о retirement не должно превращаться в главный продуктовый blocker, если содержательная совместимость и замена уже доказаны.

Исходный preserve-пункт остаётся в неизменённом документе. Здесь явно записана его новая оценка, а не утверждение, что он буквально исполнен.

## 4. LA-045: что ещё нужно, а чего не нужно делать

Удаление точной замкнутой private-группы не требует переносить compiler в новый пакет. Сохраняются active contracts, facade и доступ к historical reports. Проверка полного внешнего caller graph в первом проходе не выполнена; один search-zero никогда не объявлялся её заменой.

Но дальнейшая работа не должна превращаться в бесконечный поиск любого возможного внешнего пользователя. Нужен конечный, относящийся к поставке scope: first-party imports/string loaders/generated exports и поддержанные distributions. Обнаруженный реальный consumer проверяется по его договору. Существующий installed-wheel test — подходящий материал, а не основание строить второй packaging harness.

Требование сравнить AST всех остальных функций имело смысл на **отдельном cleanup-коммите**, чтобы отличить эквивалентную чистку от behavior change. Оно не означает, что нынешний compiler обязан сохранять AST сентября после содержательного развития. При проверке сегодняшнего продукта главное — нынешние поддержанные inputs/outputs и правильная историческая совместимость.

## 5. Отдельная характеристика, не новый подтверждённый баг

Первый проход установил различие представлений: helper может читать верхнеуровневый `required_constructs` у mapping claim, но `_claim_record_like` не переносит это поле в нормализованную запись; `metadata.required_constructs` сохраняется. [Нормализация claim](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L790-L825); [construct reader](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/data_requirement/compiler.py#L1200-L1270).

Публичный договор поддержки первого представления не установлен. Поэтому здесь нет предписания автоматически расширить API или ещё одной записи «сломано». Следующее действие — выяснить фактических producers и supported shape, затем либо исправить потерю действительного входа, либо сделать нормализацию/тест явными. Проверка одного private helper не заменяет проверку доступного public path.

## 6. Сводка «сделано / сохраняем / остаток»

| Область | Сохраняемый результат | Остаток и тип работы |
|---|---|---|
| Private cleanup | Удалена точная неиспользуемая группа; живые owners остаются | Конечная совместимость поставки; proof-only до выявления реального дефекта |
| Generic vs pilot scope | Не появляются UA/2022 из общих geography/time labels | Native query/consumer regression; не новый scope framework |
| Opaque ID и отрицание темы | Не создают прежнее обязательное construct; lexical proposal ограничен | Не выдавать это за полную интерпретацию текста; проверить реальные declared requirements |
| Text/request handoff | Содержание доходит через правильные поля | Сохранить в native caller regression |
| Domain/domain_hint | Часть canonical/alias путей поддержана | **Реальный source-контрпример: молчаливое fiscal; требуется адресный ремонт** |
| Retired family fallback | Убрана старая эвристическая ветвь; возврат не назначается | Проверить полезность и free-growth replacement, а не запрашивать ритуальное совпадение с E02 |
| N7 acquisition | Прочитан compiler handoff, не весь acquisition | ACQ-01: actual owner → принятое новое основание → изменённый зависимый расчёт |

## 7. Доказательства и статус

Сохранённый запуск source excerpts: **34 проверки, 26 PASS, 8 FAIL**, Python 3.13.5, не native package import/pytest. Это прежний опыт с тем же commit; его полный вывод и использованные definitions находятся в [portable_probes.json](../04_Проверки/REQ01_предыдущий_проход/evidence/portable_probes.json). Он не превращается в новый запуск из-за копирования в досье.

Новая часть этого выпуска — переоценка способа ремонта относительно цели и Rule 12. **LA-046 целиком не закрыта**: compiler-дефект остаётся, ACQ-01 не испытан полностью. LA-045 не переобъявляется отсутствующей реализацией только потому, что у нас нет нового installed прогона.

Следующий кодовый шаг по этой области — нормализация domain и различающая проверка настоящего адаптера. Следующий архитектурный вопрос — пригодное discovery после retirement, с реальным consumer, а не восстановление старой эвристики.
