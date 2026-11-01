# CTL-03 — стоимость, счётчики и типизированная пригодность
## C13 · выпуск v011 · 31 октября 2026 года

**Исходные задачи:** B120, B121, B123. **Область:** LANE-02; предшественник CTL-01; следующий пакет SRV-01. **Код:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. Репозиторий, зависимости и проектные тесты не изменялись.

## Решение по пакету

**Ограниченная проверка, не полная приёмка.** Исходные ремонты присутствуют: снимок фактического budget-owner доходит до stopping и отчёта; пригодная warm-history не расходует явно заданный счётчик новых обычных оцениваний; sentinel не обучает и не улучшает best; ошибочный присутствующий typed-вектор не превращается в отсутствие для выбора scalar-best. Существующие владельцы и предохранители сохраняются.

Воспроизведены три локальных остатка. Наиболее предметный — арифметика `scientific_evaluations`: sentinel, отвергнутый Stage A и не дошедший до Stage B, вычитается из числа обычных Stage B. Второй — generic sentinel-only поток не ограничен именно ordinary hard-limit, когда не задан иной конечный ресурсный предел. Третий — `CostBudgetStopping` принимает NaN как лимит, после чего этот критерий не останавливает никакой конечный расход. Последнее не означает обход отдельного durable-budget-owner.

Никакого вывода о выпущенной ошибочной политике, обходе protected publication, реально утраченных деньгах или полном отсутствии бюджетных защит этот проход не устанавливает.

## 1. Основание и критерий содержания

[Исходный E02](../05_Источники/CTL-03_исходные_строки.txt) требует исправлять именно существующий run-state/transition-owner: не создавать второй ledger, различать единицы счётчиков, не допускать scalar fallback из ошибки typed-результата и не запрещать законный legacy-режим. Исторические B-карточки — исходные контрпримеры, не автоматически сегодняшние дефекты.

Рабочая установка пользователя о LLM сохранена. LLM предлагает гипотезы и следующий содержательный шаг; алгоритмический слой должен надёжно учитывать реально выполненные и оплаченные действия, не путать контрольное испытание с новым кандидатом и не повышать невалидный результат по удобному скалярному числу. Создание универсального детерминированного генератора гипотез не требуется для закрытия CTL-03.

## 2. Карта результата по исходным IDs

| ID | Уже реализовано — сохранять | Конкретный остаток | Доказательность |
|---|---|---|---|
| B120 | State keys, refresh до/после работы, неизвестный расход не ноль; owner/run/event reconciliation; spent и reserved; корректный settled zero | C13-R03: конечность выбранного лимита; штатная provider→ledger→stop→report приёмка, цена и admission дорогого evaluator у его владельца | Тела budget/stopping исполнены с fixture owner; настоящий ledger/provider не запускались |
| B121 | Новый ordinary-counter вместо warm len(history), отдельные Stage A/B/sentinel counts; sentinel вне обычной истории и best | C13-R01: учитывать Stage B sentinel отдельно от раннего отказа; C13-R02: bounded physical work для generic sentinel-only; не представлять work count как accepted evidence | Полные blob-matched run_state/service + evaluator body, fixtures на зависимостях |
| B123 | Presence/invalid/missing различены; malformed сохраняет invalid и не обновляет best/frontier; законный scalar без typed остаётся | Настоящий ObjectiveStack, native DTO, source-owner и последующие consumers; квалифицировать разницу диагностического score в tell/full-run | Resolver prefix и consumers с явными Pydantic/score fixtures; не native PolicyEvaluationVector |

Полных закрытий не заявлено. LA-015 остаётся разделённым этапом CTL-01/SRV-03; чтение её соседей в CTL-03 не закрывает всю миграцию.

## 3. B120 — фактический бюджет уже проведён к потребителю

### 3.1. Исполненный переход

`_stopping_state` включает объявленные budget keys. `_refresh_budget_snapshot` берёт только нужные ключи и сохраняет независимый снимок. В source-bound режиме произвольное `context['cumulative_cost_usd']` не является источником USD: значение получается из владельца. `_NativeSearchServiceDriver` выполняет остановку перед генерацией, после её возврата и после оценивания. [S02–S05]

