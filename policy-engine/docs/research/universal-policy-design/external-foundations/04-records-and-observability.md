# Формат корпуса и наблюдаемость оснований

Исследовательский формат, 2026-10-20. Обязательства runtime относятся к существующим владельцам и требуют отдельной реализации/проверки.

---

## 1. Три слоя, которые нельзя смешать

| Слой | Что хранит сейчас / в будущем | Что не следует из наличия записи |
| --- | --- | --- |
| Атлас исследования | Открытые families, primary-source cards, ограничения, связи и поисковые направления | Источник уже в production corpus; capability реализована; ресурс применим к любой задаче |
| Действующие corpora и capability index | Их собственные release-bound записи, manifests, typed resources, verified transformations | Любой claim допустим от наличия ресурса |
| Основание конкретной задачи | Выбранные refs/versions, purpose, relations, assumptions, admission, evidence lines и outputs | Выбор полностью покрывает внешний мир или остаётся актуальным бессрочно |

Не вводить автоматическое чтение этого JSON в runtime. Будущая загрузка проходит через existing producer/import/admission owners и их conformance; сначала следует сопоставить поля с тем, что они уже хранят.

## 2. Документы и идентичности

families.json — canonical editorial records семейств: содержание, требуемые объекты, non-substitution, сравниваемые варианты, функции, источники и дальнейшее наполнение. sources.json — canonical source cards. Markdown объясняет связи и решения, не хранит вторую полную копию карточек.

Карточка источника содержит id, title, url, issuer, version_or_date, checked_at, kind, contribution, applicability, does_not_establish, access_limitations и verification. Последнее обозначает способ исследования страницы, не product verification verdict. При повторении одного источника сохраняется один canonical record с aliases и тематическими uses; разные версии не сливаются по title.

Поле research_access различает primary_text_or_selected_sections, abstract_or_metadata и search_extract_only. Это редакторские метки объёма доступа. Исходное описание verification сохраняет подробности: доступ к странице или выбранным разделам не означает аудит всего документа; search-only не должен поддерживать подробную нормативную интерпретацию. Точные source section locators включаются, где были установлены; отсутствие bytes digest отмечается, а не заменяется придуманным hash.

В дальнейшем нужно различать source work, version/expression, physical distribution, конкретный извлечённый тезис и task-specific use. DOI/URL помогает найти ресурс; digest binds bytes; publisher/DOI указывает на публикацию или её версию; проверенная подпись связывает issuer с конкретным подписанным содержимым в scope подписи. Ни одно из них не доказывает истинность, полномочие issuer или применимость тезиса к задаче; эти отношения устанавливаются отдельно. Разные карточки могут зависеть от одного upstream источника.

Для substantive additions следующий исследователь не просто расширяет библиографию: он добавляет отдельные положения и правила с точным section pointer, исходной терминологией, условиями, альтернативами и объяснением, какое отношение они помогают установить. Комментарий PolicyOS отделяется от утверждения автора.

## 3. Общие facets и family-native содержание

Общие поисковые facets: purpose/construct, external issuer, source/reference/version, observation/publication/effective/receipt/verification times где релевантно, population/place/jurisdiction, access/rights, provenance, disagreement, relations и named limitations. Не все поля применимы ко всем основаниям.

Специфическое содержание остаётся у семьи:

- наблюдения: sampling frame, unit, instrument, response/missingness, weights, lineage;
- методика: estimand, formula, algorithm, assumptions, operational profile, edge cases;
- причинное основание: graph, mechanism, identification assumptions, transport context, intervention regime;
- закон: provision, competence, governing correspondence, effect/transition/exceptions, authentic language;
- ценностное основание: principal, elicitation/authorization, choice purpose, constraints, dissent;
- институциональный акт: issuer competence, actual act, scope, conditions and currentness;
- feasibility: actor, capacity, schedule, resources, enforcement and dependencies;
- verification: property, verifier, independence, inputs, limits and counterexample.

Это не один обязательный мегадокумент и не новый общий event envelope. [Custody Time Model](../../../system-design-decisions/policy-design-custody-time-model.md), §§1–5, сохраняет owner-native storage и отображает отношения между ролями времени.

## 4. Что наблюдать

