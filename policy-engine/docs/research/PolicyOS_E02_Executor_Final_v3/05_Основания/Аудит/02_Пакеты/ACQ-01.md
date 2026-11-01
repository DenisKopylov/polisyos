# ACQ-01 — приобретённое основание должно дойти до зависимого расчёта
## B12 · LA-046, область acquisition | Проход C04 | 31 октября 2026 | v002

**Код:** `20d9009be21097bfbdc38a546a15cc60213b8ace`. **Режим:** read-only; product changes — нет. **Исходник задания:** [строки 616–772 E02](../05_Источники/ACQ-01_исходные_строки.txt). **Native запуск:** UNRUN. Чтение исходников и существующих проверок отделено от результатов прежних REQ-01 probes и новых изолированных CYC-03 diagnostics.

## 1. Главный вывод

**Сентябрьское описание «typed plan сохраняется, а исполнение находится только в else» больше не описывает рассмотренный `run`.** Теперь plan-путь передаёт связанный planner report в `_run_n7_acquisition_if_requested`; тот связывает compiler basis, world snapshot, capability resolutions, фактический gateway и вызывает `run_acquisition_closed_loop`. Присутствует и отдельный served action→native admission→world materialization→N5 continuation маршрут. Реализация не сводится к созданию DTO или выдаче URL. [S02](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L8500-L8800) [S09](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9300-L9600) [S10](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9590-L9790) [S14](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2000-L2250) [S16](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2460-L2680)

Более сильный последовательный тест проверяет новые epochs и фактическую смену контролируемых source bytes, сохранение прежней оценки при полной вычислительной эквивалентности и новый N5 при изменении входа. Поэтому рекомендация «написать отсутствующий мост acquisition» слишком груба и создаёт риск дублирования. Верная ближайшая работа — квалифицировать найденный мост и расширять конкретные неподдержанные случаи существующими владельцами. [S28](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L1-L260) [S29](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L260-L540) [S30](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L540-L820) [S31](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L820-L1030)

**Пакет в текущем аудите не закрывается целиком.** Свежая native-приёмка не выполнена; LA-046 содержит отдельный generic compiler/domain остаток из REQ-01; проверенная refresh-модель узкая и настроенная, а не универсальный механизм получения любого необходимого знания.

## 2. Что именно проверяется в E02

Исходный B12 требует не просто запросить данные, а провести их через фактического исполнителя и приёмку, после чего изменить зависимый расчёт. LA-046 добавляет сохранение содержания требования: text/domain/scope/явные constructs/реальный resolver, различение пустого результата и отсутствия потребности. Отдельные explicit-spec и typed-gap пути уже признавались существующими в самом исходном E02; их нельзя ретроспективно объявлять отсутствовавшими.

Содержательный тест должен различать три вида события:

| Событие | Что оно доказывает | Чего ещё не доказывает |
|---|---|---|
| Сформирован план | Определено допустимое следующее действие/потребность | Данные получены и приняты |
| Принят новый source occurrence | Владелец признал конкретное основание в конкретной области | N5 должен обязательно исполняться заново |
| Получена новая зависимая оценка либо обоснованно сохранена старая | Основание реально потреблено или его полная эквивалентность проверена | Причинная истинность, достаточность N8, право N9/публикации |

Последнее различие особенно важно: новое принятие может корректно завершаться retained evaluation. Нельзя заставлять систему производить фиктивный «новый» расчёт ради старой формулировки отчётного критерия.

## 3. Реальная цепочка владельцев

### 3.1. N6 формирует и сохраняет основание требования

`_plan_n7_requirement_gap_if_requested` вызывается только для acquisition terminal. Он сверяет форму request, включает cycle index, получает `_n7_data_requirement_basis_with_report`, сохраняет и перечитывает DataRequirementCompilationReport, строит типизированные gaps и planner input hash. Ссылки и report не только прикреплены к сообщению: downstream требует их согласованность. [S10](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9590-L9790)

