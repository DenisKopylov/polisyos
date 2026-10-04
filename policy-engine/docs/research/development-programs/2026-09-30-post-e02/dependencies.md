# Зависимости повторное использование и отрицательные связи

[Обзор](README.md) · [Сценарии](roadmap.md) · [Структурированный граф](dependencies.json)

## Как читать граф

Связь относится к **конкретному артефакту и приращению**, а не требует завершить всю upstream программу. Если нужный вход уже существует и пригоден, новую программу его создания запускать не надо. Исследовательская обратная связь не является взаимной календарной блокировкой.

Типы связей:

- **Вход:** без указанного результата выбранный claim нельзя получить
- **Общий актив:** одна и та же функция может обслужить два consumers; это пока не доказанная экономия
- **Комплемент:** два компонента дают пользу совместно, которую нельзя корректно оценить по одиночке
- **Обратная связь:** новый результат меняет следующий исследовательский вопрос, не передавая назад authority
- **Условие употребления:** отдельное scientific, security, human или institutional основание только для требующего его band
- **Конкуренция:** общий owner, reviewer, память, quota или меняющийся контракт ограничивают параллелизм
- **Негативная связь:** совместное использование может переносить ошибку, раскрывать holdout или уничтожать возможность будущего вопроса

## Основные предметные связи

| Откуда → куда | Тип | Передаваемый объект и точное условие |
|---|---|---|
| E1 → E2 | Вход | Source/measurement relation, если identification или transport требует именно её |
| E2 → E1 | Обратная связь | Различающее измерение, связь или source profile для того же target |
| E1 → M1 | Вход | Observation frame, единицы, время, missingness/censoring и нужная совместность |
| E2 → M1 | Условие употребления | Causal interpretation только при identification/transport premise; обычный прогноз не ждёт причинного certificate без нужды |
| M1 → P1 | Вход | Тот же target и joint evaluation alternatives; может быть existing native result |
| P1 → P2 | Общий актив | Неизменная идентичность действия, ресурсы и evaluator; full static programme completion не prerequisite |
| M1 → P2 | Вход | Transition/signal model и доступный information set; empirical или явно stipulated |
| P3 → P1/P2 | Вход | Материальные shared capacity, calendars, exposure или response constraints |
| P1/P2 → M2 | Общий актив | Предварительный prediction и exact intended/deployed rule; retrospective existing prediction также подходит |
| E1/P3 → M2 | Вход | Observation и delivery evidence, позволяющие различить причины residual |
| M2 → E2 | Обратная связь | Candidate hypothesis или competing explanations и полезный следующий опыт |
| M2/O3 → M1/P1 | Вход | Отдельно допущенная новая world branch, действительно прочитанная следующим циклом |
| WP01/WP02 → O3 | Условие употребления | Принятое update policy и научное основание; не блокирует весь O1/O2 |
| O1 AND O3 → DS21 | Вход | Обе backend capabilities; O2 optional |
| N → M1/P1/P2/P3 | Общий актив | Target-preserving plan, когда numerical workload действительно общий |
| R → E1/E2/N | Общий актив | Улучшенное исследовательское решение на unseen задачах; ordinary routing остаётся baseline |
| H → все human consumers | Обратная связь | Наблюдаемая ошибка понимания меняет представление и workflow, не научную истину |
| A → E1/E2/M1 | Вход | Разрешённый holder output только для недоступного иначе нужного input |
| C → все | Общий актив | Native source/target/assumption versions и exact historical/current use semantics |
| E02 exact output → selected consumer | Вход | Только конкретный version-pinned repaired результат и его границы; не общий green label |

## Комплементы которые нельзя ранжировать по отдельной отдаче

### Измерение и калибровка общего nuisance

Дополнительный канал может сам по себе не уменьшать uncertainty целевого параметра, но вместе с другим измерением устранять общий nuisance. Это известный конечный контрпример универсальному greedy selection. Полезность возникает только при настоящем общем nuisance и совместимой noise law. Оплачивается проверяемая пара против сильного прямого измерения, а не любые два источника с похожими именами.

### Действие и его оценка

Хорошие objective vectors без сохранённого исполнимого действия не дают повторного выбора. Сохранённое действие без пригодной оценки также недостаточно. Native ParetoRegistry уже содержит существенную часть этой пары; новый bridge финансируется лишь по отсутствующей точной связи.

### Процесс наблюдения и диагноз

Новый cause classifier может не помочь, пока непонятно, что означает timestamp, исчезнувший case или смена регистрации. Общий source/process профиль способен дать большую часть полезности M2. Но основание атрибуции и heldout проверка остаются отдельными от механики журнала.

### Совместные ограничения и адаптивное продолжение

Допустимое сегодня действие может уничтожить все допустимые будущие продолжения. Для P2 action identity, available history и viability проверяются вместе. Статическому D1 это не создаёт обязательства заранее покупать общий controller.

## Где синергия установлена а где ещё предполагается

Подтверждённые source-level связи включают: packet→ClaimLedger owner; publisher→current owner export и public replay; policy runtime→predictive VOI report→packet; Scientist controller→ParetoRegistry; Calibrator→measurement adapter; transport node→catalog registry. Они дают основания для reuse существующего кода, но не измеренную денежную экономию нового портфеля.

