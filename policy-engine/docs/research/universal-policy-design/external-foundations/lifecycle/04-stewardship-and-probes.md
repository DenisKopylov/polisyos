# Изменяющиеся основания: содержательные связи и работа системы

Уточнение после повторного review: [implementation protocols](05-implementation-protocols.md) и [delivery/probes](06-delivery-and-review.md) конкретизируют capture, enrollment, current-read, rights/restore и retirement. Они сохраняют standing исследовательского проекта; новые runtime проверки не выполнены.

Часть [предложения о lifecycle](../11-foundation-lifecycle.md). Полные новые записи — `G5-STW-01`–`G5-STW-05` в [grounds.json](../grounds.json), источники — `S5-STW-01`–`S5-STW-07` в [sources.json](../sources.json). Ниже проектируется использование оснований, а не присваивается authority внешнему тексту. Все сценарии и проверки — будущие; в этой работе они не исполнялись.

## 1. Уточнённые категории

**Изменения научного свидетельства.** Нужно получать не только исследование, но и последующие correction, concern, withdrawal и связанные notices. Они могут менять разные части аргумента. Crossmark допускает разные типы updates; COPE отдельно предостерегает от неясности partial retractions. Система должна уметь принять фактически выпущенное сообщение, не превращая этот способ публикации в рекомендацию. [Crossref](https://www.crossref.org/documentation/crossmark/participating-in-crossmark/), [COPE v2](https://members.publicationethics.org/sites/default/files/retraction-guidelines-cope.pdf), `G5-STW-01`.

Наш вывод: notification → exact original/version → использованный result/span → dependent claim. Пример — исправление одной оценки в статье с несколькими результатами. Автоматическое исключение всей статьи и автоматическое сохранение остальных результатов одинаково требуют обоснования. При неизвестной области последствия owner ограничивает соответствующее использование, а исследовательская ветка может продолжать явно условный анализ. Обновление права на использование и опровержение результата также не смешиваются.

**История значений, а не только кодов.** В ILO ISCO один числовой code переиспользуется при изменении состава категории; correspondence может быть many-to-many. Это содержательное основание для отказа от join по одному code. [ILO Companion Guide, Table 4.6 и module 6](https://www.ilo.org/sites/default/files/wcmsp5/groups/public/@dgreports/@stat/documents/publication/wcms_896661.pdf), `G5-STW-02`.

Наш вывод: версионировать definition, instrument и направленное mapping отдельно от dataset. Между релизами сохранять original coding, цель преобразования и evidence его допустимости. При недостаточном overlap можно показать две серии, оценить transition с uncertainty или перейти к общему уровню, если он сохраняет политический вопрос. Система ищет эти альтернативы, а не прекращает дизайн из-за отсутствия идеального crosswalk.

**Сохранность, доступность и воспроизводимость — разные основания.** PREMIS разделяет byte fixity и authenticity/integrity; LOC рассматривает зависимость пригодности формата от окружения; FORCE11 отделяет software identification от достаточности для воспроизведения. [PREMIS v3, special topics](https://www.loc.gov/standards/premis/v3/premis-3-0-final.pdf), [LOC Sustainability Factors](https://www.loc.gov/preservation/digital/formats/sustain/sustain.shtml), [Software Citation Principles](https://force11.org/info/software-citation-principles-published-2016/), `G5-STW-03`–`G5-STW-05`.

Наш вывод: в одной задаче могут одновременно быть установлены сохранность bytes, неизвестное происхождение baseline, потерянный parser и невоспроизводимый remote service. Нужен раздельный вывод по этим свойствам. Rehash не восстанавливает provenance; новый parser требует проверки потерь; ссылка на commit не исполняет метод. Режим сохранения определяется правами до копирования: «сохранять оригинал» всегда означает «если это допускает применимый режим», а не blanket retention.

## 2. Связи с существующим корпусом

| Новое основание | Существующая связь | Содержательное следствие для дизайна |
|---|---|---|
| `G5-STW-01` | `G4-SYN-03`: общие studies/cohorts | Notice относится к report, но synthesis должен знать underlying observations. Удаление дубликата не равно удалению независимого исследования; новый notice не новое независимое свидетельство. |
| `G5-STW-01` | `G3-ASR-05`: scoped status/reassessment | Reuse временной границы и пересмотра; не переносить credential revocation semantics на научную истинность. |
| `G5-STW-02` | `G3-MEA-03`, `G3-MEA-05`: invariance и изменение collection process | Mapping codes не устанавливает инвариантность измерения; смена классификации и смена способа сбора — разные причины discontinuity. |
| `G5-STW-02` | `G4-GEO-02`, `G4-GEO-03`: geography vintages/crosswalks | Общее требование — versioned directional relation. Ни occupation mapping, ни spatial overlap сами не дают weights для переноса конкретного показателя. |
| `G5-STW-03` | `S-OBS-01`, `S-OBS-02`: PROV/DCAT | Reuse lineage/catalog vocabularies; отдельный verifier проверяет фактический predicate, а не наличие provenance statement. |
| `G5-STW-04` | `G3-ACC-01`, `G3-ACC-02`, `G3-ACC-05`: доступ и использование | Dead URL, запрещённая обработка и потеря renderer требуют разных действий. Копия может существовать, но её использование недопустимо; отсутствие локальной копии не запрещает authorized remote computation. |
| `G5-STW-05` | `G4-SYN-03`, `G5-STW-04`: общая вычислительная основа | Shared code/model/calibration может связывать ошибки нескольких результатов. Citation count не измеряет независимость, а environment inventory не устанавливает научную валидность. |

Это исследовательские связи, не новые runtime relationship enums. Их применение должно быть purpose-scoped: «нужен для replay» и «нужен для validity» могут вести к одному объекту, но дают разные реакции при его утрате.

## 3. Связанный сценарий: сравнение программ переобучения

Система сравнивает несколько политик, используя administrative employment data, survey wellbeing, occupation classifications, исследования эффекта обучения и выбранную welfare convention. Один и тот же empirical basis поддерживает несколько candidate designs; различие value weights не делает их независимыми экспериментами.

1. **Получение.** Discovery находит dataset releases, instruments, classification versions и research reports. Acquisition получает разрешённые subsets и typed notices. Неполная pagination и недоступные группы остаются явными; ranking не скрывает их при выборе метода.
2. **Сопоставление.** Версии occupation codes отличаются. Scientist может сравнить dual-coded mapping, более грубую общую категорию и параллельные несопоставленные series. Каждая ветка хранит свой derivation и потерю разрешения. Если эта потеря меняет fairness question, грубое агрегирование не допустимый shortcut.
3. **Расчёт.** Эффект на employment, wellbeing и распределение выгод — разные estimands. Для каждого нужны method/output/unit binding и применимость к target population. Общая catalog identity не даёт causal transportability.
4. **Изменение.** Приходит correction эффекта из одного study. Owner связывает notice с использованной оценкой, пересчитывает materially affected branches, сохраняет прежнюю подпись и показывает источник изменения ranking. Если изменилась только license, отдельно проверяется право продолжать use/publication; величина эффекта от этого автоматически не меняется.
5. **Потеря воспроизведения.** Remote evaluator недоступен, сохранены output и разрешённые inputs. Система различает прежний проверенный результат и невозможность нового rerun; исследует замену evaluator с equivalence check. Она не объявляет старый результат ложным только из-за недоступного сервера, но и не обещает свежую верификацию.
6. **Обучение.** Успешный mapping, стоимость получения, ошибки parser и обнаруженный dependency pattern улучшают routing/acquisition priors. Изменение causal world model проходит свою evidence chain. Если design search выбирал основание по удачному результату, confirmatory проверка учитывает selection/adaptivity; память не становится дополнительным наблюдением.

Такой цикл порождает и совершенствует варианты политики. Custody здесь поддерживает содержательную работу: выявляет, какое новое исследование или получение данных действительно может изменить решение, вместо обязательного повторения всех проверок для всех источников.

## 4. Сбои и различающие проверки будущей реализации

Следующая таблица — программа behavioral probes, **не выполненные PASS**. Каждый probe должен пройти через реального producer, persisted artifact/event, consumer и fresh API/audit projection. Removal сохраняет markers/refs и убирает именно проверяемое свойство.

| Ситуация | Требуемое различие и наблюдаемый результат |
|---|---|
| Во время offset pagination вставлена запись перед уже прочитанной страницей | Traversal ended не выдаётся за snapshot/coverage complete. Consumer полного denominator ограничен; bounded candidate остаётся доступен. |
| Повтор запроса с тем же snapshot/token вернул другие bytes; `304` пришёл без сохранённого prior body | Conflict или доказанный version transition; для `304` повторный full fetch/явная утрата. Ни dedup по новому hash, ни empty dataset positive. |
| Crash после CAS write, до event/cursor; затем duplicate delivery и outbox publish без ack | Owner reconcile не продвигает неподтверждённый cursor, не удваивает result; lost ack допускает идемпотентную redelivery. Отдельно видны orphan, delivery и consumer outcome. |
| Export POST мог выполниться, но ответ потерян | Idempotency lookup/reconciliation либо indeterminate external effect; автоматический повтор не выводится из имени «fetch». |
| Два tenants делят provider key; приходит 429, worker перезапущен | Общий quota scope и persisted cooldown, отсутствие hot loop, прогресс независимого источника. Не выдавать per-worker cap за aggregate cap. |
| Source generation меняется между проверкой и public commit; reverse index отстаёт | Fence/reconciliation предотвращает unqualified current claim. Исторический cutoff-qualified result сохраняется; отсутствие index row не доказательство отсутствия зависимости. |
| Grant case A используется в case B того же tenant через cache/vector hit; token отозван перед retry | Access/read/projection повторно разрешают нужный purpose/scope/generation. Совпадение bytes, principal или tenant не grant. |
| Удалён raw, но остались index/embedding/temporary copy/WORM log/provider file | Consumer видит точный неполный erasure scope, retention conflict и ограничения reuse. Accounted bytes=0 или tombstone не доказательство all-copy deletion. |
| Receipt содержит `independent=true`, но verifier назначен самим producer; LLM добавил causal wording к неизменному source span | Origin/appointment и substantive relation проверяются отдельно. Наличие подписи/цитаты не разрешает promotion. |
| Correction пришёл раньше original; concern выдан за retraction; duplicate reports посчитаны независимыми | Typed pending relation, разрешение scope/зависимости, соответствующий пересчёт. Порядок наших действий не переписывается source event time. |
| Reused code, split/merge, reverse mapping, устаревшие weights | Нет silent equality/inversion. Установлен допустимый transform, uncertainty, common level либо parallel series. |
| Bytes неизменны, baseline подложен; parser/runtime утрачен; migration меняет единицу | Fixity, authenticity, usability, equivalence и scientific validity расходятся в результатах; общий «verified» их не схлопывает. |
| Новый source descriptor содержит import path/новый authority kind; unknown facet | Inert candidate metadata либо typed unsupported для действия. Config не исполняет код и не назначает authority. |
| Второй источник поддержанного класса добавлен без central dispatcher edit; объём вырос | Реальный same-class reuse и bounded full path. Если estimator materializes всё, ingestion streaming не выдаётся за free-grow гарантию. Approximation только с явным method/error contract. |
| Sampling отключил все traces; серьёзный event отсутствует при сохранившемся span | Telemetry не заменяет durable custody record в обе стороны. Диагностика не устанавливает полноту события или закрытие. |

## 5. Как перейти от предложения к реализации

Ниже роли существующих owners, не назначение новых агентов или разрешение менять их код в этой документационной работе. Перед реализацией — delta review от pinned snapshot и полный scope callers/consumers выбранного slice.

| Очередь | Владельцы и результат | Условие завершения |
|---|---|---|
| Capture/recovery | Fabric connector/ingestion + CAS + control-store/worker: один bounded resource, page/partition receipt, progress, mixed outcomes и reconciliation | Реальный fresh consumer различает completion/coverage/authority; crash и changed-response probes. |
| Access/copy lifecycle, параллельно первой очереди | Security/authority + storage/index/audit owners: разрешённый режим materialization, scoped reuse, inventory controlled copies, retention action/readback | Case/purpose bypass и false-erasure probes; внешний recipient scope назван. Не наращивать sensitive ingestion до этого. |
| Meaning/use binding | Native DataForge/Scholar/Lex/Foundry owners + Scientist: exact occurrence, transformation и назначение; сохраняемые alternatives | Изменение meaning при неизменных refs ломает соответствующий positive, не запрещая candidate exploration. |
| Change→custody→public | Source event producer + claim dependency/lifecycle + publisher: enrollment, scoped generation fence, update reaction | Late/duplicate/out-of-order events и publication race отражаются в fresh view без потери истории. |
| Second-source/growth | Те же owners: иной источник того же класса, partitions, scheduling/backpressure и scoped index generations | Нет source-specific branch в центральном orchestration; измеренные resource bounds и truthful partial result. |
| Retirement/replay | Artifact/retention + method/parser + claim owners: новый reader/migration, retained-use denominator, loss assessment | Старый exact use воспроизводим в объявленной границе либо честно помечен unreplayable с последствиями; нет silent latest. |

Independent review предшествует дорогой execution wave. Повторные проверки — по изменённым dependencies/relations; полный expensive replay нужен на freeze, а не после каждого source row. Реальные новые классы поведения требуют своего исследования; очередной endpoint уже поддержанного класса этого не требует.

**Граница оставшихся inputs.** Реальные issuer mandates, доступ, consent, publisher notice, custodian release и empirical overlap надо получать от соответствующих источников. Их нельзя заменить architecture prose. Но отсутствие cursor bridge, decoder, profile propagation, index scope или recovery owner — собственная engineering задача; её нельзя переименовывать в ожидание внешней authority. Невозможность получить один input должна оставлять путь сравнить законные альтернативы и оценить цену следующего шага.

Pattern pass: P01/P02/P12 — рабочая связь владельцев; P04/P05/P09/P15 — раздельные source status, evidence и наша authority; P07/P08 — версии/временные роли; P10/P14 — meaning/independence; P27/P31 — общий invariant вместо per-source bypass; P29/P32/P35/P37/P38 — полный scoped denominator и реальный discriminator. Current composed runtime verification остаётся `not_established`; исследовательские карточки не закрывают capability gaps.