| Вопрос | Нужные данные/проекция | Что было бы ложным proxy |
| --- | --- | --- |
| Какие основания нужны? | Зависимости claim и обязательства в declared scope; unresolved relations | Чеклист всех EF-family на каждую задачу |
| Что доступно для поиска? | Index/release/frontier, доступные и недоступные channels, aliases, coverage limitations | Количество URL как полнота знания |
| Что реально использовано? | Выбранные exact refs, transformations, producer runs и relation evidence | Библиография финального отчёта |
| Почему это выбрано? | Eligibility, inclusion/exclusion, отвергнутые альтернативы, learning influence | Высокий retrieval score как пригодность |
| Где основания зависимы? | Shared lineage, assumptions, cohorts, methods and synthesis | Число papers как независимость |
| Что поменяло вывод? | Basis sensitivity, ranking reversals, binding constraints, missing decisive inputs | Среднее всех чисел как консенсус |
| Что устарело? | Раздельные observed/effective/verified/currentness semantics и material dependency change | Дата последнего fetch как действительность |
| Что узнала система? | Источник learning signal, exposure/selection, transfer limits, обновлённая версия influence | Больше памяти как лучшее качество |
| Что пока не установлено? | Конкретный object/producer/verification gap и допустимый следующий шаг | Generic warning «нужны дополнительные данные» |

Наблюдаемость включает диагностику собственного выбора оснований: concentration источников/языков, пропущенные группы, selection bias, stale indexes, repeated unresolved mappings, acquisition failures. Эти показатели — диагностика с знаменателем, не универсальная оценка истинности или легитимности.

## 5. Аудитории и безопасные проекции

Public view объясняет, на чём основан вывод, от каких предпосылок зависит и что изменит решение. Expert view показывает спецификации, зависимости и расхождения. Reviewer view раскрывает admission, verifier basis и контрпримеры. Machine view ссылается на exact artifacts и rules. Все views должны сохранять смысл ограничений и purpose-scoped authority.

Нельзя превращать verification vector в общий «проверено». Historical authenticity, integrity, semantic correspondence, permission и currentness различаются. [Public verification/disclosure](../../../system-design-decisions/int-r7-r8-public-verification-and-disclosure-ratification.md), PV-K01–K09, требует учитывать и metadata/topology как канал раскрытия.

Для приватных данных публичные locators, graph topology и provenance также могут быть чувствительными. Queries, выбранные/отвергнутые кандидаты и причины включения могут раскрывать интересы или факты о людях. Hashes и stable IDs обеспечивают связывание/целостность, но не являются защитой приватности. Публикуется разрешённая bounded projection; наличие provenance не даёт права раскрывать её целиком. Controlled access совместим с исследовательским каталогом. Отказ в доступе не означает отсутствия объекта.

## 6. Изменение основания и custody

Исправление, отзыв или новая редакция создают отдельное событие; старые bytes и refs сохраняются по разрешённому retention regime. Source event сопоставляется с реально зависимыми claim uses. Не каждое изменение байтов материально, но неизменные байты также не доказывают неизменную authority: могли измениться полномочия или scope.

Итоговую реакцию определяет canonical claim/currentness owner. Атлас может обнаружить изменение и указать зависимости; он не отзывает сторонний акт и не выдаёт новый publication verdict. При недоступной актуализации следует показать последний установленный cutoff и currentness rule, не предполагать, что «нет новости» означает «всё действует».

## 7. Расширение без новой онтологической границы

Новая family или facet предлагается вместе с конкретным примером различия, которое текущая карта скрывает. Перед добавлением: проверить reuse, указать связи/пересечения, избежать синонимического дубля, сохранить старые IDs через aliases/supersession. Не требовать новой family для каждого домена. Неизвестные признаки сохраняются как research candidates; статус/authority production остаются governed.

Один редактор координирует изменения общей карты и links; исследователи приносят независимые source-bound contributions. Редакторская проверка поддерживает навигацию и не блокирует неизвестное семейство или facet на пути в candidate discovery. Формальная ратификация не требуется для записи нового исследовательского источника. Она требуется отдельно, если предлагается изменить binding authority/rule semantics.

Pattern pass: P03/P05/P07/P08/P13/P14/P25/P35/P37/P38. Будущий acceptance signal: источник заменён на неприменимый при сохранённых markers; relation reader отказывает, surface показывает именно missing applicability, старый replay остаётся прежним.
