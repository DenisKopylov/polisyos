# SRV-03 — фактический autotune consumer и границы native cutover
## C15 · выпуск v013 · 31 октября 2026 года

**Исходная карточка:** LA-015, этап 2/2 и accountable closure. Первый этап — CTL-01. **Очередь:** LANE-02; следующий пакет по исходному порядку — CTL-02. Implementation-зависимости CTL-02/STP-01 не отменяются порядком read-only аудита. **Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Код продукта, тесты, lockfiles и зависимости не изменены.

## Решение

**Частичная оценка; миграция реализации наблюдается, полная приёмка LA-015 не установлена.** `SearchLoopRunner.run` уже создаёт `_SearchLifecycleOwner` и `_NativeSearchServiceDriver`, а не `SearchController`. Существуют настоящий benchmark→сохранение→registry путь и тест с запретом старого конструктора/run и повторным чтением CAS. Не нужно создавать ещё один driver, копировать loop или удалять compatibility controller по одному факту переключения consumer. [S01, S02, S08]

**C15-R01 — локально подтверждённый разрыв роли sentinel на mutation-codec.** Штатный `SentinelInjector` добавляет `__sentinel__`; lifecycle передаёт эту роль вместе с кандидатом, но autotune передаёт ключ в строгий `PydanticMutationCodec`. Для обычного наследника `MutationArtifact` это `extra_forbidden` до вызова benchmark. Положительный обычный кандидат с тем же предметом проходит. Это не объявлено новой регрессией относительно старого controller и не доказательство отказа всех поддержанных codecs. [S01, S03, S05, S06; P16–P17]

Подтверждена достижимость ранее описанного незавершённого error-path через тело настоящего consumer: после одного успешного результата следующий benchmark-exception распространяется, lock освобождается, но `_finish_native_run` не вызывается и частичный SearchResult не выдаётся. Ранее сохранённые данные нельзя объявлять стёртыми: источник сохраняет candidate/evaluation до рассмотрения promotion, а CAS в данном опыте вообще не запускался. [S01–S03; P23–P24]

## 1. Требование и содержательная цель

[Исходный E02](../05_Источники/SRV-03_исходные_строки.txt) требует actual caller cutover, сохранения предмета оценивания, stopping/расходов/history/frontier, warm-history, контрольных ролей и частичных результатов. Совпадение с уже ошибочным старым поведением не является целью. Перед retirement обязателен конечный census реальных клиентов и договор старых histories/import names.

Рабочая установка о LLM сохранена: генерацию гипотез, постановку эксперимента и выбор следующего шага может делать LLM. Роль этого участка — точно исполнить выбранную постановку, удержать организационную роль проверки, сохранить измерения и обоснованно продолжить или остановиться. Отсутствие универсального алгоритмического генератора гипотез не является дефектом SRV-03.

## 2. Матрица LA-015

| Часть | Уже реализовано — сохранять | Остаток и уровень доказательства |
|---|---|---|
| Один state/lifecycle-owner | Owner и driver создаются прямо в `SearchLoopRunner`; старый facade не конструируется | Полный native import/runtime здесь UNRUN; воспроизведён source run с обозначенной owner-boundary |
| Обычная работа | Typed initial payload, реальные codec и evaluator ports; N-лимит через действующий driver | Benchmark/registry/CAS в опыте — recording seams; полноценная положительная цепочка есть в тестовом коде, не перезапущена |
| Независимые run | Каждый runner call создаёт новый owner/state; предыдущий результат отделён | Генератор является переданным переиспользуемым объектом; его RNG/checkpoint — самостоятельный договор CTL-02 |
| Budget binding | Парность owner/binding, конфликт run_id, явный scope вокруг полного driver | В опытах owner-validation/scope — фикстуры; настоящие ledger, резервы и реальные платные вызовы не исполнены |
| Warm-start | Fingerprint требуется; предпочтён `warm_start_for_context`, затем допустимый legacy `warm_start` | Доставка истории генератору не означает её численную пригодность/использование GP и не создаёт lifecycle history |
| Sentinel | Общий lifecycle распознаёт роль и исключает её из ordinary history/best | C15-R01: стандартная связка с mutation-codec прекращается до контрольного benchmark; роль требуется и у promotion-owner |
| Empty | Реальный driver ограничивает persistent empty и допускает transient empty | Проверен batch-путь после полезного initial seed; произвольный scalar-generator не объявлен поддерживающим `[]` |
| Ошибка/отмена | Причина не подавляется; run-lock и binding-scope освобождаются | Нет законченной возвращаемой проекции частичной попытки в исследованном caller; связь с C12, не новая отдельная B-находка |
| Compatibility/retirement | Существующие facade/serialized identities не удалены | Полный конечный consumer census и исторический installed reader не исполнены; blanket retirement не разрешается |

