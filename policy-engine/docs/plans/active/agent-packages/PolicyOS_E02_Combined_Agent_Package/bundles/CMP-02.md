# CMP-02 — Однозначные slots и ordering по occurrence

**E02 · окно CP1 · локальная проверка L · начальный статус planned.**

**B:** B45, B46. **LA:** Нет; технический пакет B.

**Предшественники:** [CMP-01](../bundles/CMP-01.md). **Совместная очередь:** LANE-04.

**Общие правила:** [TEAM_RULES](../TEAM_RULES.md) и [руководство](../EXECUTION_GUIDE.md). Source facts и новые решения E02 различены ниже; current HEAD не проверен этим пакетом.

## Поручение и минимальная приёмка

Применить существующую chain-level проверку уникального производителя входа. Проверять prerequisite для конкретных node_id/occurrence, не по последнему общему FQN. Явный merge остаётся отдельным узлом с семантикой.

**Различающие тесты и сохраняемое поведение.** Два источника одного scalar-slot не зависят от UUID; разные slots работают. estimate1→sensitivity→estimate2 не отвергается; sensitivity1→estimate→sensitivity2 не скрывает раннее нарушение. Проверить strict/warning режимы и явный merge.

**Не считать исправлением.** Не выбирать источник по UUID и не объявлять эвристические tag-rules универсальными методологическими законами.

**Цикл работы:** зафиксировать actual scope и нужный characterization; оформить equivalent move и намеренный behavior fix раздельно; выполнить указанные малые tests через I1; независимый reviewer проверяет actual owner; передать commit, path map и остатки. CLI/test selectors разрешаются по настоящему checkout до запуска, не выдумываются из названия находки.

## Файлы и координация

**Кандидаты записи по аудиту / предложенные новые пути:**

```text
policy-engine/src/polisyos/foundry/methods/backends/async_chain_executor.py
policy-engine/src/polisyos/foundry/methods/backends/chain_executor.py
policy-engine/src/polisyos/foundry/methods/components/composer.py
policy-engine/src/polisyos/foundry/methods/components/semantic_validator.py
```

**Читать как соседние контракты:**

```text
policy-engine/src/polisyos/foundry/methods/components/linker.py
policy-engine/src/polisyos/foundry/methods/types/checker.py
```

**Предлагаемый отдельный regression-файл:** `policy-engine/tests/unit/remediation/test_cmp_02.py`. Это новое место либо предложение объединить проверки с существующим ближайшим тестом после короткого чтения; оно не объявлено найденным в репозитории. Actual native tests из исходных карточек не заменяются этим именем.

**Write mutex:** CMP-01, CMP-03, RES-03, RES-04. Это не необходимые предшественники. Read-contract impacts, общие config/lockfile и новые обнаруженные tests учитывает I1/I2 до lease; никто не меняет тестируемый worktree во время job.

**Path-map записи:** MOVE-03. После принятого move работать по actual target/commit, не по историческому имени файла. Source и target move одновременно зарезервированы владельцем.

**Условия общего использования:**

**A06.** Новый async/autolink/resume профиль объявляется эквивалентным только после своей согласованной effective-plan проверки. Явный исправный sequential профиль не блокируется неготовым optional режимом.

**Ресурс:** L — I1 broker admits requests against a shared seven-unit L-equivalent budget and at most seven resource-bearing process groups across all worktrees; resource cost is micro=0.5, standard=1, measured medium=2–3. Permit is released after process-group cleanup and receipt; review does not hold it. Общий fan-out — 15 direct leaf workers; чтение/код/review продолжаются без compute permit. Named shared resources and immutable request fields remain enforced; builds/installs через I1.

**Передача:** source ID/phase и исход каждого; base/patch; exact writes; equivalent versus intended delta; actual commands/exit/log; native/fixture/deferred; reviewer; path-map/caller/lifecycle/activation остатки. Ни partial LA, ни explicit limitation не превращаются в full implemented capability.