Синергия нового приращения считается заработанной только после названного общего output и двух **действительных** consumers с одним смыслом. Два будущих блока на схеме дают гипотезу. При смене source family, information regime, законного use или scientific target часть setup и почти вся проверка могут понадобиться заново.

## Реестр уникальных затрат первого портфеля

Это правила учёта и предварительные work nodes, не смета реализации и не новый task register.

| Work node | Результат | Где считать | Что исключить |
|---|---|---|---|
| W00 Выполненная source/owner сверка | Это предложение, source census, named code boundaries | Уже выполненное исследование; будущий бюджет её не повторяет | Ещё один generic corpus audit |
| W01 Точное чтение выбранного repaired пути | D1 output/consumer и фактический остаток после E02 | Один bounded discovery node выбранного среза | Отдельная «подготовка» в каждой программе |
| W02 Модель D1 и exact reference | Все восемь наборов, constraints, objectives и value semantics уже заданы и аналитически проверены в этом исследовании | Повторная разработка этого reference не нужна; будущие production-harness, native reload и consumer проверки учитываются отдельно, только если требуются | Повторный бюджет derivation либо общий P10 foundation budget |
| W03 Доказанно отсутствующее native изменение | Конкретная action/evaluation/consumer функция | Только если W01 нашёл полезный остаток | Новый registry, simulator и уже работающие carriers |
| W04 Сквозная проверка D1 | Reload, consumer-removal, material/harmless controls | V выбранного пакета | Ещё одна оплата тех же tests под assurance |
| W05 Источниковая квалификация D2 | Exact bounded source, definition, IDs, units/time/rights | E1/D2, если inputs доступны и задача выбрана | Полный D0–D5 rebuild и фиктивный live positive |
| W06 Источниковый oracle D2 | Независимый ручной source-level расчёт | Отдельная предметная проверка E1 | Считать D1 enumerator тем же scientific gold |
| W07 Общий artifact/readback | Только недостающий общий contract или reader | Один owner, несколько конкретных consumers | Второй CAS, ledger, packet или universal schema |
| W08 Полный cost trace | Actual D/A/B/I/V, compute, waiting, rejected work и review | Один инструментальный output при совместимости | Складывать provider billing и тот же allocated usage дважды |
| W09 Новая migration/compatibility | Только затронутые old/new readers и сохранённая история | I/V конкретного semantic change | Всё дерево прежних cleanup-планов |
| W10 Независимая O/FA1 граница | Точный stronger use, если он нужен | Отдельный conditional decision/operation tranche | Разносить этот cost на все candidate вопросы |

Общая цена выбранного портфеля могла бы складываться из уникальных новых nodes, integration/requalification и действительных внешних затрат. Сейчас их scope и actual effort ещё не измерены, поэтому числовой total не приводится. Нельзя суммировать standalone estimates программ и затем механически вычесть процент «синергии».

## Отрицательные связи

1. **Общий источник умножает ошибку.** Неверная identity/unit/measurement relation одновременно портит calibration, policy choice и retrospective validation. Нужен понятный радиус зависимых выводов
2. **Общая память раскрывает оценивание.** Learning, challenges, user feedback и cached summaries могут показать heldout evidence. Разные процессы не гарантируют независимость
3. **Ранний screening необратим.** Потерянный exception, subgroup или допустимый candidate downstream уже не восстановит большее число simulation draws
4. **Сжатие уничтожает будущие вопросы.** Marginals вместо joint law, один rollout вместо rule, aggregate без document ID, выбранный winner без alternatives сокращают option value
5. **Currentness может стать all-refusal.** Слишком широкая invalidation лишает полезности, слишком узкая оставляет silent stale. Нужны material и unrelated controls
6. **Оптимизация KPI меняет наблюдение.** Policy может улучшить отчётность, а не независимый outcome; прежний holdout теряет смысл
7. **Слишком общая schema увеличивает цену второго кейса.** Придётся мигрировать множество consumers ради одного нового statistical target
8. **Общий verifier создаёт общий blind spot.** Перенос harness допустим, перенос чужого gold и guarantee — нет
9. **Больше альтернатив увеличивает человеческую нагрузку.** Более широкий frontier может ухудшить решение без подходящего представления и explicit values
10. **Новая protected authority создаёт эксплуатационный хвост.** Retention, rotation, independent deployment и revocation не заканчиваются после первого receipt

## Что можно делать параллельно

Параллельны независимые source profiles, аналитический finite reference, отдельные native modules с уже выбранным смыслом и независимая проверка замороженных inputs. Необязательно ждать окончания E1 целиком, чтобы исследовать P2 на честной stipulated модели.

Сериализуются смысловое решение одного shared contract, совместимый publish/migration, финальное подключение к меняющемуся consumer и отдельные решения principal. Coding agents конкурируют за RAM/I/O/quota, но часто ещё сильнее — за компетентный review и shared-owner integration. Их число не является делителем нормированного труда или календаря.

Активировать следующую ветвь стоит по доступному различающему основанию и очереди проверки. Набор всех допустимых опций одновременно — не рекомендуемый начальный портфель.
