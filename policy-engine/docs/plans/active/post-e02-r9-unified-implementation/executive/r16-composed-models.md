# R16: что теперь должна уметь композиция моделей

**Основное решение:** развивать существующие исполнители, поиск, lineage и currentness как согласованную систему. Не добавлять ещё один универсальный scheduler. После приёмки E02 исполнитель получает восемь конкретных участков работ в 28 существующих задачах; общий реестр сохраняет 121 задачу. Продуктовые проверки здесь не запускались.

## Один policy case — несколько взаимодействующих моделей

Например, расчёт правила налогообложения передаёт household disposable income поведенческой модели; её response меняет налоговую базу; модель исполнения учитывает доступную административную capacity; joint fiscal model учитывает обе стороны; evaluator сопоставляет результаты с несколькими objectives. Подключение каждого метода само по себе недостаточно: нужны единицы и конструкты, population/support, время, explicit producer/consumer mapping и проверенная общая композиция. Равные имена slots не означают одинаковый смысл.

В ациклическом случае исполняется проверенный порядок. При одновременной взаимной зависимости нужен явный numerical coupling, а не случайный порядок вызовов. Для поведения во времени нужны initial state, clocks/events, наблюдаемая history и проверяемое восстановление состояния. Research cycle «гипотеза→проверка→новое evidence» имеет другую семантику, чем solver iterations. Ни сходимость, ни успешный execution не дают causal validity автоматически.

## Пересчитывать нужное, сохранять смысл

Новое наблюдение может изменить estimator; новая policy mechanism — structural program; scenario — hypothetical branch; новые права — допустимость использования уже рассчитанного результата. Последнее требует немедленной честной реакции currentness, но не обязательно нового numerical run. Эти виды изменений нельзя свести к одному «обновить модель».

Система хранит actual computational influence, включая отрицательные зависимости: если вчера FX rate отсутствовал, сегодняшнее появление тоже должно отменить прежний cache hit. Для непрозрачного метода без полного read-set допустим полный пересчёт выбранной области; нельзя объявлять неизвестные dependencies пустыми. Fine-grained reuse вводится там, где fresh recompute подтверждает его правильность и измерение показывает выгоду.

Прежний результат остаётся воспроизводимым в своей historical/as-of границе. Новая correction не переписывает то, что было известно в момент решения. Новый branch не может случайно занять current head другого branch; поздно завершившийся старый worker не заменяет уже принятое новое состояние. Отмена задачи отдельно подтверждается как фактическое завершение процесса.

## Обучение без самоподтверждения

Новая статья о прежней выборке не становится новым независимым исследованием. Model outputs, LLM hypotheses и remembered successful strategies влияют на поиск, но не превращаются в наблюдения мира. При коррекции или retract evidence требуется method-valid update либо lawful refit; сохранённый posterior summary не всегда обратим.

Разные механизмы могут одинаково объяснять старые наблюдения и давать разные interventional predictions. PolicyOS должен сохранять эти alternatives и предлагать различающее исследование. Probabilities, social weights и transport/calibration grounds не возникают по умолчанию. Полезный conditional result или обоснованное сохранение рекомендации — допустимый результат; сплошные отказы не считаются выполненной capability.

## Как выглядит free-grow

Conforming model подключается через existing registry/adapter без правки центрального списка семейств. Новый scientific/clock/state primitive может потребовать небольшого owning extension с conformance tests. Это честнее, чем обещать совместимость любой модели только потому, что она возвращает JSON.

Bazel/Skyframe полезен как образец dependence capture и change pruning, Differential Dataflow/Beam — для revisions/progress, Temporal — для разделения replay и effects, FMI/HELICS/BMI — для конкретных participant/time interfaces. Их механизмы изучены; переход на эти платформы не назначен обязательным. [Primary sources и native reuse anchors](../research/composition-reexecution-r16.md).

## Что получает исполнитель

- [Архитектура](../architecture/06-composition-and-reexecution.md): identities, changes, loops, currentness и reuse.
- [Восемь delivery slices](../solutions/16-composed-execution-and-revisions.md): решения, owners, шаги, migrations и required supplier boundaries.
- [17 наборов semantic checks](../assurance/10-composition-reexecution-quality.md): useful positives, adversarial и removal controls.
- [Реальная параллельность](../execution/08-composition-stages.md): подготовка по interface agreement и приёмка по реальным producer/consumer outputs.
- [Машинный план](../tasks.json) и [coverage](../assurance/r16-capability-obligations.json): additive требования без потери прежних обязательств.

Основные неустранимые документацией inputs: подходящие реальные модели, calibration/identification/transport grounds, права на данные и вычисления, реальные institutional outcomes. Их отсутствие ограничивает конкретное утверждение; оно не оправдывает недостающий внутренний bridge. Реализация, окончательная source verification и допуск применения остаются будущими работами после E02.