Ограниченные контроли: исходная стоимость 10 при лимите 1 дала ноль вызовов; стоимость 2 после первой оценки при лимите 1 остановила вторую; отсутствие, bool, строка и non-finite стоимость дали неизвестный бюджет и ноль вызовов, не мнимый нулевой расход. Настоящий ноль остаётся допустимым. [P02–P09]

### 3.2. Настоящая граница владельца в коде

`_read_source_budget_snapshot` проверяет exact BudgetState, owner identity, typed run binding, ключ `nl-run:<run_id>`, committed producer-events и наличие сумм. Сумма событий должна совпасть с spent. Остаток рассчитывается как `limit − spent − reserved`. После учтённой работы отсутствие событий не трактуется как её бесплатность. `_OwnerBudgetStopping` отказывает при неизвестном или исчерпанном остатке. [S03, S04]

В опытах state/store/events — **интерфейсные фикстуры**. Выполнена логика consumer, а не запись настоящего FileBudgetLedger. Согласованные spent=.25, reserve=.50, limit=1 дали remaining=.25, несмотря на caller cost=999. Foreign key, unknown settlement, mismatch spent/events, неверная owner identity и чужой тип state отказали. Явно committed событие с amount=0 осталось допустимым. [P10–P18]

### 3.3. C13-R03: NaN как значение лимита

В `CostBudgetStopping.__init__` проверяется лишь `max_cost_usd <= 0`. NaN не удовлетворяет этому условию, значит принимается. Затем `finite_cost >= nan` ложно: на расходах 0, 1 и 1e9 критерий каждый раз вернул `should_stop=False`. Это прямое свойство выполняемого Python-body без fixture ledger. [S05; P19]

**Влияние:** локально выключается объявленный monetary stopping criterion при недопустимой конфигурации. **Область:** прямой API / caller без независимого корректного ограничителя; реальная частота подобных значений не измерена. **Не следует:** выдавать это за обход подтверждённого durable-owner или уже полученное право расхода.

**Направление:** на существующей границе конфигурации проверять конечность и допустимый числовой тип/знак лимита. Не подставлять 0 или бесконечность вместо ошибочного cap. Если нужен unlimited-профиль, он должен быть именно объявленным профилем, не NaN. Контроль направления отверг NaN/inf/bool/0/−1 и сохранил нормальную остановку на 1; production не изменён. [P39]

### 3.4. Остановка не заменяет предварительное разрешение цены

Post-spend stopping в опыте закономерно позволил первому fixture-evaluator потратить 2 при пороге 1 и остановил следующий вызов. Это не измерение реального перерасхода: actual evaluator может иметь собственную reservation/admission. `TracedLLMCandidateGenerator` прямо ограничивает подтверждаемый договор генерацией кандидата; произвольный callback evaluator не получает автоматически такой же budget-owner. [S04]

Приёмка B120 должна проверить выбранного реального производителя, резервы, ошибки/retry, settled zero/cache и отсутствие двойного списания. Не надо создавать параллельный счётчик денег у search-controller. Найденный существующий autotune test использует реальные middleware/client/CAS classes, но fake HTTP response и контролируемую оценку; он здесь прочитан, не запущен. [S09]

## 4. B121 — разделение счётчиков сделано, но их арифметика не полностью согласована

### 4.1. Сохраняемые различия

`MaxIterations.check` использует `evaluation_iterations`, когда этот счётчик передан; fallback на len(history) остаётся самостоятельным ограниченным договором. Три совместимые fixture warm-записи плюс лимит двух новых оценок дали пять строк истории и две новые оценки. Удаление explicit counter вернуло преждевременную остановку по warm-history — различающий removal control. [S01, S02, S05; P20, P21, P38]

Два проходящих sentinel плюс один ordinary дали три Stage B, одну обычную запись и ordinary best. Sentinel с лучшим числом не стал best. Это полезная и сохраняемая защита от загрязнения обучения контрольными испытаниями. [P22]