## 3. Фактическая композиция, а не только интерфейс

`SearchLoopRunner.run` проверяет generator, обязательную selected suite для специального claim-профиля, парность budget-owner/run binding. В защищённой бюджетной ветви вызывает существующий `TracedLLMCandidateGenerator.require_bound_owner`. Caller context отделяется от runtime run_id; конфликт явно переданного run_id с binding отвергается. Для MethodJob разрешается действительная signature; native Bayesian-профиль собирается отдельной существующей ветвью. [S01]

Далее runner строит обычный SearchConfig с `MaxIterations(max_iterations)` и `enable_stage_a=False`, создаёт `_SearchLifecycleOwner`, а Stage B связывает со своим `_evaluate_candidate`. Этот owner передаётся `_NativeSearchServiceDriver.run_search`. При связанном budget-owner выполнение обёрнуто в его scope. Простое наличие imports `SearchConfig` и `TracedLLMCandidateGenerator` из controller не означает, что autotune всё ещё создаёт старый полный controller. [S01; P02, P27]

У `_evaluate_candidate` уже есть отдельный содержательный путь: codec → сохранение candidate → benchmark evaluator → проверки выбранных источников → сохранение evaluation → `ChampionRegistry.consider_promotion` → metric projection. Настоящий `MethodJobBenchmarkEvaluator` строит JobSpec из проверенных slot-bindings и вызывает `run_job`; это не объявлено отсутствующим из-за того, что локальная проверка использовала recording callback. Численные producers, весь source admission и compare-and-publish относятся также к другим пакетам и здесь не переаттестованы. [S01]

**Полезные локальные контроли:** два значения 3 и 1 проходят в правильном порядке; два независимых runner-вызова получают разные histories и IDs; typed initial mutation даёт одну оценку без обращения к генератору. Отсутствие generator/codec, непарный owner/binding и конфликт run_id остаются явными отказами. Реальными были run/driver тела и Pydantic-валидация; семантика численного score, store и registry — fixtures. [P02–P11]

Не следует выводить из библиотечного consumer наличие default HTTP-пути для любого пользовательского policy-вопроса. Индексный поиск показал тестовые consumers; это не полный census. Прочитанная заметка от 10 октября описывает старый срез и иной набор consumer gaps: её отрицательные выводы и старые line numbers **не перенесены** как описание нынешнего кода. В частности, нынешний `_evaluate_candidate` уже содержит первичное suppression отклонённого source-score; полный соответствующий guard в этой серии не испытывался. [S01, S10]

## 4. C15-R01: служебная роль попадает в предметную схему

### 4.1. Цепочка

1. `SentinelInjector._decorated_sentinel` выдаёт исходный payload плюс `__sentinel__` с видом и идентичностью контрольного примера.
2. Lifecycle определяет `is_sentinel`, но передаёт candidate в Stage B. `invoke_candidate_evaluator` передаёт обычному callable тот же candidate/context; специальный перенос proposal есть только для конкретного funnel-owner.
3. Autotune `_evaluate_candidate` удаляет `_strategy_metadata`, при специальном условии — `semantic`, затем вызывает `codec.decode(projected_payload)`. `__sentinel__` на этой границе не отделяется.
4. `PydanticMutationCodec.decode` непосредственно выполняет `model_validate`. У базового `MutationArtifact` установлен `extra="forbid"`. [S01, S03, S05–S07]

### 4.2. Различающие наблюдения

Взята минимальная предметная модель `MutationArtifact + value:int`, как класс в существующем SRV-03 test. Без метки `{loop_id: audit-loop, value: 5}` декодируется. Тот же предмет после штатного injector даёт `ValidationError`, адрес `('__sentinel__',)`, тип `extra_forbidden`. Benchmark не вызывается, запись численного результата не появляется. [P16]

В более длинном опыте source runner, source driver и source generation-selection прошли два обычных кандидата. После появления sentinel возник тот же отказ. Осталось две обычные строки во внутренней истории и четыре записи в **in-memory fixture sink** (по candidate/evaluation); sentinel count — 0, статус owner — `running`, `_finish_native_run` не вызывался. Эти четыре записи не называются настоящими CAS-артефактами. [P17]

**Severity:** medium, conditional on stock sentinel wrapper + strict ordinary mutation-codec; **confidence:** high for the local mechanism. **Не доказаны:** частота такого профиля в production, отказ всех mutation-codecs, потеря bytes действительного CAS, ошибка научного вывода или полномочия публикации.