Текущий `GenerationCycleRecord` дополнительно связывает selected candidate с grounding/simulation/value и requirement binding; acquisition routing evidence не может одновременно играть роль owner execution receipt. Эта предметная граница сохраняет различие «решили искать» и «действительно приобрели». В исследованном диапазоне моделей показана именно эта часть, не весь набор контрактов N7. [S34](../05_Источники/C03_C04_дополнительные_основания.md#s34)

### 3.2. Наличие плана больше не исключает попытку исполнения

В `run` после получения plan передаются именно его `planner_report` и `planner_report_ref` в `_run_n7_acquisition_if_requested`. Отсутствие plan выбирает другую ветвь вызова той же операции, а не единственную исполнимую ветвь. Старое расположение `else` не является текущим дефектом. [S02](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L8500-L8800)

Внутренний executor проверяет пригодность planner route, фактическое основание MeasurementRoot, спецификации и owner gateway. Отсутствие необходимых владельцев/сохраняемого planner ref даёт точную причину, а не успех. `run_acquisition_closed_loop` получает реальные связанные inputs, а не только family string. [S09](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9300-L9600) [S10](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L9590-L9790)

Это не означает, что любое чтение такого метода даёт право запускать сеть: расходы и внешние действия остаются за действительным job/permission owner. Ни live-fetch, ни платный provider в этом аудите не запускались.

### 3.3. Локальный receipt — не native admission

`_reenter_cycle_after_n7_acquisition` прямо ограничивает свой встроенный демонстрационный путь `authority_scope == contract_testing`. В остальных случаях локальный receipt не признаётся достаточным native основанием. Это не новый разрыв B12: комментарий и served composition отправляют разрешённое продолжение через `AcquisitionWorldGrowthBridge`. [S11](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L12000-L12400)

Убирать это различие ради зелёного локального теста было бы вредным: данные не становятся допущенными к конкретному использованию только потому, что одна функция вернула оформленный receipt.

### 3.4. Served route принимает источник и строит новый расчётный вход

Bridge заново разрешает текущий route через ControlPlaneService, актуальное действие, scope и исходный цикл. Затем получает verified passport и активированные observation bytes через существующий overlay owner. Выбранные receipts, epoch/passport и projection должны совпасть. Фактический reentry budget приходит из разрешённой конфигурации. [S14](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2000-L2250)

`_prepare_candidate_world_context` выбирает строку требуемой canonical variable, проверяет её единственность, base snapshot и profile/slot. Из фактической projection собирается подготовка Data Forge; Foundry формирует значения состояния и правила; существующий context owner готовит параметры модели. Затем `_candidate_world_context_handoff` действительно материализует snapshot, строит WMR, сверяет подготовленные значения с результатом, получает новый model/context offer, сохраняет его и читает заново в области выполняющегося job. [S15](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2250-L2460) [S16](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2460-L2680)

Таким образом, текущий путь делает больше, чем переименование WMR: новый вход проходит предметные преобразования. При этом преобразование контролируемое — точная выбранная строка и существующий slot, без неявного универсального вывода причинных механизмов.

### 3.5. После вычисления проверяется, что основание не подменено

Native-writer fence не удерживается на всём протяжении async N5. После вычисления bridge заново читает current growth/admission/projection, сверяет route selection и лишь затем сохраняет terminal reentry receipt. Отдельный operation lock защищает recovery pointers, но не объявляется доказательством замораживания всего мира на время расчёта. [S14](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2000-L2250) [S15](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2250-L2460)

Это полезная инженерная граница: не блокировать все записи на время дорогой работы, но и не публиковать результат после смены существенного основания как будто ничего не произошло. Полная межпроцессная стресс-приёмка этой синхронизации в данном аудите не выполнялась.

## 4. Отдельный механизм сохранения уже выполненного N5

`AcquisitionEvaluationBasis` и dispatcher — существующие owners, а не предлагаемая новая система. Они отделяют новое admission от значения фактически потребляемых inputs. В сравнении участвует полная поддержанная native quantity, включая state, правила, NCM, request/configuration и implementation witness. Это существенно сильнее проверки числа строк, same candidate_id или голого hash источника. [S20](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation.py#L1-L250) [S21](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation.py#L650-L900)

При подтверждённом совпадении dispatcher не просто возвращает старый receipt: он требует текущую cheap continuation, сохраняет новое основание и новый current-continuation ref, но сохраняет прежний selected N5 evaluation. При различии вызывается `resume`. При неизвестности совпадение не утверждается, а невозможность восстановить configuration оформляется как конкретный recoverable отказ. [S18](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py#L240-L440) [S19](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py#L800-L1080)

**Неопределённый либо неудачный новый N5 не должен возвращать старый успех под новой датой.** В прочитанном dispatcher при таком результате сохраняется новое ограниченное основание/свидетельство отказа, заменяющее выбранный старый success witness. Это сохраняемое поведение, а не причина убрать отказ ради непрерывности интерфейса. [S19](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation_dispatch.py#L800-L1080)

## 5. Что показывает существующее устройство тестов

### 5.1. Compiler и planner проверяются как реальные артефакты

`test_served_acquisition_binds_n7_compiler_and_planner_cas_before_reentry` вызывает настоящий resolver и затем убирает только выбранные compiler/planner CAS bytes, оставляя references и встроенные поля. Требуются адресные отказы `n7_compiler_report_readback_failed` и `acquisition_planner_report_readback_failed`. Это различающий контроль того, что потребитель действительно открывает артефакт, а не доверяет красивой форме. [S26](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py#L260-L580)

### 5.2. Входы действительно достигают state/model consumers

В том же тесте wrappers вызывают исходные reconciliation methods. Контроли меняют другую native-компоненту состояния при неизменном target, source_path binding, N5 baseline и выбранный NCM при той же декларации. Реальный consumer должен отказать. Потом исходный корректный вариант вызывается без замены результата. Это адресная проверка смысла связи, не только равенства ID. [S25](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_authority_served.py#L1-L260)

### 5.3. Соседний сценарий проверяет повторяемое развитие, а не один заранее удачный шаг

`test_served_actual_acquisition_retains_equal_b_then_reenters_for_c` проводит несколько новых epochs через обычные decision/human-approval/protected POST/worker операции тестовой среды. Два новых admission с эквивалентными inputs сохраняют вычислительные refs и bytes. При изменении source value возникает новый реальный N5, после чего новый GET видит всю последовательность. [S28](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L1-L260) [S29](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L260-L540) [S30](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L540-L820) [S31](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/core_runtime/test_acquisition_retained_sequential_served.py#L820-L1030)

Ограничение старого теста «new epoch только в oracle» не переносится на весь нынешний репозиторий: соседний test уже существует. Аналогично историческая заметка от 10 октября, где до/после были разные кандидаты и отсутствовал origin, не является сегодняшним диагнозом.

### 5.4. Граница доказательства

Все эти тесты **прочитаны, не перезапущены**. Их source profiles, HTTP-response bytes, gateway и settlement контролируемы. Это приемлемая форма безопасного integration-test; но она не измеряет качество внешнего источника, реальные расходы provider, полноту discovery или правильность причинной модели. Не следует ни обесценивать такой тест как «одни фикстуры», ни объявлять его фактом эмпирически подтверждённой политики.

## 6. LA-046 не закрывается одной успешной acquisition-композицией

[REQ-01](REQ-01.md) сохраняет ранее найденный source-контрпример `education_policy → fiscal`. Проверяемый commit не изменился; этот результат перенесён как **предыдущее ограниченное свидетельство**, а не повторно исполненный здесь compiler. Наличие работающего acquisition для настроенного government.balance не исправляет потерю переданного domain на другом adapter-пути.

Равным образом scoped fixture с готовым typed gap и resolver не доказывает, что произвольный текст самостоятельно превратился в правильный requirement. Для полной LA-046 нужно проверить обе области: generic/pilot interpretation и настоящий caller→receiver→consumer. Двойной учёт одного и того же LA-ID в двух пакетах исключён из реестра.

Исходное требование сохранить старую family-эвристику не возвращается. Его содержательная цель — не потерять полезную потребность — проверяется через явные constructs, candidate discovery, scope и реальный resolver. Возвращать unsafe lexical fallback ради сентябрьского preserve-пункта не назначается.

## 7. Главный предел универсальности найденного пути

Проверенная конфигурация явно выбирает `tenant/cell/run/route`, `profile_selection_ref`, canonical variable и world slot. `_prepare_candidate_world_context` требует **ровно одну** выбранную observation row. Comparison profile называется `controlled_acquired_observation_ncm_v1`; skipped execution scope прямо ограничен configured single-candidate N4 и NCM N5. [S12](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L1-L230) [S15](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_world_growth.py#L2250-L2460) [S20](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation.py#L1-L250) [S21](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/acquisition_evaluation.py#L650-L900)

Это объясняет, что именно уже построено: корректный узкий протокол переноса действительно принятого входа в настроенный модельный расчёт и экономного повторного использования. Это **не** доказательство, что для нового policy question система сама определит измеряемую величину, единицы, population/time, причинную роль, агрегацию множества строк, метод и допустимое преобразование.

Но из узости профиля не следует, что нужно удалить его или написать общий owner с нуля. Нужен второй содержательно отличный случай через существующие точки расширения: например, другой поддержанный slot/вход или многорядное измерение с явной агрегацией. Конкретный пример выбирается по фактически имеющемуся corpus/method, а не обещается заранее как реализованный.

Особенно важно различать входное значение и причинную структуру. Получение числа для baseline может изменить условный результат заданной модели, не доказав её коэффициенты, механизм или переносимость. Требование данных не должно подменять запрос к модели, ограничениям, лицензии либо полномочию.

## 8. Матрица состояния

| Область | Установленный результат | Сохранить | Остаток |
|---|---|---|---|
| B12, plan→executor | Plan больше не исключает executor; report/ref/basis реально передаются | Связанный реальный gateway и точные отказы | Native квалификация фактического пути |
| B12, source→world→N5 | Bridge materializes/readbacks actual controlled data/state/model/context и вызывает N5 | Data Forge/Fabric/Foundry/context owners, complete comparisons, leases | Другие реально поддерживаемые input/method profiles |
| B12, same inputs | Retained evaluation с новой current consequence, не фиктивный цикл | Старые численные bytes и новые source/admission refs | Native sequential test и downstream qualification |
| LA-046, compiler | Сохранены результаты REQ-01; source-based domain mismatch остаётся отдельным остатком | Explicit semantics и resolver; не возвращать heuristic | Настоящий generic text/domain/scope→resolver→consumer на двух областях |
| Эпистемическая сила | Acquisition и условный N5 не создают N9/публикацию | Ограничения source truth/currentness/causal credibility | N8 и empirical qualification относятся к своим пакетам |

## 9. Минимальные дальнейшие действия, без раздувания ремонта

**Квалификация:** исполнить уже существующий основной sequential selector в подходящей среде, затем точные removal/identity негативные контроли. Не начинать с массового CI или ещё одной вручную положительной модели.

**Локальный остаток REQ/ACQ:** исправление domain adapter должно проверяться настоящим compiler consumer, а не RecordingCompiler. После этого удостовериться, что две смысловые области дают разные обоснованные потребности и поступают реальному resolver. Старую историю нельзя переписать как новый успешный прогон.

**Развитие:** уменьшить объём case-specific настройки между вопросом и существующим controlled refresh. Новый корректный ресурс должен обнаруживаться и связываться через существующие typed boundaries. Неизвестные mapping/units/time/causal roles должны становиться точным запросом, а не искусственным числом.

**Экономия:** повторно использовать именно полную неизменную вычислительную задачу, при этом проверять новые source/rights/current consequences. Новая независимая реплика должна оставаться новой репликой, даже при совпавшем значении; равный filename не доказывает равные inputs, а разные receipt IDs не доказывают разные inputs.

**Не назначается:** новый acquisition runtime, второй world store, автоматическое полномочие по семейной строке, снятие native admission, blanket-пересчёт после каждого receipt или расширение одного fixture до универсального proof.

## 10. Доставка и следующая очередь

CYC-03 и ACQ-01 добавлены к накопленному досье. Предыдущие CYC-01/REQ-01 и их свидетельства сохранены; machine-readable register различает реализацию, пригодность теста, фактическое исполнение и остаток. Весь E02 содержит 127 пакетов; после этого выпуска подробно рассмотрены четыре, **123 ещё не рассмотрены**.

Следующий пакет исходного порядка — **CYC-04 (B10/B11): не теряется ли пригодная альтернатива за первым выбранным кандидатом и не блокирует ли денежная эвристика разрешённое содержательное исследование**. Открытая native-квалификация пройденных пакетов остаётся видимой, но не останавливает чтение всей очереди.