`scientific_evaluations` в текущей модели означает число non-sentinel Stage B, а не число допущенных научных результатов. Один malformed typed-result уже увеличивает этот счётчик, хотя не становится promising или best. Поэтому его нельзя без отдельного основания читать как «получено научное подтверждение». Этот опыт записан как граница смысла поля, не новый дефект имени. [P36]

### 4.2. C13-R01: отклонённый до Stage B sentinel уменьшает число обычных Stage B

`apply_evaluation_transition` повышает `sentinel_evaluations` для любого sentinel-disposition. `apply_tell_transition` отдельно не повышает `stage_b_evaluations`, когда Stage A отверг кандидата. Но derived property равна `max(0, stage_b_evaluations − sentinel_evaluations)`. Таким образом, вычитаются счётчики разных множеств. [S01]

| Фактически выполнено | Сохранено |
|---|---|
| Sentinel: Stage A отказал; Stage B не вызывался | sentinel_evaluations=1 |
| Ordinary: Stage A и Stage B выполнены | stage_b_evaluations=1, ordinary history=1 |
| Реальное количество ordinary Stage B = 1 | scientific_evaluations=0 |

Контрпример дошёл через полный точный driver до итоговой telemetry, а затем отдельно воспроизведён через `_accept_tell` и тот же run-state. Оцениватели, record DTO и score-admission — fixtures; арифметика перехода и счётчиков — source code. Установлены обе локальные ветви, не пользовательский dashboard или внешний billing. [P23–P24]

**Влияние:** ложная статистика выполненной работы; возможное влияние на потребителя квоты, если он использует это поле. Последнее — риск, конкретный downstream stop по `scientific_evaluations` не найден и не заявлен.

**Направление:** различать попытки sentinel и именно выполненные sentinel Stage B у единственного state-owner; вычислять разность только на одинаковой базе. Не добавлять sentinel в обучающую историю, не уменьшать Stage B count, не исправлять посредством ещё одного `max(0, ...)`. Проверить full/tell и ранний Stage A отказ. Для настоящего acceptance нужны реальные record/DTO и обе API-формы.

### 4.3. C13-R02: hard-limit не ограничивает generated sentinel-only поток

И внешний while, и внутренний batch check сравнивают `evaluation_iterations` с `max_iterations_hard_limit`. Sentinel-transition намеренно не увеличивает эту величину. Поэтому оба ограничения защищают ordinary evaluations, а не всякую фактическую работу. [S01, S02]

При `MaxIterations(1)` и hard-limit=1 scripted generator вернул пять sentinel-кандидатов. Выполнены пять Stage B, ordinary count остаётся 0. Шестое обращение остановлено **audit watchdog**, не PolicyOS; бесконечный процесс не запускался. Отдельный контроль с реальным по логике cost criterion остановил поток после двух fixture расходов. [P25–P26]

**Существенный положительный контроль:** штатный `SentinelInjector.inject_batch` добавляет контрольные примеры между настоящими предложениями и не превращает пустой batch в sentinel. Его source-body прошёл контроль ordinary=2/StageB=3 с конечным завершением. Значит, находка не утверждает, что штатный injector сам генерирует бесконечные sentinels. Она относится к generic generator профилю, допускающему такой поток без независимого конечного cap. [S07; P40]

**Направление:** сохранить ordinary budget и назначить конечный предел фактически выполняемых контрольных/генераторных работ или обязательный независимый ресурсный предел для соответствующего профиля. Не приравнивать sentinel к обучающему примеру и не считать большее число вызовов новым научным прогрессом. Нет необходимости в новом scheduler; владелец state/stopping уже существует.

## 5. B123 — ошибочный typed-result больше не превращается в scalar-best