### 4.3. Почему простое удаление метки недостаточно

Контроль с отделением известной роли в audit-only codec позволил пройти typed mutation, а lifecycle сохранил sentinel count=1, обычную history=0 и отсутствие best. Если снять метку **до lifecycle**, тот же результат стал одной ordinary-строкой и best. Это distinguishing removal control; он не является готовым патчем. [P18, P29–P30]

Кроме того, реальный autotune `_evaluate_candidate` рассматривает promotion внутри callback **до** того, как lifecycle исключит sentinel из best/history. Поэтому добавление одного `pop('__sentinel__')` может открыть декодирование, но оставить контрольную роль неизвестной для benchmark/promotion. Реальное повышение контрольного примера не воспроизведено: registry в опыте отсутствовал. Это адресный обязательный negative-control для ремонта, а не установленный обход. [S01]

**Направление:** у существующего мостового владельца отделить известную организационную роль от предметного mutation, сохранить её до benchmark, registry, статистики и продолжения. Либо явно ограничить поддержанный профиль до входа в частично выполненный run. Не ослаблять всю Pydantic-схему, не удалять все underscore-поля и не объявлять контроль обычным новым научным кандидатом. Не создавать второй registry/driver. Предметные поля должны оставаться ровно теми, которые действительно исполняются.

## 5. Ошибка, partial outcome и настоящее продолжение

Source `run_search` освобождает lock через finally, но `_run_locked` не завершается через `_finish_native_run` при исключении evaluator. `SearchLoopRunner` также не перехватывает исключение в возвращаемое состояние и не передаёт caller сохранённого owner. В ограниченном опыте после удачного value=1 следующий value=2 вызвал контролируемую ошибку benchmark. Результат: одна завершённая history-строка, одна evaluation-entry и две candidate-entry в fixture sink, статус `running`, ноль finish-вызовов. Исходное исключение сохранено, lock доступен. При cancellation также закрывается budget scope. [S01–S03; P23–P24]

Это уточняет reachability C12 через реального по коду consumer, а не создаёт вторую независимую находку о том же raise-path. Поднимать исходную ошибку может быть правильным договором API. Незавершённость — отсутствие доступного законченного частичного run/ссылки и явного продолжения, а не сам факт exception. **Нельзя заключать, что ранее записанные реальные CAS-артефакты удалены**: код сохраняет их по ходу оценивания, здесь фактический CAS не запускался.

Приёмка должна показать: один законченный результат → следующая ошибка или отмена → доступны прежний результат, конкретная причина и оплаченная работа → разрешённое продолжение не переисполняет всё вслепую и не переносит ответ в новый run. Подойдёт existing typed interruption с snapshot/refs или иной действующий владелец попытки; обычный успешный SearchResult вместо ошибки не требуется.

**Empty — отдельный уже исправленный случай.** После полезного initial seed batch-generator, трижды вернувший пустоту, завершился с одной сохранённой оценкой и `generation_exhausted`. Вариант `[] → кандидат` дал две оценки и обычную остановку лимита. Истолкование любого empty как доказанной полноты пространства остаётся старым ограничением C12, не исправленным одним конечным числом попыток. [P31–P32]

## 6. Warm-start, тесты и границы доказательств

### 6.1. Два разных вида warm

Runner передаёт `warm_start_bridge.load_warm_start(fingerprint)` самому генератору: сначала через contextual method, иначе через callable `warm_start`. Отсутствующий fingerprint и неподдержанный generator дают адресный отказ до новых оценок. Условие численной совместимости остаётся у действительного bridge/strategy. [S01; P12–P15]

Эти данные не превращаются автоматически в `SearchConfig.initial_evaluations` или уже выполненные строки текущего owner. В нашем положительном control исторический ряд дошёл contextual generator, но lifecycle выполнил одну новую оценку, history=1 и training_evaluations=0. Это не доказательство потери warm-данных: у generator свой разрешённый training corpus. Его фактическое использование GP проверяют OPT/TRN, а RNG/checkpoint — CTL-02. Полноценный restart/resume из persisted state данными наблюдениями не установлен.

### 6.2. Действительный тест положительного consumer нужно сохранить

`test_current_autotune_runner_characterizes_real_cas_consumer_path` запрещает конструктор и `run` старого SearchController; затем создаёт настоящие FileSystemCAS/ChampionRegistry, проводит 1→2→7 через `SearchLoopRunner`, создаёт новые store/registry handles и перечитывает champion. Evaluator тестовый — возвращает число `value`; это не настоящая причинная модель. Новый handle в том же pytest-процессе не равен независимому процессу после restart. Тест **прочитан, не запускался**. [S08]

