# CYC-01 · Штатный вход и связанные контексты N4/N5

**Исходные IDs:** B01, B02, B03. **Очередь:** LANE-01, первое место исходного E02.  
**Срез:** `20d9009be21097bfbdc38a546a15cc60213b8ace` · 31 октября 2026.  
**Вид результата:** углублённый анализ текущих участков кода и устройства существующих проверок; новый product-runtime не исполнялся. Полное закрытие пакета не присваивается.

[Исходный раздел](../05_Источники/E02_исходный_план.md#bundle-cyc-01), строки 174–296; [пронумерованный текст](../05_Источники/CYC-01_исходные_строки.txt). Исходные наблюдения относятся к сентябрьской базе, а не автоматически к сегодняшнему коду.

## 1. Вывод

**Первоначальное описание трёх полностью несвязанных переходов уже не соответствует всему прочитанному текущему пути.** Штатный job-owner явно передаёт отсутствие root EvalSafety-context для соответствующего режима; после компиляции задачи вызываются владельцы контекста; рекурсивный лист получает её собственное основание; `JointSimulationPort` содержит сборщики запроса и вызывает настоящий horizon controller. Найден тест публичного HTTP→worker→N5→GET пути с реальным N5 и сохранённым результатом.

**Сохранять нужно именно эти механизмы, а не начинать новый ремонт по историческому описанию.** Одновременно найденная положительная тестовая конструкция заранее готовит конкретный профиль и модель. Из неё нельзя вывести способность самостоятельно выбрать и собрать основание для нового произвольного вопроса. Существование тестового кода без нового исполнения не выдаётся за PASS.

Два вывода разделены намеренно. Ограниченный CYC-01 может быть принят после проверки настоящего разрешённого маршрута в его области. Более широкая способность «новая задача → автоматически разрешённый модельный контекст» остаётся самостоятельным вопросом универсальности, связанным с S02/S08; она не должна превращаться в бесконечно передвигаемый критерий каждого небольшого bugfix.

## 2. Зачем этот пакет нужен проектировщику политики

N4 формирует кандидатов вмешательств; N5 вычисляет их последствия в модели; N6 организует итерации; N8 потребляет пригодный результат для оценивания. CYC-01 должен позволить обычному запросу добраться до содержательного вычисления без того, чтобы пользователь вручную конструировал внутренний Python-object, уже содержащий будущую скомпилированную задачу.

При этом программная доступность вычисления и обоснованность модели — разные вопросы. Условная симуляция может быть полезной даже на явно ограниченной модели. Она не становится эмпирическим эффектом или разрешением внешнего действия. Правильный результат этого пакета — воспроизводимый, предметно связанный вход в расчёт, а не исчезновение всех ограничений authority.

Конституция проекта описывает полезные ограниченные результаты, разделяет генерацию и обоснование и требует развития способности через корпус и discovery. North Star требует причинных, а не просто корреляционных связей и отличает отдельные вмешательства от их совместного состава. Это основания для оценки цели, не готовые научные гарантии реализации. [Vision, §1–2](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md#L40-L103); [Rule 12 и §6–7](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md#L198-L290); [North Star](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/docs/system-design-decisions/policy-design-causal-operating-system-north-star.md#L52-L110).

## 3. Сводка по исходным задачам

| ID | Исторический барьер | Что найдено сейчас | Остаток в этой проверке |
|---|---|---|---|
| **B01** | Внутренний root evaluation-context требовался ещё до создания DesignProblem | Явные режимы, sentinel против explicit None, ordinary worker передаёт None; защищённые режимы сохраняют отдельные preconditions | Новый исполняемый результат обычного входа; прозрачная граница между пользовательским запросом и заранее подготовленным серверным основанием |
| **B02** | Снятие раннего отказа не доставляло данные/модель в нижние стадии | Post-compile context resolvers, persisted handoffs, maps по узлам, реальный приём context рекурсивным GenerationCycleController, проверки problem/WMR/source membership | Исполнение связанного маршрута и различающих подмен; дальнейшая версия основания отдельно в CYC-03 |
| **B03** | N5 ожидал готовый request или callable вместо штатной сборки | Data-only builder и два profile-bound пути, WMR/CAS resolution, настоящий `_controller.run(request)`, persistence результата | Не считать разрешённый список ресурсов доказанной универсальностью; проверить постановку и повторное чтение точного входа на фактическом served пути |

Статусы «найдено» и «исполнено» не смешаны. Нет основания писать, что B01–B03 полностью отсутствуют в реализации, но нет и нового основания объявить их окончательно принятыми на текущем runtime.

## 4. Прослеженный путь: от HTTP-запроса до вычислительного owner

| Переход | Конкретная реализация | Что установлено чтением |
|---|---|---|
| Job → компиляция | [`job_nl_execution.py`, 150–350](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/job_nl_execution.py#L150-L350) | Режим и verified scope передаются явно; actor/tenant/cell и producer binding проверяются до LLM-работы |
| Компиляция → предмет задачи | [`compile_and_run_recursive_generation_cycle`, 1600–1880](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1600-L1880) | Создаётся настоящий DesignProblem; raw request сверяется; отсутствующий EvalSafety-context не равен отсутствующему режиму |
| Предмет → контекст | [Тот же owner, 1880–2150](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1880-L2150) | Resolver получает уже построенный problem; handoff перепроверяется у владельца; N4-source сохраняется и перечитывается |
| Контекст → рекурсивные листья | [HTTP dispatch, 2580–2780](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L2580-L2780), [recursive owner, 3000–3270](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3000-L3270) | Передаются конкретные maps по узлам; контекст ребёнка связан с его задачей, а не только с родительским ID |
| Лист → N6 | [Recursive route, 3450–3630](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3450-L3630) | Реально создаётся GenerationCycleController с context, store и handoffs; проверяется потребление context и вызывается `run` |
| N5-порт → постановка | [Dispatch, 4020–4270](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4020-L4270), [builder, 4830–5170](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4830-L5170) | Используются typed/persisted inputs или предусмотренный data-only builder; повреждённые привязки имеют адресные исходы |
| Постановка → движок → артефакт | [4270–4475](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4270-L4475) | Присутствует настоящий `_controller.run(request)`; результат связывается с input/state и сохраняется через existing CAS owner |
| Артефакт → публичное чтение | [Код served-теста, 930–1240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L930-L1240) | Тест требует нового GET и согласованных source/context/input/result refs с ограниченным назначением |

Это source trace конкретных переходов, не исполненная end-to-end трасса. В частности, не выполнены все ветви N6, все numerical runners и весь public reader. Отдельные большие файлы прочитаны в указанных диапазонах; остаток файла не объявлен проверенным.

## 5. B01: вход больше не требует одного и того же уровня допуска для любой работы

### Что изменилось

В HTTP composition default параметра `root_evaluation_context` — специальный sentinel. Непереданное решение отвергается, но **явное `None` — поддержанный выбор**, а не автоматически ошибка. Настоящий worker передаёт execution intent и `None`, когда evaluation-safety объекта нет. Это устраняет важное прежнее смешение «не определён режим» и «для этого режима пока нет полномочного evaluation-контекста». [Входная логика](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1600-L1775); [actual caller](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/job_nl_execution.py#L290-L350).

Для защищённого evaluation-режима контекст всё ещё необходим: проверяются его canonical type, mode и evaluator owner. DataTrust не маскируется EvalSafety: данный композиционный путь честно сообщает, что соответствующий owner bridge не подключён. Для LLM-работы реальный job-owner отдельно проверяет actor, tenant/cell, lease и producer/budget binding. Эти требования нельзя снять под предлогом «разрешим исследование».

### Что нужно сохранить

Сохраняются server-owned mode selection, предварительное право на реально используемый ресурс, различие candidate/simulation/защищённого оценивания, защита от чужого scope и проверка raw request после компиляции. Наличие container-owned verifier или promotion runtime как инфраструктурной зависимости **не доказывает**, что пользователь должен получить публикационный мандат до любой симуляции. По одной проверке `is None` такой вывод делать нельзя.

### Что остаётся

Необходимо подтвердить обычный публичный вход на текущей квалифицированной сборке и показать, что клиент передаёт только предназначенные ему поля. Подготовленная серверная конфигурация допустима и не является дефектом сама по себе. Но её наличие и цена должны быть видны: ручная сборка каждого предметного мира оператором не превращается в универсальное автоматическое проектирование только потому, что Python-context исчез из HTTP payload.

**Приёмочный смысл B01:** обычный запрос доходит до разрешённой операции; запрещённое действие или чужой доступ не проходят; частично выполненная кандидатная работа не теряется. Требовать здесь положительного N9 или правдивого эмпирического утверждения о любой политике — неоправданно расширять локальную задачу.

## 6. B02: текущая передача контекста уже не является пустым аргументом

### Найденные механизмы

Post-compile resolver получает фактический DesignProblem. Результат либо canonical CycleSubstrateContext, либо typed handoff с соответствующим контекстом. Generic route дополнительно сопоставляет exact admission owner, leaf owner и issued worker scope. Реальный N4-source сохраняется и перечитывается с проверкой problem, результата и context hash. [HTTP composition](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1880-L2150).

Рекурсивный owner не ограничивается хранением map. Он проверяет denominator узлов, принадлежность handoff листу, problem ref и соответствие context. Для детей создаются persisted capsules и currentness callbacks у canonical leaf owner, чтобы ребёнок не мог заимствовать разрешение соседа. Затем actual route создаёт GenerationCycleController с конкретным context/store/handoff и проверяет, что context не проигнорирован. [Проверки maps/capsules](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3000-L3270); [потребление листом](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/recursive_generation_cycle.py#L3450-L3630).

На N5-boundary `revalidate_cycle_substrate_context` сопровождается проверкой problem/domain, atom-world identity и всех supplied WMR refs. В profile-bound пути selected registry и NCM сопоставляются с exact WMR views; кандидат обязан существовать в сохранённом N4-source. [Generic builder](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5000-L5170); [WMR-binding](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5620-L5770).

### Как читать старое требование «один и тот же контекст»

Его полезный смысл — **одинаковое основание той же операции на всех границах**, а не неизменный object identity для всей рекурсивной системы. Ребёнок может иметь другой предмет и допустимую проекцию; новая версия данных должна дать согласованное новое основание. Использование одного старого context при изменившейся задаче как раз возвращало бы B27.

Локальный `controller._cycle_substrate_context is context` полезен как проверка того, что переданный объект действительно принят этим вызовом. Из него не следует требование общей ссылки для разных child nodes, processes или versions. Передача по typed persisted ref с правильным readback остаётся содержательно корректным вариантом.

### Что не следует переписывать

Не нужен второй world store, новый параллельный context DTO или снятие hash-проверок. Сохраняются существующие owners, различие профиля выбора и текущего problem hash, scoped capsules и версия historical replay. Поиск новых пробелов начинается с фактического движения этих объектов, а не с предположения, что отсутствие отдельного `test_cyc_01.py` означает отсутствие проверки.

### Остаток

Текущее чтение устанавливает передачу и проверки, но не заменяет исполнение. Нужен положительный runtime-путь с настоящими владельцами и контролируемыми заменами: другой problem; другой WMR; иная selected registry/version; чужой child context. Смена действительно значимого основания должна либо корректно перевыпустить привязки, либо дать точную несовместимость. Этот второй вопрос будет разобран в CYC-03, где он является непосредственным предметом задачи.

Сама идентичность артефактов доказывает, что система использует именно выбранные bytes и scope. Она не доказывает, что причинная модель подходит для политики, что данные подлинны или что единицы сопоставлены верно. Эти предметные обязанности сохраняются у своих пакетов; добавлять ещё один hash вместо проверки применимости бессмысленно.

## 7. B03: builder существует; остаётся проверить, кто содержательно ставит расчёт

### Обычный data-only builder

`_build_joint_simulation_request` уже собирает запрос из candidate, связанного WMR, интервенционных atoms, outcome, horizon, разрешённого resource и budget ref. Отсутствующие resource/budget/horizon дают конкретные причины, а не случайный defaults-пакет. Для NCM caller-supplied spec не принимается как основание: модель разрешается по WMR/CAS-ссылке. ProgramGraph plans отдельно разрешаются через настоящие graph/exec-plan/input/state owners. [Builder](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4830-L5008); [program-state owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4500-L4780).

В списке разрешённых engine kinds пять значений: `program_graph`, `ncm_parallel_worlds`, `coupled_des_abm`, `system_dynamics`, `method_registry_estimator`. Это **словарь поддерживаемого интерфейса**, не доказательство пяти успешно исполненных пользовательских путей. В частности, прочитанный GenericCycleN5RequestProfileV1 ограничен `ncm_parallel_worlds`; его не следует рекламировать как универсальный selector всех движков. [Profile DTO](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generic_simulation_admission.py#L85-L180).

Пустой baseline mapping здесь не заполняется нулевыми исходами. Defaults seed=0 и replications=1 — настройки вычислительной процедуры, а не выдуманные данные. Их допустимость и фактический расход реплик проверяются по соответствующему контексту, особенно SIM-03/B21, а не объявляются ошибкой только потому, что являются defaults.

### Как builder активируется

В `JointSimulationPort.__call__` сначала рассматриваются typed generic/candidate input routes. В обычной ветви сохранены совместимые пути callable factory и готового request, затем вызывается data-only builder при наличии соответствующего запроса его использования. Если нужный вход вообще не подготовлен, остаётся `joint_simulation_request_missing`. [Dispatch](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4020-L4270).

Следовательно, наличие builder устранило старое отсутствие возможности сборки, но **само не устанавливает**, что любой обычный NL-запрос теперь автоматически выбирает resource, horizon, comparator и существенные параметры. Это работа композиционного owner, не повод создать ещё одну третью функцию-сборщик.

Сохранённая внутренняя callable-ветвь не доказывает нарушение долговременного HTTP-контракта: надо показать её достижимость именно из serialized public input. Прочитанные configured served routes передают typed persisted input. Blanket-удаление всех внутренних callable API ради формальной чистоты не назначается.

### Реальное исполнение и долговременный вход

Порт действительно вызывает `_controller.run(request)` и затем `persist_joint_simulation_result`; он не заканчивает работу конструированием DTO. Для ProgramGraph сохраняются привязки реально потреблённого состояния; Generic request получает typed round-trip/binding. Ошибка persistence не превращается в успешно доставленный результат. [Вызов и запись](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L4270-L4475).

При этом в прочитанном коде для `joint_simulated` без generic request binding сохраняется ограничение `n5_execution_request_provenance_not_established`. Не надо снимать его ради зелёного статуса. Но и автоматически утверждать отсутствие всех внешних input artifacts нельзя: candidate V5 имеет отдельный persisted input/capture путь. Следующий проверяющий должен прочитать именно его фактический producer→reader контракт и установить, что воспроизводится. **Hash результата или надпись `joint_simulated` сами по себе не заменяют доступный точный вход расчёта.**

### Содержательное условие универсальности

Настоящая универсальность — не автоматически заполнить все missing поля любой ценой. Для нового вопроса система должна обнаружить подходящие данные/модель/метод, согласовать область и вычисляемую величину и либо построить разрешённый запрос, либо сообщить конкретный предметный пробел. Предварительный configured profile — полезная контрольная и внедренческая форма. Он не является доказательством, что такая сборка уже выполняется для ещё неизвестного кейса.

## 8. Разбор найденной положительной проверки

Рассмотрен основной setup и центральные assertions существующего:

`tests/integration/runtime_quality/test_configured_candidate_simulation_served.py::test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift`.

[Setup, 753–930](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L753-L930); [actual POST/N5/GET checks, 930–1240](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L930-L1240). **Тест в этом выпуске не запускался; его часть после строки 1240 не перечитана.**

| Участок | Что использует код теста | Какой смысл допустим |
|---|---|---|
| NL/LLM | Traced gateway с локальным protocol fixture и подготовленным recording; deterministic span-support | Проверка программной передачи/учёта; не оценка способности живой LLM понять новый вопрос |
| Модель и профиль | Подготовленный procurement profile и synthetic model declaration до POST | Явный контролируемый модельный случай; не эмпирическая пригодность модели мира |
| HTTP/job | Настоящий API, worker dispatch и временная SQLite/CAS-конфигурация с тестовой identity | Содержательный integration path; не боевое развёртывание и не институциональные полномочия |
| N5 | Обёртка наблюдения вызывает оригинальный `JointSimulationPort.__call__` | Это не mock, который сразу выдаёт `joint_simulated`; результат должен прийти от настоящего N5 |
| N8/N9 | На соответствующих owners установлены ловушки запрещённого вызова | Сохранение границы `candidate_scenario_n5_only`; положительный N8 этим тестом не доказывается |
| Fresh consumer | Новый GET парсится как RunDetailsResponse, проверяет точные refs | Доставка ограниченного результата и lineage, не только наличие файла |
| Meaning | `publication_authority=False`, currentness not established, K_sim/effect-basis limitations | Честное ограничение результата; не отсутствие полезного программного достижения |

Здесь есть материал, который следует беречь: ordinary request не содержит вручную изготовленного Python-context; связанный контекст строится server owner; реальный N5 вызывается; результат адресуется и читается публичным потребителем.

Одновременно **setup уже знает будущий кейс**: профиль выбора связан с подготовленным problem. Проверка подтверждает инфраструктурную возможность такого вычисления только при успешном реальном прогоне. Она не проверяет самостоятельно выведенный план для новой постановки и не вправе заменить собой проверку аналитической способности модели.

В просмотренной центральной части основные assertions относятся к status, lineage, exact refs и границам назначения. Независимая ожидаемая численная величина здесь не установлена чтением. Утверждать, что её нет нигде в оставшемся тесте или в sibling numerical tests, было бы неправильно. Для полной содержательной приёмки её нужно найти и связать с этим producer либо добавить малый независимый oracle в существующий тестовый контур, не повторять численную систему.

## 9. Полезные отрицательные пути, которые тоже надо сохранить

В том же файле тест `test_served_unknown_candidate_profile_keeps_persisted_n4_candidate` ожидает сохранённое предложение при отсутствии профиля, но прямо сохраняет N5/N8/N9/S8 как not_run. Это корректный частичный выход, не успешная симуляция. [Путь и assertions](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L205-L405).

`test_served_unrefreshable_profile_evidence_keeps_n4_and_blocks_n5` различает отсутствующий профиль и профиль, чьё основание невозможно актуализировать. Он сохраняет N4, сообщает `profile_refresh_unavailable` и не вызывает N5. [Основные assertions](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/tests/integration/runtime_quality/test_configured_candidate_simulation_served.py#L650-L752).

Эти тестовые конструкции не доказывают новый PASS без запуска, но хорошо задают защищаемое поведение. Нельзя улучшать метрику проходимости, выкидывая различие stale/missing или выдавая сохранённое предложение за рассчитанный эффект. Нельзя и уничтожать предложение только потому, что пока отсутствует допустимая симуляция.

## 10. Составной policy design: важное смежное ограничение

Прочитанный parent-joint builder отбирает реальные уникальные N4 source members и может построить гипотетический совместный запрос. Но код сам помечает их как **alternatives**, composition как not established и child-to-parent refinement как not established. [Parent builder](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py#L1220-L1555).

Это правильное различение. «Все варианты удалось одновременно запустить» ещё не означает «система спроектировала согласованную комбинацию политик». Альтернативные grants/taxes/rules могут конкурировать за один ресурс или быть взаимоисключающими. Снимать соответствующий limitation без производителя настоящего design-композиционного решения нельзя.

Здесь не назначается новый отдельный дефект и не блокируется вся приёмка CYC-01. Наблюдение передаётся в связанные задачи composition/SIM и общую оценку универсальности. Нынешний код уже честно удерживает эту границу — её нужно сохранить.

## 11. Точный остаток: что проверять и когда нужен код

| Остаток | Следующее конкретное действие | Когда назначать product change |
|---|---|---|
| Текущее runtime-прохождение не подтверждено этой проверкой | Исполнить указанный существующий served selector на supported runtime и точном source/input profile; прочитать полный вывод | Если обнаружится реальный разрыв, а не только несовместимость нашей среды |
| Не проверена переносимость на новый предмет | Второй кейс с другим содержанием/областью проходит тот же API; отдельно записать требуемые ручные input artifacts и новые ветки кода | Если нужные доступные ресурсы не разрешаются существующим discovery/composition owner |
| Request provenance может быть ограничена по типу producer | Разрешить сохранённый реальный input и повторно восстановить фактическую постановку через его текущего reader; проверить один meaningful drift | Если запрос или существенный параметр теряется на конкретной границе; не создавать второй общий receipt-format заранее |
| Контекст чужого узла/модели/каталога | При одном рабочем положительном пути заменить каждую существенную связь и проверить отказ до соответствующего использования | Если одна из уже имеющихся проверок действительно не защищает потребителя |
| Недостающий численный oracle в просмотренной части | Найти sibling numerical control и связать с actual selected N5; при отсутствии — один малый известный контраст | Если выяснится неверная численная семантика; само отсутствие oracle сначала задача проверки |
| Результат условный, N8/N9 не запускались | Сохранить полезный K_sim с ограничениями; downstream положительный N8 рассматривать в CYC-02/B05/B08 | Только в существующем value owner с его purpose contract; не очищать blockers целиком |

**Не назначается:** новый world store, новый запросный framework, переписывание всех owners, всеобщий повтор CI, снятие actor/resource guards, возврат family-authority, фиктивное нулевое основание или «общая автоматизация всего мира» как предусловие малого сценария.

## 12. Различающая приёмка без формального раздувания

**Рабочий положительный случай.** Один допустимый контролируемый запрос через настоящий HTTP и worker, без пользовательского Python-context. Existing owners строят input, N5 действительно считает известный простой пример, результат читается заново. Предпосылки и синтетическая природа модели видны.

**Защита основания.** От того же рабочего случая отклоняются чужой problem, WMR, selected registry/profile и source member. Незатронутый частичный результат и диагностическая причина сохраняются. Внешний доступ/бюджет не обходятся.

**Переносимость.** Другой предметный кейс использует тот же программный путь. Дополнительный datum, model или method может быть зарегистрирован через предусмотренный owner; нельзя заранее написать ветку под сам тест и назвать это discovery. Если нужен подготовленный профиль, он показывается как фактический вход и не обесценивает проверку ограниченного режима.

**Временная устойчивость.** Сохранённый вход и результат повторно читаются в их исторической версии. Новая существенная basis не заимствует старую currentness; незатронутые исторические bytes не переписываются. Полная вторая итерация — следующая CYC-03, не заявленный результат этого документа.

Первые два условия проверяют текущий ремонт CYC-01. Переносимость дополнительно проверяет направление универсального продукта. Научная валидность конкретной модели и право рекомендационного/внешнего использования остаются отдельными утверждениями с собственными основаниями.

## 13. Условия, при которых вывод изменится

Свежий положительный served прогон с отрицательными контролями позволит подтвердить ограниченную программную способность, а не просто исходный код. Второй независимый кейс, разрешаемый существующими индексами и owners без special-case ветки, усилит вывод о переносимости. Разбор фактического profile producer, показывающий автоматическое построение по вопросу, снимет нынешнюю неизвестность этой границы.

Наоборот, работающий только при подмене самого N5 успешным port, смешение selected refs при readback или восстановление чужого stale контекста отвергнут соответствующий результат. Отказ из-за действительно отсутствующей модели/права не будет объявлен программным дефектом. А отказ из-за не найденного, хотя доступного пригодного ресурса потребует ремонта discovery.

## 14. Передача в следующий пакет

CYC-03 должен ответить: может ли уже рассчитанный кандидат быть содержательно переоценён на новой версии данных или модели; как перевыпускается context; сохраняются ли старые occurrences и актуальный front. Наличие `reissue_handoff_for_problem` уже видно, но его достаточность для всех таких изменений этим проходом не установлена. [Существующий reissue owner](https://github.com/DenisKopylov/polisyos/blob/20d9009be21097bfbdc38a546a15cc60213b8ace/policy-engine/src/polisyos/runtime/quality/generic_simulation_admission.py#L945-L1140).

Начальная позиция следующего разбора: не строить новую identity-систему, а проследить текущие owners и настоящую последовательность двух итераций. ACQ-01 идёт после этого: новый источник полезен лишь тогда, когда зависимый расчёт действительно потребляет новое принятое основание.

## 15. Доказательная граница выпуска

Новый runtime-прогон — **UNRUN**. Нет утверждения о production authority, живом LLM-качестве, эмпирической корректности procurement-модели, закрытии CYC-02/SIM или универсальном обслуживании всех доменов. Отсутствие полного reread больших файлов не скрыто: [точные окна](../05_Источники/Репозиторные_основания.json), [найденные selectors и ограничения](../04_Проверки/CYC01/Чтение_и_границы.md).

Итог по CYC-01: **существенный существующий ремонт сохранить; первоначальные три барьера не переносить буквально на нынешний код; следующий расход направить на исполнение и проверку содержательной переносимости найденного пути, а не на очередную параллельную инфраструктуру.**