Resolver проверяет наличие ключей `policy_evaluation`, `policy_evaluation_bundle`, `_policy_evaluation_bundle` отдельно от их truthiness. Если ни одного ключа нет, возвращается missing; если заявленный typed input не может быть восстановлен и нет применимого stack, возвращается invalid с причиной. Ошибка импорта typed-владельца тоже не выдаётся за отсутствие режима. Полный `_evaluate_candidate` при invalid не вызывает scalar-objective и не обновляет best/frontier. [S03]

В локальной цепочке None, лишнее поле, список, bool и явно null bundle не заменили безопасного прежнего кандидата. Missing optional typed input позволил законную scalar-оценку. Валидная форма без подтверждённого source-owner оставалась `source_unverified`; положительный fixture source давал соответствующий исследовательский путь. Removal control, заменяющий invalid на missing, снова выбрал недопустимый scalar-best −100: проверка различает исходную ошибку. [P27–P34, P37]

**Граница:** `VectorFixture` — специально малый Pydantic DTO, не настоящий `PolicyEvaluationVector`; полный ObjectiveStack, protected source-owner, реальный registry/frontier и публикация не выполнялись. Из исполнения ветвей нельзя вывести полное закрытие B123.

### 5.1. Tell и полный run различаются диагностически

`_accept_tell` сохраняет invalid policy и блокирует best/frontier/is_promising, но может отдельно вычислить scalar assessment из предоставленных `simulation_results`. В опыте он сохранил scalar-status AVAILABLE при policy-status invalid, не изменив best. Полный run scalar не вычислял. Это **не автоматически повтор B123**: исходный план разрешает сохранять полезное численное вычисление без его повышения в допустимый результат. [P35]

Нужен адресный consumer-test: никакое чтение отдельного AVAILABLE не должно терять invalid policy при выборе/обучении/публикации. В текущем проходе такая downstream утечка не установлена. Не следует насильно стирать корректное число ради одинаковых записей или объявлять обход без проверки фактического потребителя.

## 6. Имеющиеся тесты и следующая содержательная приёмка

В `test_srv_01.py` уже есть stage-A rejection без Stage B, disabled Stage A, unknown/duplicate IDs и `test_malformed_typed_feedback_cannot_fall_back_to_scalar_best`. Они нужны и не заменяются файлом с названием CTL-03. Простой Stage A rejection тест не пересекает этот случай с ролью sentinel, поэтому не различает C13-R01. [S08]

Прочитан реальный caller test `test_autotune_runner_binds_real_provider_call_to_durable_budget_owner`: реальные client/middleware/FileBudgetLedger/FileSystemCAS в коде теста, контролируемые bytes HTTP и benchmark-evaluator. Неверная wire cost должна оставаться unavailable, а caller cost=1000 не заменяет настоящую стоимость. Это полезная составная проверка, **UNRUN в данном выпуске**. [S09]

Дальнейшая приёмка у существующих владельцев: (1) реальные DTO и источник оценки → malformed/absent → обе best/frontier ветви; (2) ledger run binding, резерв и cache/failed call → stopping/report; (3) ordinary + passing sentinel + rejected sentinel с независимым счётчиком actual Stage B; (4) явно выбранный sentinel-only профиль с конечной остановкой и сохранённой работой. Полная приёмка SRV-01/SRV-03 отдельно проверяет actual ask/tell consumer и lifecycle.

## 7. Проверка, окружение, преемственность

40 ограниченных наблюдений, 40 MATCH / 0 ERROR в финальном запуске. Среди них четыре строки трёх остатков, две диагностические границы, два removal controls, один direction-control и blob integrity. MATCH означает совпадение записанного ожидания, включая воспроизведение дефекта, не product PASS. [Журнал](../04_Проверки/C13_CTL03/bounded_diagnostics.json)

Первый старт harness завершился до наблюдений: временный модуль для dataclass не был зарегистрирован в sys.modules. Исправлена только регистрация собственного fixture module; исходный script/log и точная классификация сохранены. Никакая продуктовая ошибка не была «исправлена» ради зелёного результата.