### 6.3. Название сложного теста шире фактически выполненного сценария

`test_current_controller_trace_preserves_warm_sentinel_empty_error_resume` параметризован facade/native owner, не `SearchLoopRunner`. Его `evaluator-error` возвращает обычный словарь с `REJECT`; exception не возникает. `resumed` — имя следующего кандидата в том же непрерывном вызове, не восстановление после падения. Это полезный тест маршрутизации, но он не закрывает отсутствующую сложную consumer-приёмку. Отдельный exception-test специально сохраняет raise и статус RUNNING. [S08]

**C15-T01:** тот же warm trace передаёт старую запись только с `objective_value=10`, без source-results, но ожидает `training_evaluations=1`. Текущий `_begin_native_run` увеличивает этот счётчик только при AVAILABLE assessment, сверенном с source-results. В ограниченном выполнении этого тела такая запись сохранилась в history, но training count остался 0. Это рассогласование исходников теста и нынешнего договора, не свежий вывод штатного pytest. Не следует ослаблять проверку происхождения, чтобы вернуть старое ожидание. Нужно либо дать тесту действительно совместимую измеренную историю, либо ожидать ограниченную историческую строку. [S03, S08; P28]

## 7. Другие границы — не дополнительные подтверждённые production-баги

В prefix autotune по имени удаляется `_strategy_metadata`, а при отсутствии model field — `semantic`. Для явно объявленного `semantic` поле сохраняется. Неизвестный обычный ключ по-прежнему отвергается. В контрольной Pydantic-модели с разрешённым alias `_strategy_metadata` прямой codec сохранил `{seed:7}`, а runner отвёл его в generation metadata, подставив default `{}` в предметную модель. Это иллюстрирует границу зарезервированного имени и версии projection; такого реального model-consumer в проверенном наборе не найдено. Поэтому C15-G03 — точный вопрос договора и совместимости, не самостоятельная установленная ошибка реальной научной модели. [S01, S05, S07; P19–P22]

Параметр `scheduler` явно помечен как reserved и удаляется; `dedup` в прочитанном run не используется. Нельзя обещать Hyperband/dedup только из этих аргументов, но исходный SRV-03 не поручает строить эти подсистемы. Переданный generator сохраняет собственное состояние между вызовами: свежий run-state не означает автоматического сброса RNG или нового источника независимых измерений. [S01; P26]

## 8. Остаток до закрытия и приоритет

1. Согласовать контрольную роль на реальной `SentinelInjector → mutation-codec → evaluator → registry` цепочке; положительный обычный кандидат и строгий отказ неизвестному предметному полю сохранить. Контроль не попадает в ordinary best/frontier и не становится новым champion лишь из-за снятой ошибки декодирования.
2. Квалифицировать partial/error/cancel и recovery именно через `SearchLoopRunner`, сохранив источники, расходы, RNG/checkpoint и установленный смысл повторов. Существующий raise-path не менять на фиктивный success.
3. Выполнить штатные tests с настоящими contracts, CAS и текущими владельцами, затем actual caller/lifecycle/serialized-reader census для точного compatibility-профиля. CTL-02/STP-01 и остатки C12–C14 остаются открытыми; blanket-retirement controller не назначается.

**Штатная команда, только для дальнейшей приёмки, UNRUN:**

```bash
cd policy-engine
uv run pytest -q tests/unit/remediation/test_srv_03.py tests/unit/remediation/test_srv_01.py tests/unit/scientist/search/test_contracts.py
```

Не требуется новый фреймворк или универсальный алгоритм генерации гипотез. Сохраняем сделанный cutover и ремонтируем конкретные действительные границы.

## 9. Что выполнено

**32 ограниченных наблюдения — 32 MATCH, 0 ERROR.** Среди них один confirmed-local механизм в двух сценариях, positive controls, source checks, межпакетная проверка старого error-path, contract boundaries и removal/direction controls. Это не 32 product PASS. Первый промежуточный прогон включал 27 наблюдений без ошибок; итоговый расширен до 32. Их числа не суммируются. [Протокол](../04_Проверки/C15_SRV03/bounded_diagnostics.json)

Реальны CPython 3.13.5, Pydantic, текущие source-тела runner/generation/codec/injector и сохранённые полностью blob-сверенные service/run_state. Full lifecycle import не запускался: использованы ранее сохранённые и вновь прочитанные source excerpts. Native owner constructor/config, часть records/score/source context, provider/ledger/CAS/registry/funnel являются обозначенными fixtures либо не исполняются. `_decode_prefix` заканчивается до persistence; downstream recording callback не является реализацией benchmark. Никакой claim production publication из опытов не делается.