## Исходное основание B45

Источник B_r19, строки 836–851; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B45 -->
## B45. Два производителя одного входа разрешаются последней записью, а порядок зависит от UUID

*Источник карточки: C03-04. Код прочитан в C03; локальные проверки, не полное исполнение PolicyOS.*

**Приоритет и охват:** Высокий для композиции; S–M.

**Основание.** Несколько connect могут привести разные источники к одному target slot. Composer собирает bindings и сортирует их, в том числе по строке source_node_id; MethodNode создаётся с uuid4. В sequential и async сборщиках используется bound_inputs[target_slot] = source_value, поэтому последняя привязка перезаписывает предыдущую. Общий SlotLinker.validate_chain уже умеет обнаруживать повтор одного target, но в прочитанной последовательности MethodComposer.build()/validate() он не вызывается. CrossMethodValidator также не заменяет эту проверку. [N01–N05]

**Локальное свидетельство.** Два источника 10 и 20, назначенные одному x, дали разные x при перестановке фиксированных UUID. Это контролируемая иллюстрация порядка, не статистика случайных ошибок. Валидность полного набора предметных DTO и распространение результата до policy-решения здесь не испытывались.

**Предлагаемое исправление.** Проверить уникальность производителя каждого входного слота при окончательной сборке цепочки, переиспользуя существующий chain-level checker. Если нужны оба источника, вставить явный подходящий merge/aggregation-узел с определённой семантикой. Не выбирать «лучший» источник по UUID и не устранять дубли слепым dict/dedupe.

**Приёмка.** Два источника для одного однозначного входа не исполняются как молчаливый last-wins; два источника для разных входов проходят. Явное объединение воспроизводимо. Повторное построение с другими UUID не меняет смысл результата.

**Граница.** Номинальная совместимость двух пар слотов не доказывает допустимость их совместной записи. Это локальный контракт построения цепочки, а не новая система полномочий.

<!-- SOURCE_END B:B45 -->

## Исходное основание B46

Источник B_r19, строки 852–867; полный неизменённый текст.

<!-- SOURCE_BEGIN B:B46 -->
## B46. Проверка порядка смешивает разные появления одного метода по общему FQN

*Источник карточки: C03-05. Код прочитан в C03; локальные проверки, не полное исполнение PolicyOS.*

**Приоритет и охват:** S; перед повторным применением методов в цепочке.

**Основание.** CrossMethodValidator._check_ordering_rules собирает ordered_nodes по появлениям, но затем строит fqn_order_index = {fqn: i ...}. Повторный FQN заменяет позицию предыдущего экземпляра. Требования после этого проверяются по последним позициям имён, а не по конкретным узлам. При strict=True нарушение становится ошибкой. [N05]

**Два контрпримера.** estimate₁ → sensitivity → estimate₂: корректный ранний prerequisite теряется, возникает ложный отказ. sensitivity₁ → estimate → sensitivity₂: позднее корректное появление dependent скрывает раннее некорректное. В локальных проверках воспроизведены оба направления; обычная последовательность двух разных методов остаётся положительным контролем.

**Предлагаемое исправление.** Индексировать и проверять конкретные node_id/occurrence, а FQN использовать для идентичности метода и поиска требуемого класса. Для каждого dependent проверить нужную предшествующую occurrence или явное ребро, не последний индекс имени. После этого отдельно уточнять предметные правила по тегам, не выдавая их за универсальные научные законы.

**Приёмка.** Повтор одной процедуры после промежуточной проверки не создаёт искусственную цикличность; ранняя чувствительность без нужного основания не становится допустимой благодаря более поздней оценке. Проверить два повторяющихся prerequisite и dependent, строгий и предупредительный режимы.

**Граница.** Некоторые из tag-based правил могут быть лишь эвристикой. Данный диагноз касается механики индексации, а не доказанности всех содержательных правил валидатора.

<!-- SOURCE_END B:B46 -->