Cloud CPython 3.13.5; contributor baseline — Python 3.14.x. Полный checkout не получен: прямой сетевой запрос raw source в контейнере завершился DNS error. Fresh code read выполнен GitHub connector, не кэшированным публичным web-view. Зависимости не устанавливались. **Native PolicyOS pytest, полный ObjectiveStack/DTO, provider, durable ledger, CAS/HTTP и научная модель — UNRUN.**

Прежний v010 из разговора — основная база. Library содержит другой v010 с тем же именем и дополнительным StrategyAdapter-разбором; его отличающиеся и дополнительные bytes сохранены отдельной ветвью, не смешаны с результатами C12/C13. [Согласование](../06_История/Согласование_v010.md). 12 предыдущих пакетных отчётов сохраняются побайтово без переаттестации.

## Первичные источники

**S01** — [policy-engine/src/polisyos/scientist/methods/search/run_state.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/run_state.py); диапазоны [[1, 126]]; blob `b4f980de235263513c7ad7e5771e1ccfbb3d8b3d`. Full current read; archived complete source blob rechecked and executed with contract fixtures.

**S02** — [policy-engine/src/polisyos/scientist/methods/search/service.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/service.py); диапазоны [[180, 326]]; blob `bcc87e32cc1903888845a557a729f6dcf6b182b2`. Targeted fresh read; complete C12 source rechecked by current blob and executed; external owner seams are fixtures.

**S03** — [policy-engine/src/polisyos/scientist/methods/search/lifecycle.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/lifecycle.py); диапазоны [[645, 960], [960, 1188], [1250, 1580]]; blob `754e942a21b3198c3989ac9175c54342b6c67ab3`. Transcribed bodies; resolver executed only through no-stack prefix; prior same-commit accept_tell/finish bodies reused; full native imports UNRUN.

**S04** — [policy-engine/src/polisyos/scientist/methods/search/controller.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/controller.py); диапазоны [[107, 166], [1145, 1370]]; blob `4b25698f56165167e10b7f79a97753ec1d84f342`. Stop body executed; provider/client binding read-only.

**S05** — [policy-engine/src/polisyos/scientist/methods/search/stopping.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/stopping.py); диапазоны [[285, 480]]; blob `dda3875d68e1dd43002835ee332270cf3d4e23b5`. Concrete stop bodies executed; MaxIterations source from prior same-blob excerpt, freshly cross-checked source identity, project import UNRUN.

**S06** — [policy-engine/src/polisyos/scientist/policy_design/objectives.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/policy_design/objectives.py); диапазоны [[1, 290], [500, 645]]; blob `f4ea1089b4dc63d3ffb22f0e92a610de6c115e49`. Read-only; not the simplified VectorFixture used by diagnostic harness.

**S07** — [policy-engine/src/polisyos/scientist/methods/search/sentinels.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/scientist/methods/search/sentinels.py); диапазоны [[1, 120], [170, 245]]; blob `85409acfc8042bf3df14f78b0e291979a5495f96`. inject_batch body executed with explicit candidate/set fixtures; full CAS/class imports UNRUN.

**S08** — [policy-engine/tests/unit/remediation/test_srv_01.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/remediation/test_srv_01.py); диапазоны [[1, 335]]; blob `5a52ea0584e7844d1dea31afacc9cfebaf3db4ce`. Read, not executed.

**S09** — [policy-engine/tests/unit/scientist/search/test_search_loop.py](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/unit/scientist/search/test_search_loop.py); диапазоны [[1140, 1325]]; blob `9f595575ea54d2b2cd22802363c100eac0aecce3`. Read selected test body, not executed; fake provider transport and controlled evaluator, real production middleware/client/CAS classes in test code.

**S10** — [policy-engine/CONTRIBUTING.md](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/CONTRIBUTING.md); диапазоны [[1, 20]]; blob `8ff414198e306e671abff1f76f31330a1f29d765`. Python 3.14 baseline; audit cloud Python 3.13.5.

[Машиночитаемый индекс](../05_Источники/C13_источники.json) · [остатки](../01_Реестры/C13_остатки.json) · [границы](../04_Проверки/C13_CTL03/Чтение_и_границы.md).