**Native project pytest, полные imports/DTO/ObjectiveStack, реальные GP/NCM/MethodJob, provider/ledger/CAS/HTTP — UNRUN.** Поддержанный contributor baseline — Python 3.14.x. Попытка чтения raw source в cloud-контейнере получила DNS error; актуальный source прочитан через GitHub connector. Web-страница была старым индексным view и не использовалась как текущий source baseline. Dependencies не устанавливались. [S09]

30 проверок целостности досье завершились без ошибок; это не приёмка продукта. 14 предыдущих отчётов и их evidence сохранены побайтово. LA-015 остаётся partially_assessed; оба её этапа теперь просмотрены, но выполнение стадий и полное закрытие не заявляются. Следующий пакет — **CTL-02: B124/B125/B126**, по исходному порядку.

## Первичные источники

Индекс [C15_источники.json](../05_Источники/C15_источники.json) фиксирует диапазоны, Git blob и отдельный уровень исполнения. [Матрица](../04_Проверки/C15_SRV03/verification_matrix.json) · [остатки](../01_Реестры/C15_остатки.json) · [преемственность](../06_История/Согласование_v012.md).

**S01** — [policy-engine/src/polisyos/scientist/methods/autotune/runtime.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/runtime.py), blob `dcc27af39812c88b0abb9ddfcac1a76f83ca5826`, прочитанные диапазоны [[1, 650], [1700, 2440]]. read selected complete runner run and evaluation sections; run body + codec prefix transcribed/executed; real post-codec persistence/admission/registry UNRUN.

**S02** — [policy-engine/src/polisyos/scientist/methods/search/service.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py), blob `bcc87e32cc1903888845a557a729f6dcf6b182b2`, прочитанные диапазоны [[175, 335]]. fresh run path read; preserved complete source verified by Git blob and executed with declared owner dependencies.

**S03** — [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py), blob `754e942a21b3198c3989ac9175c54342b6c67ab3`, прочитанные диапазоны [[480, 665], [800, 960], [1420, 1600], [1660, 1760]]. fresh selected boundaries; same-pinned prior evaluator/begin/finish excerpts reused; whole package and native owner constructor UNRUN.

**S04** — [policy-engine/src/polisyos/scientist/methods/search/run_state.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/run_state.py), blob `b4f980de235263513c7ad7e5771e1ccfbb3d8b3d`, прочитанные диапазоны [[1, 130]]. complete fresh source read; preserved full blob verified/executed with contract fixtures.

**S05** — [policy-engine/src/polisyos/scientist/methods/autotune/models.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/autotune/models.py), blob `631d87c1ade0b084e92806cc7f253f9628571c0e`, прочитанные диапазоны [[1, 210], [650, 850], [1020, 1320]]. MutationArtifact/codec class excerpts executed with real Pydantic, not native full module; empty out-of-range queries not considered evidence.

**S06** — [policy-engine/src/polisyos/scientist/methods/search/sentinels.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/sentinels.py), blob `85409acfc8042bf3df14f78b0e291979a5495f96`, прочитанные диапазоны [[130, 285]]. injector bodies transcribed/executed; SentinelSet input fixture, no real CAS.

**S07** — [policy-engine/src/polisyos/scientist/methods/search/frontier.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/frontier.py), blob `c15801509c9a890128ad33e493974bcbb8687ebb`, прочитанные диапазоны [[1, 205], [250, 465]]. read caller/subject/invoke contracts; materializer/hash boundaries fixtures in probes.

**S08** — [policy-engine/tests/unit/remediation/test_srv_03.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_srv_03.py), blob `9a752a4e72400548590a48861d1aea9351e11e5e`, прочитанные диапазоны [[1, 650]]. complete file read; pytest UNRUN; real CAS classes in code, controlled numeric evaluator; warm trace not actual runner.

**S09** — [policy-engine/CONTRIBUTING.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/CONTRIBUTING.md), blob `8ff414198e306e671abff1f76f31330a1f29d765`, прочитанные диапазоны [[1, 18]]. supported Python 3.14 baseline only.

**S10** — [policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/v5-final-joined-search-engineering-20261010.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/v5-final-joined-search-engineering-20261010.md), blob `не сохранён`, прочитанные диапазоны [[1, 230]]. historical 2026-10-10 note; response truncated; only visible context read; not current census or native evidence.
